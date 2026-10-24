"""Bounded, fixed-destination transport for Sevdesk and optional Google OAuth.

Adapters pass provider credentials only in headers or the fixed OAuth token POST.
No provider response text is included in a user-visible exception.
"""
from contextlib import contextmanager
from contextvars import ContextVar
from http.client import HTTPSConnection, HTTPException
import io
import json
import math
import re
import socket
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit, urlunsplit, unquote
from urllib.request import Request, HTTPRedirectHandler, HTTPSHandler, build_opener

from core import Problem


_DEADLINE = ContextVar("smartplan_integration_deadline", default=None)
MAX_RESPONSE = 20 * 1024 * 1024
MAX_JSON = 2 * 1024 * 1024
_ROOTS = {
    "sevdesk": "https://my.sevdesk.de/api/v1",
    "google_calendar": "https://www.googleapis.com",
}
_SEVDESK = re.compile(r"/(?:Contact|Order|Invoice|SevUser)(?:/[1-9][0-9]{0,19})?\Z")
_GOOGLE = re.compile(
    r"/calendar/v3/(?:users/me/calendarList(?:/[^/]+)?|calendars/[^/]+/events(?:/[^/]+)?)\Z"
)
_TOKEN_URLS = {
    "google_calendar": "https://oauth2.googleapis.com/token",
}
_SAFE_HEADERS = frozenset((
    "authorization", "accept", "content-type",
))


@contextmanager
def integration_deadline(seconds=18):
    """Share one monotonic deadline across discovery, refresh and pagination."""
    if not isinstance(seconds, (int, float)) or not 0 < seconds <= 18:
        raise ValueError("invalid integration deadline")
    previous = _DEADLINE.get()
    endpoint = time.monotonic() + seconds
    token = _DEADLINE.set(min(previous, endpoint) if previous is not None else endpoint)
    try:
        yield
    finally:
        _DEADLINE.reset(token)


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, message, headers, newurl):
        return None


class IntegrationAuthenticationRequired(Problem):
    def __init__(self):
        super().__init__(409, "Die Verbindung muss erneut autorisiert werden.")


class IntegrationPermissionDenied(Problem):
    def __init__(self):
        super().__init__(409, "Der Anbieter erlaubt den Zugriff auf diesen Eintrag nicht.")


def _upstream_error(status):
    if status == 401:
        return IntegrationAuthenticationRequired()
    if status == 403:
        return IntegrationPermissionDenied()
    if status == 429:
        return Problem(429, "Der Anbieter begrenzt die Abrufe. Bitte später erneut versuchen.")
    if status in (404, 410):
        return Problem(404, "Der gewählte Eintrag ist beim Anbieter nicht mehr verfügbar.")
    return Problem(503, "Der Anbieter ist vorübergehend nicht verfügbar.")


def _remaining(endpoint):
    remaining = endpoint - time.monotonic()
    if remaining <= 0:
        raise Problem(504, "Der Anbieter hat nicht rechtzeitig geantwortet.")
    return min(8.0, remaining)


class _DeadlineReader(io.RawIOBase):
    """Apply the total deadline even inside HTTPResponse's header readline."""
    def __init__(self, raw, connection, endpoint):
        self.raw, self.connection, self.endpoint = raw, connection, endpoint

    def readable(self):
        return True

    def readinto(self, buffer):
        self.connection.settimeout(_remaining(self.endpoint))
        result = self.raw.readinto(buffer)
        _remaining(self.endpoint)
        return result

    def close(self):
        try:
            self.raw.close()
        finally:
            super().close()


class _DeadlineSocket:
    def __init__(self, connection, endpoint):
        self.connection, self.endpoint = connection, endpoint

    def __getattr__(self, name):
        return getattr(self.connection, name)

    def sendall(self, data, *args, **kwargs):
        self.connection.settimeout(_remaining(self.endpoint))
        result = self.connection.sendall(data, *args, **kwargs)
        _remaining(self.endpoint)
        return result

    def makefile(self, mode, *args, **kwargs):
        if mode != "rb" or args or kwargs:
            raise OSError("unsupported integration socket reader")
        return io.BufferedReader(_DeadlineReader(
            self.connection.makefile("rb", buffering=0), self.connection, self.endpoint))


class _DeadlineConnection:
    def __init__(self, *args, endpoint, **kwargs):
        self.endpoint = endpoint
        super().__init__(*args, **kwargs)

    def connect(self):
        super().connect()
        self.sock = _DeadlineSocket(self.sock, self.endpoint)


class _DeadlineHTTPSConnection(_DeadlineConnection, HTTPSConnection):
    pass


class _DeadlineHTTPSHandler(HTTPSHandler):
    def https_open(self, request):
        return self.do_open(
            lambda host, **kwargs: _DeadlineHTTPSConnection(host,
                endpoint=request.smartplan_deadline, **kwargs),
            request, context=self._context)


def _read_timeout(response, seconds):
    # HTTPResponse -> BufferedReader -> SocketIO -> socket. Synthetic openers do
    # not need this; live TLS reads must obey the remaining operation deadline.
    fp = getattr(response, "fp", None)
    raw = getattr(fp, "raw", None)
    connection = getattr(raw, "_sock", None)
    if connection is not None:
        connection.settimeout(seconds)


def _json_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError()
        result[key] = value
    return result


def _json_shape(result):
    pending, count = [(result, 0)], 0
    while pending:
        value, depth = pending.pop()
        count += 1
        if depth > 64 or count > 100000:
            raise ValueError()
        if isinstance(value, dict):
            pending.extend((item, depth + 1) for item in value.values())
        elif isinstance(value, list):
            pending.extend((item, depth + 1) for item in value)
        elif isinstance(value, float) and not math.isfinite(value):
            raise ValueError()


class IntegrationHttp:
    def __init__(self, provider, *, opener=None):
        if provider not in _ROOTS:
            raise ValueError("unknown integration provider")
        self.provider = provider
        self.opener = opener if opener is not None else build_opener(_NoRedirect(), _DeadlineHTTPSHandler())

    def _url(self, path, method, params, has_form):
        if not isinstance(path, str) or not path or len(path) > 8192:
            raise Problem(400, "Ungültiger Anbieterpfad.")
        try:
            parsed = urlsplit(path)
        except ValueError:
            raise Problem(400, "Ungültiger Anbieterpfad.") from None
        is_token = path == _TOKEN_URLS.get(self.provider)
        if parsed.scheme or parsed.netloc:
            if not is_token:
                raise Problem(400, "Nicht erlaubtes Anbieterziel.")
            url = path
        else:
            if parsed.query or parsed.fragment or not path.startswith("/") or path.startswith("//"):
                raise Problem(400, "Ungültiger Anbieterpfad.")
            decoded = unquote(path)
            if any(ord(c) < 32 for c in decoded) or "\\" in decoded or any(p in (".", "..") for p in decoded.split("/")):
                raise Problem(400, "Ungültiger Anbieterpfad.")
            allowed = ((self.provider == "sevdesk" and bool(_SEVDESK.fullmatch(path))) or
                       (self.provider == "google_calendar" and bool(_GOOGLE.fullmatch(path))))
            if not allowed:
                raise Problem(400, "Nicht erlaubter Anbieterpfad.")
            url = _ROOTS[self.provider] + path
        required_method = "POST" if is_token else "GET"
        if method != required_method or (has_form and not is_token) or (is_token and not has_form):
            raise Problem(400, "Nicht erlaubte Anbieteroperation.")
        if params is not None and not isinstance(params, dict):
            raise Problem(400, "Ungültige Anbieterparameter.")
        if params:
            if is_token or not isinstance(params, dict) or len(params) > 40:
                raise Problem(400, "Ungültige Anbieterparameter.")
            forbidden = {"access_token", "refresh_token", "api_key", "token", "authorization", "client_secret", "code"}
            for key, value in params.items():
                if not isinstance(key, str) or key.lower() in forbidden or not isinstance(value, (str, int, bool)) or len(str(value)) > 8192:
                    raise Problem(400, "Ungültige Anbieterparameter.")
            query = urlencode(params)
            if len(query) > 16384:
                raise Problem(400, "Zu viele Anbieterparameter.")
            parts = urlsplit(url)
            url = urlunsplit((parts.scheme, parts.netloc, parts.path, query, ""))
        return url

    def raw(self, path, *, method="GET", params=None, json_body=None, form=None,
            headers=None, max_bytes=MAX_JSON):
        if type(max_bytes) is not int or not 0 < max_bytes <= MAX_RESPONSE:
            raise Problem(400, "Ungültige Antwortgrenze.")
        if json_body is not None and form is not None:
            raise Problem(400, "Ungültiger Anbieterauftrag.")
        if headers is not None and not isinstance(headers, dict):
            raise Problem(400, "Ungültige Anbieter-Header.")
        if form is not None and (not isinstance(form, dict) or len(form) > 20 or
                any(not isinstance(key, str) or not isinstance(value, str) or
                    len(key) > 200 or len(value) > 16384 for key, value in form.items())):
            raise Problem(400, "Ungültiger Anbieterauftrag.")
        url = self._url(path, method, params, form is not None)
        if self.provider == "sevdesk" and (json_body is not None or form is not None):
            raise Problem(400, "Sevdesk wird ausschließlich lesend verwendet.")
        if self.provider == "google_calendar" and json_body is not None:
            raise Problem(400, "Nicht erlaubte Anbieteroperation.")
        outgoing = {"Accept": "application/json"}
        for key, value in (headers or {}).items():
            if not isinstance(key, str) or key.lower() not in _SAFE_HEADERS or not isinstance(value, str) or not value or len(value) > 16384 or any(ord(c) < 32 or ord(c) > 126 for c in value):
                raise Problem(400, "Ungültige Anbieter-Header.")
            outgoing[key] = value
        try:
            data = (urlencode(form).encode("ascii") if form is not None else
                    json.dumps(json_body, allow_nan=False, separators=(",", ":")).encode("utf-8") if json_body is not None else None)
        except (TypeError, ValueError, UnicodeError):
            raise Problem(400, "Ungültiger Anbieterauftrag.") from None
        if data is not None:
            if len(data) > 128 * 1024:
                raise Problem(400, "Der Anbieterauftrag ist zu groß.")
            outgoing["Content-Type"] = "application/x-www-form-urlencoded" if form is not None else "application/json"
        endpoint = _DEADLINE.get()
        if endpoint is None:
            endpoint = time.monotonic() + 18
        response = None
        try:
            request = Request(url, data=data, headers=outgoing, method=method)
            request.smartplan_deadline = endpoint
            response = self.opener.open(request, timeout=_remaining(endpoint))
            status = getattr(response, "status", None)
            if status is None:
                status = response.getcode()
            if not 200 <= status < 300:
                raise _upstream_error(status)
            result_headers = {str(k).lower(): str(v) for k, v in response.headers.items()}
            advertised = result_headers.get("content-length")
            if advertised is not None and (not advertised.isdigit() or int(advertised) > max_bytes):
                raise Problem(503, "Die Anbieterantwort überschreitet die zulässige Größe.")
            chunks = []
            size = 0
            while True:
                _read_timeout(response, _remaining(endpoint))
                chunk = response.read(min(65536, max_bytes + 1 - size))
                _remaining(endpoint)
                if not chunk:
                    break
                size += len(chunk)
                if size > max_bytes:
                    raise Problem(503, "Die Anbieterantwort überschreitet die zulässige Größe.")
                chunks.append(chunk)
            if advertised is not None and size != int(advertised):
                raise Problem(503, "Die Anbieterantwort ist unvollständig.")
            return b"".join(chunks), result_headers
        except HTTPError as error:
            if error.code == 400 and url in _TOKEN_URLS.values():
                try:
                    _read_timeout(error.fp, _remaining(endpoint))
                    body = error.read(8193)
                    _remaining(endpoint)
                    if len(body) <= 8192:
                        value = json.loads(body.decode("utf-8"), object_pairs_hook=_json_object)
                        if isinstance(value, dict) and value.get("error") in ("invalid_grant", "invalid_client", "unauthorized_client"):
                            raise IntegrationAuthenticationRequired()
                except (ValueError, UnicodeError, OSError, RecursionError):
                    pass
                finally:
                    error.close()
            else:
                error.close()
            raise _upstream_error(error.code) from None
        except (TimeoutError, socket.timeout):
            raise Problem(504, "Der Anbieter hat nicht rechtzeitig geantwortet.") from None
        except URLError as error:
            if isinstance(error.reason, (TimeoutError, socket.timeout)):
                raise Problem(504, "Der Anbieter hat nicht rechtzeitig geantwortet.") from None
            raise Problem(503, "Der Anbieter ist vorübergehend nicht verfügbar.") from None
        except (OSError, ValueError, HTTPException):
            raise Problem(503, "Der Anbieter ist vorübergehend nicht verfügbar.") from None
        finally:
            if response is not None:
                response.close()

    def call(self, path, *, method="GET", params=None, json_body=None, form=None,
             headers=None, max_bytes=MAX_JSON):
        if type(max_bytes) is not int or not 0 < max_bytes <= MAX_JSON:
            raise Problem(400, "Ungültige JSON-Antwortgrenze.")
        body, response_headers = self.raw(path, method=method, params=params,
            json_body=json_body, form=form, headers=headers, max_bytes=max_bytes)
        media_type = response_headers.get("content-type", "").split(";", 1)[0].strip().lower()
        if media_type != "application/json" and not media_type.endswith("+json"):
            raise Problem(503, "Der Anbieter hat keine gültigen Daten geliefert.")
        try:
            result = json.loads(body.decode("utf-8"), object_pairs_hook=_json_object,
                                parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
            if not isinstance(result, (dict, list)):
                raise ValueError()
            _json_shape(result)
            return result
        except (ValueError, UnicodeError, RecursionError):
            raise Problem(503, "Der Anbieter hat keine gültigen Daten geliefert.") from None

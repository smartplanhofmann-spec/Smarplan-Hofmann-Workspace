"""Read-only Google Calendar adapter; no database, event writes or invitations.

OAuth credentials stay in the caller's server vault. Provider traffic uses the
fixed-destination transport, and every public operation shares one deadline.
"""
from datetime import date, datetime, timedelta, timezone
from functools import wraps
import json
import re
from urllib.parse import quote, urlencode, urlsplit
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from core import Problem
from online.integration_http import (
    IntegrationAuthenticationRequired, IntegrationHttp, IntegrationPermissionDenied,
    integration_deadline,
)


SCOPES = (
    "https://www.googleapis.com/auth/calendar.calendarlist.readonly",
    "https://www.googleapis.com/auth/calendar.events.readonly",
)
AUTHORIZE_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
PREVIEW_DAYS_PAST = 31
PREVIEW_DAYS_FUTURE = 366
MAX_PAGES = 5
PAGE_SIZE = 100
MAX_SELECTED_EVENTS = 50
MAX_NORMALIZED_BYTES = 2 * 1024 * 1024
_CALENDARS = "/calendar/v3/users/me/calendarList"
_CALENDAR_FIELDS = "id,summary,summaryOverride,timeZone,accessRole,deleted"
_EVENT_FIELDS = "id,summary,description,start,end,location,status,htmlLink"
_RFC3339 = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})?\Z")
_DATE = re.compile(r"\d{4}-\d{2}-\d{2}\Z")


def _bad_response():
    return Problem(503, "Google Kalender hat keine gültigen Kalenderdaten geliefert.")


def _text(value, *, maximum=4096, optional=False):
    if value is None and optional:
        return ""
    if (not isinstance(value, str) or len(value) > maximum or
            any(ord(c) < 32 and c not in "\n\r\t" for c in value)):
        raise _bad_response()
    return value


def _identifier(value, *, input_value=False):
    if (not isinstance(value, str) or not value or len(value) > 1024 or
            value in (".", "..") or any(c in value for c in "/\\") or
            any(ord(c) < 33 or ord(c) == 127 for c in value)):
        if input_value:
            raise Problem(400, "Ungültige Google-Kalenderauswahl.")
        raise _bad_response()
    return value


def _secret(value, *, input_value=False):
    if (not isinstance(value, str) or not 1 <= len(value) <= 16384 or
            any(ord(c) < 33 or ord(c) > 126 for c in value)):
        if input_value:
            raise Problem(400, "Die Google-Verbindung ist nicht vollständig eingerichtet.")
        raise _bad_response()
    return value


def _config(config):
    if not isinstance(config, dict):
        raise Problem(400, "Die Google-Verbindung ist nicht vollständig eingerichtet.")
    return (_secret(config.get("client_id"), input_value=True),
            _secret(config.get("client_secret"), input_value=True))


def _redirect(value):
    if not isinstance(value, str) or len(value) > 2048:
        raise Problem(400, "Ungültige Google-Rücksprungadresse.")
    try:
        parsed = urlsplit(value)
        valid = (parsed.scheme == "https" and parsed.hostname and
                 parsed.username is None and parsed.password is None and
                 parsed.port in (None, 443) and not parsed.query and
                 not parsed.fragment and parsed.path.startswith("/") and
                 not any(ord(c) < 33 or ord(c) > 126 for c in value))
    except ValueError:
        valid = False
    if not valid:
        raise Problem(400, "Ungültige Google-Rücksprungadresse.")
    return value


def _zone(value):
    if value is None:
        return None
    if not isinstance(value, str) or not value or len(value) > 128:
        raise _bad_response()
    try:
        ZoneInfo(value)
    except (ZoneInfoNotFoundError, ValueError):
        raise _bad_response() from None
    return value


def _instant(value, zone):
    if not isinstance(value, str) or not _RFC3339.fullmatch(value):
        raise _bad_response()
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            if zone is None:
                raise ValueError()
            local = ZoneInfo(zone)
            first = parsed.replace(tzinfo=local, fold=0)
            second = parsed.replace(tzinfo=local, fold=1)
            # Never guess a missing offset in a DST overlap or gap.
            if (first.utcoffset() != second.utcoffset() or
                    first.astimezone(timezone.utc).astimezone(local).replace(tzinfo=None) != parsed):
                raise ValueError()
            parsed = first
        if parsed.utcoffset() is None:
            raise ValueError()
        return parsed
    except (ValueError, OverflowError):
        raise _bad_response() from None


def _calendar(value, *, expected=None):
    if not isinstance(value, dict):
        raise _bad_response()
    if value.get("deleted") is True:
        raise Problem(404, "Der gewählte Google-Kalender ist nicht mehr verfügbar.")
    identifier = _identifier(value.get("id"))
    if expected not in (None, "primary", identifier):
        raise _bad_response()
    role = value.get("accessRole")
    if role in ("none", "freeBusyReader"):
        raise IntegrationPermissionDenied()
    if role not in ("reader", "writer", "owner"):
        raise _bad_response()
    name = _text(value.get("summaryOverride") or value.get("summary"), optional=True)
    return {"id": identifier, "name": name or identifier,
            "time_zone": _zone(value.get("timeZone"))}


def _calendar_url(value):
    if value is None:
        return None
    if not isinstance(value, str) or len(value) > 8192:
        raise _bad_response()
    try:
        parsed = urlsplit(value)
        valid = (parsed.scheme == "https" and
                 parsed.hostname in ("www.google.com", "calendar.google.com") and
                 parsed.username is None and parsed.password is None and
                 parsed.port in (None, 443) and parsed.path.startswith("/calendar/") and
                 not any(ord(c) < 33 or ord(c) > 126 for c in value))
    except ValueError:
        valid = False
    return value if valid else None


def _event(value, *, calendar_zone, expected=None):
    if not isinstance(value, dict):
        raise _bad_response()
    identifier = _identifier(value.get("id"))
    if expected is not None and identifier != expected:
        raise _bad_response()
    status = value.get("status")
    if status not in ("confirmed", "tentative", "cancelled"):
        raise _bad_response()
    start, end = value.get("start"), value.get("end")
    start_value = end_value = all_day = None
    zone = calendar_zone
    if status != "cancelled" or (start is not None and end is not None):
        if not isinstance(start, dict) or not isinstance(end, dict):
            raise _bad_response()
        start_zone = _zone(start.get("timeZone")) or calendar_zone
        end_zone = _zone(end.get("timeZone")) or start_zone
        zone = start_zone
        if "date" in start and "date" in end and "dateTime" not in start and "dateTime" not in end:
            start_value, end_value = start["date"], end["date"]
            try:
                if (not isinstance(start_value, str) or not isinstance(end_value, str) or
                        not _DATE.fullmatch(start_value) or not _DATE.fullmatch(end_value) or
                        date.fromisoformat(end_value) <= date.fromisoformat(start_value)):
                    raise ValueError()
            except ValueError:
                raise _bad_response() from None
            all_day = True
        elif "dateTime" in start and "dateTime" in end and "date" not in start and "date" not in end:
            first = _instant(start["dateTime"], start_zone)
            last = _instant(end["dateTime"], end_zone)
            if last <= first:
                raise _bad_response()
            start_value, end_value = first.isoformat(), last.isoformat()
            all_day = False
        else:
            raise _bad_response()
    title = _text(value.get("summary"), maximum=2048, optional=True)
    return {
        "id": identifier, "title": title or ("Entfernter Termin" if status == "cancelled" else "Ohne Titel"),
        "description": _text(value.get("description"), maximum=32768, optional=True),
        "start": start_value, "end": end_value, "all_day": all_day,
        "time_zone": zone, "location": _text(value.get("location"), optional=True),
        "status": status, "url": _calendar_url(value.get("htmlLink")),
    }


class GoogleCalendarProvider:
    def __init__(self, http=None, *, clock=None):
        http = http if http is not None else IntegrationHttp("google_calendar")
        self.http = http.call if hasattr(http, "call") else http
        self.clock = clock or (lambda: datetime.now(timezone.utc))

    def authorization_url(self, config, state, challenge, redirect):
        client_id, _ = _config(config)
        if (not isinstance(state, str) or not re.fullmatch(r"[A-Za-z0-9._~-]{16,512}", state) or
                not isinstance(challenge, str) or not re.fullmatch(r"[A-Za-z0-9_-]{43}", challenge)):
            raise Problem(400, "Die Google-Anmeldung konnte nicht vorbereitet werden.")
        return AUTHORIZE_URL + "?" + urlencode({
            "client_id": client_id, "redirect_uri": _redirect(redirect), "response_type": "code",
            "scope": " ".join(SCOPES), "state": state, "access_type": "offline",
            "prompt": "consent", "include_granted_scopes": "false",
            "code_challenge": challenge, "code_challenge_method": "S256",
        })

    def _tokens(self, response, *, refresh_token=None):
        if not isinstance(response, dict):
            raise _bad_response()
        if not isinstance(response.get("token_type"), str) or response["token_type"].lower() != "bearer":
            raise _bad_response()
        access = _secret(response.get("access_token"))
        lifetime = response.get("expires_in")
        if type(lifetime) is not int or not 1 <= lifetime <= 86400:
            raise _bad_response()
        scope = response.get("scope")
        if scope is None and refresh_token is not None:
            scope = " ".join(SCOPES)  # OAuth refresh may omit the unchanged scope.
        if (not isinstance(scope, str) or len(scope) > 4096 or set(scope.split()) != set(SCOPES)):
            raise IntegrationAuthenticationRequired()
        refresh = _secret(response.get("refresh_token", refresh_token))
        result = {"access_token": access, "refresh_token": refresh, "expires_in": lifetime,
                  "token_type": "Bearer", "scope": " ".join(SCOPES)}
        if "refresh_token_expires_in" in response:
            remaining = response["refresh_token_expires_in"]
            if type(remaining) is not int or not 1 <= remaining <= 2147483647:
                raise _bad_response()
            result["refresh_token_expires_in"] = remaining
        return result

    def exchange(self, config, code, verifier, redirect):
        client_id, client_secret = _config(config)
        code = _secret(code, input_value=True)
        if not isinstance(verifier, str) or not re.fullmatch(r"[A-Za-z0-9._~-]{43,128}", verifier):
            raise Problem(400, "Die Google-Anmeldung konnte nicht bestätigt werden.")
        with integration_deadline():
            return self._tokens(self.http(TOKEN_URL, method="POST", max_bytes=65536, form={
                "client_id": client_id, "client_secret": client_secret, "code": code,
                "code_verifier": verifier, "redirect_uri": _redirect(redirect),
                "grant_type": "authorization_code",
            }))

    def refresh(self, config, refresh_token):
        client_id, client_secret = _config(config)
        refresh_token = _secret(refresh_token, input_value=True)
        with integration_deadline():
            return self._tokens(self.http(TOKEN_URL, method="POST", max_bytes=65536, form={
                "client_id": client_id, "client_secret": client_secret,
                "refresh_token": refresh_token, "grant_type": "refresh_token",
            }), refresh_token=refresh_token)

    def _get(self, access_token, path, params):
        return self.http(path, params=params,
                         headers={"Authorization": "Bearer " + _secret(access_token, input_value=True)})

    def _selected_calendar(self, access_token, calendar_id):
        calendar_id = _identifier(calendar_id, input_value=True)
        result = self._get(access_token, _CALENDARS + "/" + quote(calendar_id, safe=""),
                           {"fields": _CALENDAR_FIELDS})
        return _calendar(result, expected=calendar_id)

    def identity(self, access_token):
        with integration_deadline():
            calendar = self._selected_calendar(access_token, "primary")
            return {"id": calendar["id"], "label": calendar["name"]}

    def _pages(self, access_token, path, params):
        tokens = set()
        for _ in range(MAX_PAGES):
            result = self._get(access_token, path, params)
            if not isinstance(result, dict) or not isinstance(result.get("items", []), list):
                raise _bad_response()
            items = result.get("items", [])
            if len(items) > PAGE_SIZE:
                raise _bad_response()
            yield result, items
            token = result.get("nextPageToken")
            if token is None or token == "":
                return
            if (not isinstance(token, str) or len(token) > 4096 or
                    any(ord(c) < 33 or ord(c) > 126 for c in token) or token in tokens):
                raise _bad_response()
            tokens.add(token)
            params = {**params, "pageToken": token}
        raise Problem(413, "Die Google-Kalenderauswahl ist zu umfangreich. Bitte einen kleineren Kalender auswählen.")

    @staticmethod
    def _append(items, seen, value, size):
        identifier = value["id"]
        if identifier in seen:
            if seen[identifier] != value:
                raise _bad_response()
            return size
        size += len(json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8")) + bool(items)
        if size > MAX_NORMALIZED_BYTES:
            raise Problem(413, "Die Google-Kalenderdaten sind zu umfangreich.")
        seen[identifier] = value
        items.append(value)
        return size

    def calendars(self, access_token):
        with integration_deadline():
            calendars, seen, size = [], {}, 2
            for _, items in self._pages(access_token, _CALENDARS, {
                "maxResults": PAGE_SIZE, "minAccessRole": "reader",
                "showDeleted": "false", "showHidden": "false",
                "fields": "nextPageToken,items(" + _CALENDAR_FIELDS + ")",
            }):
                for value in items:
                    if isinstance(value, dict) and value.get("deleted") is True:
                        continue
                    size = self._append(calendars, seen, _calendar(value), size)
            return calendars

    def events(self, access_token, calendar_id):
        with integration_deadline():
            calendar = self._selected_calendar(access_token, calendar_id)
            now = self.clock().astimezone(timezone.utc).replace(microsecond=0)
            stamp = lambda day: day.isoformat().replace("+00:00", "Z")
            path = "/calendar/v3/calendars/" + quote(calendar["id"], safe="") + "/events"
            events, seen, size = [], {}, 2
            for result, items in self._pages(access_token, path, {
                "maxResults": PAGE_SIZE, "singleEvents": "true", "showDeleted": "true",
                "orderBy": "startTime", "timeMin": stamp(now - timedelta(days=PREVIEW_DAYS_PAST)),
                "timeMax": stamp(now + timedelta(days=PREVIEW_DAYS_FUTURE)),
                "fields": "nextPageToken,timeZone,items(" + _EVENT_FIELDS + ")",
            }):
                zone = _zone(result.get("timeZone")) or calendar["time_zone"]
                for value in items:
                    size = self._append(events, seen, _event(value, calendar_zone=zone), size)
            return events

    def snapshot(self, access_token, link):
        if not isinstance(link, dict):
            raise Problem(400, "Ungültige Google-Kalenderauswahl.")
        calendar_id = _identifier(link.get("calendar_id"), input_value=True)
        identifiers = link.get("event_ids")
        if not isinstance(identifiers, list) or len(identifiers) > MAX_SELECTED_EVENTS:
            raise Problem(400, "Bitte höchstens 50 Google-Termine auswählen.")
        identifiers = [_identifier(value, input_value=True) for value in identifiers]
        if len(set(identifiers)) != len(identifiers):
            raise Problem(400, "Ein Google-Termin darf nur einmal ausgewählt werden.")
        with integration_deadline():
            calendar = self._selected_calendar(access_token, calendar_id)
            path = "/calendar/v3/calendars/" + quote(calendar["id"], safe="") + "/events/"
            events, seen, size = [], {}, 2
            for identifier in identifiers:
                try:
                    value = self._get(access_token, path + quote(identifier, safe=""), {"fields": _EVENT_FIELDS})
                except Problem as error:
                    if error.status not in (404, 410):
                        raise
                    value = {"id": identifier, "status": "cancelled"}
                size = self._append(events, seen, _event(value, calendar_zone=calendar["time_zone"], expected=identifier), size)
            return {"calendar": calendar, "events": events}


def _bridge_bad():
    return Problem(400, "Die gelieferten Google-Kalenderdaten sind unvollständig oder ungültig.")


def _bridge_errors(normalize):
    @wraps(normalize)
    def checked(*args, **kwargs):
        try:
            return normalize(*args, **kwargs)
        except Problem as error:
            if error.status == 503:
                raise _bridge_bad() from None
            raise
    return checked


def _bridge_payload(payload):
    if not isinstance(payload, dict) or payload.get("complete") is not True:
        raise _bridge_bad()
    # A complete flag cannot override an explicitly incomplete/paged result.
    if any(payload.get(key) is not None and payload.get(key) is not False
           for key in ("has_more", "pending", "truncated")):
        raise _bridge_bad()
    if any(payload.get(key) not in (None, "") for key in ("nextPageToken", "next_page_token", "next_link", "@odata.nextLink")):
        raise _bridge_bad()
    try:
        encoded = json.dumps(payload, ensure_ascii=False, allow_nan=False, separators=(",", ":")).encode("utf-8")
    except (TypeError, ValueError, UnicodeError, RecursionError):
        raise _bridge_bad() from None
    if len(encoded) > MAX_NORMALIZED_BYTES:
        raise Problem(413, "Die gelieferten Google-Kalenderdaten sind zu umfangreich.")
    return payload


def _bridge_nonempty(value, maximum):
    value = _text(value, maximum=maximum)
    if not value.strip():
        raise _bridge_bad()
    return value


def _bridge_calendar(value, *, expected=None):
    if not isinstance(value, dict) or not {"id", "name", "time_zone"} <= value.keys():
        raise _bridge_bad()
    identifier = _identifier(value["id"])
    if expected is not None and identifier != expected:
        raise _bridge_bad()
    # The bot supplied source metadata, not a native OAuth/accessRole proof.
    return {"id": identifier, "name": _bridge_nonempty(value["name"], 4096),
            "time_zone": _zone(value["time_zone"])}


def _bridge_event(value, *, calendar_zone):
    if not isinstance(value, dict):
        raise _bridge_bad()
    identifier = _identifier(value.get("id"))
    status = value.get("status")
    if status in ("not_found", "notfound"):
        if any(value.get(key) is not None for key in ("start", "end", "all_day")):
            raise _bridge_bad()
        status = "cancelled"
    if status not in ("confirmed", "tentative", "cancelled"):
        raise _bridge_bad()
    start, end, all_day = value.get("start"), value.get("end"), value.get("all_day")
    zone = _zone(value.get("time_zone"))
    tombstone = status == "cancelled" and start is None and end is None and all_day is None
    if not tombstone and (type(all_day) is not bool or start is None or end is None):
        raise _bridge_bad()
    if status in ("confirmed", "tentative"):
        _bridge_nonempty(value.get("title"), 2048)
    url = _calendar_url(value.get("url"))
    if value.get("url") is not None and url is None:
        raise _bridge_bad()
    raw = {
        "id": identifier, "status": status, "summary": value.get("title"),
        "description": value.get("description"), "location": value.get("location"), "htmlLink": url,
    }
    if not tombstone:
        field = "date" if all_day else "dateTime"
        raw["start"] = {field: start, "timeZone": zone}
        raw["end"] = {field: end, "timeZone": zone}
    return _event(raw, calendar_zone=calendar_zone)


def _bridge_resource(payload, selection, limit):
    payload = _bridge_payload(payload)
    if not isinstance(selection, dict):
        raise _bridge_bad()
    calendar_id = _identifier(selection.get("calendar_id"), input_value=True)
    calendar = _bridge_calendar(payload.get("calendar"), expected=calendar_id)
    supplied = payload.get("events")
    if not isinstance(supplied, list):
        raise _bridge_bad()
    if len(supplied) > limit:
        raise Problem(413, "Es wurden zu viele Google-Termine geliefert.")
    events, seen = [], set()
    for value in supplied:
        event = _bridge_event(value, calendar_zone=calendar["time_zone"])
        if event["id"] in seen:
            raise _bridge_bad()
        seen.add(event["id"])
        events.append(event)
    return {"calendar": calendar, "events": events}


@_bridge_errors
def normalize_bridge_catalog(payload):
    """Validate complete source metadata without connecting to Google.

    The caller binds identity.id to its existing bot account/generation; this
    pure helper cannot prove OAuth ownership or compare a previous connection.
    """
    payload = _bridge_payload(payload)
    identity = payload.get("identity")
    if not isinstance(identity, dict):
        raise _bridge_bad()
    identity = {"id": _identifier(identity.get("id")),
                "label": _bridge_nonempty(identity.get("label"), 512)}
    supplied = payload.get("calendars")
    if not isinstance(supplied, list):
        raise _bridge_bad()
    if len(supplied) > 1000:
        raise Problem(413, "Es wurden zu viele Google-Kalender geliefert.")
    calendars, seen = [], set()
    for value in supplied:
        calendar = _bridge_calendar(value)
        if calendar["id"] in seen:
            raise _bridge_bad()
        seen.add(calendar["id"])
        calendars.append(calendar)
    return {"identity": identity, "calendars": calendars}


@_bridge_errors
def normalize_bridge_resource(payload, selection):
    """Validate a complete calendar selection preview, bounded to 500 events."""
    return _bridge_resource(payload, selection, MAX_PAGES * PAGE_SIZE)


@_bridge_errors
def normalize_bridge_snapshot(payload, selection):
    """Require an explicit source record/tombstone for every selected event."""
    if not isinstance(selection, dict) or not isinstance(selection.get("event_ids"), list):
        raise _bridge_bad()
    identifiers = selection["event_ids"]
    if len(identifiers) > MAX_SELECTED_EVENTS:
        raise Problem(413, "Bitte höchstens 50 Google-Termine auswählen.")
    identifiers = [_identifier(value, input_value=True) for value in identifiers]
    if len(set(identifiers)) != len(identifiers):
        raise _bridge_bad()
    result = _bridge_resource(payload, selection, MAX_SELECTED_EVENTS)
    events = {event["id"]: event for event in result["events"]}
    if set(events) != set(identifiers):
        raise _bridge_bad()
    result["events"] = [events[identifier] for identifier in identifiers]
    return result

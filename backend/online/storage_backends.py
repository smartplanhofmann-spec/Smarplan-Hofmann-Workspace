"""Document-storage adapters; authorization and receipts belong to the service.

Destinations are trusted server configuration, never values from a report or an
upload request. A NAS can be mounted as server storage or exposed through its
HTTPS WebDAV endpoint. These adapters neither publish links nor manage the
Smartplan database.
"""
import base64
from contextvars import ContextVar
import fcntl
import ipaddress
import os
from pathlib import PurePosixPath
import re
import secrets
import stat
import time
import urllib.error
import urllib.parse
import urllib.request

from core import Problem


IDENTIFIER = re.compile(r'[a-f0-9]{32}')
MAX_PDF_BYTES = 25 * 1024 * 1024
WEBDAV_BUDGET_SECONDS = 18
_webdav_deadline = ContextVar('smartplan_webdav_deadline', default=None)


def _document(project_id, report_id, pdf_bytes):
    if (not isinstance(project_id, str) or not IDENTIFIER.fullmatch(project_id)
            or not isinstance(report_id, str) or not IDENTIFIER.fullmatch(report_id)):
        raise Problem(400, 'Ungültige Dokumentzuordnung')
    if (not isinstance(pdf_bytes, bytes) or not pdf_bytes.startswith(b'%PDF-')
            or not 5 < len(pdf_bytes) <= MAX_PDF_BYTES):
        raise Problem(400, 'Gültiges PDF für die Ablage erforderlich')
    return report_id + '.pdf'


def _private_directory(descriptor):
    information = os.fstat(descriptor)
    if (not stat.S_ISDIR(information.st_mode)
            or information.st_uid != os.geteuid()
            or information.st_mode & 0o077):
        raise Problem(409, 'Das Ablageverzeichnis muss dem Dienst gehören und privat sein')


class ServerStorage:
    """Private server directory, optionally on an administrator-mounted disk.

    Directory file descriptors and O_NOFOLLOW prevent path/symlink traversal.
    A completed document is published by linking a fully flushed temporary file
    to its final name, never by replacing a pre-existing file. The destination
    filesystem therefore needs normal POSIX locking and hard-link support.
    """

    def __init__(self, base_path):
        self.base_path = os.fspath(base_path) if base_path is not None else ''

    def configured(self):
        return bool(isinstance(self.base_path, str)
                    and self.base_path.startswith('/') and self.base_path != '/'
                    and '\x00' not in self.base_path
                    and all(part not in ('.', '..')
                            for part in self.base_path.split('/')))

    def status(self):
        return {'provider': 'server', 'account_type': 'server',
                'configured': self.configured()}

    def _open_root(self):
        if not self.configured():
            raise Problem(409, 'Serverablage noch nicht eingerichtet')
        components = PurePosixPath(self.base_path).parts[1:]
        flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC
        descriptor = os.open('/', flags)
        try:
            for index, component in enumerate(components):
                try:
                    child = os.open(component, flags, dir_fd=descriptor)
                except FileNotFoundError:
                    # The trusted administrator prepares the parent/mount. The
                    # adapter may create its own final directory, not ancestors.
                    if index != len(components) - 1:
                        raise
                    try:
                        os.mkdir(component, 0o700, dir_fd=descriptor)
                    except FileExistsError:
                        pass
                    child = os.open(component, flags, dir_fd=descriptor)
                os.close(descriptor)
                descriptor = child
            _private_directory(descriptor)
            return descriptor
        except BaseException:
            os.close(descriptor)
            raise

    @staticmethod
    def _existing(directory, filename, data):
        try:
            descriptor = os.open(filename, os.O_RDONLY | os.O_NOFOLLOW
                                 | os.O_CLOEXEC | os.O_NONBLOCK, dir_fd=directory)
        except FileNotFoundError:
            return False
        try:
            information = os.fstat(descriptor)
            if (not stat.S_ISREG(information.st_mode)
                    or information.st_uid != os.geteuid()
                    or information.st_mode & 0o077 or information.st_nlink != 1):
                raise Problem(409, 'Vorhandene Datei ist keine private Smartplan-Ablage')
            if information.st_size != len(data):
                raise Problem(409, 'In der Ablage liegt bereits eine abweichende Dokumentdatei')
            chunks = []
            remaining = len(data) + 1
            while remaining:
                chunk = os.read(descriptor, min(remaining, 65536))
                if not chunk:
                    break
                chunks.append(chunk)
                remaining -= len(chunk)
            if b''.join(chunks) != data:
                raise Problem(409, 'In der Ablage liegt bereits eine abweichende Dokumentdatei')
            return True
        finally:
            os.close(descriptor)

    def put(self, project_id, report_id, pdf_bytes):
        filename = _document(project_id, report_id, pdf_bytes)
        root = project = None
        temporary = None
        try:
            root = self._open_root()
            try:
                os.mkdir(project_id, 0o700, dir_fd=root)
            except FileExistsError:
                pass
            project = os.open(project_id, os.O_RDONLY | os.O_DIRECTORY
                              | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=root)
            _private_directory(project)
            # Only this destination is locked; other projects and PostgreSQL
            # remain available. The lock also closes the publication/retry race.
            try:
                fcntl.flock(project, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                raise Problem(409, 'Dateiablage wird gerade verwendet; bitte erneut versuchen') from None
            if self._existing(project, filename, pdf_bytes):
                return {'uploaded': True, 'item_id': project_id + '/' + filename}
            temporary = '.upload-' + secrets.token_hex(16)
            descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL
                                 | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600,
                                 dir_fd=project)
            try:
                view = memoryview(pdf_bytes)
                while view:
                    written = os.write(descriptor, view)
                    if written <= 0:
                        raise OSError('Document write did not progress')
                    view = view[written:]
                os.fsync(descriptor)
            finally:
                os.close(descriptor)
            try:
                os.link(temporary, filename, src_dir_fd=project,
                        dst_dir_fd=project, follow_symlinks=False)
            except FileExistsError:
                # A process outside this adapter must never cause replacement.
                self._existing(project, filename, pdf_bytes)
            os.unlink(temporary, dir_fd=project)
            temporary = None
            os.fsync(project)
            os.fsync(root)
            return {'uploaded': True, 'item_id': project_id + '/' + filename}
        except Problem:
            raise
        except OSError:
            raise Problem(502, 'Dateiablage nicht erreichbar oder nicht beschreibbar') from None
        finally:
            if temporary is not None and project is not None:
                try:
                    os.unlink(temporary, dir_fd=project)
                except OSError:
                    pass
            if project is not None:
                os.close(project)
            if root is not None:
                os.close(root)


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class WebDavStorage:
    """HTTPS WebDAV for a server-configured cloud/NAS endpoint.

    This is not a request-controlled URL fetcher. The administrator configures
    the endpoint and any required private routing/VPN. Credentials are sent to
    that exact origin only, and HTTP redirects are deliberately rejected.
    """

    def __init__(self, url, username, password, *, timeout=8):
        self.username = username
        self.password = password
        self.timeout = min(max(float(timeout), 1), 8)
        self.url = self._url(url)
        self.opener = urllib.request.build_opener(_NoRedirect())

    @staticmethod
    def _url(value):
        if not isinstance(value, str) or not value or len(value) > 2048:
            return ''
        try:
            parsed = urllib.parse.urlsplit(value)
            host = parsed.hostname
            if (parsed.scheme != 'https' or not host or parsed.username is not None
                    or parsed.password is not None or parsed.query or parsed.fragment
                    or any(ord(character) < 33 for character in value)
                    or parsed.port is not None and not 1 <= parsed.port <= 65535):
                return ''
            host = host.rstrip('.').lower()
            if host == 'localhost' or host.endswith('.localhost') or host == 'metadata.google.internal':
                return ''
            try:
                address = ipaddress.ip_address(host)
            except ValueError:
                address = None
            if address and (address.is_loopback or address.is_link_local
                            or address.is_unspecified or address.is_multicast):
                return ''
            path = urllib.parse.unquote(parsed.path)
            if ('\\' in path or any(ord(character) < 32 for character in path)
                    or any(part in ('.', '..') for part in path.split('/'))):
                return ''
            return urllib.parse.urlunsplit(('https', parsed.netloc,
                                            parsed.path.rstrip('/'), '', ''))
        except (ValueError, UnicodeError):
            return ''

    def configured(self):
        return bool(self.url and isinstance(self.username, str) and self.username
                    and ':' not in self.username and isinstance(self.password, str)
                    and self.password)

    def status(self):
        return {'provider': 'webdav', 'account_type': 'webdav',
                'configured': self.configured()}

    def _request_timeout(self):
        deadline = _webdav_deadline.get()
        remaining = deadline - time.monotonic() if deadline is not None else self.timeout
        if remaining <= 0:
            raise Problem(504, 'WebDAV-Ablage antwortet zu langsam; bitte erneut versuchen')
        return min(self.timeout, remaining)

    def request(self, url, method, data=None):
        if not self.configured():
            raise Problem(409, 'WebDAV-Ablage noch nicht eingerichtet')
        if not url.startswith(self.url + '/'):
            raise Problem(400, 'Ungültiges Ablageziel')
        credentials = base64.b64encode((self.username + ':' + self.password).encode()).decode('ascii')
        headers = {'Authorization': 'Basic ' + credentials,
                   'Content-Type': 'application/pdf' if method == 'PUT' else 'application/octet-stream'}
        request = urllib.request.Request(url, data=data, headers=headers, method=method)
        timeout = self._request_timeout()
        try:
            with self.opener.open(request, timeout=timeout) as response:
                status_code = response.status
            # DNS/transport or a custom provider can exceed its socket timeout.
            # Never accept that late response or proceed with another request.
            self._request_timeout()
            return status_code
        except urllib.error.HTTPError as error:
            status_code = error.code
            error.close()
            self._request_timeout()
            if status_code == 405 and method == 'MKCOL':
                return status_code
            if status_code in (401, 403):
                raise Problem(409, 'WebDAV-Anmeldung oder Schreibberechtigung prüfen') from None
            raise Problem(502, 'WebDAV-Ablage antwortet nicht erfolgreich; Verbindung prüfen') from None
        except (urllib.error.URLError, OSError, ValueError):
            self._request_timeout()
            raise Problem(502, 'WebDAV-Ablage nicht erreichbar; Verbindung prüfen') from None

    def put(self, project_id, report_id, pdf_bytes):
        filename = _document(project_id, report_id, pdf_bytes)
        if not self.configured():
            raise Problem(409, 'WebDAV-Ablage noch nicht eingerichtet')
        token = _webdav_deadline.set(time.monotonic() + WEBDAV_BUDGET_SECONDS)
        try:
            prefix = self.url + '/Smartplan'
            project = prefix + '/' + urllib.parse.quote(project_id, safe='')
            for collection in (prefix, project):
                if self.request(collection, 'MKCOL') not in (201, 405):
                    raise Problem(502, 'WebDAV-Ordner konnte nicht angelegt werden')
            target = project + '/' + urllib.parse.quote(filename, safe='')
            if self.request(target, 'PUT', pdf_bytes) not in (200, 201, 204):
                raise Problem(502, 'WebDAV-Datei konnte nicht abgelegt werden')
            return {'uploaded': True, 'item_id': 'Smartplan/' + project_id + '/' + filename}
        finally:
            _webdav_deadline.reset(token)

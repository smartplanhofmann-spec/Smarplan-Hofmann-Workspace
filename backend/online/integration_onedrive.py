"""Pure validation of OneDrive metadata delivered by the existing project bot.

The bot reads its already connected Microsoft tools. This module never requests
Microsoft credentials, performs provider IO, creates links or transfers files.
IDs, parent membership, eTag/cTag and webUrl originate in actual Graph results;
the source protocol uses drive-relative item paths rather than raw Graph URLs.
"""
import json
import re
from urllib.parse import parse_qsl, unquote, urlsplit

from core import Problem


MAX_ITEMS = 1000
MAX_PAYLOAD_BYTES = 2 * 1024 * 1024
MAX_IDENTITY_BYTES = 8192
_MIME = re.compile(r"[!#$%&'*+.^_`|~0-9A-Za-z-]+/[!#$%&'*+.^_`|~0-9A-Za-z-]+")
_HOST_LABEL = re.compile(r'[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?')
_SECRET_PARAMS = frozenset(('authkey', 'access_token', 'refresh_token', 'token', 'sig',
                           'signature', 'tempauth', 'preauth', 'download', 'downloadurl',
                           'share', 'shareid', 'sharetoken', 'sharingtoken'))


def _invalid(message='Vollständige ursprüngliche OneDrive-Metadaten erwartet.'):
    return Problem(400, message)


def _json_size(value, maximum):
    try:
        raw = json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(',', ':')).encode('utf-8')
    except (TypeError, ValueError, UnicodeError, RecursionError):
        raise _invalid() from None
    if len(raw) > maximum:
        raise Problem(413, 'Die OneDrive-Metadaten überschreiten die zulässige Größe.')


def _object(value, required, optional=()):
    if not isinstance(value, dict) or not set(required) <= set(value) or set(value) - set(required) - set(optional):
        raise _invalid()
    return value


def _text(value, maximum, *, blank=False):
    if (not isinstance(value, str) or len(value) > maximum or (not blank and not value.strip())
            or any(not char.isprintable() for char in value)):
        raise _invalid()
    return value


def _id(value):
    value = _text(value, 2048)
    if any(char.isspace() for char in value):
        raise _invalid('Eine stabile ursprüngliche OneDrive-Kennung ist erforderlich.')
    return value


def _name(value):
    value = _text(value, 500)
    if value in ('.', '..') or '/' in value or '\\' in value:
        raise _invalid('Ein ursprünglicher einfacher OneDrive-Datei- oder Ordnername ist erforderlich.')
    return value


def _path(value):
    value = _text(value, 4096)
    if (not value.startswith('/') or '\\' in value or (value != '/' and value.endswith('/'))
            or (value != '/' and any(part in ('', '.', '..') for part in value[1:].split('/')))):
        raise _invalid('Ein eindeutiger laufwerkrelativer OneDrive-Pfad ist erforderlich.')
    return value


def _url(value):
    value = _text(value, 8192)
    if any(char.isspace() for char in value):
        raise _invalid('Nur ursprüngliche HTTPS-Browserlinks von OneDrive oder SharePoint sind erlaubt.')
    try:
        parsed = urlsplit(value)
        host = (parsed.hostname or '').lower()
        valid_host = (host == 'onedrive.live.com' or
                      (host.endswith('.sharepoint.com') and host != '.sharepoint.com'))
        if (parsed.scheme != 'https' or parsed.username is not None or parsed.password is not None
                or parsed.port not in (None, 443) or not valid_host or not host.isascii()
                or len(host) > 253 or any(not _HOST_LABEL.fullmatch(label) for label in host.split('.'))
                or parsed.fragment):
            raise ValueError()
        decoded = unquote(value)
        if any(ord(char) < 32 or ord(char) == 127 for char in decoded) or '\\' in decoded:
            raise ValueError()
        names = set()
        for key, item in parse_qsl(parsed.query, keep_blank_values=True):
            key = key.casefold()
            if key in names or key in _SECRET_PARAMS or (key == 'action' and item.casefold() == 'download'):
                raise ValueError()
            names.add(key)
        # SharePoint sharing shortcuts are not a replacement for original
        # driveItem.webUrl. No short/shared/preauthenticated links are created.
        if parsed.path.startswith('/:'):
            raise ValueError()
    except (ValueError, UnicodeError):
        raise _invalid('Nur ursprüngliche HTTPS-Browserlinks von OneDrive oder SharePoint sind erlaubt.') from None
    return value


def _complete(payload, required):
    _json_size(payload, MAX_PAYLOAD_BYTES)
    _object(payload, ('complete', *required), ('has_more',))
    if payload['complete'] is not True or ('has_more' in payload and payload['has_more'] is not False):
        raise _invalid('Unvollständige OneDrive-Listen werden nicht als synchronisiert bestätigt.')


def _identity(value):
    _object(value, ('id', 'label'))
    _json_size(value, MAX_IDENTITY_BYTES)
    return dict(id=_id(value['id']), label=_text(value['label'], 500))


def _folder(value, *, catalog=False):
    _object(value, ('id', 'drive_id', 'name', 'path'), ('url', 'parent_id') if catalog else ('url',))
    result = dict(id=_id(value['id']), drive_id=_id(value['drive_id']),
                  name=_name(value['name']), path=_path(value['path']))
    if result['path'] != '/' and result['path'].rsplit('/', 1)[-1].casefold() != result['name'].casefold():
        raise _invalid('OneDrive-Ordnername und ursprünglicher Pfad passen nicht zusammen.')
    if 'parent_id' in value:
        result['parent_id'] = _id(value['parent_id'])
        if result['parent_id'] == result['id']:
            raise _invalid('Ein OneDrive-Ordner kann nicht sein eigener übergeordneter Ordner sein.')
    if 'url' in value:
        result['url'] = _url(value['url'])
    return result


def _selection(value):
    _object(value, ('drive_id', 'folder_id'))
    return dict(drive_id=_id(value['drive_id']), folder_id=_id(value['folder_id']))


def _file(value, folder):
    _object(value, ('id', 'drive_id', 'parent_id', 'name', 'path', 'rev', 'size', 'media_type', 'url'))
    result = dict(id=_id(value['id']), drive_id=_id(value['drive_id']), parent_id=_id(value['parent_id']),
                  name=_name(value['name']), path=_path(value['path']), rev=_text(value['rev'], 2048),
                  size=value['size'], media_type=value['media_type'], url=_url(value['url']))
    if (result['drive_id'] != folder['drive_id'] or result['parent_id'] != folder['id']
            or result['id'] == folder['id']):
        raise Problem(409, 'OneDrive-Dateien müssen unmittelbar zum gewählten Ordner und Laufwerk gehören.')
    parent, name = result['path'].rsplit('/', 1)
    if ((parent or '/').casefold() != folder['path'].casefold() or name.casefold() != result['name'].casefold()):
        raise Problem(409, 'OneDrive-Dateipfad und direkter übergeordneter Ordner passen nicht zusammen.')
    if (type(result['size']) is not int or not 0 <= result['size'] <= 2 ** 63 - 1
            or not isinstance(result['media_type'], str) or len(result['media_type']) > 100
            or not _MIME.fullmatch(result['media_type'])):
        raise _invalid('Ursprüngliche Dateigröße und MIME-Typ von OneDrive erwartet.')
    return result


def normalize_bridge_catalog(payload):
    """Validate a complete flat catalog from the bot's actual connected account."""
    _complete(payload, ('identity', 'folders'))
    if not isinstance(payload['folders'], list) or len(payload['folders']) > MAX_ITEMS:
        raise _invalid('Eine vollständige begrenzte OneDrive-Ordnerliste ist erforderlich.')
    identity = _identity(payload['identity'])
    result, seen = [], set()
    for item in payload['folders']:
        folder = _folder(item, catalog=True)
        key = (folder['drive_id'], folder['id'])
        if key in seen:
            raise _invalid('OneDrive-Ordnerkennungen müssen innerhalb des Laufwerks eindeutig sein.')
        seen.add(key)
        result.append(folder)
    return dict(identity=identity, folders=result)


def normalize_bridge_resource(payload, selection):
    """Validate one explicitly requested folder and all its direct file entries."""
    _complete(payload, ('folder', 'files'))
    selection = _selection(selection)
    folder = _folder(payload['folder'])
    if folder['id'] != selection['folder_id'] or folder['drive_id'] != selection['drive_id']:
        raise Problem(409, 'OneDrive-Ergebnis gehört zu einer anderen Ordner- oder Laufwerksauswahl.')
    if not isinstance(payload['files'], list) or len(payload['files']) > MAX_ITEMS:
        raise _invalid('Eine vollständige begrenzte OneDrive-Dateiliste ist erforderlich.')
    files, seen = [], set()
    for item in payload['files']:
        file = _file(item, folder)
        if file['id'] in seen:
            raise _invalid('OneDrive-Dateikennungen müssen innerhalb des Ordners eindeutig sein.')
        seen.add(file['id'])
        files.append(file)
    return dict(folder=folder, files=files)


def normalize_bridge_snapshot(payload, selection):
    """A project snapshot uses the same verified direct-folder source contract."""
    return normalize_bridge_resource(payload, selection)

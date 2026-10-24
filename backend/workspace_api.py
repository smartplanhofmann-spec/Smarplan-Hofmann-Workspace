"""Shared, authenticated adapters for the project folder and enquiry inbox.

Call dispatch inside the normal Office transaction after fresh session/role
authorization. The public Gmail receiver is separate and has only its narrow
delivery credential, never an application login or offline workspace session.
"""
import base64
import binascii
from datetime import datetime, timezone
import re
from urllib.parse import quote

from core import Problem
from inquiries import Inquiries, MAX_EML_BYTES
from project_workspace import ProjectWorkspace
from inbound_connectors import InboundConnectors
from inquiry_attachments import InquiryAttachments


CAPABILITIES = ['project_workspace', 'inquiry_intake', 'gmail_intake', 'mail_attachments']
_PROJECT = r'/projects/[a-f0-9]{32}'
_ID = r'[a-f0-9]{32}'
_ROUTES = [
    (r'/inquiries', 'GET, POST'),
    (r'/inquiries/connections', 'GET'),
    (r'/inquiries/import-eml', 'POST'),
    (r'/inquiries/' + _ID, 'GET, POST'),
    (r'/inquiries/' + _ID + '/convert', 'POST'),
    (r'/inquiries/' + _ID + '/attachments', 'GET'),
    (r'/inquiries/' + _ID + '/attachments/' + _ID + '/content', 'GET'),
    (r'/inquiries/' + _ID + '/attachments/' + _ID + '/delete', 'POST'),
    (r'/inbound/gmail/tokens', 'GET, POST'),
    (r'/inbound/gmail/tokens/' + _ID + '/revoke', 'POST'),
    (_PROJECT + r'/workspace', 'GET, POST'),
    (_PROJECT + r'/(?:tasks|diary|appointments|links)(?:/' + _ID + r')?', 'GET, POST'),
    (_PROJECT + r'/appointments/' + _ID + r'/calendar', 'GET'),
    (_PROJECT + r'/mail-attachments', 'GET'),
    (_PROJECT + r'/mail-attachments/' + _ID + r'/content', 'GET'),
    (_PROJECT + r'/mail-attachments/' + _ID + r'/plan-import', 'POST'),
]


class BinaryAttachment(bytes):
    """Authenticated bytes with a download name; no content is rendered inline."""

    def __new__(cls, content, filename):
        result = super().__new__(cls, content)
        result.filename = filename
        return result


def attachment_disposition(filename):
    return 'attachment; filename="smartplan-anhang"; filename*=UTF-8\'\'' + quote(filename, safe='')


def methods(path):
    return next((allowed for pattern, allowed in _ROUTES if re.fullmatch(pattern, path)), None)


def project_path(path):
    """Classify project-only routes; the caller must also authenticate/scope."""
    return bool(re.fullmatch(_PROJECT + r'/(?:workspace|(?:tasks|diary|appointments|links)'
                             r'(?:/' + _ID + r'(?:/calendar)?)?)', path)) and methods(path) is not None


def schema_statements():
    from inquiries import schema_statements as inquiry_schema
    from project_workspace import schema_statements as project_schema
    from inbound_connectors import schema_statements as inbound_schema
    return [statement for schema in (project_schema, inquiry_schema, inbound_schema) for statement in schema()]


def validate_integrity(office):
    from project_workspace import validate_integrity as project_integrity
    project_integrity(office)
    # Foreign keys and constraints cover the inbox and delivery-key ownership;
    # application-specific integrity checks are added by those modules when
    # available, so backup/restore uses the same canonical validation path.
    for name in ('inquiries', 'inbound_connectors'):
        module = __import__(name)
        check = getattr(module, 'validate_integrity', None)
        if check is not None:
            check(office)


def _connections(office, user):
    result = Inquiries(office).connections(user)
    tokens = InboundConnectors(office).list(user)
    now = datetime.now(timezone.utc)
    active = [row for row in tokens if row['revoked_at'] is None
              and datetime.fromisoformat(row['expires_at']) > now]
    delivered = [row['last_used_at'] for row in active if row['last_used_at']]
    for provider in result['providers']:
        if provider['id'] == 'gmail':
            provider.update(state='received' if delivered else 'awaiting_first_delivery' if active else 'not_connected',
                            method='apps_script', last_received_at=max(delivered) if delivered else None)
    return result


def dispatch(office, user, path, method, data):
    """Return (body, status, media_type), or None for another domain's route."""
    if methods(path) is None:
        return None
    attachments = InquiryAttachments(office)
    match = re.fullmatch(r'/inquiries/(' + _ID + r')/attachments(?:/(' + _ID + r')/(content|delete))?', path)
    if match:
        inquiry_id, attachment_id, action = match.groups()
        if action == 'content':
            content, metadata = attachments.content_inquiry(user, inquiry_id, attachment_id)
            return BinaryAttachment(content, metadata['filename']), 200, 'application/octet-stream'
        if action == 'delete':
            if data:
                raise Problem(400, 'Leerer Löschauftrag erwartet')
            return attachments.remove_inquiry(user, inquiry_id, attachment_id), 200, 'application/json'
        return attachments.for_inquiry(user, inquiry_id), 200, 'application/json'
    match = re.fullmatch(r'/projects/(' + _ID + r')/mail-attachments(?:/(' + _ID + r')/(content|plan-import))?', path)
    if match:
        project_id, attachment_id, action = match.groups()
        if action == 'content':
            content, metadata = attachments.content_project(user, project_id, attachment_id)
            return BinaryAttachment(content, metadata['filename']), 200, 'application/octet-stream'
        if action == 'plan-import':
            return attachments.copy_to_plan(user, project_id, attachment_id, data), 201, 'application/json'
        return attachments.for_project(user, project_id), 200, 'application/json'
    inquiry = Inquiries(office)
    if path == '/inquiries/connections':
        return _connections(office, user), 200, 'application/json'
    if path == '/inquiries/import-eml':
        if set(data) != {'request_id', 'content_base64'}:
            raise Problem(400, 'Import-ID und E-Mail-Datei erwartet')
        encoded = data['content_base64']
        if not isinstance(encoded, str) or len(encoded) > 4 * ((MAX_EML_BYTES + 2) // 3):
            raise Problem(413, 'E-Mail-Datei ist zu groß')
        try:
            raw = base64.b64decode(encoded, validate=True)
        except (ValueError, binascii.Error):
            raise Problem(400, 'Ungültige E-Mail-Datei') from None
        return inquiry.import_eml(user, raw, request_id=data['request_id']), 201, 'application/json'
    if path == '/inquiries':
        return (inquiry.list(user), 200, 'application/json') if method == 'GET' else (
            inquiry.create(user, data), 201, 'application/json')
    match = re.fullmatch(r'/inquiries/(' + _ID + r')(?:/(convert))?', path)
    if match:
        identifier, action = match.groups()
        if action == 'convert':
            return inquiry.convert(user, identifier, data), 200, 'application/json'
        return (inquiry.get(user, identifier), 200, 'application/json') if method == 'GET' else (
            inquiry.update(user, identifier, data), 200, 'application/json')
    connector = InboundConnectors(office)
    if path == '/inbound/gmail/tokens':
        return (connector.list(user), 200, 'application/json') if method == 'GET' else (
            connector.issue(user, data), 201, 'application/json')
    match = re.fullmatch(r'/inbound/gmail/tokens/(' + _ID + r')/revoke', path)
    if match:
        if data:
            raise Problem(400, 'Leerer Widerrufsauftrag erwartet')
        return connector.revoke(user, match[1]), 200, 'application/json'
    parts = path.strip('/').split('/')
    project, kind = parts[1:3]
    workspace = ProjectWorkspace(office)
    if kind == 'workspace':
        return (workspace.dashboard(user, project), 200, 'application/json') if method == 'GET' else (
            workspace.save_profile(user, project, data), 200, 'application/json')
    identifier = parts[3] if len(parts) >= 4 else None
    if len(parts) == 5:
        return workspace.calendar(user, project, identifier), 200, 'text/calendar'
    if method == 'GET':
        result = workspace.get_item(user, project, kind, identifier) if identifier else workspace.list_items(user, project, kind)
        return result, 200, 'application/json'
    return workspace.save_item(user, project, kind, data, identifier), 200 if identifier else 201, 'application/json'

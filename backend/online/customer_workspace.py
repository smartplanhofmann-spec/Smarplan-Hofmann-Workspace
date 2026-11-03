"""Separate public boundary for explicit project publications and file exchange."""
import hashlib
import hmac
import json
import re

from flask import Response, jsonify, request
from werkzeug.exceptions import MethodNotAllowed

from core import Problem
from workspace_api import attachment_disposition
from online.portal import _unique_object, _invalid_constant


MAX_BODY_BYTES = 6 * 1024 * 1024
_TOKEN = re.compile(r'Bearer (SPCT_[A-Za-z0-9_-]{43})\Z')
_FILE = re.compile(r'(files|uploads)/([a-f0-9]{32})/content\Z')
_FIELDS = {'sessions': {'grant_id', 'key'}, 'logout': set(),
    'uploads': {'request_id', 'filename', 'media_type', 'size', 'sha256', 'content_base64', 'note'}}


def _body(path):
    if request.mimetype != 'application/json':
        raise Problem(415, 'JSON erwartet')
    if request.headers.get('Content-Encoding', 'identity') != 'identity':
        raise Problem(400, 'Komprimierte Anfragen werden nicht unterstützt')
    try:
        value = json.loads(request.get_data(cache=False).decode('utf-8'), object_pairs_hook=_unique_object,
            parse_constant=_invalid_constant)
    except (ValueError, UnicodeError, RecursionError):
        raise Problem(400, 'Eindeutiges gültiges JSON erwartet') from None
    if not isinstance(value, dict) or set(value) != _FIELDS[path]:
        raise Problem(400, 'Die vorgesehenen Kundenfelder angeben')
    return value


def register_customer_workspace_routes(app, office, vault_key, origin):
    material = vault_key.encode('ascii') if isinstance(vault_key, str) else bytes(vault_key)
    rate_secret = hmac.digest(material, b'smartplan.customer-workspace.rate.v1', hashlib.sha256)

    def rate(lane, limit):
        from business_portal import count_attempt
        key = hmac.new(rate_secret, (lane+'\0'+(request.remote_addr or 'unknown')).encode(), hashlib.sha256).hexdigest()
        count_attempt(office, key, limit, 60)

    @app.route('/api/v1/customer-workspace', defaults={'path': ''}, strict_slashes=False,
        methods=['GET', 'POST', 'PUT', 'PATCH', 'DELETE', 'OPTIONS', 'HEAD'], provide_automatic_options=False)
    @app.route('/api/v1/customer-workspace/<path:path>', methods=['GET', 'POST', 'PUT', 'PATCH', 'DELETE', 'OPTIONS', 'HEAD'],
        provide_automatic_options=False)
    def customer_workspace(path):
        from business_schema import state
        from business_customer_workspace import CustomerWorkspace
        request.max_content_length = MAX_BODY_BYTES if path == 'uploads' else 16 * 1024
        try:
            installed = state(office).get('read_capabilities', [])
        except RuntimeError:
            raise Problem(503, 'Kundenarbeitsbereich vorübergehend nicht verfügbar') from None
        if 'business_customer_workspace' not in installed:
            raise Problem(404, 'Kundenarbeitsbereich nicht verfügbar')
        rate('requests', 120)
        if path == 'sessions':
            rate('sessions', 10)
        elif path == 'uploads':
            rate('uploads', 20)
        match = _FILE.fullmatch(path)
        expected = 'GET' if path == 'workspace' or match else 'POST' if path in _FIELDS else None
        if expected is None:
            raise Problem(404, 'Kundenfunktion nicht verfügbar')
        if request.method != expected:
            raise MethodNotAllowed(valid_methods=[expected])
        if request.query_string:
            raise Problem(400, 'Dieser Kundenzugang erwartet keine Queryparameter')
        supplied_origin = request.headers.get('Origin')
        if (request.method == 'POST' and supplied_origin != origin) or (supplied_origin is not None and supplied_origin != origin):
            raise Problem(403, 'Kunden-Origin nicht gültig')
        data = _body(path) if expected == 'POST' else None
        if expected == 'GET' and request.get_data(cache=False):
            raise Problem(400, 'Kein Inhalt bei Datei- oder Projektabrufen erlaubt')
        api = CustomerWorkspace(office)
        if path == 'sessions':
            if request.headers.get('Authorization'):
                raise Problem(401, 'Getrennten Einladungszugang verwenden')
            return jsonify(api.open_session(data['grant_id'], data['key'])), 201
        token = _TOKEN.fullmatch(request.headers.get('Authorization', ''))
        if not token:
            raise Problem(401, 'Kundenzugang nicht verfügbar')
        token = token[1]
        if path == 'logout':
            return jsonify(api.logout(token)), 200
        if path == 'workspace':
            return jsonify(api.view(token)), 200
        if path == 'uploads':
            return jsonify(api.upload(token, data)), 201
        content, filename, media_type = api.content(token, match[1], match[2])
        return Response(content, mimetype=media_type, headers={
            'Content-Disposition': attachment_disposition(filename),
            'Content-Security-Policy': "default-src 'none'; sandbox"})

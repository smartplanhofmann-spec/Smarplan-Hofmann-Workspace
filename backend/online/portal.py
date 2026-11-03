"""Separate, bounded customer-portal HTTP boundary.

No customer is converted into an Office actor. Rate counters commit before
parsing or authentication, so bad JSON and credentials cannot roll them back.
The configured HTTPS origin and rate secret come only from the online host.
"""
import hashlib
import hmac
import json
import re

from flask import Response, jsonify, request
from werkzeug.exceptions import MethodNotAllowed

from core import Problem
from workspace_api import attachment_disposition


MAX_BODY_BYTES = 16 * 1024
WINDOW_SECONDS = 60
REQUESTS_PER_WINDOW = 120
SESSIONS_PER_WINDOW = 10
DECISIONS_PER_WINDOW = 30
_METHODS = {
    'sessions': 'POST',
    'logout': 'POST',
    'offer': 'GET',
    'offer/pdf': 'GET',
    'offer/decision': 'POST',
}
_BODY_FIELDS = {
    'sessions': {'grant_id', 'key'},
    'logout': set(),
    'offer/decision': {'request_id', 'content_hash', 'pdf_hash', 'decision',
                       'declared_name', 'statement_version', 'confirmation'},
}
_SESSION_AUTHORIZATION = re.compile(r'Bearer (SPPT_[A-Za-z0-9_-]{43})\Z')


def _unique_object(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError('Duplicate JSON member')
        value[key] = item
    return value


def _invalid_constant(value):
    raise ValueError('Non-finite JSON value')


def _body(path):
    if request.mimetype != 'application/json':
        raise Problem(415, 'JSON erwartet.')
    if request.headers.get('Content-Encoding', 'identity') != 'identity':
        raise Problem(400, 'Komprimierte Portalanfragen werden nicht unterstützt.')
    try:
        raw = request.get_data(cache=False)
        data = json.loads(raw.decode('utf-8'), object_pairs_hook=_unique_object,
                          parse_constant=_invalid_constant)
    except (UnicodeError, ValueError, RecursionError):
        raise Problem(400, 'Gültiges JSON-Objekt erwartet.') from None
    if not isinstance(data, dict) or set(data) != _BODY_FIELDS[path]:
        raise Problem(400, 'Die vorgesehenen Portalfelder angeben.')
    return data


def _token():
    match = _SESSION_AUTHORIZATION.fullmatch(request.headers.get('Authorization', ''))
    if match is None:
        raise Problem(401, 'Portalzugang nicht verfügbar.')
    return match[1]


def register_portal_routes(app, office, vault_key, origin):
    """Install customer routes before the catch-all internal API dispatcher."""
    from online.customer_workspace import register_customer_workspace_routes
    register_customer_workspace_routes(app, office, vault_key, origin)
    material = vault_key.encode('ascii') if isinstance(vault_key, str) else bytes(vault_key)
    rate_secret = hmac.digest(material, b'smartplan.offer-portal.rate.v1', hashlib.sha256)

    def rate_key(lane):
        # ProxyFix uses the one client address written by the trusted local
        # proxy. Never inspect arbitrary forwarding-header lists here.
        peer = request.remote_addr or 'unknown'
        return hmac.new(rate_secret, (lane + '\0' + peer).encode('utf-8'), hashlib.sha256).hexdigest()

    @app.route('/api/v1/portal', defaults={'path': ''}, strict_slashes=False,
               methods=['GET', 'POST', 'PUT', 'PATCH', 'DELETE', 'OPTIONS', 'HEAD'],
               provide_automatic_options=False)
    @app.route('/api/v1/portal/<path:path>',
               methods=['GET', 'POST', 'PUT', 'PATCH', 'DELETE', 'OPTIONS', 'HEAD'],
               provide_automatic_options=False)
    def customer_portal(path):
        from business_schema import state
        from business_portal import Portal, count_attempt

        request.max_content_length = MAX_BODY_BYTES
        try:
            installed = state(office).get('read_capabilities', [])
        except RuntimeError:
            # Old module registries require an explicit operator migration;
            # an anonymous request must never create or repair their tables.
            raise Problem(503, 'Portal vorübergehend nicht verfügbar.') from None
        if 'business_portal' not in installed:
            raise Problem(404, 'Portal nicht verfügbar.')

        # Each call is its own committed domain transaction. Do not wrap this
        # handler in office.db: a later failure must retain these counters.
        count_attempt(office, rate_key('requests'), REQUESTS_PER_WINDOW, WINDOW_SECONDS)
        if path == 'sessions':
            count_attempt(office, rate_key('sessions'), SESSIONS_PER_WINDOW, WINDOW_SECONDS)
        elif path == 'offer/decision':
            count_attempt(office, rate_key('decisions'), DECISIONS_PER_WINDOW, WINDOW_SECONDS)

        expected = _METHODS.get(path)
        if expected is None:
            raise Problem(404, 'Portalfunktion nicht verfügbar.')
        if request.method != expected:
            raise MethodNotAllowed(valid_methods=[expected])
        if request.query_string:
            raise Problem(400, 'Dieser Portalzugang erwartet keine Queryparameter.')

        incoming_origin = request.headers.get('Origin')
        if request.method == 'POST' and incoming_origin != origin or (
                incoming_origin is not None and incoming_origin != origin):
            raise Problem(403, 'Portal-Origin nicht gültig.')

        data = _body(path) if request.method == 'POST' else None
        if request.method == 'GET' and request.get_data(cache=False):
            raise Problem(400, 'Dieser Portalabruf erwartet keinen Anfrageinhalt.')
        portal = Portal(office)
        if path == 'sessions':
            if request.headers.get('Authorization'):
                raise Problem(401, 'Einladungszugang ohne Office-Anmeldung verwenden.')
            return jsonify(portal.open_session(data['grant_id'], data['key'])), 201

        token = _token()
        if path == 'logout':
            return jsonify(portal.logout(token)), 200
        if path == 'offer':
            return jsonify(portal.view(token)), 200
        if path == 'offer/pdf':
            content, filename = portal.pdf(token)
            return Response(content, mimetype='application/pdf',
                            headers={'Content-Disposition': attachment_disposition(filename)})
        return jsonify(portal.decide(token, data)), 201

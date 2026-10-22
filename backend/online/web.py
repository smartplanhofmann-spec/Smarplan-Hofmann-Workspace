"""Versioned JSON API served by Gunicorn behind the local HTTPS proxy."""
import os
from pathlib import Path
import re

from flask import Flask, jsonify, request, Response
from werkzeug.exceptions import HTTPException
from werkzeug.middleware.proxy_fix import ProxyFix

from core import Problem, digest
from online.auth import Authentication
from online.store import PostgresOffice

METHODS = {
    '/me': 'GET', '/logout': 'POST', '/users': 'GET, POST',
    '/customers': 'GET, POST', '/projects': 'GET, POST', '/assignments': 'POST',
    '/storage/status': 'GET', '/storage/connect': 'POST',
}
PATTERNS = [
    (r'/users/[a-f0-9]{32}', 'POST'),
    (r'/customers/[a-f0-9]{32}', 'GET, POST'),
    (r'/projects/[a-f0-9]{32}/customer', 'POST'),
    (r'/projects/[a-f0-9]{32}/assignments', 'GET'),
    (r'/projects/[a-f0-9]{32}/reports', 'GET, POST'),
    (r'/reports/[a-f0-9]{32}(?:/pdf)?', 'GET'),
    (r'/reports/[a-f0-9]{32}/sign', 'POST'),
]


def dispatch(office, user, path, method, data, token):
    if path == '/me':
        return user, 200
    if path == '/logout':
        office.db.execute('DELETE FROM sessions WHERE token=?', (digest(token),))
        return {'ok': True}, 200
    if path == '/users':
        return (office.users(user), 200) if method == 'GET' else (
            {'id': office.create_user(user, data.get('email'), data.get('password'), data.get('role', 'technician'))}, 201)
    if path == '/customers':
        return (office.customers(user), 200) if method == 'GET' else (office.create_customer(user, data), 201)
    if path == '/projects':
        return (office.projects(user), 200) if method == 'GET' else (
            {'id': office.add_project(user, data.get('name'), data.get('customer'), data.get('customer_id'))}, 201)
    if path == '/assignments':
        office.assign(user, data.get('project_id'), data.get('user_id'), data.get('remove', False))
        return {'ok': True}, 200
    if path.startswith('/storage/'):
        office.require(user, ('owner',))
        if path == '/storage/status':
            return {'configured': False, 'connected': False, 'account_type': 'personal'}, 200
        raise Problem(409, 'OneDrive wird in einem eigenen Einrichtungsschritt verbunden')
    parts = path.strip('/').split('/')
    if parts[0] == 'users':
        return office.update_user(user, parts[1], data), 200
    if parts[0] == 'customers':
        return (office.customer(user, parts[1]) if method == 'GET' else office.update_customer(user, parts[1], data)), 200
    if parts[0] == 'projects':
        if parts[2] == 'customer':
            if set(data) != {'customer_id'}:
                raise Problem(400, 'Kundenzuordnung erwartet')
            return office.project_customer(user, parts[1], data['customer_id']), 200
        if parts[2] == 'assignments':
            return office.assignments(user, parts[1]), 200
        return (office.reports(user, parts[1]), 200) if method == 'GET' else (
            office.draft(user, parts[1], data.get('kind'), data.get('description')), 201)
    if len(parts) == 3 and parts[2] == 'sign':
        return office.sign(user, parts[1], data.get('content_hash'), data.get('signer'), data.get('strokes')), 200
    if len(parts) == 3 and parts[2] == 'pdf':
        return Response(office.pdf(user, parts[1]), mimetype='application/pdf',
                        headers={'Content-Disposition': 'inline; filename="smartplan-report.pdf"'}), 200
    return office.report(user, parts[1]), 200


def create_app(*, office=None, key=None, host=None):
    host = host or os.environ['SMARTPLAN_PUBLIC_HOST']
    if not re.fullmatch(r'[a-z0-9]+(?:[.-][a-z0-9]+)+', host):
        raise RuntimeError('Gültiger öffentlicher Hostname erforderlich.')
    if key is None:
        key = Path(os.environ['SMARTPLAN_VAULT_KEY_FILE']).read_bytes().strip()
    office = office or PostgresOffice(os.environ['SMARTPLAN_DATABASE_DSN'])
    authentication = Authentication(office, key)
    app = Flask(__name__, static_folder=None)
    app.config.update(MAX_CONTENT_LENGTH=1_000_000, PROPAGATE_EXCEPTIONS=False)
    # Only reachable on loopback; Caddy replaces these two forwarding headers.
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=0, x_port=0, x_prefix=0)

    @app.before_request
    def require_https_host():
        if request.host not in (host, host + ':443') or not request.is_secure:
            raise Problem(400, 'HTTPS-Adresse nicht gültig')

    @app.after_request
    def headers(response):
        response.headers['Cache-Control'] = 'no-store'
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['Referrer-Policy'] = 'no-referrer'
        response.headers['Content-Security-Policy'] = "default-src 'none'; frame-ancestors 'none'"
        return response

    @app.errorhandler(Problem)
    def problem(error):
        response = jsonify(error=error.message)
        response.status_code = error.status
        if error.status == 429:
            response.headers['Retry-After'] = '300'
        return response

    @app.errorhandler(Exception)
    def unexpected(error):
        if isinstance(error, HTTPException):
            response = jsonify(error={400: 'Ungültiges JSON', 404: 'Funktion nicht gefunden',
                                      405: 'HTTP-Methode nicht erlaubt', 413: 'Anfrage zu groß',
                                      415: 'JSON erwartet'}.get(error.code, 'Anfrage fehlgeschlagen'))
            response.status_code = error.code
            if error.code == 405:
                response.headers['Allow'] = ', '.join(error.valid_methods or [])
            return response
        # Do not log requests, credentials, SQL parameters or connection strings.
        return jsonify(error='Interner Fehler'), 500

    def body():
        value = request.get_json()
        if not isinstance(value, dict):
            raise Problem(400, 'JSON-Objekt erwartet')
        return value

    @app.get('/health')
    @app.get('/ready')
    def ready():
        try:
            with office.lock, office.db:
                office.db.execute('SELECT COUNT(*) FROM users').fetchone()
            return jsonify(status='ok', version='0.5.0-online-pilot', database='ok')
        except Exception:
            return jsonify(status='unavailable'), 503

    @app.post('/api/v1/login')
    def login():
        data = body()
        return jsonify(authentication.begin(data.get('email'), data.get('password'), request.remote_addr or 'unknown'))

    @app.post('/api/v1/login/verify')
    def verify():
        data = body()
        return jsonify(authentication.finish(data.get('challenge'), data.get('code')))

    @app.route('/api/v1/<path:path>', methods=['GET', 'POST', 'PUT', 'PATCH', 'DELETE'])
    def api(path):
        path = '/' + path
        methods = METHODS.get(path) or next((allowed for pattern, allowed in PATTERNS if re.fullmatch(pattern, path)), None)
        if not methods:
            raise Problem(404, 'Funktion nicht gefunden')
        if request.method not in methods.split(', '):
            response = jsonify(error='HTTP-Methode nicht erlaubt')
            response.status_code = 405
            response.headers['Allow'] = methods
            return response
        data = body() if request.method == 'POST' else {}
        authorization = request.headers.get('Authorization', '')
        if not authorization.startswith('Bearer ') or len(authorization) > 200:
            raise Problem(401, 'Bitte anmelden')
        token = authorization[7:]
        # One transaction includes fresh authorization, all reads/writes, and PDF access.
        with office.lock, office.db:
            user = office.user(token)
            result, status = dispatch(office, user, path, request.method, data, token)
        return (result if isinstance(result, Response) else jsonify(result)), status

    return app

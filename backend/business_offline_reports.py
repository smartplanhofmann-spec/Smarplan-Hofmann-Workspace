"""Atomic import of frozen device captures into the existing service archive.

Device timestamps are claims, not trusted timestamps. No external side effects,
new archive or schema migration are introduced by this adapter.
"""
from datetime import datetime, timedelta, timezone
import hashlib
import json
import re

from core import Problem, canonical

ACTION = 'business.entry.offline.captured'
FIELDS = {'request_id', 'entry_id', 'content', 'content_hash', 'signer', 'strokes', 'signed_at'}
CONTENT_FIELDS = {'title', 'description', 'notes', 'project_name', 'customer', 'captured_at'}
PROOF_FIELDS = {'schema', 'content', 'content_hash', 'signed_at', 'received_at', 'request_id', 'request_hash'}
ARCHIVE_FIELDS = {'title', 'description', 'notes', 'media_ids', 'status', 'offline_capture',
                  'signer', 'strokes', 'signed_at', 'signed_by', 'signed_content_hash'}


def _hash(value):
    return hashlib.sha256(canonical(value).encode('utf-8')).hexdigest()


def _stamp(value):
    if not isinstance(value, str) or not re.fullmatch(
            r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?(?:Z|\+00:00)', value):
        raise Problem(400, 'UTC-Zeitpunkt mit Zeitzone erwartet')
    try:
        parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
        if not 1900 <= parsed.year <= 2200:
            raise ValueError('Unsupported timestamp year')
        return parsed
    except ValueError:
        raise Problem(400, 'Ungültiger UTC-Zeitpunkt') from None


def _string(value, label, maximum, required=False):
    if (not isinstance(value, str) or len(value) > maximum or
            any(ord(c) < 32 and c not in '\n\t' for c in value) or
            any(0xD800 <= ord(c) <= 0xDFFF for c in value) or
            (required and not value.strip())):
        raise Problem(400, 'Ungültiges Feld: ' + label)
    return value  # Never trim, normalize or otherwise change a signed capture.


def _input(project_id, data):
    from business_operations import identifier, _strokes
    identifier(project_id, 'Projekt-ID')
    if not isinstance(data, dict) or set(data) != FIELDS:
        raise Problem(400, 'Vollständige unveränderte Offline-Protokollerfassung erwartet')
    identifier(data['request_id'], 'Anfrage-ID')
    identifier(data['entry_id'], 'Dokument-ID')
    content = data['content']
    if not isinstance(content, dict) or set(content) != CONTENT_FIELDS:
        raise Problem(400, 'Ungültiger eingefrorener Protokollinhalt')
    for field, maximum, required in (('title', 300, True), ('description', 30000, True),
            ('notes', 10000, False), ('project_name', 500, True), ('customer', 500, True)):
        _string(content[field], field, maximum, required)
    captured, signed = _stamp(content['captured_at']), _stamp(data['signed_at'])
    if signed < captured:
        raise Problem(400, 'Unterschriftszeit liegt vor der Erfassung')
    _string(data['signer'], 'Unterzeichner', 200, True)
    _strokes(data['strokes'])
    if data['content_hash'] != _hash([data['entry_id'], project_id, content]):
        raise Problem(409, 'Der eingefrorene Protokollinhalt stimmt nicht mit seiner Prüfsumme überein')
    return _hash([ACTION, project_id, data['entry_id'], data])


def validate_row(row):
    """Verify capture identity, source, signature envelope and PDF on every read."""
    from business_operations import _strokes
    try:
        value = json.loads(row['payload_json'])
        proof = value.get('offline_capture')
        if proof is None:
            return
        if (set(value) != ARCHIVE_FIELDS or not isinstance(proof, dict) or set(proof) != PROOF_FIELDS or
                type(proof['schema']) is not int or proof['schema'] != 1 or
                row['kind'] != 'service' or row['revision'] != 2 or value['status'] != 'signed'):
            raise ValueError('Invalid offline capture envelope')
        data = dict(request_id=proof['request_id'], entry_id=row['id'], content=proof['content'],
                    content_hash=proof['content_hash'], signer=value['signer'],
                    strokes=value['strokes'], signed_at=value['signed_at'])
        if (_input(row['project_id'], data) != proof['request_hash'] or
                proof['signed_at'] != value['signed_at'] or
                row['created_by'] != value['signed_by'] or row['updated_by'] != row['created_by'] or
                row['created_at'] != proof['received_at'] or row['updated_at'] != proof['received_at'] or
                any(value[field] != proof['content'][field] for field in ('title', 'description', 'notes')) or
                value['media_ids'] != [] or 'checklist' in value):
            raise ValueError('Offline capture identity or source changed')
        received = _stamp(proof['received_at'])
        if _stamp(value['signed_at']) > received + timedelta(minutes=5):
            raise ValueError('Offline capture from the future')
        original = {key: item for key, item in value.items()
                    if key not in ('signer', 'strokes', 'signed_at', 'signed_by', 'signed_content_hash')}
        original['status'] = 'draft'
        if (_hash([row['project_id'], 'service', original]) != row['content_hash'] or
                value['signed_content_hash'] != row['content_hash'] or
                not isinstance(row['pdf'], (bytes, bytearray, memoryview)) or not row['pdf'] or
                hashlib.sha256(bytes(row['pdf'])).hexdigest() != row['pdf_sha256']):
            raise ValueError('Invalid offline capture archive')
        _strokes(value['strokes'])
    except (AttributeError, KeyError, TypeError, ValueError, Problem) as error:
        raise Problem(500, 'Integritätsprüfung des Offline-Protokolls fehlgeschlagen') from error


def capture(api, actor, project_id, data):
    from business_operations import transaction, _render_pdf
    from business_schema import require_capability
    from business_organization import require_active
    try:
        encoded = json.dumps(data, ensure_ascii=False, allow_nan=False).encode('utf-8')
        if len(encoded) > 1_000_000:
            raise Problem(413, 'Offline-Protokoll ist zu groß')
        data = json.loads(encoded)
    except (TypeError, ValueError, UnicodeError):
        raise Problem(400, 'Gültige begrenzte JSON-Erfassung erwartet') from None
    fingerprint = _input(project_id, data)
    entry_id = data['entry_id']

    def check():
        fresh = api.access(actor, 'documents.write', project_id)
        api.access(fresh, 'documents.read', project_id)
        require_capability(api.office, 'business_operations')
        require_active(api.office, fresh, '/service-reports/offline', 'business_operations', data)
        receipt = api.office.db.execute('SELECT request_hash,result_json FROM business_operations_requests '
            'WHERE user_id=? AND request_id=?', (fresh['id'], data['request_id'])).fetchone()
        if receipt:
            if receipt['request_hash'] != fingerprint:
                raise Problem(409, 'Anfrage-ID wurde bereits für eine andere Erfassung verwendet')
            row = api.row('business_operation_entries', project_id, entry_id)
            validate_row(row)
            result = api._entry(row)
            if (row['created_by'] != fresh['id'] or result.get('offline_capture', {}).get('request_hash') != fingerprint
                    or json.loads(receipt['result_json']) != result):
                raise Problem(500, 'Offline-Protokoll und Empfangsbeleg stimmen nicht überein')
            return fresh, result
        if api.office.db.execute('SELECT id FROM business_operation_entries WHERE id=?', (entry_id,)).fetchone():
            raise Problem(409, 'Dokument-ID wurde bereits verwendet; lokale Erfassung bleibt erhalten')
        project = api.office.project(fresh, project_id)
        if data['content']['project_name'] != project['name'] or data['content']['customer'] != project['customer']:
            raise Problem(409, 'Projekt oder Kunde wurde geändert; unterschriebene Erfassung unverändert prüfen')
        return fresh, None

    with transaction(api.office):
        fresh, replay = check()
        if replay is not None:
            return replay
        received = api.now()
        if _stamp(data['signed_at']) > _stamp(received) + timedelta(minutes=5):
            raise Problem(400, 'Gerätezeit liegt in der Zukunft; lokale Erfassung bleibt erhalten')
        proof = dict(schema=1, content=data['content'], content_hash=data['content_hash'],
            signed_at=data['signed_at'], received_at=received,
            request_id=data['request_id'], request_hash=fingerprint)
        body = {field: data['content'][field] for field in ('title', 'description', 'notes')}
        body.update(media_ids=[], status='draft', offline_capture=proof)
        content_hash = _hash([project_id, 'service', body])
        draft = dict(body, id=entry_id, project_id=project_id, kind='service', revision=1,
            content_hash=content_hash, created_by=fresh['id'], updated_by=fresh['id'],
            created_at=received, updated_at=received)
        signed = dict(draft, status='signed', revision=2, signer=data['signer'], strokes=data['strokes'],
            signed_at=data['signed_at'], signed_by=fresh['id'], signed_content_hash=content_hash)
    # Bounded PDF generation happens without holding a database transaction.
    pdf = _render_pdf(signed)
    if len(pdf) > 10 * 1024 * 1024:
        raise Problem(413, 'Protokoll-PDF ist zu groß')
    pdf_hash = hashlib.sha256(pdf).hexdigest()
    with transaction(api.office):
        fresh, replay = check()
        if replay is not None:
            return replay
        api.office.db.execute('''INSERT INTO business_operation_entries
            (id,project_id,kind,payload_json,content_hash,revision,pdf,pdf_sha256,created_by,created_at,updated_by,updated_at)
            VALUES(?,?,'service',?,?,1,NULL,NULL,?,?,?,?)''',
            (entry_id, project_id, canonical(body), content_hash, fresh['id'], received, fresh['id'], received))
        api._version('entry', draft)
        final = dict(body, status='signed', signer=data['signer'], strokes=data['strokes'],
            signed_at=data['signed_at'], signed_by=fresh['id'], signed_content_hash=content_hash)
        api.office.db.execute('UPDATE business_operation_entries SET payload_json=?,revision=2,pdf=?,pdf_sha256=? WHERE id=?',
            (canonical(final), pdf, pdf_hash, entry_id))
        result = api._entry(api.row('business_operation_entries', project_id, entry_id))
        api._version('entry', result)
        api.office.db.execute('INSERT INTO business_operations_requests(user_id,request_id,request_hash,result_json) VALUES(?,?,?,?)',
            (fresh['id'], data['request_id'], fingerprint, canonical(result)))
        api.office.audit(fresh, ACTION, entry_id)
        return result

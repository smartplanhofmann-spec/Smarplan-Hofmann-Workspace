"""Read-only diagnosis of a frozen capture; never rebinds a signature.

A context change may be addressed by a separate, newly signed report. This
endpoint cannot import, edit, discard or mark the original as synchronized.
"""
from datetime import timedelta
import json

from core import Problem, canonical
from business_offline_reports import _input, _stamp, validate_row
from business_operations import transaction

PATH = '/service-reports/offline/diagnosis'


def diagnose(api, actor, project_id, data):
    try:
        encoded = json.dumps(data, ensure_ascii=False, allow_nan=False).encode('utf-8')
        if len(encoded) > 1_000_000:
            raise Problem(413, 'Offline-Protokoll ist zu groß')
        data = json.loads(encoded)
    except (TypeError, ValueError, UnicodeError, RecursionError):
        raise Problem(400, 'Gültige begrenzte JSON-Erfassung erwartet') from None
    fingerprint = _input(project_id, data)
    with transaction(api.office):
        fresh = api.access(actor, 'documents.write', project_id)
        api.access(fresh, 'documents.read', project_id)
        from business_schema import require_capability
        require_capability(api.office, 'business_operations')
        project = api.office.project(fresh, project_id)
        original = {key: data['content'][key] for key in ('project_name', 'customer')}
        current = dict(project_name=project['name'], customer=project['customer'])
        receipt = api.office.db.execute(
            'SELECT request_hash,result_json FROM business_operations_requests '
            'WHERE user_id=? AND request_id=?', (fresh['id'], data['request_id'])).fetchone()
        accepted = None
        if receipt:
            if receipt['request_hash'] != fingerprint:
                raise Problem(409, 'Anfrage-ID wurde bereits für eine andere Erfassung verwendet')
            row = api.row('business_operation_entries', project_id, data['entry_id'])
            validate_row(row)
            accepted = api._entry(row)
            if (row['created_by'] != fresh['id']
                    or accepted.get('offline_capture', {}).get('request_hash') != fingerprint
                    or canonical(accepted) != canonical(json.loads(receipt['result_json']))):
                raise Problem(500, 'Offline-Protokoll und Empfangsbeleg stimmen nicht überein')
        elif api.office.db.execute('SELECT id FROM business_operation_entries WHERE id=?',
                                   (data['entry_id'],)).fetchone():
            raise Problem(409, 'Dokument-ID wurde bereits verwendet; lokale Erfassung bleibt erhalten')
        elif _stamp(data['signed_at']) > _stamp(api.now()) + timedelta(minutes=5):
            raise Problem(400, 'Gerätezeit liegt in der Zukunft; lokale Erfassung bleibt erhalten')
        return dict(schema=1, entry_id=data['entry_id'], project_id=project_id,
                    request_id=data['request_id'], content_hash=data['content_hash'],
                    captured_context=original, current_context=current,
                    state='accepted' if accepted else 'ready' if original == current else 'context_changed',
                    server_record=accepted)

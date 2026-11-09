"""Frozen actual-remittance ceiling for a positive payroll correction.

Current observations validate the complete cash ledger. Historical observations
validate only their original sequence prefix and receipt bindings; recursively
rebuilding later cash sources would re-enter the corrected payroll run.
"""
import json
import re

from core import Problem, canonical
from business_operations import identifier, transaction
from business_personnel_workflow import _sha
from payroll_cash_sources import COMPONENTS, calculated


_FIELDS = {'schema_version', 'head_sequence', 'entries', 'amounts', 'source_hash'}
_ENTRY_FIELDS = {'id', 'revision', 'sequence', 'private_hash'}


def _bad(message='Der ursprüngliche Abführungsnachweis ist nicht unverändert prüfbar.'):
    return Problem(409, message)


def _scope(employee_id, month):
    identifier(employee_id)
    if not isinstance(month, str) or not re.fullmatch(r'2026-(0[1-9]|1[0-2])', month):
        raise _bad('Abführungsprüfung benötigt einen belegten Abrechnungsmonat 2026.')
    return employee_id + ':' + month


def _seal(head, entries, amounts):
    value = dict(schema_version=1, head_sequence=head, entries=entries, amounts=amounts)
    # Scope is bound by the enclosing transition and recomputed by the reader.
    return dict(value, source_hash=_sha(value))


def _covered(calculation, amounts):
    ceilings = calculated(calculation)
    for key in COMPONENTS:
        if type(ceilings[key]) is not int or ceilings[key] < 0:
            raise _bad('Die korrigierte Abführungsschuld muss vollständig nachgerechnet sein.')
        if amounts[key] > ceilings[key]:
            raise _bad('Bereits tatsächlich abgeführte Beträge benötigen einen eigenen Erstattungs- oder Verrechnungsvertrag.')


def _bound_row(office, api, row, private):
    """Check an accepted cash row without resolving any payroll source again."""
    from business_payroll_cash import INPUT, _public
    body = api._inputs(private['command'])
    if (canonical(private) != row['private_json'] or _sha(private) != row['private_sha256']
            or body['batch_id'] != row['id'] or body['kind'] != row['kind']
            or body['instance_id'] != row['instance_id'] or body['expected_revision'] != 0
            or row['revision'] != 1 or row['previous_hash'] is not None
            or body['action'] != 'adopt'):
        raise _bad()
    public = _public(body, private, row['revision'])
    if canonical(public) != row['public_json'] or _sha(public) != row['public_sha256']:
        raise _bad()
    result = api._metadata(row)
    receipts = office.db.execute('SELECT * FROM business_payroll_cash_requests WHERE result_json=?',
                                (canonical(result),)).fetchall()
    if len(receipts) != 1:
        raise _bad('Die ursprüngliche Abführungsquittung fehlt oder ist doppelt vorhanden.')
    receipt = receipts[0]
    command = json.loads(receipt['request_json'])
    api._inputs(command, True)
    preview = dict(batch_id=body['batch_id'], revision=row['revision'], kind=body['kind'],
        instance_id=body['instance_id'], public_source=public,
        private_source_count=len(private['source_records']), private_hash=_sha(private),
        warnings=['Keine Bankübertragung; EÜR-Einordnung gesondert bestätigen.'])
    if (canonical(command) != receipt['request_json'] or _sha(command) != receipt['request_hash']
            or command['request_id'] != receipt['request_id'] or receipt['user_id'] != row['created_by']
            or {key: command[key] for key in INPUT} != body or command['preview_hash'] != _sha(preview)):
        raise _bad()


def _prefix(office, employee_id, month, head):
    from business_payroll_cash import PayrollCash
    scope = _scope(employee_id, month)
    api = PayrollCash(office)
    rows = office.db.execute('SELECT * FROM business_payroll_cash_batches WHERE sequence<=? ORDER BY sequence',
                             (head,)).fetchall()
    if len(rows) != head or any(type(row['sequence']) is not int or row['sequence'] != n
                                for n, row in enumerate(rows, 1)):
        raise _bad('Der eingefrorene Abführungspräfix ist nicht lückenlos vorhanden.')
    decoded = [(row, api._private(row)) for row in rows]
    relevant_ids = set()
    for row, private in decoded:
        if (not isinstance(private, dict) or not isinstance(private.get('transactions'), list)
                or any(not isinstance(item, dict) for item in private['transactions'])):
            raise _bad()
        if any(item.get('scope_key') == scope and item.get('component') in COMPONENTS
               for item in private['transactions']):
            relevant_ids.add(row['id'])
    entries = []
    amounts = dict.fromkeys(COMPONENTS, 0)
    for row, private in decoded:
        if row['id'] not in relevant_ids:
            continue
        # Even a later void has no transactions. Consider every revision of an
        # originally relevant batch in this prefix, not only the latest row.
        if row['kind'] != 'remittance' or row['revision'] != 1:
            raise _bad('Berichtigte oder zurückgenommene Abführungsbatches benötigen ihren eigenen Ausgleichsvertrag.')
        _bound_row(office, api, row, private)
        entries.append(dict(id=row['id'], revision=row['revision'], sequence=row['sequence'],
                            private_hash=row['private_sha256']))
        for item in private['transactions']:
            if item.get('scope_key') != scope:
                continue
            if (item.get('employee_id') != employee_id or item.get('component') not in COMPONENTS
                    or type(item.get('amount_minor')) is not int or item['amount_minor'] <= 0):
                raise _bad()
            amounts[item['component']] += item['amount_minor']
    return _seal(head, entries, amounts)


def current_observation(office, employee_id, month, calculation):
    from business_payroll_cash import installed, validate_integrity
    _scope(employee_id, month)
    try:
        with transaction(office):
            if not installed(office):
                value = _seal(0, [], dict.fromkeys(COMPONENTS, 0))
            else:
                validate_integrity(office)
                head = office.db.execute('SELECT MAX(sequence) FROM business_payroll_cash_batches').fetchone()[0] or 0
                value = _prefix(office, employee_id, month, head)
            _covered(calculation, value['amounts'])
            return value
    except (ValueError, KeyError, TypeError, IndexError) as error:
        raise _bad() from error
    except Problem as error:
        if error.status == 409:
            raise
        raise _bad() from error


def validate_observation(office, employee_id, month, calculation, observation):
    from business_payroll_cash import installed
    _scope(employee_id, month)
    try:
        if (not isinstance(observation, dict) or set(observation) != _FIELDS
                or type(observation['schema_version']) is not int or observation['schema_version'] != 1
                or type(observation['head_sequence']) is not int or not 0 <= observation['head_sequence'] <= 10**12
                or not isinstance(observation['entries'], list)
                or any(not isinstance(entry, dict) or set(entry) != _ENTRY_FIELDS for entry in observation['entries'])
                or not isinstance(observation['amounts'], dict) or set(observation['amounts']) != set(COMPONENTS)
                or any(type(value) is not int or value < 0 for value in observation['amounts'].values())):
            raise _bad()
        for entry in observation['entries']:
            if (not isinstance(entry['id'], str) or not re.fullmatch('[a-f0-9]{32}', entry['id'])
                    or type(entry['revision']) is not int or entry['revision'] < 1
                    or type(entry['sequence']) is not int or entry['sequence'] < 1
                    or not isinstance(entry['private_hash'], str)
                    or not re.fullmatch('[a-f0-9]{64}', entry['private_hash'])):
                raise _bad()
        with transaction(office):
            if installed(office):
                expected = _prefix(office, employee_id, month, observation['head_sequence'])
            else:
                expected = _seal(0, [], dict.fromkeys(COMPONENTS, 0))
            if observation != expected:
                raise _bad()
            _covered(calculation, expected['amounts'])
            return True
    except (ValueError, KeyError, TypeError, IndexError) as error:
        raise _bad() from error
    except Problem as error:
        if error.status == 409:
            raise
        raise _bad() from error

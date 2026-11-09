"""Read-only original/payment proofs for the bounded factor/travel case.

The existing travel and cash validators remain the authority. No payment,
posting, tax classification or historical travel record is created here.
"""
from core import Problem
from business_operations import identifier
from business_personnel_workflow import _sha
from business_payroll_facts import ref, reference


def payment_choices(office, actor, employee_id):
    from business_travel_allowances import TravelAllowances
    from travel_allowance_cash import financial_access
    financial_access(office, actor)
    api = TravelAllowances(office)
    api._employee(actor, employee_id, permission='personnel.read', own=False)
    return [dict(reference(value), settlement_ref=value['details']['settlement_ref'],
                 status=value['status'], kind=value['details']['kind'],
                 paid_on=value['details']['paid_on'], amount_minor=value['details']['amount_minor'])
            for value in api._all('payment', employee_id)]


def paid_taxfree_source(office, actor, employee_id, settlement_ref, payment_refs, month, *, fresh):
    from business_travel_allowances import TravelAllowances, validate_record, validate_payment
    from travel_allowance_cash import financial_access, public_source
    from payroll_de_2026 import month_range
    first, last = month_range(month)
    if first.year != 2026:
        raise Problem(400, 'Dieser Reisequellenvertrag gilt für 2026.')
    api = TravelAllowances(office)
    if actor is not None:
        financial_access(office, actor)
        api._employee(actor, employee_id, permission='personnel.read', own=False)
    settlement_ref = ref(settlement_ref)
    settlement = api._get('settlement', settlement_ref['id'], settlement_ref['revision'])
    if (reference(settlement) != settlement_ref or settlement['employee_id'] != employee_id
            or settlement['status'] != 'approved'
            or fresh and reference(api._get('settlement', settlement_ref['id'])) != settlement_ref):
        raise Problem(409, 'Aktuelle eigene unveränderte Reiseabrechnung erforderlich.')
    validate_record(api, settlement)
    if actor is not None:
        api._read_sources(actor, settlement)
    calculation, details = settlement['calculation'], settlement['details']
    totals = calculation['totals']
    if (calculation['rule_version'] not in ('de_travel_2026_v2', 'de_travel_2026_v3')
            or not calculation['can_approve'] or calculation['blockers']
            or totals['tax_free_minor'] <= 0
            or any(totals[key] for key in ('flat_taxable_minor', 'individual_taxable_minor'))
            or totals.get('expense_already_paid_minor', 0)
            or any(day['benefit_in_kind_minor'] or day['letter_m'] for day in calculation['days'])
            or details.get('payroll_month') not in (None, month)
            or details['period_from'][:7] != month or details['period_to'][:7] != month):
        raise Problem(409, 'Nur vollständig geprüfte steuerfreie Reisen desselben Monats ohne weiteren Lohnbestandteil sind zugelassen.')
    if not isinstance(payment_refs, list) or not payment_refs:
        raise Problem(409, 'Die bereits vollständig ausgeführte Reiseerstattung belegen.')
    selected, rows = {}, []
    for candidate in payment_refs:
        candidate = ref(candidate)
        if candidate['id'] in selected:
            raise Problem(400, 'Jede Reisezahlung genau einmal referenzieren.')
        value = api._get('payment', candidate['id'], candidate['revision'])
        if (reference(value) != candidate or value['employee_id'] != employee_id
                or value['details']['settlement_ref'] != settlement_ref
                or value['details'].get('legacy_payment') is not None
                or value['details']['paid_on'][:7] != month):
            raise Problem(409, 'Zahlungsoriginal gehört nicht zur eigenen Reise und zum Lohnmonat.')
        validate_payment(api, value)
        cash = public_source(office, value['id'], value['revision'])
        sequence = api._row('payment', value['id'], value['revision'])['sequence']
        selected[value['id']] = candidate
        rows.append(dict(candidate, sequence=sequence, status=value['status'], kind=value['details']['kind'],
                         paid_on=value['details']['paid_on'], amount_minor=value['details']['amount_minor'],
                         cash_source_hash=cash['source_hash']))
    cutoff = max(row['sequence'] for row in rows)
    expected = {}
    for row in api.db.execute('SELECT * FROM business_travel_payments WHERE sequence<=? ORDER BY sequence', (cutoff,)):
        value = api._view(row)
        if value['details']['settlement_ref']['id'] == settlement_ref['id']:
            expected[value['id']] = reference(value)
    if selected != expected:
        raise Problem(409, 'Den vollständigen Zahlungsstand einschließlich Rückzahlungen und Korrekturen binden.')
    if fresh:
        latest = {value['id']: reference(value) for value in api._all('payment', employee_id)
                  if value['details']['settlement_ref']['id'] == settlement_ref['id']}
        if selected != latest:
            raise Problem(409, 'Die Reisezahlungen wurden geändert; aktuellen Stand erneut prüfen.')
    rows.sort(key=lambda value: value['id'])
    paid = sum(row['amount_minor'] * (1 if row['kind'] == 'reimbursement' else -1)
               for row in rows if row['status'] != 'void')
    if paid != totals['tax_free_minor']:
        raise Problem(409, 'Die steuerfreie Reiseerstattung ist nicht vollständig tatsächlich ausgezahlt.')
    result = dict(kind='travel_allowances', schema_version=1, employee_id=employee_id, month=month,
                  settlement_ref=settlement_ref, rule_version=calculation['rule_version'],
                  rule_hash=calculation['rule_hash'], allocations=[], tax_free_external_minor=paid,
                  flat_taxable_payroll_minor=0, individual_taxable_payroll_minor=0,
                  benefit_in_kind_non_cash_minor=0, letter_m=False,
                  payment_proof=dict(schema_version=1, cutoff_sequence=cutoff, paid_minor=paid, payments=rows))
    return dict(result, source_hash=_sha(result))

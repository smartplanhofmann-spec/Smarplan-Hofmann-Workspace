"""Resolve fresh immutable sources for the explicit v16 entry/exit case."""
from core import Problem
from business_payroll_facts import reference
from payroll_de_2026 import month_range
from payroll_factor_transition_periods_2026 import RULE_VERSION, SOURCE_CONTRACT_VERSION, normalize_case_assessment


def snapshot(api, employee, details, ids, *, fresh, actor=None):
    employee_id = employee['id']
    review = normalize_case_assessment(details['factor_transition_period_assessment'])
    if review['employee_id'] != employee_id:
        raise Problem(400, 'Die Teilmonatsprognose gehört nicht zur gewählten Person.')
    if fresh and review['declaration_date'] > api.hr.now()[:10]:
        raise Problem(400, 'Die tatsächliche Teilmonatsprüfung darf nicht aus der Zukunft stammen.')
    evidence = review['forecast_evidence_ref']
    if evidence['id'] not in ids:
        raise Problem(400, 'Das tatsächliche Teilmonats-Prognoseoriginal ausdrücklich am Gesamtfall binden.')
    base = api.facts._fact_ref(employee_id, details['period_case_ref'], 'period_case', fresh=fresh)
    if base['plan']['rule_version'] != 'de_2026_standard_factor_period_v9' or base['details']['month'] != details['month']:
        raise Problem(400, 'Den ursprünglichen eigenen V9-Faktorperiodenfall desselben Monats verwenden.')
    original = base['sources']
    if fresh and api.facts._snapshot(employee, 'period_case', base['details'], base['source_file_ids']) != original:
        raise Problem(409, 'Die ursprüngliche Teilmonatsvorbereitung ist nicht mehr aktuell.')
    if (details['employment_terms_refs'] != [reference(original['employment_terms'])]
            or details['profile_refs'] != sorted([reference(r) for r in original['profiles']], key=lambda r: r['id'])
            or details['identity_refs'] != sorted([reference(r) for r in original['identities']], key=lambda r: r['id'])):
        raise Problem(400, 'Die vollständigen tatsächlichen Beschäftigungs- und Profiloriginale unverändert binden.')
    terms = [api.facts._fact_ref(employee_id, r, 'employment_terms', fresh=fresh) for r in details['employment_terms_refs']]
    profiles = [api.facts._payroll_ref(employee_id, r, fresh=fresh) for r in details['profile_refs']]
    identities = [api.facts._identity_ref(employee_id, r, fresh=fresh) for r in details['identity_refs']]
    if len(terms) != 1 or len(profiles) != 1 or len(identities) != 1:
        raise Problem(400, 'Genau eine ursprüngliche Beschäftigung, Faktorprofilfassung und Identität binden.')
    if fresh:
        first, last = month_range(details['month'])
        expected = [reference(r) for r in api.facts._all(employee_id, 'employment_terms')
            if r['status'] == 'active' and r['effective_from'] <= last.isoformat()
            and (r['effective_to'] is None or r['effective_to'] >= first.isoformat())]
        if sorted(expected, key=lambda r: r['id']) != details['employment_terms_refs']:
            raise Problem(409, 'Alle tatsächlich aktiven Beschäftigungsnachweise dieses Monats vollständig binden.')
        from business_payroll_entitlements import PayrollEntitlements
        from business_travel_allowances import TravelAllowances
        if any(r['status'] == 'active' and r['effective_from'] <= last.isoformat() and r['effective_to'] >= first.isoformat()
                for r in PayrollEntitlements(api.office)._all(employee_id)):
            raise Problem(409, 'Ein zusätzlicher tatsächlicher Anspruch gehört nicht zum einfachen Eintritts-/Austrittsteilmonat.')
        if any(r['status'] == 'approved' and r['details']['period_from'] <= last.isoformat()
                and r['details']['period_to'] >= first.isoformat()
                for r in TravelAllowances(api.office)._all('settlement', employee_id)):
            raise Problem(409, 'Ein tatsächlicher Reisebezug benötigt seinen eigenen Faktor-/Midijob-Teilmonatsvertrag.')
    files = api._files(employee_id, ids, fresh=fresh)
    if not any(r['id'] == evidence['id'] and r['content_hash'] == evidence['content_hash'] for r in files):
        raise Problem(409, 'Das ursprüngliche tatsächliche Prognoseoriginal wurde verändert.')
    if (details['segment_events'] or details['entitlement_case_refs'] or details['travel_settlement_refs']
            or details['flat_tax_decision'] is not None or details['thirty_day_rule'] != 'actual_days_capped_per_claim'):
        raise Problem(400, 'Dieser eigene Teilmonatsvertrag umfasst keine zusätzlichen Bezüge, Unterbrechungen oder Profilwechsel.')
    return dict(schema_version=1, source_contract_version=SOURCE_CONTRACT_VERSION, rule_version=RULE_VERSION,
        employee_id=employee_id, month=details['month'], period_case=base,
        employment_terms=terms, profiles=profiles, identities=identities,
        segment_events=[], thirty_day_rule=details['thirty_day_rule'], entitlements=[], travel_sources=[],
        flat_travel_tax=None, source_files=files, factor_transition_period_assessment=review)

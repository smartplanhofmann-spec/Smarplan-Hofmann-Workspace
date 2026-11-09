"""Resolve actual personal originals for the additive v11 minijob case."""
from core import Problem
from business_payroll_facts import reference
from payroll_de_2026 import month_range
from payroll_individual_minijob_2026 import (RULE_VERSION, SOURCE_CONTRACT_VERSION,
    REF_FIELDS, normalize_assessment)


def is_supported_upgrade(previous, current):
    """Only an unusable historical individual-minijob fact may change rules."""
    return (previous['kind'] == current['kind'] == 'calculation_case'
        and previous['status'] == current['status'] == 'active'
        and previous['rule_version'] == 'de_2026_segments_entitlements_v5'
        and previous['source_contract_version'] == 1
        and current['rule_version'] == RULE_VERSION
        and current['source_contract_version'] == SOURCE_CONTRACT_VERSION
        and previous['plan']['can_calculate'] is False
        and 'minijob_individual_tax' in {item['code'] for item in previous['plan']['blockers']}
        and len(previous['sources']['profiles']) == 1
        and previous['sources']['profiles'][0]['profile']['employment_kind'] == 'minijob'
        and previous['sources']['profiles'][0]['profile']['minijob_tax'] == 'individual'
        and current['plan']['can_calculate'] is True)


def require_unused_upgrade(api, previous, current):
    """Check all retained dependent sources while holding the write transaction.

    Any historical use counts, including a subsequently corrected/voided
    source. Unknown or malformed retained data is not evidence of non-use.
    """
    from business_payroll_calculation_cases import validate_case_sources
    validate_case_sources(api.office, previous)
    if not is_supported_upgrade(previous, current):
        raise Problem(400, 'Nur ein bisher nicht berechenbarer individueller v5-Minijobfall darf ausdrücklich zu v11 korrigiert werden.')

    def refers(value):
        if isinstance(value, dict):
            return value.get('id') == previous['id'] or any(refers(item) for item in value.values())
        return isinstance(value, list) and any(refers(item) for item in value)

    from business_schema import _tables
    from business_payroll import Payroll, validate_integrity as validate_payroll
    from business_payroll_accounts import PayrollAccounts, validate_integrity as validate_accounts
    from business_payroll_annual_basis import PayrollAnnualBasis, validate_integrity as validate_annual
    from business_payroll_oneoff_cases import PayrollOneoffCases, validate_integrity as validate_oneoff
    from business_payroll_multiple_cases import PayrollMultipleCases, validate_integrity as validate_multiple
    present = set(_tables(api.office))
    tables = {
        'business_payroll_events': Payroll(api.office),
        'business_payroll_account_events': PayrollAccounts(api.office),
        'business_payroll_annual_events': PayrollAnnualBasis(api.office),
        'business_payroll_oneoff_case_events': PayrollOneoffCases(api.office),
        'business_payroll_multiple_case_events': PayrollMultipleCases(api.office),
    }
    try:
        # A matching envelope hash alone does not establish a usable original:
        # absent/invalid source data could hide a dependency. Reuse the full
        # historical validators (including receipts, sources and arithmetic)
        # before treating an absent reference as evidence of non-use. These
        # validators never invoke this creation-only migration guard.
        for validate in (validate_payroll, validate_accounts, validate_annual, validate_oneoff, validate_multiple):
            validate(api.office)
        for table, resolver in tables.items():
            if table not in present:
                continue
            for row in api.db.execute('SELECT * FROM '+table+' WHERE employee_id=?', (previous['employee_id'],)):
                original = resolver._event(row)
                if refers(original):
                    raise Problem(409, 'Der ursprüngliche Gesamtfall ist bereits verbindlich verwendet; sein Regelvertrag bleibt erhalten.')
    except Problem as error:
        if error.status == 409:raise
        raise Problem(409, 'Die vollständige bisherige Verwendung des Gesamtfalls kann nicht sicher ausgeschlossen werden.') from None
    except (ValueError, TypeError, RecursionError, KeyError):
        raise Problem(409, 'Die vollständige bisherige Verwendung des Gesamtfalls kann nicht sicher ausgeschlossen werden.') from None


def snapshot(api, employee, details, ids, *, fresh, actor=None):
    employee_id = employee['id']
    assessment = normalize_assessment(details['individual_minijob_assessment'])
    if assessment['employee_id'] != employee_id:
        raise Problem(400, 'Minijobprüfung gehört nicht zur gewählten Person.')
    if fresh and assessment['declaration_date'] > api.hr.now()[:10]:
        raise Problem(400, 'Die tatsächliche Minijobprüfung darf nicht aus der Zukunft stammen.')
    original_ids = {assessment[key]['id'] for key in REF_FIELDS}
    if not original_ids.issubset(ids):
        raise Problem(400, 'Alle tatsächlich genannten Prüfungsoriginale am Gesamtfall binden.')
    base = api.facts._fact_ref(employee_id, details['period_case_ref'], 'period_case', fresh=fresh)
    if base['plan']['rule_version'] != 'de_2026_periods_pap_v4' or base['details']['month'] != details['month']:
        raise Problem(400, 'Unveränderten v4-Minijobperiodenfall desselben Monats verwenden.')
    original = base['sources']
    if fresh and api.facts._snapshot(employee, 'period_case', base['details'], base['source_file_ids']) != original:
        raise Problem(409, 'Die ursprüngliche Monatsvorbereitung wurde geändert.')
    if (details['employment_terms_refs'] != [reference(original['employment_terms'])]
            or details['profile_refs'] != sorted([reference(value) for value in original['profiles']], key=lambda row:row['id'])
            or details['identity_refs'] != sorted([reference(value) for value in original['identities']], key=lambda row:row['id'])):
        raise Problem(400, 'Die vollständigen ursprünglichen Monatsquellen unverändert binden.')
    terms = [api.facts._fact_ref(employee_id, value, 'employment_terms', fresh=fresh) for value in details['employment_terms_refs']]
    profiles = [api.facts._payroll_ref(employee_id, value, fresh=fresh) for value in details['profile_refs']]
    identities = [api.facts._identity_ref(employee_id, value, fresh=fresh) for value in details['identity_refs']]
    if len(profiles) != 1 or len(identities) != 1 or len(terms) != 1:
        raise Problem(400, 'Genau ein tatsächliches Beschäftigungsverhältnis, Profil und ELStAM-Original verwenden.')
    # A newly added overlapping employment is material even if old references
    # still resolve. Preserve historical verification but reject new use.
    if fresh:
        first, last = month_range(details['month'])
        expected = [reference(value) for value in api.facts._all(employee_id, 'employment_terms')
            if value['status']=='active' and value['effective_from']<=last.isoformat()
            and (value['effective_to'] is None or value['effective_to']>=first.isoformat())]
        if sorted(expected,key=lambda row:row['id']) != details['employment_terms_refs']:
            raise Problem(409, 'Alle tatsächlich aktiven Beschäftigungsnachweise dieses Monats müssen enthalten sein.')
        from business_payroll_entitlements import PayrollEntitlements
        from business_travel_allowances import TravelAllowances
        if any(value['status']=='active' and value['effective_from']<=last.isoformat() and value['effective_to']>=first.isoformat()
                for value in PayrollEntitlements(api.office)._all(employee_id)):
            raise Problem(409, 'Ein zusätzlicher tatsächlicher Anspruch benötigt seinen eigenen Regelzweig.')
        if any(value['status']=='approved' and value['details']['period_from']<=last.isoformat()
                and value['details']['period_to']>=first.isoformat()
                for value in TravelAllowances(api.office)._all('settlement',employee_id)):
            raise Problem(409, 'Ein tatsächlicher Reisebezug ist nicht im ersten individuellen Minijobvertrag enthalten.')
    files = api._files(employee_id, ids, fresh=fresh)
    indexed = {value['id']:value for value in files}
    for key in REF_FIELDS:
        ref=assessment[key]; actual=indexed[ref['id']]
        if actual['content_hash'] != ref['content_hash']:
            raise Problem(409, 'Ein tatsächliches Minijob-Prüfungsoriginal wurde verändert.')
    if (details['segment_events'] or details['entitlement_case_refs'] or details['travel_settlement_refs']
            or details['flat_tax_decision'] is not None or details['thirty_day_rule'] is not None):
        raise Problem(400, 'Der erste individuelle Minijobvertrag umfasst keine Zusatz-/Untermonatigkeitsfälle.')
    return dict(schema_version=1, source_contract_version=SOURCE_CONTRACT_VERSION, rule_version=RULE_VERSION,
        employee_id=employee_id, month=details['month'], period_case=base, employment_terms=terms,
        profiles=profiles, identities=identities, segment_events=[], thirty_day_rule=None, entitlements=[],
        travel_sources=[], flat_travel_tax=None, source_files=files, individual_minijob_assessment=assessment)

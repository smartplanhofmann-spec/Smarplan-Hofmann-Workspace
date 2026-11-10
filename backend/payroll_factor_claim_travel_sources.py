"""Creation-only upgrades of unused factor cases; old rule helpers stay frozen."""
from core import Problem
from payroll_factor_claim_travel_2026 import RULE_VERSION, SOURCE_CONTRACT_VERSION


def is_supported_upgrade(previous, current):
    if (previous.get('kind') != 'calculation_case' or current.get('kind') != 'calculation_case'
            or previous.get('status') != 'active' or current.get('status') != 'active'
            or current.get('rule_version') != RULE_VERSION
            or current.get('source_contract_version') != SOURCE_CONTRACT_VERSION
            or current.get('plan',{}).get('can_calculate') is not True
            or previous.get('employee_id') != current.get('employee_id')):
        return False
    contracts = {'de_2026_factor_taxfree_travel_month_v10':2, 'de_2026_factor_claims_month_v12':4}
    if previous.get('rule_version') not in contracts or previous.get('source_contract_version') != contracts[previous['rule_version']]:
        return False
    old, new = previous.get('sources',{}), current.get('sources',{})
    if (not old or not new or old.get('month') != new.get('month')
            or any(old.get(key) != new.get(key) for key in ('period_case','employment_terms','profiles','identities'))
            or not set(previous.get('source_file_ids',[])).issubset(current.get('source_file_ids',[]))):
        return False
    # Only add the previously absent component. Preserve the already reviewed
    # original claim or paid-trip component exactly, including its full proof.
    if previous['rule_version'] == 'de_2026_factor_claims_month_v12':
        return (not old.get('travel_sources') and old.get('flat_travel_tax') is None
                and old.get('entitlements') == new.get('entitlements'))
    return not old.get('entitlements') and old.get('travel_sources') == new.get('travel_sources')


def require_unused_upgrade(api, previous, current):
    from business_payroll_calculation_cases import validate_case_sources
    validate_case_sources(api.office, previous)
    if not is_supported_upgrade(previous,current):
        raise Problem(400,'Nur den fehlenden Bestandteil eines unbenutzten V10-/V12-Originalfalls ausdrücklich ergänzen.')

    def refers(value):
        if isinstance(value,dict):
            return value.get('id') == previous['id'] or any(refers(v) for v in value.values())
        return isinstance(value,list) and any(refers(v) for v in value)

    from business_schema import _tables
    from business_payroll import Payroll, validate_integrity as validate_payroll
    from business_payroll_accounts import PayrollAccounts, validate_integrity as validate_accounts
    from business_payroll_annual_basis import PayrollAnnualBasis, validate_integrity as validate_annual
    from business_payroll_oneoff_cases import PayrollOneoffCases, validate_integrity as validate_oneoff
    from business_payroll_multiple_cases import PayrollMultipleCases, validate_integrity as validate_multiple
    present = set(_tables(api.office))
    resolvers = {
        'business_payroll_events':Payroll(api.office),
        'business_payroll_account_events':PayrollAccounts(api.office),
        'business_payroll_annual_events':PayrollAnnualBasis(api.office),
        'business_payroll_oneoff_case_events':PayrollOneoffCases(api.office),
        'business_payroll_multiple_case_events':PayrollMultipleCases(api.office),
    }
    try:
        for validate in (validate_payroll,validate_accounts,validate_annual,validate_oneoff,validate_multiple):
            validate(api.office)
        for table,resolver in resolvers.items():
            if table not in present:
                continue
            for row in api.db.execute('SELECT * FROM '+table+' WHERE employee_id=?',(previous['employee_id'],)):
                if refers(resolver._event(row)):
                    raise Problem(409,'Der frühere Faktorfall wurde bereits verwendet; seine ursprüngliche Regel bleibt erhalten.')
    except Problem as error:
        if error.status == 409:
            raise
        raise Problem(409,'Die vollständige Nichtverwendung des früheren Faktorfalls ist nicht nachgewiesen.') from None
    except (ValueError,TypeError,KeyError,RecursionError):
        raise Problem(409,'Die vollständige Nichtverwendung des früheren Faktorfalls ist nicht nachgewiesen.') from None

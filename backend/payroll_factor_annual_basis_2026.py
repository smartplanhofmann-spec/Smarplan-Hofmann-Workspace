"""Explicit V2 annual projection of original factor/P4 monthly cases.

Only source-bound arithmetic. Database authority and fresh original checks
belong to FactorAnnualBasis. V1 annual sources are never rewritten.
"""
import hashlib
from pathlib import Path

from core import Problem,canonical
from business_payroll_facts import reference
import payroll_annual_basis_2026 as annual
import payroll_factor_claims_2026 as factor
from payroll_factor_2026 import normalize_factor_profile

RULE_VERSION='de_2026_factor_planned_annual_basis_v2'
CONTRACT=dict(version=2,rule_version=RULE_VERSION)
RULES=dict(version=RULE_VERSION,original_case_rule=factor.RULE_VERSION,
    original_case_contract=factor.SOURCE_CONTRACT_VERSION,
    original_annual_component=annual.ANNUAL_BASIS_VERSION,
    module_sha256=hashlib.sha256(Path(__file__).read_bytes().replace(b'\r\n',b'\n')).hexdigest())
RULES_HASH=hashlib.sha256(canonical(RULES).encode()).hexdigest()


def build_plan(snapshot,*,rule_version=RULE_VERSION):
    contract=snapshot.get('annual_source_contract')
    if (rule_version!=RULE_VERSION or not isinstance(contract,dict) or contract!=CONTRACT
            or type(contract.get('version')) is not int):
        raise Problem(400,'Ausdrücklichen Faktor-Jahresquellenvertrag V2 verwenden.')
    kind=snapshot.get('kind')
    if kind=='annual_basis':
        case=snapshot.get('current_calculation_case')
    elif kind=='annual_tax_forecast':
        basis=snapshot.get('annual_basis',{})
        if basis.get('sources',{}).get('annual_source_contract')!=CONTRACT:
            raise Problem(409,'Die Faktor-Steuerprognose benötigt ihre tatsächlich gebundene V2-Jahresbasis.')
        case=basis['sources']['current_calculation_case']
    else:
        raise Problem(400,'Der Faktor-Jahresvertrag umfasst genau Jahresbasis und Jahressteuerprognose.')
    if (not isinstance(case,dict) or case.get('rule_version')!=factor.RULE_VERSION
            or case.get('source_contract_version')!=factor.SOURCE_CONTRACT_VERSION
            or case.get('employee_id')!=snapshot['employee']['id']):
        raise Problem(409,'Tatsächlichen eigenen vollständigen Faktor-/P4-Monatsfall binden.')
    plan=factor.build_plan(case['sources'])
    if plan!=case['plan'] or not plan['can_calculate']:
        raise Problem(409,'Der Faktor-/P4-Originalfall ist nicht unverändert vollständig nachgerechnet.')
    profile=case['sources']['profiles'][0]
    if normalize_factor_profile(profile['profile'])!=profile['profile']:
        raise Problem(409,'Das tatsächliche Faktorprofil ist nicht unverändert normiert.')
    if kind=='annual_tax_forecast' and reference(snapshot['tax_identity']['sources']['profile'])!=reference(profile):
        raise Problem(409,'Die Jahressteuerprognose benötigt genau das ursprüngliche Faktorprofil des Zuflussmonats.')
    # V1's unchanged arithmetic consumes the same actual period/receipt
    # originals. Only the explicit source contract and resulting plan version
    # differ; no factor profile or accepted case is projected into a V5 shadow.
    result=annual.build_annual_plan(snapshot)
    result.pop('plan_hash');result.pop('can_confirm')
    result.update(rule_version=RULE_VERSION,rules_sha256=RULES_HASH,
        factor_case_ref=reference(case),factor_profile_ref=reference(profile))
    result['plan_hash']=hashlib.sha256(canonical(result).encode()).hexdigest()
    return dict(result,can_confirm=True)

"""Additive composition of frozen P4 factor wages and already-paid travel.

The v12 projection is the sole wage/tax/SV calculation. The independent v10
projection is used only to validate original paid tax-free travel. Its ordinary
wage figures never enter this result. No historical original is rewritten.
"""
from copy import deepcopy
import hashlib
from pathlib import Path

from core import Problem, canonical
import payroll_factor_claims_2026 as claims
import payroll_factor_taxfree_travel_2026 as travel

RULE_VERSION = 'de_2026_factor_claims_paid_travel_month_v13'
SOURCE_CONTRACT_VERSION = 5
SCOPE = 'regular_standard_factor_claims_paid_travel_month'
FEATURE = 'payroll_factor_claims_paid_travel'
PROJECTIONS = dict(
    claims='UNCHANGED_ORIGINALS_WITH_TRAVEL_SOURCES_EMPTY_AND_FLAT_TRAVEL_TAX_NULL',
    paid_travel='UNCHANGED_ORIGINALS_WITH_ENTITLEMENTS_EMPTY_FOR_TRAVEL_PROOF_ONLY')
ROOT = Path(__file__).resolve().parent
RULES = dict(version=RULE_VERSION, source_contract_version=SOURCE_CONTRACT_VERSION,
    supported_case='ONE_FULL_FACTOR_MONTH_COMPLETE_P4_ORIGINALS_FULLY_PAID_TAXFREE_EXTERNAL_TRAVEL',
    wage_component=claims.RULE_VERSION, wage_rules_sha256=claims.RULES_SHA256,
    travel_proof_component=travel.RULE_VERSION, travel_rules_sha256=travel.RULES_SHA256,
    projections=PROJECTIONS, travel_payment='NEVER_ADD_SEPARATELY_PAID_TRAVEL_TO_WAGE_GROSS_OR_NET',
    travel_component_wage_review=dict(zero_earnings_requires_review=
        'SATISFIED_ONLY_BY_COMPLETE_V12_POSITIVE_P4_WAGE_AND_FULL_SOCIAL_MONTH'),
    care_contribution_method=claims.RULES['care_contribution_method'],
    source_encoding='UTF8_CANONICAL_LF',
    sources={name:hashlib.sha256((ROOT/name).read_bytes().replace(b'\r\n',b'\n')).hexdigest()
        for name in ('payroll_factor_claims_2026.py','payroll_factor_taxfree_travel_2026.py',
                     'payroll_factor_taxfree_sources.py')},
    module_sha256=hashlib.sha256(Path(__file__).read_bytes().replace(b'\r\n',b'\n')).hexdigest(),
    runtime_network=False, official_system_approval=False)


def _sha(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


RULES_SHA256 = _sha(RULES)
FIELDS = {'schema_version','source_contract_version','rule_version','employee_id','month','period_case',
    'employment_terms','profiles','identities','segment_events','thirty_day_rule','entitlements',
    'travel_sources','flat_travel_tax','source_files'}


def projections(snapshot):
    wage = deepcopy(snapshot)
    wage.update(rule_version=claims.RULE_VERSION, source_contract_version=claims.SOURCE_CONTRACT_VERSION,
                travel_sources=[], flat_travel_tax=None)
    proof = deepcopy(snapshot)
    proof.update(rule_version=travel.RULE_VERSION, source_contract_version=travel.SOURCE_CONTRACT_VERSION,
                 entitlements=[])
    return wage, proof


def build_plan(snapshot, *, rule_version=RULE_VERSION, source_contract_version=SOURCE_CONTRACT_VERSION):
    if (not isinstance(snapshot,dict) or set(snapshot)!=FIELDS or type(snapshot['schema_version']) is not int
            or snapshot['schema_version']!=1 or rule_version!=RULE_VERSION or snapshot['rule_version']!=RULE_VERSION
            or type(source_contract_version) is not int or source_contract_version!=SOURCE_CONTRACT_VERSION
            or type(snapshot['source_contract_version']) is not int
            or snapshot['source_contract_version']!=SOURCE_CONTRACT_VERSION):
        raise Problem(400,'Eigenen vollständigen Faktor-/Anspruchs-/Reisevertrag ausdrücklich verwenden.')
    wage_source, proof_source = projections(snapshot)
    wage_plan, proof_plan = claims.build_plan(wage_source), travel.build_plan(proof_source)
    # A fully evidenced hourly holiday can have zero actual project-work pay
    # in its v9 original. V12 performs the missing complete P4/SV review and
    # supplies the real positive wage. Preserve the old v10 blocked plan; only
    # this exact wage-review code is satisfied by the successful wage component.
    satisfied_reviews = (['zero_earnings_requires_review']
        if wage_plan['can_calculate'] and wage_plan['gross_minor'] > 0
        and any(row['code']=='zero_earnings_requires_review' for row in proof_plan['blockers']) else [])
    blockers = {row['code']:row for row in wage_plan['blockers']}
    for row in proof_plan['blockers']:
        if row['code'] not in satisfied_reviews:
            blockers.setdefault(row['code'],row)
    components = {}
    for name, source, plan in (('claims',wage_source,wage_plan),('paid_travel',proof_source,proof_plan)):
        components[name] = dict(rule_version=source['rule_version'],
            source_contract_version=source['source_contract_version'], rules_sha256=plan['rules_sha256'],
            projection=PROJECTIONS[name], source_snapshot_hash=_sha(source), plan_hash=plan['plan_hash'],
            plan=deepcopy(plan))
    plan = {k:deepcopy(v) for k,v in wage_plan.items() if k not in ('plan_hash','can_confirm','can_calculate')}
    plan.update(rule_version=RULE_VERSION, source_contract_version=SOURCE_CONTRACT_VERSION,
        rules_sha256=RULES_SHA256, source_snapshot_hash=_sha(snapshot), components=components,
        travel=proof_plan['travel'], travel_source_hashes=proof_plan['travel_source_hashes'],
        travel_payment_refs=proof_plan['travel_payment_refs'], travel_paid_minor=proof_plan['travel_paid_minor'],
        satisfied_travel_component_wage_reviews=satisfied_reviews,
        blockers=sorted(blockers.values(),key=lambda row:row['code']))
    plan['plan_hash'] = _sha(plan)
    return dict(plan,can_confirm=True,can_calculate=not blockers)


def calculate_source(snapshot, *, rule_version=RULE_VERSION, source_contract_version=SOURCE_CONTRACT_VERSION):
    plan = build_plan(snapshot,rule_version=rule_version,source_contract_version=source_contract_version)
    wage_source, _ = projections(snapshot)
    result = deepcopy(claims.calculate_source(wage_source))
    result.update(rule_version=RULE_VERSION, source_contract_version=SOURCE_CONTRACT_VERSION,
        rules_sha256=RULES_SHA256, scope=SCOPE if not plan['blockers'] else 'unsupported',
        blockers=plan['blockers'], payroll_calculation_complete=not plan['blockers'],
        social_contributions_available=not plan['blockers'], travel_expenses_included_in_net=False,
        tax_method='individual_2026_verified_factor_claims_with_separately_paid_taxfree_travel')
    result['period_details'].update({key:deepcopy(plan[key]) for key in (
        'plan_hash','source_snapshot_hash','components','travel','travel_source_hashes',
        'travel_payment_refs','travel_paid_minor','satisfied_travel_component_wage_reviews')})
    if plan['blockers']:
        for key in claims.AMOUNTS:
            result[key] = None
        result['net_deductions_minor'] = None
    return result

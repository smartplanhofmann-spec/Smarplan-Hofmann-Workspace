"""Additive original-bound full-month factor pay with independently sourced P4 claims.

No historical source, profile, work hour or calculation kernel is rewritten.
The v5 structural claim plan remains a component of this explicit new contract.
"""
from copy import deepcopy
from decimal import Decimal
import hashlib
from pathlib import Path

from core import Problem, canonical
from business_payroll_facts import reference
from payroll_calculations_2026 import build_calculation_plan, CALCULATION_RULE_VERSION
from payroll_factor_2026 import calculate_factor, normalize_factor_profile
from payroll_factor_periods_2026 import (build_factor_period_plan, calculate_factor_period_tax,
    FACTOR_PERIOD_RULE_VERSION, FACTOR_PERIOD_PAP_VERSION, FACTOR_PERIOD_PAP_SHA256)
from payroll_de_2026 import month_range
from payroll_transition_2026 import care_contributions

RULE_VERSION = 'de_2026_factor_claims_month_v12'
SOURCE_CONTRACT_VERSION = 4
SCOPE = 'regular_standard_factor_claims_month'
FEATURE = 'payroll_factor_claims'
_ROOT = Path(__file__).resolve().parent
RULES = dict(version=RULE_VERSION, source_contract_version=SOURCE_CONTRACT_VERSION,
    supported_case='ONE_REGULAR_FACTOR_PROFILE_ONE_FULL_TAX_AND_SOCIAL_MONTH_WITH_COMPLETE_P4_ORIGINALS',
    structural_component=CALCULATION_RULE_VERSION, original_period_component=FACTOR_PERIOD_RULE_VERSION,
    factor_from='EXPLICIT_VERIFIED_CLASS_IV_PROFILE', work_time='NEVER_INVENT_OR_REWRITE_APPROVED_PROJECT_TIME',
    care_contribution_method='ROUND_BASE_AND_ADJUSTMENTS_SEPARATELY_GKV_2025_03_31_SECTION_3_3',
    source_encoding='UTF8_CANONICAL_LF',
    sources={name:hashlib.sha256((_ROOT/name).read_bytes().replace(b'\r\n',b'\n')).hexdigest()
        for name in ('payroll_calculations_2026.py', 'payroll_claims_composition_2026.py',
            'payroll_segments_2026.py', 'payroll_periods_2026.py', 'payroll_factor_2026.py',
            'payroll_factor_periods_2026.py', 'payroll_de_2026.py', 'payroll_transition_2026.py',
            'payroll_pap_factor_2026.py', 'payroll_pap_2026.py', 'payroll_pap_periods_2026.py')},
    module_sha256=hashlib.sha256(Path(__file__).read_bytes().replace(b'\r\n',b'\n')).hexdigest(),
    official_xml_sha256='63d8981646d139eba2f4dd990c13b43c4fb3883b402a5a40cddf253aa7aa96b4',
    runtime_network=False, official_system_approval=False)
RULES_SHA256 = hashlib.sha256(canonical(RULES).encode()).hexdigest()
AMOUNTS = ('employee_contributions', 'employer_contributions', 'employee_social_total_minor',
    'employer_social_total_minor', 'employer_levies', 'employer_flat_tax_minor',
    'employer_total_excluding_accident_insurance_minor', 'individual_wage_tax_minor',
    'solidarity_minor', 'church_tax_minor', 'employee_tax_minor', 'net_minor', 'payout_minor',
    'employee_additional_payment_minor')


def _sha(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def build_plan(snapshot, *, rule_version=RULE_VERSION, source_contract_version=SOURCE_CONTRACT_VERSION):
    fields={'schema_version','source_contract_version','rule_version','employee_id','month','period_case',
        'employment_terms','profiles','identities','segment_events','thirty_day_rule','entitlements',
        'travel_sources','flat_travel_tax','source_files'}
    if (not isinstance(snapshot,dict) or set(snapshot)!=fields or type(snapshot['schema_version']) is not int
            or snapshot['schema_version']!=1 or rule_version!=RULE_VERSION or snapshot['rule_version']!=RULE_VERSION
            or type(source_contract_version) is not int or source_contract_version!=SOURCE_CONTRACT_VERSION
            or type(snapshot['source_contract_version']) is not int or snapshot['source_contract_version']!=SOURCE_CONTRACT_VERSION):
        raise Problem(400,'Ausdrücklichen neuen Quellenvertrag für Faktor und belegte Lohnansprüche verwenden.')
    base=snapshot['period_case'];original=base['sources']
    if base['plan']['rule_version']!=FACTOR_PERIOD_RULE_VERSION:
        raise Problem(400,'Unveränderten eigenen Faktor-Periodenfall als Anspruchsgrundlage binden.')
    ordinary=build_factor_period_plan(original)
    if ordinary!=base['plan']:
        raise Problem(409,'Ursprünglicher Faktorperiodenplan ist nicht unverändert nachgerechnet.')
    if (snapshot['profiles']!=original['profiles'] or snapshot['identities']!=original['identities']
            or snapshot['employment_terms']!=[original['employment_terms']] or len(snapshot['profiles'])!=1):
        raise Problem(400,'Dieser Faktor-Anspruchsfall benötigt genau das ursprüngliche Profil, die Identität und eine Beschäftigung.')
    profile=snapshot['profiles'][0]
    if normalize_factor_profile(profile['profile'])!=profile['profile']:
        raise Problem(400,'Unverändertes normalisiertes Faktorprofil erforderlich.')
    # Only the component's explicit dispatch fields differ. Every frozen
    # employee/profile/identity/contract/claim original remains byte-for-byte.
    structural=build_calculation_plan(dict(snapshot,rule_version=CALCULATION_RULE_VERSION,source_contract_version=1),
        rule_version=CALCULATION_RULE_VERSION,source_contract_version=1)
    plan={key:value for key,value in structural.items() if key not in ('plan_hash','can_confirm','can_calculate')}
    blockers=[value for value in plan['blockers'] if value['code']!='special_case:tax_factor']
    def block(code,message):
        if not any(v['code']==code for v in blockers):blockers.append(dict(code=code,message=message))
    first,last=month_range(snapshot['month'])
    if (len(plan['employment_intervals'])!=1 or len(plan['tax_periods'])!=1 or len(plan['social_periods'])!=1
            or any(p['start']!=first.isoformat() or p['end']!=last.isoformat() for p in plan['employment_intervals'])
            or any(p['lzz']!=2 or p['tax_days']!=30 for p in plan['tax_periods'])
            or any(p['days']!=30 or p['full_month'] is not True for p in plan['social_periods'])):
        block('factor_claims_full_month_required','Dieser Anspruchsvertrag benötigt einen vollständigen tatsächlichen Steuer- und SV-Monat.')
    if not snapshot['entitlements']:
        block('factor_claims_original_required','Mindestens einen tatsächlichen vollständigen P4-Anspruch binden.')
    if snapshot['segment_events'] or snapshot['thirty_day_rule'] is not None:
        block('factor_claims_other_period_required','Profilwechsel und weitere Teilperioden benötigen ihren eigenen Faktor-Anspruchsvertrag.')
    if snapshot['travel_sources'] or snapshot['flat_travel_tax'] is not None:
        block('factor_claims_travel_requires_rule','Gleichzeitiger Reiselohn benötigt seinen eigenen vollständigen Faktor-/Anspruchs-/Reisevertrag.')
    if not blockers and any(p['gross_minor']!=plan['gross_minor'] or p['profile_ref']!=reference(profile)
            for p in plan['tax_periods']+plan['social_periods']):
        raise Problem(409,'Anspruchsbrutto und vollständige ursprüngliche Steuer-/SV-Zuordnung müssen genau übereinstimmen.')
    if not blockers:
        component=calculate_factor(profile['profile'],snapshot['month'],plan['gross_minor'],full_month_confirmed=True)
        for issue in component['blockers']:block(issue['code'],issue['message'])
    plan.update(rule_version=RULE_VERSION,source_contract_version=SOURCE_CONTRACT_VERSION,
        rules_sha256=RULES_SHA256,source_snapshot_hash=_sha(snapshot),
        care_contribution_method=RULES['care_contribution_method'],
        factor_parameters=dict(tax_factor=profile['profile']['tax_factor'],profile_ref=reference(profile)),
        blockers=sorted(blockers,key=lambda value:value['code']))
    plan['plan_hash']=_sha(plan)
    return dict(plan,can_confirm=True,can_calculate=not blockers)


def calculate_source(snapshot, *, rule_version=RULE_VERSION, source_contract_version=SOURCE_CONTRACT_VERSION):
    plan=build_plan(snapshot,rule_version=rule_version,source_contract_version=source_contract_version)
    profile=snapshot['profiles'][0]['profile'];gross=plan['gross_minor']
    result=deepcopy(calculate_factor(profile,snapshot['month'],gross if gross is not None else 0,full_month_confirmed=True))
    result.update(rule_version=RULE_VERSION,source_contract_version=SOURCE_CONTRACT_VERSION,rules_sha256=RULES_SHA256,
        scope=SCOPE if not plan['blockers'] else 'unsupported',gross_minor=gross,
        pap_version=FACTOR_PERIOD_PAP_VERSION,pap_provenance_sha256=FACTOR_PERIOD_PAP_SHA256,
        payroll_calculation_complete=not plan['blockers'],social_contributions_available=not plan['blockers'],
        blockers=plan['blockers'],travel_expenses_included_in_net=False,net_deductions_minor=0)
    result['period_details']={key:plan[key] for key in ('plan_hash','source_snapshot_hash','employment_intervals',
        'identity_intervals','earnings','tax_periods','social_periods','entitlement_sources','unpaid_dates',
        'social_continuation','travel','flat_travel_tax','travel_source_hashes','factor_parameters','care_contribution_method')}
    result['period_details'].update(social_assessments=[],tax_calculations=[])
    if plan['blockers']:
        for key in AMOUNTS:result[key]=None
        result['net_deductions_minor']=None
        return result
    tax=calculate_factor_period_tax(gross_minor=gross,lzz=2,tax_days=30,factor=profile['tax_factor'],tax_class=4,
        children_half_units=profile['tax_children_half_units'],additional_health_percent=format(Decimal(profile['health_additional_percent']),'.2f'),
        saxony=profile['federal_state']=='SN',childless_surcharge=result['care_childless_surcharge'],
        care_child_discounts=result['care_discount_children'],church_member=profile['church_tax']!='none')
    church_rate=int(result['tax_parameters']['church_tax_percent'])
    if (tax['totals']['LSTLZZ']!=result['individual_wage_tax_minor'] or tax['totals']['SOLZLZZ']!=result['solidarity_minor']
            or tax['totals']['BK']*church_rate//100!=result['church_tax_minor']):
        raise Problem(409,'Beide bestehenden Faktor-PAP-Zahlenwege müssen auf dem tatsächlichen Anspruchsbrutto centgenau übereinstimmen.')
    period=plan['social_periods'][0];caps=period['caps']
    bases={key:dict(total_minor=min(gross,caps[cap]),employee_minor=min(gross,caps[cap]))
        for key,cap in (('health_general','health_minor'),('health_additional','health_minor'),('care','care_minor'),
            ('pension','pension_minor'),('unemployment','unemployment_minor'))}
    own,firm,care=care_contributions(bases['care']['total_minor'],bases['care']['employee_minor'],
        saxony=profile['federal_state']=='SN',surcharge=result['care_childless_surcharge'],
        discount_count=result['care_discount_children'],reduced=False)
    # GKV31.03.2025 section3.3 permits one-step and two-step PV rounding.
    # V12 explicitly retains the same two-step method as the P4/v5 component;
    # the v8 scalar component and its historical one-step results stay frozen.
    result['employee_contributions']['care']=own
    result['employer_contributions']['care']=firm
    result['employee_social_total_minor']=sum(result['employee_contributions'].values())
    result['employer_social_total_minor']=sum(result['employer_contributions'].values())
    net=gross-result['employee_social_total_minor']-result['employee_tax_minor']
    result.update(net_minor=net,payout_minor=max(0,net),employee_additional_payment_minor=max(0,-net),
        employer_total_excluding_accident_insurance_minor=gross+result['employer_social_total_minor']
            +sum(result['employer_levies'].values())+result['employer_flat_tax_minor'])
    result['period_details'].update(tax_calculation=tax,
        tax_calculations=[dict(period=plan['tax_periods'][0],calculation=tax,
            church_tax_percent=church_rate,church_tax_minor=result['church_tax_minor'])],
        social_assessments=[dict(period=period,branch_bases=bases,transition=None,care_adjustments=care,
            employee_contributions=result['employee_contributions'],employer_contributions=result['employer_contributions'],
            employer_levies=result['employer_levies'],levy_assessment_minor=min(gross,caps['pension_minor']))])
    result['tax_method']='individual_2026_verified_factor_claims_month'
    return result

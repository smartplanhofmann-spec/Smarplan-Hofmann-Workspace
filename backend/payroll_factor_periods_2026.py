"""Additive class-IV factor rule for an explicitly sourced ordinary period.

One employment episode, agreement, factor/insurance profile; no transitions,
one-off pay or claim/benefit estimation. All historical kernels stay bytewise
unchanged. The original profile and source references are never rewritten.
"""
from decimal import Decimal
from datetime import date
import hashlib
from pathlib import Path

from core import Problem, canonical
from payroll_de_2026 import _age_completed, _portion, day, integer, month_range
from payroll_factor_2026 import normalize_factor_profile
from payroll_pap_factor_2026 import calculate_standard_factor_tax, FACTOR_PAP_VERSION
from payroll_pap_periods_2026 import period_tax_inputs, DAILY_PAP_VERSION
from payroll_periods_2026 import build_period_plan, PERIOD_RULE_VERSION
from payroll_transition_2026 import care_contributions


FACTOR_PERIOD_RULE_VERSION = 'de_2026_standard_factor_period_v9'
FACTOR_PERIOD_SCOPE = 'regular_standard_factor_period'
FACTOR_PERIOD_PAP_VERSION = 'bmf_2026_standard_factor_period_wrapper_v2'
_ROOT=Path(__file__).resolve().parent
FACTOR_PERIOD_SOURCE_SHA256={name:hashlib.sha256((_ROOT/name).read_bytes().replace(b'\r\n',b'\n')).hexdigest()
    for name in ('payroll_pap_2026.py','payroll_pap_factor_2026.py','payroll_factor_2026.py','payroll_pap_periods_2026.py',
                 'payroll_periods_2026.py','payroll_de_2026.py','payroll_transition_2026.py')}
FACTOR_PERIOD_PAP_RULES = dict(version=FACTOR_PERIOD_PAP_VERSION,
    factor_annual_version=FACTOR_PAP_VERSION, ordinary_period_inputs_version=DAILY_PAP_VERSION,
    source_sha256=FACTOR_PERIOD_SOURCE_SHA256,source_encoding='UTF8_CANONICAL_LF',
    module_sha256=hashlib.sha256(Path(__file__).read_bytes().replace(b'\r\n',b'\n')).hexdigest(),
    input_periods=[2,4], daily_annual_multiplier=360,
    daily_distribution='TRUNCATE_EACH_ANNUAL_FACTORED_COMPONENT_DIVIDE_360_THEN_MULTIPLY_ACTUAL_TAX_DAYS',
    factor_from='EXPLICIT_EFFECTIVE_VERIFIED_CLASS_IV_PROFILE',
    official_xml_sha256='63d8981646d139eba2f4dd990c13b43c4fb3883b402a5a40cddf253aa7aa96b4',
    source='https://www.gesetze-im-internet.de/estg/__39f.html',
    runtime_network=False, official_system_approval=False)
FACTOR_PERIOD_PAP_SHA256 = hashlib.sha256(canonical(FACTOR_PERIOD_PAP_RULES).encode()).hexdigest()
FACTOR_PERIOD_RULES = dict(version=FACTOR_PERIOD_RULE_VERSION, year=2026,
    supported_case='ONE_DOMESTIC_EMPLOYMENT_EPISODE_ONE_AGREEMENT_ONE_VERIFIED_FACTOR_PROFILE',
    scope=FACTOR_PERIOD_SCOPE, source_schema_version=2,
    ordinary_period_rule_version=PERIOD_RULE_VERSION,
    factor_period_pap=FACTOR_PERIOD_PAP_RULES,
    factor_period_pap_sha256=FACTOR_PERIOD_PAP_SHA256,
    transition_supported=False, oneoff_supported=False,
    additional_allowances_supported=False, multiple_profiles_supported=False)
FACTOR_PERIOD_RULES_SHA256 = hashlib.sha256(canonical(FACTOR_PERIOD_RULES).encode()).hexdigest()


def calculate_factor_period_tax(*, gross_minor, lzz, tax_days, factor, **parameters):
    inputs = period_tax_inputs(gross_minor, lzz=lzz, tax_days=tax_days,
        allowance_monthly_minor=0, addition_monthly_minor=0)
    args = dict(gross_minor=inputs['pap_gross_minor'], factor=factor,
        allowance_minor=0, addition_minor=0, **parameters)
    if lzz == 2:
        component = calculate_standard_factor_tax(period=2, **args)
        totals = dict(component)
    else:
        integer(inputs['pap_gross_minor'],0,10**12//360)
        args['gross_minor'] *= 360
        annual = calculate_standard_factor_tax(period=1, **args)
        component = {key:value//360 for key,value in annual.items()}
        totals = {key:value*tax_days for key,value in component.items()}
    return dict(inputs=inputs,component=component,totals=totals,factor=factor,
        version=FACTOR_PERIOD_PAP_VERSION,provenance_sha256=FACTOR_PERIOD_PAP_SHA256)


def selected_profile(snapshot, plan):
    return next(value for value in snapshot['profiles'] if
        {key:value[key] for key in ('id','revision','content_hash')}==plan['selected_profile_ref'])


def build_factor_period_plan(snapshot):
    plan = build_period_plan(snapshot)
    profile = selected_profile(snapshot,plan)['profile']
    # The ordinary planner checks every frozen reference, actual dates,
    # entitlement and non-factor blocker before the additive rule is selected.
    if 'tax_factor' not in profile:
        raise Problem(400,'Der Faktor-Periodenregelstand benötigt ein ausdrücklich belegtes Faktorprofil.')
    profile = normalize_factor_profile(profile)
    blockers = [entry for entry in plan['blockers'] if entry['code']!='special_case:tax_factor']
    first,_=month_range(plan['month'])
    if _age_completed(day(profile['date_of_birth']),64)<date(first.year,1,1):
        blockers.append(dict(code='age_allowance_not_supported',
            message='Ein vor Jahresbeginn vollendetes 64. Lebensjahr benötigt den gesonderten Altersentlastungsbetrag; der Faktor-Periodenfall berechnet ihn nicht.'))
    plan = {key:value for key,value in plan.items() if key not in ('plan_hash','can_confirm','can_calculate')}
    plan.update(rule_version=FACTOR_PERIOD_RULE_VERSION,rules_sha256=FACTOR_PERIOD_RULES_SHA256,
        factor_parameters=dict(tax_factor=profile['tax_factor'],profile_ref=plan['selected_profile_ref']),
        blockers=sorted(blockers,key=lambda entry:entry['code']))
    plan['plan_hash'] = hashlib.sha256(canonical(plan).encode()).hexdigest()
    return dict(plan,can_confirm=True,can_calculate=not blockers)


def calculate_factor_period_source(snapshot, *, rule_version=None):
    if rule_version not in (None,FACTOR_PERIOD_RULE_VERSION):
        raise Problem(400,'Unbekannter Faktor-Periodenregelstand.')
    plan=build_factor_period_plan(snapshot)
    profile=selected_profile(snapshot,plan)['profile'];gross=plan['gross_minor']
    parameters=dict(tax_class=4,children_half_units=profile['tax_children_half_units'],
        church_tax_percent='0' if profile['church_tax']=='none' else '8' if profile['federal_state'] in ('BW','BY') else '9',
        tax_factor=profile['tax_factor'])
    result=dict(rule_version=FACTOR_PERIOD_RULE_VERSION,rules_sha256=FACTOR_PERIOD_RULES_SHA256,
        month=plan['month'],currency='EUR',gross_minor=gross,scope='unsupported',
        payroll_calculation_complete=False,social_contributions_available=False,
        employee_contributions=None,employer_contributions=None,employee_social_total_minor=None,
        employer_social_total_minor=None,employer_levies=None,employer_flat_tax_minor=None,
        employer_total_excluding_accident_insurance_minor=None,accident_insurance_included=False,
        individual_wage_tax_minor=None,solidarity_minor=None,church_tax_minor=None,
        employee_tax_minor=None,net_minor=None,payout_minor=None,employee_additional_payment_minor=None,
        tax_parameters=parameters,blockers=plan['blockers'],statutory_report_status='not_transmitted',
        official_system_approval=False,travel_expenses_included_in_net=False,
        pap_version=FACTOR_PERIOD_PAP_VERSION,pap_provenance_sha256=FACTOR_PERIOD_PAP_SHA256,
        period_details={key:plan[key] for key in ('plan_hash','source_snapshot_hash',
            'employment_intervals','earnings','tax_periods','social_periods','factor_parameters')})
    if plan['blockers']:return result
    social=plan['social_periods'][0];caps=social['caps'];born=day(profile['date_of_birth'])
    surcharge=not profile['has_children'] and _age_completed(born,23).strftime('%Y-%m')<plan['month']
    discounts=max(0,min(5,profile['pv_children_under_25'])-1)
    keys=('health_general','health_additional','pension','unemployment','care')
    own=dict.fromkeys(keys,0);employer=dict.fromkeys(keys,0);bases={}
    for key,cap,rate in (('health_general',caps['health_minor'],Decimal('7.300')),
            ('health_additional',caps['health_minor'],Decimal(profile['health_additional_percent'])/2),
            ('pension',caps['pension_minor'],Decimal('9.300')),
            ('unemployment',caps['unemployment_minor'],Decimal('1.300'))):
        basis=min(gross,cap);bases[key]=dict(total_minor=basis,employee_minor=basis)
        own[key]=employer[key]=_portion(basis,rate)
    care_basis=min(gross,caps['care_minor']);bases['care']=dict(total_minor=care_basis,employee_minor=care_basis)
    own['care'],employer['care'],care=care_contributions(care_basis,care_basis,
        saxony=profile['federal_state']=='SN',surcharge=surcharge,discount_count=discounts,reduced=False)
    period=plan['tax_periods'][0]
    tax=calculate_factor_period_tax(gross_minor=gross,lzz=period['lzz'],tax_days=period['tax_days'],
        factor=profile['tax_factor'],tax_class=4,children_half_units=profile['tax_children_half_units'],
        additional_health_percent=format(Decimal(profile['health_additional_percent']),'.2f'),
        saxony=profile['federal_state']=='SN',childless_surcharge=surcharge,
        care_child_discounts=discounts,church_member=profile['church_tax']!='none')
    church=tax['totals']['BK']*int(parameters['church_tax_percent'])//100
    employee_tax=tax['totals']['LSTLZZ']+tax['totals']['SOLZLZZ']+church
    levy_base=min(gross,caps['pension_minor'])
    levies=dict(u1=_portion(levy_base,profile['u1_percent']),u2=_portion(levy_base,profile['u2_percent']),
        insolvency=_portion(levy_base,'0.150'))
    net=gross-sum(own.values())-employee_tax
    result.update(scope=FACTOR_PERIOD_SCOPE,payroll_calculation_complete=True,
        social_contributions_available=True,employee_contributions=own,employer_contributions=employer,
        employee_social_total_minor=sum(own.values()),employer_social_total_minor=sum(employer.values()),
        employer_levies=levies,employer_flat_tax_minor=0,employee_tax_minor=employee_tax,
        employer_total_excluding_accident_insurance_minor=gross+sum(employer.values())+sum(levies.values()),
        net_minor=net,payout_minor=max(0,net),employee_additional_payment_minor=max(0,-net),
        tax_method='individual_bmf_pap_2026_factor_period',individual_wage_tax_minor=tax['totals']['LSTLZZ'],
        solidarity_minor=tax['totals']['SOLZLZZ'],church_tax_minor=church,
        care_childless_surcharge=surcharge,care_discount_children=discounts)
    result['tax_parameters']['church_assessment_minor']=tax['totals']['BK']
    result['period_details'].update(tax_calculation=tax,branch_bases=bases,care_adjustments=care)
    return result

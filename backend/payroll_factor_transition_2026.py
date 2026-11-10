"""Additive full-month factor tax and explicitly evidenced Midijob assessment.

This pure component does not activate an API. The original factor profile stays
unchanged. Only a named derived contribution projection reaches the frozen v3
contribution kernel; the actual original factor reaches the frozen PAP wrapper.
"""
from copy import deepcopy
from decimal import Decimal
import hashlib
from pathlib import Path

from core import Problem, canonical
from payroll_de_2026 import month_range, day
from payroll_factor_2026 import normalize_factor_profile
from payroll_transition_2026 import normalize_assessment, calculate_transition, TRANSITION_RULE_VERSION
from payroll_factor_periods_2026 import (calculate_factor_period_tax,
    FACTOR_PERIOD_PAP_VERSION, FACTOR_PERIOD_PAP_SHA256)
import re

RULE_VERSION = 'de_2026_factor_transition_month_v14'
SOURCE_CONTRACT_VERSION = 6
SCOPE = 'regular_transition_factor_month'
FEATURE = 'payroll_factor_transition'
_ROOT = Path(__file__).resolve().parent
SOURCE_HASHES = {name:hashlib.sha256((_ROOT/name).read_bytes().replace(b'\r\n',b'\n')).hexdigest()
    for name in ('payroll_transition_2026.py','payroll_de_2026.py','payroll_factor_2026.py',
                 'payroll_factor_periods_2026.py','payroll_pap_2026.py','payroll_pap_factor_2026.py',
                 'payroll_pap_periods_2026.py','payroll_periods_2026.py')}
RULES = dict(version=RULE_VERSION, source_contract_version=SOURCE_CONTRACT_VERSION,
    scope=SCOPE, supported_case='ONE_FULL_2026_MONTH_ONE_MONTHLY_FACTOR_PROFILE_SEPARATELY_EVIDENCED_FORECAST',
    original_profile='UNCHANGED_EFFECTIVE_CLASS_IV_FACTOR_PROFILE',
    contribution_projection='REMOVE_ONLY_FACTOR_FROM_TAX_COMPONENT_ADD_EXPLICIT_SEPARATE_FORECAST',
    contribution_rule_version=TRANSITION_RULE_VERSION,
    factor_pap_version=FACTOR_PERIOD_PAP_VERSION, factor_pap_sha256=FACTOR_PERIOD_PAP_SHA256,
    actual_monthly_gross_equals_evidenced_regular_monthly_gross=True,
    gross_range_minor=[60301,200000], source_encoding='UTF8_CANONICAL_LF',
    sources=SOURCE_HASHES,
    module_sha256=hashlib.sha256(Path(__file__).read_bytes().replace(b'\r\n',b'\n')).hexdigest(),
    official_xml_sha256='63d8981646d139eba2f4dd990c13b43c4fb3883b402a5a40cddf253aa7aa96b4',
    sources_read_2026_11_10=['https://www.gesetze-im-internet.de/estg/__39f.html',
        'https://www.gesetze-im-internet.de/sgb_4/__20.html',
        'https://www.deutsche-rentenversicherung.de/DRV/DE/Experten/Arbeitgeber-und-Steuerberater/summa-summarum/Lexikon/U/uebergangsbereich.html'],
    runtime_network=False, official_system_approval=False)
RULES_SHA256 = hashlib.sha256(canonical(RULES).encode()).hexdigest()
AMOUNTS = ('employee_contributions','employer_contributions','employee_social_total_minor',
    'employer_social_total_minor','employer_levies','employer_flat_tax_minor',
    'employer_total_excluding_accident_insurance_minor','individual_wage_tax_minor',
    'solidarity_minor','church_tax_minor','employee_tax_minor','net_minor','payout_minor',
    'employee_additional_payment_minor')


def _sha(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def calculate_factor_transition(profile, assessment, month, gross_minor, *,
        full_month_confirmed, source_issues=(), rule_version=RULE_VERSION):
    if rule_version != RULE_VERSION:
        raise Problem(400,'Faktor-Midijob ausdrücklich unter dem eigenen neuen Regelstand berechnen.')
    actual = normalize_factor_profile(profile)
    # These are explicitly derived computational parameters, never replacement
    # profile originals. All unrelated special-case flags remain in force.
    projection = {key:deepcopy(value) for key,value in actual.items() if key!='tax_factor'}
    projection['special_cases'] = [code for code in actual['special_cases'] if code!='tax_factor']
    forecast = normalize_assessment(assessment, projection)
    projection['transition_assessment'] = forecast
    base = calculate_transition(projection, month, gross_minor,
        full_month_confirmed=full_month_confirmed, source_issues=source_issues)
    blockers = deepcopy(base['blockers'])
    def block(code,message):
        if not any(item['code']==code for item in blockers):
            blockers.append(dict(code=code,message=message))
    first,_ = month_range(month)
    if day(forecast['assessed_on'])>first:
        block('factor_transition_forecast_not_effective',
              'Dieser vollständige Monatsfall benötigt die belegte Prognose spätestens zum Monatsbeginn.')
    if gross_minor!=forecast['regular_monthly_gross_minor'] or not 60301<=gross_minor<=200000:
        block('factor_transition_monthly_original_mismatch',
              'Dieser erste Monatsvertrag benötigt den belegten unveränderten Monatslohn von603,01 bis2000Euro.')
    result = deepcopy(base)
    result.update(rule_version=RULE_VERSION,rules_sha256=RULES_SHA256,
        source_contract_version=SOURCE_CONTRACT_VERSION,
        pap_version=FACTOR_PERIOD_PAP_VERSION,pap_provenance_sha256=FACTOR_PERIOD_PAP_SHA256,
        scope='unsupported',payroll_calculation_complete=False,social_contributions_available=False,
        blockers=sorted(blockers,key=lambda row:row['code']),
        travel_expenses_included_in_net=False,net_deductions_minor=None,
        factor_transition_components=dict(actual_profile_sha256=_sha(profile),assessment=deepcopy(forecast),
            contribution_profile=deepcopy(projection),contribution_profile_sha256=_sha(projection),
            contribution_rule_version=TRANSITION_RULE_VERSION,
            contribution_source_sha256=SOURCE_HASHES['payroll_transition_2026.py'],
            contribution_financials=None,factor_tax=None))
    result['tax_parameters']['tax_factor'] = actual['tax_factor']
    result['tax_parameters']['church_assessment_minor'] = None
    if blockers:
        for key in AMOUNTS:
            result[key]=None
        result['transition']=None
        return result
    tax = calculate_factor_period_tax(gross_minor=gross_minor,lzz=2,tax_days=30,
        tax_class=4,factor=actual['tax_factor'],children_half_units=actual['tax_children_half_units'],
        additional_health_percent=format(Decimal(actual['health_additional_percent']),'.2f'),
        saxony=actual['federal_state']=='SN',childless_surcharge=base['care_childless_surcharge'],
        care_child_discounts=base['care_discount_children'],church_member=actual['church_tax']!='none')
    values = tax['totals']
    church = values['BK']*int(base['tax_parameters']['church_tax_percent'])//100
    employee_tax = values['LSTLZZ']+values['SOLZLZZ']+church
    net = gross_minor-base['employee_social_total_minor']-employee_tax
    result.update(scope=SCOPE,payroll_calculation_complete=True,social_contributions_available=True,
        tax_method='individual_2026_verified_factor_transition_month',
        individual_wage_tax_minor=values['LSTLZZ'],solidarity_minor=values['SOLZLZZ'],
        church_tax_minor=church,employee_tax_minor=employee_tax,net_minor=net,
        payout_minor=max(0,net),employee_additional_payment_minor=max(0,-net),net_deductions_minor=0)
    result['tax_parameters']['church_assessment_minor']=values['BK']
    result['factor_transition_components'].update(factor_tax=tax,
        contribution_financials={key:deepcopy(base[key]) for key in (
            'employee_contributions','employer_contributions','employee_social_total_minor',
            'employer_social_total_minor','employer_levies','employer_flat_tax_minor',
            'employer_total_excluding_accident_insurance_minor','transition')})
    return result


def normalize_case_assessment(value):
    fields={'schema_version','employee_id','valid_from','valid_to','declaration_date',
        'transition_assessment','forecast_evidence_ref','sole_employment_confirmed',
        'full_fixed_monthly_pay_confirmed','verification_note'}
    if not isinstance(value,dict) or set(value)!=fields:
        raise Problem(400,'Vollständige personengebundene Faktor-Midijob-Prognose mit Original angeben.')
    if (type(value['schema_version']) is not int or value['schema_version']!=1
            or not isinstance(value['employee_id'],str) or not re.fullmatch(r'[a-f0-9]{32}',value['employee_id'])):
        raise Problem(400,'Bekannte Prognosefassung und tatsächlichen Mitarbeiter angeben.')
    for key in ('valid_from','valid_to','declaration_date'):
        day(value[key])
    if value['valid_from']>value['valid_to']:
        raise Problem(400,'Gültigkeitszeitraum der Prognose ist umgekehrt.')
    for key in ('sole_employment_confirmed','full_fixed_monthly_pay_confirmed'):
        if type(value[key]) is not bool:
            raise Problem(400,'Beschäftigungs- und Monatslohnprüfung ausdrücklich mit Ja oder Nein angeben.')
    ref=value['forecast_evidence_ref']
    if (not isinstance(ref,dict) or set(ref)!={'id','revision','content_hash'}
            or not isinstance(ref['id'],str) or not re.fullmatch(r'[a-f0-9]{32}',ref['id'])
            or type(ref['revision']) is not int or ref['revision']!=1
            or not isinstance(ref['content_hash'],str) or not re.fullmatch(r'[a-f0-9]{64}',ref['content_hash'])):
        raise Problem(400,'Die ursprüngliche personengebundene Prognosedatei unverändert binden.')
    forecast=value['transition_assessment']
    from payroll_de_2026 import integer
    if not isinstance(forecast,dict):
        raise Problem(400,'Die tatsächliche Zwölfmonatsprognose strukturiert angeben.')
    amount=integer(forecast.get('regular_monthly_gross_minor'),60301,200000)
    # Shape validation only. The actual original profile is independently
    # checked against this forecast in build_plan / calculate_factor_transition.
    normalized=normalize_assessment(forecast,
        dict(employment_kind='regular',regular_annual_gross_minor=amount*12))
    note=value['verification_note']
    if not isinstance(note,str) or not note.strip() or len(note)>3000:
        raise Problem(400,'Ergebnis der tatsächlichen Faktor-/Midijobprüfung dokumentieren.')
    try:note.encode('utf-8')
    except UnicodeEncodeError:
        raise Problem(400,'Prüftext muss gültige Unicode-Zeichen enthalten.') from None
    if any(ord(char)<32 and char not in '\n\t'for char in note):
        raise Problem(400,'Prüftext enthält unzulässige Steuerzeichen.')
    return deepcopy(value)|dict(transition_assessment=normalized,verification_note=note.strip())


def build_plan(snapshot, *, rule_version=RULE_VERSION, source_contract_version=SOURCE_CONTRACT_VERSION):
    fields={'schema_version','source_contract_version','rule_version','employee_id','month','period_case',
        'employment_terms','profiles','identities','segment_events','thirty_day_rule','entitlements',
        'travel_sources','flat_travel_tax','source_files','factor_transition_assessment'}
    if (not isinstance(snapshot,dict) or set(snapshot)!=fields or type(snapshot['schema_version']) is not int
            or snapshot['schema_version']!=1 or rule_version!=RULE_VERSION or snapshot['rule_version']!=RULE_VERSION
            or type(source_contract_version) is not int or source_contract_version!=SOURCE_CONTRACT_VERSION
            or type(snapshot['source_contract_version']) is not int or snapshot['source_contract_version']!=SOURCE_CONTRACT_VERSION):
        raise Problem(400,'Faktor-Midijob mit seinem eigenen vollständigen Quellenvertrag6 verwenden.')
    from payroll_factor_periods_2026 import build_factor_period_plan, FACTOR_PERIOD_RULE_VERSION
    from payroll_calculations_2026 import build_calculation_plan, CALCULATION_RULE_VERSION
    from business_payroll_facts import reference
    base=snapshot['period_case'];original=base['sources']
    if (base['kind']!='period_case' or base['status']!='active' or base['employee_id']!=snapshot['employee_id']
            or base['plan']['rule_version']!=FACTOR_PERIOD_RULE_VERSION or base['details']['month']!=snapshot['month']):
        raise Problem(400,'Ursprünglichen eigenen Faktorperiodenfall desselben Monats binden.')
    if build_factor_period_plan(original)!=base['plan']:
        raise Problem(409,'Die ursprüngliche Faktorperiodenberechnung ist verändert.')
    if (snapshot['profiles']!=original['profiles'] or snapshot['identities']!=original['identities']
            or snapshot['employment_terms']!=[original['employment_terms']]
            or len(snapshot['profiles'])!=1 or len(snapshot['identities'])!=1):
        raise Problem(400,'Dieser Monatsfall benötigt genau die ursprüngliche Beschäftigung, das Profil und die Identität.')
    actual=snapshot['profiles'][0]
    if normalize_factor_profile(actual['profile'])!=actual['profile']:
        raise Problem(400,'Ursprüngliches normalisiertes Faktorprofil erforderlich.')
    review=normalize_case_assessment(snapshot['factor_transition_assessment'])
    if review!=snapshot['factor_transition_assessment']:
        raise Problem(400,'Normalisierte unveränderte Prognoseentscheidung erforderlich.')
    structural={key:deepcopy(value)for key,value in snapshot.items()if key!='factor_transition_assessment'}
    structural.update(rule_version=CALCULATION_RULE_VERSION,source_contract_version=1)
    ordinary=build_calculation_plan(structural,rule_version=CALCULATION_RULE_VERSION,source_contract_version=1)
    plan={key:value for key,value in ordinary.items()if key not in ('plan_hash','can_confirm','can_calculate')}
    # Only these two old limitations are satisfied by this explicit new pair
    # of original-bound components. Every other old rejection remains binding.
    blockers=[deepcopy(row)for row in plan['blockers']if row['code'] not in (
        'special_case:tax_factor','transition_assessment_missing')]
    def block(code,message):
        if not any(item['code']==code for item in blockers):blockers.append(dict(code=code,message=message))
    first,last=month_range(snapshot['month'])
    if (len(plan['employment_intervals'])!=1 or len(plan['tax_periods'])!=1 or len(plan['social_periods'])!=1
            or any(p['start']!=first.isoformat() or p['end']!=last.isoformat() for p in plan['employment_intervals'])
            or any(p['lzz']!=2 or p['tax_days']!=30 for p in plan['tax_periods'])
            or any(p['days']!=30 or p['full_month'] is not True for p in plan['social_periods'])):
        block('factor_transition_full_month_required','Der erste Faktor-Midijob-Vertrag benötigt einen vollständigen Steuer-/SV-Monat.')
    agreements=original['preparation']['snapshot']['agreements']
    if (len(agreements)!=1 or agreements[0]['pay_basis']!='monthly' or snapshot['segment_events']
            or snapshot['entitlements'] or snapshot['travel_sources'] or snapshot['flat_travel_tax'] is not None
            or snapshot['thirty_day_rule'] is not None or original['preparation']['snapshot']['approved_absences']):
        block('factor_transition_other_case','Weitere Entgeltarten, Ansprüche, Reisen und Wechsel benötigen ihren eigenen Regelzweig.')
    if (review['employee_id']!=snapshot['employee_id'] or review['valid_from']>first.isoformat()
            or review['valid_to']<last.isoformat() or not review['sole_employment_confirmed']
            or not review['full_fixed_monthly_pay_confirmed']):
        block('factor_transition_review_not_complete','Die tatsächliche Alleinbeschäftigung und feste Monatsprognose vollständig belegen.')
    identity=snapshot['identities'][0]['details']
    if (identity.get('tax_source')!='elstam_imported'
            or type(identity.get('tax_allowance_yearly_minor'))is not int or identity['tax_allowance_yearly_minor']!=0
            or type(identity.get('tax_addition_yearly_minor'))is not int or identity['tax_addition_yearly_minor']!=0):
        block('factor_transition_elstam_required','Tatsächlichen vollständigen ELStAM-Originalnachweis ohne zusätzliche Frei-/Hinzurechnungen binden.')
    files={row['id']:row for row in snapshot['source_files']};ref=review['forecast_evidence_ref'];file=files.get(ref['id'])
    if (file is None or file.get('employee_id')!=snapshot['employee_id'] or file.get('purpose')!='personnel'
            or file.get('content_hash')!=ref['content_hash']):
        raise Problem(409,'Das eigene tatsächliche Prognoseoriginal fehlt oder wurde verändert.')
    component=None
    if not blockers:
        component=calculate_factor_transition(actual['profile'],review['transition_assessment'],
            snapshot['month'],plan['gross_minor'],full_month_confirmed=True)
        for row in component['blockers']:block(row['code'],row['message'])
    plan.update(rule_version=RULE_VERSION,source_contract_version=SOURCE_CONTRACT_VERSION,rules_sha256=RULES_SHA256,
        source_snapshot_hash=_sha(snapshot),factor_parameters=dict(tax_factor=actual['profile']['tax_factor'],profile_ref=reference(actual)),
        factor_transition_assessment=review,factor_transition_component=component,
        blockers=sorted(blockers,key=lambda row:row['code']))
    plan['plan_hash']=_sha(plan)
    return dict(plan,can_confirm=True,can_calculate=not blockers)


def calculate_source(snapshot, *, rule_version=RULE_VERSION, source_contract_version=SOURCE_CONTRACT_VERSION):
    plan=build_plan(snapshot,rule_version=rule_version,source_contract_version=source_contract_version)
    actual=snapshot['profiles'][0]['profile']
    if plan['blockers']:
        result=dict(rule_version=RULE_VERSION,rules_sha256=RULES_SHA256,source_contract_version=SOURCE_CONTRACT_VERSION,month=snapshot['month'],currency='EUR',
            gross_minor=plan['gross_minor'],scope='unsupported',payroll_calculation_complete=False,
            social_contributions_available=False,blockers=plan['blockers'],statutory_report_status='not_transmitted',
            official_system_approval=False,accident_insurance_included=False,travel_expenses_included_in_net=False,
            pap_version=FACTOR_PERIOD_PAP_VERSION,pap_provenance_sha256=FACTOR_PERIOD_PAP_SHA256,
            tax_parameters=dict(tax_class=4,tax_factor=actual['tax_factor'],children_half_units=actual['tax_children_half_units'],
                church_tax_percent='0'if actual['church_tax']=='none'else'8'if actual['federal_state']in('BW','BY')else'9'),
            net_deductions_minor=None,factor_transition_components=None,transition=None)
        result.update(dict.fromkeys(AMOUNTS))
    else:
        result=deepcopy(plan['factor_transition_component'])
    result['period_details']={key:plan[key]for key in ('plan_hash','source_snapshot_hash','employment_intervals',
        'identity_intervals','earnings','tax_periods','social_periods','entitlement_sources','unpaid_dates',
        'social_continuation','travel','flat_travel_tax','travel_source_hashes','factor_parameters')}
    result['period_details'].update(social_assessments=[],tax_calculations=[],
        factor_transition_assessment=plan['factor_transition_assessment'])
    if not plan['blockers']:
        result['period_details']['social_assessments']=[dict(period=plan['social_periods'][0],
            branch_bases=result['transition']['branch_bases'],transition=result['transition'],
            employee_contributions=result['employee_contributions'],employer_contributions=result['employer_contributions'],
            employer_levies=result['employer_levies'],levy_assessment_minor=result['transition']['levy_assessment_minor'])]
        tax=result['factor_transition_components']['factor_tax'];rate=int(result['tax_parameters']['church_tax_percent'])
        result['period_details']['tax_calculations']=[dict(period=plan['tax_periods'][0],calculation=tax,
            church_tax_percent=rate,church_tax_minor=result['church_tax_minor'])]
    return result

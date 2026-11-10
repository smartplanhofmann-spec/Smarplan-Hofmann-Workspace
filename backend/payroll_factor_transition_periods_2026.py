"""Explicit ordinary factor/Midijob period with an original 30-day contract.

The original v9 period and profile are never rewritten. This additive version
binds a separate evidenced forecast, the actual employment interval and exact
partial bases. It creates no payment, filing or provider side effect.
"""
from copy import deepcopy
from decimal import Decimal
import hashlib
from pathlib import Path
import re

from core import Problem, canonical
from payroll_de_2026 import _age_completed, _portion, day, integer, month_range
from payroll_factor_2026 import normalize_factor_profile
from payroll_factor_periods_2026 import (
    FACTOR_PERIOD_RULE_VERSION, FACTOR_PERIOD_PAP_VERSION, FACTOR_PERIOD_PAP_SHA256,
    build_factor_period_plan, calculate_factor_period_source, calculate_factor_period_tax,
)
from payroll_periods_2026 import _transition_bases
from payroll_transition_2026 import care_contributions, normalize_assessment


RULE_VERSION = 'de_2026_factor_transition_period_v16'
SOURCE_CONTRACT_VERSION = 7
SCOPE = 'regular_transition_factor_period'
FEATURE = 'payroll_factor_transition_periods'
_ROOT = Path(__file__).resolve().parent
SOURCE_HASHES = {name: hashlib.sha256((_ROOT / name).read_bytes().replace(b'\r\n', b'\n')).hexdigest()
    for name in ('payroll_de_2026.py', 'payroll_factor_2026.py', 'payroll_periods_2026.py',
                 'payroll_transition_2026.py', 'payroll_factor_periods_2026.py',
                 'payroll_pap_2026.py', 'payroll_pap_factor_2026.py', 'payroll_pap_periods_2026.py',
                 'payroll_calculations_2026.py', 'payroll_segments_2026.py', 'payroll_claims_composition_2026.py')}
RULES = dict(version=RULE_VERSION, source_contract_version=SOURCE_CONTRACT_VERSION,
    scope=SCOPE, year=2026,
    supported_case='ONE_ACTUAL_ENTRY_OR_EXIT_ONE_FIXED_MONTHLY_30_DAY_CONTRACT_ONE_FACTOR_PROFILE',
    forecast='SEPARATE_ORIGINAL_TWELVE_MONTH_SOLE_EMPLOYMENT_60301_TO_200000_MINOR',
    original_period_rule=FACTOR_PERIOD_RULE_VERSION,
    tax_period='ACTUAL_CALENDAR_DAYS_DAILY_FACTOR_PAP',
    social_period='ACTUAL_SOCIAL_DAYS_CONTRACTUAL_30_DAY_RATIO_FINAL_BASE_ROUNDING_ONCE',
    factor_pap_version=FACTOR_PERIOD_PAP_VERSION, factor_pap_sha256=FACTOR_PERIOD_PAP_SHA256,
    sources=SOURCE_HASHES, source_encoding='UTF8_CANONICAL_LF',
    module_sha256=hashlib.sha256(Path(__file__).read_bytes().replace(b'\r\n', b'\n')).hexdigest(),
    official_xml_sha256='63d8981646d139eba2f4dd990c13b43c4fb3883b402a5a40cddf253aa7aa96b4',
    runtime_network=False, official_system_approval=False)
RULES_SHA256 = hashlib.sha256(canonical(RULES).encode()).hexdigest()
REVIEW_FIELDS = frozenset(('schema_version', 'employee_id', 'valid_from', 'valid_to',
    'declaration_date', 'transition_assessment', 'forecast_evidence_ref',
    'sole_employment_confirmed', 'fixed_monthly_contract_confirmed',
    'contractual_30_days_confirmed', 'verification_note'))
SNAPSHOT_FIELDS = frozenset(('schema_version', 'source_contract_version', 'rule_version',
    'employee_id', 'month', 'period_case', 'employment_terms', 'profiles', 'identities',
    'segment_events', 'thirty_day_rule', 'entitlements', 'travel_sources', 'flat_travel_tax',
    'source_files', 'factor_transition_period_assessment'))
FINANCIAL_FIELDS = ('employee_contributions', 'employer_contributions',
    'employee_social_total_minor', 'employer_social_total_minor', 'employer_levies',
    'employer_flat_tax_minor', 'employer_total_excluding_accident_insurance_minor',
    'individual_wage_tax_minor', 'solidarity_minor', 'church_tax_minor', 'employee_tax_minor',
    'net_minor', 'payout_minor', 'employee_additional_payment_minor', 'net_deductions_minor')


def _sha(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def normalize_case_assessment(value):
    if not isinstance(value, dict) or set(value) != REVIEW_FIELDS:
        raise Problem(400, 'Vollständige eigene Faktor-/Midijob-Teilmonatsprüfung mit Prognoseoriginal angeben.')
    if (type(value['schema_version']) is not int or value['schema_version'] != 1
            or not isinstance(value['employee_id'], str)
            or not re.fullmatch(r'[a-f0-9]{32}', value['employee_id'])):
        raise Problem(400, 'Bekannte Teilmonatsprüfung und tatsächliche Person angeben.')
    for key in ('valid_from', 'valid_to', 'declaration_date'):
        day(value[key])
    if value['valid_from'] > value['valid_to']:
        raise Problem(400, 'Gültigkeit der belegten Teilmonatsprüfung ist umgekehrt.')
    for key in ('sole_employment_confirmed', 'fixed_monthly_contract_confirmed', 'contractual_30_days_confirmed'):
        if type(value[key]) is not bool:
            raise Problem(400, 'Beschäftigung, Monatsvertrag und 30-Tage-Methode ausdrücklich prüfen.')
    ref = value['forecast_evidence_ref']
    if (not isinstance(ref, dict) or set(ref) != {'id', 'revision', 'content_hash'}
            or not isinstance(ref['id'], str) or not re.fullmatch(r'[a-f0-9]{32}', ref['id'])
            or type(ref['revision']) is not int or ref['revision'] != 1
            or not isinstance(ref['content_hash'], str) or not re.fullmatch(r'[a-f0-9]{64}', ref['content_hash'])):
        raise Problem(400, 'Unverändertes ursprüngliches Prognosedokument dieser Person binden.')
    forecast = value['transition_assessment']
    if not isinstance(forecast, dict):
        raise Problem(400, 'Vollständige tatsächliche Zwölfmonatsprognose angeben.')
    amount = integer(forecast.get('regular_monthly_gross_minor'), 60301, 200000)
    normalized = normalize_assessment(forecast,
        dict(employment_kind='regular', regular_annual_gross_minor=amount * 12))
    note = value['verification_note']
    if not isinstance(note, str) or not note.strip() or len(note) > 3000:
        raise Problem(400, 'Die tatsächliche Prüfung des Faktor-/Midijob-Teilmonats dokumentieren.')
    try:
        note.encode('utf-8')
    except UnicodeEncodeError:
        raise Problem(400, 'Prüftext benötigt gültige Unicode-Zeichen.') from None
    if any(ord(c) < 32 and c not in '\n\t' for c in note):
        raise Problem(400, 'Prüftext enthält unzulässige Steuerzeichen.')
    return deepcopy(value) | dict(transition_assessment=normalized, verification_note=note.strip())


def build_plan(snapshot, *, rule_version=RULE_VERSION, source_contract_version=SOURCE_CONTRACT_VERSION):
    if (not isinstance(snapshot, dict) or set(snapshot) != SNAPSHOT_FIELDS
            or type(snapshot['schema_version']) is not int or snapshot['schema_version'] != 1
            or rule_version != RULE_VERSION or snapshot['rule_version'] != RULE_VERSION
            or type(source_contract_version) is not int or source_contract_version != SOURCE_CONTRACT_VERSION
            or type(snapshot['source_contract_version']) is not int
            or snapshot['source_contract_version'] != SOURCE_CONTRACT_VERSION
            or snapshot['thirty_day_rule'] != 'actual_days_capped_per_claim'):
        raise Problem(400, 'Faktor-/Midijob-Teilmonat ausdrücklich unter Quellenvertrag 7 verwenden.')
    from business_payroll_facts import reference
    base = snapshot['period_case']
    if (base['kind'] != 'period_case' or base['status'] != 'active'
            or base['employee_id'] != snapshot['employee_id']
            or base['details']['month'] != snapshot['month']
            or base['plan']['rule_version'] != FACTOR_PERIOD_RULE_VERSION):
        raise Problem(400, 'Ursprünglichen eigenen V9-Faktorperiodenfall desselben Monats binden.')
    original = base['sources']
    if build_factor_period_plan(original) != base['plan']:
        raise Problem(409, 'Die ursprüngliche Faktorperiodenquelle wurde verändert.')
    if (snapshot['profiles'] != original['profiles'] or snapshot['identities'] != original['identities']
            or snapshot['employment_terms'] != [original['employment_terms']]
            or len(snapshot['profiles']) != 1 or len(snapshot['identities']) != 1):
        raise Problem(400, 'Genau die vollständige ursprüngliche Beschäftigung, Identität und Faktorprofilfassung binden.')
    profile_record = snapshot['profiles'][0]
    profile = normalize_factor_profile(profile_record['profile'])
    if profile != profile_record['profile']:
        raise Problem(400, 'Normalisiertes unverändertes ursprüngliches Faktorprofil verwenden.')
    review = normalize_case_assessment(snapshot['factor_transition_period_assessment'])
    if review != snapshot['factor_transition_period_assessment'] or review['employee_id'] != snapshot['employee_id']:
        raise Problem(400, 'Die normalisierte Teilmonatsprüfung gehört nicht zur ursprünglichen Person.')
    normalize_assessment(review['transition_assessment'], dict(employment_kind=profile['employment_kind'],
        regular_annual_gross_minor=profile['regular_annual_gross_minor']))
    from payroll_calculations_2026 import build_calculation_plan, CALCULATION_RULE_VERSION
    structural = {k: deepcopy(v) for k, v in snapshot.items() if k != 'factor_transition_period_assessment'}
    structural.update(rule_version=CALCULATION_RULE_VERSION, source_contract_version=1)
    ordinary = build_calculation_plan(structural, rule_version=CALCULATION_RULE_VERSION, source_contract_version=1)
    plan = {k: deepcopy(v) for k, v in ordinary.items()
            if k not in ('plan_hash', 'can_confirm', 'can_calculate')}
    blockers = []
    for row in base['plan']['blockers'] + plan['blockers']:
        if row['code'] not in ('transition_assessment_missing', 'special_case:tax_factor') and not any(r['code'] == row['code'] for r in blockers):
            blockers.append(deepcopy(row))
    if plan['gross_minor'] != base['plan']['gross_minor']:
        raise Problem(409, 'Der einfache Gesamtfall widerspricht dem unveränderten ursprünglichen Teilentgelt.')
    for key in ('employment_intervals', 'tax_periods', 'social_periods'):
        if len(plan[key]) != len(base['plan'][key]) or any(
                any(a[field] != b[field] for field in ('start', 'end'))
                for a, b in zip(plan[key], base['plan'][key])):
            raise Problem(409, 'Die tatsächliche ursprüngliche Beschäftigungs-, Steuer- oder SV-Zeitachse wurde verändert.')
    for actual, original_period in zip(plan['social_periods'], base['plan']['social_periods']):
        if actual['days'] != original_period['days'] or actual['caps'] != original_period['caps']:
            raise Problem(409, 'Die tatsächlichen SV-Tage oder Teilbemessungsgrenzen widersprechen dem Periodenoriginal.')
        actual['transition_ratio'] = deepcopy(original_period['transition_ratio'])
    for actual, original_period in zip(plan['tax_periods'], base['plan']['tax_periods']):
        if actual['tax_days'] != original_period['tax_days'] or actual['lzz'] != original_period['lzz']:
            raise Problem(409, 'Die tatsächlichen Steuertage oder der Lohnzahlungszeitraum widersprechen dem Periodenoriginal.')
        actual['inputs'] = deepcopy(original_period['inputs'])

    def block(code, message):
        if not any(r['code'] == code for r in blockers):
            blockers.append(dict(code=code, message=message))

    first, last = month_range(snapshot['month'])
    intervals = plan['employment_intervals']
    taxes = plan['tax_periods']
    social = plan['social_periods']
    if (first.year != 2026 or len(intervals) != 1 or len(taxes) != 1 or len(social) != 1
            or taxes[0]['lzz'] != 4 or social[0]['full_month'] is not False
            or not 1 <= social[0]['days'] <= 30
            or not 1 <= taxes[0]['tax_days'] <= 30):
        block('factor_transition_actual_partial_period_required',
              'Dieser eigene Vertrag benötigt genau den tatsächlichen Eintritts- oder Austrittsteilmonat.')
    agreement = original['preparation']['snapshot']['agreements']
    if (len(agreement) != 1 or agreement[0]['pay_basis'] != 'monthly'
            or original['employment_terms']['details']['proration_method'] != 'contractual_30_days'
            or snapshot['segment_events'] or snapshot['thirty_day_rule'] != 'actual_days_capped_per_claim'
            or snapshot['entitlements'] or snapshot['travel_sources']
            or snapshot['flat_travel_tax'] is not None
            or original['preparation']['snapshot']['approved_absences']):
        block('factor_transition_period_other_case',
              'Dieser Teilmonatsvertrag benötigt einen festen 30-Tage-Monatsvertrag ohne weitere Bezüge oder Wechsel.')
    if not all(review[k] for k in ('sole_employment_confirmed', 'fixed_monthly_contract_confirmed', 'contractual_30_days_confirmed')):
        block('factor_transition_period_review_not_complete',
              'Alleinbeschäftigung, festen Monatsvertrag und 30-Tage-Teilentgeltmethode vollständig prüfen.')
    if intervals:
        start, end = intervals[0]['start'], intervals[0]['end']
        if (review['valid_from'] > start or review['valid_to'] < end
                or review['transition_assessment']['assessed_on'] > start
                or review['declaration_date'] < review['transition_assessment']['assessed_on']):
            block('factor_transition_period_forecast_not_effective',
                  'Die belegte Prognose und ihre Prüfung müssen den tatsächlichen Beschäftigungszeitraum abdecken.')
    if len(agreement) == 1 and agreement[0]['amount_minor'] != review['transition_assessment']['regular_monthly_gross_minor']:
        block('factor_transition_period_fixed_wage_mismatch',
              'Der belegte feste Monatsvertrag stimmt nicht mit der gesonderten Prognose überein.')
    identity = snapshot['identities'][0]['details']
    if (identity.get('tax_source') != 'elstam_imported'
            or type(identity.get('tax_allowance_yearly_minor')) is not int or identity['tax_allowance_yearly_minor'] != 0
            or type(identity.get('tax_addition_yearly_minor')) is not int or identity['tax_addition_yearly_minor'] != 0):
        block('factor_transition_period_elstam_required',
              'Den vollständigen tatsächlichen ELStAM-Nachweis ohne zusätzliche Frei- oder Hinzurechnungen binden.')
    evidence = review['forecast_evidence_ref']
    files = {row['id']: row for row in snapshot['source_files']}
    file = files.get(evidence['id'])
    if (file is None or file.get('employee_id') != snapshot['employee_id']
            or file.get('purpose') != 'personnel' or file.get('content_hash') != evidence['content_hash']):
        raise Problem(409, 'Das private unveränderte Prognoseoriginal fehlt oder gehört nicht zu dieser Person.')
    plan.update(rule_version=RULE_VERSION, source_contract_version=SOURCE_CONTRACT_VERSION,
        rules_sha256=RULES_SHA256, source_snapshot_hash=_sha(snapshot),
        factor_parameters=dict(tax_factor=profile['tax_factor'], profile_ref=reference(profile_record)),
        factor_transition_period_assessment=review, blockers=sorted(blockers, key=lambda r: r['code']))
    plan['plan_hash'] = _sha(plan)
    plan['factor_transition_period_component'] = None
    if not blockers:
        component = _calculate_from_plan(snapshot, plan)
        plan['factor_transition_period_component'] = {k: v for k, v in component.items() if k != 'period_details'}
    plan['plan_hash'] = _sha({k: v for k, v in plan.items() if k != 'plan_hash'})
    return dict(plan, can_confirm=True, can_calculate=not blockers)


def _calculate_from_plan(snapshot, plan):
    original = snapshot['period_case']['sources']
    profile = snapshot['profiles'][0]['profile']
    result = deepcopy(calculate_factor_period_source(original))
    for key in FINANCIAL_FIELDS:
        result[key] = None
    result.pop('tax_method', None)
    result.update(rule_version=RULE_VERSION, source_contract_version=SOURCE_CONTRACT_VERSION,
        rules_sha256=RULES_SHA256, scope='unsupported', payroll_calculation_complete=False,
        social_contributions_available=False, blockers=plan['blockers'], transition=None,
        factor_transition_period_components=None,
        period_details={k: deepcopy(plan[k]) for k in ('plan_hash', 'source_snapshot_hash',
            'employment_intervals', 'identity_intervals', 'earnings', 'tax_periods', 'social_periods',
            'entitlement_sources', 'unpaid_dates', 'social_continuation', 'travel', 'flat_travel_tax',
            'travel_source_hashes', 'factor_parameters')})
    result['period_details'].update(social_assessments=[], tax_calculations=[],
        factor_transition_period_assessment=deepcopy(plan['factor_transition_period_assessment']))
    result['tax_parameters']['church_assessment_minor'] = None
    if plan['blockers']:
        return result
    social = plan['social_periods'][0]
    ratio = social['transition_ratio']
    if ratio != dict(numerator=social['days'], denominator=30):
        raise Problem(409, 'Die ursprüngliche 30-Tage-Vertragsquote widerspricht der tatsächlichen SV-Zeitachse.')
    gross = plan['gross_minor']
    basis = _transition_bases(gross, social['days'], 30)
    total, own = basis['total_assessment_minor'], basis['employee_assessment_minor']
    reduced = basis['regime'] != 'above_upper_limit'
    caps = social['caps']
    employee, employer, branch_bases = {}, {}, {}
    for key, cap, rate in (('health_general', caps['health_minor'], Decimal('7.300')),
            ('health_additional', caps['health_minor'], Decimal(profile['health_additional_percent']) / 2),
            ('pension', caps['pension_minor'], Decimal('9.300')),
            ('unemployment', caps['unemployment_minor'], Decimal('1.300'))):
        branch_total, branch_own = min(total, cap), min(own, cap)
        branch_bases[key] = dict(total_minor=branch_total, employee_minor=branch_own)
        employee[key] = _portion(branch_own, rate)
        employer[key] = (2 * _portion(branch_total, rate) - employee[key]
                         if reduced else _portion(branch_total, rate))
    born = day(profile['date_of_birth'])
    surcharge = not profile['has_children'] and _age_completed(born, 23).strftime('%Y-%m') < plan['month']
    discounts = max(0, min(5, profile['pv_children_under_25']) - 1)
    care_total, care_own = min(total, caps['care_minor']), min(own, caps['care_minor'])
    branch_bases['care'] = dict(total_minor=care_total, employee_minor=care_own)
    employee['care'], employer['care'], care = care_contributions(care_total, care_own,
        saxony=profile['federal_state'] == 'SN', surcharge=surcharge, discount_count=discounts, reduced=reduced)
    levy_base = min(total, caps['pension_minor'])
    levies = dict(u1=_portion(levy_base, profile['u1_percent']), u2=_portion(levy_base, profile['u2_percent']),
                  insolvency=_portion(levy_base, '0.150'))
    period = plan['tax_periods'][0]
    tax = calculate_factor_period_tax(gross_minor=gross, lzz=4, tax_days=period['tax_days'],
        tax_class=4, factor=profile['tax_factor'], children_half_units=profile['tax_children_half_units'],
        additional_health_percent=format(Decimal(profile['health_additional_percent']), '.2f'),
        saxony=profile['federal_state'] == 'SN', childless_surcharge=surcharge,
        care_child_discounts=discounts, church_member=profile['church_tax'] != 'none')
    church_rate = int(result['tax_parameters']['church_tax_percent'])
    church = tax['totals']['BK'] * church_rate // 100
    employee_tax = tax['totals']['LSTLZZ'] + tax['totals']['SOLZLZZ'] + church
    net = gross - sum(employee.values()) - employee_tax
    transition = dict(basis, factor='0.6619', branch_bases=branch_bases, levy_assessment_minor=levy_base,
        regular_monthly_gross_minor=plan['factor_transition_period_assessment']['transition_assessment']['regular_monthly_gross_minor'],
        care_adjustments=care,
        ratio=dict(numerator=social['days'], denominator=30), forecast=deepcopy(plan['factor_transition_period_assessment']['transition_assessment']))
    result.update(scope=SCOPE, payroll_calculation_complete=True, social_contributions_available=True,
        employee_contributions=employee, employer_contributions=employer,
        employee_social_total_minor=sum(employee.values()), employer_social_total_minor=sum(employer.values()),
        employer_levies=levies, employer_flat_tax_minor=0,
        employer_total_excluding_accident_insurance_minor=gross + sum(employer.values()) + sum(levies.values()),
        individual_wage_tax_minor=tax['totals']['LSTLZZ'], solidarity_minor=tax['totals']['SOLZLZZ'],
        church_tax_minor=church, employee_tax_minor=employee_tax, net_minor=net, payout_minor=max(0, net),
        employee_additional_payment_minor=max(0, -net), net_deductions_minor=0,
        tax_method='individual_2026_verified_factor_transition_period',
        care_childless_surcharge=surcharge, care_discount_children=discounts, transition=transition,
        factor_transition_period_components=dict(original_profile_sha256=_sha(profile),
            original_period_plan_hash=snapshot['period_case']['plan']['plan_hash'],
            assessment=deepcopy(plan['factor_transition_period_assessment']), factor_tax=tax,
            branch_bases=branch_bases, care_adjustments=care))
    result['tax_parameters']['church_assessment_minor'] = tax['totals']['BK']
    result['period_details']['social_assessments'] = [dict(period=deepcopy(social), branch_bases=branch_bases,
        transition=transition, employee_contributions=employee, employer_contributions=employer,
        employer_levies=levies, levy_assessment_minor=levy_base)]
    result['period_details']['tax_calculations'] = [dict(period=deepcopy(period), calculation=tax,
        church_tax_percent=church_rate, church_tax_minor=church)]
    return result


def calculate_source(snapshot, *, rule_version=RULE_VERSION, source_contract_version=SOURCE_CONTRACT_VERSION):
    plan = build_plan(snapshot, rule_version=rule_version, source_contract_version=source_contract_version)
    return _calculate_from_plan(snapshot, plan)

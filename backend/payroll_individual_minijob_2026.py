"""Explicit v11 full-month individual minijob, retaining every older rule."""
from copy import deepcopy
import hashlib
from pathlib import Path
import re

from core import Problem, canonical
from payroll_de_2026 import normalize_profile, month_range, day, _age_completed, _portion, RULES as CONTRIBUTION_RULES
from payroll_periods_2026 import build_period_plan, PERIOD_RULE_VERSION
from payroll_pap_periods_2026 import period_tax_inputs
from payroll_pap_minijob_2026 import calculate_individual_minijob_tax, parameters, PAP_VERSION, PAP_PROVENANCE, PAP_SHA256

RULE_VERSION = 'de_2026_individual_minijob_month_v11'
SOURCE_CONTRACT_VERSION = 3
SCOPE = 'commercial_minijob_individual_month'
FEATURE = 'payroll_individual_minijob'
ID = r'[a-f0-9]{32}'
REF_FIELDS = ('health_evidence_ref', 'pension_evidence_ref', 'employment_evidence_ref',
              'income_evidence_ref', 'elstam_evidence_ref')
BOOL_FIELDS = ('sole_employment_confirmed', 'income_review_complete',
               'no_other_relevant_income_confirmed', 'domestic_commercial_employment_confirmed',
               'no_foreign_insurance_confirmed', 'no_other_special_cases_confirmed')
ASSESSMENT_FIELDS = ('schema_version', 'employee_id', 'valid_from', 'valid_to', 'declaration_date',
                     'actual_health_insurance', 'pension_status', 'verification_note', *REF_FIELDS, *BOOL_FIELDS)
RULES = dict(version=RULE_VERSION, source_contract_version=SOURCE_CONTRACT_VERSION,
    scope=SCOPE, period='ONE_FULL_CALENDAR_MONTH_2026', gross_range_minor=[17500, 60300], tax_classes=[1, 5],
    actual_health_insurance='statutory_family', technical_pkv='BMF_2025_08_14_RZ16_PKV1_NOT_ACTUAL_PRIVATE_INSURANCE',
    pension='EXPLICIT_THIS_EMPLOYMENT_KRV0_OR_KRV1', pap=PAP_PROVENANCE,
    contributions=CONTRIBUTION_RULES, historical_dispatch='EXPLICIT_V11_CONTRACT3_ONLY',
    module_sha256=hashlib.sha256(Path(__file__).read_bytes().replace(b'\r\n', b'\n')).hexdigest(),
    official_system_approval=False)
RULES_SHA256 = hashlib.sha256(canonical(RULES).encode()).hexdigest()


def minijob_note(value):
    if not isinstance(value,str) or not value.strip() or len(value)>3000:
        raise Problem(400,'Prüfergebnis der Minijobmerkmale dokumentieren.')
    try:value.encode('utf-8')
    except UnicodeEncodeError:
        raise Problem(400,'Prüftext muss aus gültigen Unicode-Zeichen bestehen.') from None
    if any(ord(char)<32 and char not in '\n\t' for char in value):
        raise Problem(400,'Prüftext enthält unzulässige Steuerzeichen.')
    return value.strip()


def normalize_assessment(value):
    if not isinstance(value, dict) or set(value) != set(ASSESSMENT_FIELDS):
        raise Problem(400, 'Vollständige personengebundene Minijobprüfung mit Wirkungszeitraum und Originalen angeben.')
    result = deepcopy(value)
    if type(value['schema_version']) is not int or value['schema_version'] != 1 or not re.fullmatch(ID, str(value['employee_id'])):
        raise Problem(400, 'Unbekannte Minijobprüfungsfassung oder Person.')
    for key in ('valid_from', 'valid_to', 'declaration_date'):
        day(value[key])
    if value['valid_from'] > value['valid_to']:
        raise Problem(400, 'Wirkungszeitraum der Minijobprüfung ist umgekehrt.')
    if value['actual_health_insurance'] not in ('statutory_family', 'statutory_mandatory', 'statutory_voluntary', 'private', 'unknown'):
        raise Problem(400, 'Tatsächlichen Versicherungsstatus angeben; technische PAP-Parameter sind kein Versicherungsstatus.')
    if value['pension_status'] not in ('exempt', 'compulsory', 'unknown') or any(type(value[key]) is not bool for key in BOOL_FIELDS):
        raise Problem(400, 'RV-Status und tatsächliche Prüfungsaussagen ausdrücklich angeben.')
    for key in REF_FIELDS:
        ref = value[key]
        if (not isinstance(ref, dict) or set(ref) != {'id', 'revision', 'content_hash'}
                or not re.fullmatch(ID, str(ref['id'])) or type(ref['revision']) is not int or ref['revision'] != 1
                or not re.fullmatch(r'[a-f0-9]{64}', str(ref['content_hash']))):
            raise Problem(400, 'Jeden tatsächlichen Personalaktennachweis mit unveränderter Dateifassung binden.')
    result['verification_note'] = minijob_note(value['verification_note'])
    return result


def _sha(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def build_plan(snapshot, *, rule_version=RULE_VERSION, source_contract_version=SOURCE_CONTRACT_VERSION):
    fields = {'schema_version', 'source_contract_version', 'rule_version', 'employee_id', 'month', 'period_case',
              'employment_terms', 'profiles', 'identities', 'segment_events', 'thirty_day_rule', 'entitlements',
              'travel_sources', 'flat_travel_tax', 'source_files', 'individual_minijob_assessment'}
    if (not isinstance(snapshot, dict) or set(snapshot) != fields or type(snapshot['schema_version']) is not int
            or snapshot['schema_version'] != 1 or rule_version != RULE_VERSION or snapshot['rule_version'] != RULE_VERSION
            or type(source_contract_version) is not int or source_contract_version != SOURCE_CONTRACT_VERSION
            or snapshot['source_contract_version'] != SOURCE_CONTRACT_VERSION):
        raise Problem(400, 'Individueller Minijob benötigt ausdrücklich v11 mit Quellenvertrag 3.')
    first, last = month_range(snapshot['month'])
    base = snapshot['period_case']; original = base['sources']
    if (base['kind'] != 'period_case' or base['status'] != 'active' or base['employee_id'] != snapshot['employee_id']
            or base['plan']['rule_version'] != PERIOD_RULE_VERSION or base['details']['month'] != snapshot['month']):
        raise Problem(400, 'Ursprünglichen eigenen P2-Periodenfall desselben Monats binden.')
    old_plan = build_period_plan(original)
    if old_plan != base['plan']:
        raise Problem(409, 'Historischer Periodenplan widerspricht seinen Originalen.')
    if (snapshot['employment_terms'] != [original['employment_terms']] or snapshot['profiles'] != original['profiles']
            or snapshot['identities'] != original['identities']):
        raise Problem(409, 'Beschäftigung, Profil und Identität müssen vollständig zum ursprünglichen Periodenfall gehören.')
    if len(snapshot['profiles']) != 1 or len(snapshot['identities']) != 1:
        raise Problem(400, 'Dieser Minijobvertrag benötigt genau eine Profil- und Identitätsfassung.')
    profile_record = snapshot['profiles'][0]; p = profile_record['profile']; identity = snapshot['identities'][0]
    if normalize_profile(p) != p:
        raise Problem(400, 'Unverändertes normalisiertes Personalprofil erforderlich.')
    assessment = normalize_assessment(snapshot['individual_minijob_assessment'])
    blockers = []
    def block(code, message):
        if not any(row['code'] == code for row in blockers): blockers.append(dict(code=code, message=message))
    # Only this specific old rejection is resolved by the independent v11 rule.
    # Every unrelated old blocker remains visible and prevents calculation.
    for row in old_plan['blockers']:
        if row['code'] != 'minijob_individual_tax': blockers.append(deepcopy(row))
    gross = old_plan['gross_minor']
    if first.year != 2026: block('year_not_supported', 'Dieser Minijobvertrag ist ausschließlich für 2026 belegt.')
    if (len(old_plan['employment_intervals']) != 1 or old_plan['employment_intervals'][0]['start'] != first.isoformat()
            or old_plan['employment_intervals'][0]['end'] != last.isoformat()
            or len(old_plan['tax_periods']) != 1 or old_plan['tax_periods'][0]['lzz'] != 2
            or len(old_plan['social_periods']) != 1 or not old_plan['social_periods'][0]['full_month']):
        block('individual_minijob_full_month_required', 'Genau ein vollständig belegter Kalendermonat erforderlich.')
    if (snapshot['segment_events'] or snapshot['entitlements'] or snapshot['travel_sources']
            or snapshot['flat_travel_tax'] is not None or snapshot['thirty_day_rule'] is not None
            or original['preparation']['snapshot']['approved_absences']):
        block('individual_minijob_other_case', 'Reisen, Abwesenheiten, Zusatzansprüche und untermonatige Änderungen benötigen eine eigene Regel.')
    agreements = original['preparation']['snapshot']['agreements']
    if len(agreements) != 1 or agreements[0]['pay_basis'] != 'monthly':
        block('individual_minijob_monthly_contract_required', 'Dieser erste Minijobumfang benötigt einen unveränderten Monatslohnvertrag.')
    if type(gross) is not int or not 17500 <= gross <= 60300:
        block('individual_minijob_gross_outside_scope', 'Belegter Monatslohn muss im anfänglichen Bereich 175 bis 603 EUR liegen.')
    if (p['employment_kind'] != 'minijob' or p['minijob_tax'] != 'individual' or p['health_insurance'] != 'statutory_other'
            or p['tax_class'] not in (1, 5) or p['tax_children_half_units'] != 0 or p['church_tax'] != 'none'
            or p['pension_other_compulsory'] or p['special_cases']):
        block('individual_minijob_profile_outside_scope', 'Individueller gewerblicher Minijob mit tatsächlicher GKV, Klasse I/V und ohne Sondermerkmale erforderlich.')
    if _age_completed(day(p['date_of_birth']), 18) >= first or _age_completed(day(p['date_of_birth']), 65) < last:
        block('age_case_not_supported', 'Dieser Minijobumfang ist für Personen von 18 bis unter 65 Jahren belegt.')
    if (assessment['employee_id'] != snapshot['employee_id'] or assessment['valid_from'] > first.isoformat()
            or assessment['valid_to'] < last.isoformat()):
        block('individual_minijob_evidence_period', 'Die personengebundene Originalprüfung muss den vollständigen Monat abdecken.')
    if assessment['actual_health_insurance'] != 'statutory_family' or not all(assessment[key] for key in BOOL_FIELDS):
        block('individual_minijob_personal_facts_missing', 'GKV-Familienversicherung, Alleinbeschäftigung und relevante Einkünfte müssen vollständig belegt sein.')
    if assessment['pension_status'] != ('exempt' if p['minijob_rv_exempt'] else 'compulsory'):
        block('individual_minijob_pension_evidence', 'Der wirksame RV-Nachweis muss zum tatsächlichen Profil passen.')
    d = identity['details']
    if (d.get('identity_source_schema_version') != 2 or type(d.get('identity_source_schema_version')) is not int
            or d['tax_source'] != 'elstam_imported' or d['religion_code'] != 'none'
            or d['tax_allowance_yearly_minor'] != 0 or d['tax_addition_yearly_minor'] != 0):
        block('individual_minijob_elstam_required', 'Individuellen ELStAM-Originalnachweis ohne Freibeträge oder Hinzurechnungen verwenden.')
    files = {row['id']: row for row in snapshot['source_files']}
    for key in REF_FIELDS:
        ref = assessment[key]; row = files.get(ref['id'])
        if (row is None or row.get('employee_id') != snapshot['employee_id'] or row.get('purpose') != 'personnel'
                or row.get('content_hash') != ref['content_hash']):
            raise Problem(409, 'Ein personengebundenes Prüfungsoriginal fehlt oder wurde verändert.')
    if assessment['elstam_evidence_ref']['id'] != identity['source_file']['id']:
        raise Problem(409, 'ELStAM-Prüfung und Identitätsfassung müssen dasselbe Original binden.')
    tax_parameters = None if blockers else parameters(gross_minor=gross, tax_class=p['tax_class'], pension_exempt=p['minijob_rv_exempt'])
    def ref(row): return {key: row[key] for key in ('id', 'revision', 'content_hash')}
    social = [dict(period, profile_ref=ref(profile_record), gross_minor=gross) for period in old_plan['social_periods']]
    tax_periods = [dict(period, profile_ref=ref(profile_record), gross_minor=gross,
        inputs=period_tax_inputs(gross,lzz=2,tax_days=30,allowance_monthly_minor=0,addition_monthly_minor=0)
            if not blockers else None) for period in old_plan['tax_periods']]
    plan = dict(schema_version=1, rule_version=RULE_VERSION, source_contract_version=SOURCE_CONTRACT_VERSION,
        rules_sha256=RULES_SHA256, source_snapshot_hash=_sha(snapshot), employee_id=snapshot['employee_id'], month=snapshot['month'],
        selected_profile_ref=ref(profile_record), selected_identity_ref=ref(identity),
        employment_intervals=old_plan['employment_intervals'], identity_intervals=[dict(start=period['start'], end=period['end'],
            profile_ref=ref(profile_record), identity_ref=ref(identity)) for period in old_plan['employment_intervals']],
        earnings=[dict(row, claim_dates=[], **(dict(start=old_plan['employment_intervals'][0]['start'], end=old_plan['employment_intervals'][0]['end'])
            if len(old_plan['employment_intervals'])==1 else {})) for row in old_plan['earnings']],
        tax_periods=tax_periods, social_periods=social, gross_minor=gross, individual_minijob_assessment=assessment,
        actual_health_insurance=assessment['actual_health_insurance'], technical_pap_parameters=tax_parameters,
        blockers=sorted(blockers, key=lambda row: row['code']))
    plan['plan_hash'] = _sha(plan)
    return dict(plan, can_confirm=True, can_calculate=not blockers)


def calculate_source(snapshot, *, rule_version=RULE_VERSION, source_contract_version=SOURCE_CONTRACT_VERSION):
    plan = build_plan(snapshot, rule_version=rule_version, source_contract_version=source_contract_version)
    p = snapshot['profiles'][0]['profile']; gross = plan['gross_minor']
    result = dict(rule_version=RULE_VERSION, source_contract_version=SOURCE_CONTRACT_VERSION, rules_sha256=RULES_SHA256,
        month=plan['month'], currency='EUR', gross_minor=gross, scope=SCOPE if plan['can_calculate'] else 'unsupported',
        payroll_calculation_complete=plan['can_calculate'], social_contributions_available=plan['can_calculate'],
        blockers=plan['blockers'], accident_insurance_included=False, statutory_report_status='not_transmitted',
        official_system_approval=False, travel_expenses_included_in_net=False, net_deductions_minor=0,
        pap_version=PAP_VERSION, pap_provenance_sha256=PAP_SHA256,
        tax_parameters=dict(tax_class=p['tax_class'], children_half_units=0, church_tax_percent='0',
            actual_health_insurance=plan['actual_health_insurance'], technical_pap_parameters=plan['technical_pap_parameters']),
        period_details={key: deepcopy(plan[key]) for key in ('plan_hash', 'source_snapshot_hash', 'employment_intervals',
            'identity_intervals', 'earnings', 'tax_periods', 'social_periods')})
    empty = ('employee_contributions', 'employer_contributions', 'employee_social_total_minor', 'employer_social_total_minor',
             'employer_levies', 'employer_flat_tax_minor', 'employer_total_excluding_accident_insurance_minor',
             'individual_wage_tax_minor', 'solidarity_minor', 'church_tax_minor', 'employee_tax_minor',
             'net_minor', 'payout_minor', 'employee_additional_payment_minor')
    result.update(dict.fromkeys(empty))
    result['period_details'].update(travel=dict(tax_free_external_minor=0, flat_taxable_payroll_minor=0,
        individual_taxable_payroll_minor=0, benefit_in_kind_non_cash_minor=0, letter_m=False), flat_travel_tax=None,
        entitlement_sources=[], unpaid_dates=[], social_continuation=[])
    if not plan['can_calculate']: return result
    employee = dict.fromkeys(('health_general', 'health_additional', 'pension', 'unemployment', 'care'), 0)
    employer = dict(employee, health_general=_portion(gross, '13.000'), pension=_portion(gross, '15.000'))
    if not p['minijob_rv_exempt']: employee['pension'] = _portion(gross, '3.600')
    levies = dict(u1=_portion(gross, p['u1_percent']), u2=_portion(gross, p['u2_percent']), insolvency=_portion(gross, '0.150'))
    tax = calculate_individual_minijob_tax(gross_minor=gross, tax_class=p['tax_class'], pension_exempt=p['minijob_rv_exempt'])
    net = gross - sum(employee.values()) - tax['LSTLZZ']
    result.update(employee_contributions=employee, employer_contributions=employer,
        employee_social_total_minor=sum(employee.values()), employer_social_total_minor=sum(employer.values()),
        employer_levies=levies, employer_flat_tax_minor=0,
        employer_total_excluding_accident_insurance_minor=gross + sum(employer.values()) + sum(levies.values()),
        individual_wage_tax_minor=tax['LSTLZZ'], solidarity_minor=tax['SOLZLZZ'], church_tax_minor=0,
        employee_tax_minor=tax['LSTLZZ'], net_minor=net, payout_minor=net, employee_additional_payment_minor=0,
        tax_method='individual_elstam_minijob_bmf_rz16')
    social = plan['social_periods'][0]
    result['period_details'].update(social_assessments=[dict(period=social,
        branch_bases={key: dict(total_minor=gross if key in ('health_general', 'pension') else 0,
                              employee_minor=gross if key == 'pension' and not p['minijob_rv_exempt'] else 0)
                      for key in employee}, transition=None, care_adjustments=None, employee_contributions=employee,
        employer_contributions=employer, employer_levies=levies, levy_assessment_minor=gross)],
        tax_assessments=[dict(period=plan['tax_periods'][0], calculation=dict(version=PAP_VERSION,
            provenance_sha256=PAP_SHA256, **tax), church_tax_minor=0)])
    return result

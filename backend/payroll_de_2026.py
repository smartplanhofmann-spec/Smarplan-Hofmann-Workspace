"""Versioned offline 2026 contributions and bounded regular gross-to-net.

Archived v1 records retain their original SV-only result. New regular profiles
require explicit monthly tax allowances to use the checked PAP implementation.
No claim of statutory system approval; no reporting/provider IO.
"""
import calendar
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP, localcontext
import hashlib
import json
import re

from core import Problem
from payroll_pap_2026 import calculate_standard_tax, PAP_VERSION, PAP_PROVENANCE, PAP_SHA256

RULE_VERSION = 'de_2026_standard_contributions_v1'
RULES = dict(year=2026, version=RULE_VERSION, kv_general_percent='14.600', pv_percent='3.600',
    pv_childless_percent='0.600', pv_child_discount_percent='0.250', rv_percent='18.600', av_percent='2.600',
    kv_pv_monthly_cap_minor=581250, rv_av_monthly_cap_minor=845000, mandatory_kv_annual_limit_minor=7740000,
    minijob_monthly_limit_minor=60300, minijob_annual_limit_minor=723600, transition_upper_minor=200000,
    minijob_rv_minimum_minor=17500, minijob_kv_percent='13.000', minijob_rv_employer_percent='15.000',
    minijob_flat_tax_percent='2.000', minijob_u1_percent='0.800', minijob_u2_percent='0.220',
    insolvency_percent='0.150', rounding='BVV_1_2_HALF_UP_EACH_LEGAL_COMPONENT',
    sources=[
        'https://www.gkv-spitzenverband.de/media/dokumente/presse/zahlen_und_grafiken/20260101_Faktenblatt_Rechengroessen_Beitragsrecht.pdf',
        'https://magazin.minijob-zentrale.de/minijob-beitraege-2026/',
        'https://www.minijob-zentrale.de/DE/die-minijobs/rentenversicherungspflicht',
        'https://www.gesetze-im-internet.de/beitrvv/__1.html',
        'https://rvrecht.deutsche-rentenversicherung.de/SharedDocs/rvRecht/05_Normen_und_Vertraege/02_A-B/BVV/0002/0002_2025_01_01.html',
        'https://www.deutsche-rentenversicherung.de/DRV/DE/Experten/Arbeitgeber-und-Steuerberater/summa-summarum/Lexikon/B/beitragstragung',
    ])
RULES_SHA256 = hashlib.sha256(json.dumps(RULES, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
FULL_RULE_VERSION = 'de_2026_standard_monthly_pap_v2'
FULL_RULES = dict(RULES, version=FULL_RULE_VERSION, pap_version=PAP_VERSION,
    pap_provenance_sha256=PAP_SHA256, church_rounding='TRUNCATE_EACH_MONTH_CENT',
    church_rate_sources=[
        'https://verwaltung.bund.de/leistungsverzeichnis/DE/leistung/99102035002000/herausgeber/HH-S1000020010000006138/region/020000000000',
        'https://www.gesetze-bayern.de/Content/Document/BayAVKirchStG-9',
    ])
FULL_RULES_SHA256 = hashlib.sha256(json.dumps(FULL_RULES, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
FEDERAL_STATES = frozenset(('BW','BY','BE','BB','HB','HH','HE','MV','NI','NW','RP','SL','SN','ST','SH','TH'))
SPECIAL_CASES = frozenset(('multiple_employments','one_off_payment','benefit_in_kind','short_time_work',
    'unpaid_absence','sick_pay','pension_receipt','apprentice','working_student','foreign_tax',
    'occupational_pension','reduced_health_rate','tax_factor','old_minijob_before_2013','other_special_case',
    'church_tax_special_case'))
PROFILE_FIELDS = frozenset(('effective_from','employment_kind','date_of_birth','federal_state','tax_class',
    'tax_children_half_units','church_tax','health_insurance','health_fund','health_additional_percent',
    'has_children','pv_children_under_25','u1_required','u1_percent','u2_percent','minijob_rv_exempt',
    'minijob_tax','pension_other_compulsory','regular_annual_gross_minor','special_cases','verification_note'))
TAX_PROFILE_FIELDS = frozenset(('tax_allowance_monthly_minor','tax_addition_monthly_minor'))
TRANSITION_PROFILE_FIELDS = frozenset(('transition_assessment',))
ISSUES = {
    'year_not_supported': 'Nur die überprüften Regeln für 2026 sind eingerichtet.',
    'full_month_required': 'Dieser Rechenumfang benötigt einen vollständig versicherungspflichtigen Kalendermonat.',
    'age_case_not_supported': 'Beschäftigte unter 18 oder ab 65 Jahren benötigen eine gesonderte Prüfung.',
    'transition_not_supported': 'Der Übergangsbereich benötigt eine gesonderte Berechnung.',
    'minijob_limit_exceeded': 'Die erklärte Minijobgrenze wird überschritten; keine automatische Umklassifizierung.',
    'insurance_case_not_supported': 'Dieser Krankenversicherungsfall wird für reguläre Beschäftigung noch nicht berechnet.',
    'annual_insurance_limit': 'Die Jahresarbeitsentgeltgrenze erfordert eine gesonderte Versicherungsprüfung.',
    'minijob_individual_tax': 'Minijob mit individueller Lohnsteuer ist ohne verifizierten PAP noch nicht berechenbar.',
    'minijob_levy_mismatch': 'Die erfassten Minijob-Umlagen stimmen nicht mit den Regeln für 2026 überein.',
    'profile_not_effective': 'Die Payroll-Stammdaten gelten nicht für den vollständigen Monat.',
    'wage_source_mismatch': 'Das Brutto stimmt nicht mit der belegten Entgeltvereinbarung und den freigegebenen Quellen überein.',
    'multiple_wage_agreements': 'Entgeltänderungen innerhalb eines Monats benötigen eine getrennte Berechnung.',
    'absence_requires_review': 'Abwesenheiten/Entgeltfortzahlung benötigen vor dieser Standardabrechnung eine gesonderte Prüfung.',
    'profile_changed_in_month': 'Änderungen der Payroll-Stammdaten innerhalb eines Monats benötigen eine getrennte Berechnung.',
    'official_pap_not_validated': 'Amtlicher PAP 2026 und offizielle Steuervergleichsfälle sind noch nicht vollständig verifiziert; Lohnsteuer und reguläres Netto bleiben offen.',
}


def integer(value, minimum=0, maximum=10**12):
    if type(value) is not int or not minimum <= value <= maximum:
        raise Problem(400, 'Ganze Centbeträge beziehungsweise gültige ganze Zahlen erwartet.')
    return value


def day(value):
    try:
        result = date.fromisoformat(value) if isinstance(value, str) else None
    except ValueError:
        result = None
    if result is None or not 1900 <= result.year <= 2200 or result.isoformat() != value:
        raise Problem(400, 'Gültiges Datum als JJJJ-MM-TT erwartet.')
    return result


def month_range(month):
    if not isinstance(month, str) or not re.fullmatch(r'20\d\d-(0[1-9]|1[0-2])', month):
        raise Problem(400, 'Gültigen Abrechnungsmonat JJJJ-MM angeben.')
    year, number = map(int, month.split('-'))
    return date(year, number, 1), date(year, number, calendar.monthrange(year, number)[1])


def rate(value):
    if not isinstance(value, str) or not re.fullmatch(r'\d{1,2}(?:\.\d{1,3})?', value):
        raise Problem(400, 'Beitragssatz als exakten Prozenttext mit höchstens drei Nachkommastellen angeben.')
    number = Decimal(value)
    if not 0 <= number <= 20:
        raise Problem(400, 'Beitragssatz außerhalb des unterstützten Bereichs.')
    return format(number.quantize(Decimal('0.001')), 'f')


def normalize_profile(value):
    if not isinstance(value, dict) or set(value) not in (PROFILE_FIELDS,PROFILE_FIELDS|TAX_PROFILE_FIELDS,
            PROFILE_FIELDS|TAX_PROFILE_FIELDS|TRANSITION_PROFILE_FIELDS):
        raise Problem(400, 'Alle definierten Payroll-Stammdaten ausdrücklich angeben; unbekannte Felder sind nicht zulässig.')
    result = dict(value)
    for key in ('effective_from','date_of_birth'):
        day(value[key])
    for key in ('has_children','u1_required','minijob_rv_exempt','pension_other_compulsory'):
        if type(value[key]) is not bool:
            raise Problem(400, 'Versicherungsmerkmale ausdrücklich mit Ja oder Nein angeben.')
    for key, low, high in (('tax_class',1,6),('tax_children_half_units',0,20),('pv_children_under_25',0,20),('regular_annual_gross_minor',1,10**12)):
        integer(value[key],low,high)
    if value['pv_children_under_25'] and not value['has_children']:
        raise Problem(400, 'Kinderabschlag und Elternstatus widersprechen sich.')
    choices = dict(employment_kind=('regular','minijob'), church_tax=('none','standard'),
        health_insurance=('statutory_mandatory','statutory_other','private'), minijob_tax=('flat_2_employer','individual'))
    if (any(not isinstance(value[key], str) or value[key] not in allowed for key,allowed in choices.items())
            or not isinstance(value['federal_state'],str) or value['federal_state'] not in FEDERAL_STATES):
        raise Problem(400, 'Unbekannte Beschäftigungs-, Steuer- oder Versicherungsart.')
    if value['employment_kind']=='regular' and value['minijob_tax']!='individual':
        raise Problem(400, 'Reguläre Beschäftigung benötigt individuelle Lohnsteuermerkmale.')
    for key in ('health_additional_percent','u1_percent','u2_percent'):
        result[key] = rate(value[key])
    if TAX_PROFILE_FIELDS.issubset(value):
        for key in TAX_PROFILE_FIELDS:
            integer(value[key])
        if value['employment_kind'] != 'regular':
            raise Problem(400,'Monatliche individuelle Steuerfreibeträge gehören zum regulären Payroll-Profil.')
        if (value['tax_class'] >= 5 and value['tax_children_half_units']
                or value['tax_class'] == 6 and value['tax_addition_monthly_minor']
                or value['tax_class'] == 2 and not value['has_children']):
            raise Problem(400,'Steuerklasse, Kindermerkmale oder Hinzurechnungsbetrag widersprechen sich.')
        if Decimal(result['health_additional_percent']) != Decimal(result['health_additional_percent']).quantize(Decimal('0.01')):
            raise Problem(400,'Der PAP benötigt den tatsächlichen Kassenzusatzbeitrag mit höchstens zwei Nachkommastellen.')
    if not value['u1_required'] and Decimal(result['u1_percent']) != 0:
        raise Problem(400, 'Ohne U1-Teilnahme muss der U1-Satz ausdrücklich null sein.')
    for key,maximum in (('health_fund',200),('verification_note',2000)):
        if not isinstance(value[key],str) or not value[key].strip() or len(value[key]) > maximum or any(ord(c)<32 for c in value[key]):
            raise Problem(400, 'Krankenkasse/Versicherungsnachweis und Prüfvermerk vollständig angeben.')
        result[key] = value[key].strip()
    if not isinstance(value['special_cases'],list) or len(value['special_cases']) > len(SPECIAL_CASES) or any(not isinstance(code,str) or code not in SPECIAL_CASES for code in value['special_cases']) or len(set(value['special_cases'])) != len(value['special_cases']):
        raise Problem(400, 'Nur ausdrücklich unterstützte Kennzeichnungen für Sonderfälle angeben.')
    result['special_cases'] = sorted(value['special_cases'])
    if 'transition_assessment' in value:
        from payroll_transition_2026 import normalize_assessment
        result['transition_assessment'] = normalize_assessment(value['transition_assessment'], result)
    return result


def _portion(base_minor, percent):
    with localcontext() as context:
        context.prec = 40
        return int((Decimal(base_minor) * Decimal(percent) / Decimal(100)).quantize(Decimal(1), rounding=ROUND_HALF_UP))


def _age_completed(born, years):
    try:
        anniversary = date(born.year + years, born.month, born.day)
    except ValueError:  # A leap-day birth completes the year at the end of February.
        anniversary = date(born.year + years, 3, 1)
    return anniversary - timedelta(days=1)


def _calculate_contributions(profile, month, gross_minor, *, full_month_confirmed, source_issues=()):
    profile = normalize_profile(profile)
    integer(gross_minor,1)
    if type(full_month_confirmed) is not bool:
        raise Problem(400, 'Vollständigen Versicherungsmonat ausdrücklich bestätigen.')
    if not isinstance(source_issues,(tuple,list)) or any(code not in ISSUES or code == 'official_pap_not_validated' for code in source_issues):
        raise Problem(400, 'Ungültige Quellenprüfung.')
    first,last = month_range(month)
    born = day(profile['date_of_birth'])
    blockers = list(source_issues)
    if first.year != 2026:
        blockers.append('year_not_supported')
    if not full_month_confirmed:
        blockers.append('full_month_required')
    if day(profile['effective_from']) > first:
        blockers.append('profile_not_effective')
    if _age_completed(born,18) >= first or _age_completed(born,65) < last:
        blockers.append('age_case_not_supported')
    blockers.extend('special_case:' + code for code in profile['special_cases'])
    mini = profile['employment_kind'] == 'minijob'
    if mini:
        if gross_minor > RULES['minijob_monthly_limit_minor'] or profile['regular_annual_gross_minor'] > RULES['minijob_annual_limit_minor']:
            blockers.append('minijob_limit_exceeded')
        if profile['minijob_tax'] != 'flat_2_employer':
            blockers.append('minijob_individual_tax')
        if profile['u2_percent'] != RULES['minijob_u2_percent'] or profile['u1_percent'] != (RULES['minijob_u1_percent'] if profile['u1_required'] else '0.000'):
            blockers.append('minijob_levy_mismatch')
    else:
        if gross_minor <= RULES['transition_upper_minor'] or profile['regular_annual_gross_minor'] <= RULES['transition_upper_minor']*12:
            blockers.append('transition_not_supported')
        if profile['health_insurance'] != 'statutory_mandatory':
            blockers.append('insurance_case_not_supported')
        if profile['regular_annual_gross_minor'] > RULES['mandatory_kv_annual_limit_minor']:
            blockers.append('annual_insurance_limit')
        if profile['minijob_rv_exempt'] or profile['pension_other_compulsory']:
            blockers.append('special_case:other_special_case')
    blockers = sorted(set(blockers))
    result = dict(rule_version=RULE_VERSION,rules_sha256=RULES_SHA256,month=month,currency='EUR',gross_minor=gross_minor,
        scope='unsupported',payroll_calculation_complete=False,social_contributions_available=False,
        employee_contributions=None,employer_contributions=None,employee_social_total_minor=None,
        employer_social_total_minor=None,employer_levies=None,employer_flat_tax_minor=None,
        employer_total_excluding_accident_insurance_minor=None,accident_insurance_included=False,
        individual_wage_tax_minor=None,solidarity_minor=None,church_tax_minor=None,employee_tax_minor=None,
        net_minor=None,payout_minor=None,employee_additional_payment_minor=None,
        tax_parameters=dict(tax_class=profile['tax_class'],children_half_units=profile['tax_children_half_units'],
            church_tax_percent='0' if profile['church_tax']=='none' else '8' if profile['federal_state'] in ('BW','BY') else '9'),
        blockers=[dict(code=code,message=ISSUES.get(code,'Dieser ausdrücklich angegebene Sonderfall wird noch nicht berechnet.')) for code in blockers],
        statutory_report_status='not_transmitted',official_system_approval=False)
    if blockers:
        return result
    keys = ('health_general','health_additional','pension','unemployment','care')
    employee = dict.fromkeys(keys,0)
    employer = dict.fromkeys(keys,0)
    if mini:
        employer['health_general'] = _portion(gross_minor,RULES['minijob_kv_percent']) if profile['health_insurance'] != 'private' else 0
        employer['pension'] = _portion(gross_minor,RULES['minijob_rv_employer_percent'])
        if not profile['minijob_rv_exempt']:
            if gross_minor <= RULES['minijob_rv_minimum_minor'] and not profile['pension_other_compulsory']:
                employee['pension'] = _portion(RULES['minijob_rv_minimum_minor'],RULES['rv_percent']) - employer['pension']
            else:
                employee['pension'] = _portion(gross_minor,'3.600')
        levy_base = gross_minor
        result.update(scope='commercial_minijob_flat_tax',payroll_calculation_complete=True,
            employer_flat_tax_minor=_portion(gross_minor,RULES['minijob_flat_tax_percent']),employee_tax_minor=0,
            net_minor=gross_minor-employee['pension'],tax_method='flat_2_percent_employer_including_church_and_solidarity')
        result.update(payout_minor=max(0,result['net_minor']),employee_additional_payment_minor=max(0,-result['net_minor']))
    else:
        health_base = min(gross_minor,RULES['kv_pv_monthly_cap_minor'])
        pension_base = min(gross_minor,RULES['rv_av_monthly_cap_minor'])
        for key,base,percent in (('health_general',health_base,'7.300'),
                ('health_additional',health_base,Decimal(profile['health_additional_percent'])/2),
                ('pension',pension_base,'9.300'),('unemployment',pension_base,'1.300')):
            employee[key] = employer[key] = _portion(base,percent)
        care_employer = Decimal('1.300') if profile['federal_state']=='SN' else Decimal('1.800')
        care_employee = Decimal('3.600')-care_employer
        surcharge = not profile['has_children'] and _age_completed(born,23).strftime('%Y-%m') < month
        discount_count = max(0,min(5,profile['pv_children_under_25'])-1)
        care_employee += Decimal('0.600') if surcharge else -Decimal('0.250')*discount_count
        employee['care'] = _portion(health_base,care_employee)
        employer['care'] = _portion(health_base,care_employer)
        levy_base = pension_base
        result.update(scope='social_contributions_only',employer_flat_tax_minor=0,tax_method='individual_unavailable',
            care_employee_percent=format(care_employee,'f'),care_employer_percent=format(care_employer,'f'),
            care_childless_surcharge=surcharge,care_discount_children=discount_count,
            blockers=[dict(code='official_pap_not_validated',message=ISSUES['official_pap_not_validated'])])
    levies = dict(u1=_portion(levy_base,profile['u1_percent']),u2=_portion(levy_base,profile['u2_percent']),
                  insolvency=_portion(levy_base,RULES['insolvency_percent']))
    result.update(social_contributions_available=True,employee_contributions=employee,employer_contributions=employer,
        employee_social_total_minor=sum(employee.values()),employer_social_total_minor=sum(employer.values()),employer_levies=levies,
        employer_total_excluding_accident_insurance_minor=gross_minor+sum(employer.values())+sum(levies.values())+result['employer_flat_tax_minor'])
    return result


def calculate(profile, month, gross_minor, *, full_month_confirmed, source_issues=(), rule_version=None):
    """Keep archived v1 projections exact; opt in via complete explicit fields."""
    profile = normalize_profile(profile)
    from payroll_transition_2026 import TRANSITION_RULE_VERSION, calculate_transition
    if rule_version == TRANSITION_RULE_VERSION or 'transition_assessment' in profile:
        if rule_version not in (None, TRANSITION_RULE_VERSION) or 'transition_assessment' not in profile:
            raise Problem(400,'Der neue Midijob-Regelstand benötigt die ausdrücklich bestätigte Prognose; alte Regelstände bleiben unverändert.')
        return calculate_transition(profile,month,gross_minor,
            full_month_confirmed=full_month_confirmed,source_issues=source_issues)
    if rule_version not in (None,RULE_VERSION,FULL_RULE_VERSION):
        raise Problem(400,'Unbekannte versionierte Payroll-Berechnung.')
    result = _calculate_contributions(profile,month,gross_minor,
        full_month_confirmed=full_month_confirmed,source_issues=source_issues)
    if rule_version==RULE_VERSION:
        if TAX_PROFILE_FIELDS.issubset(profile):
            raise Problem(400,'Das historische Rechenwerk unterstützt diese neuen Steuermerkmale nicht.')
        return result
    if profile['employment_kind']=='minijob':
        if rule_version==FULL_RULE_VERSION:
            raise Problem(400,'Dieser Regelstand gehört zur regulären Beschäftigung.')
        return result
    result.update(rule_version=FULL_RULE_VERSION,rules_sha256=FULL_RULES_SHA256,
        pap_version=PAP_VERSION,pap_provenance_sha256=PAP_SHA256)
    if TAX_PROFILE_FIELDS.issubset(profile):
        result['tax_parameters'].update({key:profile[key] for key in TAX_PROFILE_FIELDS})
    if not result['social_contributions_available']:
        return result
    if not TAX_PROFILE_FIELDS.issubset(profile):
        result['blockers']=[dict(code='tax_profile_incomplete',
            message='Monatlichen Steuerfreibetrag und Hinzurechnungsbetrag ausdrücklich aus dem Nachweis erfassen; auch null muss bestätigt werden.')]
        return result
    first,_ = month_range(month)
    if _age_completed(day(profile['date_of_birth']),64) < date(first.year,1,1):
        result['blockers']=[dict(code='age_allowance_not_supported',
            message='Altersentlastungsbetrag: vor Jahresbeginn vollendetes 64. Lebensjahr benötigt eine gesonderte Steuerberechnung.')]
        return result
    tax = calculate_standard_tax(gross_minor=gross_minor,period=2,tax_class=profile['tax_class'],
        children_half_units=profile['tax_children_half_units'],
        additional_health_percent=format(Decimal(profile['health_additional_percent']),'.2f'),
        saxony=profile['federal_state']=='SN',childless_surcharge=result['care_childless_surcharge'],
        care_child_discounts=result['care_discount_children'],church_member=profile['church_tax']!='none',
        allowance_minor=profile['tax_allowance_monthly_minor'],addition_minor=profile['tax_addition_monthly_minor'])
    church = tax['BK'] * int(result['tax_parameters']['church_tax_percent']) // 100
    employee_tax = tax['LSTLZZ']+tax['SOLZLZZ']+church
    net = gross_minor-result['employee_social_total_minor']-employee_tax
    result.update(scope='regular_standard_monthly',payroll_calculation_complete=True,
        tax_method='individual_bmf_pap_2026_standard',individual_wage_tax_minor=tax['LSTLZZ'],
        solidarity_minor=tax['SOLZLZZ'],church_tax_minor=church,employee_tax_minor=employee_tax,
        net_minor=net,payout_minor=max(0,net),employee_additional_payment_minor=max(0,-net),blockers=[])
    result['tax_parameters']['church_assessment_minor']=tax['BK']
    return result

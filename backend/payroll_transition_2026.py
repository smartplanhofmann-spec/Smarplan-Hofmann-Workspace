"""Explicitly elected 2026 full-month transition-area payroll.

Historical v1/v2 profiles never enter this calculator. Forecast evidence belongs
to the immutable private profile original; actual monthly pay does not set the
employment status. No filing, payment, provider IO or certification claim.
"""
from datetime import date
from decimal import Decimal, ROUND_HALF_UP, localcontext
import hashlib
import json

from core import Problem
from payroll_de_2026 import (RULES, FULL_RULES, ISSUES, integer, day, month_range,
    _age_completed, _portion, calculate_standard_tax, PAP_VERSION, PAP_SHA256)

TRANSITION_RULE_VERSION = 'de_2026_transition_monthly_pap_v3'
TRANSITION_RULES = dict(FULL_RULES, version=TRANSITION_RULE_VERSION,
    transition_lower_minor=60300,transition_upper_minor=200000,transition_factor='0.6619',
    rounding='BVV_2_2_SEPARATE_BASES_HALF_RATE_ROUND_THEN_DOUBLE',
    care_discount_method='SEPARATE_AN_DISCOUNT_AG_UNCHANGED_GKV_2025_03_31_3_3',
    forecast_required=True,full_month_only=True,
    transition_sources=[
        'https://www.deutsche-rentenversicherung.de/DRV/DE/Experten/Arbeitgeber-und-Steuerberater/summa-summarum/Lexikon/U/uebergangsbereich',
        'https://rvrecht.deutsche-rentenversicherung.de/SharedDocs/rvRecht/05_Normen_und_Vertraege/02_A-B/BVV/0002/0002_2025_01_01.html',
        'https://www.gkv-spitzenverband.de/media/dokumente/pflegeversicherung/grundprinzipien/2025-03-31_GH_Beitragssatzdifferenzierung_sPV.pdf',
        'https://www.kbs.de/SharedDocs/Downloads/DE/VersicherungsrechtBeitraegeMeldungen/Downloads/Uebergangsbereich_idF_20_12_2022.pdf?__blob=publicationFile&v=2',
    ])
TRANSITION_RULES_SHA256=hashlib.sha256(json.dumps(TRANSITION_RULES,sort_keys=True,separators=(',',':')).encode()).hexdigest()
ASSESSMENT_FIELDS=frozenset(('status','assessed_on','regular_monthly_gross_minor','forecast_months',
    'foreseeable_one_off_payments','note'))


def normalize_assessment(value,profile):
    if not isinstance(value,dict) or set(value)!=ASSESSMENT_FIELDS:
        raise Problem(400,'Die belegte Midijob-Prognose muss vollständig und ohne unbekannte Felder angegeben werden.')
    if profile['employment_kind']!='regular' or value['status']!='within_transition_area':
        raise Problem(400,'Die Prognose gilt ausschließlich für ausdrücklich reguläre Beschäftigung im Übergangsbereich.')
    day(value['assessed_on'])
    integer(value['forecast_months'],12,12)
    integer(value['regular_monthly_gross_minor'],60301,200000)
    if profile['regular_annual_gross_minor']!=value['regular_monthly_gross_minor']*12:
        raise Problem(400,'Regelmäßiges Jahresentgelt und belegte Zwölfmonatsprognose widersprechen sich.')
    if type(value['foreseeable_one_off_payments']) is not bool:
        raise Problem(400,'Vorhersehbare Einmalzahlungen ausdrücklich mit Ja oder Nein kennzeichnen.')
    if (not isinstance(value['note'],str) or not value['note'].strip() or len(value['note'])>2000
            or any(ord(char)<32 for char in value['note'])):
        raise Problem(400,'Grundlage der prognostischen Statusprüfung vollständig dokumentieren.')
    return {**value,'note':value['note'].strip()}


def assessment_bases(gross_minor):
    """BVV §2(2); return both rounded cent bases, never rounded coefficients."""
    integer(gross_minor,1)
    low,high=60300,200000
    if gross_minor>high:
        return dict(regime='above_upper_limit',total_assessment_minor=gross_minor,employee_assessment_minor=gross_minor)
    with localcontext() as context:
        context.prec=50
        factor=Decimal('0.6619')
        if gross_minor<=low:
            total=Decimal(gross_minor)*factor
            employee=Decimal(0)
            regime='below_or_at_lower_limit'
        else:
            total=factor*low+(Decimal(high)/(high-low)-Decimal(low)/(high-low)*factor)*(gross_minor-low)
            employee=Decimal(high)/(high-low)*(gross_minor-low)
            regime='within_transition_area'
        return dict(regime=regime,total_assessment_minor=int(total.quantize(Decimal(1),rounding=ROUND_HALF_UP)),
            employee_assessment_minor=int(employee.quantize(Decimal(1),rounding=ROUND_HALF_UP)))


def care_contributions(total_base,employee_base,*,saxony,surcharge,discount_count,reduced):
    """GKV 31.03.2025 3.3: discount is separate; AG excludes it and surcharge."""
    employee_rate=Decimal('2.300') if saxony else Decimal('1.800')
    employer_rate=Decimal('1.300') if saxony else Decimal('1.800')
    theoretical=_portion(employee_base,employee_rate)
    employer=2*_portion(total_base,'1.800')-theoretical if reduced else _portion(total_base,employer_rate)
    addition=_portion(total_base,'0.600') if surcharge else 0
    discount=_portion(employee_base,Decimal('0.250')*discount_count)
    return theoretical+addition-discount,employer,dict(employee_before_adjustments_minor=theoretical,
        childless_surcharge_minor=addition,children_discount_minor=discount,
        employee_base_percent=format(employee_rate,'f'),employer_normal_percent=format(employer_rate,'f'))


def calculate_transition(profile,month,gross_minor,*,full_month_confirmed,source_issues=()):
    # Public dispatcher normalized the complete profile; this entry still checks
    # its explicit election so direct callers cannot bypass the evidence shape.
    from payroll_de_2026 import normalize_profile
    profile=normalize_profile(profile)
    if 'transition_assessment' not in profile:
        raise Problem(400,'Belegte Midijob-Prognose fehlt.')
    integer(gross_minor,1)
    if type(full_month_confirmed) is not bool:
        raise Problem(400,'Vollständigen Versicherungsmonat ausdrücklich bestätigen.')
    if not isinstance(source_issues,(tuple,list)) or any(code not in ISSUES or code=='official_pap_not_validated' for code in source_issues):
        raise Problem(400,'Ungültige Quellenprüfung.')
    first,last=month_range(month); born=day(profile['date_of_birth'])
    blockers=list(source_issues)
    if first.year!=2026: blockers.append('year_not_supported')
    if not full_month_confirmed: blockers.append('full_month_required')
    if day(profile['effective_from'])>first: blockers.append('profile_not_effective')
    if _age_completed(born,18)>=first or _age_completed(born,65)<last: blockers.append('age_case_not_supported')
    blockers.extend('special_case:'+code for code in profile['special_cases'])
    if profile['transition_assessment']['foreseeable_one_off_payments']: blockers.append('special_case:one_off_payment')
    if profile['health_insurance']!='statutory_mandatory': blockers.append('insurance_case_not_supported')
    if profile['minijob_rv_exempt'] or profile['pension_other_compulsory']: blockers.append('special_case:other_special_case')
    if _age_completed(born,64)<date(first.year,1,1): blockers.append('age_allowance_not_supported')
    result=dict(rule_version=TRANSITION_RULE_VERSION,rules_sha256=TRANSITION_RULES_SHA256,
        pap_version=PAP_VERSION,pap_provenance_sha256=PAP_SHA256,month=month,currency='EUR',gross_minor=gross_minor,
        scope='unsupported',payroll_calculation_complete=False,social_contributions_available=False,
        employee_contributions=None,employer_contributions=None,employee_social_total_minor=None,
        employer_social_total_minor=None,employer_levies=None,employer_flat_tax_minor=None,
        employer_total_excluding_accident_insurance_minor=None,accident_insurance_included=False,
        individual_wage_tax_minor=None,solidarity_minor=None,church_tax_minor=None,employee_tax_minor=None,
        net_minor=None,payout_minor=None,employee_additional_payment_minor=None,
        tax_parameters=dict(tax_class=profile['tax_class'],children_half_units=profile['tax_children_half_units'],
            church_tax_percent='0' if profile['church_tax']=='none' else '8' if profile['federal_state'] in ('BW','BY') else '9',
            tax_allowance_monthly_minor=profile['tax_allowance_monthly_minor'],tax_addition_monthly_minor=profile['tax_addition_monthly_minor']),
        blockers=[dict(code=code,message=ISSUES.get(code,'Dieser ausdrücklich angegebene Sonderfall benötigt eine gesonderte Berechnung.')) for code in sorted(set(blockers))],
        statutory_report_status='not_transmitted',official_system_approval=False,transition=None)
    if blockers: return result
    bases=assessment_bases(gross_minor)
    total,employee_base=bases['total_assessment_minor'],bases['employee_assessment_minor']
    reduced=bases['regime']!='above_upper_limit'
    employee={}; employer={}; branch_bases={}
    for key,cap,half in (('health_general',RULES['kv_pv_monthly_cap_minor'],Decimal('7.300')),
            ('health_additional',RULES['kv_pv_monthly_cap_minor'],Decimal(profile['health_additional_percent'])/2),
            ('pension',RULES['rv_av_monthly_cap_minor'],Decimal('9.300')),
            ('unemployment',RULES['rv_av_monthly_cap_minor'],Decimal('1.300'))):
        full_base,an_base=min(total,cap),min(employee_base,cap)
        employee[key]=_portion(an_base,half)
        employer[key]=2*_portion(full_base,half)-employee[key]
        branch_bases[key]=dict(total_minor=full_base,employee_minor=an_base)
    surcharge=not profile['has_children'] and _age_completed(born,23).strftime('%Y-%m')<month
    discount_count=max(0,min(5,profile['pv_children_under_25'])-1)
    full_care,an_care=min(total,RULES['kv_pv_monthly_cap_minor']),min(employee_base,RULES['kv_pv_monthly_cap_minor'])
    employee['care'],employer['care'],care=care_contributions(full_care,an_care,saxony=profile['federal_state']=='SN',
        surcharge=surcharge,discount_count=discount_count,reduced=reduced)
    branch_bases['care']=dict(total_minor=full_care,employee_minor=an_care)
    levy_base=min(total,RULES['rv_av_monthly_cap_minor'])
    levies=dict(u1=_portion(levy_base,profile['u1_percent']),u2=_portion(levy_base,profile['u2_percent']),
        insolvency=_portion(levy_base,RULES['insolvency_percent']))
    tax=calculate_standard_tax(gross_minor=gross_minor,period=2,tax_class=profile['tax_class'],
        children_half_units=profile['tax_children_half_units'],additional_health_percent=format(Decimal(profile['health_additional_percent']),'.2f'),
        saxony=profile['federal_state']=='SN',childless_surcharge=surcharge,care_child_discounts=discount_count,
        church_member=profile['church_tax']!='none',allowance_minor=profile['tax_allowance_monthly_minor'],
        addition_minor=profile['tax_addition_monthly_minor'])
    church=tax['BK']*int(result['tax_parameters']['church_tax_percent'])//100
    employee_tax=tax['LSTLZZ']+tax['SOLZLZZ']+church
    net=gross_minor-sum(employee.values())-employee_tax
    result.update(scope='regular_transition_monthly',payroll_calculation_complete=True,social_contributions_available=True,
        employee_contributions=employee,employer_contributions=employer,employee_social_total_minor=sum(employee.values()),
        employer_social_total_minor=sum(employer.values()),employer_levies=levies,employer_flat_tax_minor=0,
        employer_total_excluding_accident_insurance_minor=gross_minor+sum(employer.values())+sum(levies.values()),
        care_childless_surcharge=surcharge,care_discount_children=discount_count,
        tax_method='individual_bmf_pap_2026_standard',individual_wage_tax_minor=tax['LSTLZZ'],solidarity_minor=tax['SOLZLZZ'],
        church_tax_minor=church,employee_tax_minor=employee_tax,net_minor=net,payout_minor=max(0,net),
        employee_additional_payment_minor=max(0,-net),
        transition={**bases,'regular_monthly_gross_minor':profile['transition_assessment']['regular_monthly_gross_minor'],
            'factor':'0.6619','branch_bases':branch_bases,'levy_assessment_minor':levy_base,'care_adjustments':care})
    result['tax_parameters']['church_assessment_minor']=tax['BK']
    return result

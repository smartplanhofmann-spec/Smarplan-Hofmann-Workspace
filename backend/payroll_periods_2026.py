"""Pure, explicitly evidenced ordinary employment periods for payroll 2026.

No database, actor, current clock, provider, payment or filing is consulted.
P2 resolves immutable personnel sources; this module derives a period plan and
the independently versioned P3a calculation. Historical v1/v2/v3 are unchanged.
"""
from datetime import timedelta
from decimal import Decimal, ROUND_HALF_UP, localcontext
import hashlib
import json

from core import Problem, canonical
from payroll_de_2026 import (RULES, FULL_RULES, TAX_PROFILE_FIELDS, normalize_profile,
    integer, day, month_range, _portion, _age_completed, PAP_VERSION, PAP_PROVENANCE)
from payroll_pap_periods_2026 import (DAILY_PAP_RULES, DAILY_PAP_SHA256,
    calculate_period_tax, period_tax_inputs)
from payroll_transition_2026 import care_contributions

PERIOD_RULE_VERSION = 'de_2026_periods_pap_v4'
PERIOD_RULES = dict(FULL_RULES, version=PERIOD_RULE_VERSION,
    daily_pap=DAILY_PAP_RULES, daily_pap_sha256=DAILY_PAP_SHA256,
    supported_case='ONE_DOMESTIC_EMPLOYMENT_EPISODE_ONE_AGREEMENT_ONE_SOCIAL_PROFILE',
    partial_caps='ANNUAL_CAP_TIMES_ACTUAL_SOCIAL_DAYS_DIVIDE_360_ROUND_ONCE',
    church_rounding='TRUNCATE_ACTUAL_LZZ_TOTAL_BK_TIMES_RATE_TO_CENT',
    wage_method='EXPLICIT_CONTRACTUAL_QUOTIENT_NO_DEFAULT',
    transition_factor='0.6619', transition_rounding='EXACT_MONTH_EQUIVALENT_BASE_THEN_CONTRACTUAL_PART_ROUND_CENT',
    minimum_pension='17500_TIMES_SOCIAL_DAYS_DIVIDE_30_ROUND_CENT_BEFORE_CONTRIBUTION',
    source_schema_version=2,
    period_sources=[
        'https://www.deutsche-rentenversicherung.de/SharedDocs/Downloads/DE/Fachliteratur_Kommentare_Gesetzestexte/summa_summarum/e_paper_und_broschueren/broschueren/beitraege.pdf?__blob=publicationFile&v=10',
        'https://www.kbs.de/SharedDocs/Downloads/DE/VersicherungsrechtBeitraegeMeldungen/Downloads/Uebergangsbereich_idF_20_12_2022.pdf?__blob=publicationFile&v=2',
        'https://www.minijob-zentrale.de/SharedDocs/Downloads/DE/Rundschreiben/Geringfuegigkeitsrichtlinien-2026.pdf?__blob=publicationFile',
        'https://www.gesetze-bayern.de/Content/Document/BayKirchStG-8',
        'https://www.gesetze-bayern.de/Content/Document/BayKirchStG-13',
        'https://www.gesetze-bayern.de/Content/Document/BayAVKirchStG-9'])
PERIOD_RULES_SHA256 = hashlib.sha256(canonical(PERIOD_RULES).encode()).hexdigest()
METHODS = frozenset(('calendar_days_actual','contractual_30_days','scheduled_workdays','scheduled_seconds'))
SCOPES = ('regular_standard_period','regular_transition_period','commercial_minijob_period_flat_tax')


def _sha(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def _rounded(value):
    return int(Decimal(value).quantize(Decimal(1),rounding=ROUND_HALF_UP))


def _ratio_minor(value,numerator,denominator):
    with localcontext() as context:
        context.prec=50
        return _rounded(Decimal(value)*Decimal(numerator)/Decimal(denominator))


def partial_caps(social_days):
    integer(social_days,1,30)
    return dict(health_minor=_ratio_minor(6975000,social_days,360),
        care_minor=_ratio_minor(6975000,social_days,360),
        pension_minor=_ratio_minor(10140000,social_days,360),
        unemployment_minor=_ratio_minor(10140000,social_days,360))


def _ref(record):
    return {key:record[key] for key in ('id','revision','content_hash')}


def _dates(first,last):
    return [(first+timedelta(days=i)).isoformat() for i in range((last-first).days+1)]


def _profile_blockers(p,gross,start,end):
    result=[]
    def block(code,message):result.append(dict(code=code,message=message))
    born=day(p['date_of_birth']);mini=p['employment_kind']=='minijob';transition='transition_assessment' in p
    if _age_completed(born,18)>=start or _age_completed(born,65)<end:
        block('age_case_not_supported','Beschäftigte unter 18 oder ab 65 Jahren benötigen den gesonderten Altersregelzweig.')
    for value in p['special_cases']:block('special_case:'+value,'Der ausdrücklich angegebene Sonderfall benötigt seinen gesonderten Regelzweig.')
    if mini:
        if gross is not None and gross>60300 or p['regular_annual_gross_minor']>723600:
            block('minijob_limit_exceeded','Die belegte Minijobgrenze wird überschritten; keine automatische Umklassifizierung.')
        if p['minijob_tax']!='flat_2_employer':block('minijob_individual_tax','Individuell versteuerter Minijob benötigt den gesonderten Regelzweig.')
        if p['u2_percent']!='0.220' or p['u1_percent']!=('0.800' if p['u1_required'] else '0.000'):
            block('minijob_levy_mismatch','Die gewerblichen Minijob-Umlagen entsprechen nicht dem Regelstand 2026.')
    else:
        if p['health_insurance']!='statutory_mandatory':block('insurance_case_not_supported','Diese Krankenversicherung benötigt ihren eigenen Regelzweig.')
        if p['regular_annual_gross_minor']>7740000:block('annual_insurance_limit','Die Jahresarbeitsentgeltgrenze verlangt eine gesonderte Versicherungsprüfung.')
        if p['minijob_rv_exempt'] or p['pension_other_compulsory']:block('regular_insurance_mismatch','Die reguläre Beschäftigung hat widersprüchliche RV-Merkmale.')
        if not transition and p['regular_annual_gross_minor']<=2400000:
            block('transition_assessment_missing','Für den prognostischen Übergangsbereich fehlt die ausdrücklich belegte Statusentscheidung.')
        if transition and p['transition_assessment']['foreseeable_one_off_payments']:
            block('special_case:one_off_payment','Vorhersehbare Einmalbezüge benötigen ihren eigenen Entgelt- und Prognosezweig.')
    return result


def build_period_plan(source_snapshot):
    """Derive all quantities from frozen canonical sources, never user totals.

    Malformed source structure is rejected. Valid but not yet supported legal
    facts are represented by explicit blockers and no fabricated calculation.
    """
    required={'schema_version','employee_id','month','preparation','profiles','identities',
        'employment_terms','work_schedule','case_details','source_files'}
    if not isinstance(source_snapshot,dict) or set(source_snapshot)!=required or source_snapshot['schema_version']!=1:
        raise Problem(400,'Vollständigen versionierten Quellenstand für den Periodenplan angeben.')
    s=source_snapshot;first,last=month_range(s['month']);employee_id=s['employee_id']
    preparation=s['preparation'];snapshot=preparation['snapshot'];employee=snapshot['employee']
    terms=s['employment_terms'];details=terms['details'];case=s['case_details']
    if (preparation['employee_id']!=employee_id or employee['id']!=employee_id or preparation['month']!=s['month']
            or snapshot['month']!=s['month'] or terms['employee_id']!=employee_id or terms['kind']!='employment_terms'
            or terms['status']!='active' or case['month']!=s['month']):
        raise Problem(400,'Periodenquellen gehören nicht zum selben Mitarbeiter und Monat.')
    if details['proration_method'] not in METHODS:
        raise Problem(400,'Die belegte Teilentgeltmethode ist unbekannt.')
    if (not isinstance(s['profiles'],list) or not s['profiles'] or not isinstance(s['identities'],list)
            or not isinstance(case['entitlement_decisions'],list)):
        raise Problem(400,'Periodenprofile, Identitäten und Anspruchsentscheidungen vollständig angeben.')
    blockers=[]
    def block(code,message):
        if not any(value['code']==code for value in blockers):blockers.append(dict(code=code,message=message))
    if first.year!=2026:block('year_not_supported','Dieser Periodenregelstand gilt ausschließlich für 2026.')
    if employee['employment_from']!=details['employment_from'] or employee['employment_to']!=details['employment_to']:
        block('employment_source_mismatch','Belegter Beschäftigungszeitraum und Personalstamm widersprechen sich.')
    started=day(details['employment_from']);ended=day(details['employment_to']) if details['employment_to'] is not None else last
    if ended<started:raise Problem(400,'Beschäftigungsende liegt vor dem Beginn.')
    start=max(first,started);end=min(last,ended)
    if start>end:block('no_employment_in_period','In diesem Monat besteht kein belegter Beschäftigungszeitraum.')
    active_dates=[] if start>end else _dates(start,end)
    full_month=start==first and end==last
    social_days=30 if full_month else min(30,len(active_dates))
    tax_days=30 if full_month else len(active_dates)
    lzz=2 if full_month else 4
    agreements=snapshot['agreements']
    if not agreements:raise Problem(400,'Die Monatsvorbereitung enthält keine Entgeltvereinbarung.')
    if len(agreements)!=1:block('multiple_wage_agreements','Mehrere wirksame Entgeltvereinbarungen benötigen den gesonderten Segmentzweig.')
    agreement=agreements[0]
    if any(_ref(value) not in details['agreement_refs'] for value in agreements):
        block('agreement_source_mismatch','Die Vertragsfakten binden nicht alle im Monat belegten Entgeltvereinbarungen.')
    if agreement['effective_from']>start.isoformat():block('agreement_not_effective','Zum tatsächlichen Beschäftigungsbeginn fehlt eine wirksame Entgeltvereinbarung.')
    profiles=sorted(s['profiles'],key=lambda value:(value['profile']['effective_from'],value['id']))
    if any(value['employee_id']!=employee_id or value['kind']!='profile' for value in profiles):
        raise Problem(400,'Fremdes oder unzulässiges Steuerprofil im Periodenplan.')
    eligible=[value for value in profiles if value['profile']['effective_from']<=end.isoformat()]
    profile=eligible[-1] if eligible else profiles[0]
    p=normalize_profile(profile['profile'])
    if p!=profile['profile']:raise Problem(400,'Das Periodenprofil ist nicht normalisiert.')
    if p['effective_from']>start.isoformat():block('profile_not_effective','Steuer-/Versicherungsprofil deckt den Beschäftigungsbeginn nicht ab.')
    if any(start.isoformat()<value['profile']['effective_from']<=end.isoformat() for value in profiles):
        block('profile_changed_in_period','Untermonatige Steuer-/Versicherungsänderungen benötigen eine gesonderte Segmentprüfung.')
    if agreement['employment_kind']!=p['employment_kind']:block('employment_kind_mismatch','Entgeltvertrag und Versicherungsstatus stimmen nicht überein.')
    identities=[]
    for value in s['identities']:
        if value['employee_id']!=employee_id or value['kind']!='identity':raise Problem(400,'Fremder Lohnkonto-Identitätsnachweis.')
        values=value['details']
        if (values['profile_id']==profile['id'] and values['profile_revision']==profile['revision']
                and values['valid_from']<=start.isoformat() and values['valid_to']>=end.isoformat()
                and values['employment_from']<=start.isoformat()
                and (values['employment_to'] is None or values['employment_to']>=end.isoformat())):
            identities.append(value)
    if not identities:block('period_identity_missing','Ein zur gewählten Profilrevision passender Identitäts-/Steuernachweis für den tatsächlichen Zeitraum fehlt.')
    if len(identities)>1:block('ambiguous_period_identity','Mehrere widersprüchliche Identitäts-/Steuernachweise sind für diesen Zeitraum ausgewählt.')
    if case['tax_treatment']!='domestic_running_wages':block('tax_treatment_not_supported','Dieser steuerliche Periodenfall benötigt einen eigenen Regelzweig.')
    numerator=denominator=0;schedule=s['work_schedule']
    if details['proration_method']=='calendar_days_actual':numerator,denominator=len(active_dates),(last-first).days+1
    elif details['proration_method']=='contractual_30_days':numerator,denominator=(30 if full_month else min(30,len(active_dates))),30
    else:
        if schedule is None:
            block('work_schedule_missing','Für diese Vertragsmethode fehlt ein belegter vollständiger Monatsarbeitsplan.')
        else:
            if schedule['employee_id']!=employee_id or schedule['kind']!='work_schedule' or schedule['status']!='active' or schedule['details']['month']!=s['month']:
                raise Problem(400,'Arbeitsplan gehört nicht zu diesem Mitarbeiter und Monat.')
            days=schedule['details']['days']
            if not isinstance(days,list) or [value['date'] for value in days]!=_dates(first,last):
                raise Problem(400,'Der Arbeitsplan muss jeden Kalendertag des Monats genau einmal aufsteigend enthalten.')
            for value in days:integer(value['scheduled_seconds'],0,86400)
            weight=lambda value:int(value['scheduled_seconds']>0) if details['proration_method']=='scheduled_workdays' else value['scheduled_seconds']
            numerator=sum(weight(value) for value in days if value['date'] in active_dates)
            denominator=sum(weight(value) for value in days)
            if denominator==0:block('empty_work_schedule','Der gewählte Monatsarbeitsplan hat keine bezahlten Solltage beziehungsweise Sollsekunden.')
    net_seconds=integer(snapshot['net_work_seconds'],0,31*86400)
    if any(value['date'] not in active_dates and value['net_seconds'] for value in snapshot['approved_days']):
        block('work_outside_employment','Freigegebene Arbeitszeit liegt außerhalb des belegten Beschäftigungszeitraums.')
    if any(value['kind']!='vacation' or agreement['pay_basis']!='monthly' for value in snapshot['approved_absences']):
        block('entitlement_requires_calculation','Krankheit, unbezahlte Zeit oder bezahlte Ausfallstunden benötigen den eigenen Anspruchsrechenzweig.')
    if any(value['kind'] not in ('ordinary_work','vacation') or value['kind']=='vacation' and agreement['pay_basis']!='monthly'
            for value in case['entitlement_decisions']):
        block('entitlement_requires_calculation','Die ausdrücklich belegte Anspruchsentscheidung benötigt den eigenen Anspruchsrechenzweig.')
    if agreement['pay_basis']=='monthly':
        gross=_ratio_minor(agreement['amount_minor'],numerator,denominator) if denominator else None
        if p['regular_annual_gross_minor']!=agreement['amount_minor']*12:
            block('regular_wage_mismatch','Regelmäßiges Jahresentgelt stimmt nicht mit dem belegten Monatsvertrag überein.')
        transition_ratio=dict(numerator=numerator,denominator=denominator)
    elif agreement['pay_basis']=='hourly':
        gross=_ratio_minor(agreement['amount_minor'],net_seconds,3600)
        transition_ratio=dict(numerator=social_days,denominator=30)
    else:raise Problem(400,'Unbekannte Entgeltbasis im Periodenplan.')
    if gross==0:block('zero_earnings_requires_review','Ein Monat ohne Entgelt benötigt eine gesonderte Anspruchs- und SV-Fortbestandsprüfung.')
    if len(agreements)!=1:gross=None
    mini=p['employment_kind']=='minijob';tax_inputs=None
    if not mini and not TAX_PROFILE_FIELDS.issubset(p):
        block('explicit_tax_features_missing','Die ausdrücklich belegten monatlichen Steuerfreibeträge und Hinzurechnungsbeträge fehlen.')
    if gross is not None and tax_days and not mini and TAX_PROFILE_FIELDS.issubset(p):
        tax_inputs=period_tax_inputs(gross,lzz=lzz,tax_days=tax_days,
            allowance_monthly_minor=p['tax_allowance_monthly_minor'],addition_monthly_minor=p['tax_addition_monthly_minor'])
    for issue in _profile_blockers(p,gross,start,end):block(issue['code'],issue['message'])
    refs=[dict(kind='preparation',**_ref(preparation)),dict(kind='employment_terms',**_ref(terms))]
    if schedule is not None:refs.append(dict(kind='work_schedule',**_ref(schedule)))
    refs += [dict(kind='profile',**_ref(value)) for value in profiles]
    refs += [dict(kind='identity',**_ref(value)) for value in s['identities']]
    plan=dict(schema_version=1,rule_version=PERIOD_RULE_VERSION,rules_sha256=PERIOD_RULES_SHA256,
        employee_id=employee_id,month=s['month'],source_snapshot_hash=_sha(s),sources=refs,
        employment_intervals=[] if not active_dates else [dict(start=start.isoformat(),end=end.isoformat(),calendar_days=len(active_dates))],
        earnings=[dict(kind='ordinary_work',agreement_ref=_ref(agreement),pay_basis=agreement['pay_basis'],
            proration_method=details['proration_method'],numerator=numerator,denominator=denominator,
            approved_work_seconds=net_seconds,gross_minor=gross)],gross_minor=gross,
        selected_profile_ref=_ref(profile),selected_identity_ref=_ref(identities[0]) if len(identities)==1 else None,
        tax_periods=[] if not active_dates else [dict(start=start.isoformat(),end=end.isoformat(),lzz=lzz,tax_days=tax_days,inputs=tax_inputs)],
        social_periods=[] if not active_dates else [dict(start=start.isoformat(),end=end.isoformat(),days=social_days,
            full_month=full_month,caps=partial_caps(social_days),transition_ratio=transition_ratio,
            minimum_pension_basis_minor=_ratio_minor(17500,social_days,30))],
        entitlement_decisions=case['entitlement_decisions'],blockers=sorted(blockers,key=lambda value:value['code']))
    plan['plan_hash']=_sha(plan)
    return dict(plan,can_confirm=True,can_calculate=not blockers)


def _transition_bases(gross_minor,numerator,denominator):
    """Exact contractual equivalence; round the final partial bases once."""
    integer(gross_minor,1);integer(numerator,1);integer(denominator,1)
    with localcontext() as context:
        context.prec=50
        equivalent=Decimal(gross_minor)*denominator/numerator
        if equivalent>200000:
            return dict(regime='above_upper_limit',total_assessment_minor=gross_minor,
                employee_assessment_minor=gross_minor,monthly_equivalent_minor=format(equivalent,'f'))
        if equivalent<=60300:
            total=equivalent*Decimal('0.6619');employee=Decimal(0);regime='below_or_at_lower_limit'
        else:
            total=Decimal('0.6619')*60300+(Decimal(200000)/139700-Decimal(60300)/139700*Decimal('0.6619'))*(equivalent-60300)
            employee=Decimal(200000)/139700*(equivalent-60300);regime='within_transition_area'
        return dict(regime=regime,total_assessment_minor=_rounded(total*numerator/denominator),
            employee_assessment_minor=_rounded(employee*numerator/denominator),monthly_equivalent_minor=format(equivalent,'f'))


def calculate_period_source(source_snapshot,*,rule_version=None):
    if rule_version not in (None,PERIOD_RULE_VERSION):raise Problem(400,'Unbekannte Periodenregelversion.')
    plan=build_period_plan(source_snapshot)
    profile=next(value for value in source_snapshot['profiles'] if _ref(value)==plan['selected_profile_ref'])
    p=profile['profile'];gross=plan['gross_minor'];mini=p['employment_kind']=='minijob';transition='transition_assessment' in p
    blockers=list(plan['blockers'])
    born=day(p['date_of_birth'])
    result=dict(rule_version=PERIOD_RULE_VERSION,rules_sha256=PERIOD_RULES_SHA256,month=plan['month'],currency='EUR',
        gross_minor=gross,scope='unsupported',payroll_calculation_complete=False,social_contributions_available=False,
        employee_contributions=None,employer_contributions=None,employee_social_total_minor=None,employer_social_total_minor=None,
        employer_levies=None,employer_flat_tax_minor=None,employer_total_excluding_accident_insurance_minor=None,
        accident_insurance_included=False,individual_wage_tax_minor=None,solidarity_minor=None,church_tax_minor=None,
        employee_tax_minor=None,net_minor=None,payout_minor=None,employee_additional_payment_minor=None,
        tax_parameters=dict(tax_class=p['tax_class'],children_half_units=p['tax_children_half_units'],
            church_tax_percent='0' if p['church_tax']=='none' else '8' if p['federal_state'] in ('BW','BY') else '9'),
        blockers=sorted(blockers,key=lambda value:value['code']),statutory_report_status='not_transmitted',
        official_system_approval=False,travel_expenses_included_in_net=False,
        period_details={key:plan[key] for key in ('plan_hash','source_snapshot_hash','employment_intervals','earnings','tax_periods','social_periods')})
    if blockers:return result
    social=plan['social_periods'][0];caps=social['caps'];keys=('health_general','health_additional','pension','unemployment','care')
    employee=dict.fromkeys(keys,0);employer=dict.fromkeys(keys,0)
    surcharge=not p['has_children'] and _age_completed(born,23).strftime('%Y-%m')<plan['month']
    discounts=max(0,min(5,p['pv_children_under_25'])-1)
    if mini:
        employer['health_general']=_portion(gross,'13.000') if p['health_insurance']!='private' else 0
        employer['pension']=_portion(gross,'15.000')
        if not p['minijob_rv_exempt']:
            minimum=social['minimum_pension_basis_minor']
            employee['pension']=_portion(minimum,'18.600')-employer['pension'] if gross<minimum and not p['pension_other_compulsory'] else _portion(gross,'3.600')
        levy_base=gross;flat_tax=_portion(gross,'2.000');employee_tax=0
        result.update(scope='commercial_minijob_period_flat_tax',tax_method='flat_2_percent_employer_including_church_and_solidarity')
    else:
        if transition:
            ratio=social['transition_ratio'];basis=_transition_bases(gross,ratio['numerator'],ratio['denominator'])
            total_base=basis['total_assessment_minor'];employee_base=basis['employee_assessment_minor'];reduced=basis['regime']!='above_upper_limit'
        else:total_base=employee_base=gross;reduced=False
        branch_bases={}
        for key,cap,rate in (('health_general',caps['health_minor'],Decimal('7.300')),
                ('health_additional',caps['health_minor'],Decimal(p['health_additional_percent'])/2),
                ('pension',caps['pension_minor'],Decimal('9.300')),('unemployment',caps['unemployment_minor'],Decimal('1.300'))):
            total,own=min(total_base,cap),min(employee_base,cap);branch_bases[key]=dict(total_minor=total,employee_minor=own)
            employee[key]=_portion(own,rate)
            employer[key]=2*_portion(total,rate)-employee[key] if reduced else _portion(total,rate)
        care_total,care_own=min(total_base,caps['care_minor']),min(employee_base,caps['care_minor'])
        branch_bases['care']=dict(total_minor=care_total,employee_minor=care_own)
        employee['care'],employer['care'],care=care_contributions(care_total,care_own,saxony=p['federal_state']=='SN',
            surcharge=surcharge,discount_count=discounts,reduced=reduced)
        levy_base=min(total_base,caps['pension_minor']);flat_tax=0
        tax_period=plan['tax_periods'][0]
        tax=calculate_period_tax(gross_minor=gross,lzz=tax_period['lzz'],tax_days=tax_period['tax_days'],
            allowance_monthly_minor=p['tax_allowance_monthly_minor'],addition_monthly_minor=p['tax_addition_monthly_minor'],
            tax_class=p['tax_class'],children_half_units=p['tax_children_half_units'],
            additional_health_percent=format(Decimal(p['health_additional_percent']),'.2f'),
            saxony=p['federal_state']=='SN',childless_surcharge=surcharge,care_child_discounts=discounts,church_member=p['church_tax']!='none')
        church=tax['totals']['BK']*int(result['tax_parameters']['church_tax_percent'])//100
        employee_tax=tax['totals']['LSTLZZ']+tax['totals']['SOLZLZZ']+church
        result.update(scope='regular_transition_period' if transition else 'regular_standard_period',
            pap_version=tax['version'],pap_provenance_sha256=tax['provenance_sha256'],
            tax_method='individual_2026_verified_period_pap',individual_wage_tax_minor=tax['totals']['LSTLZZ'],
            solidarity_minor=tax['totals']['SOLZLZZ'],church_tax_minor=church,
            care_childless_surcharge=surcharge,care_discount_children=discounts)
        result['period_details'].update(tax_calculation=tax,branch_bases=branch_bases,care_adjustments=care)
        if transition:
            result['period_details']['transition']=dict(basis,ratio=social['transition_ratio'],branch_bases=branch_bases,
                levy_assessment_minor=levy_base,regular_monthly_gross_minor=p['transition_assessment']['regular_monthly_gross_minor'])
    levies=dict(u1=_portion(levy_base,p['u1_percent']),u2=_portion(levy_base,p['u2_percent']),insolvency=_portion(levy_base,'0.150'))
    net=gross-sum(employee.values())-employee_tax
    result.update(payroll_calculation_complete=True,social_contributions_available=True,
        employee_contributions=employee,employer_contributions=employer,
        employee_social_total_minor=sum(employee.values()),employer_social_total_minor=sum(employer.values()),
        employer_levies=levies,employer_flat_tax_minor=flat_tax,employee_tax_minor=employee_tax,
        employer_total_excluding_accident_insurance_minor=gross+sum(employer.values())+sum(levies.values())+flat_tax,
        net_minor=net,payout_minor=max(0,net),employee_additional_payment_minor=max(0,-net))
    return result

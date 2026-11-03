"""Explicit v5 composition of immutable periods, entitlements and travel.

This new dispatcher never upgrades a stored v4 plan. Database/source authority
belongs to business_payroll_calculation_cases; every amount here is derived
from its frozen source objects. Unsupported combinations keep a null net.
"""
from datetime import timedelta
from decimal import Decimal
import hashlib

from core import Problem,canonical
from payroll_de_2026 import normalize_profile,integer,day,month_range,_portion,_age_completed,TAX_PROFILE_FIELDS
from payroll_periods_2026 import _profile_blockers,_transition_bases
from payroll_pap_periods_2026 import calculate_period_tax,DAILY_PAP_SHA256
from payroll_transition_2026 import care_contributions
from payroll_segments_2026 import COMPOSITE_RULE_VERSION,reference,social_intervals,_round_ratio
from payroll_claims_composition_2026 import compose_claims
from payroll_travel_tax_2026 import calculate_flat_travel_tax,RULES_SHA256 as TRAVEL_TAX_RULES_SHA256

SOURCE_CONTRACT_VERSION=1
CALCULATION_RULE_VERSION=COMPOSITE_RULE_VERSION
SCOPES=('regular_standard_segments','regular_transition_segments','commercial_minijob_segments_flat_tax')
SOCIAL_FIELDS=frozenset(('employment_kind','date_of_birth','federal_state','health_insurance','health_fund',
    'health_additional_percent','has_children','pv_children_under_25','u1_required','u1_percent','u2_percent',
    'minijob_rv_exempt','pension_other_compulsory','minijob_tax'))
TAX_FIELDS=frozenset(('tax_class','tax_children_half_units','church_tax','tax_allowance_monthly_minor','tax_addition_monthly_minor'))
EVENT_FIELDS={'tax_features_change':TAX_FIELDS,'wage_forecast_change':frozenset(('regular_annual_gross_minor','transition_assessment')),
    'health_fund_change':frozenset(('health_fund','health_additional_percent','u1_percent','u2_percent')),
    'social_rate_change':SOCIAL_FIELDS-{'employment_kind'},'employment_status_change':SOCIAL_FIELDS|TAX_FIELDS|{'regular_annual_gross_minor','transition_assessment'},
    'data_correction':frozenset()}
RULES=dict(version=CALCULATION_RULE_VERSION,source_contract_version=SOURCE_CONTRACT_VERSION,
    pap_component_sha256=DAILY_PAP_SHA256,travel_tax_component_sha256=TRAVEL_TAX_RULES_SHA256,claims_component='de_2026_claims_composition_v1',
    segments_component='de_2026_segments_component_v1',tax_features='END_OF_ACTUAL_EMPLOYMENT_LZZ',
    unpaid_tax_period='EMPLOYMENT_CONTINUES_NO_AUTOMATIC_LZZ_REDUCTION',
    social_period='EVIDENCED_EMPLOYMENT_AND_ACTUAL_7_3_CONTINUATION',
    travel_payment='TAXABLE_CASH_IN_PAYROLL_TAX_FREE_EXTERNAL_NON_CASH_NET_DEDUCTION',
    historical_dispatch='EXPLICIT_RULE_AND_SOURCE_CONTRACT_ONLY')
RULES_SHA256=hashlib.sha256(canonical(RULES).encode()).hexdigest()


def _sha(value):return hashlib.sha256(canonical(value).encode()).hexdigest()


def _dates(start,end):
    return [(day(start)+timedelta(days=index)).isoformat() for index in range((day(end)-day(start)).days+1)]


def _inside(date,period):return period['start']<=date<=period['end']


def _profile_on(profiles,date):
    applicable=[value for value in profiles if value['profile']['effective_from']<=date]
    return applicable[-1] if applicable else None


def _insured_episodes(episodes,continuation):
    excluded={value['date'] for value in continuation if not value['employment_for_contributions_continues']}
    output=[]
    for episode in episodes:
        current=[]
        def append():
            if current:output.append(dict(start=current[0],end=current[-1],calendar_days=len(current),employment_terms_ref=episode['employment_terms_ref']))
        for date in _dates(episode['start'],episode['end']):
            if date in excluded:append();current=[]
            else:current.append(date)
        append()
    return output


def _travel_totals(sources,employee_id,month):
    keys=('tax_free_external_minor','flat_taxable_payroll_minor','individual_taxable_payroll_minor','benefit_in_kind_non_cash_minor')
    result=dict.fromkeys(keys,0);result['letter_m']=False;seen=set();allocations=set()
    for value in sources:
        if (value['kind']!='travel_allowances' or type(value['schema_version']) is not int or value['schema_version']!=1 or value['employee_id']!=employee_id
                or value['month']!=month or value['settlement_ref']['id'] in seen
                or _sha({key:item for key,item in value.items() if key!='source_hash'})!=value['source_hash']):
            raise Problem(409,'Reise-Lohnquelle ist doppelt, verändert oder gehört nicht zur Person und zum Monat.')
        seen.add(value['settlement_ref']['id'])
        sums=dict(flat_taxable_payroll=0,individual_taxable_payroll=0,benefit_in_kind_non_cash=0)
        for allocation in value['allocations']:
            if allocation['key'] in allocations or allocation['month']!=month or allocation['kind'] not in sums:
                raise Problem(409,'Reisebetragszuordnung muss eindeutig zum Lohnmonat gehören.')
            allocations.add(allocation['key']);sums[allocation['kind']]+=integer(allocation['amount_minor'],1)
        for key in sums:
            if sums[key]!=value[key+'_minor']:raise Problem(409,'Reisebeträge widersprechen ihren Originalzuordnungen.')
        for key in keys:result[key]+=integer(value[key])
        if type(value['letter_m']) is not bool:raise Problem(400,'M-Merkmal ausdrücklich angeben.')
        result['letter_m']|=value['letter_m']
    return result


def build_calculation_plan(snapshot,*,rule_version,source_contract_version):
    if rule_version!=CALCULATION_RULE_VERSION or type(source_contract_version) is not int or source_contract_version!=SOURCE_CONTRACT_VERSION:
        raise Problem(400,'Unbekannte Gesamtregel oder Quellenvertragsversion; kein automatischer Versionswechsel.')
    fields={'schema_version','source_contract_version','rule_version','employee_id','month','period_case','employment_terms',
        'profiles','identities','segment_events','thirty_day_rule','entitlements','travel_sources','flat_travel_tax','source_files'}
    if (not isinstance(snapshot,dict) or set(snapshot)!=fields or type(snapshot['schema_version']) is not int or snapshot['schema_version']!=1
            or type(snapshot['source_contract_version']) is not int or snapshot['source_contract_version']!=source_contract_version or snapshot['rule_version']!=rule_version):
        raise Problem(400,'Vollständigen explizit versionierten Gesamtquellenstand angeben.')
    s=snapshot;month=s['month'];employee_id=s['employee_id'];first,last=month_range(month)
    base=s['period_case'];old=base['sources'];prep=old['preparation']
    if base['status']!='active' or base['kind']!='period_case' or base['employee_id']!=employee_id or base['details']['month']!=month:
        raise Problem(400,'Der vollständige P2-Basisfall gehört nicht zu dieser Abrechnung.')
    claims=compose_claims(month,s['employment_terms'],prep['snapshot']['agreements'],prep,s['entitlements'],
        schedule=old['work_schedule'],thirty_day_rule=s['thirty_day_rule'])
    blockers=list(claims['blockers'])
    def block(code,message):
        if not any(value['code']==code for value in blockers):blockers.append(dict(code=code,message=message))
    for decision in base['details']['entitlement_decisions']:
        dates=_dates(decision['from'],decision['to']);kind=decision['kind']
        if kind in ('sickness_continued_pay','sickness_after_entitlement'):
            covered={date for fact in s['entitlements'] if fact['kind']=='sickness_history'
                for episode in fact['plan']['episodes'] for date in _dates(episode['from_date'],episode['to_date'])}
            if any(date not in covered for date in dates):block('declared_sickness_entitlement_missing','Die ausdrückliche P2-Krankheitsentscheidung benötigt ihre tatsächlichen Anspruchs-/Vorzeitenfakten.')
        if kind in ('unpaid_leave','sickness_after_entitlement') and any(date not in claims['unpaid_dates'] for date in dates):
            block('declared_unpaid_entitlement_missing','Die ausdrückliche unbezahlte P2-Entscheidung benötigt den wirklichen fehlenden Entgeltanspruch und SV-Fortbestand.')
    if first.year!=2026:block('year_not_supported','Diese Gesamtregel gilt ausschließlich für 2026.')
    profiles=sorted(s['profiles'],key=lambda value:(value['profile']['effective_from'],value['id']))
    if (not profiles or len({value['id'] for value in profiles})!=len(profiles)
            or len({value['profile']['effective_from'] for value in profiles})!=len(profiles)):
        raise Problem(400,'Eindeutige tatsächliche Profilfassungen erforderlich.')
    for value in profiles:
        if value['kind']!='profile' or value['employee_id']!=employee_id or normalize_profile(value['profile'])!=value['profile']:
            raise Problem(400,'Profilquelle gehört nicht zur Person oder ist nicht normalisiert.')
    episodes=claims['employment_intervals'];events={}
    for event in s['segment_events']:
        fields={'kind','effective_from','before_profile_ref','after_profile_ref','source_file_ids','reason'}
        if set(event)!=fields or event['kind'] not in EVENT_FIELDS or event['effective_from'] in events:
            raise Problem(400,'Eindeutige belegte Profilereignisse mit bekannter fachlicher Bedeutung angeben.')
        before=next((value for value in profiles if reference(value)==event['before_profile_ref']),None)
        after=next((value for value in profiles if reference(value)==event['after_profile_ref']),None)
        if (before is None or after is None or profiles.index(after)!=profiles.index(before)+1
                or after['profile']['effective_from']!=event['effective_from'] or not event['source_file_ids'] or not event['reason']):
            raise Problem(400,'Ereignis muss unmittelbar benachbarte tatsächliche Profilfassungen und Originale binden.')
        changes={key for key in set(before['profile'])|set(after['profile']) if before['profile'].get(key)!=after['profile'].get(key)}-{'effective_from','verification_note'}
        if not changes.issubset(EVENT_FIELDS[event['kind']]):
            raise Problem(400,'Ereignisbezeichnung entspricht nicht den tatsächlichen Profiländerungen.')
        if not any(episode['start']<event['effective_from']<=episode['end'] for episode in episodes):
            raise Problem(400,'Untermonatiges Ereignis liegt nicht innerhalb einer tatsächlichen Beschäftigungsepisode.')
        events[event['effective_from']]=event
    identity_intervals=[];tax_periods=[]
    for episode in episodes:
        start_profile=_profile_on(profiles,episode['start'])
        if start_profile is None:block('profile_not_effective','Zum Beschäftigungsbeginn fehlt ein wirksames Profil.');continue
        selected=[start_profile]+[value for value in profiles if episode['start']<value['profile']['effective_from']<=episode['end']]
        for index,profile in enumerate(selected):
            p=profile['profile'];start=max(episode['start'],p['effective_from'])
            end=(day(selected[index+1]['profile']['effective_from'])-timedelta(days=1)).isoformat() if index+1<len(selected) else episode['end']
            if index and p['effective_from'] not in events:block('profile_event_missing','Untermonatige Profiländerung benötigt ihren belegten fachlichen Grund.')
            if index and any(p.get(key)!=selected[index-1]['profile'].get(key) for key in SOCIAL_FIELDS):
                block('social_profile_transition_requires_rule','Dieser untermonatige Versicherungs-/Kassen-/Beitragssatzwechsel benötigt seinen nachgewiesenen SV-Zuordnungszweig.')
            for issue in _profile_blockers(p,None,day(start),day(end)):
                code=issue['code']
                if code in ('special_case:unpaid_absence','special_case:sick_pay') and s['entitlements']:continue
                if code=='special_case:benefit_in_kind' and s['travel_sources']:continue
                block(code,issue['message'])
            applicable=[]
            for identity in s['identities']:
                d=identity['details']
                if identity['kind']!='identity' or identity['employee_id']!=employee_id:raise Problem(400,'Identitätsnachweis gehört nicht zur Person.')
                if (d['profile_id']==profile['id'] and d['profile_revision']==profile['revision']
                        and d['valid_from']<=start<=end<=d['valid_to'] and d['employment_from']<=start
                        and (d['employment_to'] is None or d['employment_to']>=end)):applicable.append(identity)
            if len(applicable)!=1:block('identity_interval_missing','Jede tatsächliche Profilgültigkeit benötigt genau einen passenden Identitäts-/Steuernachweis.')
            identity_intervals.append(dict(start=start,end=end,profile_ref=reference(profile),identity_ref=reference(applicable[0]) if len(applicable)==1 else None))
        final=selected[-1];p=final['profile'];full=episode['start']==first.isoformat() and episode['end']==last.isoformat()
        if p['employment_kind']=='regular' and not TAX_PROFILE_FIELDS.issubset(p):block('explicit_tax_features_missing','Steuerfreibeträge und Hinzurechnungsbeträge müssen ausdrücklich belegt sein.')
        tax_periods.append(dict(start=episode['start'],end=episode['end'],lzz=2 if full else 4,
            tax_days=30 if full else episode['calendar_days'],profile_ref=reference(final),gross_minor=0))
    insured=_insured_episodes(episodes,claims['social_continuation']);social=social_intervals(month,insured,[])
    for period in social:
        profile=_profile_on(profiles,period['start'])
        period.update(profile_ref=reference(profile) if profile else None,gross_minor=0,earning_indexes=[],transition_ratio=None,
            minimum_pension_basis_minor=_round_ratio(17500,period['days'],30))
    earnings=[];work={value['date']:value['net_seconds'] for value in prep['snapshot']['approved_days']}
    for value in claims['base_earnings']:
        dates=[date for date in _dates(value['start'],value['end']) if date not in value['unpaid_dates']
            and (value['pay_basis']!='hourly' or work.get(date,0))]
        earnings.append(dict(value,claim_dates=dates))
    for value in claims['absence_earnings']:earnings.append(dict(value,claim_dates=value['days']))
    for index,earning in enumerate(earnings):
        amount=earning['gross_minor']
        if amount is None or amount==0:continue
        dates=earning['claim_dates'];tax_indexes={index for index,period in enumerate(tax_periods) if any(_inside(date,period) for date in dates)}
        social_indexes={index for index,period in enumerate(social) if any(_inside(date,period) for date in dates)}
        if len(tax_indexes)!=1 or any(not any(_inside(date,period) for period in tax_periods) for date in dates):
            block('earning_tax_allocation_required','Ein Anspruch über mehrere tatsächliche Steuerperioden benötigt seine exakte datierte Zuordnung.')
        else:tax_periods[next(iter(tax_indexes))]['gross_minor']+=amount
        if len(social_indexes)!=1 or any(not any(_inside(date,period) for period in social) for date in dates):
            block('earning_social_allocation_required','Ein Anspruch über mehrere SV-Perioden benötigt seine exakte datierte Zuordnung.')
        else:
            period=social[next(iter(social_indexes))];period['gross_minor']+=amount;period['earning_indexes'].append(index)
    travel=_travel_totals(s['travel_sources'],employee_id,month)
    individual=travel['individual_taxable_payroll_minor']+travel['benefit_in_kind_non_cash_minor']
    if individual:
        if len(tax_periods)!=1 or len(social)!=1:block('travel_period_allocation_required','Reiselohn in mehreren Beschäftigungs-/SV-Perioden benötigt seine tatsächliche Anspruchszuordnung.')
        else:tax_periods[0]['gross_minor']+=individual;social[0]['gross_minor']+=individual
    flat=travel['flat_taxable_payroll_minor']
    flat_calculation=None
    if flat and s['flat_travel_tax'] is None:block('flat_travel_tax_policy_missing','Die 25%-Reise-Pauschalierung benötigt die belegte gemeinsame Steuerentscheidung und zeitgerechte Erfassung.')
    if s['flat_travel_tax'] is not None:
        component=s['flat_travel_tax']
        if set(component)!={'parameters','calculation','recording_context','policy','membership_identity','source_files'}:
            raise Problem(400,'Pauschalsteuerquelle muss tatsächliche Eingangsbelege, geplanten Abschlusskontext und eingefrorene Rechnung enthalten.')
        parameters=component['parameters'];evidence=parameters['evidence']
        if (component['recording_context']!={'planned_recording_on':evidence['taxation_recorded_on'],'actual_recorded':False}
                or reference(component['policy'])!=evidence['policy_ref']):
            raise Problem(409,'Geplante Pauschalsteuerquelle darf keine bereits erfolgte Erfassung behaupten.')
        expected=sorted([value['settlement_ref'] for value in s['travel_sources'] if value['flat_taxable_payroll_minor']],key=lambda value:value['id'])
        if (not flat or evidence['payroll_month']!=month or evidence['eligible_limit_minor']!=flat
                or sorted(evidence['eligible_source_refs'],key=lambda value:value['id'])!=expected):
            raise Problem(409,'Pauschalsteuergrenze und Quellen müssen aus den tatsächlichen Reisezuordnungen stammen.')
        flat_calculation=calculate_flat_travel_tax(flat,**parameters)
        if flat_calculation!=component['calculation']:raise Problem(409,'Pauschalsteuerquelle ist nicht unverändert nachrechenbar.')
        for issue in flat_calculation['blockers']:block(issue['code'],issue['message'])
        if flat_calculation['social_gross_minor']:
            if len(social)!=1:block('travel_period_allocation_required','SV-pflichtige Reise-Pauschalbeträge benötigen die konkrete Versicherungsperiodenzuordnung.')
            else:social[0]['gross_minor']+=flat_calculation['social_gross_minor']
    kinds={value['profile']['employment_kind'] for value in profiles}
    if len(kinds)!=1:block('mixed_employment_status_requires_rule','Minijob und reguläre Beschäftigung benötigen ihre ausdrücklich belegte Status-/Steuerabgrenzung.')
    if kinds=={'minijob'} and claims['gross_minor'] is not None and claims['gross_minor']>60300:
        block('minijob_limit_exceeded','Mehrere Beschäftigungsabschnitte dürfen die belegte Monats-Geringfügigkeitsgrenze nicht mehrfach verbrauchen.')
    for period in social:
        profile=next((value for value in profiles if reference(value)==period['profile_ref']),None)
        if profile is None:continue
        p=profile['profile'];indexes=period['earning_indexes'];relevant=[earnings[index] for index in indexes]
        if p['employment_kind']=='minijob':
            if period['gross_minor']>60300:block('minijob_limit_exceeded','Die tatsächliche Monatsgrenze benötigt die belegte Geringfügigkeitsentscheidung; keine automatische Umklassifizierung.')
            if s['travel_sources']:block('minijob_travel_requires_rule','Reiselohn beim Minijob benötigt die belegte zusätzliche Entgelt-/Pauschalsteuerabgrenzung.')
            if not period['gross_minor']:block('zero_minijob_requires_rule','Minijob ohne Entgelt benötigt die gesonderte Mindestbeitrags-/Fortbestandsentscheidung.')
        if 'transition_assessment' in p:
            if claims['unpaid_dates'] or claims['absence_earnings'] or s['travel_sources']:
                block('transition_entitlement_equivalence_required','Übergangsbereich mit Ausfall-/Reiseentgelt benötigt seine nachgewiesene Monatsäquivalenz.')
            if period['full_month']:period['transition_ratio']=dict(numerator=30,denominator=30)
            elif len(relevant)==1 and relevant[0].get('pay_basis')=='monthly':
                period['transition_ratio']={key:relevant[0][key] for key in ('numerator','denominator')}
            elif relevant and all(value.get('pay_basis')=='hourly' for value in relevant):period['transition_ratio']=dict(numerator=period['days'],denominator=30)
            else:block('transition_segment_equivalence_required','Mehrere Teilentgelte benötigen ihre ausdrückliche gemeinsame Monatsäquivalenz.')
    gross=None if claims['gross_minor'] is None else claims['gross_minor']+individual+flat
    result=dict(schema_version=1,rule_version=rule_version,source_contract_version=source_contract_version,rules_sha256=RULES_SHA256,
        employee_id=employee_id,month=month,source_snapshot_hash=_sha(s),claims_component_hash=claims['component_hash'],
        employment_intervals=episodes,identity_intervals=identity_intervals,earnings=earnings,tax_periods=tax_periods,social_periods=social,
        entitlement_sources=claims['entitlement_sources'],unpaid_dates=claims['unpaid_dates'],social_continuation=claims['social_continuation'],
        travel=travel,flat_travel_tax=flat_calculation,travel_source_hashes=[value['source_hash'] for value in s['travel_sources']],gross_minor=gross,
        selected_profile_ref=reference(profiles[-1]),blockers=sorted(blockers,key=lambda value:value['code']))
    return dict(result,plan_hash=_sha(result),can_confirm=True,can_calculate=not blockers)


def calculate_calculation_source(snapshot,*,rule_version,source_contract_version):
    plan=build_calculation_plan(snapshot,rule_version=rule_version,source_contract_version=source_contract_version)
    gross=plan['gross_minor'];profiles={canonical(reference(value)):value['profile'] for value in snapshot['profiles']}
    result=dict(rule_version=rule_version,rules_sha256=RULES_SHA256,source_contract_version=source_contract_version,
        month=plan['month'],currency='EUR',gross_minor=gross,scope='unsupported',payroll_calculation_complete=False,
        social_contributions_available=False,employee_contributions=None,employer_contributions=None,
        employee_social_total_minor=None,employer_social_total_minor=None,employer_levies=None,employer_flat_tax_minor=None,
        employer_total_excluding_accident_insurance_minor=None,accident_insurance_included=False,
        individual_wage_tax_minor=None,solidarity_minor=None,church_tax_minor=None,employee_tax_minor=None,
        net_minor=None,net_deductions_minor=None,payout_minor=None,employee_additional_payment_minor=None,
        blockers=plan['blockers'],statutory_report_status='not_transmitted',official_system_approval=False,
        travel_expenses_included_in_net=bool(plan['travel']['individual_taxable_payroll_minor'] or plan['travel']['flat_taxable_payroll_minor']),
        period_details={key:plan[key] for key in ('plan_hash','source_snapshot_hash','employment_intervals','identity_intervals','earnings',
            'tax_periods','social_periods','entitlement_sources','unpaid_dates','social_continuation','travel','flat_travel_tax','travel_source_hashes')})
    if plan['blockers']:return result
    keys=('health_general','health_additional','pension','unemployment','care')
    employee=dict.fromkeys(keys,0);employer=dict.fromkeys(keys,0);levies=dict(u1=0,u2=0,insolvency=0)
    flat_tax=0;assessments=[];mini=all(p['employment_kind']=='minijob' for p in profiles.values());transition=False
    for period in plan['social_periods']:
        p=profiles[canonical(period['profile_ref'])];amount=period['gross_minor'];caps=period['caps'];born=day(p['date_of_birth'])
        own=dict.fromkeys(keys,0);firm=dict.fromkeys(keys,0);branch={};care=None;basis=None
        surcharge=not p['has_children'] and _age_completed(born,23).strftime('%Y-%m')<plan['month']
        discounts=max(0,min(5,p['pv_children_under_25'])-1)
        if mini:
            firm['health_general']=_portion(amount,'13.000') if p['health_insurance']!='private' else 0
            firm['pension']=_portion(amount,'15.000')
            if not p['minijob_rv_exempt']:
                minimum=period['minimum_pension_basis_minor']
                own['pension']=_portion(minimum,'18.600')-firm['pension'] if amount<minimum and not p['pension_other_compulsory'] else _portion(amount,'3.600')
            levy_base=amount;flat_tax+=_portion(amount,'2.000')
        else:
            transition|='transition_assessment' in p
            if 'transition_assessment' in p:
                ratio=period['transition_ratio'];basis=_transition_bases(amount,ratio['numerator'],ratio['denominator'])
                total_base=basis['total_assessment_minor'];employee_base=basis['employee_assessment_minor'];reduced=basis['regime']!='above_upper_limit'
            else:total_base=employee_base=amount;reduced=False
            for key,cap,rate in (('health_general',caps['health_minor'],Decimal('7.300')),
                    ('health_additional',caps['health_minor'],Decimal(p['health_additional_percent'])/2),
                    ('pension',caps['pension_minor'],Decimal('9.300')),('unemployment',caps['unemployment_minor'],Decimal('1.300'))):
                total,own_base=min(total_base,cap),min(employee_base,cap);branch[key]=dict(total_minor=total,employee_minor=own_base)
                own[key]=_portion(own_base,rate);firm[key]=2*_portion(total,rate)-own[key] if reduced else _portion(total,rate)
            total,own_base=min(total_base,caps['care_minor']),min(employee_base,caps['care_minor'])
            branch['care']=dict(total_minor=total,employee_minor=own_base)
            own['care'],firm['care'],care=care_contributions(total,own_base,saxony=p['federal_state']=='SN',surcharge=surcharge,discount_count=discounts,reduced=reduced)
            levy_base=min(total_base,caps['pension_minor'])
        period_levies=dict(u1=_portion(levy_base,p['u1_percent']),u2=_portion(levy_base,p['u2_percent']),insolvency=_portion(levy_base,'0.150'))
        for key in keys:employee[key]+=own[key];employer[key]+=firm[key]
        for key in levies:levies[key]+=period_levies[key]
        assessments.append(dict(period=period,branch_bases=branch,transition=basis,care_adjustments=care,employee_contributions=own,
            employer_contributions=firm,employer_levies=period_levies,levy_assessment_minor=levy_base))
    taxes=[];wage_tax=solidarity=church=0
    if not mini:
        for period in plan['tax_periods']:
            p=profiles[canonical(period['profile_ref'])];born=day(p['date_of_birth'])
            surcharge=not p['has_children'] and _age_completed(born,23).strftime('%Y-%m')<plan['month']
            discounts=max(0,min(5,p['pv_children_under_25'])-1)
            tax=calculate_period_tax(gross_minor=period['gross_minor'],lzz=period['lzz'],tax_days=period['tax_days'],
                allowance_monthly_minor=p['tax_allowance_monthly_minor'],addition_monthly_minor=p['tax_addition_monthly_minor'],
                tax_class=p['tax_class'],children_half_units=p['tax_children_half_units'],additional_health_percent=format(Decimal(p['health_additional_percent']),'.2f'),
                saxony=p['federal_state']=='SN',childless_surcharge=surcharge,care_child_discounts=discounts,church_member=p['church_tax']!='none')
            rate=0 if p['church_tax']=='none' else 8 if p['federal_state'] in ('BW','BY') else 9
            period_church=tax['totals']['BK']*rate//100
            wage_tax+=tax['totals']['LSTLZZ'];solidarity+=tax['totals']['SOLZLZZ'];church+=period_church
            taxes.append(dict(period=period,calculation=tax,church_tax_percent=rate,church_tax_minor=period_church))
        if taxes:result.update(pap_version=taxes[0]['calculation']['version'],pap_provenance_sha256=taxes[0]['calculation']['provenance_sha256'])
    flat_result=plan['flat_travel_tax'];shifted_tax=flat_result['employee_tax_minor'] if flat_result else 0
    if flat_result:flat_tax+=flat_result['statutory_employer_due_minor']
    employee_tax=wage_tax+solidarity+church;net=gross-sum(employee.values())-employee_tax
    deductions=plan['travel']['benefit_in_kind_non_cash_minor']+shifted_tax;cash_net=net-deductions
    result.update(scope=SCOPES[2] if mini else SCOPES[1] if transition else SCOPES[0],payroll_calculation_complete=True,
        social_contributions_available=True,employee_contributions=employee,employer_contributions=employer,
        employee_social_total_minor=sum(employee.values()),employer_social_total_minor=sum(employer.values()),
        employer_levies=levies,employer_flat_tax_minor=flat_tax,
        employer_total_excluding_accident_insurance_minor=gross+sum(employer.values())+sum(levies.values())+flat_tax-shifted_tax,
        individual_wage_tax_minor=0 if mini else wage_tax,solidarity_minor=0 if mini else solidarity,church_tax_minor=0 if mini else church,
        employee_tax_minor=employee_tax,net_minor=net,net_deductions_minor=deductions,payout_minor=max(0,cash_net),employee_additional_payment_minor=max(0,-cash_net),
        tax_method='flat_2_percent_employer_including_church_and_solidarity' if mini else 'individual_2026_verified_segments_pap')
    result['period_details'].update(social_assessments=assessments,tax_calculations=taxes)
    return result

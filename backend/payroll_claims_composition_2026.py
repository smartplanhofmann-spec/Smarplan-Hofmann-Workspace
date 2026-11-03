"""Compose evidenced P4 entitlements with real P3b work/contract earnings.

This isolated v5 component does not change old preparations or project time.
Private case services validate original-source existence; this component checks
the frozen arithmetic, exact contract links and non-overlapping wage claims.
"""
from datetime import timedelta
import hashlib

from core import Problem,canonical
from payroll_de_2026 import day,month_range
from payroll_entitlement_dispatch import build_entitlement_plan
from payroll_segments_2026 import contractual_earnings,reference,_round_ratio


def _dates(first,last):
    return [(first+timedelta(days=index)).isoformat() for index in range(max(0,(last-first).days+1))]


def compose_claims(month,terms,agreements,preparation,entitlements,*,schedule=None,thirty_day_rule=None):
    first,last=month_range(month);employee_ids={value['employee_id'] for value in terms}
    if len(employee_ids)!=1 or preparation['employee_id'] not in employee_ids or preparation['month']!=month:
        raise Problem(400,'Anspruchskomposition benötigt dieselbe Person und Monatsvorbereitung.')
    if not isinstance(entitlements,list):raise Problem(400,'Anspruchsfakten als vollständige Liste angeben.')
    snapshot=preparation['snapshot'];work={value['date']:value['net_seconds'] for value in snapshot['approved_days']}
    ordered=sorted(agreements,key=lambda value:(value['effective_from'],value['id']))
    def agreement(date):
        available=[value for value in ordered if value['effective_from']<=date]
        return available[-1] if available else None
    blockers=[]
    def block(code,message):
        if not any(value['code']==code for value in blockers):blockers.append(dict(code=code,message=message))
    facts=[];seen=set();sickness={};unpaid=set();continuation={};money_days={};groups={};vacations=[]
    term_refs=[reference(value) for value in terms]
    for fact in entitlements:
        if fact['id'] in seen or fact['employee_id'] not in employee_ids or fact['status']!='active':
            raise Problem(400,'Anspruchsfakten müssen eindeutig, aktiv und derselben Person zugeordnet sein.')
        seen.add(fact['id'])
        if fact['details']['employment_terms_ref'] not in term_refs:
            block('entitlement_employment_mismatch','Anspruchsfakt gehört zu einer anderen Beschäftigungsfassung.')
        plan=build_entitlement_plan(fact['sources'],fact['plan']['rule_version'])
        if plan!=fact['plan']:raise Problem(409,'Eingefrorener Anspruchsplan ist nicht identisch nachrechenbar.')
        facts.append(dict(reference=reference(fact),kind=fact['kind'],plan_hash=plan['plan_hash']))
        if fact['kind']=='sickness_history':
            phased=plan['rule_version'] in ('de_2026_sickness_phases_v3','de_2026_sickness_start_v4')
            for original in fact['details']['input']['episodes']:
                if phased and original['onset'] in ('during_existing_au','before_employment'):continue
                date=original['from']
                if first.isoformat()<=date<=last.isoformat():
                    scheduled=next((value['scheduled_seconds'] for value in (schedule or {}).get('details',{}).get('days',[]) if value['date']==date),None)
                    actual=work.get(date,0)
                    if scheduled is None:
                        block('sickness_onset_schedule_missing','Der tatsächliche AU-Beginn benötigt den gebundenen Tages-Sollplan.')
                    elif (original['onset']=='during_work' and not 0<actual<=scheduled
                            or original['onset']=='before_work' and (actual or not scheduled)
                            or original['onset']=='non_workday' and (actual or scheduled)):
                        block('sickness_onset_work_mismatch','Belegter AU-Beginn widerspricht tatsächlicher Arbeit oder Sollplan; die 42-Tage-Grenze darf nicht verschoben werden.')
            for episode in plan['phases'] if phased else plan['episodes']:
                begin,end=max(first,day(episode['from_date'])),min(last,day(episode['to_date']))
                for date in _dates(begin,end):
                    if date in sickness:block('overlapping_sickness_decisions','Mehrere Krankheitsnachweise beurteilen denselben Kalendertag.')
                    paid=(episode['entitled'] or episode['first_day_remaining_regular_wage']) if phased else (
                        (episode['entitlement_from'] is not None and episode['entitlement_from']<=date<=episode['entitlement_to'])
                        or episode['first_day_remaining_regular_wage']==date)
                    sickness[date]=dict(entitled=paid,source_ref=reference(fact))
                    if not paid:unpaid.add(date)
        elif fact['kind']=='unpaid_continuation':
            for interval in plan['intervals']:
                begin,end=max(first,day(interval['from'])),min(last,day(interval['to']))
                for date in _dates(begin,end):
                    if date in continuation:block('overlapping_unpaid_decisions','Mehrere Fortbestandsnachweise beurteilen denselben Kalendertag.')
                    unpaid.add(date);continuation[date]=dict(employment_for_contributions_continues=interval['employment_for_contributions_continues'],
                        basis=interval['basis'],source_ref=reference(fact))
        elif fact['kind']=='regular_absence':
            rate=fact['details']['input']['hourly_rate_minor'];kind=plan['entitlement_kind']
            for item in plan['days']:
                date=item['date']
                if not first.isoformat()<=date<=last.isoformat():continue
                if date in money_days:block('duplicate_absence_pay','Mehrere Ausfallvergütungen belegen denselben Tag.')
                money_days[date]=dict(kind=kind,source_ref=reference(fact),paid_seconds=item['paid_absence_seconds'])
                selected=agreement(date)
                if selected is None or selected['pay_basis']!='hourly' or selected['amount_minor']!=rate:
                    block('absence_wage_mismatch','Ausfallvergütung darf nur die tatsächliche Stundenvereinbarung ergänzen; kein zusätzlicher Monatslohn.');continue
                if item['actual_work_seconds']!=work.get(date,0):block('absence_work_mismatch','Ausfallvergütung und tatsächliche freigegebene Arbeit widersprechen sich.')
                if schedule is None:block('absence_schedule_missing','Für Ausfallstunden fehlt der konkret gebundene Monatsarbeitsplan.')
                else:
                    scheduled=next((value for value in schedule['details']['days'] if value['date']==date),None)
                    if scheduled is None or item['paid_absence_seconds']+item['actual_work_seconds']>scheduled['scheduled_seconds']:
                        block('absence_exceeds_schedule','Tatsächliche Arbeit und Ausfallstunden überschreiten den belegten Sollplan.')
                key=canonical([reference(selected),rate,kind])
                group=groups.setdefault(key,dict(kind=kind,agreement_ref=reference(selected),hourly_rate_minor=rate,paid_absence_seconds=0,days=[],source_refs=[]))
                group['paid_absence_seconds']+=item['paid_absence_seconds'];group['days'].append(date)
                if reference(fact) not in group['source_refs']:group['source_refs'].append(reference(fact))
        elif fact['kind']=='vacation_reference':
            dates=[date for date in plan['vacation_days'] if first.isoformat()<=date<=last.isoformat()]
            for date in dates:
                if date in money_days:block('duplicate_absence_pay','Urlaub und andere Vergütung belegen denselben Ausfalltag.')
                money_days[date]=dict(kind='vacation',source_ref=reference(fact),paid_seconds=None)
                selected=agreement(date)
                if selected is None or selected['pay_basis']!='hourly':block('vacation_double_monthly_salary','Eine Stundenlohn-Urlaubsreferenz darf nicht zusätzlich zum Monatsentgelt gezahlt werden.')
                if work.get(date,0):block('work_on_vacation_day','Der bezahlte Urlaubstag enthält tatsächliche freigegebene Arbeit.')
            if dates:
                average=plan['workday_average'];in_kind_daily=fact['details']['input']['in_kind_daily_minor']
                vacations.append(dict(kind='vacation',days=dates,source_refs=[reference(fact)],
                    workday_average=average,in_kind_cash_compensation_minor=in_kind_daily*len(dates),
                    gross_minor=_round_ratio(average['numerator'],len(dates),average['denominator'])+in_kind_daily*len(dates)))
        else:raise Problem(400,'Unbekannte Anspruchsfassung in der Gesamtkomposition.')
    for date,decision in sickness.items():
        if decision['entitled'] and date in continuation:
            block('paid_and_unpaid_overlap','Bezahlter Krankheitsanspruch und fehlender Entgeltanspruch widersprechen sich am selben Tag.')
        if not decision['entitled'] and date not in continuation:
            block('unpaid_social_evidence_missing','Für unbezahlte Krankheitszeit fehlt der tatsächliche Fortbestands-/Leistungsnachweis; kein Krankengeld wird angenommen.')
    for date,value in money_days.items():
        if date in unpaid and (value['paid_seconds'] is None or value['paid_seconds']):
            block('paid_and_unpaid_overlap','Bezahlte Ausfallvergütung überschneidet sich mit vollständig unbezahltem Anspruch.')
    for absence in snapshot['approved_absences']:
        dates=_dates(max(first,day(absence['start_date'])),min(last,day(absence['end_date'])))
        for date in dates:
            selected=agreement(date)
            if selected is None:continue
            if absence['kind']=='vacation':
                if selected['pay_basis']=='hourly' and money_days.get(date,{}).get('kind')!='vacation':
                    scheduled=next((value['scheduled_seconds'] for value in (schedule or {}).get('details',{}).get('days',[]) if value['date']==date),None)
                    if scheduled is None or scheduled>0:block('vacation_entitlement_missing','Für freigegebenen Stundenlohnurlaub fehlt die vollständige Urlaubsreferenz.')
            elif absence['kind']=='sick':
                if date not in sickness:block('sickness_history_missing','Für freigegebene Krankheit fehlt die vollständige Anspruchs-/Vorzeitenrechnung.')
                elif sickness[date]['entitled'] and selected['pay_basis']=='hourly':
                    scheduled=next((value['scheduled_seconds'] for value in (schedule or {}).get('details',{}).get('days',[]) if value['date']==date),None)
                    if (scheduled is None or scheduled>work.get(date,0)) and money_days.get(date,{}).get('kind') not in ('sickness','first_sickness_day_regular_wage'):
                        block('sickness_pay_missing','Bezahlter Krankheitsanspruch benötigt die konkrete Ausfallstundenvergütung.')
            elif date not in unpaid:block('absence_entitlement_missing','Für sonstige Abwesenheit fehlt die konkrete belegte Entgeltentscheidung.')
    base=contractual_earnings(month,terms,agreements,snapshot['approved_days'],schedule=schedule,
        thirty_day_rule=thirty_day_rule,unpaid_dates=sorted(unpaid))
    for issue in base['blockers']:block(issue['code'],issue['message'])
    extra=[]
    for key in sorted(groups):
        group=groups[key];group['days'].sort();group['source_refs'].sort(key=lambda value:value['id'])
        extra.append(dict(group,gross_minor=_round_ratio(group['hourly_rate_minor'],group['paid_absence_seconds'],3600)))
    extra.extend(vacations)
    result=dict(schema_version=1,component_version='de_2026_claims_composition_v1',month=month,
        base_earnings=base['earnings'],absence_earnings=extra,employment_intervals=base['employment_intervals'],
        gross_minor=None if base['gross_minor'] is None else base['gross_minor']+sum(value['gross_minor'] for value in extra),
        unpaid_dates=sorted(unpaid),social_continuation=[dict(date=date,**continuation[date]) for date in sorted(continuation)],
        entitlement_sources=facts,actual_project_time_modified=False,blockers=sorted(blockers,key=lambda value:value['code']))
    result['component_hash']=hashlib.sha256(canonical(result).encode()).hexdigest()
    return result

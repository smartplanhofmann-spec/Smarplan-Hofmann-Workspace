"""Pure P3b interval and contractual earnings primitives for the new v5 path.

These functions do not dispatch or modify historical v4 plans. The new private
case resolver must bind canonical sources and establish legal transition facts
before passing them here. No API or existing payroll route uses this module yet.
"""
from datetime import timedelta
from decimal import Decimal, ROUND_HALF_UP, localcontext
import hashlib

from core import Problem, canonical
from payroll_de_2026 import day, integer, month_range

SEGMENT_COMPONENT_VERSION = 'de_2026_segments_component_v1'
COMPOSITE_RULE_VERSION = 'de_2026_segments_entitlements_v5'
METHODS = frozenset(('calendar_days_actual', 'contractual_30_days', 'scheduled_workdays', 'scheduled_seconds'))
SOCIAL_BOUNDARY_REASONS = frozenset(('contribution_group_change', 'person_group_change',
    'collection_agency_change_for_status_transition'))


def reference(record):
    return {key:record[key] for key in ('id','revision','content_hash')}


def _sha(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def _round_ratio(amount,numerator,denominator):
    integer(amount);integer(numerator);integer(denominator,1)
    with localcontext() as context:
        context.prec=50
        return int((Decimal(amount)*numerator/denominator).quantize(Decimal(1),rounding=ROUND_HALF_UP))


def _days(start,end):
    return [(start+timedelta(days=index)).isoformat() for index in range((end-start).days+1)]


def employment_intervals(month,terms):
    """Intersect independently evidenced, non-overlapping episodes with month."""
    first,last=month_range(month)
    if not isinstance(terms,list) or not terms:raise Problem(400,'Belegte Beschäftigungsepisoden angeben.')
    output=[];employee_id=None;seen=set()
    for fact in terms:
        if fact['kind']!='employment_terms' or fact['status']!='active' or fact['id'] in seen:
            raise Problem(400,'Eindeutige aktive Beschäftigungsnachweise sind erforderlich.')
        seen.add(fact['id'])
        if employee_id is not None and fact['employee_id']!=employee_id:raise Problem(400,'Beschäftigungsepisoden gehören zu verschiedenen Personen.')
        employee_id=fact['employee_id'];details=fact['details']
        start=day(details['employment_from']);end=day(details['employment_to']) if details['employment_to'] else last
        if end<start:raise Problem(400,'Beschäftigungsende liegt vor dem Beginn.')
        start,end=max(first,start),min(last,end)
        if start>end:continue
        output.append(dict(start=start.isoformat(),end=end.isoformat(),calendar_days=(end-start).days+1,
            employment_terms_ref=reference(fact)))
    output.sort(key=lambda value:(value['start'],value['end']))
    for left,right in zip(output,output[1:]):
        if right['start']<=left['end']:raise Problem(400,'Beschäftigungsepisoden dürfen sich nicht überlappen.')
    return output


def social_intervals(month,episodes,transitions):
    """Days and caps for already verified genuine social-insurance boundaries.

    A caller cannot use an arbitrary wage/profile row as a split reason. Source
    validation of the actual before/after status belongs to the private case
    resolver; this primitive deliberately does not infer it from a fund name.
    """
    first,last=month_range(month)
    if not isinstance(transitions,list):raise Problem(400,'Belegte SV-Wechsel als Liste angeben.')
    dates={};output=[]
    for event in transitions:
        if set(event)!={'effective_from','reason','source_ref'} or event['reason'] not in SOCIAL_BOUNDARY_REASONS:
            raise Problem(400,'Nur belegte fachliche SV-Grenzen dürfen neue Teil-BBG erzeugen.')
        effective=day(event['effective_from'])
        if not first<=effective<=last or event['effective_from'] in dates:
            raise Problem(400,'SV-Grenzen müssen eindeutig im Monat liegen.')
        dates[event['effective_from']]=event
    used=set();previous_end=None
    for episode in episodes:
        start,end=day(episode['start']),day(episode['end'])
        if not first<=start<=end<=last:raise Problem(400,'Beschäftigungsintervall liegt außerhalb des Monats.')
        if previous_end is not None and start<=previous_end:raise Problem(400,'Beschäftigungsintervalle müssen aufsteigend und überschneidungsfrei sein.')
        previous_end=end
        internal=sorted(value for value in dates if episode['start']<value<=episode['end'])
        if episode['start'] in dates:used.add(episode['start'])
        bounds=[start]+[day(value) for value in internal]+[end+timedelta(days=1)]
        used.update(internal)
        for index,(left,right_exclusive) in enumerate(zip(bounds,bounds[1:])):
            right=right_exclusive-timedelta(days=1);full_month=left==first and right==last
            count=30 if full_month else min(30,(right-left).days+1)
            event=dates.get(left.isoformat())
            output.append(dict(start=left.isoformat(),end=right.isoformat(),days=count,full_month=full_month,
                employment_terms_ref=episode['employment_terms_ref'],
                boundary_reason=event['reason'] if event else 'employment_episode',
                transition_source_ref=event['source_ref'] if event else None,
                caps=dict(health_minor=_round_ratio(6975000,count,360),care_minor=_round_ratio(6975000,count,360),
                    pension_minor=_round_ratio(10140000,count,360),unemployment_minor=_round_ratio(10140000,count,360))))
    if used!=set(dates):raise Problem(400,'Ein SV-Wechsel liegt außerhalb aller belegten Beschäftigungsepisoden.')
    return output


def contractual_earnings(month,terms,agreements,approved_days,*,schedule=None,thirty_day_rule=None,unpaid_dates=()):
    """Calculate distinct actual wage agreements; no tax/SV split is inferred.

    Thirty-day segment allocation must be explicit, in addition to the old P2
    method. The supported choice uses actual claim days capped at30 /30. It is a
    documented contractual choice, not a statutory default for all contracts.
    """
    first,last=month_range(month);episodes=employment_intervals(month,terms)
    if not isinstance(unpaid_dates,(list,tuple)) or len(set(unpaid_dates))!=len(unpaid_dates):
        raise Problem(400,'Unbezahlte Anspruchstage müssen eindeutig sein.')
    unpaid=set(unpaid_dates)
    if any(not first<=day(value)<=last for value in unpaid):raise Problem(400,'Unbezahlter Anspruchstag liegt außerhalb des Monats.')
    if not isinstance(agreements,list) or not agreements or not isinstance(approved_days,list):
        raise Problem(400,'Entgeltvereinbarungen und freigegebene Tageszeiten vollständig angeben.')
    employee_ids={value['employee_id'] for value in terms}
    ordered=sorted(agreements,key=lambda value:(value['effective_from'],value['id']))
    if len({value['effective_from'] for value in ordered})!=len(ordered) or len({value['id'] for value in ordered})!=len(ordered):
        raise Problem(400,'Entgeltquellen müssen eindeutige Wirksamkeitstage und Identitäten besitzen.')
    for value in ordered:
        day(value['effective_from']);integer(value['amount_minor'],1)
        if value['employee_id'] not in employee_ids or value['pay_basis'] not in ('hourly','monthly'):
            raise Problem(400,'Entgeltquelle gehört nicht zum Beschäftigungsfall.')
    work={}
    for value in approved_days:
        date=day(value['date']);seconds=integer(value['net_seconds'],0,86400)
        if not first<=date<=last or value['date'] in work:raise Problem(400,'Freigegebene Arbeitstage müssen eindeutig im Monat liegen.')
        work[value['date']]=seconds
    if schedule is not None:
        if schedule['kind']!='work_schedule' or schedule['status']!='active' or schedule['employee_id'] not in employee_ids or schedule['details']['month']!=month:
            raise Problem(400,'Arbeitsplan gehört nicht zu diesem Beschäftigungsfall.')
        days=schedule['details']['days']
        if [value['date'] for value in days]!=_days(first,last):raise Problem(400,'Jeden Monatstag genau einmal im Arbeitsplan belegen.')
        for value in days:integer(value['scheduled_seconds'],0,86400)
    else:days=None
    terms_by_ref={canonical(reference(value)):value for value in terms}
    earnings=[];blockers=[];covered=set()
    def block(code,message):
        if not any(value['code']==code for value in blockers):blockers.append(dict(code=code,message=message))
    for episode in episodes:
        fact=terms_by_ref[canonical(episode['employment_terms_ref'])];method=fact['details']['proration_method']
        if method not in METHODS:raise Problem(400,'Unbekannte Vertragsmethode.')
        relevant=[value for value in ordered if value['effective_from']<=episode['end']]
        before=[value for value in relevant if value['effective_from']<=episode['start']]
        if not before:
            block('agreement_not_effective','Zum tatsächlichen Beschäftigungsbeginn fehlt eine Entgeltvereinbarung.');continue
        selected=[before[-1]]+[value for value in relevant if value['effective_from']>episode['start']]
        for index,agreement in enumerate(selected):
            if reference(agreement) not in fact['details']['agreement_refs']:
                block('agreement_source_mismatch','Beschäftigungsnachweis bindet nicht jede wirksame Entgeltvereinbarung.')
            start=max(day(episode['start']),day(agreement['effective_from']))
            end=day(selected[index+1]['effective_from'])-timedelta(days=1) if index+1<len(selected) else day(episode['end'])
            dates=_days(start,end);covered.update(dates);seconds=sum(work.get(date,0) for date in dates)
            unpaid_claim=[value for value in dates if value in unpaid]
            paid_dates=[value for value in dates if value not in unpaid]
            numerator=denominator=0
            if agreement['pay_basis']=='hourly':numerator,denominator=seconds,3600
            elif method=='calendar_days_actual':numerator,denominator=len(paid_dates),(last-first).days+1
            elif method=='contractual_30_days':
                if thirty_day_rule!='actual_days_capped_per_claim':
                    block('segment_contract_method_missing','Für mehrere Entgeltansprüche ist die tatsächliche vertragliche 30-Tage-Aufteilung ausdrücklich zu belegen.')
                else:
                    contract_units=30 if start==first and end==last else min(30,len(dates))
                    numerator,denominator=max(0,contract_units-len(unpaid_claim)),30
            elif days is None:block('work_schedule_missing','Die Vertragsmethode benötigt den vollständigen Monatsarbeitsplan.')
            else:
                weight=lambda value:int(value['scheduled_seconds']>0) if method=='scheduled_workdays' else value['scheduled_seconds']
                numerator=sum(weight(value) for value in days if value['date'] in paid_dates);denominator=sum(weight(value) for value in days)
                if not denominator:block('empty_work_schedule','Der Monatsarbeitsplan enthält keine Solltage oder Sollsekunden.')
            gross=_round_ratio(agreement['amount_minor'],numerator,denominator) if denominator else None
            earnings.append(dict(kind='ordinary_work',start=start.isoformat(),end=end.isoformat(),
                employment_terms_ref=reference(fact),agreement_ref=reference(agreement),pay_basis=agreement['pay_basis'],
                proration_method=method,thirty_day_rule=thirty_day_rule if method=='contractual_30_days' else None,
                numerator=numerator,denominator=denominator,approved_work_seconds=seconds,unpaid_dates=unpaid_claim,gross_minor=gross))
    if any(seconds and date not in covered for date,seconds in work.items()):
        block('work_outside_employment','Freigegebene Arbeitszeit ist keinem belegten Beschäftigungs-/Entgeltintervall zugeordnet.')
    if not unpaid.issubset(covered):block('unpaid_outside_employment','Unbezahlter Anspruch liegt außerhalb belegter Beschäftigungs-/Entgeltintervalle.')
    if any(work.get(value,0) for value in unpaid):block('work_on_fully_unpaid_day','Ein vollständig unbezahlter Ausfalltag enthält freigegebene tatsächliche Arbeitszeit.')
    if not episodes:block('no_employment_in_period','Im Monat besteht keine belegte Beschäftigungsepisode.')
    output=dict(component_version=SEGMENT_COMPONENT_VERSION,month=month,employment_intervals=episodes,earnings=earnings,
        gross_minor=sum(value['gross_minor'] for value in earnings) if earnings and all(value['gross_minor'] is not None for value in earnings) else None,
        approved_work_seconds=sum(work.values()),blockers=sorted(blockers,key=lambda value:value['code']))
    return dict(output,component_hash=_sha(output))

"""Explicit evidenced overlapping sickness phases; immutable v1/v2 are separate.

TK examples 17--19, IKK2026 p8; BAG 5 AZR 505/18; GKV EFZG section 6
for the start-of-case cap and recurrence anchors of a joined cause.
"""
from copy import deepcopy
from datetime import timedelta
import hashlib

from core import Problem, canonical
from payroll_de_2026 import day
from payroll_entitlements_2026 import ONE_DAY, _shape, _refs, _identifier, calendar_month_period_end
from payroll_sickness_2026 import derive_sickness_entitlement as separate

SICKNESS_PHASE_RULE_VERSION='de_2026_sickness_phases_v3'
SICKNESS_PHASE_RULES=dict(version=SICKNESS_PHASE_RULE_VERSION,
    independent_cases='EVIDENCED_RECOVERY_BEFORE_EACH_CASE',
    joined_causes='ACTUAL_OVERLAP_EXPLICIT_CASE_PARTITION_NO_DIAGNOSES',
    limit='INITIAL_CAUSE_REMAINING_CALENDAR_PERIOD_NEVER_EXTENDED',
    phase='FIRST_PERSISTING_CAUSE_UNTIL_ITS_END_THEN_NEXT_UNIQUE_CAUSE',
    recurrence='ONLY_RESPONSIBLE_PHASE_COUNTS_AND_ANCHORS_ADDED_CAUSE',
    unused_added_cause='NO_NEW_TWELVE_MONTH_ANCHOR_WITHOUT_PAYMENT',
    free_day='V2_FOLLOWING_CALENDAR_DAY_FOR_HOURLY_PAY',
    waiting='28_DAYS_NOT_CONSUMED',
    joined_responsibility_during_waiting='ANCHOR_DECISION_REQUIRED_IF_PAYMENT_LATER',
    simultaneous_unresolved='EXPLICIT_DECISION_REQUIRED')
SICKNESS_PHASE_RULES_SHA256=hashlib.sha256(canonical(SICKNESS_PHASE_RULES).encode()).hexdigest()


def derive_sickness_phases(source):
    _shape(source,'employment_from employment_to pay_basis complete_from complete_through history_evidence_refs episodes prevention_cases')
    basic={key:deepcopy(value) for key,value in source.items() if key!='prevention_cases'}
    if not isinstance(basic['episodes'],list) or len(basic['episodes'])>2000:
        raise Problem(400,'Ungültige Liste belegter Krankheitsursachen.')
    # The frozen v2 validator checks dates, original references and employment.
    # Only the validation copy represents a joined cause as a separate one;
    # the original source and its hash always retain its actual onset facts.
    separate(dict(basic,episodes=[]))
    episodes={};rows={}
    for original in basic['episodes']:
        _shape(original,'id from to onset first_scheduled_day continuation_group recovery_before unculpable evidence_refs')
        identity=_identifier(original['id'])
        if identity in episodes:raise Problem(400,'Krankheitsursache ist doppelt enthalten.')
        probe=deepcopy(original)
        if probe['onset']=='during_existing_au':
            if probe['recovery_before'] is not False or probe['first_scheduled_day'] is not None:
                raise Problem(400,'Hinzutritt benötigt belegte fortbestehende AU ohne erfundenen Solltag.')
            probe.update(onset='before_work',recovery_before=True)
        result=separate(dict(basic,episodes=[probe]))['episodes'][0]
        result.update(entitlement_from=None,entitlement_to=None,entitlement_calendar_days=0,
            first_day_remaining_regular_wage=None,reset_reason='not_responsible_cause',
            twelve_month_anchor=None,prior_used_days=0,remaining_days=42,
            responsibility_from=None,responsibility_to=None,prevention_case_id=None)
        episodes[identity]=original;rows[identity]=result
    cases=source['prevention_cases']
    if not isinstance(cases,list) or len(cases)>2000:raise Problem(400,'Ungültige Verhinderungsfälle.')
    assigned=set();case_ids=set();ordered=[]
    for case in cases:
        _shape(case,'id episode_ids evidence_refs');_identifier(case['id']);_refs(case['evidence_refs'])
        if case['id'] in case_ids:raise Problem(400,'Verhinderungsfall ist doppelt enthalten.')
        case_ids.add(case['id']);identities=case['episode_ids']
        if not isinstance(identities,list) or not identities:raise Problem(400,'Verhinderungsfall benötigt tatsächliche Ursachen.')
        if any(not isinstance(identity,str) or identity not in episodes or identity in assigned for identity in identities) or len(set(identities))!=len(identities):
            raise Problem(400,'Jede tatsächliche Ursache muss genau einem Verhinderungsfall zugeordnet werden.')
        assigned.update(identities)
        members=sorted([episodes[identity] for identity in identities],key=lambda value:(value['from'],value['id']))
        if len({item['continuation_group'] for item in members})!=len(members):
            raise Problem(409,'Mehrere Bescheinigungen derselben Ursache innerhalb eines Falls benötigen einen eindeutigen durchgehenden Ursachennachweis.')
        first=members[0]
        if first['recovery_before'] is not True or first['onset']=='during_existing_au':
            raise Problem(409,'Ein eigenständiger Verhinderungsfall benötigt belegte vorherige Arbeitsfähigkeit.')
        end=first['to']
        for item in members[1:]:
            if item['from']==first['from'] or item['from']>end:
                raise Problem(409,'Gleichzeitiger unklarer Beginn oder getrennte Ursachen dürfen nicht als belegter Hinzutritt berechnet werden.')
            if item['onset']!='during_existing_au' or item['recovery_before'] is not False:
                raise Problem(409,'Überlappende Ursache muss ausdrücklich als Hinzutritt bei bestehender AU belegt sein.')
            end=max(end,item['to'])
        for item in members:rows[item['id']]['prevention_case_id']=case['id']
        ordered.append((first['from'],end,case,members))
    if assigned!=set(episodes):raise Problem(400,'Nicht jede AU-Ursache ist einem belegten Verhinderungsfall zugeordnet.')
    ordered.sort(key=lambda item:(item[0],item[2]['id']))
    groups={};phases=[];case_rows=[];previous_end=None
    waiting_end=day(source['employment_from'])+timedelta(days=27)

    def state_for(group,event,count_from):
        state=groups.get(group);reset='first_evidenced_case'
        if state is not None and state['anchor'] is not None:
            if event>calendar_month_period_end(state['last_end']+ONE_DAY,6):reset='six_months_without_same_illness'
            elif count_from>calendar_month_period_end(state['anchor'],12):reset='twelve_months_since_first_case'
            else:reset='same_illness_remaining_entitlement'
        if reset!='same_illness_remaining_entitlement':state=dict(anchor=count_from,used=0,last_end=event)
        return state,reset

    for case_first,case_last,case,members in ordered:
        if previous_end is not None and case_first<=previous_end:
            raise Problem(409,'Überlappende Verhinderungsfälle dürfen nicht getrennte Fristen eröffnen.')
        previous_end=case_last;primary=members[0];primary_row=rows[primary['id']]
        count_from=day(primary_row['count_from']);paid_start=max(count_from,waiting_end+ONE_DAY)
        initial_state,_=state_for(primary['continuation_group'],day(case_first),count_from)
        initial_available=max(0,42-initial_state['used'])
        deadline=paid_start+timedelta(days=initial_available-1)
        boundaries=sorted({day(item[key])+(ONE_DAY if key=='to' else timedelta(0)) for item in members for key in ('from','to')})
        responsible_seen=set();case_paid=0
        for begin,stop in zip(boundaries,boundaries[1:]):
            end=stop-ONE_DAY
            active=sorted([item for item in members if day(item['from'])<=begin<=day(item['to'])],key=lambda item:(item['from'],item['id']))
            if not active:raise Problem(409,'Im einheitlichen Verhinderungsfall fehlt eine belegte Ursache.')
            if len(active)>1 and active[0]['from']==active[1]['from']:
                raise Problem(409,'Gleichzeitig begonnene maßgebende Ursachen benötigen eine eigene Anspruchsentscheidung.')
            responsible=active[0];identity=responsible['id'];row=rows[identity];group=responsible['continuation_group']
            if identity not in responsible_seen:
                responsible_seen.add(identity)
                if identity!=primary['id'] and begin<=waiting_end<day(responsible['to']):
                    raise Problem(409,'Wird die hinzugetretene Ursache schon in der Wartezeit allein maßgebend, benötigt ihr Zwölfmonatsanker eine eigene belegte Entscheidung.')
                event=day(case_first) if identity==primary['id'] else begin
                counting=count_from if identity==primary['id'] else begin
                state,reset=state_for(group,event,counting)
                available=max(0,42-state['used']);first=max(begin,paid_start)
                last=min(day(responsible['to']),deadline,first+timedelta(days=available-1))
                paid_days=max(0,(last-first).days+1)
                row.update(responsibility_from=begin.isoformat(),responsibility_to=responsible['to'],
                    count_from=counting.isoformat(),prior_used_days=42-available,
                    entitlement_from=first.isoformat() if paid_days else None,
                    entitlement_to=last.isoformat() if paid_days else None,
                    entitlement_calendar_days=paid_days,reset_reason=reset)
                if identity==primary['id'] and primary['onset']=='during_work' and day(case_first)>waiting_end and available:
                    row['first_day_remaining_regular_wage']=case_first
                if identity!=primary['id'] and not paid_days and reset!='same_illness_remaining_entitlement':
                    # No new twelve-month clock for a joined cause that never
                    # acquired a separate payment claim within the case cap.
                    state['anchor']=None
                state['used']+=paid_days;state['last_end']=day(responsible['to']);groups[group]=state
                row['remaining_days']=max(0,42-state['used'])
                row['twelve_month_anchor']=state['anchor'].isoformat() if state['anchor'] else None
                case_paid+=paid_days
            cuts={begin,stop}
            for boundary in (paid_start,deadline+ONE_DAY,waiting_end+ONE_DAY,
                             day(row['entitlement_from']) if row['entitlement_from'] else None,
                             day(row['entitlement_to'])+ONE_DAY if row['entitlement_to'] else None,
                             day(case_first)+ONE_DAY if row['first_day_remaining_regular_wage'] else None):
                if boundary is not None and begin<boundary<stop:cuts.add(boundary)
            cuts=sorted(cuts)
            for left,right in zip(cuts,cuts[1:]):
                current=left.isoformat();paid=row['entitlement_from'] is not None and row['entitlement_from']<=current<=row['entitlement_to']
                phases.append(dict(prevention_case_id=case['id'],from_date=current,to_date=(right-ONE_DAY).isoformat(),
                    active_episode_ids=[item['id'] for item in active],responsible_episode_id=identity,
                    entitled=paid,first_day_remaining_regular_wage=row['first_day_remaining_regular_wage']==current,
                    waiting_period=left<=waiting_end))
        case_rows.append(dict(id=case['id'],from_date=case_first,to_date=case_last,count_from=count_from.isoformat(),
            initial_remaining_days=initial_available,statutory_deadline=deadline.isoformat(),
            entitlement_calendar_days=case_paid))
    result=dict(schema_version=1,rule_version=SICKNESS_PHASE_RULE_VERSION,rules_hash=SICKNESS_PHASE_RULES_SHA256,
        kind='sickness',source_hash=hashlib.sha256(canonical(source).encode()).hexdigest(),
        waiting_period_end=waiting_end.isoformat(),episodes=[rows[item['id']] for item in sorted(episodes.values(),key=lambda item:(item['from'],item['id']))],
        prevention_cases=case_rows,phases=phases)
    result['plan_hash']=hashlib.sha256(canonical(result).encode()).hexdigest()
    return result

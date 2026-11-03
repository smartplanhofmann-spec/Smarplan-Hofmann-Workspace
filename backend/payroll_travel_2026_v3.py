"""Deterministic employee travel calculations; no database or payment effects.

The caller supplies versioned personnel evidence, never a desired tax result.
Unsupported or contradictory facts remain explicit blockers in the result.
"""
from calendar import monthrange
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
import hashlib
import json
import re

from core import Problem
from payroll_travel_rates_2026 import TABLE_HASH, rate
from payroll_travel_ground_2026 import GROUND_MODULE_HASH
from payroll_travel_mixed_2026 import MIXED_MODULE_HASH, resolve_mixed_program, prorate_minor

RULE_VERSION='de_travel_2026_v3'
RULE_HASH=hashlib.sha256(json.dumps(dict(version=RULE_VERSION,table_hash=TABLE_HASH,
    ground_module_hash=GROUND_MODULE_HASH,mixed_module_hash=MIXED_MODULE_HASH),sort_keys=True,separators=(',',':')).encode()).hexdigest()


def sha(value):
    return hashlib.sha256(json.dumps(value,ensure_ascii=False,sort_keys=True,
                                    separators=(',',':')).encode()).hexdigest()


def integer(value,minimum=0,maximum=10**12):
    if type(value) is not int or not minimum <= value <= maximum:
        raise Problem(400,'Ganze Zahl im zulässigen Bereich erforderlich.')
    return value


def day(value):
    if not isinstance(value,str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}',value):
        raise Problem(400,'Datum als JJJJ-MM-TT erforderlich.')
    try:return date.fromisoformat(value)
    except ValueError as error:raise Problem(400,'Ungültiges Kalenderdatum.') from error


def zone(value):
    if not isinstance(value,str) or len(value)>100:
        raise Problem(400,'IANA-Zeitzone erforderlich.')
    try:return ZoneInfo(value)
    except (ValueError,ZoneInfoNotFoundError) as error:raise Problem(400,'Bekannte IANA-Zeitzone auswählen.') from error


def moment(value,timezone_name=None):
    if not isinstance(value,str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(?::\d{2})?(?:Z|[+-]\d{2}:\d{2})',value):
        raise Problem(400,'Eindeutiger Zeitpunkt mit ausdrücklichem UTC-Offset erforderlich.')
    try:result=datetime.fromisoformat(value.replace('Z','+00:00'))
    except ValueError as error:raise Problem(400,'Ungültiger Reisezeitpunkt.') from error
    if timezone_name is not None:
        converted=result.astimezone(zone(timezone_name))
        if converted.replace(tzinfo=None)!=result.replace(tzinfo=None) or converted.utcoffset()!=result.utcoffset():
            raise Problem(400,'Zeitpunkt oder UTC-Offset passt nicht zur angegebenen Ortszeitzone.')
    return result.astimezone(timezone.utc)


def time_options(local,timezone_name):
    if not isinstance(local,str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}',local):
        raise Problem(400,'Örtliche Zeit als JJJJ-MM-TTThh:mm erforderlich.')
    try:naive=datetime.fromisoformat(local)
    except ValueError as error:raise Problem(400,'Ungültige örtliche Zeit.') from error
    tz=zone(timezone_name);options=[];seen=set()
    for fold in (0,1):
        candidate=naive.replace(tzinfo=tz,fold=fold)
        converted=candidate.astimezone(timezone.utc).astimezone(tz)
        if converted.replace(tzinfo=None)!=naive or candidate.utcoffset()!=converted.utcoffset():continue
        iso=candidate.isoformat(timespec='seconds')
        if iso in seen:continue
        seen.add(iso);offset=iso[-6:]
        options.append(dict(instant=iso,offset=offset,label=local.replace('T',' ')+' (UTC'+offset+')'))
    return dict(local=local,timezone=timezone_name,options=options,valid=bool(options))


def _months(value,count):
    n=value.year*12+value.month-1+count
    year,month=divmod(n,12);month+=1
    return date(year,month,min(value.day,monthrange(year,month)[1]))


def _round(value):return int(Decimal(value).quantize(Decimal('1'),rounding=ROUND_HALF_UP))


def _duration(intervals):
    total=0;end=None
    for start,finish in sorted(intervals):
        if end is None or start>end:total+=int((finish-start).total_seconds());end=finish
        elif finish>end:total+=int((finish-end).total_seconds());end=finish
    return total


def three_month(site,visited_on,all_visits):
    """Fixed-site rule with explicit assignment and evidenced visit history."""
    when=day(visited_on);details=site.get('details',site);kind=details['kind']
    if kind in ('mobile','wide_area'):
        return dict(started_on=None,expires_on=None,reset_on=None,eligible=True,reason='mobile_or_wide_area')
    if kind in ('home','first_workplace'):
        return dict(started_on=None,expires_on=None,reset_on=None,eligible=False,reason='not_external_workplace')
    regular=integer(details['regular_days_per_week'],0,7)
    complete=day(details['history_complete_from']);effective=day(details['effective_from'])
    dates=sorted({day(value) for value in details['prior_visit_dates']+list(all_visits) if day(value)<=when})
    if not dates and complete<=effective:
        return dict(started_on=None,expires_on=None,reset_on=None,eligible=True,reason='assignment_not_yet_visited')
    if not dates or complete>dates[0] or complete>effective:
        return dict(started_on=None,expires_on=None,reset_on=None,eligible=False,reason='incomplete_workplace_history')
    periods=details.get('frequency_periods',[])
    def frequency(current):
        if not periods:return regular
        matches=[p for p in periods if day(p['from'])<=current and (p['to'] is None or current<=day(p['to']))]
        if len(matches)!=1:return None
        return integer(matches[0]['days_per_week'],0,7)
    started=None;previous=None;reset=None;had_period=False
    for current in dates:
        f=frequency(current)
        if f is None:return dict(started_on=None,expires_on=None,reset_on=None,eligible=False,reason='incomplete_workplace_history')
        if previous is not None and (current-previous).days-1>=28:started=None
        if started is None and f>=3:
            started=current
            if had_period:reset=current
            had_period=True
        previous=current
    if started is None:
        return dict(started_on=None,expires_on=None,reset_on=None,eligible=True,reason='less_than_three_days_weekly')
    target=_months(started,3)
    # BGB 188(3): when the same day number does not exist in the ending
    # month, its last day is included; do not subtract another calendar day.
    expires=target if target.day<started.day else target-timedelta(days=1)
    return dict(started_on=started.isoformat(),expires_on=expires.isoformat(),
                reset_on=reset.isoformat() if reset else None,eligible=when<=expires,
                reason='within_three_months' if when<=expires else 'three_months_exhausted')



def _reference(value):
    if not isinstance(value,dict) or set(value)!={'id','revision','content_hash'}:
        raise Problem(400,'Unveränderliche Quelle mit ID, Revision und Hash erforderlich.')
    if not isinstance(value['id'],str) or not re.fullmatch('[a-f0-9]{32}',value['id']):
        raise Problem(400,'Ungültige Reisequellen-ID.')
    integer(value['revision'],1)
    if not isinstance(value['content_hash'],str) or not re.fullmatch('[a-f0-9]{64}',value['content_hash']):
        raise Problem(400,'Ungültiger Reisequellenhash.')
    return value['id'],value['revision'],value['content_hash']


def _site(ref,sites):
    key=_reference(ref)
    try:return sites[key]
    except KeyError as error:raise Problem(409,'Genau passende Stättenfassung erforderlich.') from error


def _days(start,end):
    current=start
    while current<=end:
        yield current;current+=timedelta(days=1)


def _bounds(value,tz):
    start=datetime.combine(value,datetime.min.time(),tzinfo=tz)
    finish=datetime.combine(value+timedelta(days=1),datetime.min.time(),tzinfo=tz)
    return start.astimezone(timezone.utc),finish.astimezone(timezone.utc)


def _source(record):return {key:record[key] for key in ('id','revision','content_hash')}


def calculate(trips,site_records,*,settlement_unit='trip',tax_choice='tax_free_only',
              requested_meal_minor=None,requested_lodging_minor=None,already_paid_minor=0,history_trips=(),rule_version=None):
    if rule_version=='de_travel_2026_v1':
        from payroll_travel_2026_v1 import calculate as original
        return original(trips,site_records,settlement_unit=settlement_unit,tax_choice=tax_choice,
            requested_meal_minor=requested_meal_minor,requested_lodging_minor=requested_lodging_minor,
            already_paid_minor=already_paid_minor,history_trips=history_trips)
    if rule_version=='de_travel_2026_v2':
        from payroll_travel_2026_v2 import calculate as original
        return original(trips,site_records,settlement_unit=settlement_unit,tax_choice=tax_choice,
            requested_meal_minor=requested_meal_minor,requested_lodging_minor=requested_lodging_minor,
            already_paid_minor=already_paid_minor,history_trips=history_trips)
    if rule_version not in (None,RULE_VERSION):raise Problem(409,'Unbekannte historische Reiseregelversion.')
    if not isinstance(trips,list) or not 1<=len(trips)<=100:
        raise Problem(400,'Eine bis hundert ausdrücklich ausgewählte Reisen erforderlich.')
    if settlement_unit not in ('trip','combined_period') or settlement_unit=='trip' and len(trips)!=1:
        raise Problem(400,'Abrechnungseinheit ausdrücklich passend zu den Reisen wählen.')
    if tax_choice not in ('tax_free_only','flat_25','individual'):
        raise Problem(400,'Steuerliche Behandlung ausdrücklich wählen.')
    from payroll_travel_expenses_2026 import calculate_expenses
    expenses=calculate_expenses(trips)
    sites={_reference(_source(row)):row for row in site_records};visits={};facts=[];blockers=[];seen=set();trip_intervals=[];transport_sources=[];ground_sources=[];mixed_sources=[]
    for history in history_trips:
        for segment in history['details']['segments']:
            if segment['activity']!='work':continue
            historical_site=next(s for s in history['sources']['sites'] if _source(s)==segment['site_ref'])
            tz_history=zone(historical_site['details']['timezone'])
            start_history=moment(segment['from']).astimezone(tz_history).date()
            end_history=(moment(segment['to'])-timedelta(microseconds=1)).astimezone(tz_history).date()
            visits.setdefault(historical_site['id'],set()).update(d.isoformat() for d in _days(start_history,end_history))
    def block(code,text,source_ref=None):
        value=dict(code=code,text=text,source_ref=source_ref)
        if value not in blockers:blockers.append(value)
    blockers.extend(expenses['blockers'])
    for trip in trips:
        ref=_source(trip);_reference(ref)
        if trip['id'] in seen:raise Problem(400,'Reise darf in einer Abrechnung nicht doppelt vorkommen.')
        seen.add(trip['id']);d=trip['details'];tz=zone(d['timezone'])
        from payroll_travel_transport_2026 import resolve_transport_days
        transport=resolve_transport_days(trip,site_records)
        if d.get('transport_facts') or any(s['transport']!='ground' for s in d['segments']):
            transport_sources.append(dict(trip=ref,**transport));blockers.extend(transport['blockers'])
        transport_dates={d['date']:d for d in transport['calendar_days']}
        from payroll_travel_ground_2026 import resolve_ground_calendar
        ground=resolve_ground_calendar(trip,site_records)
        if ground is not None:ground_sources.append(dict(trip=ref,**ground))
        start=moment(d['departed_at'],d['timezone']);finish=moment(d['returned_at'],d['timezone'])
        if finish<=start or finish-start>timedelta(days=366):raise Problem(400,'Reiseende muss nach Beginn und höchstens ein Jahr später liegen.')
        if any(start<b and finish>a for a,b in trip_intervals):raise Problem(400,'Tatsächliche Reisen derselben Person dürfen sich nicht überschneiden.')
        trip_intervals.append((start,finish))
        first=start.astimezone(tz).date();last=finish.astimezone(tz).date()
        if first.year!=2026 or last.year!=2026:block('rule_year_missing','Reise benötigt Regeln für ein anderes Kalenderjahr.',ref)
        home=_site(d['home_site_ref'],sites)
        if home['details']['kind']!='home':raise Problem(400,'Belegte Wohnung als Ausgangsbezug erforderlich.')
        if d['first_workplace_ref'] is not None and _site(d['first_workplace_ref'],sites)['details']['kind']!='first_workplace':
            raise Problem(400,'Erste Tätigkeitsstätte ausdrücklich nachweisen.')
        segments=[];previous=start
        for segment in d['segments']:
            s=moment(segment['from']);e=moment(segment['to']);site=_site(segment['site_ref'],sites)
            if s!=previous or e<=s or e>finish:raise Problem(400,'Ortsabschnitte müssen die Reise lückenlos ohne Überlappung abdecken.')
            previous=e
            if segment['activity'] not in ('work','transit','stay') or segment['transport'] not in ('ground','flight','ship'):
                raise Problem(400,'Unbekannte Reiseaktivität oder Beförderung.')
            if type(segment['necessary_stopover']) is not bool:raise Problem(400,'Notwendige Zwischenübernachtung ausdrücklich angeben.')
            details=site['details'];localstart=s.astimezone(zone(details['timezone'])).date();localend=(e-timedelta(microseconds=1)).astimezone(zone(details['timezone'])).date()
            if details['kind'] in ('home','first_workplace'):
                block('not_absent_from_home_or_first_workplace','Reisezeit enthält Aufenthalt an Wohnung oder erster Tätigkeitsstätte; tatsächliche Abwesenheiten getrennt erfassen.',ref)
            if day(details['effective_from'])>localstart or details['effective_to'] is not None and day(details['effective_to'])<localend:
                block('site_validity','Stättennachweis deckt den tatsächlichen Besuch nicht.',segment['site_ref'])
            if segment['activity']=='work':
                visits.setdefault(site['id'],set()).update(value.isoformat() for value in _days(localstart,localend))
            segments.append((s,e,segment,site))
        if previous!=finish:raise Problem(400,'Ortsabschnitte müssen die ganze Reise abdecken.')
        nights={}
        for item in d['overnights']:
            nd=day(item['date'])
            if nd<first or nd>last:raise Problem(400,'Übernachtung liegt außerhalb der Reise.')
            if nd in nights:raise Problem(400,'Übernachtung pro Datum eindeutig zuordnen.')
            nights[nd]=item;night_site=_site(item['site_ref'],sites)
            if night_site['details']['kind'] in ('home','first_workplace'):
                block('not_external_overnight','An-/Abreisetage verlangen eine tatsächliche auswärtige Übernachtung.',ref)
            midnight=_bounds(nd,zone(night_site['details']['timezone']))[1]
            occupied=[row for row in segments if _source(row[3])==item['site_ref'] and row[0]<midnight<=row[1]]
            if not occupied:block('overnight_location_missing','Übernachtungsort ist nicht durch einen tatsächlichen Ortsabschnitt über Mitternacht belegt.',ref)
            if item.get('accommodation_kind')=='lodging' and any(row[2]['transport']!='ground' for row in occupied):
                block('lodging_vehicle_conflict','Ortsabschnitt im Fahrzeug belegt keine Unterkunft außerhalb des Fahrzeugs.',ref)
        if nights and set(nights)!={d for d in _days(first,last-timedelta(days=1))}:
            block('overnight_evidence_missing','Jede tatsächliche Außenübernachtung der Reise muss einzeln belegt sein.',ref)
        mixed=resolve_mixed_program(trip)
        if mixed is not None:
            mixed_sources.append(dict(trip=ref,**mixed))
            for issue in mixed['blockers']:block(issue['code'],issue['text'],ref)
        share=(mixed.get('numerator',0),mixed.get('denominator',1)) if mixed is not None else (1,1)
        # Calendar attribution is explicit in the trip evidence. If a local
        # date changes differently along the itinerary, require a separately
        # reviewed allocation instead of silently counting an extra day.
        for s,e,seg,site in segments:
            sitezone=zone(site['details']['timezone'])
            if (s.astimezone(sitezone).date()!=s.astimezone(tz).date()
                    or (e-timedelta(microseconds=1)).astimezone(sitezone).date()!=(e-timedelta(microseconds=1)).astimezone(tz).date()):
                affected={s.astimezone(sitezone).date().isoformat(),s.astimezone(tz).date().isoformat(),
                    (e-timedelta(microseconds=1)).astimezone(sitezone).date().isoformat(),(e-timedelta(microseconds=1)).astimezone(tz).date().isoformat()}
                if ground is None and (transport['blockers'] or not affected<=set(transport['days'])):
                    block('calendar_boundary_assessment','Ortszeitwechsel über die Datumsgrenze benötigt belegte Tageszuordnung.',ref)
        if ground is not None and any(not first<=day(label)<=last for label in ground['days']):
            block('ground_calendar_outside_trip','Tatsächliche örtliche Tage liegen außerhalb des belegten Abreise-/Rückkehrzeitraums; Zuordnung gesondert prüfen.',ref)
        dates=list(_days(first,last));durations={}
        for current in dates:
            day_tz=zone(transport_dates[current.isoformat()]['timezone']) if current.isoformat() in transport_dates else tz
            lo,hi=_bounds(current,day_tz);durations[current]=max(0,int((min(finish,hi)-max(start,lo)).total_seconds()))
            if ground is not None:durations[current]=ground['days'].get(current.isoformat(),{}).get('absence_seconds',0)
        overnight_work=None
        if first!=last and not nights:
            if len(dates)>2:block('overnight_evidence_missing','Mehrere Reisetage benötigen tatsächliche Übernachtungsnachweise.',ref)
            elif sum(durations.values())>8*3600:
                maximum=max(durations.values());winners=[d for d,n in durations.items() if n==maximum]
                if len(winners)!=1:block('night_work_day_ambiguous','Nachtarbeit verteilt sich gleichmäßig; belegte Tageszuordnung erforderlich.',ref)
                else:overnight_work=winners[0]
        for current in dates:
            day_tz=zone(transport_dates[current.isoformat()]['timezone']) if current.isoformat() in transport_dates else tz
            lo,hi=_bounds(current,day_tz);active=[row for row in segments if row[0]<hi and row[1]>lo]
            pieces=ground['days'].get(current.isoformat(),{}).get('intervals',[]) if ground is not None else None
            if pieces is not None:
                active=[row for row in segments if row[2]['id'] in {p['segment_id'] for p in pieces}]
            if not active:continue
            work=[row for row in active if row[2]['activity']=='work']
            if first==last:
                foreign_work=[row for row in work if rate(row[3]['details']['rate_id'])['country']!='Deutschland']
                selected=foreign_work[-1] if foreign_work else work[-1] if work else active[-1]
            elif current==last:
                previous_work=[row for row in segments if row[0]<hi and row[2]['activity']=='work']
                selected=previous_work[-1] if previous_work else active[-1]
            else:selected=active[-1]
            s,e,segment,site=selected;selected_rate=rate(site['details']['rate_id'])
            transport_day=transport['days'].get(current.isoformat())
            if transport_day:selected_rate=rate(transport_day['rate_id'])
            claim='none';base=0
            if first==last and durations[current]>8*3600:claim='short';base=selected_rate['short_minor']
            elif nights and current in (first,last):claim='arrival_departure';base=selected_rate['short_minor']
            elif nights and first<current<last:claim='full';base=selected_rate['full_minor']
            elif current==overnight_work:claim='overnight_work';base=selected_rate['short_minor']
            facts.append(dict(date=current.isoformat(),trip=ref,site=site,rate=selected_rate,claim_kind=claim,
                base_minor=base,business_share=share,intervals=[(moment(p['utc_from']),moment(p['utc_to'])) for p in pieces] if pieces is not None else [(max(start,lo),min(finish,hi))],
                meals=[m for m in d['meals'] if day(m['date'])==current],night=nights.get(current),
                work_sites=[row[3] for row in work],single_day=first==last,last_work_end=e,
                related_work_sites=[row[3] for row in segments if row[2]['activity']=='work'],
                work_intervals=[(moment(p['utc_from']),moment(p['utc_to']),row[3]) for p in pieces for row in work if p['segment_id']==row[2]['id']] if pieces is not None else [(max(row[0],lo),min(row[1],hi),row[3]) for row in work],transport_day=transport_day))
        for meal in d['meals']:
            if not first<=day(meal['date'])<=last:raise Problem(400,'Mahlzeit liegt außerhalb der Reise.')
    output=[]
    for current in sorted({f['date'] for f in facts}):
        group=[f for f in facts if f['date']==current]
        selected=max(group,key=lambda v:(v['base_minor'],v['rate']['full_minor'],v['rate']['id']))
        all_single=all(f['single_day'] for f in group)
        if all_single:
            foreign=[f for f in group if f['rate']['country']!='Deutschland']
            selected=max(foreign or group,key=lambda v:v['last_work_end'])
        rr=selected['rate'];base=selected['base_minor'];reasons=[]
        if selected['transport_day']:reasons.append(dict(code=selected['transport_day']['reason'],text='Tagessatz aus belegter Flug-/Schiffszeitachse.',source=selected['transport_day']['source']))
        total_absence=_duration([interval for f in group for interval in f['intervals']])
        if all_single:base=rr['short_minor'] if total_absence>8*3600 else 0
        assessments=[(site,three_month(site,current,visits.get(site['id'],set())))
            for f in group for site in (f['work_sites'] or f['related_work_sites'])]
        failed=[a for site,a in assessments if not a['eligible']]
        assessment=failed[0] if failed else assessments[0][1] if assessments else dict(started_on=None,expires_on=None,reset_on=None,eligible=True,reason='travel_day')
        if failed:
            excluded=[];has_eligible_work=False
            for f in group:
                for a,b,site in f['work_intervals']:
                    assessed=three_month(site,current,visits.get(site['id'],set()))
                    if assessed['eligible']:has_eligible_work=True
                    else:excluded.append((a,b))
            eligible_absence=max(0,total_absence-_duration(excluded))
            base=rr['short_minor'] if has_eligible_work and eligible_absence>8*3600 else 0
            reasons.append(dict(code='ineligible_workplace_time_excluded',text='Zeit an nicht begünstigter Stätte ist vom Tagesanspruch getrennt.',source='BMF 25.11.2020 Rz.41'))
            if base:assessment=dict(assessment,eligible=True,reason='other_external_work_over_eight_hours')
            for a in failed:
                if a['reason']=='incomplete_workplace_history':block('incomplete_workplace_history','Vollständige belegte Stättenvorgeschichte erforderlich.',selected['trip'])
        unapportioned_base=base
        shares={f['business_share'] for f in group}
        if len(shares)>1:
            block('mixed_day_allocation_required','Reisen mit verschiedenen beruflichen Programmquoten am selben Tag benötigen eine gesonderte belegte Tagesabgrenzung.',selected['trip'])
            share=(0,1)
        else:share=next(iter(shares))
        base=prorate_minor(base,*share)
        if share!=(1,1):reasons.append(dict(code='mixed_program_share_before_meals',text='Belegte berufliche Programmquote vor der vollen Mahlzeitenkürzung angewandt.',source='BMF 25.11.2020 Rz.90/Beispiel59'))
        meals=[m for f in group for m in f['meals']];seen_meals=set();reduction=0;benefits=0;letter_m=False;meal_groups={};by_meal={}
        for meal in meals:
            if meal['id'] in by_meal:raise Problem(400,'Mahlzeit-ID darf im selben Abrechnungstag nicht doppelt vorkommen.')
            by_meal[meal['id']]=meal
        for meal in meals:
            kind=meal['kind']
            if kind not in ('breakfast','lunch','dinner') or meal['provider'] not in ('employer','employer_arranged','independent_third_party','self'):
                raise Problem(400,'Unbekannte Mahlzeit oder Veranlassung.')
            if type(meal['is_meal']) is not bool or type(meal['offered']) is not bool:
                raise Problem(400,'Bereitstellung und Mahlzeitenart ausdrücklich angeben.')
            price=integer(meal['price_minor']);own=integer(meal['employee_paid_minor'])
            if own>price:raise Problem(400,'Eigenanteil übersteigt den belegten Mahlzeitenpreis.')
            root=meal;chain=set()
            while root['replacement_for'] is not None:
                previous=root['replacement_for']
                if previous in chain or previous not in by_meal:raise Problem(400,'Ersatzmahlzeit benötigt eine eindeutige zugehörige Originalmahlzeit desselben Tages.')
                chain.add(previous);root=by_meal[previous]
                if root['kind']!=kind:raise Problem(400,'Ersatzmahlzeit muss dieselbe Mahlzeitenart ersetzen.')
            if not meal['is_meal'] or not meal['offered'] or meal['provider'] in ('independent_third_party','self'):continue
            meal_groups.setdefault((kind,root['id']),[]).append(meal)
        for (kind,root),provided in meal_groups.items():
            if kind in seen_meals:
                block('replacement_meal_link_missing','Mehrere Arbeitgebermahlzeiten derselben Art benötigen eine ausdrückliche Ersatzverknüpfung.',selected['trip']);continue
            seen_meals.add(kind)
            price=sum(m['price_minor'] for m in provided);own=sum(m['employee_paid_minor'] for m in provided)
            if len(provided)>1:reasons.append(dict(code='replacement_meal_combined',text='Belegte ursprüngliche und Ersatzmahlzeit gemeinsam für 60-EUR-Grenze und eine Kürzung geprüft.',source='BMF 25.11.2020 Rz.87–89'))
            if price>6000:
                benefits+=price-own;reasons.append(dict(code='reward_meal',text='Mahlzeit über 60 EUR mit tatsächlichem Wert.',source='EStG §8 Abs.2'))
            elif unapportioned_base:
                letter_m=True
                percent=20 if kind=='breakfast' else 40
                reduction+=max(0,_round(Decimal(rr['full_minor'])*percent/100)-own)
            else:
                letter_m=True;benefits+=max(0,(237 if kind=='breakfast' else 457)-own)
        reduction=min(base,reduction);lodging=0;lodging_items=[]
        for f in group:
            night=f['night']
            if not night:continue
            if night['provided_by'] not in ('employee','employer','third_party_free') or night['claim_method'] not in ('none','flat','expense'):
                raise Problem(400,'Übernachtung und Erstattungsweg ausdrücklich wählen.')
            if night['claim_method']=='none':continue
            site=_site(night['site_ref'],sites)
            if site['details']['kind'] in ('home','first_workplace'):
                block('lodging_not_external','Übernachtungspauschale nur für tatsächliche auswärtige Übernachtung.',f['trip']);continue
            if night['provided_by']!='employee':
                block('lodging_already_provided','Bereits gestellte Unterkunft darf nicht nochmals als Pauschale erstattet werden.',f['trip']);continue
            if night['claim_method']=='expense':
                continue  # Actual evidenced costs are counted once by the expense source helper.
            accommodation=night.get('accommodation_kind');other=night.get('other_lodging_started_or_finished',False)
            if type(other) is not bool:raise Problem(400,'Beginn/Ende in anderer Unterkunft ausdrücklich als Tatsache angeben.')
            if accommodation not in ('lodging','vehicle','sleeper_train','ship_cabin'):
                block('lodging_accommodation_missing','Tatsächliche Unterkunftsart für die Übernachtungspauschale belegen.',f['trip']);continue
            if accommodation=='vehicle' or accommodation in ('sleeper_train','ship_cabin') and not other:
                block('vehicle_lodging_not_eligible','Fahrzeugübernachtung berechtigt nicht zur gewöhnlichen Übernachtungspauschale; Ausnahme für Schlafwagen/Schiffskabine gesondert belegen.',f['trip']);continue
            value=prorate_minor(rate(site['details']['rate_id'])['lodging_minor'],*f['business_share']);lodging_items.append(value)
        if len(lodging_items)>1:block('duplicate_lodging','Eine Übernachtung darf nicht mehrfach in Reisen beansprucht werden.',selected['trip'])
        lodging=max(lodging_items,default=0)
        output.append(dict(date=current,rate_id=rr['id'],country=rr['country'],region=rr['region'],
            claim_kind='short' if all_single and base else selected['claim_kind'],absence_seconds=total_absence,
            full_minor=rr['full_minor'],unapportioned_base_minor=unapportioned_base,
            business_share=dict(numerator=share[0],denominator=share[1]),base_minor=base,meal_reduction_minor=reduction,
            meal_allowance_minor=base-reduction,lodging_allowance_minor=lodging,
            benefit_in_kind_minor=benefits,letter_m=letter_m,three_month=assessment,reasons=reasons,
            sources=sorted([f['trip'] for f in group],key=lambda v:v['id'])))
    meal_cap=sum(d['meal_allowance_minor'] for d in output);lodging_cap=sum(d['lodging_allowance_minor'] for d in output)
    meal_requested=sum(integer(t['details']['requested_meal_minor']) for t in trips) if requested_meal_minor is None else integer(requested_meal_minor)
    lodging_requested=sum(integer(t['details']['requested_lodging_minor']) for t in trips) if requested_lodging_minor is None else integer(requested_lodging_minor)
    requested=meal_requested+lodging_requested+expenses['allowance_minor'];cap=meal_cap+lodging_cap+expenses['allowance_minor']
    # BMF Rz.134 permits combining the tax-free reimbursable travel allowances
    # inside the expressly reviewed settlement unit, not unrelated periods.
    tax_free=min(requested,cap);extra=requested-tax_free;flat=0;individual=0
    flat_limit=sum(d['base_minor'] for d in output if d['three_month']['eligible'])
    if extra and tax_choice=='tax_free_only':block('requested_above_tax_free','Beantragter Betrag übersteigt den belegten steuerfreien Gesamtbetrag.')
    elif extra and tax_choice=='flat_25':
        # §40(2) no.4 concerns additional meal allowances, not an arbitrary
        # taxable lodging reimbursement re-labelled after aggregate offsets.
        flat=min(extra,flat_limit,max(0,meal_requested-meal_cap));individual=extra-flat
    elif extra:individual=extra
    payroll_required=bool(flat or individual or any(d['benefit_in_kind_minor'] or d['letter_m'] for d in output))
    taxable_pending=bool(flat or individual or any(d['benefit_in_kind_minor'] for d in output))
    paid=integer(already_paid_minor)+expenses['already_paid_minor'];totals=dict(meal_base_minor=sum(d['base_minor'] for d in output),
        meal_reduction_minor=sum(d['meal_reduction_minor'] for d in output),meal_allowance_minor=meal_cap,
        lodging_allowance_minor=lodging_cap,expense_allowance_minor=expenses['allowance_minor'],expense_already_paid_minor=expenses['already_paid_minor'],requested_minor=requested,tax_free_minor=tax_free,
        flat_taxable_minor=flat,individual_taxable_minor=individual,
        benefit_in_kind_minor=sum(d['benefit_in_kind_minor'] for d in output),already_paid_minor=paid,
        remaining_minor=max(0,tax_free-paid),overpaid_minor=max(0,paid-tax_free))
    return dict(rule_version=RULE_VERSION,rule_hash=RULE_HASH,table_hash=TABLE_HASH,days=output,expense_items=expenses['items'],transport_sources=transport_sources,ground_calendar_sources=ground_sources,mixed_program_sources=mixed_sources,
                totals=totals,blockers=blockers,payroll_required=payroll_required,
                can_approve=not blockers,can_pay=not blockers and not payroll_required and totals['remaining_minor']>0)

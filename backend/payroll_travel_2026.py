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

# One explicit rollout switch. Historical kernels and table provenance remain
# unchanged when new accepted calculations start using a later rule version.
RULE_VERSION='de_travel_2026_v3'


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


def rule_metadata(rule_version=None):
    """Resolve catalog identity from the same immutable kernel as calculation."""
    version=RULE_VERSION if rule_version is None else rule_version
    if version=='de_travel_2026_v1':import payroll_travel_2026_v1 as kernel
    elif version=='de_travel_2026_v2':import payroll_travel_2026_v2 as kernel
    elif version=='de_travel_2026_v3':import payroll_travel_2026_v3 as kernel
    else:raise Problem(409,'Unbekannte historische Reiseregelversion.')
    return dict(rule_version=kernel.RULE_VERSION,rule_hash=kernel.RULE_HASH,table_hash=kernel.TABLE_HASH)


def calculate(trips,site_records,*,settlement_unit='trip',tax_choice='tax_free_only',
              requested_meal_minor=None,requested_lodging_minor=None,already_paid_minor=0,history_trips=(),rule_version=None):
    """Dispatch immutable rule versions; the active default is explicit."""
    version=RULE_VERSION if rule_version is None else rule_version
    if version=='de_travel_2026_v1':
        from payroll_travel_2026_v1 import calculate as original
    elif version=='de_travel_2026_v2':
        from payroll_travel_2026_v2 import calculate as original
    elif version=='de_travel_2026_v3':
        from payroll_travel_2026_v3 import calculate as original
    else:raise Problem(409,'Unbekannte historische Reiseregelversion.')
    return original(trips,site_records,settlement_unit=settlement_unit,tax_choice=tax_choice,
        requested_meal_minor=requested_meal_minor,requested_lodging_minor=requested_lodging_minor,
        already_paid_minor=already_paid_minor,history_trips=history_trips)

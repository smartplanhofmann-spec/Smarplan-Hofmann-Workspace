"""Actual local calendar attribution for source-bound ground journeys.

Each UTC instant belongs to the local date of its evidenced location. Repeated
date labels are merged, never counted twice; no elapsed time is invented.
"""
from datetime import timedelta
from pathlib import Path
import hashlib

from core import Problem

GROUND_RULE_VERSION='de_travel_ground_2026_v1'
GROUND_SOURCE='https://www.gesetze-im-internet.de/estg/__9.html'
GROUND_MODULE_HASH=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


def resolve_ground_calendar(trip,site_records):
    from payroll_travel_2026 import _reference,_source,zone,moment,day,_days,_bounds,_duration,sha
    details=trip['details']
    if any(s['transport']!='ground' for s in details['segments']):return None
    sites={_reference(_source(s)):s for s in site_records};start=moment(details['departed_at']);finish=moment(details['returned_at']);previous=start;pieces={};boundaries=[]
    for segment in details['segments']:
        a,b=moment(segment['from']),moment(segment['to'])
        if a!=previous or b<=a or b>finish:raise Problem(400,'Bodenreise muss die tatsächliche Zeit lückenlos und ohne Überschneidung belegen.')
        previous=b
        try:site=sites[_reference(segment['site_ref'])]
        except KeyError as error:raise Problem(409,'Genau passende Ortsfassung für die Bodentageszuordnung erforderlich.') from error
        tz=zone(site['details']['timezone']);first=a.astimezone(tz).date();last=(b-timedelta(microseconds=1)).astimezone(tz).date()
        boundaries.append(dict(segment_id=segment['id'],site_ref=segment['site_ref'],timezone=site['details']['timezone'],from_local=a.astimezone(tz).isoformat(),to_local=b.astimezone(tz).isoformat()))
        for on in _days(first,last):
            lo,hi=_bounds(on,tz);lo=max(a,lo);hi=min(b,hi)
            if hi>lo:pieces.setdefault(on.isoformat(),[]).append(dict(segment_id=segment['id'],site_ref=segment['site_ref'],timezone=site['details']['timezone'],utc_from=lo.isoformat(),utc_to=hi.isoformat()))
    if previous!=finish:raise Problem(400,'Bodenreise benötigt den vollständigen Rückkehrnachweis.')
    days={}
    for label,values in sorted(pieces.items()):
        intervals=[(moment(v['utc_from']),moment(v['utc_to'])) for v in values]
        selected=max(values,key=lambda v:moment(v['utc_to']))
        days[label]=dict(intervals=values,absence_seconds=_duration(intervals),last_site_ref=selected['site_ref'],timezone=selected['timezone'])
    if sum(v['absence_seconds'] for v in days.values())!=int((finish-start).total_seconds()):
        raise Problem(409,'Örtliche Bodentage bilden die tatsächliche Reisezeit nicht verlustfrei ab.')
    result=dict(rule_version=GROUND_RULE_VERSION,module_hash=GROUND_MODULE_HASH,source=GROUND_SOURCE,days=days,boundaries=boundaries)
    return dict(result,facts_hash=sha(dict(trip=_source(trip),details=details,sites=site_records,attribution=result)))

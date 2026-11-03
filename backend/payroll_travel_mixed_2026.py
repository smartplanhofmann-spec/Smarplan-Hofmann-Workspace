"""Documented programme shares for mixed business/private travel.

BMF25.11.2020 Rz90/example59: determine the professional allowance share
before applying the full statutory meal reduction. Ordinary rest time does
not become a private programme merely because no work was performed then.
"""
from fractions import Fraction
import hashlib
from pathlib import Path
import re

from core import Problem, canonical

MIXED_RULE_VERSION='de_travel_mixed_program_2026_v1'
MIXED_SOURCE='https://www.ihk.de/blueprint/servlet/resource/blob/5260010/6167648501baf85de6053f701b93e9b5/bmf-schreiben-25-11-2020-data.pdf'
MIXED_MODULE_HASH=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


def _ids(values):
    if (not isinstance(values,list) or not 1<=len(values)<=100
            or any(not isinstance(v,str) or not re.fullmatch('[a-f0-9]{32}',v) for v in values)
            or len(set(values))!=len(values)):
        raise Problem(400,'Eindeutige Originaldateien für die tatsächliche Programmaufteilung erforderlich.')
    return sorted(values)


def resolve_mixed_program(trip):
    from payroll_travel_2026 import moment
    d=trip['details'];assessment=d.get('mixed_assessment')
    if 'mixed_assessment' in d and assessment is None:
        raise Problem(400,'Nicht benötigte Programmaufteilung weglassen oder vollständig belegen.')
    private=[];start=moment(d['departed_at']);end=moment(d['returned_at'])
    for row in d['private_intervals']:
        if not isinstance(row,dict) or set(row)!={'from','to'}:
            raise Problem(400,'Private Reisezeit benötigt einen eindeutigen tatsächlichen Zeitraum.')
        a,b=moment(row['from']),moment(row['to'])
        if not start<=a<b<=end:raise Problem(400,'Privater Zeitraum liegt außerhalb der tatsächlichen Reise.')
        private.append((a,b))
    private.sort()
    if any(a2<b1 for (_,b1),(a2,_) in zip(private,private[1:])):
        raise Problem(400,'Private tatsächliche Zeiträume dürfen sich nicht überschneiden.')
    if assessment is None:
        return None if not private else dict(rule_version=MIXED_RULE_VERSION,
            can_calculate=False,blockers=[dict(code='mixed_travel_assessment',
            text='Gemischte Reise benötigt die belegte vollständige Programmaufteilung; Privatzeit allein bestimmt keine Quote.',source_ref=None)])
    fields={'method','program_sessions','program_complete','cost_allocation_reviewed','source_file_ids','review_note'}
    if not isinstance(assessment,dict) or set(assessment)!=fields or assessment['method']!='documented_program_ratio':
        raise Problem(400,'Die konkrete belegte Programmaufteilung der gemischten Reise auswählen.')
    if type(assessment['program_complete']) is not bool or type(assessment['cost_allocation_reviewed']) is not bool:
        raise Problem(400,'Vollständige Programm- und Auslagenprüfung ausdrücklich angeben.')
    ids=_ids(assessment['source_file_ids']);note=assessment['review_note']
    if not isinstance(note,str) or not note.strip() or len(note)>2000:
        raise Problem(400,'Die tatsächliche berufliche/private Abgrenzung begründen.')
    sessions=assessment['program_sessions']
    if not isinstance(sessions,list) or not 2<=len(sessions)<=1000:
        raise Problem(400,'Mindestens zwei begrenzte berufliche/private Programmpunkte belegen.')
    work=[(moment(s['from']),moment(s['to'])) for s in d['segments'] if s['activity']=='work']
    seen=set();ordered=[];private_program=[];totals=dict(business=0,private=0);bound=set(ids)
    def covered(a,b,intervals):
        cursor=a
        for lo,hi in sorted(intervals):
            if hi<=cursor:continue
            if lo>cursor:return False
            cursor=max(cursor,hi)
            if cursor>=b:return True
        return False
    for item in sessions:
        if (not isinstance(item,dict) or set(item)!={'id','from','to','kind','source_file_ids'}
                or not isinstance(item['id'],str) or not re.fullmatch('[a-f0-9]{32}',item['id'])
                or item['id'] in seen or item['kind'] not in totals):
            raise Problem(400,'Jeden belegten beruflichen oder privaten Programmpunkt eindeutig erfassen.')
        seen.add(item['id']);files=_ids(item['source_file_ids']);bound.update(files)
        a,b=moment(item['from']),moment(item['to'])
        if not start<=a<b<=end:raise Problem(400,'Programmpunkt liegt außerhalb der tatsächlichen Reise.')
        if item['kind']=='business':
            if not covered(a,b,work) or any(a<hi and b>lo for lo,hi in private):
                raise Problem(400,'Beruflicher Programmpunkt benötigt tatsächlichen Arbeitsabschnitt ohne private Zeit.')
        elif not covered(a,b,private):
            raise Problem(400,'Privater Programmpunkt muss durch die tatsächlichen privaten Zeiträume belegt sein.')
        if item['kind']=='private':private_program.append((a,b))
        totals[item['kind']]+=int((b-a).total_seconds())
        ordered.append((a,b,item['id']))
    ordered.sort()
    if any(a2<b1 for (_,b1,_),(a2,_,_) in zip(ordered,ordered[1:])):
        raise Problem(400,'Programmpunkte dürfen nicht doppelt oder gleichzeitig angerechnet werden.')
    if not totals['business'] or not totals['private']:
        raise Problem(400,'Gemischtes Programm benötigt belegte berufliche und private Bestandteile.')
    fraction=Fraction(totals['business'],sum(totals.values()));blockers=[]
    if any(not covered(a,b,private_program) for a,b in private):
        blockers.append(dict(code='mixed_private_program_missing',text='Alle ausdrücklich privaten Zeiträume müssen dem belegten Programm zugeordnet sein; gesonderte Urlaubsverlängerungen benötigen eine eigene Abgrenzung.',source_ref=None))
    if not assessment['program_complete']:
        blockers.append(dict(code='mixed_program_incomplete',text='Die vollständigen maßgeblichen Programmpunkte müssen geprüft sein.',source_ref=None))
    if not assessment['cost_allocation_reviewed']:
        blockers.append(dict(code='mixed_cost_allocation_unreviewed',text='Direkt zuordenbare und gemeinsame Originalkosten getrennt prüfen.',source_ref=None))
    value=dict(rule_version=MIXED_RULE_VERSION,module_hash=MIXED_MODULE_HASH,source=MIXED_SOURCE,
        method=assessment['method'],business_seconds=totals['business'],private_seconds=totals['private'],
        numerator=fraction.numerator,denominator=fraction.denominator,source_file_ids=sorted(bound),
        can_calculate=not blockers,blockers=blockers)
    return dict(value,facts_hash=hashlib.sha256(canonical(dict(trip={k:trip[k] for k in ('id','revision','content_hash')},
        assessment=assessment,private_intervals=d['private_intervals'],segments=d['segments'],result=value)).encode()).hexdigest())


def prorate_minor(amount,numerator,denominator):
    if any(type(v) is not int for v in (amount,numerator,denominator)) or not 0<=amount<=10**12 or not 0<=numerator<=denominator or denominator<1:
        raise Problem(400,'Ganzzahligen belegten Betrag und tatsächliche Programmquote angeben.')
    # Half-up only at the final daily EUR-cent boundary; no floating point.
    return (amount*numerator*2+denominator)//(denominator*2)

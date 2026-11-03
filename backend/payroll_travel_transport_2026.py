"""Source-bound 2026 transport rules, independent of storage and payroll.

R 9.6(3) LStR: actual landings, necessary stopover nights, Austrian long-flight
days, Luxembourg sea days and port/qualifying German crew exceptions.
No input contains a requested country rate or tax amount.
"""
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
import hashlib
import json
import re

from core import Problem
from payroll_travel_rates_2026 import TABLE_HASH, country_rate, rate

TRANSPORT_RULE_VERSION = 'de_travel_transport_2026_v1'
TRANSPORT_SOURCE = ('https://amtliche-handbuecher.bundesfinanzministerium.de/lsth/2026/'
    'A-Einkommensteuergesetz/II-Einkommen-2-24b/4-Ueberschuss-d-Einnahmen-ueber-die-Werbungsk-8-9a/'
    'Paragraf-9/r-9-6.html')


def _sha(value):
    return hashlib.sha256(json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()


TRAVEL_TRANSPORT_HASH = _sha(dict(version=TRANSPORT_RULE_VERSION,table_hash=TABLE_HASH,
    source=TRANSPORT_SOURCE,module_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()))


def _fail(message):
    raise Problem(400,message)


def _shape(value,keys):
    if not isinstance(value,dict) or set(value)!=set(keys.split()):
        _fail('Transportnachweis benötigt genau die dokumentierten Tatsachenfelder.')


def _id(value):
    if not isinstance(value,str) or not re.fullmatch('[a-f0-9]{32}',value):
        _fail('Eindeutige Transport- oder Abschnitts-ID erforderlich.')
    return value


def _ids(value,*,nonempty=True):
    if not isinstance(value,list) or len(value)>1000 or nonempty and not value:
        _fail('Begrenzte Liste der Transportnachweise erforderlich.')
    result=[_id(item) for item in value]
    if len(set(result))!=len(result):_fail('Transportnachweis darf keine doppelten Referenzen enthalten.')
    return result


def _ref(value):
    _shape(value,'id revision content_hash');_id(value['id'])
    if type(value['revision']) is not int or value['revision']<1 or not isinstance(value['content_hash'],str) or not re.fullmatch('[a-f0-9]{64}',value['content_hash']):
        _fail('Genaue unveränderliche Stättenfassung erforderlich.')
    return value['id'],value['revision'],value['content_hash']


def _instant(value):
    if not isinstance(value,str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(?::\d{2})?(?:Z|[+-]\d{2}:\d{2})',value):
        _fail('Transportzeitpunkt mit ausdrücklichem UTC-Offset erforderlich.')
    try:return datetime.fromisoformat(value.replace('Z','+00:00')).astimezone(timezone.utc)
    except ValueError:_fail('Ungültiger Transportzeitpunkt.')


def _zone(value):
    try:return ZoneInfo(value)
    except (ValueError,TypeError,ZoneInfoNotFoundError):_fail('Belegte Ortszeitzone erforderlich.')


def _dates(first,last):
    while first<=last:
        yield first
        first+=timedelta(days=1)


def _bounds(day,tz):
    begin=datetime.combine(day,datetime.min.time(),tzinfo=tz)
    return begin.astimezone(timezone.utc),(begin+timedelta(days=1)).astimezone(timezone.utc)


def resolve_transport_days(trip,site_records):
    """Resolve actual transport countries and local calendar boundaries.

    Return days keyed once per local calendar date. ``calendar_days`` describes
    the statutory local dates, not additive UTC durations. A repeated local date
    has one result determined by the last actually reached relevant place.
    Blockers prohibit approval; they never silently choose an input tax rate.
    """
    details=trip['details'];facts=details.get('transport_facts',[])
    if not isinstance(facts,list) or len(facts)>100:_fail('Höchstens hundert strukturierte Transportnachweise erforderlich.')
    sites={_ref({k:s[k] for k in ('id','revision','content_hash')}):s for s in
           (site_records.values() if isinstance(site_records,dict) else site_records)}
    def site(reference):
        key=_ref(reference)
        if key not in sites:raise Problem(409,'Genau passende Flughafen-/Hafenfassung fehlt.')
        value=sites[key];rate(value['details']['rate_id']);_zone(value['details']['timezone'])
        return value
    def local(instant,place):return instant.astimezone(_zone(place['details']['timezone'])).date()
    def transport_site(reference):
        value=site(reference)
        if value['details']['kind']=='home':
            _fail('Eine Wohnung ist kein belegter Flughafen oder Hafen.')
        return value
    begin=_instant(details['departed_at']);finish=_instant(details['returned_at'])
    if finish<=begin:_fail('Belegte Reise muss eine positive Dauer besitzen.')
    if not isinstance(details['segments'],list) or not 1<=len(details['segments'])<=1000:
        _fail('Begrenzte vollständige Reiseabschnittsliste erforderlich.')
    segments=[];by_id={};previous=begin
    for number,item in enumerate(details['segments']):
        ident=_id(item['id'])
        if ident in by_id:_fail('Abschnitts-ID ist innerhalb der Reise doppelt.')
        start,finish=_instant(item['from']),_instant(item['to'])
        if finish<=start or start!=previous:_fail('Transportabschnitte müssen die Reise lückenlos in tatsächlicher Reihenfolge abdecken.')
        previous=finish
        record=dict(value=item,index=number,start=start,finish=finish,site=site(item['site_ref']))
        by_id[ident]=record;segments.append(record)
    finish=_instant(details['returned_at'])
    if previous!=finish:_fail('Transportabschnitte stimmen nicht mit der belegten Rückkehr überein.')
    nights={}
    for item in details.get('overnights',[]):
        ident=_id(item['id'])
        if ident in nights:_fail('Übernachtungs-ID darf nur einmal vorkommen.')
        nights[ident]=item
    blockers=[];candidates={};port_candidates={};covered=set();fact_ids=set();ignored_ground=set();transport_dates=set()
    def block(code,text,source):
        item=dict(code=code,text=text,source_ref=source)
        if item not in blockers:blockers.append(item)
    def site_at(place,instant):
        on=local(instant,place).isoformat();d=place['details']
        if on<d['effective_from'] or d['effective_to'] is not None and on>d['effective_to']:
            block('transport_site_validity','Flughafen-/Hafennachweis gilt nicht am tatsächlichen Transportdatum.',
                  {k:place[k] for k in ('id','revision','content_hash')})
    def candidate(on,place,instant,reason,source,*,rate_id=None,port=False):
        key=on.isoformat();transport_dates.add(key)
        item=dict(rate_id=rate_id or place['details']['rate_id'],reason=reason,source=source,
                  timezone=place['details']['timezone'],instant=instant)
        (port_candidates if port else candidates).setdefault(key,[]).append(item)
    def source(fact,ids,**extra):
        return dict(kind=fact['kind'],transport_id=fact['id'],segment_ids=ids,
                    source_file_ids=fact['source_file_ids'],**extra)
    def take(ident,kind):
        _id(ident)
        if ident not in by_id or by_id[ident]['value']['transport']!=kind:
            _fail('Transportnachweis bindet keinen passenden tatsächlichen Reiseabschnitt.')
        if ident in covered:_fail('Transportabschnitt ist mehreren Nachweisen zugeordnet.')
        covered.add(ident);return by_id[ident]
    for fact in facts:
        if not isinstance(fact,dict):_fail('Strukturierter Transportnachweis erforderlich.')
        _id(fact.get('id'))
        if fact['id'] in fact_ids:_fail('Transportnachweis-ID ist doppelt.')
        fact_ids.add(fact['id']);_ids(fact.get('source_file_ids'))
        if fact.get('kind')=='flight':
            _shape(fact,'id kind legs stopovers source_file_ids')
            if not isinstance(fact['legs'],list) or not 1<=len(fact['legs'])<=100:
                _fail('Ein bis hundert tatsächliche Flugabschnitte pro Flugverbindung erforderlich.')
            legs=[]
            for leg in fact['legs']:
                _shape(leg,'segment_id departure_site_ref arrival_site_ref')
                seg=take(leg['segment_id'],'flight')
                departure,arrival=transport_site(leg['departure_site_ref']),transport_site(leg['arrival_site_ref'])
                site_at(departure,seg['start']);site_at(arrival,seg['finish'])
                legs.append(dict(segment=seg,departure=departure,arrival=arrival,leg=leg))
            if not isinstance(fact['stopovers'],list) or len(fact['stopovers'])>=len(legs):
                _fail('Notwendige Zwischenübernachtungen müssen zwischen Flugabschnitten liegen.')
            stops={};used_nights=set()
            for stop in fact['stopovers']:
                _shape(stop,'after_segment_id overnight_ids');_id(stop['after_segment_id']);_ids(stop['overnight_ids'])
                if stop['after_segment_id'] in stops:_fail('Zwischenübernachtung ist doppelt zugeordnet.')
                stops[stop['after_segment_id']]=stop['overnight_ids']
            valid_stop_ids={leg['leg']['segment_id'] for leg in legs[:-1]}
            if not set(stops)<=valid_stop_ids:_fail('Zwischenübernachtung gehört nicht zwischen die angegebenen Flüge.')
            phases=[];phase_start=legs[0]['segment']['start'];phase_place=legs[0]['departure']
            for pos,leg in enumerate(legs):
                seg=leg['segment'];ident=leg['leg']['segment_id']
                if pos:
                    previous=legs[pos-1]
                    if seg['index']<=previous['segment']['index'] or seg['start']<previous['segment']['finish']:
                        _fail('Flugabschnitte müssen in tatsächlicher zeitlicher Reihenfolge stehen.')
                if pos==len(legs)-1:
                    phases.append((phase_start,phase_place,seg['finish'],leg['arrival'],[x['leg']['segment_id'] for x in legs]))
                    continue
                following=legs[pos+1];gap=segments[seg['index']+1:following['segment']['index']]
                expected=seg['finish']
                for item in gap:
                    if item['start']!=expected or item['value']['transport']!='ground' or item['value']['activity'] not in ('transit','stay'):
                        _fail('Flugverbindung benötigt lückenlos belegte Transfer-/Aufenthaltsabschnitte ohne Zwischentätigkeit.')
                    expected=item['finish']
                if expected!=following['segment']['start']:_fail('Flugverbindung enthält eine zeitlich unbelegte Anschlusslücke.')
                night_ids=stops.get(ident,[])
                if night_ids:
                    for night_id in night_ids:
                        if night_id in used_nights or night_id not in nights:_fail('Zwischenübernachtung benötigt eine eindeutige tatsächliche Nacht.')
                        used_nights.add(night_id);night=nights[night_id];place=site(night['site_ref'])
                        try:on=datetime.strptime(night['date'],'%Y-%m-%d').date()
                        except (TypeError,ValueError):_fail('Gültiges Datum der Zwischenübernachtung erforderlich.')
                        midnight=_bounds(on,_zone(place['details']['timezone']))[1]
                        matching=[item for item in gap if item['value']['activity']=='stay'
                            and _ref(item['value']['site_ref'])==_ref(night['site_ref'])
                            and item['value']['necessary_stopover'] is True and item['start']<midnight<=item['finish']]
                        if not matching or place['details']['kind'] in ('home','first_workplace'):
                            _fail('Notwendige Zwischenübernachtung ist nicht durch einen passenden Außenaufenthalt über Mitternacht belegt.')
                    phases.append((phase_start,phase_place,seg['finish'],leg['arrival'],[x['leg']['segment_id'] for x in legs[:pos+1]]))
                    phase_start=following['segment']['start'];phase_place=following['departure']
                else:
                    ignored_ground.update(item['value']['id'] for item in gap)
                    if any(item['value']['necessary_stopover'] is True for item in gap):
                        block('transport_stopover_night_missing','Notwendige Zwischenübernachtung muss mit der tatsächlichen Nacht verknüpft sein.',source(fact,[ident]))
            for start,departure,finish,arrival,ids in phases:
                first,last=local(start,departure),local(finish,arrival)
                candidate(first,departure,start,'flight_departure_before_landing',source(fact,ids,site_ref={k:departure[k] for k in ('id','revision','content_hash')}))
                for on in _dates(first+timedelta(days=1),last-timedelta(days=1)):
                    # Statutory flight calendar days; they are not inferred by
                    # adding 24 hours to the actual elapsed flight duration.
                    end=_bounds(on,_zone(departure['details']['timezone']))[1]
                    candidate(on,departure,min(end,finish),'flight_intermediate_austria',source(fact,ids),rate_id=country_rate('Österreich')['id'])
                candidate(last,arrival,finish,'flight_actual_landing',source(fact,ids,site_ref={k:arrival[k] for k in ('id','revision','content_hash')}))
        elif fact.get('kind')=='ship':
            _shape(fact,'id kind segment_ids departure_site_ref arrival_site_ref role high_seas_segment_ids source_file_ids')
            ids=_ids(fact['segment_ids']);high=set(_ids(fact['high_seas_segment_ids'],nonempty=False))
            if not high<=set(ids):_fail('Hochseeabschnitt gehört nicht zur belegten Schiffsreise.')
            if fact['role'] not in ('passenger','german_state_crew','german_merchant_crew'):
                _fail('Nachgewiesenen Passagier- oder Besatzungsstatus auswählen.')
            voyage=[take(ident,'ship') for ident in ids]
            if any(a['finish']!=b['start'] or a['index']+1!=b['index'] for a,b in zip(voyage,voyage[1:])):
                _fail('Schiffsabschnitte müssen die Fahrt lückenlos und geordnet abdecken.')
            departure,arrival=transport_site(fact['departure_site_ref']),transport_site(fact['arrival_site_ref'])
            start,finish=voyage[0]['start'],voyage[-1]['finish'];first,last=local(start,departure),local(finish,arrival)
            site_at(departure,start);site_at(arrival,finish)
            tz=_zone(departure['details']['timezone'])
            for on in _dates(min(first,last),max(first,last)):
                lo,hi=_bounds(on,tz);active=[item for item in voyage if item['start']<hi and item['finish']>lo]
                if not active:continue
                high_seas=all(item['value']['id'] in high for item in active)
                domestic=fact['role']!='passenger' and high_seas
                selected=country_rate('Deutschland' if domestic else 'Luxemburg')
                candidate(on,departure,min(hi,finish),'ship_german_crew_high_seas' if domestic else 'ship_luxembourg',
                    source(fact,ids,role=fact['role'],high_seas_segment_ids=sorted(high)),rate_id=selected['id'])
            candidate(first,departure,start,'ship_embarkation_port',source(fact,ids,site_ref=fact['departure_site_ref']),port=True)
            candidate(last,arrival,finish,'ship_disembarkation_port',source(fact,ids,site_ref=fact['arrival_site_ref']),port=True)
        else:_fail('Bekannten Flug- oder Schiffsnachweis auswählen.')
    required={item['value']['id'] for item in segments if item['value']['transport'] in ('flight','ship')}
    for ident in sorted(required-covered):
        block('transport_facts_missing','Für diesen Flug-/Schiffsabschnitt fehlen die tatsächlichen Flug-/Hafenangaben.',dict(segment_id=ident))
    # All actual ground places compete by real chronological order. This also
    # folds a repeated local date after a westbound dateline crossing once.
    for seg in segments:
        if seg['value']['transport']!='ground' or seg['value']['id'] in ignored_ground:continue
        place=seg['site'];tz=_zone(place['details']['timezone'])
        first,last=local(seg['start'],place),local(seg['finish']-timedelta(microseconds=1),place)
        for on in _dates(first,last):
            if on.isoformat() not in transport_dates:continue
            instant=min(seg['finish'],_bounds(on,tz)[1])-timedelta(microseconds=1)
            candidate(on,place,instant,'actual_ground_place',dict(segment_id=seg['value']['id'],site_ref=seg['value']['site_ref']))
    homezone=_zone(details['timezone']);begin=_instant(details['departed_at']);finish=_instant(details['returned_at'])
    first,last=begin.astimezone(homezone).date(),finish.astimezone(homezone).date();days={};calendar=[]
    for label in sorted(transport_dates):
        on=datetime.strptime(label,'%Y-%m-%d').date();values=port_candidates.get(label) or candidates.get(label,[])
        if not values:continue
        selected=max(values,key=lambda value:value['instant'])
        if not port_candidates.get(label) and (first==last or on==last):
            work=[seg for seg in segments if seg['value']['activity']=='work' and seg['start']<finish
                  and (first!=last or local(seg['start'],seg['site'])<=on<=local(seg['finish']-timedelta(microseconds=1),seg['site']))]
            foreign=[seg for seg in work if rate(seg['site']['details']['rate_id'])['country']!='Deutschland']
            if foreign and (first==last or rate(selected['rate_id'])['country']=='Deutschland'):
                actual=foreign[-1]
                selected=dict(rate_id=actual['site']['details']['rate_id'],reason='last_foreign_workplace_return',
                    source=dict(segment_id=actual['value']['id'],site_ref=actual['value']['site_ref']),
                    timezone=actual['site']['details']['timezone'],instant=actual['finish'])
        if not first<=on<=last:
            block('transport_calendar_outside_trip','Ein örtlicher Transporttag liegt außerhalb der belegten Reisetage; Abreise-/Rückkehr- und Ortsdatumsnachweise gemeinsam prüfen.',selected['source'])
        days[label]={k:v for k,v in selected.items() if k!='instant'}
        lo,hi=_bounds(on,_zone(selected['timezone']))
        calendar.append(dict(date=label,timezone=selected['timezone'],utc_from=lo.isoformat(),utc_to=hi.isoformat(),
            elapsed_overlap_seconds=max(0,int((min(finish,hi)-max(begin,lo)).total_seconds())),
            attribution='one_local_calendar_date',source=selected['source']))
    frozen=dict(trip={k:trip.get(k) for k in ('id','revision','content_hash')},details=details,
                sites=sorted(sites.values(),key=lambda item:(item['id'],item['revision'])),
                transport_rule_version=TRANSPORT_RULE_VERSION,transport_rule_hash=TRAVEL_TRANSPORT_HASH,
                days=days,calendar_days=calendar,blockers=blockers)
    return dict(days=days,calendar_days=calendar,blockers=blockers,facts_hash=_sha(frozen),
                transport_rule_version=TRANSPORT_RULE_VERSION,transport_rule_hash=TRAVEL_TRANSPORT_HASH)

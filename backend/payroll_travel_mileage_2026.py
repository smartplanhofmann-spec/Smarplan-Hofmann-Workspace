"""Explicit, bounded employee private-car reimbursement; no payment effects.

Only this new rule accepts mileage facts. Historical travel kernels are not
called or changed. The caller verifies the actual stored originals and current
permissions; this pure kernel binds their identities and documented facts.
"""
import hashlib
from pathlib import Path
import re

from core import Problem, canonical
from payroll_travel_2026 import day, moment


RULE_VERSION = 'de_travel_2026_v4_private_car'
RATE_MINOR_PER_KM = 30
RATE_TABLE = dict(effective_from='2026-01-01', effective_to='2026-12-31',
                  country='Deutschland', vehicle_kind='private_car',
                  metres_per_km=1000, rate_minor_per_km=RATE_MINOR_PER_KM)
TABLE_HASH = hashlib.sha256(canonical(RATE_TABLE).encode()).hexdigest()
SOURCES = (
    'https://www.gesetze-im-internet.de/estg/__9.html',
    'https://www.gesetze-im-internet.de/brkg_2005/__5.html',
    'https://www.gesetze-im-internet.de/estg/__3.html',
    'https://amtliche-handbuecher.bundesfinanzministerium.de/lsth/2026/A-Einkommensteuergesetz/II-Einkommen-2-24b/4-Ueberschuss-d-Einnahmen-ueber-die-Werbungsk-8-9a/Paragraf-9/inhalt.html',
)
RULES = dict(version=RULE_VERSION, table_hash=TABLE_HASH, sources=SOURCES,
             scope='ONE_EMPLOYEE_ONE_2026_BERLIN_DAY_PRIVATE_CAR_BUSINESS_ROUND_TRIP',
             rounding='HALF_UP_ON_SUM_OF_WHOLE_METRES_ONCE',
             payroll='NO_NET_ADDITION_NO_M_NO_TAXABLE_PAYMENT',
             module_sha256=hashlib.sha256(Path(__file__).read_bytes().replace(b'\r\n', b'\n')).hexdigest())
RULE_HASH = hashlib.sha256(canonical(RULES).encode()).hexdigest()

DECLARATIONS = (
    'employee_bears_vehicle_costs', 'no_employer_vehicle',
    'only_business_travel', 'no_commuting_or_family_home',
    'no_collection_point_or_wide_area', 'no_other_reimbursement',
)
_DECLARATION_TEXT = {
    'employee_bears_vehicle_costs': 'Selbst getragene Fahrzeugkosten sind noch nicht bestätigt.',
    'no_employer_vehicle': 'Das Fehlen eines arbeitgeberseitig gestellten Fahrzeugs ist noch nicht bestätigt.',
    'only_business_travel': 'Die ausschließlich dienstliche Fahrt ist noch nicht bestätigt.',
    'no_commuting_or_family_home': 'Der Ausschluss von Pendel- und Familienheimfahrten ist noch nicht bestätigt.',
    'no_collection_point_or_wide_area': 'Der Ausschluss von Sammelpunkt und weiträumigem Tätigkeitsgebiet ist noch nicht bestätigt.',
    'no_other_reimbursement': 'Das Fehlen einer anderweitigen Erstattung ist noch nicht bestätigt.',
}
_DETAIL_FIELDS = {'purpose', 'project_id', 'departed_at', 'returned_at', 'timezone',
                  'home_site_ref', 'first_workplace_ref', 'source_file_ids', 'mileage'}
_MILEAGE_FIELDS = {'schema_version', 'vehicle_kind', 'vehicle_registration',
                   'vehicle_file_id', 'declaration_file_id', 'legs', 'review_note', *DECLARATIONS}
_LEG_FIELDS = {'id', 'departed_at', 'arrived_at', 'from_site_ref', 'to_site_ref',
               'distance_m', 'evidence_file_id'}


def _fail(message):
    raise Problem(400, message)


def _shape(value, fields):
    if not isinstance(value, dict) or set(value) != fields:
        _fail('Vollständige unveränderte Kilometerfelder erforderlich.')


def _integer(value, minimum=0, maximum=10**12):
    if type(value) is not int or not minimum <= value <= maximum:
        _fail('Ganze Zahl im unterstützten Kilometerbereich erforderlich.')
    return value


def _id(value):
    if not isinstance(value, str) or re.fullmatch('[a-f0-9]{32}', value) is None:
        _fail('Eindeutige Originalkennung erforderlich.')
    return value


def _hash(value):
    if not isinstance(value, str) or re.fullmatch('[a-f0-9]{64}', value) is None:
        _fail('Unveränderlicher Originalhash erforderlich.')
    return value


def _text(value, maximum):
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        _fail('Vollständiger begrenzter Originaltext erforderlich.')
    try:
        value.encode('utf-8')
    except UnicodeEncodeError:
        _fail('Originaltext benötigt gültige Unicode-Zeichen.')
    return value


def _ref(value):
    _shape(value, {'id', 'revision', 'content_hash'})
    return _id(value['id']), _integer(value['revision'], 1), _hash(value['content_hash'])


def _record_ref(value):
    if not isinstance(value, dict):
        _fail('Gespeicherte Kilometerquelle erforderlich.')
    try:
        ref = {key: value[key] for key in ('id', 'revision', 'content_hash')}
    except KeyError:
        _fail('Vollständige Originalquellenkennung erforderlich.')
    _ref(ref)
    return ref


def _source_files(trip, details, employee_id):
    ids = details['source_file_ids']
    if (not isinstance(ids, list) or not 1 <= len(ids) <= 100
            or any(not isinstance(value, str) for value in ids)):
        _fail('Ein bis hundert private Personaloriginale erforderlich.')
    for value in ids:
        _id(value)
    if len(set(ids)) != len(ids):
        _fail('Personaloriginale dürfen nicht doppelt angegeben werden.')
    sources = trip.get('sources')
    if not isinstance(sources, dict) or not isinstance(sources.get('files'), list):
        _fail('Gespeicherte private Personaloriginale fehlen.')
    files = {}
    for value in sources['files']:
        if not isinstance(value, dict):
            _fail('Vollständiges privates Personaloriginal erforderlich.')
        ident = _id(value.get('id'))
        if (ident in files or value.get('employee_id') != employee_id
                or value.get('purpose') != 'personnel'):
            _fail('Private Originale müssen eindeutig derselben Person gehören.')
        _hash(value.get('sha256'))
        files[ident] = value
    if not set(ids) <= set(files):
        _fail('Alle genannten Personaloriginale unverändert binden.')
    return {key: files[key] for key in ids}


def calculate(trips, site_records, *, settlement_unit='trip', tax_choice='tax_free_only',
              requested_meal_minor=0, requested_lodging_minor=0, already_paid_minor=0,
              history_trips=(), rule_version=None):
    """Return exact totals for one evidenced business round trip.

    ``history_trips`` is accepted only for the shared travel-call signature;
    it is never added to the selected journey. The application owns the
    exclusive employee/day claim and the actual-payment journal.
    """
    if rule_version not in (None, RULE_VERSION):
        _fail('Den ausdrücklich neuen Kilometerregelvertrag verwenden.')
    if not isinstance(trips, list) or len(trips) != 1 or settlement_unit != 'trip':
        _fail('Genau eine Kilometerfahrt als einzelne Abrechnung erforderlich.')
    if (tax_choice != 'tax_free_only'
            or _integer(requested_meal_minor) != 0
            or _integer(requested_lodging_minor) != 0):
        _fail('Dieser Kilometerfall enthält ausschließlich die steuerfreie Fahrtstrecke.')
    _integer(already_paid_minor)
    if not isinstance(history_trips, (list, tuple)):
        _fail('Gespeicherte Reisevorgeschichte muss eine Liste sein.')
    trip = trips[0]
    trip_ref = _record_ref(trip)
    employee_id = _id(trip.get('employee_id'))
    if trip.get('rule_version') != RULE_VERSION:
        _fail('Die Quelle ist keine ausdrücklich neue Kilometerfahrt.')
    details = trip.get('details')
    _shape(details, _DETAIL_FIELDS)
    _text(details['purpose'], 1000)
    if details['project_id'] is not None:
        _id(details['project_id'])
    if details['timezone'] != 'Europe/Berlin':
        _fail('Dieser Vertrag benötigt den tatsächlichen Inlandstag in Europe/Berlin.')
    start = moment(details['departed_at'], 'Europe/Berlin')
    finish = moment(details['returned_at'], 'Europe/Berlin')
    from zoneinfo import ZoneInfo
    local_day = start.astimezone(ZoneInfo('Europe/Berlin')).date()
    if (finish <= start or local_day.year != 2026
            or finish.astimezone(ZoneInfo('Europe/Berlin')).date() != local_day):
        _fail('Eine vollständige Fahrt an genau einem Kalendertag 2026 erforderlich.')
    files = _source_files(trip, details, employee_id)
    mileage = details['mileage']
    _shape(mileage, _MILEAGE_FIELDS)
    if type(mileage['schema_version']) is not int or mileage['schema_version'] != 1:
        _fail('Bekannte Kilometerquellenfassung erforderlich.')
    if mileage['vehicle_kind'] != 'private_car':
        _fail('Dieser Vertrag unterstützt ausschließlich einen privat gestellten Pkw.')
    _text(mileage['vehicle_registration'], 32)
    _text(mileage['review_note'], 2000)
    for key in DECLARATIONS:
        if type(mileage[key]) is not bool:
            _fail('Kilometererklärungen benötigen ausdrückliche Wahrheitswerte.')

    def file_id(value):
        _id(value)
        if value not in files:
            _fail('Jeder Fahrzeug-, Erklärungs- und Streckenbeleg muss vollständig gebunden sein.')
        return value

    file_id(mileage['vehicle_file_id'])
    file_id(mileage['declaration_file_id'])
    if not isinstance(site_records, list) or not 1 <= len(site_records) <= 102:
        _fail('Begrenzte unveränderliche Stättenquellen erforderlich.')
    sites = {}
    for record in site_records:
        ref = _record_ref(record)
        ident = ref['id']
        if ident in sites:
            _fail('Jede Stätte muss in genau einer ursprünglichen Fassung vorliegen.')
        if record.get('employee_id') != employee_id or record.get('status') != 'active':
            _fail('Aktive ursprüngliche Stätte derselben Person erforderlich.')
        sd = record.get('details')
        if (not isinstance(sd, dict) or sd.get('kind') not in ('home', 'first_workplace', 'external_fixed')
                or sd.get('rate_id') != 'de_2026' or sd.get('timezone') != 'Europe/Berlin'):
            _fail('Nur belegte inländische Wohnung, erste Tätigkeitsstätte und feste Auswärtsstätte sind unterstützt.')
        valid_from = day(sd.get('effective_from'))
        valid_to = day(sd['effective_to']) if sd.get('effective_to') is not None else None
        if local_day < valid_from or valid_to is not None and (valid_to < valid_from or local_day > valid_to):
            _fail('Die ursprüngliche Stätte gilt nicht am tatsächlichen Fahrttag.')
        sites[ident] = record

    def site(value):
        ident, revision, content_hash = _ref(value)
        record = sites.get(ident)
        if record is None or record['revision'] != revision or record['content_hash'] != content_hash:
            _fail('Genau die gebundene ursprüngliche Stättenfassung auswählen.')
        return record

    home = site(details['home_site_ref'])
    if home['details']['kind'] != 'home':
        _fail('Die gebundene Wohnung muss als Wohnung eingeordnet sein.')
    first = None
    if details['first_workplace_ref'] is not None:
        first = site(details['first_workplace_ref'])
        if first['details']['kind'] != 'first_workplace':
            _fail('Die erste Tätigkeitsstätte muss ausdrücklich so eingeordnet sein.')
    base_ids = {home['id']} | ({first['id']} if first is not None else set())
    legs = mileage['legs']
    if not isinstance(legs, list) or not 1 <= len(legs) <= 100:
        _fail('Eine bis hundert geordnete tatsächliche Teilstrecken erforderlich.')
    items, seen, total_distance = [], set(), 0
    previous_site, previous_arrival, base = None, None, None
    for index, leg in enumerate(legs):
        _shape(leg, _LEG_FIELDS)
        ident = _id(leg['id'])
        if ident in seen:
            _fail('Eine Teilstrecke darf nicht mehrfach in der Fahrt vorkommen.')
        seen.add(ident)
        departure = moment(leg['departed_at'], 'Europe/Berlin')
        arrival = moment(leg['arrived_at'], 'Europe/Berlin')
        if (arrival <= departure or departure < start or arrival > finish
                or previous_arrival is not None and departure < previous_arrival):
            _fail('Teilstrecken müssen zeitlich geordnet innerhalb der tatsächlichen Fahrt liegen.')
        origin, destination = site(leg['from_site_ref']), site(leg['to_site_ref'])
        if origin['id'] == destination['id']:
            _fail('Eine gefahrene Teilstrecke benötigt unterschiedliche belegte Endpunkte.')
        if index == 0:
            if origin['id'] not in base_ids or departure != start:
                _fail('Die Fahrt muss am gebundenen Ausgangsort zur angegebenen Abfahrt beginnen.')
            base = origin['id']
        elif origin['id'] != previous_site:
            _fail('Die Ortsfolge der tatsächlichen Fahrt muss lückenlos sein.')
        if index == len(legs) - 1:
            if destination['id'] != base or arrival != finish:
                _fail('Die Rundfahrt muss zur angegebenen Rückkehr am selben Ausgangsort enden.')
        elif destination['details']['kind'] != 'external_fixed':
            _fail('Zwischenpunkte müssen belegte feste Auswärtsstätten sein.')
        if index > 0 and origin['details']['kind'] != 'external_fixed':
            _fail('Die andere Wohnung oder erste Tätigkeitsstätte darf nicht als Umweg auftreten.')
        if origin['details']['kind'] != 'external_fixed' and destination['details']['kind'] != 'external_fixed':
            _fail('Pendel- und Familienheimfahrten sind in diesem Vertrag ausgeschlossen.')
        distance = _integer(leg['distance_m'], 1, 2_000_000)
        evidence = file_id(leg['evidence_file_id'])
        items.append(dict(trip_ref=dict(trip_ref), leg_id=ident,
                          from_site_ref=dict(leg['from_site_ref']), to_site_ref=dict(leg['to_site_ref']),
                          distance_m=distance, rate_minor_per_km=RATE_MINOR_PER_KM,
                          evidence_file_id=evidence, evidence_sha256=files[evidence]['sha256']))
        total_distance += distance
        previous_site, previous_arrival = destination['id'], arrival
    amount = (total_distance * RATE_MINOR_PER_KM + 500) // 1000
    blockers = [dict(code='mileage_' + key + '_missing', text=_DECLARATION_TEXT[key],
                     source_ref=dict(trip_ref)) for key in DECLARATIONS if not mileage[key]]
    totals = dict(meal_base_minor=0, meal_reduction_minor=0, meal_allowance_minor=0,
                  lodging_allowance_minor=0, expense_allowance_minor=0, expense_already_paid_minor=0,
                  requested_minor=amount, tax_free_minor=amount, flat_taxable_minor=0,
                  individual_taxable_minor=0, benefit_in_kind_minor=0,
                  already_paid_minor=already_paid_minor, remaining_minor=max(0, amount-already_paid_minor),
                  overpaid_minor=max(0, already_paid_minor-amount),
                  mileage_distance_m=total_distance, mileage_allowance_minor=amount)
    daily = dict(date=local_day.isoformat(), country='Deutschland', base_minor=0,
                 meal_reduction_minor=0, meal_allowance_minor=0, lodging_allowance_minor=0,
                 benefit_in_kind_minor=0, letter_m=False, mileage_allowance_minor=amount)
    return dict(rule_version=RULE_VERSION, rule_hash=RULE_HASH, table_hash=TABLE_HASH,
                days=[daily], expense_items=[], transport_sources=[], ground_calendar_sources=[],
                mixed_program_sources=[], mileage_items=items, totals=totals, blockers=blockers,
                payroll_required=False, can_approve=not blockers,
                can_pay=not blockers and totals['remaining_minor'] > 0)

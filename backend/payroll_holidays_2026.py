"""Explicit 2026 state holidays. Local-only exceptions require another fact.

Provenance and known bad comparison table: CRM_ERP_LOHN_ANSPRUECHE_2026.md.
Sunday rest or a bank closing day is not automatically an EntgFG holiday.
"""
import hashlib
from core import Problem,canonical
from payroll_de_2026 import day

STATES=frozenset('BW BY BE BB HB HH HE MV NI NW RP SL SN ST SH TH'.split())
HOLIDAYS={
    '2026-01-01':('new_year',tuple(sorted(STATES))),
    '2026-01-06':('epiphany',('BW','BY','ST')),
    '2026-03-08':('international_womens_day',('BE','MV')),
    '2026-04-03':('good_friday',tuple(sorted(STATES))),
    '2026-04-05':('easter_sunday',('BB',)),
    '2026-04-06':('easter_monday',tuple(sorted(STATES))),
    '2026-05-01':('labour_day',tuple(sorted(STATES))),
    '2026-05-14':('ascension',tuple(sorted(STATES))),
    '2026-05-24':('whit_sunday',('BB',)),
    '2026-05-25':('whit_monday',tuple(sorted(STATES))),
    '2026-06-04':('corpus_christi',('BW','BY','HE','NW','RP','SL')),
    '2026-08-15':('assumption',('SL',)),
    '2026-09-20':('world_childrens_day',('TH',)),
    '2026-10-03':('german_unity',tuple(sorted(STATES))),
    '2026-10-31':('reformation',('BB','HB','HH','MV','NI','SN','ST','SH','TH')),
    '2026-11-01':('all_saints',('BW','BY','NW','RP','SL')),
    '2026-11-18':('repentance',('SN',)),
    '2026-12-25':('christmas_day',tuple(sorted(STATES))),
    '2026-12-26':('boxing_day',tuple(sorted(STATES))),
}
LOCAL_ONLY={('2026-06-04','SN'),('2026-06-04','TH'),('2026-08-08','BY'),('2026-08-15','BY')}
HOLIDAY_RULES=dict(version='de_2026_state_holidays_v1',holidays=HOLIDAYS,
    local_only=sorted(LOCAL_ONLY),sources=[
        'https://www.dgb.de/service/ratgeber/feiertage/',
        'https://innen.hessen.de/Buerger-Staat/Feiertage',
        'https://www.gesetze-bayern.de/Content/Document/BayFTG/true',
        'https://bravors.brandenburg.de/gesetze/ftg_2015',
        'https://www.mi.niedersachsen.de/themen/allgemeine_angelegenheiten_inneren/feiertagsrecht/feiertagsrecht-60368.html'])
HOLIDAY_RULES_SHA256=hashlib.sha256(canonical(HOLIDAY_RULES).encode()).hexdigest()


def public_holiday(current,federal_state):
    if day(current).year!=2026 or not isinstance(federal_state,str) or federal_state not in STATES:
        raise Problem(400,'Belegten Arbeitsort und unterstütztes Feiertagsjahr 2026 angeben.')
    if (current,federal_state) in LOCAL_ONLY:
        raise Problem(409,'Dieser Feiertag gilt nur örtlich; ein eigener amtlicher Gemeinde-/Ortsteilnachweis fehlt.')
    entry=HOLIDAYS.get(current)
    return entry[0] if entry and federal_state in entry[1] else None

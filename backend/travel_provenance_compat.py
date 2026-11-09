"""Reproduce exact historical v2/v3 travel metadata for trusted LF/CRLF code.

All monetary values, dates, sources, decisions and original records retain
their existing checks. Only metadata derived from the three unchanged trusted
kernel files may use a different, exactly reconstructed line-ending variant.
"""
from copy import deepcopy
from functools import lru_cache
import hashlib
from itertools import product
from pathlib import Path

from core import canonical
import payroll_travel_ground_2026 as ground
import payroll_travel_mixed_2026 as mixed
import payroll_travel_transport_2026 as transport
from payroll_travel_rates_2026 import TABLE_HASH


def _sha(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def _encodings(path):
    lf=Path(path).read_bytes().replace(b'\r\n',b'\n')
    return tuple(hashlib.sha256(raw).hexdigest() for raw in (lf,lf.replace(b'\n',b'\r\n')))


@lru_cache(maxsize=1)
def _trusted_variants():
    result=[]
    for ground_hash,mixed_hash,transport_hash in product(_encodings(ground.__file__),
            _encodings(mixed.__file__),_encodings(transport.__file__)):
        transport_rule_hash=_sha(dict(version=transport.TRANSPORT_RULE_VERSION,
            table_hash=TABLE_HASH,source=transport.TRANSPORT_SOURCE,module_sha256=transport_hash))
        rule_hash=_sha(dict(version='de_travel_2026_v3',table_hash=TABLE_HASH,
            ground_module_hash=ground_hash,mixed_module_hash=mixed_hash))
        result.append((ground_hash,mixed_hash,transport_rule_hash,rule_hash))
    return tuple(result)


def _reference(trip):
    return {key:trip[key] for key in ('id','revision','content_hash')}


def _candidate(calculated,trips,sites,variant):
    ground_hash,mixed_hash,transport_rule_hash,rule_hash=variant
    result=deepcopy(calculated)
    indexed={canonical(_reference(trip)):trip for trip in trips}
    if result['rule_version']=='de_travel_2026_v3':
        result['rule_hash']=rule_hash
    for value in result.get('ground_calendar_sources',[]):
        trip=indexed[canonical(value['trip'])]
        value['module_hash']=ground_hash
        attribution={key:item for key,item in value.items() if key not in ('trip','facts_hash')}
        value['facts_hash']=_sha(dict(trip=_reference(trip),details=trip['details'],
            sites=sites,attribution=attribution))
    for value in result.get('mixed_program_sources',[]):
        trip=indexed[canonical(value['trip'])];details=trip['details']
        value['module_hash']=mixed_hash
        assessment={key:item for key,item in value.items() if key not in ('trip','facts_hash')}
        value['facts_hash']=_sha(dict(trip=_reference(trip),assessment=details['mixed_assessment'],
            private_intervals=details['private_intervals'],segments=details['segments'],result=assessment))
    for value in result.get('transport_sources',[]):
        trip=indexed[canonical(value['trip'])]
        value['transport_rule_hash']=transport_rule_hash
        value['facts_hash']=_sha(dict(trip=_reference(trip),details=trip['details'],
            sites=sorted(sites,key=lambda item:(item['id'],item['revision'])),
            transport_rule_version=value['transport_rule_version'],transport_rule_hash=transport_rule_hash,
            days=value['days'],calendar_days=value['calendar_days'],blockers=value['blockers']))
    return result


def calculation_matches(calculated,original,*,trips,sites):
    if calculated==original:return True
    if (not isinstance(calculated,dict) or not isinstance(original,dict)
            or calculated.get('rule_version') not in ('de_travel_2026_v2','de_travel_2026_v3')
            or original.get('rule_version')!=calculated['rule_version']):
        return False
    return any(_candidate(calculated,trips,sites,variant)==original for variant in _trusted_variants())

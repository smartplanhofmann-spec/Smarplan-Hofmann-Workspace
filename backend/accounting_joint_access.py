"""Finite current source authorization, independent of chronological proof order.

Only typed identifiers and immutable access bindings are read while expanding
the graph. Every reached whole cash source is freshly authorized. Event-level
cycles are valid and terminate through a visited set; this never calls the
public R1, R2 or C2 access functions recursively.
"""
import json

from core import Problem, canonical
from accounting_return_lots import LotIdentity
from business_accounting_components import DocumentComponents, _stored


@_stored
def origin_access_ids(encoded):
    values = json.loads(encoded)
    if not isinstance(values, list) or canonical(values) != encoded:
        raise ValueError('Invalid versioned origin access binding')
    identities = []
    for value in values:
        if not isinstance(value, dict) or set(value) != {'origin_version', 'entry_id', 'group_id'}:
            raise ValueError('Invalid versioned origin access member')
        identity = LotIdentity(**value)
        identities.append((identity.origin_version, identity.entry_id, identity.group_id))
    if identities != sorted(set(identities)):
        raise ValueError('Invalid versioned origin access order')
    return identities


@_stored
def authorize_sources(office, actor, event_id=None, *, write=False, origins=(), segments=()):
    from business_accounting_capacity import ReusableDocumentComponents
    components = DocumentComponents(office)
    fresh = components.access(actor, 'accounting.read'); components.access(fresh, 'finance.read')
    if write:
        components.access(fresh, 'accounting.prepare'); components.access(fresh, 'finance.write')
    pending = []
    if event_id:
        components._access(fresh, event_id, write)
    for origin in origins:
        identity = LotIdentity(origin['origin_version'], origin['entry_id'], origin['group_id'])
        pending.append((('origin', identity.origin_version, identity.entry_id, identity.group_id), False))
    pending.extend((('segment', segment_id), True) for segment_id in segments)
    # Stored bindings take precedence over caller selections. In particular,
    # replaying a now missing stored lot is an integrity conflict, even when
    # that same lot also appears in the caller's original request.
    if event_id:
        pending.append((('event', event_id), False))
    seen = set()
    while pending:
        node, stored = pending.pop()
        if node in seen:
            continue
        seen.add(node)
        if node[0] == 'event':
            components._access(fresh, node[1], write)
            for row in office.db.execute('SELECT l.origin_entry_id,l.group_id FROM business_accounting_refund_lines l '
                    'JOIN business_accounting_refund_entries e ON e.id=l.entry_id WHERE e.event_id=?', (node[1],)).fetchall():
                pending.append((('origin', 'c1', row['origin_entry_id'], row['group_id']), True))
            for row in office.db.execute('SELECT access_origins_json FROM business_accounting_refunds_v2_entries WHERE event_id=?', (node[1],)).fetchall():
                pending.extend((('origin',)+identity, True) for identity in origin_access_ids(row['access_origins_json']))
            for row in office.db.execute('SELECT access_segments_json FROM business_accounting_capacity_entries WHERE event_id=?', (node[1],)).fetchall():
                pending.extend((('segment', segment_id), True) for segment_id in ReusableDocumentComponents._access_ids(row['access_segments_json']))
        elif node[0] == 'origin':
            prefix = 'business_accounting_component' if node[1] == 'c1' else 'business_accounting_capacity'
            row = office.db.execute('SELECT e.event_id FROM '+prefix+'_entries e JOIN '+prefix+'_lines l ON l.entry_id=e.id '
                                   'WHERE e.id=? AND l.group_id=?', (node[2], node[3])).fetchone()
            if not row:
                raise Problem(409 if stored else 404, 'Versionierte Ursprungslinie nicht verfügbar')
            pending.append((('event', row['event_id']), True))
        else:
            row = office.db.execute('SELECT previous_id FROM business_accounting_capacity_segments WHERE id=?', (node[1],)).fetchone()
            if not row:
                raise Problem(409, 'Gespeicherter Kapazitätsabschnitt fehlt')
            if row['previous_id']:
                pending.append((('segment', row['previous_id']), True))
            for releases, entries in (('business_accounting_capacity_releases', 'business_accounting_refund_entries'),
                                      ('business_accounting_refunds_v2_releases', 'business_accounting_refunds_v2_entries')):
                rows = office.db.execute('SELECT DISTINCT e.event_id FROM '+releases+' r JOIN '+entries+' e ON e.id=r.refund_entry_id '
                                         'WHERE r.segment_id=?', (node[1],)).fetchall()
                pending.extend((('event', row['event_id']), True) for row in rows)
    return fresh

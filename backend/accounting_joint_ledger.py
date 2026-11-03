"""One chronological, nonrecursive reconstruction of C2 and R2 journals.

Original C1/R1 proof readers remain independent sources. Old C2-v1 entries use
their original unversioned source space and a virtual opposite head of zero.
Only a validated entry is applied to the shared prefix. No horizon, public
access method or mutually recursive full ledger reader is called here.
"""
import json

from core import canonical
from accounting_joint_order import HeadObservation, merge_observed_heads
from business_accounting_components import _cents, _stored
from business_operations import instant


def combined_sources(sources, refunds):
    from business_accounting_refunds_v2 import legacy_reference, reference_order
    returned = {document_id: [legacy_reference(value) for value in values] for document_id, values in sources['returns'].items()}
    for document_id, values in refunds['returns'].items():
        returned.setdefault(document_id, []).extend(values)
    for values in returned.values():
        values.sort(key=reference_order)
    return dict(sources, returns=returned, refunds_v2_entries=refunds['rows'], r2_sequence=len(refunds['rows']))


def _capacity_step(api, row, value, proof, joint):
    ledger = joint['capacity']; sources = joint['sources']
    if proof['schema_version'] == 2:
        sources = combined_sources(sources, joint['refunds_v2'])
    if (row['sequence'] != len(ledger['rows'])+1 or row['revision'] != len(ledger['by_event'].get(row['event_id'], []))+1
            or row['portion_id'] in ledger['portions'] or row['portion_id'] in sources['legacy_portions']):
        raise ValueError('Invalid positive order or duplicated whole portion')
    context, raw = api._historical_source(row, proof)
    portion, expected = api._plan(None, context, raw, ledger, sources, historical=proof)
    if (proof != expected or portion != value['portion'] or not portion['eligible'] or portion['action'] != value['action']
            or value['amount'] != raw['amount'] or value['action'] not in ('takeover_and_document', 'document_current')
            or row['previous_state_hash'] != api._state_hash(context, ledger, sources, proof['c1_sequence'], proof['portions_before'])
            or api._entry_lines(context, portion, proof, value['lines'], ledger) != value['lines']
            or api._changes(proof) != value['capacity_changes']):
        raise ValueError('Changed historical positive source, prefix or cumulative cents')
    api._apply(row, value, proof, ledger, validate_rows=True)


@_stored
def read_joint_ledger(office, cache=None):
    from business_accounting_capacity import ReusableDocumentComponents
    from business_accounting_refunds import RefundOrigins
    from business_accounting_refunds_v2 import VersionedRefundOrigins, installed, legacy_reference, reference_order
    cache = {} if cache is None else cache
    if 'accounting_joint_ledger' in cache:
        return cache['accounting_joint_ledger']
    if not installed(office):
        raise ValueError('The complete R2 module is required for a joint ledger')
    capacity = ReusableDocumentComponents(office); refunds = VersionedRefundOrigins(office)
    original_refunds = RefundOrigins(office)._ledger(cache)
    sources = capacity._sources(cache)
    positive_rows = office.db.execute('SELECT * FROM business_accounting_capacity_entries ORDER BY sequence,id').fetchall()
    refund_rows = office.db.execute('SELECT * FROM business_accounting_refunds_v2_entries ORDER BY sequence,id').fetchall()
    positives = []; returns = []; positive_heads = []; refund_heads = []; new_proofs_seen = False
    for row in positive_rows:
        value, proof = capacity._basic(row)
        version = proof.get('schema_version')
        if type(version) is not int or version not in (1, 2) or version == 1 and new_proofs_seen:
            raise ValueError('Legacy positive proofs must form one unchanged prefix')
        if version == 2 and instant(row['created_at']) != row['created_at']:
            raise ValueError('New positive timestamp must be canonical UTC')
        new_proofs_seen = new_proofs_seen or version == 2
        positives.append((row, value, proof))
        positive_heads.append(HeadObservation(row['sequence'], 0 if version == 1 else proof['r2_sequence']))
    for row in refund_rows:
        value, proof, stored = refunds._basic(row)
        if type(proof.get('schema_version')) is not int or proof['schema_version'] != 1:
            raise ValueError('Invalid versioned refund proof schema')
        returns.append((row, value, proof, stored))
        refund_heads.append(HeadObservation(row['sequence'], proof['c2_sequence']))
    order = merge_observed_heads(positive_heads, refund_heads)
    joint = dict(sources=sources, refunds=original_refunds, capacity=capacity._empty_ledger(), refunds_v2=refunds._empty_ledger())
    observed_c1 = observed_r1 = 0
    for side, observation in order:
        operation = positives[observation.sequence-1] if side == 'left' else returns[observation.sequence-1]
        proof = operation[2]
        c1_head, r1_head = proof['c1_sequence'], proof['r1_sequence']
        if (type(c1_head) is not int or not observed_c1 <= c1_head <= sources['c1_sequence']
                or type(r1_head) is not int or not observed_r1 <= r1_head <= sources['r1_sequence']):
            raise ValueError('Observed original journal prefixes must be complete and monotone')
        if side == 'left':
            _capacity_step(capacity, *operation, joint)
        else:
            refunds._process(*operation, joint, cache)
        observed_c1, observed_r1 = c1_head, r1_head
    for document_id, handoff in joint['refunds_v2']['handoffs'].items():
        current = sorted((legacy_reference(value) for value in sources['returns'].get(document_id, [])), key=reference_order)
        if current != handoff['legacy_claims']:
            raise ValueError('A versioned refund invoice has new or changed R1 claims')
    c2 = joint['capacity']; r2 = joint['refunds_v2']
    counts = {
        'business_accounting_capacity_handoffs': len(c2['handoffs']),
        'business_accounting_capacity_segments': len(c2['segments']),
        'business_accounting_capacity_releases': sum(key[0] == 'r1' for key in c2['claims']),
        'business_accounting_capacity_entries': len(c2['rows']),
        'business_accounting_capacity_lines': sum(len(value['lines']) for value in c2['entries_by_id'].values()),
        'business_accounting_capacity_requests': len(c2['rows']),
        'business_accounting_refunds_v2_handoffs': len(r2['handoffs']),
        'business_accounting_refunds_v2_entries': len(r2['rows']),
        'business_accounting_refunds_v2_lines': sum(len(value['lines']) for value in r2['entries'].values()),
        'business_accounting_refunds_v2_requests': len(r2['rows']),
        'business_accounting_refunds_v2_releases': sum(key[0] == 'r2' for key in c2['claims']),
    }
    for table, expected in counts.items():
        if office.db.execute('SELECT COUNT(*) FROM '+table).fetchone()[0] != expected:
            raise ValueError('Missing or orphan joint journal row')
    cache['capacity_joint_sources'] = combined_sources(sources, r2)
    cache['accounting_joint_ledger'] = joint
    return joint

"""Frozen incremental invoice groups, without changing ordinary invoice proofs.

The document writer already archives full contract totals and incremental
liabilities separately. This reader proves their exact relationship through an
acyclic, non-overlapping archive graph. No money or journal entry is created.
"""
import json

from core import canonical
from business_operations import identifier
from business_accounting_components import _cents, _money, _sha, _stored

KINDS = ('advance_invoice', 'cumulative_invoice', 'final_invoice')
FAMILY = 'incremental_invoice_v1'
MAX_DOCUMENTS = 500


def is_incremental(row):
    return row is not None and row['kind'] in KINDS


def _groups(totals):
    groups = {}
    for group in totals['tax_breakdown']:
        if set(group) != {'rate', 'category', 'reason', 'net', 'tax'}:
            raise ValueError('Invalid archived tax group')
        key = (group['rate'], group['category'], group['reason'])
        if key in groups:
            raise ValueError('Duplicate archived tax group')
        groups[key] = (_cents(group['net']), _cents(group['tax']))
    if (sum(value[0] for value in groups.values()) != _cents(totals['net'])
            or sum(value[1] for value in groups.values()) != _cents(totals['tax'])
            or _cents(totals['net'])+_cents(totals['tax']) != _cents(totals['gross'])
            or totals['payable'] != totals['gross']):
        raise ValueError('Invalid archived incremental totals')
    return groups


def _subtract(full, previous):
    """The exact archived writer equation, in integer cents, including kinds."""
    deductions = {}; prior_kinds = {}; previous_gross = 0
    for totals in previous:
        previous_gross += _cents(totals['gross'])
        for key, (net, tax) in _groups(totals).items():
            before = deductions.setdefault(key, [0, 0]); before[0] += net; before[1] += tax
        for kind, values in totals['by_kind'].items():
            bucket = prior_kinds.setdefault(kind, dict(net=0, tax=0, gross=0))
            for part in bucket:
                bucket[part] += _cents(values[part])
    remaining = []
    for group in full['tax_breakdown']:
        before = deductions.pop((group['rate'], group['category'], group['reason']), (0, 0))
        net, tax = _cents(group['net'])-before[0], _cents(group['tax'])-before[1]
        if net < 0 or tax < 0:
            raise ValueError('Predecessor exceeds incremental tax group')
        remaining.append(dict(group, net=_money(net), tax=_money(tax)))
    if deductions:
        raise ValueError('Predecessor has an absent tax group')
    net = sum(_cents(value['net']) for value in remaining); tax = sum(_cents(value['tax']) for value in remaining)
    result = dict(full, net=_money(net), tax=_money(tax), gross=_money(net+tax), payable=_money(net+tax), tax_breakdown=remaining)
    by_kind = {}
    for kind, values in full['by_kind'].items():
        before = prior_kinds.pop(kind, dict(net=0, tax=0, gross=0))
        current = {part:_cents(amount)-before[part] for part, amount in values.items()}
        if any(value < 0 for value in current.values()):
            raise ValueError('Predecessor exceeds incremental position kind')
        by_kind[kind] = {part:_money(amount) for part, amount in current.items()}
    if any(any(values.values()) for values in prior_kinds.values()):
        raise ValueError('Absent predecessor position kind')
    result['by_kind'] = by_kind
    for kind in ('labor', 'material'):
        for part in ('net', 'tax', 'gross'):
            result[kind+'_'+part] = by_kind[kind][part]
    return result, _money(previous_gross)


@_stored
def archive_chain(office, root):
    """Read only immutable ancestors; later outgoing chains/cancellations are not
    folded into an old source hash. Current eligibility is checked separately.
    """
    from business_accounting_allocations import _archive
    from business_documents import calculate_positions
    if not is_incremental(root) or root['status'] != 'final' or not root['customer_id']:
        raise ValueError('A final assigned incremental invoice is required')
    nodes = {}; visiting = set(); complete = set(); descendants = {}; stack = [(root['id'], False)]
    company = None
    while stack:
        document_id, finishing = stack.pop()
        if finishing:
            node = nodes[document_id]; row = node['archive']['document']; payload = json.loads(row['payload_json'])
            previous_ids = node['previous_ids']; seen = set(); previous = []
            for previous_id in previous_ids:
                if previous_id not in complete:
                    raise ValueError('Invalid cyclic predecessor order')
                branch = descendants[previous_id] | {previous_id}
                if seen & branch:
                    raise ValueError('A predecessor is deducted twice through overlapping branches')
                seen |= branch
                prior = nodes[previous_id]; prior_row = prior['archive']['document']; prior_payload = json.loads(prior_row['payload_json'])
                if prior_row['kind'] not in ('advance_invoice', 'cumulative_invoice'):
                    raise ValueError('A final invoice cannot be deducted as predecessor')
                previous.append(dict(id=previous_id, number=prior_row['number'], sha256=prior_row['payload_sha256'],
                                     gross=prior['full_totals']['gross'], issue_date=prior_payload['issue_date']))
            if previous_ids:
                expected, gross = _subtract(node['full_totals'], [nodes[value]['full_totals'] for value in previous_ids])
                if (row['kind'] not in ('cumulative_invoice', 'final_invoice') or payload.get('previous_documents') != previous
                        or payload.get('previous_issued_gross') != gross or payload.get('totals') != expected):
                    raise ValueError('Archived incremental liability differs from its exact predecessor equation')
            elif (payload.get('previous_documents') or 'contract_totals' in payload or 'previous_issued_gross' in payload
                    or payload['totals'] != node['full_totals']):
                raise ValueError('Standalone invoice has unexplained contract deductions')
            expected_relations = [dict(target_id=document_id, source_id=value['id'], kind='deducts', source_sha256=value['sha256']) for value in previous]
            if sorted(node['relations'], key=canonical) != sorted(expected_relations, key=canonical):
                raise ValueError('Archived predecessor relationship changed')
            descendants[document_id] = seen; complete.add(document_id); visiting.remove(document_id)
            continue
        if document_id in complete:
            continue
        if document_id in visiting:
            raise ValueError('Cyclic archived invoice chain')
        identifier(document_id)
        row = office.db.execute('SELECT * FROM business_documents WHERE id=?', (document_id,)).fetchone()
        if (not is_incremental(row) or row['status'] != 'final' or row['project_id'] != root['project_id']
                or row['customer_id'] != root['customer_id']):
            raise ValueError('Predecessor belongs to a different project/customer or is not final')
        archive = _archive(office, row); payload = json.loads(row['payload_json'])
        number = office.db.execute('SELECT * FROM business_document_numbers WHERE document_id=?', (document_id,)).fetchone()
        if not number or number['number'] != row['number']:
            raise ValueError('Missing immutable issued number')
        company = number['company_id'] if company is None else company
        if number['company_id'] != company or payload.get('currency') != 'EUR':
            raise ValueError('Mixed company or currency in invoice chain')
        calculated = calculate_positions(payload['positions'])
        full = payload.get('contract_totals', payload['totals'])
        if calculated['positions'] != payload['positions'] or calculated['totals'] != full:
            raise ValueError('Archived full contract does not match its position calculation')
        _groups(full); _groups(payload['totals'])
        previous_ids = payload.get('previous_document_ids', [])
        if (not isinstance(previous_ids, list) or len(previous_ids) != len(set(previous_ids))
                or len(previous_ids) > MAX_DOCUMENTS):
            raise ValueError('Unique bounded predecessor IDs required')
        for value in previous_ids:
            identifier(value)
        if len(nodes) >= MAX_DOCUMENTS:
            raise ValueError('Invoice chain exceeds the explicitly bounded review graph')
        relations = [dict(value) for value in office.db.execute("SELECT * FROM business_document_relations WHERE target_id=? AND kind='deducts' ORDER BY source_id", (document_id,)).fetchall()]
        nodes[document_id] = dict(archive=archive, number=dict(number), previous_ids=previous_ids,
                                  full_totals=full, incremental_totals=payload['totals'], relations=relations)
        visiting.add(document_id); stack.append((document_id, True))
        stack.extend((value, False) for value in reversed(previous_ids))
    return dict(family=FAMILY, root_id=root['id'], company_id=company,
                nodes=[dict(document_id=key, **nodes[key]) for key in sorted(nodes)])


def successful_eligibility(chain):
    return dict(invoice_family=FAMILY, chain_sha256=_sha(canonical(chain)), cancellations=[])


@_stored
def eligibility(office, row, chain=None):
    chain = archive_chain(office, row) if chain is None else chain
    evidence = successful_eligibility(chain)
    cancellations = []
    for node in chain['nodes']:
        for value in office.db.execute("SELECT r.* FROM business_document_relations r JOIN business_documents d ON d.id=r.target_id "
                "WHERE r.source_id=? AND r.kind='cancels' AND d.status='final' ORDER BY r.target_id", (node['document_id'],)).fetchall():
            cancellations.append(dict(value))
    if cancellations:
        return 'cancelled_invoice_chain', dict(evidence, cancellations=sorted(cancellations, key=canonical))
    return None, evidence


@_stored
def groups_from_chain(chain):
    root = next(value for value in chain['nodes'] if value['document_id'] == chain['root_id'])
    archive = root['archive']; row = archive['document']
    binding = dict(document_id=row['id'], payload_sha256=row['payload_sha256'], pdf_sha256=archive['pdf_sha256'],
                   xml_sha256=archive['xml_sha256'], chain_sha256=_sha(canonical(chain)))
    result = []
    for group in root['incremental_totals']['tax_breakdown']:
        value = dict(group, gross=_money(_cents(group['net'])+_cents(group['tax'])))
        value['group_id'] = _sha(canonical(dict(kind=FAMILY, binding=binding, group=value)))
        result.append(value)
    return sorted(result, key=lambda value:value['group_id'])

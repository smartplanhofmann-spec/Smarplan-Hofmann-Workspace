"""Closed, source-bound assistant tools. No model-selected URLs, SQL or actors."""
from datetime import date
from decimal import Decimal
import hashlib
import json
import re

from core import Problem, canonical
from business_foundation import require_permission
from business_operations import identifier, text, iso_date

KINDS = ('project', 'task', 'open_item', 'costs', 'communication', 'document', 'dunning', 'purchase', 'article')
ACTIONS = ('task.create', 'offer.draft', 'document.email', 'dunning.email', 'supplier.order', 'payment.execute')
EXTERNAL = ('document.email', 'dunning.email', 'supplier.order', 'payment.execute')
ACTION_PERMISSIONS = {
    'task.create': ('projects.manage',), 'offer.draft': ('finance.read', 'finance.write'),
    'document.email': ('finance.read', 'finance.approve'), 'dunning.email': ('finance.read', 'finance.approve'),
    'supplier.order': ('inventory.read', 'inventory.write', 'finance.approve'),
    'payment.execute': ('finance.read', 'finance.approve'),
}


def sha(value):
    return hashlib.sha256(canonical(value).encode('utf-8')).hexdigest()


def _minor(value):
    amount = Decimal(str(value))*100
    if not amount.is_finite() or amount != amount.to_integral_value():
        raise Problem(500, 'Fachquelle enthält keinen eindeutigen Centbetrag.')
    return int(amount)


def action_access(office, actor, project, action):
    if action not in ACTIONS:
        raise Problem(400, 'Diese Assistentenaktion ist nicht vorgesehen.')
    for permission in ACTION_PERMISSIONS[action]:
        actor = require_permission(office, actor, permission, project)
    return actor


def resolve(office, actor, project, descriptor, today):
    if not isinstance(descriptor, dict) or set(descriptor) != {'kind', 'id'} or descriptor['kind'] not in KINDS:
        raise Problem(400, 'Eine ausdrücklich unterstützte Fachquelle auswählen.')
    kind, object_id = descriptor['kind'], identifier(descriptor['id'])
    project_value = office.project(actor, project)
    from project_workspace import ProjectWorkspace
    from business_documents import Documents
    from business_finance import Finance
    if kind == 'project':
        if object_id != project:
            raise Problem(404, 'Projektquelle nicht verfügbar.')
        require_permission(office, actor, 'documents.read', project)
        profile = ProjectWorkspace(office).profile(actor, project)
        value = dict(id=project, name=project_value['name'], customer_id=project_value['customer_id'],
            **{key: profile[key] for key in ('revision', 'description', 'phase', 'start_date', 'end_date')})
    elif kind == 'task':
        require_permission(office, actor, 'documents.read', project)
        raw = ProjectWorkspace(office).get_item(actor, project, 'tasks', object_id)
        value = {key: raw[key] for key in ('id', 'project_id', 'revision', 'title', 'details', 'status', 'priority', 'due_date', 'assignee_id')}
        value['overdue_days'] = max(0, (date.fromisoformat(today)-date.fromisoformat(raw['due_date'])).days) if raw['due_date'] and raw['status'] not in ('done', 'cancelled') else 0
    elif kind == 'open_item':
        items = Finance(office).open_items(actor, project)['items']
        raw = next((item for item in items if item['id'] == object_id), None)
        if raw is None:
            raise Problem(404, 'Offener Posten nicht verfügbar.')
        value = {key: raw.get(key) for key in ('id', 'project_id', 'number', 'due_date', 'open', 'paid', 'credited', 'level', 'next_due_date')}
        value['open_minor'] = _minor(raw['open'])
        value['overdue_days'] = max(0, (date.fromisoformat(today)-date.fromisoformat(raw['due_date'])).days) if value['open_minor'] > 0 else 0
    elif kind == 'costs':
        if object_id != project:
            raise Problem(404, 'Kostenquelle nicht verfügbar.')
        from business_project_economics import ProjectEconomics
        raw = ProjectEconomics(office).summary(actor, project)
        value = {key: raw[key] for key in ('project_id', 'currency', 'valuation_basis', 'tax_result_available', 'budget', 'costs', 'revenue', 'payments', 'result')}
        # No employee names, individual rates, approved-time or personnel rows.
        value['issues'] = [dict(code=item['code'], message=item['message']) for item in raw['issues']]
        value['total_cost_minor'] = sum(_minor(item) for item in raw['costs'].values())
    elif kind == 'communication':
        from inquiries import Inquiries
        raw = Inquiries(office).get(actor, object_id)
        if raw.get('project_id') != project:
            raise Problem(404, 'Kommunikation gehört nicht zum geöffneten Projekt.')
        value = {key: raw[key] for key in ('id', 'revision', 'project_id', 'subject', 'message', 'received_at', 'status')}
        value['trust'] = 'untrusted_external_content'
    elif kind == 'document':
        raw = Documents(office).get(actor, object_id)
        if raw['project_id'] != project:
            raise Problem(404, 'Beleg gehört nicht zum geöffneten Projekt.')
        value = {key: raw.get(key) for key in ('id', 'project_id', 'kind', 'status', 'revision', 'title', 'number', 'issue_date', 'due_date', 'totals')}
        value['email_preview'] = None
        if raw['status'] == 'final':
            try:
                value['email_preview'] = Documents(office).email_preview(actor, object_id)
            except Problem as error:
                if error.status not in (400, 409):
                    raise
    elif kind == 'article':
        raw = Documents(office).catalog_item(actor, 'business_articles', object_id)
        value = {key: raw[key] for key in ('id', 'revision', 'name', 'kind', 'unit', 'unit_price_net', 'tax_rate', 'currency', 'active')}
    elif kind == 'dunning':
        api = Finance(office)
        mail = api._mail(object_id)
        document = Documents(office).get(actor, mail['document_id'])
        if document['project_id'] != project:
            raise Problem(404, 'Mahnung gehört nicht zum geöffneten Projekt.')
        value = {key: mail[key] for key in ('id', 'document_id', 'payload_sha256', 'operation_id', 'recipient', 'level')}
        value['snapshot'] = json.loads(mail['payload_json'])
    else:
        from business_purchasing import Purchasing
        value = Purchasing(office).get(actor, object_id)
        if value['project_id'] != project:
            raise Problem(404, 'Bestellung gehört nicht zum geöffneten Projekt.')
    if len(canonical(value).encode()) > 40000:
        raise Problem(413, 'Diese Quelle ist für den begrenzten Assistentenkontext zu groß.')
    return dict(source_id=kind+':'+object_id, descriptor=dict(descriptor), data=value, sha256=sha(value))


def facts(sources):
    result = dict(overdue_payment=False, payment_overdue_days=0, open_minor=0,
        overdue_task=False, task_overdue_days=0, total_cost_minor=None, costs_complete=False)
    for source in sources:
        kind, data = source['descriptor']['kind'], source['data']
        if kind == 'open_item':
            result['open_minor'] += data['open_minor']
            result['payment_overdue_days'] = max(result['payment_overdue_days'], data['overdue_days'])
            result['overdue_payment'] |= data['overdue_days'] > 0
        elif kind == 'task':
            result['task_overdue_days'] = max(result['task_overdue_days'], data['overdue_days'])
            result['overdue_task'] |= data['overdue_days'] > 0
        elif kind == 'costs':
            result['total_cost_minor'] = data['total_cost_minor']
            result['costs_complete'] = data['result']['complete_for_recorded_sources']
    return result


def catalog(office, actor, project, query='', offset=0):
    if not isinstance(query,str) or len(query)>200 or type(offset) is not int or not 0<=offset<=100000:
        raise Problem(400, 'Quellensuche mit höchstens 200 Zeichen und gültiger Position angeben.')
    query = query.strip().casefold()
    office.project(actor, project)
    options = [dict(kind='project', id=project, title='Projektstand')]
    from project_workspace import ProjectWorkspace
    from business_documents import Documents
    from business_finance import Finance
    candidates = []
    operations = [lambda: [dict(kind='task', id=item['id'], title=item['title']) for item in ProjectWorkspace(office).list_items(actor, project, 'tasks')],
        lambda: [dict(kind='open_item', id=item['id'], title=item['number']) for item in Finance(office).open_items(actor, project)['items']],
        lambda: [dict(kind='document', id=item['id'], title=item.get('title') or item.get('number') or item['kind']) for item in Documents(office).list(actor, project)['items']],
        lambda: [dict(kind='article', id=item['id'], title=item['name']) for item in Documents(office).articles(actor)['items'] if item['active']]]
    for operation in operations:
        try:
            candidates.extend(operation())
        except Problem as error:
            if error.status not in (403, 404):
                raise
    for kind, table, label in (('communication', 'inquiries', 'subject'), ('purchase', 'business_purchase_orders', 'supplier_name')):
        for row in office.db.execute('SELECT id,'+label+' FROM '+table+' WHERE project_id=? ORDER BY created_at DESC,id', (project,)).fetchall():
            candidates.append(dict(kind=kind, id=row['id'], title=row[label]))
    for row in office.db.execute('SELECT o.id,a.level FROM business_finance_outbox o JOIN business_dunning_approvals a ON a.id=o.approval_id JOIN business_documents d ON d.id=a.document_id WHERE d.project_id=? ORDER BY o.created_at DESC,o.id', (project,)).fetchall():
        candidates.append(dict(kind='dunning', id=row['id'], title='Freigegebene Mahnung · Stufe '+str(row['level'])))
    candidates.append(dict(kind='costs', id=project, title='Erfasste Projektwirtschaftlichkeit'))
    # Resolve individually so even titles of forbidden source classes stay private.
    from datetime import datetime, timezone
    day = datetime.now(timezone.utc).date().isoformat()
    readable = []
    for candidate in options+candidates:
        if query and query not in ' '.join(str(candidate[key]) for key in ('title','kind','id')).casefold():
            continue
        try:
            resolve(office, actor, project, {key: candidate[key] for key in ('kind', 'id')}, day)
            readable.append(candidate)
        except Problem as error:
            if error.status not in (400, 403, 404, 409, 413):
                raise
    more = len(readable)>offset+100
    return dict(items=readable[offset:offset+100], total=len(readable), truncated=more,
                offset=offset, next_offset=offset+100 if more else None)


def parameters(action, value, context):
    if not isinstance(value, dict) or action not in ACTIONS:
        raise Problem(400, 'Unterstützte Aktion mit eindeutigen Parametern erwartet.')
    sources = context['sources']
    def source(kind, object_id):
        found = next((item['data'] for item in sources if item['descriptor'] == dict(kind=kind, id=object_id)), None)
        if found is None:
            raise Problem(409, 'Aktion benötigt die ausdrücklich ausgewählte passende Fachquelle.')
        return found
    if action == 'task.create':
        if set(value) != {'title', 'details', 'due_date', 'priority'} or value['priority'] not in ('normal', 'high'):
            raise Problem(400, 'Titel, Beschreibung, Datum und Priorität der Aufgabe angeben.')
        result = dict(title=text(value['title'], 'Aufgabe', 200, required=True), details=text(value['details'], 'Beschreibung', 10000),
            due_date=iso_date(value['due_date'], optional=True), priority=value['priority'])
    elif action == 'offer.draft':
        if set(value) != {'title', 'issue_date', 'due_date', 'positions'} or not isinstance(value['positions'], list) or not 1 <= len(value['positions']) <= 30:
            raise Problem(400, 'Begrenzten Angebotsentwurf mit Datum und Positionen angeben.')
        result = dict(title=text(value['title'], 'Angebotstitel', 300, required=True), issue_date=iso_date(value['issue_date']),
            due_date=iso_date(value['due_date']), positions=[])
        if result['due_date'] < result['issue_date']:
            raise Problem(400, 'Fälligkeit liegt vor dem Belegdatum.')
        for item in value['positions']:
            if not isinstance(item, dict) or set(item) != {'article_id', 'article_revision', 'quantity'}:
                raise Problem(400, 'Angebotspreise ausschließlich aus ausgewählter Artikel-/Leistungsquelle übernehmen.')
            selected = source('article', identifier(item['article_id']))
            if type(item['article_revision']) is not int or item['article_revision'] != selected['revision'] or not selected['active']:
                raise Problem(409, 'Aktuelle aktive Artikel-/Leistungsfassung auswählen.')
            if not isinstance(item['quantity'], str) or not re.fullmatch(r'\d{1,6}(?:\.\d{1,4})?', item['quantity']) or Decimal(item['quantity']) <= 0:
                raise Problem(400, 'Positive begrenzte Mengenangabe erforderlich.')
            result['positions'].append(dict(item))
        source('project', context['project_id'])
    else:
        field, kind = {'document.email': ('document_id', 'document'), 'dunning.email': ('outbox_id', 'dunning'),
            'supplier.order': ('order_id', 'purchase'), 'payment.execute': ('document_id', 'open_item')}[action]
        if set(value) != {field}:
            raise Problem(400, 'Nur die ausgewählte Fachquelle als Aktionsziel angeben.')
        identifier(value[field])
        selected = source(kind, value[field])
        if action == 'document.email' and not selected['email_preview']:
            raise Problem(409, 'Aktuelle Versandvorschau eines finalen Belegs erforderlich.')
        result = dict(value)
    return result


def execute_internal(office, actor, plan, context, request_id):
    value, project = plan['parameters'], context['project_id']
    if plan['action'] == 'task.create':
        from project_workspace import ProjectWorkspace
        return ProjectWorkspace(office).save_item(actor, project, 'tasks',
            dict(value, status='todo', assignee_id=actor['id'], request_id=request_id))
    if plan['action'] == 'offer.draft':
        from business_documents import Documents
        return Documents(office).create(actor, dict(value, project_id=project, kind='offer', request_id=request_id))
    raise Problem(409, 'Diese Aktion hat keinen internen Ausführungspfad.')


def execute_external(office, actor, plan, context, request_id, *, transport=None):
    selected = {item['source_id']: item['data'] for item in context['sources']}
    if plan['action'] == 'document.email':
        from business_documents import Documents
        document_id = plan['parameters']['document_id']
        source = selected['document:'+document_id]
        return Documents(office).send_mail(actor, document_id, dict(request_id=request_id,
            confirmation=True, revision=source['revision'], preview_sha256=source['email_preview']['preview_sha256']), transport=transport)
    if plan['action'] == 'dunning.email':
        from business_finance import Finance
        outbox = plan['parameters']['outbox_id']
        return Finance(office).deliver(actor, outbox, dict(request_id=request_id,
            confirmation=True, payload_sha256=selected['dunning:'+outbox]['payload_sha256']), transport=transport)
    raise Problem(409, 'Für diese Außenwirkung ist kein ausführender Anbieteradapter eingerichtet.')

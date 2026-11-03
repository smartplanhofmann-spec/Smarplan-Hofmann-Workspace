"""Source-bound assistant, versioned rules and independently enforced actions.

The model is a proposal generator, never an authorization principal. Every
business action passes a closed tool catalog, fresh source rights, the current
rule versions and the original business API. Unknown policy denies execution.
"""
from datetime import datetime, timezone
import json
import re
import sqlite3
import uuid

from core import Problem, canonical
from business_foundation import require_permission
from business_operations import identifier, text, transaction
from business_assistant_sources import ACTIONS, EXTERNAL, KINDS, action_access, catalog, facts, parameters, resolve, sha
from business_assistant_provider import configuration, OpenAICompatibleModel

FEATURES = ('assistant_workflow',)
ID = r'[a-f0-9]{32}'
TRIGGERS = ('manual', 'payment.overdue', 'task.overdue', 'cost.threshold')
MODES = ('auto', 'approval', 'deny')
FACT_TYPES = {'overdue_payment': bool, 'payment_overdue_days': int, 'open_minor': int,
    'overdue_task': bool, 'task_overdue_days': int, 'total_cost_minor': int, 'costs_complete': bool}
TABLES = tuple('business_assistant_'+name for name in ('rules', 'contexts', 'plans', 'decisions',
    'executions', 'outcomes', 'chats', 'chat_results', 'requests', 'suspensions'))


def schema_statements(binary_type='BYTEA'):
    return [
        '''CREATE TABLE IF NOT EXISTS business_assistant_rules(
        id TEXT NOT NULL,revision INTEGER NOT NULL CHECK(revision>0),project_id TEXT NOT NULL REFERENCES projects(id),
        payload_json TEXT NOT NULL,sha256 TEXT NOT NULL,created_by TEXT NOT NULL REFERENCES users(id),created_at TEXT NOT NULL,
        PRIMARY KEY(id,revision))''',
        '''CREATE TABLE IF NOT EXISTS business_assistant_contexts(
        id TEXT PRIMARY KEY,project_id TEXT NOT NULL REFERENCES projects(id),created_by TEXT NOT NULL REFERENCES users(id),
        payload_json TEXT NOT NULL,sha256 TEXT NOT NULL,created_at TEXT NOT NULL)''',
        '''CREATE TABLE IF NOT EXISTS business_assistant_plans(
        id TEXT PRIMARY KEY,context_id TEXT NOT NULL REFERENCES business_assistant_contexts(id),
        project_id TEXT NOT NULL REFERENCES projects(id),created_by TEXT NOT NULL REFERENCES users(id),
        payload_json TEXT NOT NULL,sha256 TEXT NOT NULL,created_at TEXT NOT NULL)''',
        '''CREATE TABLE IF NOT EXISTS business_assistant_decisions(
        plan_id TEXT PRIMARY KEY REFERENCES business_assistant_plans(id),decision TEXT NOT NULL CHECK(decision IN ('approved','rejected')),
        plan_sha256 TEXT NOT NULL,reason TEXT NOT NULL,created_by TEXT NOT NULL REFERENCES users(id),created_at TEXT NOT NULL)''',
        '''CREATE TABLE IF NOT EXISTS business_assistant_executions(
        plan_id TEXT PRIMARY KEY REFERENCES business_assistant_plans(id),domain_request_id TEXT NOT NULL UNIQUE,
        created_by TEXT NOT NULL REFERENCES users(id),created_at TEXT NOT NULL)''',
        '''CREATE TABLE IF NOT EXISTS business_assistant_outcomes(
        plan_id TEXT PRIMARY KEY REFERENCES business_assistant_executions(plan_id),
        status TEXT NOT NULL CHECK(status IN ('succeeded','failed','unknown','blocked')),
        payload_json TEXT NOT NULL,sha256 TEXT NOT NULL,created_at TEXT NOT NULL)''',
        '''CREATE TABLE IF NOT EXISTS business_assistant_chats(
        id TEXT PRIMARY KEY,context_id TEXT NOT NULL REFERENCES business_assistant_contexts(id),
        project_id TEXT NOT NULL REFERENCES projects(id),created_by TEXT NOT NULL REFERENCES users(id),
        payload_json TEXT NOT NULL,sha256 TEXT NOT NULL,created_at TEXT NOT NULL)''',
        '''CREATE TABLE IF NOT EXISTS business_assistant_chat_results(
        chat_id TEXT PRIMARY KEY REFERENCES business_assistant_chats(id),
        status TEXT NOT NULL CHECK(status IN ('completed','failed','stale','interrupted')),
        payload_json TEXT NOT NULL,sha256 TEXT NOT NULL,created_at TEXT NOT NULL)''',
        '''CREATE TABLE IF NOT EXISTS business_assistant_requests(
        user_id TEXT NOT NULL REFERENCES users(id),request_id TEXT NOT NULL,operation TEXT NOT NULL,
        request_json TEXT NOT NULL,request_hash TEXT NOT NULL,result_json TEXT NOT NULL,
        PRIMARY KEY(user_id,request_id))''',
        '''CREATE TABLE IF NOT EXISTS business_assistant_suspensions(
        plan_id TEXT PRIMARY KEY REFERENCES business_assistant_plans(id),reason TEXT NOT NULL,created_at TEXT NOT NULL)''',
        'CREATE INDEX IF NOT EXISTS business_assistant_plan_project ON business_assistant_plans(project_id,created_at)',
        'CREATE INDEX IF NOT EXISTS business_assistant_context_project ON business_assistant_contexts(project_id,created_at)',
    ]


def protected_tables():
    return TABLES


def runtime_privileges():
    return {table: ('SELECT', 'INSERT') for table in TABLES}


def guard_statements(dialect):
    if dialect == 'sqlite':
        result = [f"CREATE TRIGGER IF NOT EXISTS {table}_{action.lower()}_guard BEFORE {action} ON {table} "
            "BEGIN SELECT RAISE(ABORT,'immutable assistant history'); END" for table in TABLES for action in ('UPDATE', 'DELETE')]
        for table in TABLES:
            kind = table.removeprefix('business_assistant_')
            condition = 'id=NEW.id'
            if kind == 'rules': condition = 'id=NEW.id AND revision=NEW.revision'
            elif kind in ('decisions', 'outcomes', 'suspensions'): condition = 'plan_id=NEW.plan_id'
            elif kind == 'executions': condition = 'plan_id=NEW.plan_id OR domain_request_id=NEW.domain_request_id'
            elif kind == 'chat_results': condition = 'chat_id=NEW.chat_id'
            elif kind == 'requests': condition = 'user_id=NEW.user_id AND request_id=NEW.request_id'
            result.append(f"CREATE TRIGGER IF NOT EXISTS {table}_insert_guard BEFORE INSERT ON {table} "
                f"WHEN EXISTS(SELECT 1 FROM {table} WHERE {condition}) BEGIN SELECT RAISE(ABORT,'immutable assistant history'); END")
        return result
    if dialect == 'postgresql':
        result = ["""CREATE OR REPLACE FUNCTION business_assistant_immutable_guard() RETURNS trigger LANGUAGE plpgsql AS $$
          BEGIN RAISE EXCEPTION 'immutable assistant history'; END; $$"""]
        for table in TABLES:
            for action in ('UPDATE', 'DELETE'):
                name = table+'_'+action.lower()+'_guard'
                result.append(f"DO $$ BEGIN IF NOT EXISTS(SELECT 1 FROM pg_trigger WHERE tgname='{name}' AND tgrelid='{table}'::regclass) "
                    f"THEN CREATE TRIGGER {name} BEFORE {action} ON {table} FOR EACH ROW EXECUTE FUNCTION business_assistant_immutable_guard(); END IF; END $$")
        return result
    raise ValueError('Unsupported database dialect')


def _shape(data, fields):
    if not isinstance(data, dict) or set(data) != set(fields):
        raise Problem(400, 'Genau die vorgesehenen Assistentenfelder angeben.')


def _text(value, name, maximum, required=False):
    result = text(value, name, maximum, required=required)
    if any(0xD800 <= ord(c) <= 0xDFFF for c in result):
        raise Problem(400, 'Gültigen Unicode-Text angeben.')
    return result


def _conditions(value):
    if not isinstance(value, list) or len(value) > 8:
        raise Problem(400, 'Höchstens acht belegte Regelbedingungen angeben.')
    for item in value:
        _shape(item, ('field', 'operator', 'value'))
        if (not isinstance(item['field'], str) or item['field'] not in FACT_TYPES or item['operator'] not in ('eq', 'gte', 'lte') or
                type(item['value']) is not FACT_TYPES[item['field']] or
                (isinstance(item['value'], bool) and item['operator'] != 'eq') or
                (type(item['value']) is int and not -10**15 <= item['value'] <= 10**15)):
            raise Problem(400, 'Bedingung muss einen unterstützten serverseitigen Fakt vergleichen.')
    return value


class Assistant:
    def __init__(self, office, *, clock=None, model=None, delivery_transport=None):
        self.office, self.db = office, office.db
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self.model = model or OpenAICompatibleModel()
        self.delivery_transport = delivery_transport

    def now(self):
        return self.clock().astimezone(timezone.utc).isoformat(timespec='seconds')

    def _access(self, actor, project=None, permission='assistant.use'):
        if project is not None:
            identifier(project, 'Projekt-ID')
        return require_permission(self.office, actor, permission, project)

    def _gate(self):
        from business_schema import require_capability, require_financial_release
        require_capability(self.office, 'business_assistant')
        require_financial_release(self.office)

    def _instance(self):
        row = self.db.execute('SELECT instance_id FROM business_instance_identity WHERE singleton=1').fetchone()
        return row['instance_id'] if row else None

    def _receipt(self, actor, operation, data):
        identifier(data['request_id'], 'Vorgangs-ID')
        fingerprint = sha([operation, data])
        previous = self.db.execute('SELECT * FROM business_assistant_requests WHERE user_id=? AND request_id=?', (actor['id'], data['request_id'])).fetchone()
        if previous:
            if previous['operation'] != operation or previous['request_hash'] != fingerprint:
                raise Problem(409, 'Vorgangs-ID wurde bereits anders verwendet.')
            return fingerprint, json.loads(previous['result_json'])
        return fingerprint, None

    def _remember(self, actor, operation, data, fingerprint, result):
        self.db.execute('INSERT INTO business_assistant_requests(user_id,request_id,operation,request_json,request_hash,result_json) VALUES(?,?,?,?,?,?)',
            (actor['id'], data['request_id'], operation, canonical(data), fingerprint, canonical(result)))
        self.office.audit(actor, 'assistant.'+operation.split(':')[0], str(next(iter(result.values()), '')))

    def _row(self, kind, object_id):
        identifier(object_id)
        row = self.db.execute('SELECT * FROM business_assistant_'+kind+' WHERE id=?', (object_id,)).fetchone()
        if row is None:
            raise Problem(404, 'Assistentenvorgang nicht verfügbar.')
        return row

    def _value(self, row):
        value = json.loads(row['payload_json'])
        if not isinstance(value, dict) or sha(value) != row['sha256'] or 'id' in row.keys() and any(key in value and value[key] != row[key] for key in ('id', 'project_id', 'created_by', 'created_at') if key in row.keys()):
            raise Problem(500, 'Assistentennachweis besteht die Integritätsprüfung nicht.')
        return value

    def status(self, actor, project=None):
        self._access(actor, project)
        try:
            provider = dict(configured=True, **configuration(self.office).public())
        except Problem:
            provider = dict(configured=False, message='KI-Anbieter, Unternehmensbindung und Datenweitergabe noch nicht eingerichtet.')
        return dict(provider=provider, source_kinds=list(KINDS), triggers=list(TRIGGERS), modes=list(MODES),
            actions=[dict(action=action, external=action in EXTERNAL,
                executable=action not in ('supplier.order', 'payment.execute'),
                unavailable_reason='Kein ausführender Anbieteradapter eingerichtet.' if action in ('supplier.order', 'payment.execute') else None) for action in ACTIONS],
            default_policy='deny', payroll_sources=False, voice_recording=False)

    def sources(self, actor, project, query='', offset=0):
        with transaction(self.office):
            fresh = self._access(actor, project)
            return catalog(self.office, fresh, project, query, offset)

    def _rules(self, project):
        rows = self.db.execute('SELECT r.* FROM business_assistant_rules r WHERE project_id=? AND NOT EXISTS '
            '(SELECT 1 FROM business_assistant_rules n WHERE n.id=r.id AND n.revision>r.revision) ORDER BY r.id', (project,)).fetchall()
        return [self._value(row) for row in rows]

    def rules(self, actor, project):
        with transaction(self.office):
            self._access(actor, project)
            return dict(items=self._rules(project), default_policy='deny')

    def rule_history(self, actor, rule_id):
        identifier(rule_id)
        with transaction(self.office):
            rows = self.db.execute('SELECT * FROM business_assistant_rules WHERE id=? ORDER BY revision', (rule_id,)).fetchall()
            if not rows:
                raise Problem(404, 'Regel nicht verfügbar.')
            self._access(actor, rows[0]['project_id'])
            return dict(items=[self._value(row) for row in rows])

    def save_rule(self, actor, data):
        _shape(data, ('request_id', 'id', 'revision', 'project_id', 'title', 'enabled', 'trigger', 'action', 'mode', 'conditions', 'responsible_id', 'confirmation'))
        identifier(data['id']); identifier(data['responsible_id'])
        if (type(data['revision']) is not int or data['revision'] < 0 or type(data['enabled']) is not bool or
                data['trigger'] not in TRIGGERS or data['action'] not in ACTIONS or data['mode'] not in MODES or data['confirmation'] is not True):
            raise Problem(400, 'Versionierte Regel, Entscheidung und ausdrückliche Bestätigung erforderlich.')
        title = _text(data['title'], 'Regelbezeichnung', 200, True)
        _conditions(data['conditions'])
        with transaction(self.office):
            fresh = self._access(actor, data['project_id'], 'settings.manage')
            self._gate()
            target = dict(id=data['responsible_id'])
            if data['enabled']:
                self._access(target, data['project_id'])
            if data['enabled'] and data['mode'] != 'deny':
                action_access(self.office, target, data['project_id'], data['action'])
            digest, replay = self._receipt(fresh, 'rule', data)
            if replay:
                row = self.db.execute('SELECT * FROM business_assistant_rules WHERE id=? AND revision=?', (replay['rule_id'], replay['revision'])).fetchone()
                return self._value(row)
            previous = self.db.execute('SELECT * FROM business_assistant_rules WHERE id=? ORDER BY revision DESC LIMIT 1', (data['id'],)).fetchone()
            if (data['revision'] != (previous['revision'] if previous else 0) or previous and previous['project_id'] != data['project_id']):
                raise Problem(409, 'Regel oder Projektbindung wurde geändert.')
            value = {key: data[key] for key in ('id', 'project_id', 'enabled', 'trigger', 'action', 'mode', 'conditions', 'responsible_id')}
            value.update(title=title, revision=data['revision']+1, created_by=fresh['id'], created_at=self.now())
            self.db.execute('INSERT INTO business_assistant_rules(id,revision,project_id,payload_json,sha256,created_by,created_at) VALUES(?,?,?,?,?,?,?)',
                (value['id'], value['revision'], value['project_id'], canonical(value), sha(value), fresh['id'], value['created_at']))
            self._remember(fresh, 'rule', data, digest, dict(rule_id=value['id'], revision=value['revision']))
            return value

    def _snapshot(self, actor, project, descriptors):
        if not isinstance(descriptors, list) or not 1 <= len(descriptors) <= 8:
            raise Problem(400, 'Eine bis acht Fachquellen auswählen.')
        day = self.now()[:10]
        sources = [resolve(self.office, actor, project, descriptor, day) for descriptor in descriptors]
        if len({source['source_id'] for source in sources}) != len(sources):
            raise Problem(400, 'Jede Fachquelle nur einmal auswählen.')
        result = dict(project_id=project, instance_id=self._instance(), as_of=day,
            sources=sources, facts=facts(sources), available_actions=list(ACTIONS))
        if len(canonical(result).encode()) > 70000:
            raise Problem(413, 'Begrenzte ausdrücklich ausgewählte Datenbasis erforderlich.')
        return result

    def create_context(self, actor, data):
        _shape(data, ('request_id', 'project_id', 'sources'))
        with transaction(self.office):
            fresh = self._access(actor, data['project_id']); self._gate()
            snapshot = self._snapshot(fresh, data['project_id'], data['sources'])
            fingerprint, replay = self._receipt(fresh, 'context', data)
            if replay:
                return self.context(fresh, replay['context_id'])
            context_id = uuid.uuid4().hex
            self.db.execute('INSERT INTO business_assistant_contexts(id,project_id,created_by,payload_json,sha256,created_at) VALUES(?,?,?,?,?,?)',
                (context_id, data['project_id'], fresh['id'], canonical(snapshot), sha(snapshot), self.now()))
            self._remember(fresh, 'context', data, fingerprint, dict(context_id=context_id))
            return self.context(fresh, context_id)

    def _context(self, actor, context_id, *, current=False):
        row = self._row('contexts', context_id)
        fresh = self._access(actor, row['project_id'])
        value = self._value(row)
        if value['instance_id'] != self._instance():
            raise Problem(409, 'Unternehmensbindung des Kontexts wurde geändert.')
        live = self._snapshot(fresh, row['project_id'], [item['descriptor'] for item in value['sources']])
        same = sha(live) == row['sha256']
        if current and not same:
            raise Problem(409, 'Die fachliche Datenbasis wurde geändert; Quellen neu auswählen.')
        return row, value, same

    def context(self, actor, context_id):
        with transaction(self.office):
            row, value, current = self._context(actor, context_id)
            return dict(value, id=row['id'], sha256=row['sha256'], current=current, created_at=row['created_at'])

    def _policy_inputs(self, actor, project, trigger, action, values, rules):
        """Compute policy facts independently of the model's source selection."""
        from datetime import date
        from business_assistant_sources import _minor
        needed = {item['field'] for rule in rules if rule['enabled'] and rule['trigger'] == trigger and rule['action'] == action for item in rule['conditions']}
        needed.update({'payment.overdue':('overdue_payment',), 'task.overdue':('overdue_task',), 'cost.threshold':('total_cost_minor','costs_complete')}.get(trigger, ()))
        result = {key:None for key in FACT_TYPES}; evidence = []
        today = self.now()[:10]
        def save(kind, source, computed, permission):
            result.update(computed)
            evidence.append(dict(kind=kind, project_id=project, source=source, source_sha256=sha(source), facts=computed, permission=permission))
        if needed & {'overdue_payment','payment_overdue_days','open_minor'}:
            try:
                from business_finance import Finance
                items = Finance(self.office).open_items(actor, project)['items']
                target = values.get('document_id') if action in ('document.email','payment.execute') else None
                if action == 'dunning.email': target = Finance(self.office)._mail(values['outbox_id'])['document_id']
                if target is not None: items = [item for item in items if item['id'] == target]
                source = [dict(id=item['id'], due_date=item['due_date'], open=item['open'], paid=item['paid'], credited=item['credited']) for item in items]
                overdue = max((max(0,(date.fromisoformat(today)-date.fromisoformat(item['due_date'])).days) for item in source if _minor(item['open'])>0), default=0)
                save('open_items', dict(target_id=target, as_of=today, items=source), dict(open_minor=sum(_minor(item['open']) for item in source), payment_overdue_days=overdue, overdue_payment=overdue>0), 'finance.read')
            except Problem as error:
                if error.status not in (403,404): raise
        if needed & {'overdue_task','task_overdue_days'}:
            try:
                self._access(actor, project, 'documents.read')
                from project_workspace import ProjectWorkspace
                items = ProjectWorkspace(self.office).list_items(actor, project, 'tasks')
                source = [{key:item[key] for key in ('id','revision','status','due_date')} for item in items]
                overdue = max((max(0,(date.fromisoformat(today)-date.fromisoformat(item['due_date'])).days) for item in source if item['due_date'] and item['status'] not in ('done','cancelled')), default=0)
                save('tasks', dict(as_of=today, items=source), dict(overdue_task=overdue>0, task_overdue_days=overdue), 'documents.read')
            except Problem as error:
                if error.status not in (403,404): raise
        if needed & {'total_cost_minor','costs_complete'}:
            try:
                source = resolve(self.office, actor, project, dict(kind='costs',id=project), today)['data']
                save('costs', source, dict(total_cost_minor=source['total_cost_minor'], costs_complete=source['result']['complete_for_recorded_sources']), 'finance.read')
            except Problem as error:
                if error.status not in (403,404): raise
        return result, evidence

    def _evaluated_policy(self, actor, project, trigger, action, values):
        rules = self._rules(project)
        source_facts, evidence = self._policy_inputs(actor, project, trigger, action, values, rules)
        return self._policy(project, trigger, action, source_facts, rule_values=rules, evidence=evidence)

    def _policy(self, project, trigger, action, source_facts, *, rule_values=None, evidence=None):
        rules = self._rules(project) if rule_values is None else rule_values
        trigger_matches = trigger == 'manual' or trigger == 'payment.overdue' and source_facts['overdue_payment'] or trigger == 'task.overdue' and source_facts['overdue_task'] or trigger == 'cost.threshold' and source_facts['total_cost_minor'] is not None and source_facts['costs_complete']
        matching, uncheckable = [], []
        for rule in rules:
            if not trigger_matches or not rule['enabled'] or rule['trigger'] != trigger or rule['action'] != action:
                continue
            match, unknown = True, False
            for condition in rule['conditions']:
                actual, expected = source_facts[condition['field']], condition['value']
                if actual is None:
                    unknown = True; continue
                if not {'eq': lambda: actual == expected, 'gte': lambda: actual >= expected, 'lte': lambda: actual <= expected}[condition['operator']]():
                    match = False; break
            if match and unknown:
                uncheckable.append(rule)
            elif match:
                matching.append(rule)
        mode = 'deny' if not matching else max((rule['mode'] for rule in matching), key=lambda value: {'auto': 0, 'approval': 1, 'deny': 2}[value])
        selected = [rule for rule in matching if rule['mode'] == mode]
        responsible = {rule['responsible_id'] for rule in selected}
        ambiguous = len(responsible) > 1
        if ambiguous or uncheckable:
            mode = 'deny'
        return dict(mode=mode, responsible_id=next(iter(responsible)) if len(responsible) == 1 else None,
            matched_rules=[dict(id=rule['id'], revision=rule['revision']) for rule in matching],
            rule_versions=[dict(id=rule['id'], revision=rule['revision'], sha256=sha(rule)) for rule in rules],
            rules_sha256=sha(rules), reason='uncheckable_conditions' if uncheckable else 'ambiguous_responsibility' if ambiguous else 'matched_rule' if matching else 'no_matching_permission',
            facts=source_facts, evidence=evidence or [], uncheckable_rules=[dict(id=rule['id'],revision=rule['revision']) for rule in uncheckable],
            trigger_matched=bool(trigger_matches))

    def _insert_plan(self, actor, context_row, context, trigger, action, values, reason):
        if trigger not in TRIGGERS or action not in ACTIONS:
            raise Problem(400, 'Unterstützten Auslöser und geschlossene Fachaktion auswählen.')
        clean = parameters(action, values, context)
        policy = self._evaluated_policy(actor, context['project_id'], trigger, action, clean)
        plan_id, stamp = uuid.uuid4().hex, self.now()
        value = dict(id=plan_id, context_id=context_row['id'], project_id=context['project_id'],
            context_sha256=context_row['sha256'], trigger=trigger, action=action, parameters=clean,
            reason=_text(reason, 'Anlass', 2000, True), policy=policy, created_by=actor['id'], created_at=stamp)
        self.db.execute('INSERT INTO business_assistant_plans(id,context_id,project_id,created_by,payload_json,sha256,created_at) VALUES(?,?,?,?,?,?,?)',
            (plan_id, context_row['id'], context['project_id'], actor['id'], canonical(value), sha(value), stamp))
        self.office.audit(actor, 'assistant.action.planned', plan_id)
        return plan_id

    def create_plan(self, actor, data):
        _shape(data, ('request_id', 'context_id', 'trigger', 'action', 'parameters', 'reason'))
        automatic = False
        with transaction(self.office):
            context_row, context, current = self._context(actor, data['context_id'])
            fresh = self._access(actor, context['project_id']); self._gate()
            fingerprint, replay = self._receipt(fresh, 'plan', data)
            if replay:
                return self.plan(fresh, replay['plan_id'])
            if not current:
                raise Problem(409, 'Die Datenbasis wurde geändert; aktuellen Kontext neu auswählen.')
            plan_id = self._insert_plan(fresh, context_row, context, data['trigger'], data['action'], data['parameters'], data['reason'])
            self._remember(fresh, 'plan', data, fingerprint, dict(plan_id=plan_id))
            plan = self._value(self._row('plans', plan_id))
            automatic = plan['policy']['mode'] == 'auto' and plan['policy']['responsible_id'] == fresh['id']
        if automatic:
            self._automatic(fresh, plan_id)
        return self.plan(fresh, plan_id)

    def _automatic(self, actor, plan_id):
        try:
            self.execute(actor, plan_id, dict(request_id=uuid.uuid5(uuid.NAMESPACE_URL, 'smartplan-assistant-auto:'+plan_id).hex,
                plan_sha256=self._row('plans', plan_id)['sha256'], confirmation=True))
        except Problem:
            # The plan remains inspectable with its actual current gate state.
            # An action is never silently re-planned or blindly re-sent.
            return

    def _plan_access(self, actor, plan_id, *, current=False):
        row = self._row('plans', plan_id)
        fresh = self._access(actor, row['project_id'])
        value = self._value(row)
        for proof in value['policy']['evidence']:
            self._access(fresh, row['project_id'], proof['permission'])
        context_row, context, same = self._context(fresh, row['context_id'], current=current)
        if context_row['sha256'] != value['context_sha256'] or context['project_id'] != row['project_id']:
            raise Problem(500, 'Aktionsnachweis gehört nicht zur dokumentierten Quelle.')
        return fresh, row, value, context, same

    def _action_gate(self, actor, plan):
        self._gate()
        from business_organization import module_enabled
        module = 'material' if plan['action'] == 'supplier.order' else 'finance' if plan['action'] in ('dunning.email', 'payment.execute') else 'documents'
        if not module_enabled(self.office, module):
            raise Problem(423, 'Der betroffene Fachbereich ist deaktiviert.')
        action_access(self.office, actor, plan['project_id'], plan['action'])

    def _authorize_execution(self, actor, plan_id, *, require_transport=True):
        fresh, row, value, context, _ = self._plan_access(actor, plan_id, current=True)
        self._action_gate(fresh, value)
        if self.db.execute('SELECT 1 FROM business_assistant_suspensions WHERE plan_id=?', (plan_id,)).fetchone():
            raise Problem(409, 'Dieser offene Plan wurde bei Wiederherstellung gesperrt; neu prüfen.')
        policy = self._evaluated_policy(fresh, value['project_id'], value['trigger'], value['action'], value['parameters'])
        if policy != value['policy']:
            raise Problem(409, 'Regeln wurden geändert; Aktionsvorschlag neu vorbereiten.')
        if policy['mode'] == 'deny':
            raise Problem(403, 'Die serverseitigen Unternehmensregeln verbieten diese Aktion.')
        if policy['responsible_id'] != fresh['id']:
            raise Problem(403, 'Nur die aktuell zuständige Person darf diese Aktion ausführen.')
        decision = self.db.execute('SELECT * FROM business_assistant_decisions WHERE plan_id=?', (plan_id,)).fetchone()
        if decision and decision['decision'] == 'rejected':
            raise Problem(403, 'Diese Aktion wurde abgelehnt.')
        if policy['mode'] == 'approval':
            self._access(fresh, value['project_id'], 'assistant.approve')
            if decision is None or decision['decision'] != 'approved' or decision['plan_sha256'] != row['sha256']:
                raise Problem(409, 'Freigabe dieser konkreten Quelle, Regelversion und Aktion fehlt.')
        if value['action'] in ('supplier.order', 'payment.execute'):
            raise Problem(409, 'Kein ausführender Bestell- oder Bankadapter eingerichtet; keine Außenwirkung erfolgt.')
        if require_transport and value['action'] in EXTERNAL and self.delivery_transport is None:
            from business_delivery import configuration as delivery_configuration
            delivery_configuration()
        return fresh, row, value, context

    def plan(self, actor, plan_id):
        with transaction(self.office):
            fresh, row, value, context, current = self._plan_access(actor, plan_id)
            decision = self.db.execute('SELECT * FROM business_assistant_decisions WHERE plan_id=?', (plan_id,)).fetchone()
            execution = self.db.execute('SELECT * FROM business_assistant_executions WHERE plan_id=?', (plan_id,)).fetchone()
            outcome = self.db.execute('SELECT * FROM business_assistant_outcomes WHERE plan_id=?', (plan_id,)).fetchone()
            status = 'denied' if value['policy']['mode'] == 'deny' else 'awaiting_approval' if value['policy']['mode'] == 'approval' and decision is None else 'ready'
            if decision and decision['decision'] == 'rejected': status = 'rejected'
            if execution: status = outcome['status'] if outcome else 'unconfirmed'
            elif not current or self._evaluated_policy(fresh, value['project_id'], value['trigger'], value['action'], value['parameters']) != value['policy']: status = 'stale'
            elif self.db.execute('SELECT 1 FROM business_assistant_suspensions WHERE plan_id=?', (plan_id,)).fetchone(): status = 'suspended_after_restore'
            elif status != 'denied' and value['action'] in ('supplier.order', 'payment.execute'): status = 'adapter_blocked'
            can_execute = False
            blocked_reason = None
            if not execution:
                try:
                    self._authorize_execution(fresh, plan_id)
                    can_execute = True
                except Problem as error:
                    if error.status not in (403, 404, 409, 423): raise
                    blocked_reason = error.message
            return dict(value, sha256=row['sha256'], status=status, source_current=current, can_execute=can_execute,
                execution_blocked_reason=blocked_reason,
                decision=dict(decision) if decision else None,
                execution=dict(execution) if execution else None,
                outcome=None if outcome is None else dict(status=outcome['status'], result=self._value(outcome), created_at=outcome['created_at']))

    def plans(self, actor, project):
        with transaction(self.office):
            self._access(actor, project)
            result = []
            for row in self.db.execute('SELECT id FROM business_assistant_plans WHERE project_id=? ORDER BY created_at DESC,id DESC LIMIT 100', (project,)).fetchall():
                try: result.append(self.plan(actor, row['id']))
                except Problem as error:
                    if error.status not in (403, 404): raise
            return dict(items=result)

    def decide(self, actor, plan_id, approved, data):
        _shape(data, ('request_id', 'plan_sha256', 'reason', 'confirmation'))
        if data['confirmation'] is not True:
            raise Problem(400, 'Die konkrete Aktionsentscheidung ausdrücklich bestätigen.')
        reason = _text(data['reason'], 'Prüfvermerk', 1000, True)
        with transaction(self.office):
            fresh, row, value, context, _ = self._plan_access(actor, plan_id, current=True)
            self._access(fresh, row['project_id'], 'assistant.approve'); self._action_gate(fresh, value)
            if (data['plan_sha256'] != row['sha256'] or value['policy']['mode'] == 'deny' or
                    value['policy']['responsible_id'] != fresh['id'] or
                    self._evaluated_policy(fresh, row['project_id'], value['trigger'], value['action'], value['parameters']) != value['policy']):
                raise Problem(409, 'Freigabe passt nicht zur aktuellen erlaubten Aktion und zuständigen Person.')
            operation = ('approve:' if approved else 'reject:')+plan_id
            fingerprint, replay = self._receipt(fresh, operation, data)
            if replay:
                return self.plan(fresh, plan_id)
            if self.db.execute('SELECT 1 FROM business_assistant_decisions WHERE plan_id=?', (plan_id,)).fetchone() or self.db.execute('SELECT 1 FROM business_assistant_executions WHERE plan_id=?', (plan_id,)).fetchone():
                raise Problem(409, 'Dieser Aktionsplan wurde bereits entschieden oder gestartet.')
            self.db.execute('INSERT INTO business_assistant_decisions(plan_id,decision,plan_sha256,reason,created_by,created_at) VALUES(?,?,?,?,?,?)',
                (plan_id, 'approved' if approved else 'rejected', row['sha256'], reason, fresh['id'], self.now()))
            self._remember(fresh, operation, data, fingerprint, dict(plan_id=plan_id))
            return self.plan(fresh, plan_id)

    def _outcome(self, plan_id, status, value):
        self.db.execute('INSERT INTO business_assistant_outcomes(plan_id,status,payload_json,sha256,created_at) VALUES(?,?,?,?,?)',
            (plan_id, status, canonical(value), sha(value), self.now()))

    def execute(self, actor, plan_id, data):
        _shape(data, ('request_id', 'plan_sha256', 'confirmation'))
        if data['confirmation'] is not True:
            raise Problem(400, 'Die angezeigte konkrete Aktion ausdrücklich bestätigen.')
        with transaction(self.office):
            fresh, row, value, context, _ = self._plan_access(actor, plan_id)
            action_access(self.office, fresh, row['project_id'], value['action'])
            operation = 'execute:'+plan_id
            fingerprint, replay = self._receipt(fresh, operation, data)
            if data['plan_sha256'] != row['sha256']:
                raise Problem(409, 'Aktionsplan wurde geändert.')
            # A known result is read-only; current source rights are still checked.
            if replay or self.db.execute('SELECT 1 FROM business_assistant_executions WHERE plan_id=?', (plan_id,)).fetchone():
                return self.plan(fresh, plan_id)
            fresh, row, value, context = self._authorize_execution(fresh, plan_id)
            domain_request = uuid.uuid4().hex
            self.db.execute('INSERT INTO business_assistant_executions(plan_id,domain_request_id,created_by,created_at) VALUES(?,?,?,?)', (plan_id, domain_request, fresh['id'], self.now()))
            self._remember(fresh, operation, data, fingerprint, dict(plan_id=plan_id))
            if value['action'] not in EXTERNAL:
                from business_assistant_sources import execute_internal
                result = execute_internal(self.office, fresh, value, context, domain_request)
                self._outcome(plan_id, 'succeeded', result)
                self.office.audit(fresh, 'assistant.action.succeeded', plan_id)
                return self.plan(fresh, plan_id)
        # The execution claim is committed before outside I/O. A retry only reads
        # this record, including an unresolved crash; it never repeats delivery.
        from business_assistant_sources import execute_external
        api = self
        class GuardedTransport:
            def send(self, job):
                with transaction(api.office):
                    api._authorize_execution(fresh, plan_id)
                if api.delivery_transport is not None:
                    transport = api.delivery_transport
                else:
                    from business_delivery import configured_transport
                    transport = configured_transport()
                return transport.send(job)
        try:
            result = execute_external(self.office, fresh, value, context, domain_request, transport=GuardedTransport())
            raw_status = result.get('status')
            status = 'succeeded' if raw_status in ('accepted', 'sent') else 'unknown' if raw_status in ('unknown', 'sending') else 'failed'
        except Problem as error:
            # The domain receipt remains the authority for any external outcome.
            status, result = 'blocked', dict(error_code='business_gate_rejected', status_code=error.status,
                review_required=True, action=value['action'])
        except Exception:
            status, result = 'unknown', dict(error_code='execution_unconfirmed', review_required=True, action=value['action'])
        with transaction(self.office):
            self._outcome(plan_id, status, result)
            self.office.audit(fresh, 'assistant.action.'+status, plan_id)
        return self.plan(fresh, plan_id)

    def _answer(self, value, context):
        _shape(value, ('summary', 'citations', 'facts', 'proposals'))
        _text(value['summary'], 'Modellantwort', 4000, True)
        sources = {source['source_id']: source['data'] for source in context['sources']}
        citations = value['citations']
        if (not isinstance(citations, list) or not 1 <= len(citations) <= 8 or
                any(not isinstance(item, str) or item not in sources for item in citations) or len(set(citations)) != len(citations)):
            raise Problem(502, 'KI-Antwort benötigt überprüfbare ausgewählte Quellen.')
        if not isinstance(value['facts'], list) or len(value['facts']) > 12 or not isinstance(value['proposals'], list) or len(value['proposals']) > 3:
            raise Problem(502, 'Begrenzte quellgebundene KI-Antwort erwartet.')
        verified = []
        for selected in value['facts']:
            _shape(selected, ('source_id', 'path'))
            if selected['source_id'] not in citations or not isinstance(selected['path'], str) or not re.fullmatch(r'[a-z][a-z0-9_]*(?:\.(?:[a-z][a-z0-9_]*|\d{1,3})){0,6}', selected['path']):
                raise Problem(502, 'Fakt verweist nicht auf eine ausgewählte belegte Quelle.')
            raw = sources[selected['source_id']]
            try:
                for field in selected['path'].split('.'):
                    raw = raw[int(field)] if isinstance(raw, list) and field.isdigit() else raw[field]
            except (KeyError, IndexError, TypeError):
                raise Problem(502, 'KI-Fakt existiert nicht in der angegebenen Fachquelle.') from None
            if not (raw is None or type(raw) in (bool, int, str)) or isinstance(raw, str) and len(raw) > 1500:
                raise Problem(502, 'Einzelnen belegten Fakt auswählen.')
            verified.append(dict(selected, value=raw))
        proposals = []
        for item in value['proposals']:
            _shape(item, ('action', 'parameters', 'reason'))
            # Validate every proposal before any plan or business action exists.
            proposals.append(dict(action=item['action'], parameters=parameters(item['action'], item['parameters'], context),
                reason=_text(item['reason'], 'Vorschlagsbegründung', 2000, True)))
        # Free prose can contain invented amounts in words as well as digits.
        # It is therefore never published as a business-fact answer. The model
        # selects evidence and drafts; actual answer values always come from DB.
        summary = 'Die ausgewählten Fachquellen belegen die nachstehenden Angaben.' if verified else 'Es wurden keine überprüfbaren Einzelangaben ausgewählt.'
        return dict(response_type='source_answer', summary=summary, citations=citations, facts=verified, proposals=proposals,
            model_generated=False, selection_generated_by_model=True,
            business_values='resolved_from_selected_sources', actions_executed_by_model=False)

    def _chat_result(self, chat_id, status, value):
        self.db.execute('INSERT INTO business_assistant_chat_results(chat_id,status,payload_json,sha256,created_at) VALUES(?,?,?,?,?)',
            (chat_id, status, canonical(value), sha(value), self.now()))

    def chat(self, actor, data):
        _shape(data, ('request_id', 'context_id', 'message', 'data_transfer_confirmed'))
        message = _text(data['message'], 'Nachricht', 4000, True)
        if data['data_transfer_confirmed'] is not True:
            raise Problem(400, 'Weitergabe dieser Nachricht und ausgewählten Fachquellen ausdrücklich bestätigen.')
        with transaction(self.office):
            context_row, context, current = self._context(actor, data['context_id'])
            fresh = self._access(actor, context['project_id']); self._gate()
            fingerprint, replay = self._receipt(fresh, 'chat', data)
            if replay:
                return self.chat_view(fresh, replay['chat_id'])
            if not current:
                raise Problem(409, 'Die Datenbasis wurde geändert; aktuellen Kontext neu auswählen.')
            config = configuration(self.office)
            chat_id, stamp = uuid.uuid4().hex, self.now()
            value = dict(id=chat_id, context_id=context_row['id'], context_sha256=context_row['sha256'],
                project_id=context['project_id'], message=message, provider=config.public(),
                provider_sha256=sha(config.public()), data_transfer_confirmed=True,
                created_by=fresh['id'], created_at=stamp)
            self.db.execute('INSERT INTO business_assistant_chats(id,context_id,project_id,created_by,payload_json,sha256,created_at) VALUES(?,?,?,?,?,?,?)',
                (chat_id, context_row['id'], context['project_id'], fresh['id'], canonical(value), sha(value), stamp))
            self._remember(fresh, 'chat', data, fingerprint, dict(chat_id=chat_id))
        # This is the only model invocation. The committed request is never
        # automatically reissued after timeout, response loss or a worker crash.
        plans = []
        try:
            response = self.model.complete(config, context, message, chat_id)
            answer = self._answer(response, context)
            with transaction(self.office):
                current_row, current_context, _ = self._context(fresh, context_row['id'], current=True)
                self._access(fresh, context['project_id']); self._gate()
                if sha(configuration(self.office).public()) != value['provider_sha256']:
                    raise Problem(409, 'KI-Anbieterkonfiguration wurde während der Antwort geändert.')
                for proposal in answer.pop('proposals'):
                    plans.append(self._insert_plan(fresh, current_row, current_context, 'manual',
                        proposal['action'], proposal['parameters'], proposal['reason']))
                answer['plan_ids'] = plans
                self._chat_result(chat_id, 'completed', answer)
                self.office.audit(fresh, 'assistant.chat.completed', chat_id)
        except Problem as error:
            plans = []
            with transaction(self.office):
                self._chat_result(chat_id, 'stale' if error.status in (401, 403, 404, 409, 423) else 'failed',
                    dict(error_code='sources_or_access_changed' if error.status in (401, 403, 404, 409, 423) else 'provider_answer_unconfirmed',
                         retry_automatically=False, provider_call_may_have_been_charged=True))
        except Exception:
            plans = []
            with transaction(self.office):
                self._chat_result(chat_id, 'failed', dict(error_code='provider_answer_unconfirmed',
                    retry_automatically=False, provider_call_may_have_been_charged=True))
        for plan_id in plans:
            with transaction(self.office):
                plan = self._value(self._row('plans', plan_id))
            if plan['policy']['mode'] == 'auto' and plan['policy']['responsible_id'] == fresh['id']:
                self._automatic(fresh, plan_id)
        return self.chat_view(fresh, chat_id)

    def chat_view(self, actor, chat_id):
        with transaction(self.office):
            row = self._row('chats', chat_id)
            fresh = self._access(actor, row['project_id'])
            if row['created_by'] != fresh['id']:
                raise Problem(404, 'Dieser persönliche Chat ist nicht verfügbar.')
            value = self._value(row)
            _, _, current = self._context(fresh, row['context_id'])
            result = self.db.execute('SELECT * FROM business_assistant_chat_results WHERE chat_id=?', (chat_id,)).fetchone()
            return dict(value, status=result['status'] if result else 'unconfirmed', source_current=current,
                result=self._value(result) if result else None,
                retry_automatically=False)

    def chats(self, actor, project):
        with transaction(self.office):
            fresh = self._access(actor, project)
            items = []
            for row in self.db.execute('SELECT id FROM business_assistant_chats WHERE project_id=? AND created_by=? ORDER BY created_at DESC,id DESC LIMIT 30', (project, fresh['id'])).fetchall():
                try: items.append(self.chat_view(fresh, row['id']))
                except Problem as error:
                    if error.status not in (403, 404): raise
            return dict(items=items)


def require_send_policy(office, actor, project_id, action, target_id, request_id):
    """Native document/dunning gate; arguments come from the domain's own IDs.

    Call only on a delivery path which may still perform I/O, after returning
    already accepted/unknown native receipts. No request flag bypasses policy.
    Existing manual confirmation remains sufficient when no active matching
    manual-event rule applies. Configured rules otherwise require the immutable
    source-bound plan/execution ledger, including automatically permitted work.
    """
    if action not in ('document.email','dunning.email'):
        raise Problem(400, 'Unbekannte regelgebundene Versandaktion.')
    identifier(project_id); identifier(target_id); identifier(request_id)
    with transaction(office):
        from business_schema import _tables
        if 'business_assistant_rules' not in _tables(office):
            return
        api = Assistant(office)
        field = 'document_id' if action == 'document.email' else 'outbox_id'
        execution = office.db.execute('SELECT * FROM business_assistant_executions WHERE domain_request_id=?', (request_id,)).fetchone()
        if execution:
            plan = api._value(api._row('plans', execution['plan_id']))
            if (execution['created_by'] != actor.get('id') or plan['project_id'] != project_id or
                    plan['action'] != action or plan['parameters'] != {field:target_id}):
                raise Problem(403, 'Ausführungsnachweis gehört nicht zu Akteur, Projekt und Versandziel.')
            api._authorize_execution(actor, execution['plan_id'], require_transport=False)
            return
        rules = api._rules(project_id)
        if not any(rule['enabled'] and rule['trigger'] == 'manual' and rule['action'] == action for rule in rules):
            return
        source_facts, evidence = api._policy_inputs(actor, project_id, 'manual', action, {field:target_id}, rules)
        policy = api._policy(project_id, 'manual', action, source_facts, rule_values=rules, evidence=evidence)
        if not policy['matched_rules'] and not policy['uncheckable_rules']:
            return
        if policy['mode'] == 'deny':
            raise Problem(403, 'Unternehmensregel verbietet den Versand oder ihre Voraussetzungen sind nicht sicher prüfbar.')
        raise Problem(409, 'Für diesen Versand ist der konkrete regelgeprüfte Aktionsplan erforderlich; dort freigeben und ausführen.')


def sanitize_after_restore(db):
    tables = {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()} if isinstance(db, sqlite3.Connection) else {row[0] for row in db.execute("SELECT tablename FROM pg_tables WHERE schemaname='public'").fetchall()}
    if 'business_assistant_plans' not in tables:
        return
    from core import now_iso
    stamp = now_iso()
    for row in db.execute('SELECT id FROM business_assistant_plans p WHERE NOT EXISTS(SELECT 1 FROM business_assistant_outcomes o WHERE o.plan_id=p.id)').fetchall():
        if not db.execute('SELECT 1 FROM business_assistant_suspensions WHERE plan_id=?', (row['id'],)).fetchone():
            db.execute('INSERT INTO business_assistant_suspensions(plan_id,reason,created_at) VALUES(?,?,?)',
                (row['id'], 'Offene Aktion nach Wiederherstellung erneut vorbereiten.', stamp))
    for row in db.execute('SELECT id FROM business_assistant_chats c WHERE NOT EXISTS(SELECT 1 FROM business_assistant_chat_results r WHERE r.chat_id=c.id)').fetchall():
        value = dict(error_code='interrupted_by_restore', retry_automatically=False, provider_call_may_have_been_charged=True)
        db.execute('INSERT INTO business_assistant_chat_results(chat_id,status,payload_json,sha256,created_at) VALUES(?,?,?,?,?)',
            (row['id'], 'interrupted', canonical(value), sha(value), stamp))


def validate_integrity(office):
    api, db = Assistant(office), office.db
    try:
        rules = {}
        for row in db.execute('SELECT * FROM business_assistant_rules ORDER BY id,revision').fetchall():
            value = api._value(row); identifier(row['id']); _conditions(value['conditions'])
            if (row['revision'] != sum(1 for key in rules if key[0] == row['id'])+1 or
                    value['revision'] != row['revision'] or value['action'] not in ACTIONS or
                    value['mode'] not in MODES or value['trigger'] not in TRIGGERS or type(value['enabled']) is not bool):
                raise ValueError('Invalid assistant rule chain')
            identifier(value['responsible_id'])
            rules[(row['id'], row['revision'])] = value
        contexts = {}
        for row in db.execute('SELECT * FROM business_assistant_contexts').fetchall():
            value = api._value(row); identifier(row['id'])
            if set(value) != {'project_id','instance_id','as_of','sources','facts','available_actions'} or not 1 <= len(value['sources']) <= 8 or value['available_actions'] != list(ACTIONS):
                raise ValueError('Invalid assistant context')
            seen = set()
            for source in value['sources']:
                _shape(source, ('source_id','descriptor','data','sha256'))
                _shape(source['descriptor'], ('kind','id'))
                kind, object_id = source['descriptor']['kind'], identifier(source['descriptor']['id'])
                if (kind not in KINDS or source['source_id'] != kind+':'+object_id or
                        source['source_id'] in seen or sha(source['data']) != source['sha256'] or
                        'project_id' in source['data'] and source['data']['project_id'] != row['project_id'] or
                        kind in ('project','costs') and object_id != row['project_id']):
                    raise ValueError('Invalid assistant source binding')
                seen.add(source['source_id'])
            if facts(value['sources']) != value['facts']:
                raise ValueError('Assistant facts differ from recorded sources')
            contexts[row['id']] = (row, value)
        plans = {}
        for row in db.execute('SELECT * FROM business_assistant_plans').fetchall():
            value = api._value(row)
            context_row, context = contexts[row['context_id']]
            archived_rules = []
            for reference in value['policy']['rule_versions']:
                rule = rules[(reference['id'], reference['revision'])]
                if rule['project_id'] != row['project_id'] or sha(rule) != reference['sha256']:
                    raise ValueError('Invalid assistant rule reference')
                archived_rules.append(rule)
            if (row['context_id'] != value['context_id'] or row['project_id'] != context_row['project_id'] or
                    value['context_sha256'] != context_row['sha256'] or value['trigger'] not in TRIGGERS or
                    parameters(value['action'], value['parameters'], context) != value['parameters'] or
                    api._policy(row['project_id'], value['trigger'], value['action'], value['policy']['facts'], rule_values=archived_rules, evidence=value['policy']['evidence']) != value['policy']):
                raise ValueError('Invalid assistant plan or policy evidence')
            aggregate = {key:None for key in FACT_TYPES}
            for proof in value['policy']['evidence']:
                if proof['project_id'] != row['project_id'] or sha(proof['source']) != proof['source_sha256']:
                    raise ValueError('Invalid independent policy evidence')
                source = proof['source']
                from business_assistant_sources import _minor
                from datetime import date
                if proof['kind'] == 'open_items':
                    items = source['items']
                    overdue = max((max(0,(date.fromisoformat(source['as_of'])-date.fromisoformat(item['due_date'])).days) for item in items if _minor(item['open'])>0), default=0)
                    expected = dict(open_minor=sum(_minor(item['open']) for item in items), payment_overdue_days=overdue, overdue_payment=overdue>0)
                    if proof['permission'] != 'finance.read' or source['target_id'] is not None and any(item['id'] != source['target_id'] for item in items):
                        raise ValueError('Wrong payment policy scope')
                    if value['action'] in ('document.email','payment.execute') and source['target_id'] != value['parameters']['document_id']:
                        raise ValueError('Payment policy is not bound to action target')
                elif proof['kind'] == 'tasks':
                    overdue = max((max(0,(date.fromisoformat(source['as_of'])-date.fromisoformat(item['due_date'])).days) for item in source['items'] if item['due_date'] and item['status'] not in ('done','cancelled')), default=0)
                    expected = dict(overdue_task=overdue>0, task_overdue_days=overdue)
                    if proof['permission'] != 'documents.read': raise ValueError('Wrong task policy scope')
                elif proof['kind'] == 'costs':
                    expected = dict(total_cost_minor=sum(_minor(item) for item in source['costs'].values()), costs_complete=source['result']['complete_for_recorded_sources'])
                    if proof['permission'] != 'finance.read' or source['project_id'] != row['project_id']: raise ValueError('Wrong cost policy scope')
                else: raise ValueError('Unknown independent policy source')
                if expected != proof['facts']: raise ValueError('Policy facts differ from their original evidence')
                aggregate.update(expected)
            if aggregate != value['policy']['facts']:
                raise ValueError('Policy fact set differs from its evidence')
            plans[row['id']] = (row, value)
        for row in db.execute('SELECT * FROM business_assistant_decisions').fetchall():
            plan_row, plan = plans[row['plan_id']]
            if row['plan_sha256'] != plan_row['sha256'] or row['created_by'] != plan['policy']['responsible_id'] or plan['policy']['mode'] == 'deny':
                raise ValueError('Decision does not authorize this plan')
            _text(row['reason'], 'Grund', 1000, True)
        executions = {row['plan_id']: row for row in db.execute('SELECT * FROM business_assistant_executions').fetchall()}
        for row in executions.values():
            _, plan = plans[row['plan_id']]; identifier(row['domain_request_id'])
            if plan['policy']['mode'] == 'deny' or row['created_by'] != plan['policy']['responsible_id']:
                raise ValueError('Forbidden assistant execution')
            if plan['policy']['mode'] == 'approval':
                decision = db.execute('SELECT decision FROM business_assistant_decisions WHERE plan_id=?', (row['plan_id'],)).fetchone()
                if decision is None or decision['decision'] != 'approved':
                    raise ValueError('Execution without required approval')
        for row in db.execute('SELECT * FROM business_assistant_outcomes').fetchall():
            value = api._value(row)
            execution = executions[row['plan_id']]; _, plan = plans[row['plan_id']]
            if row['status'] == 'succeeded':
                if plan['action'] in ('task.create','offer.draft'):
                    table, result_field = ('workspace_requests','result') if plan['action'] == 'task.create' else ('business_document_requests','result_json')
                    saved = db.execute('SELECT '+result_field+' FROM '+table+' WHERE user_id=? AND request_id=?', (execution['created_by'], execution['domain_request_id'])).fetchone()
                    if saved is None or json.loads(saved[result_field]) != value:
                        raise ValueError('Assistant success differs from actual business receipt')
                elif plan['action'] not in ('document.email','dunning.email') or value.get('status') not in ('accepted','sent'):
                    raise ValueError('Unsupported asserted external success')
        chats = {}
        for row in db.execute('SELECT * FROM business_assistant_chats').fetchall():
            value = api._value(row); context_row, context = contexts[row['context_id']]
            if (value['context_id'] != row['context_id'] or row['project_id'] != context_row['project_id'] or
                    value['context_sha256'] != context_row['sha256'] or value['provider_sha256'] != sha(value['provider']) or
                    value['data_transfer_confirmed'] is not True or value['provider']['instance_id'] != context['instance_id'] or
                    set(value['provider']) != {'adapter','instance_id','endpoint','model'}):
                raise ValueError('Invalid instance-bound model request')
            chats[row['id']] = (row, value, context)
        for row in db.execute('SELECT * FROM business_assistant_chat_results').fetchall():
            value = api._value(row); chat_row, _, context = chats[row['chat_id']]
            if row['status'] == 'completed':
                original = dict(summary='Archived model selection', citations=value['citations'],
                    facts=[{key: item[key] for key in ('source_id','path')} for item in value['facts']], proposals=[])
                expected = api._answer(original, context); expected.pop('proposals')
                expected['plan_ids'] = value['plan_ids']
                if value != expected:
                    raise ValueError('Model answer differs from authoritative source facts')
                for plan_id in value['plan_ids']:
                    plan_row, _ = plans[plan_id]
                    if plan_row['context_id'] != chat_row['context_id'] or plan_row['created_by'] != chat_row['created_by']:
                        raise ValueError('Model action crossed source or user boundary')
        for row in db.execute('SELECT * FROM business_assistant_requests').fetchall():
            request = json.loads(row['request_json']); result = json.loads(row['result_json']); identifier(row['request_id'])
            if request['request_id'] != row['request_id'] or sha([row['operation'],request]) != row['request_hash']:
                raise ValueError('Assistant receipt differs from original command')
            operation = row['operation'].split(':')[0]
            if operation == 'context': target, _ = contexts[result['context_id']]
            elif operation == 'chat': target, _, _ = chats[result['chat_id']]
            elif operation == 'rule':
                target = rules[(result['rule_id'],result['revision'])]
            elif operation == 'execute': target = executions[result['plan_id']]
            elif operation in ('approve','reject'):
                target = db.execute('SELECT * FROM business_assistant_decisions WHERE plan_id=?', (result['plan_id'],)).fetchone()
            elif operation == 'plan': target, _ = plans[result['plan_id']]
            else: raise ValueError('Unknown assistant receipt operation')
            if target is None or target['created_by'] != row['user_id']:
                raise ValueError('Assistant receipt has foreign actor')
        for row in db.execute('SELECT * FROM business_assistant_suspensions').fetchall():
            if row['plan_id'] not in plans:
                raise ValueError('Unknown restore suspension')
    except (Problem, KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
        raise ValueError('Invalid assistant workflow history') from error
    return True


def methods(path):
    if path in ('/assistant/status','/assistant/sources') or re.fullmatch(r'/assistant/(?:contexts|plans|chat)/'+ID, path) or re.fullmatch(r'/assistant/rules/'+ID+r'/history', path): return 'GET'
    if path in ('/assistant/rules','/assistant/plans','/assistant/chat'): return 'GET, POST'
    if path == '/assistant/contexts' or re.fullmatch(r'/assistant/plans/'+ID+r'/(?:approve|reject|execute)', path): return 'POST'
    return None


def dispatch(office, actor, path, method, data):
    allowed = methods(path)
    if allowed is None: return None
    if method not in allowed.split(', '): raise Problem(405, 'Methode nicht erlaubt.')
    if not isinstance(data, dict): raise Problem(400, 'JSON-Objekt erwartet.')
    query = data.get('_query', {})
    body = {key:value for key,value in data.items() if key != '_query'}
    api = Assistant(office)
    if method == 'GET':
        if body: raise Problem(400, 'Keine zusätzlichen Abrufinhalte erlaubt.')
        if path == '/assistant/sources':
            if not isinstance(query,dict) or not {'project_id'}<=set(query)<= {'project_id','q','offset'}:
                raise Problem(400, 'Projekt und optionale Quellensuche angeben.')
            offset = query.get('offset','0')
            if not isinstance(offset,str) or not re.fullmatch(r'0|[1-9][0-9]{0,5}',offset) or int(offset)>100000:
                raise Problem(400, 'Gültige Position der Quellensuche angeben.')
            result = api.sources(actor,query['project_id'],query.get('q',''),int(offset))
        elif path in ('/assistant/rules','/assistant/plans','/assistant/chat'):
            _shape(query, ('project_id',))
            result = {'/assistant/sources':api.sources, '/assistant/rules':api.rules, '/assistant/plans':api.plans, '/assistant/chat':api.chats}[path](actor, query['project_id'])
        else:
            if path == '/assistant/status':
                if not isinstance(query, dict) or set(query) not in (set(), {'project_id'}):
                    raise Problem(400, 'Nur einen optionalen Projektfilter angeben.')
                result = api.status(actor, query.get('project_id'))
            elif path.endswith('/history'):
                _shape(query, ())
                result = api.rule_history(actor, path.split('/')[3])
            else:
                _shape(query, ())
                kind, object_id = path.split('/')[2:]
                result = {'contexts':api.context,'plans':api.plan,'chat':api.chat_view}[kind](actor, object_id)
    else:
        if query: raise Problem(400, 'Keine zusätzlichen Schreibfilter erlaubt.')
        try:
            if path == '/assistant/rules': result = api.save_rule(actor, body)
            elif path == '/assistant/contexts': result = api.create_context(actor, body)
            elif path == '/assistant/plans': result = api.create_plan(actor, body)
            elif path == '/assistant/chat': result = api.chat(actor, body)
            else:
                plan_id, action = path.split('/')[3:]
                result = api.execute(actor, plan_id, body) if action == 'execute' else api.decide(actor, plan_id, action == 'approve', body)
        except Problem as error:
            if error.status == 409 and isinstance(body.get('request_id'), str) and re.fullmatch(ID, body['request_id']):
                # Every acceptance writes this receipt in the same transaction
                # as its plan/change and before outside I/O. Only a positively
                # established absent receipt permits the client to discard an
                # attempted command. Existing or uncertain attempts stay frozen.
                with transaction(office):
                    from business_foundation import _fresh
                    try: fresh = _fresh(office, actor)
                    except Problem: raise error
                    if not office.db.execute('SELECT 1 FROM business_assistant_requests WHERE user_id=? AND request_id=?', (fresh['id'], body['request_id'])).fetchone():
                        raise Problem(409, error.message, request_resolution='not_accepted') from None
            raise
    return result, 200, 'application/json'

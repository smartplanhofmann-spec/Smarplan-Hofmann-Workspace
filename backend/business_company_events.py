"""Company event processing, persisted policies and closed business actions.

No model, caller-supplied event, tenant selector or arbitrary tool is accepted.
The explicit rule is the delegation; each action rechecks the named user's
current rights and the original domain's own gates.
"""
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
import json
import re
import sqlite3
import uuid

from core import Problem, canonical
from business_foundation import require_permission
from business_operations import identifier, text, transaction
from business_assistant_sources import ACTIONS, EXTERNAL, action_access, resolve, sha
from company_event_sources import (TRIGGERS, FACTS, COMPATIBLE, shape, conditions,
    template, event_values, observe, candidates, policy, action_context, read_source, combine_policy,
    recorded_parameters, project_policy_projection)

FEATURES = ('company_event_rules',)
BASE = '/company-events'
ID = r'[a-f0-9]{32}'
TABLES = tuple('business_company_event_'+name for name in
    ('rules', 'observations', 'plans', 'runs', 'run_results', 'decisions',
     'executions', 'outcomes', 'requests', 'suspensions'))


def schema_statements(binary_type='BYTEA'):
    result = [
        '''CREATE TABLE IF NOT EXISTS business_company_event_rules(
          id TEXT NOT NULL,revision INTEGER NOT NULL CHECK(revision>0),payload_json TEXT NOT NULL,
          sha256 TEXT NOT NULL,created_by TEXT NOT NULL REFERENCES users(id),created_at TEXT NOT NULL,
          PRIMARY KEY(id,revision))''',
        '''CREATE TABLE IF NOT EXISTS business_company_event_observations(
          id TEXT PRIMARY KEY,project_id TEXT NOT NULL REFERENCES projects(id),occurrence_key TEXT NOT NULL,
          payload_json TEXT NOT NULL,sha256 TEXT NOT NULL,created_by TEXT NOT NULL REFERENCES users(id),created_at TEXT NOT NULL)''',
        '''CREATE TABLE IF NOT EXISTS business_company_event_plans(
          id TEXT PRIMARY KEY,event_id TEXT NOT NULL REFERENCES business_company_event_observations(id),
          project_id TEXT NOT NULL REFERENCES projects(id),action_key TEXT NOT NULL,payload_json TEXT NOT NULL,
          sha256 TEXT NOT NULL,created_by TEXT NOT NULL REFERENCES users(id),created_at TEXT NOT NULL)''',
        '''CREATE TABLE IF NOT EXISTS business_company_event_runs(
          id TEXT PRIMARY KEY,payload_json TEXT NOT NULL,sha256 TEXT NOT NULL,
          created_by TEXT NOT NULL REFERENCES users(id),created_at TEXT NOT NULL)''',
        '''CREATE TABLE IF NOT EXISTS business_company_event_run_results(
          run_id TEXT PRIMARY KEY REFERENCES business_company_event_runs(id),
          payload_json TEXT NOT NULL,sha256 TEXT NOT NULL,created_at TEXT NOT NULL)''',
        '''CREATE TABLE IF NOT EXISTS business_company_event_decisions(
          plan_id TEXT PRIMARY KEY REFERENCES business_company_event_plans(id),
          decision TEXT NOT NULL CHECK(decision IN ('approved','rejected')),plan_sha256 TEXT NOT NULL,
          reason TEXT NOT NULL,created_by TEXT NOT NULL REFERENCES users(id),created_at TEXT NOT NULL)''',
        '''CREATE TABLE IF NOT EXISTS business_company_event_executions(
          plan_id TEXT PRIMARY KEY REFERENCES business_company_event_plans(id),action_key TEXT NOT NULL UNIQUE,
          domain_request_id TEXT NOT NULL UNIQUE,created_by TEXT NOT NULL REFERENCES users(id),created_at TEXT NOT NULL)''',
        '''CREATE TABLE IF NOT EXISTS business_company_event_outcomes(
          plan_id TEXT PRIMARY KEY REFERENCES business_company_event_executions(plan_id),
          status TEXT NOT NULL CHECK(status IN ('succeeded','failed','unknown','blocked')),
          payload_json TEXT NOT NULL,sha256 TEXT NOT NULL,created_at TEXT NOT NULL)''',
        '''CREATE TABLE IF NOT EXISTS business_company_event_requests(
          user_id TEXT NOT NULL REFERENCES users(id),request_id TEXT NOT NULL,operation TEXT NOT NULL,
          request_json TEXT NOT NULL,request_hash TEXT NOT NULL,result_json TEXT NOT NULL,
          PRIMARY KEY(user_id,request_id))''',
        '''CREATE TABLE IF NOT EXISTS business_company_event_suspensions(
          plan_id TEXT PRIMARY KEY REFERENCES business_company_event_plans(id),reason TEXT NOT NULL,created_at TEXT NOT NULL)''',
        'CREATE INDEX IF NOT EXISTS business_company_event_project ON business_company_event_plans(project_id,created_at)',
    ]
    return result


def protected_tables(): return TABLES
def runtime_privileges(): return {table: ('SELECT', 'INSERT') for table in TABLES}


def guard_statements(dialect):
    if dialect == 'sqlite':
        result = []
        for table in TABLES:
            for action in ('UPDATE', 'DELETE'):
                result.append(f"CREATE TRIGGER IF NOT EXISTS {table}_{action.lower()}_guard BEFORE {action} ON {table} BEGIN SELECT RAISE(ABORT,'immutable company event evidence'); END")
            key = 'id=NEW.id'
            if table.endswith('_rules'): key += ' AND revision=NEW.revision'
            elif table.endswith(('_decisions','_outcomes','_suspensions')): key = 'plan_id=NEW.plan_id'
            elif table.endswith('_executions'): key = 'plan_id=NEW.plan_id OR action_key=NEW.action_key OR domain_request_id=NEW.domain_request_id'
            elif table.endswith('_run_results'): key = 'run_id=NEW.run_id'
            elif table.endswith('_requests'): key = 'user_id=NEW.user_id AND request_id=NEW.request_id'
            result.append(f"CREATE TRIGGER IF NOT EXISTS {table}_insert_guard BEFORE INSERT ON {table} WHEN EXISTS(SELECT 1 FROM {table} WHERE {key}) BEGIN SELECT RAISE(ABORT,'immutable company event evidence'); END")
        return result
    if dialect != 'postgresql': raise ValueError('Unsupported dialect')
    result = ["CREATE OR REPLACE FUNCTION business_company_event_immutable_guard() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'immutable company event evidence'; END; $$"]
    for table in TABLES:
        for action in ('UPDATE', 'DELETE'):
            name = table+'_'+action.lower()+'_guard'
            result.append(f"DO $$ BEGIN IF NOT EXISTS(SELECT 1 FROM pg_trigger WHERE tgname='{name}' AND tgrelid='{table}'::regclass) THEN CREATE TRIGGER {name} BEFORE {action} ON {table} FOR EACH ROW EXECUTE FUNCTION business_company_event_immutable_guard(); END IF; END $$")
    return result


class CompanyEvents:
    def __init__(self, office, *, clock=None, delivery_transport=None):
        self.office, self.db = office, office.db
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self.delivery_transport = delivery_transport

    def now(self): return self.clock().astimezone(timezone.utc).isoformat(timespec='seconds')
    def today(self): return self.clock().astimezone(ZoneInfo('Europe/Berlin')).date().isoformat()

    def _lock(self):
        if not isinstance(self.db, sqlite3.Connection):
            self.db.execute('SELECT pg_advisory_xact_lock(1883046121)')

    def _access(self, actor, project=None, manager=False):
        actor = require_permission(self.office, actor, 'assistant.use', project)
        if manager: actor = require_permission(self.office, actor, 'settings.manage')
        return actor

    def _gate(self):
        from business_schema import require_capability, require_financial_release
        require_capability(self.office, 'business_company_events')
        require_financial_release(self.office)

    def _identity(self):
        instance = self.db.execute('SELECT instance_id FROM business_instance_identity WHERE singleton=1').fetchone()
        if instance is None: raise Problem(409, 'Eindeutige Unternehmensbindung dieser Installation fehlt.')
        return dict(instance_id=instance['instance_id'])

    def _value(self, row):
        value = json.loads(row['payload_json'])
        if not isinstance(value, dict) or sha(value) != row['sha256']:
            raise Problem(409, 'Ereignisnachweis besteht die Integritätsprüfung nicht.')
        return value

    def _checked(self):
        try: validate_integrity(self.office)
        except ValueError:
            raise Problem(409,'Die unveränderliche Ereignishistorie und ihre Originalannahmen müssen geprüft werden.') from None

    def _row(self, kind, object_id):
        identifier(object_id)
        row = self.db.execute('SELECT * FROM business_company_event_'+kind+' WHERE id=?', (object_id,)).fetchone()
        if row is None: raise Problem(404, 'Ereignisvorgang nicht verfügbar.')
        return row

    def _receipt(self, actor, operation, data):
        self._checked()
        identifier(data['request_id'], 'Vorgangs-ID')
        digest = sha([operation, data])
        row = self.db.execute('SELECT * FROM business_company_event_requests WHERE user_id=? AND request_id=?', (actor['id'], data['request_id'])).fetchone()
        if row:
            if row['operation'] != operation or row['request_hash'] != digest:
                raise Problem(409, 'Vorgangs-ID wurde bereits anders verwendet.')
            return digest, json.loads(row['result_json'])
        return digest, None

    def _remember(self, actor, operation, data, digest, result):
        self.db.execute('INSERT INTO business_company_event_requests VALUES(?,?,?,?,?,?)',
            (actor['id'], data['request_id'], operation, canonical(data), digest, canonical(result)))
        self.office.audit(actor, 'company_events.'+operation.split(':')[0], str(result))

    def _rules(self):
        rows = self.db.execute('SELECT r.* FROM business_company_event_rules r WHERE NOT EXISTS '
            '(SELECT 1 FROM business_company_event_rules n WHERE n.id=r.id AND n.revision>r.revision) ORDER BY id').fetchall()
        values = [self._value(row) for row in rows]
        if any(value['identity'] != self._identity() for value in values):
            raise Problem(409, 'Unternehmensbindung der Regeln stimmt nicht.')
        return values

    def status(self, actor):
        self._access(actor)
        return dict(schema_version=1, feature='company_event_rules', timezone='Europe/Berlin',
            triggers=list(TRIGGERS), condition_fields={key: {name: kind.__name__ for name, kind in fields.items()} for key, fields in FACTS.items()},
            actions=[dict(action=key, triggers=list(values), executable=key not in ('supplier.order','payment.execute')) for key, values in COMPATIBLE.items()],
            modes=['auto','approval','deny'], default_policy='deny', payroll_sources=False,
            external_model_calls=False, recurrence='once_per_occurrence_and_action', max_scan_limit=100)

    def rules(self, actor):
        with transaction(self.office):
            self._access(actor, manager=True)
            self._checked()
            return dict(schema_version=1, items=self._rules())

    def rule_history(self, actor, rule_id):
        identifier(rule_id)
        with transaction(self.office):
            self._access(actor, manager=True)
            self._checked()
            rows = self.db.execute('SELECT * FROM business_company_event_rules WHERE id=? ORDER BY revision', (rule_id,)).fetchall()
            if not rows: raise Problem(404, 'Ereignisregel nicht verfügbar.')
            return dict(schema_version=1, items=[self._value(row) for row in rows])

    def save_rule(self, actor, data):
        fields = ('request_id','id','revision','title','enabled','project_ids','trigger','action','mode','conditions','template','responsible_id','confirmation')
        shape(data, fields)
        identifier(data['id']); identifier(data['responsible_id'])
        if (type(data['revision']) is not int or data['revision'] < 0 or type(data['enabled']) is not bool or
                not isinstance(data['trigger'],str) or data['trigger'] not in TRIGGERS or data['mode'] not in ('auto','approval','deny') or data['confirmation'] is not True):
            raise Problem(400, 'Versionierte Ereignisregel ausdrücklich bestätigen.')
        projects = data['project_ids']
        if projects is not None:
            if not isinstance(projects, list) or not 1 <= len(projects) <= 100 or any(not isinstance(p,str) for p in projects) or projects != sorted(set(projects)):
                raise Problem(400, 'Sortierte eindeutige Projektmenge oder alle Projekte auswählen.')
            for project in projects: identifier(project)
        clean = template(data['trigger'], data['action'], data['template'])
        conditions(data['trigger'], data['conditions'])
        title = text(data['title'], 'Regelbezeichnung', 200, required=True)
        with transaction(self.office):
            self._lock(); fresh = self._access(actor, manager=True); self._gate()
            self._access(dict(id=data['responsible_id']))
            for project in projects or []:
                self._access(fresh, project)
                if data['enabled'] and data['mode'] != 'deny':
                    self._access(dict(id=data['responsible_id']), project)
                    action_access(self.office, dict(id=data['responsible_id']), project, data['action'])
            digest, previous = self._receipt(fresh, 'rule', data)
            if previous:
                row = self.db.execute('SELECT * FROM business_company_event_rules WHERE id=? AND revision=?', (previous['id'],previous['revision'])).fetchone()
                if row is None: raise Problem(409, 'Originalannahme der Regel fehlt.')
                return self._value(row)
            old = self.db.execute('SELECT * FROM business_company_event_rules WHERE id=? ORDER BY revision DESC LIMIT 1', (data['id'],)).fetchone()
            if data['revision'] != (old['revision'] if old else 0): raise Problem(409, 'Regelfassung wurde geändert.')
            value = {key: data[key] for key in fields if key not in ('request_id','confirmation')}
            value.update(schema_version=1, revision=data['revision']+1, title=title, template=clean,
                         identity=self._identity(), previous_hash=old['sha256'] if old else None,
                         created_by=fresh['id'], created_at=self.now())
            self.db.execute('INSERT INTO business_company_event_rules VALUES(?,?,?,?,?,?)',
                (value['id'],value['revision'],canonical(value),sha(value),fresh['id'],value['created_at']))
            self._remember(fresh,'rule',data,digest,dict(id=value['id'],revision=value['revision']))
            return value

    def _event(self, actor, event_id, *, current=False):
        row = self._row('observations', event_id)
        actor = self._access(actor, row['project_id'])
        value = self._value(row)
        if value['identity'] != self._identity(): raise Problem(409, 'Ereignis gehört nicht zu dieser Installation.')
        live = observe(self.office, actor, row['project_id'], value['trigger'], value['source']['descriptor']['id'], self.today(), self._identity())
        if current and live != value: raise Problem(409, 'Ereignisquelle oder Abfragedatum wurde geändert; neuen Lauf prüfen.')
        return row, value, live == value

    def _plan_access(self, actor, plan_id, *, current=False):
        row = self._row('plans', plan_id)
        fresh = self._access(actor, row['project_id'])
        value = self._value(row)
        event_row, event, same = self._event(fresh, row['event_id'], current=current)
        if value['event_sha256'] != event_row['sha256'] or value['project_id'] != event['project_id']:
            raise Problem(409, 'Plan und Ereignisquelle stimmen nicht überein.')
        for project_policy in value['policy']['project_policies']:
            for proof in project_policy['policy']['evidence']:
                require_permission(self.office,fresh,proof['permission'],row['project_id'])
        for source in value['context']['sources']:
            live = read_source(self.office, fresh, row['project_id'], source['descriptor'], self.today())
            if current and live != source: raise Problem(409, 'Aktionsquelle wurde geändert.')
        return fresh, row, value, event, same

    def _action_gate(self, actor, plan):
        self._gate()
        from business_organization import module_enabled
        module = 'finance' if plan['action'] in ('dunning.email','payment.execute') else 'material' if plan['action']=='supplier.order' else 'documents'
        if not module_enabled(self.office, module): raise Problem(423, 'Betroffener Fachbereich ist deaktiviert.')
        return action_access(self.office, actor, plan['project_id'], plan['action'])

    def _project_policies(self, actor, event, action, values):
        from business_assistant import Assistant, TRIGGERS as PROJECT_TRIGGERS
        if values is None: return []
        actor=self._access(actor,event['project_id'])
        api=Assistant(self.office,clock=self.clock);rules=api._rules(event['project_id'])
        result=[]
        for trigger in dict.fromkeys(['manual',event['trigger']]):
            if trigger not in PROJECT_TRIGGERS or not any(r['enabled'] and r['trigger']==trigger and r['action']==action for r in rules): continue
            original=api._evaluated_policy(actor,event['project_id'],trigger,action,values)
            result.append(dict(trigger=trigger,policy=project_policy_projection(original),
                               original_json=canonical(original),original_sha256=sha(original)))
        return result

    def _evaluated_policy(self, actor, event, action, values):
        return combine_policy(policy(self._rules(),event,action),self._project_policies(actor,event,action,values))

    def _policy_current(self, value, event):
        try:
            return self._evaluated_policy(dict(id=value['policy']['responsible_id']),event,value['action'],value['parameters'])==value['policy']
        except Problem as error:
            if error.status not in (401,403,404): raise
            return False

    def _authorize(self, actor, plan_id, *, transport=True):
        self._checked()
        fresh, row, value, event, _ = self._plan_access(actor, plan_id, current=True)
        self._action_gate(fresh, value)
        if self.db.execute('SELECT 1 FROM business_company_event_suspensions WHERE plan_id=?',(plan_id,)).fetchone():
            raise Problem(409, 'Offener Ereignisplan wurde bei Wiederherstellung gesperrt.')
        current = self._evaluated_policy(fresh, event, value['action'], value['parameters'])
        if current != value['policy']: raise Problem(409, 'Ereignisregeln wurden geändert; neuen Lauf prüfen.')
        if current['mode']=='deny': raise Problem(403, 'Unternehmensregel erlaubt diese Ereignisaktion nicht.')
        if current['responsible_id'] != fresh['id']: raise Problem(403, 'Nur die aktuell zuständige Person darf diese Aktion ausführen.')
        decision = self.db.execute('SELECT * FROM business_company_event_decisions WHERE plan_id=?',(plan_id,)).fetchone()
        if decision and decision['decision']=='rejected': raise Problem(403, 'Diese Ereignisaktion wurde abgelehnt.')
        if current['mode']=='approval':
            self._access(fresh, value['project_id']); require_permission(self.office,fresh,'assistant.approve',value['project_id'])
            if decision is None or decision['decision']!='approved' or decision['plan_sha256']!=row['sha256']:
                raise Problem(409, 'Freigabe des exakten Ereignisplans fehlt.')
        if value['preparation_error']: raise Problem(409, 'Aktionsquelle konnte nicht vollständig vorbereitet werden.')
        if value['action'] in ('supplier.order','payment.execute'): raise Problem(409, 'Kein ausführender Anbieteradapter eingerichtet.')
        if transport and value['action'] in EXTERNAL and self.delivery_transport is None:
            from business_delivery import configuration
            configuration()
        return fresh, row, value, event

    def scan(self, actor, data):
        shape(data, ('request_id','limit','after'))
        if (type(data['limit']) is not int or not 1 <= data['limit'] <= 100 or
                data['after'] is not None and (not isinstance(data['after'], str) or
                    not re.fullmatch(ID+r':[a-z]+\.[a-z]+:'+ID, data['after']))):
            raise Problem(400, 'Begrenzten Ereignislauf mit gültiger Fortsetzungsposition angeben.')
        with transaction(self.office):
            self._lock(); fresh = self._access(actor, manager=True); self._gate()
            digest, replay = self._receipt(fresh, 'scan', data)
            if replay:
                run_id = replay['run_id']
                run = self._value(self._row('runs', run_id))
            else:
                rules = self._rules()
                selected = candidates(self.office, fresh, sorted({r['trigger'] for r in rules if r['enabled']}))
                selected=[item for item in selected if any(r['enabled'] and r['trigger']==item[2] and
                    (r['project_ids'] is None or item[1] in r['project_ids']) for r in rules)]
                selected = [item for item in selected if data['after'] is None or item[0] > data['after']]
                readable,issues=[],[]
                for cursor, project, trigger, object_id in selected:
                    try:
                        event = observe(self.office, fresh, project, trigger, object_id, self.today(), self._identity())
                    except Problem as error:
                        if error.status in (403,404): continue
                        if error.status not in (409,413): raise
                        issues.append(dict(code='readable_source_unavailable',status_code=error.status))
                        continue
                    readable.append((cursor,project,trigger,object_id,event))
                    if len(readable)>data['limit']: break
                page,more=readable[:data['limit']],len(readable)>data['limit']
                items=[]
                for cursor,project,trigger,object_id,event in page:
                    if not event['active']: continue
                    event_id = sha(event)[:32]
                    old = self.db.execute('SELECT * FROM business_company_event_observations WHERE id=?',(event_id,)).fetchone()
                    if old is None:
                        self.db.execute('INSERT INTO business_company_event_observations VALUES(?,?,?,?,?,?,?)',
                            (event_id,project,event['occurrence_key'],canonical(event),sha(event),fresh['id'],self.now()))
                    elif self._value(old) != event: raise Problem(409, 'Ereigniskennung ist widersprüchlich.')
                    planned = []
                    for action in sorted({r['action'] for r in rules if r['trigger']==trigger}):
                        evaluated = policy(rules, event, action)
                        if evaluated['reason']=='no_matching_permission': continue
                        action_key = sha([event['occurrence_key'],action])
                        started = self.db.execute('SELECT plan_id FROM business_company_event_executions WHERE action_key=?',(action_key,)).fetchone()
                        if started:
                            planned.append(started['plan_id']); continue
                        context, values, preparation_error = dict(project_id=project,sources=[event['source']]), None, None
                        if evaluated['mode']!='deny':
                            try:
                                responsible = self._access(dict(id=evaluated['responsible_id']),project)
                                action_access(self.office,responsible,project,action)
                                # Responsibility is not permission to see the scanner's data.
                                observed = observe(self.office,responsible,project,trigger,object_id,self.today(),self._identity())
                                if observed != event: raise Problem(409,'Quellenstand wurde während des Laufs geändert.')
                                context, values = action_context(self.office,responsible,event,action,evaluated['template'])
                            except Problem as error:
                                if error.status not in (400,401,403,404,409,413,423): raise
                                preparation_error = dict(code='action_source_unavailable',status_code=error.status)
                        evaluated=combine_policy(evaluated,self._project_policies(dict(id=evaluated['responsible_id']),event,action,values))
                        value = dict(schema_version=1,event_id=event_id,event_sha256=sha(event),project_id=project,
                            action=action,action_key=action_key,policy=evaluated,context=context,
                            parameters=values,preparation_error=preparation_error)
                        plan_id = sha(value)[:32]
                        old = self.db.execute('SELECT * FROM business_company_event_plans WHERE id=?',(plan_id,)).fetchone()
                        # A restored pending plan cannot regain authority just by scanning
                        # exactly the same facts. Bind its replacement to the restore ID.
                        if old and self.db.execute('SELECT 1 FROM business_company_event_suspensions WHERE plan_id=?',(plan_id,)).fetchone():
                            restored = self.db.execute('SELECT restore_id FROM business_restore_state WHERE singleton=1').fetchone()
                            value['reprepared_after_restore'] = restored['restore_id']
                            plan_id = sha(value)[:32]
                            old = self.db.execute('SELECT * FROM business_company_event_plans WHERE id=?',(plan_id,)).fetchone()
                        if old is None:
                            self.db.execute('INSERT INTO business_company_event_plans VALUES(?,?,?,?,?,?,?,?)',
                                (plan_id,event_id,project,action_key,canonical(value),sha(value),fresh['id'],self.now()))
                        elif self._value(old)!=value: raise Problem(409,'Aktionskennung ist widersprüchlich.')
                        planned.append(plan_id)
                    items.append(dict(event_id=event_id,plan_ids=planned))
                run_id=sha(['company_event_scan_v1',self._identity(),fresh['id'],data['request_id']])[:32]
                run=dict(schema_version=1,identity=self._identity(),as_of=self.today(),timezone='Europe/Berlin',
                    items=items,issues=issues,scanned_count=len(page),complete=not more and not issues,
                    next_after=page[-1][0] if more else None,after=data['after'],limit=data['limit'])
                self.db.execute('INSERT INTO business_company_event_runs VALUES(?,?,?,?,?)',
                    (run_id,canonical(run),sha(run),fresh['id'],self.now()))
                self._remember(fresh,'scan',data,digest,dict(run_id=run_id))
        # Accepted scans can resume their recorded auto plans; no new source
        # selection or rule can change an already accepted scan request.
        result_row=self.db.execute('SELECT * FROM business_company_event_run_results WHERE run_id=?',(run_id,)).fetchone()
        if result_row is None:
            outcomes=[]
            for plan_id in dict.fromkeys(plan for item in run['items'] for plan in item['plan_ids']):
                with transaction(self.office):
                    self._access(fresh,manager=True);self._gate()
                value=self._value(self._row('plans',plan_id))
                status='denied' if value['policy']['mode']=='deny' else 'awaiting_approval' if value['policy']['mode']=='approval' else 'prepared'
                if value['policy']['mode']=='auto' and value['policy']['responsible_id']:
                    try:
                        result=self.execute(dict(id=value['policy']['responsible_id']),plan_id,
                            dict(request_id=uuid.uuid5(uuid.NAMESPACE_URL,'smartplan-company-event:'+plan_id).hex,
                                 plan_sha256=sha(value),confirmation=True))
                        status=result['status']
                    except Problem as error:
                        if error.status not in (400,401,403,404,409,413,423,502): raise
                        status='blocked'
                outcomes.append(dict(plan_id=plan_id,status=status))
            with transaction(self.office):
                self._lock()
                if not self.db.execute('SELECT 1 FROM business_company_event_run_results WHERE run_id=?',(run_id,)).fetchone():
                    value=dict(items=outcomes)
                    self.db.execute('INSERT INTO business_company_event_run_results VALUES(?,?,?,?)',
                        (run_id,canonical(value),sha(value),self.now()))
        return self.run(fresh,run_id)

    def event(self, actor, event_id):
        with transaction(self.office):
            row,value,current=self._event(actor,event_id)
            self._checked()
            return dict(value,id=event_id,sha256=row['sha256'],source_current=current,created_at=row['created_at'])

    def run(self, actor, run_id):
        with transaction(self.office):
            self._access(actor,manager=True)
            self._checked()
            row=self._row('runs',run_id); value=self._value(row)
            if value['identity']!=self._identity(): raise Problem(409,'Lauf gehört nicht zu dieser Installation.')
            for item in value['items']:
                self._event(actor,item['event_id'])
                for plan_id in item['plan_ids']: self._plan_access(actor,plan_id)
            result=self.db.execute('SELECT * FROM business_company_event_run_results WHERE run_id=?',(run_id,)).fetchone()
            return dict(value,id=run_id,sha256=row['sha256'],created_at=row['created_at'],
                        processing=self._value(result) if result else None)

    def plan(self, actor, plan_id):
        with transaction(self.office):
            fresh,row,value,event,same=self._plan_access(actor,plan_id)
            self._checked()
            decision=self.db.execute('SELECT * FROM business_company_event_decisions WHERE plan_id=?',(plan_id,)).fetchone()
            execution=self.db.execute('SELECT * FROM business_company_event_executions WHERE action_key=?',(row['action_key'],)).fetchone()
            outcome=self.db.execute('SELECT * FROM business_company_event_outcomes WHERE plan_id=?',(execution['plan_id'],)).fetchone() if execution else None
            status='denied' if value['policy']['mode']=='deny' else 'awaiting_approval' if value['policy']['mode']=='approval' and not decision else 'ready'
            if decision and decision['decision']=='rejected': status='rejected'
            if execution: status=outcome['status'] if outcome else 'unconfirmed'
            elif not same or not self._policy_current(value,event): status='stale'
            elif self.db.execute('SELECT 1 FROM business_company_event_suspensions WHERE plan_id=?',(plan_id,)).fetchone(): status='suspended_after_restore'
            can_execute,blocked=False,None
            if not execution:
                try:
                    self._authorize(fresh,plan_id);can_execute=True
                except Problem as error:
                    if error.status not in (400,401,403,404,409,413,423): raise
                    blocked=dict(status_code=error.status,message=error.message)
            return dict(value,id=plan_id,sha256=row['sha256'],created_at=row['created_at'],
                source_current=same,status=status,can_execute=can_execute,blocked=blocked,
                decision=dict(decision) if decision else None,execution=dict(execution) if execution else None,
                outcome=dict(status=outcome['status'],result=self._value(outcome),created_at=outcome['created_at']) if outcome else None)

    def listing(self, actor, kind, after=None, limit=50):
        if kind not in ('plans','runs','events'): raise Problem(400,'Unbekannte Ereignishistorie.')
        self._access(actor,manager=kind=='runs')
        if after is not None: identifier(after)
        if type(limit) is not int or not 1<=limit<=100: raise Problem(400,'Gültige Seitengröße angeben.')
        with transaction(self.office):
            table='observations' if kind=='events' else kind
            rows=self.db.execute('SELECT id FROM business_company_event_'+table+' WHERE id>? ORDER BY id', (after or '',)).fetchall()
            items=[];cursor=None
            for row in rows:
                cursor=row['id']
                try: items.append({'plans':self.plan,'runs':self.run,'events':self.event}[kind](actor,row['id']))
                except Problem as error:
                    if error.status not in (401,403,404): raise
                if len(items)==limit: break
            return dict(schema_version=1,items=items,next_after=cursor if cursor and cursor!=rows[-1]['id'] else None)

    def plans(self, actor, after=None, limit=50):
        return self.listing(actor,'plans',after,limit)

    def decide(self, actor, plan_id, approved, data):
        shape(data,('request_id','plan_sha256','reason','confirmation'))
        if data['confirmation'] is not True: raise Problem(400,'Konkrete Entscheidung ausdrücklich bestätigen.')
        reason=text(data['reason'],'Prüfvermerk',1000,required=True)
        with transaction(self.office):
            self._lock();fresh,row,value,event,_=self._plan_access(actor,plan_id)
            self._action_gate(fresh,value);require_permission(self.office,fresh,'assistant.approve',row['project_id'])
            operation=('approve:' if approved else 'reject:')+plan_id
            digest,replay=self._receipt(fresh,operation,data)
            if replay: return self.plan(fresh,plan_id)
            self._plan_access(fresh,plan_id,current=True)
            if (data['plan_sha256']!=row['sha256'] or value['policy']['mode']=='deny' or
                    value['policy']['responsible_id']!=fresh['id'] or self._evaluated_policy(dict(id=value['policy']['responsible_id']),event,value['action'],value['parameters'])!=value['policy']):
                raise Problem(409,'Entscheidung passt nicht zur aktuellen Quelle, Regel und Zuständigkeit.')
            if (self.db.execute('SELECT 1 FROM business_company_event_decisions WHERE plan_id=?',(plan_id,)).fetchone() or
                    self.db.execute('SELECT 1 FROM business_company_event_executions WHERE action_key=?',(row['action_key'],)).fetchone() or
                    self.db.execute('SELECT 1 FROM business_company_event_suspensions WHERE plan_id=?',(plan_id,)).fetchone()):
                raise Problem(409,'Ereignisaktion wurde bereits entschieden, gestartet oder bei Restore gesperrt.')
            self.db.execute('INSERT INTO business_company_event_decisions VALUES(?,?,?,?,?,?)',
                (plan_id,'approved' if approved else 'rejected',row['sha256'],reason,fresh['id'],self.now()))
            self._remember(fresh,operation,data,digest,dict(plan_id=plan_id))
            return self.plan(fresh,plan_id)

    def _outcome(self, plan_id, status, result):
        self.db.execute('INSERT INTO business_company_event_outcomes VALUES(?,?,?,?,?)',
            (plan_id,status,canonical(result),sha(result),self.now()))

    def execute(self, actor, plan_id, data):
        shape(data,('request_id','plan_sha256','confirmation'))
        if data['confirmation'] is not True: raise Problem(400,'Exakte Ereignisaktion ausdrücklich bestätigen.')
        with transaction(self.office):
            self._lock();fresh,row,value,event,_=self._plan_access(actor,plan_id)
            action_access(self.office,fresh,row['project_id'],value['action'])
            digest,replay=self._receipt(fresh,'execute:'+plan_id,data)
            if data['plan_sha256']!=row['sha256']: raise Problem(409,'Aktionshash stimmt nicht.')
            execution=self.db.execute('SELECT * FROM business_company_event_executions WHERE action_key=?',(row['action_key'],)).fetchone()
            if replay:
                if not execution or execution['plan_id']!=plan_id: raise Problem(409,'Ursprüngliche Ausführungsannahme fehlt.')
                return self.plan(fresh,plan_id)
            if execution: raise Problem(409,'Dieses Ereignis wurde bereits gestartet; nur den ursprünglichen Auftrag wiederholen oder seine Historie lesen.')
            fresh,row,value,event=self._authorize(fresh,plan_id)
            domain_request=uuid.uuid4().hex
            self.db.execute('INSERT INTO business_company_event_executions VALUES(?,?,?,?,?)',
                (plan_id,row['action_key'],domain_request,fresh['id'],self.now()))
            self._remember(fresh,'execute:'+plan_id,data,digest,dict(plan_id=plan_id))
            if value['action'] not in EXTERNAL:
                from business_assistant_sources import execute_internal
                result=execute_internal(self.office,fresh,value,value['context'],domain_request)
                self._outcome(plan_id,'succeeded',result)
                return self.plan(fresh,plan_id)
        api=self
        class GuardedTransport:
            def send(self, job):
                with transaction(api.office): api._authorize(fresh,plan_id)
                if api.delivery_transport is not None: transport=api.delivery_transport
                else:
                    from business_delivery import configured_transport
                    transport=configured_transport()
                return transport.send(job)
        try:
            from business_assistant_sources import execute_external
            result=execute_external(self.office,fresh,value,value['context'],domain_request,transport=GuardedTransport())
            status='succeeded' if result.get('status') in ('sent','accepted') else 'unknown' if result.get('status') in ('sending','unknown') else 'failed'
        except Problem as error:
            status,result='blocked',dict(code='business_gate_rejected',status_code=error.status,review_required=True)
        except Exception:
            status,result='unknown',dict(code='external_outcome_unconfirmed',review_required=True)
        with transaction(self.office):
            self._lock();self._outcome(plan_id,status,result)
        return self.plan(fresh,plan_id)


def require_assistant_event_policy(office, actor, plan, context):
    """An older assistant event entry must not bypass new company automation."""
    if plan['trigger'] not in TRIGGERS: return
    api=CompanyEvents(office)
    rules=[r for r in api._rules() if r['enabled'] and r['trigger']==plan['trigger'] and
           r['action']==plan['action'] and (r['project_ids'] is None or plan['project_id'] in r['project_ids'])]
    if not rules: return
    for source in context['sources']:
        if source['descriptor']['kind']!=TRIGGERS[plan['trigger']]: continue
        event=observe(office,actor,plan['project_id'],plan['trigger'],source['descriptor']['id'],api.today(),api._identity())
        result=policy(rules,event,plan['action'])
        if result['mode']=='deny' and (result['matched_rules'] or result['uncheckable_rules']):
            raise Problem(403,'Unternehmensweite Ereignisregel verbietet diese Assistentenaktion.')
    # A project-wide old fact aggregate has no unique event occurrence. It
    # cannot mint a second claim or establish that an omitted deny source is
    # irrelevant. The new scan binds that actual occurrence once.
    raise Problem(409,'Für diesen geregelten Fachauslöser den unternehmensweiten Ereignislauf verwenden.')


def require_send_policy(office, actor, project, action, target_id, request_id):
    """Called by both existing native mail gates; True means exact event claim."""
    api=CompanyEvents(office)
    execution=office.db.execute('SELECT * FROM business_company_event_executions WHERE domain_request_id=?',(request_id,)).fetchone()
    field='outbox_id' if action=='dunning.email' else 'document_id'
    if execution:
        value=api._value(api._row('plans',execution['plan_id']))
        if (execution['created_by']!=actor['id'] or value['project_id']!=project or
                value['action']!=action or value['parameters']!={field:target_id}):
            raise Problem(403,'Ereignisausführung gehört nicht zu Akteur, Projekt und Versandziel.')
        api._authorize(actor,execution['plan_id'],transport=False)
        return True
    rules=api._rules()
    trigger='dunning.ready' if action=='dunning.email' else 'document.finalized'
    if not any(r['enabled'] and r['action']==action and r['trigger']==trigger and
               (r['project_ids'] is None or project in r['project_ids']) for r in rules): return False
    event=observe(office,actor,project,trigger,target_id,api.today(),api._identity())
    result=policy(rules,event,action)
    if not result['matched_rules'] and not result['uncheckable_rules']: return False
    if result['mode']=='deny': raise Problem(403,'Unternehmensweite Ereignisregel verbietet den Versand.')
    raise Problem(409,'Dieser Versand benötigt den konkreten unternehmensweiten Ereignisplan.')


def sanitize_after_restore(db):
    tables={row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()} if isinstance(db,sqlite3.Connection) else {row[0] for row in db.execute("SELECT tablename FROM pg_tables WHERE schemaname='public'").fetchall()}
    if TABLES[0] not in tables: return
    from core import now_iso
    for row in db.execute('SELECT p.id FROM business_company_event_plans p WHERE NOT EXISTS '
        '(SELECT 1 FROM business_company_event_outcomes o WHERE o.plan_id=p.id)').fetchall():
        if not db.execute('SELECT 1 FROM business_company_event_suspensions WHERE plan_id=?',(row['id'],)).fetchone():
            db.execute('INSERT INTO business_company_event_suspensions VALUES(?,?,?)',
                (row['id'],'Offene Ereignisaktion nach Wiederherstellung erneut prüfen.',now_iso()))


def _validate_project_policies(office, project, action, values):
    from business_assistant import Assistant, FACT_TYPES
    from business_assistant_sources import _minor
    from datetime import date
    api=Assistant(office)
    for item in values:
        value=json.loads(item['original_json']);archived=[]
        if (canonical(value)!=item['original_json'] or sha(value)!=item['original_sha256'] or
                project_policy_projection(value)!=item['policy']): raise ValueError('Invalid exact legacy-policy projection')
        for reference in value['rule_versions']:
            row=office.db.execute('SELECT * FROM business_assistant_rules WHERE id=? AND revision=?',(reference['id'],reference['revision'])).fetchone()
            if not row or row['project_id']!=project or row['sha256']!=reference['sha256']: raise ValueError('Missing original project rule')
            archived.append(api._value(row))
        facts={key:None for key in FACT_TYPES}
        for proof in value['evidence']:
            source=proof['source']
            if proof['project_id']!=project or sha(source)!=proof['source_sha256']: raise ValueError('Invalid project policy evidence')
            if proof['kind']=='open_items':
                overdue=max((max(0,(date.fromisoformat(source['as_of'])-date.fromisoformat(v['due_date'])).days) for v in source['items'] if _minor(v['open'])>0),default=0)
                expected=dict(open_minor=sum(_minor(v['open']) for v in source['items']),payment_overdue_days=overdue,overdue_payment=overdue>0)
                permission='finance.read'
            elif proof['kind']=='tasks':
                overdue=max((max(0,(date.fromisoformat(source['as_of'])-date.fromisoformat(v['due_date'])).days) for v in source['items'] if v['due_date'] and v['status'] not in ('done','cancelled')),default=0)
                expected=dict(overdue_task=overdue>0,task_overdue_days=overdue);permission='documents.read'
            elif proof['kind']=='costs':
                from business_assistant_sources import cost_total_minor
                expected=dict(total_cost_minor=cost_total_minor(source),costs_complete=source['result']['complete_for_recorded_sources']);permission='finance.read'
                if source['project_id']!=project: raise ValueError('Foreign project cost source')
            else: raise ValueError('Unsupported project policy evidence')
            if expected!=proof['facts'] or proof['permission']!=permission: raise ValueError('Invalid project policy fact')
            facts.update(expected)
        if facts!=value['facts'] or api._policy(project,item['trigger'],action,facts,rule_values=archived,evidence=value['evidence'])!=value:
            raise ValueError('Invalid bound project policy')


def validate_integrity(office):
    api,db=CompanyEvents(office),office.db
    try:
        rules={}; latest={}
        for row in db.execute('SELECT * FROM business_company_event_rules ORDER BY id,revision').fetchall():
            value=api._value(row); identifier(row['id']); identifier(value['responsible_id'])
            previous=latest.get(row['id'])
            if (value['id']!=row['id'] or value['revision']!=row['revision'] or
                    value['created_by']!=row['created_by'] or value['created_at']!=row['created_at'] or
                    value['revision']!=(previous['revision']+1 if previous else 1) or
                    value['previous_hash']!=(sha(previous) if previous else None) or
                    value['identity']!=api._identity() or type(value['enabled']) is not bool or
                    value['mode'] not in ('auto','approval','deny')): raise ValueError('Invalid rule chain')
            conditions(value['trigger'],value['conditions'])
            if template(value['trigger'],value['action'],value['template'])!=value['template']: raise ValueError('Invalid rule template')
            if value['project_ids'] is not None:
                if value['project_ids']!=sorted(set(value['project_ids'])): raise ValueError('Invalid project scope')
                for project in value['project_ids']:
                    identifier(project)
                    if not db.execute('SELECT 1 FROM projects WHERE id=?',(project,)).fetchone(): raise ValueError('Missing project')
            rules[(row['id'],row['revision'])]=value;latest[row['id']]=value
        events={}
        for row in db.execute('SELECT * FROM business_company_event_observations').fetchall():
            value=api._value(row);source=value['source']
            active,facts,occurrence=event_values(value['trigger'],source)
            if (set(value)!={'schema_version','identity','project_id','trigger','as_of','source','facts','active','occurrence_key'} or
                    value['schema_version']!=1 or value['identity']!=api._identity() or
                    row['id']!=sha(value)[:32] or value['project_id']!=row['project_id'] or
                    source['sha256']!=sha(source['data']) or source['source_id']!=source['descriptor']['kind']+':'+source['descriptor']['id'] or
                    value['active']!=active or value['facts']!=facts or not active or
                    value['occurrence_key']!=sha([value['identity'],value['project_id'],value['trigger'],occurrence]) or
                    value['occurrence_key']!=row['occurrence_key']): raise ValueError('Invalid event evidence')
            from datetime import date
            date.fromisoformat(value['as_of'])
            if 'project_id' in source['data'] and source['data']['project_id']!=row['project_id']: raise ValueError('Cross-project event')
            if value['trigger'] in ('task.overdue','payment.overdue'):
                expected=max(0,(date.fromisoformat(value['as_of'])-date.fromisoformat(source['data']['due_date'])).days)
                if facts['overdue_days']!=expected: raise ValueError('Invalid overdue fact')
            if value['trigger']=='cost.threshold':
                from business_assistant_sources import cost_total_minor
                if str(cost_total_minor(source['data']))!=facts['total_cost_minor']: raise ValueError('Invalid actual cost total')
            events[row['id']]=(row,value)
        plans={}
        for row in db.execute('SELECT * FROM business_company_event_plans').fetchall():
            value=api._value(row);event_row,event=events[row['event_id']]
            _validate_project_policies(office,row['project_id'],value['action'],value['policy']['project_policies'])
            archived=[]
            for reference in value['policy']['rule_versions']:
                rule=rules[(reference['id'],reference['revision'])]
                if sha(rule)!=reference['sha256']: raise ValueError('Invalid rule proof')
                archived.append(rule)
            if (row['id']!=sha(value)[:32] or value['event_id']!=row['event_id'] or
                    value['event_sha256']!=event_row['sha256'] or row['project_id']!=event['project_id'] or
                    value['project_id']!=row['project_id'] or row['action_key']!=sha([event['occurrence_key'],value['action']]) or
                    value['action_key']!=row['action_key'] or combine_policy(policy(archived,event,value['action']),value['policy']['project_policies'])!=value['policy'] or
                    value['context']['project_id']!=row['project_id'] or value['context']['sources'][0]!=event['source']):
                raise ValueError('Invalid source or policy plan binding')
            for source in value['context']['sources']:
                if sha(source['data'])!=source['sha256']: raise ValueError('Invalid additional action source')
            if value['parameters'] is not None:
                from business_assistant_sources import parameters
                if (parameters(value['action'],value['parameters'],value['context'])!=value['parameters'] or
                        value['parameters']!=recorded_parameters(event,value['action'],value['policy']['template'])): raise ValueError('Invalid action arguments')
            elif value['policy']['mode']!='deny' and not value['preparation_error']: raise ValueError('Missing action arguments')
            plans[row['id']]=(row,value)
        for row in db.execute('SELECT * FROM business_company_event_decisions').fetchall():
            plan_row,plan=plans[row['plan_id']]
            if row['plan_sha256']!=plan_row['sha256'] or row['created_by']!=plan['policy']['responsible_id'] or plan['policy']['mode']=='deny':
                raise ValueError('Invalid concrete approval')
        executions={row['plan_id']:row for row in db.execute('SELECT * FROM business_company_event_executions').fetchall()}
        for row in executions.values():
            plan_row,plan=plans[row['plan_id']];identifier(row['domain_request_id'])
            if row['action_key']!=plan_row['action_key'] or row['created_by']!=plan['policy']['responsible_id'] or plan['policy']['mode']=='deny':
                raise ValueError('Invalid execution claim')
            if plan['policy']['mode']=='approval':
                decision=db.execute('SELECT * FROM business_company_event_decisions WHERE plan_id=?',(row['plan_id'],)).fetchone()
                if not decision or decision['decision']!='approved': raise ValueError('Unapproved execution')
        for row in db.execute('SELECT * FROM business_company_event_outcomes').fetchall():
            result=api._value(row);execution=executions[row['plan_id']];_,plan=plans[row['plan_id']]
            if row['status']=='succeeded':
                if plan['action'] in ('task.create','offer.draft'):
                    table,column=('workspace_requests','result') if plan['action']=='task.create' else ('business_document_requests','result_json')
                    receipt=db.execute('SELECT '+column+' FROM '+table+' WHERE user_id=? AND request_id=?',(execution['created_by'],execution['domain_request_id'])).fetchone()
                    if not receipt or json.loads(receipt[column])!=result: raise ValueError('Success without domain acceptance')
                elif plan['action'] not in ('document.email','dunning.email') or result.get('status') not in ('accepted','sent'):
                    raise ValueError('Unsupported external success')
        runs={};referenced_events=set();referenced_plans=set()
        for row in db.execute('SELECT * FROM business_company_event_runs').fetchall():
            value=api._value(row)
            if value['identity']!=api._identity(): raise ValueError('Foreign event run')
            for item in value['items']:
                _,event=events[item['event_id']]
                referenced_events.add(item['event_id'])
                for plan_id in item['plan_ids']:
                    referenced_plans.add(plan_id)
                    _,plan=plans[plan_id]
                    # A known execution can retain an earlier observation of
                    # the same occurrence, including the previous calendar day.
                    if plan['action_key']!=sha([event['occurrence_key'],plan['action']]): raise ValueError('Foreign run action')
            runs[row['id']]=(row,value)
        if set(events)!=referenced_events or set(plans)!=referenced_plans: raise ValueError('Missing original event run')
        for row in db.execute('SELECT * FROM business_company_event_run_results').fetchall():
            value=api._value(row);_,run=runs[row['run_id']]
            expected=list(dict.fromkeys(p for item in run['items'] for p in item['plan_ids']))
            if [item['plan_id'] for item in value['items']]!=expected: raise ValueError('Run result mismatch')
        receipts={}
        for row in db.execute('SELECT * FROM business_company_event_requests').fetchall():
            command=json.loads(row['request_json']);result=json.loads(row['result_json'])
            identifier(row['request_id'])
            if command['request_id']!=row['request_id'] or sha([row['operation'],command])!=row['request_hash']: raise ValueError('Invalid command receipt')
            kind=row['operation'].split(':')[0]
            if kind=='rule':
                target=rules[(result['id'],result['revision'])];key=(kind,result['id'],result['revision'])
                if (command['id']!=target['id'] or command['revision']+1!=target['revision'] or
                        any(command[k]!=target[k] for k in ('enabled','project_ids','trigger','action','mode','conditions','responsible_id')) or
                        template(command['trigger'],command['action'],command['template'])!=target['template'] or
                        text(command['title'],'Regelbezeichnung',200,required=True)!=target['title'] or command['confirmation'] is not True):
                    raise ValueError('Original rule command differs')
            elif kind=='scan':
                target,saved_run=runs[result['run_id']];key=(kind,result['run_id'])
                if (result['run_id']!=sha(['company_event_scan_v1',saved_run['identity'],row['user_id'],command['request_id']])[:32] or
                        saved_run['after']!=command['after'] or saved_run['limit']!=command['limit']): raise ValueError('Original scan command differs')
            elif kind=='execute':
                target=executions[result['plan_id']];key=(kind,result['plan_id'])
                if row['operation']!='execute:'+result['plan_id'] or command['plan_sha256']!=plans[result['plan_id']][0]['sha256'] or command['confirmation'] is not True:
                    raise ValueError('Original action command differs')
            elif kind in ('approve','reject'):
                target=db.execute('SELECT * FROM business_company_event_decisions WHERE plan_id=?',(result['plan_id'],)).fetchone();key=('decision',result['plan_id'])
                if (not target or row['operation']!=kind+':'+result['plan_id'] or command['plan_sha256']!=target['plan_sha256'] or
                        command['confirmation'] is not True or target['decision']!=('approved' if kind=='approve' else 'rejected') or
                        text(command['reason'],'Prüfvermerk',1000,required=True)!=target['reason']): raise ValueError('Original decision differs')
            else: raise ValueError('Unknown company event command')
            if not target or target['created_by']!=row['user_id'] or key in receipts: raise ValueError('Invalid original acceptance owner')
            receipts[key]=row
        for (rule_id,revision) in rules:
            if ('rule',rule_id,revision) not in receipts: raise ValueError('Missing original rule command')
        for run_id in runs:
            if ('scan',run_id) not in receipts: raise ValueError('Missing original scan command')
        for plan_id in executions:
            if ('execute',plan_id) not in receipts: raise ValueError('Missing original action command')
        for row in db.execute('SELECT plan_id FROM business_company_event_decisions').fetchall():
            if ('decision',row['plan_id']) not in receipts: raise ValueError('Missing original decision command')
        for row in db.execute('SELECT * FROM business_company_event_suspensions').fetchall():
            if row['plan_id'] not in plans: raise ValueError('Missing suspended plan')
    except (Problem,KeyError,TypeError,ValueError,json.JSONDecodeError) as error:
        raise ValueError('Invalid company event history') from error
    return True


def methods(path):
    if path in (BASE+'/status',BASE+'/plans',BASE+'/runs',BASE+'/events') or re.fullmatch(BASE+r'/(?:runs|events|plans)/'+ID,path) or re.fullmatch(BASE+r'/rules/'+ID+r'/history',path): return 'GET'
    if path==BASE+'/rules': return 'GET, POST'
    if path==BASE+'/scan' or re.fullmatch(BASE+r'/plans/'+ID+r'/(?:approve|reject|execute)',path): return 'POST'
    return None


def dispatch(office, actor, path, method, data):
    allowed=methods(path)
    if allowed is None: return None
    if method not in allowed.split(', '): raise Problem(405,'Methode nicht erlaubt.')
    if not isinstance(data,dict): raise Problem(400,'JSON-Objekt erwartet.')
    query=data.get('_query',{});body={key:value for key,value in data.items() if key!='_query'}
    api=CompanyEvents(office)
    if method=='GET':
        if body: raise Problem(400,'Keine zusätzlichen Abrufinhalte erlaubt.')
        if path in (BASE+'/plans',BASE+'/runs',BASE+'/events'):
            if not isinstance(query,dict) or not set(query)<={'after','limit'}: raise Problem(400,'Nur bekannte Seitenfilter angeben.')
            size=query.get('limit','50')
            if not isinstance(size,str) or not re.fullmatch(r'[1-9][0-9]{0,2}',size): raise Problem(400,'Gültige Seitengröße erforderlich.')
            result=api.listing(actor,path.split('/')[-1],query.get('after'),int(size))
        else:
            shape(query,())
            if path==BASE+'/status': result=api.status(actor)
            elif path==BASE+'/rules': result=api.rules(actor)
            elif path.endswith('/history'): result=api.rule_history(actor,path.split('/')[3])
            else:
                kind,object_id=path.split('/')[2:]
                result={'runs':api.run,'events':api.event,'plans':api.plan}[kind](actor,object_id)
    else:
        shape(query,())
        try:
            if path==BASE+'/rules': result=api.save_rule(actor,body)
            elif path==BASE+'/scan': result=api.scan(actor,body)
            else:
                plan_id,action=path.split('/')[3:]
                result=api.execute(actor,plan_id,body) if action=='execute' else api.decide(actor,plan_id,action=='approve',body)
        except Problem as error:
            if error.status==409 and isinstance(body.get('request_id'),str) and re.fullmatch(ID,body['request_id']):
                with transaction(office):
                    from business_foundation import _fresh
                    fresh=_fresh(office,actor)
                    if not office.db.execute('SELECT 1 FROM business_company_event_requests WHERE user_id=? AND request_id=?',(fresh['id'],body['request_id'])).fetchone():
                        raise Problem(409,error.message,request_resolution='not_accepted') from None
            raise
    if method=='POST':
        row=office.db.execute('SELECT * FROM business_company_event_requests WHERE user_id=? AND request_id=?',
                             (actor['id'],body['request_id'])).fetchone()
        if row is None or json.loads(row['request_json'])!=body:
            raise Problem(409,'Unveränderliche Annahme des Originalauftrags fehlt.')
        result=dict(result,acceptance=dict(request_id=row['request_id'],operation=row['operation'],request_hash=row['request_hash']))
    return result,200,'application/json'

"""Private, versioned employee travel evidence and actual reimbursements."""
import io
import json
import re
from datetime import datetime, timezone
from xml.sax.saxutils import escape

from core import Problem, canonical
from business_foundation import _fresh, permissions, require_permission
from business_operations import identifier, transaction, text
from business_personnel_workflow import PersonnelWorkflow, _sha, _shape
from payroll_travel_2026 import integer, day, zone, moment, time_options, calculate, _reference, RULE_VERSION
from payroll_travel_rates_2026 import catalog, rate
from workspace_api import BinaryAttachment

FEATURES=('travel_allowances',)
EVENT_TABLES=('business_travel_sites','business_travel_trips','business_travel_settlements','business_travel_payments')
TABLES=EVENT_TABLES+('business_travel_claims','business_travel_cash_events','business_travel_evidence','business_travel_requests')
KIND_TABLE={'site':EVENT_TABLES[0],'trip':EVENT_TABLES[1],'settlement':EVENT_TABLES[2],'payment':EVENT_TABLES[3]}
ID=r'[a-f0-9]{32}'


def schema_statements(binary_type='BYTEA'):
    if binary_type not in ('BYTEA','BLOB'):raise ValueError('Unsupported binary storage')
    result=[]
    for table in EVENT_TABLES:
        result.append(f'''CREATE TABLE IF NOT EXISTS {table}(
          id TEXT NOT NULL,revision INTEGER NOT NULL CHECK(revision>0),
          sequence INTEGER NOT NULL UNIQUE CHECK(sequence>0),
          employee_id TEXT NOT NULL REFERENCES business_employees(id),
          payload_json TEXT NOT NULL,content_hash TEXT NOT NULL,previous_hash TEXT,
          created_by TEXT NOT NULL REFERENCES users(id),created_at TEXT NOT NULL,
          pdf {binary_type},pdf_sha256 TEXT,PRIMARY KEY(id,revision))''')
        result.append(f'CREATE INDEX IF NOT EXISTS {table}_employee ON {table}(employee_id,id,revision)')
    result.extend([
      '''CREATE TABLE IF NOT EXISTS business_travel_claims(
        settlement_id TEXT NOT NULL,revision INTEGER NOT NULL,employee_id TEXT NOT NULL REFERENCES business_employees(id),
        claim_key TEXT NOT NULL,source_kind TEXT NOT NULL,source_id TEXT NOT NULL,source_revision INTEGER NOT NULL,
        amount_minor INTEGER NOT NULL CHECK(amount_minor>=0),content_hash TEXT NOT NULL,
        PRIMARY KEY(settlement_id,revision,claim_key),
        FOREIGN KEY(settlement_id,revision) REFERENCES business_travel_settlements(id,revision))''',
      '''CREATE TABLE IF NOT EXISTS business_travel_cash_events(
        id TEXT NOT NULL,revision INTEGER NOT NULL,instance_id TEXT NOT NULL,
        public_json TEXT NOT NULL,public_sha256 TEXT NOT NULL,private_sha256 TEXT NOT NULL,
        PRIMARY KEY(id,revision),FOREIGN KEY(id,revision) REFERENCES business_travel_payments(id,revision))''',
      '''CREATE TABLE IF NOT EXISTS business_travel_evidence(
        account_id TEXT NOT NULL REFERENCES business_accounting_accounts(id),evidence_key TEXT NOT NULL,
        payment_id TEXT NOT NULL,first_revision INTEGER NOT NULL,original_sha256 TEXT NOT NULL,
        PRIMARY KEY(account_id,evidence_key),
        FOREIGN KEY(payment_id,first_revision) REFERENCES business_travel_payments(id,revision))''',
      '''CREATE TABLE IF NOT EXISTS business_travel_requests(
        actor_id TEXT NOT NULL REFERENCES users(id),request_id TEXT NOT NULL,
        employee_id TEXT NOT NULL REFERENCES business_employees(id),operation TEXT NOT NULL,
        target_kind TEXT NOT NULL,target_id TEXT NOT NULL,revision INTEGER NOT NULL,
        request_hash TEXT NOT NULL,result_hash TEXT NOT NULL,created_at TEXT NOT NULL,
        PRIMARY KEY(actor_id,request_id))'''])
    return result


def protected_tables():return TABLES
def runtime_privileges():return {table:('SELECT','INSERT') for table in TABLES}


def guard_statements(dialect):
    result=[]
    if dialect=='postgresql':
        result.append("CREATE OR REPLACE FUNCTION business_travel_guard() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'immutable travel evidence'; END; $$")
    elif dialect!='sqlite':raise ValueError('Unknown travel dialect')
    for table in TABLES:
        for action in ('UPDATE','DELETE'):
            name=table+'_'+action.lower()+'_guard'
            if dialect=='sqlite':result.append(f"CREATE TRIGGER IF NOT EXISTS {name} BEFORE {action} ON {table} BEGIN SELECT RAISE(ABORT,'immutable travel evidence'); END")
            else:result.append(f"DO $$ BEGIN IF NOT EXISTS(SELECT 1 FROM pg_trigger WHERE tgname='{name}' AND tgrelid='{table}'::regclass) THEN CREATE TRIGGER {name} BEFORE {action} ON {table} FOR EACH ROW EXECUTE FUNCTION business_travel_guard(); END IF; END $$")
    if dialect=='sqlite':
        conditions=['(id=NEW.id AND revision=NEW.revision) OR sequence=NEW.sequence']*4+[
            'settlement_id=NEW.settlement_id AND revision=NEW.revision AND claim_key=NEW.claim_key',
            'id=NEW.id AND revision=NEW.revision','account_id=NEW.account_id AND evidence_key=NEW.evidence_key',
            'actor_id=NEW.actor_id AND request_id=NEW.request_id']
        for table,condition in zip(TABLES,conditions):
            result.append(f"CREATE TRIGGER IF NOT EXISTS {table}_insert_guard BEFORE INSERT ON {table} WHEN EXISTS(SELECT 1 FROM {table} WHERE {condition}) BEGIN SELECT RAISE(ABORT,'immutable travel evidence'); END")
    return result


def installed(office):
    from business_schema import _tables
    present=set(TABLES)&_tables(office)
    if present and present!=set(TABLES):raise Problem(409,'Reisemodul ist unvollständig installiert.')
    return bool(present)


def _ref(value):return {key:value[key] for key in ('id','revision','content_hash')}


def _pdf(record):
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import SimpleDocTemplate,Paragraph,Spacer
    stream=io.BytesIO();styles=getSampleStyleSheet();story=[]
    lines=['Reiseabrechnung – geprüfte Fassung', 'Abrechnung '+record['id']+' / '+str(record['revision']),
           'Mitarbeiter: '+record['sources']['employee']['name'], 'Regel: '+record['calculation']['rule_version']]
    for value in record['calculation']['days']:
        lines.append(value['date']+' · '+value['country']+' · Verpflegung '+str(value['meal_allowance_minor'])+' Cent · Übernachtung '+str(value['lodging_allowance_minor'])+' Cent')
        share=value.get('business_share')
        if share is not None and share['numerator']!=share['denominator']:
            lines.append('Beruflicher Programmanteil: '+str(share['numerator'])+'/'+str(share['denominator'])+
                ' · Pauschale vor Aufteilung '+str(value['unapportioned_base_minor'])+' Cent'+
                ' · berufliche Pauschale '+str(value['base_minor'])+' Cent'+
                ' · Mahlzeitenkürzung '+str(value['meal_reduction_minor'])+' Cent')
    totals=record['calculation']['totals'];lines.extend(['Steuerfreier Betrag: '+str(totals['tax_free_minor'])+' Cent',
        'Die Abrechnung ist keine Zahlungsbestätigung. Tatsächliche Zahlungen werden separat belegt.'])
    for line in lines:story.extend([Paragraph(escape(line),styles['Normal']),Spacer(1,7)])
    SimpleDocTemplate(stream,title='Reiseabrechnung',author='Smartplan',invariant=1).build(story)
    return stream.getvalue()


class TravelAllowances:
    def __init__(self,office,*,clock=None):
        self.office,self.db=office,office.db;self.clock=clock or (lambda:datetime.now(timezone.utc))
        self.hr=PersonnelWorkflow(office,clock=self.clock)
    def now(self):return self.clock().astimezone(timezone.utc).isoformat(timespec='seconds')
    def _employee(self,actor,employee_id,permission='personnel.read',own=True):
        return self.hr._employee(actor,employee_id,permission=permission,own=own)
    def _gate(self,actor):
        from business_schema import require_capability
        from business_organization import require_active
        require_capability(self.office,'business_travel_allowances')
        require_active(self.office,actor,'/personnel/travel','business_travel_allowances')
    def _rights(self,actor,employee):
        fresh=_fresh(self.office,actor);rights=permissions(self.office,fresh);own=employee['user_id']==fresh['id']
        return dict(read='personnel.read' in rights or own and 'time.own' in rights,
            write='personnel.write' in rights or own and 'time.own' in rights,
            approve='personnel.approve' in rights and not own,
            export='personnel.export' in rights or own and 'time.own' in rights,
            payments=all(p in rights for p in ('personnel.approve','finance.write','accounting.prepare','accounting.read','finance.read')))
    def _state(self,actor):
        from business_organization import module_enabled
        from business_schema import state
        active=module_enabled(self.office,'personnel');s=state(self.office)
        return dict(active=active,readonly=s['compatibility_mode']!='business' or bool(s['restore_pending']))
    def _files(self,actor,employee_id,ids,*,current=True):
        if not isinstance(ids,list) or not 1<=len(ids)<=100 or any(not isinstance(value,str) for value in ids) or len(set(ids))!=len(ids):
            raise Problem(400,'Ein bis hundert eindeutige Originale erforderlich.')
        output=[]
        for file_id in ids:
            identifier(file_id);row=self.hr._file(file_id,employee_id)
            if actor is not None:self.hr.file_content(actor,file_id)
            output.append(self.hr._file_view(row))
        return sorted(output,key=lambda x:x['id'])
    def _row(self,kind,object_id,revision=None):
        identifier(object_id);table=KIND_TABLE[kind];sql=f'SELECT * FROM {table} WHERE id=?';params=[object_id]
        if revision is not None:integer(revision,1);sql+=' AND revision=?';params.append(revision)
        row=self.db.execute(sql+' ORDER BY revision DESC LIMIT 1',tuple(params)).fetchone()
        if row is None:raise Problem(404,'Reisefassung nicht verfügbar.')
        return row
    def _view(self,row):
        value=json.loads(row['payload_json'])
        if (_sha(value)!=row['content_hash'] or value['id']!=row['id'] or value['revision']!=row['revision']
                or value['employee_id']!=row['employee_id'] or value['created_by']!=row['created_by']
                or value['created_at']!=row['created_at'] or value['previous_hash']!=row['previous_hash']):
            raise Problem(409,'Reisefassung besteht die Integritätsprüfung nicht.')
        result=dict(value,content_hash=row['content_hash'])
        if value['kind']=='settlement':
            pdf=bytes(row['pdf']);raw=canonical(result).encode();filename='reise-'+value['id']+'-v'+str(value['revision'])
            if _sha(pdf)!=row['pdf_sha256']:raise Problem(409,'Archiviertes Reise-PDF wurde verändert.')
            result['exports']=dict(pdf=dict(filename=filename+'.pdf',media_type='application/pdf',size=len(pdf),sha256=row['pdf_sha256']),
                json=dict(filename=filename+'.json',media_type='application/json',size=len(raw),sha256=_sha(raw)))
        return result
    def _get(self,kind,object_id,revision=None):return self._view(self._row(kind,object_id,revision))
    def _all(self,kind,employee_id):
        table=KIND_TABLE[kind]
        return [self._view(row) for row in self.db.execute(f'SELECT e.* FROM {table} e WHERE employee_id=? AND revision=(SELECT MAX(x.revision) FROM {table} x WHERE x.id=e.id) ORDER BY e.sequence',(employee_id,))]
    def _append(self,kind,actor,employee,object_id,data,previous=None,pdf=False):
        table=KIND_TABLE[kind];revision=previous['revision']+1 if previous else 1
        sequence=self.db.execute(f'SELECT COALESCE(MAX(sequence),0)+1 AS n FROM {table}').fetchone()['n']
        value=dict(schema_version=1,id=object_id,kind=kind,revision=revision,employee_id=employee['id'],
            created_by=actor['id'],created_at=self.now(),previous_hash=previous['content_hash'] if previous else None,**data)
        content_hash=_sha(value);content=_pdf(value) if pdf else None;pdf_sha=_sha(content) if content else None
        self.db.execute(f'INSERT INTO {table}(id,revision,sequence,employee_id,payload_json,content_hash,previous_hash,created_by,created_at,pdf,pdf_sha256) VALUES(?,?,?,?,?,?,?,?,?,?,?)',
            (object_id,revision,sequence,employee['id'],canonical(value),content_hash,value['previous_hash'],actor['id'],value['created_at'],content,pdf_sha))
        return self._get(kind,object_id,revision)
    def _basis(self,employee_id):
        employee=dict(self.db.execute('SELECT * FROM business_employees WHERE id=?',(employee_id,)).fetchone())
        value=dict(employee=employee,files=[dict(row) for row in self.db.execute('SELECT id,sha256,content_hash FROM business_personnel_files WHERE employee_id=? ORDER BY id',(employee_id,))],
            events={kind:[_ref(x) for x in self._all(kind,employee_id)] for kind in KIND_TABLE},
            expenses=[_ref(x) for x in self.hr._all('expense',employee_id)])
        return _sha(value)
    def sources(self,actor,employee_id):
        with transaction(self.office):
            fresh,employee=self._employee(actor,employee_id);rights=self._rights(fresh,employee)
            files=self.hr.files(fresh,dict(employee_id=employee_id))['items'];projects=[]
            for row in self.db.execute('SELECT id,name FROM projects ORDER BY name,id'):
                try:self.office.project(fresh,row['id']);projects.append(dict(row))
                except Problem as error:
                    if error.status not in (403,404):raise
            accounts=[];instance_id=None
            if rights['payments']:
                from business_accounting import Accounting
                from business_payroll_cash import _instance
                accounting=Accounting(self.office);accounting._access(fresh)
                accounts=[accounting._account(row['id']) for row in self.db.execute('SELECT id FROM business_accounting_accounts ORDER BY id')]
                instance_id=_instance(self.office)
            return dict(employee={k:employee[k] for k in ('id','user_id','name')},rights=rights,**self._state(fresh),
                files=files,projects=projects,sites=self._all('site',employee_id),expenses=self.hr._all('expense',employee_id),
                accounts=accounts,instance_id=instance_id,source_hash=self._basis(employee_id))
    def get(self,actor,kind,object_id,revision=None,history=False):
        with transaction(self.office):
            item=self._get(kind,object_id,revision);fresh,employee=self._employee(actor,item['employee_id'])
            self._read_sources(fresh,item)
            if history:
                items=[self._view(row) for row in self.db.execute(f'SELECT * FROM {KIND_TABLE[kind]} WHERE id=? ORDER BY revision',(object_id,))]
                for value in items:self._read_sources(fresh,value)
                return dict(items=items,id=object_id,employee_id=employee['id'])
            return dict(item=item,rights=self._rights(fresh,employee),source_hash=self._basis(employee['id']),**self._state(fresh))
    def listing(self,actor,kind,employee_id):
        with transaction(self.office):
            fresh,employee=self._employee(actor,employee_id);items=[]
            for value in self._all(kind,employee_id):
                try:self._read_sources(fresh,value);items.append(value)
                except Problem as error:
                    if error.status not in (403,404):raise
            return dict(items=items,employee_id=employee_id,rights=self._rights(fresh,employee),**self._state(fresh))
    def _read_sources(self,actor,item):
        for file in item.get('sources',{}).get('files',[]):
            row=self.hr._file(file['id'],item['employee_id'])
            if row['sha256']!=file['sha256']:raise Problem(409,'Reiseoriginal ist verändert.')
            if actor is not None:self.hr.file_content(actor,file['id'])
        project=item.get('details',{}).get('project_id')
        if project is not None and actor is not None:self.office.project(actor,project)
        for trip in item.get('sources',{}).get('trips',[]):self._read_sources(actor,trip)
        for trip in item.get('sources',{}).get('history_trips',[]):self._read_sources(actor,trip)
        for site in item.get('sources',{}).get('sites',[]):self._read_sources(actor,site)
        for expense in item.get('sources',{}).get('expenses',[]):
            for position in expense['items']:
                if position.get('project_id') is not None and actor is not None:self.office.project(actor,position['project_id'])
        settlement=item.get('sources',{}).get('settlement')
        if settlement is not None:self._read_sources(actor,settlement)
    def _receipt(self,row,actor=None):
        item=self._get(row['target_kind'],row['target_id'],row['revision'])
        if item['employee_id']!=row['employee_id'] or item['created_by']!=row['actor_id'] or item['command_hash']!=row['request_hash'] or _sha(item)!=row['result_hash']:
            raise Problem(409,'Reisequittung besteht die Fachprüfung nicht.')
        expected='trip.'+({'draft':'save','submitted':'submit','rejected':'reject'}[item['status']]) if item['kind']=='trip' else {'site':'site.save','settlement':'settlement.approve','payment':'payment.record'}[item['kind']]
        if row['operation']!=expected:raise Problem(409,'Reisequittung bindet eine fremde Fachoperation.')
        self._read_sources(actor,item);validate_record(self,item)
        return dict(request_id=row['request_id'],actor_id=row['actor_id'],employee_id=row['employee_id'],operation=row['operation'],
            target_kind=row['target_kind'],target_id=row['target_id'],revision=row['revision'],request_hash=row['request_hash'],
            result_hash=row['result_hash'],confirmed=True,result=item)
    def status(self,actor,request_id):
        identifier(request_id)
        with transaction(self.office):
            fresh=_fresh(self.office,actor);row=self.db.execute('SELECT * FROM business_travel_requests WHERE actor_id=? AND request_id=?',(fresh['id'],request_id)).fetchone()
            if row is None:raise Problem(404,'Keine angenommene Reisequittung verfügbar.')
            self._employee(fresh,row['employee_id']);return self._receipt(row,fresh)
    def _command(self,actor,kind,operation,data,callback,*,permission='personnel.write',own=True,original_body=None):
        identifier(data.get('request_id'));identifier(data.get('id'));identifier(data.get('employee_id'))
        fingerprint=_sha([operation,kind,data['id'],original_body if original_body is not None else data])
        with transaction(self.office):
            fresh,employee=self._employee(actor,data['employee_id'],permission=permission,own=own)
            previous=self.db.execute('SELECT * FROM business_travel_requests WHERE actor_id=? AND request_id=?',(fresh['id'],data['request_id'])).fetchone()
            if previous:
                if previous['request_hash']!=fingerprint:raise Problem(409,'Vorgangs-ID wurde mit anderem Inhalt verwendet.')
                return self._receipt(previous,fresh)
            self._gate(fresh)
            try:item=callback(fresh,employee,fingerprint)
            except Problem as error:
                if error.status==409:error.request_resolution='not_accepted'
                raise
            self.db.execute('INSERT INTO business_travel_requests(actor_id,request_id,employee_id,operation,target_kind,target_id,revision,request_hash,result_hash,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)',
                (fresh['id'],data['request_id'],employee['id'],operation,kind,item['id'],item['revision'],fingerprint,_sha(item),self.now()))
            row=self.db.execute('SELECT * FROM business_travel_requests WHERE actor_id=? AND request_id=?',(fresh['id'],data['request_id'])).fetchone()
            return self._receipt(row,fresh)
    def _previous(self,kind,data):
        try:old=self._get(kind,data['id'])
        except Problem as error:
            if error.status!=404:raise
            old=None
        if old and old['employee_id']!=data['employee_id']:raise Problem(404,'Reiseobjekt nicht verfügbar.')
        if integer(data['revision'])!=(old['revision'] if old else 0):raise Problem(409,'Reiseobjekt wurde geändert; aktuelle Fassung laden.')
        return old
    def _site_details(self,actor,employee,d):
        fields=('name','kind','address','rate_id','timezone','effective_from','effective_to','assignment_basis','regular_days_per_week','history_complete_from','prior_visit_dates','source_file_ids')
        _shape(d,fields+('frequency_periods',),fields)
        if d['kind'] not in catalog()['site_kinds']:raise Problem(400,'Bekannte Stättenart auswählen.')
        for k in ('name','address','assignment_basis'):text(d[k],k,1000,required=True)
        rate(d['rate_id']);zone(d['timezone']);start=day(d['effective_from']);complete=day(d['history_complete_from']);integer(d['regular_days_per_week'],0,7)
        if d['effective_to'] is not None and day(d['effective_to'])<start:raise Problem(400,'Stättenende liegt vor dem Beginn.')
        if complete>start:raise Problem(400,'Vollständige Vorgeschichte muss den Zuordnungsbeginn umfassen.')
        if not isinstance(d['prior_visit_dates'],list) or len(d['prior_visit_dates'])>2000 or any(not isinstance(value,str) for value in d['prior_visit_dates']) or d['prior_visit_dates']!=sorted(set(d['prior_visit_dates'])):
            raise Problem(400,'Geordnete eindeutige Besuchstage erforderlich.')
        for value in d['prior_visit_dates']:
            if day(value)<complete or value>self.now()[:10]:raise Problem(400,'Besuchstag liegt außerhalb der belegten Vorgeschichte.')
        files=self._files(actor,employee['id'],d['source_file_ids'])
        periods=d.get('frequency_periods',[])
        if not isinstance(periods,list) or len(periods)>100:raise Problem(400,'Begrenzte belegte Häufigkeitszeiträume erforderlich.')
        expected=d['effective_from']
        for period in periods:
            _shape(period,('from','to','days_per_week','source_file_ids'),('from','to','days_per_week','source_file_ids'))
            if period['from']!=expected:raise Problem(400,'Einsatzhäufigkeit lückenlos ab Stättenbeginn nachweisen.')
            start_period=day(period['from']);integer(period['days_per_week'],0,7)
            if period['to'] is not None and day(period['to'])<start_period:raise Problem(400,'Ungültiger Häufigkeitszeitraum.')
            expected=(day(period['to'])+__import__('datetime').timedelta(days=1)).isoformat() if period['to'] is not None else None
            files.extend(self._files(actor,employee['id'],period['source_file_ids']))
        if periods and periods[-1]['to']!=d['effective_to']:raise Problem(400,'Häufigkeitsnachweise müssen bis zum Stättenende reichen.')
        return dict(d),sorted({f['id']:f for f in files}.values(),key=lambda f:f['id'])
    def save_site(self,actor,data):
        fields=('request_id','employee_id','id','revision','status','details','correction_reason');_shape(data,fields,fields)
        def save(fresh,employee,fingerprint):
            old=self._previous('site',data)
            if data['status'] not in ('active','void'):raise Problem(400,'Stättenstatus aktiv oder ungültig angeben.')
            reason=text(data['correction_reason'],'Änderungsgrund',1000,required=bool(old))
            details,files=self._site_details(fresh,employee,data['details'])
            if old and details['regular_days_per_week']!=old['details']['regular_days_per_week'] and not details.get('frequency_periods'):
                raise Problem(400,'Geänderte Einsatzhäufigkeit mit vollständigen datierten Phasen belegen.')
            return self._append('site',fresh,employee,data['id'],dict(status=data['status'],details=details,sources=dict(files=files),
                correction_reason=reason,command_hash=fingerprint),old)
        return self._command(actor,'site','site.save',data,save)
    def _resolve(self,actor,kind,ref,employee_id,*,current=True):
        _reference(ref);record=self._get(kind,ref['id'],ref['revision'])
        if record['employee_id']!=employee_id:raise Problem(404,'Fremde Reisequelle nicht verfügbar.')
        if record['content_hash']!=ref['content_hash'] or current and self._get(kind,ref['id'])['revision']!=ref['revision']:
            raise Problem(409,'Genau passende aktuelle Reisequelle auswählen.')
        self._read_sources(actor,record)
        return record
    def _trip_details(self,actor,employee,d,*,current=True,rule_version=None):
        fields=('purpose','project_id','departed_at','returned_at','timezone','source_file_ids','home_site_ref','first_workplace_ref','segments','overnights','meals','expense_refs','requested_meal_minor','requested_lodging_minor','tax_choice','private_intervals')
        _shape(d,fields+('expense_allocations','transport_facts','mixed_assessment'),fields);text(d['purpose'],'Reisezweck',1000,required=True);zone(d['timezone'])
        moment(d['departed_at'],d['timezone']);moment(d['returned_at'],d['timezone'])
        for key in ('segments','overnights','meals','expense_refs','private_intervals'):
            if not isinstance(d[key],list) or len(d[key])>1000:raise Problem(400,'Begrenzte strukturierte Reiseliste erforderlich.')
        if d['project_id'] is not None:
            identifier(d['project_id'])
            if actor is not None:self.office.project(actor,d['project_id'])
        files=self._files(actor,employee['id'],d['source_file_ids']);sites=[];refs=[d['home_site_ref']]
        if d['first_workplace_ref'] is not None:refs.append(d['first_workplace_ref'])
        seen_ids=set()
        for segment in d['segments']:
            fields=('id','from','to','site_ref','activity','transport','necessary_stopover');_shape(segment,fields,fields)
            identifier(segment['id']);refs.append(segment['site_ref'])
            if segment['id'] in seen_ids:raise Problem(400,'Reiseabschnitts-ID doppelt.')
            seen_ids.add(segment['id'])
        for night in d['overnights']:
            fields=('id','date','site_ref','claim_method','provided_by','expense_ref');_shape(night,fields+('expense_receipt_file_id','accommodation_kind','other_lodging_started_or_finished'),fields)
            identifier(night['id']);refs.append(night['site_ref'])
        for meal in d['meals']:
            fields=('id','date','kind','provider','offered','is_meal','price_minor','employee_paid_minor','replacement_for','source_file_ids');_shape(meal,fields,fields)
            identifier(meal['id']);files.extend(self._files(actor,employee['id'],meal['source_file_ids']))
        for interval in d['private_intervals']:_shape(interval,('from','to'),('from','to'))
        if 'mixed_assessment' in d:
            from payroll_travel_mixed_2026 import resolve_mixed_program
            mixed=resolve_mixed_program(dict(id='0'*32,revision=1,content_hash='0'*64,details=d))
            if mixed is None:raise Problem(400,'Nicht benötigte Programmaufteilung weglassen.')
            mixed_ids=mixed['source_file_ids']
            for start in range(0,len(mixed_ids),100):files.extend(self._files(actor,employee['id'],mixed_ids[start:start+100]))
        transport=d.get('transport_facts',[])
        if not isinstance(transport,list) or len(transport)>100:raise Problem(400,'Begrenzte Beförderungsnachweise erforderlich.')
        for fact in transport:
            if not isinstance(fact,dict):raise Problem(400,'Strukturierter Beförderungsnachweis erforderlich.')
            files.extend(self._files(actor,employee['id'],fact.get('source_file_ids')))
            if fact.get('kind')=='flight':
                legs=fact.get('legs')
                if not isinstance(legs,list):raise Problem(400,'Strukturierte Flugabschnitte erforderlich.')
                for leg in legs:
                    if not isinstance(leg,dict):raise Problem(400,'Strukturierter Flugabschnitt erforderlich.')
                    refs.extend((leg.get('departure_site_ref'),leg.get('arrival_site_ref')))
            elif fact.get('kind')=='ship':refs.extend((fact.get('departure_site_ref'),fact.get('arrival_site_ref')))
        for ref in refs:
            value=self._resolve(actor,'site',ref,employee['id'],current=current)
            if value['status']!='active':raise Problem(409,'Aktiven belegten Stättennachweis auswählen.')
            if _ref(value) not in [_ref(s) for s in sites]:sites.append(value)
        expenses=[]
        for ref in d['expense_refs']:
            _reference(ref);row=self.db.execute('SELECT * FROM business_personnel_events WHERE id=? AND kind=\'expense\' AND revision=?',(ref['id'],ref['revision'])).fetchone()
            if row is None:raise Problem(404,'Auslagenfassung nicht verfügbar.')
            value=self.hr._event(row)
            if value['employee_id']!=employee['id'] or value['content_hash']!=ref['content_hash'] or current and self.hr._latest(ref['id'],'expense')['revision']!=ref['revision']:
                raise Problem(409,'Genau passende eigene Auslagenfassung erforderlich.')
            from payroll_travel_expenses_2026 import validate_expense_source
            validate_expense_source(self.hr,value)
            expenses.append(value)
            for item in value['items']:files.extend(self._files(actor,employee['id'],[item['receipt_file_id']]))
        sources=dict(files=sorted({f['id']:f for f in files}.values(),key=lambda x:x['id']),sites=sites,expenses=expenses)
        # Pure validation also produces precise blockers for still incomplete
        # facts; a draft may retain them, approval may not.
        dummy=dict(id='0'*32,revision=1,content_hash='0'*64,details=d,sources=sources)
        calculation=calculate([dummy],sites,rule_version=rule_version)
        return dict(d),sources,calculation
    def save_trip(self,actor,data):
        fields=('request_id','employee_id','id','revision','details','correction_reason');_shape(data,fields,fields)
        def save(fresh,employee,fingerprint):
            old=self._previous('trip',data)
            if old and old['status']=='submitted':raise Problem(409,'Eingereichte Reise zuerst durch die prüfende Person zurückweisen lassen.')
            reason=text(data['correction_reason'],'Änderungsgrund',1000,required=bool(old))
            details,sources,calculation=self._trip_details(fresh,employee,data['details'])
            return self._append('trip',fresh,employee,data['id'],dict(status='draft',details=details,sources=sources,
                rule_version=RULE_VERSION,correction_reason=reason,submitted_by=None,submitted_at=None,decision=None,command_hash=fingerprint),old)
        return self._command(actor,'trip','trip.save',data,save)
    def trip_action(self,actor,trip_id,action,data):
        identifier(trip_id);fields=('request_id','employee_id','revision','source_hash','confirmed')+(('reason',) if action=='reject' else ())
        _shape(data,fields,fields);original_body=data;data=dict(data,id=trip_id)
        def save(fresh,employee,fingerprint):
            old=self._previous('trip',data)
            if old is None:raise Problem(404,'Reise nicht verfügbar.')
            if data['confirmed'] is not True:raise Problem(400,'Reisevorgang ausdrücklich bestätigen.')
            if data['source_hash']!=self._basis(employee['id']):raise Problem(409,'Reisequellen wurden geändert; neu prüfen.')
            if action=='submit':
                if old['status'] not in ('draft','rejected'):raise Problem(409,'Nur eine offene Reise kann eingereicht werden.')
                self._trip_details(fresh,employee,old['details']);status='submitted';decision=None;submitted_by=fresh['id'];submitted_at=self.now()
            elif action=='reject':
                if old['status']!='submitted' or fresh['id'] in (employee['user_id'],old['submitted_by']):raise Problem(409,'Eingereichte Reise durch eine andere Person prüfen.')
                status='rejected';decision=dict(by=fresh['id'],reason=text(data['reason'],'Prüfgrund',1000,required=True));submitted_by=old['submitted_by'];submitted_at=old['submitted_at']
            else:raise Problem(404,'Unbekannte Reiseaktion.')
            return self._append('trip',fresh,employee,trip_id,dict(status=status,details=old['details'],sources=old['sources'],correction_reason=old['correction_reason'],
                rule_version=RULE_VERSION if action=='submit' else old.get('rule_version','de_travel_2026_v1'),submitted_by=submitted_by,submitted_at=submitted_at,decision=decision,command_hash=fingerprint),old)
        return self._command(actor,'trip','trip.'+action,data,save,permission='personnel.approve' if action=='reject' else 'personnel.write',own=action!='reject',original_body=original_body)
    def _preview(self,actor,data,*,historical=False):
        fields=('employee_id','trip_refs','period_from','period_to','settlement_unit','tax_choice','requested_meal_minor','requested_lodging_minor','correction_of','review_note')
        _shape(data,fields+('payroll_month',),fields);fresh,employee=self._employee(actor,data['employee_id']) if actor is not None else (None,dict(self.db.execute('SELECT * FROM business_employees WHERE id=?',(data['employee_id'],)).fetchone()))
        payroll_month=data.get('payroll_month')
        if payroll_month is not None and (not isinstance(payroll_month,str) or not re.fullmatch(r'2026-(0[1-9]|1[0-2])',payroll_month)):
            raise Problem(400,'Belegten vorgesehenen Lohn-Zuflussmonat 2026 auswählen.')
        if not isinstance(data['trip_refs'],list) or not 1<=len(data['trip_refs'])<=100:raise Problem(400,'Reisen ausdrücklich auswählen.')
        first,last=day(data['period_from']),day(data['period_to'])
        if last<first or last-first>__import__('datetime').timedelta(days=366):raise Problem(400,'Begrenzten Abrechnungszeitraum auswählen.')
        trips=[];sites=[];files=[];expenses=[]
        for ref in data['trip_refs']:
            trip=self._resolve(fresh,'trip',ref,employee['id'],current=not historical)
            if trip['status']!='submitted':raise Problem(409,'Nur eingereichte Reisen können abgerechnet werden.')
            if moment(trip['details']['departed_at']).astimezone(zone(trip['details']['timezone'])).date()<first or moment(trip['details']['returned_at']).astimezone(zone(trip['details']['timezone'])).date()>last:
                raise Problem(400,'Abrechnungszeitraum muss die ausgewählten Reisen umfassen.')
            if actor is not None:self._trip_details(fresh,employee,trip['details'],current=not historical)
            trips.append(trip);sites.extend(trip['sources']['sites']);files.extend(trip['sources']['files']);expenses.extend(trip['sources']['expenses'])
        sites=list({_reference(_ref(v)):v for v in sites}.values());files=list({f['id']:f for f in files}.values())
        history_trips=[t for t in self._all('trip',employee['id']) if t['status']=='submitted' and t['id'] not in {x['id'] for x in trips}]
        old=None
        if data['correction_of'] is not None:old=self._resolve(fresh,'settlement',data['correction_of'],employee['id'],current=not historical)
        from travel_allowance_cash import _paid
        after=self.db.execute('SELECT COALESCE(MAX(sequence),0) AS n FROM business_travel_payments').fetchone()['n']
        paid=_paid(self,old['id'],through_sequence=after) if old else 0
        calc=calculate(trips,sites,history_trips=history_trips,settlement_unit=data['settlement_unit'],tax_choice=data['tax_choice'],
            requested_meal_minor=data['requested_meal_minor'],requested_lodging_minor=data['requested_lodging_minor'],already_paid_minor=paid)
        if (calc['totals']['flat_taxable_minor'] or calc['totals']['individual_taxable_minor']) and payroll_month is None:
            calc['blockers'].append(dict(code='payroll_month_missing',text='Vorgesehenen Zuflussmonat der steuerpflichtigen Erstattung ausdrücklich auswählen.',source_ref=None));calc['can_approve']=False;calc['can_pay']=False
        from payroll_travel_expenses_2026 import ensure_expense_unreserved
        for expense in expenses:ensure_expense_unreserved(self.office,expense,own_settlement=old['id'] if old else None)
        claims={value['date'] for value in calc['days']}
        for existing in self._all('settlement',employee['id']):
            if old and existing['id']==old['id']:continue
            if claims & {v['date'] for v in existing['calculation']['days']}:
                calc['blockers'].append(dict(code='day_already_settled',text='Ein ausgewählter Mitarbeitertag ist bereits abgerechnet.',source_ref=_ref(existing)));calc['can_approve']=False;calc['can_pay']=False
        review=text(data['review_note'],'Prüfvermerk',2000,required=True)
        source_hash=self._basis(employee['id'])
        value=dict(employee_id=employee['id'],source_hash=source_hash,trip_refs=[_ref(t) for t in trips],site_refs=[_ref(s) for s in sites],
            expense_refs=[_ref(e) for e in expenses],period_from=data['period_from'],period_to=data['period_to'],settlement_unit=data['settlement_unit'],
            tax_choice=data['tax_choice'],requested_meal_minor=data['requested_meal_minor'],requested_lodging_minor=data['requested_lodging_minor'],
            correction_of=data['correction_of'],payroll_month=payroll_month,review_note=review,**calc)
        value['preview_hash']=_sha({k:v for k,v in value.items() if k not in ('can_approve','can_pay')})
        sources=dict(employee={k:employee[k] for k in ('id','user_id','name','revision')},trips=trips,history_trips=history_trips,sites=sites,files=files,expenses=expenses,after_payment_sequence=after)
        return value,sources,old
    def preview(self,actor,data):
        with transaction(self.office):return self._preview(actor,data)[0]
    def approve(self,actor,data):
        fields=('employee_id','trip_refs','period_from','period_to','settlement_unit','tax_choice','requested_meal_minor','requested_lodging_minor','correction_of','review_note','id','request_id','revision','source_hash','preview_hash','confirmed')
        _shape(data,fields+('payroll_month',),fields)
        def save(fresh,employee,fingerprint):
            old=self._previous('settlement',data);base={k:v for k,v in data.items() if k not in ('id','request_id','revision','source_hash','preview_hash','confirmed')}
            preview,sources,corrected=self._preview(fresh,base)
            if data['confirmed'] is not True:raise Problem(400,'Abrechnung ausdrücklich bestätigen.')
            if data['source_hash']!=preview['source_hash'] or data['preview_hash']!=preview['preview_hash']:raise Problem(409,'Abrechnungsquellen wurden geändert; neue Vorschau prüfen.')
            if not preview['can_approve']:raise Problem(409,'Offene Reisefakten vor Freigabe vervollständigen: '+', '.join(b['code'] for b in preview['blockers']))
            if fresh['id']==employee['user_id'] or any(t['submitted_by']==fresh['id'] for t in sources['trips']):raise Problem(409,'Eigene oder selbst eingereichte Reisen benötigen eine andere prüfende Person.')
            if (old is None)!=(corrected is None) or old is not None and old['id']!=corrected['id']:raise Problem(409,'Korrektur muss genau die bisherige Abrechnung fortschreiben.')
            record=self._append('settlement',fresh,employee,data['id'],dict(status='approved',details=base,sources=sources,
                calculation={k:preview[k] for k in ('rule_version','rule_hash','table_hash','days','totals','blockers','can_approve','can_pay','expense_items','payroll_required','transport_sources','ground_calendar_sources','mixed_program_sources') if k in preview},
                source_hash=preview['source_hash'],preview_hash=preview['preview_hash'],command_hash=fingerprint),old,pdf=True)
            for value in preview['days']:
                key='day:'+employee['id']+':'+value['date'];amount=value['meal_allowance_minor']+value['lodging_allowance_minor']
                claim=dict(settlement_id=record['id'],revision=record['revision'],employee_id=employee['id'],claim_key=key,
                    source_kind='employee_day',source_id=value['date'],source_revision=record['revision'],amount_minor=amount)
                self.db.execute('INSERT INTO business_travel_claims(settlement_id,revision,employee_id,claim_key,source_kind,source_id,source_revision,amount_minor,content_hash) VALUES(?,?,?,?,?,?,?,?,?)',tuple(claim.values())+(_sha(claim),))
            for value in preview.get('expense_items',[]):
                claim=dict(settlement_id=record['id'],revision=record['revision'],employee_id=employee['id'],claim_key='expense:'+value['receipt_sha256'],
                    source_kind='expense',source_id=value['expense_ref']['id'],source_revision=value['expense_ref']['revision'],amount_minor=value['business_minor'])
                self.db.execute('INSERT INTO business_travel_claims(settlement_id,revision,employee_id,claim_key,source_kind,source_id,source_revision,amount_minor,content_hash) VALUES(?,?,?,?,?,?,?,?,?)',tuple(claim.values())+(_sha(claim),))
            return record
        return self._command(actor,'settlement','settlement.approve',data,save,permission='personnel.approve',own=False)
    def export(self,actor,settlement_id,revision,format):
        if format not in ('pdf','json'):raise Problem(400,'PDF oder JSON auswählen.')
        with transaction(self.office):
            item=self._get('settlement',settlement_id,revision);fresh,employee=self._employee(actor,item['employee_id'])
            if not self._rights(fresh,employee)['export']:raise Problem(403,'Reiseexport ist nicht freigegeben.')
            self._read_sources(fresh,item);meta=item['exports'][format]
            content=bytes(self._row('settlement',settlement_id,item['revision'])['pdf']) if format=='pdf' else canonical({k:v for k,v in item.items() if k!='exports'}).encode()
            if _sha(content)!=meta['sha256']:raise Problem(409,'Reiseoriginal besteht die Hashprüfung nicht.')
            return BinaryAttachment(content,meta['filename']),meta['media_type']


def strict_request(path):
    return path.startswith('/personnel/travel/') or path=='/personnel/travel'


def validate_payment(api,record):
    """Validate an old actual payment against its historical source prefix."""
    from business_accounting import Accounting,_evidence
    from travel_allowance_cash import _paid,_legacy_payment,ensure_cash_available
    d=record['details'];fields=('action','settlement_ref','instance_id','account_id','account_revision','kind','paid_on','amount_minor','reference','reference_file_id','correction_reason')
    _shape(d,fields+('legacy_payment',),fields);identifier(d['instance_id']);identifier(d['account_id']);integer(d['account_revision'],1);integer(d['amount_minor'],1);day(d['paid_on'])
    if d['kind'] not in ('reimbursement','repayment') or d['action'] not in ('record','adopt_legacy','correct','void'):
        raise Problem(409,'Unbekannte archivierte Reisezahlung.')
    if (record['status']=='void')!=(d['action']=='void') or record['status'] not in ('active','void') or d['paid_on']>record['created_at'][:10]:
        raise Problem(409,'Unmöglicher historischer Reisezahlungsstatus.')
    row=api._row('payment',record['id'],record['revision']);after=integer(record['after_payment_sequence'])
    if after!=row['sequence']-1:raise Problem(409,'Reisezahlung besitzt eine fremde Journalgrenze.')
    if (record['revision']==1)!=(d['action'] in ('record','adopt_legacy')) or record['revision']>1 and not d['correction_reason'].strip():
        raise Problem(409,'Zahlungskorrektur besitzt keinen ursprünglichen Vorgang und Grund.')
    settlement=api._resolve(None,'settlement',d['settlement_ref'],record['employee_id'],current=False)
    if settlement!=record['sources']['settlement']:raise Problem(409,'Historische Reiseabrechnungsquelle wurde verändert.')
    validate_record(api,settlement)
    if not settlement['calculation']['can_approve'] or settlement['calculation']['blockers']:
        raise Problem(409,'Zahlung auf unvollständige Reiseabrechnung.')
    legacy_ref=d.get('legacy_payment');legacy=None
    if record['revision']==1 and (d['action']=='adopt_legacy')!=(legacy_ref is not None):raise Problem(409,'Historische Altzahlung besitzt keinen ausdrücklichen Übernahmemodus.')
    if legacy_ref is not None:
        legacy=_legacy_payment(api,settlement,legacy_ref,own_payment=record['id'],check_unique=True)
        if legacy!=record['sources'].get('legacy_payment'):raise Problem(409,'Historischer Altzahlungsnachweis wurde verändert.')
        original=legacy['payment']
        if any(d[k]!=original[v] for k,v in (('kind','kind'),('paid_on','paid_on'),('amount_minor','amount_minor'),('reference','reference'))):raise Problem(409,'Übernommene tatsächliche Altzahlung wurde verändert.')
    elif record['sources'].get('legacy_payment') is not None:raise Problem(409,'Fremder Altzahlungsnachweis in gewöhnlicher Reisezahlung.')
    if settlement['calculation'].get('payroll_required') and legacy is None:
        from travel_payroll_sources import travel_payroll_source
        from payroll_travel_link import validate_travel_processing
        months={v['date'][:7] for v in settlement['calculation']['days'] if v['letter_m'] or v['benefit_in_kind_minor']}
        if settlement['calculation']['totals']['flat_taxable_minor'] or settlement['calculation']['totals']['individual_taxable_minor']:months.add(settlement['details'].get('payroll_month'))
        bindings=record['sources'].get('payroll_processing',[])
        if len(bindings)!=len(months) or {p['month'] for p in bindings}!=months:raise Problem(409,'Historische Zahlung besitzt nicht alle zugehörigen Lohnverarbeitungsnachweise.')
        for binding in bindings:
            original=travel_payroll_source(api.office,None,d['settlement_ref'],binding['month'])
            if original['source_hash']!=binding['source_hash']:raise Problem(409,'Historischer Reise-Lohnquellenhash wurde verändert.')
            validate_travel_processing(api.office,binding['proof'],d['settlement_ref'],binding['month'],binding['source_hash'])
    account=Accounting(api.office)._account(d['account_id'],d['account_revision'])
    if not account['active'] or account!=record['sources']['account']:
        raise Problem(409,'Reisezahlung besitzt keinen unveränderten damaligen Kontonachweis.')
    files=api._files(None,record['employee_id'],[d['reference_file_id']])
    if files!=record['sources']['files'] or files[0]['purpose']!='personnel':raise Problem(409,'Reisezahlungsoriginal wurde verändert.')
    ensure_cash_available(api.office,account['id'],_evidence(d['reference'])[1],files[0]['sha256'],own_payment=record['id'])
    paid=_paid(api,settlement['id'],exclude_id=record['id'],through_sequence=after)
    capacity=settlement['calculation']['totals']['tax_free_minor']-settlement['calculation']['totals'].get('expense_already_paid_minor',0)
    if record['paid_before_minor']!=paid or record['available_before_minor']!=capacity-paid:
        raise Problem(409,'Historische Reisezahlungskapazität wurde verändert.')
    resulting=paid+(0 if record['status']=='void' else d['amount_minor'] if d['kind']=='reimbursement' else -d['amount_minor'])
    if legacy is None and (resulting<0 or (record['status']=='void' or d['kind']=='reimbursement') and resulting>capacity):
        raise Problem(409,'Historische Reisezahlung übersteigt die tatsächliche Kapazität.')
    if record['revision']>1:
        previous=api._get('payment',record['id'],record['revision']-1)
        if previous['details']['settlement_ref']['id']!=settlement['id']:raise Problem(409,'Zahlungskorrektur wechselt die ursprüngliche Abrechnung.')
        if previous['details'].get('legacy_payment')!=legacy_ref:raise Problem(409,'Zahlungskorrektur verändert ihre ursprüngliche Altzahlungsquelle.')
        if legacy_ref is not None and previous['details']['settlement_ref']!=d['settlement_ref']:raise Problem(409,'Altzahlungsnachweis wechselt seine ursprüngliche Abrechnungsfassung.')
        if d['action']=='void' and any(d[k]!=previous['details'][k] for k in ('settlement_ref','instance_id','account_id','account_revision','kind','paid_on','amount_minor','reference','reference_file_id')):
            raise Problem(409,'Aufhebung verändert den ursprünglichen tatsächlichen Zahlungsvorgang.')
    evidence=api.db.execute('SELECT * FROM business_travel_evidence WHERE account_id=? AND evidence_key=?',
                            (account['id'],_evidence(d['reference'])[1])).fetchone()
    if not evidence or evidence['payment_id']!=record['id'] or evidence['first_revision']>record['revision']:
        raise Problem(409,'Einmalige Zahlungsreferenzbindung fehlt.')
    first=api._get('payment',record['id'],evidence['first_revision'])
    if first['details']['account_id']!=evidence['account_id'] or _evidence(first['details']['reference'])[1]!=evidence['evidence_key'] or first['sources']['files'][0]['sha256']!=evidence['original_sha256']:
        raise Problem(409,'Zahlungsreferenz besitzt keinen unveränderten ursprünglichen Originalnachweis.')
    return True


def validate_record(api,value):
    """No current HR name/profile is substituted into an old accepted view."""
    identifier(value['id']);identifier(value['employee_id']);integer(value['revision'],1)
    kind=value['kind'];row=api._row(kind,value['id'],value['revision'])
    if api._view(row)!=value:raise Problem(409,'Archivierte Reiseansicht wurde verändert.')
    if not isinstance(value['command_hash'],str) or not re.fullmatch('[a-f0-9]{64}',value['command_hash']):
        raise Problem(409,'Reiseauftragshash fehlt.')
    previous=api._get(kind,value['id'],value['revision']-1) if value['revision']>1 else None
    if value['previous_hash']!=(previous['content_hash'] if previous else None):raise Problem(409,'Reisefassung besitzt einen falschen Vorgänger.')
    api._read_sources(None,value);employee=dict(id=value['employee_id'])
    if kind=='site':
        details,files=api._site_details(None,employee,value['details'])
        if details!=value['details'] or files!=value['sources']['files'] or value['status'] not in ('active','void'):
            raise Problem(409,'Historischer Stättennachweis wurde verändert.')
        if any(d>value['created_at'][:10] for d in details['prior_visit_dates']):raise Problem(409,'Stättenvorgeschichte enthielt zukünftige Besuche.')
    elif kind=='trip':
        details,sources,unused=api._trip_details(None,employee,value['details'],current=False,rule_version=value.get('rule_version','de_travel_2026_v1'))
        if details!=value['details'] or sources!=value['sources'] or value['status'] not in ('draft','submitted','rejected'):
            raise Problem(409,'Historische Reisequellen wurden verändert.')
        if value['status']=='draft':
            if value['submitted_by'] is not None or value['submitted_at'] is not None or value['decision'] is not None:
                raise Problem(409,'Reiseentwurf enthält eine fremde Einreichung.')
        elif value['status']=='submitted':
            if previous is None or previous['status'] not in ('draft','rejected') or value['submitted_by']!=value['created_by'] or value['submitted_at']!=value['created_at']:
                raise Problem(409,'Ungültige historische Reiseeinreichung.')
            if value['details']!=previous['details'] or value['sources']!=previous['sources'] or value['decision'] is not None:
                raise Problem(409,'Einreichung verändert Reisedetails ohne eigene Entwurfsfassung.')
        else:
            if previous is None or previous['status']!='submitted' or value['submitted_by']!=previous['submitted_by'] or value['decision']['by']!=value['created_by'] or value['created_by']==value['submitted_by']:
                raise Problem(409,'Ungültige historische Reiseprüfung.')
    elif kind=='settlement':
        d=value['details'];sources=value['sources'];employee_snapshot=sources['employee']
        _shape(employee_snapshot,('id','user_id','name','revision'),('id','user_id','name','revision'))
        original=[]
        for command in api.db.execute("SELECT result_json FROM business_planning_requests WHERE operation='employee'"):
            accepted=json.loads(command['result_json'])
            if accepted.get('id')==value['employee_id'] and accepted.get('revision')==employee_snapshot['revision']:original.append(accepted)
        current=api.db.execute('SELECT user_id FROM business_employees WHERE id=?',(value['employee_id'],)).fetchone()
        if len(original)!=1 or current is None or current['user_id']!=employee_snapshot['user_id'] or any(original[0].get(k)!=v for k,v in employee_snapshot.items()):
            raise Problem(409,'Historischer Mitarbeitersnapshot besitzt keinen passenden ursprünglichen Revisionsnachweis.')
        if employee_snapshot['id']!=value['employee_id'] or value['status']!='approved' or value['created_by']==employee_snapshot['user_id']:
            raise Problem(409,'Reiseabrechnung besitzt keine fremde Personenprüfung.')
        for trip in sources['trips']+sources['history_trips']:
            actual=api._resolve(None,'trip',_ref(trip),value['employee_id'],current=False)
            if actual!=trip or trip['status']!='submitted' or trip in sources['trips'] and trip['submitted_by']==value['created_by']:
                raise Problem(409,'Reiseabrechnung besitzt keine unabhängige eingereichte Quelle.')
            validate_record(api,trip)
        for site in sources['sites']:
            actual=api._resolve(None,'site',_ref(site),value['employee_id'],current=False)
            if actual!=site:raise Problem(409,'Historische Stättenfassung wurde verändert.')
            validate_record(api,site)
        from travel_allowance_cash import _paid
        after=integer(sources['after_payment_sequence'])
        if after>api.db.execute('SELECT COALESCE(MAX(sequence),0) AS n FROM business_travel_payments').fetchone()['n']:raise Problem(409,'Abrechnung besitzt eine fremde Zahlungsjournalgrenze.')
        paid=_paid(api,value['id'],through_sequence=after)
        result=calculate(sources['trips'],sources['sites'],history_trips=sources['history_trips'],settlement_unit=d['settlement_unit'],tax_choice=d['tax_choice'],
            requested_meal_minor=d['requested_meal_minor'],requested_lodging_minor=d['requested_lodging_minor'],already_paid_minor=paid,rule_version=value['calculation']['rule_version'])
        if result!=value['calculation'] or not result['can_approve']:
            raise Problem(409,'Historische Reiseberechnung ist nicht reproduzierbar.')
        if [_ref(t) for t in sources['trips']]!=d['trip_refs']:raise Problem(409,'Reiseabrechnung bindet andere Eingangsreisen.')
        first,last=day(d['period_from']),day(d['period_to'])
        if any(not first<=day(item['date'])<=last for item in result['days']):raise Problem(409,'Reiseabrechnung enthält fremde Tage.')
        if (previous is None)!=(d['correction_of'] is None) or previous and _ref(previous)!=d['correction_of']:
            raise Problem(409,'Reisekorrektur besitzt eine andere Vorgängerfassung.')
        expected=[]
        for item in result['days']:
            claim=dict(settlement_id=value['id'],revision=value['revision'],employee_id=value['employee_id'],
                claim_key='day:'+value['employee_id']+':'+item['date'],source_kind='employee_day',source_id=item['date'],
                source_revision=value['revision'],amount_minor=item['meal_allowance_minor']+item['lodging_allowance_minor'])
            expected.append(dict(claim,content_hash=_sha(claim)))
        for item in result.get('expense_items',[]):
            claim=dict(settlement_id=value['id'],revision=value['revision'],employee_id=value['employee_id'],claim_key='expense:'+item['receipt_sha256'],
                source_kind='expense',source_id=item['expense_ref']['id'],source_revision=item['expense_ref']['revision'],amount_minor=item['business_minor'])
            expected.append(dict(claim,content_hash=_sha(claim)))
        actual=[dict(row) for row in api.db.execute('SELECT * FROM business_travel_claims WHERE settlement_id=? AND revision=? ORDER BY claim_key',(value['id'],value['revision']))]
        if sorted(expected,key=lambda c:c['claim_key'])!=actual:raise Problem(409,'Historische Tagesbelegung stimmt nicht zur Reiseabrechnung.')
    elif kind=='payment':validate_payment(api,value)
    else:raise Problem(409,'Unbekannter historischer Reisevorgang.')
    return True


def validate_integrity(office):
    if not installed(office):return True
    api=TravelAllowances(office)
    try:
        for kind,table in KIND_TABLE.items():
            last_sequence=0
            for row in office.db.execute('SELECT * FROM '+table+' ORDER BY sequence'):
                if row['sequence']!=last_sequence+1:raise ValueError('Travel sequence gap')
                last_sequence=row['sequence'];validate_record(api,api._view(row))
        # Effective day claims must remain exclusive across different settlement
        # identities. Earlier revisions of the same identity stay historical.
        seen=set();expense_seen=set()
        for employee in office.db.execute('SELECT DISTINCT employee_id FROM business_travel_settlements'):
            for record in api._all('settlement',employee['employee_id']):
                for item in record['calculation']['days']:
                    key=(record['employee_id'],item['date'])
                    if key in seen:raise ValueError('Duplicate effective travel day')
                    seen.add(key)
                for item in record['calculation'].get('expense_items',[]):
                    if item['receipt_sha256'] in expense_seen:raise ValueError('Duplicate effective travel original')
                    expense_seen.add(item['receipt_sha256'])
        expected_claims=0
        for row in office.db.execute('SELECT * FROM business_travel_settlements'):
            record=api._view(row);expected_claims+=len(record['calculation']['days'])+len(record['calculation'].get('expense_items',[]))
        if expected_claims!=office.db.execute('SELECT COUNT(*) FROM business_travel_claims').fetchone()[0]:raise ValueError('Unexpected travel claim row')
        from business_accounting import _evidence
        from business_accounting_euer import ensure_cash_identity_available
        for evidence in office.db.execute('SELECT * FROM business_travel_evidence'):
            first=api._get('payment',evidence['payment_id'],evidence['first_revision'])
            if first['details']['account_id']!=evidence['account_id'] or _evidence(first['details']['reference'])[1]!=evidence['evidence_key'] or first['sources']['files'][0]['sha256']!=evidence['original_sha256']:
                raise ValueError('Changed travel original reservation')
            if office.db.execute('SELECT 1 FROM business_accounting_cash_events WHERE account_id=? AND evidence_key=?',(evidence['account_id'],evidence['evidence_key'])).fetchone():raise ValueError('Travel reference duplicated in legacy cash')
            if office.db.execute('SELECT 1 FROM business_accounting_receipt_bindings WHERE original_sha256=?',(evidence['original_sha256'],)).fetchone():raise ValueError('Travel original duplicated in legacy cash')
            ensure_cash_identity_available(office,evidence['account_id'],evidence['evidence_key'],evidence['original_sha256'],travel_payment_id=evidence['payment_id'])
        from travel_allowance_cash import public_source
        for row in office.db.execute('SELECT id,revision FROM business_travel_payments'):public_source(office,row['id'],row['revision'])
        payment_count=office.db.execute('SELECT COUNT(*) FROM business_travel_payments').fetchone()[0]
        if payment_count!=office.db.execute('SELECT COUNT(*) FROM business_travel_cash_events').fetchone()[0]:raise ValueError('Unexpected travel public cash row')
        for row in office.db.execute('SELECT * FROM business_travel_requests'):api._receipt(row)
        return True
    except (Problem,ValueError,TypeError,KeyError,IndexError,ImportError) as error:
        raise ValueError('Travel evidence integrity check failed: '+str(error)) from error


def methods(path):
    if path in ('/personnel/travel/catalog','/personnel/travel/sources','/personnel/travel/time-options'):
        return 'GET'
    if path in ('/personnel/travel/sites','/personnel/travel/trips','/personnel/travel/settlements','/personnel/travel/payments'):
        return 'GET, POST'
    if path=='/personnel/travel/settlements/preview':return 'POST'
    if re.fullmatch(r'/personnel/travel/(?:sites|trips|settlements|payments)/'+ID+r'(?:/history)?',path):return 'GET'
    if re.fullmatch(r'/personnel/travel/(?:requests|financial)/'+ID,path):return 'GET'
    if re.fullmatch(r'/personnel/travel/settlements/'+ID+r'/export',path):return 'GET'
    if re.fullmatch(r'/personnel/travel/trips/'+ID+r'/(?:submit|reject)',path):return 'POST'
    return None


def _query_revision(query):
    value=query.get('revision')
    if value is None:return None
    if not isinstance(value,str) or not re.fullmatch(r'[1-9][0-9]{0,8}',value):raise Problem(400,'Positive Revisionsnummer erforderlich.')
    return int(value)


def dispatch(office,actor,path,method,data):
    allowed=methods(path)
    if allowed is None:return None
    if method not in allowed.split(', '):raise Problem(405,'HTTP-Methode nicht erlaubt.')
    if not isinstance(data,dict):raise Problem(400,'JSON-Objekt erwartet.')
    api=TravelAllowances(office);tail=path.strip('/').split('/')[2:]
    query=data.get('_query',{});body={k:v for k,v in data.items() if k!='_query'}
    if method=='GET':
        if body:raise Problem(400,'Keine zusätzlichen Abrufinhalte erlaubt.')
        if tail in (['catalog'],['time-options']):
            fresh=_fresh(office,actor);rights=permissions(office,fresh)
            if not ({'personnel.read','time.own'}&set(rights)):raise Problem(403,'Personal- oder eigener Zeitzugriff erforderlich.')
        if tail==['catalog']:_shape(query,());result=catalog()
        elif tail==['time-options']:
            _shape(query,('local','timezone'),('local','timezone'));result=time_options(query['local'],query['timezone'])
        elif tail==['sources']:
            _shape(query,('employee_id',),('employee_id',));result=api.sources(actor,query['employee_id'])
        elif tail[0]=='requests':_shape(query,());result=api.status(actor,tail[1])
        elif tail[0]=='financial':
            from travel_allowance_cash import financial_access,public_source
            _shape(query,('revision',));financial_access(office,actor);result=public_source(office,tail[1],_query_revision(query))
        else:
            kind={'sites':'site','trips':'trip','settlements':'settlement','payments':'payment'}[tail[0]]
            if len(tail)==1:
                _shape(query,('employee_id',),('employee_id',));result=api.listing(actor,kind,query['employee_id'])
            elif len(tail)==2:
                _shape(query,('revision',));result=api.get(actor,kind,tail[1],_query_revision(query))
            elif tail[2]=='history':_shape(query,());result=api.get(actor,kind,tail[1],history=True)
            else:
                _shape(query,('revision','format'),('format',));result,mime=api.export(actor,tail[1],_query_revision(query),query['format'])
                return result,200,mime
    else:
        if query:raise Problem(400,'Keine zusätzlichen Schreibfilter erlaubt.')
        if tail==['sites']:result=api.save_site(actor,body)
        elif tail==['trips']:result=api.save_trip(actor,body)
        elif tail==['settlements','preview']:result=api.preview(actor,body)
        elif tail==['settlements']:result=api.approve(actor,body)
        elif tail==['payments']:
            from travel_allowance_cash import record_payment
            result=record_payment(api,actor,body)
        else:result=api.trip_action(actor,tail[1],tail[2],body)
    return result,200,'application/json'

"""Local asset and maintenance calendar with immutable visit provenance."""
import calendar
from datetime import date, timedelta
import hashlib
import json
import re
import uuid

from core import Problem, canonical
from business_operations import BusinessOperations, Domain, iso_date, request_schema, text


def schema_statements(binary_type='BYTEA'):
    if binary_type not in ('BLOB','BYTEA'): raise ValueError('Unsupported binary column type')
    return request_schema('business_maintenance_requests')+[
        '''CREATE TABLE IF NOT EXISTS business_assets(
        id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id), payload_json TEXT NOT NULL,
        revision INTEGER NOT NULL CHECK(revision>0), created_by TEXT NOT NULL REFERENCES users(id), created_at TEXT NOT NULL,
        updated_by TEXT NOT NULL REFERENCES users(id), updated_at TEXT NOT NULL)''',
        '''CREATE TABLE IF NOT EXISTS business_maintenance_contracts(
        id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id), asset_id TEXT NOT NULL REFERENCES business_assets(id),
        payload_json TEXT NOT NULL, anchor_date TEXT NOT NULL, interval_unit TEXT NOT NULL CHECK(interval_unit IN ('days','months')),
        interval_count INTEGER NOT NULL CHECK(interval_count>0), next_index INTEGER NOT NULL DEFAULT 0 CHECK(next_index>=0),
        active INTEGER NOT NULL CHECK(active IN (0,1)), revision INTEGER NOT NULL CHECK(revision>0),
        created_by TEXT NOT NULL REFERENCES users(id), created_at TEXT NOT NULL, updated_by TEXT NOT NULL REFERENCES users(id), updated_at TEXT NOT NULL)''',
        '''CREATE TABLE IF NOT EXISTS business_maintenance_visits(
        id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id), contract_id TEXT NOT NULL REFERENCES business_maintenance_contracts(id),
        asset_id TEXT NOT NULL REFERENCES business_assets(id), due_date TEXT NOT NULL, occurrence_index INTEGER NOT NULL,
        payload_json TEXT NOT NULL, status TEXT NOT NULL CHECK(status IN ('planned','completed')),
        report_id TEXT REFERENCES business_operation_entries(id), report_pdf_sha256 TEXT,
        revision INTEGER NOT NULL CHECK(revision>0), created_by TEXT NOT NULL REFERENCES users(id), created_at TEXT NOT NULL,
        updated_by TEXT NOT NULL REFERENCES users(id), updated_at TEXT NOT NULL, UNIQUE(contract_id,due_date), UNIQUE(contract_id,occurrence_index))''',
        '''CREATE TABLE IF NOT EXISTS business_maintenance_versions(
        kind TEXT NOT NULL, object_id TEXT NOT NULL, revision INTEGER NOT NULL, project_id TEXT NOT NULL REFERENCES projects(id),
        payload_json TEXT NOT NULL, PRIMARY KEY(kind,object_id,revision))''',
        'CREATE INDEX IF NOT EXISTS business_assets_project ON business_assets(project_id,created_at,id)',
        'CREATE INDEX IF NOT EXISTS business_visits_project ON business_maintenance_visits(project_id,due_date,id)',
    ]


def anniversary(anchor,unit,count,index):
    start=date.fromisoformat(anchor)
    try:
        if unit=='days': return (start+timedelta(days=count*index)).isoformat()
        month=start.year*12+start.month-1+count*index
        year,month0=divmod(month,12)
        if not 1900<=year<=2200: raise ValueError('Outside supported maintenance calendar')
        return date(year,month0+1,min(start.day,calendar.monthrange(year,month0+1)[1])).isoformat()
    except (OverflowError,ValueError):
        raise Problem(400,'Wartungsfälligkeit außerhalb des unterstützten Datumsbereichs')


class BusinessMaintenance(Domain):
    receipt_table='business_maintenance_requests'

    def _version(self,kind,value):
        self.office.db.execute('INSERT INTO business_maintenance_versions(kind,object_id,revision,project_id,payload_json) VALUES(?,?,?,?,?)',(kind,value['id'],value['revision'],value['project_id'],canonical(value)))

    def _asset(self,row): return self._record(row)

    def _contract(self,row):
        value=self._record(row)
        value.update(asset_id=row['asset_id'],anchor_date=row['anchor_date'],interval_unit=row['interval_unit'],interval_count=row['interval_count'],active=bool(row['active']),next_due_date=anniversary(row['anchor_date'],row['interval_unit'],row['interval_count'],row['next_index']))
        return value

    def _visit(self,row):
        value=self._record(row)
        value.update(contract_id=row['contract_id'],asset_id=row['asset_id'],due_date=row['due_date'],occurrence_index=row['occurrence_index'],status=row['status'],report_id=row['report_id'],report_pdf_sha256=row['report_pdf_sha256'])
        return value

    def save_asset(self,actor,project_id,data,asset_id=None):
        def save(fresh,body):
            if set(body)-{'revision','name','serial_number','asset_type','location','notes','media_ids','active'}: raise Problem(400,'Unbekannte Anlagenfelder')
            old=self.row('business_assets',project_id,asset_id) if asset_id else None
            if old: self.check_revision(body,old)
            value=json.loads(old['payload_json']) if old else {}
            value.update({k:v for k,v in body.items() if k!='revision'})
            value['name']=text(value.get('name'),'Anlage',300,required=True)
            for field in ('serial_number','asset_type','location','notes'): value[field]=text(value.get(field,''),field,5000 if field=='notes' else 1000)
            value['media_ids']=BusinessOperations(self.office)._media_refs(project_id,value.get('media_ids',[]),fresh)
            value['active']=value.get('active',True)
            if type(value['active']) is not bool: raise Problem(400,'Aktiv muss ein Wahrheitswert sein')
            identifier_,now=asset_id or uuid.uuid4().hex,self.now()
            if old:
                self.office.db.execute('UPDATE business_assets SET payload_json=?,revision=revision+1,updated_by=?,updated_at=? WHERE id=?',(canonical(value),fresh['id'],now,identifier_))
            else:
                self.office.db.execute('INSERT INTO business_assets(id,project_id,payload_json,revision,created_by,created_at,updated_by,updated_at) VALUES(?,?,?,1,?,?,?,?)',(identifier_,project_id,canonical(value),fresh['id'],now,fresh['id'],now))
            result=self._asset(self.row('business_assets',project_id,identifier_)); self._version('asset',result)
            return result
        return self.write(actor,'documents.write','business.asset.saved',project_id,data,asset_id,save)

    def list_assets(self,actor,project_id):
        with self.office.lock:
            self.access(actor,'documents.read',project_id)
            return [self._asset(row) for row in self.office.db.execute('SELECT * FROM business_assets WHERE project_id=? ORDER BY created_at,id',(project_id,)).fetchall()]

    def save_contract(self,actor,project_id,data,contract_id=None):
        def save(fresh,body):
            if set(body)-{'revision','asset_id','title','anchor_date','interval_unit','interval_count','active','notes','media_ids'}: raise Problem(400,'Unbekannte Wartungsvertragsfelder')
            old=self.row('business_maintenance_contracts',project_id,contract_id) if contract_id else None
            if old: self.check_revision(body,old)
            previous=self._contract(old) if old else {}
            value={key:body.get(key,previous.get(key)) for key in ('asset_id','title','anchor_date','interval_unit','interval_count')}
            self.row('business_assets',project_id,value['asset_id'])
            value['title']=text(value['title'],'Vertrag',300,required=True); value['anchor_date']=iso_date(value['anchor_date'])
            if value['interval_unit'] not in ('days','months') or type(value['interval_count']) is not int or not 1<=value['interval_count']<=(3660 if value['interval_unit']=='days' else 120): raise Problem(400,'Wartungsintervall ist ungültig')
            active=body.get('active',previous.get('active',True))
            if type(active) is not bool: raise Problem(400,'Aktiv muss ein Wahrheitswert sein')
            next_index=old['next_index'] if old else 0
            if old and any(value[key]!=previous[key] for key in ('asset_id','anchor_date','interval_unit','interval_count')):
                if self.office.db.execute('SELECT 1 FROM business_maintenance_visits WHERE contract_id=?',(contract_id,)).fetchone(): raise Problem(409,'Geplante Vertragsserie bleibt erhalten; neues Intervall benötigt einen neuen Vertrag')
                next_index=0
            metadata=dict(title=value['title'],notes=text(body.get('notes',previous.get('notes','')),'Notizen',10000),media_ids=BusinessOperations(self.office)._media_refs(project_id,body.get('media_ids',previous.get('media_ids',[])),fresh))
            identifier_,now=contract_id or uuid.uuid4().hex,self.now()
            if old:
                self.office.db.execute('UPDATE business_maintenance_contracts SET asset_id=?,payload_json=?,anchor_date=?,interval_unit=?,interval_count=?,next_index=?,active=?,revision=revision+1,updated_by=?,updated_at=? WHERE id=?',(value['asset_id'],canonical(metadata),value['anchor_date'],value['interval_unit'],value['interval_count'],next_index,int(active),fresh['id'],now,identifier_))
            else:
                self.office.db.execute('''INSERT INTO business_maintenance_contracts(id,project_id,asset_id,payload_json,anchor_date,interval_unit,interval_count,next_index,active,revision,created_by,created_at,updated_by,updated_at)
                    VALUES(?,?,?,?,?,?,?,0,?,1,?,?,?,?)''',(identifier_,project_id,value['asset_id'],canonical(metadata),value['anchor_date'],value['interval_unit'],value['interval_count'],int(active),fresh['id'],now,fresh['id'],now))
            result=self._contract(self.row('business_maintenance_contracts',project_id,identifier_)); self._version('contract',result)
            return result
        return self.write(actor,'projects.manage','business.maintenance.contract_saved',project_id,data,contract_id,save)

    def list_contracts(self,actor,project_id):
        with self.office.lock:
            self.access(actor,'documents.read',project_id)
            return [self._contract(row) for row in self.office.db.execute('SELECT * FROM business_maintenance_contracts WHERE project_id=? ORDER BY created_at,id',(project_id,)).fetchall()]

    def schedule_due(self,actor,data):
        project_id=data.get('project_id') if isinstance(data,dict) else None
        def schedule(fresh,body):
            if set(body)-{'project_id','as_of'}: raise Problem(400,'Unbekannte Planungsfelder')
            as_of=iso_date(body.get('as_of',self.now()[:10]))
            rows=self.office.db.execute('SELECT * FROM business_maintenance_contracts WHERE active=1 AND project_id=? ORDER BY id',(project_id,)).fetchall() if project_id else self.office.db.execute('SELECT * FROM business_maintenance_contracts WHERE active=1 ORDER BY project_id,id').fetchall()
            result=[]; more=False
            for row in rows:
                # Every contract is scoped afresh, even for a multi-project scheduling request.
                try: self.access(fresh,'projects.manage',row['project_id'])
                except Problem as error:
                    if project_id is None and error.status in (403,404): continue
                    raise
                contract=self._contract(row); asset=self._asset(self.row('business_assets',row['project_id'],row['asset_id']))
                if not asset['active']: continue
                index=row['next_index']
                while anniversary(row['anchor_date'],row['interval_unit'],row['interval_count'],index)<=as_of:
                    if len(result)>=100:
                        more=True; break
                    due=anniversary(row['anchor_date'],row['interval_unit'],row['interval_count'],index)
                    exists=self.office.db.execute('SELECT id FROM business_maintenance_visits WHERE contract_id=? AND occurrence_index=?',(row['id'],index)).fetchone()
                    if not exists:
                        identifier_,now=uuid.uuid4().hex,self.now()
                        payload=dict(contract_snapshot=contract,asset_snapshot=asset,completed_at=None,completed_by=None)
                        self.office.db.execute('''INSERT INTO business_maintenance_visits(id,project_id,contract_id,asset_id,due_date,occurrence_index,payload_json,status,report_id,report_pdf_sha256,revision,created_by,created_at,updated_by,updated_at)
                            VALUES(?,?,?,?,?,?,?,'planned',NULL,NULL,1,?,?,?,?)''',(identifier_,row['project_id'],row['id'],row['asset_id'],due,index,canonical(payload),fresh['id'],now,fresh['id'],now))
                        value=self._visit(self.row('business_maintenance_visits',row['project_id'],identifier_)); self._version('visit',value); result.append(value)
                    index+=1
                if index!=row['next_index']:
                    # Scheduling cursor is execution state, not a mutable contract revision.
                    self.office.db.execute('UPDATE business_maintenance_contracts SET next_index=? WHERE id=?',(index,row['id']))
                if more: break
            return dict(id=uuid.uuid4().hex,project_id=project_id,items=result,more_due=more,as_of=as_of,status='scheduled')
        result=self.write(actor,'projects.manage','business.maintenance.scheduled',project_id,data,None,schedule)
        with self.office.lock:
            for item in result['items']: self.access(actor,'projects.manage',item['project_id'])
        return result

    def history(self,actor,project_id,*,asset_id=None):
        with self.office.lock:
            self.access(actor,'documents.read',project_id)
            rows=self.office.db.execute('SELECT * FROM business_maintenance_visits WHERE project_id=? AND asset_id=? ORDER BY due_date,id',(project_id,asset_id)).fetchall() if asset_id else self.office.db.execute('SELECT * FROM business_maintenance_visits WHERE project_id=? ORDER BY due_date,id',(project_id,)).fetchall()
            return [self._visit(row) for row in rows]

    def complete_visit(self,actor,project_id,visit_id,data):
        def complete(fresh,body):
            if set(body)!={'revision','report_id'}: raise Problem(400,'Wartungsabschluss benötigt einen unterzeichneten Servicebericht')
            row=self.row('business_maintenance_visits',project_id,visit_id); self.check_revision(body,row)
            if row['status']!='planned': raise Problem(409,'Wartung bereits abgeschlossen')
            report=self.row('business_operation_entries',project_id,body['report_id'])
            payload=json.loads(report['payload_json'])
            if report['kind']!='service' or payload.get('status')!='signed' or not report['pdf']:
                raise Problem(409,'Unterzeichneter Servicebericht fehlt')
            pdf_hash=hashlib.sha256(bytes(report['pdf'])).hexdigest()
            if pdf_hash!=report['pdf_sha256']: raise Problem(500,'Servicebericht-Prüfsumme stimmt nicht')
            previous=self.office.db.execute('SELECT id FROM business_maintenance_visits WHERE report_id=?',(body['report_id'],)).fetchone()
            if previous: raise Problem(409,'Servicebericht wurde bereits einer Wartung zugeordnet')
            now=self.now(); value=json.loads(row['payload_json']); value.update(completed_at=now,completed_by=fresh['id'])
            self.office.db.execute("UPDATE business_maintenance_visits SET payload_json=?,status='completed',report_id=?,report_pdf_sha256=?,revision=revision+1,updated_by=?,updated_at=? WHERE id=?",(canonical(value),body['report_id'],pdf_hash,fresh['id'],now,visit_id))
            result=self._visit(self.row('business_maintenance_visits',project_id,visit_id)); self._version('visit',result)
            return result
        return self.write(actor,'documents.write','business.maintenance.completed',project_id,data,visit_id,complete)


def _validate_integrity(office):
    api=BusinessMaintenance(office); expected={}
    for table,kind,reader in [('business_assets','asset',api._asset),('business_maintenance_contracts','contract',api._contract),('business_maintenance_visits','visit',api._visit)]:
        for row in office.db.execute(f'SELECT * FROM {table}').fetchall(): expected[(kind,row['id'])]=reader(row)
    histories={}
    for row in office.db.execute('SELECT * FROM business_maintenance_versions ORDER BY kind,object_id,revision').fetchall():
        key=(row['kind'],row['object_id']); value=json.loads(row['payload_json']); history=histories.setdefault(key,[])
        if key not in expected or value.get('project_id')!=row['project_id'] or value.get('id')!=row['object_id'] or value.get('revision')!=len(history)+1: raise ValueError('Invalid maintenance version')
        history.append(value)
    for key,value in expected.items():
        history=histories.get(key,[])
        stored=dict(history[-1]) if history else {}; current=dict(value)
        if key[0]=='contract':
            stored.pop('next_due_date',None); current.pop('next_due_date',None)
        if len(history)!=value['revision'] or stored!=current: raise ValueError('Maintenance version mismatch')
    for row in office.db.execute('SELECT * FROM business_maintenance_visits').fetchall():
        value=json.loads(row['payload_json']); contract=value['contract_snapshot']; asset=value['asset_snapshot']
        if contract['id']!=row['contract_id'] or asset['id']!=row['asset_id'] or contract['project_id']!=row['project_id'] or asset['project_id']!=row['project_id'] or anniversary(contract['anchor_date'],contract['interval_unit'],contract['interval_count'],row['occurrence_index'])!=row['due_date']: raise ValueError('Invalid maintenance occurrence')
        if row['status']=='completed':
            report=office.db.execute('SELECT * FROM business_operation_entries WHERE id=?',(row['report_id'],)).fetchone()
            if not report or report['project_id']!=row['project_id'] or report['kind']!='service' or not report['pdf'] or report['pdf_sha256']!=row['report_pdf_sha256'] or hashlib.sha256(bytes(report['pdf'])).hexdigest()!=row['report_pdf_sha256'] or json.loads(report['payload_json']).get('status')!='signed': raise ValueError('Invalid maintenance service history')
        elif row['report_id'] or row['report_pdf_sha256']: raise ValueError('Planned maintenance has completed service')
    return True


def validate_integrity(office):
    try:
        return _validate_integrity(office)
    except (Problem,TypeError,KeyError,json.JSONDecodeError) as error:
        raise ValueError('Invalid maintenance data') from error


def methods(path):
    if path in ('/maintenance/due','/maintenance/history'): return 'GET'
    if path=='/maintenance/schedule' or re.fullmatch(r'/maintenance/visits/[a-f0-9]{32}/complete',path): return 'POST'
    if re.fullmatch(r'/(assets|maintenance/contracts)(?:/[a-f0-9]{32})?',path): return 'GET, POST'
    return None


def dispatch(office,actor,path,method,data):
    if methods(path) is None: return None
    api=BusinessMaintenance(office); query=data.get('_query',{}); body={k:v for k,v in data.items() if k!='_query'}
    def parameter(key):
        value=query.get(key); return value[0] if isinstance(value,list) and len(value)==1 else value
    project_id=parameter('project_id') if method=='GET' else body.get('project_id')
    object_match=re.fullmatch(r'/(assets|maintenance/contracts)/([a-f0-9]{32})',path)
    if not project_id and object_match:
        table='business_assets' if object_match[1]=='assets' else 'business_maintenance_contracts'
        row=office.db.execute(f'SELECT project_id FROM {table} WHERE id=?',(object_match[2],)).fetchone()
        if row: project_id=row['project_id']
    visit_match=re.fullmatch(r'/maintenance/visits/([a-f0-9]{32})/complete',path)
    if visit_match and not project_id:
        row=office.db.execute('SELECT project_id FROM business_maintenance_visits WHERE id=?',(visit_match[1],)).fetchone()
        if row: project_id=row['project_id']
    if path=='/maintenance/schedule' and method=='POST': return api.schedule_due(actor,body),200,'application/json'
    if not project_id: raise Problem(400,'project_id fehlt')
    payload={k:v for k,v in body.items() if k!='project_id'}
    if visit_match and method=='POST': return api.complete_visit(actor,project_id,visit_match[1],payload),200,'application/json'
    if path in ('/maintenance/history','/maintenance/due') and method=='GET':
        items=api.history(actor,project_id,asset_id=parameter('asset_id'))
        if path.endswith('/due'): items=[item for item in items if item['status']=='planned' and item['due_date']<=iso_date(parameter('as_of') or api.now()[:10])]
        return {'items':items},200,'application/json'
    is_asset=path.startswith('/assets'); object_id=object_match[2] if object_match else None
    if method=='POST':
        value=(api.save_asset if is_asset else api.save_contract)(actor,project_id,payload,object_id)
        return value,200 if object_id else 201,'application/json'
    if method=='GET':
        if object_id:
            api.access(actor,'documents.read',project_id)
            row=api.row('business_assets' if is_asset else 'business_maintenance_contracts',project_id,object_id)
            return (api._asset if is_asset else api._contract)(row),200,'application/json'
        return {'items':(api.list_assets if is_asset else api.list_contracts)(actor,project_id)},200,'application/json'
    raise Problem(405,'Methode nicht unterstützt')

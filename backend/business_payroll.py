"""Versioned private payroll profiles and reproducible 2026 calculation records.

Minijob, complete supported regular PAP and legacy partial SV records have
different explicit scopes. No statutory filing or bank IO.
"""
import hashlib
import io
import json
import re
import uuid
from decimal import Decimal, ROUND_HALF_UP, localcontext
from xml.sax.saxutils import escape

from core import Problem, canonical
from business_foundation import _fresh, require_permission
from business_operations import identifier, text, transaction
from business_personnel_workflow import PersonnelWorkflow, _sha, _shape, _integer
from payroll_de_2026 import (calculate, normalize_profile, month_range, RULE_VERSION, RULES, RULES_SHA256,
    FULL_RULES,FULL_RULES_SHA256,PAP_PROVENANCE)
from payroll_transition_2026 import TRANSITION_RULES,TRANSITION_RULES_SHA256
from payroll_periods_2026 import PERIOD_RULES,PERIOD_RULES_SHA256,SCOPES as PERIOD_SCOPES
from payroll_calculations_2026 import RULES as CALCULATION_RULES,RULES_SHA256 as CALCULATION_RULES_SHA256,SCOPES as CALCULATION_SCOPES
from workspace_api import BinaryAttachment

FEATURES = ('german_payroll_2026', 'payroll_employee_statements')
TABLES = ('business_payroll_events','business_payroll_requests')
COLUMNS = 'id,kind,employee_id,revision,payload_json,content_hash,previous_hash,identity_key,created_by,created_at,pdf_sha256'
ID = r'[a-f0-9]{32}'
INPUT_FIELDS = ('employee_id','profile_id','profile_revision','preparation_id','preparation_revision','gross_minor','full_month_confirmed')
PERIOD_INPUT_FIELDS = ('source_schema_version','employee_id','period_case_ref')
CALCULATION_INPUT_FIELDS = ('source_schema_version','employee_id','calculation_case_ref')
ONEOFF_INPUT_FIELDS = ('source_schema_version','employee_id','one_off_case_ref')
MULTIPLE_INPUT_FIELDS = ('source_schema_version','employee_id','multiple_one_off_case_ref')


def schema_statements(binary_type='BYTEA'):
    if binary_type not in ('BYTEA','BLOB'):
        raise ValueError('Unsupported payroll binary type')
    return [f'''CREATE TABLE IF NOT EXISTS business_payroll_events(
      id TEXT NOT NULL,kind TEXT NOT NULL CHECK(kind IN ('profile','run')),
      employee_id TEXT NOT NULL REFERENCES business_employees(id),revision INTEGER NOT NULL CHECK(revision>0),
      payload_json TEXT NOT NULL,content_hash TEXT NOT NULL,previous_hash TEXT,identity_key TEXT,
      created_by TEXT NOT NULL REFERENCES users(id),created_at TEXT NOT NULL,pdf {binary_type},pdf_sha256 TEXT,
      PRIMARY KEY(id,revision),UNIQUE(employee_id,identity_key))''',
      '''CREATE TABLE IF NOT EXISTS business_payroll_requests(
      user_id TEXT NOT NULL REFERENCES users(id),request_id TEXT NOT NULL,request_hash TEXT NOT NULL,
      result_json TEXT NOT NULL,PRIMARY KEY(user_id,request_id))''',
      'CREATE INDEX IF NOT EXISTS business_payroll_employee ON business_payroll_events(employee_id,kind,id,revision)']


def protected_tables():
    return TABLES


def runtime_privileges():
    return {table: ('SELECT','INSERT') for table in TABLES}


def guard_statements(dialect):
    if dialect == 'sqlite':
        output = [f"CREATE TRIGGER IF NOT EXISTS {table}_{action.lower()}_guard BEFORE {action} ON {table} "
                  "BEGIN SELECT RAISE(ABORT,'immutable payroll record'); END" for table in TABLES for action in ('UPDATE','DELETE')]
        for table,condition in zip(TABLES, ('(id=NEW.id AND revision=NEW.revision) OR (NEW.identity_key IS NOT NULL AND employee_id=NEW.employee_id AND identity_key=NEW.identity_key)',
                                           'user_id=NEW.user_id AND request_id=NEW.request_id')):
            output.append(f"CREATE TRIGGER IF NOT EXISTS {table}_insert_guard BEFORE INSERT ON {table} "
                          f"WHEN EXISTS(SELECT 1 FROM {table} WHERE {condition}) "
                          "BEGIN SELECT RAISE(ABORT,'immutable payroll record'); END")
        return output
    if dialect == 'postgresql':
        output = ["""CREATE OR REPLACE FUNCTION business_payroll_immutable_guard() RETURNS trigger LANGUAGE plpgsql
          AS $$ BEGIN RAISE EXCEPTION 'immutable payroll record'; END; $$"""]
        for table in TABLES:
            for action in ('UPDATE','DELETE'):
                name = table+'_'+action.lower()+'_guard'
                output.append(f"DO $$ BEGIN IF NOT EXISTS(SELECT 1 FROM pg_trigger WHERE tgname='{name}' AND tgrelid='{table}'::regclass) THEN "
                              f"CREATE TRIGGER {name} BEFORE {action} ON {table} FOR EACH ROW EXECUTE FUNCTION business_payroll_immutable_guard(); END IF; END $$")
        return output
    raise ValueError('Unsupported payroll guard dialect')


class Payroll:
    def __init__(self, office, *, clock=None):
        self.office,self.db = office,office.db
        self.hr = PersonnelWorkflow(office,clock=clock)

    def _access(self, actor, employee_id, permission='personnel.read', own=False):
        return self.hr._employee(actor,employee_id,permission=permission,own=own)

    def _gate(self, actor):
        from business_schema import require_capability
        from business_organization import require_active
        require_capability(self.office,'business_payroll')
        require_active(self.office,actor,'/payroll','business_payroll')

    def _receipt(self, actor, operation, data):
        identifier(data.get('request_id'),'Vorgangs-ID')
        fingerprint = _sha([operation,data])
        row = self.db.execute('SELECT request_hash,result_json FROM business_payroll_requests WHERE user_id=? AND request_id=?',
                              (actor['id'],data['request_id'])).fetchone()
        if row:
            if row['request_hash'] != fingerprint:
                raise Problem(409,'Diese Vorgangs-ID wurde bereits mit anderem Inhalt verwendet.')
            result=json.loads(row['result_json'])
            if result.get('source',{}).get('source_schema_version')==2:
                self._verify_period_record(result)
            if result.get('source',{}).get('source_schema_version') in (3,4,5):
                self._verify_calculation_record(result)
            return fingerprint,result
        return fingerprint,None

    def _verify_period_record(self,record):
        from business_payroll_facts import PayrollFacts,validate_fact_sources
        if self._event(self._row(record['id'],'run',record['revision']))!=record:
            raise Problem(500,'Die historische Periodenquittung stimmt nicht mit der angenommenen Lohnfassung überein.')
        fact=record['source']['period_case']
        if PayrollFacts(self.office)._get(fact['id'],fact['revision'])!=fact:
            raise Problem(500,'Die historische Lohnfaktenquelle wurde verändert.')
        try:validate_fact_sources(self.office,fact)
        except ValueError as error:raise Problem(500,'Die historische Lohnfaktenquelle ist nicht reproduzierbar.') from error
        if _calculate_source(record['source'],rule_version=record['calculation']['rule_version'])!=record['calculation']:
            raise Problem(500,'Die historische Periodenberechnung wurde verändert.')

    def _period_read_access(self,actor,employee_id,records):
        if any(record.get('source',{}).get('source_schema_version') in (2,3,4,5) for record in records):
            self._access(actor,employee_id)

    def _verify_calculation_record(self,record):
        if record['source'].get('source_schema_version')==5:
            from payroll_multiple_runs import verify_record
            return verify_record(self,record)
        if record['source'].get('source_schema_version')==4:
            from payroll_oneoff_runs import verify_record
            return verify_record(self,record)
        from business_payroll_calculation_cases import PayrollCalculationCases,validate_case_sources
        from payroll_travel_recording import validate_tax_recording
        if self._event(self._row(record['id'],'run',record['revision']))!=record:
            raise Problem(500,'Die historische Gesamtfallquittung widerspricht dem tatsächlichen Lohnarchiv.')
        fact=record['source']['calculation_case']
        if PayrollCalculationCases(self.office)._get(fact['id'],fact['revision'])!=fact:
            raise Problem(500,'Die tatsächliche historische Gesamtfallquelle wurde verändert.')
        try:
            validate_case_sources(self.office,fact);validate_tax_recording(self.office,record)
        except ValueError as error:raise Problem(500,'Historische Quellen oder tatsächliche Steuererfassung sind nicht reproduzierbar.') from error
        if _calculate_source(record['source'],rule_version=record['calculation']['rule_version'])!=record['calculation']:
            raise Problem(500,'Die historische Gesamtberechnung wurde verändert.')

    def _write(self, actor, employee_id, permission, operation, data, callback):
        with transaction(self.office):
            fresh,employee = self._access(actor,employee_id,permission)
            self._access(fresh,employee_id,'personnel.read')
            period=data.get('source_schema_version') in (2,3,4,5)
            if not period:self._gate(fresh)
            fingerprint,previous = self._receipt(fresh,operation,data)
            if previous is not None:
                return previous
            if period:self._gate(fresh)
            try:
                result = callback(fresh,employee)
            except Problem as error:
                if error.status == 409:
                    raise Problem(409,error.message,request_resolution='not_accepted') from None
                raise
            self.db.execute('INSERT INTO business_payroll_requests(user_id,request_id,request_hash,result_json) VALUES(?,?,?,?)',
                            (fresh['id'],data['request_id'],fingerprint,canonical(result)))
            self.office.audit(fresh,'payroll.'+operation,result['id'])
            return result

    def _event(self,row):
        payload = json.loads(row['payload_json'])
        envelope = {key:row[key] for key in COLUMNS.split(',') if key not in ('payload_json','content_hash')}
        envelope['payload'] = payload
        if _sha(envelope) != row['content_hash']:
            raise Problem(500,'Integritätsprüfung des Payroll-Archivs fehlgeschlagen.')
        return dict(payload,**{key:row[key] for key in COLUMNS.split(',') if key not in ('payload_json','identity_key')})

    def _row(self,object_id,kind=None,revision=None):
        identifier(object_id)
        if revision is None:
            row = self.db.execute('SELECT '+COLUMNS+' FROM business_payroll_events WHERE id=? ORDER BY revision DESC LIMIT 1',(object_id,)).fetchone()
        else:
            _integer(revision,1)
            row = self.db.execute('SELECT '+COLUMNS+' FROM business_payroll_events WHERE id=? AND revision=?',(object_id,revision)).fetchone()
        if row is None or kind is not None and row['kind'] != kind:
            raise Problem(404,'Payroll-Vorgang nicht verfügbar.')
        return row

    def _latest(self,object_id,kind=None):
        return self._event(self._row(object_id,kind))

    def _all(self,kind,employee_id):
        rows = self.db.execute('SELECT '+','.join('e.'+key for key in COLUMNS.split(','))+
            ' FROM business_payroll_events e WHERE e.kind=? AND e.employee_id=? AND NOT EXISTS '
            '(SELECT 1 FROM business_payroll_events n WHERE n.id=e.id AND n.revision>e.revision) ORDER BY e.created_at,e.id',
            (kind,employee_id)).fetchall()
        return [self._event(row) for row in rows]

    def _append(self,actor,kind,employee_id,payload,previous=None,pdf=None):
        object_id,revision = (previous['id'],previous['revision']+1) if previous else (uuid.uuid4().hex,1)
        identity = None if previous else kind+':'+(payload['profile']['effective_from'] if kind=='profile' else payload['source']['month'])
        envelope = dict(id=object_id,kind=kind,employee_id=employee_id,revision=revision,
            previous_hash=previous['content_hash'] if previous else None,identity_key=identity,
            created_by=actor['id'],created_at=self.hr.now(),pdf_sha256=_sha(pdf) if pdf else None,payload=payload)
        self.db.execute('INSERT INTO business_payroll_events(id,kind,employee_id,revision,payload_json,content_hash,previous_hash,identity_key,created_by,created_at,pdf,pdf_sha256) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',
            (object_id,kind,employee_id,revision,canonical(payload),_sha(envelope),envelope['previous_hash'],identity,actor['id'],envelope['created_at'],pdf,envelope['pdf_sha256']))
        return self._latest(object_id,kind)

    def profiles(self,actor,query=None):
        return self.records(actor,'profile',query)

    def records(self,actor,kind,query=None):
        query = query or {}
        _shape(query,('employee_id',))
        with transaction(self.office):
            _,employee = self._access(actor,query.get('employee_id'),own=True)
            items=self._all(kind,employee['id'])
            self._period_read_access(actor,employee['id'],items)
            for value in items:
                if value.get('source',{}).get('source_schema_version') in (3,4,5):self._verify_calculation_record(value)
            return dict(employee_id=employee['id'],items=items)

    def get(self,actor,kind,object_id,history=False):
        with transaction(self.office):
            value = self._latest(object_id,kind)
            self._access(actor,value['employee_id'],own=True)
            if history:
                items=[self._event(row) for row in self.db.execute('SELECT '+COLUMNS+' FROM business_payroll_events WHERE id=? ORDER BY revision',(object_id,)).fetchall()]
                self._period_read_access(actor,value['employee_id'],items)
                for item in items:
                    if item.get('source',{}).get('source_schema_version') in (3,4,5):self._verify_calculation_record(item)
                return dict(items=items)
            self._period_read_access(actor,value['employee_id'],[value])
            if value.get('source',{}).get('source_schema_version') in (3,4,5):self._verify_calculation_record(value)
            return value

    def save_profile(self,actor,data):
        _shape(data,('request_id','employee_id','profile','source_file_id','confirmed','id','revision','correction_reason'),
               ('request_id','employee_id','profile','source_file_id','confirmed','revision'))
        profile = normalize_profile(data['profile'])
        if data['confirmed'] is not True:
            raise Problem(400,'Steuer-/Versicherungsmerkmale und ihre Nachweise ausdrücklich bestätigen.')
        if 'id' in data:
            identifier(data['id'])
        def save(fresh,employee):
            if profile.get('transition_assessment',{}).get('assessed_on','')>self.hr.now()[:10]:
                raise Problem(400,'Eine Prognoseprüfung darf nicht mit einem zukünftigen Prüfdatum bestätigt werden.')
            previous = self._latest(data['id'],'profile') if data.get('id') else None
            if previous and previous['employee_id'] != employee['id']:
                raise Problem(404,'Payroll-Profil nicht verfügbar.')
            if _integer(data['revision']) != (previous['revision'] if previous else 0):
                raise Problem(409,'Das Payroll-Profil wurde geändert. Bitte neu laden.')
            reason = text(data.get('correction_reason',''),'Korrekturgrund',1000,required=bool(previous))
            if previous and previous['profile']['effective_from'] != profile['effective_from']:
                raise Problem(400,'Ein neuer Gültigkeitsbeginn benötigt ein neues Payroll-Profil.')
            if any(item['profile']['effective_from']==profile['effective_from'] and (not previous or item['id']!=previous['id']) for item in self._all('profile',employee['id'])):
                raise Problem(409,'Für diesen Gültigkeitsbeginn besteht bereits ein Payroll-Profil.')
            original = self.hr._file(data['source_file_id'],employee['id'])
            if original['purpose'] != 'personnel':
                raise Problem(400,'Payroll-Stammdaten benötigen einen geschützten Personalaktennachweis.')
            return self._append(fresh,'profile',employee['id'],dict(profile=profile,
                source_file={key:original[key] for key in ('id','employee_id','sha256','content_hash')},
                confirmed=True,correction_reason=reason),previous)
        return self._write(actor,data['employee_id'],'personnel.write','profile.saved',data,save)

    def _prepare(self,actor,data):
        if data.get('source_schema_version')==5:
            from payroll_multiple_runs import prepare
            return prepare(self,actor,data)
        if data.get('source_schema_version')==4:
            from payroll_oneoff_runs import prepare
            return prepare(self,actor,data)
        if data.get('source_schema_version')==3:
            return self._prepare_calculation(actor,data)
        if data.get('source_schema_version')==2:
            return self._prepare_period(actor,data)
        _shape(data,INPUT_FIELDS,INPUT_FIELDS)
        _,employee = self._access(actor,data['employee_id'])
        profile = self._latest(data['profile_id'],'profile')
        preparation = self.hr._latest(data['preparation_id'],'preparation')
        if profile['employee_id'] != employee['id'] or preparation['employee_id'] != employee['id']:
            raise Problem(404,'Die Payroll-Quellen gehören nicht zu diesem Mitarbeiter.')
        if _integer(data['profile_revision'],1)!=profile['revision'] or _integer(data['preparation_revision'],1)!=preparation['revision']:
            raise Problem(409,'Payroll-Profil oder Monatsvorbereitung wurde geändert.')
        month = preparation['month']
        first,last = month_range(month)
        current = self.hr._snapshot(employee,month)
        if _sha(current) != preparation['source_hash']:
            raise Problem(409,'Die Monatsvorbereitung entspricht nicht mehr den aktuellen freigegebenen Quellen. Zuerst eine Korrekturversion abschließen.')
        applicable = sorted((item for item in self._all('profile',employee['id']) if item['profile']['effective_from']<=last.isoformat()),key=lambda item:item['profile']['effective_from'])
        eligible = [item for item in applicable if item['profile']['effective_from']<=first.isoformat()]
        if eligible and eligible[-1]['id']!=profile['id']:
            raise Problem(409,'Für diesen Monat ist ein neueres Payroll-Profil gültig.')
        source = dict(employee_id=employee['id'],month=month,input=dict(data),profile=profile,preparation=preparation)
        calculation = _calculate_source(source)
        return dict(source=source,calculation=calculation,preview_hash=_sha(dict(source=source,calculation=calculation)),
                    can_finalize=calculation['social_contributions_available'])

    def _prepare_period(self,actor,data):
        from business_payroll_facts import PayrollFacts
        _shape(data,PERIOD_INPUT_FIELDS,PERIOD_INPUT_FIELDS)
        if type(data['source_schema_version']) is not int or data['source_schema_version']!=2:
            raise Problem(400,'Die neue Quellenfassung muss ausdrücklich Version 2 verwenden.')
        _,employee=self._access(actor,data['employee_id'])
        fact=PayrollFacts(self.office,clock=self.hr.clock).resolve_period_case(actor,employee['id'],data['period_case_ref'],fresh=True)
        profile=next(value for value in fact['sources']['profiles']
            if {key:value[key] for key in ('id','revision','content_hash')}==fact['plan']['selected_profile_ref'])
        source=dict(source_schema_version=2,employee_id=employee['id'],month=fact['details']['month'],
            input=json.loads(canonical(data)),profile=profile,preparation=fact['sources']['preparation'],period_case=fact)
        calculation=_calculate_source(source)
        return dict(source=source,calculation=calculation,preview_hash=_sha(dict(source=source,calculation=calculation)),
            can_finalize=calculation['payroll_calculation_complete'])

    def preview(self,actor,data):
        with transaction(self.office):
            result = self._prepare(actor,data)
            if data.get('source_schema_version') in (2,3,4,5):return result
            # Later effective records must also be represented in the immutable input.
            result['source']['profiles_in_month'] = [item for item in self._all('profile',data['employee_id'])
                if result['source']['month']+'-01' < item['profile']['effective_from'] <= month_range(result['source']['month'])[1].isoformat()]
            result['calculation'] = _calculate_source(result['source'])
            result['preview_hash'] = _sha(dict(source=result['source'],calculation=result['calculation']))
            result['can_finalize'] = result['calculation']['social_contributions_available']
            return result

    def _prepare_calculation(self,actor,data):
        from business_payroll_calculation_cases import PayrollCalculationCases
        _shape(data,CALCULATION_INPUT_FIELDS,CALCULATION_INPUT_FIELDS)
        if type(data['source_schema_version']) is not int or data['source_schema_version']!=3:
            raise Problem(400,'Gesamtfallquellen benötigen ausdrücklich Quellenfassung 3.')
        _,employee=self._access(actor,data['employee_id'])
        fact=PayrollCalculationCases(self.office,clock=self.hr.clock).resolve_calculation_case(actor,employee['id'],data['calculation_case_ref'],fresh=True)
        profile=next(value for value in fact['sources']['profiles'] if {key:value[key] for key in ('id','revision','content_hash')}==fact['plan']['selected_profile_ref'])
        source=dict(source_schema_version=3,employee_id=employee['id'],month=fact['details']['month'],input=json.loads(canonical(data)),
            profile=profile,preparation=fact['sources']['period_case']['sources']['preparation'],calculation_case=fact)
        calculation=_calculate_source(source)
        return dict(source=source,calculation=calculation,preview_hash=_sha(dict(source=source,calculation=calculation)),can_finalize=calculation['payroll_calculation_complete'])

    def finalize(self,actor,data):
        input_fields=MULTIPLE_INPUT_FIELDS if data.get('source_schema_version')==5 else ONEOFF_INPUT_FIELDS if data.get('source_schema_version')==4 else CALCULATION_INPUT_FIELDS if data.get('source_schema_version')==3 else PERIOD_INPUT_FIELDS if data.get('source_schema_version')==2 else INPUT_FIELDS
        fields = input_fields+('request_id','preview_hash','accepted_scope','confirmed','id','revision','correction_reason')
        _shape(data,fields,input_fields+('request_id','preview_hash','accepted_scope','confirmed','revision'))
        if data['confirmed'] is not True or not isinstance(data['preview_hash'],str) or not re.fullmatch(r'[a-f0-9]{64}',data['preview_hash']):
            raise Problem(400,'Geprüfte Berechnungsvorschau und ausdrückliche Bestätigung erforderlich.')
        if data['accepted_scope'] not in ('commercial_minijob_flat_tax','social_contributions_only','regular_standard_monthly','regular_transition_monthly')+PERIOD_SCOPES+CALCULATION_SCOPES+('regular_standard_oneoff','regular_standard_multiple_oneoff'):
            raise Problem(400,'Den tatsächlich verfügbaren Berechnungsumfang ausdrücklich bestätigen.')
        if 'id' in data:
            identifier(data['id'])
        with transaction(self.office):
            fresh,_ = self._access(actor,data['employee_id'],'personnel.approve')
            self._access(fresh,data['employee_id'])
            if data.get('source_schema_version') not in (2,3,4,5):self._gate(fresh)
            _,prior = self._receipt(fresh,'run.finalized',data)
            if prior is not None:
                return prior
            if data.get('source_schema_version') in (2,3,4,5):self._gate(fresh)
        inputs = {key:data[key] for key in input_fields}
        try:
            prepared = self.preview(actor,inputs)
        except Problem as error:
            if error.status!=409:
                raise
            def reject(fresh,employee):
                raise Problem(409,error.message)
            return self._write(actor,data['employee_id'],'personnel.approve','run.finalized',data,reject)
        pdf = _render(prepared)
        def commit(fresh,employee):
            current = self.preview(fresh,inputs)
            from business_payroll_accounts import require_no_carryover
            require_no_carryover(self.office,employee['id'],current['source']['month'])
            if current['preview_hash']!=data['preview_hash'] or current['preview_hash']!=prepared['preview_hash']:
                raise Problem(409,'Die Payroll-Quellen oder Berechnung wurden geändert. Vorschau neu prüfen.')
            if not current['can_finalize'] or current['calculation']['scope']!=data['accepted_scope']:
                raise Problem(409,'Der bestätigte Berechnungsumfang ist für diese Quellen nicht verfügbar.')
            previous = self._latest(data['id'],'run') if data.get('id') else None
            if previous and (previous['employee_id']!=employee['id'] or previous['source']['month']!=current['source']['month']):
                raise Problem(404,'Die Korrektur gehört nicht zu diesem Mitarbeiter und Monat.')
            if previous and previous['source'].get('source_schema_version') in (4,5) and current['source'].get('source_schema_version')!=previous['source'].get('source_schema_version'):
                raise Problem(409,'Ein angenommener Einmalanspruch muss mit seinem vollständigen Einmalfall korrigiert werden; ein Wechsel zum bloß laufenden Lohn darf ihn nicht entfernen.')
            if current['source'].get('source_schema_version')==5:
                from payroll_multiple_runs import require_supported_correction
                require_supported_correction(self,previous,current)
            if _integer(data['revision'])!=(previous['revision'] if previous else 0):
                raise Problem(409,'Der Berechnungslauf wurde geändert. Bitte neu laden.')
            if not previous and any(item['source']['month']==current['source']['month'] for item in self._all('run',employee['id'])):
                raise Problem(409,'Für diesen Monat besteht bereits ein Lauf. Eine begründete Korrekturversion anlegen.')
            reason = text(data.get('correction_reason',''),'Korrekturgrund',1000,required=bool(previous))
            result = current['calculation']
            delta = None if previous is None else _delta(result,previous['calculation'])
            recorded=self._append(fresh,'run',employee['id'],dict(source=current['source'],calculation=result,
                preview_hash=current['preview_hash'],accepted_scope=data['accepted_scope'],confirmed=True,
                correction_reason=reason,delta=delta,status='calculation_recorded',transmission_status='not_transmitted'),previous,pdf)
            if current['source'].get('source_schema_version') in (3,4,5):
                from payroll_travel_recording import record_tax_treatment
                record_tax_treatment(self.office,fresh,recorded)
            if current['source'].get('source_schema_version')==4:
                from business_payroll_oneoff_cases import record_run_consumption
                record_run_consumption(self.office,fresh,recorded,previous=previous)
            if current['source'].get('source_schema_version')==5:
                from business_payroll_multiple_cases import record_run_consumption
                record_run_consumption(self.office,fresh,recorded,previous=previous)
            return recorded
        return self._write(actor,data['employee_id'],'personnel.approve','run.finalized',data,commit)

    def export(self,actor,object_id,format_,revision=None):
        with transaction(self.office):
            latest = self._latest(object_id,'run')
            self._access(actor,latest['employee_id'],'personnel.export')
            self._access(actor,latest['employee_id'])
            if revision is not None:
                if not isinstance(revision,str) or not re.fullmatch(r'[1-9]\d{0,7}',revision):
                    raise Problem(400,'Gültige historische Revision erwartet.')
                latest = self._event(self._row(object_id,'run',int(revision)))
            if latest['source'].get('source_schema_version') in (3,4,5):self._verify_calculation_record(latest)
            name = 'lohn-berechnung-'+latest['source']['month']+'-v'+str(latest['revision'])
            if format_=='json':
                content,mime = canonical(latest).encode(),'application/json; charset=utf-8'
            else:
                row = self.db.execute('SELECT pdf,pdf_sha256 FROM business_payroll_events WHERE id=? AND revision=?',(object_id,latest['revision'])).fetchone()
                content,mime = bytes(row['pdf']),'application/pdf'
                if _sha(content)!=row['pdf_sha256']:
                    raise Problem(500,'Integritätsprüfung des Payroll-PDF fehlgeschlagen.')
            self.office.audit(_fresh(self.office,actor),'payroll.run.exported',object_id+':'+str(latest['revision']))
            return BinaryAttachment(content,name+'.'+format_),mime

    def _ledger(self,actor,employee_id,year):
        from payroll_ledger import build_ledger
        _,employee=self._access(actor,employee_id,own=True)
        if not isinstance(year,str) or not re.fullmatch(r'20\d{2}',year):
            raise Problem(400,'Kalenderjahr als vierstellige Jahreszahl angeben.')
        records=[record for record in self._all('run',employee_id) if record['source']['month'].startswith(year+'-')]
        self._period_read_access(actor,employee_id,records)
        if len({record['source']['month'] for record in records})!=len(records):
            raise Problem(500,'Mehrere wirksame Abrechnungsläufe für denselben Monat.')
        histories={}
        for record in records:
            if record['source'].get('source_schema_version') in (3,4,5):self._verify_calculation_record(record)
            if _calculate_source(record['source'],rule_version=record['calculation']['rule_version'])!=record['calculation']:
                raise Problem(500,'Die archivierte Monatsberechnung lässt sich nicht reproduzieren.')
            chain=[self._event(row) for row in self.db.execute('SELECT '+COLUMNS+
                ' FROM business_payroll_events WHERE id=? ORDER BY revision',(record['id'],)).fetchall()]
            previous=None
            for event in chain:
                if event['source'].get('source_schema_version') in (3,4,5):self._verify_calculation_record(event)
                if (event['employee_id']!=employee_id or event['source']['month']!=record['source']['month']
                        or event['revision']!=(previous['revision']+1 if previous else 1)
                        or event['previous_hash']!=(previous['content_hash'] if previous else None)
                        or event['delta']!=(_delta(event['calculation'],previous['calculation']) if previous else None)):
                    raise Problem(500,'Die monatliche Korrekturhistorie ist nicht vollständig nachvollziehbar.')
                previous=event
            if previous!=record:
                raise Problem(500,'Die wirksame Monatsrevision stimmt nicht mit der Historie überein.')
            histories[record['id']]=chain
        from business_payroll_accounts import PayrollAccounts,available
        accounts=[];carry_histories={}
        if available(self.office):
            accounts=PayrollAccounts(self.office)._all(employee_id)
            for account in accounts:
                PayrollAccounts(self.office)._verify_source5(account)
                if account['kind']=='carryover' and account['details']['month'].startswith(year+'-'):
                    carry_histories[account['id']]=[PayrollAccounts(self.office)._event(row) for row in self.db.execute(
                        'SELECT * FROM business_payroll_account_events WHERE id=? ORDER BY revision',(account['id'],)).fetchall()]
                if account['kind']=='carryover' and account['details']['status']=='active' and account['details']['month'].startswith(year+'-'):
                    month=account['details']['month']
                    if any(record['source']['month']==month for record in records):
                        raise Problem(500,'Monatsvortrag überschneidet sich mit lokaler Abrechnung.')
                    records.append(dict(id=account['id'],revision=account['revision'],content_hash=account['content_hash'],
                        origin='external_carryover',account=account,calculation=account['sources']['calculation'],
                        source=dict(month=month,profile=account['sources']['profile'],preparation=None)))
                    histories[account['id']]=[]
        wage_interruptions=None
        if any(value['source'].get('source_schema_version') in (3,4,5) for value in records):
            from business_payroll_wage_interruptions import current_projection
            wage_interruptions=current_projection(self.office,employee_id,year,records)
        return build_ledger(employee,year,records,histories,accounts,carry_histories,wage_interruptions=wage_interruptions)

    def ledger(self,actor,query):
        from payroll_ledger import export_contents,export_manifest
        _shape(query,('employee_id','year'),('employee_id','year'))
        with transaction(self.office):
            ledger=self._ledger(actor,query['employee_id'],query['year'])
            contents=export_contents(ledger)
            return dict(ledger=ledger,exports=export_manifest(ledger,contents))

    def export_ledger(self,actor,query,format_):
        from payroll_ledger import export_contents,export_manifest
        _shape(query,('employee_id','year','snapshot_hash'),('employee_id','year','snapshot_hash'))
        if not isinstance(query['snapshot_hash'],str) or not re.fullmatch(r'[a-f0-9]{64}',query['snapshot_hash']):
            raise Problem(400,'Geprüfte Jahresübersicht mit gültiger Snapshot-Prüfsumme auswählen.')
        if format_ not in ('json','csv','pdf'):
            raise Problem(400,'Unbekanntes Exportformat.')
        with transaction(self.office):
            fresh,_=self._access(actor,query['employee_id'],'personnel.export')
            self._access(fresh,query['employee_id'])
            ledger=self._ledger(fresh,query['employee_id'],query['year'])
            if ledger['snapshot_hash']!=query['snapshot_hash']:
                raise Problem(409,'Die Jahresübersicht wurde durch neue Quellen oder Korrekturen geändert. Zuerst neu laden und prüfen.')
            contents=export_contents(ledger)
            manifest=export_manifest(ledger,contents)[format_]
            self.office.audit(fresh,'payroll.ledger.exported',query['employee_id']+':'+query['year']+':'+ledger['snapshot_hash'])
            return BinaryAttachment(contents[format_],manifest['filename']),manifest['media_type']


def _calculate_source(source,*,rule_version=None):
    if source.get('source_schema_version')==5:
        from payroll_multiple_runs import calculate_run_source
        return calculate_run_source(source,rule_version=rule_version)
    if source.get('source_schema_version')==4:
        from payroll_oneoff_runs import calculate_run_source
        return calculate_run_source(source,rule_version=rule_version)
    if source.get('source_schema_version')==3:
        from payroll_calculations_2026 import build_calculation_plan,calculate_calculation_source
        fields=('source_schema_version','employee_id','month','input','profile','preparation','calculation_case')
        _shape(source,fields,fields);_shape(source['input'],CALCULATION_INPUT_FIELDS,CALCULATION_INPUT_FIELDS)
        fact=source['calculation_case'];snapshot=fact['sources']
        plan=build_calculation_plan(snapshot,rule_version=fact['rule_version'],source_contract_version=fact['source_contract_version'])
        selected=next(value for value in snapshot['profiles'] if {key:value[key] for key in ('id','revision','content_hash')}==plan['selected_profile_ref'])
        if (type(source['source_schema_version']) is not int or type(source['input']['source_schema_version']) is not int
                or source['input']['source_schema_version']!=3 or source['input']['employee_id']!=source['employee_id']
                or source['input']['calculation_case_ref']!={key:fact[key] for key in ('id','revision','content_hash')}
                or fact['employee_id']!=source['employee_id'] or fact['kind']!='calculation_case' or fact['status']!='active'
                or fact['details']['month']!=source['month'] or snapshot['month']!=source['month']
                or source['profile']!=selected or source['preparation']!=snapshot['period_case']['sources']['preparation'] or fact['plan']!=plan
                or rule_version is not None and rule_version!=fact['rule_version']):
            raise Problem(400,'Unveränderlicher Gesamtfall, Regel und tatsächliche Abrechnungsquelle widersprechen sich.')
        return calculate_calculation_source(snapshot,rule_version=fact['rule_version'],source_contract_version=fact['source_contract_version'])
    if source.get('source_schema_version')==2:
        from payroll_periods_2026 import build_period_plan,calculate_period_source
        _shape(source,('source_schema_version','employee_id','month','input','profile','preparation','period_case'),
            ('source_schema_version','employee_id','month','input','profile','preparation','period_case'))
        _shape(source['input'],PERIOD_INPUT_FIELDS,PERIOD_INPUT_FIELDS)
        fact=source['period_case'];snapshot=fact['sources'];plan=build_period_plan(snapshot)
        selected=next(value for value in snapshot['profiles']
            if {key:value[key] for key in ('id','revision','content_hash')}==plan['selected_profile_ref'])
        if (source['input']['source_schema_version']!=2 or source['input']['employee_id']!=source['employee_id']
                or source['input']['period_case_ref']!={key:fact[key] for key in ('id','revision','content_hash')}
                or fact['employee_id']!=source['employee_id'] or fact['kind']!='period_case' or fact['status']!='active'
                or fact['details']['month']!=source['month'] or snapshot['month']!=source['month']
                or source['profile']!=selected or source['preparation']!=snapshot['preparation'] or fact['plan']!=plan):
            raise Problem(400,'Die unveränderlichen Periodenquellen und ihre Berechnung stimmen nicht überein.')
        return calculate_period_source(snapshot,rule_version=rule_version)
    profile = source['profile']['profile']
    preparation = source['preparation']
    snapshot = preparation['snapshot']
    inputs = source['input']
    first,last = month_range(source['month'])
    issues = []
    employee = snapshot['employee']
    if employee['employment_from'] and employee['employment_from']>first.isoformat() or employee['employment_to'] and employee['employment_to']<last.isoformat():
        issues.append('full_month_required')
    agreements = snapshot['agreements']
    if len(agreements)!=1:
        issues.append('multiple_wage_agreements')
    else:
        agreement = agreements[0]
        if agreement['employment_kind']!=profile['employment_kind']:
            issues.append('wage_source_mismatch')
        if agreement['pay_basis']=='monthly':
            expected = agreement['amount_minor']
            if profile['regular_annual_gross_minor']!=expected*12:
                issues.append('wage_source_mismatch')
        else:
            with localcontext() as context:
                context.prec=40
                expected=int((Decimal(agreement['amount_minor'])*Decimal(snapshot['net_work_seconds'])/Decimal(3600)).quantize(Decimal(1),rounding=ROUND_HALF_UP))
        if expected!=inputs['gross_minor']:
            issues.append('wage_source_mismatch')
        if any(item['kind']!='vacation' or agreement['pay_basis']!='monthly' for item in snapshot['approved_absences']):
            issues.append('absence_requires_review')
    if source.get('profiles_in_month'):
        issues.append('profile_changed_in_month')
    result = calculate(profile,source['month'],inputs['gross_minor'],full_month_confirmed=inputs['full_month_confirmed'],
        source_issues=issues,rule_version=rule_version)
    result['travel_expenses_included_in_net'] = False
    return result


def _render(prepared):
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import SimpleDocTemplate,Paragraph,Spacer
    source,result = prepared['source'],prepared['calculation']
    stream=io.BytesIO(); styles=getSampleStyleSheet()
    title = {'commercial_minijob_flat_tax':'Minijob-Berechnungsbeleg',
        'commercial_minijob_period_flat_tax':'Minijob-Berechnungsbeleg mit Zeitnachweis',
        'regular_standard_monthly':'Lohnberechnungsbeleg',
        'regular_transition_monthly':'Midijob-Lohnberechnungsbeleg',
        'regular_standard_period':'Lohnberechnungsbeleg mit Zeitnachweis',
        'regular_standard_oneoff':'Lohnberechnungsbeleg mit sonstigem Bezug',
        'regular_standard_multiple_oneoff':'Lohnberechnungsbeleg mit einzeln zugeordnetem sonstigem Bezug',
        'regular_transition_period':'Midijob-Lohnberechnungsbeleg mit Zeitnachweis',
        'social_contributions_only':'Sozialversicherungsberechnung – Lohnsteuer offen'}.get(result['scope'],'Payroll-Prüfbeleg')
    story=[Paragraph(title+' '+source['month'],styles['Title'])]
    def line(value):
        story.extend([Paragraph(escape(str(value)),styles['Normal']),Spacer(1,5)])
    line(source['preparation']['snapshot']['employee']['name'])
    line('Regelstand: '+result['rule_version'])
    line('Regel-SHA256: '+result['rules_sha256'])
    if result.get('pap_version'):
        line('PAP-Implementierung: '+result['pap_version'])
        line('PAP-Quellenmetadaten-SHA256: '+result['pap_provenance_sha256'])
    line('Quellen-/Ergebnis-SHA256: '+prepared['preview_hash'])
    line('Brutto: '+str(result['gross_minor'])+' Cent EUR')
    extra=(result.get('one_off_details') or result.get('multiple_one_off_details',{}).get('single_original_calculation',{}).get('one_off_details'))
    if extra:
        line('Sonstiger Bezug: '+str(extra['amount_minor'])+' Cent EUR / geplanter tatsächlicher Zufluss '+extra['receipt_date'])
        line('Einmalanspruch: '+canonical(extra['earning_ref']))
        line('Laufender Originalfall: '+canonical({key:source['calculation_case'][key] for key in ('id','revision','content_hash')}))
        if extra.get('assignment'):line('SV-Zuordnung des Einmalbezugs: '+canonical(extra['assignment']))
        if extra.get('tax'):
            line('Steuer auf sonstigen Bezug: Lohnsteuer '+str(extra['tax']['STS'])+' / Solidaritätszuschlag '+
                str(extra['tax']['SOLZS'])+' / Kirchensteuer '+str(extra['church_tax_minor'])+' Cent EUR')
    if result.get('period_details'):
        periods=result['period_details']
        line('Bestätigter Periodenplan: '+periods['plan_hash'])
        for period in periods['employment_intervals']:
            line('Beschäftigung: '+period['start']+' bis '+period['end']+' / '+str(period['calendar_days'])+' Kalendertage')
        for earning in periods['earnings']:
            if 'proration_method' in earning:
                line('Entgeltmethode: '+earning['proration_method']+' / Quote '+str(earning['numerator'])+'/'+str(earning['denominator']))
            else:line('Belegte Ausfallvergütung: '+earning['kind']+' / '+str(earning['gross_minor'])+' Cent EUR')
        for period in periods['social_periods']:
            line('SV-Tage: '+str(period['days'])+' / KV-PV-Grenze '+str(period['caps']['health_minor'])+
                ' / RV-AV-Grenze '+str(period['caps']['pension_minor'])+' Cent EUR')
        for period in periods['tax_periods']:
            line('Steuer-LZZ: '+('Monat' if period['lzz']==2 else 'Tag')+' / Steuertage '+str(period['tax_days']))
            if period.get('inputs'):
                inputs=period['inputs']
                line('PAP-Rechenbrutto: '+str(inputs['pap_gross_minor'])+' Cent / Rest '+
                    str(inputs['gross_remainder_minor'])+'/'+str(inputs['gross_divisor'])+' Cent; tatsächliches Brutto unverändert')
        if periods.get('transition'):
            line('Übergangsbereich / Teil-Gesamtbasis: '+str(periods['transition']['total_assessment_minor'])+
                ' / Teil-AN-Basis: '+str(periods['transition']['employee_assessment_minor'])+' Cent EUR')
        if periods.get('travel'):
            travel=periods['travel']
            line('Reiseverpflegung / Kennzeichen M: '+('ja' if travel['letter_m'] else 'nein'))
            line('Steuerfreie Reiseerstattung außerhalb der Lohnzahlung: '+str(travel['tax_free_external_minor'])+' Cent EUR')
            line('Individuell steuerpflichtige Reiseerstattung: '+str(travel['individual_taxable_payroll_minor'])+' Cent EUR')
            line('Sachbezug ohne zusätzliche Barauszahlung: '+str(travel['benefit_in_kind_non_cash_minor'])+' Cent EUR')
        if periods.get('flat_travel_tax'):
            flat=periods['flat_travel_tax']
            line('Reise-Pauschalsteuer / Lohnsteuer '+str(flat['wage_tax_minor'])+' / Solidaritätszuschlag '+
                str(flat['solidarity_minor'])+' / Kirchensteuer '+str(flat['church_tax_minor'])+' Cent EUR')
            line('Belegter Arbeitnehmerabzug für Pauschalsteuer: '+str(flat['employee_tax_minor'])+' Cent EUR')
    if result.get('transition'):
        transition=result['transition']
        line('Belegter Übergangsbereich / tatsächlicher Monatsfall: '+transition['regime'])
        line('Prognostisches Monatsentgelt: '+str(transition['regular_monthly_gross_minor'])+' Cent EUR')
        for label,key in (('Gesamtbemessungsgrundlage','total_assessment_minor'),('AN-Bemessungsgrundlage','employee_assessment_minor'),('Umlagebasis','levy_assessment_minor')):
            line(label+': '+str(transition[key])+' Cent EUR')
        for branch,amounts in transition['branch_bases'].items():
            line('Begrenzte Basis / '+branch+': Gesamt '+str(amounts['total_minor'])+', AN '+str(amounts['employee_minor'])+' Cent EUR')
        for label,key in (('PV-Kinderlosenzuschlag','childless_surcharge_minor'),('PV-Kinderabschlag','children_discount_minor')):
            line(label+': '+str(transition['care_adjustments'][key])+' Cent EUR')
    for heading,key in (('Arbeitnehmer','employee_contributions'),('Arbeitgeber','employer_contributions'),('Arbeitgeber-Umlagen','employer_levies')):
        if result[key] is not None:
            for category,amount in result[key].items():
                line(heading+' / '+category+': '+str(amount)+' Cent EUR')
    if result['net_minor'] is not None:
        if result['scope'] in ('commercial_minijob_flat_tax','commercial_minijob_period_flat_tax','commercial_minijob_segments_flat_tax'):
            line('Arbeitgeber-Pauschsteuer (einschließlich Kirchensteuer/Soli): '+str(result['employer_flat_tax_minor'])+' Cent EUR')
        else:
            for label,key in (('Lohnsteuer','individual_wage_tax_minor'),('Solidaritätszuschlag','solidarity_minor'),('Kirchenlohnsteuer','church_tax_minor')):
                line(label+': '+str(result[key])+' Cent EUR')
        line('Netto: '+str(result['net_minor'])+' Cent EUR')
        if result.get('net_deductions_minor'):
            line('Belegte Nettoabzüge: '+str(result['net_deductions_minor'])+' Cent EUR')
        if 'net_deductions_minor' in result:line('Belegte Sachbezugs-/Steuerabwälzungsabzüge: '+str(result['net_deductions_minor'])+' Cent EUR')
        line('Auszahlungsbetrag: '+str(result['payout_minor'])+' Cent EUR')
        line('Zusätzlicher Arbeitnehmerbeitrag, falls erforderlich: '+str(result['employee_additional_payment_minor'])+' Cent EUR')
    for issue in result['blockers']:
        line(issue['message'])
    line('Arbeitgeberbetrag ohne Unfallversicherung: '+str(result['employer_total_excluding_accident_insurance_minor'])+' Cent EUR')
    if prepared['source'].get('source_schema_version') in (3,4,5):
        line('Steuerpflichtige Reiseerstattungen sind ausdrücklich enthalten; steuerfreie Reisezahlung bleibt separat. Keine Zahlung oder amtliche Meldung ausgeführt.')
    else:line('Auslagen sind separat zu prüfen und nicht im Netto enthalten. Keine Zahlung oder amtliche Meldung ausgeführt.')
    line('Berechnungsbeleg für den ausgewiesenen Fallumfang; keine Bestätigung amtlicher Systemzulassung oder vollständiger gesetzlicher Entgeltunterlagen.')
    SimpleDocTemplate(stream,pageCompression=0).build(story)
    return stream.getvalue()


def _delta(current,previous):
    keys=('gross_minor','employee_social_total_minor','employer_social_total_minor','employer_flat_tax_minor','net_minor')
    regular=('regular_standard_monthly','regular_transition_monthly','regular_standard_period','regular_transition_period','regular_standard_segments','regular_transition_segments','regular_standard_oneoff','regular_standard_multiple_oneoff')
    if current['scope'] in regular or previous['scope'] in regular:
        keys+=('individual_wage_tax_minor','solidarity_minor','church_tax_minor','employee_tax_minor','payout_minor')
    result={key:current[key]-previous[key] if current[key] is not None and previous[key] is not None else None for key in keys}
    if 'net_deductions_minor' in current or 'net_deductions_minor' in previous:
        result['net_deductions_minor']=current.get('net_deductions_minor',0)-previous.get('net_deductions_minor',0)
    return result


def validate_integrity(office):
    from business_schema import _tables
    present=set(TABLES).intersection(_tables(office))
    if not present:
        return True  # Genuine historical HR fixtures predate this additive module.
    if present!=set(TABLES):
        raise ValueError('Incomplete payroll schema')
    api=Payroll(office)
    from business_personnel_workflow import EVENT_COLUMNS
    try:
        previous={}
        for row in office.db.execute('SELECT '+COLUMNS+' FROM business_payroll_events ORDER BY id,revision').fetchall():
            value=api._event(row)
            prior=previous.get(row['id'])
            if row['revision']!=(prior['revision']+1 if prior else 1) or row['previous_hash']!=(prior['content_hash'] if prior else None):
                raise ValueError('Broken payroll revision chain')
            if prior and any(value[key]!=prior[key] for key in ('kind','employee_id')):
                raise ValueError('Changed payroll identity')
            if row['kind']=='profile':
                if normalize_profile(value['profile'])!=value['profile'] or value['confirmed'] is not True:
                    raise ValueError('Invalid payroll profile')
                if value['profile'].get('transition_assessment',{}).get('assessed_on','')>row['created_at'][:10]:
                    raise ValueError('Future payroll transition assessment')
                original=api.hr._file(value['source_file']['id'],value['employee_id'])
                if original['purpose']!='personnel' or any(original[key]!=value['source_file'][key] for key in ('id','employee_id','sha256','content_hash')):
                    raise ValueError('Changed payroll profile evidence')
                identity='profile:'+value['profile']['effective_from']
                if prior and (value['profile']['effective_from']!=prior['profile']['effective_from'] or not value['correction_reason']):
                    raise ValueError('Changed profile validity in correction')
            else:
                source=value['source']; calculated=value['calculation']; preparation=source['preparation']; profile=source['profile']
                if (source['employee_id']!=value['employee_id'] or preparation['employee_id']!=value['employee_id']
                        or profile['employee_id']!=value['employee_id'] or preparation['month']!=source['month']):
                    raise ValueError('Foreign payroll sources')
                original=office.db.execute('SELECT '+EVENT_COLUMNS+' FROM business_personnel_events WHERE id=? AND revision=?',
                    (preparation['id'],preparation['revision'])).fetchone()
                if original is None or original['kind']!='preparation' or api.hr._event(original)!=preparation:
                    raise ValueError('Missing payroll preparation source')
                if api._event(api._row(profile['id'],'profile',profile['revision']))!=profile:
                    raise ValueError('Missing payroll profile source')
                for changed in source.get('profiles_in_month',[]):
                    if changed['employee_id']!=value['employee_id'] or api._event(api._row(changed['id'],'profile',changed['revision']))!=changed:
                        raise ValueError('Foreign in-month payroll profile')
                if source.get('source_schema_version') in (3,4,5):
                    api._verify_calculation_record(value)
                elif source.get('source_schema_version')==2:
                    from business_payroll_facts import PayrollFacts,validate_fact_sources
                    fact=source['period_case']
                    if PayrollFacts(office)._get(fact['id'],fact['revision'])!=fact:
                        raise ValueError('Changed payroll period fact reference')
                    validate_fact_sources(office,fact)
                else:
                    _shape(source['input'],INPUT_FIELDS,INPUT_FIELDS)
                    if (source['input']['employee_id']!=value['employee_id'] or source['input']['profile_id']!=profile['id']
                            or source['input']['profile_revision']!=profile['revision'] or source['input']['preparation_id']!=preparation['id']
                            or source['input']['preparation_revision']!=preparation['revision']):
                        raise ValueError('Changed payroll input references')
                if (_calculate_source(source,rule_version=calculated.get('rule_version'))!=calculated or not calculated['social_contributions_available']
                        or _sha(dict(source=source,calculation=calculated))!=value['preview_hash']
                        or value['accepted_scope']!=calculated['scope'] or value['confirmed'] is not True
                        or value['transmission_status']!='not_transmitted' or value['status']!='calculation_recorded'):
                    raise ValueError('Payroll calculation does not reproduce')
                pdf=office.db.execute('SELECT pdf FROM business_payroll_events WHERE id=? AND revision=?',(row['id'],row['revision'])).fetchone()['pdf']
                if not pdf or _sha(bytes(pdf))!=row['pdf_sha256']:
                    raise ValueError('Changed payroll PDF')
                identity='run:'+source['month']
                if prior:
                    expected_delta=_delta(calculated,prior['calculation'])
                    if prior['source']['month']!=source['month'] or not value['correction_reason'] or value['delta']!=expected_delta:
                        raise ValueError('Invalid payroll correction')
                elif value['delta'] is not None:
                    raise ValueError('Unexpected initial payroll correction')
            if row['identity_key']!=(None if prior else identity):
                raise ValueError('Changed payroll period identity')
            previous[row['id']]=value
        for row in office.db.execute('SELECT * FROM business_payroll_requests').fetchall():
            identifier(row['request_id'])
            result=json.loads(row['result_json'])
            if not re.fullmatch(r'[a-f0-9]{64}',row['request_hash']) or api._event(api._row(result['id'],revision=result['revision']))!=result:
                raise ValueError('Changed payroll command receipt')
    except (Problem,KeyError,TypeError,json.JSONDecodeError) as error:
        raise ValueError('Invalid payroll archive') from error
    return True


def methods(path):
    from business_payroll_statements import methods as statement_methods
    statement_route = statement_methods(path)
    if statement_route is not None:
        return statement_route
    if path in ('/payroll/profiles','/payroll/runs'):
        return 'GET, POST'
    if path=='/payroll/preview':
        return 'POST'
    if path in ('/payroll/rules','/payroll/ledger','/payroll/ledger/json','/payroll/ledger/csv','/payroll/ledger/pdf'):
        return 'GET'
    if re.fullmatch(r'/payroll/(?:profiles|runs)/'+ID+r'(?:/history)?',path) or re.fullmatch(r'/payroll/runs/'+ID+r'/(?:pdf|json)',path):
        return 'GET'
    return None


def dispatch(office,actor,path,method,data):
    from business_payroll_statements import methods as statement_methods, dispatch as statement_dispatch
    if statement_methods(path) is not None:
        return statement_dispatch(office,actor,path,method,data)
    allowed=methods(path)
    if allowed is None:
        return None
    if method not in allowed.split(', '):
        raise Problem(405,'HTTP-Methode nicht erlaubt.')
    api=Payroll(office)
    if method=='POST':
        handler=api.save_profile if path=='/payroll/profiles' else api.finalize if path=='/payroll/runs' else api.preview
        return handler(actor,data),200,'application/json'
    _shape(data,('_query',)); query=data.get('_query',{})
    if path=='/payroll/ledger':
        result=api.ledger(actor,query)
    elif path.startswith('/payroll/ledger/'):
        content,mime=api.export_ledger(actor,query,path.rsplit('/',1)[1])
        return content,200,mime
    elif path=='/payroll/rules':
        _shape(query,())
        with transaction(office):
            require_permission(office,actor,'personnel.read')
            result=dict(rules=RULES,rules_sha256=RULES_SHA256,regular_standard_rules=FULL_RULES,
                regular_standard_rules_sha256=FULL_RULES_SHA256,pap_provenance=PAP_PROVENANCE,
                regular_transition_rules=TRANSITION_RULES,regular_transition_rules_sha256=TRANSITION_RULES_SHA256,
                period_rules=PERIOD_RULES,period_rules_sha256=PERIOD_RULES_SHA256,
                calculation_rules=CALCULATION_RULES,calculation_rules_sha256=CALCULATION_RULES_SHA256,
                individual_wage_tax_available=True,official_system_approval=False)
    else:
        parts=path.split('/')[2:]
        kind='profile' if parts[0]=='profiles' else 'run'
        if len(parts)==1:
            result=api.records(actor,kind,query)
        elif len(parts)==3 and parts[2] in ('pdf','json'):
            _shape(query,('revision',))
            content,mime=api.export(actor,parts[1],parts[2],query.get('revision'))
            return content,200,mime
        else:
            _shape(query,())
            result=api.get(actor,kind,parts[1],len(parts)==3)
    return result,200,'application/json'

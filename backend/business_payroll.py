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
from workspace_api import BinaryAttachment

FEATURES = ('german_payroll_2026',)
TABLES = ('business_payroll_events','business_payroll_requests')
COLUMNS = 'id,kind,employee_id,revision,payload_json,content_hash,previous_hash,identity_key,created_by,created_at,pdf_sha256'
ID = r'[a-f0-9]{32}'
INPUT_FIELDS = ('employee_id','profile_id','profile_revision','preparation_id','preparation_revision','gross_minor','full_month_confirmed')


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
            return fingerprint,json.loads(row['result_json'])
        return fingerprint,None

    def _write(self, actor, employee_id, permission, operation, data, callback):
        with transaction(self.office):
            fresh,employee = self._access(actor,employee_id,permission)
            self._access(fresh,employee_id,'personnel.read')
            self._gate(fresh)
            fingerprint,previous = self._receipt(fresh,operation,data)
            if previous is not None:
                return previous
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
            return dict(employee_id=employee['id'],items=self._all(kind,employee['id']))

    def get(self,actor,kind,object_id,history=False):
        with transaction(self.office):
            value = self._latest(object_id,kind)
            self._access(actor,value['employee_id'],own=True)
            if history:
                return dict(items=[self._event(row) for row in self.db.execute('SELECT '+COLUMNS+' FROM business_payroll_events WHERE id=? ORDER BY revision',(object_id,)).fetchall()])
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

    def preview(self,actor,data):
        with transaction(self.office):
            result = self._prepare(actor,data)
            # Later effective records must also be represented in the immutable input.
            result['source']['profiles_in_month'] = [item for item in self._all('profile',data['employee_id'])
                if result['source']['month']+'-01' < item['profile']['effective_from'] <= month_range(result['source']['month'])[1].isoformat()]
            result['calculation'] = _calculate_source(result['source'])
            result['preview_hash'] = _sha(dict(source=result['source'],calculation=result['calculation']))
            result['can_finalize'] = result['calculation']['social_contributions_available']
            return result

    def finalize(self,actor,data):
        fields = INPUT_FIELDS+('request_id','preview_hash','accepted_scope','confirmed','id','revision','correction_reason')
        _shape(data,fields,INPUT_FIELDS+('request_id','preview_hash','accepted_scope','confirmed','revision'))
        if data['confirmed'] is not True or not isinstance(data['preview_hash'],str) or not re.fullmatch(r'[a-f0-9]{64}',data['preview_hash']):
            raise Problem(400,'Geprüfte Berechnungsvorschau und ausdrückliche Bestätigung erforderlich.')
        if data['accepted_scope'] not in ('commercial_minijob_flat_tax','social_contributions_only','regular_standard_monthly','regular_transition_monthly'):
            raise Problem(400,'Den tatsächlich verfügbaren Berechnungsumfang ausdrücklich bestätigen.')
        if 'id' in data:
            identifier(data['id'])
        with transaction(self.office):
            fresh,_ = self._access(actor,data['employee_id'],'personnel.approve')
            self._access(fresh,data['employee_id'])
            self._gate(fresh)
            _,prior = self._receipt(fresh,'run.finalized',data)
            if prior is not None:
                return prior
        inputs = {key:data[key] for key in INPUT_FIELDS}
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
            if _integer(data['revision'])!=(previous['revision'] if previous else 0):
                raise Problem(409,'Der Berechnungslauf wurde geändert. Bitte neu laden.')
            if not previous and any(item['source']['month']==current['source']['month'] for item in self._all('run',employee['id'])):
                raise Problem(409,'Für diesen Monat besteht bereits ein Lauf. Eine begründete Korrekturversion anlegen.')
            reason = text(data.get('correction_reason',''),'Korrekturgrund',1000,required=bool(previous))
            result = current['calculation']
            delta = None if previous is None else _delta(result,previous['calculation'])
            return self._append(fresh,'run',employee['id'],dict(source=current['source'],calculation=result,
                preview_hash=current['preview_hash'],accepted_scope=data['accepted_scope'],confirmed=True,
                correction_reason=reason,delta=delta,status='calculation_recorded',transmission_status='not_transmitted'),previous,pdf)
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
        if len({record['source']['month'] for record in records})!=len(records):
            raise Problem(500,'Mehrere wirksame Abrechnungsläufe für denselben Monat.')
        histories={}
        for record in records:
            if _calculate_source(record['source'],rule_version=record['calculation']['rule_version'])!=record['calculation']:
                raise Problem(500,'Die archivierte Monatsberechnung lässt sich nicht reproduzieren.')
            chain=[self._event(row) for row in self.db.execute('SELECT '+COLUMNS+
                ' FROM business_payroll_events WHERE id=? ORDER BY revision',(record['id'],)).fetchall()]
            previous=None
            for event in chain:
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
        return build_ledger(employee,year,records,histories,accounts,carry_histories)

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
        'regular_standard_monthly':'Lohnberechnungsbeleg',
        'regular_transition_monthly':'Midijob-Lohnberechnungsbeleg',
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
        if result['scope']=='commercial_minijob_flat_tax':
            line('Arbeitgeber-Pauschsteuer (einschließlich Kirchensteuer/Soli): '+str(result['employer_flat_tax_minor'])+' Cent EUR')
        else:
            for label,key in (('Lohnsteuer','individual_wage_tax_minor'),('Solidaritätszuschlag','solidarity_minor'),('Kirchenlohnsteuer','church_tax_minor')):
                line(label+': '+str(result[key])+' Cent EUR')
        line('Netto: '+str(result['net_minor'])+' Cent EUR')
        line('Auszahlungsbetrag: '+str(result['payout_minor'])+' Cent EUR')
        line('Zusätzlicher Arbeitnehmerbeitrag, falls erforderlich: '+str(result['employee_additional_payment_minor'])+' Cent EUR')
    for issue in result['blockers']:
        line(issue['message'])
    line('Arbeitgeberbetrag ohne Unfallversicherung: '+str(result['employer_total_excluding_accident_insurance_minor'])+' Cent EUR')
    line('Auslagen sind separat zu prüfen und nicht im Netto enthalten. Keine Zahlung oder amtliche Meldung ausgeführt.')
    line('Berechnungsbeleg für den ausgewiesenen Fallumfang; keine Bestätigung amtlicher Systemzulassung oder vollständiger gesetzlicher Entgeltunterlagen.')
    SimpleDocTemplate(stream,pageCompression=0).build(story)
    return stream.getvalue()


def _delta(current,previous):
    keys=('gross_minor','employee_social_total_minor','employer_social_total_minor','employer_flat_tax_minor','net_minor')
    if current['scope'] in ('regular_standard_monthly','regular_transition_monthly') or previous['scope'] in ('regular_standard_monthly','regular_transition_monthly'):
        keys+=('individual_wage_tax_minor','solidarity_minor','church_tax_minor','employee_tax_minor','payout_minor')
    return {key:current[key]-previous[key] if current[key] is not None and previous[key] is not None else None for key in keys}


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

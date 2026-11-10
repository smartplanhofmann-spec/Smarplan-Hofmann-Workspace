"""Private, immutable statutory payroll identities, payment evidence and carry-ins.

Explicit source documents and version references; no external payment/reporting.
The supported case is the same bounded monthly 2026 payroll scope.
"""
import json
import re
import uuid
import unicodedata

from core import Problem,canonical
from business_foundation import _fresh
from business_operations import identifier,text,transaction
from business_personnel_workflow import PersonnelWorkflow,_sha,_shape,_integer
from payroll_de_2026 import calculate,day,month_range

FEATURES=('payroll_wage_account','payroll_source5_payment_dates')
TABLES=('business_payroll_account_events','business_payroll_account_requests')
ID=r'[a-f0-9]{32}'
IDENTITY_FIELDS=('profile_id','profile_revision','given_name','family_name','date_of_birth','address_line',
    'postal_code','city','country_code','tax_id','employer_name','employer_address','employer_tax_number',
    'employment_from','employment_to','tax_source','tax_source_date','valid_from','valid_to',
    'tax_allowance_yearly_minor','tax_addition_yearly_minor','religion_code','standard_case_confirmed')
PAYMENT_FIELDS=('run_id','run_revision','identity_id','identity_revision','payments',
    'tax_free_payments_minor','tax_free_basis','standard_case_confirmed')
CARRY_FIELDS=('month','profile_id','profile_revision','identity_id','identity_revision','gross_minor',
    'expected_net_minor','expected_employee_tax_minor','expected_employee_social_total_minor',
    'expected_employer_social_total_minor','expected_employer_total_minor','payments',
    'tax_free_payments_minor','tax_free_basis','standard_case_confirmed','status')


def _payment_key(payment):
    return payment['paid_on'],unicodedata.normalize('NFKC',payment['payment_reference']).casefold()


def schema_statements(binary_type='BYTEA'):
    return ['''CREATE TABLE IF NOT EXISTS business_payroll_account_events(
        id TEXT NOT NULL,revision INTEGER NOT NULL CHECK(revision>0),
        kind TEXT NOT NULL CHECK(kind IN ('identity','payment','carryover')),
        employee_id TEXT NOT NULL REFERENCES business_employees(id),identity_key TEXT,
        payload_json TEXT NOT NULL,content_hash TEXT NOT NULL,previous_hash TEXT,
        created_by TEXT NOT NULL REFERENCES users(id),created_at TEXT NOT NULL,
        PRIMARY KEY(id,revision),UNIQUE(employee_id,identity_key))''',
        '''CREATE TABLE IF NOT EXISTS business_payroll_account_requests(
        user_id TEXT NOT NULL REFERENCES users(id),request_id TEXT NOT NULL,request_hash TEXT NOT NULL,
        result_json TEXT NOT NULL,PRIMARY KEY(user_id,request_id))''',
        'CREATE INDEX IF NOT EXISTS business_payroll_account_employee ON business_payroll_account_events(employee_id,kind,id,revision)']


def protected_tables():
    return TABLES


def runtime_privileges():
    return {table:('SELECT','INSERT') for table in TABLES}


def guard_statements(dialect):
    if dialect=='sqlite':
        output=[f"CREATE TRIGGER IF NOT EXISTS {table}_{action.lower()}_guard BEFORE {action} ON {table} BEGIN SELECT RAISE(ABORT,'immutable payroll account'); END"
            for table in TABLES for action in ('UPDATE','DELETE')]
        for table,condition in zip(TABLES,('id=NEW.id AND revision=NEW.revision OR NEW.identity_key IS NOT NULL AND employee_id=NEW.employee_id AND identity_key=NEW.identity_key',
            'user_id=NEW.user_id AND request_id=NEW.request_id')):
            output.append(f"CREATE TRIGGER IF NOT EXISTS {table}_insert_guard BEFORE INSERT ON {table} WHEN EXISTS(SELECT 1 FROM {table} WHERE {condition}) BEGIN SELECT RAISE(ABORT,'immutable payroll account'); END")
        return output
    if dialect=='postgresql':
        output=["CREATE OR REPLACE FUNCTION business_payroll_account_immutable_guard() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'immutable payroll account'; END; $$"]
        for table in TABLES:
            for action in ('UPDATE','DELETE'):
                name=table+'_'+action.lower()+'_guard'
                output.append(f"DO $$ BEGIN IF NOT EXISTS(SELECT 1 FROM pg_trigger WHERE tgname='{name}' AND tgrelid='{table}'::regclass) THEN CREATE TRIGGER {name} BEFORE {action} ON {table} FOR EACH ROW EXECUTE FUNCTION business_payroll_account_immutable_guard(); END IF; END $$")
        return output
    raise ValueError('Unknown payroll account dialect')


class PayrollAccounts:
    def __init__(self,office,*,clock=None):
        from business_payroll import Payroll
        self.office,self.db=office,office.db
        self.payroll=Payroll(office,clock=clock)
        self.hr=PersonnelWorkflow(office,clock=clock)

    def _event(self,row):
        value=dict(id=row['id'],revision=row['revision'],kind=row['kind'],employee_id=row['employee_id'],
            identity_key=row['identity_key'],previous_hash=row['previous_hash'],created_by=row['created_by'],
            created_at=row['created_at'],payload=json.loads(row['payload_json']))
        if _sha(value)!=row['content_hash']:
            raise Problem(500,'Integrität des Lohnkontonachweises verletzt.')
        payload=value.pop('payload');value.pop('identity_key')
        return dict(value,**payload,content_hash=row['content_hash'])

    def _get(self,object_id,revision=None):
        identifier(object_id)
        if revision is None:
            row=self.db.execute('SELECT * FROM business_payroll_account_events WHERE id=? ORDER BY revision DESC LIMIT 1',(object_id,)).fetchone()
        else:
            _integer(revision,1)
            row=self.db.execute('SELECT * FROM business_payroll_account_events WHERE id=? AND revision=?',(object_id,revision)).fetchone()
        if row is None:
            raise Problem(404,'Lohnkontonachweis nicht verfügbar.')
        return self._event(row)

    def _all(self,employee_id):
        rows=self.db.execute('SELECT e.* FROM business_payroll_account_events e WHERE e.employee_id=? AND NOT EXISTS '
            '(SELECT 1 FROM business_payroll_account_events n WHERE n.id=e.id AND n.revision>e.revision) ORDER BY e.created_at,e.id',(employee_id,)).fetchall()
        return [self._event(row) for row in rows]

    def _verify_source5(self,record):
        if record.get('sources',{}).get('run',{}).get('source',{}).get('source_schema_version')!=5:return
        if self._get(record['id'],record['revision'])!=record:
            raise Problem(500,'Source5-Zahlungsquittung widerspricht dem tatsächlichen Original.')
        details,sources,_=self._normalize(record['employee_id'],'payment',record['details'])
        if details!=record['details'] or sources!=record['sources']:
            raise Problem(500,'Source5-Zahlungszuordnung ist nicht unverändert nachrechenbar.')
        receipts=self.db.execute('SELECT result_json FROM business_payroll_account_requests WHERE user_id=?',(record['created_by'],)).fetchall()
        if sum(json.loads(row['result_json'])==record for row in receipts)!=1:
            raise Problem(500,'Ursprüngliche Source5-Zahlungsannahmequittung fehlt oder ist doppelt vorhanden.')
        original=self.hr._file(record['source_file']['id'],record['employee_id'])
        if any(original[key]!=record['source_file'][key] for key in record['source_file']):
            raise Problem(500,'Geschütztes Source5-Zahlungsoriginal wurde verändert.')

    def records(self,actor,query):
        _shape(query,('employee_id',),('employee_id',))
        with transaction(self.office):
            _,employee=self.hr._employee(actor,query['employee_id'],own=True)
            items=self._all(employee['id'])
            for item in items:self._verify_source5(item)
            self.payroll._period_read_access(actor,employee['id'],[value.get('sources',{}).get('run',{}) for value in items])
            return dict(employee_id=employee['id'],items=items)

    def get(self,actor,object_id,history=False):
        with transaction(self.office):
            record=self._get(object_id)
            self.hr._employee(actor,record['employee_id'],own=True)
            if history:
                items=[self._event(row) for row in self.db.execute('SELECT * FROM business_payroll_account_events WHERE id=? ORDER BY revision',(object_id,)).fetchall()]
                for item in items:self._verify_source5(item)
                self.payroll._period_read_access(actor,record['employee_id'],[value.get('sources',{}).get('run',{}) for value in items])
                return dict(items=items)
            self._verify_source5(record)
            self.payroll._period_read_access(actor,record['employee_id'],[record.get('sources',{}).get('run',{})])
            return record

    def _profile(self,employee_id,details):
        profile=self.payroll._event(self.payroll._row(details['profile_id'],'profile',details['profile_revision']))
        if profile['employee_id']!=employee_id:
            raise Problem(404,'Steuerprofil gehört nicht zu diesem Mitarbeiter.')
        return profile

    def _identity(self,employee_id,details,profile,month,*,period_plan=None):
        identity=self._get(details['identity_id'],details['identity_revision'])
        if identity['kind']!='identity' or identity['employee_id']!=employee_id:
            raise Problem(404,'Identitätsnachweis gehört nicht zu diesem Mitarbeiter.')
        values=identity['details'];first,last=month_range(month)
        if period_plan is not None:
            if 'identity_intervals' in period_plan:
                matched=[value for value in period_plan['identity_intervals']
                    if value['profile_ref']=={key:profile[key] for key in ('id','revision','content_hash')}
                    and value['identity_ref']=={key:identity[key] for key in ('id','revision','content_hash')}]
                if not matched:raise Problem(409,'Der Zahlungsnachweis benötigt die im Gesamtfall belegte aktuelle Identitätsfassung.')
                first,last=day(matched[-1]['start']),day(matched[-1]['end'])
            else:
                periods=period_plan['employment_intervals']
                if len(periods)!=1 or period_plan['selected_identity_ref']!={key:identity[key] for key in ('id','revision','content_hash')}:
                    raise Problem(409,'Der Zahlungsnachweis benötigt die im Periodenplan belegte Identitätsfassung.')
                first,last=day(periods[0]['start']),day(periods[0]['end'])
        if (values['profile_id']!=profile['id'] or values['profile_revision']!=profile['revision']
                or values['valid_from']>first.isoformat() or values['valid_to']<last.isoformat()
                or values['employment_from']>first.isoformat()
                or values['employment_to'] and values['employment_to']<last.isoformat()):
            raise Problem(409,'Identitäts-/Steuernachweis deckt diese Profilrevision und den erforderlichen Beschäftigungszeitraum nicht ab.')
        return identity

    def _payment_fields(self,details,calculation,month,*,verified_composite=False,receipt_date=None,additional_net_indexes=()):
        payments=details['payments']
        actual_due=calculation['net_minor']-calculation.get('net_deductions_minor',0)
        # A private declaration tied to an actual verified zero-payable run is
        # evidence that no net transfer is due, never an invented cash payment.
        minimum=0 if verified_composite and actual_due==0 else 1
        if not isinstance(payments,list) or not minimum<=len(payments)<=20:
            raise Problem(400,'Ein bis zwanzig tatsächlich belegte Zahlungsteile angeben.')
        seen=set();total=0
        for payment in payments:
            _shape(payment,('paid_on','amount_minor','payment_reference'),('paid_on','amount_minor','payment_reference'))
            paid=day(payment['paid_on'])
            # This ledger only records the supported same-year regular 2026 case.
            if paid.year!=2026 or payment['paid_on'][:7]<month or payment['paid_on']>self.hr.now()[:10]:
                raise Problem(400,'Tatsächlicher Zahlungstag darf nicht zukünftig sein und muss im Abrechnungsmonat oder später im unterstützten Jahr 2026 liegen.')
            amount=payment['amount_minor']
            if type(amount) is not int or not -10**12<=amount<=10**12 or amount==0:
                raise Problem(400,'Tatsächlichen Zahlungsbetrag in ganzen Cent angeben; negative Beträge sind Arbeitnehmer-Nachzahlungen.')
            reference=text(payment['payment_reference'],'Zahlungsreferenz',200,required=True)
            if reference!=payment['payment_reference'] or _payment_key(payment) in seen:
                raise Problem(400,'Zahlungsreferenzen müssen eindeutig und ohne Rand-Leerzeichen sein.')
            seen.add(_payment_key(payment));total+=amount
        if total!=actual_due:
            raise Problem(400,'Die belegten Zahlungen abzüglich Arbeitnehmer-Nachzahlungen müssen dem tatsächlichen Auszahlungsnetto nach belegten Nettoabzügen entsprechen.')
        if calculation.get('travel_expenses_included_in_net') and any(payment['paid_on'][:7]!=month
                for index,payment in enumerate(payments) if index not in additional_net_indexes):
            raise Problem(409,'Reise-Mehrerstattungen müssen im tatsächlich gebundenen Zuflussmonat ausgezahlt werden; den Gesamtfall bei abweichender Zahlung korrigieren.')
        if receipt_date is not None and any(payment['paid_on']!=receipt_date for payment in payments):
            raise Problem(409,'Dieser Einmalfall benötigt sämtliche tatsächlich belegten Nettozahlungsteile am gebundenen Anspruchszuflusstag; unterschiedliche Zuflusstage benötigen eine gesonderte belegte Aufteilung.')
        _integer(details['tax_free_payments_minor'])
        text(details['tax_free_basis'],'Nachweis steuerfreier Bezüge',2000,required=details['tax_free_payments_minor']>0)
        if details['standard_case_confirmed'] is not True:
            raise Problem(400,'Ausschließlich die im geprüften Lauf belegten Entgelte und Nettoabzüge ohne weitere unberücksichtigte Sachverhalte bestätigen.')

    def _normalize(self,employee_id,kind,details,*,rule_version=None):
        fields=IDENTITY_FIELDS if kind=='identity' else PAYMENT_FIELDS if kind=='payment' else CARRY_FIELDS
        if not isinstance(details,dict):_shape(details,fields,fields)
        individual_identity=kind=='identity' and 'identity_source_schema_version' in details
        if individual_identity:
            fields+=('identity_source_schema_version',)
            if type(details['identity_source_schema_version']) is not int or details['identity_source_schema_version']!=2:
                raise Problem(400,'Individuelle Minijob-Identität benötigt ausdrücklich Quellenfassung 2.')
        if kind=='payment':
            _shape(details,PAYMENT_FIELDS+('payment_source_schema_version','settlement_allocations','prior_payment_ref'),PAYMENT_FIELDS)
            run=self.payroll._event(self.payroll._row(details['run_id'],'run',details['run_revision']))
            if run['source'].get('source_schema_version')==5:
                fields=PAYMENT_FIELDS+('payment_source_schema_version','settlement_allocations','prior_payment_ref')
                expected=(2,3) if 'settlement_transition' in run else (1,)
                if type(details.get('payment_source_schema_version')) is not int or details['payment_source_schema_version'] not in expected:
                    raise Problem(400,'Source5-Zahlungen benötigen die zum angenommenen Lauf gehörende ausdrückliche Zuordnungsfassung.')
        _shape(details,fields,fields)
        details=json.loads(canonical(details))
        if kind=='identity':
            profile=self._profile(employee_id,details)
            for field in ('given_name','family_name','address_line','city','employer_name','employer_address','employer_tax_number','religion_code'):
                details[field]=text(details[field],field,500,required=True)
            for field in ('date_of_birth','employment_from','tax_source_date','valid_from','valid_to'):
                day(details[field])
            if details['tax_source_date']>self.hr.now()[:10]:
                raise Problem(400,'Abruf-/Bescheinigungsdatum darf nicht in der Zukunft liegen.')
            if details['employment_to'] is not None:
                day(details['employment_to'])
            if (details['country_code']!='DE' or not isinstance(details['postal_code'],str)
                    or not re.fullmatch(r'\d{5}',details['postal_code']) or not isinstance(details['tax_id'],str)
                    or not re.fullmatch(r'[1-9]\d{10}',details['tax_id'])
                    or not re.fullmatch(r'[0-9 /]{10,30}',details['employer_tax_number'])):
                raise Problem(400,'Deutsche Anschrift, elfstellige Steuer-ID und belegte Arbeitgeber-Steuernummer angeben.')
            if (details['date_of_birth']!=profile['profile']['date_of_birth'] or details['valid_from']>details['valid_to']
                    or details['valid_from']<profile['profile']['effective_from']
                    or details['employment_to'] is not None and details['employment_from']>details['employment_to']):
                raise Problem(400,'Geburtsdatum oder Gültigkeits-/Beschäftigungszeitraum widerspricht dem Nachweis.')
            if details['tax_source'] not in ('elstam_imported','tax_office_certificate','flat_minijob_evidence'):
                raise Problem(400,'Tatsächliche Herkunft der Steuermerkmale angeben.')
            mini=profile['profile']['employment_kind']=='minijob'
            if individual_identity:
                p=profile['profile']
                if (not mini or p['minijob_tax']!='individual' or p['health_insurance']!='statutory_other'
                        or p['tax_class'] not in (1,5) or p['church_tax']!='none'
                        or details['tax_source']!='elstam_imported'):
                    raise Problem(400,'Diese neue Identitätsfassung gilt nur für den belegten individuellen gewerblichen GKV-Minijob mit Klasse I/V.')
            elif (details['tax_source']=='flat_minijob_evidence')!=mini:
                raise Problem(400,'Nachweisart und Beschäftigungsfall stimmen nicht überein.')
            for field in ('tax_allowance_yearly_minor','tax_addition_yearly_minor'):
                _integer(details[field])
            for monthly,yearly in (('tax_allowance_monthly_minor','tax_allowance_yearly_minor'),
                    ('tax_addition_monthly_minor','tax_addition_yearly_minor')):
                if (mini and details[yearly]!=0 or not mini and profile['profile'].get(monthly,0)>details[yearly]):
                    raise Problem(400,'Jahres- und Monatsbetrag der Steuermerkmale widersprechen sich.')
            if not mini and profile['profile']['tax_class']==6 and details['tax_addition_yearly_minor']:
                raise Problem(400,'Steuerklasse VI darf keinen Jahreshinzurechnungsbetrag enthalten.')
            if details['standard_case_confirmed'] is not True:
                raise Problem(400,'Unterstützten inländischen Standardfall ausdrücklich bestätigen.')
            if (not mini or individual_identity) and (profile['profile']['church_tax']=='none')!=(details['religion_code']=='none'):
                raise Problem(400,'Religionsmerkmal und Steuerprofil widersprechen sich.')
            return details,dict(profile=profile),kind+':'+profile['id']+':'+str(profile['revision'])
        if kind=='payment':
            record=self.payroll._event(self.payroll._row(details['run_id'],'run',details['run_revision']))
            if record['employee_id']!=employee_id:
                raise Problem(404,'Abrechnung gehört nicht zu diesem Mitarbeiter.')
            if not record['calculation']['payroll_calculation_complete']:
                raise Problem(409,'Ein unvollständiger SV-Lauf kann kein vollständiger Lohnkontoeintrag werden.')
            source_version=record['source'].get('source_schema_version')
            if source_version in (3,4,5):self.payroll._verify_calculation_record(record)
            period_plan=(record['source']['calculation_case']['plan'] if source_version in (3,4,5) else
                record['source']['period_case']['plan'] if source_version==2 else None)
            identity=self._identity(employee_id,details,record['source']['profile'],record['source']['month'],period_plan=period_plan)
            sources=dict(run=record,identity=identity)
            if source_version==5:
                if details['payment_source_schema_version'] in (2,3):
                    from payroll_multiple_corrections import resolve_positive_payment_plan
                    sources['single_payment_plan']=resolve_positive_payment_plan(self,record,details)
                else:
                    from payroll_multiple_payments import resolve_single_payment_plan
                    sources['single_payment_plan']=resolve_single_payment_plan(self,record,details)
            # Only an independently resolved V3 positive bonus difference may
            # have a later cash month. The full old transfer/allocation prefix,
            # including every original travel amount/date, is already sealed.
            # Other payroll/travel contracts retain their original date guard.
            additional=(tuple(a['payment_index'] for a in sources['single_payment_plan']['allocations']
                if a['running_minor']==0)
                if source_version==5 and details['payment_source_schema_version']==3 else ())
            self._payment_fields(details,record['calculation'],record['source']['month'],verified_composite=source_version in (3,4,5),
                receipt_date=record['calculation']['one_off_details']['receipt_date'] if source_version==4 else None,
                additional_net_indexes=additional)
            if source_version in (3,4,5):
                sources['identity_intervals']=[]
                for period in period_plan['identity_intervals']:
                    ref=period['identity_ref'];original=self._get(ref['id'],ref['revision'])
                    if original['employee_id']!=employee_id or {key:original[key] for key in ('id','revision','content_hash')}!=ref:
                        raise Problem(409,'Eine tatsächliche Identitätsfassung der Beschäftigungsabschnitte wurde verändert.')
                    sources['identity_intervals'].append(dict(start=period['start'],end=period['end'],profile_ref=period['profile_ref'],identity=original))
            return details,sources,kind+':'+record['id']+':'+str(record['revision'])
        month_range(details['month'])
        if details['month'][:4]!='2026' or details['status'] not in ('active','void'):
            raise Problem(400,'Belegter Monatsvortrag muss zum unterstützten Jahr 2026 gehören.')
        profile=self._profile(employee_id,details)
        calculation=calculate(profile['profile'],details['month'],details['gross_minor'],full_month_confirmed=True,rule_version=rule_version)
        calculation['travel_expenses_included_in_net']=False
        if not calculation['payroll_calculation_complete']:
            raise Problem(400,'Monatsvortrag liegt außerhalb des vollständig unterstützten Rechenumfangs.')
        for field,result in (('expected_net_minor','net_minor'),('expected_employee_tax_minor','employee_tax_minor'),
                ('expected_employee_social_total_minor','employee_social_total_minor'),('expected_employer_social_total_minor','employer_social_total_minor'),
                ('expected_employer_total_minor','employer_total_excluding_accident_insurance_minor')):
            value=details[field]
            if type(value) is not int or value!=calculation[result]:
                raise Problem(400,'Belegter Vortragsbetrag '+field+' stimmt nicht mit der geprüften Standardberechnung überein.')
        identity=self._identity(employee_id,details,profile,details['month'])
        self._payment_fields(details,calculation,details['month'])
        return details,dict(profile=profile,identity=identity,calculation=calculation),kind+':'+details['month']

    def save(self,actor,data):
        fields=('request_id','employee_id','kind','id','revision','source_file_id','confirmed','correction_reason','details')
        _shape(data,fields,tuple(key for key in fields if key not in ('id','correction_reason')))
        identifier(data['request_id'])
        if data['kind'] not in ('identity','payment','carryover') or data['confirmed'] is not True:
            raise Problem(400,'Lohnkontonachweisart und ausdrückliche Bestätigung erforderlich.')
        with transaction(self.office):
            permission='personnel.write' if data['kind']=='identity' else 'personnel.approve'
            fresh,employee=self.hr._employee(actor,data['employee_id'],permission=permission)
            self.hr._employee(fresh,employee['id'])
            self.payroll._gate(fresh)
            from business_schema import require_capability
            require_capability(self.office,'business_payroll_accounts')
            fingerprint=_sha(data)
            prior=self.db.execute('SELECT * FROM business_payroll_account_requests WHERE user_id=? AND request_id=?',(fresh['id'],data['request_id'])).fetchone()
            if prior:
                if prior['request_hash']!=fingerprint:
                    raise Problem(409,'Vorgangs-ID wurde mit anderem Inhalt verwendet.')
                result=json.loads(prior['result_json']);self._verify_source5(result)
                return result
            try:
                previous=self._get(data['id']) if data.get('id') else None
                if previous and (previous['employee_id']!=employee['id'] or previous['kind']!=data['kind']):
                    raise Problem(404,'Korrektur gehört nicht zu diesem Lohnkontonachweis.')
                if previous and data['kind']=='payment':
                    from payroll_multiple_corrections import require_unbound_payment_revision
                    require_unbound_payment_revision(self,previous)
                if _integer(data['revision'])!=(previous['revision'] if previous else 0):
                    raise Problem(409,'Lohnkontonachweis wurde geändert. Neu laden.')
                reason=text(data.get('correction_reason',''),'Korrekturgrund',2000,required=bool(previous))
                original=self.hr._file(data['source_file_id'],employee['id'])
                if original['purpose']!='personnel':
                    raise Problem(400,'Geschützter Personalakten-Originalnachweis erforderlich.')
                details,sources,key=self._normalize(employee['id'],data['kind'],data['details'])
                if data['kind']=='payment' and sources['run']['source'].get('source_schema_version')==5:
                    if details['payment_source_schema_version'] in (2,3):
                        from payroll_multiple_corrections import require_current_positive_settlement
                        require_current_positive_settlement(self,sources['run'],details)
                    else:
                        from payroll_multiple_payments import require_current_prior_settlement
                        require_current_prior_settlement(self,sources['run'],details)
                if data['kind']=='payment' and sources['run']['source'].get('source_schema_version') in (4,5):
                    from payroll_cash_sources import require_preserved_actual_net_parts
                    require_preserved_actual_net_parts(self.office,employee['id'],sources['run']['source']['month'],details['payments'])
                existing=self.db.execute('SELECT id FROM business_payroll_account_events WHERE employee_id=? AND identity_key=?',(employee['id'],key)).fetchone()
                if existing and (not previous or previous['id']!=existing['id']):
                    raise Problem(409,'Für diese Quelle besteht bereits ein Nachweis. Begründete Korrekturversion anlegen.')
                if previous:
                    oldkey=self.db.execute('SELECT identity_key FROM business_payroll_account_events WHERE id=? AND revision=1',(previous['id'],)).fetchone()['identity_key']
                    if oldkey!=key:
                        raise Problem(400,'Quelle/Monat eines bestehenden Nachweises darf nicht gewechselt werden.')
                if data['kind']=='carryover' and details['status']=='active':
                    if any(run['source']['month']==details['month'] for run in self.payroll._all('run',employee['id'])):
                        raise Problem(409,'Für diesen Monat besteht eine lokale Abrechnung; Vortrag würde doppelt zählen.')
                if data['kind'] in ('payment','carryover'):
                    effective={run['id']:run['revision'] for run in self.payroll._all('run',employee['id'])}
                    def active(kind_,details_):
                        return details_['status']=='active' if kind_=='carryover' else effective.get(details_['run_id'])==details_['run_revision']
                    def references(details_):
                        return {_payment_key(item) for item in details_['payments']}
                    if active(data['kind'],details):
                        used=references(details)
                        for other in self._all(employee['id']):
                            if other['kind'] in ('payment','carryover') and (not previous or other['id']!=previous['id']) and active(other['kind'],other['details']):
                                if used.intersection(references(other['details'])):
                                    raise Problem(409,'Eine Zahlungsreferenz ist bereits einem anderen wirksamen Monat zugeordnet.')
                object_id=previous['id'] if previous else uuid.uuid4().hex
                payload=dict(details=details,sources=sources,source_file={k:original[k] for k in ('id','employee_id','sha256','content_hash')},confirmed=True,correction_reason=reason)
                envelope=dict(id=object_id,revision=(previous['revision']+1 if previous else 1),kind=data['kind'],employee_id=employee['id'],
                    identity_key=None if previous else key,previous_hash=previous['content_hash'] if previous else None,
                    created_by=fresh['id'],created_at=self.hr.now(),payload=payload)
                self.db.execute('INSERT INTO business_payroll_account_events(id,revision,kind,employee_id,identity_key,payload_json,content_hash,previous_hash,created_by,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)',
                    (object_id,envelope['revision'],data['kind'],employee['id'],envelope['identity_key'],canonical(payload),_sha(envelope),envelope['previous_hash'],fresh['id'],envelope['created_at']))
                result=self._get(object_id)
                self.db.execute('INSERT INTO business_payroll_account_requests(user_id,request_id,request_hash,result_json) VALUES(?,?,?,?)',
                    (fresh['id'],data['request_id'],fingerprint,canonical(result)))
                self.office.audit(fresh,'payroll.account.'+data['kind'],object_id)
                return result
            except Problem as error:
                if error.status==409:
                    raise Problem(409,error.message,request_resolution='not_accepted') from None
                raise


def available(office):
    from business_schema import _tables
    return set(TABLES).issubset(_tables(office))


def require_no_carryover(office,employee_id,month):
    if available(office) and any(record['kind']=='carryover' and record['details']['month']==month
            and record['details']['status']=='active' for record in PayrollAccounts(office)._all(employee_id)):
        raise Problem(409,'Ein aktiver Monatsvortrag besteht. Erst ausdrücklich mit Begründung aufheben, bevor eine lokale Abrechnung ihn ersetzt.')


def validate_integrity(office):
    from business_schema import _tables
    present=set(TABLES).intersection(_tables(office))
    if not present:
        return True
    if present!=set(TABLES):
        raise ValueError('Incomplete payroll account schema')
    api=PayrollAccounts(office);previous={};identities={}
    try:
        for row in office.db.execute('SELECT * FROM business_payroll_account_events ORDER BY id,revision').fetchall():
            record=api._event(row);prior=previous.get(record['id'])
            api._verify_source5(record)
            if record['revision']!=(prior['revision']+1 if prior else 1) or record['previous_hash']!=(prior['content_hash'] if prior else None):
                raise ValueError('Broken payroll account history')
            version=record['sources']['calculation']['rule_version'] if record['kind']=='carryover' else None
            details,sources,key=api._normalize(record['employee_id'],record['kind'],record['details'],rule_version=version)
            if (details!=record['details'] or sources!=record['sources'] or record['confirmed'] is not True
                    or row['identity_key']!=(None if prior else key) or prior and not record['correction_reason']):
                raise ValueError('Changed payroll account evidence')
            if prior and (record['kind']!=prior['kind'] or record['employee_id']!=prior['employee_id'] or identities[record['id']]!=key):
                raise ValueError('Changed payroll account identity')
            identities[record['id']]=key
            original=api.hr._file(record['source_file']['id'],record['employee_id'])
            if original['purpose']!='personnel' or any(original[k]!=record['source_file'][k] for k in ('id','employee_id','sha256','content_hash')):
                raise ValueError('Changed payroll account original')
            previous[record['id']]=record
        for record in previous.values():
            if record['kind']=='carryover' and record['details']['status']=='active' and any(
                    run['source']['month']==record['details']['month'] for run in api.payroll._all('run',record['employee_id'])):
                raise ValueError('Payroll run overlaps active carryover')
        settlements=set()
        for record in previous.values():
            if record['kind'] not in ('payment','carryover'):
                continue
            details=record['details']
            active=details['status']=='active' if record['kind']=='carryover' else api.payroll._latest(details['run_id'],'run')['revision']==details['run_revision']
            if active:
                for payment in details['payments']:
                    key=(record['employee_id'],*_payment_key(payment))
                    if key in settlements:
                        raise ValueError('Payroll payment reused in effective months')
                    settlements.add(key)
        for row in office.db.execute('SELECT * FROM business_payroll_account_requests').fetchall():
            identifier(row['request_id']);result=json.loads(row['result_json'])
            if not re.fullmatch(r'[a-f0-9]{64}',row['request_hash']) or api._get(result['id'],result['revision'])!=result:
                raise ValueError('Changed payroll account receipt')
    except (Problem,KeyError,TypeError,json.JSONDecodeError) as error:
        raise ValueError('Invalid payroll account archive') from error
    return True


def methods(path):
    if path=='/payroll/account-records':
        return 'GET, POST'
    if re.fullmatch(r'/payroll/account-records/'+ID+r'(?:/history)?',path):
        return 'GET'
    return None


def dispatch(office,actor,path,method,data):
    allowed=methods(path)
    if allowed is None:
        return None
    if method not in allowed.split(', '):
        raise Problem(405,'HTTP-Methode nicht erlaubt.')
    api=PayrollAccounts(office)
    if method=='POST':
        return api.save(actor,data),200,'application/json'
    _shape(data,('_query',));query=data.get('_query',{})
    if path=='/payroll/account-records':
        result=api.records(actor,query)
    else:
        _shape(query,())
        result=api.get(actor,path.split('/')[3],path.endswith('/history'))
    return result,200,'application/json'

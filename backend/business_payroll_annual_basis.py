"""Private append-only annual payroll evidence for the future v6 composition.

Internal periods are reconstructed from actual accepted runs; external periods
retain their protected originals and explicit tax/SV provenance. All new uses
check current source revisions. Original accepted commands remain private.
"""
import calendar
from contextvars import ContextVar
from datetime import date,timedelta
from functools import wraps
import json
import re
import uuid

from core import Problem,canonical
from business_operations import identifier,text,transaction
from business_personnel_workflow import _integer,_sha,_shape
from business_payroll_facts import PayrollFacts,reference,ref,file_ids,employee_view,EMPLOYEE_FIELDS
from payroll_annual_basis_2026 import (ANNUAL_BASIS_VERSION,KINDS,normalize_details,
    build_annual_plan as build_annual_plan_v1,employer_key,dates,running_tax_year)
from payroll_oneoff_2026 import BRANCHES,annual_social_room

FEATURES=('payroll_annual_basis',)
TABLES=('business_payroll_annual_events','business_payroll_annual_requests')
ID=r'[a-f0-9]{32}'


def build_annual_plan(snapshot,*,rule_version=None):
    if 'annual_source_contract' in snapshot:
        from payroll_factor_annual_basis_2026 import build_plan,RULE_VERSION
        return build_plan(snapshot,rule_version=RULE_VERSION if rule_version is None else rule_version)
    if 'annual_source_contract' in snapshot.get('annual_basis',{}).get('sources',{}):
        raise Problem(409,'Die V2-Jahresbasis benötigt ihre ausdrücklich versionierte Jahressteuerprognose.')
    return build_annual_plan_v1(snapshot,rule_version=ANNUAL_BASIS_VERSION if rule_version is None else rule_version)


def _source_api(office,sources,*,clock=None):
    if 'annual_source_contract' in sources:
        from business_payroll_factor_annual_basis import FactorAnnualBasis
        return FactorAnnualBasis(office,clock=clock)
    return PayrollAnnualBasis(office,clock=clock)
_CHECKS=ContextVar('payroll_annual_original_checks',default=None)


def _original_check_scope(function):
    """Deduplicate successful graph checks only within this read operation.

    The next request always starts empty, including after a changed original
    or missing receipt. Freshness checks are never cached. Context isolation
    also keeps concurrent PostgreSQL writers from sharing successful checks.
    """
    @wraps(function)
    def checked(*args,**kwargs):
        if _CHECKS.get() is not None:return function(*args,**kwargs)
        token=_CHECKS.set(set())
        try:return function(*args,**kwargs)
        finally:_CHECKS.reset(token)
    return checked


def schema_statements(binary_type='BYTEA'):
    if binary_type not in ('BYTEA','BLOB'):raise ValueError('Unsupported annual payroll storage')
    return [
        '''CREATE TABLE IF NOT EXISTS business_payroll_annual_events(
        id TEXT NOT NULL,revision INTEGER NOT NULL CHECK(revision>0),employee_id TEXT NOT NULL REFERENCES business_employees(id),
        kind TEXT NOT NULL CHECK(kind IN ('imported_period','imported_one_off','annual_basis','one_off_earning','annual_tax_forecast')),
        effective_from TEXT NOT NULL,effective_to TEXT NOT NULL,status TEXT NOT NULL CHECK(status IN ('active','void')),
        payload_json TEXT NOT NULL,sources_json TEXT NOT NULL,source_hash TEXT NOT NULL,previous_hash TEXT,content_hash TEXT NOT NULL,
        created_by TEXT NOT NULL REFERENCES users(id),created_at TEXT NOT NULL,identity_key TEXT,command_hash TEXT NOT NULL,
        PRIMARY KEY(id,revision),UNIQUE(employee_id,identity_key))''',
        '''CREATE TABLE IF NOT EXISTS business_payroll_annual_requests(
        user_id TEXT NOT NULL REFERENCES users(id),request_id TEXT NOT NULL,operation TEXT NOT NULL,request_hash TEXT NOT NULL,
        fact_id TEXT NOT NULL,fact_revision INTEGER NOT NULL,fact_content_hash TEXT NOT NULL,created_at TEXT NOT NULL,
        PRIMARY KEY(user_id,request_id),FOREIGN KEY(fact_id,fact_revision) REFERENCES business_payroll_annual_events(id,revision))''',
        'CREATE INDEX IF NOT EXISTS business_payroll_annual_employee ON business_payroll_annual_events(employee_id,kind,id,revision)',
    ]


def protected_tables():return TABLES
def runtime_privileges():return {name:('SELECT','INSERT') for name in TABLES}


def guard_statements(dialect):
    from business_payroll_facts import guard_statements as guards
    return [value.replace('business_payroll_fact','business_payroll_annual').replace('immutable payroll fact','immutable payroll annual fact') for value in guards(dialect)]


def effective(kind,d):
    if kind=='imported_period':return d['period_start'],d['period_end']
    if kind=='imported_one_off':return d['receipt_date'],d['receipt_date']
    if kind=='annual_basis':return f"{d['year']}-01-01",d['coverage_to']
    return (d['planned_receipt_date'],)*2 if kind=='one_off_earning' else (d['receipt_date'],)*2


def identity_key(kind,d):
    if kind=='imported_period':key=[d['period_start'],d['period_end'],d['original_payroll_reference'],d['section_key']]
    elif kind=='imported_one_off':key=[d['original_reference'],d['receipt_date']]
    elif kind=='annual_basis':key=[d['year'],d['coverage_to'],d['as_of_date']]
    elif kind=='one_off_earning':key=[d['claim_key']['id'],d['claim_reference']]
    else:key=[d['current_one_off_ref']['id']]
    return kind+':'+_sha(key)


def _document_refs(value):
    result=[]
    if isinstance(value,dict):
        for key,item in value.items():
            if key in ('evidence_ref','claim_key','no_previous_employer_ref') and item is not None:result.append(item)
            elif key=='document_refs':result.extend(item)
            else:result.extend(_document_refs(item))
    elif isinstance(value,list):
        for item in value:result.extend(_document_refs(item))
    return result


class PayrollAnnualBasis:
    def __init__(self,office,*,clock=None):
        self.office,self.db=office,office.db
        self.facts=PayrollFacts(office,clock=clock);self.hr=self.facts.hr

    @staticmethod
    def _operation(kind):
        return 'annual.saved:'+kind

    def _check_current_case(self,employee,candidate,*,fresh):
        from business_payroll_calculation_cases import PayrollCalculationCases,validate_case_sources
        api=PayrollCalculationCases(self.office,clock=self.hr.clock)
        validate_case_sources(self.office,candidate)
        if fresh and (reference(api._get(candidate['id']))!=reference(candidate) or api._snapshot(employee,'calculation_case',candidate['details'],candidate['source_file_ids'],
                planned_on=candidate['sources']['flat_travel_tax']['recording_context']['planned_recording_on'] if candidate['sources']['flat_travel_tax'] else None,
                rule_version=candidate['rule_version'],source_contract_version=candidate['source_contract_version'])!=candidate['sources']):
            raise Problem(409,'Aktuelle laufende Monatsquelle wurde geändert.')

    def _planned_calculation(self,employee,candidate,*,fresh):
        from payroll_calculations_2026 import CALCULATION_RULE_VERSION,SOURCE_CONTRACT_VERSION,calculate_calculation_source
        if candidate['rule_version']!=CALCULATION_RULE_VERSION or candidate['source_contract_version']!=SOURCE_CONTRACT_VERSION:
            raise Problem(409,'Dieser noch nicht abgeschlossene Monatsfall benötigt seinen eigenen Jahresvorschauvertrag; zuerst den verifizierten Monatslauf abschließen.')
        self._check_current_case(employee,candidate,fresh=fresh)
        return calculate_calculation_source(candidate['sources'],rule_version=candidate['rule_version'],source_contract_version=candidate['source_contract_version'])

    def _access(self,actor,employee_id,permission='personnel.read'):
        return self.facts._access(actor,employee_id,permission)

    def _gate(self,actor,*,new=True):
        from business_schema import require_capability
        from business_organization import require_active
        require_capability(self.office,'business_payroll_annual_basis')
        if new:require_active(self.office,actor,'/payroll','business_payroll')

    def _row(self,object_id,revision=None):
        identifier(object_id)
        if revision is None:row=self.db.execute('SELECT * FROM business_payroll_annual_events WHERE id=? ORDER BY revision DESC LIMIT 1',(object_id,)).fetchone()
        else:
            _integer(revision,1);row=self.db.execute('SELECT * FROM business_payroll_annual_events WHERE id=? AND revision=?',(object_id,revision)).fetchone()
        if row is None:raise Problem(404,'Jahresquellenfassung nicht verfügbar.')
        return row

    def _event(self,row):
        payload=json.loads(row['payload_json']);sources=json.loads(row['sources_json'])
        envelope={key:row[key] for key in row.keys() if key not in ('payload_json','sources_json','content_hash')}
        envelope.update(payload=payload,sources=sources)
        if _sha(envelope)!=row['content_hash'] or _sha(sources)!=row['source_hash']:raise Problem(500,'Integrität der Jahresquellenhistorie verletzt.')
        payload.pop('accepted_command',None)
        return dict(**{key:row[key] for key in ('id','revision','employee_id','kind','effective_from','effective_to','status','source_hash','previous_hash','content_hash','created_by','created_at')},**payload,sources=sources)

    def _get(self,object_id,revision=None):return self._event(self._row(object_id,revision))

    def _all(self,employee_id,kind=None):
        rows=self.db.execute('SELECT e.* FROM business_payroll_annual_events e WHERE e.employee_id=? AND NOT EXISTS '
            '(SELECT 1 FROM business_payroll_annual_events n WHERE n.id=e.id AND n.revision>e.revision) ORDER BY e.created_at,e.id',(employee_id,)).fetchall()
        return [self._event(row) for row in rows if kind is None or row['kind']==kind]

    def records(self,actor,query):
        _shape(query,('employee_id','kind'),('employee_id',))
        if query.get('kind') is not None and query['kind'] not in KINDS:raise Problem(400,'Unbekannte Jahresquellenart.')
        with transaction(self.office):
            fresh,employee=self._access(actor,query['employee_id'])
            return dict(employee_id=employee['id'],items=self._all(employee['id'],query.get('kind')),**self.facts._capabilities(fresh))

    def get(self,actor,object_id,history=False):
        with transaction(self.office):
            row=self._row(object_id);self._access(actor,row['employee_id'])
            if history:return dict(employee_id=row['employee_id'],items=[self._event(item) for item in self.db.execute('SELECT * FROM business_payroll_annual_events WHERE id=? ORDER BY revision',(object_id,))])
            return self._event(row)

    def sources(self,actor,query):
        _shape(query,('employee_id',),('employee_id',))
        from business_payroll import Payroll
        from business_payroll_accounts import PayrollAccounts
        from business_payroll_calculation_cases import PayrollCalculationCases
        from payroll_calculations_2026 import CALCULATION_RULE_VERSION,SOURCE_CONTRACT_VERSION
        with transaction(self.office):
            result=self.facts.sources(actor,query)
            result.update(annual_facts=self._all(result['employee_id']),payroll_runs=Payroll(self.office)._all('run',result['employee_id']),
                payroll_payments=[item for item in PayrollAccounts(self.office)._all(result['employee_id']) if item['kind']=='payment'],
                calculation_cases=[item for item in PayrollCalculationCases(self.office)._all(result['employee_id'],'calculation_case')
                    if item['rule_version']==CALCULATION_RULE_VERSION and item['source_contract_version']==SOURCE_CONTRACT_VERSION])
            return result

    def _reference(self,employee_id,value,kind=None,*,fresh,current_one_off_id=None):
        value=ref(value);result=self._get(value['id'],value['revision'])
        if result['employee_id']!=employee_id or kind is not None and result['kind']!=kind:raise Problem(404,'Jahresquelle gehört nicht zu diesem Mitarbeiter oder Quellentyp.')
        if result['status']!='active' or reference(result)!=value or fresh and reference(self._get(value['id']))!=value:raise Problem(409,'Jahresquelle wurde korrigiert oder archiviert.')
        validate_annual_sources(self.office,result)
        if fresh:
            self.facts._files(employee_id,result['source_file_ids'],fresh=True)
            # Re-resolve dependencies with the original accepted employee view;
            # current top-level employee revision is checked at the caller.
            if _source_api(self.office,result['sources'],clock=self.hr.clock)._snapshot(result['sources']['employee'],result['kind'],result['details'],result['source_file_ids'],
                    fresh=True,current_one_off_id=current_one_off_id)!=result['sources']:
                raise Problem(409,'Jahresquelle entspricht nicht mehr ihren vollständigen aktuellen Originalen.')
        return result

    def _run(self,employee_id,value,*,fresh):
        from business_payroll import Payroll,calculation_matches_source
        api=Payroll(self.office);value=ref(value);run=api._event(api._row(value['id'],'run',value['revision']))
        if run['employee_id']!=employee_id:raise Problem(404,'Lohnperiode gehört nicht zu diesem Mitarbeiter.')
        if reference(run)!=value or fresh and reference(api._latest(value['id'],'run'))!=value:raise Problem(409,'Die wirksame Lohnperiode wurde geändert.')
        if not run['calculation']['payroll_calculation_complete']:raise Problem(409,'Unvollständige Lohnperiode ist kein Jahresvortrag.')
        if run['source'].get('source_schema_version') in (3,4,5):api._verify_calculation_record(run)
        else:
            from business_payroll import validate_integrity as validate_payroll_integrity
            validate_payroll_integrity(self.office)
            if not calculation_matches_source(run['source'],run['calculation']):raise Problem(500,'Historische Lohnperiode ist nicht unverändert nachrechenbar.')
        return run

    def _project_run(self,run,*,candidate=False,as_of_date,payment=None,basis_year=None,coverage_to=None):
        """Project verified original running wages and actual separate v6 receipts."""
        from business_payroll_accounts import PayrollAccounts
        source,calc=run['source'],run['calculation'];month=source['month'];year=int(month[:4])
        composite=source.get('source_schema_version') in (4,5)
        original_calc=calc
        if composite:calc=calc['running_calculation']
        basis_year=year if basis_year is None else basis_year
        first=month+'-01';last=month+f'-{calendar.monthrange(year,int(month[5:]))[1]:02}'
        period_details=calc.get('period_details');run_ref=reference(run);periods=[]
        if source.get('source_schema_version') in (3,4,5):
            snapshot=source['calculation_case']['sources']
            profiles={canonical(reference(item)):item['profile'] for item in snapshot['profiles']}
            assessments=period_details['social_assessments']
            all_periods=[(item['period'],profiles[canonical(item['period']['profile_ref'])],item['branch_bases']) for item in assessments]
        elif source.get('source_schema_version')==2:
            profile=source['profile']['profile'];period=period_details['social_periods'][0]
            all_periods=[(period,profile,period_details.get('branch_bases',{}))]
        else:
            profile=source['profile']['profile'];basis=calc.get('transition',{}).get('branch_bases',{})
            all_periods=[(dict(start=first,end=last,gross_minor=calc['gross_minor']),profile,basis)]
        for index,(period,p,bases) in enumerate(all_periods):
            branches={};mini=p['employment_kind']=='minijob';amount=period['gross_minor']
            for branch in BRANCHES:
                active=branch not in ('care','unemployment') if mini else True
                if branch in ('health','care') and p['health_insurance']=='private':active=False
                if not active:contributed=0
                elif bases:
                    key='health_general' if branch=='health' else branch
                    contributed=bases[key]['total_minor']
                else:
                    cap=period.get('caps',{}).get('health_minor' if branch in ('health','care') else 'pension_minor')
                    if cap is None:
                        from payroll_oneoff_2026 import YEAR_RULES
                        cap=YEAR_RULES[year]['health_cap_minor' if branch in ('health','care') else 'pension_cap_minor']//12
                    contributed=min(amount,cap)
                intervals=[]
                if active:
                    reasons={value['date']:value for value in (period_details or {}).get('social_continuation',[])}
                    groups=[]
                    for day in dates(period['start'],period['end']):
                        reason='continued_section_7_3' if day in reasons else 'paid_employment'
                        if groups and groups[-1]['legal_reason']==reason:groups[-1]['end']=day
                        else:groups.append(dict(start=day,end=day,legal_reason=reason,source_ref=run_ref))
                    intervals=groups
                branches[branch]=dict(eligible_intervals=intervals,contributed_minor=contributed)
            periods.append(dict(source_ref=run_ref,part_key='social:'+str(index),section_key='minijob' if mini else 'regular',
                start=period['start'],end=period['end'],branches=branches))
        from payroll_individual_minijob_2026 import RULE_VERSION as INDIVIDUAL_MINIJOB_RULE
        individually_taxed_minijob=calc['rule_version']==INDIVIDUAL_MINIJOB_RULE
        taxable=(sum(item['gross_minor'] for item in period_details['tax_periods']) if period_details else calc['gross_minor']) if individually_taxed_minijob or not all(p['employment_kind']=='minijob' for _,p,_ in all_periods) else 0
        if payment is not None:
            # The exact accepted payment ref is part of the annual command.
            # Later payments must never rewrite an earlier historical snapshot.
            accounts=PayrollAccounts(self.office)
            accounts._verify_source5(payment)
            normalized,sources,_=accounts._normalize(run['employee_id'],'payment',payment['details'])
            if normalized!=payment['details'] or sources!=payment['sources']:raise Problem(500,'Zahlungsquelle der Jahresperiode ist nicht kanonisch.')
        running_payments=payment['details']['payments'] if payment else []
        if source.get('source_schema_version')==5 and payment:
            running_payments=[payment['details']['payments'][item['payment_index']] for item in payment['details']['settlement_allocations'] if item['running_minor']>0]
        if candidate:status='planned_current_period'
        elif taxable==0:status='not_individually_taxable'
        elif payment and all(value['paid_on']<=as_of_date and running_tax_year(last,value['paid_on'])==year for value in running_payments):status='received_same_year'
        else:status='unproven'
        projection=dict(source_ref=run_ref,coverage_start=first,coverage_end=last,periods=periods,
            running_taxable_minor=taxable if status!='unproven' else 0,tax_receipt_status=status,payment_evidence=payment)
        if composite:
            extra=(original_calc['multiple_one_off_details']['single_original_calculation']['one_off_details'] if source.get('source_schema_version')==5 else original_calc['one_off_details'])
            assignment=extra['assignment']
            bonus_payments=payment['details']['payments'] if payment else []
            if source.get('source_schema_version')==5 and payment:
                bonus_payments=[payment['details']['payments'][item['payment_index']] for item in payment['details']['settlement_allocations'] if item['one_off_allocations']]
            actual_adjustment=(source.get('source_schema_version')==5 and payment
                and payment['details'].get('payment_source_schema_version') in (3,4,5))
            # V3/V4/V5 already resolve every immutable predecessor and the same
            # original gross event above. A later pure net adjustment is not
            # a new gross receipt. Retain the actual original bonus-day proof
            # and require all later money facts by the requested cutoff.
            original_receipt=(any(part['paid_on']==extra['receipt_date'] and part['amount_minor']>0
                for part in bonus_payments) if actual_adjustment else True)
            if not payment or not bonus_payments or not original_receipt or any(
                    (not actual_adjustment and part['paid_on']!=extra['receipt_date']) or part['paid_on']>as_of_date
                    for part in bonus_payments):
                raise Problem(409,'Ein früherer interner Einmalbezug benötigt seinen tatsächlichen vollständig gebundenen Zufluss bis zum Jahresstichtag.')
            projected_ref=run_ref if assignment['assigned_period_ref']==reference(source['calculation_case']) else assignment['assigned_period_ref']
            projection['one_off_payment']=dict(source_ref=run_ref,payment_ref=reference(payment),
                receipt_date=extra['receipt_date'],tax_year=assignment['tax_year'],social_year=assignment['social_year'],
                amount_minor=extra['amount_minor'],section_key=(source['multiple_one_off_case']['sources']['calculation_source']['components'][0]['earning']['details']['section_key'] if source.get('source_schema_version')==5 else source['one_off_case']['sources']['calculation_source']['one_off_earning']['details']['section_key']),
                assigned_period_ref=projected_ref,assigned_part_key=extra['assigned_part_key'],
                assigned_period_end=assignment['assigned_period_end'],bases_minor=assignment['bases_minor'])
            projection['assignment_profiles']=[dict(part_key='social:'+str(index),start=value['period']['start'],end=value['period']['end'],
                profile_ref=value['period']['profile_ref'],profile=profiles[canonical(value['period']['profile_ref'])]) for index,value in enumerate(assessments)]
            # The exact originals are read and verified above; store their small
            # reference projections to avoid recursively copying all prior years.
            projection['payment_evidence']=self._compact_payment(payment)
            if basis_year!=year or coverage_to is not None and last>coverage_to:
                projection.update(coverage_start=None,coverage_end=None,periods=[],running_taxable_minor=0,
                    tax_receipt_status='outside_running_year',assignment_profiles=[])
        return projection

    @staticmethod
    def _compact_payment(payment):
        return {key:payment[key] for key in ('id','revision','content_hash','kind','employee_id','details','source_file','created_at')}

    @staticmethod
    def _compact_run(run):
        version=run['source'].get('source_schema_version')
        if version not in (4,5):return run
        return dict(reference(run),kind='run',employee_id=run['employee_id'],
            source=dict(source_schema_version=version,month=run['source']['month']),projection_format='source'+str(version)+'_annual_reference_v1')

    @staticmethod
    def _relevant_run(run,details,candidate,current_one_off_id=None):
        month=run['source']['month']
        # A correction replaces this exact bound claim, including its previous-
        # year March-clause assignment. Other accepted claims remain mandatory.
        if (current_one_off_id is not None and run['source'].get('source_schema_version')==4
                and run['source']['one_off_case']['details']['one_off_earning_ref']['id']==current_one_off_id):return False
        if (current_one_off_id is not None and run['source'].get('source_schema_version')==5
                and any(part['component_key']==current_one_off_id for part in run['source']['multiple_one_off_case']['details']['components'])):return False
        if candidate is not None and month==candidate['details']['month']:return False
        if month.startswith(str(details['year'])+'-') and month<=details['coverage_to'][:7]:return True
        extra=(run['calculation'].get('one_off_details') or run['calculation'].get('multiple_one_off_details',{}).get('single_original_calculation',{}).get('one_off_details'))
        return bool(extra and extra['assignment']['social_year']==details['year']
            and extra['assignment']['assigned_period_end']<=details['coverage_to'] and extra['receipt_date']<=details['as_of_date'])

    @_original_check_scope
    def _snapshot(self,employee,kind,d,ids,*,fresh=True,current_one_off_id=None):
        employee_id=employee['id'];files=self.facts._files(employee_id,ids,fresh=fresh)
        file_refs={item['id']:dict(id=item['id'],revision=1,content_hash=item['content_hash']) for item in files}
        if any(file_refs.get(value['id'])!=value for value in _document_refs(d)):raise Problem(409,'Jede strukturierte Jahresangabe muss ihre exakte geschützte Originalfassung derselben Person binden.')
        identity=self.facts._identity_ref(employee_id,d['employer_identity_ref'],fresh=fresh)
        from business_payroll_accounts import PayrollAccounts
        normalized_identity,identity_sources,_=PayrollAccounts(self.office)._normalize(employee_id,'identity',identity['details'])
        if normalized_identity!=identity['details'] or identity_sources!=identity['sources']:raise Problem(500,'Arbeitgeberidentität ist nicht aus ihrem tatsächlichen Lohnprofil rekonstruierbar.')
        snapshot=dict(schema_version=1,kind=kind,employee=employee_view(employee),details=d,identity=identity,source_files=files)
        if kind=='imported_period':
            if fresh and (d['period_end']>self.hr.now()[:10] or any(item['received_on']>self.hr.now()[:10] for item in d['running_receipts'])):
                raise Problem(400,'Eine ursprüngliche historische Periode oder ein tatsächlicher Zufluss darf nicht zukünftig behauptet werden.')
        elif kind=='imported_one_off':
            if fresh and d['receipt_date']>self.hr.now()[:10]:raise Problem(400,'Ein tatsächlich früherer Einmalzufluss darf nicht zukünftig sein.')
            snapshot['assigned_period']=self._reference(employee_id,d['assigned_period_ref'],'imported_period',fresh=fresh)
        elif kind=='one_off_earning':
            terms=[self.facts._fact_ref(employee_id,value,'employment_terms',fresh=fresh) for value in d['employment_terms_refs']]
            for claim in d['claim_periods']:
                if any(not any(term['details']['employment_from']<=day<=(term['details']['employment_to'] or '9999-12-31') for term in terms) for day in dates(claim['start'],claim['end'])):
                    raise Problem(409,'Einmalanspruch liegt außerhalb der konkret belegten Beschäftigung.')
            snapshot['employment_terms']=terms
        elif kind=='annual_basis':
            imported=[self._reference(employee_id,value,'imported_period',fresh=fresh) for value in d['imported_period_refs']]
            bonuses=[self._reference(employee_id,value,'imported_one_off',fresh=fresh) for value in d['imported_one_off_refs']]
            runs=[self._run(employee_id,value,fresh=fresh) for value in d['payroll_run_refs']]
            from business_payroll_accounts import PayrollAccounts
            accounts=PayrollAccounts(self.office);payments=[];payment_by_run={}
            for value in d['payroll_payment_refs']:
                payment=accounts._get(value['id'],value['revision'])
                if payment['employee_id']!=employee_id or payment['kind']!='payment':raise Problem(404,'Zahlungsnachweis gehört nicht zu diesem Mitarbeiter.')
                if reference(payment)!=value or fresh and reference(accounts._get(value['id']))!=value:raise Problem(409,'Zahlungsfassung wurde geändert.')
                key=(payment['details']['run_id'],payment['details']['run_revision'])
                if key in payment_by_run or key not in {(run['id'],run['revision']) for run in runs}:raise Problem(409,'Zahlung benötigt genau ihre tatsächliche gebundene Lohnperiode.')
                payment_by_run[key]=payment;payments.append(payment)
            if any(employer_key(record['sources']['identity'])!=employer_key(identity) for record in imported+bonuses):raise Problem(409,'Jahresperioden gehören nicht zur selben rechtlichen Arbeitgeberidentität.')
            candidate=None
            if d['current_calculation_case_ref'] is not None:
                from business_payroll_calculation_cases import PayrollCalculationCases
                from payroll_calculations_2026 import calculate_calculation_source
                api=PayrollCalculationCases(self.office,clock=self.hr.clock)
                candidate=api._get(d['current_calculation_case_ref']['id'],d['current_calculation_case_ref']['revision'])
                from business_payroll_calculation_cases import validate_case_sources
                if candidate['employee_id']!=employee_id or candidate['kind']!='calculation_case' or candidate['status']!='active' or reference(candidate)!=d['current_calculation_case_ref']:
                    raise Problem(409,'Aktuelle laufende Monatsquelle ist nicht kanonisch an diese Person gebunden.')
                calc=self._planned_calculation(employee,candidate,fresh=fresh)
                if not calc['payroll_calculation_complete']:raise Problem(409,'Die laufende aktuelle Monatsrechnung muss vollständig sein.')
                if candidate['details']['month']!=d['coverage_to'][:7]:raise Problem(400,'Geplante laufende Rechnung gehört ausschließlich zum letzten Jahresbasismonat.')
                current=dict(id=candidate['id'],revision=candidate['revision'],content_hash=candidate['content_hash'],employee_id=employee_id,
                    source=dict(source_schema_version=3,month=candidate['details']['month'],calculation_case=candidate),calculation=calc)
            if fresh:
                known=self._all(employee_id)
                expected_periods=[reference(value) for value in known if value['kind']=='imported_period' and value['status']=='active' and
                    value['details']['period_start'][:4]==str(d['year']) and value['details']['period_end']<=d['coverage_to']]
                expected_bonuses=[reference(value) for value in known if value['kind']=='imported_one_off' and value['status']=='active' and
                    value['plan']['social_year']==d['year'] and value['plan']['assigned_period_end']<=d['coverage_to'] and value['details']['receipt_date']<=d['as_of_date']]
                if sorted(expected_periods,key=lambda v:v['id'])!=d['imported_period_refs'] or sorted(expected_bonuses,key=lambda v:v['id'])!=d['imported_one_off_refs']:
                    raise Problem(409,'Alle einschlägigen aktuellen Importperioden und bereits verarbeiteten Einmalbezüge binden.')
                from business_payroll import Payroll
                expected_runs=[reference(value) for value in Payroll(self.office)._all('run',employee_id) if self._relevant_run(value,d,candidate,current_one_off_id)]
                if sorted(expected_runs,key=lambda v:v['id'])!=d['payroll_run_refs']:raise Problem(409,'Alle tatsächlichen wirksamen Lohnperioden vollständig binden; die aktuelle laufende Quelle ersetzt nur ihren eigenen Monat.')
                expected_payments=[reference(value) for value in accounts._all(employee_id) if value['kind']=='payment' and
                    (value['details']['run_id'],value['details']['run_revision']) in {(run['id'],run['revision']) for run in runs}]
                if sorted(expected_payments,key=lambda value:value['id'])!=d['payroll_payment_refs']:raise Problem(409,'Alle aktuellen tatsächlichen Zahlungsfassungen der gebundenen Lohnperioden angeben.')
            projected=[self._project_run(value,as_of_date=d['as_of_date'],payment=payment_by_run.get((value['id'],value['revision'])),basis_year=d['year'],coverage_to=d['coverage_to']) for value in runs]
            if candidate is not None:projected.append(self._project_run(current,candidate=True,as_of_date=d['as_of_date']))
            for run,projection in zip(runs,projected):
                source=run['source']
                identities=(source['calculation_case']['sources']['identities'] if source.get('source_schema_version') in (3,4,5) else
                    source['period_case']['sources']['identities'] if source.get('source_schema_version')==2 else
                    [projection['payment_evidence']['sources']['identity']] if projection['payment_evidence'] else [])
                if not identities or any(employer_key(item)!=employer_key(identity) for item in identities):
                    raise Problem(409,'Tatsächliche interne Lohnperioden benötigen ihre passende belegte Arbeitgeberidentität.')
            if candidate is not None and any(employer_key(item)!=employer_key(identity) for item in candidate['sources']['identities']):
                raise Problem(409,'Aktuelle Monatsquelle gehört zu einer anderen Arbeitgeberidentität.')
            snapshot.update(imported_periods=imported,imported_one_offs=bonuses,payroll_runs=[self._compact_run(run) for run in runs],
                payroll_payments=[self._compact_payment(payment) if next(run for run in runs if run['id']==payment['details']['run_id'])['source'].get('source_schema_version') in (4,5) else payment for payment in payments],
                current_calculation_case=candidate,internal_periods=projected)
        else:
            history=self._reference(employee_id,d['annual_basis_ref'],'annual_basis',fresh=fresh)
            earning=self._reference(employee_id,d['current_one_off_ref'],'one_off_earning',fresh=fresh)
            tax_identity=self.facts._identity_ref(employee_id,d['identity_ref'],fresh=fresh)
            tax_profile=tax_identity['sources']['profile']['profile']
            if tax_identity['details']['tax_source'] not in ('elstam_imported','tax_office_certificate') or tax_profile['employment_kind']!='regular':
                raise Problem(409,'Individuelle Jahreslohnsteuer benötigt den tatsächlichen regulären ELStAM-Nachweis; pauschal besteuerte Minijobs sind kein individuelles Steuerbrutto.')
            if any(employer_key(item['sources']['identity'])!=employer_key(identity) for item in (history,earning)) or employer_key(tax_identity)!=employer_key(identity):
                raise Problem(409,'Steuervorschau verbindet verschiedene Arbeitgeber.')
            end=d['receipt_date'][:7]+f"-{calendar.monthrange(2026,int(d['receipt_date'][5:7]))[1]:02}"
            if not tax_identity['details']['valid_from']<=end<=tax_identity['details']['valid_to']:raise Problem(409,'Die Steuermerkmale müssen am Ende des tatsächlichen Zuflussmonats gelten.')
            from payroll_segments_2026 import contractual_earnings
            future=[];future_sources=[]
            for item in d['remaining_periods']:
                terms=self.facts._fact_ref(employee_id,item['employment_terms_ref'],'employment_terms',fresh=fresh)
                agreements=[self.facts._hr_ref(employee_id,value,'agreement',fresh=fresh) for value in item['agreement_refs']]
                if any(value['employment_kind']!='regular' for value in agreements):
                    raise Problem(409,'Künftiger Wechsel zwischen Pauschal- und Individualbesteuerung benötigt eine eigene belegte Jahressteuerzuordnung.')
                if any(reference(value) not in terms['details']['agreement_refs'] for value in agreements):raise Problem(409,'Prognosevertrag fehlt im tatsächlichen Beschäftigungsnachweis.')
                month_first=item['month']+'-01';month_last=item['month']+f"-{calendar.monthrange(2026,int(item['month'][5:7]))[1]:02}"
                employed=terms['details']['employment_from']<=month_last and (terms['details']['employment_to'] is None or terms['details']['employment_to']>=month_first)
                if fresh:
                    expected=[reference(value) for value in self.facts._all(employee_id,'employment_terms') if value['status']=='active' and
                        value['effective_from']<=month_last and (value['effective_to'] is None or value['effective_to']>=month_first)]
                    if expected!=([reference(terms)] if employed else []):raise Problem(409,'Jede künftige Beschäftigungsepisode muss vollständig und eindeutig belegt sein.')
                    if employed:
                        first=max(month_first,terms['details']['employment_from']);last=min(month_last,terms['details']['employment_to'] or month_last)
                        actual=sorted(self.hr._all('agreement',employee_id),key=lambda value:(value['effective_from'],value['id']))
                        before=[value for value in actual if value['effective_from']<=first]
                        needed=([before[-1]] if before else [])+[value for value in actual if first<value['effective_from']<=last]
                        if sorted([reference(value) for value in needed],key=lambda value:value['id'])!=item['agreement_refs']:
                            raise Problem(409,'Alle tatsächlich vereinbarten künftigen Entgeltänderungen müssen in der Prognose stehen.')
                schedule=self.facts._fact_ref(employee_id,item['work_schedule_ref'],'work_schedule',fresh=fresh) if item['work_schedule_ref'] else None
                if schedule and schedule['details']['month']!=item['month']:raise Problem(409,'Prognosearbeitsplan gehört zu einem anderen Monat.')
                if any(value['pay_basis']=='hourly' for value in agreements) and schedule is None:raise Problem(409,'Stundenlohnprognose benötigt ausdrücklich belegte geplante Arbeitszeit.')
                planned=[dict(date=value['date'],net_seconds=value['scheduled_seconds']) for value in schedule['details']['days']] if schedule else []
                calculation=contractual_earnings(item['month'],[terms],agreements,planned,schedule=schedule) if employed else dict(
                    gross_minor=0,blockers=[],reason='evidenced_outside_employment',employment_terms_ref=reference(terms))
                if calculation['blockers']:raise Problem(409,'Verbleibende Entgeltprognose ist mit dem konkreten Vertragsverfahren nicht vollständig berechenbar.')
                future.append(dict(month=item['month'],gross_minor=calculation['gross_minor'],basis='planned_contract_and_schedule',actual_time_modified=False))
                future_sources.append(dict(terms=terms,agreements=agreements,work_schedule=schedule,calculation=calculation))
            extra=[];extra_amount=0;bound={value['id'] for value in history['details']['imported_period_refs']+history['details']['imported_one_off_refs']}
            def received_tax_amount(record):
                if record['kind']=='imported_period':
                    matching=[item for item in record['details']['running_receipts'] if '2026-01-01'<=item['received_on']<=d['receipt_date']]
                    return sum(item['taxable_minor'] for item in matching if running_tax_year(record['details']['period_end'],item['received_on'])==2026)
                return record['details']['amount_minor'] if '2026-01-01'<=record['details']['receipt_date']<=d['receipt_date'] else 0
            if fresh:
                expected=[]
                for record in self._all(employee_id):
                    if (record['kind'] not in ('imported_period','imported_one_off') or record['status']!='active'
                            or record['id'] in bound or employer_key(record['sources']['identity'])!=employer_key(identity)):continue
                    validate_annual_sources(self.office,record)
                    if received_tax_amount(record):expected.append(reference(record))
                if sorted(expected,key=lambda value:value['id'])!=d['other_tax_receipt_refs']:
                    raise Problem(409,'Alle bereits bekannten tatsächlichen Steuerzuflüsse außerhalb der SV-Jahresbasis müssen vollständig gebunden sein.')
            for value in d['other_tax_receipt_refs']:
                record=self._reference(employee_id,value,fresh=fresh)
                if record['id'] in bound or record['kind'] not in ('imported_period','imported_one_off'):raise Problem(409,'Weiterer Steuerzufluss ist bereits enthalten oder keine echte Importquelle.')
                if employer_key(record['sources']['identity'])!=employer_key(identity):raise Problem(409,'Weiterer Steuerzufluss gehört zu einem anderen Arbeitgeber.')
                amount=received_tax_amount(record)
                if amount==0:raise Problem(409,'Weiterer Steuerzufluss belegt keinen tatsächlichen Bezug vor diesem Zuflussfall.')
                extra.append(record);extra_amount+=amount
            snapshot.update(annual_basis=history,current_one_off=earning,tax_identity=tax_identity,future_earnings=future,
                future_sources=future_sources,other_tax_receipts=extra,other_tax_receipts_minor=extra_amount)
        return snapshot

    def preview(self,actor,data):
        fields=('employee_id','employee_revision','kind','details','source_file_ids')
        _shape(data,fields,fields);d=normalize_details(data['kind'],data['details']);ids=file_ids(data['source_file_ids'])
        with transaction(self.office):
            fresh,employee=self._access(actor,data['employee_id'])
            if _integer(data['employee_revision'],1)!=employee['revision']:raise Problem(409,'Mitarbeiterstamm wurde geändert. Neu laden.')
            snapshot=self._snapshot(employee,data['kind'],d,ids);plan=build_annual_plan(snapshot)
            return dict(employee_id=employee['id'],kind=data['kind'],source_snapshot=snapshot,source_hash=_sha(snapshot),plan=plan,
                preview_hash=_sha(dict(source_snapshot=snapshot,plan=plan)),can_confirm=True,**self.facts._capabilities(fresh))

    def save(self,actor,data):
        required=('request_id','employee_id','employee_revision','kind','revision','status','details','source_file_ids','confirmed','preview_hash')
        _shape(data,required+('id','correction_reason'),required);identifier(data['request_id']);identifier(data['employee_id'])
        if data.get('id') is not None:identifier(data['id'])
        if data['confirmed'] is not True or data['status'] not in ('active','void'):raise Problem(400,'Geprüfte Jahresquelle ausdrücklich bestätigen.')
        if not isinstance(data['preview_hash'],str) or not re.fullmatch('[a-f0-9]{64}',data['preview_hash']):raise Problem(400,'Die genaue geprüfte Jahresvorschau ist erforderlich.')
        d=normalize_details(data['kind'],data['details']);ids=file_ids(data['source_file_ids']);_integer(data['employee_revision'],1);_integer(data['revision'])
        reason=text(data.get('correction_reason',''),'Korrekturgrund',2000,required=bool(data.get('id')))
        operation=self._operation(data['kind']);fingerprint=_sha([operation,data])
        with transaction(self.office):
            fresh,employee=self._access(actor,data['employee_id'],'personnel.approve');self._gate(fresh,new=False)
            receipt=self.db.execute('SELECT * FROM business_payroll_annual_requests WHERE user_id=? AND request_id=?',(fresh['id'],data['request_id'])).fetchone()
            if receipt is not None:
                if receipt['operation']!=operation or receipt['request_hash']!=fingerprint:raise Problem(409,'Vorgangs-ID wurde mit anderem Inhalt verwendet.')
                saved=self._get(receipt['fact_id'],receipt['fact_revision']);validate_annual_sources(self.office,saved)
                if saved['employee_id']!=employee['id'] or saved['content_hash']!=receipt['fact_content_hash']:raise Problem(500,'Jahresquittung widerspricht der ursprünglichen Annahme.')
                return saved
            try:
                self._gate(fresh)
                if employee['revision']!=data['employee_revision']:raise Problem(409,'Mitarbeiterstamm wurde geändert. Neu laden.')
                previous=self._get(data['id']) if data.get('id') else None
                if previous and (previous['employee_id']!=employee['id'] or previous['kind']!=data['kind']):raise Problem(404,'Korrektur gehört nicht zu diesem Jahresfakt.')
                if data['revision']!=(previous['revision'] if previous else 0):raise Problem(409,'Jahresfakt wurde geändert. Neu laden.')
                key=identity_key(data['kind'],d)
                if previous and identity_key(previous['kind'],previous['details'])!=key:raise Problem(400,'Ursprüngliche Jahresfallidentität bleibt unverändert.')
                existing=self.db.execute('SELECT id FROM business_payroll_annual_events WHERE employee_id=? AND identity_key=?',(employee['id'],key)).fetchone()
                if existing and (not previous or existing['id']!=previous['id']):raise Problem(409,'Dieser konkrete Jahresfall besteht bereits; seine Korrektur verwenden.')
                if data['status']=='void':
                    if not previous or previous['status']!='active' or d!=previous['details'] or ids!=previous['source_file_ids'] or data['preview_hash']!=previous['preview_hash']:
                        raise Problem(400,'Archivieren benötigt die unveränderte aktive Jahresfassung.')
                    validate_annual_sources(self.office,previous);snapshot,plan,preview_hash=previous['sources'],previous['plan'],previous['preview_hash']
                else:
                    snapshot=self._snapshot(employee,data['kind'],d,ids);plan=build_annual_plan(snapshot)
                    preview_hash=_sha(dict(source_snapshot=snapshot,plan=plan))
                    if data['preview_hash']!=preview_hash:raise Problem(409,'Jahresquelle oder Berechnung änderte sich seit der Vorschau.')
                payload=dict(details=d,source_file_ids=ids,plan=plan,preview_hash=preview_hash,correction_reason=reason,
                    accepted_command=json.loads(canonical(data)))
                first,last=effective(data['kind'],d)
                envelope=dict(id=previous['id'] if previous else uuid.uuid4().hex,revision=previous['revision']+1 if previous else 1,
                    employee_id=employee['id'],kind=data['kind'],effective_from=first,effective_to=last,status=data['status'],source_hash=_sha(snapshot),
                    previous_hash=previous['content_hash'] if previous else None,created_by=fresh['id'],created_at=self.hr.now(),
                    identity_key=None if previous else key,command_hash=fingerprint,payload=payload,sources=snapshot)
                columns=[key for key in envelope if key not in ('payload','sources')]
                self.db.execute('INSERT INTO business_payroll_annual_events('+','.join(columns)+',payload_json,sources_json,content_hash) VALUES('+','.join('?' for _ in range(len(columns)+3))+')',
                    tuple(envelope[key] for key in columns)+(canonical(payload),canonical(snapshot),_sha(envelope)))
                self.db.execute('INSERT INTO business_payroll_annual_requests(user_id,request_id,operation,request_hash,fact_id,fact_revision,fact_content_hash,created_at) VALUES(?,?,?,?,?,?,?,?)',
                    (fresh['id'],data['request_id'],operation,fingerprint,envelope['id'],envelope['revision'],_sha(envelope),envelope['created_at']))
                saved=self._get(envelope['id']);validate_annual_sources(self.office,saved)
                self.office.audit(fresh,'payroll.annual.'+data['kind'],saved['id']);return saved
            except Problem as error:
                if error.status==409:raise Problem(409,error.message,request_resolution='not_accepted') from None
                raise

    def resolve(self,actor,employee_id,value,kind=None,*,fresh=True):
        with transaction(self.office):
            self._access(actor,employee_id);return self._reference(employee_id,value,kind,fresh=fresh)

    def social_room(self,actor,employee_id,value,*,through,section_key,fresh=True):
        record=self.resolve(actor,employee_id,value,'annual_basis',fresh=fresh)
        return annual_social_room(dict(record['plan']['projection'],source_ref=reference(record)),through=through,section_key=section_key)


@_original_check_scope
def validate_annual_sources(office,value):
    api=_source_api(office,value['sources'])
    checks=_CHECKS.get();key=(id(office),'annual',_sha(value))
    if key in checks:return True
    try:
        row=api._row(value['id'],value['revision']);payload=json.loads(row['payload_json']);command=payload['accepted_command']
        if (value!=api._event(row) or _sha([api._operation(value['kind']),command])!=row['command_hash']
                or command['employee_id']!=value['employee_id'] or command['kind']!=value['kind'] or command['confirmed'] is not True
                or command['status']!=value['status'] or normalize_details(value['kind'],command['details'])!=value['details']
                or file_ids(command['source_file_ids'])!=value['source_file_ids'] or command['preview_hash']!=value['preview_hash']
                or command['revision']+1!=value['revision'] or command.get('id',value['id'])!=value['id']
                or text(command.get('correction_reason',''),'Korrekturgrund',2000)!=value['correction_reason']
                or effective(value['kind'],value['details'])!=(value['effective_from'],value['effective_to'])):
            raise ValueError('Changed original annual acceptance')
        receipt=office.db.execute('SELECT * FROM business_payroll_annual_requests WHERE user_id=? AND request_id=?',(row['created_by'],command['request_id'])).fetchone()
        if receipt is None or any(receipt[key]!=expected for key,expected in dict(operation=api._operation(value['kind']),request_hash=row['command_hash'],fact_id=value['id'],fact_revision=value['revision'],fact_content_hash=value['content_hash'],created_at=row['created_at']).items()):
            raise ValueError('Changed annual acceptance receipt')
        employee=value['sources']['employee'];_shape(employee,EMPLOYEE_FIELDS,EMPLOYEE_FIELDS)
        if value['status']=='active' and command['employee_revision']!=employee['revision']:raise ValueError('Changed accepted employee revision')
        originals=[]
        for found in office.db.execute("SELECT result_json FROM business_planning_requests WHERE operation='employee' AND result_json LIKE ?",('%"id":"'+employee['id']+'"%',)):
            original=json.loads(found['result_json'])
            if original.get('id')==employee['id'] and original.get('revision')==employee['revision']:originals.append(original)
        if len(originals)!=1 or employee['id']!=value['employee_id'] or any(originals[0].get(key)!=employee[key] for key in EMPLOYEE_FIELDS if key in originals[0]):raise ValueError('Changed actual employee original')
        expected=api._snapshot(employee,value['kind'],value['details'],value['source_file_ids'],fresh=False)
        plan=build_annual_plan(expected,rule_version=value['plan']['rule_version'])
        if expected!=value['sources'] or _sha(expected)!=value['source_hash'] or plan!=value['plan'] or value['preview_hash']!=_sha(dict(source_snapshot=expected,plan=plan)):
            raise ValueError('Changed annual sources or arithmetic')
        checks.add(key)
        return True
    except (Problem,KeyError,TypeError,ValueError,RecursionError) as error:raise ValueError('Invalid historical annual payroll sources') from error


def validate_integrity(office):
    from business_schema import _tables
    present=set(TABLES).intersection(_tables(office))
    if not present:return True
    if present!=set(TABLES):raise ValueError('Incomplete annual payroll schema')
    api=PayrollAnnualBasis(office);prior={};seen=set()
    try:
        for row in office.db.execute('SELECT * FROM business_payroll_annual_events ORDER BY id,revision'):
            record=api._event(row);old=prior.get(record['id'])
            if (record['revision']!=(old['revision']+1 if old else 1) or record['previous_hash']!=(old['content_hash'] if old else None)
                    or row['identity_key']!=(None if old else identity_key(record['kind'],record['details']))
                    or old and (record['employee_id']!=old['employee_id'] or record['kind']!=old['kind'] or not record['correction_reason'] or identity_key(record['kind'],record['details'])!=identity_key(old['kind'],old['details']))
                    or not old and record['status']!='active'):raise ValueError('Broken annual payroll history')
            if record['status']=='void' and (not old or old['status']!='active' or any(record[key]!=old[key] for key in ('details','source_file_ids','sources','source_hash','plan','preview_hash'))):raise ValueError('Changed void annual fact')
            validate_annual_sources(office,record);prior[record['id']]=record;seen.add((record['id'],record['revision']))
        receipts=[dict(row) for row in office.db.execute('SELECT * FROM business_payroll_annual_requests')]
        if len(receipts)!=len(seen) or {(r['fact_id'],r['fact_revision']) for r in receipts}!=seen:raise ValueError('Changed annual receipt cardinality')
    except (Problem,KeyError,TypeError,ValueError,json.JSONDecodeError) as error:raise ValueError('Invalid annual payroll archive') from error
    return True


def methods(path):
    if path.startswith('/payroll/annual-facts/factor-v2'):
        path=path.replace('/payroll/annual-facts/factor-v2','/payroll/annual-facts',1)
    if path=='/payroll/annual-facts':return 'GET, POST'
    if path=='/payroll/annual-facts/preview':return 'POST'
    if path=='/payroll/annual-facts/sources' or re.fullmatch('/payroll/annual-facts/'+ID+'(?:/history)?',path):return 'GET'
    return None


def dispatch(office,actor,path,method,data):
    allowed=methods(path)
    if allowed is None:return None
    if method not in allowed.split(', '):raise Problem(405,'Methode für diese Jahresquellenroute nicht zulässig.')
    if path.startswith('/payroll/annual-facts/factor-v2'):
        from business_payroll_factor_annual_basis import FactorAnnualBasis
        api=FactorAnnualBasis(office)
        path=path.replace('/payroll/annual-facts/factor-v2','/payroll/annual-facts',1)
    else:api=PayrollAnnualBasis(office)
    if method=='POST':result=api.preview(actor,data) if path.endswith('/preview') else api.save(actor,data)
    else:
        _shape(data,('_query',));query=data.get('_query',{})
        if path=='/payroll/annual-facts/sources':result=api.sources(actor,query)
        elif path=='/payroll/annual-facts':result=api.records(actor,query)
        else:_shape(query,());result=api.get(actor,path.split('/')[3],path.endswith('/history'))
    return result,200,'application/json'

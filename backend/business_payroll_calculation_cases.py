"""Private immutable v5 calculation cases and employer-wide travel tax policy.

The accepted command is retained privately and checked against its receipt.
Planned tax treatment is explicitly a preview context, never an assertion that
tax was booked, paid or transmitted. Actual booking is bound at run finalization.
"""
import json
import re
import uuid
from datetime import timedelta

from core import Problem,canonical
from business_foundation import _fresh,require_permission
from business_operations import identifier,text,transaction
from business_personnel_workflow import _integer,_sha,_shape
from business_payroll_facts import PayrollFacts,ref,references,reference,file_ids,month_days,validate_fact_sources
from payroll_calculations_2026 import CALCULATION_RULE_VERSION,SOURCE_CONTRACT_VERSION,build_calculation_plan,EVENT_FIELDS
from payroll_travel_tax_2026 import calculate_flat_travel_tax,SIMPLIFIED_RATES,_filing_period

FEATURES=('payroll_calculation_cases','payroll_factor_taxfree_travel')
TABLES=('business_payroll_calculation_case_events','business_payroll_calculation_case_requests')
KINDS=('calculation_case','travel_tax_policy')
POLICY_RULE_VERSION='de_2026_travel_tax_policy_v1'
ID=r'[a-f0-9]{32}'


def schema_statements(binary_type='BYTEA'):
    if binary_type not in ('BYTEA','BLOB'):raise ValueError('Unsupported calculation case storage')
    return [
        '''CREATE TABLE IF NOT EXISTS business_payroll_calculation_case_events(
        id TEXT NOT NULL,revision INTEGER NOT NULL CHECK(revision>0),employee_id TEXT REFERENCES business_employees(id),
        kind TEXT NOT NULL CHECK(kind IN ('calculation_case','travel_tax_policy')),
        effective_from TEXT NOT NULL,effective_to TEXT NOT NULL,status TEXT NOT NULL CHECK(status IN ('active','void')),
        payload_json TEXT NOT NULL,sources_json TEXT NOT NULL,source_hash TEXT NOT NULL,previous_hash TEXT,content_hash TEXT NOT NULL,
        created_by TEXT NOT NULL REFERENCES users(id),created_at TEXT NOT NULL,identity_key TEXT UNIQUE,command_hash TEXT NOT NULL,
        PRIMARY KEY(id,revision),CHECK((kind='calculation_case' AND employee_id IS NOT NULL) OR (kind='travel_tax_policy' AND employee_id IS NULL)))''',
        '''CREATE TABLE IF NOT EXISTS business_payroll_calculation_case_requests(
        user_id TEXT NOT NULL REFERENCES users(id),request_id TEXT NOT NULL,operation TEXT NOT NULL,request_hash TEXT NOT NULL,
        fact_id TEXT NOT NULL,fact_revision INTEGER NOT NULL,fact_content_hash TEXT NOT NULL,created_at TEXT NOT NULL,
        PRIMARY KEY(user_id,request_id),FOREIGN KEY(fact_id,fact_revision) REFERENCES business_payroll_calculation_case_events(id,revision))''',
        'CREATE INDEX IF NOT EXISTS business_payroll_calculation_case_employee ON business_payroll_calculation_case_events(employee_id,kind,id,revision)',
    ]


def protected_tables():return TABLES
def runtime_privileges():return {table:('SELECT','INSERT') for table in TABLES}


def guard_statements(dialect):
    from business_payroll_facts import guard_statements as original
    return [statement.replace('business_payroll_fact','business_payroll_calculation_case')
        .replace('employee_id=NEW.employee_id AND identity_key=NEW.identity_key','identity_key=NEW.identity_key')
        .replace('immutable payroll fact','immutable payroll calculation case') for statement in original(dialect)]


def normalize_details(kind,value):
    if not isinstance(value,dict):raise Problem(400,'Strukturierte Gesamtfalldetails erforderlich.')
    if kind=='travel_tax_policy':
        fields=('filing_period_from','filing_period_to','federal_state','church_method','church_rate_region',
            'church_method_applies_to_all','employer_bears_tax','verification_note')
        _shape(value,fields,fields)
        if (value['federal_state'] not in SIMPLIFIED_RATES or value['church_method'] not in ('simplified','evidence')
                or value['church_method_applies_to_all'] is not True or type(value['employer_bears_tax']) is not bool
                or value['church_rate_region'] not in ('standard','ni_ev_westfalen','bw_bad_wimpfen_mainz')
                or value['church_rate_region']=='ni_ev_westfalen' and value['federal_state']!='NI'
                or value['church_rate_region']=='bw_bad_wimpfen_mainz' and value['federal_state']!='BW'):
            raise Problem(400,'Einheitliches belegtes Kirchensteuerverfahren und Betriebsstätten-Zuständigkeit angeben.')
        _filing_period(dict(value,payroll_month=value['filing_period_from'][:7]))
        return dict(value,verification_note=text(value['verification_note'],'Betriebliche Steuerentscheidung',3000,required=True))
    if kind!='calculation_case':raise Problem(400,'Unbekannte Gesamtfallart.')
    fields=('month','period_case_ref','employment_terms_refs','profile_refs','identity_refs','segment_events','thirty_day_rule',
        'entitlement_case_refs','travel_settlement_refs','flat_tax_decision','verification_note')
    fields=fields+(('travel_payment_refs',) if 'travel_payment_refs' in value else ())
    _shape(value,fields,fields);dates=month_days(value['month'])
    if value['thirty_day_rule'] not in (None,'actual_days_capped_per_claim'):
        raise Problem(400,'Unbekannte ausdrücklich belegte 30-Tage-Vertragsregel.')
    if not isinstance(value['segment_events'],list) or len(value['segment_events'])>31:raise Problem(400,'Begrenzte tatsächliche Segmentereignisse angeben.')
    events=[]
    for event in value['segment_events']:
        fields=('kind','effective_from','before_profile_ref','after_profile_ref','source_file_ids','reason')
        _shape(event,fields,fields)
        if event['kind'] not in EVENT_FIELDS or not dates[0]<=event['effective_from']<=dates[-1]:raise Problem(400,'Belegtes Ereignis innerhalb des Monats angeben.')
        events.append(dict(kind=event['kind'],effective_from=event['effective_from'],before_profile_ref=ref(event['before_profile_ref']),
            after_profile_ref=ref(event['after_profile_ref']),source_file_ids=file_ids(event['source_file_ids']),reason=text(event['reason'],'Ereignisgrund',2000,required=True)))
    events.sort(key=lambda value:value['effective_from'])
    decision=value['flat_tax_decision']
    if decision is not None:
        fields=('policy_ref','church_membership_evidence','employee_deduction_file_ref','tax_certificate_file_ref','tax_certificate_issued_on','record_on_finalize')
        _shape(decision,fields,fields)
        if decision['record_on_finalize'] is not True:raise Problem(400,'Tatsächliche Pauschalsteuer-Erfassung mit dem Lohnabschluss ausdrücklich beauftragen.')
        decision=dict(decision,**{key:None if decision[key] is None else ref(decision[key]) for key in fields if key.endswith('_ref')})
        membership=decision['church_membership_evidence']
        if membership is not None:
            _shape(membership,('kind','reference','church_tax'),('kind','reference','church_tax'))
            if (membership['kind'] not in ('elstam','substitute_tax_certificate','official_employee_declaration','unknown_membership_general_rate')
                    or membership['kind']=='unknown_membership_general_rate' and membership['church_tax'] is not None
                    or membership['kind']!='unknown_membership_general_rate' and type(membership['church_tax']) is not bool):
                raise Problem(400,'Tatsächlichen Kirchensteuer-Nachweis mit belegter Zugehörigkeit oder ausdrücklichem allgemeinen Satz angeben.')
            decision['church_membership_evidence']=dict(membership,reference=ref(membership['reference']))
        if (decision['tax_certificate_file_ref'] is None)!=(decision['tax_certificate_issued_on'] is None):
            raise Problem(400,'Bescheinigungsdatum und tatsächlichen Originalnachweis gemeinsam binden.')
        if decision['tax_certificate_issued_on'] is not None:
            from payroll_de_2026 import day
            day(decision['tax_certificate_issued_on'])
    extra=dict(travel_payment_refs=references(value['travel_payment_refs'])) if 'travel_payment_refs' in value else {}
    return dict(extra,month=value['month'],period_case_ref=ref(value['period_case_ref']),employment_terms_refs=references(value['employment_terms_refs']),
        profile_refs=references(value['profile_refs']),identity_refs=references(value['identity_refs']),segment_events=events,
        thirty_day_rule=value['thirty_day_rule'],entitlement_case_refs=references(value['entitlement_case_refs'],minimum=0),
        travel_settlement_refs=references(value['travel_settlement_refs'],minimum=0),flat_tax_decision=decision,
        verification_note=text(value['verification_note'],'Gesamtfallprüfung',3000,required=True))


def _effective(kind,details):
    if kind=='travel_tax_policy':return details['filing_period_from'],details['filing_period_to']
    days=month_days(details['month']);return days[0],days[-1]


def _key(kind,employee_id,details):
    if kind=='calculation_case':return kind+':'+employee_id+':'+details['month']
    return kind+':'+_sha({key:details[key] for key in ('filing_period_from','filing_period_to','federal_state','church_rate_region')})


class PayrollCalculationCases(PayrollFacts):
    def __init__(self,office,*,clock=None):
        super().__init__(office,clock=clock);self.facts=PayrollFacts(office,clock=clock)

    def _access(self,actor,employee_id,permission='personnel.read'):
        if employee_id is not None:return super()._access(actor,employee_id,permission)
        fresh=_fresh(self.office,actor);require_permission(self.office,fresh,permission);require_permission(self.office,fresh,'personnel.read')
        return fresh,None

    def _gate(self,actor,*,new=True):
        from business_schema import require_capability
        from business_organization import require_active
        require_capability(self.office,'business_payroll_calculation_cases')
        if new:require_active(self.office,actor,'/payroll','business_payroll')

    def _row(self,object_id,revision=None):
        identifier(object_id)
        if revision is None:row=self.db.execute('SELECT * FROM business_payroll_calculation_case_events WHERE id=? ORDER BY revision DESC LIMIT 1',(object_id,)).fetchone()
        else:
            _integer(revision,1);row=self.db.execute('SELECT * FROM business_payroll_calculation_case_events WHERE id=? AND revision=?',(object_id,revision)).fetchone()
        if row is None:raise Problem(404,'Gesamtfall-/Steuerentscheidungsfassung nicht verfügbar.')
        return row

    def _event(self,row):
        result=super()._event(row)
        result.pop('accepted_command')
        return result

    def _all(self,employee_id,kind=None):
        predicate='e.employee_id IS NULL' if employee_id is None else 'e.employee_id=?'
        rows=self.db.execute('SELECT e.* FROM business_payroll_calculation_case_events e WHERE '
            +predicate+' AND NOT EXISTS '
            '(SELECT 1 FROM business_payroll_calculation_case_events n WHERE n.id=e.id AND n.revision>e.revision) ORDER BY e.created_at,e.id',
            () if employee_id is None else (employee_id,)).fetchall()
        return [self._event(row) for row in rows if kind is None or row['kind']==kind]

    def records(self,actor,query,*,policies=False):
        _shape(query,() if policies else ('employee_id','month'),() if policies else ('employee_id',))
        with transaction(self.office):
            fresh,_=self._access(actor,None if policies else query['employee_id'])
            items=self._all(None if policies else query['employee_id'])
            if query.get('month') is not None:
                month_days(query['month']);items=[value for value in items if value['details']['month']==query['month']]
            return dict(items=items,**self._capabilities(fresh))

    def get(self,actor,object_id,history=False):
        with transaction(self.office):
            row=self._row(object_id);self._access(actor,row['employee_id'])
            if history:return dict(items=[self._event(value) for value in self.db.execute('SELECT * FROM business_payroll_calculation_case_events WHERE id=? ORDER BY revision',(object_id,))])
            return self._event(row)

    def sources(self,actor,query):
        _shape(query,('employee_id','month'),('employee_id','month'));month_days(query['month'])
        with transaction(self.office):
            fresh,employee=self._access(actor,query['employee_id'])
            from business_payroll_entitlements import PayrollEntitlements
            from business_travel_allowances import TravelAllowances
            result=self.facts.sources(fresh,dict(employee_id=employee['id']))
            # Factor periods have their own v9 running-pay rule. They must not
            # be offered to the historical v5 claims/travel composition rule.
            factor_facts=[item for item in result['facts'] if item['kind']=='period_case' and item['plan']['rule_version']=='de_2026_standard_factor_period_v9']
            result['facts']=[item for item in result['facts'] if item['kind']!='period_case' or item['plan']['rule_version']=='de_2026_periods_pap_v4']
            from payroll_factor_taxfree_sources import payment_choices
            try: payments=payment_choices(self.office,fresh,employee['id'])
            except Problem as error:
                if error.status!=403:raise
                payments=[]
            result.update(factor_period_facts=factor_facts,travel_payment_proofs=payments)
            result.update(month=query['month'],calculation_cases=self._all(employee['id']),travel_tax_policies=self._all(None),
                entitlements=PayrollEntitlements(self.office)._all(employee['id']),travel_settlements=TravelAllowances(self.office)._all('settlement',employee['id']))
            return result

    def policy_sources(self,actor,query):
        _shape(query,())
        with transaction(self.office):
            fresh,_=self._access(actor,None)
            ids=[row['id'] for row in self.db.execute(
                "SELECT f.id FROM business_personnel_files f WHERE f.purpose='personnel' AND NOT EXISTS "
                '(SELECT 1 FROM business_personnel_files n WHERE n.supersedes=f.id) ORDER BY f.created_at,f.id')]
            files=self._files(None,ids,fresh=True)
            return dict(employee_id=None,files=files,file_references=[dict(id=value['id'],revision=1,content_hash=value['content_hash']) for value in files],
                policies=self._all(None,'travel_tax_policy'),**self._capabilities(fresh))

    def _policy(self,value,*,fresh):
        value=ref(value);record=self._get(value['id'],value['revision'])
        if (record['kind']!='travel_tax_policy' or record['status']!='active' or reference(record)!=value
                or fresh and reference(self._get(value['id']))!=value):raise Problem(409,'Aktive tatsächliche Steuerentscheidungsfassung erforderlich.')
        validate_case_sources(self.office,record)
        if fresh:
            self._files(None,record['source_file_ids'],fresh=True);self._policy_uniform(record['details'],record['id'])
        return record

    def _policy_uniform(self,details,own_id=None):
        for other in self._all(None,'travel_tax_policy'):
            d=other['details']
            if other['id']==own_id or other['status']!='active':continue
            if max(d['filing_period_from'],details['filing_period_from'])<=min(d['filing_period_to'],details['filing_period_to']):
                # One company dataset: overlapping filing periods must not permit
                # a per-person or per-case switch of the church-tax method.
                if d['church_method']!=details['church_method']:
                    raise Problem(409,'Für denselben Anmeldezeitraum/Tatbestand besteht eine abweichende betriebliche Kirchensteuerwahl.')
        from payroll_travel_recording import require_uniform_recorded_policy
        require_uniform_recorded_policy(self.office,details)

    def _snapshot(self,employee,kind,details,ids,*,fresh=True,planned_on=None,rule_version=None,source_contract_version=1,actor=None):
        if kind=='travel_tax_policy':
            if fresh:self._policy_uniform(details)
            return dict(schema_version=1,policy=details,source_files=self._files(None,ids,fresh=fresh))
        from payroll_factor_taxfree_travel_2026 import RULE_VERSION as FACTOR_TRAVEL_RULE
        factor_travel=rule_version==FACTOR_TRAVEL_RULE
        employee_id=employee['id'];base=self.facts._fact_ref(employee_id,details['period_case_ref'],'period_case',fresh=fresh)
        expected_base='de_2026_standard_factor_period_v9' if factor_travel else 'de_2026_periods_pap_v4'
        if base['plan']['rule_version']!=expected_base:
            raise Problem(400,'Dieser Faktor-Monatsfall wird direkt als belegter Periodenlohn abgerechnet. Ansprüche, Reisen und Einmalbezüge benötigen ihren eigenen Faktor-Regelzweig.')
        if base['details']['month']!=details['month']:raise Problem(400,'P2-Basisfall gehört zu einem anderen Monat.')
        if fresh:
            expected=self.facts._snapshot(employee,'period_case',base['details'],base['source_file_ids'])
            if expected!=base['sources']:raise Problem(409,'P2-Basisfall entspricht nicht mehr der tatsächlichen aktuellen Personalvorbereitung.')
        terms=[self.facts._fact_ref(employee_id,value,'employment_terms',fresh=fresh) for value in details['employment_terms_refs']]
        if reference(base['sources']['employment_terms']) not in details['employment_terms_refs']:
            raise Problem(400,'Beschäftigungsnachweis des tatsächlichen P2-Basisfalls muss enthalten bleiben.')
        if fresh:
            first,last=month_days(details['month'])[0],month_days(details['month'])[-1]
            expected=[reference(value) for value in self.facts._all(employee_id,'employment_terms')
                if value['status']=='active' and value['effective_from']<=last and (value['effective_to'] is None or value['effective_to']>=first)]
            if sorted(expected,key=lambda value:value['id'])!=details['employment_terms_refs']:
                raise Problem(409,'Alle tatsächlich aktiven Beschäftigungsnachweise dieses Monats müssen vollständig gebunden sein.')
        profiles=[self.facts._payroll_ref(employee_id,value,fresh=fresh) for value in details['profile_refs']]
        identities=[self.facts._identity_ref(employee_id,value,fresh=fresh) for value in details['identity_refs']]
        if not all(value in details['profile_refs'] for value in base['details']['profile_refs']):raise Problem(400,'Tatsächliche P2-Profilfassungen dürfen nicht aus dem Gesamtfall entfernt werden.')
        for event in details['segment_events']:
            if not set(event['source_file_ids']).issubset(ids):raise Problem(400,'Jedes Ereignisoriginal am Gesamtfall binden.')
        from payroll_segments_2026 import employment_intervals
        episodes=employment_intervals(details['month'],terms)
        if fresh:
            from business_payroll import Payroll
            available=sorted(Payroll(self.office)._all('profile',employee_id),key=lambda value:value['profile']['effective_from'])
            expected={}
            for episode in episodes:
                before=[value for value in available if value['profile']['effective_from']<=episode['start']]
                for value in ([before[-1]] if before else [])+[value for value in available if episode['start']<value['profile']['effective_from']<=episode['end']]:expected[value['id']]=reference(value)
            if sorted(expected.values(),key=lambda value:value['id'])!=details['profile_refs']:raise Problem(409,'Alle tatsächlich einschlägigen aktuellen Profile müssen vollständig gebunden sein.')
        from business_payroll_entitlements import PayrollEntitlements,validate_entitlement_sources
        entitlements_api=PayrollEntitlements(self.office,clock=self.hr.clock);entitlements=[]
        if fresh:
            first,last=month_days(details['month'])[0],month_days(details['month'])[-1]
            expected=[reference(value) for value in entitlements_api._all(employee_id)
                if value['status']=='active' and value['effective_from']<=last and value['effective_to']>=first]
            if sorted(expected,key=lambda value:value['id'])!=details['entitlement_case_refs']:
                raise Problem(409,'Alle tatsächlich aktiven Anspruchsnachweise dieses Monats müssen vollständig gebunden sein.')
        for value in details['entitlement_case_refs']:
            record=entitlements_api._ref(employee_id,value,fresh=fresh);validate_entitlement_sources(self.office,record)
            if fresh and entitlements_api._snapshot(employee,record['kind'],record['details'],record['source_file_ids'])!=record['sources']:
                raise Problem(409,'Anspruchsfassung entspricht nicht mehr den aktuellen Originalen.')
            if fresh:_require_safe_sickness_source(record)
            entitlements.append(record)
        from travel_payroll_sources import travel_payroll_source
        from business_travel_allowances import TravelAllowances
        travel=[]
        used_payments=set()
        for value in details['travel_settlement_refs']:
            if fresh and reference(TravelAllowances(self.office)._get('settlement',value['id']))!=value:
                raise Problem(409,'Für neue Berechnung die aktuelle tatsächliche Reiseabrechnung binden.')
            if factor_travel:
                from payroll_factor_taxfree_sources import paid_taxfree_source
                selected=[]
                for payment_ref in details['travel_payment_refs']:
                    payment=TravelAllowances(self.office)._get('payment',payment_ref['id'],payment_ref['revision'])
                    if payment['details']['settlement_ref']['id']==value['id']:
                        selected.append(payment_ref);used_payments.add(payment_ref['id'])
                adapter=paid_taxfree_source(self.office,actor,employee_id,value,selected,details['month'],fresh=fresh)
            else:adapter=travel_payroll_source(self.office,None,value,details['month'])
            if adapter['employee_id']!=employee_id:raise Problem(404,'Reisequelle gehört nicht zu diesem Mitarbeiter.')
            travel.append(adapter)
        if factor_travel and used_payments!={value['id'] for value in details['travel_payment_refs']}:
            raise Problem(400,'Jede Zahlungsreferenz muss zu einer der ausgewählten Originalreisen gehören.')
        flat_sources=[value for value in travel if value['flat_taxable_payroll_minor']];flat=None
        decision=details['flat_tax_decision']
        if decision is not None:
            if not flat_sources:raise Problem(400,'Pauschalierungsauftrag benötigt tatsächlich pauschalierbare Reisebeträge.')
            policy=self._policy(decision['policy_ref'],fresh=fresh);p=policy['details']
            if fresh and planned_on!=self.hr.now()[:10]:raise Problem(409,'Vorgesehener Erfassungstag wurde geändert; neue Vorschau erforderlich.')
            membership=None;member=None;membership_record=None;files=[]
            selected_evidence=decision['church_membership_evidence']
            if selected_evidence is not None and selected_evidence['kind'] in ('elstam','substitute_tax_certificate'):
                membership_record=self.facts._identity_ref(employee_id,selected_evidence['reference'],fresh=fresh)
                d=membership_record['details'];selected=next((value for value in profiles if value['id']==d['profile_id'] and value['revision']==d['profile_revision']),None)
                if selected is None or d['tax_source'] not in ('elstam_imported','tax_office_certificate'):
                    raise Problem(400,'Kirchensteuer-Nachweis muss zu einer tatsächlichen gewählten ELStAM-/Bescheinigungsfassung gehören.')
                if not (d['valid_from']<=details['month']+'-01' and d['valid_to']>=month_days(details['month'])[-1]):
                    raise Problem(409,'Kirchensteuer-Nachweis deckt den Zuflussmonat nicht vollständig ab.')
                member=selected['profile']['church_tax']!='none'
                membership=dict(kind='elstam' if d['tax_source']=='elstam_imported' else 'substitute_tax_certificate',reference=reference(membership_record))
                if selected_evidence['kind']!=membership['kind'] or selected_evidence['church_tax']!=member:
                    raise Problem(409,'Kirchensteuer-Zugehörigkeit oder Nachweisart widerspricht der tatsächlichen Steuermerkmalquelle.')
            elif selected_evidence is not None:
                value=selected_evidence['reference'];file=self.facts._files(employee_id,[value['id']],fresh=fresh)[0]
                if value['revision']!=1 or file['content_hash']!=value['content_hash']:raise Problem(409,'Amtliche Arbeitnehmererklärung oder dokumentierter allgemeiner Satz benötigt das tatsächliche Original.')
                files.append(file);member=selected_evidence['church_tax'];membership={key:selected_evidence[key] for key in ('kind','reference')}
            for key in ('employee_deduction_file_ref','tax_certificate_file_ref'):
                value=decision[key]
                if value is not None:
                    file=self.facts._files(employee_id,[value['id']],fresh=fresh)[0]
                    if value['revision']!=1 or file['content_hash']!=value['content_hash']:raise Problem(409,'Unveränderte tatsächliche Personaldatei als Steuerbeleg erforderlich.')
                    files.append(file)
            if fresh and decision['tax_certificate_issued_on'] is not None and decision['tax_certificate_issued_on']>self.hr.now()[:10]:
                raise Problem(400,'Eine bereits ausgestellte Bescheinigung darf nicht zukünftig behauptet werden.')
            evidence=dict(policy_ref=reference(policy),filing_period_from=p['filing_period_from'],filing_period_to=p['filing_period_to'],
                payroll_month=details['month'],taxation_recorded_on=planned_on,tax_certificate_issued_on=decision['tax_certificate_issued_on'],
                eligible_limit_minor=sum(value['flat_taxable_payroll_minor'] for value in flat_sources),
                eligible_source_refs=[value['settlement_ref'] for value in flat_sources],church_rate_region=p['church_rate_region'],
                church_method_applies_to_all=True,church_membership_evidence=membership,
                employee_deduction_authorization=decision['employee_deduction_file_ref'])
            args=dict(federal_state=p['federal_state'],church_method=p['church_method'],church_tax=member,employer_bears_tax=p['employer_bears_tax'],evidence=evidence)
            flat=dict(parameters=args,calculation=calculate_flat_travel_tax(evidence['eligible_limit_minor'],**args),
                recording_context=dict(planned_recording_on=planned_on,actual_recorded=False),policy=policy,membership_identity=membership_record,source_files=files)
        return dict(schema_version=1,source_contract_version=source_contract_version,rule_version=rule_version or CALCULATION_RULE_VERSION,
            employee_id=employee_id,month=details['month'],period_case=base,employment_terms=terms,profiles=profiles,identities=identities,
            segment_events=details['segment_events'],thirty_day_rule=details['thirty_day_rule'],entitlements=entitlements,
            travel_sources=travel,flat_travel_tax=flat,source_files=self._files(employee_id,ids,fresh=fresh))

    def preview(self,actor,data):
        fields=('employee_id','employee_revision','kind','rule_version','source_contract_version','details','source_file_ids')
        _shape(data,fields,fields);kind=data['kind'];details=normalize_details(kind,data['details']);ids=file_ids(data['source_file_ids'])
        self._versions(data)
        with transaction(self.office):
            fresh,employee=self._access(actor,data['employee_id'])
            if (employee['revision'] if employee else None)!=data['employee_revision']:raise Problem(409,'Mitarbeiterrevision stimmt nicht mit dem tatsächlichen aktuellen Stamm überein.')
            snapshot=self._snapshot(employee,kind,details,ids,planned_on=self.hr.now()[:10],rule_version=data['rule_version'],source_contract_version=data['source_contract_version'],actor=fresh)
            plan=self._plan(kind,snapshot)
            return dict(employee_id=data['employee_id'],kind=kind,source_snapshot=snapshot,source_hash=_sha(snapshot),plan=plan,
                preview_hash=_sha(dict(source_snapshot=snapshot,plan=plan)),can_confirm=True,
                can_calculate=plan['can_calculate'] if plan else False,**self._capabilities(fresh))

    @staticmethod
    def _versions(data):
        if not isinstance(data.get('details'),dict):raise Problem(400,'Strukturierte Gesamtfalldetails erforderlich.')
        from payroll_factor_taxfree_travel_2026 import RULE_VERSION as FACTOR_TRAVEL_RULE
        is_new=data['kind']=='calculation_case' and data['rule_version']==FACTOR_TRAVEL_RULE
        expected=FACTOR_TRAVEL_RULE if is_new else CALCULATION_RULE_VERSION if data['kind']=='calculation_case' else POLICY_RULE_VERSION
        contract=2 if is_new else SOURCE_CONTRACT_VERSION
        if data['kind']=='calculation_case' and ('travel_payment_refs' in data['details'])!=is_new:raise Problem(400,'Reisezahlungsnachweise gehören ausschließlich zum neuen Faktorvertrag.')
        if data['rule_version']!=expected or type(data['source_contract_version']) is not int or data['source_contract_version']!=contract:
            raise Problem(400,'Regel und Quellenvertrag ausdrücklich in ihrer bekannten Version angeben.')
        if (data['kind']=='travel_tax_policy')!=(data['employee_id'] is None) or data['employee_id'] is None and data['employee_revision'] is not None:
            raise Problem(400,'Betriebliche Steuerentscheidung ohne Mitarbeiter; Gesamtfall mit tatsächlicher Person angeben.')

    @staticmethod
    def _plan(kind,snapshot):
        if kind=='travel_tax_policy':return None
        from payroll_factor_taxfree_travel_2026 import RULE_VERSION as FACTOR_TRAVEL_RULE,build_plan
        builder=build_plan if snapshot['rule_version']==FACTOR_TRAVEL_RULE else build_calculation_plan
        return builder(snapshot,rule_version=snapshot['rule_version'],source_contract_version=snapshot['source_contract_version'])

    def save(self,actor,data):
        required=('request_id','employee_id','employee_revision','kind','rule_version','source_contract_version','revision','status',
            'details','source_file_ids','confirmed','preview_hash')
        _shape(data,required+('id','correction_reason'),required);identifier(data['request_id']);self._versions(data)
        if data.get('id') is not None:identifier(data['id'])
        if data['confirmed'] is not True or data['status'] not in ('active','void') or not re.fullmatch('[a-f0-9]{64}',str(data['preview_hash'])):
            raise Problem(400,'Tatsächliche geprüfte Vorschau und ausdrückliche Bestätigung erforderlich.')
        _integer(data['revision']);details=normalize_details(data['kind'],data['details']);ids=file_ids(data['source_file_ids'])
        reason=text(data.get('correction_reason',''),'Korrekturgrund',2000,required=bool(data.get('id')))
        operation='calculation_fact.saved:'+data['kind'];fingerprint=_sha([operation,data])
        with transaction(self.office):
            fresh,employee=self._access(actor,data['employee_id'],'personnel.approve');self._gate(fresh,new=False)
            receipt=self.db.execute('SELECT * FROM business_payroll_calculation_case_requests WHERE user_id=? AND request_id=?',(fresh['id'],data['request_id'])).fetchone()
            if receipt is not None:
                if receipt['operation']!=operation or receipt['request_hash']!=fingerprint:raise Problem(409,'Vorgangs-ID wurde mit anderem ursprünglichen Inhalt verwendet.')
                original=self._row(receipt['fact_id'],receipt['fact_revision']);value=self._event(original)
                if (value['content_hash']!=receipt['fact_content_hash'] or original['command_hash']!=fingerprint
                        or json.loads(original['payload_json'])['accepted_command']!=data):raise Problem(500,'Unveränderliche Annahmequittung widerspricht dem ursprünglichen Auftrag.')
                validate_case_sources(self.office,value);return value
            try:
                self._gate(fresh)
                if (employee['revision'] if employee else None)!=data['employee_revision']:raise Problem(409,'Mitarbeiter wurde geändert; neue Vorschau erforderlich.')
                previous=self._get(data['id']) if data.get('id') else None
                if previous and (previous['employee_id']!=data['employee_id'] or previous['kind']!=data['kind']):raise Problem(404,'Korrektur gehört nicht zu diesem Gesamtfall.')
                if previous and (previous['rule_version']!=data['rule_version'] or previous['source_contract_version']!=data['source_contract_version']):
                    raise Problem(400,'Eine Korrektur bleibt beim ursprünglichen Regel- und Quellenvertrag.')
                if data['revision']!=(previous['revision'] if previous else 0):raise Problem(409,'Gesamtfall wurde inzwischen geändert.')
                identity_key=_key(data['kind'],data['employee_id'],details)
                existing=self.db.execute('SELECT id FROM business_payroll_calculation_case_events WHERE identity_key=?',(identity_key,)).fetchone()
                if existing and (previous is None or previous['id']!=existing['id']):raise Problem(409,'Für diesen Monat oder Steuerzeitraum besteht bereits ein Fall; Korrektur verwenden.')
                if previous and _key(previous['kind'],previous['employee_id'],previous['details'])!=identity_key:raise Problem(400,'Ursprüngliche Fall-/Steuerzeitraumidentität nicht wechseln.')
                if data['status']=='void':
                    if previous is None or previous['status']!='active' or details!=previous['details'] or ids!=previous['source_file_ids'] or data['preview_hash']!=previous['preview_hash']:
                        raise Problem(400,'Archivieren benötigt die unveränderte aktive Fassung.')
                    validate_case_sources(self.office,previous);snapshot,plan=previous['sources'],previous['plan']
                else:
                    snapshot=self._snapshot(employee,data['kind'],details,ids,planned_on=self.hr.now()[:10],rule_version=data['rule_version'],source_contract_version=data['source_contract_version'],actor=fresh);plan=self._plan(data['kind'],snapshot)
                    if _sha(dict(source_snapshot=snapshot,plan=plan))!=data['preview_hash']:raise Problem(409,'Tatsächliche Quellen oder Erfassungstag seit Vorschau geändert.')
                start,end=_effective(data['kind'],details)
                payload=dict(rule_version=data['rule_version'],source_contract_version=data['source_contract_version'],details=details,source_file_ids=ids,
                    plan=plan,preview_hash=data['preview_hash'],correction_reason=reason,accepted_command=json.loads(canonical(data)))
                envelope=dict(id=previous['id'] if previous else uuid.uuid4().hex,revision=previous['revision']+1 if previous else 1,
                    employee_id=data['employee_id'],kind=data['kind'],effective_from=start,effective_to=end,status=data['status'],source_hash=_sha(snapshot),
                    previous_hash=previous['content_hash'] if previous else None,created_by=fresh['id'],created_at=self.hr.now(),
                    identity_key=None if previous else identity_key,command_hash=fingerprint,payload=payload,sources=snapshot)
                columns=tuple(key for key in envelope if key not in ('payload','sources'))
                self.db.execute('INSERT INTO business_payroll_calculation_case_events('+','.join(columns)+',payload_json,sources_json,content_hash) VALUES('+','.join('?' for _ in range(len(columns)+3))+')',
                    tuple(envelope[key] for key in columns)+(canonical(payload),canonical(snapshot),_sha(envelope)))
                result=self._get(envelope['id'])
                self.db.execute('INSERT INTO business_payroll_calculation_case_requests(user_id,request_id,operation,request_hash,fact_id,fact_revision,fact_content_hash,created_at) VALUES(?,?,?,?,?,?,?,?)',
                    (fresh['id'],data['request_id'],operation,fingerprint,result['id'],result['revision'],result['content_hash'],envelope['created_at']))
                validate_case_sources(self.office,result)
                self.office.audit(fresh,'payroll.'+data['kind'],result['id']);return result
            except Problem as error:
                if error.status==409:raise Problem(409,error.message,request_resolution='not_accepted') from None
                raise

    def resolve_calculation_case(self,actor,employee_id,value,*,fresh=True):
        value=ref(value)
        with transaction(self.office):
            _,employee=self._access(actor,employee_id);record=self._get(value['id'],value['revision'])
            if record['employee_id']!=employee_id or record['kind']!='calculation_case':raise Problem(404,'Gesamtfall gehört nicht zu dieser Person.')
            if reference(record)!=value or record['status']!='active' or fresh and reference(self._get(value['id']))!=value:
                raise Problem(409,'Aktive unveränderte Gesamtfallfassung erforderlich.')
            validate_case_sources(self.office,record)
            if fresh and self._snapshot(employee,'calculation_case',record['details'],record['source_file_ids'],planned_on=self.hr.now()[:10],rule_version=record['rule_version'],source_contract_version=record['source_contract_version'],actor=actor)!=record['sources']:
                raise Problem(409,'Gesamtfallquellen oder geplanter Steuererfassungstag haben sich geändert. Neue bestätigte Vorschau erforderlich.')
            return record


def _require_safe_sickness_source(value):
    """Do not use a known v1 free-day deadline ambiguity for a new v5 run."""
    from payroll_de_2026 import day
    history=value if value['kind']=='sickness_history' else value['sources'].get('sickness_history')
    if history is None or history['plan']['rule_version']!='de_2026_entitlements_v1':return
    source=history['details']['input']
    if source['pay_basis']!='hourly':return
    for episode in source['episodes']:
        if (episode['onset']=='non_workday' and episode['first_scheduled_day'] is not None
                and day(episode['first_scheduled_day'])>day(episode['from'])+timedelta(days=1)):
            raise Problem(409,'Für diesen freien AU-Anfang ist die korrigierte versionierte Krankheitsfrist erforderlich; der alte Nachweis bleibt historisch erhalten.')


def validate_case_sources(office,value):
    api=PayrollCalculationCases(office)
    try:
        row=api._row(value['id'],value['revision'])
        details=normalize_details(value['kind'],value['details']);command=json.loads(row['payload_json'])['accepted_command'];api._versions(command)
        if (details!=value['details'] or file_ids(value['source_file_ids'])!=value['source_file_ids']
                or _effective(value['kind'],details)!=(value['effective_from'],value['effective_to'])
                or command['kind']!=value['kind'] or command['employee_id']!=value['employee_id'] or command['status']!=value['status']
                or normalize_details(value['kind'],command['details'])!=details or command['confirmed'] is not True
                or file_ids(command['source_file_ids'])!=value['source_file_ids'] or command['preview_hash']!=value['preview_hash']
                or command['revision']+1!=value['revision'] or command.get('id',value['id'])!=value['id']
                or text(command.get('correction_reason',''),'Korrekturgrund',2000)!=value['correction_reason']
                or command['rule_version']!=value['rule_version'] or command['source_contract_version']!=value['source_contract_version']):
            raise ValueError('Changed canonical calculation case or accepted original command')
        if _sha(['calculation_fact.saved:'+value['kind'],command])!=row['command_hash']:raise ValueError('Original acceptance command hash mismatch')
        receipt=office.db.execute('SELECT * FROM business_payroll_calculation_case_requests WHERE user_id=? AND request_id=?',
            (value['created_by'],command['request_id'])).fetchone()
        if (receipt is None or receipt['operation']!='calculation_fact.saved:'+value['kind']
                or receipt['request_hash']!=row['command_hash'] or receipt['fact_id']!=value['id']
                or receipt['fact_revision']!=value['revision'] or receipt['fact_content_hash']!=value['content_hash']
                or receipt['created_at']!=value['created_at']):
            raise ValueError('Original acceptance receipt mismatch')
        source=value['sources'];employee=None;planned=None
        if value['kind']=='calculation_case':
            validate_fact_sources(office,source['period_case'])
            employee=source['period_case']['sources']['preparation']['snapshot']['employee']
            if value['status']=='active' and employee['revision']!=command['employee_revision']:raise ValueError('Changed originally accepted employee revision')
            if source['flat_travel_tax'] is not None:planned=source['flat_travel_tax']['recording_context']['planned_recording_on']
        expected=api._snapshot(employee,value['kind'],details,value['source_file_ids'],fresh=False,planned_on=planned,rule_version=value['rule_version'],source_contract_version=value['source_contract_version'])
        plan=api._plan(value['kind'],expected)
        if expected!=source or _sha(source)!=value['source_hash'] or plan!=value['plan'] or _sha(dict(source_snapshot=source,plan=plan))!=value['preview_hash']:
            raise ValueError('Calculation sources or historical arithmetic changed')
        return True
    except (Problem,KeyError,TypeError,ValueError,RecursionError) as error:
        raise ValueError('Invalid historical calculation case') from error


def validate_integrity(office):
    from business_schema import _tables
    present=set(TABLES).intersection(_tables(office))
    if not present:return True
    if present!=set(TABLES):raise ValueError('Incomplete calculation case schema')
    api=PayrollCalculationCases(office);previous={};receipts=set()
    try:
        for row in office.db.execute('SELECT * FROM business_payroll_calculation_case_events ORDER BY id,revision'):
            value=api._event(row);prior=previous.get(value['id'])
            if (value['revision']!=(prior['revision']+1 if prior else 1) or value['previous_hash']!=(prior['content_hash'] if prior else None)
                    or row['identity_key']!=(None if prior else _key(value['kind'],value['employee_id'],value['details']))
                    or prior and any(value[key]!=prior[key] for key in ('kind','employee_id','effective_from','effective_to'))
                    or prior and not value['correction_reason'] or not prior and value['status']!='active'):
                raise ValueError('Broken calculation case history')
            if value['status']=='void' and (not prior or prior['status']!='active' or any(value[key]!=prior[key] for key in ('details','source_file_ids','sources','source_hash','plan','preview_hash'))):
                raise ValueError('Changed void calculation case')
            validate_case_sources(office,value);previous[value['id']]=value
        for receipt in office.db.execute('SELECT * FROM business_payroll_calculation_case_requests'):
            row=api._row(receipt['fact_id'],receipt['fact_revision']);value=api._event(row);key=(value['id'],value['revision']);command=json.loads(row['payload_json'])['accepted_command']
            if (receipt['operation']!='calculation_fact.saved:'+value['kind'] or receipt['request_hash']!=row['command_hash']
                    or receipt['user_id']!=row['created_by'] or receipt['request_id']!=command['request_id']
                    or receipt['fact_content_hash']!=row['content_hash'] or receipt['created_at']!=row['created_at'] or key in receipts):
                raise ValueError('Changed original calculation case receipt')
            receipts.add(key)
        if len(receipts)!=office.db.execute('SELECT COUNT(*) FROM business_payroll_calculation_case_events').fetchone()[0]:raise ValueError('Missing calculation case acceptance')
    except (Problem,KeyError,TypeError,ValueError,json.JSONDecodeError) as error:raise ValueError('Invalid calculation case archive') from error
    return True


def methods(path):
    if path in ('/payroll/calculation-cases','/payroll/travel-tax-policies'):return 'GET, POST'
    if path in ('/payroll/calculation-cases/preview','/payroll/travel-tax-policies/preview'):return 'POST'
    if path in ('/payroll/calculation-cases/sources','/payroll/travel-tax-policies/sources') or re.fullmatch(r'/payroll/(?:calculation-cases|travel-tax-policies)/'+ID+r'(?:/history)?',path):return 'GET'
    return None


def dispatch(office,actor,path,method,data):
    allowed=methods(path)
    if allowed is None:return None
    if method not in allowed.split(', '):raise Problem(405,'Methode für diese Gesamtfallroute nicht zulässig.')
    api=PayrollCalculationCases(office);policies=path.startswith('/payroll/travel-tax-policies')
    if method=='POST':
        if data.get('kind')!=('travel_tax_policy' if policies else 'calculation_case'):raise Problem(400,'Faktenart entspricht nicht der gewählten Route.')
        result=api.preview(actor,data) if path.endswith('/preview') else api.save(actor,data)
    else:
        _shape(data,('_query',));query=data.get('_query',{})
        if path=='/payroll/calculation-cases/sources':result=api.sources(actor,query)
        elif path=='/payroll/travel-tax-policies/sources':result=api.policy_sources(actor,query)
        elif path in ('/payroll/calculation-cases','/payroll/travel-tax-policies'):result=api.records(actor,query,policies=policies)
        else:_shape(query,());result=api.get(actor,path.split('/')[3],path.endswith('/history'))
    return result,200,'application/json'

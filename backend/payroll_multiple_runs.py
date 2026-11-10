"""Explicit Source5 run adapter; single full bonus with explicit separate payment allocations."""
import json
from copy import deepcopy

from core import Problem,canonical
from business_personnel_workflow import _shape
from business_payroll_facts import reference
from payroll_multiple_oneoff_2026 import MULTIPLE_RULE_VERSION
from payroll_verification import calculate_multiple_source,within_original_graph
from payroll_verification import once_per_original_graph

INPUT_FIELDS=('source_schema_version','employee_id','multiple_one_off_case_ref')
OPTIONAL_INPUT_FIELDS=INPUT_FIELDS+('settlement_review',)
SOURCE_FIELDS=('source_schema_version','employee_id','month','input','profile','preparation','calculation_case','multiple_one_off_case')


def calculate_run_source(source,*,rule_version=None):
    _shape(source,SOURCE_FIELDS,SOURCE_FIELDS);_shape(source['input'],OPTIONAL_INPUT_FIELDS,INPUT_FIELDS)
    if 'settlement_review' in source['input']:
        from payroll_multiple_corrections import normalize_review
        normalize_review(source['input']['settlement_review'])
    fact=source['multiple_one_off_case'];snapshot=fact['sources']['calculation_source'];running=snapshot['running_calculation_case']
    selected=next(value for value in running['sources']['profiles'] if reference(value)==running['plan']['selected_profile_ref'])
    if (type(source['source_schema_version']) is not int or source['source_schema_version']!=5
            or type(source['input']['source_schema_version']) is not int or source['input']['source_schema_version']!=5
            or source['input']['employee_id']!=source['employee_id'] or source['input']['multiple_one_off_case_ref']!=reference(fact)
            or fact['employee_id']!=source['employee_id'] or fact['kind']!='multiple_one_off_case' or fact['status']!='active'
            or fact['details']['month']!=source['month'] or snapshot['month']!=source['month']
            or source['calculation_case']!=running or source['profile']!=selected
            or source['preparation']!=running['sources']['period_case']['sources']['preparation']
            or fact['rule_version']!=MULTIPLE_RULE_VERSION or rule_version is not None and rule_version!=fact['rule_version']):
        raise Problem(400,'Einmalfall, laufender Originalfall und tatsächliche Lohnquelle widersprechen sich.')
    result=calculate_multiple_source(snapshot,rule_version=fact['rule_version'],source_contract_version=fact['source_contract_version'])
    from oneoff_provenance_compat import calculation_matches
    if not calculation_matches(snapshot,result,fact['plan']):raise Problem(400,'Angenommener Einmalfall ist nicht unverändert nachrechenbar.')
    return deepcopy(fact['plan'])


@within_original_graph
def prepare(payroll,actor,data):
    from business_payroll_multiple_cases import PayrollMultipleCases
    from business_personnel_workflow import _sha
    _shape(data,OPTIONAL_INPUT_FIELDS,INPUT_FIELDS)
    if type(data['source_schema_version']) is not int or data['source_schema_version']!=5:
        raise Problem(400,'Einmalbezüge benötigen ausdrücklich Quellenfassung 5.')
    _,employee=payroll._access(actor,data['employee_id'])
    fact=PayrollMultipleCases(payroll.office,clock=payroll.hr.clock).resolve_multiple_case(actor,employee['id'],data['multiple_one_off_case_ref'],fresh=True)
    running=fact['sources']['calculation_source']['running_calculation_case']
    selected=next(value for value in running['sources']['profiles'] if reference(value)==running['plan']['selected_profile_ref'])
    source=dict(source_schema_version=5,employee_id=employee['id'],month=fact['details']['month'],input=json.loads(canonical(data)),
        profile=selected,preparation=running['sources']['period_case']['sources']['preparation'],calculation_case=running,multiple_one_off_case=fact)
    calculation=calculate_run_source(source)
    value=dict(source=source,calculation=calculation)
    if not calculation['payroll_calculation_complete'] and 'settlement_review' in data:
        raise Problem(409,'Vollständigkeitsprüfung ist nur für eine vollständig berechenbare positive Korrektur zulässig.')
    if calculation['payroll_calculation_complete']:
        from payroll_multiple_corrections import prepare_transition
        previous=next((item for item in payroll._all('run',employee['id']) if item['source']['month']==source['month']),None)
        transition=prepare_transition(payroll,previous,value)
        if transition is not None:value['settlement_transition']=transition
    return dict(value,preview_hash=_sha(value),can_finalize=calculation['payroll_calculation_complete'])


@once_per_original_graph
def verify_record(payroll,record):
    from business_payroll_multiple_cases import PayrollMultipleCases,validate_case_sources,validate_run_consumption
    from payroll_travel_recording import validate_tax_recording
    if payroll._event(payroll._row(record['id'],'run',record['revision']))!=record:
        raise Problem(500,'Die historische Einmalfallquittung widerspricht dem tatsächlichen Lohnarchiv.')
    fact=record['source']['multiple_one_off_case']
    if PayrollMultipleCases(payroll.office)._get(fact['id'],fact['revision'])!=fact:
        raise Problem(500,'Die tatsächliche historische Einmalfallquelle wurde verändert.')
    try:
        validate_case_sources(payroll.office,fact);validate_tax_recording(payroll.office,record)
        validate_run_consumption(payroll.office,record)
    except ValueError as error:raise Problem(500,'Historische Einmalquellen, Anspruchsreservierung oder Steuererfassung sind nicht reproduzierbar.') from error
    if calculate_run_source(record['source'],rule_version=record['calculation']['rule_version'])!=record['calculation']:
        raise Problem(500,'Die historische Einmalfallberechnung wurde verändert.')
    if ('settlement_review' in record['source']['input'])!=('settlement_transition' in record):
        raise Problem(500,'Vollständigkeitsprüfung und angenommene Korrekturbindung müssen gemeinsam vorhanden sein.')
    if 'settlement_transition' in record:
        from payroll_multiple_corrections import verify_transition
        verify_transition(payroll,record)


def require_supported_correction(payroll,previous,current):
    if previous is None:return
    if 'settlement_transition' in current:
        from payroll_multiple_corrections import prepare_transition
        if prepare_transition(payroll,previous,current)!=current['settlement_transition']:
            raise Problem(409,'Die ursprüngliche Zahlungs- oder Abführungsbindung wurde geändert.')
        return
    version=previous['source'].get('source_schema_version')
    if version==3:
        if previous['source']['calculation_case']!=current['source']['calculation_case']:
            raise Problem(409,'Source5 übernimmt ausschließlich den unveränderten laufenden v5-Originalfall.')
    elif version!=5:raise Problem(409,'Dieser Quellenwechsel ist für den Source5-Einzelanspruch noch nicht geprüft.')
    from business_payroll_accounts import PayrollAccounts
    from payroll_multiple_payments import previous_actual_settlements
    accounts=PayrollAccounts(payroll.office)
    pending=dict(previous,revision=previous['revision']+1)
    paid=previous_actual_settlements(accounts,pending)
    for evidence in paid:
        old=payroll._event(payroll._row(previous['id'],'run',evidence['details']['run_revision']))
        payroll._verify_calculation_record(old)
        if old['source'].get('source_schema_version')!=3:
            raise Problem(409,'Eine bereits bezahlte Source5-Vorfassung benötigt den gesonderten Nachzahlungs- oder Rückzahlungsvertrag; unbezahlte Zwischenrevisionen heben diese Bindung nicht auf.')
        if old['source']['calculation_case']!=current['source']['calculation_case'] or old['calculation']!=current['calculation']['running_calculation']:
            raise Problem(409,'Eine frühere tatsächliche Zahlung gehört zu einer anderen laufenden Rechnung; vollständigen Differenzvertrag verwenden.')
    if paid and any(evidence['details']['payments']!=paid[-1]['details']['payments'] for evidence in paid):
        raise Problem(409,'Unterschiedliche tatsächliche Vorgängerzahlungen benötigen den gesonderten vollständigen Korrekturvertrag.')

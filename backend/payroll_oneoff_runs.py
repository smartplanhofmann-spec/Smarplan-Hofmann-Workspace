"""Explicit Source4 run adapter; frozen v5 running sources remain unchanged."""
import json

from core import Problem,canonical
from business_personnel_workflow import _shape
from business_payroll_facts import reference
from payroll_oneoff_composition_2026 import calculate_oneoff_source,ONEOFF_RULE_VERSION

INPUT_FIELDS=('source_schema_version','employee_id','one_off_case_ref')
SOURCE_FIELDS=('source_schema_version','employee_id','month','input','profile','preparation','calculation_case','one_off_case')


def calculate_run_source(source,*,rule_version=None):
    _shape(source,SOURCE_FIELDS,SOURCE_FIELDS);_shape(source['input'],INPUT_FIELDS,INPUT_FIELDS)
    fact=source['one_off_case'];snapshot=fact['sources']['calculation_source'];running=snapshot['running_calculation_case']
    selected=next(value for value in running['sources']['profiles'] if reference(value)==running['plan']['selected_profile_ref'])
    if (type(source['source_schema_version']) is not int or source['source_schema_version']!=4
            or type(source['input']['source_schema_version']) is not int or source['input']['source_schema_version']!=4
            or source['input']['employee_id']!=source['employee_id'] or source['input']['one_off_case_ref']!=reference(fact)
            or fact['employee_id']!=source['employee_id'] or fact['kind']!='one_off_case' or fact['status']!='active'
            or fact['details']['month']!=source['month'] or snapshot['month']!=source['month']
            or source['calculation_case']!=running or source['profile']!=selected
            or source['preparation']!=running['sources']['period_case']['sources']['preparation']
            or fact['rule_version']!=ONEOFF_RULE_VERSION or rule_version is not None and rule_version!=fact['rule_version']):
        raise Problem(400,'Einmalfall, laufender Originalfall und tatsächliche Lohnquelle widersprechen sich.')
    result=calculate_oneoff_source(snapshot,rule_version=fact['rule_version'],source_contract_version=fact['source_contract_version'])
    if fact['plan']!=result:raise Problem(400,'Angenommener Einmalfall ist nicht unverändert nachrechenbar.')
    return result


def prepare(payroll,actor,data):
    from business_payroll_oneoff_cases import PayrollOneoffCases
    from business_personnel_workflow import _sha
    _shape(data,INPUT_FIELDS,INPUT_FIELDS)
    if type(data['source_schema_version']) is not int or data['source_schema_version']!=4:
        raise Problem(400,'Einmalbezüge benötigen ausdrücklich Quellenfassung 4.')
    _,employee=payroll._access(actor,data['employee_id'])
    fact=PayrollOneoffCases(payroll.office,clock=payroll.hr.clock).resolve_one_off_case(actor,employee['id'],data['one_off_case_ref'],fresh=True)
    running=fact['sources']['calculation_source']['running_calculation_case']
    selected=next(value for value in running['sources']['profiles'] if reference(value)==running['plan']['selected_profile_ref'])
    source=dict(source_schema_version=4,employee_id=employee['id'],month=fact['details']['month'],input=json.loads(canonical(data)),
        profile=selected,preparation=running['sources']['period_case']['sources']['preparation'],calculation_case=running,one_off_case=fact)
    calculation=calculate_run_source(source)
    return dict(source=source,calculation=calculation,preview_hash=_sha(dict(source=source,calculation=calculation)),
        can_finalize=calculation['payroll_calculation_complete'])


def verify_record(payroll,record):
    from business_payroll_oneoff_cases import PayrollOneoffCases,validate_case_sources,validate_run_consumption
    from payroll_travel_recording import validate_tax_recording
    if payroll._event(payroll._row(record['id'],'run',record['revision']))!=record:
        raise Problem(500,'Die historische Einmalfallquittung widerspricht dem tatsächlichen Lohnarchiv.')
    fact=record['source']['one_off_case']
    if PayrollOneoffCases(payroll.office)._get(fact['id'],fact['revision'])!=fact:
        raise Problem(500,'Die tatsächliche historische Einmalfallquelle wurde verändert.')
    try:
        validate_case_sources(payroll.office,fact);validate_tax_recording(payroll.office,record)
        validate_run_consumption(payroll.office,record)
    except ValueError as error:raise Problem(500,'Historische Einmalquellen, Anspruchsreservierung oder Steuererfassung sind nicht reproduzierbar.') from error
    if calculate_run_source(record['source'],rule_version=record['calculation']['rule_version'])!=record['calculation']:
        raise Problem(500,'Die historische Einmalfallberechnung wurde verändert.')

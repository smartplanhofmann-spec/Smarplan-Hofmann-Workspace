"""Explicit V15 Source4 adapter; immutable V6 run arithmetic remains intact."""
from copy import deepcopy

from core import Problem
from business_personnel_workflow import _shape
from business_payroll_facts import reference
from payroll_oneoff_runs import INPUT_FIELDS,SOURCE_FIELDS
from payroll_factor_oneoff_composition_2026 import RULE_VERSION,SOURCE_CONTRACT_VERSION,calculate_source,calculation_matches


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
            or fact['rule_version']!=RULE_VERSION or type(fact['source_contract_version']) is not int
            or fact['source_contract_version']!=SOURCE_CONTRACT_VERSION
            or rule_version is not None and rule_version!=RULE_VERSION):
        raise Problem(400,'Faktor-Einmalfall, laufender Originalfall und tatsächliche Lohnquelle widersprechen sich.')
    result=calculate_source(snapshot,rule_version=RULE_VERSION,source_contract_version=SOURCE_CONTRACT_VERSION)
    if not calculation_matches(snapshot,result,fact['plan']):
        raise Problem(400,'Angenommener Faktor-Einmalfall ist nicht unverändert nachrechenbar.')
    return deepcopy(fact['plan'])


def verify_record(payroll,record):
    from business_payroll_oneoff_cases import PayrollOneoffCases,validate_case_sources,validate_run_consumption
    from payroll_travel_recording import validate_tax_recording
    if payroll._event(payroll._row(record['id'],'run',record['revision']))!=record:
        raise Problem(500,'Die historische Faktor-Einmalfallquittung widerspricht dem tatsächlichen Lohnarchiv.')
    fact=record['source']['one_off_case']
    if PayrollOneoffCases(payroll.office)._get(fact['id'],fact['revision'])!=fact:
        raise Problem(500,'Die tatsächliche historische Faktor-Einmalfallquelle wurde verändert.')
    try:
        validate_case_sources(payroll.office,fact);validate_tax_recording(payroll.office,record)
        validate_run_consumption(payroll.office,record)
    except ValueError as error:
        raise Problem(500,'Historische Faktor-Einmalquellen, Anspruchsreservierung oder Steuererfassung sind nicht reproduzierbar.') from error
    if calculate_run_source(record['source'],rule_version=record['calculation']['rule_version'])!=record['calculation']:
        raise Problem(500,'Die historische Faktor-Einmalfallberechnung wurde verändert.')

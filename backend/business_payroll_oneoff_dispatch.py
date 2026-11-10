"""Version selection from authorized immutable cases, never client totals."""
import json

from core import Problem,canonical
from business_personnel_workflow import _shape,_sha
from business_payroll_facts import reference
from payroll_oneoff_runs import INPUT_FIELDS


def adapter(source):
    from payroll_oneoff_composition_2026 import ONEOFF_RULE_VERSION
    from payroll_factor_oneoff_composition_2026 import RULE_VERSION
    version=source['one_off_case']['rule_version']
    if version==RULE_VERSION:
        import payroll_factor_oneoff_runs as selected
    elif version==ONEOFF_RULE_VERSION:
        import payroll_oneoff_runs as selected
    else:raise Problem(400,'Unbekannte ausdrückliche Einmalbezugsregel im tatsächlichen Originalfall.')
    return selected


def prepare(payroll,actor,data):
    from business_payroll_oneoff_cases import PayrollOneoffCases
    _shape(data,INPUT_FIELDS,INPUT_FIELDS)
    if type(data['source_schema_version']) is not int or data['source_schema_version']!=4:
        raise Problem(400,'Einmalbezüge benötigen ausdrücklich Quellenfassung 4.')
    _,employee=payroll._access(actor,data['employee_id'])
    fact=PayrollOneoffCases(payroll.office,clock=payroll.hr.clock).resolve_one_off_case(actor,employee['id'],data['one_off_case_ref'],fresh=True)
    running=fact['sources']['calculation_source']['running_calculation_case']
    selected=next(value for value in running['sources']['profiles'] if reference(value)==running['plan']['selected_profile_ref'])
    source=dict(source_schema_version=4,employee_id=employee['id'],month=fact['details']['month'],input=json.loads(canonical(data)),
        profile=selected,preparation=running['sources']['period_case']['sources']['preparation'],calculation_case=running,one_off_case=fact)
    calculation=adapter(source).calculate_run_source(source)
    return dict(source=source,calculation=calculation,preview_hash=_sha(dict(source=source,calculation=calculation)),
        can_finalize=calculation['payroll_calculation_complete'])

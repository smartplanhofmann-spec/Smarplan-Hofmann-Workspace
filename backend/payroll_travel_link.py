"""Narrow current/historical travel processing proof without private raw DTOs."""
from core import Problem
from business_personnel_workflow import _sha
from business_payroll_facts import reference,ref
from business_operations import transaction


def _proof(office,run,settlement_ref,month,source_hash):
    from business_payroll import Payroll
    if (run['source'].get('source_schema_version') not in (3,4) or run['source']['month']!=month
            or not run['calculation']['payroll_calculation_complete'] or run['status']!='calculation_recorded'):
        raise Problem(409,'Vollständig angenommener passender neuer Lohnlauf erforderlich.')
    Payroll(office)._verify_calculation_record(run)
    matches=[value for value in run['source']['calculation_case']['sources']['travel_sources']
        if value['settlement_ref']==settlement_ref and value['month']==month and value['source_hash']==source_hash]
    if len(matches)!=1:raise Problem(409,'Lohnlauf verarbeitet nicht genau diese unveränderliche Reisequelle.')
    source=matches[0]
    value=dict(schema_version=1,run_ref=reference(run),settlement_ref=settlement_ref,month=month,source_hash=source_hash,
        allocation_keys=[value['key'] for value in source['allocations']],letter_m=source['letter_m'])
    return dict(value,processing_hash=_sha(value))


def assert_travel_processed(office,actor,settlement_ref,month,source_hash):
    from business_payroll import Payroll
    from travel_payroll_sources import travel_payroll_source
    with transaction(office):
        adapter=travel_payroll_source(office,actor,ref(settlement_ref),month)
        if adapter['source_hash']!=source_hash:raise Problem(409,'Reise-Lohnquelle wurde verändert.')
        api=Payroll(office);api._access(actor,adapter['employee_id'])
        runs=[value for value in api._all('run',adapter['employee_id']) if value['source']['month']==month]
        if len(runs)!=1:raise Problem(409,'Die Reisequelle benötigt zuerst ihren vollständig angenommenen Lohnlauf.')
        return _proof(office,runs[0],settlement_ref,month,source_hash)


def validate_travel_processing(office,proof,settlement_ref,month,source_hash):
    from business_payroll import Payroll
    try:
        value=ref(proof['run_ref']);api=Payroll(office);run=api._event(api._row(value['id'],'run',value['revision']))
        if reference(run)!=value or _proof(office,run,settlement_ref,month,source_hash)!=proof:
            raise ValueError('Changed original travel payroll processing proof')
        return True
    except (Problem,KeyError,TypeError,ValueError) as error:raise ValueError('Invalid historical travel payroll processing') from error

"""Actual immutable travel flat-tax treatment, atomically bound to a payroll run.

Creating this event records payroll tax treatment only. It is neither an actual
payment nor a statutory transmission. Preview/calculation-case sources retain
their explicit planned context and are never rewritten as completed actions.
"""
import json

from core import Problem,canonical
from business_personnel_workflow import _sha
from business_payroll_facts import reference

FEATURES=('payroll_travel_tax_recording',)
TABLES=('business_payroll_travel_tax_recordings',)


def schema_statements(binary_type='BYTEA'):
    return ['''CREATE TABLE IF NOT EXISTS business_payroll_travel_tax_recordings(
        run_id TEXT NOT NULL,run_revision INTEGER NOT NULL,payload_json TEXT NOT NULL,content_hash TEXT NOT NULL,
        created_by TEXT NOT NULL REFERENCES users(id),created_at TEXT NOT NULL,PRIMARY KEY(run_id,run_revision),
        FOREIGN KEY(run_id,run_revision) REFERENCES business_payroll_events(id,revision))''']


def protected_tables():return TABLES
def runtime_privileges():return {TABLES[0]:('SELECT','INSERT')}


def guard_statements(dialect):
    table=TABLES[0]
    if dialect=='sqlite':
        return [f"CREATE TRIGGER IF NOT EXISTS {table}_{action.lower()}_guard BEFORE {action} ON {table} BEGIN SELECT RAISE(ABORT,'immutable payroll tax recording'); END" for action in ('UPDATE','DELETE')]+[
            f"CREATE TRIGGER IF NOT EXISTS {table}_insert_guard BEFORE INSERT ON {table} WHEN EXISTS(SELECT 1 FROM {table} WHERE run_id=NEW.run_id AND run_revision=NEW.run_revision) BEGIN SELECT RAISE(ABORT,'immutable payroll tax recording'); END"]
    if dialect=='postgresql':
        output=["CREATE OR REPLACE FUNCTION business_payroll_travel_tax_immutable_guard() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'immutable payroll tax recording'; END; $$"]
        for action in ('UPDATE','DELETE'):
            name=table+'_'+action.lower()+'_guard'
            output.append(f"DO $$ BEGIN IF NOT EXISTS(SELECT 1 FROM pg_trigger WHERE tgname='{name}' AND tgrelid='{table}'::regclass) THEN CREATE TRIGGER {name} BEFORE {action} ON {table} FOR EACH ROW EXECUTE FUNCTION business_payroll_travel_tax_immutable_guard(); END IF; END $$")
        return output
    raise ValueError('Unsupported payroll tax recording guard')


def _expected(run):
    if run.get('source',{}).get('source_schema_version')!=3:return None
    case=run['source']['calculation_case'];flat=case['sources']['flat_travel_tax']
    if flat is None:return None
    calculation=flat['calculation'];planned=flat['recording_context']
    if (planned['actual_recorded'] is not False or planned['planned_recording_on']!=run['created_at'][:10]
            or flat['parameters']['evidence']['taxation_recorded_on']!=run['created_at'][:10]
            or run['status']!='calculation_recorded' or not run['calculation']['payroll_calculation_complete']
            or not calculation['can_calculate'] or case['details']['flat_tax_decision']['record_on_finalize'] is not True):
        raise Problem(409,'Pauschalsteuer-Erfassung benötigt genau den beauftragten tatsächlichen Lohnabschluss am vorgesehenen Tag.')
    return dict(schema_version=1,kind='payroll_travel_flat_tax_recording',run_ref=reference(run),calculation_case_ref=reference(case),
        policy_ref=calculation['policy_ref'],policy_key=calculation['policy_key'],policy_choice_hash=calculation['policy_choice_hash'],
        employee_id=run['employee_id'],month=run['source']['month'],flat_calculation_hash=calculation['calculation_hash'],
        travel_source_hashes=[value['source_hash'] for value in case['sources']['travel_sources'] if value['flat_taxable_payroll_minor']],
        amount_minor=calculation['amount_minor'],wage_tax_minor=calculation['wage_tax_minor'],solidarity_minor=calculation['solidarity_minor'],
        church_tax_minor=calculation['church_tax_minor'],statutory_employer_due_minor=calculation['statutory_employer_due_minor'],
        employee_tax_shift_minor=calculation['employee_tax_minor'],social_exempt=calculation['social_exempt'],
        actual_recorded=True,actual_payment_created=False,statutory_transmitted=False,recorded_on=run['created_at'][:10],
        created_by=run['created_by'],created_at=run['created_at'])


def record_tax_treatment(office,actor,run):
    """Call inside the existing payroll finalize transaction, after append."""
    value=_expected(run)
    if value is None:return None
    if actor['id']!=run['created_by']:raise Problem(403,'Steuererfassung muss vom tatsächlichen angenommenen Abschluss stammen.')
    require_uniform_recorded_policy(office,run['source']['calculation_case']['sources']['flat_travel_tax']['policy']['details'])
    office.db.execute('INSERT INTO business_payroll_travel_tax_recordings(run_id,run_revision,payload_json,content_hash,created_by,created_at) VALUES(?,?,?,?,?,?)',
        (run['id'],run['revision'],canonical(value),_sha(value),run['created_by'],run['created_at']))
    return dict(value,content_hash=_sha(value))


def require_uniform_recorded_policy(office,details):
    """Voiding a policy cannot erase the method used by an effective run.

    Correcting every affected payroll run may remove that effective use, but
    an archive-only policy revision never does. Historical proofs stay intact.
    """
    from business_schema import _tables
    if TABLES[0] not in _tables(office):return
    from business_payroll import Payroll
    payroll=Payroll(office)
    rows=office.db.execute('SELECT t.run_id,t.run_revision FROM business_payroll_travel_tax_recordings t '
        'WHERE NOT EXISTS (SELECT 1 FROM business_payroll_events n WHERE n.id=t.run_id AND n.revision>t.run_revision)').fetchall()
    for row in rows:
        run=payroll._event(payroll._row(row['run_id'],'run',row['run_revision']))
        validate_tax_recording(office,run)
        prior=run['source']['calculation_case']['sources']['flat_travel_tax']['policy']['details']
        if (max(prior['filing_period_from'],details['filing_period_from'])<=min(prior['filing_period_to'],details['filing_period_to'])
                and prior['church_method']!=details['church_method']):
            raise Problem(409,'Eine wirksame tatsächliche Lohnsteuererfassung dieses Zeitraums bindet bereits das andere Kirchensteuerverfahren.')


def validate_tax_recording(office,run):
    expected=_expected(run)
    row=office.db.execute('SELECT * FROM business_payroll_travel_tax_recordings WHERE run_id=? AND run_revision=?',(run['id'],run['revision'])).fetchone()
    if expected is None:
        if row is not None:raise ValueError('Unexpected payroll tax recording')
        return None
    if (row is None or json.loads(row['payload_json'])!=expected or row['content_hash']!=_sha(expected)
            or row['created_by']!=run['created_by'] or row['created_at']!=run['created_at']):
        raise ValueError('Missing or changed actual payroll travel tax recording')
    return dict(expected,content_hash=row['content_hash'])


def validate_integrity(office):
    from business_schema import _tables
    if TABLES[0] not in _tables(office):return True
    from business_payroll import Payroll,_calculate_source
    from business_payroll_calculation_cases import validate_case_sources
    api=Payroll(office);expected=set()
    try:
        for row in office.db.execute("SELECT id,revision FROM business_payroll_events WHERE kind='run'"):
            run=api._event(api._row(row['id'],'run',row['revision']))
            if run['source'].get('source_schema_version')!=3:continue
            validate_case_sources(office,run['source']['calculation_case'])
            if _calculate_source(run['source'],rule_version=run['calculation']['rule_version'])!=run['calculation']:raise ValueError('Changed recorded payroll calculation')
            if validate_tax_recording(office,run) is not None:expected.add((run['id'],run['revision']))
        actual={(row['run_id'],row['run_revision']) for row in office.db.execute('SELECT run_id,run_revision FROM business_payroll_travel_tax_recordings')}
        if actual!=expected:raise ValueError('Orphan payroll tax recording')
    except (Problem,KeyError,ValueError,TypeError,json.JSONDecodeError) as error:raise ValueError('Invalid payroll travel tax recording archive') from error
    return True

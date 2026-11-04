"""Pure explicit settlement of one Source5 bonus and its unchanged running pay.

This validates actual transfer parts and exact private allocations. It performs
no persistence, bank operation, claim consumption or Cash/EÜR import. A private
resolver must establish source authority, fresh rights, and the actual clock.
"""
from copy import deepcopy
import unicodedata

from core import Problem
from payroll_oneoff_2026 import _shape, _date, _int
from payroll_multiple_oneoff_2026 import MULTIPLE_RULE_VERSION, calculate_multiple_source, sha


PAYMENT_CONTRACT='source5_single_other_payment_settlement_v1'


def _payment_key(payment):
    return payment['paid_on'],unicodedata.normalize('NFKC',payment['payment_reference']).casefold()


def build_single_payment_plan(snapshot,*,payments,allocations,as_of,prior_settlement=None):
    """Bind exact net obligations to real dates without inventing gross ratios.

    Only one complete regular original bonus is supported. Its statutory gross
    and net come from the verified composition. A prior paid v5 run must contain
    precisely the same running case; its original transfer parts are retained
    verbatim in their original order and cannot be relabelled as bonus payments.
    """
    result=calculate_multiple_source(snapshot,rule_version=MULTIPLE_RULE_VERSION,source_contract_version=1)
    details=result['multiple_one_off_details'];events=details['receipt_events']
    if not result['payroll_calculation_complete'] or len(events)!=1 or 'single_original_calculation' not in details:
        raise Problem(409,'Tatsächliche Nettozuordnung benötigt einen vollständigen einzelnen Einmalanspruch ohne ungeklärte Steuergruppe.')
    _date(as_of);event=events[0];running=result['running_calculation']
    running_due=running['net_minor']-running['net_deductions_minor']
    total_due=result['net_minor']-result['net_deductions_minor'];bonus_due=total_due-running_due
    if running_due<0 or bonus_due<=0:
        raise Problem(409,'Rückzahlungen, negative Forderungen und Verrechnungen benötigen ihren eigenen belegten Zahlungszweig.')
    if not isinstance(payments,list) or not 1<=len(payments)<=20 or not isinstance(allocations,list) or len(allocations)!=len(payments):
        raise Problem(400,'Ein bis zwanzig echte Zahlungsteile und genau ihre einzelnen Zuordnungen erforderlich.')
    seen=set();payment_total=0
    for payment in payments:
        _shape(payment,'paid_on amount_minor payment_reference');day=_date(payment['paid_on']);_int(payment['amount_minor'],1)
        value=payment['payment_reference']
        if (not isinstance(value,str) or not value.strip() or value.strip()!=value or len(value)>200
                or any(ord(c)<32 or ord(c)==127 or 0xD800<=ord(c)<=0xDFFF for c in value)):
            raise Problem(400,'Eindeutige unveränderte tatsächliche Zahlungsreferenz erforderlich.')
        if day.year!=2026 or payment['paid_on'][:7]<snapshot['month'] or payment['paid_on']>as_of:
            raise Problem(400,'Der echte Zahlungstag muss ab dem Lohnmonat bis zum Prüfdatum im unterstützten Jahr 2026 liegen.')
        key=_payment_key(payment)
        if key in seen:raise Problem(409,'Eine tatsächliche Überweisung darf nicht durch mehrere private Zuordnungen dupliziert werden.')
        seen.add(key);payment_total+=payment['amount_minor']
    indexes=set();running_total=0;bonus_total=0;normalized=[]
    for allocation in allocations:
        _shape(allocation,'payment_index running_minor one_off_allocations')
        index=allocation['payment_index'];_int(index,0,len(payments)-1);_int(allocation['running_minor'])
        if index in indexes:raise Problem(409,'Jeder tatsächliche Zahlungsteil benötigt genau eine vollständige Zuordnung.')
        indexes.add(index);oneoffs=allocation['one_off_allocations']
        if not isinstance(oneoffs,list) or len(oneoffs)>1:raise Problem(400,'Dieser Zahlungszweig bindet genau einen möglichen Einmalanspruch.')
        bonus=0
        for part in oneoffs:
            _shape(part,'event_key net_minor');_int(part['net_minor'],1)
            if part['event_key']!=event['event_key']:raise Problem(409,'Zahlungszuordnung verweist auf ein anderes Bruttozuflussereignis.')
            if payments[index]['paid_on']!=event['receipt_date']:
                raise Problem(409,'Der tatsächlich erfüllte Bonus muss am belegten steuerlichen und sozialversicherungsrechtlichen Zuflusstag gezahlt sein.')
            bonus+=part['net_minor']
        if allocation['running_minor']+bonus!=payments[index]['amount_minor']:
            raise Problem(409,'Private Erfüllungszuordnungen müssen genau den tatsächlichen Zahlungsteil ergeben.')
        running_total+=allocation['running_minor'];bonus_total+=bonus;normalized.append(deepcopy(allocation))
    normalized.sort(key=lambda value:value['payment_index'])
    if running_total!=running_due or bonus_total!=bonus_due or payment_total!=total_due:
        raise Problem(409,'Tatsächliche Zahlungen müssen laufendes Netto und den einzelnen Bonus jeweils exakt erfüllen; eine Nettoquote genügt nicht.')
    prior_count=0;prior_refs=None
    if prior_settlement is not None:
        _shape(prior_settlement,'run payment');old=prior_settlement['run'];paid=prior_settlement['payment']
        if (old.get('kind')!='run' or old.get('employee_id')!=snapshot['employee_id']
                or old.get('source',{}).get('source_schema_version')!=3 or old['source']['month']!=snapshot['month']
                or old['source']['calculation_case']!=snapshot['running_calculation_case'] or old['calculation']!=running
                or paid.get('kind')!='payment' or paid.get('employee_id')!=snapshot['employee_id']
                or paid['details']['run_id']!=old['id'] or paid['details']['run_revision']!=old['revision']
                or paid['sources']['run']!=old):
            raise Problem(409,'Übernahme benötigt den tatsächlichen bezahlten v5-Lauf mit exakt derselben laufenden Originalrechnung.')
        old_parts=paid['details']['payments'];prior_count=len(old_parts)
        if sum(value['amount_minor'] for value in old_parts)!=running_due or payments[:prior_count]!=old_parts:
            raise Problem(409,'Alle bereits bezahlten laufenden Originalteile bleiben mit Betrag, Datum, Referenz und Reihenfolge erhalten.')
        if any(normalized[index]['running_minor']!=old_parts[index]['amount_minor'] or normalized[index]['one_off_allocations'] for index in range(prior_count)):
            raise Problem(409,'Ein bereits bezahlter laufender Teil darf nicht nachträglich als Bonuszahlung bezeichnet werden.')
        prior_refs={kind:{key:value[key] for key in ('id','revision','content_hash')} for kind,value in (('run',old),('payment',paid))}
    plan=dict(schema_version=1,contract=PAYMENT_CONTRACT,employee_id=snapshot['employee_id'],month=snapshot['month'],
        composition_hash=sha(result),event_key=event['event_key'],bonus_receipt_date=event['receipt_date'],
        running_net_minor=running_due,one_off_net_minor=bonus_due,total_net_minor=total_due,
        payments=deepcopy(payments),allocations=normalized,prior_settlement_refs=prior_refs,
        preserved_prior_payment_indexes=list(range(prior_count)),new_payment_indexes=list(range(prior_count,len(payments))),
        actual_payment_created=False,cash_import_created=False,claim_consumption_created=False)
    return dict(plan,plan_hash=sha(plan))


def resolve_single_payment_plan(accounts,run,details):
    """Read exact accepted originals; private caller owns fresh personnel rights."""
    from business_payroll_facts import ref,reference
    prior=None;value=details['prior_payment_ref']
    if value is not None:
        value=ref(value);paid=accounts._get(value['id'],value['revision'])
        if paid['employee_id']!=run['employee_id'] or paid['kind']!='payment' or reference(paid)!=value:
            raise Problem(409,'Vorherige Zahlung benötigt genau ihre tatsächliche private Originalfassung.')
        if run['revision']<2:raise Problem(409,'Ein neuer Erstlauf kann keinen vorherigen Monatslauf übernehmen.')
        if paid['details']['run_id']!=run['id'] or paid['details']['run_revision']>=run['revision']:
            raise Problem(409,'Übernommene Zahlung muss zu einer früheren tatsächlichen Revision desselben Lohnlaufs gehören.')
        old=accounts.payroll._event(accounts.payroll._row(run['id'],'run',paid['details']['run_revision']))
        accounts.payroll._verify_calculation_record(old)
        normalized,sources,_=accounts._normalize(run['employee_id'],'payment',paid['details'])
        if normalized!=paid['details'] or sources!=paid['sources']:
            raise Problem(500,'Vorherige tatsächliche Zahlung ist nicht unverändert rekonstruierbar.')
        import json
        receipts=accounts.db.execute('SELECT result_json FROM business_payroll_account_requests WHERE user_id=?',(paid['created_by'],)).fetchall()
        if sum(json.loads(row['result_json'])==paid for row in receipts)!=1:
            raise Problem(500,'Ursprüngliche Annahme der übernommenen Zahlung fehlt oder ist doppelt vorhanden.')
        original=accounts.hr._file(paid['source_file']['id'],run['employee_id'])
        if any(original[key]!=paid['source_file'][key] for key in paid['source_file']):
            raise Problem(500,'Vorheriger privater Zahlungsbeleg wurde verändert.')
        prior=dict(run=old,payment=paid)
    return build_single_payment_plan(run['source']['multiple_one_off_case']['sources']['calculation_source'],
        payments=details['payments'],allocations=details['settlement_allocations'],as_of=accounts.hr.now()[:10],prior_settlement=prior)


def previous_actual_settlements(accounts,run):
    """Latest evidence of every prior revision, never just its direct parent.

    An unpaid intermediate revision cannot erase a previously accepted transfer.
    Different prior settlement amounts/references require a separate correction
    contract; the first Source5 branch does not invent which transfer disappeared.
    """
    values=[record for record in accounts._all(run['employee_id']) if record['kind']=='payment'
        and record['details']['run_id']==run['id'] and record['details']['run_revision']<run['revision']]
    return sorted(values,key=lambda item:(item['details']['run_revision'],item['revision']))


def require_current_prior_settlement(accounts,run,details):
    """New acceptance binds the last real paid original across the run chain."""
    from business_payroll_facts import reference
    prior=previous_actual_settlements(accounts,run)
    for paid in prior:
        old=accounts.payroll._event(accounts.payroll._row(run['id'],'run',paid['details']['run_revision']))
        accounts.payroll._verify_calculation_record(old)
        if old['source'].get('source_schema_version')!=3:
            raise Problem(409,'Bereits bezahlte frühere Source5-Revision benötigt ihren gesonderten Korrekturvertrag.')
        if old['source']['calculation_case']!=run['source']['calculation_case'] or old['calculation']!=run['calculation']['running_calculation']:
            raise Problem(409,'Frühere echte Zahlung gehört zu einer anderen laufenden Rechnung; keine unveränderte Übernahme ohne Differenzvertrag.')
    if prior and any(paid['details']['payments']!=prior[-1]['details']['payments'] for paid in prior):
        raise Problem(409,'Mehrere unterschiedliche tatsächliche frühere Zahlungsfassungen benötigen ihren vollständigen Korrekturvertrag.')
    expected=reference(prior[-1]) if prior else None
    if details['prior_payment_ref']!=expected:
        raise Problem(409,'Die letzte tatsächliche vorherige Zahlung der vollständigen Laufkette muss unverändert gebunden sein; unbezahlte Zwischenrevisionen entfernen keine Zahlung.')

"""Additive Source5 positive net correction with immutable original transfers.

No new gross event, payment creation, debt waiver, tax transmission or mutation
of the v1 settlement is performed here. V2 retains its actual same-day contract;
V3 binds later actual positive transfers to the unchanged original gross event.
Both require a separately corrected complete source.
"""
from payroll_verification import within_original_graph
from copy import deepcopy
import json

from core import Problem,canonical
from business_payroll_facts import reference,ref
from business_personnel_workflow import _shape,_integer,_sha
from payroll_cash_sources import calculated
from payroll_multiple_payments import _payment_key,previous_actual_settlements

TRANSITION_CONTRACT='source5_positive_net_correction_v1'
PAYMENT_CONTRACT='source5_positive_net_correction_v2'
PAYMENT_DATES_CONTRACT='source5_positive_net_correction_v3'
TRANSITION_FIELDS=('schema_version','contract','employee_id','month','previous_run_ref','prior_run_ref',
    'prior_payment_ref','prior_plan_hash','old_composition_hash','new_composition_hash','component_key',
    'event_key','receipt_date','running_net_minor','prior_total_net_minor','total_net_minor',
    'additional_net_minor','remittance_observation','transition_hash')
TRANSITION_FIELDS=TRANSITION_FIELDS+('settlement_review',)


def _error(message):raise Problem(409,message)


def _hash(value):
    if not isinstance(value,str) or len(value)!=64 or any(c not in '0123456789abcdef' for c in value):
        _error('Vollständige unveränderte Korrekturbindung erforderlich.')
    return value


def due(calculation):return calculation['net_minor']-calculation['net_deductions_minor']


def normalize_review(value):
    if isinstance(value,dict) and value.get('schema_version')==3:
        from payroll_multiple_adjustments import normalize_review as adjustment_review
        return adjustment_review(value)
    if isinstance(value,dict) and value.get('schema_version')==2:
        from payroll_multiple_repayments import normalize_review as repayment_review
        return repayment_review(value)
    _shape(value,('schema_version','payments_complete','remittances_complete','evidence_ref'),
        ('schema_version','payments_complete','remittances_complete','evidence_ref'))
    if (type(value['schema_version']) is not int or value['schema_version']!=1
            or value['payments_complete'] is not True or value['remittances_complete'] is not True):
        _error('Sämtliche tatsächlichen Zahlungen und Abführungen ausdrücklich vollständig bestätigen.')
    evidence=ref(value['evidence_ref'])
    if evidence['revision']!=1:_error('Konkretes unverändertes Personaloriginal zur Vollständigkeitsprüfung auswählen.')
    return dict(value,evidence_ref=evidence)


def _review_evidence(payroll,value,employee_id,*,fresh):
    from business_payroll_facts import PayrollFacts
    value=normalize_review(value)
    files=PayrollFacts(payroll.office,clock=payroll.hr.clock)._files(employee_id,[value['evidence_ref']['id']],fresh=fresh)
    if len(files)!=1 or files[0]['content_hash']!=value['evidence_ref']['content_hash']:
        _error('Vollständigkeitserklärung benötigt genau ihren ursprünglichen privaten Personalbeleg.')
    return value


def _single(run):
    from payroll_multiple_runs import calculate_run_source
    source=run['source'];calculation=run['calculation']
    if source.get('source_schema_version')!=5 or not calculation['payroll_calculation_complete']:
        _error('Positive Korrektur benötigt einen vollständigen Source5-Einzelanspruch.')
    if calculate_run_source(source,rule_version=calculation['rule_version'])!=calculation:
        _error('Korrekturquelle ist nicht unverändert nachgerechnet.')
    parts=source['multiple_one_off_case']['sources']['calculation_source']['components']
    events=calculation['multiple_one_off_details']['receipt_events']
    if len(parts)!=1 or len(events)!=1 or len(parts[0]['planned_receipts'])!=1:
        _error('Dieser Korrekturvertrag umfasst genau einen unveränderten Bruttozufluss.')
    return source,calculation,parts[0],events[0]


def _same_subject(old,current):
    old_source,old_calc,old_part,old_event=_single(old)
    source,calc,part,event=_single(current)
    if (old_source['employee_id']!=source['employee_id'] or old_source['month']!=source['month']
            or old_source['calculation_case']!=source['calculation_case']
            or old_calc['running_calculation']!=calc['running_calculation']
            or old_part!=part or old_event!=event):
        _error('Laufender Originalfall, Anspruch, Brutto und Zuflusstag dürfen nicht verändert werden.')
    old_extra=old_calc['multiple_one_off_details']['single_original_calculation']['one_off_details']
    extra=calc['multiple_one_off_details']['single_original_calculation']['one_off_details']
    # A cross-year/period assignment correction requires its own consumer proof.
    anchors=('tax_year','social_year','assigned_period_ref','assigned_period_end')
    if (any(old_extra['assignment'][k]!=extra['assignment'][k] for k in anchors)
            or old_extra['assigned_part_key']!=extra['assigned_part_key']):
        _error('Ein Wechsel der steuerlichen oder sozialrechtlichen Zuordnung benötigt einen eigenen Korrekturvertrag.')
    return source,calc,part,event


def _resolved_payment(accounts,run,record):
    if record['kind']!='payment' or record['employee_id']!=run['source']['employee_id'] or record['revision']!=1:
        _error('Genau eine unveränderte ursprüngliche Zahlungsannahme je früherer Laufrevision erforderlich.')
    details=record['details']
    if details['run_id']!=run['id'] or not 0<details['run_revision']<run['revision']:
        _error('Vorherige Zahlung muss zu einer früheren Revision desselben Lohnlaufs gehören.')
    old=accounts.payroll._event(accounts.payroll._row(run['id'],'run',details['run_revision']))
    accounts.payroll._verify_calculation_record(old)
    normalized,sources,_=accounts._normalize(record['employee_id'],'payment',details)
    if normalized!=details or sources!=record['sources']:
        _error('Vorherige tatsächliche Zahlung ist nicht unverändert rekonstruierbar.')
    receipts=accounts.db.execute('SELECT result_json FROM business_payroll_account_requests WHERE user_id=?',(record['created_by'],)).fetchall()
    if sum(json.loads(row['result_json'])==record for row in receipts)!=1:
        _error('Ursprüngliche eindeutige Annahme der vorherigen Zahlung fehlt.')
    original=accounts.hr._file(record['source_file']['id'],record['employee_id'])
    if any(original[k]!=record['source_file'][k] for k in record['source_file']):
        _error('Geschützter vorheriger Zahlungsbeleg wurde verändert.')
    return dict(run=old,payment=record)


def _prior_chain(accounts,previous,current):
    pending=dict(previous,revision=previous['revision']+1)
    records=previous_actual_settlements(accounts,pending)
    if not records:return None
    resolved=[_resolved_payment(accounts,pending,value) for value in records]
    if all(value['run']['source'].get('source_schema_version')==3 for value in resolved):return None
    prior=resolved[-1]
    if prior['run']['source'].get('source_schema_version')!=5:
        _error('Letzte tatsächliche Zahlung muss eine vollständige Source5-Abrechnung erfüllen.')
    _same_subject(prior['run'],current)
    latest=prior['payment']['details']['payments'];old_calc=prior['run']['calculation']
    if sum(p['amount_minor'] for p in latest)!=due(old_calc):_error('Vorherige Nettoverpflichtung ist nicht vollständig erfüllt.')
    for entry in resolved:
        old=entry['run'];parts=entry['payment']['details']['payments']
        if latest[:len(parts)]!=parts:
            _error('Frühere tatsächliche Zahlungen bilden keinen unveränderten vollständigen Präfix.')
        if old['source'].get('source_schema_version')==5:
            _same_subject(old,current)
            allocations=entry['payment']['details']['settlement_allocations']
            if prior['payment']['details']['settlement_allocations'][:len(allocations)]!=allocations:
                _error('Frühere Zuordnungen dürfen nicht nachträglich umgewidmet werden.')
        elif (old['source'].get('source_schema_version')!=3
                or old['source']['calculation_case']!=current['source']['calculation_case']
                or old['calculation']!=current['calculation']['running_calculation']):
            _error('Die frühere Quellenkette enthält einen anderen laufenden Originalfall.')
    return prior


def _transition(previous,current,prior,observation):
    source,calc,part,event=_same_subject(prior['run'],current)
    if previous['source'].get('source_schema_version')!=5:_error('Positive Korrektur benötigt eine vorherige Source5-Fassung.')
    _same_subject(previous,current)
    before=due(prior['run']['calculation']);total=due(calc);running=due(calc['running_calculation'])
    if total<=before or running<0:_error('Dieser Vertrag umfasst ausschließlich eine positive zusätzliche Nettoverpflichtung.')
    old_plan=prior['payment']['sources']['single_payment_plan']
    if type(old_plan['schema_version']) is not int or old_plan['schema_version'] not in (1,2,3) or old_plan['plan_hash']!=_sha({k:v for k,v in old_plan.items() if k!='plan_hash'}):
        _error('Unveränderter alter Zahlungsplan erforderlich.')
    value=dict(schema_version=1,contract=TRANSITION_CONTRACT,employee_id=source['employee_id'],month=source['month'],
        previous_run_ref=reference(previous),prior_run_ref=reference(prior['run']),prior_payment_ref=reference(prior['payment']),
        prior_plan_hash=old_plan['plan_hash'],old_composition_hash=_sha(prior['run']['calculation']),new_composition_hash=_sha(calc),
        component_key=part['component_key'],event_key=event['event_key'],receipt_date=event['receipt_date'],
        running_net_minor=running,prior_total_net_minor=before,total_net_minor=total,additional_net_minor=total-before,
        remittance_observation=observation,settlement_review=normalize_review(source['input']['settlement_review']))
    return dict(value,transition_hash=_sha(value))


@within_original_graph
def prepare_transition(payroll,previous,current):
    """Fresh write/preview guard inside the shared serialized transaction."""
    from business_payroll_accounts import PayrollAccounts
    from payroll_correction_remittances import current_observation
    review=current['source']['input'].get('settlement_review')
    if previous is None:
        if review is not None:_error('Die Vollständigkeitsprüfung gehört ausschließlich zu einer bezahlten Source5-Korrektur.')
        return None
    accounts=PayrollAccounts(payroll.office,clock=payroll.hr.clock)
    prior=_prior_chain(accounts,previous,current)
    if prior is None:
        if review is not None:_error('Die Vollständigkeitsprüfung gehört ausschließlich zu einer bezahlten Source5-Korrektur.')
        return None
    if review is None:_error('Tatsächliche Zahlungen und Abführungen zuerst vollständig mit privatem Originalbeleg prüfen.')
    _review_evidence(payroll,review,current['source']['employee_id'],fresh=True)
    observation=current_observation(payroll.office,current['source']['employee_id'],current['source']['month'],current['calculation'])
    if review['schema_version']==3:
        from payroll_multiple_adjustments import build_transition
        return build_transition(previous,current,prior,observation)
    if review['schema_version']==2:
        from payroll_multiple_repayments import build_transition
        return build_transition(previous,current,prior,observation)
    return _transition(previous,current,prior,observation)


def validate_transition_shape(value):
    _shape(value,TRANSITION_FIELDS,TRANSITION_FIELDS)
    if type(value['schema_version']) is not int or value['schema_version']!=1 or value['contract']!=TRANSITION_CONTRACT:
        _error('Unbekannter positiver Netto-Korrekturvertrag.')
    if not isinstance(value['settlement_review'],dict) or value['settlement_review'].get('schema_version')!=1:
        _error('Der ursprüngliche positive Korrekturvertrag benötigt seine unveränderte Vollständigkeitsprüfung der Version 1.')
    for key in ('previous_run_ref','prior_run_ref','prior_payment_ref'):ref(value[key])
    for key in ('prior_plan_hash','old_composition_hash','new_composition_hash','transition_hash'):_hash(value[key])
    for key in ('running_net_minor','prior_total_net_minor','total_net_minor','additional_net_minor'):_integer(value[key],0,10**12)
    if value['additional_net_minor']<=0 or value['total_net_minor']-value['prior_total_net_minor']!=value['additional_net_minor']:
        _error('Positive unveränderte Nettodifferenz erforderlich.')
    normalize_review(value['settlement_review'])
    if value['transition_hash']!=_sha({k:v for k,v in value.items() if k!='transition_hash'}):
        _error('Korrekturbindung wurde verändert.')
    return value


def verify_transition(payroll,run):
    if run['settlement_transition'].get('schema_version')==3:
        from payroll_multiple_adjustments import verify_transition as verify_adjustment
        return verify_adjustment(payroll,run)
    if run['settlement_transition'].get('schema_version')==2:
        from payroll_multiple_repayments import verify_transition as verify_repayment
        return verify_repayment(payroll,run)
    value=validate_transition_shape(run['settlement_transition'])
    if run['revision']<2:_error('Erstlauf kann keinen bezahlten Vorgänger korrigieren.')
    previous=payroll._event(payroll._row(run['id'],'run',run['revision']-1))
    from business_payroll_accounts import PayrollAccounts
    from payroll_correction_remittances import validate_observation
    accounts=PayrollAccounts(payroll.office,clock=payroll.hr.clock)
    paid=accounts._get(value['prior_payment_ref']['id'],value['prior_payment_ref']['revision'])
    if reference(paid)!=value['prior_payment_ref']:_error('Ursprüngliche vorherige Zahlungsfassung fehlt.')
    prior=_resolved_payment(accounts,run,paid)
    _review_evidence(payroll,value['settlement_review'],run['source']['employee_id'],fresh=False)
    validate_observation(payroll.office,run['source']['employee_id'],run['source']['month'],run['calculation'],value['remittance_observation'])
    if _transition(previous,run,prior,value['remittance_observation'])!=value:
        _error('Historischer Korrekturübergang stimmt nicht mit den tatsächlichen Originalen überein.')
    proof=dict(source=run['source'],calculation=run['calculation'],settlement_transition=value)
    if run['preview_hash']!=_sha(proof):_error('Korrekturlauf besitzt keine exakt passende gebundene Vorschau.')
    return True


@within_original_graph
def build_positive_payment_plan(run,*,payments,allocations,as_of,prior_settlement,payment_source_schema_version=2):
    """V2 retains its original same-day contract; V3 records actual later days.

    V3 changes no gross receipt, calculation, debt or historic payment. Only
    additional positive, evidenced 2026 cash transfers may have a later date.
    """
    from payroll_oneoff_2026 import _date,_int
    version=payment_source_schema_version
    if type(version) is not int or version not in (2,3):
        _error('Ausdrückliche unterstützte positive Zahlungsfassung erforderlich.')
    value=validate_transition_shape(run['settlement_transition']);prior=prior_settlement
    source,calc,part,event=_same_subject(prior['run'],run)
    if (run.get('kind')!='run' or run.get('confirmed') is not True or run.get('status')!='calculation_recorded'
            or run.get('accepted_scope')!=calc['scope'] or run.get('id')!=prior['run']['id']
            or type(run.get('revision')) is not int or run['revision']<=prior['run']['revision']
            or reference(prior['run'])!=value['prior_run_ref'] or reference(prior['payment'])!=value['prior_payment_ref']
            or _sha(calc)!=value['new_composition_hash'] or _sha(prior['run']['calculation'])!=value['old_composition_hash']
            or value['employee_id']!=source['employee_id'] or value['month']!=source['month']
            or value['event_key']!=event['event_key'] or value['component_key']!=part['component_key']
            or value['receipt_date']!=event['receipt_date'] or value['total_net_minor']!=due(calc)
            or value['running_net_minor']!=due(calc['running_calculation'])
            or value['settlement_review']!=source['input']['settlement_review']):
        _error('Zahlungsplan benötigt genau den angenommenen Korrekturlauf und seine wirkliche Vorzahlung.')
    old_payments=prior['payment']['details']['payments'];old_allocations=prior['payment']['details']['settlement_allocations']
    old_plan=prior['payment']['sources']['single_payment_plan']
    if version==2 and old_plan.get('schema_version')==3:
        _error('Ein später datierter Zahlungspräfix benötigt weiterhin Zahlungsfassung 3.')
    if (old_plan['plan_hash']!=value['prior_plan_hash'] or old_plan['plan_hash']!=_sha({k:v for k,v in old_plan.items() if k!='plan_hash'})
            or old_plan['payments']!=old_payments or old_plan['allocations']!=old_allocations):
        _error('Vorheriger Zahlungsplan oder seine tatsächlichen Zuordnungen wurden verändert.')
    count=len(old_payments);_date(as_of)
    if (not isinstance(payments,list) or not count<len(payments)<=20 or not isinstance(allocations,list)
            or len(allocations)!=len(payments) or payments[:count]!=old_payments or allocations[:count]!=old_allocations):
        _error('Vollständigen unveränderten Zahlungs- und Zuordnungspräfix mit zusätzlicher tatsächlicher Zahlung angeben.')
    not_before=max([event['receipt_date']]+[p['paid_on'] for p in old_payments])
    seen=set();new_total=0
    for index,payment in enumerate(payments):
        _shape(payment,('paid_on','amount_minor','payment_reference'),('paid_on','amount_minor','payment_reference'))
        day=_date(payment['paid_on']);_int(payment['amount_minor'],1)
        text=payment['payment_reference']
        if not isinstance(text,str) or not text or text.strip()!=text or len(text)>200 or any(ord(c)<32 or ord(c)==127 or 0xD800<=ord(c)<=0xDFFF for c in text):
            _error('Eindeutige unveränderte tatsächliche Zahlungsreferenz erforderlich.')
        if day.year!=2026 or payment['paid_on'][:7]<source['month'] or payment['paid_on']>as_of or _payment_key(payment) in seen:
            _error('Tatsächlicher Zahlungstag oder Zahlungsidentität ist ungültig.')
        seen.add(_payment_key(payment));a=allocations[index]
        _shape(a,('payment_index','running_minor','one_off_allocations'),('payment_index','running_minor','one_off_allocations'))
        if type(a['payment_index']) is not int or a['payment_index']!=index:_error('Geordnete genaue Zahlungszuordnungen erforderlich.')
        if index>=count:
            if not isinstance(a['one_off_allocations'],list) or len(a['one_off_allocations'])!=1:
                _error('Genau eine belegte Bonuszuordnung je zusätzlicher Zahlung erforderlich.')
            _shape(a['one_off_allocations'][0],('event_key','net_minor'),('event_key','net_minor'))
            _int(a['one_off_allocations'][0]['net_minor'],1)
            if (a['running_minor']!=0 or type(a['running_minor']) is not int
                    or a['one_off_allocations']!=[dict(event_key=event['event_key'],net_minor=payment['amount_minor'])]
                    or (payment['paid_on']!=event['receipt_date'] if version==2
                        else payment['paid_on']<not_before)):
                _error('Neue Teile erfüllen ausschließlich dieselbe Bonus-Nettoverpflichtung am belegten ursprünglichen Zuflusstag.'
                    if version==2 else 'Zusätzliche positive Zahlungen müssen dieselbe Bonus-Nettoverpflichtung frühestens nach dem bisherigen Zahlungspräfix erfüllen.')
            new_total+=payment['amount_minor']
    if (new_total!=value['additional_net_minor'] or sum(p['amount_minor'] for p in payments)!=due(calc)
            or sum(p['amount_minor'] for p in old_payments)!=value['prior_total_net_minor']):
        _error('Neue Nettozahlungen müssen genau die bestätigte positive Differenz erfüllen.')
    plan=dict(schema_version=version,contract=PAYMENT_CONTRACT if version==2 else PAYMENT_DATES_CONTRACT,employee_id=source['employee_id'],month=source['month'],
        composition_hash=_sha(calc),event_key=event['event_key'],bonus_receipt_date=event['receipt_date'],
        running_net_minor=value['running_net_minor'],one_off_net_minor=due(calc)-value['running_net_minor'],total_net_minor=due(calc),
        payments=deepcopy(payments),allocations=deepcopy(allocations),
        prior_settlement_refs=dict(run=reference(prior['run']),payment=reference(prior['payment'])),
        preserved_prior_payment_indexes=list(range(count)),new_payment_indexes=list(range(count,len(payments))),
        actual_payment_created=False,cash_import_created=False,claim_consumption_created=False,
        prior_total_net_minor=value['prior_total_net_minor'],additional_net_minor=value['additional_net_minor'],
        prior_plan_hash=value['prior_plan_hash'],transition_hash=value['transition_hash'])
    if version==3:plan['settlement_date_basis']='actual_positive_transfer_2026'
    return dict(plan,plan_hash=_sha(plan))


def resolve_positive_payment_plan(accounts,run,details):
    value=validate_transition_shape(run['settlement_transition'])
    if details['prior_payment_ref']!=value['prior_payment_ref']:_error('Genau die im Korrekturlauf gebundene vorherige Zahlung auswählen.')
    paid=accounts._get(value['prior_payment_ref']['id'],value['prior_payment_ref']['revision'])
    if reference(paid)!=value['prior_payment_ref']:_error('Gebundene vorherige Zahlungsfassung fehlt.')
    prior=_resolved_payment(accounts,run,paid)
    return build_positive_payment_plan(run,payments=details['payments'],allocations=details['settlement_allocations'],
        as_of=accounts.hr.now()[:10],prior_settlement=prior,
        payment_source_schema_version=details['payment_source_schema_version'])


def require_current_positive_settlement(accounts,run,details):
    """Fresh acceptance only; never invalidate an earlier exact receipt replay."""
    from payroll_correction_remittances import current_observation
    if accounts.payroll._row(run['id'],'run')['revision']!=run['revision']:
        _error('Neue Zahlung benötigt die aktuelle Korrekturfassung.')
    _review_evidence(accounts.payroll,run['settlement_transition']['settlement_review'],run['employee_id'],fresh=True)
    previous=accounts.payroll._event(accounts.payroll._row(run['id'],'run',run['revision']-1))
    prior=_prior_chain(accounts,previous,run)
    if prior is None or reference(prior['payment'])!=details['prior_payment_ref'] or details['prior_payment_ref']!=run['settlement_transition']['prior_payment_ref']:
        _error('Letzte tatsächliche vorherige Zahlung muss unverändert gebunden bleiben.')
    current_observation(accounts.office,run['employee_id'],run['source']['month'],run['calculation'])


def require_unbound_payment_revision(accounts,previous):
    """Do not create contradictory later evidence for a consumed actual prefix."""
    if previous is None or previous['kind']!='payment':return
    from business_payroll import COLUMNS
    for row in accounts.db.execute('SELECT '+COLUMNS+" FROM business_payroll_events WHERE employee_id=? AND kind='run'",
            (previous['employee_id'],)):
        run=accounts.payroll._event(row);bound=run.get('settlement_transition',{}).get('prior_payment_ref')
        if bound==reference(previous):
            _error('Dieser ursprüngliche Zahlungsnachweis ist bereits als unveränderlicher Präfix eines Korrekturlaufs gebunden.')

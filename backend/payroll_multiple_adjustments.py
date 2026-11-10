"""Additive repeated signed or zero net adjustments after a Source5 repayment.

This records a separately evidenced cash return. It never withdraws a payment,
changes an old gross receipt, releases tax remittances or executes a transfer.
"""
from payroll_verification import within_original_graph
from copy import deepcopy

from core import Problem
from business_payroll_facts import reference, ref
from business_personnel_workflow import _shape, _integer, _sha
from payroll_multiple_payments import _payment_key

REVIEW_CONTRACT='source5_actual_net_adjustment_review_v1'
TRANSITION_CONTRACT='source5_net_adjustment_v1'
PAYMENT_CONTRACT='source5_actual_net_adjustment_v5'
REVIEW_FIELDS=('schema_version','contract','payments_complete','remittances_complete','evidence_ref')
OLD_CONTRACTS={4:'source5_actual_net_repayment_v4',5:PAYMENT_CONTRACT}


def _bad(message):
    raise Problem(409,message)


def normalize_review(value):
    _shape(value,REVIEW_FIELDS,REVIEW_FIELDS)
    if (type(value['schema_version']) is not int or value['schema_version']!=3
            or value['contract']!=REVIEW_CONTRACT or value['payments_complete'] is not True
            or value['remittances_complete'] is not True):
        _bad('Sämtliche bisherigen Zahlungen, Rückzahlungen und Abführungen für den weiteren Nettoausgleich ausdrücklich prüfen.')
    evidence=ref(value['evidence_ref'])
    if evidence['revision']!=1:
        _bad('Unverändertes privates Original für die vollständige Prüfung des weiteren Nettoausgleichs auswählen.')
    return dict(value,evidence_ref=evidence)


def build_transition(previous,current,prior,observation):
    from payroll_multiple_corrections import _same_subject, due
    source,calc,part,event=_same_subject(prior['run'],current)
    if previous['source'].get('source_schema_version')!=5:
        _bad('Weiterer Nettoausgleich benötigt die frühere Source5-Originalfassung.')
    _same_subject(previous,current)
    before=due(prior['run']['calculation']);total=due(calc);running=due(calc['running_calculation'])
    if not 0<=running<=total or before<running:
        _bad('Weiterer Nettoausgleich darf das laufende Originalnetto nicht unterschreiten oder verändern.')
    old=prior['payment']['sources']['single_payment_plan']
    if (type(old['schema_version']) is not int or old['schema_version'] not in OLD_CONTRACTS
            or old.get('contract')!=OLD_CONTRACTS[old['schema_version']]
            or old['plan_hash']!=_sha({k:v for k,v in old.items() if k!='plan_hash'})):
        _bad('Weiterer Nettoausgleich benötigt den vollständigen unveränderten gemischten V4-/V5-Zahlungspräfix.')
    value=dict(schema_version=3,contract=TRANSITION_CONTRACT,employee_id=source['employee_id'],month=source['month'],
        previous_run_ref=reference(previous),prior_run_ref=reference(prior['run']),prior_payment_ref=reference(prior['payment']),
        prior_plan_hash=old['plan_hash'],old_composition_hash=_sha(prior['run']['calculation']),new_composition_hash=_sha(calc),
        component_key=part['component_key'],event_key=event['event_key'],receipt_date=event['receipt_date'],
        running_net_minor=running,prior_total_net_minor=before,total_net_minor=total,
        net_delta_minor=total-before,repayment_minor=max(before-total,0),additional_net_minor=max(total-before,0),
        remittance_observation=observation,settlement_review=normalize_review(source['input']['settlement_review']))
    return dict(value,transition_hash=_sha(value))


def validate_transition(value):
    from payroll_multiple_corrections import TRANSITION_FIELDS,_hash
    fields=tuple(k for k in TRANSITION_FIELDS if k!='additional_net_minor')+('net_delta_minor','repayment_minor','additional_net_minor')
    _shape(value,fields,fields)
    if type(value['schema_version']) is not int or value['schema_version']!=3 or value['contract']!=TRANSITION_CONTRACT:
        _bad('Unbekannter ausdrücklicher Vertrag für einen weiteren Nettoausgleich.')
    for key in ('previous_run_ref','prior_run_ref','prior_payment_ref'):
        ref(value[key])
    for key in ('prior_plan_hash','old_composition_hash','new_composition_hash','transition_hash'):
        _hash(value[key])
    for key in ('running_net_minor','prior_total_net_minor','total_net_minor','repayment_minor','additional_net_minor'):
        _integer(value[key],0,10**12)
    if (type(value['net_delta_minor']) is not int or not -10**12<=value['net_delta_minor']<=10**12
            or not 0<=value['running_net_minor']<=min(value['total_net_minor'],value['prior_total_net_minor'])
            or value['total_net_minor']-value['prior_total_net_minor']!=value['net_delta_minor']
            or value['repayment_minor']!=max(-value['net_delta_minor'],0)
            or value['additional_net_minor']!=max(value['net_delta_minor'],0)):
        _bad('Richtung und Beträge des Nettoausgleichs müssen genau der vollständig belegten Nettodifferenz entsprechen.')
    normalize_review(value['settlement_review'])
    if value['transition_hash']!=_sha({k:v for k,v in value.items() if k!='transition_hash'}):
        _bad('Die ursprüngliche Nettoausgleichsbindung wurde verändert.')
    return value


def verify_transition(payroll,run):
    from payroll_multiple_corrections import _resolved_payment,_review_evidence
    from payroll_correction_remittances import validate_observation
    value=validate_transition(run['settlement_transition'])
    if run['revision']<2:
        _bad('Ein weiterer Nettoausgleich benötigt einen tatsächlich erfüllten früheren Lauf.')
    previous=payroll._event(payroll._row(run['id'],'run',run['revision']-1))
    from business_payroll_accounts import PayrollAccounts
    accounts=PayrollAccounts(payroll.office,clock=payroll.hr.clock)
    paid=accounts._get(value['prior_payment_ref']['id'],value['prior_payment_ref']['revision'])
    if reference(paid)!=value['prior_payment_ref']:
        _bad('Ursprünglicher vorheriger Zahlungsbeleg fehlt.')
    prior=_resolved_payment(accounts,run,paid)
    _review_evidence(payroll,value['settlement_review'],run['source']['employee_id'],fresh=False)
    validate_observation(payroll.office,run['source']['employee_id'],run['source']['month'],run['calculation'],value['remittance_observation'])
    if build_transition(previous,run,prior,value['remittance_observation'])!=value:
        _bad('Nettoausgleich stimmt nicht mit den wirklichen Originalen überein.')
    if run['preview_hash']!=_sha(dict(source=run['source'],calculation=run['calculation'],settlement_transition=value)):
        _bad('Angenommener Nettoausgleich hat keine exakt passende Vorschau.')
    return True


@within_original_graph
def build_payment_plan(run,*,payments,allocations,as_of,prior_settlement):
    from payroll_multiple_corrections import _same_subject,due
    from payroll_oneoff_2026 import _date
    value=validate_transition(run['settlement_transition']);prior=prior_settlement
    source,calc,part,event=_same_subject(prior['run'],run)
    if (run.get('kind')!='run' or run.get('confirmed') is not True or run.get('status')!='calculation_recorded'
            or run.get('accepted_scope')!=calc['scope'] or run['id']!=prior['run']['id']
            or type(run['revision']) is not int or run['revision']<=prior['run']['revision']
            or reference(prior['run'])!=value['prior_run_ref'] or reference(prior['payment'])!=value['prior_payment_ref']
            or _sha(calc)!=value['new_composition_hash'] or _sha(prior['run']['calculation'])!=value['old_composition_hash']
            or value['employee_id']!=source['employee_id'] or value['month']!=source['month']
            or value['event_key']!=event['event_key'] or value['component_key']!=part['component_key']
            or value['receipt_date']!=event['receipt_date'] or value['total_net_minor']!=due(calc)
            or value['running_net_minor']!=due(calc['running_calculation'])
            or value['settlement_review']!=source['input']['settlement_review']):
        _bad('Nettoausgleich muss genau den angenommenen Lauf, das ursprüngliche Ereignis und die letzte tatsächliche Zahlung erfüllen.')
    old=prior['payment']['details'];old_plan=prior['payment']['sources']['single_payment_plan']
    count=len(old['payments']);_date(as_of)
    if (type(old_plan['schema_version']) is not int or old_plan['schema_version'] not in OLD_CONTRACTS
            or old_plan.get('contract')!=OLD_CONTRACTS[old_plan['schema_version']] or old_plan['plan_hash']!=value['prior_plan_hash']
            or old_plan['plan_hash']!=_sha({k:v for k,v in old_plan.items() if k!='plan_hash'})
            or old_plan['payments']!=old['payments'] or old_plan['allocations']!=old['settlement_allocations']
            or not isinstance(payments,list) or not count<=len(payments)<=20
            or (len(payments)==count)!=(value['net_delta_minor']==0)
            or not isinstance(allocations,list) or len(allocations)!=len(payments)
            or payments[:count]!=old['payments'] or allocations[:count]!=old['settlement_allocations']):
        _bad('Vollständigen unveränderten gemischten Zahlungspräfix beibehalten; bei null Differenz keine neuen Zahlungsteile angeben.')
    not_before=max([event['receipt_date']]+[p['paid_on'] for p in old['payments']])
    seen=set();new_total=0
    for index,payment in enumerate(payments):
        _shape(payment,('paid_on','amount_minor','payment_reference'),('paid_on','amount_minor','payment_reference'))
        date=_date(payment['paid_on']);amount=payment['amount_minor'];text=payment['payment_reference']
        if (type(amount) is not int or not -10**12<=amount<=10**12 or amount==0
                or date.year!=2026 or payment['paid_on'][:7]<source['month'] or payment['paid_on']>as_of
                or not isinstance(text,str) or not text or text.strip()!=text or len(text)>200
                or any(ord(c)<32 or ord(c)==127 or 0xD800<=ord(c)<=0xDFFF for c in text)):
            _bad('Tatsächlichen Nettoausgleich mit genauem Tag, vorzeichenrichtigen Cent und unveränderter eindeutiger Referenz belegen.')
        key=_payment_key(payment)
        if key in seen:
            _bad('Tatsächliche Zahlungsidentitäten dürfen nicht doppelt enthalten sein.')
        seen.add(key);allocation=allocations[index]
        _shape(allocation,('payment_index','running_minor','one_off_allocations'),('payment_index','running_minor','one_off_allocations'))
        if type(allocation['payment_index']) is not int or allocation['payment_index']!=index:
            _bad('Geordnete genaue Zahlungszuordnungen erforderlich.')
        if index>=count:
            if (amount*value['net_delta_minor']<=0 or payment['paid_on']<not_before or type(allocation['running_minor']) is not int
                    or allocation['running_minor']!=0 or not isinstance(allocation['one_off_allocations'],list)
                    or len(allocation['one_off_allocations'])!=1):
                _bad('Neue tatsächliche Bonus-Zahlungsteile müssen genau der belegten Differenzrichtung folgen und dürfen nicht vor dem alten Zahlungspräfix liegen.')
            one=allocation['one_off_allocations'][0]
            _shape(one,('event_key','net_minor'),('event_key','net_minor'))
            if type(one['net_minor']) is not int or one!=dict(event_key=event['event_key'],net_minor=amount):
                _bad('Exakte vorzeichenrichtige Bonuszuordnung zum tatsächlichen Nettoausgleich erforderlich.')
            new_total+=amount
    if (new_total!=value['net_delta_minor'] or sum(p['amount_minor'] for p in payments)!=due(calc)
            or sum(p['amount_minor'] for p in old['payments'])!=value['prior_total_net_minor']):
        _bad('Die neuen tatsächlichen Zahlungen müssen genau die belegte Nettodifferenz erfüllen; null bedeutet keinen neuen Geldfluss.')
    plan=dict(schema_version=5,contract=PAYMENT_CONTRACT,employee_id=source['employee_id'],month=source['month'],
        composition_hash=_sha(calc),event_key=event['event_key'],bonus_receipt_date=event['receipt_date'],
        running_net_minor=value['running_net_minor'],one_off_net_minor=due(calc)-value['running_net_minor'],total_net_minor=due(calc),
        payments=deepcopy(payments),allocations=deepcopy(allocations),
        prior_settlement_refs=dict(run=reference(prior['run']),payment=reference(prior['payment'])),
        preserved_prior_payment_indexes=list(range(count)),new_payment_indexes=list(range(count,len(payments))),
        actual_payment_created=False,cash_import_created=False,claim_consumption_created=False,
        prior_total_net_minor=value['prior_total_net_minor'],net_delta_minor=value['net_delta_minor'],repayment_minor=value['repayment_minor'],additional_net_minor=value['additional_net_minor'],
        prior_plan_hash=value['prior_plan_hash'],transition_hash=value['transition_hash'],
        settlement_date_basis='actual_signed_net_adjustment_2026')
    return dict(plan,plan_hash=_sha(plan))


def resolve_payment_plan(accounts,run,details):
    from payroll_multiple_corrections import _resolved_payment
    value=validate_transition(run['settlement_transition'])
    if details['prior_payment_ref']!=value['prior_payment_ref']:
        _bad('Die tatsächlich gebundene vorherige vollständige Zahlung auswählen.')
    paid=accounts._get(value['prior_payment_ref']['id'],value['prior_payment_ref']['revision'])
    if reference(paid)!=value['prior_payment_ref']:
        _bad('Die gebundene frühere Zahlungsfassung wurde verändert.')
    return build_payment_plan(run,payments=details['payments'],allocations=details['settlement_allocations'],
        as_of=accounts.hr.now()[:10],prior_settlement=_resolved_payment(accounts,run,paid))

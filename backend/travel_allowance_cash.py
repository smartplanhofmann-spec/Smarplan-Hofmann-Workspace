"""Actual travel reimbursement sources with a strict private/public boundary."""
import hashlib
import json

from core import Problem,canonical
from business_accounting import Accounting,_evidence
from business_operations import identifier,text
from business_personnel_workflow import _sha,_shape
from business_payroll_cash import _instance
from payroll_travel_2026 import integer,day

RESTORE_TABLES=('business_travel_sites','business_travel_trips','business_travel_settlements',
    'business_travel_payments','business_travel_claims','business_travel_cash_events','business_travel_evidence','business_travel_requests')


def installed(office):
    from business_travel_allowances import installed as check
    return check(office)


def financial_access(office,actor,write=False):
    if actor is None:return None
    api=Accounting(office);fresh=api._access(actor)
    if write:api.access(fresh,'accounting.prepare');api.access(fresh,'finance.write')
    return fresh


def _money(value):return str(value//100)+'.'+str(value%100).zfill(2)


def _public(payment):
    d=payment['details'];direction='out' if d['kind']=='reimbursement' else 'in'
    movement=dict(id=_sha([payment['id'],d['paid_on'],direction])[:32],date=d['paid_on'],account=payment['sources']['account'],
        direction=direction,amount=_money(d['amount_minor']),categories={'travel_allowance':_money(d['amount_minor'])})
    result=dict(kind='travel_cash',id=payment['id'],revision=payment['revision'],instance_id=d['instance_id'],
        status=payment['status'],date=d['paid_on'],cash_movements=[] if payment['status']=='void' else [movement],proof_hash=_sha(payment),
        source_path='/personnel/travel/financial/'+payment['id']+'?revision='+str(payment['revision']))
    return dict(result,source_hash=_sha(result))


def public_source(office,payment_id,revision=None):
    from business_travel_allowances import TravelAllowances,validate_payment
    identifier(payment_id);api=TravelAllowances(office)
    payment=api._get('payment',payment_id,revision);validate_payment(api,payment)
    row=office.db.execute('SELECT * FROM business_travel_cash_events WHERE id=? AND revision=?',(payment_id,payment['revision'])).fetchone()
    if row is None:raise Problem(409,'Öffentlicher Reisegeldfluss fehlt.')
    expected=_public(payment);actual=json.loads(row['public_json'])
    if actual!=expected or _sha(actual)!=row['public_sha256'] or row['private_sha256']!=payment['content_hash'] or row['instance_id']!=actual['instance_id']:
        raise Problem(409,'Öffentliche Reisegeldquelle besteht die Integritätsprüfung nicht.')
    return actual


def ensure_cash_available(office,account_id,evidence_key,original_sha256=None,*,own_payment=None):
    if not installed(office):return
    key=_evidence(evidence_key)[1]
    row=office.db.execute('SELECT payment_id FROM business_travel_evidence WHERE account_id=? AND evidence_key=?',(account_id,key)).fetchone()
    if row and row['payment_id']!=own_payment:raise Problem(409,'Zahlungsreferenz ist bereits als Reisegeldquelle gebunden.')
    if original_sha256:
        for row in office.db.execute('SELECT payment_id FROM business_travel_evidence WHERE original_sha256=?',(original_sha256,)):
            if row['payment_id']!=own_payment:raise Problem(409,'Original ist bereits als Reisegeldnachweis gebunden.')
        for row in office.db.execute('SELECT id,payload_json FROM business_travel_payments'):
            if row['id']!=own_payment and any(f['sha256']==original_sha256 for f in json.loads(row['payload_json'])['sources']['files']):
                raise Problem(409,'Original ist bereits in einer historischen Reisezahlung gebunden.')


def _paid(api,settlement_id,exclude_id=None,through_sequence=None):
    sql='SELECT * FROM business_travel_payments';args=[]
    if through_sequence is not None:sql+=' WHERE sequence<=?';args.append(through_sequence)
    latest={}
    for row in api.db.execute(sql+' ORDER BY sequence',tuple(args)):latest[row['id']]=api._view(row)
    total=0
    for value in latest.values():
        if value['id']==exclude_id or value['status']=='void' or value['details'].get('legacy_payment') is not None or value['details']['settlement_ref']['id']!=settlement_id:continue
        total+=value['details']['amount_minor']*(1 if value['details']['kind']=='reimbursement' else -1)
    return total


def _legacy_payment(api,settlement,reference,*,own_payment=None,check_unique=False):
    """Bind an actual old HR payment; supplying finance evidence creates no pay."""
    from payroll_travel_2026 import _reference
    _shape(reference,('expense_ref','payment_index','payment_hash'),('expense_ref','payment_index','payment_hash'))
    _reference(reference['expense_ref']);index=integer(reference['payment_index'],0,10000)
    matches=[e for e in settlement['sources']['expenses'] if {k:e[k] for k in ('id','revision','content_hash')}==reference['expense_ref']]
    if len(matches)!=1:raise Problem(409,'Übernahme benötigt genau die in der Abrechnung gebundene ursprüngliche Auslagenfassung.')
    expense=matches[0]
    if index>=len(expense['payments']):raise Problem(400,'Tatsächliche frühere Zahlungsposition auswählen.')
    payment=expense['payments'][index]
    if _sha(payment)!=reference['payment_hash']:raise Problem(409,'Unveränderten ursprünglichen Zahlungsnachweis auswählen.')
    allocations=[i for i in settlement['calculation'].get('expense_items',[]) if i['expense_ref']==reference['expense_ref']]
    if not allocations or sum(i['business_minor'] for i in allocations)!=expense['total_minor'] or any(i['private_minor'] or i['provided_minor'] for i in allocations):
        raise Problem(409,'Alte Zahlung benötigt eine vollständig geprüfte betriebliche Originalauslage ohne ungeklärte private/gestellte Anteile.')
    originals=[]
    for row in api.db.execute("SELECT * FROM business_personnel_events WHERE id=? AND kind='expense' ORDER BY revision",(expense['id'],)):
        candidate=api.hr._event(row)
        if len(candidate['payments'])>index:
            originals.append(candidate);break
    if not originals or originals[0]['payments'][index]!=payment or originals[0]['items']!=expense['items'] or payment['amount_minor']!=expense['total_minor']:
        raise Problem(409,'Frühere Zahlung und damalige Originalpositionen sind nicht unverändert nachvollziehbar.')
    if check_unique:
        for row in api.db.execute('SELECT id,payload_json FROM business_travel_payments'):
            prior=json.loads(row['payload_json'])['details'].get('legacy_payment')
            if row['id']!=own_payment and prior is not None and prior['expense_ref']['id']==expense['id'] and prior['payment_index']==index:
                raise Problem(409,'Diese tatsächliche alte Zahlung besitzt bereits einen eigenen Finanznachweis.')
    return dict(expense_ref=reference['expense_ref'],payment_index=index,payment_hash=reference['payment_hash'],
                original_event={k:originals[0][k] for k in ('id','revision','content_hash')},payment=payment)


def record_payment(api,actor,data):
    fields=('request_id','employee_id','id','revision','action','settlement_ref','instance_id','account_id','account_revision',
            'kind','paid_on','amount_minor','reference','reference_file_id','source_hash','correction_reason','confirmed')
    _shape(data,fields+('legacy_payment',),fields);financial_access(api.office,actor,True)
    def save(fresh,employee,fingerprint):
        accounting=Accounting(api.office);accounting._write_gate();old=api._previous('payment',data)
        if data['action'] not in ('record','adopt_legacy','correct','void') or (data['action'] in ('record','adopt_legacy'))!=(old is None):
            raise Problem(409,'Neue Zahlung oder belegte Korrektur einer vorhandenen Zahlung ausdrücklich wählen.')
        if data['confirmed'] is not True:raise Problem(400,'Tatsächlich ausgeführte Zahlung ausdrücklich bestätigen.')
        if data['source_hash']!=api._basis(employee['id']):raise Problem(409,'Zahlungsquellen wurden geändert; neu prüfen.')
        if data['instance_id']!=_instance(api.office):raise Problem(409,'Zahlungsbeleg gehört nicht zur gebundenen Unternehmensinstanz.')
        if data['kind'] not in ('reimbursement','repayment'):raise Problem(400,'Auszahlung oder tatsächliche Rückzahlung auswählen.')
        day(data['paid_on'])
        if data['paid_on']>api.now()[:10]:raise Problem(400,'Tatsächliche Zahlung darf nicht in der Zukunft liegen.')
        amount=integer(data['amount_minor'],1);integer(data['account_revision'],1)
        account=accounting._account(data['account_id'])
        if account['revision']!=data['account_revision'] or not account['active'] or account['currency']!='EUR':
            raise Problem(409,'Aktuelles aktives EUR-Geldkonto ausdrücklich auswählen.')
        legacy_correction=old is not None and data.get('legacy_payment') is not None
        settlement=api._resolve(fresh,'settlement',data['settlement_ref'],employee['id'],current=data['action']!='void' and not legacy_correction)
        if data['action']!='void' and not legacy_correction:
            for expense in settlement['sources']['expenses']:
                if api.hr._latest(expense['id'],'expense')['content_hash']!=expense['content_hash']:
                    raise Problem(409,'Auslagenquelle wurde nach der Abrechnung verändert; Abrechnung zuerst ausdrücklich korrigieren.')
        if old and old['details']['settlement_ref']['id']!=settlement['id']:raise Problem(409,'Zahlungskorrektur muss bei ihrer ursprünglichen Abrechnung bleiben.')
        legacy_ref=data.get('legacy_payment');legacy=None
        if old and old['details'].get('legacy_payment')!=legacy_ref:raise Problem(409,'Zahlungskorrektur muss ihre ursprüngliche Übernahmequelle beibehalten.')
        if legacy_correction and old['details']['settlement_ref']!=data['settlement_ref']:
            raise Problem(409,'Nachweiskorrektur einer Altzahlung muss die ursprüngliche Abrechnungsfassung beibehalten.')
        if old is None and (data['action']=='adopt_legacy')!=(legacy_ref is not None):raise Problem(400,'Alte Zahlung ausdrücklich als Nachweisübernahme kennzeichnen.')
        if legacy_ref is not None:
            legacy=_legacy_payment(api,settlement,legacy_ref,own_payment=data['id'],check_unique=True)
            original=legacy['payment']
            if data['kind']!=original['kind'] or data['paid_on']!=original['paid_on'] or amount!=original['amount_minor'] or data['reference']!=original['reference']:
                raise Problem(409,'Übernahme darf Datum, Betrag, Richtung oder Referenz der tatsächlich früheren Zahlung nicht verändern.')
        if not settlement['calculation']['can_approve'] or settlement['calculation']['blockers'] or settlement['calculation']['totals']['tax_free_minor']<=0:
            raise Problem(409,'Vollständig geprüfte steuerfreie Reiseabrechnung erforderlich.')
        payroll_processing=old['sources'].get('payroll_processing',[]) if old and data['action']=='void' else []
        if settlement['calculation'].get('payroll_required') and data['action']!='void' and legacy is None:
            from travel_payroll_sources import travel_payroll_source
            try:from payroll_travel_link import assert_travel_processed
            except ImportError as error:raise Problem(409,'Die zugehörige Reise-Lohnquelle ist noch nicht vollständig verarbeitet.') from error
            months={v['date'][:7] for v in settlement['calculation']['days'] if v['letter_m'] or v['benefit_in_kind_minor']}
            scheduled=settlement['details'].get('payroll_month')
            if settlement['calculation']['totals']['flat_taxable_minor'] or settlement['calculation']['totals']['individual_taxable_minor']:
                if data['paid_on'][:7]!=scheduled:raise Problem(409,'Tatsächlicher Zuflussmonat weicht vom geprüften Lohnmonat ab; Abrechnung und Lohnquelle zuerst korrigieren.')
                months.add(scheduled)
            for month in sorted(months):
                payroll_source=travel_payroll_source(api.office,fresh,data['settlement_ref'],month)
                proof=assert_travel_processed(api.office,fresh,data['settlement_ref'],month,payroll_source['source_hash'])
                payroll_processing.append(dict(month=month,source_hash=payroll_source['source_hash'],proof=proof))
        reason=text(data['correction_reason'],'Korrekturgrund',1000,required=old is not None)
        reference,evidence_key=_evidence(data['reference']);files=api._files(fresh,employee['id'],[data['reference_file_id']]);origin=files[0]
        if origin['purpose']!='personnel':raise Problem(400,'Geschütztes Personaloriginal als Zahlungsbeleg auswählen.')
        from business_accounting_euer import ensure_cash_identity_available
        if api.db.execute('SELECT 1 FROM business_accounting_cash_events WHERE account_id=? AND evidence_key=?',(account['id'],evidence_key)).fetchone():
            raise Problem(409,'Zahlungsreferenz ist bereits im vorhandenen Geldjournal erfasst.')
        if api.db.execute('SELECT 1 FROM business_accounting_receipt_bindings WHERE original_sha256=?',(origin['sha256'],)).fetchone():
            raise Problem(409,'Original ist bereits einem anderen Geldfluss zugeordnet.')
        ensure_cash_identity_available(api.office,account['id'],evidence_key,origin['sha256'],travel_payment_id=data['id'])
        from business_accounting_euer import EuerAccounting
        ledger=EuerAccounting(api.office)._ledger()
        dates={data['paid_on']}|({old['details']['paid_on']} if old else set())
        EuerAccounting._unlocked(ledger,[dict(date=value) for value in dates])
        after=api.db.execute('SELECT COALESCE(MAX(sequence),0) AS n FROM business_travel_payments').fetchone()['n']
        legacy_paid=settlement['calculation']['totals'].get('expense_already_paid_minor',0)
        paid=_paid(api,settlement['id'],exclude_id=data['id']);capacity=settlement['calculation']['totals']['tax_free_minor']-legacy_paid
        resulting=paid+(0 if data['action']=='void' else amount if data['kind']=='reimbursement' else -amount)
        if legacy is None and (resulting<0 or (data['action']=='void' or data['kind']=='reimbursement') and resulting>capacity):
            raise Problem(409,'Zahlung übersteigt die belegte verfügbare Reiseerstattung beziehungsweise tatsächliche Vorzahlung.')
        if data['action']=='void' and any(data[k]!=old['details'][k] for k in ('settlement_ref','instance_id','account_id','account_revision','kind','paid_on','amount_minor','reference','reference_file_id')):
            raise Problem(409,'Dokumentarisches Aufheben muss die ursprünglichen Zahlungsdaten beibehalten.')
        details={key:data[key] for key in fields if key not in ('request_id','employee_id','id','revision','source_hash','confirmed')}
        if legacy_ref is not None:details['legacy_payment']=legacy_ref
        details['reference']=reference
        payment=api._append('payment',fresh,employee,data['id'],dict(status='void' if data['action']=='void' else 'active',details=details,
            sources=dict(files=files,account=account,settlement=settlement,payroll_processing=payroll_processing,legacy_payment=legacy),after_payment_sequence=after,
            available_before_minor=capacity-paid,paid_before_minor=paid,command_hash=fingerprint),old)
        public=_public(payment)
        api.db.execute('INSERT INTO business_travel_cash_events(id,revision,instance_id,public_json,public_sha256,private_sha256) VALUES(?,?,?,?,?,?)',
            (payment['id'],payment['revision'],data['instance_id'],canonical(public),_sha(public),payment['content_hash']))
        existing=api.db.execute('SELECT payment_id FROM business_travel_evidence WHERE account_id=? AND evidence_key=?',(account['id'],evidence_key)).fetchone()
        if existing is None:api.db.execute('INSERT INTO business_travel_evidence(account_id,evidence_key,payment_id,first_revision,original_sha256) VALUES(?,?,?,?,?)',
            (account['id'],evidence_key,payment['id'],payment['revision'],origin['sha256']))
        return payment
    return api._command(actor,'payment','payment.record',data,save,permission='personnel.approve',own=False)


def restore_horizon(office):
    if not installed(office):return None
    from business_travel_allowances import validate_integrity
    validate_integrity(office);counts={};content={}
    for table in RESTORE_TABLES:
        rows=[]
        for row in office.db.execute('SELECT * FROM '+table):
            value={key:(dict(sha256=hashlib.sha256(bytes(row[key])).hexdigest(),size=len(row[key]))
                        if isinstance(row[key],(bytes,bytearray,memoryview)) else row[key]) for key in row.keys()}
            rows.append(value)
        rows.sort(key=canonical);counts[table]=len(rows);content[table]=rows
    return dict(schema_version=1,table_counts=counts,sha256=_sha(content))

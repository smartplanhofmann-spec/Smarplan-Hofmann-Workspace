"""First, explicit domestic EÜR/Ist opening-item contract; all arithmetic in cents."""
import re
import unicodedata
from core import Problem
from business_operations import iso_date
from business_accounting_openings import shape,line,hash_value

RULE_VERSION='de_euer_ist_open_items_v1'
EXPENSES={'materials','external_services','rent','insurance','software','other_expense'}

def entity_key(value):
    line(value,'Unveränderliche externe Kennung',200)
    return ' '.join(unicodedata.normalize('NFKC',value).casefold().split())

def cents(value):
    if not isinstance(value,str) or not re.fullmatch(r'(0|[1-9][0-9]{0,10})\.[0-9]{2}',value):
        raise Problem(400,'Exakter nichtnegativer Eurobetrag mit zwei Nachkommastellen erforderlich.')
    return int(value.replace('.',''))

def money(value):return ('-' if value<0 else '')+str(abs(value)//100)+'.'+str(abs(value)%100).zfill(2)

def proof(value):
    from business_operations import identifier
    shape(value,('original_id','sha256'));identifier(value['original_id']);hash_value(value['sha256'])

def tax_at(gross,tax,total):return (2*gross*tax+total)//(2*total)

def payment_split(item,already,amount):
    total=cents(item['gross']);tax=cents(item['tax'])
    if amount<=0 or already<0 or already+amount>total:raise Problem(409,'Zahlung überschreitet den tatsächlich offenen ursprünglichen Posten.')
    before=tax_at(already,tax,total);after=tax_at(already+amount,tax,total)
    return dict(gross=money(amount),net=money(amount-after+before),tax=money(after-before),
                settled_before=money(already),settled_after=money(already+amount),remaining=money(total-already-amount))

def normalize_item(item,opening_date,vat_effective_from):
    shape(item,('status','external_system','external_id','direction','counterparty_key','counterparty_name','invoice_number',
                'invoice_date','service_date','invoice_received_date','currency','rate','category','net','tax','gross',
                'prior_payments','invoice_proof','cutover_proof','history_through','prior_input_vat','scope_confirmed'))
    if item['status'] not in ('active','void') or item['direction'] not in ('receivable','payable'):raise Problem(400,'Bekannte Altpostenart und ausdrücklicher Status erforderlich.')
    for key in ('external_system','external_id','counterparty_key','counterparty_name','invoice_number'):line(item[key],key,200)
    if item['currency']!='EUR' or item['rate'] not in ('19','7') or item['scope_confirmed'] is not True:
        raise Problem(400,'Nur vollständig betriebliche gewöhnliche deutsche EUR-Umsätze mit ausdrücklich bestätigtem unverändertem EÜR-/Ist-/Regelbesteuerungsverlauf.')
    if item['category'] not in ({'sales'} if item['direction']=='receivable' else EXPENSES):raise Problem(400,'Unterstützte gewöhnliche Erlös-/Aufwandsart erforderlich; Anlagen und Sonderfälle bleiben gesperrt.')
    for key in ('invoice_date','service_date','invoice_received_date','history_through'):iso_date(item[key])
    from datetime import date,timedelta
    if item['history_through']!=(date.fromisoformat(opening_date)-timedelta(days=1)).isoformat():raise Problem(400,'Lückenlose Originalhistorie bis unmittelbar vor Buchführungsbeginn erforderlich.')
    if not vat_effective_from<=min(item['invoice_date'],item['service_date']) or max(item['invoice_date'],item['service_date'],item['invoice_received_date'])>=opening_date:
        raise Problem(409,'Vollständig vor Beginn ausgeführte und erhaltene Rechnung im belegten unveränderten Umsatzsteuerzeitraum erforderlich.')
    if item['invoice_received_date']<item['invoice_date']:raise Problem(400,'Rechnungseingang liegt vor Rechnungsdatum.')
    net,tax,gross=(cents(item[key]) for key in ('net','tax','gross'))
    # First contract is one tax group with total-net tax rounding. Other actual
    # historical rounding must be implemented explicitly, never silently fixed.
    if net<=0 or tax!=(net*int(item['rate'])+50)//100 or net+tax!=gross:
        raise Problem(400,'Exakte positive Originalbeträge und eine belegte Gesamt-Netto-Steuergruppe erforderlich.')
    proof(item['invoice_proof']);proof(item['cutover_proof'])
    prior=item['prior_payments']
    if not isinstance(prior,list) or len(prior)>100:raise Problem(400,'Belegte ursprüngliche Teilzahlungen erforderlich.')
    settled=0;last='0000-00-00';seen=set()
    for paid in prior:
        shape(paid,('date','reference','gross','net','tax','proof'));iso_date(paid['date']);line(paid['reference'],'Ursprüngliche Zahlungsreferenz',200);proof(paid['proof'])
        if not max(item['invoice_date'],item['service_date'])<=paid['date']<opening_date or paid['date']<last:raise Problem(400,'Ursprüngliche tatsächliche Zahlungstage chronologisch vor Beginn und nach Leistung erforderlich.')
        key=(paid['date'],entity_key(paid['reference']))
        if key in seen:raise Problem(400,'Ursprüngliche Teilzahlung doppelt angegeben.')
        seen.add(key);split=payment_split(item,settled,cents(paid['gross']))
        if any(paid[key]!=split[key] for key in ('gross','net','tax')):raise Problem(409,'Historische Centaufteilung passt nicht zum ausdrücklich unterstützten Originalverfahren; keine Altdaten umrechnen.')
        settled+=cents(paid['gross']);last=paid['date']
    if settled>=gross:raise Problem(409,'Nur tatsächlich noch offene Altposten übernehmen.')
    vat=item['prior_input_vat']
    if item['direction']=='receivable':
        if vat is not None:raise Problem(400,'Ausgangsrechnung besitzt keinen Vorsteuerübertrag.')
    else:
        shape(vat,('amount','entitlement_date','declared_period','deducted_on','proof'));proof(vat['proof']);iso_date(vat['entitlement_date']);iso_date(vat['deducted_on'])
        if vat['amount']!=item['tax'] or vat['entitlement_date']!=max(item['service_date'],item['invoice_received_date']):raise Problem(409,'Vollständiges bereits entstandenes ursprüngliches Vorsteuerrecht erforderlich.')
        if not isinstance(vat['declared_period'],str) or not re.fullmatch(r'20[0-9]{2}-(0[1-9]|1[0-2])',vat['declared_period']) or vat['declared_period']!=vat['entitlement_date'][:7] or vat['declared_period']>=opening_date[:7]:
            raise Problem(409,'In einer abgeschlossenen Vorperiode bereits ausgeübter vollständiger Vorsteuerabzug erforderlich.')
        if not vat['entitlement_date']<=vat['deducted_on']<opening_date:raise Problem(409,'Tatsächliche frühere Ausübung des Vorsteuerrechts muss vor Beginn liegen; ein alter Erklärungszeitraum allein genügt nicht.')
    prior_tax=sum(cents(value['tax']) for value in prior);prior_net=sum(cents(value['net']) for value in prior)
    return dict(original_gross=item['gross'],settled_before_start=money(settled),opening_remaining=money(gross-settled),
                opening_remaining_net=money(net-prior_net),opening_remaining_tax=money(tax-prior_tax),
                original_identity=[item['direction'],entity_key(item['counterparty_key']),entity_key(item['invoice_number']),item['invoice_date']],
                external_identity=[entity_key(item['external_system']),entity_key(item['external_id'])])

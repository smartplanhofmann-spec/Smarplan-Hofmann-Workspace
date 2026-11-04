"""Explicit prior-period journal copy; never creates an actual cash movement."""
from datetime import date,timedelta
import re
from core import Problem
from business_operations import iso_date
from business_accounting_openings import shape,hash_value,line,sha
from accounting_open_item_rules import normalize_item,entity_key,cents,money

RULE_VERSION='de_euer_same_year_carryover_v1'

def signed_cents(value):
    if not isinstance(value,str) or not re.fullmatch(r'-?(0|[1-9][0-9]{0,10})\.[0-9]{2}',value) or value=='-0.00':
        raise Problem(400,'Exakter vorzeichenbehafteter ursprünglicher Eurobetrag erforderlich.')
    return -cents(value[1:]) if value.startswith('-') else cents(value)

def account(value):
    if not isinstance(value,str) or not re.fullmatch(r'[0-9]{4}',value):raise Problem(400,'Geprüftes ursprüngliches SKR04-Konto erforderlich.')
    return value

def grouped(postings):
    values={}
    for row in postings:
        key=(row['ledger'],row['category'],row['account']);values[key]=values.get(key,0)+signed_cents(row['amount'])
    return [dict(ledger=k[0],category=k[1],account=k[2],amount=money(v)) for k,v in sorted(values.items())]

def canonical_controls(value):
    if not isinstance(value,list) or len(value)>1000:raise Problem(400,'Ausdrücklich belegte Kontrollsummen des ursprünglichen Journals erforderlich.')
    result=[];seen=set()
    for row in value:
        shape(row,('ledger','category','account','amount'));account(row['account']);signed_cents(row['amount'])
        if row['ledger'] not in ('euer','vat') or not isinstance(row['category'],str):raise Problem(400,'Bekannte historische Journal-/Kategoriezuordnung erforderlich.')
        key=(row['ledger'],row['category'],row['account'])
        if key in seen:raise Problem(400,'Jede ursprüngliche Kontrollsumme nur einmal angeben.')
        seen.add(key);result.append(dict(row))
    return sorted(result,key=lambda row:(row['ledger'],row['category'],row['account']))

def calculate(profile,coverage,sources,controls):
    """Sources are original-bound private resolver outputs, never raw API rows.

    A source is a whole unchanged invoice history. Only its original economic
    rows within the chosen period are copied. Claim timing and actual payment
    timing are retained independently, with stable identities for both roles.
    """
    facts=profile['profile']
    if (facts['legal_form'],facts['accounting_method'],facts['vat_regime'],facts['vat_timing'])!=('sole_proprietorship','euer','regular','cash'):
        raise Problem(409,'Unveränderter EÜR-/Ist-/Regelbesteuerungsverlauf erforderlich.')
    opening=facts['bookkeeping_start'];iso_date(opening);year=opening[:4];first=year+'-01-01';last=(date.fromisoformat(opening)-timedelta(days=1)).isoformat()
    shape(coverage,('from','through'));iso_date(coverage['from']);iso_date(coverage['through'])
    if not first<=coverage['from']<=coverage['through']<=last or facts['vat_effective_from'] is None or facts['vat_effective_from']>coverage['from']:
        raise Problem(409,'Belegter Zeitraum desselben Jahres vor Beginn und innerhalb des unveränderten Steuerstatus erforderlich.')
    if not isinstance(sources,list) or len(sources)>1000:raise Problem(400,'Begrenzte vollständige ursprüngliche Quellenliste erforderlich.')
    postings=[];identities=set();invoices=set();external=set();economic_invoices=set();journal_keys=set();copied=[]
    for source in sources:
        shape(source,('kind','source_ref','record','accounts','cash_entry_keys','vat_entry_key'))
        if source['kind'] not in ('opening_item','closed_trade'):raise Problem(400,'Unterstützte kanonische Altquelle erforderlich.')
        hash_value(source['source_ref']);record=source['record']
        normalized=normalize_item(record,opening,facts['vat_effective_from'],allow_settled=source['kind']=='closed_trade')
        if record['status']!='active' or source['kind']=='closed_trade' and normalized['opening_remaining']!='0.00':
            raise Problem(409,'Ein externer noch offener Beleg muss zuerst über den belegten Altpostenweg gebunden werden.')
        original=record['invoice_proof']['sha256'];external_id=tuple(normalized['external_identity'])
        original_identity=tuple(normalized['original_identity'])
        if original in invoices or external_id in external or original_identity in economic_invoices:raise Problem(409,'Ursprüngliche Rechnung und ihre Zahlungen nur einmal je Jahresvortrag übernehmen.')
        invoices.add(original);external.add(external_id);economic_invoices.add(original_identity)
        shape(source['accounts'],('net','tax','input_vat'))
        for value in source['accounts'].values():account(value)
        keys=source['cash_entry_keys']
        if not isinstance(keys,list) or len(keys)!=len(record['prior_payments']):raise Problem(400,'Jede ursprüngliche Teilzahlung braucht ihre ursprüngliche Buchungsidentität.')
        for paid,key in zip(record['prior_payments'],keys):
            line(key,'Ursprüngliche Buchungsidentität',200)
            if not coverage['from']<=paid['date']<=coverage['through']:continue
            identity=sha(['cash',original,paid['date'],entity_key(paid['reference'])]);journal_key=(entity_key(record['external_system']),entity_key(key))
            if identity in identities or journal_key in journal_keys:raise Problem(409,'Ursprünglicher wirtschaftlicher Zahlungsanteil oder Journalbezug doppelt übernommen.')
            identities.add(identity);journal_keys.add(journal_key)
            incoming=record['direction']=='receivable';sign=1 if incoming else -1
            amount=cents(paid['net']);tax=cents(paid['tax'])
            parts=[('euer','sales' if incoming else record['category'],sign*amount,source['accounts']['net']),
                   ('euer','vat_collected' if incoming else 'paid_input_vat',sign*tax,source['accounts']['tax'])]
            if incoming:parts.append(('vat','output_vat',tax,source['accounts']['tax']))
            for ledger,category,value,code in parts:
                postings.append(dict(ledger=ledger,category=category,account=code,amount=money(value),date=paid['date'],economic_key=identity,original_entry_key=key,source_ref=source['source_ref']))
            copied.append(dict(kind='cash_history',economic_key=identity,date=paid['date'],gross=paid['gross'],net=paid['net'],tax=paid['tax'],original_entry_key=key,source_ref=source['source_ref']))
        vat=record['prior_input_vat']
        if vat is None:
            if source['vat_entry_key'] is not None:raise Problem(400,'Ausgangsrechnung besitzt keine ursprüngliche Vorsteuerbuchung.')
        else:
            line(source['vat_entry_key'],'Ursprüngliche Vorsteuerbuchungsidentität',200)
            if coverage['from']<=vat['entitlement_date']<=coverage['through']:
                identity=sha(['input_vat',original]);key=source['vat_entry_key'];journal_key=(entity_key(record['external_system']),entity_key(key))
                if identity in identities or journal_key in journal_keys:raise Problem(409,'Ursprünglicher Vorsteueranspruch ist bereits im Vortrag enthalten.')
                identities.add(identity);journal_keys.add(journal_key)
                postings.append(dict(ledger='vat',category='input_vat',account=source['accounts']['input_vat'],amount=money(-cents(vat['amount'])),date=vat['entitlement_date'],economic_key=identity,original_entry_key=key,source_ref=source['source_ref']))
                copied.append(dict(kind='already_exercised_input_vat',economic_key=identity,date=vat['entitlement_date'],amount=vat['amount'],deducted_on=vat['deducted_on'],declared_period=vat['declared_period'],original_entry_key=key,source_ref=source['source_ref']))
    expected=grouped(postings)
    if canonical_controls(controls)!=expected:raise Problem(409,'Originaljournal und ausdrücklich belegte Kontrollsummen stimmen nicht exakt überein.')
    return dict(schema_version=1,rule_version=RULE_VERSION,year=int(year),opening_date=opening,coverage=coverage,
                complete_prior_period=coverage=={'from':first,'through':last},
                historical_postings=postings,controls=expected,copied_rows=copied,economic_keys=sorted(identities),
                cash_flow_created=False,new_input_vat_claim_created=False,original_periods_preserved=True)


def year_key(value):
    if not isinstance(value,str) or not re.fullmatch(r'20[0-9]{2}',value):raise Problem(400,'Unveränderliches vierstelliges Vortragsjahr erforderlich.')
    return value

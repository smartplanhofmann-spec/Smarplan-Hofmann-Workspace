"""Actual old-item cash continues through EÜR, bank matching and liquidity."""
from core import Problem
from business_operations import identifier
from business_accounting_openings import hash_value,profile_reference
from accounting_open_item_rules import cents

def prepare(api,actor,payload,ledger,historical):
    from business_accounting_euer import _shape,_account,_posting
    from business_accounting_open_items import OpeningItems,public_source
    _shape(payload,'payment_id revision source_hash net_account tax_account')
    identifier(payload['payment_id']);hash_value(payload['source_hash']);_account(payload['net_account']);_account(payload['tax_account'])
    if type(payload['revision']) is not int or payload['revision']<1:raise Problem(400,'Positive ursprüngliche Zahlungsrevision erforderlich.')
    source=historical or public_source(api.office,payload['payment_id'],payload['revision']);api._source_access(actor,source)
    if source['id']!=payload['payment_id'] or source['revision']!=payload['revision'] or source['source_hash']!=payload['source_hash'] or source['status']!='active':raise Problem(409,'Genau passende aktive ursprüngliche Altpostenzahlung erforderlich.')
    if historical is None and (public_source(api.office,source['id'])!=source or source['profile_ref']!=profile_reference(OpeningItems(api.office)._profile())):
        raise Problem(409,'Zahlungsquelle oder Buchführungsprofil wurde geändert.')
    target='opening_item_cash:'+source['id'];day=source['date'];net=cents(source['net']);tax=cents(source['tax'])
    if source['direction']=='in':
        postings=[_posting('euer','sales',net,day,payload['net_account'],target),_posting('euer','vat_collected',tax,day,payload['tax_account'],target),_posting('vat','output_vat',tax,day,payload['tax_account'],target)]
    else:
        # Old full input VAT is proved and preserved. Actual vendor payment is
        # EÜR expenditure now, but never a second VAT-input deduction.
        postings=[_posting('euer',source['category'],-net,day,payload['net_account'],target),_posting('euer','paid_input_vat',-tax,day,payload['tax_account'],target)]
    return source,target,postings,dict(date=day,net=source['net'],tax=source['tax'],gross=source['gross'],prior_input_vat_preserved=source['direction']=='out')

def catalog(api,actor,ledger):
    from business_accounting_open_items import OpeningItems,installed,public_source,BASE
    if not installed(api.office):return [],[],[]
    domain=OpeningItems(api.office)
    if actor is not None:domain._access(actor)
    current=domain._ledger();profile=domain._profile(optional=True);items=[];issues=[];movements=[]
    for entry in current['current'].values():
        if entry['operation']=='item':
            if entry['payload']['status']=='active' and profile and entry['profile_ref']!=profile_reference(profile):issues.append(dict(code='opening_item_profile_changed',source_id=entry['id'],date=entry['details']['opening_date'],source_path=BASE))
            continue
        source=public_source(api.office,entry['entity_key']);posted=ledger['active'].get('opening_item_cash:'+source['id']);reasons=[]
        if source['status']=='active' and not posted:reasons.append('opening_item_cash_classification_missing')
        if posted and posted['effect']['source']!=source:reasons.append('opening_item_cash_source_changed')
        if source['status']=='active' and (not profile or source['profile_ref']!=profile_reference(profile)):reasons.append('opening_item_profile_changed')
        items.append(dict(kind='opening_item_cash',id=source['id'],date=source['date'],source=source,current=posted,reasons=reasons))
        for movement in source['cash_movements']:movements.append(dict(source_kind='opening_item_cash',source_id=movement['id'],account=movement['account'],date=movement['date'],direction=movement['direction'],amount=movement['amount'],source_path=source['source_path']))
        for code in reasons:issues.append(dict(code=code,source_id=source['id'],date=source['date'],source_path=source['source_path']))
    for row in api.office.db.execute('SELECT DISTINCT entity_key FROM business_accounting_open_item_originals'):
        if row['entity_key'] not in current['current']:
            issues.append(dict(code='opening_item_review_missing',source_id=row['entity_key'],date=profile['profile']['bookkeeping_start'] if profile else '1900-01-01',source_path=BASE))
    return items,issues,movements

def verify_bank_source(office,source):
    import re
    from business_accounting_open_items import public_source,BASE
    match=re.fullmatch(BASE+r'/payments/([a-f0-9]{32})\?revision=([1-9][0-9]*)',source['source_path'])
    if not match:raise ValueError('Invalid old-item bank cash path')
    original=public_source(office,match[1],int(match[2]))
    if original['source_hash']!=source['origin_hash'] or source['source_id']!=original['id'] or len(original['cash_movements'])!=1:raise ValueError('Changed old-item cash bank source')
    return {key:original['cash_movements'][0][key] for key in ('account','date','direction','amount')}

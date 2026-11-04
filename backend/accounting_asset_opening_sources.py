"""Additive EÜR adapter for old assets; never contributes a cash movement."""
from core import Problem
from business_operations import identifier
from business_accounting_openings import hash_value,profile_reference,cents
from business_accounting_asset_openings import HistoricalAssets,installed,public_source,BASE
from accounting_asset_opening_rules import continuation


def prepare(api,actor,payload,ledger,historical):
    from business_accounting_euer import _shape,_year,_account,_posting
    _shape(payload,'asset_entry_id source_hash year account');identifier(payload['asset_entry_id']);hash_value(payload['source_hash']);year=_year(payload['year']);_account(payload['account'])
    if not installed(api.office):raise Problem(409,'Historischer Anlagenvortrag ist nicht installiert.')
    source=historical or public_source(api.office,payload['asset_entry_id']);api._source_access(actor,source)
    if source['source_hash']!=payload['source_hash'] or source['id']!=payload['asset_entry_id'] or source['status']!='active':
        raise Problem(409,'Genau die aktive belegte historische Anlagenquelle erforderlich.')
    if historical is None:
        assets=HistoricalAssets(api.office);current=assets._ledger()['current'].get(source['asset_key'])
        if not current or current['id']!=source['id'] or source['profile_ref']!=profile_reference(assets._profile()):
            raise Problem(409,'Anlagenquelle oder Buchführungsprofil wurde geändert; Übernahme zuerst erneut prüfen.')
    details=continuation(source['asset'],source['opening_date'],year)
    if cents(details['amount'])==0:raise Problem(409,'Für dieses Jahr ist keine zusätzliche positive AfA aus dem belegten Vortrag offen.')
    for previous in details['prior_required_years']:
        if 'opening_depreciation:'+source['id']+':'+str(previous) not in ledger['active']:
            raise Problem(409,'Frühere erforderliche Abschreibungsjahre dieser Anlagenfassung zuerst ausdrücklich buchen.')
    target='opening_depreciation:'+source['id']+':'+str(year);day=str(year)+'-12-31'
    return source,target,[_posting('euer','depreciation',-cents(details['amount']),day,payload['account'],target)],dict(
        details,date=day,asset_entry_id=source['id'],asset_key=source['asset_key'],basis=source['asset']['cost_basis'])


def catalog(api,actor):
    if not installed(api.office):return [],[]
    assets=HistoricalAssets(api.office)
    if actor is not None:assets._access(actor)
    ledger=assets._ledger();profile=assets._profile(optional=True);items=[];issues=[]
    for entry in ledger['current'].values():
        if entry['status']!='active':continue
        source=public_source(api.office,entry['id']);reasons=[]
        if not profile or entry['profile_ref']!=profile_reference(profile):reasons.append('historical_asset_profile_changed')
        items.append(dict(kind='opening_asset',id=entry['id'],date=entry['opening_date'],source=source,current=entry,reasons=reasons))
        for code in reasons:issues.append(dict(code=code,source_id=entry['id'],date=entry['opening_date'],source_path=source['source_path']))
    for row in api.office.db.execute('SELECT DISTINCT asset_key FROM business_accounting_asset_opening_originals'):
        if row['asset_key'] not in ledger['current']:
            issues.append(dict(code='historical_asset_review_missing',source_id=row['asset_key'],date=profile['profile']['bookkeeping_start'] if profile else '1900-01-01',source_path=BASE))
    return items,issues


def report_assets(api,actor,year,ledger,*,month=None):
    items,unused=catalog(api,actor);result=[];issues=[]
    for item in items:
        entry=item['current'];source=item['source']
        if int(entry['opening_date'][:4])>year:continue
        details=continuation(entry['asset'],entry['opening_date'],year);key='opening_depreciation:'+entry['id']+':'+str(year)
        depreciation=ledger['active'].get(key)
        if month is None or month.endswith('-12'):
            if cents(details['amount']) and not depreciation:
                issues.append(dict(code='historical_asset_depreciation_missing',source_id=entry['id'],date=str(year)+'-12-31',source_path=source['source_path']))
            for previous in details['prior_required_years']:
                if 'opening_depreciation:'+entry['id']+':'+str(previous) not in ledger['active']:
                    issues.append(dict(code='historical_asset_prior_depreciation_missing',source_id=entry['id'],date=str(year)+'-12-31',missing_year=previous,source_path=source['source_path']))
        if item['reasons']:
            for code in item['reasons']:issues.append(dict(code=code,source_id=entry['id'],date=month or str(year),source_path=source['source_path']))
        result.append(dict(entry_id=entry['id'],entry_hash=entry['content_hash'],asset_key=entry['asset_key'],asset=entry['asset'],
                           opening_date=entry['opening_date'],source=source,continuation=details,depreciation=depreciation))
    return result,issues


def validate_report_assets(api,report,ledger):
    """Validate retained rows against original sources, never today's catalog.

    Sources arriving after an export cannot be added to that old export. Every
    retained row and every booked historical asset in its journal prefix must
    nevertheless agree with the immutable original and that exact prefix.
    """
    rows=report['historical_assets'];year=report['year'];seen=set()
    if not isinstance(rows,list):raise ValueError('Invalid frozen historical asset list')
    for row in rows:
        if not isinstance(row,dict) or set(row)!=set('entry_id entry_hash asset_key asset opening_date source continuation depreciation'.split()):
            raise ValueError('Invalid frozen historical asset projection')
        source=public_source(api.office,row['entry_id'])
        if source['status']!='active' or source['id'] in seen or int(source['opening_date'][:4])>year:
            raise ValueError('Invalid or duplicate frozen historical asset source')
        seen.add(source['id']);details=continuation(source['asset'],source['opening_date'],year)
        expected=dict(entry_id=source['id'],entry_hash=source['entry_hash'],asset_key=source['asset_key'],asset=source['asset'],
                      opening_date=source['opening_date'],source=source,continuation=details,
                      depreciation=ledger['active'].get('opening_depreciation:'+source['id']+':'+str(year)))
        if row!=expected:raise ValueError('Frozen historical asset changed its original or journal projection')
    for entry in ledger['active'].values():
        if entry['effect']['operation']=='opening_depreciation':
            source=entry['effect']['source']
            if int(source['opening_date'][:4])<=year and source['id'] not in seen:
                raise ValueError('Frozen report omitted a booked historical asset')

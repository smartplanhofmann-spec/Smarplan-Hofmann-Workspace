"""Explicit old journal continuation, never an ordinary VAT claim or cash source."""
from calendar import monthrange
from core import Problem
from business_accounting_openings import shape,hash_value,integer,profile_reference
from accounting_year_opening_rules import year_key,signed_cents


def prepare(api,actor,payload,ledger,historical):
    from business_accounting_euer import _posting
    from business_accounting_year_openings import YearValues,public_source
    shape(payload,('year','revision','source_hash'));year_key(payload['year']);integer(payload['revision'],1);hash_value(payload['source_hash'])
    source=historical or public_source(api.office,payload['year'],payload['revision']);api._source_access(actor,source)
    if (source['id']!=payload['year'] or source['revision']!=payload['revision'] or source['source_hash']!=payload['source_hash'] or source['status']!='active'):
        raise Problem(409,'Genau passende aktive ursprüngliche Jahresquelle erforderlich.')
    if historical is None:
        domain=YearValues(api.office);entry=domain._ledger()['by_id'][source['entry_id']]
        if public_source(api.office,source['id'])!=source or source['profile_ref']!=profile_reference(domain._profile()):raise Problem(409,'Aktuelle Jahresquelle und unverändertes Buchführungsprofil erforderlich.')
        domain._known(entry['payload'],entry['profile'],ledger=ledger)
    target='opening_year_values:'+source['id']
    postings=[_posting(p['ledger'],p['category'],signed_cents(p['amount']),p['date'],p['account'],target+':'+p['economic_key']) for p in source['details']['historical_postings']]
    return source,target,postings,dict(date=source['date'],coverage=source['coverage'],cash_flow_created=False,new_input_vat_claim_created=False,original_periods_preserved=True)


def catalog(api,actor,ledger):
    from business_accounting_year_openings import YearValues,installed,public_source,BASE
    if not installed(api.office):return [],[]
    domain=YearValues(api.office)
    if actor is not None:domain._access(actor)
    current=domain._ledger();profile=domain._profile(optional=True);items=[];issues=[]
    for entry in current['current'].values():
        source=public_source(api.office,entry['entity_key']);posted=ledger['active'].get('opening_year_values:'+source['id']);reasons=[]
        if source['status']=='active':
            if not posted:reasons.append('opening_year_values_classification_missing')
            if profile is None or source['profile_ref']!=profile_reference(profile):reasons.append('opening_year_values_profile_changed')
            try:
                for value in entry['payload']['sources']:domain._resolve(source['id'],value,entry['profile'])
                domain._known(entry['payload'],entry['profile'],ledger=ledger)
            except Problem:reasons.append('opening_year_values_coverage_changed')
        if posted and posted['effect']['source']!=source:reasons.append('opening_year_values_source_changed')
        items.append(dict(kind='opening_year_values',id=source['id'],date=source['coverage']['from'],source=source,current=posted,reasons=reasons))
        for code in reasons:issues.append(dict(code=code,source_id=source['id'],date=source['coverage']['from'],source_path=source['source_path']))
    for row in api.office.db.execute('SELECT DISTINCT entity_key FROM business_accounting_year_opening_originals'):
        if row['entity_key'] not in current['current']:issues.append(dict(code='opening_year_values_review_missing',source_id=row['entity_key'],date=row['entity_key']+'-01-01',source_path=BASE))
    return items,issues


def report_projection(ledger,profile,year,month=None):
    entry=ledger['active'].get('opening_year_values:'+str(year))
    if not entry:return None,False
    source=entry['effect']['source'];coverage=source['coverage']
    value=dict(schema_version=1,entry_id=entry['id'],entry_hash=entry['entry_hash'],source_hash=source['source_hash'],source_path=source['source_path'],
               coverage=coverage,original_periods_preserved=True,cash_flow_created=False,new_input_vat_claim_created=False)
    first=month+'-01' if month else str(year)+'-01-01'
    last=month+'-'+str(monthrange(year,int(month[-2:]))[1]) if month else str(year)+'-12-31'
    opening=source['date']
    from datetime import date,timedelta
    needed_end=min(last,(date.fromisoformat(opening)-timedelta(days=1)).isoformat())
    covered=profile is not None and source['profile_ref']==profile_reference(profile) and coverage['from']<=first<=coverage['through'] and coverage['through']>=needed_end
    return value,covered


def validate_report(api,report,ledger,profile):
    expected,covered=report_projection(ledger,profile,report['year'],report['period'])
    if report.get('historical_year_values')!=expected:raise ValueError('Changed frozen original year coverage')
    partial=any(row['code']=='partial_period_profile_coverage' for row in report['issues'])
    if covered and partial:raise ValueError('Frozen report lost its evidenced original period coverage')
    if not covered and profile and max(profile['profile']['bookkeeping_start'],profile['profile']['vat_effective_from'])>(report['period']+'-01' if report['period'] else str(report['year'])+'-01-01') and not partial:raise ValueError('Frozen report invented missing historical coverage')

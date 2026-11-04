"""Bounded resumable company-event worker; never configures rules/providers."""
import uuid

from core import Problem
from business_operations import identifier
from business_company_events import CompanyEvents


def process(office, actor, *, request_id, after=None, page_size=100, max_pages=10, clock=None, delivery_transport=None):
    identifier(request_id,'Worker-Vorgangs-ID')
    if type(max_pages) is not int or not 1<=max_pages<=100:
        raise Problem(400,'Einen bis hundert begrenzte Verarbeitungsschritte angeben.')
    api=CompanyEvents(office,clock=clock,delivery_transport=delivery_transport)
    runs=[];cursor=after
    for _ in range(max_pages):
        command=dict(request_id=uuid.uuid5(uuid.NAMESPACE_URL,'smartplan-company-worker:'+request_id+':'+str(cursor)).hex,
                     limit=page_size,after=cursor)
        run=api.scan(actor,command);runs.append(run)
        cursor=run['next_after']
        if cursor is None: break
    return dict(schema_version=1,request_id=request_id,runs=runs,next_after=cursor,
                complete=cursor is None and not any(run['issues'] for run in runs))

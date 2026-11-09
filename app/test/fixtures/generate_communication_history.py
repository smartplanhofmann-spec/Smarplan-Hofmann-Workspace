"""Controlled canonical service/sales/document sources, not expected DTO mocks."""
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[3]
sys.path[:0]=[str(ROOT/'backend'),str(ROOT/'backend/online')]
from test_communication_history import CommunicationHistoryTests

f=CommunicationHistoryTests('runTest');f.setUp()
try:
    source=f.seed();f.document_mail(source['project_id'])
    scope=dict(customer_id=f.contact['id'])
    full=f.history.listing(f.owner,scope)
    first=f.history.listing(f.owner,dict(scope,limit='2'))
    second=f.history.listing(f.owner,dict(scope,limit='2',cursor=first['next_cursor']))
    project_scope=dict(scope,project_id=source['project_id'])
    value=dict(scope=scope,project_scope=project_scope,full=full,first=first,second=second,
        project=f.history.listing(f.owner,project_scope),
        filtered=f.history.listing(f.owner,dict(scope,kind='sales',q='corrected')))
    path=ROOT/'app/test/fixtures/communication_history.json'
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')
    print(dict(items=len(full['items']),kinds=sorted({i['kind'] for i in full['items']})))
finally:f.doCleanups()

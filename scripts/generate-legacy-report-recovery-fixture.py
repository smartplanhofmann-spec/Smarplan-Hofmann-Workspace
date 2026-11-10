"""Actual controlled MFA/HTTP report archives for independent native recovery."""
from pathlib import Path
import json
import sys

ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT/'backend'))
from core import canonical,digest
from business_offline_reports import ACTION
from online.test_legacy_service_report_recovery import LegacyServiceReportRecoveryHttpTests,capture_body,reference_hash


def bundle(f,body):
    office=f.company['office']
    accepted=f.f.call(f.company,'/business/service-reports/offline',body,status=201).json
    old={k:v for k,v in body.items() if k!='project_id'}
    query=dict(f.request,entry_id=body['entry_id'],request_id=body['request_id'],
        capture_hash=reference_hash([ACTION,body['project_id'],body['entry_id'],old]))
    proof=f.call(query).json
    record=dict(id=body['entry_id'],project_id=body['project_id'],kind='service',
        **body['content'],content=body['content'],content_hash=body['content_hash'],
        status='signed',capture_request=body,signer=body['signer'],strokes=body['strokes'],
        signed_at=body['signed_at'],sync_status='Auf diesem Gerät unterschrieben · Übertragung ausstehend')
    return dict(record=record,command=query,response=proof,accepted=accepted)


def main():
    f=LegacyServiceReportRecoveryHttpTests('runTest');f.setUp()
    try:
        cases=[bundle(f,f.body)]
        body=capture_body(f.company['office'],f.owner,f.f.project)
        body['strokes']=[[[0.0,-0.0],[1e-7,0.1],[1,1.0]]]
        cases.append(bundle(f,body))
        value=dict(schema_version=1,account_id=f.owner['id'],binding=f.f.binding(f.company),
            cases=cases,source='Actually accepted original capture and hash-only current-company MFA/HTTP response; synthetic data')
        target=ROOT/'app/test/fixtures/legacy_report_recovery.json'
        target.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        print(target.relative_to(ROOT),target.stat().st_size,'bytes; two actual archives and original read-only proofs')
    finally:f.doCleanups()


if __name__=='__main__':main()

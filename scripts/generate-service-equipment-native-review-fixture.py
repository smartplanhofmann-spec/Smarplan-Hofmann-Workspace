#!/usr/bin/env python3
"""Actual isolated service/custody replies for native lifecycle review."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))
from business_api import dispatch
from business_service import Service
from test_business_resource_custody import ResourceCustodyTests, req


def generate():
    f = ResourceCustodyTests('runTest')
    f.setUp()
    try:
        actor = f.office.user(f.office.login('custody-owner@example.test', 'Synthetic-resource-owner-password'))
        f.profile(serial_number='SYN-R0707-ORIGINAL', manufacturer='Synthetic maker', model='Review drill', location='Synthetic custody desk')
        proof = f.file()
        requirement = f.requirement()
        inspection = f.inspect(requirement, proof)
        issued = f.handoff()
        service = Service(f.office, clock=lambda: datetime(2026, 11, 3, 12, tzinfo=timezone.utc))
        incident = service.save(actor, req(revision=0, customer_id=f.customer['id'], person_id=None,
            project_id=f.project, asset_id=None, contract_id=None, visit_id=None, inquiry_id=None,
            defect_id=None, title='Synthetic private complaint R07.07', kind='complaint', priority='high',
            responsible_id=f.manager['id'], follow_up_on='2026-11-04', description='Synthetic private customer history'))
        incident = service.view(actor, incident['id'])
        return {'schema_version': 1, 'synthetic': True, 'actor': {k: actor[k] for k in ('id', 'email', 'role')},
            'capabilities': dispatch(f.office, actor, '/business/capabilities', 'GET', {})[0],
            'scoped_capabilities': dispatch(f.office, actor, '/business/capabilities', 'GET', {'_query': {'project_id': f.project}})[0],
            'service': {'item': incident, 'listing': service.listing(actor, {}),
                'options': service.options(actor, f.customer['id'], f.project),
                'history': service.history(actor, incident['id'])},
            'custody': {'item': f.api.view(actor, f.resource['id']), 'listing': f.api.listing(actor),
                'options': f.api.options(actor), 'history': f.api.history(actor, f.resource['id']),
                'proof': proof, 'inspection': inspection, 'issued': issued}}
    finally:
        f.doCleanups()


if __name__ == '__main__':
    data = (json.dumps(generate(), ensure_ascii=False, indent=2) + '\n').encode()
    for folder in ('docs/fixtures', 'app/test/fixtures'):
        target = ROOT / folder / 'service_equipment_native_review_2026.json'
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    print(len(data), hashlib.sha256(data).hexdigest())

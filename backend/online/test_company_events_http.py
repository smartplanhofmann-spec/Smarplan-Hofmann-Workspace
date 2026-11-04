"""Real MFA/HTTP commands and source-bound acceptance receipts."""
from datetime import datetime, timedelta, timezone
import json
import unittest
import uuid

from core import canonical
from business_assistant_sources import sha
from business_foundation import _transaction as transaction
from project_workspace import ProjectWorkspace
from online import test_portal_http as fixture


class CompanyEventsHTTPTests(unittest.TestCase):
    call=fixture.PortalHTTPTests.call
    staff_call=fixture.PortalHTTPTests.staff_call
    req=staticmethod(fixture.PortalHTTPTests.req)

    def setUp(self):
        fixture.PortalHTTPTests.setUp(self)
        self.actor=self.office.user(self.staff)
        with self.office.db:
            self.office.db.execute('INSERT INTO business_instance_identity VALUES(1,?,?,?,?,?)',
                (uuid.uuid4().hex,'portal.example.test',str(self.directory),'d'*64,datetime.now(timezone.utc).isoformat()))
        self.project=self.staff_call('/projects',dict(name='Synthetic event HTTP project',customer='Synthetic event customer'),status=201).json['id']
        with transaction(self.office):
            self.task=ProjectWorkspace(self.office).save_item(self.actor,self.project,'tasks',self.req(
                title='Actual HTTP source',details='Original source',status='todo',priority='normal',
                due_date=(datetime.now(timezone.utc)-timedelta(days=3)).date().isoformat(),assignee_id=self.actor['id']))

    def rule(self, **changes):
        command=self.req(id=uuid.uuid4().hex,revision=0,title='Explicit HTTP company rule',enabled=True,
            project_ids=[self.project],trigger='task.overdue',action='task.create',mode='approval',conditions=[],
            template=dict(title='HTTP accepted task',details='Fixed reviewed template',priority='normal',due_days=None),
            responsible_id=self.actor['id'],confirmation=True)
        command.update(changes)
        return command

    def acceptance(self, response, command, operation):
        self.assertEqual(response['acceptance'],dict(request_id=command['request_id'],operation=operation,request_hash=sha([operation,command])))

    def test_http_scan_approval_execution_and_all_original_acceptances(self):
        rule=self.rule();saved=self.staff_call('/business/company-events/rules',rule).json
        self.acceptance(saved,rule,'rule')
        command=self.req(limit=100,after=None)
        run=self.staff_call('/business/company-events/scan',command).json
        self.acceptance(run,command,'scan')
        self.assertEqual(self.staff_call('/business/company-events/scan',command).json,run)
        plan_id=run['items'][0]['plan_ids'][0]
        plan=self.staff_call('/business/company-events/plans/'+plan_id).json
        decision=self.req(plan_sha256=plan['sha256'],reason='Reviewed actual event and exact rule',confirmation=True)
        approved=self.staff_call('/business/company-events/plans/'+plan_id+'/approve',decision).json
        self.acceptance(approved,decision,'approve:'+plan_id)
        execute=self.req(plan_sha256=plan['sha256'],confirmation=True)
        done=self.staff_call('/business/company-events/plans/'+plan_id+'/execute',execute).json
        self.acceptance(done,execute,'execute:'+plan_id)
        self.assertEqual(done['status'],'succeeded')
        self.assertEqual(self.staff_call('/business/company-events/plans/'+plan_id+'/execute',execute).json,done)
        duplicate=self.staff_call('/business/company-events/plans/'+plan_id+'/execute',{**execute,'request_id':uuid.uuid4().hex},status=409).json
        self.assertEqual(duplicate['request_resolution'],'not_accepted')
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM workspace_items').fetchone()[0],2)
        for kind in ('plans','events','runs'):
            page=self.staff_call('/business/company-events/'+kind+'?limit=1').json
            self.assertEqual(len(page['items']),1);self.assertNotIn('acceptance',page['items'][0])

    def test_distinct_runs_have_distinct_bound_receipts_and_unmet_observations_remain_listed(self):
        self.staff_call('/business/company-events/rules',self.rule(conditions=[dict(field='overdue_days',operator='gte',value=10)]))
        first=self.req(limit=100,after=None);second=self.req(limit=100,after=None)
        left=self.staff_call('/business/company-events/scan',first).json
        right=self.staff_call('/business/company-events/scan',second).json
        self.assertNotEqual(left['id'],right['id']);self.assertNotEqual(left['acceptance'],right['acceptance'])
        self.assertEqual(left['items'][0]['plan_ids'],[])
        self.assertEqual(len(self.staff_call('/business/company-events/events').json['items']),1)
        self.assertEqual(len(self.staff_call('/business/company-events/runs').json['items']),2)

    def test_strict_shapes_duplicate_json_filters_public_and_offline_tokens(self):
        rule=self.rule()
        self.staff_call('/business/company-events/rules',raw=json.dumps(rule)[:-1]+',"mode":"auto"}',status=400)
        self.staff_call('/business/company-events/rules',{**rule,'instance_id':uuid.uuid4().hex},status=400)
        self.staff_call('/business/company-events/scan',self.req(limit=100,after=None,sources=[]),status=400)
        for path in ('/status?extra=1','/plans?limit=01','/runs?limit=0','/events?extra=1'):
            self.staff_call('/business/company-events'+path,status=400)
        self.call('/business/company-events/status',token='SPCT_'+'a'*43,status=401)
        device=self.staff_call('/business/offline/access',{},status=201).json['token']
        self.call('/business/company-events/status',token=device,status=403)
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM business_company_event_rules').fetchone()[0],0)


if __name__=='__main__':unittest.main()

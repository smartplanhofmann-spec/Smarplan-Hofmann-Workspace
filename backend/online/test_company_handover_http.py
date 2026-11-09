"""Two operator-bound companies with real MFA sessions and portable ZIP replies."""
import io
import json
import unittest
import uuid
import zipfile

from business_company_handover import CHECKS
from company_export_archive import verify
from online import test_instance_isolation as fixture


class CompanyHandoverHttp(unittest.TestCase):
    def setUp(self):
        self.f=fixture.InstanceIsolationTests('runTest');self.f.setUp();self.addCleanup(self.f.doCleanups)
        self.first,self.second=[self.f.start(value) for value in self.f.company]

    def call(self,company,path,body=None,**kwargs):
        return self.f.request(company,'/business/company-handover'+path,body,token=kwargs.pop('token',company['token']),**kwargs)

    def command(self,company):
        state=self.call(company,'').json
        self.assertTrue(state['ready'],state['blockers'])
        return dict(request_id=uuid.uuid4().hex,instance_id=state['instance_id'],catalog_sha256=state['catalog_sha256'],
            reason='Synthetic isolated company handover',confirmation=True,sensitive_data_confirmed=True)

    def test_mfa_bound_company_export_exact_replay_download_and_foreign_access(self):
        first,second=self.first,self.second
        command=self.command(first);created=self.call(first,'/exports',command,status=201).json
        replay=self.call(first,'/exports',command,status=201).json;self.assertEqual(replay,created)
        original=self.call(first,'/exports/'+created['id']+'/archive')
        self.assertEqual(original.mimetype,'application/zip')
        self.assertIn('.zip',original.headers['Content-Disposition'])
        self.assertTrue(verify(original.data,instance_id=first['instance_id'])['valid'])
        self.assertEqual(self.call(first,'/exports/'+created['id']+'/verify').json['sha256'],created['sha256'])
        with zipfile.ZipFile(io.BytesIO(original.data)) as archive:
            projects=[json.loads(line) for line in archive.read('data/projects.jsonl').splitlines()]
            self.assertEqual([row['id'] for row in projects],[first['project']])
            self.assertNotIn(second['project'].encode(),original.data)
        self.call(first,'/exports/'+created['id'],token=second['token'],status=401)
        self.call(second,'/exports/'+created['id'],status=404)
        self.call(second,'/exports',command,status=409)
        grant=self.f.request(first,'/offline/access/v2',{},token=first['token'],status=201).json
        origin=grant['binding']['instance_id']+':'+grant['binding']['account_id']
        self.call(first,'',token=grant['token'],origin=origin,status=403)
        self.assertEqual(self.call(first,'/exports/'+created['id']+'/archive').data,original.data)

    def test_strict_request_shapes_partial_checklist_and_fresh_owner_revocation(self):
        company=self.first;command=self.command(company)
        self.call(company,'?instance_id='+company['instance_id'],status=400)
        self.call(company,'',{'unexpected':'body'},method='GET',status=400)
        self.call(company,'/exports?unexpected=1',command,status=400)
        malformed=json.dumps(command)[:-1]+',"confirmation":false}'
        response=company['client'].post('/api/v1/business/company-handover/exports',base_url='https://'+company['host'],
            data=malformed,content_type='application/json',headers={'Authorization':'Bearer '+company['token']})
        self.assertEqual(response.status_code,400)
        created=self.call(company,'/exports',command,status=201).json
        review=dict(request_id=uuid.uuid4().hex,instance_id=company['instance_id'],expected_revision=0,export_id=created['id'],export_sha256=created['sha256'],
            checks={key:key=='export_opened' for key in CHECKS},evidence='Synthetic package reopened locally; other duties pending',reason='Initial checklist',confirmation=True)
        saved=self.call(company,'/exit-reviews',review,status=201).json
        self.assertEqual(saved['status'],'in_progress');self.assertFalse(saved['revocations_executed'])
        self.assertEqual(self.call(company,'/exit-reviews',review,status=201).json,saved)
        with company['office'].db:company['office'].db.execute("UPDATE users SET role='manager' WHERE email='owner@example.test'")
        self.call(company,'/exports',command,status=403)
        self.call(company,'/exports/'+created['id']+'/archive',status=403)


if __name__=='__main__':unittest.main()

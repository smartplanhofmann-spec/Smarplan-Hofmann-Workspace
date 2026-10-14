import json
import os
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch
from cryptography.fernet import Fernet
from core import Office, Problem, Signature
from onedrive import OneDrive
from server import make_handler


class OfficeTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.office=Office(Path(self.temp.name)/'test.sqlite3')
        self.owner_id=self.office.add_user('owner@example.test','Secure-test-owner-123','owner')
        self.tech_id=self.office.add_user('tech@example.test','Secure-test-tech-123','technician')
        self.owner=self.office.user(self.office.login('owner@example.test','Secure-test-owner-123'))
        self.tech=self.office.user(self.office.login('tech@example.test','Secure-test-tech-123'))
        self.project=self.office.add_project(self.owner,'Demoprojekt A','Musterkunde')
        self.private=self.office.add_project(self.owner,'Demoprojekt B','Anderer Musterkunde')
        with self.office.db:
            self.office.db.execute('INSERT INTO assignments VALUES(?,?)',(self.tech_id,self.project))

    def tearDown(self):
        self.office.db.close()
        self.temp.cleanup()

    def assert_problem(self,status,fn):
        with self.assertRaises(Problem) as e: fn()
        self.assertEqual(e.exception.status,status)

    def draft(self):
        return self.office.draft(self.tech,self.project,'Servicebericht','Beleuchtung geprüft.\nParametrierung angepasst.')

    def test_project_isolation_including_pdf(self):
        self.assertEqual([p['id'] for p in self.office.projects(self.tech)],[self.project])
        self.assert_problem(404,lambda:self.office.project(self.tech,self.private))
        private_report=self.office.draft(self.owner,self.private,'Lieferschein','Material geliefert')
        self.assert_problem(404,lambda:self.office.pdf(self.tech,private_report['id']))

    def test_technician_cannot_create_project_or_connect_drive(self):
        self.assert_problem(403,lambda:self.office.add_project(self.tech,'Hidden','Hidden'))
        self.assert_problem(403,lambda:OneDrive(self.office).begin(self.tech))

    def test_signature_binds_version_and_is_immutable(self):
        signature=Signature([[[.1,.5],[.8,.4]]])
        self.assertGreater(signature.width,0)
        self.assertGreater(signature.height,0)
        r=self.draft()
        self.assert_problem(409,lambda:self.office.sign(self.tech,r['id'],'changed','Max Muster',[[[.1,.5],[.8,.4]]]))
        signed=self.office.sign(self.tech,r['id'],r['content_hash'],'Max Muster',[[[.1,.5],[.3,.2],[.4,.8],[.8,.4]]])
        self.assertEqual(signed['status'],'signed')
        first=self.office.pdf(self.tech,r['id'])
        self.assertTrue(first.startswith(b'%PDF'))
        self.assertEqual(first,self.office.pdf(self.tech,r['id']))
        self.assert_problem(409,lambda:self.office.sign(self.tech,r['id'],r['content_hash'],'Other',[[[.1,.5],[.8,.4]]]))

    def test_revoked_project_access(self):
        r=self.draft()
        with self.office.db:
            self.office.db.execute('DELETE FROM assignments WHERE user_id=?',(self.tech_id,))
        self.assert_problem(404,lambda:self.office.report(self.tech,r['id']))

    def test_disabled_user_and_failed_login(self):
        token=self.office.login('tech@example.test','Secure-test-tech-123')
        with self.office.db: self.office.db.execute('UPDATE users SET active=0 WHERE id=?',(self.tech_id,))
        self.assert_problem(401,lambda:self.office.user(token))
        for _ in range(5): self.assert_problem(401,lambda:self.office.login('missing@example.test','invalid'))
        self.assert_problem(429,lambda:self.office.login('missing@example.test','invalid'))

    def test_pdf_tampering_detected(self):
        r=self.draft()
        self.office.sign(self.tech,r['id'],r['content_hash'],'Max',[[[.1,.5],[.8,.4]]])
        with self.office.db: self.office.db.execute('UPDATE reports SET pdf=? WHERE id=?',(b'altered',r['id']))
        self.assert_problem(500,lambda:self.office.pdf(self.tech,r['id']))

    def drive(self):
        env={'MS_CLIENT_ID':'test-app','MS_CLIENT_SECRET':'test-secret','OFFICE_VAULT_KEY':Fernet.generate_key().decode()}
        with patch.dict(os.environ,env): return OneDrive(self.office)

    def test_oauth_pkce_encryption_and_state_replay(self):
        from urllib.parse import parse_qs,urlsplit
        drive=self.drive()
        url=drive.begin(self.owner)
        query=parse_qs(urlsplit(url).query)
        self.assertEqual(query['code_challenge_method'],['S256'])
        self.assertEqual(query['scope'],['offline_access Files.ReadWrite.AppFolder'])
        state=query['state'][0]
        with patch.object(drive,'token_request',return_value={'access_token':'TEST-TOKEN','refresh_token':'REFRESH','expires_in':3600}):
            drive.callback(state,'auth-code')
        stored=self.office.db.execute("SELECT value FROM secrets WHERE name='onedrive'").fetchone()[0]
        self.assertNotIn('TEST-TOKEN',stored)
        self.assertEqual(drive.access_token(),'TEST-TOKEN')
        self.assert_problem(400,lambda:drive.callback(state,'replayed-code'))

    def test_onedrive_upload_uses_app_folder_and_denies_technician(self):
        r=self.draft()
        self.office.sign(self.tech,r['id'],r['content_hash'],'Max',[[[.1,.5],[.8,.4]]])
        drive=self.drive()
        self.assert_problem(403,lambda:drive.upload_report(self.tech,r['id']))
        with patch.object(drive,'access_token',return_value='TEST'),patch.object(drive,'request',side_effect=[{'id':'app-folder'},{'id':'file-1'}]) as request:
            self.assertTrue(drive.upload_report(self.owner,r['id'])['uploaded'])
        self.assertTrue(request.call_args_list[0].args[0].endswith('/me/drive/special/approot'))
        self.assertIn('/me/drive/items/app-folder:/',request.call_args_list[1].args[0])
        self.assertEqual(request.call_args_list[1].args[1],'PUT')

    def test_http_auth_and_project_permissions(self):
        server=ThreadingHTTPServer(('127.0.0.1',0),make_handler(self.office,OneDrive(self.office)))
        thread=threading.Thread(target=server.serve_forever,daemon=True); thread.start()
        base=f'http://127.0.0.1:{server.server_port}'
        try:
            with self.assertRaises(urllib.error.HTTPError) as e: urllib.request.urlopen(base+'/api/projects')
            self.assertEqual(e.exception.code,401)
            token=self.office.login('tech@example.test','Secure-test-tech-123')
            req=urllib.request.Request(base+'/api/users',headers={'Authorization':'Bearer '+token})
            with self.assertRaises(urllib.error.HTTPError) as e: urllib.request.urlopen(req)
            self.assertEqual(e.exception.code,403)
            req=urllib.request.Request(base+'/api/projects',headers={'Authorization':'Bearer '+token})
            with urllib.request.urlopen(req) as response: result=json.load(response)
            self.assertEqual(len(result),1)
        finally: server.shutdown(); server.server_close(); thread.join()


if __name__=='__main__': unittest.main()

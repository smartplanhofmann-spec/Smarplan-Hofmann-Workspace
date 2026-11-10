"""Run the real archived server and browser assets in a separate interpreter."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]


class ArchivedOnlineRuntimeTests(unittest.TestCase):
    def test_actual_commit_archive_serves_its_own_marker_and_browser_entrypoints_after_mfa(self):
        commit=subprocess.check_output(['git','-C',str(ROOT),'rev-parse','HEAD'],text=True).strip()
        self.assertRegex(commit,r'^[a-f0-9]{40}$')
        with tempfile.TemporaryDirectory(prefix='synthetic-archived-online-')as directory:
            root=Path(directory);app=root/'app';app.mkdir();archive=root/'source.tar'
            subprocess.run(['git','-c','tar.umask=0022','-C',str(ROOT),'archive','--format=tar',
                '--output',str(archive),commit,'backend','web'],check=True,capture_output=True)
            with tarfile.open(archive)as source:source.extractall(app,filter='data')
            code='''import json,sys
from pathlib import Path
sys.path.insert(0,sys.argv[1])
from online.installation import MARKER,write_context
write_context(MARKER,sys.argv[2])
from online.test_offline_instance_binding import OfflineInstanceBindingHttpTests
f=OfflineInstanceBindingHttpTests('runTest');f.setUp()
try:
 value=f.call(f.a,'/business/installation').json
 assert value['source_commit']==sys.argv[2] and value['status']=='recorded'
 app=f.a['client'];origin='https://'+f.a['host']
 for name in ('','office.js','office.css','installation-context.js','payroll-factor-claim-travel.js','bank-camt-contract.js','bank-camt-ui.js','payroll-rv-lifecycle.js'):
  response=app.get('/office/'+name,base_url=origin)
  assert response.status_code==200,(name,response.status_code)
 assert 'API-Kompatibilität' in (Path(sys.argv[1]).parent/'web/office/office.js').read_text()
 from bank_camt_2026_v1 import _schema
 _schema()
 from payroll_minijob_rv_lifecycle_2026 import RULES_SHA256
 from business_payroll_rv_lifecycle import PayrollRvLifecycle
 capabilities=f.call(f.a,'/business/capabilities').json
 assert 'payroll_rv_lifecycle' in capabilities['features']
 assert 'business_payroll_rv_lifecycle' in capabilities['capabilities']
 assert RULES_SHA256 in (Path(sys.argv[1]).parent/'web/office/payroll-rv-lifecycle.js').read_text()
 print(json.dumps(dict(source_commit=value['source_commit'],mfa=True,browser_assets=8,bank_xml_schema=True,rv_backend_and_browser=True)))
finally:f.doCleanups()
'''
            result=subprocess.run([sys.executable,'-I','-B','-c',code,str(app/'backend'),commit],
                cwd=root,env={k:v for k,v in os.environ.items()if k not in ('PYTHONPATH','PYTHONHOME','SMARTPLAN_TEST_DSN')},
                capture_output=True,text=True,timeout=120)
            self.assertEqual(result.returncode,0,result.stderr[-4000:])
            proof=json.loads(result.stdout)
            self.assertEqual(proof,dict(source_commit=commit,mfa=True,browser_assets=8,bank_xml_schema=True,rv_backend_and_browser=True))


if __name__=='__main__':unittest.main()

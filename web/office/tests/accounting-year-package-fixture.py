"""Actual accepted synthetic exports on a disposable bound instance and real MFA."""
import argparse,json,signal,sys,tempfile,uuid
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[3]/'backend'))
from cryptography.fernet import Fernet
from werkzeug.serving import make_server
from test_business_accounting_euer import EuerWorkflowTests
from test_accounting_year_package_http import MFA_SCHEMA
from online.instance import bind
from online.storage import Storage
from online.web import create_app
from serve_fixture import LoopbackProxyContract

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--ready-file',type=Path,required=True);args=parser.parse_args()
    def stop(*_):raise SystemExit(0)
    signal.signal(signal.SIGTERM,stop)
    f=EuerWorkflowTests('runTest');f.setUp();server=None
    with tempfile.TemporaryDirectory(prefix='synthetic-year-browser-') as directory:
      try:
        key=Fernet.generate_key();instance=uuid.uuid4().hex
        storage=Storage(f.office,key,'127.0.0.1',config={'server':{'path':str(Path(directory)/'company')}})
        bind(f.office,instance,'127.0.0.1',key,storage)
        income=f.sale();sale=f.post('cash',f.cash_payload(income))
        receipt=f.incoming();f.post('input_vat',f.vat_payload(receipt));expense=f.payout(receipt);f.post('cash',f.cash_payload(expense,'materials'))
        changed=f.cash_payload(income);changed['lines'][0]['account']='4401';f.post('correct',dict(entry_id=sale['id'],operation='cash',payload=changed))
        first=f.post('export',{'year':2026});f.incoming('100.00','19.00','119.00');second=f.post('export',{'year':2026})
        email='year-browser-owner@example.test';reader='year-browser-reader@example.test';password='Synthetic-password-123'
        f.office.add_user(email,password,'owner');reader_user=f.office.add_user(reader,password,'technician')
        f.office.assign(f.owner,f.fixture.project,reader_user)
        f.office.db.executescript(MFA_SCHEMA);f.office.db.commit()
        app=create_app(office=f.office,key=key,host='127.0.0.1',instance_id=instance,storage=storage)
        server=make_server('127.0.0.1',0,LoopbackProxyContract(app),threaded=True)
        args.ready_file.write_text(json.dumps(dict(base_url='http://127.0.0.1:'+str(server.server_port),email=email,reader_email=reader,reader_id=reader_user,exports=[dict(id=e['id'],sequence=e['sequence']) for e in [first,second]])));args.ready_file.chmod(0o600)
        server.serve_forever()
      finally:
        if server:server.server_close()
        f.doCleanups();args.ready_file.unlink(missing_ok=True)
if __name__=='__main__':main()

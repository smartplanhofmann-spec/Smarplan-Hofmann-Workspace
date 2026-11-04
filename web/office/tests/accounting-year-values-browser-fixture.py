"""Disposable actual original-backed prior-year-period setup and real MFA HTTP."""
import argparse,json,signal,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[3]/'backend'))
from cryptography.fernet import Fernet
from werkzeug.serving import make_server
from test_accounting_year_openings import YearOpeningWorkflow
from online.web import create_app
from serve_fixture import LoopbackProxyContract
MFA='''CREATE TABLE mfa(user_id TEXT PRIMARY KEY REFERENCES users(id),secret TEXT NOT NULL,last_step BIGINT NOT NULL DEFAULT -1,recovery TEXT NOT NULL);CREATE TABLE auth_challenges(token TEXT PRIMARY KEY,user_id TEXT REFERENCES users(id),credential TEXT NOT NULL,secret TEXT NOT NULL,expiry DOUBLE PRECISION NOT NULL,failures INTEGER NOT NULL DEFAULT 0);CREATE TABLE login_limits(key TEXT PRIMARY KEY,failures INTEGER NOT NULL,reset_at DOUBLE PRECISION NOT NULL);'''
def main():
 p=argparse.ArgumentParser();p.add_argument('--ready-file',type=Path,required=True);a=p.parse_args()
 def stop(*_):raise SystemExit(0)
 signal.signal(signal.SIGTERM,stop)
 f=YearOpeningWorkflow('runTest');f.setUp();server=None
 try:
  email='year-values-browser-owner@example.test';f.office.add_user(email,'Synthetic-password-123','owner')
  f.office.db.executescript(MFA);f.office.db.commit()
  app=create_app(office=f.office,key=Fernet.generate_key(),host='127.0.0.1');server=make_server('127.0.0.1',0,LoopbackProxyContract(app),threaded=True)
  a.ready_file.write_text(json.dumps(dict(base_url='http://127.0.0.1:'+str(server.server_port),email=email,payload=f.payload,old_item=f.old)));a.ready_file.chmod(0o600);server.serve_forever()
 finally:
  if server:server.server_close()
  f.doCleanups();a.ready_file.unlink(missing_ok=True)
if __name__=='__main__':main()

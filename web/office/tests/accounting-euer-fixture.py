"""Disposable loopback EÜR browser fixture; real auth/MFA/domain, synthetic archives.

No issued sessions or tax decisions are injected. Existing documented sources are
seeded; every EÜR/profile decision is performed through the browser workflow.
"""
import argparse
from pathlib import Path
import json
import signal
import sys
import uuid
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / 'backend'))
from cryptography.fernet import Fernet
from werkzeug.serving import make_server
from business_accounting_euer import EuerAccounting
from online.web import create_app
from test_business_accounting_components import ComponentTests
from test_business_accounting_euer import EuerWorkflowTests
from serve_fixture import LoopbackProxyContract


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--ready-file',required=True,type=Path);args=parser.parse_args()
    def stop(_signum,_frame):raise SystemExit(0)
    signal.signal(signal.SIGTERM,stop)
    f=ComponentTests('runTest');f.setUp();server=None
    try:
        case=EuerWorkflowTests('runTest');case.fixture=f;case.office=f.office;case.owner=f.owner;case.api=EuerAccounting(f.office,clock=f.clock)
        sale=case.sale()
        def receipt(label,net,tax,gross):
            value=case.incoming(net,tax,gross)
            f.finance.review_receipt(f.owner,value['id'],f.review_body(revision=2,net=net,tax=tax,gross=gross,vendor=label,invoice_number='SYN-'+label,issue_date='2026-11-01'))
            return value
        expense=receipt('Synthetic running expense','50.00','9.50','59.50');expense_event=case.payout(expense)
        tax=receipt('Synthetic VAT transfer','9.50','0.00','9.50')
        asset=receipt('Synthetic new asset','1000.00','190.00','1190.00');asset_event=case.payout(asset,'1190.00')
        f.office.db.executescript('''CREATE TABLE mfa(user_id TEXT PRIMARY KEY REFERENCES users(id),secret TEXT NOT NULL,last_step BIGINT NOT NULL DEFAULT -1,recovery TEXT NOT NULL);
        CREATE TABLE auth_challenges(token TEXT PRIMARY KEY,user_id TEXT REFERENCES users(id),credential TEXT NOT NULL,secret TEXT NOT NULL,expiry DOUBLE PRECISION NOT NULL,failures INTEGER NOT NULL DEFAULT 0);
        CREATE TABLE login_limits(key TEXT PRIMARY KEY,failures INTEGER NOT NULL,reset_at DOUBLE PRECISION NOT NULL);''')
        f.office.db.commit()
        app=create_app(office=f.office,key=Fernet.generate_key(),host='127.0.0.1')
        server=make_server('127.0.0.1',0,LoopbackProxyContract(app),threaded=True)
        metadata=dict(base_url='http://127.0.0.1:'+str(server.server_port),email=f.owner['email'],project_id=f.project,sale_id=sale['id'],expense_id=expense['id'],expense_event_id=expense_event['id'],tax_id=tax['id'],asset_id=asset['id'],asset_event_id=asset_event['id'])
        args.ready_file.write_text(json.dumps(metadata));args.ready_file.chmod(0o600)
        server.serve_forever()
    finally:
        if server:server.server_close()
        f.doCleanups();args.ready_file.unlink(missing_ok=True)
if __name__=='__main__':main()

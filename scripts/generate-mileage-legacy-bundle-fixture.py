#!/usr/bin/env python3
"""Freeze actual earlier V4 originals; tests never rewrite a claim to look old."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[1]


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--source-commit',default='ae0c851c9b7f3b99736c29f99da24cee070185d0');args=parser.parse_args()
    with tempfile.TemporaryDirectory(prefix='synthetic-old-mileage-source-') as directory:
        target=Path(directory)/'backend'
        shutil.copytree(ROOT/'backend',target,ignore=shutil.ignore_patterns('.venv','__pycache__','*.pyc','*.sqlite3','*.db'))
        sources={}
        for name in ('business_travel_mileage.py','business_travel_allowances.py'):
            raw=subprocess.check_output(['git','-C',str(ROOT),'show',args.source_commit+':backend/'+name])
            (target/name).write_bytes(raw);sources[name]=hashlib.sha256(raw).hexdigest()
        runner=Path(directory)/'produce.py'
        runner.write_text('''import base64,json,sqlite3,sys,unittest
from pathlib import Path
sys.path.insert(0,sys.argv[1])
from core import canonical
from test_business_travel_mileage import MileageFixture
from travel_allowance_cash import record_payment
from business_travel_allowances import validate_integrity
owner=unittest.TestCase();x=MileageFixture(owner);f=x.f
try:
 extra=f.upload(visible=True,marker=b'Actual earlier second-leg original Y')
 x.input['details']['source_file_ids'].append(extra['id'])
 x.input['details']['mileage']['legs'][1]['evidence_file_id']=extra['id']
 x.submitted();settlement=x.approval()
 payment_command=f.payment(settlement,3000);payment=record_payment(x.api,f.owner,payment_command)
 assert validate_integrity(f.office)
 pdf=x.api.export(f.owner,settlement['id'],1,'pdf')[0]
 value=dict(synthetic_only=True,employee=f.employee,actor=f.owner,employee_actor=f.technician,
  trip_command=x.input,settlement_command=x.approve_command,settlement=settlement,
  receipt=x.api.status(f.owner,x.approve_command['request_id']),payment_command=payment_command,
  payment=payment,pdf_base64=base64.b64encode(pdf).decode(),
  claims=[dict(row) for row in f.office.db.execute('SELECT * FROM business_travel_claims ORDER BY claim_key')])
 Path(sys.argv[3]).write_text(canonical(value))
 f.office.db.commit();copy=sqlite3.connect(sys.argv[2]);f.office.db.backup(copy);copy.close()
finally:owner.doCleanups()
''')
        database=Path(directory)/'original.sqlite3';document=Path(directory)/'original.json'
        subprocess.run([sys.executable,'-I',str(runner),str(target),str(database),str(document)],check=True,timeout=120)
        data=json.loads(document.read_text());data.update(source_commit=args.source_commit,source_sha256=sources)
        out=ROOT/'backend/testdata';out.mkdir(exist_ok=True)
        (out/'mileage_legacy_bundle.sqlite3.gz').write_bytes(gzip.compress(database.read_bytes(),mtime=0))
        (out/'mileage_legacy_bundle.json').write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
        print(out/'mileage_legacy_bundle.sqlite3.gz')


if __name__=='__main__':main()

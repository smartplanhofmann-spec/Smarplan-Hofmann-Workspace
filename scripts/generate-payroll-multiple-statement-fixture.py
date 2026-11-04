"""Generate actual reduced Source5 employee statements and original PDFs/JSON."""
import base64
import json
from pathlib import Path
from business_payroll_statements import PayrollStatements
from test_business_payroll_statements_v7 import Source5StatementTests


def main():
    f=Source5StatementTests('runTest');f.setUp()
    try:
        api=f.api;actor=f.f.technician;run=f.run
        statement=api.get(actor,run['id'])['statement']
        previous=api.get(actor,run['id'],dict(revision='1'))['statement']
        query=dict(revision='2',statement_hash=statement['statement_hash'])
        pdf,_=api.export(actor,run['id'],query)
        document,_=api.export(actor,run['id'],query,file_format='json')
        old_pdf,_=api.export(actor,run['id'],dict(revision='1',statement_hash=previous['statement_hash']))
        output=dict(employee=f.f.employee,actor=actor,statement=statement,previous=previous,
            page=api.records(actor),history=api.get(actor,run['id'],history=True),
            pdf_base64=base64.b64encode(pdf).decode(),previous_pdf_base64=base64.b64encode(old_pdf).decode(),
            json_base64=base64.b64encode(document).decode())
        target=Path(__file__).resolve().parents[1]/'app/test/fixtures/payroll_statements_v7.json'
        target.write_text(json.dumps(output,ensure_ascii=False,indent=2)+'\n');target.chmod(0o644)
        print('Generated actual Source5 own schema4 fixture:',target.name,target.stat().st_size)
    finally:f.doCleanups()


if __name__=='__main__':main()

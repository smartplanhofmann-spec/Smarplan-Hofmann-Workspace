"""Historical CRLF factor originals remain exact on LF, without weaker checks."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import business_schema
from business_payroll import _calculate_source,calculation_matches_source
from business_payroll_statements import PayrollStatements
from core import canonical
import test_business_payroll_accounts as accounts


class FactorOriginalTransport(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.copied=tempfile.TemporaryDirectory(prefix='historical-payroll-crlf-')
        cls.root=Path(cls.copied.name)
        for source in Path(__file__).resolve().parent.glob('*.py'):
            if not source.name.startswith('test'):
                lf=source.read_bytes().replace(b'\r\n',b'\n')
                (cls.root/source.name).write_bytes(lf.replace(b'\n',b'\r\n'))
        cls.addClassCleanup(cls.copied.cleanup)

    def setUp(self):
        self.f=accounts.PayrollAccountTests('runTest');self.f.setUp();self.addCleanup(self.f.doCleanups)

    def windows_calculate(self,source,*,rule_version=None):
        # Isolated execution of trusted production source bytes; no office DB,
        # external process tool or provider is available to this calculation.
        program=('import json,sys;sys.path.insert(0,sys.argv[1]);'
            'from business_payroll import _calculate_source;data=json.load(sys.stdin);'
            'print(json.dumps(_calculate_source(data["source"],rule_version=data["rule_version"])))')
        result=subprocess.run([sys.executable,'-I','-B','-c',program,str(self.root)],
            input=json.dumps(dict(source=source,rule_version=rule_version)),text=True,
            capture_output=True,check=True,timeout=30,cwd=self.root,
            env={'PATH':os.environ.get('PATH',''),'LANG':'C.UTF-8'})
        return json.loads(result.stdout)

    def original(self):
        f=self.f
        data=f.case('regular',500000,tax_class=4,health_additional_percent='2.90',
            tax_allowance_monthly_minor=0,tax_addition_monthly_minor=0,
            special_cases=['tax_factor'],tax_factor='0.753')
        with patch('business_payroll._calculate_source',side_effect=self.windows_calculate):
            command=f.command(data);run=f.payroll.finalize(f.owner,command)
        return data,command,run

    def test_actual_crlf_calculation_matches_only_exact_trusted_provenance_pair(self):
        _,_,run=self.original();source=run['source'];old=run['calculation']
        current=_calculate_source(source,rule_version=old['rule_version'])
        self.assertNotEqual(current['rules_sha256'],old['rules_sha256'])
        self.assertNotEqual(current['pap_provenance_sha256'],old['pap_provenance_sha256'])
        self.assertEqual({k:v for k,v in current.items() if k not in ('rules_sha256','pap_provenance_sha256')},
            {k:v for k,v in old.items() if k not in ('rules_sha256','pap_provenance_sha256')})
        self.assertTrue(calculation_matches_source(source,old))
        self.assertFalse(calculation_matches_source(source,dict(old,rules_sha256=current['rules_sha256'])))
        self.assertFalse(calculation_matches_source(source,dict(old,pap_provenance_sha256=current['pap_provenance_sha256'])))
        for key in ('rules_sha256','pap_provenance_sha256'):
            self.assertFalse(calculation_matches_source(source,dict(old,**{key:'0'*64})))
        for key in ('net_minor','gross_minor','individual_wage_tax_minor','employee_tax_minor'):
            self.assertFalse(calculation_matches_source(source,dict(old,**{key:old[key]+1})))
        changed=json.loads(canonical(old));changed['tax_parameters']['tax_factor']='0.900'
        self.assertFalse(calculation_matches_source(source,changed))
        self.assertFalse(calculation_matches_source(source,dict(old,extra='unrecognized')))

    def test_original_pdf_hash_receipt_statement_ledger_and_fresh_rights_are_preserved(self):
        _,command,run=self.original();f=self.f
        frozen=canonical(run);pdf=f.payroll.export(f.owner,run['id'],'pdf')[0]
        before=[tuple(row) for row in f.office.db.execute('SELECT id,revision,content_hash,pdf_sha256,payload_json FROM business_payroll_events ORDER BY id,revision')]
        self.assertTrue(business_schema.validate_integrity(f.office))
        self.assertEqual(f.payroll.finalize(f.owner,command),run)
        self.assertEqual(PayrollStatements(f.office).get(f.technician,run['id'])['statement']['calculation']['net_minor'],332342)
        self.assertEqual(f.ledger()['totals']['net_minor'],332342)
        f.problem(403,lambda:f.payroll.export(f.technician,run['id'],'pdf'))
        self.assertEqual(f.payroll.export(f.owner,run['id'],'pdf')[0],pdf)
        self.assertEqual(canonical(f.payroll.get(f.owner,'run',run['id'])),frozen)
        self.assertEqual([tuple(row) for row in f.office.db.execute('SELECT id,revision,content_hash,pdf_sha256,payload_json FROM business_payroll_events ORDER BY id,revision')],before)

    def test_native_factor_correction_keeps_cross_platform_original_and_delta(self):
        data,command,run=self.original();f=self.f
        pdf=f.payroll.export(f.owner,run['id'],'pdf')[0]
        saved=f.payroll.save_profile(f.owner,dict(request_id=accounts.monthly.rid(),employee_id=f.employee['id'],
            id=data['profile']['id'],revision=1,profile=dict(data['profile']['profile'],tax_factor='0.900'),
            source_file_id=data['file']['id'],confirmed=True,correction_reason='Synthetic actual new ELStAM original'))
        data['inputs']['profile_revision']=saved['revision']
        changed=f.payroll.finalize(f.owner,f.command(data,id=run['id'],revision=1,
            correction_reason='Synthetic original-preserving native correction'))
        self.assertEqual(changed['calculation']['net_minor'],320834)
        self.assertEqual(changed['delta']['net_minor'],-11508)
        self.assertEqual(changed['delta']['employee_tax_minor'],11508)
        self.assertEqual(f.payroll.finalize(f.owner,command),run)
        self.assertEqual(f.payroll.export(f.owner,run['id'],'pdf','1')[0],pdf)
        self.assertTrue(business_schema.validate_integrity(f.office))

    def test_crlf_runtime_also_recognizes_unchanged_lf_original(self):
        _,_,run=self.original()
        lf=_calculate_source(run['source'],rule_version=run['calculation']['rule_version'])
        program=('import json,sys;sys.path.insert(0,sys.argv[1]);'
            'from business_payroll import calculation_matches_source;data=json.load(sys.stdin);'
            'print(json.dumps(calculation_matches_source(data["source"],data["calculation"])))')
        result=subprocess.run([sys.executable,'-I','-B','-c',program,str(self.root)],
            input=json.dumps(dict(source=run['source'],calculation=lf)),text=True,
            capture_output=True,check=True,timeout=30,cwd=self.root,
            env={'PATH':os.environ.get('PATH',''),'LANG':'C.UTF-8'})
        self.assertIs(json.loads(result.stdout),True)

    def test_actual_payment_and_remittance_sources_do_not_reject_original_encoding(self):
        data,_,run=self.original();f=self.f
        identity,_=f.save_account(data,'identity',f.identity_details(data))
        paid,_=f.save_account(data,'payment',f.payment_details(run,identity))
        from payroll_cash_sources import Sources
        from business_payroll_cash import PayrollCash
        adapter=Sources(PayrollCash(f.office))
        account=adapter.account(f.owner,dict(account_record_id=paid['id'],revision=paid['revision'],content_hash=paid['content_hash']))
        self.assertEqual(account['calculation'],run['calculation'])
        remittance=adapter.remittance(f.owner,dict(source_kind='run',id=run['id'],revision=run['revision'],content_hash=run['content_hash']))
        self.assertEqual(remittance['calculation'],run['calculation'])
        self.assertTrue(business_schema.validate_integrity(f.office))

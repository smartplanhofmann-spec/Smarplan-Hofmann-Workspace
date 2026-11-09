"""Real archived CRLF travel originals survive LF checks without rewriting."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import business_schema
from core import canonical
from payroll_travel_2026 import calculate
from travel_provenance_compat import calculation_matches
from travel_allowance_cash import record_payment,public_source
import test_business_travel_v3 as travel
import test_payroll_travel_2026 as basic
import test_payroll_travel_transport_2026 as transport
import test_business_travel_finance as finance


class TravelOriginalTransport(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.copied=tempfile.TemporaryDirectory(prefix='historical-travel-crlf-')
        cls.root=Path(cls.copied.name);cls.addClassCleanup(cls.copied.cleanup)
        for source in Path(__file__).resolve().parent.glob('*.py'):
            if not source.name.startswith('test'):
                (cls.root/source.name).write_bytes(source.read_bytes().replace(b'\r\n',b'\n').replace(b'\n',b'\r\n'))

    def setUp(self):
        self.f=travel.TravelV3WorkflowTests('runTest');self.f.setUp();self.addCleanup(self.f.doCleanups)

    def windows_calculate(self,trips,sites,**options):
        if options.get('rule_version') is None:
            import payroll_travel_2026
            options=dict(options,rule_version=payroll_travel_2026.RULE_VERSION)
        code=('import sys,json;sys.path.insert(0,sys.argv[1]);from payroll_travel_2026 import calculate;'
            'd=json.load(sys.stdin);print(json.dumps(calculate(d["trips"],d["sites"],**d["options"])))')
        result=subprocess.run([sys.executable,'-I','-B','-c',code,str(self.root)],text=True,
            input=json.dumps(dict(trips=trips,sites=sites,options=options)),capture_output=True,
            check=True,timeout=30,cwd=self.root,env={'PATH':os.environ.get('PATH',''),'LANG':'C.UTF-8'})
        return json.loads(result.stdout)

    def original(self):
        f=self.f
        with patch('business_travel_allowances.calculate',side_effect=self.windows_calculate):
            body,_=f.mixed_body();trip=f.submit_body(body)
            command=f.approval(trip,requested_meal_minor=933)
            receipt=f.api.approve(f.owner,command)
        return trip,command,receipt

    def recompute(self,record):
        source=record['sources'];d=record['details']
        return calculate(source['trips'],source['sites'],history_trips=source['history_trips'],
            settlement_unit=d['settlement_unit'],tax_choice=d['tax_choice'],
            requested_meal_minor=d['requested_meal_minor'],requested_lodging_minor=d['requested_lodging_minor'],
            already_paid_minor=record['calculation']['totals']['already_paid_minor'],rule_version=record['calculation']['rule_version'])

    def test_genuine_crlf_ground_and_mixed_sources_require_exact_metadata_and_money(self):
        _,_,receipt=self.original();record=receipt['result'];old=record['calculation'];current=self.recompute(record)
        self.assertNotEqual(old['rule_hash'],current['rule_hash'])
        self.assertEqual(old['totals'],current['totals'])
        args=dict(trips=record['sources']['trips'],sites=record['sources']['sites'])
        frozen=canonical(old);self.assertTrue(calculation_matches(current,old,**args))
        for collection in ('ground_calendar_sources','mixed_program_sources'):
            for key in ('module_hash','facts_hash'):
                changed=json.loads(frozen);changed[collection][0][key]='0'*64
                self.assertFalse(calculation_matches(current,changed,**args))
            changed=json.loads(frozen);changed[collection][0]['facts_hash']=current[collection][0]['facts_hash']
            self.assertFalse(calculation_matches(current,changed,**args))
        changed=json.loads(frozen);changed['rule_hash']='0'*64
        self.assertFalse(calculation_matches(current,changed,**args))
        changed=json.loads(frozen);changed['totals']['tax_free_minor']+=1
        self.assertFalse(calculation_matches(current,changed,**args))
        changed=json.loads(frozen);changed['days'][0]['meal_allowance_minor']+=1
        self.assertFalse(calculation_matches(current,changed,**args))
        self.assertEqual(canonical(old),frozen)

    def test_actual_original_exports_receipt_and_private_sources_remain_unchanged(self):
        _,command,receipt=self.original();f=self.f;record=receipt['result']
        original_json=f.api.export(f.owner,record['id'],1,'json')[0]
        original_pdf=f.api.export(f.owner,record['id'],1,'pdf')[0]
        before=[tuple(row) for row in f.office.db.execute('SELECT id,revision,content_hash,payload_json FROM business_travel_settlements ORDER BY id,revision')]
        self.assertTrue(business_schema.validate_integrity(f.office))
        self.assertEqual(f.api.approve(f.owner,command),receipt)
        self.assertEqual(f.api.status(f.owner,command['request_id']),receipt)
        self.assertEqual(f.api.export(f.owner,record['id'],1,'json')[0],original_json)
        self.assertEqual(f.api.export(f.owner,record['id'],1,'pdf')[0],original_pdf)
        self.assertEqual([tuple(row) for row in f.office.db.execute('SELECT id,revision,content_hash,payload_json FROM business_travel_settlements ORDER BY id,revision')],before)
        f.office.db.execute('UPDATE users SET active=0 WHERE id=?',(f.owner['id'],))
        f.problem(401,lambda:f.api.status(f.owner,command['request_id']))

    def test_actual_partial_payments_still_use_original_and_never_duplicate_cash(self):
        _,_,receipt=self.original();f=self.f;record=receipt['result']
        payment=f.payment(record,533);accepted=record_payment(f.api,f.owner,payment)
        self.assertEqual(record_payment(f.api,f.owner,payment),accepted)
        self.assertEqual(public_source(f.office,accepted['target_id'])['cash_movements'][0]['amount'],'5.33')
        remaining=record_payment(f.api,f.owner,f.payment(record,400))
        self.assertEqual(public_source(f.office,remaining['target_id'])['cash_movements'][0]['amount'],'4.00')
        self.assertEqual(f.office.db.execute('SELECT COUNT(*) FROM business_travel_payments').fetchone()[0],2)
        self.assertTrue(business_schema.validate_integrity(f.office))

    def test_native_correction_keeps_old_crlf_original_and_actual_overpayment(self):
        trip,command,receipt=self.original();f=self.f;record=receipt['result']
        pdf=f.api.export(f.owner,record['id'],1,'pdf')[0]
        record_payment(f.api,f.owner,f.payment(record,933))
        changed_command=f.approval(trip,requested_meal_minor=900,correction_of=travel._ref(record))
        changed_command.update(id=record['id'],revision=1)
        changed=f.api.approve(f.owner,changed_command)['result']
        self.assertEqual(changed['calculation']['totals']['tax_free_minor'],900)
        self.assertEqual(changed['calculation']['totals']['overpaid_minor'],33)
        self.assertEqual(f.api.approve(f.owner,command),receipt)
        self.assertEqual(f.api.export(f.owner,record['id'],1,'pdf')[0],pdf)
        self.assertTrue(business_schema.validate_integrity(f.office))

    def test_transport_metadata_is_exact_for_both_historical_v2_and_v3(self):
        f=transport.TravelTransportTests('runTest');f.setUp()
        leg=f.segment('2026-02-02T09:00:00+01:00','2026-02-02T10:00:00+01:00',f.be,'flight','transit')
        stay=f.segment(leg['to'],'2026-02-02T20:00:00+01:00',f.be)
        trip=basic.trip(901,leg['from'],stay['to'],f.be,f.home,requested=4000)
        trip['details'].update(segments=[leg,stay],transport_facts=[f.flight([(leg,f.de,f.be)])])
        for version in ('de_travel_2026_v2','de_travel_2026_v3'):
            with self.subTest(version=version):
                current=calculate([trip],f.places,rule_version=version)
                original=self.windows_calculate([trip],f.places,rule_version=version)
                self.assertTrue(current['can_approve']);self.assertNotEqual(current,original)
                self.assertTrue(calculation_matches(current,original,trips=[trip],sites=f.places))
                changed=json.loads(canonical(original));changed['transport_sources'][0]['facts_hash']='0'*64
                self.assertFalse(calculation_matches(current,changed,trips=[trip],sites=f.places))

    def test_crlf_runtime_reproduces_unchanged_lf_ground_and_mixed_original(self):
        _,_,receipt=self.original();record=receipt['result'];lf=self.recompute(record)
        code=('import sys,json;sys.path.insert(0,sys.argv[1]);from payroll_travel_2026 import calculate;'
            'from travel_provenance_compat import calculation_matches;d=json.load(sys.stdin);r=d["record"];'
            's=r["sources"];p=r["details"];actual=calculate(s["trips"],s["sites"],history_trips=s["history_trips"],'
            'settlement_unit=p["settlement_unit"],tax_choice=p["tax_choice"],requested_meal_minor=p["requested_meal_minor"],'
            'requested_lodging_minor=p["requested_lodging_minor"],rule_version=r["calculation"]["rule_version"]);'
            'print(json.dumps(calculation_matches(actual,d["lf"],trips=s["trips"],sites=s["sites"])))')
        result=subprocess.run([sys.executable,'-I','-B','-c',code,str(self.root)],text=True,
            input=json.dumps(dict(record=record,lf=lf)),capture_output=True,check=True,timeout=30,
            cwd=self.root,env={'PATH':os.environ.get('PATH',''),'LANG':'C.UTF-8'})
        self.assertIs(json.loads(result.stdout),True)

    def test_crlf_original_reaches_euer_and_bank_only_through_actual_payments(self):
        f=finance.TravelFinanceTests('runTest');self.addCleanup(f.doCleanups)
        with patch('business_travel_allowances.calculate',side_effect=self.windows_calculate):
            f.setUp()
        self.assertNotEqual(f.settlement['calculation']['rule_hash'],self.recompute(f.settlement)['rule_hash'])
        f.test_two_actual_partial_payments_have_exact_expense_and_bank_evidence()

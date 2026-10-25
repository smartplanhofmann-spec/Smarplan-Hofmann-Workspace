"""Actual official KoSIT acceptance; intentionally no success-shaped fake."""
from pathlib import Path
import os
import unittest
import xml.etree.ElementTree as ET

from core import Problem
import business_einvoice as einvoice
from test_documents import DocumentsFixture


class ElectronicInvoiceTests(DocumentsFixture,unittest.TestCase):
    def snapshot(self,kind='invoice'):
        self.settings();draft=self.draft(kind=kind)
        return self.api.prepare_finalization(self.owner,draft['id'],1)['snapshot']

    def test_generated_ubl_is_accepted_by_actual_official_kosit(self):
        xml=einvoice.build_xrechnung(self.snapshot())
        self.assertTrue(einvoice.validate_xrechnung(xml)['accepted'])
        facts=einvoice.inspect_invoice(xml)
        self.assertEqual('EUR',facts['currency']);self.assertEqual('needs_review',facts['status'])

    def test_official_validator_rejects_wrong_totals_even_with_zero_process_exit(self):
        xml=einvoice.build_xrechnung(self.snapshot())
        root=ET.fromstring(xml);node=root.find('.//{'+einvoice.CAC+'}LegalMonetaryTotal/{'+einvoice.CBC+'}PayableAmount');node.text='9999.99'
        with self.assertRaises(Problem) as error:einvoice.validate_xrechnung(ET.tostring(root,encoding='utf-8',xml_declaration=True))
        self.assertEqual(409,error.exception.status)

    def test_dtd_entity_utf16_and_unsupported_profiles_are_fail_closed(self):
        for value in (b'<!DOCTYPE x [<!ENTITY z SYSTEM "file:///etc/passwd">]><x>&z;</x>',b'\xff\xfe<\x00x\x00/\x00>\x00'):
            with self.assertRaises(Problem):einvoice.secure_xml(value)
        self.assertIn('EN16931',einvoice.capabilities()['zugferd']);self.assertEqual('only_verified_zugferd_artifact',einvoice.capabilities()['pdfa'])

    def test_missing_official_validator_does_not_claim_conformance(self):
        from unittest.mock import patch
        with patch.dict(os.environ,{'SMARTPLAN_KOSIT_JAR':'/nonexistent/validator.jar'}):
            with self.assertRaises(Problem):einvoice.validate_xrechnung(einvoice.build_xrechnung(self.snapshot()))

    def test_real_zugferd_en16931_embedded_xml_and_pdfa3_validator(self):
        from business_documents import render_pdf
        snapshot=self.snapshot();pdf,xml,result=einvoice.build_zugferd(snapshot,render_pdf(snapshot))
        self.assertTrue(result['accepted']);self.assertTrue(result['pdfa']['accepted']);self.assertEqual('PDF/A-3B',result['pdfa']['profile'])
        self.assertEqual('cii',einvoice.inspect_invoice(xml)['format']);self.assertTrue(pdf.startswith(b'%PDF-'))

    def test_ordinary_pdf_is_not_falsely_declared_pdfa3(self):
        from business_documents import render_pdf
        with self.assertRaises(Problem) as error:einvoice.validate_pdfa3(render_pdf(self.snapshot()))
        self.assertEqual(409,error.exception.status)

    def test_real_mustang_rejects_invalid_zugferd_monetary_totals(self):
        from business_documents import render_pdf
        snapshot=self.snapshot();snapshot['totals']['gross']='9999.99'
        with self.assertRaises(Problem) as error:einvoice.build_zugferd(snapshot,render_pdf(snapshot))
        self.assertEqual(409,error.exception.status)

    def test_cumulative_reference_allowances_are_valid_in_both_real_einvoice_formats(self):
        from business_documents import render_pdf
        self.settings()
        def positions(value):return [dict(description='Synthetic cumulative work',quantity='1',unit='HUR',unit_price_net=value,tax_rate='19',kind='labor')]
        advance=self.issue(self.draft(kind='advance_invoice',positions=positions('100')))
        final=self.draft(kind='final_invoice',positions=positions('300'),previous_document_ids=[advance['id']])
        snapshot=self.api.prepare_finalization(self.owner,final['id'],1)['snapshot']
        self.assertTrue(einvoice.validate_xrechnung(einvoice.build_xrechnung(snapshot))['accepted'])
        self.assertTrue(einvoice.build_zugferd(snapshot,render_pdf(snapshot))[2]['pdfa']['accepted'])
        self.assertEqual('238.00',snapshot['totals']['gross'])

    def test_credit_note_has_original_number_and_passes_both_real_validators(self):
        from business_documents import render_pdf
        import uuid
        self.settings();invoice=self.issue(self.draft(kind='invoice'))
        credit=self.call('cancel',invoice['id'],dict(request_id=uuid.uuid4().hex,revision=invoice['revision'],reason='Synthetic correction'))
        snapshot=self.api.prepare_finalization(self.owner,credit['id'],1)['snapshot']
        self.assertEqual(invoice['number'],snapshot['cancelled_number'])
        self.assertTrue(einvoice.validate_xrechnung(einvoice.build_xrechnung(snapshot))['accepted'])
        self.assertTrue(einvoice.build_zugferd(snapshot,render_pdf(snapshot))[2]['accepted'])

    def test_second_exact_price_basis_survives_both_real_formats(self):
        from business_documents import calculate_positions,render_pdf
        snapshot=self.snapshot();snapshot.update(calculate_positions([dict(description='Seven seconds at stated hourly rate',quantity='7',unit='SEC',unit_price_net='10000.00',price_base_quantity='3600',tax_rate='19',kind='labor')]))
        self.assertEqual('19.44',snapshot['totals']['net'])
        self.assertTrue(einvoice.validate_xrechnung(einvoice.build_xrechnung(snapshot))['accepted'])
        self.assertTrue(einvoice.build_zugferd(snapshot,render_pdf(snapshot))[2]['accepted'])


if __name__=='__main__':unittest.main()

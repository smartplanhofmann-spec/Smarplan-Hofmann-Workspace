"""The client regression DTOs/PDFs must remain exact projections of real runs."""
import importlib.util
import json
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
GENERATOR=ROOT/'app/test/fixtures/generate_payroll_statement_composites.py'
SPEC=importlib.util.spec_from_file_location('statement_composite_fixture_generator',GENERATOR)
generator=importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(generator)


class CompositeStatementOriginals(unittest.TestCase):
    def test_all_recorded_dtos_and_pdf_bytes_are_actual_unchanged_production_projections(self):
        saved=json.loads(GENERATOR.with_name('payroll_statement_composites.json').read_text())
        self.assertEqual(generator.generate(),saved)
        self.assertEqual(len(saved['cases']),11)
        for row in saved['cases']:
            self.assertEqual(row['statement']['schema_version'],2)


if __name__=='__main__':unittest.main()

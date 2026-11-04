"""Independent populated catalog + opening restore across the shared release."""
import base64
import unittest

import business_schema
import business_catalog_imports as catalog
from business_accounting_openings import OpeningBalances
from business_adapters import Adapters
from core import Problem
from online import release, test_business_accounting_openings_pg as opening
from online.store import PostgresOffice
from online.test_postgres_accounting_components_integration import disposable_restore, evidence_for, approve


@unittest.skipUnless(opening.fixture.DSN, 'Disposable loopback PostgreSQL required')
class CatalogAndOpeningRestore(unittest.TestCase):
    def test_actual_catalog_original_acceptance_and_opening_survive_dump_restore(self):
        f = opening.OpeningBalancesPostgres('runTest')
        f.setUp()
        self.addCleanup(f.doCleanups)
        original, _, _ = f.original()
        opening_command = f.command(original)
        opening_receipt = f.call('POST', opening.BASE + '/confirm', opening_command, status=201).json
        adapter = f.call('POST', '/business/adapters', opening.req(
            name='Synthetic restored supplier catalog', profile='catalog_csv_v1', enabled=True), status=201).json
        raw = 'code;name;unit;cost_price_net;unit_price_net;tax_rate\nRESTORE;Prüfartikel;ST;10;15;19\n'.encode()
        import_command = opening.req(filename='synthetic-restore.csv', content_base64=base64.b64encode(raw).decode())
        staged = f.call('POST', '/business/adapters/' + adapter['id'] + '/import', import_command, status=201).json
        apply_command = opening.req(confirmed=True)
        accepted = f.call('POST', '/business/adapters/imports/' + staged['id'] + '/apply', apply_command).json
        source = release.snapshot_fingerprint(opening.fixture.DSN)
        f.office.db.close()
        with disposable_restore(f.runtime) as (target, runtime, report):
            restored = PostgresOffice(runtime)
            try:
                self.assertTrue(business_schema.validate_integrity(restored))
                api = catalog.CatalogImports(restored)
                self.assertEqual(api.detail(f.actor, staged['id']), accepted)
                self.assertEqual(api.original(f.actor, staged['id'])[0], raw)
                self.assertEqual(OpeningBalances(restored).state(f.actor)['items'], [opening_receipt])
                # Existing catalog V1 replay is a read of the accepted result,
                # with no cash, journal or numbering effect. The independent
                # financial reconciliation gate applies to Opening commands.
                before_replay = release.snapshot_fingerprint(target)
                self.assertEqual(Adapters(restored).apply_catalog(f.actor, staged['id'], apply_command), accepted)
                self.assertEqual(release.snapshot_fingerprint(target), before_replay)
                with self.assertRaises(Problem):
                    OpeningBalances(restored).confirm(f.actor, opening_command)
                evidence = evidence_for(restored, report)
                self.assertEqual(evidence['schema'], 16)
            finally:
                restored.db.close()
            operator = PostgresOffice(target)
            try:
                self.assertTrue(approve(operator, evidence)['reconciled'])
            finally:
                operator.db.close()
            restored = PostgresOffice(runtime)
            try:
                api = catalog.CatalogImports(restored)
                self.assertEqual(api.original(f.actor, staged['id'])[0], raw)
                self.assertEqual(Adapters(restored).apply_catalog(f.actor, staged['id'], apply_command), accepted)
                self.assertEqual(Adapters(restored).import_data(f.actor, adapter['id'], import_command), accepted)
                self.assertEqual(OpeningBalances(restored).confirm(f.actor, opening_command), opening_receipt)
                current = release.snapshot_fingerprint(target)
                for table in catalog.TABLES + ('business_articles', 'business_adapter_runs', 'business_adapter_requests'):
                    self.assertEqual(current[table], source[table], table)
                self.assertTrue(business_schema.validate_integrity(restored))
            finally:
                restored.db.close()


if __name__ == '__main__':
    unittest.main()

"""Synthetic adapter contracts; no provider network or real credentials."""
import base64
from decimal import Decimal
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import uuid

from core import Office, Problem
from business_foundation import ensure_sqlite_schema as ensure_foundation
from business_adapters import Adapters, ensure_sqlite_schema, parse_catalog, inspect_gaeb, validate_integrity


def request(**data):
    return {'request_id': uuid.uuid4().hex, **data}


class AdapterTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='synthetic-adapters-')
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'office.db'
        self.office = Office(self.path)
        self.addCleanup(lambda: self.office.db.close())
        ensure_foundation(self.office)
        ensure_sqlite_schema(self.office)
        self.owner = {'id': self.office.add_user('owner@example.test', 'Synthetic-password-123', 'owner'),
                      'email': 'owner@example.test', 'role': 'owner'}
        self.now = [1000.0]
        self.secret = 'SPLD_' + 'x' * 43
        self.api = Adapters(self.office, environ={'SMARTPLAN_WEBSITE_LEAD_SECRET': self.secret},
                            feature=lambda name: True, clock=lambda: self.now[0])

    def problem(self, status, fn):
        with self.assertRaises(Problem) as failure:
            fn()
        self.assertEqual(failure.exception.status, status)

    def configure(self, profile='website_lead_v1', **extra):
        return self.api.save(self.owner, request(name='Synthetic adapter', profile=profile, enabled=True,
            **({'secret_ref': 'SMARTPLAN_WEBSITE_LEAD_SECRET'} if profile == 'website_lead_v1' else {}), **extra))

    def envelope(self, **extra):
        return {'external_id': 'synthetic-website-17', 'subject': 'Synthetic callback',
                'message': 'Synthetic inquiry, no acceptance or order', 'sender_name': 'Synthetic sender',
                'sender_email': 'sender@example.test', 'sender_phone': '+49 000 1234567', **extra}

    def test_dedicated_website_intake_creates_real_inquiry_once_without_modifying_gmail_contract(self):
        adapter = self.configure()
        receipt = self.api.receive_lead(adapter['id'], self.secret, self.envelope())
        self.assertEqual(set(receipt), {'id', 'status'})
        self.assertEqual(receipt['status'], 'received')
        self.assertEqual(self.api.receive_lead(adapter['id'], self.secret, self.envelope()), receipt)
        row = self.office.db.execute('SELECT * FROM inquiries WHERE id=?', (receipt['id'],)).fetchone()
        self.assertEqual((row['source'], row['source_account'], row['status']), ('import', 'lead:' + adapter['id'], 'new'))
        self.assertIsNone(row['customer_id'])
        self.assertIsNone(row['project_id'])
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM customers').fetchone()[0], 0)
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM business_leads').fetchone()[0], 1)
        self.assertTrue(validate_integrity(self.office))
        self.assertEqual(self.api.receive_lead(adapter['id'], self.secret, dict(reversed(list(self.envelope().items())))), receipt)

    def test_wrong_or_unconfigured_credentials_and_disabled_feature_never_write_leads(self):
        adapter = self.configure()
        for token in ('123456', 'SPIN_' + 'x' * 43, self.secret + 'wrong'):
            self.problem(401, lambda: self.api.receive_lead(adapter['id'], token, self.envelope()))
        blocked = Adapters(self.office, environ={}, feature=lambda name: True)
        self.problem(409, lambda: blocked.receive_lead(adapter['id'], self.secret, self.envelope()))
        disabled = Adapters(self.office, environ={'SMARTPLAN_WEBSITE_LEAD_SECRET': self.secret}, feature=lambda name: False)
        self.problem(409, lambda: disabled.receive_lead(adapter['id'], self.secret, self.envelope()))
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM inquiries').fetchone()[0], 0)

    def test_lead_retries_survive_reopen_and_mutated_external_id_conflicts(self):
        adapter = self.configure()
        first = self.api.receive_lead(adapter['id'], self.secret, self.envelope())
        self.now[0] += 3600
        self.office.db.close()
        self.office = Office(self.path)
        self.api = Adapters(self.office, environ={'SMARTPLAN_WEBSITE_LEAD_SECRET': self.secret}, feature=lambda name: True)
        self.assertEqual(self.api.receive_lead(adapter['id'], self.secret, self.envelope()), first)
        self.problem(409, lambda: self.api.receive_lead(adapter['id'], self.secret, self.envelope(message='Changed immutable inquiry')))

    def test_live_secret_values_and_unsupported_provider_enablement_are_rejected(self):
        self.problem(400, lambda: self.api.save(self.owner, request(name='Unsafe', profile='website_lead_v1',
            enabled=True, secret_ref=self.secret)))
        self.problem(400, lambda: self.api.save(self.owner, request(name='Unsafe', profile='website_lead_v1',
            enabled=True, api_token=self.secret)))
        self.problem(409, lambda: self.configure('aroundhome_partner'))
        listed = self.api.list(self.owner)
        self.assertNotIn(self.secret, str(listed))

    def test_only_requested_wholesalers_are_named_without_inventing_verified_partner_access(self):
        suppliers = self.api.list(self.owner)['suppliers']
        self.assertEqual([s['name'] for s in suppliers], ['Granzow', 'Alexander Bürkle'])
        self.assertTrue(all(s['live_access'] is False and s['verified_protocols'] == [] for s in suppliers))
        adapter = self.configure('catalog_csv_v1', supplier='granzow')
        self.assertEqual(adapter['supplier_info']['name'], 'Granzow')
        self.problem(409, lambda: self.api.save(self.owner, request(revision=1, supplier='alexander_buerkle'), adapter['id']))
        self.problem(400, lambda: self.configure('catalog_csv_v1', supplier='invented-other-vendor'))
        self.assertTrue(validate_integrity(self.office))

    def test_website_rate_and_inactive_source_owner_are_checked_fresh(self):
        adapter = self.configure()
        for _ in range(30):
            self.api.receive_lead(adapter['id'], self.secret, self.envelope())
        self.problem(429, lambda: self.api.receive_lead(adapter['id'], self.secret, self.envelope()))
        self.now[0] += 60
        self.api.receive_lead(adapter['id'], self.secret, self.envelope())
        with self.office.db:
            self.office.db.execute("UPDATE users SET role='manager' WHERE id=?", (self.owner['id'],))
        self.problem(401, lambda: self.api.receive_lead(adapter['id'], self.secret, self.envelope()))

    def test_late_lead_failure_rolls_back_inquiry_receipt_and_provenance_together(self):
        from inquiries import Inquiries
        adapter = self.configure()
        original = Inquiries._create
        def fail(instance, actor, data, **kwargs):
            original(instance, actor, data, **kwargs)
            raise RuntimeError('Synthetic interrupted lead publication')
        with patch.object(Inquiries, '_create', new=fail):
            with self.assertRaises(RuntimeError):
                self.api.receive_lead(adapter['id'], self.secret, self.envelope())
        for table in ('inquiries', 'inquiry_requests', 'business_leads'):
            self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM ' + table).fetchone()[0], 0)
        self.api.receive_lead(adapter['id'], self.secret, self.envelope())

    def test_datanorm_a14_cp850_preserves_price_basis_without_inventing_vat_or_unsupported_records(self):
        raw = 'A;N;ART-17;;Überwurf;synthetisch;2;1;ST;12345;;;;\r\n'.encode('cp850')
        items = parse_catalog('datanorm_a14_cp850_v1', raw)
        self.assertEqual(items[0]['code'], 'ART-17')
        self.assertEqual(items[0]['name'], 'Überwurf synthetisch')
        self.assertEqual(items[0]['source_price_integer'], '12345')
        self.assertEqual(items[0]['price_basis'], '10')
        self.assertNotIn('tax_rate', items[0])
        self.problem(415, lambda: parse_catalog('datanorm_a14_cp850_v1', b'R;N;unsupported-discount\r\n'))
        self.problem(400, lambda: parse_catalog('datanorm_a14_cp850_v1', b'A;N;broken'))

    def test_catalog_csv_stages_real_rows_with_immutable_hash_and_lost_ack_retry(self):
        adapter = self.configure('catalog_csv_v1')
        raw = b'code;name;unit;cost_price_net;unit_price_net;tax_rate\nART17;Synthetic valve;ST;12.50;20.00;19\n'
        body = request(content_base64=base64.b64encode(raw).decode())
        staged = self.api.import_data(self.owner, adapter['id'], body)
        self.assertEqual(staged['status'], 'staged')
        self.assertEqual(staged['rows'][0]['cost_price_net'], '12.50')
        self.assertEqual(self.api.import_data(self.owner, adapter['id'], body)['id'], staged['id'])
        self.assertNotIn('article_id', staged['rows'][0])
        self.problem(409, lambda: self.api.import_data(self.owner, adapter['id'], {**body, 'content_base64': base64.b64encode(raw + b'bad').decode()}))

    def test_modified_staged_position_payload_is_blocked_by_integrity_before_application(self):
        adapter = self.configure('catalog_csv_v1')
        raw = b'code;name;unit;cost_price_net;unit_price_net;tax_rate\nART17;Synthetic valve;ST;12.50;20.00;19\n'
        staged = self.api.import_data(self.owner, adapter['id'], request(content_base64=base64.b64encode(raw).decode()))
        changed = [{**staged['rows'][0], 'cost_price_net': '999.99'}]
        with self.office.db:
            self.office.db.execute('UPDATE business_adapter_runs SET rows_json=? WHERE id=?', (json.dumps(changed), staged['id']))
        self.problem(409, lambda: self.api.apply_catalog(self.owner, staged['id'], request(confirmed=True)))
        with self.assertRaises(ValueError):
            validate_integrity(self.office)

    def test_gaeb_inspection_rejects_entities_and_wrong_exchange_phase_without_claiming_schema_validation(self):
        xml = b'<GAEB xmlns="http://www.gaeb.de/GAEB_DA_XML/DA83/3.2"><Award><DP>83</DP><BoQ><BoQBody><Itemlist><Item ID="i17" RNoPart="001"><Qty>2.000</Qty><QU>ST</QU><Description><CompleteText><DetailTxt><Text>Line synthetic</Text></DetailTxt></CompleteText></Description></Item></Itemlist></BoQBody></BoQ></Award></GAEB>'
        result = inspect_gaeb(xml)
        self.assertEqual(result['phase'], '83')
        self.assertFalse(result['official_schema_validated'])
        self.assertEqual(result['items'][0]['quantity'], '2.000')
        self.problem(415, lambda: inspect_gaeb(xml.replace(b'DA83', b'DA84').replace(b'>83<', b'>84<')))
        self.problem(400, lambda: inspect_gaeb(b'<!DOCTYPE x [<!ENTITY y "boom">]><GAEB>&y;</GAEB>'))

    def test_negative_money_unknown_csv_headers_and_oversize_bytes_are_rejected(self):
        self.problem(400, lambda: parse_catalog('catalog_csv_v1', b'code;name;unit;cost_price_net;unit_price_net;tax_rate\nx;x;ST;-1;2;19\n'))
        self.problem(400, lambda: parse_catalog('catalog_csv_v1', b'code;name;unexpected\nx;x;secret\n'))
        self.problem(413, lambda: parse_catalog('catalog_csv_v1', b'x' * (2 * 1024 * 1024 + 1)))


from business_tests.test_documents import DocumentsFixture


class AdapterCommercialTests(DocumentsFixture, unittest.TestCase):
    def setUp(self):
        super().setUp()
        ensure_sqlite_schema(self.office)
        self.adapters = Adapters(self.office, feature=lambda name: True)

    def config(self, profile):
        return self.adapters.save(self.owner, request(name='Synthetic interchange ' + profile, profile=profile, enabled=True))

    def stage(self, adapter, raw):
        return self.adapters.import_data(self.owner, adapter['id'], request(content_base64=base64.b64encode(raw).decode()))

    def test_confirmed_csv_import_creates_real_articles_and_late_failure_rolls_everything_back(self):
        from business_documents import Documents
        adapter = self.config('catalog_csv_v1')
        raw = b'code;name;unit;cost_price_net;unit_price_net;tax_rate\nART17;Synthetic A;ST;10.00;20.00;19\nART18;Synthetic B;ST;11.00;21.00;19\n'
        staged = self.stage(adapter, raw)
        body = request(confirmed=True)
        save = Documents.save_article
        calls = []
        def fail(instance, actor, data, article_id=None):
            result = save(instance, actor, data, article_id)
            calls.append(result['id'])
            if len(calls) == 2:
                raise RuntimeError('Synthetic late article failure')
            return result
        with patch.object(Documents, 'save_article', new=fail):
            with self.assertRaises(RuntimeError):
                self.adapters.apply_catalog(self.owner, staged['id'], body)
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM business_articles').fetchone()[0], 0)
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM business_adapter_articles').fetchone()[0], 0)
        applied = self.adapters.apply_catalog(self.owner, staged['id'], body)
        self.assertEqual(applied['status'], 'applied')
        self.assertEqual(len(applied['result']['article_ids']), 2)
        self.assertEqual(self.adapters.apply_catalog(self.owner, staged['id'], body), applied)
        self.assertEqual(next(item for item in self.call('articles')['items'] if item['code'] == 'ART17')['cost_price_net'], '10.00')
        self.assertTrue(validate_integrity(self.office))

    def test_explicit_datanorm_price_role_preserves_the_other_previously_confirmed_price(self):
        adapter = self.config('datanorm_a14_cp850_v1')
        first = self.stage(adapter, b'A;N;ART-17;;Synthetic;valve;2;1;ST;12345;;;;\r\n')
        a = self.adapters.apply_catalog(self.owner, first['id'], request(confirmed=True, price_scale='0.01', target_price='sales_net', tax_rate='19'))
        second = self.stage(adapter, b'A;N;ART-17;;Synthetic;valve;2;1;ST;20000;;;;\r\n')
        b = self.adapters.apply_catalog(self.owner, second['id'], request(confirmed=True, price_scale='0.01', target_price='purchase_net', tax_rate='19'))
        self.assertEqual(a['result']['article_ids'], b['result']['article_ids'])
        article = self.call('articles')['items'][0]
        self.assertEqual((article['unit_price_net'], article['cost_price_net']), ('12.3450', '20.0000'))

    def test_manual_article_change_after_preview_prevents_silent_overwrite(self):
        adapter = self.config('catalog_csv_v1')
        raw = b'code;name;unit;cost_price_net;unit_price_net;tax_rate\nART17;Synthetic A;ST;10.00;20.00;19\n'
        first = self.stage(adapter, raw)
        self.adapters.apply_catalog(self.owner, first['id'], request(confirmed=True))
        second = self.stage(adapter, raw.replace(b'10.00', b'11.00'))
        article = self.call('articles')['items'][0]
        self.call('save_article', request(revision=article['revision'], unit_price_net='25.00'), article['id'])
        with self.assertRaises(Problem) as failure:
            self.adapters.apply_catalog(self.owner, second['id'], request(confirmed=True))
        self.assertEqual(failure.exception.status, 409)
        self.assertEqual(self.call('articles')['items'][0]['unit_price_net'], '25.00')

    def test_catalog_export_masks_formula_text_and_roundtrips_its_declared_escape_profile(self):
        adapter = self.config('catalog_csv_v1')
        article = self.call('save_article', request(code='+SKU17', name='=SYNTHETIC_FORMULA', kind='material', unit='ST',
            unit_price_net='12.00', cost_price_net='10.00', tax_rate='19', currency='EUR', active=True))
        exported = self.adapters.export_data(self.owner, adapter['id'], request())
        raw = base64.b64decode(exported['result']['artifact_base64'])
        self.assertIn(b"'=SYNTHETIC_FORMULA", raw)
        parsed = parse_catalog('catalog_csv_v1', raw)[0]
        self.assertEqual((parsed['code'], parsed['name']), (article['code'], article['name']))

    def test_gaeb_position_inspection_roundtrips_and_creates_a_real_explicitly_priced_offer(self):
        adapter = self.config('gaeb_x83_inspect_v1')
        raw = b'<GAEB xmlns="http://www.gaeb.de/GAEB_DA_XML/DA83/3.3"><Award><DP>83</DP><BoQ><BoQBody><Itemlist><Item ID="i17" RNoPart="001"><Qty>2.000</Qty><QU>ST</QU><Description><CompleteText><DetailTxt><Text>\n Line synthetic \n</Text></DetailTxt></CompleteText></Description></Item></Itemlist></BoQBody></BoQ></Award></GAEB>'
        staged = self.stage(adapter, raw)
        exported = self.adapters.export_data(self.owner, adapter['id'], request(import_id=staged['id']))
        self.assertEqual(inspect_gaeb(base64.b64decode(exported['result']['artifact_base64']))['items'], staged['rows'])
        body = request(confirmed=True, project_id=self.project, issue_date='2030-01-10', due_date='2030-01-24',
            buyer={'name': 'Synthetic Buyer', 'address_line': 'Synthetic Road 2', 'postal_code': '10117', 'city': 'Berlin', 'country': 'DE', 'email': 'buyer@example.test'},
            position_prices={'i17': '22.50'}, tax_rate='19')
        offer = self.adapters.create_offer_from_inspection(self.owner, staged['id'], body)
        self.assertEqual((offer['kind'], offer['status'], offer['totals']['net']), ('offer', 'draft', '45.00'))
        self.assertEqual(self.adapters.create_offer_from_inspection(self.owner, staged['id'], body)['id'], offer['id'])
        self.assertFalse(exported['result']['official_schema_validated'])

    def test_gaeb_alternative_reference_or_unknown_item_semantics_are_inspectable_but_never_summed_or_dropped_in_export(self):
        adapter = self.config('gaeb_x83_inspect_v1')
        simple = b'<GAEB xmlns="http://www.gaeb.de/GAEB_DA_XML/DA83/3.3"><Award><DP>83</DP><BoQ><BoQBody><Itemlist><Item ID="i17" RNoPart="001"><Qty>2.000</Qty><QU>ST</QU><Description><CompleteText><DetailTxt><Text>Synthetic alternative</Text></DetailTxt></CompleteText></Description></Item></Itemlist></BoQBody></BoQ></Award></GAEB>'
        documents_before = self.office.db.execute('SELECT COUNT(*) FROM business_documents').fetchone()[0]
        for marker in (b'<ALNGroupNo>1</ALNGroupNo>', b'<RefRNo>001</RefRNo>',
                       b'<UnrecognizedPriceRule>extra</UnrecognizedPriceRule>'):
            with self.subTest(marker=marker):
                staged = self.stage(adapter, simple.replace(b'</Item>', marker + b'</Item>'))
                self.assertFalse(staged['result']['simple_positions_supported'])
                self.assertTrue(staged['result']['unsupported_semantics'])
                body = request(confirmed=True, project_id=self.project, issue_date='2030-01-10', due_date='2030-01-24',
                    buyer={'name': 'Synthetic Buyer', 'address_line': 'Synthetic Road 2', 'postal_code': '10117', 'city': 'Berlin', 'country': 'DE', 'email': 'buyer@example.test'},
                    position_prices={'i17': '22.50'}, tax_rate='19')
                for operation in (lambda: self.adapters.create_offer_from_inspection(self.owner, staged['id'], body),
                                  lambda: self.adapters.export_data(self.owner, adapter['id'], request(import_id=staged['id']))):
                    with self.assertRaises(Problem) as failure:
                        operation()
                    self.assertEqual(failure.exception.status, 409)
                self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM business_documents').fetchone()[0], documents_before)
                self.assertEqual(self.office.db.execute("SELECT COUNT(*) FROM audit WHERE action='business.adapter.offer_created'").fetchone()[0], 0)
        for raw in (simple.replace(b' ID="i17"', b' Alternative="true" ID="i17"'),
                    simple.replace(b'</Itemlist>', b'</Itemlist><AlternativeGroup>1</AlternativeGroup>')):
            inspected = inspect_gaeb(raw)
            self.assertFalse(inspected['simple_positions_supported'])
            self.assertTrue(inspected['unsupported_semantics'])
        self.assertTrue(inspect_gaeb(simple)['simple_positions_supported'])
        self.assertTrue(validate_integrity(self.office))

    def test_final_invoice_tax_groups_map_exactly_without_claiming_datev_native_import(self):
        self.settings()
        invoice = self.issue(self.draft(kind='invoice'))
        adapter = self.config('datev_review_csv_v1')
        body = request(document_ids=[invoice['id']], mapping={invoice['id']: {
            'account': '10001', 'contra_account': '8400', 'tax_keys': {'19': '3', '7': '2'}}})
        exported = self.adapters.export_data(self.owner, adapter['id'], body)
        self.assertEqual(self.adapters.export_data(self.owner, adapter['id'], body), exported)
        self.assertEqual(sum(Decimal(row['amount_gross']) for row in exported['rows']), Decimal(invoice['totals']['gross']))
        self.assertEqual(len(exported['rows']), 2)
        self.assertFalse(exported['result']['native_import_approved'])
        self.assertTrue(exported['result']['review_required'])
        raw = base64.b64decode(exported['result']['artifact_base64'])
        self.assertIn(invoice['number'].encode(), raw)
        self.assertEqual(self.call('get', invoice['id'])['payload_sha256'], invoice['payload_sha256'])

    def test_lexware_mapping_preserves_snapshot_and_replay_never_bypasses_revoked_project_scope(self):
        self.settings()
        invoice = self.issue(self.draft(kind='invoice'))
        adapter = self.config('lexware_review_json_v1')
        actor = {'id': uuid.uuid4().hex, 'email': 'synthetic-accountant@example.test', 'role': 'accountant'}
        with self.office.db:
            self.office.db.execute('INSERT INTO users(id,email,role,active) VALUES(?,?,?,1)', (actor['id'], actor['email'], actor['role']))
        self.office.assign(self.owner, self.project, actor['id'])
        body = request(document_ids=[invoice['id']], mapping={invoice['id']: {'remote_contact_id': 'synthetic-remote-17'}})
        exported = self.adapters.export_data(actor, adapter['id'], body)
        payload = json.loads(base64.b64decode(exported['result']['artifact_base64']))
        self.assertFalse(payload['native_api_payload'])
        self.assertFalse(payload['live_synchronized'])
        self.assertEqual(payload['documents'][0]['totals'], invoice['totals'])
        self.office.assign(self.owner, self.project, actor['id'], remove=True)
        with self.assertRaises(Problem) as failure:
            self.adapters.export_data(actor, adapter['id'], body)
        self.assertIn(failure.exception.status, (403, 404))


class ContactFormTests(unittest.TestCase):
    setUp = AdapterTests.setUp
    configure = AdapterTests.configure
    problem = AdapterTests.problem

    def setup_form(self):
        adapter = self.configure()
        self.api.environ.update(SMARTPLAN_CONTACT_ADAPTER_ID=adapter['id'],
            SMARTPLAN_CONTACT_ALLOWED_ORIGINS='https://office.example.test', SMARTPLAN_SMTP_FROM='reply@example.test')
        self.api.approve_reply_template(self.owner, adapter['id'], request(revision=0, approved=True, enabled=True,
            subject='Ihre Anfrage', text='Guten Tag {sender_name}, wir melden uns zur Klärung. Dies ist keine Auftragsbestätigung.'))
        return adapter

    def body(self, **extra):
        return request(subject='Synthetic website inquiry', message='Synthetic callback, no order.', sender_name='Synthetic customer',
                       sender_email='form-customer@example.test', sender_phone='', website='', privacy_notice_version='synthetic-v1', **extra)

    def test_public_form_creates_one_real_inquiry_and_one_pending_reply_without_browser_secret(self):
        self.setup_form()
        body = self.body()
        first = self.api.receive_form('https://office.example.test', '127.0.0.1', body)
        self.assertEqual(first['status'], 'received')
        self.assertEqual(first['reply_status'], 'pending')
        self.assertFalse(first['accepted_by_server'])
        self.assertNotIn(self.secret, str(first))
        self.assertEqual(self.api.receive_form('https://office.example.test', '127.0.0.1', body)['id'], first['id'])
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM inquiries').fetchone()[0], 1)
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM business_lead_reply_outbox').fetchone()[0], 1)
        self.assertEqual(self.api.public_form_receipt(first['id']), {'id': first['id'], 'status': 'pending'})

    def test_origin_honeypot_and_disabled_source_block_before_business_writes(self):
        self.setup_form()
        self.problem(403, lambda: self.api.receive_form('https://unrelated.example.test', '127.0.0.1', self.body()))
        malicious = self.body()
        malicious['website'] = 'https://synthetic-spam.example.test'
        self.problem(400, lambda: self.api.receive_form('https://office.example.test', '127.0.0.1', malicious))
        self.api.feature = lambda name: name != 'external.website_form'
        self.problem(409, lambda: self.api.receive_form('https://office.example.test', '127.0.0.1', self.body()))
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM inquiries').fetchone()[0], 0)

    def test_form_rate_uses_private_ip_hmac_and_resets_without_silent_duplicates(self):
        self.setup_form()
        for _ in range(5):
            self.api.receive_form('https://office.example.test', '127.0.0.1', self.body())
        self.problem(429, lambda: self.api.receive_form('https://office.example.test', '127.0.0.1', self.body()))
        self.assertNotIn('127.0.0.1', str([dict(row) for row in self.office.db.execute('SELECT * FROM business_contact_form_limits')]))
        self.now[0] += 600
        self.api.receive_form('https://office.example.test', '127.0.0.1', self.body())
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM inquiries').fetchone()[0], 6)

    def test_approved_response_is_accepted_only_after_actual_transport_ack_and_never_sent_twice(self):
        from business_delivery import DeliveryReceipt
        self.setup_form()
        self.api.receive_form('https://office.example.test', '127.0.0.1', self.body())
        outbox = self.office.db.execute('SELECT id FROM business_lead_reply_outbox').fetchone()[0]
        calls = []
        owner = self
        class Transport:
            def send(self, job):
                owner.assertFalse(owner.office.db.in_transaction)
                owner.assertFalse(owner.office.lock._is_owned())
                calls.append(job)
                return DeliveryReceipt('accepted', job['operation_id'], receipt_id='synthetic-smtp-ack', accepted_by_server=True)
        state = self.api.deliver_reply(self.owner, outbox, request(), transport=Transport())
        self.assertTrue(state['accepted_by_server'])
        self.assertFalse(state['recipient_delivery_confirmed'])
        self.assertEqual(self.api.deliver_reply(self.owner, outbox, request(), transport=Transport())['status'], 'accepted')
        self.assertEqual(len(calls), 1)

    def test_unknown_smtp_outcome_blocks_replay_even_with_another_request_id(self):
        from business_delivery import DeliveryReceipt
        self.setup_form()
        self.api.receive_form('https://office.example.test', '127.0.0.1', self.body())
        outbox = self.office.db.execute('SELECT id FROM business_lead_reply_outbox').fetchone()[0]
        calls = []
        class Transport:
            def send(self, job):
                calls.append(job)
                return DeliveryReceipt('unknown', job['operation_id'], error_code='delivery_unconfirmed')
        self.assertEqual(self.api.deliver_reply(self.owner, outbox, request(), transport=Transport())['status'], 'unknown')
        self.assertEqual(self.api.deliver_reply(self.owner, outbox, request(), transport=Transport())['status'], 'unknown')
        self.assertEqual(len(calls), 1)

    def test_template_variables_are_bounded_and_missing_approval_or_disabled_reply_never_sends(self):
        adapter = self.setup_form()
        self.problem(400, lambda: self.api.approve_reply_template(self.owner, adapter['id'], request(revision=1,
            subject='Unsafe', text='{sender_name.__class__}', approved=True, enabled=True)))
        self.api.feature = lambda name: name != 'external.lead_autoreply'
        receipt = self.api.receive_form('https://office.example.test', '127.0.0.1', self.body())
        self.assertEqual(receipt['reply_status'], 'disabled')
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM business_lead_reply_outbox').fetchone()[0], 0)

    def test_worker_is_explicitly_disabled_by_default_and_processes_one_reply_once_after_flag(self):
        from business_adapters import deliver_pending_replies
        from business_delivery import DeliveryReceipt
        from business_schema import set_feature_flag
        self.setup_form()
        self.api.receive_form('https://office.example.test', '127.0.0.1', self.body())
        calls = []
        class Transport:
            def send(self, job):
                calls.append(job)
                return DeliveryReceipt('accepted', job['operation_id'], receipt_id='synthetic-worker-ack', accepted_by_server=True)
        self.assertFalse(deliver_pending_replies(self.office, transport=Transport())['enabled'])
        self.assertEqual(calls, [])
        set_feature_flag(self.office, self.owner, 'external.lead_autoreply', True)
        self.assertEqual(deliver_pending_replies(self.office, transport=Transport())['accepted'], 1)
        self.assertEqual(deliver_pending_replies(self.office, transport=Transport())['processed'], 0)
        self.assertEqual(len(calls), 1)

    def test_a_status_word_without_valid_smtp_ack_does_not_claim_acceptance(self):
        from business_delivery import DeliveryReceipt
        self.setup_form()
        self.api.receive_form('https://office.example.test', '127.0.0.1', self.body())
        outbox = self.office.db.execute('SELECT id FROM business_lead_reply_outbox').fetchone()[0]
        class Transport:
            def send(self, job):
                return DeliveryReceipt('accepted', job['operation_id'])
        state = self.api.deliver_reply(self.owner, outbox, request(), transport=Transport())
        self.assertEqual(state['status'], 'unknown')
        self.assertFalse(state['accepted_by_server'])

    def test_delivery_outcome_is_retained_but_not_published_after_owner_revocation_during_io(self):
        from business_delivery import DeliveryReceipt
        self.setup_form()
        self.api.receive_form('https://office.example.test', '127.0.0.1', self.body())
        outbox = self.office.db.execute('SELECT id FROM business_lead_reply_outbox').fetchone()[0]
        office, actor = self.office, self.owner
        class Transport:
            def send(self, job):
                with office.db:
                    office.db.execute("UPDATE users SET role='technician' WHERE id=?", (actor['id'],))
                return DeliveryReceipt('accepted', job['operation_id'], receipt_id='synthetic-ack-after-revocation', accepted_by_server=True)
        self.problem(403, lambda: self.api.deliver_reply(self.owner, outbox, request(), transport=Transport()))
        self.assertEqual(self.office.db.execute('SELECT status FROM business_lead_reply_receipts ORDER BY ordinal DESC LIMIT 1').fetchone()[0], 'accepted')

    def test_disaster_restore_marks_pending_delivery_unknown_without_changing_jobs_or_resending(self):
        from business_adapters import sanitize_after_restore
        self.setup_form()
        self.api.receive_form('https://office.example.test', '127.0.0.1', self.body())
        outbox = dict(self.office.db.execute('SELECT * FROM business_lead_reply_outbox').fetchone())
        with self.office.db:
            sanitize_after_restore(self.office)
            sanitize_after_restore(self.office)
        self.assertEqual(dict(self.office.db.execute('SELECT * FROM business_lead_reply_outbox').fetchone()), outbox)
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM business_lead_reply_receipts').fetchone()[0], 2)
        self.assertEqual(self.api.public_form_receipt(outbox['inquiry_id']), {'id': outbox['inquiry_id'], 'status': 'unknown'})
        self.assertTrue(validate_integrity(self.office))


if __name__ == '__main__':
    unittest.main(verbosity=2)

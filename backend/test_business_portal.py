"""Synthetic real final offers, separate portal identity and transactional history.

Uses production Documents rendering/finalization for offers. No issuer-policy
override, provider, external identity service or live customer is involved.
"""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import sqlite3
import tempfile
import threading
import unittest
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit
import uuid

from core import Office, Problem
from business_documents import Documents, render_prepared
from business_foundation import BusinessFoundation
from business_operations import transaction
from business_portal import (Portal, STATEMENTS, count_attempt, dispatch, methods, runtime_features,
                             sanitize_after_restore, validate_integrity, protected_tables)
from business_schema import ensure_schema


class PortalTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='synthetic-portal-')
        self.addCleanup(temporary.cleanup)
        self.path = Path(temporary.name) / 'office.db'
        self.office = Office(self.path)
        self.addCleanup(self.office.db.close)
        self.office.portal_origin = 'https://portal.example.test'
        ensure_schema(self.office, activate=True)
        self.owner = self.actor('owner')
        self.tech = self.actor('technician')
        self.project = self.office.add_project(self.owner, 'Synthetic portal project', 'Synthetic customer A')
        self.other = self.office.add_project(self.owner, 'Other portal project', 'Synthetic customer B')
        self.customer = self.office.db.execute('SELECT customer_id FROM projects WHERE id=?', (self.project,)).fetchone()[0]
        self.office.assign(self.owner, self.project, self.tech['id'])
        self.stamp = datetime(2026, 11, 2, 12, tzinfo=timezone.utc)
        self.clock = lambda: self.stamp
        self.api = Portal(self.office, clock=self.clock)
        self.documents = Documents(self.office, clock=self.clock)
        self.documents.save_settings(self.owner, self.req(revision=0, company_name='Synthetic seller',
            address_line='Synthetic street 1', postal_code='10115', city='Berlin', country='DE',
            email='seller@example.test', phone='+4930123456', vat_id='DE123456789',
            payment_terms='Synthetic payment terms', footer='Synthetic footer'))
        self.article = self.documents.save_article(self.owner, self.req(name='Calculated material', code='CALC-M',
            unit='m', kind='material', cost_price_net='317.13', unit_price_net='400.00', tax_rate='19'))
        preview = self.documents.pricing_preview(self.owner, dict(base_cost_net='317.13', markup_percent='20', quantity='2',
            kind='material', unit='m', source_article_id=self.article['id'], source_article_revision=1))
        self.article = self.documents.save_article(self.owner, self.req(revision=1, pricing=preview['inputs'],
            pricing_hash=preview['preview_hash'], price_confirmation=True), self.article['id'])
        self.offer = self.final_offer()

    def actor(self, role):
        email = uuid.uuid4().hex + '@example.test'
        return dict(id=self.office.add_user(email, 'Synthetic-password-123', role), role=role, email=email)

    def req(self, **data):
        return dict(request_id=uuid.uuid4().hex, **data)

    def final_offer(self, project=None):
        draft = self.documents.create(self.owner, self.req(project_id=project or self.project, kind='offer',
            title='Synthetic offer', issue_date='2026-11-02', due_date='2026-11-16', intro='Synthetic introduction', notes='Synthetic conditions',
            buyer=dict(name='Synthetic buyer', address_line='Buyer street 2', postal_code='10117', city='Berlin',
                country='DE', email='buyer@example.test', contact_name='Synthetic recipient'),
            positions=[dict(article_id=self.article['id'], article_revision=self.article['revision'], quantity='2')]))
        prepared = self.documents.prepare_finalization(self.owner, draft['id'], draft['revision'])
        return self.documents.finalize(self.owner, draft['id'], render_prepared(prepared), uuid.uuid4().hex)

    def grant_body(self, offer=None, **changes):
        offer = offer or self.offer
        source = self.api.list_grants(self.owner, offer['id'])['source']
        return self.req(**{**dict(offer_id=offer['id'], source_revision=source['source_revision'],
            content_hash=source['content_hash'], pdf_hash=source['pdf_hash'], recipient_name='Synthetic recipient',
            recipient_email='recipient@example.test', expires_in_days=7, confirmation=True), **changes})

    def access(self, offer=None):
        created = self.api.create_grant(self.owner, self.grant_body(offer))
        key = parse_qs(urlsplit(created['portal_url']).fragment)['key'][0]
        session = self.api.open_session(created['grant']['id'], key)
        return created, key, session['token']

    def decision_body(self, token, **changes):
        offer = self.api.view(token)['offer']
        return self.req(**{**dict(content_hash=offer['content_hash'], pdf_hash=offer['pdf_hash'], decision='accepted',
            declared_name='Synthetic customer signer', statement_version=STATEMENTS['version'], confirmation=True), **changes})

    def adoption_body(self, decision, **changes):
        source = self.api.list_grants(self.owner, decision['offer_id'])['source']
        return self.req(**{**dict(decision_id=decision['id'], source_revision=source['source_revision'],
            content_hash=source['content_hash'], pdf_hash=source['pdf_hash'], confirmation=True), **changes})

    def permission(self, name, *, effect='allow', revision=0, scope=None):
        return BusinessFoundation(self.office).save_grant(self.owner, self.req(user_id=self.tech['id'], permission=name,
            scope=scope or self.project, effect=effect, revision=revision))

    def problem(self, status, function, *args):
        with self.assertRaises(Problem) as caught:
            function(*args)
        self.assertEqual(caught.exception.status, status, caught.exception.message)

    def snapshot(self, tables):
        return {table: sorted((tuple(row) for row in self.office.db.execute('SELECT * FROM ' + table)), key=repr) for table in tables}

    def test_real_final_offer_projection_pdf_and_separate_hash_only_identity(self):
        before = self.snapshot(('business_documents', 'business_document_archives', 'business_document_numbers', 'users', 'assignments', 'sessions'))
        created, key, token = self.access()
        viewed = self.api.view(token)
        offer = viewed['offer']
        self.assertEqual(set(offer), {'id','number','revision','content_hash','pdf_hash','title','issue_date','due_date','currency',
            'intro','notes','buyer','issuer','positions','totals'})
        self.assertEqual(set(offer['buyer']), {'name','contact_name','address_line','postal_code','city','country','email','vat_id'})
        self.assertEqual(set(offer['issuer']), {'company_name','address_line','postal_code','city','country','email','phone','website',
            'vat_id','tax_number','iban','bic','payment_terms','footer'})
        self.assertEqual(set(offer['positions'][0]), {'index','description','quantity','unit','unit_price_net','price_base_quantity',
            'discount_percent','tax_rate','tax_category','tax_exemption_reason','net'})
        self.assertEqual(set(offer['totals']), {'net','tax','gross','payable','labor_net','labor_tax','labor_gross',
            'material_net','material_tax','material_gross','tax_breakdown'})
        self.assertEqual(set(offer['totals']['tax_breakdown'][0]), {'rate','category','reason','net','tax'})
        self.assertEqual((offer['totals']['gross'], offer['positions'][0]['unit']), (self.offer['totals']['gross'], 'm'))
        self.assertTrue(viewed['actions_allowed'])
        self.assertIsNone(viewed['decision'])
        self.assertEqual(viewed['statements'], STATEMENTS)
        pdf, filename = self.api.pdf(token)
        self.assertEqual(pdf, self.documents.archive(self.owner, self.offer['id']))
        self.assertTrue(filename.startswith('Angebot-'))
        self.assertEqual(hashlib.sha256(pdf).hexdigest(), offer['pdf_hash'])
        self.assertIn('pricing_snapshot', json.dumps(self.offer))
        for hidden in ('cost_price_net', 'pricing_snapshot', 'source_article_id', 'issuer_mode', 'settings_revision', '317.13'):
            self.assertNotIn(hidden, json.dumps(viewed))
        self.assertEqual(before, self.snapshot(tuple(before)))
        tables = [row[0] for row in self.office.db.execute("SELECT name FROM sqlite_master WHERE type='table'")]
        persisted = repr(self.snapshot(tables))
        self.assertNotIn(key, persisted)
        self.assertNotIn(token, persisted)
        self.assertNotIn(created['portal_url'], persisted)
        self.assertEqual(self.office.db.execute('SELECT secret_hash FROM business_portal_grants').fetchone()[0], hashlib.sha256(key.encode()).hexdigest())
        self.assertTrue(validate_integrity(self.office))

    def test_grant_replay_never_recovers_secret_and_requires_explicit_replacement(self):
        body = self.grant_body()
        first = self.api.create_grant(self.owner, body)
        second = self.api.create_grant(self.owner, body)
        self.assertEqual(second, {'grant': first['grant'], 'link_available': False})
        ensure_schema(self.office)
        self.assertEqual(self.api.list_grants(self.owner, self.offer['id'])['items'][0]['status'], 'active')
        self.problem(409, self.api.create_grant, self.owner, {**body, 'recipient_name': 'Changed'})
        self.problem(409, self.api.create_grant, self.owner, self.grant_body())
        revoked = self.api.revoke_grant(self.owner, first['grant']['id'], self.req(reason='Synthetic replacement', confirmation=True))
        self.assertEqual(revoked['status'], 'revoked')
        replacement = self.api.create_grant(self.owner, self.grant_body())
        self.assertNotEqual(first['grant']['id'], replacement['grant']['id'])
        self.assertEqual(len(self.api.list_grants(self.owner, self.offer['id'])['items']), 2)

    def test_principal_and_token_prefix_boundaries_and_cross_company_access(self):
        created, key, token = self.access()
        grant_id = created['grant']['id']
        for invalid in ('', token, 'SPPI_' + 'x' * 42, 'SPPI_' + 'x' * 44, 'office-token', key + '\n'):
            self.problem(401, self.api.open_session, grant_id, invalid)
        for invalid in ('', key, token + '\n', 'office-token', 'SPPT_' + 'x' * 43):
            self.problem(401, self.api.view, invalid)
        self.problem(401, self.api.open_session, 'f' * 32, key)
        with tempfile.TemporaryDirectory() as temporary:
            other = Office(Path(temporary) / 'separate-company.db')
            try:
                other.portal_origin = self.office.portal_origin
                self.problem(401, Portal(other).open_session, grant_id, key)
                self.problem(401, Portal(other).view, token)
            finally:
                other.db.close()
        with self.office.db:
            self.office.db.execute('UPDATE business_portal_principals SET active=0,revision=revision+1 WHERE id=?',
                                   (created['grant']['principal']['id'],))
        self.problem(401, self.api.view, token)
        self.problem(401, self.api.open_session, grant_id, key)
        self.assertTrue(validate_integrity(self.office))

    def test_session_limit_logout_expiry_and_grant_expiry_cap(self):
        created, key, token = self.access()
        tokens = [token] + [self.api.open_session(created['grant']['id'], key)['token'] for _ in range(4)]
        self.problem(429, self.api.open_session, created['grant']['id'], key)
        self.assertEqual(self.api.logout(tokens[0]), {'logged_out': True})
        self.assertEqual(self.api.logout(tokens[0]), {'logged_out': True})
        self.problem(401, self.api.view, tokens[0])
        self.api.open_session(created['grant']['id'], key)
        self.stamp += timedelta(minutes=30)
        self.problem(401, self.api.view, tokens[1])
        self.api.open_session(created['grant']['id'], key)
        self.stamp = datetime.fromisoformat(created['grant']['expires_at']) - timedelta(minutes=5)
        final = self.api.open_session(created['grant']['id'], key)
        self.assertEqual(final['expires_at'], created['grant']['expires_at'])
        self.stamp += timedelta(minutes=5)
        self.problem(401, self.api.open_session, created['grant']['id'], key)
        self.problem(401, self.api.view, final['token'])
        self.assertEqual(self.api.list_grants(self.owner, self.offer['id'])['items'][0]['status'], 'expired')

    def test_revoke_and_customer_project_binding_are_fresh_without_invalidating_history(self):
        created, key, token = self.access()
        other_customer = self.office.db.execute('SELECT customer_id FROM projects WHERE id=?', (self.other,)).fetchone()[0]
        self.office.project_customer(self.owner, self.project, other_customer)
        self.problem(401, self.api.view, token)
        self.problem(401, self.api.open_session, created['grant']['id'], key)
        self.assertTrue(validate_integrity(self.office))
        self.office.project_customer(self.owner, self.project, self.customer)
        self.office.update_customer(self.owner, self.customer, {'active': False})
        self.problem(401, self.api.pdf, token)
        self.assertTrue(validate_integrity(self.office))
        self.office.update_customer(self.owner, self.customer, {'active': True})
        self.api.view(token)
        body = self.req(reason='Synthetic revocation', confirmation=True)
        revoked = self.api.revoke_grant(self.owner, created['grant']['id'], body)
        self.assertEqual(self.api.revoke_grant(self.owner, created['grant']['id'], body), revoked)
        self.problem(401, self.api.view, token)
        self.problem(401, self.api.open_session, created['grant']['id'], key)
        self.assertTrue(validate_integrity(self.office))

    def test_erased_customer_blocks_access_without_rewriting_old_grants(self):
        _, _, token = self.access()
        with self.office.db:
            self.office.db.execute("INSERT INTO business_contact_extras(customer_id,entity_type,kinds_json,tags_json,revision,erased_at,updated_by,updated_at) "
                "VALUES(?,'company','[]','[]',1,?,?,?) ON CONFLICT(customer_id) DO UPDATE SET erased_at=excluded.erased_at",
                (self.customer, self.api.now(), self.owner['id'], self.api.now()))
        self.problem(401, self.api.view, token)
        self.assertTrue(validate_integrity(self.office))

    def test_tampered_archive_hashes_block_access_and_integrity(self):
        _, _, token = self.access()
        with self.office.db:
            for row in self.office.db.execute("SELECT name FROM sqlite_master WHERE type='trigger' AND tbl_name='business_document_archives'").fetchall():
                self.office.db.execute('DROP TRIGGER ' + row['name'])
            self.office.db.execute('UPDATE business_document_archives SET pdf=? WHERE document_id=?', (b'%PDF-corrupt', self.offer['id']))
        self.problem(401, self.api.view, token)
        self.problem(401, self.api.pdf, token)
        with self.assertRaises(ValueError):
            validate_integrity(self.office)

    def test_content_hash_and_pdf_size_are_checked_before_publication(self):
        from business_documents import MAX_PDF
        with self.office.db:
            for row in self.office.db.execute("SELECT name FROM sqlite_master WHERE type='trigger' AND tbl_name='business_document_archives'").fetchall():
                self.office.db.execute('DROP TRIGGER ' + row['name'])
            archive = dict(self.office.db.execute('SELECT * FROM business_document_archives WHERE document_id=?', (self.offer['id'],)).fetchone())
            self.office.db.execute('UPDATE business_document_archives SET payload_json=? WHERE document_id=?',
                                   (archive['payload_json'] + ' ', self.offer['id']))
        self.problem(409, self.api._source, self.offer['id'])
        huge = b'%PDF-' + b'x' * MAX_PDF
        with self.office.db:
            self.office.db.execute('UPDATE business_document_archives SET payload_json=?,pdf=?,pdf_sha256=? WHERE document_id=?',
                (archive['payload_json'], huge, hashlib.sha256(huge).hexdigest(), self.offer['id']))
        self.problem(409, self.api._source, self.offer['id'])

    def test_grants_reject_drafts_nonoffers_and_recovered_financial_state(self):
        draft = self.documents.create(self.owner, self.req(project_id=self.project, kind='offer', issue_date='2026-11-02',
            buyer=dict(name='Synthetic buyer'), positions=[dict(description='Synthetic', quantity='1', unit='m', unit_price_net='1', tax_rate='19')]))
        self.problem(409, self.api.list_grants, self.owner, draft['id'])
        _, _, token = self.access()
        body = self.decision_body(token)
        with self.office.db:
            self.office.db.execute('INSERT INTO business_restore_state(singleton,pending,financial_reconciliation_required,restore_id) VALUES(1,0,1,?) '
                'ON CONFLICT(singleton) DO UPDATE SET financial_reconciliation_required=1,restore_id=excluded.restore_id', (uuid.uuid4().hex,))
        self.assertFalse(self.api.view(token)['actions_allowed'])
        self.problem(409, self.api.decide, token, body)

    def test_acceptance_replay_semantic_unique_decline_and_source_staleness(self):
        created, _, token = self.access()
        body = self.decision_body(token)
        self.problem(409, self.api.decide, token, {**body, 'pdf_hash': '0' * 64})
        self.problem(409, self.api.decide, token, {**body, 'content_hash': '0' * 64})
        first = self.api.decide(token, body)
        self.assertEqual(self.api.decide(token, body), first)
        self.assertEqual(first['statement_text'], STATEMENTS['accepted'])
        self.assertEqual(first['grant_id'], created['grant']['id'])
        self.assertFalse(self.api.view(token)['actions_allowed'])
        self.problem(409, self.api.decide, token, {**body, 'request_id': uuid.uuid4().hex})
        self.problem(409, self.api.decide, token, {**body, 'declared_name': 'Different signer'})
        self.problem(409, self.api.decide, token, {**body, 'decision': 'declined'})
        other = self.final_offer(self.other)
        _, _, other_token = self.access(other)
        declined = self.api.decide(other_token, self.decision_body(other_token, decision='declined'))
        self.assertEqual(declined['statement_text'], STATEMENTS['declined'])
        self.problem(409, self.api.adopt, self.owner, other['id'], self.adoption_body(declined))
        self.problem(409, self.api.decide, other_token, body)
        self.assertEqual(self.documents.get(self.owner, self.offer['id'])['status'], 'final')
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM business_portal_decisions').fetchone()[0], 2)
        self.assertEqual(self.office.db.execute("SELECT COUNT(*) FROM audit WHERE action LIKE 'business.portal.%'").fetchone()[0], 2)
        self.assertTrue(validate_integrity(self.office))

    def test_conflicting_decisions_from_two_connections_have_one_winner(self):
        created, key, token = self.access()
        second_token = self.api.open_session(created['grant']['id'], key)['token']
        second = Office(self.path)
        second.portal_origin = self.office.portal_origin
        barrier = threading.Barrier(2)
        bodies = [self.decision_body(token), self.decision_body(second_token, decision='declined')]
        def run(args):
            api, bearer, body = args
            barrier.wait(timeout=5)
            try:
                return api.decide(bearer, body)
            except Problem as error:
                return error.status
        try:
            with ThreadPoolExecutor(max_workers=2) as pool:
                outcomes = list(pool.map(run, ((self.api, token, bodies[0]), (Portal(second, clock=self.clock), second_token, bodies[1]))))
        finally:
            second.db.close()
        self.assertEqual(sum(isinstance(item, dict) for item in outcomes), 1)
        self.assertIn(409, outcomes)
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM business_portal_decisions').fetchone()[0], 1)
        self.assertTrue(validate_integrity(self.office))

    def test_decision_failure_rolls_back_then_revocation_blocks_same_request(self):
        created, _, token = self.access()
        body = self.decision_body(token)
        with self.office.db:
            self.office.db.execute("CREATE TRIGGER synthetic_decision_failure BEFORE INSERT ON business_portal_decision_requests "
                                   "BEGIN SELECT RAISE(ABORT,'synthetic receipt failure'); END")
        with self.assertRaises(sqlite3.IntegrityError):
            self.api.decide(token, body)
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM business_portal_decisions').fetchone()[0], 0)
        self.office.db.execute('DROP TRIGGER synthetic_decision_failure')
        self.api.decide(token, body)
        self.api.revoke_grant(self.owner, created['grant']['id'], self.req(reason='Revoked after declaration', confirmation=True))
        self.problem(401, self.api.decide, token, body)
        self.assertTrue(validate_integrity(self.office))

    def test_explicit_adoption_is_one_draft_atomic_with_receipt_and_actual_staff_actor(self):
        _, _, token = self.access()
        decision = self.api.decide(token, self.decision_body(token))
        for permission in ('portal.manage', 'finance.read', 'finance.write', 'projects.manage'):
            self.permission(permission)
        body = self.adoption_body(decision)
        before = self.snapshot(('business_document_archives', 'business_document_numbers'))
        first = self.api.adopt(self.tech, self.offer['id'], body)
        self.assertEqual(self.api.adopt(self.tech, self.offer['id'], body), first)
        self.assertEqual(first['created_by'], self.tech['id'])
        result = self.documents.get(self.owner, first['document_id'])
        self.assertEqual((result['kind'], result['status'], result['project_id']), ('order_confirmation', 'draft', self.project))
        self.assertEqual(self.office.db.execute('SELECT created_by FROM business_documents WHERE id=?', (result['id'],)).fetchone()[0], self.tech['id'])
        self.assertEqual(result['positions'], self.offer['positions'])
        self.assertEqual(before, self.snapshot(tuple(before)))
        self.problem(409, self.api.adopt, self.tech, self.offer['id'], {**body, 'request_id': uuid.uuid4().hex})
        self.permission('finance.write', effect='deny', revision=1)
        self.problem(403, self.api.adopt, self.tech, self.offer['id'], body)
        self.assertTrue(validate_integrity(self.office))

    def test_adoption_rollback_and_existing_manual_conversion_prevent_duplicate_targets(self):
        _, _, token = self.access()
        decision = self.api.decide(token, self.decision_body(token))
        body = self.adoption_body(decision)
        tables = ('business_documents', 'business_document_versions', 'business_document_relations',
                  'business_document_requests', 'business_portal_adoptions', 'business_portal_staff_requests', 'audit')
        before = self.snapshot(tables)
        original = self.office.audit
        def fail(actor, action, target):
            if action == 'business.portal.adopted':
                raise RuntimeError('Synthetic final audit failure')
            return original(actor, action, target)
        with patch.object(self.office, 'audit', side_effect=fail), self.assertRaises(RuntimeError):
            self.api.adopt(self.owner, self.offer['id'], body)
        self.assertEqual(self.snapshot(tables), before)
        self.documents.convert(self.owner, self.offer['id'], self.req(revision=self.offer['revision'], target_kind='order_confirmation'))
        self.problem(409, self.api.adopt, self.owner, self.offer['id'], body)
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM business_portal_adoptions').fetchone()[0], 0)

    def test_concurrent_adoptions_create_one_order_confirmation(self):
        _, _, token = self.access()
        decision = self.api.decide(token, self.decision_body(token))
        bodies = [self.adoption_body(decision), self.adoption_body(decision)]
        second = Office(self.path)
        second.portal_origin = self.office.portal_origin
        barrier = threading.Barrier(2)
        def run(args):
            api, body = args
            barrier.wait(timeout=5)
            try:
                return api.adopt(self.owner, self.offer['id'], body)
            except Problem as error:
                return error.status
        try:
            with ThreadPoolExecutor(max_workers=2) as pool:
                outcomes = list(pool.map(run, ((self.api, bodies[0]), (Portal(second, clock=self.clock), bodies[1]))))
        finally:
            second.db.close()
        self.assertEqual(sum(isinstance(item, dict) for item in outcomes), 1)
        self.assertIn(409, outcomes)
        self.assertEqual(self.office.db.execute("SELECT COUNT(*) FROM business_documents WHERE kind='order_confirmation'").fetchone()[0], 1)
        self.assertTrue(validate_integrity(self.office))

    def test_staff_rights_project_denial_and_replay_are_fresh(self):
        body = self.grant_body()
        self.problem(403, self.api.create_grant, self.tech, body)
        self.permission('portal.manage'); self.permission('finance.read')
        created = self.api.create_grant(self.tech, body)
        self.permission('finance.read', effect='deny', revision=1)
        self.problem(403, self.api.create_grant, self.tech, body)
        self.problem(403, self.api.list_grants, self.tech, self.offer['id'])
        self.problem(403, self.api.revoke_grant, self.tech, created['grant']['id'], self.req(reason='Denied', confirmation=True))
        self.permission('finance.read', revision=2)
        self.office.assign(self.owner, self.project, self.tech['id'], remove=True)
        self.problem(404, self.api.create_grant, self.tech, body)

    def test_runtime_origin_module_and_restore_gates_leave_security_actions_available(self):
        from business_organization import Organization
        self.assertEqual(runtime_features(self.office), ('offer_portal',))
        for origin in (None, 'http://portal.example.test', 'https://portal.example.test/path', 'https://a:b@portal.example.test',
                       'https://portal.example.test?x=1', 'https://portal.example.test/#fragment'):
            self.office.portal_origin = origin
            self.assertEqual(runtime_features(self.office), ())
            self.problem(409, self.api.create_grant, self.owner, self.grant_body())
        self.office.portal_origin = 'https://portal.example.test'
        created, _, token = self.access()
        body = self.decision_body(token)
        organization = Organization(self.office)
        settings = organization.get(self.owner)
        modules = {key: dict(visible=value['visibility_override'], enabled=value['enabled']) for key, value in settings['modules'].items()}
        modules['documents']['enabled'] = False
        organization.save(self.owner, self.req(revision=settings['revision'], needs=settings['needs'], modules=modules))
        self.assertFalse(self.api.view(token)['actions_allowed'])
        self.problem(423, self.api.decide, token, body)
        self.api.pdf(token)
        self.api.revoke_grant(self.owner, created['grant']['id'], self.req(reason='Safety action', confirmation=True))
        self.assertEqual(self.api.logout(token), {'logged_out': True})

    def test_rate_counter_failures_persist_and_expired_keys_are_bounded(self):
        key = 'a' * 64
        with patch('business_portal.time.time', return_value=120):
            count_attempt(self.office, key, 2, 60)
            self.problem(401, self.api.open_session, 'f' * 32, 'SPPI_' + 'x' * 43)
            count_attempt(self.office, key, 2, 60)
            self.problem(429, count_attempt, self.office, key, 2, 60)
        second = Office(self.path)
        try:
            self.assertEqual(second.db.execute('SELECT attempts FROM business_portal_rate_counters WHERE key_hash=?', (key,)).fetchone()[0], 3)
        finally:
            second.db.close()
        with patch('business_portal.time.time', return_value=300):
            count_attempt(self.office, 'b' * 64, 2, 60)
        self.assertIsNone(self.office.db.execute('SELECT 1 FROM business_portal_rate_counters WHERE key_hash=?', (key,)).fetchone())

    def test_restore_hook_is_transactional_idempotent_and_preserves_declarations(self):
        created, key, token = self.access()
        decision = self.api.decide(token, self.decision_body(token))
        count_attempt(self.office, 'a' * 64, 2, 60)
        preserved = self.snapshot(('business_portal_decisions', 'business_portal_decision_requests', 'business_document_archives'))
        with self.assertRaises(RuntimeError):
            with transaction(self.office):
                sanitize_after_restore(self.office.db)
                raise RuntimeError('Synthetic restore rollback')
        self.assertEqual(self.api.view(token)['decision'], decision)
        with transaction(self.office):
            sanitize_after_restore(self.office.db)
        state = self.snapshot(('business_portal_revocations', 'business_portal_principals'))
        with transaction(self.office):
            sanitize_after_restore(self.office.db)
        self.assertEqual(self.snapshot(tuple(state)), state)
        self.assertEqual(self.snapshot(tuple(preserved)), preserved)
        self.problem(401, self.api.view, token)
        self.problem(401, self.api.open_session, created['grant']['id'], key)
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM business_portal_rate_counters').fetchone()[0], 0)
        revoked = self.api.list_grants(self.owner, self.offer['id'])['items'][0]['revocation']
        self.assertEqual((revoked['kind'], revoked['revoked_by']), ('restore', None))
        self.assertTrue(validate_integrity(self.office))

    def test_append_only_guards_block_update_delete_and_sqlite_replace_unique_keys(self):
        created, _, token = self.access()
        decision = self.api.decide(token, self.decision_body(token))
        self.api.adopt(self.owner, self.offer['id'], self.adoption_body(decision))
        self.api.revoke_grant(self.owner, created['grant']['id'], self.req(reason='Synthetic guard proof', confirmation=True))
        for table in protected_tables():
            columns = [row['name'] for row in self.office.db.execute('PRAGMA table_info(' + table + ')')]
            values = dict(self.office.db.execute('SELECT * FROM ' + table + ' LIMIT 1').fetchone())
            self.assertTrue(values)
            statements = [('UPDATE ' + table + ' SET ' + columns[0] + '=' + columns[0], ()), ('DELETE FROM ' + table, ())]
            variants = [values]
            if 'id' in values:
                variants.append({**values, 'id': uuid.uuid4().hex})
            for replacement in variants:
                statements.append(('INSERT OR REPLACE INTO ' + table + '(' + ','.join(columns) + ') VALUES(' + ','.join('?' for _ in columns) + ')',
                                   tuple(replacement[column] for column in columns)))
            for sql, arguments in statements:
                with self.subTest(table=table, sql=sql), self.assertRaises(sqlite3.IntegrityError):
                    with self.office.db:
                        self.office.db.execute(sql, arguments)
        self.assertTrue(validate_integrity(self.office))

    def test_request_contract_rejects_unknown_fields_unsafe_actions_and_bad_hashes(self):
        body = self.grant_body()
        for changes in ({'confirmation': False}, {'expires_in_days': True}, {'expires_in_days': 31}, {'recipient_email': 'invalid'},
                        {'recipient_name': 'bad\nname'}, {'company_id': 'other'}):
            self.problem(400, self.api.create_grant, self.owner, {**body, **changes})
        self.problem(409, self.api.create_grant, self.owner, {**body, 'source_revision': True})
        self.problem(409, self.api.create_grant, self.owner, {**body, 'pdf_hash': 'f' * 64})
        self.assertEqual(methods('/portal/grants'), 'GET, POST')
        self.problem(405, dispatch, self.office, self.owner, '/portal/grants', 'DELETE', {})
        self.problem(400, dispatch, self.office, self.owner, '/portal/grants', 'GET', {'_query': {'offer_id': self.offer['id'], 'other': ''}})
        created, _, token = self.access()
        decision_body = self.decision_body(token)
        for changes in ({'decision': 'pending'}, {'statement_version': 'other'}, {'declared_name': ''}, {'confirmation': False}, {'offer_id': self.offer['id']}):
            self.problem(400, self.api.decide, token, {**decision_body, **changes})


class PortalMigrationTests(unittest.TestCase):
    def test_additive_migration_preserves_all_old_tables_and_never_runs_restore_cleanup(self):
        import business_schema
        with tempfile.TemporaryDirectory() as temporary:
            previous = tuple(spec for spec in business_schema.registry() if spec.name != 'business_portal')
            with patch.object(business_schema, 'registry', return_value=previous):
                office = Office(Path(temporary) / 'previous-schema7.db')
            try:
                owner = dict(id=office.add_user('owner@example.test', 'Synthetic-password-123', 'owner'), role='owner')
                project = office.add_project(owner, 'Old project', 'Old customer')
                report = office.draft(owner, project, 'Servicebericht', 'Existing signed report')
                signed = office.sign(owner, report['id'], report['content_hash'], 'Synthetic signer', [[[0.1,0.2],[0.8,0.9]]])
                pdf = office.pdf(owner, report['id'])
                documents = Documents(office)
                request = lambda **body: dict(request_id=uuid.uuid4().hex, **body)
                documents.save_settings(owner, request(revision=0, company_name='Existing issuer', address_line='Existing address',
                    postal_code='10115', city='Berlin', country='DE'))
                draft = documents.create(owner, request(project_id=project, kind='offer', issue_date='2026-11-02',
                    buyer=dict(name='Existing buyer'), positions=[dict(description='Existing material', quantity='1', unit='m', unit_price_net='20', tax_rate='19')]))
                with patch.object(business_schema, 'registry', return_value=previous):
                    rendered = render_prepared(documents.prepare_finalization(owner, draft['id'], draft['revision']))
                    offer = documents.finalize(owner, draft['id'], rendered, uuid.uuid4().hex)
                offer_pdf = documents.archive(owner, offer['id'])
                tables = [row[0] for row in office.db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
                          if not row[0].startswith('business_schema_')]
                snapshot = lambda: {table: sorted((tuple(row) for row in office.db.execute('SELECT * FROM ' + table)), key=repr) for table in tables}
                before = snapshot()
                ensure_schema(office)
                ensure_schema(office)
                self.assertEqual(snapshot(), before)
                self.assertEqual(office.report(owner, report['id']), signed)
                self.assertEqual(office.pdf(owner, report['id']), pdf)
                self.assertEqual(documents.get(owner, offer['id']), offer)
                self.assertEqual(documents.archive(owner, offer['id']), offer_pdf)
                self.assertTrue(validate_integrity(office))
                self.assertEqual(office.db.execute('SELECT COUNT(*) FROM business_portal_revocations').fetchone()[0], 0)
            finally:
                office.db.close()
        with sqlite3.connect(':memory:') as old:
            old.execute('CREATE TABLE legacy(value TEXT)')
            old.execute("INSERT INTO legacy VALUES('preserved')")
            sanitize_after_restore(old)
            self.assertEqual(old.execute('SELECT * FROM legacy').fetchone()[0], 'preserved')


if __name__ == '__main__':
    unittest.main()

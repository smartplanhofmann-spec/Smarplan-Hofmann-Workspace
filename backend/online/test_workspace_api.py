"""Synthetic HTTP workflows through the actual Flask, auth and SQL adapters.

SQLite runs without services; the separate PostgreSQL cases require the same
explicitly disposable smartplan_check database as the existing online suite.
No provider connections, real messages or production data are used.
"""
import base64
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
import hashlib
import json
import time
import unittest
from unittest.mock import patch
import uuid

import test_online as pg_fixture
import test_plan_imports as import_fixture
from core import Office, digest
from inquiries import MAX_EML_BYTES
from online.auth import totp
from online.plan_imports import validate_integrity as validate_imports
from online.store import PostgresOffice, SCHEMA_VERSION
from online.web import create_app
import plan_access
import workspace_api


def request_id():
    return uuid.uuid4().hex


class WorkspaceHttpFlow:
    """Reusable operations only: this mixin intentionally defines no tests."""

    call = import_fixture.PlanImportApiTests.call
    manifest = import_fixture.PlanImportApiTests.manifest

    def mfa_login(self, email='owner@example.test', password='Owner-password-123'):
        pending = self.call('POST', '/login', {'email': email, 'password': password}, token=None).json
        self.assertTrue(pending['mfa_required'])
        self.assertNotIn('token', pending)
        self.secrets[email] = pending.get('enrollment', {}).get('secret', self.secrets.get(email))
        verified = self.call('POST', '/login/verify', {
            'challenge': pending['challenge'],
            'code': totp(self.secrets[email], int(time.time() // 30)),
        }, token=None).json
        return verified['token']

    def add_actor(self, role, *, assign=True):
        email = role + '-' + request_id()[:8] + '@example.test'
        password = 'Synthetic-test-password-123'
        identifier = self.call('POST', '/users', {
            'email': email, 'password': password, 'role': role,
        }, status=201).json['id']
        token = self.mfa_login(email, password)
        if assign:
            self.call('POST', '/assignments', {'project_id': self.project, 'user_id': identifier})
        return identifier, token

    def issue_gmail(self):
        return self.call('POST', '/inbound/gmail/tokens', {
            'name': 'Synthetic Gmail Apps Script', 'source_account': 'inbox@example.test', 'expires_days': 7,
        }, status=201).json

    def gmail_message(self, **changes):
        return {'source_account': 'inbox@example.test', 'source_id': 'synthetic-gmail-message-17',
                'subject': 'Synthetische Anfrage zum Aufmaß',
                'message': 'Bitte zunächst Rückruf und Unterlagen klären. Noch keine Zusage.',
                'sender_name': 'Synthetischer Interessent', 'sender_email': 'CONTACT@example.test',
                'received_at': '2026-10-24T10:00:00+02:00', **changes}

    def reopen(self):
        self.office.db.close()
        self.office = PostgresOffice(pg_fixture.DSN) if self.postgres else Office(self.database)
        self.app = create_app(office=self.office, key=self.key, host='office.example.test')
        self.client = self.app.test_client()

    def run_inquiry_to_project_workflow(self):
        ready = self.client.get('/ready', base_url='https://office.example.test')
        self.assertEqual(ready.status_code, 200)
        self.assertEqual(ready.json['schema_version'], SCHEMA_VERSION)
        self.assertTrue({'project_workspace', 'inquiry_intake', 'gmail_intake', 'offline_workspace', 'plan_deletion'}
                        <= set(ready.json['capabilities']))
        customer = self.call('POST', '/customers', {
            'name': 'Synthetischer Bestandskunde', 'email': 'contact@example.test',
            'address': 'Teststraße 17', 'notes': 'Interne Kundennotiz, nicht für den Eingangszugang',
        }, status=201).json
        self.call('POST', '/customers', {
            'name': 'Synthetischer anderer Kunde', 'email': 'someone@example.test',
        }, status=201)
        count_before = len(self.call('GET', '/customers').json)
        connector = self.issue_gmail()
        envelope = self.gmail_message()
        receipt = self.call('POST', '/intake/gmail', envelope, token=connector['token'], status=201).json
        self.assertEqual(set(receipt), {'id', 'status', 'ingested_at'})
        self.assertEqual(receipt['status'], 'received')
        repeated = self.call('POST', '/intake/gmail', envelope, token=connector['token'], status=201).json
        self.assertEqual(repeated['id'], receipt['id'])
        inbox = self.call('GET', '/inquiries').json
        self.assertEqual([row['id'] for row in inbox], [receipt['id']])
        entry_path = '/inquiries/' + receipt['id']
        entry = self.call('GET', entry_path).json
        self.assertEqual(entry['status'], 'new')
        self.assertIsNone(entry['customer_id'])
        self.assertIsNone(entry['project_id'])
        self.assertEqual(entry['received_at'], '2026-10-24T08:00:00+00:00')
        self.assertEqual([row['id'] for row in entry['candidate_customers']], [customer['id']])
        self.assertEqual(entry['candidate_customers'][0]['match_reasons'], ['email'])
        self.assertEqual(len(self.call('GET', '/customers').json), count_before)
        conversion = {'request_id': request_id(), 'revision': entry['revision'],
                      'project_name': 'Synthetische Erstklärung', 'customer_id': customer['id']}
        converted = self.call('POST', entry_path + '/convert', conversion).json
        self.assertEqual(self.call('POST', entry_path + '/convert', conversion).json, converted)
        self.assertEqual(converted['inquiry']['acceptance_channel'], '')
        self.assertEqual(converted['inquiry']['review_method'], '')
        self.project = converted['project']['id']
        self.assertEqual(converted['project']['customer_id'], customer['id'])
        base = '/projects/' + self.project
        dashboard = self.call('GET', base + '/workspace').json
        self.assertEqual(dashboard['profile']['revision'], 0)
        self.assertEqual(dashboard['profile']['phase'], 'planning')
        self.assertEqual(dashboard['profile']['deposit_status'], 'not_recorded')
        self.assertEqual(dashboard['profile']['materials_status'], 'not_recorded')
        self.assertEqual(dashboard['counters']['tasks_open'], 0)
        self.assertEqual(dashboard['latest_diary'], [])
        technician_id, technician = self.add_actor('technician')
        profile = self.call('POST', base + '/workspace', {
            'request_id': request_id(), 'revision': 0, 'description': 'Erstklärung mit freiem Ablauf',
            'site_address': 'Teststraße 17, Musterstadt', 'phase': 'execution',
        }).json
        # Beginning execution does not invent a deposit or require material milestones.
        self.assertEqual(profile['deposit_status'], 'not_recorded')
        self.assertEqual(profile['materials_status'], 'not_recorded')
        task_request = {'request_id': request_id(), 'title': 'Unterlagen und Aufmaß prüfen',
                        'details': 'Rückfragen zum ausgedruckten Plan klären', 'assignee_id': technician_id,
                        'due_date': '2000-01-01', 'priority': 'high'}
        task = self.call('POST', base + '/tasks', task_request, token=technician, status=201).json
        self.assertEqual(self.call('POST', base + '/tasks', task_request, token=technician, status=201).json, task)
        diary = self.call('POST', base + '/diary', {
            'request_id': request_id(), 'entry_date': '2026-10-24',
            'work_performed': 'Synthetischer Ortstermin und Unterlagenprüfung',
            'issues': 'Maß an der Treppe offen', 'next_steps': 'Maß nachliefern', 'crew_count': 2,
        }, token=technician, status=201).json
        start = (datetime.now(timezone.utc) + timedelta(days=2)).replace(microsecond=0)
        appointment = self.call('POST', base + '/appointments', {
            'request_id': request_id(), 'title': 'Aufmaß, Prüfung; Test',
            'details': 'Unterlagen prüfen\nZweite Zeile',
            'start_at': start.isoformat(), 'end_at': (start + timedelta(hours=1)).isoformat(),
        }, status=201).json
        links = []
        for title, category, url in (
                ('Projektunterlagen in Dropbox', 'dropbox', 'https://www.dropbox.com/scl/fo/synthetic'),
                ('Angebot in sevdesk', 'offer', 'https://my.sevdesk.de/offers/synthetic'),
                ('Rechnung in sevdesk', 'invoice', 'https://my.sevdesk.de/invoices/synthetic')):
            links.append(self.call('POST', base + '/links', {
                'request_id': request_id(), 'title': title, 'category': category, 'url': url,
            }, status=201).json)
        calendar = self.call('GET', base + '/appointments/' + appointment['id'] + '/calendar')
        self.assertEqual(calendar.mimetype, 'text/calendar')
        self.assertIn('attachment;', calendar.headers['Content-Disposition'])
        self.assertIn(b'UID:' + appointment['id'].encode() + b'@smartplan-hofmann.de\r\n', calendar.data)
        self.assertIn(b'SUMMARY:Aufma', calendar.data)
        self.assertIn(b'\\, Pr', calendar.data)
        self.assertIn(b'DESCRIPTION:Unterlagen pr', calendar.data)
        self.assertIn(b'\\nZweite Zeile\r\n', calendar.data)
        self.assertEqual(calendar.data, self.call('GET', base + '/appointments/' + appointment['id'] + '/calendar').data)
        dashboard = self.call('GET', base + '/workspace', token=technician).json
        self.assertEqual(dashboard['counters']['tasks_open'], 1)
        self.assertEqual(dashboard['counters']['tasks_overdue'], 1)
        self.assertEqual(dashboard['counters']['diary_entries'], 1)
        self.assertEqual(dashboard['counters']['appointments_upcoming'], 1)
        self.assertEqual(dashboard['open_tasks'][0]['id'], task['id'])
        self.assertEqual(dashboard['latest_diary'][0]['id'], diary['id'])
        self.assertEqual({row['id'] for row in dashboard['links']}, {row['id'] for row in links})
        self.assertIn(technician_id, {row['id'] for row in dashboard['team']})
        self.assertTrue(all(set(row) == {'id', 'email', 'role'} for row in dashboard['team']))

        # A real binary plan source uploads, then deletion survives delayed retries and restart.
        source = import_fixture.png()
        imports = base + '/plan-imports'
        manifest = self.manifest(source, request_id=request_id())
        uploaded = self.call('POST', imports, manifest, status=201).json
        import_path = imports + '/' + uploaded['id']
        self.call('PUT', import_path + '/chunks/0', source, mime='application/octet-stream')
        self.call('POST', import_path + '/complete', {})
        self.assertEqual(self.call('GET', import_path + '/source').data, source)
        self.assertEqual(self.call('GET', base + '/workspace').json['counters']['imports'], 1)
        deletion = {'request_id': request_id(), 'id': uploaded['id']}
        deleted = self.call('POST', imports + '/delete', deletion).json
        self.assertEqual(deleted['id'], uploaded['id'])
        self.assertTrue(deleted['deleted'])
        self.assertEqual(self.call('POST', imports + '/delete', deletion).json, deleted)
        self.call('POST', imports, manifest, status=410)
        drawing_request = {'request_id': request_id(), 'title': 'Synthetischer Grundriss', 'walls': []}
        drawing = self.call('POST', base + '/plans', drawing_request, status=201).json
        self.call('POST', base + '/plans/delete', {'request_id': request_id(), 'id': drawing['id']})
        self.reopen()
        for suffix in ('', '/source'):
            self.call('GET', import_path + suffix, status=410)
        self.call('POST', imports, manifest, status=410)
        self.call('POST', base + '/plans', drawing_request, status=410)
        self.call('GET', base + '/plans/' + drawing['id'], status=410)
        self.assertEqual(self.call('GET', imports).json, [])
        self.assertEqual(self.call('GET', base + '/plans').json, [])
        dashboard = self.call('GET', base + '/workspace').json
        self.assertEqual(dashboard['counters']['imports'], 0)
        self.assertEqual(dashboard['counters']['plans'], 0)
        self.assertEqual(dashboard['counters']['tasks_open'], 1)
        self.assertEqual(len(self.call('GET', base + '/plan-deletions').json), 2)
        self.assertEqual(self.call('GET', entry_path).json['project_id'], self.project)
        self.assertTrue(validate_imports(self.office))
        workspace_api.validate_integrity(self.office)


class WorkspaceApiTests(WorkspaceHttpFlow, unittest.TestCase):
    tearDown = import_fixture.PlanImportApiTests.tearDown
    open_app = import_fixture.PlanImportApiTests.open_app

    def setUp(self):
        import_fixture.PlanImportApiTests.setUp(self)
        self.postgres = False
        self.secrets = {}
        # Core SQLite intentionally has no online MFA tables. This synthetic
        # online fixture mirrors their production definitions without migration.
        self.office.db.executescript('''
            CREATE TABLE mfa(user_id TEXT PRIMARY KEY REFERENCES users(id),secret TEXT NOT NULL,
                last_step BIGINT NOT NULL DEFAULT -1,recovery TEXT NOT NULL);
            CREATE TABLE auth_challenges(token TEXT PRIMARY KEY,user_id TEXT REFERENCES users(id),
                credential TEXT NOT NULL,secret TEXT NOT NULL,expiry DOUBLE PRECISION NOT NULL,
                failures INTEGER NOT NULL DEFAULT 0);
            CREATE TABLE login_limits(key TEXT PRIMARY KEY,failures INTEGER NOT NULL,
                reset_at DOUBLE PRECISION NOT NULL);
            DELETE FROM sessions;
        ''')
        self.token = self.mfa_login()
        self.owner = self.office.user(self.token)

    def test_full_mfa_gmail_customer_handover_workspace_and_plan_deletion_workflow(self):
        self.run_inquiry_to_project_workflow()

    def test_old_offline_grants_stay_plan_only_and_new_grants_last_seven_days(self):
        base = '/projects/' + self.project
        with self.office.lock, self.office.db:
            old = plan_access.issue(self.office, self.owner)['token']
        self.call('GET', base + '/plans', token=old)
        for path in (base + '/workspace', base + '/tasks', base + '/diary', base + '/appointments', base + '/links'):
            self.call('GET', path, token=old, status=403)
        access = self.call('POST', '/offline/access', {}, status=201).json
        current = access['token']
        self.assertTrue(current.startswith(plan_access.WORKSPACE_PREFIX))
        self.assertIn('offline_workspace', access['capabilities'])
        issued = datetime.fromisoformat(access['issued_at'])
        expires = datetime.fromisoformat(access['expires_at'])
        self.assertEqual(expires - issued, timedelta(days=7))
        self.call('GET', base + '/workspace', token=current)
        task_body = {'request_id': request_id(), 'title': 'Offline erfassbare Aufgabe'}
        task = self.call('POST', base + '/tasks', task_body, token=current, status=201).json
        self.assertEqual(self.call('POST', base + '/tasks', task_body, token=current, status=201).json, task)
        self.call('POST', base + '/diary', {
            'request_id': request_id(), 'work_performed': 'Offline vorbereitet, jetzt synchronisiert',
        }, token=current, status=201)
        for path in ('/inquiries', '/inquiries/connections', '/customers', '/users',
                     base + '/reports', '/inbound/gmail/tokens', '/storage/status', '/me'):
            self.call('GET', path, token=current, status=403)
        self.call('POST', '/offline/access', {}, token=current, status=403)
        self.call('POST', '/inbound/gmail/tokens', {
            'name': 'Forbidden', 'source_account': 'inbox@example.test',
        }, token=current, status=403)
        forged = plan_access.WORKSPACE_PREFIX + old[len(plan_access.PREFIX):]
        self.call('GET', base + '/workspace', token=forged, status=401)
        exact_expiry = self.office.db.execute('SELECT expiry FROM plan_sessions WHERE token=?',
                                              (digest(current),)).fetchone()[0]
        with patch('plan_access.time.time', return_value=exact_expiry):
            self.call('GET', base + '/workspace', token=current, status=401)
        self.call('GET', base + '/workspace', token=current)
        self.call('POST', '/offline/logout', {}, token=current)
        self.call('GET', base + '/workspace', token=current, status=401)
        self.assertEqual(self.call('GET', base + '/tasks').json[0]['id'], task['id'])

    def test_project_scope_fresh_assignment_and_roles_apply_to_every_workspace_adapter(self):
        base = '/projects/' + self.project
        technician_id, technician = self.add_actor('technician')
        accountant_id, accountant = self.add_actor('accountant')
        outsider_id, outsider = self.add_actor('technician', assign=False)
        manager_id, manager = self.add_actor('manager')
        del accountant_id, manager_id
        task = self.call('POST', base + '/tasks', {
            'request_id': request_id(), 'title': 'Aufgabe', 'assignee_id': technician_id,
        }, status=201).json
        appointment = self.call('POST', base + '/appointments', {
            'request_id': request_id(), 'title': 'Termin',
            'start_at': '2030-01-01T10:00:00+01:00', 'end_at': '2030-01-01T11:00:00+01:00',
        }, status=201).json
        routes = [base + '/' + kind for kind in ('workspace', 'tasks', 'diary', 'appointments', 'links')]
        routes += [base + '/tasks/' + task['id'], base + '/appointments/' + appointment['id'] + '/calendar']
        for path in routes:
            self.call('GET', path, token=None, status=401)
            self.call('GET', path, token=outsider, status=404)
            self.call('GET', path, token=accountant)
        self.call('POST', base + '/tasks', {
            'request_id': request_id(), 'title': 'Unerlaubt',
        }, token=accountant, status=403)
        self.call('POST', base + '/workspace', {
            'request_id': request_id(), 'revision': 0, 'description': 'Unerlaubt',
        }, token=technician, status=403)
        profile = self.call('POST', base + '/workspace', {
            'request_id': request_id(), 'revision': 0, 'phase': 'on_hold',
        }, token=manager).json
        self.assertEqual(profile['phase'], 'on_hold')
        self.call('POST', base + '/tasks', {
            'request_id': request_id(), 'title': 'Kein fremder Bearbeiter', 'assignee_id': outsider_id,
        }, status=400)
        other = self.call('POST', '/projects', {'name': 'Anderes synthetisches Projekt',
                                               'customer': 'Anderer synthetischer Kunde'}, status=201).json['id']
        self.call('GET', '/projects/' + other + '/tasks/' + task['id'], status=404)
        offline = self.call('POST', '/offline/access', {}, token=technician, status=201).json['token']
        self.call('GET', base + '/workspace', token=offline)
        self.call('GET', '/projects/' + other + '/workspace', token=offline, status=404)
        self.call('POST', '/assignments', {'project_id': self.project, 'user_id': technician_id, 'remove': True})
        self.call('GET', base + '/workspace', token=offline, status=404)
        self.call('GET', base + '/tasks', token=technician, status=404)
        self.call('POST', '/assignments', {'project_id': self.project, 'user_id': technician_id})
        self.call('GET', base + '/workspace', token=offline)
        self.call('POST', '/users/' + technician_id, {'role': 'accountant'})
        self.call('GET', base + '/workspace', token=offline, status=401)
        self.call('GET', base + '/workspace', token=technician, status=401)

    def test_http_request_retries_stale_revisions_and_atomic_failure(self):
        base = '/projects/' + self.project
        creation = {'request_id': request_id(), 'title': 'Ursprüngliche Aufgabe'}
        first = self.call('POST', base + '/tasks', creation, status=201).json
        path = base + '/tasks/' + first['id']
        update = {'request_id': request_id(), 'revision': 1, 'status': 'done'}
        second = self.call('POST', path, update).json
        self.assertEqual(self.call('POST', path, update).json, second)
        self.assertEqual(self.call('POST', base + '/tasks', creation, status=201).json, first)
        self.assertEqual(self.call('GET', path).json, second)
        self.call('POST', path, {**update, 'request_id': request_id()}, status=409)
        self.call('POST', base + '/tasks', {**creation, 'title': 'Veränderte Wiederholung'}, status=409)
        before = self.office.db.execute('SELECT COUNT(*) FROM workspace_items').fetchone()[0]
        original = self.office.audit

        def fail_audit(actor, action, identifier):
            if action == 'workspace.diary.created':
                raise RuntimeError('Synthetic interrupted transaction')
            return original(actor, action, identifier)

        body = {'request_id': request_id(), 'work_performed': 'Darf nicht halb gespeichert werden'}
        with patch.object(self.office, 'audit', side_effect=fail_audit):
            self.call('POST', base + '/diary', body, status=500)
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM workspace_items').fetchone()[0], before)
        self.assertEqual(self.call('GET', base + '/diary').json, [])
        self.call('POST', base + '/diary', body, status=201)
        workspace_api.validate_integrity(self.office)

    def test_gmail_ingress_credentials_are_single_purpose_minimal_and_revocable(self):
        connector = self.issue_gmail()
        secret = connector['token']
        self.assertTrue(secret.startswith('SPIN_'))
        stored = self.office.db.execute('SELECT token_hash FROM inbound_import_tokens WHERE id=?',
                                        (connector['id'],)).fetchone()[0]
        self.assertEqual(stored, hashlib.sha256(secret.encode()).hexdigest())
        self.assertNotIn(secret, json.dumps(self.call('GET', '/inbound/gmail/tokens').json))
        for path in ('/inquiries', '/customers', '/projects', '/inbound/gmail/tokens',
                     '/projects/' + self.project + '/workspace'):
            self.call('GET', path, token=secret, status=401)
        self.call('POST', '/offline/access', {}, token=secret, status=401)
        self.call('POST', '/intake/gmail', self.gmail_message(), token=self.token, status=401)
        self.call('POST', '/intake/gmail', self.gmail_message(), token=None, status=401)
        self.call('POST', '/intake/gmail', self.gmail_message(source_account='other@example.test'), token=secret, status=403)
        self.call('POST', '/intake/gmail', {**self.gmail_message(), 'attachments': ['forbidden']}, token=secret, status=400)
        self.assertEqual(self.call('GET', '/inquiries').json, [])
        receipt = self.call('POST', '/intake/gmail', self.gmail_message(), token=secret, status=201).json
        self.assertEqual(set(receipt), {'id', 'status', 'ingested_at'})
        self.assertNotIn('message', json.dumps(receipt))
        self.call('POST', '/intake/gmail', self.gmail_message(message='Veränderte Nachrichten-ID'), token=secret, status=409)
        self.assertEqual(len(self.call('GET', '/inquiries').json), 1)
        revoked = self.call('POST', '/inbound/gmail/tokens/' + connector['id'] + '/revoke', {}).json
        self.assertIsNotNone(revoked['revoked_at'])
        self.assertEqual(self.call('POST', '/inbound/gmail/tokens/' + connector['id'] + '/revoke', {}).json, revoked)
        self.call('POST', '/intake/gmail', self.gmail_message(source_id='synthetic-after-revoke'), token=secret, status=401)

    def test_pending_mfa_and_nonowners_cannot_manage_intake_or_read_inbox(self):
        owner = self.call('POST', '/users', {
            'email': 'pending-owner@example.test', 'password': 'Pending-password-123', 'role': 'owner',
        }, status=201).json
        self.assertIn('id', owner)
        pending = self.call('POST', '/login', {
            'email': 'pending-owner@example.test', 'password': 'Pending-password-123',
        }, token=None).json
        for path in ('/inquiries', '/inbound/gmail/tokens'):
            self.call('GET', path, token=pending['challenge'], status=401)
        for role in ('manager', 'technician', 'accountant'):
            _, token = self.add_actor(role)
            for path in ('/inquiries', '/inquiries/connections', '/inbound/gmail/tokens'):
                self.call('GET', path, token=token, status=403)
            self.call('POST', '/inbound/gmail/tokens', {
                'name': 'Nicht zulässig', 'source_account': 'inbox@example.test',
            }, token=token, status=403)
        self.call('POST', '/inbound/gmail/tokens', {
            'name': 'Ohne Anmeldung', 'source_account': 'inbox@example.test',
        }, token=None, status=401)

    def test_gmail_owner_downgrade_expiry_and_envelope_limit_apply_at_http_boundary(self):
        owner_id, owner = self.add_actor('owner', assign=False)
        connector = self.call('POST', '/inbound/gmail/tokens', {
            'name': 'Zweiter synthetischer Besitzer', 'source_account': 'inbox@example.test',
        }, token=owner, status=201).json
        # Administrative tokens are not exposed or revoked through another owner's list.
        self.assertEqual(self.call('GET', '/inbound/gmail/tokens').json, [])
        self.call('POST', '/inbound/gmail/tokens/' + connector['id'] + '/revoke', {}, status=404)
        self.call('POST', '/intake/gmail', self.gmail_message(message='x' * 200_001),
                  token=connector['token'], status=413)
        with self.office.db:
            self.office.db.execute('UPDATE inbound_import_tokens SET expires_at=0 WHERE id=?', (connector['id'],))
        self.call('POST', '/intake/gmail', self.gmail_message(), token=connector['token'], status=401)
        second = self.call('POST', '/inbound/gmail/tokens', {
            'name': 'Vor Rollenwechsel', 'source_account': 'inbox@example.test',
        }, token=owner, status=201).json
        self.call('POST', '/users/' + owner_id, {'role': 'manager'})
        self.call('POST', '/intake/gmail', self.gmail_message(), token=second['token'], status=401)
        self.assertEqual(self.call('GET', '/inquiries').json, [])

    def test_connection_state_is_observed_delivery_and_not_a_fake_live_integration(self):
        def gmail():
            result = self.call('GET', '/inquiries/connections').json
            self.assertFalse(result['automatic_ingestion'])
            return next(row for row in result['providers'] if row['id'] == 'gmail')

        self.assertEqual(gmail()['state'], 'not_connected')
        connector = self.issue_gmail()
        self.assertEqual(gmail()['state'], 'awaiting_first_delivery')
        self.assertIsNone(gmail()['last_received_at'])
        self.call('POST', '/intake/gmail', self.gmail_message(), token=connector['token'], status=201)
        self.assertEqual(gmail()['state'], 'received')
        self.assertIsNotNone(gmail()['last_received_at'])
        self.call('POST', '/inbound/gmail/tokens/' + connector['id'] + '/revoke', {})
        self.assertEqual(gmail()['state'], 'not_connected')

    def test_eml_http_adapter_bounds_base64_and_preserves_only_attachment_metadata(self):
        mail = EmailMessage()
        mail['From'] = 'Synthetischer Absender <sender@example.test>'
        mail['Subject'] = 'Synthetisches Aufmaß'
        mail['Message-ID'] = '<synthetic-eml-17@example.test>'
        mail.set_content('Bitte Rückruf zur Planung.')
        mail.add_alternative('<p>HTML Alternative</p><script>PRIVATE_SCRIPT</script>', subtype='html')
        attachment = b'SYNTHETIC_ATTACHMENT_BYTES_7341'
        mail.add_attachment(attachment, maintype='application', subtype='pdf', filename='../../Plan.pdf')
        body = {'request_id': request_id(), 'content_base64': base64.b64encode(mail.as_bytes()).decode()}
        entry = self.call('POST', '/inquiries/import-eml', body, status=201).json
        self.assertEqual(entry['source'], 'import')
        self.assertIn('Bitte Rückruf', entry['message'])
        self.assertNotIn('PRIVATE_SCRIPT', json.dumps(entry))
        self.assertEqual(entry['provenance']['attachments'][0]['filename'], 'Plan.pdf')
        self.assertEqual(entry['provenance']['attachments'][0]['size'], len(attachment))
        self.assertNotIn(attachment.decode(), json.dumps(entry))
        self.assertEqual(self.call('POST', '/inquiries/import-eml', body, status=201).json, entry)
        for bad in ('@@invalid@@', 'a', 42, None):
            self.call('POST', '/inquiries/import-eml', {'request_id': request_id(), 'content_base64': bad},
                      status=400 if isinstance(bad, str) else 413)
        encoded = base64.b64encode(b'x' * (MAX_EML_BYTES + 1)).decode()
        self.call('POST', '/inquiries/import-eml', {'request_id': request_id(), 'content_base64': encoded}, status=413)
        self.call('POST', '/inquiries/import-eml', {**body, 'filename': 'not-an-adapter-field.eml'}, status=400)
        self.assertEqual(len(self.call('GET', '/inquiries').json), 1)

    def test_new_routes_enforce_methods_json_size_and_https_headers(self):
        base = '/projects/' + self.project
        for path, allowed in ((base + '/workspace', 'GET, POST'), (base + '/tasks', 'GET, POST'),
                              ('/inquiries', 'GET, POST'), ('/inbound/gmail/tokens', 'GET, POST')):
            response = self.call('DELETE', path, status=405)
            self.assertEqual(response.headers['Allow'], allowed)
        self.call('POST', base + '/tasks', b'[]', mime='application/json', status=400)
        self.call('POST', base + '/tasks', b'{', mime='application/json', status=400)
        self.call('POST', base + '/tasks', b'plain', mime='text/plain', status=415)
        self.call('POST', base + '/tasks', {'request_id': request_id(), 'title': 'x' * 1_000_000}, status=413)
        self.call('GET', base + '/workspace/unknown', status=404)
        response = self.call('GET', base + '/workspace')
        self.assertEqual(response.headers['Cache-Control'], 'no-store')
        self.assertEqual(response.headers['X-Content-Type-Options'], 'nosniff')
        insecure = self.client.get('/api/v1' + base + '/workspace', base_url='http://office.example.test',
                                   headers={'Authorization': 'Bearer ' + self.token})
        self.assertEqual(insecure.status_code, 400)


@unittest.skipUnless(pg_fixture.DSN, 'Disposable SMARTPLAN_TEST_DSN required')
class PostgresWorkspaceApiTests(WorkspaceHttpFlow, unittest.TestCase):
    """Separate real PostgreSQL contract; never inherits SQLite test methods."""

    def setUp(self):
        pg_fixture.OnlineApiTests.setUp(self)
        self.postgres = True
        self.token = self.mfa_login()
        self.owner = self.office.user(self.token)

    def tearDown(self):
        try:
            self.office.db.close()
        finally:
            # reset() validates smartplan_check via the imported fixture and
            # CASCADE removes all new workspace/inquiry/token child records.
            pg_fixture.reset()

    def test_mfa_gmail_to_project_workspace_and_tombstones_survive_reconnection(self):
        self.run_inquiry_to_project_workflow()


if __name__ == '__main__':
    unittest.main(verbosity=2)

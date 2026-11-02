"""Company setup and operator binding under real least-privilege PostgreSQL.

Only the guarded disposable loopback smartplan_check database is reset. These
contracts do not certify multiple companies in a shared database or deployment.
"""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from pathlib import Path
import tempfile
import threading
import unittest
import uuid

from cryptography.fernet import Fernet
import psycopg
from psycopg import sql
from psycopg.conninfo import make_conninfo

import business_schema
from business_organization import Organization
from core import Problem
from online import release, test_online as base, test_business_journey_pg as journey
from online.instance import bind, identity, verify, InstanceConfigurationError
from online.storage import Storage
from online.store import migrate, PostgresOffice
from online.web import create_app


def configuration_body(value):
    return dict(request_id=uuid.uuid4().hex, revision=value['revision'], needs=deepcopy(value['needs']),
                modules={key: dict(visible=item['visibility_override'], enabled=item['enabled'])
                         for key, item in value['modules'].items()})


@unittest.skipUnless(journey.DSN, 'Disposable loopback SMARTPLAN_TEST_DSN required')
class OrganizationPostgres(unittest.TestCase):
    setUp = journey.BusinessJourneyPostgres.setUp
    call = journey.BusinessJourneyPostgres.call
    login = journey.BusinessJourneyPostgres.login

    def test_employee_suggestion_manual_override_history_and_permissions(self):
        self.assertTrue(business_schema.require_runtime_security(self.office))
        self.assertEqual(self.office.db.execute('SELECT current_user').fetchone()[0], 'smartplan-online')
        config = self.call('GET', '/business/organization').json
        self.assertFalse(config['modules']['personnel']['visible'])
        owner = self.office.user(self.token)
        employee = self.call('POST', '/business/employees', journey.request(
            user_id=owner['id'], name='Synthetic working owner'), status=201).json
        config = self.call('GET', '/business/organization').json
        self.assertTrue(config['modules']['personnel']['visible'])
        body = configuration_body(config)
        body['modules']['personnel'] = dict(visible=False, enabled=False)
        saved = self.call('POST', '/business/organization', body).json
        self.assertEqual(saved, self.call('POST', '/business/organization', body).json)
        self.call('POST', '/business/time/events', journey.request(), status=423)
        self.assertEqual(self.call('GET', '/business/employees').json['items'][0]['id'], employee['id'])
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM business_organization_events').fetchone()[0], 1)
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM business_organization_requests').fetchone()[0], 1)
        for statement in ('DELETE FROM business_organization_events',
                          'UPDATE business_organization_events SET revision=2'):
            with self.assertRaises(psycopg.Error), self.office.db:
                self.office.db.execute(statement)
        self.call('POST', '/users', {'email': 'limited@example.test',
            'password': 'Synthetic-limited-password-123', 'role': 'technician'}, status=201)
        limited = self.login('limited@example.test', 'Synthetic-limited-password-123')
        self.call('GET', '/business/organization', token=limited, status=403)
        self.call('POST', '/business/organization', body, token=limited, status=403)
        self.call('GET', '/business/organization?company_id=foreign', status=400)
        self.call('POST', '/business/organization', {**body, 'company_id': 'foreign'}, status=400)

    def test_competing_runtime_writers_commit_one_revision_and_replay_it_after_reconnect(self):
        config = self.call('GET', '/business/organization').json
        owner = self.office.user(self.token)
        commands = [configuration_body(config), configuration_body(config)]
        commands[0]['needs']['uses_inventory'] = True
        commands[1]['needs']['works_with_tax_advisor'] = True
        ready = threading.Barrier(2)

        def write(body):
            worker = PostgresOffice(self.office.db.dsn)
            try:
                ready.wait(timeout=5)
                try:
                    return 200, body, Organization(worker).save(owner, body)
                except Problem as error:
                    return error.status, body, None
            finally:
                worker.db.close()

        with ThreadPoolExecutor(max_workers=2) as workers:
            outcomes = list(workers.map(write, commands))
        self.assertEqual(sorted(item[0] for item in outcomes), [200, 409])
        _, winning_body, committed = next(item for item in outcomes if item[0] == 200)
        reopened = PostgresOffice(self.office.db.dsn)
        try:
            self.assertEqual(Organization(reopened).save(owner, winning_body), committed)
            self.assertEqual(Organization(reopened).get(owner), committed)
            self.assertEqual(reopened.db.execute('SELECT COUNT(*) FROM business_organization_events').fetchone()[0], 1)
        finally:
            reopened.db.close()


@unittest.skipUnless(journey.DSN, 'Disposable loopback SMARTPLAN_TEST_DSN required')
class InstanceBindingPostgres(unittest.TestCase):
    def setUp(self):
        base.reset()
        migrate(journey.DSN, compatibility_mode='business', require_business_modules=True)
        bootstrap = PostgresOffice(journey.DSN)
        try:
            bootstrap.add_user('owner@example.test', 'Synthetic-owner-password-123', 'owner')
        finally:
            bootstrap.db.close()
        with psycopg.connect(journey.DSN) as connection:
            if not connection.execute("SELECT 1 FROM pg_roles WHERE rolname='smartplan-online'").fetchone():
                connection.execute('CREATE ROLE "smartplan-online" LOGIN')
            connection.execute(sql.SQL('ALTER ROLE "smartplan-online" PASSWORD {}').format(
                sql.Literal('synthetic-business-runtime-only')))
        release.secure_database(journey.DSN, test_mode=True)
        self.temp = tempfile.TemporaryDirectory(prefix='smartplan-pg-instance-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / 'company-files'
        self.key, self.host, self.instance_id = Fernet.generate_key(), 'company.example.test', uuid.uuid4().hex
        self.office = PostgresOffice(make_conninfo(journey.DSN, user='smartplan-online',
                                                   password='synthetic-business-runtime-only'))
        self.addCleanup(self.office.db.close)
        self.storage = self.storage_for(self.office)

    def storage_for(self, office):
        return Storage(office, self.key, self.host, config={'server': {'path': str(self.root)}})

    def operator_bind(self):
        operator = PostgresOffice(journey.DSN)
        try:
            with operator.db:
                operator.db.execute('SET LOCAL ROLE "smartplan-migrator"')
                return bind(operator, self.instance_id, self.host, self.key, self.storage_for(operator))
        finally:
            operator.db.close()

    def test_explicit_migrator_binding_survives_restart_and_runtime_cannot_change_identity(self):
        self.assertTrue(business_schema.require_runtime_security(self.office))
        self.assertIsNone(identity(self.office))
        result = self.operator_bind()
        saved = identity(self.office)
        self.assertEqual(self.operator_bind(), result)
        self.assertEqual(identity(self.office), saved)
        self.assertEqual(verify(self.office, self.instance_id, self.host, self.key, self.storage), result)
        for statement in ('DELETE FROM business_instance_identity',
                          "UPDATE business_instance_identity SET public_host='other.example.test'",
                          'INSERT INTO business_instance_identity SELECT * FROM business_instance_identity',
                          'TRUNCATE business_instance_identity'):
            with self.assertRaises(psycopg.errors.InsufficientPrivilege), self.office.db:
                self.office.db.execute(statement)
        reopened = PostgresOffice(self.office.db.dsn)
        try:
            app = create_app(office=reopened, key=self.key, host=self.host,
                             storage=self.storage_for(reopened), instance_id=self.instance_id)
            self.assertEqual(app.extensions['smartplan_instance'], result)
            self.assertEqual(app.test_client().get('/ready', base_url='https://' + self.host).status_code, 200)
        finally:
            reopened.db.close()
        self.assertEqual(identity(self.office), saved)

    def test_bound_runtime_rejects_missing_or_wrong_company_configuration(self):
        self.operator_bind()
        for instance_id, host, key in ((None, self.host, self.key),
                                       (uuid.uuid4().hex, self.host, self.key),
                                       (self.instance_id, 'foreign.example.test', self.key),
                                       (self.instance_id, self.host, Fernet.generate_key())):
            with self.subTest(instance_id=instance_id, host=host), self.assertRaises(InstanceConfigurationError):
                verify(self.office, instance_id, host, key, self.storage)


if __name__ == '__main__':
    unittest.main()

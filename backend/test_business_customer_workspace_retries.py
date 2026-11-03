"""A rejected first attempt must not strand the editor or erase a real receipt."""
import unittest
from unittest.mock import patch

from core import Problem
import test_business_customer_workspace as fixture

request = fixture.request


class CustomerWorkspaceRetryTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixture.CustomerWorkspaceTests('runTest')
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)

    def error(self, function, *args):
        with self.assertRaises(Problem) as caught:
            function(*args)
        self.assertEqual(caught.exception.status, 409)
        return caught.exception

    def test_stale_unaccepted_publication_can_be_edited_but_receipted_nonce_stays_fixed(self):
        f = self.fixture
        result, body = f.publication()
        rejected = request(**{key: value for key, value in body.items() if key != 'request_id'})
        error = self.error(f.api.publish, f.owner, rejected)
        self.assertEqual(error.request_resolution, 'not_accepted')
        self.assertIsNone(f.office.db.execute(
            'SELECT 1 FROM business_customer_staff_requests WHERE request_id=?', (rejected['request_id'],)).fetchone())
        conflict = self.error(f.api.publish, f.owner, dict(body, title='Changed after acceptance'))
        self.assertIsNone(conflict.request_resolution)
        self.assertEqual(f.api.publish(f.owner, body), result)

    def test_same_active_recipient_is_known_unaccepted_and_original_link_receipt_survives(self):
        f = self.fixture
        result, body, _, _ = f.grant()
        rejected = request(**{key: value for key, value in body.items() if key != 'request_id'})
        self.assertEqual(self.error(f.api.create_grant, f.owner, rejected).request_resolution, 'not_accepted')
        replay = f.api.create_grant(f.owner, body)
        self.assertEqual(replay['grant']['id'], result['grant']['id'])
        self.assertFalse(replay['link_available'])

    def test_source_change_before_first_acceptance_and_after_saved_receipt_are_distinct(self):
        f = self.fixture
        _, _, token, _ = f.grant()
        upload, _ = f.upload(token)
        accepted = f.api.accept_upload(f.owner, upload['id'], request(classification='operational', confirmation=True))
        _, body = f.publish_media(accepted['media_id'])
        other = request(**{key: value for key, value in body.items() if key != 'request_id'})
        with patch.object(f.api, '_source', side_effect=Problem(409, 'Source is no longer available')):
            self.assertEqual(self.error(f.api.publish_file, f.owner, other).request_resolution, 'not_accepted')
            self.assertIsNone(self.error(f.api.publish_file, f.owner, body).request_resolution)

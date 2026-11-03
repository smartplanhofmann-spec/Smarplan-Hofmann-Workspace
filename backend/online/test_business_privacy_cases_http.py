"""Actual MFA HTTP reference receipts and bounded private case contracts."""
import json
import unittest
import uuid
from datetime import date
from online import test_portal_http as fixture


class PrivacyCasesHttp(unittest.TestCase):
    call=fixture.PortalHTTPTests.call
    staff_call=fixture.PortalHTTPTests.staff_call
    req=staticmethod(fixture.PortalHTTPTests.req)
    setUp=fixture.PortalHTTPTests.setUp

    def test_actual_mfa_intake_lost_ack_reference_status_and_strict_transport(self):
        contact=self.staff_call('/business/contacts',self.req(name='Synthetic private HTTP person',email='private-http@example.test',entity_type='person'),status=201).json
        today=date.today().isoformat()
        me=self.staff_call('/me').json
        command=self.req(id=uuid.uuid4().hex,subject_kind='customer',subject_id=contact['id'],request_kind='access',received_date=today,
            due_date=today,retain_until=today,assigned_to=me['id'],scope='Synthetic access request',retention_reason='Temporary private working purpose')
        value=self.staff_call('/business/privacy/cases',command).json
        path='/business/privacy/cases/'+value['id']
        proof=self.staff_call(path+'/commands/'+command['request_id']).json
        self.assertEqual(proof['reference'],{'case_id':value['id']});self.assertTrue(proof['confirmed'])
        self.assertNotIn(contact['email'],json.dumps(proof))
        self.assertEqual(self.staff_call('/business/privacy/cases',command).json,value)
        self.staff_call(path+'/commands/'+uuid.uuid4().hex,status=404)
        self.call(path+'/commands/'+command['request_id'],token='SPCT_'+'a'*43,status=401)
        self.staff_call(path+'/commands/'+command['request_id'],{},method='GET',status=400)
        self.staff_call(path+'/commands/'+command['request_id']+'?ignored=1',status=400)
        self.staff_call('/business/privacy/cases?ignored=1',command,status=400)
        self.staff_call('/business/privacy/cases',raw=json.dumps(command)[:-1]+',"scope":"duplicate"}',status=400)
        self.staff_call('/business/privacy/cases',raw='{"x":NaN}',status=400)
        options=self.staff_call('/business/privacy/cases/options?q=Synthetic%20private%20HTTP').json
        self.assertEqual(options['subjects'],[{'kind':'customer','id':contact['id'],'label':contact['name']}])
        self.staff_call('/business/privacy/cases/options?ignored=1',status=400)
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM business_privacy_case_events').fetchone()[0],1)


if __name__=='__main__':unittest.main()

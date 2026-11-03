"""Actual MFA and strict HTTP body limits for ephemeral speech transcription."""
import base64
import json
import os
import unittest
from unittest.mock import patch
import uuid

from core import now_iso
from online import test_portal_http as fixture
from test_business_assistant_speech import wav, SyntheticSpeech
from business_assistant_speech import validate_integrity


class SpeechHTTP(unittest.TestCase):
    call=fixture.PortalHTTPTests.call
    staff_call=fixture.PortalHTTPTests.staff_call
    req=staticmethod(fixture.PortalHTTPTests.req)

    def setUp(self):
        fixture.PortalHTTPTests.setUp(self)
        instance=uuid.uuid4().hex
        with self.office.db:
            self.office.db.execute('INSERT INTO business_instance_identity(singleton,instance_id,public_host,storage_root,vault_fingerprint,created_at) VALUES(1,?,?,?,?,?)',
                (instance,'portal.example.test',str(self.directory),'a'*64,now_iso()))
        self.env={'SMARTPLAN_ASSISTANT_SPEECH_ENABLED':'1','SMARTPLAN_ASSISTANT_SPEECH_DATA_TRANSFER_APPROVED':'1',
            'SMARTPLAN_ASSISTANT_SPEECH_INSTANCE_ID':instance,'SMARTPLAN_ASSISTANT_SPEECH_ENDPOINT':'https://speech.example.test/v1/audio/transcriptions',
            'SMARTPLAN_ASSISTANT_SPEECH_MODEL':'synthetic-transcription','SMARTPLAN_ASSISTANT_SPEECH_API_KEY':'synthetic-never-transmitted-secret'}
        environment=patch.dict(os.environ,self.env);environment.start();self.addCleanup(environment.stop)
        self.transport=SyntheticSpeech()
        transport=patch('business_assistant_speech.OpenAICompatibleSpeech',return_value=self.transport);transport.start();self.addCleanup(transport.stop)
        self.project=self.staff_call('/projects',dict(name='Synthetic speech project',customer='Synthetic customer'),status=201).json['id']
        self.context=self.staff_call('/business/assistant/contexts',self.req(project_id=self.project,sources=[dict(kind='project',id=self.project)])).json

    def body(self,samples=16000):
        return self.req(context_id=self.context['id'],data_transfer_confirmed=True,audio_base64=base64.b64encode(wav(samples)).decode())

    def test_valid_sixty_second_audio_above_one_megabyte_and_lost_reply_status(self):
        body=self.body(960000)
        self.assertGreater(len(json.dumps(body)),1_000_000)
        status=self.staff_call('/business/assistant/speech/status?project_id='+self.project).json
        self.assertEqual(status['limits']['max_audio_bytes'],1920044);self.assertTrue(status['provider']['configured'])
        result=self.staff_call('/business/assistant/speech/transcribe',body).json
        self.assertEqual(result['status'],'completed');self.assertEqual(result['text'],self.transport.result)
        self.staff_call('/business/assistant/speech/transcribe',body,status=409)
        metadata=self.staff_call('/business/assistant/speech/requests/'+body['request_id']).json
        self.assertNotIn('text',metadata);self.assertEqual(metadata['status'],'completed')
        self.assertEqual(len(self.transport.calls),1)
        self.assertTrue(validate_integrity(self.office))

    def test_speech_limit_does_not_expand_other_routes_and_strict_json_is_retained(self):
        path='/business/assistant/speech/transcribe'
        self.staff_call(path,raw='x'*2_600_001,status=413)
        self.staff_call('/business/assistant/chat',raw='x'*1_000_001,status=413)
        body=self.body()
        encoded=json.dumps(body)
        self.staff_call(path,raw=encoded[:-1]+',"data_transfer_confirmed":true}',status=400)
        self.staff_call(path,raw=encoded.replace('true','NaN',1),status=400)
        self.staff_call(path+'?ignored=1',body,status=400)
        self.staff_call('/business/assistant/speech/status?project_id='+self.project,{},method='GET',status=400)
        self.call(path,body,token='SPCT_'+'a'*43,status=401)
        self.assertEqual(self.transport.calls,[])
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM business_assistant_speech_requests').fetchone()[0],0)


if __name__=='__main__':unittest.main()

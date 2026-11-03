"""Synthetic dictation, metadata-only persistence and no provider retries."""
import base64
import hashlib
import json
import os
import struct
import unittest
from unittest.mock import patch
import uuid

from core import Problem
from business_assistant_speech import AssistantSpeech, SpeechConfiguration, OpenAICompatibleSpeech, configuration, wav_bytes, validate_integrity, sanitize_after_restore
from business_foundation import BusinessFoundation
import test_business_assistant as fixture
import test_business_assistant_provider as provider_fixture


def wav(samples=16000):
    pcm=(b'private-synthetic-audio!!'*((samples*2+23)//24))[:samples*2]
    return struct.pack('<4sI4s4sIHHIIHH4sI',b'RIFF',len(pcm)+36,b'WAVE',b'fmt ',16,1,1,16000,32000,2,16,b'data',len(pcm))+pcm


class SyntheticSpeech:
    def __init__(self,effect=None,result='Nur synthetische, private Diktatwörter.'):
        self.effect,self.result,self.calls=effect,result,[]
    def transcribe(self,config,audio,operation):
        self.calls.append((config.public(),hashlib.sha256(audio).hexdigest(),operation))
        if self.effect:self.effect()
        return self.result


class SpeechDomain(unittest.TestCase):
    def setUp(self):
        self.fixture=fixture.AssistantTests()
        self.fixture.setUp();self.addCleanup(self.fixture.doCleanups)
        for key in ('office','owner','other','project','private','clock','path','problem'):
            setattr(self,key,getattr(self.fixture,key))
        self.fixture.bind_model(fixture.SyntheticModelForTests())
        instance=self.office.db.execute('SELECT instance_id FROM business_instance_identity').fetchone()['instance_id']
        self.env={
            'SMARTPLAN_ASSISTANT_SPEECH_ENABLED':'1','SMARTPLAN_ASSISTANT_SPEECH_DATA_TRANSFER_APPROVED':'1',
            'SMARTPLAN_ASSISTANT_SPEECH_INSTANCE_ID':instance,
            'SMARTPLAN_ASSISTANT_SPEECH_ENDPOINT':'https://speech.example.test/v1/audio/transcriptions',
            'SMARTPLAN_ASSISTANT_SPEECH_MODEL':'synthetic-transcription',
            'SMARTPLAN_ASSISTANT_SPEECH_API_KEY':'synthetic-speech-private-secret',
        }
        self.context=self.fixture.context()
        self.transport=SyntheticSpeech()
        self.api=AssistantSpeech(self.office,clock=self.clock,environ=self.env,transport=self.transport)
        self.body=fixture.request(context_id=self.context['id'],data_transfer_confirmed=True,audio_base64=base64.b64encode(wav()).decode())

    def test_audio_and_transcript_exist_only_in_transient_response_with_exact_context(self):
        result=self.api.transcribe(self.owner,self.body)
        self.assertEqual(result['text'],self.transport.result)
        self.assertEqual(result['context_sha256'],self.context['sha256'])
        status=self.api.request(self.owner,self.body['request_id'])
        self.assertEqual(status['status'],'completed');self.assertNotIn('text',status)
        self.assertFalse(status['audio_persisted']);self.assertFalse(status['transcript_persisted'])
        for table in ('business_assistant_speech_requests','business_assistant_speech_outcomes','audit'):
            dumped=json.dumps([dict(row) for row in self.office.db.execute('SELECT * FROM '+table)])
            for private in (self.body['audio_base64'],self.transport.result,self.env['SMARTPLAN_ASSISTANT_SPEECH_API_KEY']):
                self.assertNotIn(private,dumped)
        self.assertNotIn(wav(),self.path.read_bytes())
        self.assertTrue(validate_integrity(self.office))

    def test_same_request_never_invokes_provider_again_even_after_success(self):
        self.api.transcribe(self.owner,self.body)
        self.problem(409,self.api.transcribe,self.owner,self.body)
        self.problem(409,self.api.transcribe,self.owner,{**self.body,'audio_base64':base64.b64encode(wav(8000)).decode()})
        self.assertEqual(len(self.transport.calls),1)
        self.problem(404,self.api.request,self.other,self.body['request_id'])

    def test_timeout_is_metadata_only_and_cannot_be_retried(self):
        self.transport.effect=lambda:(_ for _ in ()).throw(TimeoutError('Synthetic private provider response'))
        self.problem(502,self.api.transcribe,self.owner,self.body)
        self.assertEqual(self.api.request(self.owner,self.body['request_id'])['status'],'failed')
        self.problem(409,self.api.transcribe,self.owner,self.body)
        self.assertEqual(len(self.transport.calls),1)

    def test_rights_revoked_during_provider_response_never_return_transcript(self):
        self.office.assign(self.owner,self.project,self.other['id'])
        def revoke():
            BusinessFoundation(self.office).save_grant(self.owner,fixture.request(user_id=self.other['id'],permission='assistant.use',scope=self.project,effect='deny',revision=0))
        self.transport.effect=revoke
        self.problem(403,self.api.transcribe,self.other,self.body)
        self.assertEqual(self.office.db.execute('SELECT error_code FROM business_assistant_speech_outcomes').fetchone()['error_code'],'access_or_context_changed')
        self.problem(403,self.api.request,self.other,self.body['request_id'])

    def test_source_changed_during_provider_call_rejects_text_without_creating_assistant_action(self):
        def change():
            self.office.db.execute("UPDATE projects SET name='Changed synthetic project' WHERE id=?",(self.project,));self.office.db.commit()
        self.transport.effect=change
        self.problem(409,self.api.transcribe,self.owner,self.body)
        self.assertEqual(self.api.request(self.owner,self.body['request_id'])['status'],'failed')
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM business_assistant_plans').fetchone()[0],0)

    def test_selected_source_right_revoked_while_assistant_use_remains_allowed(self):
        self.office.assign(self.owner,self.project,self.other['id'])
        def revoke():
            BusinessFoundation(self.office).save_grant(self.owner,fixture.request(user_id=self.other['id'],permission='documents.read',scope=self.project,effect='deny',revision=0))
        self.transport.effect=revoke
        self.problem(403,self.api.transcribe,self.other,self.body)
        self.api.assistant._access(self.other,self.project)
        self.problem(403,self.api.request,self.other,self.body['request_id'])
        self.assertEqual(len(self.transport.calls),1)

    def test_instance_provider_approval_revoked_during_response_rejects_text(self):
        self.transport.effect=lambda:self.env.update(SMARTPLAN_ASSISTANT_SPEECH_DATA_TRANSFER_APPROVED='0')
        self.problem(409,self.api.transcribe,self.owner,self.body)
        self.assertEqual(self.api.request(self.owner,self.body['request_id'])['status'],'failed')
        self.assertEqual(len(self.transport.calls),1)

    def test_consent_foreign_context_and_missing_provider_stop_before_claim(self):
        self.problem(400,self.api.transcribe,self.owner,{**self.body,'data_transfer_confirmed':False})
        self.problem(404,self.api.transcribe,self.other,self.body)
        self.api.environ={**self.env,'SMARTPLAN_ASSISTANT_SPEECH_INSTANCE_ID':'f'*32}
        self.problem(409,self.api.transcribe,self.owner,self.body)
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM business_assistant_speech_requests').fetchone()[0],0)
        self.assertEqual(self.transport.calls,[])

    def test_restore_interruption_retains_claim_and_never_reopens_provider_call(self):
        self.transport.effect=lambda:(_ for _ in ()).throw(KeyboardInterrupt())
        with self.assertRaises(KeyboardInterrupt):self.api.transcribe(self.owner,self.body)
        self.assertEqual(self.api.request(self.owner,self.body['request_id'])['status'],'started')
        with self.office.db:sanitize_after_restore(self.office.db);sanitize_after_restore(self.office.db)
        self.assertEqual(self.api.request(self.owner,self.body['request_id'])['status'],'interrupted')
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM business_assistant_speech_outcomes').fetchone()[0],1)
        self.problem(409,self.api.transcribe,self.owner,self.body)
        self.assertTrue(validate_integrity(self.office))

    def test_same_id_during_provider_call_is_already_claimed(self):
        self.transport.effect=lambda:self.problem(409,self.api.transcribe,self.owner,self.body)
        self.assertEqual(self.api.transcribe(self.owner,self.body)['status'],'completed')
        self.assertEqual(len(self.transport.calls),1)

    def test_restore_during_provider_call_never_releases_late_transcript(self):
        def restore():
            with self.office.db:sanitize_after_restore(self.office.db)
        self.transport.effect=restore
        self.problem(409,self.api.transcribe,self.owner,self.body)
        self.assertEqual(self.api.request(self.owner,self.body['request_id'])['status'],'interrupted')
        self.assertEqual(len(self.transport.calls),1)
        self.assertTrue(validate_integrity(self.office))

    def test_configuration_changes_after_claim_stop_before_provider(self):
        actual=configuration
        count=0
        def changing(office,environ):
            nonlocal count
            count+=1
            if count==2:self.env['SMARTPLAN_ASSISTANT_SPEECH_MODEL']='changed-synthetic-model'
            return actual(office,environ)
        with patch('business_assistant_speech.configuration',side_effect=changing):
            self.problem(409,self.api.transcribe,self.owner,self.body)
        self.assertEqual(self.transport.calls,[])
        status=self.api.request(self.owner,self.body['request_id'])
        self.assertEqual(status['status'],'failed');self.assertFalse(status['provider_call_may_have_been_charged'])

    def test_configuration_is_explicit_instance_bound_and_separate_from_chat(self):
        self.assertEqual(configuration(self.office,self.env).public()['adapter'],'openai_compatible_transcription')
        for change in ({'ENABLED':'0'},{'DATA_TRANSFER_APPROVED':'0'},{'INSTANCE_ID':'f'*32},
                       {'ENDPOINT':'http://speech.example.test/v1/audio/transcriptions'},
                       {'ENDPOINT':'https://speech.example.test/v1/chat/completions'},
                       {'ENDPOINT':'https://user:secret@speech.example.test/v1/audio/transcriptions'}):
            with self.subTest(change=change),self.assertRaises(Problem):
                configuration(self.office,{**self.env,**{'SMARTPLAN_ASSISTANT_SPEECH_'+key:value for key,value in change.items()}})
        self.assertNotIn(self.env['SMARTPLAN_ASSISTANT_SPEECH_API_KEY'],repr(configuration(self.office,self.env)))


class SpeechWire(unittest.TestCase):
    def test_canonical_wav_exact_sixty_seconds_and_malformed_audio(self):
        self.assertEqual(wav_bytes(base64.b64encode(wav(960000)).decode())[1],960000)
        for raw in (wav(0),wav()+b'trailing',wav()[:44],b'not wav',wav().replace(b'WAVE',b'FLAC',1),
                    wav()[:22]+struct.pack('<I',44100)+wav()[26:]):
            with self.subTest(size=len(raw)),self.assertRaises(Problem):wav_bytes(base64.b64encode(raw).decode())
        for encoded in ('not base64!','a'*(4*((1920044+2)//3)+1)):
            with self.assertRaises(Problem):wav_bytes(encoded)

    def invoke(self,connection,environ=None,address='8.8.8.8'):
        config=SpeechConfiguration('a'*32,'https://speech.example.test/v1/audio/transcriptions','synthetic-model','synthetic-never-transmitted-secret')
        with patch.dict(os.environ,environ or {},clear=True),patch('socket.getaddrinfo',return_value=[(2,1,6,'',(address,443))]), \
                patch('business_assistant_speech._PinnedHTTPS',return_value=connection) as direct, \
                patch('business_assistant_speech.http.client.HTTPSConnection',return_value=connection) as proxy:
            value=OpenAICompatibleSpeech().transcribe(config,wav(),'b'*32)
            return value,direct.call_count,proxy.call_count

    def test_documented_multipart_contract_contains_audio_no_project_sources_or_tools(self):
        connection=provider_fixture.Connection(b'{"text":"Synthetic speech"}')
        value,direct,proxy=self.invoke(connection)
        self.assertEqual((value,direct,proxy),('Synthetic speech',1,0))
        args,options=connection.requests[0]
        self.assertEqual(args,('POST','/v1/audio/transcriptions'))
        for field in (b'name="model"',b'name="language"',b'name="response_format"',b'filename="recording.wav"',wav()):
            self.assertIn(field,options['body'])
        self.assertNotIn(b'project_id',options['body']);self.assertNotIn(b'tools',options['body'])
        self.assertTrue(connection.closed)

    def test_mandatory_proxy_not_bypassed_and_private_provider_redirect_bad_text_rejected(self):
        connection=provider_fixture.Connection(b'{"text":"Synthetic speech"}')
        _,direct,proxy=self.invoke(connection,{'HTTPS_PROXY':'http://proxy.example.test:8080','NO_PROXY':'*'})
        self.assertEqual((direct,proxy),(0,1));self.assertEqual(connection.tunnels[0][0],('speech.example.test',443))
        with self.assertRaises(Problem):self.invoke(provider_fixture.Connection(b'{}'),address='127.0.0.1')
        for body in (b'{"text":"A","text":"B"}',b'{"text":NaN}',b'{"text":""}',json.dumps({'text':'x'*4001}).encode()):
            with self.subTest(body=body[:30]),self.assertRaises(Problem):self.invoke(provider_fixture.Connection(body))
        connection=provider_fixture.Connection(b'{"text":"Synthetic speech"}');connection.response.status=302
        with self.assertRaises(Problem):self.invoke(connection)
        self.assertEqual(len(connection.requests),1)
        connection=provider_fixture.Connection(b'{"text":"Synthetic speech"}')
        with self.assertRaises(Problem):self.invoke(connection,{'HTTPS_PROXY':'socks5://proxy.example.test'})
        self.assertEqual(connection.requests,[])


if __name__=='__main__':unittest.main()

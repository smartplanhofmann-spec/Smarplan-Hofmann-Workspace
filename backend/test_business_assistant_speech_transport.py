"""Actual local HTTP framing preserves speech-only size and JSON limits."""
import base64
from http.server import ThreadingHTTPServer
import json
import os
import threading
import unittest
from unittest.mock import patch

from onedrive import OneDrive
from server import make_handler
import test_business_assistant_speech as domain
import test_business_offline_reports_transport as local


class SpeechLocalHTTP(unittest.TestCase):
    call=local.OfflineReportLocalTransportTests.call

    def setUp(self):
        fixture=domain.SpeechDomain();fixture.setUp();self.addCleanup(fixture.doCleanups)
        self.fixture,self.office,self.transport=fixture,fixture.office,fixture.transport
        self.token=self.office.login('owner@example.test','Synthetic-owner-password')
        environment=patch.dict(os.environ,fixture.env);environment.start();self.addCleanup(environment.stop)
        transport=patch('business_assistant_speech.OpenAICompatibleSpeech',return_value=self.transport)
        transport.start();self.addCleanup(transport.stop)
        self.server=ThreadingHTTPServer(('127.0.0.1',0),make_handler(self.office,OneDrive(self.office)))
        worker=threading.Thread(target=self.server.serve_forever,daemon=True);worker.start()
        self.addCleanup(worker.join);self.addCleanup(self.server.server_close);self.addCleanup(self.server.shutdown)

    def test_full_minute_local_audio_and_narrow_strict_boundaries(self):
        body={**self.fixture.body,'audio_base64':base64.b64encode(domain.wav(960000)).decode()}
        path='/business/assistant/speech/transcribe'
        self.assertGreater(len(json.dumps(body)),1_000_000)
        self.assertEqual(self.call('POST',path,body)[0]['status'],'completed')
        self.call('POST',path,body,status=409)
        # Invalid framing is rejected from headers before reading the body.
        # Keep that body small so an early close cannot become BrokenPipe in
        # the client and hide the server's actual rejection response.
        self.call('POST',path,b'{}',headers={'Content-Length':'2600001'},status=413)
        self.call('POST','/business/assistant/chat',b'{}',headers={'Content-Length':'1000001'},status=413)
        for invalid in (b'{"request_id":"a","request_id":"b"}',b'{"x":NaN}'):
            self.call('POST',path,invalid,status=400)
        self.call('POST',path+'?unexpected=1',{},status=400)
        self.call('GET','/business/assistant/speech/requests/'+body['request_id'],{},status=400)
        self.assertEqual(len(self.transport.calls),1)
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM business_assistant_speech_requests').fetchone()[0],1)


if __name__=='__main__':unittest.main()

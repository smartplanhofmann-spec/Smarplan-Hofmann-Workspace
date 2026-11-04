"""Independent real two-process HTTP review; provider transports are local doubles.

Reuse the owner's actual host/MFA/instance/database fixture without discovering
its TestCase again. No external request, PostgreSQL or product monkeypatch beyond
the two provider transports and explicit synthetic process configuration.
"""
import base64
from contextlib import ExitStack
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import unittest
from unittest.mock import patch
import uuid

import online.test_company_isolation_current as fixture
from test_business_assistant_speech import wav


ORIGINAL_SERVE = fixture.serve_company


def serve_review_company(value, ports):
    from online.web import create_app
    log = Path(value['database']).with_suffix('.provider-calls.jsonl')

    def remember(kind, config, operation, **facts):
        assert config.instance_id == value['instance_id']
        with log.open('a') as output:
            output.write(json.dumps(dict(kind=kind, instance_id=config.instance_id,
                operation=operation, **facts)) + '\n')

    class LocalModel:
        def complete(self, config, context, message, operation):
            assert context['instance_id'] == value['instance_id']
            remember('chat', config, operation, context=context, message=message)
            sources = context['sources']
            return dict(summary=value['marker'] + ' local model answer',
                citations=[s['source_id'] for s in sources],
                facts=[dict(source_id=s['source_id'], path='name') for s in sources],
                proposals=[])

    class LocalSpeech:
        def transcribe(self, config, audio, operation):
            remember('speech', config, operation, audio_sha256=hashlib.sha256(audio).hexdigest())
            return value['marker'] + ' local transient dictation'

    def configured_app(**kwargs):
        identity = ('f' * 32 if os.environ.get('SMARTPLAN_REVIEW_PROVIDER_MISMATCH') == '1'
            and value['marker'] == 'ONLYBETA' else value['instance_id'])
        for prefix, endpoint in (
            ('SMARTPLAN_ASSISTANT_', 'https://never-called.example.test/v1/chat/completions'),
            ('SMARTPLAN_ASSISTANT_SPEECH_', 'https://never-called.example.test/v1/audio/transcriptions'),
        ):
            os.environ.update({prefix + 'ENABLED':'1', prefix + 'DATA_TRANSFER_APPROVED':'1',
                prefix + 'INSTANCE_ID':identity, prefix + 'ENDPOINT':endpoint,
                prefix + 'MODEL':'synthetic-local-review',
                prefix + 'API_KEY':'synthetic-never-transmitted-review-secret'})
        return create_app(**kwargs)

    with ExitStack() as stack:
        stack.enter_context(patch('online.web.create_app', side_effect=configured_app))
        stack.enter_context(patch('business_assistant.OpenAICompatibleModel', return_value=LocalModel()))
        stack.enter_context(patch('business_assistant_speech.OpenAICompatibleSpeech', return_value=LocalSpeech()))
        # Any unintended real provider transport is a test error, not a fallback.
        stack.enter_context(patch('http.client.HTTPSConnection.connect', side_effect=AssertionError('External HTTPS forbidden')))
        ORIGINAL_SERVE(value, ports)


class CompanyAssistantIsolationReview(fixture.CurrentCompanyScenario, unittest.TestCase):
    stop = fixture.CompanyIsolationCurrentHTTP.stop

    def setUp(self):
        mismatch = 'mismatched_provider' in self._testMethodName
        with patch.dict(os.environ, SMARTPLAN_REVIEW_PROVIDER_MISMATCH='1' if mismatch else '0'), \
                patch.object(fixture, 'serve_company', serve_review_company):
            fixture.CompanyIsolationCurrentHTTP.setUp(self)
        self.initialize_http()

    def context(self, company, *, token='owner'):
        self.catalog(company, request_id=uuid.uuid4().hex)
        article = self.call(company, '/business/articles?query=' + company['marker'])['items'][0]
        sources = self.call(company, '/business/assistant/sources?project_id=' + company['project'])
        self.assertIn(article['id'], [v['id'] for v in sources['items']])
        context = self.call(company, '/business/assistant/contexts', fixture.req(
            project_id=company['project'], sources=[dict(kind='project', id=company['project']),
                dict(kind='article', id=article['id'])]), token=token)
        self.assertEqual(context['instance_id'], company['instance_id'])
        company.update(article=article, context=context, search=sources)
        return context

    def calls(self, company):
        path = Path(company['database']).with_suffix('.provider-calls.jsonl')
        return [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []

    def speech_body(self, context, request_id):
        return dict(request_id=request_id, context_id=context['id'], data_transfer_confirmed=True,
            audio_base64=base64.b64encode(wav(1600)).decode())

    def test_actual_same_nonces_keep_search_chat_speech_and_original_sources_in_each_instance(self):
        chat_nonce, speech_nonce = uuid.uuid4().hex, uuid.uuid4().hex
        snapshots = []
        for company in self.companies:
            context = self.context(company)
            body = dict(request_id=chat_nonce, context_id=context['id'],
                message=company['marker'] + ' selected originals only', data_transfer_confirmed=True)
            chat = self.call(company, '/business/assistant/chat', body)
            self.assertEqual(chat['status'], 'completed')
            self.assertEqual(chat['provider']['instance_id'], company['instance_id'])
            self.assertEqual([f['value'] for f in chat['result']['facts']],
                [s['data']['name'] for s in context['sources']])
            self.assertEqual(self.call(company, '/business/assistant/chat', body), chat)
            speech_body = self.speech_body(context, speech_nonce)
            speech = self.call(company, '/business/assistant/speech/transcribe', speech_body)
            self.assertEqual(speech['text'], company['marker'] + ' local transient dictation')
            self.assertEqual(speech['context_sha256'], context['sha256'])
            self.call(company, '/business/assistant/speech/transcribe', speech_body, status=409)
            status = self.call(company, '/business/assistant/speech/requests/' + speech_nonce)
            self.assertNotIn('text', status)
            self.assertFalse(status['audio_persisted']); self.assertFalse(status['transcript_persisted'])
            self.assertEqual([v['kind'] for v in self.calls(company)], ['chat', 'speech'])
            company.update(chat=chat, chat_body=body, speech=speech, speech_body=speech_body, speech_status=status)
            snapshot = {key:company[key] for key in (
                'instance_id','marker','project','article','catalog','context','search','chat','speech','speech_status')}
            snapshot['capabilities'] = self.call(company, '/business/capabilities?project_id=' + company['project'])
            snapshot['me'] = self.call(company, '/me')
            snapshot['assistant_status'] = self.call(company, '/business/assistant/status?project_id=' + company['project'])
            snapshot['speech_provider_status'] = self.call(company, '/business/assistant/speech/status?project_id=' + company['project'])
            snapshot['rules'] = self.call(company, '/business/assistant/rules?project_id=' + company['project'])
            snapshot['plans'] = self.call(company, '/business/assistant/plans?project_id=' + company['project'])
            snapshot['chats'] = self.call(company, '/business/assistant/chat?project_id=' + company['project'])
            snapshots.append(snapshot)
        for own, foreign in (self.companies, self.companies[::-1]):
            self.call(own, '/business/assistant/chat/' + foreign['chat']['id'], status=404)
            self.call(own, '/business/assistant/chat', foreign['chat_body'], status=404)
            self.call(own, '/business/assistant/speech/transcribe', foreign['speech_body'], status=404)
            self.call(own, '/business/assistant/contexts', fixture.req(project_id=own['project'],
                sources=[dict(kind='article', id=foreign['article']['id'])]), status=404)
            self.call(own, '/business/assistant/sources?project_id=' + foreign['project'], status=404)
            self.assertEqual(self.call(own, '/business/assistant/sources?project_id=' + own['project'] +
                '&q=' + foreign['marker'])['items'], [])
            self.call(own, '/business/assistant/speech/requests/' + speech_nonce,
                token=foreign['token'], status=401)
            self.call(own, '/business/assistant/chat/' + own['chat']['id'], host=foreign['host'], status=400)
            self.assertEqual(self.call(own, '/business/assistant/speech/requests/' + speech_nonce)['context_id'],
                own['context']['id'])
            calls = self.calls(own)
            self.assertEqual(len(calls), 2)
            self.assertNotIn(foreign['marker'], json.dumps(calls))
            self.assertNotIn(foreign['instance_id'], json.dumps(calls))
            with sqlite3.connect('file:' + own['database'] + '?mode=ro', uri=True) as db:
                text = json.dumps([db.execute('SELECT * FROM ' + table).fetchall() for table in
                    ('business_assistant_speech_requests','business_assistant_speech_outcomes','audit')])
                self.assertNotIn(own['speech']['text'], text)
                self.assertNotIn(own['speech_body']['audio_base64'], text)
                self.assertNotIn('synthetic-never-transmitted-review-secret', text)
        target = os.environ.get('SMARTPLAN_ISOLATION_REVIEW_FIXTURE')
        if target:
            Path(target).write_text(json.dumps(dict(schema_version=1, synthetic_only=True,
                transport='local deterministic provider doubles; actual two HTTP/MFA/DB instances',
                companies=snapshots), ensure_ascii=False, indent=2) + '\n')

    def test_actual_catalog_source_right_revocation_closes_existing_chat_and_speech_in_only_one_company(self):
        for company in self.companies:
            self.context(company)
            reader = self.call(company, '/users', dict(email='same-assistant-reader@example.test',
                password=fixture.PASSWORD, role='accountant'), status=201)
            self.call(company, '/assignments', dict(project_id=company['project'], user_id=reader['id']))
            self.call(company, '/business/settings/permissions', fixture.req(user_id=reader['id'],
                permission='assistant.use', scope='*', effect='allow', revision=0))
            token = self.login(company, email='same-assistant-reader@example.test')
            context = self.call(company, '/business/assistant/contexts', fixture.req(project_id=company['project'],
                sources=[dict(kind='article', id=company['article']['id'])]), token=token)
            chat_body = fixture.req(context_id=context['id'], message='Synthetic selected article', data_transfer_confirmed=True)
            chat = self.call(company, '/business/assistant/chat', chat_body, token=token)
            speech_body = self.speech_body(context, uuid.uuid4().hex)
            self.call(company, '/business/assistant/speech/transcribe', speech_body, token=token)
            company.update(reader=reader, reader_token=token, reader_context=context,
                reader_chat=chat, reader_chat_body=chat_body, reader_speech_body=speech_body)
        own, other = self.companies
        self.call(own, '/business/settings/permissions', fixture.req(user_id=own['reader']['id'],
            permission='finance.read', scope='*', effect='deny', revision=0))
        caps = self.call(own, '/business/capabilities?project_id=' + own['project'], token=own['reader_token'])
        self.assertIn('assistant.use', caps['permissions']); self.assertNotIn('finance.read', caps['permissions'])
        search = self.call(own, '/business/assistant/sources?project_id=' + own['project'], token=own['reader_token'])
        self.assertNotIn(own['article']['id'], [v['id'] for v in search['items']])
        for path, body in (
            ('/business/assistant/contexts/' + own['reader_context']['id'], None),
            ('/business/assistant/chat/' + own['reader_chat']['id'], None),
            ('/business/assistant/chat', own['reader_chat_body']),
            ('/business/assistant/speech/requests/' + own['reader_speech_body']['request_id'], None),
            ('/business/assistant/speech/transcribe', self.speech_body(own['reader_context'], uuid.uuid4().hex)),
        ):
            self.call(own, path, body, token=own['reader_token'], status=403)
        self.assertEqual(len(self.calls(own)), 2)
        self.assertEqual(self.call(other, '/business/assistant/chat/' + other['reader_chat']['id'],
            token=other['reader_token']), other['reader_chat'])
        self.assertEqual(self.call(other, '/business/assistant/speech/requests/' + other['reader_speech_body']['request_id'],
            token=other['reader_token'])['status'], 'completed')

    def test_actual_mismatched_provider_company_configuration_blocks_both_transports(self):
        own, wrong = self.companies
        for company in self.companies:
            context = self.context(company)
            expected = company is own
            self.assertEqual(self.call(company, '/business/assistant/status?project_id=' + company['project'])['provider']['configured'], expected)
            self.assertEqual(self.call(company, '/business/assistant/speech/status?project_id=' + company['project'])['provider']['configured'], expected)
            if not expected:
                self.call(company, '/business/assistant/chat', fixture.req(context_id=context['id'],
                    message='Synthetic forbidden provider attempt', data_transfer_confirmed=True), status=409)
                self.call(company, '/business/assistant/speech/transcribe', self.speech_body(context, uuid.uuid4().hex), status=409)
                self.assertEqual(self.calls(company), [])
        self.assertNotEqual(own['instance_id'], wrong['instance_id'])


if __name__ == '__main__':
    unittest.main()

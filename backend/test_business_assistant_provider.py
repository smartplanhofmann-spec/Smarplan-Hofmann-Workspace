"""Model protocol and mandatory egress behavior without any network request."""
import json
import os
import unittest
from unittest.mock import patch

from business_assistant_provider import ModelConfiguration, OpenAICompatibleModel, SYSTEM, configuration
from core import Problem
import test_business_assistant as domain_fixture
from test_business_assistant import SyntheticModelForTests


class Response:
    status = 200
    def __init__(self, body): self.body = body
    def getheader(self, name, default=''):
        return 'application/json' if name == 'Content-Type' else default
    def read1(self, size):
        value, self.body = self.body[:size], self.body[size:]
        return value


class Connection:
    sock = None
    def __init__(self, body):
        self.response, self.requests, self.tunnels, self.closed = Response(body), [], [], False
    def set_tunnel(self, *args, **kwargs): self.tunnels.append((args, kwargs))
    def request(self, *args, **kwargs): self.requests.append((args, kwargs))
    def getresponse(self): return self.response
    def close(self): self.closed = True


class ModelProviderTests(unittest.TestCase):
    def config(self):
        return ModelConfiguration('a'*32, 'https://model.example.test/v1/chat/completions',
            'synthetic-protocol', 'synthetic-never-transmitted-secret')

    def encoded(self, **changes):
        answer = dict(summary='Source selection', citations=['project:'+'b'*32], facts=[], proposals=[])
        message = dict(role='assistant', content=json.dumps(answer))
        message.update(changes)
        return json.dumps(dict(choices=[dict(finish_reason='stop', message=message)])).encode()

    def invoke(self, connection, environ=None):
        with patch.dict(os.environ, environ or {}, clear=True), patch('socket.getaddrinfo', return_value=[(2,1,6,'',('8.8.8.8',443))]), \
                patch('business_assistant_provider._PinnedHTTPS', return_value=connection) as direct, \
                patch('business_assistant_provider.http.client.HTTPSConnection', return_value=connection) as proxy:
            result = OpenAICompatibleModel().complete(self.config(), dict(sources=[],facts={},available_actions=[]), 'Synthetic question', 'c'*32)
            return result, direct.call_count, proxy.call_count

    def test_direct_transport_has_no_tools_and_uses_source_data_as_user_content(self):
        connection = Connection(self.encoded())
        result, direct, proxy = self.invoke(connection)
        self.assertEqual((direct,proxy), (1,0))
        self.assertEqual(result['summary'], 'Source selection')
        arguments, options = connection.requests[0]
        self.assertEqual(arguments, ('POST','/v1/chat/completions'))
        request = json.loads(options['body'])
        self.assertEqual(request['messages'][0], dict(role='system',content=SYSTEM))
        self.assertEqual(request['messages'][1]['role'], 'user')
        self.assertFalse(request['stream'])
        self.assertNotIn('tools',request)
        self.assertNotIn('synthetic-never-transmitted-secret', options['body'].decode())
        self.assertTrue(connection.closed)
        self.assertNotIn('synthetic-never-transmitted-secret',repr(self.config()))

    def test_configured_proxy_is_mandatory_even_when_no_proxy_names_target(self):
        connection = Connection(self.encoded())
        _, direct, proxy = self.invoke(connection, {'HTTPS_PROXY':'http://proxy.example.test:8080', 'NO_PROXY':'*'})
        self.assertEqual((direct,proxy), (0,1))
        self.assertEqual(connection.tunnels[0][0], ('model.example.test',443))

    def test_private_provider_address_is_rejected_before_any_connection(self):
        with patch.dict(os.environ,{},clear=True), patch('socket.getaddrinfo', return_value=[(2,1,6,'',('127.0.0.1',443))]), patch('business_assistant_provider._PinnedHTTPS') as connection:
            with self.assertRaises(Problem) as rejected:
                OpenAICompatibleModel().complete(self.config(),dict(sources=[],facts={},available_actions=[]),'Synthetic', 'c'*32)
            self.assertEqual(rejected.exception.status,502)
            connection.assert_not_called()

    def test_unavailable_proxy_never_falls_back_to_direct_connection(self):
        connection = Connection(self.encoded())
        with self.assertRaises(Problem):
            self.invoke(connection, {'HTTPS_PROXY':'socks5://proxy.example.test:1080'})
        self.assertEqual(connection.requests,[])

    def test_redirect_duplicate_keys_and_provider_tools_are_not_accepted(self):
        for connection in (Connection(self.encoded(tool_calls=[dict(type='function',function=dict(name='send_mail',arguments='{}'))])),
                Connection(b'{"choices":[],"choices":[]}')):
            with self.assertRaises(Problem) as error:
                self.invoke(connection)
            self.assertEqual(error.exception.status,502)
            self.assertTrue(connection.closed)
        redirected = Connection(self.encoded()); redirected.response.status=302
        with self.assertRaises(Problem): self.invoke(redirected)
        self.assertEqual(len(redirected.requests),1)


class ModelConfigurationTests(unittest.TestCase):
    setUp = domain_fixture.AssistantTests.setUp
    bind_model = domain_fixture.AssistantTests.bind_model

    def test_provider_is_bound_to_instance_and_explicit_data_transfer_without_exposing_secret(self):
        self.bind_model(SyntheticModelForTests())
        current = configuration(self.office)
        self.assertEqual(current.public()['model'],'synthetic-protocol-test')
        self.assertNotIn('secret',json.dumps(current.public()))
        for change in ({'SMARTPLAN_ASSISTANT_INSTANCE_ID':'f'*32}, {'SMARTPLAN_ASSISTANT_DATA_TRANSFER_APPROVED':'0'},
                       {'SMARTPLAN_ASSISTANT_ENDPOINT':'http://model.example.test/v1/chat/completions'},
                       {'SMARTPLAN_ASSISTANT_ENDPOINT':'https://user:password@model.example.test/v1/chat/completions'},
                       {'SMARTPLAN_ASSISTANT_ENABLED':'0'}):
            with patch.dict(os.environ,change), self.assertRaises(Problem) as error:
                configuration(self.office)
            self.assertEqual(error.exception.status,409)


if __name__ == '__main__': unittest.main()

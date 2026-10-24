"""Synthetic HTTP responses exercise the actual bounded transport, without IO."""
from io import BytesIO
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from http.client import HTTPConnection
from datetime import datetime, timedelta, timezone
import ipaddress
import json
from pathlib import Path
import socket
import ssl
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, ProxyHandler, HTTPHandler, build_opener

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID, ExtendedKeyUsageOID

from core import Problem
from online.integration_http import (IntegrationHttp, integration_deadline, _NoRedirect,
    IntegrationAuthenticationRequired, IntegrationPermissionDenied, _DeadlineConnection,
    _DeadlineHTTPSHandler)


class Response(BytesIO):
    status = 200

    def __init__(self, body=b'{}', *, status=200, headers=None):
        super().__init__(body)
        self.status = status
        self.headers = {"Content-Type": "application/json", **(headers or {})}


class Opener:
    def __init__(self, *responses):
        self.responses = list(responses)
        self.requests = []

    def open(self, request, *, timeout):
        self.requests.append((request, timeout))
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


class TransportTests(unittest.TestCase):
    def assert_problem(self, status, callback):
        with self.assertRaises(Problem) as caught:
            callback()
        self.assertEqual(status, caught.exception.status)
        self.assertNotIn("SYNTHETIC_SECRET", caught.exception.message)
        return caught.exception

    def test_fixed_get_and_encoded_query_keep_token_only_in_header(self):
        opener = Opener(Response(b'{"objects":[]}'))
        client = IntegrationHttp("sevdesk", opener=opener)
        self.assertEqual({"objects": []}, client.call("/Invoice", params={"contact[id]": "42"}, headers={"Authorization": "SYNTHETIC_SECRET"}))
        request, timeout = opener.requests[0]
        self.assertEqual("https://my.sevdesk.de/api/v1/Invoice?contact%5Bid%5D=42", request.full_url)
        self.assertEqual("SYNTHETIC_SECRET", request.get_header("Authorization"))
        self.assertEqual("GET", request.get_method())
        self.assertLessEqual(timeout, 8)

    def test_destinations_write_endpoints_and_embedded_secrets_are_rejected_before_io(self):
        opener = Opener()
        client = IntegrationHttp("sevdesk", opener=opener)
        cases = [lambda: client.call("https://attacker.invalid/Invoice"),
                 lambda: client.call("//my.sevdesk.de/Invoice"),
                 lambda: client.call("/Invoice/1/getPdf"),
                 lambda: client.call("/Invoice/1/changeStatus"),
                 lambda: client.call("/Invoice", method="POST", json_body={}),
                 lambda: client.call("/Contact?limit=1"),
                 lambda: client.call("/Contact", params={"access_token": "SYNTHETIC_SECRET"}),
                 lambda: client.call("/Contact", headers={"Authorization": "SYNTHETIC_SECRET\r\nHost: evil"})]
        for case in cases:
            self.assert_problem(400, case)
        self.assertEqual([], opener.requests)

    def test_google_path_encoding_and_separate_oauth_form(self):
        opener = Opener(Response(), Response(b'{"access_token":"synthetic"}'))
        client = IntegrationHttp("google_calendar", opener=opener)
        client.call("/calendar/v3/calendars/a%40example.invalid/events/event%23one")
        result = client.call("https://oauth2.googleapis.com/token", method="POST",
                             form={"grant_type": "authorization_code", "code": "synthetic code"})
        self.assertEqual("synthetic", result["access_token"])
        self.assertEqual(b"grant_type=authorization_code&code=synthetic+code", opener.requests[1][0].data)
        self.assertEqual("application/x-www-form-urlencoded", opener.requests[1][0].get_header("Content-type"))
        self.assert_problem(400, lambda: client.call("https://oauth2.googleapis.com/token/", method="POST", form={}))
        self.assert_problem(400, lambda: client.call("/calendar/v3/calendars/x/events", method="POST", json_body={}))
        self.assert_problem(400, lambda: client.call("/calendar/v3/calendars/%2e%2e/events"))

    def test_unknown_provider_or_unneeded_direct_cloud_route_is_not_available(self):
        for provider in ('dropbox','onedrive','unknown'):
            with self.assertRaises(ValueError):
                IntegrationHttp(provider, opener=Opener())
        client=IntegrationHttp('google_calendar',opener=Opener())
        self.assert_problem(400,lambda:client.call('https://graph.microsoft.com/v1.0/me/drive/root'))

    def test_http_errors_are_sanitized_and_oauth400_requires_reconnect(self):
        for upstream, expected in [(401,409), (403,409), (429,429), (500,503), (302,503), (404,404), (410,404)]:
            with self.subTest(upstream=upstream):
                error = HTTPError("https://secret.invalid/SYNTHETIC_SECRET", upstream, "SYNTHETIC_SECRET", {}, BytesIO(b"SYNTHETIC_SECRET"))
                self.assert_problem(expected, lambda: IntegrationHttp("sevdesk", opener=Opener(error)).call("/Contact"))
                self.assertTrue(error.fp is None or error.fp.closed)
        error = HTTPError("https://oauth2.googleapis.com/token", 400, "SYNTHETIC_SECRET", {}, BytesIO(b'{"error":"invalid_grant","error_description":"SYNTHETIC_SECRET"}'))
        self.assert_problem(409, lambda: IntegrationHttp("google_calendar", opener=Opener(error)).call("https://oauth2.googleapis.com/token", method="POST", form={"code":"synthetic"}))
        error = HTTPError("https://www.googleapis.com/calendar/v3/users/me/calendarList", 400, "SYNTHETIC_SECRET", {}, BytesIO())
        self.assert_problem(503, lambda: IntegrationHttp("google_calendar", opener=Opener(error)).call("/calendar/v3/users/me/calendarList"))

    def test_only_confirmed_authentication_errors_invalidate_global_connection(self):
        for status, body, expected in [(401,b"",IntegrationAuthenticationRequired),
                                       (403,b"",IntegrationPermissionDenied),
                                       (400,b'{"error":"invalid_client"}',IntegrationAuthenticationRequired),
                                       (400,b'{"error":"unauthorized_client"}',IntegrationAuthenticationRequired)]:
            error = HTTPError("https://oauth2.googleapis.com/token", status, "secret", {}, BytesIO(body))
            with self.assertRaises(expected):
                IntegrationHttp("google_calendar", opener=Opener(error)).call("https://oauth2.googleapis.com/token", method="POST", form={})
        for body in [b'{"error":"invalid_request"}', b"invalid_grant", b'{"description":"invalid_grant"}', b'{"error":"invalid_grant","padding":"'+b'x'*8192+b'"}']:
            error = HTTPError("https://oauth2.googleapis.com/token", 400, "secret", {}, BytesIO(body))
            self.assert_problem(503, lambda: IntegrationHttp("google_calendar", opener=Opener(error)).call("https://oauth2.googleapis.com/token", method="POST", form={}))

    def test_no_redirect_handler_never_constructs_redirect_request(self):
        self.assertIsNone(_NoRedirect().redirect_request(None, None, 302, "found", {}, "https://evil.invalid"))

    def test_bad_content_type_json_constants_depth_and_top_level_fail_closed(self):
        for body, headers in [(b'{"v":NaN}',{}), (b'{"v":Infinity}',{}), (b'{"v":1e999}',{}), (b'{"id":1,"id":2}',{}), (b'<html>secret</html>',{"Content-Type":"text/html"}),
                              (b'"value"',{}), (b'\xff',{}), (b'['*1500+b']'*1500,{})]:
            response = Response(body, headers=headers)
            self.assert_problem(503, lambda: IntegrationHttp("sevdesk", opener=Opener(response)).call("/Contact"))
            self.assertTrue(response.closed)

    def test_streamed_and_advertised_length_cannot_exceed_limit_or_truncate(self):
        for body, headers in [(b"x"*33,{}), (b"",{"Content-Length":"33"}), (b"abc",{"Content-Length":"4"}), (b"",{"Content-Length":"-1"})]:
            response = Response(body, headers=headers)
            self.assert_problem(503, lambda: IntegrationHttp("sevdesk", opener=Opener(response)).raw("/Contact", max_bytes=32))
            self.assertTrue(response.closed)
        self.assert_problem(400, lambda: IntegrationHttp("sevdesk", opener=Opener()).raw("/Contact", max_bytes=20*1024*1024+1))

    def test_shared_deadline_covers_multiple_calls_and_limits_open_timeout(self):
        opener = Opener(Response(), Response())
        with patch("online.integration_http.time.monotonic", return_value=100):
            with integration_deadline(18):
                client = IntegrationHttp("sevdesk", opener=opener)
                with patch("online.integration_http.time.monotonic", return_value=112):
                    client.call("/Contact")
                self.assertEqual(6, opener.requests[0][1])
                with patch("online.integration_http.time.monotonic", return_value=119):
                    self.assert_problem(504, lambda: client.call("/Contact"))
        self.assertEqual(1, len(opener.requests))

    def test_socket_timeout_and_network_failure_have_no_provider_details(self):
        self.assert_problem(504, lambda: IntegrationHttp("sevdesk", opener=Opener(socket.timeout("SYNTHETIC_SECRET"))).call("/Contact"))
        self.assert_problem(503, lambda: IntegrationHttp("sevdesk", opener=Opener(URLError("SYNTHETIC_SECRET"))).call("/Contact"))
        self.assert_problem(504, lambda: IntegrationHttp("sevdesk", opener=Opener(URLError(socket.timeout("SYNTHETIC_SECRET")))).call("/Contact"))

    def test_slow_drip_http_headers_obey_total_deadline_not_only_idle_timeout(self):
        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                try:
                    self.wfile.write(b"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nX-Slow: ")
                    self.wfile.flush()
                    for _ in range(30):
                        self.wfile.write(b"x")
                        self.wfile.flush()
                        time.sleep(0.04)
                    self.wfile.write(b"\r\nContent-Length: 2\r\n\r\n{}")
                except (BrokenPipeError, ConnectionResetError):
                    pass

            def log_message(self, *args):
                pass

        class BoundedConnection(_DeadlineConnection, HTTPConnection):
            pass

        class BoundedHandler(HTTPHandler):
            def http_open(self, request):
                return self.do_open(lambda host, **kwargs: BoundedConnection(
                    host, endpoint=request.smartplan_deadline, **kwargs), request)

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        local_opener = build_opener(ProxyHandler({}), _NoRedirect(), BoundedHandler())

        class SyntheticOpener:
            def open(self, request, *, timeout):
                parts = urlsplit(request.full_url)
                assert parts.scheme == "https" and parts.netloc == "my.sevdesk.de"
                target = Request("http://127.0.0.1:" + str(server.server_port) + parts.path)
                target.smartplan_deadline = request.smartplan_deadline
                return local_opener.open(target, timeout=timeout)

        try:
            started = time.monotonic()
            with integration_deadline(0.18):
                self.assert_problem(504, lambda: IntegrationHttp("sevdesk", opener=SyntheticOpener()).call("/Contact"))
            self.assertLess(time.monotonic() - started, 0.9)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=3)

    def test_real_loopback_http_framing_and_redirect_rejection_without_provider_contact(self):
        received = []

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                received.append((self.path, self.headers.get("Authorization")))
                if self.path == "/api/v1/Contact":
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(b'{"objects":[]}')
                else:
                    self.send_response(302)
                    self.send_header("Location", "/must-never-be-followed")
                    self.end_headers()

            def log_message(self, *args):
                pass

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()

        class BoundedConnection(_DeadlineConnection, HTTPConnection):
            pass

        class BoundedHandler(HTTPHandler):
            def http_open(self, request):
                return self.do_open(lambda host, **kwargs: BoundedConnection(
                    host, endpoint=request.smartplan_deadline, **kwargs), request)

        local_opener = build_opener(ProxyHandler({}), _NoRedirect(), BoundedHandler())

        class SyntheticOpener:
            def open(self, request, *, timeout):
                parts = urlsplit(request.full_url)
                assert parts.scheme == "https" and parts.netloc == "my.sevdesk.de"
                target = "http://127.0.0.1:" + str(server.server_port) + parts.path
                outgoing = Request(target, headers=dict(request.header_items()), method=request.method)
                outgoing.smartplan_deadline = request.smartplan_deadline
                return local_opener.open(outgoing, timeout=timeout)

        try:
            client = IntegrationHttp("sevdesk", opener=SyntheticOpener())
            self.assertEqual({"objects": []}, client.call("/Contact", headers={"Authorization":"synthetic-only"}))
            self.assert_problem(503, lambda: client.call("/Invoice"))
            self.assertEqual([("/api/v1/Contact", "synthetic-only"), ("/api/v1/Invoice", None)], received)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=3)

    def test_real_tls_verified_ca_hostname_chunked_body_and_no_redirect_with_deadline_handler(self):
        received=[]

        class Handler(BaseHTTPRequestHandler):
            protocol_version='HTTP/1.1'

            def do_GET(self):
                received.append((self.path,self.headers.get('Authorization')))
                if self.path=='/api/v1/Contact':
                    self.send_response(200)
                    self.send_header('Content-Type','application/json')
                    self.send_header('Transfer-Encoding','chunked')
                    self.end_headers()
                    for chunk in (b'{"objects":',b'[]}'):
                        self.wfile.write(format(len(chunk),'x').encode()+b'\r\n'+chunk+b'\r\n')
                    self.wfile.write(b'0\r\n\r\n');self.wfile.flush()
                else:
                    self.send_response(302)
                    self.send_header('Location','https://must-never-be-contacted.invalid')
                    self.send_header('Content-Length','0')
                    self.end_headers()

            def log_message(self,*args):
                pass

        now=datetime.now(timezone.utc)
        ca_key=rsa.generate_private_key(public_exponent=65537,key_size=2048)
        ca_name=x509.Name([x509.NameAttribute(NameOID.COMMON_NAME,'Synthetic Smartplan Test CA')])
        ca=(x509.CertificateBuilder().subject_name(ca_name).issuer_name(ca_name)
            .public_key(ca_key.public_key()).serial_number(x509.random_serial_number())
            .not_valid_before(now-timedelta(days=1)).not_valid_after(now+timedelta(days=1))
            .add_extension(x509.BasicConstraints(ca=True,path_length=0),critical=True)
            .add_extension(x509.KeyUsage(digital_signature=True,content_commitment=False,key_encipherment=False,
                data_encipherment=False,key_agreement=False,key_cert_sign=True,crl_sign=True,
                encipher_only=None,decipher_only=None),critical=True)
            .add_extension(x509.SubjectKeyIdentifier.from_public_key(ca_key.public_key()),critical=False)
            .sign(ca_key,hashes.SHA256()))
        key=rsa.generate_private_key(public_exponent=65537,key_size=2048)
        certificate=(x509.CertificateBuilder()
            .subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME,'localhost')])).issuer_name(ca_name)
            .public_key(key.public_key()).serial_number(x509.random_serial_number())
            .not_valid_before(now-timedelta(days=1)).not_valid_after(now+timedelta(days=1))
            .add_extension(x509.BasicConstraints(ca=False,path_length=None),critical=True)
            .add_extension(x509.SubjectAlternativeName([x509.DNSName('localhost'),x509.IPAddress(ipaddress.ip_address('127.0.0.1'))]),critical=False)
            .add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH]),critical=False)
            .add_extension(x509.AuthorityKeyIdentifier.from_issuer_public_key(ca_key.public_key()),critical=False)
            .sign(ca_key,hashes.SHA256()))
        with tempfile.TemporaryDirectory(prefix='smartplan-tls-fixture-') as directory:
            base=Path(directory)
            (base/'ca.pem').write_bytes(ca.public_bytes(serialization.Encoding.PEM))
            (base/'server.pem').write_bytes(certificate.public_bytes(serialization.Encoding.PEM))
            (base/'server.key').write_bytes(key.private_bytes(serialization.Encoding.PEM,
                serialization.PrivateFormat.PKCS8,serialization.NoEncryption()))
            (base/'server.key').chmod(0o600)
            server_context=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            server_context.load_cert_chain(base/'server.pem',base/'server.key')
            server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
            server.socket=server_context.wrap_socket(server.socket,server_side=True)
            thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
            trusted=ssl.create_default_context(cafile=str(base/'ca.pem'))
            self.assertEqual(ssl.CERT_REQUIRED,trusted.verify_mode)
            self.assertTrue(trusted.check_hostname)
            opener=build_opener(ProxyHandler({}),_NoRedirect(),_DeadlineHTTPSHandler(context=trusted))
            untrusted=build_opener(ProxyHandler({}),_NoRedirect(),_DeadlineHTTPSHandler(context=ssl.create_default_context()))
            try:
                with patch.dict('online.integration_http._ROOTS',{'sevdesk':'https://127.0.0.1:'+str(server.server_port)+'/api/v1'}):
                    client=IntegrationHttp('sevdesk',opener=opener)
                    with integration_deadline(5):
                        self.assertEqual({'objects':[]},client.call('/Contact',headers={'Authorization':'synthetic-tls-only'}))
                        self.assert_problem(503,lambda:client.call('/Invoice'))
                    self.assert_problem(503,lambda:IntegrationHttp('sevdesk',opener=untrusted).call('/Contact'))
                self.assertEqual([('/api/v1/Contact','synthetic-tls-only'),('/api/v1/Invoice',None)],received)
            finally:
                server.shutdown();server.server_close();thread.join(timeout=3)


if __name__ == "__main__":
    unittest.main()

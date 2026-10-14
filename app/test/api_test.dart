import 'dart:convert';
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:smartplan_office/api.dart';

class RealHttp extends HttpOverrides {}

void main() {
  Future<void> withServer(
    Future<void> Function(HttpServer server, OfficeApi api) check,
  ) => HttpOverrides.runWithHttpOverrides(() async {
    final server = await HttpServer.bind(InternetAddress.loopbackIPv4, 0);
    final api = OfficeApi(baseUrl: 'http://127.0.0.1:${server.port}');
    try {
      await check(server, api);
    } finally {
      api.dispose();
      await server.close(force: true);
    }
  }, RealHttp());

  test(
    'JSON requests preserve UTF-8, bearer token and POST body',
    () => withServer((server, api) async {
      api.token = 'test-bearer';
      int? declaredLength;
      String? transferEncoding;
      final body = {'description': 'Geräte geprüft'};
      server.listen((request) async {
        declaredLength = request.contentLength;
        transferEncoding = request.headers.value('Transfer-Encoding');
        expect(request.method, 'POST');
        expect(request.headers.value('Authorization'), 'Bearer test-bearer');
        expect(request.headers.contentType?.mimeType, 'application/json');
        expect(jsonDecode(await utf8.decoder.bind(request).join()), {
          'description': 'Geräte geprüft',
        });
        request.response.headers.contentType = ContentType.json;
        request.response.write(jsonEncode({'name': 'Büro'}));
        await request.response.close();
      });
      expect(await api.call('/api/projects', body), {'name': 'Büro'});
      expect(declaredLength, utf8.encode(jsonEncode(body)).length);
      expect(transferEncoding, isNull);
    }),
  );

  test(
    'PDF request returns original binary bytes, not decoded JSON',
    () => withServer((server, api) async {
      final bytes = <int>[...ascii.encode('%PDF-1.7\n'), 0, 128, 255];
      server.listen((request) async {
        expect(request.uri.path, '/api/reports/report-1/pdf');
        request.response.headers.contentType = ContentType(
          'application',
          'pdf',
        );
        request.response.add(bytes);
        await request.response.close();
      });
      expect(await api.pdf('report-1'), bytes);
    }),
  );

  test(
    'A non-PDF response is rejected before preview or saving',
    () => withServer((server, api) async {
      server.listen((request) async {
        request.response.headers.contentType = ContentType.json;
        request.response.write('{"status":"ok"}');
        await request.response.close();
      });
      await expectLater(api.pdf('report-1'), throwsA(isA<ApiException>()));
    }),
  );

  test(
    'Unauthorized response clears session and notifies the UI',
    () => withServer((server, api) async {
      api.token = 'expired';
      var notifications = 0;
      api.addListener(() => notifications++);
      server.listen((request) async {
        request.response.statusCode = 401;
        request.response.headers.contentType = ContentType.json;
        request.response.write('{"error":"Bitte anmelden"}');
        await request.response.close();
      });
      await expectLater(
        api.call('/api/me'),
        throwsA(isA<ApiException>().having((e) => e.status, 'status', 401)),
      );
      expect(api.token, isNull);
      expect(notifications, 1);
    }),
  );

  test(
    'Redirects are refused rather than forwarding authentication',
    () => withServer((server, api) async {
      api.token = 'test-bearer';
      var requests = 0;
      server.listen((request) async {
        requests++;
        request.response.statusCode = 302;
        request.response.headers.set('Location', '/other');
        await request.response.close();
      });
      await expectLater(
        api.call('/api/projects'),
        throwsA(isA<ApiException>()),
      );
      expect(requests, 1);
    }),
  );

  test('Remote cleartext HTTP is rejected before connecting', () async {
    final api = OfficeApi(baseUrl: 'http://example.invalid');
    try {
      await expectLater(
        api.call('/api/projects'),
        throwsA(
          isA<ApiException>().having(
            (e) => e.message,
            'message',
            contains('HTTPS'),
          ),
        ),
      );
    } finally {
      api.dispose();
    }
  });
}

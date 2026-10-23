import 'dart:async';
import 'dart:convert';
import 'dart:io';
import 'dart:typed_data';

import 'package:flutter_test/flutter_test.dart';
import 'package:smartplan_office/api.dart';

import 'backend_integration_test.dart' show BackendHttp;

void main() {
  test(
    'Binary transport sends exact bounded chunks with bearer and API version',
    () async {
      await HttpOverrides.runWithHttpOverrides(() async {
        final server = await HttpServer.bind(InternetAddress.loopbackIPv4, 0);
        final seen = Completer<List<int>>();
        final listener = server.listen((request) async {
          expect(
            request.uri.path,
            '/api/v1/projects/p/plan-imports/i/chunks/0',
          );
          expect(request.method, 'PUT');
          expect(
            request.headers.value('authorization'),
            'Bearer synthetic-token',
          );
          expect(
            request.headers.contentType?.mimeType,
            'application/octet-stream',
          );
          expect(request.contentLength, 262144);
          final bytes = await request.fold<List<int>>(
            [],
            (a, b) => a..addAll(b),
          );
          seen.complete(bytes);
          request.response.headers.contentType = ContentType.json;
          request.response.write('{"status":"uploading"}');
          await request.response.close();
        });
        final api = OfficeApi(
          baseUrl: 'http://127.0.0.1:${server.port}',
          apiVersion: 'v1',
        )..token = 'synthetic-token';
        try {
          final chunk = Uint8List.fromList(
            List.generate(262144, (i) => i % 251),
          );
          final response = await api.putChunk(
            '/api/projects/p/plan-imports/i/chunks/0',
            chunk,
          );
          expect(response['status'], 'uploading');
          expect(await seen.future, chunk);
          await expectLater(
            api.putChunk('/api/test', Uint8List(262145)),
            throwsA(isA<ApiException>().having((e) => e.status, 'status', 400)),
          );
          await expectLater(
            api.putChunk('/api/test', Uint8List(0)),
            throwsA(isA<ApiException>().having((e) => e.status, 'status', 400)),
          );
        } finally {
          api.dispose();
          await listener.cancel();
          await server.close(force: true);
        }
      }, BackendHttp());
    },
  );

  test('Downloads enforce content type, size and redirect isolation', () async {
    await HttpOverrides.runWithHttpOverrides(() async {
      final server = await HttpServer.bind(InternetAddress.loopbackIPv4, 0);
      var redirectedRequests = 0;
      final listener = server.listen((request) async {
        switch (request.uri.path) {
          case '/valid':
            request.response.headers.contentType = ContentType('image', 'png');
            request.response.add([137, 80, 78, 71]);
          case '/wrong':
            request.response.headers.contentType = ContentType.html;
            request.response.write('<html>Not a source</html>');
          case '/large':
            request.response.headers.contentType = ContentType('image', 'png');
            request.response.add(List.filled(65, 1));
          case '/redirect':
            request.response.statusCode = 302;
            request.response.headers.set('Location', '/target');
          case '/target':
            redirectedRequests++;
          case '/denied':
            request.response.statusCode = 403;
            request.response.headers.contentType = ContentType.json;
            request.response.write(
              jsonEncode({'error': 'Projekt nicht freigegeben'}),
            );
        }
        await request.response.close();
      });
      final api = OfficeApi(baseUrl: 'http://127.0.0.1:${server.port}')
        ..token = 'synthetic-token';
      try {
        expect(await api.bytes('/valid', mediaType: 'image/png'), [
          137,
          80,
          78,
          71,
        ]);
        for (final path in ['/wrong', '/large', '/redirect']) {
          await expectLater(
            api.bytes(path, mediaType: 'image/png', maxBytes: 64),
            throwsA(isA<ApiException>().having((e) => e.status, 'status', 0)),
          );
        }
        expect(redirectedRequests, 0);
        await expectLater(
          api.bytes('/denied', mediaType: 'image/png'),
          throwsA(isA<ApiException>().having((e) => e.status, 'status', 403)),
        );
      } finally {
        api.dispose();
        await listener.cancel();
        await server.close(force: true);
      }
    }, BackendHttp());
  });
}

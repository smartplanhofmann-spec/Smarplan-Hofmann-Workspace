@Tags(['posix_backend'])
library;

import 'dart:async';
import 'dart:convert';
import 'dart:io';
import 'dart:typed_data';

import 'package:flutter_test/flutter_test.dart';
import 'package:smartplan_office/api.dart';
import 'package:smartplan_office/business_catalog_prices.dart';
import 'package:smartplan_office/business_session.dart';

import 'business_catalog_prices_test.dart';
import 'backend_integration_test.dart' show BackendHttp;
import 'import_backend_integration_test.dart' show fixture;

class PriceHttpApi extends OfficeApi {
  PriceHttpApi(String base) : super(baseUrl: base, apiVersion: 'v1');
  final sent = <Map<String, dynamic>>[];
  bool dropStage = true, dropApply = true, dropDocument = true;
  @override
  Future<dynamic> call(String path, [Map<String, dynamic>? body]) async {
    final result = await super.call(path, body);
    if (body != null) sent.add({'path': path, 'body': priceCopy(body)});
    if (body != null &&
        path.contains('/catalog-prices/sources/') &&
        path.endsWith('/imports') &&
        dropStage) {
      dropStage = false;
      throw const ApiException(0, 'Synthetic lost stage ACK');
    }
    if (path.endsWith('/apply') && dropApply) {
      dropApply = false;
      throw const ApiException(0, 'Synthetic lost acceptance ACK');
    }
    if (body != null && path.endsWith('/documents') && dropDocument) {
      dropDocument = false;
      throw const ApiException(0, 'Synthetic lost document ACK');
    }
    return result;
  }
}

Map<String, dynamic> newDecisions(Map<String, dynamic> run) => {
  'expected_source_version': run['current_source_version'],
  'bindings': {
    for (final row in run['rows'])
      row['code']: {
        'action': 'create',
        'article_id': null,
        'article_revision': null,
        'expected_binding_revision': 0,
        'confirm_name_difference': false,
      },
  },
  'replacements': <String, dynamic>{},
};
void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  test('actual HTTP v2 original, bound preview, consumer and lost ACK roundtrip with 2 MiB original', () async {
    final backend = Directory('../backend').absolute,
        temporary = await Directory.systemTemp.createTemp(
          'smartplan-native-price-v2-',
        );
    final python =
        Platform.environment['SMARTPLAN_TEST_PYTHON'] ??
        '${Directory('../backend').absolute.path}/.venv/${Platform.isWindows ? 'Scripts/python.exe' : 'bin/python'}';
    Process? server;
    StreamIterator<String>? output;
    StreamSubscription<String>? errors;
    PriceHttpApi? api;
    BusinessSession? session;
    final diagnostics = StringBuffer();
    try {
      final seed = fixture.replaceFirst(
        'app = create_app(',
        'from business_schema import ensure_schema\nensure_schema(office, activate=True)\napp = create_app(',
      );
      server = await Process.start(python, [
        '-u',
        '-c',
        seed,
        temporary.path,
      ], workingDirectory: backend.path);
      errors = server.stderr.transform(utf8.decoder).listen(diagnostics.write);
      output = StreamIterator(
        server.stdout.transform(utf8.decoder).transform(const LineSplitter()),
      );
      if (!await output.moveNext().timeout(const Duration(seconds: 30)))
        throw StateError('$diagnostics');
      final hello = priceCopy(jsonDecode(output.current));
      await HttpOverrides.runWithHttpOverrides(() async {
        api = PriceHttpApi('http://127.0.0.1:${hello['port']}')
          ..token = hello['token'];
        session = BusinessSession(api: api!);
        await session!.load();
        expect(catalogPricesWritable(session!), true, reason: session!.error);
        final source = businessMap(
          await session!.command(
            'catalog-v2-source',
            '/catalog-prices/sources',
            {'name': 'Native actual source', 'reference': 'SYNTHETIC-V2'},
          ),
        );
        final key = 'catalog-v2-import-${source['id']}',
            path = '/catalog-prices/sources/${source['id']}/imports';
        await expectLater(
          session!.command(key, path, {
            'catalog_revision': 'NOV-DEC-2026',
            'filename': 'native-v2.csv',
            'content_base64': priceFixture['original_base64'],
          }),
          throwsA(isA<ApiException>()),
        );
        final staged = businessMap(
          await session!.repeatCatalogPricesCommand(key),
        );
        final detail = businessMap(
              await session!.read('/catalog-prices/imports/${staged['id']}'),
            ),
            decisions = newDecisions(
              businessMap(
                await session!.read('/catalog-prices/imports/${staged['id']}'),
              ),
            );
        final checked = await catalogPricePreview(
          detail,
          decisions,
          await api!.call(
            session!.path('/catalog-prices/imports/${staged['id']}/preview'),
            decisions,
          ),
        );
        final applyKey = 'catalog-v2-apply-${staged['id']}';
        await expectLater(
          session!.command(
            applyKey,
            '/catalog-prices/imports/${staged['id']}/apply',
            {
              ...decisions,
              'preview_sha256': checked['preview_sha256'],
              'confirmation': true,
            },
          ),
          throwsA(isA<ApiException>()),
        );
        final application = businessMap(
          await session!.repeatCatalogPricesCommand(applyKey),
        );
        expect(
          api!.sent
              .where((item) => item['path'].endsWith('/imports'))
              .toList()[0],
          api!.sent
              .where((item) => item['path'].endsWith('/imports'))
              .toList()[1],
        );
        expect(
          api!.sent
              .where((item) => item['path'].endsWith('/apply'))
              .toList()[0],
          api!.sent
              .where((item) => item['path'].endsWith('/apply'))
              .toList()[1],
        );
        final articleId = application['bindings'][0]['article_id'];
        final article = businessMap(
          await session!.read('/articles/$articleId'),
        );
        final candidates = catalogPriceCandidates(
          await api!.call(session!.path('/catalog-prices/candidates'), {
            'article_id': articleId,
            'price_role': 'sales_net',
            'effective_on': '2026-11-30',
          }),
          articleId: articleId,
          role: 'sales_net',
          day: '2026-11-30',
        );
        final chosen = candidates.singleWhere(
          (value) => value.value['status'] == 'eligible',
        );
        expect(chosen.price['price_net'], '10.00');
        final docKey = 'catalog-v2-document-${hello['project_id']}',
            body = {
              'project_id': hello['project_id'],
              'kind': 'offer',
              'title': 'Exact November source',
              'issue_date': '2026-11-04',
              'positions': [
                {
                  'article_id': articleId,
                  'article_revision': article['revision'],
                  'quantity': '3',
                  'catalog_price_selection': chosen.selection,
                },
              ],
            };
        await expectLater(
          session!.catalogConsumerCommand(docKey, '/documents', body),
          throwsA(isA<ApiException>()),
        );
        final document = businessMap(
          await session!.catalogConsumerCommand(docKey, '/documents', body),
        );
        expect(
          document['positions'][0]['catalog_price_snapshot']['effective_on'],
          '2026-11-30',
        );
        expect(document['totals']['net'], '30.00');
        expect(
          api!.sent
              .where((item) => item['path'].endsWith('/documents'))
              .toList()[0],
          api!.sent
              .where((item) => item['path'].endsWith('/documents'))
              .toList()[1],
        );
        final bytes = await api!.bytes(
          session!.path('/catalog-prices/imports/${staged['id']}/original'),
          mediaType: 'application/octet-stream',
          maxBytes: 2097152,
        );
        expect(bytes, base64Decode(priceFixture['original_base64']));
        final header = utf8
            .decode(base64Decode(priceFixture['original_base64']))
            .split('\n')
            .first;
        final largeRaw = utf8.encode(
          '$header\n' +
              List.generate(
                2000,
                (i) =>
                    'native-limit-$i;NATIVE-LIMIT-$i;${'é' * 450};ST;purchase_net;1.00;3;EUR;19;2026-11-01;\n',
              ).join(),
        );
        expect(largeRaw.length, lessThan(2097152));
        final large = Uint8List.fromList([
          ...largeRaw,
          ...List.filled(2097152 - largeRaw.length, 10),
        ]);
        final largeStage = businessMap(
          await session!.command(key, path, {
            'catalog_revision': 'EXACT-2-MIB',
            'filename': 'native-limit-v2.csv',
            'content_base64': base64Encode(large),
          }),
        );
        final largeDetail = businessMap(
              await session!.read(
                '/catalog-prices/imports/${largeStage['id']}',
              ),
            ),
            largeChoices = newDecisions(
              businessMap(
                await session!.read(
                  '/catalog-prices/imports/${largeStage['id']}',
                ),
              ),
            );
        final largePreview = await catalogPricePreview(
          largeDetail,
          largeChoices,
          await api!.call(
            session!.path(
              '/catalog-prices/imports/${largeStage['id']}/preview',
            ),
            largeChoices,
          ),
        );
        expect(largePreview['rows'], hasLength(2000));
        expect(largePreview['ready'], true);
        expect(
          await api!.bytes(
            session!.path(
              '/catalog-prices/imports/${largeStage['id']}/original',
            ),
            mediaType: 'application/octet-stream',
            maxBytes: 2097152,
          ),
          large,
        );
      }, BackendHttp());
    } finally {
      session?.dispose();
      api?.dispose();
      await output?.cancel();
      await errors?.cancel();
      server?.kill();
      if (server != null)
        await server.exitCode.timeout(const Duration(seconds: 10));
      await temporary.delete(recursive: true);
    }
  }, timeout: const Timeout(Duration(minutes: 3)));
  test(
    'actual HTTP enforces exact 32 MiB v2 JSON and unchanged ordinary bound',
    () async {
      await HttpOverrides.runWithHttpOverrides(() async {
        final server = await HttpServer.bind(InternetAddress.loopbackIPv4, 0);
        final api = OfficeApi(baseUrl: 'http://127.0.0.1:${server.port}');
        final sizes = [
          32 * 1024 * 1024,
          32 * 1024 * 1024 + 1,
          20 * 1024 * 1024 + 1,
        ];
        var index = 0;
        server.listen((request) async {
          request.response.headers.contentType = ContentType.json;
          request.response.write(
            jsonEncode({'value': 'x' * (sizes[index++] - 12)}),
          );
          try {
            await request.response.close();
          } on HttpException {
          } on SocketException {}
        });
        try {
          final path = '/api/business/catalog-prices/imports/${'a' * 32}';
          expect((await api.call(path))['value'].length, 32 * 1024 * 1024 - 12);
          await expectLater(api.call(path), throwsA(isA<ApiException>()));
          await expectLater(
            api.call('/api/business/articles'),
            throwsA(isA<ApiException>()),
          );
          expect(index, 3);
        } finally {
          api.dispose();
          await server.close(force: true);
        }
      }, BackendHttp());
    },
  );
}

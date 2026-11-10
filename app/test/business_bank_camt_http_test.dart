@Tags(['posix_backend'])
library;

import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:smartplan_office/api.dart';
import 'package:smartplan_office/business_bank_camt_contract.dart';
import 'package:smartplan_office/business_bank_reconciliation.dart';
import 'package:smartplan_office/business_session.dart';
import 'package:smartplan_office/offline_vault.dart' show offlineId;

import 'backend_integration_test.dart' show BackendHttp;
import 'business_bank_camt_test.dart' show camtFixture, camtCopy;
import 'import_backend_integration_test.dart' show fixture;

class CamtHttpApi extends OfficeApi {
  CamtHttpApi(String base) : super(baseUrl: base, apiVersion: 'v1');
  bool lose = true;
  final imports = <Map<String, dynamic>>[];
  @override
  Future<dynamic> call(String path, [Map<String, dynamic>? body]) async {
    final value = await super.call(path, body);
    if (body != null && path.endsWith('/bank/camt/statements')) {
      imports.add(camtCopy(body));
      if (lose) {
        lose = false;
        throw const ApiException(0, 'Synthetic lost actual XML commit reply');
      }
    }
    return value;
  }
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  test('native actual HTTP keeps original XML bytes and repeats one accepted import', () async {
    final temporary = await Directory.systemTemp.createTemp(
      'smartplan-camt-native-',
    );
    final backend = Directory('../backend').absolute;
    final python =
        Platform.environment['SMARTPLAN_TEST_PYTHON'] ??
        '${backend.path}/.venv/bin/python';
    Process? server;
    StreamIterator<String>? output;
    StreamSubscription<String>? errors;
    CamtHttpApi? api;
    BusinessSession? session;
    final diagnostics = StringBuffer();
    try {
      server = await Process.start(python, [
        '-u',
        '-c',
        fixture.replaceFirst(
          'app = create_app(',
          'from business_schema import ensure_schema\nensure_schema(office, activate=True)\napp = create_app(',
        ),
        temporary.path,
      ], workingDirectory: backend.path);
      errors = server.stderr.transform(utf8.decoder).listen(diagnostics.write);
      output = StreamIterator(
        server.stdout.transform(utf8.decoder).transform(const LineSplitter()),
      );
      expect(
        await output.moveNext().timeout(const Duration(seconds: 30)),
        isTrue,
        reason: '$diagnostics',
      );
      final hello = businessMap(jsonDecode(output.current));
      await HttpOverrides.runWithHttpOverrides(() async {
        api = CamtHttpApi('http://127.0.0.1:${hello['port']}')
          ..token = hello['token'];
        session = BusinessSession(api: api!);
        final live = session!;
        await live.load();
        expect(live.hasFeature('bank_camt_v1'), isTrue, reason: live.error);
        final account = businessMap(
          await live.command('synthetic-camt-account', '/accounting/accounts', {
            'code': 'XML-SYN',
            'name': 'Synthetic XML bank',
            'kind': 'bank',
            'confirmation': true,
          }),
        );
        final binding = businessMap(
          await live.command('synthetic-camt-binding', '/bank/accounts', {
            'account_id': account['id'],
            'account_revision': 1,
            'revision': 0,
            'iban': 'DE89370400440532013000',
            'label': 'Synthetic XML bank',
            'active': true,
            'coverage_from': '2026-10-01',
            'coverage_to': null,
            'reason': '',
          }),
        );
        final request = <String, dynamic>{
          'account_id': account['id'],
          'account_revision': 1,
          'bank_revision': binding['revision'],
          'filename': 'synthetic.xml',
          'content_base64': camtFixture['request']['content_base64'],
        };
        final digest = camtFixture['inspection']['original_sha256'] as String;
        final inspection = await bankCamtInspection(
          await api!.call(live.path('/bank/camt/inspect'), request),
          request,
          digest,
        );
        expect(inspection['confirmation_required'], isTrue);
        expect(
          inspection['suggested_body'].containsKey(
            'complete_statement_confirmed',
          ),
          isFalse,
        );
        final body = <String, dynamic>{
          ...businessMap(inspection['suggested_body']),
          'content_base64': request['content_base64'],
          'complete_statement_confirmed': true,
        };
        final preview = bankImportPreview(
          await bankCamtPreviewHash(
            await api!.call(live.path('/bank/camt/preview'), body),
          ),
          body,
          digest,
        );
        final command = <String, dynamic>{
          ...body,
          'preview_hash': preview['preview_hash'],
          'confirmation': true,
        };
        final key = 'bank-import-${offlineId()}';
        await expectLater(
          live.command(
            key,
            '/bank/camt/statements',
            command,
            validateResult: bankReceipt('import', command, preview),
          ),
          throwsA(isA<ApiException>()),
        );
        final saved = businessMap(await live.repeatBankCommand(key));
        expect(api!.imports, hasLength(2));
        expect(api!.imports.first, api!.imports.last);
        expect(live.pending(key), isFalse);
        final id = saved['statement']['id'];
        final detail = businessMap(await live.read('/bank/statements/$id'));
        bankCamtMetadata(detail['statement']['payload']);
        final original = await api!.bytes(
          live.path('/bank/statements/$id/original'),
          mediaType: 'application/xml',
          maxBytes: 5 * 1024 * 1024,
        );
        expect(original, base64Decode(request['content_base64']));
        await bankVerifyBytes(original, businessMap(detail['original']));
        final page = businessMap(
          await live.read('/bank/statements?account_id=${account['id']}'),
        );
        expect(page['items'], hasLength(1));
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
  }, timeout: const Timeout(Duration(minutes: 2)));
}

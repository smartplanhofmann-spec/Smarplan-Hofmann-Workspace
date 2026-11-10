@Tags(['posix_backend'])
library;

import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:cryptography/cryptography.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:smartplan_office/api.dart';
import 'package:smartplan_office/legacy_offline_recovery.dart';
import 'package:smartplan_office/offline_binding.dart';
import 'package:smartplan_office/offline_vault.dart';

import 'backend_integration_test.dart' show BackendHttp;
import 'offline_instance_http_test.dart' show instanceFixture;

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  test('real MFA HTTP confirms exact old signature and PDF without reupload or encrypted-file changes, and isolates replacement company', () async {
    FlutterSecureStorage.setMockInitialValues({});
    final backend = Directory(
      Platform.environment['SMARTPLAN_TEST_BACKEND'] ?? '../backend',
    ).absolute;
    final python =
        Platform.environment['SMARTPLAN_TEST_PYTHON'] ??
        '${backend.path}/.venv/bin/python';
    final root = await Directory.systemTemp.createTemp('legacy-report-http-');
    final script = instanceFixture
        .replaceFirst("if path=='/__state':", r'''if path=='/__report_state':
        return response(start_response,'200 OK',{'archives':{name:{'entries':v['office'].db.execute('SELECT COUNT(*) FROM business_operation_entries').fetchone()[0],'versions':v['office'].db.execute('SELECT COUNT(*) FROM business_operation_versions').fetchone()[0],'receipts':v['office'].db.execute('SELECT COUNT(*) FROM business_operations_requests').fetchone()[0]} for name,v in companies.items() if name in ('a','b')},'seen':seen})
    if path=='/__state':''')
        .replaceFirst(
          "if path.endswith('/business/offline/recovery/lookup'):",
          "if path.endswith(('/business/offline/recovery/lookup','/business/offline/recovery/service-report')):",
        );
    Process? process;
    StreamIterator<String>? output;
    StreamSubscription<String>? errors;
    OfficeApi? api;
    LegacyOfflineRecovery? recovery;
    final diagnostic = StringBuffer();
    try {
      process = await Process.start(python, [
        '-u',
        '-c',
        script,
        root.path,
      ], workingDirectory: backend.path);
      errors = process.stderr.transform(utf8.decoder).listen(diagnostic.write);
      output = StreamIterator(
        process.stdout.transform(utf8.decoder).transform(const LineSplitter()),
      );
      expect(
        await output.moveNext().timeout(const Duration(seconds: 45)),
        true,
        reason: '$diagnostic',
      );
      final setup = Map<String, dynamic>.from(jsonDecode(output.current));
      await HttpOverrides.runWithHttpOverrides(() async {
        api = OfficeApi(
          baseUrl: 'http://127.0.0.1:${setup['port']}',
          apiVersion: 'v1',
        )..token = setup['token_a'];
        final now = DateTime.now().toUtc();
        final id = offlineId();
        final content = {
          'title': ' Unverändertes altes Protokoll ä ',
          'description':
              'Tatsächliche synthetische Leistung.\nKein erneuter Upload.',
          'notes': '',
          'project_name': 'Same name',
          'customer': 'Same customer',
          'captured_at': now
              .subtract(const Duration(minutes: 10))
              .toIso8601String(),
        };
        final body = <String, dynamic>{
          'request_id': offlineId(),
          'entry_id': id,
          'project_id': setup['project'],
          'content': content,
          'content_hash': offlineBindingHash([id, setup['project'], content]),
          'signer': ' Synthetischer Kunde ',
          'strokes': [
            [
              [0.0, -0.0],
              [1e-7, 0.1],
              [1, 1.0],
            ],
          ],
          'signed_at': now
              .subtract(const Duration(minutes: 5))
              .toIso8601String(),
        };
        final accepted = await api!.call(
          '/api/business/service-reports/offline',
          body,
        );
        final record = {
          'id': id,
          'project_id': setup['project'],
          'kind': 'service',
          'content': content,
          ...content,
          'content_hash': body['content_hash'],
          'capture_request': body,
          'signer': body['signer'],
          'strokes': body['strokes'],
          'signed_at': body['signed_at'],
          'status': 'signed',
          'sync_status':
              'Auf diesem Gerät unterschrieben · Übertragung ausstehend',
        };
        final device = OfflineDevice(
          root: () async => Directory('${root.path}/device'),
          unlock: () async => true,
        );
        final server = '${api!.base}|${api!.version}',
            vault = await device.open(server, setup['account'], create: true);
        await vault.write({
          'cache_schema': 1,
          'user': {'id': setup['account']},
          'records': {},
          'outbox': [],
          'service_report_records': {id: record},
          'service_report_outbox': [id],
          'workspace_outbox': [
            {'private': 'Unproven old diary never uploaded'},
          ],
        });
        await device.saveSession(
          server,
          setup['account'],
          'offline_old_report_v1',
        );
        await device.select(server, setup['account']);
        Future<Map<String, String>> bytes() async => {
          await for (final f in Directory(
            '${root.path}/device',
          ).list(recursive: true))
            if (f is File) f.path: base64Encode(await f.readAsBytes()),
        };
        final before = await bytes(), keys = await device.storage.readAll();
        final archivedBefore = (await api!.call('/__report_state'))['archives'];
        recovery = LegacyOfflineRecovery(api: api!, device: device);
        await recovery!.inspect();
        expect(recovery!.reports.length, 1);
        expect(recovery!.otherPending, 1);
        await recovery!.checkReport(0);
        final row = recovery!.reports.single;
        expect(row.status, LegacyPlanStatus.confirmed);
        expect(row.confirmation!.pdfSha256, accepted['pdf_sha256']);
        final pdf = await api!.bytes(
          '/api/business/service-reports/$id/pdf?project_id=${setup['project']}',
          mediaType: 'application/pdf',
        );
        final hash = (await Sha256().hash(pdf)).bytes
            .map((b) => b.toRadixString(16).padLeft(2, '0'))
            .join();
        expect(hash, row.confirmation!.pdfSha256);
        expect(
          (await api!.call('/__report_state'))['archives'],
          archivedBefore,
        );
        recovery!.dispose();
        recovery = null;
        await api!.call('/__select/b');
        api!.token = setup['token_b'];
        recovery = LegacyOfflineRecovery(api: api!, device: device);
        await recovery!.inspect();
        expect(recovery!.reports.length, 1);
        await expectLater(
          recovery!.checkReport(0),
          throwsA(
            isA<ApiException>().having(
              (e) => e.requestResolution,
              'no new write authority',
              isNull,
            ),
          ),
        );
        expect(recovery!.reports.single.status, LegacyPlanStatus.unresolved);
        expect(recovery!.reports.single.confirmation, isNull);
        final state = await api!.call('/__report_state');
        expect(state['archives'], archivedBefore);
        final lookups = (state['seen'] as List)
            .where(
              (r) => r['path'].endsWith(
                '/business/offline/recovery/service-report',
              ),
            )
            .toList();
        expect(lookups.length, 2);
        expect(lookups.map((r) => r['company']), ['a', 'b']);
        for (final observed in lookups) {
          final query = jsonDecode(observed['body']) as Map;
          expect(query.keys.toSet(), {
            'schema_version',
            'nonce',
            'kind',
            'project_id',
            'entry_id',
            'request_id',
            'capture_hash',
          });
          expect(query['request_id'], body['request_id']);
          expect(query['entry_id'], id);
          expect(jsonEncode(query), isNot(contains(content['description']!)));
          expect(query.containsKey('strokes'), false);
        }
        expect(
          (state['seen'] as List)
              .where(
                (r) =>
                    r['method'] == 'POST' &&
                    r['path'].endsWith('/business/service-reports/offline'),
              )
              .length,
          1,
        );
        expect(await bytes(), before);
        expect(await device.storage.readAll(), keys);
      }, BackendHttp());
    } finally {
      recovery?.dispose();
      api?.dispose();
      process?.kill();
      if (process != null) await process.exitCode;
      await output?.cancel();
      await errors?.cancel();
      await root.delete(recursive: true);
    }
  }, timeout: const Timeout(Duration(seconds: 150)));
}

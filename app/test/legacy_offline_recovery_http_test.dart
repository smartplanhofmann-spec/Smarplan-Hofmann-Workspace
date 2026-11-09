@Tags(['posix_backend'])
library;

import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:smartplan_office/api.dart';
import 'package:smartplan_office/legacy_offline_recovery.dart';
import 'package:smartplan_office/offline_vault.dart';

import 'backend_integration_test.dart' show BackendHttp;
import 'offline_instance_http_test.dart' show instanceFixture;

Future<Map<String, String>> retainedBytes(Directory directory) async => {
  await for (final f in directory.list(recursive: true))
    if (f is File) f.path: base64Encode(await f.readAsBytes()),
};

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  test('real MFA HTTP resolves one retained accepted V1 plan, transmits no geometry to cloned firm, and never writes either cache or duplicate plan', () async {
    FlutterSecureStorage.setMockInitialValues({});
    final backend = Directory(
      Platform.environment['SMARTPLAN_TEST_BACKEND'] ?? '../backend',
    ).absolute;
    final python =
        Platform.environment['SMARTPLAN_TEST_PYTHON'] ??
        '${backend.path}/.venv/bin/python';
    final root = await Directory.systemTemp.createTemp(
      'legacy-plan-readonly-http-',
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
        instanceFixture,
        root.path,
      ], workingDirectory: backend.path);
      errors = process.stderr.transform(utf8.decoder).listen(diagnostic.write);
      output = StreamIterator(
        process.stdout.transform(utf8.decoder).transform(const LineSplitter()),
      );
      expect(
        await output.moveNext().timeout(const Duration(seconds: 45)),
        isTrue,
        reason: '$diagnostic',
      );
      final setup = Map<String, dynamic>.from(jsonDecode(output.current));
      await HttpOverrides.runWithHttpOverrides(() async {
        api = OfficeApi(
          baseUrl: 'http://127.0.0.1:${setup['port']}',
          apiVersion: 'v1',
        )..token = setup['token_a'];
        final command = {
          'request_id': offlineId(),
          'title': 'Private original A, never upload during recovery',
          'walls': [
            {
              'id': 'original-wall',
              'points': [
                [1.0, -0.0],
                [3.0, 4.0],
              ],
            },
          ],
        };
        final original = await api!.call(
          '/api/projects/${setup['project']}/plans',
          command,
        );
        final device = OfflineDevice(
          root: () async => Directory('${root.path}/device'),
          unlock: () async => true,
        );
        final server = '${api!.base}|${api!.version}';
        final vault = await device.open(server, setup['account'], create: true);
        await vault.write({
          'cache_schema': 1,
          'user': {'id': setup['account']},
          'records': {},
          'outbox': [
            {
              'local_id': offlineId(),
              'project_id': setup['project'],
              'request_id': command['request_id'],
              'path': '/api/projects/${setup['project']}/plans',
              'body': command,
              'snapshot': {'title': 'Unproven private snapshot'},
            },
          ],
          'business_time_outbox': [
            {
              'body': {'note': 'Unproven private time'},
            },
          ],
        });
        await device.saveSession(
          server,
          setup['account'],
          'offline_old_v1_retained',
        );
        await device.select(server, setup['account']);
        final before = await retainedBytes(Directory('${root.path}/device')),
            keys = await device.storage.readAll();
        recovery = LegacyOfflineRecovery(api: api!, device: device);
        await recovery!.inspect();
        await recovery!.check(0);
        expect(recovery!.plans.single.status, LegacyPlanStatus.confirmed);
        expect(recovery!.plans.single.serverTitle, original['title']);
        expect(recovery!.otherPending, 1);
        var state = await api!.call('/__state');
        expect(state['plans']['a'], hasLength(1));
        expect(state['plans']['a'].single, original);
        recovery!.dispose();
        recovery = null;
        await api!.call('/__select/b');
        api!.token = setup['token_b'];
        recovery = LegacyOfflineRecovery(api: api!, device: device);
        await recovery!.inspect();
        await expectLater(
          recovery!.check(0),
          throwsA(
            isA<ApiException>().having(
              (e) => e.requestResolution,
              'no new write authority',
              isNull,
            ),
          ),
        );
        expect(recovery!.plans.single.status, LegacyPlanStatus.unresolved);
        expect(recovery!.plans.single.serverTitle, isNull);
        state = await api!.call('/__state');
        expect(state['plans']['a'], hasLength(1));
        expect(state['plans']['b'], isEmpty);
        final lookups = (state['seen'] as List)
            .where(
              (r) => r['path'].endsWith('/business/offline/recovery/lookup'),
            )
            .toList();
        expect(lookups, hasLength(2));
        expect(lookups.map((r) => r['company']), ['a', 'b']);
        for (final observed in lookups) {
          final request = jsonDecode(observed['body']) as Map;
          expect(request.keys.toSet(), {
            'schema_version',
            'nonce',
            'kind',
            'project_id',
            'plan_id',
            'request_id',
            'request_hash',
          });
          expect(observed['body'], isNot(contains(command['title'])));
          expect(request.containsKey('walls'), isFalse);
        }
        expect(
          (state['seen'] as List).where(
            (r) => r['method'] == 'POST' && r['path'].endsWith('/plans'),
          ),
          hasLength(1),
        );
        expect(await retainedBytes(Directory('${root.path}/device')), before);
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

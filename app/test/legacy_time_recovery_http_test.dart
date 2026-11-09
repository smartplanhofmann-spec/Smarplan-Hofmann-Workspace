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

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  test('real MFA HTTP time core uses retained employee basis and never copies a new firm profile or replays time events', () async {
    FlutterSecureStorage.setMockInitialValues({});
    final backend = Directory(
      Platform.environment['SMARTPLAN_TEST_BACKEND'] ?? '../backend',
    ).absolute;
    final python =
        Platform.environment['SMARTPLAN_TEST_PYTHON'] ??
        '${backend.path}/.venv/bin/python';
    final root = await Directory.systemTemp.createTemp(
      'legacy-time-core-http-',
    );
    final script = instanceFixture
        .replaceFirst("if path=='/__state':", r'''if path=='/__time_state':
        return response(start_response,'200 OK',{'events':{name:[dict(row) for row in v['office'].db.execute('SELECT * FROM business_time_events ORDER BY request_id')] for name,v in companies.items() if name in ('a','b')},'seen':seen})
    if path=='/__state':''')
        .replaceFirst(
          "if path.endswith('/business/offline/recovery/lookup'):",
          "if path.endswith(('/business/offline/recovery/lookup','/business/offline/recovery/time-event')):",
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
        isTrue,
        reason: '$diagnostic',
      );
      final setup = Map<String, dynamic>.from(jsonDecode(output.current));
      await HttpOverrides.runWithHttpOverrides(() async {
        api = OfficeApi(
          baseUrl: 'http://127.0.0.1:${setup['port']}',
          apiVersion: 'v1',
        )..token = setup['token_a'];
        Future<dynamic> employee() => api!.call('/api/business/employees', {
          'request_id': offlineId(),
          'user_id': setup['account'],
          'name': 'Synthetic retained time owner',
          'weekly_minutes': 2400,
          'hourly_cost_minor': 3500,
        });
        await employee();
        final instant = DateTime.now().toUtc().subtract(
          const Duration(hours: 4),
        );
        final start = <String, dynamic>{
          'request_id': offlineId(),
          'entry_id': offlineId(),
          'device_id': offlineId(),
          'sequence': 1,
          'revision': 0,
          'action': 'start',
          'occurred_at': instant.toIso8601String(),
          'project_id': setup['project'],
        };
        start['event_id'] = start['request_id'];
        final first = await api!.call('/api/business/time/events', start);
        final stop = <String, dynamic>{
          ...start,
          'request_id': offlineId(),
          'sequence': 2,
          'revision': 1,
          'action': 'stop',
          'occurred_at': instant
              .add(const Duration(hours: 1))
              .toIso8601String(),
        };
        stop['event_id'] = stop['request_id'];
        await api!.call('/api/business/time/events', stop);
        final record = Map<String, dynamic>.from(first['entry'])
          ..remove('hourly_cost_minor')
          ..remove('supplement_percent');
        record.addAll({
          'user_id': setup['account'],
          'status': 'stopped',
          'revision': 2,
          'sequence': 2,
          'sync_status': 'Auf diesem Gerät gesichert',
        });
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
          'business_time_records': {record['id']: record},
          'business_time_outbox': [
            {
              'entry_id': stop['entry_id'],
              'project_id': setup['project'],
              'body': stop,
            },
          ],
          'workspace_outbox': [
            {'private': 'Unproven old diary never uploaded'},
          ],
        });
        await device.saveSession(
          server,
          setup['account'],
          'offline_old_time_v1',
        );
        await device.select(server, setup['account']);
        Future<Map<String, String>> bytes() async => {
          await for (final f in Directory(
            '${root.path}/device',
          ).list(recursive: true))
            if (f is File) f.path: base64Encode(await f.readAsBytes()),
        };
        final before = await bytes(),
            keys = await device.storage.readAll(),
            eventsBefore = (await api!.call('/__time_state'))['events'];
        recovery = LegacyOfflineRecovery(api: api!, device: device);
        await recovery!.inspect();
        expect(recovery!.times, hasLength(1));
        expect(recovery!.otherPending, 1);
        expect(recovery!.times.single.confirmation, isNull);
        await recovery!.checkTime(0);
        expect(recovery!.times.single.status, LegacyPlanStatus.confirmed);
        expect(recovery!.times.single.confirmation!.action, 'stop');
        expect((await api!.call('/__time_state'))['events'], eventsBefore);
        final acceptedHash =
            ((await api!.call('/__time_state'))['seen'] as List)
                .where(
                  (r) => r['path'].endsWith(
                    '/business/offline/recovery/time-event',
                  ),
                )
                .single['body'];
        final oldHash = jsonDecode(acceptedHash)['request_hash'];
        recovery!.dispose();
        recovery = null;
        await api!.call('/__select/b');
        api!.token = setup['token_b'];
        final replacementEmployee = await employee();
        expect(replacementEmployee['id'], isNot(record['employee_id']));
        await api!.call('/api/business/time/events', start);
        await api!.call('/api/business/time/events', stop);
        final replacementBefore = (await api!.call('/__time_state'))['events'];
        recovery = LegacyOfflineRecovery(api: api!, device: device);
        await recovery!.inspect();
        expect(recovery!.times, hasLength(1));
        await expectLater(
          recovery!.checkTime(0),
          throwsA(
            isA<ApiException>().having(
              (e) => e.requestResolution,
              'no new write authority',
              isNull,
            ),
          ),
        );
        expect(recovery!.times.single.status, LegacyPlanStatus.unresolved);
        expect(recovery!.times.single.confirmation, isNull);
        final state = await api!.call('/__time_state');
        expect(state['events'], replacementBefore);
        final lookups = (state['seen'] as List)
            .where(
              (r) =>
                  r['path'].endsWith('/business/offline/recovery/time-event'),
            )
            .toList();
        expect(lookups, hasLength(2));
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
            'request_hash',
          });
          expect(query['request_hash'], oldHash);
          expect(query['request_id'], stop['request_id']);
          expect(query.containsKey('employee_id'), isFalse);
          expect(query.containsKey('body'), isFalse);
        }
        expect(
          (state['seen'] as List).where(
            (r) =>
                r['method'] == 'POST' &&
                r['path'].endsWith('/business/time/events'),
          ),
          hasLength(4),
        );
        expect((state['events']['a'] as List), hasLength(2));
        expect((state['events']['b'] as List), hasLength(2));
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

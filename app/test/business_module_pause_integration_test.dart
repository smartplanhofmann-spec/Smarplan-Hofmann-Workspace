@Tags(['posix_backend'])
library;

import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:smartplan_office/api.dart';
import 'package:smartplan_office/offline_plans.dart';
import 'package:smartplan_office/offline_vault.dart' show offlineId;

import 'backend_integration_test.dart' show BackendHttp;
import 'import_backend_integration_test.dart' show fixture, ImportConnection;
import 'offline_plans_test.dart' show TestDevice, idle;

class TimeModuleConnection extends ImportConnection {
  bool loseTimeAck = false;
  TimeModuleConnection(super.base);

  @override
  Future<dynamic> call(String path, [Map<String, dynamic>? body]) async {
    final result = await super.call(path, body);
    if (path == '/api/business/time/events' && loseTimeAck) {
      loseTimeAck = false;
      throw const ApiException(
        0,
        'Synthetic loss of the committed time response',
      );
    }
    return result;
  }
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  final backend = Directory('../backend').absolute;
  final python =
      Platform.environment['SMARTPLAN_TEST_PYTHON'] ??
      '${backend.path}/.venv/${Platform.isWindows ? 'Scripts/python.exe' : 'bin/python'}';
  test(
    'Real HTTP retains time events across lost response, module deactivation, restart and reactivation',
    () async {
      await HttpOverrides.runWithHttpOverrides(() async {
        final directory = await Directory.systemTemp.createTemp(
          'smartplan-module-pause-http-',
        );
        Process? process;
        StreamIterator<String>? output;
        StreamSubscription<String>? errors;
        OfficeApi? api;
        TimeModuleConnection? connection;
        OfflinePlans? repo;
        final diagnostics = StringBuffer();
        try {
          final seed = fixture.replaceFirst(
            'app = create_app(',
            '''from business_schema import ensure_schema
from business_planning import Planning
ensure_schema(office, activate=True)
Planning(office).save_employee(user,dict(request_id='1'*32,user_id=user['id'],name='Synthetic employee',active=True,weekly_minutes=2400,hourly_cost_minor=1000))
app = create_app(''',
          );
          process = await Process.start(python, [
            '-u',
            '-c',
            seed,
            directory.path,
          ], workingDirectory: backend.path);
          errors = process.stderr
              .transform(utf8.decoder)
              .listen(diagnostics.write);
          output = StreamIterator(
            process.stdout
                .transform(utf8.decoder)
                .transform(const LineSplitter()),
          );
          if (!await output.moveNext().timeout(const Duration(seconds: 30))) {
            throw StateError('Fixture not ready: $diagnostics');
          }
          final hello = Map<String, dynamic>.from(jsonDecode(output.current));
          final base = 'http://127.0.0.1:${hello['port']}';
          api = OfficeApi(baseUrl: base, apiVersion: 'v1')
            ..token = hello['token'];
          final owner = api;
          Future<void> timeEnabled(bool enabled) async {
            final config = Map<String, dynamic>.from(
              await owner.call('/api/business/organization'),
            );
            final modules = <String, dynamic>{
              for (final entry in (config['modules'] as Map).entries)
                entry.key: {
                  'visible': entry.value['visibility_override'],
                  'enabled': entry.value['enabled'],
                },
            };
            modules['personnel']['enabled'] = enabled;
            await owner.call('/api/business/organization', {
              'request_id': offlineId(),
              'revision': config['revision'],
              'needs': config['needs'],
              'modules': modules,
            });
          }

          final now = DateTime.now().toUtc();
          final project = hello['project_id'] as String;
          final device = TestDevice(Directory('${directory.path}/device'));
          connection = TimeModuleConnection(base);
          final transport = connection;
          OfflinePlans open() => OfflinePlans(
            api: owner,
            transport: transport,
            device: device,
            clock: () => now,
          );
          repo = open();
          await repo.login(
            Map<String, dynamic>.from(hello['user']),
            List<dynamic>.from(hello['projects']),
            businessTime: true,
          );
          await idle(repo);
          transport.connected = false;
          final entry = await repo.saveTimeEvent(
            project,
            'start',
            occurredAt: now.subtract(const Duration(hours: 1)),
          );
          await idle(repo);
          await repo.saveTimeEvent(
            project,
            'stop',
            entryId: entry['id'],
            occurredAt: now,
          );
          await idle(repo);
          expect(repo.pending, 2);

          transport.connected = true;
          transport.loseTimeAck = true;
          await repo.sync();
          expect(repo.pending, 2);
          final beforePause = await owner.call(
            '/api/business/time/entries/${entry['id']}',
          );
          expect(beforePause['events'], hasLength(1));

          await timeEnabled(false);
          await repo.sync();
          // The committed start is acknowledged despite deactivation. The new
          // stop remains queued with its original identity and local timestamp.
          expect(repo.pending, 1, reason: repo.notice);
          expect(
            repo.timeEntries(project).single['sync_status'],
            'Wartet auf Modulaktivierung',
          );
          expect(repo.timeEntries(project).single['status'], 'stopped');
          await repo.leave();
          repo.dispose();
          repo = open();
          await repo.resume();
          await idle(repo);
          expect(repo.pending, 1);
          expect(
            repo.timeEntries(project).single['sync_status'],
            'Wartet auf Modulaktivierung',
          );
          final stillPaused = await owner.call(
            '/api/business/time/entries/${entry['id']}',
          );
          expect(stillPaused['events'], hasLength(1));

          await timeEnabled(true);
          await repo.sync();
          expect(repo.pending, 0, reason: repo.notice);
          expect(
            repo.timeEntries(project).single['sync_status'],
            'Synchronisiert',
          );
          expect(
            repo.timeEntries(project).single.containsKey('sync_error'),
            isFalse,
          );
          expect(repo.notice, isNull);
          final completed = await owner.call(
            '/api/business/time/entries/${entry['id']}',
          );
          expect(completed['events'], hasLength(2));
          expect(completed['revision'], 2);
          expect(completed['status'], 'stopped');
          await repo.sync();
          expect(
            (await owner.call(
              '/api/business/time/entries/${entry['id']}',
            ))['events'],
            completed['events'],
          );
        } finally {
          await repo?.flush();
          if (repo != null) await idle(repo);
          repo?.dispose();
          connection?.dispose();
          api?.dispose();
          await output?.cancel();
          await errors?.cancel();
          if (process != null) {
            process.kill();
            try {
              await process.exitCode.timeout(const Duration(seconds: 5));
            } on TimeoutException {
              process.kill(ProcessSignal.sigkill);
              await process.exitCode;
            }
          }
          await directory.delete(recursive: true);
        }
      }, BackendHttp());
    },
    skip: !Platform.isLinux,
    timeout: const Timeout(Duration(minutes: 2)),
  );
}

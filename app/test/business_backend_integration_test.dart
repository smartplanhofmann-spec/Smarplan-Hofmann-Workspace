@Tags(['posix_backend'])
library;

import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:smartplan_office/api.dart';
import 'package:smartplan_office/business_session.dart';
import 'package:smartplan_office/offline_plans.dart';
import 'package:smartplan_office/offline_vault.dart' show offlineId;

import 'backend_integration_test.dart' show BackendHttp;
import 'import_backend_integration_test.dart' show fixture, ImportConnection;
import 'offline_plans_test.dart' show TestDevice, idle;
import 'business_offline_media_test.dart' show fieldPng;

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  final backend = Directory(
    Platform.environment['SMARTPLAN_TEST_BACKEND'] ?? '../backend',
  ).absolute;
  final python =
      Platform.environment['SMARTPLAN_TEST_PYTHON'] ??
      '${backend.path}/.venv/${Platform.isWindows ? 'Scripts/python.exe' : 'bin/python'}';
  test(
    'Real business HTTP preserves draft values and durable own time through the scoped grant',
    () async {
      await HttpOverrides.runWithHttpOverrides(() async {
        final directory = await Directory.systemTemp.createTemp(
          'smartplan-business-http-',
        );
        Process? process;
        StreamIterator<String>? output;
        StreamSubscription<String>? stderr;
        OfficeApi? api;
        ImportConnection? connection;
        OfflinePlans? repo;
        BusinessSession? session;
        final diagnostics = StringBuffer();
        try {
          final seed = fixture.replaceFirst(
            'app = create_app(',
            """from business_schema import ensure_schema
from business_planning import Planning
ensure_schema(office, activate=True)
Planning(office).save_employee(user,dict(request_id='1'*32,user_id=user['id'],name='Synthetic employee',active=True,weekly_minutes=2400,hourly_cost_minor=1000))
app = create_app(""",
          );
          process = await Process.start(python, [
            '-u',
            '-c',
            seed,
            directory.path,
          ], workingDirectory: backend.path);
          stderr = process.stderr
              .transform(utf8.decoder)
              .listen(diagnostics.write);
          output = StreamIterator(
            process.stdout
                .transform(utf8.decoder)
                .transform(const LineSplitter()),
          );
          if (!await output.moveNext().timeout(const Duration(seconds: 30)))
            throw StateError('Fixture not ready: $diagnostics');
          final hello = Map<String, dynamic>.from(jsonDecode(output.current));
          final base = 'http://127.0.0.1:${hello['port']}';
          api = OfficeApi(baseUrl: base, apiVersion: 'v1')
            ..token = hello['token'];
          session = BusinessSession(api: api, projectId: hello['project_id']);
          await session.load();
          expect(session.supported, isTrue, reason: session.error);
          final draft = businessMap(
            await session.command('offer', '/documents', {
              'project_id': hello['project_id'],
              'kind': 'offer',
              'title': 'Synthetisches Angebot',
              'issue_date': '2026-10-26',
              'buyer': {
                'name': 'Synthetic customer',
                'address_line': 'Testweg 1',
                'postal_code': '12345',
                'city': 'Teststadt',
                'country': 'DE',
                'email': 'buyer@example.test',
              },
              'positions': [
                {
                  'description': 'Geprüfte Montage',
                  'quantity': '2.50',
                  'unit': 'HUR',
                  'unit_price_net': '55.50',
                  'tax_rate': '19',
                  'kind': 'labor',
                },
              ],
            }),
          );
          final converted = businessMap(
            await session.command(
              'convert',
              '/documents/${draft['id']}/convert',
              {'revision': draft['revision'], 'target_kind': 'invoice'},
            ),
          );
          expect(converted['positions'], draft['positions']);
          expect(converted['status'], 'draft');
          connection = ImportConnection(base);
          var now = DateTime.now().toUtc();
          // Exact whole-second assertions need a whole-second fixture clock;
          // fractional per-day rounding is separate from offline replay.
          now = DateTime.utc(
            now.year,
            now.month,
            now.day,
            now.hour,
            now.minute,
            now.second,
          );
          repo = OfflinePlans(
            api: api,
            transport: connection,
            device: TestDevice(Directory('${directory.path}/device')),
            clock: () => now,
          );
          await repo.login(
            Map<String, dynamic>.from(hello['user']),
            List<dynamic>.from(hello['projects']),
            businessTime: true,
            fieldMedia: true,
          );
          await idle(repo);
          expect(repo.timeEventsSupported, isTrue);
          expect(repo.fieldMediaSupported, isTrue);
          connection.connected = false;
          final local = await repo.saveTimeEvent(
            hello['project_id'],
            'start',
            occurredAt: now.subtract(const Duration(hours: 3)),
          );
          await idle(repo);
          await repo.saveTimeEvent(
            hello['project_id'],
            'pause',
            entryId: local['id'],
            occurredAt: now.subtract(const Duration(hours: 1)),
          );
          await idle(repo);
          await repo.saveTimeEvent(
            hello['project_id'],
            'stop',
            entryId: local['id'],
            occurredAt: now,
          );
          await idle(repo);
          final photo = await repo.captureFieldPhoto(
            hello['project_id'],
            fieldPng,
            filename: 'synthetic-site.png',
            mediaType: 'image/png',
            caption: 'Synthetische Baustellennotiz',
          );
          await idle(repo);
          expect(repo.pending, 4);
          await repo.leave();
          await repo.resume();
          await idle(repo);
          connection.connected = true;
          await repo.sync();
          expect(repo.pending, 0, reason: repo.notice);
          expect(
            repo.timeEntries(hello['project_id']).single['status'],
            'stopped',
          );
          final entry = businessMap(
            await session.read('/time/entries/${local['id']}'),
          );
          expect(entry['revision'], 3);
          expect(entry['events'], hasLength(3));
          // A shift started elsewhere can be continued from its cached server
          // history. Offline replay must neither lose its first interval nor
          // submit the already accepted start a second time.
          final remoteId = offlineId();
          await session.command('remote-clock', '/time/events', {
            'entry_id': remoteId,
            'device_id': 'synthetic-other-device',
            'sequence': 1,
            'revision': 0,
            'project_id': hello['project_id'],
            'action': 'start',
            'occurred_at': now
                .subtract(const Duration(hours: 7))
                .toIso8601String(),
          });
          await repo.cacheTimeEntries(hello['project_id'], [
            businessMap(await session.read('/time/entries/$remoteId')),
          ]);
          connection.connected = false;
          for (final event in [('pause', 6), ('resume', 5), ('stop', 4)]) {
            await repo.saveTimeEvent(
              hello['project_id'],
              event.$1,
              entryId: remoteId,
              occurredAt: now.subtract(Duration(hours: event.$2)),
            );
          }
          await idle(repo);
          await repo.leave();
          await repo.resume();
          await idle(repo);
          final cached = repo
              .timeEntries(hello['project_id'])
              .singleWhere((r) => r['id'] == remoteId);
          expect(cached['local_events'], hasLength(4));
          expect(repo.pending, 3);
          connection.connected = true;
          await repo.sync();
          await repo.sync();
          final remote = businessMap(
            await session.read('/time/entries/$remoteId'),
          );
          expect(remote['events'], hasLength(4));
          expect(remote['worked_seconds'], 7200);
          expect(remote['break_seconds'], 3600);
          expect(repo.pending, 0);
          final uploaded = repo.fieldPhotos(hello['project_id']).single;
          expect(uploaded['local_id'], photo['local_id']);
          expect(uploaded['sync_status'], 'Synchronisiert');
          final verified = await api.bytes(
            '/api/business/media/${uploaded['server_id']}/content',
            mediaType: 'image/png',
          );
          expect(verified, fieldPng);
          expect(uploaded['caption'], 'Synthetische Baustellennotiz');
          await expectLater(
            connection.call('/api/business/finance/open-items'),
            throwsA(isA<ApiException>().having((e) => e.status, 'status', 403)),
          );
          await expectLater(
            api.call('/api/offline/access', {}),
            throwsA(isA<ApiException>().having((e) => e.status, 'status', 409)),
          );
          expect(offlineId(), matches(RegExp(r'^[a-f0-9]{32}$')));
        } finally {
          await repo?.flush();
          if (repo != null) await idle(repo);
          await repo?.leave();
          repo?.dispose();
          connection?.dispose();
          session?.dispose();
          api?.dispose();
          await output?.cancel();
          await stderr?.cancel();
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

import 'dart:convert';
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:smartplan_office/api.dart';
import 'package:smartplan_office/offline_plans.dart';

import 'offline_plans_test.dart' show PlanServer, TestDevice, idle, loginV2;

class TimeServer extends PlanServer {
  bool timeGrant = true, conflict = false, timeEnabled = true;
  final timeReceipts = <String, Map<String, dynamic>>{};
  final timeBodies = <Map<String, dynamic>>[];
  @override
  Future<dynamic> call(String path, [Map<String, dynamic>? body]) async {
    if (!online) throw const ApiException(0, 'Offline');
    if (path.split('?').first == '/api/business/capabilities')
      return {
        'readonly': false,
        'permissions': ['time.own', 'documents.read', 'documents.write'],
        'capabilities': ['business_time', 'business_operations'],
      };
    if (path == '/api/business/offline/access/v2')
      return v2Grant(kind: 'business', extra: [if (timeGrant) 'time_events']);
    if (path == '/api/business/time/events') {
      if (forbidden) throw const ApiException(403, 'Entzogen');
      if (conflict)
        throw const ApiException(409, 'Zweites Gerät hat die Zeit geändert');
      timeBodies.add(Map<String, dynamic>.from(jsonDecode(jsonEncode(body))));
      final request = body!['request_id'];
      if (!timeEnabled && !timeReceipts.containsKey(request)) {
        throw const ApiException(423, 'Personal ist fachlich deaktiviert.');
      }
      final result = timeReceipts.putIfAbsent(
        request,
        () => {
          'request_id': request,
          'event_id': body['event_id'],
          'entry': {
            'id': body['entry_id'],
            'project_id': body['project_id'],
            'revision': body['revision'] + 1,
            'sequence': body['sequence'],
            'status': body['action'] == 'stop'
                ? 'stopped'
                : body['action'] == 'pause'
                ? 'paused'
                : 'working',
            'events': [],
          },
        },
      );
      if (loseAck) {
        loseAck = false;
        throw const ApiException(0, 'ACK verloren');
      }
      return result;
    }
    return super.call(path, body);
  }
}

void main() {
  late Directory folder;
  late TestDevice device;
  late TimeServer server;
  late OfflinePlans repo;
  var now = DateTime.utc(2026, 10, 26, 8);
  setUp(() async {
    folder = await Directory.systemTemp.createTemp('smartplan-business-clock-');
    device = TestDevice(folder);
    server = TimeServer()..token = 'synthetic-session';
    repo = OfflinePlans(
      api: server,
      transport: server.offlineTransport,
      device: device,
      clock: () => now,
    );
    await loginV2(
      repo,
      {'id': 'a' * 32, 'role': 'technician'},
      [
        {'id': 'p', 'name': 'Synthetische Baustelle'},
      ],
      businessTime: true,
    );
    await idle(repo);
  });
  tearDown(() async {
    await idle(repo);
    repo.dispose();
    server.dispose();
    await folder.delete(recursive: true);
  });
  test('Server-started time preserves its full history when continued offline and reopened', () async {
    final start = now.subtract(const Duration(hours: 2));
    final id = 'b' * 32;
    await repo.cacheTimeEntries('p', [
      {
        'id': id,
        'project_id': 'p',
        'revision': 1,
        'sequence': 1,
        'status': 'working',
        'started_at': start.toIso8601String(),
        'last_at': start.toIso8601String(),
        'events': [
          {'action': 'start', 'occurred_at': start.toIso8601String()},
        ],
      },
    ]);
    server.online = false;
    await repo.saveTimeEvent('p', 'pause', entryId: id);
    await idle(repo);
    await repo.leave();
    repo.api.token = null;
    await repo.resume();
    await idle(repo);
    final paused = repo.timeEntries('p').single;
    expect(paused['local_events'], [
      {'action': 'start', 'occurred_at': start.toIso8601String()},
      {'action': 'pause', 'occurred_at': now.toIso8601String()},
    ], reason: 'Previously confirmed work must remain in the local duration.');
    now = now.add(const Duration(minutes: 30));
    await repo.saveTimeEvent('p', 'resume', entryId: id);
    now = now.add(const Duration(hours: 1));
    await repo.saveTimeEvent('p', 'stop', entryId: id);
    await idle(repo);
    server.online = true;
    await repo.sync();
    final synced = repo.timeEntries('p').single;
    expect(synced['local_events'], hasLength(4));
    expect(synced['sync_status'], 'Synchronisiert');
    expect(server.timeBodies.map((body) => body['sequence']), [2, 3, 4]);
    expect(repo.pending, 0);
  });
  test('Offline start pause stop survives reopening and lost ACK without a duplicate', () async {
    server.online = false;
    final entry = await repo.saveTimeEvent('p', 'start');
    now = now.add(const Duration(hours: 2));
    await repo.saveTimeEvent('p', 'pause', entryId: entry['id']);
    now = now.add(const Duration(minutes: 20));
    await repo.saveTimeEvent('p', 'stop', entryId: entry['id']);
    await idle(repo);
    expect(repo.pending, 3);
    final files = await folder
        .list(recursive: true)
        .where((f) => f.path.endsWith('.enc'))
        .cast<File>()
        .toList();
    expect(await files.last.readAsString(), isNot(contains('occurred_at')));
    repo.dispose();
    repo = OfflinePlans(
      api: server,
      transport: server.offlineTransport,
      device: device,
      clock: () => now,
    );
    repo.api.token = null;
    await repo.resume();
    await idle(repo);
    expect(repo.timeEntries('p').single['status'], 'stopped');
    server.online = true;
    server.loseAck = true;
    await repo.sync();
    expect(repo.pending, 3);
    await repo.sync();
    expect(repo.pending, 0);
    expect(server.timeReceipts.length, 3);
    expect(server.timeBodies[0], server.timeBodies[1]);
    expect(repo.timeEntries('p').single['sync_status'], 'Synchronisiert');
  });
  test(
    'Conflict preserves the durable event and stops automatic replay',
    () async {
      server.online = false;
      await repo.saveTimeEvent('p', 'start');
      await idle(repo);
      server.online = true;
      server.conflict = true;
      await repo.sync();
      expect(repo.pending, 1);
      expect(repo.timeEntries('p').single['sync_status'], 'Konflikt');
      await repo.sync();
      expect(repo.pending, 1);
    },
  );
  test('A committed event is acknowledged while disabled and pending events resume once reactivated', () async {
    server.online = false;
    final entry = await repo.saveTimeEvent('p', 'start');
    now = now.add(const Duration(hours: 1));
    await repo.saveTimeEvent('p', 'stop', entryId: entry['id']);
    await idle(repo);
    server.online = true;
    server.loseAck = true;
    await repo.sync();
    expect(server.timeReceipts, hasLength(1));
    expect(repo.pending, 2);

    server.timeEnabled = false;
    await repo.sync();
    expect(server.timeReceipts, hasLength(1));
    expect(repo.pending, 1);
    expect(
      repo.timeEntries('p').single['sync_status'],
      'Wartet auf Modulaktivierung',
    );
    final blockedBody = server.timeBodies.last;
    await repo.leave();
    repo.dispose();
    repo = OfflinePlans(
      api: server,
      transport: server.offlineTransport,
      device: device,
      clock: () => now,
    );
    repo.api.token = null;
    await repo.resume();
    await idle(repo);
    expect(repo.pending, 1);
    expect(repo.timeEntries('p').single['status'], 'stopped');
    expect(
      repo.timeEntries('p').single['sync_status'],
      'Wartet auf Modulaktivierung',
    );

    server.timeEnabled = true;
    await repo.sync();
    expect(server.timeBodies.last, blockedBody);
    expect(repo.pending, 0);
    expect(server.timeReceipts, hasLength(2));
    expect(repo.timeEntries('p').single['sync_status'], 'Synchronisiert');
    expect(repo.timeEntries('p').single.containsKey('sync_error'), isFalse);
    expect(repo.notice, isNull);
    await repo.sync();
    expect(server.timeReceipts, hasLength(2));
  });
  test('New offline events wait during deactivation and remain editable until upload resumes', () async {
    server.online = false;
    final entry = await repo.saveTimeEvent('p', 'start');
    await idle(repo);
    server.timeEnabled = false;
    server.online = true;
    await repo.sync();
    expect(server.timeReceipts, isEmpty);
    expect(repo.pending, 1);
    expect(
      repo.timeEntries('p').single['sync_status'],
      'Wartet auf Modulaktivierung',
    );
    final original = server.timeBodies.single;

    now = now.add(const Duration(hours: 1));
    await repo.saveTimeEvent('p', 'stop', entryId: entry['id']);
    await idle(repo);
    expect(repo.pending, 2);
    expect(repo.timeEntries('p').single['status'], 'stopped');
    expect(
      repo.timeEntries('p').single['sync_status'],
      'Wartet auf Modulaktivierung',
    );
    server.timeEnabled = true;
    await repo.sync();
    expect(repo.pending, 0);
    expect(server.timeReceipts, hasLength(2));
    expect(
      server.timeBodies.where((item) => item['action'] == 'start'),
      everyElement(original),
    );
    expect(repo.timeEntries('p').single['sync_status'], 'Synchronisiert');
  });
  test('An old grant is never silently expanded to time recording', () async {
    server.timeGrant = false;
    await loginV2(
      repo,
      {'id': 'a' * 32, 'role': 'technician'},
      [
        {'id': 'p', 'name': 'Test'},
      ],
    );
    await idle(repo);
    expect(repo.timeEventsSupported, isFalse);
    await expectLater(
      repo.saveTimeEvent('p', 'start'),
      throwsA(isA<ApiException>()),
    );
    expect(repo.pending, 0);
  });
}

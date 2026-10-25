import 'dart:convert';
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:smartplan_office/api.dart';
import 'package:smartplan_office/offline_plans.dart';

import 'offline_plans_test.dart' show PlanServer, TestDevice, idle;

class TimeServer extends PlanServer {
  bool timeGrant = true, conflict = false;
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
    if (path == '/api/business/offline/access')
      return {
        'token': 'offline-synthetic',
        'expires_at': DateTime.utc(2026, 11, 1).toIso8601String(),
        'capabilities': [if (timeGrant) 'time_events'],
      };
    if (path == '/api/business/time/events') {
      if (forbidden) throw const ApiException(403, 'Entzogen');
      if (conflict)
        throw const ApiException(409, 'Zweites Gerät hat die Zeit geändert');
      timeBodies.add(Map<String, dynamic>.from(jsonDecode(jsonEncode(body))));
      final request = body!['request_id'];
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
      transport: server,
      device: device,
      clock: () => now,
    );
    await repo.login(
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
      transport: server,
      device: device,
      clock: () => now,
    );
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
  test('An old grant is never silently expanded to time recording', () async {
    server.timeGrant = false;
    await repo.login(
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

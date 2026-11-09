import 'dart:async';
import 'dart:convert';
import 'dart:io';
import 'dart:typed_data';

import 'package:cryptography/cryptography.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:smartplan_office/api.dart';
import 'package:smartplan_office/offline_plans.dart';
import 'package:smartplan_office/offline_vault.dart';

class TestDevice extends OfflineDevice {
  final Directory folder;
  final keys = <String, SecretKey>{};
  final sessions = <String, String?>{};
  final accounts = <String, String>{};
  bool unlocked = true;
  TestDevice(this.folder);
  @override
  Future<bool> Function() get unlock =>
      () async => unlocked;
  @override
  Future<String?> selected(String server) async => accounts[server];
  @override
  Future<void> select(String server, String user) async {
    accounts[server] = user;
  }

  @override
  Future<void> saveSession(String server, String user, String? token) async {
    sessions['$server|$user'] = token;
  }

  @override
  Future<String?> session(String server, String user) async =>
      sessions['$server|$user'];
  @override
  Future<OfflineVault> open(
    String server,
    String user, {
    bool create = false,
  }) async {
    final scope = '${await namespace(server)}.$user';
    if (!keys.containsKey(scope)) {
      if (!create) throw StateError('Missing key');
      keys[scope] = await AesGcm.with256bits().newSecretKey();
    }
    return OfflineVault(Directory('${folder.path}/$scope'), keys[scope]!);
  }
}

class PlanServer extends OfficeApi {
  PlanServer() {
    token = 'full-session';
  }
  String accountId = 'a' * 32, instanceId = 'f' * 32;
  Map<String, dynamic> currentUser = {'id': 'a' * 32, 'role': 'owner'};
  List<dynamic> currentProjects = const [];
  OfficeApi? _offlineTransport;
  OfficeApi get offlineTransport =>
      _offlineTransport ??= OfflineTestTransport(this);
  Map<String, dynamic> get binding => {
    'schema_version': 1,
    'instance_id': instanceId,
    'account_id': accountId,
  };
  Map<String, dynamic> v2Grant({
    String kind = 'workspace',
    List<String> extra = const [],
    DateTime? at,
    List<String> reports = const [],
  }) {
    final now = (at ?? DateTime.now()).toUtc();
    return {
      'schema_version': 2,
      'binding': binding,
      'token': 'offline_${kind}_v2_synthetic_$instanceId',
      'issued_at': now.toIso8601String(),
      'expires_at': now.add(const Duration(days: 7)).toIso8601String(),
      'capabilities': {
        'project_plans',
        'offline_plan_access',
        'plan_deletion',
        'project_workspace',
        'offline_workspace',
        ...extra,
      }.toList(),
      if (kind == 'business') ...{
        'report_project_ids': reports,
        'report_writes_enabled': true,
      },
    };
  }

  bool online = true, loseAck = false, forbidden = false;
  Completer<void>? hold;
  final started = Completer<void>();
  final plans = <String, Map<String, dynamic>>{};
  final requests = <String, Map<String, dynamic>>{};
  final sent = <String>[];
  int number = 0;
  @override
  Future<dynamic> call(String path, [Map<String, dynamic>? body]) async {
    if (!online) throw const ApiException(0, 'Offline');
    if (path == '/api/offline/context')
      return {'schema_version': 2, 'mode': 'bound_v2', 'binding': binding};
    if (path == '/api/offline/access/v2') return v2Grant();
    if (path == '/api/me') return Map<String, dynamic>.from(currentUser);
    if (path == '/api/projects' && body == null)
      return List<dynamic>.from(currentProjects);
    if (path == '/api/offline/logout') return {'ok': true};
    if (path.endsWith('/plan-deletions') && body == null) return <dynamic>[];
    if (forbidden) throw const ApiException(403, 'Access revoked');
    if (body == null)
      return path.endsWith('/plans')
          ? plans.values.toList()
          : plans[path.split('/').last];
    final requestId = body['request_id'] as String;
    sent.add(requestId);
    if (!started.isCompleted) started.complete();
    if (hold != null) await hold!.future;
    if (requests.containsKey(requestId)) return requests[requestId];
    final create = path.endsWith('/plans');
    final id = create ? 'server-${++number}' : path.split('/').last;
    if (!create && plans[id]!['revision'] != body['revision'])
      throw const ApiException(409, 'Conflict');
    final result = <String, dynamic>{
      'id': id,
      'project_id': 'project',
      'title': body['title'],
      'walls': body['walls'],
      'revision': create ? 1 : plans[id]!['revision'] + 1,
    };
    plans[id] = result;
    requests[requestId] = result;
    if (loseAck) {
      loseAck = false;
      throw const ApiException(0, 'Lost acknowledgement');
    }
    return result;
  }
}

/// The unit server and device transport have distinct credentials like the
/// production client, while requests still use the same controlled fixture.
class OfflineTestTransport extends OfficeApi {
  OfflineTestTransport(this.server);
  final OfficeApi server;
  @override
  Future<dynamic> call(String path, [Map<String, dynamic>? body]) =>
      server.call(path, body);
  @override
  Future<dynamic> putChunk(String path, Uint8List bytes) =>
      server.putChunk(path, bytes);
  @override
  Future<Uint8List> bytes(
    String path, {
    required String mediaType,
    int maxBytes = 20 * 1024 * 1024,
  }) => server.bytes(path, mediaType: mediaType, maxBytes: maxBytes);
}

Future<void> loginV2(
  OfflinePlans repo,
  Map<String, dynamic> user,
  List<dynamic> projects, {
  bool businessTime = false,
  bool fieldMedia = false,
  bool offlineReports = false,
}) async {
  final server = repo.api as PlanServer;
  server.accountId = user['id'];
  server.currentUser = user;
  server.currentProjects = projects;
  server.token = 'full-session-${user['id']}';
  await repo.login(
    user,
    projects,
    businessTime: businessTime,
    fieldMedia: fieldMedia,
    offlineReports: offlineReports,
  );
}

String v2TestNamespace(OfflinePlans repo, String account) => jsonEncode([
  'smartplan-offline-v2',
  repo.api.base,
  repo.api.version,
  (repo.api as PlanServer).instanceId,
  account,
]);

Future<void> idle(OfflinePlans repo) async {
  for (var i = 0; i < 1000; i++) {
    if (!repo.syncing) return;
    await Future<void>.delayed(const Duration(milliseconds: 2));
  }
  fail('Sync did not finish');
}

void main() {
  late Directory folder;
  late TestDevice device;
  late PlanServer server;
  late OfflinePlans repo;
  var now = DateTime.utc(2026, 10, 23);
  final user = <String, dynamic>{
    'id': 'a' * 32,
    'email': 'test@example.test',
    'role': 'owner',
  };
  final projects = [
    {'id': 'project', 'name': 'Test project'},
  ];
  setUp(() async {
    folder = await Directory.systemTemp.createTemp('smartplan-offline-test-');
    device = TestDevice(folder);
    server = PlanServer()..token = 'full-session';
    now = DateTime.utc(2026, 10, 23);
    repo = OfflinePlans(
      api: server,
      transport: server.offlineTransport,
      device: device,
      clock: () => now,
    );
    await loginV2(repo, user, projects);
    await idle(repo);
  });
  tearDown(() async {
    await idle(repo);
    repo.dispose();
    server.dispose();
    await folder.delete(recursive: true);
  });

  test('Encrypted drafts survive restart and then synchronize', () async {
    server.online = false;
    final plan = await repo.save('project', {
      'title': 'Private ground floor',
      'walls': [],
    });
    await idle(repo);
    expect(repo.pending, 1);
    final ciphertext = await folder
        .list(recursive: true)
        .where((f) => f.path.endsWith('.enc'))
        .cast<File>()
        .asyncMap((f) => f.readAsString())
        .join();
    expect(ciphertext, isNot(contains('Private ground floor')));
    await repo.leave();
    repo.dispose();
    now = now.add(const Duration(days: 1));
    repo = OfflinePlans(
      api: server,
      transport: server.offlineTransport,
      device: device,
      clock: () => now,
    );
    server.token = null; // A restarted offline app has no online identity.
    await repo.resume();
    await idle(repo);
    expect(repo.get(plan['local_id'])['title'], 'Private ground floor');
    server.online = true;
    await repo.sync();
    expect(repo.pending, 0);
    expect(server.plans, hasLength(1));
  });
  test(
    'Lost acknowledgement retries the identical operation without duplicates',
    () async {
      server.loseAck = true;
      await repo.save('project', {'title': 'EG', 'walls': []});
      await idle(repo);
      expect(repo.pending, 1);
      await repo.sync();
      expect(repo.pending, 0);
      expect(server.plans, hasLength(1));
      expect(server.sent.toSet(), hasLength(1));
    },
  );
  test('Edits during an upload remain queued for the next revision', () async {
    server.hold = Completer<void>();
    final first = await repo.save('project', {'title': 'First', 'walls': []});
    await server.started.future;
    await repo.save('project', {
      'title': 'Latest',
      'walls': [],
    }, localId: first['local_id']);
    server.hold!.complete();
    await idle(repo);
    expect(repo.pending, 0);
    expect(server.plans.values.single['title'], 'Latest');
    expect(server.plans.values.single['revision'], 2);
    expect(repo.get(first['local_id'])['title'], 'Latest');
  });
  test(
    'Conflict keeps both versions and offers a separate local copy',
    () async {
      final local = await repo.save('project', {'title': 'EG', 'walls': []});
      await idle(repo);
      server.plans.values.single['revision'] = 2;
      server.plans.values.single['title'] = 'Windows version';
      await repo.save('project', {
        'title': 'iPad version',
        'walls': [],
      }, localId: local['local_id']);
      await idle(repo);
      expect(repo.get(local['local_id'])['sync_status'], 'Konflikt');
      expect(repo.get(local['local_id'])['title'], 'iPad version');
      expect(repo.get(local['local_id'])['remote']['title'], 'Windows version');
      await repo.resolve(local['local_id'], keepCopy: true);
      await idle(repo);
      expect(server.plans, hasLength(2));
      expect(
        server.plans.values.map((p) => p['title']),
        containsAll(['Windows version', 'iPad version (lokale Kopie)']),
      );
    },
  );
  test(
    'Seven-day expiry retains pending data until online reauthentication',
    () async {
      server.online = false;
      await repo.save('project', {'title': 'Pending', 'walls': []});
      await idle(repo);
      now = now.add(const Duration(days: 7));
      expect(repo.permitted, false);
      expect(() => repo.list('project'), throwsA(isA<ApiException>()));
      expect(repo.pending, 1);
      server.online = true;
      await loginV2(repo, user, projects);
      await idle(repo);
      expect(repo.pending, 0);
      expect(server.plans.values.single['title'], 'Pending');
    },
  );
  test(
    'Account switching isolates data and failed unlock opens no workspace',
    () async {
      server.online = false;
      await repo.save('project', {'title': 'Account A', 'walls': []});
      await idle(repo);
      server.online = true;
      await loginV2(repo, {...user, 'id': 'b' * 32}, projects);
      expect(repo.list('project'), isEmpty);
      await repo.leave();
      device.unlocked = false;
      await expectLater(repo.resume(), throwsA(isA<ApiException>()));
      expect(repo.active, false);
    },
  );
  test('Clock rollback is rejected and corrupt newest commit is never silently reset', () async {
    server.online = false;
    await repo.save('project', {'title': 'Keep this', 'walls': []});
    await idle(repo);
    now = now.subtract(const Duration(hours: 1));
    expect(repo.permitted, false);
    now = now.add(const Duration(hours: 1));
    await repo.leave();
    final files = await folder
        .list(recursive: true)
        .where((f) => f.path.endsWith('.enc'))
        .toList();
    files.sort((a, b) => a.path.compareTo(b.path));
    await File(files.last.path).writeAsString('{broken');
    await expectLater(repo.resume(), throwsA(anything));
    expect(await File(files.last.path).readAsString(), '{broken');
  });
  test('Failed local write leaves the previous committed drawing and outbox unchanged', () async {
    server.online = false;
    final plan = await repo.save('project', {
      'title': 'Committed',
      'walls': [],
    });
    await idle(repo);
    final vault = await device.open(repo.storageNamespace, user['id']);
    final original = vault.directory.path;
    final backup = await vault.directory.rename('$original.backup');
    await File(original).writeAsString('Simulated unavailable directory');
    try {
      await expectLater(
        repo.save('project', {
          'title': 'Uncommitted',
          'walls': [],
        }, localId: plan['local_id']),
        throwsA(isA<FileSystemException>()),
      );
      expect(repo.get(plan['local_id'])['title'], 'Committed');
      expect(repo.pending, 1);
    } finally {
      await File(original).delete();
      await backup.rename(original);
    }
  });
  test('Known project revocation hides cached plans without deleting pending edits', () async {
    server.online = false;
    final plan = await repo.save('project', {
      'title': 'Keep pending',
      'walls': [],
    });
    await idle(repo);
    server.online = true;
    server.forbidden = true;
    await repo.sync();
    expect(repo.pending, 1);
    expect(repo.canAccessProject('project'), false);
    expect(() => repo.get(plan['local_id']), throwsA(isA<ApiException>()));
  });
}

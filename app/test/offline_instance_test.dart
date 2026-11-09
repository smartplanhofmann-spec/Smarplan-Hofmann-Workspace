import 'dart:async';
import 'dart:convert';
import 'dart:io';
import 'dart:typed_data';

import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:smartplan_office/offline_vault.dart';
import 'package:smartplan_office/api.dart';
import 'package:smartplan_office/offline_plans.dart';

import 'backend_integration_test.dart' show BackendHttp;
import 'offline_plans_test.dart' show PlanServer, TestDevice, idle, loginV2;

const account = 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa';
const user = {'id': account, 'role': 'owner', 'email': 'same@example.test'};
const projects = [
  {'id': 'project', 'name': 'Identischer Projektname'},
];

class SelectionGateDevice extends TestDevice {
  SelectionGateDevice(super.folder);
  final entered = Completer<void>(), release = Completer<void>();
  @override
  Future<void> select(String server, String user) async {
    if (server.contains('smartplan-offline-v2-selection')) {
      entered.complete();
      await release.future;
    }
    await super.select(server, user);
  }
}

class ProductionGateDevice extends OfflineDevice {
  ProductionGateDevice(Directory folder)
    : super(root: () async => folder, unlock: () async => true);
  bool delay = false, failWrites = false, failTokenDelete = false;
  @override
  Future<void> saveSession(String server, String user, String? token) async {
    if (token == null && failTokenDelete)
      throw const FileSystemException("Synthetic secure storage failure");
    await super.saveSession(server, user, token);
  }

  final entered = Completer<void>(), release = Completer<void>();
  @override
  Future<OfflineVault> open(
    String server,
    String user, {
    bool create = false,
  }) async {
    final vault = await super.open(server, user, create: create);
    return ProductionGateVault(vault, this);
  }
}

class ProductionGateVault extends OfflineVault {
  ProductionGateVault(OfflineVault vault, this.device)
    : super(vault.directory, vault.key);
  final ProductionGateDevice device;
  @override
  Future<void> write(Map<String, dynamic> state) async {
    if (device.failWrites)
      throw const FileSystemException("Synthetic full disk");
    if (device.delay) {
      device.delay = false;
      device.entered.complete();
      await device.release.future;
    }
    await super.write(state);
  }
}

class UnboundServer extends PlanServer {
  Object? fail;
  @override
  Future<dynamic> call(String path, [Map<String, dynamic>? body]) async {
    if (path == '/api/offline/context') {
      if (fail != null) throw fail!;
      return {'schema_version': 2, 'mode': 'unbound_legacy', 'binding': null};
    }
    return super.call(path, body);
  }
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  test('production secure-storage namespaces isolate keys tokens selection and a late A write', () async {
    FlutterSecureStorage.setMockInitialValues({});
    final temp = await Directory.systemTemp.createTemp(
      'offline-v2-real-device-',
    );
    final device = ProductionGateDevice(temp), server = PlanServer();
    final repo = OfflinePlans(
      api: server,
      transport: server.offlineTransport,
      device: device,
    );
    try {
      await loginV2(repo, user, projects);
      await idle(repo);
      final scopeA = repo.storageNamespace;
      final tokenA = await device.session(scopeA, account);
      server.online = false;
      device.delay = true;
      final saved = repo.save('project', {
        'title': 'A late original',
        'walls': [],
      });
      final interrupted = expectLater(saved, throwsA(isA<StateError>()));
      await device.entered.future;
      server.instanceId = 'b' * 32;
      server.online = true;
      var activatedB = false;
      final b = loginV2(repo, user, projects).then((_) => activatedB = true);
      await Future<void>.delayed(Duration.zero);
      expect(activatedB, isFalse);
      device.release.complete();
      await interrupted;
      await b;
      await idle(repo);
      final scopeB = repo.storageNamespace;
      final tokenB = await device.session(scopeB, account);
      expect(scopeB, isNot(scopeA));
      expect(tokenB, isNot(tokenA));
      expect(repo.list('project'), isEmpty);
      expect(repo.pending, 0);
      expect(server.sent, isEmpty);
      final a = await (await device.open(scopeA, account)).read();
      expect((a!['records'] as Map).values.single['title'], 'A late original');
      expect(a['outbox'], hasLength(1));
      final store = await const FlutterSecureStorage().readAll();
      final hashA = await device.namespace(scopeA),
          hashB = await device.namespace(scopeB);
      expect(store['smartplan.session.$hashA.$account'], tokenA);
      expect(store['smartplan.session.$hashB.$account'], tokenB);
      expect(
        store['smartplan.key.$hashA.$account'],
        isNot(store['smartplan.key.$hashB.$account']),
      );
      expect(store['smartplan.account.$hashA'], account);
      expect(store['smartplan.account.$hashB'], account);
      await repo.leave();
      server.token = null;
      await repo.resume();
      expect(repo.storageNamespace, scopeB);
      expect(repo.list('project'), isEmpty);
      await repo.leave();
      server.instanceId = 'f' * 32;
      await loginV2(repo, user, projects);
      await idle(repo);
      expect(repo.storageNamespace, scopeA);
      expect(repo.list('project').single['title'], 'A late original');
      expect(repo.pending, 0);
      expect(server.sent, hasLength(1));
    } finally {
      if (!device.release.isCompleted) device.release.complete();
      await repo.leave();
      repo.dispose();
      server.offlineTransport.dispose();
      server.dispose();
      await temp.delete(recursive: true);
    }
  });
  for (final storageFailure in ['vault', 'token']) {
    test(
      'logout clears active scope even when $storageFailure close fails',
      () async {
        FlutterSecureStorage.setMockInitialValues({});
        final temp = await Directory.systemTemp.createTemp(
          'offline-v2-logout-fault-',
        );
        final device = ProductionGateDevice(temp), server = PlanServer();
        final repo = OfflinePlans(
          api: server,
          transport: server.offlineTransport,
          device: device,
        );
        try {
          await loginV2(repo, user, projects);
          await idle(repo);
          server.online = false;
          await repo.save('project', {
            'title': 'Must remain on disk',
            'walls': [],
          });
          await idle(repo);
          final scope = repo.storageNamespace;
          device.failWrites = storageFailure == 'vault';
          device.failTokenDelete = storageFailure == 'token';
          await expectLater(repo.logout(), throwsA(isA<FileSystemException>()));
          expect(repo.active, isFalse);
          expect(repo.permitted, isFalse);
          expect(server.offlineTransport.token, isNull);
          device.failWrites = device.failTokenDelete = false;
          final state = await (await device.open(scope, account)).read();
          expect(
            (state!['records'] as Map).values.single['title'],
            'Must remain on disk',
          );
          expect(state['outbox'], hasLength(1));
          if (storageFailure == 'vault')
            expect(await device.session(scope, account), isNull);
          if (storageFailure == 'token') expect(state['locked'], isTrue);
          server.token = null;
          await expectLater(repo.resume(), throwsA(anything));
          expect(repo.active, isFalse);
          expect(server.sent, isEmpty);
        } finally {
          device.failWrites = device.failTokenDelete = false;
          await repo.leave();
          repo.dispose();
          server.offlineTransport.dispose();
          server.dispose();
          await temp.delete(recursive: true);
        }
      },
    );
  }

  for (final corruption in ['token', 'queue binding']) {
    test(
      'resume rejects a mismatched $corruption without sending preserved work',
      () async {
        final temp = await Directory.systemTemp.createTemp(
          'offline-v2-origin-check-',
        );
        final device = TestDevice(temp), server = PlanServer();
        final repo = OfflinePlans(
          api: server,
          transport: server.offlineTransport,
          device: device,
        );
        try {
          await loginV2(repo, user, projects);
          await idle(repo);
          server.online = false;
          await repo.save('project', {
            'title': 'Retain disputed original',
            'walls': [],
          });
          await idle(repo);
          final scope = repo.storageNamespace;
          final vault = await device.open(scope, account);
          if (corruption == 'token') {
            await device.saveSession(
              scope,
              account,
              'offline_workspace_v2_other_company',
            );
          } else {
            final state = (await vault.read())!;
            final refs = state['queue_bindings'] as Map;
            refs[refs.keys.single]['instance_id'] = 'b' * 32;
            await vault.write(state);
          }
          await repo.leave();
          server.token = null;
          await expectLater(repo.resume(), throwsA(isA<FormatException>()));
          expect(repo.active, isFalse);
          expect(server.sent, isEmpty);
          final kept = (await vault.read())!;
          expect(
            (kept['records'] as Map).values.single['title'],
            'Retain disputed original',
          );
          expect(kept['outbox'], hasLength(1));
        } finally {
          await repo.leave();
          repo.dispose();
          server.offlineTransport.dispose();
          server.dispose();
          await temp.delete(recursive: true);
        }
      },
    );
  }

  test('same server/account/project names never transfer company A queue into company B', () async {
    final temp = await Directory.systemTemp.createTemp('offline-v2-isolation-');
    final device = TestDevice(temp), server = PlanServer();
    final repo = OfflinePlans(
      api: server,
      transport: server.offlineTransport,
      device: device,
    );
    try {
      await loginV2(repo, user, projects);
      await idle(repo);
      final originA = repo.storageNamespace;
      server.online = false;
      final local = await repo.save('project', {
        'title': 'Nur Firma A',
        'walls': [],
      });
      await idle(repo);
      final aVault = await device.open(originA, account);
      final stateA = await aVault.read();
      final original = (stateA!['outbox'] as List).single;
      expect(
        (stateA['queue_bindings'] as Map).values.single['instance_id'],
        'f' * 32,
      );
      await repo.leave();
      server.online = true;
      server.instanceId = 'b' * 32;
      await loginV2(repo, user, projects);
      await idle(repo);
      expect(repo.storageNamespace, isNot(originA));
      expect(repo.list('project'), isEmpty);
      expect(repo.pending, 0);
      expect(server.sent, isEmpty);
      expect((await aVault.read())!['outbox'], [original]);
      expect(
        (await aVault.read())!['records'][local['local_id']]['title'],
        'Nur Firma A',
      );
      final originB = repo.storageNamespace;
      await repo.leave();
      server.instanceId = 'f' * 32;
      await loginV2(repo, user, projects);
      await idle(repo);
      expect(repo.storageNamespace, originA);
      expect(repo.pending, 0);
      expect(server.sent, [original['request_id']]);
      expect(
        (await (await device.open(originB, account)).read())!['outbox'],
        isEmpty,
      );
    } finally {
      await repo.leave();
      repo.dispose();
      server.offlineTransport.dispose();
      server.dispose();
      await temp.delete(recursive: true);
    }
  });

  test('logout during final selection leaves staged cache locked and never publishes it', () async {
    final temp = await Directory.systemTemp.createTemp('offline-v2-logout-');
    final device = SelectionGateDevice(temp), server = PlanServer();
    final repo = OfflinePlans(
      api: server,
      transport: server.offlineTransport,
      device: device,
    );
    try {
      final login = loginV2(repo, user, projects);
      final rejected = expectLater(login, throwsA(isA<ApiException>()));
      await device.entered.future;
      expect(repo.active, isFalse);
      final logout = repo.logout();
      device.release.complete();
      await rejected;
      await logout;
      expect(repo.active, isFalse);
      server.token = null;
      await expectLater(repo.resume(), throwsA(isA<ApiException>()));
      expect(repo.active, isFalse);
      final snapshots = await temp
          .list(recursive: true)
          .where((f) => f.path.endsWith('.enc'))
          .toList();
      expect(snapshots, isNotEmpty);
    } finally {
      if (!device.release.isCompleted) device.release.complete();
      await repo.leave();
      repo.dispose();
      server.offlineTransport.dispose();
      server.dispose();
      await temp.delete(recursive: true);
    }
  });

  test('unbound, missing and failed discovery preserve legacy bytes/keys/token without enabling fallback', () async {
    final temp = await Directory.systemTemp.createTemp('offline-v2-legacy-');
    final device = TestDevice(temp), server = UnboundServer();
    final repo = OfflinePlans(
      api: server,
      transport: server.offlineTransport,
      device: device,
    );
    final legacy = await device.open(repo.server, account, create: true);
    await legacy.write({
      'cache_schema': 1,
      'records': {
        'old': {'title': 'Ungesicherte Firma A'},
      },
      'outbox': [
        {'request_id': 'd' * 32},
      ],
    });
    await device.saveSession(repo.server, account, 'offline-old-token');
    await device.select(repo.server, account);
    final keys = Map.of(device.keys),
        sessions = Map.of(device.sessions),
        selections = Map.of(device.accounts);
    final old = await legacy.read();
    try {
      for (final failure in [
        null,
        const ApiException(404, 'Old server'),
        const ApiException(0, 'No network'),
      ]) {
        server.fail = failure;
        await expectLater(
          loginV2(repo, user, projects),
          throwsA(isA<ApiException>()),
        );
        expect(repo.active, isFalse);
        expect(device.keys, keys);
        expect(device.sessions, sessions);
        expect(device.accounts, selections);
        expect(await legacy.read(), old);
      }
      server.token = null;
      await expectLater(repo.resume(), throwsA(isA<ApiException>()));
      expect(repo.active, isFalse);
      expect(server.sent, isEmpty);
    } finally {
      await repo.leave();
      repo.dispose();
      server.offlineTransport.dispose();
      server.dispose();
      await temp.delete(recursive: true);
    }
  });

  test('real JSON, GET, binary PUT and file requests carry the captured original header', () async {
    await HttpOverrides.runWithHttpOverrides(() async {
      final server = await HttpServer.bind(InternetAddress.loopbackIPv4, 0);
      final received =
          <
            ({
              String method,
              String path,
              String? header,
              String? token,
              List<int> bytes,
            })
          >[];
      final held = Completer<void>(), entered = Completer<void>();
      server.listen((request) async {
        final body = <int>[];
        await for (final chunk in request) {
          body.addAll(chunk);
        }
        received.add((
          method: request.method,
          path: request.uri.path,
          header: request.headers.value('X-Smartplan-Offline-Binding'),
          token: request.headers.value('Authorization'),
          bytes: body,
        ));
        if (request.uri.path == '/held') {
          entered.complete();
          await held.future;
        }
        final binary = request.uri.path == '/file';
        request.response.headers.contentType = binary
            ? ContentType.binary
            : ContentType.json;
        request.response.add(binary ? [1, 2, 3] : utf8.encode('{"ok":true}'));
        await request.response.close();
      });
      final api = OfficeApi(baseUrl: 'http://127.0.0.1:${server.port}');
      final originA = '${'a' * 32}:${'b' * 32}',
          originB = '${'c' * 32}:${'b' * 32}';
      try {
        api.configureOfflineSession('offline_workspace_v2_first', originA);
        final first = api.call('/held');
        await entered.future;
        api.configureOfflineSession('offline_workspace_v2_second', originB);
        held.complete();
        await first;
        await api.call('/json', {
          'request_id': 'd' * 32,
          'title': 'Unverändert',
        });
        await api.putChunk('/chunk', Uint8List.fromList([8, 9]));
        expect(
          await api.bytes('/file', mediaType: 'application/octet-stream'),
          [1, 2, 3],
        );
        expect(received.first.header, originA);
        expect(received.first.token, 'Bearer offline_workspace_v2_first');
        expect(received.skip(1).every((r) => r.header == originB), isTrue);
        expect(received[2].method, 'PUT');
        expect(received[2].bytes, [8, 9]);
        api.token = 'offline_workspace_v2_unbound';
        await expectLater(api.call('/forbidden'), throwsA(isA<ApiException>()));
        expect(received, hasLength(4));
        api.token = 'normal-online-token';
        await api.call('/online');
        expect(received.last.header, isNull);
      } finally {
        if (!held.isCompleted) held.complete();
        api.dispose();
        await server.close(force: true);
      }
    }, BackendHttp());
  });
}

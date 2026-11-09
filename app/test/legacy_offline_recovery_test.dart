import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:smartplan_office/api.dart';
import 'package:smartplan_office/business_session.dart';
import 'package:smartplan_office/business_shell.dart';
import 'package:smartplan_office/legacy_offline_recovery.dart';
import 'package:smartplan_office/legacy_offline_recovery_page.dart';
import 'package:smartplan_office/offline_binding.dart';
import 'package:smartplan_office/offline_vault.dart';
import 'package:smartplan_office/offline_plans.dart';

import 'business_shell_widget_test.dart' show ShellApi;

final recoveryFixture = jsonDecode(
  File('test/fixtures/offline_binding_v2.json').readAsStringSync(),
) as Map<String, dynamic>;
Map<String, dynamic> clone(dynamic value) =>
    Map<String, dynamic>.from(jsonDecode(jsonEncode(value)));

class RecoveryServer extends OfficeApi {
  RecoveryServer()
    : super(baseUrl: 'https://same.example.test', apiVersion: 'v1') {
    token = 'synthetic-full-mfa-session';
  }
  Map<String, dynamic> binding = clone(recoveryFixture['context']['binding']);
  final lookups = <Map<String, dynamic>>[];
  ApiException? failure;
  bool corrupt = false, unbound = false;
  Completer<void>? entered, release;
  @override
  Future<dynamic> call(String path, [Map<String, dynamic>? body]) async {
    if (path == '/api/me') return {'id': recoveryFixture['account_id']};
    if (path == '/api/offline/context')
      return {
        'schema_version': 2,
        'mode': unbound ? 'unbound_legacy' : 'bound_v2',
        'binding': unbound ? null : binding,
      };
    expect(path, '/api/business/offline/recovery/lookup');
    lookups.add(clone(body));
    entered?.complete();
    await release?.future;
    if (failure != null) throw failure!;
    final response = clone(recoveryFixture['lookup_result']);
    response['nonce'] = body!['nonce'];
    response['lookup_hash'] = offlineBindingHash(body);
    if (corrupt)
      response['original']['title'] =
          'Self-consistent but different private original';
    return response;
  }
}

class RecoveryModel {
  RecoveryModel(this.root, this.api, this.device);
  final Directory root;
  final RecoveryServer api;
  final OfflineDevice device;
  OfflineVault? vault;
  Map<String, dynamic> command = clone(recoveryFixture['retained_command']);
  String get server => '${api.base}|${api.version}';
  String get account => recoveryFixture['account_id'];
  Map<String, dynamic> operation({Map<String, dynamic>? body}) => {
    'local_id': 'a' * 32,
    'project_id': recoveryFixture['lookup_command']['project_id'],
    'request_id': (body ?? command)['request_id'],
    'path':
        '/api/projects/${recoveryFixture['lookup_command']['project_id']}/plans',
    'body': clone(body ?? command),
    'snapshot': {'title': 'Sensitive unsent snapshot'},
  };
  Future<void> seed([List<dynamic>? operations]) async {
    vault = await device.open(server, account, create: true);
    await vault!.write({
      'cache_schema': 1,
      'user': {'id': account},
      'records': {
        'sensitive': {'title': 'A private old project title'},
      },
      'outbox': operations ?? [operation()],
      'business_time_outbox': [
        {'sensitive': 'Unassigned old time'},
      ],
    });
    await device.saveSession(server, account, 'offline_old_v1_synthetic');
    await device.select(server, account);
  }

  LegacyOfflineRecovery controller() =>
      LegacyOfflineRecovery(api: api, device: device);
  Future<Map<String, String>> bytes() async => {
    await for (final file in root.list(recursive: true))
      if (file is File) file.path: base64Encode(await file.readAsBytes()),
  };
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  late RecoveryModel m;
  setUp(() async {
    FlutterSecureStorage.setMockInitialValues({});
    final root = await Directory.systemTemp.createTemp(
      'smartplan-v1-readonly-',
    );
    m = RecoveryModel(
      root,
      RecoveryServer(),
      OfflineDevice(root: () async => root, unlock: () async => true),
    );
  });
  tearDown(() async {
    m.api.dispose();
    await m.root.delete(recursive: true);
  });
  test('only hash metadata leaves a real encrypted V1 vault; exact positive proof never rewrites original files keys token or selection', () async {
    await m.seed();
    final before = await m.bytes(),
        keys = await m.device.storage.readAll(),
        c = m.controller();
    await c.inspect();
    expect(c.plans.single.status, LegacyPlanStatus.unchecked);
    expect(c.otherPending, 1);
    expect(m.api.lookups, isEmpty);
    await c.check(0);
    expect(c.plans.single.status, LegacyPlanStatus.confirmed);
    expect(
      c.plans.single.serverTitle,
      recoveryFixture['lookup_result']['original']['title'],
    );
    final sent = m.api.lookups.single;
    expect(sent.keys.toSet(), {
      'schema_version',
      'nonce',
      'kind',
      'project_id',
      'plan_id',
      'request_id',
      'request_hash',
    });
    expect(jsonEncode(sent), isNot(contains(m.command['title'])));
    expect(sent.containsKey('walls'), isFalse);
    expect(await m.bytes(), before);
    expect(await m.device.storage.readAll(), keys);
    c.dispose();
  });
  test(
    'missing V1 vault does not create a key, selection, token or directory',
    () async {
      final c = m.controller();
      await c.inspect();
      expect(c.inspected, isTrue);
      expect(c.found, isFalse);
      expect(await m.bytes(), isEmpty);
      expect(await m.device.storage.readAll(), isEmpty);
      expect(m.api.lookups, isEmpty);
      c.dispose();
    },
  );
  test('denied device unlock, unbound context and offline token never authorize retained cache inspection or lookup', () async {
    await m.seed();
    final before = await m.bytes(), keys = await m.device.storage.readAll();
    final locked = OfflineDevice(
      root: () async => m.root,
      unlock: () async => false,
    );
    var c = LegacyOfflineRecovery(api: m.api, device: locked);
    await expectLater(c.inspect(), throwsA(isA<ApiException>()));
    expect(c.plans, isEmpty);
    c.dispose();
    m.api.unbound = true;
    c = m.controller();
    await expectLater(c.inspect(), throwsA(isA<ApiException>()));
    c.dispose();
    m.api.unbound = false;
    m.api.token = 'offline_workspace_v2_untrusted';
    c = m.controller();
    await expectLater(c.inspect(), throwsA(isA<ApiException>()));
    c.dispose();
    expect(m.api.lookups, isEmpty);
    expect(await m.bytes(), before);
    expect(await m.device.storage.readAll(), keys);
  });
  test('unprepared nonintegral and malformed old plans are retained without any recovery request', () async {
    final float = clone(m.command);
    float['walls'][0]['points'][0][0] = 0.25;
    await m.seed([
      {...m.operation(), 'body': null},
      m.operation(body: float),
      {...m.operation(), 'path': '/api/projects/${'e' * 32}/plans'},
    ]);
    final c = m.controller(), before = await m.bytes();
    await c.inspect();
    expect(c.plans.map((r) => r.status), [
      LegacyPlanStatus.unprepared,
      LegacyPlanStatus.unsupported,
      LegacyPlanStatus.unsupported,
    ]);
    for (var i = 0; i < 3; i++)
      await expectLater(c.check(i), throwsA(isA<ApiException>()));
    expect(m.api.lookups, isEmpty);
    expect(await m.bytes(), before);
    c.dispose();
  });
  test('a bound new cache or contradictory stored host is never interpreted as a V1 original', () async {
    await m.seed();
    final original = (await m.vault!.read())!;
    for (final changes in [
      {'cache_schema': 2},
      {'cache_schema': null},
      {'server': 'different.example.test|v1'},
    ]) {
      await m.vault!.write({...original, ...changes});
      final before = await m.bytes(), c = m.controller();
      await expectLater(c.inspect(), throwsA(isA<FormatException>()));
      expect(c.plans, isEmpty);
      expect(await m.bytes(), before);
      c.dispose();
    }
    expect(m.api.lookups, isEmpty);
  });
  test('a replacement firm cannot use an earlier positive receipt or a negative status as acceptance', () async {
    await m.seed();
    m.api.binding['instance_id'] = 'f' * 32;
    final c = m.controller();
    await c.inspect();
    await expectLater(c.check(0), throwsA(isA<ApiException>()));
    expect(c.plans.single.status, LegacyPlanStatus.unresolved);
    m.api.failure = const ApiException(404, 'Synthetic absent original');
    await expectLater(c.check(0), throwsA(isA<ApiException>()));
    expect(c.plans.single.status, LegacyPlanStatus.unresolved);
    expect(m.api.lookups, hasLength(2));
    c.dispose();
  });
  test('project revocation and altered positive contents keep original unresolved without any upload fallback', () async {
    await m.seed();
    final before = await m.bytes(), c = m.controller();
    await c.inspect();
    expect(c.plans.single.serverTitle, isNull);
    await c.check(0);
    expect(c.plans.single.serverTitle, isNotNull);
    m.api.failure = const ApiException(403, 'Synthetic project denied');
    await expectLater(c.check(0), throwsA(isA<ApiException>()));
    expect(c.plans.single.status, LegacyPlanStatus.unresolved);
    expect(c.plans.single.serverTitle, isNull);
    m.api.failure = null;
    m.api.corrupt = true;
    await expectLater(c.check(0), throwsA(isA<ApiException>()));
    expect(c.plans.single.status, LegacyPlanStatus.unresolved);
    expect(await m.bytes(), before);
    c.dispose();
  });
  test('changed original snapshot and changed current firm block lookup before POST', () async {
    await m.seed();
    final c = m.controller();
    await c.inspect();
    final state = (await m.vault!.read())!;
    await m.vault!.write({...state, 'changed': true});
    await expectLater(c.check(0), throwsA(isA<ApiException>()));
    expect(m.api.lookups, isEmpty);
    await c.inspect();
    m.api.binding['instance_id'] = 'e' * 32;
    await expectLater(c.check(0), throwsA(isA<ApiException>()));
    expect(m.api.lookups, isEmpty);
    c.dispose();
  });
  test('access change clears retained command RAM immediately before any further operation', () async {
    await m.seed();
    final before = await m.bytes(), access = ValueNotifier(true);
    final c = LegacyOfflineRecovery(
      api: m.api,
      device: m.device,
      allowed: () => access.value,
      accessChanges: access,
    );
    await c.inspect();
    expect(c.plans, hasLength(1));
    access.value = false;
    expect(c.plans, isEmpty);
    expect(c.found, isFalse);
    expect(await m.bytes(), before);
    expect(m.api.lookups, isEmpty);
    c.dispose();
    access.dispose();
  });
  test('late reply after logout clears RAM while encrypted original and secure entries stay untouched', () async {
    await m.seed();
    final c = m.controller(),
        before = await m.bytes(),
        keys = await m.device.storage.readAll();
    await c.inspect();
    m.api.entered = Completer();
    m.api.release = Completer();
    final checking = c.check(0);
    await m.api.entered!.future;
    m.api.token = 'different-mfa-session';
    m.api.release!.complete();
    await expectLater(checking, throwsA(isA<ApiException>()));
    expect(c.plans, isEmpty);
    expect(c.found, isFalse);
    expect(await m.bytes(), before);
    expect(await m.device.storage.readAll(), keys);
    c.dispose();
  });
  test('missing key, malformed newest commit and damaged newest ciphertext never fall back to an older snapshot', () async {
    await m.seed();
    final original = (await m.vault!.read())!;
    await m.vault!.write(original);
    final files = await m.vault!.directory
        .list()
        .where((f) => f.path.endsWith('.enc'))
        .toList();
    files.sort((a, b) => a.path.compareTo(b.path));
    await File(files.last.path).writeAsString('{broken');
    var before = await m.bytes();
    var c = m.controller();
    await expectLater(c.inspect(), throwsA(anything));
    expect(c.plans, isEmpty);
    expect(await m.bytes(), before);
    c.dispose();
    await File(files.last.path).delete();
    await File('${m.vault!.directory.path}/state-incomplete.enc')
        .writeAsString('retained');
    before = await m.bytes();
    c = m.controller();
    await expectLater(c.inspect(), throwsA(anything));
    expect(await m.bytes(), before);
    c.dispose();
    await File('${m.vault!.directory.path}/state-incomplete.enc').delete();
    await m.device.storage.delete(
      key: 'smartplan.key.${await m.device.namespace(m.server)}.${m.account}',
    );
    final keys = await m.device.storage.readAll();
    before = await m.bytes();
    c = m.controller();
    await expectLater(c.inspect(), throwsA(anything));
    expect(await m.bytes(), before);
    expect(await m.device.storage.readAll(), keys);
    c.dispose();
  });
  testWidgets(
    'actual mobile navigation opens the explicit inspection page without opening or uploading old data',
    (tester) async {
      tester.view.physicalSize = const Size(390, 844);
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.resetPhysicalSize);
      addTearDown(tester.view.resetDevicePixelRatio);
      final shellApi = ShellApi(),
          shellSession = BusinessSession(api: shellApi);
      final repository = OfflinePlans(api: shellApi, device: m.device);
      await shellSession.load();
      await tester.pumpWidget(
        MaterialApp(
          home: BusinessHome(
            session: shellSession,
            repository: repository,
            onProject: (_) {},
            onLegacy: () {},
            onLogout: () {},
          ),
        ),
      );
      await tester.pumpAndSettle();
      await tester.tap(find.byIcon(Icons.menu));
      await tester.pumpAndSettle();
      await tester.scrollUntilVisible(
        find.text('Alte Offline-Aufträge prüfen'),
        200,
        scrollable: find.descendant(
          of: find.byType(Drawer),
          matching: find.byType(Scrollable),
        ),
      );
      await tester.tap(find.text('Alte Offline-Aufträge prüfen'));
      await tester.pumpAndSettle();
      expect(find.text('Gerätebestand prüfen'), findsOneWidget);
      expect(find.text('Planauftrag 1'), findsNothing);
      expect(
        shellApi.calls.where(
          (c) =>
              c.path.endsWith('/offline/context') ||
              c.path.contains('/offline/recovery'),
        ),
        isEmpty,
      );
      expect(tester.takeException(), isNull);
      await tester.pumpWidget(const SizedBox.shrink());
      repository.dispose();
      shellSession.dispose();
      shellApi.dispose();
    },
  );
  testWidgets(
    '390px view shows only opaque status and survives biometric inactive transition, then clears private memory on pause',
    (tester) async {
      tester.view.physicalSize = const Size(390, 844);
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.resetPhysicalSize);
      addTearDown(tester.view.resetDevicePixelRatio);
      await tester.runAsync(() => m.seed());
      late Completer<void> entered;
      late Completer<bool> release;
      final device = OfflineDevice(
        root: () async => m.root,
        unlock: () {
          entered.complete();
          return release.future;
        },
      );
      final c = LegacyOfflineRecovery(api: m.api, device: device);
      await tester.pumpWidget(
        MaterialApp(home: LegacyOfflineRecoveryPage(recovery: c)),
      );
      await tester.runAsync(() async {
        entered = Completer<void>();
        release = Completer<bool>();
        await tester.tap(find.text('Gerätebestand prüfen'));
        await entered.future.timeout(const Duration(seconds: 10));
        tester.binding.handleAppLifecycleStateChanged(
          AppLifecycleState.inactive,
        );
        release.complete(true);
        final deadline = DateTime.now().add(const Duration(seconds: 15));
        while (c.busy) {
          if (DateTime.now().isAfter(deadline))
            throw StateError('Synthetic recovery did not finish after unlock');
          await Future<void>.delayed(const Duration(milliseconds: 5));
        }
      });
      await tester.pumpAndSettle();
      expect(find.text('Planauftrag 1'), findsOneWidget);
      expect(find.textContaining(m.command['title']), findsNothing);
      expect(find.textContaining('A private old project title'), findsNothing);
      await tester.ensureVisible(find.text('Ursprüngliche Annahme prüfen'));
      await tester.pumpAndSettle();
      await tester.runAsync(() async {
        await tester.tap(find.text('Ursprüngliche Annahme prüfen'));
        final deadline = DateTime.now().add(const Duration(seconds: 15));
        while (c.busy) {
          if (DateTime.now().isAfter(deadline))
            throw StateError('Synthetic hash lookup did not finish');
          await Future<void>.delayed(const Duration(milliseconds: 5));
        }
      });
      await tester.pumpAndSettle();
      expect(
        find.textContaining(
          recoveryFixture['lookup_result']['original']['title'],
        ),
        findsOneWidget,
      );
      expect(tester.takeException(), isNull);
      tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.paused);
      await tester.pump();
      expect(c.plans, isEmpty);
      tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.resumed);
      await tester.pumpWidget(const SizedBox.shrink());
    },
  );
}

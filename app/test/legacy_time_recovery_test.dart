import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:smartplan_office/api.dart';
import 'package:smartplan_office/legacy_offline_recovery.dart';
import 'package:smartplan_office/legacy_offline_recovery_page.dart';
import 'package:smartplan_office/offline_binding.dart';
import 'package:smartplan_office/offline_vault.dart';

final timeFixture = jsonDecode(
  File('test/fixtures/legacy_time_recovery.json').readAsStringSync(),
) as Map<String, dynamic>;
Map<String, dynamic> duplicate(dynamic value) =>
    Map<String, dynamic>.from(jsonDecode(jsonEncode(value)));

class TimeRecoveryApi extends OfficeApi {
  TimeRecoveryApi()
    : super(baseUrl: 'https://same.example.test', apiVersion: 'v1') {
    token = 'synthetic-full-time-session';
  }
  final binding = duplicate(timeFixture['binding']);
  final paths = <String>[], lookups = <Map<String, dynamic>>[];
  bool feature = true, permission = true, corrupt = false;
  ApiException? failure;
  Completer<void>? entered, release;
  void replaceSession() {
    token = 'synthetic-replaced-session';
    notifyListeners();
  }

  @override
  Future<dynamic> call(String path, [Map<String, dynamic>? body]) async {
    paths.add(path);
    if (path == '/api/me') return {'id': timeFixture['account_id']};
    if (path == '/api/offline/context')
      return {'schema_version': 2, 'mode': 'bound_v2', 'binding': binding};
    if (path == '/api/business/capabilities')
      return {
        'features': [if (feature) 'offline_time_event_recovery'],
        'capabilities': ['business_time'],
        'permissions': [if (permission) 'time.own'],
      };
    expect(path, '/api/business/offline/recovery/time-event');
    lookups.add(duplicate(body));
    entered?.complete();
    await release?.future;
    if (failure != null) throw failure!;
    final result = duplicate(timeFixture['lookup_result']);
    result['nonce'] = body!['nonce'];
    result['lookup_hash'] = offlineBindingHash(body);
    if (corrupt) {
      result['original']['core']['employee_id'] = 'f' * 32;
      result['original']['request_hash'] = offlineBindingHash(
        result['original']['core'],
      );
    }
    return result;
  }
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  late Directory root;
  late OfflineDevice device;
  late OfflineVault vault;
  late TimeRecoveryApi api;
  Future<Map<String, String>> bytes() async => {
    await for (final file in root.list(recursive: true))
      if (file is File) file.path: base64Encode(await file.readAsBytes()),
  };
  Future<void> seed({bool basis = true}) async {
    final record = duplicate(timeFixture['cache_record']);
    if (!basis) record.remove('employee_id');
    vault = await device.open(
      '${api.base}|${api.version}',
      timeFixture['account_id'],
      create: true,
    );
    await vault.write({
      'cache_schema': 1,
      'user': {'id': timeFixture['account_id']},
      'records': {},
      'outbox': [],
      'business_time_records': {record['id']: record},
      'business_time_outbox': [duplicate(timeFixture['retained_operation'])],
      'workspace_outbox': [
        {'private': 'Unproven old diary'},
      ],
    });
  }

  setUp(() async {
    FlutterSecureStorage.setMockInitialValues({});
    root = await Directory.systemTemp.createTemp('legacy-time-core-');
    api = TimeRecoveryApi();
    device = OfflineDevice(root: () async => root, unlock: () async => true);
  });
  tearDown(() async {
    api.dispose();
    await root.delete(recursive: true);
  });
  LegacyOfflineRecovery controller() =>
      LegacyOfflineRecovery(api: api, device: device);
  test('typed time proof uses old encrypted basis and never writes a cache key token selection or original event', () async {
    await seed();
    final before = await bytes(),
        keys = await device.storage.readAll(),
        c = controller();
    await c.inspect();
    expect(c.times, hasLength(1));
    expect(c.times.single.confirmation, isNull);
    expect(c.otherPending, 1);
    expect(api.lookups, isEmpty);
    await c.checkTime(0);
    expect(c.times.single.status, LegacyPlanStatus.confirmed);
    expect(c.times.single.confirmation!.action, 'stop');
    expect(
      api.lookups.single['request_hash'],
      timeFixture['lookup_command']['request_hash'],
    );
    expect(api.lookups.single.containsKey('body'), isFalse);
    expect(api.lookups.single.containsKey('employee_id'), isFalse);
    expect(await bytes(), before);
    expect(await device.storage.readAll(), keys);
    c.dispose();
  });
  test('unknown old employee basis never fetches a new profile or probes a time receipt', () async {
    await seed(basis: false);
    final before = await bytes(), c = controller();
    await c.inspect();
    expect(c.times, isEmpty);
    expect(c.otherPending, 2);
    expect(api.paths, isNot(contains('/api/business/capabilities')));
    expect(api.lookups, isEmpty);
    expect(await bytes(), before);
    c.dispose();
  });
  test('missing capability or fresh own-time permission preserves original without a lookup fallback', () async {
    await seed();
    api.feature = false;
    final c = controller(), before = await bytes();
    await c.inspect();
    expect(c.times, isEmpty);
    expect(c.otherPending, 2);
    api.feature = true;
    await c.inspect();
    expect(c.times, hasLength(1));
    api.permission = false;
    await expectLater(c.checkTime(0), throwsA(isA<ApiException>()));
    expect(c.times.single.confirmation, isNull);
    expect(c.times.single.status, LegacyPlanStatus.unresolved);
    expect(api.lookups, isEmpty);
    expect(await bytes(), before);
    c.dispose();
  });
  test(
    'replacement firm and changed old snapshot block before the metadata POST',
    () async {
      await seed();
      final c = controller();
      await c.inspect();
      api.binding['instance_id'] = 'f' * 32;
      await expectLater(c.checkTime(0), throwsA(isA<ApiException>()));
      expect(api.lookups, isEmpty);
      api.binding['instance_id'] = timeFixture['binding']['instance_id'];
      await c.inspect();
      final state = (await vault.read())!;
      await vault.write({...state, 'private_changed': true});
      final before = await bytes();
      await expectLater(c.checkTime(0), throwsA(isA<ApiException>()));
      expect(api.lookups, isEmpty);
      expect(await bytes(), before);
      c.dispose();
    },
  );
  test('failed or self-consistently swapped event core removes confirmed display without inventing nonacceptance', () async {
    await seed();
    final c = controller(), before = await bytes();
    await c.inspect();
    await c.checkTime(0);
    api.failure = const ApiException(404, 'Synthetic absent old event');
    await expectLater(c.checkTime(0), throwsA(isA<ApiException>()));
    expect(c.times.single.confirmation, isNull);
    expect(c.times.single.status, LegacyPlanStatus.unresolved);
    api.failure = null;
    api.corrupt = true;
    await expectLater(c.checkTime(0), throwsA(isA<ApiException>()));
    expect(c.times.single.confirmation, isNull);
    expect(await bytes(), before);
    c.dispose();
  });
  test('a late original after notified session replacement cannot republish cleared private memory', () async {
    await seed();
    final c = controller(), before = await bytes();
    await c.inspect();
    api.entered = Completer();
    api.release = Completer();
    final checking = c.checkTime(0);
    await api.entered!.future;
    api.replaceSession();
    expect(c.times, isEmpty);
    api.release!.complete();
    await expectLater(checking, throwsA(isA<ApiException>()));
    expect(c.times, isEmpty);
    expect(await bytes(), before);
    c.dispose();
  });
  testWidgets(
    '390px time row shows only status until current original proof and clears on real pause',
    (tester) async {
      tester.view.physicalSize = const Size(390, 844);
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.resetPhysicalSize);
      addTearDown(tester.view.resetDevicePixelRatio);
      await tester.runAsync(() => seed());
      final c = controller();
      await tester.pumpWidget(
        MaterialApp(home: LegacyOfflineRecoveryPage(recovery: c)),
      );
      Future<void> press(String title) async {
        await tester.ensureVisible(find.text(title));
        await tester.pumpAndSettle();
        await tester.runAsync(() async {
          await tester.tap(find.text(title));
          final deadline = DateTime.now().add(const Duration(seconds: 15));
          while (c.busy) {
            if (DateTime.now().isAfter(deadline))
              throw StateError('Synthetic time inspection did not finish');
            await Future<void>.delayed(const Duration(milliseconds: 5));
          }
        });
        await tester.pumpAndSettle();
      }

      await press('Gerätebestand prüfen');
      expect(find.text('Zeitauftrag 1'), findsOneWidget);
      expect(find.textContaining('Ende ·'), findsNothing);
      await press('Ursprüngliches Zeitereignis prüfen');
      expect(find.textContaining('Ende ·'), findsOneWidget);
      expect(tester.takeException(), isNull);
      tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.paused);
      await tester.pump();
      expect(c.times, isEmpty);
      tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.resumed);
      await tester.pumpWidget(const SizedBox.shrink());
    },
  );
}

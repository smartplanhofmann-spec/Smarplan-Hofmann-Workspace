import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:smartplan_office/api.dart';
import 'package:smartplan_office/offline_binding.dart';
import 'package:smartplan_office/offline_report_recovery.dart';
import 'package:smartplan_office/offline_vault.dart';
import 'package:smartplan_office/legacy_offline_recovery.dart';
import 'package:smartplan_office/legacy_offline_recovery_page.dart';

import 'legacy_offline_recovery_test.dart' as base;

final reportFixture = jsonDecode(
  File('test/fixtures/legacy_report_recovery.json').readAsStringSync(),
) as Map<String, dynamic>;
Map<String, dynamic> clone(dynamic v) =>
    Map<String, dynamic>.from(jsonDecode(jsonEncode(v)) as Map);
List<Map<String, dynamic>> get cases => [
  for (final v in reportFixture['cases']) clone(v),
];
final account = reportFixture['account_id'] as String;

class ReportServer extends base.RecoveryServer {
  ReportServer() : super() {
    binding = clone(reportFixture['binding']);
  }
  bool feature = true;
  final reportQueries = <Map<String, dynamic>>[];
  @override
  Future<dynamic> call(String path, [Map<String, dynamic>? body]) async {
    if (path == '/api/me') return {'id': account};
    if (path == '/api/business/capabilities')
      return {
        'features': [if (feature) legacyReportRecoveryFeature],
        'capabilities': ['business_operations'],
        'permissions': ['documents.read'],
      };
    if (path == '/api/business/offline/recovery/service-report') {
      reportQueries.add(clone(body));
      entered?.complete();
      await release?.future;
      if (failure != null) throw failure!;
      final original = cases.singleWhere(
        (c) => c['command']['entry_id'] == body!['entry_id'],
      );
      final response = clone(original['response']);
      response['nonce'] = body!['nonce'];
      response['lookup_hash'] = offlineBindingHash(body);
      if (corrupt) response['original']['signature_sha256'] = '0' * 64;
      return response;
    }
    return super.call(path, body);
  }
}

class ReportModel extends base.RecoveryModel {
  ReportModel(super.root, ReportServer super.api, super.device);
  @override
  String get account => reportFixture['account_id'];
  Future<void> seedReports() async {
    await seed([]);
    final state = (await vault!.read())!;
    state['service_report_outbox'] = [for (final c in cases) c['record']['id']];
    state['service_report_records'] = {
      for (final c in cases) c['record']['id']: c['record'],
    };
    await vault!.write(state);
  }
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  test('both actual original archives bind exact binary64 coordinates and signature hashes', () {
    for (final c in cases) {
      final original = LegacyReportOriginal.fromCache(
        c['record'],
        accountId: account,
      );
      expect(original.query(nonce: c['command']['nonce']), c['command']);
      expect(
        original.signatureHash,
        c['response']['original']['signature_sha256'],
      );
      final proof = original.match(
        c['response'],
        request: clone(c['command']),
        binding: OfflineBinding.fromJson(reportFixture['binding']),
      );
      expect(proof.pdfSha256, c['accepted']['pdf_sha256']);
    }
    expect(legacyReportProofHash([-0.0]), isNot(legacyReportProofHash([0.0])));
    expect(legacyReportProofHash([1]), isNot(legacyReportProofHash([1.0])));
  });
  test('changed private signed record or mismatched archive cannot become confirmed', () {
    final c = cases.first;
    for (final alter in <void Function(Map<String, dynamic>)>[
      (v) => v['capture_request']['content']['title'] += 'changed',
      (v) => v['strokes'][0][0][0] = 0.5,
      (v) => v['capture_request']['strokes'][0][0][0] = double.nan,
      (v) => v['content_hash'] = '0' * 64,
      (v) => v['signer'] = 'another signer',
      (v) => v['status'] = 'draft',
    ]) {
      final value = clone(c['record']);
      alter(value);
      expect(
        () => LegacyReportOriginal.fromCache(value, accountId: account),
        throwsException,
      );
    }
    final original = LegacyReportOriginal.fromCache(
      c['record'],
      accountId: account,
    );
    for (final alter in <void Function(Map<String, dynamic>)>[
      (v) => v['nonce'] = 'f' * 32,
      (v) => v['binding']['instance_id'] = 'f' * 32,
      (v) => v['original']['signature_sha256'] = '0' * 64,
      (v) => v['original']['content_hash'] = '0' * 64,
      (v) => v['original']['actor_id'] = 'f' * 32,
      (v) => v['original']['revision'] = 1,
      (v) => v['original']['request_hash'] = 'unknown',
      (v) => v['original']['received_at'] = '1900-01-01T00:00:00Z',
      (v) => v['original']['content'] = {'unexpected': 'private original'},
    ]) {
      final value = clone(c['response']);
      alter(value);
      expect(
        () => original.match(
          value,
          request: clone(c['command']),
          binding: OfflineBinding.fromJson(reportFixture['binding']),
        ),
        throwsException,
      );
    }
  });

  group('real encrypted retained V1 report cache', () {
    late ReportModel model;
    late ReportServer api;
    setUp(() async {
      FlutterSecureStorage.setMockInitialValues({});
      final root = await Directory.systemTemp.createTemp(
        'smartplan-v1-reports-',
      );
      api = ReportServer();
      model = ReportModel(
        root,
        api,
        OfflineDevice(root: () async => root, unlock: () async => true),
      );
      addTearDown(api.dispose);
      addTearDown(() => root.delete(recursive: true));
      await model.seedReports();
    });
    test('only hashes leave the vault; keys, session, files, generation and pending originals remain exact', () async {
      final before = await model.bytes(),
          keys = await model.device.storage.readAll();
      final c = model.controller();
      addTearDown(c.dispose);
      await c.inspect();
      expect(c.reports.length, 2);
      expect(c.otherPending, 1);
      expect(api.reportQueries, isEmpty);
      for (var i = 0; i < c.reports.length; i++) await c.checkReport(i);
      expect(
        c.reports.every((r) => r.status == LegacyPlanStatus.confirmed),
        true,
      );
      for (final query in api.reportQueries) {
        expect(query.keys.toSet(), {
          'schema_version',
          'nonce',
          'kind',
          'project_id',
          'entry_id',
          'request_id',
          'capture_hash',
        });
        expect(
          jsonEncode(query),
          isNot(contains(cases.first['record']['description'])),
        );
        expect(query.containsKey('signer'), false);
        expect(query.containsKey('strokes'), false);
      }
      expect(await model.bytes(), before);
      expect(await model.device.storage.readAll(), keys);
    });
    test('missing new feature leaves both originals in quarantine without querying them', () async {
      api.feature = false;
      final c = model.controller();
      addTearDown(c.dispose);
      await c.inspect();
      expect(c.reports, isEmpty);
      expect(c.otherPending, 3);
      expect(api.reportQueries, isEmpty);
    });
    test('feature loss or changed company sends no old original and preserves every byte', () async {
      final before = await model.bytes(), c = model.controller();
      addTearDown(c.dispose);
      await c.inspect();
      api.feature = false;
      await expectLater(c.checkReport(0), throwsException);
      expect(api.reportQueries, isEmpty);
      api.feature = true;
      api.binding['instance_id'] = 'f' * 32;
      await expectLater(c.checkReport(0), throwsException);
      expect(api.reportQueries, isEmpty);
      expect(await model.bytes(), before);
    });
    test('unknown acceptance and a false signature remain unresolved without cache rewriting', () async {
      final before = await model.bytes(), c = model.controller();
      addTearDown(c.dispose);
      await c.inspect();
      api.failure = const ApiException(404, 'Synthetic missing old original');
      await expectLater(c.checkReport(0), throwsException);
      expect(c.reports.first.status, LegacyPlanStatus.unresolved);
      api.failure = null;
      api.corrupt = true;
      await expectLater(c.checkReport(0), throwsException);
      expect(c.reports.first.confirmation, isNull);
      expect(await model.bytes(), before);
    });
    test('clearing private context before a late reply never restores its metadata', () async {
      final before = await model.bytes(), c = model.controller();
      addTearDown(c.dispose);
      await c.inspect();
      api.entered = Completer<void>();
      api.release = Completer<void>();
      final attempt = c.checkReport(0);
      final failed = expectLater(attempt, throwsException);
      await api.entered!.future;
      c.clear();
      api.release!.complete();
      await failed;
      expect(c.reports, isEmpty);
      expect(await model.bytes(), before);
    });
    test('a changed encrypted snapshot during lookup prevents acceptance of the old view', () async {
      final c = model.controller();
      addTearDown(c.dispose);
      await c.inspect();
      api.entered = Completer<void>();
      api.release = Completer<void>();
      final attempt = c.checkReport(0),
          failed = expectLater(attempt, throwsException);
      await api.entered!.future;
      final state = (await model.vault!.read())!
        ..['separately_changed'] = 'Synthetic independent writer';
      await model.vault!.write(state);
      final changed = await model.bytes();
      api.release!.complete();
      await failed;
      expect(c.reports.first.confirmation, isNull);
      expect(await model.bytes(), changed);
    });
    testWidgets(
      '390px view identifies each old report without exposing unproved text or sending it again',
      (t) async {
        t.view.physicalSize = const Size(390, 844);
        t.view.devicePixelRatio = 1;
        addTearDown(t.view.resetPhysicalSize);
        addTearDown(t.view.resetDevicePixelRatio);
        final c = model.controller();
        final before = await t.runAsync(() async {
          final bytes = await model.bytes();
          await c.inspect();
          return bytes;
        });
        await t.pumpWidget(
          MaterialApp(home: LegacyOfflineRecoveryPage(recovery: c)),
        );
        await t.pumpAndSettle();
        expect(
          find.textContaining(cases.first['record']['title']),
          findsNothing,
        );
        await t.scrollUntilVisible(find.text('Protokollauftrag 1'),180,maxScrolls:10);
        final card=find.ancestor(of:find.text('Protokollauftrag 1'),matching:find.byType(Card));
        final button = find.descendant(of:card,matching:find.text('Ursprüngliches Protokoll prüfen'));
        await t.ensureVisible(button);
        await t.runAsync(() async {
          await t.tap(button);
          final deadline = DateTime.now().add(const Duration(seconds: 15));
          while (c.busy) {
            if (DateTime.now().isAfter(deadline))
              throw StateError('Synthetic report inspection did not finish');
            await Future<void>.delayed(const Duration(milliseconds: 5));
          }
        });
        await t.pumpAndSettle();
        expect(
          find.textContaining('Passende unterschriebene Archivfassung'),
          findsOneWidget,
        );
        expect(api.reportQueries.length, 1);
        expect(await t.runAsync(model.bytes), before);
        expect(t.takeException(), isNull);
        await t.pumpWidget(const SizedBox());
        await t.pump();
      },
    );
  });
}

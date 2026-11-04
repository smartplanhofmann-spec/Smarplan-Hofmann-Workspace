import 'dart:async';
import 'dart:convert';

import 'package:file_selector/file_selector.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:smartplan_office/api.dart';
import 'package:smartplan_office/business_accounting_historical_assets.dart';
import 'package:smartplan_office/business_session.dart';
import 'package:smartplan_office/business_accounting_euer.dart';

import 'business_accounting_historical_assets_contract_test.dart'
    show historicalFixture, historicalCopy;

class HistoricalApi extends OfficeApi {
  HistoricalApi() : super(apiVersion: 'v1') {
    token = 'synthetic-historical-actor';
  }
  bool read = true, write = true, lose = false, wrong = false;
  int generation = 1;
  Completer<dynamic>? heldHistory, heldPreview, heldIdentity;
  final posts = <Map<String, dynamic>>[];
  @override
  Future<dynamic> call(String path, [Map<String, dynamic>? body]) async {
    final f = historicalFixture;
    if (path.endsWith('/capabilities'))
      return {
        'compatibility_mode': 'business',
        'generation': generation,
        'storage_version': 13,
        'readonly': false,
        'features': [
          'accounting_historical_assets',
          'accounting_euer',
          'accounting_prejournal',
        ],
        'capabilities': [
          'business_accounting_asset_openings',
          'business_accounting_euer',
          'business_accounting',
        ],
        'permissions': [
          'accounting.read',
          if (read) 'finance.read',
          if (write) ...[
            'accounting.admin',
            'accounting.prepare',
            'finance.write',
          ],
        ],
      };
    if (path == '/api/business$historicalAssetPath')
      return historicalCopy(f['state_after']);
    if (path.contains('$historicalAssetPath/history?'))
      return heldHistory?.future ?? historicalCopy(f['history']);
    if (path == '/api/business/accounting/euer')
      return historicalCopy(f['euer_state']);
    if (path == '/api/business/accounting/euer/sources')
      return historicalCopy(f['euer_sources']);
    if (path.contains('/accounting/euer/journal?'))
      return {'items': [], 'next_offset': null};
    if (path == '/api/business/accounting/accounts') return {'items': []};
    if (path.contains('/accounting/euer/report?'))
      return historicalCopy(f['euer_report_before']);
    if (path.endsWith('$historicalAssetPath/identity'))
      return heldIdentity?.future ??
          {
            'schema_version': 1,
            'inventory_number': body!['inventory_number'],
            'asset_key': f['saved']['asset_key'],
          };
    if (body != null) {
      posts.add(historicalCopy(body));
      if (path.endsWith('/preview')) return heldPreview!.future;
      if (lose) {
        lose = false;
        throw const ApiException(0, 'Synthetic ACK lost');
      }
      if (path.endsWith('/originals')) return historicalCopy(f['original']);
      return historicalCopy(wrong ? f['correction'] : f['saved']);
    }
    throw StateError('Unexpected historical route: $path');
  }
}

Future<void> historicalTap(WidgetTester tester, String text) async {
  final scroll = find.byType(Scrollable).first;
  tester.state<ScrollableState>(scroll).position.jumpTo(0);
  await tester.pump();
  final f = find.text(text);
  await tester.scrollUntilVisible(f, 250, scrollable: scroll);
  await tester.ensureVisible(f.first);
  await tester.pumpAndSettle();
  await tester.tap(f.first);
  await tester.pump();
}

Future<void> historicalEnter(
  WidgetTester tester,
  String label,
  String text,
) async {
  final scroll = find.byType(Scrollable).first;
  tester.state<ScrollableState>(scroll).position.jumpTo(0);
  await tester.pump();
  final f = find.byWidgetPredicate(
    (v) => v is TextField && v.decoration?.labelText == label,
  );
  await tester.scrollUntilVisible(f, 250, scrollable: scroll);
  await tester.ensureVisible(f);
  await tester.pumpAndSettle();
  await tester.enterText(f, text);
  await tester.pump();
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  test('unknown historical ACK preserves exact original nonce, source proof and validator across generation and revoked write access', () async {
    final api = HistoricalApi();
    final s = BusinessSession(api: api);
    addTearDown(s.dispose);
    await s.load();
    expect(historicalAssetsWritable(s), true);
    expect(s.can('bank.read'), false);
    api.lose = true;
    final command = historicalCopy(historicalFixture['command'])
      ..remove('request_id');
    await expectLater(
      s.command(
        'historical-asset-confirm',
        '$historicalAssetPath/confirm',
        command,
        validateResult: historicalAssetReceipt(
          historicalCopy(historicalFixture['preview']),
        ),
      ),
      throwsA(isA<ApiException>()),
    );
    expect(s.pendingHistoricalAssetKeys, ['historical-asset-confirm']);
    api.generation = 2;
    api.write = false;
    await expectLater(
      s.repeatHistoricalAssetCommand('historical-asset-confirm'),
      throwsA(isA<ApiException>()),
    );
    expect(api.posts.length, 1);
    api.write = true;
    api.wrong = true;
    await expectLater(
      s.repeatHistoricalAssetCommand('historical-asset-confirm'),
      throwsA(isA<ApiException>()),
    );
    expect(s.pendingHistoricalAssetKeys, isNotEmpty);
    api.wrong = false;
    await s.repeatHistoricalAssetCommand('historical-asset-confirm');
    expect(api.posts[0], api.posts[1]);
    expect(api.posts[1], api.posts[2]);
    expect(s.pendingHistoricalAssetKeys, isEmpty);
  });
  Future<void> open(
    WidgetTester t,
    HistoricalApi api,
    BusinessSession s, {
    Future<XFile?> Function()? picker,
  }) async {
    await s.load();
    await t.pumpWidget(
      MaterialApp(
        home: BusinessHistoricalAssetsPage(
          session: s,
          assetKey: historicalFixture['saved']['asset_key'],
          pickFile: picker,
        ),
      ),
    );
    await t.pumpAndSettle();
    expect(find.textContaining('Bestätigter Anlagenstand:'), findsOneWidget);
  }

  testWidgets(
    'held historical source is discarded after fresh capability read detects silent read revocation',
    (t) async {
      final api = HistoricalApi();
      final session = BusinessSession(api: api);
      await open(t, api, session);
      api.heldHistory = Completer<dynamic>();
      await t.tap(find.byTooltip('Anlagenstand aktualisieren'));
      await t.pump();
      api.read = false;
      api.heldHistory!.complete(historicalCopy(historicalFixture['history']));
      await t.pumpAndSettle();
      expect(
        find.text('Historische Anlagen nicht freigegeben'),
        findsOneWidget,
      );
      expect(find.textContaining('Synthetic historical'), findsNothing);
      expect(t.takeException(), null);
      await t.pumpWidget(const SizedBox.shrink());
      session.dispose();
    },
  );
  testWidgets(
    'pending picker after session read loss sends no original bytes',
    (t) async {
      final api = HistoricalApi();
      final session = BusinessSession(api: api), pick = Completer<XFile?>();
      await open(t, api, session, picker: () => pick.future);
      await historicalTap(t, 'Anlagenvortrag berichtigen');
      await t.pumpAndSettle();
      await historicalTap(t, 'Historisches Anlagenoriginal hochladen');
      api.read = false;
      await session.load();
      await t.pump();
      pick.complete(
        XFile.fromData(
          base64Decode(historicalFixture['original_upload']['content_base64']),
          name: 'synthetic.pdf',
        ),
      );
      await t.pumpAndSettle();
      expect(api.posts, isEmpty);
      expect(
        find.text('Historische Anlagen nicht freigegeben'),
        findsOneWidget,
      );
      await t.pumpWidget(const SizedBox.shrink());
      session.dispose();
    },
  );
  testWidgets(
    'session replacement removes historical fields and typed source reason including editor',
    (t) async {
      final api = HistoricalApi(), s = BusinessSession(api: api);
      await open(t, api, s);
      await historicalTap(t, 'Anlagenvortrag berichtigen');
      await t.pumpAndSettle();
      await historicalEnter(
        t,
        'Prüf-, Korrektur- oder Aufhebungsgrund',
        'Private old historical draft',
      );
      final other = BusinessSession(api: HistoricalApi()..read = false);
      await other.load();
      await t.pumpWidget(
        MaterialApp(home: BusinessHistoricalAssetsPage(session: other)),
      );
      await t.pumpAndSettle();
      expect(find.text('Private old historical draft'), findsNothing);
      expect(find.byType(TextField), findsNothing);
      expect(
        find.text('Historische Anlagen nicht freigegeben'),
        findsOneWidget,
      );
      await t.pumpWidget(const SizedBox.shrink());
      s.dispose();
      other.dispose();
    },
  );
  testWidgets(
    'delayed preview cannot publish original values after silent permission withdrawal',
    (t) async {
      final api = HistoricalApi(), session = BusinessSession(api: api);
      await open(t, api, session);
      await historicalTap(t, 'Anlagenvortrag berichtigen');
      await t.pumpAndSettle();
      await historicalEnter(
        t,
        'Bezeichnung der historischen Anlage',
        historicalFixture['correction_preview_request']['asset']['description'],
      );
      await historicalEnter(
        t,
        'Prüf-, Korrektur- oder Aufhebungsgrund',
        historicalFixture['correction_preview_request']['reason'],
      );
      await historicalTap(
        t,
        'Originalwerte, ausschließlich betriebliche bewegliche Anlage und unveränderte lineare Historie einschließlich bisheriger Rundung ausdrücklich geprüft.',
      );
      await t.pumpAndSettle();
      api.heldPreview = Completer<dynamic>();
      await historicalTap(t, 'Anlagenvortrag unverbindlich prüfen');
      await t.pump();
      expect(api.posts.single, historicalFixture['correction_preview_request']);
      api.read = false;
      api.heldPreview!.complete(
        historicalCopy(historicalFixture['correction_preview']),
      );
      await t.pumpAndSettle();
      expect(
        find.text('Historische Anlagen nicht freigegeben'),
        findsOneWidget,
      );
      expect(find.text('Geprüfte historische Übernahme'), findsNothing);
      expect(find.byType(TextField), findsNothing);
      await t.pumpWidget(const SizedBox.shrink());
      session.dispose();
    },
  );
  testWidgets(
    'background invalidates held history and draft; resume requires explicit fresh reload',
    (t) async {
      final api = HistoricalApi(), s = BusinessSession(api: api);
      await open(t, api, s);
      await historicalTap(t, 'Anlagenvortrag berichtigen');
      await t.pumpAndSettle();
      await historicalEnter(
        t,
        'Prüf-, Korrektur- oder Aufhebungsgrund',
        'Private background draft',
      );
      api.heldHistory = Completer<dynamic>();
      await t.tap(find.byTooltip('Anlagenstand aktualisieren'));
      await t.pump();
      for (final v in [
        AppLifecycleState.inactive,
        AppLifecycleState.hidden,
        AppLifecycleState.paused,
      ]) {
        t.binding.handleAppLifecycleStateChanged(v);
        await t.pump();
      }
      api.heldHistory!.complete(historicalCopy(historicalFixture['history']));
      api.heldHistory = null;
      await t.pumpAndSettle();
      for (final v in [
        AppLifecycleState.hidden,
        AppLifecycleState.inactive,
        AppLifecycleState.resumed,
      ]) {
        t.binding.handleAppLifecycleStateChanged(v);
        await t.pump();
      }
      expect(
        find.text('Historische Anlagen nicht freigegeben'),
        findsOneWidget,
      );
      expect(find.text('Private background draft'), findsNothing);
      await t.tap(find.byTooltip('Anlagenstand aktualisieren'));
      await t.pumpAndSettle();
      expect(find.textContaining('Bestätigter Anlagenstand:'), findsOneWidget);
      expect(t.takeException(), null);
      await t.pumpWidget(const SizedBox.shrink());
      s.dispose();
    },
  );
  testWidgets(
    'actual historical EÜR editor clears private inputs and title on write withdrawal and on background',
    (t) async {
      for (final background in [false, true]) {
        final api = HistoricalApi(), session = BusinessSession(api: api);
        await session.load();
        await t.pumpWidget(
          MaterialApp(
            home: BusinessEuerPage(
              session: session,
              initialYear: 2026,
              initialHistoricalAssetId: historicalFixture['saved']['id'],
            ),
          ),
        );
        await t.pumpAndSettle();
        expect(find.byType(AlertDialog), findsOneWidget);
        final reason = find.byWidgetPredicate(
          (v) =>
              v is TextField &&
              v.decoration?.labelText == 'Fachliche Begründung',
        );
        await t.enterText(reason, 'Private historical AfA draft');
        if (background) {
          for (final v in [
            AppLifecycleState.inactive,
            AppLifecycleState.hidden,
            AppLifecycleState.paused,
          ]) {
            t.binding.handleAppLifecycleStateChanged(v);
            await t.pump();
          }
        } else {
          api.write = false;
          await session.load();
          await t.pumpAndSettle();
        }
        expect(find.text('Private historical AfA draft'), findsNothing);
        expect(find.text('Belegte historische Jahres-AfA'), findsNothing);
        expect(find.byType(TextField), findsNothing);
        expect(find.text('Zugang geändert'), findsOneWidget);
        expect(t.takeException(), null);
        await t.pumpWidget(const SizedBox.shrink());
        session.dispose();
        if (background) {
          for (final v in [
            AppLifecycleState.hidden,
            AppLifecycleState.inactive,
            AppLifecycleState.resumed,
          ]) {
            t.binding.handleAppLifecycleStateChanged(v);
            await t.pump();
          }
        }
      }
    },
  );
}

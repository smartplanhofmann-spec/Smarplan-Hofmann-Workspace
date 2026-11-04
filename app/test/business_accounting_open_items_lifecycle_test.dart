import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:smartplan_office/api.dart';
import 'package:smartplan_office/business_accounting_open_items.dart';
import 'package:smartplan_office/business_session.dart';

import 'business_accounting_open_items_contract_test.dart'
    show openItemsFixture;

class OpenItemsApi extends OfficeApi {
  OpenItemsApi() : super(apiVersion: 'v1') {
    token = 'synthetic-opening-items-worker';
  }
  bool read = true, write = true, lose = false, wrong = false;
  int generation = 1;
  String stateName = 'final_state';
  Completer<dynamic>? heldPreview;
  Completer<dynamic>? heldHistory, heldSource, heldAccounts, heldCapabilities;
  final posts = <Map<String, dynamic>>[];
  Map<String, dynamic> get f => openItemsFixture['receivable_prior_parts'];
  Map<String, dynamic> capabilities() => {
    'compatibility_mode': 'business',
    'generation': generation,
    'storage_version': 16,
    'readonly': false,
    'features': ['accounting_open_items'],
    'capabilities': ['business_accounting_open_items'],
    'permissions': [
      'accounting.read',
      if (read) 'finance.read',
      if (write) ...['accounting.admin', 'accounting.prepare', 'finance.write'],
    ],
  };
  @override
  Future<dynamic> call(String path, [Map<String, dynamic>? body]) async {
    if (path.endsWith('/capabilities'))
      return heldCapabilities?.future ?? capabilities();
    if (path == '/api/business$openItemPath') return openItemCopy(f[stateName]);
    if (path == '/api/business/accounting/accounts')
      return heldAccounts?.future ?? openItemCopy(f['accounts']);
    if (path.contains('$openItemPath/history?'))
      return heldHistory?.future ?? openItemCopy(f['history']);
    if (path.contains('$openItemPath/payments/'))
      return heldSource?.future ?? openItemCopy(f['payments'][0]['source']);
    if (body != null) {
      posts.add(openItemCopy(body));
      if (path.endsWith('$openItemPath/preview'))
        return heldPreview?.future ?? openItemCopy(f['item_preview']);
      if (lose) {
        lose = false;
        throw const ApiException(0, 'Synthetic accepted reply lost');
      }
      return openItemCopy(wrong ? f['payments'][0]['payment'] : f['item']);
    }
    throw StateError('Unexpected opening item route $path');
  }
}

Future<void> oiTap(WidgetTester t, String label) async {
  final scroll = find.byType(Scrollable).first;
  t.state<ScrollableState>(scroll).position.jumpTo(0);
  await t.pump();
  final finder = find.text(label);
  await t.scrollUntilVisible(finder, 250, scrollable: scroll);
  await t.ensureVisible(finder.first);
  await t.pumpAndSettle();
  await t.tap(finder.first);
  await t.pump();
}

Future<void> oiOpen(WidgetTester t, OpenItemsApi api, BusinessSession s) async {
  await s.load();
  await t.pumpWidget(
    MaterialApp(
      home: BusinessOpenItemsPage(
        session: s,
        entityKey: api.f['item']['entity_key'],
      ),
    ),
  );
  await t.pumpAndSettle();
  expect(
    find.text('Synthetic counterparty · OLD-synthetic-receivable'),
    findsOneWidget,
  );
}

Future<void> oiClose(WidgetTester t, BusinessSession s) async {
  await t.pumpWidget(const SizedBox.shrink());
  s.dispose();
  expect(t.takeException(), null);
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  test('unknown acceptance retains frozen nonce and validator across newer generation, revoked rights and foreign valid receipt', () async {
    final api = OpenItemsApi();
    final session = BusinessSession(api: api);
    addTearDown(session.dispose);
    await session.load();
    api.lose = true;
    final command = openItemCopy(api.f['item_command'])..remove('request_id');
    await expectLater(
      session.command(
        'opening-item-confirm-original',
        '$openItemPath/confirm',
        command,
        validateResult: openItemReceipt(api.f['item_preview']),
      ),
      throwsA(isA<ApiException>()),
    );
    command['reason'] =
        'Mutation after accepted request must not change replay';
    api.generation = 2;
    api.write = false;
    await expectLater(
      session.repeatOpenItemCommand('opening-item-confirm-original'),
      throwsA(isA<ApiException>()),
    );
    expect(api.posts.length, 1);
    api.write = true;
    api.wrong = true;
    await expectLater(
      session.repeatOpenItemCommand('opening-item-confirm-original'),
      throwsA(isA<ApiException>()),
    );
    expect(session.pendingOpenItemKeys, ['opening-item-confirm-original']);
    api.wrong = false;
    await session.repeatOpenItemCommand('opening-item-confirm-original');
    expect(api.posts[0], api.posts[1]);
    expect(api.posts[1], api.posts[2]);
    expect(session.pendingOpenItemKeys, isEmpty);
  });
  test('closed UI during pending replay capability preflight prevents a not-yet-started POST', () async {
    final api = OpenItemsApi();
    final session = BusinessSession(api: api);
    addTearDown(session.dispose);
    await session.load();
    api.lose = true;
    await expectLater(
      session.command(
        'opening-item-confirm-original',
        '$openItemPath/confirm',
        openItemCopy(api.f['item_command'])..remove('request_id'),
        validateResult: openItemReceipt(api.f['item_preview']),
      ),
      throwsA(isA<ApiException>()),
    );
    bool current = true;
    api.heldCapabilities = Completer<dynamic>();
    final retry = session.repeatOpenItemCommand(
      'opening-item-confirm-original',
      stillCurrent: () => current,
    );
    final expectation = expectLater(retry, throwsA(isA<ApiException>()));
    current = false;
    api.heldCapabilities!.complete(api.capabilities());
    await expectation;
    expect(api.posts.length, 1);
    expect(session.pendingOpenItemKeys, isNotEmpty);
  });
  testWidgets(
    'held original history is discarded after silent global read revocation',
    (t) async {
      final api = OpenItemsApi();
      final session = BusinessSession(api: api);
      await oiOpen(t, api, session);
      api.heldHistory = Completer<dynamic>();
      await oiTap(t, 'Übernahmehistorie');
      api.read = false;
      api.heldHistory!.complete(openItemCopy(api.f['history']));
      await t.pumpAndSettle();
      expect(find.textContaining('Synthetic counterparty'), findsNothing);
      expect(find.textContaining('nicht freigegeben'), findsOneWidget);
      await oiClose(t, session);
    },
  );
  testWidgets(
    'held account list cannot reveal earlier item after silent read revocation',
    (t) async {
      final api = OpenItemsApi();
      final s = BusinessSession(api: api);
      await oiOpen(t, api, s);
      api.heldAccounts = Completer<dynamic>();
      await oiTap(t, 'Bestand aktualisieren');
      api.read = false;
      api.heldAccounts!.complete(openItemCopy(api.f['accounts']));
      await t.pumpAndSettle();
      expect(find.textContaining('Synthetic counterparty'), findsNothing);
      await oiClose(t, s);
    },
  );
  testWidgets(
    'background clears private source and draft; late source cannot repopulate until explicit reload',
    (t) async {
      final api = OpenItemsApi();
      final s = BusinessSession(api: api);
      await oiOpen(t, api, s);
      api.heldSource = Completer<dynamic>();
      await oiTap(t, 'Zahlungsquelle und EÜR-Zuordnung');
      t.binding.handleAppLifecycleStateChanged(AppLifecycleState.paused);
      await t.pump();
      api.heldSource!.complete(openItemCopy(api.f['payments'][0]['source']));
      await t.pumpAndSettle();
      expect(find.textContaining('Synthetic counterparty'), findsNothing);
      expect(find.text('Originalgebundene Geld-/EÜR-Quelle'), findsNothing);
      t.binding.handleAppLifecycleStateChanged(AppLifecycleState.resumed);
      await t.pump();
      expect(find.textContaining('Synthetic counterparty'), findsNothing);
      await t.tap(find.text('Zugriff erneut prüfen'));
      await t.pumpAndSettle();
      expect(find.textContaining('Synthetic counterparty'), findsOneWidget);
      await oiClose(t, s);
    },
  );
  testWidgets(
    'replacement session removes edited historical facts and late original error',
    (t) async {
      final api = OpenItemsApi(), session = BusinessSession(api: api);
      await oiOpen(t, api, session);
      api.heldHistory = Completer<dynamic>();
      await oiTap(t, 'Übernahmehistorie');
      final otherApi = OpenItemsApi()..read = false;
      final replacement = BusinessSession(api: otherApi);
      await replacement.load();
      await t.pumpWidget(
        MaterialApp(home: BusinessOpenItemsPage(session: replacement)),
      );
      api.heldHistory!.completeError(
        const ApiException(409, 'Private old supplier reference'),
      );
      await t.pumpAndSettle();
      expect(find.textContaining('Private old supplier'), findsNothing);
      expect(find.textContaining('Synthetic counterparty'), findsNothing);
      session.dispose();
      await oiClose(t, replacement);
    },
  );
  testWidgets(
    'write revocation clears populated correction while retaining authorized read-only original',
    (t) async {
      final api = OpenItemsApi(), session = BusinessSession(api: api);
      await oiOpen(t, api, session);
      await oiTap(t, 'Übernahme berichtigen / Profil erneut prüfen');
      await t.pumpAndSettle();
      await t.scrollUntilVisible(
        find.byKey(const ValueKey('opening-item-external_id')),
        250,
        scrollable: find.byType(Scrollable).first,
      );
      expect(
        find.byKey(const ValueKey('opening-item-external_id')),
        findsOneWidget,
      );
      api.write = false;
      await session.load();
      await t.pumpAndSettle();
      expect(
        find.byKey(const ValueKey('opening-item-external_id')),
        findsNothing,
      );
      t
          .state<ScrollableState>(find.byType(Scrollable).first)
          .position
          .jumpTo(0);
      await t.pump();
      expect(find.textContaining('Synthetic counterparty'), findsOneWidget);
      expect(api.posts, isEmpty);
      await oiClose(t, session);
    },
  );
  testWidgets(
    'held actual preview cannot reveal data after silently revoked read permission',
    (t) async {
      final api = OpenItemsApi()..stateName = 'initial_state',
          session = BusinessSession(api: api);
      await session.load();
      await t.pumpWidget(
        MaterialApp(home: BusinessOpenItemsPage(session: session)),
      );
      await t.pumpAndSettle();
      await oiTap(t, 'Belegte Übernahme fortsetzen');
      await t.pumpAndSettle();
      Future<void> visible(Finder f) async {
        final scroll = find.byType(Scrollable).first;
        t.state<ScrollableState>(scroll).position.jumpTo(0);
        await t.pump();
        await t.scrollUntilVisible(f, 250, scrollable: scroll);
        await t.ensureVisible(f.first);
        await t.pumpAndSettle();
      }

      Future<void> enter(String key, String value) async {
        final f = find.byKey(ValueKey('opening-item-$key'));
        await visible(f);
        await t.enterText(f, value);
        await t.pump();
      }

      Future<void> choose(String label, String value) async {
        final f = find.byWidgetPredicate(
          (v) =>
              v is DropdownButtonFormField<String> &&
              v.decoration.labelText == label,
        );
        await visible(f);
        await t.tap(f);
        await t.pumpAndSettle();
        await t.tap(find.text(value).last);
        await t.pumpAndSettle();
      }

      final payload = api.f['item_command']['payload'];
      await choose('Rechnungsrichtung', 'Offene Kundenforderung');
      for (final key in [
        'external_system',
        'external_id',
        'counterparty_key',
        'counterparty_name',
        'invoice_number',
        'invoice_date',
        'service_date',
        'invoice_received_date',
        'net',
        'tax',
        'gross',
        'history_through',
      ])
        await enter(key, payload[key]);
      await enter('reason', api.f['item_command']['reason']);
      await choose('Belegter einzelner Steuersatz', '19 %');
      await choose('Gewöhnliche Erlös-/Aufwandsart', 'Erlös');
      String original(dynamic proof) {
        final o = (api.f['initial_state']['originals'] as List).singleWhere(
          (v) => v['id'] == proof['original_id'],
        );
        return "${o['filename']} · ${o['sha256'].substring(0, 12)}";
      }

      await choose(
        'Ursprüngliches Rechnungsoriginal',
        original(payload['invoice_proof']),
      );
      await choose(
        'Vollständige Stichtagsaufstellung',
        original(payload['cutover_proof']),
      );
      await oiTap(t, 'Belegte alte Teilzahlung ergänzen');
      await t.pumpAndSettle();
      final prior = payload['prior_payments'][0];
      for (final k in ['date', 'reference', 'net', 'tax', 'gross'])
        await enter('prior-0-$k', prior[k]);
      await choose('Original dieser alten Zahlung', original(prior['proof']));
      for (final key in ['history-confirmed', 'scope-confirmed']) {
        final f = find.byKey(ValueKey('opening-item-$key'));
        await visible(f);
        await t.tap(f);
        await t.pumpAndSettle();
      }
      api.heldPreview = Completer<dynamic>();
      await oiTap(t, 'Verbindliche Vorschau prüfen');
      expect(api.posts.last['payload'], payload);
      api.read = false;
      api.heldPreview!.complete(openItemCopy(api.f['item_preview']));
      await t.pumpAndSettle();
      expect(find.text('Unveränderte Servervorschau'), findsNothing);
      expect(find.textContaining('nicht freigegeben'), findsOneWidget);
      expect(api.posts.length, 1);
      await oiClose(t, session);
    },
  );
  testWidgets(
    'background hides populated correction fields and does not restore private draft on resume',
    (t) async {
      final api = OpenItemsApi(), session = BusinessSession(api: api);
      await oiOpen(t, api, session);
      await oiTap(t, 'Übernahme berichtigen / Profil erneut prüfen');
      await t.pumpAndSettle();
      final field = find.byKey(
        const ValueKey('opening-item-counterparty_name'),
      );
      await t.scrollUntilVisible(
        field,
        250,
        scrollable: find.byType(Scrollable).first,
      );
      await t.ensureVisible(field);
      await t.pumpAndSettle();
      await t.enterText(field, 'Private draft supplier name');
      await t.pump();
      t.binding.handleAppLifecycleStateChanged(AppLifecycleState.paused);
      await t.pumpAndSettle();
      expect(find.text('Private draft supplier name'), findsNothing);
      expect(find.byType(TextField), findsNothing);
      t.binding.handleAppLifecycleStateChanged(AppLifecycleState.resumed);
      await t.pumpAndSettle();
      expect(find.byType(TextField), findsNothing);
      expect(api.posts, isEmpty);
      await oiClose(t, session);
    },
  );
  testWidgets(
    'removing a preceding old payment keeps visible values bound to the surviving evidence row',
    (t) async {
      final api = OpenItemsApi(), session = BusinessSession(api: api);
      await oiOpen(t, api, session);
      await oiTap(t, 'Übernahme berichtigen / Profil erneut prüfen');
      await t.pumpAndSettle();
      await oiTap(t, 'Belegte alte Teilzahlung ergänzen');
      await t.pumpAndSettle();
      final second = find.byKey(
        const ValueKey('opening-item-prior-1-reference'),
      );
      final scroll = find.byType(Scrollable).first;
      t.state<ScrollableState>(scroll).position.jumpTo(0);
      await t.pump();
      await t.scrollUntilVisible(
        second,
        250,
        scrollable: scroll,
        maxScrolls: 50,
      );
      await t.ensureVisible(second);
      await t.pumpAndSettle();
      await t.enterText(second, 'Second documented original payment');
      await t.pump();
      await t.ensureVisible(find.text('Alte Teilzahlung entfernen').first);
      await t.pumpAndSettle();
      await t.tap(find.text('Alte Teilzahlung entfernen').first);
      await t.pumpAndSettle();
      final remaining = find.byKey(
        const ValueKey('opening-item-prior-0-reference'),
      );
      t.state<ScrollableState>(scroll).position.jumpTo(0);
      await t.pump();
      await t.scrollUntilVisible(
        remaining,
        250,
        scrollable: scroll,
        maxScrolls: 50,
      );
      await t.ensureVisible(remaining);
      await t.pumpAndSettle();
      final input = find.descendant(
        of: remaining,
        matching: find.byType(EditableText),
      );
      expect(
        t.widget<EditableText>(input).controller.text,
        'Second documented original payment',
      );
      expect(
        find.byKey(const ValueKey('opening-item-prior-1-reference')),
        findsNothing,
      );
      await oiClose(t, session);
    },
  );
}

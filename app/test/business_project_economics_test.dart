import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:file_selector/file_selector.dart';

import 'business_offline_media_test.dart' show fieldPng;

import 'package:flutter_test/flutter_test.dart';
import 'package:smartplan_office/api.dart';
import 'package:smartplan_office/business_project_economics.dart';
import 'package:smartplan_office/business_project_receipts.dart';
import 'package:smartplan_office/business_session.dart';

import 'project_economics_fixture.dart';

class ReceiptUiApi extends EconomicsApi {
  Map<String, dynamic>? uploaded, received;
  bool loseCapture = true;
  final receiptResults = <String, Map<String, dynamic>>{};
  @override
  Future<dynamic> call(String path, [Map<String, dynamic>? body]) async {
    final route = path.split('?').first;
    if (route.startsWith('/api/business/receipt-media')) {
      calls.add((path: path, body: body == null ? null : ecCopy(body)));
      if (route == '/api/business/receipt-media') {
        uploaded = {...ecCopy(body!), 'id': 'c' * 32, 'status': 'uploading'};
        return ecCopy(uploaded!);
      }
      if (route.endsWith('/complete')) {
        uploaded!['status'] = 'ready';
        return ecCopy(uploaded!);
      }
      if (route.contains('/chunks/')) return {'stored': true};
    }
    if (route == '/api/business/finance/receipts') {
      calls.add((path: path, body: body == null ? null : ecCopy(body)));
      if (body == null)
        return {
          'items': [if (received != null) ecCopy(received!)],
        };
      received = receiptResults.putIfAbsent(
        body['request_id'],
        () => {
          'id': economicsReceipt,
          'project_id': economicsProject,
          'filename': uploaded!['filename'],
          'media_type': uploaded!['media_type'],
          'sha256': uploaded!['sha256'],
          'status': 'needs_review',
          'revision': 0,
        },
      );
      if (loseCapture) {
        loseCapture = false;
        throw const ApiException(0, 'Antwort nach Belegspeicherung verloren');
      }
      return ecCopy(received!);
    }
    if (route == '/api/business/finance/receipts/$economicsReceipt') {
      calls.add((path: path, body: body == null ? null : ecCopy(body)));
      if (body != null)
        received = {
          ...received!,
          ...ecCopy(body),
          'revision': body['revision'] + 1,
        };
      return ecCopy(received!);
    }
    return super.call(path, body);
  }
}

Future<BusinessSession> sessionFor(EconomicsApi api) async {
  final session = BusinessSession(
    api: api,
    projectId: economicsProject,
    projects: [
      {
        'id': economicsProject,
        'name': 'Synthetic project',
        'customer': 'Synthetic customer',
      },
    ],
  );
  await session.load();
  return session;
}

Future<void> cleanup(
  WidgetTester tester,
  BusinessSession session,
  EconomicsApi api,
) async {
  await tester.pumpWidget(const SizedBox.shrink());
  session.dispose();
  api.dispose();
}

Future<void> tapVisible(WidgetTester tester, Finder finder) async {
  await tester.scrollUntilVisible(
    finder,
    350,
    scrollable: find.byType(Scrollable).first,
    maxScrolls: 35,
  );
  await tester.ensureVisible(finder);
  await tester.tap(finder);
  await tester.pumpAndSettle();
}

void main() {
  test('EUR amounts are decimal exact and never silently rounded', () {
    expect(projectCostMoney('1.234,56'), '1234.56');
    expect(projectCostMoney('0012.5'), '12.50');
    expect(projectCostMoney('0'), '0.00');
    for (final value in ['-1', '1.001', 'NaN', '1e2', ''])
      expect(() => projectCostMoney(value), throwsFormatException);
  });
  test('ACK validation precedes pending removal and repeats the original command after generation and rights changes', () async {
    final api = EconomicsApi()..wrongConfirm = true,
        session = await sessionFor(api);
    addTearDown(session.dispose);
    addTearDown(api.dispose);
    final body = economicsBody(),
        key = 'project-economics-$economicsProject-$economicsReceipt';
    await expectLater(
      session.command(
        key,
        '/project-economics/confirm',
        body,
        validateResult: projectCostReceiptValidator(body, economicsProof()),
      ),
      throwsA(isA<ApiException>().having((e) => e.status, 'status', 0)),
    );
    expect(session.pending(key), isTrue);
    expect(api.entries, hasLength(1));
    body['reason'] = 'Changed local editor';
    (body['allocations'] as List).clear();
    api.generation++;
    api.denyConfirm = true;
    await expectLater(
      session.repeatProjectEconomicsCommand(economicsProject, economicsReceipt),
      throwsA(isA<ApiException>().having((e) => e.status, 'status', 403)),
    );
    expect(session.pending(key), isTrue);
    api.denyConfirm = false;
    final accepted = await session.repeatProjectEconomicsCommand(
      economicsProject,
      economicsReceipt,
    );
    expect(accepted['reason'], 'Geprüfte Fremdleistung');
    expect(api.entries, hasLength(1));
    expect(session.pending(key), isFalse);
    final requests = api.calls
        .where((call) => call.path.endsWith('/confirm'))
        .map((e) => jsonEncode(e.body))
        .toSet();
    expect(requests, hasLength(1));
  });
  test('Receipt validators retain exact project, original and reviewed financial fields', () {
    final expected = {
      'project_id': economicsProject,
      'filename': 'Original.pdf',
      'media_type': 'application/pdf',
      'size': 12,
      'sha256': 'a' * 64,
    };
    final media = {'id': 'c' * 32, ...expected, 'status': 'ready'};
    final validate = projectReceiptUploadValidator(
      phase: 'media-complete',
      expected: expected,
      mediaId: 'c' * 32,
    );
    validate(media);
    expected['sha256'] = 'changed';
    validate(media);
    for (final changed in [
      {'sha256': 'b' * 64},
      {'project_id': '9' * 32},
      {'size': 13},
      {'id': '8' * 32},
      {'status': 'uploading'},
    ])
      expect(
        () => validate({...media, ...changed}),
        throwsA(isA<ApiException>()),
      );
    final request = {
      'revision': 1,
      'vendor': 'Vendor',
      'invoice_number': 'INV',
      'issue_date': '2026-11-03',
      'net': '1.00',
      'tax': '0.19',
      'gross': '1.19',
      'currency': 'EUR',
      'status': 'reviewed',
      'note': '',
    };
    final review = projectReceiptReviewValidator(
      project: economicsProject,
      receipt: economicsReceipt,
      originalHash: 'a' * 64,
      expected: request,
    );
    final receipt = {
      'id': economicsReceipt,
      'project_id': economicsProject,
      'sha256': 'a' * 64,
      ...request,
      'revision': 2,
    };
    review(receipt);
    request['net'] = 'wrong';
    review(receipt);
    expect(
      () => review({...receipt, 'gross': '2.00'}),
      throwsA(isA<ApiException>()),
    );
  });
  testWidgets(
    'Project view separates unsupported cash completeness from actual costs and hides data on read denial',
    (tester) async {
      tester.view.physicalSize = const Size(390, 844);
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.resetPhysicalSize);
      addTearDown(tester.view.resetDevicePixelRatio);
      final api = EconomicsApi(), session = await sessionFor(api);
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(body: BusinessProjectEconomicsPage(session: session)),
        ),
      );
      await tester.pumpAndSettle();
      expect(find.text('Projektwirtschaftlichkeit'), findsOneWidget);
      expect(find.textContaining('keine EÜR'), findsOneWidget);
      await tester.scrollUntilVisible(
        find.textContaining('Ein fehlender Betrag bedeutet nicht null'),
        400,
        scrollable: find.byType(Scrollable).first,
        maxScrolls: 30,
      );
      expect(tester.takeException(), isNull);
      expect(
        find.textContaining('Ein fehlender Betrag bedeutet nicht null'),
        findsOneWidget,
      );
      api.rights.remove('finance.read');
      await session.load();
      await tester.pumpAndSettle();
      expect(
        find.text('Projektwirtschaftlichkeit nicht freigegeben'),
        findsOneWidget,
      );
      expect(find.text('100,00 €'), findsNothing);
      await cleanup(tester, session, api);
    },
    variant: TargetPlatformVariant.only(TargetPlatform.windows),
  );
  testWidgets(
    'Full allocation review freezes input and survives a lost confirm ACK without a second entry',
    (tester) async {
      tester.view.physicalSize = const Size(1200, 2400);
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.resetPhysicalSize);
      addTearDown(tester.view.resetDevicePixelRatio);
      final api = EconomicsApi()..loseConfirm = true,
          session = await sessionFor(api);
      await tester.pumpWidget(
        MaterialApp(
          home: BusinessProjectCostEditor(session: session, source: api.source),
        ),
      );
      await tester.pumpAndSettle();
      await tester.enterText(
        find.widgetWithText(TextField, 'Fremdleistungen (€ netto)'),
        '90,00',
      );
      await tester.enterText(
        find.widgetWithText(TextField, 'Begründung der Einordnung / Korrektur'),
        'Synthetische Fremdleistung',
      );
      await tapVisible(tester, find.text('Einordnung unverbindlich prüfen'));
      expect(find.textContaining('Die Summe muss genau'), findsOneWidget);
      expect(api.calls.where((c) => c.path.endsWith('/preview')), isEmpty);
      await tester.enterText(
        find.widgetWithText(TextField, 'Fremdleistungen (€ netto)'),
        '100,00',
      );
      await tapVisible(tester, find.text('Einordnung unverbindlich prüfen'));
      expect(find.text('Geprüfte Einordnung'), findsOneWidget);
      await tapVisible(tester, find.byType(CheckboxListTile));
      await tapVisible(tester, find.text('Einordnung verbindlich festhalten'));
      expect(
        find.textContaining('Antwort nach Speicherung verloren'),
        findsOneWidget,
      );
      expect(api.entries, hasLength(1));
      await tapVisible(tester, find.text('Unverändert erneut senden'));
      expect(
        find.text(
          'Die Einordnung ist als unveränderliche Fassung gespeichert.',
        ),
        findsOneWidget,
      );
      expect(api.entries, hasLength(1));
      expect(
        api.calls
            .where((c) => c.path.endsWith('/confirm'))
            .map((c) => jsonEncode(c.body))
            .toSet(),
        hasLength(1),
      );
      api.generation++;
      await session.load();
      await tester.pumpAndSettle();
      expect(find.text('Beleg nicht mehr freigegeben'), findsOneWidget);
      expect(find.textContaining('Synthetischer Service'), findsNothing);
      expect(find.byType(TextField), findsNothing);
      await cleanup(tester, session, api);
    },
    variant: TargetPlatformVariant.only(TargetPlatform.windows),
  );
  testWidgets(
    'Receipt upload survives a closed page and review uses the actual existing endpoint',
    (tester) async {
      tester.view.physicalSize = const Size(1200, 2400);
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.resetPhysicalSize);
      addTearDown(tester.view.resetDevicePixelRatio);
      final api = ReceiptUiApi(), session = await sessionFor(api);
      Widget page() => MaterialApp(
        home: BusinessProjectReceiptsPage(
          session: session,
          pickFile: () async => XFile.fromData(
            fieldPng,
            name: 'synthetic-invoice.png',
            mimeType: 'image/png',
          ),
        ),
      );
      await tester.pumpWidget(page());
      await tester.pumpAndSettle();
      await tester.runAsync(() async {
        await tester.tap(find.text('Belegoriginal auswählen'));
        await Future<void>.delayed(const Duration(milliseconds: 100));
      });
      await tester.pumpAndSettle();
      expect(
        find.textContaining('Antwort nach Belegspeicherung verloren'),
        findsOneWidget,
        reason: tester
            .widgetList<Text>(find.byType(Text))
            .map((w) => w.data)
            .join(' | '),
      );
      expect(api.receiptResults, hasLength(1));
      await tester.pumpWidget(const SizedBox.shrink());
      await tester.pumpAndSettle();
      await tester.pumpWidget(page());
      await tester.pumpAndSettle();
      await tester.tap(find.text('Übertragung unverändert fortsetzen'));
      await tester.pumpAndSettle();
      expect(api.receiptResults, hasLength(1));
      expect(find.text('Übertragung unverändert fortsetzen'), findsNothing);
      await tester.tap(find.text('Beleg prüfen'));
      await tester.pumpAndSettle();
      for (final item in {
        'Lieferant / Aussteller': 'Prüfbetrieb',
        'Belegnummer': 'SYN-1',
        'Belegdatum': '03.11.2026',
        'Nettobetrag laut Beleg (€)': '100,00',
        'Ausgewiesene Steuer laut Beleg (€)': '19,00',
        'Bruttobetrag laut Beleg (€)': '119,00',
      }.entries) {
        await tester.enterText(
          find.widgetWithText(TextFormField, item.key),
          item.value,
        );
      }
      await tester.tap(find.text('Bitte ausdrücklich wählen'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Angaben geprüft').last);
      await tester.pumpAndSettle();
      await tester.tap(find.byType(SwitchListTile));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Belegprüfung festhalten'));
      await tester.pumpAndSettle();
      expect(find.text('Geprüft · Fassung 1'), findsOneWidget);
      expect(
        api.calls
            .where(
              (c) =>
                  c.path == '/api/business/finance/receipts' && c.body != null,
            )
            .map((c) => jsonEncode(c.body))
            .toSet(),
        hasLength(1),
      );
      expect(api.calls.any((c) => c.path.endsWith('/review')), isFalse);
      api.generation++;
      await session.load();
      await tester.pumpAndSettle();
      expect(find.text('Geprüft · Fassung 1'), findsNothing);
      await tester.tap(find.text('Belegliste aktualisieren'));
      await tester.pumpAndSettle();
      expect(find.text('Geprüft · Fassung 1'), findsOneWidget);
      await cleanup(tester, session, api);
    },
    variant: TargetPlatformVariant.only(TargetPlatform.windows),
  );

  testWidgets(
    'Known missing approval right prevents all economic writes while leaving recorded evidence readable',
    (tester) async {
      final api = EconomicsApi()..rights.remove('finance.approve'),
          session = await sessionFor(api);
      await tester.pumpWidget(
        MaterialApp(
          home: BusinessProjectCostEditor(session: session, source: api.source),
        ),
      );
      await tester.pumpAndSettle();
      final button = find.widgetWithText(
        FilledButton,
        'Einordnung unverbindlich prüfen',
      );
      await tester.scrollUntilVisible(
        button,
        300,
        scrollable: find.byType(Scrollable).first,
        maxScrolls: 20,
      );
      expect(tester.widget<FilledButton>(button).onPressed, isNull);
      expect(api.calls.where((c) => c.body != null), isEmpty);
      await cleanup(tester, session, api);
    },
    variant: TargetPlatformVariant.only(TargetPlatform.windows),
  );
}

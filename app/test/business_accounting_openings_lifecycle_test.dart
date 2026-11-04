import 'dart:async';
import 'dart:convert';

import 'package:file_selector/file_selector.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:smartplan_office/business_accounting_openings.dart';
import 'package:smartplan_office/business_session.dart';
import 'package:smartplan_office/business_widgets.dart';

import 'business_accounting_openings_test.dart'
    show OpeningApi, openingFixture, copyOpening;

class OpeningWidgetApi extends OpeningApi {
  Completer<dynamic>? heldState, heldSources, heldPreview;
  bool bank = false;
  final reads = <String>[];
  @override
  Future<dynamic> call(String path, [Map<String, dynamic>? body]) async {
    reads.add(path);
    final f = bank ? openingFixture['bank'] : openingFixture;
    if (body == null &&
        path == '/api/business$openingPath' &&
        heldState != null)
      return heldState!.future;
    if (path.contains('$openingPath/liquidity?'))
      return copyOpening(f['liquidity']);
    if (path.contains('$openingPath/sources?'))
      return heldSources?.future ?? copyOpening(f['sources']);
    if (path.endsWith('$openingPath/preview') && body != null) {
      posts.add(copyOpening(body));
      return heldPreview!.future;
    }
    if (bank && path == '/api/business$openingPath')
      return copyOpening(f['state_after']);
    if (path.endsWith('/history'))
      return bank
          ? {
              'schema_version': 1,
              'account_id': f['saved']['account_id'],
              'items': [copyOpening(f['saved'])],
            }
          : copyOpening(f['history']);
    if (path.endsWith('$openingPath/originals') && body != null) {
      posts.add(copyOpening(body));
      return copyOpening(f['original']);
    }
    return super.call(path, body);
  }
}

void main() {
  Future<void> open(
    WidgetTester tester,
    OpeningWidgetApi api,
    BusinessSession session, {
    Future<XFile?> Function()? picker,
  }) async {
    await session.load();
    await tester.pumpWidget(
      MaterialApp(
        home: BusinessOpeningBalancesPage(
          session: session,
          accountId: api.bank
              ? openingFixture['bank']['saved']['account_id']
              : openingFixture['saved']['account_id'],
          pickFile: picker,
        ),
      ),
    );
    await tester.pumpAndSettle();
    // Deliberately choose the actual fixture's report date. A response for a
    // different default date must not be displayed as if it were current.
    final date = find.byWidgetPredicate(
      (v) =>
          v is TextField &&
          v.decoration?.labelText == 'Bestandsstichtag (JJJJ-MM-TT)',
    );
    await tester.enterText(
      date,
      api.bank
          ? openingFixture['bank']['liquidity']['as_of']
          : openingFixture['liquidity']['as_of'],
    );
    await tester.tap(find.text('Liquidität zum Stichtag prüfen'));
    await tester.pumpAndSettle();
    expect(
      find.text(
        api.bank ? 'Liquidität am 31.01.2026' : 'Liquidität am 02.11.2026',
      ),
      findsOneWidget,
      reason: tester
          .widgetList<Text>(find.byType(Text))
          .map((v) => v.data)
          .join(' | '),
    );
  }

  testWidgets(
    'delayed state cannot repopulate financial data after read revocation',
    (tester) async {
      final api = OpeningWidgetApi();
      final current = BusinessSession(api: api);
      await open(tester, api, current);
      api.heldState = Completer<dynamic>();
      await tester.tap(find.byTooltip('Stand aktualisieren'));
      await tester.pump();
      api.read = false;
      await current.load();
      await tester.pump();
      api.heldState!.complete(copyOpening(openingFixture['state_after']));
      await tester.pumpAndSettle();
      expect(find.text('Anfangsbestände nicht freigegeben'), findsOneWidget);
      expect(find.text('Unveränderte Kontohistorie'), findsNothing);
      expect(tester.takeException(), null);
      await tester.pumpWidget(const SizedBox.shrink());
      current.dispose();
    },
  );
  testWidgets(
    'file picker completing after context loss sends no original bytes or command',
    (tester) async {
      final api = OpeningWidgetApi();
      final session = BusinessSession(api: api), picker = Completer<XFile?>();
      await open(tester, api, session, picker: () => picker.future);
      final button = find.text('Bestandsoriginal hochladen');
      await tester.scrollUntilVisible(
        button,
        400,
        scrollable: find.byType(Scrollable).first,
      );
      await tester.tap(button);
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 50));
      api.read = false;
      await session.load();
      await tester.pump();
      picker.complete(
        XFile.fromData(
          base64Decode(openingFixture['original_upload']['content_base64']),
          mimeType: 'application/pdf',
          name: 'synthetic-opening.pdf',
        ),
      );
      await tester.pumpAndSettle();
      expect(api.posts, isEmpty);
      expect(find.text('Anfangsbestände nicht freigegeben'), findsOneWidget);
      expect(tester.takeException(), null);
      await tester.pumpWidget(const SizedBox.shrink());
      session.dispose();
    },
  );
  testWidgets(
    'session replacement forgets old account details and typed proof immediately',
    (tester) async {
      final api = OpeningWidgetApi();
      final current = BusinessSession(api: api);
      await open(tester, api, current);
      final button = find.text('Anfangsbestand aus Nachweisen prüfen');
      await tester.scrollUntilVisible(
        button,
        400,
        scrollable: find.byType(Scrollable).first,
      );
      await tester.tap(button);
      await tester.pumpAndSettle();
      final reason = find.byWidgetPredicate(
        (v) =>
            v is TextField &&
            v.decoration?.labelText == 'Prüf- oder Korrekturgrund',
      );
      await tester.scrollUntilVisible(
        reason,
        400,
        scrollable: find.byType(Scrollable).first,
      );
      await tester.enterText(reason, 'Private old draft must disappear');
      final otherApi = OpeningWidgetApi()..read = false;
      final replacement = BusinessSession(api: otherApi);
      await replacement.load();
      await tester.pumpWidget(
        MaterialApp(
          home: BusinessOpeningBalancesPage(
            session: replacement,
            accountId: openingFixture['saved']['account_id'],
          ),
        ),
      );
      await tester.pumpAndSettle();
      expect(find.text('Private old draft must disappear'), findsNothing);
      expect(find.text('Unveränderte Kontohistorie'), findsNothing);
      expect(tester.takeException(), null);
      await tester.pumpWidget(const SizedBox.shrink());
      current.dispose();
      replacement.dispose();
    },
  );

  Future<void> tapVisible(WidgetTester tester, String label) async {
    tester
        .state<ScrollableState>(find.byType(Scrollable).first)
        .position
        .jumpTo(0);
    await tester.pump();
    final f = find.text(label);
    await tester.scrollUntilVisible(
      f,
      200,
      scrollable: find.byType(Scrollable).first,
    );
    await tester.ensureVisible(f);
    await tester.pumpAndSettle();
    await tester.tap(f);
    await tester.pump();
  }

  Future<void> selectSource(WidgetTester tester, String option) async {
    final chooser = find.byWidgetPredicate(
      (v) =>
          v is DropdownButtonFormField<String> &&
          v.decoration.labelText == 'Unveränderten Bestandsnachweis auswählen',
    );
    await tester.scrollUntilVisible(
      chooser,
      200,
      scrollable: find.byType(Scrollable).first,
    );
    await tester.ensureVisible(chooser);
    await tester.pumpAndSettle();
    await tester.tap(chooser);
    await tester.pumpAndSettle();
    await tester.tap(find.text(option).last);
    await tester.pumpAndSettle();
  }

  Future<void> enter(WidgetTester tester, String label, String value) async {
    tester
        .state<ScrollableState>(find.byType(Scrollable).first)
        .position
        .jumpTo(0);
    await tester.pump();
    final field = find.byWidgetPredicate(
      (v) => v is TextField && v.decoration?.labelText == label,
    );
    await tester.scrollUntilVisible(
      field,
      200,
      scrollable: find.byType(Scrollable).first,
    );
    await tester.ensureVisible(field);
    await tester.pumpAndSettle();
    await tester.enterText(field, value);
    await tester.pump();
  }

  testWidgets(
    'actual capability read after delayed sources detects revocation without prior session notification',
    (tester) async {
      final api = OpeningWidgetApi();
      final current = BusinessSession(api: api);
      await open(tester, api, current);
      api.heldSources = Completer<dynamic>();
      await tester.tap(find.byTooltip('Stand aktualisieren'));
      await tester.pump(const Duration(milliseconds: 50));
      api.read = false; // No session.load(): the response completion must refresh rights.
      api.heldSources!.complete(copyOpening(openingFixture['sources']));
      await tester.pumpAndSettle();
      expect(find.text('Anfangsbestände nicht freigegeben'), findsOneWidget);
      expect(
        find.textContaining(openingFixture['sources']['account']['name']),
        findsNothing,
      );
      expect(find.text('Unveränderte Kontohistorie'), findsNothing);
      expect(tester.takeException(), null);
      await tester.pumpWidget(const SizedBox.shrink());
      current.dispose();
    },
  );
  testWidgets(
    'delayed preview refreshes rights before showing the accepted financial proof',
    (tester) async {
      final api = OpeningWidgetApi();
      final session = BusinessSession(api: api);
      await open(tester, api, session);
      await tapVisible(tester, 'Anfangsbestand aus Nachweisen prüfen');
      await selectSource(tester, 'Original · synthetic-opening.pdf');
      await enter(
        tester,
        'Belegter Anfangsbestand (EUR)',
        openingFixture['correction_preview_request']['amount'],
      );
      await enter(
        tester,
        'Prüf- oder Korrekturgrund',
        openingFixture['correction_preview_request']['reason'],
      );
      await tapVisible(
        tester,
        'Das Original belegt den Bestand vor der ersten Bewegung dieses Stichtags.',
      );
      api.heldPreview = Completer<dynamic>();
      await tapVisible(tester, 'Anfangsbestand unverbindlich prüfen');
      await tester.pump(const Duration(milliseconds: 50));
      expect(api.posts, isNotEmpty);
      api.read = false;
      final actualPreview = copyOpening(openingFixture['correction']);
      for (final key in [
        'created_by',
        'revision',
        'sequence',
        'created_at',
        'id',
        'previous_hash',
        'content_hash',
      ]) {
        actualPreview.remove(key);
      }
      api.heldPreview!.complete(actualPreview);
      await tester.pumpAndSettle();
      expect(find.text('Anfangsbestände nicht freigegeben'), findsOneWidget);
      expect(find.text('Geprüften Anfangsbestand bestätigen'), findsNothing);
      expect(find.textContaining('synthetic-opening.pdf'), findsNothing);
      expect(tester.takeException(), null);
      await tester.pumpWidget(const SizedBox.shrink());
      session.dispose();
    },
  );
  testWidgets(
    'background transition clears draft and delayed sources until an explicit current reload',
    (tester) async {
      final api = OpeningWidgetApi();
      final current = BusinessSession(api: api);
      await open(tester, api, current);
      await tapVisible(tester, 'Anfangsbestand aus Nachweisen prüfen');
      await enter(tester, 'Prüf- oder Korrekturgrund', 'Private paused draft');
      for (final value in [
        AppLifecycleState.inactive,
        AppLifecycleState.hidden,
        AppLifecycleState.paused,
      ]) {
        tester.binding.handleAppLifecycleStateChanged(value);
      }
      await tester.pumpAndSettle();
      expect(find.text('Private paused draft'), findsNothing);
      expect(
        find.textContaining(openingFixture['sources']['account']['name']),
        findsNothing,
      );
      for (final value in [
        AppLifecycleState.hidden,
        AppLifecycleState.inactive,
        AppLifecycleState.resumed,
      ]) {
        tester.binding.handleAppLifecycleStateChanged(value);
      }
      await tester.pumpAndSettle();
      expect(find.text('Anfangsbestände nicht freigegeben'), findsOneWidget);
      api.heldSources = Completer<dynamic>();
      await tester.tap(find.byTooltip('Stand aktualisieren'));
      await tester.pump(const Duration(milliseconds: 50));
      for (final value in [
        AppLifecycleState.inactive,
        AppLifecycleState.hidden,
        AppLifecycleState.paused,
      ]) {
        tester.binding.handleAppLifecycleStateChanged(value);
      }
      api.heldSources!.complete(copyOpening(openingFixture['sources']));
      await tester.pumpAndSettle();
      for (final value in [
        AppLifecycleState.hidden,
        AppLifecycleState.inactive,
        AppLifecycleState.resumed,
      ]) {
        tester.binding.handleAppLifecycleStateChanged(value);
      }
      await tester.pumpAndSettle();
      expect(find.text('Anfangsbestände nicht freigegeben'), findsOneWidget);
      api.heldSources = null;
      await tester.tap(find.byTooltip('Stand aktualisieren'));
      await tester.pumpAndSettle();
      expect(find.text('Liquidität am 02.11.2026'), findsOneWidget);
      expect(find.text('Private paused draft'), findsNothing);
      expect(tester.takeException(), null);
      await tester.pumpWidget(const SizedBox.shrink());
      current.dispose();
    },
  );
  testWidgets(
    'bank source displays immutable real statement balance without manual amount entry',
    (tester) async {
      final api = OpeningWidgetApi()..bank = true;
      final session = BusinessSession(api: api);
      await open(tester, api, session);
      await tapVisible(tester, 'Anfangsbestand aus Nachweisen prüfen');
      final source = openingFixture['bank']['sources']['bank_statements'][0];
      await selectSource(
        tester,
        'Bankauszug · ${source['statement_reference']} · ${businessMoney(source['amount'])}',
      );
      final field = find.byWidgetPredicate(
        (v) =>
            v is TextField &&
            v.decoration?.labelText == 'Belegter Anfangsbestand (EUR)',
      );
      await tester.scrollUntilVisible(
        field,
        200,
        scrollable: find.byType(Scrollable).first,
      );
      final input = tester.widget<TextField>(field);
      expect(input.readOnly, true);
      expect(input.controller!.text, source['amount']);
      expect(input.decoration!.helperText, contains('Bankauszug'));
      expect(tester.takeException(), null);
      await tester.pumpWidget(const SizedBox.shrink());
      session.dispose();
    },
  );
}

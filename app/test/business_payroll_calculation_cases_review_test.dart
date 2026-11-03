import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:smartplan_office/business_payroll_calculation_cases.dart';
import 'package:smartplan_office/api.dart';
import 'package:smartplan_office/business_session.dart';

import 'business_payroll_calculation_cases_test.dart' as base;

class DelayedCasesApi extends base.CasesApi {
  bool holdSource = false;
  bool holdPreview = false;
  Completer<dynamic>? release;
  Completer<dynamic>? previewRelease;
  dynamic heldPreview;
  dynamic held;
  final sourceMonths = <String>[];
  @override
  Future<dynamic> call(String path, [Map<String, dynamic>? body]) async {
    if (path == '/api/business/payroll/calculation-cases/preview' &&
        holdPreview) {
      holdPreview = false;
      heldPreview = await super.call(path, body);
      previewRelease = Completer<dynamic>();
      return previewRelease!.future;
    }
    if (path.startsWith('/api/business/payroll/calculation-cases/sources?')) {
      final month = Uri.parse(path).queryParameters['month']!;
      sourceMonths.add(month);
      final response = base.copy(await super.call(path, body));
      response['month'] = month;
      if (month != '2026-10') response['calculation_cases'] = [];
      if (holdSource) {
        holdSource = false;
        held = response;
        release = Completer<dynamic>();
        return release!.future;
      }
      return response;
    }
    return super.call(path, body);
  }
}

Future<void> openReviewPage(
  WidgetTester t,
  DelayedCasesApi api,
  BusinessSession session, {
  Future<void> Function(Map<String, dynamic>)? onOriginal,
}) async {
  await session.load();
  await t.pumpWidget(
    MaterialApp(
      home: BusinessPayrollCalculationCasesPage(
        session: session,
        employee: base.copy(base.fixture['sources']['employee']),
        initialMonth: '2026-10',
        onOriginal: onOriginal ?? (_) async {},
        onCalculate: (_) async {},
      ),
    ),
  );
  await t.pumpAndSettle();
}

void background(WidgetTester t) {
  t.binding.handleAppLifecycleStateChanged(AppLifecycleState.inactive);
  t.binding.handleAppLifecycleStateChanged(AppLifecycleState.hidden);
  t.binding.handleAppLifecycleStateChanged(AppLifecycleState.paused);
}

void resume(WidgetTester t) {
  if (t.binding.lifecycleState == AppLifecycleState.paused) {
    t.binding.handleAppLifecycleStateChanged(AppLifecycleState.hidden);
  }
  if (t.binding.lifecycleState == AppLifecycleState.hidden) {
    t.binding.handleAppLifecycleStateChanged(AppLifecycleState.inactive);
  }
  t.binding.handleAppLifecycleStateChanged(AppLifecycleState.resumed);
}

void reviewWidgets(
  String name,
  Future<void> Function(WidgetTester, DelayedCasesApi, BusinessSession) run,
) {
  testWidgets(name, (t) async {
    final api = DelayedCasesApi(), session = BusinessSession(api: api);
    try {
      await run(t, api, session);
    } finally {
      await t.pumpWidget(const SizedBox.shrink());
      session.dispose();
      api.dispose();
      resume(t);
      await t.pump();
    }
  });
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  reviewWidgets(
    'late inspect response cannot repopulate a hidden private page',
    (t, api, session) async {
      await openReviewPage(t, api, session);
      api.holdSource = true;
      await t.tap(find.text('Abrechnungsfall 2026-10 · Fassung 1').last);
      await t.pump();
      expect(api.release, isNotNull);
      background(t);
      await t.pump();
      resume(t);
      await t.pump(const Duration(milliseconds: 100));
      api.release!.complete(api.held);
      await t.pumpAndSettle();
      expect(find.byType(PayrollCalculationCasePlanView), findsNothing);
      expect(
        find.text('Belegter Arbeitnehmerabzug für Steuerkosten'),
        findsNothing,
      );
      expect(find.textContaining('Personaloriginal:'), findsNothing);
    },
  );

  reviewWidgets(
    'background clears an open editor containing private original details',
    (t, api, session) async {
      await openReviewPage(t, api, session);
      await base.tapVisible(
        t,
        find.text('Abrechnungsfall 2026-10 · Fassung 1').last,
      );
      await base.tapVisible(t, find.text('Abrechnungsfall berichtigen'));
      final note = find.byKey(
        const ValueKey('business-field-verification_note'),
      );
      expect(note, findsOneWidget);
      final original = t.widget<TextFormField>(note).controller!.text;
      expect(original, isNotEmpty);
      background(t);
      await t.pump();
      resume(t);
      await t.pumpAndSettle();
      expect(find.text(original), findsNothing);
      expect(
        find.text('Geschützte Originale für diesen Gesamtfall'),
        findsNothing,
      );
    },
  );

  reviewWidgets(
    'month switch requests the new month and clears selected original and plan',
    (t, api, session) async {
      await openReviewPage(t, api, session);
      await base.tapVisible(
        t,
        find.text('Abrechnungsfall 2026-10 · Fassung 1').last,
      );
      expect(
        find.text('Belegter Arbeitnehmerabzug für Steuerkosten'),
        findsOneWidget,
      );
      await base.tapVisible(t, find.text('Monat 2026-10 wählen'));
      await t.enterText(find.byType(TextFormField), '2026-11');
      await base.tapVisible(t, find.text('Monat öffnen'));
      expect(api.sourceMonths.last, '2026-11');
      expect(find.text('Monat 2026-11 wählen'), findsOneWidget);
      expect(
        find.text('Belegter Arbeitnehmerabzug für Steuerkosten'),
        findsNothing,
      );
      expect(find.textContaining('Personaloriginal:'), findsNothing);
      expect(api.sent, isEmpty);
    },
  );

  reviewWidgets(
    'original callback receives the exact selected historical file',
    (t, api, session) async {
      Map<String, dynamic>? opened;
      await openReviewPage(
        t,
        api,
        session,
        onOriginal: (v) async {
          opened = base.copy(v);
        },
      );
      await base.tapVisible(
        t,
        find.text('Abrechnungsfall 2026-10 · Fassung 1').last,
      );
      final originals =
          base.fixture['saved']['sources']['source_files'] as List;
      await base.tapVisible(
        t,
        find.text('Personaloriginal: ${originals.first['filename']}').first,
      );
      expect(opened, originals.first);
      expect(api.sent, isEmpty);
    },
  );

  reviewWidgets(
    'flat tax recording remains an explicit new instruction on correction',
    (t, api, session) async {
      await openReviewPage(t, api, session);
      await base.tapVisible(
        t,
        find.text('Abrechnungsfall 2026-10 · Fassung 1').last,
      );
      await base.tapVisible(t, find.text('Abrechnungsfall berichtigen'));
      await t.enterText(
        find.byKey(const ValueKey('business-field-correction_reason')),
        'Unabhängiger Quellenabgleich',
      );
      await base.tapVisible(t, find.text('Angaben übernehmen'));
      final recording = find.widgetWithText(
        SwitchListTile,
        'Pauschalsteuer mit dem tatsächlichen Lohnabschluss erfassen.',
      );
      expect(t.widget<SwitchListTile>(recording).value, false);
      await base.tapVisible(
        t,
        find.text(
          'Ich bestätige die vollständigen tatsächlichen Quellen und ihre Zuordnung.',
        ),
      );
      await base.tapVisible(
        t,
        find.text('Abrechnungsfall unverbindlich prüfen'),
      );
      expect(api.previews, 0);
      expect(api.sent, isEmpty);
      expect(
        find.text(
          'Aktuelle betriebliche Steuerentscheidung und tatsächliche Erfassung mit Abschluss bestätigen.',
        ),
        findsOneWidget,
      );
    },
  );

  reviewWidgets(
    'late preview after background cannot restore editor or submit a command',
    (t, api, session) async {
      await openReviewPage(t, api, session);
      await base.tapVisible(
        t,
        find.text('Abrechnungsfall 2026-10 · Fassung 1').last,
      );
      await base.tapVisible(t, find.text('Abrechnungsfall berichtigen'));
      await t.enterText(
        find.byKey(const ValueKey('business-field-correction_reason')),
        'Unabhängiger verspäteter Quellenabgleich',
      );
      await base.tapVisible(t, find.text('Angaben übernehmen'));
      await base.tapVisible(
        t,
        find.text(
          'Pauschalsteuer mit dem tatsächlichen Lohnabschluss erfassen.',
        ),
      );
      await base.tapVisible(
        t,
        find.text(
          'Ich bestätige die vollständigen tatsächlichen Quellen und ihre Zuordnung.',
        ),
      );
      api.holdPreview = true;
      await t.ensureVisible(find.text('Abrechnungsfall unverbindlich prüfen'));
      await t.tap(find.text('Abrechnungsfall unverbindlich prüfen'));
      await t.pump();
      expect(api.previewRelease, isNotNull);
      background(t);
      await t.pump();
      resume(t);
      await t.pumpAndSettle();
      api.previewRelease!.complete(api.heldPreview);
      await t.pumpAndSettle();
      expect(find.text('Abrechnungsfall prüfen'), findsNothing);
      expect(find.text('Konkrete Zuordnung prüfen'), findsNothing);
      expect(api.sent, isEmpty);
      expect(
        session.pending('payroll-calculation-cases-${api.employee}'),
        false,
      );
    },
  );

  reviewWidgets(
    'pending original blocks month change and new calculation-case actions',
    (t, api, session) async {
      await session.load();
      api.lose = true;
      final body = base.copy(base.fixture['command'])..remove('request_id');
      await expectLater(
        session.command(
          'payroll-calculation-cases-${api.employee}',
          '/payroll/calculation-cases',
          body,
        ),
        throwsA(isA<ApiException>()),
      );
      await openReviewPage(t, api, session);
      expect(
        t
            .widget<OutlinedButton>(
              find.widgetWithText(OutlinedButton, 'Monat 2026-10 wählen'),
            )
            .onPressed,
        isNull,
      );
      expect(
        find.text('Belegten Abrechnungsfall zusammenstellen'),
        findsNothing,
      );
      expect(
        find.text('Ursprünglichen Abrechnungsauftrag erneut senden'),
        findsOneWidget,
      );
      await base.tapVisible(
        t,
        find.text('Abrechnungsfall 2026-10 · Fassung 1').last,
      );
      expect(find.text('Lohn aus diesem Gesamtfall berechnen'), findsNothing);
      expect(find.text('Abrechnungsfall berichtigen'), findsNothing);
      expect(api.sent.length, 1);
    },
  );

  reviewWidgets(
    'revoked read right prevents original opening after a visible selection',
    (t, api, session) async {
      Map<String, dynamic>? opened;
      await openReviewPage(
        t,
        api,
        session,
        onOriginal: (v) async {
          opened = v;
        },
      );
      await base.tapVisible(
        t,
        find.text('Abrechnungsfall 2026-10 · Fassung 1').last,
      );
      final first =
          (base.fixture['saved']['sources']['source_files'] as List).first;
      api.read = false;
      await base.tapVisible(
        t,
        find.text('Personaloriginal: ${first['filename']}').first,
      );
      expect(opened, isNull);
      expect(find.text('Abrechnungsfälle nicht freigegeben'), findsOneWidget);
      expect(find.textContaining('Personaloriginal:'), findsNothing);
      expect(api.sent, isEmpty);
    },
  );
}

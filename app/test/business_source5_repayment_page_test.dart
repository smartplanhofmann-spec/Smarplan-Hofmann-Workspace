import 'dart:convert';
import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:smartplan_office/business_payroll_accounts.dart';
import 'package:smartplan_office/business_session.dart';

import 'business_source5_positive_page_test.dart' as old;

final original = old.copy(
  jsonDecode(File('test/fixtures/source5_repayment.json').readAsStringSync()),
);

class RepaymentApi extends old.PositiveApi {
  RepaymentApi({super.runPage});
  bool repaymentFeature = true;
  @override
  dynamic get f => original;
  @override
  Future<dynamic> call(String path, [Map<String, dynamic>? body]) async {
    final value = await super.call(path, body);
    if (path.startsWith('/api/business/capabilities') && repaymentFeature)
      (value['features'] as List).add('payroll_source5_net_repayments');
    return value;
  }
}

Future<void> fillRepayment(WidgetTester t, RepaymentApi api) async {
  await old.fillPayment(t, api);
  final count = (api.f['prior_payment']['details']['payments'] as List).length;
  await t.enterText(
    find.byKey(ValueKey('business-field-paid_on_$count')),
    '03.11.2026',
  );
}

void main() {
  testWidgets(
    'actual 390px employee repayment retains old readonly money and replays the same negative original after reopening',
    (t) async {
      t.view.physicalSize = const Size(390, 844);
      t.view.devicePixelRatio = 1;
      addTearDown(t.view.resetPhysicalSize);
      addTearDown(t.view.resetDevicePixelRatio);
      final api = RepaymentApi()..losePayment = true;
      final current = BusinessSession(api: api);
      try {
        await old.paymentEditor(t, api, current);
        final count =
            (api.f['prior_payment']['details']['payments'] as List).length;
        for (var i = 0; i < count; i++)
          expect(
            find.byKey(ValueKey('business-field-amount_$i')),
            findsNothing,
          );
        await fillRepayment(t, api);
        await old.press(t, 'Geprüften Lohnkontonachweis speichern');
        expect(api.paymentCommands.length, 1);
        expect(
          api
              .paymentCommands
              .single['details']['payment_source_schema_version'],
          4,
        );
        expect(
          api
              .paymentCommands
              .single['details']['payments']
              .last['amount_minor'],
          -3900,
        );
        expect(current.pending('payroll-account-${api.employee}'), true);
        await t.pumpWidget(const SizedBox.shrink());
        await t.pumpWidget(
          MaterialApp(
            home: BusinessPayrollAccountsPage(
              session: current,
              employee: old.copy(api.f['employee']),
              onOriginal: (_) async {},
            ),
          ),
        );
        await t.pumpAndSettle();
        await old.press(t, 'Ursprünglichen Nachweis erneut senden');
        expect(api.paymentCommands.length, 2);
        expect(api.paymentCommands.first, api.paymentCommands.last);
        expect(current.pending('payroll-account-${api.employee}'), false);
        await t.scrollUntilVisible(
          find.text(
            'Die tatsächliche Rückzahlung des Beschäftigten ist mit ihrem eigenen Tag und Original erfasst. Frühere Zahlungen und der ursprüngliche Bruttozufluss bleiben unverändert. Hier wird kein Geld eingezogen.',
          ),
          300,
        );
        expect(t.takeException(), isNull);
      } finally {
        await t.pumpWidget(const SizedBox.shrink());
        current.dispose();
        api.dispose();
      }
    },
  );

  testWidgets(
    'fresh repayment feature withdrawal blocks a new negative original',
    (t) async {
      final api = RepaymentApi();
      final current = BusinessSession(api: api);
      try {
        await old.paymentEditor(t, api, current);
        await fillRepayment(t, api);
        api.repaymentFeature = false;
        await old.press(t, 'Geprüften Lohnkontonachweis speichern');
        expect(api.paymentCommands, isEmpty);
        expect(current.pending('payroll-account-${api.employee}'), false);
        expect(t.takeException(), isNull);
      } finally {
        await t.pumpWidget(const SizedBox.shrink());
        current.dispose();
        api.dispose();
      }
    },
  );

  testWidgets(
    'actual corrected run explicitly selects repayment review and seals its original after lost reply',
    (t) async {
      final api = RepaymentApi(runPage: true)..loseRun = true;
      final current = BusinessSession(api: api);
      try {
        await old.correctionReason(t, api, current);
        await old.press(t, 'Speichern', settle: false);
        await old.untilVisible(
          t,
          find.text('Zahlungen und Abführungen vollständig prüfen'),
        );
        old.choose(t, 'Belegte Richtung des Nettoausgleichs', 'repayment');
        old.choose(
          t,
          'Geschützter Nachweis des vollständigen Abgleichs',
          api.f['run_input']['settlement_review']['evidence_ref']['id'],
        );
        for (final toggle
            in t
                .widgetList<SwitchListTile>(find.byType(SwitchListTile))
                .toList())
          toggle.onChanged!(true);
        await t.pump();
        await old.press(t, 'Vollständigen Abgleich bestätigen', settle: false);
        await old.untilClosed(t);
        expect(api.previews, 1);
        await t.scrollUntilVisible(
          find.text('Unverbindliche Berechnungsvorschau'),
          300,
          scrollable: find.byType(Scrollable).first,
          maxScrolls: 100,
        );
        await t.pumpAndSettle();
        expect(
          find.textContaining(
            'Belegte Rückzahlungsverpflichtung des Beschäftigten',
          ),
          findsWidgets,
        );
        await old.press(
          t,
          'Ich bestätige ausschließlich diesen geprüften Umfang: Regulärer Gesamtlohn mit vollständigem Einzelanspruch · getrennte Zahlungstage',
        );
        await old.press(t, 'Geprüften Berechnungsumfang festhalten');
        expect(api.runCommands.length, 1);
        await old.press(t, 'Ursprünglichen Auftrag erneut senden');
        expect(api.runCommands.length, 2);
        expect(api.runCommands.first, api.runCommands.last);
        expect(t.takeException(), isNull);
      } finally {
        await t.pumpWidget(const SizedBox.shrink());
        current.dispose();
        api.dispose();
      }
    },
  );
}

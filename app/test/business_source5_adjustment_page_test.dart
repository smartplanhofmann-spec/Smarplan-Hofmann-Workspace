import 'dart:convert';
import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:smartplan_office/business_payroll_accounts.dart';
import 'package:smartplan_office/business_session.dart';

import 'business_source5_positive_page_test.dart' as old;

final originals =
    jsonDecode(
          File('test/fixtures/source5_adjustments.json').readAsStringSync(),
        )['cases']
        as List;

class AdjustmentApi extends old.PositiveApi {
  AdjustmentApi({super.runPage, this.index = 0});
  final int index;
  bool adjustmentFeature = true;
  @override
  dynamic get f => originals[index];
  @override
  Future<dynamic> call(String path, [Map<String, dynamic>? body]) async {
    final value = await super.call(path, body);
    if (path.startsWith('/api/business/capabilities') && adjustmentFeature)
      (value['features'] as List).add('payroll_source5_net_adjustments');
    return value;
  }
}

Future<void> paymentEditor(
  WidgetTester t,
  AdjustmentApi api,
  BusinessSession session,
) async {
  if (api.f['label'] != 'zero') {
    await old.paymentEditor(t, api, session);
    return;
  }
  await session.load();
  await t.pumpWidget(
    MaterialApp(
      home: BusinessPayrollAccountsPage(
        session: session,
        employee: old.copy(api.f['employee']),
        onOriginal: (_) async {},
      ),
    ),
  );
  await t.pumpAndSettle();
  await old.press(t, 'Tatsächliche Lohnzahlung erfassen');
  old.choose(
    t,
    'Abgeschlossene Monatsberechnung',
    '${api.f['run']['id']}@${api.f['run']['revision']}',
  );
  await t.pump();
  await old.press(t, 'Ausgewählten Lauf prüfen');
  old.choose(
    t,
    'Letzte tatsächlich belegte Monatsgruppenzahlung',
    '${api.f['prior_payment']['id']}@${api.f['prior_payment']['revision']}',
  );
  await t.pump();
  await old.press(t, 'Bisherigen Zahlungsursprung festhalten');
  expect(find.byKey(const ValueKey('business-field-count')), findsNothing);
}

Future<void> fillAdjustment(WidgetTester t, AdjustmentApi api) async {
  if (api.f['label'] == 'zero') {
    old.choose(
      t,
      'Gültiger Stamm- und Steuermerkmalsnachweis',
      '${api.f['details']['identity_id']}@${api.f['details']['identity_revision']}',
    );
    old.choose(
      t,
      'Geschütztes Original des Nachweises',
      api.f['payment']['source_file']['id'],
    );
    await t.enterText(
      find.byKey(const ValueKey('business-field-tax_free_payments_minor')),
      '0.00',
    );
    for (final toggle
        in t.widgetList<SwitchListTile>(find.byType(SwitchListTile)).toList()) {
      toggle.onChanged!(true);
    }
    await t.pump();
    return;
  }
  await old.fillPayment(t, api);
  final count = (api.f['prior_payment']['details']['payments'] as List).length;
  await t.enterText(
    find.byKey(ValueKey('business-field-paid_on_$count')),
    '03.11.2026',
  );
}

void main() {
  for (var index = 0; index < originals.length; index++) {
    group(originals[index]['label'] as String, () {
      testWidgets(
        'actual 390px mixed net adjustment retains old readonly money and replays the same signed original after reopening',
        (t) async {
          t.view.physicalSize = const Size(390, 844);
          t.view.devicePixelRatio = 1;
          addTearDown(t.view.resetPhysicalSize);
          addTearDown(t.view.resetDevicePixelRatio);
          final api = AdjustmentApi(index: index)..losePayment = true;
          final current = BusinessSession(api: api);
          try {
            await paymentEditor(t, api, current);
            final count =
                (api.f['prior_payment']['details']['payments'] as List).length;
            for (var i = 0; i < count; i++)
              expect(
                find.byKey(ValueKey('business-field-amount_$i')),
                findsNothing,
              );
            await fillAdjustment(t, api);
            await old.press(t, 'Geprüften Lohnkontonachweis speichern');
            expect(api.paymentCommands.length, 1);
            expect(
              api
                  .paymentCommands
                  .single['details']['payment_source_schema_version'],
              5,
            );
            expect(
              api
                  .paymentCommands
                  .single['details']['payments']
                  .last['amount_minor'],
              api.f['details']['payments'].last['amount_minor'],
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
                api.f['label'] == 'zero'
                    ? 'Keine Nettodifferenz. Ausschließlich der unveränderte bisherige Zahlungspräfix ist bestätigt; kein neuer Geldfluss.'
                    : 'Der weitere Nettoausgleich ist mit seinen tatsächlichen Zahlungsteilen belegt. Frühere Zahlungen, Rückzahlungen und der ursprüngliche Bruttozufluss bleiben unverändert.',
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
        'fresh repayment feature withdrawal blocks a new signed original',
        (t) async {
          final api = AdjustmentApi(index: index);
          final current = BusinessSession(api: api);
          try {
            await paymentEditor(t, api, current);
            await fillAdjustment(t, api);
            api.adjustmentFeature = false;
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
        'actual corrected run explicitly selects further adjustment review and seals its original after lost reply',
        (t) async {
          final api = AdjustmentApi(index: index, runPage: true)
            ..loseRun = true;
          final current = BusinessSession(api: api);
          try {
            await old.correctionReason(t, api, current);
            await old.press(t, 'Speichern', settle: false);
            await old.untilVisible(
              t,
              find.text('Zahlungen und Abführungen vollständig prüfen'),
            );
            old.choose(t, 'Belegte Richtung des Nettoausgleichs', 'adjustment');
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
            await old.press(
              t,
              'Vollständigen Abgleich bestätigen',
              settle: false,
            );
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
              find.textContaining('Weiterer belegter Nettoausgleich'),
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
    });
  }
}

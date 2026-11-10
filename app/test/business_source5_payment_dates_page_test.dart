import 'dart:convert';
import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:smartplan_office/business_payroll_accounts.dart';
import 'package:smartplan_office/business_session.dart';

import 'business_source5_positive_page_test.dart' as old;

final dates = jsonDecode(
  File('test/fixtures/source5_payment_dates.json').readAsStringSync(),
) as Map<String, dynamic>;

class ActualDatesApi extends old.PositiveApi {
  ActualDatesApi(this.index);
  final int index;
  bool datesFeature = true;
  @override
  dynamic get f => {
    ...old.copy(dates['cases'][index]),
    'employee': dates['employee'],
    'files': [dates['evidence_file']],
    'payment_command': dates['cases'][index]['command'],
  };
  @override
  Future<dynamic> call(String path, [Map<String, dynamic>? body]) async {
    final value = await super.call(path, body);
    if (path.startsWith('/api/business/capabilities') && datesFeature) {
      (value['features'] as List).add('payroll_source5_payment_dates');
    }
    return value;
  }
}

Future<void> fillActualDate(WidgetTester t, ActualDatesApi api) async {
  await old.fillPayment(t, api);
  final count = (api.f['prior_payment']['details']['payments'] as List).length;
  final day =
      api.f['payment']['details']['payments'][count]['paid_on'] as String;
  final parts = day.split('-');
  await t.enterText(
    find.byKey(ValueKey('business-field-paid_on_$count')),
    '${parts[2]}.${parts[1]}.${parts[0]}',
  );
}

void main() {
  testWidgets(
    'two later actual dates preserve originals and replay lost replies after reopening at 390px',
    (t) async {
      t.view.physicalSize = const Size(390, 844);
      t.view.devicePixelRatio = 1;
      addTearDown(t.view.resetPhysicalSize);
      addTearDown(t.view.resetDevicePixelRatio);
      for (var index = 0; index < 2; index++) {
        final api = ActualDatesApi(index)..losePayment = true;
        final session = BusinessSession(api: api);
        try {
          await old.paymentEditor(t, api, session);
          await fillActualDate(t, api);
          await old.press(t, 'Geprüften Lohnkontonachweis speichern');
          expect(api.paymentCommands.length, 1);
          expect(
            api
                .paymentCommands
                .single['details']['payment_source_schema_version'],
            3,
          );
          expect(session.pending('payroll-account-${api.employee}'), true);
          await t.pumpWidget(const SizedBox.shrink());
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
          await old.press(t, 'Ursprünglichen Nachweis erneut senden');
          expect(api.paymentCommands.length, 2);
          expect(api.paymentCommands.first, api.paymentCommands.last);
          expect(session.pending('payroll-account-${api.employee}'), false);
          final actualNotice = find.text(
            'Die ursprünglichen Bruttozuflüsse bleiben unverändert. Zusätzliche Nettozahlungen sind an ihren tatsächlichen belegten Zahlungstagen erfasst.',
          );
          await t.scrollUntilVisible(actualNotice, 300);
          expect(actualNotice, findsOneWidget);
          expect(t.takeException(), isNull);
        } finally {
          await t.pumpWidget(const SizedBox.shrink());
          session.dispose();
          api.dispose();
        }
      }
    },
  );

  testWidgets('fresh actual-date feature withdrawal blocks a new V3 command', (
    t,
  ) async {
    final api = ActualDatesApi(0);
    final current = BusinessSession(api: api);
    try {
      await old.paymentEditor(t, api, current);
      await fillActualDate(t, api);
      api.datesFeature = false;
      await old.press(t, 'Geprüften Lohnkontonachweis speichern');
      expect(api.paymentCommands, isEmpty);
      expect(current.pending('payroll-account-${api.employee}'), false);
      expect(t.takeException(), isNull);
    } finally {
      await t.pumpWidget(const SizedBox.shrink());
      current.dispose();
      api.dispose();
    }
  });
}

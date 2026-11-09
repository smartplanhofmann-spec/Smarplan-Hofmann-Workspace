import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:smartplan_office/api.dart';
import 'package:smartplan_office/business_payroll.dart';
import 'package:smartplan_office/business_payroll_accounts.dart';
import 'package:smartplan_office/business_session.dart';
import 'package:smartplan_office/business_widgets.dart';

final all = jsonDecode(
  File('test/fixtures/source5_positive_corrections.json').readAsStringSync(),
) as Map<String, dynamic>;
Map<String, dynamic> copy(dynamic value) =>
    Map<String, dynamic>.from(jsonDecode(jsonEncode(value)) as Map);

class PositiveApi extends OfficeApi {
  PositiveApi({this.runPage = false, this.scenario = 'correction'})
    : super(apiVersion: 'v1') {
    token = 'synthetic-positive-source5';
  }
  final bool runPage;
  final String scenario;
  bool approve = true,
      feature = true,
      acceptedPayment = false,
      acceptedRun = false,
      losePayment = false,
      loseRun = false;
  int previews = 0;
  Completer<void>? heldPayment;
  Completer<void>? heldAccountRead, heldFileRead;
  int accountReads = 0, fileReads = 0;
  final paymentCommands = <Map<String, dynamic>>[],
      runCommands = <Map<String, dynamic>>[];
  dynamic get f => all[scenario];
  String get employee => f['run']['employee_id'];
  @override
  Future<dynamic> call(String path, [Map<String, dynamic>? body]) async {
    if (path.startsWith('/api/business/capabilities'))
      return {
        'compatibility_mode': 'business',
        'storage_version': 10,
        'generation': 1,
        'readonly': false,
        'features': [
          'german_payroll_2026',
          'payroll_wage_account',
          'personnel_preparation',
          'payroll_multiple_cases',
          if (feature) 'payroll_source5_positive_corrections',
        ],
        'capabilities': [
          'business_payroll',
          'business_payroll_accounts',
          'business_personnel_workflow',
          'business_planning',
          'business_payroll_multiple_cases',
        ],
        'permissions': [
          'personnel.read',
          'personnel.write',
          if (approve) 'personnel.approve',
          'personnel.export',
        ],
        'organization': {
          'modules': {
            'personnel': {'enabled': true, 'visible': true},
          },
        },
      };
    if (path == '/api/me') return {'id': 'f' * 32};
    if (path == '/api/business/employees') return [f['employee']];
    if (path.startsWith('/api/business/payroll/account-records?')) {
      accountReads++;
      if (heldAccountRead != null) await heldAccountRead!.future;
      return {
        'employee_id': employee,
        'items': [
          copy(f['payment']['sources']['identity']),
          copy(f['prior_payment']),
          if (acceptedPayment) copy(f['payment']),
        ],
      };
    }
    if (path.startsWith('/api/business/payroll/profiles?'))
      return {
        'employee_id': employee,
        'items': [copy(f['run']['source']['profile'])],
      };
    if (path.startsWith('/api/business/payroll/runs?'))
      return {
        'employee_id': employee,
        'items': [copy(runPage && !acceptedRun ? f['prior_run'] : f['run'])],
      };
    if (path.startsWith('/api/business/personnel/files?')) {
      fileReads++;
      if (heldFileRead != null) await heldFileRead!.future;
      return {'employee_id': employee, 'items': f['files']};
    }
    if (path.startsWith('/api/business/personnel/payroll-preparations?'))
      return {
        'employee_id': employee,
        'items': [copy(f['run']['source']['preparation'])],
      };
    if (path == '/api/business/payroll/rules')
      return {
        'rules': {'version': 'synthetic real fixture'},
      };
    if (path.startsWith(
      '/api/business/payroll/multiple-one-off-cases/sources?',
    ))
      return {
        ...copy(f['sources']),
        'multiple_one_off_cases': [copy(f['case'])],
      };
    if (path == '/api/business/payroll/preview') {
      previews++;
      expect(body, f['run_input']);
      return copy(f['run_preview']);
    }
    if (path == '/api/business/payroll/runs') {
      runCommands.add(copy(body));
      expect(
        copy(body)..remove('request_id'),
        copy(f['run_command'])..remove('request_id'),
      );
      acceptedRun = true;
      if (loseRun) {
        loseRun = false;
        throw const ApiException(0, 'Synthetic accepted run response lost');
      }
      return copy(f['run']);
    }
    if (path == '/api/business/payroll/account-records') {
      paymentCommands.add(copy(body));
      expect(
        copy(body)..remove('request_id'),
        copy(f['payment_command'])..remove('request_id'),
      );
      acceptedPayment = true;
      if (heldPayment != null) await heldPayment!.future;
      if (losePayment) {
        losePayment = false;
        throw const ApiException(0, 'Synthetic accepted payment response lost');
      }
      return copy(f['payment']);
    }
    throw StateError('Unexpected $path');
  }
}

Future<void> press(WidgetTester t, String text, {bool settle = true}) async {
  final matches = find.text(text);
  if (matches.evaluate().isEmpty) {
    final s = t.state<ScrollableState>(find.byType(Scrollable).first);
    s.position.jumpTo(s.position.minScrollExtent);
    if (settle) {
      await t.pumpAndSettle();
    } else {
      await t.pump();
    }
    await t.scrollUntilVisible(
      matches,
      300,
      scrollable: find.byType(Scrollable).first,
      maxScrolls: 100,
    );
  }
  final target = matches.last;
  await t.ensureVisible(target);
  if (settle) {
    await t.pumpAndSettle();
  } else {
    await t.pump();
  }
  await t.tap(target);
  if (settle) {
    await t.pumpAndSettle();
  } else {
    await t.pump();
  }
}

Future<void> untilVisible(WidgetTester t, Finder target) async {
  for (var frame = 0; frame < 100 && target.evaluate().isEmpty; frame++) {
    await t.pump(const Duration(milliseconds: 16));
  }
  expect(target, findsWidgets);
}

Future<void> untilClosed(WidgetTester t) async {
  for (
    var frame = 0;
    frame < 100 && find.byType(BusinessEditor).evaluate().isNotEmpty;
    frame++
  ) {
    await t.pump(const Duration(milliseconds: 16));
  }
  expect(find.byType(BusinessEditor), findsNothing);
}

void choose(WidgetTester t, String label, String value) {
  final field = t
      .widgetList<DropdownButtonFormField<String>>(
        find.byType(DropdownButtonFormField<String>),
      )
      .firstWhere((w) => w.decoration.labelText == label);
  field.onChanged!(value);
}

Future<void> paymentEditor(
  WidgetTester t,
  PositiveApi api,
  BusinessSession session,
) async {
  await session.load();
  await t.pumpWidget(
    MaterialApp(
      home: BusinessPayrollAccountsPage(
        session: session,
        employee: copy(api.f['employee']),
        onOriginal: (_) async {},
      ),
    ),
  );
  await t.pumpAndSettle();
  await press(t, 'Tatsächliche Lohnzahlung erfassen');
  choose(
    t,
    'Abgeschlossene Monatsberechnung',
    '${api.f['run']['id']}@${api.f['run']['revision']}',
  );
  await t.pump();
  await press(t, 'Ausgewählten Lauf prüfen');
  if (!api.feature) return;
  choose(
    t,
    'Letzte tatsächlich belegte Monatsgruppenzahlung',
    '${api.f['prior_payment']['id']}@${api.f['prior_payment']['revision']}',
  );
  await t.pump();
  await press(t, 'Bisherigen Zahlungsursprung festhalten');
  await t.enterText(
    find.byKey(const ValueKey('business-field-count')),
    '${api.f['payment']['details']['payments'].length}',
  );
  await press(t, 'Zahlungsnachweise erfassen');
}

Future<void> fillPayment(WidgetTester t, PositiveApi api) async {
  final f = api.f,
      count = (f['prior_payment']['details']['payments'] as List).length;
  choose(
    t,
    'Gültiger Stamm- und Steuermerkmalsnachweis',
    '${f['payment']['details']['identity_id']}@${f['payment']['details']['identity_revision']}',
  );
  choose(
    t,
    'Geschütztes Original des Nachweises',
    f['payment']['source_file']['id'],
  );
  final part = f['payment']['details']['payments'][count],
      allocation = f['payment']['details']['settlement_allocations'][count];
  final values = {
    'paid_on_$count': '31.10.2026',
    'amount_$count': (part['amount_minor'] / 100).toStringAsFixed(2),
    'reference_$count': part['payment_reference'],
    'running_$count': '0.00',
    'bonus_$count': (allocation['one_off_allocations'][0]['net_minor'] / 100)
        .toStringAsFixed(2),
    'tax_free_payments_minor': '0.00',
  };
  for (final e in values.entries)
    await t.enterText(find.byKey(ValueKey('business-field-${e.key}')), e.value);
  for (final toggle
      in t.widgetList<SwitchListTile>(find.byType(SwitchListTile)).toList())
    toggle.onChanged!(true);
  await t.pump();
}

Future<void> correctionReason(
  WidgetTester t,
  PositiveApi api,
  BusinessSession session,
) async {
  await session.load();
  await t.pumpWidget(
    MaterialApp(
      home: BusinessPayrollPage(
        session: session,
        employee: copy(api.f['employee']),
      ),
    ),
  );
  await t.pumpAndSettle();
  await press(t, 'Monatsgruppen mit getrennten Zahlungstagen öffnen');
  await press(t, 'Monatsgruppenmonat wählen');
  await t.enterText(find.byType(TextField).first, '2026-10');
  await press(t, 'Monat öffnen');
  await press(t, 'Monatsgruppe 2026-10 · Fassung ${api.f['case']['revision']}');
  await press(t, 'Lohn mit dieser Monatsgruppe berechnen');
  await t.enterText(
    find.byKey(const ValueKey('business-field-reason')),
    api.f['run_command']['correction_reason'],
  );
}

void main() {
  testWidgets(
    'two real cumulative positive payments preserve readonly originals and exact lost-reply retry',
    (t) async {
      t.view.physicalSize = const Size(390, 844);
      t.view.devicePixelRatio = 1;
      addTearDown(t.view.resetPhysicalSize);
      addTearDown(t.view.resetDevicePixelRatio);
      for (final key in ['correction', 'second_correction']) {
        final api = PositiveApi(scenario: key)..losePayment = true,
            session = BusinessSession(api: api);
        try {
          await paymentEditor(t, api, session);
          final count =
              (api.f['prior_payment']['details']['payments'] as List).length;
          for (var i = 0; i < count; i++) {
            expect(
              find.byKey(ValueKey('business-field-amount_$i')),
              findsNothing,
            );
            expect(
              find.byKey(ValueKey('business-field-running_$i')),
              findsNothing,
            );
            expect(
              find.byKey(ValueKey('business-field-bonus_$i')),
              findsNothing,
            );
          }
          final editor = t.widget<BusinessEditor>(find.byType(BusinessEditor));
          expect(editor.initial['amount_$count'], '');
          expect(
            editor.fields
                .where((f) => f.name.startsWith('preserved_allocation_'))
                .length,
            count,
          );
          await fillPayment(t, api);
          await t.enterText(
            find.byKey(ValueKey('business-field-amount_$count')),
            '0.01',
          );
          await press(t, 'Geprüften Lohnkontonachweis speichern');
          expect(api.paymentCommands, isEmpty);
          expect(session.pending('payroll-account-${api.employee}'), false);
          final input = t.widget<TextFormField>(
            find.byKey(ValueKey('business-field-amount_$count')),
          );
          expect(input.enabled, true);
          await t.enterText(
            find.byKey(ValueKey('business-field-amount_$count')),
            (api.f['payment']['details']['payments'][count]['amount_minor'] /
                    100)
                .toStringAsFixed(2),
          );
          await press(t, 'Geprüften Lohnkontonachweis speichern');
          expect(api.paymentCommands.length, 1);
          expect(session.pending('payroll-account-${api.employee}'), true);
          await t.pumpWidget(const SizedBox.shrink());
          await t.pumpWidget(
            MaterialApp(
              home: BusinessPayrollAccountsPage(
                session: session,
                employee: copy(api.f['employee']),
                onOriginal: (_) async {},
              ),
            ),
          );
          await t.pumpAndSettle();
          await press(t, 'Ursprünglichen Nachweis erneut senden');
          expect(api.paymentCommands.length, 2);
          expect(api.paymentCommands.first, api.paymentCommands.last);
          expect(session.pending('payroll-account-${api.employee}'), false);
          expect(t.takeException(), isNull);
        } finally {
          await t.pumpWidget(const SizedBox.shrink());
          session.dispose();
          api.dispose();
        }
      }
    },
  );

  testWidgets(
    'fresh approval withdrawal blocks positive payment before posting',
    (t) async {
      final api = PositiveApi(), session = BusinessSession(api: api);
      try {
        await paymentEditor(t, api, session);
        await fillPayment(t, api);
        api.approve = false;
        await press(t, 'Geprüften Lohnkontonachweis speichern');
        expect(api.paymentCommands, isEmpty);
        expect(t.takeException(), isNull);
      } finally {
        await t.pumpWidget(const SizedBox.shrink());
        session.dispose();
        api.dispose();
      }
    },
  );

  testWidgets(
    'a real late accepted reply does not reopen a closed payment editor',
    (t) async {
      final api = PositiveApi()..heldPayment = Completer<void>(),
          session = BusinessSession(api: api);
      try {
        await paymentEditor(t, api, session);
        await fillPayment(t, api);
        await press(t, 'Geprüften Lohnkontonachweis speichern', settle: false);
        for (var i = 0; i < 100 && api.paymentCommands.isEmpty; i++)
          await t.pump(const Duration(milliseconds: 16));
        expect(api.paymentCommands.length, 1);
        final sent = copy(api.paymentCommands.single);
        await t.pumpWidget(const SizedBox.shrink());
        await t.pumpWidget(
          MaterialApp(
            home: BusinessPayrollAccountsPage(
              session: session,
              employee: copy(api.f['employee']),
              onOriginal: (_) async {},
            ),
          ),
        );
        await t.pump();
        api.heldPayment!.complete();
        await t.pumpAndSettle();
        expect(api.paymentCommands.single, sent);
        expect(api.paymentCommands.length, 1);
        expect(session.pending('payroll-account-${api.employee}'), false);
        expect(find.byType(BusinessEditor), findsNothing);
        expect(t.takeException(), isNull);
      } finally {
        if (!api.heldPayment!.isCompleted) api.heldPayment!.complete();
        await t.pumpWidget(const SizedBox.shrink());
        session.dispose();
        api.dispose();
      }
    },
  );

  testWidgets('legacy capability cannot create the new positive payment', (
    t,
  ) async {
    final api = PositiveApi()..feature = false,
        session = BusinessSession(api: api);
    try {
      await paymentEditor(t, api, session);
      expect(api.paymentCommands, isEmpty);
      expect(
        find.textContaining(
          'unterstützt diese belegte zusätzliche Nettozahlung',
        ),
        findsOneWidget,
      );
    } finally {
      await t.pumpWidget(const SizedBox.shrink());
      session.dispose();
      api.dispose();
    }
  });

  testWidgets(
    'actual corrected run requires explicit complete original evidence and seals transition on retry',
    (t) async {
      final api = PositiveApi(runPage: true)..loseRun = true,
          session = BusinessSession(api: api);
      try {
        await session.load();
        await t.pumpWidget(
          MaterialApp(
            home: BusinessPayrollPage(
              session: session,
              employee: copy(api.f['employee']),
            ),
          ),
        );
        await t.pumpAndSettle();
        await press(t, 'Monatsgruppen mit getrennten Zahlungstagen öffnen');
        await press(t, 'Monatsgruppenmonat wählen');
        await t.enterText(find.byType(TextField).first, '2026-10');
        await press(t, 'Monat öffnen');
        await press(
          t,
          'Monatsgruppe 2026-10 · Fassung ${api.f['case']['revision']}',
        );
        await press(t, 'Lohn mit dieser Monatsgruppe berechnen');
        await t.enterText(
          find.byKey(const ValueKey('business-field-reason')),
          api.f['run_command']['correction_reason'],
        );
        await press(t, 'Speichern', settle: false);
        await untilVisible(
          t,
          find.text('Zahlungen und Abführungen vollständig prüfen'),
        );
        final review = t.widget<BusinessEditor>(
          find.byType(BusinessEditor).last,
        );
        expect(review.initial['payments_complete'], false);
        expect(review.initial['remittances_complete'], false);
        choose(
          t,
          'Geschützter Nachweis des vollständigen Abgleichs',
          api.f['run_input']['settlement_review']['evidence_ref']['id'],
        );
        await press(t, 'Vollständigen Abgleich bestätigen', settle: false);
        expect(api.previews, 0);
        for (final toggle
            in t
                .widgetList<SwitchListTile>(find.byType(SwitchListTile))
                .toList())
          toggle.onChanged!(true);
        await t.pump();
        await press(t, 'Vollständigen Abgleich bestätigen', settle: false);
        await untilClosed(t);
        await t.scrollUntilVisible(
          find.text('Unverbindliche Berechnungsvorschau'),
          300,
          scrollable: find.byType(Scrollable).first,
          maxScrolls: 100,
        );
        await t.pumpAndSettle();
        expect(api.previews, 1);
        expect(
          find.textContaining('Belegte zusätzliche Nettozahlung'),
          findsWidgets,
        );
        await press(
          t,
          'Ich bestätige ausschließlich diesen geprüften Umfang: Regulärer Gesamtlohn mit vollständigem Einzelanspruch · getrennte Zahlungstage',
        );
        await press(t, 'Geprüften Berechnungsumfang festhalten');
        expect(api.runCommands.length, 1);
        await press(t, 'Ursprünglichen Auftrag erneut senden');
        expect(api.runCommands.length, 2);
        expect(api.runCommands.first, api.runCommands.last);
        expect(t.takeException(), isNull);
      } finally {
        await t.pumpWidget(const SizedBox.shrink());
        session.dispose();
        api.dispose();
      }
    },
  );

  testWidgets(
    'late prior-payment or original-file read cannot reopen a cancelled correction dialog',
    (t) async {
      for (final step in ['accounts', 'file']) {
        final api = PositiveApi(runPage: true),
            session = BusinessSession(api: api);
        try {
          await correctionReason(t, api, session);
          if (step == 'accounts') api.heldAccountRead = Completer<void>();
          await press(t, 'Speichern', settle: false);
          if (step == 'accounts') {
            for (var frame = 0; frame < 100 && api.accountReads == 0; frame++)
              await t.pump(const Duration(milliseconds: 16));
            expect(api.accountReads, 1);
          } else {
            await untilVisible(
              t,
              find.text('Zahlungen und Abführungen vollständig prüfen'),
            );
            choose(
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
            final before = api.fileReads;
            api.heldFileRead = Completer<void>();
            await press(t, 'Vollständigen Abgleich bestätigen', settle: false);
            for (var frame = 0; frame < 100 && api.fileReads == before; frame++)
              await t.pump(const Duration(milliseconds: 16));
            expect(api.fileReads, greaterThan(before));
          }
          // Cancel only the actual active dialog; the payroll page stays mounted.
          Navigator.of(t.element(find.byType(BusinessEditor).last)).pop();
          await t.pumpAndSettle();
          if (step == 'accounts') {
            api.heldAccountRead!.complete();
          } else {
            api.heldFileRead!.complete();
          }
          await t.pumpAndSettle();
          expect(api.previews, 0);
          expect(api.runCommands, isEmpty);
          expect(find.byType(BusinessEditor), findsNothing);
          expect(t.takeException(), isNull);
        } finally {
          if (api.heldAccountRead != null && !api.heldAccountRead!.isCompleted)
            api.heldAccountRead!.complete();
          if (api.heldFileRead != null && !api.heldFileRead!.isCompleted)
            api.heldFileRead!.complete();
          await t.pumpWidget(const SizedBox.shrink());
          session.dispose();
          api.dispose();
        }
      }
    },
  );
}

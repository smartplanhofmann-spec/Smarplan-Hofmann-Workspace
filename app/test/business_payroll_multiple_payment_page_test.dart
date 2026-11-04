import 'dart:convert';
import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:smartplan_office/api.dart';
import 'package:smartplan_office/business_payroll_accounts.dart';
import 'package:smartplan_office/business_session.dart';
import 'package:smartplan_office/business_widgets.dart';

final all = jsonDecode(
      File('test/fixtures/payroll_multiple_runs.json').readAsStringSync(),
    ) as Map<String, dynamic>,
    f = all['paid_v5_upgrade'];
Map<String, dynamic> copy(dynamic v) =>
    Map<String, dynamic>.from(jsonDecode(jsonEncode(v)) as Map);
final employee = copy(f['case']['sources']['employee']),
    id = employee['id'] as String;

class PaymentApi extends OfficeApi {
  PaymentApi() : super(apiVersion: 'v1') {
    token = 'synthetic-source5-payment';
  }
  bool approve = true, accepted = false, lose = true;
  final commands = <Map<String, dynamic>>[];
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
        ],
        'capabilities': [
          'business_payroll',
          'business_payroll_accounts',
          'business_personnel_workflow',
          'business_planning',
        ],
        'permissions': ['personnel.read', if (approve) 'personnel.approve'],
        'organization': {
          'modules': {
            'personnel': {'enabled': true, 'visible': true},
          },
        },
      };
    if (path == '/api/me') return {'id': 'f' * 32};
    if (path == '/api/business/employees') return [employee];
    if (path.startsWith('/api/business/payroll/account-records?'))
      return {
        'employee_id': id,
        'items': [
          copy(f['payment']['sources']['identity']),
          copy(f['original_payment']),
          if (accepted) copy(f['payment']),
        ],
      };
    if (path.startsWith('/api/business/payroll/profiles?'))
      return {
        'employee_id': id,
        'items': [copy(f['run']['source']['profile'])],
      };
    if (path.startsWith('/api/business/payroll/runs?'))
      return {
        'employee_id': id,
        'items': [copy(f['run'])],
      };
    if (path.startsWith('/api/business/personnel/files?'))
      return {
        'employee_id': id,
        'items': [copy(f['case']['sources']['source_files'][0])],
      };
    if (path == '/api/business/payroll/account-records') {
      commands.add(copy(body));
      expect(
        copy(body)..remove('request_id'),
        copy(f['payment_command'])..remove('request_id'),
      );
      accepted = true;
      if (lose) {
        lose = false;
        throw const ApiException(0, 'Synthetic accepted payment response lost');
      }
      return copy(f['payment']);
    }
    throw StateError(path);
  }
}

Future<void> press(WidgetTester t, String label) async {
  final target = find.text(label).last;
  await t.ensureVisible(target);
  await t.pumpAndSettle();
  await t.tap(target);
  await t.pumpAndSettle();
}

void choose(WidgetTester t, String label, String value) {
  final field = t
      .widgetList<DropdownButtonFormField<String>>(
        find.byType(DropdownButtonFormField<String>),
      )
      .firstWhere((w) => w.decoration.labelText == label);
  field.onChanged!(value);
}

Future<void> start(
  WidgetTester t,
  PaymentApi api,
  BusinessSession session, {
  int count = 2,
}) async {
  await session.load();
  await t.pumpWidget(
    MaterialApp(
      home: BusinessPayrollAccountsPage(
        session: session,
        employee: employee,
        onOriginal: (_) async {},
      ),
    ),
  );
  await t.pumpAndSettle();
  await press(t, 'Tatsächliche Lohnzahlung erfassen');
  choose(
    t,
    'Abgeschlossene Monatsberechnung',
    '${f['run']['id']}@${f['run']['revision']}',
  );
  await t.pump();
  await press(t, 'Ausgewählten Lauf prüfen');
  choose(
    t,
    'Bereits belegte laufende Originalzahlung',
    '${f['original_payment']['id']}@${f['original_payment']['revision']}',
  );
  await t.pump();
  await press(t, 'Laufenden Zahlungsursprung festhalten');
  await t.enterText(
    find.byKey(const ValueKey('business-field-count')),
    '$count',
  );
  await press(t, 'Zahlungsnachweise erfassen');
}

void main() {
  testWidgets(
    'actual paid v5 prefix is visible but never editable; missing bonus saves exact Source5 payment and retries lost ACK',
    (t) async {
      t.view.physicalSize = const Size(390, 844);
      t.view.devicePixelRatio = 1;
      addTearDown(t.view.resetPhysicalSize);
      addTearDown(t.view.resetDevicePixelRatio);
      final api = PaymentApi(), session = BusinessSession(api: api);
      try {
        await start(t, api, session);
        expect(
          find.byKey(const ValueKey('business-field-amount_0')),
          findsNothing,
        );
        expect(
          find.byKey(const ValueKey('business-field-reference_0')),
          findsNothing,
        );
        final editor = t.widget<BusinessEditor>(find.byType(BusinessEditor));
        expect(
          editor.fields
              .where((f) => f.name == 'preserved_0')
              .single
              .choices
              .values
              .single,
          contains(
            f['original_payment']['details']['payments'][0]['payment_reference'],
          ),
        );
        expect(editor.initial['amount_1'], '');
        expect(editor.initial['running_1'], '');
        expect(editor.initial['bonus_1'], '');
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
        final part = f['payment']['details']['payments'][1],
            allocation = f['payment']['details']['settlement_allocations'][1];
        for (final entry in {
          'paid_on_1': '31.10.2026',
          'amount_1': (part['amount_minor'] / 100).toStringAsFixed(2),
          'reference_1': part['payment_reference'],
          'running_1': '0.00',
          'bonus_1': (allocation['one_off_allocations'][0]['net_minor'] / 100)
              .toStringAsFixed(2),
          'tax_free_payments_minor': '0.00',
        }.entries)
          await t.enterText(
            find.byKey(ValueKey('business-field-${entry.key}')),
            entry.value,
          );
        for (final toggle
            in t
                .widgetList<SwitchListTile>(find.byType(SwitchListTile))
                .toList())
          toggle.onChanged!(true);
        await t.pump();
        await press(t, 'Geprüften Lohnkontonachweis speichern');
        expect(
          api.commands.length,
          1,
          reason: t
              .widgetList<Text>(find.byType(Text))
              .map((v) => v.data)
              .join(' | '),
        );
        expect(session.pending('payroll-account-$id'), true);
        await t.pumpWidget(const SizedBox.shrink());
        await t.pumpWidget(
          MaterialApp(
            home: BusinessPayrollAccountsPage(
              session: session,
              employee: employee,
              onOriginal: (_) async {},
            ),
          ),
        );
        await t.pumpAndSettle();
        await press(t, 'Ursprünglichen Nachweis erneut senden');
        expect(api.commands.length, 2);
        expect(api.commands.first, api.commands.last);
        expect(session.pending('payroll-account-$id'), false);
        expect(t.takeException(), isNull);
      } finally {
        await t.pumpWidget(const SizedBox.shrink());
        session.dispose();
        api.dispose();
      }
    },
  );
  testWidgets(
    'approval withdrawal removes Source5 payment editor before any transfer evidence is sent',
    (t) async {
      final api = PaymentApi(), session = BusinessSession(api: api);
      try {
        await start(t, api, session, count: 3);
        final names = t
            .widget<BusinessEditor>(find.byType(BusinessEditor))
            .fields
            .map((f) => f.name)
            .toList();
        expect(names.toSet().length, names.length);
        api.approve = false;
        await session.load();
        await t.pumpAndSettle();
        expect(find.byType(BusinessEditor), findsNothing);
        expect(api.commands, isEmpty);
        expect(t.takeException(), isNull);
      } finally {
        await t.pumpWidget(const SizedBox.shrink());
        session.dispose();
        api.dispose();
      }
    },
  );
}

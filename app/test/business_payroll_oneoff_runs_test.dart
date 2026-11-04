import 'dart:convert';
import 'dart:io';
import 'dart:typed_data';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:smartplan_office/api.dart';
import 'package:smartplan_office/business_payroll.dart';
import 'package:smartplan_office/business_payroll_accounts.dart';
import 'package:smartplan_office/business_payroll_oneoff_case_contract.dart';
import 'package:smartplan_office/business_session.dart';

final f = jsonDecode(
  File('test/fixtures/payroll_oneoff_runs.json').readAsStringSync(),
) as Map<String, dynamic>;
Map<String, dynamic> copy(dynamic value) =>
    Map<String, dynamic>.from(jsonDecode(jsonEncode(value)) as Map);
final id = f['run']['employee_id'] as String;
final employee = {
  ...copy(f['sources']['employee']),
  'name': 'Synthetic source4 employee',
};

class OneOffRunApi extends OfficeApi {
  OneOffRunApi() : super(apiVersion: 'v1') {
    token = 'synthetic-source4-session';
  }
  bool accepted = false, lose = false;
  int previews = 0;
  final commands = <Map<String, dynamic>>[];
  @override
  Future<dynamic> call(String path, [Map<String, dynamic>? body]) async {
    if (path.startsWith('/api/business/capabilities'))
      return {
        'compatibility_mode': 'business',
        'storage_version': 8,
        'generation': 1,
        'readonly': false,
        'features': [
          'german_payroll_2026',
          'personnel_preparation',
          'payroll_oneoff_cases',
        ],
        'capabilities': [
          'business_payroll',
          'business_personnel_workflow',
          'business_planning',
          'business_payroll_oneoff_cases',
        ],
        'permissions': [
          'personnel.read',
          'personnel.write',
          'personnel.approve',
          'personnel.export',
        ],
        'organization': {
          'modules': {
            'personnel': {'enabled': true, 'visible': true},
          },
        },
      };
    if (path == '/api/me') return {'id': 'a' * 32};
    if (path == '/api/business/employees') return [employee];
    if (path.startsWith('/api/business/payroll/profiles?'))
      return {
        'employee_id': id,
        'items': [copy(f['run']['source']['profile'])],
      };
    if (path.startsWith('/api/business/payroll/runs?'))
      return {
        'employee_id': id,
        'items': accepted ? [copy(f['run'])] : [],
      };
    if (path.startsWith('/api/business/personnel/files?'))
      return {'employee_id': id, 'items': f['sources']['files']};
    if (path.startsWith('/api/business/personnel/payroll-preparations?'))
      return {
        'employee_id': id,
        'items': [copy(f['run']['source']['preparation'])],
      };
    if (path == '/api/business/payroll/rules')
      return {
        'rules': {'version': 'synthetic verified fixture'},
      };
    if (path.startsWith('/api/business/payroll/one-off-cases/sources?'))
      return {
        ...copy(f['sources']),
        'one_off_cases': [copy(f['saved'])],
      };
    if (path == '/api/business/payroll/preview') {
      previews++;
      expect(body, f['run_input']);
      return copy(f['run_preview']);
    }
    if (path == '/api/business/payroll/runs') {
      commands.add(copy(body));
      expect(
        copy(body)..remove('request_id'),
        copy(f['run_command'])..remove('request_id'),
      );
      accepted = true;
      if (lose) {
        lose = false;
        throw const ApiException(0, 'Synthetic accepted run response lost');
      }
      return copy(f['run']);
    }
    throw StateError('Unexpected $path');
  }
}

Future<void> tapVisible(WidgetTester tester, Finder target) async {
  if (target.evaluate().isEmpty) {
    final scroll = tester.state<ScrollableState>(find.byType(Scrollable).first);
    scroll.position.jumpTo(scroll.position.minScrollExtent);
    await tester.pumpAndSettle();
  }
  await tester.scrollUntilVisible(
    target,
    400,
    scrollable: find.byType(Scrollable).first,
    maxScrolls: 100,
  );
  await tester.ensureVisible(target);
  await tester.pumpAndSettle();
  await tester.ensureVisible(target);
  await tester.pumpAndSettle();
  await tester.tap(target);
  await tester.pumpAndSettle();
}

void main() {
  for (final key in ['correction', 'paid_v5_upgrade']) {
    test(
      'actual $key keeps original run, full delta and existing paid part',
      () {
        final section = copy(f[key]);
        final previous = copy(
          key == 'correction' ? f['run'] : section['original_run'],
        );
        payrollPreview(section['run_preview'], copy(section['run_input']));
        payrollReceiptValidator(
          copy(section['run_command']),
          preview: copy(section['run_preview']),
          previous: previous,
        )(section['run']);
        expect(section['run']['id'], previous['id']);
        expect(section['run']['previous_hash'], previous['content_hash']);
        expect(
          section['run']['delta']['payout_minor'],
          section['run']['calculation']['payout_minor'] -
              previous['calculation']['payout_minor'],
        );
        expect(section['run']['delta']['net_deductions_minor'], 0);
        payrollAccountRecord(
          section['payment'],
          section['run']['employee_id'],
          kind: 'payment',
        );
        final original = key == 'correction'
            ? f['payment']
            : section['original_payment'];
        expect(
          section['payment']['details']['payments'][0],
          original['details']['payments'][0],
        );
        expect(
          section['payment']['details']['payments'][1]['amount_minor'],
          section['run']['delta']['payout_minor'],
        );
        final missing = copy(section['run']);
        (missing['delta'] as Map).remove('payout_minor');
        expect(
          () => payrollReceiptValidator(
            copy(section['run_command']),
            preview: copy(section['run_preview']),
            previous: previous,
          )(missing),
          throwsA(isA<ApiException>()),
        );
      },
    );
  }
  test('actual Source4 general adapters retain running travel, bonus and deductions', () async {
    expect(payrollOneOffCaseRunInput(copy(f['saved'])), f['run_input']);
    expect(
      payrollCalculation(f['run']['calculation'])['scope'],
      'regular_standard_oneoff',
    );
    payrollPreview(f['run_preview'], copy(f['run_input']));
    payrollReceiptValidator(
      copy(f['run_command']),
      preview: copy(f['run_preview']),
    )(f['run']);
    await payrollExportAttachment(
      copy(f['run']),
      Uint8List.fromList(utf8.encode(jsonEncode(f['run']))),
      'json',
    );
    final c = f['run']['calculation'];
    expect(c['period_details']['travel']['flat_taxable_payroll_minor'], 400);
    expect(c['net_deductions_minor'], 109);
    expect(c['payout_minor'], c['net_minor'] - 109);
  });
  test('actual Source4 source substitution and money replacement fail closed', () {
    for (final change in <void Function(Map<String, dynamic>)>[
      (v) => v['source']['employee_id'] = 'f' * 32,
      (v) => v['source']['calculation_case']['id'] = 'f' * 32,
      (v) =>
          v['source']['one_off_case']['details']['one_off_earning_ref']['id'] =
              'f' * 32,
      (v) => v['source']['input']['source_schema_version'] = 3,
      (v) => v['calculation']['net_deductions_minor'] = 0,
    ]) {
      final bad = copy(f['run_preview']);
      change(bad);
      expect(
        () => payrollPreview(bad, copy(f['run_input'])),
        throwsA(isA<ApiException>()),
      );
    }
  });
  test(
    'actual Source4 accepted receipt remains frozen after local changes',
    () {
      final command = copy(f['run_command']), preview = copy(f['run_preview']);
      final validate = payrollReceiptValidator(command, preview: preview);
      command['employee_id'] = 'f' * 32;
      preview['calculation']['net_minor']++;
      validate(f['run']);
      final bad = copy(f['run']);
      bad['source']['one_off_case']['source_hash'] = 'f' * 64;
      expect(() => validate(bad), throwsA(isA<ApiException>()));
    },
  );
  test('actual Source4 account and yearly ledger require original amount and receipt day', () async {
    payrollAccountRecord(f['payment'], id, kind: 'payment');
    expect(payrollAccountNoPaymentDue(f['run']), false);
    await payrollLedgerSnapshot(f['ledger'], id, 2026);
    for (final change in <void Function(Map<String, dynamic>)>[
      (v) => v['details']['payments'][0]['paid_on'] = '2026-11-01',
      (v) => v['details']['payments'][0]['amount_minor']++,
      (v) => v['details']['payments'] = [],
      (v) => v['sources']['run']['calculation']['net_deductions_minor'] = 0,
    ]) {
      final bad = copy(f['payment']);
      change(bad);
      expect(
        () => payrollAccountRecord(bad, id, kind: 'payment'),
        throwsA(isA<ApiException>()),
      );
    }
  });
  testWidgets(
    'productive native entry opens the actual case and finalizes its Source4 run after exact lost response retry',
    (tester) async {
      final api = OneOffRunApi()..lose = true;
      final active = BusinessSession(api: api);
      await active.load();
      await tester.pumpWidget(
        MaterialApp(
          home: BusinessPayrollPage(session: active, employee: employee),
        ),
      );
      await tester.pumpAndSettle();
      await tapVisible(
        tester,
        find.text('Einmalbezugsfälle aus Jahresquellen öffnen'),
      );
      await tapVisible(tester, find.text('Einmalbezugsmonat wählen'));
      await tester.enterText(find.byType(TextField).first, '2026-10');
      await tapVisible(tester, find.text('Monat öffnen'));
      await tapVisible(
        tester,
        find.text('Einmalbezugsfall 2026-10 · Fassung 1'),
      );
      await tapVisible(
        tester,
        find.text('Lohn mit diesem Einmalbezugsfall berechnen'),
      );
      expect(api.previews, 1);
      await tester.scrollUntilVisible(
        find.text('Unverbindliche Berechnungsvorschau'),
        300,
        scrollable: find.byType(Scrollable).first,
        maxScrolls: 100,
      );
      await tester.pumpAndSettle();
      expect(find.text('Unverbindliche Berechnungsvorschau'), findsOneWidget);
      await tapVisible(tester, find.text('Eingaben erneut prüfen'));
      expect(api.previews, 2);
      expect(
        find.text('Geprüftes Brutto aus Vereinbarung und Monatsquellen (€)'),
        findsNothing,
      );
      final confirmation = find.text(
        'Ich bestätige ausschließlich diesen geprüften Umfang: Regulärer Gesamtlohn mit belegtem Einmalbezug · PAP 2026',
      );
      await tapVisible(tester, confirmation);
      await tapVisible(
        tester,
        find.text('Geprüften Berechnungsumfang festhalten'),
      );
      expect(api.commands.length, 1);
      expect(active.pending('payroll-run-$id'), true);
      await tapVisible(
        tester,
        find.text('Ursprünglichen Auftrag erneut senden'),
      );
      expect(api.commands.length, 2);
      expect(api.commands[0], api.commands[1]);
      expect(active.pending('payroll-run-$id'), false);
      expect(find.text('Unverbindliche Berechnungsvorschau'), findsNothing);
      await tester.pumpWidget(const SizedBox());
      active.dispose();
    },
  );
}

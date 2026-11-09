import 'dart:convert';
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:flutter/material.dart';
import 'package:smartplan_office/api.dart';
import 'package:smartplan_office/business_payroll.dart';
import 'package:smartplan_office/business_payroll_facts.dart';
import 'package:smartplan_office/business_payroll_statements.dart';
import 'package:smartplan_office/business_session.dart';

import 'business_payroll_facts_test.dart' show FactsApi;

final f = jsonDecode(
  File('test/fixtures/payroll_factor_periods_2026_workflow.json')
      .readAsStringSync(),
) as Map<String, dynamic>;
Map<String, dynamic> copy(dynamic value) =>
    Map<String, dynamic>.from(jsonDecode(jsonEncode(value)) as Map);

class FactorPeriodApi extends FactsApi {
  @override
  Future<dynamic> call(String path, [Map<String, dynamic>? body]) async {
    if (path.startsWith('/api/business/payroll/facts/sources?'))
      return {
        ...copy(f['facts_sources']),
        'can_write': write,
        'can_approve': approve,
        'writes_enabled': !paused,
      };
    if (path.startsWith(
      '/api/business/payroll/facts/${f['period_case']['id']}',
    ))
      return path.endsWith('/history')
          ? {
              'employee_id': f['employee']['id'],
              'items': [copy(f['period_case'])],
            }
          : copy(f['period_case']);
    return super.call(path, body);
  }
}

void main() {
  for (final width in [390.0, 1200.0])
    testWidgets(
      'native factor-period plan opens its exact source and clears on revocation at $width',
      (tester) async {
        tester.view.physicalSize = Size(width, 844);
        tester.view.devicePixelRatio = 1;
        addTearDown(tester.view.resetPhysicalSize);
        addTearDown(tester.view.resetDevicePixelRatio);
        final api = FactorPeriodApi(), session = BusinessSession(api: api);
        Map<String, dynamic>? chosen;
        await session.load();
        await tester.pumpWidget(
          MaterialApp(
            home: BusinessPayrollFactsPage(
              session: session,
              employee: copy(f['employee']),
              onOriginal: (_) async {},
              onCalculate: (value) async {
                chosen = value;
              },
            ),
          ),
        );
        await tester.pumpAndSettle();
        final row = find.text('2026-10 · Fassung 1');
        await tester.scrollUntilVisible(
          row,
          300,
          scrollable: find.byType(Scrollable).first,
        );
        await tester.pumpAndSettle();
        await tester.ensureVisible(row);
        await tester.pumpAndSettle();
        expect(row.hitTestable(),findsOneWidget);
        await tester.tap(row);
        await tester.pumpAndSettle();
        await tester.scrollUntilVisible(
          find.text('0,753'),
          -250,
          scrollable: find.byType(Scrollable).first,
        );
        expect(find.text('0,753'), findsOneWidget);
        final calculate = find.text('Lohn aus diesem Fall berechnen');
        await tester.scrollUntilVisible(
          calculate,
          250,
          scrollable: find.byType(Scrollable).first,
        );
        await tester.pumpAndSettle();
        await tester.ensureVisible(calculate);
        await tester.pumpAndSettle();
        await tester.tap(calculate);
        await tester.pumpAndSettle();
        expect(chosen?['id'], f['period_case']['id']);
        expect(chosen?['plan']['rule_version'], payrollFactorPeriodRule);
        expect(tester.takeException(), isNull);
        api.read = false;
        await session.load();
        await tester.pumpAndSettle();
        expect(find.text('0,753'), findsNothing);
        expect(find.text('Lohnzeitachsen nicht freigegeben'), findsOneWidget);
        await tester.pumpWidget(const SizedBox());
        session.dispose();
        api.dispose();
      },
    );
  test('actual factor period keeps actual days, source factor and complete amounts', () {
    expect(payrollFactRunInput(copy(f['period_case'])), f['inputs']);
    payrollPreview(copy(f['preview']), copy(f['inputs']));
    final c = payrollCalculation(f['run']['calculation']),
        p = payrollPeriodCalculation(c);
    expect(c['rule_version'], payrollFactorPeriodRule);
    expect(c['scope'], 'regular_standard_factor_period');
    expect(c['gross_minor'], 274194);
    expect(c['tax_parameters']['tax_factor'], '0.753');
    expect(p['tax_periods'][0]['tax_days'], 17);
    expect(p['social_periods'][0]['days'], 17);
    expect(p['tax_calculation']['inputs']['gross_remainder_minor'], 1);
  });
  test('actual correction retains source original and independently bound tax delta', () {
    payrollReceiptValidator(copy(f['command']), preview: copy(f['preview']))(
      f['run'],
    );
    payrollReceiptValidator(
      copy(f['corrected_command']),
      preview: copy(f['corrected_preview']),
      previous: copy(f['run']),
    )(f['corrected_run']);
    expect(
      f['corrected_run']['delta']['net_minor'],
      -f['corrected_run']['delta']['employee_tax_minor'],
    );
    final bad = copy(f['corrected_run']);
    bad['delta']['individual_wage_tax_minor']++;
    expect(
      () => payrollReceiptValidator(
        copy(f['corrected_command']),
        preview: copy(f['corrected_preview']),
        previous: copy(f['run']),
      )(bad),
      throwsA(isA<ApiException>()),
    );
  });
  test('own employee statement has actual period amounts without private source originals', () async {
    final statement = await payrollStatement(
      f['statement'],
      f['employee']['id'],
    );
    expect(statement['period_summary']['tax_periods'][0]['tax_days'], 17);
    expect(statement['calculation']['scope'], 'regular_standard_factor_period');
    expect(jsonEncode(statement), isNot(contains('verification_note')));
  });
  test('factor profile plan and source cannot be substituted', () {
    final changes = <void Function(Map<String, dynamic>)>[
      (p) => p['calculation']['tax_parameters']['tax_factor'] = '0.900',
      (p) => p['source']['profile']['profile']['tax_factor'] = '0.900',
      (p) => p['source']['period_case']['plan']['rule_version'] =
          'de_2026_periods_pap_v4',
      (p) =>
          p['calculation']['period_details']['factor_parameters']['profile_ref']['id'] =
              'f' * 32,
    ];
    for (final change in changes) {
      final bad = copy(f['preview']);
      change(bad);
      expect(
        () => payrollPreview(bad, copy(f['inputs'])),
        throwsA(isA<ApiException>()),
      );
    }
  });
  test('daily tax components and legacy substitution cannot claim a completed calculation', () {
    final changes = <void Function(Map<String, dynamic>)>[
      (p) => p['period_details']['tax_calculation']['component']['LSTLZZ']++,
      (p) => p['period_details']['tax_calculation']['factor'] = '0.900',
      (p) => p['period_details']['tax_calculation']['inputs']['tax_days']++,
      (p) => p['tax_parameters']['church_assessment_minor']++,
      (p) => p['rule_version'] = 'de_2026_periods_pap_v4',
      (p) => p['period_details']['tax_periods'][0]['tax_days'] = 30,
      (p) => p['pap_version'] = 'old-version',
    ];
    for (final change in changes) {
      final bad = copy(f['run']['calculation']);
      change(bad);
      expect(() => payrollCalculation(bad), throwsA(isA<ApiException>()));
    }
  });
}

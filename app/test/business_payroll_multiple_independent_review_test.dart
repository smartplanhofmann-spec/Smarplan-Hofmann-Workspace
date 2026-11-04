import 'dart:convert';
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:flutter/material.dart';
import 'package:smartplan_office/api.dart';
import 'package:smartplan_office/business_session.dart';
import 'package:smartplan_office/business_widgets.dart';
import 'package:smartplan_office/business_payroll_multiple_cases.dart';
import 'package:smartplan_office/business_payroll_accounts.dart';

Map<String, dynamic> clone(dynamic value) =>
    Map<String, dynamic>.from(jsonDecode(jsonEncode(value)) as Map);
final fixture = clone(
  jsonDecode(
    File('test/fixtures/payroll_multiple_runs.json').readAsStringSync(),
  ),
);

class IndependentMultipleApi extends OfficeApi {
  IndependentMultipleApi() : super(apiVersion: 'v1') {
    token = 'synthetic-independent-native-review';
  }
  @override
  Future<dynamic> call(String path, [Map<String, dynamic>? body]) async {
    if (path.startsWith('/api/business/capabilities'))
      return {
        'compatibility_mode': 'business',
        'generation': 1,
        'storage_version': 10,
        'readonly': false,
        'features': ['payroll_multiple_cases'],
        'capabilities': ['business_payroll_multiple_cases'],
        'permissions': ['personnel.read', 'personnel.approve'],
        'organization': {
          'modules': {
            'personnel': {'enabled': true, 'visible': true},
          },
        },
      };
    if (path == '/api/me') return {'id': 'a' * 32};
    if (path.contains('/multiple-one-off-cases/sources?'))
      return {
        ...clone(fixture['sources']),
        'multiple_one_off_cases': [clone(fixture['saved'])],
      };
    throw StateError(path);
  }
}

Future<void> pressReview(WidgetTester tester, String label) async {
  final finder = find.text(label);
  if (finder.evaluate().isEmpty)
    await tester.scrollUntilVisible(
      finder,
      250,
      scrollable: find.byType(Scrollable).first,
    );
  await tester.ensureVisible(finder.last);
  await tester.pumpAndSettle();
  await tester.tap(finder.last);
  await tester.pumpAndSettle();
}

void main() {
  test('independent actual Source5 accepted records retain both exact settlement plans', () async {
    for (final section in [fixture, fixture['paid_v5_upgrade']]) {
      final run = clone(section['run']), payment = clone(section['payment']);
      payrollMultipleCaseRecord(
        run['source']['multiple_one_off_case'],
        run['employee_id'],
      );
      payrollAccountRecord(payment, run['employee_id']);
      expect(
        await payrollMultiplePaymentPlan(
          clone(payment['details']),
          run,
          prior: section['original_payment'] == null
              ? null
              : clone(section['original_payment']),
        ),
        payment['sources']['single_payment_plan'],
      );
    }
  });
  for (final mode in ['missing_run', 'downgraded_version', 'missing_version']) {
    test(
      'independent Source5 payment cannot bypass its source contract via $mode',
      () {
        final bad = clone(fixture['payment']);
        if (mode == 'missing_run') {
          (bad['sources'] as Map).remove('run');
        }
        if (mode == 'downgraded_version') {
          bad['sources']['run']['source']['source_schema_version'] = 3;
        }
        if (mode == 'missing_version') {
          (bad['sources']['run']['source'] as Map).remove(
            'source_schema_version',
          );
        }
        expect(
          () => payrollAccountRecord(bad, bad['employee_id']),
          throwsA(anything),
        );
      },
    );
  }
  final alterations = <String, void Function(Map<String, dynamic>)>{
    'component identity': (v) =>
        v['details']['components'][0]['component_key'] = 'f' * 32,
    'event document original': (v) =>
        v['details']['components'][0]['planned_receipts'][0]['document_refs'][0]['content_hash'] =
            'f' * 64,
    'complete-month original': (v) =>
        v['details']['completeness']['evidence_ref']['content_hash'] = 'f' * 64,
    'full annual source binding': (v) =>
        v['sources']['calculation_source']['current_annual_basis']['content_hash'] =
            'f' * 64,
    'tax source receipt day': (v) =>
        v['sources']['calculation_source']['annual_tax_forecasts'][0]['annual_tax_forecast']['details']['receipt_date'] =
            '2026-10-30',
    'previous year decision': (v) => v['details']['previous_annual_basis_ref'] =
        clone(v['details']['current_annual_basis_ref']),
    'component original claim': (v) =>
        v['plan']['multiple_one_off_details']['components'][0]['earning_ref']['content_hash'] =
            'f' * 64,
  };
  for (final entry in alterations.entries) {
    test('independent Source5 rejects replacement of ${entry.key}', () {
      final bad = clone(fixture['saved']);
      entry.value(bad);
      expect(
        () => payrollMultipleCaseRecord(bad, bad['employee_id']),
        throwsA(anything),
      );
    });
  }
  test('independent original running settlement cannot be replaced by a same-id different accepted revision', () async {
    final section = fixture['paid_v5_upgrade'],
        prior = clone(section['original_payment']);
    prior['revision']++;
    await expectLater(
      payrollMultiplePaymentPlan(
        clone(section['payment']['details']),
        clone(section['run']),
        prior: prior,
      ),
      throwsA(anything),
    );
  });
  test(
    'independent changed original prefix rejects before a payment command',
    () async {
      final s = fixture['paid_v5_upgrade'];
      for (final mutate in <void Function(Map<String, dynamic>)>[
        (v) => v['payments'][0]['payment_reference'] = 'Other original',
        (v) => v['payments'][0]['paid_on'] = '2026-10-29',
      ]) {
        final details = clone(s['payment']['details']);
        mutate(details);
        await expectLater(
          payrollMultiplePaymentPlan(
            details,
            clone(s['run']),
            prior: clone(s['original_payment']),
          ),
          throwsA(anything),
        );
      }
    },
  );
  testWidgets(
    'independent Source5 page unmount closes private editor on retained navigator',
    (tester) async {
      final api = IndependentMultipleApi();
      final session = BusinessSession(api: api);
      final show = ValueNotifier(true);
      try {
        await session.load();
        await tester.pumpWidget(
          MaterialApp(
            home: ValueListenableBuilder<bool>(
              valueListenable: show,
              builder: (context, visible, child) => visible
                  ? BusinessPayrollMultipleCasesPage(
                      session: session,
                      employee: clone(fixture['sources']['employee']),
                      initialMonth: '2026-10',
                      onOriginal: (_) async {},
                      onCalculate: (_) async {},
                    )
                  : const Scaffold(body: Text('Neutral retained navigator')),
            ),
          ),
        );
        await tester.pumpAndSettle();
        await pressReview(tester, 'Monatsgruppe 2026-10 · Fassung 1');
        await pressReview(tester, 'Monatsgruppe berichtigen');
        expect(find.byType(BusinessEditor), findsOneWidget);
        expect(
          find.text(fixture['saved']['details']['verification_note']),
          findsWidgets,
        );
        show.value = false;
        await tester.pumpAndSettle();
        expect(find.byType(BusinessPayrollMultipleCasesPage), findsNothing);
        expect(find.byType(BusinessEditor), findsNothing);
        expect(
          find.text(fixture['saved']['details']['verification_note']),
          findsNothing,
        );
        expect(tester.takeException(), isNull);
      } finally {
        await tester.pumpWidget(const SizedBox.shrink());
        show.dispose();
        session.dispose();
        api.dispose();
      }
    },
  );

  testWidgets(
    'independent Source5 allowed session replacement closes original private editor',
    (tester) async {
      final a = IndependentMultipleApi(), b = IndependentMultipleApi();
      final first = BusinessSession(api: a), second = BusinessSession(api: b);
      final selected = ValueNotifier(first);
      try {
        await first.load();
        await second.load();
        expect(first.generation, second.generation);
        await tester.pumpWidget(
          MaterialApp(
            home: ValueListenableBuilder<BusinessSession>(
              valueListenable: selected,
              builder: (context, session, child) =>
                  BusinessPayrollMultipleCasesPage(
                    session: session,
                    employee: clone(fixture['sources']['employee']),
                    initialMonth: '2026-10',
                    onOriginal: (_) async {},
                    onCalculate: (_) async {},
                  ),
            ),
          ),
        );
        await tester.pumpAndSettle();
        await pressReview(tester, 'Monatsgruppe 2026-10 · Fassung 1');
        await pressReview(tester, 'Monatsgruppe berichtigen');
        expect(find.byType(BusinessEditor), findsOneWidget);
        selected.value = second;
        await tester.pumpAndSettle();
        expect(find.byType(BusinessEditor), findsNothing);
        expect(tester.takeException(), isNull);
      } finally {
        await tester.pumpWidget(const SizedBox.shrink());
        selected.dispose();
        first.dispose();
        second.dispose();
        a.dispose();
        b.dispose();
      }
    },
  );
}

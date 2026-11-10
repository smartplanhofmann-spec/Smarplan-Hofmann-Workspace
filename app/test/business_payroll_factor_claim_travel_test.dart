import 'dart:convert';
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:smartplan_office/api.dart';
import 'package:smartplan_office/business_payroll.dart' as payroll;
import 'package:smartplan_office/business_session.dart'
    show businessMap, businessItems;
import 'package:smartplan_office/business_payroll_factor_claim_travel.dart';
import 'package:smartplan_office/business_payroll_calculation_case_contract.dart'
    as common;

dynamic copy(dynamic v) => jsonDecode(jsonEncode(v));

void main() {
  final fixture = businessMap(
    jsonDecode(
      File('test/fixtures/payroll_factor_claim_travel.json').readAsStringSync(),
    ),
  );
  final cases = businessItems(fixture['cases']);
  for (final c in cases) {
    test(
      'actual complete13 component/source/preview/run proofs: ${c['kind']}',
      () {
        payrollFactorClaimTravelPlan(businessMap(c['case']['plan']));
        payrollFactorClaimTravelBindings(
          businessMap(c['case']['sources']),
          businessMap(c['case']['details']),
          businessMap(c['case']['plan']),
        );
        payrollFactorClaimTravelCaseHashes(businessMap(c['case_preview']));
        payrollFactorClaimTravelCaseHashes(businessMap(c['case']));
        payrollFactorClaimTravelRunHashes(businessMap(c['run_preview']));
      },
    );
    test(
      'actual complete13 explicit originals and unused upgrade: ${c['kind']}',
      () {
        final body = payrollFactorClaimTravelInput(
          c['employee']['id'],
          businessMap(c['sources']),
          businessMap(c['values']),
          previous: c['previous'] == null ? null : businessMap(c['previous']),
        );
        final expected = businessMap(copy(c['case_command']))
          ..remove('request_id')
          ..remove('preview_hash');
        expect(body, expected);
      },
    );
    test(
      'actual13 generic command, original receipt and calculation routing: ${c['kind']}',
      () {
        final previous = c['previous'] == null
            ? null
            : businessMap(c['previous']);
        final body = common.payrollCalculationCaseInput(
          c['employee']['id'],
          businessMap(c['sources']),
          {
            ...businessMap(c['values']),
            'rule_version': payrollFactorClaimTravelRule,
          },
          previous: previous,
        );
        final expected = businessMap(copy(c['case_command']))
          ..remove('request_id')
          ..remove('preview_hash');
        expect(body, expected);
        common.payrollCalculationCasePreview(
          c['case_preview'],
          businessMap(c['case_command']),
        );
        common.payrollCalculationCaseValidator(
          businessMap(c['case_command']),
          previous: previous,
          preview: businessMap(c['case_preview']),
        )(c['case']);
        common.payrollCompositeCalculation(c['run']['calculation']);
        payroll.payrollPreview(c['run_preview'], businessMap(c['run_input']));
        payroll.payrollReceiptValidator(
          businessMap(c['run_command']),
          preview: businessMap(c['run_preview']),
        )(c['run']);
        common.payrollCompositeSource(
          c['run_preview'],
          businessMap(c['run_input']),
        );
      },
    );
  }
  test('hourly old plan stays zero; only a complete positive P4 component satisfies its exact review', () {
    final c = cases.firstWhere((c) => c['kind'] == 'hourly'),
        p = businessMap(c['case']['plan']);
    expect(c['period']['plan']['gross_minor'], 0);
    expect(c['period']['plan']['can_calculate'], false);
    expect(p['gross_minor'], 320000);
    expect(p['components']['paid_travel']['plan']['can_calculate'], false);
    expect(p['satisfied_travel_component_wage_reviews'], [
      'zero_earnings_requires_review',
    ]);
    expect(p['can_calculate'], true);
    final changed = businessMap(copy(p));
    changed['satisfied_travel_component_wage_reviews'] = [];
    expect(
      () => payrollFactorClaimTravelPlan(changed),
      throwsA(isA<ApiException>()),
    );
  });
  test('missing payment/P4 originals and implicit upgrades never generate commands', () {
    final c = cases.first;
    for (final field in [
      'entitlement_case_ids',
      'travel_settlement_ids',
      'travel_payment_ids',
    ]) {
      final v = businessMap(copy(c['values']));
      v[field] = [];
      expect(
        () => payrollFactorClaimTravelInput(
          c['employee']['id'],
          businessMap(c['sources']),
          v,
        ),
        throwsA(isA<ApiException>()),
      );
    }
    final u = cases.firstWhere((c) => c['previous'] != null),
        v = businessMap(copy(u['values']));
    v['confirm_unused_upgrade'] = false;
    expect(
      () => payrollFactorClaimTravelInput(
        u['employee']['id'],
        businessMap(u['sources']),
        v,
        previous: businessMap(u['previous']),
      ),
      throwsA(isA<ApiException>()),
    );
  });
  test('altered component gross, sum, projection, source and run fail independent canonical hashes', () {
    final c = cases.first;
    final changes = <void Function(Map<String, dynamic>)>[
      (v) => v['plan']['gross_minor']++,
      (v) => v['plan']['travel_paid_minor']++,
      (v) => v['plan']['components']['paid_travel']['projection'] =
          'GUESS_AN_UNBOUND_PAYMENT',
      (v) =>
          v['plan']['components']['claims']['source_snapshot_hash'] = '0' * 64,
      (v) =>
          v['sources']['travel_sources'][0]['payment_proof']['payments'][0]['amount_minor']++,
    ];
    for (final change in changes) {
      final v = businessMap(copy(c['case']));
      change(v);
      expect(
        () => payrollFactorClaimTravelCaseHashes(v),
        throwsA(isA<ApiException>()),
      );
    }
    final run = businessMap(copy(c['run_preview']));
    run['calculation']['payout_minor'] += 1400;
    expect(
      () => payrollFactorClaimTravelRunHashes(run),
      throwsA(isA<ApiException>()),
    );
  });
}

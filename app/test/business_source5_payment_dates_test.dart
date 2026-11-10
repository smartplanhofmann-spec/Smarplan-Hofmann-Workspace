import 'dart:convert';
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:smartplan_office/api.dart';
import 'package:smartplan_office/business_payroll_accounts.dart';
import 'package:smartplan_office/business_payroll_source5_transition.dart';

final fixture = jsonDecode(
  File('test/fixtures/source5_payment_dates.json').readAsStringSync(),
) as Map<String, dynamic>;
Map<String, dynamic> copy(dynamic value) =>
    Map<String, dynamic>.from(jsonDecode(jsonEncode(value)));

void main() {
  test('both actually accepted later-date payment originals match native hashes and preserve prior money', () async {
    final original = jsonEncode(fixture);
    for (final raw in fixture['cases']) {
      final s = copy(raw),
          run = copy(s['run']),
          prior = copy(s['prior_payment']),
          payment = copy(s['payment']);
      payrollAccountRecord(payment, payment['employee_id'], kind: 'payment');
      final plan = await payrollMultiplePaymentPlan(
        copy(s['details']),
        run,
        prior: prior,
      );
      expect(plan, payment['sources']['single_payment_plan']);
      expect(plan['schema_version'], 3);
      expect(plan['bonus_receipt_date'], '2026-10-31');
      expect(plan['settlement_date_basis'], 'actual_positive_transfer_2026');
      expect(plan['payments'].last['paid_on'], startsWith('2026-11-'));
      expect(
        (plan['payments'] as List)
            .take((prior['details']['payments'] as List).length)
            .toList(),
        prior['details']['payments'],
      );
    }
    expect(jsonEncode(fixture), original);
  });
  test('native proof rejects substituted actual days, original prefixes and date-basis contracts', () {
    for (final change in ['date', 'basis', 'version', 'prefix']) {
      final value = copy(fixture['cases'][1]['payment']),
          plan = value['sources']['single_payment_plan'];
      if (change == 'date') {
        value['details']['payments'].last['paid_on'] = '2026-10-31';
        plan['payments'].last['paid_on'] = '2026-10-31';
      }
      if (change == 'basis')
        plan['settlement_date_basis'] = 'new_gross_receipt';
      if (change == 'version') {
        value['details']['payment_source_schema_version'] = 2;
        plan['schema_version'] = 2;
      }
      if (change == 'prefix') value['details']['payments'][0]['amount_minor']++;
      plan['plan_hash'] = payrollPositiveHash(
        Map<String, dynamic>.from(plan)..remove('plan_hash'),
      );
      expect(
        () =>
            payrollAccountRecord(value, value['employee_id'], kind: 'payment'),
        throwsA(isA<ApiException>()),
      );
    }
  });
}

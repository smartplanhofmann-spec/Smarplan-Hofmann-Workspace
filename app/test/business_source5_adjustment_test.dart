import 'dart:convert';
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:smartplan_office/api.dart';
import 'package:smartplan_office/business_session.dart';
import 'package:smartplan_office/business_payroll_source5_adjustment.dart';
import 'package:smartplan_office/business_payroll_accounts.dart';

final fixtures = businessMap(
  jsonDecode(File('test/fixtures/source5_adjustments.json').readAsStringSync()),
);
Map<String, dynamic> copy(dynamic v) => businessMap(jsonDecode(jsonEncode(v)));

void main() {
  for (final raw in fixtures['cases']) {
    final fixture = businessMap(raw);
    group(fixture['label'] as String, () {
      test('native repeated adjustment reproduces complete accepted hashes and unchanged signed prefix', () {
        final before = jsonEncode(fixture),
            run = copy(fixture['run']),
            prior = copy(fixture['prior_payment']),
            details = copy(fixture['details']);
        payrollAdjustmentTransition(run);
        payrollAccountRecord(
          copy(fixture['payment']),
          fixture['employee']['id'],
          kind: 'payment',
        );
        final plan = payrollAdjustmentPaymentPlan(details, run, prior: prior);
        expect(plan, fixture['payment']['sources']['single_payment_plan']);
        expect(plan['schema_version'], 5);
        expect(
          plan['net_delta_minor'],
          fixture['run']['settlement_transition']['net_delta_minor'],
        );
        expect(
          (plan['payments'] as List)
              .take((prior['details']['payments'] as List).length)
              .toList(),
          prior['details']['payments'],
        );
        expect(jsonEncode(fixture), before);
      });
      test('productive native input builder requires adjustment capability and signed bonus portions', () {
        final d = fixture['details'];
        String ref(dynamic v) => '${v['id']}@${v['revision']}';
        String money(dynamic n) => (n / 100).toStringAsFixed(2);
        final values = <String, dynamic>{
          'run_ref': ref(fixture['run']),
          'identity_ref': '${d['identity_id']}@${d['identity_revision']}',
          'prior_payment_ref': ref(fixture['prior_payment']),
          'standard_case_confirmed': true,
          'tax_free_payments_minor': '0.00',
          'tax_free_basis': '',
        };
        for (var i = 0; i < (d['payments'] as List).length; i++) {
          final p = d['payments'][i], a = d['settlement_allocations'][i];
          values.addAll({
            'paid_on_$i': p['paid_on'],
            'amount_$i': money(p['amount_minor']),
            'reference_$i': p['payment_reference'],
            'running_$i': money(a['running_minor']),
            'bonus_$i': money(
              (a['one_off_allocations'] as List).fold<int>(
                0,
                (n, v) => n + (v['net_minor'] as int),
              ),
            ),
          });
        }
        final sources = <String, List<Map<String, dynamic>>>{
          'runs': [copy(fixture['run'])],
          'identities': [copy(fixture['payment']['sources']['identity'])],
          'payments': [copy(fixture['prior_payment'])],
        };
        expect(
          () => payrollAccountDetails(
            'payment',
            values,
            sources,
            count: (d['payments'] as List).length,
          ),
          throwsA(isA<ApiException>()),
        );
        expect(
          payrollAccountDetails(
            'payment',
            values,
            sources,
            count: (d['payments'] as List).length,
            adjustments: true,
          ),
          d,
        );
      });
      test('native mixed adjustment rejects changed old money, positive payment, earlier date and old source version', () {
        for (final change in ['prefix', 'positive', 'early', 'version']) {
          final details = copy(fixture['details']);
          if (change == 'prefix') details['payments'][0]['amount_minor']++;
          if (change == 'positive') {
            if (fixture['label'] == 'zero') {
              details['payments'].add({
                'paid_on': '2026-11-03',
                'amount_minor': 0,
                'payment_reference': 'FAKE-ZERO',
              });
              details['settlement_allocations'].add({
                'payment_index': (details['payments'] as List).length - 1,
                'running_minor': 0,
                'one_off_allocations': [],
              });
            } else {
              details['payments'].last['amount_minor'] *= -1;
              details['settlement_allocations']
                      .last['one_off_allocations'][0]['net_minor'] *=
                  -1;
            }
          }
          if (change == 'early')
            details['payments'].last['paid_on'] = '2026-10-30';
          if (change == 'version') details['payment_source_schema_version'] = 4;
          expect(
            () => payrollAdjustmentPaymentPlan(
              details,
              copy(fixture['run']),
              prior: copy(fixture['prior_payment']),
            ),
            throwsA(isA<ApiException>()),
          );
        }
      });
    });
  }
}

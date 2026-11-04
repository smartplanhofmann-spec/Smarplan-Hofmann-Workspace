import 'dart:convert';
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:smartplan_office/api.dart';
import 'package:smartplan_office/business_payroll_accounts.dart';
import 'package:smartplan_office/business_payroll_cash.dart';

final f = jsonDecode(
  File('test/fixtures/payroll_multiple_runs.json').readAsStringSync(),
) as Map<String, dynamic>;
Map<String, dynamic> copy(dynamic v) =>
    Map<String, dynamic>.from(jsonDecode(jsonEncode(v)) as Map);
String money(dynamic v) => (v / 100).toStringAsFixed(2);
Map<String, dynamic> input(dynamic section) {
  final d = section['payment']['details'];
  return {
    'run_ref': '${d['run_id']}@${d['run_revision']}',
    'identity_ref': '${d['identity_id']}@${d['identity_revision']}',
    'standard_case_confirmed': true,
    'tax_free_payments_minor': money(d['tax_free_payments_minor']),
    'tax_free_basis': d['tax_free_basis'],
    'prior_payment_ref': d['prior_payment_ref'] == null
        ? 'none'
        : '${d['prior_payment_ref']['id']}@${d['prior_payment_ref']['revision']}',
    for (var i = 0; i < (d['payments'] as List).length; i++) ...{
      'paid_on_$i': d['payments'][i]['paid_on'],
      'amount_$i': money(d['payments'][i]['amount_minor']),
      'reference_$i': d['payments'][i]['payment_reference'],
      'running_$i': money(d['settlement_allocations'][i]['running_minor']),
      'bonus_$i': money(
        (d['settlement_allocations'][i]['one_off_allocations'] as List)
            .fold<int>(0, (n, p) => n + (p['net_minor'] as int)),
      ),
    },
  };
}

Map<String, List<Map<String, dynamic>>> sources(dynamic s) => {
  'runs': [copy(s['run'])],
  'identities': [copy(s['payment']['sources']['identity'])],
  'payments': [if (s['original_payment'] != null) copy(s['original_payment'])],
};
void main() {
  for (final key in ['initial', 'paid_v5_upgrade'])
    test(
      'actual $key separated dates retain canonical payment, hash and cash originals',
      () async {
        final section = key == 'initial' ? f : f[key],
            payment = section['payment'],
            id = section['run']['employee_id'] as String;
        payrollAccountRecord(payment, id, kind: 'payment');
        final details = payrollAccountDetails(
          'payment',
          input(section),
          sources(section),
          count: payment['details']['payments'].length,
        );
        expect(details, payment['details']);
        final plan = await payrollMultiplePaymentPlan(
          details,
          copy(section['run']),
          prior: section['original_payment'] == null
              ? null
              : copy(section['original_payment']),
        );
        expect(plan, payment['sources']['single_payment_plan']);
        payrollAccountReceiptValidator(
          copy(section['payment_command']),
          copy(payment['source_file']),
          sourceEvidence: {
            'run': section['run'],
            'identity': payment['sources']['identity'],
            'single_payment_plan': plan,
          },
        )(payment);
        payrollCashPublic(section['net_batch']['public_source']);
        if (key == 'paid_v5_upgrade') {
          expect(plan['preserved_prior_payment_indexes'], [0]);
          expect(plan['new_payment_indexes'], [1]);
          expect(
            details['payments'][0],
            section['original_payment']['details']['payments'][0],
          );
          expect(
            (section['net_batch']['public_source']['cash_movements'] as List)
                .length,
            1,
          );
        }
      },
    );
  test('changed bonus day, crossed event, missing running amount and fabricated allocation are refused', () {
    final changes = <void Function(Map<String, dynamic>)>[
      (v) => v['details']['payment_source_schema_version'] = 1.0,
      (v) => v['details']['settlement_allocations'][0]['payment_index'] = 0.0,
      (v) => v['details']['payments'][1]['paid_on'] = '2026-10-30',
      (v) =>
          v['details']['settlement_allocations'][1]['one_off_allocations'][0]['event_key'] =
              'f' * 32,
      (v) => v['details']['settlement_allocations'][0]['running_minor']--,
      (v) => v['sources']['single_payment_plan']['new_payment_indexes'] = [
        0,
        1,
        2,
      ],
      (v) =>
          v['sources']['single_payment_plan']['actual_payment_created'] = true,
    ];
    for (final change in changes) {
      final bad = copy(f['payment']);
      change(bad);
      expect(
        () => payrollAccountRecord(bad, f['run']['employee_id']),
        throwsA(isA<ApiException>()),
      );
    }
  });
  test(
    'paid v5 original prefix may never be relabelled or omitted by UI builder',
    () {
      final section = f['paid_v5_upgrade'];
      for (final changes in [
        {'reference_0': 'renamed transfer'},
        {'paid_on_0': '2026-10-29'},
        {'running_0': '0.00'},
        {'prior_payment_ref': ''},
      ]) {
        expect(
          () => payrollAccountDetails(
            'payment',
            {...input(section), ...changes},
            sources(section),
            count: 2,
          ),
          throwsA(anything),
        );
      }
    },
  );
  test('receipt validator seals actual prior-source projection and all original payments', () async {
    final s = f['paid_v5_upgrade'],
        body = copy(s['payment_command']),
        proof = copy(s['payment']['sources']);
    final validate = payrollAccountReceiptValidator(
      body,
      copy(s['payment']['source_file']),
      sourceEvidence: proof,
    );
    body['details']['payments'][0]['payment_reference'] = 'later';
    proof['single_payment_plan']['plan_hash'] = 'f' * 64;
    validate(s['payment']);
    final bad = copy(s['payment']);
    bad['sources']['single_payment_plan']['prior_settlement_refs']['payment']['content_hash'] =
        'f' * 64;
    expect(() => validate(bad), throwsA(isA<ApiException>()));
  });
}

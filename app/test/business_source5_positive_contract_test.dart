import 'dart:convert';
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:smartplan_office/api.dart';
import 'package:smartplan_office/business_payroll.dart';
import 'package:smartplan_office/business_payroll_accounts.dart';
import 'package:smartplan_office/business_payroll_source5_transition.dart';

final fixture = jsonDecode(
  File('test/fixtures/source5_positive_corrections.json').readAsStringSync(),
) as Map<String, dynamic>;
Map<String, dynamic> copy(dynamic value) =>
    Map<String, dynamic>.from(jsonDecode(jsonEncode(value)) as Map);

void rehash(Map<String, dynamic> run) {
  final transition = run['settlement_transition'],
      observation = transition['remittance_observation'];
  observation['source_hash'] = payrollPositiveHash(
    {...copy(observation)}..remove('source_hash'),
  );
  transition['transition_hash'] = payrollPositiveHash(
    {...copy(transition)}..remove('transition_hash'),
  );
  run['preview_hash'] = payrollPositiveHash({
    'source': run['source'],
    'calculation': run['calculation'],
    'settlement_transition': transition,
  });
}

void main() {
  test('actual v1 and both positive corrected previews and receipts preserve all original bindings', () {
    for (final key in ['initial', 'correction', 'second_correction']) {
      final f = fixture[key],
          before = jsonEncode(f),
          input = copy(f['run_input']);
      expect(payrollPreview(copy(f['run_preview']), input), f['run_preview']);
      payrollReceiptValidator(
        copy(f['run_command']),
        preview: copy(f['run_preview']),
        previous: f['prior_run'] == null ? null : copy(f['prior_run']),
      )(copy(f['run']));
      expect(
        payrollAccountRecord(
          copy(f['payment']),
          f['run']['employee_id'],
          kind: 'payment',
        ),
        f['payment'],
      );
      expect(jsonEncode(f), before);
    }
    expect(
      fixture['initial']['run'].containsKey('settlement_transition'),
      false,
    );
    expect(
      fixture['initial']['run_input'].containsKey('settlement_review'),
      false,
    );
  });

  test('actual cumulative v2 plans preserve the complete paid prefix and exact positive new indexes', () async {
    for (final key in ['initial', 'correction', 'second_correction']) {
      final f = fixture[key],
          payment = copy(f['payment']),
          prior = f['prior_payment'];
      final plan = await payrollMultiplePaymentPlan(
        copy(payment['details']),
        copy(f['run']),
        prior: prior == null ? null : copy(prior),
      );
      expect(plan, payment['sources']['single_payment_plan']);
      payrollAccountReceiptValidator(
        copy(f['payment_command']),
        copy(payment['source_file']),
        sourceEvidence: {
          'run': f['run'],
          'identity': payment['sources']['identity'],
          'single_payment_plan': plan,
        },
      )(payment);
      if (prior != null) {
        final count = (prior['details']['payments'] as List).length;
        expect(
          (payment['details']['payments'] as List).take(count).toList(),
          prior['details']['payments'],
        );
        expect(
          (payment['details']['settlement_allocations'] as List)
              .take(count)
              .toList(),
          prior['details']['settlement_allocations'],
        );
        expect(
          plan['preserved_prior_payment_indexes'],
          List.generate(count, (i) => i),
        );
        expect(plan['new_payment_indexes'], [count]);
        expect(plan['actual_payment_created'], false);
        expect(plan['cash_import_created'], false);
        expect(plan['claim_consumption_created'], false);
      }
    }
  });

  test('even rehashed positive transitions reject unknown, incomplete, overpaid or substituted facts', () {
    for (final mutate in <void Function(Map<String, dynamic>)>[
      (r) => r['settlement_transition']['additional_net_minor']++,
      (r) => r['settlement_transition']['prior_payment_ref']['revision'] = 2,
      (r) => r['settlement_transition']['previous_run_ref']['id'] = 'f' * 32,
      (r) =>
          r['settlement_transition']['remittance_observation']['amounts']['employee_tax'] =
              r['calculation']['employee_tax_minor'] + 1,
      (r) {
        r['settlement_transition']['settlement_review']['payments_complete'] =
            false;
        r['source']['input']['settlement_review']['payments_complete'] = false;
      },
      (r) {
        r['settlement_transition']['settlement_review']['remittances_complete'] =
            false;
        r['source']['input']['settlement_review']['remittances_complete'] =
            false;
      },
      (r) {
        r['settlement_transition']['settlement_review']['evidence_ref']['revision'] =
            2;
        r['source']['input']['settlement_review']['evidence_ref']['revision'] =
            2;
      },
      (r) =>
          r['settlement_transition']['remittance_observation']['unknown_bank_data'] =
              'not permitted',
      (r) => r['source']['input'].remove('settlement_review'),
    ]) {
      final run = copy(fixture['correction']['run']);
      mutate(run);
      rehash(run);
      expect(
        () => payrollPositiveTransition(run),
        throwsA(isA<ApiException>()),
      );
    }
    final missing = copy(fixture['correction']['run_preview'])
      ..remove('settlement_transition');
    expect(
      () => payrollPreview(missing, copy(fixture['correction']['run_input'])),
      throwsA(isA<ApiException>()),
    );
    final missingHash = copy(fixture['correction']['run'])
      ..remove('preview_hash');
    expect(
      () => payrollPositiveTransition(missingHash),
      throwsA(isA<ApiException>()),
    );
  });

  test('v2 payment rejects changed originals, missing prior, negative transfers and foreign dates', () async {
    for (final key in ['correction', 'second_correction']) {
      final f = fixture[key],
          count = (f['prior_payment']['details']['payments'] as List).length;
      for (final mutate in <void Function(Map<String, dynamic>)>[
        (d) => d['prior_payment_ref']['content_hash'] = 'f' * 64,
        (d) =>
            d['payments'][0]['payment_reference'] = 'Substituted paid original',
        (d) => d['settlement_allocations'][0]['running_minor']++,
        (d) => d['payments'][count]['paid_on'] = '2026-11-01',
        (d) => d['payments'][count]['amount_minor'] = -1,
        (d) => d['payment_source_schema_version'] = 1,
      ]) {
        final details = copy(f['payment']['details']);
        mutate(details);
        await expectLater(
          payrollMultiplePaymentPlan(
            details,
            copy(f['run']),
            prior: copy(f['prior_payment']),
          ),
          throwsA(isA<ApiException>()),
        );
      }
      await expectLater(
        payrollMultiplePaymentPlan(
          copy(f['payment']['details']),
          copy(f['run']),
        ),
        throwsA(isA<ApiException>()),
      );
      final prior = copy(f['prior_payment']);
      prior['sources']['single_payment_plan']['plan_hash'] = 'f' * 64;
      await expectLater(
        payrollMultiplePaymentPlan(
          copy(f['payment']['details']),
          copy(f['run']),
          prior: prior,
        ),
        throwsA(isA<ApiException>()),
      );
    }
  });

  test('sealed run and payment receipts reject changed review or substituted transition', () {
    final f = fixture['correction'];
    final command = copy(f['run_command']);
    command['settlement_review']['evidence_ref']['content_hash'] = 'f' * 64;
    expect(
      () => payrollReceiptValidator(
        command,
        preview: copy(f['run_preview']),
        previous: copy(f['prior_run']),
      )(copy(f['run'])),
      throwsA(isA<ApiException>()),
    );
    final run = copy(f['run']);
    run['settlement_transition']['prior_plan_hash'] = 'f' * 64;
    rehash(run);
    expect(
      () => payrollReceiptValidator(
        copy(f['run_command']),
        preview: copy(f['run_preview']),
        previous: copy(f['prior_run']),
      )(run),
      throwsA(isA<ApiException>()),
    );
    final payment = copy(f['payment']);
    payment['sources']['single_payment_plan']['new_payment_indexes'] = [0];
    expect(
      () => payrollAccountRecord(
        payment,
        f['run']['employee_id'],
        kind: 'payment',
      ),
      throwsA(isA<ApiException>()),
    );
  });
}

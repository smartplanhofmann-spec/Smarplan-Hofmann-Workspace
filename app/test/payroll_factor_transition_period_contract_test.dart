import 'dart:convert';
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:cryptography/dart.dart';

import 'package:smartplan_office/api.dart';
import 'package:smartplan_office/business_payroll_calculation_case_contract.dart';
import 'package:smartplan_office/business_payroll.dart';
import 'package:smartplan_office/business_payroll_statements.dart';

Map<String, dynamic> copy(dynamic v) =>
    Map<String, dynamic>.from(jsonDecode(jsonEncode(v)) as Map);
dynamic order(dynamic v) => v is List
    ? v.map(order).toList()
    : v is Map
    ? {
        for (final key in v.keys.cast<String>().toList()..sort())
          key: order(v[key]),
      }
    : v;
String sha(dynamic v) => const DartSha256()
    .hashSync(utf8.encode(jsonEncode(order(v))))
    .bytes
    .map((b) => b.toRadixString(16).padLeft(2, '0'))
    .join();
final data = jsonDecode(
  File('test/fixtures/payroll_factor_transition_period.json')
      .readAsStringSync(),
) as Map<String, dynamic>;
final rows = (data['cases'] as List).map(copy).toList();
Map<String, dynamic> values(Map<String, dynamic> r) => {
  'month': '2026-10',
  'period_case_id': r['input']['details']['period_case_ref']['id'],
  for (final e in {
    'employment_terms_ids': 'employment_terms_refs',
    'profile_ids': 'profile_refs',
    'identity_ids': 'identity_refs',
  }.entries)
    e.key: (r['input']['details'][e.value] as List)
        .map((v) => v['id'])
        .toList(),
  'factor_transition_period_assessment': copy(
    r['input']['details']['factor_transition_period_assessment'],
  ),
  'source_file_ids': r['input']['source_file_ids'],
  'verification_note': r['input']['details']['verification_note'],
};

void main() {
  test('generic native case, original acknowledgements and full run readers use the explicit v16 contract', () {
    for (final r in rows) {
      final input = values(r)
        ..['rule_version'] = payrollFactorTransitionPeriodRule;
      final body = payrollCalculationCaseInput(
        r['employee']['id'],
        copy(r['sources']),
        input,
      );
      final expected = copy(r['case_command'])
        ..remove('request_id')
        ..remove('preview_hash');
      expect(body, expected);
      payrollCalculationCasePreview(r['case_preview'], body);
      payrollCalculationCaseValidator(
        copy(r['case_command']),
        preview: copy(r['case_preview']),
      )(r['case']);
      payrollPreview(r['run_preview'], copy(r['run_input']));
      payrollReceiptValidator(
        copy(r['run_command']),
        preview: copy(r['run_preview']),
      )(r['run']);
    }
  });

  test('untrusted preview hashes are checked before either new or historical factor case acceptance', () {
    final historical = copy(
      jsonDecode(
        File('test/fixtures/payroll_factor_transition.json').readAsStringSync(),
      ),
    );
    for (final entry in [
      {'preview': rows.first['case_preview'], 'body': rows.first['input']},
      {'preview': historical['case_preview'], 'body': historical['case_input']},
    ]) {
      final altered = copy(entry['preview'])..['preview_hash'] = 'f' * 64;
      expect(
        () => payrollCalculationCasePreview(altered, copy(entry['body'])),
        throwsA(isA<ApiException>()),
      );
    }
  });

  test('actual own statements accept only the new exact rule/scope pair and retain the private source boundary', () async {
    for (final r in rows) {
      final own = await payrollStatement(
        r['own']['statement'],
        r['employee']['id'],
      );
      expect(
        own['calculation']['net_minor'],
        r['run']['calculation']['net_minor'],
      );
      expect(
        jsonEncode(own),
        isNot(contains('factor_transition_period_assessment')),
      );
      final bad = copy(r['own']['statement']);
      bad['calculation']['scope'] = 'regular_transition_factor_month';
      await expectLater(
        payrollStatement(bad, r['employee']['id']),
        throwsA(isA<ApiException>()),
      );
    }
  });

  test('two actual private API originals and positive factor tax reproduce native complete hashes and exact input', () {
    expect(rows, hasLength(2));
    for (final r in rows) {
      expect(
        payrollFactorTransitionPeriodSelectable(
          r['case']['sources']['period_case'],
          '2026-10',
        ),
        isTrue,
      );
      expect(
        payrollFactorTransitionPeriodPlan(r['case']['plan']),
        r['case']['plan'],
      );
      payrollFactorTransitionPeriodBindings(
        copy(r['case']['sources']),
        copy(r['case']['details']),
        copy(r['case']['plan']),
      );
      payrollFactorTransitionPeriodCaseHashes(copy(r['case_preview']));
      payrollFactorTransitionPeriodCaseHashes(copy(r['case']));
      payrollFactorTransitionPeriodCalculation(r['run']['calculation']);
      payrollFactorTransitionPeriodRunHashes(copy(r['run_preview']));
      payrollFactorTransitionPeriodRunHashes(copy(r['run']));
      final expected = copy(r['case_command'])
        ..remove('request_id')
        ..remove('preview_hash');
      expect(
        payrollFactorTransitionPeriodInput(
          r['employee']['id'],
          copy(r['sources']),
          values(r),
        ),
        expected,
      );
    }
    expect(rows.first['run']['calculation']['net_minor'], 49565);
    expect(rows.last['run']['calculation']['individual_wage_tax_minor'], 3740);
    expect(rows.last['run']['calculation']['net_minor'], 84944);
  });

  test('self-consistent changed tax and replaced run proof cannot override the separately accepted complete case component', () {
    final v = copy(rows.last['run']),
        c = v['calculation'],
        t = c['factor_transition_period_components']['factor_tax'];
    t['component']['LSTLZZ'] += 1;
    t['totals']['LSTLZZ'] += 17;
    c['individual_wage_tax_minor'] += 17;
    c['employee_tax_minor'] += 17;
    c['net_minor'] -= 17;
    c['payout_minor'] -= 17;
    c['period_details']['tax_calculations'][0]['calculation'] = copy(t);
    v['preview_hash'] = sha({'source': v['source'], 'calculation': c});
    payrollFactorTransitionPeriodCalculation(c);
    expect(
      () => payrollFactorTransitionPeriodRunHashes(v),
      throwsA(isA<ApiException>()),
    );
  });

  test('foreign private evidence is rejected after recomputing the reported case hashes', () {
    final v = copy(rows.first['case']),
        id =
            v['sources']['factor_transition_period_assessment']['forecast_evidence_ref']['id'];
    (v['sources']['source_files'] as List).firstWhere(
      (f) => f['id'] == id,
    )['employee_id'] = 'f' * 32;
    v['source_hash'] = sha(v['sources']);
    v['plan']['source_snapshot_hash'] = v['source_hash'];
    final p = copy(v['plan'])
      ..remove('plan_hash')
      ..remove('can_confirm')
      ..remove('can_calculate');
    v['plan']['plan_hash'] = sha(p);
    v['preview_hash'] = sha({
      'source_snapshot': v['sources'],
      'plan': v['plan'],
    });
    expect(
      () => payrollFactorTransitionPeriodCaseHashes(v),
      throwsA(isA<ApiException>()),
    );
  });

  test('full months and old labels cannot be promoted into the new actual partial period', () {
    final v = copy(rows.first['case']), base = v['sources']['period_case'];
    base['plan']['tax_periods'][0]['lzz'] = 2;
    base['plan']['tax_periods'][0]['tax_days'] = 30;
    base['plan']['social_periods'][0]['full_month'] = true;
    expect(payrollFactorTransitionPeriodSelectable(base, '2026-10'), isFalse);
    final plan = copy(v['plan'])
      ..['rule_version'] = 'de_2026_factor_transition_month_v14'
      ..['source_contract_version'] = 6;
    expect(
      () => payrollFactorTransitionPeriodPlan(plan),
      throwsA(isA<ApiException>()),
    );
  });

  test('the native constructor never selects the first original or drops extra sources', () {
    final r = rows.first;
    for (final key in [
      'period_case_id',
      'employment_terms_ids',
      'profile_ids',
      'identity_ids',
    ]) {
      final input = values(r)..remove(key);
      expect(
        () => payrollFactorTransitionPeriodInput(
          r['employee']['id'],
          copy(r['sources']),
          input,
        ),
        throwsA(isA<ApiException>()),
      );
    }
    final input = values(r)..['travel_settlement_ids'] = ['a' * 32];
    expect(
      () => payrollFactorTransitionPeriodInput(
        r['employee']['id'],
        copy(r['sources']),
        input,
      ),
      throwsA(isA<ApiException>()),
    );
  });

  test('review types, unknown fields and unpaired Unicode are closed while multiline notes remain valid', () {
    final r = rows.first,
        review = copy(
          r['input']['details']['factor_transition_period_assessment'],
        );
    for (final change in [
      <String, dynamic>{'schema_version': true},
      {'contractual_30_days_confirmed': 1},
      {'unknown': true},
      {'verification_note': String.fromCharCode(0xd800)},
    ]) {
      expect(
        () => payrollFactorTransitionPeriodAssessment({
          ...review,
          ...change,
        }, r['employee']['id']),
        throwsA(isA<ApiException>()),
      );
    }
    final valid = {
      ...review,
      'verification_note': 'Beleg geprüft\nZweite Zeile ✓',
    };
    expect(
      payrollFactorTransitionPeriodAssessment(valid, r['employee']['id']),
      valid,
    );
  });

  test('a blocked calculation never carries apparently complete money or an altered daily remainder', () {
    final c = copy(rows.first['run']['calculation'])
      ..['scope'] = 'unsupported'
      ..['payroll_calculation_complete'] = false
      ..['social_contributions_available'] = false
      ..['blockers'] = [
        {'code': 'test', 'message': 'blocked'},
      ];
    expect(
      () => payrollFactorTransitionPeriodCalculation(c),
      throwsA(isA<ApiException>()),
    );
    final altered = copy(rows.last['run']['calculation']);
    altered['factor_transition_period_components']['factor_tax']['inputs']['gross_remainder_minor']++;
    expect(
      () => payrollFactorTransitionPeriodCalculation(altered),
      throwsA(isA<ApiException>()),
    );
  });
}

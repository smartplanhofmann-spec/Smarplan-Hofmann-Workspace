import 'dart:convert';
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:smartplan_office/api.dart';
import 'package:smartplan_office/business_payroll_oneoff_case_contract.dart';

final f = jsonDecode(
  File('../docs/fixtures/payroll-oneoff-cases-2026.json').readAsStringSync(),
) as Map<String, dynamic>;
Map<String, dynamic> copy(dynamic v) =>
    Map<String, dynamic>.from(jsonDecode(jsonEncode(v)) as Map);
Map<String, dynamic> clean(dynamic v) => copy(v)..remove('request_id');
Map<String, dynamic> values(Map<String, dynamic> c) => {
  'month': c['details']['month'],
  'source_file_ids': c['source_file_ids'],
  'verification_note': c['details']['verification_note'],
  'correction_reason': c['correction_reason'],
  for (final entry in (c['details'] as Map).entries)
    if ((entry.key as String).endsWith('_ref'))
      (entry.key as String).replaceFirst(RegExp(r'_ref$'), '_id'):
          entry.value?['id'],
};
void main() {
  final id = f['saved']['employee_id'] as String;
  test('actual oneoff choices preserve full canonical original command and preview', () {
    payrollOneOffCaseSources(f['sources'], id, '2026-10');
    final body = payrollOneOffCaseInput(
      id,
      copy(f['sources']),
      values(copy(f['command'])),
    );
    expect({
      ...body,
      'preview_hash': f['preview']['preview_hash'],
    }, clean(f['command']));
    payrollOneOffCasePreview(f['preview'], body);
    expect(
      payrollOneOffCaseValidator(
        clean(f['command']),
        preview: copy(f['preview']),
      )(f['saved']),
      f['saved'],
    );
  });
  test(
    'actual correction, void and historical original remain precisely bound',
    () {
      final body = payrollOneOffCaseInput(
        id,
        copy(f['sources']),
        values(copy(f['correction_command'])),
        previous: copy(f['saved']),
      );
      expect({
        ...body,
        'preview_hash': f['correction_preview']['preview_hash'],
      }, clean(f['correction_command']));
      payrollOneOffCasePreview(f['correction_preview'], body);
      payrollOneOffCaseValidator(
        clean(f['correction_command']),
        previous: copy(f['saved']),
        preview: copy(f['correction_preview']),
      )(f['corrected']);
      payrollOneOffCaseValidator(
        clean(f['void_command']),
        previous: copy(f['corrected']),
      )(f['voided']);
      for (final r in f['history']['items']) payrollOneOffCaseRecord(r, id);
      expect(f['voided']['revision'], 3);
      expect(f['history']['items'][0], f['saved']);
    },
  );
  test('original running net and bonus cannot be counted twice', () {
    final c = payrollOneOffCalculation(f['saved']['plan']),
        r = c['running_calculation'],
        d = c['one_off_details'];
    expect(
      c['net_minor'],
      r['net_minor'] +
          d['amount_minor'] -
          d['social']['employee_total_minor'] -
          d['tax']['STS'] -
          d['tax']['SOLZS'] -
          d['church_tax_minor'],
    );
    expect(c['net_deductions_minor'], r['net_deductions_minor']);
    for (final key in [
      'gross_minor',
      'net_minor',
      'payout_minor',
      'employee_tax_minor',
      'employer_total_excluding_accident_insurance_minor',
    ]) {
      final bad = copy(c);
      bad[key]++;
      expect(() => payrollOneOffCalculation(bad), throwsA(isA<ApiException>()));
    }
    final altered = copy(c);
    altered['period_details']['travel']['tax_free_external_minor']++;
    expect(
      () => payrollOneOffCalculation(altered),
      throwsA(isA<ApiException>()),
    );
  });
  test('preview refuses substituted claim, previous year, employee or original', () {
    final changes = <void Function(Map<String, dynamic>)>[
      (v) => v['source_snapshot']['employee']['revision']++,
      (v) => v['source_snapshot']['source_files'][0]['employee_id'] = 'f' * 32,
      (v) =>
          v['source_snapshot']['calculation_source']['one_off_earning']['id'] =
              'f' * 32,
      (
        v,
      ) => v['source_snapshot']['calculation_source']['previous_annual_basis'] =
          v['source_snapshot']['calculation_source']['current_annual_basis'],
    ];
    for (final change in changes) {
      final bad = copy(f['preview']);
      change(bad);
      expect(
        () => payrollOneOffCasePreview(bad, copy(f['command'])),
        throwsA(isA<ApiException>()),
      );
    }
  });
  test('receipt verifier keeps sealed original after editor changes', () {
    final body = clean(f['command']),
        preview = copy(f['preview']),
        validate = payrollOneOffCaseValidator(body, preview: preview);
    body['details']['verification_note'] = 'Later text';
    preview['plan']['net_minor']++;
    validate(f['saved']);
    final altered = copy(f['saved']);
    altered['source_hash'] = 'f' * 64;
    expect(() => validate(altered), throwsA(isA<ApiException>()));
  });
  test('unknown current source and foreign personal originals are refused', () {
    final v = values(copy(f['command'])), s = copy(f['sources']);
    for (final r in s['annual_facts'])
      if (r['id'] == v['one_off_earning_id']) r['status'] = 'void';
    expect(
      () => payrollOneOffCaseInput(id, s, v),
      throwsA(isA<ApiException>()),
    );
    final foreign = copy(f['sources']);
    foreign['files'][0]['employee_id'] = 'f' * 32;
    expect(
      () => payrollOneOffCaseInput(id, foreign, v),
      throwsA(isA<ApiException>()),
    );
  });
}

import 'dart:convert';
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:smartplan_office/api.dart';
import 'package:smartplan_office/business_payroll_oneoff_case_contract.dart';
import 'package:smartplan_office/business_payroll_annual_basis_contract.dart';
import 'package:smartplan_office/business_payroll_statements.dart';
import 'package:smartplan_office/business_payroll.dart';

final f = jsonDecode(
  File('test/fixtures/payroll_factor_oneoff.json').readAsStringSync(),
) as Map<String, dynamic>;
final employee = f['employee']['id'] as String;
Map<String, dynamic> copy(dynamic value) =>
    Map<String, dynamic>.from(jsonDecode(jsonEncode(value)) as Map);

void main() {
  test('actual protected V12/V2/V15 originals bind one run with positive factor tax', () {
    payrollAnnualSources(f['annual_sources'], employee);
    payrollAnnualRecord(
      f['source']['current_annual_basis'],
      employee,
      kind: 'annual_basis',
    );
    payrollAnnualRecord(
      f['source']['annual_tax_forecast'],
      employee,
      kind: 'annual_tax_forecast',
    );
    payrollOneOffCaseSources(f['case_sources'], employee, '2026-10');
    payrollOneOffCaseRecord(f['case'], employee);
    payrollOneOffSource(f['run_preview'], copy(f['run_input']));
    payrollPreview(f['run_preview'],copy(f['run_input']));
    payrollReceiptValidator(copy(f['run_command']),preview:copy(f['run_preview']))(f['run']);
    expect(
      f['run']['calculation']['one_off_details']['tax']['STS'],
      greaterThan(0),
    );
    expect(
      f['run']['calculation']['one_off_details']['tax']['SOLZS'],
      greaterThan(0),
    );
  });
  test('changed factor, versions, original annual identity or tax cents are rejected', () {
    for (final change in <void Function(Map<String, dynamic>)>[
      (v) => v['rule_version'] = 'latest',
      (v) => v['source_contract_version'] = 1,
      (v) => v['plan']['one_off_details']['tax_factor'] = '0.754',
      (v) => v['plan']['one_off_details']['tax']['STS']++,
      (v) =>
          v['sources']['calculation_source']['current_annual_basis']['sources']['annual_source_contract']['version'] =
              true,
      (v) =>
          v['sources']['calculation_source']['annual_tax_forecast']['plan']['factor_profile_ref']['content_hash'] =
              '0' * 64,
    ]) {
      final v = copy(f['case']);
      change(v);
      expect(
        () => payrollOneOffCaseRecord(v, employee),
        throwsA(isA<ApiException>()),
      );
    }
  });
  test('own schema5 statement and exact PDF keep known scope and discard private extras', () async {
    await payrollStatement(f['statement'], employee);
    await payrollStatementAttachment(
      base64Decode(f['pdf_base64']),
      copy(f['statement']),
    );
    for (final change in <void Function(Map<String, dynamic>)>[
      (v) => v['schema_version'] = 3,
      (v) => v['calculation']['scope'] = 'regular_standard_oneoff',
      (v) => v['calculation']['rule_version'] = 'de_2026_oneoff_composition_v6',
      (v) => v['one_off_summary']['tax_factor'] = '0.753',
      (v) => v['source'] = {},
      (v) => v['calculation']['net_minor']++,
    ]) {
      final v = copy(f['statement']);
      change(v);
      await expectLater(
        payrollStatement(v, employee),
        throwsA(isA<ApiException>()),
      );
    }
  });
}

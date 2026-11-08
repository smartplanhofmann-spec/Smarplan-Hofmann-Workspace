import 'dart:convert';
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:smartplan_office/api.dart';
import 'package:smartplan_office/business_payroll.dart';
import 'package:smartplan_office/business_payroll_statements.dart';

final f = jsonDecode(
  File('test/fixtures/payroll_factor_2026_workflow.json').readAsStringSync(),
) as Map<String, dynamic>;
Map<String, dynamic> copy(dynamic value) =>
    Map<String, dynamic>.from(jsonDecode(jsonEncode(value)) as Map);

Map<String, dynamic> values() {
  final p = copy(f['profile']['profile']);
  for (final key in [
    'has_children',
    'u1_required',
    'minijob_rv_exempt',
    'pension_other_compulsory',
  ]) {
    p[key] = p[key] == true ? 'yes' : 'no';
  }
  return {
    ...p,
    'special_cases': <String>[],
    'annual_gross': '60000',
    'regular_tax_scope': 'factor',
    'transition_scope': 'none',
    'tax_allowance_monthly_minor': '0',
    'tax_addition_monthly_minor': '0',
    'tax_factor': '0,753',
  };
}

void main() {
  test('factor is supplied as exact text and never rounded or inferred', () {
    expect(payrollFactor('0,753'), '0.753');
    expect(payrollFactor('0.000'), '0.000');
    for (final value in [
      '',
      null,
      0.753,
      '0.75',
      '0.7539',
      '1.000',
      '-0.100',
    ]) {
      expect(() => payrollFactor(value), throwsFormatException);
    }
  });
  test(
    'factor editor offers an explicit scope and preserves source profile',
    () {
      final fields = payrollProfileFields([copy(f['file'])]);
      expect(fields.any((field) => field.name == 'tax_factor'), isTrue);
      expect(payrollProfileInput(values()), f['profile']['profile']);
      for (final change in [
        {'tax_class': 1},
        {'tax_allowance_monthly_minor': '1'},
        {'tax_addition_monthly_minor': '1'},
        {'transition_scope': 'monthly'},
        {'tax_factor': ''},
        {'regular_tax_scope': 'standard'},
        {'employment_kind': 'minijob', 'regular_tax_scope': 'minijob'},
      ]) {
        expect(
          () => payrollProfileInput({...values(), ...change}),
          throwsFormatException,
        );
      }
    },
  );
  test(
    'factor calculation and source preview retain independently checked net',
    () {
      expect(payrollCalculation(f['run']['calculation'])['net_minor'], 332342);
      payrollPreview(copy(f['preview']), copy(f['inputs']));
      final altered = copy(f['preview']);
      altered['calculation']['tax_parameters']['tax_factor'] = '0.900';
      expect(
        () => payrollPreview(altered, copy(f['inputs'])),
        throwsA(isA<ApiException>()),
      );
      for (final change in [
        {'rule_version': 'de_2026_standard_monthly_pap_v2'},
        {'tax_parameters': <String, dynamic>{}},
        {'employee_tax_minor': 0},
      ]) {
        expect(
          () =>
              payrollCalculation({...copy(f['run']['calculation']), ...change}),
          throwsA(isA<ApiException>()),
        );
      }
    },
  );
  test('factor correction receipt retains actual tax deltas and historical version', () {
    payrollReceiptValidator(copy(f['command']), preview: copy(f['preview']))(
      f['run'],
    );
    payrollReceiptValidator(
      copy(f['corrected_command']),
      preview: copy(f['corrected_preview']),
      previous: copy(f['run']),
    )(f['corrected_run']);
    expect(f['corrected_run']['delta']['employee_tax_minor'], 11508);
    final altered = copy(f['corrected_run']);
    altered['delta']['individual_wage_tax_minor'] = 0;
    expect(
      () => payrollReceiptValidator(
        copy(f['corrected_command']),
        preview: copy(f['corrected_preview']),
        previous: copy(f['run']),
      )(altered),
      throwsA(isA<ApiException>()),
    );
  });
  test('employee factor statements contain own amounts without private tax profile', () async {
    await payrollStatement(f['statement'], f['employee']['id']);
    await payrollStatement(f['corrected_statement'], f['employee']['id']);
    expect(f['statement']['calculation']['net_minor'], 332342);
    expect(
      f['statement']['calculation'].containsKey('tax_parameters'),
      isFalse,
    );
  });
}

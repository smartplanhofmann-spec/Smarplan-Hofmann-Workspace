import 'dart:convert';
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:smartplan_office/api.dart';
import 'package:smartplan_office/business_payroll_oneoff_case_contract.dart';
import 'package:smartplan_office/business_payroll_multiple_case_contract.dart';
import 'package:smartplan_office/business_payroll_accounts.dart';

final fixture = jsonDecode(
  File('test/fixtures/oneoff_provenance_workflow.json').readAsStringSync(),
) as Map<String, dynamic>;
Map<String, dynamic> copy(dynamic value) =>
    Map<String, dynamic>.from(jsonDecode(jsonEncode(value)) as Map);

void main() {
  final cases = [
    ('single', 'one_off_case', payrollOneOffCaseRecord, payrollOneOffSource),
    (
      'multiple',
      'multiple_one_off_case',
      payrollMultipleCaseRecord,
      payrollMultipleSource,
    ),
  ];
  test('actual CRLF v6/v7 originals retain their complete source and money contract', () {
    for (final entry in cases) {
      final f = fixture[entry.$1],
          value = copy(f['preview']),
          before = jsonEncode(value),
          fact = copy(value['source'][entry.$2]);
      expect(fact['plan'], isNot(f['calculation_lf']));
      expect(fact['plan']['net_minor'], f['calculation_lf']['net_minor']);
      expect(entry.$3(fact, fact['employee_id']), fact);
      expect(entry.$4(value, copy(value['source']['input'])), value);
      expect(jsonEncode(value), before);
    }
  });
  test(
    'archived v6/v7 views reject substituted sources and monetary amounts',
    () {
      for (final entry in cases) {
        for (final change in <void Function(Map<String, dynamic>)>[
          (v) => v['calculation']['net_minor']++,
          (v) =>
              v['source'][entry
                  .$2]['details']['current_annual_basis_ref']['revision']++,
        ]) {
          final value = copy(fixture[entry.$1]['preview']);
          change(value);
          expect(
            () => entry.$4(value, copy(value['source']['input'])),
            throwsA(isA<ApiException>()),
          );
        }
      }
    },
  );
  test('actual CRLF original v1 payment plan binds accepted run and unchanged prior payment', () async {
    final paid = fixture['multiple_payment'],
        run = {
          ...copy(paid['run_metadata']),
          ...copy(fixture['multiple']['preview']),
        };
    expect(
      await payrollMultiplePaymentPlan(
        copy(paid['details']),
        run,
        prior: copy(paid['prior_payment']),
      ),
      paid['plan'],
    );
    final bad = copy(paid['details']);
    bad['payments'][1]['amount_minor']++;
    await expectLater(
      payrollMultiplePaymentPlan(bad, run, prior: copy(paid['prior_payment'])),
      throwsA(isA<ApiException>()),
    );
  });
}

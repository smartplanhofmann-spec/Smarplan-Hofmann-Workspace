import 'dart:convert';
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:smartplan_office/api.dart';
import 'package:smartplan_office/business_payroll_statements.dart';
import 'package:smartplan_office/business_payroll.dart';

final f = jsonDecode(
  File('test/fixtures/payroll_statements_v5.json').readAsStringSync(),
) as Map<String, dynamic>;
final full = jsonDecode(
  File('test/fixtures/payroll_calculation_cases.json').readAsStringSync(),
) as Map<String, dynamic>;
Map<String, dynamic> copy(dynamic v) =>
    Map<String, dynamic>.from(jsonDecode(jsonEncode(v)) as Map);
void main() {
  test(
    'actual v5 employee projection preserves own amounts and net deduction',
    () async {
      await payrollStatement(f, f['employee_id']);
      expect(f['calculation']['net_deductions_minor'], 109);
      expect(f['calculation']['payout_minor'], 172977);
      expect(f['travel_summary']['tax_free_external_minor'], 1400);
    },
  );
  test(
    'own projection rejects raw sources, unknown kinds and altered cash payout',
    () async {
      for (final change in <void Function(Map<String, dynamic>)>[
        (v) => v['earnings_summary'][0]['source_refs'] = [],
        (v) => v['travel_summary']['policy'] = {},
        (v) => v['earnings_summary'][0]['kind'] = 'private_claim',
        (v) => v['calculation']['payout_minor'] += 109,
        (v) => v['calculation']['net_deductions_minor'] = 0,
        (v) => v['schema_version'] = 1,
      ]) {
        final bad = copy(f);
        change(bad);
        await expectLater(
          payrollStatement(bad, f['employee_id']),
          throwsA(isA<ApiException>()),
        );
      }
    },
  );
  test('existing payroll, receipt and annual parsers dispatch actual source3 additively', () async {
    payrollCalculation(full['run']['calculation']);
    payrollPreview(full['run_preview'], copy(full['run_input']));
    payrollReceiptValidator(
      copy(full['run_command']),
      preview: copy(full['run_preview']),
    )(full['run']);
    await payrollLedgerSnapshot(
      full['ledger'],
      full['command']['employee_id'],
      2026,
    );
  });
}

import 'dart:convert';
import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:smartplan_office/api.dart';
import 'package:smartplan_office/business_session.dart';
import 'package:smartplan_office/business_payroll.dart';
import 'package:smartplan_office/business_payroll_statements.dart';

final f = jsonDecode(
  File('test/fixtures/payroll_statements_v6.json').readAsStringSync(),
) as Map<String, dynamic>;
Map<String, dynamic> copy(dynamic value) =>
    Map<String, dynamic>.from(jsonDecode(jsonEncode(value)) as Map);
dynamic order(dynamic value) => value is List
    ? value.map(order).toList()
    : value is Map
    ? {
        for (final k in value.keys.map((v) => '$v').toList()..sort())
          k: order(value[k]),
      }
    : value;
Future<void> rehash(Map<String, dynamic> value) async {
  final base = copy(value)
    ..remove('statement_hash')
    ..remove('pdf_sha256')
    ..remove('pdf_size');
  value['statement_hash'] = await payrollStatementHash(
    utf8.encode(jsonEncode(order(base))),
  );
}

class OneoffStatementsApi extends OfficeApi {
  OneoffStatementsApi() : super(apiVersion: 'v1') {
    token = 'synthetic-v6-employee';
  }
  bool allowed = true;
  final paths = <String>[];
  @override
  Future<dynamic> call(String path, [Map<String, dynamic>? body]) async {
    paths.add(path);
    if (path.startsWith('/api/business/capabilities'))
      return {
        'compatibility_mode': 'business',
        'generation': 1,
        'storage_version': 10,
        'readonly': false,
        'features': ['german_payroll_2026', 'payroll_employee_statements'],
        'capabilities': ['business_payroll'],
        'permissions': [if (allowed) 'time.own'],
        'organization': {
          'modules': {
            'personnel': {'enabled': true, 'visible': true},
          },
        },
      };
    if (path == '/api/me') return f['actor'];
    if (path == '/api/business/employees') return [f['employee']];
    if (!allowed) throw const ApiException(403, 'Freigabe entzogen');
    if (path.startsWith('/api/business/payroll/employee-statements?'))
      return copy(f['page']);
    if (path.contains('/payroll/employee-statements/') &&
        path.endsWith('/history'))
      return copy(f['history']);
    if (path.contains('/payroll/employee-statements/'))
      return {
        'employee_id': f['employee']['id'],
        'can_export': true,
        'statement': copy(
          path.contains('revision=1') ? f['previous'] : f['statement'],
        ),
      };
    throw StateError('Unapproved raw annual source request: $path');
  }
}

void main() {
  test(
    'actual v6 own statement and March split coexist with original v5 PDF',
    () async {
      for (final v in [f['statement'], f['previous'], f['march']]) {
        await payrollStatement(v, v['employee_id']);
      }
      await payrollStatementPage(f['page'], f['employee']['id']);
      await payrollStatementPage(f['history'], f['employee']['id']);
      expect(f['statement']['one_off_summary']['amount_minor'], 50000);
      expect(
        f['statement']['calculation']['payout_minor'] -
            f['previous']['calculation']['payout_minor'],
        39125,
      );
      expect(f['statement']['calculation']['net_deductions_minor'], 109);
      expect(f['march']['one_off_summary']['social_year'], 2025);
      expect(f['march']['one_off_summary']['tax_year'], 2026);
      await payrollStatementAttachment(
        base64Decode(f['pdf_base64']),
        copy(f['statement']),
      );
      await payrollStatementAttachment(
        base64Decode(f['previous_pdf_base64']),
        copy(f['previous']),
      );
      await expectLater(
        payrollStatementAttachment(
          base64Decode(f['previous_pdf_base64']),
          copy(f['statement']),
        ),
        throwsA(isA<ApiException>()),
      );
    },
  );
  test('rehashing cannot admit private annual facts or inconsistent year and money', () async {
    for (final change in <void Function(Map<String, dynamic>)>[
      (v) => v['one_off_summary']['annual_pay_before_minor'] = 1,
      (v) => v['one_off_summary']['earning_ref'] = {},
      (v) => v['one_off_summary']['employee_contributions']['profile'] = {},
      (v) => v['one_off_summary']['receipt_date'] = '2026-11-01',
      (v) => v['one_off_summary']['tax_year'] = 2025,
      (v) => v['one_off_summary']['social_year'] = 2025,
      (v) {
        v['one_off_summary']['social_year'] = 2025;
        v['one_off_summary']['march_clause'] = true;
      },
      (v) => v['one_off_summary']['employee_social_total_minor']++,
      (v) => v['one_off_summary']['individual_wage_tax_minor'] =
          v['calculation']['individual_wage_tax_minor'] + 1,
      (v) => v['one_off_summary']['amount_minor']++,
      (v) => v['calculation']['net_deductions_minor'] = 0,
      (v) => v['schema_version'] = 2,
      (v) =>
          v['calculation']['rule_version'] = 'de_2026_segments_entitlements_v5',
      (v) => v['calculation']['scope'] = 'regular_standard_segments',
      (v) => v['one_off_summary']['amount_minor'] = 0,
      (v) => v['calculation']['individual_wage_tax_minor'] = null,
      (v) => v['calculation']['individual_wage_tax_minor']++,
    ]) {
      final bad = copy(f['statement']);
      change(bad);
      await rehash(bad);
      await expectLater(
        payrollStatement(bad, f['employee']['id']),
        throwsA(isA<ApiException>()),
      );
    }
  });
  testWidgets(
    'existing own payroll entry shows v6 bonus and v5 history at 390px without private routes, then clears revocation',
    (tester) async {
      tester.view.physicalSize = const Size(390, 844);
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.resetPhysicalSize);
      addTearDown(tester.view.resetDevicePixelRatio);
      final api = OneoffStatementsApi();
      final current = BusinessSession(api: api);
      await current.load();
      await tester.pumpWidget(
        MaterialApp(
          home: BusinessPayrollPage(
            session: current,
            employee: copy(f['employee']),
          ),
        ),
      );
      await tester.pumpAndSettle();
      await tester.tap(find.text('Lohnnachweis ansehen'));
      await tester.pumpAndSettle();
      await tester.scrollUntilVisible(
        find.text('Einmalzahlung / sonstiger Bezug'),
        500,
      );
      expect(find.text('Brutto der Einmalzahlung'), findsOneWidget);
      expect(find.text('Berechneter Zuflussstichtag'), findsOneWidget);
      expect(tester.takeException(), null);
      await tester.scrollUntilVisible(find.text('Beleghistorie öffnen'), 500);
      await tester.tap(find.text('Beleghistorie öffnen'));
      await tester.pumpAndSettle();
      expect(find.text('Diese Fassung ansehen'), findsNWidgets(2));
      await tester.tap(find.text('Diese Fassung ansehen').first);
      await tester.pumpAndSettle();
      expect(find.textContaining('Fassung 1'), findsOneWidget);
      expect(find.text('Einmalzahlung / sonstiger Bezug'), findsNothing);
      expect(
        api.paths.any(
          (p) =>
              RegExp(
                r'/payroll/(runs|profiles|facts|annual-facts|one-off-cases)',
              ).hasMatch(p) ||
              p.contains('/personnel/files'),
        ),
        false,
      );
      api.allowed = false;
      await current.load();
      await tester.pumpAndSettle();
      expect(find.text('Netto'), findsNothing);
      expect(tester.takeException(), null);
      await tester.pumpWidget(const SizedBox.shrink());
      current.dispose();
    },
  );
}

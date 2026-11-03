import 'dart:convert';
import 'dart:io';
import 'dart:typed_data';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:smartplan_office/api.dart';
import 'package:smartplan_office/business_session.dart';
import 'package:smartplan_office/business_payroll.dart';
import 'package:smartplan_office/business_payroll_statements.dart';

final f = jsonDecode(
  File('test/fixtures/payroll_statements.json').readAsStringSync(),
) as Map<String, dynamic>;
Map<String, dynamic> copy(dynamic value) =>
    Map<String, dynamic>.from(jsonDecode(jsonEncode(value)) as Map);
final employee = f['employee']['id'] as String;

class StatementsApi extends OfficeApi {
  StatementsApi() : super(apiVersion: 'v1') {
    token = 'synthetic-employee-statement';
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
    if (path.startsWith('/api/business/payroll/employee-statements?')) {
      if (!allowed) throw const ApiException(403, 'Freigabe entzogen');
      return copy(f['page']);
    }
    if (path.contains('/payroll/employee-statements/') &&
        path.endsWith('/history'))
      return copy(f['page']);
    if (path.contains('/payroll/employee-statements/'))
      return {
        'employee_id': employee,
        'can_export': true,
        'statement': copy(f['statement']),
      };
    throw StateError('Unapproved raw source request: $path');
  }
}

void main() {
  test(
    'actual v4 employee statement and own PDF bind exact frozen bytes',
    () async {
      await payrollStatement(f['statement'], employee);
      await payrollStatementPage(f['page'], employee);
      final bytes = base64Decode(f['pdf_base64']);
      final attachment = await payrollStatementAttachment(
        bytes,
        copy(f['statement']),
      );
      expect(attachment.filename, 'lohnnachweis-2026-10-v1.pdf');
      expect(f['statement']['calculation']['net_minor'], 31878);
      final changed = Uint8List.fromList(bytes);
      changed[100] ^= 1;
      await expectLater(
        payrollStatementAttachment(changed, copy(f['statement'])),
        throwsA(isA<ApiException>()),
      );
    },
  );
  test('private nested fields and foreign or altered historical statement are rejected', () async {
    for (final alter in <void Function(Map<String, dynamic>)>[
      (v) => v['source'] = {},
      (v) => v['calculation']['profile'] = {},
      (v) => v['period_summary']['social_periods'][0]['reason'] = 'private',
      (v) => v['employee_id'] = 'f' * 32,
      (v) => v['run_ref']['revision']++,
      (v) => v['employee_name'] = 'Changed historical name',
      (v) => v['calculation']['net_minor']++,
    ]) {
      final bad = copy(f['statement']);
      alter(bad);
      await expectLater(
        payrollStatement(bad, employee),
        throwsA(isA<ApiException>()),
      );
    }
    await expectLater(
      payrollStatementPage({
        ...copy(f['page']),
        'items': [f['statement'], f['statement']],
      }, employee),
      throwsA(isA<ApiException>()),
    );
  });
  test('incomplete scope retains unknown values', () async {
    await payrollStatement(f['partial'], f['partial']['employee_id']);
    expect(f['partial']['calculation']['net_minor'], null);
    final v = copy(f['partial']);
    v['calculation']['net_minor'] = 0;
    await expectLater(
      payrollStatement(v, v['employee_id']),
      throwsA(isA<ApiException>()),
    );
  });
  testWidgets(
    'existing payroll entry uses only reduced own routes and clears on revoked rights at 390px',
    (tester) async {
      tester.view.physicalSize = const Size(390, 844);
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.resetPhysicalSize);
      addTearDown(tester.view.resetDevicePixelRatio);
      final api = StatementsApi();
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
      expect(find.text('Meine Lohnnachweise'), findsOneWidget);
      expect(find.text('Lohnnachweis ansehen'), findsOneWidget);
      await tester.tap(find.text('Lohnnachweis ansehen'));
      await tester.pumpAndSettle();
      expect(find.text('Netto'), findsOneWidget);
      expect(tester.takeException(), null);
      expect(
        api.paths.any(
          (p) =>
              p.contains('/payroll/runs') ||
              p.contains('/payroll/profiles') ||
              p.contains('/payroll/facts') ||
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

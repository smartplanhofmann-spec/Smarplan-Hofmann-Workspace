import 'dart:convert';
import 'dart:io';
import 'dart:typed_data';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:smartplan_office/api.dart';
import 'package:smartplan_office/business_payroll.dart';
import 'package:smartplan_office/business_payroll_statements.dart';
import 'package:smartplan_office/business_session.dart';

final fixture = jsonDecode(
  File('test/fixtures/payroll_statement_composites.json').readAsStringSync(),
) as Map<String, dynamic>;
Map<String, dynamic> copy(dynamic value) =>
    Map<String, dynamic>.from(jsonDecode(jsonEncode(value)) as Map);
dynamic ordered(dynamic v) => v is List
    ? v.map(ordered).toList()
    : v is Map
    ? {
        for (final key in v.keys.map((k) => '$k').toList()..sort())
          key: ordered(v[key]),
      }
    : v;
Future<Map<String, dynamic>> rehash(Map<String, dynamic> value) async {
  final base = copy(value)
    ..remove('statement_hash')
    ..remove('pdf_sha256')
    ..remove('pdf_size');
  value['statement_hash'] = await payrollStatementHash(
    utf8.encode(jsonEncode(ordered(base))),
  );
  return value;
}

void main() {
  for (final original in fixture['cases'] as List) {
    test(
      'actual own DTO and PDF: ${original['source_fixture']} ${original['kind']}',
      () async {
        final value = copy(original['statement']);
        await payrollStatement(value, original['employee_id']);
        await payrollStatementAttachment(
          base64Decode(original['pdf_base64']),
          value,
        );
        await payrollStatementJsonAttachment(
          Uint8List.fromList(utf8.encode(jsonEncode(ordered(value)))),
          value,
        );
        final text = jsonEncode(value);
        for (final key in [
          'profile',
          'tax_id',
          'social_insurance_number',
          'source_file_ids',
          'verification_note',
          'factor_transition_assessment',
        ]) {
          expect(text.contains('"$key":'), false, reason: key);
        }
      },
    );
  }
  test('known rules cannot borrow another scope or future rule with a recomputed narrow hash', () async {
    final examples = <String, dynamic>{
      for (final original in fixture['cases'])
        original['statement']['calculation']['rule_version']: original,
    };
    for (final original in examples.values) {
      for (final other in examples.values.where(
        (x) =>
            x['statement']['calculation']['rule_version'] !=
            original['statement']['calculation']['rule_version'],
      )) {
        final bad = copy(original['statement']);
        bad['calculation']['scope'] =
            other['statement']['calculation']['scope'];
        await rehash(bad);
        await expectLater(
          payrollStatement(bad, original['employee_id']),
          throwsA(
            isA<ApiException>().having(
              (e) => e.message,
              'message',
              contains('Belegversion'),
            ),
          ),
        );
      }
      final bad = copy(original['statement']);
      bad['calculation']['rule_version'] = 'de_2026_unreviewed_future';
      await rehash(bad);
      await expectLater(
        payrollStatement(bad, original['employee_id']),
        throwsA(isA<ApiException>()),
      );
    }
  });
  test('private additions, foreign employee and edited original PDF remain rejected', () async {
    for (final original in fixture['cases']) {
      final bad = copy(original['statement']);
      bad['calculation']['profile'] = {'tax_factor': .753};
      await rehash(bad);
      await expectLater(
        payrollStatement(bad, original['employee_id']),
        throwsA(isA<ApiException>()),
      );
      await expectLater(
        payrollStatement(original['statement'], 'f' * 32),
        throwsA(isA<ApiException>()),
      );
      final pdf = base64Decode(original['pdf_base64']);
      pdf[pdf.length - 50] ^= 1;
      await expectLater(
        payrollStatementAttachment(pdf, copy(original['statement'])),
        throwsA(isA<ApiException>()),
      );
    }
  });
  testWidgets(
    'actual new factor Midijob statement renders through own entry and clears on revocation at390px',
    (tester) async {
      tester.view.physicalSize = const Size(390, 844);
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.resetPhysicalSize);
      addTearDown(tester.view.resetDevicePixelRatio);
      final original = fixture['cases'].last,
          source = jsonDecode(
            File('test/fixtures/payroll_factor_transition.json')
                .readAsStringSync(),
          );
      final api = CompositeStatementsApi(
        copy(original['statement']),
        copy(source['employee']),
      );
      final session = BusinessSession(api: api);
      try {
        await session.load();
        await tester.pumpWidget(
          MaterialApp(
            home: BusinessPayrollPage(session: session, employee: api.employee),
          ),
        );
        await tester.pumpAndSettle();
        await tester.tap(find.text('Lohnnachweis ansehen'));
        await tester.pumpAndSettle();
        expect(find.text('Netto'), findsOneWidget);
        expect(find.textContaining('1.498,67'), findsWidgets);
        expect(
          api.paths.any(
            (p) => RegExp(r'/payroll/(runs|profiles|facts)(/|\?)').hasMatch(p),
          ),
          false,
        );
        api.allowed = false;
        await session.load();
        await tester.pumpAndSettle();
        expect(find.text('Netto'), findsNothing);
        expect(tester.takeException(), null);
      } finally {
        await tester.pumpWidget(const SizedBox.shrink());
        session.dispose();
        api.dispose();
      }
    },
  );
}

class CompositeStatementsApi extends OfficeApi {
  CompositeStatementsApi(this.statement, this.employee)
    : super(apiVersion: 'v1') {
    token = 'synthetic-own-factor-midijob';
  }
  final Map<String, dynamic> statement, employee;
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
    if (path == '/api/me')
      return {
        'id': employee['user_id'],
        'role': 'technician',
        'email': 'synthetic-own@example.test',
      };
    if (path == '/api/business/employees') return [employee];
    if (path.startsWith('/api/business/payroll/employee-statements')) {
      if (!allowed) throw const ApiException(403, 'Freigabe entzogen');
      return {
        'employee_id': employee['id'],
        'can_export': true,
        if (path.contains('?employee_id='))
          'items': [statement]
        else
          'statement': statement,
      };
    }
    throw StateError('Unapproved private source request: $path');
  }
}

import 'dart:convert';
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:smartplan_office/business_travel_cash.dart';

Map<String, dynamic> clone(dynamic value) =>
    Map<String, dynamic>.from(jsonDecode(jsonEncode(value)) as Map);

void main() {
  final fixture = jsonDecode(
    File('test/fixtures/travel_cash.json').readAsStringSync(),
  ) as Map;
  test('actual backend public cash and bank source with historical void', () {
    expect(travelCashPublic(fixture['active']), fixture['active']);
    expect(travelBankSource(fixture['bank']), fixture['bank']);
    expect(travelCashCategoryKeys(clone(fixture['active'])), [
      'travel_allowance',
    ]);
    expect(travelCashPublic(fixture['void']), fixture['void']);
    expect(travelCashCategoryKeys(clone(fixture['void'])), isEmpty);
    expect(fixture['void']['cash_movements'], isEmpty);
  });
  test('private additions at every public level are rejected', () {
    final changes = <void Function(Map<String, dynamic>)>[
      (s) => s['employee_id'] = 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',
      (s) => s['cash_movements'][0]['employee_name'] = 'Private',
      (s) => s['cash_movements'][0]['account']['personnel_file'] = 'secret',
      (s) => s['cash_movements'][0]['categories']['taxable_wages'] = '0.00',
    ];
    for (final change in changes) {
      final source = clone(fixture['active']);
      change(source);
      expect(() => travelCashPublic(source), throwsA(anything));
    }
    for (final key in ['employee_id', 'settlement_id', 'sources', 'file_id']) {
      expect(
        () => travelBankSource({...clone(fixture['bank']), key: 'private'}),
        throwsA(anything),
      );
    }
  });
  test('revision, monetary values and documentary void must be explicit', () {
    final changes = <void Function(Map<String, dynamic>)>[
      (s) => s['revision'] = true,
      (s) => s['revision'] = 2,
      (s) => s['source_hash'] = 'invalid',
      (s) => s['proof_hash'] = null,
      (s) => s['status'] = 'void',
      (s) => s['cash_movements'] = [],
      (s) => s['cash_movements'][0]['date'] = '2026-10-28',
      (s) => s['cash_movements'][0]['amount'] = '14.01',
      (s) => s['cash_movements'][0]['account']['currency'] = 'USD',
      (s) => s['cash_movements'][0]['account']['revision'] = 0,
    ];
    for (final change in changes) {
      final source = clone(fixture['active']);
      change(source);
      expect(() => travelCashPublic(source), throwsA(anything));
    }
    for (final value in [
      '0.00',
      '-14.00',
      '1e2',
      '14',
      14,
      '014.00',
      '14.001',
      null,
    ]) {
      final source = clone(fixture['active']);
      source['cash_movements'][0]['amount'] = value;
      source['cash_movements'][0]['categories']['travel_allowance'] = value;
      expect(() => travelCashPublic(source), throwsA(anything));
      expect(
        () => travelBankSource({...clone(fixture['bank']), 'amount': value}),
        throwsA(anything),
      );
    }
  });
  test('impossible calendar dates cannot become travel cash dates', () {
    for (final day in [
      '2026-02-29',
      '2026-04-31',
      '2026-00-01',
      '2026-13-01',
      '2026-10-00',
    ]) {
      final source = clone(fixture['active']);
      source['date'] = day;
      source['cash_movements'][0]['date'] = day;
      expect(() => travelCashPublic(source), throwsA(anything), reason: day);
      expect(
        () => travelBankSource({...clone(fixture['bank']), 'date': day}),
        throwsA(anything),
        reason: day,
      );
    }
  });
  test('bank source retains complete original revision and public shape', () {
    for (final change in [
      {'source_path': '${fixture['bank']['source_path']}&employee=private'},
      {
        'source_path': (fixture['bank']['source_path'] as String).replaceFirst(
          RegExp(r'revision=\d+$'),
          'revision=0',
        ),
      },
      {'origin_hash': 'bad'},
      {'source_hash': null},
      {'direction': 'refund'},
      {'source_kind': 'payroll_cash'},
    ]) {
      expect(
        () => travelBankSource({...clone(fixture['bank']), ...change}),
        throwsA(anything),
      );
    }
  });
}

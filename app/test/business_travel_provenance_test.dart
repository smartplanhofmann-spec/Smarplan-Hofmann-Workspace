import 'dart:convert';
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:smartplan_office/api.dart';
import 'package:smartplan_office/business_travel_allowances.dart';

final fixture = jsonDecode(
  File('test/fixtures/travel_provenance_workflow.json').readAsStringSync(),
) as Map<String, dynamic>;
Map<String, dynamic> copy(dynamic value) =>
    Map<String, dynamic>.from(jsonDecode(jsonEncode(value)) as Map);

void main() {
  final refs = (fixture['record']['details']['trip_refs'] as List)
      .map((value) => copy(value))
      .toList();
  test('actual archived CRLF travel retains original values and hashes', () {
    final old = copy(fixture['record']['calculation']),
        frozen = jsonEncode(old);
    expect(old['rule_hash'], isNot(fixture['calculation_lf']['rule_hash']));
    expect(old['totals']['tax_free_minor'], 933);
    expect(travelV3Calculation(old, refs), old);
    expect(jsonEncode(old), frozen);
    expect(
      travelV3Calculation(copy(fixture['calculation_lf']), refs),
      fixture['calculation_lf'],
    );
  });
  test('archived CRLF travel still requires linked original revisions and metadata', () {
    for (final change in <void Function(Map<String, dynamic>)>[
      (value) => value['ground_calendar_sources'][0]['trip']['revision']++,
      (value) => value['mixed_program_sources'][0]['facts_hash'] = 'invalid',
      (value) => value['mixed_program_sources'][0]['source_file_ids'] = [],
    ]) {
      final old = copy(fixture['record']['calculation']);
      change(old);
      expect(
        () => travelV3Calculation(old, refs),
        throwsA(isA<ApiException>()),
      );
    }
  });
}

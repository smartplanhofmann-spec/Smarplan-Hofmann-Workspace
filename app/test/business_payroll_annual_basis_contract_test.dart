import 'dart:convert';
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:smartplan_office/api.dart';
import 'package:smartplan_office/business_payroll_annual_basis_contract.dart';

final f = jsonDecode(
  File('../docs/fixtures/payroll-annual-basis-2026.json').readAsStringSync(),
) as Map<String, dynamic>;
Map<String, dynamic> copy(dynamic v) =>
    Map<String, dynamic>.from(jsonDecode(jsonEncode(v)) as Map);
dynamic ids(dynamic v, [String? key]) {
  if (key == 'claim_key' || key?.endsWith('_ref') == true)
    return v == null ? null : v['id'];
  if (key == 'document_refs' || key?.endsWith('_refs') == true)
    return [for (final r in v) r['id']];
  if (v is List) return v.map((v) => ids(v)).toList();
  if (v is Map)
    return {for (final e in v.entries) '${e.key}': ids(e.value, '${e.key}')};
  return v;
}

void main() {
  for (final fixture in f['cases'])
    test(
      'actual ${fixture['command']['kind']} typed references preserve canonical preview and receipt',
      () {
        final c = fixture['command'],
            id = c['employee_id'] as String,
            body = payrollAnnualInput(id, copy(fixture['sources']), c['kind'], {
              'details': ids(c['details']),
              'source_file_ids': c['source_file_ids'],
              'verification_note': c['details']['verification_note'],
            });
        payrollAnnualSources(fixture['sources'], id);
        payrollAnnualRecord(fixture['saved'], id);
        expect({
          ...body,
          'preview_hash': fixture['preview']['preview_hash'],
        }, copy(c)..remove('request_id'));
        payrollAnnualPreview(fixture['preview'], body);
        payrollAnnualValidator(
          copy(c)..remove('request_id'),
          preview: copy(fixture['preview']),
        )(fixture['saved']);
      },
    );
  test(
    'foreign originals, employer identity and replaced plan are rejected',
    () {
      for (final fixture in f['cases']) {
        final c = fixture['command'], bad = copy(fixture['preview']);
        bad['source_snapshot']['identity']['employee_id'] = 'f' * 32;
        expect(
          () => payrollAnnualPreview(bad, copy(c)),
          throwsA(isA<ApiException>()),
        );
        final changed = copy(fixture['saved']);
        changed['plan']['plan_hash'] = 'f' * 64;
        expect(
          () => payrollAnnualValidator(
            copy(c)..remove('request_id'),
            preview: copy(fixture['preview']),
          )(changed),
          throwsA(isA<ApiException>()),
        );
        final source = copy(fixture['sources']);
        source['files'][0]['employee_id'] = 'f' * 32;
        expect(
          () => payrollAnnualSources(source, c['employee_id']),
          throwsA(isA<ApiException>()),
        );
      }
    },
  );
  test('unknown monetary basis never becomes a zero source', () {
    expect(payrollAnnualMoney('0,00'), 0);
    expect(payrollAnnualMoney('12,34'), 1234);
    for (final v in ['', null, ' ', '1.234', '-1'])
      expect(() => payrollAnnualMoney(v), throwsA(isA<ApiException>()));
  });
}

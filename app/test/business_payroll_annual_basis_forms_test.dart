import 'package:flutter_test/flutter_test.dart';
import 'package:smartplan_office/api.dart';
import 'package:smartplan_office/business_payroll_annual_basis_contract.dart';
import 'package:smartplan_office/business_payroll_annual_basis_forms.dart';
import 'package:smartplan_office/business_widgets.dart';

import 'business_payroll_annual_basis_contract_test.dart' as actual;

Map<String, dynamic> renew(List<BusinessField> fields) => {
  for (final field in fields)
    field.name: field.type == BusinessInput.toggle ? true : field.initial,
};

void main() {
  for (final fixture in actual.f['cases']) {
    test(
      'all structured ${fixture['kind']} steps reconstruct actual canonical source details',
      () async {
        final command = fixture['command'],
            source = actual.copy(fixture['sources']),
            dialogs = <String>[],
            fieldsSeen = <BusinessField>[];
        final forms = PayrollAnnualForms(
          source,
          List<String>.from(command['source_file_ids']),
          (title, fields) async {
            dialogs.add(title);
            fieldsSeen.addAll(fields);
            for (final field in fields) {
              if (field.type == BusinessInput.choice && !field.required)
                expect(
                  field.choices.containsKey(''),
                  false,
                  reason: 'BusinessEditor supplies its optional empty option',
                );
              expect(field.name, isNot('details_json'));
            }
            return renew(fields);
          },
        );
        final result = await forms.collect(
          command['kind'],
          actual.copy(command['details']),
        );
        expect(result, isNotNull);
        final body = payrollAnnualInput(
          command['employee_id'],
          source,
          command['kind'],
          {
            'source_file_ids': command['source_file_ids'],
            'verification_note': command['details']['verification_note'],
            'details': {
              ...result!,
              'employer_identity_ref':
                  command['details']['employer_identity_ref']['id'],
            },
          },
        );
        expect({
          ...body,
          'preview_hash': fixture['preview']['preview_hash'],
        }, actual.copy(command)..remove('request_id'));
        expect(dialogs, isNotEmpty);
        expect(
          fieldsSeen.any(
            (field) =>
                field.name.endsWith('_ref') ||
                field.name.endsWith('_refs') ||
                field.name == 'claim_key',
          ),
          true,
        );
      },
    );
  }
  test('new amount, count and historical insurance choices are not fabricated defaults', () async {
    final fixture = actual.f['cases'][0];
    final forms = PayrollAnnualForms(actual.copy(fixture['sources']), [], (
      title,
      fields,
    ) async {
      for (final field in fields.where(
        (field) => [
          BusinessInput.integer,
          BusinessInput.decimal,
          BusinessInput.date,
          BusinessInput.choice,
        ].contains(field.type),
      ))
        expect(field.initial, isNull, reason: field.name);
      return null;
    });
    expect(await forms.collect('imported_period', {}), isNull);
  });
  test(
    'missing renewed classification and completeness produce form error 400',
    () async {
      for (final fixture in (actual.f['cases'] as List).where(
        (v) => ['annual_basis', 'one_off_earning'].contains(v['kind']),
      )) {
        final forms = PayrollAnnualForms(
          actual.copy(fixture['sources']),
          List<String>.from(fixture['command']['source_file_ids']),
          (title, fields) async => {
            for (final field in fields)
              field.name: field.type == BusinessInput.toggle
                  ? false
                  : field.initial,
          },
        );
        await expectLater(
          forms.collect(
            fixture['kind'],
            actual.copy(fixture['command']['details']),
          ),
          throwsA(isA<ApiException>().having((e) => e.status, 'status', 400)),
        );
      }
    },
  );
  test(
    'unknown amount and count are rejected before they become annual zero',
    () async {
      final fixture = (actual.f['cases'] as List).firstWhere(
        (v) => v['kind'] == 'one_off_earning',
      );
      for (final invalid in ['amount_minor', 'period_count']) {
        final forms = PayrollAnnualForms(
          actual.copy(fixture['sources']),
          List<String>.from(fixture['command']['source_file_ids']),
          (title, fields) async => {...renew(fields), invalid: null},
        );
        await expectLater(
          forms.collect(
            fixture['kind'],
            actual.copy(fixture['command']['details']),
          ),
          throwsA(isA<ApiException>().having((e) => e.status, 'status', 400)),
        );
      }
    },
  );
}

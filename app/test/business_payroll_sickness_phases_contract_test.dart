import 'dart:convert';
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:smartplan_office/api.dart';
import 'package:smartplan_office/business_payroll_entitlement_contract.dart';

Map<String, dynamic> copy(dynamic value) =>
    Map<String, dynamic>.from(jsonDecode(jsonEncode(value)) as Map);
final samples = [
  for (final name in ['phases_v3', 'start_v4'])
    jsonDecode(
      File('test/fixtures/payroll_sickness_$name.json').readAsStringSync(),
    )['sickness'],
];
Map<String, dynamic> assemble(dynamic value) {
  final original = value['command']['details']['input'],
      base = copy(original),
      cases = original['prevention_cases'] as List;
  base.remove('prevention_cases');
  base.remove('employment_commencement');
  final episodes = base['episodes'] as List;
  return payrollSicknessStructure(
    base,
    original['employment_commencement'] == null ? 'combined' : 'preemployment',
    caseChoices: [
      for (var i = 0; i < episodes.length; i++)
        (() {
          final item = cases.firstWhere(
            (c) => (c['episode_ids'] as List).contains(episodes[i]['id']),
          );
          final first = episodes.indexWhere(
            (e) => (item['episode_ids'] as List).contains(e['id']),
          );
          return first == i ? 'new' : 'same:$first';
        })(),
    ],
    caseIds: [
      for (final episode in episodes)
        cases.firstWhere(
              (c) => (c['episode_ids'] as List).contains(episode['id']),
            )['id']
            as String,
    ],
    evidenceRefs: [for (final ref in cases[0]['evidence_refs']) copy(ref)],
    commencement: original['employment_commencement'] == null
        ? null
        : copy(original['employment_commencement']),
  );
}

Map<String, dynamic> values(dynamic value, Map<String, dynamic> input) {
  final details = value['command']['details'];
  return {
    'case_key': details['case_key'],
    'employment_terms_id': details['employment_terms_ref']['id'],
    'agreement_ids': [for (final ref in details['agreement_refs']) ref['id']],
    'work_schedule_ids': <String>[],
    'preparation_ids': <String>[],
    'source_file_ids': value['command']['source_file_ids'],
    'verification_note': details['verification_note'],
    'input': input,
  };
}

void main() {
  for (var index = 0; index < samples.length; index++) {
    test(
      'actual sickness v${index + 3} structured input preserves original and checked preview',
      () {
        final value = samples[index],
            id = value['command']['employee_id'] as String,
            input = assemble(value),
            original = copy(value['command'])..remove('request_id');
        expect(input, value['command']['details']['input']);
        payrollEntitlementSources(value['sources'], id);
        payrollEntitlementRecord(value['saved'], id);
        final body = payrollEntitlementInput(
          id,
          copy(value['sources']),
          'sickness_history',
          values(value, input),
        );
        expect({
          ...body,
          'preview_hash': value['preview']['preview_hash'],
        }, original);
        payrollEntitlementPreview(value['preview'], body);
        payrollEntitlementValidator(original, preview: copy(value['preview']))(
          value['saved'],
        );
      },
    );
  }
  test(
    'joined cause needs existing AU without fabricated recovery or shift',
    () {
      final source = copy(samples[0]['command']['details']['input']),
          cases = source.remove('prevention_cases') as List,
          ids = [for (final _ in source['episodes']) cases[0]['id'] as String],
          refs = [for (final r in cases[0]['evidence_refs']) copy(r)];
      Map<String, dynamic> run(List<String> choices) =>
          payrollSicknessStructure(
            source,
            'combined',
            caseChoices: choices,
            caseIds: ids,
            evidenceRefs: refs,
          );
      expect(() => run(['new', 'new']), throwsA(isA<ApiException>()));
      expect(() => run(['same:0', 'same:0']), throwsA(isA<ApiException>()));
      source['episodes'][1]['recovery_before'] = true;
      expect(() => run(['new', 'same:0']), throwsA(isA<ApiException>()));
      source['episodes'][1]['recovery_before'] = false;
      source['episodes'][1]['first_scheduled_day'] = '2026-11-20';
      expect(() => run(['new', 'same:0']), throwsA(isA<ApiException>()));
      expect(
        () => payrollSicknessStructure(source, 'separate'),
        throwsA(isA<ApiException>()),
      );
    },
  );
  test(
    'preemployment keeps actual earlier onset and requires contract original',
    () {
      final source = copy(samples[1]['command']['details']['input']),
          cases = source.remove('prevention_cases') as List;
      source.remove('employment_commencement');
      expect(
        () => payrollSicknessStructure(
          source,
          'preemployment',
          caseChoices: ['new'],
          caseIds: [cases[0]['id']],
          evidenceRefs: [for (final r in cases[0]['evidence_refs']) copy(r)],
        ),
        throwsA(isA<ApiException>()),
      );
      final result = assemble(samples[1]);
      expect(result['episodes'][0]['from'], '2026-10-10');
      expect(result['episodes'][0]['first_scheduled_day'], isNull);
    },
  );
  test('phase parser rejects unknown rules overlap identity errors and nonboolean flags', () {
    for (final alter in <void Function(Map<String, dynamic>)>[
      (v) => v['plan']['rule_version'] = 'de_2026_sickness_future',
      (v) => v['plan']['phases'][1]['from_date'] =
          v['plan']['phases'][0]['to_date'],
      (v) => v['plan']['phases'][0]['responsible_episode_id'] = 'f' * 32,
      (v) => v['plan']['phases'] = [null],
      (v) => v['plan']['phases'][0]['entitled'] = 'true',
    ]) {
      final value = copy(samples[0]['saved']);
      alter(value);
      expect(
        () => payrollEntitlementRecord(value, value['employee_id']),
        throwsA(isA<ApiException>()),
      );
    }
    final value = copy(samples[1]['saved']);
    value['plan']['preemployment_periods'][0]['employment_wage_entitlement'] =
        true;
    expect(
      () => payrollEntitlementRecord(value, value['employee_id']),
      throwsA(isA<ApiException>()),
    );
  });
  test('case and employment contract proof remain canonical employee file references', () {
    for (final value in samples) {
      final input = assemble(value);
      input['prevention_cases'][0]['evidence_refs'][0]['content_hash'] =
          'f' * 64;
      expect(
        () => payrollEntitlementInput(
          value['command']['employee_id'],
          copy(value['sources']),
          'sickness_history',
          values(value, input),
        ),
        throwsA(isA<ApiException>()),
      );
    }
    final value = samples[1], input = assemble(value);
    input['employment_commencement']['evidence_refs'][0]['id'] = 'f' * 32;
    expect(
      () => payrollEntitlementInput(
        value['command']['employee_id'],
        copy(value['sources']),
        'sickness_history',
        values(value, input),
      ),
      throwsA(isA<ApiException>()),
    );
  });
}

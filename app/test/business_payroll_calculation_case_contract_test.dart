import 'dart:convert';
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:smartplan_office/api.dart';
import 'package:smartplan_office/business_payroll_calculation_case_contract.dart';

final f = jsonDecode(
  File('test/fixtures/payroll_calculation_cases.json').readAsStringSync(),
) as Map<String, dynamic>;
Map<String, dynamic> copy(dynamic v) =>
    Map<String, dynamic>.from(jsonDecode(jsonEncode(v)) as Map);
Map<String, dynamic> values() {
  final d = f['command']['details'], decision = d['flat_tax_decision'];
  return {
    'month': d['month'],
    'period_case_id': d['period_case_ref']['id'],
    'employment_terms_ids': [
      for (final r in d['employment_terms_refs']) r['id'],
    ],
    'profile_ids': [for (final r in d['profile_refs']) r['id']],
    'identity_ids': [for (final r in d['identity_refs']) r['id']],
    'entitlement_case_ids': [
      for (final r in d['entitlement_case_refs']) r['id'],
    ],
    'travel_settlement_ids': [
      for (final r in d['travel_settlement_refs']) r['id'],
    ],
    'segment_events': [],
    'thirty_day_rule': d['thirty_day_rule'],
    'source_file_ids': f['command']['source_file_ids'],
    'verification_note': d['verification_note'],
    'policy_id': decision['policy_ref']['id'],
    'record_on_finalize': true,
    'employee_deduction_file_id': decision['employee_deduction_file_ref']['id'],
  };
}

void main() {
  test('actual evidence policy binds ELStAM identity and separately evidenced membership', () {
    final e = jsonDecode(
          File('test/fixtures/payroll_calculation_case_evidence.json')
              .readAsStringSync(),
        ) as Map<String, dynamic>,
        d = e['command']['details'],
        decision = d['flat_tax_decision'],
        m = decision['church_membership_evidence'];
    final v = <String, dynamic>{
      'month': d['month'],
      'period_case_id': d['period_case_ref']['id'],
      'employment_terms_ids': [
        for (final r in d['employment_terms_refs']) r['id'],
      ],
      'profile_ids': [for (final r in d['profile_refs']) r['id']],
      'identity_ids': [for (final r in d['identity_refs']) r['id']],
      'entitlement_case_ids': [
        for (final r in d['entitlement_case_refs']) r['id'],
      ],
      'travel_settlement_ids': [
        for (final r in d['travel_settlement_refs']) r['id'],
      ],
      'segment_events': [],
      'thirty_day_rule': d['thirty_day_rule'],
      'source_file_ids': e['command']['source_file_ids'],
      'verification_note': d['verification_note'],
      'policy_id': decision['policy_ref']['id'],
      'record_on_finalize': true,
      'membership_kind': m['kind'],
      'membership_identity_id': m['reference']['id'],
      'membership_church_tax': m['church_tax'],
    };
    final body = payrollCalculationCaseInput(
      e['command']['employee_id'],
      copy(e['sources']),
      v,
    );
    expect({
      ...body,
      'preview_hash': e['preview']['preview_hash'],
    }, copy(e['command'])..remove('request_id'));
    payrollCalculationCasePreview(e['preview'], body);
    payrollCalculationCaseValidator(
      copy(e['command'])..remove('request_id'),
      preview: copy(e['preview']),
    )(e['saved']);
    final bad = copy(e['preview']);
    bad['source_snapshot']['flat_travel_tax']['parameters']['church_tax'] =
        true;
    expect(
      () => payrollCalculationCasePreview(bad, body),
      throwsA(isA<ApiException>()),
    );
    expect(
      () => payrollCalculationCaseInput(
        e['command']['employee_id'],
        copy(e['sources']),
        {...v, 'membership_identity_id': e['sources']['files'][0]['id']},
      ),
      throwsA(isA<ApiException>()),
    );
  });

  test('actual v5 typed case command and accepted plan preserve all original sources', () {
    final id = f['command']['employee_id'] as String,
        body = payrollCalculationCaseInput(id, copy(f['sources']), values());
    expect({
      ...body,
      'preview_hash': f['preview']['preview_hash'],
    }, copy(f['command'])..remove('request_id'));
    payrollCalculationCasePreview(f['preview'], body);
    payrollCalculationCaseValidator({
      ...body,
      'preview_hash': f['preview']['preview_hash'],
    }, preview: copy(f['preview']))(f['saved']);
    expect(payrollCalculationCaseRunInput(copy(f['saved'])), f['run_input']);
  });
  test('actual v5 net includes taxable travel once and subtracts documented employee flat tax costs', () {
    payrollCompositeSource(f['run_preview'], copy(f['run_input']));
    payrollCompositeCalculation(f['run']['calculation']);
    expect(f['run']['calculation']['net_deductions_minor'], 109);
    expect(f['run']['calculation']['payout_minor'], 172977);
    for (final alter in <void Function(Map<String, dynamic>)>[
      (v) => v['payout_minor'] += 109,
      (v) => v['net_deductions_minor'] = 0,
      (v) => v['employer_total_excluding_accident_insurance_minor'] += 109,
      (v) => v['period_details']['travel']['tax_free_external_minor'] = null,
      (v) =>
          v['period_details']['social_assessments'][0]['employee_contributions']['care']++,
    ]) {
      final bad = copy(f['run']['calculation']);
      alter(bad);
      expect(
        () => payrollCompositeCalculation(bad),
        throwsA(isA<ApiException>()),
      );
    }
  });
  test('foreign private source, replaced case, unsupported rules and altered accepted body fail', () {
    final id = f['command']['employee_id'] as String;
    for (final alter in <void Function(Map<String, dynamic>)>[
      (v) => v['employee_id'] = 'f' * 32,
      (v) => v['month'] = '2026-11',
      (v) => v['travel_settlements'][0]['employee_id'] = 'f' * 32,
    ]) {
      final bad = copy(f['sources']);
      alter(bad);
      expect(
        () => payrollCalculationCaseSources(bad, id, '2026-10'),
        throwsA(isA<ApiException>()),
      );
    }
    final bad = copy(f['run_preview']);
    bad['source']['calculation_case']['sources']['profiles'][0]['revision']++;
    expect(
      () => payrollCompositeSource(bad, copy(f['run_input'])),
      throwsA(isA<ApiException>()),
    );
    final future = copy(f['saved']);
    future['rule_version'] = 'future';
    expect(
      () => payrollCalculationCaseRecord(future, id),
      throwsA(isA<ApiException>()),
    );
  });
}

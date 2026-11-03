import 'dart:convert';
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:smartplan_office/api.dart';
import 'package:smartplan_office/business_payroll_entitlement_contract.dart';

final fixture = jsonDecode(
  File('test/fixtures/payroll_entitlements.json').readAsStringSync(),
) as Map<String, dynamic>;
Map<String, dynamic> copy(dynamic value) =>
    Map<String, dynamic>.from(jsonDecode(jsonEncode(value)) as Map);
Map<String, dynamic> clean(dynamic value) => copy(value)..remove('request_id');
Map<String, dynamic> values(dynamic value) {
  final d = value['command']['details'];
  return {
    'case_key': d['case_key'],
    'employment_terms_id': d['employment_terms_ref']['id'],
    'agreement_ids': [for (final v in d['agreement_refs']) v['id']],
    'work_schedule_ids': [for (final v in d['work_schedule_refs']) v['id']],
    'preparation_ids': [for (final v in d['preparation_refs']) v['id']],
    'sickness_history_id': d['sickness_history_ref']?['id'] ?? '',
    'source_file_ids': value['command']['source_file_ids'],
    'input': d['input'],
    'verification_note': d['verification_note'],
    'correction_reason': value['command']['correction_reason'],
  };
}

void main() {
  test('explicit sickness v2 preserves historical v1 and rejects unknown or mismatched rules',(){
    final history=copy((fixture['sickness']['sources']['entitlements'] as List).firstWhere((v)=>v['kind']=='sickness_history')),id=history['employee_id'] as String;
    payrollEntitlementRecord(history,id);history['plan']['rule_version']='de_2026_sickness_v2';payrollEntitlementRecord(history,id);
    history['plan']['rule_version']='de_2026_sickness_future';expect(()=>payrollEntitlementRecord(history,id),throwsA(isA<ApiException>()));
    final wrong=copy(fixture['unpaid']['saved']);wrong['plan']['rule_version']='de_2026_sickness_v2';expect(()=>payrollEntitlementRecord(wrong,wrong['employee_id']),throwsA(isA<ApiException>()));
  });

  test(
    'actual P4 typed corrections bind canonical sources and original preview',
    () {
      for (final name in ['sickness', 'vacation', 'unpaid']) {
        final v = fixture[name], id = v['command']['employee_id'] as String;
        payrollEntitlementSources(v['sources'], id);
        payrollEntitlementRecord(v['saved'], id);
        final body = payrollEntitlementInput(
          id,
          copy(v['sources']),
          v['saved']['kind'],
          values(v),
          previous: copy(v['history']['items'][0]),
        );
        expect({
          ...body,
          'preview_hash': v['preview']['preview_hash'],
        }, clean(v['command']));
        payrollEntitlementPreview(v['preview'], body);
        payrollEntitlementValidator(
          clean(v['command']),
          previous: copy(v['history']['items'][0]),
          preview: copy(v['preview']),
        )(v['saved']);
      }
      expect(
        fixture['vacation']['command']['details']['input']['reference_days']
            .length,
        91,
      );
    },
  );
  test('foreign private source, mutable original revision and changed accepted plan are rejected', () {
    final v = fixture['sickness'], id = v['command']['employee_id'] as String;
    for (final alter in <void Function(Map<String, dynamic>)>[
      (v) => v['files'][0]['employee_id'] = 'f' * 32,
      (v) => v['file_references'][0]['revision'] = 2,
      (v) => v['entitlements'][0]['employee_id'] = 'f' * 32,
    ]) {
      final page = copy(v['sources']);
      alter(page);
      expect(
        () => payrollEntitlementSources(page, id),
        throwsA(isA<ApiException>()),
      );
    }
    final bad = copy(v['saved']);
    bad['plan']['gross_minor']++;
    expect(
      () => payrollEntitlementValidator(
        clean(v['command']),
        previous: copy(v['history']['items'][0]),
        preview: copy(v['preview']),
      )(bad),
      throwsA(isA<ApiException>()),
    );
  });
  test('fresh own-only and write-only rights do not authorize private entitlement approval', () {
    final caps = {
      'readonly': false,
      'features': ['payroll_entitlements'],
      'capabilities': ['business_payroll_entitlements'],
      'permissions': ['personnel.read', 'personnel.approve'],
    };
    expect(payrollEntitlementRights(caps)['approve'], true);
    expect(
      payrollEntitlementRights({
        ...caps,
        'permissions': ['time.own'],
      })['read'],
      false,
    );
    expect(
      payrollEntitlementRights({
        ...caps,
        'permissions': ['personnel.read', 'personnel.write'],
      })['approve'],
      false,
    );
  });
  test(
    'money and date inputs distinguish unknown from expressly evidenced zero',
    () {
      expect(payrollEntitlementMoney('0,00'), 0);
      expect(payrollEntitlementMoney('12,34'), 1234);
      expect(() => payrollEntitlementMoney(''), throwsA(isA<ApiException>()));
      expect(payrollEntitlementDays('2026-02-27', '2026-03-01'), [
        '2026-02-27',
        '2026-02-28',
        '2026-03-01',
      ]);
      expect(
        () => payrollEntitlementDays('2026-02-29', '2026-03-01'),
        throwsA(isA<ApiException>()),
      );
    },
  );
}

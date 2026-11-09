import 'dart:convert';
import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:smartplan_office/api.dart';
import 'package:smartplan_office/business_payroll.dart';
import 'package:smartplan_office/business_payroll_accounts.dart';
import 'package:smartplan_office/business_payroll_calculation_case_contract.dart';
import 'package:smartplan_office/business_payroll_calculation_cases.dart';
import 'package:smartplan_office/business_session.dart';
import 'package:smartplan_office/business_widgets.dart';

final all = jsonDecode(
  File('test/fixtures/individual_minijob_v11.json').readAsStringSync(),
) as Map<String, dynamic>;
final boundaries = jsonDecode(
  File('test/fixtures/individual_minijob_client_boundaries.json')
      .readAsStringSync(),
) as Map<String, dynamic>;
Map<String, dynamic> copy(dynamic value) =>
    Map<String, dynamic>.from(jsonDecode(jsonEncode(value)) as Map);
Map<String, dynamic> values(Map<String, dynamic> branch) {
  final command = branch['case_command'],
      d = command['details'],
      a = d['individual_minijob_assessment'];
  return {
    'month': d['month'],
    'rule_version': individualMinijobRule,
    'period_case_id': d['period_case_ref']['id'],
    'employment_terms_id': d['employment_terms_refs'][0]['id'],
    'profile_id': d['profile_refs'][0]['id'],
    'identity_id': d['identity_refs'][0]['id'],
    'source_file_ids': command['source_file_ids'],
    'verification_note': d['verification_note'],
    'valid_from': a['valid_from'],
    'valid_to': a['valid_to'],
    'declaration_date': a['declaration_date'],
    'actual_health_insurance': a['actual_health_insurance'],
    'pension_status': a['pension_status'],
    'assessment_note': a['verification_note'],
    for (final key in individualMinijobConfirmations.keys) key: a[key],
    for (final key in individualMinijobEvidence.keys) '${key}_id': a[key]['id'],
    if (command['correction_reason'] != null)
      'correction_reason': command['correction_reason'],
  };
}

class MinijobApi extends OfficeApi {
  MinijobApi(this.branch) : super(apiVersion: 'v1') {
    token = 'synthetic-individual-minijob-session';
  }
  final Map<String, dynamic> branch;
  bool feature = true, approve = true, lose = false, oldOnly = false;
  String? returnedEmployee;
  final sent = <Map<String, dynamic>>[];
  String get employee => branch['employee']['id'];
  @override
  Future<dynamic> call(String path, [Map<String, dynamic>? body]) async {
    if (path.startsWith('/api/business/capabilities'))
      return {
        'compatibility_mode': 'business',
        'generation': 1,
        'storage_version': 10,
        'readonly': false,
        'features': [
          'payroll_calculation_cases',
          'german_payroll_2026',
          if (feature) individualMinijobFeature,
        ],
        'capabilities': [
          'business_payroll_calculation_cases',
          'business_payroll',
        ],
        'permissions': ['personnel.read', if (approve) 'personnel.approve'],
        'organization': {
          'modules': {
            'personnel': {'enabled': true, 'visible': true},
          },
        },
      };
    if (path == '/api/me') return {'id': 'a' * 32};
    if (path.startsWith('/api/business/payroll/calculation-cases/sources?'))
      return {
        ...copy(branch['sources']),
        'employee_id': returnedEmployee ?? employee,
        'calculation_cases': [copy(branch[oldOnly ? 'legacy_case' : 'case'])],
      };
    if (path == '/api/business/payroll/calculation-cases') {
      sent.add(copy(body));
      if (lose) {
        lose = false;
        throw const ApiException(0, 'Synthetic accepted answer lost.');
      }
      return copy(branch['case']);
    }
    if (path.startsWith('/api/business/payroll/runs?'))
      return {
        'employee_id': returnedEmployee ?? employee,
        'items': [copy(branch['run'])],
      };
    if (path == '/api/business/payroll/runs') {
      sent.add(copy(body));
      if (lose) {
        lose = false;
        throw const ApiException(0, 'Synthetic accepted payroll answer lost.');
      }
      return copy(branch['run']);
    }
    throw StateError(path);
  }
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  test('real compulsory exempt and explicit migrated fixtures retain their own contracts', () {
    for (final name in ['compulsory', 'exempt', 'migrated']) {
      final b = copy(all[name]), employee = b['employee']['id'] as String;
      final previous = name == 'migrated' ? copy(b['legacy_case']) : null;
      final body = payrollCalculationCaseInput(
        employee,
        copy(b['sources']),
        values(b),
        previous: previous,
      );
      final expected = copy(b['case_command'])..remove('request_id');
      expected['source_file_ids'] = List<String>.from(
        expected['source_file_ids'],
      )..sort();
      expect({
        ...body,
        'preview_hash': b['case_preview']['preview_hash'],
      }, expected);
      payrollCalculationCasePreview(b['case_preview'], body);
      payrollCalculationCaseValidator(
        {...body, 'preview_hash': b['case_preview']['preview_hash']},
        previous: previous,
        preview: copy(b['case_preview']),
      )(b['case']);
      expect(payrollCalculationCaseRunInput(copy(b['case'])), b['run_input']);
      payrollCompositeSource(b['run_preview'], copy(b['run_input']));
      final calculation = payrollCalculation(b['run']['calculation']);
      expect(calculation['scope'], individualMinijobScope);
      expect(calculation['net_minor'], name == 'exempt' ? 44484 : 43334);
      expect(b['profile']['profile']['health_insurance'], 'statutory_other');
      expect(
        calculation['tax_parameters']['actual_health_insurance'],
        'statutory_family',
      );
      expect(
        calculation['tax_parameters']['technical_pap_parameters']['PKV'],
        1,
      );
    }
  });
  test('five concrete originals are required and incomplete declarations cannot calculate', () {
    final b = copy(all['compulsory']), employee = b['employee']['id'] as String;
    for (final key in individualMinijobConfirmations.keys) {
      final input = payrollCalculationCaseInput(employee, copy(b['sources']), {
        ...values(b),
        key: false,
      });
      expect(input['details']['individual_minijob_assessment'][key], false);
      expect(
        () => individualMinijobAssessment(
          input['details']['individual_minijob_assessment'],
          employee,
          '2026-10',
        ),
        throwsA(isA<ApiException>()),
      );
    }
    for (final key in individualMinijobEvidence.keys) {
      expect(
        () => payrollCalculationCaseInput(employee, copy(b['sources']), {
          ...values(b),
          '${key}_id': 'e' * 32,
        }),
        throwsA(isA<ApiException>()),
      );
    }
    expect(
      () => individualMinijobAssessment(
        {
          ...copy(b['case']['details']['individual_minijob_assessment']),
          'actual_health_insurance': 'private',
        },
        employee,
        '2026-10',
      ),
      throwsA(isA<ApiException>()),
    );
    expect(
      () => individualMinijobAssessment(
        {
          ...copy(b['case']['details']['individual_minijob_assessment']),
          'valid_from': '2026-10-02',
        },
        employee,
        '2026-10',
      ),
      throwsA(isA<ApiException>()),
    );
  });
  test('actual accepted wider evidence and multiline Unicode notes remain unchanged', () {
    final b = copy(boundaries['covered']),
        command = copy(b['command']),
        employee = b['employee_id'] as String;
    final note =
        command['details']['individual_minijob_assessment']['verification_note']
            as String;
    expect(note.contains('\n'), true);
    expect(note.contains('\t'), true);
    expect(note.length, greaterThan(3000));
    expect(note.runes.length, lessThanOrEqualTo(3000));
    final value = payrollCalculationCaseRecord(b['record'], employee);
    expect(
      value['details']['individual_minijob_assessment']['verification_note'],
      note,
    );
    expect(value['plan']['can_calculate'], true);
    expect(
      value['details']['individual_minijob_assessment']['valid_from'],
      '2026-01-01',
    );
    expect(
      value['details']['individual_minijob_assessment']['valid_to'],
      '2026-12-31',
    );
    payrollCalculationCasePreview(b['preview'], command);
    payrollCalculationCaseValidator(command, preview: copy(b['preview']))(
      b['record'],
    );
    payrollCompositeSource(b['run_preview'], copy(b['run_input']));
    expect(b['run_preview']['calculation']['net_minor'], 43334);
  });
  test('actual accepted blocked V11 evidence remains readable with no invented net', () {
    final b = copy(boundaries['blocked']),
        employee = b['employee_id'] as String;
    final value = payrollCalculationCaseRecord(b['record'], employee);
    expect(
      value['details']['individual_minijob_assessment']['income_review_complete'],
      false,
    );
    expect(value['plan']['can_calculate'], false);
    payrollCalculationCasePreview(b['preview'], copy(b['command']));
    payrollCalculationCaseValidator(
      copy(b['command']),
      preview: copy(b['preview']),
    )(value);
    payrollCompositeSource(b['run_preview'], copy(b['run_input']));
    final calculation = payrollCalculation(b['run_preview']['calculation']);
    expect(calculation['scope'], 'unsupported');
    expect(calculation['net_minor'], isNull);
    expect(calculation['payout_minor'], isNull);
    final replaced = copy(calculation)..['net_minor'] = 0;
    expect(() => payrollCalculation(replaced), throwsA(isA<ApiException>()));
    expect(
      () => payrollCalculationCaseRunInput(value),
      throwsA(isA<ApiException>()),
    );
  });
  test('assessment retains exact original text but rejects malformed shapes and Unicode', () {
    final b = copy(boundaries['covered']),
        employee = b['employee_id'] as String;
    final original = copy(
      b['record']['details']['individual_minijob_assessment'],
    );
    for (final change in <void Function(Map<String, dynamic>)>[
      (v) => v['income_review_complete'] = 1,
      (v) => v['actual_health_insurance'] = 'invented',
      (v) => v['valid_from'] = '2027-01-01',
      (v) => v['valid_to'] = '2025-12-31',
      (v) => v['health_evidence_ref']['revision'] = 2,
      (v) => v['health_evidence_ref']['revision'] = 1.0,
      (v) => v['health_evidence_ref']['other'] = 'not accepted',
      (v) => v['verification_note'] = '😀' * 3001,
      (v) => v['verification_note'] = 'Original\rChanged',
      (v) => v['verification_note'] = String.fromCharCode(0xd800),
    ]) {
      final value = copy(original);
      change(value);
      expect(
        () => individualMinijobAssessment(
          value,
          employee,
          '2026-10',
          complete: false,
        ),
        throwsA(isA<ApiException>()),
      );
    }
  });
  test('historical assessment and direct PAP amounts cannot be replaced or converted into the old wrapper', () {
    final b = copy(all['compulsory']), employee = b['employee']['id'] as String;
    for (final change in <void Function(Map<String, dynamic>)>[
      (v) =>
          v['plan']['individual_minijob_assessment']['employee_id'] = 'e' * 32,
      (v) =>
          v['sources']['individual_minijob_assessment']['health_evidence_ref']['revision']++,
      (v) => v['plan']['technical_pap_parameters']['PKV'] = 0,
      (v) => v['sources']['profiles'][0]['profile']['health_insurance'] =
          'private',
      (v) => v['source_contract_version'] = 3.0,
      (v) => v['plan']['claims_component_hash'] = 'e' * 64,
    ]) {
      final value = copy(b['case']);
      change(value);
      expect(
        () => payrollCalculationCaseRecord(value, employee),
        throwsA(isA<ApiException>()),
      );
    }
    for (final change in <void Function(Map<String, dynamic>)>[
      (v) =>
          v['period_details']['tax_assessments'][0]['calculation']['LSTLZZ']++,
      (v) =>
          v['period_details']['tax_assessments'][0]['calculation']['version'] =
              'bmf_2026_standard_factor_period_wrapper_v2',
      (v) => v['net_minor']++,
      (v) => v['employer_flat_tax_minor'] = 1000,
    ]) {
      final value = copy(b['run']['calculation']);
      change(value);
      expect(() => payrollCalculation(value), throwsA(isA<ApiException>()));
    }
  });
  test('identity v2 requires explicit selection and preserves actual insurance and ELStAM source', () {
    final b = copy(all['compulsory']),
        d = copy(b['identity_command']['details']);
    final input = {
      ...d,
      'profile_ref': '${d['profile_id']}@${d['profile_revision']}',
      'identity_scope': 'individual_minijob',
      'tax_allowance_yearly_minor': '0.00',
      'tax_addition_yearly_minor': '0.00',
    };
    final result = payrollAccountDetails('identity', input, {
      'profiles': [copy(b['profile'])],
    });
    expect(result, d);
    payrollAccountRecord(b['identity'], b['employee']['id'], kind: 'identity');
    final malformed = copy(b['identity']);
    malformed['details']['identity_source_schema_version'] = 2.0;
    expect(
      () => payrollAccountRecord(
        malformed,
        b['employee']['id'],
        kind: 'identity',
      ),
      throwsA(isA<ApiException>()),
    );
    expect(
      () => payrollAccountDetails(
        'identity',
        {...input, 'tax_source': 'flat_minijob_evidence'},
        {
          'profiles': [copy(b['profile'])],
        },
      ),
      throwsFormatException,
    );
    final legacy = payrollAccountDetails(
      'identity',
      {...input, 'identity_scope': 'legacy'},
      {
        'profiles': [copy(b['profile'])],
      },
    );
    expect(legacy.containsKey('identity_source_schema_version'), false);
  });
  test(
    'only an explicitly blocked old individual case may change its contract',
    () {
      final b = copy(all['migrated']), old = copy(b['legacy_case']);
      expect(individualMinijobCanConvert(old), true);
      old['plan']['can_calculate'] = true;
      expect(
        () => payrollCalculationCaseInput(
          b['employee']['id'],
          copy(b['sources']),
          values(b),
          previous: old,
        ),
        throwsA(isA<ApiException>()),
      );
    },
  );
  test('lost migrated acceptance keeps original contract and references through fresh rights checks', () async {
    final b = copy(all['migrated']),
        api = MinijobApi(copy(all['migrated']))..lose = true;
    final own = BusinessSession(api: api);
    addTearDown(own.dispose);
    addTearDown(api.dispose);
    await own.load();
    final key = 'payroll-calculation-cases-${api.employee}',
        body = copy(b['case_command'])..remove('request_id');
    await expectLater(
      own.command(
        key,
        '/payroll/calculation-cases',
        body,
        validateResult: payrollCalculationCaseValidator(
          body,
          previous: copy(b['legacy_case']),
          preview: copy(b['case_preview']),
        ),
      ),
      throwsA(isA<ApiException>()),
    );
    api.feature = false;
    await expectLater(
      own.repeatPayrollCalculationCaseCommand(api.employee),
      throwsA(isA<ApiException>()),
    );
    expect(api.sent.length, 1);
    expect(own.pending(key), true);
    api.feature = true;
    api.returnedEmployee = 'e' * 32;
    await expectLater(
      own.repeatPayrollCalculationCaseCommand(api.employee),
      throwsA(isA<ApiException>()),
    );
    expect(api.sent.length, 1);
    api.returnedEmployee = null;
    await own.repeatPayrollCalculationCaseCommand(api.employee);
    expect(api.sent[0], api.sent[1]);
    expect(own.pending(key), false);
  });
  test('lost individual payroll acceptance retains exact original through renewed rights', () async {
    final b = copy(all['compulsory']),
        api = MinijobApi(copy(all['compulsory']))..lose = true;
    final session = BusinessSession(api: api);
    addTearDown(session.dispose);
    addTearDown(api.dispose);
    await session.load();
    final body = copy(b['run_command'])..remove('request_id'),
        key = 'payroll-run-${api.employee}';
    await expectLater(
      session.command(key, '/payroll/runs', body),
      throwsA(isA<ApiException>()),
    );
    api.feature = false;
    await expectLater(
      session.repeatPayrollCommand(api.employee),
      throwsA(isA<ApiException>()),
    );
    expect(api.sent.length, 1);
    expect(session.pending(key), true);
    api.feature = true;
    api.returnedEmployee = 'e' * 32;
    await expectLater(
      session.repeatPayrollCommand(api.employee),
      throwsA(isA<ApiException>()),
    );
    expect(api.sent.length, 1);
    api.returnedEmployee = null;
    api.approve = false;
    await expectLater(
      session.repeatPayrollCommand(api.employee),
      throwsA(isA<ApiException>()),
    );
    expect(api.sent.length, 1);
    api.approve = true;
    await session.repeatPayrollCommand(api.employee);
    expect(api.sent[0], api.sent[1]);
    expect(api.sent[0]['accepted_scope'], individualMinijobScope);
    expect(session.pending(key), false);
  });
  testWidgets(
    'mobile minijob display identifies actual family insurance and explicit old-case reassessment',
    (tester) async {
      tester.view.physicalSize = const Size(390, 844);
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.resetPhysicalSize);
      addTearDown(tester.view.resetDevicePixelRatio);
      final b = copy(all['migrated']),
          api = MinijobApi(copy(all['migrated']))..oldOnly = true;
      final session = BusinessSession(api: api);
      await session.load();
      await tester.pumpWidget(
        MaterialApp(
          home: BusinessPayrollCalculationCasesPage(
            session: session,
            employee: copy(b['employee']),
            initialMonth: '2026-10',
            onOriginal: (_) async {},
            onCalculate: (_) async {},
          ),
        ),
      );
      await tester.pumpAndSettle();
      expect(find.text('Individuellen Minijob belegt prüfen'), findsOneWidget);
      final row = find.text('Abrechnungsfall 2026-10 · Fassung 1');
      await tester.ensureVisible(row);
      await tester.tap(row);
      await tester.pumpAndSettle();
      final convert = find.text(
        'Gesperrten Minijob ausdrücklich neu beurteilen',
      );
      await tester.scrollUntilVisible(
        convert,
        300,
        scrollable: find.byType(Scrollable).first,
      );
      await tester.ensureVisible(convert);
      await tester.pumpAndSettle();
      await tester.tap(convert);
      await tester.pumpAndSettle();
      final editor = tester.widget<BusinessEditor>(find.byType(BusinessEditor));
      expect(
        individualMinijobConfirmations.keys.every(
          (key) => editor.fields.any((field) => field.name == key),
        ),
        true,
      );
      expect(
        individualMinijobEvidence.keys.every(
          (key) => editor.fields.any((field) => field.name == '${key}_id'),
        ),
        true,
      );
      expect(api.sent, isEmpty);
      await tester.pumpWidget(const SizedBox());
      session.dispose();
      api.dispose();
      await tester.pump();
    },
  );
}

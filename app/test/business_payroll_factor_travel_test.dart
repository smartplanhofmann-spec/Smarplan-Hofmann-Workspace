import 'dart:convert';
import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:smartplan_office/api.dart';
import 'package:smartplan_office/business_payroll.dart';
import 'package:smartplan_office/business_payroll_calculation_case_contract.dart';
import 'package:smartplan_office/business_payroll_calculation_cases.dart';
import 'package:smartplan_office/business_session.dart';
import 'package:smartplan_office/business_widgets.dart';

final fixture = jsonDecode(
  File('test/fixtures/payroll_factor_travel.json').readAsStringSync(),
) as Map<String, dynamic>;
Map<String, dynamic> copy(dynamic value) =>
    Map<String, dynamic>.from(jsonDecode(jsonEncode(value)) as Map);
Map<String, dynamic> formValues([Map<String, dynamic>? value]) {
  final command = value ?? fixture['command'], details = command['details'];
  return {
    'month': details['month'],
    'rule_version': payrollFactorTaxfreeTravelRule,
    'period_case_id': details['period_case_ref']['id'],
    for (final entry in {
      'employment_terms_ids': 'employment_terms_refs',
      'profile_ids': 'profile_refs',
      'identity_ids': 'identity_refs',
      'travel_settlement_ids': 'travel_settlement_refs',
      'travel_payment_ids': 'travel_payment_refs',
    }.entries)
      entry.key: [for (final ref in details[entry.value]) ref['id']],
    'segment_events': <dynamic>[],
    'entitlement_case_ids': <String>[],
    'thirty_day_rule': null,
    'policy_id': null,
    'source_file_ids': command['source_file_ids'],
    'verification_note': details['verification_note'],
    if (command['correction_reason'] != null)
      'correction_reason': command['correction_reason'],
  };
}

class FactorTravelApi extends OfficeApi {
  FactorTravelApi() : super(apiVersion: 'v1') {
    token = 'synthetic-factor-travel-native-session';
  }
  bool feature = true, approve = true, lose = false;
  String? returnedEmployee;
  final sent = <Map<String, dynamic>>[];
  final previews = <Map<String, dynamic>>[];
  String get employee => fixture['employee_id'];
  @override
  Future<dynamic> call(String path, [Map<String, dynamic>? body]) async {
    if (path.startsWith('/api/business/capabilities')) {
      return {
        'compatibility_mode': 'business',
        'generation': 1,
        'storage_version': 10,
        'readonly': false,
        'features': [
          'payroll_calculation_cases',
          'german_payroll_2026',
          if (feature) 'payroll_factor_taxfree_travel',
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
    }
    if (path == '/api/me') return {'id': 'a' * 32};
    if (path.startsWith('/api/business/payroll/calculation-cases/sources?')) {
      return {
        ...copy(fixture['sources']),
        'employee_id': returnedEmployee ?? employee,
        'calculation_cases': [copy(fixture['saved'])],
      };
    }
    if (path == '/api/business/payroll/calculation-cases') {
      sent.add(copy(body));
      if (lose) {
        lose = false;
        throw const ApiException(
          0,
          'Synthetic accepted original response lost.',
        );
      }
      return copy(fixture['saved']);
    }
    if (path == '/api/business/payroll/calculation-cases/preview') {
      previews.add(copy(body));
      return copy(fixture['preview']);
    }
    if (path.startsWith('/api/business/payroll/runs?'))
      return {
        'employee_id': employee,
        'items': [copy(fixture['run'])],
      };
    if (path == '/api/business/payroll/runs') {
      sent.add(copy(body));
      if (lose) {
        lose = false;
        throw const ApiException(
          0,
          'Synthetic accepted payroll run response lost.',
        );
      }
      return copy(fixture['run']);
    }
    throw StateError(path);
  }
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  test('real backend fixture preserves v10 source selection, payment proof and exact payroll amounts', () {
    final body = payrollCalculationCaseInput(
      fixture['employee_id'],
      copy(fixture['sources']),
      formValues(),
    );
    expect({
      ...body,
      'preview_hash': fixture['preview']['preview_hash'],
    }, copy(fixture['command'])..remove('request_id'));
    payrollCalculationCasePreview(fixture['preview'], body);
    payrollCalculationCaseValidator({
      ...body,
      'preview_hash': fixture['preview']['preview_hash'],
    }, preview: copy(fixture['preview']))(fixture['saved']);
    expect(
      payrollCalculationCaseRunInput(copy(fixture['saved'])),
      fixture['run_input'],
    );
    payrollCompositeSource(fixture['run_preview'], copy(fixture['run_input']));
    final calculation = payrollCalculation(fixture['run']['calculation']);
    for (final key in [
      'gross_minor',
      'net_minor',
      'payout_minor',
      'individual_wage_tax_minor',
      'employee_social_total_minor',
      'employer_social_total_minor',
    ]) {
      expect(
        calculation[key],
        fixture['v9_base_calculation'][key],
        reason: key,
      );
      expect(
        calculation[key],
        fixture['v8_base_calculation'][key],
        reason: key,
      );
    }
    expect(calculation['travel_expenses_included_in_net'], false);
    expect(calculation['period_details']['travel_paid_minor'], 1400);
  });

  test('payment selection must bind the actual settlement and cannot select unapproved scope', () {
    for (final change in [
      {'travel_payment_ids': <String>[]},
      {'travel_settlement_ids': <String>[]},
      {'profile_ids': <String>[]},
      {'policy_id': 'e' * 32},
      {
        'segment_events': [
          {'kind': 'data_correction'},
        ],
      },
      {
        'entitlement_case_ids': ['e' * 32],
      },
    ]) {
      expect(
        () => payrollCalculationCaseInput(
          fixture['employee_id'],
          copy(fixture['sources']),
          {...formValues(), ...change},
        ),
        throwsA(isA<ApiException>()),
      );
    }
    final wrong = copy(fixture['sources']);
    wrong['travel_payment_proofs'][0]['settlement_ref']['id'] = 'f' * 32;
    expect(
      () => payrollCalculationCaseInput(
        fixture['employee_id'],
        wrong,
        formValues(),
      ),
      throwsA(isA<ApiException>()),
    );
  });

  test('real factor correction preserves the old travel original and changes only the confirmed payroll source', () {
    final command = copy(fixture['correction_case_command']);
    final body = payrollCalculationCaseInput(
      fixture['employee_id'],
      copy(fixture['correction_sources']),
      formValues(command),
      previous: copy(fixture['saved']),
    );
    expect({
      ...body,
      'preview_hash': fixture['correction_case_preview']['preview_hash'],
    }, command..remove('request_id'));
    payrollCalculationCasePreview(fixture['correction_case_preview'], body);
    payrollCalculationCaseValidator(
      {
        ...body,
        'preview_hash': fixture['correction_case_preview']['preview_hash'],
      },
      previous: copy(fixture['saved']),
      preview: copy(fixture['correction_case_preview']),
    )(fixture['correction_case']);
    payrollCalculation(fixture['correction_run']['calculation']);
    expect(fixture['history']['items'].first, fixture['saved']);
    expect(
      fixture['correction_case']['details']['travel_payment_refs'],
      fixture['saved']['details']['travel_payment_refs'],
    );
    expect(
      fixture['correction_run']['calculation']['period_details']['travel_paid_minor'],
      1400,
    );
    expect(
      fixture['correction_run']['calculation']['net_minor'],
      isNot(fixture['run']['calculation']['net_minor']),
    );
  });

  test('history rejects changed payment prefix, cash proof, factor, rule or net additions', () {
    for (final change in <void Function(Map<String, dynamic>)>[
      (v) =>
          v['sources']['travel_sources'][0]['payment_proof']['payments'][0]['amount_minor']++,
      (v) =>
          v['sources']['travel_sources'][0]['payment_proof']['payments'][0]['cash_source_hash'] =
              '',
      (v) => v['sources']['travel_sources'][0]['payment_proof']['payments']
          .clear(),
      (v) =>
          v['sources']['travel_sources'][0]['payment_proof']['cutoff_sequence']++,
      (v) =>
          v['sources']['travel_sources'][0]['payment_proof']['payments'][0]['paid_on'] =
              '2026-09-27',
      (v) => v['plan']['factor_parameters']['profile_ref']['revision']++,
      (v) => v['plan']['earnings'][0]['kind'] = 'one_off',
      (v) => v['plan']['tax_periods'][0]['tax_days'] = 17,
      (v) => v['source_contract_version'] = 1,
      (v) => v['source_contract_version'] = 2.0,
      (v) => v['sources']['source_contract_version'] = 2.0,
    ]) {
      final value = copy(fixture['saved']);
      change(value);
      expect(
        () => payrollCalculationCaseRecord(value, fixture['employee_id']),
        throwsA(isA<ApiException>()),
      );
    }
    for (final change in <void Function(Map<String, dynamic>)>[
      (v) => v['net_minor'] += 1400,
      (v) => v['period_details']['travel']['individual_taxable_payroll_minor'] =
          1400,
      (v) => v['period_details']['travel']['letter_m'] = true,
      (v) {
        v['period_details']['travel_paid_minor'] = 0;
        v['period_details']['travel']['tax_free_external_minor'] = 0;
      },
      (v) => v['period_details']['factor_parameters']['tax_factor'] = '0.75',
      (v) =>
          v['period_details']['tax_calculations'][0]['calculation']['factor'] =
              '0.900',
    ]) {
      final value = copy(fixture['run']['calculation']);
      change(value);
      expect(
        () => payrollCompositeCalculation(value),
        throwsA(isA<ApiException>()),
      );
    }
  });

  test('frozen plan total must equal all original travel payment proofs', () {
    final value = copy(fixture['saved']);
    value['plan']['travel_paid_minor']++;
    expect(
      () => payrollCalculationCaseRecord(value, fixture['employee_id']),
      throwsA(isA<ApiException>()),
    );
  });
  test('retired payment versions remain explicitly bound in the complete source selection', () {
    final sources = copy(fixture['sources']);
    final retired = copy(sources['travel_payment_proofs'][0])
      ..['id'] = 'e' * 32
      ..['content_hash'] = 'd' * 64
      ..['status'] = 'void';
    sources['travel_payment_proofs'].add(retired);
    expect(
      () => payrollCalculationCaseInput(
        fixture['employee_id'],
        sources,
        formValues(),
      ),
      throwsA(isA<ApiException>()),
    );
    final values = formValues();
    values['travel_payment_ids'] = [
      ...values['travel_payment_ids'],
      retired['id'],
    ];
    final body = payrollCalculationCaseInput(
      fixture['employee_id'],
      sources,
      values,
    );
    expect(body['details']['travel_payment_refs'].length, 2);
    expect(body['details']['travel_payment_refs'].last['id'], retired['id']);
  });
  test(
    'frozen plan factor must equal the original selected profile factor',
    () {
      final value = copy(fixture['saved']);
      value['plan']['factor_parameters']['tax_factor'] = '0.900';
      expect(
        () => payrollCalculationCaseRecord(value, fixture['employee_id']),
        throwsA(isA<ApiException>()),
      );
    },
  );
  test('calculation factor must equal its frozen plan factor', () {
    final value = copy(fixture['run']['calculation']);
    value['tax_parameters']['tax_factor'] = '0.900';
    expect(
      () => payrollCompositeCalculation(value),
      throwsA(isA<ApiException>()),
    );
  });

  test('accepted v10 reply loss retries the exact original only after current feature and employee checks', () async {
    final api = FactorTravelApi()..lose = true;
    final own = BusinessSession(api: api);
    addTearDown(own.dispose);
    addTearDown(api.dispose);
    await own.load();
    final key = 'payroll-calculation-cases-${api.employee}';
    final body = copy(fixture['command'])..remove('request_id');
    await expectLater(
      own.command(
        key,
        '/payroll/calculation-cases',
        body,
        validateResult: payrollCalculationCaseValidator(
          body,
          preview: copy(fixture['preview']),
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
    api.returnedEmployee = 'f' * 32;
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

  test('accepted payroll run retains the same payment references across feature loss and exact retry', () async {
    final api = FactorTravelApi()..lose = true;
    final own = BusinessSession(api: api);
    addTearDown(own.dispose);
    addTearDown(api.dispose);
    await own.load();
    final body = copy(fixture['run_command'])..remove('request_id');
    final key = 'payroll-run-${api.employee}';
    await expectLater(
      own.command(key, '/payroll/runs', body),
      throwsA(isA<ApiException>()),
    );
    api.feature = false;
    await expectLater(
      own.repeatPayrollCommand(api.employee),
      throwsA(isA<ApiException>()),
    );
    expect(api.sent.length, 1);
    expect(own.pending(key), true);
    api.feature = true;
    await own.repeatPayrollCommand(api.employee);
    expect(api.sent[0], api.sent[1]);
    expect(own.pending(key), false);
  });

  testWidgets(
    'explicit factor-travel form sends exact chosen original references for preview only',
    (tester) async {
      final api = FactorTravelApi();
      final own = BusinessSession(api: api);
      await own.load();
      await tester.pumpWidget(
        MaterialApp(
          home: BusinessPayrollCalculationCasesPage(
            session: own,
            employee: copy(fixture['sources']['employee']),
            initialMonth: '2026-10',
            onOriginal: (_) async {},
            onCalculate: (_) async {},
          ),
        ),
      );
      await tester.pumpAndSettle();
      final open = find.text(
        'Faktor-Vollmonat mit bezahlter steuerfreier Reise',
      );
      await tester.ensureVisible(open);
      await tester.tap(open);
      await tester.pumpAndSettle();
      final editor = tester.widget<BusinessEditor>(find.byType(BusinessEditor));
      final values = formValues();
      final period = editor.fields.singleWhere(
        (field) => field.name == 'period_case_id',
      );
      await tester.tap(find.byType(DropdownButtonFormField<String>).first);
      await tester.pumpAndSettle();
      await tester.tap(
        find.text(period.choices[values['period_case_id']]!).last,
      );
      await tester.pumpAndSettle();
      for (final name in [
        'employment_terms_ids',
        'profile_ids',
        'identity_ids',
        'travel_settlement_ids',
        'travel_payment_ids',
        'source_file_ids',
      ]) {
        final field = editor.fields.singleWhere((field) => field.name == name);
        for (final id in values[name] as List) {
          final checkbox = find
              .widgetWithText(CheckboxListTile, field.choices[id]!)
              .last;
          await tester.ensureVisible(checkbox);
          await tester.tap(checkbox);
          await tester.pumpAndSettle();
        }
      }
      final note = find.widgetWithText(
        TextFormField,
        'Belegte Prüfung der gesamten Zuordnung',
      );
      await tester.ensureVisible(note);
      await tester.enterText(note, values['verification_note']);
      final confirmation = find.byType(SwitchListTile).last;
      await tester.ensureVisible(confirmation);
      await tester.tap(confirmation);
      await tester.pumpAndSettle();
      final submit = find.text('Faktor-Reisefall unverbindlich prüfen');
      await tester.ensureVisible(submit);
      await tester.tap(submit);
      await tester.pumpAndSettle();
      expect(
        api.previews.single,
        payrollCalculationCasePreviewInput(copy(fixture['command'])),
      );
      expect(api.sent, isEmpty);
      expect(
        find.text('Bereits außerhalb des Lohns erstattet'),
        findsOneWidget,
      );
      expect(tester.takeException(), isNull);
      await tester.pumpWidget(const SizedBox());
      own.dispose();
      api.dispose();
      await tester.pump();
    },
  );

  testWidgets(
    'mobile explicit factor-travel choice and historical paid proof stay separate from payroll',
    (tester) async {
      tester.view.physicalSize = const Size(390, 844);
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.resetPhysicalSize);
      addTearDown(tester.view.resetDevicePixelRatio);
      final api = FactorTravelApi();
      final own = BusinessSession(api: api);
      await own.load();
      await tester.pumpWidget(
        MaterialApp(
          home: BusinessPayrollCalculationCasesPage(
            session: own,
            employee: copy(fixture['sources']['employee']),
            initialMonth: '2026-10',
            onOriginal: (_) async {},
            onCalculate: (_) async {},
          ),
        ),
      );
      await tester.pumpAndSettle();
      expect(
        find.text('Faktor-Vollmonat mit bezahlter steuerfreier Reise'),
        findsOneWidget,
      );
      final item = find.text('Abrechnungsfall 2026-10 · Fassung 1');
      await tester.ensureVisible(item);
      await tester.tap(item);
      await tester.pumpAndSettle();
      expect(find.text('0,753'), findsOneWidget);
      expect(
        find.text('Bereits außerhalb des Lohns erstattet'),
        findsOneWidget,
      );
      expect(find.text('Belegte Reiseerstattung'), findsOneWidget);
      expect(tester.takeException(), isNull);
      await tester.pumpWidget(const SizedBox());
      own.dispose();
      api.dispose();
      await tester.pump();
    },
  );
}

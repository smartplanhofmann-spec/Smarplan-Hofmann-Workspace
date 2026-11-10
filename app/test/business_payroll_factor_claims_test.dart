import 'dart:convert';
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:flutter/material.dart';
import 'package:smartplan_office/api.dart';
import 'package:smartplan_office/business_session.dart';
import 'package:smartplan_office/business_widgets.dart';
import 'package:smartplan_office/business_payroll_calculation_cases.dart';
import 'package:smartplan_office/business_payroll.dart';
import 'package:smartplan_office/business_payroll_calculation_case_contract.dart';

final f = jsonDecode(
  File('test/fixtures/payroll_factor_claims.json').readAsStringSync(),
) as Map<String, dynamic>;
Map<String, dynamic> copy(dynamic v) =>
    Map<String, dynamic>.from(jsonDecode(jsonEncode(v)) as Map);
Map<String, dynamic> values() {
  final d = f['case_command']['details'];
  return {
    'rule_version': payrollFactorClaimsRule,
    'month': d['month'],
    'period_case_id': d['period_case_ref']['id'],
    for (final e in {
      'employment_terms_ids': 'employment_terms_refs',
      'profile_ids': 'profile_refs',
      'identity_ids': 'identity_refs',
      'entitlement_case_ids': 'entitlement_case_refs',
    }.entries)
      e.key: [for (final ref in d[e.value]) ref['id']],
    'source_file_ids': f['case_command']['source_file_ids'],
    'segment_events': [],
    'travel_settlement_ids': [],
    'verification_note': d['verification_note'],
  };
}

void main() {
  test('actual hourly holiday original binds paid absence, zero worked hours and independent XML tax', () {
    final h = copy(f['hourly']), id = h['employee']['id'] as String;
    payrollCalculationCaseSources(h['sources'], id, '2026-10');
    payrollCalculationCasePreview(h['case_preview'], copy(h['case_input']));
    payrollCalculationCaseValidator(
      copy(h['case_command']),
      preview: copy(h['case_preview']),
    )(h['case']);
    payrollCompositeSource(h['run_preview'], copy(h['run_input']));
    payrollPreview(h['run_preview'], copy(h['run_input']));
    payrollFactorClaimsRunHashes(copy(h['run']));
    expect(h['period']['plan']['gross_minor'], 0);
    expect(h['run']['calculation']['gross_minor'], 320000);
    expect(h['run']['calculation']['individual_wage_tax_minor'], 25391);
    expect(
      h['case']['sources']['period_case']['sources']['preparation']['snapshot']['net_work_seconds'],
      0,
    );
  });

  for (final run in [false, true])
    test(
      'new ${run ? 'run' : 'case'} without its own negotiated feature sends no POST',
      () async {
        final api = ClaimsApi()..feature = false;
        final session = BusinessSession(api: api);
        addTearDown(session.dispose);
        addTearDown(api.dispose);
        await session.load();
        final employee = f['employee']['id'] as String;
        final key = run
            ? 'payroll-run-$employee'
            : 'payroll-calculation-cases-$employee';
        final command = copy(run ? f['run_command'] : f['case_command'])
          ..remove('request_id');
        await expectLater(
          session.command(
            key,
            run ? '/payroll/runs' : '/payroll/calculation-cases',
            command,
          ),
          throwsA(isA<ApiException>()),
        );
        expect(api.sent, isEmpty);
        expect(session.pending(key), false);
      },
    );

  for (final run in [false, true])
    test(
      'original ${run ? 'run' : 'case'} retries only with its own current feature and rights',
      () async {
        final api = ClaimsApi()..lose = true;
        final session = BusinessSession(api: api);
        addTearDown(session.dispose);
        addTearDown(api.dispose);
        await session.load();
        final employee = f['employee']['id'] as String;
        final key = run
            ? 'payroll-run-$employee'
            : 'payroll-calculation-cases-$employee';
        final command = copy(run ? f['run_command'] : f['case_command'])
          ..remove('request_id');
        await expectLater(
          session.command(
            key,
            run ? '/payroll/runs' : '/payroll/calculation-cases',
            command,
          ),
          throwsA(isA<ApiException>()),
        );
        api.feature = false;
        await expectLater(
          run
              ? session.repeatPayrollCommand(employee)
              : session.repeatPayrollCalculationCaseCommand(employee),
          throwsA(isA<ApiException>()),
        );
        expect(api.sent.length, 1);
        expect(session.pending(key), true);
        api.feature = true;
        api.approve = false;
        await expectLater(
          run
              ? session.repeatPayrollCommand(employee)
              : session.repeatPayrollCalculationCaseCommand(employee),
          throwsA(isA<ApiException>()),
        );
        expect(api.sent.length, 1);
        api.approve = true;
        await (run
            ? session.repeatPayrollCommand(employee)
            : session.repeatPayrollCalculationCaseCommand(employee));
        expect(api.sent[1], api.sent[0]);
        expect(session.pending(key), false);
      },
    );
  testWidgets(
    'only the claims feature exposes the full factor and P4 original selection',
    (tester) async {
      final api = ClaimsApi();
      final own = BusinessSession(api: api);
      await own.load();
      await tester.pumpWidget(
        MaterialApp(
          home: BusinessPayrollCalculationCasesPage(
            session: own,
            employee: copy(f['employee']),
            initialMonth: '2026-10',
            onOriginal: (_) async {},
            onCalculate: (_) async {},
          ),
        ),
      );
      await tester.pumpAndSettle();
      final open = find.text('Faktor-Monat mit belegten Lohnansprüchen');
      await tester.ensureVisible(open);
      await tester.tap(open);
      await tester.pumpAndSettle();
      final editor = tester.widget<BusinessEditor>(find.byType(BusinessEditor));
      final v = values();
      expect(
        editor.fields.any(
          (e) =>
              e.name == 'travel_settlement_ids' ||
              e.name == 'travel_payment_ids' ||
              e.name == 'event_count',
        ),
        false,
      );
      final period = editor.fields.singleWhere(
        (e) => e.name == 'period_case_id',
      );
      await tester.tap(find.byType(DropdownButtonFormField<String>).first);
      await tester.pumpAndSettle();
      await tester.tap(find.text(period.choices[v['period_case_id']]!).last);
      await tester.pumpAndSettle();
      for (final name in [
        'employment_terms_ids',
        'profile_ids',
        'identity_ids',
        'source_file_ids',
      ]) {
        final field = editor.fields.singleWhere((e) => e.name == name);
        for (final id in v[name] as List) {
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
      await tester.enterText(note, v['verification_note']);
      final confirm = find.byType(SwitchListTile).last;
      await tester.ensureVisible(confirm);
      await tester.tap(confirm);
      await tester.pumpAndSettle();
      final submit = find.text('Faktor-Anspruchsfall unverbindlich prüfen');
      await tester.ensureVisible(submit);
      await tester.tap(submit);
      await tester.pumpAndSettle();
      expect(
        api.previews.single,
        payrollCalculationCasePreviewInput(copy(f['case_command'])),
      );
      expect(api.sent, isEmpty);
      expect(tester.takeException(), isNull);
      await tester.pumpWidget(const SizedBox());
      own.dispose();
      api.dispose();
      await tester.pump();
    },
  );

  final id = f['employee']['id'] as String;
  test('actual factor/P4 command, immutable case and run independently bind the whole snapshot', () {
    payrollCalculationCaseSources(f['sources'], id, '2026-10');
    final body = payrollCalculationCaseInput(id, copy(f['sources']), values());
    final command = copy(f['case_command'])..remove('request_id');
    expect({
      ...body,
      'preview_hash': f['case_preview']['preview_hash'],
    }, command);
    payrollCalculationCasePreview(f['case_preview'], body);
    payrollCalculationCaseValidator(command, preview: copy(f['case_preview']))(
      f['case'],
    );
    expect(payrollCalculationCaseRunInput(copy(f['case'])), f['run_input']);
    payrollCompositeSource(f['run_preview'], copy(f['run_input']));
    payrollPreview(f['run_preview'], copy(f['run_input']));
    payrollFactorClaimsRunHashes(copy(f['run']));
    expect(f['run']['calculation']['individual_wage_tax_minor'], 43091);
    expect(f['run']['calculation']['employee_contributions']['care'], 10064);
    expect(f['run']['calculation']['net_minor'], 285054);
  });
  test('source selection rejects missing claims, duplicates, partial month and extra travel', () {
    for (final alter in <void Function(Map<String, dynamic>)>[
      (v) => v['entitlement_case_ids'] = [],
      (v) => v['entitlement_case_ids'].add(v['entitlement_case_ids'][0]),
      (v) => v['travel_settlement_ids'] = [f['claim']['id']],
      (v) => v['thirty_day_rule'] = 'actual_days_capped_per_claim',
      (v) => v['source_file_ids'] = [],
      (v) => v['period_case_id'] = f['claim']['id'],
    ]) {
      final v = values();
      alter(v);
      expect(
        () => payrollCalculationCaseInput(id, copy(f['sources']), v),
        throwsException,
      );
    }
    final s = copy(f['sources']);
    s['factor_period_facts'][0]['plan']['social_periods'][0]['full_month'] =
        false;
    expect(() => payrollCalculationCaseInput(id, s, values()), throwsException);
  });
  test('independent hashes reject substituted source bytes, plan, rounding method and preview', () {
    for (final alter in <void Function(Map<String, dynamic>)>[
      (v) => v['sources']['entitlements'][0]['details']['verification_note'] +=
          ' changed',
      (v) => v['plan']['gross_minor']++,
      (v) => v['plan']['factor_parameters']['tax_factor'] = '0.900',
      (v) => v['plan']['care_contribution_method'] = 'ONE_STEP',
      (v) => v['plan']['plan_hash'] = '0' * 64,
      (v) => v['preview_hash'] = '1' * 64,
    ]) {
      final v = copy(f['case']);
      alter(v);
      expect(() => payrollFactorClaimsCaseHashes(v), throwsException);
    }
    for (final alter in <void Function(Map<String, dynamic>)>[
      (v) => v['calculation']['net_minor']++,
      (v) => v['source']['profile']['profile']['tax_factor'] = '0.900',
      (v) => v['preview_hash'] = '0' * 64,
    ]) {
      final v = copy(f['run']);
      alter(v);
      expect(() => payrollFactorClaimsRunHashes(v), throwsException);
    }
  });
}

class ClaimsApi extends OfficeApi {
  ClaimsApi() : super(apiVersion: 'v1') {
    token = 'synthetic-factor-claim-session';
  }
  bool feature = true, lose = false, approve = true;
  final sent = <Map<String, dynamic>>[], previews = <Map<String, dynamic>>[];
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
          if (feature) payrollFactorClaimsFeature,
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
      return copy(f['sources']);
    if (path == '/api/business/payroll/calculation-cases/preview') {
      previews.add(copy(body));
      return copy(f['case_preview']);
    }
    if (path.startsWith('/api/business/payroll/runs?'))
      return {
        'employee_id': f['employee']['id'],
        'items': [copy(f['run'])],
      };
    if (path == '/api/business/payroll/calculation-cases' ||
        path == '/api/business/payroll/runs') {
      sent.add(copy(body));
      if (lose) {
        lose = false;
        throw const ApiException(0, 'Synthetic accepted reply lost');
      }
      return copy(path.endsWith('/runs') ? f['run'] : f['case']);
    }
    throw StateError('Unexpected factor-claim path: $path');
  }
}

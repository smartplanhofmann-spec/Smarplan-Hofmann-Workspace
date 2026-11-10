import 'dart:convert';
import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:smartplan_office/api.dart';
import 'package:smartplan_office/business_session.dart';
import 'package:smartplan_office/business_widgets.dart';
import 'package:smartplan_office/business_payroll.dart';
import 'package:smartplan_office/business_payroll_calculation_cases.dart';
import 'package:smartplan_office/business_payroll_calculation_case_contract.dart';

final Map<String, dynamic> f = (() {
  final root = jsonDecode(
    File('test/fixtures/payroll_factor_transition_period.json')
        .readAsStringSync(),
  );
  final row = Map<String, dynamic>.from(root['cases'].last as Map);
  return {...row, 'case_input': row['input'], 'sources_before': row['sources']};
})();
Map<String, dynamic> copy(dynamic v) =>
    Map<String, dynamic>.from(jsonDecode(jsonEncode(v)) as Map);
Map<String, dynamic> values() {
  final d = f['case_input']['details'];
  return {
    'rule_version': payrollFactorTransitionPeriodRule,
    'month': d['month'],
    'period_case_id': d['period_case_ref']['id'],
    for (final entry in {
      'employment_terms_ids': 'employment_terms_refs',
      'profile_ids': 'profile_refs',
      'identity_ids': 'identity_refs',
    }.entries)
      entry.key: [for (final r in d[entry.value]) r['id']],
    'source_file_ids': f['case_input']['source_file_ids'],
    'factor_transition_period_assessment': copy(
      d['factor_transition_period_assessment'],
    ),
    'verification_note': d['verification_note'],
  };
}

void main() {
  final id = f['employee']['id'] as String;
  test('actual factor/Midijob originals, partial plan and financial component bind independently', () {
    payrollCalculationCaseSources(f['sources_before'], id, '2026-10');
    final body = payrollCalculationCaseInput(
      id,
      copy(f['sources_before']),
      values(),
    );
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
    payrollFactorTransitionPeriodRunHashes(copy(f['run']));
    expect(f['run']['calculation']['individual_wage_tax_minor'], 3740);
    expect(f['run']['calculation']['employee_social_total_minor'], 24649);
    expect(f['run']['calculation']['net_minor'], 84944);
  });
  test('native source choice refuses omitted evidence, other requested movements and foreign period', () {
    for (final alter in <void Function(Map<String, dynamic>)>[
      (v) => v['source_file_ids'] = [],
      (v) => v['profile_ids'] = [],
      (v) => v['segment_events'] = [{}],
      (v) => v['entitlement_case_ids'] = [id],
      (v) => v['travel_settlement_ids'] = [id],
      (v) => v['factor_transition_period_assessment']['employee_id'] = 'f' * 32,
      (v) =>
          v['factor_transition_period_assessment']['transition_assessment']['forecast_months'] =
              11,
      (v) =>
          v['factor_transition_period_assessment']['forecast_evidence_ref']['content_hash'] =
              'f' * 64,
    ]) {
      final v = values();
      alter(v);
      expect(
        () => payrollCalculationCaseInput(id, copy(f['sources_before']), v),
        throwsException,
      );
    }
  });
  test('independent full hashes refuse replaced factor, forecast or financial projection', () {
    for (final alter in <void Function(Map<String, dynamic>)>[
      (v) =>
          v['sources']['factor_transition_period_assessment']['transition_assessment']['note'] +=
              ' changed',
      (v) => v['plan']['gross_minor']++,
      (v) => v['plan']['factor_parameters']['tax_factor'] = '0.900',
      (v) =>
          v['plan']['factor_transition_period_component']['individual_wage_tax_minor']++,
    ]) {
      final v = copy(f['case']);
      alter(v);
      expect(() => payrollFactorTransitionPeriodCaseHashes(v), throwsException);
    }
    final v = copy(f['run']);
    v['calculation']['net_minor']++;
    expect(() => payrollFactorTransitionPeriodRunHashes(v), throwsException);
  });
  for (final run in [false, true]) {
    test(
      'new ${run ? 'run' : 'case'} requires its own fresh feature before any write',
      () async {
        final api = FactorTransitionPeriodApi()..feature = false;
        final session = BusinessSession(api: api);
        addTearDown(session.dispose);
        addTearDown(api.dispose);
        await session.load();
        final body = copy(run ? f['run_command'] : f['case_command'])
          ..remove('request_id');
        await expectLater(
          session.command(
            '${run ? 'payroll-run-' : 'payroll-calculation-cases-'}$id',
            run ? '/payroll/runs' : '/payroll/calculation-cases',
            body,
          ),
          throwsA(isA<ApiException>()),
        );
        expect(api.sent, isEmpty);
      },
    );
    test(
      'original ${run ? 'run' : 'case'} survives lost reply and refuses revoked feature or approval',
      () async {
        final api = FactorTransitionPeriodApi()..lose = true;
        final session = BusinessSession(api: api);
        addTearDown(session.dispose);
        addTearDown(api.dispose);
        await session.load();
        final key = '${run ? 'payroll-run-' : 'payroll-calculation-cases-'}$id';
        final body = copy(run ? f['run_command'] : f['case_command'])
          ..remove('request_id');
        await expectLater(
          session.command(
            key,
            run ? '/payroll/runs' : '/payroll/calculation-cases',
            body,
          ),
          throwsA(isA<ApiException>()),
        );
        api.feature = false;
        await expectLater(
          run
              ? session.repeatPayrollCommand(id)
              : session.repeatPayrollCalculationCaseCommand(id),
          throwsA(isA<ApiException>()),
        );
        expect(api.sent.length, 1);
        expect(session.pending(key), true);
        api.feature = true;
        api.approve = false;
        await expectLater(
          run
              ? session.repeatPayrollCommand(id)
              : session.repeatPayrollCalculationCaseCommand(id),
          throwsA(isA<ApiException>()),
        );
        expect(api.sent.length, 1);
        api.approve = true;
        await (run
            ? session.repeatPayrollCommand(id)
            : session.repeatPayrollCalculationCaseCommand(id));
        expect(api.sent[1], api.sent[0]);
        expect(session.pending(key), false);
      },
    );
  }
  for (final width in [1100.0, 390.0]) {
    testWidgets(
      'real native $width px form submits the actual chosen originals and explicit partial-period prognosis',
      (tester) async {
        await tester.binding.setSurfaceSize(Size(width, 844));
        addTearDown(() => tester.binding.setSurfaceSize(null));
        final backend = FactorTransitionPeriodApi();
        final own = BusinessSession(api: backend);
        try {
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
          final open = find.text(
            'Midijob-Teilmonat mit belegtem ELStAM-Faktor',
          );
          await tester.ensureVisible(open);
          await tester.tap(open);
          await tester.pumpAndSettle();
          final editor = tester.widget<BusinessEditor>(
                find.byType(BusinessEditor),
              ),
              v = values();
          for (final name in [
            'employment_terms_ids',
            'profile_ids',
            'identity_ids',
            'source_file_ids',
          ]) {
            final field = editor.fields.singleWhere((x) => x.name == name);
            for (final selected in v[name] as List) {
              final tile = find
                  .widgetWithText(CheckboxListTile, field.choices[selected]!)
                  .last;
              await tester.ensureVisible(tile);
              await tester.tap(tile);
              await tester.pumpAndSettle();
            }
          }
          Future<void> select(String name, String id, bool first) async {
            final field = editor.fields.singleWhere((x) => x.name == name);
            final dropdown = first
                ? find.byType(DropdownButtonFormField<String>).first
                : find.byType(DropdownButtonFormField<String>).last;
            await tester.ensureVisible(dropdown);
            await tester.tap(dropdown);
            await tester.pumpAndSettle();
            await tester.tap(find.text(field.choices[id]!).last);
            await tester.pumpAndSettle();
          }

          await select('period_case_id', v['period_case_id'], true);
          final review = v['factor_transition_period_assessment'],
              forecast = review['transition_assessment'];
          await select(
            'forecast_file_id',
            review['forecast_evidence_ref']['id'],
            false,
          );
          final raw = {
            'valid_from': review['valid_from'],
            'valid_to': review['valid_to'],
            'declaration_date': review['declaration_date'],
            'assessed_on': forecast['assessed_on'],
            'regular_monthly_gross': '2000.00',
            'forecast_months': '12',
            'forecast_note': forecast['note'],
            'assessment_note': review['verification_note'],
            'verification_note': v['verification_note'],
          };
          for (final entry in raw.entries) {
            final field = editor.fields.singleWhere((x) => x.name == entry.key);
            final input = find.widgetWithText(TextFormField, field.label);
            await tester.ensureVisible(input);
            await tester.enterText(input, '${entry.value}');
          }
          for (final name in [
            'sole_employment_confirmed',
            'fixed_monthly_contract_confirmed',
            'contractual_30_days_confirmed',
            'no_foreseeable_one_off_confirmed',
          ]) {
            final field = editor.fields.singleWhere((x) => x.name == name),
                toggle = find.widgetWithText(
                  SwitchListTile,
                  editor.fields.singleWhere((x) => x.name == name).label,
                );
            expect(field.type, BusinessInput.toggle);
            await tester.ensureVisible(toggle);
            await tester.tap(toggle);
            await tester.pumpAndSettle();
          }
          final submit = find.text(
            'Faktor-Midijob-Teilmonat unverbindlich prüfen',
          );
          await tester.ensureVisible(submit);
          await tester.tap(submit);
          await tester.pumpAndSettle();
          expect(backend.previews.length, 1);
          expect(backend.previews.single, f['case_input']);
        } finally {
          await tester.pumpWidget(const SizedBox.shrink());
          own.dispose();
          backend.dispose();
        }
      },
    );
  }
}

class FactorTransitionPeriodApi extends OfficeApi {
  FactorTransitionPeriodApi() : super(apiVersion: 'v1') {
    token = 'synthetic-factor-midijob-session';
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
          if (feature) payrollFactorTransitionPeriodFeature,
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
      return copy(f['sources_before']);
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
    throw StateError('Unexpected factor/Midijob path: $path');
  }
}

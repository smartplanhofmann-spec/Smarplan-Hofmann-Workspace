import 'dart:convert';
import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:smartplan_office/api.dart';
import 'package:smartplan_office/business_session.dart';
import 'package:smartplan_office/business_payroll.dart';

final f = jsonDecode(
  File('test/fixtures/payroll_transition.json').readAsStringSync(),
) as Map<String, dynamic>;
Map<String, dynamic> copy(dynamic v) =>
    Map<String, dynamic>.from(jsonDecode(jsonEncode(v)) as Map);
Map<String, dynamic> values() {
  final p = copy(f['original']['profile']['profile']);
  for (final key in [
    'has_children',
    'u1_required',
    'minijob_rv_exempt',
    'pension_other_compulsory',
  ])
    p[key] = p[key] == true ? 'yes' : 'no';
  p.remove('transition_assessment');
  return {
    ...p,
    'regular_tax_scope': 'standard',
    'annual_gross': '12000',
    'tax_allowance_monthly_minor': '0',
    'tax_addition_monthly_minor': '0',
    'transition_scope': 'monthly',
    'transition_assessed_on': '2026-01-01',
    'transition_regular_monthly': '1000',
    'transition_forecast_months': '12',
    'transition_one_off': 'no',
    'transition_note':
        f['original']['profile']['profile']['transition_assessment']['note'],
  };
}

class TransitionApi extends OfficeApi {
  TransitionApi() : super(apiVersion: 'v1') {
    token = 'synthetic-transition';
  }
  bool read = true;
  @override
  Future<dynamic> call(String path, [Map<String, dynamic>? body]) async {
    if (path.startsWith('/api/business/capabilities'))
      return {
        'compatibility_mode': 'business',
        'generation': 1,
        'storage_version': 10,
        'readonly': false,
        'features': ['german_payroll_2026'],
        'capabilities': ['business_payroll'],
        'permissions': [
          if (read) 'personnel.read',
          'personnel.write',
          'personnel.approve',
          'personnel.export',
        ],
      };
    if (path == '/api/me') return {'id': 'a' * 32};
    if (path == '/api/business/employees') return [f['employee']];
    if (path.startsWith('/api/business/payroll/rules')) return {'year': 2026};
    final items = path.contains('/payroll/profiles?')
        ? [f['original']['profile']]
        : path.contains('/payroll/runs?')
        ? [f['run']]
        : path.contains('/personnel/files?')
        ? [f['original']['file']]
        : path.contains('/personnel/payroll-preparations?')
        ? [f['original']['preparation']]
        : null;
    if (items != null)
      return {'employee_id': f['employee']['id'], 'items': items};
    throw StateError(path);
  }
}

void main() {
  test(
    'forecast is explicit complete and never inferred from actual gross',
    () {
      expect(
        payrollProfileInput(values()),
        f['original']['profile']['profile'],
      );
      expect(
        payrollProfileInput({...values(), 'transition_scope': 'none'})
            .containsKey('transition_assessment'),
        false,
      );
      for (final patch in [
        {'transition_scope': ''},
        {'regular_tax_scope': 'social_only'},
        {'transition_regular_monthly': '603'},
        {'transition_regular_monthly': '2000.01'},
        {'transition_forecast_months': ''},
        {'transition_one_off': ''},
        {'transition_assessed_on': ''},
        {'transition_note': ''},
        {'annual_gross': '12001'},
      ])
        expect(
          () => payrollProfileInput({...values(), ...patch}),
          throwsFormatException,
        );
      expect(
        payrollProfileInput({
          ...values(),
          'transition_one_off': 'yes',
        })['transition_assessment']['foreseeable_one_off_payments'],
        true,
      );
    },
  );
  test('transition results retain exact complete PAP and contribution sums through tax-aware correction', () {
    payrollCalculation(f['run']['calculation']);
    payrollPreview(f['preview'], copy(f['original']['inputs']));
    payrollReceiptValidator(copy(f['command']), preview: copy(f['preview']))(
      f['run'],
    );
    payrollReceiptValidator(
      copy(f['corrected_command']),
      preview: copy(f['corrected_preview']),
      previous: copy(f['run']),
    )(f['corrected_run']);
    expect(f['run']['calculation']['net_minor'], 87467);
    expect(f['corrected_run']['calculation']['net_minor'], 88121);
    expect(f['corrected_run']['delta']['employer_social_total_minor'], 0);
  });
  test('actual pay below or above forecast band retains status; foreseeable one-off remains unsupported', () {
    payrollCalculation(f['below']);
    payrollCalculation(f['above']);
    payrollCalculation(f['blocked']);
    expect(f['below']['scope'], 'regular_transition_monthly');
    expect(f['below']['transition']['employee_assessment_minor'], 0);
    expect(f['above']['transition']['regime'], 'above_upper_limit');
    expect(f['blocked']['net_minor'], null);
    expect(f['blocked']['transition'], null);
    expect(
      () => payrollCalculation({
        ...copy(f['blocked']),
        'transition': f['run']['calculation']['transition'],
      }),
      throwsA(isA<ApiException>()),
    );
  });
  test('missing contribution branch or forged care adjustment never becomes displayed payroll', () {
    final bad = copy(f['run']['calculation']);
    bad['transition']['care_adjustments']['children_discount_minor']++;
    expect(() => payrollCalculation(bad), throwsA(isA<ApiException>()));
    final missing = copy(f['run']['calculation']);
    missing['transition']['branch_bases'].remove('care');
    expect(() => payrollCalculation(missing), throwsA(isA<ApiException>()));
  });
  testWidgets(
    'transition profile and contribution bases render at390px and disappear on read revocation',
    (tester) async {
      tester.view.physicalSize = const Size(390, 844);
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.resetPhysicalSize);
      addTearDown(tester.view.resetDevicePixelRatio);
      final api = TransitionApi(), s = BusinessSession(api: api);
      await s.load();
      await tester.pumpWidget(
        MaterialApp(
          home: BusinessPayrollPage(session: s, employee: copy(f['employee'])),
        ),
      );
      await tester.pumpAndSettle();
      await tester.scrollUntilVisible(
        find.text('Belegter Übergangsbereich · Vollmonat und PAP 2026'),
        400,
        scrollable: find.byType(Scrollable).first,
      );
      expect(
        find.text('Belegter Übergangsbereich · Vollmonat und PAP 2026'),
        findsOneWidget,
      );
      final basis = find.text('Prognose und Beitragsbemessung');
      await tester.pumpAndSettle();
      await tester.scrollUntilVisible(
        basis.hitTestable(),
        400,
        scrollable: find.byType(Scrollable).first,
      );
      await tester.pumpAndSettle();
      await tester.tap(basis);
      await tester.pumpAndSettle();
      expect(find.text('Arbeitnehmerbemessungsgrundlage'), findsOneWidget);
      expect(tester.takeException(), isNull);
      api.read = false;
      await s.load();
      await tester.pumpAndSettle();
      expect(find.text('Arbeitnehmerbemessungsgrundlage'), findsNothing);
      await tester.pumpWidget(const SizedBox.shrink());
      s.dispose();
    },
  );
}

import 'dart:convert';
import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:smartplan_office/api.dart';
import 'package:smartplan_office/business_payroll_calculation_case_contract.dart';
import 'package:smartplan_office/business_payroll_calculation_cases.dart';
import 'package:smartplan_office/business_session.dart';

final fixture = jsonDecode(
  File('test/fixtures/payroll_calculation_cases.json').readAsStringSync(),
) as Map<String, dynamic>;
Map<String, dynamic> copy(dynamic v) =>
    Map<String, dynamic>.from(jsonDecode(jsonEncode(v)) as Map);

class CasesApi extends OfficeApi {
  CasesApi() : super(apiVersion: 'v1') {
    token = 'synthetic-payroll-cases';
  }
  String get employee => fixture['command']['employee_id'];
  bool read = true,
      approve = true,
      sourceApprove = true,
      paused = false,
      lose = false;
  String? sourceEmployee, sourceMonth;
  final sent = <Map<String, dynamic>>[];
  Map<String, dynamic>? accepted;
  int previews = 0;
  @override
  Future<dynamic> call(String path, [Map<String, dynamic>? body]) async {
    if (path.startsWith('/api/business/capabilities'))
      return {
        'compatibility_mode': 'business',
        'generation': 1,
        'storage_version': 10,
        'readonly': false,
        'features': ['payroll_calculation_cases'],
        'capabilities': ['business_payroll_calculation_cases'],
        'permissions': [
          if (read) 'personnel.read',
          if (approve) 'personnel.approve',
        ],
        'organization': {
          'modules': {
            'personnel': {'enabled': !paused, 'visible': true},
          },
        },
      };
    if (path == '/api/me') return {'id': 'a' * 32};
    if (path.startsWith('/api/business/payroll/calculation-cases/sources?'))
      return {
        ...copy(fixture['sources']),
        'employee_id': sourceEmployee ?? employee,
        'month': sourceMonth ?? '2026-10',
        'calculation_cases': [accepted ?? copy(fixture['saved'])],
        'can_approve': sourceApprove,
        'writes_enabled': !paused,
      };
    if (path == '/api/business/payroll/calculation-cases/preview') {
      previews++;
      return copy(fixture['preview']);
    }
    if (path == '/api/business/payroll/calculation-cases') {
      sent.add(copy(body));
      accepted ??= {
        ...copy(fixture['saved']),
        if (body!['revision'] == 1) ...{
          'revision': 2,
          'previous_hash': fixture['saved']['content_hash'],
          'content_hash': 'e' * 64,
          'correction_reason': body['correction_reason'],
        },
      };
      if (lose) {
        lose = false;
        throw const ApiException(
          0,
          'Angenommene Antwort synthetisch verloren.',
        );
      }
      return copy(accepted);
    }
    if (path.endsWith('/history'))
      return {
        'items': [
          copy(fixture['saved']),
          if (accepted != null && accepted!['revision'] == 2) copy(accepted),
        ],
      };
    throw StateError(path);
  }
}

Future<void> tapVisible(WidgetTester t, Finder f) async {
  if (f.evaluate().isEmpty) {
    await t.scrollUntilVisible(
      f,
      250,
      scrollable: find.byType(Scrollable).first,
    );
  }
  await t.ensureVisible(f);
  await t.pumpAndSettle();
  await t.tap(f);
  await t.pumpAndSettle();
}

Future<void> mount(
  WidgetTester t,
  CasesApi a,
  BusinessSession s, {
  Future<void> Function(Map<String, dynamic>)? onCalculate,
}) async {
  await s.load();
  await t.pumpWidget(
    MaterialApp(
      home: BusinessPayrollCalculationCasesPage(
        session: s,
        employee: copy(fixture['sources']['employee']),
        initialMonth: '2026-10',
        onOriginal: (_) async {},
        onCalculate: onCalculate ?? (_) async {},
      ),
    ),
  );
  await t.pumpAndSettle();
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  testWidgets('absence earnings show the exact nonconsecutive claim dates', (
    t,
  ) async {
    final plan = copy(fixture['saved']['plan']);
    plan['earnings'] = [
      {
        'kind': 'vacation',
        'days': ['2026-10-19', '2026-10-21'],
        'claim_dates': ['2026-10-19', '2026-10-21'],
        'gross_minor': 24000,
      },
      {
        'kind': 'sickness',
        'days': ['2026-10-23'],
        'claim_dates': ['2026-10-23'],
        'gross_minor': 12000,
      },
    ];
    await t.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: SingleChildScrollView(
            child: PayrollCalculationCasePlanView(plan: plan),
          ),
        ),
      ),
    );
    expect(find.text('Urlaubsentgelt'), findsOneWidget);
    expect(find.text('19.10.2026, 21.10.2026 · 240,00 €'), findsOneWidget);
    expect(find.text('Entgeltfortzahlung bei Krankheit'), findsOneWidget);
    expect(find.text('23.10.2026 · 120,00 €'), findsOneWidget);
    expect(t.takeException(), isNull);
  });

  test(
    'actual source3 receipt survives pause with original body and validator',
    () async {
      final a = CasesApi()..lose = true, s = BusinessSession(api: a);
      addTearDown(s.dispose);
      addTearDown(a.dispose);
      await s.load();
      final b = copy(fixture['command'])..remove('request_id'),
          key = 'payroll-calculation-cases-${a.employee}';
      await expectLater(
        s.command(
          key,
          '/payroll/calculation-cases',
          b,
          validateResult: payrollCalculationCaseValidator(
            b,
            preview: copy(fixture['preview']),
          ),
        ),
        throwsA(isA<ApiException>()),
      );
      b['details']['verification_note'] = 'Later editor text';
      a.paused = true;
      await s.repeatPayrollCalculationCaseCommand(a.employee);
      expect(a.sent.length, 2);
      expect(a.sent.first, a.sent.last);
      expect(s.pending(key), false);
    },
  );
  test('source3 retry requires fresh person month and approval before another POST', () async {
    final a = CasesApi()..lose = true, s = BusinessSession(api: a);
    addTearDown(s.dispose);
    addTearDown(a.dispose);
    await s.load();
    final b = copy(fixture['command'])..remove('request_id'),
        key = 'payroll-calculation-cases-${a.employee}';
    await expectLater(
      s.command(key, '/payroll/calculation-cases', b),
      throwsA(isA<ApiException>()),
    );
    a.approve = false;
    await expectLater(
      s.repeatPayrollCalculationCaseCommand(a.employee),
      throwsA(isA<ApiException>().having((e) => e.status, 'rights', 403)),
    );
    a.approve = true;
    a.sourceApprove = false;
    await expectLater(
      s.repeatPayrollCalculationCaseCommand(a.employee),
      throwsA(
        isA<ApiException>().having((e) => e.status, 'source rights', 403),
      ),
    );
    a.sourceApprove = true;
    a.sourceEmployee = 'f' * 32;
    await expectLater(
      s.repeatPayrollCalculationCaseCommand(a.employee),
      throwsA(isA<ApiException>().having((e) => e.status, 'person', 502)),
    );
    a.sourceEmployee = null;
    a.sourceMonth = '2026-11';
    await expectLater(
      s.repeatPayrollCalculationCaseCommand(a.employee),
      throwsA(isA<ApiException>().having((e) => e.status, 'month', 502)),
    );
    expect(a.sent.length, 1);
    expect(s.pending(key), true);
    a.sourceMonth = null;
    await s.repeatPayrollCalculationCaseCommand(a.employee);
    expect(a.sent.length, 2);
    expect(s.pending(key), false);
  });
  testWidgets(
    'mobile composite plan separates travel and clears revoked private data',
    (t) async {
      t.view.physicalSize = const Size(390, 844);
      t.view.devicePixelRatio = 1;
      addTearDown(t.view.resetPhysicalSize);
      addTearDown(t.view.resetDevicePixelRatio);
      final a = CasesApi(), s = BusinessSession(api: a);
      Map<String, dynamic>? requested;
      await mount(
        t,
        a,
        s,
        onCalculate: (v) async {
          requested = v;
        },
      );
      await tapVisible(
        t,
        find.text('Abrechnungsfall 2026-10 · Fassung 1').last,
      );
      expect(
        find.text('Belegter Arbeitnehmerabzug für Steuerkosten'),
        findsOneWidget,
      );
      expect(
        find.text('Steuerfreie Reiseerstattung über Reisekostenzahlung'),
        findsOneWidget,
      );
      await tapVisible(t, find.text('Lohn aus diesem Gesamtfall berechnen'));
      expect(requested, fixture['saved']);
      await tapVisible(t, find.text('Abrechnungsfallhistorie öffnen'));
      expect(find.text('Fassung 1 · aktiv'), findsOneWidget);
      expect(t.takeException(), isNull);
      a.read = false;
      await s.load();
      await t.pumpAndSettle();
      expect(
        find.text('Belegter Arbeitnehmerabzug für Steuerkosten'),
        findsNothing,
      );
      expect(find.text('Abrechnungsfälle nicht freigegeben'), findsOneWidget);
      await t.pumpWidget(const SizedBox.shrink());
      s.dispose();
      a.dispose();
    },
  );
  testWidgets(
    'typed correction previews then repeats accepted original after lost acknowledgement',
    (t) async {
      final a = CasesApi(), s = BusinessSession(api: a);
      await mount(t, a, s);
      await tapVisible(
        t,
        find.text('Abrechnungsfall 2026-10 · Fassung 1').last,
      );
      await tapVisible(t, find.text('Abrechnungsfall berichtigen'));
      expect(
        find.byKey(const ValueKey('business-field-gross_minor')),
        findsNothing,
      );
      await t.enterText(
        find.byKey(const ValueKey('business-field-correction_reason')),
        'Belegzuordnung nochmals geprüft',
      );
      await tapVisible(t, find.text('Angaben übernehmen'));
      expect(find.text('Konkrete Zuordnung prüfen'), findsOneWidget);
      await tapVisible(
        t,
        find.text(
          'Pauschalsteuer mit dem tatsächlichen Lohnabschluss erfassen.',
        ),
      );
      await tapVisible(
        t,
        find.text(
          'Ich bestätige die vollständigen tatsächlichen Quellen und ihre Zuordnung.',
        ),
      );
      await tapVisible(t, find.text('Abrechnungsfall unverbindlich prüfen'));
      expect(a.previews, 1);
      expect(a.sent, isEmpty);
      expect(find.text('Abrechnungsfall prüfen'), findsOneWidget);
      await tapVisible(t, find.text('Geprüften Abrechnungsfall festhalten'));
      a.lose = true;
      await tapVisible(t, find.text('Abrechnungsfall festhalten'));
      expect(a.sent.length, 1);
      expect(s.pending('payroll-calculation-cases-${a.employee}'), true);
      await tapVisible(
        t,
        find.text('Ursprünglichen Abrechnungsauftrag erneut senden'),
      );
      expect(a.sent.length, 2);
      expect(a.sent.last, a.sent.first);
      expect(
        a.sent.last['correction_reason'],
        'Belegzuordnung nochmals geprüft',
      );
      expect(s.pending('payroll-calculation-cases-${a.employee}'), false);
      expect(find.text('Abrechnungsfall 2026-10 · Fassung 2'), findsWidgets);
      expect(t.takeException(), isNull);
      await t.pumpWidget(const SizedBox.shrink());
      s.dispose();
      a.dispose();
    },
  );
}

import 'dart:convert';
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:flutter/material.dart';
import 'package:smartplan_office/api.dart';
import 'package:smartplan_office/business_session.dart';
import 'package:smartplan_office/business_widgets.dart';
import 'package:smartplan_office/business_payroll_calculation_cases.dart';
import 'package:smartplan_office/business_payroll_calculation_case_contract.dart';

final fixtureCases = businessItems(
  jsonDecode(
    File('test/fixtures/payroll_factor_claim_travel.json').readAsStringSync(),
  )['cases'],
);
final f = fixtureCases.first;
Map<String, dynamic> copy(dynamic v) => businessMap(jsonDecode(jsonEncode(v)));
Map<String, dynamic> values() => {
  ...copy(f['values']),
  'rule_version': payrollFactorClaimTravelRule,
};
void main() {
  for (final run in [false, true])
    test(
      'new ${run ? 'run' : 'case'} without its own negotiated feature sends no POST',
      () async {
        final api = ClaimTravelApi()..feature = false;
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
        final api = ClaimTravelApi()..lose = true;
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
  for (final f in fixtureCases)
    testWidgets(
      'combined ${f['kind']} form preserves all actual P4 and paid-travel originals without writing',
      (tester) async {
        final api = ClaimTravelApi(f);
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
        if (f['previous'] != null) {
          final old = find.text('Abrechnungsfall 2026-10 · Fassung 1');
          await tester.ensureVisible(old);
          await tester.tap(old);
          await tester.pumpAndSettle();
        }
        final open = find.text(
          f['previous'] == null
              ? 'Faktor-Monat mit Ansprüchen und bezahlten Reisen'
              : 'Fehlenden Anspruchs- oder Reisebestandteil belegt ergänzen',
        );
        await tester.ensureVisible(open);
        await tester.pumpAndSettle();
        for (
          var scroll = 0;
          open.hitTestable().evaluate().isEmpty && scroll < 12;
          scroll++
        ) {
          await tester.drag(find.byType(ListView).first, const Offset(0, -400));
          await tester.pumpAndSettle();
        }
        expect(open.hitTestable(), findsOneWidget);
        await tester.tap(open);
        await tester.pumpAndSettle();
        final editor = tester.widget<BusinessEditor>(
          find.byType(BusinessEditor),
        );
        final v = {
          ...copy(f['values']),
          'rule_version': payrollFactorClaimTravelRule,
        };
        expect(
          editor.fields.any(
            (e) => e.name == 'event_count' || e.name == 'policy_id',
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
          'travel_settlement_ids',
          'travel_payment_ids',
        ]) {
          final field = editor.fields.singleWhere((e) => e.name == name);
          for (final id in v[name] as List) {
            final checkbox = find
                .widgetWithText(CheckboxListTile, field.choices[id]!)
                .last;
            await tester.ensureVisible(checkbox);
            if (!tester.widget<CheckboxListTile>(checkbox).value!)
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
        if (f['previous'] != null) {
          final reason = find.widgetWithText(
            TextFormField,
            'Belegter Berichtigungsgrund',
          );
          await tester.ensureVisible(reason);
          await tester.enterText(reason, v['correction_reason']);
          final upgrade = find.byType(SwitchListTile).first;
          await tester.ensureVisible(upgrade);
          await tester.tap(upgrade);
          await tester.pumpAndSettle();
        }
        final confirm = find.byType(SwitchListTile).last;
        await tester.ensureVisible(confirm);
        await tester.tap(confirm);
        await tester.pumpAndSettle();
        final submit = find.text(
          'Faktor-/Anspruchs-/Reisefall unverbindlich prüfen',
        );
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
}

class ClaimTravelApi extends OfficeApi {
  final Map<String, dynamic> f;
  ClaimTravelApi([Map<String, dynamic>? record])
    : f = record ?? fixtureCases.first,
      super(apiVersion: 'v1') {
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
          if (feature) payrollFactorClaimTravelFeature,
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
    if (f['previous'] != null &&
        path ==
            '/api/business/payroll/calculation-cases/${f['previous']['id']}')
      return copy(f['previous']);
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

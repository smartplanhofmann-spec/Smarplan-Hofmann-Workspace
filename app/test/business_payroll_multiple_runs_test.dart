import 'dart:convert';
import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:smartplan_office/api.dart';
import 'package:smartplan_office/business_payroll.dart';
import 'package:smartplan_office/business_session.dart';

final f = jsonDecode(
  File('test/fixtures/payroll_multiple_runs.json').readAsStringSync(),
) as Map<String, dynamic>;
Map<String, dynamic> copy(dynamic value) =>
    Map<String, dynamic>.from(jsonDecode(jsonEncode(value)) as Map);
final id = f['run']['employee_id'] as String;
final employee = {
  ...copy(f['sources']['employee']),
  'name': 'Synthetic source4 employee',
};

class MultipleRunApi extends OfficeApi {
  MultipleRunApi() : super(apiVersion: 'v1') {
    token = 'synthetic-source4-session';
  }
  bool accepted = false, lose = false;
  int previews = 0;
  final commands = <Map<String, dynamic>>[];
  @override
  Future<dynamic> call(String path, [Map<String, dynamic>? body]) async {
    if (path.startsWith('/api/business/capabilities'))
      return {
        'compatibility_mode': 'business',
        'storage_version': 8,
        'generation': 1,
        'readonly': false,
        'features': [
          'german_payroll_2026',
          'personnel_preparation',
          'payroll_multiple_cases',
        ],
        'capabilities': [
          'business_payroll',
          'business_personnel_workflow',
          'business_planning',
          'business_payroll_multiple_cases',
        ],
        'permissions': [
          'personnel.read',
          'personnel.write',
          'personnel.approve',
          'personnel.export',
        ],
        'organization': {
          'modules': {
            'personnel': {'enabled': true, 'visible': true},
          },
        },
      };
    if (path == '/api/me') return {'id': 'a' * 32};
    if (path == '/api/business/employees') return [employee];
    if (path.startsWith('/api/business/payroll/profiles?'))
      return {
        'employee_id': id,
        'items': [copy(f['run']['source']['profile'])],
      };
    if (path.startsWith('/api/business/payroll/runs?'))
      return {
        'employee_id': id,
        'items': accepted ? [copy(f['run'])] : [],
      };
    if (path.startsWith('/api/business/personnel/files?'))
      return {'employee_id': id, 'items': f['sources']['files']};
    if (path.startsWith('/api/business/personnel/payroll-preparations?'))
      return {
        'employee_id': id,
        'items': [copy(f['run']['source']['preparation'])],
      };
    if (path == '/api/business/payroll/rules')
      return {
        'rules': {'version': 'synthetic verified fixture'},
      };
    if (path.startsWith(
      '/api/business/payroll/multiple-one-off-cases/sources?',
    ))
      return {
        ...copy(f['sources']),
        'multiple_one_off_cases': [copy(f['saved'])],
      };
    if (path == '/api/business/payroll/preview') {
      previews++;
      expect(body, f['run_input']);
      return copy(f['run_preview']);
    }
    if (path == '/api/business/payroll/runs') {
      commands.add(copy(body));
      expect(
        copy(body)..remove('request_id'),
        copy(f['run_command'])..remove('request_id'),
      );
      accepted = true;
      if (lose) {
        lose = false;
        throw const ApiException(0, 'Synthetic accepted run response lost');
      }
      return copy(f['run']);
    }
    throw StateError('Unexpected $path');
  }
}

Future<void> tapVisible(WidgetTester tester, Finder target) async {
  if (target.evaluate().isEmpty) {
    final scroll = tester.state<ScrollableState>(find.byType(Scrollable).first);
    scroll.position.jumpTo(scroll.position.minScrollExtent);
    await tester.pumpAndSettle();
  }
  await tester.scrollUntilVisible(
    target,
    400,
    scrollable: find.byType(Scrollable).first,
    maxScrolls: 100,
  );
  await tester.ensureVisible(target);
  await tester.pumpAndSettle();
  await tester.ensureVisible(target);
  await tester.pumpAndSettle();
  await tester.tap(target);
  await tester.pumpAndSettle();
}

void main() {
  testWidgets(
    'productive native entry opens the actual case and finalizes its Source5 run after exact lost response retry',
    (tester) async {
      final api = MultipleRunApi()..lose = true;
      final active = BusinessSession(api: api);
      await active.load();
      await tester.pumpWidget(
        MaterialApp(
          home: BusinessPayrollPage(session: active, employee: employee),
        ),
      );
      await tester.pumpAndSettle();
      await tapVisible(
        tester,
        find.text('Monatsgruppen mit getrennten Zahlungstagen öffnen'),
      );
      await tapVisible(tester, find.text('Monatsgruppenmonat wählen'));
      await tester.enterText(find.byType(TextField).first, '2026-10');
      await tapVisible(tester, find.text('Monat öffnen'));
      await tapVisible(tester, find.text('Monatsgruppe 2026-10 · Fassung 1'));
      await tapVisible(
        tester,
        find.text('Lohn mit dieser Monatsgruppe berechnen'),
      );
      expect(api.previews, 1);
      await tester.scrollUntilVisible(
        find.text('Unverbindliche Berechnungsvorschau'),
        300,
        scrollable: find.byType(Scrollable).first,
        maxScrolls: 100,
      );
      await tester.pumpAndSettle();
      expect(find.text('Unverbindliche Berechnungsvorschau'), findsOneWidget);
      await tapVisible(tester, find.text('Eingaben erneut prüfen'));
      expect(api.previews, 2);
      expect(
        find.text('Geprüftes Brutto aus Vereinbarung und Monatsquellen (€)'),
        findsNothing,
      );
      final confirmation = find.text(
        'Ich bestätige ausschließlich diesen geprüften Umfang: Regulärer Gesamtlohn mit vollständigem Einzelanspruch · getrennte Zahlungstage',
      );
      await tapVisible(tester, confirmation);
      await tapVisible(
        tester,
        find.text('Geprüften Berechnungsumfang festhalten'),
      );
      expect(api.commands.length, 1);
      expect(active.pending('payroll-run-$id'), true);
      await tapVisible(
        tester,
        find.text('Ursprünglichen Auftrag erneut senden'),
      );
      expect(api.commands.length, 2);
      expect(api.commands[0], api.commands[1]);
      expect(active.pending('payroll-run-$id'), false);
      expect(find.text('Unverbindliche Berechnungsvorschau'), findsNothing);
      await tester.pumpWidget(const SizedBox());
      active.dispose();
    },
  );
}

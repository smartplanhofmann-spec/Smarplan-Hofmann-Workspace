import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:smartplan_office/api.dart';
import 'package:smartplan_office/business_payroll_multiple_cases.dart';
import 'package:smartplan_office/business_session.dart';
import 'package:smartplan_office/business_widgets.dart';

final fixture = jsonDecode(
  File('test/fixtures/payroll_multiple_runs.json').readAsStringSync(),
) as Map<String, dynamic>;
Map<String, dynamic> copy(dynamic v) =>
    Map<String, dynamic>.from(jsonDecode(jsonEncode(v)) as Map);

class MultipleApi extends OfficeApi {
  MultipleApi() : super(apiVersion: 'v1') {
    token = 'synthetic-oneoff-native';
  }
  String get employee => fixture['command']['employee_id'];
  bool read = true, approve = true, paused = false, lose = false;
  bool forceLost = false, replaceReceipt = false;
  Map<String, dynamic> accepted = copy(fixture['saved']);
  final sent = <Map<String, dynamic>>[], previews = <Map<String, dynamic>>[];
  final sourceMonths = <String>[];
  Completer<dynamic>? heldPreview;
  @override
  Future<dynamic> call(String path, [Map<String, dynamic>? body]) async {
    if (path.startsWith('/api/business/capabilities'))
      return {
        'compatibility_mode': 'business',
        'generation': 1,
        'storage_version': 10,
        'readonly': false,
        'features': ['payroll_multiple_cases'],
        'capabilities': ['business_payroll_multiple_cases'],
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
    if (path.startsWith(
      '/api/business/payroll/multiple-one-off-cases/sources?',
    )) {
      final month = Uri.parse(path).queryParameters['month']!;
      sourceMonths.add(month);
      final actual = accepted['sources'], c = actual['calculation_source'];
      return {
        ...copy(fixture['sources']),
        'employee_id': accepted['employee_id'],
        'employee': copy(actual['employee']),
        for (final key in [
          'agreements',
          'preparations',
          'profiles',
          'identities',
          'facts',
          'absences',
          'payroll_runs',
          'payroll_payments',
        ])
          key: <dynamic>[],
        'files': actual['source_files'],
        'calculation_cases': [c['running_calculation_case']],
        'annual_facts': [
          c['current_annual_basis'],
          if (c['previous_annual_basis'] != null) c['previous_annual_basis'],
          for (final p in c['components']) p['earning'],
          for (final t in c['annual_tax_forecasts']) t['annual_tax_forecast'],
        ],
        'month': month,
        'multiple_one_off_cases': [copy(accepted)],
        'can_approve': approve,
        'writes_enabled': !paused,
      };
    }
    if (path == '/api/business/payroll/multiple-one-off-cases/preview') {
      previews.add(copy(body));
      if (heldPreview != null) return heldPreview!.future;
      return copy(fixture['preview']);
    }
    if (path == '/api/business/payroll/multiple-one-off-cases') {
      sent.add(copy(body));
      if (forceLost)
        throw const ApiException(0, 'Synthetische unbestätigte Übertragung.');
      expect(
        copy(body)..remove('request_id'),
        copy(fixture['command'])..remove('request_id'),
      );
      accepted = copy(fixture['saved']);
      if (lose) {
        lose = false;
        throw const ApiException(
          0,
          'Synthetische angenommene Antwort verloren.',
        );
      }
      return {...copy(accepted), if (replaceReceipt) 'employee_id': 'f' * 32};
    }
    if (path.endsWith('/history')) return copy(fixture['history']);
    throw StateError(path);
  }
}

Future<void> press(WidgetTester t, String label) async {
  final matches = find.text(label);
  if (matches.evaluate().isEmpty)
    await t.scrollUntilVisible(
      find.text(label),
      250,
      scrollable: find.byType(Scrollable).first,
    );
  final f = matches.last;
  await t.ensureVisible(f);
  await t.pumpAndSettle();
  await t.tap(f);
  await t.pumpAndSettle();
}

Future<void> open(
  WidgetTester t,
  MultipleApi api,
  BusinessSession session, {
  Map<String, dynamic>? employee,
  Future<void> Function(Map<String, dynamic>)? onOriginal,
  Future<void> Function(Map<String, dynamic>)? onCalculate,
}) async {
  await session.load();
  await t.pumpWidget(
    MaterialApp(
      home: BusinessPayrollMultipleCasesPage(
        session: session,
        employee: employee ?? copy(api.accepted['sources']['employee']),
        initialMonth: '2026-10',
        onOriginal: onOriginal ?? (_) async {},
        onCalculate: onCalculate ?? (_) async {},
      ),
    ),
  );
  await t.pumpAndSettle();
}

Future<void> inspect(WidgetTester t) async =>
    press(t, 'Monatsgruppe 2026-10 · Fassung 1');

Future<void> prepare(WidgetTester t) async {
  await press(t, 'Monatsgruppe berichtigen');
  await t.enterText(
    find.byKey(const ValueKey('business-field-correction_reason')),
    'Synthetische Originalprüfung',
  );
  final toggle = t.widget<SwitchListTile>(find.byType(SwitchListTile));
  expect(toggle.value, false);
  toggle.onChanged!(true);
  await t.pump();
}

void background(WidgetTester t) {
  t.binding.handleAppLifecycleStateChanged(AppLifecycleState.inactive);
  t.binding.handleAppLifecycleStateChanged(AppLifecycleState.hidden);
  t.binding.handleAppLifecycleStateChanged(AppLifecycleState.paused);
}

void resume(WidgetTester t) {
  t.binding.handleAppLifecycleStateChanged(AppLifecycleState.hidden);
  t.binding.handleAppLifecycleStateChanged(AppLifecycleState.inactive);
  t.binding.handleAppLifecycleStateChanged(AppLifecycleState.resumed);
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  testWidgets(
    'actual Source5 at 390px preserves original files, complete handoff and history',
    (t) async {
      t.view.physicalSize = const Size(390, 844);
      t.view.devicePixelRatio = 1;
      addTearDown(t.view.resetPhysicalSize);
      addTearDown(t.view.resetDevicePixelRatio);
      final api = MultipleApi(),
          session = BusinessSession(api: api),
          files = <Map<String, dynamic>>[],
          cases = <Map<String, dynamic>>[];
      try {
        await open(
          t,
          api,
          session,
          onOriginal: (v) async {
            files.add(v);
          },
          onCalculate: (v) async {
            cases.add(v);
          },
        );
        await inspect(t);
        expect(find.text('Gesamtnetto'), findsOneWidget);
        final file = fixture['saved']['sources']['source_files'][0];
        await press(t, 'Personaloriginal: ${file['filename']}');
        expect(files.single, file);
        await press(t, 'Lohn mit dieser Monatsgruppe berechnen');
        expect(cases.single, fixture['saved']);
        await press(t, 'Monatsgruppenhistorie öffnen');
        await press(t, 'Historische Monatsgruppenfassung 1');
        expect(find.text('Historische Originalfassung'), findsOneWidget);
        expect(
          find.text('Lohn mit dieser Monatsgruppe berechnen'),
          findsNothing,
        );
        expect(t.takeException(), isNull);
        expect(api.sent, isEmpty);
      } finally {
        await t.pumpWidget(const SizedBox.shrink());
        session.dispose();
        api.dispose();
      }
    },
  );
  testWidgets(
    'actual incomplete monthly group remains reviewable without native finalize',
    (t) async {
      final api = MultipleApi()
            ..accepted = copy(fixture['blocked_multiple']['saved']),
          session = BusinessSession(api: api);
      try {
        await open(t, api, session);
        await inspect(t);
        expect(
          find.text('Lohn mit dieser Monatsgruppe berechnen'),
          findsNothing,
        );
        expect(find.text('Nicht berechenbar'), findsWidgets);
        expect(api.sent, isEmpty);
        expect(t.takeException(), isNull);
      } finally {
        await t.pumpWidget(const SizedBox.shrink());
        session.dispose();
        api.dispose();
      }
    },
  );
  for (final error in [false, true])
    testWidgets(
      'late Source5 preview ${error ? 'failure' : 'response'} cannot revive private data after background',
      (t) async {
        final api = MultipleApi(), session = BusinessSession(api: api);
        try {
          await open(t, api, session);
          await inspect(t);
          await prepare(t);
          final response = Completer<dynamic>();
          api.heldPreview = response;
          final button = find.text('Monatsgruppe unverbindlich prüfen');
          await t.ensureVisible(button);
          await t.pumpAndSettle();
          await t.tap(button);
          await t.pump();
          await t.pump(const Duration(milliseconds: 100));
          expect(api.previews.length, 1);
          expect(
            api.previews.single['details']['components'],
            fixture['command']['details']['components'],
          );
          background(t);
          await t.pump();
          resume(t);
          await t.pump();
          if (error)
            response.completeError(
              const ApiException(400, 'private-late-error'),
            );
          else
            response.complete(copy(fixture['preview']));
          await t.pumpAndSettle();
          expect(find.text('Monatsgruppe prüfen'), findsNothing);
          expect(find.text('private-late-error'), findsNothing);
          expect(api.sent, isEmpty);
          expect(t.takeException(), isNull);
        } finally {
          await t.pumpWidget(const SizedBox.shrink());
          session.dispose();
          api.dispose();
        }
      },
    );
  testWidgets(
    'native Source5 editor closes immediately after approval withdrawal',
    (t) async {
      final api = MultipleApi(), session = BusinessSession(api: api);
      try {
        await open(t, api, session);
        await inspect(t);
        await prepare(t);
        api.approve = false;
        await session.load();
        await t.pumpAndSettle();
        expect(find.byType(BusinessEditor), findsNothing);
        expect(api.previews, isEmpty);
        expect(api.sent, isEmpty);
      } finally {
        await t.pumpWidget(const SizedBox.shrink());
        session.dispose();
        api.dispose();
      }
    },
  );
  testWidgets(
    'original Source5 lost-ACK command repeats while module paused and rejects foreign receipt',
    (t) async {
      final api = MultipleApi()..lose = true,
          session = BusinessSession(api: api),
          body = copy(fixture['command'])..remove('request_id');
      final key = 'payroll-multiple-${api.employee}';
      try {
        await session.load();
        await expectLater(
          session.command(
            key,
            '/payroll/multiple-one-off-cases',
            body,
            validateResult: payrollMultipleCaseValidator(
              body,
              preview: copy(fixture['preview']),
            ),
          ),
          throwsA(isA<ApiException>()),
        );
        api.paused = true;
        api.replaceReceipt = true;
        await expectLater(
          session.repeatPayrollMultipleCaseCommand(api.employee),
          throwsA(isA<ApiException>()),
        );
        expect(session.pending(key), true);
        expect(api.sent.first, api.sent.last);
        api.replaceReceipt = false;
        await open(t, api, session);
        await press(t, 'Ursprünglichen Monatsgruppenauftrag erneut senden');
        expect(session.pending(key), false);
        expect(api.sent.first, api.sent.last);
        expect(t.takeException(), isNull);
      } finally {
        await t.pumpWidget(const SizedBox.shrink());
        session.dispose();
        api.dispose();
      }
    },
  );
  test('Source5 retry rejects wrong person, source contract and rule before resend', () async {
    for (final mutate in <void Function(Map<String, dynamic>)>[
      (v) => v['employee_id'] = 'f' * 32,
      (v) => v['rule_version'] = 'future',
      (v) => v['source_contract_version'] = 2,
    ]) {
      final api = MultipleApi()..forceLost = true,
          session = BusinessSession(api: api),
          body = copy(fixture['command'])..remove('request_id');
      mutate(body);
      try {
        await session.load();
        await expectLater(
          session.command(
            'payroll-multiple-${api.employee}',
            '/payroll/multiple-one-off-cases',
            body,
          ),
          throwsA(isA<ApiException>()),
        );
        final count = api.sent.length;
        await expectLater(
          session.repeatPayrollMultipleCaseCommand(api.employee),
          throwsA(isA<ApiException>()),
        );
        expect(api.sent.length, count);
      } finally {
        session.dispose();
        api.dispose();
      }
    }
  });
}

import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:smartplan_office/api.dart';
import 'package:smartplan_office/business_payroll_oneoff_cases.dart';
import 'package:smartplan_office/business_session.dart';
import 'package:smartplan_office/business_widgets.dart';

final fixture = jsonDecode(
  File('../docs/fixtures/payroll-oneoff-cases-2026.json').readAsStringSync(),
) as Map<String, dynamic>;
Map<String, dynamic> copy(dynamic v) =>
    Map<String, dynamic>.from(jsonDecode(jsonEncode(v)) as Map);

class OneoffApi extends OfficeApi {
  OneoffApi() : super(apiVersion: 'v1') {
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
        'features': ['payroll_oneoff_cases'],
        'capabilities': ['business_payroll_oneoff_cases'],
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
    if (path.startsWith('/api/business/payroll/one-off-cases/sources?')) {
      final month = Uri.parse(path).queryParameters['month']!;
      sourceMonths.add(month);
      return {
        ...copy(fixture['sources']),
        'month': month,
        'one_off_cases': [copy(accepted)],
        'can_approve': approve,
        'writes_enabled': !paused,
      };
    }
    if (path == '/api/business/payroll/one-off-cases/preview') {
      previews.add(copy(body));
      if (heldPreview != null) return heldPreview!.future;
      return copy(
        fixture[body!['details']['verification_note'] ==
                fixture['command']['details']['verification_note']
            ? 'preview'
            : 'correction_preview'],
      );
    }
    if (path == '/api/business/payroll/one-off-cases') {
      sent.add(copy(body));
      if (forceLost)
        throw const ApiException(0, 'Synthetische unbestätigte Übertragung.');
      final key = body!['status'] == 'void'
          ? 'void_command'
          : body['revision'] == 0
          ? 'command'
          : 'correction_command';
      expect(
        copy(body)..remove('request_id'),
        copy(fixture[key])..remove('request_id'),
      );
      accepted = copy(
        fixture[key == 'void_command'
            ? 'voided'
            : key == 'command'
            ? 'saved'
            : 'corrected'],
      );
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
  OneoffApi api,
  BusinessSession session, {
  Map<String, dynamic>? employee,
  Future<void> Function(Map<String, dynamic>)? onOriginal,
  Future<void> Function(Map<String, dynamic>)? onCalculate,
}) async {
  await session.load();
  await t.pumpWidget(
    MaterialApp(
      home: BusinessPayrollOneoffCasesPage(
        session: session,
        employee: employee ?? copy(fixture['sources']['employee']),
        initialMonth: '2026-10',
        onOriginal: onOriginal ?? (_) async {},
        onCalculate: onCalculate ?? (_) async {},
      ),
    ),
  );
  await t.pumpAndSettle();
}

Future<void> inspect(WidgetTester t) async =>
    press(t, 'Einmalbezugsfall 2026-10 · Fassung 1');
Future<void> prepare(WidgetTester t) async {
  await press(t, 'Einmalbezugsfall berichtigen');
  await t.enterText(
    find.byKey(const ValueKey('business-field-correction_reason')),
    fixture['correction_command']['correction_reason'],
  );
  await t.enterText(
    find.byKey(const ValueKey('business-field-verification_note')),
    fixture['correction_command']['details']['verification_note'],
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
    'actual v6 mobile correction confirms exact sources, replays lost ACK, voids and reads original history',
    (t) async {
      t.view.physicalSize = const Size(390, 844);
      t.view.devicePixelRatio = 1;
      addTearDown(t.view.resetPhysicalSize);
      addTearDown(t.view.resetDevicePixelRatio);
      final api = OneoffApi(), session = BusinessSession(api: api);
      try {
        await open(t, api, session);
        await inspect(t);
        expect(find.text('Gesamtnetto'), findsOneWidget);
        expect(t.takeException(), isNull);
        await prepare(t);
        expect(
          find.byKey(const ValueKey('business-field-gross_minor')),
          findsNothing,
        );
        await press(t, 'Einmalbezugsfall unverbindlich prüfen');
        expect(
          api.previews.single,
          fixture['correction_preview']['source_snapshot'] == null
              ? null
              : payrollOneOffCasePreviewInput(
                  copy(fixture['correction_command']),
                ),
        );
        await press(t, 'Geprüften Einmalbezugsfall festhalten');
        api.lose = true;
        await press(t, 'Einmalbezugsfall festhalten');
        expect(find.text('Einmalbezugsbestätigung offen'), findsOneWidget);
        expect(api.sent.length, 1);
        final monthButton = t.widget<OutlinedButton>(
          find.widgetWithText(OutlinedButton, 'Einmalbezugsmonat wählen'),
        );
        expect(monthButton.onPressed, isNull);
        api.paused = true;
        await press(t, 'Ursprünglichen Einmalbezugsauftrag erneut senden');
        expect(api.sent.length, 2);
        expect(api.sent.first, api.sent.last);
        expect(find.text('Einmalbezugsbestätigung offen'), findsNothing);
        api.paused = false;
        await t.tap(
          find.byTooltip('Rechte und Einmalbezugsquellen aktualisieren'),
        );
        await t.pumpAndSettle();
        await press(t, 'Fälschlichen Einmalbezugsfall aufheben');
        await t.enterText(
          find.byKey(const ValueKey('business-field-correction_reason')),
          fixture['void_command']['correction_reason'],
        );
        t.widget<SwitchListTile>(find.byType(SwitchListTile)).onChanged!(true);
        await t.pump();
        await press(t, 'Einmalbezugsfall belegt aufheben');
        expect(api.accepted, fixture['voided']);
        await press(t, 'Einmalbezugsfallhistorie öffnen');
        await press(t, 'Historische Einmalbezugsfassung 1');
        expect(
          find.text(fixture['saved']['details']['verification_note']),
          findsOneWidget,
        );
        expect(find.text('Historische Originalfassung'), findsOneWidget);
        expect(find.text('Einmalbezugsfall berichtigen'), findsNothing);
        expect(t.takeException(), isNull);
      } finally {
        await t.pumpWidget(const SizedBox.shrink());
        session.dispose();
        api.dispose();
      }
    },
  );
  testWidgets(
    'actual v6 original and calculation handoff preserve exact frozen case',
    (t) async {
      final api = OneoffApi(),
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
        final original = fixture['saved']['sources']['source_files'][0];
        await press(t, 'Personaloriginal: ${original['filename']}');
        expect(files.single, original);
        await press(t, 'Lohn mit diesem Einmalbezugsfall berechnen');
        expect(cases.single, fixture['saved']);
        expect(api.sent, isEmpty);
        t
            .state<ScrollableState>(find.byType(Scrollable).first)
            .position
            .jumpTo(0);
        await t.pumpAndSettle();
        await press(t, 'Einmalbezugsmonat wählen');
        await t.enterText(find.byType(TextFormField), '2026-11');
        await press(t, 'Monat öffnen');
        expect(api.sourceMonths.last, '2026-11');
        expect(find.byType(PayrollOneoffCasePlanView), findsNothing);
        expect(t.takeException(), isNull);
      } finally {
        await t.pumpWidget(const SizedBox.shrink());
        session.dispose();
        api.dispose();
      }
    },
  );
  for (final failure in [false, true])
    testWidgets(
      'late v6 preview ${failure ? 'error' : 'result'} cannot restore private data after background',
      (t) async {
        final api = OneoffApi(), session = BusinessSession(api: api);
        const secret = 'Synthetischer privater Einmalbezugsvermerk';
        try {
          await open(t, api, session);
          await inspect(t);
          await prepare(t);
          final response = Completer<dynamic>();
          api.heldPreview = response;
          final button = find.text('Einmalbezugsfall unverbindlich prüfen');
          await t.ensureVisible(button);
          await t.pumpAndSettle();
          await t.tap(button);
          await t.pump();
          await t.pump(const Duration(milliseconds: 100));
          expect(api.previews.length, 1);
          background(t);
          await t.pump();
          resume(t);
          await t.pump();
          if (failure)
            response.completeError(const ApiException(400, secret));
          else
            response.complete(copy(fixture['correction_preview']));
          await t.pumpAndSettle();
          expect(find.text('Einmalbezugsfall prüfen'), findsNothing);
          expect(find.text(secret), findsNothing);
          expect(
            find.text(fixture['saved']['details']['verification_note']),
            findsNothing,
          );
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
    'approval withdrawal closes v6 editor while personnel read remains',
    (t) async {
      final api = OneoffApi(), session = BusinessSession(api: api);
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
    'employee context replacement cannot retain a private v6 editor',
    (t) async {
      final api = OneoffApi(), session = BusinessSession(api: api);
      try {
        await open(t, api, session);
        await inspect(t);
        await prepare(t);
        await open(
          t,
          api,
          session,
          employee: {
            ...copy(fixture['sources']['employee']),
            'id': 'f' * 32,
            'name': 'Other synthetic employee',
          },
        );
        expect(find.byType(BusinessEditor), findsNothing);
        expect(
          find.text(fixture['saved']['details']['verification_note']),
          findsNothing,
        );
        expect(api.sent, isEmpty);
        expect(t.takeException(), isNull);
      } finally {
        await t.pumpWidget(const SizedBox.shrink());
        session.dispose();
        api.dispose();
      }
    },
  );
  test('actual v6 replay rejects wrong employee, rule and source contract before resending', () async {
    for (final mutate in <void Function(Map<String, dynamic>)>[
      (b) => b['employee_id'] = 'f' * 32,
      (b) => b['rule_version'] = 'future',
      (b) => b['source_contract_version'] = 2,
    ]) {
      final api = OneoffApi()..forceLost = true,
          session = BusinessSession(api: api);
      try {
        await session.load();
        final body = copy(fixture['command'])..remove('request_id');
        mutate(body);
        await expectLater(
          session.command(
            'payroll-oneoff-cases-${api.employee}',
            '/payroll/one-off-cases',
            body,
            validateResult: payrollOneOffCaseValidator(
              body,
              preview: copy(fixture['preview']),
            ),
          ),
          throwsA(isA<ApiException>()),
        );
        final count = api.sent.length;
        await expectLater(
          session.repeatPayrollOneoffCaseCommand(api.employee),
          throwsA(isA<ApiException>()),
        );
        expect(api.sent.length, count);
      } finally {
        session.dispose();
        api.dispose();
      }
    }
  });
  test('actual v6 replay preserves the original validator against a foreign receipt', () async {
    final api = OneoffApi()..lose = true, session = BusinessSession(api: api);
    try {
      await session.load();
      final body = copy(fixture['command'])..remove('request_id'),
          key = 'payroll-oneoff-cases-${api.employee}';
      await expectLater(
        session.command(
          key,
          '/payroll/one-off-cases',
          body,
          validateResult: payrollOneOffCaseValidator(
            body,
            preview: copy(fixture['preview']),
          ),
        ),
        throwsA(isA<ApiException>()),
      );
      api.replaceReceipt = true;
      await expectLater(
        session.repeatPayrollOneoffCaseCommand(api.employee),
        throwsA(isA<ApiException>()),
      );
      expect(session.pending(key), true);
      expect(api.sent.first, api.sent.last);
      api.replaceReceipt = false;
      await session.repeatPayrollOneoffCaseCommand(api.employee);
      expect(session.pending(key), false);
      expect(api.sent.first, api.sent.last);
    } finally {
      session.dispose();
      api.dispose();
    }
  });
}

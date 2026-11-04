import 'dart:convert';
import 'dart:async';
import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:smartplan_office/api.dart';
import 'package:smartplan_office/business_payroll_wage_interruptions.dart';
import 'package:smartplan_office/business_session.dart';

final fixture = jsonDecode(
  File('test/fixtures/payroll_wage_interruptions.json').readAsStringSync(),
) as Map<String, dynamic>;
Map<String, dynamic> copy(dynamic v) =>
    Map<String, dynamic>.from(jsonDecode(jsonEncode(v)) as Map);
String get employeeId => fixture['command']['employee_id'];
Map<String, dynamic> values(dynamic command) {
  final d = command['details'];
  List<dynamic> ids(String field) =>
      businessItems(d[field]).map((r) => r['id']).toList();
  return {
    'year': 2026,
    'assessment_through': d['assessment_through'],
    'employment_terms_ids': ids('employment_terms_refs'),
    'run_ids': ids('run_refs'),
    'work_schedule_ids': ids('work_schedule_refs'),
    'entitlement_case_ids': ids('entitlement_case_refs'),
    'exception_review_file_ids': ids('exception_review_file_refs'),
    'source_file_ids': List.from(command['source_file_ids']),
    'excluded_reviews': {
      for (final k in payrollWageInterruptionExceptions.keys) k: 'none',
    },
    'excluded_payments': [],
    'verification_note': d['verification_note'],
    'correction_reason': command['correction_reason'] ?? '',
  };
}

class WageInterruptionsApi extends OfficeApi {
  WageInterruptionsApi() : super(apiVersion: 'v1') {
    token = 'synthetic-u-fixture-session';
  }
  bool read = true,
      approve = true,
      sourceApprove = true,
      paused = false,
      lose = false;
  bool includeSaved = false,
      corrected = false,
      showVoid = false,
      wrongSource = false,
      wrongReceipt = false;
  int employeeRevision = 2, created = 0;
  Completer<dynamic>? delayedHistory;
  final sent = <Map<String, dynamic>>[];
  final previews = <Map<String, dynamic>>[];
  @override
  Future<dynamic> call(String path, [Map<String, dynamic>? body]) async {
    if (path.startsWith('/api/business/capabilities'))
      return {
        'compatibility_mode': 'business',
        'generation': 1,
        'storage_version': 10,
        'readonly': false,
        'features': ['payroll_wage_interruptions', 'organization_modules'],
        'capabilities': ['business_payroll_wage_interruptions'],
        'permissions': [
          if (read) 'personnel.read',
          if (approve) 'personnel.approve',
        ],
        'organization': {
          'revision': 1,
          'configured': true,
          'modules': {
            for (final name in BusinessSession.organizationSections)
              name: {
                'visible': true,
                'enabled': name != 'personnel' || !paused,
              },
          },
        },
      };
    if (path == '/api/me') return {'id': 'a' * 32};
    if (path.startsWith('/api/business/payroll/wage-interruptions/sources?')) {
      final page = copy(fixture['sources']);
      page['can_approve'] = sourceApprove;
      page['writes_enabled'] = !paused;
      page['employee']['revision'] = employeeRevision;
      if (wrongSource) page['employee']['id'] = 'f' * 32;
      page['assessments'] = [
        if (includeSaved)
          copy(
            fixture[showVoid
                ? 'void'
                : corrected
                ? 'corrected'
                : 'saved'],
          ),
      ];
      return page;
    }
    if (path == '/api/business/payroll/wage-interruptions/preview') {
      previews.add(copy(body));
      return copy(fixture[includeSaved ? 'correction_preview' : 'preview']);
    }
    if (path == '/api/business/payroll/wage-interruptions') {
      sent.add(copy(body));
      if (created == 0) created++;
      corrected = body?['id'] != null;
      if (lose) {
        lose = false;
        throw const ApiException(
          0,
          'Angenommene Antwort synthetisch verloren.',
        );
      }
      final result = copy(fixture[corrected ? 'corrected' : 'saved']);
      if (wrongReceipt)
        result['details']['verification_note'] = 'Replaced accepted original';
      return result;
    }
    if (path.endsWith('/history'))
      return delayedHistory?.future ?? copy(fixture['history']);
    throw StateError(path);
  }
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  test('actual backend create correction and void bind exact original plans and histories', () {
    final sources = payrollWageInterruptionSources(
      copy(fixture['sources']),
      employeeId,
    );
    final input = payrollWageInterruptionInput(
      employeeId,
      sources,
      values(fixture['command']),
    );
    expect(
      payrollWageInterruptionPreviewInput(input),
      fixture['preview_request'],
    );
    expect(
      payrollWageInterruptionPreview(fixture['preview'], input),
      fixture['preview'],
    );
    payrollWageInterruptionValidator(
      copy(fixture['command']),
      preview: copy(fixture['preview']),
    )(fixture['saved']);
    final correction = payrollWageInterruptionInput(
      employeeId,
      sources,
      values(fixture['correction_body']),
      previous: copy(fixture['saved']),
    );
    expect(
      payrollWageInterruptionPreview(fixture['correction_preview'], correction),
      fixture['correction_preview'],
    );
    payrollWageInterruptionValidator(
      copy(fixture['correction_body']),
      previous: copy(fixture['saved']),
      preview: copy(fixture['correction_preview']),
    )(fixture['corrected']);
    payrollWageInterruptionValidator(
      copy(fixture['void_body']),
      previous: copy(fixture['corrected']),
    )(fixture['void']);
    for (final item in businessItems(fixture['history']['items']))
      payrollWageInterruptionRecord(item, employeeId);
    expect(fixture['saved']['plan']['number_u'], 1);
    expect(fixture['saved']['plan']['periods'].single['workday_count'], 5);
  });
  test('all eight legal exception decisions must be explicit and agree with actual periods', () {
    for (final mutate in <void Function(Map<String, dynamic>)>[
      (v) => v['excluded_reviews'] = {},
      (v) => v['excluded_reviews'].remove('qualification_benefit'),
      (v) => v['excluded_reviews']['qualification_benefit'] = 'present',
      (v) => v['excluded_reviews']['invented'] = 'none',
      (v) => v['source_file_ids'] = [],
      (v) => v['run_ids'].add(v['run_ids'].first),
      (v) => v['work_schedule_ids'] = ['f' * 32],
    ]) {
      final bad = values(fixture['command']);
      mutate(bad);
      expect(
        () => payrollWageInterruptionInput(
          employeeId,
          copy(fixture['sources']),
          bad,
        ),
        throwsA(isA<ApiException>()),
      );
    }
    final withPayment = values(fixture['command']);
    withPayment['excluded_reviews']['qualification_benefit'] = 'present';
    withPayment['excluded_payments'] = [
      {
        'from': '2026-10-20',
        'to': '2026-10-26',
        'kind': 'qualification_benefit',
        'evidence_file_ids': withPayment['source_file_ids'],
      },
    ];
    final input = payrollWageInterruptionInput(
      employeeId,
      copy(fixture['sources']),
      withPayment,
    );
    expect(
      input['details']['excluded_payments'].single['evidence_refs'],
      fixture['command']['details']['exception_review_file_refs'],
    );
    withPayment['excluded_payments'].add(
      copy(withPayment['excluded_payments'].first),
    );
    expect(
      () => payrollWageInterruptionInput(
        employeeId,
        copy(fixture['sources']),
        withPayment,
      ),
      throwsA(isA<ApiException>()),
    );
  });
  test('unknown annual count never becomes zero and fake daily evidence is refused', () {
    final blocked = copy(fixture['preview']['plan']);
    blocked['blockers'] = [
      {'code': 'missing_days', 'message': 'Tatsächliche Laufquellen fehlen.'},
    ];
    blocked['can_determine'] = false;
    blocked['number_u'] = null;
    expect(payrollWageInterruptionPlan(blocked)['number_u'], null);
    blocked['number_u'] = 0;
    expect(
      () => payrollWageInterruptionPlan(blocked),
      throwsA(isA<ApiException>()),
    );
    for (final change in <void Function(Map<String, dynamic>)>[
      (v) =>
          v['plan']['input']['days'][0]['claim_evidence_refs'][0]['revision']++,
      (v) =>
          v['plan']['input']['days'][0]['schedule_evidence_refs'][0]['content_hash'] =
              'f' * 64,
      (v) => v['plan']['input']['days'][0]['exception_evidence_refs'][0]['id'] =
          'f' * 32,
      (v) =>
          v['plan']['input']['employment_intervals'][0]['from'] = '2026-01-01',
      (v) => v['source_snapshot']['source_files'][0]['employee_id'] = 'f' * 32,
      (v) => v['source_snapshot']['employee']['revision']++,
      (v) => v['plan']['covered_dates'].removeLast(),
      (v) => v['plan']['periods'][0]['workday_count'] = 6,
    ]) {
      final bad = copy(fixture['preview']);
      change(bad);
      expect(
        () => payrollWageInterruptionPreview(bad, copy(fixture['command'])),
        throwsA(isA<ApiException>()),
      );
    }
  });
  test(
    'accepted receipt cannot replace original note, proof or revision chain',
    () {
      final validate = payrollWageInterruptionValidator(
        copy(fixture['correction_body']),
        previous: copy(fixture['saved']),
        preview: copy(fixture['correction_preview']),
      );
      for (final change in <void Function(Map<String, dynamic>)>[
        (v) => v['previous_hash'] = 'f' * 64,
        (v) => v['details']['verification_note'] = 'Changed original',
        (v) => v['sources']['runs'][0]['revision']++,
        (v) => v['plan']['plan_hash'] = 'f' * 64,
        (v) => v['source_file_ids'] = [],
      ]) {
        final bad = copy(fixture['corrected']);
        change(bad);
        expect(() => validate(bad), throwsA(isA<ApiException>()));
      }
    },
  );
  test('actual accepted LostACK keeps body nonce and validator through pause and newer employee sources', () async {
    final api = WageInterruptionsApi()..lose = true;
    final current = BusinessSession(api: api);
    addTearDown(current.dispose);
    addTearDown(api.dispose);
    await current.load();
    final body = copy(fixture['command'])..remove('request_id'),
        key = 'payroll-wage-interruptions-$employeeId';
    await expectLater(
      current.command(
        key,
        '/payroll/wage-interruptions',
        body,
        validateResult: payrollWageInterruptionValidator(
          body,
          preview: copy(fixture['preview']),
        ),
      ),
      throwsA(isA<ApiException>()),
    );
    api.paused = true;
    api.employeeRevision = 99;
    api.wrongReceipt = true;
    await expectLater(
      current.repeatPayrollWageInterruptionsCommand(employeeId),
      throwsA(isA<ApiException>()),
    );
    expect(current.pending(key), true);
    api.wrongReceipt = false;
    await current.repeatPayrollWageInterruptionsCommand(employeeId);
    expect(api.created, 1);
    expect(api.sent, hasLength(3));
    expect(
      api.sent.every((v) => jsonEncode(v) == jsonEncode(api.sent.first)),
      true,
    );
    expect(current.pending(key), false);
    expect(current.sectionEnabled('personnel'), false);
  });
  test(
    'fresh approval and exact private employee gate original replay',
    () async {
      final api = WageInterruptionsApi()..lose = true;
      final session = BusinessSession(api: api);
      addTearDown(session.dispose);
      addTearDown(api.dispose);
      await session.load();
      final body = copy(fixture['command'])..remove('request_id'),
          key = 'payroll-wage-interruptions-$employeeId';
      await expectLater(
        session.command(
          key,
          '/payroll/wage-interruptions',
          body,
          validateResult: payrollWageInterruptionValidator(
            body,
            preview: copy(fixture['preview']),
          ),
        ),
        throwsA(isA<ApiException>()),
      );
      api.approve = false;
      await expectLater(
        session.repeatPayrollWageInterruptionsCommand(employeeId),
        throwsA(isA<ApiException>()),
      );
      api.approve = true;
      api.sourceApprove = false;
      await expectLater(
        session.repeatPayrollWageInterruptionsCommand(employeeId),
        throwsA(isA<ApiException>()),
      );
      api.sourceApprove = true;
      api.wrongSource = true;
      await expectLater(
        session.repeatPayrollWageInterruptionsCommand(employeeId),
        throwsA(isA<ApiException>()),
      );
      expect(api.sent, hasLength(1));
      expect(session.pending(key), true);
      api.wrongSource = false;
      await session.repeatPayrollWageInterruptionsCommand(employeeId);
      expect(api.sent, hasLength(2));
    },
  );
  testWidgets(
    'readonly actual day derivation and explicit unknown count render on mobile',
    (tester) async {
      tester.view.physicalSize = const Size(390, 844);
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.resetPhysicalSize);
      addTearDown(tester.view.resetDevicePixelRatio);
      Future<void> show(Map<String, dynamic> plan) => tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: SingleChildScrollView(
              child: PayrollWageInterruptionPlanView(plan: plan),
            ),
          ),
        ),
      );
      await show(copy(fixture['preview']['plan']));
      await tester.pumpAndSettle();
      expect(find.text('Anzahl U: 1'), findsOneWidget);
      expect(find.byType(TextField), findsNothing);
      await tester.tap(find.text('Abgeleitete Tagesherleitung'));
      await tester.pumpAndSettle();
      expect(find.textContaining('15.10.2026'), findsOneWidget);
      expect(find.byType(TextField), findsNothing);
      expect(tester.takeException(), null);
      final blocked = copy(fixture['preview']['plan'])
        ..['can_determine'] = false
        ..['number_u'] = null
        ..['blockers'] = [
          {'code': 'sources', 'message': 'Originale fehlen'},
        ];
      await show(blocked);
      await tester.pumpAndSettle();
      expect(find.text('Anzahl U noch ungeklärt'), findsOneWidget);
      expect(find.text('Anzahl U: 0'), findsNothing);
      expect(tester.takeException(), null);
    },
  );
  testWidgets(
    'real correction form resets reviews and LostACK UI replays original through personnel pause',
    (tester) async {
      await tester.binding.setSurfaceSize(const Size(1100, 1000));
      addTearDown(() => tester.binding.setSurfaceSize(null));
      final api = WageInterruptionsApi()..includeSaved = true;
      final current = BusinessSession(api: api);
      await current.load();
      await tester.pumpWidget(
        MaterialApp(
          home: BusinessPayrollWageInterruptionsPage(
            session: current,
            employee: copy(fixture['sources']['employee']),
            onOriginal: (_) async {},
          ),
        ),
      );
      await tester.pumpAndSettle();
      Future<void> tap(String label) async {
        final matches = find.text(label);
        if (matches.evaluate().isEmpty) {
          await tester.scrollUntilVisible(
            matches,
            400,
            scrollable: find.byType(Scrollable).first,
            maxScrolls: 20,
          );
        }
        final target = matches.last;
        await tester.ensureVisible(target);
        await tester.pumpAndSettle();
        await tester.tap(target);
        await tester.pumpAndSettle();
      }

      Future<void> enter(String key, String text) async {
        final f = find.byKey(ValueKey('business-field-$key'));
        await tester.ensureVisible(f);
        await tester.pumpAndSettle();
        await tester.enterText(f, text);
        await tester.pumpAndSettle();
      }

      Future<void> review() async {
        await tap('Alle gesetzlichen Leistungsarten prüfen');
        for (final k in payrollWageInterruptionExceptions.keys) {
          final field = find.byWidgetPredicate(
            (w) =>
                w is DropdownButtonFormField<String> &&
                w.decoration.labelText == payrollWageInterruptionExceptions[k],
          );
          await tester.ensureVisible(field);
          await tester.pumpAndSettle();
          expect(
            tester.widget<DropdownButtonFormField<String>>(field).initialValue,
            '',
          );
          await tester.tap(field);
          await tester.pumpAndSettle();
          await tap('Nicht vorhanden – anhand der Originale geprüft');
        }
        await tap('Geprüfte Angaben übernehmen');
      }

      await tap('Jahresprüfstand · Fassung 1');
      await tap('Jahresprüfstand korrigieren');
      await enter(
        'verification_note',
        fixture['correction_body']['details']['verification_note'],
      );
      await enter(
        'correction_reason',
        fixture['correction_body']['correction_reason'],
      );
      expect(
        find.byKey(const ValueKey('business-field-number_u')),
        findsNothing,
      );
      await tap('Geprüfte Angaben übernehmen');
      await review();
      await tap('Quellenauswahl ändern');
      await tap('Geprüfte Angaben übernehmen');
      expect(find.textContaining('0/8 Leistungsarten geprüft'), findsOneWidget);
      await review();
      await tap('Jahresprüfung unverbindlich ableiten');
      expect(api.previews, hasLength(1));
      expect(
        api.previews.single,
        payrollWageInterruptionPreviewInput(copy(fixture['correction_body'])),
      );
      expect(find.text('Anzahl U: 1'), findsAtLeastNWidgets(1));
      api.lose = true;
      await tap('Geprüften Jahresstand festhalten');
      await tap('Jahresprüfstand festhalten');
      expect(current.pending('payroll-wage-interruptions-$employeeId'), true);
      expect(api.created, 1);
      api.paused = true;
      api.employeeRevision = 99;
      await tap('Ursprünglichen Auftrag erneut prüfen');
      expect(api.sent, hasLength(2));
      expect(api.sent.first, api.sent.last);
      expect(current.pending('payroll-wage-interruptions-$employeeId'), false);
      expect(
        find.text(fixture['corrected']['details']['verification_note']),
        findsOneWidget,
      );
      api.read = false;
      await current.load();
      await tester.pumpAndSettle();
      expect(
        find.text(fixture['corrected']['details']['verification_note']),
        findsNothing,
      );
      expect(
        find.text('Keine aktuelle globale Personalfreigabe.'),
        findsOneWidget,
      );
      expect(tester.takeException(), null);
      await tester.pumpWidget(const SizedBox.shrink());
      current.dispose();
      api.dispose();
    },
  );

  testWidgets(
    'new annual form begins with no assumed date or source and clears private draft on employee change',
    (tester) async {
      final api = WageInterruptionsApi();
      final current = BusinessSession(api: api);
      await current.load();
      Future<void> show(Map<String, dynamic> employee) => tester.pumpWidget(
        MaterialApp(
          home: BusinessPayrollWageInterruptionsPage(
            session: current,
            employee: employee,
            onOriginal: (_) async {},
          ),
        ),
      );
      await show(copy(fixture['sources']['employee']));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Jahresprüfung vorbereiten'));
      await tester.pumpAndSettle();
      expect(
        find.text('Quellen für die Jahresprüfung auswählen'),
        findsOneWidget,
      );
      expect(
        tester
            .widget<TextFormField>(
              find.byKey(const ValueKey('business-field-assessment_through')),
            )
            .controller!
            .text,
        '',
      );
      for (final box in tester.widgetList<CheckboxListTile>(
        find.byType(CheckboxListTile),
      ))
        expect(box.value, false);
      expect(
        find.byKey(const ValueKey('business-field-number_u')),
        findsNothing,
      );
      api.read = false;
      await current.load();
      await tester.pumpAndSettle();
      expect(
        find.text('Quellen für die Jahresprüfung auswählen'),
        findsNothing,
      );
      expect(tester.takeException(), null);
      api.read = true;
      api.includeSaved = true;
      await current.load();
      await tester.pumpAndSettle();
      await tester.tap(find.text('Jahresquellen neu laden'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Jahresprüfstand · Fassung 1'));
      await tester.pumpAndSettle();
      expect(
        find.text(fixture['saved']['details']['verification_note']),
        findsOneWidget,
      );
      await show({...copy(fixture['sources']['employee']), 'id': 'f' * 32});
      await tester.pumpAndSettle();
      expect(
        find.text(fixture['saved']['details']['verification_note']),
        findsNothing,
      );
      expect(tester.takeException(), null);
      await tester.pumpWidget(const SizedBox.shrink());
      current.dispose();
      api.dispose();
    },
  );
  testWidgets(
    'current void annual assessment can be explicitly corrected but cannot be voided again',
    (tester) async {
      final api = WageInterruptionsApi()
        ..includeSaved = true
        ..showVoid = true;
      final session = BusinessSession(api: api);
      await session.load();
      await tester.pumpWidget(
        MaterialApp(
          home: BusinessPayrollWageInterruptionsPage(
            session: session,
            employee: copy(fixture['sources']['employee']),
            onOriginal: (_) async {},
          ),
        ),
      );
      await tester.pumpAndSettle();
      await tester.tap(find.text('Jahresprüfstand · Fassung 3'));
      await tester.pumpAndSettle();
      await tester.scrollUntilVisible(
        find.text('Jahresprüfstand korrigieren'),
        300,
        scrollable: find.byType(Scrollable).first,
      );
      await tester.ensureVisible(find.text('Jahresprüfstand korrigieren'));
      await tester.pumpAndSettle();
      expect(find.text('Fälschlichen Jahresprüfstand aufheben'), findsNothing);
      await tester.tap(find.text('Jahresprüfstand korrigieren'));
      await tester.pumpAndSettle();
      expect(
        find.text('Quellen für die Jahresprüfung auswählen'),
        findsOneWidget,
      );
      expect(
        tester
            .widget<TextFormField>(
              find.byKey(const ValueKey('business-field-correction_reason')),
            )
            .controller!
            .text,
        '',
      );
      expect(tester.takeException(), null);
      await tester.pumpWidget(const SizedBox.shrink());
      session.dispose();
      api.dispose();
    },
  );
  testWidgets(
    'U editor closes on approve-only withdrawal and late private history errors disappear after background',
    (tester) async {
      await tester.binding.setSurfaceSize(const Size(1100, 1000));
      addTearDown(() => tester.binding.setSurfaceSize(null));
      final api = WageInterruptionsApi()..includeSaved = true;
      final session = BusinessSession(api: api);
      await session.load();
      await tester.pumpWidget(
        MaterialApp(
          home: BusinessPayrollWageInterruptionsPage(
            session: session,
            employee: copy(fixture['sources']['employee']),
            onOriginal: (_) async {},
          ),
        ),
      );
      await tester.pumpAndSettle();
      Future<void> tap(String label) async {
        final target = find.text(label);
        await tester.ensureVisible(target);
        await tester.pumpAndSettle();
        await tester.tap(target);
        await tester.pumpAndSettle();
      }

      await tap('Jahresprüfstand · Fassung 1');
      await tap('Jahresprüfstand korrigieren');
      api.approve = false;
      await session.load();
      await tester.pumpAndSettle();
      expect(
        find.text('Quellen für die Jahresprüfung auswählen'),
        findsNothing,
      );
      api.approve = true;
      await session.load();
      await tester.pumpAndSettle();
      await tap('Jahresquellen neu laden');
      await tap('Jahresprüfstand · Fassung 1');
      api.delayedHistory = Completer<dynamic>();
      final history = find.text('Jahresprüfhistorie öffnen');
      await tester.ensureVisible(history);
      await tester.pumpAndSettle();
      await tester.tap(history);
      await tester.pump();
      tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.paused);
      await tester.pump();
      api.delayedHistory!.completeError(
        const ApiException(500, 'PRIVATE_OLD_U_HISTORY'),
      );
      await tester.pumpAndSettle();
      tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.resumed);
      await tester.pumpAndSettle();
      expect(find.text('PRIVATE_OLD_U_HISTORY'), findsNothing);
      expect(
        find.text(fixture['saved']['details']['verification_note']),
        findsNothing,
      );
      expect(tester.takeException(), null);
      await tester.pumpWidget(const SizedBox.shrink());
      session.dispose();
      api.dispose();
    },
  );
}

import 'dart:convert';
import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:smartplan_office/api.dart';
import 'package:smartplan_office/business_session.dart';
import 'package:smartplan_office/business_payroll.dart';
import 'package:smartplan_office/business_payroll_facts.dart';

final f = jsonDecode(
  File('test/fixtures/payroll_facts.json').readAsStringSync(),
) as Map<String, dynamic>;
Map<String, dynamic> copy(dynamic value) =>
    Map<String, dynamic>.from(jsonDecode(jsonEncode(value)) as Map);
final employee = f['employee']['id'] as String;
Map<String, dynamic> clean(dynamic value) => copy(value)..remove('request_id');
Map<String, dynamic> values() {
  final d = f['command']['details'];
  return {
    'month': d['month'],
    'preparation_id': d['preparation_ref']['id'],
    'employment_terms_id': d['employment_terms_ref']['id'],
    'work_schedule_id': '',
    'profile_ids': [for (final r in d['profile_refs']) r['id']],
    'identity_ids': [for (final r in d['identity_refs']) r['id']],
    'tax_treatment': d['tax_treatment'],
    'verification_note': d['verification_note'],
    'entitlement_decisions': d['entitlement_decisions'],
    'source_file_ids': f['command']['source_file_ids'],
  };
}

class FactsApi extends OfficeApi {
  FactsApi() : super(apiVersion: 'v1') {
    token = 'synthetic-private-facts';
  }
  bool read = true,
      write = true,
      approve = true,
      paused = false,
      lose = false,
      wrongPerson = false;
  int created = 0;
  final sent = <Map<String, dynamic>>[];
  @override
  Future<dynamic> call(String path, [Map<String, dynamic>? body]) async {
    if (path.startsWith('/api/business/capabilities'))
      return {
        'compatibility_mode': 'business',
        'generation': 1,
        'storage_version': 10,
        'readonly': false,
        'features': ['payroll_period_facts', 'german_payroll_2026'],
        'capabilities': ['business_payroll_facts', 'business_payroll'],
        'permissions': [
          if (read) 'personnel.read',
          if (write) 'personnel.write',
          if (approve) 'personnel.approve',
        ],
        'organization': {
          'modules': {
            'personnel': {'enabled': !paused, 'visible': true},
          },
        },
      };
    if (path == '/api/me') return {'id': 'a' * 32};
    if (path.startsWith('/api/business/payroll/facts/sources?'))
      return {
        ...copy(f['sources']),
        'employee_id': wrongPerson ? 'f' * 32 : employee,
        'can_write': write,
        'can_approve': approve,
        'writes_enabled': !paused,
      };
    if (path == '/api/business/payroll/facts') {
      sent.add(copy(body));
      if (created == 0) created++;
      if (lose) {
        lose = false;
        throw const ApiException(
          0,
          'Synthetisch verlorene angenommene Antwort.',
        );
      }
      return copy(f['terms']);
    }
    if (path.endsWith('/history'))
      return {
        'employee_id': employee,
        'items': [copy(f['terms'])],
      };
    throw StateError(path);
  }
}

void main() {
  test(
    'strict calendar and duration distinguish unknown from explicitly zero',
    () {
      expect(payrollFactDate('2026-02-28'), '2026-02-28');
      expect(payrollFactDate('', optional: true), null);
      for (final v in ['', '2026-02-29', '2026-04-31'])
        expect(() => payrollFactDate(v), throwsA(isA<ApiException>()));
      expect(payrollFactDates('2026-02').length, 28);
      expect(payrollFactSeconds('00:00'), 0);
      expect(payrollFactSeconds('07:30:01'), 27001);
      expect(payrollFactTime(27001), '07:30:01');
      for (final v in ['', '8', '8.5', '24:01'])
        expect(() => payrollFactSeconds(v), throwsA(isA<ApiException>()));
    },
  );
  test('employment binds original personnel date and exact agreement with no default method', () {
    final d = copy(f['terms_command']['details']),
        v = {
          ...d,
          'agreement_ids': [for (final r in d['agreement_refs']) r['id']],
          'source_file_ids': f['terms_command']['source_file_ids'],
        };
    Map<String, dynamic> build(Map<String, dynamic> input) => payrollFactInput(
      employee,
      copy(f['sources_before']),
      'employment_terms',
      input,
    );
    expect(build(v), clean(f['terms_command']));
    for (final patch in [
      {'employment_from': ''},
      {'employment_from': '2026-10-01'},
      {'proration_method': ''},
      {'agreement_ids': []},
      {
        'source_file_ids': ['f' * 32],
      },
    ])
      expect(() => build({...v, ...patch}), throwsA(isA<ApiException>()));
  });
  test(
    'every chronological work schedule day requires explicit time and region',
    () {
      final days = [
            for (final date in payrollFactDates('2026-02'))
              {
                'date': date,
                'scheduled_seconds': 0,
                'workplace': '',
                'federal_state': 'BW',
              },
          ],
          v = {
            'month': '2026-02',
            'days': days,
            'reason': 'Synthetischer belegter vollständiger Arbeitsplan',
            'source_file_ids': f['command']['source_file_ids'],
          };
      Map<String, dynamic> build(Map<String, dynamic> value) =>
          payrollFactInput(
            employee,
            copy(f['sources']),
            'work_schedule',
            value,
          );
      expect(build(v)['details']['days'].length, 28);
      expect(
        () => build({...v, 'days': days.sublist(1)}),
        throwsA(isA<ApiException>()),
      );
      expect(
        () => build({
          ...v,
          'days': [
            {...days.first, 'scheduled_seconds': 3600},
            ...days.skip(1),
          ],
        }),
        throwsA(isA<ApiException>()),
      );
    },
  );
  test('actual backend preview binds source and separate tax social days without client gross input', () {
    final body = payrollFactInput(
      employee,
      copy(f['sources']),
      'period_case',
      values(),
    );
    expect({
      ...body,
      'preview_hash': f['preview']['preview_hash'],
    }, clean(f['command']));
    payrollFactPreview(f['preview'], body);
    expect(body.containsKey('gross_minor'), false);
    expect(f['preview']['plan']['gross_minor'], 33068);
    for (final alter in <void Function(Map<String, dynamic>)>[
      (v) => v['employee_id'] = 'f' * 32,
      (v) => v['source_snapshot']['preparation']['revision']++,
      (v) => v['source_snapshot']['profiles'][0]['employee_id'] = 'f' * 32,
      (v) => v['source_snapshot']['source_files'] = [],
    ]) {
      final bad = copy(f['preview']);
      alter(bad);
      expect(() => payrollFactPreview(bad, body), throwsA(isA<ApiException>()));
    }
  });
  test(
    'approved absence binds person and claim dates without private free text',
    () {
      final page = copy(f['sources']);
      final absence = <String, dynamic>{
        'id': 'a' * 32,
        'employee_id': employee,
        'status': 'approved',
        'start_date': '2026-10-20',
        'end_date': '2026-10-21',
        'kind': 'sick',
      };
      page['absences'] = [absence];
      payrollFactSources(page, employee);
      final claim = <String, dynamic>{
        'kind': 'sickness_continued_pay',
        'from': '2026-10-20',
        'to': '2026-10-21',
        'source_absence_id': absence['id'],
        'source_file_ids': f['command']['source_file_ids'],
        'reason': 'Synthetic evidenced entitlement',
      };
      payrollFactInput(employee, page, 'period_case', {
        ...values(),
        'entitlement_decisions': [claim],
      });
      for (final patch in [
        {'employee_id': 'f' * 32},
        {'status': 'requested'},
        {'details': 'Unnecessary private text'},
        {'end_date': '2026-10-19'},
      ]) {
        expect(
          () => payrollFactSources({
            ...page,
            'absences': [
              {...absence, ...patch},
            ],
          }, employee),
          throwsA(isA<ApiException>()),
        );
      }
      for (final patch in [
        {'source_absence_id': 'f' * 32},
        {'from': '2026-10-19'},
      ]) {
        expect(
          () => payrollFactInput(employee, page, 'period_case', {
            ...values(),
            'entitlement_decisions': [
              {...claim, ...patch},
            ],
          }),
          throwsA(isA<ApiException>()),
        );
      }
    },
  );
  test('unsupported entitlement remains documentable but incomplete', () {
    final blockedFact = copy(f['period']);
    blockedFact['plan'] = copy(f['blocked']['plan']);
    expect(
      () => payrollFactRunInput(blockedFact),
      throwsA(isA<ApiException>()),
    );
    blockedFact['plan']['blockers'] = [];
    expect(
      () => payrollFactRunInput(blockedFact),
      throwsA(isA<ApiException>()),
    );
    final body = {
      ...clean(f['command']),
      'details': f['blocked']['source_snapshot']['case_details'],
    };
    payrollFactPreview(f['blocked'], body);
    expect(f['blocked']['can_confirm'], true);
    expect(f['blocked']['can_calculate'], false);
    expect(
      () => payrollFactPreview({
        ...copy(f['blocked']),
        'can_calculate': true,
      }, body),
      throwsA(isA<ApiException>()),
    );
  });
  test(
    'fact receipts bind correction and void to exact historical original',
    () {
      payrollFactValidator(clean(f['terms_command']))(f['terms']);
      payrollFactValidator(clean(f['command']), preview: copy(f['preview']))(
        f['period'],
      );
      payrollFactValidator(
        clean(f['corrected_command']),
        previous: copy(f['period']),
        preview: copy(f['corrected_preview']),
      )(f['corrected']);
      payrollFactValidator(
        clean(f['void_command']),
        previous: copy(f['corrected']),
      )(f['void']);
      final bad = copy(f['void']);
      bad['plan']['gross_minor']++;
      expect(
        () => payrollFactValidator(
          clean(f['void_command']),
          previous: copy(f['corrected']),
        )(bad),
        throwsA(isA<ApiException>()),
      );
      expect(
        payrollFactRunInput(copy(f['period']))['source_schema_version'],
        2,
      );
      expect(
        () => payrollFactRunInput(copy(f['void'])),
        throwsA(isA<ApiException>()),
      );
    },
  );
  test('all three period rules and one effective yearly correction use actual backend fixtures', () async {
    for (final v in [
      {
        'inputs': f['run_input'],
        'preview': f['run_preview'],
        'command': f['run_command'],
        'run': f['run'],
      },
      f['regular'],
      f['transition'],
    ]) {
      payrollCalculation(v['run']['calculation']);
      payrollPreview(v['preview'], copy(v['inputs']));
      payrollReceiptValidator(copy(v['command']), preview: copy(v['preview']))(
        v['run'],
      );
      final bad = copy(v['preview']);
      bad['calculation']['period_details']['plan_hash'] = 'f' * 64;
      expect(
        () => payrollPreview(bad, copy(v['inputs'])),
        throwsA(isA<ApiException>()),
      );
    }
    payrollReceiptValidator(
      copy(f['corrected_run_command']),
      preview: copy(f['corrected_run_preview']),
      previous: copy(f['run']),
    )(f['corrected_run']);
    await payrollLedgerSnapshot(f['ledger'], employee, 2026);
    expect(f['ledger']['ledger']['recorded_months'], 1);
    expect(f['run']['calculation']['net_minor'], 31878);
  });
  test('accepted native fact replay keeps exact command through later sources and module pause', () async {
    final api = FactsApi()..lose = true, session = BusinessSession(api: api);
    await session.load();
    final body = clean(f['terms_command']), key = 'payroll-facts-$employee';
    await expectLater(
      session.command(
        key,
        '/payroll/facts',
        body,
        validateResult: payrollFactValidator(body),
      ),
      throwsA(isA<ApiException>()),
    );
    expect(session.pending(key), true);
    api.paused = true;
    await session.repeatPayrollFactsCommand(employee);
    expect(api.created, 1);
    expect(api.sent.length, 2);
    expect(api.sent[0], api.sent[1]);
    expect(session.pending(key), false);
    session.dispose();
  });
  testWidgets(
    'private mobile fact page opens details and clears them on fresh role withdrawal',
    (tester) async {
      tester.view.physicalSize = const Size(390, 844);
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.resetPhysicalSize);
      addTearDown(tester.view.resetDevicePixelRatio);
      final api = FactsApi(), session = BusinessSession(api: api);
      await session.load();
      await tester.pumpWidget(
        MaterialApp(
          home: BusinessPayrollFactsPage(
            session: session,
            employee: copy(f['employee']),
            onOriginal: (_) async {},
          ),
        ),
      );
      await tester.pumpAndSettle();
      expect(find.text('Beschäftigung und Entgelt erfassen'), findsOneWidget);
      final tile = find.text('15.10.2026 · Fassung 1');
      await tester.ensureVisible(tile);
      await tester.tap(tile);
      await tester.pumpAndSettle();
      expect(find.text(f['terms']['details']['reason']), findsOneWidget);
      expect(tester.takeException(), isNull);
      api.read = false;
      await session.load();
      await tester.pumpAndSettle();
      expect(find.text(f['terms']['details']['reason']), findsNothing);
      expect(find.text('Lohnzeitachsen nicht freigegeben'), findsOneWidget);
      await tester.pumpWidget(const SizedBox.shrink());
      session.dispose();
    },
  );
  testWidgets(
    'new native employment form starts with explicit empty dates and method',
    (tester) async {
      final api = FactsApi(), session = BusinessSession(api: api);
      await session.load();
      await tester.pumpWidget(
        MaterialApp(
          home: BusinessPayrollFactsPage(
            session: session,
            employee: copy(f['employee']),
            onOriginal: (_) async {},
          ),
        ),
      );
      await tester.pumpAndSettle();
      final button = find.text('Beschäftigung und Entgelt erfassen');
      await tester.ensureVisible(button);
      await tester.tap(button);
      await tester.pumpAndSettle();
      final date = find.widgetWithText(
        TextFormField,
        'Belegter Beschäftigungsbeginn',
      );
      expect(tester.widget<TextFormField>(date).controller!.text, '');
      expect(
        tester
            .widget<DropdownButtonFormField<String>>(
              find.byType(DropdownButtonFormField<String>).first,
            )
            .initialValue,
        isNull,
      );
      expect(tester.takeException(), isNull);
      await tester.pumpWidget(const SizedBox.shrink());
      session.dispose();
    },
  );
}

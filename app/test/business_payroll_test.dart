import 'dart:convert';
import 'dart:io';
import 'dart:typed_data';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:smartplan_office/api.dart';
import 'package:smartplan_office/business_payroll.dart';
import 'package:smartplan_office/business_session.dart';

final fixture = jsonDecode(
  File('test/fixtures/payroll_workflow.json').readAsStringSync(),
) as Map<String, dynamic>;
Map<String, dynamic> copy(dynamic v) =>
    Map<String, dynamic>.from(jsonDecode(jsonEncode(v)) as Map);
final employee = copy(fixture['employee']);
final employeeId = employee['id'] as String;
final runKey = 'payroll-run-$employeeId';

class PayrollApi extends OfficeApi {
  PayrollApi() : super(apiVersion: 'v1') {
    token = 'synthetic-payroll-session';
  }
  bool read = true,
      approve = true,
      write = true,
      own = false,
      paused = false,
      lose = false,
      wrong = false,
      wrongEmployee = false;
  int generation = 1, creations = 0;
  final commands = <Map<String, dynamic>>[];
  @override
  Future<dynamic> call(String path, [Map<String, dynamic>? body]) async {
    if (path.startsWith('/api/business/capabilities'))
      return {
        'compatibility_mode': 'business',
        'storage_version': 8,
        'generation': generation,
        'readonly': false,
        'features': ['german_payroll_2026', 'personnel_preparation'],
        'capabilities': [
          'business_payroll',
          'business_personnel_workflow',
          'business_planning',
        ],
        'permissions': [
          if (read) 'personnel.read',
          if (write) 'personnel.write',
          if (approve) 'personnel.approve',
          'personnel.export',
          if (own) 'time.own',
        ],
        'organization': {
          'modules': {
            'personnel': {'enabled': !paused, 'visible': true},
          },
        },
      };
    if (path == '/api/me') return {'id': own ? employee['user_id'] : 'a' * 32};
    if (path == '/api/business/employees') return [employee];
    if (path.startsWith('/api/business/payroll/profiles?'))
      return {
        'employee_id': wrongEmployee ? 'f' * 32 : employeeId,
        'items': [copy(fixture['profile'])],
      };
    if (path.startsWith('/api/business/payroll/runs?'))
      return {
        'employee_id': wrongEmployee ? 'f' * 32 : employeeId,
        'items': creations > 0 ? [copy(fixture['run'])] : [],
      };
    if (path.startsWith('/api/business/personnel/files?'))
      return {
        'employee_id': employeeId,
        'items': own ? [] : [copy(fixture['file'])],
      };
    if (path.startsWith('/api/business/personnel/payroll-preparations?'))
      return {
        'employee_id': employeeId,
        'items': [copy(fixture['preparation'])],
      };
    if (path.startsWith('/api/business/payroll/ledger?'))
      return copy(fixture['ledger']);
    if (path == '/api/business/payroll/rules')
      return {
        'rules': {
          'version': 'synthetic',
          'minijob_monthly_limit_minor': 60300,
          'minijob_annual_limit_minor': 723600,
        },
      };
    if (path == '/api/business/payroll/preview')
      return copy(fixture['preview']);
    if (path == '/api/business/payroll/runs') {
      commands.add(copy(body));
      if (!read || !approve)
        throw const ApiException(403, 'Personalrecht entzogen');
      creations = 1;
      if (lose) {
        lose = false;
        throw const ApiException(0, 'Erfolgsantwort verloren');
      }
      return copy(fixture[wrong ? 'profile' : 'run']);
    }
    if (path.endsWith('/history'))
      return {
        'items': [copy(fixture['run']), copy(fixture['corrected_run'])],
      };
    throw StateError('Unexpected $path');
  }
}

Future<BusinessSession> sessionFor(PayrollApi api) async {
  final session = BusinessSession(api: api);
  await session.load();
  return session;
}

Future<void> visibleTap(WidgetTester tester, Finder finder) async {
  await tester.scrollUntilVisible(
    finder,
    400,
    scrollable: find.byType(Scrollable).first,
    maxScrolls: 50,
  );
  await tester.ensureVisible(finder);
  await tester.tap(finder);
  await tester.pumpAndSettle();
}

void main() {
  test('money and known zero ELStAM never round fractional cents or invent missing inputs', () {
    expect(payrollTaxMinor('0,00'), 0);
    expect(payrollTaxMinor('12.34'), 1234);
    expect(payrollRate('2,9'), '2.900');
    for (final v in ['', '-1', '1e2', '1.001'])
      expect(() => payrollTaxMinor(v), throwsFormatException);
    expect(() => payrollRate('20.001'), throwsFormatException);
  });
  test('profile normalizer separates explicitly selected standard tax and legacy contribution scope', () {
    final values = copy(fixture['profile']['profile']);
    for (final k in [
      'has_children',
      'u1_required',
      'minijob_rv_exempt',
      'pension_other_compulsory',
    ])
      values[k] = values[k] == true ? 'yes' : 'no';
    values['annual_gross'] = '7236';
    values['transition_scope'] = 'none';
    values['regular_tax_scope'] = 'minijob';
    expect(payrollProfileInput(values), fixture['profile']['profile']);
    values['employment_kind'] = 'regular';
    values['regular_tax_scope'] = 'standard';
    expect(() => payrollProfileInput(values), throwsFormatException);
    values['tax_allowance_monthly_minor'] = '0';
    values['tax_addition_monthly_minor'] = '12.34';
    expect(payrollProfileInput(values)['tax_addition_monthly_minor'], 1234);
    values['regular_tax_scope'] = 'social_only';
    expect(
      payrollProfileInput(values).containsKey('tax_allowance_monthly_minor'),
      false,
    );
  });
  test('backend minijob calculation accepts exact 581.29 and rejects fabricated net and totals', () {
    final calc = copy(fixture['run']['calculation']);
    expect(payrollCalculation(calc)['net_minor'], 58129);
    expect(
      () => payrollCalculation({...calc, 'net_minor': 60300}),
      throwsA(isA<ApiException>()),
    );
    expect(
      () => payrollCalculation({...calc, 'employer_social_total_minor': 0}),
      throwsA(isA<ApiException>()),
    );
    calc['scope'] = 'social_contributions_only';
    calc['payroll_calculation_complete'] = false;
    for (final k in [
      'individual_wage_tax_minor',
      'solidarity_minor',
      'church_tax_minor',
      'employee_tax_minor',
      'net_minor',
      'payout_minor',
      'employee_additional_payment_minor',
    ])
      calc[k] = null;
    expect(payrollCalculation(calc)['net_minor'], null);
    expect(
      () => payrollCalculation({...calc, 'net_minor': 0}),
      throwsA(isA<ApiException>()),
    );
  });
  test('preview rejects another employee even when profile and preparation ids match', () {
    final preview = copy(fixture['preview']),
        inputs = copy(preview['source']['input']);
    payrollPreview(preview, inputs);
    preview['source']['profile']['employee_id'] = 'f' * 32;
    expect(() => payrollPreview(preview, inputs), throwsA(isA<ApiException>()));
  });
  test(
    'receipts bind frozen source, exact correction delta and original evidence',
    () {
      payrollReceiptValidator(
        copy(fixture['body']),
        preview: copy(fixture['preview']),
      )(fixture['run']);
      final validate = payrollReceiptValidator(
        copy(fixture['corrected_body']),
        preview: copy(fixture['corrected_preview']),
        previous: copy(fixture['run']),
      );
      validate(fixture['corrected_run']);
      final bad = copy(fixture['corrected_run']);
      bad['delta']['net_minor'] = 0;
      expect(() => validate(bad), throwsA(isA<ApiException>()));
      final body = {
        'employee_id': employeeId,
        'profile': fixture['profile']['profile'],
        'source_file_id': fixture['file']['id'],
        'confirmed': true,
        'revision': 0,
      };
      payrollReceiptValidator(body, original: copy(fixture['file']))(
        fixture['profile'],
      );
      expect(
        () => payrollReceiptValidator(
          body,
          original: {...copy(fixture['file']), 'sha256': 'f' * 64},
        )(fixture['profile']),
        throwsA(isA<ApiException>()),
      );
    },
  );
  test('historical JSON validates exact envelope hash rather than only current record equality', () async {
    for (final key in ['run', 'corrected_run']) {
      final record = copy(fixture[key]);
      expect(
        (await payrollExportAttachment(
          record,
          Uint8List.fromList(utf8.encode(jsonEncode(record))),
          'json',
        )).filename,
        contains('-v${record['revision']}.json'),
      );
    }
    final bad = {...copy(fixture['run']), 'content_hash': 'f' * 64};
    await expectLater(
      payrollExportAttachment(
        bad,
        Uint8List.fromList(utf8.encode(jsonEncode(bad))),
        'json',
      ),
      throwsA(isA<ApiException>()),
    );
  });
  test('lost ACK remains pending through fresh rights revocation and retries original nonce and body', () async {
    final api = PayrollApi()..lose = true, session = await sessionFor(api);
    addTearDown(session.dispose);
    addTearDown(api.dispose);
    final body = copy(fixture['body']), proof = copy(fixture['preview']);
    await expectLater(
      session.command(
        runKey,
        '/payroll/runs',
        body,
        validateResult: payrollReceiptValidator(body, preview: proof),
      ),
      throwsA(isA<ApiException>()),
    );
    body['gross_minor'] = 1;
    proof['calculation']['net_minor'] = 0;
    api.read = false;
    await expectLater(
      session.repeatPayrollCommand(employeeId),
      throwsA(isA<ApiException>()),
    );
    expect(api.commands.length, 1);
    expect(session.pending(runKey), true);
    api.read = true;
    api.generation++;
    await session.repeatPayrollCommand(employeeId);
    expect(session.pending(runKey), false);
    expect(api.commands[0], api.commands[1]);
    expect(api.creations, 1);
  });
  test('mismatched acknowledgment retains request and employee-bound state prevents replay', () async {
    final api = PayrollApi()..wrong = true, session = await sessionFor(api);
    addTearDown(session.dispose);
    addTearDown(api.dispose);
    await expectLater(
      session.command(
        runKey,
        '/payroll/runs',
        copy(fixture['body']),
        validateResult: payrollReceiptValidator(
          copy(fixture['body']),
          preview: copy(fixture['preview']),
        ),
      ),
      throwsA(isA<ApiException>()),
    );
    api.wrong = false;
    api.wrongEmployee = true;
    await expectLater(
      session.repeatPayrollCommand(employeeId),
      throwsA(isA<ApiException>()),
    );
    expect(api.commands.length, 1);
    expect(session.pending(runKey), true);
  });
  test('regular PAP receipt requires provenance, exact taxes and net', () {
    final run = copy(fixture['regular_run']),
        preview = copy(fixture['regular_preview']);
    expect(payrollCalculation(run['calculation'])['net_minor'], 233584);
    expect(run['calculation']['individual_wage_tax_minor'], 40658);
    payrollPreview(preview, copy(preview['source']['input']));
    payrollReceiptValidator(copy(fixture['regular_body']), preview: preview)(
      run,
    );
    final bad = copy(run['calculation']);
    bad['employee_tax_minor'] += 1;
    expect(() => payrollCalculation(bad), throwsA(isA<ApiException>()));
    expect(
      () => payrollCalculation({
        ...copy(run['calculation']),
        'pap_provenance_sha256': '',
      }),
      throwsA(isA<ApiException>()),
    );
  });
  test('regular correction retains extended tax delta fields and unknown prior tax', () {
    final validate = payrollReceiptValidator(
      copy(fixture['upgraded_regular_body']),
      preview: copy(fixture['upgraded_regular_preview']),
      previous: copy(fixture['legacy_regular_run']),
    );
    validate(fixture['upgraded_regular_run']);
    final bad = copy(fixture['upgraded_regular_run']);
    bad['delta']['individual_wage_tax_minor'] = 0;
    expect(() => validate(bad), throwsA(isA<ApiException>()));
  });
  test(
    'annual snapshot sums only effective correction and exposes missing months',
    () async {
      final view = await payrollLedgerSnapshot(
            fixture['ledger'],
            employeeId,
            2026,
          ),
          ledger = businessMap(view['ledger']);
      expect(ledger['totals']['net_minor'], 60300);
      expect(ledger['totals']['gross_minor'], 60300);
      expect(ledger['totals']['individual_wage_tax_minor'], 0);
      expect(ledger['missing_months'], hasLength(11));
      expect(ledger['annual_totals_complete'], false);
      expect(ledger['correction_history'], hasLength(1));
      final bad = copy(view);
      bad['ledger']['totals']['net_minor'] += 2171;
      await expectLater(
        payrollLedgerSnapshot(bad, employeeId, 2026),
        throwsA(isA<ApiException>()),
      );
      await expectLater(
        payrollLedgerSnapshot(view, 'f' * 32, 2026),
        throwsA(isA<ApiException>()),
      );
    },
  );
  test('empty and partial annual snapshots preserve unknown money and verify hashes', () async {
    final empty = await payrollLedgerSnapshot(
      fixture['empty_ledger'],
      employeeId,
      2025,
    );
    expect(empty['ledger']['totals']['gross_minor'], null);
    expect(empty['ledger']['totals']['net_minor'], null);
    final partial = copy(fixture['partial_ledger']),
        id = partial['ledger']['employee']['id'] as String;
    await payrollLedgerSnapshot(partial, id, 2026);
    expect(partial['ledger']['totals']['net_minor'], null);
    partial['ledger']['snapshot_hash'] = 'f' * 64;
    await expectLater(
      payrollLedgerSnapshot(partial, id, 2026),
      throwsA(isA<ApiException>()),
    );
  });
  test('annual export validates manifest size and exact bytes', () async {
    dynamic ordered(dynamic v) => v is List
        ? v.map(ordered).toList()
        : v is Map
        ? {
            for (final key in v.keys.map((k) => '$k').toList()..sort())
              key: ordered(v[key]),
          }
        : v;
    final view = copy(fixture['ledger']),
        bytes = Uint8List.fromList(
          utf8.encode(jsonEncode(ordered(view['ledger']))),
        );
    expect(
      (await payrollLedgerExportAttachment(view, bytes, 'json')).filename,
      contains('2026'),
    );
    await expectLater(
      payrollLedgerExportAttachment(
        view,
        Uint8List.fromList([1, 2, 3]),
        'json',
      ),
      throwsA(isA<ApiException>()),
    );
  });
  testWidgets(
    'annual overview shows missing periods and never adds a correction twice',
    (tester) async {
      await tester.binding.setSurfaceSize(const Size(1100, 900));
      addTearDown(() => tester.binding.setSurfaceSize(null));
      final api = PayrollApi(), session = await sessionFor(api);
      addTearDown(api.dispose);
      await tester.pumpWidget(
        MaterialApp(
          home: BusinessPayrollPage(session: session, employee: employee),
        ),
      );
      await tester.pumpAndSettle();
      await visibleTap(tester, find.text('Jahresübersicht öffnen'));
      await tester.enterText(
        find.byKey(const ValueKey('business-field-year')),
        '2026',
      );
      await tester.tap(find.text('Jahresübersicht laden'));
      await tester.pumpAndSettle();
      expect(find.text('Lohn-Jahresübersicht 2026'), findsOneWidget);
      expect(
        find.text(
          '1 von 12 Monaten erfasst. Summen umfassen die jeweils letzte wirksame Monatsfassung.',
        ),
        findsOneWidget,
      );
      await tester.scrollUntilVisible(
        find.text('Jahresübersicht als JSON'),
        400,
        scrollable: find.byType(Scrollable).first,
        maxScrolls: 100,
      );
      expect(find.text('Jahresübersicht als JSON'), findsOneWidget);
      expect(tester.takeException(), null);
      await tester.pumpWidget(const SizedBox());
      session.dispose();
    },
  );
  testWidgets(
    'pending run survives closing page and renders a recoverable exact retry',
    (tester) async {
      await tester.binding.setSurfaceSize(const Size(1100, 900));
      addTearDown(() => tester.binding.setSurfaceSize(null));
      final api = PayrollApi()..lose = true, session = await sessionFor(api);
      addTearDown(api.dispose);
      await expectLater(
        session.command(
          runKey,
          '/payroll/runs',
          copy(fixture['body']),
          validateResult: payrollReceiptValidator(
            copy(fixture['body']),
            preview: copy(fixture['preview']),
          ),
        ),
        throwsA(isA<ApiException>()),
      );
      await tester.pumpWidget(
        MaterialApp(
          home: BusinessPayrollPage(session: session, employee: employee),
        ),
      );
      await tester.pumpAndSettle();
      expect(find.text('Berechnungsbestätigung offen'), findsOneWidget);
      await tester.pumpWidget(const SizedBox());
      await tester.pumpAndSettle();
      await tester.pumpWidget(
        MaterialApp(
          home: BusinessPayrollPage(session: session, employee: employee),
        ),
      );
      await tester.pumpAndSettle();
      await visibleTap(
        tester,
        find.text('Ursprünglichen Auftrag erneut senden'),
      );
      expect(session.pending(runKey), false);
      expect(api.commands[0], api.commands[1]);
      expect(tester.takeException(), null);
      await tester.pumpWidget(const SizedBox());
      session.dispose();
    },
  );
  testWidgets(
    'own payroll hides staff writes and loses all displayed data after access withdrawal',
    (tester) async {
      final api = PayrollApi()
            ..read = false
            ..write = false
            ..approve = false
            ..own = true
            ..creations = 1,
          session = await sessionFor(api);
      addTearDown(api.dispose);
      await tester.pumpWidget(
        MaterialApp(
          home: BusinessPayrollPage(session: session, employee: employee),
        ),
      );
      await tester.pumpAndSettle();
      expect(find.text('Lohnberechnung nicht freigegeben'), findsNothing);
      final newProfile = find.widgetWithText(
        OutlinedButton,
        'Neues Lohnprofil erfassen',
      );
      await tester.scrollUntilVisible(
        newProfile,
        400,
        scrollable: find.byType(Scrollable).first,
        maxScrolls: 50,
      );
      expect(tester.widget<OutlinedButton>(newProfile).onPressed, null);
      api.own = false;
      api.generation++;
      await session.load();
      await tester.pumpAndSettle();
      expect(find.text('Lohnberechnung nicht freigegeben'), findsOneWidget);
      expect(find.text('Berechnung Fassung 1'), findsNothing);
      expect(tester.takeException(), null);
      await tester.pumpWidget(const SizedBox());
      session.dispose();
    },
  );
}

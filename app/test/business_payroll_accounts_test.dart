import 'dart:convert';
import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:smartplan_office/api.dart';
import 'package:smartplan_office/business_payroll.dart';
import 'package:smartplan_office/business_payroll_accounts.dart';
import 'package:smartplan_office/business_session.dart';

final f = jsonDecode(
  File('test/fixtures/payroll_accounts.json').readAsStringSync(),
) as Map<String, dynamic>;
Map<String, dynamic> copy(dynamic value) =>
    Map<String, dynamic>.from(jsonDecode(jsonEncode(value)) as Map);
final employee = copy(f['employee']);
final employeeId = employee['id'] as String;
final pendingKey = 'payroll-account-$employeeId';
Map<String, dynamic> values(String kind) {
  final d = copy(f[kind]['details']), result = copy(d);
  result['standard_case_confirmed'] = true;
  for (final key in result.keys.toList())
    if (key.endsWith('_minor'))
      result[key] = (result[key] / 100).toStringAsFixed(2);
  for (final name in ['profile', 'run', 'identity'])
    if (d['${name}_id'] != null)
      result['${name}_ref'] = '${d['${name}_id']}@${d['${name}_revision']}';
  for (var i = 0; i < (d['payments'] as List? ?? []).length; i++) {
    final p = d['payments'][i];
    result['paid_on_$i'] = p['paid_on'];
    result['amount_$i'] = (p['amount_minor'] / 100).toStringAsFixed(2);
    result['reference_$i'] = p['payment_reference'];
  }
  return result;
}

Map<String, List<Map<String, dynamic>>> sources() => {
  'profiles': [copy(f['profile'])],
  'runs': [copy(f['run'])],
  'identities': [copy(f['identity'])],
};

class AccountApi extends OfficeApi {
  AccountApi() : super(apiVersion: 'v1') {
    token = 'synthetic-account-session';
  }
  bool read = true,
      write = true,
      approve = true,
      own = false,
      lose = false,
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
        'capabilities': [
          'business_payroll',
          'business_payroll_accounts',
          'business_personnel_workflow',
          'business_planning',
        ],
        'features': [
          'german_payroll_2026',
          'payroll_wage_account',
          'personnel_preparation',
        ],
        'permissions': [
          if (read) 'personnel.read',
          if (write) 'personnel.write',
          if (approve) 'personnel.approve',
          if (own) 'time.own',
        ],
      };
    if (path == '/api/me') return {'id': own ? employee['user_id'] : 'f' * 32};
    if (path == '/api/business/employees') return [employee];
    if (path.startsWith('/api/business/payroll/account-records?'))
      return {
        'employee_id': wrongEmployee ? 'f' * 32 : employeeId,
        'items': [copy(f['identity']), copy(f['payment'])],
      };
    if (path.startsWith('/api/business/payroll/profiles?'))
      return {
        'employee_id': employeeId,
        'items': [copy(f['profile'])],
      };
    if (path.startsWith('/api/business/payroll/runs?'))
      return {
        'employee_id': employeeId,
        'items': [copy(f['run'])],
      };
    if (path.startsWith('/api/business/personnel/files?'))
      return {
        'employee_id': employeeId,
        'items': [copy(f['file'])],
      };
    if (path == '/api/business/payroll/account-records') {
      commands.add(copy(body));
      if (!read || (body!['kind'] == 'identity' ? !write : !approve))
        throw const ApiException(403, 'Nachweisrecht entzogen');
      creations = 1;
      if (lose) {
        lose = false;
        throw const ApiException(0, 'Erfolgsantwort verloren');
      }
      return copy(f[body['kind']]);
    }
    if (path.endsWith('/history'))
      return {
        'items': [copy(f['identity']), copy(f['corrected_identity'])],
      };
    throw StateError(path);
  }
}

Future<BusinessSession> sessionFor(AccountApi api) async {
  final session = BusinessSession(api: api);
  await session.load();
  return session;
}

void main() {
  test('employee top-ups remain signed exact cents; missing amounts are never inferred', () {
    expect(payrollAccountMinor('-3,80', signed: true), -380);
    expect(payrollAccountMinor('0'), 0);
    for (final v in ['', '3.801', '1e2'])
      expect(() => payrollAccountMinor(v, signed: true), throwsFormatException);
    expect(() => payrollAccountMinor('-3.80'), throwsFormatException);
  });
  test('identity detail builder binds profile revision and preserves unknown employment end', () {
    expect(
      payrollAccountDetails('identity', values('identity'), sources()),
      f['identity']['details'],
    );
    final v = values('identity')..['employment_to'] = '';
    expect(
      payrollAccountDetails('identity', v, sources())['employment_to'],
      null,
    );
    v['tax_allowance_yearly_minor'] = '';
    expect(
      () => payrollAccountDetails('identity', v, sources()),
      throwsFormatException,
    );
  });
  test(
    'actual payment parts preserve each date reference and exact amount',
    () {
      final actual = payrollAccountDetails(
        'payment',
        values('payment'),
        sources(),
        count: 2,
      );
      expect(actual, f['payment']['details']);
      expect(actual['payments'][0]['amount_minor'], 30000);
      expect(actual['payments'][1]['amount_minor'], 28129);
      expect(
        () => payrollAccountDetails(
          'payment',
          {...values('payment'), 'amount_0': '0'},
          sources(),
          count: 2,
        ),
        throwsFormatException,
      );
      expect(
        () => payrollAccountDetails(
          'payment',
          {...values('payment'), 'identity_ref': 'foreign'},
          sources(),
          count: 2,
        ),
        throwsFormatException,
      );
    },
  );
  test('account receipts bind evidence, source revisions and immutable correction ancestry', () {
    payrollAccountReceiptValidator(copy(f['identity_body']), copy(f['file']))(
      f['identity'],
    );
    payrollAccountReceiptValidator(copy(f['payment_body']), copy(f['file']))(
      f['payment'],
    );
    final validate = payrollAccountReceiptValidator(
      copy(f['corrected_payment_body']),
      copy(f['file']),
      previous: copy(f['payment']),
    );
    validate(f['corrected_payment']);
    final changedContent = copy(f['payment']);
    changedContent['sources']['run']['calculation']['net_minor'] += 1;
    expect(
      () => payrollAccountReceiptValidator(
        copy(f['payment_body']),
        copy(f['file']),
        sourceEvidence: {'run': f['run'], 'identity': f['identity']},
      )(changedContent),
      throwsA(isA<ApiException>()),
    );
    final bad = copy(f['corrected_payment']);
    bad['sources']['identity']['revision'] = 1;
    expect(() => validate(bad), throwsA(isA<ApiException>()));
    expect(
      () => payrollAccountRecord(f['identity'], 'f' * 32),
      throwsA(isA<ApiException>()),
    );
  });
  test('complete supported wage account and carryover remain separate from complete calendar and digital audit approval', () async {
    final local = await payrollLedgerSnapshot(f['ledger'], employeeId, 2026);
    expect(local['ledger']['statutory_wage_account_complete'], true);
    expect(local['ledger']['calendar_year_complete'], false);
    expect(local['ledger']['digital_audit_export_compliant'], false);
    final carry = copy(f['carry_case']);
    final view = await payrollLedgerSnapshot(
      carry['ledger'],
      carry['employee']['id'],
      2026,
    );
    expect(view['ledger']['months'][9]['run_id'], null);
    expect(view['ledger']['months'][9]['carryover_id'], carry['carry']['id']);
    expect(view['ledger']['totals']['net_minor'], 58129);
  });
  test('account pending command preserves exact source values across rights loss and generation change', () async {
    final api = AccountApi()..lose = true, session = await sessionFor(api);
    addTearDown(session.dispose);
    addTearDown(api.dispose);
    final body = copy(f['identity_body']);
    await expectLater(
      session.command(
        pendingKey,
        '/payroll/account-records',
        body,
        validateResult: payrollAccountReceiptValidator(body, copy(f['file'])),
      ),
      throwsA(isA<ApiException>()),
    );
    body['details']['tax_id'] = '99999999999';
    api.read = false;
    await expectLater(
      session.repeatPayrollAccountCommand(employeeId),
      throwsA(isA<ApiException>()),
    );
    expect(api.commands.length, 1);
    expect(session.pending(pendingKey), true);
    api.read = true;
    api.write = false;
    await expectLater(
      session.repeatPayrollAccountCommand(employeeId),
      throwsA(isA<ApiException>()),
    );
    expect(api.commands.length, 1);
    api.write = true;
    api.generation++;
    await session.repeatPayrollAccountCommand(employeeId);
    expect(api.commands[0], api.commands[1]);
    expect(api.creations, 1);
    expect(session.pending(pendingKey), false);
  });
  test(
    'payment pending requires approval and matching employee collection',
    () async {
      final api = AccountApi()..lose = true, session = await sessionFor(api);
      addTearDown(session.dispose);
      addTearDown(api.dispose);
      final body = copy(f['payment_body']);
      await expectLater(
        session.command(
          pendingKey,
          '/payroll/account-records',
          body,
          validateResult: payrollAccountReceiptValidator(body, copy(f['file'])),
        ),
        throwsA(isA<ApiException>()),
      );
      api.approve = false;
      await expectLater(
        session.repeatPayrollAccountCommand(employeeId),
        throwsA(isA<ApiException>()),
      );
      expect(api.commands.length, 1);
      api.approve = true;
      api.wrongEmployee = true;
      await expectLater(
        session.repeatPayrollAccountCommand(employeeId),
        throwsA(isA<ApiException>()),
      );
      expect(api.commands.length, 1);
      expect(session.pending(pendingKey), true);
    },
  );
  testWidgets(
    'account pending survives page closure and repeats original identity once',
    (tester) async {
      await tester.binding.setSurfaceSize(const Size(1100, 900));
      addTearDown(() => tester.binding.setSurfaceSize(null));
      final api = AccountApi()..lose = true, session = await sessionFor(api);
      addTearDown(api.dispose);
      final body = copy(f['identity_body']);
      await expectLater(
        session.command(
          pendingKey,
          '/payroll/account-records',
          body,
          validateResult: payrollAccountReceiptValidator(body, copy(f['file'])),
        ),
        throwsA(isA<ApiException>()),
      );
      Widget page() => MaterialApp(
        home: BusinessPayrollAccountsPage(
          session: session,
          employee: employee,
          onOriginal: (_) async {},
        ),
      );
      await tester.pumpWidget(page());
      await tester.pumpAndSettle();
      expect(find.text('Nachweisbestätigung offen'), findsOneWidget);
      await tester.pumpWidget(const SizedBox());
      await tester.pumpWidget(page());
      await tester.pumpAndSettle();
      await tester.tap(find.text('Ursprünglichen Nachweis erneut senden'));
      await tester.pumpAndSettle();
      expect(session.pending(pendingKey), false);
      expect(api.commands[0], api.commands[1]);
      expect(tester.takeException(), null);
      await tester.pumpWidget(const SizedBox());
      session.dispose();
    },
  );
  testWidgets(
    'own account view cannot write and is removed on own permission withdrawal',
    (tester) async {
      final api = AccountApi()
            ..read = false
            ..write = false
            ..approve = false
            ..own = true,
          session = await sessionFor(api);
      addTearDown(api.dispose);
      await tester.pumpWidget(
        MaterialApp(
          home: BusinessPayrollAccountsPage(
            session: session,
            employee: employee,
            onOriginal: (_) async {},
          ),
        ),
      );
      await tester.pumpAndSettle();
      expect(find.text('Lohnkonto nicht freigegeben'), findsNothing);
      expect(
        find.text('Stamm- und Steuermerkmalsnachweis erfassen'),
        findsNothing,
      );
      api.own = false;
      api.generation++;
      await session.load();
      await tester.pumpAndSettle();
      expect(find.text('Lohnkonto nicht freigegeben'), findsOneWidget);
      expect(tester.takeException(), null);
      await tester.pumpWidget(const SizedBox());
      session.dispose();
    },
  );
}

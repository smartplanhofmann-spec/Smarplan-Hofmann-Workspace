import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:smartplan_office/api.dart';
import 'package:smartplan_office/business_payroll.dart';
import 'package:smartplan_office/business_payroll_accounts.dart';
import 'package:smartplan_office/business_session.dart';

final f = jsonDecode(
  File('test/fixtures/payroll_zero_account.json').readAsStringSync(),
) as Map<String, dynamic>;
Map<String, dynamic> copy(dynamic v) =>
    Map<String, dynamic>.from(jsonDecode(jsonEncode(v)) as Map);
String get employeeId => f['employee']['id'];
String ref(dynamic v) => '${v['id']}@${v['revision']}';
Map<String, List<Map<String, dynamic>>> sources() => {
  'profiles': businessItems(f['sources']['profiles']),
  'runs': [copy(f['run'])],
  'identities': [copy(f['identity'])],
};
Map<String, dynamic> values() => {
  'run_ref': ref(f['run']),
  'identity_ref': ref(f['identity']),
  'tax_free_payments_minor': '0.00',
  'tax_free_basis': '',
  'standard_case_confirmed': true,
};

class ZeroAccountApi extends OfficeApi {
  ZeroAccountApi() : super(apiVersion: 'v1') {
    token = 'synthetic-zero-account';
  }
  bool read = true, approve = true, lose = false, wrong = false;
  int savedRevision = 0, creations = 0;
  final sent = <Map<String, dynamic>>[];
  Completer<dynamic>? delayedHistory;
  @override
  Future<dynamic> call(String path, [Map<String, dynamic>? body]) async {
    if (path.startsWith('/api/business/capabilities'))
      return {
        'compatibility_mode': 'business',
        'storage_version': 10,
        'generation': 1,
        'readonly': false,
        'features': ['german_payroll_2026', 'payroll_wage_account'],
        'capabilities': ['business_payroll', 'business_payroll_accounts'],
        'permissions': [
          if (read) 'personnel.read',
          if (approve) 'personnel.approve',
          'personnel.write',
        ],
      };
    if (path == '/api/me') return {'id': 'f' * 32};
    if (path == '/api/business/employees') return [copy(f['employee'])];
    if (path.startsWith('/api/business/payroll/account-records?'))
      return {
        'employee_id': employeeId,
        'items': [
          ...businessItems(f['records_before']['items']),
          if (savedRevision > 0)
            copy(f[savedRevision == 1 ? 'saved' : 'corrected']),
        ],
      };
    if (path.startsWith('/api/business/payroll/profiles?'))
      return {'employee_id': employeeId, 'items': f['sources']['profiles']};
    if (path.startsWith('/api/business/payroll/runs?'))
      return {
        'employee_id': employeeId,
        'items': [copy(f['run'])],
      };
    if (path.startsWith('/api/business/personnel/files?'))
      return {'employee_id': employeeId, 'items': f['sources']['files']};
    if (path == '/api/business/payroll/account-records') {
      sent.add(copy(body));
      final revision = body!['revision'] + 1;
      if (revision > savedRevision) {
        savedRevision = revision;
        creations++;
      }
      if (lose) {
        lose = false;
        throw const ApiException(0, 'Angenommene Antwort synthetisch verloren');
      }
      final value = copy(f[body['revision'] == 0 ? 'saved' : 'corrected']);
      if (wrong) value['sources']['run']['calculation']['net_minor'] = 1;
      return value;
    }
    if (path.endsWith('/history'))
      return delayedHistory?.future ?? copy(f['history']);
    throw StateError(path);
  }
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  test('actual accepted zero-net original correction and ledger retain no fictitious cash and open statutory gaps', () async {
    expect(payrollAccountNoPaymentDue(f['run']), true);
    expect(
      payrollAccountDetails('payment', values(), sources()),
      f['command']['details'],
    );
    payrollAccountReceiptValidator(
      copy(f['command']),
      copy(f['saved']['source_file']),
      sourceEvidence: {'run': f['run'], 'identity': f['identity']},
    )(f['saved']);
    payrollAccountReceiptValidator(
      copy(f['correction_body']),
      copy(f['corrected']['source_file']),
      previous: copy(f['saved']),
      sourceEvidence: {'run': f['run'], 'identity': f['identity']},
    )(f['corrected']);
    for (final r in businessItems(f['history']))
      payrollAccountRecord(r, employeeId, kind: 'payment');
    final view = await payrollLedgerSnapshot(f['ledger'], employeeId, 2026),
        ledger = view['ledger'];
    expect(
      payrollAccountPaymentStatus(
        copy(ledger['months'][9]),
        ledger['account_records'],
        employeeId,
      ),
      'no_payment_due',
    );
    expect(ledger['statutory_wage_account_complete'], false);
    expect(
      ledger['account_completeness_issues'],
      contains('unpaid_statutory_marker_requires_evidence'),
    );
    expect(
      latin1.decode(base64Decode(f['ledger_pdf_base64'])),
      contains('Keine Nettozahlung geschuldet'),
    );
  });
  test('missing old malformed or substituted source3 data never authorizes empty payments', () {
    for (final change in <void Function(Map<String, dynamic>)>[
      (r) => r['source']['source_schema_version'] = 1,
      (r) => r['calculation']['net_minor'] = null,
      (r) => r['calculation']['net_minor'] = 1,
      (r) => r['confirmed'] = false,
      (r) => r['calculation']['payroll_calculation_complete'] = false,
      (r) => r['source']['calculation_case']['plan']['plan_hash'] = 'f' * 64,
      (r) =>
          r['source']['calculation_case']['sources']['employee_id'] = 'f' * 32,
    ]) {
      final r = copy(f['run']);
      change(r);
      expect(
        () => payrollAccountDetails('payment', values(), {
          ...sources(),
          'runs': [r],
        }),
        throwsA(anyOf(isA<ApiException>(), isA<FormatException>())),
      );
    }
    expect(
      () => payrollAccountDetails(
        'payment',
        {
          ...values(),
          'amount_0': '0',
          'paid_on_0': '2026-10-31',
          'reference_0': 'No fictitious cash',
        },
        sources(),
        count: 1,
      ),
      throwsFormatException,
    );
    expect(
      () => payrollAccountDetails('payment', {
        ...values(),
        'standard_case_confirmed': false,
      }, sources()),
      throwsFormatException,
    );
    for (final change in <void Function(Map<String, dynamic>)>[
      (m) => m['wage_account'].remove('payment_status'),
      (m) => m['wage_account']['payment_status'] = 'payments_evidenced',
      (m) => m['wage_account']['payable_minor'] = 1,
      (m) => m['wage_account']['payment_ref']['revision'] = 99,
      (m) => m['revision']++,
    ]) {
      final m = copy(f['ledger']['ledger']['months'][9]);
      change(m);
      expect(
        () => payrollAccountPaymentStatus(
          m,
          f['ledger']['ledger']['account_records'],
          employeeId,
        ),
        throwsA(isA<ApiException>()),
      );
    }
  });
  test('zero account original replay retains validation and nonce across missing approval and a false receipt', () async {
    final api = ZeroAccountApi()..lose = true;
    final current = BusinessSession(api: api);
    addTearDown(current.dispose);
    addTearDown(api.dispose);
    await current.load();
    final body = copy(f['command'])..remove('request_id'),
        key = 'payroll-account-$employeeId';
    await expectLater(
      current.command(
        key,
        '/payroll/account-records',
        body,
        validateResult: payrollAccountReceiptValidator(
          body,
          copy(f['saved']['source_file']),
          sourceEvidence: {'run': f['run'], 'identity': f['identity']},
        ),
      ),
      throwsA(isA<ApiException>()),
    );
    api.approve = false;
    await expectLater(
      current.repeatPayrollAccountCommand(employeeId),
      throwsA(isA<ApiException>()),
    );
    expect(api.sent.length, 1);
    api.approve = true;
    api.wrong = true;
    await expectLater(
      current.repeatPayrollAccountCommand(employeeId),
      throwsA(isA<ApiException>()),
    );
    expect(current.pending(key), true);
    api.wrong = false;
    await current.repeatPayrollAccountCommand(employeeId);
    expect(api.sent.length, 3);
    expect(api.sent.first, api.sent.last);
    expect(api.creations, 1);
    expect(current.pending(key), false);
  });
  testWidgets(
    'rendered zero-net selection requires original and both confirmations then replays and corrects without cash fields',
    (tester) async {
      await tester.binding.setSurfaceSize(const Size(1100, 1000));
      addTearDown(() => tester.binding.setSurfaceSize(null));
      final api = ZeroAccountApi();
      final current = BusinessSession(api: api);
      await current.load();
      final opened = <Map<String, dynamic>>[];
      await tester.pumpWidget(
        MaterialApp(
          home: BusinessPayrollAccountsPage(
            session: current,
            employee: copy(f['employee']),
            onOriginal: (v) async {
              opened.add(copy(v));
            },
          ),
        ),
      );
      await tester.pumpAndSettle();
      Future<void> tapFinder(Finder target) async {
        if (target.evaluate().isEmpty)
          await tester.scrollUntilVisible(
            target,
            400,
            scrollable: find.byType(Scrollable).first,
            maxScrolls: 30,
          );
        await tester.ensureVisible(target);
        await tester.pumpAndSettle();
        await tester.tap(target);
        await tester.pumpAndSettle();
      }

      Future<void> tap(String label) async {
        final matches = find.text(label);
        if (matches.evaluate().isEmpty)
          await tester.scrollUntilVisible(
            matches,
            400,
            scrollable: find.byType(Scrollable).first,
            maxScrolls: 30,
          );
        await tapFinder(matches.last);
      }

      Future<void> choose(String label, String value) async {
        final field = find.byWidgetPredicate(
          (w) =>
              w is DropdownButtonFormField<String> &&
              w.decoration.labelText == label,
        );
        await tester.ensureVisible(field);
        await tester.pumpAndSettle();
        final dropdown = tester.widget<DropdownButton<String>>(
          find.descendant(
            of: field,
            matching: find.byType(DropdownButton<String>),
          ),
        );
        final text =
            (dropdown.items!.firstWhere((item) => item.value == value).child
                    as Text)
                .data!;
        await tester.tap(field);
        await tester.pumpAndSettle();
        await tap(text);
      }

      Future<void> enter(String name, String value) async {
        final field = find.byKey(ValueKey('business-field-$name'));
        await tester.ensureVisible(field);
        await tester.pumpAndSettle();
        await tester.enterText(field, value);
        await tester.pumpAndSettle();
      }

      Future<void> confirmZero() async {
        expect(
          find.byKey(const ValueKey('business-field-count')),
          findsNothing,
        );
        expect(
          find.byKey(const ValueKey('business-field-amount_0')),
          findsNothing,
        );
        expect(
          find.byKey(const ValueKey('business-field-paid_on_0')),
          findsNothing,
        );
        for (final toggle in tester.widgetList<SwitchListTile>(
          find.byType(SwitchListTile),
        ))
          expect(toggle.value, false);
        await choose(
          'Gültiger Stamm- und Steuermerkmalsnachweis',
          ref(f['identity']),
        );
        await enter('tax_free_payments_minor', '0.00');
        await choose(
          'Geschütztes Original des Nachweises',
          f['saved']['source_file']['id'],
        );
        await tap(
          'Ich habe ausschließlich die im ausgewählten Lohnlauf belegten Entgelte und Nettoabzüge ohne weitere unberücksichtigte Sachverhalte geprüft.',
        );
        await tap(
          'Ich bestätige den belegten Nullnetto-Nachweis und die ausgewählten Quellfassungen. Gesonderte Steuer- und Beitragsabführungen bleiben getrennt nachzuweisen.',
        );
      }

      await tap('Tatsächliche Lohnzahlung erfassen');
      expect(
        find.text('Abgerechneten Lauf für den Lohnkontonachweis auswählen'),
        findsOneWidget,
      );
      await choose('Abgeschlossene Monatsberechnung', ref(f['run']));
      await tap('Ausgewählten Lauf prüfen');
      expect(
        find.text('Erfassung · Keine Nettozahlung geschuldet'),
        findsOneWidget,
      );
      await confirmZero();
      api.lose = true;
      await tap('Geprüften Lohnkontonachweis speichern');
      expect(current.pending('payroll-account-$employeeId'), true);
      await tap('Schließen');
      await tap('Ursprünglichen Nachweis erneut senden');
      expect(api.sent.first, api.sent.last);
      expect(api.creations, 1);
      expect(api.sent.first['details']['payments'], isEmpty);
      final card = find.ancestor(
        of: find.text('Tatsächliche Lohnzahlung · Fassung 1'),
        matching: find.byType(Card),
      );
      await tapFinder(
        find.descendant(
          of: card,
          matching: find.text('Nachweisoriginal öffnen'),
        ),
      );
      expect(opened.single['sha256'], f['saved']['source_file']['sha256']);
      await tapFinder(
        find.descendant(of: card, matching: find.text('Nachweis berichtigen')),
      );
      await tap('Ausgewählten Lauf prüfen');
      await confirmZero();
      await enter(
        'correction_reason',
        f['correction_body']['correction_reason'],
      );
      await tap('Geprüften Lohnkontonachweis speichern');
      expect(api.creations, 2);
      expect(api.sent.last['details'], f['correction_body']['details']);
      expect(api.sent.last['revision'], 1);
      expect(
        api.sent.last['correction_reason'],
        f['correction_body']['correction_reason'],
      );
      expect(tester.takeException(), null);
      await tester.pumpWidget(const SizedBox.shrink());
      current.dispose();
      api.dispose();
    },
  );
  testWidgets(
    'account closes on approve withdrawal and drops private history failures after background',
    (tester) async {
      final api = ZeroAccountApi();
      final current = BusinessSession(api: api);
      await current.load();
      await tester.pumpWidget(
        MaterialApp(
          home: BusinessPayrollAccountsPage(
            session: current,
            employee: copy(f['employee']),
            onOriginal: (_) async {},
          ),
        ),
      );
      await tester.pumpAndSettle();
      await tester.tap(find.text('Tatsächliche Lohnzahlung erfassen'));
      await tester.pumpAndSettle();
      api.approve = false;
      await current.load();
      await tester.pumpAndSettle();
      expect(
        find.text('Abgerechneten Lauf für den Lohnkontonachweis auswählen'),
        findsNothing,
      );
      api.approve = true;
      await tester.tap(find.byTooltip('Rechte und Nachweise aktualisieren'));
      await tester.pumpAndSettle();
      api.delayedHistory = Completer<dynamic>();
      final button = find.text('Nachweishistorie').first;
      await tester.ensureVisible(button);
      await tester.pumpAndSettle();
      await tester.tap(button);
      await tester.pump();
      tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.paused);
      await tester.pump();
      api.delayedHistory!.completeError(
        const ApiException(500, 'PRIVATE_OLD_ACCOUNT_HISTORY'),
      );
      await tester.pumpAndSettle();
      tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.resumed);
      await tester.pumpAndSettle();
      expect(find.text('PRIVATE_OLD_ACCOUNT_HISTORY'), findsNothing);
      expect(
        find.text('Stamm- und Steuermerkmalsnachweis · Fassung 1'),
        findsNothing,
      );
      expect(tester.takeException(), null);
      await tester.pumpWidget(const SizedBox.shrink());
      current.dispose();
      api.dispose();
    },
  );
  testWidgets(
    'zero evidence stays readable on mobile but fresh original rights and changed employee/session clear private context',
    (tester) async {
      tester.view.physicalSize = const Size(390, 844);
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.resetPhysicalSize);
      addTearDown(tester.view.resetDevicePixelRatio);
      final api = ZeroAccountApi()..savedRevision = 1;
      final session = BusinessSession(api: api);
      await session.load();
      var opened = 0;
      Future<void> show(
        BusinessSession current,
        Map<String, dynamic> employee,
      ) => tester.pumpWidget(
        MaterialApp(
          home: BusinessPayrollAccountsPage(
            session: current,
            employee: employee,
            onOriginal: (_) async {
              opened++;
            },
          ),
        ),
      );
      await show(session, copy(f['employee']));
      await tester.pumpAndSettle();
      final title = find.text('Tatsächliche Lohnzahlung · Fassung 1');
      await tester.scrollUntilVisible(
        title,
        300,
        scrollable: find.byType(Scrollable).first,
      );
      await tester.ensureVisible(title);
      await tester.pumpAndSettle();
      expect(
        find.textContaining('Keine Nettozahlung geschuldet.'),
        findsOneWidget,
      );
      expect(tester.takeException(), null);
      final card = find.ancestor(of: title, matching: find.byType(Card)),
          original = find.descendant(
            of: card,
            matching: find.text('Nachweisoriginal öffnen'),
          );
      await tester.ensureVisible(original);
      await tester.pumpAndSettle();
      api.read = false;
      await tester.tap(original);
      await tester.pumpAndSettle();
      expect(opened, 0);
      expect(
        find.text('Lohnkonto-Nachweise · ${f['employee']['name']}'),
        findsNothing,
      );
      expect(
        find.textContaining('Keine Nettozahlung geschuldet.'),
        findsNothing,
      );
      api.read = true;
      await session.load();
      await tester.pumpAndSettle();
      await tester.tap(find.byTooltip('Rechte und Nachweise aktualisieren'));
      await tester.pumpAndSettle();
      await show(session, {
        ...copy(f['employee']),
        'id': 'e' * 32,
        'name': 'Other synthetic employee',
      });
      await tester.pumpAndSettle();
      expect(find.text('Tatsächliche Lohnzahlung · Fassung 1'), findsNothing);
      final otherApi = ZeroAccountApi()..read = false;
      final otherSession = BusinessSession(api: otherApi);
      await otherSession.load();
      await show(otherSession, copy(f['employee']));
      await tester.pumpAndSettle();
      expect(
        find.text('Lohnkonto-Nachweise · ${f['employee']['name']}'),
        findsNothing,
      );
      expect(find.text('Tatsächliche Lohnzahlung · Fassung 1'), findsNothing);
      expect(tester.takeException(), null);
      await tester.pumpWidget(const SizedBox.shrink());
      session.dispose();
      api.dispose();
      otherSession.dispose();
      otherApi.dispose();
    },
  );
}

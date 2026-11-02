import 'dart:async';
import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:smartplan_office/api.dart';
import 'package:smartplan_office/business_accounting.dart';
import 'package:smartplan_office/business_finance.dart';
import 'package:smartplan_office/business_session.dart';
import 'package:smartplan_office/design.dart';

const accountId = 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa';
const paymentId = 'bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb';
const receiptId = 'cccccccccccccccccccccccccccccccc';
Map<String, dynamic> copy(Map<String, dynamic> v) =>
    jsonDecode(jsonEncode(v)) as Map<String, dynamic>;

class AccountingApi extends OfficeApi {
  AccountingApi() : super(apiVersion: 'v1') {
    token = 'synthetic-accounting';
  }
  Set<String> rights = {
    'finance.read',
    'accounting.read',
    'accounting.prepare',
    'accounting.admin',
  };
  bool feature = true,
      readonly = false,
      enabled = true,
      writes = true,
      denied = false,
      lose = false,
      paging = false;
  Completer<void>? delayed;
  final calls = <({String path, Map<String, dynamic>? body})>[];
  final account = <String, dynamic>{
    'id': accountId,
    'code': 'BANK',
    'name': 'Synthetisches Bankkonto',
    'kind': 'bank',
    'currency': 'EUR',
    'active': true,
    'revision': 1,
  };
  final payment = <String, dynamic>{
    'payment_id': paymentId,
    'kind': 'receipt',
    'direction': 'in',
    'amount': '119.00',
    'currency': 'EUR',
    'booking_date': '2026-11-01',
    'reference': 'Synthetische Kundenzahlung',
    'source_id': 'synthetic',
    'source_hash': '1' * 64,
    'allocations': [],
    'unallocated': '119.00',
    'linked_event_id': null,
  };
  final receipt = <String, dynamic>{
    'receipt_id': receiptId,
    'project_id': 'd' * 32,
    'filename': 'synthetischer-beleg.pdf',
    'media_type': 'application/pdf',
    'original_sha256': '2' * 64,
    'review_revision': 1,
    'review_sha256': '3' * 64,
    'source_hash': '4' * 64,
    'vendor': 'Synthetischer Lieferant',
    'invoice_number': 'SYN-119',
    'issue_date': '2026-11-01',
    'net': '100.00',
    'tax': '19.00',
    'gross': '119.00',
    'currency': 'EUR',
    'cash_revision': 0,
    'paid_amount': '0.00',
    'remaining_amount': '119.00',
    'payable': true,
    'blocked_reason': null,
  };
  final results = <String, Map<String, dynamic>>{},
      requests = <String, Map<String, dynamic>>{};
  final events = <Map<String, dynamic>>[];
  @override
  Future<dynamic> call(String path, [Map<String, dynamic>? body]) async {
    calls.add((path: path, body: body == null ? null : copy(body)));
    final route = path.split('?').first;
    if (route == '/api/business/capabilities')
      return {
        'storage_version': 7,
        'compatibility_mode': readonly ? 'legacy' : 'business',
        'readonly': readonly,
        'generation': 1,
        'capabilities': ['business_finance', 'business_accounting'],
        'features': [
          if (feature) 'accounting_prejournal',
          'organization_modules',
        ],
        'permissions': rights.toList(),
        'organization': {
          'revision': 1,
          'configured': true,
          'modules': {
            for (final s in BusinessSession.organizationSections)
              s: {'visible': true, 'enabled': s == 'finance' ? enabled : true},
          },
        },
      };
    if (route.startsWith('/api/business/finance/')) return {'items': []};
    if (denied) throw const ApiException(403, 'Quellenzugriff entzogen');
    if (body == null) {
      if (route.endsWith('/status'))
        return {
          'profile_status': 'unconfigured',
          'tax_status': 'unconfigured',
          'tax_result_available': false,
          'scope': 'authorized_sources',
          'writes_allowed': writes,
        };
      if (route.endsWith('/accounts'))
        return {
          'items': [copy(account)],
        };
      final offset = Uri.parse(path).queryParameters['offset'];
      if (route.endsWith('/sources/payments'))
        return {
          'items': [copy(payment)],
          'total': 1,
          'next_offset': null,
          'scope': 'authorized_sources',
        };
      if (route.endsWith('/sources/receipts'))
        return {
          'items': [
            if (!paging || offset == '0')
              copy(receipt)
            else
              {
                ...receipt,
                'receipt_id': 'e' * 32,
                'invoice_number': 'SYN-PAGE-2',
              },
          ],
          'total': paging ? 2 : 1,
          'next_offset': paging && offset == '0' ? 50 : null,
          'scope': 'authorized_sources',
        };
      if (route.endsWith('/events'))
        return {
          'items': events.map(copy).toList(),
          'total': events.length,
          'next_offset': null,
          'scope': 'authorized_sources',
          'tax_result_available': false,
        };
      if (route.contains('/events/'))
        return copy(
          events.firstWhere((e) => route.endsWith(e['id'] as String)),
        );
      throw const ApiException(404, 'Unbekannte Testroute');
    }
    final key = body['request_id'] as String;
    if (requests.containsKey(key)) {
      expect(body, requests[key]);
      return copy(results[key]!);
    }
    Map<String, dynamic> result;
    if (route.contains('/accounts')) {
      result = {
        ...account,
        ...body,
        'revision': (account['revision'] as int) + 1,
      };
      account.addAll(result);
    } else {
      final payout = route.endsWith('/payout');
      result = {
        'id': events.length.toRadixString(16).padLeft(32, '0'),
        'sequence': events.length + 1,
        'account': copy(account),
        'direction': payout ? 'out' : 'in',
        'amount': payout ? body['amount'] : payment['amount'],
        'currency': 'EUR',
        'cash_date': body['cash_date'],
        'evidence_reference': body['evidence_reference'],
        'reference': body['reference'] ?? payment['reference'],
        'source': {
          'kind': payout ? 'receipt' : 'payment',
          'id': payout ? receiptId : paymentId,
          'source_hash': body['source_hash'],
          'snapshot': copy(payout ? receipt : payment),
        },
        'classification_status': 'unclassified',
        'unresolved_reasons': ['tax_profile_unconfigured'],
        'created_at': '2026-11-02T12:00:00Z',
        'created_by': 'synthetic-bookkeeper',
      };
      events.add(copy(result));
      if (payout) {
        receipt['cash_revision'] = (receipt['cash_revision'] as int) + 1;
        receipt['paid_amount'] = body['amount'];
        receipt['remaining_amount'] = '59.50';
      } else {
        payment['linked_event_id'] = result['id'];
      }
    }
    requests[key] = copy(body);
    results[key] = copy(result);
    if (delayed != null) await delayed!.future;
    if (lose) {
      lose = false;
      throw const ApiException(0, 'Synthetisch verlorene Antwort');
    }
    return copy(result);
  }
}

Finder field(String name) => find.byKey(ValueKey('business-field-$name'));
Future<void> press(WidgetTester tester, String text) async {
  final target = find.text(text).last;
  await tester.ensureVisible(target);
  await tester.pumpAndSettle();
  await tester.tap(target);
  await tester.pumpAndSettle();
}

Future<void> fill(WidgetTester tester, String name, String text) async {
  await tester.ensureVisible(field(name));
  await tester.enterText(field(name), text);
  await tester.pump();
}

Future<void> cashForm(
  WidgetTester tester, {
  bool payout = true,
  String amount = '59,50',
}) async {
  await tester.ensureVisible(find.byType(DropdownButtonFormField<String>));
  await tester.tap(find.byType(DropdownButtonFormField<String>));
  await tester.pumpAndSettle();
  await tester.tap(find.text('BANK · Synthetisches Bankkonto · EUR').last);
  await tester.pumpAndSettle();
  if (payout) await fill(tester, 'amount', amount);
  await fill(tester, 'cash_date', '02.11.2026');
  await fill(tester, 'evidence_reference', 'SYN-NACHWEIS-1');
  await tester.ensureVisible(find.byType(SwitchListTile));
  await tester.pumpAndSettle();
  await tester.tap(find.byType(SwitchListTile));
  await tester.pumpAndSettle();
}

BusinessSession? activeSession;
OfficeApi? activeApi;
void accountingWidgetTest(
  String description,
  Future<void> Function(WidgetTester) body,
) {
  testWidgets(description, (tester) async {
    try {
      await body(tester);
    } finally {
      await tester.pumpWidget(const SizedBox());
      activeSession?.dispose();
      activeApi?.dispose();
      activeSession = null;
      activeApi = null;
    }
  });
}

void main() {
  Future<BusinessSession> show(
    WidgetTester tester,
    AccountingApi api, {
    double width = 1200,
    bool finance = false,
    String? projectId,
  }) async {
    tester.view.physicalSize = Size(width, 1000);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    final session = BusinessSession(api: api, projectId: projectId);
    activeSession = session;
    activeApi = api;
    await session.load();
    await tester.pumpWidget(
      MaterialApp(
        theme: officeTheme(),
        home: finance
            ? Scaffold(body: BusinessFinancePage(session: session))
            : BusinessAccountingPage(session: session),
      ),
    );
    await tester.pumpAndSettle();
    return session;
  }

  test('EUR cents reject rounding and canonicalize positive amounts', () {
    expect(accountingAmount('59,5'), '59.50');
    expect(accountingAmount('000001'), '1.00');
    for (final input in ['0', '-1', '1,001', '1000000000', '1.0001'])
      expect(() => accountingAmount(input), throwsFormatException);
    expect(accountingAmount('999999999,99'), '999999999.99');
  });
  for (final width in [390.0, 1200.0]) {
    accountingWidgetTest(
      'global reader opens unconfigured preparation at $width without owner or write rights',
      (tester) async {
        final api = AccountingApi()
          ..rights = {'finance.read', 'accounting.read'};
        await show(tester, api, width: width, finance: true);
        await press(tester, 'EÜR-Vorbereitung');
        expect(
          find.textContaining('Steuerprofil nicht eingerichtet'),
          findsOneWidget,
        );
        expect(find.textContaining('Nur freigegebene Quellen'), findsOneWidget);
        await press(tester, 'Auszahlungen');
        expect(find.text('Synthetischer Lieferant · SYN-119'), findsOneWidget);
        expect(find.text('Auszahlung bestätigen'), findsNothing);
        await press(tester, 'Geldkonten');
        expect(find.text('Geldkonto anlegen'), findsNothing);
        expect(tester.takeException(), isNull);
      },
    );
  }
  accountingWidgetTest('missing feature avoids endpoint probes', (
    tester,
  ) async {
    final api = AccountingApi()..feature = false;
    await show(tester, api);
    expect(find.text('EÜR-Vorbereitung nicht freigegeben'), findsOneWidget);
    expect(api.calls.where((c) => c.path.contains('/accounting/')), isEmpty);
  });
  accountingWidgetTest(
    'project grants cannot create the global finance entry',
    (tester) async {
      final api = AccountingApi();
      await show(tester, api, finance: true, projectId: 'd' * 32);
      expect(find.text('EÜR-Vorbereitung'), findsNothing);
      expect(api.calls.where((c) => c.path.contains('/accounting/')), isEmpty);
    },
  );
  accountingWidgetTest(
    'partial payout carries exact source and account version on phone',
    (tester) async {
      final api = AccountingApi();
      await show(tester, api, width: 390);
      await press(tester, 'Auszahlungen');
      await press(tester, 'Auszahlung bestätigen');
      await cashForm(tester);
      await press(tester, 'Geldabfluss bestätigen');
      final body = api.calls.lastWhere((c) => c.path.endsWith('/payout')).body!;
      expect(body['amount'], '59.50');
      expect(body['review_revision'], 1);
      expect(body['expected_cash_revision'], 0);
      expect(body['source_hash'], '4' * 64);
      expect(body['account_revision'], 1);
      expect(body['original_sha256'], '2' * 64);
      expect(api.events, hasLength(1));
      expect(
        find.textContaining('Bestätigt ausgezahlt: 59,50'),
        findsOneWidget,
      );
      expect(tester.takeException(), isNull);
    },
  );
  accountingWidgetTest('third decimal is explained before transmission', (
    tester,
  ) async {
    final api = AccountingApi();
    await show(tester, api);
    await press(tester, 'Auszahlungen');
    await press(tester, 'Auszahlung bestätigen');
    await cashForm(tester, amount: '1,001');
    await press(tester, 'Geldabfluss bestätigen');
    expect(
      find.textContaining('höchstens zwei Nachkommastellen'),
      findsOneWidget,
    );
    expect(api.calls.where((c) => c.body != null), isEmpty);
  });
  accountingWidgetTest(
    'lost payout resumes exact id after review and inactive renamed account',
    (tester) async {
      final api = AccountingApi()..lose = true;
      await show(tester, api);
      await press(tester, 'Auszahlungen');
      await press(tester, 'Auszahlung bestätigen');
      await cashForm(tester);
      await press(tester, 'Geldabfluss bestätigen');
      await press(tester, 'Schließen');
      api.account.addAll({
        'name': 'Neu benannt',
        'revision': 2,
        'active': false,
      });
      api.receipt.addAll({
        'review_revision': 2,
        'review_sha256': '5' * 64,
        'source_hash': '6' * 64,
        'payable': false,
        'blocked_reason': 'review_changed',
      });
      await tester.tap(find.byTooltip('Vorjournal aktualisieren'));
      await tester.pumpAndSettle();
      await press(tester, 'Auszahlung fortsetzen');
      expect(
        tester.widget<TextFormField>(field('amount')).controller!.text,
        '59,50',
      );
      await press(tester, 'Erneut senden');
      final sent = api.calls.where((c) => c.path.endsWith('/payout')).toList();
      expect(sent, hasLength(2));
      expect(sent[0].body, sent[1].body);
      expect(api.events, hasLength(1));
    },
  );
  accountingWidgetTest(
    'import links original payment and resumes after link exists',
    (tester) async {
      final api = AccountingApi()..lose = true;
      await show(tester, api);
      await press(tester, 'Kundenzahlungen');
      await press(tester, 'Zahlung übernehmen');
      await cashForm(tester, payout: false);
      await press(tester, 'Einmalig ins Vorjournal übernehmen');
      await press(tester, 'Schließen');
      await press(tester, 'Übernahme fortsetzen');
      await press(tester, 'Erneut senden');
      final sent = api.calls
          .where((c) => c.path.endsWith('/import-payment'))
          .toList();
      expect(sent, hasLength(2));
      expect(sent[0].body, sent[1].body);
      expect(
        api.calls.where((c) => c.body != null && c.path.contains('/finance/')),
        isEmpty,
      );
      expect(api.events, hasLength(1));
      expect(find.text('Bereits im Vorjournal · ansehen'), findsOneWidget);
    },
  );
  accountingWidgetTest('finance read loss clears editor data', (tester) async {
    final api = AccountingApi();
    final session = await show(tester, api);
    await press(tester, 'Auszahlungen');
    await press(tester, 'Auszahlung bestätigen');
    await cashForm(tester);
    api.rights.remove('finance.read');
    await session.load();
    await tester.pumpAndSettle();
    expect(find.text('59,50'), findsNothing);
    expect(find.text('SYN-NACHWEIS-1'), findsNothing);
    expect(
      tester
          .widget<FilledButton>(
            find.ancestor(
              of: find.text('Geldabfluss bestätigen'),
              matching: find.byType(FilledButton),
            ),
          )
          .onPressed,
      isNull,
    );
  });
  accountingWidgetTest('known server denial clears loaded sources', (
    tester,
  ) async {
    final api = AccountingApi();
    await show(tester, api);
    await press(tester, 'Auszahlungen');
    expect(find.text('Synthetischer Lieferant · SYN-119'), findsOneWidget);
    api.denied = true;
    await tester.tap(find.byTooltip('Vorjournal aktualisieren'));
    await tester.pumpAndSettle();
    expect(find.text('Synthetischer Lieferant · SYN-119'), findsNothing);
    expect(find.text('EÜR-Vorbereitung nicht freigegeben'), findsOneWidget);
  });
  accountingWidgetTest('source pages append without project filter', (
    tester,
  ) async {
    final api = AccountingApi()..paging = true;
    await show(tester, api);
    await press(tester, 'Auszahlungen');
    await press(tester, 'Weitere Einträge laden');
    expect(find.text('Synthetischer Lieferant · SYN-119'), findsOneWidget);
    expect(find.text('Synthetischer Lieferant · SYN-PAGE-2'), findsOneWidget);
    final requests = api.calls
        .where((c) => c.path.contains('/sources/receipts'))
        .toList();
    expect(requests.last.path, endsWith('?limit=50&offset=50'));
    expect(requests.any((c) => c.path.contains('project_id')), false);
  });
  accountingWidgetTest(
    'finance pause and restore preserve readable sources without writes',
    (tester) async {
      final api = AccountingApi()
        ..enabled = false
        ..writes = false;
      await show(tester, api);
      await press(tester, 'Auszahlungen');
      expect(find.text('Synthetischer Lieferant · SYN-119'), findsOneWidget);
      expect(find.text('Auszahlung bestätigen'), findsNothing);
      await press(tester, 'Geldkonten');
      expect(find.text('Geldkonto anlegen'), findsNothing);
    },
  );
  accountingWidgetTest('account admin edits without cash prepare permission', (
    tester,
  ) async {
    final api = AccountingApi()..rights.remove('accounting.prepare');
    await show(tester, api);
    await press(tester, 'Geldkonten');
    await press(tester, 'Konto ändern');
    await fill(tester, 'name', 'Geprüfte Kasse');
    await tester.tap(find.byType(SwitchListTile).last);
    await tester.pumpAndSettle();
    await press(tester, 'Speichern');
    expect(api.account['name'], 'Geprüfte Kasse');
    await press(tester, 'Auszahlungen');
    expect(find.text('Auszahlung bestätigen'), findsNothing);
  });
  test(
    'pending snapshot is detached, path-bound and cleared on token loss',
    () async {
      final api = AccountingApi()..lose = true;
      final session = BusinessSession(api: api);
      await session.load();
      await expectLater(
        session.command('test', '/accounting/accounts', {
          'name': 'Konto',
          'nested': [
            {'value': 'Original'},
          ],
        }),
        throwsA(isA<ApiException>()),
      );
      final pending = session.pendingCommandValues(
        'test',
        path: '/accounting/accounts',
      )!;
      (pending['nested'] as List).first['value'] = 'Changed';
      expect(
        (session.pendingCommandValues(
                  'test',
                  path: '/accounting/accounts',
                )!['nested']
                as List)
            .first['value'],
        'Original',
      );
      expect(session.pendingCommandValues('test', path: '/different'), isNull);
      api.token = 'different-user';
      expect(
        session.pendingCommandValues('test', path: '/accounting/accounts'),
        isNull,
      );
      session.dispose();
      api.dispose();
    },
  );
  accountingWidgetTest(
    'server source denial during save hides the open financial form',
    (tester) async {
      final api = AccountingApi();
      await show(tester, api);
      await press(tester, 'Auszahlungen');
      await press(tester, 'Auszahlung bestätigen');
      await cashForm(tester);
      api.denied = true;
      await press(tester, 'Geldabfluss bestätigen');
      expect(find.text('59,50'), findsNothing);
      expect(find.text('SYN-NACHWEIS-1'), findsNothing);
      expect(find.text('Der Zugang ist nicht mehr verfügbar.'), findsOneWidget);
      expect(api.events, isEmpty);
    },
  );
  accountingWidgetTest(
    'reopen during an in-flight payout restores frozen original fields before any error',
    (tester) async {
      final api = AccountingApi()
        ..lose = true
        ..delayed = Completer<void>();
      await show(tester, api);
      await press(tester, 'Auszahlungen');
      await press(tester, 'Auszahlung bestätigen');
      await cashForm(tester);
      await tester.tap(find.text('Geldabfluss bestätigen'));
      await tester.pump();
      expect(api.events, hasLength(1));
      await tester.tapAt(const Offset(5, 5));
      await tester.pumpAndSettle();
      await press(tester, 'Auszahlung fortsetzen');
      final restored = tester.widget<TextFormField>(field('amount'));
      expect(restored.controller!.text, '59,50');
      expect(restored.enabled, false);
      expect(
        tester
            .widget<TextFormField>(field('evidence_reference'))
            .controller!
            .text,
        'SYN-NACHWEIS-1',
      );
      api.delayed!.complete();
      await tester.pumpAndSettle();
      await press(tester, 'Erneut senden');
      final sent = api.calls.where((c) => c.path.endsWith('/payout')).toList();
      expect(sent, hasLength(2));
      expect(sent[0].body, sent[1].body);
      expect(api.events, hasLength(1));
    },
  );
  accountingWidgetTest(
    'late successful acknowledgement cannot turn an open retry into a second payout',
    (tester) async {
      final api = AccountingApi()..delayed = Completer<void>();
      await show(tester, api);
      await press(tester, 'Auszahlungen');
      await press(tester, 'Auszahlung bestätigen');
      await cashForm(tester);
      await tester.tap(find.text('Geldabfluss bestätigen'));
      await tester.pump();
      await tester.tapAt(const Offset(5, 5));
      await tester.pumpAndSettle();
      await press(tester, 'Auszahlung fortsetzen');
      api.delayed!.complete();
      await tester.pumpAndSettle();
      await press(tester, 'Erneut senden');
      expect(
        find.textContaining(
          'Die frühere Übertragung wurde inzwischen beantwortet',
        ),
        findsOneWidget,
      );
      expect(api.calls.where((c) => c.path.endsWith('/payout')), hasLength(1));
      expect(api.events, hasLength(1));
    },
  );
  test('cash date validates real calendar days without normalization', () {
    expect(accountingCashDate('2.11.2026'), '2026-11-02');
    expect(accountingCashDate('2024-02-29'), '2024-02-29');
    for (final input in [
      '2026-02-30',
      '2026-02-29',
      '31.04.2026',
      '2026-13-01',
      '2026-11-02T12:00:00',
    ]) {
      expect(() => accountingCashDate(input), throwsFormatException);
    }
  });
  accountingWidgetTest(
    'invalid ISO date and multiline reference are explained before a cash request',
    (tester) async {
      final api = AccountingApi();
      await show(tester, api);
      await press(tester, 'Auszahlungen');
      await press(tester, 'Auszahlung bestätigen');
      await cashForm(tester);
      await fill(tester, 'cash_date', '2026-02-30');
      await press(tester, 'Geldabfluss bestätigen');
      expect(find.textContaining('kein gültiger Kalendertag'), findsOneWidget);
      expect(api.events, isEmpty);
      await fill(tester, 'cash_date', '2026-11-02');
      tester.widget<TextFormField>(field('reference')).controller!.text =
          'Zeile 1\nZeile 2';
      await tester.pump();
      await press(tester, 'Geldabfluss bestätigen');
      expect(
        find.textContaining('einzeiligen Text ohne Steuerzeichen'),
        findsOneWidget,
      );
      expect(api.events, isEmpty);
    },
  );
}

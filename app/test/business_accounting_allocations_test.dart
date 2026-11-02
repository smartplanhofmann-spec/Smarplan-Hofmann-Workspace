import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:smartplan_office/api.dart';
import 'package:smartplan_office/business_accounting.dart';
import 'package:smartplan_office/business_accounting_allocations.dart';
import 'package:smartplan_office/business_session.dart';
import 'package:smartplan_office/design.dart';

import 'business_accounting_test.dart' as base;

const paymentId = base.paymentId;
const invoiceId = 'dddddddddddddddddddddddddddddddd';
const customerId = 'eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee';

class AllocationApi extends base.AccountingApi {
  AllocationApi() {
    rights.add('finance.write');
    payment['linked_event_id'] = 'f' * 32;
  }
  bool allocationFeature = true,
      allocationDenied = false,
      loseAssignment = false;
  bool stale = false, pages = false;
  bool targetDenied = false, loseBeforeServer = false;
  Completer<void>? delayedPreview, delayedAssign;
  int revision = 0;
  final entries = <Map<String, dynamic>>[];
  final allocationRequests = <String, Map<String, dynamic>>{};
  final allocationResults = <String, Map<String, dynamic>>{};
  Map<String, dynamic> get target => {
    'document_id': invoiceId,
    'number': 'SYN-RE-1',
    'project_id': '1' * 32,
    'customer_id': customerId,
    'buyer_name': 'Synthetischer Kunde',
    'gross': '119.00',
    'paid': revision == 0 ? '0.00' : '59.50',
    'credited': '0.00',
    'open': revision == 0 ? '119.00' : '59.50',
    'payload_sha256': '2' * 64,
    'pdf_sha256': '3' * 64,
    'document_state_hash': revision == 0 ? '4' * 64 : '5' * 64,
  };
  Map<String, dynamic> get state => {
    'payment_id': paymentId,
    'event_id': 'f' * 32,
    'source_hash': '1' * 64,
    'revision': revision,
    'state_hash': revision == 0 ? '6' * 64 : '7' * 64,
    'amount': '119.00',
    'currency': 'EUR',
    'customer_id': revision == 0 ? null : customerId,
    'allocated_amount': revision == 0 ? '0.00' : '59.50',
    'unallocated_amount': revision == 0 ? '119.00' : '59.50',
    'allocations': revision == 0
        ? []
        : [
            {'document_id': invoiceId, 'amount': '59.50'},
          ],
    'eligible': true,
    'blocked_reason': null,
    'writes_allowed':
        writes &&
        enabled &&
        !readonly &&
        rights.contains('finance.write') &&
        rights.contains('accounting.prepare'),
    'scope': 'authorized_sources',
    'tax_result_available': false,
  };
  @override
  Future<dynamic> call(String path, [Map<String, dynamic>? body]) async {
    final route = path.split('?').first;
    if (route == '/api/business/capabilities') {
      final result = base.copy(
        await super.call(path, body) as Map<String, dynamic>,
      );
      (result['capabilities'] as List).add('business_accounting_allocations');
      if (allocationFeature)
        (result['features'] as List).add('accounting_payment_allocation');
      return result;
    }
    if (route == '/api/business/documents/$invoiceId') {
      calls.add((path: path, body: body));
      if (targetDenied)
        throw const ApiException(403, 'Zielprojekt nicht mehr lesbar');
      return {'id': invoiceId, 'number': target['number']};
    }
    if (!route.contains('/accounting/allocations/'))
      return super.call(path, body);
    calls.add((path: path, body: body == null ? null : base.copy(body)));
    if (allocationDenied)
      throw const ApiException(403, 'Synthetischer Quellenzugriff entzogen');
    if (body == null) {
      if (route.endsWith('/candidates')) {
        final offset = Uri.parse(path).queryParameters['offset'];
        return {
          'items': [
            if (!targetDenied)
              if (!pages || offset == '0')
                target
              else
                {...target, 'document_id': 'a' * 32, 'number': 'SYN-RE-2'},
          ],
          'total': pages ? 2 : 1,
          'next_offset': pages && offset == '0' ? 50 : null,
          'scope': 'authorized_sources',
        };
      }
      if (route.endsWith('/history'))
        return {
          'items': entries.map(base.copy).toList(),
          'total': entries.length,
          'next_offset': null,
          'scope': 'authorized_sources',
        };
      return state;
    }
    if (route.endsWith('/preview')) {
      expect(body.containsKey('request_id'), false);
      expect(body.containsKey('confirmation'), false);
      if (stale ||
          body['expected_revision'] != revision ||
          body['document_state_hash'] != target['document_state_hash'])
        throw const ApiException(
          409,
          'Der bestätigte Stand ist veraltet. Bitte neu laden.',
        );
      final proposed = <String, dynamic>{
        ...state,
        ...body,
        'document': target,
        'unallocated_before': state['unallocated_amount'],
        'unallocated_after': '59.50',
        'open_before': target['open'],
        'open_after': '59.50',
        'preview_hash': '8' * 64,
      };
      if (delayedPreview != null) await delayedPreview!.future;
      return proposed;
    }
    expect(route.endsWith('/assign'), true);
    if (loseBeforeServer) {
      loseBeforeServer = false;
      throw const ApiException(0, 'Anfrage vor der Serverannahme verloren');
    }
    final requestId = body['request_id'] as String;
    if (allocationRequests.containsKey(requestId)) {
      expect(body, allocationRequests[requestId]);
      return base.copy(allocationResults[requestId]!);
    }
    if (stale || body['expected_revision'] != revision)
      throw const ApiException(
        409,
        'Die Vorschau ist veraltet. Bitte neu prüfen.',
      );
    expect(body['confirmation'], true);
    expect(body['preview_hash'], '8' * 64);
    final entry = <String, dynamic>{
      'id': entries.length.toRadixString(16).padLeft(32, '0'),
      'payment_id': paymentId,
      'event_id': 'f' * 32,
      'revision': revision + 1,
      'customer_id': body['customer_id'],
      'source_hash': body['source_hash'],
      'previous_state_hash': body['state_hash'],
      'document': target,
      'amount': body['amount'],
      'reason': body['reason'],
      'unallocated_before': state['unallocated_amount'],
      'unallocated_after': '59.50',
      'open_before': target['open'],
      'open_after': '59.50',
      'preview_hash': body['preview_hash'],
      'created_by': 'synthetic-bookkeeper',
      'created_at': '2026-11-02T12:00:00Z',
      'scope': 'authorized_sources',
      'tax_result_available': false,
    };
    entries.add(base.copy(entry));
    revision++;
    allocationRequests[requestId] = base.copy(body);
    allocationResults[requestId] = base.copy(entry);
    if (delayedAssign != null) await delayedAssign!.future;
    if (loseAssignment) {
      loseAssignment = false;
      throw const ApiException(0, 'Synthetisch verlorene Zuordnungsantwort');
    }
    return entry;
  }
}

void main() {
  Future<BusinessSession> show(
    WidgetTester tester,
    AllocationApi api, {
    double width = 1200,
    bool accountingEntry = false,
    String? projectId,
    bool offline = false,
  }) async {
    tester.view.physicalSize = Size(width, 1000);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    final session = BusinessSession(
      api: api,
      projectId: projectId,
      offlineMode: offline,
    );
    base.activeSession = session;
    base.activeApi = api;
    await session.load();
    await tester.pumpWidget(
      MaterialApp(
        theme: officeTheme(),
        home: accountingEntry
            ? BusinessAccountingPage(session: session)
            : BusinessPaymentAllocationsPage(
                session: session,
                paymentId: paymentId,
              ),
      ),
    );
    await tester.pumpAndSettle();
    return session;
  }

  Future<void> select(
    WidgetTester tester, {
    bool confirm = true,
    String amount = '59,50',
  }) async {
    await base.press(tester, 'Diese Rechnung auswählen');
    if (confirm) {
      await tester.ensureVisible(find.byType(CheckboxListTile));
      await tester.pumpAndSettle();
      await tester.tap(find.byType(CheckboxListTile));
      await tester.pumpAndSettle();
    }
    await tester.ensureVisible(find.byKey(const ValueKey('allocation-amount')));
    await tester.enterText(
      find.byKey(const ValueKey('allocation-amount')),
      amount,
    );
    await tester.ensureVisible(find.byKey(const ValueKey('allocation-reason')));
    await tester.enterText(
      find.byKey(const ValueKey('allocation-reason')),
      'Synthetisch geprüfte Kundenbindung',
    );
    await tester.pumpAndSettle();
  }

  Future<void> reopen(WidgetTester tester, BusinessSession session) async {
    await tester.pumpWidget(const SizedBox());
    await tester.pumpWidget(
      MaterialApp(
        theme: officeTheme(),
        home: BusinessPaymentAllocationsPage(
          session: session,
          paymentId: paymentId,
        ),
      ),
    );
    await tester.pumpAndSettle();
  }

  for (final width in [390.0, 1200.0]) {
    base.accountingWidgetTest(
      'separate side-effect-free preview and explicit assignment at $width',
      (tester) async {
        final api = AllocationApi();
        await show(tester, api, width: width, accountingEntry: true);
        await base.press(tester, 'Kundenzahlungen');
        expect(
          find.textContaining(
            'Im ursprünglichen Zahlungsnachweis nicht zugeordnet',
          ),
          findsOneWidget,
        );
        await base.press(tester, 'Rechnung zuordnen');
        await select(tester);
        await base.press(tester, 'Vorschau berechnen');
        expect(api.entries, isEmpty);
        expect(find.text('Vorschau prüfen'), findsOneWidget);
        expect(find.textContaining('59,50 €'), findsWidgets);
        expect(
          api.calls
              .where((c) => c.path.endsWith('/preview'))
              .single
              .body!['amount'],
          '59.50',
        );
        await base.press(tester, 'Zuordnung verbindlich bestätigen');
        expect(api.entries, hasLength(1));
        expect(find.text('Aktueller Zuordnungsstand'), findsOneWidget);
        expect(find.text('Bestätigte Zuordnung Nr. 1'), findsOneWidget);
        expect(api.payment['unallocated'], '119.00');
        expect(tester.takeException(), isNull);
      },
    );
  }
  base.accountingWidgetTest(
    'customer confirmation and precise cents precede preview',
    (tester) async {
      final api = AllocationApi();
      await show(tester, api);
      await select(tester, confirm: false);
      await base.press(tester, 'Vorschau berechnen');
      expect(
        find.textContaining('Kunden ausdrücklich bestätigen'),
        findsOneWidget,
      );
      expect(api.calls.where((c) => c.body != null), isEmpty);
      await tester.ensureVisible(find.byType(CheckboxListTile));
      await tester.pumpAndSettle();
      await tester.tap(find.byType(CheckboxListTile));
      await tester.enterText(
        find.byKey(const ValueKey('allocation-amount')),
        '1,001',
      );
      await base.press(tester, 'Vorschau berechnen');
      expect(
        find.textContaining('höchstens zwei Nachkommastellen'),
        findsOneWidget,
      );
      expect(api.calls.where((c) => c.body != null), isEmpty);
    },
  );
  base.accountingWidgetTest(
    'changing inputs discards a previous preview and customer confirmation',
    (tester) async {
      final api = AllocationApi();
      await show(tester, api);
      await select(tester);
      await base.press(tester, 'Vorschau berechnen');
      await base.press(tester, 'Eingaben ändern');
      expect(find.text('Zuordnung verbindlich bestätigen'), findsNothing);
      expect(
        tester.widget<CheckboxListTile>(find.byType(CheckboxListTile)).value,
        false,
      );
      expect(api.entries, isEmpty);
    },
  );
  base.accountingWidgetTest(
    'lost assignment resumes exact original preview and request after newer state',
    (tester) async {
      final api = AllocationApi()..loseAssignment = true;
      final session = await show(tester, api);
      await select(tester);
      await base.press(tester, 'Vorschau berechnen');
      await base.press(tester, 'Zuordnung verbindlich bestätigen');
      expect(api.entries, hasLength(1));
      await reopen(tester, session);
      expect(
        find.text('Unbestätigte Übertragung · ursprüngliche Vorschau'),
        findsOneWidget,
      );
      expect(find.byKey(const ValueKey('allocation-amount')), findsNothing);
      await base.press(tester, 'Unverändert erneut senden');
      final sent = api.calls.where((c) => c.path.endsWith('/assign')).toList();
      expect(sent, hasLength(2));
      expect(sent.first.body, sent.last.body);
      expect(api.entries, hasLength(1));
      expect(api.calls.where((c) => c.path.endsWith('/preview')), hasLength(1));
    },
  );
  base.accountingWidgetTest(
    'inflight reopen freezes preview and late acknowledgement cannot create a new command',
    (tester) async {
      final api = AllocationApi()..delayedAssign = Completer<void>();
      final session = await show(tester, api);
      await select(tester);
      await base.press(tester, 'Vorschau berechnen');
      await tester.ensureVisible(find.text('Zuordnung verbindlich bestätigen'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Zuordnung verbindlich bestätigen'));
      await tester.pump();
      expect(api.entries, hasLength(1));
      await reopen(tester, session);
      expect(
        find.text('Unbestätigte Übertragung · ursprüngliche Vorschau'),
        findsOneWidget,
      );
      api.delayedAssign!.complete();
      await tester.pumpAndSettle();
      await base.press(tester, 'Unverändert erneut senden');
      expect(
        find.textContaining('frühere Übertragung wurde inzwischen beantwortet'),
        findsOneWidget,
      );
      expect(api.calls.where((c) => c.path.endsWith('/assign')), hasLength(1));
      expect(api.entries, hasLength(1));
    },
  );
  for (final mode in ['read', 'readonly', 'paused', 'restore']) {
    base.accountingWidgetTest(
      '$mode keeps state/history readable and makes no candidate or preview requests',
      (tester) async {
        final api = AllocationApi();
        if (mode == 'read') api.rights.remove('finance.write');
        if (mode == 'readonly') api.readonly = true;
        if (mode == 'paused') api.enabled = false;
        if (mode == 'restore') api.writes = false;
        await show(tester, api);
        expect(find.text('Aktueller Zuordnungsstand'), findsOneWidget);
        expect(find.text('Diese Rechnung auswählen'), findsNothing);
        expect(
          api.calls.where(
            (c) =>
                c.path.contains('/candidates') || c.path.endsWith('/preview'),
          ),
          isEmpty,
        );
      },
    );
  }
  for (final mode in ['feature', 'project', 'offline']) {
    base.accountingWidgetTest('$mode blocks allocation probes entirely', (
      tester,
    ) async {
      final api = AllocationApi();
      if (mode == 'feature') api.allocationFeature = false;
      await show(
        tester,
        api,
        projectId: mode == 'project' ? '1' * 32 : null,
        offline: mode == 'offline',
      );
      expect(find.text('Zahlungszuordnung nicht freigegeben'), findsOneWidget);
      expect(api.calls.where((c) => c.path.contains('/allocations/')), isEmpty);
    });
  }
  base.accountingWidgetTest(
    'known source denial hides selected financial data and late preview',
    (tester) async {
      final api = AllocationApi()..delayedPreview = Completer<void>();
      final session = await show(tester, api);
      await select(tester);
      await tester.ensureVisible(find.text('Vorschau berechnen'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Vorschau berechnen'));
      await tester.pump();
      api.rights.remove('finance.read');
      await session.load();
      await tester.pump();
      api.delayedPreview!.complete();
      await tester.pumpAndSettle();
      expect(find.text('Synthetischer Kunde'), findsNothing);
      expect(find.text('Vorschau prüfen'), findsNothing);
      expect(find.text('Zahlungszuordnung nicht freigegeben'), findsOneWidget);
    },
  );
  base.accountingWidgetTest('server-only source403 clears the open proposal', (
    tester,
  ) async {
    final api = AllocationApi();
    await show(tester, api);
    await select(tester);
    await base.press(tester, 'Vorschau berechnen');
    api.allocationDenied = true;
    await base.press(tester, 'Zuordnung verbindlich bestätigen');
    expect(find.text('Vorschau prüfen'), findsNothing);
    expect(find.text('Synthetischer Kunde'), findsNothing);
    expect(api.entries, isEmpty);
  });
  base.accountingWidgetTest(
    'stale preview is rejected without assignment and can be refreshed',
    (tester) async {
      final api = AllocationApi();
      await show(tester, api);
      await select(tester);
      await base.press(tester, 'Vorschau berechnen');
      api.stale = true;
      await base.press(tester, 'Zuordnung verbindlich bestätigen');
      expect(find.textContaining('Vorschau ist veraltet'), findsOneWidget);
      expect(api.entries, isEmpty);
      expect(find.text('Zuordnung verbindlich bestätigen'), findsNothing);
    },
  );
  base.accountingWidgetTest(
    'candidate paging exposes later eligible invoices',
    (tester) async {
      final api = AllocationApi()..pages = true;
      await show(tester, api);
      await base.press(tester, 'Weitere Rechnungen laden');
      expect(find.text('SYN-RE-1'), findsOneWidget);
      expect(find.text('SYN-RE-2'), findsOneWidget);
      expect(
        api.calls.lastWhere((c) => c.path.contains('/candidates')).path,
        endsWith('offset=50'),
      );
    },
  );
  test('preview helper is exact scoped side-effect-free POST and refuses readonly or disabled finance', () async {
    final api = AllocationApi();
    final session = BusinessSession(api: api);
    await session.load();
    final body = {
      'source_hash': '1' * 64,
      'expected_revision': 0,
      'state_hash': '6' * 64,
      'customer_id': customerId,
      'document_id': invoiceId,
      'document_state_hash': '4' * 64,
      'amount': '59.50',
      'reason': 'Synthetic preview',
    };
    await session.previewPaymentAllocation(paymentId, body);
    expect(session.pending('accounting-allocation-$paymentId'), false);
    expect(api.calls.last.body, body);
    api.readonly = true;
    await session.load();
    await expectLater(
      session.previewPaymentAllocation(paymentId, body),
      throwsA(isA<ApiException>().having((e) => e.status, 'status', 403)),
    );
    api.readonly = false;
    api.enabled = false;
    await session.load();
    await expectLater(
      session.previewPaymentAllocation(paymentId, body),
      throwsA(isA<ApiException>().having((e) => e.status, 'status', 423)),
    );
    session.dispose();
    api.dispose();
  });
  base.accountingWidgetTest(
    'pending target read is rechecked before restoring an unreceived assignment',
    (tester) async {
      final api = AllocationApi()..loseBeforeServer = true;
      final session = await show(tester, api);
      await select(tester);
      await base.press(tester, 'Vorschau berechnen');
      await base.press(tester, 'Zuordnung verbindlich bestätigen');
      expect(api.entries, isEmpty);
      expect(session.pending('accounting-allocation-$paymentId'), true);
      api.targetDenied = true;
      await reopen(tester, session);
      expect(find.text('Synthetischer Kunde'), findsNothing);
      expect(
        find.text('Unbestätigte Übertragung · ursprüngliche Vorschau'),
        findsNothing,
      );
      expect(find.text('Zahlungszuordnung nicht freigegeben'), findsOneWidget);
      expect(session.pending('accounting-allocation-$paymentId'), true);
      api.targetDenied = false;
      await tester.tap(find.byTooltip('Zuordnungen aktualisieren'));
      await tester.pumpAndSettle();
      await base.press(tester, 'Unverändert erneut senden');
      final sent = api.calls.where((c) => c.path.endsWith('/assign')).toList();
      expect(sent, hasLength(2));
      expect(sent.first.body, sent.last.body);
      expect(api.entries, hasLength(1));
    },
  );
}

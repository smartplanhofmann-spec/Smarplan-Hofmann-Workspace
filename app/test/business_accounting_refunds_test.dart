import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:smartplan_office/api.dart';
import 'package:smartplan_office/business_accounting.dart';
import 'package:smartplan_office/business_accounting_refunds.dart';
import 'package:smartplan_office/business_session.dart';
import 'package:smartplan_office/design.dart';

import 'business_accounting_test.dart' as base;

const eventId = '11111111111111111111111111111111';
const firstEntry = '22222222222222222222222222222222';
const secondEntry = '33333333333333333333333333333333';
const firstEvent = '44444444444444444444444444444444';
const secondEvent = '55555555555555555555555555555555';
String get groupId => 'a' * 64;
String get portionId => 'b' * 64;
String get pendingKey => 'accounting-refunds-$eventId';
String get path => '/accounting/refunds/events/$eventId';
int cents(Object? v) => int.parse('$v'.replaceAll('.', ''));
String money(int n) => '${n ~/ 100}.${(n % 100).toString().padLeft(2, '0')}';

class RefundApi extends base.AccountingApi {
  RefundApi() {
    rights.add('finance.write');
  }
  bool refundFeature = true,
      pages = false,
      lost = false,
      beforeServer = false,
      sourceDenied = false,
      stale = false,
      zeroGroups = false;
  String? deniedOrigin, blocked;
  Completer<void>? previewReply, confirmReply, historyReply, originReply;
  int revision = 0;
  final entries = <Map<String, dynamic>>[];
  final refundRequests = <String, Map<String, dynamic>>{},
      refundResults = <String, Map<String, dynamic>>{};
  Map<String, dynamic> get portion => {
    'portion_id': portionId,
    'kind': 'original_refund_allocation',
    'event_id': eventId,
    'document_id': base.paymentId,
    'customer_id': '6' * 32,
    'project_id': '7' * 32,
    'number': 'SYN-REFUND-INVOICE',
    'party_name': 'Synthetischer Kunde',
    'amount': '26.44',
    'currency': 'EUR',
    'payload_sha256': 'c' * 64,
    'pdf_sha256': 'd' * 64,
    'portion_state_hash': 'e' * 64,
    'eligible': blocked == null,
    'blocked_reason': blocked,
  };
  Map<String, dynamic> origin(bool second) => {
    'entry_id': second ? secondEntry : firstEntry,
    'group_id': groupId,
    'origin_event_id': second ? secondEvent : firstEvent,
    'component_sequence': second ? 12 : 11,
    'rate': zeroGroups ? '0' : '19',
    'category': zeroGroups ? (second ? 'E' : 'Z') : 'S',
    'tax_reason': zeroGroups
        ? (second ? 'Befreiung laut Archiv' : 'Nullsatz laut Archiv')
        : null,
    'document_id': base.paymentId,
    'customer_id': '6' * 32,
    'project_id': '7' * 32,
    'number': 'SYN-REFUND-INVOICE',
    'party_name': 'Synthetischer Kunde',
    'cash_date': '2026-11-01',
    'evidence_reference': second ? 'ORIGIN-SECOND' : 'ORIGIN-FIRST',
    'reference': 'Synthetisch bestätigte Einnahme',
    'currency': 'EUR',
    'amount': '39.67',
    'net': second ? '33.33' : '33.34',
    'tax': second ? '6.34' : '6.33',
    'returned_amount': '0.00',
    'returned_net': '0.00',
    'returned_tax': '0.00',
    'remaining_amount': '39.67',
    'remaining_net': second ? '33.33' : '33.34',
    'remaining_tax': second ? '6.34' : '6.33',
    'lot_state_hash': (second ? 'f' : '9') * 64,
  };
  Map<String, dynamic> get state => {
    'event_id': eventId,
    'source_hash': '1' * 64,
    'revision': revision,
    'state_hash': '$revision'.padLeft(64, '0'),
    'source_kind': 'customer_refund',
    'amount': '26.44',
    'currency': 'EUR',
    'cash_date': '2026-11-02',
    'evidence_reference': 'REFUND-EVIDENCE',
    'reference': 'Bereits bestätigte Kundenerstattung',
    'origin_documented_amount': revision == 0 ? '0.00' : '26.44',
    'origin_unresolved_amount': revision == 0 ? '26.44' : '0.00',
    'unallocated_amount': blocked == 'unallocated' ? '26.44' : '0.00',
    'eligible': revision == 0 && blocked == null,
    'blocked_reason': revision > 0 ? 'fully_documented' : blocked,
    'writes_allowed':
        writes &&
        enabled &&
        !readonly &&
        rights.contains('finance.write') &&
        rights.contains('accounting.prepare'),
    'capacity_released': false,
    'scope': 'authorized_sources',
    'tax_status': 'unconfigured',
    'tax_result_available': false,
  };
  Map<String, dynamic> list(List<Map<String, dynamic>> values, {int? next}) => {
    'items': values,
    'total': next == null ? values.length : 2,
    'next_offset': next,
    'scope': 'authorized_sources',
  };
  @override
  Future<dynamic> call(String routePath, [Map<String, dynamic>? body]) async {
    final route = routePath.split('?').first;
    if (route == '/api/business/capabilities') {
      final value = base.copy(
        await super.call(routePath, body) as Map<String, dynamic>,
      );
      (value['capabilities'] as List).addAll([
        'business_accounting_refunds',
        'business_accounting_components',
      ]);
      (value['features'] as List).add('accounting_document_components');
      if (refundFeature)
        (value['features'] as List).add('accounting_refund_origins');
      return value;
    }
    if (route == '/api/business/accounting/events/$firstEvent' ||
        route == '/api/business/accounting/events/$secondEvent') {
      calls.add((path: routePath, body: body));
      if (originReply != null) await originReply!.future;
      if (route.endsWith('/$deniedOrigin'))
        throw const ApiException(403, 'Ursprungszugriff entzogen');
      return {'id': route.split('/').last};
    }
    if (route == '/api/business/accounting/events/$eventId' && events.isEmpty) {
      calls.add((path: routePath, body: body));
      if (sourceDenied)
        throw const ApiException(403, 'Erstattungszugriff entzogen');
      return {'id': eventId};
    }
    if (!route.contains('/accounting/refunds/'))
      return super.call(routePath, body);
    calls.add((path: routePath, body: body == null ? null : base.copy(body)));
    if (sourceDenied)
      throw const ApiException(403, 'Erstattungszugriff entzogen');
    if (body == null) {
      if (route.endsWith('/history')) {
        if (historyReply != null) await historyReply!.future;
        return list(entries.map(base.copy).toList());
      }
      if (route.endsWith('/portions'))
        return list([if (revision == 0) portion]);
      if (route.endsWith('/origins')) {
        final later = Uri.parse(routePath).queryParameters['offset'] != '0';
        return list([
          if (!pages || !later) origin(false),
          if (!pages || later) origin(true),
        ], next: pages && !later ? 50 : null);
      }
      return state;
    }
    if (route.endsWith('/preview')) {
      expect(body.containsKey('request_id'), false);
      expect(body.containsKey('confirmation'), false);
      if (previewReply != null) await previewReply!.future;
      if (stale)
        throw const ApiException(
          409,
          'Ursprungsstand geändert. Bitte neu prüfen.',
        );
      final lines = <Map<String, dynamic>>[];
      for (final value in body['origins'] as List) {
        final o = origin(value['entry_id'] == secondEntry),
            gross = cents(value['amount']);
        final tax =
            (2 * gross * cents(o['tax']) + cents(o['amount'])) ~/
            (2 * cents(o['amount']));
        lines.add({
          for (final k in [
            'entry_id',
            'group_id',
            'origin_event_id',
            'component_sequence',
            'rate',
            'category',
            'tax_reason',
            'lot_state_hash',
          ])
            k: o[k],
          'origin_cash_date': o['cash_date'],
          'origin_evidence_reference': o['evidence_reference'],
          'origin_reference': o['reference'],
          'amount': value['amount'],
          'net': money(gross - tax),
          'tax': money(tax),
          'gross_before': '0.00',
          'gross_after': value['amount'],
          'net_before': '0.00',
          'net_after': money(gross - tax),
          'tax_before': '0.00',
          'tax_after': money(tax),
          'remaining_gross': money(cents(o['amount']) - gross),
          'remaining_net': money(cents(o['net']) - gross + tax),
          'remaining_tax': money(cents(o['tax']) - tax),
        });
      }
      lines.sort((a, b) => '${b['entry_id']}'.compareTo('${a['entry_id']}'));
      return {
        'event_id': eventId,
        'source_hash': body['source_hash'],
        'expected_revision': body['expected_revision'],
        'state_hash': body['state_hash'],
        'cash_date': state['cash_date'],
        'evidence_reference': state['evidence_reference'],
        'reference': state['reference'],
        'portion': portion,
        'amount': portion['amount'],
        'net': money(lines.fold(0, (n, l) => n + cents(l['net']))),
        'tax': money(lines.fold(0, (n, l) => n + cents(l['tax']))),
        'lines': lines,
        'reason': body['reason'],
        'preview_hash': '8' * 64,
        'capacity_released': false,
        'scope': 'authorized_sources',
        'tax_status': 'unconfigured',
        'tax_result_available': false,
      };
    }
    if (route.endsWith('/confirm')) {
      if (beforeServer) {
        beforeServer = false;
        throw const ApiException(0, 'Verbindung vor Zustellung verloren');
      }
      final id = '${body['request_id']}';
      if (refundResults.containsKey(id)) {
        expect(body, refundRequests[id]);
        return base.copy(refundResults[id]!);
      }
      final p = await call(
        '/api/business$path/preview',
        {...body}
          ..remove('request_id')
          ..remove('confirmation')
          ..remove('preview_hash'),
      ) as Map<String, dynamic>;
      p.remove('expected_revision');
      p.remove('state_hash');
      p.addAll({
        'id': '7' * 32,
        'sequence': 1,
        'revision': ++revision,
        'previous_state_hash': '0' * 64,
        'created_by': '8' * 32,
        'created_at': '2026-11-02T10:00:00Z',
      });
      refundRequests[id] = base.copy(body);
      refundResults[id] = base.copy(p);
      entries.add(base.copy(p));
      if (confirmReply != null) await confirmReply!.future;
      if (lost) {
        lost = false;
        throw const ApiException(0, 'Antwort verloren');
      }
      return base.copy(p);
    }
    throw StateError(routePath);
  }
}

void main() {
  Future<BusinessSession> show(
    WidgetTester tester,
    RefundApi api, {
    double width = 1200,
    bool entry = false,
    bool offline = false,
    String? project,
  }) async {
    tester.view.physicalSize = Size(width, 1000);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    final session = BusinessSession(
      api: api,
      offlineMode: offline,
      projectId: project,
    );
    base.activeApi = api;
    base.activeSession = session;
    await session.load();
    if (entry)
      api.events.add({
        'id': eventId,
        'sequence': 1,
        'account': api.account,
        'direction': 'out',
        'amount': '26.44',
        'cash_date': '2026-11-02',
        'evidence_reference': 'REFUND-EVIDENCE',
        'source': {
          'kind': 'payment',
          'id': base.paymentId,
          'snapshot': {...api.payment, 'kind': 'refund'},
        },
        'unresolved_reasons': ['refund_origin_unresolved'],
      });
    await tester.pumpWidget(
      MaterialApp(
        theme: officeTheme(),
        home: entry
            ? BusinessAccountingPage(session: session)
            : BusinessRefundOriginsPage(session: session, eventId: eventId),
      ),
    );
    await tester.pumpAndSettle();
    return session;
  }

  Future<void> value(WidgetTester tester, String entry, String amount) async {
    final field = find.byKey(ValueKey('refund-origin-$entry:$groupId'));
    await tester.ensureVisible(field);
    await tester.enterText(field, amount);
    await tester.pumpAndSettle();
  }

  Future<void> choose(WidgetTester tester, {bool pages = false}) async {
    await base.press(tester, 'Ursprünge für diesen Anteil wählen');
    await value(tester, firstEntry, '13,22');
    if (pages) await base.press(tester, 'Weitere Ursprünge laden');
    await value(tester, secondEntry, '13,22');
    await tester.ensureVisible(find.byKey(const ValueKey('refund-reason')));
    await tester.enterText(
      find.byKey(const ValueKey('refund-reason')),
      'Synthetisch belegte Herkunft',
    );
    await tester.pumpAndSettle();
  }

  Future<void> preview(WidgetTester tester, {bool pages = false}) async {
    await choose(tester, pages: pages);
    await base.press(tester, 'Erstattungsursprung vorschauen');
  }

  Future<void> reopen(WidgetTester tester, BusinessSession session) async {
    await tester.pumpWidget(const SizedBox());
    await tester.pumpWidget(
      MaterialApp(
        theme: officeTheme(),
        home: BusinessRefundOriginsPage(session: session, eventId: eventId),
      ),
    );
    await tester.pumpAndSettle();
  }

  for (final width in [390.0, 1200.0]) {
    base.accountingWidgetTest(
      'refund entry and exact separate confirmation at $width',
      (tester) async {
        final api = RefundApi();
        await show(tester, api, width: width, entry: true);
        await base.press(tester, 'Geldfluss ansehen');
        expect(
          find.textContaining(
            'Bei der Übernahme war der Erstattungsursprung ungeklärt.',
          ),
          findsOneWidget,
        );
        await base.press(tester, 'Erstattungsursprünge ansehen');
        await preview(tester);
        expect(api.entries, isEmpty);
        expect(
          find.text(
            'Dokumentierte Rücknahme: netto 22,22 € · ausgewiesene Steuer 4,22 € · brutto 26,44 €',
          ),
          findsOneWidget,
        );
        expect(find.text('Dokumentierte Aufteilung Nr. 11'), findsOneWidget);
        expect(find.text('Dokumentierte Aufteilung Nr. 12'), findsOneWidget);
        await base.press(tester, 'Erstattungsursprung verbindlich bestätigen');
        expect(api.entries, hasLength(1));
        expect(find.text('Bestätigte Ursprungsbindung Nr. 1'), findsOneWidget);
        expect(find.textContaining('gibt keine Belegbeträge'), findsOneWidget);
        expect(tester.takeException(), isNull);
      },
    );
  }
  base.accountingWidgetTest(
    'same group across paginated entries keeps explicit selections and original request order',
    (tester) async {
      final api = RefundApi()..pages = true;
      await show(tester, api);
      await preview(tester, pages: true);
      final first = api.calls
          .firstWhere((c) => c.path.endsWith('/preview'))
          .body!;
      expect((first['origins'] as List).map((o) => o['entry_id']), [
        firstEntry,
        secondEntry,
      ]);
      expect((first['origins'] as List).map((o) => o['group_id']), [
        groupId,
        groupId,
      ]);
      await base.press(tester, 'Erstattungsursprung verbindlich bestätigen');
      expect(api.refundRequests.values.single['origins'], first['origins']);
    },
  );
  base.accountingWidgetTest(
    'no automatic origin selection, exact sum, positive cents and capacity checked before preview',
    (tester) async {
      final api = RefundApi();
      await show(tester, api);
      await base.press(tester, 'Ursprünge für diesen Anteil wählen');
      expect(
        tester
            .widget<TextField>(
              find.byKey(ValueKey('refund-origin-$firstEntry:$groupId')),
            )
            .controller!
            .text,
        isEmpty,
      );
      await chooseReason(tester);
      for (final invalid in ['', '13.222', '-1', '40.00', '13.21']) {
        await value(tester, firstEntry, invalid);
        await base.press(tester, 'Erstattungsursprung vorschauen');
        expect(api.calls.where((c) => c.path.endsWith('/preview')), isEmpty);
      }
    },
  );
  base.accountingWidgetTest(
    'zero tax category and reason remain distinct in preview and history',
    (tester) async {
      final api = RefundApi()..zeroGroups = true;
      await show(tester, api);
      await preview(tester);
      expect(find.textContaining('Kategorie laut Beleg: Z'), findsOneWidget);
      expect(find.textContaining('Kategorie laut Beleg: E'), findsOneWidget);
      expect(find.text('Nullsatz laut Archiv'), findsOneWidget);
      expect(find.text('Befreiung laut Archiv'), findsOneWidget);
      await base.press(tester, 'Erstattungsursprung verbindlich bestätigen');
      expect(find.text('Befreiung laut Archiv'), findsOneWidget);
    },
  );
  for (final blocked in [
    'unallocated',
    'source_customer_unresolved',
    'unsupported_document',
    'not_customer_refund',
  ]) {
    base.accountingWidgetTest(
      'blocked $blocked remains readable without invented origins',
      (tester) async {
        final api = RefundApi()..blocked = blocked;
        await show(tester, api);
        expect(find.text('Bestätigter Geldfluss: 26,44 €'), findsOneWidget);
        expect(
          api.calls.where(
            (c) => c.path.contains('/origins') || c.path.endsWith('/preview'),
          ),
          isEmpty,
        );
        expect(find.text('Ursprünge für diesen Anteil wählen'), findsNothing);
      },
    );
  }
  base.accountingWidgetTest(
    'older server keeps historical refund wording and component entry without probing new route',
    (tester) async {
      final api = RefundApi()..refundFeature = false;
      await show(tester, api, entry: true);
      await base.press(tester, 'Geldfluss ansehen');
      expect(
        find.text('Der ursprüngliche Erstattungsbezug ist noch ungeklärt.'),
        findsOneWidget,
      );
      expect(find.text('Aufteilungen ansehen'), findsOneWidget);
      expect(find.text('Erstattungsursprünge ansehen'), findsNothing);
      expect(
        api.calls.where((c) => c.path.contains('/accounting/refunds/')),
        isEmpty,
      );
    },
  );
  for (final gate in [
    'feature',
    'offline',
    'project',
    'accounting.read',
    'finance.read',
  ]) {
    base.accountingWidgetTest('$gate gate prevents unsupported refund reads', (
      tester,
    ) async {
      final api = RefundApi();
      if (gate == 'feature') api.refundFeature = false;
      if (gate.endsWith('.read')) api.rights.remove(gate);
      await show(
        tester,
        api,
        offline: gate == 'offline',
        project: gate == 'project' ? '6' * 32 : null,
      );
      expect(
        api.calls.where((c) => c.path.contains('/accounting/refunds/')),
        isEmpty,
      );
    });
  }
  for (final gate in [
    'readonly',
    'module',
    'accounting.prepare',
    'finance.write',
  ]) {
    base.accountingWidgetTest(
      '$gate allows history but no origin selection or preview',
      (tester) async {
        final api = RefundApi();
        if (gate == 'readonly') api.readonly = true;
        if (gate == 'module') api.enabled = false;
        api.rights.remove(gate);
        final session = await show(tester, api);
        expect(find.text('Bestätigter Geldfluss: 26,44 €'), findsOneWidget);
        expect(
          api.calls.where(
            (c) => c.path.contains('/portions') || c.path.contains('/origins'),
          ),
          isEmpty,
        );
        await expectLater(
          session.previewRefundOrigins(eventId, {}),
          throwsA(isA<ApiException>()),
        );
        expect(api.calls.where((c) => c.path.endsWith('/preview')), isEmpty);
      },
    );
  }
  base.accountingWidgetTest(
    'lost response reopens frozen preview and exact ID after candidate consumed',
    (tester) async {
      final api = RefundApi()..lost = true;
      final session = await show(tester, api);
      await preview(tester);
      await base.press(tester, 'Erstattungsursprung verbindlich bestätigen');
      expect(session.pending(pendingKey), true);
      final original = api.refundRequests.values.single;
      await reopen(tester, session);
      expect(
        find.text('Unbestätigte Übertragung · ursprüngliche Vorschau'),
        findsOneWidget,
      );
      expect(
        api.calls
            .where((c) => c.path.endsWith('/accounting/events/$firstEvent'))
            .length,
        greaterThan(1),
      );
      expect(
        api.calls
            .where((c) => c.path.endsWith('/accounting/events/$secondEvent'))
            .length,
        greaterThan(1),
      );
      await base.press(tester, 'Unverändert erneut senden');
      final sent = api.calls
          .where((c) => c.path.endsWith('/confirm'))
          .map((c) => c.body)
          .toList();
      expect(sent, [original, original]);
      expect(api.entries, hasLength(1));
      expect(session.pending(pendingKey), false);
    },
  );
  base.accountingWidgetTest(
    'unsent pending hides origin expanded from project A to denied A+B while refund stays readable',
    (tester) async {
      final api = RefundApi()..beforeServer = true;
      final session = await show(tester, api);
      await preview(tester);
      await base.press(tester, 'Erstattungsursprung verbindlich bestätigen');
      api.deniedOrigin = secondEvent;
      await reopen(tester, session);
      expect(find.textContaining('ORIGIN-FIRST'), findsNothing);
      expect(find.textContaining('ORIGIN-SECOND'), findsNothing);
      expect(find.textContaining('Synthetisch belegte Herkunft'), findsNothing);
      expect(session.pending(pendingKey), true);
      expect(
        find.text('Erstattungsursprünge nicht freigegeben'),
        findsOneWidget,
      );
    },
  );
  base.accountingWidgetTest(
    'previously bound origin denial blocks pending restore at source-state preflight',
    (tester) async {
      final api = RefundApi()..lost = true;
      final session = await show(tester, api);
      await preview(tester);
      await base.press(tester, 'Erstattungsursprung verbindlich bestätigen');
      expect(api.entries, hasLength(1));
      expect(session.pending(pendingKey), true);
      // The refund endpoint rejects the complete view after a prior bound origin
      // loses a project grant, even when the original refund itself remains A-only.
      api.sourceDenied = true;
      final before = api.calls
          .where((c) => c.path.endsWith('/accounting/events/$firstEvent'))
          .length;
      await reopen(tester, session);
      expect(find.textContaining('ORIGIN-FIRST'), findsNothing);
      expect(find.textContaining('Synthetisch belegte Herkunft'), findsNothing);
      expect(
        api.calls
            .where((c) => c.path.endsWith('/accounting/events/$firstEvent'))
            .length,
        before,
      );
      expect(session.pending(pendingKey), true);
    },
  );
  base.accountingWidgetTest(
    'logout erases uncertain refund command and preview from RAM',
    (tester) async {
      final api = RefundApi()..beforeServer = true;
      final session = await show(tester, api);
      await preview(tester);
      await base.press(tester, 'Erstattungsursprung verbindlich bestätigen');
      expect(session.pending(pendingKey), true);
      api.token = null;
      session.revoke();
      await tester.pumpAndSettle();
      expect(session.pending(pendingKey), false);
      expect(session.pendingEditorValues(pendingKey), isNull);
      expect(find.textContaining('ORIGIN-FIRST'), findsNothing);
    },
  );
  base.accountingWidgetTest(
    'known source denial clears existing private view',
    (tester) async {
      final api = RefundApi();
      await show(tester, api);
      await preview(tester);
      api.sourceDenied = true;
      await tester.tap(find.byTooltip('Erstattungsursprünge aktualisieren'));
      await tester.pumpAndSettle();
      expect(find.textContaining('ORIGIN-FIRST'), findsNothing);
      expect(find.textContaining('26,44'), findsNothing);
    },
  );
  base.accountingWidgetTest('confirm rechecks each origin before sending', (
    tester,
  ) async {
    final api = RefundApi();
    await show(tester, api);
    await preview(tester);
    api.deniedOrigin = secondEvent;
    await base.press(tester, 'Erstattungsursprung verbindlich bestätigen');
    expect(api.calls.where((c) => c.path.endsWith('/confirm')), isEmpty);
    expect(find.textContaining('ORIGIN-FIRST'), findsNothing);
  });
  base.accountingWidgetTest(
    'source state conflict does not send confirmation',
    (tester) async {
      final api = RefundApi()..stale = true;
      await show(tester, api);
      await preview(tester);
      tester
          .state<ScrollableState>(find.byType(Scrollable).first)
          .position
          .jumpTo(0);
      await tester.pumpAndSettle();
      expect(
        find.text('Ursprungsstand geändert. Bitte neu prüfen.'),
        findsOneWidget,
      );
      expect(api.calls.where((c) => c.path.endsWith('/confirm')), isEmpty);
    },
  );
  base.accountingWidgetTest(
    'late preview after logout cannot expose origins and drops RAM pending',
    (tester) async {
      final api = RefundApi();
      final session = await show(tester, api);
      await choose(tester);
      api.previewReply = Completer<void>();
      await tester.ensureVisible(find.text('Erstattungsursprung vorschauen'));
      await tester.tap(find.text('Erstattungsursprung vorschauen'));
      await tester.pump();
      api.token = null;
      api.previewReply!.complete();
      await tester.pumpAndSettle();
      expect(find.text('Erstattungsursprung prüfen'), findsNothing);
      expect(session.pending(pendingKey), false);
    },
  );
  base.accountingWidgetTest(
    'in-flight reopen preserves original data and late ACK refreshes history',
    (tester) async {
      final api = RefundApi();
      final session = await show(tester, api);
      await preview(tester);
      api.confirmReply = Completer<void>();
      await tester.ensureVisible(
        find.text('Erstattungsursprung verbindlich bestätigen'),
      );
      await tester.tap(find.text('Erstattungsursprung verbindlich bestätigen'));
      await tester.pump();
      expect(session.pending(pendingKey), true);
      expect(session.pendingEditorValues(pendingKey), isNotNull);
      await tester.pumpWidget(const SizedBox());
      api.historyReply = Completer<void>();
      await tester.pumpWidget(
        MaterialApp(
          home: BusinessRefundOriginsPage(session: session, eventId: eventId),
        ),
      );
      await tester.pump();
      api.confirmReply!.complete();
      await tester.pump();
      api.historyReply!.complete();
      await tester.pumpAndSettle();
      expect(find.text('Bestätigte Ursprungsbindung Nr. 1'), findsOneWidget);
      expect(find.text('Unverändert erneut senden'), findsNothing);
      expect(api.calls.where((c) => c.path.endsWith('/confirm')), hasLength(1));
    },
  );
  base.accountingWidgetTest(
    'old confirmation ACK during retry metadata cannot create a new command',
    (tester) async {
      final api = RefundApi();
      final session = await show(tester, api);
      await preview(tester);
      api.confirmReply = Completer<void>();
      await tester.ensureVisible(
        find.text('Erstattungsursprung verbindlich bestätigen'),
      );
      await tester.tap(find.text('Erstattungsursprung verbindlich bestätigen'));
      await tester.pump();
      await reopen(tester, session);
      api.originReply = Completer<void>();
      await tester.ensureVisible(find.text('Unverändert erneut senden'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Unverändert erneut senden'));
      await tester.pump();
      api.confirmReply!.complete();
      await tester.pump();
      api.originReply!.complete();
      await tester.pumpAndSettle();
      expect(api.calls.where((c) => c.path.endsWith('/confirm')), hasLength(1));
      tester
          .state<ScrollableState>(find.byType(Scrollable).first)
          .position
          .jumpTo(0);
      await tester.pumpAndSettle();
      expect(
        find.textContaining('frühere Übertragung wurde inzwischen beantwortet'),
        findsOneWidget,
      );
    },
  );
}

Future<void> chooseReason(WidgetTester tester) async {
  await tester.ensureVisible(find.byKey(const ValueKey('refund-reason')));
  await tester.enterText(
    find.byKey(const ValueKey('refund-reason')),
    'Synthetisch belegte Herkunft',
  );
  await tester.pumpAndSettle();
}

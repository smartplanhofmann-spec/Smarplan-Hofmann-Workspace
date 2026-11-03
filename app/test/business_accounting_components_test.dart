import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:smartplan_office/api.dart';
import 'package:smartplan_office/business_accounting.dart';
import 'package:smartplan_office/business_accounting_components.dart';
import 'package:smartplan_office/business_session.dart';
import 'package:smartplan_office/design.dart';

import 'business_accounting_test.dart' as base;

const eventId = '11111111111111111111111111111111';
const receiptId = base.receiptId;
String get portionId => 'a' * 64;
String get groupId => 'b' * 64;
String get secondGroup => 'c' * 64;
int cents(Object? v) => int.parse('$v'.replaceAll('.', ''));
String money(int n) => '${n ~/ 100}.${(n % 100).toString().padLeft(2, '0')}';

class ComponentsApi extends base.AccountingApi {
  ComponentsApi() {
    rights.add('finance.write');
  }
  bool componentFeature = true,
      multi = false,
      refund = false,
      sourceDenied = false,
      targetDenied = false,
      stale = false,
      lost = false,
      beforeServer = false,
      pages = false;
  Completer<void>? delayedPreview, delayedConfirm;
  int revision = 0;
  final entries = <Map<String, dynamic>>[];
  final componentRequests = <String, Map<String, dynamic>>{},
      componentResults = <String, Map<String, dynamic>>{};
  Map<String, dynamic> group(String id, String net, String tax, String rate) =>
      {
        'group_id': id,
        'rate': multi ? rate : null,
        'category': multi ? 'S' : null,
        'reason': null,
        'net': net,
        'tax': tax,
        'gross': money(cents(net) + cents(tax)),
        'documented_net': '0.00',
        'documented_tax': '0.00',
        'documented_gross': '0.00',
        'remaining_net': net,
        'remaining_tax': tax,
        'remaining_gross': money(cents(net) + cents(tax)),
      };
  Map<String, dynamic> get portion => {
    'portion_id': portionId,
    'kind': multi ? 'original_allocation' : 'supplier_payout',
    'event_id': eventId,
    'document_id': multi ? base.paymentId : null,
    'receipt_id': multi ? null : receiptId,
    'project_id': 'd' * 32,
    'number': 'SYN-119',
    'party_name': 'Synthetischer Geschäftspartner',
    'amount': multi ? '60.00' : '39.67',
    'currency': 'EUR',
    'payload_sha256': multi ? '1' * 64 : null,
    'pdf_sha256': multi ? '2' * 64 : null,
    'original_sha256': multi ? null : '3' * 64,
    'review_revision': multi ? null : 1,
    'review_sha256': multi ? null : '4' * 64,
    'portion_state_hash': '5' * 64,
    'eligible': !stale,
    'blocked_reason': stale ? 'review_changed' : null,
    'groups': [
      group(groupId, '100.00', '19.00', '19'),
      if (multi) group(secondGroup, '50.00', '3.50', '7'),
    ],
  };
  Map<String, dynamic> get state => {
    'event_id': eventId,
    'source_hash': '6' * 64,
    'revision': revision,
    'state_hash': revision == 0 ? '7' * 64 : '8' * 64,
    'source_kind': refund
        ? 'customer_refund'
        : multi
        ? 'customer_receipt'
        : 'supplier_payout',
    'amount': portion['amount'],
    'currency': 'EUR',
    'documented_amount': revision == 0 ? '0.00' : portion['amount'],
    'undocumented_amount': revision == 0 ? portion['amount'] : '0.00',
    'unallocated_amount': '0.00',
    'eligible': !refund && revision == 0,
    'blocked_reason': refund
        ? 'refund_origin_unresolved'
        : revision > 0
        ? 'fully_documented'
        : null,
    'writes_allowed':
        writes &&
        enabled &&
        !readonly &&
        rights.contains('finance.write') &&
        rights.contains('accounting.prepare'),
    'scope': 'authorized_sources',
    'tax_status': 'unconfigured',
    'tax_result_available': false,
  };
  @override
  Future<dynamic> call(String path, [Map<String, dynamic>? body]) async {
    final route = path.split('?').first;
    if (route == '/api/business/capabilities') {
      final result = base.copy(
        await super.call(path, body) as Map<String, dynamic>,
      );
      (result['capabilities'] as List).add('business_accounting_components');
      if (componentFeature)
        (result['features'] as List).add('accounting_document_components');
      return result;
    }
    if (route == '/api/business/finance/receipts/$receiptId' ||
        route == '/api/business/documents/${base.paymentId}') {
      calls.add((path: path, body: body));
      if (targetDenied) throw const ApiException(403, 'Belegzugriff entzogen');
      return {'id': receiptId};
    }
    if (route == '/api/business/accounting/events/$eventId' && events.isEmpty) {
      calls.add((path: path, body: body));
      if (sourceDenied)
        throw const ApiException(403, 'Geldflusszugriff entzogen');
      return {'id': eventId};
    }
    if (!route.contains('/accounting/components/'))
      return super.call(path, body);
    calls.add((path: path, body: body == null ? null : base.copy(body)));
    if (sourceDenied)
      throw const ApiException(403, 'Geldflusszugriff entzogen');
    if (body == null) {
      if (route.endsWith('/history'))
        return {
          'items': entries.map(base.copy).toList(),
          'total': entries.length,
          'next_offset': null,
          'scope': 'authorized_sources',
        };
      if (route.endsWith('/portions')) {
        final offset = Uri.parse(path).queryParameters['offset'];
        return {
          'items': [
            if (revision == 0)
              {...portion, if (pages && offset != '0') 'number': 'SYN-PAGE-2'},
          ],
          'total': pages ? 2 : 1,
          'next_offset': pages && offset == '0' ? 50 : null,
          'scope': 'authorized_sources',
        };
      }
      return state;
    }
    if (route.endsWith('/preview')) {
      expect(body.containsKey('request_id'), false);
      expect(body.containsKey('confirmation'), false);
      if (stale)
        throw const ApiException(
          409,
          'Quellenstand geändert. Bitte neu prüfen.',
        );
      final lines = <Map<String, dynamic>>[];
      for (final item in body['groups'] as List) {
        final g = (portion['groups'] as List).firstWhere(
          (g) => g['group_id'] == item['group_id'],
        );
        final gross = cents(item['amount']),
            capacity = cents(g['gross']),
            tax =
                (2 * cents(item['amount']) * cents(g['tax']) +
                    cents(g['gross'])) ~/
                (2 * cents(g['gross']));
        lines.add({
          'group_id': item['group_id'],
          'amount': item['amount'],
          'net': money(gross - tax),
          'tax': money(tax),
          'gross_before': '0.00',
          'gross_after': item['amount'],
          'net_before': '0.00',
          'net_after': money(gross - tax),
          'tax_before': '0.00',
          'tax_after': money(tax),
          'remaining_gross': money(capacity - gross),
        });
      }
      final result = <String, dynamic>{
        'event_id': eventId,
        'source_hash': body['source_hash'],
        'expected_revision': body['expected_revision'],
        'state_hash': body['state_hash'],
        'portion': base.copy(portion),
        'amount': portion['amount'],
        'net': money(lines.fold(0, (n, l) => n + cents(l['net']))),
        'tax': money(lines.fold(0, (n, l) => n + cents(l['tax']))),
        'lines': lines,
        'reason': body['reason'],
        'preview_hash': '9' * 64,
        'scope': 'authorized_sources',
        'tax_status': 'unconfigured',
        'tax_result_available': false,
      };
      componentResults['preview'] = base.copy(result);
      if (delayedPreview != null) await delayedPreview!.future;
      return result;
    }
    expect(route.endsWith('/confirm'), true);
    if (beforeServer) {
      beforeServer = false;
      throw const ApiException(0, 'Vor Annahme verloren');
    }
    final id = body['request_id'] as String;
    if (componentRequests.containsKey(id)) {
      expect(body, componentRequests[id]);
      return base.copy(componentResults[id]!);
    }
    if (stale || revision != body['expected_revision'])
      throw const ApiException(409, 'Gruppenstand geändert. Bitte neu prüfen.');
    expect(body['confirmation'], true);
    final result =
        <String, dynamic>{
            ...componentResults['preview']!,
            'id': 'e' * 32,
            'sequence': 1,
            'revision': ++revision,
            'previous_state_hash': body['state_hash'],
            'created_by': 'synthetic-worker',
            'created_at': '2026-11-02T12:00:00Z',
          }
          ..remove('expected_revision')
          ..remove('state_hash');
    entries.add(base.copy(result));
    componentRequests[id] = base.copy(body);
    componentResults[id] = base.copy(result);
    if (delayedConfirm != null) await delayedConfirm!.future;
    if (lost) {
      lost = false;
      throw const ApiException(0, 'Antwort verloren');
    }
    return result;
  }
}

class ZeroGroupsApi extends ComponentsApi {
  ZeroGroupsApi() {
    multi = true;
  }
  @override
  Map<String, dynamic> get portion {
    final value = super.portion;
    for (final g in value['groups'] as List) {
      final first = g['group_id'] == groupId;
      g.addAll({
        'rate': '0',
        'category': first ? 'Z' : 'E',
        'reason': first ? 'Nullsatz laut Original' : 'Befreiung laut Original',
        'tax': '0.00',
        'gross': g['net'],
        'remaining_tax': '0.00',
        'remaining_gross': g['net'],
      });
    }
    return value;
  }
}

class HistoryDelayApi extends ComponentsApi {
  Completer<void>? historyReply;
  @override
  Future<dynamic> call(String path, [Map<String, dynamic>? body]) async {
    if (path.contains('/components/') &&
        path.split('?').first.endsWith('/history') &&
        historyReply != null)
      await historyReply!.future;
    return super.call(path, body);
  }
}

class LargeGroupApi extends ComponentsApi {
  static const large = '999999999999999999999999999.00';
  @override
  Map<String, dynamic> get portion => {
    ...super.portion,
    'groups': [
      {
        ...super.group(groupId, '100.00', '0.00', '0'),
        'net': large,
        'gross': large,
        'remaining_net': large,
        'remaining_gross': large,
      },
    ],
  };
  @override
  Future<dynamic> call(String path, [Map<String, dynamic>? body]) async {
    if (body != null &&
        path.contains('/components/') &&
        path.endsWith('/preview')) {
      calls.add((path: path, body: base.copy(body)));
      final remaining =
          BigInt.parse(large.replaceAll('.', '')) - BigInt.from(3967);
      final remainingText =
          '${remaining ~/ BigInt.from(100)}.${(remaining % BigInt.from(100)).toString().padLeft(2, '0')}';
      return {
        'event_id': eventId,
        'source_hash': body['source_hash'],
        'expected_revision': 0,
        'state_hash': body['state_hash'],
        'portion': portion,
        'amount': '39.67',
        'net': '39.67',
        'tax': '0.00',
        'lines': [
          {
            'group_id': groupId,
            'amount': '39.67',
            'net': '39.67',
            'tax': '0.00',
            'gross_before': '0.00',
            'gross_after': '39.67',
            'net_before': '0.00',
            'net_after': '39.67',
            'tax_before': '0.00',
            'tax_after': '0.00',
            'remaining_gross': remainingText,
          },
        ],
        'reason': body['reason'],
        'preview_hash': '9' * 64,
        'scope': 'authorized_sources',
        'tax_status': 'unconfigured',
        'tax_result_available': false,
      };
    }
    return super.call(path, body);
  }
}

void main() {
  Future<BusinessSession> show(
    WidgetTester tester,
    ComponentsApi api, {
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
    base.activeSession = session;
    base.activeApi = api;
    await session.load();
    if (entry)
      api.events.add({
        'id': eventId,
        'sequence': 1,
        'account': api.account,
        'direction': 'out',
        'amount': '39.67',
        'cash_date': '2026-11-02',
        'evidence_reference': 'SYN-FLOW',
        'source': {'kind': 'receipt', 'id': receiptId, 'snapshot': api.receipt},
        'unresolved_reasons': ['tax_profile_unconfigured'],
      });
    await tester.pumpWidget(
      MaterialApp(
        theme: officeTheme(),
        home: entry
            ? BusinessAccountingPage(session: session)
            : BusinessDocumentComponentsPage(
                session: session,
                eventId: eventId,
              ),
      ),
    );
    await tester.pumpAndSettle();
    return session;
  }

  Future<void> choose(WidgetTester tester) async {
    await base.press(tester, 'Diesen Beleganteil aufteilen');
    await tester.ensureVisible(find.byKey(const ValueKey('component-reason')));
    await tester.enterText(
      find.byKey(const ValueKey('component-reason')),
      'Synthetisch geprüfte Belegaufteilung',
    );
    await tester.pumpAndSettle();
  }

  Future<void> value(WidgetTester tester, String id, String value) async {
    final field = find.byKey(ValueKey('component-group-$id'));
    await tester.ensureVisible(field);
    await tester.enterText(field, value);
    await tester.pumpAndSettle();
  }

  Future<void> reopen(WidgetTester tester, BusinessSession session) async {
    await tester.pumpWidget(const SizedBox());
    await tester.pumpWidget(
      MaterialApp(
        theme: officeTheme(),
        home: BusinessDocumentComponentsPage(
          session: session,
          eventId: eventId,
        ),
      ),
    );
    await tester.pumpAndSettle();
  }

  for (final width in [390.0, 1200.0]) {
    base.accountingWidgetTest(
      'single reviewed group previews exact documentary cents and confirms separately at $width',
      (tester) async {
        final api = ComponentsApi();
        await show(tester, api, width: width, entry: true);
        await base.press(tester, 'Geldfluss ansehen');
        await base.press(tester, 'Beleganteile aufteilen');
        await choose(tester);
        expect(
          tester
              .widget<TextField>(
                find.byKey(ValueKey('component-group-$groupId')),
              )
              .controller!
              .text,
          '39,67',
        );
        await base.press(tester, 'Belegaufteilung vorschauen');
        expect(api.entries, isEmpty);
        expect(find.text('Belegter Nettoanteil: 33,34 €'), findsOneWidget);
        expect(
          find.text('Ausgewiesener Steueranteil laut Prüfung: 6,33 €'),
          findsOneWidget,
        );
        await base.press(tester, 'Belegaufteilung verbindlich bestätigen');
        expect(api.entries, hasLength(1));
        expect(find.text('Bestätigte Aufteilung Nr. 1'), findsOneWidget);
        expect(tester.takeException(), isNull);
      },
    );
  }
  base.accountingWidgetTest(
    'multiple groups start empty and require exact explicit total',
    (tester) async {
      final api = ComponentsApi()..multi = true;
      await show(tester, api);
      await choose(tester);
      expect(
        tester
            .widget<TextField>(find.byKey(ValueKey('component-group-$groupId')))
            .controller!
            .text,
        '',
      );
      await base.press(tester, 'Belegaufteilung vorschauen');
      expect(
        find.text(
          'Die Gruppenbeträge müssen zusammen genau den ganzen Beleganteil ergeben.',
        ),
        findsOneWidget,
      );
      await value(tester, groupId, '40,00');
      await value(tester, secondGroup, '19,99');
      await base.press(tester, 'Belegaufteilung vorschauen');
      expect(api.calls.where((c) => c.body != null), isEmpty);
      await value(tester, secondGroup, '20');
      await base.press(tester, 'Belegaufteilung vorschauen');
      final body = api.calls
          .lastWhere((c) => c.path.endsWith('/preview'))
          .body!;
      expect(body['groups'], [
        {'group_id': groupId, 'amount': '40.00'},
        {'group_id': secondGroup, 'amount': '20.00'},
      ]);
      expect(
        find.text('Ausgewiesener Steueranteil laut Beleg: 7,70 €'),
        findsOneWidget,
      );
    },
  );
  base.accountingWidgetTest(
    'zero groups are omitted and extra decimals never rounded',
    (tester) async {
      final api = ComponentsApi()..multi = true;
      await show(tester, api);
      await choose(tester);
      await value(tester, groupId, '60,001');
      await value(tester, secondGroup, '0');
      await base.press(tester, 'Belegaufteilung vorschauen');
      expect(api.calls.where((c) => c.body != null), isEmpty);
      await value(tester, groupId, '60');
      await base.press(tester, 'Belegaufteilung vorschauen');
      expect(
        api.calls.lastWhere((c) => c.path.endsWith('/preview')).body!['groups'],
        [
          {'group_id': groupId, 'amount': '60.00'},
        ],
      );
    },
  );
  base.accountingWidgetTest('group capacity is checked before preview', (
    tester,
  ) async {
    final api = ComponentsApi()..multi = true;
    await show(tester, api);
    await choose(tester);
    await value(tester, secondGroup, '60');
    await base.press(tester, 'Belegaufteilung vorschauen');
    expect(find.textContaining('verfügbaren Bruttobetrag'), findsOneWidget);
    expect(api.calls.where((c) => c.body != null), isEmpty);
  });
  base.accountingWidgetTest(
    'lost reply restores original groups and reviewed preview despite changed review',
    (tester) async {
      final api = ComponentsApi()..lost = true;
      final session = await show(tester, api);
      await choose(tester);
      await base.press(tester, 'Belegaufteilung vorschauen');
      await base.press(tester, 'Belegaufteilung verbindlich bestätigen');
      api.stale = true;
      await reopen(tester, session);
      expect(
        find.text('Unbestätigte Übertragung · ursprüngliche Vorschau'),
        findsOneWidget,
      );
      await base.press(tester, 'Unverändert erneut senden');
      final sent = api.calls.where((c) => c.path.endsWith('/confirm')).toList();
      expect(sent, hasLength(2));
      expect(sent[0].body, sent[1].body);
      expect(api.entries, hasLength(1));
    },
  );
  base.accountingWidgetTest(
    'inflight reopen restores preview and late ACK never becomes a new component command',
    (tester) async {
      final api = ComponentsApi()..delayedConfirm = Completer<void>();
      final session = await show(tester, api);
      await choose(tester);
      await base.press(tester, 'Belegaufteilung vorschauen');
      await tester.ensureVisible(
        find.text('Belegaufteilung verbindlich bestätigen'),
      );
      await tester.pumpAndSettle();
      await tester.tap(find.text('Belegaufteilung verbindlich bestätigen'));
      await tester.pump();
      await reopen(tester, session);
      expect(
        find.text('Unbestätigte Übertragung · ursprüngliche Vorschau'),
        findsOneWidget,
      );
      api.delayedConfirm!.complete();
      await tester.pumpAndSettle();
      await base.press(tester, 'Unverändert erneut senden');
      expect(
        find.textContaining('frühere Übertragung wurde inzwischen beantwortet'),
        findsOneWidget,
      );
      expect(api.calls.where((c) => c.path.endsWith('/confirm')), hasLength(1));
    },
  );
  base.accountingWidgetTest(
    'pending receipt details stay hidden after target403 and retain exact retry',
    (tester) async {
      final api = ComponentsApi()..beforeServer = true;
      final session = await show(tester, api);
      await choose(tester);
      await base.press(tester, 'Belegaufteilung vorschauen');
      await base.press(tester, 'Belegaufteilung verbindlich bestätigen');
      api.targetDenied = true;
      await reopen(tester, session);
      expect(
        find.text('SYN-119 · Synthetischer Geschäftspartner'),
        findsNothing,
      );
      expect(find.text('Belegaufteilung nicht freigegeben'), findsOneWidget);
      expect(session.pending('accounting-components-$eventId'), true);
      api.targetDenied = false;
      await tester.tap(find.byTooltip('Belegaufteilungen aktualisieren'));
      await tester.pumpAndSettle();
      await base.press(tester, 'Unverändert erneut senden');
      final sent = api.calls.where((c) => c.path.endsWith('/confirm')).toList();
      expect(sent[0].body, sent[1].body);
    },
  );
  base.accountingWidgetTest(
    'stale global group pool invalidates a new confirmation',
    (tester) async {
      final api = ComponentsApi();
      await show(tester, api);
      await choose(tester);
      await base.press(tester, 'Belegaufteilung vorschauen');
      api.stale = true;
      await base.press(tester, 'Belegaufteilung verbindlich bestätigen');
      expect(find.textContaining('Gruppenstand geändert'), findsOneWidget);
      expect(api.entries, isEmpty);
      expect(find.text('Belegaufteilung verbindlich bestätigen'), findsNothing);
    },
  );
  for (final mode in ['read', 'readonly', 'paused', 'restore', 'refund']) {
    base.accountingWidgetTest(
      '$mode keeps documentary history readable without portion requests',
      (tester) async {
        final api = ComponentsApi();
        if (mode == 'read') api.rights.remove('finance.write');
        if (mode == 'readonly') api.readonly = true;
        if (mode == 'paused') api.enabled = false;
        if (mode == 'restore') api.writes = false;
        if (mode == 'refund') api.refund = true;
        await show(tester, api);
        expect(find.text('Bestätigter Geldfluss: 39,67 €'), findsOneWidget);
        expect(find.text('Diesen Beleganteil aufteilen'), findsNothing);
        expect(api.calls.where((c) => c.path.contains('/portions')), isEmpty);
        if (mode == 'refund')
          expect(
            find.textContaining('Ursprung dieser Erstattung'),
            findsOneWidget,
          );
      },
    );
  }
  for (final mode in ['feature', 'offline', 'project']) {
    base.accountingWidgetTest('$mode does not probe components routes', (
      tester,
    ) async {
      final api = ComponentsApi();
      if (mode == 'feature') api.componentFeature = false;
      await show(
        tester,
        api,
        offline: mode == 'offline',
        project: mode == 'project' ? 'a' * 32 : null,
      );
      expect(api.calls.where((c) => c.path.contains('/components/')), isEmpty);
    });
  }
  base.accountingWidgetTest(
    'late preview after finance read loss cannot refill the screen',
    (tester) async {
      final api = ComponentsApi()..delayedPreview = Completer<void>();
      final session = await show(tester, api);
      await choose(tester);
      await tester.ensureVisible(find.text('Belegaufteilung vorschauen'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Belegaufteilung vorschauen'));
      await tester.pump();
      api.rights.remove('finance.read');
      await session.load();
      await tester.pump();
      api.delayedPreview!.complete();
      await tester.pumpAndSettle();
      expect(find.text('Belegaufteilung prüfen'), findsNothing);
      expect(
        find.text('SYN-119 · Synthetischer Geschäftspartner'),
        findsNothing,
      );
    },
  );
  base.accountingWidgetTest('server source403 clears a displayed proposal', (
    tester,
  ) async {
    final api = ComponentsApi();
    await show(tester, api);
    await choose(tester);
    await base.press(tester, 'Belegaufteilung vorschauen');
    api.sourceDenied = true;
    await base.press(tester, 'Belegaufteilung verbindlich bestätigen');
    expect(find.text('Belegter Nettoanteil: 33,34 €'), findsNothing);
    expect(api.entries, isEmpty);
  });
  base.accountingWidgetTest(
    'portion paging preserves complete source choices',
    (tester) async {
      final api = ComponentsApi()..pages = true;
      await show(tester, api);
      await base.press(tester, 'Weitere Beleganteile laden');
      expect(
        find.text('SYN-119 · Synthetischer Geschäftspartner'),
        findsOneWidget,
      );
      expect(
        find.text('SYN-PAGE-2 · Synthetischer Geschäftspartner'),
        findsOneWidget,
      );
    },
  );
  base.accountingWidgetTest(
    'equal rates retain distinct archived category and reason in preview and history',
    (tester) async {
      final api = ZeroGroupsApi();
      await show(tester, api);
      await choose(tester);
      await value(tester, groupId, '40');
      await value(tester, secondGroup, '20');
      await base.press(tester, 'Belegaufteilung vorschauen');
      expect(find.text('Kategorie laut Beleg: Z'), findsOneWidget);
      expect(find.text('Kategorie laut Beleg: E'), findsOneWidget);
      expect(find.text('Nullsatz laut Original'), findsOneWidget);
      expect(find.text('Befreiung laut Original'), findsOneWidget);
      await base.press(tester, 'Belegaufteilung verbindlich bestätigen');
      expect(find.text('Kategorie laut Beleg: Z'), findsOneWidget);
      expect(find.text('Kategorie laut Beleg: E'), findsOneWidget);
      expect(find.text('Nullsatz laut Original'), findsOneWidget);
      expect(find.text('Befreiung laut Original'), findsOneWidget);
    },
  );
  base.accountingWidgetTest(
    'acknowledgement during pending history read discards stale confirmation UI',
    (tester) async {
      final api = HistoryDelayApi()..delayedConfirm = Completer<void>();
      final session = await show(tester, api);
      await choose(tester);
      await base.press(tester, 'Belegaufteilung vorschauen');
      await tester.ensureVisible(
        find.text('Belegaufteilung verbindlich bestätigen'),
      );
      await tester.pumpAndSettle();
      await tester.tap(find.text('Belegaufteilung verbindlich bestätigen'));
      await tester.pump();
      api.historyReply = Completer<void>();
      await tester.pumpWidget(const SizedBox());
      await tester.pumpWidget(
        MaterialApp(
          theme: officeTheme(),
          home: BusinessDocumentComponentsPage(
            session: session,
            eventId: eventId,
          ),
        ),
      );
      await tester.pump();
      api.delayedConfirm!.complete();
      await tester.pump();
      api.historyReply!.complete();
      await tester.pumpAndSettle();
      expect(
        find.text('Unbestätigte Übertragung · ursprüngliche Vorschau'),
        findsNothing,
      );
      expect(find.text('Belegaufteilung verbindlich bestätigen'), findsNothing);
      expect(find.text('Bestätigte Aufteilung Nr. 1'), findsOneWidget);
      expect(api.calls.where((c) => c.path.endsWith('/confirm')), hasLength(1));
    },
  );
  base.accountingWidgetTest(
    'large archived group capacity remains exact without native integer overflow',
    (tester) async {
      final api = LargeGroupApi();
      await show(tester, api);
      await choose(tester);
      expect(
        find.textContaining('999.999.999.999.999.999.999.999.999,00'),
        findsWidgets,
      );
      await base.press(tester, 'Belegaufteilung vorschauen');
      expect(api.calls.where((c) => c.path.endsWith('/preview')), hasLength(1));
      expect(find.text('Belegter Nettoanteil: 39,67 €'), findsOneWidget);
      expect(
        find.textContaining('999.999.999.999.999.999.999.999.959,33'),
        findsOneWidget,
      );
      expect(tester.takeException(), isNull);
    },
  );
}

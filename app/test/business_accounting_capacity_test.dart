import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:smartplan_office/api.dart';
import 'package:smartplan_office/business_accounting.dart';
import 'package:smartplan_office/business_accounting_capacity.dart';
import 'package:smartplan_office/business_session.dart';
import 'package:smartplan_office/design.dart';

import 'business_accounting_components_test.dart' as old;
import 'business_accounting_test.dart' as base;

const eventId = old.eventId;
const key = 'accounting-components-$eventId';
const path = '/accounting/components/v2/events/$eventId';
const legacyPath = '/accounting/components/events/$eventId';
String get groupId => old.groupId;
String get zeroGroup => 'd' * 64;

class CapacityApi extends old.ComponentsApi {
  CapacityApi() {
    multi = true;
  }
  bool reuse = true,
      mixed = false,
      legacyOnly = false,
      current = false,
      beforeDate = false,
      hideSources = false,
      loseCapacity = false,
      pendingUnresolved = false;
  bool refundV2Feature = false, refundV2Module = false;
  int capacityRevision = 0, generation = 1;
  int? capacityFailure;
  int? confirmGateFailure;
  String? confirmationResolution;
  bool capacityBeforeServer = false;
  Completer<void>? capacityPreviewReply,
      capacityConfirmReply,
      capacityHistoryReply;
  final capacityEntries = <Map<String, dynamic>>[];
  final capacityRequests = <String, Map<String, dynamic>>{},
      capacityResults = <String, Map<String, dynamic>>{};
  @override
  Map<String, dynamic> get portion => {
    ...super.portion,
    'amount': '39.67',
    'number': 'RE-ALT',
  };
  Map<String, dynamic> amount(String net, String tax, String gross) => {
    'net': net,
    'tax': tax,
    'gross': gross,
  };
  Map<String, dynamic> capacity(String net, String tax, String gross) => {
    ...amount(net, tax, gross),
    'segment_id': current ? '3' * 64 : null,
    'not_before_date': beforeDate ? '2026-11-04' : '2026-11-02',
  };
  List<Map<String, dynamic>> get groups => [
    {
      'group_id': groupId,
      'rate': '19',
      'category': 'S',
      'reason': null,
      'archive': amount('100.00', '19.00', '119.00'),
      'current_capacity': current
          ? capacity('33.33', '6.34', '39.67')
          : capacity('0.00', '0.00', '0.00'),
      'pending_returns': {
        ...amount('33.33', '6.34', '39.67'),
        'not_before_date': '2026-11-02',
      },
      'offered_capacity': capacity('33.33', '6.34', '39.67'),
      'transition': current ? 'none' : 'takeover',
      'group_state_hash': '4' * 64,
    },
    {
      'group_id': zeroGroup,
      'rate': '0',
      'category': 'Z',
      'reason': 'Leere Originalgruppe',
      'archive': amount('0.00', '0.00', '0.00'),
      'current_capacity': capacity('0.00', '0.00', '0.00'),
      'pending_returns': {
        ...amount('0.00', '0.00', '0.00'),
        'not_before_date': null,
      },
      'offered_capacity': capacity('0.00', '0.00', '0.00'),
      'transition': current ? 'none' : 'takeover',
      'group_state_hash': '5' * 64,
    },
  ];
  Map<String, dynamic> get newPortion => {
    'portion_id': 'f' * 64,
    'kind': 'original_allocation',
    'event_id': eventId,
    'document_id': 'e' * 32,
    'customer_id': 'f' * 32,
    'project_id': 'd' * 32,
    'number': 'RE-NEU',
    'party_name': 'Synthetischer Kunde',
    'amount': '39.67',
    'currency': 'EUR',
    'payload_sha256': '1' * 64,
    'pdf_sha256': '2' * 64,
    'ownership_id': current ? 'e' * 32 : null,
    'writer': 'c2',
    'action': hideSources
        ? null
        : current
        ? 'document_current'
        : 'takeover_and_document',
    'refund_status': pendingUnresolved ? 'unresolved' : 'clear',
    'pending_blocked_reason': hideSources
        ? 'source_access_required'
        : pendingUnresolved
        ? 'refund_origin_unresolved'
        : null,
    'portion_state_hash': '6' * 64,
    'eligible': !hideSources && !beforeDate,
    'blocked_reason': hideSources
        ? 'source_access_required'
        : beforeDate
        ? 'receipt_before_capacity'
        : null,
    'groups': groups,
  };
  Map<String, dynamic> get legacyChoice => {
    ...newPortion,
    'portion_id': old.portionId,
    'number': 'RE-ALT',
    'document_id': base.paymentId,
    'writer': 'c1',
    'action': 'document_legacy',
    'groups': [
      for (final group in base.copy(portion)['groups'] as List)
        {
          'group_id': group['group_id'],
          'rate': group['rate'],
          'category': group['category'],
          'reason': group['reason'],
          'archive': amount(group['net'], group['tax'], group['gross']),
          'current_capacity': {
            ...amount(
              group['remaining_net'],
              group['remaining_tax'],
              group['remaining_gross'],
            ),
            'segment_id': null,
            'not_before_date': null,
          },
          'pending_returns': {
            ...amount('0.00', '0.00', '0.00'),
            'not_before_date': null,
          },
          'offered_capacity': {
            ...amount(
              group['remaining_net'],
              group['remaining_tax'],
              group['remaining_gross'],
            ),
            'segment_id': null,
            'not_before_date': null,
          },
          'transition': 'none',
          'group_state_hash': '7' * 64,
        },
    ],
  };
  Map<String, dynamic> get capacityState => {
    'event_id': eventId,
    'source_hash': '8' * 64,
    'revision': capacityRevision,
    'state_hash': '9' * 64,
    'source_kind': 'customer_receipt',
    'amount': mixed ? '79.34' : '39.67',
    'currency': 'EUR',
    'cash_date': '2026-11-03',
    'documented_amount': old.money((capacityRevision + revision) * 3967),
    'undocumented_amount': old.money(
      ((mixed ? 2 : 1) - capacityRevision - revision) * 3967,
    ),
    'unallocated_amount': '0.00',
    'eligible':
        !hideSources && (capacityRevision == 0 || (mixed && revision == 0)),
    'blocked_reason': hideSources
        ? 'source_access_required'
        : capacityRevision > 0
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
  Map<String, dynamic> list(List<Map<String, dynamic>> items) => {
    'items': items.map(base.copy).toList(),
    'total': items.length,
    'next_offset': null,
    'scope': 'authorized_sources',
  };

  @override
  Future<dynamic> call(String routePath, [Map<String, dynamic>? body]) async {
    final route = routePath.split('?').first;
    if (route == '/api/business/capabilities') {
      final result = base.copy(
        await super.call(routePath, body) as Map<String, dynamic>,
      );
      result['generation'] = generation;
      (result['capabilities'] as List).add('business_accounting_capacity');
      if (refundV2Module)
        (result['capabilities'] as List).add('business_accounting_refunds_v2');
      if (refundV2Feature)
        (result['features'] as List).add('accounting_refund_origins_v2');
      if (reuse)
        (result['features'] as List).add('accounting_document_component_reuse');
      return result;
    }
    if (!route.startsWith('/api/business$path'))
      return super.call(routePath, body);
    calls.add((path: routePath, body: body == null ? null : base.copy(body)));
    if (sourceDenied)
      throw const ApiException(
        403,
        'Gesamte gebundene Quelle nicht freigegeben',
      );
    if (body == null) {
      if (route.endsWith('/history')) {
        if (capacityHistoryReply != null) await capacityHistoryReply!.future;
        return list(capacityEntries);
      }
      if (route.endsWith('/portions'))
        return list([
          if ((mixed || legacyOnly) && revision == 0) legacyChoice,
          if (!legacyOnly && capacityRevision == 0) newPortion,
        ]);
      return capacityState;
    }
    if (route.endsWith('/preview')) {
      expect(body.containsKey('request_id'), false);
      expect(body['expected_revision'], capacityRevision);
      expect(body['state_hash'], capacityState['state_hash']);
      if (capacityFailure != null)
        throw ApiException(
          capacityFailure!,
          'Synthetischer Kapazitätskonflikt',
        );
      final result = <String, dynamic>{
        'event_id': eventId,
        'source_hash': body['source_hash'],
        'expected_revision': body['expected_revision'],
        'state_hash': body['state_hash'],
        'action': body['action'],
        'portion': newPortion,
        'amount': '39.67',
        'net': '33.33',
        'tax': '6.34',
        'lines': [
          {
            'group_id': groupId,
            'segment_id': 'a' * 64,
            'amount': '39.67',
            'net': '33.33',
            'tax': '6.34',
            'gross_before': '0.00',
            'gross_after': '39.67',
            'net_before': '0.00',
            'net_after': '33.33',
            'tax_before': '0.00',
            'tax_after': '6.34',
            'remaining_gross': '0.00',
            'remaining_net': '0.00',
            'remaining_tax': '0.00',
          },
        ],
        'capacity_changes': current
            ? []
            : [
                for (final group in groups)
                  {
                    'group_id': group['group_id'],
                    'previous_segment_id': null,
                    'segment_id': 'a' * 64,
                    'carry': amount('0.00', '0.00', '0.00'),
                    'returned': {
                      for (final field in ['net', 'tax', 'gross'])
                        field: (group['pending_returns'] as Map)[field],
                    },
                    'basis': {
                      for (final field in ['net', 'tax', 'gross'])
                        field: (group['offered_capacity'] as Map)[field],
                    },
                    'not_before_date': '2026-11-02',
                  },
              ],
        'reason': body['reason'],
        'preview_hash': 'b' * 64,
        'scope': 'authorized_sources',
        'tax_status': 'unconfigured',
        'tax_result_available': false,
      };
      capacityResults['preview'] = base.copy(result);
      if (capacityPreviewReply != null) await capacityPreviewReply!.future;
      return result;
    }
    if (capacityBeforeServer) {
      capacityBeforeServer = false;
      throw const ApiException(0, 'Synthetisch vor Annahme unterbrochen');
    }
    if (confirmGateFailure != null) {
      throw ApiException(
        confirmGateFailure!,
        'Synthetischer Freigabekonflikt',
        requestResolution: confirmationResolution,
      );
    }
    final id = body['request_id'] as String;
    if (capacityRequests.containsKey(id)) {
      expect(body, capacityRequests[id]);
      return base.copy(capacityResults[id]!);
    }
    if (capacityFailure != null)
      throw ApiException(capacityFailure!, 'Synthetischer Kapazitätskonflikt');
    final result =
        <String, dynamic>{
            ...capacityResults['preview']!,
            'id': 'c' * 32,
            'sequence': 1,
            'revision': ++capacityRevision,
            'previous_state_hash': body['state_hash'],
            'created_by': 'synthetic',
            'created_at': '2026-11-03T12:00:00Z',
          }
          ..remove('expected_revision')
          ..remove('state_hash');
    capacityEntries.add(base.copy(result));
    capacityRequests[id] = base.copy(body);
    capacityResults[id] = base.copy(result);
    if (capacityConfirmReply != null) await capacityConfirmReply!.future;
    if (loseCapacity) {
      loseCapacity = false;
      throw const ApiException(0, 'Synthetisch verlorene Antwort');
    }
    return result;
  }
}

void main() {
  Future<BusinessSession> show(
    WidgetTester tester,
    CapacityApi api, {
    double width = 1200,
    bool offline = false,
    String? project,
    String? entry,
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
    if (entry != null) {
      api.events.add({
        'id': eventId,
        'sequence': 1,
        'account': api.account,
        'direction': entry == 'supplier' ? 'out' : 'in',
        'amount': '39.67',
        'cash_date': '2026-11-03',
        'evidence_reference': 'SYN-ENTRY',
        'source': {
          'kind': entry == 'supplier' ? 'receipt' : 'payment',
          'id': entry == 'supplier' ? base.receiptId : base.paymentId,
          'snapshot': entry == 'supplier' ? api.receipt : api.payment,
        },
        'unresolved_reasons': ['tax_profile_unconfigured'],
      });
    }
    await tester.pumpWidget(
      MaterialApp(
        theme: officeTheme(),
        home: entry == null
            ? BusinessReusableComponentsPage(session: session, eventId: eventId)
            : BusinessAccountingPage(session: session),
      ),
    );
    await tester.pumpAndSettle();
    return session;
  }

  Future<void> reopen(WidgetTester tester, BusinessSession session) async {
    await tester.pumpWidget(const SizedBox());
    await tester.pumpWidget(
      MaterialApp(
        theme: officeTheme(),
        home: BusinessReusableComponentsPage(
          session: session,
          eventId: eventId,
        ),
      ),
    );
    await tester.pumpAndSettle();
  }

  Future<void> fill(WidgetTester tester, {String amount = '39,67'}) async {
    final field = find.byKey(ValueKey('capacity-group-$groupId'));
    await tester.ensureVisible(field);
    await tester.enterText(field, amount);
    final explanation = find.byKey(const ValueKey('capacity-reason'));
    await tester.ensureVisible(explanation);
    await tester.enterText(
      explanation,
      'Synthetisch geprüfte Wiederverwendung',
    );
    await tester.pumpAndSettle();
  }

  Future<void> preview(WidgetTester tester) async {
    await base.press(tester, 'Diesen Beleganteil aufteilen');
    await fill(tester);
    await base.press(tester, 'Belegaufteilung vorschauen');
  }

  Future<void> accept(WidgetTester tester) async {
    final control = find.byKey(const ValueKey('capacity-accept'));
    await tester.ensureVisible(control);
    await tester.pumpAndSettle();
    await tester.tap(control);
    await tester.pumpAndSettle();
  }

  Future<void> confirm(WidgetTester tester) async {
    await accept(tester);
    await base.press(tester, 'Belegaufteilung verbindlich bestätigen');
  }

  for (final width in [390.0, 1200.0]) {
    base.accountingWidgetTest(
      'exact reclaimed cents and all-group takeover require explicit confirmation at $width',
      (tester) async {
        final api = CapacityApi();
        await show(tester, api, width: width);
        await base.press(tester, 'Diesen Beleganteil aufteilen');
        expect(
          tester
              .widget<TextField>(
                find.byKey(ValueKey('capacity-group-$groupId')),
              )
              .controller!
              .text,
          isEmpty,
        );
        expect(find.byKey(ValueKey('capacity-group-$zeroGroup')), findsNothing);
        await fill(tester);
        await base.press(tester, 'Belegaufteilung vorschauen');
        expect(api.capacityEntries, isEmpty);
        expect(
          find.text(
            'Für die hier neu aufgeteilten Zahlungsanteile ist die Zuordnung späterer Erstattungen noch nicht verfügbar.',
          ),
          findsOneWidget,
        );
        expect(
          find.text(
            'Dokumentierter Anteil: netto 33,33 € · ausgewiesene Steuer 6,34 € · brutto 39,67 €',
          ),
          findsOneWidget,
        );
        expect(find.text('Leere Originalgruppe'), findsOneWidget);
        expect(
          tester
              .widget<FilledButton>(
                find.widgetWithText(
                  FilledButton,
                  'Belegaufteilung verbindlich bestätigen',
                ),
              )
              .onPressed,
          isNull,
        );
        await confirm(tester);
        expect(api.capacityEntries, hasLength(1));
        expect(
          find.text('Aufteilung mit wiederverwendbaren Beträgen Nr. 1'),
          findsOneWidget,
        );
        expect(tester.takeException(), isNull);
      },
    );
  }
  for (final entry in [
    ('receipt', true),
    ('receipt', false),
    ('supplier', true),
  ]) {
    base.accountingWidgetTest(
      'accounting entry selects additive capacity only for supported incoming cash $entry',
      (tester) async {
        final api = CapacityApi()..reuse = entry.$2;
        await show(tester, api, entry: entry.$1);
        await base.press(tester, 'Geldfluss ansehen');
        await base.press(tester, 'Beleganteile aufteilen');
        expect(
          api.calls.any((c) => c.path.contains('/components/v2/')),
          entry.$1 == 'receipt' && entry.$2,
        );
        expect(find.text('Diesen Beleganteil aufteilen'), findsOneWidget);
      },
    );
  }
  base.accountingWidgetTest(
    'unresolved later refunds preserve existing capacity without an invented release',
    (tester) async {
      final api = CapacityApi()
        ..current = true
        ..pendingUnresolved = true;
      await show(tester, api);
      await preview(tester);
      expect(find.byKey(const ValueKey('capacity-accept')), findsNothing);
      expect(
        find.text(
          'Für die hier neu aufgeteilten Zahlungsanteile ist die Zuordnung späterer Erstattungen noch nicht verfügbar.',
        ),
        findsOneWidget,
      );
      final body = api.calls
          .lastWhere((c) => c.path.endsWith('/preview'))
          .body!;
      expect(body['action'], 'document_current');
      await base.press(tester, 'Belegaufteilung verbindlich bestätigen');
      expect(api.capacityEntries.single['capacity_changes'], isEmpty);
    },
  );
  base.accountingWidgetTest(
    'legacy action uses original writer state and hashes, then separate unchanged history',
    (tester) async {
      final api = CapacityApi()..legacyOnly = true;
      await show(tester, api);
      await preview(tester);
      final sent = api.calls.lastWhere((c) => c.path.endsWith('/preview'));
      expect(sent.path, '/api/business$legacyPath/preview');
      expect(sent.body!['state_hash'], api.state['state_hash']);
      expect(sent.body!['source_hash'], api.state['source_hash']);
      expect(sent.body!.containsKey('action'), false);
      await base.press(tester, 'Belegaufteilung verbindlich bestätigen');
      expect(api.entries, hasLength(1));
      expect(api.capacityEntries, isEmpty);
      expect(find.text('Frühere Belegaufteilung Nr. 1'), findsOneWidget);
    },
  );
  base.accountingWidgetTest(
    'mixed event documents each whole portion with its own writer',
    (tester) async {
      final api = CapacityApi()..mixed = true;
      await show(tester, api);
      final legacyCard = find.ancestor(
        of: find.text('RE-ALT · Synthetischer Kunde'),
        matching: find.byType(Card),
      );
      final action = find.descendant(
        of: legacyCard,
        matching: find.text('Diesen Beleganteil aufteilen'),
      );
      await tester.ensureVisible(action);
      await tester.tap(action);
      await tester.pumpAndSettle();
      await fill(tester);
      await base.press(tester, 'Belegaufteilung vorschauen');
      await base.press(tester, 'Belegaufteilung verbindlich bestätigen');
      await preview(tester);
      await confirm(tester);
      expect(api.entries, hasLength(1));
      expect(api.capacityEntries, hasLength(1));
      tester
          .state<ScrollableState>(find.byType(Scrollable).first)
          .position
          .jumpTo(0);
      await tester.pumpAndSettle();
      expect(
        find.text(
          'Insgesamt dokumentiert: 79,34 € · Noch nicht dokumentiert: 0,00 €',
        ),
        findsOneWidget,
      );
      expect(
        api.calls.where((c) => c.path.endsWith('/confirm')).map((c) => c.path),
        ['/api/business$legacyPath/confirm', '/api/business$path/confirm'],
      );
    },
  );
  for (final invalid in ['', '-1', '39.671', '39.66', '40.00']) {
    base.accountingWidgetTest(
      'invalid explicit group amount $invalid never creates preview',
      (tester) async {
        final api = CapacityApi();
        await show(tester, api);
        await base.press(tester, 'Diesen Beleganteil aufteilen');
        await fill(tester, amount: invalid);
        await base.press(tester, 'Belegaufteilung vorschauen');
        expect(api.calls.where((c) => c.path.endsWith('/preview')), isEmpty);
      },
    );
  }
  for (final gate in [
    'feature',
    'offline',
    'project',
    'accounting.read',
    'finance.read',
  ]) {
    base.accountingWidgetTest('$gate prevents capacity route reads', (
      tester,
    ) async {
      final api = CapacityApi();
      if (gate == 'feature') api.reuse = false;
      if (gate.endsWith('.read')) api.rights.remove(gate);
      await show(
        tester,
        api,
        offline: gate == 'offline',
        project: gate == 'project' ? 'f' * 32 : null,
      );
      expect(
        api.calls.where((c) => c.path.contains('/components/v2/')),
        isEmpty,
      );
    });
  }
  for (final gate in [
    'readonly',
    'finance.write',
    'accounting.prepare',
    'disabled',
  ]) {
    base.accountingWidgetTest(
      '$gate keeps both histories readable without new portions',
      (tester) async {
        final api = CapacityApi();
        if (gate == 'readonly') api.readonly = true;
        if (gate == 'disabled') api.enabled = false;
        api.rights.remove(gate);
        final session = await show(tester, api);
        expect(find.text('Bestätigter Geldfluss: 39,67 €'), findsOneWidget);
        expect(
          api.calls.where((c) => c.path.endsWith('/history?limit=50&offset=0')),
          hasLength(2),
        );
        expect(api.calls.where((c) => c.path.contains('/portions')), isEmpty);
        await expectLater(
          session.previewReusableDocumentComponents(eventId, {}),
          throwsA(isA<ApiException>()),
        );
      },
    );
  }
  base.accountingWidgetTest(
    'missing source rights offer only a neutral blocked explanation',
    (tester) async {
      final api = CapacityApi()..hideSources = true;
      await show(tester, api);
      expect(find.text('Diesen Beleganteil aufteilen'), findsNothing);
      expect(
        find.text(
          'Die erforderlichen Quellen sind nicht vollständig freigegeben.',
        ),
        findsWidgets,
      );
      expect(find.textContaining('6,34'), findsNothing);
    },
  );
  base.accountingWidgetTest('receipt before capacity date cannot be selected', (
    tester,
  ) async {
    final api = CapacityApi()..beforeDate = true;
    await show(tester, api);
    expect(find.text('Diesen Beleganteil aufteilen'), findsNothing);
    expect(find.textContaining('frühesten zulässigen Tag'), findsOneWidget);
  });
  base.accountingWidgetTest(
    'lost response reopens neutrally and preserves original ID after generation change',
    (tester) async {
      final api = CapacityApi()..loseCapacity = true;
      final session = await show(tester, api);
      await preview(tester);
      await confirm(tester);
      expect(session.pending(key), true);
      final original = api.capacityRequests.values.single;
      api.generation = 2;
      await session.load();
      await reopen(tester, session);
      expect(find.text('Unbestätigte Belegaufteilung'), findsOneWidget);
      expect(find.byKey(const ValueKey('capacity-accept')), findsNothing);
      expect(find.text('Diesen Beleganteil aufteilen'), findsNothing);
      await base.press(tester, 'Unverändert erneut senden');
      expect(
        api.calls.where((c) => c.path.endsWith('/confirm')).map((c) => c.body),
        [original, original],
      );
      expect(api.capacityEntries, hasLength(1));
      expect(session.pending(key), false);
    },
  );
  base.accountingWidgetTest(
    'old pending is repeated at its stored writer after feature upgrade',
    (tester) async {
      final api = CapacityApi()
        ..legacyOnly = true
        ..lost = true;
      final session = await show(tester, api);
      await preview(tester);
      await base.press(tester, 'Belegaufteilung verbindlich bestätigen');
      final original = api.componentRequests.values.single;
      api.legacyOnly = false;
      api.generation = 2;
      await session.load();
      await reopen(tester, session);
      expect(find.text('Diesen Beleganteil aufteilen'), findsNothing);
      await base.press(tester, 'Unverändert erneut senden');
      expect(
        api.calls.where((c) => c.path.endsWith('/confirm')).map((c) => c.path),
        [
          '/api/business$legacyPath/confirm',
          '/api/business$legacyPath/confirm',
        ],
      );
      expect(
        api.calls.lastWhere((c) => c.path.endsWith('/confirm')).body,
        original,
      );
      expect(api.capacityEntries, isEmpty);
    },
  );
  base.accountingWidgetTest(
    'source denial clears already displayed private capacity details',
    (tester) async {
      final api = CapacityApi();
      await show(tester, api);
      await preview(tester);
      api.sourceDenied = true;
      await tester.tap(find.byTooltip('Belegaufteilung aktualisieren'));
      await tester.pumpAndSettle();
      expect(find.textContaining('6,34'), findsNothing);
      expect(find.textContaining('RE-NEU'), findsNothing);
    },
  );
  base.accountingWidgetTest(
    'late preview after logout cannot restore private capacity details',
    (tester) async {
      final api = CapacityApi();
      final session = await show(tester, api);
      await base.press(tester, 'Diesen Beleganteil aufteilen');
      await fill(tester);
      api.capacityPreviewReply = Completer<void>();
      await tester.ensureVisible(find.text('Belegaufteilung vorschauen'));
      await tester.tap(find.text('Belegaufteilung vorschauen'));
      await tester.pump();
      api.token = null;
      session.revoke();
      api.capacityPreviewReply!.complete();
      await tester.pumpAndSettle();
      expect(find.text('Belegaufteilung prüfen'), findsNothing);
      expect(session.pending(key), false);
    },
  );
  base.accountingWidgetTest(
    'ACK during reopened history refresh discards neutral pending without a second POST',
    (tester) async {
      final api = CapacityApi();
      final session = await show(tester, api);
      await preview(tester);
      await accept(tester);
      api.capacityConfirmReply = Completer<void>();
      await tester.ensureVisible(
        find.text('Belegaufteilung verbindlich bestätigen'),
      );
      await tester.tap(find.text('Belegaufteilung verbindlich bestätigen'));
      await tester.pump();
      expect(session.pending(key), true);
      await tester.pumpWidget(const SizedBox());
      api.capacityHistoryReply = Completer<void>();
      await tester.pumpWidget(
        MaterialApp(
          home: BusinessReusableComponentsPage(
            session: session,
            eventId: eventId,
          ),
        ),
      );
      await tester.pump();
      api.capacityConfirmReply!.complete();
      await tester.pump();
      api.capacityHistoryReply!.complete();
      await tester.pumpAndSettle();
      expect(find.text('Unverändert erneut senden'), findsNothing);
      expect(
        find.text('Aufteilung mit wiederverwendbaren Beträgen Nr. 1'),
        findsOneWidget,
      );
      expect(api.calls.where((c) => c.path.endsWith('/confirm')), hasLength(1));
    },
  );
  for (final accepted in [true, false]) {
    base.accountingWidgetTest(
      'pending conflict resolves only with explicit server absence proof, accepted=$accepted',
      (tester) async {
        final api = CapacityApi()
          ..loseCapacity = accepted
          ..capacityBeforeServer = !accepted;
        final session = await show(tester, api);
        await preview(tester);
        await confirm(tester);
        expect(session.pending(key), true);
        final original = api.calls
            .lastWhere((c) => c.path.endsWith('/confirm'))
            .body;
        api.confirmGateFailure = 409;
        api.confirmationResolution = accepted ? null : 'not_accepted';
        await base.press(tester, 'Unverändert erneut senden');
        if (accepted) {
          expect(session.pending(key), true);
          expect(find.text('Diesen Beleganteil aufteilen'), findsNothing);
          api.confirmGateFailure = null;
          await base.press(tester, 'Unverändert erneut senden');
          expect(api.capacityEntries, hasLength(1));
          expect(
            api.calls
                .where((c) => c.path.endsWith('/confirm'))
                .map((c) => c.body),
            [original, original, original],
          );
        } else {
          expect(session.pending(key), false);
          expect(api.capacityEntries, isEmpty);
          expect(find.text('Diesen Beleganteil aufteilen'), findsOneWidget);
          expect(
            api.calls.where((c) => c.path.endsWith('/confirm')),
            hasLength(2),
          );
        }
      },
    );
  }
  for (final support in [(true, true), (true, false), (false, true)]) {
    base.accountingWidgetTest(
      'later-refund limitation disappears only with complete module and feature $support',
      (tester) async {
        final api = CapacityApi()
          ..refundV2Feature = support.$1
          ..refundV2Module = support.$2;
        await show(tester, api);
        await preview(tester);
        expect(
          find.text(
            'Für die hier neu aufgeteilten Zahlungsanteile ist die Zuordnung späterer Erstattungen noch nicht verfügbar.',
          ),
          support.$1 && support.$2 ? findsNothing : findsOneWidget,
        );
      },
    );
  }
}

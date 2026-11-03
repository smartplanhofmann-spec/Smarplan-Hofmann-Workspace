import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:smartplan_office/api.dart';
import 'package:smartplan_office/business_accounting.dart';
import 'package:smartplan_office/business_accounting_refunds_v2.dart';
import 'package:smartplan_office/business_session.dart';
import 'package:smartplan_office/design.dart';

import 'business_accounting_refunds_test.dart' as old;
import 'business_accounting_test.dart' as base;

const eventId = old.eventId;
const key = 'accounting-refunds-$eventId';
const path = '/accounting/refunds/v2/events/$eventId';
const legacyPath = '/accounting/refunds/events/$eventId';
String get portionId => 'f' * 64;
String get groupId => old.groupId;

class VersionedRefundApi extends old.RefundApi {
  bool versionedFeature = true,
      versionedModule = true,
      legacyOnly = false,
      mixedWriters = false,
      current = false,
      paginated = false,
      versionedLost = false,
      versionedBeforeServer = false,
      originWritable = true;
  int versionedRevision = 0, generation = 1;
  int? confirmGateFailure;
  String? requestResolution;
  Completer<void>? versionedPreviewReply,
      versionedConfirmReply,
      versionedHistoryReply,
      sourceStateReply;
  final versionedEntries = <Map<String, dynamic>>[];
  final versionedRequests = <String, Map<String, dynamic>>{},
      versionedResults = <String, Map<String, dynamic>>{};
  Map<String, dynamic> get newPortion => {
    ...portion,
    'portion_id': portionId,
    'number': 'RE-ERWEITERT',
    'capacity_ownership_id': portion['document_id'],
    'ownership_id': current ? portion['document_id'] : null,
    'writer': 'r2',
    'action': blocked == null
        ? (current ? 'bind_current' : 'takeover_and_bind')
        : null,
    'portion_state_hash': '7' * 64,
  };
  Map<String, dynamic> get legacyChoice => {
    ...portion,
    'number': 'RE-BISHERIG',
    'capacity_ownership_id': null,
    'ownership_id': null,
    'writer': 'r1',
    'action': 'bind_legacy',
  };
  Map<String, dynamic> versionedOrigin(bool reused) => {
    ...origin(reused), 'origin_version': reused ? 'c2' : 'c1',
    // Deliberate identical raw entry/group/sequence identifiers across modules.
    'entry_id': old.firstEntry, 'component_sequence': 11,
    'amount': reused ? '13.22' : '39.67',
    'net': reused ? '11.11' : '33.33',
    'tax': reused ? '2.11' : '6.34',
    'returned_amount': reused ? '0.00' : '13.22',
    'returned_net': reused ? '0.00' : '11.11',
    'returned_tax': reused ? '0.00' : '2.11',
    'remaining_amount': reused ? '13.22' : '26.45',
    'remaining_net': reused ? '11.11' : '22.22',
    'remaining_tax': reused ? '2.11' : '4.23',
  };
  Map<String, dynamic> get versionedState => {
    ...state,
    'revision': versionedRevision,
    'state_hash': '8' * 64,
    'source_hash': '9' * 64,
    'amount': mixedWriters ? '52.88' : '26.44',
    'origin_documented_amount': old.money(
      (revision + versionedRevision) * 2644,
    ),
    'origin_unresolved_amount': old.money(
      ((mixedWriters ? 2 : 1) - revision - versionedRevision) * 2644,
    ),
    'eligible':
        blocked == null &&
        (versionedRevision == 0 || (mixedWriters && revision == 0)),
    'blocked_reason':
        blocked ?? (versionedRevision > 0 ? 'fully_documented' : null),
  };
  @override
  Future<dynamic> call(String routePath, [Map<String, dynamic>? body]) async {
    final route = routePath.split('?').first;
    if (route == '/api/business/capabilities') {
      final value = base.copy(
        await super.call(routePath, body) as Map<String, dynamic>,
      );
      value['generation'] = generation;
      if (versionedFeature)
        (value['features'] as List).add('accounting_refund_origins_v2');
      if (versionedModule)
        (value['capabilities'] as List).add('business_accounting_refunds_v2');
      (value['features'] as List).add('accounting_document_component_reuse');
      (value['capabilities'] as List).add('business_accounting_capacity');
      return value;
    }
    if (route ==
            '/api/business/accounting/components/v2/events/${old.firstEvent}' ||
        route ==
            '/api/business/accounting/components/v2/events/${old.secondEvent}') {
      calls.add((path: routePath, body: body));
      if (sourceStateReply != null) await sourceStateReply!.future;
      if (route.endsWith('/$deniedOrigin'))
        throw const ApiException(
          403,
          'Gesamte historische Ursprungshülle nicht freigegeben',
        );
      return {
        'writes_allowed': originWritable,
        'eligible': false,
        'blocked_reason': 'fully_documented',
      };
    }
    if (!route.startsWith('/api/business$path'))
      return super.call(routePath, body);
    calls.add((path: routePath, body: body == null ? null : base.copy(body)));
    if (sourceDenied)
      throw const ApiException(
        403,
        'Gesamte Erstattungshülle nicht freigegeben',
      );
    if (body == null) {
      if (route.endsWith('/history')) {
        if (versionedHistoryReply != null) await versionedHistoryReply!.future;
        return list(versionedEntries);
      }
      if (route.endsWith('/portions'))
        return list([
          if ((legacyOnly || mixedWriters) && revision == 0) legacyChoice,
          if (!legacyOnly && versionedRevision == 0) newPortion,
        ]);
      if (route.endsWith('/origins')) {
        final more = Uri.parse(routePath).queryParameters['offset'] != '0';
        return list([
          if (!paginated || !more) versionedOrigin(false),
          if (!paginated || more) versionedOrigin(true),
        ], next: paginated && !more ? 50 : null);
      }
      return versionedState;
    }
    if (route.endsWith('/preview')) {
      expect(body.containsKey('request_id'), false);
      expect(body['state_hash'], versionedState['state_hash']);
      final lines = <Map<String, dynamic>>[];
      for (final selected in body['origins'] as List) {
        final reused = selected['origin_version'] == 'c2';
        expect(selected['entry_id'], old.firstEntry);
        expect(selected['group_id'], groupId);
        expect(selected['amount'], '13.22');
        final source = versionedOrigin(reused);
        lines.add({
          'origin_version': selected['origin_version'],
          'entry_id': selected['entry_id'],
          'group_id': groupId,
          'origin_event_id': source['origin_event_id'],
          'component_sequence': 11,
          'rate': '19',
          'category': 'S',
          'tax_reason': null,
          'origin_cash_date': source['cash_date'],
          'origin_evidence_reference': source['evidence_reference'],
          'origin_reference': source['reference'],
          'lot_state_hash': source['lot_state_hash'],
          'amount': '13.22',
          'net': reused ? '11.11' : '11.10',
          'tax': reused ? '2.11' : '2.12',
          'gross_before': source['returned_amount'],
          'net_before': source['returned_net'],
          'tax_before': source['returned_tax'],
          'gross_after': reused ? '13.22' : '26.44',
          'net_after': reused ? '11.11' : '22.21',
          'tax_after': reused ? '2.11' : '4.23',
          'remaining_gross': reused ? '0.00' : '13.23',
          'remaining_net': reused ? '0.00' : '11.12',
          'remaining_tax': reused ? '0.00' : '2.11',
        });
      }
      final result = <String, dynamic>{
        'event_id': eventId,
        'source_hash': body['source_hash'],
        'expected_revision': body['expected_revision'],
        'state_hash': body['state_hash'],
        'action': body['action'],
        'cash_date': '2026-11-03',
        'evidence_reference': 'REFUND-EVIDENCE',
        'reference': 'Bestätigte Erstattung',
        'portion': newPortion,
        'amount': '26.44',
        'net': '22.21',
        'tax': '4.23',
        'lines': lines,
        'reason': body['reason'],
        'preview_hash': 'a' * 64,
        'capacity_released': false,
        'scope': 'authorized_sources',
        'tax_status': 'unconfigured',
        'tax_result_available': false,
      };
      versionedResults['preview'] = base.copy(result);
      if (versionedPreviewReply != null) await versionedPreviewReply!.future;
      return result;
    }
    if (versionedBeforeServer) {
      versionedBeforeServer = false;
      throw const ApiException(0, 'Synthetisch vor Annahme unterbrochen');
    }
    if (confirmGateFailure != null)
      throw ApiException(
        confirmGateFailure!,
        'Synthetische Freigabeprüfung',
        requestResolution: requestResolution,
      );
    final id = body['request_id'] as String;
    if (versionedRequests.containsKey(id)) {
      expect(body, versionedRequests[id]);
      return base.copy(versionedResults[id]!);
    }
    final result =
        <String, dynamic>{
            ...versionedResults['preview']!,
            'id': 'b' * 32,
            'sequence': 1,
            'revision': ++versionedRevision,
            'previous_state_hash': body['state_hash'],
            'created_by': 'synthetic',
            'created_at': '2026-11-03T12:00:00Z',
          }
          ..remove('expected_revision')
          ..remove('state_hash');
    versionedEntries.add(base.copy(result));
    versionedRequests[id] = base.copy(body);
    versionedResults[id] = base.copy(result);
    if (versionedConfirmReply != null) await versionedConfirmReply!.future;
    if (versionedLost) {
      versionedLost = false;
      throw const ApiException(0, 'Synthetisch verlorene Antwort');
    }
    return result;
  }
}

void main() {
  Future<BusinessSession> show(
    WidgetTester tester,
    VersionedRefundApi api, {
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
        'amount': '26.44',
        'cash_date': '2026-11-03',
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
            : BusinessVersionedRefundOriginsPage(
                session: session,
                eventId: eventId,
              ),
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
        home: BusinessVersionedRefundOriginsPage(
          session: session,
          eventId: eventId,
        ),
      ),
    );
    await tester.pumpAndSettle();
  }

  Finder originField(String version, String entry) =>
      find.byKey(ValueKey('refund-v2-origin-$version:$entry:$groupId'));
  Future<void> value(
    WidgetTester tester,
    String version,
    String entry,
    String amount,
  ) async {
    final field = originField(version, entry);
    await tester.ensureVisible(field);
    await tester.pumpAndSettle();
    await tester.enterText(field, amount);
    await tester.pumpAndSettle();
  }

  Future<void> explanation(WidgetTester tester) async {
    final field = find.byKey(const ValueKey('refund-v2-reason'));
    await tester.ensureVisible(field);
    await tester.enterText(field, 'Synthetisch geprüfte gemischte Herkunft');
    await tester.pumpAndSettle();
  }

  Future<void> fill(
    WidgetTester tester, {
    bool legacy = false,
    bool pages = false,
  }) async {
    await value(tester, 'c1', old.firstEntry, '13,22');
    if (pages) await base.press(tester, 'Weitere Ursprünge laden');
    await value(
      tester,
      legacy ? 'c1' : 'c2',
      legacy ? old.secondEntry : old.firstEntry,
      '13,22',
    );
    await explanation(tester);
  }

  Future<void> preview(
    WidgetTester tester, {
    bool legacy = false,
    bool pages = false,
  }) async {
    await base.press(tester, 'Ursprünge für diesen Anteil wählen');
    await fill(tester, legacy: legacy, pages: pages);
    await base.press(tester, 'Erstattungsursprung vorschauen');
  }

  Future<void> accept(WidgetTester tester) async {
    final control = find.byKey(const ValueKey('refund-v2-handoff'));
    if (control.evaluate().isNotEmpty) {
      await tester.ensureVisible(control);
      await tester.pumpAndSettle();
      await tester.tap(control);
      await tester.pumpAndSettle();
    }
  }

  Future<void> confirm(WidgetTester tester) async {
    await accept(tester);
    await base.press(tester, 'Erstattungsursprung verbindlich bestätigen');
  }

  for (final width in [390.0, 1200.0]) {
    base.accountingWidgetTest(
      'whole mixed refund distinguishes colliding versioned lots and exact cumulative cents at $width',
      (tester) async {
        final api = VersionedRefundApi();
        await show(tester, api, width: width);
        await base.press(tester, 'Ursprünge für diesen Anteil wählen');
        expect(
          tester
              .widget<TextField>(originField('c1', old.firstEntry))
              .controller!
              .text,
          isEmpty,
        );
        expect(
          tester
              .widget<TextField>(originField('c2', old.firstEntry))
              .controller!
              .text,
          isEmpty,
        );
        await fill(tester);
        await base.press(tester, 'Erstattungsursprung vorschauen');
        expect(api.versionedEntries, isEmpty);
        expect(find.text('Ursprüngliche Aufteilung Nr. 11'), findsOneWidget);
        expect(
          find.text('Aufteilung nach Wiederverwendung Nr. 11'),
          findsOneWidget,
        );
        expect(
          find.text(
            'Dokumentierte Rücknahme: netto 22,21 € · ausgewiesene Steuer 4,23 € · brutto 26,44 €',
          ),
          findsOneWidget,
        );
        expect(
          find.text(
            'Zuvor zurückgenommen: netto 11,11 € · ausgewiesene Steuer 2,11 € · brutto 13,22 €',
          ),
          findsOneWidget,
        );
        expect(
          tester
              .widget<FilledButton>(
                find.widgetWithText(
                  FilledButton,
                  'Erstattungsursprung verbindlich bestätigen',
                ),
              )
              .onPressed,
          isNull,
        );
        final sent = api.calls
            .lastWhere((c) => c.path.endsWith('/preview'))
            .body!;
        expect((sent['origins'] as List).map((o) => o['origin_version']), [
          'c1',
          'c2',
        ]);
        expect((sent['origins'] as List).map((o) => o['entry_id']), [
          old.firstEntry,
          old.firstEntry,
        ]);
        await confirm(tester);
        expect(api.versionedEntries, hasLength(1));
        expect(find.text('Erweiterte Ursprungsbindung Nr. 1'), findsOneWidget);
        expect(tester.takeException(), isNull);
      },
    );
  }
  for (final gate in [
    'feature',
    'module',
    'offline',
    'project',
    'accounting.read',
    'finance.read',
  ]) {
    base.accountingWidgetTest('$gate prevents versioned refund reads', (
      tester,
    ) async {
      final api = VersionedRefundApi();
      if (gate == 'feature') api.versionedFeature = false;
      if (gate == 'module') api.versionedModule = false;
      api.rights.remove(gate);
      await show(
        tester,
        api,
        offline: gate == 'offline',
        project: gate == 'project' ? 'c' * 32 : null,
      );
      expect(api.calls.where((c) => c.path.contains('/refunds/v2/')), isEmpty);
    });
  }
  for (final gate in [
    'readonly',
    'disabled',
    'accounting.prepare',
    'finance.write',
  ]) {
    base.accountingWidgetTest(
      '$gate retains both histories without candidates or preview',
      (tester) async {
        final api = VersionedRefundApi();
        if (gate == 'readonly') api.readonly = true;
        if (gate == 'disabled') api.enabled = false;
        api.rights.remove(gate);
        final session = await show(tester, api);
        expect(find.text('Bestätigter Geldfluss: 26,44 €'), findsOneWidget);
        expect(
          api.calls.where((c) => c.path.contains('/history?')),
          hasLength(2),
        );
        expect(
          api.calls.where(
            (c) => c.path.contains('/portions') || c.path.contains('/origins'),
          ),
          isEmpty,
        );
        await expectLater(
          session.previewVersionedRefundOrigins(eventId, {}),
          throwsA(isA<ApiException>()),
        );
      },
    );
  }
  for (final enabled in [true, false]) {
    base.accountingWidgetTest(
      'entry chooses supported refund writer, new feature=$enabled',
      (tester) async {
        final api = VersionedRefundApi()..versionedFeature = enabled;
        await show(tester, api, entry: true);
        await base.press(tester, 'Geldfluss ansehen');
        await base.press(tester, 'Erstattungsursprünge ansehen');
        expect(api.calls.any((c) => c.path.contains('/refunds/v2/')), enabled);
        expect(find.text('Ursprünge für diesen Anteil wählen'), findsOneWidget);
      },
    );
  }
  base.accountingWidgetTest(
    'paging retains distinct versions and rechecks previously displayed sources without current eligibility',
    (tester) async {
      final api = VersionedRefundApi()..paginated = true;
      await show(tester, api);
      await preview(tester, pages: true);
      expect(
        api.calls
            .where(
              (c) =>
                  c.path ==
                  '/api/business/accounting/components/v2/events/${old.firstEvent}',
            )
            .length,
        greaterThan(1),
      );
      expect(
        api.calls.where(
          (c) =>
              c.path ==
              '/api/business/accounting/components/v2/events/${old.secondEvent}',
        ),
        isNotEmpty,
      );
      await confirm(tester);
      expect(
        api.versionedRequests.values.single['origins'],
        api.calls
            .firstWhere((c) => c.path.endsWith('/preview'))
            .body!['origins'],
      );
    },
  );
  base.accountingWidgetTest(
    'revoked carried source of an earlier page is hidden before loading more origins',
    (tester) async {
      final api = VersionedRefundApi()..paginated = true;
      await show(tester, api);
      await base.press(tester, 'Ursprünge für diesen Anteil wählen');
      await value(tester, 'c1', old.firstEntry, '13,22');
      api.deniedOrigin = old.firstEvent;
      await base.press(tester, 'Weitere Ursprünge laden');
      expect(find.textContaining('ORIGIN-FIRST'), findsNothing);
      expect(find.byType(TextField), findsNothing);
      expect(
        api.calls.where((c) => c.path.contains('/origins?')),
        hasLength(1),
      );
    },
  );
  base.accountingWidgetTest(
    'editing preview reauthorizes cached origin closure before redisplay',
    (tester) async {
      final api = VersionedRefundApi();
      await show(tester, api);
      await preview(tester);
      api.deniedOrigin = old.secondEvent;
      await base.press(tester, 'Ursprungsbeträge ändern');
      expect(find.textContaining('ORIGIN-FIRST'), findsNothing);
      expect(find.textContaining('ORIGIN-SECOND'), findsNothing);
      expect(
        find.text('Erstattungsursprünge nicht freigegeben'),
        findsOneWidget,
      );
    },
  );
  for (final invalid in ['', '-1', '13.221', '13.21', '40.00']) {
    base.accountingWidgetTest(
      'invalid origin amount $invalid cannot preview a partial mixed portion',
      (tester) async {
        final api = VersionedRefundApi();
        await show(tester, api);
        await base.press(tester, 'Ursprünge für diesen Anteil wählen');
        await value(tester, 'c1', old.firstEntry, invalid);
        await value(tester, 'c2', old.firstEntry, '13,22');
        await explanation(tester);
        await base.press(tester, 'Erstattungsursprung vorschauen');
        expect(api.calls.where((c) => c.path.endsWith('/preview')), isEmpty);
      },
    );
  }
  base.accountingWidgetTest(
    'legacy binding uses original R1 state and never sends version or action fields',
    (tester) async {
      final api = VersionedRefundApi()..legacyOnly = true;
      await show(tester, api);
      await preview(tester, legacy: true);
      final request = api.calls.lastWhere((c) => c.path.endsWith('/preview'));
      expect(request.path, '/api/business$legacyPath/preview');
      expect(request.body!['state_hash'], api.state['state_hash']);
      expect(request.body!.containsKey('action'), false);
      expect(
        (request.body!['origins'] as List).every(
          (o) => !(o as Map).containsKey('origin_version'),
        ),
        true,
      );
      await confirm(tester);
      expect(api.entries, hasLength(1));
      expect(api.versionedEntries, isEmpty);
      expect(find.text('Frühere Ursprungsbindung Nr. 1'), findsOneWidget);
    },
  );
  base.accountingWidgetTest(
    'mixed event binds each whole invoice portion with its offered writer',
    (tester) async {
      final api = VersionedRefundApi()..mixedWriters = true;
      await show(tester, api);
      final legacyCard = find.ancestor(
        of: find.text('RE-BISHERIG · Synthetischer Kunde'),
        matching: find.byType(Card),
      );
      final button = find.descendant(
        of: legacyCard,
        matching: find.text('Ursprünge für diesen Anteil wählen'),
      );
      await tester.ensureVisible(button);
      await tester.pumpAndSettle();
      await tester.tap(button);
      await tester.pumpAndSettle();
      await fill(tester, legacy: true);
      await base.press(tester, 'Erstattungsursprung vorschauen');
      await confirm(tester);
      await preview(tester);
      await confirm(tester);
      expect(api.entries, hasLength(1));
      expect(api.versionedEntries, hasLength(1));
      expect(
        api.calls.where((c) => c.path.endsWith('/confirm')).map((c) => c.path),
        ['/api/business$legacyPath/confirm', '/api/business$path/confirm'],
      );
    },
  );
  base.accountingWidgetTest(
    'current binding needs separate confirmation without repeating invoice handoff',
    (tester) async {
      final api = VersionedRefundApi()..current = true;
      await show(tester, api);
      await preview(tester);
      expect(find.byKey(const ValueKey('refund-v2-handoff')), findsNothing);
      await confirm(tester);
      expect(api.versionedRequests.values.single['action'], 'bind_current');
    },
  );
  base.accountingWidgetTest(
    'lost acknowledgement stays neutral and resumes unchanged after generation and lot exhaustion',
    (tester) async {
      final api = VersionedRefundApi()..versionedLost = true;
      final session = await show(tester, api);
      await preview(tester);
      await confirm(tester);
      expect(session.pending(key), true);
      final original = api.versionedRequests.values.single;
      api.generation = 2;
      await session.load();
      await reopen(tester, session);
      expect(find.text('Unbestätigte Ursprungsbindung'), findsOneWidget);
      expect(find.text('Erstattungsursprung prüfen'), findsNothing);
      expect(find.text('Ursprünge für diesen Anteil wählen'), findsNothing);
      await base.press(tester, 'Unverändert erneut senden');
      expect(
        api.calls.where((c) => c.path.endsWith('/confirm')).map((c) => c.body),
        [original, original],
      );
      expect(api.versionedEntries, hasLength(1));
      expect(session.pending(key), false);
    },
  );
  base.accountingWidgetTest(
    'accepted old pending keeps original R1 path after invoice writer changes',
    (tester) async {
      final api = VersionedRefundApi()
        ..legacyOnly = true
        ..lost = true;
      final session = await show(tester, api);
      await preview(tester, legacy: true);
      await confirm(tester);
      final original = api.refundRequests.values.single;
      api.legacyOnly = false;
      api.generation = 2;
      await session.load();
      await reopen(tester, session);
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
      expect(api.versionedEntries, isEmpty);
    },
  );
  for (final accepted in [true, false]) {
    base.accountingWidgetTest(
      'only marked absence resolves pending conflict, accepted=$accepted',
      (tester) async {
        final api = VersionedRefundApi()
          ..versionedLost = accepted
          ..versionedBeforeServer = !accepted;
        final session = await show(tester, api);
        await preview(tester);
        await confirm(tester);
        final original = api.calls
            .lastWhere((c) => c.path.endsWith('/confirm'))
            .body;
        api.confirmGateFailure = 409;
        api.requestResolution = accepted ? null : 'not_accepted';
        await base.press(tester, 'Unverändert erneut senden');
        expect(session.pending(key), accepted);
        if (accepted) {
          expect(find.text('Ursprünge für diesen Anteil wählen'), findsNothing);
          api.confirmGateFailure = null;
          await base.press(tester, 'Unverändert erneut senden');
          expect(
            api.calls
                .where((c) => c.path.endsWith('/confirm'))
                .map((c) => c.body),
            [original, original, original],
          );
          expect(api.versionedEntries, hasLength(1));
        } else {
          expect(api.versionedEntries, isEmpty);
          expect(
            find.text('Ursprünge für diesen Anteil wählen'),
            findsOneWidget,
          );
        }
      },
    );
  }
  base.accountingWidgetTest(
    'late preview after logout cannot restore origin details',
    (tester) async {
      final api = VersionedRefundApi();
      final session = await show(tester, api);
      await base.press(tester, 'Ursprünge für diesen Anteil wählen');
      await fill(tester);
      api.versionedPreviewReply = Completer<void>();
      await tester.ensureVisible(find.text('Erstattungsursprung vorschauen'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Erstattungsursprung vorschauen'));
      await tester.pump();
      api.token = null;
      session.revoke();
      api.versionedPreviewReply!.complete();
      await tester.pumpAndSettle();
      expect(find.textContaining('ORIGIN-FIRST'), findsNothing);
      expect(find.text('Erstattungsursprung prüfen'), findsNothing);
      expect(session.pending(key), false);
    },
  );
  base.accountingWidgetTest(
    'late ACK during reopened history cannot create a new refund command',
    (tester) async {
      final api = VersionedRefundApi();
      final session = await show(tester, api);
      await preview(tester);
      await accept(tester);
      api.versionedConfirmReply = Completer<void>();
      await tester.ensureVisible(
        find.text('Erstattungsursprung verbindlich bestätigen'),
      );
      await tester.pumpAndSettle();
      await tester.tap(find.text('Erstattungsursprung verbindlich bestätigen'));
      await tester.pump();
      expect(session.pending(key), true);
      await tester.pumpWidget(const SizedBox());
      api.versionedHistoryReply = Completer<void>();
      await tester.pumpWidget(
        MaterialApp(
          home: BusinessVersionedRefundOriginsPage(
            session: session,
            eventId: eventId,
          ),
        ),
      );
      await tester.pump();
      api.versionedConfirmReply!.complete();
      await tester.pump();
      api.versionedHistoryReply!.complete();
      await tester.pumpAndSettle();
      expect(find.text('Unverändert erneut senden'), findsNothing);
      expect(find.text('Erweiterte Ursprungsbindung Nr. 1'), findsOneWidget);
      expect(api.calls.where((c) => c.path.endsWith('/confirm')), hasLength(1));
    },
  );
  base.accountingWidgetTest(
    'current origin write denial removes the reviewed proposal before confirmation',
    (tester) async {
      final api = VersionedRefundApi();
      await show(tester, api);
      await preview(tester);
      api.originWritable = false;
      await confirm(tester);
      expect(api.calls.where((c) => c.path.endsWith('/confirm')), isEmpty);
      expect(find.textContaining('ORIGIN-FIRST'), findsNothing);
      expect(
        find.text('Erstattungsursprünge nicht freigegeben'),
        findsOneWidget,
      );
    },
  );
  base.accountingWidgetTest(
    'unresolved original customer leaves the entire refund portion blocked',
    (tester) async {
      final api = VersionedRefundApi()..blocked = 'source_customer_unresolved';
      await show(tester, api);
      expect(find.text('Ursprünge für diesen Anteil wählen'), findsNothing);
      expect(api.calls.where((c) => c.path.contains('/origins?')), isEmpty);
      expect(find.text('Bestätigter Geldfluss: 26,44 €'), findsOneWidget);
    },
  );
}

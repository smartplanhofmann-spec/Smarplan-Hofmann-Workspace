import 'dart:async';
import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:smartplan_office/api.dart';
import 'package:smartplan_office/business_operations.dart';
import 'package:smartplan_office/business_purchasing.dart';
import 'package:smartplan_office/business_session.dart';
import 'package:smartplan_office/design.dart';

const orderId = 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa';
const articleId = 'bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb';
const locationId = 'cccccccccccccccccccccccccccccccc';
const projectId = 'dddddddddddddddddddddddddddddddd';
Map<String, dynamic> clone(Map<String, dynamic> value) =>
    jsonDecode(jsonEncode(value)) as Map<String, dynamic>;
int units(String value) {
  final parts = value.split('.');
  return int.parse(parts[0]) * 10000 +
      int.parse((parts.length == 1 ? '' : parts[1]).padRight(4, '0'));
}

String quantity(int value) =>
    '${value ~/ 10000}.${(value % 10000).toString().padLeft(4, '0')}';

class PurchasingApi extends OfficeApi {
  PurchasingApi({String? status = 'approved'}) : super(apiVersion: 'v1') {
    token = 'synthetic-purchasing-session';
    if (status != null) {
      order = {
        'id': orderId,
        'project_id': projectId,
        'supplier_name': 'Synthetischer Lieferant',
        'source_revision': 3,
        'receipt_revision': 0,
        'status': status,
        'delivery_status': 'not_sent',
        'confirmation': status == 'ordered'
            ? {
                'order_reference': 'PO-SYNTH-1',
                'ordered_on': '2026-11-02',
                'confirmed_by': 'owner',
                'confirmed_at': '2026-11-02T10:00:00Z',
              }
            : null,
        'items': [
          for (var index = 0; index < 2; index++)
            {
              'line_index': index,
              'article_id': articleId,
              'article_name': 'Synthetisches Kabel',
              'article_code': 'TEST-CABLE',
              'unit': 'm',
              'ordered_quantity': index == 0 ? '5.0000' : '10.0000',
              'received_quantity': '0.0000',
              'remaining_quantity': index == 0 ? '5.0000' : '10.0000',
            },
        ],
      };
    }
  }
  Map<String, dynamic>? order;
  Set<String>? scopedPermissions;
  bool catalog = false, deniedCatalog = false;
  List<Map<String, dynamic>> catalogRows = [
    {
      'id': articleId,
      'revision': 1,
      'code': 'TEST-CABLE',
      'name': 'Synthetisches Kabel',
      'kind': 'material',
      'unit': 'm',
      'active': true,
      'cost_price_net': '99.8765',
    },
  ];
  bool lostProposalAck = false;
  bool deniedDetail = false;
  Completer<void>? proposalReply;
  void switchUser() {
    token = 'other-synthetic-user';
    notifyListeners();
  }

  final receipts = <Map<String, dynamic>>[];
  final saved = <String, Map<String, dynamic>>{};
  final calls = <({String path, Map<String, dynamic>? body})>[];
  bool financeRead = true,
      financeWrite = true,
      approve = true,
      inventoryWrite = true;
  bool active = true,
      feature = true,
      lostReceiptAck = false,
      pauseReceipt = false;

  @override
  Future<dynamic> call(String path, [Map<String, dynamic>? body]) async {
    calls.add((path: path, body: body == null ? null : clone(body)));
    final route = path.split('?').first;
    final scoped = Uri.parse(path).queryParameters['project_id'] == projectId;
    final effectivePermissions = scoped ? scopedPermissions : null;
    if (route == '/api/business/capabilities')
      return {
        'storage_version': 7,
        'compatibility_mode': 'business',
        'readonly': false,
        'generation': 1,
        'capabilities': [
          'business_foundation',
          'business_inventory',
          'business_documents',
          'business_purchasing',
        ],
        'features': [
          'organization_modules',
          if (feature) 'purchasing_receipts',
          if (catalog) 'purchasing_catalog',
        ],
        'permissions':
            effectivePermissions?.toList() ??
            [
              'inventory.read',
              if (inventoryWrite) 'inventory.write',
              if (financeRead) 'finance.read',
              if (financeWrite) 'finance.write',
              if (approve) 'finance.approve',
            ],
        'organization': {
          'revision': 1,
          'configured': true,
          'modules': {
            for (final key in BusinessSession.organizationSections)
              key: {
                'visible': true,
                'enabled': key == 'material' ? active : true,
              },
          },
        },
      };
    if (route == '/api/business/purchasing/articles') {
      if (!catalog) throw const ApiException(404, 'Katalog nicht unterstützt');
      if (deniedCatalog ||
          (scoped &&
              scopedPermissions != null &&
              !scopedPermissions!.contains('inventory.read'))) {
        throw const ApiException(
          403,
          'Projektbezogene Artikelauswahl gesperrt',
        );
      }
      final query = Uri.parse(path).queryParameters;
      final search = (query['query'] ?? '').toLowerCase();
      final offset = int.parse(query['offset'] ?? '0');
      final limit = int.parse(query['limit'] ?? '100');
      final filtered = catalogRows
          .where(
            (item) => '${item['code']} ${item['name']}'.toLowerCase().contains(
              search,
            ),
          )
          .toList();
      final items = filtered.skip(offset).take(limit).map(clone).toList();
      return {
        'items': items,
        'total': filtered.length,
        'next_offset': offset + items.length < filtered.length
            ? offset + items.length
            : null,
      };
    }
    if (route == '/api/business/articles')
      return {
        'items': [
          {
            'id': articleId,
            'name': 'Synthetisches Kabel',
            'code': 'TEST-CABLE',
            'kind': 'material',
            'active': true,
            'unit': 'm',
            'cost_price_net': '99.8765',
          },
        ],
      };
    if (route == '/api/business/inventory/locations')
      return {
        'items': [
          {'id': locationId, 'name': 'Testlager', 'active': true},
        ],
      };
    if (route == '/api/business/inventory/orders' ||
        route == '/api/business/inventory/orders/$orderId') {
      if (body == null)
        return {
          'items': order == null ? [] : [clone(order!)],
        };
      final previous = saved[body['request_id']];
      if (previous != null) return clone(previous);
      final next = (order?['source_revision'] as int? ?? 0) + 1;
      order = {
        'id': orderId,
        'project_id': body['project_id'],
        'supplier_name': body['supplier_name'],
        'source_revision': next,
        'receipt_revision': 0,
        'confirmation': null,
        'delivery_status': 'not_sent',
        'status': body['status'] == 'approved' ? 'approved' : 'proposal',
        'items': [
          for (var i = 0; i < (body['items'] as List).length; i++)
            {
              'line_index': i,
              'article_id': body['items'][i]['article_id'],
              'article_name': 'Synthetisches Kabel',
              'article_code': 'TEST-CABLE',
              'unit': 'm',
              'ordered_quantity': quantity(units(body['items'][i]['quantity'])),
              'received_quantity': '0.0000',
              'remaining_quantity': quantity(
                units(body['items'][i]['quantity']),
              ),
            },
        ],
      };
      final result = saved[body['request_id']] = {
        'id': orderId,
        'revision': next,
      };
      if (lostProposalAck) {
        lostProposalAck = false;
        await proposalReply?.future;
        throw const ApiException(0, 'Synthetische Erfolgsantwort verloren');
      }
      return result;
    }
    if (route == '/api/business/purchasing/orders')
      return {
        'items': order == null ? [] : [clone(order!)],
      };
    if (route == '/api/business/purchasing/orders/$orderId') {
      if (deniedDetail)
        throw const ApiException(403, 'Projektzugriff entzogen');
      return clone(order!);
    }
    if (route == '/api/business/purchasing/orders/$orderId/confirm') {
      expect(body!['confirmation'], true);
      expect(body['source_revision'], order!['source_revision']);
      expect(body['expected_receipt_revision'], 0);
      order!['confirmation'] = {
        'order_reference': body['order_reference'],
        'ordered_on': body['ordered_on'],
      };
      order!['status'] = 'ordered';
      order!['receipt_revision'] = 0;
      return clone(order!);
    }
    if (route == '/api/business/purchasing/orders/$orderId/receipts') {
      if (body == null) return {'items': receipts.map(clone).toList()};
      if (pauseReceipt) {
        pauseReceipt = false;
        throw const ApiException(423, 'Material wurde vorübergehend pausiert');
      }
      final previous = saved[body['request_id']];
      if (previous != null) return clone(previous);
      expect(body['source_revision'], order!['source_revision']);
      expect(body['expected_receipt_revision'], order!['receipt_revision']);
      order!['receipt_revision'] = (order!['receipt_revision'] as int) + 1;
      final result = <String, dynamic>{
        'id': 'receipt-${receipts.length}',
        'order_id': orderId,
        'project_id': projectId,
        'source_revision': order!['source_revision'],
        'receipt_revision': order!['receipt_revision'],
        'receipt_reference': body['receipt_reference'],
        'received_on': body['received_on'],
        'location_id': body['location_id'],
        'created_at': '2026-11-02T12:00:00Z',
        'created_by': 'owner',
        'lines': <Map<String, dynamic>>[],
      };
      for (final item in body['lines']) {
        final source = order!['items'][item['line_index']];
        final received =
            units(source['received_quantity']) + units(item['quantity']);
        source['received_quantity'] = quantity(received);
        source['remaining_quantity'] = quantity(
          units(source['ordered_quantity']) - received,
        );
        (result['lines'] as List).add({
          'line_index': item['line_index'],
          'article_id': articleId,
          'article_name': source['article_name'],
          'unit': 'm',
          'quantity': item['quantity'],
          'unit_cost_net': item['unit_cost_net'],
          'cost_net': '777.77',
          'movement_id': 'movement-${receipts.length}-${item['line_index']}',
        });
      }
      order!['status'] =
          (order!['items'] as List).every(
            (line) => units(line['remaining_quantity']) == 0,
          )
          ? 'received'
          : 'partially_received';
      receipts.add(clone(result));
      saved[body['request_id']] = clone(result);
      if (lostReceiptAck) {
        lostReceiptAck = false;
        throw const ApiException(0, 'Erfolgsantwort verloren');
      }
      return result;
    }
    return {'items': []};
  }
}

Finder textField(String name) => find.byKey(ValueKey('business-field-$name'));
Finder choice(String label) => find.byWidgetPredicate(
  (widget) =>
      widget is DropdownButtonFormField<String> &&
      widget.decoration.labelText == label,
);

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  setUpAll(() async {
    await (FontLoader(
      'Inter',
    )..addFont(rootBundle.load('assets/fonts/Inter.ttf'))).load();
  });
  Future<BusinessSession> show(
    WidgetTester tester,
    PurchasingApi api, {
    double width = 1200,
    bool materialEntry = false,
    bool global = false,
  }) async {
    tester.view.physicalSize = Size(width, 1000);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    final session = BusinessSession(
      api: api,
      projectId: global ? null : projectId,
      projects: [
        {'id': projectId, 'name': 'Synthetisches Projekt'},
      ],
    );
    await session.load();
    await tester.pumpWidget(
      MaterialApp(
        theme: officeTheme(),
        home: Scaffold(
          body: materialEntry
              ? BusinessAreaPage(session: session, area: 'material')
              : BusinessPurchasingPage(session: session),
        ),
      ),
    );
    await tester.pumpAndSettle();
    return session;
  }

  Future<void> close(
    WidgetTester tester,
    BusinessSession session,
    PurchasingApi api,
  ) async {
    await tester.pumpWidget(const SizedBox());
    session.dispose();
    api.dispose();
  }

  Future<void> tap(WidgetTester tester, Finder target) async {
    await tester.ensureVisible(target);
    await tester.pumpAndSettle();
    await tester.tap(target);
    await tester.pumpAndSettle();
  }

  Future<void> type(WidgetTester tester, String name, String value) async {
    await tester.ensureVisible(textField(name));
    await tester.enterText(textField(name), value);
    await tester.pumpAndSettle();
  }

  Future<void> select(WidgetTester tester, String label, String value) async {
    await tap(tester, choice(label));
    await tap(tester, find.text(value).last);
  }

  Future<void> receipt(
    WidgetTester tester,
    String reference,
    Map<int, String> quantities,
  ) async {
    await tap(tester, find.text('Wareneingang buchen'));
    await type(tester, 'receipt_reference', reference);
    await select(tester, 'Ziellager', 'Testlager');
    for (final entry in quantities.entries) {
      await type(tester, 'quantity_${entry.key}', entry.value);
      await type(tester, 'cost_${entry.key}', '3,50');
    }
    await tap(tester, find.text('Wareneingang verbindlich buchen'));
  }

  for (final width in [390.0, 1200.0]) {
    testWidgets(
      'Explicit order confirmation and position-bound partial/final receipts at width $width',
      (tester) async {
        final api = PurchasingApi()..lostReceiptAck = true;
        final session = await show(tester, api, width: width);
        try {
          await tap(tester, find.text('Synthetischer Lieferant'));
          expect(find.text('Wareneingang buchen'), findsNothing);
          await tap(tester, find.text('Externe Bestellung dokumentieren'));
          await type(tester, 'order_reference', 'PO-SYNTH-1');
          await tap(
            tester,
            find.text(
              'Die Bestellung wurde außerhalb dieser Anwendung ausgelöst',
            ),
          );
          await tap(tester, find.text('Bestellung dokumentieren'));
          expect(api.order!['status'], 'ordered');
          await receipt(tester, 'LIEF-TEIL', {1: '2,125'});
          expect(api.receipts, hasLength(1));
          final initial = api.calls
              .lastWhere(
                (call) => call.body != null && call.path.endsWith('/receipts'),
              )
              .body!;
          expect(initial['source_revision'], 3);
          expect(initial['expected_receipt_revision'], 0);
          expect(initial['lines'], [
            {'line_index': 1, 'quantity': '2.125', 'unit_cost_net': '3.50'},
          ]);
          await tap(tester, find.text('Erneut senden'));
          final retry = api.calls
              .lastWhere(
                (call) => call.body != null && call.path.endsWith('/receipts'),
              )
              .body!;
          expect(retry, initial);
          expect(api.receipts, hasLength(1));
          expect(api.order!['status'], 'partially_received');
          await receipt(tester, 'LIEF-REST', {0: '5', 1: '7,875'});
          expect(api.order!['status'], 'received');
          expect(api.receipts, hasLength(2));
          expect(find.text('Wareneingang buchen'), findsNothing);
          expect(find.text('LIEF-TEIL'), findsOneWidget);
          expect(find.text('LIEF-REST'), findsOneWidget);
          expect(tester.takeException(), isNull);
        } finally {
          await close(tester, session, api);
        }
      },
    );
  }

  testWidgets(
    'Draft creation and extra source position precede approval without confirming external order',
    (tester) async {
      final api = PurchasingApi(status: null);
      final session = await show(tester, api, materialEntry: true);
      try {
        await tap(tester, find.text('Bestellvorschlag anlegen'));
        await type(tester, 'supplier_name', 'Synthetischer neuer Lieferant');
        await select(
          tester,
          'Artikel · Position 1',
          'TEST-CABLE Synthetisches Kabel · m',
        );
        await type(tester, 'quantity_0', '3,125');
        await tap(tester, find.text('Vorschlag speichern'));
        expect(api.order!['status'], 'proposal');
        expect(api.order!['project_id'], projectId);
        await tap(tester, find.text('Position hinzufügen'));
        await select(
          tester,
          'Artikel · Position 2',
          'TEST-CABLE Synthetisches Kabel · m',
        );
        await type(tester, 'quantity_1', '8');
        await tap(tester, find.text('Vorschlag speichern'));
        expect(api.order!['items'], hasLength(2));
        await tap(tester, find.text('Vorschlag freigeben'));
        await tap(tester, find.text('Positionen und Mengen sind geprüft'));
        await tap(
          tester,
          find.widgetWithText(FilledButton, 'Vorschlag freigeben').last,
        );
        expect(api.order!['status'], 'approved');
        expect(api.order!['confirmation'], isNull);
        expect(
          api.calls.any((call) => call.path.endsWith('/confirm')),
          isFalse,
        );
        expect(tester.takeException(), isNull);
      } finally {
        await close(tester, session, api);
      }
    },
  );

  testWidgets(
    'A 423 receipt pause freezes inputs and retries exactly after activation',
    (tester) async {
      final api = PurchasingApi(status: 'ordered')..pauseReceipt = true;
      final session = await show(tester, api);
      try {
        await tap(tester, find.text('Synthetischer Lieferant'));
        await receipt(tester, 'LIEF-PAUSE', {0: '1'});
        final first = api.calls
            .lastWhere(
              (call) => call.path.endsWith('/receipts') && call.body != null,
            )
            .body!;
        expect(
          tester.widget<TextFormField>(textField('receipt_reference')).enabled,
          isFalse,
        );
        await tap(tester, find.text('Erneut senden'));
        final retry = api.calls
            .lastWhere(
              (call) => call.path.endsWith('/receipts') && call.body != null,
            )
            .body!;
        expect(retry, first);
        expect(api.receipts, hasLength(1));
      } finally {
        await close(tester, session, api);
      }
    },
  );

  testWidgets(
    'Read rights retain inactive history while finance revocation hides prices immediately',
    (tester) async {
      final api = PurchasingApi(status: 'ordered');
      final session = await show(tester, api);
      try {
        await tap(tester, find.text('Synthetischer Lieferant'));
        await receipt(tester, 'LIEF-HISTORY', {0: '1'});
        expect(find.textContaining('777,77'), findsOneWidget);
        api.financeRead = false;
        api.financeWrite = false;
        api.approve = false;
        api.active = false;
        await session.load();
        await tester.pumpAndSettle();
        expect(find.textContaining('777,77'), findsNothing);
        expect(find.textContaining('Einstand netto:'), findsNothing);
        expect(find.text('Wareneingang buchen'), findsNothing);
        expect(find.text('LIEF-HISTORY'), findsOneWidget);
        expect(
          find.textContaining('Material ist fachlich deaktiviert.'),
          findsOneWidget,
        );
        final before = api.calls.where((call) => call.body != null).length;
        await expectLater(
          session.command(
            'disabled-receipt',
            '/purchasing/orders/$orderId/receipts',
            {},
          ),
          throwsA(
            isA<ApiException>().having((error) => error.status, 'status', 423),
          ),
        );
        expect(api.calls.where((call) => call.body != null).length, before);
      } finally {
        await close(tester, session, api);
      }
    },
  );

  testWidgets(
    'Confirmation needs approval without finance write and rechecks inventory rights while open',
    (tester) async {
      final api = PurchasingApi()
        ..financeRead = false
        ..financeWrite = false;
      final session = await show(tester, api);
      try {
        await tap(tester, find.text('Synthetischer Lieferant'));
        await tap(tester, find.text('Externe Bestellung dokumentieren'));
        await type(tester, 'order_reference', 'SYN-EXTERNAL');
        await tap(
          tester,
          find.text(
            'Die Bestellung wurde außerhalb dieser Anwendung ausgelöst',
          ),
        );
        api.inventoryWrite = false;
        await session.load();
        await tester.pumpAndSettle();
        await tap(tester, find.text('Bestellung dokumentieren'));
        expect(api.calls.any((call) => call.path.endsWith('/confirm')), false);
        expect(
          find.text('Die erforderliche Einkaufsberechtigung fehlt.'),
          findsOneWidget,
        );
        api.inventoryWrite = true;
        await session.load();
        await tester.pumpAndSettle();
        await tap(tester, find.text('Bestellung dokumentieren'));
        expect(api.order!['status'], 'ordered');
        expect(find.text('Wareneingang buchen'), findsNothing);
        expect(find.textContaining('Einstand netto:'), findsNothing);
      } finally {
        await close(tester, session, api);
      }
    },
  );

  testWidgets(
    'Global detail honors project grants and denies without changing global capabilities',
    (tester) async {
      final api = PurchasingApi()
        ..financeWrite = false
        ..approve = false
        ..scopedPermissions = {
          'inventory.read',
          'inventory.write',
          'finance.approve',
          'finance.write',
          'finance.read',
        };
      final session = await show(tester, api, global: true);
      try {
        expect(session.can('finance.approve'), false);
        await tap(tester, find.text('Synthetischer Lieferant'));
        expect(find.text('Externe Bestellung dokumentieren'), findsOneWidget);
        expect(
          api.calls.any(
            (call) =>
                call.path == '/api/business/capabilities?project_id=$projectId',
          ),
          true,
        );
        expect(session.can('finance.approve'), false);
        await tap(tester, find.text('Externe Bestellung dokumentieren'));
        await type(tester, 'order_reference', 'SYN-SCOPED');
        await tap(
          tester,
          find.text(
            'Die Bestellung wurde außerhalb dieser Anwendung ausgelöst',
          ),
        );
        await tap(tester, find.text('Bestellung dokumentieren'));
        await receipt(tester, 'SYN-SCOPED-RECEIPT', {0: '1'});
        expect(find.textContaining('777,77'), findsOneWidget);
        api.financeWrite = true;
        api.approve = true;
        api.scopedPermissions = {'inventory.read', 'inventory.write'};
        await session.load();
        await tester.pumpAndSettle();
        expect(session.can('finance.write'), true);
        expect(find.text('Wareneingang buchen'), findsNothing);
        expect(find.textContaining('777,77'), findsNothing);
        expect(find.text('SYN-SCOPED-RECEIPT'), findsOneWidget);
      } finally {
        await close(tester, session, api);
      }
    },
  );

  testWidgets(
    'Purchase decimal precision is rejected before sending without rounding',
    (tester) async {
      final api = PurchasingApi(status: 'ordered');
      final session = await show(tester, api);
      try {
        await tap(tester, find.text('Synthetischer Lieferant'));
        await receipt(tester, 'SYN-PRECISION', {0: '1,00001'});
        expect(
          api.calls.where(
            (call) => call.path.endsWith('/receipts') && call.body != null,
          ),
          isEmpty,
        );
        expect(
          find.textContaining('vier Stellen nach dem Komma'),
          findsOneWidget,
        );
        await type(tester, 'quantity_0', '1,0000');
        await type(tester, 'cost_0', '0,12345');
        await tap(tester, find.text('Wareneingang verbindlich buchen'));
        expect(api.receipts, isEmpty);
        await type(tester, 'cost_0', '0,1234');
        await tap(tester, find.text('Wareneingang verbindlich buchen'));
        final body = api.calls.lastWhere((call) => call.body != null).body!;
        expect(body['lines'], [
          {'line_index': 0, 'quantity': '1.0000', 'unit_cost_net': '0.1234'},
        ]);
      } finally {
        await close(tester, session, api);
      }
    },
  );

  testWidgets(
    'Unconfirmed new proposal restores frozen values and the same request after closing',
    (tester) async {
      final api = PurchasingApi(status: null)..lostProposalAck = true;
      final session = await show(tester, api);
      try {
        await tap(tester, find.text('Bestellvorschlag anlegen'));
        await type(
          tester,
          'supplier_name',
          'Synthetischer wiederaufgenommener Lieferant',
        );
        await select(
          tester,
          'Artikel · Position 1',
          'TEST-CABLE Synthetisches Kabel · m',
        );
        await type(tester, 'quantity_0', '1,1250');
        await tap(tester, find.text('Vorschlag speichern'));
        final first = api.calls.lastWhere((call) => call.body != null).body!;
        await tap(tester, find.text('Schließen'));
        await tap(tester, find.text('Bestellvorschlag anlegen'));
        expect(
          tester
              .widget<TextFormField>(textField('quantity_0'))
              .controller!
              .text,
          '1,1250',
        );
        expect(
          tester.widget<TextFormField>(textField('quantity_0')).enabled,
          false,
        );
        await tap(tester, find.text('Erneut senden'));
        expect(api.calls.lastWhere((call) => call.body != null).body!, first);
        expect(
          session.pendingEditorValues('purchase-proposal-$projectId-new-0-1'),
          isNull,
        );
        expect(api.saved, hasLength(1));
      } finally {
        await close(tester, session, api);
      }
    },
  );

  testWidgets(
    'Paused receipt can close for activation, reopen unchanged, and clears on user switch',
    (tester) async {
      final api = PurchasingApi(status: 'ordered')..pauseReceipt = true;
      final session = await show(tester, api);
      try {
        await tap(tester, find.text('Synthetischer Lieferant'));
        await receipt(tester, 'SYN-PAUSE-REOPEN', {0: '1'});
        final first = api.calls.lastWhere((call) => call.body != null).body!;
        api.inventoryWrite = false;
        await tap(tester, find.text('Erneut senden'));
        expect(
          tester.widget<TextFormField>(textField('cost_0')).enabled,
          false,
        );
        expect(api.calls.lastWhere((call) => call.body != null).body!, first);
        api.inventoryWrite = true;
        await tap(tester, find.text('Schließen'));
        api.active = false;
        await session.load();
        await tester.pumpAndSettle();
        expect(find.text('Wareneingang buchen'), findsNothing);
        expect(find.byType(AlertDialog), findsNothing);
        api.active = true;
        await session.load();
        await tester.pumpAndSettle();
        await tap(tester, find.text('Wareneingang buchen'));
        expect(
          tester.widget<TextFormField>(textField('cost_0')).controller!.text,
          '3,50',
        );
        await tap(tester, find.text('Erneut senden'));
        expect(api.calls.lastWhere((call) => call.body != null).body!, first);
        api.pauseReceipt = true;
        await receipt(tester, 'SYN-REVOKED', {0: '1'});
        expect(
          session.pendingEditorValues('purchase-receive-$orderId-1'),
          isNotNull,
        );
        api.scopedPermissions = {'finance.read'};
        await session.load();
        await tester.pumpAndSettle();
        expect(find.byType(TextFormField), findsNothing);
        expect(find.textContaining('Einstand netto'), findsNothing);
        await tap(tester, find.text('Schließen'));
        api.switchUser();
        await tester.pumpAndSettle();
        expect(
          session.pendingEditorValues('purchase-receive-$orderId-1'),
          isNull,
        );
        expect(session.pending('purchase-receive-$orderId-1'), false);
      } finally {
        await close(tester, session, api);
      }
    },
  );

  testWidgets(
    'Dismiss during in-flight proposal preserves original retry after lost reply',
    (tester) async {
      final reply = Completer<void>();
      final api = PurchasingApi(status: null)
        ..lostProposalAck = true
        ..proposalReply = reply;
      final session = await show(tester, api);
      try {
        await tap(tester, find.text('Bestellvorschlag anlegen'));
        await type(
          tester,
          'supplier_name',
          'Synthetischer wartender Lieferant',
        );
        await select(
          tester,
          'Artikel · Position 1',
          'TEST-CABLE Synthetisches Kabel · m',
        );
        await tester.ensureVisible(find.text('Vorschlag speichern'));
        await tester.tap(find.text('Vorschlag speichern'));
        await tester.pump();
        final first = api.calls.lastWhere((call) => call.body != null).body!;
        api.scopedPermissions = {'inventory.write'};
        await session.load();
        await tester.pump();
        expect(find.byType(TextFormField), findsNothing);
        await tester.tapAt(const Offset(8, 8));
        await tester.pumpAndSettle();
        expect(find.byType(AlertDialog), findsNothing);
        reply.complete();
        await tester.pumpAndSettle();
        api.scopedPermissions = null;
        await session.load();
        await tester.pumpAndSettle();
        await tap(tester, find.text('Bestellvorschlag anlegen'));
        expect(
          tester
              .widget<TextFormField>(textField('supplier_name'))
              .controller!
              .text,
          'Synthetischer wartender Lieferant',
        );
        expect(
          tester.widget<TextFormField>(textField('supplier_name')).enabled,
          false,
        );
        await tap(tester, find.text('Erneut senden'));
        expect(api.calls.lastWhere((call) => call.body != null).body!, first);
      } finally {
        if (!reply.isCompleted) reply.complete();
        await close(tester, session, api);
      }
    },
  );

  testWidgets(
    'Known project read denial clears previously loaded receipt history immediately',
    (tester) async {
      final api = PurchasingApi(status: 'ordered');
      final session = await show(tester, api, global: true);
      try {
        await tap(tester, find.text('Synthetischer Lieferant'));
        await receipt(tester, 'SYN-DENIED-HISTORY', {0: '1'});
        expect(find.textContaining('777,77'), findsOneWidget);
        api.deniedDetail = true;
        await tap(tester, find.byTooltip('Bestellungen aktualisieren'));
        expect(session.can('finance.read'), true);
        expect(find.textContaining('777,77'), findsNothing);
        expect(find.text('SYN-DENIED-HISTORY'), findsNothing);
        expect(find.textContaining('Projektzugriff entzogen'), findsOneWidget);
      } finally {
        await close(tester, session, api);
      }
    },
  );

  testWidgets(
    'Inventory role searches and pages price-free articles while retaining the selected position',
    (tester) async {
      final api = PurchasingApi(status: null)
        ..catalog = true
        ..financeRead = false
        ..financeWrite = false
        ..approve = false
        ..catalogRows = [
          for (var i = 0; i < 65; i++)
            {
              'id': i.toRadixString(16).padLeft(32, '0'),
              'revision': 1,
              'code': 'CAT-${i.toString().padLeft(3, '0')}',
              'name': 'Synthetischer Katalogartikel $i',
              'kind': 'material',
              'unit': 'm',
              'active': true,
              'cost_price_net': '99.8765',
            },
        ];
      final session = await show(tester, api, width: 390);
      try {
        await tap(tester, find.text('Bestellvorschlag anlegen'));
        expect(find.textContaining('99,8765'), findsNothing);
        expect(find.textContaining('99.8765'), findsNothing);
        await tap(
          tester,
          find.byKey(ValueKey('purchase-catalog-item-${'0'.padLeft(32, '0')}')),
        );
        await tester.enterText(
          find.byKey(const ValueKey('purchase-catalog-search')),
          'CAT-064',
        );
        await tap(tester, find.byTooltip('Artikel suchen'));
        expect(find.textContaining('Ausgewählt: CAT-000'), findsOneWidget);
        expect(
          find.text('CAT-064 Synthetischer Katalogartikel 64'),
          findsOneWidget,
        );
        await tester.enterText(
          find.byKey(const ValueKey('purchase-catalog-search')),
          '',
        );
        await tap(tester, find.byTooltip('Artikel suchen'));
        await tap(tester, find.text('Weitere Ergebnisse'));
        expect(
          api.calls.any(
            (call) =>
                call.path.contains('/purchasing/articles') &&
                Uri.parse(call.path).queryParameters['offset'] == '30',
          ),
          true,
        );
        expect(find.textContaining('Ausgewählt: CAT-000'), findsOneWidget);
        await tap(tester, find.text('Artikel übernehmen'));
        await type(tester, 'supplier_name', 'Synthetischer Lagerlieferant');
        await type(tester, 'quantity_0', '2,1250');
        await tap(tester, find.text('Vorschlag speichern'));
        expect(api.order!['status'], 'proposal');
        expect(api.order!['items'][0]['article_id'], '0'.padLeft(32, '0'));
        expect(
          api.calls.where(
            (call) => call.path.split('?').first == '/api/business/articles',
          ),
          isEmpty,
        );
        expect(
          api.calls
              .where((call) => call.path.contains('/purchasing/articles'))
              .every(
                (call) =>
                    Uri.parse(call.path).queryParameters['project_id'] ==
                    projectId,
              ),
          true,
        );
        expect(tester.takeException(), isNull);
      } finally {
        await close(tester, session, api);
      }
    },
  );

  testWidgets(
    'Catalog pending proposal reopens directly without reselecting unavailable articles',
    (tester) async {
      final api = PurchasingApi(status: null)
        ..catalog = true
        ..financeRead = false
        ..lostProposalAck = true;
      final session = await show(tester, api);
      try {
        await tap(tester, find.text('Bestellvorschlag anlegen'));
        await tap(
          tester,
          find.byKey(const ValueKey('purchase-catalog-item-$articleId')),
        );
        await tap(tester, find.text('Artikel übernehmen'));
        await type(tester, 'supplier_name', 'Synthetischer Katalogretry');
        await type(tester, 'quantity_0', '3,1250');
        await tap(tester, find.text('Vorschlag speichern'));
        final first = api.calls.lastWhere((call) => call.body != null).body!;
        final reads = api.calls
            .where((call) => call.path.contains('/purchasing/articles'))
            .length;
        await tap(tester, find.text('Schließen'));
        api.catalogRows = [];
        await tap(tester, find.text('Bestellvorschlag anlegen'));
        expect(find.text('Einkaufsartikel auswählen'), findsNothing);
        expect(
          api.calls
              .where((call) => call.path.contains('/purchasing/articles'))
              .length,
          reads,
        );
        expect(
          tester
              .widget<TextFormField>(textField('quantity_0'))
              .controller!
              .text,
          '3,1250',
        );
        expect(
          tester.widget<TextFormField>(textField('quantity_0')).enabled,
          false,
        );
        await tap(tester, find.text('Erneut senden'));
        expect(api.calls.lastWhere((call) => call.body != null).body!, first);
        expect(api.order!['status'], 'proposal');
      } finally {
        await close(tester, session, api);
      }
    },
  );

  testWidgets(
    'Project-specific catalog denial clears the selection without leaking financial data',
    (tester) async {
      final api = PurchasingApi(status: 'proposal')
        ..catalog = true
        ..financeRead = false;
      final session = await show(tester, api, global: true);
      try {
        await tap(tester, find.text('Synthetischer Lieferant'));
        await tap(tester, find.text('Position hinzufügen'));
        await tap(
          tester,
          find.byKey(const ValueKey('purchase-catalog-item-$articleId')),
        );
        expect(
          find.byKey(const ValueKey('purchase-catalog-selection')),
          findsOneWidget,
        );
        api.deniedCatalog = true;
        await tap(tester, find.byTooltip('Artikel suchen'));
        expect(
          find.byKey(const ValueKey('purchase-catalog-selection')),
          findsNothing,
        );
        expect(
          find.textContaining('Projektbezogene Artikelauswahl gesperrt'),
          findsOneWidget,
        );
        expect(
          tester
              .widget<FilledButton>(
                find.widgetWithText(FilledButton, 'Artikel übernehmen'),
              )
              .onPressed,
          isNull,
        );
        expect(
          api.calls
              .where((call) => call.path.contains('/purchasing/articles'))
              .every(
                (call) =>
                    Uri.parse(call.path).queryParameters['project_id'] ==
                    projectId,
              ),
          true,
        );
        expect(api.calls.where((call) => call.body != null), isEmpty);
        expect(find.textContaining('99.8765'), findsNothing);
      } finally {
        await close(tester, session, api);
      }
    },
  );

  testWidgets(
    'Catalog adds a position without replacing existing source positions',
    (tester) async {
      const extraId = 'eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee';
      final api = PurchasingApi(status: 'proposal')
        ..catalog = true
        ..financeRead = false;
      api.catalogRows.add({
        'id': extraId,
        'revision': 1,
        'code': 'TEST-NEW',
        'name': 'Neuer Lagerartikel',
        'kind': 'machine',
        'unit': 'Stk',
        'active': true,
      });
      final session = await show(tester, api);
      try {
        await tap(tester, find.text('Synthetischer Lieferant'));
        await tap(tester, find.text('Position hinzufügen'));
        await tester.enterText(
          find.byKey(const ValueKey('purchase-catalog-search')),
          'TEST-NEW',
        );
        await tap(tester, find.byTooltip('Artikel suchen'));
        await tap(
          tester,
          find.byKey(const ValueKey('purchase-catalog-item-$extraId')),
        );
        await tap(tester, find.text('Artikel übernehmen'));
        await type(tester, 'quantity_2', '2');
        await tap(tester, find.text('Vorschlag speichern'));
        final body = api.calls.lastWhere((call) => call.body != null).body!;
        expect(body['items'], [
          {'article_id': articleId, 'quantity': '5.0000'},
          {'article_id': articleId, 'quantity': '10.0000'},
          {'article_id': extraId, 'quantity': '2'},
        ]);
      } finally {
        await close(tester, session, api);
      }
    },
  );

  testWidgets(
    'Older receipt server without price-free catalog explains restricted creation and never calls missing route',
    (tester) async {
      final api = PurchasingApi(status: null)..financeRead = false;
      final session = await show(tester, api);
      try {
        expect(find.text('Bestellvorschlag anlegen'), findsNothing);
        expect(
          find.textContaining('noch keine preisfreie Einkaufsartikelauswahl'),
          findsOneWidget,
        );
        await tap(tester, find.byTooltip('Bestellungen aktualisieren'));
        expect(
          api.calls.where((call) => call.path.contains('/articles')),
          isEmpty,
        );
        expect(api.calls.where((call) => call.body != null), isEmpty);
      } finally {
        await close(tester, session, api);
      }
    },
  );

  testWidgets(
    'Older server without purchasing feature does not expose or fetch purchase flow',
    (tester) async {
      final api = PurchasingApi()..feature = false;
      final session = await show(tester, api, materialEntry: true);
      try {
        expect(find.text('Bestellungen und Wareneingänge'), findsNothing);
        expect(
          api.calls.where((call) => call.path.contains('/purchasing/')),
          isEmpty,
        );
      } finally {
        await close(tester, session, api);
      }
    },
  );
}

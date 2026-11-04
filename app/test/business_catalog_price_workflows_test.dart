import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:smartplan_office/api.dart';
import 'package:smartplan_office/business_catalog_prices.dart';
import 'package:smartplan_office/business_documents.dart';
import 'package:smartplan_office/business_purchasing.dart';
import 'package:smartplan_office/business_sales.dart';
import 'package:smartplan_office/business_operations.dart';
import 'package:smartplan_office/business_session.dart';

import 'business_catalog_prices_test.dart';
import 'business_catalog_price_consumers_test.dart';
import 'business_purchasing_test.dart' as purchasing;
import 'business_sales_test.dart' as sales;

class DatedPurchaseApi extends purchasing.PurchasingApi {
  DatedPurchaseApi() : super(status: null);
  final prices = PriceApi();
  @override
  Future<dynamic> call(String path, [Map<String, dynamic>? body]) async {
    if (path.contains('/catalog-prices/') ||
        path.split('?').first == '/api/business/articles')
      return prices.call(path, body);
    if (path.contains('/capabilities')) {
      final result = priceCopy(await super.call(path, body));
      result['capabilities'].add('business_catalog_prices');
      result['features'].add('catalog_prices_v2');
      return result;
    }
    final result = await super.call(path, body);
    if (body != null && path.contains('/inventory/orders')) {
      for (final item in order!['items']) {
        item['catalog_price_required'] = true;
        item['catalog_price_snapshot'] = priceCopy(
          priceFixture['pricing']['components'][0]['catalog_price_snapshot'],
        );
        item['unit'] = 'ST';
      }
    }
    return result;
  }

  @override
  void dispose() {
    prices.dispose();
    super.dispose();
  }
}

class DatedSalesApi extends sales.SalesApi {
  final prices = PriceApi();
  final offers = <Map<String, dynamic>>[];
  @override
  Future<dynamic> call(String path, [Map<String, dynamic>? body]) async {
    if (path.contains('/catalog-prices/') || path == '/api/business/articles')
      return prices.call(path, body);
    if (path.contains('/capabilities')) {
      final result = priceCopy(await super.call(path, body));
      result['capabilities'].add('business_catalog_prices');
      result['features'].add('catalog_prices_v2');
      return result;
    }
    if (path.endsWith('/offer')) {
      offers.add(priceCopy(body));
      return {'id': 'e' * 32};
    }
    return super.call(path, body);
  }

  @override
  void dispose() {
    prices.dispose();
    super.dispose();
  }
}

class ReplayConsumerApi extends ConsumerPriceApi {
  int? lose;
  Completer<void>? holdSave;
  @override
  Future<dynamic> call(String path, [Map<String, dynamic>? body]) async {
    if (body != null &&
        (path == '/api/business/documents' ||
            path.startsWith('/api/business/inventory/orders'))) {
      saves.add(priceCopy(body));
      await holdSave?.future;
      if (lose != null) {
        final code = lose!;
        lose = null;
        throw ApiException(code, 'SYNTHETIC UNCERTAIN DATED SAVE');
      }
      return {...priceCopy(priceFixture['document']), ...body};
    }
    if (path.startsWith('/api/business/documents/'))
      return priceCopy(priceFixture['document']);
    return super.call(path, body);
  }
}

Future<void> setupSize(WidgetTester t) async {
  t.view.physicalSize = const Size(1100, 1600);
  t.view.devicePixelRatio = 1;
  addTearDown(t.view.resetPhysicalSize);
  addTearDown(t.view.resetDevicePixelRatio);
}

Future<void> selectField(WidgetTester t, String label, String text) async {
  final field = find.byWidgetPredicate(
    (w) =>
        w is DropdownButtonFormField<String> && w.decoration.labelText == label,
  );
  await t.ensureVisible(field);
  await t.tap(field);
  await t.pumpAndSettle();
  await t.tap(find.text(text).last);
  await t.pumpAndSettle();
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  for (final status in [0, 403, 404, 409])
    for (final order in [false, true])
      test(
        'narrow dated ${order ? 'order' : 'document'} replay $status preserves nonce after generation and requires fresh rights',
        () async {
          final api = ReplayConsumerApi()..lose = status;
          final owner = BusinessSession(api: api);
          await owner.load();
          final id = 'b' * 32,
              key = order
                  ? 'purchase-proposal-all-new-0-1'
                  : 'catalog-v2-document-$id',
              path = order ? '/inventory/orders' : '/documents';
          final values = <String, dynamic>{
            'project_id': id,
            order ? 'items' : 'positions': [
              {
                'article_id': api.article['id'],
                'quantity': '3',
                'catalog_price_selection': catalogSelectionFromSnapshot(
                  priceCopy(
                    priceFixture['document']['positions'][0]['catalog_price_snapshot'],
                  ),
                ),
              },
            ],
          };
          await expectLater(
            owner.catalogConsumerCommand(key, path, values),
            throwsA(isA<ApiException>()),
          );
          expect(owner.pending(key), true);
          api.generation++;
          api.read = false;
          await expectLater(
            owner.catalogConsumerCommand(key, path, values),
            throwsA(isA<ApiException>()),
          );
          expect(api.saves, hasLength(1));
          api.read = true;
          await owner.catalogConsumerCommand(key, path, values);
          expect(api.saves[0], api.saves[1]);
          expect(owner.pending(key), false);
          owner.dispose();
          api.dispose();
        },
      );
  test(
    'ordinary document command keeps existing non-documentary policy',
    () async {
      final api = ReplayConsumerApi()..lose = 403;
      final session = BusinessSession(api: api);
      await session.load();
      final key = 'catalog-v2-document-${'b' * 32}';
      await expectLater(
        session.catalogConsumerCommand(key, '/documents', {
          'positions': [
            {'description': 'Manual', 'unit_price_net': '0'},
          ],
        }),
        throwsA(isA<ApiException>()),
      );
      expect(session.pending(key), false);
      session.dispose();
      api.dispose();
    },
  );
  testWidgets(
    'dated document lost ACK survives close reopen with original source and nonce',
    (t) async {
      final api = ReplayConsumerApi()..lose = 0;
      final session = await consumerMount(t, api);
      await t.enterText(
        find.byKey(const ValueKey('business-document-title')),
        'Unconfirmed source',
      );
      await priceTap(t, 'Katalogpreis auswählen');
      await chooseArticle(t, api, quantity: '3');
      await chooseDay(t);
      await priceTap(t, 'Entwurf speichern');
      expect(api.saves, hasLength(1));
      await t.pumpWidget(const SizedBox.shrink());
      await t.pumpAndSettle();
      api.generation++;
      await session.load();
      await t.pumpWidget(
        MaterialApp(home: BusinessDocumentEditor(session: session)),
      );
      await t.pumpAndSettle();
      expect(api.candidateCalls, hasLength(2));
      await priceTap(t, 'Dieselben Eingaben erneut senden');
      expect(api.saves, hasLength(2));
      expect(api.saves[0], api.saves[1]);
      expect(api.candidateCalls, hasLength(2));
      await finishPrices(t, session, api);
    },
  );
  testWidgets(
    'purchasing uses explicit price without finance write and preserves it through approval',
    (t) async {
      await setupSize(t);
      final api = DatedPurchaseApi()..financeWrite = false;
      final session = BusinessSession(
        api: api,
        projectId: purchasing.projectId,
      );
      await session.load();
      await t.pumpWidget(
        MaterialApp(
          home: Scaffold(body: BusinessPurchasingPage(session: session)),
        ),
      );
      await t.pumpAndSettle();
      await priceTap(t, 'Bestellvorschlag anlegen');
      await t.enterText(
        find.byKey(const ValueKey('business-field-supplier_name')),
        'Synthetic dated supplier',
      );
      await selectField(
        t,
        'Artikel · Position 1',
        '${api.prices.article['code']} ${api.prices.article['name']} · ${api.prices.article['unit']}',
      );
      await t.enterText(
        find.byKey(const ValueKey('business-field-quantity_0')),
        '3',
      );
      await t.tap(find.text('Vorschlag speichern'));
      await t.pump();
      await t.pump(const Duration(milliseconds: 300));
      await t.enterText(
        find.byKey(const ValueKey('catalog-price-day')),
        '2026-11-30',
      );
      await t.tap(find.text('Preisquellen prüfen'));
      await t.pump();
      await t.pump(const Duration(milliseconds: 300));
      await t.tap(find.text('Diesen Preis wählen'));
      await t.pumpAndSettle();
      final first = api.calls
          .lastWhere(
            (c) => c.body != null && c.path.contains('/inventory/orders'),
          )
          .body!;
      expect(
        first['items'][0]['catalog_price_selection']['effective_on'],
        '2026-11-30',
      );
      expect(first['items'][0].containsKey('unit_cost_net'), false);
      await priceTap(t, 'Vorschlag freigeben');
      await priceTap(t, 'Positionen und Mengen sind geprüft');
      await t.tap(
        find.widgetWithText(FilledButton, 'Vorschlag freigeben').last,
      );
      await t.pumpAndSettle();
      final approved = api.calls
          .lastWhere(
            (c) => c.body != null && c.path.contains('/inventory/orders'),
          )
          .body!;
      expect(
        approved['items'][0]['catalog_price_selection'],
        first['items'][0]['catalog_price_selection'],
      );
      await priceTap(t, 'Externe Bestellung dokumentieren');
      expect(
        t
            .widget<TextFormField>(
              find.byKey(const ValueKey('business-field-ordered_on')),
            )
            .controller!
            .text,
        '',
      );
      await t.enterText(
        find.byKey(const ValueKey('business-field-order_reference')),
        'SYN-ORDER',
      );
      await t.enterText(
        find.byKey(const ValueKey('business-field-ordered_on')),
        '2026-12-01',
      );
      await priceTap(
        t,
        'Die Bestellung wurde außerhalb dieser Anwendung ausgelöst',
      );
      await t.tap(
        find.widgetWithText(FilledButton, 'Bestellung dokumentieren').last,
      );
      await t.pumpAndSettle();
      expect(api.calls.where((c) => c.path.endsWith('/confirm')), isEmpty);
      expect(find.textContaining('Tatsächliches Bestelldatum'), findsOneWidget);
      await t.pumpWidget(const SizedBox.shrink());
      session.dispose();
      api.dispose();
    },
  );
  testWidgets(
    'sales adoption keeps explicit dated article identity and quantity',
    (t) async {
      await setupSize(t);
      final api = DatedSalesApi();
      api.saved['links'] = [
        {'kind': 'project', 'project_id': 'd' * 32},
      ];
      final owner = BusinessSession(api: api);
      await owner.load();
      await t.pumpWidget(MaterialApp(home: BusinessSalesPage(session: owner)));
      await t.pumpAndSettle();
      await priceTap(t, 'Synthetic installation');
      await priceTap(t, 'Angebot aus Katalog erstellen');
      await priceTap(
        t,
        '${api.prices.article['name']} · Datierter Verkaufspreis erforderlich',
      );
      await priceTap(t, 'Speichern');
      await chooseDay(t);
      await t.enterText(
        find.byKey(const ValueKey('business-field-due_date')),
        '2026-12-01',
      );
      await t.enterText(
        find.byKey(
          ValueKey('business-field-quantity_${api.prices.article['id']}'),
        ),
        '3',
      );
      await priceTap(
        t,
        'Ich bestätige Positionen, Katalogpreise und Angebotsentwurf.',
      );
      await priceTap(t, 'Speichern');
      final line = api.offers.single['positions'].single;
      expect(line['article_id'], api.prices.article['id']);
      expect(line['article_revision'], api.prices.article['revision']);
      expect(line['quantity'], '3');
      expect(line['catalog_price_selection']['effective_on'], '2026-11-30');
      await t.pumpWidget(const SizedBox.shrink());
      owner.dispose();
      api.dispose();
    },
  );
  testWidgets('managed article editor hides technical zero price fields', (
    t,
  ) async {
    await setupSize(t);
    final api = PriceApi();
    final owner = BusinessSession(api: api);
    await owner.load();
    await t.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: BusinessAreaPage(session: owner, area: 'material'),
        ),
      ),
    );
    await t.pumpAndSettle();
    await t.tap(find.byType(DropdownButtonFormField<String>).first);
    await t.pumpAndSettle();
    await t.tap(find.text('Artikel und Leistungen').last);
    await t.pumpAndSettle();
    await priceTap(t, api.article['name']);
    expect(find.text('Artikelstamm · datierte Preise separat'), findsOneWidget);
    expect(
      find.byKey(const ValueKey('business-field-unit_price_net')),
      findsNothing,
    );
    expect(
      find.byKey(const ValueKey('business-field-cost_price_net')),
      findsNothing,
    );
    await finishPrices(t, owner, api);
  });
  for (final lateError in [false, true])
    testWidgets(
      'late dated document save $lateError cannot navigate or reveal error after background',
      (t) async {
        final api = ReplayConsumerApi()..holdSave = Completer<void>();
        if (lateError) api.lose = 409;
        final owner = await consumerMount(t, api);
        await t.enterText(
          find.byKey(const ValueKey('business-document-title')),
          'Private pending document',
        );
        await priceTap(t, 'Katalogpreis auswählen');
        await chooseArticle(t, api, quantity: '3');
        await chooseDay(t);
        final button = find.text('Entwurf speichern');
        await t.ensureVisible(button);
        await t.tap(button);
        await t.pump();
        expect(api.saves, hasLength(1));
        t.binding.handleAppLifecycleStateChanged(AppLifecycleState.inactive);
        await t.pump();
        t.binding.handleAppLifecycleStateChanged(AppLifecycleState.resumed);
        api.holdSave!.complete();
        await t.pumpAndSettle();
        expect(find.byType(BusinessDocumentPage), findsNothing);
        expect(find.textContaining('SYNTHETIC UNCERTAIN'), findsNothing);
        expect(find.text('Private pending document'), findsNothing);
        await finishPrices(t, owner, api);
      },
    );
  testWidgets(
    'global editor recovers exact dated pending document after explicit project selection',
    (t) async {
      await setupSize(t);
      final api = ReplayConsumerApi()..lose = 0;
      final owner = BusinessSession(
        api: api,
        projects: [
          {'id': 'b' * 32, 'name': 'Explicit project'},
        ],
      );
      await owner.load();
      final body = {
        'project_id': 'b' * 32,
        'kind': 'offer',
        'title': 'Original global pending title',
        'issue_date': '2026-11-04',
        'positions': priceCopy(priceFixture['document'])['positions'],
      };
      await expectLater(
        owner.catalogConsumerCommand(
          'catalog-v2-document-${'b' * 32}',
          '/documents',
          body,
        ),
        throwsA(isA<ApiException>()),
      );
      await t.pumpWidget(
        MaterialApp(home: BusinessDocumentEditor(session: owner)),
      );
      await t.pumpAndSettle();
      await selectField(t, 'Projekt', 'Explicit project');
      expect(
        t
            .widget<TextFormField>(
              find.byKey(const ValueKey('business-document-title')),
            )
            .controller!
            .text,
        body['title'],
      );
      await priceTap(t, 'Dieselben Eingaben erneut senden');
      expect(api.saves, hasLength(2));
      expect(api.saves[0], api.saves[1]);
      await finishPrices(t, owner, api);
    },
  );
}

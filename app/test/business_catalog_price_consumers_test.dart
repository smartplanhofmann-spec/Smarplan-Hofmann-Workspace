import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:smartplan_office/business_documents.dart';
import 'package:smartplan_office/business_document_pricing.dart';
import 'package:smartplan_office/business_session.dart';
import 'package:smartplan_office/api.dart';

import 'business_catalog_prices_test.dart';

class ConsumerPriceApi extends PriceApi {
  final saves = <Map<String, dynamic>>[],
      calculations = <Map<String, dynamic>>[];
  @override
  Future<dynamic> call(String path, [Map<String, dynamic>? body]) async {
    if (path == '/api/business/templates' ||
        path.startsWith('/api/business/documents/time-sources') ||
        path.startsWith('/api/business/documents?'))
      return {'items': []};
    if (path == '/api/business/documents' && body != null) {
      saves.add(priceCopy(body));
      return {...priceCopy(priceFixture['document']), ...body};
    }
    if (path == '/api/business/commercial/pricing/preview') {
      calculations.add(priceCopy(body));
      return priceCopy(priceFixture['pricing']);
    }
    return super.call(path, body);
  }
}

Future<void> chooseArticle(
  WidgetTester t,
  ConsumerPriceApi api, {
  String? quantity,
}) async {
  final field = find.byWidgetPredicate(
    (widget) =>
        widget is DropdownButtonFormField<String> &&
        widget.decoration.labelText == 'Artikel',
  );
  await t.ensureVisible(field);
  await t.tap(field);
  await t.pumpAndSettle();
  await t.tap(find.textContaining(api.article['name']).last);
  await t.pumpAndSettle();
  if (quantity != null)
    await t.enterText(
      find.byKey(const ValueKey('business-field-quantity')),
      quantity,
    );
  await t.tap(find.widgetWithText(FilledButton, 'Speichern').last);
  await t.pumpAndSettle();
}

Future<void> chooseDay(WidgetTester t) async {
  expect(
    t
        .widget<TextField>(find.byKey(const ValueKey('catalog-price-day')))
        .controller!
        .text,
    '',
  );
  await t.enterText(
    find.byKey(const ValueKey('catalog-price-day')),
    '2026-11-30',
  );
  await priceTap(t, 'Preisquellen prüfen');
  await priceTap(t, 'Diesen Preis wählen');
}

Future<BusinessSession> consumerMount(
  WidgetTester t,
  ConsumerPriceApi api, {
  bool pricing = false,
}) async {
  t.view.physicalSize = const Size(1100, 1600);
  t.view.devicePixelRatio = 1;
  addTearDown(t.view.resetPhysicalSize);
  addTearDown(t.view.resetDevicePixelRatio);
  final session = BusinessSession(api: api, projectId: 'b' * 32);
  await session.load();
  await t.pumpWidget(
    MaterialApp(
      home: pricing
          ? BusinessPricingEditor(session: session)
          : BusinessDocumentEditor(session: session),
    ),
  );
  await t.pumpAndSettle();
  return session;
}

void main() {
  testWidgets(
    'document creates explicit dated position with original raw price and identity',
    (t) async {
      final api = ConsumerPriceApi();
      final session = await consumerMount(t, api);
      await t.enterText(
        find.byKey(const ValueKey('business-document-title')),
        'Novemberquelle',
      );
      await priceTap(t, 'Katalogpreis auswählen');
      await chooseArticle(t, api, quantity: '3');
      await chooseDay(t);
      expect(find.textContaining('10.00 EUR / 1 ST'), findsOneWidget);
      await priceTap(t, api.article['name']);
      await t.enterText(
        find.byKey(const ValueKey('business-field-tax_rate')),
        '7',
      );
      await priceTap(t, 'Speichern');
      await priceTap(t, 'Entwurf speichern');
      final line = api.saves.single['positions'].single;
      expect(line['article_id'], api.article['id']);
      expect(line['article_revision'], api.article['revision']);
      expect(line['unit_price_net'], '10.00');
      expect(line['price_base_quantity'], '1');
      expect(line['quantity'], '3');
      expect(line['tax_rate'], '7');
      expect(line['catalog_price_label'], isNull);
      expect(line['catalog_price_selection']['effective_on'], '2026-11-30');
      expect(
        line['catalog_price_selection']['price_id'],
        (priceFixture['candidates']['2026-11-30']['items'] as List).singleWhere(
          (item) => item['status'] == 'eligible',
        )['price_id'],
      );
      await finishPrices(t, session, api);
    },
  );
  testWidgets(
    'pricing BOM sends explicit purchase source without rounding one euro per three units',
    (t) async {
      final api = ConsumerPriceApi();
      final session = await consumerMount(t, api, pricing: true);
      await t.enterText(
        find.byKey(const ValueKey('pricing-description')),
        'Exakte Stückliste',
      );
      await t.enterText(
        find.byKey(const ValueKey('pricing-base_cost_net')),
        '0',
      );
      await priceTap(t, 'Artikel hinzufügen');
      await chooseArticle(t, api, quantity: '3');
      await chooseDay(t);
      expect(find.textContaining('1.00 EUR / 3 ST'), findsOneWidget);
      await priceTap(t, 'Preis berechnen');
      final input = api.calculations.single;
      final component = input['components'].single;
      expect(component['quantity'], '3');
      expect(component['price_selection']['effective_on'], '2026-11-30');
      expect(component.containsKey('cost_price_net'), false);
      expect(find.text('Kalkulationsvorschau'), findsOneWidget);
      expect(priceFixture['pricing']['unit_cost_net'], '1.00');
      await finishPrices(t, session, api);
    },
  );
  testWidgets(
    'bound root cost skips manual required zero and sends only authoritative source',
    (t) async {
      final api = ConsumerPriceApi();
      final session = await consumerMount(t, api, pricing: true);
      await t.enterText(
        find.byKey(const ValueKey('pricing-description')),
        'Gebundene Basis',
      );
      await priceTap(t, 'Datierte Basiskostenquelle wählen');
      await chooseArticle(t, api);
      await chooseDay(t);
      expect(
        t
            .widget<TextFormField>(
              find.byKey(const ValueKey('pricing-base_cost_net')),
            )
            .enabled,
        false,
      );
      await priceTap(t, 'Preis berechnen');
      expect(api.calculations, hasLength(1));
      expect(api.calculations.single.containsKey('base_cost_net'), false);
      expect(
        api.calculations.single['source_price_selection']['effective_on'],
        '2026-11-30',
      );
      await finishPrices(t, session, api);
    },
  );
  for (final screen in ['document', 'pricing'])
    for (final change in [
      'background',
      'generation',
      'read',
      'write',
      'module',
    ]) {
      testWidgets('$screen delayed source error is discarded after $change', (
        t,
      ) async {
        final api = ConsumerPriceApi()..holdCandidates = Completer<dynamic>();
        final session = await consumerMount(
          t,
          api,
          pricing: screen == 'pricing',
        );
        await priceTap(
          t,
          screen == 'pricing' ? 'Artikel hinzufügen' : 'Katalogpreis auswählen',
        );
        await chooseArticle(t, api, quantity: '3');
        await t.enterText(
          find.byKey(const ValueKey('catalog-price-day')),
          '2026-11-30',
        );
        await t.tap(find.text('Preisquellen prüfen'));
        await t.pump();
        if (change == 'background') {
          t.binding.handleAppLifecycleStateChanged(AppLifecycleState.paused);
          await t.pump();
          t.binding.handleAppLifecycleStateChanged(AppLifecycleState.resumed);
        } else {
          if (change == 'generation') api.generation++;
          if (change == 'read') api.read = false;
          if (change == 'write') api.write = false;
          if (change == 'module') api.enabled = false;
          await session.load();
        }
        api.holdCandidates!.completeError(
          const ApiException(409, 'PRIVATE OLD CANDIDATE'),
        );
        await t.pumpAndSettle();
        expect(find.textContaining('PRIVATE OLD'), findsNothing);
        expect(find.text('Diesen Preis wählen'), findsNothing);
        expect(api.saves, isEmpty);
        expect(api.calculations, isEmpty);
        await finishPrices(t, session, api);
      });
    }
}

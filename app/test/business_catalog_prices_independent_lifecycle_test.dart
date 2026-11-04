import 'dart:async';
import 'dart:convert';
import 'dart:typed_data';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:smartplan_office/api.dart';
import 'package:smartplan_office/business_catalog_prices.dart';
import 'package:smartplan_office/business_document_pricing.dart';
import 'package:smartplan_office/business_documents.dart';
import 'package:smartplan_office/business_purchasing.dart';
import 'package:smartplan_office/business_session.dart';
import 'package:smartplan_office/mail_attachment_widgets.dart';

// Reuse only transports and actual domain fixtures, not the owner's assertions.
import 'business_catalog_prices_test.dart';
import 'business_catalog_price_consumers_test.dart';
import 'business_catalog_price_workflows_test.dart';
import 'business_purchasing_test.dart' as purchasing;

class HeldCalculationApi extends ConsumerPriceApi {
  final reply = Completer<dynamic>();
  @override
  Future<dynamic> call(String path, [Map<String, dynamic>? body]) async {
    if (path.endsWith('/commercial/pricing/preview')) {
      calculations.add(priceCopy(body));
      return reply.future;
    }
    return super.call(path, body);
  }
}

class HeldPurchaseApi extends DatedPurchaseApi {
  final reply = Completer<void>();
  bool fail = false;
  @override
  Future<dynamic> call(String path, [Map<String, dynamic>? body]) async {
    final result = await super.call(path, body);
    if (body != null && path == '/api/business/inventory/orders') {
      await reply.future;
      if (fail) throw const ApiException(0, 'PRIVATE OLD ORDER RESPONSE');
    }
    return result;
  }
}

Future<void> reviewClick(WidgetTester t, String label) async {
  final button = find.text(label).last;
  await t.ensureVisible(button);
  await t.pump();
  await t.tap(button);
  await t.pump();
  await t.pump(const Duration(milliseconds: 300));
}

Future<void> selectDatedDocument(WidgetTester t, ConsumerPriceApi api) async {
  await t.enterText(
    find.byKey(const ValueKey('business-document-title')),
    'PRIVATE ORIGINAL DOCUMENT',
  );
  await priceTap(t, 'Katalogpreis auswählen');
  await chooseArticle(t, api, quantity: '3');
  await chooseDay(t);
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  for (final fail in [false, true]) {
    testWidgets('independent role replacement rejects late candidate $fail', (
      t,
    ) async {
      final api = PriceApi()..holdCandidates = Completer<dynamic>();
      final session = await mountPrices(t, api, picker: true);
      await t.enterText(
        find.byKey(const ValueKey('catalog-price-day')),
        '2026-11-30',
      );
      await reviewClick(t, 'Preisquellen prüfen');
      expect(api.candidateCalls.single['price_role'], 'sales_net');
      await t.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: CatalogPricePicker(
              session: session,
              article: api.article,
              role: 'purchase_net',
            ),
          ),
        ),
      );
      await t.pump();
      if (fail) {
        api.holdCandidates!.completeError(
          const ApiException(409, 'PRIVATE OLD SALES PRICE'),
        );
      } else {
        api.holdCandidates!.complete(
          priceCopy(priceFixture['candidates']['2026-11-30']),
        );
      }
      await t.pumpAndSettle();
      expect(find.textContaining('PRIVATE OLD SALES PRICE'), findsNothing);
      expect(find.text('Diesen Preis wählen'), findsNothing);
      expect(
        t
            .widget<TextField>(find.byKey(const ValueKey('catalog-price-day')))
            .controller!
            .text,
        '',
      );
      expect(api.commands, isEmpty);
      await finishPrices(t, session, api);
    });
  }

  for (final grant in ['read', 'write']) {
    testWidgets(
      'independent selected price rechecks $grant after unnotified revoke',
      (t) async {
        final api = ConsumerPriceApi();
        final session = await consumerMount(t, api);
        await priceTap(t, 'Katalogpreis auswählen');
        await chooseArticle(t, api, quantity: '3');
        await t.enterText(
          find.byKey(const ValueKey('catalog-price-day')),
          '2026-11-30',
        );
        await priceTap(t, 'Preisquellen prüfen');
        api.holdCandidates = Completer<dynamic>();
        await reviewClick(t, 'Diesen Preis wählen');
        expect(api.candidateCalls, hasLength(2));
        // No session notification: the final actual capability request must detect this.
        if (grant == 'read') api.read = false;
        if (grant == 'write') api.write = false;
        api.holdCandidates!.complete(
          priceCopy(priceFixture['candidates']['2026-11-30']),
        );
        await t.pumpAndSettle();
        expect(find.byType(CatalogPricePicker), findsNothing);
        expect(find.textContaining('je 1.0000 ST netto'), findsNothing);
        expect(api.saves, isEmpty);
        await finishPrices(t, session, api);
      },
    );
  }

  testWidgets(
    'independent revoked source between listing and choice never becomes a document position',
    (t) async {
      final api = ConsumerPriceApi();
      final session = await consumerMount(t, api);
      await priceTap(t, 'Katalogpreis auswählen');
      await chooseArticle(t, api, quantity: '3');
      await t.enterText(
        find.byKey(const ValueKey('catalog-price-day')),
        '2026-11-30',
      );
      await priceTap(t, 'Preisquellen prüfen');
      api.holdCandidates = Completer<dynamic>();
      await reviewClick(t, 'Diesen Preis wählen');
      final response = priceCopy(priceFixture['candidates']['2026-11-30']);
      response['items'] = <dynamic>[];
      api.holdCandidates!.complete(response);
      await t.pumpAndSettle();
      expect(find.textContaining('Preisquelle wurde geändert'), findsOneWidget);
      expect(find.byType(CatalogPricePicker), findsOneWidget);
      expect(api.saves, isEmpty);
      await finishPrices(t, session, api);
    },
  );

  testWidgets(
    'independent original export rechecks read after correct delayed bytes',
    (t) async {
      final api = PriceApi()..holdOriginal = Completer<Uint8List>();
      var exports = 0;
      final session = await mountPrices(
        t,
        api,
        exporter: (_, __, ___) async {
          exports++;
          return MailAttachmentExportResult.saved;
        },
      );
      await openPriceRun(t, api);
      await reviewClick(t, 'Original herunterladen');
      api.read = false; // Deliberately not followed by session.load().
      api.holdOriginal!.complete(base64Decode(priceFixture['original_base64']));
      await t.pumpAndSettle();
      expect(exports, 0);
      expect(find.text('Original herunterladen'), findsNothing);
      await finishPrices(t, session, api);
    },
  );

  for (final fail in [false, true]) {
    for (final change in ['session', 'generation', 'read']) {
      testWidgets(
        'independent delayed document save $fail cannot cross $change at 390px',
        (t) async {
          final api = ReplayConsumerApi()..holdSave = Completer<void>();
          if (fail) api.lose = 409;
          final owner = await consumerMount(t, api);
          await selectDatedDocument(t, api);
          t.view.physicalSize = const Size(390, 844);
          await t.pumpAndSettle();
          await reviewClick(t, 'Entwurf speichern');
          expect(api.saves, hasLength(1));
          final submitted = priceCopy(api.saves.single);
          BusinessSession? replacement;
          ReplayConsumerApi? replacementApi;
          if (change == 'session') {
            replacementApi = ReplayConsumerApi();
            replacement = BusinessSession(
              api: replacementApi,
              projectId: 'c' * 32,
            );
            await replacement.load();
            await t.pumpWidget(
              MaterialApp(home: BusinessDocumentEditor(session: replacement)),
            );
          } else {
            if (change == 'generation') api.generation++;
            if (change == 'read') api.read = false;
            await owner.load();
            await t.pump();
          }
          api.holdSave!.complete();
          await t.pumpAndSettle();
          expect(find.byType(BusinessDocumentPage), findsNothing);
          expect(find.textContaining('SYNTHETIC UNCERTAIN'), findsNothing);
          expect(find.text('PRIVATE ORIGINAL DOCUMENT'), findsNothing);
          expect(api.saves.single, submitted);
          expect(replacementApi?.saves ?? [], isEmpty);
          expect(t.takeException(), isNull);
          await finishPrices(t, owner, api);
          replacement?.dispose();
          replacementApi?.dispose();
        },
      );
    }
  }

  testWidgets(
    'independent global project choice resolves only its exact original pending command',
    (t) async {
      await setupSize(t);
      final api = ReplayConsumerApi();
      final owner = BusinessSession(
        api: api,
        projects: [
          {'id': 'b' * 32, 'name': 'Pending project B'},
          {'id': 'c' * 32, 'name': 'Pending project C'},
        ],
      );
      await owner.load();
      for (final id in ['b' * 32, 'c' * 32]) {
        api.lose = 0;
        await expectLater(
          owner.catalogConsumerCommand(
            'catalog-v2-document-$id',
            '/documents',
            {
              'project_id': id,
              'kind': 'offer',
              'title': 'PRIVATE ${id[0]} ORIGINAL',
              'issue_date': '2026-11-04',
              'positions': priceCopy(priceFixture['document'])['positions'],
            },
          ),
          throwsA(isA<ApiException>()),
        );
      }
      final originalB = priceCopy(api.saves[0]),
          originalC = priceCopy(api.saves[1]);
      expect(originalB['request_id'], isNot(originalC['request_id']));
      await t.pumpWidget(
        MaterialApp(home: BusinessDocumentEditor(session: owner)),
      );
      await t.pumpAndSettle();
      expect(
        t
            .widget<TextFormField>(
              find.byKey(const ValueKey('business-document-title')),
            )
            .controller!
            .text,
        '',
      );
      await selectField(t, 'Projekt', 'Pending project C');
      expect(
        t
            .widget<TextFormField>(
              find.byKey(const ValueKey('business-document-title')),
            )
            .controller!
            .text,
        originalC['title'],
      );
      await priceTap(t, 'Dieselben Eingaben erneut senden');
      expect(api.saves, hasLength(3));
      expect(api.saves.last, originalC);
      expect(owner.pending('catalog-v2-document-${'b' * 32}'), true);
      expect(owner.pending('catalog-v2-document-${'c' * 32}'), false);
      expect(api.candidateCalls, isEmpty);
      await finishPrices(t, owner, api);
    },
  );

  for (final fail in [false, true]) {
    testWidgets(
      'independent priced calculation $fail cannot cross project replacement',
      (t) async {
        final api = HeldCalculationApi();
        final owner = await consumerMount(t, api, pricing: true);
        await t.enterText(
          find.byKey(const ValueKey('pricing-description')),
          'PRIVATE PROJECT CALCULATION',
        );
        await priceTap(t, 'Datierte Basiskostenquelle wählen');
        await chooseArticle(t, api);
        await chooseDay(t);
        await reviewClick(t, 'Preis berechnen');
        expect(api.calculations, hasLength(1));
        await t.pumpWidget(
          MaterialApp(
            home: BusinessPricingEditor(session: owner, projectId: 'c' * 32),
          ),
        );
        if (fail) {
          api.reply.completeError(
            const ApiException(409, 'PRIVATE OLD CALCULATION'),
          );
        } else {
          api.reply.complete(priceCopy(priceFixture['pricing']));
        }
        await t.pumpAndSettle();
        expect(find.textContaining('PRIVATE OLD CALCULATION'), findsNothing);
        expect(find.text('PRIVATE PROJECT CALCULATION'), findsNothing);
        expect(find.text('Kalkulierten Preis übernehmen'), findsNothing);
        expect(api.saves, isEmpty);
        await finishPrices(t, owner, api);
      },
    );
  }

  for (final fail in [false, true]) {
    testWidgets(
      'independent dated order reply $fail stays outside resumed editor',
      (t) async {
        await setupSize(t);
        final api = HeldPurchaseApi()..fail = fail;
        final owner = BusinessSession(
          api: api,
          projectId: purchasing.projectId,
        );
        await owner.load();
        await t.pumpWidget(
          MaterialApp(
            home: Scaffold(body: BusinessPurchasingPage(session: owner)),
          ),
        );
        await t.pumpAndSettle();
        await priceTap(t, 'Bestellvorschlag anlegen');
        await t.enterText(
          find.byKey(const ValueKey('business-field-supplier_name')),
          'PRIVATE OLD SUPPLIER',
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
        await reviewClick(t, 'Vorschlag speichern');
        await t.enterText(
          find.byKey(const ValueKey('catalog-price-day')),
          '2026-11-30',
        );
        await reviewClick(t, 'Preisquellen prüfen');
        await reviewClick(t, 'Diesen Preis wählen');
        final posts = api.calls
            .where(
              (c) =>
                  c.path == '/api/business/inventory/orders' && c.body != null,
            )
            .toList();
        expect(posts, hasLength(1));
        expect(
          posts
              .single
              .body!['items'][0]['catalog_price_selection']['effective_on'],
          '2026-11-30',
        );
        t.binding.handleAppLifecycleStateChanged(AppLifecycleState.inactive);
        await t.pump();
        t.binding.handleAppLifecycleStateChanged(AppLifecycleState.resumed);
        api.reply.complete();
        await t.pumpAndSettle();
        expect(find.text('PRIVATE OLD SUPPLIER'), findsNothing);
        expect(find.textContaining('PRIVATE OLD ORDER RESPONSE'), findsNothing);
        expect(find.text('Vorschlag freigeben'), findsNothing);
        expect(api.saved, hasLength(1));
        expect(t.takeException(), isNull);
        if (fail) {
          final pendingKey =
              'purchase-proposal-${purchasing.projectId}-new-0-1';
          expect(owner.pending(pendingKey), true);
          api.inventoryWrite = false;
          await owner.load();
          await t.pumpAndSettle();
          expect(find.text('Bestellvorschlag anlegen'), findsNothing);
          expect(owner.pending(pendingKey), true);
          api.inventoryWrite = true;
          api.fail = false;
          await owner.load();
          await t.pumpAndSettle();
          await priceTap(t, 'Bestellvorschlag anlegen');
          final supplier = t.widget<TextFormField>(
            find.byKey(const ValueKey('business-field-supplier_name')),
          );
          expect(supplier.controller!.text, 'PRIVATE OLD SUPPLIER');
          expect(supplier.enabled, false);
          await priceTap(t, 'Erneut senden');
          final repeated = api.calls
              .where(
                (call) =>
                    call.path == '/api/business/inventory/orders' &&
                    call.body != null,
              )
              .toList();
          expect(repeated, hasLength(2));
          expect(repeated.last.body, repeated.first.body);
          expect(api.prices.candidateCalls, hasLength(2));
          expect(api.saved, hasLength(1));
          expect(owner.pending(pendingKey), false);
        }
        await t.pumpWidget(const SizedBox.shrink());
        await t.pumpAndSettle();
        owner.dispose();
        api.dispose();
      },
    );
  }
}

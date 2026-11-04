import 'dart:async';
import 'dart:convert';
import 'dart:io';
import 'dart:typed_data';

import 'package:file_selector/file_selector.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:smartplan_office/api.dart';
import 'package:smartplan_office/business_catalog_prices.dart';
import 'package:smartplan_office/business_session.dart';
import 'package:smartplan_office/mail_attachment_widgets.dart';

Map<String, dynamic> priceCopy(dynamic value) =>
    Map<String, dynamic>.from(jsonDecode(jsonEncode(value)));
final priceFixture = priceCopy(
  jsonDecode(File('test/fixtures/catalog_prices_v2.json').readAsStringSync()),
);

class PriceApi extends OfficeApi {
  PriceApi() : super(apiVersion: 'v1') {
    token = 'synthetic-price-session';
  }
  bool read = true,
      write = true,
      manage = true,
      enabled = true,
      installed = true,
      applied = false,
      withdrawn = false;
  int generation = 1;
  int? loseImport, loseApply, loseSource, loseWithdraw;
  Completer<dynamic>? holdCandidates,
      holdPreview,
      holdImport,
      holdApply,
      holdDetail;
  Completer<Uint8List>? holdOriginal;
  final commands = <Map<String, dynamic>>[],
      candidateCalls = <Map<String, dynamic>>[],
      previews = <Map<String, dynamic>>[];
  final effects = <String>{};
  Map<String, dynamic> get source => priceCopy(priceFixture['source']);
  Map<String, dynamic> get article => priceCopy(priceFixture['article']);
  String get sourceId => source['id'];
  String get importId => priceFixture['staged']['id'];
  String get priceId => priceFixture['application']['prices'][0]['price_id'];
  Map<String, dynamic> get detail =>
      priceCopy(priceFixture[applied ? 'applied_detail' : 'detail']);
  @override
  Future<dynamic> call(String path, [Map<String, dynamic>? body]) async {
    if (path.startsWith('/api/business/capabilities'))
      return {
        'compatibility_mode': 'business',
        'generation': generation,
        'readonly': false,
        'capabilities': [
          'business_documents',
          'business_adapters',
          'business_purchasing',
          if (installed) 'business_catalog_prices',
        ],
        'features': [
          'organization_modules',
          'quote_pricing',
          'purchasing_catalog',
          'purchasing_receipts',
          if (installed) 'catalog_prices_v2',
        ],
        'permissions': [
          'inventory.read',
          'inventory.write',
          'finance.approve',
          if (read) 'finance.read',
          if (write) 'finance.write',
          if (manage) 'settings.manage',
        ],
        'organization': {
          'revision': 1,
          'configured': true,
          'modules': {
            for (final section in BusinessSession.organizationSections)
              section: {
                'visible': true,
                'enabled': section != 'documents' || enabled,
              },
          },
        },
      };
    if (path == '/api/business/articles')
      return {
        'items': [article],
      };
    if (path == '/api/business/catalog-prices/sources') {
      if (body == null)
        return {
          'items': [source],
          'profile': 'catalog_csv_v2',
        };
      commands.add({'path': path, 'body': priceCopy(body)});
      effects.add(body['request_id']);
      if (loseSource != null) {
        final status = loseSource!;
        loseSource = null;
        throw ApiException(status, 'Synthetic lost source ACK');
      }
      return source;
    }
    if (path == '/api/business/catalog-prices/sources/$sourceId/imports') {
      commands.add({'path': path, 'body': priceCopy(body)});
      effects.add(body!['request_id']);
      if (holdImport != null) return await holdImport!.future;
      if (loseImport != null) {
        final status = loseImport!;
        loseImport = null;
        throw ApiException(status, 'Synthetic lost import ACK');
      }
      return priceCopy(priceFixture['staged']);
    }
    if (path.startsWith(
      '/api/business/catalog-prices/sources/$sourceId/imports?',
    )) {
      final value = priceCopy(priceFixture['history']);
      value['items'][0]['status'] = applied ? 'applied' : 'staged';
      return value;
    }
    if (path == '/api/business/catalog-prices/imports/$importId')
      return holdDetail == null ? detail : await holdDetail!.future;
    if (path == '/api/business/catalog-prices/imports/$importId/preview') {
      previews.add(priceCopy(body));
      return holdPreview == null
          ? priceCopy(priceFixture['preview'])
          : await holdPreview!.future;
    }
    if (path == '/api/business/catalog-prices/imports/$importId/apply') {
      commands.add({'path': path, 'body': priceCopy(body)});
      effects.add(body!['request_id']);
      applied = true;
      if (holdApply != null) return await holdApply!.future;
      if (loseApply != null) {
        final status = loseApply!;
        loseApply = null;
        throw ApiException(status, 'Synthetic lost apply ACK');
      }
      return priceCopy(priceFixture['application']);
    }
    if (path == '/api/business/catalog-prices/prices/$priceId/history')
      return priceCopy(
        priceFixture[withdrawn ? 'withdrawn_history' : 'price_history'],
      );
    if (path == '/api/business/catalog-prices/prices/$priceId/withdraw') {
      commands.add({'path': path, 'body': priceCopy(body)});
      effects.add(body!['request_id']);
      withdrawn = true;
      if (loseWithdraw != null) {
        final status = loseWithdraw!;
        loseWithdraw = null;
        throw ApiException(status, 'Synthetic lost withdrawal ACK');
      }
      return priceCopy(priceFixture['withdrawn']);
    }
    if (path == '/api/business/catalog-prices/candidates') {
      candidateCalls.add(priceCopy(body));
      if (holdCandidates != null) return await holdCandidates!.future;
      return priceCopy(
        body!['price_role'] == 'purchase_net'
            ? priceFixture['purchase_candidates']
            : priceFixture['candidates'][body['effective_on']],
      );
    }
    throw StateError('Unexpected price API call: $path');
  }

  @override
  Future<Uint8List> bytes(
    String path, {
    required String mediaType,
    int maxBytes = 20 * 1024 * 1024,
  }) async {
    expect(path, '/api/business/catalog-prices/imports/$importId/original');
    expect(mediaType, 'application/octet-stream');
    expect(maxBytes, 2097152);
    return holdOriginal == null
        ? base64Decode(priceFixture['original_base64'])
        : await holdOriginal!.future;
  }
}

Future<BusinessSession> mountPrices(
  WidgetTester tester,
  PriceApi api, {
  BusinessSession? session,
  bool picker = false,
  Future<XFile?> Function()? filePicker,
  MailAttachmentExporter? exporter,
}) async {
  final owner = session ?? BusinessSession(api: api);
  await owner.load();
  await tester.pumpWidget(
    MaterialApp(
      home: picker
          ? Scaffold(
              body: CatalogPricePicker(
                session: owner,
                article: api.article,
                role: 'sales_net',
              ),
            )
          : BusinessCatalogPricesPage(
              session: owner,
              picker:
                  filePicker ??
                  () async => XFile.fromData(
                    base64Decode(priceFixture['original_base64']),
                    path: 'synthetic-v2.csv',
                  ),
              exporter: exporter,
            ),
    ),
  );
  await tester.pumpAndSettle();
  return owner;
}

Future<void> priceTap(WidgetTester tester, String text) async {
  final found = find.text(text);
  if (found.evaluate().isEmpty) {
    tester
        .state<ScrollableState>(find.byType(Scrollable).first)
        .position
        .jumpTo(0);
    await tester.pump();
  }
  if (found.evaluate().isEmpty)
    await tester.scrollUntilVisible(
      found,
      220,
      scrollable: find.byType(Scrollable).first,
    );
  await Scrollable.ensureVisible(tester.element(found.first), alignment: 0.5);
  await tester.pumpAndSettle();
  await tester.tap(found.first);
  await tester.pumpAndSettle();
}

Future<void> openPriceRun(WidgetTester tester, PriceApi api) async {
  await priceTap(tester, api.source['name']);
  await priceTap(
    tester,
    '${priceFixture['staged']['catalog_revision']} · synthetic-v2.csv',
  );
}

Future<void> finishPrices(
  WidgetTester tester,
  BusinessSession session,
  PriceApi api,
) async {
  await tester.pumpWidget(const SizedBox.shrink());
  await tester.pumpAndSettle();
  session.dispose();
  api.dispose();
}

void main() {
  test(
    'actual original fixture keeps dated rows and canonical bound previews',
    () async {
      final result = await catalogPricePreview(
        priceCopy(priceFixture['detail']),
        priceCopy(priceFixture['decisions']),
        priceFixture['preview'],
      );
      expect(result, priceFixture['preview']);
      final correction = await catalogPricePreview(
        priceCopy(priceFixture['correction_detail']),
        priceCopy(priceFixture['correction_decisions']),
        priceFixture['correction_preview'],
      );
      expect(correction['ready'], true);
      for (final key in [
        'source_id',
        'import_id',
        'original_sha256',
        'rows_sha256',
        'preview_sha256',
      ]) {
        final value = priceCopy(priceFixture['preview']);
        value[key] = 'f' * 64;
        await expectLater(
          catalogPricePreview(
            priceCopy(priceFixture['detail']),
            priceCopy(priceFixture['decisions']),
            value,
          ),
          throwsA(isA<ApiException>()),
        );
      }
    },
  );
  test('November and December candidates retain raw amount and explicit date without a default', () {
    for (final day in ['2026-11-30', '2026-12-01']) {
      final choices = catalogPriceCandidates(
        priceFixture['candidates'][day],
        articleId: priceFixture['article']['id'],
        role: 'sales_net',
        day: day,
      );
      expect(
        choices
            .where((item) => item.value['status'] == 'eligible')
            .single
            .price['price_net'],
        day == '2026-11-30' ? '10.00' : '12.00',
      );
    }
    final purchase = catalogPriceCandidates(
      priceFixture['purchase_candidates'],
      articleId: priceFixture['article']['id'],
      role: 'purchase_net',
      day: '2026-11-30',
    ).single;
    expect(purchase.price['price_net'], '1.00');
    expect(purchase.price['price_base_quantity'], '3');
    for (final day in ['', '2026-02-29', '2026-04-31', '26-11-04'])
      expect(() => catalogPriceDay(day), throwsFormatException);
  });
  for (final status in [0, 403, 404, 409])
    test(
      'catalog v2 lost ACK $status retains exact request through generation refresh',
      () async {
        final api = PriceApi()..loseImport = status;
        final session = BusinessSession(api: api);
        await session.load();
        final key = 'catalog-v2-import-${api.sourceId}',
            body = {
              'catalog_revision': priceFixture['staged']['catalog_revision'],
              'filename': 'synthetic-v2.csv',
              'content_base64': priceFixture['original_base64'],
            };
        await expectLater(
          session.command(
            key,
            '/catalog-prices/sources/${api.sourceId}/imports',
            body,
          ),
          throwsA(isA<ApiException>()),
        );
        api.generation++;
        await session.repeatCatalogPricesCommand(key);
        expect(api.commands[0], api.commands[1]);
        expect(api.effects.length, 1);
        session.dispose();
        api.dispose();
      },
    );
  testWidgets(
    'selector starts with blank date, shows exact source and never chooses automatically',
    (tester) async {
      final api = PriceApi();
      final session = await mountPrices(tester, api, picker: true);
      expect(
        tester
            .widget<TextField>(find.byKey(const ValueKey('catalog-price-day')))
            .controller!
            .text,
        '',
      );
      expect(api.candidateCalls, isEmpty);
      await tester.enterText(
        find.byKey(const ValueKey('catalog-price-day')),
        '2026-11-30',
      );
      await priceTap(tester, 'Preisquellen prüfen');
      expect(find.textContaining('10.00 EUR / 1 ST'), findsOneWidget);
      expect(find.textContaining('12.00 EUR / 1 ST'), findsOneWidget);
      expect(find.text('Diesen Preis wählen'), findsOneWidget);
      await tester.enterText(
        find.byKey(const ValueKey('catalog-price-day')),
        '2026-12-01',
      );
      await tester.pump();
      expect(find.textContaining('10.00 EUR / 1 ST'), findsNothing);
      await priceTap(tester, 'Preisquellen prüfen');
      expect(find.textContaining('12.00 EUR / 1 ST'), findsOneWidget);
      expect(api.commands, isEmpty);
      await finishPrices(tester, session, api);
    },
  );
  testWidgets(
    'server-bound native preview requires explicit acceptance and exports original bytes',
    (tester) async {
      final api = PriceApi();
      Uint8List? exported;
      final session = await mountPrices(
        tester,
        api,
        exporter: (_, file, allowed) async {
          expect(allowed(), true);
          exported = file.bytes;
          return MailAttachmentExportResult.saved;
        },
      );
      await openPriceRun(tester, api);
      await priceTap(
        tester,
        'Vorhandene Bindungen und Neuanlagen als Vorschlag einsetzen',
      );
      await priceTap(tester, 'Verbindliche Preisvorschau laden');
      expect(api.previews.single, priceFixture['decisions']);
      expect(api.commands, isEmpty);
      await priceTap(tester, 'Preise ausdrücklich übernehmen');
      expect(api.commands, isEmpty);
      await priceTap(
        tester,
        'Original, Bindungen, Gültigkeiten und Preisänderungen vollständig geprüft',
      );
      await priceTap(tester, 'Preise ausdrücklich übernehmen');
      expect(api.commands.length, 1);
      expect(api.applied, true);
      await priceTap(tester, 'Original herunterladen');
      expect(exported, base64Decode(priceFixture['original_base64']));
      await finishPrices(tester, session, api);
    },
  );
  for (final change in ['read', 'write', 'module', 'generation', 'background'])
    testWidgets('late catalog preview cannot refill after $change loss', (
      tester,
    ) async {
      final api = PriceApi()..holdPreview = Completer<dynamic>();
      final session = await mountPrices(tester, api);
      await openPriceRun(tester, api);
      await priceTap(
        tester,
        'Vorhandene Bindungen und Neuanlagen als Vorschlag einsetzen',
      );
      await tester.ensureVisible(find.text('Verbindliche Preisvorschau laden'));
      await tester.tap(find.text('Verbindliche Preisvorschau laden'));
      await tester.pump();
      if (change == 'read') api.read = false;
      if (change == 'write') api.write = false;
      if (change == 'module') api.enabled = false;
      if (change == 'generation') api.generation++;
      if (change == 'background') {
        tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.paused);
        await tester.pump();
        tester.binding.handleAppLifecycleStateChanged(
          AppLifecycleState.resumed,
        );
      } else {
        await session.load();
      }
      api.holdPreview!.completeError(
        const ApiException(409, 'OLD PRIVATE PRICE ERROR'),
      );
      await tester.pumpAndSettle();
      expect(find.textContaining('OLD PRIVATE'), findsNothing);
      expect(
        find.text(
          'Original, Bindungen, Gültigkeiten und Preisänderungen vollständig geprüft',
        ),
        findsNothing,
      );
      await finishPrices(tester, session, api);
    });
  testWidgets(
    'lost apply ACK reopens applied original and repeats exact old command',
    (tester) async {
      final api = PriceApi()..loseApply = 0;
      final session = await mountPrices(tester, api);
      await openPriceRun(tester, api);
      await priceTap(
        tester,
        'Vorhandene Bindungen und Neuanlagen als Vorschlag einsetzen',
      );
      await priceTap(tester, 'Verbindliche Preisvorschau laden');
      await priceTap(
        tester,
        'Original, Bindungen, Gültigkeiten und Preisänderungen vollständig geprüft',
      );
      await priceTap(tester, 'Preise ausdrücklich übernehmen');
      expect(session.pending('catalog-v2-apply-${api.importId}'), true);
      await tester.pumpWidget(const SizedBox.shrink());
      await tester.pumpAndSettle();
      await mountPrices(tester, api, session: session);
      await openPriceRun(tester, api);
      await priceTap(tester, 'Ursprüngliche Preisannahme erneut prüfen');
      expect(api.commands[0], api.commands[1]);
      expect(api.effects.length, 1);
      await finishPrices(tester, session, api);
    },
  );
  testWidgets('native catalog layout fits 390 pixels', (tester) async {
    tester.view.physicalSize = const Size(390, 844);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    final api = PriceApi();
    final session = await mountPrices(tester, api);
    await openPriceRun(tester, api);
    expect(tester.takeException(), isNull);
    await finishPrices(tester, session, api);
  });
}

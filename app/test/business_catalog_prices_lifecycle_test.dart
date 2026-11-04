import 'dart:async';
import 'dart:convert';
import 'dart:typed_data';

import 'package:file_selector/file_selector.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:smartplan_office/api.dart';
import 'package:smartplan_office/business_catalog_prices.dart';
import 'package:smartplan_office/business_session.dart';
import 'package:smartplan_office/mail_attachment_widgets.dart';

import 'business_catalog_prices_test.dart';

class TwinSourcesApi extends PriceApi {
  @override
  Future<dynamic> call(String path, [Map<String, dynamic>? body]) async {
    if (path.endsWith('/catalog-prices/candidates'))
      return priceCopy(priceFixture['twin_candidates']);
    return super.call(path, body);
  }
}

class CorrectionApi extends PriceApi {
  @override
  String get importId => priceFixture['correction_detail']['id'];
  @override
  Map<String, dynamic> get detail =>
      priceCopy(priceFixture['correction_detail']);
  @override
  Future<dynamic> call(String path, [Map<String, dynamic>? body]) async {
    if (path.contains('/sources/$sourceId/imports?'))
      return {
        'items': [detail],
        'offset': 0,
        'limit': 20,
        'total': 1,
      };
    if (path.endsWith('/imports/$importId/preview')) {
      previews.add(priceCopy(body));
      return priceCopy(
        priceFixture[(body!['replacements'] as Map).isEmpty
            ? 'correction_required'
            : 'correction_preview'],
      );
    }
    return super.call(path, body);
  }
}

Future<void> pickOriginal(WidgetTester t, PriceApi api) async {
  await priceTap(t, api.source['name']);
  await priceTap(t, 'CSV-v2-Original auswählen');
  await t.enterText(
    find.byKey(const ValueKey('business-field-catalog_revision')),
    priceFixture['staged']['catalog_revision'],
  );
  await t.tap(find.widgetWithText(FilledButton, 'Speichern'));
  await t.pump();
}

void main() {
  testWidgets(
    'real equal-named sources remain distinguishable by evidence reference at 390 pixels',
    (t) async {
      t.view.physicalSize = const Size(390, 844);
      t.view.devicePixelRatio = 1;
      addTearDown(t.view.resetPhysicalSize);
      addTearDown(t.view.resetDevicePixelRatio);
      final api = TwinSourcesApi();
      final owner = await mountPrices(t, api, picker: true);
      await t.enterText(
        find.byKey(const ValueKey('catalog-price-day')),
        '2026-11-30',
      );
      await priceTap(t, 'Preisquellen prüfen');
      final choices = catalogPriceCandidates(
        priceFixture['twin_candidates'],
        articleId: api.article['id'],
        role: 'sales_net',
        day: '2026-11-30',
      ).where((item) => item.value['status'] == 'eligible').toList();
      expect(choices, hasLength(2));
      expect(
        choices.map((item) => item.value['source_name']).toSet(),
        hasLength(1),
      );
      expect(choices.map((item) => item.sourceLabel).toSet(), hasLength(2));
      for (final choice in choices)
        expect(find.text(choice.label), findsOneWidget);
      expect(t.takeException(), isNull);
      await finishPrices(t, owner, api);
    },
  );
  test('32 MiB is scoped to exact v2 catalog JSON routes', () {
    final id = 'a' * 32;
    for (final suffix in [
      'sources/$id/imports',
      'imports/$id',
      'imports/$id/preview',
      'imports/$id/apply',
      'candidates',
      'prices/$id/history',
    ]) {
      expect(
        officeJsonResponseLimit('/api/business/catalog-prices/$suffix'),
        32 * 1024 * 1024,
      );
      expect(
        officeJsonResponseLimit('/api/v1/business/catalog-prices/$suffix'),
        32 * 1024 * 1024,
      );
    }
    for (final suffix in [
      'sources',
      'imports/$id/original',
      'prices/$id/withdraw',
      'imports/$id/preview/extra',
      'imports/wrong',
      'unknown',
    ])
      expect(
        officeJsonResponseLimit('/api/business/catalog-prices/$suffix'),
        20 * 1024 * 1024,
      );
    expect(officeJsonResponseLimit('/api/business/articles'), 20 * 1024 * 1024);
  });
  testWidgets(
    'correction requires explicit acknowledgement before server re-preview',
    (t) async {
      final api = CorrectionApi();
      final session = await mountPrices(t, api);
      await priceTap(t, api.source['name']);
      await priceTap(
        t,
        '${api.detail['catalog_revision']} · ${api.detail['original']['filename']}',
      );
      await priceTap(
        t,
        'Vorhandene Bindungen und Neuanlagen als Vorschlag einsetzen',
      );
      await priceTap(t, 'Verbindliche Preisvorschau laden');
      expect(api.previews.single['replacements'], isEmpty);
      expect(api.commands, isEmpty);
      expect(
        find.text(
          'Original, Bindungen, Gültigkeiten und Preisänderungen vollständig geprüft',
        ),
        findsNothing,
      );
      await priceTap(
        t,
        'Diese Korrekturen ausdrücklich bestätigen und erneut prüfen',
      );
      expect(api.previews.last, priceFixture['correction_decisions']);
      expect(api.commands, isEmpty);
      expect(
        find.text(
          'Original, Bindungen, Gültigkeiten und Preisänderungen vollständig geprüft',
        ),
        findsOneWidget,
      );
      await finishPrices(t, session, api);
    },
  );
  testWidgets(
    'real file picker import retries identical original after lost ACK and reopening',
    (t) async {
      var picks = 0;
      final api = PriceApi()..loseImport = 0;
      final session = await mountPrices(
        t,
        api,
        filePicker: () async {
          picks++;
          return XFile.fromData(
            base64Decode(priceFixture['original_base64']),
            path: 'synthetic-v2.csv',
          );
        },
      );
      await pickOriginal(t, api);
      await t.pumpAndSettle();
      expect(api.commands, hasLength(1));
      await t.pumpWidget(const SizedBox.shrink());
      await t.pumpAndSettle();
      await mountPrices(
        t,
        api,
        session: session,
        filePicker: () async {
          picks++;
          throw StateError('must not repick');
        },
      );
      await priceTap(t, api.source['name']);
      await priceTap(t, 'Ursprünglichen Dateiimport erneut prüfen');
      expect(api.commands[0], api.commands[1]);
      expect(picks, 1);
      expect(api.effects, hasLength(1));
      await finishPrices(t, session, api);
    },
  );
  for (final change in [
    'background',
    'session',
    'read',
    'write',
    'module',
    'generation',
  ])
    testWidgets('late selected original is discarded after $change', (t) async {
      final file = Completer<XFile?>(), api = PriceApi();
      final session = await mountPrices(t, api, filePicker: () => file.future);
      await pickOriginal(t, api);
      await t.pump();
      BusinessSession? other;
      PriceApi? otherApi;
      if (change == 'session') {
        otherApi = PriceApi();
        other = BusinessSession(api: otherApi);
        await mountPrices(t, otherApi, session: other);
      } else if (change == 'background') {
        t.binding.handleAppLifecycleStateChanged(AppLifecycleState.inactive);
        await t.pump();
        t.binding.handleAppLifecycleStateChanged(AppLifecycleState.resumed);
      } else {
        if (change == 'read') api.read = false;
        if (change == 'write') api.write = false;
        if (change == 'module') api.enabled = false;
        if (change == 'generation') api.generation++;
        await session.load();
      }
      file.complete(
        XFile.fromData(
          base64Decode(priceFixture['original_base64']),
          path: 'synthetic-v2.csv',
        ),
      );
      await t.pumpAndSettle();
      expect(api.commands, isEmpty);
      expect(find.textContaining('Originalrevision benennen'), findsNothing);
      await finishPrices(t, session, api);
      other?.dispose();
      otherApi?.dispose();
    });
  for (final lateError in [false, true])
    for (final change in [
      'session',
      'article',
      'background',
      'generation',
      'read',
      'write',
    ])
      testWidgets(
        'candidate $lateError response cannot reopen stale $change context',
        (t) async {
          final api = PriceApi()..holdCandidates = Completer<dynamic>();
          final session = await mountPrices(t, api, picker: true);
          await t.enterText(
            find.byKey(const ValueKey('catalog-price-day')),
            '2026-11-30',
          );
          await t.tap(find.text('Preisquellen prüfen'));
          await t.pump();
          BusinessSession? other;
          PriceApi? otherApi;
          if (change == 'session') {
            otherApi = PriceApi();
            other = BusinessSession(api: otherApi);
            await mountPrices(t, otherApi, session: other, picker: true);
          } else if (change == 'article') {
            await t.pumpWidget(
              MaterialApp(
                home: Scaffold(
                  body: CatalogPricePicker(
                    session: session,
                    article: {...api.article, 'id': 'f' * 32},
                    role: 'sales_net',
                  ),
                ),
              ),
            );
          } else if (change == 'background') {
            t.binding.handleAppLifecycleStateChanged(
              AppLifecycleState.inactive,
            );
            await t.pump();
            t.binding.handleAppLifecycleStateChanged(AppLifecycleState.resumed);
          } else {
            if (change == 'generation') api.generation++;
            if (change == 'read') api.read = false;
            if (change == 'write') api.write = false;
            await session.load();
          }
          if (lateError)
            api.holdCandidates!.completeError(
              const ApiException(409, 'OLD PRICE PERSON ERROR'),
            );
          else
            api.holdCandidates!.complete(
              priceCopy(priceFixture['candidates']['2026-11-30']),
            );
          await t.pumpAndSettle();
          expect(find.textContaining('OLD PRICE PERSON'), findsNothing);
          expect(find.text('Diesen Preis wählen'), findsNothing);
          expect(api.commands, isEmpty);
          await finishPrices(t, session, api);
          other?.dispose();
          otherApi?.dispose();
        },
      );
  testWidgets('tampered original cannot export bytes', (t) async {
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
    await t.tap(find.text('Original herunterladen'));
    await t.pump();
    api.holdOriginal!.complete(Uint8List.fromList([0, 1, 2]));
    await t.pumpAndSettle();
    expect(exports, 0);
    expect(find.textContaining('Originalbytes stimmen nicht'), findsOneWidget);
    await finishPrices(t, session, api);
  });
  testWidgets(
    'withdrawal keeps exact original revision on replay of lost ACK',
    (t) async {
      final api = PriceApi()
        ..applied = true
        ..loseWithdraw = 0;
      final session = await mountPrices(t, api);
      await openPriceRun(t, api);
      await priceTap(t, 'Preisverlauf · ${api.priceId} · Revision 1');
      await priceTap(t, 'Preis ausdrücklich zurücknehmen');
      await t.enterText(
        find.byKey(const ValueKey('business-field-reason')),
        'Synthetische Rücknahme',
      );
      await priceTap(t, 'Diese Preisquelle für neue Auswahlen zurücknehmen');
      await priceTap(t, 'Speichern');
      expect(api.commands, hasLength(1));
      await priceTap(t, 'Erneut senden');
      expect(api.commands[0], api.commands[1]);
      expect(api.commands[1]['body']['revision'], 1);
      expect(api.effects, hasLength(1));
      await finishPrices(t, session, api);
    },
  );
}

import 'dart:async';
import 'dart:convert';
import 'dart:io';
import 'dart:typed_data';

import 'package:file_selector/file_selector.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:smartplan_office/api.dart';
import 'package:smartplan_office/business_adapters.dart';
import 'package:smartplan_office/business_catalog_imports.dart';
import 'package:smartplan_office/business_session.dart';
import 'package:smartplan_office/mail_attachment_widgets.dart';

import 'backend_integration_test.dart' show BackendHttp;
import 'import_backend_integration_test.dart' show fixture;

final catalogFixtures = Map<String, dynamic>.from(
  jsonDecode(
    File('../web/office/tests/fixtures/catalog-import-previews.json')
        .readAsStringSync(),
  ),
);
Map<String, dynamic> cloneCatalog(Object? value) =>
    Map<String, dynamic>.from(jsonDecode(jsonEncode(value)));
Map<String, dynamic> catalogFixture([String name = 'csv_create']) =>
    cloneCatalog(
      (catalogFixtures['cases'] as List).firstWhere(
        (item) => item['name'] == name,
      ),
    );
final catalogBytes = Uint8List.fromList(
  utf8.encode(
    'code;name;unit;cost_price_net;unit_price_net;tax_rate\r\nSYN-17;Synthetic valve;ST;12.50;20.00;19\r\n',
  ),
);
Future<XFile?> catalogPicker() async =>
    XFile.fromData(catalogBytes, path: 'synthetic.csv', name: 'synthetic.csv');

class CatalogApi extends OfficeApi {
  CatalogApi({String caseName = 'csv_create'})
    : fixture = catalogFixture(caseName),
      super(apiVersion: 'v1') {
    token = 'synthetic-native-catalog-session';
  }
  final Map<String, dynamic> fixture;
  bool readable = true,
      writable = true,
      enabled = true,
      installed = true,
      readonly = false,
      hasRun = true,
      applied = false;
  int generation = 1;
  int? loseImport, loseApply;
  Completer<dynamic>? holdPreview, holdImport, holdDetail, holdApply;
  final otherAdapters = <String>{};
  Completer<Uint8List>? holdOriginal;
  Uint8List? alteredOriginal;
  final posts = <Map<String, dynamic>>[],
      calls = <String>[],
      previews = <Map<String, dynamic>>[],
      effects = <String>{};
  String get adapterId => fixture['run']['adapter_id'];
  String get runId => fixture['run']['id'];
  Map<String, dynamic> get adapter => {
    'id': adapterId,
    'name': 'Synthetic native catalog',
    'profile': fixture['run']['profile'],
    'enabled': true,
    'profile_info': {
      'import': true,
      'export': true,
      'label': 'Synthetic catalog profile',
      'scope': 'Synthetic local file',
    },
  };
  Map<String, dynamic> get currentRun => {
    ...cloneCatalog(fixture['run']),
    if (applied) 'status': 'applied',
    if (applied)
      'result': {
        'article_ids': ['c' * 32],
      },
  };
  @override
  Future<dynamic> call(String path, [Map<String, dynamic>? body]) async {
    calls.add(path);
    if (path.startsWith('/api/business/capabilities'))
      return {
        'compatibility_mode': readonly ? 'legacy' : 'business',
        'generation': generation,
        'readonly': readonly,
        'capabilities': [
          'business_adapters',
          if (installed) 'business_catalog_imports',
        ],
        'features': ['catalog_import_history', 'organization_modules'],
        'permissions': [
          'settings.manage',
          if (readable) 'finance.read',
          if (writable) 'finance.write',
        ],
        'organization': {
          'revision': 1,
          'configured': true,
          'modules': {
            for (final area in BusinessSession.organizationSections)
              area: {
                'visible': true,
                'enabled': area != 'documents' || enabled,
              },
          },
        },
      };
    if (path == '/api/business/adapters')
      return {
        'items': [adapter],
        'profiles': [],
        'suppliers': [],
      };
    if (path == '/api/business/adapters/$adapterId') return adapter;
    for (final other in otherAdapters) {
      if (path.startsWith('/api/business/adapters/$other/imports?'))
        return {'offset': 0, 'limit': 20, 'total': 0, 'items': []};
    }
    if (path.startsWith('/api/business/adapters/$adapterId/imports?')) {
      final offset = int.parse(
        Uri.parse(path).queryParameters['offset'] ?? '0',
      );
      return {
        'offset': offset,
        'limit': 20,
        'total': hasRun ? 1 : 0,
        'items': [
          if (hasRun && offset == 0) {...currentRun, 'row_count': 1},
        ],
      };
    }
    if (path == '/api/business/adapters/imports/$runId')
      return holdDetail == null ? currentRun : await holdDetail!.future;
    if (path == '/api/business/adapters/imports/$runId/catalog-preview') {
      previews.add(cloneCatalog(body));
      return holdPreview == null
          ? cloneCatalog(fixture['preview'])
          : await holdPreview!.future;
    }
    if (path == '/api/business/adapters/$adapterId/import') {
      posts.add({'path': path, 'body': cloneCatalog(body)});
      effects.add(body!['request_id']);
      hasRun = true;
      if (holdImport != null) return await holdImport!.future;
      if (loseImport != null) {
        final status = loseImport!;
        loseImport = null;
        throw ApiException(status, 'Synthetische unbestätigte Importantwort.');
      }
      return currentRun;
    }
    if (path == '/api/business/adapters/imports/$runId/apply') {
      posts.add({'path': path, 'body': cloneCatalog(body)});
      effects.add(body!['request_id']);
      applied = true;
      if (holdApply != null) return await holdApply!.future;
      if (loseApply != null) {
        final status = loseApply!;
        loseApply = null;
        throw ApiException(status, 'Synthetische unbestätigte Annahmeantwort.');
      }
      return currentRun;
    }
    throw StateError('Unexpected catalog request: $path');
  }

  @override
  Future<Uint8List> bytes(
    String path, {
    required String mediaType,
    int maxBytes = 20 * 1024 * 1024,
  }) async {
    calls.add(path);
    expect(path, '/api/business/adapters/imports/$runId/original');
    expect(mediaType, 'application/octet-stream');
    expect(maxBytes, 2097152);
    return holdOriginal == null
        ? alteredOriginal ?? catalogBytes
        : await holdOriginal!.future;
  }
}

class CatalogHttpApi extends OfficeApi {
  CatalogHttpApi(String base) : super(baseUrl: base, apiVersion: 'v1');
  bool loseImport = true, loseApply = true;
  final commands = <Map<String, dynamic>>[];
  @override
  Future<dynamic> call(String path, [Map<String, dynamic>? body]) async {
    final importing =
            body != null &&
            RegExp(r'^/api/business/adapters/[a-f0-9]{32}/import$')
                .hasMatch(path),
        applying =
            body != null &&
            RegExp(r'^/api/business/adapters/imports/[a-f0-9]{32}/apply$')
                .hasMatch(path);
    if (importing || applying)
      commands.add({'path': path, 'body': cloneCatalog(body)});
    final result = await super.call(path, body);
    if (importing && loseImport) {
      loseImport = false;
      throw const ApiException(
        0,
        'Tatsächlich angenommener Import: Antwort verloren.',
      );
    }
    if (applying && loseApply) {
      loseApply = false;
      throw const ApiException(
        0,
        'Tatsächlich angenommene Artikelübernahme: Antwort verloren.',
      );
    }
    return result;
  }
}

Future<BusinessSession> mountCatalog(
  WidgetTester tester,
  CatalogApi api, {
  BusinessSession? session,
  Key? key,
  Future<XFile?> Function()? picker,
  MailAttachmentExporter? exporter,
  Map<String, dynamic>? adapter,
}) async {
  final owner = session ?? BusinessSession(api: api);
  await owner.load();
  await tester.pumpWidget(
    MaterialApp(
      home: BusinessCatalogImportsPage(
        key: key,
        session: owner,
        adapter: adapter ?? api.adapter,
        picker: picker ?? catalogPicker,
        exporter: exporter,
      ),
    ),
  );
  await tester.pumpAndSettle();
  return owner;
}

Future<void> tapCatalog(WidgetTester tester, String label) async {
  final found = find.text(label);
  await tester.ensureVisible(found);
  await tester.tap(found);
  await tester.pumpAndSettle();
}

Future<void> openCatalogRun(WidgetTester tester) async =>
    tapCatalog(tester, 'synthetic.csv');
Future<void> cleanCatalog(
  WidgetTester tester,
  BusinessSession session,
  CatalogApi api,
) async {
  await tester.pumpWidget(const SizedBox.shrink());
  session.dispose();
  api.dispose();
}

void main() {
  for (final item in catalogFixtures['cases']) {
    test('actual backend preview and digest: ${item['name']}', () async {
      final fixture = cloneCatalog(item),
          run = catalogRun(
            fixture['run'],
            adapterId: fixture['run']['adapter_id'],
          );
      final result = await catalogPreview(
        run,
        cloneCatalog(fixture['mapping']),
        fixture['preview'],
      );
      expect(result, fixture['preview']);
      if (fixture['name'] == 'csv_noop_preserves_unknown_cost') {
        expect(result['rows'][0]['action'], 'noop');
        expect(result['rows'][0]['after']['cost_known'], false);
      }
    });
  }
  test('preview rejects altered original, mapping, article revision, hash and forged exact price', () async {
    final fixture = catalogFixture('csv_update');
    for (final change in ['source', 'mapping', 'revision', 'hash', 'price']) {
      final preview = cloneCatalog(fixture['preview']);
      if (change == 'source') preview['source_sha256'] = 'd' * 64;
      if (change == 'mapping') preview['price_mapping'] = {'tax_rate': '7'};
      if (change == 'revision') preview['rows'][0]['revision']++;
      if (change == 'hash') preview['preview_sha256'] = 'd' * 64;
      if (change == 'price')
        preview['rows'][0]['after']['cost_price_net'] = '999';
      await expectLater(
        catalogPreview(cloneCatalog(fixture['run']), {}, preview),
        throwsA(isA<ApiException>()),
      );
    }
  });
  test('DATANORM is decimal exact and does not infer price scale or VAT', () {
    expect(
      catalogDatanormPrice({
        'source_price_integer': '15',
        'price_basis': '10',
      }, '0.0001'),
      '0.0002',
    );
    expect(
      catalogDatanormPrice({
        'source_price_integer': '99999999999999',
        'price_basis': '1000',
      }, '0.01'),
      '1000000000.0000',
    );
    for (final value in [null, '', '-1', '1e2', '0.00001']) {
      expect(() => catalogDecimal(value), throwsFormatException);
    }
    expect(
      () => catalogDatanormPrice({
        'source_price_integer': '15',
        'price_basis': '10',
      }, '0'),
      throwsFormatException,
    );
  });
  test('only exact catalog JSON paths receive a 32 MiB response allowance', () {
    final id = 'a' * 32;
    for (final path in [
      '/api/business/adapters/$id/import',
      '/api/v1/business/adapters/imports/$id',
      '/api/business/adapters/imports/$id/catalog-preview',
      '/api/business/adapters/imports/$id/apply',
    ]) {
      expect(officeJsonResponseLimit(path), 32 * 1024 * 1024);
    }
    for (final path in [
      '/api/business/adapters',
      '/api/business/adapters/$id/export',
      '/api/business/adapters/imports/$id/original',
      '/api/business/adapters/imports/$id/offer',
      '/api/business/articles',
    ]) {
      expect(officeJsonResponseLimit(path), 20 * 1024 * 1024);
    }
  });
  for (final status in [0, 403, 404, 409]) {
    test(
      'catalog command retains exact nonce on uncertain $status across a fresh generation',
      () async {
        final api = CatalogApi()..loseImport = status;
        final owner = BusinessSession(api: api);
        addTearDown(owner.dispose);
        addTearDown(api.dispose);
        await owner.load();
        final key = 'catalog-import-${api.adapterId}',
            path = '/adapters/${api.adapterId}/import',
            body = {
              'filename': 'synthetic.csv',
              'content_base64': base64Encode(catalogBytes),
            };
        await expectLater(
          owner.command(key, path, body),
          throwsA(isA<ApiException>()),
        );
        expect(owner.pending(key), true);
        api.generation++;
        await owner.repeatCatalogCommand(key);
        expect(api.posts[0], api.posts[1]);
        expect(api.effects.length, 1);
        expect(owner.pending(key), false);
      },
    );
  }
  for (final loss in ['read', 'write', 'module']) {
    test(
      'catalog replay verifies fresh $loss authority before another POST',
      () async {
        final api = CatalogApi()..loseImport = 0;
        final session = BusinessSession(api: api);
        addTearDown(session.dispose);
        addTearDown(api.dispose);
        await session.load();
        final key = 'catalog-import-${api.adapterId}';
        await expectLater(
          session.command(key, '/adapters/${api.adapterId}/import', {
            'content_base64': base64Encode(catalogBytes),
          }),
          throwsA(isA<ApiException>()),
        );
        if (loss == 'read') api.readable = false;
        if (loss == 'write') api.writable = false;
        if (loss == 'module') api.enabled = false;
        await expectLater(
          session.repeatCatalogCommand(key),
          throwsA(isA<ApiException>()),
        );
        expect(api.posts.length, 1);
        expect(session.pending(key), true);
      },
    );
  }
  testWidgets(
    'real file bytes, bound CSV preview, explicit confirmation, history and original export',
    (tester) async {
      final api = CatalogApi()..hasRun = false;
      VerifiedMailAttachment? exported;
      final session = await mountCatalog(
        tester,
        api,
        exporter: (_, original, mayExport) async {
          expect(mayExport(), true);
          exported = original;
          return MailAttachmentExportResult.saved;
        },
      );
      await tapCatalog(tester, 'Katalogdatei auswählen');
      expect(
        base64Decode(api.posts.single['body']['content_base64']),
        catalogBytes,
      );
      expect(api.posts.single['body']['filename'], 'synthetic.csv');
      expect(
        find.text('1 neu · 0 aktualisiert · 0 ohne Änderung'),
        findsOneWidget,
      );
      await tapCatalog(tester, 'Artikel ausdrücklich übernehmen');
      expect(api.posts.length, 1);
      await tester.ensureVisible(find.byType(CheckboxListTile));
      await tester.tap(find.byType(CheckboxListTile));
      await tester.pumpAndSettle();
      await tapCatalog(tester, 'Artikel ausdrücklich übernehmen');
      expect(api.posts.last['body']['confirmed'], true);
      expect(find.text('1 Artikel · Bereits übernommen'), findsOneWidget);
      await tapCatalog(tester, 'Original herunterladen');
      expect(exported!.bytes, catalogBytes);
      expect(exported!.sha256, api.currentRun['source_sha256']);
      await tapCatalog(tester, 'Zur Importhistorie');
      expect(find.text('synthetic.csv'), findsOneWidget);
      await cleanCatalog(tester, session, api);
    },
  );
  testWidgets(
    'lost import ACK survives page disposal with exact original request_id and bytes',
    (tester) async {
      final api = CatalogApi()
        ..hasRun = false
        ..loseImport = 0;
      final session = await mountCatalog(tester, api);
      await tapCatalog(tester, 'Katalogdatei auswählen');
      expect(session.pending('catalog-import-${api.adapterId}'), true);
      await tester.pumpWidget(const SizedBox.shrink());
      await mountCatalog(tester, api, session: session);
      await tapCatalog(tester, 'Ursprüngliche Importantwort erneut prüfen');
      expect(api.posts[0], api.posts[1]);
      expect(api.effects.length, 1);
      await cleanCatalog(tester, session, api);
    },
  );
  testWidgets(
    'lost acceptance ACK reopens applied history and repeats the identical confirmation',
    (tester) async {
      final api = CatalogApi()..loseApply = 0;
      final session = await mountCatalog(tester, api);
      await openCatalogRun(tester);
      await tester.ensureVisible(find.byType(CheckboxListTile));
      await tester.tap(find.byType(CheckboxListTile));
      await tester.pumpAndSettle();
      await tapCatalog(tester, 'Artikel ausdrücklich übernehmen');
      expect(session.pending('catalog-apply-${api.runId}'), true);
      await tester.pumpWidget(const SizedBox.shrink());
      await mountCatalog(tester, api, session: session);
      await openCatalogRun(tester);
      await tapCatalog(tester, 'Ursprüngliche Annahmeantwort erneut prüfen');
      expect(api.posts[0], api.posts[1]);
      expect(api.effects.length, 1);
      await cleanCatalog(tester, session, api);
    },
  );
  testWidgets(
    'existing no-op keeps unknown cost and does not promise a new article revision',
    (tester) async {
      final api = CatalogApi(caseName: 'csv_noop_preserves_unknown_cost');
      final owner = await mountCatalog(tester, api);
      await openCatalogRun(tester);
      expect(
        find.text('0 neu · 0 aktualisiert · 1 ohne Änderung'),
        findsOneWidget,
      );
      await tester.scrollUntilVisible(
        find.text('Einstand bekannt: Nein → Nein'),
        300,
        scrollable: find.byType(Scrollable).first,
      );
      expect(find.text('Einstand bekannt: Nein → Nein'), findsOneWidget);
      await cleanCatalog(tester, owner, api);
    },
  );
  testWidgets(
    'readonly and module-off retain genuine inspection without acceptance controls',
    (tester) async {
      final api = CatalogApi()
        ..writable = false
        ..enabled = false;
      final session = await mountCatalog(tester, api);
      await openCatalogRun(tester);
      expect(
        find.text('1 neu · 0 aktualisiert · 0 ohne Änderung'),
        findsOneWidget,
      );
      expect(find.byType(CheckboxListTile), findsNothing);
      expect(find.text('Artikel ausdrücklich übernehmen'), findsNothing);
      expect(api.previews, [{}]);
      await cleanCatalog(tester, session, api);
    },
  );
  for (final loss in ['write', 'module', 'read', 'generation']) {
    testWidgets(
      'late native server preview cannot refill after $loss changes',
      (tester) async {
        final api = CatalogApi()..holdPreview = Completer<dynamic>();
        final session = await mountCatalog(tester, api);
        await tester.tap(find.text('synthetic.csv'));
        await tester.pump();
        await tester.pump(const Duration(milliseconds: 50));
        expect(api.previews.length, 1);
        if (loss == 'write') api.writable = false;
        if (loss == 'module') api.enabled = false;
        if (loss == 'read') api.readable = false;
        if (loss == 'generation') api.generation++;
        await session.load();
        await tester.pump();
        api.holdPreview!.complete(cloneCatalog(api.fixture['preview']));
        await tester.pumpAndSettle();
        expect(find.text('Artikel ausdrücklich übernehmen'), findsNothing);
        expect(find.textContaining('Einkauf netto:'), findsNothing);
        expect(api.posts, isEmpty);
        await cleanCatalog(tester, session, api);
      },
    );
  }
  testWidgets(
    'session replacement detaches old listener and suppresses its late private error',
    (tester) async {
      final first = CatalogApi()..holdPreview = Completer<dynamic>(),
          second = CatalogApi()..hasRun = false;
      const key = ValueKey('same-catalog-state');
      final original = await mountCatalog(tester, first, key: key);
      await tester.tap(find.text('synthetic.csv'));
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 50));
      final replacement = await mountCatalog(
        tester,
        second,
        key: key,
        adapter: {...second.adapter, 'name': 'Second session source'},
      );
      first.holdPreview!.completeError(
        const ApiException(409, 'OLD PRIVATE CATALOG ERROR'),
      );
      first.readable = false;
      await original.load();
      await tester.pumpAndSettle();
      expect(find.text('Katalog · Second session source'), findsOneWidget);
      expect(find.textContaining('OLD PRIVATE'), findsNothing);
      expect(find.text('Katalogdatei auswählen'), findsOneWidget);
      original.dispose();
      first.dispose();
      await cleanCatalog(tester, replacement, second);
    },
  );
  for (final fail in [false, true]) {
    testWidgets(
      'background invalidates a late file picker ${fail ? 'error' : 'result'} before upload',
      (tester) async {
        final api = CatalogApi()..hasRun = false, picker = Completer<XFile?>();
        final session = await mountCatalog(
          tester,
          api,
          picker: () => picker.future,
        );
        await tester.tap(find.text('Katalogdatei auswählen'));
        await tester.pump();
        await tester.pump(const Duration(milliseconds: 50));
        tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.paused);
        await tester.pump();
        tester.binding.handleAppLifecycleStateChanged(
          AppLifecycleState.resumed,
        );
        await tester.pump();
        if (fail) {
          picker.completeError(
            const ApiException(400, 'OLD PRIVATE FILE ERROR'),
          );
        } else {
          picker.complete(await catalogPicker());
        }
        await tester.pumpAndSettle();
        expect(api.posts, isEmpty);
        expect(find.textContaining('OLD PRIVATE'), findsNothing);
        expect(find.text('Artikel ausdrücklich übernehmen'), findsNothing);
        await cleanCatalog(tester, session, api);
      },
    );
  }
  testWidgets('withdrawn original download cannot reach the native exporter', (
    tester,
  ) async {
    final api = CatalogApi()
      ..applied = true
      ..holdOriginal = Completer<Uint8List>();
    var exports = 0;
    final session = await mountCatalog(
      tester,
      api,
      exporter: (_, original, mayExport) async {
        exports++;
        return MailAttachmentExportResult.saved;
      },
    );
    await openCatalogRun(tester);
    await tester.ensureVisible(find.text('Original herunterladen'));
    await tester.tap(find.text('Original herunterladen'));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 50));
    api.readable = false;
    await session.load();
    api.holdOriginal!.complete(catalogBytes);
    await tester.pumpAndSettle();
    expect(exports, 0);
    await cleanCatalog(tester, session, api);
  });
  testWidgets('native catalog preview fits a 390-pixel viewport', (
    tester,
  ) async {
    tester.view.physicalSize = const Size(390, 844);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    final api = CatalogApi();
    final owner = await mountCatalog(tester, api);
    await openCatalogRun(tester);
    expect(tester.takeException(), isNull);
    await cleanCatalog(tester, owner, api);
  });
  testWidgets(
    'existing adapter page routes catalogs to evidence workflow and keeps GAEB import',
    (tester) async {
      final api = CatalogApi();
      final owner = BusinessSession(api: api);
      await owner.load();
      await tester.pumpWidget(
        MaterialApp(
          home: BusinessAdapterPage(
            session: owner,
            adapter: api.adapter,
            onConfigure: () async {},
          ),
        ),
      );
      await tester.pumpAndSettle();
      expect(find.text('Katalogimporte und Originale'), findsOneWidget);
      expect(find.text('Datei zur Prüfung einlesen'), findsNothing);
      expect(find.text('Prüfexport erstellen'), findsOneWidget);
      await tester.pumpWidget(
        MaterialApp(
          home: BusinessAdapterPage(
            session: owner,
            adapter: {
              ...api.adapter,
              'id': 'f' * 32,
              'profile': 'gaeb_x83_inspect_v1',
            },
            onConfigure: () async {},
          ),
        ),
      );
      await tester.pumpAndSettle();
      expect(find.text('Datei zur Prüfung einlesen'), findsOneWidget);
      expect(find.text('Katalogimporte und Originale'), findsNothing);
      await cleanCatalog(tester, owner, api);
    },
  );

  for (final phase in ['picker', 'preview', 'accept']) {
    for (final replacingSession in [false, true]) {
      testWidgets(
        '${replacingSession ? 'session' : 'adapter'} replacement while $phase is pending suppresses the late private error',
        (tester) async {
          final api = CatalogApi(), picker = Completer<XFile?>();
          if (phase == 'preview') api.holdPreview = Completer<dynamic>();
          if (phase == 'accept') api.holdApply = Completer<dynamic>();
          const key = ValueKey('replace-native-catalog');
          final owner = await mountCatalog(
            tester,
            api,
            key: key,
            picker: phase == 'picker' ? () => picker.future : catalogPicker,
          );
          if (phase == 'picker') {
            await tester.tap(find.text('Katalogdatei auswählen'));
          } else if (phase == 'preview') {
            await tester.tap(find.text('synthetic.csv'));
          } else {
            await openCatalogRun(tester);
            await tester.ensureVisible(find.byType(CheckboxListTile));
            await tester.tap(find.byType(CheckboxListTile));
            await tester.pumpAndSettle();
            await tester.ensureVisible(
              find.text('Artikel ausdrücklich übernehmen'),
            );
            await tester.tap(find.text('Artikel ausdrücklich übernehmen'));
          }
          await tester.pump();
          await tester.pump(const Duration(milliseconds: 50));
          CatalogApi? nextApi;
          BusinessSession? nextSession;
          if (replacingSession) {
            nextApi = CatalogApi()..hasRun = false;
            nextSession = await mountCatalog(
              tester,
              nextApi,
              key: key,
              adapter: {...nextApi.adapter, 'name': 'Replacement catalog'},
            );
          } else {
            final nextId = 'e' * 32;
            api.otherAdapters.add(nextId);
            await mountCatalog(
              tester,
              api,
              session: owner,
              key: key,
              adapter: {
                ...api.adapter,
                'id': nextId,
                'name': 'Replacement catalog',
              },
            );
          }
          final failure = const ApiException(
            409,
            'OLD PRIVATE NATIVE CATALOG ERROR',
          );
          if (phase == 'picker') picker.completeError(failure);
          if (phase == 'preview') api.holdPreview!.completeError(failure);
          if (phase == 'accept') api.holdApply!.completeError(failure);
          await tester.pumpAndSettle();
          expect(find.text('Katalog · Replacement catalog'), findsOneWidget);
          expect(find.textContaining('OLD PRIVATE'), findsNothing);
          expect(find.text('Artikel ausdrücklich übernehmen'), findsNothing);
          expect(find.text('Katalogdatei auswählen'), findsOneWidget);
          if (phase != 'accept') expect(api.posts, isEmpty);
          if (phase == 'accept')
            expect(owner.pending('catalog-apply-${api.runId}'), true);
          if (nextSession != null) {
            await cleanCatalog(tester, nextSession, nextApi!);
            owner.dispose();
            api.dispose();
          } else {
            await cleanCatalog(tester, owner, api);
          }
        },
      );
    }
  }
  testWidgets(
    'accepted original ACK after adapter replacement resolves only its captured command',
    (tester) async {
      final api = CatalogApi()..holdImport = Completer<dynamic>();
      const key = ValueKey('late-original-ack');
      final session = await mountCatalog(tester, api, key: key);
      await tester.tap(find.text('Katalogdatei auswählen'));
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 50));
      expect(api.posts.length, 1);
      final nextId = 'f' * 32;
      api.otherAdapters.add(nextId);
      await mountCatalog(
        tester,
        api,
        session: session,
        key: key,
        adapter: {...api.adapter, 'id': nextId, 'name': 'Next source'},
      );
      api.holdImport!.complete(api.currentRun);
      await tester.pumpAndSettle();
      expect(session.pending('catalog-import-${api.adapterId}'), false);
      expect(find.text('Katalog · Next source'), findsOneWidget);
      expect(find.text('Artikel ausdrücklich übernehmen'), findsNothing);
      await cleanCatalog(tester, session, api);
    },
  );
  testWidgets(
    'late preview failure after background does not reappear on resume',
    (tester) async {
      final api = CatalogApi()..holdPreview = Completer<dynamic>();
      final session = await mountCatalog(tester, api);
      await tester.tap(find.text('synthetic.csv'));
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 50));
      tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.paused);
      await tester.pump();
      tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.resumed);
      await tester.pump();
      api.holdPreview!.completeError(
        const ApiException(409, 'OLD PRIVATE PREVIEW ERROR'),
      );
      await tester.pumpAndSettle();
      expect(find.textContaining('OLD PRIVATE'), findsNothing);
      expect(find.text('Artikel ausdrücklich übernehmen'), findsNothing);
      await cleanCatalog(tester, session, api);
    },
  );
  testWidgets(
    'oversize file is rejected before a catalog import command exists',
    (tester) async {
      final api = CatalogApi()..hasRun = false;
      final session = await mountCatalog(
        tester,
        api,
        picker: () async =>
            XFile.fromData(Uint8List(1), path: 'oversize.csv', length: 2097153),
      );
      await tapCatalog(tester, 'Katalogdatei auswählen');
      expect(api.posts, isEmpty);
      expect(session.pending('catalog-import-${api.adapterId}'), false);
      expect(find.textContaining('2 MiB auswählen'), findsOneWidget);
      await cleanCatalog(tester, session, api);
    },
  );

  testWidgets(
    'DATANORM native mapping starts empty and requires a new preview after edits',
    (tester) async {
      await tester.binding.setSurfaceSize(const Size(1100, 1800));
      addTearDown(() => tester.binding.setSurfaceSize(null));
      final api = CatalogApi(caseName: 'datanorm_create_half_up');
      final session = await mountCatalog(tester, api);
      await openCatalogRun(tester);
      expect(api.previews, isEmpty);
      Finder field(String label) => find.byWidgetPredicate(
        (widget) =>
            widget is TextField && widget.decoration?.labelText == label,
      );
      expect(
        tester.widget<TextField>(field('Rohpreisskalierung')).controller!.text,
        '',
      );
      expect(
        tester.widget<TextField>(field('Umsatzsteuersatz')).controller!.text,
        '',
      );
      await tester.ensureVisible(find.byType(DropdownButtonFormField<String>));
      await tester.tap(find.byType(DropdownButtonFormField<String>));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Einkauf netto').last);
      await tester.pumpAndSettle();
      await tester.enterText(field('Rohpreisskalierung'), '0,0001');
      await tester.enterText(field('Umsatzsteuersatz'), '19');
      await tapCatalog(tester, 'Verbindliche Vorschau laden');
      expect(api.previews.single, api.fixture['mapping']);
      expect(
        find.text('1 neu · 0 aktualisiert · 0 ohne Änderung'),
        findsOneWidget,
      );
      await tester.enterText(field('Rohpreisskalierung'), '0,01');
      await tester.pumpAndSettle();
      expect(
        find.text('1 neu · 0 aktualisiert · 0 ohne Änderung'),
        findsNothing,
      );
      await tapCatalog(tester, 'Artikel ausdrücklich übernehmen');
      expect(api.posts, isEmpty);
      await cleanCatalog(tester, session, api);
    },
  );
  testWidgets(
    'a changed original is rejected before any native exporter sees its bytes',
    (tester) async {
      final api = CatalogApi()
        ..applied = true
        ..alteredOriginal = Uint8List.fromList([...catalogBytes, 10]);
      var exports = 0;
      final session = await mountCatalog(
        tester,
        api,
        exporter: (_, file, allowed) async {
          exports++;
          return MailAttachmentExportResult.saved;
        },
      );
      await openCatalogRun(tester);
      await tapCatalog(tester, 'Original herunterladen');
      expect(exports, 0);
      expect(
        find.textContaining(
          'Originaldatei und gespeicherter Import stimmen nicht',
        ),
        findsOneWidget,
      );
      await cleanCatalog(tester, session, api);
    },
  );
  for (final entry in ['list', 'detail']) {
    testWidgets(
      '$entry navigation closes catalog when the parent session is replaced',
      (tester) async {
        final firstApi = CatalogApi(), nextApi = CatalogApi();
        final first = BusinessSession(api: firstApi),
            next = BusinessSession(api: nextApi);
        await first.load();
        await next.load();
        var selected = first;
        late StateSetter rebuild;
        await tester.pumpWidget(
          MaterialApp(
            home: StatefulBuilder(
              builder: (context, setState) {
                rebuild = setState;
                return entry == 'list'
                    ? BusinessAdaptersPage(session: selected)
                    : BusinessAdapterPage(
                        session: selected,
                        adapter: firstApi.adapter,
                        onConfigure: () async {},
                      );
              },
            ),
          ),
        );
        await tester.pumpAndSettle();
        if (entry == 'list')
          await tapCatalog(tester, 'Synthetic native catalog');
        await tapCatalog(tester, 'Katalogimporte und Originale');
        await openCatalogRun(tester);
        expect(find.text('Artikel ausdrücklich übernehmen'), findsOneWidget);
        rebuild(() => selected = next);
        await tester.pumpAndSettle();
        expect(tester.takeException(), isNull);
        expect(find.byType(BusinessCatalogImportsPage), findsNothing);
        expect(find.text('Artikel ausdrücklich übernehmen'), findsNothing);
        await tester.pumpWidget(const SizedBox.shrink());
        await tester.pumpAndSettle();
        first.dispose();
        next.dispose();
        firstApi.dispose();
        nextApi.dispose();
      },
    );
  }
  test('actual HTTP enforces exact 32 MiB catalog and unchanged 20 MiB ordinary JSON boundaries', () async {
    await HttpOverrides.runWithHttpOverrides(() async {
      final server = await HttpServer.bind(InternetAddress.loopbackIPv4, 0);
      final api = OfficeApi(baseUrl: 'http://127.0.0.1:${server.port}');
      final sizes = [
        32 * 1024 * 1024,
        32 * 1024 * 1024 + 1,
        20 * 1024 * 1024 + 1,
      ];
      var requestIndex = 0;
      server.listen((request) async {
        request.response.headers.contentType = ContentType.json;
        final bytes = utf8.encode(
          jsonEncode({'value': 'x' * (sizes[requestIndex++] - 12)}),
        );
        request.response.add(bytes);
        try {
          await request.response.close();
        } on HttpException {
          /* Expected bounded client abort. */
        } on SocketException {
          /* Expected bounded client abort. */
        }
      });
      try {
        final path = '/api/business/adapters/imports/${'a' * 32}';
        final value = await api.call(path);
        expect(value['value'].length, 32 * 1024 * 1024 - 12);
        await expectLater(
          api.call(path),
          throwsA(
            isA<ApiException>().having(
              (error) => error.message,
              'size error',
              'Antwort ist zu groß.',
            ),
          ),
        );
        await expectLater(
          api.call('/api/business/adapters'),
          throwsA(
            isA<ApiException>().having(
              (error) => error.message,
              'size error',
              'Antwort ist zu groß.',
            ),
          ),
        );
        expect(requestIndex, 3);
      } finally {
        api.dispose();
        await server.close(force: true);
      }
    }, BackendHttp());
  });
  test(
    'actual native HTTP imports original bytes, binds preview, replays both lost ACKs and reads 2 MiB Unicode catalog',
    () async {
      final backend = Directory('../backend').absolute,
          python =
              Platform.environment['SMARTPLAN_TEST_PYTHON'] ??
              '${Directory('../backend').absolute.path}/.venv/${Platform.isWindows ? 'Scripts/python.exe' : 'bin/python'}',
          temporary = await Directory.systemTemp.createTemp(
            'smartplan-native-catalog-',
          );
      Process? server;
      StreamIterator<String>? output;
      StreamSubscription<String>? stderr;
      CatalogHttpApi? api;
      BusinessSession? session;
      final diagnostics = StringBuffer();
      try {
        final seed = fixture.replaceFirst(
          'app = create_app(',
          'from business_schema import ensure_schema\nensure_schema(office, activate=True)\napp = create_app(',
        );
        server = await Process.start(python, [
          '-u',
          '-c',
          seed,
          temporary.path,
        ], workingDirectory: backend.path);
        stderr = server.stderr
            .transform(utf8.decoder)
            .listen(diagnostics.write);
        output = StreamIterator(
          server.stdout.transform(utf8.decoder).transform(const LineSplitter()),
        );
        if (!await output.moveNext().timeout(const Duration(seconds: 30)))
          throw StateError('Catalog fixture not ready: $diagnostics');
        final hello = cloneCatalog(jsonDecode(output.current));
        await HttpOverrides.runWithHttpOverrides(() async {
          api = CatalogHttpApi('http://127.0.0.1:${hello['port']}')
            ..token = hello['token'];
          session = BusinessSession(api: api!);
          await session!.load();
          expect(catalogWritable(session!), true, reason: session!.error);
          final source = businessMap(
            await session!.command('native-catalog-config', '/adapters', {
              'name': 'Synthetic native HTTP source',
              'profile': 'catalog_csv_v1',
              'enabled': true,
            }),
          );
          final importKey = 'catalog-import-${source['id']}',
              importPath = '/adapters/${source['id']}/import',
              body = {
                'filename': 'native-original.csv',
                'content_base64': base64Encode(catalogBytes),
              };
          await expectLater(
            session!.command(importKey, importPath, body),
            throwsA(isA<ApiException>()),
          );
          final run = catalogRun(
            await session!.repeatCatalogCommand(importKey),
            adapterId: source['id'],
          );
          expect(api!.commands[0], api!.commands[1]);
          expect(businessItems(await session!.read('/articles')), isEmpty);
          final rawPreview = await api!.call(
            session!.path('/adapters/imports/${run['id']}/catalog-preview'),
            {},
          );
          final preview = await catalogPreview(run, {}, rawPreview);
          expect(preview['rows'][0]['action'], 'create');
          final applyKey = 'catalog-apply-${run['id']}';
          await expectLater(
            session!.command(applyKey, '/adapters/imports/${run['id']}/apply', {
              'confirmed': true,
            }),
            throwsA(isA<ApiException>()),
          );
          final accepted = catalogRun(
            await session!.repeatCatalogCommand(applyKey),
            adapterId: source['id'],
            runId: run['id'],
          );
          expect(accepted['status'], 'applied');
          expect(api!.commands[2], api!.commands[3]);
          final original = await api!.bytes(
            session!.path('/adapters/imports/${run['id']}/original'),
            mediaType: 'application/octet-stream',
            maxBytes: 2097152,
          );
          expect(original, catalogBytes);
          final history = businessMap(
            await session!.read(
              '/adapters/${source['id']}/imports?offset=0&limit=20',
            ),
          );
          expect(history['total'], 1);
          expect(history['items'][0]['original']['available'], true);
          final current = businessItems(await session!.read('/articles'))
              .single;
          await session!.command(
            'native-catalog-unknown-cost',
            '/articles/${current['id']}',
            {'revision': current['revision'], 'cost_known': false},
          );
          final again = catalogRun(
            await session!.command(importKey, importPath, body),
            adapterId: source['id'],
          );
          final noOp = await catalogPreview(
            again,
            {},
            await api!.call(
              session!.path('/adapters/imports/${again['id']}/catalog-preview'),
              {},
            ),
          );
          expect(noOp['rows'][0]['action'], 'noop');
          expect(noOp['rows'][0]['after']['cost_known'], false);
          final raw = utf8.encode(
            'code;name;unit;cost_price_net;unit_price_net;tax_rate\n' +
                List.generate(
                  2000,
                  (i) =>
                      'SYN-LARGE-$i;${List.filled(500, 'é').join()};ST;1;2;19\n',
                ).join(),
          );
          expect(raw.length, lessThan(2097152));
          final large = Uint8List.fromList([
            ...raw,
            ...List.filled(2097152 - raw.length, 10),
          ]);
          final largeRun = catalogRun(
            await session!.command(importKey, importPath, {
              'filename': 'native-limit.csv',
              'content_base64': base64Encode(large),
            }),
            adapterId: source['id'],
          );
          expect(largeRun['rows'], hasLength(2000));
          final largePreview = await catalogPreview(
            largeRun,
            {},
            await api!.call(
              session!.path(
                '/adapters/imports/${largeRun['id']}/catalog-preview',
              ),
              {},
            ),
          );
          expect(largePreview['rows'], hasLength(2000));
          expect(
            await api!.bytes(
              session!.path('/adapters/imports/${largeRun['id']}/original'),
              mediaType: 'application/octet-stream',
              maxBytes: 2097152,
            ),
            large,
          );
        }, BackendHttp());
      } finally {
        session?.dispose();
        api?.dispose();
        await output?.cancel();
        await stderr?.cancel();
        if (server != null) {
          server.kill();
          try {
            await server.exitCode.timeout(const Duration(seconds: 5));
          } on TimeoutException {
            server.kill(ProcessSignal.sigkill);
            await server.exitCode;
          }
        }
        await temporary.delete(recursive: true);
      }
    },
    tags: const ['posix_backend'],
    timeout: const Timeout(Duration(minutes: 3)),
  );
}

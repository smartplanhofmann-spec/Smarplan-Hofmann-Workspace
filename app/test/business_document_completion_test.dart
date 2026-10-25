import 'dart:async';
import 'dart:io';
import 'dart:ui' as ui;

import 'package:flutter/material.dart';
import 'package:flutter/rendering.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:smartplan_office/api.dart';
import 'package:smartplan_office/business_documents.dart';
import 'package:smartplan_office/business_session.dart';
import 'package:smartplan_office/design.dart';

import 'business_session_test.dart' show BusinessTestApi;

final project = 'b' * 32, measurement = 'e' * 32, article = 'a' * 32;

class CompletionApi extends BusinessTestApi {
  final enabledFeatures = [
    'quote_pricing',
    'measurement_transfer',
    'billing_contact',
  ];
  Completer<dynamic>? pricingResponse, billingResponse;
  final billingByProject = <String, Completer<dynamic>>{};
  Map<String, dynamic>? created;
  bool staleMeasurement = false;
  int? billingDenied, pricingDenied, measurementDenied;
  bool denyPdf = false;
  bool globalCatalogDenied = false, canReadMeasurements = true;
  int? projectFinanceDenied;

  Map<String, dynamic> billing({
    String name = 'Synthetische Bauherrin',
    String city = 'Musterstadt',
  }) => {
    'contact_id': 'c' * 32,
    'contact_revision': 2,
    'source_fingerprint': 'f' * 64,
    'buyer': {
      'name': name,
      'address_line': 'Testweg 7',
      'postal_code': '12345',
      'city': city,
      'country': 'DE',
      'email': 'rechnung@example.invalid',
      'contact_name': 'Test Buchhaltung',
      'vat_id': '',
      'endpoint_id': '',
      'endpoint_scheme': '',
    },
    'address_options': [],
    'person_options': [],
    'completeness': {
      'ready_for_invoice': true,
      'status': 'complete',
      'missing_fields': [],
      'address_status': 'structured',
    },
  };

  Map<String, dynamic> pricing(Map<String, dynamic> body) => {
    'inputs': {...body}..remove('request_id'),
    'preview_hash': 'f' * 64,
    'unit_price_net': '72.60',
    'unit_cost_net': '60.50',
    'breakdown': {
      'base_cost_net': '55.00',
      'labor_cost_net': '0.00',
      'component_cost_net': '0.00',
      'direct_cost_net': '55.00',
      'overhead_net': '5.50',
      'markup_net': '12.10',
      'surcharge_net': '0.00',
    },
    'totals': {
      'net': '145.20',
      'tax': '27.59',
      'gross': '172.79',
      'cost_net': '121.00',
      'profit_net': '24.20',
      'margin_percent': '16.67',
    },
  };

  Map<String, dynamic> source() => {
    'id': measurement,
    'project_id': project,
    'revision': 3,
    'content_hash': 'd' * 64,
    'status': 'signed',
    'title': 'Aufmaß Küche',
    'lines': [
      {
        'description': 'Wandfläche Küche',
        'quantity': '6.8200',
        'unit': 'm2',
        'formula': 'length * width',
      },
    ],
  };

  @override
  Future<dynamic> call(String path, [Map<String, dynamic>? body]) async {
    calls.add((path: path, body: body));
    if (path.split('?').first == '/api/business/capabilities')
      return {
        'storage_version': 7,
        'compatibility_mode': 'business',
        'generation': 1,
        'features': enabledFeatures,
        'capabilities': ['business_documents', 'business_operations'],
        'permissions': [
          'finance.read',
          'finance.write',
          if (canReadMeasurements) 'documents.read',
        ],
      };
    if (path.contains('/billing-contact')) {
      if (billingDenied != null)
        throw ApiException(billingDenied!, 'Projektkontakt nicht verfügbar.');
      final id = path.split('/')[4];
      return billingByProject[id]?.future ??
          billingResponse?.future ??
          billing();
    }
    if ((path == '/api/business/articles' ||
            path == '/api/business/templates') &&
        globalCatalogDenied) {
      throw const ApiException(403, 'Globaler Katalog nicht freigegeben.');
    }
    if (path == '/api/business/articles')
      return {
        'items': [
          {
            'id': article,
            'revision': 4,
            'active': true,
            'name': 'Test-Material',
            'unit': 'C62',
            'cost_price_net': '10.00',
            'unit_price_net': '15.00',
          },
        ],
      };
    if (path == '/api/business/commercial/pricing/preview') {
      if (pricingDenied != null)
        throw ApiException(
          pricingDenied!,
          'Kalkulation nicht mehr freigegeben.',
        );
      return pricingResponse?.future ?? pricing(body!);
    }
    if (path == '/api/business/commercial/measurement-preview') {
      if (measurementDenied != null)
        throw ApiException(
          measurementDenied!,
          'Aufmaß nicht mehr freigegeben.',
        );
      if (staleMeasurement)
        throw const ApiException(
          409,
          'Das Aufmaß wurde geändert. Bitte neu laden.',
        );
      return {
        'preview_hash': '9' * 64,
        'requires_confirmation': true,
        'source': source(),
        'positions': [
          {
            'description': body!['lines'][0]['description'],
            'quantity': '6.8200',
            'unit': 'MTK',
            'unit_price_net': body['lines'][0]['unit_price_net'],
            'tax_rate': '19',
            'kind': 'service',
            'source_type': 'measurement',
            'source_id': measurement,
          },
        ],
      };
    }
    if (path.startsWith('/api/business/measurements?'))
      return {
        'items': [source()],
      };
    if (path == '/api/business/measurements/$measurement') return source();
    if (path == '/api/business/templates' ||
        path.contains('/documents/time-sources'))
      return {'items': []};
    if (path == '/api/business/commercial/document-calculation')
      return {
        'totals': {'net': '25.00', 'gross': '29.75'},
        'cost_summary': {
          'complete': false,
          'known_cost_net': '0.00',
          'unknown_positions': [0],
        },
        'profit_net': null,
        'margin_percent': null,
      };
    if (path.startsWith('/api/business/documents?')) {
      if (projectFinanceDenied != null)
        throw ApiException(
          projectFinanceDenied!,
          'Projektfinanzen nicht mehr freigegeben.',
        );
      return {'items': []};
    }
    if (path == '/api/business/documents' && body != null) {
      created = {...body, 'id': '7' * 32, 'revision': 1, 'status': 'draft'};
      return created;
    }
    if (path == '/api/business/documents/${'7' * 32}') return created;
    return {'items': []};
  }

  @override
  Future<Uint8List> bytes(
    String path, {
    required String mediaType,
    int maxBytes = 20 * 1024 * 1024,
  }) async {
    if (denyPdf) throw const ApiException(404, 'Beleg nicht verfügbar.');
    return super.bytes(path, mediaType: mediaType, maxBytes: maxBytes);
  }
}

BusinessSession? activeSession;
CompletionApi? activeApi;

Future<void> closeEditor(WidgetTester tester) async {
  await tester.pumpWidget(const SizedBox());
  activeSession?.dispose();
  activeApi?.dispose();
  activeSession = null;
  activeApi = null;
}

Future<BusinessSession> showEditor(
  WidgetTester tester,
  CompletionApi api, {
  Map<String, dynamic>? document,
  bool global = false,
}) async {
  tester.view.physicalSize = const Size(1100, 1400);
  tester.view.devicePixelRatio = 1;
  addTearDown(tester.view.resetPhysicalSize);
  addTearDown(tester.view.resetDevicePixelRatio);
  final session = BusinessSession(
    api: api,
    projectId: global ? null : project,
    projects: [
      {'id': project, 'name': 'Testprojekt'},
      {'id': '8' * 32, 'name': 'Anderes Projekt'},
    ],
  );
  await session.load();
  await tester.pumpWidget(
    RepaintBoundary(
      key: const ValueKey('completion-capture'),
      child: MaterialApp(
        debugShowCheckedModeBanner: false,
        theme: officeTheme(),
        home: BusinessDocumentEditor(session: session, document: document),
      ),
    ),
  );
  await tester.pumpAndSettle();
  activeSession = session;
  activeApi = api;
  return session;
}

Future<void> tapVisible(
  WidgetTester tester,
  Finder finder, {
  bool settle = true,
}) async {
  FocusManager.instance.primaryFocus?.unfocus();
  await tester.pumpAndSettle();
  await tester.ensureVisible(finder);
  await tester.pumpAndSettle();
  await tester.tap(finder);
  if (settle)
    await tester.pumpAndSettle();
  else
    await tester.pump();
}

Future<void> configurePricing(WidgetTester tester) async {
  await tapVisible(tester, find.text('Position kalkulieren'));
  for (final entry in {
    'description': 'Synthetische Montage',
    'quantity': '2',
    'base_cost_net': '55,00',
  }.entries) {
    final field = find.byKey(ValueKey('pricing-${entry.key}'));
    await tester.ensureVisible(field);
    await tester.enterText(field, entry.value);
  }
  await tapVisible(tester, find.text('Gemeinkosten und Aufschläge'));
  for (final entry in {
    'overhead_percent': '10',
    'markup_percent': '20',
  }.entries) {
    final field = find.byKey(ValueKey('pricing-${entry.key}'));
    await tester.ensureVisible(field);
    await tester.enterText(field, entry.value);
  }
}

Future<void> chooseMeasurement(WidgetTester tester) async {
  await tapVisible(tester, find.text('Mengen aus Aufmaß'));
  await tester.tap(
    find.widgetWithText(DropdownButtonFormField<String>, 'Aufmaß auswählen'),
  );
  await tester.pumpAndSettle();
  await tester.tap(find.text('Aufmaß Küche').last);
  await tester.pumpAndSettle();
  await tester.tap(find.text('Wandfläche Küche'));
  await tester.pumpAndSettle();
  await tester.enterText(
    find.byKey(const ValueKey('business-field-unit_price_net')),
    '25,50',
  );
  await tapVisible(tester, find.widgetWithText(FilledButton, 'Speichern'));
}

void main() {
  setUpAll(() async {
    await (FontLoader(
      'Inter',
    )..addFont(rootBundle.load('assets/fonts/Inter.ttf'))).load();
    await (FontLoader(
      'MaterialIcons',
    )..addFont(rootBundle.load('fonts/MaterialIcons-Regular.otf'))).load();
  });
  testWidgets(
    'Legacy servers keep the manual editor without new feature requests',
    (tester) async {
      final api = CompletionApi()..enabledFeatures.clear();
      await showEditor(tester, api);
      expect(find.text('Position kalkulieren'), findsNothing);
      expect(find.text('Mengen aus Aufmaß'), findsNothing);
      expect(
        api.calls.where(
          (r) =>
              r.path.contains('billing-contact') ||
              r.path.contains('/articles'),
        ),
        isEmpty,
      );
      await closeEditor(tester);
    },
  );

  testWidgets(
    'Calculated prices are only added after explicit adoption and keep their proof',
    (tester) async {
      final api = CompletionApi();
      await showEditor(tester, api);
      await tester.enterText(
        find.byKey(const ValueKey('business-document-title')),
        'Kalkuliertes Angebot',
      );
      await configurePricing(tester);
      expect(
        tester
            .widget<FilledButton>(
              find.widgetWithText(
                FilledButton,
                'Kalkulierten Preis übernehmen',
              ),
            )
            .onPressed,
        isNull,
      );
      await tapVisible(tester, find.text('Preis berechnen'));
      expect(api.created, isNull);
      expect(find.text('Kalkulationsvorschau'), findsOneWidget);
      await tapVisible(tester, find.text('Kalkulierten Preis übernehmen'));
      expect(api.created, isNull);
      await tapVisible(tester, find.text('Entwurf speichern'));
      final position = (api.created!['positions'] as List).single as Map;
      expect(position['unit_price_net'], '72.60');
      expect(position['pricing']['base_cost_net'], '55.00');
      expect(position['pricing']['quantity'], '2');
      expect(position['pricing_hash'], 'f' * 64);
      expect(position['price_confirmation'], true);
      expect(tester.takeException(), isNull);
      await closeEditor(tester);
    },
  );

  testWidgets('Changing a cost invalidates a previous price proposal', (
    tester,
  ) async {
    await showEditor(tester, CompletionApi());
    await configurePricing(tester);
    await tapVisible(tester, find.text('Preis berechnen'));
    final cost = find.byKey(const ValueKey('pricing-base_cost_net'));
    await tester.ensureVisible(cost);
    await tester.enterText(cost, '60');
    await tester.pump();
    expect(find.text('Kalkulationsvorschau'), findsNothing);
    expect(
      tester
          .widget<FilledButton>(
            find.widgetWithText(FilledButton, 'Kalkulierten Preis übernehmen'),
          )
          .onPressed,
      isNull,
    );
    await closeEditor(tester);
  });

  testWidgets(
    'A late calculation after logout cannot reveal prices or adopt a position',
    (tester) async {
      final api = CompletionApi()..pricingResponse = Completer<dynamic>();
      await showEditor(tester, api);
      await configurePricing(tester);
      await tapVisible(tester, find.text('Preis berechnen'), settle: false);
      final body = api.calls
          .lastWhere((r) => r.path.endsWith('/pricing/preview'))
          .body!;
      api.logout();
      api.pricingResponse!.complete(api.pricing(body));
      await tester.pumpAndSettle();
      expect(find.text('Kalkulationsvorschau'), findsNothing);
      expect(find.text('Synthetische Montage'), findsNothing);
      expect(tester.takeException(), isNull);
      await closeEditor(tester);
    },
  );

  testWidgets(
    'BOM article quantities preserve selected article revisions in the server calculation',
    (tester) async {
      final api = CompletionApi();
      await showEditor(tester, api);
      await configurePricing(tester);
      await tapVisible(tester, find.text('Artikel hinzufügen'));
      await tester.tap(
        find.widgetWithText(DropdownButtonFormField<String>, 'Artikel'),
      );
      await tester.pumpAndSettle();
      await tester.tap(find.textContaining('Test-Material').last);
      await tester.pumpAndSettle();
      await tester.enterText(
        find.byKey(const ValueKey('business-field-quantity')),
        '2,5',
      );
      await tapVisible(tester, find.widgetWithText(FilledButton, 'Speichern'));
      await tapVisible(tester, find.text('Preis berechnen'));
      final body = api.calls
          .lastWhere((r) => r.path.endsWith('/pricing/preview'))
          .body!;
      expect(body['components'], [
        {'article_id': article, 'article_revision': 4, 'quantity': '2.5'},
      ]);
      expect(body['base_cost_net'], '55.00');
      await closeEditor(tester);
    },
  );

  testWidgets(
    'Measured quantities require price selection, preview and explicit commit confirmation',
    (tester) async {
      final api = CompletionApi();
      await showEditor(tester, api);
      await tester.enterText(
        find.byKey(const ValueKey('business-document-title')),
        'Angebot aus Aufmaß',
      );
      await chooseMeasurement(tester);
      expect(
        tester
            .widget<FilledButton>(
              find.widgetWithText(FilledButton, 'Mengen und Preise übernehmen'),
            )
            .onPressed,
        isNull,
      );
      await tapVisible(tester, find.text('Übernahme prüfen'));
      expect(find.textContaining('6.8200 MTK'), findsOneWidget);
      await tapVisible(tester, find.text('Mengen und Preise übernehmen'));
      expect(api.created, isNull);
      await tapVisible(tester, find.text('Entwurf speichern'));
      expect(api.created!['positions'], isEmpty);
      final imported =
          (api.created!['measurement_imports'] as List).single as Map;
      expect(imported['measurement_revision'], 3);
      expect(imported['measurement_hash'], 'd' * 64);
      expect(imported['preview_hash'], '9' * 64);
      expect(imported['quantity_confirmation'], true);
      expect(imported['price_confirmation'], true);
      expect(imported['lines'][0]['unit_price_net'], '25.50');
      expect(imported.containsKey('project_id'), false);
      expect(tester.takeException(), isNull);
      await closeEditor(tester);
    },
  );

  testWidgets(
    'A stale measurement keeps selections and explains why import was refused',
    (tester) async {
      final api = CompletionApi()..staleMeasurement = true;
      await showEditor(tester, api);
      await chooseMeasurement(tester);
      await tapVisible(tester, find.text('Übernahme prüfen'));
      expect(
        find.text('Das Aufmaß wurde geändert. Bitte neu laden.'),
        findsOneWidget,
      );
      expect(find.textContaining('25,50 € netto'), findsOneWidget);
      expect(
        tester
            .widget<FilledButton>(
              find.widgetWithText(FilledButton, 'Mengen und Preise übernehmen'),
            )
            .onPressed,
        isNull,
      );
      expect(api.created, isNull);
      await closeEditor(tester);
    },
  );

  testWidgets(
    'New drafts use the structured billing contact without overwriting manual input on reload',
    (tester) async {
      final api = CompletionApi();
      await showEditor(tester, api);
      await tapVisible(tester, find.text('Empfänger und Rechnungsanschrift'));
      final city = find.byKey(const ValueKey('business-buyer-city'));
      expect(
        tester.widget<TextFormField>(city).controller!.text,
        'Musterstadt',
      );
      await tester.ensureVisible(city);
      await tester.enterText(city, 'Manuell ergänzt');
      api.billingResponse = Completer<dynamic>();
      await tapVisible(tester, find.text('Kontakt laden'), settle: false);
      api.billingResponse!.complete(api.billing(city: 'Neue Stammdatenstadt'));
      await tester.pumpAndSettle();
      expect(
        tester.widget<TextFormField>(city).controller!.text,
        'Manuell ergänzt',
      );
      expect(find.text('Neue Stammdatenstadt'), findsNothing);
      expect(find.textContaining('Neue Stammdatenstadt'), findsOneWidget);
      await closeEditor(tester);
    },
  );

  testWidgets(
    'Existing draft buyer snapshots are not fetched or overwritten automatically',
    (tester) async {
      final api = CompletionApi();
      await showEditor(
        tester,
        api,
        document: {
          'id': '6' * 32,
          'revision': 1,
          'project_id': project,
          'buyer': {'name': 'Eingefrorener Empfänger', 'city': 'Alte Stadt'},
        },
      );
      expect(
        api.calls.where((r) => r.path.contains('/billing-contact')),
        isEmpty,
      );
      await tapVisible(tester, find.text('Empfänger und Rechnungsanschrift'));
      expect(
        tester
            .widget<TextFormField>(
              find.byKey(const ValueKey('business-buyer-name')),
            )
            .controller!
            .text,
        'Eingefrorener Empfänger',
      );
      await tapVisible(tester, find.text('Kontakt laden'));
      expect(
        tester
            .widget<TextFormField>(
              find.byKey(const ValueKey('business-buyer-name')),
            )
            .controller!
            .text,
        'Eingefrorener Empfänger',
      );
      await closeEditor(tester);
    },
  );

  testWidgets(
    'Unknown purchase costs stay incomplete instead of showing an invented margin',
    (tester) async {
      final api = CompletionApi();
      await showEditor(
        tester,
        api,
        document: {
          'id': '6' * 32,
          'revision': 1,
          'project_id': project,
          'positions': [
            {
              'description': 'Position ohne EK',
              'quantity': '1',
              'unit': 'C62',
              'unit_price_net': '25.00',
              'tax_rate': '19',
              'kind': 'service',
            },
          ],
        },
      );
      await tapVisible(tester, find.text('Gesamtkalkulation prüfen'));
      expect(find.textContaining('Kosten sind unvollständig'), findsOneWidget);
      expect(find.textContaining('Gewinn netto:'), findsNothing);
      expect(find.textContaining('Marge:'), findsNothing);
      expect(
        api.calls.where(
          (r) => r.path == '/api/business/documents' && r.body != null,
        ),
        isEmpty,
      );
      await closeEditor(tester);
    },
  );

  testWidgets(
    'A billing response arriving after manual input preserves the entered recipient',
    (tester) async {
      final api = CompletionApi()..billingResponse = Completer<dynamic>();
      await showEditor(tester, api);
      await tester.tap(find.text('Empfänger und Rechnungsanschrift'));
      await tester.pump(const Duration(milliseconds: 400));
      final name = find.byKey(const ValueKey('business-buyer-name'));
      await tester.enterText(name, 'Manuell eingegebener Empfänger');
      api.billingResponse!.complete(api.billing());
      await tester.pumpAndSettle();
      expect(
        tester.widget<TextFormField>(name).controller!.text,
        'Manuell eingegebener Empfänger',
      );
      expect(
        tester
            .widget<TextFormField>(
              find.byKey(const ValueKey('business-buyer-city')),
            )
            .controller!
            .text,
        'Musterstadt',
      );
      expect(tester.takeException(), isNull);
      await closeEditor(tester);
    },
  );

  testWidgets(
    'A late response for the previous project cannot populate a different project',
    (tester) async {
      final api = CompletionApi();
      final previous = Completer<dynamic>();
      api.billingByProject[project] = previous;
      await showEditor(tester, api, global: true);
      Future<void> choose(String label) async {
        await tester.tap(
          find.widgetWithText(DropdownButtonFormField<String>, 'Projekt'),
        );
        await tester.pumpAndSettle();
        await tester.tap(find.text(label).last);
        await tester.pumpAndSettle();
      }

      await choose('Testprojekt');
      await choose('Anderes Projekt');
      previous.complete(
        api.billing(
          name: 'Empfänger des alten Projekts',
          city: 'Alte Projektstadt',
        ),
      );
      await tester.pumpAndSettle();
      await tapVisible(tester, find.text('Empfänger und Rechnungsanschrift'));
      expect(
        tester
            .widget<TextFormField>(
              find.byKey(const ValueKey('business-buyer-name')),
            )
            .controller!
            .text,
        'Synthetische Bauherrin',
      );
      expect(find.textContaining('Empfänger des alten Projekts'), findsNothing);
      expect(tester.takeException(), isNull);
      await closeEditor(tester);
    },
  );

  testWidgets(
    'Fresh project contact denial removes cached financial fields without logging out other projects',
    (tester) async {
      final api = CompletionApi();
      final session = await showEditor(tester, api);
      await tapVisible(tester, find.text('Empfänger und Rechnungsanschrift'));
      expect(find.byKey(const ValueKey('business-buyer-name')), findsOneWidget);
      api.billingDenied = 404;
      await tapVisible(tester, find.text('Kontakt laden'));
      expect(find.byKey(const ValueKey('business-buyer-name')), findsNothing);
      expect(find.text('Der Zugang ist nicht mehr verfügbar.'), findsOneWidget);
      expect(session.can('finance.read'), true);
      expect(tester.takeException(), isNull);
      await closeEditor(tester);
    },
  );

  testWidgets(
    'A canonical project documents 404 hides an existing draft even when global finance read remains',
    (tester) async {
      final api = CompletionApi()..projectFinanceDenied = 404;
      final session = await showEditor(
        tester,
        api,
        document: {
          'id': '6' * 32,
          'revision': 1,
          'project_id': project,
          'title': 'Entwurf nach Projektentzug',
          'buyer': {'name': 'Privater Projektkontakt'},
          'positions': [
            {
              'description': 'Vertrauliche Kalkulation',
              'quantity': '1',
              'unit': 'C62',
              'unit_price_net': '50.00',
              'tax_rate': '19',
              'kind': 'service',
            },
          ],
        },
      );
      expect(
        find.byKey(const ValueKey('business-document-title')),
        findsNothing,
      );
      expect(find.text('Vertrauliche Kalkulation'), findsNothing);
      expect(find.text('Der Zugang ist nicht mehr verfügbar.'), findsOneWidget);
      expect(session.can('finance.read'), true);
      expect(tester.takeException(), isNull);
      await closeEditor(tester);
    },
  );

  testWidgets(
    'Fresh pricing denial clears its proposal and the underlying financial editor',
    (tester) async {
      final api = CompletionApi();
      final session = await showEditor(tester, api);
      await configurePricing(tester);
      api.pricingDenied = 403;
      api.projectFinanceDenied = 403;
      await tapVisible(tester, find.text('Preis berechnen'));
      expect(find.byKey(const ValueKey('pricing-base_cost_net')), findsNothing);
      expect(
        find.byKey(const ValueKey('business-document-title')),
        findsNothing,
      );
      expect(find.text('Kalkulationsvorschau'), findsNothing);
      expect(session.allowed, true);
      expect(tester.takeException(), isNull);
      await closeEditor(tester);
    },
  );

  testWidgets(
    'A denied measurement read drops only the measurement sources and selections',
    (tester) async {
      final api = CompletionApi();
      final session = await showEditor(tester, api);
      await chooseMeasurement(tester);
      api.measurementDenied = 403;
      await tapVisible(tester, find.text('Übernahme prüfen'));
      expect(find.text('Wandfläche Küche'), findsNothing);
      expect(find.text('Mengen und Preise übernehmen'), findsNothing);
      expect(session.can('finance.read'), true);
      expect(tester.takeException(), isNull);
      await closeEditor(tester);
    },
  );

  testWidgets(
    'A fresh archive PDF 404 clears previously displayed document data',
    (tester) async {
      final api = CompletionApi()
        ..created = {
          'id': '7' * 32,
          'project_id': project,
          'revision': 1,
          'kind': 'invoice',
          'status': 'final',
          'title': 'Privater synthetischer Archivbeleg',
          'number': 'SYN-007',
          'positions': [],
          'totals': {'net': '10.00', 'gross': '11.90'},
        };
      final session = await showEditor(tester, api);
      await tester.pumpWidget(
        MaterialApp(
          theme: officeTheme(),
          home: BusinessDocumentPage(session: session, id: '7' * 32),
        ),
      );
      await tester.pumpAndSettle();
      expect(find.text('Privater synthetischer Archivbeleg'), findsOneWidget);
      api.denyPdf = true;
      await tapVisible(tester, find.text('PDF öffnen'));
      expect(find.text('Privater synthetischer Archivbeleg'), findsNothing);
      expect(find.text('SYN-007'), findsNothing);
      expect(find.text('Der Zugang ist nicht mehr verfügbar.'), findsOneWidget);
      expect(session.allowed, true);
      expect(tester.takeException(), isNull);
      await closeEditor(tester);
    },
  );

  testWidgets(
    'Recalculation starts with current commercial position fields instead of an older pricing snapshot',
    (tester) async {
      await showEditor(
        tester,
        CompletionApi(),
        document: {
          'id': '6' * 32,
          'revision': 1,
          'project_id': project,
          'positions': [
            {
              'id': '5' * 32,
              'description': 'Bestehende Kalkulation',
              'quantity': '2',
              'unit': 'HUR',
              'tax_rate': '7',
              'kind': 'labor',
              'unit_price_net': '50.00',
              'pricing_snapshot': {
                'inputs': {
                  'quantity': '1',
                  'unit': 'MTR',
                  'tax_rate': '19',
                  'kind': 'material',
                  'base_cost_net': '30.00',
                },
              },
            },
          ],
        },
      );
      await tapVisible(tester, find.text('Bestehende Kalkulation'));
      expect(
        tester
            .widget<TextFormField>(
              find.byKey(const ValueKey('pricing-quantity')),
            )
            .controller!
            .text,
        '2',
      );
      expect(
        tester
            .widget<TextFormField>(find.byKey(const ValueKey('pricing-unit')))
            .controller!
            .text,
        'HUR',
      );
      expect(
        tester
            .widget<TextFormField>(
              find.byKey(const ValueKey('pricing-tax_rate')),
            )
            .controller!
            .text,
        '7',
      );
      expect(find.text('Kalkulationsvorschau'), findsNothing);
      await closeEditor(tester);
    },
  );

  testWidgets(
    'Project finance grants can calculate manually when global catalogs are forbidden',
    (tester) async {
      final api = CompletionApi()..globalCatalogDenied = true;
      final session = await showEditor(tester, api);
      expect(
        find.byKey(const ValueKey('business-document-title')),
        findsOneWidget,
      );
      await configurePricing(tester);
      expect(
        find.textContaining('Der globale Artikelstamm ist nicht freigegeben'),
        findsOneWidget,
      );
      await tapVisible(tester, find.text('Preis berechnen'));
      expect(find.text('Kalkulationsvorschau'), findsOneWidget);
      expect(session.can('finance.read'), true);
      expect(tester.takeException(), isNull);
      await closeEditor(tester);
    },
  );

  testWidgets(
    'Denied live article pricing does not remove an independently authorized financial draft',
    (tester) async {
      final api = CompletionApi()..globalCatalogDenied = true;
      await showEditor(tester, api);
      await tester.enterText(
        find.byKey(const ValueKey('business-document-title')),
        'Berechtigter Projektentwurf',
      );
      await configurePricing(tester);
      api.pricingDenied = 403;
      await tapVisible(tester, find.text('Preis berechnen'));
      expect(find.byKey(const ValueKey('pricing-base_cost_net')), findsNothing);
      expect(
        find.byKey(const ValueKey('business-document-title')),
        findsOneWidget,
      );
      expect(
        api.calls
            .where(
              (r) => r.path == '/api/business/documents?project_id=$project',
            )
            .length,
        greaterThanOrEqualTo(2),
      );
      expect(tester.takeException(), isNull);
      await closeEditor(tester);
    },
  );

  testWidgets(
    'Losing live measurement permission removes pending transfers while keeping frozen document positions',
    (tester) async {
      final api = CompletionApi();
      final session = await showEditor(
        tester,
        api,
        document: {
          'id': '6' * 32,
          'revision': 1,
          'project_id': project,
          'positions': [
            {
              'id': '5' * 32,
              'description': 'Bereits übernommene Belegmenge',
              'quantity': '2',
              'unit': 'MTK',
              'unit_price_net': '25.00',
              'tax_rate': '19',
              'kind': 'service',
              'source_type': 'measurement',
              'source_id': measurement,
            },
          ],
        },
      );
      await chooseMeasurement(tester);
      await tapVisible(tester, find.text('Übernahme prüfen'));
      await tapVisible(tester, find.text('Mengen und Preise übernehmen'));
      expect(find.text('Aus Aufmaß: Aufmaß Küche'), findsOneWidget);
      api.canReadMeasurements = false;
      await session.load();
      await tester.pumpAndSettle();
      expect(find.text('Aus Aufmaß: Aufmaß Küche'), findsNothing);
      expect(find.text('Bereits übernommene Belegmenge'), findsOneWidget);
      expect(session.can('finance.read'), true);
      expect(tester.takeException(), isNull);
      await closeEditor(tester);
    },
  );

  for (final phone in [false, true]) {
    testWidgets(
      'Calculation proposal is usable at ${phone ? '390px' : 'desktop'} width',
      (tester) async {
        await showEditor(tester, CompletionApi());
        tester.view.physicalSize = phone
            ? const Size(390, 840)
            : const Size(1100, 900);
        await tester.pumpAndSettle();
        await configurePricing(tester);
        await tapVisible(tester, find.text('Preis berechnen'));
        await tester.ensureVisible(find.text('Kalkulationsvorschau'));
        await tester.pumpAndSettle();
        expect(
          tester
              .widget<FilledButton>(
                find.widgetWithText(
                  FilledButton,
                  'Kalkulierten Preis übernehmen',
                ),
              )
              .onPressed,
          isNotNull,
        );
        expect(tester.takeException(), isNull);
        if (Platform.environment['SMARTPLAN_CAPTURE_UI'] == '1') {
          await tester.runAsync(() async {
            final boundary = tester.renderObject<RenderRepaintBoundary>(
              find.byKey(const ValueKey('completion-capture')),
            );
            final image = await boundary.toImage();
            try {
              final bytes = await image.toByteData(
                format: ui.ImageByteFormat.png,
              );
              final directory = Directory(
                Platform.environment['SMARTPLAN_UI_OUTPUT'] ??
                    Directory.systemTemp.path,
              );
              await directory.create(recursive: true);
              await File(
                '${directory.path}/smartplan-business-pricing${phone ? '-phone' : ''}.png',
              ).writeAsBytes(bytes!.buffer.asUint8List(), flush: true);
            } finally {
              image.dispose();
            }
          });
        }
        await closeEditor(tester);
      },
    );
  }
}

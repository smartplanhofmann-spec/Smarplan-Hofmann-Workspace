import 'dart:async';
import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:smartplan_office/api.dart';
import 'package:smartplan_office/business_documents.dart';
import 'package:smartplan_office/business_operations.dart';
import 'package:smartplan_office/business_session.dart';
import 'package:smartplan_office/design.dart';

import 'business_session_test.dart' show BusinessTestApi;

const projectId = 'bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb';
const articleId = 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa';
const secondArticleId = 'cccccccccccccccccccccccccccccccc';
const locationId = 'dddddddddddddddddddddddddddddddd';

class MaterialAccessApi extends BusinessTestApi {
  bool feature = true, read = true, badCursor = false;
  Completer<dynamic>? page;
  @override
  Future<dynamic> call(String path, [Map<String, dynamic>? body]) async {
    calls.add((path: path, body: body));
    final uri = Uri.parse(path);
    if (uri.path == '/api/business/capabilities') {
      return {
        'storage_version': 7,
        'compatibility_mode': 'business',
        'generation': 1,
        'capabilities': ['business_inventory'],
        'features': [if (feature) 'inventory_article_refs'],
        'permissions': [if (read) 'inventory.read', 'inventory.write'],
      };
    }
    if (uri.path == '/api/business/articles') {
      throw StateError('A warehouse role must never request catalog prices');
    }
    if (uri.path == '/api/business/inventory/articles') {
      expect(uri.queryParameters['project_id'], projectId);
      expect(uri.queryParameters['limit'], '200');
      if (page != null) return page!.future;
      final next = uri.queryParameters.containsKey('after');
      return {
        'items': [
          {
            'id': next ? secondArticleId : articleId,
            'revision': 1,
            'code': next ? 'MAT-2' : 'MAT-1',
            'name': next ? 'Kabel aus Folgeseite' : 'Rohr aus erster Seite',
            'unit': 'MTR',
            'active': true,
          },
        ],
        'has_more': !next,
        'next_after': next
            ? null
            : badCursor
            ? secondArticleId
            : articleId,
      };
    }
    if (uri.path == '/api/business/inventory/locations') {
      return {
        'items': [
          {'id': locationId, 'name': 'Werkstatt', 'active': true},
        ],
      };
    }
    if (uri.path == '/api/business/inventory/reservations' && body != null) {
      return {...body, 'id': 'e' * 32, 'revision': 1};
    }
    return {'items': []};
  }
}

class DocumentAccessApi extends BusinessTestApi {
  bool read = true, write = true, settings = true, failOnce = false;
  final saved = <Map<String, dynamic>>[];
  final document = <String, dynamic>{
    'id': 'f' * 32,
    'project_id': projectId,
    'kind': 'credit_note',
    'status': 'draft',
    'revision': 2,
    'title': 'Storno zu RE-2026-001',
    'issue_date': '2026-11-04',
    'due_date': '2026-11-04',
    'cancel_reason': 'Falsche Menge',
    'cancelled_number': 'RE-2026-001',
    'cancels': 'e' * 32,
    'buyer': {'name': 'Synthetischer Empfänger'},
    'positions': [
      {
        'description': 'Gebundene Originalposition',
        'quantity': '-2',
        'unit': 'HUR',
        'unit_price_net': '55.50',
        'tax_rate': '19',
        'kind': 'labor',
        'catalog_price_snapshot': {
          'price_id': articleId,
          'unit_price_net': '55.50',
        },
      },
    ],
    'totals': {'net': '-111.00', 'tax': '-21.09', 'gross': '-132.09'},
  };
  @override
  Future<dynamic> call(String path, [Map<String, dynamic>? body]) async {
    calls.add((path: path, body: body));
    if (path.split('?').first == '/api/business/capabilities') {
      return {
        'storage_version': 7,
        'compatibility_mode': 'business',
        'generation': 1,
        'capabilities': ['business_documents'],
        'permissions': [
          if (read) 'finance.read',
          if (write) 'finance.write',
          if (settings) 'settings.manage',
          'finance.issue',
        ],
      };
    }
    if (path == '/api/business/documents/${document['id']}') {
      if (body != null) {
        saved.add(jsonDecode(jsonEncode(body)) as Map<String, dynamic>);
        if (failOnce) {
          failOnce = false;
          throw const ApiException(0, 'Antwort unbestätigt');
        }
        document.addAll({...body, 'revision': 3});
      }
      return document;
    }
    return {'items': []};
  }
}

Future<void> display(WidgetTester tester, Widget page) async {
  tester.view.physicalSize = const Size(1100, 1400);
  tester.view.devicePixelRatio = 1;
  addTearDown(tester.view.resetPhysicalSize);
  addTearDown(tester.view.resetDevicePixelRatio);
  await tester.pumpWidget(
    MaterialApp(
      theme: officeTheme(),
      home: Scaffold(body: page),
    ),
  );
  await tester.pumpAndSettle();
}

Future<void> section(WidgetTester tester, String name) async {
  await tester.tap(find.byType(DropdownButtonFormField<String>).first);
  await tester.pumpAndSettle();
  await tester.tap(find.text(name).last);
  await tester.pumpAndSettle();
}

Future<void> addPosition(WidgetTester tester) async {
  await tester.ensureVisible(find.text('Position hinzufügen'));
  await tester.tap(find.text('Position hinzufügen'));
  await tester.pumpAndSettle();
  await tester.enterText(
    find.byKey(const ValueKey('business-field-description')),
    'Privater Positionsentwurf',
  );
}

void main() {
  testWidgets(
    'Warehouse role selects a paginated price-free article in the actual reservation dialog',
    (tester) async {
      final api = MaterialAccessApi();
      final owner = BusinessSession(api: api, projectId: projectId);
      await owner.load();
      await display(tester, BusinessAreaPage(session: owner, area: 'material'));
      await section(tester, 'Reservierungen');
      await tester.tap(find.text('Neu anlegen'));
      await tester.pumpAndSettle();
      expect(
        find.byKey(const ValueKey('business-field-unit_cost_net')),
        findsNothing,
      );
      await tester.tap(
        find.byWidgetPredicate(
          (widget) =>
              widget is DropdownButtonFormField<String> &&
              widget.decoration.labelText == 'Artikel',
        ),
      );
      await tester.pumpAndSettle();
      await tester.tap(find.text('Kabel aus Folgeseite').last);
      await tester.pumpAndSettle();
      await tester.tap(
        find.byWidgetPredicate(
          (widget) =>
              widget is DropdownButtonFormField<String> &&
              widget.decoration.labelText == 'Lagerort',
        ),
      );
      await tester.pumpAndSettle();
      await tester.tap(find.text('Werkstatt').last);
      await tester.pumpAndSettle();
      await tester.enterText(
        find.byKey(const ValueKey('business-field-quantity')),
        '2',
      );
      await tester.tap(find.widgetWithText(FilledButton, 'Speichern'));
      await tester.pumpAndSettle();
      final saved = api.calls.singleWhere((call) => call.body != null).body!;
      expect(saved['article_id'], secondArticleId);
      expect(saved['location_id'], locationId);
      expect(saved['project_id'], projectId);
      expect(saved['quantity'], '2');
      expect(
        saved.keys,
        unorderedEquals([
          'article_id',
          'location_id',
          'project_id',
          'quantity',
          'request_id',
        ]),
      );
      expect(
        api.calls.where(
          (call) => Uri.parse(call.path).path == '/api/business/articles',
        ),
        isEmpty,
      );
      expect(
        api.calls.where(
          (call) =>
              Uri.parse(call.path).path == '/api/business/inventory/articles',
        ),
        hasLength(2),
      );
      expect(owner.can('finance.read'), isFalse);
      expect(tester.takeException(), isNull);
      await tester.pumpWidget(const SizedBox());
      owner.dispose();
      api.dispose();
    },
  );
  testWidgets('Late reference pages cannot restore a revoked inventory view', (
    tester,
  ) async {
    final api = MaterialAccessApi();
    final owner = BusinessSession(api: api, projectId: projectId);
    await owner.load();
    await display(tester, BusinessAreaPage(session: owner, area: 'material'));
    api.page = Completer<dynamic>();
    await tester.tap(find.byType(DropdownButtonFormField<String>).first);
    await tester.pumpAndSettle();
    await tester.tap(find.text('Lagerbewegungen').last);
    await tester.pump();
    api.read = false;
    await owner.load();
    await tester.pump();
    api.page!.complete({
      'items': [
        {
          'id': articleId,
          'revision': 1,
          'code': 'MAT-PRIVATE',
          'name': 'Verspäteter Artikel',
          'unit': 'MTR',
          'active': true,
        },
      ],
      'has_more': false,
      'next_after': null,
    });
    await tester.pumpAndSettle();
    expect(find.text('Verspäteter Artikel'), findsNothing);
    expect(find.text('Neu anlegen'), findsNothing);
    expect(api.calls.where((call) => call.body != null), isEmpty);
    expect(tester.takeException(), isNull);
    await tester.pumpWidget(const SizedBox());
    owner.dispose();
    api.dispose();
  });
  for (final unsupported in [true, false]) {
    testWidgets(
      unsupported
          ? 'Old server reports unavailable references without requesting catalog prices'
          : 'Broken pagination never exposes partial material choices',
      (tester) async {
        final api = MaterialAccessApi()
          ..feature = !unsupported
          ..badCursor = !unsupported;
        final owner = BusinessSession(api: api, projectId: projectId);
        await owner.load();
        await display(
          tester,
          BusinessAreaPage(session: owner, area: 'material'),
        );
        await section(tester, 'Lagerbewegungen');
        expect(
          find.textContaining(
            unsupported
                ? 'preisfreie Materialauswahl noch nicht'
                : 'Materialauswahl ist unvollständig',
          ),
          findsOneWidget,
        );
        expect(
          api.calls.where(
            (call) => Uri.parse(call.path).path == '/api/business/articles',
          ),
          isEmpty,
        );
        expect(find.text('Rohr aus erster Seite'), findsNothing);
        await tester.pumpWidget(const SizedBox());
        owner.dispose();
        api.dispose();
      },
    );
  }
  for (final template in [false, true]) {
    testWidgets(
      'Open ${template ? 'template' : 'document'} position dialog enforces its current write permission',
      (tester) async {
        final api = DocumentAccessApi()..write = !template;
        final session = BusinessSession(api: api, projectId: projectId);
        await session.load();
        await display(
          tester,
          BusinessDocumentEditor(
            session: session,
            templateMode: template,
            document: template
                ? {
                    'id': 'e' * 32,
                    'kind': 'offer',
                    'name': 'Bestehende Vorlage',
                    'title': 'Vorlage',
                    'positions': [],
                  }
                : null,
          ),
        );
        if (template) {
          expect(session.canWrite('finance.write'), isFalse);
          expect(
            tester
                .widget<FilledButton>(
                  find.widgetWithText(FilledButton, 'Vorlage speichern'),
                )
                .onPressed,
            isNotNull,
          );
          expect(
            tester
                .widget<DropdownButtonFormField<String>>(
                  find.byType(DropdownButtonFormField<String>).first,
                )
                .onChanged,
            isNotNull,
          );
          await tester.tap(find.byType(DropdownButtonFormField<String>).first);
          await tester.pumpAndSettle();
          await tester.tap(find.text('Kostenvoranschlag').last);
          await tester.pumpAndSettle();
        }
        await addPosition(tester);
        if (template) {
          api.settings = false;
        } else {
          api.write = false;
        }
        await session.load();
        await tester.pumpAndSettle();
        expect(
          tester
              .widget<FilledButton>(
                find.widgetWithText(FilledButton, 'Speichern'),
              )
              .onPressed,
          isNull,
        );
        expect(api.saved, isEmpty);
        api.read = false;
        await session.load();
        await tester.pumpAndSettle();
        expect(find.text('Privater Positionsentwurf'), findsNothing);
        expect(
          find.byKey(const ValueKey('business-field-unit_price_net')),
          findsNothing,
        );
        expect(tester.takeException(), isNull);
        await tester.pumpWidget(const SizedBox());
        session.dispose();
        api.dispose();
      },
    );
  }
  testWidgets('A new document offers only creatable kinds', (tester) async {
    final api = DocumentAccessApi();
    final owner = BusinessSession(api: api, projectId: projectId);
    await owner.load();
    await display(tester, BusinessDocumentEditor(session: owner));
    await tester.tap(find.byType(DropdownButtonFormField<String>).first);
    await tester.pumpAndSettle();
    expect(find.text('Stornogutschrift'), findsNothing);
    expect(find.text('Storno'), findsNothing);
    expect(find.text('Schlussrechnung'), findsOneWidget);
    await tester.pumpWidget(const SizedBox());
    owner.dispose();
    api.dispose();
  });
  testWidgets(
    'An existing credit note edits metadata only and restores the exact pending command after reopening',
    (tester) async {
      final api = DocumentAccessApi()..failOnce = true;
      final owner = BusinessSession(api: api, projectId: projectId);
      await owner.load();
      await display(
        tester,
        BusinessDocumentEditor(session: owner, document: api.document),
      );
      expect(find.text('Stornogutschrift bearbeiten'), findsOneWidget);
      expect(find.text('Gebundene Originalposition'), findsOneWidget);
      expect(find.text('Synthetischer Empfänger'), findsOneWidget);
      expect(find.text('Position hinzufügen'), findsNothing);
      expect(find.byType(DropdownButtonFormField<String>), findsNothing);
      await tester.enterText(
        find.byKey(const ValueKey('business-document-title')),
        'Korrigierter Begleittext',
      );
      await tester.enterText(
        find.byKey(const ValueKey('business-document-cancel-reason')),
        'Nach Prüfung',
      );
      await tester.tap(find.text('Entwurf speichern'));
      await tester.pumpAndSettle();
      expect(api.saved, hasLength(1));
      expect(
        api.saved.single.keys,
        unorderedEquals([
          'revision',
          'title',
          'issue_date',
          'due_date',
          'notes',
          'intro',
          'cancel_reason',
          'request_id',
        ]),
      );
      expect(api.saved.single['cancel_reason'], 'Nach Prüfung');
      expect(
        tester
            .widget<TextFormField>(
              find.byKey(const ValueKey('business-document-title')),
            )
            .enabled,
        isFalse,
      );
      await tester.pumpWidget(const SizedBox());
      await tester.pumpWidget(
        MaterialApp(
          theme: officeTheme(),
          home: BusinessDocumentEditor(session: owner, document: api.document),
        ),
      );
      await tester.pumpAndSettle();
      expect(find.text('Gebundene Originalposition'), findsOneWidget);
      expect(find.text('Synthetischer Empfänger'), findsOneWidget);
      expect(find.text('Korrigierter Begleittext'), findsOneWidget);
      expect(
        tester
            .widget<TextFormField>(
              find.byKey(const ValueKey('business-document-title')),
            )
            .enabled,
        isFalse,
      );
      await tester.tap(find.text('Dieselben Eingaben erneut senden'));
      await tester.pumpAndSettle();
      expect(api.saved, hasLength(2));
      expect(api.saved[1], api.saved[0]);
      expect(tester.takeException(), isNull);
      await tester.pumpWidget(const SizedBox());
      owner.dispose();
      api.dispose();
    },
  );
}

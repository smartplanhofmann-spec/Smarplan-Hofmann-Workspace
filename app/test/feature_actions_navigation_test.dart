import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:smartplan_office/api.dart';
import 'package:smartplan_office/business_operations.dart';
import 'package:smartplan_office/business_session.dart';
import 'package:smartplan_office/business_widgets.dart';
import 'package:smartplan_office/design.dart';

import 'business_session_test.dart' show BusinessTestApi;

const project = 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa';
const article = 'bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb';
const issue = 'cccccccccccccccccccccccccccccccc';
const store = 'dddddddddddddddddddddddddddddddd';
const destination = 'eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee';

class ActionsApi extends BusinessTestApi {
  final permissions = <String>{
    'documents.read',
    'documents.write',
    'projects.manage',
    'inventory.read',
    'inventory.write',
    'finance.read',
    'finance.write',
  };
  bool refsFeature = true, globalFinance = false, pages = false;
  bool failReports = false, failRefs = false;
  bool cleaned = false;

  @override
  Future<dynamic> call(String path, [Map<String, dynamic>? body]) async {
    final uri = Uri.parse(path), route = Uri.parse(path).path;
    calls.add((
      path: path,
      body: body == null
          ? null
          : Map<String, dynamic>.from(jsonDecode(jsonEncode(body))),
    ));
    if (route == '/api/business/capabilities') {
      return {
        'storage_version': 7,
        'compatibility_mode': 'business',
        'readonly': false,
        'generation': 1,
        'capabilities': [
          'business_foundation',
          'business_documents',
          'business_inventory',
          'business_maintenance',
          'business_operations',
        ],
        'permissions': permissions.toList(),
        'global_permissions': [
          'inventory.read',
          'inventory.write',
          if (globalFinance) 'finance.read',
        ],
        'features': [if (refsFeature) 'inventory_article_refs'],
      };
    }
    if (route == '/api/business/inventory/articles') {
      if (failRefs)
        throw const ApiException(
          503,
          'Synthetischer Katalog vorübergehend nicht erreichbar',
        );
      final second = uri.queryParameters.containsKey('after');
      return {
        'items': [
          {
            'id': second ? 'ffffffffffffffffffffffffffffffff' : article,
            'revision': 1,
            'code': second ? 'SYN-2' : 'SYN-1',
            'name': second
                ? 'Synthetischer zweiter Artikel'
                : 'Synthetisches Kabel',
            'unit': 'm',
            'active': true,
          },
        ],
        'has_more': pages && !second,
        'next_after': pages && !second ? article : null,
      };
    }
    if (route == '/api/business/articles') {
      if (!globalFinance)
        throw const ApiException(403, 'Finanzkatalog nicht freigegeben');
      return {
        'items': [
          {
            'id': article,
            'revision': 1,
            'code': 'SYN-1',
            'name': 'Synthetisches Kabel',
            'unit': 'm',
            'kind': 'material',
            'active': true,
            'cost_price_net': '1.25',
          },
        ],
      };
    }
    if (route == '/api/business/inventory/locations') {
      return {
        'items': [
          {'id': store, 'name': 'Synthetisches Hauptlager'},
          {'id': destination, 'name': 'Synthetisches Ziellager'},
        ],
      };
    }
    if (route == '/api/business/inventory/stock') {
      return {
        'items': [
          {'name': 'PRIVATE SYNTHETIC STOCK DETAIL', 'quantity': '2'},
        ],
      };
    }
    if (route == '/api/business/inventory/movements') {
      if (body != null) {
        if (body['kind'] == 'transfer' && body.containsKey('project_id')) {
          throw const ApiException(
            400,
            'Umbuchung wird keinem Projekt berechnet',
          );
        }
        if (body['kind'] == 'return' && body['reversal_of'] != issue) {
          throw const ApiException(
            400,
            'Rückgabe benötigt die ursprüngliche Entnahme',
          );
        }
        return {'id': '99999999999999999999999999999999', ...body};
      }
      return {
        'items': [
          {
            'id': issue,
            'kind': 'issue',
            'article_id': article,
            'project_id': project,
            'quantity': '4.0000',
            'from_location_id': store,
            'to_location_id': null,
            'article_snapshot': {'name': 'Synthetisches Kabel', 'unit': 'm'},
            'created_at': '2026-10-25T08:00:00+00:00',
            'revision': 1,
          },
        ],
      };
    }
    if (route == '/api/business/maintenance/history') {
      return {
        'items': [
          {
            'id': '11111111111111111111111111111111',
            'title': 'Synthetische Wartung',
            'status': 'planned',
            'revision': 1,
            'due_date': '2026-10-25',
            'project_id': project,
          },
        ],
      };
    }
    if (route == '/api/business/service-reports') {
      if (failReports)
        throw const ApiException(
          503,
          'Synthetische Berichte vorübergehend nicht erreichbar',
        );
      return {
        'items': [
          {
            'id': '22222222222222222222222222222222',
            'title': 'Synthetischer unterschriebener Bericht',
            'status': 'signed',
            'signed_at': '2026-10-25T09:00:00+00:00',
          },
        ],
      };
    }
    if ([
      '/api/business/assets',
      '/api/business/inventory/reservations',
      '/api/business/budgets',
    ].contains(route)) {
      return {'items': []};
    }
    throw StateError('Unexpected synthetic action API: $path');
  }
}

Future<BusinessSession> mountArea(
  WidgetTester tester,
  ActionsApi api, {
  String area = 'material',
  bool scoped = true,
  Size size = const Size(1100, 1100),
}) async {
  tester.view.physicalSize = size;
  tester.view.devicePixelRatio = 1;
  addTearDown(tester.view.resetPhysicalSize);
  addTearDown(tester.view.resetDevicePixelRatio);
  final session = BusinessSession(
    api: api,
    projectId: scoped ? project : null,
    projects: [
      {'id': project, 'name': 'Synthetisches Projekt'},
    ],
  );
  await session.load();
  addTearDown(() => finish(tester, session));
  await tester.pumpWidget(
    MaterialApp(
      theme: officeTheme(),
      home: Scaffold(
        body: BusinessAreaPage(session: session, area: area),
      ),
    ),
  );
  await tester.pumpAndSettle();
  return session;
}

Future<void> finish(WidgetTester tester, BusinessSession session) async {
  final api = session.api as ActionsApi;
  if (api.cleaned) return;
  api.cleaned = true;
  await tester.pumpWidget(const SizedBox());
  session.dispose();
  api.dispose();
}

Future<void> choose(WidgetTester tester, String label, String option) async {
  final field = find.widgetWithText(DropdownButtonFormField<String>, label);
  await tester.ensureVisible(field);
  await tester.tap(field);
  await tester.pumpAndSettle();
  await tester.tap(find.text(option).last);
  await tester.pumpAndSettle();
}

Future<void> section(WidgetTester tester, String name) =>
    choose(tester, 'Bereich', name);
Future<void> input(WidgetTester tester, String name, String value) async {
  final field = find.byKey(ValueKey('business-field-$name'));
  await tester.ensureVisible(field);
  await tester.enterText(field, value);
}

void main() {
  testWidgets(
    'Global scoped sections keep the selector and can return to an unscoped section',
    (tester) async {
      final api = ActionsApi()..globalFinance = true;
      final session = await mountArea(
        tester,
        api,
        scoped: false,
        size: const Size(390, 844),
      );
      await section(tester, 'Reservierungen');
      expect(find.text('Projekt auswählen'), findsOneWidget);
      expect(
        find.widgetWithText(DropdownButtonFormField<String>, 'Bereich'),
        findsOneWidget,
      );
      await section(tester, 'Projektbudget');
      await section(tester, 'Artikel und Leistungen');
      expect(find.text('Synthetisches Kabel'), findsWidgets);
      expect(tester.takeException(), isNull);
      await finish(tester, session);
    },
  );

  testWidgets(
    'Inventory selectors use every safe reference page without requesting financial articles',
    (tester) async {
      final api = ActionsApi()..pages = true;
      api.permissions.removeAll(['finance.read', 'finance.write']);
      final session = await mountArea(tester, api);
      await section(tester, 'Reservierungen');
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
      await tester.tap(find.text('Neu anlegen'));
      await tester.pumpAndSettle();
      await choose(tester, 'Artikel', 'Synthetischer zweiter Artikel');
      await tester.tap(find.widgetWithText(TextButton, 'Schließen'));
      await tester.pumpAndSettle();
      expect(find.byType(BusinessEditor), findsNothing);
      expect(tester.takeException(), isNull);
      await finish(tester, session);
    },
  );

  testWidgets(
    'Old inventory servers need an update unless a global financial catalog grant is confirmed',
    (tester) async {
      final api = ActionsApi()..refsFeature = false;
      final session = await mountArea(tester, api);
      api.calls.clear(); // Inspect this selector's preflight, not the preceding catalog page.
      await section(tester, 'Reservierungen');
      expect(
        api.calls.where(
          (call) => Uri.parse(call.path).path == '/api/business/articles',
        ),
        isEmpty,
      );
      expect(find.textContaining('Serverupdate'), findsOneWidget);
      api.globalFinance = true;
      await section(tester, 'Lagerorte');
      await section(tester, 'Reservierungen');
      expect(
        api.calls.where(
          (call) => Uri.parse(call.path).path == '/api/business/articles',
        ),
        hasLength(1),
      );
      expect(find.textContaining('Serverupdate'), findsNothing);
      expect(tester.takeException(), isNull);
      await finish(tester, session);
    },
  );

  testWidgets(
    'A return selects its original project issue and derives article without sending a cost override',
    (tester) async {
      final api = ActionsApi()..globalFinance = true;
      final session = await mountArea(tester, api);
      await section(tester, 'Lagerbewegungen');
      await tester.tap(find.text('Neu anlegen'));
      await tester.pumpAndSettle();
      await choose(tester, 'Bewegung', 'Rückgabe');
      final source = find.widgetWithText(
        DropdownButtonFormField<String>,
        'Ursprüngliche Projektentnahme',
      );
      expect(source, findsOneWidget);
      await tester.ensureVisible(source);
      await tester.tap(source);
      await tester.pumpAndSettle();
      await tester.tap(find.textContaining('Synthetisches Kabel').last);
      await tester.pumpAndSettle();
      await choose(tester, 'In Lagerort', 'Synthetisches Ziellager');
      await input(tester, 'quantity', '1');
      await input(tester, 'unit_cost_net', '999');
      await tester.ensureVisible(
        find.widgetWithText(FilledButton, 'Speichern'),
      );
      await tester.tap(find.widgetWithText(FilledButton, 'Speichern'));
      await tester.pumpAndSettle();
      final body = api.calls
          .where(
            (call) =>
                Uri.parse(call.path).path ==
                    '/api/business/inventory/movements' &&
                call.body != null,
          )
          .single
          .body!;
      expect(body['reversal_of'], issue);
      expect(body['article_id'], article);
      expect(body['project_id'], project);
      expect(body.containsKey('from_location_id'), isFalse);
      expect(body.containsKey('unit_cost_net'), isFalse);
      expect(find.byType(BusinessEditor), findsNothing);
      expect(tester.takeException(), isNull);
      await finish(tester, session);
    },
  );

  testWidgets(
    'A transfer opened inside a project sends only stock locations and no project attribution',
    (tester) async {
      final api = ActionsApi()..globalFinance = true;
      final session = await mountArea(tester, api);
      await section(tester, 'Lagerbewegungen');
      await tester.tap(find.text('Neu anlegen'));
      await tester.pumpAndSettle();
      await choose(tester, 'Bewegung', 'Umlagerung');
      await choose(tester, 'Artikel', 'Synthetisches Kabel');
      await choose(tester, 'Aus Lagerort', 'Synthetisches Hauptlager');
      await choose(tester, 'In Lagerort', 'Synthetisches Ziellager');
      await input(tester, 'quantity', '2');
      await tester.ensureVisible(
        find.widgetWithText(FilledButton, 'Speichern'),
      );
      await tester.tap(find.widgetWithText(FilledButton, 'Speichern'));
      await tester.pumpAndSettle();
      final body = api.calls
          .where(
            (call) =>
                Uri.parse(call.path).path ==
                    '/api/business/inventory/movements' &&
                call.body != null,
          )
          .single
          .body!;
      expect(body['kind'], 'transfer');
      expect(body.containsKey('project_id'), isFalse);
      expect(body.containsKey('unit_cost_net'), isFalse);
      expect(find.byType(BusinessEditor), findsNothing);
      expect(tester.takeException(), isNull);
      await finish(tester, session);
    },
  );

  testWidgets(
    'A failed maintenance preflight remains visible and can reopen then cancel the same action',
    (tester) async {
      final api = ActionsApi()..failReports = true;
      final session = await mountArea(tester, api, area: 'maintenance');
      await section(tester, 'Wartungshistorie');
      await tester.tap(find.text('Synthetische Wartung'));
      await tester.pumpAndSettle();
      expect(tester.takeException(), isNull);
      expect(
        find.textContaining('Berichte vorübergehend nicht erreichbar'),
        findsOneWidget,
      );
      api.failReports = false;
      await tester.tap(find.text('Erneut versuchen'));
      await tester.pumpAndSettle();
      expect(find.text('Wartung abschließen'), findsOneWidget);
      await tester.tap(find.widgetWithText(TextButton, 'Schließen'));
      await tester.pumpAndSettle();
      expect(find.text('Synthetische Wartung'), findsOneWidget);
      expect(
        find.textContaining('Berichte vorübergehend nicht erreichbar'),
        findsNothing,
      );
      expect(api.calls.where((call) => call.body != null), isEmpty);
      expect(tester.takeException(), isNull);
      await finish(tester, session);
    },
  );

  testWidgets(
    'A collection create preflight reports a failure and retries without dropping its host',
    (tester) async {
      final api = ActionsApi();
      final session = await mountArea(tester, api, area: 'maintenance');
      var attempts = 0;
      await tester.pumpWidget(
        MaterialApp(
          theme: officeTheme(),
          home: Scaffold(
            body: BusinessCollection(
              session: session,
              path: '/assets',
              title: 'Synthetische Anlagen',
              readPermission: 'documents.read',
              writePermission: 'documents.write',
              fields: const [],
              onCreate: () async {
                attempts++;
                if (attempts == 1)
                  throw const ApiException(
                    503,
                    'Synthetischer Vorabruf fehlgeschlagen',
                  );
              },
            ),
          ),
        ),
      );
      await tester.pumpAndSettle();
      await tester.tap(find.text('Neu anlegen'));
      await tester.pumpAndSettle();
      expect(tester.takeException(), isNull);
      expect(find.textContaining('Vorabruf fehlgeschlagen'), findsOneWidget);
      await tester.tap(find.text('Erneut versuchen'));
      await tester.tap(
        find.text('Erneut versuchen'),
      ); // Same rendered callback, no rebuild between taps.
      await tester.pumpAndSettle();
      expect(attempts, 2);
      expect(find.text('Synthetische Anlagen'), findsOneWidget);
      expect(find.textContaining('Vorabruf fehlgeschlagen'), findsNothing);
      await finish(tester, session);
    },
  );

  testWidgets(
    'An editor requires every additional fresh read and write grant independently',
    (tester) async {
      final api = ActionsApi();
      final session = await mountArea(tester, api);
      var saves = 0;
      final editor = Function.apply(BusinessEditor.new, const [], {
        #session: session,
        #title: 'PRIVATE SYNTHETIC DIALOG TITLE',
        #fields: const [BusinessField('name', 'Geschützter Text')],
        #initial: {'name': 'PRIVATE SYNTHETIC DIALOG'},
        #readPermission: 'documents.read',
        #writePermission: 'documents.write',
        #additionalReadPermissions: const <String>{'finance.read'},
        #additionalWritePermissions: const <String>{'finance.write'},
        #onSave: (Map<String, dynamic> _) async {
          saves++;
        },
      }) as Widget;
      await tester.pumpWidget(
        MaterialApp(
          theme: officeTheme(),
          home: Scaffold(body: editor),
        ),
      );
      await tester.pumpAndSettle();
      api.permissions.remove('finance.write');
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
      expect(find.text('PRIVATE SYNTHETIC DIALOG'), findsOneWidget);
      api.permissions.remove('finance.read');
      await session.load();
      await tester.pumpAndSettle();
      expect(find.text('PRIVATE SYNTHETIC DIALOG'), findsNothing);
      expect(find.text('PRIVATE SYNTHETIC DIALOG TITLE'), findsNothing);
      expect(saves, 0);
      expect(tester.takeException(), isNull);
      await finish(tester, session);
    },
  );

  testWidgets(
    'A read-only detail hides its title and fields after revocation and closes after its parent is removed',
    (tester) async {
      final api = ActionsApi();
      final session = await mountArea(tester, api);
      await tester.pumpWidget(
        MaterialApp(
          theme: officeTheme(),
          home: Scaffold(
            body: AnimatedBuilder(
              animation: session,
              builder: (_, _) => session.can('inventory.read')
                  ? BusinessCollection(
                      session: session,
                      path: '/inventory/stock',
                      title: 'Synthetischer Bestand',
                      readPermission: 'inventory.read',
                      writePermission: '',
                      editable: false,
                      fields: const [BusinessField('name', 'Artikelname')],
                    )
                  : const Text('Host bleibt nach Rechteentzug geöffnet'),
            ),
          ),
        ),
      );
      await tester.pumpAndSettle();
      await tester.tap(find.text('PRIVATE SYNTHETIC STOCK DETAIL'));
      await tester.pump(const Duration(milliseconds: 500));
      expect(find.byType(AlertDialog), findsOneWidget);
      api.permissions.remove('inventory.read');
      await session.load();
      await tester.pump(const Duration(milliseconds: 500));
      expect(find.text('PRIVATE SYNTHETIC STOCK DETAIL'), findsNothing);
      expect(
        find.text('Host bleibt nach Rechteentzug geöffnet'),
        findsOneWidget,
      );
      await tester.tap(find.widgetWithText(TextButton, 'Schließen'));
      await tester.pumpAndSettle();
      expect(find.byType(AlertDialog), findsNothing);
      expect(
        find.text('Host bleibt nach Rechteentzug geöffnet'),
        findsOneWidget,
      );
      expect(tester.takeException(), isNull);
      await finish(tester, session);
    },
  );
}

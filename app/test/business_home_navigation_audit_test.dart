// Exercise actual OfficeApp routes, controllers and editors. Only the API is
// synthetic: unknown reads and every business mutation fail. Authentication
// endpoints are explicit; no customer, provider, device or server is contacted.
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:smartplan_office/api.dart';
import 'package:smartplan_office/business_contacts.dart';
import 'package:smartplan_office/business_documents.dart';
import 'package:smartplan_office/business_finance.dart';
import 'package:smartplan_office/business_operations.dart';
import 'package:smartplan_office/business_planning.dart';
import 'package:smartplan_office/business_settings.dart';
import 'package:smartplan_office/business_shell.dart';
import 'package:smartplan_office/business_widgets.dart';
import 'package:smartplan_office/main.dart';

const auditProject = 'bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb';
const auditContact = 'cccccccccccccccccccccccccccccccc';

class HomeNavigationAuditApi extends OfficeApi {
  HomeNavigationAuditApi() : super(apiVersion: 'v1');
  final calls = <({String path, Map<String, dynamic>? body})>[];
  final unexpected = <String>[];
  bool financialPermission = true;
  bool emptyProjects = false, failContacts = false;
  static const modules = [
    'business_foundation',
    'business_documents',
    'business_finance',
    'business_planning',
    'business_time',
    'business_operations',
    'business_inventory',
    'business_maintenance',
    'business_adapters',
  ];
  static const permissions = [
    'contacts.read',
    'contacts.write',
    'documents.read',
    'documents.write',
    'planning.read',
    'planning.write',
    'inventory.read',
    'inventory.write',
    'time.own',
    'time.approve',
    'personnel.read',
    'personnel.manage',
    'settings.manage',
    'projects.read',
    'projects.write',
  ];
  static const projects = [
    {
      'id': auditProject,
      'name': 'Synthetisches Prüfprojekt',
      'customer': 'Synthetischer Kunde',
      'status_id': 'active',
    },
  ];
  static const article = {
    'id': 'dddddddddddddddddddddddddddddddd',
    'revision': 1,
    'name': 'Synthetisches Prüfmaterial',
    'unit': 'C62',
    'kind': 'material',
    'unit_price_net': '8.00',
    'cost_price_net': '5.00',
    'tax_rate': '19',
    'active': true,
  };
  static const settings = {
    'revision': 1,
    'company_name': 'Synthetischer Prüfbetrieb',
    'address_line': 'Prüfstraße 1',
    'postal_code': '10115',
    'city': 'Berlin',
    'country': 'DE',
    'issuer_mode': 'sevdesk',
    'issuing_enabled': false,
    'einvoice_format': 'none',
    'default_due_days': 14,
  };

  @override
  Future<dynamic> call(String path, [Map<String, dynamic>? body]) async {
    calls.add((path: path, body: body));
    final uri = Uri.parse(path);
    final route = uri.path;
    if (route == '/api/login') return {'token': 'synthetic-audit-session'};
    if (route == '/api/logout') {
      if (body == null || body.isNotEmpty)
        throw StateError('Unexpected logout payload');
      return <String, dynamic>{};
    }
    if (body != null) {
      throw StateError('Navigation must not issue mutations: $route');
    }
    switch (route) {
      case '/api/me':
        return {
          'id': 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',
          'email': 'owner@example.test',
          'role': 'owner',
        };
      case '/api/projects':
        return emptyProjects ? <Map<String, dynamic>>[] : projects;
      case '/api/storage/status':
        return {
          'selected_provider': 'none',
          'configured': false,
          'connected': false,
          'providers': <Map<String, dynamic>>[],
        };
      case '/api/business/capabilities':
        return {
          'storage_version': 7,
          'compatibility_mode': 'business',
          'generation': 1,
          'capabilities': modules,
          'permissions': [
            ...permissions,
            if (financialPermission) ...[
              'finance.read',
              'finance.write',
              'finance.approve',
            ],
          ],
        };
      case '/api/business/overview':
        return {
          'projects': emptyProjects ? <Map<String, dynamic>>[] : projects,
          'statuses': [
            {'id': 'active', 'name': 'In Ausführung'},
          ],
          'counters': {'projects': emptyProjects ? 0 : 1},
        };
      case '/api/business/feed':
        return {'items': <Map<String, dynamic>>[]};
      case '/api/business/contacts':
        if (failContacts)
          throw const ApiException(
            503,
            'Synthetischer Ladefehler: Kontakte vorübergehend nicht erreichbar.',
          );
        return {
          'items': [
            {
              'id': auditContact,
              'name': 'Synthetischer Prüfkontakt',
              'revision': 1,
              'email': 'contact@example.test',
            },
          ],
        };
      case '/api/business/planning/calendar':
        return {
          'appointments': <Map<String, dynamic>>[],
          'employees': <Map<String, dynamic>>[],
          'resources': <Map<String, dynamic>>[],
          'absences': <Map<String, dynamic>>[],
        };
      case '/api/business/documents':
        return {
          'items': [
            {
              'id': 'eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee',
              'title': 'Synthetischer Angebotsentwurf',
              'kind': 'offer',
              'status': 'draft',
              'revision': 1,
              'project_id': auditProject,
            },
          ],
        };
      case '/api/business/finance/open-items':
        return {
          'items': [
            {
              'id': 'ffffffffffffffffffffffffffffffff',
              'number': 'RE-PRÜFUNG-1',
              'document_id': 'ffffffffffffffffffffffffffffffff',
              'gross': '119.00',
              'paid': '19.00',
              'open': '100.00',
              'due_date': '2026-10-01',
              'level': 0,
            },
          ],
        };
      case '/api/business/finance/outbox':
        return {'items': <Map<String, dynamic>>[]};
      case '/api/business/articles':
        return {
          'items': [article],
        };
      case '/api/business/inventory/locations':
        return {
          'items': [
            {
              'id': '11111111111111111111111111111111',
              'name': 'Synthetisches Hauptlager',
              'revision': 1,
              'active': true,
            },
          ],
        };
      case '/api/business/inventory/stock':
      case '/api/business/inventory/movements':
      case '/api/business/inventory/reservations':
      case '/api/business/budgets':
      case '/api/business/templates':
      case '/api/business/text-blocks':
      case '/api/business/project-statuses':
      case '/api/business/absences':
      case '/api/business/resources':
      case '/api/business/time/categories':
        return {'items': <Map<String, dynamic>>[]};
      case '/api/business/employees':
        return {
          'items': [
            {
              'id': '22222222222222222222222222222222',
              'name': 'Synthetische Mitarbeiterin',
              'revision': 1,
              'user_id': 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',
              'active': true,
            },
          ],
        };
      case '/api/users':
        return [
          {
            'id': 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',
            'email': 'owner@example.test',
            'role': 'owner',
            'active': true,
          },
        ];
      case '/api/business/time/accounts':
        return {
          'employee_id': '22222222222222222222222222222222',
          'net_seconds': 3600,
          'target_seconds': 7200,
          'balance_seconds': -3600,
          'days': <Map<String, dynamic>>[],
        };
      case '/api/business/commercial/settings':
        return settings;
      case '/api/business/finance/dunning/settings':
        return {
          'revision': 1,
          'enabled': false,
          'levels': <Map<String, dynamic>>[],
        };
      case '/api/business/adapters':
        return {
          'items': <Map<String, dynamic>>[],
          'profiles': <Map<String, dynamic>>[],
          'suppliers': <Map<String, dynamic>>[],
        };
      case '/api/inquiries':
        return <Map<String, dynamic>>[];
      case '/api/integrations':
        return {'providers': <Map<String, dynamic>>[]};
      default:
        unexpected.add(path);
        throw StateError('Unspecified audit read: $path');
    }
  }
}

Future<void> auditTap(WidgetTester tester, Finder finder) async {
  await tester.ensureVisible(finder);
  await tester.pumpAndSettle();
  await tester.tap(finder);
  await tester.pumpAndSettle();
  expect(tester.takeException(), isNull);
}

Future<void> mountAudit(
  WidgetTester tester,
  HomeNavigationAuditApi api,
  Size size,
) async {
  tester.view.physicalSize = size;
  tester.view.devicePixelRatio = 1;
  addTearDown(tester.view.resetPhysicalSize);
  addTearDown(tester.view.resetDevicePixelRatio);
  addTearDown(api.dispose);
  addTearDown(() => expect(api.unexpected, isEmpty));
  await tester.pumpWidget(OfficeApp(api: api));
  await tester.enterText(
    find.byType(TextFormField).at(0),
    'owner@example.test',
  );
  await tester.enterText(
    find.byType(TextFormField).at(1),
    'Synthetic-password-123',
  );
  await auditTap(tester, find.widgetWithText(FilledButton, 'Anmelden'));
  expect(find.byType(BusinessHome), findsOneWidget);
}

Future<void> auditMenu(WidgetTester tester, String label) async {
  final state = tester.state<ScaffoldState>(
    find
        .descendant(
          of: find.byType(BusinessHome),
          matching: find.byType(Scaffold),
        )
        .first,
  );
  if (state.widget.drawer != null) {
    state.openDrawer();
    await tester.pumpAndSettle();
  }
  final entry = find.widgetWithText(ListTile, label);
  if (entry.evaluate().isEmpty) {
    final navigation = state.widget.drawer != null
        ? find.byType(Drawer)
        : find
              .descendant(
                of: find.byType(BusinessHome),
                matching: find.byType(Material),
              )
              .first;
    final scrollable = find
        .descendant(of: navigation, matching: find.byType(Scrollable))
        .first;
    await tester.scrollUntilVisible(entry, 240, scrollable: scrollable);
  }
  await auditTap(tester, entry.first);
}

Future<void> auditCancel(WidgetTester tester, String button) async {
  await auditTap(tester, find.text(button).last);
  expect(find.byType(BusinessEditor), findsOneWidget);
  await auditTap(tester, find.text('Schließen'));
  expect(find.byType(BusinessEditor), findsNothing);
}

Future<void> auditArea(WidgetTester tester, String value) async {
  final selector = find.ancestor(
    of: find.text('Bereich'),
    matching: find.byType(DropdownButtonFormField<String>),
  );
  await auditTap(tester, selector);
  await auditTap(tester, find.text(value).last);
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
  for (final size in [const Size(1360, 1000), const Size(390, 844)]) {
    testWidgets(
      'All actual global Home destinations and primary editors return at ${size.width}',
      (tester) async {
        final api = HomeNavigationAuditApi();
        await mountAudit(tester, api, size);
        expect(find.text('Synthetisches Prüfprojekt'), findsOneWidget);
        await auditMenu(tester, 'Projekte');
        expect(find.text('Synthetisches Prüfprojekt'), findsOneWidget);
        await auditMenu(tester, 'Kontakte');
        expect(find.byType(BusinessContactsPage), findsOneWidget);
        expect(find.text('Synthetischer Prüfkontakt'), findsOneWidget);
        await auditCancel(tester, 'Kontakt erstellen');
        await auditMenu(tester, 'Einsatzplanung');
        expect(find.byType(BusinessPlanningPage), findsOneWidget);
        await auditCancel(tester, 'Einsatz planen');
        await auditMenu(tester, 'Belege');
        expect(find.text('Synthetischer Angebotsentwurf'), findsOneWidget);
        await auditTap(tester, find.text('Beleg erstellen'));
        expect(find.byType(BusinessDocumentEditor), findsOneWidget);
        await tester.pageBack();
        await tester.pumpAndSettle();
        expect(find.byType(BusinessDocumentsPage), findsOneWidget);
        await auditMenu(tester, 'Finanzen');
        expect(find.byType(BusinessFinancePage), findsOneWidget);
        expect(find.text('RE-PRÜFUNG-1'), findsOneWidget);
        await auditCancel(tester, 'Zahlung erfassen');
        await auditMenu(tester, 'Material');
        expect(find.text('Synthetisches Prüfmaterial'), findsOneWidget);
        await auditCancel(tester, 'Neu anlegen');
        await auditMenu(tester, 'Personal');
        expect(find.text('Zeitkonto'), findsOneWidget);
        expect(find.text('Netto erfasst: 1:00 Std.'), findsOneWidget);
        await auditMenu(tester, 'Einstellungen');
        expect(find.text('Synthetischer Prüfbetrieb'), findsOneWidget);
        await auditCancel(tester, 'Firma und Ausgabe bearbeiten');
        await auditMenu(tester, 'Übersicht');
        expect(find.text('Ihr Betrieb im Blick'), findsOneWidget);
        expect(find.byType(BusinessHome), findsOneWidget);
        expect(
          api.calls.where(
            (call) => call.body != null && call.path != '/api/login',
          ),
          isEmpty,
        );
        await tester.pumpWidget(const SizedBox());
      },
    );

    testWidgets(
      'Actual Home inquiry, integration and administration routes return at ${size.width}',
      (tester) async {
        final api = HomeNavigationAuditApi();
        await mountAudit(tester, api, size);
        await auditMenu(tester, 'Anfragen');
        expect(find.text('Dein Eingang'), findsOneWidget);
        await auditTap(tester, find.text('Anfrage erfassen').first);
        expect(find.text('Manuell / Telefon'), findsOneWidget);
        await auditTap(tester, find.text('Abbrechen'));
        await tester.pageBack();
        await tester.pumpAndSettle();
        expect(find.text('Ihr Betrieb im Blick'), findsOneWidget);
        await auditMenu(tester, 'Integrationen');
        expect(find.text('Ihre Werkzeuge verbinden.'), findsOneWidget);
        await tester.pageBack();
        await tester.pumpAndSettle();
        expect(find.text('Ihr Betrieb im Blick'), findsOneWidget);
        await auditMenu(tester, 'Weitere Verwaltung');
        await auditTap(
          tester,
          find.byKey(const ValueKey('workspace-return-overview')),
        );
        expect(find.text('Ihr Betrieb im Blick'), findsOneWidget);
        expect(
          api.calls.where(
            (call) => call.body != null && call.path != '/api/login',
          ),
          isEmpty,
        );
        await tester.pumpWidget(const SizedBox());
      },
    );
  }

  testWidgets(
    'Settings opens each actual child route and editor then returns to the existing Home',
    (tester) async {
      final api = HomeNavigationAuditApi();
      await mountAudit(tester, api, const Size(1360, 1000));
      await auditMenu(tester, 'Einstellungen');
      for (final entry in [
        ('Vorlagen und Textbausteine', 'Eigene Dokumentvorlagen'),
        ('Schnittstellenprofile', 'Profil einrichten'),
        ('Mahnregeln', 'Stufe hinzufügen'),
        ('Projektstatus verwalten', 'Projektstatus'),
      ]) {
        await auditTap(tester, find.text(entry.$1));
        expect(find.text(entry.$2), findsWidgets);
        if (entry.$1 == 'Vorlagen und Textbausteine') {
          await auditTap(tester, find.text('Vorlage erstellen'));
          expect(find.byType(BusinessDocumentEditor), findsOneWidget);
          await tester.pageBack();
          await tester.pumpAndSettle();
          await auditTap(tester, find.text('Textbausteine'));
          await auditCancel(tester, 'Textbaustein erstellen');
        } else if (entry.$1 == 'Schnittstellenprofile') {
          await auditCancel(tester, 'Profil einrichten');
        } else if (entry.$1 == 'Mahnregeln') {
          await auditCancel(tester, 'Stufe hinzufügen');
        } else {
          await auditCancel(tester, 'Neu anlegen');
        }
        await tester.pageBack();
        await tester.pumpAndSettle();
        expect(find.byType(BusinessSettingsPage), findsOneWidget);
        expect(find.byType(BusinessHome), findsOneWidget);
        expect(tester.takeException(), isNull);
      }
      expect(
        api.calls.where(
          (call) => call.body != null && call.path != '/api/login',
        ),
        isEmpty,
      );
      await tester.pumpWidget(const SizedBox());
    },
  );

  testWidgets(
    'Every global Material and Personnel subsection retains a way back',
    (tester) async {
      final api = HomeNavigationAuditApi();
      await mountAudit(tester, api, const Size(1360, 1000));
      await auditMenu(tester, 'Material');
      for (final label in [
        'Lagerorte',
        'Bestände',
        'Lagerbewegungen',
        'Reservierungen',
        'Projektbudget',
        'Artikel und Leistungen',
      ]) {
        await auditArea(tester, label);
        expect(find.byType(BusinessAreaPage), findsOneWidget);
        expect(
          find.ancestor(
            of: find.text('Bereich'),
            matching: find.byType(DropdownButtonFormField<String>),
          ),
          findsOneWidget,
          reason:
              'A project-required subsection must not remove the subsection navigation: $label',
        );
        if (find.text('Neu anlegen').evaluate().isNotEmpty) {
          await auditCancel(tester, 'Neu anlegen');
        }
        expect(tester.takeException(), isNull);
      }
      await auditMenu(tester, 'Personal');
      for (final label in [
        'Mitarbeiter',
        'Abwesenheiten',
        'Fahrzeuge und Werkzeuge',
        'Zeitkategorien',
        'Zeitkonto und Freigabe',
      ]) {
        await auditArea(tester, label);
        expect(find.byType(BusinessAreaPage), findsOneWidget);
        if (find.text('Neu anlegen').evaluate().isNotEmpty) {
          await auditCancel(tester, 'Neu anlegen');
        }
        expect(tester.takeException(), isNull);
      }
      expect(find.text('Zeitkonto'), findsOneWidget);
      await auditMenu(tester, 'Übersicht');
      expect(find.text('Ihr Betrieb im Blick'), findsOneWidget);
      await tester.pumpWidget(const SizedBox());
    },
  );

  testWidgets(
    'Fresh rights withdrawal hides Finance destinations and leaves overview usable',
    (tester) async {
      final api = HomeNavigationAuditApi();
      await mountAudit(tester, api, const Size(1360, 1000));
      await auditMenu(tester, 'Finanzen');
      expect(find.text('RE-PRÜFUNG-1'), findsOneWidget);
      api.financialPermission = false;
      await tester
          .widget<BusinessHome>(find.byType(BusinessHome))
          .session
          .load();
      await tester.pumpAndSettle();
      expect(find.text('RE-PRÜFUNG-1'), findsNothing);
      expect(find.widgetWithText(ListTile, 'Finanzen'), findsNothing);
      expect(find.widgetWithText(ListTile, 'Belege'), findsNothing);
      expect(find.text('Finanzen nicht freigegeben'), findsOneWidget);
      await auditMenu(tester, 'Übersicht');
      expect(find.text('Synthetisches Prüfprojekt'), findsOneWidget);
      expect(tester.takeException(), isNull);
      await tester.pumpWidget(const SizedBox());
    },
  );

  testWidgets(
    'Empty overview and failed Contacts load retain navigation and an actual retry',
    (tester) async {
      final api = HomeNavigationAuditApi()
        ..emptyProjects = true
        ..failContacts = true;
      await mountAudit(tester, api, const Size(390, 844));
      expect(find.text('Keine passenden Projekte'), findsOneWidget);
      await auditMenu(tester, 'Kontakte');
      expect(find.textContaining('Synthetischer Ladefehler'), findsOneWidget);
      expect(find.text('Synthetischer Prüfkontakt'), findsNothing);
      final previousReads = api.calls
          .where((call) => call.path == '/api/business/contacts')
          .length;
      api.failContacts = false;
      await auditTap(tester, find.byTooltip('Aktualisieren'));
      expect(
        api.calls.where((call) => call.path == '/api/business/contacts').length,
        previousReads + 1,
      );
      expect(find.text('Synthetischer Prüfkontakt'), findsOneWidget);
      expect(find.textContaining('Synthetischer Ladefehler'), findsNothing);
      await auditMenu(tester, 'Übersicht');
      expect(find.text('Keine passenden Projekte'), findsOneWidget);
      expect(tester.takeException(), isNull);
      expect(
        api.calls.where(
          (call) => call.body != null && call.path != '/api/login',
        ),
        isEmpty,
      );
      await tester.pumpWidget(const SizedBox());
    },
  );

  testWidgets('Actual Home logout clears the session and returns to login', (
    tester,
  ) async {
    final api = HomeNavigationAuditApi();
    await mountAudit(tester, api, const Size(390, 844));
    await auditMenu(tester, 'Abmelden');
    expect(api.token, isNull);
    expect(find.byType(BusinessHome), findsNothing);
    expect(find.byType(TextFormField), findsNWidgets(2));
    expect(find.widgetWithText(FilledButton, 'Anmelden'), findsOneWidget);
    expect(api.calls.where((call) => call.path == '/api/logout'), hasLength(1));
    expect(
      api.calls.where(
        (call) =>
            call.body != null &&
            !['/api/login', '/api/logout'].contains(call.path),
      ),
      isEmpty,
    );
    expect(tester.takeException(), isNull);
    await tester.pumpWidget(const SizedBox());
  });
}

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:smartplan_office/api.dart';
import 'package:smartplan_office/main.dart';

import 'workflow_test.dart' show TestApi;

class CustomerTestApi extends TestApi {
  bool failCreate = false;
  final customers = <Map<String, dynamic>>[
    {
      'id': 'c1',
      'name': 'Muster GmbH',
      'contact': 'Anna Muster',
      'email': 'anna@example.test',
      'phone': '+49 123',
      'address': 'Parkweg 7',
      'notes': 'Testnotiz',
      'active': 1,
      'project_count': 1,
    },
    {
      'id': 'c2',
      'name': 'Planung Süd',
      'contact': '',
      'email': '',
      'phone': '',
      'address': 'Südstraße 2',
      'notes': '',
      'active': 1,
      'project_count': 0,
    },
  ];
  final projects = <Map<String, dynamic>>[
    {
      'id': 'project-1',
      'name': 'Baustelle',
      'customer': 'Muster GmbH',
      'customer_id': 'c1',
    },
  ];
  @override
  Future<dynamic> call(String path, [Map<String, dynamic>? body]) async {
    if (path == '/api/customers' ||
        path.startsWith('/api/customers/') ||
        path == '/api/projects' ||
        path == '/api/projects/project-1/customer') {
      calls.add((path: path, body: body));
      if (path == '/api/customers') {
        if (body == null)
          return [for (final c in customers) Map<String, dynamic>.from(c)];
        if (failCreate) {
          failCreate = false;
          throw const ApiException(409, 'Kunde existiert bereits.');
        }
        final c = <String, dynamic>{
          'id': 'c${customers.length + 1}',
          ...body,
          'active': body['active'] == true ? 1 : 0,
          'project_count': 0,
        };
        customers.add(c);
        return c;
      }
      if (path.startsWith('/api/customers/')) {
        final c = customers.firstWhere((c) => path.endsWith('/${c['id']}'));
        c.addAll({...body!, 'active': body['active'] == true ? 1 : 0});
        return c;
      }
      if (path == '/api/projects') {
        if (body == null) return projects;
        final c = customers.firstWhere((c) => c['id'] == body['customer_id']);
        final p = {
          'id': 'new-project',
          'name': body['name'],
          'customer': c['name'],
          'customer_id': c['id'],
        };
        projects.add(p);
        c['project_count'] = (c['project_count'] as int) + 1;
        return {'id': 'new-project'};
      }
      if (path == '/api/projects/project-1/customer') {
        final c = customers.firstWhere((c) => c['id'] == body!['customer_id']);
        projects.first['customer_id'] = c['id'];
        projects.first['customer'] = c['name'];
        return projects.first;
      }
    }
    return super.call(path, body);
  }
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  setUpAll(() async {
    await (FontLoader(
      'Inter',
    )..addFont(rootBundle.load('assets/fonts/Inter.ttf'))).load();
    await (FontLoader(
      'MaterialIcons',
    )..addFont(rootBundle.load('fonts/MaterialIcons-Regular.otf'))).load();
  });

  Future<CustomerTestApi> login(
    WidgetTester tester, {
    Size size = const Size(1280, 1500),
  }) async {
    tester.view.physicalSize = size;
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    final api = CustomerTestApi();
    await tester.pumpWidget(OfficeApp(api: api));
    await tester.enterText(
      find.byType(TextFormField).at(0),
      'owner@example.test',
    );
    await tester.enterText(
      find.byType(TextFormField).at(1),
      'Owner-password-123',
    );
    await tester.ensureVisible(find.text('Anmelden'));
    await tester.tap(find.text('Anmelden'));
    await tester.pumpAndSettle();
    return api;
  }

  Future<void> openCustomers(WidgetTester tester) async {
    if (find.byTooltip('Navigation öffnen').evaluate().isNotEmpty) {
      await tester.tap(find.byTooltip('Navigation öffnen'));
      await tester.pumpAndSettle();
    }
    await tester.tap(find.text('Kunden'));
    await tester.pumpAndSettle();
  }

  testWidgets(
    'Customer search, edit, archive and reactivation preserve entered data',
    (tester) async {
      final api = await login(tester);
      await openCustomers(tester);
      await tester.enterText(find.byType(TextField), 'Anna');
      await tester.pumpAndSettle();
      expect(find.text('Muster GmbH'), findsOneWidget);
      expect(find.text('Planung Süd'), findsNothing);
      await tester.tap(find.byTooltip('Suche zurücksetzen'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Muster GmbH'));
      await tester.pumpAndSettle();
      await tester.enterText(find.byType(TextFormField).at(3), '+49 987');
      await tester.tap(find.byType(SwitchListTile));
      await tester.tap(find.text('Speichern'));
      await tester.pumpAndSettle();
      expect(api.customers.first['phone'], '+49 987');
      expect(api.customers.first['active'], 0);
      expect(find.text('Muster GmbH'), findsNothing);
      await tester.tap(find.text('Archivierte anzeigen'));
      await tester.pumpAndSettle();
      expect(find.text('Archiviert'), findsOneWidget);
      await tester.tap(find.text('Muster GmbH'));
      await tester.pumpAndSettle();
      expect(
        tester
            .widget<TextFormField>(find.byType(TextFormField).at(3))
            .controller!
            .text,
        '+49 987',
      );
      await tester.tap(find.byType(SwitchListTile));
      await tester.tap(find.text('Speichern'));
      await tester.pumpAndSettle();
      expect(api.customers.first['active'], 1);
      expect(tester.takeException(), isNull);
    },
  );

  testWidgets(
    'Invalid customer fields are checked and a server error retains the form',
    (tester) async {
      final api = await login(tester);
      await openCustomers(tester);
      await tester.tap(find.text('Kunde anlegen'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Speichern'));
      await tester.pumpAndSettle();
      expect(find.text('Kundennamen eingeben.'), findsOneWidget);
      expect(
        api.calls.where((c) => c.path == '/api/customers' && c.body != null),
        isEmpty,
      );
      await tester.enterText(find.byType(TextFormField).at(0), 'Neuer Kunde');
      await tester.enterText(find.byType(TextFormField).at(2), 'ungueltig');
      await tester.tap(find.text('Speichern'));
      await tester.pumpAndSettle();
      expect(find.text('Gültige E-Mail-Adresse eingeben.'), findsOneWidget);
      await tester.enterText(
        find.byType(TextFormField).at(2),
        'kunde@example.test',
      );
      await tester.enterText(
        find.byType(TextFormField).at(5),
        'Eingabe soll erhalten bleiben',
      );
      api.failCreate = true;
      await tester.tap(find.text('Speichern'));
      await tester.pumpAndSettle();
      expect(find.text('Kunde existiert bereits.'), findsOneWidget);
      expect(
        tester
            .widget<TextFormField>(find.byType(TextFormField).at(5))
            .controller!
            .text,
        'Eingabe soll erhalten bleiben',
      );
      await tester.tap(find.text('Speichern'));
      await tester.pumpAndSettle();
      expect(find.text('Neuer Kunde'), findsOneWidget);
      expect(api.customers.last['notes'], 'Eingabe soll erhalten bleiben');
      expect(tester.takeException(), isNull);
    },
  );

  testWidgets(
    'A customer project starts with the chosen customer and returns to the list',
    (tester) async {
      final api = await login(tester);
      await openCustomers(tester);
      await tester.tap(
        find.byTooltip('Projekt für diesen Kunden anlegen').first,
      );
      await tester.pumpAndSettle();
      expect(find.byType(TextFormField), findsOneWidget);
      await tester.enterText(find.byType(TextFormField), 'Kundenprojekt');
      await tester.tap(find.text('Anlegen'));
      await tester.pumpAndSettle();
      expect(
        api.calls
            .lastWhere((c) => c.path == '/api/projects' && c.body != null)
            .body!['customer_id'],
        'c1',
      );
      expect(find.text('2 Projekte'), findsOneWidget);
      await tester.pageBack();
      await tester.pumpAndSettle();
      expect(find.text('Kundenprojekt'), findsOneWidget);
      expect(tester.takeException(), isNull);
    },
  );

  testWidgets('Existing projects can be assigned to another active customer', (
    tester,
  ) async {
    final api = await login(tester);
    await tester.tap(find.text('Baustelle'));
    await tester.pumpAndSettle();
    await tester.tap(find.byTooltip('Kunden zuordnen'));
    await tester.pumpAndSettle();
    await tester.tap(
      find.descendant(
        of: find.byType(AlertDialog),
        matching: find.byType(DropdownButtonFormField<String>),
      ),
    );
    await tester.pumpAndSettle();
    await tester.tap(find.text('Planung Süd · Südstraße 2').last);
    await tester.pumpAndSettle();
    await tester.tap(find.text('Zuordnen'));
    await tester.pumpAndSettle();
    expect(find.text('Planung Süd'), findsOneWidget);
    expect(api.projects.first['customer_id'], 'c2');
    expect(tester.takeException(), isNull);
  });

  testWidgets('Customer editor works in a narrow phone-sized window', (
    tester,
  ) async {
    await login(tester, size: const Size(390, 844));
    await openCustomers(tester);
    await tester.tap(find.text('Kunde anlegen'));
    await tester.pumpAndSettle();
    await tester.enterText(
      find.byType(TextFormField).at(0),
      'Mobiler Testkunde',
    );
    await tester.ensureVisible(find.byType(TextFormField).at(5));
    await tester.enterText(
      find.byType(TextFormField).at(5),
      'Notiz am kleinen Fenster',
    );
    await tester.tap(find.text('Speichern'));
    await tester.pumpAndSettle();
    expect(find.text('Mobiler Testkunde'), findsOneWidget);
    expect(tester.takeException(), isNull);
  });
}

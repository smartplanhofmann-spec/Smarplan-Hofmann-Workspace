import 'dart:io';
import 'dart:ui' as ui;

import 'package:flutter/material.dart';
import 'package:flutter/rendering.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:smartplan_office/main.dart';

import 'workflow_test.dart' show TestApi, openProjectReports;

class DesignApi extends TestApi {
  @override
  Future<dynamic> call(String path, [Map<String, dynamic>? body]) async {
    if (path == '/api/customers' && body == null)
      return [
        {
          'id': 'customer-1',
          'name': 'Muster Gebäudetechnik',
          'contact': 'Anna Muster',
          'email': 'kontakt@example.test',
          'phone': '+49 123 456789',
          'address': 'Parkweg 7\n12345 Musterstadt',
          'notes': 'Vor dem Besuch telefonisch einen Termin abstimmen.',
          'active': 1,
          'project_count': 2,
        },
        {
          'id': 'customer-2',
          'name': 'Planungsbüro Westend',
          'contact': 'Max Beispiel',
          'email': 'buero@example.test',
          'phone': '+49 987 654321',
          'address': 'Westendstraße 12\n54321 Beispielstadt',
          'notes': '',
          'active': 1,
          'project_count': 1,
        },
      ];
    if (path == '/api/projects' && body == null) {
      return [
        {
          'id': 'project-1',
          'name': 'Wohnhaus am Park',
          'customer': 'Familie Berger',
        },
        {
          'id': 'project-2',
          'name': 'Büroausbau Westend',
          'customer': 'Westend Immobilien',
        },
        {
          'id': 'project-3',
          'name': 'Lichtkonzept Altbau',
          'customer': 'Praxis Dr. Weber',
        },
      ];
    }
    return super.call(path, body);
  }
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  final boundaryKey = GlobalKey();

  setUpAll(() async {
    await (FontLoader(
      'Inter',
    )..addFont(rootBundle.load('assets/fonts/Inter.ttf'))).load();
    await (FontLoader(
      'MaterialIcons',
    )..addFont(rootBundle.load('fonts/MaterialIcons-Regular.otf'))).load();
  });

  Future<void> setup(
    WidgetTester tester,
    Size size, {
    double textScale = 1,
  }) async {
    tester.view.physicalSize = size;
    tester.view.devicePixelRatio = 1;
    tester.platformDispatcher.textScaleFactorTestValue = textScale;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    addTearDown(tester.platformDispatcher.clearTextScaleFactorTestValue);
    await tester.pumpWidget(
      RepaintBoundary(
        key: boundaryKey,
        child: OfficeApp(api: DesignApi()),
      ),
    );
    await tester.pumpAndSettle();
  }

  Future<void> signIn(WidgetTester tester) async {
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
  }

  Future<void> capture(WidgetTester tester, String name) async {
    if (!const bool.fromEnvironment('DESIGN_PREVIEW')) return;
    await tester.runAsync(() async {
      final boundary = tester.renderObject<RenderRepaintBoundary>(
        find.byKey(boundaryKey),
      );
      final image = await boundary.toImage(pixelRatio: 1);
      final data = await image.toByteData(format: ui.ImageByteFormat.png);
      final file = File('../design/previews/$name.png');
      await file.parent.create(recursive: true);
      await file.writeAsBytes(data!.buffer.asUint8List());
      image.dispose();
    });
  }

  testWidgets(
    'Desktop navigation, search, sorting and list view work with real layout',
    (tester) async {
      await setup(tester, const Size(1440, 1000));
      await capture(tester, '01-anmeldung');
      await signIn(tester);
      expect(find.text('Wohnhaus am Park'), findsOneWidget);
      await capture(tester, '02-projekte');
      await tester.sendKeyDownEvent(LogicalKeyboardKey.controlLeft);
      await tester.sendKeyEvent(LogicalKeyboardKey.keyF);
      await tester.sendKeyUpEvent(LogicalKeyboardKey.controlLeft);
      await tester.pumpAndSettle();
      expect(
        tester.widget<TextField>(find.byType(TextField)).focusNode!.hasFocus,
        isTrue,
      );
      await tester.enterText(find.byType(TextField), 'Berger');
      await tester.pumpAndSettle();
      expect(find.text('Wohnhaus am Park'), findsOneWidget);
      expect(find.text('Büroausbau Westend'), findsNothing);
      await tester.tap(find.byTooltip('Suche zurücksetzen'));
      await tester.pumpAndSettle();
      await tester.tap(find.byTooltip('Nach Name sortieren'));
      await tester.tap(find.byTooltip('Listenansicht'));
      await tester.pumpAndSettle();
      expect(
        tester.getTopLeft(find.text('Büroausbau Westend')).dy,
        lessThan(tester.getTopLeft(find.text('Wohnhaus am Park')).dy),
      );
      await tester.enterText(find.byType(TextField), 'kein treffer');
      await tester.pumpAndSettle();
      expect(find.text('Kein passendes Projekt.'), findsOneWidget);
      expect(tester.takeException(), isNull);
    },
  );

  testWidgets(
    'Document, access, team and storage screens render with navigation',
    (tester) async {
      await setup(tester, const Size(1440, 1300));
      await signIn(tester);
      await tester.tap(find.text('Wohnhaus am Park'));
      await tester.pumpAndSettle();
      await openProjectReports(tester);
      await capture(tester, '03-neuer-bericht');
      await tester.tap(find.text('Servicebericht').first);
      await tester.pumpAndSettle();
      await capture(tester, '04-unterschrift');
      await tester.tap(find.byTooltip('Projektzugriff verwalten'));
      await tester.pumpAndSettle();
      await capture(tester, '05-projektzugriff');
      await tester.pageBack();
      await tester.pumpAndSettle();
      await tester.pageBack();
      await tester.pumpAndSettle();
      await tester.tap(find.text('Benutzerverwaltung'));
      await tester.pumpAndSettle();
      await capture(tester, '06-team');
      await tester.pageBack();
      await tester.pumpAndSettle();
      await tester.tap(find.text('Ablage'));
      await tester.pumpAndSettle();
      expect(find.text('Noch nicht eingerichtet'), findsOneWidget);
      await capture(tester, '07-ablage');
      await tester.sendKeyDownEvent(LogicalKeyboardKey.controlLeft);
      await tester.sendKeyEvent(LogicalKeyboardKey.keyF);
      await tester.sendKeyUpEvent(LogicalKeyboardKey.controlLeft);
      await tester.pumpAndSettle();
      expect(
        tester.widget<TextField>(find.byType(TextField)).focusNode!.hasFocus,
        isTrue,
      );
      if (const bool.fromEnvironment('DESIGN_PREVIEW')) {
        await tester.tap(find.text('Kunden'));
        await tester.pumpAndSettle();
        await capture(tester, '10-kunden');
        await tester.tap(find.text('Muster Gebäudetechnik'));
        await tester.pumpAndSettle();
        await capture(tester, '11-kundenkontakt');
      }
      expect(tester.takeException(), isNull);
    },
  );

  testWidgets('Narrow phone layout keeps login and navigation usable', (
    tester,
  ) async {
    await setup(tester, const Size(390, 844));
    await capture(tester, '08-anmeldung-mobil');
    await signIn(tester);
    await capture(tester, '09-projekte-mobil');
    await tester.tap(find.byTooltip('Navigation öffnen'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Benutzerverwaltung'));
    await tester.pumpAndSettle();
    expect(find.text('Das Team.'), findsOneWidget);
    expect(tester.takeException(), isNull);
  });

  testWidgets('Large text remains usable in a narrow window', (tester) async {
    await setup(tester, const Size(390, 844), textScale: 1.5);
    await signIn(tester);
    await tester.tap(find.byTooltip('Navigation öffnen'));
    await tester.pumpAndSettle();
    expect(find.text('Benutzerverwaltung'), findsOneWidget);
    expect(tester.takeException(), isNull);
  });

  testWidgets(
    'Narrow document workflow and short desktop windows stay usable',
    (tester) async {
      await setup(tester, const Size(390, 844));
      await signIn(tester);
      await tester.ensureVisible(find.text('Wohnhaus am Park'));
      await tester.tap(find.text('Wohnhaus am Park'));
      await tester.pumpAndSettle();
      await openProjectReports(tester);
      await tester.tap(find.text('Servicebericht').first);
      await tester.pumpAndSettle();
      await tester.ensureVisible(find.text('Unterschrift speichern'));
      await tester.pumpAndSettle();
      expect(tester.takeException(), isNull);
      await tester.pageBack();
      await tester.pumpAndSettle();
      tester.view.physicalSize = const Size(1024, 600);
      await tester.pumpAndSettle();
      expect(tester.takeException(), isNull);
    },
  );
}

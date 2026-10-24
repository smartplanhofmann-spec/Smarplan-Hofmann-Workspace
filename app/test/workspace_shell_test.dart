import 'dart:io';
import 'dart:ui' as ui;

import 'package:flutter/material.dart';
import 'package:flutter/rendering.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:smartplan_office/design.dart';
import 'package:smartplan_office/home_views.dart';

void main() {
  final boundaryKey = GlobalKey();
  setUpAll(() async {
    await (FontLoader(
      'Inter',
    )..addFont(rootBundle.load('assets/fonts/Inter.ttf'))).load();
    await (FontLoader(
      'MaterialIcons',
    )..addFont(rootBundle.load('fonts/MaterialIcons-Regular.otf'))).load();
  });

  Future<void> capture(WidgetTester tester, String name) async {
    if (Platform.environment['SMARTPLAN_CAPTURE_UI'] != '1') return;
    final output =
        Platform.environment['SMARTPLAN_UI_OUTPUT'] ?? '/workspace/scratch';
    await tester.runAsync(() async {
      final boundary = tester.renderObject<RenderRepaintBoundary>(
        find.byKey(boundaryKey),
      );
      final image = await boundary.toImage(pixelRatio: 1);
      try {
        final bytes = await image.toByteData(format: ui.ImageByteFormat.png);
        final file = File('$output/smartplan-0101-$name.png');
        await file.parent.create(recursive: true);
        await file.writeAsBytes(bytes!.buffer.asUint8List(), flush: true);
      } finally {
        image.dispose();
      }
    });
  }

  final projects = <Map<String, dynamic>>[
    {
      'id': 'one',
      'name': 'Synthetisches Wohnhaus',
      'customer': 'Familie Beispiel',
    },
    {
      'id': 'two',
      'name': 'Synthetischer Büroausbau',
      'customer': 'Firma Muster',
    },
  ];

  Future<void> mount(
    WidgetTester tester, {
    required Size size,
    String role = 'owner',
    double textScale = 1,
    VoidCallback? onInquiries,
    VoidCallback? onCustomers,
    void Function(Map<String, dynamic>)? onProject,
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
        child: MaterialApp(
          theme: officeTheme(),
          home: WorkspaceView(
            user: {
              'id': 'synthetic-user',
              'email': 'user@example.test',
              'role': role,
            },
            projects: projects,
            busy: false,
            onRefresh: () {},
            onLogout: () {},
            onNewProject: () {},
            onConnectDrive: () {},
            onSelectStorage: (_) {},
            onUsers: () {},
            onCustomers: onCustomers ?? () {},
            onInquiries: role == 'owner' ? onInquiries ?? () {} : null,
            onProject: onProject ?? (_) {},
          ),
        ),
      ),
    );
    await tester.pumpAndSettle();
  }

  testWidgets(
    'Phone exposes named work areas and returns from storage to search',
    (tester) async {
      var enquiries = 0;
      var customers = 0;
      await mount(
        tester,
        size: const Size(390, 844),
        onInquiries: () => enquiries++,
        onCustomers: () => customers++,
      );
      expect(
        tester.widget<NavigationBar>(find.byType(NavigationBar)).selectedIndex,
        0,
      );
      expect(tester.takeException(), isNull);
      await capture(tester, 'home-phone');
      await tester.tap(find.text('Anfragen'));
      await tester.tap(find.text('Kunden'));
      expect((enquiries, customers), (1, 1));
      await tester.tap(find.text('Mehr'));
      await tester.pumpAndSettle();
      expect(find.byType(NavigationBar), findsNothing);
      expect(find.text('Organisation'), findsOneWidget);
      await tester.tap(find.text('Ablage'));
      await tester.pumpAndSettle();
      expect(
        tester.widget<NavigationBar>(find.byType(NavigationBar)).selectedIndex,
        3,
      );
      await tester.sendKeyDownEvent(LogicalKeyboardKey.metaLeft);
      await tester.sendKeyEvent(LogicalKeyboardKey.keyF);
      await tester.sendKeyUpEvent(LogicalKeyboardKey.metaLeft);
      await tester.pumpAndSettle();
      expect(
        tester.widget<TextField>(find.byType(TextField)).focusNode!.hasFocus,
        isTrue,
      );
      expect(
        tester.widget<NavigationBar>(find.byType(NavigationBar)).selectedIndex,
        0,
      );
      expect(tester.takeException(), isNull);
    },
  );

  testWidgets(
    'Whole project row opens its actual project and customer search stays local',
    (tester) async {
      Map<String, dynamic>? opened;
      await mount(
        tester,
        size: const Size(1200, 700),
        onProject: (project) => opened = project,
      );
      final row = find.byKey(const ValueKey('project-card-one'));
      final bounds = tester.getRect(row);
      await tester.tapAt(Offset(bounds.right - 20, bounds.center.dy));
      expect(opened?['id'], 'one');
      expect(tester.takeException(), isNull);
      await capture(tester, 'home-desktop');
      await tester.enterText(find.byType(TextField), 'Firma Muster');
      await tester.pumpAndSettle();
      expect(find.text('Synthetisches Wohnhaus'), findsNothing);
      expect(find.text('Synthetischer Büroausbau'), findsOneWidget);
      expect(find.text('1 Treffer'), findsOneWidget);
      expect(tester.takeException(), isNull);
    },
  );

  testWidgets(
    'Large text and short desktop preserve navigation without owner-only actions',
    (tester) async {
      await mount(
        tester,
        size: const Size(390, 844),
        role: 'technician',
        textScale: 1.5,
      );
      expect(find.text('Projekt anlegen'), findsNothing);
      expect(find.text('Anfragen'), findsNothing);
      expect(find.text('Kunden'), findsNothing);
      await tester.tap(find.byTooltip('Navigation öffnen'));
      await tester.pumpAndSettle();
      expect(find.text('Benutzerverwaltung'), findsNothing);
      expect(find.text('Ablage'), findsNothing);
      await tester.tap(find.byTooltip('Navigation schließen'));
      await tester.pumpAndSettle();
      tester.view.physicalSize = const Size(1024, 600);
      await tester.pumpAndSettle();
      expect(find.byType(NavigationBar), findsNothing);
      expect(find.text('Synthetisches Wohnhaus'), findsOneWidget);
      expect(tester.takeException(), isNull);
    },
  );
}

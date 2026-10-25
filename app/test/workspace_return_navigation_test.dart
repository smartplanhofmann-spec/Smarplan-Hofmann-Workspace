import 'dart:io';
import 'dart:ui' as ui;

import 'package:flutter/material.dart';
import 'package:flutter/rendering.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:smartplan_office/api.dart';
import 'package:smartplan_office/business_shell.dart';
import 'package:smartplan_office/home_views.dart';
import 'package:smartplan_office/main.dart';

const returnButton = ValueKey('workspace-return-overview');
const captureBoundary = ValueKey('workspace-return-capture');

class ReturnNavigationApi extends OfficeApi {
  ReturnNavigationApi({this.businessSupported = true})
    : super(apiVersion: 'v1');
  final bool businessSupported;
  final calls = <({String path, Map<String, dynamic>? body})>[];
  final projects = [
    {
      'id': 'b' * 32,
      'name': 'Synthetisches Wohnhaus',
      'customer': 'Familie Beispiel',
    },
    {
      'id': 'c' * 32,
      'name': 'Synthetische Werkstatt',
      'customer': 'Beispielbetrieb',
    },
  ];

  @override
  Future<dynamic> call(String path, [Map<String, dynamic>? body]) async {
    calls.add((path: path, body: body));
    if (path == '/api/login') return {'token': 'synthetic-navigation-session'};
    if (path == '/api/me')
      return {'id': 'a' * 32, 'email': 'owner@example.test', 'role': 'owner'};
    if (path == '/api/projects') return projects;
    if (path == '/api/storage/status')
      return {
        'selected_provider': 'none',
        'configured': false,
        'connected': false,
        'providers': <Map<String, dynamic>>[],
      };
    if (path == '/api/business/capabilities') {
      if (!businessSupported) throw const ApiException(404, 'Älterer Server');
      return {
        'storage_version': 7,
        'compatibility_mode': 'business',
        'generation': 1,
        'capabilities': ['business_foundation'],
        'permissions': [],
      };
    }
    if (path == '/api/business/overview')
      return {
        'projects': projects,
        'statuses': [],
        'counters': {'projects': projects.length},
      };
    if (path == '/api/business/feed') return {'items': []};
    throw StateError('Unexpected navigation request: $path');
  }

  void expire() {
    token = null;
    notifyListeners();
  }
}

Future<void> tapVisible(WidgetTester tester, Finder finder) async {
  FocusManager.instance.primaryFocus?.unfocus();
  await tester.pumpAndSettle();
  await tester.ensureVisible(finder);
  await tester.pumpAndSettle();
  await tester.tap(finder);
  await tester.pumpAndSettle();
}

Future<void> mountAndLogin(
  WidgetTester tester,
  ReturnNavigationApi api,
  Size size, {
  double textScale = 1,
}) async {
  tester.view.physicalSize = size;
  tester.view.devicePixelRatio = 1;
  tester.platformDispatcher.textScaleFactorTestValue = 1;
  addTearDown(tester.view.resetPhysicalSize);
  addTearDown(tester.view.resetDevicePixelRatio);
  addTearDown(tester.platformDispatcher.clearTextScaleFactorTestValue);
  await tester.pumpWidget(
    RepaintBoundary(
      key: captureBoundary,
      child: OfficeApp(api: api),
    ),
  );
  await tester.enterText(
    find.byType(TextFormField).at(0),
    'owner@example.test',
  );
  await tester.enterText(
    find.byType(TextFormField).at(1),
    'Synthetic-navigation-password-123',
  );
  await tapVisible(tester, find.text('Anmelden'));
  // This regression checks authenticated navigation with enlarged text; the
  // login screen has its own independent responsive layout coverage.
  tester.platformDispatcher.textScaleFactorTestValue = textScale;
  await tester.pumpAndSettle();
}

Future<void> modernDestination(
  WidgetTester tester,
  String label, {
  required bool narrow,
}) async {
  if (narrow) await tapVisible(tester, find.byType(DrawerButton));
  await tapVisible(tester, find.widgetWithText(ListTile, label));
}

Future<void> openStorage(WidgetTester tester, {required bool narrow}) async {
  if (narrow) await tapVisible(tester, find.byTooltip('Navigation öffnen'));
  await tapVisible(tester, find.text('Ablage'));
  expect(find.text('Ihre Dokumentablage'), findsOneWidget);
}

Future<void> capture(WidgetTester tester, String name) async {
  if (Platform.environment['SMARTPLAN_CAPTURE_UI'] != '1') return;
  await tester.runAsync(() async {
    final directory = Directory(
      Platform.environment['SMARTPLAN_UI_OUTPUT'] ?? Directory.systemTemp.path,
    );
    await directory.create(recursive: true);
    final image = await tester
        .renderObject<RenderRepaintBoundary>(find.byKey(captureBoundary))
        .toImage();
    try {
      final bytes = await image.toByteData(format: ui.ImageByteFormat.png);
      await File('${directory.path}/smartplan-legacy-return-$name.png')
          .writeAsBytes(bytes!.buffer.asUint8List(), flush: true);
    } finally {
      image.dispose();
    }
  });
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

  for (final scenario in [
    (size: const Size(1200, 900), scale: 1.0, name: 'desktop'),
    (size: const Size(390, 844), scale: 1.0, name: 'phone'),
    (size: const Size(320, 844), scale: 1.5, name: 'phone-large-text'),
  ]) {
    testWidgets(
      'The real app returns from administration to its existing workspace twice on ${scenario.name}',
      (tester) async {
        final api = ReturnNavigationApi();
        final narrow = scenario.size.width < 1000;
        try {
          await mountAndLogin(
            tester,
            api,
            scenario.size,
            textScale: scenario.scale,
          );
          final homeState = tester.state(find.byType(BusinessHome));
          await modernDestination(tester, 'Projekte', narrow: narrow);
          final overviewState = tester.state(find.byType(BusinessOverview));
          await tester.enterText(
            find.widgetWithText(
              TextField,
              'Projekt, Kunde oder Projektnummer suchen',
            ),
            'Wohnhaus',
          );
          await tester.pumpAndSettle();
          expect(find.text('Synthetische Werkstatt'), findsNothing);
          for (var attempt = 0; attempt < 2; attempt++) {
            await modernDestination(
              tester,
              'Weitere Verwaltung',
              narrow: narrow,
            );
            expect(find.byType(WorkspaceView), findsOneWidget);
            await openStorage(tester, narrow: narrow);
            expect(find.byKey(returnButton), findsOneWidget);
            expect(find.text('Zur Übersicht'), findsOneWidget);
            expect(
              find.byKey(returnButton).hitTestable(),
              findsOneWidget,
              reason: 'Return must be visible without opening another navigation menu.',
            );
            if (attempt == 0) await capture(tester, scenario.name);
            expect(tester.takeException(), isNull);
            await tapVisible(tester, find.byKey(returnButton));
            expect(tester.state(find.byType(BusinessHome)), same(homeState));
            expect(
              tester.state(find.byType(BusinessOverview)),
              same(overviewState),
            );
            expect(find.text('Synthetisches Wohnhaus'), findsOneWidget);
            expect(find.text('Synthetische Werkstatt'), findsNothing);
            expect(
              find.byType(WorkspaceView, skipOffstage: false),
              findsNothing,
            );
            expect(
              tester
                  .state<NavigatorState>(find.byType(Navigator).first)
                  .canPop(),
              false,
            );
          }
          expect(api.token, 'synthetic-navigation-session');
          expect(api.calls.where((c) => c.path == '/api/login'), hasLength(1));
          expect(
            api.calls.where((c) => c.body != null && c.path != '/api/login'),
            isEmpty,
          );
          expect(api.calls.where((c) => c.path == '/api/logout'), isEmpty);
          expect(tester.takeException(), isNull);
        } finally {
          await tester.pumpWidget(const SizedBox());
          api.dispose();
        }
      },
    );
  }

  testWidgets(
    'A standalone legacy root has no fabricated dashboard return even while its drawer can pop',
    (tester) async {
      final api = ReturnNavigationApi(businessSupported: false);
      try {
        await mountAndLogin(tester, api, const Size(390, 844));
        expect(find.byType(WorkspaceView), findsOneWidget);
        expect(find.byKey(returnButton), findsNothing);
        await tapVisible(tester, find.byTooltip('Navigation öffnen'));
        expect(
          tester.state<NavigatorState>(find.byType(Navigator).first).canPop(),
          true,
        );
        expect(find.byKey(returnButton), findsNothing);
        await tapVisible(tester, find.byTooltip('Navigation schließen'));
        expect(
          tester.state<NavigatorState>(find.byType(Navigator).first).canPop(),
          false,
        );
        expect(tester.takeException(), isNull);
      } finally {
        await tester.pumpWidget(const SizedBox());
        api.dispose();
      }
    },
  );

  testWidgets(
    'Rapid repeated return activation keeps the original dashboard and root route',
    (tester) async {
      final api = ReturnNavigationApi();
      try {
        await mountAndLogin(tester, api, const Size(1200, 900));
        final homeState = tester.state(find.byType(BusinessHome));
        await modernDestination(tester, 'Weitere Verwaltung', narrow: false);
        final returnAction = tester
            .widget<TextButton>(find.byKey(returnButton))
            .onPressed!;
        returnAction();
        returnAction();
        await tester.pumpAndSettle();
        expect(
          find.byType(BusinessHome),
          findsOneWidget,
          reason:
              'A second activation must not pop the original root workspace.',
        );
        expect(tester.state(find.byType(BusinessHome)), same(homeState));
        expect(find.byType(WorkspaceView, skipOffstage: false), findsNothing);
        expect(
          tester.state<NavigatorState>(find.byType(Navigator).first).canPop(),
          false,
        );
        expect(api.token, 'synthetic-navigation-session');
        expect(
          api.calls.where((c) => c.body != null && c.path != '/api/login'),
          isEmpty,
        );
        expect(tester.takeException(), isNull);
      } finally {
        await tester.pumpWidget(const SizedBox());
        api.dispose();
      }
    },
  );

  testWidgets(
    'Session expiry closes administration and cannot expose the previous workspace through return navigation',
    (tester) async {
      final api = ReturnNavigationApi();
      try {
        await mountAndLogin(tester, api, const Size(1200, 900));
        await modernDestination(tester, 'Weitere Verwaltung', narrow: false);
        expect(find.byType(WorkspaceView), findsOneWidget);
        api.expire();
        await tester.pumpAndSettle();
        expect(find.text('Anmelden'), findsOneWidget);
        expect(find.byType(BusinessHome, skipOffstage: false), findsNothing);
        expect(find.byType(WorkspaceView, skipOffstage: false), findsNothing);
        expect(find.byKey(returnButton), findsNothing);
        expect(
          tester.state<NavigatorState>(find.byType(Navigator).first).canPop(),
          false,
        );
        expect(tester.takeException(), isNull);
      } finally {
        await tester.pumpWidget(const SizedBox());
        api.dispose();
      }
    },
  );
}

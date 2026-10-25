import 'dart:io';
import 'dart:ui' as ui;

import 'package:flutter/material.dart';
import 'package:flutter/rendering.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:smartplan_office/business_session.dart';
import 'package:smartplan_office/business_shell.dart';
import 'package:smartplan_office/design.dart';

import 'business_session_test.dart' show BusinessTestApi;

class ShellApi extends BusinessTestApi {
  bool finance = true;
  @override
  Future<dynamic> call(String path, [Map<String, dynamic>? body]) async {
    calls.add((path: path, body: body));
    if (path.split('?').first == '/api/business/capabilities')
      return {
        'storage_version': 7,
        'compatibility_mode': 'business',
        'generation': 1,
        'capabilities': [
          'business_foundation',
          'business_documents',
          'business_finance',
          'business_planning',
          'business_time',
          'business_inventory',
          'business_operations',
          'business_maintenance',
        ],
        'permissions': [
          'contacts.read',
          'documents.read',
          'time.own',
          'planning.read',
          'inventory.read',
          if (finance) 'finance.read',
        ],
      };
    if (path == '/api/business/overview')
      return {
        'projects': [
          {
            'id': 'a' * 32,
            'name': 'Umbau im Wohnhaus',
            'customer': 'Familie Muster',
            'project_number': '2026-012',
            'site_address': 'Testweg 12 · Beispielstadt',
            'status_id': 's',
            'status': {'id': 's', 'name': 'Ausführung'},
          },
          {
            'id': 'b' * 32,
            'name': 'Wartung der Heizungsanlage',
            'customer': 'Beispiel GmbH',
            'status_id': 'p',
            'status': {'id': 'p', 'name': 'In Klärung'},
          },
        ],
        'statuses': [
          {'id': 's', 'name': 'Ausführung'},
          {'id': 'p', 'name': 'In Klärung'},
        ],
        'counters': {'projects': 2},
      };
    if (path == '/api/business/feed')
      return {
        'items': [
          {
            'summary': 'Montage für morgen vorbereitet. Material liegt im Projektlager bereit.',
            'created_at': '2026-10-26T12:30:00Z',
          },
        ],
      };
    return {'items': []};
  }
}

void main() {
  final boundary = GlobalKey();
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
    await tester.runAsync(() async {
      final output = Directory(
        Platform.environment['SMARTPLAN_UI_OUTPUT'] ??
            Directory.systemTemp.path,
      );
      await output.create(recursive: true);
      final image = await tester
          .renderObject<RenderRepaintBoundary>(find.byKey(boundary))
          .toImage(pixelRatio: 1);
      try {
        final data = await image.toByteData(format: ui.ImageByteFormat.png);
        await File('${output.path}/smartplan-business-$name.png')
            .writeAsBytes(data!.buffer.asUint8List(), flush: true);
      } finally {
        image.dispose();
      }
    });
  }

  for (final size in [const Size(1200, 900), const Size(390, 844)]) {
    testWidgets('Real business dashboard renders at ${size.width}', (
      tester,
    ) async {
      tester.view.physicalSize = size;
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.resetPhysicalSize);
      addTearDown(tester.view.resetDevicePixelRatio);
      final api = ShellApi();
      final session = BusinessSession(api: api);
      await session.load();
      var project = '';
      await tester.pumpWidget(
        RepaintBoundary(
          key: boundary,
          child: MaterialApp(
            debugShowCheckedModeBanner: false,
            theme: officeTheme(),
            home: BusinessHome(
              session: session,
              onProject: (p) => project = p['id'],
              onLegacy: () {},
              onLogout: () {},
            ),
          ),
        ),
      );
      await tester.pumpAndSettle();
      expect(find.text('Umbau im Wohnhaus'), findsOneWidget);
      expect(tester.takeException(), isNull);
      await capture(tester, size.width < 500 ? 'dashboard-phone' : 'dashboard');
      await tester.tap(find.text('Wartung der Heizungsanlage'));
      expect(project, 'b' * 32);
      await tester.pumpWidget(const SizedBox());
      session.dispose();
      api.dispose();
    });
  }
  testWidgets(
    'Finance stays absent without finance permission, even when module exists',
    (tester) async {
      tester.view.physicalSize = const Size(1200, 900);
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.resetPhysicalSize);
      addTearDown(tester.view.resetDevicePixelRatio);
      final api = ShellApi()..finance = false;
      final session = BusinessSession(api: api);
      await session.load();
      await tester.pumpWidget(
        MaterialApp(
          debugShowCheckedModeBanner: false,
          theme: officeTheme(),
          home: BusinessHome(
            session: session,
            onProject: (_) {},
            onLegacy: () {},
            onLogout: () {},
          ),
        ),
      );
      await tester.pumpAndSettle();
      expect(find.text('Finanzen'), findsNothing);
      expect(find.text('Belege'), findsNothing);
      expect(
        api.calls.where(
          (c) => c.path.contains('/finance') || c.path.contains('/documents'),
        ),
        isEmpty,
      );
      await tester.pumpWidget(const SizedBox());
      session.dispose();
      api.dispose();
    },
  );
}

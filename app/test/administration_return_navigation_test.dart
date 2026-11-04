import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:smartplan_office/business_shell.dart';
import 'package:smartplan_office/home_views.dart';
import 'package:smartplan_office/main.dart';

import 'workflow_test.dart' show TestApi;

class AdministrationApi extends TestApi {
  @override
  String get version => 'v1';
  @override
  Future<dynamic> call(String path, [Map<String, dynamic>? body]) async {
    if (path.split('?').first == '/api/business/capabilities') {
      return {
        'storage_version': 7,
        'compatibility_mode': 'business',
        'generation': 1,
        'capabilities': ['business_foundation'],
        'permissions': <String>[],
        'features': <String>[],
      };
    }
    if (path == '/api/business/overview')
      return {'projects': [], 'statuses': []};
    if (path == '/api/business/feed') return {'items': []};
    return super.call(path, body);
  }
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
  for (final size in [const Size(1200, 900), const Size(390, 844)]) {
    testWidgets(
      'Administration returns to the same workspace at ${size.width}',
      (tester) async {
        final api = AdministrationApi();
        tester.view.devicePixelRatio = 1;
        tester.view.physicalSize = size;
        addTearDown(tester.view.resetPhysicalSize);
        addTearDown(tester.view.resetDevicePixelRatio);
        try {
          await tester.pumpWidget(OfficeApp(api: api));
          expect(
            tester.takeException(),
            isNull,
            reason: 'Initial login screen',
          );
          await tester.enterText(
            find.byType(TextFormField).at(0),
            'owner@example.test',
          );
          await tester.enterText(
            find.byType(TextFormField).at(1),
            'Synthetic-password-123',
          );
          await tester.tap(find.text('Anmelden'));
          await tester.pumpAndSettle();
          expect(tester.takeException(), isNull, reason: 'Loaded workspace');
          expect(find.byType(BusinessHome), findsOneWidget);
          final originalWorkspace = tester.state(find.byType(BusinessHome));
          for (var repeat = 0; repeat < 2; repeat++) {
            if (size.width < 1000) {
              await tester.tap(find.byType(DrawerButton));
              await tester.pumpAndSettle();
            }
            final administration = find.text('Weitere Verwaltung');
            await tester.ensureVisible(administration);
            await tester.tap(administration);
            await tester.pumpAndSettle();
            expect(
              tester.takeException(),
              isNull,
              reason: 'Opened administration',
            );
            expect(find.byType(WorkspaceView), findsOneWidget);
            final back = tester
                .widget<IconButton>(
                  find.widgetWithIcon(IconButton, Icons.arrow_back_rounded),
                )
                .onPressed!;
            await tester.tap(find.byTooltip('Zum Arbeitsbereich'));
            await tester.pumpAndSettle();
            expect(find.byType(WorkspaceView), findsNothing);
            expect(
              tester.state(find.byType(BusinessHome)),
              same(originalWorkspace),
            );
            // A queued callback from the removed administration must not pop
            // a later unrelated route or the original workspace.
            final navigator = tester.state<NavigatorState>(
              find.byType(Navigator).first,
            );
            navigator.push<void>(
              MaterialPageRoute(
                builder: (_) => const Scaffold(body: Text('Spätere Route')),
              ),
            );
            await tester.pumpAndSettle();
            back();
            await tester.pumpAndSettle();
            expect(find.text('Spätere Route'), findsOneWidget);
            navigator.pop();
            await tester.pumpAndSettle();
          }
          expect(tester.takeException(), isNull);
          expect(
            api.calls.where((c) => c.body != null && c.path != '/api/login'),
            isEmpty,
          );
        } finally {
          await tester.pumpWidget(const SizedBox());
          api.dispose();
        }
      },
    );
  }
}

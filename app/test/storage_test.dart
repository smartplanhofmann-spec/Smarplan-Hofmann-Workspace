import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:smartplan_office/api.dart';
import 'package:smartplan_office/main.dart';
import 'package:smartplan_office/project_page.dart';

import 'workflow_test.dart' show TestApi;

class StorageApi extends OfficeApi {
  StorageApi() : super(apiVersion: 'v1');

  final fallback = TestApi();
  final calls = <({String path, Map<String, dynamic>? body})>[];
  String selected = 'none';
  bool rejectSelection = false;
  bool unknownProvider = false;

  Map<String, dynamic> status() => {
    'selected_provider': unknownProvider ? 'missing-provider' : selected,
    'configured': unknownProvider || ['server', 'onedrive'].contains(selected),
    'connected': unknownProvider || selected == 'server',
    'providers': [
      {
        'id': 'server',
        'label': 'Smartplan-Server',
        'configured': true,
        'connected': true,
        'requires_connection': false,
      },
      {
        'id': 'onedrive',
        'label': 'OneDrive',
        'configured': true,
        'connected': false,
        'requires_connection': true,
      },
      {
        'id': 'webdav',
        'label': 'Cloud / NAS (WebDAV)',
        'configured': false,
        'connected': false,
        'requires_connection': false,
      },
    ],
  };

  @override
  Future<dynamic> call(String path, [Map<String, dynamic>? body]) async {
    calls.add((path: path, body: body));
    if (path == '/api/storage/status') return status();
    if (path == '/api/storage/provider') {
      if (rejectSelection) {
        throw const ApiException(409, 'Ablage konnte nicht geändert werden.');
      }
      selected = body!['provider'];
      return status();
    }
    if (path == '/api/storage/connect') {
      return {'url': 'https://login.microsoftonline.com/example'};
    }
    if (path == '/api/reports/report-1/storage') return {'uploaded': true};
    return fallback.call(path, body);
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

  Future<void> showStorage(
    WidgetTester tester,
    StorageApi api, {
    Size size = const Size(1200, 1300),
  }) async {
    tester.view.physicalSize = size;
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    await tester.pumpWidget(OfficeApp(api: api));
    await tester.enterText(
      find.byType(TextFormField).at(0),
      'owner@example.test',
    );
    await tester.enterText(
      find.byType(TextFormField).at(1),
      'Owner-password-123',
    );
    await tester.tap(find.text('Anmelden'));
    await tester.pumpAndSettle();
    if (size.width < 1000) {
      await tester.tap(find.byTooltip('Navigation öffnen'));
      await tester.pumpAndSettle();
    }
    await tester.tap(find.text('Ablage'));
    await tester.pumpAndSettle();
  }

  Future<void> choose(WidgetTester tester, String label) async {
    await tester.tap(find.byKey(const ValueKey('storage-provider')));
    await tester.pumpAndSettle();
    await tester.tap(find.text(label).last);
    await tester.pumpAndSettle();
  }

  testWidgets(
    'Owner chooses server, OneDrive or NAS without moving documents',
    (tester) async {
      final api = StorageApi();
      await showStorage(tester, api);
      expect(find.text('Noch keine Ablage gewählt'), findsOneWidget);

      await choose(tester, 'Smartplan-Server');
      expect(api.selected, 'server');
      expect(find.text('Eingerichtet'), findsOneWidget);
      expect(find.text('Mit OneDrive verbinden'), findsNothing);

      await choose(tester, 'OneDrive');
      expect(api.selected, 'onedrive');
      expect(find.text('Noch nicht verbunden'), findsOneWidget);
      expect(find.text('Mit OneDrive verbinden'), findsOneWidget);

      await choose(tester, 'Cloud / NAS (WebDAV)');
      expect(api.selected, 'webdav');
      expect(find.text('Noch nicht eingerichtet'), findsOneWidget);
      expect(find.text('Mit OneDrive verbinden'), findsNothing);
      expect(
        find.textContaining(
          'Bereits abgelegte Dateien werden nicht verschoben',
        ),
        findsOneWidget,
      );
      expect(
        api.calls
            .where((call) => call.path == '/api/storage/provider')
            .map((call) => call.body!['provider']),
        ['server', 'onedrive', 'webdav'],
      );
      expect(
        api.calls.where((call) => call.path.contains('/reports/')),
        isEmpty,
      );
      expect(tester.takeException(), isNull);
    },
  );

  testWidgets('Failed selection preserves the saved storage choice', (
    tester,
  ) async {
    final api = StorageApi()
      ..selected = 'server'
      ..rejectSelection = true;
    await showStorage(tester, api);
    await choose(tester, 'OneDrive');
    expect(api.selected, 'server');
    final dropdown = tester.widget<DropdownButton<String>>(
      find.byKey(const ValueKey('storage-provider')),
    );
    expect(dropdown.value, 'server');
    expect(find.text('Ablage konnte nicht geändert werden.'), findsOneWidget);
    expect(find.text('Mit OneDrive verbinden'), findsNothing);
  });

  testWidgets('Unknown target does not claim a working connection', (
    tester,
  ) async {
    await showStorage(tester, StorageApi()..unknownProvider = true);
    expect(find.text('Ablage nicht verfügbar'), findsOneWidget);
    expect(find.text('Eingerichtet'), findsNothing);
    expect(find.text('Anmeldung gespeichert'), findsNothing);
    expect(find.text('Mit OneDrive verbinden'), findsNothing);
    expect(tester.takeException(), isNull);
  });

  testWidgets('Signed report uses the selected-storage endpoint online', (
    tester,
  ) async {
    tester.view.physicalSize = const Size(1200, 1300);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    final api = StorageApi();
    api.fallback.report = {
      ...api.fallback.report,
      'status': 'signed',
      'signer': 'Testkunde',
      'signed_at': '2026-10-23T08:00:00Z',
    };
    await tester.pumpWidget(
      MaterialApp(
        home: ProjectPage(
          api: api,
          project: const {
            'id': 'project-1',
            'name': 'Baustelle',
            'customer': 'Musterkunde',
          },
          role: 'owner',
        ),
      ),
    );
    await tester.pumpAndSettle();
    await tester.tap(find.text('Servicebericht').first);
    await tester.pumpAndSettle();
    await tester.ensureVisible(find.text('PDF in Ablage speichern'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('PDF in Ablage speichern'));
    await tester.pumpAndSettle();
    expect(find.text('PDF wurde in der Ablage gespeichert.'), findsOneWidget);
    expect(
      api.calls.where((call) => call.path == '/api/reports/report-1/storage'),
      hasLength(1),
    );
    expect(api.calls.where((call) => call.path.endsWith('/onedrive')), isEmpty);
  });

  testWidgets('Storage choice remains usable on a narrow phone', (
    tester,
  ) async {
    final api = StorageApi();
    await showStorage(tester, api, size: const Size(390, 844));
    await tester.ensureVisible(find.byKey(const ValueKey('storage-provider')));
    await choose(tester, 'Cloud / NAS (WebDAV)');
    expect(api.selected, 'webdav');
    await tester.ensureVisible(find.text('Noch nicht eingerichtet'));
    expect(find.text('Noch nicht eingerichtet'), findsOneWidget);
    expect(find.text('Mit OneDrive verbinden'), findsNothing);
    expect(tester.takeException(), isNull);
  });
}

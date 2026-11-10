import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:smartplan_office/api.dart';
import 'package:smartplan_office/business_installation.dart';
import 'package:smartplan_office/business_session.dart';
import 'package:smartplan_office/business_settings.dart';

import 'business_organization_test.dart' show OrganizationApi;

Map<String, dynamic> recorded() => {
  'schema_version': 1,
  'status': 'recorded',
  'source_commit': 'a' * 40,
  'api_compatibility_version': '0.12.0-online-pilot',
};

class InstallationApi extends OrganizationApi {
  bool installationFeature = true, revokeOnRead = false;
  int reads = 0;
  @override
  Future<dynamic> call(String path, [Map<String, dynamic>? body]) async {
    if (path == '/api/business/capabilities') {
      final value = await super.call(path, body);
      value['features'] = [if (installationFeature) 'installation_context'];
      return value;
    }
    if (path == '/api/business/commercial/settings')
      return {
        'revision': 0,
        'country': 'DE',
        'company_name': 'Synthetic support company',
      };
    if (path == '/api/business/installation') {
      reads++;
      if (revokeOnRead) settingsAccess = false;
      return recorded();
    }
    return super.call(path, body);
  }
}

void main() {
  test('original recorded source is distinct from compatibility and missing sources stay unknown', () {
    expect(installationContextView(recorded())['source'], 'a' * 40);
    expect(
      installationContextView({
        ...recorded(),
        'status': 'unrecorded',
        'source_commit': null,
      })['recorded'],
      false,
    );
    for (final v in [
      {...recorded(), 'source_commit': null},
      {...recorded(), 'schema_version': true},
      {...recorded(), 'status': 'unrecorded'},
      {...recorded(), 'source_commit': '${'a' * 40}\n'},
      {...recorded(), 'private_path': '/private/source'},
    ])
      expect(() => installationContextView(v), throwsA(isA<ApiException>()));
  });
  for (final revoke in [false, true])
    test(
      'fresh access ${revoke ? 'after' : 'before'} metadata read cannot disclose a revoked source',
      () async {
        final api = InstallationApi()..revokeOnRead = revoke;
        if (!revoke) api.settingsAccess = false;
        final session = BusinessSession(api: api);
        addTearDown(session.dispose);
        addTearDown(api.dispose);
        await session.load();
        await expectLater(
          readInstallationContext(session),
          throwsA(isA<ApiException>()),
        );
        expect(api.reads, revoke ? 1 : 0);
        expect(api.calls.any((c) => c.body != null), false);
      },
    );
  testWidgets(
    'settings open real metadata dialog and clear its source after permission loss',
    (tester) async {
      final api = InstallationApi();
      final own = BusinessSession(api: api);
      await own.load();
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(body: BusinessSettingsPage(session: own)),
        ),
      );
      await tester.pumpAndSettle();
      final button = find.text('Serverstand anzeigen');
      await tester.ensureVisible(button);
      await tester.tap(button);
      await tester.pumpAndSettle();
      expect(find.text('Installierter Serverstand'), findsOneWidget);
      expect(find.text('a' * 40), findsOneWidget);
      expect(api.reads, 1);
      api.settingsAccess = false;
      await own.load();
      await tester.pumpAndSettle();
      expect(find.text('a' * 40), findsNothing);
      expect(
        find.text(
          'Der Serverstand ist mit dem aktuellen Zugang nicht mehr verfügbar.',
        ),
        findsOneWidget,
      );
      await tester.tap(find.text('Schließen'));
      await tester.pumpAndSettle();
      expect(find.text('Kein Zugriff'), findsOneWidget);
      await tester.pumpWidget(const SizedBox());
      own.dispose();
      api.dispose();
      await tester.pump();
    },
  );
  testWidgets(
    'an old server without the feature never gets a metadata request',
    (tester) async {
      final api = InstallationApi()..installationFeature = false;
      final own = BusinessSession(api: api);
      await own.load();
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(body: BusinessSettingsPage(session: own)),
        ),
      );
      await tester.pumpAndSettle();
      expect(find.text('Serverstand anzeigen'), findsNothing);
      expect(api.reads, 0);
      await tester.pumpWidget(const SizedBox());
      own.dispose();
      api.dispose();
      await tester.pump();
    },
  );
}

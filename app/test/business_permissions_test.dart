import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:smartplan_office/api.dart';
import 'package:smartplan_office/business_permissions.dart';
import 'package:smartplan_office/business_session.dart';
import 'package:smartplan_office/design.dart';

const workerId = '11111111111111111111111111111111';
const ownerId = '22222222222222222222222222222222';
const projectId = '33333333333333333333333333333333';
Map<String, dynamic> copy(Map<String, dynamic> value) =>
    jsonDecode(jsonEncode(value)) as Map<String, dynamic>;

class PermissionApi extends OfficeApi {
  PermissionApi() : super(apiVersion: 'v1') {
    token = 'synthetic-permission-token';
  }
  bool manage = true,
      readOnly = false,
      portal = true,
      accounting = true,
      userAccess = true,
      loseAck = false;
  bool metadataUnavailable = false;
  final grants = <Map<String, dynamic>>[];
  final calls = <({String path, Map<String, dynamic>? body})>[];
  final results = <String, Map<String, dynamic>>{};
  @override
  Future<dynamic> call(String path, [Map<String, dynamic>? body]) async {
    calls.add((path: path, body: body == null ? null : copy(body)));
    if (path.startsWith('/api/business/capabilities')) {
      if (metadataUnavailable)
        throw const ApiException(503, 'Berechtigungsstand nicht erreichbar');
      return {
        'storage_version': 7,
        'compatibility_mode': readOnly ? 'legacy' : 'business',
        'readonly': readOnly,
        'generation': 1,
        'capabilities': ['business_foundation'],
        'features': [
          if (portal) 'offer_portal',
          if (accounting) 'accounting_prejournal',
        ],
        'permissions': [if (manage) 'settings.manage'],
      };
    }
    if (path == '/api/users') {
      if (!userAccess)
        throw const ApiException(
          403,
          'Nur die Geschäftsführung darf die Benutzerliste lesen.',
        );
      return [
        {
          'id': ownerId,
          'email': 'owner@example.test',
          'role': 'owner',
          'active': true,
        },
        {
          'id': workerId,
          'email': 'worker@example.test',
          'role': 'technician',
          'active': true,
        },
      ];
    }
    if (path == '/api/business/settings/permissions') {
      if (!manage)
        throw const ApiException(403, 'Fachrechte nicht freigegeben');
      if (body == null) return {'items': grants.map(copy).toList()};
      expect(body.keys.toSet(), {
        'request_id',
        'user_id',
        'permission',
        'scope',
        'effect',
        'revision',
      });
      expect(body['user_id'], isNot(ownerId));
      final previous = results[body['request_id']];
      if (previous != null) return copy(previous);
      final index = grants.indexWhere(
        (grant) =>
            grant['user_id'] == body['user_id'] &&
            grant['permission'] == body['permission'] &&
            grant['scope'] == body['scope'],
      );
      final revision = index < 0 ? 0 : grants[index]['revision'] as int;
      if (body['revision'] != revision)
        throw const ApiException(409, 'Berechtigung wurde inzwischen geändert');
      final result = <String, dynamic>{
        'id': index < 0 ? 'grant-${grants.length}' : grants[index]['id'],
        'user_id': body['user_id'],
        'permission': body['permission'],
        'scope': body['scope'],
        'effect': body['effect'],
        'revision': revision + 1,
      };
      if (index < 0) {
        grants.add(copy(result));
      } else {
        grants[index] = copy(result);
      }
      results[body['request_id']] = copy(result);
      if (loseAck) {
        loseAck = false;
        throw const ApiException(0, 'Synthetisch verlorene Erfolgsantwort');
      }
      return result;
    }
    throw ApiException(404, 'Unbekannter Testpfad: $path');
  }
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  setUpAll(() async {
    await (FontLoader(
      'Inter',
    )..addFont(rootBundle.load('assets/fonts/Inter.ttf'))).load();
  });

  Future<BusinessSession> show(
    WidgetTester tester,
    PermissionApi api, {
    double width = 1200,
  }) async {
    tester.view.physicalSize = Size(width, 1000);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    final session = BusinessSession(
      api: api,
      projects: [
        {'id': projectId, 'name': 'Synthetisches Projekt'},
      ],
    );
    await session.load();
    await tester.pumpWidget(
      MaterialApp(
        theme: officeTheme(),
        home: BusinessPermissionsPage(session: session),
      ),
    );
    await tester.pumpAndSettle();
    return session;
  }

  Future<void> close(
    WidgetTester tester,
    PermissionApi api,
    BusinessSession session,
  ) async {
    await tester.pumpWidget(const SizedBox());
    session.dispose();
    api.dispose();
  }

  Finder field(String label) => find.byWidgetPredicate(
    (widget) =>
        widget is DropdownButtonFormField<String> &&
        widget.decoration.labelText == label,
  );

  Future<void> tap(WidgetTester tester, Finder finder) async {
    await tester.ensureVisible(finder);
    await tester.pumpAndSettle();
    await tester.tap(finder);
    await tester.pumpAndSettle();
  }

  Future<void> pick(WidgetTester tester, Finder selector, String label) async {
    await tap(tester, selector);
    final menu = find.byType(Scrollable).last;
    final item = find.descendant(of: menu, matching: find.text(label));
    await tester.scrollUntilVisible(item, 220, scrollable: menu);
    await tester.pumpAndSettle();
    await tester.tap(item);
    await tester.pumpAndSettle();
  }

  Future<void> choosePortal(WidgetTester tester) async {
    await pick(tester, field('Benutzer'), 'worker@example.test · Technik');
    await pick(tester, field('Umfang'), 'Synthetisches Projekt');
    await pick(tester, field('Fachrecht'), 'Angebotsportal verwalten');
    await tap(tester, find.text('Regel prüfen'));
  }

  for (final width in [390.0, 1200.0]) {
    testWidgets(
      'Project-scoped portal permission uses real users and correct revisions at $width',
      (tester) async {
        final api = PermissionApi();
        final session = await show(tester, api, width: width);
        try {
          await choosePortal(tester);
          await tap(tester, find.text('Fachrecht speichern'));
          expect(api.grants.single['scope'], projectId);
          expect(api.grants.single['permission'], 'portal.manage');
          expect(api.grants.single['effect'], 'allow');
          expect(api.grants.single['revision'], 1);
          await tap(tester, find.text('Regel prüfen'));
          await pick(
            tester,
            find.byType(DropdownButtonFormField<String>).last,
            'Sperren',
          );
          await tap(tester, find.text('Fachrecht speichern'));
          final changes = api.calls
              .where((call) => call.body != null)
              .map((call) => call.body!)
              .toList();
          expect(changes.map((body) => body['revision']), [0, 1]);
          expect(api.grants.single['effect'], 'deny');
          expect(api.grants.single['revision'], 2);
          expect(
            api.calls.where((call) => call.path == '/api/users'),
            hasLength(5),
          );
          expect(tester.takeException(), isNull);
        } finally {
          await close(tester, api, session);
        }
      },
    );
  }

  testWidgets(
    'Lost permission acknowledgement resumes the original revision and request after reload',
    (tester) async {
      final api = PermissionApi()..loseAck = true;
      final session = await show(tester, api);
      try {
        await choosePortal(tester);
        await tap(tester, find.text('Fachrecht speichern'));
        final first = api.calls.lastWhere((call) => call.body != null).body!;
        expect(api.grants.single['revision'], 1);
        await tap(tester, find.text('Schließen'));
        await tap(tester, find.text('Regel prüfen'));
        expect(
          tester
              .widget<DropdownButtonFormField<String>>(
                find.byType(DropdownButtonFormField<String>).last,
              )
              .onChanged,
          isNull,
        );
        await tap(tester, find.text('Erneut senden'));
        expect(api.calls.lastWhere((call) => call.body != null).body!, first);
        expect(api.grants.single['revision'], 1);
        expect(api.results, hasLength(1));
      } finally {
        await close(tester, api, session);
      }
    },
  );

  testWidgets(
    'Fresh settings permission loss prevents writes and clears an open editor',
    (tester) async {
      final api = PermissionApi();
      final session = await show(tester, api);
      try {
        await choosePortal(tester);
        api.manage = false;
        await tap(tester, find.text('Fachrecht speichern'));
        expect(api.calls.where((call) => call.body != null), isEmpty);
        expect(find.textContaining('worker@example.test'), findsNothing);
        expect(
          find.text('Der Zugang ist nicht mehr verfügbar.'),
          findsOneWidget,
        );
        await tap(tester, find.text('Schließen'));
        expect(find.text('Kein Zugriff'), findsOneWidget);
      } finally {
        await close(tester, api, session);
      }
    },
  );

  testWidgets('A newer grant is not overwritten by an older reviewed version', (
    tester,
  ) async {
    final api = PermissionApi();
    api.grants.add({
      'id': 'existing',
      'user_id': workerId,
      'permission': 'portal.manage',
      'scope': projectId,
      'effect': 'allow',
      'revision': 3,
    });
    final session = await show(tester, api);
    try {
      await choosePortal(tester);
      await pick(
        tester,
        find.byType(DropdownButtonFormField<String>).last,
        'Sperren',
      );
      api.grants.single['revision'] = 4;
      await tap(tester, find.text('Fachrecht speichern'));
      expect(
        find.text('Berechtigung wurde inzwischen geändert'),
        findsOneWidget,
      );
      expect(
        api.calls.lastWhere((call) => call.body != null).body!['revision'],
        3,
      );
      expect(api.grants.single['effect'], 'allow');
      expect(api.grants.single['revision'], 4);
    } finally {
      await close(tester, api, session);
    }
  });

  testWidgets(
    'Delegated settings access cannot bypass the owner-only user list',
    (tester) async {
      final api = PermissionApi()..userAccess = false;
      final session = await show(tester, api);
      try {
        expect(find.textContaining('Nur die Geschäftsführung'), findsOneWidget);
        expect(find.text('Regel prüfen'), findsNothing);
        expect(find.byType(DropdownButtonFormField<String>), findsNothing);
        expect(api.calls.where((call) => call.body != null), isEmpty);
      } finally {
        await close(tester, api, session);
      }
    },
  );

  testWidgets(
    'An unavailable fresh capability check cannot dispatch a permission change',
    (tester) async {
      final api = PermissionApi();
      final session = await show(tester, api);
      try {
        await choosePortal(tester);
        api.metadataUnavailable = true;
        await tap(tester, find.text('Fachrecht speichern'));
        expect(api.calls.where((call) => call.body != null), isEmpty);
        expect(find.textContaining('aktuellen Berechtigungen'), findsOneWidget);
        api.metadataUnavailable = false;
        await tap(tester, find.text('Erneut senden'));
        expect(api.grants, hasLength(1));
      } finally {
        await close(tester, api, session);
      }
    },
  );

  testWidgets(
    'Losing owner-only user-list access while the editor is open prevents a write',
    (tester) async {
      final api = PermissionApi();
      final session = await show(tester, api);
      try {
        await choosePortal(tester);
        api.userAccess = false;
        await tap(tester, find.text('Fachrecht speichern'));
        expect(api.calls.where((call) => call.body != null), isEmpty);
        expect(find.textContaining('Nur die Geschäftsführung'), findsOneWidget);
        await tap(tester, find.text('Schließen'));
        expect(find.byType(DropdownButtonFormField<String>), findsNothing);
      } finally {
        await close(tester, api, session);
      }
    },
  );

  testWidgets(
    'Older servers hide the portal right while retaining ordinary permission choices',
    (tester) async {
      final api = PermissionApi()..portal = false;
      final session = await show(tester, api);
      try {
        final options = tester.widget<DropdownButton<String>>(
          find.descendant(
            of: field('Fachrecht'),
            matching: find.byType(DropdownButton<String>),
          ),
        );
        expect(
          options.items!.map((item) => item.value),
          isNot(contains('portal.manage')),
        );
        expect(
          options.items!.map((item) => item.value),
          containsAll(['finance.read', 'finance.write', 'projects.manage']),
        );
        final users = tester.widget<DropdownButton<String>>(
          find.descendant(
            of: field('Benutzer'),
            matching: find.byType(DropdownButton<String>),
          ),
        );
        expect(
          users.items!.map((item) => item.value),
          isNot(contains(ownerId)),
        );
        api.readOnly = true;
        await session.load();
        await tester.pumpAndSettle();
        expect(
          tester
              .widget<DropdownButtonFormField<String>>(field('Benutzer'))
              .onChanged,
          isNull,
        );
        expect(
          tester
              .widget<FilledButton>(
                find.widgetWithText(FilledButton, 'Regel prüfen'),
              )
              .onPressed,
          isNull,
        );
      } finally {
        await close(tester, api, session);
      }
    },
  );
  testWidgets(
    'Accounting grants are available only globally and retain their explicit scope',
    (tester) async {
      final api = PermissionApi();
      final session = await show(tester, api);
      try {
        await pick(tester, field('Benutzer'), 'worker@example.test · Technik');
        await pick(tester, field('Fachrecht'), 'EÜR-Vorbereitung lesen');
        await tap(tester, find.text('Regel prüfen'));
        await tap(tester, find.text('Fachrecht speichern'));
        expect(api.grants.single['permission'], 'accounting.read');
        expect(api.grants.single['scope'], '*');
        await pick(tester, field('Umfang'), 'Synthetisches Projekt');
        final options = tester.widget<DropdownButton<String>>(
          find.descendant(
            of: field('Fachrecht'),
            matching: find.byType(DropdownButton<String>),
          ),
        );
        expect(
          options.items!.any(
            (item) => '${item.value}'.startsWith('accounting.'),
          ),
          false,
        );
        expect(
          tester
              .widget<FilledButton>(
                find.widgetWithText(FilledButton, 'Regel prüfen'),
              )
              .onPressed,
          isNull,
        );
      } finally {
        await close(tester, api, session);
      }
    },
  );

  testWidgets(
    'Older accounting servers do not offer new administrative rights',
    (tester) async {
      final api = PermissionApi()..accounting = false;
      final session = await show(tester, api);
      try {
        final options = tester.widget<DropdownButton<String>>(
          find.descendant(
            of: field('Fachrecht'),
            matching: find.byType(DropdownButton<String>),
          ),
        );
        expect(
          options.items!.any(
            (item) => '${item.value}'.startsWith('accounting.'),
          ),
          false,
        );
        expect(
          options.items!.map((item) => item.value),
          contains('finance.read'),
        );
      } finally {
        await close(tester, api, session);
      }
    },
  );
}

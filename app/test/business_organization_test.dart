import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:smartplan_office/api.dart';
import 'package:smartplan_office/business_organization.dart';
import 'package:smartplan_office/business_session.dart';
import 'package:smartplan_office/business_shell.dart';
import 'package:smartplan_office/design.dart';

Map<String, dynamic> copyMap(Map<String, dynamic> value) =>
    jsonDecode(jsonEncode(value)) as Map<String, dynamic>;

class OrganizationApi extends OfficeApi {
  OrganizationApi() : super(apiVersion: 'v1') {
    token = 'synthetic-session';
  }
  bool feature = true, finance = false, readonly = false, loseAck = false;
  bool settingsAccess = true;
  bool simulateTimePause = false;
  int timeAttempt = 0;
  int employeeCount = 0;
  final calls = <({String path, Map<String, dynamic>? body})>[];
  final receipts = <String, Map<String, dynamic>>{};
  Map<String, dynamic> configuration = {
    'revision': 0,
    'configured': false,
    'needs': {
      'has_employees': false,
      'uses_inventory': false,
      'project_work': true,
      'uses_finance': true,
      'works_with_tax_advisor': false,
    },
    'modules': {
      for (final key in organizationModules.keys)
        key: {'visible': null, 'enabled': true},
    },
  };

  Map<String, dynamic> view() {
    final needs = businessMap(configuration['needs']);
    final choices = businessMap(configuration['modules']);
    final suggested = {
      'personnel': needs['has_employees'] == true || employeeCount > 0,
      'material': needs['uses_inventory'] == true,
      'planning': needs['project_work'] == true,
      'documents': needs['uses_finance'] == true,
      'finance': needs['uses_finance'] == true,
    };
    return {
      ...copyMap(configuration),
      'active_employee_count': employeeCount,
      'modules': {
        for (final entry in organizationModules.entries)
          entry.key: {
            'label': entry.value,
            'visible': choices[entry.key]['visible'] ?? suggested[entry.key],
            'visibility_override': choices[entry.key]['visible'],
            'suggested': suggested[entry.key],
            'enabled': choices[entry.key]['enabled'],
          },
      },
    };
  }

  @override
  Future<dynamic> call(String path, [Map<String, dynamic>? body]) async {
    calls.add((path: path, body: body == null ? null : copyMap(body)));
    if (path == '/api/business/capabilities') {
      return {
        'storage_version': 7,
        'compatibility_mode': readonly ? 'legacy' : 'business',
        'readonly': readonly,
        'generation': 1,
        'capabilities': [
          'business_foundation',
          'business_organization',
          'business_planning',
          'business_time',
          'business_inventory',
          'business_documents',
          'business_finance',
        ],
        'permissions': [
          if (settingsAccess) 'settings.manage',
          'time.own',
          'personnel.read',
          'personnel.manage',
          'planning.read',
          'planning.write',
          'inventory.read',
          if (finance) 'finance.read',
        ],
        'features': [if (feature) 'organization_modules'],
        if (feature)
          'organization': {
            'revision': configuration['revision'],
            'configured': configuration['configured'],
            'modules': {
              for (final entry in businessMap(view()['modules']).entries)
                entry.key: {
                  'visible': entry.value['visible'],
                  'enabled': entry.value['enabled'],
                },
            },
          },
      };
    }
    if (path == '/api/business/organization') {
      if (body == null) return view();
      final request = body['request_id'] as String;
      if (receipts.containsKey(request)) return copyMap(receipts[request]!);
      configuration = {
        'revision': (configuration['revision'] as int) + 1,
        'configured': true,
        'needs': body['needs'],
        'modules': body['modules'],
      };
      receipts[request] = view();
      if (loseAck) {
        loseAck = false;
        throw const ApiException(0, 'Synthetisch verlorene Erfolgsantwort');
      }
      return view();
    }
    if (path == '/api/business/overview')
      return {'projects': [], 'statuses': []};
    if (path == '/api/business/employees' && body != null) employeeCount = 1;
    if (path == '/api/business/time/events' &&
        simulateTimePause &&
        body != null) {
      timeAttempt++;
      if (timeAttempt == 1)
        throw const ApiException(0, 'Erfolgsantwort verloren');
      if (timeAttempt == 2) throw const ApiException(423, 'Modul pausiert');
    }
    return {'items': []};
  }
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  setUpAll(() async {
    await (FontLoader(
      'Inter',
    )..addFont(rootBundle.load('assets/fonts/Inter.ttf'))).load();
  });

  test(
    'Company choices preserve permission and legacy server boundaries',
    () async {
      final api = OrganizationApi();
      final session = BusinessSession(api: api);
      addTearDown(session.dispose);
      addTearDown(api.dispose);
      await session.load();
      expect(session.sectionVisible('personnel'), isFalse);
      expect(session.sectionEnabled('personnel'), isTrue);
      expect(session.sectionVisible('finance'), isTrue);
      expect(session.can('finance.read'), isFalse);
      api.employeeCount = 1;
      await session.load();
      expect(session.sectionVisible('personnel'), isTrue);
      api.configuration['modules']['personnel']['visible'] = false;
      await session.load();
      expect(session.sectionVisible('personnel'), isFalse);
      api.feature = false;
      await session.load();
      expect(session.sectionVisible('personnel'), isTrue);
      expect(session.organizationModules, isEmpty);
      session.revoke();
      expect(session.organizationModules, isEmpty);
      expect(session.can('finance.read'), isFalse);
    },
  );

  test(
    'Inactive modules block new commands, retain reads and remain configurable',
    () async {
      final api = OrganizationApi();
      for (final value in (api.configuration['modules'] as Map).values) {
        value['enabled'] = false;
      }
      final session = BusinessSession(api: api);
      addTearDown(session.dispose);
      addTearDown(api.dispose);
      await session.load();
      for (final route in [
        '/employees',
        '/absences',
        '/shifts',
        '/time/events',
        '/resources',
        '/appointments',
        '/planning/conflicts',
        '/inventory/movements',
        '/budgets',
        '/projects/${'a' * 32}/changes',
        '/documents',
        '/articles',
        '/services',
        '/templates',
        '/text-blocks',
        '/commercial/pricing/preview',
        '/finance/payments',
      ]) {
        await expectLater(
          session.command(route, route, {}),
          throwsA(isA<ApiException>().having((e) => e.status, 'status', 423)),
        );
      }
      expect(api.calls.where((call) => call.body != null), isEmpty);
      await session.read('/employees');
      await session.read('/finance/payments');
      await session.command('branding', '/settings/branding', {});
      await session.command('commercial-settings', '/commercial/settings', {});
      expect(api.calls.last.path, '/api/business/commercial/settings');
      for (final action in ['apply', 'offer']) {
        await expectLater(
          session.command(
            'import-$action',
            '/adapters/imports/${'a' * 32}/$action',
            {},
          ),
          throwsA(isA<ApiException>().having((e) => e.status, 'status', 423)),
        );
      }
    },
  );

  test(
    'Adding an employee refreshes the automatic navigation immediately',
    () async {
      final api = OrganizationApi();
      final session = BusinessSession(api: api);
      addTearDown(session.dispose);
      addTearDown(api.dispose);
      await session.load();
      expect(session.sectionVisible('personnel'), isFalse);
      await session.command('employee', '/employees', {
        'name': 'Synthetischer Mitarbeiter',
      });
      expect(session.sectionVisible('personnel'), isTrue);
    },
  );

  test(
    'Unconfirmed commands retain their exact identity through a module pause',
    () async {
      final api = OrganizationApi()..simulateTimePause = true;
      final session = BusinessSession(api: api);
      addTearDown(session.dispose);
      addTearDown(api.dispose);
      await session.load();
      const values = {'action': 'start'};
      await expectLater(
        session.command('timer', '/time/events', values),
        throwsA(isA<ApiException>()),
      );
      api.configuration['modules']['personnel']['enabled'] = false;
      await session.load();
      await expectLater(
        session.command('timer', '/time/events', values),
        throwsA(isA<ApiException>().having((e) => e.status, 'status', 423)),
      );
      expect(session.pending('timer'), isTrue);
      api.configuration['modules']['personnel']['enabled'] = true;
      await session.load();
      await session.command('timer', '/time/events', values);
      expect(session.pending('timer'), isFalse);
      final attempts = api.calls
          .where((call) => call.path == '/api/business/time/events')
          .toList();
      expect(attempts, hasLength(3));
      expect(
        attempts.map((call) => call.body).toList(),
        everyElement(attempts.first.body),
      );
    },
  );

  testWidgets(
    'Navigation follows company suggestions without granting finance access',
    (tester) async {
      tester.view.physicalSize = const Size(1200, 900);
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.resetPhysicalSize);
      addTearDown(tester.view.resetDevicePixelRatio);
      final api = OrganizationApi();
      final session = BusinessSession(api: api);
      await session.load();
      await tester.pumpWidget(
        MaterialApp(
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
      expect(find.text('Personal'), findsNothing);
      expect(find.text('Material'), findsNothing);
      expect(find.text('Finanzen'), findsNothing);
      api.employeeCount = 1;
      await session.load();
      await tester.pumpAndSettle();
      expect(find.text('Personal'), findsOneWidget);
      expect(find.text('Finanzen'), findsNothing);
      await tester.pumpWidget(const SizedBox());
      session.dispose();
      api.dispose();
    },
  );

  testWidgets(
    'Authorized hidden history remains reachable without settings permission',
    (tester) async {
      tester.view.physicalSize = const Size(1200, 900);
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.resetPhysicalSize);
      addTearDown(tester.view.resetDevicePixelRatio);
      final api = OrganizationApi()..settingsAccess = false;
      api.configuration['modules']['personnel']['enabled'] = false;
      final session = BusinessSession(api: api);
      await session.load();
      await tester.pumpWidget(
        MaterialApp(
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
      expect(find.text('Einstellungen'), findsNothing);
      expect(find.text('Personal'), findsNothing);
      await tester.tap(find.text('Weitere Bereiche'));
      await tester.pumpAndSettle();
      expect(find.text('Personal'), findsOneWidget);
      expect(find.text('Finanzen'), findsNothing);
      await tester.tap(find.text('Personal'));
      await tester.pumpAndSettle();
      expect(
        find.textContaining('Dieser Bereich ist fachlich deaktiviert.'),
        findsOneWidget,
      );
      expect(session.sectionVisible('personnel'), isFalse);
      expect(
        api.calls.any((call) => call.path == '/api/business/organization'),
        isFalse,
      );
      expect(api.calls.where((call) => call.body != null), isEmpty);
      expect(tester.takeException(), isNull);
      await tester.pumpWidget(const SizedBox());
      session.dispose();
      api.dispose();
    },
  );

  for (final width in [390.0, 1200.0]) {
    testWidgets(
      'Company settings preserve manual choices and exact retry at width $width',
      (tester) async {
        tester.view.physicalSize = Size(width, 900);
        tester.view.devicePixelRatio = 1;
        addTearDown(tester.view.resetPhysicalSize);
        addTearDown(tester.view.resetDevicePixelRatio);
        final api = OrganizationApi()..loseAck = true;
        final session = BusinessSession(api: api);
        await session.load();
        await tester.pumpWidget(
          MaterialApp(
            theme: officeTheme(),
            home: Scaffold(
              body: SingleChildScrollView(
                child: BusinessOrganizationPanel(session: session),
              ),
            ),
          ),
        );
        await tester.pumpAndSettle();
        final staffNeed = find.byKey(
          const ValueKey('organization-need-has_employees'),
        );
        await tester.ensureVisible(staffNeed);
        await tester.tap(staffNeed);
        await tester.pumpAndSettle();
        final visible = find.byKey(
          const ValueKey('organization-visible-personnel-0-auto'),
        );
        await tester.ensureVisible(visible);
        await tester.tap(visible);
        await tester.pumpAndSettle();
        await tester.tap(find.text('Ausblenden').last);
        await tester.pumpAndSettle();
        final active = find.byKey(
          const ValueKey('organization-enabled-personnel'),
        );
        await tester.ensureVisible(active);
        await tester.tap(active);
        await tester.pumpAndSettle();
        final save = find.byKey(const ValueKey('organization-save'));
        await tester.ensureVisible(save);
        await tester.tap(save);
        await tester.pumpAndSettle();
        expect(api.configuration['revision'], 1);
        final first = api.calls
            .where(
              (call) =>
                  call.path.endsWith('/organization') && call.body != null,
            )
            .last
            .body!;
        expect(first['needs']['has_employees'], isTrue);
        expect(first['modules']['personnel'], {
          'visible': false,
          'enabled': false,
        });
        expect((first['modules'] as Map).length, 5);
        expect(find.text('Speichern erneut bestätigen'), findsOneWidget);
        await tester.ensureVisible(save);
        await tester.pumpAndSettle();
        await tester.tap(save);
        await tester.pumpAndSettle();
        final repeated = api.calls
            .where(
              (call) =>
                  call.path.endsWith('/organization') && call.body != null,
            )
            .last
            .body;
        expect(repeated, first);
        expect(api.configuration['revision'], 1);
        expect(session.sectionVisible('personnel'), isFalse);
        expect(session.sectionEnabled('personnel'), isFalse);
        expect(tester.takeException(), isNull);
        await tester.pumpWidget(const SizedBox());
        session.dispose();
        api.dispose();
      },
    );
  }

  testWidgets(
    'Read-only configuration exposes authorized hidden history without saving',
    (tester) async {
      final api = OrganizationApi()..readonly = true;
      final session = BusinessSession(api: api);
      await session.load();
      String? opened;
      await tester.pumpWidget(
        MaterialApp(
          theme: officeTheme(),
          home: Scaffold(
            body: SingleChildScrollView(
              child: BusinessOrganizationPanel(
                session: session,
                onOpenSection: (section) => opened = section,
              ),
            ),
          ),
        ),
      );
      await tester.pumpAndSettle();
      final open = find.byKey(const ValueKey('organization-open-personnel'));
      await tester.ensureVisible(open);
      await tester.tap(open);
      expect(opened, 'personnel');
      expect(
        find.byKey(const ValueKey('organization-open-finance')),
        findsNothing,
      );
      final button = tester.widget<FilledButton>(
        find.byKey(const ValueKey('organization-save')),
      );
      expect(button.onPressed, isNull);
      expect(api.calls.where((call) => call.body != null), isEmpty);
      await tester.pumpWidget(const SizedBox());
      session.dispose();
      api.dispose();
    },
  );
}

import 'dart:async';
import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:smartplan_office/api.dart';
import 'package:smartplan_office/business_operations.dart';
import 'package:smartplan_office/business_session.dart';
import 'package:smartplan_office/design.dart';

final user = 'a' * 32, employee = 'b' * 32;
Map<String, dynamic> selection() => {
  'schema_version': 1,
  'items': [
    {'id': user, 'email': 'synthetic-hr@example.test'},
  ],
};

class AccountsApi extends OfficeApi {
  AccountsApi() : super(apiVersion: 'v1') {
    token = 'synthetic-employee-selection';
  }
  bool manage = true, lose = false;
  Completer<dynamic>? held;
  final requested = <String>[];
  final commands = <Map<String, dynamic>>[];
  final receipts = <String, Map<String, dynamic>>{};
  final records = <Map<String, dynamic>>[
    {
      'id': employee,
      'user_id': 'd' * 32,
      'name': 'Synthetic employee',
      'active': true,
      'weekly_minutes': 1200,
      'hourly_cost_minor': 2500,
      'employment_from': null,
      'employment_to': null,
      'revision': 1,
    },
  ];
  @override
  Future<dynamic> call(String path, [Map<String, dynamic>? body]) async {
    if (path.startsWith('/api/business/capabilities'))
      return {
        'storage_version': 7,
        'compatibility_mode': 'business',
        'generation': 1,
        'readonly': false,
        'features': ['employee_account_selection_v1'],
        'capabilities': ['business_planning'],
        'permissions': ['personnel.read', if (manage) 'personnel.manage'],
      };
    requested.add(path);
    if (path == '/api/users')
      throw const ApiException(403, 'User administration remains owner-only');
    if (path == '/api/business/employees/account-selection')
      return held == null ? selection() : await held!.future;
    if (body == null && path == '/api/business/employees')
      return {'items': records};
    if (body != null && path.startsWith('/api/business/employees')) {
      if (!manage) throw const ApiException(403, 'HR write revoked');
      final command = Map<String, dynamic>.from(jsonDecode(jsonEncode(body)));
      commands.add(command);
      final request = body['request_id'] as String;
      final value = receipts.putIfAbsent(
        request,
        () => {
          ...command,
          'id': employee,
          'revision': (body['revision'] as int? ?? 0) + 1,
        },
      );
      if (lose) {
        lose = false;
        throw const ApiException(0, 'Synthetic committed employee reply lost');
      }
      return value;
    }
    throw ApiException(404, 'Unhandled synthetic path: $path');
  }
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  test(
    'closed selection accepts actual identities and rejects extra private data',
    () {
      expect(employeeAccountSelection(selection()), selection()['items']);
      for (final v in <dynamic>[
        {'schema_version': 2, 'items': []},
        {...selection(), 'has_more': true},
        {
          'schema_version': 1,
          'items': [
            {'id': user, 'email': 'synthetic@example.test', 'role': 'owner'},
          ],
        },
        {
          'schema_version': 1,
          'items': [selection()['items'][0], selection()['items'][0]],
        },
        {
          'schema_version': 1,
          'items': [
            {'id': '../user', 'email': 'invalid'},
          ],
        },
      ]) {
        expect(() => employeeAccountSelection(v), throwsA(isA<ApiException>()));
      }
    },
  );
  Future<void> page(
    WidgetTester tester,
    AccountsApi api,
    Future<void> Function(BusinessSession) run,
  ) async {
    tester.view.physicalSize = const Size(390, 1000);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    final session = BusinessSession(api: api);
    await session.load();
    try {
      await tester.pumpWidget(
        MaterialApp(
          theme: officeTheme(),
          home: Scaffold(
            body: BusinessAreaPage(session: session, area: 'personnel'),
          ),
        ),
      );
      await tester.pumpAndSettle();
      await run(session);
    } finally {
      await tester.pumpWidget(const SizedBox.shrink());
      session.dispose();
      api.dispose();
    }
  }

  testWidgets(
    'HR creates at 390px with explicit account and unchanged retry without user admin',
    (tester) async {
      final api = AccountsApi();
      await page(tester, api, (session) async {
        await tester.tap(find.text('Neu anlegen'));
        await tester.pumpAndSettle();
        expect(find.text('Mitarbeiterprofil anlegen'), findsOneWidget);
        final chooser = find.widgetWithText(
          DropdownButtonFormField<String>,
          'Benutzerkonto',
        );
        expect(
          tester.widget<DropdownButtonFormField<String>>(chooser).initialValue,
          isNull,
        );
        await tester.tap(chooser);
        await tester.pumpAndSettle();
        await tester.tap(find.text('synthetic-hr@example.test').last);
        await tester.pumpAndSettle();
        await tester.enterText(
          find.widgetWithText(TextFormField, 'Name'),
          'Synthetic new profile',
        );
        api.lose = true;
        await tester.tap(find.text('Speichern'));
        await tester.pumpAndSettle();
        expect(api.commands, hasLength(1));
        await tester.tap(find.text('Erneut senden'));
        await tester.pumpAndSettle();
        expect(api.commands, hasLength(2));
        expect(api.commands.first, api.commands.last);
        expect(
          api.requested,
          contains('/api/business/employees/account-selection'),
        );
        expect(api.requested, isNot(contains('/api/users')));
        expect(tester.takeException(), isNull);
      });
    },
    variant: TargetPlatformVariant({
      TargetPlatform.windows,
      TargetPlatform.iOS,
    }),
  );
  testWidgets(
    'read-only HR reads profiles without any account directory request',
    (tester) async {
      final api = AccountsApi()..manage = false;
      await page(tester, api, (session) async {
        expect(find.text('Synthetic employee'), findsOneWidget);
        expect(find.text('Neu anlegen'), findsNothing);
        await tester.tap(find.text('Synthetic employee'));
        await tester.pumpAndSettle();
        expect(find.text('Name'), findsOneWidget);
        expect(api.requested, isNot(contains('/api/users')));
        expect(
          api.requested,
          isNot(contains('/api/business/employees/account-selection')),
        );
      });
    },
  );
  testWidgets(
    'held account result after manage revocation cannot open private editor',
    (tester) async {
      final api = AccountsApi()..held = Completer<dynamic>();
      await page(tester, api, (session) async {
        await tester.tap(find.text('Neu anlegen'));
        await tester.pump();
        api.manage = false;
        await session.load();
        await tester.pump();
        api.held!.complete(selection());
        await tester.pumpAndSettle();
        expect(find.text('Mitarbeiterprofil anlegen'), findsNothing);
        expect(find.text('synthetic-hr@example.test'), findsNothing);
        expect(api.commands, isEmpty);
      });
    },
  );
  testWidgets(
    'existing profile keeps its account and removes private form on manage loss',
    (tester) async {
      final api = AccountsApi();
      await page(tester, api, (session) async {
        await tester.tap(find.text('Synthetic employee'));
        await tester.pumpAndSettle();
        expect(find.text('Mitarbeiterprofil ändern'), findsOneWidget);
        expect(
          api.requested,
          isNot(contains('/api/business/employees/account-selection')),
        );
        api.manage = false;
        await session.load();
        await tester.pumpAndSettle();
        expect(find.text('Benutzerkonto'), findsNothing);
        expect(find.text('Name'), findsNothing);
        expect(api.commands, isEmpty);
      });
    },
  );
  testWidgets('session replacement closes only the owned private editor', (
    tester,
  ) async {
    final api = AccountsApi();
    await page(tester, api, (session) async {
      await tester.tap(find.text('Neu anlegen'));
      await tester.pumpAndSettle();
      expect(find.text('Mitarbeiterprofil anlegen'), findsOneWidget);
      final nextApi = AccountsApi()..manage = false;
      final next = BusinessSession(api: nextApi);
      await next.load();
      try {
        await tester.pumpWidget(
          MaterialApp(
            theme: officeTheme(),
            home: Scaffold(
              body: BusinessAreaPage(session: next, area: 'personnel'),
            ),
          ),
        );
        await tester.pumpAndSettle();
        expect(find.text('Mitarbeiterprofil anlegen'), findsNothing);
        expect(find.text('synthetic-hr@example.test'), findsNothing);
        expect(api.commands, isEmpty);
      } finally {
        await tester.pumpWidget(const SizedBox.shrink());
        next.dispose();
        nextApi.dispose();
      }
    });
  });
}

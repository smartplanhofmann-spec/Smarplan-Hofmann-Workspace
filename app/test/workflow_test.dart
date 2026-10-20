import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:smartplan_office/admin_pages.dart';
import 'package:smartplan_office/api.dart';
import 'package:smartplan_office/main.dart';
import 'package:smartplan_office/project_page.dart';

class TestApi extends OfficeApi {
  TestApi({this.role = 'owner'});
  final String role;
  final calls = <({String path, Map<String, dynamic>? body})>[];
  final users = <Map<String, dynamic>>[
    {
      'id': 'owner',
      'email': 'owner@example.test',
      'role': 'owner',
      'active': 1,
    },
    {
      'id': 'tech',
      'email': 'tech@example.test',
      'role': 'technician',
      'active': 1,
    },
  ];
  final assigned = <String>{};
  Map<String, dynamic> report = {
    'id': 'report-1',
    'status': 'draft',
    'content_hash': 'version-1',
    'content': {
      'kind': 'Servicebericht',
      'description': 'Beleuchtung geprüft',
      'created_at': '2026-10-14T08:00:00+00:00',
    },
  };
  @override
  Future<dynamic> call(String path, [Map<String, dynamic>? body]) async {
    calls.add((path: path, body: body));
    if (path == '/api/login') return {'token': 'test-session'};
    if (path == '/api/me')
      return {'id': 'owner', 'email': 'owner@example.test', 'role': role};
    if (path == '/api/logout') return {'ok': true};
    if (path == '/api/storage/status')
      return {'configured': false, 'connected': false};
    if (path == '/api/projects')
      return [
        {'id': 'project-1', 'name': 'Baustelle', 'customer': 'Musterkunde'},
      ];
    if (path == '/api/users' && body == null) return users;
    if (path == '/api/users' && body != null) {
      users.add({
        'id': 'new-user',
        'email': body['email'],
        'role': body['role'],
        'active': 1,
      });
      return {'id': 'new-user'};
    }
    if (path == '/api/projects/project-1/assignments')
      return users.where((u) => assigned.contains(u['id'])).toList();
    if (path == '/api/assignments') {
      if (body!['remove'] == true) {
        assigned.remove(body['user_id']);
      } else {
        assigned.add(body['user_id']);
      }
      return {'ok': true};
    }
    if (path == '/api/projects/project-1/reports' && body == null)
      return [report];
    if (path == '/api/reports/report-1') return report;
    if (path == '/api/reports/report-1/sign') {
      report = {
        ...report,
        'status': 'signed',
        'signer': body!['signer'],
        'signed_at': '2026-10-14T09:00:00+00:00',
      };
      return report;
    }
    throw StateError('Unexpected API request: $path');
  }

  void expireSession() {
    token = null;
    notifyListeners();
  }
}

void main() {
  Future<void> desktopSize(WidgetTester tester) async {
    tester.view.resetPhysicalSize();
    tester.view.physicalSize = const Size(1200, 1800);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
  }

  Future<void> login(WidgetTester tester, TestApi api) async {
    await desktopSize(tester);
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
  }

  testWidgets(
    'Owner can log in, open administration and create a validated user',
    (tester) async {
      final api = TestApi();
      await login(tester, api);
      await tester.tap(find.text('Benutzerverwaltung'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Benutzer anlegen'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Speichern'));
      await tester.pumpAndSettle();
      expect(
        api.calls.where((c) => c.path == '/api/users' && c.body != null),
        isEmpty,
      );
      await tester.enterText(
        find.byType(TextFormField).at(0),
        'new@example.test',
      );
      await tester.enterText(
        find.byType(TextFormField).at(1),
        'New-user-password-123',
      );
      await tester.tap(find.text('Speichern'));
      await tester.pumpAndSettle();
      expect(find.text('new@example.test'), findsOneWidget);
      expect(
        api.calls
            .lastWhere((c) => c.path == '/api/users' && c.body != null)
            .body!['role'],
        'technician',
      );
      expect(tester.takeException(), isNull);
    },
  );

  testWidgets('Project access can be granted and removed', (tester) async {
    final api = TestApi();
    await tester.pumpWidget(
      MaterialApp(
        home: AssignmentsPage(
          api: api,
          project: const {'id': 'project-1', 'name': 'Baustelle'},
        ),
      ),
    );
    await tester.pumpAndSettle();
    await tester.tap(find.byType(CheckboxListTile));
    await tester.pumpAndSettle();
    expect(api.assigned, contains('tech'));
    expect(
      tester.widget<CheckboxListTile>(find.byType(CheckboxListTile)).value,
      isTrue,
    );
    await tester.tap(find.byType(CheckboxListTile));
    await tester.pumpAndSettle();
    expect(api.assigned, isEmpty);
    expect(
      api.calls.lastWhere((c) => c.path == '/api/assignments').body!['remove'],
      isTrue,
    );
  });

  testWidgets('Accountant can reopen reports but has no writing controls', (
    tester,
  ) async {
    await desktopSize(tester);
    final api = TestApi(role: 'accountant');
    await tester.pumpWidget(
      MaterialApp(
        home: ProjectPage(
          api: api,
          project: const {
            'id': 'project-1',
            'name': 'Baustelle',
            'customer': 'Kunde',
          },
          role: 'accountant',
        ),
      ),
    );
    await tester.pumpAndSettle();
    await tester.tap(find.text('Servicebericht'));
    await tester.pumpAndSettle();
    expect(find.text('PDF ansehen / speichern'), findsOneWidget);
    expect(find.text('Unterschrift speichern'), findsNothing);
    expect(find.text('Dokument zur Prüfung erstellen'), findsNothing);
    expect(find.byTooltip('Projektzugriff verwalten'), findsNothing);
  });

  testWidgets(
    'A report needs name, drawn signature and confirmation before signing',
    (tester) async {
      await desktopSize(tester);
      final api = TestApi();
      await tester.pumpWidget(
        MaterialApp(
          home: ProjectPage(
            api: api,
            project: const {
              'id': 'project-1',
              'name': 'Baustelle',
              'customer': 'Kunde',
            },
            role: 'technician',
          ),
        ),
      );
      await tester.pumpAndSettle();
      await tester.tap(find.text('Servicebericht').first);
      await tester.pumpAndSettle();
      final save = find.widgetWithText(FilledButton, 'Unterschrift speichern');
      expect(tester.widget<FilledButton>(save).onPressed, isNull);
      await tester.enterText(find.byType(TextField), 'Kunde Muster');
      await tester.tap(find.byType(CheckboxListTile));
      await tester.pumpAndSettle();
      expect(tester.widget<FilledButton>(save).onPressed, isNull);
      final canvas = find.byWidgetPredicate(
        (w) => w is CustomPaint && w.painter is SignaturePainter,
      );
      await tester.drag(canvas, const Offset(100, 30));
      await tester.pumpAndSettle();
      expect(tester.widget<FilledButton>(save).onPressed, isNotNull);
      await tester.tap(save);
      await tester.pumpAndSettle();
      expect(api.report['status'], 'signed');
      final body = api.calls.lastWhere((c) => c.path.endsWith('/sign')).body!;
      expect(body['content_hash'], 'version-1');
      expect(body['strokes'], isNotEmpty);
      expect(find.text('Unterschrift speichern'), findsNothing);
      expect(find.text('Neuen Entwurf erstellen'), findsOneWidget);
    },
  );

  testWidgets('Expired session closes administration and returns to login', (
    tester,
  ) async {
    final api = TestApi();
    await login(tester, api);
    await tester.tap(find.text('Benutzerverwaltung'));
    await tester.pumpAndSettle();
    api.expireSession();
    await tester.pumpAndSettle();
    expect(find.text('Anmelden'), findsOneWidget);
    expect(
      find.text('Sitzung beendet. Bitte erneut anmelden.'),
      findsOneWidget,
    );
    expect(find.text('Benutzerverwaltung'), findsNothing);
  });

  testWidgets('Technician home has no owner administration or OneDrive setup', (
    tester,
  ) async {
    final api = TestApi(role: 'technician');
    await login(tester, api);
    expect(find.text('Baustelle'), findsOneWidget);
    expect(find.text('Benutzerverwaltung'), findsNothing);
    expect(find.text('Projekt anlegen'), findsNothing);
    expect(find.text('Kunden'), findsNothing);
    expect(find.text('OneDrive Family verbinden'), findsNothing);
    expect(api.calls.where((c) => c.path == '/api/storage/status'), isEmpty);
  });
}

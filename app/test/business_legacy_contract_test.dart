import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:smartplan_office/design.dart';
import 'package:smartplan_office/home_views.dart';
import 'package:smartplan_office/project_page.dart';

import 'project_workspace_widget_test.dart' show WorkspaceApi, section;

/// Regression boundary before the additive business suite. Existing work and
/// access paths remain available without requiring a native billing rollout.
void main() {
  testWidgets(
    'Existing assigned project remains the entry to its real records',
    (tester) async {
      tester.view.physicalSize = const Size(1100, 840);
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.resetPhysicalSize);
      addTearDown(tester.view.resetDevicePixelRatio);
      Map<String, dynamic>? selected;
      await tester.pumpWidget(
        MaterialApp(
          theme: officeTheme(),
          home: WorkspaceView(
            user: const {
              'id': 'synthetic-tech',
              'email': 'tech@example.test',
              'role': 'technician',
            },
            projects: const [WorkspaceApi.project],
            busy: false,
            onRefresh: () {},
            onLogout: () {},
            onNewProject: () {},
            onConnectDrive: () {},
            onSelectStorage: (_) {},
            onUsers: () {},
            onCustomers: () {},
            onProject: (project) => selected = project,
          ),
        ),
      );
      await tester.pumpAndSettle();
      await tester.tap(find.byKey(const ValueKey('project-card-project-1')));
      expect(selected?['id'], 'project-1');
      expect(find.text('Benutzerverwaltung'), findsNothing);
      expect(find.text('Projekt anlegen'), findsNothing);
      expect(tester.takeException(), isNull);
    },
  );

  testWidgets('Flexible project work does not require a quote or a payment', (
    tester,
  ) async {
    tester.view.physicalSize = const Size(1100, 1100);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    final api = WorkspaceApi()..token = 'synthetic-existing-session';
    addTearDown(api.dispose);
    api.items['tasks']!.add({
      'id': 'a' * 32,
      'project_id': 'project-1',
      'title': 'Erstbesichtigung ohne vorheriges Angebot',
      'details': 'Ablauf bleibt frei.',
      'status': 'todo',
      'priority': 'normal',
      'due_date': null,
      'assignee_id': null,
      'revision': 1,
    });
    await tester.pumpWidget(
      MaterialApp(
        theme: officeTheme(),
        home: ProjectPage(
          api: api,
          project: WorkspaceApi.project,
          role: 'owner',
        ),
      ),
    );
    await tester.pumpAndSettle();
    await section(tester, 'Aufgaben');
    expect(find.text('Erstbesichtigung ohne vorheriges Angebot'), findsWidgets);
    expect(api.writes, isEmpty);
    expect(tester.takeException(), isNull);
    await tester.pumpWidget(const SizedBox());
  });
}

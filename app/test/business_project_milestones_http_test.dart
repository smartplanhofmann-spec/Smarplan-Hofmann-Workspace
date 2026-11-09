@Tags(['posix_backend'])
library;

import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:smartplan_office/api.dart';
import 'package:smartplan_office/business_project_milestone_contract.dart';
import 'package:smartplan_office/business_session.dart';
import 'package:smartplan_office/business_widgets.dart';
import 'package:smartplan_office/project_workspace_page.dart';

import 'backend_integration_test.dart' show BackendHttp;
import 'import_backend_integration_test.dart' show fixture;

class MilestoneHttpApi extends OfficeApi {
  MilestoneHttpApi(String base) : super(baseUrl: base, apiVersion: 'v1');
  bool loseNext = true;
  int inFlight = 0;
  final posts = <Map<String, dynamic>>[];

  @override
  Future<dynamic> call(String path, [Map<String, dynamic>? body]) async {
    inFlight++;
    try {
      final change = body != null && path.contains('/milestones');
      if (change)
        posts.add(Map<String, dynamic>.from(jsonDecode(jsonEncode(body))));
      final value = await super.call(path, body);
      if (change && loseNext) {
        loseNext = false;
        throw const ApiException(
          0,
          'Synthetisch verlorene echte HTTP-Bestätigung',
        );
      }
      return value;
    } finally {
      inFlight--;
    }
  }
}

Future<void> waitFor(WidgetTester t, bool Function() done) async {
  for (var i = 0; i < 600 && !done(); i++) {
    await t.runAsync(
      () => Future<void>.delayed(const Duration(milliseconds: 20)),
    );
    await t.pump(const Duration(milliseconds: 16));
  }
  expect(done(), isTrue, reason: 'The expected HTTP/UI state did not arrive');
}

Future<void> httpClick(WidgetTester t, Finder target) async {
  await t.ensureVisible(target);
  await t.tap(target);
  await t.pump();
}

void main() {
  testWidgets(
    'actual project navigation and HTTP create retry preserve CRLF, manual status and history at 390px',
    (t) async {
      final backend = Directory(
        Platform.environment['SMARTPLAN_TEST_BACKEND'] ?? '../backend',
      ).absolute;
      final python =
          Platform.environment['SMARTPLAN_TEST_PYTHON'] ??
          '${backend.path}/.venv/bin/python';
      final temp = (await t.runAsync(
        () => Directory.systemTemp.createTemp('milestones-native-http-'),
      ))!;
      Process? process;
      StreamIterator<String>? output;
      StreamSubscription<String>? errors;
      MilestoneHttpApi? api;
      BusinessSession? session;
      final diagnostics = StringBuffer();
      await t.binding.setSurfaceSize(const Size(390, 844));
      try {
        final hello = await t.runAsync(() async {
          final source = fixture.replaceFirst('app = create_app(', '''
from business_schema import ensure_schema
ensure_schema(office, activate=True)
from project_workspace import ProjectWorkspace
import uuid
ProjectWorkspace(office).save_item(user, project, 'tasks', dict(
    request_id=uuid.uuid4().hex, title='Bestehende Aufgabe', details='Unverändert erhalten',
    status='todo', priority='normal', due_date='2026-11-30', assignee_id=user['id']))
app = create_app(''');
          process = await Process.start(python, [
            '-u',
            '-c',
            source,
            temp.path,
          ], workingDirectory: backend.path);
          errors = process!.stderr
              .transform(utf8.decoder)
              .listen(diagnostics.write);
          output = StreamIterator(
            process!.stdout
                .transform(utf8.decoder)
                .transform(const LineSplitter()),
          );
          expect(
            await output!.moveNext().timeout(const Duration(seconds: 30)),
            isTrue,
            reason: '$diagnostics',
          );
          return Map<String, dynamic>.from(jsonDecode(output!.current));
        });
        await HttpOverrides.runWithHttpOverrides(() async {
          api = MilestoneHttpApi('http://127.0.0.1:${hello!['port']}')
            ..token = hello['token'];
          final project = hello['project_id'] as String,
              actor = hello['user']['id'] as String;
          session = BusinessSession(api: api!, projectId: project);
          await t.runAsync(() => session!.load());
          expect(
            session!.hasFeature('project_milestones'),
            isTrue,
            reason: session!.error,
          );
          final before = await t.runAsync(
            () => session!.legacyRead('/api/projects/$project/workspace'),
          );
          await t.pumpWidget(
            MaterialApp(
              home: ProjectWorkspacePage(
                api: api!,
                project: Map<String, dynamic>.from(hello['projects'][0]),
                role: 'owner',
                reportsBuilder: (_) => const SizedBox(),
              ),
            ),
          );
          final navigation = find.byType(DropdownButtonFormField<int>);
          await waitFor(
            t,
            () => navigation.evaluate().isNotEmpty && api!.inFlight == 0,
          );
          await httpClick(t, navigation);
          await t.pumpAndSettle();
          final milestones = find.text('Meilensteine').hitTestable();
          await t.scrollUntilVisible(
            milestones,
            160,
            scrollable: find.byType(Scrollable).last,
          );
          await httpClick(t, milestones.last);
          await waitFor(
            t,
            () => find.text('Noch keine Meilensteine').evaluate().isNotEmpty,
          );
          await httpClick(t, find.text('Meilenstein anlegen'));
          await waitFor(
            t,
            () => find.byType(BusinessEditor).evaluate().isNotEmpty,
          );
          await t.pumpAndSettle();
          const title = '  Freigabe Süd 🚧  ', detail = 'Original prüfen.\r\n';
          await t.enterText(find.byType(TextFormField).at(0), title);
          await t.enterText(find.byType(TextFormField).at(1), detail);
          await t.enterText(find.byType(TextFormField).at(2), '30.11.2026');
          await httpClick(
            t,
            find.byType(DropdownButtonFormField<String>).first,
          );
          await t.pumpAndSettle();
          await httpClick(t, find.text('synthetic@example.test').last);
          await t.pumpAndSettle();
          await httpClick(t, find.widgetWithText(FilledButton, 'Speichern'));
          await waitFor(
            t,
            () => find
                .text('Synthetisch verlorene echte HTTP-Bestätigung')
                .evaluate()
                .isNotEmpty,
          );
          expect(api!.posts, hasLength(1));
          final original = Map<String, dynamic>.from(api!.posts.single);
          expect(original['title'], title);
          expect(original['details'], detail);
          expect(original['assignee_id'], actor);
          await httpClick(t, find.text('Schließen'));
          await waitFor(
            t,
            () =>
                find.byType(BusinessEditor).evaluate().isEmpty &&
                api!.inFlight == 0,
          );
          await httpClick(t, find.text('Anlage fortsetzen'));
          await waitFor(
            t,
            () => find.text('Erneut senden').evaluate().isNotEmpty,
          );
          await t.pumpAndSettle();
          expect(
            t.widget<TextFormField>(find.byType(TextFormField).first).enabled,
            isFalse,
          );
          await httpClick(
            t,
            find.widgetWithText(FilledButton, 'Erneut senden'),
          );
          await waitFor(
            t,
            () =>
                find.byType(BusinessEditor).evaluate().isEmpty &&
                api!.inFlight == 0,
          );
          expect(api!.posts, [original, original]);
          final path = '/projects/$project/milestones';
          final first = milestoneList(
            await t.runAsync(() => session!.read(path)),
            project,
          ).single;
          expect(first['revision'], 1);
          expect(first['title'], title);
          await httpClick(t, find.text('Bearbeiten'));
          await waitFor(
            t,
            () => find.byType(BusinessEditor).evaluate().isNotEmpty,
          );
          await t.pumpAndSettle();
          await httpClick(t, find.byType(DropdownButtonFormField<String>).last);
          await t.pumpAndSettle();
          await httpClick(t, find.text('Erreicht').last);
          await t.pumpAndSettle();
          await httpClick(t, find.widgetWithText(FilledButton, 'Speichern'));
          await waitFor(
            t,
            () =>
                find.byType(BusinessEditor).evaluate().isEmpty &&
                api!.inFlight == 0,
          );
          final current = milestoneList(
            await t.runAsync(() => session!.read(path)),
            project,
          ).single;
          expect(current['status'], 'achieved');
          expect(current['revision'], 2);
          expect(current['title'], title);
          expect(current['details'], detail);
          final history = milestoneHistory(
            await t.runAsync(
              () => session!.read('$path/${current['id']}/history'),
            ),
            project,
            current['id'],
            anchor: first,
          );
          expect(history.first, first);
          expect(history.last, current);
          final after = await t.runAsync(
            () => session!.legacyRead('/api/projects/$project/workspace'),
          );
          expect((before as Map)['open_tasks'], isNotEmpty);
          for (final field in [
            'counters',
            'open_tasks',
            'upcoming_appointments',
          ]) {
            expect((after as Map)[field], before[field]);
          }
          await httpClick(t, find.text('Änderungshistorie · Revision 2'));
          await waitFor(
            t,
            () => find
                .text('Meilenstein: Änderungshistorie')
                .evaluate()
                .isNotEmpty,
          );
          await t.pumpAndSettle();
          expect(find.textContaining('Revision 2 · Erreicht'), findsOneWidget);
          await t.scrollUntilVisible(
            find.textContaining('Revision 1 · Geplant'),
            180,
            scrollable: find
                .descendant(
                  of: find.byType(AlertDialog),
                  matching: find.byType(Scrollable),
                )
                .first,
          );
          expect(find.textContaining('Revision 1 · Geplant'), findsOneWidget);
          expect(api!.posts, hasLength(3));
          expect(t.takeException(), isNull);
        }, BackendHttp());
      } finally {
        await t.pumpWidget(const SizedBox());
        session?.dispose();
        api?.dispose();
        await t.binding.setSurfaceSize(null);
        await t.runAsync(() async {
          process?.kill();
          await process?.exitCode;
          await output?.cancel();
          await errors?.cancel();
          await temp.delete(recursive: true);
        });
      }
    },
  );
}

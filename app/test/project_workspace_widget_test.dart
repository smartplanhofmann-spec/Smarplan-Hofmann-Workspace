import 'dart:convert';
import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:smartplan_office/api.dart';
import 'package:smartplan_office/project_page.dart';
import 'package:smartplan_office/project_workspace_page.dart';
import 'package:smartplan_office/offline_plans.dart';

import 'workflow_test.dart' show TestApi, openProjectReports;
import 'offline_plans_test.dart' show TestDevice, idle;

/// All records are synthetic. Requests use the production revision/request-ID
/// contract; no customer files, URLs or calendar applications are contacted.
class WorkspaceApi extends TestApi {
  WorkspaceApi({super.role});
  static const project = {
    'id': 'project-1',
    'name': 'Service und Aufmaß',
    'customer': 'Fiktive Hausverwaltung',
  };
  final profile = <String, dynamic>{
    'revision': 0,
    'project_id': 'project-1',
    'description': 'Zuerst Bestand prüfen; Ablauf bleibt offen.',
    'site_address': 'Musterstraße 1, 12345 Teststadt',
    'phase': 'planning',
    'deposit_status': 'not_recorded',
    'materials_status': 'not_recorded',
    'start_date': null,
    'end_date': null,
  };
  final items = <String, List<Map<String, dynamic>>>{
    'tasks': [],
    'appointments': [],
    'diary': [],
    'links': [],
  };
  final receipts = <String, Map<String, dynamic>>{};
  final writes = <Map<String, dynamic>>[];
  bool unsupported = false,
      revoked = false,
      loseNextAck = false,
      conflictNext = false;
  int sequence = 0;
  bool network = true;
  int networkCalls = 0;

  @override
  Future<dynamic> call(String path, [Map<String, dynamic>? body]) async {
    const base = '/api/projects/project-1';
    networkCalls++;
    if (!network) throw const ApiException(0, 'Synthetic offline connection');
    if (path == '/api/offline/access')
      return {
        'token': 'synthetic-offline-token',
        'expires_at': DateTime.now()
            .toUtc()
            .add(const Duration(days: 7))
            .toIso8601String(),
        'capabilities': ['offline_workspace', 'project_workspace'],
      };
    if (path == '/api/projects') return revoked ? [] : [project];
    if (path.startsWith('$base/workspace') ||
        [
          'tasks',
          'diary',
          'appointments',
          'links',
        ].any((kind) => path.startsWith('$base/$kind'))) {
      calls.add((path: path, body: body));
      if (revoked) throw const ApiException(403, 'Projektzugriff entzogen');
      if (unsupported) throw const ApiException(404, 'Route nicht verfügbar');
      if (body != null) {
        writes.add(Map<String, dynamic>.from(body));
        final id = body['request_id'] as String;
        expect(id, matches(RegExp(r'^[a-f0-9]{32}$')));
        if (receipts.containsKey(id))
          return Map<String, dynamic>.from(receipts[id]!);
        final kind = path.split('/')[4];
        final collection = items[kind];
        final current = kind == 'workspace'
            ? profile
            : path.split('/').length == 6
            ? collection!.firstWhere(
                (item) => item['id'] == path.split('/').last,
              )
            : null;
        if (conflictNext && current != null) {
          conflictNext = false;
          current['revision'] = (current['revision'] as int) + 1;
          current['details'] = 'Das Team hat zwischenzeitlich nachgemessen.';
          throw const ApiException(409, 'Eintrag wurde inzwischen geändert.');
        }
        if (current != null && body['revision'] != current['revision']) {
          throw const ApiException(409, 'Ausgangsversion veraltet');
        }
        final result = <String, dynamic>{
          ...?current,
          if (current == null)
            'id': (++sequence).toRadixString(16).padLeft(32, '0'),
          for (final entry in body.entries)
            if (!['request_id', 'revision'].contains(entry.key))
              entry.key: entry.value,
          'revision': (current?['revision'] as int? ?? 0) + 1,
        };
        if (current != null) {
          current
            ..clear()
            ..addAll(result);
        } else {
          collection!.add(result);
        }
        receipts[id] = Map<String, dynamic>.from(result);
        if (loseNextAck) {
          loseNextAck = false;
          throw const ApiException(0, 'Antwort unterbrochen');
        }
        return result;
      }
      if (path.endsWith('/workspace')) {
        final open = items['tasks']!
            .where((item) => ['todo', 'in_progress'].contains(item['status']))
            .toList();
        return {
          'project': project,
          'profile': Map<String, dynamic>.from(profile),
          'team': [
            {'id': 'a' * 32, 'email': 'leitung@example.test', 'role': 'owner'},
            {
              'id': 'b' * 32,
              'email': 'technik@example.test',
              'role': 'technician',
            },
          ],
          'counters': {
            'tasks_open': open.length,
            'tasks_overdue': 0,
            'appointments_upcoming': items['appointments']!
                .where((item) => item['status'] == 'scheduled')
                .length,
          },
          'open_tasks': open,
          'upcoming_appointments': items['appointments'],
          'latest_diary': items['diary']!.reversed.toList(),
          'links': items['links'],
        };
      }
      final kind = path.split('/')[4];
      return path.split('/').length == 6
          ? Map<String, dynamic>.from(
              items[kind]!.firstWhere(
                (item) => item['id'] == path.split('/').last,
              ),
            )
          : items[kind]!
                .map((item) => Map<String, dynamic>.from(item))
                .toList();
    }
    return super.call(path, body);
  }
}

/// Real encrypted workspace cache, paired only with synthetic in-process HTTP
/// replies. Extension methods deliberately stay real instead of being mocked.
class CacheFixture {
  final Directory folder;
  final WorkspaceApi api;
  final OfflinePlans repository;
  DateTime now = DateTime.now().toUtc();
  CacheFixture(this.folder, this.api, this.repository);
  static Future<CacheFixture> create() async {
    final folder = await Directory.systemTemp.createTemp(
      'smartplan-project-ui-',
    );
    final api = WorkspaceApi()..token = 'synthetic-online-session';
    api.profile['description'] = 'Lokal gesicherte Baustelle';
    api.profile['site_address'] = 'Private Testadresse';
    late CacheFixture fixture;
    final repo = OfflinePlans(
      api: api,
      transport: api,
      device: TestDevice(folder),
      clock: () => fixture.now,
    );
    fixture = CacheFixture(folder, api, repo);
    await repo.login({'id': 'a' * 32, 'role': 'owner'}, [WorkspaceApi.project]);
    await idle(repo);
    await repo.refreshWorkspace('project-1');
    await idle(repo);
    api.network = false;
    api.calls.clear();
    return fixture;
  }

  Future<void> close() async {
    await repository.flush();
    await idle(repository);
    repository.dispose();
    api.dispose();
    await folder.delete(recursive: true);
  }
}

Future<void> settleStorage(WidgetTester tester, bool Function() done) async {
  for (var attempt = 0; attempt < 300; attempt++) {
    await tester.runAsync(
      () => Future<void>.delayed(const Duration(milliseconds: 5)),
    );
    await tester.pump(const Duration(milliseconds: 20));
    if (done()) {
      await tester.pumpAndSettle();
      return;
    }
  }
  fail('Encrypted project UI operation did not complete');
}

Future<void> section(WidgetTester tester, String label) async {
  final picker = find.byType(DropdownButtonFormField<int>);
  if (picker.evaluate().isNotEmpty) {
    await tester.tap(picker);
    await tester.pumpAndSettle();
    await tester.tap(find.text(label).last);
  } else {
    final button = find.widgetWithText(TextButton, label).first;
    await tester.ensureVisible(button);
    await tester.pumpAndSettle();
    await tester.tap(button);
  }
  await tester.pumpAndSettle();
}

Future<void> enter(WidgetTester tester, String field, String value) async {
  final finder = find.byKey(ValueKey('workspace-field-$field'));
  await tester.ensureVisible(finder);
  await tester.pump();
  await tester.enterText(finder, value);
}

Future<void> save(WidgetTester tester) async {
  await tester.tap(find.widgetWithText(FilledButton, 'Speichern'));
  await tester.pumpAndSettle();
}

void main() {
  Future<void> mount(
    WidgetTester tester,
    WorkspaceApi api, {
    Size size = const Size(1280, 1000),
  }) async {
    tester.view.devicePixelRatio = 1;
    tester.view.physicalSize = size;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    await tester.pumpWidget(
      MaterialApp(
        home: ProjectPage(
          api: api,
          project: WorkspaceApi.project,
          role: api.role,
        ),
      ),
    );
    await tester.pumpAndSettle();
  }

  testWidgets(
    'A connected workday starts in the overview and records tasks, diary, appointments and document links in any order',
    (tester) async {
      final api = WorkspaceApi();
      await mount(tester, api);
      expect(find.text('Projekt und Baustelle'), findsOneWidget);
      expect(find.text('Fiktive Hausverwaltung'), findsOneWidget);
      expect(find.text('Dokument zur Prüfung erstellen'), findsNothing);
      expect(find.text('Anzahlung: Noch nicht erfasst'), findsOneWidget);
      await tester.tap(find.text('Aufgabe anlegen').first);
      await tester.pumpAndSettle();
      await enter(tester, 'title', 'Bestand im Erdgeschoss aufnehmen');
      await enter(tester, 'details', 'Vor Materialbestellung vor Ort prüfen.');
      await tester.ensureVisible(
        find.byKey(const ValueKey('workspace-field-assignee_id')),
      );
      await tester.pump();
      await tester.tap(
        find.byKey(const ValueKey('workspace-field-assignee_id')),
      );
      await tester.pumpAndSettle();
      await tester.tap(find.text('technik@example.test').last);
      await tester.pumpAndSettle();
      await enter(tester, 'due_date', '31.12.2030');
      await save(tester);
      expect(api.items['tasks'], hasLength(1));
      expect(api.items['tasks']!.single['assignee_id'], 'b' * 32);
      expect(
        api.profile['deposit_status'],
        'not_recorded',
        reason: 'A task must not require an offer, payment or material phase.',
      );

      await section(tester, 'Bautagebuch');
      await tester.tap(find.text('Tagesbericht erfassen'));
      await tester.pumpAndSettle();
      await enter(tester, 'entry_date', '24.10.2026');
      await enter(
        tester,
        'work_performed',
        'Bestand aufgenommen, Stromkreis geprüft.',
      );
      await enter(tester, 'issues', 'Abweichung vom gedruckten Plan.');
      await enter(tester, 'next_steps', 'Ausführung mit dem Kunden abstimmen.');
      await save(tester);
      expect(
        find.text('Bestand aufgenommen, Stromkreis geprüft.'),
        findsOneWidget,
      );
      expect(
        api.items['diary']!.single['issues'],
        'Abweichung vom gedruckten Plan.',
      );

      await section(tester, 'Termine');
      await tester.tap(find.text('Termin planen'));
      await tester.pumpAndSettle();
      await enter(tester, 'title', 'Abstimmung auf der Baustelle');
      await enter(tester, 'start_day', '31.12.2030');
      await enter(tester, 'start_time', '10:00');
      await enter(tester, 'end_day', '31.12.2030');
      await enter(tester, 'end_time', '11:00');
      await save(tester);
      expect(api.items['appointments'], hasLength(1));
      expect(
        DateTime.parse(api.items['appointments']!.single['start_at']).isUtc,
        isTrue,
      );

      await section(tester, 'Dokumente');
      await tester.tap(find.text('Dokumentlink hinzufügen').first);
      await tester.pumpAndSettle();
      await enter(tester, 'title', 'Vertrag zur Prüfung');
      await enter(tester, 'url', 'https://example.test/synthetic-contract');
      await save(tester);
      expect(find.text('Vertrag zur Prüfung'), findsOneWidget);
      expect(find.text('Link öffnen'), findsOneWidget);
      expect(api.items['links'], hasLength(1));
      await section(tester, 'Aufgaben');
      await tester.tap(find.byTooltip('Als erledigt markieren'));
      await tester.pumpAndSettle();
      expect(api.items['tasks']!.single['status'], 'done');
      await section(tester, 'Übersicht');
      await tester.scrollUntilVisible(
        find.text('Bestand aufgenommen, Stromkreis geprüft.'),
        400,
        scrollable: find.byType(Scrollable).last,
      );
      expect(
        find.text('Bestand aufgenommen, Stromkreis geprüft.'),
        findsOneWidget,
      );
      await openProjectReports(tester);
      expect(find.text('Servicebericht'), findsWidgets);
      expect(tester.takeException(), isNull);
    },
  );

  testWidgets(
    'A lost acknowledgement retries the same request without duplicating a task',
    (tester) async {
      final api = WorkspaceApi()..loseNextAck = true;
      await mount(tester, api);
      await tester.tap(find.text('Aufgabe anlegen').first);
      await tester.pumpAndSettle();
      await enter(tester, 'title', 'Einmaliger Aufmaßauftrag');
      await save(tester);
      expect(find.text('Einmaliger Aufmaßauftrag'), findsOneWidget);
      expect(api.items['tasks'], hasLength(1));
      await save(tester);
      expect(api.items['tasks'], hasLength(1));
      expect(api.writes[0]['request_id'], api.writes[1]['request_id']);
      expect(find.byType(AlertDialog), findsNothing);
    },
  );

  testWidgets(
    'A conflict keeps edits, requires comparison and uses the newly confirmed revision',
    (tester) async {
      final api = WorkspaceApi();
      api.items['tasks']!.add({
        'id': 'c' * 32,
        'revision': 1,
        'title': 'Bestand prüfen',
        'details': '',
        'status': 'todo',
        'priority': 'normal',
        'due_date': null,
        'assignee_id': null,
      });
      await mount(tester, api);
      await section(tester, 'Aufgaben');
      await tester.tap(find.text('Bestand prüfen'));
      await tester.pumpAndSettle();
      await enter(tester, 'details', 'Eigene Ergänzung bleibt erhalten.');
      api.conflictNext = true;
      await save(tester);
      expect(find.text('Eigene Ergänzung bleibt erhalten.'), findsOneWidget);
      expect(
        tester
            .widget<FilledButton>(
              find.widgetWithText(FilledButton, 'Speichern'),
            )
            .onPressed,
        isNull,
      );
      await tester.tap(find.text('Andere Fassung prüfen'));
      await tester.pumpAndSettle();
      expect(
        find.textContaining('Das Team hat zwischenzeitlich nachgemessen.'),
        findsOneWidget,
      );
      await tester.tap(find.text('Eigene Eingaben weiterverwenden'));
      await tester.pumpAndSettle();
      await save(tester);
      expect(
        api.items['tasks']!.single['details'],
        'Eigene Ergänzung bleibt erhalten.',
      );
      expect(api.writes.last['revision'], 2);
      expect(
        api.writes.first['request_id'],
        isNot(api.writes.last['request_id']),
      );
    },
  );

  testWidgets(
    'Old server fallback retains real reports, while project withdrawal hides the workspace',
    (tester) async {
      final api = WorkspaceApi()..unsupported = true;
      await mount(tester, api);
      expect(
        find.textContaining('erweiterte Projektmappe ist noch nicht verfügbar'),
        findsOneWidget,
      );
      expect(find.text('Aufgabe anlegen'), findsNothing);
      await openProjectReports(tester);
      expect(find.text('Servicebericht'), findsWidgets);
      api.revoked = true;
      await tester.tap(find.byTooltip('Projekt aktualisieren'));
      await tester.pumpAndSettle();
      expect(find.text('Servicebericht'), findsNothing);
      expect(find.textContaining('Projektzugriff'), findsOneWidget);
    },
  );

  testWidgets(
    'Narrow read-only projects expose all named registers without creating data',
    (tester) async {
      final api = WorkspaceApi(role: 'accountant');
      await mount(tester, api, size: const Size(390, 844));
      expect(find.byType(DropdownButtonFormField<int>), findsOneWidget);
      expect(find.text('Aufgabe anlegen'), findsNothing);
      expect(find.text('Projektdaten bearbeiten'), findsNothing);
      for (final label in ['Aufgaben', 'Termine', 'Bautagebuch', 'Dokumente']) {
        await section(tester, label);
        expect(find.byType(FilledButton), findsNothing);
        expect(tester.takeException(), isNull);
      }
      expect(api.writes, isEmpty);
    },
  );

  testWidgets(
    'Phone overview keeps equal compact counters, primary actions and the first task above the fold',
    (tester) async {
      final api = WorkspaceApi();
      api.profile['description'] = 'Lange synthetische Projektbeschreibung mit Bestand, Abstimmung und weiteren Einzelheiten, die erst bei Bedarf eingeblendet werden.';
      api.profile['site_address'] =
          'Musterstraße 1\nHinterhaus, zweiter Zugang\n12345 Teststadt';
      api.items['tasks']!.add({
        'id': 'e' * 32,
        'revision': 1,
        'title': 'Bestand vor Ort prüfen',
        'details': '',
        'status': 'todo',
        'priority': 'normal',
        'due_date': '2030-12-31',
        'assignee_id': 'b' * 32,
      });
      await mount(tester, api, size: const Size(390, 840));
      expect(find.text(api.profile['description']), findsNothing);
      expect(find.text('Phase: Klärung / Planung'), findsOneWidget);
      expect(find.text('Fiktive Hausverwaltung'), findsOneWidget);
      final metrics = [
        for (final kind in [
          'tasks_open',
          'tasks_overdue',
          'appointments_upcoming',
        ])
          tester.getRect(find.byKey(ValueKey('workspace-metric-$kind'))),
      ];
      expect(metrics[0].top, metrics[1].top);
      expect(metrics[1].top, metrics[2].top);
      expect(metrics[0].width, closeTo(metrics[2].width, .1));
      for (final label in [
        'Aufgabe anlegen',
        'Tagesbericht erfassen',
        'Termin planen',
      ]) {
        expect(find.text(label).hitTestable(), findsOneWidget);
      }
      expect(
        tester.getBottomRight(find.text('Bestand vor Ort prüfen')).dy,
        lessThan(840),
      );
      await tester.tap(find.text('Projekt und Baustelle'));
      await tester.pumpAndSettle();
      expect(find.text(api.profile['description']), findsOneWidget);
      expect(find.text('Projektdaten bearbeiten'), findsOneWidget);
      expect(tester.takeException(), isNull);
    },
  );

  testWidgets(
    'Cached offline workspace queues a task through encrypted storage and keeps reports online only',
    (tester) async {
      final fixture = (await tester.runAsync(CacheFixture.create))!;
      final api = fixture.api;
      final cache = fixture.repository;
      final callsBeforeEntry = api.networkCalls;
      try {
        await tester.pumpWidget(
          MaterialApp(
            home: ProjectPage(
              api: api,
              project: WorkspaceApi.project,
              role: 'owner',
              repository: cache,
              offlineMode: true,
            ),
          ),
        );
        await tester.pumpAndSettle();
        expect(find.text('Lokal gesicherte Baustelle'), findsOneWidget);
        expect(
          api.networkCalls,
          callsBeforeEntry,
          reason: 'Explicit offline entry must not wait for a network timeout.',
        );
        expect(find.byTooltip('Kunden zuordnen'), findsNothing);
        expect(find.byTooltip('Projektzugriff verwalten'), findsNothing);
        await tester.scrollUntilVisible(
          find.text('Aufgabe anlegen'),
          300,
          scrollable: find.byType(Scrollable).last,
        );
        await tester.tap(find.text('Aufgabe anlegen').first);
        await tester.pumpAndSettle();
        await enter(tester, 'title', 'Vor Ort ohne Empfang notiert');
        await tester.tap(find.widgetWithText(FilledButton, 'Speichern'));
        await settleStorage(
          tester,
          () => find.byType(AlertDialog).evaluate().isEmpty,
        );
        expect(cache.getWorkspace('project-1')!['tasks'], hasLength(1));
        expect(cache.getWorkspace('project-1')!['has_pending_changes'], isTrue);
        expect(find.textContaining('diesem Gerät'), findsWidgets);
        expect(api.writes, isEmpty);
        await section(tester, 'Berichte');
        expect(
          find.textContaining(
            'Berichte und Unterschriften benötigen eine Online-Anmeldung',
          ),
          findsOneWidget,
        );
        expect(
          api.calls.where((call) => call.path.endsWith('/reports')),
          isEmpty,
        );
      } finally {
        await settleStorage(tester, () => !cache.syncing);
        await tester.pumpWidget(const SizedBox());
        await tester.runAsync(fixture.close);
      }
    },
  );

  testWidgets(
    'Expired project access hides an open task form including its team dropdown',
    (tester) async {
      final fixture = (await tester.runAsync(CacheFixture.create))!;
      final cache = fixture.repository;
      try {
        await tester.pumpWidget(
          MaterialApp(
            home: ProjectPage(
              api: fixture.api,
              project: WorkspaceApi.project,
              role: 'owner',
              repository: cache,
              offlineMode: true,
            ),
          ),
        );
        await tester.pumpAndSettle();
        await tester.scrollUntilVisible(
          find.text('Aufgabe anlegen'),
          300,
          scrollable: find.byType(Scrollable).last,
        );
        await tester.tap(find.text('Aufgabe anlegen').first);
        await tester.pumpAndSettle();
        await enter(tester, 'title', 'Vertrauliche synthetische Aufgabe');
        final assignee = find.byKey(
          const ValueKey('workspace-field-assignee_id'),
        );
        FocusManager.instance.primaryFocus?.unfocus();
        await tester.pumpAndSettle();
        final dropdown = find.descendant(
          of: assignee,
          matching: find.byType(DropdownButton<String>),
        );
        await Scrollable.ensureVisible(tester.element(dropdown), alignment: .5);
        await tester.pumpAndSettle();
        await tester.tap(dropdown);
        await tester.pumpAndSettle();
        expect(find.text('technik@example.test'), findsOneWidget);
        fixture.now = fixture.now.add(const Duration(days: 7));
        cache.changed();
        await tester.pumpAndSettle();
        expect(find.text('Vertrauliche synthetische Aufgabe'), findsNothing);
        expect(find.text('Private Testadresse'), findsNothing);
        expect(find.text('Projektzugriff nicht verfügbar'), findsOneWidget);
        expect(fixture.api.writes, isEmpty);
        expect(tester.takeException(), isNull);
      } finally {
        await settleStorage(tester, () => !cache.syncing);
        await tester.pumpWidget(const SizedBox());
        await tester.runAsync(fixture.close);
      }
    },
  );

  testWidgets(
    'Calendar and external-link handoffs only run after explicit clicks',
    (tester) async {
      final api = WorkspaceApi();
      api.items['appointments']!.add({
        'id': 'd' * 32,
        'revision': 1,
        'title': 'Synthetischer Termin',
        'details': 'Nur nach eigener Bestätigung übertragen.',
        'status': 'scheduled',
        'start_at': '2030-12-31T10:00:00+00:00',
        'end_at': '2030-12-31T11:00:00+00:00',
      });
      final opened = <Uri>[];
      final exported = <String>[];
      await tester.pumpWidget(
        MaterialApp(
          home: ProjectWorkspacePage(
            api: api,
            project: WorkspaceApi.project,
            role: 'owner',
            reportsBuilder: (_) => const Text('Berichtsbereich'),
            openExternal: (uri) async {
              opened.add(uri);
              return true;
            },
            calendarExport: (item) async {
              exported.add(item['id']);
            },
          ),
        ),
      );
      await tester.pumpAndSettle();
      await section(tester, 'Termine');
      expect(opened, isEmpty);
      expect(exported, isEmpty);
      await tester.tap(find.text('Kalenderdatei speichern'));
      await tester.pumpAndSettle();
      expect(exported, ['d' * 32]);
      expect(opened, isEmpty);
      await tester.ensureVisible(find.text('In Google Kalender öffnen'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('In Google Kalender öffnen'));
      await tester.pumpAndSettle();
      expect(opened.single.host, 'calendar.google.com');
      expect(
        opened.single.queryParameters['dates'],
        '20301231T100000Z/20301231T110000Z',
      );
      expect(
        jsonEncode(opened.single.queryParameters),
        contains('Synthetischer Termin'),
      );
    },
  );
}

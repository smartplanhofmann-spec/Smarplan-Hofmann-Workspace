import 'dart:async';
import 'dart:io';
import 'dart:ui' as ui;

import 'package:flutter/material.dart';
import 'package:flutter/rendering.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:smartplan_office/api.dart';
import 'package:smartplan_office/business_finance.dart';
import 'package:smartplan_office/business_time.dart';
import 'package:smartplan_office/design.dart';
import 'package:smartplan_office/project_page.dart';
import 'package:smartplan_office/project_workspace_page.dart';

import 'project_workspace_widget_test.dart' show WorkspaceApi;

const businessTabs = [
  'Unterlagenfreigabe',
  'Belege',
  'Arbeitszeit',
  'Einsatzplanung',
  'Material',
  'Kalkulation',
  'Finanzen',
  'Dokumentation',
  'Fotos',
  'Wartung',
];
const allTabs = [...projectSections, ...businessTabs];
const rootCapture = ValueKey('project-tabs-capture');

class ProjectTabsApi extends WorkspaceApi {
  @override
  String get version => 'v1';
  final permissions = <String>{
    'documents.classify',
    'finance.read',
    'finance.write',
    'finance.approve',
    'time.own',
    'planning.read',
    'planning.write',
    'inventory.read',
    'inventory.write',
    'documents.read',
    'documents.write',
    'projects.manage',
  };
  final businessCalls = <({String path, Map<String, dynamic>? body})>[];
  final unexpected = <String>[];
  final failPaths = <String>{};
  Completer<dynamic>? pendingDocuments;
  int generation = 1;
  final documentId = 'd' * 32;
  final timeEntries = <Map<String, dynamic>>[];

  ProjectTabsApi() {
    token = 'synthetic-project-tabs-session';
    items['tasks']!.add({
      'id': '1' * 32,
      'title': 'Synthetische Projektaufgabe',
      'status': 'todo',
      'priority': 'normal',
      'revision': 1,
      'details': '',
      'due_date': null,
      'assignee_id': null,
    });
    items['appointments']!.add({
      'id': '2' * 32,
      'title': 'Synthetischer Projekttermin',
      'start_at': '2026-10-26T09:00:00Z',
      'end_at': '2026-10-26T10:00:00Z',
      'details': '',
      'status': 'scheduled',
      'revision': 1,
    });
    items['diary']!.add({
      'id': '3' * 32,
      'entry_date': '2026-10-26',
      'work_performed': 'Synthetische Tagebucharbeit',
      'issues': '',
      'next_steps': '',
      'weather': '',
      'revision': 1,
    });
    items['links']!.add({
      'id': '4' * 32,
      'title': 'Synthetische Projektunterlage',
      'url': 'https://example.invalid/synthetic',
      'category': 'document',
      'active': true,
      'revision': 1,
    });
  }

  List<Map<String, dynamic>> get documents => [
    {
      'id': documentId,
      'project_id': WorkspaceApi.project['id'],
      'title': 'Synthetisches Projektangebot',
      'kind': 'offer',
      'status': 'draft',
      'revision': 1,
      'issue_date': '2026-10-26',
      'positions': [],
      'totals': {'net': '0.00', 'tax': '0.00', 'gross': '0.00'},
    },
  ];

  @override
  Future<dynamic> call(String path, [Map<String, dynamic>? body]) async {
    final uri = Uri.parse(path), route = Uri.parse(path).path;
    if (route == '/api/projects/project-1/integrations')
      return {'providers': [], 'financial_visible': true};
    if (route == '/api/projects/project-1/mail-attachments')
      return {'files': [], 'pending_count': 0, 'unannounced_count': 0};
    if (route == '/api/projects/project-1/plans') return [];
    if (!route.startsWith('/api/business/')) return super.call(path, body);
    businessCalls.add((path: path, body: body));
    if (uri.queryParameters.containsKey('project_id'))
      expect(uri.queryParameters['project_id'], WorkspaceApi.project['id']);
    if (failPaths.contains(route))
      throw const ApiException(0, 'Synthetischer Verbindungsfehler');
    if (route == '/api/business/capabilities')
      return {
        'storage_version': 7,
        'compatibility_mode': 'business',
        'generation': generation,
        'capabilities': [
          'business_foundation',
          'business_documents',
          'business_time',
          'business_planning',
          'business_inventory',
          'business_finance',
          'business_operations',
          'business_maintenance',
        ],
        'permissions': permissions.toList(),
        'features': [],
      };
    if (route == '/api/business/documents')
      return pendingDocuments?.future ?? {'items': documents};
    if (route == '/api/business/documents/$documentId') return documents.single;
    if (route == '/api/business/time/entries') return {'items': timeEntries};
    if (route == '/api/business/time/events') {
      expect(body!['project_id'], WorkspaceApi.project['id']);
      expect(body['request_id'], matches(RegExp(r'^[a-f0-9]{32}$')));
      expect(body['event_id'], isNull);
      final old = timeEntries
          .where((r) => r['id'] == body['entry_id'])
          .firstOrNull;
      expect(body['revision'], old?['revision'] ?? 0);
      expect(body['sequence'], (old?['sequence'] as int? ?? 0) + 1);
      final entry = <String, dynamic>{
        ...?old,
        'id': body['entry_id'],
        'project_id': body['project_id'],
        'revision': body['revision'] + 1,
        'sequence': body['sequence'],
        'status': switch (body['action']) {
          'pause' => 'paused',
          'stop' => 'stopped',
          _ => 'working',
        },
        'started_at': old?['started_at'] ?? body['occurred_at'],
        'events': [],
        'worked_seconds': 0,
      };
      if (old != null) timeEntries.remove(old);
      timeEntries.add(entry);
      return {
        'entry': entry,
        'request_id': body['request_id'],
        'event_id': body['request_id'],
      };
    }
    if (route == '/api/business/planning/calendar') {
      final now = DateTime.now();
      final start = DateTime(now.year, now.month, now.day - now.weekday + 1, 9);
      return {
        'appointments': [
          {
            'id': '5' * 32,
            'project_id': WorkspaceApi.project['id'],
            'title': 'Synthetischer Montageeinsatz',
            'start_at': start.toUtc().toIso8601String(),
            'end_at': start
                .add(const Duration(hours: 1))
                .toUtc()
                .toIso8601String(),
            'employee_ids': [],
            'resource_ids': [],
            'status': 'scheduled',
            'revision': 1,
          },
        ],
        'employees': [],
        'resources': [],
        'absences': [],
      };
    }
    if (route == '/api/business/articles')
      return {
        'items': [
          {
            'id': '6' * 32,
            'name': 'Synthetischer Materialartikel',
            'code': 'SYNTH',
            'kind': 'material',
            'unit': 'C62',
            'unit_price_net': '10.00',
            'cost_price_net': '5.00',
            'tax_rate': '19',
            'revision': 1,
            'active': true,
          },
        ],
      };
    if (route == '/api/business/projects/project-1/costs')
      return {
        'budget_net': '1000.00',
        'approved_changes_net': '0.00',
        'material_actual_net': '20.00',
        'labor_actual_net': '50.00',
        'actual_net': '70.00',
        'remaining_net': '930.00',
        'costs_complete': true,
        'missing_rates_count': 0,
        'approved_times': [],
        'materials': [],
      };
    if (route == '/api/business/finance/open-items')
      return {
        'items': [
          {
            'id': '7' * 32,
            'document_id': documentId,
            'project_id': WorkspaceApi.project['id'],
            'number': 'SYN-RE-001',
            'gross': '100.00',
            'paid': '25.00',
            'open': '75.00',
            'due_date': '2026-10-26',
            'level': 0,
          },
        ],
      };
    if (route == '/api/business/finance/outbox') return {'items': []};
    if (route == '/api/business/checklists')
      return {
        'items': [
          {
            'id': '8' * 32,
            'title': 'Synthetische Technikercheckliste',
            'revision': 1,
            'items': [],
          },
        ],
      };
    if (route == '/api/business/checklist-runs') return {'items': []};
    if (route == '/api/business/media')
      return {
        'items': [
          {
            'id': '9' * 32,
            'project_id': WorkspaceApi.project['id'],
            'filename': 'synthetic-site.png',
            'caption': 'Synthetisches Baustellenfoto',
            'media_type': 'image/png',
            'size': 68,
            'sha256': 'f' * 64,
            'status': 'ready',
            'revision': 1,
          },
        ],
      };
    if (route == '/api/business/assets')
      return {
        'items': [
          {
            'id': 'a' * 32,
            'project_id': WorkspaceApi.project['id'],
            'name': 'Synthetische Heizungsanlage',
            'revision': 1,
          },
        ],
      };
    if (route.endsWith('/classification'))
      return {
        'classification': 'operational',
        'effective_classification': 'operational',
        'release_current': true,
        'revision': 1,
        'source_fingerprint': 'f' * 64,
      };
    unexpected.add(path);
    throw StateError('Unexpected project business request: $path');
  }
}

Future<void> mount(WidgetTester tester, ProjectTabsApi api, Size size) async {
  tester.view.physicalSize = size;
  tester.view.devicePixelRatio = 1;
  addTearDown(tester.view.resetPhysicalSize);
  addTearDown(tester.view.resetDevicePixelRatio);
  await tester.pumpWidget(
    RepaintBoundary(
      key: rootCapture,
      child: MaterialApp(
        debugShowCheckedModeBanner: false,
        theme: officeTheme(),
        home: Builder(
          builder: (context) => Scaffold(
            body: Center(
              child: TextButton(
                onPressed: () => Navigator.push<void>(
                  context,
                  MaterialPageRoute(
                    builder: (_) => ProjectPage(
                      api: api,
                      project: WorkspaceApi.project,
                      role: 'owner',
                    ),
                  ),
                ),
                child: const Text('Projektliste · Projekt öffnen'),
              ),
            ),
          ),
        ),
      ),
    ),
  );
  await enterProject(tester);
}

Future<void> enterProject(WidgetTester tester) async {
  await tester.tap(find.text('Projektliste · Projekt öffnen'));
  await tester.pumpAndSettle();
  expect(find.byType(ProjectPage), findsOneWidget);
}

Future<void> selectTab(WidgetTester tester, String label) async {
  FocusManager.instance.primaryFocus?.unfocus();
  await tester.pumpAndSettle();
  final picker = find.byType(DropdownButtonFormField<int>);
  if (picker.evaluate().isNotEmpty) {
    final old =
        tester.widget<DropdownButtonFormField<int>>(picker).initialValue ?? 0;
    await tester.tap(picker);
    await tester.pumpAndSettle();
    final target = find.text(label).hitTestable();
    await tester.scrollUntilVisible(
      target,
      allTabs.indexOf(label) < old ? -160 : 160,
      scrollable: find.byType(Scrollable).last,
      maxScrolls: 30,
    );
    await tester.tap(target.last);
  } else {
    final target = find.widgetWithText(TextButton, label).first;
    await tester.ensureVisible(target);
    await tester.pumpAndSettle();
    await tester.tap(target);
  }
  await tester.pumpAndSettle();
  expect(
    tester.takeException(),
    isNull,
    reason:
        'Project register $label must leave the complete project page usable.',
  );
}

Future<void> leaveProject(WidgetTester tester) async {
  await tester.tap(find.byType(BackButton).first);
  await tester.pumpAndSettle();
  expect(find.text('Projektliste · Projekt öffnen'), findsOneWidget);
  expect(find.byType(ProjectPage, skipOffstage: false), findsNothing);
  expect(
    tester.state<NavigatorState>(find.byType(Navigator).first).canPop(),
    false,
  );
}

Future<void> capture(WidgetTester tester, String suffix) async {
  if (Platform.environment['SMARTPLAN_CAPTURE_UI'] != '1') return;
  await tester.runAsync(() async {
    final directory = Directory(
      Platform.environment['SMARTPLAN_UI_OUTPUT'] ?? Directory.systemTemp.path,
    );
    await directory.create(recursive: true);
    final image = await tester
        .renderObject<RenderRepaintBoundary>(find.byKey(rootCapture))
        .toImage();
    try {
      final bytes = await image.toByteData(format: ui.ImageByteFormat.png);
      await File('${directory.path}/smartplan-project-tabs-$suffix.png')
          .writeAsBytes(bytes!.buffer.asUint8List(), flush: true);
    } finally {
      image.dispose();
    }
  });
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

  testWidgets(
    'The real project page can open Arbeitszeit without losing its scaffold or return path',
    (tester) async {
      final api = ProjectTabsApi();
      try {
        await mount(tester, api, const Size(1200, 900));
        await selectTab(tester, 'Arbeitszeit');
        expect(find.text('Arbeit beginnen'), findsOneWidget);
        await leaveProject(tester);
        expect(api.unexpected, isEmpty);
      } finally {
        await tester.pumpWidget(const SizedBox());
        api.dispose();
      }
    },
  );

  for (final size in [const Size(1200, 900), const Size(390, 844)]) {
    testWidgets(
      'All seventeen project registers render and return through the real project route at ${size.width}',
      (tester) async {
        final api = ProjectTabsApi();
        const content = {
          'Übersicht': 'Nächste Termine',
          'Aufgaben': 'Synthetische Projektaufgabe',
          'Termine': 'Synthetischer Projekttermin',
          'Bautagebuch': 'Synthetische Tagebucharbeit',
          'Pläne': 'Neuer Grundriss',
          'Dokumente': 'Synthetische Projektunterlage',
          'Berichte': 'Neues Dokument',
          'Unterlagenfreigabe': 'Freigabe prüfen',
          'Belege': 'Synthetisches Projektangebot',
          'Arbeitszeit': 'Arbeit beginnen',
          'Einsatzplanung': 'Synthetischer Montageeinsatz',
          'Material': 'Synthetischer Materialartikel',
          'Kalkulation': 'Soll und Ist',
          'Finanzen': 'SYN-RE-001',
          'Dokumentation': 'Synthetische Technikercheckliste',
          'Fotos': 'Synthetisches Baustellenfoto',
          'Wartung': 'Synthetische Heizungsanlage',
        };
        try {
          await mount(tester, api, size);
          for (final tab in allTabs) {
            await selectTab(tester, tab);
            expect(
              find.textContaining(content[tab]!),
              findsWidgets,
              reason: '$tab must display its actual project content.',
            );
            if (tab == 'Übersicht')
              await capture(
                tester,
                size.width < 1000 ? 'overview-phone' : 'overview-desktop',
              );
            if (tab == 'Arbeitszeit')
              await capture(
                tester,
                size.width < 1000 ? 'time-phone' : 'time-desktop',
              );
            await selectTab(tester, 'Übersicht');
            await selectTab(tester, tab);
            await leaveProject(tester);
            await enterProject(tester);
          }
          expect(api.unexpected, isEmpty);
          expect(api.businessCalls.where((c) => c.body != null), isEmpty);
          expect(tester.takeException(), isNull);
        } finally {
          await tester.pumpWidget(const SizedBox());
          api.dispose();
        }
      },
    );
  }

  testWidgets(
    'Changing project permissions keeps an allowed active register and its state when earlier registers disappear',
    (tester) async {
      final api = ProjectTabsApi();
      try {
        await mount(tester, api, const Size(1200, 900));
        await selectTab(tester, 'Arbeitszeit');
        final timeState = tester.state(find.byType(BusinessTimePage));
        api.permissions.remove('documents.classify');
        api.generation++;
        await tester.tap(find.byTooltip('Projekt aktualisieren'));
        await tester.pumpAndSettle();
        expect(tester.takeException(), isNull);
        expect(find.byType(BusinessTimePage), findsOneWidget);
        expect(tester.state(find.byType(BusinessTimePage)), same(timeState));
        expect(find.text('Arbeit beginnen'), findsOneWidget);
        await leaveProject(tester);
      } finally {
        await tester.pumpWidget(const SizedBox());
        api.dispose();
      }
    },
  );

  for (final size in [const Size(1200, 900), const Size(390, 844)]) {
    testWidgets(
      'Old register callbacks follow the same permitted identity and reject removed destinations at ${size.width}',
      (tester) async {
        final api = ProjectTabsApi();
        try {
          await mount(tester, api, size);
          late final VoidCallback staleFinance;
          if (size.width < 1000) {
            final changed = tester
                .widget<DropdownButtonFormField<int>>(
                  find.byType(DropdownButtonFormField<int>),
                )
                .onChanged!;
            staleFinance = () => changed(allTabs.indexOf('Finanzen'));
          } else {
            staleFinance = tester
                .widget<TextButton>(find.widgetWithText(TextButton, 'Finanzen'))
                .onPressed!;
          }
          api.permissions.remove('documents.classify');
          api.generation++;
          await tester.tap(find.byTooltip('Projekt aktualisieren'));
          await tester.pumpAndSettle();
          staleFinance();
          await tester.pumpAndSettle();
          expect(tester.takeException(), isNull);
          expect(find.byType(BusinessFinancePage), findsOneWidget);
          api.permissions.remove('finance.read');
          api.generation++;
          await tester.tap(find.byTooltip('Projekt aktualisieren'));
          await tester.pumpAndSettle();
          expect(find.byType(BusinessFinancePage), findsNothing);
          expect(find.text('Nächste Termine'), findsWidgets);
          staleFinance();
          await tester.pumpAndSettle();
          expect(tester.takeException(), isNull);
          expect(find.byType(BusinessFinancePage), findsNothing);
          expect(find.text('Nächste Termine'), findsWidgets);
          await leaveProject(tester);
        } finally {
          await tester.pumpWidget(const SizedBox());
          api.dispose();
        }
      },
    );
  }

  testWidgets(
    'Pending and failed register reads preserve overview and project back navigation',
    (tester) async {
      final api = ProjectTabsApi()..pendingDocuments = Completer<dynamic>();
      try {
        await mount(tester, api, const Size(1200, 900));
        // An indeterminate loading indicator deliberately prevents settle.
        await tester.ensureVisible(find.widgetWithText(TextButton, 'Belege'));
        await tester.pump();
        await tester.tap(find.widgetWithText(TextButton, 'Belege'));
        await tester.pump();
        expect(tester.takeException(), isNull);
        expect(find.byType(LinearProgressIndicator), findsWidgets);
        await tester.ensureVisible(
          find.widgetWithText(TextButton, 'Übersicht'),
        );
        await tester.pump();
        await tester.tap(find.widgetWithText(TextButton, 'Übersicht'));
        await tester.pumpAndSettle();
        api.pendingDocuments!.complete({'items': api.documents});
        await tester.pumpAndSettle();
        await selectTab(tester, 'Belege');
        expect(find.text('Synthetisches Projektangebot'), findsOneWidget);
        await leaveProject(tester);
        api.failPaths.add('/api/business/media');
        await enterProject(tester);
        await selectTab(tester, 'Fotos');
        expect(
          find.textContaining('Synthetischer Verbindungsfehler'),
          findsOneWidget,
        );
        await selectTab(tester, 'Übersicht');
        await leaveProject(tester);
        expect(api.unexpected, isEmpty);
      } finally {
        if (api.pendingDocuments?.isCompleted == false)
          api.pendingDocuments!.complete({'items': api.documents});
        await tester.pumpWidget(const SizedBox());
        api.dispose();
      }
    },
  );

  testWidgets(
    'Project Arbeitszeit performs start pause resume stop on the same scoped entry and still returns',
    (tester) async {
      final api = ProjectTabsApi();
      try {
        await mount(tester, api, const Size(390, 844));
        await selectTab(tester, 'Arbeitszeit');
        for (final label in [
          'Arbeit beginnen',
          'Pause beginnen',
          'Weiterarbeiten',
          'Arbeit beenden',
        ]) {
          final button = find.text(label);
          await tester.ensureVisible(button);
          await tester.pumpAndSettle();
          await tester.tap(button);
          await tester.pumpAndSettle();
          expect(tester.takeException(), isNull);
        }
        expect(api.timeEntries, hasLength(1));
        expect(api.timeEntries.single['status'], 'stopped');
        expect(api.timeEntries.single['revision'], 4);
        expect(
          api.businessCalls
              .where((c) => c.body != null)
              .map((c) => c.body!['action']),
          ['start', 'pause', 'resume', 'stop'],
        );
        await selectTab(tester, 'Übersicht');
        await leaveProject(tester);
        expect(api.unexpected, isEmpty);
      } finally {
        await tester.pumpWidget(const SizedBox());
        api.dispose();
      }
    },
  );
}

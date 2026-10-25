import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:cryptography/cryptography.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:smartplan_office/mail_attachment_widgets.dart';
import 'package:smartplan_office/offline_plans.dart';
import 'package:smartplan_office/offline_vault.dart';
import 'package:smartplan_office/plan_pages.dart';
import 'package:smartplan_office/project_page.dart';

import 'offline_plans_test.dart' show TestDevice;
import 'project_business_tabs_navigation_test.dart'
    show ProjectTabsApi, selectTab;
import 'project_workspace_widget_test.dart' show WorkspaceApi;

/// Real project/inner-route widgets and OfflinePlans transactions are used.
/// Only the network and final device-write boundary are synthetic.
class UnsavedProjectApi extends ProjectTabsApi {
  final plan = <String, dynamic>{
    'id': 'synthetic-plan',
    'project_id': WorkspaceApi.project['id'],
    'title': 'Synthetischer Ausgangsplan',
    'revision': 1,
    'walls': <dynamic>[],
  };
  final planWrites = <Map<String, dynamic>>[];
  final planReceipts = <String, Map<String, dynamic>>{};
  Completer<void>? holdSave;
  bool saveStarted = false;
  int projectPops = 0;

  @override
  Future<dynamic> call(String path, [Map<String, dynamic>? body]) async {
    if (path == '/api/offline/access') {
      return {
        'token': 'offline_synthetic-plan-exit',
        'expires_at': DateTime.now()
            .toUtc()
            .add(const Duration(days: 7))
            .toIso8601String(),
        'capabilities': <String>[],
      };
    }
    const plans = '/api/projects/project-1/plans';
    if (path == plans || path == '$plans/synthetic-plan') {
      if (body == null) {
        final copy = businessCopy(plan);
        return path == plans ? [copy] : copy;
      }
      planWrites.add(businessCopy(body));
      saveStarted = true;
      if (holdSave != null) await holdSave!.future;
      final request = body['request_id'];
      if (request is String && planReceipts.containsKey(request)) {
        return businessCopy(planReceipts[request]!);
      }
      plan.addAll({
        'title': body['title'],
        'walls': body['walls'],
        'revision': (plan['revision'] as int) + 1,
      });
      if (request is String) planReceipts[request] = businessCopy(plan);
      return businessCopy(plan);
    }
    return super.call(path, body);
  }
}

class ProjectReturnObserver extends NavigatorObserver {
  ProjectReturnObserver(this.api);
  final UnsavedProjectApi api;
  @override
  void didPop(Route<dynamic> route, Route<dynamic>? previousRoute) {
    if (route.settings.name == 'synthetic-project') api.projectPops++;
  }
}

Map<String, dynamic> businessCopy(Map<String, dynamic> value) =>
    Map<String, dynamic>.from(jsonDecode(jsonEncode(value)) as Map);

class GatedPlanVault extends OfflineVault {
  GatedPlanVault()
    : super(Directory('unused-plan-return'), SecretKey(List.filled(32, 0)));
  Map<String, dynamic>? stored;
  Completer<void>? holdWrite;
  bool writeStarted = false, failWrites = false;

  @override
  Future<Map<String, dynamic>?> read() async =>
      stored == null ? null : businessCopy(stored!);

  @override
  Future<void> write(Map<String, dynamic> value) async {
    writeStarted = true;
    final hold = holdWrite;
    if (hold != null) await hold.future;
    if (failWrites) throw const FileSystemException('Synthetic full device');
    stored = businessCopy(value);
  }

  void release() {
    final hold = holdWrite;
    holdWrite = null;
    if (hold != null && !hold.isCompleted) hold.complete();
  }
}

class PlanExitDevice extends TestDevice {
  PlanExitDevice() : super(Directory('unused-plan-return'));
  final vault = GatedPlanVault();
  @override
  Future<OfflineVault> open(
    String server,
    String user, {
    bool create = false,
  }) async => vault;
}

Future<void> frames(WidgetTester tester, [int count = 6]) async {
  for (var index = 0; index < count; index++) {
    await tester.pump(const Duration(milliseconds: 40));
  }
}

Future<void> mountPlanProject(
  WidgetTester tester,
  UnsavedProjectApi api, {
  OfflinePlans? repository,
  Size size = const Size(1200, 900),
}) async {
  tester.view.physicalSize = size;
  tester.view.devicePixelRatio = 1;
  addTearDown(tester.view.resetPhysicalSize);
  addTearDown(tester.view.resetDevicePixelRatio);
  await tester.pumpWidget(
    MaterialApp(
      navigatorObservers: [ProjectReturnObserver(api)],
      home: Builder(
        builder: (context) => Scaffold(
          body: TextButton(
            onPressed: () => Navigator.push<void>(
              context,
              MaterialPageRoute<void>(
                settings: const RouteSettings(name: 'synthetic-project'),
                builder: (_) => ProjectPage(
                  api: api,
                  project: WorkspaceApi.project,
                  role: 'owner',
                  repository: repository,
                ),
              ),
            ),
            child: const Text('Projektliste · Projekt öffnen'),
          ),
        ),
      ),
    ),
  );
  await tester.tap(find.text('Projektliste · Projekt öffnen'));
  await tester.pumpAndSettle();
  await selectTab(tester, 'Pläne');
  await tester.tap(find.text('Synthetischer Ausgangsplan'));
  await tester.pumpAndSettle();
  expect(find.byType(PlanPage), findsOneWidget);
  expect(tester.takeException(), isNull);
}

Finder planTitle() => find.descendant(
  of: find.byType(PlanPage, skipOffstage: false),
  matching: find.byType(TextField, skipOffstage: false),
  skipOffstage: false,
);

Future<void> rootBack(
  WidgetTester tester, {
  bool system = false,
  bool settle = true,
}) async {
  if (system) {
    await tester.binding.handlePopRoute();
  } else {
    // The nested plan has an explicit IconButton. This is the outer project's
    // automatically generated BackButton, not the inner editor's leave().
    await tester.tap(find.byType(BackButton).first);
  }
  if (settle) {
    await tester.pumpAndSettle();
  } else {
    // Beyond a route's reverse animation, while an unresolved save may keep
    // its progress animation running and therefore cannot pumpAndSettle.
    await frames(tester, 12);
  }
}

void expectRootReturned() {
  expect(find.text('Projektliste · Projekt öffnen'), findsOneWidget);
  expect(find.byType(ProjectPage, skipOffstage: false), findsNothing);
}

void expectProjectRetained(WidgetTester tester, UnsavedProjectApi api) {
  final page = find.byType(ProjectPage);
  expect(page, findsOneWidget);
  expect(
    api.projectPops,
    0,
    reason:
        'A reverse animation must not disguise an already accepted root pop.',
  );
}

void main() {
  setUpAll(() async {
    await (FontLoader(
      'Inter',
    )..addFont(rootBundle.load('assets/fonts/Inter.ttf'))).load();
  });

  for (final system in [false, true]) {
    testWidgets(
      'Offstage dirty plan survives ${system ? 'system' : 'project appbar'} back until explicit discard',
      (tester) async {
        final api = UnsavedProjectApi();
        try {
          await mountPlanProject(
            tester,
            api,
            size: system ? const Size(390, 844) : const Size(1200, 900),
          );
          final editor = tester.state(find.byType(PlanPage));
          await tester.enterText(planTitle(), 'Noch nicht gespeicherter Plan');
          await selectTab(tester, 'Übersicht');
          await rootBack(tester, system: system);
          expectProjectRetained(tester, api);
          expect(find.text('Ungespeicherte Änderungen'), findsOneWidget);
          await tester.tap(find.text('Weiter bearbeiten'));
          await tester.pumpAndSettle();
          expect(
            tester.state(find.byType(PlanPage, skipOffstage: false)),
            same(editor),
          );
          expect(
            tester.widget<TextField>(planTitle()).controller!.text,
            'Noch nicht gespeicherter Plan',
          );
          expect(api.planWrites, isEmpty);
          await selectTab(tester, 'Übersicht');
          await rootBack(tester, system: system);
          await tester.tap(find.text('Verwerfen'));
          await tester.pumpAndSettle();
          expectRootReturned();
          expect(api.plan['title'], 'Synthetischer Ausgangsplan');
          expect(api.planWrites, isEmpty);
          expect(tester.takeException(), isNull);
        } finally {
          await tester.pumpWidget(const SizedBox());
          api.dispose();
        }
      },
    );
  }

  testWidgets(
    'Active inner plan back also honors its dirty confirmation once',
    (tester) async {
      final api = UnsavedProjectApi();
      try {
        await mountPlanProject(tester, api);
        await tester.enterText(planTitle(), 'Aktiv ungesicherter Plan');
        await rootBack(tester);
        expect(find.text('Ungespeicherte Änderungen'), findsOneWidget);
        await tester.tap(find.text('Weiter bearbeiten'));
        await tester.pumpAndSettle();
        expect(find.byType(PlanPage), findsOneWidget);
        await rootBack(tester);
        expect(find.text('Ungespeicherte Änderungen'), findsOneWidget);
        await tester.tap(find.text('Verwerfen'));
        await tester.pumpAndSettle();
        expect(find.byType(PlanPage, skipOffstage: false), findsNothing);
        expectProjectRetained(tester, api);
        expect(api.planWrites, isEmpty);
        await rootBack(tester);
        expectRootReturned();
        expect(tester.takeException(), isNull);
      } finally {
        await tester.pumpWidget(const SizedBox());
        api.dispose();
      }
    },
  );

  testWidgets('Clean offstage plan does not add another project-back click', (
    tester,
  ) async {
    final api = UnsavedProjectApi();
    try {
      await mountPlanProject(tester, api);
      await selectTab(tester, 'Übersicht');
      await rootBack(tester);
      expectRootReturned();
      expect(find.text('Ungespeicherte Änderungen'), findsNothing);
      expect(api.planWrites, isEmpty);
      expect(tester.takeException(), isNull);
    } finally {
      await tester.pumpWidget(const SizedBox());
      api.dispose();
    }
  });

  testWidgets(
    'Two queued clean editor-back callbacks cannot remove its plan list',
    (tester) async {
      final api = UnsavedProjectApi();
      try {
        await mountPlanProject(tester, api);
        final bar = tester.widget<AppBar>(
          find.descendant(
            of: find.byType(PlanPage),
            matching: find.byType(AppBar),
          ),
        );
        final leave = (bar.leading! as IconButton).onPressed!;
        leave();
        leave();
        await tester.pumpAndSettle();
        expectProjectRetained(tester, api);
        expect(find.byType(PlanPage, skipOffstage: false), findsNothing);
        expect(find.byType(PlansPage), findsOneWidget);
        expect(find.text('Synthetischer Ausgangsplan'), findsOneWidget);
        expect(tester.takeException(), isNull);
        await rootBack(tester);
        expectRootReturned();
        expect(api.projectPops, 1);
      } finally {
        await tester.pumpWidget(const SizedBox());
        api.dispose();
      }
    },
  );

  testWidgets('Offstage online save cannot be disposed before its real ACK', (
    tester,
  ) async {
    final api = UnsavedProjectApi();
    try {
      await mountPlanProject(tester, api);
      await tester.enterText(planTitle(), 'Plan wartet auf Serverantwort');
      api.holdSave = Completer<void>();
      await tester.tap(find.byTooltip('Speichern'));
      await frames(tester);
      expect(api.saveStarted, true);
      await selectTab(tester, 'Übersicht');
      await rootBack(tester, settle: false);
      expectProjectRetained(tester, api);
      expect(find.byType(PlanPage, skipOffstage: false), findsOneWidget);
      expect(find.text('Verwerfen'), findsNothing);
      api.holdSave!.complete();
      await tester.pumpAndSettle();
      expect(api.plan['title'], 'Plan wartet auf Serverantwort');
      await selectTab(tester, 'Übersicht');
      await rootBack(tester);
      expectRootReturned();
      expect(api.planWrites, hasLength(1));
      expect(tester.takeException(), isNull);
    } finally {
      if (api.holdSave != null && !api.holdSave!.isCompleted) {
        api.holdSave!.complete();
        await frames(tester);
      }
      await tester.pumpWidget(const SizedBox());
      api.dispose();
    }
  });

  for (final fail in [false, true]) {
    testWidgets(
      'Real local plan transaction retains draft during ${fail ? 'device-write failure' : 'pending device write'}',
      (tester) async {
        final api = UnsavedProjectApi(), transport = UnsavedProjectApi();
        final device = PlanExitDevice();
        final repo = OfflinePlans(
          api: api,
          transport: transport,
          device: device,
        );
        try {
          await repo.login(
            {'id': 'a' * 32, 'role': 'owner'},
            [WorkspaceApi.project],
          );
          await mountPlanProject(tester, api, repository: repo);
          final editor = tester.state(find.byType(PlanPage));
          device.vault.writeStarted = false;
          if (fail) {
            device.vault.failWrites = true;
          } else {
            device.vault.holdWrite = Completer<void>();
          }
          await tester.enterText(planTitle(), 'Lokal noch unbestätigter Plan');
          await frames(tester);
          expect(device.vault.writeStarted, true);
          await selectTab(tester, 'Übersicht');
          await rootBack(tester, settle: false);
          expectProjectRetained(tester, api);
          expect(
            tester.state(find.byType(PlanPage, skipOffstage: false)),
            same(editor),
          );
          expect(
            repo.get('synthetic-plan')['title'],
            'Synthetischer Ausgangsplan',
          );
          if (fail) {
            expect(find.text('Ungespeicherte Änderungen'), findsOneWidget);
            await tester.tap(find.text('Weiter bearbeiten'));
            await tester.pumpAndSettle();
            await selectTab(tester, 'Pläne');
            expect(
              tester.widget<TextField>(planTitle()).controller!.text,
              'Lokal noch unbestätigter Plan',
            );
            device.vault.failWrites = false;
            await tester.tap(find.byTooltip('Speichern'));
          } else {
            expect(find.text('Verwerfen'), findsNothing);
            device.vault.release();
          }
          await tester.pumpAndSettle();
          expect(
            repo.get('synthetic-plan')['title'],
            'Lokal noch unbestätigter Plan',
          );
          await selectTab(tester, 'Übersicht');
          await rootBack(tester);
          expectRootReturned();
          expect(tester.takeException(), isNull);
        } finally {
          device.vault.failWrites = false;
          device.vault.release();
          await frames(tester);
          await tester.pumpWidget(const SizedBox());
          repo.dispose();
          transport.dispose();
          api.dispose();
        }
      },
    );
  }

  testWidgets(
    'Mail plan-import navigation cannot reset an unsaved offstage plan',
    (tester) async {
      final api = UnsavedProjectApi();
      try {
        await mountPlanProject(tester, api);
        final editor = tester.state(find.byType(PlanPage));
        await tester.enterText(planTitle(), 'Plan vor Import-Rücksprung');
        await selectTab(tester, 'Dokumente');
        final card = tester.widget<MailAttachmentsCard>(
          find.byType(MailAttachmentsCard),
        );
        expect(card.onPlans, isNotNull);
        card.onPlans!();
        await tester.pumpAndSettle();
        expect(find.text('Ungespeicherte Änderungen'), findsOneWidget);
        await tester.tap(find.text('Weiter bearbeiten'));
        await tester.pumpAndSettle();
        expect(
          tester.state(find.byType(PlanPage, skipOffstage: false)),
          same(editor),
        );
        await selectTab(tester, 'Pläne');
        expect(
          tester.widget<TextField>(planTitle()).controller!.text,
          'Plan vor Import-Rücksprung',
        );
        expect(api.planWrites, isEmpty);
        expect(tester.takeException(), isNull);
      } finally {
        await tester.pumpWidget(const SizedBox());
        api.dispose();
      }
    },
  );
}

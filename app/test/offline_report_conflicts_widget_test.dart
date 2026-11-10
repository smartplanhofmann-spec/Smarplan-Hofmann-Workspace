import 'dart:io';
import 'dart:ui' as ui;

import 'package:flutter/material.dart';
import 'package:flutter/foundation.dart' show defaultTargetPlatform;
import 'package:flutter/rendering.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:smartplan_office/business_service_reports.dart';
import 'package:smartplan_office/business_session.dart';
import 'package:smartplan_office/offline_plans.dart';
import 'package:smartplan_office/design.dart';

import 'business_offline_reports_test.dart'
    show reportInk, reportProject, reportUser;
import 'offline_plan_widget_test.dart' show FrameDevice;
import 'offline_plans_test.dart' show loginV2;
import 'offline_report_conflicts_test.dart'
    show ConflictReportServer, conflictProjects;

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  setUpAll(() async {
    await (FontLoader(
      'Inter',
    )..addFont(rootBundle.load('assets/fonts/Inter.ttf'))).load();
    await (FontLoader(
      'MaterialIcons',
    )..addFont(rootBundle.load('fonts/MaterialIcons-Regular.otf'))).load();
  });
  const captureKey = ValueKey('offline-conflict-capture');
  Future<void> capture(WidgetTester tester, String name) async {
    final destination =
        Platform.environment['SMARTPLAN_CONFLICT_SCREENSHOT_DIR'];
    if (destination == null) return;
    await tester.runAsync(() async {
      final image = await tester
          .renderObject<RenderRepaintBoundary>(find.byKey(captureKey))
          .toImage(pixelRatio: 1);
      try {
        final bytes = await image.toByteData(format: ui.ImageByteFormat.png);
        final file = File(
          '$destination/$name-${defaultTargetPlatform.name}.png',
        );
        await file.parent.create(recursive: true);
        await file.writeAsBytes(bytes!.buffer.asUint8List(), flush: true);
      } finally {
        image.dispose();
      }
    });
  }

  Future<(OfflinePlans, ConflictReportServer, BusinessSession, String)> setup(
    WidgetTester tester,
  ) async {
    tester.view.physicalSize = const Size(390, 1000);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    final now = DateTime.utc(2026, 11, 10, 10);
    final server = ConflictReportServer(() => now)..token = 'synthetic';
    final repo = OfflinePlans(
      api: server,
      transport: server.offlineTransport,
      device: FrameDevice(),
      clock: () => now,
    );
    final session = BusinessSession(
      api: server,
      projectId: reportProject,
      offlineMode: true,
    );
    addTearDown(() {
      repo.dispose();
      session.dispose();
      server.dispose();
    });
    await loginV2(
      repo,
      {'id': reportUser, 'role': 'technician'},
      conflictProjects,
      offlineReports: true,
    );
    server.online = false;
    final draft = await repo.saveServiceReportDraft(
      reportProject,
      title: 'Privates Prüfprotokoll',
      description: 'Unveränderter Leistungsstand',
      notes: '',
    );
    await repo.signServiceReport(
      reportProject,
      draft['id'],
      signer: 'Bisherige Unterschrift',
      strokes: reportInk,
    );
    await tester.pumpAndSettle();
    await repo.sync();
    server.currentContext = {
      'project_name': 'Neues Projekt',
      'customer': 'Neuer Kunde',
    };
    server.online = true;
    await repo.sync();
    await tester.pumpAndSettle();
    await repo.sync();
    expect(
      repo.serviceReport(reportProject, draft['id'])['sync_status'],
      'Konflikt',
    );
    await tester.pumpWidget(
      RepaintBoundary(
        key: captureKey,
        child: MaterialApp(
          theme: officeTheme(),
          debugShowCheckedModeBanner: false,
          home: OfflineServiceReportPage(
            session: session,
            repository: repo,
            project: reportProject,
            id: draft['id'],
          ),
        ),
      ),
    );
    await tester.pumpAndSettle();
    final button = find.text('Konflikt prüfen');
    await tester.scrollUntilVisible(
      button,
      250,
      scrollable: find.byType(Scrollable).first,
    );
    await tester.tap(button);
    await tester.pumpAndSettle();
    return (repo, server, session, draft['id'] as String);
  }

  testWidgets(
    'mobile conflict review preserves original, creates a draft and reopens the one successor',
    (tester) async {
      final (repo, server, _, id) = await setup(tester);
      final dialog = find.byType(AlertDialog);
      expect(dialog, findsOneWidget);
      final text = tester
          .widget<Text>(
            find.descendant(of: dialog, matching: find.byType(Text)).at(1),
          )
          .data!;
      expect(text, contains('Ursprünglicher Kunde'));
      expect(text, contains('Neuer Kunde'));
      expect(text, contains('neu unterschrieben'));
      await capture(tester, 'conflict-review-390');
      await tester.tap(find.text('Abbrechen'));
      await tester.pumpAndSettle();
      expect(repo.serviceReports(reportProject), hasLength(1));
      await tester.tap(find.text('Konflikt prüfen'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Neuen Entwurf erstellen'));
      await tester.pumpAndSettle();
      final copied = repo
          .serviceReports(reportProject)
          .singleWhere((r) => r['id'] != id);
      expect(copied['status'], 'draft');
      expect(find.text('Prüfen und unterschreiben'), findsOneWidget);
      expect(find.text('Bisherige Unterschrift'), findsNothing);
      expect(
        find.text('Projekt: Neues Projekt\nKunde: Neuer Kunde'),
        findsOneWidget,
      );
      await capture(tester, 'conflict-new-draft-390');
      await tester.pageBack();
      await tester.pumpAndSettle();
      final open = find.text('Neuen Bericht öffnen');
      await tester.scrollUntilVisible(
        open,
        250,
        scrollable: find.byType(Scrollable).first,
      );
      await tester.tap(open);
      await tester.pumpAndSettle();
      expect(repo.serviceReports(reportProject), hasLength(2));
      expect(server.reportReceipts, isEmpty);
      expect(tester.takeException(), isNull);
      await tester.pumpWidget(const SizedBox.shrink());
      await repo.leave();
    },
    variant: TargetPlatformVariant({
      TargetPlatform.windows,
      TargetPlatform.iOS,
    }),
  );

  testWidgets(
    'locking the account hides an open conflict dialog and disables confirmation',
    (tester) async {
      final (repo, _, _, _) = await setup(tester);
      expect(
        find.descendant(
          of: find.byType(AlertDialog),
          matching: find.textContaining('Ursprünglicher Kunde'),
        ),
        findsOneWidget,
      );
      await repo.lock();
      await tester.pumpAndSettle();
      expect(find.textContaining('Ursprünglicher Kunde'), findsNothing);
      expect(find.textContaining('Neuer Kunde'), findsNothing);
      final button = tester.widget<FilledButton>(
        find.widgetWithText(FilledButton, 'Neuen Entwurf erstellen'),
      );
      expect(button.onPressed, isNull);
      await capture(tester, 'conflict-locked-390');
      expect(tester.takeException(), isNull);
      await tester.pumpWidget(const SizedBox.shrink());
      await repo.leave();
    },
    variant: TargetPlatformVariant({
      TargetPlatform.windows,
      TargetPlatform.iOS,
    }),
  );
}

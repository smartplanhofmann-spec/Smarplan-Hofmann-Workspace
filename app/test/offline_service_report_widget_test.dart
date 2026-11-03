import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:smartplan_office/business_service_reports.dart';
import 'package:smartplan_office/business_session.dart';
import 'package:smartplan_office/offline_plans.dart';

import 'business_offline_reports_test.dart'
    show OfflineReportServer, reportProject, reportUser;
import 'offline_plan_widget_test.dart' show FrameDevice;

void main() {
  Future<(OfflinePlans, OfflineReportServer, BusinessSession)> setup() async {
    final now = DateTime.utc(2026, 11, 3, 9);
    final server = OfflineReportServer(() => now)..token = 'synthetic';
    final repo = OfflinePlans(
      api: server,
      transport: server,
      device: FrameDevice(),
      clock: () => now,
    );
    await repo.login(
      {'id': reportUser, 'role': 'technician'},
      [
        {
          'id': reportProject,
          'name': 'Wartung Süd',
          'customer': 'Synthetischer Kunde',
        },
      ],
      offlineReports: true,
    );
    server.online = false;
    final session = BusinessSession(
      api: server,
      projectId: reportProject,
      offlineMode: true,
    );
    return (repo, server, session);
  }

  testWidgets(
    'Offline service report can be reviewed, signed and reopened without a fake server success',
    (tester) async {
      tester.view.physicalSize = const Size(1100, 1500);
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.resetPhysicalSize);
      addTearDown(tester.view.resetDevicePixelRatio);
      final (repo, server, session) = await setup();
      addTearDown(() {
        repo.dispose();
        session.dispose();
        server.dispose();
      });
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: BusinessServiceReportsPage(
              session: session,
              repository: repo,
            ),
          ),
        ),
      );
      await tester.pumpAndSettle();
      await tester.tap(find.text('Servicebericht erfassen'));
      await tester.pumpAndSettle();
      await tester.enterText(
        find.byType(TextField).at(0),
        'Synthetische Druckprüfung',
      );
      await tester.enterText(
        find.byType(TextField).at(1),
        'Ventil geprüft. Dichtheit bestätigt.',
      );
      await tester.enterText(
        find.byType(TextField).at(2),
        'Hinweise übergeben.',
      );
      final save = find.text('Entwurf auf diesem Gerät speichern');
      await tester.ensureVisible(save);
      await tester.tap(save);
      await tester.pumpAndSettle();
      expect(repo.serviceReports(reportProject).single['status'], 'draft');
      await tester.tap(find.text('Prüfen und unterschreiben'));
      await tester.pumpAndSettle();
      final dialog = find.byType(AlertDialog);
      expect(
        find.descendant(
          of: dialog,
          matching: find.text('Ventil geprüft. Dichtheit bestätigt.'),
        ),
        findsOneWidget,
      );
      await tester.enterText(
        find.descendant(of: dialog, matching: find.byType(TextField)),
        'Synthetische Kundin',
      );
      await tester.tap(find.text('Unterschrift erfassen'));
      await tester.pumpAndSettle();
      await tester.drag(
        find.byKey(const ValueKey('signature-canvas')),
        const Offset(120, 45),
      );
      await tester.pumpAndSettle();
      await tester.tap(find.byKey(const ValueKey('signature-done')));
      await tester.pumpAndSettle();
      await tester.tap(find.byType(CheckboxListTile));
      await tester.tap(find.text('Unterschrift auf diesem Gerät sichern'));
      await tester.pumpAndSettle();
      final signed = repo.serviceReports(reportProject).single;
      expect(signed['status'], 'signed');
      expect(repo.pending, 1);
      expect(
        find.text('Auf diesem Gerät unterschrieben · Übertragung ausstehend'),
        findsOneWidget,
      );
      expect(find.text('Archiviertes PDF öffnen'), findsNothing);
      expect(find.text('Entwurf bearbeiten'), findsNothing);
      expect(server.reportBodies, isEmpty);
      await tester.pageBack();
      await tester.pumpAndSettle();
      await tester.tap(find.text('Synthetische Druckprüfung'));
      await tester.pumpAndSettle();
      expect(find.text('Ventil geprüft. Dichtheit bestätigt.'), findsOneWidget);
      expect(
        repo.serviceReports(reportProject).single['capture_request'],
        signed['capture_request'],
      );
      await tester.pumpWidget(const SizedBox.shrink());
      await repo.leave();
    },
    variant: TargetPlatformVariant.only(TargetPlatform.windows),
  );

  testWidgets(
    'Revoked offline grant hides reviewed content and disables signature persistence',
    (tester) async {
      tester.view.physicalSize = const Size(1000, 1600);
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.resetPhysicalSize);
      addTearDown(tester.view.resetDevicePixelRatio);
      final (repo, server, session) = await setup();
      addTearDown(() {
        repo.dispose();
        session.dispose();
        server.dispose();
      });
      final draft = await repo.saveServiceReportDraft(
        reportProject,
        title: 'Vertrauliche Anlage',
        description: 'Vertraulicher Leistungsstand',
      );
      await tester.pumpWidget(
        MaterialApp(
          home: OfflineServiceReportPage(
            session: session,
            repository: repo,
            project: reportProject,
            id: draft['id'],
          ),
        ),
      );
      await tester.pumpAndSettle();
      await tester.tap(find.text('Prüfen und unterschreiben'));
      await tester.pumpAndSettle();
      await repo.lock();
      await tester.pumpAndSettle();
      expect(find.text('Vertraulicher Leistungsstand'), findsNothing);
      expect(find.text('Vertrauliche Anlage'), findsNothing);
      final button = tester.widget<FilledButton>(
        find.widgetWithText(
          FilledButton,
          'Unterschrift auf diesem Gerät sichern',
        ),
      );
      expect(button.onPressed, isNull);
      expect(repo.pending, 0);
      await tester.pumpWidget(const SizedBox.shrink());
      await repo.leave();
    },
    variant: TargetPlatformVariant.only(TargetPlatform.windows),
  );
}

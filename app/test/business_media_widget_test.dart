import 'dart:io';

import 'package:file_selector/file_selector.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:smartplan_office/business_media.dart';
import 'package:smartplan_office/business_session.dart';
import 'package:smartplan_office/offline_plans.dart';

import 'business_offline_media_test.dart' show FieldServer, fieldPng;
import 'offline_plans_test.dart' show TestDevice, idle;

void main() {
  testWidgets(
    'Camera capture acknowledges an encrypted photo and note before deleting its temporary original',
    (tester) async {
      final folder = (await tester.runAsync(
        () => Directory.systemTemp.createTemp('smartplan-camera-ui-'),
      ))!;
      final camera = File('${folder.path}/camera.png');
      await tester.runAsync(() => camera.writeAsBytes(fieldPng, flush: true));
      final server = FieldServer()..token = 'synthetic-session';
      var now = DateTime.now().toUtc();
      final repo = OfflinePlans(
        api: server,
        transport: server,
        device: TestDevice(Directory('${folder.path}/vault')),
        clock: () => now,
      );
      await tester.runAsync(() async {
        await repo.login(
          {'id': 'a' * 32, 'role': 'technician'},
          [
            {'id': 'p', 'name': 'Synthetisches Projekt'},
          ],
          fieldMedia: true,
        );
        await idle(repo);
      });
      server.online = false;
      final session = BusinessSession(
        api: server,
        projectId: 'p',
        offlineMode: true,
      );
      debugDefaultTargetPlatformOverride = TargetPlatform.iOS;
      try {
        await tester.pumpWidget(
          MaterialApp(
            home: Scaffold(
              body: BusinessMediaPage(
                session: session,
                repository: repo,
                takePhoto: () async => XFile(camera.path),
              ),
            ),
          ),
        );
        await tester.pumpAndSettle();
        await tester.enterText(
          find.widgetWithText(TextField, 'Bildnotiz (optional)'),
          'Synthetischer Leitungsdurchbruch',
        );
        await tester.tap(find.text('Foto aufnehmen'));
        var committed = false;
        for (var attempt = 0; attempt < 300; attempt++) {
          await tester.runAsync(
            () => Future<void>.delayed(const Duration(milliseconds: 5)),
          );
          await tester.pump(const Duration(milliseconds: 20));
          if (repo.pending == 1 &&
              find
                  .textContaining(
                    'Foto und Notiz sind verschlüsselt auf diesem Gerät gesichert.',
                  )
                  .evaluate()
                  .isNotEmpty &&
              find.byType(LinearProgressIndicator).evaluate().isEmpty) {
            committed = true;
            break;
          }
        }
        expect(
          committed,
          isTrue,
          reason: 'The UI must acknowledge its durable commit and finish camera cleanup before a settled frame is asserted.',
        );
        await tester.runAsync(() async {
          await repo.flush();
          await idle(repo);
          expect(await camera.exists(), isFalse);
          expect(
            await repo.fieldPhotoSource(
              repo.fieldPhotos('p').single['local_id'],
            ),
            fieldPng,
          );
        });
        expect(
          find.textContaining('verschlüsselt auf diesem Gerät gesichert'),
          findsWidgets,
        );
        expect(server.media, isEmpty);
        expect(tester.takeException(), isNull);
        now = now.add(const Duration(days: 8));
        repo.changed();
        await tester.pumpAndSettle();
        expect(find.text('Synthetischer Leitungsdurchbruch'), findsNothing);
        expect(repo.pending, 1);
        expect(find.text('Fotos nicht freigegeben'), findsOneWidget);
      } finally {
        await tester.pumpWidget(const SizedBox());
        debugDefaultTargetPlatformOverride = null;
        await tester.runAsync(() async {
          await repo.flush();
          await idle(repo);
          repo.dispose();
          session.dispose();
          server.dispose();
          await folder.delete(recursive: true);
        });
      }
    },
  );
}

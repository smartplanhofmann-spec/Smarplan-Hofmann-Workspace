import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:file_selector/file_selector.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:smartplan_office/business_media.dart';
import 'package:smartplan_office/business_session.dart';
import 'package:smartplan_office/design.dart';
import 'package:smartplan_office/offline_plans.dart';
import 'package:smartplan_office/offline_vault.dart';

import 'business_offline_media_test.dart' show FieldServer, fieldPng;
import 'offline_plans_test.dart' show TestDevice, idle;

class HeldMediaVault extends OfflineVault {
  HeldMediaVault(super.directory, super.key);
  bool holdMediaCommit = false;
  final commitStarted = Completer<void>(), allowCommit = Completer<void>();

  @override
  Future<void> write(Map<String, dynamic> data) async {
    if (holdMediaCommit &&
        (data['business_media_records'] as Map? ?? {}).isNotEmpty &&
        !commitStarted.isCompleted) {
      commitStarted.complete();
      await allowCommit.future;
    }
    await super.write(data);
  }
}

class HeldMediaDevice extends TestDevice {
  HeldMediaDevice(super.folder);
  HeldMediaVault? vault;

  @override
  Future<OfflineVault> open(
    String server,
    String user, {
    bool create = false,
  }) async {
    final opened = await super.open(server, user, create: create);
    return vault = HeldMediaVault(opened.directory, opened.key);
  }
}

bool captureAcknowledged() => find
    .textContaining(
      'Foto und Notiz sind verschlüsselt auf diesem Gerät gesichert.',
    )
    .evaluate()
    .isNotEmpty;

Future<void> waitForCapture(
  WidgetTester tester,
  OfflinePlans repo,
  File camera, {
  bool Function()? reached,
  String phase = 'durable camera commit and cleanup',
}) async {
  // File I/O, AES and native stream cleanup run outside the widget fake clock.
  // Bound actual elapsed time instead of assuming a number of pumped frames
  // represents how long a Windows filesystem has had to complete its work.
  final elapsed = Stopwatch()..start();
  bool? cameraExists;
  while (elapsed.elapsed < const Duration(seconds: 15)) {
    cameraExists = await tester.runAsync(() async {
      await Future<void>.delayed(const Duration(milliseconds: 20));
      return camera.exists();
    });
    await tester.pump(const Duration(milliseconds: 20));
    if (reached != null
        ? reached()
        : repo.pending == 1 &&
              captureAcknowledged() &&
              find.byType(LinearProgressIndicator).evaluate().isEmpty &&
              cameraExists == false)
      return;
  }
  final notices = tester
      .widgetList<Notice>(find.byType(Notice))
      .map((n) => n.message)
      .join(' | ');
  fail(
    'Timed out after 15 real seconds waiting for $phase. '
    'pending=${repo.pending}, acknowledged=${captureAcknowledged()}, '
    'busy=${find.byType(LinearProgressIndicator).evaluate().isNotEmpty}, '
    'cameraExists=$cameraExists, notices=${notices.length > 600 ? notices.substring(0, 600) : notices}',
  );
}

void main() {
  for (final slowCommit in [false, true]) {
    testWidgets(
      slowCommit
          ? 'A delayed encrypted photo commit keeps the original until durable acknowledgement and cleanup'
          : 'Camera capture acknowledges an encrypted photo and note before deleting its temporary original',
      (tester) async {
        final folder = (await tester.runAsync(
          () => Directory.systemTemp.createTemp('smartplan-camera-ui-'),
        ))!;
        final camera = File('${folder.path}/camera.png');
        await tester.runAsync(() => camera.writeAsBytes(fieldPng, flush: true));
        final server = FieldServer()..token = 'synthetic-session';
        var now = DateTime.now().toUtc();
        final device = HeldMediaDevice(Directory('${folder.path}/vault'));
        Timer? releaseTimer;
        final repo = OfflinePlans(
          api: server,
          transport: server,
          device: device,
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
        device.vault!.holdMediaCommit = slowCommit;
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
          if (slowCommit) {
            await waitForCapture(
              tester,
              repo,
              camera,
              reached: () => device.vault!.commitStarted.isCompleted,
              phase: 'the controlled photo metadata write',
            );
            expect(repo.pending, 0);
            expect(captureAcknowledged(), isFalse);
            expect(find.byType(LinearProgressIndicator), findsOneWidget);
            expect(await tester.runAsync(() => camera.exists()), isTrue);
            final stored = await tester.runAsync(
              () => OfflineVault(
                device.vault!.directory,
                device.vault!.key,
              ).read(),
            );
            expect((stored?['business_media_records'] as Map? ?? {}), isEmpty);
            await tester.runAsync(() async {
              // Keep a real metadata write outstanding longer than the former
              // 1.5-second polling budget while the ordinary waiter runs.
              releaseTimer = Timer(const Duration(seconds: 2), () {
                if (!device.vault!.allowCommit.isCompleted)
                  device.vault!.allowCommit.complete();
              });
            });
          }
          await waitForCapture(tester, repo, camera);
          await tester.runAsync(() async {
            await repo.flush();
            await idle(repo);
            expect(await camera.exists(), isFalse);
            expect(
              repo.fieldPhotos('p').single['caption'],
              'Synthetischer Leitungsdurchbruch',
            );
            final stored = await OfflineVault(
              device.vault!.directory,
              device.vault!.key,
            ).read();
            final saved =
                (stored!['business_media_records'] as Map).values.single as Map;
            expect(saved['caption'], 'Synthetischer Leitungsdurchbruch');
            expect(stored['business_media_outbox'], [saved['local_id']]);
            final encryptedFiles = await device.folder
                .list(recursive: true)
                .where((entry) => entry is File)
                .cast<File>()
                .toList();
            for (final file in encryptedFiles) {
              final bytes = await file.readAsBytes();
              expect(listEquals(bytes, fieldPng), isFalse);
              expect(
                utf8.decode(bytes, allowMalformed: true),
                isNot(contains('Synthetischer Leitungsdurchbruch')),
              );
            }
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
          releaseTimer?.cancel();
          if (!device.vault!.allowCommit.isCompleted)
            device.vault!.allowCommit.complete();
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
}

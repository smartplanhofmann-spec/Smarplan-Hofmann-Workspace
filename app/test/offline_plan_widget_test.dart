import 'dart:io';

import 'package:cryptography/cryptography.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:smartplan_office/offline_plans.dart';
import 'package:smartplan_office/offline_vault.dart';
import 'package:smartplan_office/plan_pages.dart';

import 'offline_plans_test.dart' show TestDevice, PlanServer;

// Storage durability is exercised with real encrypted files in the service and
// HTTP integration tests. This widget test keeps I/O out of the fake frame clock.
class FrameVault extends OfflineVault {
  Map<String, dynamic>? value;
  FrameVault() : super(Directory('unused'), SecretKey(List.filled(32, 0)));
  @override
  Future<Map<String, dynamic>?> read() async =>
      value == null ? null : offlineCopy(value!);
  @override
  Future<void> write(Map<String, dynamic> data) async {
    value = offlineCopy(data);
  }
}

class FrameDevice extends TestDevice {
  final vault = FrameVault();
  FrameDevice() : super(Directory('unused'));
  @override
  Future<OfflineVault> open(
    String server,
    String user, {
    bool create = false,
  }) async => vault;
}

void main() {
  testWidgets(
    'Offline editor automatically commits title and wall before closing',
    (tester) async {
      final server = PlanServer();
      final repo = OfflinePlans(
        api: server,
        transport: server,
        device: FrameDevice(),
      );
      await repo.login(
        {'id': 'a' * 32, 'role': 'owner'},
        [
          {'id': 'project'},
        ],
      );
      server.online = false;
      final initial = await repo.save('project', {'title': 'EG', 'walls': []});
      try {
        await tester.pumpWidget(
          MaterialApp(
            home: PlanPage(
              api: server,
              path: '/api/projects/project/plans',
              initial: initial,
              canWrite: true,
              repository: repo,
            ),
          ),
        );
        await tester.enterText(find.byType(TextField), 'iPad drawing');
        final canvas = find.byWidgetPredicate(
          (w) => w is CustomPaint && w.painter is PlanPainter,
        );
        final rect = tester.getRect(canvas);
        await tester.tapAt(
          rect.topLeft + Offset(rect.width * .2, rect.height * .3),
        );
        await tester.pump();
        await tester.tapAt(
          rect.topLeft + Offset(rect.width * .7, rect.height * .3),
        );
        await tester.pumpAndSettle();
        expect(repo.get(initial['local_id'])['title'], 'iPad drawing');
        expect(repo.get(initial['local_id'])['walls'], hasLength(1));
        expect(find.text('Lokal gespeichert'), findsOneWidget);
        await tester.pumpWidget(const MaterialApp(home: SizedBox()));
        await repo.flush();
        await repo.leave();
        await repo.resume();
        expect(repo.get(initial['local_id'])['walls'], hasLength(1));
        await tester.pump();
      } finally {
        repo.dispose();
        server.dispose();
      }
    },
  );
}

import 'dart:async';
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:smartplan_office/offline_plans.dart';
import 'package:smartplan_office/offline_vault.dart';

import 'offline_plans_test.dart' show PlanServer, TestDevice, idle;

class DelayedDevice extends TestDevice {
  DelayedDevice(super.folder);
  bool delay = false;
  final entered = Completer<void>();
  final release = Completer<void>();

  @override
  Future<OfflineVault> open(String server, String user, {bool create = false}) async {
    final vault = await super.open(server, user, create: create);
    return DelayedVault(vault, this);
  }
}

class DelayedVault extends OfflineVault {
  DelayedVault(OfflineVault original, this.device)
    : super(original.directory, original.key);
  final DelayedDevice device;

  @override
  Future<void> write(Map<String, dynamic> data) async {
    if (device.delay) {
      if (!device.entered.isCompleted) device.entered.complete();
      await device.release.future;
    }
    await super.write(data);
  }
}

void main() {
  test('Leaving waits for a real outstanding encrypted write before files can be removed', () async {
    final directory = await Directory.systemTemp.createTemp('smartplan-drain-');
    final device = DelayedDevice(directory);
    final server = PlanServer()..token = 'synthetic-online';
    final repository = OfflinePlans(
      api: server, transport: server, device: device,
      clock: () => DateTime.utc(2026, 10, 23),
    );
    try {
      await repository.login({'id': 'a' * 32, 'role': 'owner', 'email': 'synthetic@example.test'},
                             [{'id': 'project', 'name': 'Synthetic project'}]);
      await idle(repository);
      server.online = false;
      device.delay = true;
      final save = repository.save('project', {'title': 'Retained during shutdown', 'walls': []});
      // Attach the error observer before leave invalidates the view epoch.
      final completedSave = expectLater(save, throwsA(isA<StateError>()));
      await device.entered.future;
      var left = false;
      final leaving = repository.leave().then((_) { left = true; });
      await Future<void>.delayed(Duration.zero);
      expect(left, false);
      device.release.complete();
      await completedSave;
      await leaving;
      expect(left, true);
      final stored = await (await device.open(repository.server, 'a' * 32)).read();
      expect((stored!['records'] as Map).values.single['title'], 'Retained during shutdown');
      await directory.delete(recursive: true);
      expect(await directory.exists(), false);
    } finally {
      if (!device.release.isCompleted) device.release.complete();
      await repository.leave();
      repository.dispose();
      server.dispose();
      if (await directory.exists()) await directory.delete(recursive: true);
    }
  });
}

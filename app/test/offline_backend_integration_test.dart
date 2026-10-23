import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:smartplan_office/api.dart';
import 'package:smartplan_office/offline_plans.dart';

import 'backend_integration_test.dart' show backendFixture, BackendHttp;
import 'offline_plans_test.dart' show TestDevice, idle;

class ConnectionApi extends OfficeApi {
  bool connected = true;
  ConnectionApi(String base) : super(baseUrl: base);
  @override
  Future<dynamic> call(String path, [Map<String, dynamic>? body]) {
    if (!connected) throw const ApiException(0, 'No reception');
    return super.call(path, body);
  }
}

void main() {
  final backend = Directory('../backend').absolute;
  final python =
      Platform.environment['SMARTPLAN_TEST_PYTHON'] ??
      '${backend.path}/.venv/${Platform.isWindows ? 'Scripts/python.exe' : 'bin/python'}';
  test('Real backend accepts an offline draft after client restart using its plan-only device grant', () async {
    await HttpOverrides.runWithHttpOverrides(() async {
      final directory = await Directory.systemTemp.createTemp(
        'smartplan-offline-http-',
      );
      Process? process;
      StreamIterator<String>? output;
      StreamSubscription<String>? errors;
      OfficeApi? full;
      ConnectionApi? connection;
      OfflinePlans? repository;
      try {
        process = await Process.start(python, [
          '-u',
          '-c',
          backendFixture,
          directory.path,
        ], workingDirectory: backend.path);
        final diagnostics = StringBuffer();
        errors = process.stderr
            .transform(utf8.decoder)
            .listen(diagnostics.write);
        output = StreamIterator(
          process.stdout
              .transform(utf8.decoder)
              .transform(const LineSplitter()),
        );
        expect(
          await output.moveNext().timeout(const Duration(seconds: 20)),
          true,
          reason: diagnostics.toString(),
        );
        final port = int.parse(output.current.substring(5));
        final base = 'http://127.0.0.1:$port';
        full = OfficeApi(baseUrl: base);
        full.token = (await full.call('/api/login', {
          'email': 'owner@example.test',
          'password': 'Integration-password-123',
        }))['token'];
        final user = Map<String, dynamic>.from(await full.call('/api/me'));
        final project = await full.call('/api/projects', {
          'name': 'Offline project',
          'customer': 'Synthetic customer',
        });
        final projects = List<dynamic>.from(await full.call('/api/projects'));
        final device = TestDevice(Directory('${directory.path}/device'));
        connection = ConnectionApi(base);
        repository = OfflinePlans(
          api: full,
          transport: connection,
          device: device,
        );
        await repository.login(user, projects);
        await idle(repository);
        connection.connected = false;
        final wall = {
          'id': 'wall_1',
          'points': [
            [10, 20],
            [200, 20],
          ],
        };
        final local = await repository.save(project['id'], {
          'title': 'Ground floor offline',
          'walls': [wall],
        });
        await idle(repository);
        expect(repository.pending, 1);
        await repository.leave();
        repository.dispose();
        repository = OfflinePlans(
          api: full,
          transport: connection,
          device: device,
        );
        await repository.resume();
        await idle(repository);
        expect(repository.get(local['local_id'])['walls'], [wall]);
        connection.connected = true;
        await repository.sync();
        expect(repository.pending, 0);
        final saved = await full.call('/api/projects/${project['id']}/plans');
        expect(saved, hasLength(1));
        expect(saved.single['title'], 'Ground floor offline');
        expect(saved.single['walls'], [wall]);
        await expectLater(
          connection.call('/api/users'),
          throwsA(isA<ApiException>().having((e) => e.status, 'status', 403)),
        );
      } finally {
        repository?.dispose();
        full?.dispose();
        connection?.dispose();
        if (process != null) {
          process.kill();
          await process.exitCode.timeout(
            const Duration(seconds: 10),
            onTimeout: () async {
              process!.kill(ProcessSignal.sigkill);
              return await process.exitCode;
            },
          );
        }
        await output?.cancel();
        await errors?.cancel();
        await directory.delete(recursive: true);
      }
    }, BackendHttp());
  }, skip: File(python).existsSync() ? false : 'Backend virtualenv required');
}

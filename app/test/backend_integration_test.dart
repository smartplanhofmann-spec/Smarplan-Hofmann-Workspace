import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:smartplan_office/api.dart';

class BackendHttp extends HttpOverrides {}

// This fixture uses synthetic accounts in a temporary database. It never opens
// the developer's Office database or a real Microsoft connection.
const backendFixture = r'''
import os
import sys
from pathlib import Path
from http.server import ThreadingHTTPServer
from core import Office
from onedrive import OneDrive
from server import make_handler

for name in ('MS_CLIENT_ID', 'MS_CLIENT_SECRET', 'MS_REDIRECT_URI', 'OFFICE_VAULT_KEY'):
    os.environ.pop(name, None)
office = Office(Path(sys.argv[1]) / 'office.sqlite3')
office.add_user('owner@example.test', 'Integration-password-123', 'owner')
server = ThreadingHTTPServer(('127.0.0.1', 0), make_handler(office, OneDrive(office)))
print('PORT:' + str(server.server_port), flush=True)
server.serve_forever()
''';

void main() {
  final backend = Directory('../backend').absolute;
  final python =
      Platform.environment['SMARTPLAN_TEST_PYTHON'] ??
      '${backend.path}/.venv/${Platform.isWindows ? 'Scripts/python.exe' : 'bin/python'}';

  test(
    'Real Python backend accepts login, Unicode reports, signature, PDF and logout',
    () async {
      await HttpOverrides.runWithHttpOverrides(() async {
        final directory = await Directory.systemTemp.createTemp(
          'smartplan-client-',
        );
        Process? process;
        StreamIterator<String>? output;
        StreamSubscription<String>? stderr;
        final diagnostics = StringBuffer();
        OfficeApi? owner;
        OfficeApi? technician;
        try {
          process = await Process.start(python, [
            '-u',
            '-c',
            backendFixture,
            directory.path,
          ], workingDirectory: backend.path);
          stderr = process.stderr
              .transform(utf8.decoder)
              .listen(diagnostics.write);
          output = StreamIterator(
            process.stdout
                .transform(utf8.decoder)
                .transform(const LineSplitter()),
          );
          if (!await output.moveNext().timeout(const Duration(seconds: 20))) {
            throw StateError('Test backend did not start: $diagnostics');
          }
          expect(output.current, startsWith('PORT:'));
          final port = int.parse(output.current.substring(5));
          final base = 'http://127.0.0.1:$port';
          owner = OfficeApi(baseUrl: base);
          final login = await owner.call('/api/login', {
            'email': 'owner@example.test',
            'password': 'Integration-password-123',
          });
          owner.token = login['token'];
          expect((await owner.call('/api/me'))['role'], 'owner');
          expect(await owner.call('/api/projects'), isEmpty);
          final project = await owner.call('/api/projects', {
            'name': 'Projekt Büro',
            'customer': 'Müller & Söhne',
          });
          final user = await owner.call('/api/users', {
            'email': 'tech@example.test',
            'password': 'Technician-password-123',
            'role': 'technician',
          });
          await owner.call('/api/assignments', {
            'user_id': user['id'],
            'project_id': project['id'],
          });
          technician = OfficeApi(baseUrl: base);
          final techLogin = await technician.call('/api/login', {
            'email': 'tech@example.test',
            'password': 'Technician-password-123',
          });
          technician.token = techLogin['token'];
          expect(
            (await technician.call('/api/projects') as List).single['name'],
            'Projekt Büro',
          );
          final report = await technician.call(
            '/api/projects/${project['id']}/reports',
            {
              'kind': 'Servicebericht',
              'description': 'Leuchten geprüft – Gerät eingebaut.',
            },
          );
          final signed = await technician.call(
            '/api/reports/${report['id']}/sign',
            {
              'content_hash': report['content_hash'],
              'signer': 'Kunde Müller',
              'strokes': [
                [
                  [0.1, 0.2],
                  [0.8, 0.7],
                ],
              ],
            },
          );
          expect(signed['status'], 'signed');
          final pdf = await technician.pdf(report['id']);
          expect(ascii.decode(pdf.sublist(0, 4)), '%PDF');
          expect(await owner.pdf(report['id']), pdf);
          await owner.call('/api/assignments', {
            'user_id': user['id'],
            'project_id': project['id'],
            'remove': true,
          });
          await expectLater(
            technician.pdf(report['id']),
            throwsA(isA<ApiException>().having((e) => e.status, 'status', 404)),
          );
          expect(await owner.call('/api/logout', {}), {'ok': true});
          await expectLater(
            owner.call('/api/me'),
            throwsA(isA<ApiException>().having((e) => e.status, 'status', 401)),
          );
          expect(owner.token, isNull);
        } finally {
          owner?.dispose();
          technician?.dispose();
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
          await stderr?.cancel();
          await directory.delete(recursive: true);
        }
      }, BackendHttp());
    },
    skip: File(python).existsSync()
        ? false
        : 'Backend Python environment missing; run setup-cloud.sh first',
  );
}

import 'dart:async';
import 'dart:convert';
import 'dart:io';
import 'dart:typed_data';

import 'package:flutter_test/flutter_test.dart';
import 'package:smartplan_office/api.dart';
import 'package:smartplan_office/offline_plans.dart';

import 'backend_integration_test.dart' show BackendHttp;
import 'offline_plans_test.dart' show TestDevice, idle;

// The synthetic fixture simulates only the trusted local HTTPS proxy envelope.
// TLS itself is exercised by the independent real-Caddy release tests.
const fixture = r'''
import json, os, sys
from pathlib import Path
from socketserver import TCPServer
from wsgiref.simple_server import WSGIServer, WSGIRequestHandler
from cryptography.fernet import Fernet
from core import Office
from online.web import create_app

for name in ('SMARTPLAN_DATABASE_DSN', 'SMARTPLAN_VAULT_KEY_FILE', 'SMARTPLAN_STORAGE_CONFIG_FILE'):
    os.environ.pop(name, None)
office = Office(Path(sys.argv[1]) / 'office.sqlite3')
office.add_user('synthetic@example.test', 'Synthetic-import-password-123', 'owner')
token = office.login('synthetic@example.test', 'Synthetic-import-password-123')
user = office.user(token)
project = office.add_project(user, 'Importfixture', 'Synthetic customer')
app = create_app(office=office, key=Fernet.generate_key(), host='office.example.test', storage_config={})
def proxy(environ, start_response):
    environ['HTTP_HOST'] = 'office.example.test'
    environ['HTTP_X_FORWARDED_PROTO'] = 'https'
    return app(environ, start_response)
class LocalServer(WSGIServer):
    def server_bind(self):
        TCPServer.server_bind(self)
        self.server_name, self.server_port = self.server_address
        self.setup_environ()
class Quiet(WSGIRequestHandler):
    def log_message(self, *args): pass
server = LocalServer(('127.0.0.1', 0), Quiet)
server.set_app(proxy)
print(json.dumps(dict(port=server.server_port, token=token, user=user,
                     projects=office.projects(user), project_id=project)), flush=True)
server.serve_forever()
''';

class ImportConnection extends OfficeApi {
  bool connected = true;
  ImportConnection(String base) : super(baseUrl: base, apiVersion: 'v1');
  void check() {
    if (!connected) throw const ApiException(0, 'No reception');
  }

  @override
  Future<dynamic> call(String path, [Map<String, dynamic>? body]) {
    check();
    return super.call(path, body);
  }

  @override
  Future<dynamic> putChunk(String path, Uint8List bytes) {
    check();
    return super.putChunk(path, bytes);
  }

  @override
  Future<Uint8List> bytes(
    String path, {
    required String mediaType,
    int maxBytes = 20 * 1024 * 1024,
  }) {
    check();
    return super.bytes(path, mediaType: mediaType, maxBytes: maxBytes);
  }
}

Uint8List syntheticPdf() {
  final bytes = BytesBuilder();
  void write(String text) => bytes.add(ascii.encode(text));
  write('%PDF-1.4\n%${List.filled(299000, 'x').join()}\n');
  const stream = 'BT /F1 18 Tf 20 100 Td (SYNTHETIC PLAN) Tj ET\n';
  final objects = [
    '<< /Type /Catalog /Pages 2 0 R >>',
    '<< /Type /Pages /Kids [3 0 R] /Count 1 >>',
    '<< /Type /Page /Parent 2 0 R /MediaBox [0 0 300 200] /Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>',
    '<< /Length ${stream.length} >>\nstream\n${stream}endstream',
    '<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>',
  ];
  final offsets = <int>[];
  for (var index = 0; index < objects.length; index++) {
    offsets.add(bytes.length);
    write('${index + 1} 0 obj\n${objects[index]}\nendobj\n');
  }
  final xref = bytes.length;
  write('xref\n0 6\n0000000000 65535 f \n');
  for (final offset in offsets) {
    write('${offset.toString().padLeft(10, '0')} 00000 n \n');
  }
  write('trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n$xref\n%%EOF\n');
  return bytes.takeBytes();
}

void main() {
  final backend = Directory('../backend').absolute;
  final python =
      Platform.environment['SMARTPLAN_TEST_PYTHON'] ??
      '${backend.path}/.venv/${Platform.isWindows ? 'Scripts/python.exe' : 'bin/python'}';
  test(
    'Real Flask API receives an encrypted offline source after restart and serves it to a second device',
    () async {
      await HttpOverrides.runWithHttpOverrides(() async {
        final directory = await Directory.systemTemp.createTemp(
          'smartplan-import-http-',
        );
        Process? process;
        StreamIterator<String>? output;
        StreamSubscription<String>? errors;
        OfficeApi? full;
        ImportConnection? connection;
        OfflinePlans? repo, second;
        try {
          process = await Process.start(python, [
            '-u',
            '-c',
            fixture,
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
          final setup = jsonDecode(output.current);
          final base = 'http://127.0.0.1:${setup['port']}';
          full = OfficeApi(baseUrl: base, apiVersion: 'v1')
            ..token = setup['token'];
          connection = ImportConnection(base);
          final device = TestDevice(
            Directory('${directory.path}/first-device'),
          );
          final user = Map<String, dynamic>.from(setup['user']);
          final projects = List<dynamic>.from(setup['projects']);
          final project = setup['project_id'] as String;
          repo = OfflinePlans(api: full, transport: connection, device: device);
          await repo.login(user, projects);
          await idle(repo);
          final granted = await (await device.open(
            repo.server,
            user['id'],
          )).read();
          expect(granted?['imports_supported'], isTrue);
          connection.connected = false;
          // A vector PDF with a long synthetic comment exercises two real PUTs.
          final source = syntheticPdf();
          final local = await repo.captureImport(
            project,
            source,
            filename: 'synthetic.pdf',
            mediaType: 'application/pdf',
            title: 'Offline source',
          );
          await idle(repo);
          expect(repo.pending, 1);
          await repo.leave();
          repo.dispose();
          repo = OfflinePlans(api: full, transport: connection, device: device);
          await repo.resume();
          await idle(repo);
          expect(await repo.importSource(local['local_id']), source);
          connection.connected = true;
          await repo.sync();
          expect(repo.pending, 0);
          expect(repo.getImport(local['local_id'])['status'], 'queued');
          final remote = await full.call('/api/projects/$project/plan-imports');
          expect(remote, hasLength(1));
          expect(remote.single['uploaded_chunks'], [0, 1]);
          second = OfflinePlans(
            api: full,
            transport: ImportConnection(base),
            device: TestDevice(Directory('${directory.path}/second-device')),
          );
          await second.login(user, projects);
          await idle(second);
          await second.refreshImports(project);
          final copied = second.imports(project).single;
          expect(await second.importSource(copied['local_id']), source);
          expect(copied['sha256'], local['sha256']);
          await expectLater(
            connection.call('/api/users'),
            throwsA(isA<ApiException>().having((e) => e.status, 'status', 403)),
          );
        } finally {
          repo?.dispose();
          second?.dispose();
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
    },
    // This fixture starts the actual Hetzner API, whose document adapters
    // require POSIX directory descriptors, locks and private file modes.
    // Linux CI exercises it end to end. Windows still runs the real desktop
    // backend fixture and every import repository/widget test.
    skip: Platform.isWindows
        ? 'Starts the Linux/Hetzner online server; exercised on Linux CI'
        : File(python).existsSync()
        ? false
        : 'Backend virtualenv with online dependencies required',
  );
}

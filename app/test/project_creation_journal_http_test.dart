@Tags(['posix_backend'])
library;

import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:smartplan_office/api.dart';
import 'package:smartplan_office/main.dart';
import 'package:smartplan_office/project_creation_journal.dart';

import 'backend_integration_test.dart' show BackendHttp;
import 'offline_plans_test.dart' show TestDevice;

const fixture = r'''
import json, sys, uuid
from pathlib import Path
from wsgiref.simple_server import WSGIServer, WSGIRequestHandler
from socketserver import TCPServer
from cryptography.fernet import Fernet
from core import Office, digest
from online.instance import bind
from online.storage import Storage
from online.web import create_app
from online.test_instance_isolation import MFA_SCHEMA
office=Office(Path(sys.argv[1])/'synthetic.db')
office.db.executescript(MFA_SCHEMA)
owner=office.add_user('journal@example.test','Synthetic-journal-password-123','owner')
customer=office.create_customer(dict(id=owner,role='owner'),dict(name='Müller Originalkunde',address='Südstraße 7'))
key=Fernet.generate_key();host='journal.example.test';instance=uuid.uuid4().hex
storage=Storage(office,key,host,config={'server':{'path':str(Path(sys.argv[1])/'storage')}})
bind(office,instance,host,key,storage)
with office.db:
    office.db.execute('INSERT INTO mfa VALUES(?,?,?,?)',(owner,Fernet(key).encrypt(b'JBSWY3DPEHPK3PXP').decode(),-1,json.dumps([digest('111111111111111111111111'),digest('222222222222222222222222')])))
app=create_app(office=office,key=key,host=host,storage=storage,instance_id=instance)
def proxy(environ,start_response):
    environ['HTTP_HOST']=host;environ['HTTP_X_FORWARDED_PROTO']='https'
    return app(environ,start_response)
class LoopbackServer(WSGIServer):
    def server_bind(self):
        TCPServer.server_bind(self);self.server_name,self.server_port=self.server_address;self.setup_environ()
class Quiet(WSGIRequestHandler):
    def log_message(self,*args):pass
server=LoopbackServer(('127.0.0.1',0),Quiet);server.set_app(proxy)
print(json.dumps(dict(port=server.server_port,owner=owner,customer=customer['id'],instance=instance)),flush=True)
server.serve_forever()
''';

class JournalHttpApi extends OfficeApi {
  JournalHttpApi(superBase, {required this.recovery, this.loseAck = false})
    : super(baseUrl: superBase, apiVersion: 'v1');
  final String recovery;
  bool loseAck;
  int inFlight = 0;
  final posts = <Map<String, dynamic>>[];
  @override
  Future<dynamic> call(String path, [Map<String, dynamic>? body]) async {
    inFlight++;
    try {
      if (path == '/api/login') {
        final pending = await super.call(path, body);
        expect(pending['mfa_required'], isTrue);
        return await super.call('/api/login/verify', {
          'challenge': pending['challenge'],
          'code': recovery,
        });
      }
      final create = path == '/api/projects' && body != null;
      if (create)
        posts.add(Map<String, dynamic>.from(jsonDecode(jsonEncode(body))));
      final result = await super.call(path, body);
      if (create && loseAck) {
        loseAck = false;
        throw const ApiException(0, 'Synthetic lost actual project response');
      }
      return result;
    } finally {
      inFlight--;
    }
  }
}

Future<void> until(WidgetTester tester, bool Function() done) async {
  for (var i = 0; i < 300 && !done(); i++) {
    await tester.runAsync(
      () => Future<void>.delayed(const Duration(milliseconds: 20)),
    );
    await tester.pump(const Duration(milliseconds: 20));
  }
  expect(
    done(),
    isTrue,
    reason:
        'Actual HTTP/UI operation did not complete: ${tester.widgetList<Text>(find.byType(Text)).map((t) => t.data).join(" | ")}',
  );
}

void main() {
  testWidgets(
    'actual MFA accepted create survives full app recreation and fresh login without duplicate',
    (tester) async {
      final temp = (await tester.runAsync(
        () => Directory.systemTemp.createTemp('project-journal-http-'),
      ))!;
      Process? process;
      StreamIterator<String>? output;
      StreamSubscription<String>? errors;
      JournalHttpApi? api;
      final diagnostics = StringBuffer();
      final device = TestDevice(Directory('${temp.path}/device'));
      await tester.binding.setSurfaceSize(const Size(1200, 900));
      try {
        final setup = await tester.runAsync(() async {
          final python =
              Platform.environment['SMARTPLAN_TEST_PYTHON'] ??
              '${Directory('../backend').absolute.path}/.venv/bin/python';
          process = await Process.start(python, [
            '-u',
            '-c',
            fixture,
            temp.path,
          ], workingDirectory: Directory('../backend').absolute.path);
          errors = process!.stderr
              .transform(utf8.decoder)
              .listen(diagnostics.write);
          output = StreamIterator(
            process!.stdout
                .transform(utf8.decoder)
                .transform(const LineSplitter()),
          );
          expect(
            await output!.moveNext().timeout(const Duration(seconds: 30)),
            isTrue,
            reason: '$diagnostics',
          );
          return jsonDecode(output!.current) as Map<String, dynamic>;
        });
        await HttpOverrides.runWithHttpOverrides(() async {
          final base = 'http://127.0.0.1:${setup!['port']}';
          Future<void> loginApp(String recovery, {bool loseAck = false}) async {
            api = JournalHttpApi(base, recovery: recovery, loseAck: loseAck);
            await tester.pumpWidget(
              OfficeApp(
                api: api,
                projectCreationJournal: ProjectCreationJournal(device: device),
              ),
            );
            await tester.enterText(
              find.byType(TextFormField).at(0),
              'journal@example.test',
            );
            await tester.enterText(
              find.byType(TextFormField).at(1),
              'Synthetic-journal-password-123',
            );
            await tester.tap(find.text('Anmelden'));
            await until(
              tester,
              () =>
                  find.text('Weitere Bereiche').evaluate().isNotEmpty ||
                  find.text('Weitere Verwaltung').evaluate().isNotEmpty,
            );
            if (find.text('Weitere Verwaltung').evaluate().isEmpty) {
              await tester.scrollUntilVisible(
                find.text('Weitere Verwaltung'),
                250,
                scrollable: find
                    .ancestor(
                      of: find.text('Weitere Bereiche'),
                      matching: find.byType(Scrollable),
                    )
                    .first,
              );
            }
            await tester.ensureVisible(find.text('Weitere Verwaltung'));
            await tester.tap(find.text('Weitere Verwaltung'));
            await tester.pumpAndSettle();
          }

          Future<void> openCreate() async {
            await tester.tap(
              find.widgetWithText(FilledButton, 'Projekt anlegen'),
            );
            await until(
              tester,
              () => find.byType(ProjectDialog).evaluate().isNotEmpty,
            );
            await tester.pumpAndSettle();
          }

          await loginApp('111111111111111111111111', loseAck: true);
          final firstToken = api!.token;
          await openCreate();
          await tester.enterText(
            find.byType(TextFormField).first,
            'Synthetische Montage Süd',
          );
          await tester.tap(find.byType(DropdownButtonFormField<String>));
          await tester.pumpAndSettle();
          await tester.tap(find.textContaining('Müller Originalkunde').last);
          await tester.pumpAndSettle();
          await tester.tap(find.widgetWithText(FilledButton, 'Anlegen'));
          await until(
            tester,
            () => find
                .text('Synthetic lost actual project response')
                .evaluate()
                .isNotEmpty,
          );
          expect(api!.posts, hasLength(1));
          final original = api!.posts.single;
          final saved = (await tester.runAsync(
            () => ProjectCreationJournal(device: device).open(
              server: base,
              version: 'v1',
              accountId: setup['owner'],
              scope: ProjectCreationScope(
                server: base,
                version: 'v1',
                accountId: setup['owner'],
                instanceId: setup['instance'],
              ),
            ),
          ))!;
          expect(saved.pending!['body'], original);
          final projects = await tester.runAsync(
            () => api!.call('/api/projects'),
          );
          expect(projects, hasLength(1));
          // Dispose the entire app, API and all in-memory pending state.
          await tester.pumpWidget(const SizedBox());
          api!.dispose();
          await tester.pump();
          await loginApp('222222222222222222222222');
          expect(api!.token, isNot(firstToken));
          await openCreate();
          expect(
            tester
                .widget<TextFormField>(find.byType(TextFormField).first)
                .controller!
                .text,
            'Synthetische Montage Süd',
          );
          expect(
            tester
                .widget<TextFormField>(find.byType(TextFormField).first)
                .enabled,
            isFalse,
          );
          await tester.tap(
            find.widgetWithText(FilledButton, 'Erneut versuchen'),
          );
          await until(
            tester,
            () => find.byType(ProjectDialog).evaluate().isEmpty,
          );
          expect(api!.posts, [original]);
          final finalProjects = await tester.runAsync(
            () => api!.call('/api/projects'),
          );
          expect(finalProjects, hasLength(1));
          expect(finalProjects.single['id'], projects.single['id']);
          expect(finalProjects.single['customer_id'], setup['customer']);
          final customers = await tester.runAsync(
            () => api!.call('/api/customers'),
          );
          expect(customers, hasLength(1));
          final cleared = await tester.runAsync(
            () => ProjectCreationJournal(device: device).open(
              server: base,
              version: 'v1',
              accountId: setup['owner'],
              scope: ProjectCreationScope(
                server: base,
                version: 'v1',
                accountId: setup['owner'],
                instanceId: setup['instance'],
              ),
            ),
          );
          expect(cleared!.pending, isNull);
          expect(tester.takeException(), isNull);
        }, BackendHttp());
      } finally {
        await tester.pumpWidget(const SizedBox());
        api?.dispose();
        await tester.runAsync(() async {
          process?.kill();
          if (process != null)
            await process!.exitCode.timeout(const Duration(seconds: 10));
          await output?.cancel();
          await errors?.cancel();
          await temp.delete(recursive: true);
        });
        await tester.binding.setSurfaceSize(null);
      }
    },
  );
}

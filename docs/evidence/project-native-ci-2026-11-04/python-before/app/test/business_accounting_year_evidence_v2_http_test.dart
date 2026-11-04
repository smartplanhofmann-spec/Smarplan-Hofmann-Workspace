import 'dart:async';
import 'dart:convert';
import 'dart:io';
import 'dart:typed_data';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:smartplan_office/api.dart';
import 'package:smartplan_office/business_accounting_euer.dart';
import 'package:smartplan_office/business_accounting_year_evidence.dart';
import 'package:smartplan_office/business_session.dart';

import 'backend_integration_test.dart' show BackendHttp;

const yearHttpFixture = r'''
import json,os,uuid,tempfile
from cryptography.fernet import Fernet
from online.instance import bind
from pathlib import Path
from wsgiref.simple_server import WSGIServer,WSGIRequestHandler
from socketserver import TCPServer
from test_accounting_year_openings import YearOpeningWorkflow
from business_foundation import BusinessFoundation
from online.storage import Storage
from online.web import create_app
for name in ('MS_CLIENT_ID','MS_CLIENT_SECRET','MS_REDIRECT_URI','OFFICE_VAULT_KEY','SMARTPLAN_DATABASE_DSN','SMARTPLAN_VAULT_KEY_FILE','SMARTPLAN_STORAGE_CONFIG_FILE'):
    os.environ.pop(name,None)
f=YearOpeningWorkflow('runTest');f.setUp();office=f.office
key=Fernet.generate_key();instance=uuid.uuid4().hex;temp=tempfile.TemporaryDirectory(prefix='synthetic-native-v2-')
host='year-review-v2.example.test';storage=Storage(office,key,host,config={'server':{'path':str(Path(temp.name)/'company')}})
bind(office,instance,host,key,storage)
original,_=f.save();f.classify(original)
payment,_=f.f.payment(f.old,'59.50',day='2026-11-01');f.f.classify(payment)
euer=f.f.euer
receipt=euer.incoming();euer.post('input_vat',euer.vat_payload(receipt));expense=euer.payout(receipt);euer.post('cash',euer.cash_payload(expense,'materials'))
entry=euer.post('export',{'year':2026})
worker=office.add_user('native-year-reader@example.test','Synthetic-year-reader-password-123','accountant')
admin=office.add_user('native-year-admin@example.test','Synthetic-year-admin-password-123','owner')
foundation=BusinessFoundation(office)
for permission in ('accounting.read','finance.read'):
    foundation.save_grant(f.owner,dict(request_id=uuid.uuid4().hex,user_id=worker,permission=permission,scope='*',effect='allow',revision=0))
office.assign(f.owner,f.f.euer.fixture.project,worker)
app=create_app(office=office,key=key,host=host,instance_id=instance,storage=storage)
def proxy(environ,start_response):
    environ['HTTP_HOST']=host;environ['HTTP_X_FORWARDED_PROTO']='https'
    return app(environ,start_response)
class LoopbackServer(WSGIServer):
    def server_bind(self):
        TCPServer.server_bind(self);self.server_name,self.server_port=self.server_address;self.setup_environ()
class Quiet(WSGIRequestHandler):
    def log_message(self,*args):pass
server=LoopbackServer(('127.0.0.1',0),Quiet);server.set_app(proxy)
print(json.dumps(dict(port=server.server_port,token=office.login('native-year-reader@example.test','Synthetic-year-reader-password-123'),admin_token=office.login('native-year-admin@example.test','Synthetic-year-admin-password-123'),user_id=worker,project=f.f.euer.fixture.project,entry=entry)),flush=True)
try:server.serve_forever()
finally:f.doCleanups();temp.cleanup()
''';

class YearHttpApi extends OfficeApi {
  YearHttpApi(String base) : super(baseUrl: base, apiVersion: 'v1');
  int inFlight = 0, metadataReads = 0, archiveReads = 0, posts = 0;
  bool lose = true;
  @override
  Future<dynamic> call(String path, [Map<String, dynamic>? body]) async {
    inFlight++;
    if (body != null) posts++;
    if (path.endsWith('/evidence')) metadataReads++;
    try {
      return await super.call(path, body);
    } finally {
      inFlight--;
    }
  }

  @override
  Future<Uint8List> bytes(
    String path, {
    required String mediaType,
    int maxBytes = 20 * 1024 * 1024,
  }) async {
    inFlight++;
    archiveReads++;
    try {
      final raw = await super.bytes(
        path,
        mediaType: mediaType,
        maxBytes: maxBytes,
      );
      if (lose) {
        lose = false;
        throw const ApiException(
          0,
          'Synthetic ZIP reply lost after actual read',
        );
      }
      return raw;
    } finally {
      inFlight--;
    }
  }
}

void main() {
  testWidgets(
    'actual v2 390px original EÜR navigation, exact ZIP file, unknown response and project-only source revocation before save',
    (t) async {
      final temporary = (await t.runAsync(
        () => Directory.systemTemp.createTemp('synthetic-native-year-'),
      ))!;
      Process? process;
      StreamIterator<String>? output;
      StreamSubscription<String>? errors;
      BusinessSession? session;
      YearHttpApi? api;
      OfficeApi? admin;
      final diagnostics = StringBuffer();
      await t.binding.setSurfaceSize(const Size(390, 844));
      try {
        final setup = (await t.runAsync(() async {
          process = await Process.start(
            Platform.environment['SMARTPLAN_TEST_PYTHON'] ??
                '/tmp/smartplan-backend-verified/bin/python',
            ['-u', '-c', yearHttpFixture],
            workingDirectory: Directory('../backend').absolute.path,
          );
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
            true,
            reason: '$diagnostics',
          );
          return yearEvidenceCopy(jsonDecode(output!.current));
        }))!;
        await HttpOverrides.runWithHttpOverrides(() async {
          api = YearHttpApi('http://127.0.0.1:${setup['port']}')
            ..token = setup['token'];
          session = BusinessSession(api: api!);
          admin = OfficeApi(baseUrl: api!.base, apiVersion: 'v1')
            ..token = setup['admin_token'];
          Future<T> request<T>(Future<T> Function() action) async {
            T? value;
            Object? error;
            bool done = false;
            action().then(
              (v) {
                value = v;
                done = true;
              },
              onError: (Object e) {
                error = e;
                done = true;
              },
            );
            for (var i = 0; i < 1500 && !done; i++) {
              await t.runAsync(
                () => Future<void>.delayed(const Duration(milliseconds: 10)),
              );
              await t.pump(const Duration(milliseconds: 20));
            }
            expect(done, true, reason: 'HTTP timeout $diagnostics');
            if (error != null) throw error!;
            return value as T;
          }

          Future<void> settle() async {
            int quiet = 0;
            for (var i = 0; i < 1500; i++) {
              await t.runAsync(
                () => Future<void>.delayed(const Duration(milliseconds: 10)),
              );
              await t.pump(const Duration(milliseconds: 20));
              if (api!.inFlight == 0) {
                if (++quiet == 8) {
                  await t.pumpAndSettle();
                  return;
                }
              } else {
                quiet = 0;
              }
            }
            fail('Native year requests did not settle $diagnostics');
          }

          Future<void> tap(String label, {bool settled = true}) async {
            final finder = find.text(label),
                scroll = find.byType(Scrollable).first;
            t.state<ScrollableState>(scroll).position.jumpTo(0);
            await t.pump();
            await t.scrollUntilVisible(
              finder,
              250,
              scrollable: scroll,
              maxScrolls: 70,
            );
            await t.ensureVisible(finder.first);
            await t.pumpAndSettle();
            await t.tap(finder.first);
            await t.pump();
            if (settled) await settle();
          }

          await request(() => session!.load());
          expect(yearEvidenceReadable(session!), true);
          await t.pumpWidget(
            MaterialApp(
              home: BusinessEuerPage(session: session!, initialTab: 'journal'),
            ),
          );
          await settle();
          await tap('Original-/Journal-Jahresnachweis öffnen');
          final opened = t.widget<BusinessYearEvidencePage>(
            find.byType(BusinessYearEvidencePage),
          );
          expect(opened.exportEntry, setup['entry']);
          final saved = File('${temporary.path}/actual-year.zip');
          int saveCount = 0;
          bool chooserReady = false;
          Completer<void>? chooser;
          // Dispose the navigation host before replacing its route with the
          // test exporter; otherwise its existing pushed production route stays.
          await t.pumpWidget(const SizedBox.shrink());
          await t.pump();
          await t.pumpWidget(
            MaterialApp(
              home: BusinessYearEvidencePage(
                session: session!,
                exportEntry: opened.exportEntry,
                exportFile: (attachment, authorize) async {
                  chooserReady = true;
                  if (chooser != null) await chooser.future;
                  if (await authorize()) {
                    try {
                      await saved.writeAsBytes(attachment.bytes, flush: true);
                    } catch (e) {
                      diagnostics.write('Actual output error: $e');
                      rethrow;
                    }
                    saveCount++;
                  }
                },
              ),
            ),
          );
          await settle();
          await tap('Original-/Journal-ZIP speichern');
          expect(saveCount, 0);
          await tap('Originalnachweis erneut lesen');
          await tap('Original-/Journal-ZIP speichern');
          expect(
            saveCount,
            1,
            reason:
                'reads ${api!.archiveReads}/${api!.metadataReads}; $diagnostics; UI: ${t.widgetList<Text>(find.byType(Text)).map((v) => v.data).join(' | ')}',
          );
          expect(api!.archiveReads, 2);
          final metadata = yearEvidenceMetadata(
            await request(
              () => session!.read(yearEvidencePath(setup['entry']['id'])),
            ),
            setup['entry'],
          );
          expect(metadata['format'], 'smartplan-year-evidence-v2');
          final raw = (await t.runAsync(() => saved.readAsBytes()))!;
          expect(
            yearEvidenceAttachment(raw, metadata, setup['entry']).sha256,
            metadata['sha256'],
          );
          expect(api!.posts, 0);
          expect(api!.metadataReads, greaterThanOrEqualTo(5));
          // Global finance access remains; only one included project's source right
          // is revoked while the native chooser is open, before the final save.
          chooser = Completer<void>();
          chooserReady = false;
          await tap('Original-/Journal-ZIP speichern', settled: false);
          await request(() async {
            while (!chooserReady) {
              await Future<void>.delayed(const Duration(milliseconds: 10));
            }
          });
          await request(
            () => admin!.call('/api/business/settings/permissions', {
              'request_id': 'c' * 32,
              'user_id': setup['user_id'],
              'permission': 'finance.read',
              'scope': setup['project'],
              'effect': 'deny',
              'revision': 0,
            }),
          );
          chooser.complete();
          await settle();
          expect(session!.can('finance.read'), true);
          expect(
            saveCount,
            1,
            reason:
                'reads ${api!.archiveReads}/${api!.metadataReads}; $diagnostics; UI: ${t.widgetList<Text>(find.byType(Text)).map((v) => v.data).join(' | ')}',
          );
          expect(
            find.textContaining('derzeit nicht freigegeben'),
            findsOneWidget,
          );
          expect(find.text(metadata['filename']), findsNothing);
          expect(api!.posts, 0);
          expect(t.takeException(), null);
          final checked = await t.runAsync(
            () => Process.run(
              Platform.environment['SMARTPLAN_TEST_PYTHON'] ??
                  '/tmp/smartplan-backend-verified/bin/python',
              [
                '-I',
                File('../backend/accounting_year_verify_v2.py').absolute.path,
                saved.path,
                '--sha256',
                metadata['sha256'],
              ],
              workingDirectory: Directory('../backend').absolute.path,
            ),
          );
          expect(checked!.exitCode, 0, reason: '${checked.stderr}');
          final verification = jsonDecode('${checked.stdout}');
          expect(verification['verified'], true);
          expect(verification['intrinsic_dependency_closure'], false);
        }, BackendHttp());
      } finally {
        await t.pumpWidget(const SizedBox.shrink());
        session?.dispose();
        api?.dispose();
        admin?.dispose();
        await t.binding.setSurfaceSize(null);
        await t.runAsync(() async {
          process?.kill();
          await process?.exitCode;
          await output?.cancel();
          await errors?.cancel();
          await temporary.delete(recursive: true);
        });
      }
    },
    timeout: const Timeout(Duration(minutes: 4)),
  );
}

import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:file_selector/file_selector.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:smartplan_office/api.dart';
import 'package:smartplan_office/business_accounting_openings.dart';
import 'package:smartplan_office/business_session.dart';
import 'package:smartplan_office/mail_attachment_widgets.dart';

import 'backend_integration_test.dart' show BackendHttp;

const openingHttpFixture = r'''
import json, os, sys, uuid
from pathlib import Path
from wsgiref.simple_server import WSGIServer, WSGIRequestHandler
from cryptography.fernet import Fernet
from socketserver import TCPServer
from core import Office
from online.web import create_app
from business_accounting import Accounting
from business_accounting_profile import AccountingPreparationProfile
from business_foundation import BusinessFoundation
for name in ('MS_CLIENT_ID','MS_CLIENT_SECRET','MS_REDIRECT_URI','OFFICE_VAULT_KEY','SMARTPLAN_DATABASE_DSN','SMARTPLAN_VAULT_KEY_FILE','SMARTPLAN_STORAGE_CONFIG_FILE'):
    os.environ.pop(name,None)
office=Office(Path(sys.argv[1])/'synthetic.db')
uid=office.add_user('native-opening@example.test','Synthetic-opening-password-123','owner');owner=dict(id=uid)
account=Accounting(office).create_account(owner,dict(request_id=uuid.uuid4().hex,code='OPEN',name='Synthetic opening bank',kind='bank',confirmation=True))
profile=AccountingPreparationProfile(office);state=profile.state(owner)
body=dict(expected_revision=state['revision'],state_hash=state['state_hash'],reason='Synthetic original founding date reviewed',evidence_reference='Synthetic original dated contract',
    profile=dict(legal_form='sole_proprietorship',accounting_method='euer',vat_regime='regular',vat_timing='cash',vat_effective_from='2026-01-01',bookkeeping_start='2026-01-01'))
preview=profile.preview(owner,body);profile.confirm(owner,body|dict(request_id=uuid.uuid4().hex,confirmation=True,preview_hash=preview['preview_hash']))
worker=office.add_user('native-opening-worker@example.test','Synthetic-opening-worker-password-123','accountant')
foundation=BusinessFoundation(office)
for permission in ('accounting.read','finance.read','bank.read','accounting.admin','accounting.prepare','finance.write'):
    foundation.save_grant(owner,dict(request_id=uuid.uuid4().hex,user_id=worker,permission=permission,scope='*',effect='allow',revision=0))
app=create_app(office=office,key=Fernet.generate_key(),host='office.example.test',storage_config={})
def proxy(environ,start_response):
    environ['HTTP_HOST']='office.example.test';environ['HTTP_X_FORWARDED_PROTO']='https'
    return app(environ,start_response)
class LoopbackServer(WSGIServer):
    def server_bind(self):
        TCPServer.server_bind(self);self.server_name,self.server_port=self.server_address;self.setup_environ()
class Quiet(WSGIRequestHandler):
    def log_message(self,*args):pass
server=LoopbackServer(('127.0.0.1',0),Quiet);server.set_app(proxy)
print(json.dumps(dict(port=server.server_port,token=office.login('native-opening-worker@example.test','Synthetic-opening-worker-password-123'),admin_token=office.login('native-opening@example.test','Synthetic-opening-password-123'),account=account,user_id=worker)),flush=True)
server.serve_forever()
''';

class OpeningHttpApi extends OfficeApi {
  OpeningHttpApi(String base) : super(baseUrl: base, apiVersion: 'v1');
  bool loseConfirm = true;
  final confirms = <Map<String, dynamic>>[];
  @override
  Future<dynamic> call(String path, [Map<String, dynamic>? body]) async {
    if (path.endsWith('$openingPath/confirm') && body != null)
      confirms.add(Map<String, dynamic>.from(jsonDecode(jsonEncode(body))));
    final response = await super.call(path, body);
    if (path.endsWith('$openingPath/confirm') && body != null && loseConfirm) {
      loseConfirm = false;
      throw const ApiException(
        0,
        'Synthetic reply lost after actual acceptance',
      );
    }
    return response;
  }
}

void main() {
  testWidgets(
    'actual native HTTP upload, negative bank opening, lost ACK, corrected zero, explicit void, original bytes and revoked access at 390px',
    (tester) async {
      final temporary = (await tester.runAsync(
        () => Directory.systemTemp.createTemp('synthetic-native-opening-'),
      ))!;
      final backend = Directory('../backend').absolute,
          python =
              Platform.environment['SMARTPLAN_TEST_PYTHON'] ??
              '${Directory('../backend').absolute.path}/.venv/${Platform.isWindows ? 'Scripts/python.exe' : 'bin/python'}';
      Process? process;
      StreamIterator<String>? output;
      StreamSubscription<String>? errors;
      BusinessSession? session;
      OpeningHttpApi? api;
      OfficeApi? admin;
      final diagnostics = StringBuffer(), saved = <VerifiedMailAttachment>[];
      await tester.binding.setSurfaceSize(const Size(390, 844));
      try {
        final setup = await tester.runAsync(() async {
          process = await Process.start(python, [
            '-u',
            '-c',
            openingHttpFixture,
            temporary.path,
          ], workingDirectory: backend.path);
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
          return jsonDecode(output!.current) as Map<String, dynamic>;
        });
        await HttpOverrides.runWithHttpOverrides(() async {
          api = OpeningHttpApi('http://127.0.0.1:${setup!['port']}')
            ..token = setup['token'];
          session = BusinessSession(api: api!);
          admin = OfficeApi(
            baseUrl: 'http://127.0.0.1:${setup['port']}',
            apiVersion: 'v1',
          )..token = setup['admin_token'];
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
              await tester.runAsync(
                () => Future<void>.delayed(const Duration(milliseconds: 10)),
              );
              await tester.pump(const Duration(milliseconds: 20));
            }
            expect(done, true, reason: 'HTTP timed out. $diagnostics');
            if (error != null) throw error!;
            return value as T;
          }

          Future<void> settled() async {
            // The progress indicator is in the lazy main list. Keep its first
            // section mounted while waiting for actual socket work to finish.
            if (find.byType(Scrollable).evaluate().isNotEmpty) {
              tester
                  .state<ScrollableState>(find.byType(Scrollable).first)
                  .position
                  .jumpTo(0);
              await tester.pump();
            }
            for (var i = 0; i < 1500; i++) {
              await tester.runAsync(
                () => Future<void>.delayed(const Duration(milliseconds: 10)),
              );
              await tester.pump(const Duration(milliseconds: 20));
              if (find.byType(LinearProgressIndicator).evaluate().isEmpty) {
                await tester.pump();
                return;
              }
            }
            fail('Native UI did not settle. $diagnostics');
          }

          Future<void> tap(String text) async {
            tester
                .state<ScrollableState>(find.byType(Scrollable).first)
                .position
                .jumpTo(0);
            await tester.pump();
            final f = find.text(text);
            try {
              await tester.scrollUntilVisible(
                f,
                250,
                scrollable: find.byType(Scrollable).first,
              );
            } catch (_) {
              fail(
                'Missing action $text; pending ${session!.pendingOpeningKeys}; UI: ${tester.widgetList<Text>(find.byType(Text)).map((v) => v.data).join(' | ')}; $diagnostics',
              );
            }
            await tester.ensureVisible(f);
            await tester.pumpAndSettle();
            await tester.tap(f);
            await tester.pump();
            await settled();
          }

          Future<void> enter(String label, String text) async {
            tester
                .state<ScrollableState>(find.byType(Scrollable).first)
                .position
                .jumpTo(0);
            await tester.pump();
            final f = find.byWidgetPredicate(
              (v) => v is TextField && v.decoration?.labelText == label,
            );
            await tester.scrollUntilVisible(
              f,
              250,
              scrollable: find.byType(Scrollable).first,
            );
            await tester.ensureVisible(f);
            await tester.pumpAndSettle();
            await tester.enterText(f, text);
            await tester.pump();
          }

          await request(() => session!.load());
          expect(openingWritable(session!), true);
          final raw = utf8.encode(
            '%PDF-1.4\nSynthetic native opening original\n%%EOF\n',
          );
          final originalFile = File(
            '${temporary.path}/synthetic-native-opening.pdf',
          );
          await tester.runAsync(() => originalFile.writeAsBytes(raw));
          await tester.pumpWidget(
            MaterialApp(
              home: BusinessOpeningBalancesPage(
                session: session!,
                accountId: setup['account']['id'],
                pickFile: () async => XFile(originalFile.path),
                exportFile: (file) async {
                  saved.add(file);
                },
              ),
            ),
          );
          await settled();
          expect(tester.takeException(), null);
          expect(
            find.byType(Scrollable),
            findsWidgets,
            reason:
                tester
                    .widgetList<Text>(find.byType(Text))
                    .map((v) => v.data)
                    .join(' | ') +
                ' $diagnostics',
          );
          await tap('Bestandsoriginal hochladen');
          expect(
            find.text(
              'Original gespeichert. Den passenden Nachweis ausdrücklich auswählen.',
            ),
            findsOneWidget,
            reason: tester
                .widgetList<Text>(find.byType(Text))
                .map((v) => v.data)
                .join(' | '),
          );
          expect(
            session!.pendingOpeningKeys,
            isEmpty,
            reason: tester
                .widgetList<Text>(find.byType(Text))
                .map((v) => v.data)
                .join(' | '),
          );
          expect(
            find.byType(Scrollable),
            findsWidgets,
            reason:
                tester
                    .widgetList<Text>(find.byType(Text))
                    .map((v) => v.data)
                    .join(' | ') +
                ' $diagnostics',
          );
          await tap('Anfangsbestand aus Nachweisen prüfen');
          Future<void> fill(String amount, String reason) async {
            tester
                .state<ScrollableState>(find.byType(Scrollable).first)
                .position
                .jumpTo(0);
            await tester.pump();
            final chooser = find.byWidgetPredicate(
              (v) =>
                  v is DropdownButtonFormField<String> &&
                  v.decoration.labelText ==
                      'Unveränderten Bestandsnachweis auswählen',
            );
            await tester.scrollUntilVisible(
              chooser,
              250,
              scrollable: find.byType(Scrollable).first,
            );
            await tester.ensureVisible(chooser);
            await tester.pumpAndSettle();
            expect(
              tester
                  .widget<DropdownButton<String>>(
                    find.descendant(
                      of: chooser,
                      matching: find.byType(DropdownButton<String>),
                    ),
                  )
                  .items,
              isNotEmpty,
              reason: tester
                  .widgetList<Text>(find.byType(Text))
                  .map((v) => v.data)
                  .join(' | '),
            );
            await tester.tap(chooser);
            await tester.pumpAndSettle();
            expect(
              find.text('Original · synthetic-native-opening.pdf'),
              findsWidgets,
              reason: tester
                  .widgetList<Text>(find.byType(Text))
                  .map((v) => v.data)
                  .join(' | '),
            );
            await tester.tap(
              find.text('Original · synthetic-native-opening.pdf').last,
            );
            await tester.pumpAndSettle();
            await enter('Belegter Anfangsbestand (EUR)', amount);
            await enter('Prüf- oder Korrekturgrund', reason);
            await tap(
              'Das Original belegt den Bestand vor der ersten Bewegung dieses Stichtags.',
            );
          }

          await fill(
            '-100,00',
            'Tatsächlich geprüfter synthetischer Banküberziehungsnachweis',
          );
          await tap('Anfangsbestand unverbindlich prüfen');
          await tap(
            'Ich bestätige genau diesen Bestand, Stichtag und Originalnachweis.',
          );
          await tap('Geprüften Anfangsbestand bestätigen');
          expect(session!.pendingOpeningKeys, ['accounting-opening-confirm']);
          await tap('Ursprünglichen Bestandsauftrag unverändert erneut senden');
          expect(api!.confirms.length, 2);
          expect(api!.confirms[0], api!.confirms[1]);
          expect(session!.pendingOpeningKeys, isEmpty);
          final id = setup['account']['id'];
          var history = openingHistory(
            await request(
              () => session!.read('$openingPath/accounts/$id/history'),
            ),
            id,
          );
          expect(businessItems(history).length, 1);
          expect(history['items'][0]['amount'], '-100.00');
          await tester.scrollUntilVisible(
            find.text('Unverändertes Bestandsoriginal öffnen'),
            250,
            scrollable: find.byType(Scrollable).first,
          );
          await tester.ensureVisible(
            find.text('Unverändertes Bestandsoriginal öffnen').first,
          );
          await tester.pumpAndSettle();
          await tester.tap(
            find.text('Unverändertes Bestandsoriginal öffnen').first,
          );
          await tester.pump();
          await settled();
          expect(saved.length, 1);
          expect(saved.single.bytes, raw);
          await tap('Anfangsbestand berichtigen');
          await fill('0', 'Synthetic corrected original explicitly shows zero');
          await tap('Anfangsbestand unverbindlich prüfen');
          await tap(
            'Ich bestätige genau diesen Bestand, Stichtag und Originalnachweis.',
          );
          await tap('Geprüften Anfangsbestand bestätigen');
          history = openingHistory(
            await request(
              () => session!.read('$openingPath/accounts/$id/history'),
            ),
            id,
          );
          expect(businessItems(history).length, 2);
          expect(history['items'][1]['amount'], '0.00');
          await tap('Anfangsbestand berichtigen');
          await enter(
            'Prüf- oder Korrekturgrund',
            'Synthetic original opening explicitly withdrawn',
          );
          await tap(
            'Unveränderten bisherigen Anfangsbestand zur Aufhebung prüfen',
          );
          await tap(
            'Ich bestätige genau diesen Bestand, Stichtag und Originalnachweis.',
          );
          await tap('Anfangsbestand belegt aufheben');
          history = openingHistory(
            await request(
              () => session!.read('$openingPath/accounts/$id/history'),
            ),
            id,
          );
          expect(businessItems(history).length, 3);
          expect(history['items'][2]['status'], 'void');
          final cash = openingLiquidity(
            await request(
              () => session!.read('$openingPath/liquidity?as_of=2026-11-02'),
            ),
            '2026-11-02',
          );
          expect(cash['known_balance_sum'], null);
          expect(cash['balance_total'], null);
          await request(
            () => admin!.call('/api/business/settings/permissions', {
              'request_id': 'f' * 32,
              'user_id': setup['user_id'],
              'permission': 'bank.read',
              'scope': '*',
              'effect': 'deny',
              'revision': 1,
            }),
          );
          await request(() => session!.load());
          await tester.pumpAndSettle();
          expect(
            find.text('Anfangsbestände nicht freigegeben'),
            findsOneWidget,
          );
          expect(find.text('Unveränderte Kontohistorie'), findsNothing);
          expect(find.textContaining('Synthetic opening bank'), findsNothing);
          expect(
            find.textContaining('synthetic-native-opening.pdf'),
            findsNothing,
          );
          expect(find.textContaining('OPEN ·'), findsNothing);
          expect(tester.takeException(), null);
        }, BackendHttp());
      } finally {
        await tester.pumpWidget(const SizedBox.shrink());
        session?.dispose();
        api?.dispose();
        admin?.dispose();
        await tester.binding.setSurfaceSize(null);
        await tester.runAsync(() async {
          process?.kill();
          await process?.exitCode;
          await output?.cancel();
          await errors?.cancel();
          await temporary.delete(recursive: true);
        });
      }
    },
    timeout: const Timeout(Duration(minutes: 3)),
  );
}

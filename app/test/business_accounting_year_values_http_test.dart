import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:file_selector/file_selector.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:smartplan_office/api.dart';
import 'package:smartplan_office/business_accounting_year_values.dart';
import 'package:smartplan_office/business_accounting_open_items_contract.dart';
import 'package:smartplan_office/business_session.dart';
import 'package:smartplan_office/mail_attachment_widgets.dart';

import 'backend_integration_test.dart' show BackendHttp;

const yearValuesHttpFixture = r'''
import json,os,uuid
from wsgiref.simple_server import WSGIServer,WSGIRequestHandler
from socketserver import TCPServer
from cryptography.fernet import Fernet
from test_accounting_year_openings import YearOpeningWorkflow
from business_foundation import BusinessFoundation
from online.web import create_app
for name in ('MS_CLIENT_ID','MS_CLIENT_SECRET','MS_REDIRECT_URI','OFFICE_VAULT_KEY','SMARTPLAN_DATABASE_DSN','SMARTPLAN_VAULT_KEY_FILE','SMARTPLAN_STORAGE_CONFIG_FILE'):
    os.environ.pop(name,None)
f=YearOpeningWorkflow('runTest');f.setUp();office=f.office
worker=office.add_user('year-values-native@example.test','Synthetic-year-values-123','accountant')
admin=office.add_user('year-values-admin@example.test','Synthetic-year-values-admin-123','owner')
foundation=BusinessFoundation(office)
for permission in ('accounting.read','finance.read','accounting.admin','accounting.prepare','finance.write'):
    foundation.save_grant(f.owner,dict(request_id=uuid.uuid4().hex,user_id=worker,permission=permission,scope='*',effect='allow',revision=0))
app=create_app(office=office,key=Fernet.generate_key(),host='office.example.test',storage_config={})
def proxy(environ,start_response):
    environ['HTTP_HOST']='office.example.test';environ['HTTP_X_FORWARDED_PROTO']='https';return app(environ,start_response)
class LoopbackServer(WSGIServer):
    def server_bind(self):
        TCPServer.server_bind(self);self.server_name,self.server_port=self.server_address;self.setup_environ()
class Quiet(WSGIRequestHandler):
    def log_message(self,*args):pass
server=LoopbackServer(('127.0.0.1',0),Quiet);server.set_app(proxy)
print(json.dumps(dict(port=server.server_port,token=office.login('year-values-native@example.test','Synthetic-year-values-123'),admin_token=office.login('year-values-admin@example.test','Synthetic-year-values-admin-123'),user_id=worker,old_item=f.old,controls=f.rules.controls)),flush=True)
try:server.serve_forever()
finally:f.doCleanups()
''';

class YearValuesHttpApi extends OfficeApi {
  YearValuesHttpApi(String url) : super(baseUrl: url, apiVersion: 'v1');
  int inFlight = 0;
  bool loseUpload = true, loseConfirm = true;
  final uploads = <Map<String, dynamic>>[], confirms = <Map<String, dynamic>>[];
  @override
  Future<dynamic> call(String path, [Map<String, dynamic>? body]) async {
    inFlight++;
    try {
      final upload = path.endsWith('$yearValuesPath/originals') && body != null,
          confirm = path.endsWith('$yearValuesPath/confirm') && body != null;
      if (upload) uploads.add(openItemCopy(body));
      if (confirm) confirms.add(openItemCopy(body));
      final r = await super.call(path, body);
      if (upload && loseUpload) {
        loseUpload = false;
        throw const ApiException(0, 'Synthetic actual year upload reply lost');
      }
      if (confirm && loseConfirm) {
        loseConfirm = false;
        throw const ApiException(
          0,
          'Synthetic actual year acceptance reply lost',
        );
      }
      return r;
    } finally {
      inFlight--;
    }
  }
}

void main() {
  testWidgets(
    'actual 390px yearly original upload, canonical prior values, controls, exact lost ACK, EÜR, history, correction and void',
    (t) async {
      final temp = (await t.runAsync(
        () => Directory.systemTemp.createTemp('native-year-values-'),
      ))!;
      Process? process;
      StreamIterator<String>? output;
      StreamSubscription<String>? errors;
      BusinessSession? session;
      YearValuesHttpApi? api;
      OfficeApi? admin;
      final diagnostics = StringBuffer(), saved = <VerifiedMailAttachment>[];
      await t.binding.setSurfaceSize(const Size(390, 844));
      try {
        final setup = await t.runAsync(() async {
          process = await Process.start(
            Platform.environment['SMARTPLAN_TEST_PYTHON'] ??
                '/tmp/smartplan-backend-verified/bin/python',
            ['-u', '-c', yearValuesHttpFixture],
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
          return jsonDecode(output!.current) as Map<String, dynamic>;
        });
        await HttpOverrides.runWithHttpOverrides(() async {
          api = YearValuesHttpApi('http://127.0.0.1:${setup!['port']}')
            ..token = setup['token'];
          session = BusinessSession(api: api!);
          admin = OfficeApi(baseUrl: api!.base, apiVersion: 'v1')
            ..token = setup['admin_token'];
          String ui() => t
              .widgetList<Text>(find.byType(Text))
              .map((v) => v.data)
              .join(' | ');
          Future<void> settle() async {
            var quiet = 0;
            for (var i = 0; i < 1500; i++) {
              await t.runAsync(
                () => Future<void>.delayed(const Duration(milliseconds: 10)),
              );
              await t.pump(const Duration(milliseconds: 20));
              if (api!.inFlight == 0) {
                if (++quiet >= 8) {
                  await t.pumpAndSettle();
                  return;
                }
              } else {
                quiet = 0;
              }
            }
            fail('HTTP UI did not settle: ${ui()} $diagnostics');
          }

          Future<T> request<T>(Future<T> Function() action) async {
            T? value;
            Object? error;
            var done = false;
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

          Finder scroll() {
            final dialog = find.byType(AlertDialog),
                all = find.byWidgetPredicate(
                  (v) => v is Scrollable && v.axis == Axis.vertical,
                );
            return dialog.evaluate().isEmpty
                ? all.first
                : find.descendant(of: dialog, matching: all).last;
          }

          Future<void> visible(Finder f) async {
            final sc = scroll();
            t.state<ScrollableState>(sc).position.jumpTo(0);
            await t.pump();
            try {
              await t.scrollUntilVisible(
                f,
                250,
                scrollable: sc,
                maxScrolls: 100,
              );
            } catch (_) {
              fail('Missing $f : ${ui()} $diagnostics');
            }
            await Scrollable.ensureVisible(t.element(f.first), alignment: 0.35);
            await t.pumpAndSettle();
          }

          Future<void> tap(String label) async {
            print('Native yearly step: $label');
            final f = find.text(label);
            await visible(f);
            await t.tap(f.first);
            await t.pump();
            await settle();
          }

          Future<void> enter(String label, String v) async {
            print('Native yearly field: $label');
            final f = find.byWidgetPredicate(
              (w) => w is TextField && w.decoration?.labelText == label,
            );
            await visible(f);
            await t.enterText(f.first, v);
            await t.pump();
          }

          Future<void> choose(String label, String option) async {
            final f = find.byWidgetPredicate(
              (w) =>
                  w is DropdownButtonFormField<String> &&
                  w.decoration.labelText == label,
            );
            await visible(f);
            await t.tap(f.first);
            await t.pumpAndSettle();
            final optionFinder = find.text(option);
            if (optionFinder.evaluate().isEmpty)
              await t.scrollUntilVisible(
                optionFinder,
                180,
                scrollable: find.byType(Scrollable).last,
                maxScrolls: 60,
              );
            await Scrollable.ensureVisible(
              t.element(optionFinder.last),
              alignment: 0.35,
            );
            await t.pumpAndSettle();
            await t.tap(optionFinder.last);
            await t.pumpAndSettle();
          }

          await request(() => session!.load());
          expect(yearValuesWritable(session!), true);
          final file = File('${temp.path}/reviewed-year-journal.pdf');
          final bytes = utf8.encode(
            '%PDF-1.4\nSynthetic independent original year journal coverage Jan-Oct with explicit old control totals\n%%EOF',
          );
          await t.runAsync(() => file.writeAsBytes(bytes));
          await t.pumpWidget(
            MaterialApp(
              home: BusinessYearValuesPage(
                session: session!,
                pickFile: () async => XFile(file.path),
                exportFile: (v) async => saved.add(v),
              ),
            ),
          );
          await settle();
          await tap('Jahresoriginal hochladen');
          expect(session!.pendingYearValuesKeys, hasLength(1));
          await tap('Unverändert erneut prüfen');
          expect(api!.uploads, hasLength(2));
          expect(api!.uploads[0], api!.uploads[1]);
          final state = yearValuesState(
            await request(() => session!.read(yearValuesPath)),
          );
          final original = businessItems(state['originals'])
              .firstWhere((v) => v['filename'] == 'reviewed-year-journal.pdf');
          await tap('Jahresvortrag vorbereiten');
          await enter('Belegter Zeitraum von (JJJJ-MM-TT)', '2026-01-01');
          await enter('Belegter Zeitraum bis (JJJJ-MM-TT)', '2026-10-31');
          await choose(
            'Eigenständiges Zeitraumjournal',
            '${original['filename']} · ${original['sha256'].substring(0, 12)}',
          );
          await choose(
            'Ursprüngliche Quellenart',
            'Bestätigte Altpostenfassung',
          );
          final old = setup['old_item'];
          await choose(
            'Unveränderte Altpostenfassung',
            '${old['payload']['invoice_number']} · ${old['payload']['counterparty_name']} · Fassung ${old['revision']}',
          );
          await enter('Ursprüngliches SKR04-Nettokonto', '5400');
          await enter('Ursprüngliches SKR04-Steuerkonto', '1406');
          await enter('Ursprüngliches SKR04-Vorsteuerkonto', '1406');
          await enter(
            'Alte Zahlungsbuchungen: eine Kennung je Zahlung in Originalreihenfolge',
            'OLD-2026-081',
          );
          await enter(
            'Ursprüngliche Vorsteuerbuchungsidentität (nur Lieferantenrechnung)',
            'OLD-2026-061',
          );
          await tap('Geprüfte ursprüngliche Quelle hinzufügen');
          for (final row in businessItems(setup['controls'])) {
            await tap('Belegte Kontrollsumme hinzufügen');
            await choose(
              'Ursprüngliches Journal',
              row['ledger'] == 'euer' ? 'EÜR' : 'Umsatzsteuer',
            );
            await choose(
              'Ursprüngliche Kategorie',
              {
                'materials': 'Material',
                'paid_input_vat': 'Bezahlte abziehbare Vorsteuer',
                'input_vat': 'Vorsteuerrecht',
              }[row['category']]!,
            );
            await enter('Geprüftes ursprüngliches SKR04-Konto', row['account']);
            await enter('Belegter vorzeichenbehafteter Betrag', row['amount']);
            await tap('Geprüfte Angaben übernehmen');
          }
          await tap('Buchführungsmethode unverändert fortgeführt');
          await tap(
            'Ursprüngliches Journal im erklärten Zeitraum vollständig geprüft',
          );
          await tap(
            'Keine unzulässigen Anlagen-, Lohn-, Privat- oder Sonderwerte enthalten',
          );
          await enter(
            'Prüf-/Korrekturgrund',
            'Actual native original journal review',
          );
          await tap('Originale und Jahreswerte vorprüfen');
          expect(
            find.textContaining('Die Jahreswerte konnten nicht'),
            findsNothing,
            reason: ui(),
          );
          await tap(
            'Genau diese ursprünglichen Werte und Nachweise verbindlich bestätigen',
          );
          await tap('Geprüfte Jahresfassung annehmen');
          expect(session!.pendingYearValuesKeys, hasLength(1), reason: ui());
          await tap('Unverändert erneut prüfen');
          expect(api!.confirms, hasLength(2));
          expect(api!.confirms[0], api!.confirms[1]);
          final accepted = yearValuesState(
            await request(() => session!.read(yearValuesPath)),
          );
          expect(accepted['revision'], 1);
          final entry = yearValuesEntry(accepted['items'][0]);
          expect(entry['details']['cash_flow_created'], false);
          expect(entry['details']['new_input_vat_claim_created'], false);
          expect(
            entry['details']['historical_postings'][2]['date'],
            '2026-06-11',
          );
          await tap('EÜR, Gegenbuchungen und Perioden prüfen');
          await enter(
            'Fachliche Begründung',
            'Actual native historical EÜR classification',
          );
          await enter(
            'Nachweis / Prüfgrundlage',
            'Reviewed original year journal',
          );
          // The existing EÜR form requires a separate preview and explicit acceptance.
          final button = find.text('Buchung unverbindlich prüfen');
          if (button.evaluate().isNotEmpty) {
            await tap('Buchung unverbindlich prüfen');
          } else {
            fail('Expected existing EÜR preview action: ${ui()}');
          }
          await tap(
            'Ich habe Quelle, fachliche Einordnung, Beträge, Zeitraum und Konten geprüft und bestätige diesen Vorgang.',
          );
          await tap('Buchung verbindlich festhalten');
          final report = await request(
            () => session!.read('/accounting/euer/report?year=2026'),
          );
          expect(report['totals']['confirmed_expenses'], '59.50');
          expect(report['totals']['confirmed_input_vat'], '19.00');
          expect(report['cash_movements'], isEmpty);
          expect(report['historical_year_values']['cash_flow_created'], false);
          // Return to source page; a source change stays blocked until explicit EÜR reversal.
          await t.pageBack();
          await settle();
          await tap('Belegte Korrektur vorbereiten');
          await enter(
            'Prüf-/Korrekturgrund',
            'Blocked while historical EÜR remains active',
          );
          await tap('Buchführungsmethode unverändert fortgeführt');
          await tap(
            'Ursprüngliches Journal im erklärten Zeitraum vollständig geprüft',
          );
          await tap(
            'Keine unzulässigen Anlagen-, Lohn-, Privat- oder Sonderwerte enthalten',
          );
          await tap('Originale und Jahreswerte vorprüfen');
          await visible(find.textContaining('gegenbuchen'));
          expect(
            find.textContaining('gegenbuchen'),
            findsWidgets,
            reason: ui(),
          );
          await tap('Bearbeitung schließen');
          final journal = await request(
            () => session!.read('/accounting/euer/journal?limit=50&offset=0'),
          );
          final active = businessItems(journal)
              .firstWhere((v) => v['operation'] == 'opening_year_values');
          final es = await request(() => session!.read('/accounting/euer'));
          final rb = {
            'expected_revision': es['revision'],
            'state_hash': es['state_hash'],
            'operation': 'reverse',
            'payload': {'entry_id': active['id']},
            'reason': 'Explicit actual original counterposting before source correction',
            'evidence_reference': 'Synthetic reviewed correction',
          };
          final rp = await request(
            () => api!.call(session!.path('/accounting/euer/preview'), rb),
          );
          await request(
            () => api!.call(session!.path('/accounting/euer/confirm'), {
              ...rb,
              'request_id': 'b' * 32,
              'confirmation': true,
              'preview_hash': rp['preview_hash'],
            }),
          );
          await tap('Unverändert aufheben');
          await enter(
            'Prüf-/Korrekturgrund',
            'Explicit actual year source withdrawal',
          );
          await tap('Originale und Jahreswerte vorprüfen');
          await tap(
            'Genau diese ursprünglichen Werte und Nachweise verbindlich bestätigen',
          );
          await tap('Geprüfte Jahresfassung annehmen');
          expect(
            (await request(
              () => session!.read(yearValuesPath),
            ))['items'][0]['payload']['status'],
            'void',
          );
          await tap('Belegte Korrektur vorbereiten');
          await enter(
            'Prüf-/Korrekturgrund',
            'Explicit corrected original year review after withdrawal',
          );
          await tap('Buchführungsmethode unverändert fortgeführt');
          await tap(
            'Ursprüngliches Journal im erklärten Zeitraum vollständig geprüft',
          );
          await tap(
            'Keine unzulässigen Anlagen-, Lohn-, Privat- oder Sonderwerte enthalten',
          );
          await tap('Originale und Jahreswerte vorprüfen');
          await tap(
            'Genau diese ursprünglichen Werte und Nachweise verbindlich bestätigen',
          );
          await tap('Geprüfte Jahresfassung annehmen');
          final corrected = yearValuesState(
            await request(() => session!.read(yearValuesPath)),
          );
          expect(corrected['revision'], 3);
          expect(corrected['items'][0]['payload']['status'], 'active');
          await tap('Geschützte Jahresoriginale (2)');
          await tap('reviewed-year-journal.pdf');
          expect(saved, hasLength(1));
          expect(saved.single.bytes, bytes);
          expect(saved.single.sha256, original['sha256']);
          await tap('Ursprüngliche Jahresfassungen');
          await tap('Ursprüngliche Fassung 1 · Aktiv');
          await tap('Diese ursprüngliche Quelle prüfen');
          await visible(find.text('Originalgebundene Jahres-/EÜR-Quelle'));
          expect(
            find.text('Originalgebundene Jahres-/EÜR-Quelle'),
            findsOneWidget,
          );
          await request(
            () => admin!.call('/api/business/settings/permissions', {
              'request_id': 'c' * 32,
              'user_id': setup['user_id'],
              'permission': 'finance.read',
              'scope': '*',
              'effect': 'deny',
              'revision': 1,
            }),
          );
          await tap('Neu laden');
          expect(
            find.textContaining('Jahreswerte sind in diesem aktuellen Kontext'),
            findsOneWidget,
          );
          expect(find.text(entry['content_hash']), findsNothing);
          expect(t.takeException(), null);
        }, BackendHttp());
      } finally {
        await t.pumpWidget(const SizedBox());
        session?.dispose();
        api?.dispose();
        admin?.dispose();
        await t.runAsync(() async {
          process?.kill();
          if (process != null)
            await process!.exitCode.timeout(
              const Duration(seconds: 5),
              onTimeout: () => -1,
            );
          await output?.cancel();
          await errors?.cancel();
          await temp.delete(recursive: true);
        });
        await t.binding.setSurfaceSize(null);
      }
    },
  );
}

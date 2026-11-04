import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:file_selector/file_selector.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:smartplan_office/api.dart';
import 'package:smartplan_office/business_accounting_historical_assets.dart';
import 'package:smartplan_office/business_session.dart';
import 'package:smartplan_office/mail_attachment_widgets.dart';

import 'backend_integration_test.dart' show BackendHttp;

import 'business_accounting_openings_http_widget_test.dart'
    show openingHttpFixture;

class HistoricalHttpApi extends OfficeApi {
  HistoricalHttpApi(String base) : super(baseUrl: base, apiVersion: 'v1');
  final originals = <Map<String, dynamic>>[],
      confirms = <Map<String, dynamic>>[],
      euerConfirms = <Map<String, dynamic>>[];
  int inFlight = 0;
  bool loseOriginal = true, loseConfirm = true, loseEuer = true;
  @override
  Future<dynamic> call(String path, [Map<String, dynamic>? body]) async {
    inFlight++;
    try {
      final original =
              path.endsWith('$historicalAssetPath/originals') && body != null,
          confirm =
              path.endsWith('$historicalAssetPath/confirm') && body != null,
          euer = path.endsWith('/accounting/euer/confirm') && body != null;
      if (original)
        originals.add(Map<String, dynamic>.from(jsonDecode(jsonEncode(body))));
      if (confirm)
        confirms.add(Map<String, dynamic>.from(jsonDecode(jsonEncode(body))));
      if (euer)
        euerConfirms.add(
          Map<String, dynamic>.from(jsonDecode(jsonEncode(body))),
        );
      final result = await super.call(path, body);
      if (original && loseOriginal) {
        loseOriginal = false;
        throw const ApiException(0, 'Synthetic actual original ACK lost');
      }
      if (confirm && loseConfirm) {
        loseConfirm = false;
        throw const ApiException(0, 'Synthetic actual source ACK lost');
      }
      if (euer && loseEuer) {
        loseEuer = false;
        throw const ApiException(0, 'Synthetic actual EÜR ACK lost');
      }
      return result;
    } finally {
      inFlight--;
    }
  }
}

void main() {
  testWidgets(
    'actual historical 390px HTTP originals, Unicode identity, three lost ACKs, annual AfA, source correction, void, journal and revoked access',
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
      HistoricalHttpApi? api;
      OfficeApi? admin;
      final diagnostics = StringBuffer(), saved = <VerifiedMailAttachment>[];
      await tester.binding.setSurfaceSize(const Size(390, 844));
      try {
        final setup = await tester.runAsync(() async {
          process = await Process.start(python, [
            '-u',
            '-c',
            openingHttpFixture.replaceAll(
              "'finance.read','bank.read'",
              "'finance.read'",
            ),
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
          api = HistoricalHttpApi('http://127.0.0.1:${setup!['port']}')
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

          Finder mainScroll() {
            final dialog = find.byType(AlertDialog);
            final all = find.byWidgetPredicate(
              (v) => v is Scrollable && v.axis == Axis.vertical,
            );
            return dialog.evaluate().isEmpty
                ? all.first
                : find.descendant(of: dialog, matching: all).last;
          }

          String ui() => tester
              .widgetList<Text>(find.byType(Text))
              .map((v) => v.data)
              .join(' | ');
          Future<void> settled() async {
            var quiet = 0;
            for (var i = 0; i < 1500; i++) {
              await tester.runAsync(
                () => Future<void>.delayed(const Duration(milliseconds: 10)),
              );
              await tester.pump(const Duration(milliseconds: 20));
              if (api!.inFlight == 0) {
                quiet++;
                if (quiet >= 8) {
                  await tester.pumpAndSettle();
                  return;
                }
              } else {
                quiet = 0;
              }
            }
            fail('Native UI did not settle: ${ui()} $diagnostics');
          }

          Future<void> visible(Finder f) async {
            final scroll = mainScroll();
            tester.state<ScrollableState>(scroll).position.jumpTo(0);
            await tester.pump();
            try {
              await tester.scrollUntilVisible(f, 250, scrollable: scroll);
            } catch (_) {
              fail('Missing $f: ${ui()} $diagnostics');
            }
            await tester.ensureVisible(f.first);
            await tester.pumpAndSettle();
            await settled();
          }

          Future<void> tap(String label) async {
            final f = find.text(label);
            await visible(f);
            await tester.tap(f.first);
            await tester.pump();
            await settled();
          }

          Future<void> enter(String label, String value) async {
            final f = find.byWidgetPredicate(
              (v) => v is TextField && v.decoration?.labelText == label,
            );
            await visible(f);
            await tester.enterText(f, value);
            await tester.pump();
          }

          Future<void> choose(String label, String option) async {
            final f = find.byWidgetPredicate(
              (v) =>
                  v is DropdownButtonFormField<String> &&
                  v.decoration.labelText == label,
            );
            await visible(f);
            await tester.tap(f);
            await tester.pumpAndSettle();
            await tester.tap(find.text(option).last);
            await tester.pumpAndSettle();
          }

          await request(() => session!.load());
          expect(historicalAssetsWritable(session!), true);
          final raw = utf8.encode(
            '%PDF-1.4\nSynthetic native opening original\n%%EOF\n',
          );
          final originalFile = File(
            '${temporary.path}/synthetic-native-opening.pdf',
          );
          await tester.runAsync(() => originalFile.writeAsBytes(raw));
          await tester.pumpWidget(
            MaterialApp(
              home: BusinessHistoricalAssetsPage(
                session: session!,
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
          expect(session!.can('bank.read'), false);
          await tap('Historische Anlage aus Originalen vorbereiten');
          await enter('Betriebliche Inventarnummer', ' ＭAẞE-01 ');
          await tap('Inventarnummer eindeutig prüfen');
          await tap('Historisches Anlagenoriginal hochladen');
          expect(session!.pendingHistoricalAssetKeys.length, 1, reason: ui());
          await tap('Ursprünglichen Anlagenauftrag unverändert erneut senden');
          expect(api!.originals.length, 2);
          expect(api!.originals[0], api!.originals[1]);
          expect(session!.pendingHistoricalAssetKeys, isEmpty);
          await tap('Historische Anlage aus Originalen vorbereiten');
          await enter('Betriebliche Inventarnummer', ' ＭAẞE-01 ');
          await tap('Inventarnummer eindeutig prüfen');
          await choose(
            'Unverändertes Anlagenoriginal ausdrücklich wählen',
            'synthetic-native-opening.pdf',
          );
          await tap('Ausgewähltes Anlagenoriginal öffnen');
          expect(saved.single.bytes, raw);
          for (final e in <String, String>{
            'Eindeutige Position im Anlagenoriginal':
                'Position 1 · synthetic machine',
            'Historie belegt bis (JJJJ-MM-TT)': '2025-12-31',
            'Bezeichnung der historischen Anlage':
                'Synthetic machine historic original',
            'Ursprüngliche Anschaffung (JJJJ-MM-TT)': '2024-01-15',
            'Ursprünglicher AfA-/Nutzungsbeginn (JJJJ-MM-TT)': '2024-01-15',
            'Belegte ursprüngliche Nutzungsdauer (Monate)': '36',
            'Ursprüngliche Bruttokosten (EUR)': '4284',
            'Abziehbare ursprüngliche Vorsteuer (EUR)': '684',
            'Belegte betriebliche Kostenbasis (EUR)': '3600',
            'Belegte AfA vor dem Übernahmejahr (EUR)': '2400',
            'Bereits im Übernahmejahr gebuchte AfA (EUR)': '0',
            'Belegter Restbuchwert am Übernahmestichtag (EUR)': '1200',
            'Geprüftes SKR04-Anlagenkonto': '0440',
            'Prüf-, Korrektur- oder Aufhebungsgrund':
                'Actual synthetic historical original reviewed',
          }.entries) {
            await enter(e.key, e.value);
          }
          await choose(
            'Tatsächlich belegtes bisheriges Rundungsverfahren',
            historicalAssetRounding['cumulative_months_half_up']!,
          );
          await tap(
            'Originalwerte, ausschließlich betriebliche bewegliche Anlage und unveränderte lineare Historie einschließlich bisheriger Rundung ausdrücklich geprüft.',
          );
          await tap('Anlagenvortrag unverbindlich prüfen');
          await tap(
            'Ich bestätige genau diese historische Anlage, Originalposition und Vortragswerte.',
          );
          await tap('Geprüften Anlagenvortrag bestätigen');
          expect(session!.pendingHistoricalAssetKeys, [
            'historical-asset-confirm',
          ], reason: ui());
          await tap('Ursprünglichen Anlagenauftrag unverändert erneut senden');
          expect(api!.confirms.length, 2);
          expect(api!.confirms[0], api!.confirms[1]);
          expect(session!.pendingHistoricalAssetKeys, isEmpty);
          var history = historicalAssetHistory(
            await request(
              () => session!.read(historicalAssetHistoryPath('masse-01')),
            ),
            'masse-01',
          );
          expect(businessItems(history).length, 1);
          final originalEvent = history['items'][0];
          expect(originalEvent['asset']['inventory_number'], ' ＭAẞE-01 ');
          expect(originalEvent['start_year']['amount'], '1200.00');
          await tap('Folge-AfA im EÜR-Journal prüfen');
          expect(find.byType(AlertDialog), findsOneWidget, reason: ui());
          for (final e in {
            'AfA-Jahr': '2026',
            'Geprüftes SKR04-Sachkonto': '6220',
            'Fachliche Begründung': 'Synthetic documented remaining annual AfA',
            'Nachweis / Prüfgrundlage':
                'Synthetic historic position 1 and annual ledger',
          }.entries) {
            await enter(e.key, e.value);
          }
          await tap('Buchung unverbindlich prüfen');
          await tap(
            'Ich habe Quelle, fachliche Einordnung, Beträge, Zeitraum und Konten geprüft und bestätige diesen Vorgang.',
          );
          await tap('Buchung verbindlich festhalten');
          expect(session!.pending('accounting-euer'), true);
          await tap('Ursprünglichen Auftrag erneut senden');
          tester.state<ScrollableState>(mainScroll()).position.jumpTo(0);
          await tester.pump();
          expect(api!.euerConfirms.length, 2, reason: ui());
          expect(api!.euerConfirms[0], api!.euerConfirms[1]);
          final report = await request(
            () => session!.read('/accounting/euer/report?year=2026'),
          );
          final rows = historicalAssetReport(report);
          expect(rows.single['continuation']['amount'], '1200.00');
          expect(
            rows.single['depreciation']['postings'].single['amount'],
            '-1200.00',
          );
          expect(
            rows.single['depreciation']['postings'].single['ledger'],
            'euer',
          );
          await tap('Buchungen und Korrekturen');
          await tap('Geprüft berichtigen');
          await enter('Geprüftes SKR04-Sachkonto', '6221');
          await enter(
            'Fachliche Begründung',
            'Synthetic explicitly corrected depreciation account',
          );
          await enter(
            'Nachweis / Prüfgrundlage',
            'Synthetic historical account review',
          );
          await tap('Buchung unverbindlich prüfen');
          await tap(
            'Ich habe Quelle, fachliche Einordnung, Beträge, Zeitraum und Konten geprüft und bestätige diesen Vorgang.',
          );
          await tap('Buchung verbindlich festhalten');
          final correctedReport = await request(
            () => session!.read('/accounting/euer/report?year=2026'),
          );
          final correctedAfa = historicalAssetReport(correctedReport)
              .single['depreciation'];
          expect(correctedAfa['operation'], 'correct');
          expect(correctedAfa['postings'].length, 2);
          expect(correctedAfa['postings'].last['account'], '6221');
          await tap('Jahr und Perioden');
          Future<void> period(String action) async {
            await tap('Monatsperiode prüfen');
            await enter('Monatsperiode (JJJJ-MM)', '2026-12');
            await choose('Periodenaktion', action);
            for (final label in [
              'Bank- und Kassenbewegungen vollständig abgeglichen',
              'Originalbelege für diese Periode vollständig geprüft',
              'Sonderfälle und erforderliche Berichtigungen geprüft',
            ])
              await tap(label);
            await enter('Fachliche Begründung', 'Synthetic explicit $action');
            await enter(
              'Nachweis / Prüfgrundlage',
              'Synthetic actual period control',
            );
            await tap('Buchung unverbindlich prüfen');
            tester.state<ScrollableState>(mainScroll()).position.jumpTo(0);
            await tester.pump();
            expect(
              find.text('Geprüfte Buchungsvorschau'),
              findsOneWidget,
              reason: ui(),
            );
            await tap(
              'Ich habe Quelle, fachliche Einordnung, Beträge, Zeitraum und Konten geprüft und bestätige diesen Vorgang.',
            );
            await tap('Buchung verbindlich festhalten');
          }

          await period('Periode schließen');
          final closed = await request(() => session!.read('/accounting/euer'));
          expect(closed['periods'].single['status'], 'closed');
          await expectLater(
            request(
              () =>
                  session!.api.call(session!.path('/accounting/euer/preview'), {
                    'operation': 'reverse',
                    'payload': {'entry_id': correctedAfa['id']},
                    'expected_revision': closed['revision'],
                    'state_hash': closed['state_hash'],
                    'reason': 'Synthetic blocked closed-period reversal',
                    'evidence_reference': 'Synthetic actual closed period',
                  }),
            ),
            throwsA(isA<ApiException>().having((e) => e.status, 'status', 409)),
          );
          await period('Periode begründet wieder öffnen');
          // Actual active AfA blocks changing its source. This is a server assertion,
          // not an invented fixture or a client-side omission.
          final state = historicalAssetState(
            await request(() => session!.read(historicalAssetPath)),
          );
          final corrected = {
            for (final k in historicalAssetInput) k: originalEvent[k],
            'expected_revision': state['revision'],
            'state_hash': state['state_hash'],
            'reason': 'Synthetic blocked correction while AfA active',
          };
          await expectLater(
            request(
              () => session!.api.call(
                session!.path('$historicalAssetPath/preview'),
                corrected,
              ),
            ),
            throwsA(isA<ApiException>().having((e) => e.status, 'status', 409)),
          );
          // Reverse through the existing real EÜR journal UI.
          await tap('Buchungen und Korrekturen');
          await tap('Genau gegenbuchen');
          await enter(
            'Fachliche Begründung',
            'Synthetic reversal before source correction',
          );
          await enter(
            'Nachweis / Prüfgrundlage',
            'Synthetic original correction review',
          );
          await tap('Buchung unverbindlich prüfen');
          await tap(
            'Ich habe Quelle, fachliche Einordnung, Beträge, Zeitraum und Konten geprüft und bestätige diesen Vorgang.',
          );
          await tap('Buchung verbindlich festhalten');
          await tester.pageBack();
          await tester.pump();
          await settled();
          await tap('Anlagenvortrag berichtigen');
          await enter(
            'Bezeichnung der historischen Anlage',
            'Synthetic corrected historic description',
          );
          await enter(
            'Prüf-, Korrektur- oder Aufhebungsgrund',
            'Synthetic source description correction',
          );
          await tap(
            'Originalwerte, ausschließlich betriebliche bewegliche Anlage und unveränderte lineare Historie einschließlich bisheriger Rundung ausdrücklich geprüft.',
          );
          await tap('Anlagenvortrag unverbindlich prüfen');
          await tap(
            'Ich bestätige genau diese historische Anlage, Originalposition und Vortragswerte.',
          );
          await tap('Geprüften Anlagenvortrag bestätigen');
          history = historicalAssetHistory(
            await request(
              () => session!.read(historicalAssetHistoryPath('masse-01')),
            ),
            'masse-01',
          );
          expect(businessItems(history).length, 2);
          await tap('Anlagenvortrag berichtigen');
          await enter(
            'Prüf-, Korrektur- oder Aufhebungsgrund',
            'Synthetic explicit withdrawal retaining immutable original',
          );
          await tap(
            'Unveränderten bisherigen Anlagenvortrag zur Aufhebung prüfen',
          );
          await tap(
            'Ich bestätige genau diese historische Anlage, Originalposition und Vortragswerte.',
          );
          await tap('Anlagenvortrag belegt aufheben');
          history = historicalAssetHistory(
            await request(
              () => session!.read(historicalAssetHistoryPath('masse-01')),
            ),
            'masse-01',
          );
          expect(businessItems(history).length, 3);
          expect(history['items'][2]['status'], 'void');
          await tap('Unverändertes Anlagenoriginal öffnen');
          expect(saved.last.bytes, raw);
          await request(
            () => admin!.call('/api/business/settings/permissions', {
              'request_id': 'f' * 32,
              'user_id': setup['user_id'],
              'permission': 'finance.read',
              'scope': '*',
              'effect': 'deny',
              'revision': 1,
            }),
          );
          await request(() => session!.load());
          await tester.pumpAndSettle();
          expect(
            find.text('Historische Anlagen nicht freigegeben'),
            findsOneWidget,
          );
          expect(find.textContaining('masse-01'), findsNothing);
          expect(find.textContaining('Synthetic corrected'), findsNothing);
          expect(
            find.textContaining('synthetic-native-opening.pdf'),
            findsNothing,
          );
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
    timeout: const Timeout(Duration(minutes: 5)),
  );
}

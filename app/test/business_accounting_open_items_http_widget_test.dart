@Tags(['posix_backend'])
library;

import 'dart:async';
import 'dart:convert';
import 'dart:io';
import 'dart:typed_data';

import 'package:file_selector/file_selector.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:smartplan_office/api.dart';
import 'package:smartplan_office/business_accounting_open_items.dart';
import 'package:smartplan_office/business_session.dart';
import 'package:smartplan_office/mail_attachment_widgets.dart';

import 'backend_integration_test.dart' show BackendHttp;

import 'business_accounting_openings_http_widget_test.dart'
    show openingHttpFixture;

// Opt-in diagnostics contain method/path/duration only, never credentials or
// document bodies. Keep ordinary full-suite output quiet.
final _traceEnabled =
    Platform.environment['SMARTPLAN_TEST_TRACE_OPEN_ITEMS'] == '1';
void _traceOpenItems(String message) {
  if (_traceEnabled) print(message);
}

class OpenItemsHttpApi extends OfficeApi {
  OpenItemsHttpApi(String base) : super(baseUrl: base, apiVersion: 'v1');
  final originals = <Map<String, dynamic>>[],
      confirms = <Map<String, dynamic>>[],
      euerConfirms = <Map<String, dynamic>>[];
  int inFlight = 0;
  bool loseOriginal = true, loseConfirm = true, loseEuer = true;
  @override
  Future<dynamic> call(String path, [Map<String, dynamic>? body]) async {
    inFlight++;
    final timer = Stopwatch()..start();
    final method = body == null ? "GET" : "POST";
    final origin =
        _traceEnabled &&
            StackTrace.current.toString().contains(
              "_loadCapabilities.<anonymous closure>",
            )
        ? "timer"
        : "action";
    _traceOpenItems(
      "TRACE begin $method $path inFlight=$inFlight origin=$origin",
    );
    try {
      final original = path.endsWith('$openItemPath/originals') && body != null,
          confirm = path.endsWith('$openItemPath/confirm') && body != null,
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
      _traceOpenItems(
        "TRACE end $method $path ms=${timer.elapsedMilliseconds} inFlight=$inFlight",
      );
    }
  }

  @override
  Future<Uint8List> bytes(
    String path, {
    required String mediaType,
    int maxBytes = 20 * 1024 * 1024,
  }) async {
    inFlight++;
    final timer = Stopwatch()..start();
    _traceOpenItems('TRACE begin GET-BYTES $path inFlight=$inFlight');
    try {
      return await super.bytes(path, mediaType: mediaType, maxBytes: maxBytes);
    } finally {
      inFlight--;
      _traceOpenItems(
        'TRACE end GET-BYTES $path ms=${timer.elapsedMilliseconds} inFlight=$inFlight',
      );
    }
  }
}

void main() {
  testWidgets(
    'actual opening-item 390px HTTP original import, prior cents, two rest payments, lost ACK, EÜR, correction, void and access loss',
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
      OpenItemsHttpApi? api;
      OfficeApi? admin;
      final diagnostics = StringBuffer(), saved = <VerifiedMailAttachment>[];
      await tester.binding.setSurfaceSize(const Size(390, 844));
      try {
        final setup = await tester.runAsync(() async {
          process = await Process.start(python, [
            '-u',
            '-c',
            openingHttpFixture.replaceAll(
              "vat_effective_from='2026-01-01'",
              "vat_effective_from='2025-01-01'",
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
          api = OpenItemsHttpApi('http://127.0.0.1:${setup!['port']}')
            ..token = setup['token'];
          session = BusinessSession(api: api!);
          admin = OfficeApi(
            baseUrl: 'http://127.0.0.1:${setup['port']}',
            apiVersion: 'v1',
          )..token = setup['admin_token'];
          // Socket/file work advances in real time. Do not fast-forward the
          // 30-second metadata timer while only waiting for that work. Frames
          // needed by navigation and scrolling still advance after IO is idle.
          bool waitingForIo() =>
              // The status bar can be outside the lazy scroll viewport while
              // file IO is still pending, before the next HTTP call starts.
              tester
                  .stateList(find.byType(BusinessOpenItemsPage))
                  .any((state) => (state as dynamic).busy == true) ||
              api!.inFlight > 0 ||
              session!.loading ||
              find.byType(LinearProgressIndicator).evaluate().isNotEmpty ||
              find.byType(CircularProgressIndicator).evaluate().isNotEmpty;
          Future<void> tick() async {
            await tester.runAsync(
              () => Future<void>.delayed(const Duration(milliseconds: 10)),
            );
            await tester.pump(
              !waitingForIo() && tester.binding.hasScheduledFrame
                  ? const Duration(milliseconds: 100)
                  : Duration.zero,
            );
          }

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
            final deadline = Stopwatch()..start();
            while (!done && deadline.elapsed < const Duration(seconds: 40)) {
              await tick();
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
          var settleNumber = 0;
          Future<void> settled([bool Function()? ready]) async {
            final number = ++settleNumber;
            final timer = Stopwatch()..start();
            _traceOpenItems("TRACE settle begin $number");
            var quiet = 0, frames = 0;
            while (timer.elapsed < const Duration(seconds: 40)) {
              await tick();
              frames++;
              final exception = tester.takeException();
              if (exception != null) throw exception;
              if (!waitingForIo() &&
                  !tester.binding.hasScheduledFrame &&
                  (ready?.call() ?? true)) {
                quiet++;
                if (quiet >= 2) {
                  _traceOpenItems(
                    "TRACE settle end $number ms=${timer.elapsedMilliseconds} loops=$frames",
                  );
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
            await settled();
            await tester.tap(find.text(option).last);
            await settled();
          }

          await request(() => session!.load());
          expect(openItemsWritable(session!), true);
          // This separate original explicitly proves the synthetic bank opening.
          // A missing opening must stay unknown, never become a fictitious zero.
          const opening = '/accounting/opening-balances';
          final openingState = await request(() => session!.read(opening));
          final openingOriginal = await request(
            () => api!.call(session!.path('$opening/originals'), {
              'request_id': 'a' * 32,
              'account_id': setup['account']['id'],
              'filename': 'synthetic-bank-opening.pdf',
              'media_type': 'application/pdf',
              'content_base64': base64Encode(
                utf8.encode(
                  '%PDF-1.4\nSynthetic bank opening EUR 1000.00 before first movement 2026-01-01\n%%EOF\n',
                ),
              ),
            }),
          );
          final openingBody = <String, dynamic>{
            'expected_revision': openingState['revision'],
            'state_hash': openingState['state_hash'],
            'account_id': setup['account']['id'],
            'account_revision': setup['account']['revision'],
            'profile_ref': openingState['profile_ref'],
            'status': 'active',
            'opening_date': '2026-01-01',
            'amount': '1000.00',
            'source': {
              'kind': 'original',
              'original_id': openingOriginal['id'],
              'sha256': openingOriginal['sha256'],
              'evidence_type': 'account_statement',
              'at_start_of_day': true,
            },
            'reason': 'Synthetic original bank balance independently reviewed',
          };
          final openingPreview = await request(
            () => api!.call(session!.path('$opening/preview'), openingBody),
          );
          await request(
            () => api!.call(session!.path('$opening/confirm'), {
              ...openingBody,
              'request_id': 'b' * 32,
              'preview_hash': openingPreview['preview_hash'],
              'confirmation': true,
            }),
          );

          final files = <File>[];
          for (final name in [
            'invoice',
            'cutover',
            'payment-one',
            'payment-two',
            'payable-invoice',
            'payable-cutover',
            'payable-old-vat',
            'payable-payment',
          ]) {
            final file = File('${temporary.path}/$name.pdf');
            await tester.runAsync(
              () => file.writeAsBytes(
                utf8.encode('%PDF-1.4\nSynthetic opening item $name\n%%EOF\n'),
              ),
            );
            files.add(file);
          }
          var picked = 0;
          await tester.pumpWidget(
            MaterialApp(
              home: BusinessOpenItemsPage(
                session: session!,
                pickFile: () async => XFile(files[picked++].path),
                exportFile: (v) async {
                  saved.add(v);
                },
              ),
            ),
          );
          await settled();
          Future<void> keyTap(String key) async {
            final f = find.byKey(ValueKey('opening-item-$key'));
            await visible(f);
            await tester.tap(f);
            await tester.pump();
            await settled();
          }

          Future<void> keyEnter(String key, String value) async {
            final f = find.byKey(ValueKey('opening-item-$key'));
            await visible(f);
            await tester.enterText(f, value);
            await tester.pump();
          }

          Future<void> originalChoice(String label, String filename) async {
            final state = await request(() => session!.read(openItemPath));
            final original = (state['originals'] as List).singleWhere(
              (o) => o['filename'] == filename,
            );
            await choose(
              label,
              '$filename · ${original['sha256'].substring(0, 12)}',
            );
          }

          Future<void> accept() async {
            await tap('Verbindliche Vorschau prüfen');
            await keyTap('accept');
            await tap('Unverändert verbindlich bestätigen');
          }

          await tap('Neue externe Altübernahme vorbereiten');
          await tap('Originaldatei unverändert hochladen');
          expect(session!.pendingOpenItemKeys.length, 1, reason: ui());
          await tap('Unveränderten Originalauftrag erneut senden');
          expect(api!.originals[0], api!.originals[1]);
          await tap('Zur Altpostenübersicht');
          await tap('Belegte Übernahme fortsetzen');
          await tap('Originaldatei unverändert hochladen');
          await choose('Rechnungsrichtung', 'Offene Kundenforderung');
          for (final e in {
            'external_system': 'Synthetic legacy source',
            'external_id': 'native-invoice-1',
            'counterparty_key': 'native-customer-1',
            'counterparty_name': 'Synthetic old customer',
            'invoice_number': 'SYN-OLD-1',
            'invoice_date': '2025-11-10',
            'service_date': '2025-11-10',
            'invoice_received_date': '2025-11-11',
            'net': '100',
            'tax': '19',
            'gross': '119',
            'history_through': '2025-12-31',
            'reason': 'Synthetic complete original opening reviewed',
          }.entries)
            await keyEnter(e.key, e.value);
          await choose('Belegter einzelner Steuersatz', '19 %');
          await choose('Gewöhnliche Erlös-/Aufwandsart', 'Erlös');
          await originalChoice(
            'Ursprüngliches Rechnungsoriginal',
            'invoice.pdf',
          );
          await originalChoice(
            'Vollständige Stichtagsaufstellung',
            'cutover.pdf',
          );
          await tap('Belegte alte Teilzahlung ergänzen');
          for (final e in {
            'date': '2025-12-20',
            'reference': 'Synthetic original old part',
            'net': '33.34',
            'tax': '6.33',
            'gross': '39.67',
          }.entries)
            await keyEnter('prior-0-${e.key}', e.value);
          await originalChoice('Original dieser alten Zahlung', 'cutover.pdf');
          await keyTap('history-confirmed');
          await keyTap('scope-confirmed');
          await accept();
          expect(session!.pendingOpenItemKeys.length, 1, reason: ui());
          await tap('Unveränderten Originalauftrag erneut senden');
          expect(api!.confirms[0], api!.confirms[1]);
          expect(session!.pendingOpenItemKeys, isEmpty);
          var state = openItemState(
            await request(() => session!.read(openItemPath)),
          );
          final itemKey = state['items'][0]['entity_key'];
          expect(RegExp(r'^[a-f0-9]{32}$').hasMatch(itemKey), true);
          expect(state['items'][0]['remaining'], '79.33');
          expect(state['payments'], isEmpty);
          await tap('invoice.pdf');
          await settled(() => saved.length == 1);
          expect(
            saved.single.bytes,
            await tester.runAsync(() => files.first.readAsBytes()),
          );
          Future<void> payment(
            String amount,
            String filename,
            String date,
          ) async {
            await tap('Originaldatei unverändert hochladen');
            await tap('Tatsächliche Restzahlung erfassen');
            await keyEnter('date', date);
            await keyEnter('amount', amount);
            await choose(
              'Tatsächliches Geldkonto',
              'OPEN · Synthetic opening bank',
            );
            await keyEnter('evidence_reference', 'Synthetic $filename');
            await originalChoice(
              'Eigenes Original der neuen Restzahlung',
              filename,
            );
            await keyTap('payment-confirmed');
            await keyEnter('reason', 'Synthetic actual cash evidence checked');
            await accept();
          }

          await payment('39.67', 'payment-one.pdf', '2026-02-15');
          await payment('39.66', 'payment-two.pdf', '2026-02-16');
          state = openItemState(
            await request(() => session!.read(openItemPath)),
          );
          expect(state['items'][0]['remaining'], '0.00');
          expect(state['payments'].map((p) => p['details']['tax']).toList(), [
            '6.34',
            '6.33',
          ]);
          await tap('Übernahmehistorie');
          await visible(find.text('Unveränderliche Originalhistorie'));
          final liquidity = await request(
            () => session!.read(
              '/accounting/opening-balances/liquidity?as_of=2026-02-28',
            ),
          );
          expect(jsonEncode(liquidity), contains('opening_item_cash'));
          expect(liquidity['accounts'][0]['balance'], '1079.33');
          expect(liquidity['accounts'][0]['inflows'], '79.33');
          await tap('Zahlungsquelle und EÜR-Zuordnung');
          await tap('EÜR-Quelle einordnen oder gegenbuchen');
          expect(find.byType(AlertDialog), findsOneWidget, reason: ui());
          for (final e in {
            'Geprüftes SKR04-Nettoerlös-/Aufwandskonto': '4400',
            'Geprüftes SKR04-Konto für vereinnahmte/gezahlte Steuer': '3806',
            'Fachliche Begründung':
                'Synthetic reviewed original remaining payment',
            'Nachweis / Prüfgrundlage':
                'Synthetic original preserved source and SKR04',
          }.entries)
            await enter(e.key, e.value);
          await tap('Buchung unverbindlich prüfen');
          await tap(
            'Ich habe Quelle, fachliche Einordnung, Beträge, Zeitraum und Konten geprüft und bestätige diesen Vorgang.',
          );
          await tap('Buchung verbindlich festhalten');
          expect(session!.pending('accounting-euer'), true, reason: ui());
          await tap('Ursprünglichen Auftrag erneut senden');
          expect(api!.euerConfirms[0], api!.euerConfirms[1]);
          final report = await request(
            () => session!.read('/accounting/euer/report?year=2026'),
          );
          expect(jsonEncode(report), contains('opening_item_cash'));

          await tap('Buchungen und Korrekturen');
          await tap('Geprüft berichtigen');
          await enter('Geprüftes SKR04-Nettoerlös-/Aufwandskonto', '4401');
          await enter(
            'Fachliche Begründung',
            'Synthetic corrected classification account',
          );
          await enter(
            'Nachweis / Prüfgrundlage',
            'Synthetic preserved original source',
          );
          await tap('Buchung unverbindlich prüfen');
          await tap(
            'Ich habe Quelle, fachliche Einordnung, Beträge, Zeitraum und Konten geprüft und bestätige diesen Vorgang.',
          );
          await tap('Buchung verbindlich festhalten');
          final corrected = await request(
            () => session!.read('/accounting/euer/journal?offset=0&limit=100'),
          );
          final correction = (corrected['items'] as List).singleWhere(
            (v) => v['operation'] == 'correct',
          );
          expect(correction['postings'].length, 6);
          openItemEuerEffect(correction['effect']);
          expect(correction['effect']['payload']['net_account'], '4401');
          await tap('Genau gegenbuchen');
          await enter(
            'Fachliche Begründung',
            'Synthetic original EÜR classification reversed',
          );
          await enter(
            'Nachweis / Prüfgrundlage',
            'Synthetic original reversal review',
          );
          await tap('Buchung unverbindlich prüfen');
          await tap(
            'Ich habe Quelle, fachliche Einordnung, Beträge, Zeitraum und Konten geprüft und bestätige diesen Vorgang.',
          );
          await tap('Buchung verbindlich festhalten');
          final reversed = await request(
            () => session!.read('/accounting/euer/journal?offset=0&limit=100'),
          );
          expect(
            (reversed['items'] as List)
                .where((v) => v['operation'] == 'reverse')
                .length,
            1,
          );
          await tester.pageBack();
          await settled();
          // Pick the last payment by its card, preserving the earlier immutable payment.
          Future<void> lastPaymentAction(String label) async {
            final f = find.text(label);
            await visible(f);
            await tester.ensureVisible(f.last);
            await settled();
            await tester.tap(f.last);
            await tester.pump();
            await settled();
          }

          await lastPaymentAction('Fehlerhafte Zahlung berichtigen');
          await keyEnter('amount', '39.65');
          await keyTap('payment-confirmed');
          await keyEnter('reason', 'Synthetic one cent clerical correction');
          await accept();
          state = openItemState(
            await request(() => session!.read(openItemPath)),
          );
          expect(state['items'][0]['remaining'], '0.01');
          await lastPaymentAction('Fehlerhaften Zahlungsnachweis aufheben');
          await keyTap('void-confirmed');
          await keyEnter(
            'reason',
            'Synthetic wrong capture withdrawn without refund',
          );
          await accept();
          state = openItemState(
            await request(() => session!.read(openItemPath)),
          );
          expect(state['items'][0]['remaining'], '39.66');
          expect(state['payments'].last['payload']['status'], 'void');
          await lastPaymentAction('Zahlungshistorie');
          await visible(find.text('Unveränderliche Originalhistorie'));
          expect(find.textContaining('Fassung 3'), findsOneWidget);
          final history = await request(
            () => session!.read(openItemHistoryPath(itemKey)),
          );
          expect(history['items'].length, 1);

          await tap('Zur Altpostenübersicht');
          await tap('Neue externe Altübernahme vorbereiten');
          for (var i = 0; i < 3; i++)
            await tap('Originaldatei unverändert hochladen');
          await choose(
            'Rechnungsrichtung',
            'Offene Lieferantenverbindlichkeit',
          );
          for (final e in {
            'external_system': 'Synthetic legacy source',
            'external_id': 'native-payable-1',
            'counterparty_key': 'native-supplier-1',
            'counterparty_name': 'Synthetic old supplier',
            'invoice_number': 'SYN-OLD-PAY-1',
            'invoice_date': '2025-11-10',
            'service_date': '2025-11-10',
            'invoice_received_date': '2025-11-11',
            'net': '100',
            'tax': '19',
            'gross': '119',
            'history_through': '2025-12-31',
            'vat_amount': '19',
            'vat_entitlement_date': '2025-11-11',
            'vat_declared_period': '2025-11',
            'vat_deducted_on': '2025-12-10',
            'reason':
                'Synthetic full old input VAT exercised before software start',
          }.entries)
            await keyEnter(e.key, e.value);
          await choose('Belegter einzelner Steuersatz', '19 %');
          await choose('Gewöhnliche Erlös-/Aufwandsart', 'Material');
          await originalChoice(
            'Ursprüngliches Rechnungsoriginal',
            'payable-invoice.pdf',
          );
          await originalChoice(
            'Vollständige Stichtagsaufstellung',
            'payable-cutover.pdf',
          );
          await originalChoice(
            'Originalnachweis des früheren Vorsteuerabzugs',
            'payable-old-vat.pdf',
          );
          await keyTap('history-confirmed');
          await keyTap('scope-confirmed');
          await accept();
          await payment('119', 'payable-payment.pdf', '2026-02-17');
          await tap('Zahlungsquelle und EÜR-Zuordnung');
          await visible(find.textContaining('neuer Vorsteuerabzug: 0,00'));
          await tap('EÜR-Quelle einordnen oder gegenbuchen');
          for (final e in {
            'Geprüftes SKR04-Nettoerlös-/Aufwandskonto': '5400',
            'Geprüftes SKR04-Konto für vereinnahmte/gezahlte Steuer': '1406',
            'Fachliche Begründung':
                'Synthetic original input VAT already deducted',
            'Nachweis / Prüfgrundlage':
                'Synthetic old VAT ledger and actual outgoing cash',
          }.entries)
            await enter(e.key, e.value);
          await tap('Buchung unverbindlich prüfen');
          await tap(
            'Ich habe Quelle, fachliche Einordnung, Beträge, Zeitraum und Konten geprüft und bestätige diesen Vorgang.',
          );
          await tap('Buchung verbindlich festhalten');
          final euerJournal = await request(
            () => session!.read('/accounting/euer/journal?offset=0&limit=100'),
          );
          final payableEntry = (euerJournal['items'] as List).firstWhere(
            (v) => v['effect']?['source']?['direction'] == 'out',
          );
          openItemEuerEffect(payableEntry['effect']);
          expect(payableEntry['postings'].length, 2);
          expect(
            payableEntry['effect']['details']['prior_input_vat_preserved'],
            true,
          );
          expect(
            payableEntry['effect']['source']['prior_input_vat']['deducted_on'],
            '2025-12-10',
          );
          await tester.pageBack();
          await settled();

          // A later, unchanged item acceptance must not replace the payment's
          // immutable original item reference with today's head.
          final beforeRecheck = openItemState(
            await request(() => session!.read(openItemPath)),
          );
          final payableBefore = (beforeRecheck['items'] as List).singleWhere(
            (v) => v['payload']['direction'] == 'payable',
          );
          await tap('Übernahme berichtigen / Profil erneut prüfen');
          await keyTap('history-confirmed');
          await keyTap('scope-confirmed');
          await keyEnter(
            'reason',
            'Synthetic unchanged original revalidated without rewriting old payment',
          );
          await accept();
          final afterRecheck = openItemState(
            await request(() => session!.read(openItemPath)),
          );
          final payableAfter = (afterRecheck['items'] as List).singleWhere(
            (v) => v['payload']['direction'] == 'payable',
          );
          expect(payableAfter['id'], isNot(payableBefore['id']));
          final preservedPayment = (afterRecheck['payments'] as List)
              .singleWhere(
                (v) => v['payload']['item_key'] == payableAfter['entity_key'],
              );
          expect(preservedPayment['payload']['item_id'], payableBefore['id']);
          await tap('Zahlungsquelle und EÜR-Zuordnung');
          await visible(find.textContaining('neuer Vorsteuerabzug: 0,00'));
          await tap('Anfangsbestände und Liquidität');
          await tester.pageBack();
          await settled();
          await tap('Bankabgleich');
          await tester.pageBack();
          await settled();
          await request(
            () => admin!.call('/api/business/settings/permissions', {
              'request_id': 'd' * 32,
              'user_id': setup['user_id'],
              'permission': 'finance.read',
              'scope': '*',
              'effect': 'deny',
              'revision': 1,
            }),
          );
          await request(() => session!.load());
          await settled();
          expect(find.textContaining('Synthetic old customer'), findsNothing);
          expect(find.text('invoice.pdf'), findsNothing);
          expect(find.textContaining('nicht freigegeben'), findsOneWidget);
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

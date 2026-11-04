@Tags(['posix_backend'])
library;

import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:smartplan_office/business_accounting.dart';
import 'package:smartplan_office/business_accounting_profile.dart';
import 'package:smartplan_office/business_session.dart';
import 'package:smartplan_office/design.dart';

import 'backend_integration_test.dart' show BackendHttp;
import 'business_accounting_allocations_http_test.dart' show seedInvoice;
import 'business_accounting_refunds_v2_http_widget_test.dart'
    show RefundJourneyConnection;
import 'import_backend_integration_test.dart' show fixture;

void main() {
  testWidgets(
    'real profile widgets store explicit unknown facts and replay the original across new version and admin withdrawal',
    (tester) async {
      final backend = Directory('../backend').absolute;
      final python =
          Platform.environment['SMARTPLAN_TEST_PYTHON'] ??
          '${backend.path}/.venv/bin/python';
      Directory? directory;
      Process? server;
      StreamIterator<String>? output;
      StreamSubscription<String>? errors;
      final diagnostics = StringBuffer(),
          sessions = <BusinessSession>[],
          connections = <RefundJourneyConnection>[];
      await tester.binding.setSurfaceSize(const Size(1200, 1000));
      try {
        final setup = await tester.runAsync(() async {
          directory = await Directory.systemTemp.createTemp(
            'synthetic-profile-ui-',
          );
          // Only an old synthetic invoice is seeded. No profile is seeded.
          final seed = fixture
              .replaceFirst(
                'app = create_app(',
                '$seedInvoice\napp = create_app(',
              )
              .replaceFirst(
                'project_id=project)',
                "project_id=project, invoice_id=invoice['id'], worker_id=worker_id, worker_token=worker_token)",
              );
          server = await Process.start(python, [
            '-u',
            '-c',
            seed,
            directory!.path,
          ], workingDirectory: backend.path);
          errors = server!.stderr
              .transform(utf8.decoder)
              .listen(diagnostics.write);
          output = StreamIterator(
            server!.stdout
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
          Future<dynamic> transport(Future<dynamic> Function() task) async {
            var complete = false;
            dynamic result;
            Object? failure;
            StackTrace? trace;
            task().then(
              (value) {
                result = value;
                complete = true;
              },
              onError: (Object error, StackTrace stack) {
                failure = error;
                trace = stack;
                complete = true;
              },
            );
            for (var i = 0; i < 1000 && !complete; i++) {
              await tester.runAsync(
                () => Future<void>.delayed(const Duration(milliseconds: 10)),
              );
              await tester.pump(const Duration(milliseconds: 20));
            }
            expect(
              complete,
              true,
              reason: 'Real profile HTTP did not finish. $diagnostics',
            );
            if (failure != null) Error.throwWithStackTrace(failure!, trace!);
            return result;
          }

          Future<BusinessSession> connect(String token) async {
            final api = RefundJourneyConnection(
              'http://127.0.0.1:${setup!['port']}',
            )..token = token;
            connections.add(api);
            final session = BusinessSession(api: api);
            sessions.add(session);
            await transport(session.load);
            return session;
          }

          final owner = await connect(setup!['token']);
          final ownerApi = owner.api as RefundJourneyConnection;
          Future<Map<String, dynamic>> command(
            BusinessSession session,
            String key,
            String route,
            Map<String, dynamic> body,
          ) async => businessMap(
            await transport(() => session.command(key, route, body)),
          );
          Future<dynamic> read(BusinessSession session, String path) =>
              transport(() => session.read(path));
          Future<void> permission(
            String right,
            String effect,
            int revision,
          ) async {
            await command(
              owner,
              'permission-$right-$revision',
              '/settings/permissions',
              {
                'user_id': setup['worker_id'],
                'scope': '*',
                'permission': right,
                'effect': effect,
                'revision': revision,
              },
            );
          }

          await permission('accounting.read', 'allow', 0);
          await permission('accounting.admin', 'allow', 0);
          await permission('finance.write', 'deny', 0);
          await permission('accounting.prepare', 'deny', 0);
          final worker = await connect(setup['worker_token']);
          final workerApi = worker.api as RefundJourneyConnection;
          expect(worker.canWrite('accounting.admin'), true);
          expect(worker.canWrite('finance.write'), false);
          expect(worker.canWrite('accounting.prepare'), false);
          expect(worker.hasFeature('accounting_preparation_profile'), true);

          // Existing financial evidence is setup only, so the profile workflow can
          // prove it leaves an actual CashEvent and paid invoice unchanged.
          final account = await command(
            owner,
            'setup-account',
            '/accounting/accounts',
            {
              'code': 'SYNPROFILE',
              'name': 'Synthetisches Bestandskonto',
              'kind': 'bank',
              'confirmation': true,
            },
          );
          final payment = await command(
            owner,
            'setup-payment',
            '/finance/payments',
            {
              'source_id': 'synthetic-profile-existing-payment',
              'kind': 'receipt',
              'amount': '119.00',
              'currency': 'EUR',
              'booking_date': '2026-11-03',
              'reference': 'Synthetischer bestehender Geldfluss',
              'allocations': [
                {'document_id': setup['invoice_id'], 'amount': '119.00'},
              ],
            },
          );
          final source = businessItems(
            await read(owner, '/accounting/sources/payments'),
          ).singleWhere((value) => value['payment_id'] == payment['id']);
          final event = await command(
            owner,
            'setup-cash',
            '/accounting/events/import-payment',
            {
              'payment_id': payment['id'],
              'source_hash': source['source_hash'],
              'account_id': account['id'],
              'account_revision': 1,
              'cash_date': '2026-11-03',
              'evidence_reference': 'SYN-PROFILE-BESTAND',
              'confirmation': true,
            },
          );
          final oldStatus = await read(owner, '/accounting/status'),
              oldOpenItems = await read(owner, '/finance/open-items'),
              oldCash = await read(owner, '/accounting/events/${event['id']}');
          final initial = businessMap(
            await read(worker, '/accounting/profile'),
          );
          expect(initial['revision'], 0);
          expect(initial['current'], isNull);
          expect(initial['preparation_status'], 'unrecorded');
          expect(
            businessItems(await read(worker, '/accounting/profile/history')),
            isEmpty,
          );

          BusinessSession active = worker;
          Future<void> settle([bool Function()? ready]) async {
            for (var i = 0; i < 700; i++) {
              await tester.runAsync(
                () => Future<void>.delayed(const Duration(milliseconds: 10)),
              );
              await tester.pump(const Duration(milliseconds: 100));
              final exception = tester.takeException();
              if (exception != null) throw exception;
              if (!active.loading &&
                  find.byType(LinearProgressIndicator).evaluate().isEmpty &&
                  find.byType(CircularProgressIndicator).evaluate().isEmpty &&
                  (ready?.call() ?? true)) {
                await tester.runAsync(
                  () => Future<void>.delayed(const Duration(milliseconds: 10)),
                );
                await tester.pump(const Duration(milliseconds: 100));
                if (!active.loading &&
                    find.byType(LinearProgressIndicator).evaluate().isEmpty &&
                    (ready?.call() ?? true))
                  return;
              }
            }
            fail(
              'Profile widgets did not settle. ${active.error}\n${tester.widgetList<Text>(find.byType(Text)).map((w) => w.data).join('\n')}\n$diagnostics',
            );
          }

          Future<void> mount(
            BusinessSession session, {
            bool entry = false,
          }) async {
            active = session;
            await tester.pumpWidget(const SizedBox());
            await tester.pumpWidget(
              MaterialApp(
                theme: officeTheme(),
                home: entry
                    ? BusinessAccountingPage(session: session)
                    : BusinessPreparationProfilePage(session: session),
              ),
            );
            await settle();
          }

          Future<void> click(Finder finder, [bool Function()? ready]) async {
            expect(finder, findsOneWidget);
            await tester.ensureVisible(finder);
            await tester.pump(const Duration(milliseconds: 300));
            await settle();
            await tester.tap(finder);
            await settle(ready);
          }

          Future<void> fill(String name, String value) async {
            final finder = find.byKey(ValueKey('profile-$name'));
            await tester.ensureVisible(finder);
            await tester.pump(const Duration(milliseconds: 300));
            await settle();
            await tester.enterText(finder, value);
            await tester.pump();
          }

          Future<void> preview(String reason, String evidence) async {
            await click(find.text('Neuen Vorbereitungsstand erfassen'));
            await fill('reason', reason);
            await fill('evidence', evidence);
            await click(
              find.text('Vorbereitungsstand vorschauen'),
              () => find
                  .text('Vorbereitungsstand verbindlich speichern')
                  .evaluate()
                  .isNotEmpty,
            );
          }

          Future<void> confirm({bool lost = false}) async {
            await click(find.byKey(const ValueKey('profile-confirmation')));
            await click(
              find.text('Vorbereitungsstand verbindlich speichern'),
              () => lost
                  ? find.text('Unverändert erneut senden').evaluate().isNotEmpty
                  : find
                        .text('Vorbereitungsstand verbindlich speichern')
                        .evaluate()
                        .isEmpty,
            );
          }

          await mount(worker, entry: true);
          await click(find.text('Vorbereitungsprofil ansehen'));
          expect(
            find.text('Noch kein Vorbereitungsstand gespeichert'),
            findsOneWidget,
          );
          expect(workerApi.writes, isEmpty);
          await preview(
            '  Explizite Inhaberangabe ohne Umsatzsteuerantwort  ',
            '  SYN-INHABER-ERKLÄRUNG  ',
          );
          final firstPreview = workerApi.writes.last;
          expect(firstPreview.path, worker.path('/accounting/profile/preview'));
          expect(firstPreview.body['profile'], {
            'legal_form': 'sole_proprietorship',
            'accounting_method': 'euer',
            'vat_regime': null,
            'vat_timing': null,
            'vat_effective_from': null,
            'bookkeeping_start': null,
          });
          expect(
            firstPreview.body['reason'],
            '  Explizite Inhaberangabe ohne Umsatzsteuerantwort  ',
          );
          expect(
            businessMap(await read(worker, '/accounting/profile'))['revision'],
            0,
          );
          expect(
            businessItems(await read(worker, '/accounting/profile/history')),
            isEmpty,
          );
          workerApi.losePath = worker.path('/accounting/profile/confirm');
          await confirm(lost: true);
          final firstCommand = workerApi.writes.lastWhere(
            (w) => w.path.endsWith('/confirm'),
          );
          final firstEntry = businessMap(firstCommand.result);
          expect(firstEntry['revision'], 1);
          expect(firstEntry['tax_status'], 'unconfigured');
          expect(worker.pending('accounting-profile'), true);

          await mount(owner);
          await preview(
            'Zweite ausdrücklich bestätigte offene Angabe',
            'SYN-INHABER-2',
          );
          await confirm();
          final secondEntry = businessMap(
            ownerApi.writes
                .lastWhere(
                  (w) => w.path.endsWith('/accounting/profile/confirm'),
                )
                .result,
          );
          expect(secondEntry['revision'], 2);
          expect(secondEntry['profile']['vat_timing'], isNull);
          await permission('accounting.admin', 'deny', 1);
          await transport(worker.load);
          await mount(worker);
          expect(worker.pending('accounting-profile'), true);
          expect(find.text('Unbestätigter Vorbereitungsstand'), findsOneWidget);
          final retry = find.widgetWithText(
            FilledButton,
            'Unverändert erneut senden',
          );
          expect(tester.widget<FilledButton>(retry).onPressed, isNull);
          expect(find.byType(TextField), findsNothing);
          expect(
            workerApi.writes.where((w) => w.path.endsWith('/confirm')),
            hasLength(1),
          );
          await permission('accounting.admin', 'allow', 2);
          await transport(worker.load);
          await click(find.byTooltip('Vorbereitungsprofil aktualisieren'));
          expect(find.text('Vorbereitungsstand prüfen'), findsNothing);
          await click(
            find.text('Unverändert erneut senden'),
            () => !worker.pending('accounting-profile'),
          );
          final replay = workerApi.writes.lastWhere(
            (w) => w.path.endsWith('/confirm'),
          );
          expect(replay.path, firstCommand.path);
          expect(replay.body, firstCommand.body);
          expect(replay.result, firstEntry);
          final finalState = businessMap(
            await read(worker, '/accounting/profile'),
          );
          expect(finalState['revision'], 2);
          expect(finalState['preparation_status'], 'recorded');
          expect(finalState['current'], secondEntry);
          expect(finalState['tax_result_available'], false);
          expect(
            businessItems(await read(worker, '/accounting/profile/history')),
            [secondEntry, firstEntry],
          );
          expect(await read(owner, '/accounting/status'), oldStatus);
          expect(await read(owner, '/finance/open-items'), oldOpenItems);
          expect(
            await read(owner, '/accounting/events/${event['id']}'),
            oldCash,
          );
          expect(
            businessItems(await read(owner, '/accounting/events')),
            hasLength(1),
          );
        }, BackendHttp());
      } finally {
        await tester.pumpWidget(const SizedBox());
        for (final session in sessions) {
          session.dispose();
        }
        for (final api in connections) {
          api.dispose();
        }
        await tester.runAsync(() async {
          server?.kill();
          if (server != null)
            await server!.exitCode.timeout(const Duration(seconds: 10));
          await output?.cancel();
          await errors?.cancel();
          if (directory != null) await directory!.delete(recursive: true);
        });
        if (diagnostics.isNotEmpty)
          debugPrint('Synthetic profile backend diagnostics: $diagnostics');
        await tester.binding.setSurfaceSize(null);
      }
    },
    timeout: const Timeout(Duration(minutes: 3)),
  );
}

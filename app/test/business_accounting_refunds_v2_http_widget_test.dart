import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:smartplan_office/api.dart';
import 'package:smartplan_office/business_accounting.dart';
import 'package:smartplan_office/business_accounting_capacity.dart';
import 'package:smartplan_office/business_accounting_refunds_v2.dart';
import 'package:smartplan_office/business_session.dart';
import 'package:smartplan_office/design.dart';

import 'backend_integration_test.dart' show BackendHttp;
import 'business_accounting_allocations_http_test.dart' show seedInvoice;
import 'import_backend_integration_test.dart' show fixture;

/// Records actual transport; loss is injected only after the real server commits.
class RefundJourneyConnection extends OfficeApi {
  RefundJourneyConnection(String base) : super(baseUrl: base, apiVersion: 'v1');
  String? losePath;
  final writes = <({String path, Map<String, dynamic> body, dynamic result})>[];
  @override
  Future<dynamic> call(String path, [Map<String, dynamic>? body]) async {
    dynamic result;
    try {
      result = await super.call(path, body);
    } on ApiException catch (error) {
      throw ApiException(
        error.status,
        '$path: ${error.message}',
        requestResolution: error.requestResolution,
      );
    }
    if (body != null) {
      writes.add((
        path: path,
        body: jsonDecode(jsonEncode(body)),
        result: jsonDecode(jsonEncode(result)),
      ));
    }
    if (path == losePath) {
      losePath = null;
      throw const ApiException(
        0,
        'Synthetic lost acknowledgement after commit',
      );
    }
    return result;
  }
}

void main() {
  testWidgets(
    'real widgets and HTTP bind whole mixed refunds through two reuse cycles and replay the old writer',
    (tester) async {
      final backend = Directory('../backend').absolute;
      final python =
          Platform.environment['SMARTPLAN_TEST_PYTHON'] ??
          '${backend.path}/.venv/bin/python';
      Directory? temp;
      Process? server;
      StreamIterator<String>? output;
      StreamSubscription<String>? errors;
      BusinessSession? session;
      RefundJourneyConnection? connection;
      final diagnostics = StringBuffer();
      await tester.binding.setSurfaceSize(const Size(1200, 1000));
      try {
        final setup = await tester.runAsync(() async {
          temp = await Directory.systemTemp.createTemp('synthetic-refund-ui-');
          final seed = fixture
              .replaceFirst(
                'app = create_app(',
                '$seedInvoice\napp = create_app(',
              )
              .replaceFirst(
                'project_id=project)',
                "project_id=project, invoice_id=invoice['id'])",
              );
          server = await Process.start(python, [
            '-u',
            '-c',
            seed,
            temp!.path,
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
          final api = connection = RefundJourneyConnection(
            'http://127.0.0.1:${setup!['port']}',
          )..token = setup['token'];
          final business = session = BusinessSession(api: api);
          // Keep UI continuations moving while real sockets complete. A whole
          // awaited read in runAsync could strand a concurrently opened UI
          // request in fake time and block the serial fixture HTTP server.
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
              reason: 'Real HTTP did not complete. $diagnostics',
            );
            if (failure != null) Error.throwWithStackTrace(failure!, trace!);
            return result;
          }

          Future<dynamic> read(String path) =>
              transport(() => business.read(path));
          var request = 0;
          Future<Map<String, dynamic>> setupPost(
            String path,
            Map<String, dynamic> body,
          ) async => businessMap(
            await transport(
              () => api.call(business.path(path), {
                ...body,
                'request_id': (++request).toRadixString(16).padLeft(32, '0'),
              }),
            ),
          );
          await transport(business.load);
          expect(
            business.hasFeature('accounting_refund_origins_v2'),
            true,
            reason: business.error,
          );
          await setupPost('/accounting/accounts', {
            'code': 'SYNUI',
            'name': 'Synthetisches Testkonto',
            'kind': 'bank',
            'confirmation': true,
          });

          Future<void> settle([bool Function()? ready]) async {
            for (var i = 0; i < 500; i++) {
              await tester.runAsync(
                () => Future<void>.delayed(const Duration(milliseconds: 10)),
              );
              await tester.pump(const Duration(milliseconds: 100));
              final exception = tester.takeException();
              if (exception != null) throw exception;
              if (!business.loading &&
                  find.byType(LinearProgressIndicator).evaluate().isEmpty &&
                  find.byType(CircularProgressIndicator).evaluate().isEmpty &&
                  (ready?.call() ?? true)) {
                // Drain callbacks whose first HTTP operation starts at this frame.
                await tester.runAsync(
                  () => Future<void>.delayed(const Duration(milliseconds: 10)),
                );
                await tester.pump(const Duration(milliseconds: 100));
                if (!business.loading &&
                    find.byType(LinearProgressIndicator).evaluate().isEmpty &&
                    find.byType(CircularProgressIndicator).evaluate().isEmpty &&
                    (ready?.call() ?? true))
                  return;
              }
            }
            final shown = tester
                .widgetList<Text>(find.byType(Text))
                .map((t) => t.data)
                .whereType<String>()
                .join('\n');
            fail(
              'HTTP widget flow did not settle. ${business.error}\n$shown\n$diagnostics',
            );
          }

          Future<void> mount(Widget page) async {
            await tester.pumpWidget(const SizedBox());
            await tester.pumpWidget(
              MaterialApp(theme: officeTheme(), home: page),
            );
            await settle();
          }

          Future<void> click(Finder finder, [bool Function()? ready]) async {
            expect(finder, findsOneWidget);
            await tester.ensureVisible(finder);
            await tester.pump(const Duration(milliseconds: 300));
            // The animation pump may start the periodic metadata request.
            // Wait for those current rights before a deliberate user action.
            await settle();
            await tester.tap(finder);
            await settle(ready);
          }

          Future<void> fill(Finder finder, String value) async {
            expect(finder, findsOneWidget);
            await tester.ensureVisible(finder);
            await tester.pump(const Duration(milliseconds: 300));
            await tester.enterText(finder, value);
            await tester.pump();
          }

          Finder field(String name) =>
              find.byKey(ValueKey('business-field-$name'));
          final cashSnapshots = <String, Map<String, dynamic>>{};
          final opSnapshots = <String, dynamic>{};
          Future<void> unchanged(String eventId) async {
            expect(await read('/finance/open-items'), opSnapshots[eventId]);
            for (final entry in cashSnapshots.entries) {
              expect(
                await read('/accounting/events/${entry.key}'),
                entry.value,
                reason:
                    'Documentary UI must not rewrite original cash evidence',
              );
            }
          }

          Future<Map<String, dynamic>> flow(
            String label,
            String amount,
            String kind,
          ) async {
            // Only the confirmed Finance source is test setup, created at its cycle.
            // Import and every following documentary action use real widgets.
            final payment = await setupPost('/finance/payments', {
              'source_id': 'synthetic-ui-$label',
              'kind': kind,
              'amount': amount,
              'currency': 'EUR',
              'booking_date': '2026-11-03',
              'reference': 'SYN-UI-$label',
              'allocations': [
                {'document_id': setup['invoice_id'], 'amount': amount},
              ],
            });
            final op = await read('/finance/open-items');
            await mount(BusinessAccountingPage(session: business));
            await click(find.text('Kundenzahlungen'));
            final card = find.ancestor(
              of: find.textContaining('SYN-UI-$label'),
              matching: find.byType(Card),
            );
            await click(
              find.descendant(
                of: card,
                matching: find.text('Zahlung übernehmen'),
              ),
            );
            await click(find.byType(DropdownButtonFormField<String>));
            await click(find.textContaining('Synthetisches Testkonto').last);
            await fill(field('cash_date'), '03.11.2026');
            await fill(field('evidence_reference'), 'SYN-UI-NACHWEIS-$label');
            await click(find.byType(SwitchListTile));
            await click(
              find.text('Einmalig ins Vorjournal übernehmen'),
              () =>
                  api.writes.any(
                    (w) =>
                        w.path.endsWith('/import-payment') &&
                        w.body['payment_id'] == payment['id'],
                  ) &&
                  find
                      .text('Einmalig ins Vorjournal übernehmen')
                      .evaluate()
                      .isEmpty,
            );
            final source = businessItems(
              await read('/accounting/sources/payments'),
            ).singleWhere((v) => v['payment_id'] == payment['id']);
            final id = source['linked_event_id'] as String;
            final event = businessMap(await read('/accounting/events/$id'));
            cashSnapshots[id] = event;
            opSnapshots[id] = op;
            await unchanged(id);
            return event;
          }

          Future<Map<String, dynamic>> split(
            Map<String, dynamic> event,
            String amount, {
            required bool reused,
          }) async {
            final id = event['id'] as String;
            final before = api.writes.length;
            await mount(
              BusinessReusableComponentsPage(session: business, eventId: id),
            );
            await click(find.text('Diesen Beleganteil aufteilen'));
            final group = find.byWidgetPredicate(
              (w) => w is TextField && '${w.key}'.contains('capacity-group-'),
            );
            await fill(group, amount);
            await fill(
              find.byKey(const ValueKey('capacity-reason')),
              'Synthetischer UI-Nachweis $amount',
            );
            await click(
              find.text('Belegaufteilung vorschauen'),
              () => find
                  .text('Belegaufteilung verbindlich bestätigen')
                  .evaluate()
                  .isNotEmpty,
            );
            if (find
                .byKey(const ValueKey('capacity-accept'))
                .evaluate()
                .isNotEmpty) {
              await click(find.byKey(const ValueKey('capacity-accept')));
            }
            expect(
              find.text(
                'Für die hier neu aufgeteilten Zahlungsanteile ist die Zuordnung späterer Erstattungen noch nicht verfügbar.',
              ),
              findsNothing,
            );
            await click(
              find.text('Belegaufteilung verbindlich bestätigen'),
              () => find
                  .text('Belegaufteilung verbindlich bestätigen')
                  .evaluate()
                  .isEmpty,
            );
            final recorded = api.writes
                .skip(before)
                .singleWhere((v) => v.path.endsWith('/confirm'));
            expect(
              recorded.path,
              business.path(
                '/accounting/components/${reused ? 'v2/' : ''}events/$id/confirm',
              ),
            );
            await unchanged(id);
            return businessMap(recorded.result);
          }

          Future<Map<String, dynamic>> refund(
            Map<String, dynamic> event,
            List<({String version, Map<String, dynamic> entry, String amount})>
            chosen, {
            required bool versioned,
            bool lose = false,
          }) async {
            final id = event['id'] as String;
            final before = api.writes.length;
            await mount(
              BusinessVersionedRefundOriginsPage(
                session: business,
                eventId: id,
              ),
            );
            await click(find.text('Ursprünge für diesen Anteil wählen'));
            for (final origin in chosen) {
              final line = businessItems(origin.entry['lines']).single;
              await fill(
                find.byKey(
                  ValueKey(
                    'refund-v2-origin-${origin.version}:${origin.entry['id']}:${line['group_id']}',
                  ),
                ),
                origin.amount,
              );
            }
            await fill(
              find.byKey(const ValueKey('refund-v2-reason')),
              'Synthetische ganze Erstattung $id',
            );
            await click(
              find.text('Erstattungsursprung vorschauen'),
              () => find
                  .text('Erstattungsursprung verbindlich bestätigen')
                  .evaluate()
                  .isNotEmpty,
            );
            if (find
                .byKey(const ValueKey('refund-v2-handoff'))
                .evaluate()
                .isNotEmpty) {
              await click(find.byKey(const ValueKey('refund-v2-handoff')));
            }
            final path = business.path(
              '/accounting/refunds/${versioned ? 'v2/' : ''}events/$id/confirm',
            );
            if (lose) api.losePath = path;
            await click(
              find.text('Erstattungsursprung verbindlich bestätigen'),
              () => lose
                  ? find.text('Unverändert erneut senden').evaluate().isNotEmpty
                  : find
                        .text('Erstattungsursprung verbindlich bestätigen')
                        .evaluate()
                        .isEmpty,
            );
            final recorded = api.writes
                .skip(before)
                .singleWhere((v) => v.path.endsWith('/confirm'));
            expect(recorded.path, path);
            if (!versioned) {
              expect(recorded.body.containsKey('action'), false);
              expect(
                businessItems(recorded.body['origins']).single
                    .containsKey('origin_version'),
                false,
              );
            }
            await unchanged(id);
            return businessMap(recorded.result);
          }

          final originals = <Map<String, dynamic>>[],
              initial = <Map<String, dynamic>>[];
          for (var i = 0; i < 3; i++) {
            final amount = i == 2 ? '39.66' : '39.67';
            final event = await flow('initial-$i', amount, 'receipt');
            originals.add(event);
            initial.add(await split(event, amount, reused: false));
          }
          expect(initial.map((v) => v['net']), ['33.34', '33.33', '33.33']);
          expect(initial.map((v) => v['tax']), ['6.33', '6.34', '6.33']);
          final oldRefund = await flow('first-return', '13.22', 'refund');
          final r1 = await refund(
            oldRefund,
            [(version: 'c1', entry: initial[1], amount: '13.22')],
            versioned: false,
            lose: true,
          );
          expect([r1['net'], r1['tax']], ['11.11', '2.11']);
          final oldRequest = api.writes.lastWhere(
            (w) => w.path.endsWith('/confirm'),
          );
          final legacyHistory = await read(
            '/accounting/refunds/events/${oldRefund['id']}/history',
          );
          var positive = await flow('reuse-a', '13.22', 'receipt');
          var reused = await split(positive, '13.22', reused: true);
          expect([reused['net'], reused['tax']], ['11.11', '2.11']);
          final cycleEntries = <Map<String, dynamic>>[];
          for (var cycle = 0; cycle < 2; cycle++) {
            final amount = cycle == 0 ? '26.44' : '39.67';
            final event = await flow('mixed-return-$cycle', amount, 'refund');
            final result = await refund(
              event,
              [
                (
                  version: 'c1',
                  entry: initial[1],
                  amount: cycle == 0 ? '13.22' : '13.23',
                ),
                (
                  version: 'c2',
                  entry: reused,
                  amount: cycle == 0 ? '13.22' : '26.44',
                ),
              ],
              versioned: true,
              lose: cycle == 0,
            );
            cycleEntries.add(result);
            final lines = businessItems(result['lines']);
            final c1 = lines.singleWhere(
              (line) => line['origin_version'] == 'c1',
            );
            expect([
              c1['net'],
              c1['tax'],
            ], cycle == 0 ? ['11.10', '2.12'] : ['11.12', '2.11']);
            expect([
              result['net'],
              result['tax'],
            ], cycle == 0 ? ['22.21', '4.23'] : ['33.33', '6.34']);
            if (cycle == 0) {
              final accepted = api.writes.lastWhere(
                (w) => w.path.endsWith('/confirm'),
              );
              await click(
                find.text('Unverändert erneut senden'),
                () => !business.pending('accounting-refunds-${event['id']}'),
              );
              final replay = api.writes.lastWhere(
                (w) => w.path.endsWith('/confirm'),
              );
              expect(replay.path, accepted.path);
              expect(replay.body, accepted.body);
              expect(replay.result, accepted.result);
            }
            positive = await flow('reuse-${cycle + 1}', amount, 'receipt');
            reused = await split(positive, amount, reused: true);
            expect([
              reused['net'],
              reused['tax'],
            ], cycle == 0 ? ['22.21', '4.23'] : ['33.33', '6.34']);
          }
          // The older accepted R1 command survives both writer changes and lot exhaustion.
          await mount(
            BusinessVersionedRefundOriginsPage(
              session: business,
              eventId: oldRefund['id'],
            ),
          );
          expect(find.byKey(const ValueKey('refund-v2-handoff')), findsNothing);
          await click(
            find.text('Unverändert erneut senden'),
            () => !business.pending('accounting-refunds-${oldRefund['id']}'),
          );
          final replay = api.writes.lastWhere(
            (w) => w.path.endsWith('/confirm'),
          );
          expect(replay.path, oldRequest.path);
          expect(replay.body, oldRequest.body);
          expect(replay.result, oldRequest.result);
          expect(
            await read('/accounting/refunds/events/${oldRefund['id']}/history'),
            legacyHistory,
          );
          expect(
            businessItems(
              await read(
                '/accounting/refunds/v2/events/${oldRefund['id']}/history',
              ),
            ),
            isEmpty,
          );
          for (var i = 0; i < originals.length; i++) {
            expect(
              businessItems(
                await read(
                  '/accounting/components/events/${originals[i]['id']}/history',
                ),
              ).single,
              initial[i],
            );
          }
          expect(cycleEntries.length, 2);
          await unchanged(positive['id']);
          final documentary = api.writes
              .where(
                (w) =>
                    w.path.endsWith('/confirm') ||
                    w.path.endsWith('/import-payment'),
              )
              .toList();
          expect(
            documentary.where((w) => w.path.endsWith('/import-payment')).length,
            9,
          );
          expect(
            documentary
                .where(
                  (w) =>
                      w.path.contains('/refunds/v2/') &&
                      w.path.endsWith('/confirm'),
                )
                .length,
            3,
          );
          expect(
            documentary
                .where(
                  (w) =>
                      w.path.contains('/components/v2/') &&
                      w.path.endsWith('/confirm'),
                )
                .length,
            3,
          );
        }, BackendHttp());
      } finally {
        await tester.pumpWidget(const SizedBox());
        session?.dispose();
        connection?.dispose();
        await tester.runAsync(() async {
          server?.kill();
          if (server != null)
            await server!.exitCode.timeout(const Duration(seconds: 10));
          await output?.cancel();
          await errors?.cancel();
          if (temp != null) await temp!.delete(recursive: true);
        });
        if (diagnostics.isNotEmpty)
          debugPrint('Synthetic backend diagnostics: $diagnostics');
        await tester.binding.setSurfaceSize(null);
      }
    },
    timeout: const Timeout(Duration(minutes: 4)),
  );
}

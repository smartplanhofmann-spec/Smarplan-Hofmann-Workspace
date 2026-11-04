import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:smartplan_office/api.dart';
import 'package:smartplan_office/business_session.dart';

import 'backend_integration_test.dart' show BackendHttp;
import 'import_backend_integration_test.dart' show fixture;
import 'business_accounting_allocations_http_test.dart' show seedInvoice;

// Only the existing invoice archive uses the explicit synthetic SQLite issuer.
// These are real client/Flask/domain requests, not production issuance evidence.
class RefundConnection extends OfficeApi {
  RefundConnection(String base) : super(baseUrl: base, apiVersion: 'v1');
  bool lose = false;
  final confirms = <Map<String, dynamic>>[];
  @override
  Future<dynamic> call(String path, [Map<String, dynamic>? body]) async {
    final confirmation =
        body != null &&
        path.contains('/accounting/refunds/') &&
        path.endsWith('/confirm');
    if (confirmation)
      confirms.add(jsonDecode(jsonEncode(body)) as Map<String, dynamic>);
    dynamic result;
    try {
      result = await super.call(path, body);
    } on ApiException catch (e) {
      throw ApiException(e.status, '$path: ${e.message}');
    }
    if (confirmation && lose) {
      lose = false;
      throw const ApiException(0, 'Synthetic lost refund response');
    }
    return result;
  }
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  test('Real HTTP refund origins preserve cash, OP and C1 capacity, exact lot cents and replay after exhaustion', () async {
    final backend = Directory('../backend').absolute;
    final python =
        Platform.environment['SMARTPLAN_TEST_PYTHON'] ??
        '${backend.path}/.venv/bin/python';
    final temp = await Directory.systemTemp.createTemp(
      'synthetic-refund-flutter-',
    );
    Process? server;
    StreamIterator<String>? output;
    StreamSubscription<String>? errors;
    final diagnostics = StringBuffer(),
        apis = <RefundConnection>[],
        sessions = <BusinessSession>[];
    try {
      final seed = fixture
          .replaceFirst('app = create_app(', '$seedInvoice\napp = create_app(')
          .replaceFirst(
            'project_id=project)',
            "project_id=project, worker_id=worker_id, worker_token=worker_token, invoice_id=invoice['id'])",
          );
      server = await Process.start(python, [
        '-u',
        '-c',
        seed,
        temp.path,
      ], workingDirectory: backend.path);
      errors = server.stderr.transform(utf8.decoder).listen(diagnostics.write);
      output = StreamIterator(
        server.stdout.transform(utf8.decoder).transform(const LineSplitter()),
      );
      expect(
        await output.moveNext().timeout(const Duration(seconds: 30)),
        true,
        reason: '$diagnostics',
      );
      final setup = jsonDecode(output.current) as Map<String, dynamic>;
      await HttpOverrides.runWithHttpOverrides(() async {
        Future<BusinessSession> connect(String token) async {
          final api = RefundConnection('http://127.0.0.1:${setup['port']}')
            ..token = token;
          final session = BusinessSession(api: api);
          apis.add(api);
          sessions.add(session);
          await session.load();
          return session;
        }

        final owner = await connect(setup['token']),
            worker = await connect(setup['worker_token']);
        expect(
          owner.hasFeature('accounting_refund_origins'),
          true,
          reason: owner.error,
        );
        for (final right in ['accounting.read', 'accounting.prepare']) {
          await owner.command('grant-$right', '/settings/permissions', {
            'user_id': setup['worker_id'],
            'scope': '*',
            'permission': right,
            'effect': 'allow',
            'revision': 0,
          });
        }
        await worker.load();
        final account = businessMap(
          await owner.command('account', '/accounting/accounts', {
            'code': 'REFUND',
            'name': 'Synthetic evidence account',
            'kind': 'bank',
            'confirmation': true,
          }),
        );
        Future<Map<String, dynamic>> flow(
          String key,
          String amount,
          String kind,
        ) async {
          final payment = businessMap(
            await worker.command('payment-$key', '/finance/payments', {
              'source_id': 'synthetic-refund-$key',
              'kind': kind,
              'amount': amount,
              'currency': 'EUR',
              'booking_date': '2026-11-02',
              'reference': 'Synthetic already confirmed $kind $key',
              'allocations': [
                {'document_id': setup['invoice_id'], 'amount': amount},
              ],
            }),
          );
          final source = businessItems(
            await worker.read('/accounting/sources/payments'),
          ).singleWhere((s) => s['payment_id'] == payment['id']);
          return businessMap(
            await worker.command(
              'import-$key',
              '/accounting/events/import-payment',
              {
                'payment_id': payment['id'],
                'source_hash': source['source_hash'],
                'account_id': account['id'],
                'account_revision': 1,
                'cash_date': '2026-11-02',
                'evidence_reference': 'SYN-$key',
                'confirmation': true,
              },
            ),
          );
        }

        final incoming = <Map<String, dynamic>>[],
            components = <Map<String, dynamic>>[],
            refunds = <Map<String, dynamic>>[];
        for (var i = 0; i < 3; i++) {
          final event = await flow(
            'IN-$i',
            i == 2 ? '39.66' : '39.67',
            'receipt',
          );
          incoming.add(event);
          final prefix = '/accounting/components/events/${event['id']}';
          final state = businessMap(await worker.read(prefix)),
              portion = businessItems(await worker.read('$prefix/portions'))
                  .single;
          final body = {
            'source_hash': state['source_hash'],
            'expected_revision': state['revision'],
            'state_hash': state['state_hash'],
            'portion_id': portion['portion_id'],
            'portion_state_hash': portion['portion_state_hash'],
            'groups': [
              {
                'group_id': businessItems(portion['groups']).single['group_id'],
                'amount': portion['amount'],
              },
            ],
            'reason': 'Synthetic positive original receipt component',
          };
          final preview = businessMap(
            await worker.previewDocumentComponents(event['id'], body),
          );
          components.add(
            businessMap(
              await worker.command('component-$i', '$prefix/confirm', {
                ...body,
                'preview_hash': preview['preview_hash'],
                'confirmation': true,
              }),
            ),
          );
        }
        expect(components.map((e) => e['net']), ['33.34', '33.33', '33.33']);
        expect(components.map((e) => e['tax']), ['6.33', '6.34', '6.33']);
        for (var i = 0; i < 3; i++)
          refunds.add(
            await flow('OUT-$i', i == 2 ? '26.46' : '26.44', 'refund'),
          );
        // An inactive evidence account does not invalidate existing cash events.
        await owner.command(
          'inactive',
          '/accounting/accounts/${account['id']}',
          {
            'revision': 1,
            'name': 'Synthetic inactive evidence account',
            'active': false,
            'confirmation': true,
          },
        );
        final beforeOpen = await worker.read('/finance/open-items');
        final beforeComponents = <dynamic>[];
        for (final e in incoming)
          beforeComponents.add(
            await worker.read(
              '/accounting/components/events/${e['id']}/history',
            ),
          );
        final api = worker.api as RefundConnection,
            results = <Map<String, dynamic>>[];
        Map<String, dynamic>? originalCommand;
        for (var i = 0; i < 3; i++) {
          final event = refunds[i],
              prefix = '/accounting/refunds/events/${refunds[i]['id']}';
          final state = businessMap(await worker.read(prefix)),
              portion = businessItems(
                await worker.read('$prefix/portions?limit=1&offset=0'),
              ).single;
          final originPage = businessMap(
            await worker.read(
              '$prefix/origins?portion_id=${portion['portion_id']}&limit=1&offset=0',
            ),
          );
          expect(originPage['next_offset'], 1);
          final next = businessItems(
            await worker.read(
              '$prefix/origins?portion_id=${portion['portion_id']}&limit=100&offset=1',
            ),
          );
          final all = [...businessItems(originPage), ...next];
          // Explicitly choose the first two C1 entries, never an automatic match.
          final chosen = components
              .take(2)
              .map((c) => all.singleWhere((o) => o['entry_id'] == c['id']))
              .toList();
          expect(chosen[0]['group_id'], chosen[1]['group_id']);
          expect(chosen[0]['entry_id'], isNot(chosen[1]['entry_id']));
          expect(chosen[0]['component_sequence'], components[0]['sequence']);
          expect(chosen[0]['category'], 'S');
          expect(chosen[0]['rate'], '19');
          for (final o in chosen)
            await worker.read('/accounting/events/${o['origin_event_id']}');
          final body = {
            'source_hash': state['source_hash'],
            'expected_revision': state['revision'],
            'state_hash': state['state_hash'],
            'portion_id': portion['portion_id'],
            'portion_state_hash': portion['portion_state_hash'],
            'origins': [
              for (final o in chosen)
                {
                  'entry_id': o['entry_id'],
                  'group_id': o['group_id'],
                  'lot_state_hash': o['lot_state_hash'],
                  'amount': i == 2 ? '13.23' : '13.22',
                },
            ],
            'reason': 'Synthetic explicitly reviewed original receipt shares',
          };
          final history = await worker.read('$prefix/history');
          final preview = businessMap(
            await worker.previewRefundOrigins(event['id'], body),
          );
          expect(await worker.read('$prefix/history'), history);
          expect(await worker.read(prefix), state);
          final command = {
            ...body,
            'preview_hash': preview['preview_hash'],
            'confirmation': true,
          };
          if (i == 0) {
            originalCommand = command;
            api.lose = true;
            await expectLater(
              worker.command('refund-$i', '$prefix/confirm', command),
              throwsA(isA<ApiException>().having((e) => e.status, 'status', 0)),
            );
          }
          if (i == 0) {
            results.add(
              businessItems(await worker.read('$prefix/history')).single,
            );
          } else {
            results.add(
              businessMap(
                await worker.command('refund-$i', '$prefix/confirm', command),
              ),
            );
          }
          expect(await worker.read('/accounting/events/${event['id']}'), event);
          expect(await worker.read('/finance/open-items'), beforeOpen);
        }
        expect(results.map((e) => e['net']), ['22.22', '22.21', '22.24']);
        expect(results.map((e) => e['tax']), ['4.22', '4.23', '4.22']);
        for (final r in results) {
          expect(r['capacity_released'], false);
          expect(r['tax_result_available'], false);
        }
        expect(
          businessItems(results.last['lines']).map((l) => l['remaining_gross']),
          ['0.00', '0.00'],
        );
        final firstPath = '/accounting/refunds/events/${refunds.first['id']}';
        final replay = await worker.command(
          'refund-0',
          '$firstPath/confirm',
          originalCommand!,
        );
        expect(replay, results.first);
        expect(api.confirms.first, api.confirms.last);
        for (var i = 0; i < incoming.length; i++) {
          expect(
            await worker.read('/accounting/events/${incoming[i]['id']}'),
            incoming[i],
          );
          expect(
            await worker.read(
              '/accounting/components/events/${incoming[i]['id']}/history',
            ),
            beforeComponents[i],
          );
        }
        // A later full source read denial also hides the old refund history.
        await owner.command('deny-source', '/settings/permissions', {
          'user_id': setup['worker_id'],
          'scope': setup['project_id'],
          'permission': 'finance.read',
          'effect': 'deny',
          'revision': 0,
        });
        await expectLater(
          worker.read('$firstPath/history'),
          throwsA(isA<ApiException>().having((e) => e.status, 'status', 403)),
        );
        await expectLater(
          api.call(worker.path('$firstPath/confirm'), api.confirms.first),
          throwsA(isA<ApiException>().having((e) => e.status, 'status', 403)),
        );
      }, BackendHttp());
    } finally {
      for (final session in sessions) session.dispose();
      for (final api in apis) api.dispose();
      server?.kill();
      await output?.cancel();
      await errors?.cancel();
      if (server != null)
        await server.exitCode.timeout(
          const Duration(seconds: 5),
          onTimeout: () => -1,
        );
      await temp.delete(recursive: true);
    }
  }, timeout: const Timeout(Duration(minutes: 2)));
}

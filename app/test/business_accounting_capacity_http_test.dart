@Tags(['posix_backend'])
library;

import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:smartplan_office/api.dart';
import 'package:smartplan_office/business_session.dart';

import 'backend_integration_test.dart' show BackendHttp;
import 'business_accounting_allocations_http_test.dart' show seedInvoice;
import 'import_backend_integration_test.dart' show fixture;

class CapacityConnection extends OfficeApi {
  CapacityConnection(String base) : super(baseUrl: base, apiVersion: 'v1');
  String? losePath;
  final confirmations = <({String path, Map<String, dynamic> body})>[];
  @override
  Future<dynamic> call(String path, [Map<String, dynamic>? body]) async {
    if (body != null &&
        path.contains('/accounting/components/') &&
        path.endsWith('/confirm')) {
      confirmations.add((
        path: path,
        body: jsonDecode(jsonEncode(body)) as Map<String, dynamic>,
      ));
    }
    dynamic result;
    try {
      result = await super.call(path, body);
    } on ApiException catch (e) {
      throw ApiException(
        e.status,
        '$path: ${e.message}',
        requestResolution: e.requestResolution,
      );
    }
    if (path == losePath) {
      losePath = null;
      throw const ApiException(0, 'Synthetic lost component acknowledgement');
    }
    return result;
  }
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  test('real HTTP preserves the middle lot cents and historical pending path across capacity handoff', () async {
    final backend = Directory('../backend').absolute;
    final python =
        Platform.environment['SMARTPLAN_TEST_PYTHON'] ??
        '${backend.path}/.venv/bin/python';
    final temp = await Directory.systemTemp.createTemp(
      'synthetic-capacity-flutter-',
    );
    Process? server;
    StreamIterator<String>? output;
    StreamSubscription<String>? errors;
    final diagnostics = StringBuffer(),
        apis = <CapacityConnection>[],
        sessions = <BusinessSession>[];
    try {
      // The archive fixture uses the explicitly synthetic SQLite issuer only.
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
          final api = CapacityConnection('http://127.0.0.1:${setup['port']}')
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
          owner.hasFeature('accounting_document_component_reuse'),
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
        final api = worker.api as CapacityConnection;
        final account = businessMap(
          await owner.command('account', '/accounting/accounts', {
            'code': 'CAPACITY',
            'name': 'Synthetic documentary account',
            'kind': 'bank',
            'confirmation': true,
          }),
        );
        Future<Map<String, dynamic>> flow(
          String label,
          String amount,
          String kind,
        ) async {
          final payment = businessMap(
            await worker.command('payment-$label', '/finance/payments', {
              'source_id': 'synthetic-capacity-$label',
              'kind': kind,
              'amount': amount,
              'currency': 'EUR',
              'booking_date': '2026-11-03',
              'reference': 'Synthetic already confirmed $kind $label',
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
              'import-$label',
              '/accounting/events/import-payment',
              {
                'payment_id': payment['id'],
                'source_hash': source['source_hash'],
                'account_id': account['id'],
                'account_revision': 1,
                'cash_date': '2026-11-03',
                'evidence_reference': 'SYN-$label',
                'confirmation': true,
              },
            ),
          );
        }

        final incoming = <Map<String, dynamic>>[],
            entries = <Map<String, dynamic>>[];
        for (var i = 0; i < 3; i++) {
          final event = await flow(
            'original-$i',
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
            'reason': 'Synthetic original invoice group',
          };
          final preview = businessMap(
            await worker.previewDocumentComponents(event['id'], body),
          );
          final command = {
            ...body,
            'preview_hash': preview['preview_hash'],
            'confirmation': true,
          };
          if (i == 1) {
            api.losePath = worker.path('$prefix/confirm');
            await expectLater(
              worker.command(
                'accounting-components-${event['id']}',
                '$prefix/confirm',
                command,
              ),
              throwsA(isA<ApiException>().having((e) => e.status, 'status', 0)),
            );
            entries.add(
              businessItems(await worker.read('$prefix/history')).single,
            );
          } else {
            entries.add(
              businessMap(
                await worker.command(
                  'accounting-components-${event['id']}',
                  '$prefix/confirm',
                  command,
                ),
              ),
            );
          }
        }
        expect(entries.map((e) => e['tax']), ['6.33', '6.34', '6.33']);
        final refund = await flow('refund-middle', '39.67', 'refund');
        final refundPath = '/accounting/refunds/events/${refund['id']}';
        final refundState = businessMap(await worker.read(refundPath)),
            refundPortion = businessItems(
              await worker.read('$refundPath/portions'),
            ).single;
        final origin = businessItems(
          await worker.read(
            '$refundPath/origins?portion_id=${refundPortion['portion_id']}',
          ),
        ).singleWhere((o) => o['entry_id'] == entries[1]['id']);
        final refundBody = {
          'source_hash': refundState['source_hash'],
          'expected_revision': refundState['revision'],
          'state_hash': refundState['state_hash'],
          'portion_id': refundPortion['portion_id'],
          'portion_state_hash': refundPortion['portion_state_hash'],
          'origins': [
            {
              'entry_id': origin['entry_id'],
              'group_id': origin['group_id'],
              'lot_state_hash': origin['lot_state_hash'],
              'amount': '39.67',
            },
          ],
          'reason': 'Synthetic full return of exact middle lot',
        };
        final refundPreview = businessMap(
          await worker.previewRefundOrigins(refund['id'], refundBody),
        );
        final returned = businessMap(
          await worker.command('refund', '$refundPath/confirm', {
            ...refundBody,
            'preview_hash': refundPreview['preview_hash'],
            'confirmation': true,
          }),
        );
        expect(returned['net'], '33.33');
        expect(returned['tax'], '6.34');
        expect(returned['capacity_released'], false);
        final receipt = await flow('new-receipt', '39.67', 'receipt');
        final prefix = '/accounting/components/v2/events/${receipt['id']}';
        final state = businessMap(await worker.read(prefix)),
            portion = businessItems(await worker.read('$prefix/portions'))
                .single;
        expect(portion['writer'], 'c2');
        expect(portion['action'], 'takeover_and_document');
        final offered = businessMap(
          businessItems(portion['groups']).single['offered_capacity'],
        );
        expect(offered['net'], '33.33');
        expect(offered['tax'], '6.34');
        expect(offered['gross'], '39.67');
        final body = {
          'source_hash': state['source_hash'],
          'expected_revision': state['revision'],
          'state_hash': state['state_hash'],
          'portion_id': portion['portion_id'],
          'portion_state_hash': portion['portion_state_hash'],
          'action': portion['action'],
          'groups': [
            {
              'group_id': businessItems(portion['groups']).single['group_id'],
              'amount': '39.67',
            },
          ],
          'reason': 'Synthetic explicitly reviewed all-group handoff',
        };
        final openItems = await worker.read('/finance/open-items'),
            oldHistory = await worker.read(
              '/accounting/components/events/${incoming[1]['id']}/history',
            );
        final preview = businessMap(
          await worker.previewReusableDocumentComponents(receipt['id'], body),
        );
        expect(await worker.read(prefix), state);
        expect(businessItems(await worker.read('$prefix/history')), isEmpty);
        expect(preview['net'], '33.33');
        expect(preview['tax'], '6.34');
        expect(businessItems(preview['capacity_changes']).single['returned'], {
          'net': '33.33',
          'tax': '6.34',
          'gross': '39.67',
        });
        api.losePath = worker.path('$prefix/confirm');
        await expectLater(
          worker.command(
            'accounting-components-${receipt['id']}',
            '$prefix/confirm',
            {
              ...body,
              'preview_hash': preview['preview_hash'],
              'confirmation': true,
            },
          ),
          throwsA(isA<ApiException>().having((e) => e.status, 'status', 0)),
        );
        final accepted = businessItems(await worker.read('$prefix/history'))
            .single;
        final replay = await worker.repeatDocumentComponentCommand(
          receipt['id'],
        );
        expect(replay, accepted);
        expect(accepted['tax_result_available'], false);
        expect(await worker.read('/finance/open-items'), openItems);
        expect(
          await worker.read('/accounting/events/${receipt['id']}'),
          receipt,
        );
        expect(await worker.read('/accounting/events/${refund['id']}'), refund);
        expect(
          await worker.read(
            '/accounting/components/events/${incoming[1]['id']}/history',
          ),
          oldHistory,
        );
        expect(
          businessItems(await worker.read('$refundPath/history')).single,
          returned,
        );
        final oldReplay = await worker.repeatDocumentComponentCommand(
          incoming[1]['id'],
        );
        expect(oldReplay, entries[1]);
        final legacySent = api.confirmations
            .where(
              (c) => c.path.endsWith('/events/${incoming[1]['id']}/confirm'),
            )
            .toList();
        expect(legacySent, hasLength(2));
        expect(legacySent.first.body, legacySent.last.body);
        final newerSent = api.confirmations
            .where((c) => c.path == worker.path('$prefix/confirm'))
            .toList();
        expect(newerSent, hasLength(2));
        expect(newerSent.first.body, newerSent.last.body);
        await expectLater(
          worker.command(
            'accounting-components-${receipt['id']}',
            '$prefix/confirm',
            {
              ...body,
              'preview_hash': preview['preview_hash'],
              'confirmation': true,
            },
          ),
          throwsA(
            isA<ApiException>()
                .having((e) => e.status, 'status', 409)
                .having(
                  (e) => e.requestResolution,
                  'server proof of non-acceptance',
                  'not_accepted',
                ),
          ),
        );
        expect(worker.pending('accounting-components-${receipt['id']}'), false);
        expect(
          businessItems(await worker.read('$prefix/history')),
          hasLength(1),
        );
      }, BackendHttp());
    } finally {
      for (final session in sessions) {
        session.dispose();
      }
      for (final api in apis) {
        api.dispose();
      }
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

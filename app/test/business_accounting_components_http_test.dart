@Tags(['posix_backend'])
library;

import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:smartplan_office/api.dart';
import 'package:smartplan_office/business_session.dart';

import 'backend_integration_test.dart' show BackendHttp;
import 'import_backend_integration_test.dart' show fixture;
import 'business_accounting_allocations_http_test.dart' show seedInvoice;

class ComponentConnection extends OfficeApi {
  ComponentConnection(String base) : super(baseUrl: base, apiVersion: 'v1');
  bool lose = false;
  final confirms = <Map<String, dynamic>>[];
  @override
  Future<dynamic> call(String path, [Map<String, dynamic>? body]) async {
    if (body != null &&
        path.contains('/components/') &&
        path.endsWith('/confirm'))
      confirms.add(jsonDecode(jsonEncode(body)) as Map<String, dynamic>);
    final result = await super.call(path, body);
    if (body != null &&
        path.contains('/components/') &&
        path.endsWith('/confirm') &&
        lose) {
      lose = false;
      throw const ApiException(0, 'Synthetic component response loss');
    }
    return result;
  }
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  test('Real HTTP documentary cents share one group across payouts and preserve reviews, payment and OP proofs', () async {
    final backend = Directory('../backend').absolute;
    final python =
        Platform.environment['SMARTPLAN_TEST_PYTHON'] ??
        '${backend.path}/.venv/bin/python';
    final temp = await Directory.systemTemp.createTemp(
      'synthetic-components-flutter-',
    );
    Process? server;
    StreamIterator<String>? output;
    StreamSubscription<String>? errors;
    final diagnostics = StringBuffer(),
        apis = <ComponentConnection>[],
        sessions = <BusinessSession>[];
    try {
      // Only the input invoice archive uses the explicit synthetic SQLite test
      // issuer. All HTTP component/payment/authorization paths remain real.
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
          final api = ComponentConnection('http://127.0.0.1:${setup['port']}')
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
          owner.hasFeature('accounting_document_components'),
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
            'code': 'CENTS',
            'name': 'Synthetic account',
            'kind': 'bank',
            'confirmation': true,
          }),
        );
        final receipt = businessMap(
          await owner.command('receipt', '/finance/receipts', {
            'project_id': setup['project_id'],
            'filename': 'synthetic-cents.pdf',
            'media_type': 'application/pdf',
            'original_base64': base64Encode(
              utf8.encode('%PDF-1.4\nSynthetic components original\n%%EOF'),
            ),
            'note': 'Synthetic evidence',
          }),
        );
        Map<String, dynamic> review(int revision, String vendor) => {
          'revision': revision,
          'vendor': vendor,
          'invoice_number': 'SYN-CENTS',
          'issue_date': '2026-11-01',
          'net': '100.00',
          'tax': '19.00',
          'gross': '119.00',
          'currency': 'EUR',
          'status': 'reviewed',
          'note': 'Synthetic review',
        };
        await owner.command(
          'review',
          '/finance/receipts/${receipt['id']}',
          review(0, 'Synthetic supplier'),
        );
        final payouts = <Map<String, dynamic>>[];
        for (var i = 0; i < 3; i++) {
          final source = businessItems(
            await worker.read('/accounting/sources/receipts'),
          ).single;
          payouts.add(
            businessMap(
              await worker.command('payout-$i', '/accounting/events/payout', {
                'receipt_id': source['receipt_id'],
                'source_hash': source['source_hash'],
                'review_revision': source['review_revision'],
                'review_sha256': source['review_sha256'],
                'original_sha256': source['original_sha256'],
                'account_id': account['id'],
                'account_revision': 1,
                'expected_cash_revision': source['cash_revision'],
                'amount': i == 2 ? '39.66' : '39.67',
                'cash_date': '2026-11-02',
                'evidence_reference': 'SYN-PART-$i',
                'reference': 'Synthetic confirmed payout',
                'confirmation': true,
              }),
            ),
          );
        }
        await owner.command(
          'inactive',
          '/accounting/accounts/${account['id']}',
          {
            'revision': 1,
            'name': 'Synthetic inactive account',
            'active': false,
            'confirmation': true,
          },
        );
        final results = <Map<String, dynamic>>[];
        final workerApi = worker.api as ComponentConnection;
        Map<String, dynamic>? firstCommand;
        for (var i = 0; i < payouts.length; i++) {
          final event = payouts[i],
              path = '/accounting/components/events/${payouts[i]['id']}';
          final state = businessMap(await worker.read(path));
          final portion = businessItems(await worker.read('$path/portions'))
              .single;
          final body = <String, dynamic>{
            'source_hash': state['source_hash'],
            'expected_revision': state['revision'],
            'state_hash': state['state_hash'],
            'portion_id': portion['portion_id'],
            'portion_state_hash': portion['portion_state_hash'],
            'groups': [
              {
                'group_id': (portion['groups'] as List).single['group_id'],
                'amount': portion['amount'],
              },
            ],
            'reason': 'Synthetic exact documentary portion',
          };
          final before = await worker.read('$path/history');
          final preview = businessMap(
            await worker.previewDocumentComponents(event['id'], body),
          );
          expect(await worker.read('$path/history'), before);
          expect(await worker.read(path), state);
          final command = {
            ...body,
            'preview_hash': preview['preview_hash'],
            'confirmation': true,
          };
          if (i == 0) {
            firstCommand = command;
            workerApi.lose = true;
            await expectLater(
              worker.command('components-first', '$path/confirm', command),
              throwsA(isA<ApiException>().having((e) => e.status, 'status', 0)),
            );
            results.add(
              businessItems(await worker.read('$path/history')).single,
            );
          } else
            results.add(
              businessMap(
                await worker.command('components-$i', '$path/confirm', command),
              ),
            );
          expect(await worker.read('/accounting/events/${event['id']}'), event);
        }
        expect(results.map((r) => r['net']), ['33.34', '33.33', '33.33']);
        expect(results.map((r) => r['tax']), ['6.33', '6.34', '6.33']);
        expect(
          (results.last['lines'] as List).single['remaining_gross'],
          '0.00',
        );
        await owner.command(
          'review-new',
          '/finance/receipts/${receipt['id']}',
          review(1, 'Synthetic supplier new review'),
        );
        final firstPath =
            '/accounting/components/events/${payouts.first['id']}';
        final replay = businessMap(
          await worker.command(
            'components-first',
            '$firstPath/confirm',
            worker.pendingCommandValues(
              'components-first',
              path: '$firstPath/confirm',
            )!,
          ),
        );
        expect(replay, results.first);
        expect(replay['portion']['review_revision'], 1);
        expect(workerApi.confirms.first, workerApi.confirms.last);
        await expectLater(
          worker.command(
            'new-after-review',
            '$firstPath/confirm',
            firstCommand!,
          ),
          throwsA(isA<ApiException>().having((e) => e.status, 'status', 409)),
        );
        // Original customer allocation is documented once without any second OP effect.
        final payment = businessMap(
          await worker.command('payment', '/finance/payments', {
            'source_id': 'synthetic-component-payment',
            'kind': 'receipt',
            'amount': '59.50',
            'currency': 'EUR',
            'booking_date': '2026-11-02',
            'reference': 'Synthetic customer receipt',
            'allocations': [
              {'document_id': setup['invoice_id'], 'amount': '59.50'},
            ],
          }),
        );
        final source = businessItems(
          await worker.read('/accounting/sources/payments'),
        ).singleWhere((p) => p['payment_id'] == payment['id']);
        await owner.command(
          'reactivate',
          '/accounting/accounts/${account['id']}',
          {
            'revision': 2,
            'name': 'Synthetic active account',
            'active': true,
            'confirmation': true,
          },
        );
        final customerCash = businessMap(
          await worker.command('import', '/accounting/events/import-payment', {
            'payment_id': payment['id'],
            'source_hash': source['source_hash'],
            'account_id': account['id'],
            'account_revision': 3,
            'cash_date': '2026-11-02',
            'evidence_reference': 'SYN-CUSTOMER',
            'confirmation': true,
          }),
        );
        final path = '/accounting/components/events/${customerCash['id']}';
        final state = businessMap(await worker.read(path)),
            portion = businessItems(await worker.read('$path/portions')).single;
        final body = <String, dynamic>{
          'source_hash': state['source_hash'],
          'expected_revision': 0,
          'state_hash': state['state_hash'],
          'portion_id': portion['portion_id'],
          'portion_state_hash': portion['portion_state_hash'],
          'groups': [
            {
              'group_id': (portion['groups'] as List).single['group_id'],
              'amount': '59.50',
            },
          ],
          'reason': 'Synthetic original invoice portion',
        };
        final openBefore = await worker.read('/finance/open-items');
        final preview = businessMap(
          await worker.previewDocumentComponents(customerCash['id'], body),
        );
        await worker.command('customer-components', '$path/confirm', {
          ...body,
          'preview_hash': preview['preview_hash'],
          'confirmation': true,
        });
        expect(await worker.read('/finance/open-items'), openBefore);
        expect(
          await worker.read('/accounting/events/${customerCash['id']}'),
          customerCash,
        );
        await owner.command('source-deny', '/settings/permissions', {
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
          worker.read(path),
          throwsA(isA<ApiException>().having((e) => e.status, 'status', 403)),
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

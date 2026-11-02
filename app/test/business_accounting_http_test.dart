import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:smartplan_office/api.dart';
import 'package:smartplan_office/business_accounting.dart';
import 'package:smartplan_office/business_session.dart';

import 'backend_integration_test.dart' show BackendHttp;
import 'import_backend_integration_test.dart' show fixture;

class AccountingConnection extends OfficeApi {
  AccountingConnection(String base) : super(baseUrl: base, apiVersion: 'v1');
  bool lose = false;
  final payouts = <Map<String, dynamic>>[];
  @override
  Future<dynamic> call(String path, [Map<String, dynamic>? body]) async {
    if (body != null && path.endsWith('/accounting/events/payout'))
      payouts.add(jsonDecode(jsonEncode(body)) as Map<String, dynamic>);
    final result = await super.call(path, body);
    if (body != null && path.endsWith('/accounting/events/payout') && lose) {
      lose = false;
      throw const ApiException(0, 'Synthetic response loss');
    }
    return result;
  }
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  test('Real HTTP nonowner global preparation links sources once and replays frozen partial payout', () async {
    final backend = Directory('../backend').absolute;
    final python =
        Platform.environment['SMARTPLAN_TEST_PYTHON'] ??
        '${backend.path}/.venv/bin/python';
    final temporary = await Directory.systemTemp.createTemp(
      'synthetic-accounting-flutter-',
    );
    Process? server;
    StreamIterator<String>? output;
    StreamSubscription<String>? errors;
    AccountingConnection? ownerApi, workerApi;
    BusinessSession? owner, worker;
    final diagnostic = StringBuffer();
    try {
      final seed = fixture
          .replaceFirst('app = create_app(', '''worker_id = office.add_user('worker@example.test', 'Synthetic-accounting-worker-123', 'accountant')
worker_token = office.login('worker@example.test', 'Synthetic-accounting-worker-123')
office.assign(user, project, worker_id)
app = create_app(''')
          .replaceFirst(
            'project_id=project)',
            'project_id=project, worker_id=worker_id, worker_token=worker_token)',
          );
      server = await Process.start(python, [
        '-u',
        '-c',
        seed,
        temporary.path,
      ], workingDirectory: backend.path);
      errors = server.stderr.transform(utf8.decoder).listen(diagnostic.write);
      output = StreamIterator(
        server.stdout.transform(utf8.decoder).transform(const LineSplitter()),
      );
      expect(
        await output.moveNext().timeout(const Duration(seconds: 30)),
        true,
        reason: '$diagnostic',
      );
      final setup = jsonDecode(output.current) as Map<String, dynamic>;
      await HttpOverrides.runWithHttpOverrides(() async {
        final base = 'http://127.0.0.1:${setup['port']}';
        ownerApi = AccountingConnection(base)..token = setup['token'];
        workerApi = AccountingConnection(base)..token = setup['worker_token'];
        owner = BusinessSession(api: ownerApi!);
        worker = BusinessSession(api: workerApi!);
        await owner!.load();
        await worker!.load();
        expect(worker!.can('accounting.read'), false);
        expect(businessAccountingReadable(worker!), false);
        for (final right in ['accounting.read', 'accounting.prepare']) {
          await owner!.command('grant-$right', '/settings/permissions', {
            'user_id': setup['worker_id'],
            'scope': '*',
            'permission': right,
            'effect': 'allow',
            'revision': 0,
          });
        }
        await worker!.load();
        expect(businessAccountingReadable(worker!), true);
        expect(worker!.can('accounting.admin'), false);
        final account = businessMap(
          await owner!.command('account', '/accounting/accounts', {
            'code': 'BANK',
            'name': 'Synthetic account',
            'kind': 'bank',
            'confirmation': true,
          }),
        );
        expect(
          businessMap(
            await worker!.read('/accounting/status'),
          )['tax_result_available'],
          false,
        );
        Future<Map<String, dynamic>> receipt(
          String suffix, {
          bool project = true,
        }) async {
          final r = businessMap(
            await owner!.command('receipt-$suffix', '/finance/receipts', {
              if (project) 'project_id': setup['project_id'],
              'filename': 'synthetic-$suffix.pdf',
              'media_type': 'application/pdf',
              'original_base64': base64Encode(
                utf8.encode('%PDF-1.4\nSynthetic $suffix\n%%EOF'),
              ),
              'note': 'Synthetic evidence',
            }),
          );
          await owner!.command(
            'review-$suffix',
            '/finance/receipts/${r['id']}',
            {
              'revision': 0,
              'vendor': 'Synthetic supplier',
              'invoice_number': 'SYN-$suffix',
              'issue_date': '2026-11-01',
              'net': '100.00',
              'tax': '19.00',
              'gross': '119.00',
              'currency': 'EUR',
              'status': 'reviewed',
              'note': 'Synthetic review',
            },
          );
          return r;
        }

        final visible = await receipt('visible');
        await receipt('owner-only', project: false);
        final sources = businessItems(
          await worker!.read('/accounting/sources/receipts?limit=50&offset=0'),
        );
        expect(sources, hasLength(1));
        expect(sources.single['receipt_id'], visible['id']);
        final source = sources.single;
        final payout = <String, dynamic>{
          'receipt_id': source['receipt_id'],
          'source_hash': source['source_hash'],
          'review_revision': source['review_revision'],
          'review_sha256': source['review_sha256'],
          'original_sha256': source['original_sha256'],
          'account_id': account['id'],
          'account_revision': account['revision'],
          'expected_cash_revision': source['cash_revision'],
          'amount': accountingAmount('59,50'),
          'cash_date': '2026-11-02',
          'evidence_reference': 'SYN-PART-1',
          'reference': 'Synthetic manual payout',
          'confirmation': true,
        };
        workerApi!.lose = true;
        await expectLater(
          worker!.command('payout', '/accounting/events/payout', payout),
          throwsA(isA<ApiException>().having((e) => e.status, 'status', 0)),
        );
        await owner!.command(
          'rename',
          '/accounting/accounts/${account['id']}',
          {
            'revision': 1,
            'name': 'Synthetic renamed inactive account',
            'active': false,
            'confirmation': true,
          },
        );
        await owner!.command(
          'review-new',
          '/finance/receipts/${visible['id']}',
          {
            'revision': 1,
            'vendor': 'Synthetic supplier revised',
            'invoice_number': 'SYN-visible',
            'issue_date': '2026-11-01',
            'net': '100.00',
            'tax': '19.00',
            'gross': '119.00',
            'currency': 'EUR',
            'status': 'reviewed',
            'note': 'New legitimate review',
          },
        );
        final replay = businessMap(
          await worker!.command(
            'payout',
            '/accounting/events/payout',
            worker!.pendingCommandValues(
              'payout',
              path: '/accounting/events/payout',
            )!,
          ),
        );
        expect(replay['amount'], '59.50');
        expect(replay['account']['revision'], 1);
        expect(workerApi!.payouts, hasLength(2));
        expect(workerApi!.payouts[0], workerApi!.payouts[1]);
        expect(
          businessItems(await worker!.read('/accounting/events')),
          hasLength(1),
        );
        expect(
          businessItems(await worker!.read('/accounting/sources/receipts'))
              .single['blocked_reason'],
          'review_changed',
        );
        await expectLater(
          worker!.command('new-stale', '/accounting/events/payout', {
            ...payout,
            'evidence_reference': 'SYN-PART-2',
          }),
          throwsA(isA<ApiException>().having((e) => e.status, 'status', 409)),
        );
        final active = businessMap(
          await owner!.command(
            'reactivate',
            '/accounting/accounts/${account['id']}',
            {
              'revision': 2,
              'name': 'Synthetic active account',
              'active': true,
              'confirmation': true,
            },
          ),
        );
        await worker!.command('existing-payment', '/finance/payments', {
          'source_id': 'synthetic-old-payment',
          'kind': 'receipt',
          'amount': '25.00',
          'currency': 'EUR',
          'booking_date': '2026-11-01',
          'reference': 'Synthetic existing customer payment',
          'allocations': [],
        });
        final before = businessItems(await worker!.read('/finance/payments'));
        final payment = businessItems(
          await worker!.read('/accounting/sources/payments'),
        ).single;
        final values = <String, dynamic>{
          'payment_id': payment['payment_id'],
          'source_hash': payment['source_hash'],
          'account_id': active['id'],
          'account_revision': active['revision'],
          'cash_date': '2026-11-02',
          'evidence_reference': 'SYN-IMPORT-1',
          'confirmation': true,
        };
        await worker!.command(
          'import',
          '/accounting/events/import-payment',
          values,
        );
        expect(businessItems(await worker!.read('/finance/payments')), before);
        await expectLater(
          worker!.command(
            'import-again',
            '/accounting/events/import-payment',
            values,
          ),
          throwsA(isA<ApiException>().having((e) => e.status, 'status', 409)),
        );
        await owner!.command('revoke-source', '/settings/permissions', {
          'user_id': setup['worker_id'],
          'scope': setup['project_id'],
          'permission': 'finance.read',
          'effect': 'deny',
          'revision': 0,
        });
        expect(
          businessItems(await worker!.read('/accounting/sources/receipts')),
          isEmpty,
        );
        expect(
          businessItems(await worker!.read('/accounting/events')),
          hasLength(1),
        );
        await expectLater(
          worker!.read('/accounting/events/${replay['id']}'),
          throwsA(isA<ApiException>().having((e) => e.status, 'status', 403)),
        );
      }, BackendHttp());
    } finally {
      owner?.dispose();
      worker?.dispose();
      ownerApi?.dispose();
      workerApi?.dispose();
      server?.kill();
      await output?.cancel();
      await errors?.cancel();
      if (server != null)
        await server.exitCode.timeout(
          const Duration(seconds: 5),
          onTimeout: () => -1,
        );
      await temporary.delete(recursive: true);
    }
  }, timeout: const Timeout(Duration(minutes: 2)));
}

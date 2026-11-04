import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:smartplan_office/api.dart';
import 'package:smartplan_office/business_session.dart';

import 'backend_integration_test.dart' show BackendHttp;
import 'import_backend_integration_test.dart' show fixture;

// Transport/retry proof against real Flask/domain code. The archived invoice is
// seeded by the repository's explicitly synthetic SQLite issuer test fixture.
// Production invoice issuance remains gated and is tested separately on PG.
const seedInvoice = r'''
import uuid
from business_tests.test_documents import SyntheticDocuments, seed_synthetic_issuer
from business_documents import render_prepared
worker_id = office.add_user('worker@example.test', 'Synthetic-allocation-worker-123', 'accountant')
worker_token = office.login('worker@example.test', 'Synthetic-allocation-worker-123')
other_id = office.add_user('other@example.test', 'Synthetic-allocation-other-123', 'accountant')
other_token = office.login('other@example.test', 'Synthetic-allocation-other-123')
office.assign(user, project, worker_id)
office.assign(user, project, other_id)
def req(**values): return dict(request_id=uuid.uuid4().hex, **values)
docs = SyntheticDocuments(office)
docs.save_settings(user, req(revision=0, company_name='Synthetic seller', address_line='Testweg 1', postal_code='10115', city='Berlin', country='DE', vat_id='DE123456789', email='synthetic@example.test', issuing_enabled=False, issuer_mode='own', cutover_ack=True, cutover_date='2026-01-01', einvoice_format='none'))
seed_synthetic_issuer(docs, user)
draft = docs.create(user, req(project_id=project, kind='invoice', title='Synthetic allocation target', issue_date='2026-11-02', due_date='2026-11-16', buyer=dict(name='Synthetic customer', address_line='Testweg 2', postal_code='10117', city='Berlin', country='DE'), positions=[dict(description='Synthetic service', quantity='1', unit='C62', unit_price_net='100.00', tax_rate='19')]))
prepared = docs.prepare_finalization(user, draft['id'], draft['revision'])
invoice = docs.finalize(user, draft['id'], render_prepared(prepared), uuid.uuid4().hex)
''';

class AllocationConnection extends OfficeApi {
  AllocationConnection(String base) : super(baseUrl: base, apiVersion: 'v1');
  bool loseAssignment = false;
  final assignments = <Map<String, dynamic>>[];
  final previews = <Map<String, dynamic>>[];
  @override
  Future<dynamic> call(String path, [Map<String, dynamic>? body]) async {
    if (body != null && path.contains('/accounting/allocations/')) {
      final saved = jsonDecode(jsonEncode(body)) as Map<String, dynamic>;
      if (path.endsWith('/assign')) assignments.add(saved);
      if (path.endsWith('/preview')) previews.add(saved);
    }
    final result = await super.call(path, body);
    if (body != null && path.endsWith('/assign') && loseAssignment) {
      loseAssignment = false;
      throw const ApiException(0, 'Synthetic allocation response loss');
    }
    return result;
  }
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  test('Real HTTP allocates imported payment without rewriting cash proof, retries after OP changes, and keeps private/source boundaries', () async {
    final backend = Directory('../backend').absolute;
    final python =
        Platform.environment['SMARTPLAN_TEST_PYTHON'] ??
        '${backend.path}/.venv/bin/python';
    final temp = await Directory.systemTemp.createTemp(
      'synthetic-flutter-allocation-',
    );
    Process? server;
    StreamIterator<String>? output;
    StreamSubscription<String>? errors;
    final apis = <AllocationConnection>[];
    final sessions = <BusinessSession>[];
    final diagnostics = StringBuffer();
    try {
      final seed = fixture
          .replaceFirst('app = create_app(', '$seedInvoice\napp = create_app(')
          .replaceFirst(
            'project_id=project)',
            "project_id=project, worker_id=worker_id, worker_token=worker_token, other_id=other_id, other_token=other_token, invoice_id=invoice['id'])",
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
        Future<BusinessSession> connection(String token) async {
          final api = AllocationConnection('http://127.0.0.1:${setup['port']}')
            ..token = token;
          final session = BusinessSession(api: api);
          apis.add(api);
          sessions.add(session);
          await session.load();
          return session;
        }

        final owner = await connection(setup['token']);
        final worker = await connection(setup['worker_token']);
        final other = await connection(setup['other_token']);
        expect(
          owner.hasFeature('accounting_payment_allocation'),
          true,
          reason: owner.error,
        );
        for (final user in [setup['worker_id'], setup['other_id']]) {
          for (final right in ['accounting.read', 'accounting.prepare']) {
            await owner.command('grant-$user-$right', '/settings/permissions', {
              'user_id': user,
              'scope': '*',
              'permission': right,
              'effect': 'allow',
              'revision': 0,
            });
          }
        }
        await worker.load();
        await other.load();
        final account = businessMap(
          await owner.command('account', '/accounting/accounts', {
            'code': 'SYNBANK',
            'name': 'Synthetic bank evidence',
            'kind': 'bank',
            'confirmation': true,
          }),
        );
        final payment = businessMap(
          await worker.command('payment', '/finance/payments', {
            'source_id': 'synthetic-free-receipt',
            'kind': 'receipt',
            'amount': '119.00',
            'currency': 'EUR',
            'booking_date': '2026-11-02',
            'reference': 'Synthetic received amount',
            'allocations': [],
          }),
        );
        final source = businessItems(
          await worker.read('/accounting/sources/payments'),
        ).single;
        final cash = businessMap(
          await worker.command('import', '/accounting/events/import-payment', {
            'payment_id': payment['id'],
            'source_hash': source['source_hash'],
            'account_id': account['id'],
            'account_revision': account['revision'],
            'cash_date': '2026-11-02',
            'evidence_reference': 'SYN-RECEIVED-119',
            'confirmation': true,
          }),
        );
        final prefix = '/accounting/allocations/payments/${payment['id']}';
        Future<Map<String, dynamic>> openItem() async =>
            businessItems(await worker.read('/finance/open-items'))
                .singleWhere((row) => row['id'] == setup['invoice_id']);
        expect((await openItem())['open'], '119.00');
        final state = businessMap(await worker.read(prefix));
        final candidate = businessItems(
          await worker.read('$prefix/candidates?limit=50&offset=0'),
        ).single;
        final body = <String, dynamic>{
          'source_hash': state['source_hash'],
          'expected_revision': state['revision'],
          'state_hash': state['state_hash'],
          'customer_id': candidate['customer_id'],
          'document_id': candidate['document_id'],
          'document_state_hash': candidate['document_state_hash'],
          'amount': '59.50',
          'reason': 'Synthetic confirmed customer and invoice match',
        };
        final beforeHistory = await worker.read('$prefix/history');
        final preview = businessMap(
          await worker.previewPaymentAllocation(payment['id'], body),
        );
        expect(await worker.read(prefix), state);
        expect(await worker.read('$prefix/history'), beforeHistory);
        expect((await openItem())['open'], '119.00');
        final workerApi = worker.api as AllocationConnection;
        expect(workerApi.previews.single.keys, isNot(contains('request_id')));
        final assign = {
          ...body,
          'preview_hash': preview['preview_hash'],
          'confirmation': true,
        };
        workerApi.loseAssignment = true;
        await expectLater(
          worker.command('assign', '$prefix/assign', assign),
          throwsA(isA<ApiException>().having((e) => e.status, 'status', 0)),
        );
        expect((await openItem())['open'], '59.50');
        await owner.command(
          'inactive-account',
          '/accounting/accounts/${account['id']}',
          {
            'revision': 1,
            'name': 'Synthetic closed account',
            'active': false,
            'confirmation': true,
          },
        );
        await owner.command('later-payment', '/finance/payments', {
          'source_id': 'synthetic-later-payment',
          'kind': 'receipt',
          'amount': '10.00',
          'currency': 'EUR',
          'booking_date': '2026-11-02',
          'reference': 'Synthetic separate later payment',
          'allocations': [
            {'document_id': candidate['document_id'], 'amount': '10.00'},
          ],
        });
        expect((await openItem())['open'], '49.50');
        final entry = businessMap(
          await worker.command(
            'assign',
            '$prefix/assign',
            worker.pendingCommandValues('assign', path: '$prefix/assign')!,
          ),
        );
        expect(entry['open_after'], '59.50');
        expect(workerApi.assignments[0], workerApi.assignments[1]);
        expect(
          businessItems(await worker.read('$prefix/history')),
          hasLength(1),
        );
        expect(await worker.read('/accounting/events/${cash['id']}'), cash);
        expect(
          businessItems(await worker.read('/accounting/sources/payments'))
              .singleWhere((row) => row['payment_id'] == payment['id']),
          {...source, 'linked_event_id': cash['id']},
        );
        await expectLater(
          worker.command('new-stale', '$prefix/assign', assign),
          throwsA(isA<ApiException>().having((e) => e.status, 'status', 409)),
        );
        await expectLater(
          other.read(prefix),
          throwsA(isA<ApiException>().having((e) => e.status, 'status', 403)),
        );
        await expectLater(
          other.read('/accounting/events/${cash['id']}'),
          throwsA(isA<ApiException>().having((e) => e.status, 'status', 403)),
        );
        final fresh = businessMap(await worker.read(prefix));
        final next = businessItems(await worker.read('$prefix/candidates'))
            .single;
        final lastBody = <String, dynamic>{
          'source_hash': fresh['source_hash'],
          'expected_revision': fresh['revision'],
          'state_hash': fresh['state_hash'],
          'customer_id': next['customer_id'],
          'document_id': next['document_id'],
          'document_state_hash': next['document_state_hash'],
          'amount': '49.50',
          'reason': 'Synthetic remaining invoice amount',
        };
        final lastPreview = businessMap(
          await worker.previewPaymentAllocation(payment['id'], lastBody),
        );
        await worker.command('last', '$prefix/assign', {
          ...lastBody,
          'preview_hash': lastPreview['preview_hash'],
          'confirmation': true,
        });
        expect((await openItem())['open'], '0.00');
        expect(
          businessMap(await worker.read(prefix))['unallocated_amount'],
          '10.00',
        );
        expect(
          businessItems(await worker.read('$prefix/history')),
          hasLength(2),
        );
        expect(await worker.read('/accounting/events/${cash['id']}'), cash);
        await owner.command('revoke-source', '/settings/permissions', {
          'user_id': setup['worker_id'],
          'scope': setup['project_id'],
          'permission': 'finance.read',
          'effect': 'deny',
          'revision': 0,
        });
        await expectLater(
          worker.read(prefix),
          throwsA(isA<ApiException>().having((e) => e.status, 'status', 403)),
        );
        expect(businessItems(await worker.read('/accounting/events')), isEmpty);
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

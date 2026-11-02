import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:smartplan_office/api.dart';
import 'package:smartplan_office/business_session.dart';

import 'backend_integration_test.dart' show BackendHttp;
import 'import_backend_integration_test.dart' show fixture;

class PurchasingConnection extends OfficeApi {
  PurchasingConnection(String base) : super(baseUrl: base, apiVersion: 'v1');
  bool dropReceiptAcknowledgement = true;
  final receiptBodies = <Map<String, dynamic>>[];

  @override
  Future<dynamic> call(String path, [Map<String, dynamic>? body]) async {
    if (body != null && path.endsWith('/receipts')) {
      receiptBodies.add(jsonDecode(jsonEncode(body)) as Map<String, dynamic>);
    }
    final result = await super.call(path, body);
    if (body != null &&
        path.endsWith('/receipts') &&
        dropReceiptAcknowledgement) {
      dropReceiptAcknowledgement = false;
      throw const ApiException(0, 'Synthetisch verlorene Erfolgsantwort');
    }
    return result;
  }
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  test(
    'Actual HTTP purchase source, confirmation and receipt retry preserve exact stock and source indices',
    () async {
      final backend = Directory('../backend').absolute;
      final python =
          Platform.environment['SMARTPLAN_TEST_PYTHON'] ??
          '${backend.path}/.venv/bin/python';
      final temporary = await Directory.systemTemp.createTemp(
        'smartplan-purchasing-client-',
      );
      Process? server;
      StreamIterator<String>? output;
      StreamSubscription<String>? errors;
      PurchasingConnection? api;
      BusinessSession? session;
      final diagnostics = StringBuffer();
      try {
        final seed = fixture.replaceFirst(
          'app = create_app(',
          '''from business_schema import ensure_schema
ensure_schema(office, activate=True)
app = create_app(''',
        );
        server = await Process.start(python, [
          '-u',
          '-c',
          seed,
          temporary.path,
        ], workingDirectory: backend.path);
        errors = server.stderr
            .transform(utf8.decoder)
            .listen(diagnostics.write);
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
          api = PurchasingConnection('http://127.0.0.1:${setup['port']}')
            ..token = setup['token'];
          final project = setup['project_id'];
          session = BusinessSession(api: api!, projectId: project);
          await session!.load();
          expect(
            session!.hasFeature('purchasing_receipts'),
            true,
            reason: session!.error,
          );
          expect(session!.hasModule('purchasing'), true);
          final article = businessMap(
            await session!.command('article', '/articles', {
              'code': 'SYN-CABLE',
              'name': 'Synthetisches Kabel',
              'kind': 'material',
              'unit': 'm',
              'unit_price_net': '8.00',
              'cost_price_net': '5.00',
              'tax_rate': '19',
              'currency': 'EUR',
              'active': true,
            }),
          );
          final location = businessMap(
            await session!.command('location', '/inventory/locations', {
              'name': 'Synthetisches Lager',
            }),
          );
          final source = <String, dynamic>{
            'project_id': project,
            'supplier_name': 'Synthetischer Lieferant',
            'status': 'draft',
            'items': [
              {'article_id': article['id'], 'quantity': '5.0000'},
              {'article_id': article['id'], 'quantity': '10.0000'},
            ],
          };
          final draft = businessMap(
            await session!.command('draft', '/inventory/orders', source),
          );
          final orderPath = '/purchasing/orders/${draft['id']}';
          expect(
            businessMap(await session!.read(orderPath))['status'],
            'proposal',
          );
          final approved = businessMap(
            await session!.command(
              'approve',
              '/inventory/orders/${draft['id']}',
              {...source, 'revision': draft['revision'], 'status': 'approved'},
            ),
          );
          final confirmed = businessMap(
            await session!.command('confirm', '$orderPath/confirm', {
              'source_revision': approved['revision'],
              'expected_receipt_revision': 0,
              'order_reference': 'SYN-EXTERN-1',
              'ordered_on': '2026-11-01',
              'confirmation': true,
            }),
          );
          expect(confirmed['status'], 'ordered');
          expect(confirmed['receipt_revision'], 0);
          expect(confirmed['delivery_status'], 'not_sent');
          final partial = <String, dynamic>{
            'source_revision': approved['revision'],
            'expected_receipt_revision': 0,
            'receipt_reference': 'SYN-TEIL-1',
            'received_on': '2026-11-02',
            'location_id': location['id'],
            'lines': [
              {'line_index': 1, 'quantity': '2.125', 'unit_cost_net': '3.5000'},
            ],
          };
          await expectLater(
            session!.command('partial', '$orderPath/receipts', partial),
            throwsA(
              isA<ApiException>().having((error) => error.status, 'status', 0),
            ),
          );
          final first = businessMap(
            await session!.command('partial', '$orderPath/receipts', partial),
          );
          expect(api!.receiptBodies, hasLength(2));
          expect(api!.receiptBodies[0], api!.receiptBodies[1]);
          expect(first['receipt_revision'], 1);
          final progress = businessMap(await session!.read(orderPath));
          expect(progress['status'], 'partially_received');
          expect(progress['items'][0]['received_quantity'], '0.0000');
          expect(progress['items'][1]['remaining_quantity'], '7.8750');
          expect(
            businessItems(await session!.read('$orderPath/receipts')),
            hasLength(1),
          );
          await session!.command('final', '$orderPath/receipts', {
            ...partial,
            'expected_receipt_revision': 1,
            'receipt_reference': 'SYN-REST-2',
            'lines': [
              {
                'line_index': 0,
                'quantity': '5.0000',
                'unit_cost_net': '3.5000',
              },
              {
                'line_index': 1,
                'quantity': '7.8750',
                'unit_cost_net': '3.5000',
              },
            ],
          });
          final complete = businessMap(await session!.read(orderPath));
          expect(complete['status'], 'received');
          expect(complete['receipt_revision'], 2);
          expect(complete['delivery_status'], 'not_sent');
          expect(
            (complete['items'] as List).map(
              (line) => line['remaining_quantity'],
            ),
            everyElement('0.0000'),
          );
          final history = businessItems(
            await session!.read('$orderPath/receipts'),
          );
          expect(history, hasLength(2));
          expect(
            history
                .expand((receipt) => receipt['lines'] as List)
                .map((line) => line['movement_id'])
                .toSet(),
            hasLength(3),
          );
          final stock = businessMap(
            await session!.read(
              '/inventory/stock?article_id=${article['id']}&location_id=${location['id']}',
            ),
          );
          expect(stock['on_hand'], '15.0000');
          expect(stock['stock_value_net'], '52.50');
          final costs = businessMap(
            await session!.read('/projects/$project/costs'),
          );
          expect(costs['material_actual_net'], '0.00');
        }, BackendHttp());
      } finally {
        session?.dispose();
        api?.dispose();
        await output?.cancel();
        await errors?.cancel();
        if (server != null) {
          server.kill();
          try {
            await server.exitCode.timeout(const Duration(seconds: 5));
          } on TimeoutException {
            server.kill(ProcessSignal.sigkill);
            await server.exitCode;
          }
        }
        await temporary.delete(recursive: true);
      }
    },
    skip: !Platform.isLinux,
    timeout: const Timeout(Duration(minutes: 2)),
  );
}

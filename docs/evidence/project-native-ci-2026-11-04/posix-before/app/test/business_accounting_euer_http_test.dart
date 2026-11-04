import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:smartplan_office/api.dart';
import 'package:smartplan_office/business_accounting_euer.dart';
import 'package:smartplan_office/business_session.dart';

import 'backend_integration_test.dart' show BackendHttp;
import 'business_accounting_allocations_http_test.dart' show seedInvoice;
import 'import_backend_integration_test.dart' show fixture;

class EuerHttpConnection extends OfficeApi {
  EuerHttpConnection(String url) : super(baseUrl: url, apiVersion: 'v1');
  bool lose = false, wrong = false;
  String last = '';
  final confirms = <Map<String, dynamic>>[];
  @override
  Future<dynamic> call(String path, [Map<String, dynamic>? body]) async {
    last = path;
    if (body != null && path.endsWith('/euer/confirm'))
      confirms.add(Map<String, dynamic>.from(jsonDecode(jsonEncode(body))));
    final result = await super.call(path, body);
    if (body != null && path.endsWith('/euer/confirm')) {
      if (lose) {
        lose = false;
        throw const ApiException(
          0,
          'Synthetic response loss after real commit',
        );
      }
      if (wrong) {
        wrong = false;
        return {...businessMap(result), 'postings': []};
      }
    }
    return result;
  }
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  test('Real HTTP EÜR chain separates cash, input VAT, asset depreciation, counter-postings, periods and immutable year packages', () async {
    final backend = Directory('../backend').absolute,
        python =
            Platform.environment['SMARTPLAN_TEST_PYTHON'] ??
            '${Directory('../backend').absolute.path}/.venv/bin/python';
    final directory = await Directory.systemTemp.createTemp(
      'synthetic-euer-http-',
    );
    Process? server;
    StreamIterator<String>? output;
    StreamSubscription<String>? errors;
    EuerHttpConnection? api;
    BusinessSession? session;
    final diagnostic = StringBuffer();
    try {
      final seed = fixture
          .replaceFirst(
            'app = create_app(',
            "$seedInvoice\nfrom business_schema import ensure_schema\nensure_schema(office, activate=True)\napp = create_app(",
          )
          .replaceFirst(
            'project_id=project)',
            "project_id=project, invoice_id=invoice['id'])",
          );
      server = await Process.start(python, [
        '-u',
        '-c',
        seed,
        directory.path,
      ], workingDirectory: backend.path);
      errors = server.stderr.transform(utf8.decoder).listen(diagnostic.write);
      output = StreamIterator(
        server.stdout.transform(utf8.decoder).transform(const LineSplitter()),
      );
      expect(
        await output.moveNext().timeout(const Duration(seconds: 30)),
        isTrue,
        reason: '$diagnostic',
      );
      final hello = businessMap(jsonDecode(output.current));
      await HttpOverrides.runWithHttpOverrides(() async {
        api = EuerHttpConnection('http://127.0.0.1:${hello['port']}')
          ..token = hello['token'];
        session = BusinessSession(
          api: api!,
          projects: businessItems(hello['projects']),
        );
        final live = session!;
        await live.load();
        expect(businessEuerReadable(live), isTrue, reason: live.error);
        final profile = businessMap(await live.read('/accounting/profile'));
        final profileBody = {
          'expected_revision': profile['revision'],
          'state_hash': profile['state_hash'],
          'reason': 'Explicit synthetic company facts',
          'evidence_reference': 'Synthetic fixture owner facts',
          'profile': {
            'legal_form': 'sole_proprietorship',
            'accounting_method': 'euer',
            'vat_regime': 'regular',
            'vat_timing': 'cash',
            'vat_effective_from': '2026-01-01',
            'bookkeeping_start': '2026-01-01',
          },
        };
        final pp = businessMap(
          await api!.call(
            live.path('/accounting/profile/preview'),
            profileBody,
          ),
        );
        await live.command(
          'accounting-profile',
          '/accounting/profile/confirm',
          {
            ...profileBody,
            'preview_hash': pp['preview_hash'],
            'confirmation': true,
          },
        );
        final account = businessMap(
          await live.command('synthetic-account', '/accounting/accounts', {
            'code': 'SYNBANK',
            'name': 'Synthetic bank proof',
            'kind': 'bank',
            'confirmation': true,
          }),
        );
        final payment = businessMap(
          await live.command('synthetic-payment', '/finance/payments', {
            'source_id': 'synthetic-euer-income',
            'kind': 'receipt',
            'amount': '119.00',
            'currency': 'EUR',
            'booking_date': '2026-11-02',
            'reference': 'Synthetic received service',
            'allocations': [
              {'document_id': hello['invoice_id'], 'amount': '119.00'},
            ],
          }),
        );
        final paymentSource = businessItems(
          await live.read('/accounting/sources/payments'),
        ).single;
        final sale = businessMap(
          await live.command(
            'synthetic-import',
            '/accounting/events/import-payment',
            {
              'payment_id': payment['id'],
              'source_hash': paymentSource['source_hash'],
              'account_id': account['id'],
              'account_revision': account['revision'],
              'cash_date': '2026-11-02',
              'evidence_reference': 'SYN-IN-119',
              'confirmation': true,
            },
          ),
        );
        Future<void> components(Map<String, dynamic> event) async {
          final path = '/accounting/components/events/${event['id']}',
              state = businessMap(
                await live.read('/accounting/components/events/${event['id']}'),
              ),
              portion = businessItems(
                await live.read(
                  '/accounting/components/events/${event['id']}/portions',
                ),
              ).single;
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
            'reason': 'Exact synthetic invoice cents',
          };
          final preview = businessMap(
            await api!.call(live.path('$path/preview'), body),
          );
          await live.command(
            'synthetic-component-${event['id']}',
            '$path/confirm',
            {
              ...body,
              'preview_hash': preview['preview_hash'],
              'confirmation': true,
            },
          );
        }

        await components(sale);
        Future<Map<String, dynamic>> source(String id) async => businessMap(
          businessItems(await live.read('$euerPath/sources'))
              .singleWhere((row) => row['id'] == id)['source'],
        );
        Future<Map<String, dynamic>> post(
          String operation,
          Map<String, dynamic> payload, {
          bool lost = false,
          bool wrong = false,
        }) async {
          final state = businessMap(await live.read(euerPath));
          final body = {
            'operation': operation,
            'expected_revision': state['revision'],
            'state_hash': state['state_hash'],
            'payload': payload,
            'reason': 'Explicit synthetic subject and account review',
            'evidence_reference': 'Synthetic original and statement',
          };
          final before = await live.read('$euerPath/journal');
          final preview = euerPreview(
            businessMap(await api!.call(live.path('$euerPath/preview'), body)),
            body,
          );
          expect(await live.read('$euerPath/journal'), before);
          final command = {
            ...body,
            'preview_hash': preview['preview_hash'],
            'confirmation': true,
          };
          api!
            ..lose = lost
            ..wrong = wrong;
          if (lost || wrong) {
            await expectLater(
              live.command(
                euerPendingKey,
                '$euerPath/confirm',
                command,
                validateResult: euerReceiptValidator(command, preview),
              ),
              throwsA(isA<ApiException>().having((e) => e.status, 'status', 0)),
            );
            expect(live.pending(euerPendingKey), isTrue);
            final count = businessItems(await live.read('$euerPath/journal'))
                .length;
            final result = businessMap(
              await live.repeatAccountingEuerCommand(),
            );
            expect(
              businessItems(await live.read('$euerPath/journal')),
              hasLength(count),
            );
            expect(
              api!.confirms[api!.confirms.length - 1],
              api!.confirms[api!.confirms.length - 2],
            );
            return result;
          }
          return businessMap(
            await live.command(
              euerPendingKey,
              '$euerPath/confirm',
              command,
              validateResult: euerReceiptValidator(command, preview),
            ),
          );
        }

        Map<String, dynamic> cashPayload(
          Map<String, dynamic> source,
          String category,
        ) {
          final event = businessMap(source['event']),
              income = category == 'sales';
          return {
            'event_id': event['id'],
            'source_hash': source['source_hash'],
            'euer_date': event['cash_date'],
            'year_rule': {'kind': 'cash'},
            'lines': [
              for (final unit in businessItems(source['units']))
                {
                  'unit_id': unit['unit_id'],
                  'category': category,
                  'business_net': unit['net'],
                  'deductible_net': income ? '0.00' : unit['net'],
                  'business_tax': unit['tax'],
                  'deductible_input_tax': income ? '0.00' : unit['tax'],
                  'deductible_tax_cost': '0.00',
                  'account': income ? '4400' : '5400',
                  'vat_account': income ? '3806' : '1406',
                },
            ],
          };
        }

        final saleEntry = await post(
          'cash',
          cashPayload(await source(sale['id']), 'sales'),
          lost: true,
        );
        Future<Map<String, dynamic>> receipt(
          String suffix,
          String net,
          String tax,
          String gross,
          String day,
        ) async {
          final record = businessMap(
            await live.command(
              'synthetic-receipt-$suffix',
              '/finance/receipts',
              {
                'project_id': hello['project_id'],
                'filename': 'synthetic-$suffix.pdf',
                'media_type': 'application/pdf',
                'original_base64': base64Encode(
                  utf8.encode('%PDF-1.4\nSynthetic Euer $suffix\n%%EOF'),
                ),
                'note': 'Synthetic original',
              },
            ),
          );
          return businessMap(
            await live.command(
              'synthetic-review-$suffix',
              '/finance/receipts/${record['id']}',
              {
                'revision': 0,
                'vendor': 'Synthetic supplier $suffix',
                'invoice_number': 'SYN-$suffix',
                'issue_date': day,
                'net': net,
                'tax': tax,
                'gross': gross,
                'currency': 'EUR',
                'status': 'reviewed',
                'note': 'Explicit synthetic original review',
              },
            ),
          );
        }

        Future<Map<String, dynamic>> vat(
          Map<String, dynamic> receipt,
          String amount,
          String day,
        ) async {
          final s = await source(receipt['id']);
          return post('input_vat', {
            'receipt_id': receipt['id'],
            'source_hash': s['source_hash'],
            'invoice_received_date': day,
            'service_date': day,
            'prepayment': false,
            'payment_event_id': null,
            'entitlement_date': day,
            'deductible_tax': amount,
            'account': '1406',
            'conditions_confirmed': true,
          });
        }

        final supplier = await receipt(
          'supplier',
          '50.00',
          '9.50',
          '59.50',
          '2026-11-01',
        );
        await vat(supplier, '9.50', '2026-11-01');
        final rs = businessItems(
          await live.read('/accounting/sources/receipts'),
        ).singleWhere((r) => r['receipt_id'] == supplier['id']);
        final payout = businessMap(
          await live.command('synthetic-payout', '/accounting/events/payout', {
            'receipt_id': rs['receipt_id'],
            'source_hash': rs['source_hash'],
            'review_revision': rs['review_revision'],
            'review_sha256': rs['review_sha256'],
            'original_sha256': rs['original_sha256'],
            'account_id': account['id'],
            'account_revision': 1,
            'expected_cash_revision': rs['cash_revision'],
            'amount': '59.50',
            'cash_date': '2026-11-02',
            'evidence_reference': 'SYN-OUT-5950',
            'reference': 'Synthetic paid supplier',
            'confirmation': true,
          }),
        );
        await components(payout);
        final costPayload = cashPayload(
          await source(payout['id']),
          'materials',
        );
        final cost = await post('cash', costPayload, wrong: true);
        var report = businessMap(await live.read('$euerPath/report?year=2026'));
        expect(report['totals']['confirmed_surplus'], '59.50');
        expect(report['totals']['confirmed_output_vat'], '19.00');
        expect(report['totals']['confirmed_input_vat'], '9.50');
        final tax = await receipt('tax', '9.50', '0.00', '9.50', '2026-11-03'),
            ts = await source(tax['id']);
        final external = await post('external_cash', {
          'receipt_id': tax['id'],
          'source_hash': ts['source_hash'],
          'account_id': account['id'],
          'account_revision': 1,
          'evidence_key': 'SYN-TAX-950',
          'cash_date': '2026-11-03',
          'amount': '9.50',
          'direction': 'out',
          'category': 'vat_payment',
          'euer_date': '2026-11-03',
          'year_rule': {'kind': 'cash'},
          'account': '3820',
        });
        report = businessMap(await live.read('$euerPath/report?year=2026'));
        expect(report['totals']['euer_surplus'], '50.00');
        final paymentEvidence = businessItems(
          await live.read('/accounting/sources/receipts'),
        ).singleWhere((row) => row['receipt_id'] == tax['id']);
        expect(paymentEvidence['source_role'], 'payment_evidence');
        expect(paymentEvidence['payable'], false);
        expect(paymentEvidence['paid_amount'], null);
        expect(paymentEvidence['remaining_amount'], null);
        expect(
          paymentEvidence['external_cash_binding']['active_entry_id'],
          isNotNull,
        );
        final correctedPayload =
            jsonDecode(jsonEncode(costPayload)) as Map<String, dynamic>;
        correctedPayload['lines'][0]['category'] = 'external_services';
        correctedPayload['lines'][0]['account'] = '5900';
        final corrected = await post('correct', {
          'entry_id': cost['id'],
          'operation': 'cash',
          'payload': correctedPayload,
        });
        expect(corrected['reverses'], cost['id']);
        expect(
          businessMap(
            await live.read('$euerPath/report?year=2026'),
          )['totals']['euer_surplus'],
          '50.00',
        );
        final closed = await post('period', {
          'period': '2026-11',
          'action': 'close',
          'expected_period_revision': 0,
          'attestation': {
            'bank_reconciled': true,
            'originals_complete': true,
            'special_cases_reviewed': true,
          },
        });
        expect(closed['control']['report']['period'], '2026-11');
        await expectLater(
          post('reverse', {'entry_id': saleEntry['id']}),
          throwsA(isA<ApiException>().having((e) => e.status, 'status', 409)),
        );
        await post('period', {
          'period': '2026-11',
          'action': 'reopen',
          'expected_period_revision': 1,
          'attestation': {
            'bank_reconciled': false,
            'originals_complete': false,
            'special_cases_reviewed': false,
          },
        });
        final assetReceipt = await receipt(
          'asset',
          '1200.00',
          '228.00',
          '1428.00',
          '2026-12-01',
        );
        await vat(assetReceipt, '228.00', '2026-12-01');
        final assetSource = await source(assetReceipt['id']);
        final asset = await post('asset', {
          'receipt_id': assetReceipt['id'],
          'source_hash': assetSource['source_hash'],
          'description': 'Synthetic new asset',
          'business_basis': '1200.00',
          'use_start': '2026-12-01',
          'life_months': 36,
          'account': '0670',
        });
        final depreciation = await post('depreciation', {
          'asset_entry_id': asset['id'],
          'year': 2026,
          'account': '6220',
        });
        expect(depreciation['effect']['details']['amount'], '33.33');
        final exported = await post('export', {'year': 2026});
        final frozen = await live.read('$euerPath/exports/${exported['id']}');
        expect(frozen['report']['totals']['euer_surplus'], '16.67');
        expect(frozen['official_tax_return'], false);
        expect(frozen['datev_certified'], false);
        expect(frozen['csv'], contains('5900'));
        final jsonFile = await euerExportAttachment(
          businessMap(frozen),
          exported,
          csv: false,
        );
        final csvFile = await euerExportAttachment(
          businessMap(frozen),
          exported,
          csv: true,
        );
        expect(jsonDecode(utf8.decode(jsonFile.bytes)), frozen);
        expect(utf8.decode(csvFile.bytes), frozen['csv']);
        await expectLater(
          euerExportAttachment(
            {...businessMap(frozen), 'csv': 'tampered'},
            exported,
            csv: true,
          ),
          throwsA(isA<ApiException>()),
        );
        await post('reverse', {'entry_id': corrected['id']});
        await post('reverse', {'entry_id': external['id']});
        final reversedEvidence = businessItems(
          await live.read('$euerPath/sources'),
        ).singleWhere((row) => row['id'] == tax['id']);
        expect(reversedEvidence['source_role'], 'payment_evidence');
        expect(
          reversedEvidence['reasons'],
          contains('external_cash_classification_missing'),
        );
        expect(
          reversedEvidence['reasons'],
          isNot(contains('input_vat_decision_missing')),
        );
        report = businessMap(await live.read('$euerPath/report?year=2026'));
        expect(report['complete_for_recorded_sources'], false);
        expect(report['totals']['euer_surplus'], null);
        expect(await live.read('$euerPath/exports/${exported['id']}'), frozen);
        final history = businessItems(await live.read('$euerPath/journal'));
        expect(history.singleWhere((e) => e['id'] == cost['id']), cost);
        expect(await live.read('/accounting/events/${payout['id']}'), payout);
      }, BackendHttp());
    } catch (e, stack) {
      Error.throwWithStackTrace(
        StateError('$e\nLast request: ${api?.last}\n$diagnostic'),
        stack,
      );
    } finally {
      session?.dispose();
      api?.dispose();
      server?.kill();
      if (server != null)
        await server.exitCode.timeout(
          const Duration(seconds: 10),
          onTimeout: () => -1,
        );
      await output?.cancel();
      await errors?.cancel();
      await directory.delete(recursive: true);
    }
  }, timeout: const Timeout(Duration(minutes: 3)));
}

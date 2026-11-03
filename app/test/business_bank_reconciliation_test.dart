import 'dart:convert';
import 'dart:io';
import 'dart:typed_data';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:smartplan_office/api.dart';
import 'package:smartplan_office/business_session.dart';
import 'package:smartplan_office/business_bank_reconciliation.dart';

final f = jsonDecode(
  File('test/fixtures/bank_reconciliation.json').readAsStringSync(),
) as Map<String, dynamic>;
Map<String, dynamic> copy(dynamic value) =>
    Map<String, dynamic>.from(jsonDecode(jsonEncode(value)) as Map);

class BankApi extends OfficeApi {
  BankApi() : super(apiVersion: 'v1') {
    token = 'synthetic-bank-client';
  }
  bool read = true,
      write = true,
      admin = true,
      lose = false,
      wrongTransaction = false;
  int revision = 1;
  final posts = <Map<String, dynamic>>[];
  @override
  Future<dynamic> call(String path, [Map<String, dynamic>? body]) async {
    if (path.startsWith('/api/business/capabilities'))
      return {
        'compatibility_mode': 'business',
        'generation': 1,
        'storage_version': 10,
        'readonly': false,
        'features': ['bank_reconciliation'],
        'capabilities': ['business_bank_reconciliation'],
        'permissions': [
          if (read) 'bank.read',
          'accounting.read',
          'finance.read',
          if (write) 'bank.prepare',
          'accounting.prepare',
          'finance.write',
          if (admin) ...['bank.admin', 'accounting.admin'],
        ],
      };
    if (path == '/api/business/bank/accounts' && body == null) {
      final page = copy(f['accounts']);
      page['items'][0]['revision'] = revision;
      page['available_accounts'][0]['revision'] = revision;
      return page;
    }
    if (path.endsWith('/candidates')) {
      final page = copy(f['candidates']);
      if (wrongTransaction) page['transaction']['id'] = 'f' * 32;
      return page;
    }
    if (path.startsWith('/api/business/bank/statements?'))
      return {'items': [], 'next_offset': null};
    if (path.startsWith('/api/business/bank/reconciliations?'))
      return {'items': [], 'next_offset': null};
    if (body != null) {
      posts.add(copy(body));
      if (lose) {
        lose = false;
        throw const ApiException(0, 'Synthetic accepted reply lost');
      }
      if (path.endsWith('/matches')) return copy(f['match']);
      if (path.endsWith('/accounts')) return copy(f['binding']);
      return copy(f['statement']);
    }
    throw StateError(path);
  }
}

Future<BusinessSession> session(BankApi api) async {
  final s = BusinessSession(api: api);
  await s.load();
  return s;
}

void main() {
  test(
    'exact bank cents reject rounding, implicit zeros and unrequested signs',
    () {
      expect(bankMoney('00119,1'), '119.10');
      expect(bankMoney('-18,71', signed: true), '-18.71');
      expect(bankMoney('-0.00', signed: true), '0.00');
      for (final v in ['', '1e2', '1.005', '-1'])
        expect(() => bankMoney(v), throwsA(isA<ApiException>()));
      expect(
        () => bankMoney('0', positive: true),
        throwsA(isA<ApiException>()),
      );
    },
  );
  test('original preview and ACK bind exact file metadata and all normalized bank rows', () {
    bankImportPreview(
      f['preview'],
      copy(f['body']),
      f['preview']['metadata']['file_sha256'],
    );
    final validate = bankReceipt('import', copy(f['body']), copy(f['preview']));
    validate(f['statement']);
    final wrong = copy(f['statement']);
    wrong['lines'][0]['transaction']['payload']['amount'] = '120.00';
    expect(() => validate(wrong), throwsA(isA<ApiException>()));
    expect(
      () => validate({...copy(f['statement']), 'lines': []}),
      throwsA(isA<ApiException>()),
    );
    expect(
      () => bankImportPreview(f['preview'], copy(f['body']), 'f' * 64),
      throwsA(isA<ApiException>()),
    );
  });
  test(
    'lookalike evidence is explicitly included only after new bound preview',
    () {
      final preview = copy(f['preview']);
      preview['metadata']['distinct_transaction_confirmations'] = {
        'OTHER': 'Two documented distinct original transactions',
      };
      expect(
        () => bankImportPreview(
          preview,
          copy(f['body']),
          preview['metadata']['file_sha256'],
        ),
        throwsA(isA<ApiException>()),
      );
      bankImportPreview(preview, {
        ...copy(f['body']),
        'distinct_transaction_confirmations':
            preview['metadata']['distinct_transaction_confirmations'],
      }, preview['metadata']['file_sha256']);
    },
  );
  test('explicit partial match requires current source and date justification without changing cash date', () {
    final values = {'amount_0': '119.00', 'reason': f['match_body']['reason']};
    expect(
      bankMatchInput(
        copy(f['candidates']),
        values,
        businessItems(f['candidates']['items']),
      ),
      f['match_body'],
    );
    expect(
      () => bankMatchInput(copy(f['candidates']), {
        ...values,
        'amount_0': '',
      }, businessItems(f['candidates']['items'])),
      throwsA(isA<ApiException>()),
    );
    final page = copy(f['candidates']);
    page['transaction']['payload']['booking_date'] = '2026-11-03';
    expect(
      () => bankMatchInput(page, values, businessItems(page['items'])),
      throwsA(isA<ApiException>()),
    );
    expect(
      bankMatchInput(page, {
        ...values,
        'date_reason_0': 'Original order the prior day',
      }, businessItems(page['items']))['links'][0]['amount'],
      '119.00',
    );
    expect(
      bankMatchInput(page, {'reason': 'Explicit removal'}, [])['links'],
      isEmpty,
    );
  });
  test('stored nested account match report receipts cannot change original reviewed sources', () {
    bankReceipt('account', copy(f['account_body']), null)(f['binding']);
    bankMatchPreview(
      f['match_preview'],
      copy(f['match_body']),
      f['candidates']['transaction']['id'],
    );
    bankReceipt('match', copy(f['match_body']), copy(f['match_preview']))(
      f['match'],
    );
    bankReportPreview(f['report_preview'], copy(f['report_body']));
    final validate = bankReceipt(
      'report',
      copy(f['report_body']),
      copy(f['report_preview']),
    );
    validate(f['report']);
    final bad = copy(f['report']);
    bad['record']['payload']['complete'] = false;
    expect(() => validate(bad), throwsA(isA<ApiException>()));
  });
  test(
    'archived charset parameters are normalized for exact native media check',
    () {
      expect(
        bankExportMediaType('json', copy(f['report']['exports']['json'])),
        'application/json',
      );
      expect(
        bankExportMediaType('csv', copy(f['report']['exports']['csv'])),
        'text/csv',
      );
      expect(
        () => bankExportMediaType('pdf', copy(f['report']['exports']['json'])),
        throwsA(isA<ApiException>()),
      );
    },
  );
  test(
    'historical exports require complete digest size and exact JSON envelope',
    () async {
      final bytes = Uint8List.fromList(
            utf8.encode(jsonEncode(f['report']['record'])),
          ),
          manifest = {'size': bytes.length, 'sha256': await bankDigest(bytes)};
      await bankVerifyBytes(
        bytes,
        manifest,
        event: copy(f['report']['record']),
      );
      await expectLater(
        bankVerifyBytes(bytes.sublist(1), manifest),
        throwsA(isA<ApiException>()),
      );
      await expectLater(
        bankVerifyBytes(bytes, manifest, event: copy(f['match'])),
        throwsA(isA<ApiException>()),
      );
    },
  );
  test('native lost import ACK keeps nonce body and neutral key through bank grant removal and later revisions', () async {
    final api = BankApi(),
        s = await session(api),
        key = 'bank-import-${'a' * 32}',
        body = {
          ...copy(f['body']),
          'confirmation': true,
          'preview_hash': f['preview']['preview_hash'],
        };
    api.lose = true;
    await expectLater(
      s.command(
        key,
        '/bank/statements',
        body,
        validateResult: bankReceipt('import', body, copy(f['preview'])),
      ),
      throwsA(isA<ApiException>()),
    );
    expect(s.pendingBankKeys, [key]);
    api.write = false;
    await expectLater(s.repeatBankCommand(key), throwsA(isA<ApiException>()));
    expect(api.posts, hasLength(1));
    expect(s.pending(key), true);
    api.write = true;
    api.revision = 99;
    await s.repeatBankCommand(key);
    expect(api.posts[0], api.posts[1]);
    expect(s.pendingBankKeys, isEmpty);
    s.dispose();
  });
  test(
    'native match replay checks transaction binding before any repeated POST',
    () async {
      final api = BankApi(),
          s = await session(api),
          id = f['candidates']['transaction']['id'],
          key = 'bank-match-$id',
          body = {
            ...copy(f['match_body']),
            'confirmation': true,
            'preview_hash': f['match_preview']['preview_hash'],
          };
      api.lose = true;
      await expectLater(
        s.command(
          key,
          '/bank/transactions/$id/matches',
          body,
          validateResult: bankReceipt('match', body, copy(f['match_preview'])),
        ),
        throwsA(isA<ApiException>()),
      );
      api.wrongTransaction = true;
      await expectLater(s.repeatBankCommand(key), throwsA(isA<ApiException>()));
      expect(api.posts, hasLength(1));
      api.wrongTransaction = false;
      await s.repeatBankCommand(key);
      expect(api.posts[0], api.posts[1]);
      s.dispose();
    },
  );
  testWidgets(
    '390px private bank view clears IBAN and pending content when bank read is revoked',
    (tester) async {
      tester.view.physicalSize = const Size(390, 844);
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.resetPhysicalSize);
      addTearDown(tester.view.resetDevicePixelRatio);
      final api = BankApi(), s = await session(api);
      await tester.pumpWidget(
        MaterialApp(home: BusinessBankReconciliationPage(session: s)),
      );
      await tester.pumpAndSettle();
      expect(find.textContaining('DE89370400440532013000'), findsOneWidget);
      expect(tester.takeException(), isNull);
      api.read = false;
      await s.load();
      await tester.pumpAndSettle();
      expect(find.textContaining('DE89370400440532013000'), findsNothing);
      expect(find.text('Bankdaten nicht freigegeben'), findsOneWidget);
      await tester.pumpWidget(const SizedBox.shrink());
      s.dispose();
    },
  );
  testWidgets(
    'bank binding defaults all factual choices empty and activation unconfirmed',
    (tester) async {
      final api = BankApi(), s = await session(api);
      await tester.pumpWidget(
        MaterialApp(home: BusinessBankReconciliationPage(session: s)),
      );
      await tester.pumpAndSettle();
      await tester.tap(find.text('Vorhandenes Geldkonto mit Bank verbinden'));
      await tester.pumpAndSettle();
      expect(
        tester.widget<SwitchListTile>(find.byType(SwitchListTile)).value,
        false,
      );
      final fields = tester
          .widgetList<TextFormField>(find.byType(TextFormField))
          .toList();
      expect(
        fields.where((v) => v.controller?.text.isNotEmpty == true),
        isEmpty,
      );
      api.read = false;
      await s.load();
      await tester.pumpAndSettle();
      expect(find.text('IBAN'), findsNothing);
      await tester.pumpWidget(const SizedBox.shrink());
      s.dispose();
    },
  );
}

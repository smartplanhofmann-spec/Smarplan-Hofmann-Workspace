import 'dart:convert';
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:smartplan_office/api.dart';
import 'package:smartplan_office/business_bank_camt_contract.dart';
import 'package:smartplan_office/business_bank_reconciliation.dart';
import 'package:smartplan_office/business_session.dart';

import 'business_bank_reconciliation_test.dart' as legacy;

final camtFixture = jsonDecode(
  File('test/fixtures/bank_camt.json').readAsStringSync(),
) as Map<String, dynamic>;
Map<String, dynamic> camtCopy(dynamic value) =>
    Map<String, dynamic>.from(jsonDecode(jsonEncode(value)) as Map);

class CamtApi extends legacy.BankApi {
  bool xmlAllowed = true;
  final paths = <String>[];
  @override
  Future<dynamic> call(String path, [Map<String, dynamic>? body]) async {
    if (path.startsWith('/api/business/capabilities')) {
      final caps = Map<String, dynamic>.from(await super.call(path, body));
      caps['features'] = [
        'bank_reconciliation',
        if (xmlAllowed) 'bank_camt_v1',
      ];
      return caps;
    }
    if (path == '/api/business/bank/accounts' && body == null)
      return {
        'items': [camtCopy(camtFixture['preview']['metadata']['bank'])],
        'available_accounts': [
          camtCopy(camtFixture['preview']['metadata']['account']),
        ],
        'external_connection': false,
      };
    if (path == '/api/business/bank/camt/inspect')
      return camtCopy(camtFixture['inspection']);
    if (path == '/api/business/bank/camt/preview')
      return camtCopy(camtFixture['preview']);
    if (path == '/api/business/bank/camt/statements' && body != null) {
      paths.add(path);
      posts.add(camtCopy(body));
      if (lose) {
        lose = false;
        throw const ApiException(0, 'Synthetic accepted XML reply lost');
      }
      return camtCopy(camtFixture['receipt']);
    }
    if (path ==
        '/api/business/bank/statements/${camtFixture['receipt']['statement']['id']}')
      return camtCopy(camtFixture['statement']);
    return super.call(path, body);
  }
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  test('actual XML bank fixture passes native metadata and canonical preview binding', () async {
    final original = camtCopy(camtFixture);
    expect(
      bankCamtMetadata(camtFixture['receipt']['statement']['payload']),
      camtFixture['preview']['metadata'],
    );
    expect(
      await bankCamtPreviewHash(camtFixture['preview']),
      camtFixture['preview'],
    );
    expect(
      await bankCamtInspection(
        camtFixture['inspection'],
        camtCopy(camtFixture['request']),
        camtFixture['inspection']['original_sha256'],
      ),
      camtFixture['inspection'],
    );
    expect(camtFixture, original);
    expect(
      bankImportPreview(
        camtFixture['preview'],
        camtCopy(camtFixture['body']),
        camtFixture['inspection']['original_sha256'],
      ),
      camtFixture['preview'],
    );
    expect(
      () => bankReceipt(
        'import',
        camtCopy(camtFixture['command']),
        camtCopy(camtFixture['preview']),
      )(camtFixture['receipt']),
      returnsNormally,
    );
  });
  test('canonical sorting follows Unicode scalar order and preserves negative integers', () {
    final privateUse = String.fromCharCode(0xe000);
    expect(
      bankCamtCanonical({'😀': 1, privateUse: -2}),
      '{"$privateUse":-2,"😀":1}',
    );
  });
  test(
    'unknown schemas versions namespaces and formats cannot select a new rule',
    () {
      for (final mutation in <void Function(Map<String, dynamic>)>[
        (m) => m['contract'] = 'unknown',
        (m) => m['delimiter'] = ';',
        (m) => m['camt']['namespace'] = 'urn:unknown',
        (m) => m['camt']['schema_sha256'] = '0' * 64,
      ]) {
        final meta = camtCopy(camtFixture['preview']['metadata']);
        mutation(meta);
        expect(() => bankCamtMetadata(meta), throwsA(isA<ApiException>()));
      }
    },
  );
  test(
    'altered rows and balances cannot reuse the actual server preview hash',
    () async {
      final p = camtCopy(camtFixture['preview']);
      p['metadata']['rows'][0]['amount'] = '125.01';
      p['metadata']['closing_balance'] = '200.01';
      p['total'] = '100.01';
      bankCamtMetadata(p['metadata']);
      await expectLater(bankCamtPreviewHash(p), throwsA(isA<ApiException>()));
    },
  );
  test('unknown original fields or entry fields are not ignored', () {
    for (final mutation in <void Function(Map<String, dynamic>)>[
      (m) => m['extra'] = true,
      (m) => m['camt']['extra'] = true,
      (m) => m['rows'][0]['tax_guess'] = '19',
      (m) => m['camt']['entry_sources'][0]['ignore_reference'] = true,
    ]) {
      final meta = camtCopy(camtFixture['preview']['metadata']);
      mutation(meta);
      expect(() => bankCamtMetadata(meta), throwsA(isA<ApiException>()));
    }
  });
  test(
    'account original and explicit review are all required for inspection',
    () async {
      for (final change in [
        {'original_sha256': '0' * 64},
        {'financial_changes': true},
        {'confirmation_required': false},
        {'schema_version': 2},
      ]) {
        final value = {...camtCopy(camtFixture['inspection']), ...change};
        await expectLater(
          bankCamtInspection(
            value,
            camtCopy(camtFixture['request']),
            camtFixture['inspection']['original_sha256'],
          ),
          throwsA(isA<ApiException>()),
        );
      }
      await expectLater(
        bankCamtInspection(camtFixture['inspection'], {
          ...camtCopy(camtFixture['request']),
          'account_id': 'b' * 32,
        }, camtFixture['inspection']['original_sha256']),
        throwsA(isA<ApiException>()),
      );
    },
  );
  test('duplicates fractional cents and unexpected payment directions are rejected', () {
    for (final mutation in <void Function(Map<String, dynamic>)>[
      (m) => m['rows'][1]['transaction_id'] = m['rows'][0]['transaction_id'],
      (m) => m['rows'][0]['amount'] = '125.001',
      (m) => m['rows'][1]['amount'] = '25.00',
      (m) => m['rows'][0]['currency'] = 'USD',
    ]) {
      final meta = camtCopy(camtFixture['preview']['metadata']);
      mutation(meta);
      expect(() => bankCamtMetadata(meta), throwsA(isA<ApiException>()));
    }
  });
  test('all entry ordinals and stable bank references are original bound', () {
    for (final mutation in <void Function(Map<String, dynamic>)>[
      (m) => m['camt']['entry_sources'].removeLast(),
      (m) => m['camt']['entry_sources'][0]['line_number'] = 2,
      (m) => m['camt']['entry_sources'][0]['bank_reference'] = 'other',
      (m) => m['camt']['file_sha256'] = '0' * 64,
    ]) {
      final meta = camtCopy(camtFixture['preview']['metadata']);
      mutation(meta);
      expect(() => bankCamtMetadata(meta), throwsA(isA<ApiException>()));
    }
  });
  test(
    'lost XML import reply keeps its original nonce through feature withdrawal',
    () async {
      final api = CamtApi();
      final s = BusinessSession(api: api);
      await s.load();
      addTearDown(() {
        s.dispose();
        api.dispose();
      });
      final body = camtCopy(camtFixture['command']),
          proof = camtCopy(camtFixture['preview']);
      final key = 'bank-import-${'a' * 32}';
      api.lose = true;
      await expectLater(
        s.command(
          key,
          '/bank/camt/statements',
          body,
          validateResult: bankReceipt('import', body, proof),
        ),
        throwsA(isA<ApiException>()),
      );
      expect(s.pending(key), true);
      api.xmlAllowed = false;
      await expectLater(s.repeatBankCommand(key), throwsA(isA<ApiException>()));
      expect(api.posts, hasLength(1));
      expect(s.pending(key), true);
      api.xmlAllowed = true;
      expect(await s.repeatBankCommand(key), camtFixture['receipt']);
      expect(api.paths, everyElement('/api/business/bank/camt/statements'));
      expect(api.posts, hasLength(2));
      expect(api.posts.first, api.posts.last);
      expect(s.pending(key), false);
    },
  );
}

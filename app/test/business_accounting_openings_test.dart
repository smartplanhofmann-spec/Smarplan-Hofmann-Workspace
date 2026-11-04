import 'dart:convert';
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:smartplan_office/api.dart';
import 'package:smartplan_office/business_accounting_openings.dart';
import 'package:smartplan_office/business_session.dart';

final openingFixture = jsonDecode(
  File('test/fixtures/accounting_openings_2026.json').readAsStringSync(),
) as Map<String, dynamic>;
Map<String, dynamic> copyOpening(dynamic value) =>
    Map<String, dynamic>.from(jsonDecode(jsonEncode(value)) as Map);
Map<String, dynamic> openingBody(dynamic value) =>
    copyOpening(value)..remove('request_id');

class OpeningApi extends OfficeApi {
  OpeningApi() : super(apiVersion: 'v1') {
    token = 'synthetic-opening-client';
  }
  bool read = true, write = true, lose = false, wrong = false;
  int generation = 1;
  final posts = <Map<String, dynamic>>[];
  @override
  Future<dynamic> call(String path, [Map<String, dynamic>? body]) async {
    final f = openingFixture;
    if (path.endsWith('/capabilities'))
      return {
        'compatibility_mode': 'business',
        'generation': generation,
        'storage_version': 10,
        'readonly': false,
        'features': ['accounting_opening_balances'],
        'capabilities': ['business_accounting_openings'],
        'permissions': [
          'accounting.read',
          'finance.read',
          if (read) 'bank.read',
          if (write) ...[
            'accounting.admin',
            'accounting.prepare',
            'finance.write',
          ],
        ],
      };
    if (path == '/api/business$openingPath')
      return copyOpening(f['state_after']);
    if (body != null) {
      posts.add(copyOpening(body));
      if (lose) {
        lose = false;
        throw const ApiException(0, 'Synthetic accepted response lost');
      }
      return copyOpening(wrong ? f['correction'] : f['saved']);
    }
    throw StateError('Unexpected route: $path');
  }
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  test('actual opening originals, sources, previews, receipts and bank-negative balances validate unchanged', () {
    final f = openingFixture;
    for (final scenario in [f, f['bank']]) {
      final state = openingState(scenario['state_before']);
      openingSources(
        scenario['sources'],
        state,
        scenario['preview_request']['account_id'],
      );
      openingPreview(
        scenario['preview'],
        copyOpening(scenario['preview_request']),
      );
      openingReceipt(copyOpening(scenario['preview']))(scenario['saved']);
      openingState(scenario['state_after']);
      openingLiquidity(scenario['liquidity'], scenario['liquidity']['as_of']);
    }
    openingHistory(f['history_after_void'], f['saved']['account_id']);
    openingLiquidity(
      f['corrected_liquidity'],
      f['corrected_liquidity']['as_of'],
    );
    openingLiquidity(f['void_liquidity'], f['void_liquidity']['as_of']);
    expect(f['void_liquidity']['known_balance_sum'], null);
    final bytes = base64Decode(f['original_upload']['content_base64']);
    openingOriginalReceipt(openingBody(f['original_upload']))(f['original']);
    openingVerifyBytes(bytes, copyOpening(f['original']));
    bytes[15] ^= 1;
    expect(
      () => openingVerifyBytes(bytes, copyOpening(f['original'])),
      throwsA(isA<ApiException>()),
    );
  });
  test('exact input distinguishes explicit zero, absent amount and negative bank balances', () {
    expect(openingAmount('0'), '0.00');
    expect(openingAmount('-100,5'), '-100.50');
    expect(
      openingAggregateCents('9007199254740993.01'),
      BigInt.parse('900719925474099301'),
    );
    expect(
      () => openingAmount('100000000118.99'),
      throwsA(isA<ApiException>()),
    );
    for (final value in ['-0.00', '00.00', '1.0', '1e3']) {
      expect(() => openingAggregateCents(value), throwsA(isA<ApiException>()));
    }
    for (final value in ['', '-0.00', '1.001', '1e3', '1.000,00', 'NaN']) {
      expect(() => openingAmount(value), throwsA(isA<ApiException>()));
    }
    expect(() => openingDate('2026-02-30'), throwsA(isA<ApiException>()));
  });
  test('foreign source, historical ACK, unexpected cash effects and false complete liquidity are rejected', () {
    final f = openingFixture;
    for (final change in <void Function(Map<String, dynamic>)>[
      (v) => v['account_id'] = 'f' * 32,
      (v) => v['amount'] = '9999.00',
      (v) => v['source']['sha256'] = '0' * 64,
      (v) => v['cash_flow_created'] = true,
      (v) => v['tax_postings_created'] = true,
      (v) => v['timezone'] = 'UTC',
      (v) => v['profile_ref']['revision']++,
      (v) => v['source_proof']['original']['account_id'] = 'f' * 32,
      (v) => v['future_private_source'] = {},
    ]) {
      final bad = copyOpening(f['preview']);
      change(bad);
      expect(
        () => openingPreview(bad, copyOpening(f['preview_request'])),
        throwsA(isA<ApiException>()),
      );
    }
    expect(
      () => openingReceipt(copyOpening(f['preview']))(f['correction']),
      throwsA(isA<ApiException>()),
    );
    final foreign = copyOpening(f['sources']);
    foreign['account']['id'] = 'f' * 32;
    expect(
      () => openingSources(
        foreign,
        copyOpening(f['state_before']),
        f['saved']['account_id'],
      ),
      throwsA(isA<ApiException>()),
    );
    for (final change in <void Function(Map<String, dynamic>)>[
      (v) => v['balance_total'] = '0.00',
      (v) => v['known_balance_sum'] = '0.00',
      (v) => v['complete_for_recorded_accounts'] = true,
      (v) => v['known_account_count'] = 1,
      (v) => v['accounts'][0]['balance'] = '0.00',
    ]) {
      final bad = copyOpening(f['void_liquidity']);
      change(bad);
      expect(
        () => openingLiquidity(bad, bad['as_of']),
        throwsA(isA<ApiException>()),
      );
    }
  });
  test('unknown accepted command keeps original nonce and validator across changed generation, rights withdrawal and retry', () async {
    final api = OpeningApi();
    final session = BusinessSession(api: api);
    await session.load();
    addTearDown(session.dispose);
    api.lose = true;
    final body = openingBody(openingFixture['command']);
    await expectLater(
      session.command(
        'accounting-opening-confirm',
        '$openingPath/confirm',
        body,
        validateResult: openingReceipt(copyOpening(openingFixture['preview'])),
      ),
      throwsA(isA<ApiException>()),
    );
    expect(session.pendingOpeningKeys, ['accounting-opening-confirm']);
    api.write = false;
    api.generation = 2;
    await expectLater(
      session.repeatOpeningCommand('accounting-opening-confirm'),
      throwsA(isA<ApiException>()),
    );
    expect(api.posts.length, 1);
    api.write = true;
    api.wrong = true;
    await expectLater(
      session.repeatOpeningCommand('accounting-opening-confirm'),
      throwsA(isA<ApiException>()),
    );
    expect(session.pendingOpeningKeys, isNotEmpty);
    api.wrong = false;
    await session.repeatOpeningCommand('accounting-opening-confirm');
    expect(api.posts[0], api.posts[1]);
    expect(api.posts[1], api.posts[2]);
    expect(session.pendingOpeningKeys, isEmpty);
  });
  test('bank boundary claims cannot agree while disagreeing with recorded movements', () {
    final f = openingFixture;
    final changed = copyOpening(f['bank']['liquidity']);
    changed['accounts'][0]['bank_connections'][0]['recorded_balance'] =
        '-99.00';
    changed['accounts'][0]['bank_connections'][0]['statement_balance'] =
        '-99.00';
    expect(
      () => openingLiquidity(changed, changed['as_of']),
      throwsA(isA<ApiException>()),
    );
    final duplicate = copyOpening(f['bank']['liquidity']);
    duplicate['accounts'][0]['bank_connections'].add(
      copyOpening(duplicate['accounts'][0]['bank_connections'][0]),
    );
    expect(
      () => openingLiquidity(duplicate, duplicate['as_of']),
      throwsA(isA<ApiException>()),
    );
  });
  test('negative calculated cash remains explicitly unresolved without confirmed total', () {
    final value = copyOpening(openingFixture['liquidity']),
        row = value['accounts'][0];
    row['account']['kind'] = 'cash';
    for (final m in row['movements']) {
      m['account']['kind'] = 'cash';
      if (m['direction'] == 'out') m['amount'] = '2000.00';
    }
    row['outflows'] = '2000.00';
    row['calculated_balance'] = '-881.00';
    row['balance'] = '-881.00';
    value['balance_total'] = '-881.00';
    value['known_balance_sum'] = '-881.00';
    expect(
      () => openingLiquidity(value, value['as_of']),
      throwsA(isA<ApiException>()),
    );
    row['issues'] = [
      {'code': 'cash_balance_negative'},
    ];
    row['balance'] = null;
    value['balance_total'] = null;
    value['known_balance_sum'] = null;
    value['known_account_count'] = 0;
    value['complete_for_recorded_accounts'] = false;
    openingLiquidity(value, value['as_of']);
  });

  test('actual large positive and negative balances preserve every aggregate cent while single-input limits remain unchanged', () {
    final large = jsonDecode(
      File('test/fixtures/accounting_openings_large_balances_2026.json')
          .readAsStringSync(),
    ) as Map<String, dynamic>;
    for (final key in ['positive', 'negative']) {
      final scenario = large[key];
      openingState(scenario['state']);
      final result = openingLiquidity(
        scenario['liquidity'],
        scenario['liquidity']['as_of'],
      );
      expect(
        result['balance_total'],
        key == 'positive' ? '100000000118.99' : '-100000000059.49',
      );
      expect(result['known_balance_sum'], result['balance_total']);
      if (key == 'positive') {
        final forged = copyOpening(result), row = forged['accounts'][0];
        row['movements'][0]['amount'] = '100000000000.00';
        row['inflows'] = '100000000000.00';
        row['calculated_balance'] = row['balance'] = '199999999999.99';
        forged['known_balance_sum'] = forged['balance_total'] =
            '199999999999.99';
        expect(
          () => openingLiquidity(forged, forged['as_of']),
          throwsA(isA<ApiException>()),
        );
      }
      expect(result['complete_for_recorded_accounts'], true);
      expect(
        () => openingAmount(result['balance_total']),
        throwsA(isA<ApiException>()),
      );
      expect(
        openingAmount(scenario['saved']['amount']),
        scenario['saved']['amount'],
      );
      final wrong = copyOpening(result);
      wrong['balance_total'] = key == 'positive'
          ? '100000000119.00'
          : '-100000000059.50';
      expect(
        () => openingLiquidity(wrong, wrong['as_of']),
        throwsA(isA<ApiException>()),
      );
    }
  });
}

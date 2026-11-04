import 'dart:convert';
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:smartplan_office/api.dart';
import 'package:smartplan_office/business_accounting_historical_assets_contract.dart';

final historicalFixture = jsonDecode(
  File('test/fixtures/accounting_historical_assets_2026.json')
      .readAsStringSync(),
) as Map<String, dynamic>;
Map<String, dynamic> historicalCopy(dynamic v) =>
    Map<String, dynamic>.from(jsonDecode(jsonEncode(v)) as Map);
void main() {
  test('actual historical original, source, immutable receipts, correction, void, EÜR and under-year fixtures validate', () {
    for (final f in [historicalFixture, historicalFixture['under_year']]) {
      historicalAssetIdentity(
        f['identity'],
        f['identity_request']['inventory_number'],
      );
      for (final key in [
        'state_before_upload',
        'state_before',
        'state_after',
        'state_after_correction',
        'state_after_void',
      ]) {
        historicalAssetState(f[key]);
      }
      historicalAssetOriginalReceipt(historicalCopy(f['original_upload']))(
        f['original'],
      );
      historicalAssetPreview(
        f['preview'],
        historicalCopy(f['preview_request']),
      );
      historicalAssetReceipt(historicalCopy(f['preview']))(f['saved']);
      historicalAssetEvent(f['correction']);
      historicalAssetEvent(f['void']);
      historicalAssetHistory(f['history_after_void'], f['saved']['asset_key']);
      historicalAssetEuerPreview(
        f['depreciation_preview'],
        historicalCopy(f['depreciation_preview_request']),
      );
      historicalAssetEuerReceipt(historicalCopy(f['depreciation_preview']))(
        f['depreciation'],
      );
      historicalAssetReport(f['euer_report_before']);
      historicalAssetReport(f['euer_report_after']);
      historicalAssetReport(f['euer_report_void']);
    }
  });
  test('receipt, profile, source, annual quota and unexpected cash/tax effects cannot be substituted', () {
    final f = historicalFixture;
    for (final mutate in <void Function(Map<String, dynamic>)>[
      (v) => v['asset']['cost_basis'] = '3600.01',
      (v) => v['source']['sha256'] = '0' * 64,
      (v) => v['source_proof']['original']['asset_key'] = 'foreign',
      (v) => v['start_year']['amount'] = '1199.99',
      (v) => v['profile_ref']['revision']++,
      (v) => v['tax_postings_created'] = true,
      (v) => v['cash_flow_created'] = true,
      (v) => v['future_fields'] = {},
    ]) {
      final bad = historicalCopy(f['preview']);
      mutate(bad);
      expect(
        () => historicalAssetPreview(bad, historicalCopy(f['preview_request'])),
        throwsA(isA<ApiException>()),
      );
    }
    expect(
      () =>
          historicalAssetReceipt(historicalCopy(f['preview']))(f['correction']),
      throwsA(isA<ApiException>()),
    );
    final bad = historicalCopy(f['depreciation_preview']);
    bad['postings'][0]['amount'] = '-1200.01';
    bad['preview_hash'] = historicalAssetHash({...bad}..remove('preview_hash'));
    expect(
      () => historicalAssetEuerPreview(
        bad,
        historicalCopy(f['depreciation_preview_request']),
      ),
      throwsA(isA<ApiException>()),
    );
  });
  test('old-month shift, unsupported methods, fake prior AfA, missing zeros and over-limit individual money fail before preview', () {
    for (final change in <void Function(Map<String, dynamic>)>[
      (v) => v['acquired_on'] = '2023-12-31',
      (v) => v['method'] = 'degressive',
      (v) => v['depreciation_before_start_year'] = '2399.99',
      (v) => v['depreciation_in_start_year'] = null,
      (v) => v['unchanged_linear_history_confirmed'] = false,
      (v) => v['description'] = 'x' * 301,
      (v) {
        v['acquired_on'] = '1899-01-01';
        v['use_start'] = '1899-01-01';
        v['depreciation_before_start_year'] = '3600.00';
        v['opening_book_value'] = '0.00';
      },
    ]) {
      final bad = historicalCopy(historicalFixture['saved']['asset']);
      change(bad);
      expect(
        () => historicalAssetData(bad, '2026-01-01'),
        throwsA(isA<ApiException>()),
      );
    }
    expect(historicalAssetAmount('0'), '0.00');
    expect(historicalAssetAmount('99999999999,99'), '99999999999.99');
    for (final v in ['', '-1', '100000000000.00', '1e3', '1.001']) {
      expect(() => historicalAssetAmount(v), throwsA(isA<ApiException>()));
    }
  });
  test('identity preserves server Unicode result and original spaces; changed echo or oversized server key fails', () {
    final f = historicalFixture;
    expect(
      historicalAssetIdentity(
        f['identity'],
        f['identity_request']['inventory_number'],
      )['asset_key'],
      'masse-01',
    );
    expect(
      () => historicalAssetIdentity(f['identity'], 'MAẞE-01'),
      throwsA(isA<ApiException>()),
    );
    final bad = historicalCopy(f['identity'])..['asset_key'] = 's' * 101;
    expect(
      () => historicalAssetIdentity(
        bad,
        f['identity_request']['inventory_number'],
      ),
      throwsA(isA<ApiException>()),
    );
    expect(
      historicalAssetHistoryPath('maß /'),
      '$historicalAssetPath/history?asset_key=ma%C3%9F%20%2F',
    );
  });
  test('verified originals and history reject changed bytes and invented ancestry; false zero report cannot replace remaining AfA', () {
    final f = historicalFixture,
        bytes = base64Decode(
          historicalFixture['original_upload']['content_base64'],
        );
    historicalAssetVerifyBytes(bytes, historicalCopy(f['original']));
    bytes[3] ^= 1;
    expect(
      () => historicalAssetVerifyBytes(bytes, historicalCopy(f['original'])),
      throwsA(isA<ApiException>()),
    );
    final h = historicalCopy(f['history_after_void']);
    h['items'].removeAt(1);
    expect(
      () => historicalAssetHistory(h, f['saved']['asset_key']),
      throwsA(isA<ApiException>()),
    );
    final report = historicalCopy(f['euer_report_before']);
    report['historical_assets'][0]['continuation']['amount'] = '0.00';
    expect(() => historicalAssetReport(report), throwsA(isA<ApiException>()));
  });
}

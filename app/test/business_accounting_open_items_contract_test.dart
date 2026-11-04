import 'dart:convert';
import 'dart:io';
import 'dart:typed_data';

import 'package:flutter_test/flutter_test.dart';
import 'package:smartplan_office/api.dart';
import 'package:smartplan_office/business_accounting_open_items_contract.dart';

final openItemsFixture = openItemCopy(
  jsonDecode(
    File('test/fixtures/accounting_open_items_ui_v1.json').readAsStringSync(),
  ),
);
Map<String, dynamic> openItemsBody(dynamic command) => {
  for (final k in openItemInput) k: command[k],
};
void main() {
  test('original filename follows exact server length and separator boundary', () {
    final original = openItemCopy(
      openItemsFixture['receivable_prior_parts']['initial_state']['originals'][0],
    );
    for (final name in [
      '../invoice.pdf',
      r'folder\invoice.pdf',
      '${'a' * 197}.pdf',
    ]) {
      final wrong = {...original, 'filename': name};
      expect(() => openItemOriginal(wrong), throwsA(isA<ApiException>()));
    }
    expect(
      openItemOriginal({
        ...original,
        'filename': '${'a' * 196}.pdf',
      })['filename'].length,
      200,
    );
  });

  test('actual EÜR effects preserve inflow VAT and original payable input VAT without second deduction', () {
    for (final key in [
      'receivable_prior_parts',
      'payable_old_input_vat',
      'clerical_payment_correction',
    ]) {
      for (final payment in openItemsFixture[key]['payments']) {
        openItemEuerEffect(payment['euer_entry']['effect']);
      }
    }
  });
  test('payable effect rejects invented second input VAT even with valid original source', () {
    final effect = openItemCopy(
      openItemsFixture['payable_old_input_vat']['payments'][0]['euer_entry']['effect'],
    );
    effect['postings'].add({
      ...effect['postings'][1],
      'ledger': 'vat',
      'category': 'input_vat',
    });
    expect(() => openItemEuerEffect(effect), throwsA(isA<ApiException>()));
  });

  for (final scenario in [
    'receivable_prior_parts',
    'payable_old_input_vat',
    'clerical_payment_correction',
  ]) {
    test(
      'actual opening item, payment, preview, remaining and original history: $scenario',
      () {
        final f = openItemsFixture[scenario];
        for (final name in ['initial_state', 'state_after_item', 'final_state'])
          expect(openItemState(f[name]), f[name]);
        expect(
          openItemPreview(f['item_preview'], openItemsBody(f['item_command'])),
          f['item_preview'],
        );
        openItemReceipt(f['item_preview'])(f['item']);
        for (final p in f['payments']) {
          expect(
            openItemPreview(p['preview'], openItemsBody(p['command'])),
            p['preview'],
          );
          openItemReceipt(p['preview'])(p['payment']);
          expect(
            openItemSource(p['source'], payment: p['payment'], item: f['item']),
            p['source'],
          );
        }
        expect(
          openItemHistory(f['history'], f['item']['entity_key']),
          f['history'],
        );
        if (f['correction'] != null) {
          final c = f['correction'];
          openItemReceipt(c['void_preview'])(c['void']);
          openItemReceipt(c['preview'])(c['payment']);
        }
      },
    );
  }
  test(
    'state rejects wrong remaining cents outside immutable original hash',
    () {
      final state = openItemCopy(
        openItemsFixture['receivable_prior_parts']['state_after_item'],
      );
      state['items'][0]['remaining_net'] = '66.65';
      expect(() => openItemState(state), throwsA(isA<ApiException>()));
    },
  );
  test('correct foreign payment receipt cannot acknowledge frozen first-payment preview', () {
    final p = openItemsFixture['receivable_prior_parts']['payments'];
    expect(
      () => openItemReceipt(p[0]['preview'])(p[1]['payment']),
      throwsA(isA<ApiException>()),
    );
  });
  test('source identity binds original payment even with valid foreign source hash', () {
    final p = openItemsFixture['receivable_prior_parts']['payments'];
    expect(
      () => openItemSource(p[1]['source'], payment: p[0]['payment']),
      throwsA(isA<ApiException>()),
    );
  });
  test('prior input VAT preserves actual prior exercise date and no second input claim', () {
    final f = openItemsFixture['payable_old_input_vat'];
    final vat = f['item']['payload']['prior_input_vat'];
    expect(vat['deducted_on'], isNotEmpty);
    final postings = f['payments'][0]['euer_entry']['postings'] as List;
    expect(
      postings.where(
        (p) => p['ledger'] == 'vat' && p['category'] == 'input_vat',
      ),
      isEmpty,
    );
  });
  test('monetary input never defaults empty history values and preserves exact limit', () {
    expect(openItemAmount('99999999999,99'), '99999999999.99');
    expect(openItemCents('99999999999.99'), BigInt.parse('9999999999999'));
    for (final value in ['', '-1', '1.001', '100000000000.00', '1e2'])
      expect(() => openItemAmount(value), throwsA(isA<ApiException>()));
  });
  test('upload response must bind exact accepted original bytes', () {
    final metadata = openItemCopy(
      openItemsFixture['receivable_prior_parts']['initial_state']['originals'][0],
    );
    final input = {
      'entity_key': metadata['entity_key'],
      'filename': metadata['filename'],
      'media_type': metadata['media_type'],
    };
    expect(
      () => openItemOriginalReceipt(input, Uint8List.fromList([1, 2, 3]))(
        metadata,
      ),
      throwsA(isA<ApiException>()),
    );
  });
}

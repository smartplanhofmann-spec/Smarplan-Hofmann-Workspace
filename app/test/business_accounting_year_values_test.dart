import 'dart:convert';
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:smartplan_office/business_accounting_year_values_contract.dart';
import 'package:smartplan_office/business_accounting_open_items_contract.dart';
import 'package:smartplan_office/business_session.dart';

Map<String, dynamic> yearValuesFixture() => jsonDecode(
  File('test/fixtures/accounting_year_values_v1.json').readAsStringSync(),
) as Map<String, dynamic>;
void main() {
  final f = yearValuesFixture();
  for (final name in ['complete', 'partial_then_corrected', 'closed_trade']) {
    test('actual $name original state preview receipt source and history', () {
      final s = Map<String, dynamic>.from(f[name]);
      final state = yearValuesState(s['initial_state']),
          command = openItemCopy(s['command']),
          body = {for (final k in yearValuesInput) k: command[k]},
          preview = yearValuesPreview(
            s['preview'],
            body,
            openingItems: [openItemEvent(s['old_item'])],
          );
      yearValuesReceipt(command, preview, state)(s['entry']);
      yearValuesSource(s['source'], entry: openItemCopy(s['entry']));
      yearValuesState(s['state_after_acceptance']);
      yearValuesState(s['final_state']);
      yearValuesHistory(s['history'], '2026');
      yearValuesReport(openItemCopy(s['report']), businessItems(s['sources']));
      yearValuesEuerPreview(openItemCopy(s['euer_preview']), {
        for (final k in [
          'expected_revision',
          'state_hash',
          'operation',
          'payload',
          'reason',
          'evidence_reference',
        ])
          k: s['euer_preview'][k],
      });
    });
  }
  test('separate signed cent controls without guessed zeros', () {
    expect(yearValuesAmount('-59,50'), '-59.50');
    expect(() => yearValuesCents('-0.00'), throwsA(isA<Exception>()));
    expect(() => yearValuesCents('100000000000.00'), throwsA(isA<Exception>()));
  });
  test('rehash cannot change old VAT day or original account projection', () {
    final s = f['complete'];
    for (final field in ['vat', 'account']) {
      final p = openItemCopy(s['preview']);
      if (field == 'vat') {
        p['details']['copied_rows'][1]['deducted_on'] = '2026-07-11';
      } else {
        p['details']['historical_postings'][0]['account'] = '9999';
        p['details']['controls'][0]['account'] = '9999';
      }
      p.remove('preview_hash');
      p['preview_hash'] = openItemHash(p);
      expect(
        () => yearValuesPreview(
          p,
          {for (final k in yearValuesInput) k: s['command'][k]},
          openingItems: [openItemEvent(s['old_item'])],
        ),
        throwsA(isA<Exception>()),
      );
    }
  });
  test('source requires original entry even after valid foreign rehash', () {
    final s = f['complete'], source = openItemCopy(s['source']);
    source['details']['copied_rows'][1]['deducted_on'] = '2026-07-11';
    source.remove('source_hash');
    source['source_hash'] = openItemHash(source);
    expect(
      () => yearValuesSource(source, entry: openItemCopy(s['entry'])),
      throwsA(isA<Exception>()),
    );
  });
  test('partial coverage cannot be relabelled complete', () {
    final s = f['partial_then_corrected'], p = openItemCopy(s['preview']);
    p['details']['complete_prior_period'] = true;
    p.remove('preview_hash');
    p['preview_hash'] = openItemHash(p);
    expect(
      () => yearValuesPreview(p, {
        for (final k in yearValuesInput) k: s['command'][k],
      }),
      throwsA(isA<Exception>()),
    );
  });
  test(
    'receipt rejects foreign actual original and frozen state alteration',
    () {
      final s = f['complete'],
          validator = yearValuesReceipt(
            openItemCopy(s['command']),
            openItemCopy(s['preview']),
            openItemCopy(s['initial_state']),
          );
      expect(
        () => validator(f['closed_trade']['entry']),
        throwsA(isA<Exception>()),
      );
    },
  );
  test('unchanged originals reject rehashed moved days and copied cent substitutions', () {
    final f = yearValuesFixture()['complete'];
    for (final kind in ['day', 'cents']) {
      final p = openItemCopy(f['preview']);
      if (kind == 'day') {
        p['details']['copied_rows'][0]['date'] = '2026-09-20';
        p['details']['historical_postings'][0]['date'] = '2026-09-20';
        p['details']['historical_postings'][1]['date'] = '2026-09-20';
      } else {
        p['details']['copied_rows'][0]['gross'] = '59.51';
        p['details']['copied_rows'][0]['net'] = '50.01';
      }
      p.remove('preview_hash');
      p['preview_hash'] = openItemHash(p);
      expect(
        () => yearValuesPreview(p, {
          for (final k in yearValuesInput) k: f['command'][k],
        }),
        throwsA(isA<Exception>()),
      );
    }
  });
  test('public rehashed source still binds copied original net to projected journal cents', () {
    final source = openItemCopy(yearValuesFixture()['complete']['source']);
    source['details']['historical_postings'][0]['amount'] = '-49.00';
    source['details']['controls'][0]['amount'] = '-49.00';
    source.remove('source_hash');
    source['source_hash'] = openItemHash(source);
    expect(() => yearValuesSource(source), throwsA(isA<Exception>()));
  });
}

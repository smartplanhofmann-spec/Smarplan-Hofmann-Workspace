import 'dart:convert';
import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:smartplan_office/api.dart';
import 'package:smartplan_office/business_session.dart';
import 'package:smartplan_office/business_bank_reconciliation.dart';
import 'package:smartplan_office/business_qonto_readonly.dart';

final f = jsonDecode(
  File('test/fixtures/qonto_readonly.json').readAsStringSync(),
) as Map<String, dynamic>;
Map<String, dynamic> copy(dynamic value) =>
    Map<String, dynamic>.from(jsonDecode(jsonEncode(value)) as Map);
Future<Map<String, dynamic>> checked(dynamic value) => qontoReadView(
  value,
  accountId: f['status']['account_id'],
  bindingHash: f['result']['bank_binding_hash'],
  iban: f['result']['account_after']['iban'],
  body: copy(f['body']),
);

class QontoApi extends OfficeApi {
  QontoApi() : super(apiVersion: 'v1') {
    token = 'synthetic-qonto-client';
  }
  bool readable = true;
  final reads = <Map<String, dynamic>>[];
  @override
  Future<dynamic> call(String path, [Map<String, dynamic>? body]) async {
    if (path == '/api/business/capabilities') {
      final caps = copy(f['capabilities']);
      if (!readable)
        caps['permissions'] = (caps['permissions'] as List)
            .where((v) => v != 'bank.read')
            .toList();
      return caps;
    }
    if (path == '/api/business/bank/accounts') return copy(f['accounts']);
    if (path == '/api/bank-feeds/qonto/status') return copy(f['status']);
    if (path == '/api/bank-feeds/qonto/read' && body != null) {
      reads.add(copy(body));
      return copy(f['result']);
    }
    throw StateError(path);
  }
}

void main() {
  test(
    'actual MFA/HTTP fixture has exact negative cents and is never a statement',
    () async {
      final result = await checked(f['result']);
      expect(result['financial_changes'], false);
      expect(qontoMoney(result['items'][0]['signed_amount_cents']), '-0.43');
      expect(qontoMoney(999999999999999), '9999999999999.99');
      expect(qontoStatusLabel('pending'), 'Vorgemerkt');
      expect(qontoStatusLabel('reversed'), 'Storniert');
    },
  );
  test('UTC window rejects rollover, inversions and unbounded reads', () {
    expect(qontoWindow({'from': '2026-11-01', 'to': '2026-11-10'}), {
      'updated_from': '2026-11-01T00:00:00.000Z',
      'updated_to': '2026-11-10T00:00:00.000Z',
    });
    for (final value in [
      {'from': '2026-02-30', 'to': '2026-03-02'},
      {'from': '2026-01-01', 'to': '2026-02-10'},
      {'from': '2026-11-10', 'to': '2026-11-01'},
    ]) {
      expect(() => qontoWindow(value), throwsA(isA<ApiException>()));
    }
  });
  test('foreign bank, bad status, invented semantics and altered amounts are rejected', () async {
    for (final mutate in <void Function(Map<String, dynamic>)>[
      (v) => v['complete_statement'] = true,
      (v) => v['financial_changes'] = true,
      (v) => v['bank_binding_hash'] = 'a' * 64,
      (v) => v['local_account_id'] = 'b' * 32,
      (v) => v['items'][0]['status'] = 'booked',
      (v) => v['items'][0]['amount_cents'] = 44,
      (v) => v['items'][0]['signed_amount_cents'] = 43,
      (v) => v['items'][0]['updated_at'] = f['body']['updated_to'],
      (v) => v['account_before']['iban'] = 'OTHER',
      (v) => v['items'].add(copy(v['items'][0])),
    ]) {
      final value = copy(f['result']);
      mutate(value);
      await expectLater(checked(value), throwsA(isA<ApiException>()));
    }
  });
  testWidgets(
    'native bank view opens real Qonto form and clears after fresh bank revocation',
    (tester) async {
      final api = QontoApi();
      final s = BusinessSession(api: api);
      await s.load();
      try {
        await tester.pumpWidget(
          MaterialApp(home: BusinessBankReconciliationPage(session: s)),
        );
        await tester.pumpAndSettle();
        await tester.tap(find.text('Qonto-Umsatzänderungen lesen'));
        await tester.pumpAndSettle();
        expect(find.text('Qonto lesen'), findsOneWidget);
        final fields = find.byType(TextFormField);
        expect(fields, findsNWidgets(2));
        await tester.enterText(fields.at(0), '2026-11-01');
        await tester.enterText(fields.at(1), '2026-11-10');
        await tester.tap(find.text('Angaben unverbindlich prüfen'));
        await tester.pumpAndSettle();
        expect(find.text('Qonto · gelesene Umsatzänderungen'), findsOneWidget);
        expect(
          find.textContaining('kein vollständiger Kontoauszug'),
          findsOneWidget,
        );
        expect(find.text('Synthetic payer'), findsOneWidget);
        expect(api.reads, hasLength(1));
        api.readable = false;
        await s.load();
        await tester.pumpAndSettle();
        expect(find.text('Synthetic payer'), findsNothing);
      } finally {
        await tester.pumpWidget(const SizedBox.shrink());
        await tester.pumpAndSettle();
        s.dispose();
      }
    },
  );
}

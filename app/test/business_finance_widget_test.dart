import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:smartplan_office/business_finance.dart';
import 'package:smartplan_office/business_session.dart';

import 'business_session_test.dart' show BusinessTestApi;

class FinanceApi extends BusinessTestApi {
  @override
  Future<dynamic> call(String path, [Map<String, dynamic>? body]) async {
    if (path.split('?').first == '/api/business/capabilities')
      return {
        'storage_version': 7,
        'compatibility_mode': 'business',
        'generation': 1,
        'capabilities': ['business_finance'],
        'permissions': ['finance.read', 'finance.write', 'finance.approve'],
      };
    calls.add((path: path, body: body));
    if (path.startsWith('/api/business/finance/open-items'))
      return {
        'items': [
          {
            'id': 'a' * 32,
            'document_id': 'a' * 32,
            'number': 'RE-2026-008',
            'gross': '100.00',
            'paid': '25.00',
            'open': '75.00',
            'due_date': '2026-10-01',
            'level': 0,
          },
        ],
      };
    if (path == '/api/business/finance/outbox') return {'items': []};
    if (path == '/api/business/finance/dunning/preview')
      return {
        'items': [
          {
            'id': 'b' * 32,
            'number': 'RE-2026-008',
            'recipient': 'synthetic@example.test',
            'open': '75.00',
            'total': '75.00',
            'rule': {'name': 'Erinnerung', 'text': 'Bitte prüfen.'},
            'status': 'needs_approval',
          },
        ],
        'sent': false,
      };
    return {};
  }
}

void main() {
  testWidgets('Dunning is a review proposal, never an automatic send', (
    tester,
  ) async {
    final api = FinanceApi();
    final session = BusinessSession(api: api);
    await session.load();
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(body: BusinessFinancePage(session: session)),
      ),
    );
    await tester.pumpAndSettle();
    expect(find.textContaining('75,00'), findsWidgets);
    await tester.tap(find.text('Mahnlauf vorbereiten'));
    await tester.pumpAndSettle();
    expect(find.text('Vorschläge prüfen'), findsOneWidget);
    expect(find.textContaining('synthetic@example.test'), findsOneWidget);
    expect(
      api.calls.where(
        (r) => r.path.contains('/approve') || r.path.contains('/deliver'),
      ),
      isEmpty,
    );
    expect(tester.takeException(), isNull);
    await tester.pumpWidget(const SizedBox());
    session.dispose();
    api.dispose();
  });
}

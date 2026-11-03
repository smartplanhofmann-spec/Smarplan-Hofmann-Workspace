import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:smartplan_office/api.dart';
import 'package:smartplan_office/business_documents.dart';
import 'package:smartplan_office/business_session.dart';
import 'package:smartplan_office/design.dart';

import 'business_documents_widget_test.dart' show DocumentApi;

final firstId = 'a' * 32,
    middleId = 'c' * 32,
    finalId = 'd' * 32,
    projectId = 'b' * 32;

class ChainDocumentApi extends DocumentApi {
  bool loseConversion = false;
  Map<String, dynamic> doc(String id, String kind, {bool draft = false}) => {
    'id': id,
    'project_id': projectId,
    'kind': kind,
    'title': 'Synthetische Rechnungskette',
    'status': draft ? 'draft' : 'final',
    'revision': draft ? 1 : 2,
    'number': draft ? null : 'SYN-$kind',
    'issue_date': '2026-11-01',
    'due_date': '2026-11-10',
    'buyer': {
      'name': 'Synthetic buyer',
      'address_line': 'Testweg',
      'postal_code': '10115',
      'city': 'Berlin',
      'country': 'DE',
    },
    'positions': [
      {
        'description': 'Gesamte Vertragsleistung',
        'quantity': '1',
        'unit': 'C62',
        'unit_price_net': '100.00',
        'tax_rate': '19',
        'kind': 'service',
      },
    ],
    'totals': {
      'net': '30.00',
      'tax': '5.70',
      'gross': '35.70',
      'payable': '35.70',
    },
    if (kind != 'advance_invoice') ...{
      'previous_document_ids': [firstId],
      'contract_totals': {'net': '100.00', 'tax': '19.00', 'gross': '119.00'},
      'previous_issued_gross': '83.30',
      'previous_documents': [
        {'id': middleId, 'number': 'SYN-KUM-70', 'gross': '83.30'},
      ],
    },
  };
  @override
  Future<dynamic> call(String path, [Map<String, dynamic>? body]) async {
    if (path == '/api/business/documents/$firstId/convert') {
      calls.add((path: path, body: body));
      if (loseConversion) {
        loseConversion = false;
        throw const ApiException(0, 'Keine sichere Antwort.');
      }
      return doc(middleId, 'cumulative_invoice', draft: true);
    }
    if (path == '/api/business/documents/$firstId')
      return doc(firstId, 'advance_invoice');
    if (path == '/api/business/documents/$middleId')
      return doc(middleId, 'cumulative_invoice', draft: true);
    if (path == '/api/business/documents/$finalId')
      return doc(finalId, 'final_invoice');
    if (path.contains('/documents/time-sources') ||
        path == '/api/business/templates')
      return {'items': []};
    if (path.startsWith('/api/business/documents?'))
      return {
        'items': [
          doc(firstId, 'advance_invoice'),
          doc(middleId, 'cumulative_invoice'),
          doc('e' * 32, 'invoice'),
          doc(finalId, 'final_invoice'),
        ],
      };
    return super.call(path, body);
  }
}

Future<BusinessSession> showPage(
  WidgetTester tester,
  ChainDocumentApi api,
  String id,
) async {
  tester.view.physicalSize = const Size(1200, 1800);
  tester.view.devicePixelRatio = 1;
  addTearDown(tester.view.resetPhysicalSize);
  addTearDown(tester.view.resetDevicePixelRatio);
  final session = BusinessSession(api: api, projectId: projectId);
  await session.load();
  await tester.pumpWidget(
    MaterialApp(
      theme: officeTheme(),
      home: BusinessDocumentPage(session: session, id: id),
    ),
  );
  await tester.pumpAndSettle();
  return session;
}

void main() {
  testWidgets(
    'Issued advance converts to cumulative with the exact original request after a lost reply',
    (tester) async {
      final api = ChainDocumentApi()..loseConversion = true;
      final session = await showPage(tester, api, firstId);
      expect(find.text('In Rechnung umwandeln'), findsNothing);
      final button = find.text('In Kumulierte Rechnung umwandeln');
      expect(button, findsOneWidget);
      await tester.tap(button);
      await tester.pumpAndSettle();
      expect(find.textContaining('Keine sichere Antwort'), findsOneWidget);
      await tester.tap(button);
      await tester.pumpAndSettle();
      final writes = api.calls
          .where((value) => value.path.endsWith('/convert'))
          .toList();
      expect(writes, hasLength(2));
      expect(writes[0].body, writes[1].body);
      expect(writes[1].body!['target_kind'], 'cumulative_invoice');
      expect(writes[1].body!['revision'], 2);
      expect(find.text('Entwurf bearbeiten'), findsOneWidget);
      expect(
        find.text('In Kumulierte Rechnung umwandeln'),
        findsNothing,
        reason: 'Draft predecessor must first be issued.',
      );
      expect(tester.takeException(), isNull);
      await tester.pumpWidget(const SizedBox());
      session.dispose();
      api.dispose();
    },
  );
  testWidgets(
    'Final invoice distinguishes full contract, predecessor base and additional liability',
    (tester) async {
      final api = ChainDocumentApi();
      final session = await showPage(tester, api, finalId);
      expect(
        find.textContaining('Gesamte Vertragsleistung brutto: 119,00'),
        findsOneWidget,
      );
      expect(
        find.textContaining('Bereits berechnete Vertragsbasis brutto: 83,30'),
        findsOneWidget,
      );
      expect(find.textContaining('Vorbeleg SYN-KUM-70'), findsOneWidget);
      expect(
        find.text('Zusätzlich berechneter Rechnungsbetrag'),
        findsOneWidget,
      );
      expect(find.textContaining('Zu zahlen: 35,70'), findsOneWidget);
      expect(find.textContaining('umwandeln'), findsNothing);
      expect(tester.takeException(), isNull);
      await tester.pumpWidget(const SizedBox());
      session.dispose();
      api.dispose();
    },
  );
  testWidgets('Predecessor selection excludes ordinary and final invoices', (
    tester,
  ) async {
    final api = ChainDocumentApi();
    final session = await showPage(tester, api, middleId);
    await tester.tap(find.text('Entwurf bearbeiten'));
    await tester.pumpAndSettle();
    final heading = find.text(
      'Bereits ausgestellte Rechnungen berücksichtigen',
    );
    await tester.ensureVisible(heading);
    await tester.tap(heading);
    await tester.pumpAndSettle();
    expect(
      find.textContaining('SYN-advance_invoice · Vertragsbasis'),
      findsOneWidget,
    );
    expect(find.textContaining('SYN-invoice · Vertragsbasis'), findsNothing);
    expect(
      find.textContaining('SYN-final_invoice · Vertragsbasis'),
      findsNothing,
    );
    expect(tester.takeException(), isNull);
    await tester.pumpWidget(const SizedBox());
    session.dispose();
    api.dispose();
  });
}

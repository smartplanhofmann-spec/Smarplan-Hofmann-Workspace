import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:smartplan_office/business_documents.dart';
import 'package:smartplan_office/business_session.dart';
import 'package:smartplan_office/design.dart';

import 'business_session_test.dart' show BusinessTestApi;

class DocumentApi extends BusinessTestApi {
  @override
  Future<dynamic> call(String path, [Map<String, dynamic>? body]) async {
    if (path.split('?').first == '/api/business/capabilities')
      return {
        'storage_version': 7,
        'compatibility_mode': 'business',
        'generation': 1,
        'capabilities': ['business_documents'],
        'permissions': [
          'documents.read',
          'documents.write',
          'finance.read',
          'finance.write',
          'finance.issue',
        ],
      };
    if (path.startsWith('/api/business/documents')) {
      calls.add((path: path, body: body));
      final doc = {
        'id': 'a' * 32,
        'project_id': 'b' * 32,
        'kind': 'invoice',
        'title': 'Synthetische Schlussrechnung',
        'issue_date': '2026-10-26',
        'due_date': null,
        'status': 'final',
        'revision': 2,
        'number': 'RE-2026-001',
        'positions': [
          {
            'description': 'Leitung montiert',
            'quantity': '2',
            'unit': 'HUR',
            'unit_price_net': '55.50',
            'tax_rate': '19',
            'kind': 'labor',
          },
        ],
        'totals': {
          'net': '111.00',
          'tax': '21.09',
          'gross': '132.09',
          'payable': '132.09',
        },
      };
      return path.contains('?') || path.endsWith('/documents')
          ? {
              'items': [doc],
            }
          : doc;
    }
    return super.call(path, body);
  }
}

class DocumentCreateApi extends DocumentApi {
  Map<String, dynamic>? created;
  @override
  Future<dynamic> call(String path, [Map<String, dynamic>? body]) async {
    if (path == '/api/business/templates' ||
        path.contains('/documents/time-sources'))
      return {'items': []};
    if (path == '/api/business/documents' && body != null) {
      expect(body['project_id'], 'b' * 32);
      expect(body['kind'], 'offer');
      expect(body['issue_date'], matches(RegExp(r'^\d{4}-\d{2}-\d{2}$')));
      expect(
        body.containsKey('due_date'),
        isFalse,
        reason:
            'An optional due date must be omitted rather than sent as null.',
      );
      expect(body['positions'], hasLength(1));
      expect(body['positions'][0]['quantity'], '2');
      expect(body['positions'][0]['unit_price_net'], '55.50');
      calls.add((path: path, body: body));
      created = {
        ...body,
        'id': 'd' * 32,
        'revision': 1,
        'status': 'draft',
        'totals': {'net': '111.00', 'tax': '21.09', 'gross': '132.09'},
      };
      return created;
    }
    if (path == '/api/business/documents/${'d' * 32}') return created;
    return super.call(path, body);
  }
}

void main() {
  testWidgets('Final invoice is a readable archive without edit action', (
    tester,
  ) async {
    tester.view.physicalSize = const Size(1100, 1000);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    final api = DocumentApi();
    final session = BusinessSession(api: api, projectId: 'b' * 32);
    await session.load();
    await tester.pumpWidget(
      MaterialApp(
        theme: officeTheme(),
        home: Scaffold(body: BusinessDocumentsPage(session: session)),
      ),
    );
    await tester.pumpAndSettle();
    await tester.tap(find.text('Synthetische Schlussrechnung'));
    await tester.pumpAndSettle();
    expect(find.text('RE-2026-001'), findsWidgets);
    expect(find.text('Leitung montiert'), findsOneWidget);
    expect(find.text('Entwurf bearbeiten'), findsNothing);
    expect(find.textContaining('Unveränderlich'), findsOneWidget);
    expect(api.calls.where((v) => v.body != null), isEmpty);
    expect(tester.takeException(), isNull);
    await tester.pumpWidget(const SizedBox());
    session.dispose();
    api.dispose();
  });
  testWidgets(
    'A real document form creates typed positions and omits an empty optional due date',
    (tester) async {
      tester.view.physicalSize = const Size(1100, 1400);
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.resetPhysicalSize);
      addTearDown(tester.view.resetDevicePixelRatio);
      final api = DocumentCreateApi();
      final session = BusinessSession(api: api, projectId: 'b' * 32);
      await session.load();
      await tester.pumpWidget(
        MaterialApp(
          theme: officeTheme(),
          home: BusinessDocumentEditor(session: session),
        ),
      );
      await tester.pumpAndSettle();
      await tester.enterText(
        find.byKey(const ValueKey('business-document-title')),
        'Neues synthetisches Angebot',
      );
      final add = find.text('Position hinzufügen');
      await tester.ensureVisible(add);
      await tester.tap(add);
      await tester.pumpAndSettle();
      await tester.enterText(
        find.byKey(const ValueKey('business-field-description')),
        'Synthetische Montage',
      );
      await tester.enterText(
        find.byKey(const ValueKey('business-field-quantity')),
        '2',
      );
      await tester.enterText(
        find.byKey(const ValueKey('business-field-unit_price_net')),
        '55,50',
      );
      await tester.tap(find.widgetWithText(FilledButton, 'Speichern'));
      await tester.pumpAndSettle();
      final save = find.text('Entwurf speichern');
      await tester.ensureVisible(save);
      await tester.tap(save);
      await tester.pumpAndSettle();
      expect(api.created, isNotNull);
      expect(find.text('Neues synthetisches Angebot'), findsOneWidget);
      expect(find.textContaining('Entwurf'), findsWidgets);
      expect(tester.takeException(), isNull);
      await tester.pumpWidget(const SizedBox());
      session.dispose();
      api.dispose();
    },
  );
}

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:smartplan_office/api.dart';
import 'package:smartplan_office/business_document_access.dart';
import 'package:smartplan_office/business_session.dart';

import 'business_session_test.dart' show BusinessTestApi;

class AccessApi extends BusinessTestApi {
  String category = 'document', fingerprint = 'a' * 64;
  Map<String, dynamic>? approved;
  @override
  Future<dynamic> call(String path, [Map<String, dynamic>? body]) async {
    if (path.split('?').first == '/api/business/capabilities')
      return {
        'storage_version': 7,
        'compatibility_mode': 'business',
        'generation': 1,
        'capabilities': ['business_foundation'],
        'permissions': ['documents.read', 'documents.classify'],
      };
    if (path == '/api/projects/${'p' * 32}/links')
      return [
        {
          'id': 'b' * 32,
          'title': 'Synthetischer Projektlink',
          'url': 'https://example.test/old',
          'category': category,
          'revision': 1,
        },
      ];
    if (path == '/api/projects/${'p' * 32}/mail-attachments')
      return {'files': []};
    if (path.endsWith('/classification')) {
      calls.add((path: path, body: body));
      if (body != null) {
        if (body['expected_source_fingerprint'] != fingerprint)
          throw const ApiException(409, 'Quelle geändert');
        approved = body;
      }
      return {
        'id': 'b' * 32,
        'kind': 'link',
        'classification': body?['classification'] ?? 'unclassified',
        'revision': body == null ? 0 : 1,
        'release_current': body != null,
        'source_fingerprint': fingerprint,
      };
    }
    return super.call(path, body);
  }
}

void main() {
  testWidgets(
    'An explicit release binds the exact reviewed source fingerprint',
    (tester) async {
      final api = AccessApi();
      final session = BusinessSession(api: api, projectId: 'p' * 32);
      await session.load();
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(body: BusinessDocumentAccessPage(session: session)),
        ),
      );
      await tester.pumpAndSettle();
      await tester.tap(find.text('Freigabe prüfen'));
      await tester.pumpAndSettle();
      await tester.tap(find.byType(DropdownButtonFormField<String>));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Projektteam · operativ').last);
      await tester.pumpAndSettle();
      await tester.tap(find.text('Freigabe speichern'));
      await tester.pumpAndSettle();
      expect(api.approved?['expected_source_fingerprint'], 'a' * 64);
      expect(api.approved?['revision'], 0);
      expect(tester.takeException(), isNull);
      await tester.pumpWidget(const SizedBox());
      session.dispose();
      api.dispose();
    },
  );
  testWidgets('A changed link cannot be approved by retrying an old dialog', (
    tester,
  ) async {
    final api = AccessApi();
    final session = BusinessSession(api: api, projectId: 'p' * 32);
    await session.load();
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(body: BusinessDocumentAccessPage(session: session)),
      ),
    );
    await tester.pumpAndSettle();
    await tester.tap(find.text('Freigabe prüfen'));
    await tester.pumpAndSettle();
    api.fingerprint = 'c' * 64;
    await tester.tap(find.text('Freigabe speichern'));
    await tester.pumpAndSettle();
    expect(api.approved, isNull);
    expect(find.textContaining('erneut prüfen'), findsWidgets);
    final count = api.calls.where((c) => c.body != null).length;
    await tester.tap(find.text('Freigabe speichern'));
    await tester.pumpAndSettle();
    expect(api.calls.where((c) => c.body != null).length, count);
    await tester.pumpWidget(const SizedBox());
    session.dispose();
    api.dispose();
  });
}

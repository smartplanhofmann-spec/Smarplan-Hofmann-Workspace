import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:smartplan_office/business_contacts.dart';
import 'package:smartplan_office/business_session.dart';
import 'package:smartplan_office/business_templates.dart';
import 'package:smartplan_office/business_workflows.dart';
import 'package:smartplan_office/design.dart';

import 'business_session_test.dart' show BusinessTestApi;

class WorkflowApi extends BusinessTestApi {
  Map<String, dynamic> contact = {
    'id': 'a' * 32,
    'revision': 0,
    'name': 'Synthetischer Auftraggeber',
    'entity_type': 'company',
    'kinds': ['customer'],
    'persons': [],
    'addresses': [],
    'active': true,
  };
  final templates = <Map<String, dynamic>>[];
  final day = <String, dynamic>{
    'date': '2026-10-26',
    'revision': 3,
    'status': 'draft',
    'worked_seconds': 3600,
    'net_seconds': 3600,
    'break_seconds': 900,
    'auto_pause_seconds': 0,
    'target_seconds': 28800,
  };
  @override
  Future<dynamic> call(String path, [Map<String, dynamic>? body]) async {
    if (path.split('?').first == '/api/business/capabilities')
      return {
        'storage_version': 7,
        'compatibility_mode': 'business',
        'generation': 1,
        'capabilities': [
          'business_foundation',
          'business_documents',
          'business_time',
          'business_planning',
        ],
        'permissions': [
          'contacts.read',
          'contacts.write',
          'finance.read',
          'finance.write',
          'settings.manage',
          'time.own',
          'time.approve',
        ],
      };
    calls.add((
      path: path,
      body: body == null
          ? null
          : Map<String, dynamic>.from(jsonDecode(jsonEncode(body))),
    ));
    if (path == '/api/business/contacts/${'a' * 32}') {
      if (body != null) {
        expect(body['revision'], contact['revision']);
        contact = {...contact, ...body, 'revision': contact['revision'] + 1};
      }
      return Map<String, dynamic>.from(contact);
    }
    if (path == '/api/business/templates') {
      if (body != null) {
        expect(
          body.keys,
          containsAll([
            'name',
            'kind',
            'title',
            'intro',
            'notes',
            'positions',
            'request_id',
          ]),
        );
        expect(body.containsKey('project_id'), isFalse);
        expect(body.containsKey('issue_date'), isFalse);
        final row = {...body, 'id': 'b' * 32, 'revision': 1};
        templates.add(row);
        return row;
      }
      return {'items': templates};
    }
    if (path == '/api/business/text-blocks') return {'items': []};
    if (path.startsWith('/api/business/time/accounts'))
      return {
        'employee_id': 'd' * 32,
        'days': [Map<String, dynamic>.from(day)],
        'net_seconds': 3600,
        'target_seconds': 28800,
        'balance_seconds': -25200,
      };
    if (path == '/api/business/time/days/2026-10-26/approve') {
      expect(body!['employee_id'], 'd' * 32);
      expect(body['revision'], 3);
      day['status'] = 'approved';
      day['revision'] = 4;
      return day;
    }
    throw StateError('Unexpected workflow API request: $path');
  }
}

Finder field(String label) => find.widgetWithText(TextFormField, label);

void main() {
  Future<void> size(WidgetTester tester) async {
    tester.view.physicalSize = const Size(1100, 1400);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
  }

  testWidgets(
    'Contact work persists multiple address and person records through their real revisions',
    (tester) async {
      await size(tester);
      final api = WorkflowApi();
      final session = BusinessSession(api: api);
      await session.load();
      await tester.pumpWidget(
        MaterialApp(
          theme: officeTheme(),
          home: BusinessContactPage(session: session, id: 'a' * 32),
        ),
      );
      await tester.pumpAndSettle();
      await tester.tap(find.text('Hinzufügen').last);
      await tester.pumpAndSettle();
      await tester.enterText(
        field('Straße und Hausnummer'),
        'Synthetischer Weg 8',
      );
      await tester.enterText(field('Ort'), 'Beispielstadt');
      await tester.tap(find.widgetWithText(FilledButton, 'Speichern'));
      await tester.pumpAndSettle();
      expect(api.contact['addresses'], hasLength(1));
      await tester.tap(find.text('Hinzufügen').first);
      await tester.pumpAndSettle();
      await tester.enterText(field('Name'), 'Fiktive Bauleitung');
      await tester.enterText(field('E-Mail'), 'leitung@example.test');
      await tester.tap(find.widgetWithText(FilledButton, 'Speichern'));
      await tester.pumpAndSettle();
      expect(api.contact['persons'], hasLength(1));
      expect(api.contact['revision'], 2);
      expect(
        api.calls.where((c) => c.body != null).map((c) => c.body!['revision']),
        [0, 1],
      );
      expect(tester.takeException(), isNull);
      await tester.pumpWidget(const SizedBox());
      session.dispose();
      api.dispose();
    },
  );
  testWidgets(
    'A document template is editable without a project or invoice issue date',
    (tester) async {
      await size(tester);
      final api = WorkflowApi();
      final session = BusinessSession(api: api);
      await session.load();
      await tester.pumpWidget(
        MaterialApp(
          theme: officeTheme(),
          home: BusinessTemplatesPage(session: session),
        ),
      );
      await tester.pumpAndSettle();
      await tester.tap(find.text('Vorlage erstellen'));
      await tester.pumpAndSettle();
      await tester.enterText(
        field('Vorlagenname'),
        'Synthetisches Serviceangebot',
      );
      await tester.enterText(
        find.byKey(const ValueKey('business-document-title')),
        'Angebot zum Service',
      );
      final add = find.text('Position hinzufügen');
      await tester.ensureVisible(add);
      await tester.tap(add);
      await tester.pumpAndSettle();
      await tester.enterText(
        find.byKey(const ValueKey('business-field-description')),
        'Synthetische Leistung',
      );
      await tester.tap(find.widgetWithText(FilledButton, 'Speichern'));
      await tester.pumpAndSettle();
      final save = find.text('Vorlage speichern');
      await tester.ensureVisible(save);
      await tester.tap(save);
      await tester.pumpAndSettle();
      expect(api.templates, hasLength(1));
      expect(find.text('Synthetisches Serviceangebot'), findsOneWidget);
      expect(tester.takeException(), isNull);
      await tester.pumpWidget(const SizedBox());
      session.dispose();
      api.dispose();
    },
  );
  testWidgets(
    'The time account requires an explicit approval of the displayed day revision',
    (tester) async {
      await size(tester);
      final api = WorkflowApi();
      final session = BusinessSession(api: api);
      await session.load();
      await tester.pumpWidget(
        MaterialApp(
          theme: officeTheme(),
          home: Scaffold(body: BusinessTimeAccountsPage(session: session)),
        ),
      );
      await tester.pumpAndSettle();
      expect(api.calls.where((c) => c.body != null), isEmpty);
      await tester.tap(find.text('Tag prüfen und freigeben'));
      await tester.pumpAndSettle();
      expect(api.calls.where((c) => c.body != null), isEmpty);
      await tester.tap(find.text('Geprüften Tag freigeben'));
      await tester.pumpAndSettle();
      expect(api.day['status'], 'approved');
      expect(find.text('Freigegeben'), findsOneWidget);
      expect(tester.takeException(), isNull);
      await tester.pumpWidget(const SizedBox());
      session.dispose();
      api.dispose();
    },
  );
}

import 'dart:async';
import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:smartplan_office/api.dart';
import 'package:smartplan_office/business_sales.dart';
import 'package:smartplan_office/business_session.dart';

const customer = 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',
    actor = 'bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb',
    opportunity = 'cccccccccccccccccccccccccccccccc';
Map<String, dynamic> copy(Map<String, dynamic> value) =>
    Map<String, dynamic>.from(jsonDecode(jsonEncode(value)));
Map<String, dynamic> record() => {
  'id': opportunity,
  'revision': 1,
  'customer_id': customer,
  'customer_name': 'Synthetic customer',
  'inquiry_id': null,
  'inquiry_subject': null,
  'title': 'Synthetic installation',
  'person_id': null,
  'person_snapshot': null,
  'stage': 'qualified',
  'expected_net_minor': 123456,
  'probability_percent': 50,
  'responsible_id': actor,
  'follow_up_on': null,
  'expected_close_on': null,
  'description': 'Explicit forecast only',
  'closure_reason': '',
  'source_sha256': 'f' * 64,
  'links': <dynamic>[],
  'overdue': false,
  'created_at': '2026-11-03T12:00:00+00:00',
  'created_by': actor,
};

class SalesApi extends OfficeApi {
  SalesApi() : super(apiVersion: 'v1') {
    token = 'synthetic-sales-token';
  }
  Set<String> rights = {
    'contacts.read',
    'contacts.write',
    'projects.manage',
    'finance.read',
    'finance.write',
  };
  bool lose = false, readonly = false;
  Map<String, dynamic> saved = record();
  final sent = <Map<String, dynamic>>[];
  final receipts = <String, Map<String, dynamic>>{};
  Completer<dynamic>? delayedList;
  final requestedPaths = <String>[];
  List<Map<String, dynamic>> projects = [];
  @override
  Future<dynamic> call(String path, [Map<String, dynamic>? body]) async {
    requestedPaths.add(path);
    final route = path.split('?').first;
    if (route == '/api/business/capabilities')
      return {
        'compatibility_mode': 'business',
        'readonly': readonly,
        'generation': 1,
        'capabilities': [
          'business_sales',
          'business_foundation',
          'business_documents',
        ],
        'permissions': rights.toList(),
        'features': ['sales_pipeline'],
        'organization': {
          'modules': {
            'documents': {'visible': true, 'enabled': true},
          },
        },
      };
    if (route == '/api/business/sales/options')
      return {
        'customer_id': Uri.parse(path).queryParameters['customer_id'],
        'customers': [
          {
            'id': customer,
            'name': 'Synthetic customer',
            'persons': <dynamic>[],
          },
        ],
        'responsibles': [
          {'id': actor, 'email': 'sales@example.test'},
        ],
      };
    if (route == '/api/business/sales/opportunities' && body == null) {
      final value = {
        'items': [copy(saved)],
        'summary': {
          'open_count': 1,
          'expected_net_minor': 123456,
          'weighted_net_minor': 61728,
          'overdue_count': 0,
          'as_of': '2026-11-03T12:00:00+00:00',
        },
      };
      return delayedList == null ? value : delayedList!.future;
    }
    if (route == '/api/business/sales/opportunities' && body != null) {
      sent.add(copy(body));
      final result = receipts.putIfAbsent(
        body['request_id'],
        () => {
          ...copy(body),
          'id': opportunity,
          'revision': body['revision'] + 1,
          'created_by': actor,
        },
      );
      saved = {...record(), ...result};
      if (lose) {
        lose = false;
        throw const ApiException(
          0,
          'Synthetic acknowledgement lost after commit',
        );
      }
      return copy(result);
    }
    if (route == '/api/business/sales/opportunities/$opportunity')
      return copy(saved);
    if (route.endsWith('/activities')) return {'items': <dynamic>[]};
    if (route.endsWith('/history'))
      return {
        'items': [record(), copy(saved)],
      };
    if (route == '/api/inquiries') return <dynamic>[];
    if (route == '/api/projects') return projects.map(copy).toList();
    throw StateError('Unexpected sales fixture route $path');
  }
}

Future<BusinessSession> session(SalesApi api) async {
  final value = BusinessSession(api: api);
  await value.load();
  return value;
}

Future<void> open(WidgetTester tester, BusinessSession session) async {
  await tester.binding.setSurfaceSize(const Size(1100, 900));
  await tester.pumpWidget(
    MaterialApp(home: BusinessSalesPage(session: session)),
  );
  await tester.pumpAndSettle();
}

Finder field(String label) => find.widgetWithText(TextFormField, label);

void main() {
  testWidgets(
    'project adoption opens only the fresh canonical collection member',
    (tester) async {
      const projectId = 'dddddddddddddddddddddddddddddddd';
      final api = SalesApi();
      api.saved['links'] = [
        {'kind': 'project', 'project_id': projectId},
      ];
      api.projects = [
        {'id': projectId, 'name': 'Canonical project', 'customer_id': customer},
      ];
      final value = await session(api);
      Map<String, dynamic>? opened;
      await tester.binding.setSurfaceSize(const Size(1100, 900));
      addTearDown(() => tester.binding.setSurfaceSize(null));
      await tester.pumpWidget(
        MaterialApp(
          home: BusinessSalesPage(
            session: value,
            onProject: (project) => opened = project,
          ),
        ),
      );
      await tester.pumpAndSettle();
      await tester.tap(find.text('Synthetic installation'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Projekt öffnen'));
      await tester.pumpAndSettle();
      expect(opened?['id'], projectId);
      expect(api.requestedPaths, contains('/api/projects'));
      expect(
        api.requestedPaths.where((path) => path.startsWith('/api/projects/')),
        isEmpty,
      );
      opened = null;
      api.projects = [];
      await tester.tap(find.text('Projekt öffnen'));
      await tester.pumpAndSettle();
      expect(opened, isNull);
      expect(
        find.text('Das verknüpfte Projekt ist nicht mehr verfügbar.'),
        findsOneWidget,
      );
      await tester.pumpWidget(const SizedBox.shrink());
      value.dispose();
      api.dispose();
    },
  );
  test('forecast cents and closure evidence are explicit', () {
    expect(salesMinor('1234,56'), 123456);
    expect(salesMinor('0.01'), 1);
    for (final input in ['1.234', '1e3', '-1', 'NaN'])
      expect(() => salesMinor(input), throwsFormatException);
    final values = {
      'title': 'Synthetic',
      'stage': 'qualified',
      'expected_net': '1234,56',
      'probability_percent': 50,
      'responsible_id': actor,
    };
    expect(
      salesValues(values, customerId: customer)['expected_net_minor'],
      123456,
    );
    expect(
      () => salesValues({...values, 'stage': 'won'}, customerId: customer),
      throwsFormatException,
    );
    expect(
      () => salesValues({
        ...values,
        'stage': 'lost',
        'probability_percent': 0,
      }, customerId: customer),
      throwsFormatException,
    );
  });
  test('lost create ACK is retained during revoked rights and exact original survives metadata reload', () async {
    final api = SalesApi()..lose = true;
    final value = await session(api);
    addTearDown(value.dispose);
    final body = {...record()}..remove('id');
    body['revision'] = 0;
    final key = 'sales-save-new-$customer';
    await expectLater(
      value.command(key, '/sales/opportunities', body),
      throwsA(isA<ApiException>()),
    );
    expect(value.pending(key), isTrue);
    api.rights.remove('contacts.write');
    await expectLater(
      value.repeatSalesCommand(key),
      throwsA(isA<ApiException>()),
    );
    expect(api.sent, hasLength(1));
    expect(value.pending(key), isTrue);
    api.rights.add('contacts.write');
    await value.repeatSalesCommand(key);
    expect(api.sent, hasLength(2));
    expect(api.sent[1], api.sent[0]);
    expect(value.pending(key), isFalse);
  });
  testWidgets(
    'pipeline distinguishes forecast and editing preserves canonical customer',
    (tester) async {
      final api = SalesApi();
      final value = await session(api);
      addTearDown(() => tester.binding.setSurfaceSize(null));
      await open(tester, value);
      expect(find.textContaining('keine Umsätze'), findsOneWidget);
      expect(find.textContaining('617,28 € gewichtet'), findsOneWidget);
      await tester.tap(find.text('Synthetic installation'));
      await tester.pumpAndSettle();
      expect(find.text('Aktivität dokumentieren'), findsOneWidget);
      await tester.tap(find.text('Chance bearbeiten'));
      await tester.pumpAndSettle();
      await tester.enterText(field('Erwarteter Nettowert in EUR'), '1500,25');
      await tester.enterText(field('Wahrscheinlichkeit in Prozent'), '75');
      await tester.tap(find.widgetWithText(FilledButton, 'Speichern'));
      await tester.pumpAndSettle();
      expect(api.sent, hasLength(1));
      expect(api.sent.single['expected_net_minor'], 150025);
      expect(api.sent.single['customer_id'], customer);
      expect(api.sent.single['revision'], 1);
      expect(find.textContaining('1500,25 € netto erwartet'), findsOneWidget);
      expect(tester.takeException(), isNull);
      await tester.pumpWidget(const SizedBox.shrink());
      value.dispose();
      api.dispose();
    },
  );
  testWidgets(
    'current read-only rights leave history readable and hide mutation actions',
    (tester) async {
      final api = SalesApi()..readonly = true;
      final value = await session(api);
      addTearDown(() => tester.binding.setSurfaceSize(null));
      await open(tester, value);
      expect(find.text('Verkaufschance erfassen'), findsNothing);
      await tester.tap(find.text('Synthetic installation'));
      await tester.pumpAndSettle();
      expect(find.text('Chance bearbeiten'), findsNothing);
      expect(find.text('Änderungsverlauf'), findsOneWidget);
      await tester.tap(find.text('Änderungsverlauf'));
      await tester.pumpAndSettle();
      expect(find.textContaining('Fassung 1'), findsWidgets);
      expect(api.sent, isEmpty);
      await tester.pumpWidget(const SizedBox.shrink());
      value.dispose();
      api.dispose();
    },
  );
  testWidgets(
    'late list response cannot redisplay source data after rights revocation',
    (tester) async {
      final api = SalesApi()..delayedList = Completer<dynamic>();
      final value = await session(api);
      addTearDown(() => tester.binding.setSurfaceSize(null));
      await tester.pumpWidget(
        MaterialApp(home: BusinessSalesPage(session: value)),
      );
      await tester.pump();
      api.rights.clear();
      await value.load();
      await tester.pump();
      api.delayedList!.complete({
        'items': [record()],
        'summary': {},
      });
      await tester.pumpAndSettle();
      expect(find.text('Der Zugang ist nicht mehr verfügbar.'), findsOneWidget);
      expect(find.text('Synthetic installation'), findsNothing);
      expect(tester.takeException(), isNull);
      await tester.pumpWidget(const SizedBox.shrink());
      value.dispose();
      api.dispose();
    },
  );
}

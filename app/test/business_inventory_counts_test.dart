import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:smartplan_office/api.dart';
import 'package:smartplan_office/business_inventory_counts.dart';
import 'package:smartplan_office/business_session.dart';

const countId = 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',
    article = 'bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb',
    location = 'cccccccccccccccccccccccccccccccc';
Map<String, dynamic> record({int revision = 1, String status = 'open'}) => {
  'id': countId,
  'revision': revision,
  'status': status,
  'history_sha256': 'd' * 64,
  'title': 'Synthetische Inventur',
  'location_id': location,
  'location_name': 'Lager A',
  'counted_on': '2026-11-03',
  'reason': 'Jahreszählung',
  'basis_current': status == 'approved' ? null : true,
  'financial_values_visible': true,
  'items': [
    {
      'article': {'id': article, 'name': 'Kabel', 'unit': 'm'},
      'on_hand': '10.0000',
      'reserved': '0.0000',
      'counted_quantity': status == 'open' ? null : '8.0000',
      'difference': status == 'open' ? null : '-2.0000',
      'reason': status == 'open' ? '' : 'Bruch',
      if (status == 'approved') 'adjustment_value_net': '-4.0000',
    },
  ],
};

class CountApi extends OfficeApi {
  CountApi() : super(apiVersion: 'v1') {
    token = 'synthetic-inventory-count-token';
  }
  bool read = true, approve = true, loseAck = false;
  int revision = 1;
  String status = 'open';
  final commands = <Map<String, dynamic>>[];
  @override
  Future<dynamic> call(String path, [Map<String, dynamic>? body]) async {
    if (path.startsWith('/api/business/capabilities'))
      return {
        'compatibility_mode': 'business',
        'storage_version': 7,
        'generation': 1,
        'readonly': false,
        'features': ['inventory_counts'],
        'capabilities': ['business_inventory_counts', 'business_inventory'],
        'permissions': read
            ? [
                'inventory.read',
                'inventory.write',
                'finance.read',
                'finance.write',
                if (approve) 'finance.approve',
              ]
            : [],
        'organization': {
          'modules': {
            'material': {'visible': true, 'enabled': true},
          },
        },
      };
    if (path == '/api/business/inventory/locations')
      return {
        'items': [
          {'id': location, 'name': 'Lager A', 'active': true},
        ],
      };
    if (path == '/api/business/inventory/counts')
      return {
        'items': [record(revision: revision, status: status)],
      };
    if (path == '/api/business/inventory/counts/$countId' && body == null)
      return record(revision: revision, status: status);
    if (path.endsWith('/history'))
      return {
        'items': [record(), record(revision: 2, status: 'counted')],
      };
    if (path.endsWith('/preview'))
      return {
        'id': countId,
        'revision': 2,
        'project_cost_effect': 'none',
        'items': [
          {
            'article_id': article,
            'quantity_delta': '-2.0000',
            'value_delta_net': '-4.0000',
          },
        ],
      };
    if (path.endsWith('/count') || path.endsWith('/approve')) {
      commands.add(jsonDecode(jsonEncode(body)) as Map<String, dynamic>);
      status = path.endsWith('/count') ? 'counted' : 'approved';
      revision = status == 'counted' ? 2 : 3;
      if (loseAck) {
        loseAck = false;
        throw const ApiException(0, 'Erfolgsantwort verloren');
      }
      return record(revision: revision, status: status);
    }
    throw StateError('Unexpected path $path');
  }
}

void main() {
  test('quantities remain exact and every difference needs a reason', () {
    expect(inventoryQuantity('999999999999,9999'), '999999999999.9999');
    for (final value in ['', '-1', '1e3', '1.00001'])
      expect(() => inventoryQuantity(value), throwsA(isA<ApiException>()));
    expect(
      () => inventoryCountValues(record(), {
        'quantity_$article': '8',
        'reason_$article': '',
      }),
      throwsA(isA<ApiException>()),
    );
    expect(
      inventoryCountValues(record(), {
        'quantity_$article': '8',
        'reason_$article': 'Bruch',
      })['lines'],
      [
        {'article_id': article, 'quantity': '8.0000', 'reason': 'Bruch'},
      ],
    );
  });
  test('wrong archive identity or revision never confirms a command', () {
    for (final value in [
      {...record(), 'id': location},
      {...record(), 'revision': 2},
      {...record(), 'history_sha256': ''},
    ]) {
      expect(
        () => inventoryCountRecord(value, id: countId, revision: 1),
        throwsA(isA<ApiException>()),
      );
    }
  });
  test('lost approval retries exact nonce after fresh grant check, not a new count revision', () async {
    final api = CountApi()
      ..loseAck = true
      ..revision = 2
      ..status = 'counted';
    final session = BusinessSession(api: api);
    addTearDown(session.dispose);
    addTearDown(api.dispose);
    await session.load();
    const key = 'inventory-count-approve-$countId';
    await expectLater(
      session.command(
        key,
        '/inventory/counts/$countId/approve',
        {'revision': 2, 'confirmed': true, 'zero_stock_unit_costs': {}},
        validateResult: (value) => inventoryCountRecord(
          value,
          id: countId,
          revision: 3,
          status: 'approved',
        ),
      ),
      throwsA(isA<ApiException>()),
    );
    api.approve = false;
    await expectLater(
      session.repeatInventoryCountCommand(key),
      throwsA(isA<ApiException>()),
    );
    expect(api.commands.length, 1);
    expect(session.pending(key), true);
    api.approve = true;
    await session.repeatInventoryCountCommand(key);
    expect(api.commands[1], api.commands[0]);
    expect(session.pending(key), false);
  });
  testWidgets(
    'physical count UI records quantities then displays the approved valuation',
    (tester) async {
      await tester.binding.setSurfaceSize(const Size(1100, 1000));
      addTearDown(() => tester.binding.setSurfaceSize(null));
      final api = CountApi();
      final view = BusinessSession(api: api);
      await view.load();
      await tester.pumpWidget(
        MaterialApp(home: BusinessInventoryCountsPage(session: view)),
      );
      await tester.pumpAndSettle();
      await tester.tap(find.text('Synthetische Inventur').first);
      await tester.pumpAndSettle();
      await tester.ensureVisible(find.text('Mengen zählen'));
      await tester.tap(find.text('Mengen zählen'));
      await tester.pumpAndSettle();
      await tester.enterText(
        find.widgetWithText(TextFormField, 'Gezählte Menge · Kabel'),
        '8',
      );
      await tester.enterText(
        find.widgetWithText(TextFormField, 'Differenzgrund · Kabel'),
        'Bruch',
      );
      await tester.tap(
        find.widgetWithText(FilledButton, 'Zählung dokumentieren'),
      );
      await tester.pumpAndSettle();
      expect(api.commands.last['lines'], [
        {'article_id': article, 'quantity': '8.0000', 'reason': 'Bruch'},
      ]);
      await tester.ensureVisible(find.text('Differenzen prüfen und freigeben'));
      await tester.tap(find.text('Differenzen prüfen und freigeben'));
      await tester.pumpAndSettle();
      expect(find.textContaining('-4,0000'), findsOneWidget);
      await tester.tap(find.byType(SwitchListTile));
      await tester.pumpAndSettle();
      await tester.tap(
        find.widgetWithText(FilledButton, 'Differenzen verbindlich buchen'),
      );
      await tester.pumpAndSettle();
      expect(api.commands.last['confirmed'], true);
      expect(api.status, 'approved');
      expect(find.textContaining('Wertänderung netto'), findsOneWidget);
      api.read = false;
      await view.load();
      await tester.pumpAndSettle();
      expect(find.textContaining('Wertänderung netto'), findsNothing);
      expect(find.textContaining('nicht verfügbar'), findsOneWidget);
      await tester.pumpWidget(const SizedBox());
      view.dispose();
      api.dispose();
      await tester.pump();
    },
  );
}

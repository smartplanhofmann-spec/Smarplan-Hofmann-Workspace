import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:smartplan_office/api.dart';
import 'package:smartplan_office/business_asset_provenance.dart';
import 'package:smartplan_office/business_session.dart';

const project = 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa';
const receipt = 'bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb';
const issue = 'cccccccccccccccccccccccccccccccc';
Map<String, dynamic> copy(Map<String, dynamic> value) =>
    jsonDecode(jsonEncode(value)) as Map<String, dynamic>;
Map<String, dynamic> source() => {
  'receipt_id': receipt,
  'line_index': 0,
  'order_reference': 'BEST-1',
  'receipt_reference': 'LIEF-1',
  'available_quantity': '2.0000',
  'document_accessible': true,
  'document': {'content_hash': 'a' * 64},
  'article': {'id': 'd' * 32, 'name': 'Synthetisches Gerät', 'unit': 'Stk.'},
  'issues': [
    {'id': issue, 'sequence_number': 7, 'available_quantity': '2.0000'},
  ],
};
Map<String, dynamic> values() => {
  'name': 'Synthetisches Gerät',
  'serial_number': 'SYN-1',
  'asset_type': 'Pumpe',
  'location': 'Raum',
  'notes': 'Notiz',
  'issue_movement_id': issue,
  'quantity': '1,2500',
  'confirmed': true,
};

class ProvenanceApi extends OfficeApi {
  ProvenanceApi() : super(apiVersion: 'v1') {
    token = 'synthetic-asset-provenance-session';
  }
  bool allowed = true, loseAck = true;
  int created = 0;
  final commands = <Map<String, dynamic>>[];
  Map<String, dynamic>? saved;
  @override
  Future<dynamic> call(String path, [Map<String, dynamic>? body]) async {
    if (path.startsWith('/api/business/capabilities'))
      return {
        'compatibility_mode': 'business',
        'storage_version': 7,
        'generation': 1,
        'readonly': false,
        'capabilities': ['business_asset_provenance', 'business_maintenance'],
        'features': ['asset_delivery_provenance'],
        'permissions': allowed
            ? [
                'documents.read',
                'documents.write',
                'inventory.read',
                'inventory.write',
              ]
            : [],
      };
    if (path.startsWith('/api/business/assets/origin-sources')) {
      final row = source();
      if (created > 0) {
        row['available_quantity'] = '0.0000';
        row['issues'] = <dynamic>[];
      }
      return {
        'items': [row],
        'total': 1,
        'next_offset': null,
      };
    }
    if (path == '/api/business/assets/from-delivery') {
      if (!allowed) throw const ApiException(403, 'Keine Berechtigung');
      commands.add(copy(body!));
      if (saved == null) {
        created++;
        saved = copy(body);
      } else {
        expect(body, saved);
      }
      if (loseAck) {
        loseAck = false;
        throw const ApiException(0, 'Erfolgsantwort verloren');
      }
      return {
        'id': 'e' * 32,
        'asset': {'id': 'e' * 32},
        'origin': {'asset_id': 'e' * 32},
      };
    }
    throw StateError('Unexpected API $path');
  }
}

void main() {
  test(
    'explicit origin keeps decimal strings and limits copied device fields',
    () {
      final row = source(), before = copy(source());
      final result = assetOriginValues(row, values());
      expect(result['quantity'], '1.2500');
      expect(result['receipt_id'], receipt);
      expect(result['asset'], {
        'name': 'Synthetisches Gerät',
        'serial_number': 'SYN-1',
        'asset_type': 'Pumpe',
        'location': 'Raum',
        'notes': 'Notiz',
      });
      expect(row, before);
      expect(result.containsKey('unit_cost_net'), isFalse);
    },
  );
  test('binding an existing asset preserves its revision and creates no nested asset', () {
    final result = assetOriginValues(
      source(),
      values(),
      asset: {'id': 'e' * 32, 'revision': 4},
    );
    expect(result['asset_revision'], 4);
    expect(result.containsKey('asset'), isFalse);
  });
  test(
    'original, issue and confirmation must be present before the command',
    () {
      for (final change in [
        <String, dynamic>{'document_accessible': false},
        {'document': null},
        {'issues': []},
        {'line_index': -1},
      ]) {
        expect(
          () => assetOriginValues({...source(), ...change}, values()),
          throwsA(isA<ApiException>()),
        );
      }
      expect(
        () => assetOriginValues(source(), {...values(), 'confirmed': false}),
        throwsA(isA<ApiException>()),
      );
    },
  );
  test(
    'inexact or zero amounts and missing device identity do not send a command',
    () {
      for (final quantity in ['0', '-1', '1.12345', '1e3'])
        expect(
          () =>
              assetOriginValues(source(), {...values(), 'quantity': quantity}),
          throwsA(isA<ApiException>()),
        );
      expect(
        () => assetOriginValues(source(), {...values(), 'serial_number': ' '}),
        throwsA(isA<ApiException>()),
      );
    },
  );

  Future<BusinessSession> show(WidgetTester tester, ProvenanceApi api) async {
    tester.view.physicalSize = const Size(1400, 1500);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    final session = BusinessSession(
      api: api,
      projectId: project,
      projects: const [
        {'id': project, 'name': 'Synthetischer Einsatz'},
      ],
    );
    await session.load();
    await tester.pumpWidget(
      MaterialApp(home: BusinessAssetProvenancePage(session: session)),
    );
    await tester.pumpAndSettle();
    return session;
  }

  testWidgets(
    'lost creation reply can reopen and retry after the source capacity is consumed',
    (tester) async {
      final api = ProvenanceApi();
      final session = await show(tester, api);
      // Use the actual instance wired to this session throughout the interaction.
      final connected = session.api as ProvenanceApi;
      try {
        await tester.tap(find.text('Gerät aus Lieferung anlegen'));
        await tester.pumpAndSettle();
        await tester.enterText(
          find.byKey(const ValueKey('business-field-serial_number')),
          'SYN-SERIAL-7',
        );
        final choice = find.byWidgetPredicate(
          (widget) =>
              widget is DropdownButtonFormField<String> &&
              widget.decoration.labelText == 'Tatsächliche Materialentnahme',
        );
        await tester.tap(choice);
        await tester.pumpAndSettle();
        await tester.tap(find.text('Entnahme 7 · noch 2.0000 Stk.').last);
        await tester.pumpAndSettle();
        await tester.tap(find.byType(SwitchListTile));
        await tester.tap(find.text('Herkunft verbindlich bestätigen'));
        await tester.pumpAndSettle();
        expect(find.text('Erfolgsantwort verloren'), findsOneWidget);
        expect(connected.created, 1);
        await tester.tap(find.text('Schließen'));
        await tester.pumpAndSettle();
        await tester.tap(find.text('Unbestätigte Zuordnung wiederholen'));
        await tester.pumpAndSettle();
        expect(
          find.widgetWithText(TextFormField, 'SYN-SERIAL-7'),
          findsOneWidget,
        );
        await tester.tap(find.text('Erneut senden'));
        await tester.pumpAndSettle();
        expect(connected.commands, hasLength(2));
        expect(connected.commands.first, connected.commands.last);
        expect(connected.created, 1);
        expect(session.pending('asset-origin-$project-$receipt-0'), isFalse);
      } finally {
        await tester.pumpWidget(const SizedBox.shrink());
        session.dispose();
        api.dispose();
      }
    },
    variant: TargetPlatformVariant.only(TargetPlatform.windows),
  );

  testWidgets(
    'known read revocation removes source details and creation controls',
    (tester) async {
      final api = ProvenanceApi();
      final session = await show(tester, api);
      final connected = session.api as ProvenanceApi;
      try {
        expect(find.text('Synthetisches Gerät · LIEF-1'), findsOneWidget);
        connected.allowed = false;
        await session.load();
        await tester.pumpAndSettle();
        expect(find.text('Synthetisches Gerät · LIEF-1'), findsNothing);
        expect(find.text('Gerät aus Lieferung anlegen'), findsNothing);
        expect(find.text('Zugang nicht verfügbar'), findsOneWidget);
        expect(connected.commands, isEmpty);
      } finally {
        await tester.pumpWidget(const SizedBox.shrink());
        session.dispose();
        api.dispose();
      }
    },
    variant: TargetPlatformVariant.only(TargetPlatform.windows),
  );
}

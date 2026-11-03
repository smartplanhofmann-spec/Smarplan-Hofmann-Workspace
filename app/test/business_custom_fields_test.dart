import 'dart:convert';

import 'package:flutter/material.dart';

import 'package:flutter_test/flutter_test.dart';
import 'package:smartplan_office/business_custom_fields.dart';
import 'package:smartplan_office/api.dart';
import 'package:smartplan_office/business_session.dart';

final id = 'a' * 32, actor = 'b' * 32, entity = 'c' * 32, hash = 'd' * 64;
final definition = <String, dynamic>{
  'id': id,
  'revision': 1,
  'entity_type': 'project',
  'label': 'Messwert',
  'help_text': '',
  'field_type': 'number',
  'required': true,
  'active': true,
  'options': [],
  'reason': '',
  'content_hash': hash,
  'previous_hash': null,
  'created_by': actor,
  'created_at': '2026-11-03T10:00:00+00:00',
};
final current = <String, dynamic>{
  'entity_type': 'project',
  'entity_id': entity,
  'revision': 0,
  'previous_hash': null,
  'content_hash': null,
  'created_by': null,
  'created_at': null,
  'definitions_hash': null,
  'values': <String, dynamic>{},
};
final view = <String, dynamic>{
  'entity': {
    'entity_type': 'project',
    'id': entity,
    'label': 'Synthetic',
    'project_id': entity,
  },
  'definitions': [definition],
  'definitions_hash': hash,
  'current': current,
  'missing_required': [id],
  'complete': false,
  'can_write': true,
};
final body = <String, dynamic>{
  'revision': 0,
  'definitions_hash': hash,
  'values': {id: '0.123456'},
  'reason': '',
};
final result = <String, dynamic>{
  ...current,
  'revision': 1,
  'content_hash': hash,
  'created_by': actor,
  'created_at': definition['created_at'],
  'definitions_hash': hash,
  'definitions': [definition],
  'values': {
    id: {'definition': definition, 'value': '0.123456'},
  },
  'reason': '',
};
Map<String, dynamic> copy(dynamic v) =>
    Map<String, dynamic>.from(jsonDecode(jsonEncode(v)) as Map);

class CustomApi extends OfficeApi {
  bool malformed = true, lose = false, write = true;
  final posts = <Map<String, dynamic>>[];
  CustomApi() : super(apiVersion: 'v1') {
    token = 'synthetic-custom-field-session';
  }
  @override
  Future<dynamic> call(String path, [Map<String, dynamic>? values]) async {
    if (path.startsWith('/api/business/capabilities'))
      return {
        'compatibility_mode': 'business',
        'storage_version': 7,
        'generation': 1,
        'readonly': false,
        'features': ['custom_fields'],
        'capabilities': ['business_custom_fields'],
        'permissions': ['documents.read', 'projects.manage', 'settings.manage'],
      };
    if (path == '/api/me') return {'id': actor};
    if (path.endsWith('/history'))
      return {
        'items': [copy(result)],
        'next_before_revision': null,
      };
    if (values == null) return {...copy(view), 'can_write': write};
    posts.add(copy(values));
    if (lose) {
      lose = false;
      throw const ApiException(0, 'Lost acknowledgment');
    }
    if (!malformed) return copy(result);
    return {...copy(result), 'values': {}};
  }
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  test(
    'exact values preserve decimals and explicit false without coercion',
    () {
      expect(
        customValue(definition, '999999999999,123456'),
        '999999999999.123456',
      );
      expect(
        customValue({...definition, 'field_type': 'boolean'}, 'false'),
        false,
      );
      expect(customValue({...definition, 'required': false}, ''), null);
      for (final v in [0, true, '1e2', '01', '1.1234567', '١']) {
        expect(() => customValue(definition, v), throwsA(isA<ApiException>()));
      }
      expect(
        () => customValue({...definition, 'field_type': 'date'}, '2026-02-29'),
        throwsA(isA<ApiException>()),
      );
      expect(
        customValue({...definition, 'field_type': 'date'}, '2028-02-29'),
        '2028-02-29',
      );
    },
  );
  test('archived choices stay readable but cannot be newly selected', () {
    final old = 'e' * 32,
        d = {
          ...definition,
          'field_type': 'choice',
          'options': [
            {'id': old, 'label': 'Alte Auswahl', 'active': false},
          ],
        };
    expect(customValue(d, old, old), old);
    expect(() => customValue(d, old), throwsA(isA<ApiException>()));
    expect(customDisplay({'definition': d, 'value': old}), 'Alte Auswahl');
  });
  test('entity, frozen meaning and original values bind acknowledgments', () {
    customSnapshot(view, 'project', entity);
    expect(
      () => customSnapshot(view, 'contact', entity),
      throwsA(isA<ApiException>()),
    );
    final validate = customReceipt(body, previous: current, snapshot: view);
    validate(result);
    final bad = copy(result);
    bad['values'][id]['value'] = '0';
    expect(() => validate(bad), throwsA(isA<ApiException>()));
    expect(
      () => validate({...result, 'entity_id': actor}),
      throwsA(isA<ApiException>()),
    );
    expect(
      () => validate({...result, 'definitions': []}),
      throwsA(isA<ApiException>()),
    );
  });
  test(
    'definition acknowledgment binds explicit required and active flags',
    () {
      final command = <String, dynamic>{
        'revision': 0,
        'reason': '',
        'definition': {
          for (final key in [
            'entity_type',
            'label',
            'help_text',
            'field_type',
            'required',
            'active',
            'options',
          ])
            key: definition[key],
        },
      };
      customReceipt(command)(definition);
      expect(
        () => customReceipt(command)({...definition, 'required': false}),
        throwsA(isA<ApiException>()),
      );
    },
  );
  test('malformed receipt keeps exact pending command', () async {
    final api = CustomApi(), session = BusinessSession(api: api);
    await session.load();
    final key = 'custom-fields-project-$entity',
        path = '/custom-fields/entities/project/$entity';
    await expectLater(
      session.command(
        key,
        path,
        body,
        validateResult: customReceipt(body, previous: current, snapshot: view),
      ),
      throwsA(isA<ApiException>()),
    );
    expect(session.pending(key), true);
    expect(session.pendingCommandValues(key, path: path), body);
    session.dispose();
  });
  test('lost acknowledgment keeps nonce through fresh entity denial and restoration', () async {
    final api = CustomApi()
          ..malformed = false
          ..lose = true,
        session = BusinessSession(api: api);
    await session.load();
    final key = 'custom-fields-project-$entity',
        path = '/custom-fields/entities/project/$entity';
    await expectLater(
      session.command(
        key,
        path,
        body,
        validateResult: customReceipt(body, previous: current, snapshot: view),
      ),
      throwsA(isA<ApiException>()),
    );
    api.write = false;
    await expectLater(
      session.repeatCustomFieldsCommand(key),
      throwsA(isA<ApiException>()),
    );
    expect(api.posts.length, 1);
    expect(session.pending(key), true);
    api.write = true;
    await session.repeatCustomFieldsCommand(key);
    expect(session.pending(key), false);
    expect(api.posts[0], api.posts[1]);
    session.dispose();
  });
  testWidgets(
    'native editor uses typed field and private history disappears on revocation',
    (tester) async {
      final api = CustomApi(), session = BusinessSession(api: api);
      await session.load();
      await tester.pumpWidget(
        MaterialApp(
          home: BusinessCustomFieldsPage(
            session: session,
            entityType: 'project',
            entityId: entity,
          ),
        ),
      );
      await tester.pumpAndSettle();
      expect(find.textContaining('Pflichtangaben fehlen'), findsOneWidget);
      await tester.tap(find.text('Zusatzwerte bearbeiten'));
      await tester.pumpAndSettle();
      expect(find.byKey(ValueKey('business-field-$id')), findsOneWidget);
      await tester.enterText(
        find.byKey(ValueKey('business-field-$id')),
        '0,123456',
      );
      await tester.tap(find.text('Schließen'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Änderungshistorie'));
      await tester.pumpAndSettle();
      expect(find.text('Messwert: 0.123456'), findsOneWidget);
      session.revoke();
      await tester.pumpAndSettle();
      expect(find.text('Messwert: 0.123456'), findsNothing);
      expect(find.text('Zugang nicht mehr verfügbar'), findsOneWidget);
      await tester.pumpWidget(const SizedBox());
      session.dispose();
    },
  );
}

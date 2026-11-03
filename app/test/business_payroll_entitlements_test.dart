import 'dart:convert';
import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:smartplan_office/api.dart';
import 'package:smartplan_office/business_payroll_entitlements.dart';
import 'package:smartplan_office/business_session.dart';

final fixture = jsonDecode(
  File('test/fixtures/payroll_entitlements.json').readAsStringSync(),
) as Map<String, dynamic>;
Map<String, dynamic> copy(dynamic v) =>
    Map<String, dynamic>.from(jsonDecode(jsonEncode(v)) as Map);

class EntitlementsApi extends OfficeApi {
  EntitlementsApi(this.name) : super(apiVersion: 'v1') {
    token = 'synthetic-entitlement-client';
  }
  final String name;
  dynamic get value => fixture[name];
  String get employee => value['command']['employee_id'];
  bool read = true, approve = true, paused = false, lose = false;
  int created = 0;
  final sent = <Map<String, dynamic>>[];
  @override
  Future<dynamic> call(String path, [Map<String, dynamic>? body]) async {
    if (path.startsWith('/api/business/capabilities'))
      return {
        'compatibility_mode': 'business',
        'generation': 1,
        'storage_version': 10,
        'readonly': false,
        'features': ['payroll_entitlements'],
        'capabilities': ['business_payroll_entitlements'],
        'permissions': [
          if (read) 'personnel.read',
          if (approve) 'personnel.approve',
        ],
        'organization': {
          'modules': {
            'personnel': {'enabled': !paused, 'visible': true},
          },
        },
      };
    if (path == '/api/me') return {'id': 'a' * 32};
    if (path.startsWith('/api/business/payroll/entitlements/sources?'))
      return {
        ...copy(value['sources']),
        'can_approve': approve,
        'writes_enabled': !paused,
      };
    if (path == '/api/business/payroll/entitlements/preview')
      return copy(value['preview']);
    if (path == '/api/business/payroll/entitlements') {
      sent.add(copy(body));
      if (created == 0) created++;
      if (lose) {
        lose = false;
        throw const ApiException(
          0,
          'Angenommene Antwort synthetisch verloren.',
        );
      }
      return copy(value['saved']);
    }
    if (path.endsWith('/history')) return copy(value['history']);
    throw StateError(path);
  }
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  test('accepted claim keeps exact sources, original nonce and validator after pause', () async {
    final api = EntitlementsApi('unpaid')..lose = true,
        session = BusinessSession(api: api);
    addTearDown(session.dispose);
    addTearDown(api.dispose);
    await session.load();
    final v = api.value,
        body = copy(v['command'])..remove('request_id'),
        key = 'payroll-entitlements-${api.employee}';
    await expectLater(
      session.command(
        key,
        '/payroll/entitlements',
        body,
        validateResult: payrollEntitlementValidator(
          body,
          previous: copy(v['history']['items'][0]),
          preview: copy(v['preview']),
        ),
      ),
      throwsA(isA<ApiException>()),
    );
    expect(session.pending(key), true);
    api.paused = true;
    await session.repeatPayrollEntitlementsCommand(api.employee);
    expect(api.created, 1);
    expect(api.sent.length, 2);
    expect(api.sent.first, api.sent.last);
    expect(session.pending(key), false);
  });
  for (final name in ['sickness', 'vacation', 'unpaid']) {
    testWidgets(
      'actual $name plan displays private result on mobile and clears on rights withdrawal',
      (tester) async {
        tester.view.physicalSize = const Size(390, 844);
        tester.view.devicePixelRatio = 1;
        addTearDown(tester.view.resetPhysicalSize);
        addTearDown(tester.view.resetDevicePixelRatio);
        final api = EntitlementsApi(name), session = BusinessSession(api: api);
        await session.load();
        await tester.pumpWidget(
          MaterialApp(
            home: BusinessPayrollEntitlementsPage(
              session: session,
              employee: copy(api.value['sources']['employee']),
              onOriginal: (_) async {},
            ),
          ),
        );
        await tester.pumpAndSettle();
        final tile = find.textContaining('· Fassung 2').last;
        await tester.ensureVisible(tile);
        await tester.pumpAndSettle();
        await tester.tap(tile);
        await tester.pumpAndSettle();
        expect(
          find.text(api.value['saved']['details']['verification_note']),
          findsOneWidget,
        );
        expect(find.text('Anspruchshistorie öffnen'), findsOneWidget);
        expect(tester.takeException(), isNull);
        api.read = false;
        await session.load();
        await tester.pumpAndSettle();
        expect(
          find.text(api.value['saved']['details']['verification_note']),
          findsNothing,
        );
        expect(
          find.text('Anspruchsnachweise nicht freigegeben'),
          findsOneWidget,
        );
        await tester.pumpWidget(const SizedBox.shrink());
        session.dispose();
        api.dispose();
      },
    );
  }
  testWidgets(
    'regular absence form has typed source and cause choices without a free entitlement amount',
    (tester) async {
      final api = EntitlementsApi('sickness'),
          session = BusinessSession(api: api);
      await session.load();
      await tester.pumpWidget(
        MaterialApp(
          home: BusinessPayrollEntitlementsPage(
            session: session,
            employee: copy(api.value['sources']['employee']),
            onOriginal: (_) async {},
          ),
        ),
      );
      await tester.pumpAndSettle();
      final create = find.text(
        '${payrollEntitlementKinds['regular_absence']} erfassen',
      );
      await tester.ensureVisible(create);
      await tester.pumpAndSettle();
      await tester.tap(create);
      await tester.pumpAndSettle();
      expect(find.text('Belegte Beschäftigungsfassung'), findsOneWidget);
      expect(
        find.text('Belegte Art der regelmäßigen Ausfallvergütung'),
        findsOneWidget,
      );
      expect(
        find.byKey(const ValueKey('business-field-gross_minor')),
        findsNothing,
      );
      expect(
        tester
            .widget<TextFormField>(
              find.byKey(const ValueKey('business-field-from')),
            )
            .controller!
            .text,
        '',
      );
      expect(tester.takeException(), isNull);
      api.read = false;
      await session.load();
      await tester.pumpAndSettle();
      expect(find.text('Belegte Beschäftigungsfassung'), findsNothing);
      await tester.pumpWidget(const SizedBox.shrink());
      session.dispose();
      api.dispose();
    },
  );
  testWidgets(
    'unpaid source form requires renewed explicit legal facts even for correction',
    (tester) async {
      final api = EntitlementsApi('unpaid'),
          session = BusinessSession(api: api);
      await session.load();
      await tester.pumpWidget(
        MaterialApp(
          home: BusinessPayrollEntitlementsPage(
            session: session,
            employee: copy(api.value['sources']['employee']),
            onOriginal: (_) async {},
          ),
        ),
      );
      await tester.pumpAndSettle();
      final tile = find.textContaining('· Fassung 2');
      await tester.ensureVisible(tile);
      await tester.pumpAndSettle();
      await tester.tap(tile);
      await tester.pumpAndSettle();
      final correct = find.text('Anspruch korrigieren');
      await tester.ensureVisible(correct);
      await tester.pumpAndSettle();
      await tester.tap(correct);
      await tester.pumpAndSettle();
      expect(find.text('Belegter Korrekturgrund'), findsOneWidget);
      for (final field in tester.widgetList<SwitchListTile>(
        find.byType(SwitchListTile),
      ))
        expect(field.value, false);
      expect(find.text('Konkrete Anspruchsangaben belegen'), findsOneWidget);
      expect(tester.takeException(), isNull);
      await tester.pumpWidget(const SizedBox.shrink());
      session.dispose();
      api.dispose();
    },
  );
}

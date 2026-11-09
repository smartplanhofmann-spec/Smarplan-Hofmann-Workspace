import 'dart:convert';
import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:smartplan_office/business_session.dart';
import 'package:smartplan_office/business_settings.dart';

import 'business_organization_test.dart' show OrganizationApi;

Map<String, dynamic> fixture(String country) => Map<String, dynamic>.from(
  jsonDecode(
    File('test/fixtures/commercial-country-scope.json').readAsStringSync(),
  )[country],
);

class ScopeApi extends OrganizationApi {
  String country = 'DE';
  bool scopeFeature = true, stale = false;
  int scopeReads = 0;
  @override
  Future<dynamic> call(String path, [Map<String, dynamic>? body]) async {
    if (path == '/api/business/capabilities') {
      final result = await super.call(path, body);
      result['features'] = [if (scopeFeature) 'commercial_country_scope'];
      return result;
    }
    if (path == '/api/business/commercial/settings') {
      return {
        'revision': 2,
        'country': country,
        'company_name': 'Synthetic company',
        'issuing_enabled': false,
      };
    }
    if (path == '/api/business/commercial/rule-scope') {
      scopeReads++;
      return fixture(country)..['settings_revision'] = stale ? 1 : 2;
    }
    return super.call(path, body);
  }
}

void main() {
  test('native display accepts actual scope without granting issuing or changing configuration', () {
    final settings = {'revision': 2, 'country': 'DE', 'issuing_enabled': false};
    final value = commercialCountryScopeView(fixture('DE'), settings);
    expect(value.unsupported, isFalse);
    expect(value.message, contains('Deutschland'));
    expect(settings['issuing_enabled'], isFalse);
    for (final country in ['AT', 'CH']) {
      expect(
        commercialCountryScopeView(fixture(country), {
          'revision': 2,
          'country': country,
        }).unsupported,
        isTrue,
      );
    }
  });
  test(
    'native display refuses stale, incomplete and substituted rule packages',
    () {
      for (final value in [
        fixture('DE')..['settings_revision'] = 1,
        fixture('DE')..['issuer_country'] = 'AT',
        fixture('DE')..['supported_issuer'] = false,
        fixture('DE')..['selected']['currency'] = 'CHF',
        fixture('DE')..['supported'] = [],
        fixture('DE')..['scope_note'] = '',
      ]) {
        expect(
          () => commercialCountryScopeView(value, {
            'revision': 2,
            'country': 'DE',
          }),
          throwsFormatException,
        );
      }
    },
  );
  testWidgets(
    'settings show supported scope and immediately hide it after rights loss',
    (tester) async {
      final api = ScopeApi();
      final active = BusinessSession(api: api);
      try {
        await active.load();
        await tester.pumpWidget(
          MaterialApp(
            home: Scaffold(body: BusinessSettingsPage(session: active)),
          ),
        );
        await tester.pumpAndSettle();
        expect(find.text('Länderumfang der Rechnungsstellung'), findsOneWidget);
        expect(find.textContaining('Ausstellerland: DE.'), findsOneWidget);
        expect(api.scopeReads, 1);
        api.settingsAccess = false;
        await active.load();
        await tester.pumpAndSettle();
        expect(find.textContaining('Ausstellerland: DE.'), findsNothing);
        expect(find.text('Kein Zugriff'), findsOneWidget);
      } finally {
        await tester.pumpWidget(const SizedBox());
        active.dispose();
        api.dispose();
      }
    },
  );
  testWidgets(
    '390px settings describe an unsupported issuer without clipping or activating issuing',
    (tester) async {
      tester.view.devicePixelRatio = 1;
      tester.view.physicalSize = const Size(390, 844);
      addTearDown(tester.view.resetDevicePixelRatio);
      addTearDown(tester.view.resetPhysicalSize);
      final api = ScopeApi()..country = 'AT';
      final active = BusinessSession(api: api);
      try {
        await active.load();
        await tester.pumpWidget(
          MaterialApp(
            home: Scaffold(body: BusinessSettingsPage(session: active)),
          ),
        );
        await tester.pumpAndSettle();
        expect(find.textContaining('Ausstellerland: AT.'), findsOneWidget);
        expect(
          find.text('Sevdesk führt · eigene Belegausgabe gesperrt'),
          findsOneWidget,
        );
        expect(tester.takeException(), isNull);
      } finally {
        await tester.pumpWidget(const SizedBox());
        active.dispose();
        api.dispose();
      }
    },
  );
  testWidgets(
    'stale scope shows reload error and a legacy server is never probed',
    (tester) async {
      final api = ScopeApi()..stale = true;
      final active = BusinessSession(api: api);
      try {
        await active.load();
        await tester.pumpWidget(
          MaterialApp(
            home: Scaffold(body: BusinessSettingsPage(session: active)),
          ),
        );
        await tester.pumpAndSettle();
        expect(find.textContaining('Bitte neu laden.'), findsOneWidget);
        expect(find.text('Länderumfang der Rechnungsstellung'), findsNothing);
        await tester.pumpWidget(const SizedBox());
        api.scopeFeature = false;
        await active.load();
        await tester.pumpWidget(
          MaterialApp(
            home: Scaffold(body: BusinessSettingsPage(session: active)),
          ),
        );
        await tester.pumpAndSettle();
        expect(api.scopeReads, 1);
        expect(find.text('Länderumfang der Rechnungsstellung'), findsNothing);
      } finally {
        await tester.pumpWidget(const SizedBox());
        active.dispose();
        api.dispose();
      }
    },
  );
}

import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:smartplan_office/api.dart';
import 'package:smartplan_office/business_payroll_entitlements.dart';
import 'package:smartplan_office/business_session.dart';

import 'business_payroll_entitlements_test.dart' as base;

class PhasesApi extends base.EntitlementsApi {
  PhasesApi(this.fixtureVersion) : super('sickness');
  final String fixtureVersion;
  late final sample = jsonDecode(
    File('test/fixtures/payroll_sickness_$fixtureVersion.json')
        .readAsStringSync(),
  )['sickness'];
  @override
  dynamic get value => sample;
  final previews = <Map<String, dynamic>>[];
  Completer<dynamic>? heldPreview;
  Completer<dynamic>? heldCommand;
  @override
  Future<dynamic> call(String path, [Map<String, dynamic>? body]) async {
    if (path == '/api/business/payroll/entitlements' && heldCommand != null) {
      sent.add(base.copy(body));
      return heldCommand!.future;
    }
    if (path == '/api/business/payroll/entitlements/preview') {
      previews.add(base.copy(body));
      if (heldPreview != null) return heldPreview!.future;
    }
    return super.call(path, body);
  }
}

Future<void> press(WidgetTester tester, String label) async {
  final finder = find.text(label).last;
  await tester.ensureVisible(finder);
  await tester.pumpAndSettle();
  await tester.tap(finder);
  await tester.pumpAndSettle();
}

Future<void> prepareCorrection(WidgetTester tester, PhasesApi api) async {
  await press(tester, 'Anspruch korrigieren');
  expect(
    tester
        .widget<DropdownButtonFormField<String>>(
          choice('Belegte Form des Krankheitsverlaufs'),
        )
        .initialValue,
    api.fixtureVersion == 'phases_v3' ? 'combined' : 'preemployment',
  );
  await tester.enterText(
    find.byKey(const ValueKey('business-field-correction_reason')),
    'Synthetische erneute vollständige Belegprüfung',
  );
  await press(tester, 'Konkrete Anspruchsangaben belegen');
  final episodes = api.value['command']['details']['input']['episodes'] as List;
  for (var index = 0; index < episodes.length; index++) {
    final selector = choice(
      'Vorzeitenfall ${index + 1}: vorherige Arbeitsfähigkeit belegt (Nein bei fortbestehender AU)',
    );
    final widget = tester.widget<DropdownButtonFormField<String>>(selector);
    expect(widget.initialValue, '');
    widget.onChanged!(episodes[index]['recovery_before'] ? 'yes' : 'no');
    await tester.pump();
  }
  for (final widget
      in tester
          .widgetList<SwitchListTile>(find.byType(SwitchListTile))
          .toList()) {
    expect(widget.value, false);
    widget.onChanged!(true);
    await tester.pump();
  }
}

void background(WidgetTester tester) {
  tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.inactive);
  tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.hidden);
  tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.paused);
}

void resume(WidgetTester tester) {
  tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.hidden);
  tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.inactive);
  tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.resumed);
}

Finder choice(String label) => find.byWidgetPredicate(
  (widget) =>
      widget is DropdownButtonFormField<String> &&
      widget.decoration.labelText == label,
);
Future<void> start(
  WidgetTester tester,
  PhasesApi api,
  BusinessSession session,
) async {
  await session.load();
  await tester.pumpWidget(
    MaterialApp(
      home: BusinessPayrollEntitlementsPage(
        session: session,
        employee: base.copy(api.value['sources']['employee']),
        onOriginal: (_) async {},
      ),
    ),
  );
  await tester.pumpAndSettle();
  expect(
    find.text('Anspruchsnachweise nicht freigegeben'),
    findsNothing,
    reason:
        'session error=${session.error}; allowed=${session.allowed}; visible=${tester.widgetList<Text>(find.byType(Text)).map((w) => w.data).toList()}',
  );
  final tile = find.textContaining('· Fassung 1');
  await tester.scrollUntilVisible(
    tile,
    250,
    scrollable: find.byType(Scrollable).first,
  );
  await tester.ensureVisible(tile);
  await tester.pumpAndSettle();
  await tester.tap(tile);
  await tester.pumpAndSettle();
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  for (final version in ['phases_v3', 'start_v4']) {
    testWidgets(
      'actual $version mobile correction uses structured cases and exact original dates',
      (tester) async {
        tester.view.physicalSize = const Size(390, 844);
        tester.view.devicePixelRatio = 1;
        addTearDown(tester.view.resetPhysicalSize);
        addTearDown(tester.view.resetDevicePixelRatio);
        final api = PhasesApi(version), session = BusinessSession(api: api);
        await start(tester, api, session);
        expect(
          find.text('Zusammenhängender Verhinderungsfall 1'),
          findsOneWidget,
        );
        expect(
          find.text('Geprüfte Phasen ohne doppelte Tageszählung'),
          findsOneWidget,
        );
        if (version == 'start_v4')
          expect(
            find.text('Belegter Zeitraum vor Beschäftigungsbeginn'),
            findsOneWidget,
          );
        await prepareCorrection(tester, api);
        final original = api.value['command']['details']['input'];
        expect(
          find.byKey(const ValueKey('business-field-gross_minor')),
          findsNothing,
        );
        await press(tester, 'Anspruch unverbindlich prüfen');
        expect(api.previews.length, 1);
        expect(api.previews.single['details']['input'], original);
        await tester.scrollUntilVisible(
          find.text('Geprüften Anspruchsbaustein festhalten'),
          200,
          scrollable: find.byType(Scrollable).first,
        );
        expect(
          find.text('Geprüften Anspruchsbaustein festhalten'),
          findsOneWidget,
        );
        expect(tester.takeException(), isNull);
        await tester.pumpWidget(const SizedBox.shrink());
        session.dispose();
        api.dispose();
      },
    );
  }
  testWidgets(
    'backgrounding an open private sickness editor removes personal fields',
    (tester) async {
      final api = PhasesApi('phases_v3'), session = BusinessSession(api: api);
      await start(tester, api, session);
      await press(tester, 'Anspruch korrigieren');
      final field = find.byKey(
        const ValueKey('business-field-verification_note'),
      );
      expect(field, findsOneWidget);
      background(tester);
      await tester.pump();
      resume(tester);
      await tester.pumpAndSettle();
      expect(field, findsNothing);
      expect(api.previews, isEmpty);
      await tester.pumpWidget(const SizedBox.shrink());
      session.dispose();
      api.dispose();
    },
  );
  testWidgets(
    'late sickness preview after background cannot restore private details or submit a command',
    (tester) async {
      final api = PhasesApi('phases_v3'), session = BusinessSession(api: api);
      await start(tester, api, session);
      await prepareCorrection(tester, api);
      final response = Completer<dynamic>();
      api.heldPreview = response;
      final check = find.text('Anspruch unverbindlich prüfen');
      await tester.ensureVisible(check);
      await tester.pumpAndSettle();
      await tester.tap(check);
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 100));
      expect(api.previews.length, 1);
      background(tester);
      await tester.pump();
      resume(tester);
      await tester.pumpAndSettle();
      response.complete(base.copy(api.value['preview']));
      await tester.pumpAndSettle();
      expect(find.text('Anspruchsbaustein prüfen'), findsNothing);
      expect(
        find.text(api.value['saved']['details']['verification_note']),
        findsNothing,
      );
      expect(api.sent, isEmpty);
      expect(tester.takeException(), isNull);
      await tester.pumpWidget(const SizedBox.shrink());
      session.dispose();
      api.dispose();
    },
  );
  testWidgets(
    'late private sickness save error remains cleared after background',
    (tester) async {
      final api = PhasesApi('phases_v3'), session = BusinessSession(api: api);
      const secret =
          'Synthetischer privater Anspruchsvermerk aus verspäteter Speicherfehlermeldung';
      try {
        await start(tester, api, session);
        await prepareCorrection(tester, api);
        await press(tester, 'Anspruch unverbindlich prüfen');
        final confirm = find.text('Geprüften Anspruchsbaustein festhalten');
        await tester.scrollUntilVisible(
          confirm,
          200,
          scrollable: find.byType(Scrollable).first,
        );
        await press(tester, 'Geprüften Anspruchsbaustein festhalten');
        final response = Completer<dynamic>();
        api.heldCommand = response;
        await tester.tap(find.text('Anspruchsbaustein festhalten'));
        await tester.pump();
        await tester.pump(const Duration(milliseconds: 100));
        expect(api.sent.length, 1);
        background(tester);
        await tester.pump();
        resume(tester);
        await tester.pump();
        response.completeError(const ApiException(400, secret));
        await tester.pumpAndSettle();
        expect(find.text(secret), findsNothing);
        expect(tester.takeException(), isNull);
      } finally {
        await tester.pumpWidget(const SizedBox.shrink());
        session.dispose();
        api.dispose();
      }
    },
  );
}

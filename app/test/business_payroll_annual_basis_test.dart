import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:smartplan_office/api.dart';
import 'package:smartplan_office/business_payroll_annual_basis.dart';
import 'package:smartplan_office/business_session.dart';
import 'package:smartplan_office/business_widgets.dart';

import 'business_payroll_annual_basis_contract_test.dart' as actual;

class AnnualApi extends OfficeApi {
  AnnualApi(this.kind) : super(apiVersion: 'v1') {
    token = 'synthetic-private-annual-client';
  }
  final String kind;
  late final Map<String, dynamic> fixture = actual.copy(
    (actual.f['cases'] as List).firstWhere((v) => v['kind'] == kind),
  );
  String get employeeId => fixture['command']['employee_id'];
  bool read = true, approve = true, paused = false, lose = false;
  int created = 0;
  final sent = <Map<String, dynamic>>[], previews = <Map<String, dynamic>>[];
  Completer<dynamic>? heldPreview, heldSources;
  @override
  Future<dynamic> call(String path, [Map<String, dynamic>? body]) async {
    if (path.startsWith('/api/business/capabilities'))
      return {
        'compatibility_mode': 'business',
        'generation': 1,
        'storage_version': 10,
        'readonly': false,
        'features': ['payroll_annual_basis'],
        'capabilities': ['business_payroll_annual_basis'],
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
    if (path.startsWith('/api/business/payroll/annual-facts/sources?')) {
      if (heldSources != null) return heldSources!.future;
      return sources();
    }
    if (path == '/api/business/payroll/annual-facts/preview') {
      previews.add(actual.copy(body));
      if (heldPreview != null) return heldPreview!.future;
      return actual.copy(fixture['preview']);
    }
    if (path == '/api/business/payroll/annual-facts') {
      sent.add(actual.copy(body));
      if (created == 0) created++;
      if (lose) {
        lose = false;
        throw const ApiException(
          0,
          'Angenommene Antwort synthetisch verloren.',
        );
      }
      return actual.copy(fixture['saved']);
    }
    if (path.endsWith('/history')) return actual.copy(fixture['history']);
    throw StateError(path);
  }

  Map<String, dynamic> sources() => {
    ...actual.copy(fixture['sources']),
    'annual_facts': [
      ...fixture['sources']['annual_facts'],
      actual.copy(fixture['saved']),
    ],
    'can_approve': approve,
    'writes_enabled': !paused,
  };
}

class RecordedAnnualApi extends AnnualApi {
  RecordedAnnualApi() : super('annual_tax_forecast');
  final data = jsonDecode(
    File('test/fixtures/payroll_annual_basis_browser.json').readAsStringSync(),
  ) as Map<String, dynamic>;
  int stage = 0;
  @override
  late final Map<String, dynamic> fixture = {
    'sources': data['correction']['sources'],
    'command': data['correction']['command'],
    'saved': data['initial'],
    'preview': data['correction']['preview'],
  };
  @override
  Map<String, dynamic> sources() => actual.copy(
    stage == 0
        ? data['correction']['sources']
        : stage == 1
        ? data['void']['sources']
        : data['after_void_sources'],
  );
  @override
  Future<dynamic> call(String path, [Map<String, dynamic>? body]) async {
    if (path == '/api/business/payroll/annual-facts') {
      sent.add(actual.copy(body));
      final receipt = stage == 0 ? data['correction'] : data['void'];
      expect(
        actual.copy(body)..remove('request_id'),
        actual.copy(receipt['command'])..remove('request_id'),
      );
      stage++;
      return actual.copy(receipt['saved']);
    }
    if (path.endsWith('/history'))
      return {
        'employee_id': employeeId,
        'items': [
          data['initial'],
          if (stage > 0) data['correction']['saved'],
          if (stage > 1) data['void']['saved'],
        ],
      };
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

Future<void> open(
  WidgetTester tester,
  AnnualApi api,
  BusinessSession session, {
  Future<void> Function(Map<String, dynamic>)? onOriginal,
  Future<void> Function(Map<String, dynamic>)? onSelected,
}) async {
  await session.load();
  await tester.pumpWidget(
    MaterialApp(
      home: BusinessPayrollAnnualBasisPage(
        session: session,
        employee: actual.copy(api.fixture['sources']['employee']),
        onOriginal: onOriginal ?? (_) async {},
        onSelected: onSelected,
      ),
    ),
  );
  await tester.pumpAndSettle();
}

Future<void> inspect(WidgetTester tester, AnnualApi api) async {
  final heading = find.text(payrollAnnualKinds[api.kind]!);
  await tester.scrollUntilVisible(
    heading,
    250,
    scrollable: find.byType(Scrollable).first,
  );
  final card = find.ancestor(of: heading, matching: find.byType(Card)).last;
  final tile = find.descendant(of: card, matching: find.byType(ListTile)).last;
  await tester.ensureVisible(tile);
  await tester.pumpAndSettle();
  await tester.tap(tile);
  await tester.pumpAndSettle();
}

Future<void> renewEditor(WidgetTester tester) async {
  for (final toggle
      in tester
          .widgetList<SwitchListTile>(find.byType(SwitchListTile))
          .toList()) {
    expect(toggle.value, false);
    toggle.onChanged!(true);
    await tester.pump();
  }
}

Future<void> correction(WidgetTester tester) async {
  await press(tester, 'Jahresquelle korrigieren');
  await tester.enterText(
    find.byKey(const ValueKey('business-field-correction_reason')),
    'Synthetische erneute vollständige Quellenprüfung',
  );
}

void background(WidgetTester t) {
  t.binding.handleAppLifecycleStateChanged(AppLifecycleState.inactive);
  t.binding.handleAppLifecycleStateChanged(AppLifecycleState.hidden);
  t.binding.handleAppLifecycleStateChanged(AppLifecycleState.paused);
}

void resume(WidgetTester t) {
  t.binding.handleAppLifecycleStateChanged(AppLifecycleState.hidden);
  t.binding.handleAppLifecycleStateChanged(AppLifecycleState.inactive);
  t.binding.handleAppLifecycleStateChanged(AppLifecycleState.resumed);
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  for (final kind in payrollAnnualKinds.keys) {
    testWidgets(
      'actual $kind mobile view and all correction steps preserve canonical details',
      (tester) async {
        tester.view.physicalSize = const Size(390, 844);
        tester.view.devicePixelRatio = 1;
        addTearDown(tester.view.resetPhysicalSize);
        addTearDown(tester.view.resetDevicePixelRatio);
        final api = AnnualApi(kind), session = BusinessSession(api: api);
        try {
          await open(tester, api, session);
          await inspect(tester, api);
          expect(
            find.text(api.fixture['saved']['details']['verification_note']),
            findsOneWidget,
          );
          expect(tester.takeException(), isNull);
          await correction(tester);
          var steps = 0;
          while (find.byType(BusinessEditor).evaluate().isNotEmpty) {
            expect(++steps, lessThan(30));
            await renewEditor(tester);
            await press(tester, 'Belegte Angaben übernehmen');
          }
          expect(api.previews.length, 1);
          expect(api.previews.single, api.fixture['preview_request']);
          expect(find.text('Jahresquelle prüfen'), findsOneWidget);
          expect(tester.takeException(), isNull);
          api.read = false;
          await session.load();
          await tester.pumpAndSettle();
          expect(find.text('Jahresquelle prüfen'), findsNothing);
          expect(find.text('Jahresquellen nicht freigegeben'), findsOneWidget);
        } finally {
          await tester.pumpWidget(const SizedBox.shrink());
          session.dispose();
          api.dispose();
        }
      },
    );
  }
  test('accepted annual source replays exact nonce after pause, with renewed global rights', () async {
    final api = AnnualApi('one_off_earning')..lose = true,
        session = BusinessSession(api: api);
    addTearDown(session.dispose);
    addTearDown(api.dispose);
    await session.load();
    final body = actual.copy(api.fixture['command'])..remove('request_id'),
        key = 'payroll-annual-basis-${api.employeeId}';
    await expectLater(
      session.command(
        key,
        '/payroll/annual-facts',
        body,
        validateResult: payrollAnnualValidator(
          body,
          preview: actual.copy(api.fixture['preview']),
        ),
      ),
      throwsA(isA<ApiException>()),
    );
    expect(session.pending(key), true);
    api.approve = false;
    await expectLater(
      session.repeatPayrollAnnualBasisCommand(api.employeeId),
      throwsA(isA<ApiException>()),
    );
    expect(api.sent.length, 1);
    api.approve = true;
    api.paused = true;
    await session.repeatPayrollAnnualBasisCommand(api.employeeId);
    expect(api.created, 1);
    expect(api.sent.length, 2);
    expect(api.sent.first, api.sent.last);
    expect(session.pending(key), false);
  });
  testWidgets(
    'historical original and active selection use exact fresh employee sources',
    (tester) async {
      final api = AnnualApi('one_off_earning'),
          session = BusinessSession(api: api),
          originals = <Map<String, dynamic>>[],
          selected = <Map<String, dynamic>>[];
      try {
        await open(
          tester,
          api,
          session,
          onOriginal: (v) async {
            originals.add(v);
          },
          onSelected: (v) async {
            selected.add(v);
          },
        );
        await inspect(tester, api);
        final file = api.fixture['saved']['sources']['source_files'][0];
        await press(tester, 'Personaloriginal: ${file['filename']}');
        expect(originals.single, file);
        await press(tester, 'Diese Jahresquelle auswählen');
        expect(selected.single, api.fixture['saved']);
        await press(tester, 'Jahresquellenhistorie öffnen');
        final history = find.text('Historische Jahresquellenfassung 1');
        await tester.scrollUntilVisible(
          history,
          200,
          scrollable: find.byType(Scrollable).first,
        );
        await press(tester, 'Historische Jahresquellenfassung 1');
        expect(find.text('Historische Originalfassung'), findsOneWidget);
        expect(find.text('Jahresquelle korrigieren'), findsNothing);
        expect(find.text('Diese Jahresquelle auswählen'), findsNothing);
        expect(tester.takeException(), isNull);
      } finally {
        await tester.pumpWidget(const SizedBox.shrink());
        session.dispose();
        api.dispose();
      }
    },
  );
  testWidgets('background removes an open private annual editor', (
    tester,
  ) async {
    final api = AnnualApi('one_off_earning'),
        session = BusinessSession(api: api);
    try {
      await open(tester, api, session);
      await inspect(tester, api);
      await correction(tester);
      expect(find.byType(BusinessEditor), findsOneWidget);
      background(tester);
      await tester.pump();
      resume(tester);
      await tester.pumpAndSettle();
      expect(find.byType(BusinessEditor), findsNothing);
      expect(
        find.text(api.fixture['saved']['details']['verification_note']),
        findsNothing,
      );
      expect(api.previews, isEmpty);
    } finally {
      await tester.pumpWidget(const SizedBox.shrink());
      session.dispose();
      api.dispose();
    }
  });
  testWidgets(
    'late annual preview cannot restore private data after returning from background',
    (tester) async {
      final api = AnnualApi('one_off_earning'),
          session = BusinessSession(api: api);
      try {
        await open(tester, api, session);
        await inspect(tester, api);
        await correction(tester);
        while (tester
                .widget<BusinessEditor>(find.byType(BusinessEditor))
                .title !=
            'Konkrete Jahresquellen prüfen') {
          await renewEditor(tester);
          await press(tester, 'Belegte Angaben übernehmen');
        }
        await renewEditor(tester);
        final response = Completer<dynamic>();
        api.heldPreview = response;
        final button = find.text('Belegte Angaben übernehmen');
        await tester.ensureVisible(button);
        await tester.pumpAndSettle();
        await tester.tap(button);
        await tester.pump();
        await tester.pump(const Duration(milliseconds: 100));
        expect(api.previews.length, 1);
        background(tester);
        await tester.pump();
        resume(tester);
        await tester.pump();
        response.complete(actual.copy(api.fixture['preview']));
        await tester.pumpAndSettle();
        expect(find.text('Jahresquelle prüfen'), findsNothing);
        expect(
          find.text(api.fixture['saved']['details']['verification_note']),
          findsNothing,
        );
        expect(api.sent, isEmpty);
        expect(tester.takeException(), isNull);
      } finally {
        await tester.pumpWidget(const SizedBox.shrink());
        session.dispose();
        api.dispose();
      }
    },
  );
  testWidgets(
    'actual HTTP correction and void receipts survive native confirmation and preserve historical original',
    (tester) async {
      final api = RecordedAnnualApi(), session = BusinessSession(api: api);
      try {
        await open(tester, api, session);
        await inspect(tester, api);
        await correction(tester);
        await tester.enterText(
          find.byKey(const ValueKey('business-field-correction_reason')),
          api.data['correction']['command']['correction_reason'],
        );
        await tester.enterText(
          find.byKey(const ValueKey('business-field-verification_note')),
          api.data['correction']['command']['details']['verification_note'],
        );
        var steps = 0;
        while (find.byType(BusinessEditor).evaluate().isNotEmpty) {
          expect(++steps, lessThan(30));
          await renewEditor(tester);
          await press(tester, 'Belegte Angaben übernehmen');
        }
        expect(api.previews.single, api.data['correction']['preview_request']);
        final confirm = find.text('Geprüfte Jahresquelle festhalten');
        await tester.scrollUntilVisible(
          confirm,
          200,
          scrollable: find.byType(Scrollable).first,
        );
        await press(tester, 'Geprüfte Jahresquelle festhalten');
        await press(tester, 'Jahresquelle festhalten');
        expect(api.stage, 1);
        expect(
          find.text('${payrollAnnualKinds[api.kind]} · Fassung 2'),
          findsOneWidget,
        );
        await press(tester, 'Fälschliche Jahresquelle aufheben');
        await tester.enterText(
          find.byKey(const ValueKey('business-field-correction_reason')),
          api.data['void']['command']['correction_reason'],
        );
        await renewEditor(tester);
        await press(tester, 'Belegte Angaben übernehmen');
        expect(api.stage, 2);
        expect(
          find.text('${payrollAnnualKinds[api.kind]} · Fassung 3'),
          findsOneWidget,
        );
        await press(tester, 'Jahresquellenhistorie öffnen');
        final historic = find.text('Historische Jahresquellenfassung 1');
        await tester.scrollUntilVisible(
          historic,
          200,
          scrollable: find.byType(Scrollable).first,
        );
        await press(tester, 'Historische Jahresquellenfassung 1');
        expect(
          find.text(api.data['initial']['details']['verification_note']),
          findsOneWidget,
        );
        expect(find.text('Historische Originalfassung'), findsOneWidget);
        expect(api.sent.length, 2);
        expect(tester.takeException(), isNull);
      } finally {
        await tester.pumpWidget(const SizedBox.shrink());
        session.dispose();
        api.dispose();
      }
    },
  );
  testWidgets(
    'pending annual confirmation blocks new forms and replays the original after module pause',
    (tester) async {
      final api = AnnualApi('one_off_earning')..lose = true,
          session = BusinessSession(api: api);
      try {
        await session.load();
        final body = actual.copy(api.fixture['command'])..remove('request_id');
        await expectLater(
          session.command(
            'payroll-annual-basis-${api.employeeId}',
            '/payroll/annual-facts',
            body,
            validateResult: payrollAnnualValidator(
              body,
              preview: actual.copy(api.fixture['preview']),
            ),
          ),
          throwsA(isA<ApiException>()),
        );
        api.paused = true;
        await open(tester, api, session);
        expect(find.text('Jahresquellenbestätigung offen'), findsOneWidget);
        expect(find.textContaining(' erfassen'), findsNothing);
        expect(find.text('Jahresquelle korrigieren'), findsNothing);
        await press(
          tester,
          'Ursprünglichen Jahresquellenauftrag erneut senden',
        );
        expect(api.sent.length, 2);
        expect(api.sent.first, api.sent.last);
        expect(api.created, 1);
        expect(find.text('Jahresquellenbestätigung offen'), findsNothing);
        expect(
          find.text(api.fixture['saved']['details']['verification_note']),
          findsOneWidget,
        );
        expect(tester.takeException(), isNull);
      } finally {
        await tester.pumpWidget(const SizedBox.shrink());
        session.dispose();
        api.dispose();
      }
    },
  );
  testWidgets(
    'late annual error text stays cleared after the private view was left',
    (tester) async {
      final api = AnnualApi('one_off_earning'),
          session = BusinessSession(api: api);
      const secret =
          'Synthetischer privater Belegvermerk in verspäteter Fehlermeldung';
      try {
        await open(tester, api, session);
        await inspect(tester, api);
        await correction(tester);
        while (tester
                .widget<BusinessEditor>(find.byType(BusinessEditor))
                .title !=
            'Konkrete Jahresquellen prüfen') {
          await renewEditor(tester);
          await press(tester, 'Belegte Angaben übernehmen');
        }
        await renewEditor(tester);
        final response = Completer<dynamic>();
        api.heldPreview = response;
        final button = find.text('Belegte Angaben übernehmen');
        await tester.ensureVisible(button);
        await tester.pumpAndSettle();
        await tester.tap(button);
        await tester.pump();
        await tester.pump(const Duration(milliseconds: 100));
        expect(api.previews.length, 1);
        background(tester);
        await tester.pump();
        resume(tester);
        await tester.pump();
        response.completeError(const ApiException(400, secret));
        await tester.pumpAndSettle();
        expect(find.text(secret), findsNothing);
        expect(api.sent, isEmpty);
        expect(tester.takeException(), isNull);
      } finally {
        await tester.pumpWidget(const SizedBox.shrink());
        session.dispose();
        api.dispose();
      }
    },
  );
}

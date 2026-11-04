import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:smartplan_office/api.dart';
import 'package:smartplan_office/business_payroll_annual_basis.dart';
import 'package:smartplan_office/business_session.dart';
import 'package:smartplan_office/business_widgets.dart';

import 'business_payroll_annual_basis_contract_test.dart' as actual;
import 'business_payroll_annual_basis_test.dart' as owner;

class ReviewAnnualApi extends owner.AnnualApi {
  ReviewAnnualApi() : super('one_off_earning');
  void Function(Map<String, dynamic>)? alterResult, alterSources;
  @override
  Map<String, dynamic> sources() {
    final result = super.sources();
    alterSources?.call(result);
    return result;
  }

  @override
  Future<dynamic> call(String path, [Map<String, dynamic>? body]) async {
    final result = await super.call(path, body);
    if (path == '/api/business/payroll/annual-facts') {
      alterResult?.call(result as Map<String, dynamic>);
    }
    return result;
  }
}

Future<void> stop(
  WidgetTester tester,
  BusinessSession session,
  OfficeApi api,
) async {
  await tester.pumpWidget(const SizedBox.shrink());
  session.dispose();
  api.dispose();
}

Future<void> holdPreview(WidgetTester tester, ReviewAnnualApi api) async {
  await owner.correction(tester);
  var steps = 0;
  while (tester.widget<BusinessEditor>(find.byType(BusinessEditor)).title !=
      'Konkrete Jahresquellen prüfen') {
    expect(++steps, lessThan(30));
    await owner.renewEditor(tester);
    await owner.press(tester, 'Belegte Angaben übernehmen');
  }
  await owner.renewEditor(tester);
  api.heldPreview = Completer<dynamic>();
  final button = find.text('Belegte Angaben übernehmen');
  await tester.ensureVisible(button);
  await tester.pumpAndSettle();
  await tester.tap(button);
  await tester.pump();
  await tester.pump(const Duration(milliseconds: 100));
  expect(api.previews.length, 1);
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  testWidgets(
    'review employee change removes existing private annual editor and old selected original',
    (tester) async {
      final api = ReviewAnnualApi(), session = BusinessSession(api: api);
      try {
        await owner.open(tester, api, session);
        await owner.inspect(tester, api);
        await owner.correction(tester);
        expect(find.byType(BusinessEditor), findsOneWidget);
        await tester.pumpWidget(
          MaterialApp(
            home: BusinessPayrollAnnualBasisPage(
              session: session,
              employee: {
                ...actual.copy(api.fixture['sources']['employee']),
                'id': 'f' * 32,
                'name': 'Other synthetic employee',
              },
              onOriginal: (_) async {},
            ),
          ),
        );
        await tester.pumpAndSettle();
        expect(find.byType(BusinessEditor), findsNothing);
        expect(
          find.text(api.fixture['saved']['details']['verification_note']),
          findsNothing,
        );
        expect(api.previews, isEmpty);
        expect(tester.takeException(), isNull);
      } finally {
        await stop(tester, session, api);
      }
    },
  );
  testWidgets(
    'review replacement session removes private editor tied to the previous session',
    (tester) async {
      final api = ReviewAnnualApi(), session = BusinessSession(api: api);
      final nextApi = ReviewAnnualApi()..read = false,
          nextSession = BusinessSession(api: nextApi);
      try {
        await owner.open(tester, api, session);
        await owner.inspect(tester, api);
        await owner.correction(tester);
        await nextSession.load();
        await tester.pumpWidget(
          MaterialApp(
            home: BusinessPayrollAnnualBasisPage(
              session: nextSession,
              employee: actual.copy(api.fixture['sources']['employee']),
              onOriginal: (_) async {},
            ),
          ),
        );
        await tester.pumpAndSettle();
        expect(find.byType(BusinessEditor), findsNothing);
        expect(
          find.text(api.fixture['saved']['details']['verification_note']),
          findsNothing,
        );
        expect(find.text('Jahresquellen nicht freigegeben'), findsOneWidget);
        expect(api.previews, isEmpty);
        expect(tester.takeException(), isNull);
      } finally {
        await stop(tester, session, api);
        nextSession.dispose();
        nextApi.dispose();
      }
    },
  );
  testWidgets(
    'review delayed annual preview cannot restore previous employee data after widget change',
    (tester) async {
      final api = ReviewAnnualApi(), session = BusinessSession(api: api);
      try {
        await owner.open(tester, api, session);
        await owner.inspect(tester, api);
        await holdPreview(tester, api);
        await tester.pumpWidget(
          MaterialApp(
            home: BusinessPayrollAnnualBasisPage(
              session: session,
              employee: {
                ...actual.copy(api.fixture['sources']['employee']),
                'id': 'f' * 32,
                'name': 'Other synthetic employee',
              },
              onOriginal: (_) async {},
            ),
          ),
        );
        await tester.pump();
        api.heldPreview!.complete(actual.copy(api.fixture['preview']));
        await tester.pumpAndSettle();
        expect(find.text('Jahresquelle prüfen'), findsNothing);
        expect(
          find.text(api.fixture['saved']['details']['verification_note']),
          findsNothing,
        );
        expect(api.sent, isEmpty);
        expect(tester.takeException(), isNull);
      } finally {
        await stop(tester, session, api);
      }
    },
  );
  testWidgets(
    'review approve withdrawal with read retained closes private annual correction dialog',
    (tester) async {
      final api = ReviewAnnualApi(), session = BusinessSession(api: api);
      try {
        await owner.open(tester, api, session);
        await owner.inspect(tester, api);
        await owner.correction(tester);
        api.approve = false;
        await session.load();
        await tester.pumpAndSettle();
        expect(session.can('personnel.read'), true);
        expect(find.byType(BusinessEditor), findsNothing);
        expect(api.sent, isEmpty);
        expect(tester.takeException(), isNull);
      } finally {
        await stop(tester, session, api);
      }
    },
  );
  testWidgets(
    'review delayed annual preview cannot restore a write workflow after approval withdrawal',
    (tester) async {
      final api = ReviewAnnualApi(), session = BusinessSession(api: api);
      try {
        await owner.open(tester, api, session);
        await owner.inspect(tester, api);
        await holdPreview(tester, api);
        api.approve = false;
        await session.load();
        await tester.pump();
        api.heldPreview!.complete(actual.copy(api.fixture['preview']));
        await tester.pumpAndSettle();
        expect(session.can('personnel.read'), true);
        expect(find.text('Jahresquelle prüfen'), findsNothing);
        expect(find.text('Geprüfte Jahresquelle festhalten'), findsNothing);
        expect(api.sent, isEmpty);
        expect(tester.takeException(), isNull);
      } finally {
        await stop(tester, session, api);
      }
    },
  );
  testWidgets(
    'review delayed original authorization cannot dispatch private download after background',
    (tester) async {
      final api = ReviewAnnualApi(),
          session = BusinessSession(api: api),
          originals = <Map<String, dynamic>>[];
      try {
        await owner.open(
          tester,
          api,
          session,
          onOriginal: (file) async {
            originals.add(file);
          },
        );
        await owner.inspect(tester, api);
        api.heldSources = Completer<dynamic>();
        final file = api.fixture['saved']['sources']['source_files'][0],
            button = find.text('Personaloriginal: ${file['filename']}');
        await tester.ensureVisible(button);
        await tester.pumpAndSettle();
        await tester.tap(button);
        await tester.pump();
        await tester.pump(const Duration(milliseconds: 100));
        owner.background(tester);
        await tester.pump();
        owner.resume(tester);
        await tester.pump();
        api.heldSources!.complete(api.sources());
        await tester.pumpAndSettle();
        expect(originals, isEmpty);
        expect(
          find.text(api.fixture['saved']['details']['verification_note']),
          findsNothing,
        );
        expect(tester.takeException(), isNull);
      } finally {
        await stop(tester, session, api);
      }
    },
  );
  for (final field in ['employee_id', 'kind']) {
    test(
      'review actual annual repeat rejects frozen wrong $field without new POST and retains original nonce',
      () async {
        final api = ReviewAnnualApi()..lose = true,
            session = BusinessSession(api: api);
        addTearDown(session.dispose);
        addTearDown(api.dispose);
        await session.load();
        final key = 'payroll-annual-basis-${api.employeeId}',
            body = actual.copy(api.fixture['command'])..remove('request_id');
        body[field] = field == 'employee_id'
            ? 'f' * 32
            : 'unsupported_annual_kind';
        await expectLater(
          session.command(key, '/payroll/annual-facts', body),
          throwsA(isA<ApiException>()),
        );
        await expectLater(
          session.repeatPayrollAnnualBasisCommand(api.employeeId),
          throwsA(isA<ApiException>()),
        );
        expect(api.sent.length, 1);
        expect(session.pending(key), true);
        expect(
          session.pendingCommandValues(key, path: '/payroll/annual-facts'),
          body,
        );
      },
    );
  }
  test('review actual annual repeat retains receipt validator against foreign employee kind and year', () async {
    final api = ReviewAnnualApi()..lose = true,
        session = BusinessSession(api: api);
    addTearDown(session.dispose);
    addTearDown(api.dispose);
    await session.load();
    final key = 'payroll-annual-basis-${api.employeeId}',
        body = actual.copy(api.fixture['command'])..remove('request_id');
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
    for (final alter in <void Function(Map<String, dynamic>)>[
      (value) => value['employee_id'] = 'f' * 32,
      (value) => value['kind'] = 'imported_period',
      (value) => value['details']['year'] = 2025,
    ]) {
      api.alterResult = alter;
      await expectLater(
        session.repeatPayrollAnnualBasisCommand(api.employeeId),
        throwsA(isA<ApiException>()),
      );
      expect(session.pending(key), true);
    }
    api.alterResult = null;
    expect(
      await session.repeatPayrollAnnualBasisCommand(api.employeeId),
      api.fixture['saved'],
    );
    expect(api.sent.length, 5);
    expect(session.pending(key), false);
    for (final command in api.sent) {
      expect(command, api.sent.first);
    }
  });
  test('review actual annual repeat rejects a foreign fresh source catalog and preserves exact pending body', () async {
    final api = ReviewAnnualApi()..lose = true,
        session = BusinessSession(api: api);
    addTearDown(session.dispose);
    addTearDown(api.dispose);
    await session.load();
    final key = 'payroll-annual-basis-${api.employeeId}',
        body = actual.copy(api.fixture['command'])..remove('request_id');
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
    api.alterSources = (sources) {
      sources['employee_id'] = 'f' * 32;
    };
    await expectLater(
      session.repeatPayrollAnnualBasisCommand(api.employeeId),
      throwsA(isA<ApiException>()),
    );
    expect(api.sent.length, 1);
    expect(session.pending(key), true);
    api.alterSources = null;
    await session.repeatPayrollAnnualBasisCommand(api.employeeId);
    expect(api.sent.first, api.sent.last);
  });
}

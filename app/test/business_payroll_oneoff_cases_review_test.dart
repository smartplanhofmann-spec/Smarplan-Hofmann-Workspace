import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:smartplan_office/api.dart';
import 'package:smartplan_office/business_payroll_oneoff_cases.dart';
import 'package:smartplan_office/business_session.dart';
import 'package:smartplan_office/business_widgets.dart';

import 'business_payroll_oneoff_cases_test.dart' as owner;

class ReviewOneoffApi extends owner.OneoffApi {
  Completer<dynamic>? heldSources, heldHistory;
  int heldSourceCalls = 0;
  @override
  Future<dynamic> call(String path, [Map<String, dynamic>? body]) async {
    if (path.contains('/payroll/one-off-cases/sources?') &&
        heldSources != null) {
      heldSourceCalls++;
      return heldSources!.future;
    }
    if (path.endsWith('/history') && heldHistory != null) {
      return heldHistory!.future;
    }
    return super.call(path, body);
  }
}

class TrackedSession extends BusinessSession {
  TrackedSession({required super.api});
  final activeListeners = <VoidCallback>{};
  final registeredAt = <VoidCallback, String>{};
  @override
  void addListener(VoidCallback listener) {
    activeListeners.add(listener);
    registeredAt[listener] = StackTrace.current
        .toString()
        .split("\n")
        .where((line) => line.contains("business_"))
        .join("\n");
    super.addListener(listener);
  }

  @override
  void removeListener(VoidCallback listener) {
    activeListeners.remove(listener);
    super.removeListener(listener);
  }
}

Future<void> stop(
  WidgetTester t,
  BusinessSession session,
  OfficeApi api,
) async {
  await t.pumpWidget(const SizedBox.shrink());
  session.dispose();
  api.dispose();
}

Future<void> mount(
  WidgetTester t,
  BusinessSession session, {
  Map<String, dynamic>? employee,
}) async {
  await t.pumpWidget(
    MaterialApp(
      home: BusinessPayrollOneoffCasesPage(
        session: session,
        employee: employee ?? owner.copy(owner.fixture['sources']['employee']),
        initialMonth: '2026-10',
        onOriginal: (_) async {},
        onCalculate: (_) async {},
      ),
    ),
  );
}

Future<void> holdPreview(WidgetTester t, ReviewOneoffApi api) async {
  await owner.prepare(t);
  api.heldPreview = Completer<dynamic>();
  final button = find.text('Einmalbezugsfall unverbindlich prüfen');
  await t.ensureVisible(button);
  await t.pumpAndSettle();
  await t.tap(button);
  await t.pump();
  await t.pump(const Duration(milliseconds: 100));
  expect(api.previews.length, 1);
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  testWidgets(
    'independent v6 session replacement closes editor and detaches old listener',
    (t) async {
      final api = ReviewOneoffApi(), session = TrackedSession(api: api);
      final nextApi = ReviewOneoffApi()..read = false,
          nextSession = BusinessSession(api: nextApi);
      try {
        await owner.open(t, api, session);
        await owner.inspect(t);
        await owner.prepare(t);
        expect(find.byType(BusinessEditor), findsOneWidget);
        await nextSession.load();
        await mount(t, nextSession);
        await t.pumpAndSettle();
        expect(find.byType(BusinessEditor), findsNothing);
        expect(
          session.activeListeners.map(
            (callback) => session.registeredAt[callback],
          ),
          isEmpty,
        );
        expect(
          find.text('Einmalbezugsfälle nicht freigegeben'),
          findsOneWidget,
        );
        expect(
          find.text(owner.fixture['saved']['details']['verification_note']),
          findsNothing,
        );
        api.read = false;
        await session.load();
        await t.pumpAndSettle();
        expect(
          find.text('Einmalbezugsfälle nicht freigegeben'),
          findsOneWidget,
        );
        expect(api.previews, isEmpty);
        expect(api.sent, isEmpty);
        expect(t.takeException(), isNull);
      } finally {
        await stop(t, session, api);
        nextSession.dispose();
        nextApi.dispose();
      }
    },
  );

  testWidgets(
    'independent v6 employee change invalidates pending original preview',
    (t) async {
      final api = ReviewOneoffApi(), session = BusinessSession(api: api);
      try {
        await owner.open(t, api, session);
        await owner.inspect(t);
        await holdPreview(t, api);
        await mount(
          t,
          session,
          employee: {
            ...owner.copy(owner.fixture['sources']['employee']),
            'id': 'f' * 32,
            'name': 'Other synthetic oneoff employee',
          },
        );
        await t.pump();
        api.heldPreview!.complete(
          owner.copy(owner.fixture['correction_preview']),
        );
        await t.pumpAndSettle();
        expect(find.byType(BusinessEditor), findsNothing);
        expect(find.text('Einmalbezugsfall prüfen'), findsNothing);
        expect(find.byType(PayrollOneoffCasePlanView), findsNothing);
        expect(
          find.text(owner.fixture['saved']['details']['verification_note']),
          findsNothing,
        );
        expect(api.sent, isEmpty);
        expect(t.takeException(), isNull);
      } finally {
        await stop(t, session, api);
      }
    },
  );

  testWidgets(
    'independent v6 approve loss with read retained invalidates delayed preview',
    (t) async {
      final api = ReviewOneoffApi(), session = BusinessSession(api: api);
      try {
        await owner.open(t, api, session);
        await owner.inspect(t);
        await holdPreview(t, api);
        api.approve = false;
        await session.load();
        await t.pump();
        expect(session.can('personnel.read'), true);
        expect(session.can('personnel.approve'), false);
        api.heldPreview!.complete(
          owner.copy(owner.fixture['correction_preview']),
        );
        await t.pumpAndSettle();
        expect(find.byType(BusinessEditor), findsNothing);
        expect(find.text('Einmalbezugsfall prüfen'), findsNothing);
        expect(find.byType(PayrollOneoffCasePlanView), findsNothing);
        expect(
          find.text('Geprüften Einmalbezugsfall festhalten'),
          findsNothing,
        );
        expect(api.sent, isEmpty);
        expect(t.takeException(), isNull);
      } finally {
        await stop(t, session, api);
      }
    },
  );

  testWidgets(
    'independent v6 session replacement suppresses delayed private preview error',
    (t) async {
      final api = ReviewOneoffApi(), session = BusinessSession(api: api);
      final nextApi = ReviewOneoffApi()..read = false,
          nextSession = BusinessSession(api: nextApi);
      const secret = 'Synthetischer vertraulicher Altmandant im Einmalfehler';
      try {
        await owner.open(t, api, session);
        await owner.inspect(t);
        await holdPreview(t, api);
        await nextSession.load();
        await mount(t, nextSession);
        await t.pump();
        api.heldPreview!.completeError(const ApiException(400, secret));
        await t.pumpAndSettle();
        expect(find.text(secret), findsNothing);
        expect(find.byType(BusinessEditor), findsNothing);
        expect(
          find.text('Einmalbezugsfälle nicht freigegeben'),
          findsOneWidget,
        );
        expect(api.sent, isEmpty);
        expect(t.takeException(), isNull);
      } finally {
        await stop(t, session, api);
        nextSession.dispose();
        nextApi.dispose();
      }
    },
  );

  testWidgets(
    'independent v6 original callback waits for still valid view after held authorization',
    (t) async {
      final api = ReviewOneoffApi(),
          session = BusinessSession(api: api),
          originals = <Map<String, dynamic>>[];
      try {
        await owner.open(
          t,
          api,
          session,
          onOriginal: (value) async {
            originals.add(value);
          },
        );
        await owner.inspect(t);
        final file = owner.fixture['saved']['sources']['source_files'][0];
        api.heldSources = Completer<dynamic>();
        final button = find.text('Personaloriginal: ${file['filename']}');
        await t.ensureVisible(button);
        await t.pumpAndSettle();
        await t.tap(button);
        await t.pump();
        await t.pump(const Duration(milliseconds: 100));
        expect(api.heldSourceCalls, 1);
        owner.background(t);
        await t.pump();
        api.heldSources!.complete({
          ...owner.copy(owner.fixture['sources']),
          'month': '2026-10',
          'one_off_cases': [owner.copy(owner.fixture['saved'])],
        });
        await t.pumpAndSettle();
        expect(originals, isEmpty);
        expect(find.byType(PayrollOneoffCasePlanView), findsNothing);
        api.heldSources = null;
        owner.resume(t);
        await t.pumpAndSettle();
        expect(originals, isEmpty);
        expect(t.takeException(), isNull);
      } finally {
        await stop(t, session, api);
      }
    },
  );

  testWidgets(
    'independent v6 old private history error stays hidden after context replacement',
    (t) async {
      final api = ReviewOneoffApi(), session = BusinessSession(api: api);
      const secret =
          'Synthetischer vertraulicher historischer Anspruchsvermerk';
      try {
        await owner.open(t, api, session);
        await owner.inspect(t);
        api.heldHistory = Completer<dynamic>();
        final button = find.text('Einmalbezugsfallhistorie öffnen');
        await t.ensureVisible(button);
        await t.pumpAndSettle();
        await t.tap(button);
        await t.pump();
        await t.pump(const Duration(milliseconds: 100));
        await mount(
          t,
          session,
          employee: {
            ...owner.copy(owner.fixture['sources']['employee']),
            'id': 'f' * 32,
            'name': 'Other synthetic employee for historical isolation',
          },
        );
        await t.pump();
        api.heldHistory!.completeError(const ApiException(400, secret));
        await t.pumpAndSettle();
        expect(find.text(secret), findsNothing);
        expect(
          find.text(owner.fixture['saved']['details']['verification_note']),
          findsNothing,
        );
        expect(find.byType(PayrollOneoffCasePlanView), findsNothing);
        expect(t.takeException(), isNull);
      } finally {
        await stop(t, session, api);
      }
    },
  );
}

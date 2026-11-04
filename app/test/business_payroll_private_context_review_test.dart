import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:smartplan_office/api.dart';
import 'package:smartplan_office/business_payroll_calculation_cases.dart';
import 'package:smartplan_office/business_payroll_entitlements.dart';
import 'package:smartplan_office/business_session.dart';
import 'package:smartplan_office/business_widgets.dart';

import 'business_payroll_calculation_cases_test.dart' as cases;
import 'business_payroll_calculation_cases_review_test.dart' as casesReview;
import 'business_payroll_sickness_phases_test.dart' as claims;

class PrivateClaimsApi extends claims.PhasesApi {
  PrivateClaimsApi() : super('phases_v3');
  bool holdSource = false;
  Completer<dynamic>? sourceRelease;
  @override
  Future<dynamic> call(String path, [Map<String, dynamic>? body]) async {
    if (holdSource &&
        path.startsWith('/api/business/payroll/entitlements/sources?')) {
      holdSource = false;
      sourceRelease = Completer<dynamic>();
      return sourceRelease!.future;
    }
    return super.call(path, body);
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

Widget casePage(BusinessSession session, {String? employeeId}) => MaterialApp(
  home: BusinessPayrollCalculationCasesPage(
    session: session,
    employee: {
      ...cases.copy(cases.fixture['sources']['employee']),
      if (employeeId != null) 'id': employeeId,
    },
    initialMonth: '2026-10',
    onOriginal: (_) async {},
    onCalculate: (_) async {},
  ),
);

Widget claimPage(
  BusinessSession session,
  claims.PhasesApi api, {
  String? employeeId,
}) => MaterialApp(
  home: BusinessPayrollEntitlementsPage(
    session: session,
    employee: {
      ...cases.copy(api.value['sources']['employee']),
      if (employeeId != null) 'id': employeeId,
    },
    onOriginal: (_) async {},
  ),
);

Future<void> caseEditor(
  WidgetTester t,
  casesReview.DelayedCasesApi api,
  BusinessSession session,
) async {
  await casesReview.openReviewPage(t, api, session);
  await cases.tapVisible(
    t,
    find.text('Abrechnungsfall 2026-10 · Fassung 1').last,
  );
  await cases.tapVisible(t, find.text('Abrechnungsfall berichtigen'));
  expect(find.byType(BusinessEditor), findsOneWidget);
}

Future<void> heldCasePreview(
  WidgetTester t,
  casesReview.DelayedCasesApi api,
  BusinessSession session,
) async {
  await caseEditor(t, api, session);
  await t.enterText(
    find.byKey(const ValueKey('business-field-correction_reason')),
    'Independent private context review',
  );
  await cases.tapVisible(t, find.text('Angaben übernehmen'));
  await cases.tapVisible(
    t,
    find.text('Pauschalsteuer mit dem tatsächlichen Lohnabschluss erfassen.'),
  );
  await cases.tapVisible(
    t,
    find.text(
      'Ich bestätige die vollständigen tatsächlichen Quellen und ihre Zuordnung.',
    ),
  );
  api.holdPreview = true;
  final button = find.text('Abrechnungsfall unverbindlich prüfen');
  await t.ensureVisible(button);
  await t.pumpAndSettle();
  await t.tap(button);
  await t.pump();
  await t.pump(const Duration(milliseconds: 100));
  expect(api.previewRelease, isNotNull);
}

Future<void> claimEditor(
  WidgetTester t,
  claims.PhasesApi api,
  BusinessSession session,
) async {
  await claims.start(t, api, session);
  await claims.press(t, 'Anspruch korrigieren');
  expect(find.byType(BusinessEditor), findsOneWidget);
}

Future<void> heldClaimPreview(
  WidgetTester t,
  claims.PhasesApi api,
  BusinessSession session,
) async {
  await claims.start(t, api, session);
  await claims.prepareCorrection(t, api);
  api.heldPreview = Completer<dynamic>();
  final button = find.text('Anspruch unverbindlich prüfen');
  await t.ensureVisible(button);
  await t.pumpAndSettle();
  await t.tap(button);
  await t.pump();
  await t.pump(const Duration(milliseconds: 100));
  expect(api.previews.length, 1);
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  for (final change in ['employee', 'session', 'approval']) {
    testWidgets('Source3 $change change closes private correction editor', (
      t,
    ) async {
      final api = casesReview.DelayedCasesApi(),
          session = BusinessSession(api: api);
      final otherApi = casesReview.DelayedCasesApi()..read = false;
      final other = BusinessSession(api: otherApi);
      try {
        await caseEditor(t, api, session);
        if (change == 'employee') {
          await t.pumpWidget(casePage(session, employeeId: 'f' * 32));
        } else if (change == 'session') {
          await other.load();
          await t.pumpWidget(casePage(other));
        } else {
          api.approve = false;
          await session.load();
          expect(session.can('personnel.read'), true);
        }
        await t.pumpAndSettle();
        expect(find.byType(BusinessEditor), findsNothing);
        expect(
          find.byKey(const ValueKey('business-field-verification_note')),
          findsNothing,
        );
        expect(api.sent, isEmpty);
        expect(t.takeException(), isNull);
      } finally {
        await stop(t, session, api);
        other.dispose();
        otherApi.dispose();
      }
    });
    testWidgets('P4 $change change closes private correction editor', (
      t,
    ) async {
      final api = claims.PhasesApi('phases_v3'),
          session = BusinessSession(api: api);
      final otherApi = claims.PhasesApi('phases_v3')..read = false;
      final other = BusinessSession(api: otherApi);
      try {
        await claimEditor(t, api, session);
        if (change == 'employee') {
          await t.pumpWidget(claimPage(session, api, employeeId: 'f' * 32));
        } else if (change == 'session') {
          await other.load();
          await t.pumpWidget(claimPage(other, api));
        } else {
          api.approve = false;
          await session.load();
          expect(session.can('personnel.read'), true);
        }
        await t.pumpAndSettle();
        expect(find.byType(BusinessEditor), findsNothing);
        expect(
          find.byKey(const ValueKey('business-field-verification_note')),
          findsNothing,
        );
        expect(api.sent, isEmpty);
        expect(t.takeException(), isNull);
      } finally {
        await stop(t, session, api);
        other.dispose();
        otherApi.dispose();
      }
    });
  }
  for (final change in ['employee', 'approval']) {
    testWidgets('Source3 late preview cannot cross $change change', (t) async {
      final api = casesReview.DelayedCasesApi(),
          session = BusinessSession(api: api);
      try {
        await heldCasePreview(t, api, session);
        if (change == 'employee') {
          await t.pumpWidget(casePage(session, employeeId: 'f' * 32));
        } else {
          api.approve = false;
          await session.load();
          expect(session.can('personnel.read'), true);
        }
        await t.pump();
        api.previewRelease!.complete(api.heldPreview);
        await t.pumpAndSettle();
        expect(find.text('Abrechnungsfall prüfen'), findsNothing);
        expect(find.text('Konkrete Zuordnung prüfen'), findsNothing);
        expect(find.byType(PayrollCalculationCasePlanView), findsNothing);
        expect(api.sent, isEmpty);
        expect(t.takeException(), isNull);
      } finally {
        await stop(t, session, api);
      }
    });
    testWidgets('P4 late preview cannot cross $change change', (t) async {
      final api = claims.PhasesApi('phases_v3'),
          session = BusinessSession(api: api);
      try {
        await heldClaimPreview(t, api, session);
        if (change == 'employee') {
          await t.pumpWidget(claimPage(session, api, employeeId: 'f' * 32));
        } else {
          api.approve = false;
          await session.load();
          expect(session.can('personnel.read'), true);
        }
        await t.pump();
        api.heldPreview!.complete(cases.copy(api.value['preview']));
        await t.pumpAndSettle();
        expect(find.text('Anspruchsbaustein prüfen'), findsNothing);
        expect(
          find.text('Geprüften Anspruchsbaustein festhalten'),
          findsNothing,
        );
        expect(find.byType(PayrollEntitlementPlanView), findsNothing);
        expect(api.sent, isEmpty);
        expect(t.takeException(), isNull);
      } finally {
        await stop(t, session, api);
      }
    });
  }
  for (final action in ['edit', 'cancel']) {
    testWidgets(
      'Source3 late private $action error is discarded after background',
      (t) async {
        final api = casesReview.DelayedCasesApi(),
            session = BusinessSession(api: api);
        const secret =
            'Synthetic private Source3 action error after context loss';
        try {
          await casesReview.openReviewPage(t, api, session);
          await cases.tapVisible(
            t,
            find.text('Abrechnungsfall 2026-10 · Fassung 1').last,
          );
          final button = find.text(
            action == 'edit'
                ? 'Abrechnungsfall berichtigen'
                : 'Fälschlichen Abrechnungsfall aufheben',
          );
          await t.ensureVisible(button);
          await t.pumpAndSettle();
          api.holdSource = true;
          await t.tap(button);
          await t.pump();
          await t.pump(const Duration(milliseconds: 100));
          expect(api.release, isNotNull);
          casesReview.background(t);
          await t.pump();
          casesReview.resume(t);
          await t.pumpAndSettle();
          api.release!.completeError(const ApiException(400, secret));
          await t.pumpAndSettle();
          expect(find.text(secret), findsNothing);
          expect(api.sent, isEmpty);
          expect(t.takeException(), isNull);
        } finally {
          await stop(t, session, api);
        }
      },
    );
    testWidgets('P4 late private $action error is discarded after background', (
      t,
    ) async {
      final api = PrivateClaimsApi(), session = BusinessSession(api: api);
      const secret = 'Synthetic private P4 action error after context loss';
      try {
        await claims.start(t, api, session);
        final button = find.text(
          action == 'edit'
              ? 'Anspruch korrigieren'
              : 'Fälschlichen Anspruch aufheben',
        );
        await t.ensureVisible(button);
        await t.pumpAndSettle();
        api.holdSource = true;
        await t.tap(button);
        await t.pump();
        await t.pump(const Duration(milliseconds: 100));
        expect(api.sourceRelease, isNotNull);
        casesReview.background(t);
        await t.pump();
        casesReview.resume(t);
        await t.pumpAndSettle();
        api.sourceRelease!.completeError(const ApiException(400, secret));
        await t.pumpAndSettle();
        expect(find.text(secret), findsNothing);
        expect(api.sent, isEmpty);
        expect(t.takeException(), isNull);
      } finally {
        await stop(t, session, api);
      }
    });
  }
}

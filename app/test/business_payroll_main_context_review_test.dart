import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:smartplan_office/api.dart';
import 'package:smartplan_office/business_payroll.dart';
import 'package:smartplan_office/business_payroll_oneoff_cases.dart';
import 'package:smartplan_office/business_session.dart';
import 'package:smartplan_office/business_widgets.dart';

import 'business_editor_context_test.dart' show ListenerSession;
import 'business_payroll_calculation_cases_review_test.dart'
    show background, resume;
import 'business_payroll_oneoff_runs_test.dart' as owner;

class MainContextApi extends owner.OneOffRunApi {
  bool read = true, approve = true, holdPreview = false;
  int generation = 1;
  Completer<dynamic>? release;
  dynamic heldPreview;
  Map<String, dynamic> employee = owner.copy(owner.employee);

  @override
  Future<dynamic> call(String path, [Map<String, dynamic>? body]) async {
    if (path.startsWith('/api/business/capabilities')) {
      final value = owner.copy(await super.call(path, body));
      value['generation'] = generation;
      value['permissions'] = (value['permissions'] as List)
          .where((v) => read || v != 'personnel.read')
          .where((v) => approve || v != 'personnel.approve')
          .toList();
      return value;
    }
    if (path == '/api/business/employees') return [employee];
    if (employee['id'] != owner.id &&
        (path.startsWith('/api/business/payroll/profiles?') ||
            path.startsWith('/api/business/payroll/runs?') ||
            path.startsWith('/api/business/personnel/files?') ||
            path.startsWith('/api/business/personnel/payroll-preparations?'))) {
      return {'employee_id': employee['id'], 'items': []};
    }
    if (path == '/api/business/payroll/preview' && holdPreview) {
      holdPreview = false;
      heldPreview = await super.call(path, body);
      release = Completer<dynamic>();
      return release!.future;
    }
    return super.call(path, body);
  }
}

class MainHarness {
  final api = MainContextApi(), nextApi = MainContextApi();
  late final session = ListenerSession(api: api);
  late final next = ListenerSession(api: nextApi);

  Future<void> mount(
    WidgetTester t,
    BusinessSession active,
    Map<String, dynamic> employee,
  ) => t.pumpWidget(
    MaterialApp(
      home: BusinessPayrollPage(session: active, employee: employee),
    ),
  );

  Future<void> open(WidgetTester t, {bool existingRun = false}) async {
    await t.binding.setSurfaceSize(const Size(1100, 14000));
    api.accepted = existingRun;
    await Future.wait([session.load(), next.load()]);
    await mount(t, session, api.employee);
    await t.pumpAndSettle();
  }

  Future<void> inspectCase(WidgetTester t) async {
    await owner.tapVisible(
      t,
      find.text('Einmalbezugsfälle aus Jahresquellen öffnen'),
    );
    await owner.tapVisible(t, find.text('Einmalbezugsmonat wählen'));
    await t.enterText(find.byType(TextField).first, '2026-10');
    await owner.tapVisible(t, find.text('Monat öffnen'));
    await owner.tapVisible(
      t,
      find.text('Einmalbezugsfall 2026-10 · Fassung 1'),
    );
  }

  Future<void> selectCase(WidgetTester t) async {
    await inspectCase(t);
    await owner.tapVisible(
      t,
      find.text('Lohn mit diesem Einmalbezugsfall berechnen'),
    );
  }

  Future<void> preview(WidgetTester t, {bool correction = false}) async {
    await open(t, existingRun: correction);
    if (!correction) api.holdPreview = true;
    await selectCase(t);
    if (correction) {
      expect(find.byType(BusinessEditor), findsOneWidget);
      await t.enterText(
        find.byKey(const ValueKey('business-field-reason')),
        'Synthetic private correction reason',
      );
      api.holdPreview = true;
      await t.tap(find.text('Speichern'));
      await t.pump();
      await t.pump(const Duration(milliseconds: 100));
    }
    expect(api.release, isNotNull);
    expect(api.previews, 1);
  }

  Future<void> change(WidgetTester t, String change) async {
    switch (change) {
      case 'session':
        expect(next.generation, session.generation);
        expect(next.can('personnel.read'), isTrue);
        await mount(t, next, nextApi.employee);
      case 'employee':
        api.employee = {
          ...api.employee,
          'id': 'f' * 32,
          'name': 'Other synthetic payroll employee',
        };
        await mount(t, session, api.employee);
      case 'read':
        api.read = false;
        await session.load();
      case 'approve':
        api.approve = false;
        await session.load();
        expect(session.can('personnel.read'), isTrue);
      case 'generation':
        api.generation++;
        await session.load();
      case 'background':
        background(t);
        await t.pump();
        resume(t);
    }
    await t.pump();
    await t.pump(const Duration(milliseconds: 400));
  }

  Future<void> dispose(WidgetTester t) async {
    if (api.release case final held? when !held.isCompleted) {
      held.complete(api.heldPreview);
      await t.pumpAndSettle();
    }
    await t.pumpWidget(const SizedBox.shrink());
    session.dispose();
    next.dispose();
    api.dispose();
    nextApi.dispose();
    resume(t);
    await t.pump();
    await t.binding.setSurfaceSize(null);
  }
}

void main() {
  testWidgets(
    'Source4 main unmount closes nested private routes while navigator stays',
    (t) async {
      final h = MainHarness();
      try {
        await h.open(t);
        await h.inspectCase(t);
        await owner.tapVisible(t, find.text('Einmalbezugsfall berichtigen'));
        expect(find.byType(BusinessEditor), findsOneWidget);
        await t.pumpWidget(
          const MaterialApp(
            home: Scaffold(body: Text('Separate synthetic destination')),
          ),
        );
        await t.pumpAndSettle();
        expect(find.byType(BusinessPayrollPage), findsNothing);
        expect(find.byType(BusinessPayrollOneoffCasesPage), findsNothing);
        expect(find.byType(BusinessEditor), findsNothing);
        expect(find.text('Separate synthetic destination'), findsOneWidget);
        expect(h.session.subscriptions, isEmpty);
        expect(h.api.commands, isEmpty);
        expect(t.takeException(), isNull);
      } finally {
        await h.dispose(t);
      }
    },
  );

  testWidgets('Source4 main late preview cannot cross allowed session change', (
    t,
  ) async {
    final h = MainHarness();
    try {
      await h.preview(t);
      await h.change(t, 'session');
      h.api.release!.complete(h.api.heldPreview);
      await t.pumpAndSettle();
      expect(find.text('Unverbindliche Berechnungsvorschau'), findsNothing);
      expect(h.session.subscriptions, isEmpty);
      expect(h.next.subscriptions, hasLength(1));
      expect(h.api.commands, isEmpty);
      expect(h.nextApi.commands, isEmpty);
      expect(t.takeException(), isNull);
    } finally {
      await h.dispose(t);
    }
  });

  for (final change in [
    'employee',
    'read',
    'approve',
    'generation',
    'background',
  ]) {
    testWidgets('Source4 main late preview cannot cross $change change', (
      t,
    ) async {
      final h = MainHarness();
      try {
        await h.preview(t);
        await h.change(t, change);
        h.api.release!.complete(h.api.heldPreview);
        await t.pumpAndSettle();
        expect(find.text('Unverbindliche Berechnungsvorschau'), findsNothing);
        expect(h.api.commands, isEmpty);
        expect(t.takeException(), isNull);
      } finally {
        await h.dispose(t);
      }
    });
  }

  for (final change in [
    'session',
    'employee',
    'read',
    'approve',
    'generation',
    'background',
  ]) {
    testWidgets('Source4 main nested case editor closes on $change change', (
      t,
    ) async {
      final h = MainHarness();
      try {
        await h.open(t);
        await h.inspectCase(t);
        await owner.tapVisible(t, find.text('Einmalbezugsfall berichtigen'));
        expect(find.byType(BusinessEditor), findsOneWidget);
        expect(
          find.byKey(const ValueKey('business-field-verification_note')),
          findsOneWidget,
        );
        await h.change(t, change);
        await t.pumpAndSettle();
        expect(find.byType(BusinessPayrollOneoffCasesPage), findsNothing);
        expect(find.byType(BusinessEditor), findsNothing);
        expect(
          find.byKey(const ValueKey('business-field-verification_note')),
          findsNothing,
        );
        expect(h.api.previews, 0);
        expect(h.api.commands, isEmpty);
        expect(t.takeException(), isNull);
      } finally {
        await h.dispose(t);
      }
    });

    testWidgets('Source4 main correction selector closes on $change change', (
      t,
    ) async {
      final h = MainHarness();
      try {
        await h.open(t, existingRun: true);
        await owner.tapVisible(t, find.text('Monatsberechnung korrigieren'));
        expect(find.byType(BusinessPayrollOneoffCasesPage), findsOneWidget);
        await h.change(t, change);
        await t.pumpAndSettle();
        expect(find.byType(BusinessPayrollOneoffCasesPage), findsNothing);
        expect(find.byType(BusinessEditor), findsNothing);
        expect(h.api.previews, 0);
        expect(h.api.commands, isEmpty);
        expect(t.takeException(), isNull);
      } finally {
        await h.dispose(t);
      }
    });

    testWidgets('Source4 main private correction closes on $change change', (
      t,
    ) async {
      final h = MainHarness();
      try {
        await h.open(t, existingRun: true);
        await h.selectCase(t);
        expect(find.byType(BusinessEditor), findsOneWidget);
        await t.enterText(
          find.byKey(const ValueKey('business-field-reason')),
          'Synthetic private correction reason',
        );
        await h.change(t, change);
        await t.pumpAndSettle();
        expect(find.byType(BusinessEditor), findsNothing);
        expect(find.text('Synthetic private correction reason'), findsNothing);
        expect(h.api.previews, 0);
        expect(h.api.commands, isEmpty);
        expect(t.takeException(), isNull);
      } finally {
        await h.dispose(t);
      }
    });

    testWidgets(
      'Source4 main late correction preview is discarded on $change',
      (t) async {
        final h = MainHarness();
        try {
          await h.preview(t, correction: true);
          await h.change(t, change);
          h.api.release!.complete(h.api.heldPreview);
          await t.pumpAndSettle();
          expect(find.byType(BusinessEditor), findsNothing);
          expect(find.text('Unverbindliche Berechnungsvorschau'), findsNothing);
          expect(
            find.text('Synthetic private correction reason'),
            findsNothing,
          );
          expect(h.api.commands, isEmpty);
          expect(t.takeException(), isNull);
        } finally {
          await h.dispose(t);
        }
      },
    );

    testWidgets(
      'Source4 main late private preview error is discarded on $change',
      (t) async {
        final h = MainHarness();
        const secret = 'Synthetic private main payroll preview error';
        try {
          await h.preview(t);
          await h.change(t, change);
          h.api.release!.completeError(const ApiException(400, secret));
          await t.pumpAndSettle();
          expect(find.text(secret), findsNothing);
          expect(find.text('Unverbindliche Berechnungsvorschau'), findsNothing);
          expect(h.api.commands, isEmpty);
          expect(t.takeException(), isNull);
        } finally {
          await h.dispose(t);
        }
      },
    );

    testWidgets(
      'Source4 main late private correction error is discarded on $change',
      (t) async {
        final h = MainHarness();
        const secret = 'Synthetic private main correction error';
        try {
          await h.preview(t, correction: true);
          await h.change(t, change);
          h.api.release!.completeError(const ApiException(400, secret));
          await t.pumpAndSettle();
          expect(find.byType(BusinessEditor), findsNothing);
          expect(find.text(secret), findsNothing);
          expect(find.text('Unverbindliche Berechnungsvorschau'), findsNothing);
          expect(h.api.commands, isEmpty);
          expect(t.takeException(), isNull);
        } finally {
          await h.dispose(t);
        }
      },
    );
  }
}

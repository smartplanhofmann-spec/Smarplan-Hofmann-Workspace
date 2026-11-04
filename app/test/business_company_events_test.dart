import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:smartplan_office/api.dart';
import 'package:smartplan_office/business_assistant.dart';
import 'package:smartplan_office/business_company_event_contract.dart';
import 'package:smartplan_office/business_company_events.dart';
import 'package:smartplan_office/business_session.dart';

import 'business_company_event_contract_test.dart'
    show companyFixture, copyCompany;

class CompanyEventApi extends OfficeApi {
  CompanyEventApi([String scenario = 'approval'])
    : fixture = companyFixture(scenario),
      super(apiVersion: 'v1') {
    token = 'synthetic-company-event-$scenario';
  }
  final Map<String, dynamic> fixture;
  bool readable = true,
      manage = true,
      approve = true,
      sourceRead = true,
      financeRead = true,
      write = true,
      enabled = true,
      readonly = false,
      badReceipt = false;
  int generation = 1;
  int? loseStatus;
  ApiException? rejectBefore;
  String state = 'original';
  String? holdPath;
  Completer<dynamic>? holdRead, holdPost, holdActor;
  final paths = <String>[], posts = <Map<String, dynamic>>[];
  final effects = <String>{};
  Map<String, dynamic>? lastResponse;
  List<Map<String, dynamic>>? ruleRows;
  String get project => fixture['project_id'];
  String get planId => fixture['plans']['items'][0]['id'];
  String get eventId => fixture['events']['items'][0]['id'];
  String get runId => fixture['scan']['id'];
  Map<String, dynamic> get plan => copyCompany(
    state == 'approved'
        ? fixture['approved']
        : state == 'executed'
        ? fixture['plan_after']
        : fixture['plans']['items'][0],
  );
  @override
  Future<dynamic> call(String path, [Map<String, dynamic>? body]) async {
    paths.add(path);
    final uri = Uri.parse(path), p = uri.path;
    if (p == '/api/business/capabilities')
      return {
        'compatibility_mode': 'business',
        'generation': generation,
        'readonly': readonly,
        'features': [
          'company_event_rules',
          'organization_modules',
          'assistant_workflow',
        ],
        'capabilities': ['business_company_events', 'business_assistant'],
        'permissions': [
          if (readable) 'assistant.use',
          if (manage) 'settings.manage',
          if (approve) 'assistant.approve',
          if (sourceRead) 'documents.read',
          if (financeRead) 'finance.read',
          if (write) ...['projects.manage', 'finance.write', 'finance.approve'],
        ],
        'organization': {
          'revision': 1,
          'configured': true,
          'modules': {
            for (final s in BusinessSession.organizationSections)
              s: {'visible': true, 'enabled': enabled},
          },
        },
      };
    if (p == '/api/me')
      return holdActor?.future ?? copyCompany(fixture['actor']);
    if (p == '/api/users')
      return [
        {...fixture['actor'], 'name': 'Synthetic owner'},
      ];
    if (p == '/api/business/articles') return <dynamic>[];
    if (body != null) {
      posts.add({'path': path, 'body': copyCompany(body)});
      if (rejectBefore != null) throw rejectBefore!;
      final short = p.substring('/api/business'.length),
          operation = companyEventOperation(short);
      Map<String, dynamic> result;
      if (operation == 'rule') {
        result = {
          ...copyCompany(fixture['rule']),
          ...copyCompany(body),
          'revision': body['revision'] + 1,
        };
        result.remove('request_id');
        result.remove('confirmation');
        ruleRows = [copyCompany(result)..remove('acceptance')];
      } else if (operation == 'scan') {
        result = copyCompany(fixture['scan']);
      } else if (operation.startsWith('approve:')) {
        state = 'approved';
        result = copyCompany(fixture['approved']);
        result['decision']['reason'] = body['reason'];
      } else if (operation.startsWith('reject:')) {
        result = plan;
        result['status'] = 'rejected';
        result['can_execute'] = false;
        result['decision'] = {
          'plan_id': planId,
          'plan_sha256': body['plan_sha256'],
          'created_by': fixture['actor']['id'],
          'decision': 'rejected',
          'reason': body['reason'],
          'created_at': '2026-11-04T12:00:00Z',
        };
      } else {
        state = 'executed';
        result = copyCompany(fixture['executed']);
      }
      result['acceptance'] = {
        'request_id': body['request_id'],
        'operation': operation,
        'request_hash': companyEventHash([operation, body]),
      };
      if (badReceipt) result['acceptance']['request_hash'] = 'a' * 64;
      effects.add(body['request_id']);
      lastResponse = copyCompany(result);
      if (holdPost != null) return holdPost!.future;
      if (loseStatus != null) {
        final status = loseStatus!;
        loseStatus = null;
        throw ApiException(status, 'Synthetic private lost ACK');
      }
      return result;
    }
    if (holdPath == p && holdRead != null) return holdRead!.future;
    if (p == '/api/business/company-events/status')
      return copyCompany(fixture['status']);
    if (p == '/api/business/company-events/rules')
      return {
        'schema_version': 1,
        'items': ruleRows ?? fixture['rules_after']['items'],
      };
    if (p.endsWith('/history')) return copyCompany(fixture['rule_history']);
    if (p == '/api/business/company-events/plans')
      return {
        'schema_version': 1,
        'items': [plan],
        'next_after': null,
      };
    if (p == '/api/business/company-events/events')
      return copyCompany(fixture['events']);
    if (p == '/api/business/company-events/runs')
      return copyCompany(fixture['runs']);
    if (p == '/api/business/company-events/plans/$planId') return plan;
    if (p == '/api/business/company-events/events/$eventId')
      return copyCompany(fixture['events']['items'][0]);
    if (p == '/api/business/company-events/runs/$runId')
      return copyCompany(fixture['runs']['items'][0]);
    if (p.startsWith('/api/projects/$project/tasks/'))
      return copyCompany(fixture['plan_after']['outcome']['result']);
    throw StateError('Unexpected $path');
  }
}

Future<BusinessSession> companySession(CompanyEventApi api) async {
  final session = BusinessSession(
    api: api,
    projects: [
      {'id': api.project, 'name': 'Synthetic native project'},
    ],
  );
  await session.load();
  return session;
}

Future<void> mountCompany(
  WidgetTester t,
  BusinessSession session, {
  double width = 800,
}) async {
  t.view.physicalSize = Size(width, 900);
  t.view.devicePixelRatio = 1;
  await t.pumpWidget(
    MaterialApp(
      home: BusinessCompanyEventsPage(
        key: const ValueKey('company-events'),
        session: session,
      ),
    ),
  );
  await t.pumpAndSettle();
}

Future<void> clickCompany(WidgetTester t, String title) async {
  final found = find.text(title);
  await showCompany(t, found);
  await t.tap(found.first);
  await t.pumpAndSettle();
}

Future<void> showCompany(WidgetTester t, Finder found) async {
  t.testTextInput.hide();
  await t.pumpAndSettle();
  if (found.evaluate().isEmpty) {
    await t.scrollUntilVisible(
      found,
      400,
      scrollable: find.byType(Scrollable).first,
    );
  }
  await t.ensureVisible(found.first);
  await t.pumpAndSettle();
}

Future<void> removeCompany(
  WidgetTester t,
  List<BusinessSession> sessions,
) async {
  await t.pumpWidget(const SizedBox());
  for (final s in sessions) {
    s.dispose();
    s.api.dispose();
  }
  t.view.resetPhysicalSize();
  t.view.resetDevicePixelRatio();
}

Map<String, dynamic> commandValues(dynamic value) =>
    copyCompany(value)..remove('request_id');

void main() {
  testWidgets(
    'assistant entry closes its private route when parent session is replaced',
    (t) async {
      final firstApi = CompanyEventApi(), nextApi = CompanyEventApi('deny');
      final first = await companySession(firstApi),
          next = await companySession(nextApi);
      var current = first;
      late StateSetter rebuild;
      await t.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: StatefulBuilder(
              builder: (context, setState) {
                rebuild = setState;
                return BusinessAssistantPage(session: current);
              },
            ),
          ),
        ),
      );
      await t.pumpAndSettle();
      await clickCompany(t, 'Unternehmensereignisse öffnen');
      expect(find.byType(BusinessCompanyEventsPage), findsOneWidget);
      rebuild(() => current = next);
      await t.pumpAndSettle();
      expect(find.byType(BusinessCompanyEventsPage), findsNothing);
      await removeCompany(t, [first, next]);
    },
  );
  test('only bound company commands retry original receipt through generation and rights changes', () async {
    final api = CompanyEventApi(), session = await companySession(api);
    addTearDown(() {
      session.dispose();
      api.dispose();
    });
    const path = '/company-events/scan';
    final values = commandValues(api.fixture['scan_command']);
    api.loseStatus = 0;
    await expectLater(
      session.companyEventCommand(path, values),
      throwsA(isA<ApiException>()),
    );
    final key = companyEventCommandKey(path, values);
    expect(session.pending(key), true);
    api.generation++;
    api.manage = false;
    await expectLater(
      session.repeatCompanyEventCommand(key),
      throwsA(isA<ApiException>()),
    );
    expect(api.posts.length, 1);
    expect(session.pending(key), true);
    api.manage = true;
    await session.repeatCompanyEventCommand(key);
    expect(api.posts.length, 2);
    expect(api.posts[0]['body'], api.posts[1]['body']);
    expect(api.effects.length, 1);
    expect(session.pending(key), false);
  });
  test(
    'concurrent same-intent calls share one future and one original nonce',
    () async {
      final api = CompanyEventApi(), session = await companySession(api);
      addTearDown(() {
        session.dispose();
        api.dispose();
      });
      api.holdPost = Completer();
      final values = commandValues(api.fixture['scan_command']);
      final first = session.companyEventCommand('/company-events/scan', values),
          second = session.companyEventCommand('/company-events/scan', values);
      expect(identical(first, second), true);
      await Future<void>.delayed(const Duration(milliseconds: 10));
      expect(api.posts.length, 1);
      expect(
        () => session.companyEventCommand('/company-events/scan', {
          'limit': 50,
          'after': null,
        }),
        throwsA(isA<ApiException>()),
      );
      api.holdPost!.complete(api.lastResponse);
      await first;
      expect(api.effects.length, 1);
    },
  );
  test('wrong receipt remains pending; later exact accepted claim may clear without outcome', () async {
    final api = CompanyEventApi('external_unconfirmed'),
        session = await companySession(api);
    addTearDown(() {
      session.dispose();
      api.dispose();
    });
    final path = '/company-events/plans/${api.planId}/execute',
        values = commandValues(api.fixture['execute_command']);
    api.badReceipt = true;
    await expectLater(
      session.companyEventCommand(path, values),
      throwsA(isA<ApiException>()),
    );
    final key = companyEventCommandKey(path, values);
    expect(session.pending(key), true);
    api.badReceipt = false;
    final result = await session.repeatCompanyEventCommand(key);
    expect(result['status'], 'unconfirmed');
    expect(result['outcome'], null);
    expect(session.pending(key), false);
    expect(api.posts[0]['body'], api.posts[1]['body']);
  });
  test('plan replay rechecks project source, approval and actor rather than global permissions', () async {
    final api = CompanyEventApi(), session = await companySession(api);
    addTearDown(() {
      session.dispose();
      api.dispose();
    });
    final path = '/company-events/plans/${api.planId}/approve',
        values = commandValues(api.fixture['approve_command']);
    api.loseStatus = 0;
    await expectLater(
      session.companyEventCommand(path, values),
      throwsA(isA<ApiException>()),
    );
    final key = companyEventCommandKey(path, values);
    for (final change in ['source', 'approve', 'actor']) {
      api.sourceRead = change != 'source';
      api.approve = change != 'approve';
      if (change == 'actor') {
        api.fixture['actor']['id'] = 'b' * 32;
      }
      await expectLater(
        session.repeatCompanyEventCommand(key),
        throwsA(isA<ApiException>()),
      );
      expect(api.posts.length, 1);
      expect(session.pending(key), true);
    }
  });
  for (final status in [403, 404, 409, 423, 429, 503]) {
    test(
      'uncertain $status preserves the closed event command nonce',
      () async {
        final api = CompanyEventApi(), session = await companySession(api);
        addTearDown(() {
          session.dispose();
          api.dispose();
        });
        api.rejectBefore = ApiException(
          status,
          'Synthetic unresolved response',
        );
        final values = commandValues(api.fixture['scan_command']);
        await expectLater(
          session.companyEventCommand('/company-events/scan', values),
          throwsA(isA<ApiException>()),
        );
        expect(session.pending('company-event-scan'), true);
        api.rejectBefore = null;
        await session.repeatCompanyEventCommand('company-event-scan');
        expect(api.posts[0]['body'], api.posts[1]['body']);
        expect(api.effects.length, 1);
      },
    );
  }
  test(
    'explicit not_accepted releases only the rejected event request',
    () async {
      final api = CompanyEventApi(), session = await companySession(api);
      addTearDown(() {
        session.dispose();
        api.dispose();
      });
      api.rejectBefore = const ApiException(
        409,
        'No acceptance',
        requestResolution: 'not_accepted',
      );
      await expectLater(
        session.companyEventCommand(
          '/company-events/scan',
          commandValues(api.fixture['scan_command']),
        ),
        throwsA(isA<ApiException>()),
      );
      expect(session.pending('company-event-scan'), false);
      expect(api.effects, isEmpty);
    },
  );
  test(
    'rights withdrawn during held current-actor check prevent the POST',
    () async {
      final api = CompanyEventApi(), session = await companySession(api);
      addTearDown(() {
        session.dispose();
        api.dispose();
      });
      api.holdActor = Completer();
      final request = session.companyEventCommand(
        '/company-events/plans/${api.planId}/approve',
        commandValues(api.fixture['approve_command']),
      );
      final expectation = expectLater(request, throwsA(isA<ApiException>()));
      await Future<void>.delayed(const Duration(milliseconds: 10));
      api.approve = false;
      await session.sharedProjectSession(api.project).load();
      api.holdActor!.complete(copyCompany(api.fixture['actor']));
      await expectation;
      expect(api.posts, isEmpty);
    },
  );
  for (final scenario in [
    'approval',
    'external_unknown',
    'external_unconfirmed',
  ]) {
    testWidgets('390px actual $scenario plan original and execution state', (
      t,
    ) async {
      final api = CompanyEventApi(scenario),
          session = await companySession(api);
      if (scenario != 'approval') api.state = 'executed';
      await mountCompany(t, session, width: 390);
      await clickCompany(t, 'Ereignisplan öffnen');
      expect(find.text('Konkreter Ereignisauftrag'), findsOneWidget);
      await showCompany(t, find.text('Belegte Grundlage'));
      expect(find.text('Belegte Grundlage'), findsOneWidget);
      if (scenario == 'approval') {
        await showCompany(t, find.text('Diesen Ereignisplan freigeben'));
        expect(find.text('Diesen Ereignisplan freigeben'), findsOneWidget);
      } else {
        await showCompany(t, find.textContaining('nicht als Erfolg'));
        expect(find.text('Freigegebenen Ereignisplan ausführen'), findsNothing);
        expect(find.text('Diesen Ereignisplan freigeben'), findsNothing);
        expect(find.textContaining('nicht als Erfolg'), findsOneWidget);
      }
      expect(t.takeException(), isNull);
      await removeCompany(t, [session]);
    });
  }
  testWidgets(
    'rule creation, history and scan all require explicit confirmations',
    (t) async {
      final api = CompanyEventApi(), session = await companySession(api);
      await mountCompany(t, session);
      await clickCompany(t, 'Unternehmensregel anlegen');
      expect(
        find.text('Neue Unternehmensregelfassung speichern'),
        findsOneWidget,
      );
      Finder input(String label) => find.byWidgetPredicate(
        (w) => w is TextField && w.decoration?.labelText == label,
      );
      await t.enterText(
        input('Regelbezeichnung'),
        'Synthetic native accepted rule',
      );
      await t.ensureVisible(input('Aufgabentitel'));
      await t.enterText(input('Aufgabentitel'), 'Actual native follow-up');
      expect(api.posts, isEmpty);
      await clickCompany(
        t,
        'Ich bestätige diese Unternehmensregel, ihre Zuständigkeit und zulässige Wirkung.',
      );
      await clickCompany(t, 'Neue Unternehmensregelfassung speichern');
      expect(
        api.posts.single['body']['template']['title'],
        'Actual native follow-up',
      );
      expect(api.posts.single['body']['confirmation'], true);
      await clickCompany(t, 'Ereignislauf starten');
      expect(api.posts.length, 1);
      await clickCompany(
        t,
        'Ich starte die aktuelle Quellenprüfung und bestätige die mögliche Wirkung gespeicherter Automatikregeln.',
      );
      await clickCompany(t, 'Ereignislauf verbindlich starten');
      expect(api.posts.length, 2);
      expect(api.posts.last['body'].keys.toSet(), {
        'request_id',
        'limit',
        'after',
      });
      expect(find.text('Abfragestatus: Vollständig'), findsOneWidget);
      await removeCompany(t, [session]);
    },
  );
  testWidgets(
    'lost ACK survives closing page and repeats exact original body',
    (t) async {
      final api = CompanyEventApi(), session = await companySession(api);
      await mountCompany(t, session);
      await clickCompany(t, 'Ereignislauf starten');
      await clickCompany(
        t,
        'Ich starte die aktuelle Quellenprüfung und bestätige die mögliche Wirkung gespeicherter Automatikregeln.',
      );
      api.loseStatus = 0;
      await clickCompany(t, 'Ereignislauf verbindlich starten');
      expect(find.text('Unbestätigter Originalauftrag'), findsOneWidget);
      await t.pumpWidget(const SizedBox());
      await mountCompany(t, session);
      api.generation++;
      await clickCompany(t, 'Originalauftrag unverändert erneut senden');
      // A newly discovered generation invalidates the old screen before POST.
      // The next explicit retry in the refreshed context keeps the same nonce.
      expect(api.posts.length, 1);
      expect(session.pending('company-event-scan'), true);
      await clickCompany(t, 'Originalauftrag unverändert erneut senden');
      expect(api.posts.length, 2);
      expect(api.posts[0]['body'], api.posts[1]['body']);
      expect(api.effects.length, 1);
      await removeCompany(t, [session]);
    },
  );
  for (final change in [
    'session',
    'background',
    'generation',
    'read',
    'write',
    'source',
  ]) {
    for (final response in ['success', 'error']) {
      testWidgets('late private plan $response discarded after $change', (
        t,
      ) async {
        final api = CompanyEventApi(), session = await companySession(api);
        await mountCompany(t, session);
        api.holdPath = '/api/business/company-events/plans/${api.planId}';
        api.holdRead = Completer();
        await t.tap(find.text('Ereignisplan öffnen'));
        await t.pump();
        await t.pump(const Duration(milliseconds: 20));
        final sessions = [session];
        if (change == 'session') {
          final nextApi = CompanyEventApi('deny'),
              next = await companySession(nextApi);
          sessions.add(next);
          await mountCompany(t, next);
        } else if (change == 'background') {
          t.binding.handleAppLifecycleStateChanged(AppLifecycleState.paused);
          await t.pump();
        } else {
          if (change == 'generation') api.generation++;
          if (change == 'read') api.readable = false;
          if (change == 'write') api.readonly = true;
          if (change == 'source') api.sourceRead = false;
          await session.load();
          await t.pump();
        }
        if (response == 'error') {
          api.holdRead!.completeError(
            const ApiException(502, 'PRIVATE LATE SOURCE MESSAGE'),
          );
        } else {
          api.holdRead!.complete(api.plan);
        }
        await t.pumpAndSettle();
        expect(find.text('Konkreter Ereignisauftrag'), findsNothing);
        expect(find.text('PRIVATE LATE SOURCE MESSAGE'), findsNothing);
        expect(find.text('Diesen Ereignisplan freigeben'), findsNothing);
        expect(t.takeException(), isNull);
        if (change == 'background') {
          t.binding.handleAppLifecycleStateChanged(AppLifecycleState.resumed);
          await t.pump();
        }
        await removeCompany(t, sessions);
      });
    }
  }
  testWidgets(
    'approve-only withdrawal closes a private reason editor with read retained',
    (t) async {
      final api = CompanyEventApi(), session = await companySession(api);
      await mountCompany(t, session);
      await clickCompany(t, 'Ereignisplan öffnen');
      await clickCompany(t, 'Diesen Ereignisplan freigeben');
      await t.enterText(find.byType(TextField), 'PRIVATE REVIEW NOTE');
      api.approve = false;
      await session.load();
      await t.pumpAndSettle();
      expect(find.text('PRIVATE REVIEW NOTE'), findsNothing);
      expect(find.text('Konkrete Ereignisfreigabe speichern'), findsNothing);
      expect(api.posts, isEmpty);
      await removeCompany(t, [session]);
    },
  );
  testWidgets(
    'silent source right loss after held GET is checked before disclosure',
    (t) async {
      final api = CompanyEventApi(), session = await companySession(api);
      await mountCompany(t, session);
      api.holdPath = '/api/business/company-events/plans/${api.planId}';
      api.holdRead = Completer();
      await t.tap(find.text('Ereignisplan öffnen'));
      await t.pump();
      await t.pump(const Duration(milliseconds: 20));
      api.sourceRead = false;
      api.holdRead!.complete(api.plan);
      await t.pumpAndSettle();
      expect(find.text('Konkreter Ereignisauftrag'), findsNothing);
      expect(find.textContaining('Original source text'), findsNothing);
      await removeCompany(t, [session]);
    },
  );
  for (final change in [
    'session',
    'background',
    'generation',
    'read',
    'approve',
    'module',
  ]) {
    for (final response in ['success', 'error']) {
      testWidgets(
        'held approval $response never restores private page after $change',
        (t) async {
          final api = CompanyEventApi(), session = await companySession(api);
          await mountCompany(t, session);
          await clickCompany(t, 'Ereignisplan öffnen');
          await clickCompany(t, 'Diesen Ereignisplan freigeben');
          await t.enterText(
            find.byType(TextField),
            'PRIVATE HELD APPROVAL NOTE',
          );
          await clickCompany(
            t,
            'Ich habe diesen Ereignisplan, seine Quellen und Zuständigkeit geprüft.',
          );
          api.holdPost = Completer();
          await t.tap(find.text('Konkrete Ereignisfreigabe speichern'));
          await t.pump();
          await t.pump(const Duration(milliseconds: 20));
          expect(api.posts.length, 1);
          final sessions = [session];
          if (change == 'session') {
            final next = await companySession(CompanyEventApi('deny'));
            sessions.add(next);
            await mountCompany(t, next);
          } else if (change == 'background') {
            t.binding.handleAppLifecycleStateChanged(AppLifecycleState.paused);
            await t.pump();
          } else {
            if (change == 'generation') api.generation++;
            if (change == 'read') api.readable = false;
            if (change == 'approve') api.approve = false;
            if (change == 'module') api.enabled = false;
            await session.load();
            await t.pump();
          }
          if (response == 'success')
            api.holdPost!.complete(api.lastResponse);
          else
            api.holdPost!.completeError(
              const ApiException(502, 'PRIVATE LATE APPROVAL ERROR'),
            );
          await t.pumpAndSettle();
          expect(find.text('PRIVATE HELD APPROVAL NOTE'), findsNothing);
          expect(find.text('PRIVATE LATE APPROVAL ERROR'), findsNothing);
          expect(find.text('Gespeicherte Entscheidung'), findsNothing);
          expect(
            find.text('Konkrete Ereignisfreigabe speichern'),
            findsNothing,
          );
          expect(t.takeException(), isNull);
          if (change == 'background') {
            t.binding.handleAppLifecycleStateChanged(AppLifecycleState.resumed);
            await t.pump();
          }
          await removeCompany(t, sessions);
        },
      );
    }
  }
  for (final change in ['session', 'background', 'generation', 'approve']) {
    testWidgets('held authorization cannot start a new POST after $change', (
      t,
    ) async {
      final api = CompanyEventApi(), session = await companySession(api);
      await mountCompany(t, session);
      await clickCompany(t, 'Ereignisplan öffnen');
      await clickCompany(t, 'Diesen Ereignisplan freigeben');
      await t.enterText(find.byType(TextField), 'PRIVATE PRE-FLIGHT NOTE');
      await clickCompany(
        t,
        'Ich habe diesen Ereignisplan, seine Quellen und Zuständigkeit geprüft.',
      );
      api.holdActor = Completer();
      await t.tap(find.text('Konkrete Ereignisfreigabe speichern'));
      await t.pump();
      await t.pump(const Duration(milliseconds: 20));
      expect(api.posts, isEmpty);
      final sessions = [session];
      if (change == 'session') {
        final next = await companySession(CompanyEventApi('deny'));
        sessions.add(next);
        await mountCompany(t, next);
      } else if (change == 'background') {
        t.binding.handleAppLifecycleStateChanged(AppLifecycleState.paused);
        await t.pump();
      } else {
        if (change == 'generation')
          api.generation++;
        else
          api.approve = false;
        await session.load();
        await t.pump();
      }
      api.holdActor!.complete(copyCompany(api.fixture['actor']));
      await t.pumpAndSettle();
      expect(api.posts, isEmpty);
      expect(find.text('PRIVATE PRE-FLIGHT NOTE'), findsNothing);
      if (change == 'background') {
        t.binding.handleAppLifecycleStateChanged(AppLifecycleState.resumed);
        await t.pump();
      }
      await removeCompany(t, sessions);
    });
  }
}

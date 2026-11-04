import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:smartplan_office/api.dart';
import 'package:smartplan_office/business_company_event_contract.dart';
import 'package:smartplan_office/business_company_events.dart';

import 'business_company_event_contract_test.dart'
    show companyFixture, copyCompany;
import 'business_company_events_test.dart'
    show
        CompanyEventApi,
        companySession,
        mountCompany,
        clickCompany,
        removeCompany,
        commandValues;

class IndependentProjectApi extends CompanyEventApi {
  IndependentProjectApi([super.scenario]);
  bool projectSource = true, projectApprove = true, projectWrite = true;
  @override
  Future<dynamic> call(String path, [Map<String, dynamic>? body]) async {
    final answer = await super.call(path, body), uri = Uri.parse(path);
    if (uri.path == '/api/business/capabilities' &&
        uri.queryParameters['project_id'] == project) {
      final value = copyCompany(answer);
      value['permissions'] = (value['permissions'] as List)
          .where(
            (permission) =>
                (projectSource || permission != 'documents.read') &&
                (projectApprove || permission != 'assistant.approve') &&
                (projectWrite || permission != 'projects.manage'),
          )
          .toList();
      return value;
    }
    return answer;
  }
}

Future<void> openDecision(WidgetTester tester) async {
  await clickCompany(tester, 'Ereignisplan öffnen');
  await clickCompany(tester, 'Diesen Ereignisplan freigeben');
  await tester.enterText(
    find.byType(TextField),
    'INDEPENDENT PRIVATE DECISION',
  );
}

Finder ruleTitle() => find.byWidgetPredicate(
  (widget) =>
      widget is TextField && widget.decoration?.labelText == 'Regelbezeichnung',
);

void main() {
  test('unconfirmed original execution cannot be relabelled as succeeded without an outcome', () {
    final original = copyCompany(
      companyFixture('external_unconfirmed')['plan_after'],
    );
    expect(original['execution'], isNotNull);
    expect(original['outcome'], isNull);
    companyEventPlan(original);
    final contradictory = copyCompany(original)..['status'] = 'succeeded';
    expect(() => companyEventPlan(contradictory), throwsA(isA<ApiException>()));
  });

  testWidgets(
    'contradictory accepted claim never renders a successful action in the native overview',
    (t) async {
      final api = CompanyEventApi('external_unconfirmed'),
          session = await companySession(api);
      api.fixture['plan_after']['status'] = 'succeeded';
      api.state = 'executed';
      await mountCompany(t, session, width: 390);
      expect(find.text('Status: Erfolgreich ausgeführt'), findsNothing);
      expect(find.text('Freigegebenen Ereignisplan ausführen'), findsNothing);
      expect(api.posts, isEmpty);
      await removeCompany(t, [session]);
    },
  );

  test('an actually successful historical execution remains valid after source staleness or restore suspension', () {
    final original = copyCompany(companyFixture('auto')['plan_after']);
    expect(original['execution'], isNotNull);
    expect(original['outcome']['status'], 'succeeded');
    for (final status in ['stale', 'suspended_after_restore']) {
      final historic = copyCompany(original)
        ..['status'] = status
        ..['source_current'] = false;
      expect(companyEventPlan(historic)['outcome'], original['outcome']);
    }
  });

  for (final change in ['source', 'approve']) {
    testWidgets(
      'project-only $change withdrawal clears private editor while global rights remain',
      (t) async {
        final api = IndependentProjectApi(),
            session = await companySession(api);
        await mountCompany(t, session);
        await openDecision(t);
        if (change == 'source') api.projectSource = false;
        if (change == 'approve') api.projectApprove = false;
        await session.sharedProjectSession(api.project).load();
        await t.pumpAndSettle();
        expect(session.can('documents.read'), true);
        expect(session.can('assistant.approve'), true);
        expect(find.text('INDEPENDENT PRIVATE DECISION'), findsNothing);
        expect(find.text('Konkrete Ereignisfreigabe speichern'), findsNothing);
        expect(api.posts, isEmpty);
        await removeCompany(t, [session]);
      },
    );
  }

  test('project write right disappearing during actor read prevents a fresh command', () async {
    final api = IndependentProjectApi(), session = await companySession(api);
    addTearDown(() {
      session.dispose();
      api.dispose();
    });
    api.holdActor = Completer();
    final request = session.companyEventCommand(
      '/company-events/plans/${api.planId}/approve',
      commandValues(api.fixture['approve_command']),
    );
    final checked = expectLater(request, throwsA(isA<ApiException>()));
    await Future<void>.delayed(const Duration(milliseconds: 10));
    api.projectWrite = false;
    await session.sharedProjectSession(api.project).load();
    expect(session.canWrite('projects.manage'), true);
    api.holdActor!.complete(copyCompany(api.fixture['actor']));
    await checked;
    expect(api.posts, isEmpty);
    expect(session.pendingCompanyEventCommands, isEmpty);
  });

  for (final response in ['success', 'error']) {
    testWidgets(
      'older plan $response cannot replace or erase a newly entered rule',
      (t) async {
        final api = CompanyEventApi(), session = await companySession(api);
        await mountCompany(t, session);
        api.holdPath = '/api/business/company-events/plans/${api.planId}';
        api.holdRead = Completer();
        await t.tap(find.text('Ereignisplan öffnen'));
        await t.pump();
        await t.pump(const Duration(milliseconds: 20));
        await t.tap(find.text('Zur Übersicht'));
        await t.pumpAndSettle();
        await clickCompany(t, 'Unternehmensregel anlegen');
        await t.enterText(ruleTitle(), 'NEW INDEPENDENT RULE');
        if (response == 'success') {
          api.holdRead!.complete(api.plan);
        } else {
          api.holdRead!.completeError(
            const ApiException(502, 'OLD PRIVATE ERROR'),
          );
        }
        await t.pumpAndSettle();
        expect(find.text('NEW INDEPENDENT RULE'), findsOneWidget);
        expect(find.text('Konkreter Ereignisauftrag'), findsNothing);
        expect(find.text('OLD PRIVATE ERROR'), findsNothing);
        expect(
          find.textContaining('Der Vorgang konnte nicht sicher bestätigt'),
          findsNothing,
        );
        expect(api.posts, isEmpty);
        await removeCompany(t, [session]);
      },
    );
  }

  for (final response in ['success', 'error']) {
    testWidgets(
      'late approval $response belongs to its original pending operation and preserves newer editor',
      (t) async {
        final api = CompanyEventApi(), session = await companySession(api);
        await mountCompany(t, session);
        await openDecision(t);
        await clickCompany(
          t,
          'Ich habe diesen Ereignisplan, seine Quellen und Zuständigkeit geprüft.',
        );
        api.holdPost = Completer();
        await t.tap(find.text('Konkrete Ereignisfreigabe speichern'));
        await t.pump();
        await t.pump(const Duration(milliseconds: 20));
        expect(api.posts.length, 1);
        await t.tap(find.text('Zur Übersicht'));
        await t.pumpAndSettle();
        await clickCompany(t, 'Unternehmensregel anlegen');
        await t.enterText(ruleTitle(), 'NEW RULE DURING ORIGINAL APPROVAL');
        if (response == 'success') {
          api.holdPost!.complete(api.lastResponse);
        } else {
          api.holdPost!.completeError(
            const ApiException(503, 'OLD APPROVAL PRIVATE ERROR'),
          );
        }
        await t.pumpAndSettle();
        expect(find.text('NEW RULE DURING ORIGINAL APPROVAL'), findsOneWidget);
        expect(find.text('Gespeicherte Entscheidung'), findsNothing);
        expect(find.text('OLD APPROVAL PRIVATE ERROR'), findsNothing);
        expect(
          session.pendingCompanyEventCommands.length,
          response == 'success' ? 0 : 1,
        );
        expect(api.posts.length, 1);
        await removeCompany(t, [session]);
      },
    );
  }

  for (final change in ['session', 'background', 'manager']) {
    testWidgets('private rule draft is erased after $change', (t) async {
      final api = CompanyEventApi(), session = await companySession(api);
      final sessions = [session];
      await mountCompany(t, session);
      await clickCompany(t, 'Unternehmensregel anlegen');
      await t.enterText(ruleTitle(), 'PRIVATE RULE ORIGINAL');
      if (change == 'session') {
        final replacement = await companySession(CompanyEventApi('deny'));
        sessions.add(replacement);
        await mountCompany(t, replacement);
        api.readable = false;
        await session.load();
        await t.pumpAndSettle();
        expect(find.text('Ereignisplan öffnen'), findsOneWidget);
      } else if (change == 'background') {
        t.binding.handleAppLifecycleStateChanged(AppLifecycleState.paused);
        await t.pumpAndSettle();
        t.binding.handleAppLifecycleStateChanged(AppLifecycleState.resumed);
        await t.pumpAndSettle();
      } else {
        api.manage = false;
        await session.load();
        await t.pumpAndSettle();
        expect(session.can('assistant.use'), true);
      }
      expect(find.text('PRIVATE RULE ORIGINAL'), findsNothing);
      expect(find.byType(CompanyEventRuleEditor), findsNothing);
      expect(api.posts, isEmpty);
      expect(t.takeException(), isNull);
      await removeCompany(t, sessions);
    });
  }

  test('three pending operation kinds preserve distinct original bodies and reject crossed receipts', () async {
    final api = CompanyEventApi(), session = await companySession(api);
    addTearDown(() {
      session.dispose();
      api.dispose();
    });
    final paths = [
      '/company-events/rules',
      '/company-events/scan',
      '/company-events/plans/${api.planId}/approve',
    ];
    final bodies = [
      'rule_command',
      'scan_command',
      'approve_command',
    ].map((key) => commandValues(api.fixture[key])).toList();
    for (var i = 0; i < paths.length; i++) {
      api.loseStatus = 0;
      await expectLater(
        session.companyEventCommand(paths[i], bodies[i]),
        throwsA(isA<ApiException>()),
      );
    }
    final keys = List.generate(
      paths.length,
      (i) => companyEventCommandKey(paths[i], bodies[i]),
    );
    expect(session.pendingCompanyEventCommands.length, 3);
    expect(api.posts.map((v) => v['body']['request_id']).toSet().length, 3);
    api.holdPost = Completer();
    final crossed = session.repeatCompanyEventCommand(keys[2]);
    final rejected = expectLater(crossed, throwsA(isA<ApiException>()));
    await Future<void>.delayed(const Duration(milliseconds: 10));
    final wrong = copyCompany(api.lastResponse);
    wrong['acceptance'] = {
      'operation': 'scan',
      'request_id': api.posts[1]['body']['request_id'],
      'request_hash': companyEventHash(['scan', api.posts[1]['body']]),
    };
    api.holdPost!.complete(wrong);
    await rejected;
    expect(session.pendingCompanyEventCommands.length, 3);
    api.holdPost = null;
    for (final i in [1, 2, 0]) {
      await session.repeatCompanyEventCommand(keys[i]);
      expect(api.posts.last['body'], api.posts[i]['body']);
      expect(session.pending(keys[i]), false);
    }
    expect(session.pendingCompanyEventCommands, isEmpty);
    expect(api.effects.length, 3);
  });
}

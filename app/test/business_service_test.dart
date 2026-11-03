import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:smartplan_office/api.dart';
import 'package:smartplan_office/business_service.dart';
import 'package:smartplan_office/business_session.dart';

const caseId = 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',
    project = 'bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb',
    customer = 'cccccccccccccccccccccccccccccccc',
    actor = 'dddddddddddddddddddddddddddddddd',
    eventId = 'eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee';
final hash = 'f' * 64;
Map<String, dynamic> record({int revision = 1, String status = 'open'}) => {
  'id': caseId,
  'revision': revision,
  'source_sha256': hash,
  'customer_id': customer,
  'customer_name': 'Synthetischer Kunde',
  'person_id': null,
  'project_id': project,
  'asset_id': null,
  'contract_id': null,
  'visit_id': null,
  'inquiry_id': null,
  'defect_id': null,
  'title': 'Synthetische Reklamation',
  'kind': 'complaint',
  'priority': 'high',
  'responsible_id': actor,
  'responsible_name': 'Synthetische Leitung',
  'description': 'Die Anlage tropft.',
  'follow_up_on': '2026-11-01',
  'status': status,
  'resolution': ['resolved', 'closed'].contains(status)
      ? 'Dichtung ersetzt.'
      : '',
  'overdue': true,
  'links': [],
  'allowed_transitions': const {
    'open': ['triaged', 'cancelled'],
    'triaged': ['resolved', 'waiting_customer'],
    'resolved': ['closed', 'triaged'],
    'closed': ['triaged'],
  }[status],
};

class ServiceApi extends OfficeApi {
  ServiceApi() : super(apiVersion: 'v1') {
    token = 'synthetic-service-native-token';
  }
  int revision = 1, generation = 1;
  String status = 'open';
  bool allowed = true, lose = false, enabled = true;
  final commands = <Map<String, dynamic>>[], reads = <String>[];
  final versions = <Map<String, dynamic>>[record()];
  @override
  Future<dynamic> call(String path, [Map<String, dynamic>? body]) async {
    reads.add(path);
    if (path.startsWith('/api/business/capabilities'))
      return {
        'compatibility_mode': 'business',
        'generation': generation,
        'readonly': false,
        'features': ['service_cases', 'organization_modules'],
        'organization': {
          'revision': 1,
          'configured': true,
          'modules': {
            for (final section in BusinessSession.organizationSections)
              section: {'enabled': enabled, 'visible': true},
          },
        },
        'capabilities': ['business_service'],
        'permissions': allowed
            ? [
                'contacts.read',
                'contacts.write',
                'documents.read',
                'documents.write',
                'planning.write',
                'projects.manage',
              ]
            : [],
      };
    if (path == '/api/me') return {'role': 'owner', 'id': actor};
    if (path.startsWith('/api/business/service/options'))
      return {
        'customer_id': customer,
        'project_id': project,
        'customers': [
          {'id': customer, 'name': 'Synthetischer Kunde', 'persons': []},
        ],
        'projects': [
          {
            'id': project,
            'name': 'Synthetisches Projekt',
            'customer_id': customer,
          },
        ],
        'responsibles': [
          {'id': actor, 'email': 'owner@example.test'},
        ],
        'assets': [],
        'contracts': [],
        'visits': [],
        'defects': [],
        'reports': [],
        'employees': [],
        'resources': [],
        'inquiries': [],
      };
    if (path == '/api/business/service/cases/$caseId')
      return record(revision: revision, status: status);
    if (path == '/api/business/service/cases/$caseId/history')
      return {'versions': versions, 'events': []};
    if (path.startsWith('/api/business/service/cases?'))
      return {
        'items': [record(revision: revision, status: status)],
        'summary': {
          'open_count': 1,
          'overdue_count': 1,
          'as_of': '2026-11-03T10:00:00Z',
        },
      };
    if (path == '/api/business/service/cases/$caseId/transition' ||
        path == '/api/business/service/cases/$caseId/dispatch') {
      commands.add(jsonDecode(jsonEncode(body)) as Map<String, dynamic>);
      if (commands
              .where((entry) => entry['request_id'] == body!['request_id'])
              .length ==
          1) {
        revision++;
        status = path.endsWith('/dispatch') ? 'planned' : body!['status'];
        versions.add(record(revision: revision, status: status));
      }
      if (lose) {
        lose = false;
        throw const ApiException(0, 'Erfolgsantwort verloren');
      }
      return {
        'case': record(revision: revision, status: status),
        if (path.endsWith('/dispatch')) 'link': {'target_id': eventId},
      };
    }
    throw StateError(path);
  }
}

void main() {
  test('origin and customer remain explicit and status uses current allowed transitions', () {
    final value = serviceCaseValues(
      {
        'title': 'Störung',
        'kind': 'complaint',
        'priority': 'high',
        'responsible_id': actor,
        'follow_up_on': '',
      },
      {'customer_id': customer, 'project_id': project, 'defect_id': eventId},
    );
    expect(value['defect_id'], eventId);
    expect(value['follow_up_on'], null);
    expect(
      () => serviceCaseValues(
        {
          'title': 'x',
          'kind': 'complaint',
          'priority': 'high',
          'responsible_id': actor,
        },
        {'customer_id': customer, 'defect_id': eventId, 'inquiry_id': caseId},
      ),
      throwsFormatException,
    );
    expect(
      () => serviceTransitionValues(record(), {
        'status': 'closed',
        'reason': 'Skip',
        'resolution': 'Fertig',
      }),
      throwsFormatException,
    );
    expect(
      () => serviceTransitionValues(record(status: 'triaged'), {
        'status': 'resolved',
        'reason': 'Prüfung',
        'resolution': '',
      }),
      throwsFormatException,
    );
  });
  test(
    'activity acknowledgement binds immutable event and same case revision',
    () {
      final body = {
            ...serviceBound(record()),
            'kind': 'call',
            'text': 'Rücksprache',
            'occurred_on': '2026-11-03',
          },
          response = {
            'case': record(),
            'event': {
              'id': eventId,
              'case_id': caseId,
              'kind': 'call',
              'values': {'text': 'Rücksprache', 'occurred_on': '2026-11-03'},
            },
          };
      expect(
        serviceReceipt('/service/cases/$caseId/events', body, response),
        response,
      );
      expect(
        () => serviceReceipt('/service/cases/$caseId/events', body, {
          ...response,
          'event': {
            'id': eventId,
            'case_id': customer,
            'kind': 'call',
            'values': {'text': 'Rücksprache', 'occurred_on': '2026-11-03'},
          },
        }),
        throwsA(isA<ApiException>()),
      );
    },
  );
  for (final scoped in [false, true]) {
    test(
      'lost transition retries exact nonce with fresh ${scoped ? 'project' : 'central'} session rights',
      () async {
        final api = ServiceApi()..lose = true,
            session = BusinessSession(
              api: api,
              projectId: scoped ? project : null,
            );
        addTearDown(session.dispose);
        addTearDown(api.dispose);
        await session.load();
        final body = serviceTransitionValues(record(), {
          'status': 'triaged',
          'reason': 'Problem geprüft',
          'resolution': '',
        });
        await expectLater(
          session.command(
            'service-transition-test',
            '/service/cases/$caseId/transition',
            body,
            validateResult: (value) => serviceReceipt(
              '/service/cases/$caseId/transition',
              body,
              value,
            ),
          ),
          throwsA(isA<ApiException>()),
        );
        api.allowed = false;
        await expectLater(
          session.repeatServiceCommand('service-transition-test'),
          throwsA(isA<ApiException>()),
        );
        expect(session.pending('service-transition-test'), true);
        expect(api.commands.length, 1);
        api.allowed = true;
        await session.repeatServiceCommand('service-transition-test');
        expect(api.commands.length, 2);
        expect(api.commands[1], api.commands[0]);
        expect(api.revision, 2);
        expect(session.pending('service-transition-test'), false);
        expect(
          api.reads.any(
            (path) => path.contains('capabilities?project_id=$project'),
          ),
          true,
        );
      },
    );
  }
  test('accepted native dispatch replays its original receipt after planning is disabled', () async {
    final api = ServiceApi()..lose = true, session = BusinessSession(api: api);
    addTearDown(session.dispose);
    addTearDown(api.dispose);
    await session.load();
    final body = {...serviceBound(record()), 'confirmation': true};
    await expectLater(
      session.command(
        'service-dispatch-test',
        '/service/cases/$caseId/dispatch',
        body,
        validateResult: (value) =>
            serviceReceipt('/service/cases/$caseId/dispatch', body, value),
      ),
      throwsA(isA<ApiException>()),
    );
    api.enabled = false;
    await session.repeatServiceCommand('service-dispatch-test');
    expect(api.commands.length, 2);
    expect(api.commands[0], api.commands[1]);
    expect(api.revision, 2);
    expect(session.pending('service-dispatch-test'), false);
  });
  Future<BusinessSession> show(WidgetTester tester, ServiceApi api) async {
    tester.view.physicalSize = const Size(1300, 2000);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    final session = BusinessSession(api: api);
    await session.load();
    await tester.pumpWidget(
      MaterialApp(home: BusinessServicePage(session: session)),
    );
    await tester.pumpAndSettle();
    return session;
  }

  Future<void> transition(
    WidgetTester tester,
    String next,
    String reason, {
    String resolution = '',
  }) async {
    await tester.ensureVisible(find.text('Status und Lösung'));
    await tester.tap(find.text('Status und Lösung'));
    await tester.pumpAndSettle();
    await tester.tap(find.byType(DropdownButtonFormField<String>).last);
    await tester.pumpAndSettle();
    await tester.tap(find.text(serviceStages[next]!).last);
    await tester.pumpAndSettle();
    await tester.enterText(
      find.widgetWithText(TextFormField, 'Begründung / Wiedereröffnungsgrund'),
      reason,
    );
    await tester.enterText(
      find.widgetWithText(TextFormField, 'Dokumentierte Lösung'),
      resolution,
    );
    await tester.tap(
      find.widgetWithText(FilledButton, 'Statusentscheidung festhalten'),
    );
    await tester.pumpAndSettle();
  }

  testWidgets(
    'native case resolves, closes and reopens without discarding historical resolution',
    (tester) async {
      final api = ServiceApi(), session = await show(tester, api);
      try {
        await tester.tap(find.text('Synthetische Reklamation'));
        await tester.pumpAndSettle();
        await transition(tester, 'triaged', 'Ursache geprüft');
        await transition(
          tester,
          'resolved',
          'Reparatur geprüft',
          resolution: 'Dichtung ersetzt.',
        );
        await transition(
          tester,
          'closed',
          'Kunde informiert',
          resolution: 'Dichtung ersetzt.',
        );
        expect(api.status, 'closed');
        await transition(
          tester,
          'triaged',
          'Erneuter Wasseraustritt gemeldet',
          resolution: 'Dichtung ersetzt.',
        );
        expect(api.status, 'triaged');
        expect(
          api.versions.any(
            (value) =>
                value['status'] == 'closed' &&
                value['resolution'] == 'Dichtung ersetzt.',
          ),
          true,
        );
        expect(api.commands.last['reason'], 'Erneuter Wasseraustritt gemeldet');
        expect(
          api.commands.map((value) => value['request_id']).toSet().length,
          4,
        );
      } finally {
        await tester.pumpWidget(const SizedBox());
        session.dispose();
        api.dispose();
      }
    },
    variant: TargetPlatformVariant.only(TargetPlatform.windows),
  );
  testWidgets('project source right loss clears case and stops transitions', (
    tester,
  ) async {
    final api = ServiceApi(), session = await show(tester, api);
    try {
      await tester.tap(find.text('Synthetische Reklamation'));
      await tester.pumpAndSettle();
      api.allowed = false;
      await session.sharedProjectSession(project).load();
      await tester.pumpAndSettle();
      expect(find.text('Synthetische Reklamation'), findsNothing);
      expect(find.text('Status und Lösung'), findsNothing);
      expect(api.commands, isEmpty);
    } finally {
      await tester.pumpWidget(const SizedBox());
      session.dispose();
      api.dispose();
    }
  }, variant: TargetPlatformVariant.only(TargetPlatform.windows));
}

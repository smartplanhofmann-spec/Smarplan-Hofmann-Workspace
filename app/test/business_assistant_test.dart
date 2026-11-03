import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:smartplan_office/api.dart';
import 'package:smartplan_office/business_assistant.dart';
import 'package:smartplan_office/business_session.dart';

const project = 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',
    second = 'bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb',
    article = 'cccccccccccccccccccccccccccccccc',
    contextId = 'dddddddddddddddddddddddddddddddd';
Map<String, dynamic> evidence() => {
  'id': contextId,
  'project_id': project,
  'current': true,
  'sha256': 'a' * 64,
  'sources': [
    {
      'source_id': 'project:$project',
      'descriptor': {'kind': 'project', 'id': project},
      'data': {'name': 'Synthetic project'},
    },
    {
      'source_id': 'article:$article',
      'descriptor': {'kind': 'article', 'id': article},
      'data': {
        'name': 'Synthetic article',
        'active': true,
        'revision': 4,
        'unit_price_net': '79.90',
        'tax_rate': '19',
      },
    },
  ],
};
Map<String, dynamic> answer() => {
  'context_id': contextId,
  'project_id': project,
  'status': 'completed',
  'result': {
    'response_type': 'source_answer',
    'business_values': 'resolved_from_selected_sources',
    'actions_executed_by_model': false,
    'citations': ['article:$article'],
    'facts': [
      {
        'source_id': 'article:$article',
        'path': 'unit_price_net',
        'value': '79.90',
      },
    ],
  },
};
Map<String, dynamic> clone(Map<String, dynamic> value) =>
    jsonDecode(jsonEncode(value)) as Map<String, dynamic>;

class AssistantApi extends OfficeApi {
  AssistantApi() : super(apiVersion: 'v1') {
    token = 'synthetic-assistant-session';
  }
  bool allowed = true, sourceRead = true, lose = true, readonly = false;
  int generation = 1, created = 0;
  final savedRules = <Map<String, dynamic>>[];
  final commands = <Map<String, dynamic>>[], paths = <String>[];
  @override
  Future<dynamic> call(String path, [Map<String, dynamic>? body]) async {
    paths.add(path);
    if (path.startsWith('/api/business/capabilities'))
      return {
        'compatibility_mode': 'business',
        'generation': generation,
        'readonly': readonly,
        'capabilities': ['business_assistant'],
        'features': ['assistant_workflow'],
        'permissions': [
          if (allowed) 'assistant.use',
          if (sourceRead) 'documents.read',
          'settings.manage',
          'projects.manage',
          'assistant.approve',
        ],
      };
    if (path == '/api/me') return {'id': second};
    if (path == '/api/users')
      return [
        {'id': second, 'email': 'synthetic-owner@example.test'},
      ];
    if (path == '/api/business/assistant/rules') {
      savedRules.add(clone(body!));
      return {...body, 'revision': body['revision'] + 1};
    }
    if (path.startsWith('/api/business/assistant/rules?')) return {'items': []};
    if (path.startsWith('/api/business/assistant/status'))
      return {
        'provider': {
          'configured': false,
          'message': 'Kein Modellanbieter konfiguriert.',
        },
        'actions': [],
      };
    if (path.startsWith('/api/business/assistant/sources?'))
      return {
        'items': sourceRead
            ? [
                {
                  'kind': 'project',
                  'id': path.contains(second) ? second : project,
                  'title': 'Synthetic project',
                },
              ]
            : [],
      };
    if (RegExp(r'^/api/business/assistant/(rules|plans|chat)\?').hasMatch(path))
      return {'items': []};
    if (path == '/api/business/assistant/contexts') {
      commands.add(clone(body!));
      if (!allowed || !sourceRead)
        throw const ApiException(403, 'Quellrecht entzogen');
      created = 1;
      if (lose) {
        lose = false;
        throw const ApiException(0, 'Erfolgsantwort verloren');
      }
      final result = evidence();
      result['sources'] = (result['sources'] as List)
          .where(
            (source) => (body['sources'] as List).any(
              (selected) =>
                  selected['kind'] == source['descriptor']['kind'] &&
                  selected['id'] == source['descriptor']['id'],
            ),
          )
          .toList();
      return result;
    }
    if (path == '/api/business/assistant/contexts/$contextId') {
      if (!sourceRead) throw const ApiException(403, 'Quellrecht entzogen');
      return evidence();
    }
    throw StateError('Unexpected $path');
  }
}

void main() {
  test('offer input never supplies model prices or taxes', () {
    expect(
      assistantOfferPositions(evidence(), {
        article: '1,2500',
        'unit_price_net': '0.01',
        'tax_rate': '0',
      }),
      [
        {'article_id': article, 'article_revision': 4, 'quantity': '1.2500'},
      ],
    );
    for (final input in ['0', '-1', '1e2', '1.00001', '1000000']) {
      expect(
        () => assistantOfferPositions(evidence(), {article: input}),
        throwsFormatException,
      );
    }
    expect(
      () => assistantOfferPositions(
        {...evidence(), 'project_id': second},
        {article: '1'},
      ),
      throwsFormatException,
    );
  });
  test('typed rule comparisons use exact decimal cents', () {
    expect(
      assistantConditions([
        {'field': 'open_minor', 'operator': 'gte', 'value': '49,87'},
        {'field': 'overdue_task', 'operator': 'eq', 'value': 'Nein'},
      ]),
      [
        {'field': 'open_minor', 'operator': 'gte', 'value': 4987},
        {'field': 'overdue_task', 'operator': 'eq', 'value': false},
      ],
    );
    for (final row in [
      {'field': 'open_minor', 'operator': 'gte', 'value': '1.001'},
      {'field': 'overdue_task', 'operator': 'gte', 'value': 'Ja'},
      {'field': 'net_wage', 'operator': 'eq', 'value': '100'},
    ]) {
      expect(() => assistantConditions([row]), throwsFormatException);
    }
  });
  test('facts must match exact cited values and current project', () {
    expect(
      assistantAnswerValues(evidence(), answer())['facts'][0]['value'],
      '79.90',
    );
    final invented = answer();
    invented['result']['facts'][0]['value'] = '0.01';
    expect(
      () => assistantAnswerValues(evidence(), invented),
      throwsFormatException,
    );
    expect(
      () => assistantAnswerValues(evidence(), {
        ...answer(),
        'project_id': second,
      }),
      throwsFormatException,
    );
    final wrong = answer();
    wrong['result']['citations'] = ['foreign:source'];
    expect(
      () => assistantAnswerValues(evidence(), wrong),
      throwsFormatException,
    );
  });
  Future<BusinessSession> show(
    WidgetTester tester,
    AssistantApi api, {
    bool global = false,
  }) async {
    tester.view.physicalSize = const Size(1500, 1800);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    final session = BusinessSession(
      api: api,
      projectId: global ? null : project,
      projects: [
        {'id': project, 'name': 'Synthetic project'},
        {'id': second, 'name': 'Other project'},
      ],
    );
    await session.load();
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(body: BusinessAssistantPage(session: session)),
      ),
    );
    await tester.pumpAndSettle();
    return session;
  }

  Future<void> selectSources(WidgetTester tester) async {
    await tester.tap(find.text('Quellen auswählen'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Projekt · Synthetic project'));
    await tester.tap(find.text('Datenbasis verbindlich auswählen').last);
    await tester.pumpAndSettle();
  }

  testWidgets(
    'unconfigured provider is explicit and no chat request is invented',
    (tester) async {
      final api = AssistantApi(), session = await show(tester, api);
      try {
        expect(find.text('Kein Modellanbieter konfiguriert.'), findsOneWidget);
        expect(find.text('Frage stellen'), findsNothing);
        expect(
          api.paths.any((path) => path == '/api/business/assistant/chat'),
          isFalse,
        );
        expect(find.textContaining('Mikrofonaufnahme'), findsOneWidget);
      } finally {
        await tester.pumpWidget(const SizedBox());
        session.dispose();
        api.dispose();
      }
    },
    variant: TargetPlatformVariant.only(TargetPlatform.windows),
  );
  testWidgets(
    'lost context ACK locks original input, survives rights and generation changes and creates once',
    (tester) async {
      final api = AssistantApi(), session = await show(tester, api);
      try {
        await selectSources(tester);
        expect(find.text('Erfolgsantwort verloren'), findsOneWidget);
        expect(api.created, 1);
        final check = tester.widget<CheckboxListTile>(
          find.byType(CheckboxListTile),
        );
        expect(check.onChanged, isNull);
        await tester.tap(find.text('Schließen'));
        await tester.pumpAndSettle();
        api.sourceRead = false;
        api.generation = 2;
        await session.load();
        await tester.pumpAndSettle();
        await tester.tap(find.text('Unverändert wiederholen'));
        await tester.pumpAndSettle();
        expect(find.text('Quellrecht entzogen'), findsOneWidget);
        expect(session.pending('assistant-context-$project'), isTrue);
        api.sourceRead = true;
        api.generation = 3;
        await session.load();
        await tester.pumpAndSettle();
        await tester.tap(find.text('Unverändert wiederholen'));
        await tester.pumpAndSettle();
        expect(api.created, 1);
        expect(api.commands, hasLength(3));
        expect(api.commands[0], api.commands[2]);
        expect(session.pending('assistant-context-$project'), isFalse);
        expect(find.text('Synthetic article'), findsOneWidget);
        api.sourceRead = false;
        await session.load();
        await tester.pumpAndSettle();
        expect(find.text('Synthetic article'), findsNothing);
      } finally {
        await tester.pumpWidget(const SizedBox());
        session.dispose();
        api.dispose();
      }
    },
    variant: TargetPlatformVariant.only(TargetPlatform.windows),
  );
  testWidgets(
    'native versioned rule editor submits typed evidence and explicit approval',
    (tester) async {
      final api = AssistantApi(), session = await show(tester, api);
      try {
        await tester.ensureVisible(find.text('Regel anlegen'));
        await tester.tap(find.text('Regel anlegen'));
        await tester.pumpAndSettle();
        await tester.enterText(
          find.widgetWithText(
            TextFormField,
            'Zahl der belegten Bedingungen (0 bis 8)',
          ),
          '1',
        );
        await tester.tap(find.text('Regel bearbeiten'));
        await tester.pumpAndSettle();
        await tester.enterText(
          find.widgetWithText(TextFormField, 'Regelbezeichnung'),
          'Synthetische belegte Regel',
        );
        await tester.enterText(
          find.widgetWithText(
            TextFormField,
            'Vergleichswert 1 (Tage / EUR / Ja oder Nein)',
          ),
          'Nein',
        );
        final consent = find.text(
          'Ich bestätige diese Regel und ihre Zuständigkeit. Automatisch erlaubte Aktionen können unmittelbar ausgeführt werden.',
        );
        await tester.ensureVisible(consent);
        await tester.tap(consent);
        await tester.tap(
          find.text('Neue Regelfassung verbindlich speichern').last,
        );
        await tester.pumpAndSettle();
        expect(api.savedRules, hasLength(1));
        expect(api.savedRules.single['mode'], 'approval');
        expect(api.savedRules.single['revision'], 0);
        expect(api.savedRules.single['confirmation'], isTrue);
        expect(api.savedRules.single['conditions'], [
          {'field': 'overdue_payment', 'operator': 'eq', 'value': false},
        ]);
        expect(api.savedRules.single['project_id'], project);
      } finally {
        await tester.pumpWidget(const SizedBox());
        session.dispose();
        api.dispose();
      }
    },
    variant: TargetPlatformVariant.only(TargetPlatform.windows),
  );
  testWidgets(
    'source search remains readable in readonly mode without creating a command',
    (tester) async {
      final api = AssistantApi()..readonly = true,
          session = await show(tester, api);
      try {
        expect(
          tester
              .widget<FilledButton>(
                find.widgetWithText(FilledButton, 'Quellen auswählen'),
              )
              .onPressed,
          isNull,
        );
        await tester.tap(find.text('Quellen suchen'));
        await tester.pumpAndSettle();
        await tester.enterText(
          find.widgetWithText(TextFormField, 'Quellenbezeichnung oder Kennung'),
          'Synthetic article',
        );
        await tester.tap(find.text('Quellen suchen').last);
        await tester.pumpAndSettle();
        expect(
          api.paths.any(
            (path) =>
                path.contains('q=Synthetic+article') &&
                path.contains('offset=0'),
          ),
          isTrue,
        );
        expect(api.commands, isEmpty);
        expect(tester.takeException(), isNull);
      } finally {
        await tester.pumpWidget(const SizedBox());
        session.dispose();
        api.dispose();
      }
    },
    variant: TargetPlatformVariant.only(TargetPlatform.windows),
  );
  test('project-owned pending operation cannot replay in a second project and survives navigation', () async {
    final api = AssistantApi(),
        parent = BusinessSession(
          api: api,
          projects: [
            {'id': project},
            {'id': second},
          ],
        );
    try {
      await parent.load();
      final scope = parent.sharedProjectSession(project);
      await scope.load();
      await expectLater(
        scope.command('pending', '/assistant/contexts', {
          'project_id': project,
          'sources': [
            {'kind': 'project', 'id': project},
          ],
        }),
        throwsA(isA<ApiException>()),
      );
      expect(parent.sharedProjectSession(project), same(scope));
      await expectLater(
        scope.repeatAssistantCommand('pending', second),
        throwsA(isA<ApiException>()),
      );
      expect(api.commands, hasLength(1));
      expect(scope.pending('pending'), isTrue);
      api.generation = 2;
      await scope.repeatAssistantCommand('pending', project);
      expect(api.commands, hasLength(2));
      expect(api.commands[0], api.commands[1]);
    } finally {
      parent.dispose();
      api.dispose();
    }
  });
}

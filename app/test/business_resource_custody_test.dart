import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:smartplan_office/api.dart';
import 'package:smartplan_office/business_session.dart';
import 'package:smartplan_office/business_resource_custody.dart';

const resource = 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',
    employee = 'bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb',
    project = 'cccccccccccccccccccccccccccccccc',
    recordId = 'dddddddddddddddddddddddddddddddd';
final hash = 'e' * 64;
Map<String, dynamic> detail({
  String condition = 'restricted',
  int revision = 1,
}) => {
  'id': resource,
  'resource': {
    'id': resource,
    'name': 'Synthetisches Werkzeug',
    'kind': 'tool',
    'code': 'W-001',
    'active': true,
    'revision': 1,
  },
  'source_sha256': hash,
  'profile': {
    'id': resource,
    'resource_id': resource,
    'revision': revision,
    'serial_number': 'TEST',
    'manufacturer': 'Synthetisch',
    'model': 'Prüfgerät',
    'location': 'Werkstatt',
    'condition': 'serviceable',
    'notes': '',
  },
  'state': {
    'condition': condition,
    'configured': true,
    'inspection_knowledge': 'unconfigured',
    'open_handoff': null,
    'blockers': condition == 'restricted'
        ? [
            {'code': 'condition', 'message': 'Zustand sperrt die Nutzung.'},
          ]
        : [],
    'available': condition == 'serviceable',
  },
  'requirements': [],
  'inspections': [],
  'handoffs': [],
  'files': [],
};

class CustodyApi extends OfficeApi {
  CustodyApi() : super(apiVersion: 'v1') {
    token = 'synthetic-custody-token';
  }
  bool allowed = true, projectAllowed = true, enabled = true, lose = false;
  int revision = 1, generation = 1;
  String condition = 'restricted';
  final posts = <Map<String, dynamic>>[],
      reads = <String>[],
      effects = <String>{};
  @override
  Future<dynamic> call(String path, [Map<String, dynamic>? body]) async {
    reads.add(path);
    if (path.startsWith('/api/business/capabilities'))
      return {
        'compatibility_mode': 'business',
        'generation': generation,
        'readonly': false,
        'features': ['resource_custody', 'organization_modules'],
        'capabilities': ['business_resource_custody'],
        'permissions': (path.contains('project_id=') ? projectAllowed : allowed)
            ? ['planning.read', 'planning.write']
            : [],
        'organization': {
          'revision': 1,
          'configured': true,
          'modules': {
            for (final section in BusinessSession.organizationSections)
              section: {'enabled': enabled, 'visible': true},
          },
        },
      };
    if (path == '/api/business/resource-custody/options')
      return {
        'resources': [detail()['resource']],
        'employees': [
          {'id': employee, 'name': 'Synthetischer Empfänger', 'active': true},
        ],
        'projects': [
          {'id': project, 'name': 'Synthetisches Projekt'},
        ],
      };
    if (path == '/api/business/resource-custody/$resource')
      return detail(condition: condition, revision: revision);
    if (path == '/api/business/resource-custody')
      return {
        'items': [detail(condition: condition, revision: revision)],
      };
    if (path == '/api/business/resource-custody/$resource/profile' ||
        path == '/api/business/resource-custody/$resource/handoffs') {
      posts.add(jsonDecode(jsonEncode(body)) as Map<String, dynamic>);
      if (effects.add(body!['request_id'])) {
        revision++;
        condition = body['condition'];
      }
      if (lose) {
        lose = false;
        throw const ApiException(0, 'Angenommene Antwort verloren');
      }
      return {
        'resource': detail(condition: condition, revision: revision),
        'record': {
          'id': path.endsWith('/profile') ? resource : recordId,
          'resource_id': resource,
          ...body,
          'revision': revision,
        },
      };
    }
    throw StateError(path);
  }
}

void main() {
  test(
    'canonical identity and explicit physical receiver or project are required',
    () {
      expect(custodyBound(detail()), {'source_sha256': hash});
      expect(
        () => custodyBound({
          ...detail(),
          'resource': {'id': project},
        }),
        throwsFormatException,
      );
      expect(
        () => custodyHandoffValues(detail(), {
          'employee_id': '',
          'project_id': '',
        }),
        throwsFormatException,
      );
      expect(
        custodyHandoffValues(detail(), {
          'employee_id': employee,
          'project_id': '',
        })['project_id'],
        isNull,
      );
      expect(
        () => custodyHandoffValues(
          {
            ...detail(),
            'state': {
              'open_handoff': {'id': recordId},
            },
          },
          {'employee_id': employee},
        ),
        throwsFormatException,
      );
    },
  );
  test('return receipt binds exact issue and profile revision', () {
    final body = {'handoff_id': recordId, 'condition': 'restricted'},
        answer = {
          'resource': detail(),
          'record': {'id': employee, 'resource_id': resource, ...body},
        };
    expect(
      custodyReceipt('/resource-custody/$resource/returns', body, answer),
      answer,
    );
    expect(
      () => custodyReceipt('/resource-custody/$resource/returns', body, {
        ...answer,
        'record': {...answer['record'] as Map, 'handoff_id': project},
      }),
      throwsA(isA<ApiException>()),
    );
    expect(
      () => custodyReceipt(
        '/resource-custody/$resource/profile',
        {'revision': 1, 'condition': 'restricted'},
        {
          'resource': detail(),
          'record': {
            'resource_id': resource,
            'revision': 1,
            'condition': 'restricted',
          },
        },
      ),
      throwsA(isA<ApiException>()),
    );
  });
  test('accepted handoff replay refreshes global rights and keeps exact command after module deactivation', () async {
    final api = CustodyApi()..lose = true, session = BusinessSession(api: api);
    await session.load();
    const key = 'resource-custody-handoffs-test',
        path = '/resource-custody/$resource/handoffs';
    await expectLater(
      session.command(key, path, {
        'source_sha256': hash,
        'employee_id': employee,
        'project_id': project,
        'condition': 'serviceable',
      }),
      throwsA(isA<ApiException>()),
    );
    api.allowed = false;
    await expectLater(
      session.repeatResourceCustodyCommand(key),
      throwsA(isA<ApiException>()),
    );
    expect(session.pending(key), true);
    expect(api.posts.length, 1);
    api.allowed = true;
    api.enabled = false;
    await session.repeatResourceCustodyCommand(key);
    expect(api.posts[0], api.posts[1]);
    expect(api.effects.length, 1);
    expect(session.pending(key), false);
    expect(
      api.reads
          .where((value) => value.startsWith('/api/business/capabilities'))
          .every((value) => !value.contains('project_id=')),
      true,
    );
    session.dispose();
    api.dispose();
  });
  testWidgets(
    'profile editor uses latest return state rather than earlier profile state and saves a new version',
    (tester) async {
      await tester.binding.setSurfaceSize(const Size(1100, 1000));
      addTearDown(() => tester.binding.setSurfaceSize(null));
      final api = CustodyApi(), session = BusinessSession(api: api);
      await session.load();
      await tester.pumpWidget(
        MaterialApp(
          home: BusinessResourceCustodyPage(
            session: session,
            resourceId: resource,
          ),
        ),
      );
      await tester.pumpAndSettle();
      expect(find.text('Zustand: Eingeschränkt / gesperrt'), findsOneWidget);
      await tester.tap(
        find.widgetWithText(OutlinedButton, 'Profil und Zustand'),
      );
      await tester.pumpAndSettle();
      expect(find.text('Eingeschränkt / gesperrt'), findsWidgets);
      await tester.enterText(
        find.widgetWithText(TextFormField, 'Grund der neuen Profilfassung'),
        'Zustand aus Rücknahme ausdrücklich bestätigt.',
      );
      await tester.tap(find.byType(SwitchListTile));
      await tester.ensureVisible(
        find.widgetWithText(FilledButton, 'Profil und Zustand speichern'),
      );
      await tester.tap(
        find.widgetWithText(FilledButton, 'Profil und Zustand speichern'),
      );
      await tester.pumpAndSettle();
      expect(api.posts.single['condition'], 'restricted');
      expect(api.posts.single['revision'], 1);
      expect(api.revision, 2);
      await tester.pumpWidget(const SizedBox());
      session.dispose();
      api.dispose();
    },
  );
  testWidgets(
    'scoped project entry loads independent global rights and returns to the same parent-owned session',
    (tester) async {
      final api = CustodyApi(), parent = BusinessSession(api: api);
      await parent.load();
      final scoped = parent.sharedProjectSession(project);
      await scoped.load();
      expect(identical(scoped.sharedGlobalSession(), parent), true);
      api.allowed = false;
      String? failure;
      await tester.pumpWidget(
        MaterialApp(
          home: StatefulBuilder(
            builder: (context, setState) => Scaffold(
              body: Column(
                children: [
                  TextButton(
                    onPressed: () async {
                      try {
                        await openResourceCustody(context, scoped);
                      } catch (value) {
                        setState(() => failure = '$value');
                      }
                    },
                    child: const Text('Projektbetriebsmittel öffnen'),
                  ),
                  if (failure != null) Text(failure!),
                ],
              ),
            ),
          ),
        ),
      );
      await tester.tap(find.text('Projektbetriebsmittel öffnen'));
      await tester.pumpAndSettle();
      expect(
        find.textContaining('Globale Betriebsmittelfreigabe fehlt.'),
        findsOneWidget,
      );
      expect(find.text('Synthetisches Werkzeug'), findsNothing);
      expect(scoped.can('planning.write'), true);
      api.allowed = true;
      await tester.tap(find.text('Projektbetriebsmittel öffnen'));
      await tester.pumpAndSettle();
      expect(find.text('Synthetisches Werkzeug'), findsOneWidget);
      expect(
        api.reads
            .where((value) => value == '/api/business/capabilities')
            .length,
        greaterThanOrEqualTo(3),
      );
      api.allowed = false;
      await parent.load();
      await tester.pumpAndSettle();
      expect(find.text('Synthetisches Werkzeug'), findsNothing);
      await tester.pumpWidget(const SizedBox());
      parent.dispose();
      api.dispose();
    },
  );

  testWidgets(
    'global rights withdrawal clears loaded resource and original evidence view',
    (tester) async {
      final api = CustodyApi(), session = BusinessSession(api: api);
      await session.load();
      await tester.pumpWidget(
        MaterialApp(
          home: BusinessResourceCustodyPage(
            session: session,
            resourceId: resource,
          ),
        ),
      );
      await tester.pumpAndSettle();
      expect(find.text('Synthetisches Werkzeug'), findsOneWidget);
      api.allowed = false;
      await session.load();
      await tester.pumpAndSettle();
      expect(find.text('Synthetisches Werkzeug'), findsNothing);
      expect(
        find.textContaining('Globale Lese- und Schreibrechte'),
        findsOneWidget,
      );
      await tester.pumpWidget(const SizedBox());
      session.dispose();
      api.dispose();
    },
  );
}

import 'dart:convert';
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:smartplan_office/api.dart';
import 'package:smartplan_office/business_project_milestone_contract.dart';

final fixture = jsonDecode(
  File('test/fixtures/project_milestones.json').readAsStringSync(),
) as Map<String, dynamic>;
final project = fixture['project_id'] as String;
final milestone = fixture['created']['id'] as String;
final actor = fixture['actor']['id'] as String;

Map<String, dynamic> copy(dynamic value) =>
    Map<String, dynamic>.from(jsonDecode(jsonEncode(value)) as Map);

Map<String, dynamic> input(dynamic command) =>
    copy(command)..remove('request_id');

Map<String, dynamic> rehash(Map<String, dynamic> record) {
  final changed = copy(record)..remove('content_hash');
  return {...changed, 'content_hash': milestoneHash(changed)};
}

void main() {
  test(
    'actual accepted originals retain exact Unicode, hashes and full history',
    () {
      for (final name in [
        'created',
        'updated',
        'cancelled',
        'reopened',
        'empty_created',
      ]) {
        final original = copy(fixture[name]);
        expect(milestoneRecord(original, project), original);
        expect(
          milestoneHash({...original}..remove('content_hash')),
          original['content_hash'],
        );
      }
      final history = milestoneHistory(
        fixture['history'],
        project,
        milestone,
        anchor: copy(fixture['updated']),
      );
      expect(history, fixture['history']['items']);
      expect(history.map((row) => row['revision']).toList(), [1, 2, 3, 4]);
      expect(history.map((row) => row['status']).toList(), [
        'planned',
        'achieved',
        'cancelled',
        'planned',
      ]);
      expect(
        milestoneList(fixture['listing'], project),
        fixture['listing']['items'],
      );
    },
  );

  test(
    'actual whitespace is preserved without rewriting accepted originals',
    () {
      final initial = milestoneRecord(fixture['created'], project);
      expect(initial['title'], ' Freigabe Süd 🚧 – Phase 1 ');
      expect(initial['details'], 'Original prüfen.\nÜbernahme unverändert.\n');
      expect(
        milestoneBody({
          for (final field in milestoneFields) field: initial[field],
        }),
        input(fixture['create_command']),
      );
    },
  );

  test('revision order remains authoritative after a clock adjustment', () {
    // The backend permits a system-clock correction between revisions. This
    // explicit boundary variant must not add a monotonic-time requirement.
    final initial = milestoneRecord(fixture['created'], project);
    final changed = rehash({
      ...copy(fixture['updated']),
      'updated_at': '2026-11-09T11:55:00+00:00',
    });
    expect(milestoneRecord(changed, project), changed);
    expect(
      milestoneHistory(
        {
          'schema_version': 1,
          'project_id': project,
          'milestone_id': milestone,
          'items': [initial, changed],
        },
        project,
        milestone,
        anchor: initial,
      ),
      [initial, changed],
    );
    milestoneReceiptValidator(
      project,
      input(fixture['update_command']),
      previous: initial,
      expectedActor: actor,
    )(changed);
  });

  test(
    'every original receipt binds input, actor and immutable creation fields',
    () {
      milestoneReceiptValidator(
        project,
        input(fixture['create_command']),
        expectedActor: actor,
      )(fixture['created']);
      for (final step in [
        ('created', 'update_command', 'updated'),
        ('updated', 'cancel_command', 'cancelled'),
        ('cancelled', 'reopen_command', 'reopened'),
      ]) {
        milestoneReceiptValidator(
          project,
          input(fixture[step.$2]),
          previous: copy(fixture[step.$1]),
          expectedActor: actor,
        )(fixture[step.$3]);
      }
      // A replay returns its original revision even though the latest is now 4.
      milestoneReceiptValidator(
        project,
        input(fixture['update_command']),
        previous: copy(fixture['created']),
        expectedActor: actor,
      )(fixture['updated']);
      expect(
        () => milestoneReceiptValidator(
          project,
          input(fixture['update_command']),
          previous: copy(fixture['created']),
          expectedActor: actor,
        )(fixture['reopened']),
        throwsA(isA<ApiException>()),
      );
    },
  );

  test('validly rehashed foreign actor, content or creation cannot replace a receipt', () {
    final validate = milestoneReceiptValidator(
      project,
      input(fixture['update_command']),
      previous: copy(fixture['created']),
      expectedActor: actor,
    );
    for (final patch in [
      {'updated_by': 'f' * 32},
      {'created_by': 'f' * 32},
      {'created_at': '2026-11-08T12:00:00+00:00'},
      {'title': 'Anderer Auftrag'},
      {'status': 'planned'},
      {'assignee_id': null},
      {'due_date': null},
    ]) {
      expect(
        () => validate(rehash({...copy(fixture['updated']), ...patch})),
        throwsA(isA<ApiException>()),
      );
    }
    final create = milestoneReceiptValidator(
      project,
      input(fixture['create_command']),
      expectedActor: actor,
    );
    expect(
      () =>
          create(rehash({...copy(fixture['created']), 'created_by': 'f' * 32})),
      throwsA(isA<ApiException>()),
    );
  });

  test('record shapes, dates, controls, identifiers and timestamp zones are strict', () {
    for (final patch in [
      {'schema_version': 2},
      {'schema_version': true},
      {'status': 'done'},
      {'due_date': '2026-02-30'},
      {'due_date': '1899-12-31'},
      {'due_date': '2201-01-01'},
      {'assignee_id': ''},
      {'title': ' '},
      {'title': 'hidden\u0000title'},
      {'details': 'hidden\u007fdetails'},
      {'created_by': 'invalid'},
      {'updated_at': '2026-11-09T12:00:00'},
      {'updated_at': '2026-02-30T12:00:00+00:00'},
      {'updated_at': '2026-11-09T24:00:00+00:00'},
      {'updated_at': '2026-11-09T12:00:00+24:00'},
      {'unexpected': true},
    ]) {
      final changed = rehash({...copy(fixture['created']), ...patch});
      expect(
        () => milestoneRecord(changed, project),
        throwsA(isA<ApiException>()),
        reason: '$patch',
      );
    }
    for (final revision in [0, 2147483648, 1.5]) {
      final changed = {...copy(fixture['created']), 'revision': revision};
      expect(
        () => milestoneRecord(changed, project),
        throwsA(isA<ApiException>()),
      );
    }
    final changed = {
      ...copy(fixture['created']),
      'title': 'Ungeprüfte Änderung',
    };
    expect(
      () => milestoneRecord(changed, project),
      throwsA(isA<ApiException>()),
    );
  });

  test('full form body preserves strings and counts Unicode code points', () {
    final fields = {
      for (final key in milestoneFields) key: fixture['created'][key],
    };
    expect(
      milestoneBody({...fields, 'title': '🏗' * 200})['title'],
      '🏗' * 200,
    );
    expect(
      milestoneBody({
        ...fields,
        'title': '  Titel  ',
        'details': '\r\n\t Beschreibung  ',
      })['title'],
      '  Titel  ',
    );
    for (final invalid in [
      {...fields, 'title': '🏗' * 201},
      {...fields, 'details': 'x' * 10001},
      {...fields, 'due_date': ''},
      {...fields, 'assignee_id': ''},
      {...fields, 'request_id': 'f' * 32},
      {...fields}..remove('status'),
    ]) {
      expect(() => milestoneBody(invalid), throwsA(isA<FormatException>()));
    }
    expect(
      () => milestoneBody(fields, revision: 0),
      throwsA(isA<FormatException>()),
    );
    expect(
      () => milestoneBody(fields, revision: 2147483648),
      throwsA(isA<FormatException>()),
    );
    expect(milestoneBody(fields, revision: 1)['revision'], 1);
  });

  test(
    'unpaired Unicode surrogates are rejected before input or original hashing',
    () {
      final fields = {
        for (final key in milestoneFields) key: fixture['created'][key],
      };
      for (final field in ['title', 'details']) {
        for (final broken in ['before\uD800after', 'before\uDC00after']) {
          expect(
            () => milestoneBody({...fields, field: broken}),
            throwsA(isA<FormatException>()),
          );
          expect(
            () => milestoneRecord({
              ...copy(fixture['created']),
              field: broken,
            }, project),
            throwsA(isA<ApiException>()),
          );
        }
      }
      expect(
        milestoneBody({...fields, 'title': 'Gültiges Paar 🚧'})['title'],
        'Gültiges Paar 🚧',
      );
    },
  );

  test('history rejects gaps, duplicates, swapped rows and a foreign original anchor', () {
    final rows = [for (final row in fixture['history']['items']) copy(row)];
    for (final invalid in [
      [rows[0], rows[2]],
      [rows[0], rows[0]],
      [rows[1], rows[0]],
      <Map<String, dynamic>>[],
      [
        rows[0],
        rehash({...rows[1], 'created_by': 'f' * 32}),
        ...rows.skip(2),
      ],
    ]) {
      expect(
        () => milestoneHistory(
          {...copy(fixture['history']), 'items': invalid},
          project,
          milestone,
        ),
        throwsA(isA<ApiException>()),
      );
    }
    expect(
      () => milestoneHistory(
        fixture['history'],
        project,
        milestone,
        anchor: rehash({
          ...copy(fixture['updated']),
          'details': 'Andere Originalfassung',
        }),
      ),
      throwsA(isA<ApiException>()),
    );
  });

  test('lists and history require one canonical project and milestone', () {
    final listing = copy(fixture['listing']);
    expect(
      () => milestoneList(listing, fixture['other_project_id']),
      throwsA(isA<ApiException>()),
    );
    expect(
      () => milestoneList({
        ...listing,
        'project_id': fixture['other_project_id'],
      }, project),
      throwsA(isA<ApiException>()),
    );
    expect(
      () => milestoneList({
        ...listing,
        'items': [listing['items'][0], listing['items'][0]],
      }, project),
      throwsA(isA<ApiException>()),
    );
    expect(
      () => milestoneHistory(
        fixture['history'],
        project,
        fixture['empty_created']['id'],
      ),
      throwsA(isA<ApiException>()),
    );
    expect(
      () => milestoneList({
        'schema_version': 1,
        'project_id': 'invalid',
        'items': [],
      }, 'invalid'),
      throwsA(isA<ApiException>()),
    );
    expect(
      milestoneList({
        'schema_version': 1,
        'project_id': project,
        'items': [],
      }, project),
      isEmpty,
    );
  });

  test(
    'historical removed assignee stays intact without fetching other personnel',
    () {
      final oldTeam = milestoneTeam(fixture['workspace'], project);
      final currentTeam = milestoneTeam(
        fixture['workspace_after_assignee_removed'],
        project,
      );
      final assignee = fixture['created']['assignee_id'];
      expect(oldTeam.any((row) => row['id'] == assignee), isTrue);
      expect(currentTeam.any((row) => row['id'] == assignee), isFalse);
      expect(
        milestoneRecord(fixture['reopened'], project)['assignee_id'],
        assignee,
      );
      milestoneReceiptValidator(
        project,
        input(fixture['reopen_command']),
        previous: copy(fixture['cancelled']),
        expectedActor: actor,
      )(fixture['reopened']);
    },
  );

  test(
    'team source rejects cross-project, duplicate and expanded identities',
    () {
      final workspace = copy(fixture['workspace']);
      final team = workspace['team'] as List;
      for (final changed in [
        {
          ...workspace,
          'project': {
            ...copy(workspace['project']),
            'id': fixture['other_project_id'],
          },
        },
        {
          ...workspace,
          'team': [team[0], team[0]],
        },
        {
          ...workspace,
          'team': [
            {...copy(team[0]), 'salary': 'private'},
          ],
        },
        {
          ...workspace,
          'team': [
            {...copy(team[0]), 'id': 'invalid'},
          ],
        },
      ]) {
        expect(
          () => milestoneTeam(changed, project),
          throwsA(isA<ApiException>()),
        );
      }
    },
  );
}

import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:smartplan_office/api.dart';
import 'package:smartplan_office/business_project_milestones.dart';
import 'package:smartplan_office/business_session.dart';
import 'package:smartplan_office/business_widgets.dart';

Map<String, dynamic> copy(dynamic value) =>
    Map<String, dynamic>.from(jsonDecode(jsonEncode(value)) as Map);
final milestoneFixture = copy(
  jsonDecode(File('test/fixtures/project_milestones.json').readAsStringSync()),
);

class MilestoneUiApi extends OfficeApi {
  MilestoneUiApi({bool existing = true}) : super(apiVersion: 'v1') {
    token = 'synthetic-milestone-session';
    current = existing ? copy(f['created']) : null;
  }
  Map<String, dynamic> get f => milestoneFixture;
  String get project => f['project_id'];
  Map<String, dynamic>? current;
  bool read = true,
      write = true,
      feature = true,
      removed = false,
      loseNext = false;
  ApiException? rejectNext;
  Completer<dynamic>? heldList;
  Completer<void>? heldPost;
  Completer<dynamic>? heldMe;
  final posts = <Map<String, dynamic>>[];
  final calls = <String>[];
  final receipts = <String, Map<String, dynamic>>{};
  dynamic foreignHistory;

  @override
  Future<dynamic> call(String path, [Map<String, dynamic>? body]) async {
    calls.add(path);
    if (path.endsWith('/capabilities?project_id=$project') ||
        path.startsWith('/api/business/capabilities')) {
      return {
        'storage_version': 7,
        'compatibility_mode': 'business',
        'generation': 1,
        'capabilities': ['business_project_milestones'],
        'features': [if (feature) 'project_milestones'],
        'permissions': [
          if (read) 'planning.read',
          if (write) 'projects.manage',
        ],
      };
    }
    if (path == '/api/me') return heldMe?.future ?? copy(f['actor']);
    if (path == '/api/projects/$project/workspace')
      return copy(
        f[removed ? 'workspace_after_assignee_removed' : 'workspace'],
      );
    if (path == '/api/projects/${f['other_project_id']}/workspace')
      return {
        'project': {'id': f['other_project_id']},
        'team': [],
      };
    final root = '/api/business/projects/$project/milestones';
    if (path == '/api/business/projects/${f['other_project_id']}/milestones')
      return {
        'schema_version': 1,
        'project_id': f['other_project_id'],
        'items': [],
      };
    if (path == root && body == null) {
      if (heldList != null) return heldList!.future;
      return {
        'schema_version': 1,
        'project_id': project,
        'items': [if (current != null) copy(current)],
      };
    }
    if (path == '$root/${f['created']['id']}' && body == null)
      return copy(current!);
    if (path == '$root/${f['created']['id']}/history') {
      if (foreignHistory != null) return copy(foreignHistory);
      return {
        'schema_version': 1,
        'project_id': project,
        'milestone_id': f['created']['id'],
        'items': [
          for (final row in f['history']['items'])
            if (row['revision'] <= current!['revision']) copy(row),
        ],
      };
    }
    if (body != null &&
        (path == root || path == '$root/${f['created']['id']}')) {
      posts.add(copy(body));
      final denial = rejectNext;
      rejectNext = null;
      if (denial != null) throw denial;
      final request = body['request_id'] as String;
      if (!receipts.containsKey(request)) {
        final create = path == root;
        final command = copy(f[create ? 'create_command' : 'update_command'])
          ..remove('request_id');
        expect({...body}..remove('request_id'), command);
        current = copy(f[create ? 'created' : 'updated']);
        receipts[request] = copy(current);
      }
      if (loseNext) {
        loseNext = false;
        throw const ApiException(0, 'Synthetisch verlorene Bestätigung');
      }
      if (heldPost != null) await heldPost!.future;
      return copy(receipts[request]);
    }
    throw StateError('Unexpected milestone request $path');
  }
}

Future<BusinessSession> mountMilestones(
  WidgetTester t,
  MilestoneUiApi api, {
  String? project,
  bool settle = true,
}) async {
  final session = BusinessSession(api: api, projectId: project ?? api.project);
  await session.load();
  await t.pumpWidget(
    MaterialApp(
      home: Scaffold(body: BusinessProjectMilestonesPage(session: session)),
    ),
  );
  if (settle) {
    await t.pumpAndSettle();
  } else {
    await t.pump();
  }
  return session;
}

Future<void> click(WidgetTester t, String text) async {
  final target = find.text(text).last;
  await t.ensureVisible(target);
  await t.tap(target);
  await t.pumpAndSettle();
}

Future<void> chooseStatus(WidgetTester t, String label) async {
  final field = find.byType(DropdownButtonFormField<String>).last;
  await t.ensureVisible(field);
  await t.tap(field);
  await t.pumpAndSettle();
  await click(t, label);
}

Future<void> closeMilestones(
  WidgetTester t,
  BusinessSession session,
  MilestoneUiApi api,
) async {
  await t.pumpWidget(const SizedBox());
  session.dispose();
  api.dispose();
  expect(t.takeException(), isNull);
}

void main() {
  testWidgets(
    '390px edit preserves exact original whitespace and shows immutable history',
    (t) async {
      await t.binding.setSurfaceSize(const Size(390, 844));
      final api = MilestoneUiApi(), session = await mountMilestones(t, api);
      try {
        expect(find.text(api.f['created']['title']), findsOneWidget);
        await click(t, 'Bearbeiten');
        expect(
          t
              .widget<TextFormField>(find.byType(TextFormField).at(0))
              .controller!
              .text,
          api.f['created']['title'],
        );
        expect(
          t
              .widget<TextFormField>(find.byType(TextFormField).at(1))
              .controller!
              .text,
          api.f['created']['details'],
        );
        await chooseStatus(t, 'Erreicht');
        await click(t, 'Speichern');
        expect(api.posts, hasLength(1));
        expect(api.posts.single['title'], api.f['created']['title']);
        expect(api.posts.single['details'], api.f['created']['details']);
        expect(api.current, api.f['updated']);
        expect(find.byType(BusinessEditor), findsNothing);
        api.removed = true;
        await click(t, 'Änderungshistorie · Revision 2');
        expect(find.text('Meilenstein: Änderungshistorie'), findsOneWidget);
        expect(find.textContaining('Revision 2 · Erreicht'), findsOneWidget);
        expect(
          find.textContaining('Nicht mehr im aktuellen Projektteam'),
          findsWidgets,
        );
        expect(
          find.textContaining(api.f['updated']['assignee_id']),
          findsWidgets,
        );
        await t.scrollUntilVisible(
          find.textContaining('Revision 1 · Geplant'),
          180,
          scrollable: find
              .descendant(
                of: find.byType(AlertDialog),
                matching: find.byType(Scrollable),
              )
              .first,
        );
        expect(find.textContaining('Revision 1 · Geplant'), findsOneWidget);
        await click(t, 'Schließen');
        expect(api.posts, hasLength(1));
      } finally {
        await closeMilestones(t, session, api);
        await t.binding.setSurfaceSize(null);
      }
    },
  );

  testWidgets(
    'lost create ACK closes and reopens with exact frozen values and same request',
    (t) async {
      final api = MilestoneUiApi(existing: false)..loseNext = true;
      final session = await mountMilestones(t, api);
      try {
        await click(t, 'Meilenstein anlegen');
        await t.enterText(
          find.byType(TextFormField).at(0),
          api.f['create_command']['title'],
        );
        await t.enterText(
          find.byType(TextFormField).at(1),
          api.f['create_command']['details'],
        );
        await t.enterText(find.byType(TextFormField).at(2), '30.11.2026');
        final assignee = find.byType(DropdownButtonFormField<String>).first;
        await t.ensureVisible(assignee);
        await t.tap(assignee);
        await t.pumpAndSettle();
        final email = (api.f['workspace']['team'] as List).singleWhere(
          (p) => p['id'] == api.f['create_command']['assignee_id'],
        )['email'];
        await click(t, email);
        await click(t, 'Speichern');
        expect(api.posts, hasLength(1));
        expect(find.text('Synthetisch verlorene Bestätigung'), findsOneWidget);
        expect(
          t.widget<TextFormField>(find.byType(TextFormField).first).enabled,
          isFalse,
        );
        await click(t, 'Schließen');
        api.removed = true;
        await click(t, 'Anlage fortsetzen');
        expect(
          t
              .widget<TextFormField>(find.byType(TextFormField).first)
              .controller!
              .text,
          api.f['create_command']['title'],
        );
        expect(
          t.widget<TextFormField>(find.byType(TextFormField).first).enabled,
          isFalse,
        );
        await click(t, 'Erneut senden');
        expect(api.posts, hasLength(2));
        expect(api.posts.last, api.posts.first);
        expect(api.receipts, hasLength(1));
        expect(
          session.pending('project-milestone-${api.project}-new'),
          isFalse,
        );
        expect(find.byType(BusinessEditor), findsNothing);
      } finally {
        await closeMilestones(t, session, api);
      }
    },
  );

  testWidgets(
    'denied update retry retains original nonce and accepted historical receipt',
    (t) async {
      final api = MilestoneUiApi()..loseNext = true;
      final session = await mountMilestones(t, api);
      try {
        await click(t, 'Bearbeiten');
        await chooseStatus(t, 'Erreicht');
        await click(t, 'Speichern');
        api.rejectNext = const ApiException(
          403,
          'Synthetisch entzogene Schreibfreigabe',
        );
        await click(t, 'Erneut senden');
        final key =
            'project-milestone-${api.project}-${api.f['created']['id']}';
        expect(session.pending(key), isTrue);
        expect(api.posts.last, api.posts.first);
        await click(t, 'Schließen');
        await click(t, 'Änderung fortsetzen');
        await click(t, 'Erneut senden');
        expect(api.posts, hasLength(3));
        expect(api.posts.last, api.posts.first);
        expect(session.pending(key), isFalse);
      } finally {
        await closeMilestones(t, session, api);
      }
    },
  );

  testWidgets(
    'late project list cannot populate a different project or revoked view',
    (t) async {
      final api = MilestoneUiApi()..heldList = Completer<dynamic>();
      final first = await mountMilestones(t, api, settle: false);
      final second = BusinessSession(
        api: api,
        projectId: api.f['other_project_id'],
      );
      try {
        await second.load();
        await t.pumpWidget(
          MaterialApp(
            home: Scaffold(
              body: BusinessProjectMilestonesPage(session: second),
            ),
          ),
        );
        await t.pumpAndSettle();
        api.heldList!.complete({
          'schema_version': 1,
          'project_id': api.project,
          'items': [api.f['created']],
        });
        await t.pumpAndSettle();
        expect(find.text(api.f['created']['title']), findsNothing);
        expect(find.text('Noch keine Meilensteine'), findsOneWidget);
        api.read = false;
        await second.load();
        await t.pumpAndSettle();
        expect(find.textContaining('nicht verfügbar'), findsOneWidget);
        expect(api.posts, isEmpty);
      } finally {
        first.dispose();
        await closeMilestones(t, second, api);
      }
    },
  );

  for (final phase in ['in_flight', 'during_identity_check'])
    testWidgets(
      'reopening a create during $phase returns the original receipt without another POST',
      (t) async {
        final held = Completer<void>();
        final api = MilestoneUiApi(existing: false)..heldPost = held;
        final session = await mountMilestones(t, api);
        try {
          await click(t, 'Meilenstein anlegen');
          await t.enterText(
            find.byType(TextFormField).at(0),
            api.f['create_command']['title'],
          );
          await t.enterText(
            find.byType(TextFormField).at(1),
            api.f['create_command']['details'],
          );
          await t.enterText(find.byType(TextFormField).at(2), '30.11.2026');
          await t.ensureVisible(
            find.byType(DropdownButtonFormField<String>).first,
          );
          await t.tap(find.byType(DropdownButtonFormField<String>).first);
          await t.pumpAndSettle();
          final email = (api.f['workspace']['team'] as List).singleWhere(
            (p) => p['id'] == api.f['create_command']['assignee_id'],
          )['email'];
          await click(t, email);
          await t.tap(find.widgetWithText(FilledButton, 'Speichern'));
          await t.pump();
          expect(api.posts, hasLength(1));
          await t.tapAt(const Offset(5, 5));
          await t.pumpAndSettle();
          expect(find.byType(BusinessEditor), findsNothing);
          await click(t, 'Anlage fortsetzen');
          if (phase == 'during_identity_check')
            api.heldMe = Completer<dynamic>();
          await t.tap(find.widgetWithText(FilledButton, 'Erneut senden'));
          await t.pump();
          expect(api.posts, hasLength(1));
          held.complete();
          if (phase == 'during_identity_check') {
            await t.pump();
            expect(
              session.pending('project-milestone-${api.project}-new'),
              isFalse,
            );
            api.heldMe!.complete(copy(api.f['actor']));
          }
          await t.pumpAndSettle();
          expect(find.byType(BusinessEditor), findsNothing);
          expect(api.posts, hasLength(1));
          expect(api.receipts, hasLength(1));
          expect(
            session.pending('project-milestone-${api.project}-new'),
            isFalse,
          );
        } finally {
          if (!held.isCompleted) held.complete();
          if (api.heldMe?.isCompleted == false)
            api.heldMe!.complete(copy(api.f['actor']));
          await closeMilestones(t, session, api);
        }
      },
    );

  testWidgets(
    'missing capability skips milestone IO and read-only rights forbid edits',
    (t) async {
      final api = MilestoneUiApi()..feature = false;
      final session = await mountMilestones(t, api);
      try {
        expect(api.calls.where((p) => p.endsWith('/milestones')), isEmpty);
        expect(find.text('Meilenstein anlegen'), findsNothing);
        api.feature = true;
        api.write = false;
        await session.load();
        await t.pumpWidget(
          MaterialApp(
            home: Scaffold(
              body: BusinessProjectMilestonesPage(
                key: const ValueKey('fresh'),
                session: session,
              ),
            ),
          ),
        );
        await t.pumpAndSettle();
        expect(find.text(api.f['created']['title']), findsOneWidget);
        expect(find.text('Bearbeiten'), findsNothing);
        expect(api.posts, isEmpty);
      } finally {
        await closeMilestones(t, session, api);
      }
    },
  );
}

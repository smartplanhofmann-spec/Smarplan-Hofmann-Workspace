import 'dart:async';
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:smartplan_office/api.dart';
import 'package:smartplan_office/offline_plans.dart';
import 'package:smartplan_office/offline_vault.dart';

import 'offline_plans_test.dart' show PlanServer, TestDevice, idle;

const workspaceKinds = ['tasks', 'diary', 'appointments', 'links'];
const workspaceUserId = 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa';
const workspaceOtherUserId = 'bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb';
const workspaceProject = 'cccccccccccccccccccccccccccccccc';
const workspaceOtherProject = 'dddddddddddddddddddddddddddddddd';

Map<String, dynamic> workspaceInput(String kind, [String text = 'Local work']) {
  switch (kind) {
    case 'tasks':
      return {
        'title': text,
        'details': 'Synthetic task details',
        'status': 'todo',
        'priority': 'normal',
        'due_date': '2026-10-30',
        'assignee_id': null,
      };
    case 'diary':
      return {
        'entry_date': '2026-10-24',
        'work_performed': text,
        'issues': '',
        'next_steps': 'Continue tomorrow',
        'weather': 'Dry',
        'crew_count': 2,
      };
    case 'appointments':
      return {
        'title': text,
        'details': '',
        'start_at': '2026-10-26T08:00:00+00:00',
        'end_at': '2026-10-26T09:00:00+00:00',
        'status': 'scheduled',
      };
    case 'links':
      return {
        'title': text,
        'category': 'document',
        'url': 'https://example.test/synthetic-document',
        'active': true,
      };
    default:
      throw ArgumentError.value(kind);
  }
}

/// Stateful model of project_workspace.py: full lists, optimistic revisions and
/// receipts keyed by request ID. No external service participates in these tests.
class WorkspaceServer extends PlanServer {
  List<String> workspaceCapabilities = [
    'project_workspace',
    'offline_workspace',
  ];
  bool workspaceAvailable = true, loseWorkspaceAcknowledgment = false;
  int workspaceDeniedStatus = 403, nextWorkspaceId = 0;
  final workspaceRecords = <String, Map<String, dynamic>>{};
  final workspaceProfiles = <String, Map<String, dynamic>>{};
  final workspaceReceipts = <String, Map<String, dynamic>>{};
  final workspaceCommands = <Map<String, dynamic>>[];
  final workspaceReads = <String>[];
  Completer<void>? readStarted, releaseRead;
  Completer<void>? writeAccepted, releaseWrite;
  int? delayedReadStatus;
  String? failingWorkspaceRead;

  Map<String, dynamic> profile(String project) => offlineCopy(
    workspaceProfiles[project] ??
        {
          'project_id': project,
          'description': '',
          'site_address': '',
          'phase': 'planning',
          'deposit_status': 'not_recorded',
          'materials_status': 'not_recorded',
          'start_date': null,
          'end_date': null,
          'revision': 0,
          'updated_by': null,
          'updated_at': null,
        },
  );

  List<Map<String, dynamic>> items(String project, String kind) => [
    for (final record in workspaceRecords.values)
      if (record['project_id'] == project && record['_kind'] == kind)
        {...offlineCopy(record)}..remove('_kind'),
  ];

  Map<String, dynamic> seed(
    String kind, {
    String project = workspaceProject,
    String text = 'Server work',
    Map<String, dynamic> data = const {},
  }) {
    final id = (++nextWorkspaceId).toRadixString(16).padLeft(32, '0');
    final record = <String, dynamic>{
      ...workspaceInput(kind, text),
      ...data,
      'id': id,
      'project_id': project,
      'revision': 1,
      'created_by': workspaceUserId,
      'updated_by': workspaceUserId,
      'created_at': '2026-10-24T08:00:00+00:00',
      'updated_at': '2026-10-24T08:00:00+00:00',
      '_kind': kind,
    };
    workspaceRecords[id] = record;
    return {...offlineCopy(record)}..remove('_kind');
  }

  Map<String, dynamic> dashboard(String project) {
    final tasks = items(project, 'tasks');
    final appointments = items(project, 'appointments');
    final diary = items(project, 'diary');
    return {
      'project': {'id': project, 'name': 'Synthetic project'},
      'profile': profile(project),
      'team': [
        {'id': workspaceUserId, 'email': 'owner@example.test', 'role': 'owner'},
      ],
      'counters': {
        'tasks_open': tasks.where((v) => v['status'] == 'todo').length,
        'tasks_overdue': 0,
        'appointments_upcoming': appointments.length,
        'diary_entries': diary.length,
        'reports': 0,
        'plans': 0,
        'imports': 0,
      },
      'open_tasks': tasks.where((v) => v['status'] == 'todo').toList(),
      'upcoming_appointments': appointments.take(10).toList(),
      'latest_diary': diary.take(5).toList(),
      'links': items(
        project,
        'links',
      ).where((v) => v['active'] == true).toList(),
    };
  }

  void workspaceGuard() {
    if (!online) throw const ApiException(0, 'Offline');
    if (forbidden) {
      throw ApiException(workspaceDeniedStatus, 'Project no longer permitted');
    }
    if (!workspaceAvailable) throw const ApiException(404, 'Old server');
  }

  @override
  Future<dynamic> call(String path, [Map<String, dynamic>? body]) async {
    if (path == '/api/offline/access') {
      if (body == null || body.isNotEmpty) {
        throw const ApiException(
          400,
          'Offline grant still expects empty input',
        );
      }
      final value = Map<String, dynamic>.from(await super.call(path, body));
      value['capabilities'] = [...workspaceCapabilities];
      return value;
    }
    final route = RegExp(
      r'^/api/projects/([^/]+)/(workspace|tasks|diary|appointments|links)(?:/([^/]+))?$',
    ).firstMatch(path);
    if (route == null) return super.call(path, body);
    workspaceGuard();
    final project = route[1]!, kind = route[2]!, id = route[3];
    if (body == null) {
      workspaceReads.add(path);
      if (path == failingWorkspaceRead) {
        throw const ApiException(500, 'Synthetic failure in one full list');
      }
      final dynamic result;
      if (kind == 'workspace') {
        result = dashboard(project);
      } else if (id == null) {
        result = items(project, kind);
      } else {
        final record = workspaceRecords[id];
        if (record == null ||
            record['project_id'] != project ||
            record['_kind'] != kind) {
          throw const ApiException(404, 'Item not found');
        }
        result = {...offlineCopy(record)}..remove('_kind');
      }
      if (kind == 'workspace' && releaseRead != null) {
        final gate = releaseRead!;
        if (!readStarted!.isCompleted) readStarted!.complete();
        await gate.future;
        if (delayedReadStatus != null) {
          throw ApiException(
            delayedReadStatus!,
            'Delayed old account response',
          );
        }
      }
      return result;
    }
    final command = {'path': path, 'body': offlineCopy(body)};
    workspaceCommands.add(command);
    final requestId = body['request_id'];
    if (requestId is! String ||
        !RegExp(r'^[a-f0-9]{32}$').hasMatch(requestId)) {
      throw const ApiException(400, 'Request ID expected');
    }
    if (workspaceReceipts.containsKey(requestId)) {
      final first = workspaceCommands.firstWhere(
        (value) => value['body']['request_id'] == requestId,
      );
      if (!const DeepCollectionEqualityForWorkspace().equal(first, command)) {
        throw const ApiException(
          409,
          'Request ID reused with different command',
        );
      }
      return offlineCopy(workspaceReceipts[requestId]!);
    }
    final fields = kind == 'workspace'
        ? {
            'description',
            'site_address',
            'phase',
            'deposit_status',
            'materials_status',
            'start_date',
            'end_date',
          }
        : workspaceInput(kind).keys.toSet();
    if (body.keys.any(
          (key) => !{...fields, 'request_id', 'revision'}.contains(key),
        ) ||
        !body.keys.any(fields.contains)) {
      throw const ApiException(400, 'Unexpected workspace fields');
    }
    final Map<String, dynamic> result;
    if (kind == 'workspace') {
      final current = profile(project);
      if (body['revision'] != current['revision']) {
        throw const ApiException(409, 'Profile changed');
      }
      result = {
        ...current,
        for (final field in fields)
          if (body.containsKey(field)) field: body[field],
        'revision': (current['revision'] as int) + 1,
        'updated_by': workspaceUserId,
        'updated_at': '2026-10-24T09:00:00+00:00',
      };
      workspaceProfiles[project] = result;
    } else if (id == null) {
      if (body.containsKey('revision')) {
        throw const ApiException(400, 'Create has no revision');
      }
      result = seed(
        kind,
        project: project,
        data: {
          for (final field in fields)
            if (body.containsKey(field)) field: body[field],
        },
      );
    } else {
      final current = workspaceRecords[id];
      if (current == null ||
          current['project_id'] != project ||
          current['_kind'] != kind) {
        throw const ApiException(404, 'Item not found');
      }
      if (body['revision'] != current['revision']) {
        throw const ApiException(409, 'Item changed');
      }
      final changed = {
        ...current,
        for (final field in fields)
          if (body.containsKey(field)) field: body[field],
        'revision': (current['revision'] as int) + 1,
        'updated_at': '2026-10-24T09:00:00+00:00',
      };
      workspaceRecords[id] = changed;
      result = {...offlineCopy(changed)}..remove('_kind');
    }
    workspaceReceipts[requestId] = offlineCopy(result);
    if (releaseWrite != null) {
      final gate = releaseWrite!;
      if (!writeAccepted!.isCompleted) writeAccepted!.complete();
      await gate.future;
    }
    if (loseWorkspaceAcknowledgment) {
      loseWorkspaceAcknowledgment = false;
      throw const ApiException(0, 'Accepted but response lost');
    }
    return offlineCopy(result);
  }
}

/// Compare request structure independent of map insertion order.
class DeepCollectionEqualityForWorkspace {
  const DeepCollectionEqualityForWorkspace();
  bool equal(dynamic a, dynamic b) {
    if (a is Map && b is Map) {
      return a.length == b.length &&
          a.keys.every((key) => b.containsKey(key) && equal(a[key], b[key]));
    }
    if (a is List && b is List) {
      return a.length == b.length &&
          List.generate(
            a.length,
            (index) => index,
          ).every((index) => equal(a[index], b[index]));
    }
    return a == b;
  }
}

class WorkspaceDevice extends TestDevice {
  WorkspaceDevice(super.folder);
  bool failNextWrite = false;

  @override
  Future<OfflineVault> open(
    String server,
    String user, {
    bool create = false,
  }) async {
    final vault = await super.open(server, user, create: create);
    return WorkspaceVault(vault, this);
  }
}

class WorkspaceVault extends OfflineVault {
  WorkspaceVault(OfflineVault vault, this.device)
    : super(vault.directory, vault.key);
  final WorkspaceDevice device;

  @override
  Future<void> write(Map<String, dynamic> data) async {
    if (device.failNextWrite) {
      device.failNextWrite = false;
      throw const FileSystemException('Synthetic workspace disk failure');
    }
    await super.write(data);
  }
}

void main() {
  late Directory directory;
  late WorkspaceDevice device;
  late WorkspaceServer server;
  late OfflinePlans repo;
  late DateTime now;
  final user = <String, dynamic>{
    'id': workspaceUserId,
    'email': 'owner@example.test',
    'role': 'owner',
  };
  final projects = [
    {'id': workspaceProject, 'name': 'Synthetic project'},
  ];
  OfflinePlans open() => OfflinePlans(
    api: server,
    transport: server,
    device: device,
    clock: () => now,
  );
  Future<void> restart() async {
    await idle(repo);
    await repo.leave();
    repo.dispose();
    repo = open();
    await repo.resume();
    await idle(repo);
  }

  List<dynamic> cachedItems(String kind) =>
      repo.getWorkspace(workspaceProject)![kind] as List;
  Map<String, dynamic> cachedItem(String kind, String localId) =>
      Map<String, dynamic>.from(
        cachedItems(kind).singleWhere((item) => item['local_id'] == localId),
      );
  Matcher status(int expected) =>
      isA<ApiException>().having((error) => error.status, 'status', expected);

  setUp(() async {
    directory = await Directory.systemTemp.createTemp('smartplan-workspace-');
    device = WorkspaceDevice(directory);
    server = WorkspaceServer()..token = 'full-session';
    now = DateTime.utc(2026, 10, 24, 12);
    repo = open();
    await repo.login(user, projects);
    await idle(repo);
    server.online = false;
  });
  tearDown(() async {
    for (final gate in [server.releaseRead, server.releaseWrite]) {
      if (gate != null && !gate.isCompleted) gate.complete();
    }
    await idle(repo);
    await repo.flush();
    repo.dispose();
    server.dispose();
    await directory.delete(recursive: true);
  });

  test('Full workspace is encrypted and survives an offline restart', () async {
    final task = server.seed(
      'tasks',
      text: 'Private completed task',
      data: {'status': 'done'},
    );
    for (final kind in ['diary', 'appointments', 'links']) {
      server.seed(kind, text: 'Private synthetic $kind');
    }
    server.seed(
      'links',
      text: 'Inactive synthetic link',
      data: {'active': false},
    );
    expect(repo.workspaceSupported, isTrue);
    expect(repo.getWorkspace(workspaceProject), isNull);
    server.online = true;
    await repo.refreshWorkspace(workspaceProject);
    final workspace = repo.getWorkspace(workspaceProject)!;
    expect(workspace['project']['id'], workspaceProject);
    expect(workspace['profile']['revision'], 0);
    expect(workspace['team'], hasLength(1));
    expect(workspace['open_tasks'], isEmpty);
    expect((workspace['tasks'] as List).single['server_id'], task['id']);
    expect(workspace['links'], hasLength(2));
    expect(workspace['active_links'], hasLength(1));
    expect(
      server.workspaceReads.toSet(),
      containsAll([
        '/api/projects/$workspaceProject/workspace',
        for (final kind in workspaceKinds)
          '/api/projects/$workspaceProject/$kind',
      ]),
    );
    final files = await directory
        .list(recursive: true)
        .where((file) => file is File)
        .cast<File>()
        .toList();
    for (final file in files) {
      expect(await file.readAsString(), isNot(contains('Private synthetic')));
      expect(
        await file.readAsString(),
        isNot(contains('Private completed task')),
      );
    }
    server.online = false;
    await restart();
    expect(repo.getWorkspace(workspaceProject), workspace);
    final copy = repo.getWorkspace(workspaceProject)!;
    copy['tasks'][0]['title'] = 'Mutation outside repository';
    copy['profile']['description'] = 'Outside profile mutation';
    expect(repo.getWorkspace(workspaceProject), workspace);
  });

  for (final capabilities in <List<String>>[
    [],
    ['project_workspace'],
    ['offline_workspace'],
  ]) {
    test(
      'Incomplete grant $capabilities never gains workspace scope',
      () async {
        server.online = true;
        await repo.refreshWorkspace(workspaceProject);
        server.workspaceCapabilities = capabilities;
        await repo.login(user, projects);
        await idle(repo);
        expect(repo.workspaceSupported, isFalse);
        expect(repo.getWorkspace(workspaceProject), isNull);
        final readsBefore = server.workspaceReads.length;
        await expectLater(
          repo.refreshWorkspace(workspaceProject),
          throwsA(status(403)),
        );
        expect(server.workspaceReads, hasLength(readsBefore));
        await expectLater(
          repo.saveWorkspaceItem(
            workspaceProject,
            'tasks',
            workspaceInput('tasks'),
          ),
          throwsA(isA<ApiException>()),
        );
        expect(server.workspaceCommands, isEmpty);
        expect(repo.pending, 0);
        expect(repo.canAccessProject(workspaceProject), isTrue);
      },
    );
  }

  test(
    'Initial full cache is required before creating offline items',
    () async {
      await expectLater(
        repo.saveWorkspaceItem(
          workspaceProject,
          'tasks',
          workspaceInput('tasks'),
        ),
        throwsA(isA<ApiException>()),
      );
      await expectLater(
        repo.saveWorkspaceProfile(workspaceProject, {
          'description': 'No baseline',
        }),
        throwsA(isA<ApiException>()),
      );
      expect(repo.pending, 0);
      expect(repo.getWorkspace(workspaceProject), isNull);
    },
  );

  test(
    'A failed full-list fetch never publishes a partial workspace',
    () async {
      final task = server.seed('tasks', text: 'Previous complete snapshot');
      server.online = true;
      await repo.refreshWorkspace(workspaceProject);
      final previous = repo.getWorkspace(workspaceProject)!;
      server.workspaceRecords[task['id']]!.addAll({
        'title': 'New server task',
        'revision': 2,
      });
      server.workspaceProfiles[workspaceProject] = {
        ...server.profile(workspaceProject),
        'description': 'New server profile',
        'revision': 1,
      };
      server.failingWorkspaceRead = '/api/projects/$workspaceProject/links';
      await expectLater(
        repo.refreshWorkspace(workspaceProject),
        throwsA(status(500)),
      );
      expect(repo.getWorkspace(workspaceProject), previous);
      expect(repo.canAccessProject(workspaceProject), isTrue);
      server.online = false;
      await restart();
      expect(repo.getWorkspace(workspaceProject), previous);
      server.failingWorkspaceRead = null;
      server.online = true;
      await repo.refreshWorkspace(workspaceProject);
      expect(cachedItems('tasks').single['title'], 'New server task');
      expect(
        repo.getWorkspace(workspaceProject)!['profile']['description'],
        'New server profile',
      );
    },
  );

  test(
    'Losing workspace grant retains queued work without using old scope',
    () async {
      server.online = true;
      await repo.refreshWorkspace(workspaceProject);
      server.online = false;
      final local = await repo.saveWorkspaceItem(
        workspaceProject,
        'tasks',
        workspaceInput('tasks', 'Retained across older server login'),
      );
      await idle(repo);
      server.workspaceCapabilities = ['project_workspace'];
      server.online = true;
      await repo.login(user, projects);
      await idle(repo);
      expect(repo.workspaceSupported, isFalse);
      expect(repo.getWorkspace(workspaceProject), isNull);
      expect(repo.pending, 1);
      expect(server.workspaceCommands, isEmpty);
      expect(repo.canAccessProject(workspaceProject), isTrue);
      final vault = await device.open(repo.server, workspaceUserId);
      expect(
        (await vault.read()).toString(),
        contains('Retained across older server login'),
      );
      server.workspaceCapabilities = ['project_workspace', 'offline_workspace'];
      await repo.login(user, projects);
      await idle(repo);
      expect(repo.pending, 0);
      expect(
        cachedItem('tasks', local['local_id'])['title'],
        'Retained across older server login',
      );
      expect(server.workspaceRecords, hasLength(1));
    },
  );

  test(
    'All four offline kinds persist and synchronize with stable local IDs',
    () async {
      server.online = true;
      await repo.refreshWorkspace(workspaceProject);
      server.online = false;
      final local = <String, Map<String, dynamic>>{};
      for (final kind in workspaceKinds) {
        final input = workspaceInput(kind, 'Offline $kind');
        local[kind] = await repo.saveWorkspaceItem(
          workspaceProject,
          kind,
          input,
        );
        input[input.containsKey('title') ? 'title' : 'work_performed'] =
            'Caller mutation';
        expect(local[kind]!['local_id'], matches(RegExp(r'^[a-f0-9]{32}$')));
        expect(local[kind]!['server_id'], isNull);
        expect(local[kind]!['id'], local[kind]!['local_id']);
        expect(local[kind]!['sync_status'], 'Wartet auf Verbindung');
      }
      await idle(repo);
      expect(repo.pending, 4);
      await restart();
      expect(repo.pending, 4);
      for (final kind in workspaceKinds) {
        final item = cachedItem(kind, local[kind]!['local_id']);
        expect(
          item[kind == 'diary' ? 'work_performed' : 'title'],
          'Offline $kind',
        );
      }
      server.online = true;
      await repo.sync();
      expect(repo.pending, 0);
      expect(server.workspaceRecords, hasLength(4));
      for (final kind in workspaceKinds) {
        final item = cachedItem(kind, local[kind]!['local_id']);
        expect(item['id'], item['server_id']);
        expect(item['local_id'], local[kind]!['local_id']);
        expect(item['revision'], 1);
        expect(item['sync_status'], 'Synchronisiert');
      }
      expect(
        server.workspaceCommands.every(
          (value) => !(value['body'] as Map).containsKey('revision'),
        ),
        isTrue,
      );
    },
  );

  test(
    'Lost create acknowledgment retries an identical command after restart',
    () async {
      server.online = true;
      await repo.refreshWorkspace(workspaceProject);
      server.loseWorkspaceAcknowledgment = true;
      final local = await repo.saveWorkspaceItem(
        workspaceProject,
        'tasks',
        workspaceInput('tasks', 'Once only'),
      );
      await idle(repo);
      expect(repo.pending, 1);
      expect(server.workspaceRecords, hasLength(1));
      final first = offlineCopy(server.workspaceCommands.single);
      server.online = false;
      await restart();
      server.online = true;
      await repo.sync();
      expect(repo.pending, 0);
      expect(server.workspaceRecords, hasLength(1));
      expect(server.workspaceCommands, [first, first]);
      expect(
        cachedItem('tasks', local['local_id'])['server_id'],
        server.workspaceRecords.keys.single,
      );
    },
  );

  test('Editing during accepted upload queues a new revision without losing either intent', () async {
    server.online = true;
    await repo.refreshWorkspace(workspaceProject);
    server.writeAccepted = Completer<void>();
    server.releaseWrite = Completer<void>();
    final first = await repo.saveWorkspaceItem(
      workspaceProject,
      'tasks',
      workspaceInput('tasks', 'First draft'),
    );
    await server.writeAccepted!.future;
    await repo.saveWorkspaceItem(
      workspaceProject,
      'tasks',
      workspaceInput('tasks', 'Latest draft'),
      id: first['local_id'],
    );
    server.releaseWrite!.complete();
    await idle(repo);
    expect(repo.pending, 0);
    expect(server.workspaceRecords, hasLength(1));
    final result = cachedItem('tasks', first['local_id']);
    expect(result['title'], 'Latest draft');
    expect(result['revision'], 2);
    expect(server.workspaceRecords.values.single['title'], 'Latest draft');
    expect(
      server.workspaceCommands
          .map((value) => value['body']['request_id'])
          .toSet(),
      hasLength(2),
    );
  });

  for (final kind in ['tasks', 'profile']) {
    test(
      'Stale $kind editor preserves its draft without rebasing onto a refreshed revision',
      () async {
        final String id;
        if (kind == 'profile') {
          server.workspaceProfiles[workspaceProject] = {
            ...server.profile(workspaceProject),
            'description': 'Profile when editor opened',
            'revision': 1,
          };
          id = workspaceProject;
        } else {
          id = server.seed('tasks', text: 'Task when editor opened')['id'];
        }
        Map<String, dynamic> view() => kind == 'profile'
            ? Map<String, dynamic>.from(
                repo.getWorkspace(workspaceProject)!['profile'],
              )
            : cachedItem('tasks', id);
        server.online = true;
        await repo.refreshWorkspace(workspaceProject);
        final editorRevision = view()['revision'];
        expect(editorRevision, 1);
        final field = kind == 'profile' ? 'description' : 'title';
        final current = kind == 'profile'
            ? server.workspaceProfiles[workspaceProject]!
            : server.workspaceRecords[id]!;
        current.addAll({field: 'Changed by another device', 'revision': 2});
        await repo.refreshWorkspace(workspaceProject);
        expect(view()['revision'], 2);
        expect(view()[field], 'Changed by another device');
        final input = <String, dynamic>{
          field: 'Old form private draft',
          'revision': editorRevision,
        };
        final saved = kind == 'profile'
            ? await repo.saveWorkspaceProfile(workspaceProject, input)
            : await repo.saveWorkspaceItem(
                workspaceProject,
                'tasks',
                input,
                id: id,
              );
        await idle(repo);
        await repo.sync();
        expect(saved['sync_status'], 'Konflikt');
        expect(view()[field], 'Old form private draft');
        expect(view()['remote'][field], 'Changed by another device');
        expect(view()['remote']['revision'], 2);
        expect(repo.pending, 1);
        expect(server.workspaceCommands, isEmpty);
        expect(current[field], 'Changed by another device');
        expect(current['revision'], 2);
        server.online = false;
        await restart();
        expect(view()[field], 'Old form private draft');
        expect(view()['sync_status'], 'Konflikt');
        expect(view()['remote']['revision'], 2);
        expect(repo.pending, 1);
        expect(server.workspaceCommands, isEmpty);
        await repo.resolveWorkspaceConflict(
          workspaceProject,
          kind,
          id,
          keepLocal: true,
        );
        await idle(repo);
        expect(server.workspaceCommands, isEmpty);
        server.online = true;
        await repo.sync();
        expect(repo.pending, 0);
        expect(server.workspaceCommands, hasLength(1));
        expect(server.workspaceCommands.single['body']['revision'], 2);
        expect(view()[field], 'Old form private draft');
        expect(view()['revision'], 3);
        expect(view()['sync_status'], 'Synchronisiert');
      },
    );
  }

  for (final keepLocal in [false, true]) {
    test(
      '409 item conflict survives restart and resolves keepLocal=$keepLocal',
      () async {
        final original = server.seed('tasks', text: 'Original server task');
        server.online = true;
        await repo.refreshWorkspace(workspaceProject);
        final id = (cachedItems('tasks').single as Map)['local_id'] as String;
        server.online = false;
        await repo.saveWorkspaceItem(
          workspaceProject,
          'tasks',
          workspaceInput('tasks', 'Local conflicting draft'),
          id: id,
        );
        await idle(repo);
        server.workspaceRecords[original['id']]!.addAll({
          'title': 'Other device revision',
          'revision': 2,
        });
        server.online = true;
        await repo.sync();
        expect(repo.pending, 1);
        expect(cachedItem('tasks', id)['sync_status'], 'Konflikt');
        expect(cachedItem('tasks', id)['title'], 'Local conflicting draft');
        expect(
          cachedItem('tasks', id)['remote']['title'],
          'Other device revision',
        );
        final rejectedRequest =
            server.workspaceCommands.single['body']['request_id'];
        server.online = false;
        await restart();
        expect(cachedItem('tasks', id)['sync_status'], 'Konflikt');
        await repo.resolveWorkspaceConflict(
          workspaceProject,
          'tasks',
          id,
          keepLocal: keepLocal,
        );
        await idle(repo);
        if (keepLocal) {
          expect(repo.pending, 1);
          server.online = true;
          await repo.sync();
          expect(server.workspaceCommands.last['body']['revision'], 2);
          expect(
            server.workspaceCommands.last['body']['request_id'],
            isNot(rejectedRequest),
          );
          expect(
            server.workspaceRecords[original['id']]!['title'],
            'Local conflicting draft',
          );
          expect(server.workspaceRecords[original['id']]!['revision'], 3);
        } else {
          expect(cachedItem('tasks', id)['title'], 'Other device revision');
          expect(server.workspaceCommands, hasLength(1));
        }
        expect(repo.pending, 0);
        expect(server.workspaceRecords, hasLength(1));
        expect(cachedItem('tasks', id)['local_id'], id);
        expect(cachedItem('tasks', id)['sync_status'], 'Synchronisiert');
      },
    );
  }

  for (final keepLocal in [false, true]) {
    test(
      'Profile revision zero and conflict use project identity, keepLocal=$keepLocal',
      () async {
        server.online = true;
        await repo.refreshWorkspace(workspaceProject);
        server.online = false;
        await repo.saveWorkspaceProfile(workspaceProject, {
          'description': 'Private local description',
          'phase': 'execution',
        });
        await idle(repo);
        server.workspaceProfiles[workspaceProject] = {
          ...server.profile(workspaceProject),
          'description': 'Office description',
          'revision': 1,
        };
        server.online = true;
        await repo.sync();
        expect(server.workspaceCommands.single['body']['revision'], 0);
        final conflicted = repo.getWorkspace(workspaceProject)!['profile'];
        expect(conflicted['description'], 'Private local description');
        expect(conflicted['sync_status'], 'Konflikt');
        expect(conflicted['remote']['description'], 'Office description');
        server.online = false;
        await restart();
        await repo.resolveWorkspaceConflict(
          workspaceProject,
          'profile',
          workspaceProject,
          keepLocal: keepLocal,
        );
        await idle(repo);
        if (keepLocal) {
          server.online = true;
          await repo.sync();
          expect(server.workspaceCommands.last['body']['revision'], 1);
          expect(
            server.workspaceProfiles[workspaceProject]!['description'],
            'Private local description',
          );
          expect(server.workspaceProfiles[workspaceProject]!['revision'], 2);
        } else {
          expect(
            repo.getWorkspace(workspaceProject)!['profile']['description'],
            'Office description',
          );
          expect(server.workspaceCommands, hasLength(1));
        }
        expect(repo.pending, 0);
      },
    );
  }

  test('A failed local snapshot retains the prior workspace and outbox after restart', () async {
    server.online = true;
    await repo.refreshWorkspace(workspaceProject);
    server.online = false;
    final first = await repo.saveWorkspaceItem(
      workspaceProject,
      'tasks',
      workspaceInput('tasks', 'Durable draft'),
    );
    await idle(repo);
    device.failNextWrite = true;
    await expectLater(
      repo.saveWorkspaceItem(
        workspaceProject,
        'tasks',
        workspaceInput('tasks', 'Never committed'),
        id: first['local_id'],
      ),
      throwsA(isA<FileSystemException>()),
    );
    expect(cachedItem('tasks', first['local_id'])['title'], 'Durable draft');
    expect(repo.pending, 1);
    await restart();
    expect(cachedItem('tasks', first['local_id'])['title'], 'Durable draft');
    expect(repo.pending, 1);
  });

  test('Seven-day expiry hides workspace but retains pending drafts until reauthentication', () async {
    server.online = true;
    await repo.refreshWorkspace(workspaceProject);
    server.online = false;
    final draft = await repo.saveWorkspaceItem(
      workspaceProject,
      'diary',
      workspaceInput('diary', 'Retained field notes'),
    );
    await idle(repo);
    now = now.add(const Duration(days: 7));
    expect(repo.workspaceSupported, isFalse);
    expect(() => repo.getWorkspace(workspaceProject), throwsA(status(401)));
    await expectLater(
      repo.saveWorkspaceProfile(workspaceProject, {'description': 'Expired'}),
      throwsA(status(401)),
    );
    expect(repo.pending, 1);
    final vault = await device.open(repo.server, workspaceUserId);
    final durable = await vault.read();
    expect(durable.toString(), contains('Retained field notes'));
    server.online = true;
    await repo.login(user, projects);
    await idle(repo);
    expect(repo.pending, 0);
    expect(
      cachedItem('diary', draft['local_id'])['work_performed'],
      'Retained field notes',
    );
  });

  test('Project revocation hides cached workspace while retaining its local outbox', () async {
    server.online = true;
    await repo.refreshWorkspace(workspaceProject);
    server.online = false;
    final draft = await repo.saveWorkspaceItem(
      workspaceProject,
      'tasks',
      workspaceInput('tasks', 'Keep if reassigned'),
    );
    await idle(repo);
    server.online = true;
    server.forbidden = true;
    server.workspaceDeniedStatus = 404;
    await expectLater(
      repo.refreshWorkspace(workspaceProject),
      throwsA(status(404)),
    );
    expect(repo.canAccessProject(workspaceProject), isFalse);
    expect(() => repo.getWorkspace(workspaceProject), throwsA(status(403)));
    expect(repo.pending, 1);
    final vault = await device.open(repo.server, workspaceUserId);
    expect((await vault.read()).toString(), contains('Keep if reassigned'));
    server.forbidden = false;
    await repo.login(user, projects);
    await idle(repo);
    expect(repo.pending, 0);
    expect(
      cachedItem('tasks', draft['local_id'])['title'],
      'Keep if reassigned',
    );
  });

  test(
    'Read-only roles can read downloaded workspace but cannot queue writes',
    () async {
      server.seed('tasks');
      server.online = true;
      await repo.refreshWorkspace(workspaceProject);
      await repo.login({...user, 'role': 'accountant'}, projects);
      await idle(repo);
      server.online = false;
      expect(cachedItems('tasks'), hasLength(1));
      await expectLater(
        repo.saveWorkspaceItem(
          workspaceProject,
          'tasks',
          workspaceInput('tasks'),
        ),
        throwsA(status(403)),
      );
      await expectLater(
        repo.saveWorkspaceProfile(workspaceProject, {
          'description': 'Unauthorized',
        }),
        throwsA(status(403)),
      );
      expect(repo.pending, 0);
      expect(server.workspaceCommands, isEmpty);
    },
  );

  test(
    'Technicians may queue items but profile remains owner/manager scoped',
    () async {
      server.online = true;
      await repo.refreshWorkspace(workspaceProject);
      await repo.login({...user, 'role': 'technician'}, projects);
      await idle(repo);
      server.online = false;
      await repo.saveWorkspaceItem(
        workspaceProject,
        'diary',
        workspaceInput('diary'),
      );
      await expectLater(
        repo.saveWorkspaceProfile(workspaceProject, {'phase': 'execution'}),
        throwsA(status(403)),
      );
      expect(repo.pending, 1);
    },
  );

  test(
    'Unknown project and foreign item identity cannot mutate the local cache',
    () async {
      final other = server.seed('tasks', project: workspaceOtherProject);
      server.online = true;
      await repo.refreshWorkspace(workspaceProject);
      server.online = false;
      expect(
        () => repo.getWorkspace(workspaceOtherProject),
        throwsA(status(403)),
      );
      await expectLater(
        repo.refreshWorkspace(workspaceOtherProject),
        throwsA(status(403)),
      );
      await expectLater(
        repo.saveWorkspaceItem(
          workspaceOtherProject,
          'tasks',
          workspaceInput('tasks'),
        ),
        throwsA(status(403)),
      );
      await expectLater(
        repo.saveWorkspaceItem(
          workspaceProject,
          'tasks',
          workspaceInput('tasks'),
          id: other['id'],
        ),
        throwsA(isA<ApiException>()),
      );
      expect(cachedItems('tasks'), isEmpty);
      expect(repo.pending, 0);
      expect(server.workspaceCommands, isEmpty);
    },
  );

  for (final delayedStatus in [null, 401, 403, 404]) {
    test(
      'Late workspace refresh $delayedStatus cannot publish or lock another account',
      () async {
        server.seed('tasks', text: 'Account A remote value');
        server.online = true;
        server.readStarted = Completer<void>();
        server.releaseRead = Completer<void>();
        server.delayedReadStatus = delayedStatus;
        final refresh = repo
            .refreshWorkspace(workspaceProject)
            .then<void>((_) {}, onError: (Object error) {});
        await server.readStarted!.future;
        await repo.login({...user, 'id': workspaceOtherUserId}, projects);
        server.releaseRead!.complete();
        await refresh;
        await idle(repo);
        expect(repo.user['id'], workspaceOtherUserId);
        expect(repo.permitted, isTrue);
        expect(repo.canAccessProject(workspaceProject), isTrue);
        expect(repo.getWorkspace(workspaceProject), isNull);
        expect(repo.pending, 0);
      },
    );
  }

  test(
    'Late accepted write cannot populate a newly selected account',
    () async {
      server.online = true;
      await repo.refreshWorkspace(workspaceProject);
      server.writeAccepted = Completer<void>();
      server.releaseWrite = Completer<void>();
      final local = await repo.saveWorkspaceItem(
        workspaceProject,
        'tasks',
        workspaceInput('tasks', 'Account A draft'),
      );
      await server.writeAccepted!.future;
      await repo.login({...user, 'id': workspaceOtherUserId}, projects);
      server.releaseWrite!.complete();
      await idle(repo);
      expect(repo.user['id'], workspaceOtherUserId);
      expect(repo.getWorkspace(workspaceProject), isNull);
      expect(repo.pending, 0);
      server.online = false;
      final aVault = await device.open(repo.server, workspaceUserId);
      expect((await aVault.read()).toString(), contains(local['local_id']));
    },
  );
}

import 'dart:async';
import 'dart:io';
import 'dart:typed_data';

import 'package:flutter_test/flutter_test.dart';
import 'package:smartplan_office/api.dart';
import 'package:smartplan_office/offline_plans.dart';
import 'package:smartplan_office/offline_vault.dart';

import 'offline_imports_test.dart'
    show ImportServer, previewPng, checksum, syntheticPdf;
import 'offline_plans_test.dart' show TestDevice, idle;
import 'offline_assets_test.dart' show InterruptedFile, nativeFile;

/// Inject metadata failures while retaining real snapshot encryption, source
/// files and account keys. A failed commit must never become visible in memory.
class ControlledDevice extends TestDevice {
  ControlledDevice(super.folder);
  bool failNext = false;
  Completer<void>? writeStarted;
  Completer<void>? releaseWrite;

  void pauseNextWrite() {
    writeStarted = Completer<void>();
    releaseWrite = Completer<void>();
  }

  @override
  Future<OfflineVault> open(
    String server,
    String user, {
    bool create = false,
  }) async {
    final vault = await super.open(server, user, create: create);
    return ControlledVault(vault, this);
  }
}

class ControlledVault extends OfflineVault {
  ControlledVault(OfflineVault vault, this.control)
    : super(vault.directory, vault.key);
  final ControlledDevice control;

  @override
  Future<void> write(Map<String, dynamic> data) async {
    final gate = control.releaseWrite;
    if (gate != null && !control.writeStarted!.isCompleted) {
      control.writeStarted!.complete();
      await gate.future;
      control.releaseWrite = null;
    }
    if (control.failNext) {
      control.failNext = false;
      throw const FileSystemException('Synthetic metadata disk failure');
    }
    await super.write(data);
  }
}

/// Models the confirmed delete-by-ID/create-request protocol and project-scoped
/// tombstone feed. Accepted deletes are durable before an optional lost reply.
class DeletionServer extends ImportServer {
  bool loseDeleteAcknowledgment = false;
  bool losePlanCreateAcknowledgment = false;
  bool hideDeletionFeed = false;
  final deletedImports = <String>{};
  final deletedPlans = <String>{};
  final cancelledImportCreates = <String>{};
  final cancelledPlanCreates = <String>{};
  final deletionEvents = <Map<String, dynamic>>[];
  final deletionReceipts = <String, Map<String, dynamic>>{};
  final deleteBodies = <Map<String, dynamic>>[];
  final deletePaths = <String>[];
  final planRequestBodies = <String, Map<String, dynamic>>{};
  int nextPlan = 0;
  Completer<void>? chunkAccepted;
  Completer<void>? releaseChunk;
  Completer<void>? planAccepted, releasePlanReply;
  Completer<void>? manifestAccepted, releaseManifestReply;
  Completer<void>? planListStarted, releasePlanList;
  bool deletePlanDuringConflict = false;
  bool corruptSourceDownload = false;
  int sourceDownloads = 0;
  Completer<void>? twoSourceDownloads;

  @override
  Future<dynamic> call(String path, [Map<String, dynamic>? body]) async {
    if (path == '/api/offline/access') {
      final grant = Map<String, dynamic>.from(await super.call(path, body));
      grant['capabilities'] = [
        ...((grant['capabilities'] as List?) ?? []),
        'plan_deletion',
      ];
      return grant;
    }
    final feed = RegExp(r'^/api/projects/([^/]+)/plan-deletions$')
        .firstMatch(path);
    if (feed != null) {
      guard();
      if (hideDeletionFeed) return <dynamic>[];
      return [
        for (final event in deletionEvents)
          if (event['project_id'] == feed[1]) offlineCopy(event),
      ];
    }
    final deletion = RegExp(
      r'^/api/projects/([^/]+)/(plans|plan-imports)/delete$',
    ).firstMatch(path);
    if (deletion != null) {
      guard();
      if (body == null ||
          body.keys.any(
            (key) => !{'request_id', 'id', 'create_request_id'}.contains(key),
          ) ||
          body['request_id'] is! String ||
          !RegExp(r'^[a-f0-9]{32}$').hasMatch(body['request_id']) ||
          (body['id'] == null && body['create_request_id'] == null)) {
        throw const ApiException(400, 'Invalid deletion command');
      }
      deleteBodies.add(offlineCopy(body));
      deletePaths.add(path);
      final request = body['request_id'] as String;
      if (deletionReceipts.containsKey(request)) {
        final previous = deleteBodies.firstWhere(
          (value) => value['request_id'] == request,
        );
        if (previous.length != body.length ||
            previous.keys.any((key) => previous[key] != body[key])) {
          throw const ApiException(409, 'Deletion request changed');
        }
        return offlineCopy(deletionReceipts[request]!);
      }
      final kind = deletion[2] == 'plans' ? 'plan' : 'import';
      final createRequest = body['create_request_id'] as String?;
      var id = body['id'] as String?;
      if (kind == 'import') {
        id ??= createRequest == null ? null : importRequests[createRequest];
        if (createRequest != null) cancelledImportCreates.add(createRequest);
        if (id != null) {
          if (records[id] != null &&
              records[id]!['project_id'] != deletion[1]) {
            throw const ApiException(404, 'Project not available');
          }
          deletedImports.add(id);
          cancelledImportCreates.addAll(
            importRequests.entries
                .where((entry) => entry.value == id)
                .map((entry) => entry.key),
          );
          records.remove(id);
          sources.remove(id);
          chunks.remove(id);
          previews.remove(id);
          results.remove(id);
        }
      } else {
        id ??= createRequest == null
            ? null
            : requests[createRequest]?['id'] as String?;
        if (createRequest != null) cancelledPlanCreates.add(createRequest);
        if (id != null) {
          if (plans[id] != null && plans[id]!['project_id'] != deletion[1]) {
            throw const ApiException(404, 'Project not available');
          }
          deletedPlans.add(id);
          cancelledPlanCreates.addAll(
            requests.entries
                .where((entry) => entry.value['id'] == id)
                .map((entry) => entry.key),
          );
          plans.remove(id);
        }
      }
      final receipt = <String, dynamic>{
        'deleted': true,
        'kind': kind,
        'id': id,
        'project_id': deletion[1],
        'status': 'deleted',
        'deleted_at': now.toUtc().toIso8601String(),
        if (createRequest != null) 'create_request_id': createRequest,
      };
      deletionReceipts[request] = receipt;
      deletionEvents.add(receipt);
      if (loseDeleteAcknowledgment) {
        loseDeleteAcknowledgment = false;
        throw const ApiException(0, 'Delete accepted, response lost');
      }
      return offlineCopy(receipt);
    }
    final importItem = RegExp(
      r'^/api/projects/([^/]+)/plan-imports/([a-f0-9]{32})(?:/complete)?$',
    ).firstMatch(path);
    if (importItem != null && deletedImports.contains(importItem[2])) {
      guard();
      throw const ApiException(410, 'Import deleted');
    }
    if (path.endsWith('/plan-imports') &&
        body != null &&
        cancelledImportCreates.contains(body['request_id'])) {
      guard();
      throw const ApiException(410, 'Import create request cancelled');
    }
    final plan = RegExp(r'^/api/projects/([^/]+)/plans(?:/([a-f0-9]{32}))?$')
        .firstMatch(path);
    if (plan != null) {
      guard();
      final id = plan[2];
      if (id != null && deletedPlans.contains(id)) {
        throw const ApiException(410, 'Plan deleted');
      }
      if (body == null) {
        if (id == null) {
          final snapshot = [
            for (final value in plans.values) offlineCopy(value),
          ];
          if (planListStarted != null && !planListStarted!.isCompleted) {
            planListStarted!.complete();
            await releasePlanList!.future;
          }
          return snapshot;
        }
        if (plans[id] == null)
          throw const ApiException(404, 'Plan unavailable');
        return offlineCopy(plans[id]!);
      }
      final request = body['request_id'] as String;
      if (id != null && deletePlanDuringConflict) {
        deletePlanDuringConflict = false;
        deletedPlans.add(id);
        plans.remove(id);
        throw const ApiException(409, 'Concurrent deletion');
      }
      if (cancelledPlanCreates.contains(request)) {
        throw const ApiException(410, 'Plan create request cancelled');
      }
      if (requests.containsKey(request)) return offlineCopy(requests[request]!);
      if (id != null && body['revision'] != plans[id]?['revision']) {
        throw const ApiException(409, 'Plan changed');
      }
      final serverId = id ?? (++nextPlan).toRadixString(16).padLeft(32, '0');
      final result = <String, dynamic>{
        'id': serverId,
        'project_id': plan[1],
        'title': body['title'],
        'walls': body['walls'],
        'revision': id == null ? 1 : plans[id]!['revision'] + 1,
      };
      plans[serverId] = result;
      requests[request] = result;
      planRequestBodies[request] = offlineCopy(body);
      if (planAccepted != null && !planAccepted!.isCompleted) {
        planAccepted!.complete();
        await releasePlanReply!.future;
      }
      if (losePlanCreateAcknowledgment) {
        losePlanCreateAcknowledgment = false;
        throw const ApiException(0, 'Plan accepted, response lost');
      }
      return offlineCopy(result);
    }
    final response = await super.call(path, body);
    if (path.endsWith('/plan-imports') &&
        body != null &&
        manifestAccepted != null &&
        !manifestAccepted!.isCompleted) {
      manifestAccepted!.complete();
      await releaseManifestReply!.future;
    }
    return response;
  }

  @override
  Future<dynamic> putChunk(String path, Uint8List bytes) async {
    final id = path.split('/')[5];
    if (deletedImports.contains(id)) {
      guard();
      throw const ApiException(410, 'Import deleted');
    }
    final response = await super.putChunk(path, bytes);
    if (chunkAccepted != null && !chunkAccepted!.isCompleted) {
      chunkAccepted!.complete();
      await releaseChunk!.future;
    }
    return response;
  }

  @override
  Future<Uint8List> bytes(
    String path, {
    required String mediaType,
    int maxBytes = 20 * 1024 * 1024,
  }) async {
    final id = path.split('/')[5];
    if (deletedImports.contains(id)) {
      guard();
      throw const ApiException(410, 'Import deleted');
    }
    if (path.endsWith('/source')) {
      sourceDownloads++;
      if (sourceDownloads >= 2 &&
          twoSourceDownloads != null &&
          !twoSourceDownloads!.isCompleted) {
        twoSourceDownloads!.complete();
      }
    }
    final response = await super.bytes(
      path,
      mediaType: mediaType,
      maxBytes: maxBytes,
    );
    if (path.endsWith('/source') && corruptSourceDownload) {
      return Uint8List.fromList(response)..[response.length - 1] ^= 1;
    }
    return response;
  }
}

void main() {
  late Directory folder;
  late ControlledDevice device;
  late DeletionServer server;
  late OfflinePlans repo;
  late DateTime now;
  final extraGates = <Completer<void>>[];
  final user = <String, dynamic>{
    'id': 'a' * 32,
    'email': 'rotation@example.test',
    'role': 'owner',
  };
  final projects = [
    {'id': 'project', 'name': 'Synthetic project'},
  ];
  const rotation = 'view_rotation_quarter_turns';

  OfflinePlans createRepository() => OfflinePlans(
    api: server,
    transport: server,
    device: device,
    clock: () => now,
  );

  Future<Map<String, dynamic>> persisted() async {
    final vault = await device.open(repo.server, user['id']);
    return (await vault.read())!;
  }

  Future<Map<String, dynamic>> capture({
    Uint8List? bytes,
    String mediaType = 'image/png',
  }) async {
    final record = await repo.captureImport(
      'project',
      bytes ?? previewPng(),
      filename: mediaType == 'application/pdf'
          ? 'synthetic.pdf'
          : 'synthetic.png',
      mediaType: mediaType,
      title: 'Synthetic original',
    );
    await idle(repo);
    return record;
  }

  Future<Map<String, dynamic>> savePlan() async {
    final record = await repo.save('project', {
      'title': 'Synthetic wall drawing',
      'walls': <dynamic>[],
    });
    await idle(repo);
    return record;
  }

  Future<List<File>> activeAssetFiles() async => folder
      .list(recursive: true, followLinks: false)
      .where(
        (entry) => entry is File && entry.uri.pathSegments.contains('assets'),
      )
      .cast<File>()
      .toList();

  Future<File> sourceFile(Map<String, dynamic> record) async {
    final vault = await device.open(repo.server, user['id']);
    return File.fromUri(
      vault.directory.uri.resolve(
        'assets/${record['source']['id']}/original.enc',
      ),
    );
  }

  Future<void> restart() async {
    await idle(repo);
    await repo.leave();
    repo.dispose();
    repo = createRepository();
    await repo.resume();
    await idle(repo);
  }

  setUp(() async {
    extraGates.clear();
    folder = await Directory.systemTemp.createTemp('smartplan-local-actions-');
    device = ControlledDevice(folder);
    now = DateTime.utc(2026, 10, 24);
    server = DeletionServer()
      ..now = now
      ..grantImportCapability = true
      ..token = 'synthetic-session';
    repo = createRepository();
    await repo.login(user, projects);
    await idle(repo);
    server.online = false;
  });

  tearDown(() async {
    for (final gate in [
      device.releaseWrite,
      server.releaseChunk,
      server.sourceRelease,
      server.releasePlanReply,
      server.releaseManifestReply,
      server.releasePlanList,
      ...extraGates,
    ]) {
      if (gate != null && !gate.isCompleted) gate.complete();
    }
    await idle(repo);
    await repo.flush();
    repo.dispose();
    server.dispose();
    await folder.delete(recursive: true);
  });

  test('Quarter-turn view changes persist offline without changing source bytes or ciphertext', () async {
    final record = await capture();
    final id = record['local_id'] as String;
    final file = await sourceFile(record);
    final encryptedBefore = await file.readAsBytes();
    final originalHash = await checksum(previewPng());
    expect(repo.getImport(id)[rotation], 0);
    final pendingBefore = repo.pending;
    for (final turns in [1, 2, 3, 0]) {
      await repo.setImportRotation(id, turns);
      expect(repo.getImport(id)[rotation], turns);
      expect((await persisted())['imports'][id][rotation], turns);
      expect(await repo.importSource(id), orderedEquals(previewPng()));
      expect(await checksum(await repo.importSource(id)), originalHash);
      expect(repo.getImport(id)['source'], record['source']);
      expect(await file.readAsBytes(), orderedEquals(encryptedBefore));
      expect(repo.pending, pendingBefore);
      await restart();
      expect(repo.getImport(id)[rotation], turns);
    }
    expect(server.manifestCalls, isEmpty);
  });

  test('Concurrent local rotations serialize and the last requested view survives restart', () async {
    final record = await capture();
    final id = record['local_id'] as String;
    await Future.wait([
      repo.setImportRotation(id, 1),
      repo.setImportRotation(id, 2),
      repo.setImportRotation(id, 3),
    ]);
    expect(repo.getImport(id)[rotation], 3);
    await restart();
    expect(repo.getImport(id)[rotation], 3);
    expect(await repo.importSource(id), orderedEquals(previewPng()));
  });

  test(
    'A failed rotation commit preserves the preceding visible and durable view',
    () async {
      final record = await capture();
      final id = record['local_id'] as String;
      await repo.setImportRotation(id, 1);
      device.failNext = true;
      await expectLater(
        repo.setImportRotation(id, 3),
        throwsA(isA<FileSystemException>()),
      );
      expect(repo.getImport(id)[rotation], 1);
      expect((await persisted())['imports'][id][rotation], 1);
      await restart();
      expect(repo.getImport(id)[rotation], 1);
      expect(await repo.importSource(id), orderedEquals(previewPng()));
    },
  );

  test(
    'Out-of-range rotations reject without changing metadata or source',
    () async {
      final record = await capture();
      final id = record['local_id'] as String;
      await repo.setImportRotation(id, 2);
      for (final invalid in [-1, 4, 999]) {
        await expectLater(
          repo.setImportRotation(id, invalid),
          throwsA(
            isA<ApiException>().having((error) => error.status, 'status', 400),
          ),
        );
      }
      expect(repo.getImport(id)[rotation], 2);
      expect((await persisted())['imports'][id][rotation], 2);
      expect(await repo.importSource(id), orderedEquals(previewPng()));
    },
  );

  test('Seven-day expiry prevents view changes and preserves the preceding source and rotation', () async {
    final record = await capture();
    final id = record['local_id'] as String;
    await repo.setImportRotation(id, 1);
    final file = await sourceFile(record);
    final encrypted = await file.readAsBytes();
    now = now.add(const Duration(days: 7));
    await expectLater(
      repo.setImportRotation(id, 2),
      throwsA(
        isA<ApiException>().having((error) => error.status, 'status', 401),
      ),
    );
    expect((await persisted())['imports'][id][rotation], 1);
    expect(await file.readAsBytes(), orderedEquals(encrypted));
  });

  test('A revoked project cannot change source rotation', () async {
    final record = await capture();
    final id = record['local_id'] as String;
    await repo.setImportRotation(id, 1);
    await repo.refreshProjects([]);
    await expectLater(
      repo.setImportRotation(id, 2),
      throwsA(isA<ApiException>()),
    );
    expect((await persisted())['imports'][id][rotation], 1);
    expect(await (await sourceFile(record)).exists(), isTrue);
  });

  test('A read-only project member may rotate the local view without rewriting or uploading its source', () async {
    final record = await capture();
    final id = record['local_id'] as String;
    server.online = true;
    await repo.login({...user, 'role': 'accountant'}, projects);
    await idle(repo);
    server.online = false;
    final pendingBefore = repo.pending;
    await repo.setImportRotation(id, 3);
    expect(repo.getImport(id)[rotation], 3);
    expect(repo.pending, pendingBefore);
    expect(server.manifestCalls, isEmpty);
    await restart();
    expect(repo.getImport(id)[rotation], 3);
    expect(await repo.importSource(id), orderedEquals(previewPng()));
  });

  test('An import stays visible and its bytes stay present until its deletion marker commits', () async {
    final record = await capture();
    final id = record['local_id'] as String;
    final file = await sourceFile(record);
    device.pauseNextWrite();
    final deleting = repo.deleteImport(id);
    await device.writeStarted!.future.timeout(const Duration(seconds: 3));
    expect(await file.exists(), isTrue);
    expect(repo.getImport(id)['source'], record['source']);
    device.releaseWrite!.complete();
    await deleting;
    await idle(repo);
    expect(repo.imports('project'), isEmpty);
    expect(await file.exists(), isFalse);
    final state = await persisted();
    expect(state['import_deletions'][id], isA<Map>());
    expect(state['import_delete_outbox'], [id]);
    expect(state['import_outbox'], isEmpty);
    await restart();
    expect(repo.imports('project'), isEmpty);
    expect(await file.exists(), isFalse);
  });

  test(
    'Failed deletion metadata never hides or removes the preceding original',
    () async {
      final record = await capture();
      final id = record['local_id'] as String;
      final file = await sourceFile(record);
      final encrypted = await file.readAsBytes();
      device.failNext = true;
      await expectLater(
        repo.deleteImport(id),
        throwsA(isA<FileSystemException>()),
      );
      expect(repo.getImport(id)['source'], record['source']);
      expect(await file.readAsBytes(), orderedEquals(encrypted));
      expect(repo.pending, 1);
      await restart();
      expect(repo.imports('project').single['local_id'], id);
      expect(await repo.importSource(id), orderedEquals(previewPng()));
      expect(server.deleteBodies, isEmpty);
    },
  );

  test('Offline deletion cancels unseen plan and import creates without later ghost objects', () async {
    final plan = await savePlan();
    final source = await capture();
    final planId = plan['local_id'] as String;
    final sourceId = source['local_id'] as String;
    final stateBefore = await persisted();
    final planRequest = (stateBefore['outbox'] as List).single['request_id'];
    await repo.deletePlan(planId);
    await repo.deleteImport(sourceId);
    await idle(repo);
    expect(repo.list('project'), isEmpty);
    expect(repo.imports('project'), isEmpty);
    expect(await activeAssetFiles(), isEmpty);
    await restart();
    server.online = true;
    await repo.sync();
    expect(repo.pending, 0);
    expect(server.plans, isEmpty);
    expect(server.records, isEmpty);
    expect(server.manifestCalls, isEmpty);
    expect(server.planRequestBodies, isEmpty);
    expect(server.chunkCalls, isEmpty);
    expect(server.deleteBodies, hasLength(2));
    expect(
      server.deleteBodies.map((body) => body['create_request_id']),
      containsAll([planRequest, source['request_id']]),
    );
  });

  for (final kind in ['plan', 'import']) {
    test(
      'Deletion after a lost $kind create acknowledgment cancels the already accepted object after restart',
      () async {
        final record = kind == 'plan' ? await savePlan() : await capture();
        final id = record['local_id'] as String;
        if (kind == 'plan') {
          server.losePlanCreateAcknowledgment = true;
        } else {
          server.loseManifestAcknowledgment = true;
        }
        server.online = true;
        await repo.sync();
        expect(kind == 'plan' ? server.plans : server.records, hasLength(1));
        server.online = false;
        if (kind == 'plan') {
          await repo.deletePlan(id);
        } else {
          await repo.deleteImport(id);
        }
        await idle(repo);
        await restart();
        server.online = true;
        await repo.sync();
        expect(repo.pending, 0);
        expect(server.plans, isEmpty);
        expect(server.records, isEmpty);
        expect(server.deleteBodies.single['create_request_id'], isNotNull);
        expect(server.deletionEvents.single['id'], isNotNull);
        expect(repo.canAccessProject('project'), isTrue);
        expect(repo.list('project'), isEmpty);
        expect(repo.imports('project'), isEmpty);
        expect(await activeAssetFiles(), isEmpty);
      },
    );
  }

  test('A lost deletion response retries the identical request after offline restart', () async {
    final record = await capture();
    final id = record['local_id'] as String;
    server.online = true;
    await repo.sync();
    expect(repo.pending, 0);
    server.online = false;
    await repo.deleteImport(id);
    await idle(repo);
    server.online = true;
    server.loseDeleteAcknowledgment = true;
    await repo.sync();
    expect(server.records, isEmpty);
    expect(repo.pending, 1);
    expect(server.deleteBodies, hasLength(1));
    server.online = false;
    await restart();
    expect(repo.imports('project'), isEmpty);
    server.online = true;
    await repo.sync();
    expect(repo.pending, 0);
    expect(server.deleteBodies, hasLength(2));
    expect(server.deleteBodies[1], server.deleteBodies[0]);
    expect(server.deletionEvents, hasLength(1));
    expect(await activeAssetFiles(), isEmpty);
  });

  test('Deleting an in-flight upload prevents completion and survives its late accepted chunk response', () async {
    final record = await capture(
      bytes: syntheticPdf(),
      mediaType: 'application/pdf',
    );
    final id = record['local_id'] as String;
    server.chunkAccepted = Completer<void>();
    server.releaseChunk = Completer<void>();
    server.online = true;
    final uploading = repo.sync();
    await server.chunkAccepted!.future.timeout(const Duration(seconds: 3));
    await repo.deleteImport(id);
    expect(repo.imports('project'), isEmpty);
    expect(await activeAssetFiles(), isEmpty);
    server.releaseChunk!.complete();
    await uploading;
    await repo.sync();
    expect(repo.pending, 0);
    expect(server.completions, 0);
    expect(server.records, isEmpty);
    expect(repo.imports('project'), isEmpty);
    expect(repo.canAccessProject('project'), isTrue);
    await restart();
    expect(repo.imports('project'), isEmpty);
  });

  test('Deleting during a source download prevents late bytes from repopulating the cache', () async {
    server.online = true;
    await server.seed(syntheticPdf());
    server.sourceStarted = Completer<void>();
    server.sourceRelease = Completer<void>();
    Object? refreshError;
    final refreshing = repo
        .refreshImports('project')
        .then<void>(
          (_) {},
          onError: (Object error, StackTrace _) {
            refreshError = error;
          },
        );
    await server.sourceStarted!.future.timeout(const Duration(seconds: 3));
    final id = repo.imports('project').single['local_id'] as String;
    await repo.deleteImport(id);
    await idle(repo);
    server.sourceRelease!.complete();
    await refreshing;
    await repo.sync();
    if (refreshError != null) {
      expect(
        refreshError,
        isA<ApiException>().having((error) => error.status, 'status', 410),
      );
    }
    expect(repo.imports('project'), isEmpty);
    expect(repo.canAccessProject('project'), isTrue);
    expect(await activeAssetFiles(), isEmpty);
    expect(server.records, isEmpty);
  });

  test('An item 410 hides the deleted import without revoking the project even before its feed arrives', () async {
    final record = await capture();
    final id = record['local_id'] as String;
    server.online = true;
    await repo.sync();
    final remoteId = repo.getImport(id)['server_id'];
    await server.call('/api/projects/project/plan-imports/delete', {
      'request_id': offlineId(),
      'id': remoteId,
    });
    server.hideDeletionFeed = true;
    await repo.sync();
    expect(repo.canAccessProject('project'), isTrue);
    expect(repo.imports('project'), isEmpty);
    expect(await activeAssetFiles(), isEmpty);
    expect(repo.pending, 0);
  });

  for (final kind in ['plan', 'import']) {
    test(
      'A late accepted $kind creation reply cannot revive a locally deleted entry',
      () async {
        final record = kind == 'plan' ? await savePlan() : await capture();
        final id = record['local_id'] as String;
        final accepted = Completer<void>(), release = Completer<void>();
        if (kind == 'plan') {
          server.planAccepted = accepted;
          server.releasePlanReply = release;
        } else {
          server.manifestAccepted = accepted;
          server.releaseManifestReply = release;
        }
        server.online = true;
        final sending = repo.sync();
        await accepted.future.timeout(const Duration(seconds: 3));
        if (kind == 'plan') {
          await repo.deletePlan(id);
        } else {
          await repo.deleteImport(id);
        }
        expect(repo.list('project'), isEmpty);
        expect(repo.imports('project'), isEmpty);
        release.complete();
        await sending;
        expect(server.plans, isEmpty);
        expect(server.records, isEmpty);
        expect(server.completions, 0);
        expect(server.chunkCalls, isEmpty);
        expect(repo.pending, 0);
        expect(await activeAssetFiles(), isEmpty);
        await restart();
        expect(repo.list('project'), isEmpty);
        expect(repo.imports('project'), isEmpty);
      },
    );
  }

  test(
    'A late manual save reply cannot restore a deleted synchronized plan',
    () async {
      final record = await savePlan();
      final id = record['local_id'] as String;
      server.online = true;
      await repo.sync();
      server.online = false;
      await repo.save('project', {
        'title': 'Changed while offline',
        'walls': [],
      }, localId: id);
      await idle(repo);
      server.planAccepted = Completer<void>();
      server.releasePlanReply = Completer<void>();
      server.online = true;
      final saving = repo.sync();
      await server.planAccepted!.future.timeout(const Duration(seconds: 3));
      await repo.deletePlan(id);
      server.releasePlanReply!.complete();
      await saving;
      expect(repo.list('project'), isEmpty);
      expect(server.plans, isEmpty);
      expect(repo.pending, 0);
      expect(repo.canAccessProject('project'), isTrue);
    },
  );

  test('A list captured before deletion cannot reinsert a lost-ack plan under its server ID', () async {
    final record = await savePlan();
    server.online = true;
    server.losePlanCreateAcknowledgment = true;
    await repo.sync();
    expect(server.plans, hasLength(1));
    expect(repo.get(record['local_id'])['server_id'], isNull);
    server.planListStarted = Completer<void>();
    server.releasePlanList = Completer<void>();
    final refreshing = repo.refresh('project');
    await server.planListStarted!.future.timeout(const Duration(seconds: 3));
    server.online = false;
    await repo.deletePlan(record['local_id']);
    await idle(repo);
    server.releasePlanList!.complete();
    await refreshing;
    expect(repo.list('project'), isEmpty);
    server.online = true;
    await repo.sync();
    await repo.refresh('project');
    expect(server.plans, isEmpty);
    expect(repo.list('project'), isEmpty);
    expect(repo.pending, 0);
  });

  test('An item 410 while loading a save conflict creates a tombstone without revoking the project', () async {
    final record = await savePlan();
    server.online = true;
    await repo.sync();
    server.online = false;
    await repo.save('project', {
      'title': 'Local change',
      'walls': [],
    }, localId: record['local_id']);
    await idle(repo);
    server.online = true;
    server.deletePlanDuringConflict = true;
    await repo.sync();
    expect(repo.canAccessProject('project'), isTrue);
    expect(repo.list('project'), isEmpty);
    expect(repo.pending, 0);
    expect(
      (await persisted())['plan_deletions'][record['local_id']],
      isA<Map>(),
    );
  });

  test('A metadata write finishing after leave cannot publish the preceding account again', () async {
    final record = await capture();
    device.pauseNextWrite();
    final seenAccounts = <String?>[];
    repo.addListener(
      () => seenAccounts.add(repo.active ? repo.user['id'] as String : null),
    );
    final rotating = repo.setImportRotation(record['local_id'], 3);
    final rejected = expectLater(rotating, throwsStateError);
    await device.writeStarted!.future.timeout(const Duration(seconds: 3));
    final leaving = repo.leave();
    device.releaseWrite!.complete();
    await rejected;
    await leaving;
    expect(seenAccounts, isNot(contains(user['id'])));
    server.online = true;
    final other = {...user, 'id': 'b' * 32};
    await repo.login(other, projects);
    await idle(repo);
    expect(repo.user['id'], other['id']);
    expect(repo.imports('project'), isEmpty);
    final previous = await device.open(repo.server, user['id']);
    expect(
      (await previous.read())!['imports'][record['local_id']][rotation],
      3,
    );
  });

  test(
    'Concurrent source refreshes retain only the one published encrypted asset',
    () async {
      server.online = true;
      await server.seed(syntheticPdf());
      server.sourceStarted = Completer<void>();
      server.sourceRelease = Completer<void>();
      server.twoSourceDownloads = Completer<void>();
      final first = repo.refreshImports('project');
      await server.sourceStarted!.future.timeout(const Duration(seconds: 3));
      final second = repo.refreshImports('project');
      await server.twoSourceDownloads!.future.timeout(
        const Duration(seconds: 3),
      );
      server.sourceRelease!.complete();
      await Future.wait([first, second]);
      expect(await activeAssetFiles(), hasLength(1));
      expect(
        await repo.importSource(repo.imports('project').single['local_id']),
        orderedEquals(syntheticPdf()),
      );
    },
  );

  test('An asset whose metadata commit fails is removed only after proving it was not published', () async {
    server.online = true;
    await server.seed(syntheticPdf());
    server.sourceStarted = Completer<void>();
    server.sourceRelease = Completer<void>();
    final refreshing = repo.refreshImports('project');
    final failed = expectLater(refreshing, throwsA(isA<FileSystemException>()));
    await server.sourceStarted!.future.timeout(const Duration(seconds: 3));
    device.failNext = true;
    server.sourceRelease!.complete();
    await failed;
    expect(await activeAssetFiles(), isEmpty);
    expect(repo.imports('project').single['source'], isNull);
    await repo.refreshImports('project');
    expect(await activeAssetFiles(), hasLength(1));
    expect(
      await repo.importSource(repo.imports('project').single['local_id']),
      orderedEquals(syntheticPdf()),
    );
  });

  test(
    'Rejected source hashes do not accumulate unreferenced encrypted originals',
    () async {
      server.online = true;
      await server.seed(syntheticPdf());
      server.corruptSourceDownload = true;
      await repo.refreshImports('project');
      await repo.refreshImports('project');
      expect(await activeAssetFiles(), isEmpty);
      expect(repo.imports('project').single['source'], isNull);
      expect(server.sources.values.single, orderedEquals(syntheticPdf()));
    },
  );

  test(
    'A stale import list followed by source 410 tombstones only that item',
    () async {
      server.online = true;
      final remoteId = await server.seed(syntheticPdf());
      server.hideDeletionFeed = true;
      server.deletedImports.add(remoteId);
      await repo.refreshImports('project');
      expect(repo.imports('project'), isEmpty);
      expect(repo.canAccessProject('project'), isTrue);
      expect(await activeAssetFiles(), isEmpty);
      expect((await persisted())['import_deletions'][remoteId], isA<Map>());
    },
  );

  test('Offline resume retries a persisted cleanup intent even without a stored server token', () async {
    final record = await capture();
    final source = await sourceFile(record);
    final directory = source.parent;
    final extra = File.fromUri(directory.uri.resolve('unrelated.keep'));
    await extra.writeAsString('Synthetic unrelated bytes.');
    await repo.deleteImport(record['local_id']);
    await idle(repo);
    expect(await extra.readAsString(), 'Synthetic unrelated bytes.');
    expect(
      (await persisted())['import_deletions'][record['local_id']]['assets'],
      hasLength(1),
    );
    await extra.delete();
    await device.saveSession(repo.server, user['id'], null);
    await restart();
    expect(repo.imports('project'), isEmpty);
    expect(repo.pending, 1);
    expect(await directory.exists(), isFalse);
    expect(
      (await persisted())['import_deletions'][record['local_id']]['assets'],
      isEmpty,
    );
    expect(server.manifestCalls, isEmpty);
  });

  test('A cache write finishing after an account switch removes only its own unpublished file', () async {
    server.online = true;
    await server.seed(syntheticPdf());
    final started = Completer<void>(), release = Completer<void>();
    extraGates.add(release);
    final refreshing = IOOverrides.runZoned(
      () => repo.refreshImports('project'),
      createFile: (path) {
        final file = nativeFile(path);
        final parts = path.split(RegExp(r'[/\\]'));
        return parts.last == 'original.enc' &&
                parts.any((part) => part.startsWith('.pending-'))
            ? InterruptedFile(file, started: started, release: release)
            : file;
      },
    );
    final rejected = expectLater(refreshing, throwsStateError);
    await started.future.timeout(const Duration(seconds: 3));
    await repo.leave();
    final other = {...user, 'id': 'b' * 32};
    await repo.login(other, projects);
    await idle(repo);
    server.online = false;
    final otherSource = await capture();
    release.complete();
    await rejected;
    expect(repo.user['id'], other['id']);
    expect(
      await repo.importSource(otherSource['local_id']),
      orderedEquals(previewPng()),
    );
    expect(await activeAssetFiles(), hasLength(1));
  });

  for (final restriction in ['read_only', 'expired', 'project_revoked']) {
    test(
      'Plan and import deletion respect $restriction without destroying inputs',
      () async {
        final plan = await savePlan();
        final source = await capture();
        if (restriction == 'read_only') {
          server.online = true;
          await repo.login({...user, 'role': 'accountant'}, projects);
          await idle(repo);
          server.online = false;
        } else if (restriction == 'expired') {
          now = now.add(const Duration(days: 7));
        } else {
          await repo.refreshProjects([]);
        }
        final status = restriction == 'expired' ? 401 : 403;
        for (final deleting in [
          () => repo.deletePlan(plan['local_id']),
          () => repo.deleteImport(source['local_id']),
        ]) {
          await expectLater(
            deleting(),
            throwsA(
              isA<ApiException>().having(
                (error) => error.status,
                'status',
                status,
              ),
            ),
          );
        }
        final state = await persisted();
        expect(state['records'][plan['local_id']], isNotNull);
        expect(
          state['imports'][source['local_id']]['source'],
          source['source'],
        );
        expect(await (await sourceFile(source)).exists(), isTrue);
        expect(server.deleteBodies, isEmpty);
      },
    );
  }
}

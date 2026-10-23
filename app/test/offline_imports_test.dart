import 'dart:async';
import 'dart:convert';
import 'dart:io';
import 'dart:typed_data';

import 'package:cryptography/cryptography.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:smartplan_office/api.dart';
import 'package:smartplan_office/offline_assets.dart';
import 'package:smartplan_office/offline_plans.dart';
import 'package:smartplan_office/offline_vault.dart';

import 'offline_plans_test.dart' show TestDevice, PlanServer, idle;

const chunkSize = 262144;
const privateOriginal = 'SYNTHETIC_PRIVATE_ORIGINAL_5537';
const privateRecognition = 'SYNTHETIC_PRIVATE_RECOGNITION_7751';

Uint8List syntheticPdf([int size = 620000]) {
  final bytes = Uint8List(size);
  final header = utf8.encode('%PDF-1.7\n$privateOriginal\n');
  bytes.setRange(0, header.length, header);
  for (var index = header.length; index < bytes.length; index++) {
    bytes[index] = 32 + (index % 80);
  }
  return bytes;
}

Uint8List previewPng() => base64Decode(
  'iVBORw0KGgoAAAANSUhEUgAAAAMAAAACCAIAAAASFvFNAAAAHElEQVR4nGP8//8/'
  'AwMDAwMDEwMDwxFRFQYGBgA7lwP+rv264gAAAABJRU5ErkJggg==',
);

Future<String> checksum(Uint8List bytes) async =>
    (await Sha256().hash(bytes)).bytes
        .map((byte) => byte.toRadixString(16).padLeft(2, '0'))
        .join();

/// Stateful wire contract: accepts chunks before simulating a lost response,
/// derives resume indexes from persisted chunks, and verifies completion bytes.
class ImportServer extends PlanServer {
  bool supported = true;
  bool loseChunkAcknowledgment = false;
  bool loseManifestAcknowledgment = false;
  bool mutateManifestHash = false;
  bool grantImportCapability = false;
  int deniedStatus = 403;
  DateTime now = DateTime.utc(2026, 10, 23);
  final records = <String, Map<String, dynamic>>{};
  final importRequests = <String, String>{};
  final requestBodies = <String, String>{};
  final manifestCalls = <Map<String, dynamic>>[];
  final chunks = <String, Map<int, Uint8List>>{};
  final sources = <String, Uint8List>{};
  final previews = <String, Uint8List>{};
  final results = <String, Uint8List>{};
  final chunkCalls = <int>[];
  final downloadCalls = <String>[];
  int nextImport = 0;
  int completions = 0;
  Completer<void>? sourceStarted;
  Completer<void>? sourceRelease;
  Completer<void>? planRefreshStarted;
  Completer<void>? planRefreshRelease;
  int delayedPlanStatus = 403;

  void guard() {
    if (!online) throw const ApiException(0, 'Offline');
    if (forbidden) throw ApiException(deniedStatus, 'Project access revoked');
    if (!supported) throw const ApiException(404, 'Import route unavailable');
  }

  Map<String, dynamic> manifest(Map<String, dynamic> record) {
    final copy = offlineCopy(record);
    if (mutateManifestHash) copy['sha256'] = 'f' * 64;
    return copy;
  }

  @override
  Future<dynamic> call(String path, [Map<String, dynamic>? body]) async {
    if (path == '/api/projects/project/plans' &&
        body == null &&
        planRefreshStarted != null) {
      if (!planRefreshStarted!.isCompleted) planRefreshStarted!.complete();
      await planRefreshRelease!.future;
      throw ApiException(delayedPlanStatus, 'Delayed old-account response');
    }
    if (path == '/api/offline/access') {
      if (!online) throw const ApiException(0, 'Offline');
      return {
        'token': 'offline-test',
        'expires_at': now.add(const Duration(days: 7)).toIso8601String(),
        if (grantImportCapability)
          'capabilities': [
            'project_plans',
            'offline_plan_access',
            'plan_imports',
          ],
      };
    }
    if (!path.contains('/plan-imports')) return super.call(path, body);
    guard();
    final match = RegExp(
      r'^/api/projects/([^/]+)/plan-imports(?:/([a-f0-9]{32})(?:/(complete))?)?$',
    ).firstMatch(path);
    if (match == null) throw StateError('Unexpected import route: $path');
    final project = match[1]!;
    final id = match[2];
    if (id == null) {
      if (body == null) {
        return [
          for (final record in records.values)
            if (record['project_id'] == project) manifest(record),
        ];
      }
      final requestId = body['request_id'] as String;
      final serialized = jsonEncode(body);
      manifestCalls.add(offlineCopy(body));
      if (importRequests.containsKey(requestId)) {
        if (requestBodies[requestId] != serialized) {
          throw const ApiException(409, 'Request content changed');
        }
        return manifest(records[importRequests[requestId]]!);
      }
      final createdId = (++nextImport).toRadixString(16).padLeft(32, '0');
      final record = <String, dynamic>{
        ...offlineCopy(body),
        'id': createdId,
        'project_id': project,
        'status': 'uploading',
        'chunk_size': chunkSize,
        'uploaded_chunks': <int>[],
      };
      records[createdId] = record;
      chunks[createdId] = {};
      importRequests[requestId] = createdId;
      requestBodies[requestId] = serialized;
      if (loseManifestAcknowledgment) {
        loseManifestAcknowledgment = false;
        throw const ApiException(0, 'Manifest accepted, response lost');
      }
      return manifest(record);
    }
    final record = records[id];
    if (record == null || record['project_id'] != project) {
      throw const ApiException(404, 'Source not available in this project');
    }
    if (match[3] == 'complete') {
      final count = ((record['size'] as int) + chunkSize - 1) ~/ chunkSize;
      final builder = BytesBuilder(copy: false);
      for (var index = 0; index < count; index++) {
        final chunk = chunks[id]?[index];
        if (chunk == null) throw const ApiException(409, 'Missing chunk');
        builder.add(chunk);
      }
      final bytes = builder.takeBytes();
      if (bytes.length != record['size'] ||
          await checksum(bytes) != record['sha256']) {
        throw const ApiException(409, 'Source checksum mismatch');
      }
      sources[id] = bytes;
      record['status'] = 'queued';
      completions++;
    }
    return manifest(record);
  }

  @override
  Future<dynamic> putChunk(String path, Uint8List bytes) async {
    guard();
    final match = RegExp(
      r'^/api/projects/([^/]+)/plan-imports/([a-f0-9]{32})/chunks/(\d+)$',
    ).firstMatch(path);
    if (match == null) throw StateError('Unexpected chunk route: $path');
    final id = match[2]!;
    final index = int.parse(match[3]!);
    final record = records[id];
    if (record == null || record['project_id'] != match[1]) {
      throw const ApiException(404, 'Source not available in this project');
    }
    final remaining = (record['size'] as int) - index * chunkSize;
    final expected = remaining.clamp(0, chunkSize);
    if (expected == 0 || bytes.length != expected) {
      throw const ApiException(400, 'Invalid chunk length');
    }
    final previous = chunks[id]![index];
    if (previous != null && base64Encode(previous) != base64Encode(bytes)) {
      throw const ApiException(409, 'Chunk content changed');
    }
    chunkCalls.add(index);
    chunks[id]![index] = Uint8List.fromList(bytes);
    record['uploaded_chunks'] = chunks[id]!.keys.toList()..sort();
    if (loseChunkAcknowledgment && index == 0) {
      loseChunkAcknowledgment = false;
      throw const ApiException(0, 'Chunk accepted, response lost');
    }
    return {'ok': true};
  }

  @override
  Future<Uint8List> bytes(
    String path, {
    required String mediaType,
    int maxBytes = 20 * 1024 * 1024,
  }) async {
    guard();
    final match = RegExp(
      r'^/api/projects/([^/]+)/plan-imports/([a-f0-9]{32})/(source|preview|result)$',
    ).firstMatch(path);
    if (match == null) throw StateError('Unexpected download route: $path');
    final id = match[2]!;
    final kind = match[3]!;
    final record = records[id];
    if (record == null || record['project_id'] != match[1]) {
      throw const ApiException(404, 'Source not available in this project');
    }
    final content = switch (kind) {
      'source' => sources[id],
      'preview' => previews[id],
      _ => results[id],
    };
    if (content == null) throw const ApiException(404, 'File unavailable');
    final expectedType = kind == 'source'
        ? record['media_type']
        : kind == 'preview'
        ? 'image/png'
        : 'application/json';
    if (mediaType != expectedType || content.length > maxBytes) {
      throw const ApiException(0, 'Invalid type or response limit');
    }
    downloadCalls.add(kind);
    if (kind == 'source' && sourceStarted != null) {
      if (!sourceStarted!.isCompleted) sourceStarted!.complete();
      await sourceRelease!.future;
    }
    return Uint8List.fromList(content);
  }

  Future<String> seed(
    Uint8List source, {
    String project = 'project',
    int page = 0,
  }) async {
    final id = (++nextImport).toRadixString(16).padLeft(32, '0');
    records[id] = {
      'id': id,
      'project_id': project,
      'title': 'Synthetic server source',
      'filename': 'synthetic-server.pdf',
      'media_type': 'application/pdf',
      'size': source.length,
      'sha256': await checksum(source),
      'page': page,
      'status': 'queued',
      'chunk_size': chunkSize,
      'uploaded_chunks': <int>[],
    };
    sources[id] = Uint8List.fromList(source);
    return id;
  }

  Future<void> finishRecognition(
    String id, {
    int? selectedPage,
    String? sourceHash,
  }) async {
    final record = records[id]!;
    final preview = previewPng();
    final result = <String, dynamic>{
      'schema_version': 1,
      'status': 'needs_review',
      'source': {
        'sha256': sourceHash ?? record['sha256'],
        'size': record['size'],
        'selected_page': selectedPage ?? record['page'],
      },
      'preview': {'width': 3, 'height': 2},
      'analysis': {
        'status': 'needs_review',
        'line_candidates': [
          {
            'start': [0, 0],
            'end': [1, 1],
          },
        ],
        'text_candidates': [
          {
            'text': privateRecognition,
            'bbox': [0, 0, 1, 1],
          },
        ],
      },
      'calibration': {'status': 'unknown', 'units': 'unitless'},
    };
    final encoded = Uint8List.fromList(utf8.encode(jsonEncode(result)));
    previews[id] = preview;
    results[id] = encoded;
    record.addAll({
      'status': 'needs_review',
      'preview_sha256': await checksum(preview),
      'preview_size': preview.length,
      'result_sha256': await checksum(encoded),
    });
  }
}

void main() {
  late Directory folder;
  late TestDevice device;
  late ImportServer server;
  late OfflinePlans repo;
  late DateTime now;
  final user = <String, dynamic>{
    'id': 'a' * 32,
    'email': 'synthetic-import@example.test',
    'role': 'owner',
  };
  final projects = [
    {'id': 'project', 'name': 'Synthetic project'},
  ];

  OfflinePlans createRepository() => OfflinePlans(
    api: server,
    transport: server,
    device: device,
    clock: () => now,
  );

  Future<Map<String, dynamic>> persisted([String? account]) async {
    final vault = await device.open(repo.server, account ?? user['id']);
    return (await vault.read())!;
  }

  Future<List<File>> encryptedFiles() async => folder
      .list(recursive: true, followLinks: false)
      .where((file) => file is File && file.path.endsWith('.enc'))
      .cast<File>()
      .toList();

  Future<Map<String, dynamic>> capture([Uint8List? bytes]) async {
    final record = await repo.captureImport(
      'project',
      bytes ?? syntheticPdf(),
      filename: 'synthetic-private.pdf',
      mediaType: 'application/pdf',
      title: 'Synthetic private plan',
    );
    await idle(repo);
    return record;
  }

  Future<void> restartOffline() async {
    await idle(repo);
    await repo.leave();
    repo.dispose();
    repo = createRepository();
    await repo.resume();
    await idle(repo);
  }

  setUp(() async {
    folder = await Directory.systemTemp.createTemp('smartplan-import-offline-');
    device = TestDevice(folder);
    server = ImportServer()..token = 'full-session';
    now = DateTime.utc(2026, 10, 23);
    repo = createRepository();
    await repo.login(user, projects);
    await idle(repo);
  });

  tearDown(() async {
    if (server.sourceRelease != null && !server.sourceRelease!.isCompleted) {
      server.sourceRelease!.complete();
    }
    if (server.planRefreshRelease != null &&
        !server.planRefreshRelease!.isCompleted) {
      server.planRefreshRelease!.complete();
    }
    await idle(repo);
    repo.dispose();
    server.dispose();
    await folder.delete(recursive: true);
  });

  test('Offline originals are encrypted references and survive restart before upload', () async {
    server.online = false;
    final bytes = syntheticPdf();
    final record = await capture(bytes);
    final id = record['local_id'] as String;
    final request = record['request_id'];
    expect(repo.pending, 1);
    expect(await repo.importSource(id), orderedEquals(bytes));
    final state = await persisted();
    expect(state['import_outbox'], [id]);
    final source = state['imports'][id]['source'] as Map;
    expect(source.keys.toSet(), {
      'id',
      'sha256',
      'size',
      'media_type',
      'filename',
    });
    final serialized = jsonEncode(state);
    expect(serialized.length, lessThan(20000));
    expect(serialized, isNot(contains(privateOriginal)));
    expect(serialized, isNot(contains(base64Encode(bytes))));
    for (final file in await encryptedFiles()) {
      expect(
        latin1.decode(await file.readAsBytes()),
        isNot(contains(privateOriginal)),
      );
    }
    await restartOffline();
    expect(repo.imports('project').single['local_id'], id);
    expect(repo.getImport(id)['request_id'], request);
    expect(await repo.importSource(id), orderedEquals(bytes));
    server.online = true;
    await repo.sync();
    expect(repo.pending, 0);
    expect(server.records, hasLength(1));
    expect(server.manifestCalls.single['request_id'], request);
    expect(repo.getImport(id)['local_id'], id);
    expect(repo.getImport(id)['status'], 'queued');
    expect(server.sources.values.single, orderedEquals(bytes));
  });

  test('A lost chunk response resumes from server indexes without resending index zero', () async {
    server.online = false;
    final bytes = syntheticPdf();
    final record = await capture(bytes);
    server.online = true;
    server.loseChunkAcknowledgment = true;
    await repo.sync();
    expect(server.chunkCalls, [0]);
    expect(repo.pending, 1);
    expect(server.completions, 0);
    await repo.sync();
    expect(server.chunkCalls, [0, 1, 2]);
    expect(server.manifestCalls, hasLength(2));
    expect(server.manifestCalls[0], server.manifestCalls[1]);
    expect(server.records, hasLength(1));
    expect(server.completions, 1);
    expect(repo.pending, 0);
    expect(await repo.importSource(record['local_id']), orderedEquals(bytes));
    expect(server.sources.values.single, orderedEquals(bytes));
  });

  test(
    'A lost manifest response and client restart reuse the accepted import',
    () async {
      server.online = false;
      final record = await capture();
      server.online = true;
      server.loseManifestAcknowledgment = true;
      await repo.sync();
      expect(server.records, hasLength(1));
      expect(server.chunkCalls, isEmpty);
      expect(repo.pending, 1);
      server.online = false;
      await restartOffline();
      server.online = true;
      await repo.sync();
      expect(server.records, hasLength(1));
      expect(server.manifestCalls, hasLength(2));
      expect(server.manifestCalls[0], server.manifestCalls[1]);
      expect(repo.getImport(record['local_id'])['status'], 'queued');
      expect(repo.pending, 0);
    },
  );

  test(
    'Seven-day expiry retains source and queue until online authentication',
    () async {
      server.online = false;
      final record = await capture();
      final id = record['local_id'] as String;
      final reference = Map<String, dynamic>.from(record['source']);
      now = now.add(const Duration(days: 7));
      expect(repo.permitted, isFalse);
      expect(
        () => repo.getImport(id),
        throwsA(isA<ApiException>().having((e) => e.status, 'status', 401)),
      );
      await repo.sync();
      expect(server.manifestCalls, isEmpty);
      final state = await persisted();
      expect(state['import_outbox'], [id]);
      final vault = await device.open(repo.server, user['id']);
      expect(
        await EncryptedAssets(vault).read(reference),
        orderedEquals(syntheticPdf()),
      );
      server.now = now;
      server.online = true;
      await repo.login(user, projects);
      await idle(repo);
      expect(repo.permitted, isTrue);
      expect(repo.pending, 0);
      expect(repo.getImport(id)['request_id'], record['request_id']);
      expect(await repo.importSource(id), orderedEquals(syntheticPdf()));
    },
  );

  test(
    'An older server preserves import queue and project access until upgrade',
    () async {
      server.supported = false;
      final record = await capture();
      final id = record['local_id'] as String;
      expect(repo.pending, 1);
      expect(repo.canAccessProject('project'), isTrue);
      expect(repo.getImport(id)['sync_status'], 'Server-Update erforderlich');
      expect(await repo.importSource(id), orderedEquals(syntheticPdf()));
      server.supported = true;
      await repo.sync();
      expect(repo.pending, 0);
      expect(repo.getImport(id)['status'], 'queued');
      expect(repo.canAccessProject('project'), isTrue);
    },
  );

  for (final supportSource in ['accepted_manifest', 'grant_capability']) {
    test(
      'A known import server 404 revokes access after $supportSource and preserves resumable uploads',
      () async {
        if (supportSource == 'grant_capability') {
          server.grantImportCapability = true;
          await repo.login(user, projects);
          await idle(repo);
        }
        server.online = false;
        final record = await capture();
        final id = record['local_id'] as String;
        if (supportSource == 'accepted_manifest') {
          server.online = true;
          server.loseChunkAcknowledgment = true;
          await repo.sync();
          expect(server.chunkCalls, [0]);
          expect(repo.getImport(id)['status'], 'uploading');
        }
        expect((await persisted())['imports_supported'], isTrue);
        expect(repo.pending, 1);
        server.online = true;
        server.forbidden = true;
        server.deniedStatus = 404;
        if (supportSource == 'accepted_manifest') {
          await repo.refreshImports('project');
        } else {
          await repo.sync();
        }
        expect(repo.canAccessProject('project'), isFalse);
        expect(
          () => repo.getImport(id),
          throwsA(
            isA<ApiException>().having((error) => error.status, 'status', 404),
          ),
        );
        await expectLater(
          repo.importSource(id),
          throwsA(
            isA<ApiException>().having((error) => error.status, 'status', 404),
          ),
        );
        final state = await persisted();
        expect(state['import_outbox'], [id]);
        expect(state['imports'][id]['source'], record['source']);
        expect(repo.pending, 1);
        final vault = await device.open(repo.server, user['id']);
        expect(
          await EncryptedAssets(vault)
              .read(Map<String, dynamic>.from(record['source'])),
          orderedEquals(syntheticPdf()),
        );
        server.forbidden = false;
        await repo.login(user, projects);
        await idle(repo);
        expect(repo.canAccessProject('project'), isTrue);
        expect(repo.pending, 0);
        expect(repo.getImport(id)['source'], record['source']);
        expect(repo.getImport(id)['status'], 'queued');
        expect(server.records, hasLength(1));
        expect(server.chunkCalls, [0, 1, 2]);
        expect(server.sources.values.single, orderedEquals(syntheticPdf()));
      },
    );
  }

  test(
    'Revoked project access hides sources without deleting encrypted inputs',
    () async {
      server.online = false;
      final record = await capture();
      final id = record['local_id'] as String;
      final filesBefore = (await encryptedFiles())
          .map((file) => file.path)
          .toSet();
      server.online = true;
      server.forbidden = true;
      await repo.sync();
      expect(repo.canAccessProject('project'), isFalse);
      expect(
        () => repo.imports('project'),
        throwsA(isA<ApiException>().having((e) => e.status, 'status', 403)),
      );
      expect(
        () => repo.getImport(id),
        throwsA(isA<ApiException>().having((e) => e.status, 'status', 404)),
      );
      await expectLater(
        repo.importSource(id),
        throwsA(isA<ApiException>().having((e) => e.status, 'status', 404)),
      );
      final state = await persisted();
      expect(state['imports'][id]['source'], record['source']);
      expect(state['import_outbox'], [id]);
      expect(
        (await encryptedFiles()).map((file) => file.path).toSet(),
        containsAll(filesBefore.where((path) => path.contains('/assets/'))),
      );
      final vault = await device.open(repo.server, user['id']);
      expect(
        await EncryptedAssets(vault)
            .read(Map<String, dynamic>.from(record['source'])),
        orderedEquals(syntheticPdf()),
      );
      server.forbidden = false;
      await repo.login(user, projects);
      await idle(repo);
      expect(repo.canAccessProject('project'), isTrue);
      expect(repo.pending, 0);
      expect(repo.getImport(id)['status'], 'queued');
      expect(repo.getImport(id)['source'], record['source']);
      expect(await repo.importSource(id), orderedEquals(syntheticPdf()));
    },
  );

  for (final status in [401, 403]) {
    test(
      'A delayed refresh $status from account A cannot lock or revoke account B',
      () async {
        server.delayedPlanStatus = status;
        server.planRefreshStarted = Completer<void>();
        server.planRefreshRelease = Completer<void>();
        final refresh = repo.refresh('project');
        await server.planRefreshStarted!.future.timeout(
          const Duration(seconds: 3),
        );
        final other = <String, dynamic>{
          ...user,
          'id': 'b' * 32,
          'email': 'other@example.test',
        };
        await repo.login(other, projects);
        await idle(repo);
        server.planRefreshRelease!.complete();
        await refresh;
        await repo.flush();
        expect(repo.user['id'], other['id']);
        expect(repo.permitted, isTrue);
        expect(repo.canAccessProject('project'), isTrue);
        expect(repo.projects.single['id'], 'project');
        final state = await persisted(other['id']);
        expect(state['locked'], isFalse);
        expect((state['projects'] as List).single['id'], 'project');
      },
    );
  }

  test('Account switch during a source download never returns or caches old bytes for the new account', () async {
    final remoteId = await server.seed(syntheticPdf());
    server.sourceStarted = Completer<void>();
    server.sourceRelease = Completer<void>();
    final refresh = repo.refreshImports('project');
    final rejected = expectLater(refresh, throwsStateError);
    await server.sourceStarted!.future.timeout(const Duration(seconds: 3));
    final other = <String, dynamic>{
      ...user,
      'id': 'b' * 32,
      'email': 'other@example.test',
    };
    await repo.login(other, [
      {'id': 'other-project', 'name': 'Other account project'},
    ]);
    server.sourceRelease!.complete();
    await rejected;
    await idle(repo);
    expect(repo.user['id'], other['id']);
    expect(repo.imports('other-project'), isEmpty);
    final state = await persisted(other['id']);
    expect(state['imports'] ?? {}, isEmpty);
    final otherVault = await device.open(repo.server, other['id']);
    expect(
      await Directory('${otherVault.directory.path}/assets').exists(),
      isFalse,
    );
    final firstState = await persisted(user['id']);
    expect(firstState['imports'][remoteId]['source'], isNull);
  });

  test('Needs-review previews and recognition are separately encrypted and readable after restart', () async {
    final remoteId = await server.seed(syntheticPdf());
    await server.finishRecognition(remoteId);
    await repo.refreshImports('project');
    final record = repo.imports('project').single;
    final id = record['local_id'] as String;
    expect(record['status'], 'needs_review');
    expect(await repo.importPreview(id), orderedEquals(previewPng()));
    final recognition = await repo.importRecognition(id);
    expect(
      recognition['analysis']['text_candidates'][0]['text'],
      privateRecognition,
    );
    final state = await persisted();
    final cached = state['imports'][id] as Map;
    expect(cached['source']['id'], isNot(cached['preview']['id']));
    expect(cached['preview']['id'], isNot(cached['recognition']['id']));
    expect(cached['recognition']['media_type'], 'application/json');
    expect(jsonEncode(state), isNot(contains(privateRecognition)));
    final assets = (await encryptedFiles())
        .where((file) => file.path.contains('/assets/'))
        .toList();
    expect(assets, hasLength(3));
    for (final file in assets) {
      final encrypted = await file.readAsBytes();
      expect(ascii.decode(encrypted.sublist(0, 8)), 'SPASSET1');
      expect(latin1.decode(encrypted), isNot(contains(privateRecognition)));
      expect(latin1.decode(encrypted), isNot(contains(privateOriginal)));
    }
    server.online = false;
    await restartOffline();
    expect(await repo.importPreview(id), orderedEquals(previewPng()));
    expect(await repo.importRecognition(id), recognition);
    expect(await repo.importSource(id), orderedEquals(syntheticPdf()));
  });

  for (final mismatch in ['source_hash', 'selected_page']) {
    test(
      'Recognition with the wrong $mismatch is never published to the local result cache',
      () async {
        final remoteId = await server.seed(syntheticPdf(), page: 1);
        await server.finishRecognition(
          remoteId,
          selectedPage: mismatch == 'selected_page' ? 0 : 1,
          sourceHash: mismatch == 'source_hash' ? 'e' * 64 : null,
        );
        await repo.refreshImports('project');
        final record = repo.imports('project').single;
        expect(record['page'], 1);
        expect(record['recognition'], isNull);
        final state = await persisted();
        expect(state['imports'][record['local_id']]['recognition'], isNull);
        await expectLater(
          repo.importRecognition(record['local_id']),
          throwsA(isA<ApiException>()),
        );
        expect(
          await repo.importSource(record['local_id']),
          orderedEquals(syntheticPdf()),
        );
        expect(
          (await encryptedFiles()).where(
            (file) => file.path.contains('/assets/'),
          ),
          hasLength(2),
        );
      },
    );
  }

  test(
    'A changed server manifest cannot replace the locally preserved source',
    () async {
      server.online = false;
      final record = await capture();
      final id = record['local_id'] as String;
      final originalReference = offlineCopy(
        Map<String, dynamic>.from(record['source']),
      );
      server.mutateManifestHash = true;
      server.online = true;
      await repo.sync();
      expect(repo.pending, 1);
      expect(repo.getImport(id)['sync_status'], 'Eingabe prüfen');
      expect(repo.getImport(id)['source'], originalReference);
      expect(repo.getImport(id)['sha256'], record['sha256']);
      expect(server.chunkCalls, isEmpty);
      expect(await repo.importSource(id), orderedEquals(syntheticPdf()));
      final state = await persisted();
      expect(state['imports'][id]['source'], originalReference);
    },
  );

  test('Capture requires project permission and a writing role before publishing media', () async {
    final bytes = syntheticPdf();
    await expectLater(
      repo.captureImport(
        'unassigned-project',
        bytes,
        filename: 'synthetic.pdf',
        mediaType: 'application/pdf',
        title: 'Denied',
      ),
      throwsA(isA<ApiException>().having((e) => e.status, 'status', 403)),
    );
    await repo.login({...user, 'role': 'accountant'}, projects);
    await idle(repo);
    await expectLater(
      repo.captureImport(
        'project',
        bytes,
        filename: 'synthetic.pdf',
        mediaType: 'application/pdf',
        title: 'Read only',
      ),
      throwsA(isA<ApiException>().having((e) => e.status, 'status', 403)),
    );
    expect(repo.pending, 0);
    expect(server.manifestCalls, isEmpty);
    expect(
      (await encryptedFiles()).where((file) => file.path.contains('/assets/')),
      isEmpty,
    );
  });
}

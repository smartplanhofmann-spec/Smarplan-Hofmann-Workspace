import 'dart:convert';
import 'dart:io';
import 'dart:typed_data';

import 'package:flutter_test/flutter_test.dart';
import 'package:smartplan_office/api.dart';
import 'package:smartplan_office/offline_plans.dart';

import 'offline_plans_test.dart' show PlanServer, TestDevice, idle;

final fieldPng = Uint8List.fromList(
  base64Decode(
    'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=',
  ),
);

class FieldServer extends PlanServer {
  bool fieldGrant = true;
  final media = <String, Map<String, dynamic>>{};
  final creates = <Map<String, dynamic>>[];
  final chunks = <int, Uint8List>{};
  @override
  Future<dynamic> call(String path, [Map<String, dynamic>? body]) async {
    if (!online) throw const ApiException(0, 'Offline');
    if (path.split('?').first == '/api/business/capabilities')
      return {
        'readonly': false,
        'permissions': ['time.own', 'documents.read', 'documents.write'],
        'capabilities': ['business_time', 'business_operations'],
      };
    if (path == '/api/business/offline/access')
      return {
        'token': 'offline_business_synthetic',
        'expires_at': DateTime.now()
            .toUtc()
            .add(const Duration(days: 7))
            .toIso8601String(),
        'capabilities': [if (fieldGrant) 'field_media'],
      };
    if (path.startsWith('/api/business/media')) {
      if (forbidden) throw const ApiException(403, 'Zugriff entzogen');
      if (path == '/api/business/media') {
        creates.add(Map<String, dynamic>.from(jsonDecode(jsonEncode(body))));
        return media.putIfAbsent(
          body!['request_id'],
          () => {
            ...body,
            'id': 'b' * 32,
            'project_id': 'p',
            'status': 'uploading',
            'revision': 1,
            'uploaded_chunks': [],
            'chunk_size': 262144,
          },
        );
      }
      if (path.contains('/chunks/')) {
        chunks[int.parse(path.split('/').last)] = base64Decode(
          body!['content_base64'],
        );
        return {'ok': true};
      }
      final record = media.values.single;
      if (path.endsWith('/complete')) {
        record['status'] = 'ready';
        record['uploaded_chunks'] = chunks.keys.toList();
        if (loseAck) {
          loseAck = false;
          throw const ApiException(0, 'Bestätigung verloren');
        }
        return record;
      }
      return record;
    }
    return super.call(path, body);
  }
}

void main() {
  late Directory folder;
  late TestDevice device;
  late FieldServer server;
  late OfflinePlans repo;
  setUp(() async {
    folder = await Directory.systemTemp.createTemp('smartplan-field-media-');
    device = TestDevice(folder);
    server = FieldServer()..token = 'full-session';
    repo = OfflinePlans(api: server, transport: server, device: device);
    await repo.login(
      {'id': 'a' * 32, 'role': 'technician'},
      [
        {'id': 'p', 'name': 'Test'},
      ],
      fieldMedia: true,
    );
    await idle(repo);
  });
  tearDown(() async {
    await idle(repo);
    repo.dispose();
    server.dispose();
    await folder.delete(recursive: true);
  });
  test('Original and note are encrypted before acknowledgement and survive restart and lost upload ACK', () async {
    server.online = false;
    final record = await repo.captureFieldPhoto(
      'p',
      fieldPng,
      filename: 'synthetic.png',
      mediaType: 'image/png',
      caption: 'Synthetischer Mangel im Test',
    );
    await idle(repo);
    expect(repo.pending, 1);
    expect(await repo.fieldPhotoSource(record['local_id']), fieldPng);
    final plaintext = await folder
        .list(recursive: true)
        .where((f) => f is File)
        .cast<File>()
        .asyncMap((f) => f.readAsBytes())
        .toList();
    expect(
      plaintext.any(
        (b) => utf8
            .decode(b, allowMalformed: true)
            .contains('Synthetischer Mangel'),
      ),
      isFalse,
    );
    repo.dispose();
    repo = OfflinePlans(api: server, transport: server, device: device);
    await repo.resume();
    await idle(repo);
    expect(
      repo.fieldPhotos('p').single['caption'],
      'Synthetischer Mangel im Test',
    );
    server.online = true;
    server.loseAck = true;
    await repo.sync();
    expect(repo.pending, 1);
    await repo.sync();
    expect(repo.pending, 0);
    expect(server.media.length, 1);
    expect(server.creates, hasLength(1));
    expect(repo.fieldPhotos('p').single['sync_status'], 'Synchronisiert');
    expect(await repo.fieldPhotoSource(record['local_id']), fieldPng);
  });
  test(
    'Field grant refuses PDF and preserves an unsynced photo on access denial',
    () async {
      await expectLater(
        repo.captureFieldPhoto(
          'p',
          Uint8List.fromList(ascii.encode('%PDF-1.4')),
          filename: 'private.pdf',
          mediaType: 'application/pdf',
        ),
        throwsA(isA<ApiException>()),
      );
      server.online = false;
      await repo.captureFieldPhoto(
        'p',
        fieldPng,
        filename: 'keep.png',
        mediaType: 'image/png',
      );
      await idle(repo);
      server.online = true;
      server.forbidden = true;
      await repo.sync();
      expect(repo.pending, 1);
      expect(repo.fieldPhotos('p').single['sync_status'], 'Zugriff gesperrt');
    },
  );
}

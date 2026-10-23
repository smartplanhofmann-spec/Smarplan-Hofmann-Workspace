part of 'offline_plans.dart';

/// Import metadata shares the plan workspace's single durable writer. Source
/// and preview bytes live only in independently encrypted immutable assets.
extension PlanImports on OfflinePlans {
  Map get _imports => _state?['imports'] as Map? ?? {};

  void _importAccess(int epoch, String project) {
    if (epoch != _epoch || _disposed) {
      throw StateError('Offline-Konto wurde gewechselt.');
    }
    requireAccess();
    if (!_allowed(project)) {
      throw const ApiException(403, 'Projekt nicht freigegeben.');
    }
  }

  List<Map<String, dynamic>> imports(String project) {
    _importAccess(_epoch, project);
    return [
      for (final entry in _imports.values)
        if (entry['project_id'] == project)
          offlineCopy(Map<String, dynamic>.from(entry)),
    ];
  }

  Map<String, dynamic> getImport(String localId) {
    requireAccess();
    final record = _imports[localId];
    if (record == null || !_allowed(record['project_id'])) {
      throw const ApiException(
        404,
        'Planquelle auf diesem Gerät nicht verfügbar.',
      );
    }
    return offlineCopy(Map<String, dynamic>.from(record));
  }

  Future<Map<String, dynamic>> captureImport(
    String project,
    Uint8List bytes, {
    required String filename,
    required String mediaType,
    required String title,
    int page = 0,
  }) async {
    final epoch = _epoch;
    _importAccess(epoch, project);
    if (!['owner', 'manager', 'technician'].contains(user['role'])) {
      throw const ApiException(403, 'Keine Schreibberechtigung.');
    }
    if (title.trim().isEmpty ||
        title.length > 200 ||
        page < 0 ||
        page >= 50 ||
        (mediaType != 'application/pdf' && page != 0)) {
      throw const ApiException(
        400,
        'Plantitel und gültige Quellseite erwartet.',
      );
    }
    final source = await EncryptedAssets(_vault!)
        .put(bytes, mediaType: mediaType, filename: filename);
    _importAccess(epoch, project);
    final id = source['id'] as String;
    final result = await _change((state) {
      _importAccess(epoch, project);
      final record = <String, dynamic>{
        ...source,
        'local_id': id,
        'project_id': project,
        'title': title.trim(),
        'page': page,
        'source': source,
        'request_id': offlineId(),
        'status': 'local',
        'sync_status': 'Wartet auf Verbindung',
      };
      (state['imports'] ??= {})[id] = record;
      (state['import_outbox'] ??= []).add(id);
      return offlineCopy(record);
    });
    unawaited(sync());
    return result;
  }

  Future<Uint8List> importSource(String localId) =>
      _readImportAsset(localId, 'source');

  Future<Map<String, dynamic>> importRecognition(String localId) async {
    final bytes = await _readImportAsset(localId, 'recognition');
    final data = Map<String, dynamic>.from(jsonDecode(utf8.decode(bytes)));
    final record = getImport(localId);
    if (data['schema_version'] != 1 ||
        data['status'] != 'needs_review' ||
        data['source']?['sha256'] != record['sha256'] ||
        data['source']?['selected_page'] != record['page']) {
      throw const ApiException(
        0,
        'Erkennung gehört nicht zu dieser Planquelle.',
      );
    }
    return data;
  }

  Future<Uint8List> importPreview(String localId) async {
    final record = getImport(localId);
    if (record['preview'] != null) return _readImportAsset(localId, 'preview');
    if (record['media_type'] != 'application/pdf') return importSource(localId);
    throw const ApiException(
      0,
      'Die PDF-Vorschau ist nach der Verarbeitung auf dem Server verfügbar.',
    );
  }

  Future<Uint8List> _readImportAsset(String localId, String kind) async {
    final epoch = _epoch;
    final record = getImport(localId);
    final ref = record[kind];
    if (ref is! Map) {
      throw const ApiException(
        0,
        'Diese Datei ist noch nicht auf dem Gerät gespeichert. Mit Verbindung neu laden.',
      );
    }
    final bytes = await EncryptedAssets(_vault!)
        .read(Map<String, dynamic>.from(ref));
    _importAccess(epoch, record['project_id']);
    return bytes;
  }

  Map<String, dynamic> _validateImport(
    Map<String, dynamic> remote,
    String project,
  ) {
    const states = {'uploading', 'queued', 'running', 'needs_review', 'failed'};
    if (remote['id'] is! String ||
        !RegExp(r'^[a-f0-9]{32}$').hasMatch(remote['id']) ||
        remote['project_id'] != project ||
        remote['sha256'] is! String ||
        !RegExp(r'^[a-f0-9]{64}$').hasMatch(remote['sha256']) ||
        remote['size'] is! int ||
        remote['size'] < 1 ||
        remote['size'] > 20 * 1024 * 1024 ||
        !{
          'image/jpeg',
          'image/png',
          'application/pdf',
        }.contains(remote['media_type']) ||
        remote['title'] is! String ||
        remote['filename'] is! String ||
        remote['page'] is! int ||
        remote['page'] < 0 ||
        remote['page'] >= 50 ||
        !states.contains(remote['status'])) {
      throw const ApiException(0, 'Ungültiger Planimport vom Server.');
    }
    return remote;
  }

  String _importStatus(String status) => switch (status) {
    'uploading' => 'Wartet auf Übertragung',
    'queued' => 'Auf Server gespeichert · wartet auf Verarbeitung',
    'running' => 'Wird auf dem Server verarbeitet',
    'needs_review' => 'Ergebnis zur Prüfung bereit',
    'failed' => 'Verarbeitung fehlgeschlagen · Original erhalten',
    _ => 'Wartet auf Verbindung',
  };

  Future<void> _mergeImport(
    int epoch,
    String project,
    Map<String, dynamic> remote, {
    String? localId,
  }) async {
    _importAccess(epoch, project);
    _validateImport(remote, project);
    await _change((state) {
      _importAccess(epoch, project);
      state['imports_supported'] = true;
      final records = state['imports'] ??= {};
      final matches = records.values.where(
        (r) => r['server_id'] == remote['id'],
      );
      final id =
          localId ??
          (matches.isEmpty ? remote['id'] : matches.first['local_id']);
      final previous = records[id];
      if (previous != null &&
          [
            'project_id',
            'sha256',
            'size',
            'media_type',
            'filename',
            'page',
          ].any((key) => previous[key] != remote[key])) {
        throw const ApiException(
          409,
          'Serverquelle stimmt nicht mit dem gespeicherten Original überein.',
        );
      }
      records[id] = {
        ...remote,
        ...?(previous as Map?),
        'local_id': id,
        'server_id': remote['id'],
        'status': remote['status'],
        'sync_status': _importStatus(remote['status']),
        'uploaded_chunks': remote['uploaded_chunks'],
        'preview_sha256': remote['preview_sha256'],
        'preview_size': remote['preview_size'],
        'result_sha256': remote['result_sha256'],
        'error_message': remote['error_message'],
      };
      if (remote['status'] != 'uploading') {
        (state['import_outbox'] as List?)?.remove(id);
      }
    });
  }

  Future<void> _cacheImport(int epoch, String localId) async {
    var record = getImport(localId);
    final project = record['project_id'] as String;
    final path = '/api/projects/$project/plan-imports/${record['server_id']}';
    for (final kind in ['source', 'preview', 'recognition']) {
      _importAccess(epoch, project);
      record = getImport(localId);
      if (record[kind] != null ||
          record['status'] == 'uploading' ||
          (kind != 'source' && record['status'] != 'needs_review'))
        continue;
      if (kind == 'recognition') {
        final bytes = await transport.bytes(
          '$path/result',
          mediaType: 'application/json',
          maxBytes: 1024 * 1024,
        );
        _importAccess(epoch, project);
        final hash = (await Sha256().hash(bytes)).bytes
            .map((byte) => byte.toRadixString(16).padLeft(2, '0'))
            .join();
        _importAccess(epoch, project);
        if (hash != record['result_sha256']) {
          throw const ApiException(
            0,
            'Erkennung stimmt nicht mit ihrer Prüfsumme überein.',
          );
        }
        final result = Map<String, dynamic>.from(
          jsonDecode(utf8.decode(bytes)),
        );
        if (result['source']?['sha256'] != record['sha256'] ||
            result['source']?['selected_page'] != record['page']) {
          throw const ApiException(
            0,
            'Erkennung gehört nicht zu dieser Planquelle.',
          );
        }
        final ref = await EncryptedAssets(_vault!).putRecognition(result);
        _importAccess(epoch, project);
        await _change((state) {
          _importAccess(epoch, project);
          state['imports'][localId]['recognition'] ??= ref;
        });
        continue;
      }
      final mime = kind == 'source'
          ? record['media_type'] as String
          : 'image/png';
      final expectedHash = kind == 'source'
          ? record['sha256']
          : record['preview_sha256'];
      final expectedSize = kind == 'source'
          ? record['size']
          : record['preview_size'];
      if (expectedHash is! String ||
          expectedSize is! int ||
          expectedSize < 1 ||
          expectedSize > 20 * 1024 * 1024) {
        throw const ApiException(0, 'Prüfsumme der Serverdatei fehlt.');
      }
      final bytes = await transport.bytes(
        '$path/$kind',
        mediaType: mime,
        maxBytes: expectedSize,
      );
      _importAccess(epoch, project);
      final ref = await EncryptedAssets(_vault!).put(
        bytes,
        mediaType: mime,
        filename: kind == 'source' ? record['filename'] : 'plan-vorschau.png',
      );
      _importAccess(epoch, project);
      if (ref['sha256'] != expectedHash || ref['size'] != expectedSize) {
        throw const ApiException(
          0,
          'Serverdatei stimmt nicht mit ihrer Prüfsumme überein.',
        );
      }
      await _change((state) {
        _importAccess(epoch, project);
        state['imports'][localId][kind] ??= ref;
      });
    }
  }

  Future<void> refreshImports(String project) async {
    final epoch = _epoch;
    _importAccess(epoch, project);
    if (transport.token == null) return;
    try {
      final remote = await transport.call(
        '/api/projects/$project/plan-imports',
      );
      _importAccess(epoch, project);
      if (remote is! List)
        throw const ApiException(0, 'Ungültige Importliste.');
      await _change((state) {
        _importAccess(epoch, project);
        state['imports_supported'] = true;
      });
      for (final item in remote) {
        final data = Map<String, dynamic>.from(item);
        await _mergeImport(epoch, project, data);
        final matches = _imports.values.where(
          (r) => r['server_id'] == data['id'],
        );
        if (matches.isNotEmpty)
          await _cacheImport(epoch, matches.first['local_id']);
      }
    } on ApiException catch (error) {
      await _importError(epoch, project, null, error);
    }
  }

  Future<void> _importError(
    int epoch,
    String project,
    String? localId,
    ApiException error,
  ) async {
    if (epoch != _epoch || !active) return;
    if (error.status == 401) {
      await lock();
      return;
    }
    final revoked =
        error.status == 403 ||
        (error.status == 404 && _state?['imports_supported'] == true);
    final message = error.status == 404 && !revoked
        ? 'Import wartet auf das Server-Update. Original bleibt auf diesem Gerät.'
        : error.status == 0 || error.status >= 500
        ? 'Keine Verbindung · Original bleibt auf diesem Gerät gespeichert.'
        : error.message;
    notice = message;
    await _change((state) {
      if (localId != null) {
        state['imports'][localId]['sync_status'] = revoked
            ? 'Zugriff gesperrt'
            : [400, 409, 413, 415].contains(error.status)
            ? 'Eingabe prüfen'
            : error.status == 404
            ? 'Server-Update erforderlich'
            : 'Wartet auf Verbindung';
        state['imports'][localId]['error_message'] = message;
      }
      if (revoked) {
        (state['projects'] as List).removeWhere((p) => p['id'] == project);
      }
    });
  }

  Future<void> _syncImports(int epoch, String? token) async {
    final candidates = _imports.keys.toList();
    for (final localId in candidates) {
      if (epoch != _epoch || !permitted || token != transport.token) return;
      var record = Map<String, dynamic>.from(_imports[localId]);
      final project = record['project_id'] as String;
      if (!_allowed(project) ||
          [
            'Zugriff gesperrt',
            'Eingabe prüfen',
          ].contains(record['sync_status']))
        continue;
      final pending = (_state!['import_outbox'] as List? ?? []).contains(
        localId,
      );
      final needsCache =
          record['server_id'] != null &&
          record['status'] != 'uploading' &&
          (record['source'] == null ||
              (record['status'] == 'needs_review' &&
                  (record['preview'] == null ||
                      record['recognition'] == null)));
      if (!pending &&
          !needsCache &&
          !['queued', 'running'].contains(record['status']))
        continue;
      if (pending && !['owner', 'manager', 'technician'].contains(user['role']))
        continue;
      final collection = '/api/projects/$project/plan-imports';
      try {
        Map<String, dynamic> remote;
        if (pending) {
          remote = Map<String, dynamic>.from(
            await transport.call(collection, {
              for (final key in [
                'request_id',
                'title',
                'filename',
                'media_type',
                'size',
                'sha256',
                'page',
              ])
                key: record[key],
            }),
          );
        } else {
          remote = Map<String, dynamic>.from(
            await transport.call('$collection/${record['server_id']}'),
          );
        }
        _importAccess(epoch, project);
        await _mergeImport(epoch, project, remote, localId: localId);
        if (pending && remote['status'] == 'uploading') {
          if (remote['chunk_size'] != 262144 ||
              remote['uploaded_chunks'] is! List) {
            throw const ApiException(0, 'Unbekanntes Übertragungsformat.');
          }
          final source = await importSource(localId);
          _importAccess(epoch, project);
          final count = (source.length + 262143) ~/ 262144;
          final received = remote['uploaded_chunks'] as List;
          if (received.any((i) => i is! int || i < 0 || i >= count) ||
              received.toSet().length != received.length) {
            throw const ApiException(0, 'Ungültiger Übertragungsstand.');
          }
          for (var index = 0; index < count; index++) {
            if (received.contains(index)) continue;
            _importAccess(epoch, project);
            await transport.putChunk(
              '$collection/${remote['id']}/chunks/$index',
              Uint8List.sublistView(
                source,
                index * 262144,
                ((index + 1) * 262144).clamp(0, source.length),
              ),
            );
            _importAccess(epoch, project);
          }
          remote = Map<String, dynamic>.from(
            await transport.call('$collection/${remote['id']}/complete', {}),
          );
          _importAccess(epoch, project);
          await _mergeImport(epoch, project, remote, localId: localId);
        }
        record = getImport(localId);
        await _cacheImport(epoch, localId);
      } on ApiException catch (error) {
        await _importError(epoch, project, localId, error);
        if (error.status == 0 || error.status == 401 || error.status >= 500)
          return;
      }
    }
  }
}

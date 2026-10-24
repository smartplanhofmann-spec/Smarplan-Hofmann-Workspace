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
        if (entry['project_id'] == project &&
            !_deleted(
              'import',
              localId: entry['local_id'],
              serverId: entry['server_id'],
            ))
          offlineCopy(Map<String, dynamic>.from(entry)),
    ];
  }

  Map<String, dynamic> getImport(String localId) {
    requireAccess();
    final record = _imports[localId];
    if (record == null ||
        !_allowed(record['project_id']) ||
        _deleted('import', localId: localId, serverId: record['server_id'])) {
      throw const ApiException(
        404,
        'Planquelle auf diesem Gerät nicht verfügbar.',
      );
    }
    return offlineCopy({
      ...Map<String, dynamic>.from(record),
      'view_rotation_quarter_turns': record['view_rotation_quarter_turns'] ?? 0,
    });
  }

  Future<void> setImportRotation(String localId, int quarterTurns) async {
    if (quarterTurns < 0 || quarterTurns > 3) {
      throw const ApiException(
        400,
        'Eine Ansichtsdrehung von 0 bis 3 erwartet.',
      );
    }
    final epoch = _epoch;
    final record = getImport(localId);
    final project = record['project_id'] as String;
    _importAccess(epoch, project);
    await _change((state) {
      _importAccess(epoch, project);
      getImport(localId);
      state['imports'][localId]['view_rotation_quarter_turns'] = quarterTurns;
    });
  }

  Future<void> deleteImport(String localId) => _deleteEntry('import', localId);

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
    final requestId = offlineId();
    final result = await _change((state) {
      _importAccess(epoch, project);
      final record = <String, dynamic>{
        ...source,
        'local_id': id,
        'project_id': project,
        'title': title.trim(),
        'page': page,
        'source': source,
        'request_id': requestId,
        'create_request_id': requestId,
        'status': 'local',
        'sync_status': 'Wartet auf Verbindung',
        'view_rotation_quarter_turns': 0,
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
    getImport(localId);
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
    if (remote['deleted'] == true) {
      final event = _deletionEvent(remote, project, kind: 'import');
      await _change((state) {
        _importAccess(epoch, project);
        _applyDeletion(state, event);
      });
      await _cleanupDeletedAssets(epoch);
      return;
    }
    _validateImport(remote, project);
    await _change((state) {
      _importAccess(epoch, project);
      state['imports_supported'] = true;
      if (_deleted(
        'import',
        localId: localId,
        serverId: remote['id'],
        state: state,
      )) {
        if (localId != null) {
          final marker = (state['import_deletions'] as Map? ?? {})[localId];
          if (marker != null) marker['server_id'] ??= remote['id'];
        }
        return;
      }
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
        'view_rotation_quarter_turns':
            previous?['view_rotation_quarter_turns'] ?? 0,
        'create_request_id': previous?['create_request_id'],
      };
      if (remote['status'] != 'uploading') {
        (state['import_outbox'] as List?)?.remove(id);
      }
    });
  }

  Future<void> _cacheImport(int epoch, String localId) async {
    try {
      await _cacheImportAssets(epoch, localId);
    } on ApiException catch (error) {
      if (error.status != 410) rethrow;
      await _acceptItemGone(epoch, 'import', localId);
    }
  }

  Future<void> _cacheImportAssets(int epoch, String localId) async {
    if (_deleted('import', localId: localId)) return;
    var record = getImport(localId);
    final project = record['project_id'] as String;
    final path = '/api/projects/$project/plan-imports/${record['server_id']}';
    for (final kind in ['source', 'preview', 'recognition']) {
      _importAccess(epoch, project);
      if (_deleted('import', localId: localId)) return;
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
        if (_deleted('import', localId: localId)) return;
        final hash = (await Sha256().hash(bytes)).bytes
            .map((byte) => byte.toRadixString(16).padLeft(2, '0'))
            .join();
        _importAccess(epoch, project);
        if (_deleted('import', localId: localId)) return;
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
        final vault = _vault!;
        final ref = await EncryptedAssets(vault).putRecognition(result);
        await _publishImportRef(
          epoch,
          localId,
          project,
          'recognition',
          ref,
          vault,
        );
        if (_deleted('import', localId: localId)) {
          await _cleanupDeletedAssets(epoch);
          return;
        }
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
      if (_deleted('import', localId: localId)) return;
      final vault = _vault!;
      final ref = await EncryptedAssets(vault).put(
        bytes,
        mediaType: mime,
        filename: kind == 'source' ? record['filename'] : 'plan-vorschau.png',
      );
      if (epoch != _epoch || _vault != vault) {
        await EncryptedAssets(vault).remove(ref);
        throw StateError('Offline-Konto wurde gewechselt.');
      }
      if (ref['sha256'] != expectedHash || ref['size'] != expectedSize) {
        await EncryptedAssets(vault).remove(ref);
        throw const ApiException(
          0,
          'Serverdatei stimmt nicht mit ihrer Prüfsumme überein.',
        );
      }
      await _publishImportRef(epoch, localId, project, kind, ref, vault);
      if (_deleted('import', localId: localId)) {
        await _cleanupDeletedAssets(epoch);
        return;
      }
    }
  }

  Future<void> _publishImportRef(
    int epoch,
    String localId,
    String project,
    String kind,
    Map<String, dynamic> ref,
    OfflineVault vault,
  ) async {
    if (epoch != _epoch || _vault != vault) {
      await EncryptedAssets(vault).remove(ref);
      throw StateError('Offline-Konto wurde gewechselt.');
    }
    var unused = false;
    try {
      await _change((state) {
        _importAccess(epoch, project);
        if (_deleted('import', localId: localId, state: state)) {
          final marker = state['import_deletions'][localId];
          (marker['assets'] ??= []).add(ref);
        } else if (state['imports'][localId][kind] == null) {
          state['imports'][localId][kind] = ref;
        } else {
          unused = true;
        }
      });
    } catch (_) {
      // A failed acknowledgement can follow a durable snapshot. Check with a
      // separate reader so an active writer's generation is never changed.
      await _removeUnpublishedImportRef(vault, ref);
      rethrow;
    }
    if (unused) await EncryptedAssets(vault).remove(ref);
  }

  Future<void> _removeUnpublishedImportRef(
    OfflineVault vault,
    Map<String, dynamic> ref,
  ) async {
    try {
      final saved = await OfflineVault(vault.directory, vault.key).read();
      final records = (saved?['imports'] as Map? ?? {}).values;
      if (records.any(
        (record) => [
          'source',
          'preview',
          'recognition',
        ].any((kind) => record[kind]?['id'] == ref['id']),
      ))
        return;
      final deleted = (saved?['import_deletions'] as Map? ?? {}).values;
      if (deleted.any(
        (marker) => (marker['assets'] as List? ?? []).any(
          (asset) => asset['id'] == ref['id'],
        ),
      ))
        return;
      await EncryptedAssets(vault).remove(ref);
    } catch (_) {
      // Keep the original failure and preserve bytes if committed ownership
      // cannot be established; never remove an ambiguously referenced asset.
    }
  }

  Future<void> refreshImports(String project) async {
    final epoch = _epoch;
    _importAccess(epoch, project);
    if (transport.token == null) return;
    try {
      if (_state?['deletions_supported'] == true)
        await _refreshDeletions(epoch, project);
      if (_unresolvedDeletion('import', project)) return;
      final generation = _state?['deletion_generation'] ?? 0;
      final remote = await transport.call(
        '/api/projects/$project/plan-imports',
      );
      _importAccess(epoch, project);
      if (generation != (_state?['deletion_generation'] ?? 0)) return;
      if (remote is! List)
        throw const ApiException(0, 'Ungültige Importliste.');
      await _change((state) {
        _importAccess(epoch, project);
        state['imports_supported'] = true;
      });
      for (final item in remote) {
        if (generation != (_state?['deletion_generation'] ?? 0)) return;
        final data = Map<String, dynamic>.from(item);
        await _mergeImport(epoch, project, data);
        final matches = _imports.values.where(
          (r) => r['server_id'] == data['id'],
        );
        if (matches.isNotEmpty &&
            !_deleted('import', localId: matches.first['local_id']))
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
    if (error.status == 410 && localId != null) {
      await _acceptItemGone(epoch, 'import', localId);
      return;
    }
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
        if (_deleted('import', localId: localId, state: state)) return;
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
      if (_deleted('import', localId: localId) || _imports[localId] == null)
        continue;
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
        if (_deleted('import', localId: localId)) continue;
        if (pending && remote['status'] == 'uploading') {
          if (remote['chunk_size'] != 262144 ||
              remote['uploaded_chunks'] is! List) {
            throw const ApiException(0, 'Unbekanntes Übertragungsformat.');
          }
          final source = await importSource(localId);
          _importAccess(epoch, project);
          if (_deleted('import', localId: localId)) continue;
          final count = (source.length + 262143) ~/ 262144;
          final received = remote['uploaded_chunks'] as List;
          if (received.any((i) => i is! int || i < 0 || i >= count) ||
              received.toSet().length != received.length) {
            throw const ApiException(0, 'Ungültiger Übertragungsstand.');
          }
          for (var index = 0; index < count; index++) {
            if (received.contains(index)) continue;
            _importAccess(epoch, project);
            if (_deleted('import', localId: localId)) break;
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
          if (_deleted('import', localId: localId)) continue;
          remote = Map<String, dynamic>.from(
            await transport.call('$collection/${remote['id']}/complete', {}),
          );
          _importAccess(epoch, project);
          await _mergeImport(epoch, project, remote, localId: localId);
        }
        if (_deleted('import', localId: localId)) continue;
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

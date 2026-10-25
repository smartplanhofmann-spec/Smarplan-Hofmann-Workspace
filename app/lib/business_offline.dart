part of 'offline_plans.dart';

/// Time events use the same encrypted atomic writer and account grant as plans.
/// Each event is frozen durably before the UI acknowledges a tap or sync runs.
extension OfflineBusinessTime on OfflinePlans {
  bool get businessReadOnly => _state?['business_readonly'] == true;
  Future<bool> _businessWritesAvailable(int epoch, String? token) async {
    try {
      final value = Map<String, dynamic>.from(
        await transport.call('/api/business/capabilities'),
      );
      if (epoch != _epoch || transport.token != token || !permitted)
        return false;
      final readonly = value['readonly'] == true;
      await _change((state) {
        state['business_readonly'] = readonly;
      });
      if (readonly) {
        notice = 'Der Server ist im Lesemodus. Gesicherte Zeiten und Fotos warten unverändert auf die erneute Schreibfreigabe.';
        return false;
      }
      return true;
    } on ApiException catch (e) {
      if (epoch != _epoch) return false;
      if (e.status == 401) await lock();
      notice = 'Gesicherte Eingaben warten auf eine bestätigte Serverfreigabe. Sie bleiben auf diesem Gerät.';
      return false;
    } catch (_) {
      return false;
    }
  }

  bool get timeEventsSupported =>
      permitted && _state?['time_events_supported'] == true;
  List<Map<String, dynamic>> timeEntries(String project) {
    _entryAccess(_epoch, project);
    if (!timeEventsSupported) return [];
    return [
      for (final value
          in (_state?['business_time_records'] as Map? ?? {}).values)
        if (value['project_id'] == project)
          offlineCopy(Map<String, dynamic>.from(value)),
    ];
  }

  Future<void> cacheTimeEntries(
    String project,
    List<Map<String, dynamic>> entries,
  ) async {
    final epoch = _epoch;
    _entryAccess(epoch, project);
    if (!timeEventsSupported) return;
    final clean = <Map<String, dynamic>>[];
    for (final entry in entries) {
      if (entry['project_id'] != project ||
          entry['id'] is! String ||
          !RegExp(r'^[a-f0-9]{32}$').hasMatch(entry['id']) ||
          entry['revision'] is! int ||
          entry['revision'] < 1)
        throw const ApiException(0, 'Ungültige Zeitbestätigung vom Server.');
      clean.add({
        for (final field in [
          'id',
          'project_id',
          'employee_id',
          'category_id',
          'status',
          'revision',
          'sequence',
          'last_sequence',
          'started_at',
          'start_at',
          'last_at',
          'ended_at',
          'timezone',
          'events',
          'worked_seconds',
          'break_seconds',
          'updated_at',
        ])
          if (entry.containsKey(field)) field: entry[field],
        'user_id': user['id'],
        'sync_status': 'Synchronisiert',
      });
    }
    await _change((state) {
      _entryAccess(epoch, project);
      final records = state.putIfAbsent(
        'business_time_records',
        () => <String, dynamic>{},
      ) as Map;
      for (final entry in clean) {
        final waiting = (state['business_time_outbox'] as List? ?? []).any(
          (op) => op['entry_id'] == entry['id'],
        );
        if (!waiting) records[entry['id']] = entry;
      }
    });
  }

  Future<Map<String, dynamic>> saveTimeEvent(
    String project,
    String action, {
    String? entryId,
    String? categoryId,
    DateTime? occurredAt,
  }) async {
    final epoch = _epoch;
    _entryAccess(epoch, project);
    if (!timeEventsSupported)
      throw const ApiException(
        403,
        'Für die Stempeluhr bitte einmal mit Verbindung neu anmelden und das Projekt freigeben.',
      );
    if (!['start', 'pause', 'resume', 'stop'].contains(action))
      throw const ApiException(400, 'Unbekannte Zeitaktion.');
    final id = entryId ?? offlineId();
    final eventId = offlineId();
    final instant = (occurredAt ?? clock()).toUtc().toIso8601String();
    final result = await _change((state) {
      _entryAccess(epoch, project);
      if (state['time_events_supported'] != true)
        throw const ApiException(403, 'Keine Offline-Zeitfreigabe.');
      final records = state.putIfAbsent(
        'business_time_records',
        () => <String, dynamic>{},
      ) as Map;
      final previous = records[id] as Map?;
      if (previous != null && previous['project_id'] != project)
        throw const ApiException(
          403,
          'Zeiterfassung gehört zu einem anderen Projekt.',
        );
      final status = previous?['status'];
      if (previous?['sync_status'] == 'Konflikt' ||
          previous?['sync_status'] == 'Zugriff gesperrt')
        throw const ApiException(
          409,
          'Diese Zeiterfassung muss zuerst geklärt werden. Ihre Zeiten bleiben gespeichert.',
        );
      if ((action == 'start' && previous != null) ||
          (action == 'pause' && status != 'working') ||
          (action == 'resume' && status != 'paused') ||
          (action == 'stop' && !['working', 'paused'].contains(status)))
        throw const ApiException(
          409,
          'Diese Zeitaktion passt nicht zum aktuellen Stand.',
        );
      if (action == 'start' &&
          records.values.any(
            (r) =>
                r['user_id'] == user['id'] &&
                ['working', 'paused'].contains(r['status']),
          ))
        throw const ApiException(
          409,
          'Bitte die laufende Zeiterfassung zuerst beenden.',
        );
      final revision = previous?['revision'] as int? ?? 0;
      final sequence = (previous?['sequence'] as int? ?? 0) + 1;
      final device = state.putIfAbsent('business_time_device', offlineId);
      final body = <String, dynamic>{
        'request_id': eventId,
        'event_id': eventId,
        'entry_id': id,
        'device_id': device,
        'sequence': sequence,
        'revision': revision,
        'action': action,
        'occurred_at': instant,
        'project_id': project,
        if (categoryId != null) 'category_id': categoryId,
      };
      final events = [
        ...(previous?['local_events'] as List? ?? []),
        {'action': action, 'occurred_at': instant},
      ];
      final record = <String, dynamic>{
        ...?previous,
        'id': id,
        'project_id': project,
        'user_id': user['id'],
        'status': action == 'stop'
            ? 'stopped'
            : action == 'pause'
            ? 'paused'
            : 'working',
        'revision': revision + 1,
        'sequence': sequence,
        'local_events': events,
        'sync_status': 'Auf diesem Gerät gesichert',
      };
      records[id] = record;
      (state.putIfAbsent('business_time_outbox', () => []) as List).add({
        'entry_id': id,
        'project_id': project,
        'body': body,
      });
      return offlineCopy(record);
    });
    unawaited(sync());
    return result;
  }

  Future<void> _syncBusinessTime(int epoch, String? token) async {
    if (!timeEventsSupported) return;
    while (epoch == _epoch && timeEventsSupported && transport.token == token) {
      final queue = _state?['business_time_outbox'] as List? ?? [];
      final records = _state?['business_time_records'] as Map? ?? {};
      final eligible = queue.where(
        (op) =>
            _allowed(op['project_id']) &&
            ![
              'Konflikt',
              'Zugriff gesperrt',
              'Eingabe prüfen',
            ].contains(records[op['entry_id']]?['sync_status']),
      );
      if (eligible.isEmpty) return;
      final op = offlineCopy(Map<String, dynamic>.from(eligible.first));
      final body = Map<String, dynamic>.from(op['body']);
      try {
        final response = Map<String, dynamic>.from(
          await transport.call('/api/business/time/events', body),
        );
        _entryAccess(epoch, op['project_id']);
        if (transport.token != token) return;
        final entry = response['entry'];
        if (response['request_id'] != body['request_id'] ||
            entry is! Map ||
            entry['id'] != op['entry_id'] ||
            entry['project_id'] != op['project_id'] ||
            entry['revision'] is! int)
          throw const ApiException(
            0,
            'Die Zeitbestätigung passt nicht zum gesicherten Vorgang.',
          );
        await _change((state) {
          _entryAccess(epoch, op['project_id']);
          final operations = state['business_time_outbox'] as List;
          operations.removeWhere(
            (item) => item['body']['request_id'] == body['request_id'],
          );
          final local = state['business_time_records'][op['entry_id']] as Map;
          if (!operations.any((item) => item['entry_id'] == op['entry_id'])) {
            state['business_time_records'][op['entry_id']] = {
              ...Map<String, dynamic>.from(entry),
              'user_id': user['id'],
              'sequence': body['sequence'],
              'local_events': local['local_events'],
              'sync_status': 'Synchronisiert',
            };
          }
        });
      } on ApiException catch (e) {
        if (epoch != _epoch || !active) return;
        if (e.status == 401) {
          await lock();
          return;
        }
        if (e.status == 0 || e.status >= 500 || e.status == 429) {
          notice = 'Zeiten bleiben auf diesem Gerät gesichert. Synchronisierung wartet auf Verbindung.';
          return;
        }
        await _change((state) {
          final record = state['business_time_records']?[op['entry_id']];
          if (record != null) {
            record['sync_status'] = e.status == 409
                ? 'Konflikt'
                : [403, 404].contains(e.status)
                ? 'Zugriff gesperrt'
                : 'Eingabe prüfen';
            record['sync_error'] = e.message;
          }
        });
        if (e.status == 403 || e.status == 404) return;
      }
    }
  }
}

extension OfflineBusinessMedia on OfflinePlans {
  bool get fieldMediaSupported =>
      permitted && _state?['field_media_supported'] == true;
  void _fieldAccess(int epoch, String project) {
    _entryAccess(epoch, project);
    if (!fieldMediaSupported)
      throw const ApiException(
        403,
        'Für Offlinefotos bitte mit Verbindung neu anmelden. Vorhandene Originale bleiben gesichert.',
      );
  }

  List<Map<String, dynamic>> fieldPhotos(String project) {
    _fieldAccess(_epoch, project);
    return [
      for (final value
          in (_state?['business_media_records'] as Map? ?? {}).values)
        if (value['project_id'] == project)
          offlineCopy(Map<String, dynamic>.from(value)),
    ];
  }

  Future<Map<String, dynamic>> captureFieldPhoto(
    String project,
    Uint8List bytes, {
    required String filename,
    required String mediaType,
    String caption = '',
  }) async {
    final epoch = _epoch;
    _fieldAccess(epoch, project);
    if (!['image/jpeg', 'image/png'].contains(mediaType))
      throw const ApiException(
        415,
        'Die Offline-Fotodokumentation unterstützt JPEG und PNG.',
      );
    if (caption.length > 2000)
      throw const ApiException(
        400,
        'Die Bildnotiz darf höchstens 2000 Zeichen enthalten.',
      );
    final source = await EncryptedAssets(_vault!)
        .put(bytes, mediaType: mediaType, filename: filename);
    _fieldAccess(epoch, project);
    final request = offlineId();
    final result = await _change((state) {
      _fieldAccess(epoch, project);
      final record = <String, dynamic>{
        ...source,
        'local_id': source['id'],
        'server_id': null,
        'project_id': project,
        'source': source,
        'caption': caption,
        'captured_at': clock().toUtc().toIso8601String(),
        'purpose': 'site_photo',
        'classification': 'operational',
        'create_request_id': request,
        'complete_request_id': offlineId(),
        'status': 'local',
        'sync_status': 'Auf diesem Gerät gesichert',
        'uploaded_chunks': [],
      };
      (state.putIfAbsent('business_media_records', () => <String, dynamic>{})
              as Map)[source['id']] =
          record;
      (state.putIfAbsent('business_media_outbox', () => []) as List).add(
        source['id'],
      );
      return offlineCopy(record);
    });
    unawaited(sync());
    return result;
  }

  Future<Uint8List> fieldPhotoSource(String localId) async {
    final epoch = _epoch;
    final record = (_state?['business_media_records'] as Map? ?? {})[localId];
    if (record == null)
      throw const ApiException(
        404,
        'Foto ist auf diesem Gerät nicht vorhanden.',
      );
    _fieldAccess(epoch, record['project_id']);
    final bytes = await EncryptedAssets(_vault!)
        .read(Map<String, dynamic>.from(record['source']));
    _fieldAccess(epoch, record['project_id']);
    return bytes;
  }

  Map<String, dynamic> _fieldRemote(Map<String, dynamic> remote, Map record) {
    if (remote['id'] is! String ||
        !RegExp(r'^[a-f0-9]{32}$').hasMatch(remote['id']) ||
        remote['project_id'] != record['project_id'] ||
        remote['sha256'] != record['sha256'] ||
        remote['size'] != record['size'] ||
        remote['media_type'] != record['media_type'] ||
        !['uploading', 'ready'].contains(remote['status']))
      throw const ApiException(
        0,
        'Die Fotobestätigung passt nicht zum lokal gesicherten Original.',
      );
    return remote;
  }

  Future<void> _syncBusinessMedia(int epoch, String? token) async {
    if (!fieldMediaSupported) return;
    final waiting = List<String>.from(
      _state?['business_media_outbox'] as List? ?? [],
    );
    for (final id in waiting) {
      if (epoch != _epoch || !fieldMediaSupported || transport.token != token)
        return;
      var record = offlineCopy(
        Map<String, dynamic>.from(_state!['business_media_records'][id]),
      );
      final project = record['project_id'] as String;
      if (!_allowed(project) ||
          [
            'Zugriff gesperrt',
            'Eingabe prüfen',
          ].contains(record['sync_status']))
        continue;
      try {
        _fieldAccess(epoch, project);
        if (record['server_id'] == null) {
          final created = _fieldRemote(
            Map<String, dynamic>.from(
              await transport.call('/api/business/media', {
                'request_id': record['create_request_id'],
                'project_id': project,
                for (final field in [
                  'filename',
                  'media_type',
                  'size',
                  'sha256',
                  'caption',
                  'captured_at',
                  'purpose',
                  'classification',
                ])
                  field: record[field],
              }),
            ),
            record,
          );
          _fieldAccess(epoch, project);
          if (transport.token != token) return;
          await _change((state) {
            _fieldAccess(epoch, project);
            state['business_media_records'][id]['server_id'] = created['id'];
          });
          record = offlineCopy(
            Map<String, dynamic>.from(_state!['business_media_records'][id]),
          );
        }
        var remote = _fieldRemote(
          Map<String, dynamic>.from(
            await transport.call('/api/business/media/${record['server_id']}'),
          ),
          record,
        );
        _fieldAccess(epoch, project);
        if (transport.token != token) return;
        if (remote['status'] != 'ready') {
          final chunks = remote['uploaded_chunks'];
          final count = ((record['size'] as int) + 262143) ~/ 262144;
          if (remote['chunk_size'] != 262144 ||
              chunks is! List ||
              chunks.any((i) => i is! int || i < 0 || i >= count) ||
              chunks.toSet().length != chunks.length)
            throw const ApiException(
              0,
              'Der Foto-Übertragungsstand ist ungültig.',
            );
          final bytes = await fieldPhotoSource(id);
          _fieldAccess(epoch, project);
          for (var index = 0; index < count; index++) {
            if (chunks.contains(index)) continue;
            _fieldAccess(epoch, project);
            if (transport.token != token) return;
            await transport.call(
              '/api/business/media/${record['server_id']}/chunks/$index',
              {
                'content_base64': base64Encode(
                  Uint8List.sublistView(
                    bytes,
                    index * 262144,
                    ((index + 1) * 262144).clamp(0, bytes.length),
                  ),
                ),
              },
            );
            _fieldAccess(epoch, project);
            if (transport.token != token) return;
            await _change((state) {
              _fieldAccess(epoch, project);
              final progress = List<int>.from(
                state['business_media_records'][id]['uploaded_chunks'],
              );
              if (!progress.contains(index)) progress.add(index);
              state['business_media_records'][id]['uploaded_chunks'] = progress;
            });
          }
          remote = _fieldRemote(
            Map<String, dynamic>.from(
              await transport.call(
                '/api/business/media/${record['server_id']}/complete',
                {'request_id': record['complete_request_id']},
              ),
            ),
            record,
          );
          _fieldAccess(epoch, project);
          if (transport.token != token) return;
          if (remote['status'] != 'ready')
            throw const ApiException(
              0,
              'Die vollständige Fotoübertragung wurde noch nicht bestätigt.',
            );
        }
        await _change((state) {
          _fieldAccess(epoch, project);
          final local = state['business_media_records'][id] as Map;
          local['status'] = 'ready';
          local['sync_status'] = 'Synchronisiert';
          local['server_id'] = remote['id'];
          local['revision'] = remote['revision'];
          (state['business_media_outbox'] as List).remove(id);
        });
      } on ApiException catch (e) {
        if (epoch != _epoch || !active) return;
        if (e.status == 401) {
          await lock();
          return;
        }
        if (e.status == 0 || e.status >= 500 || e.status == 429) {
          notice = 'Foto und Notiz bleiben verschlüsselt auf diesem Gerät. Die Übertragung wird fortgesetzt.';
          return;
        }
        await _change((state) {
          final record = state['business_media_records']?[id];
          if (record != null) {
            record['sync_status'] = [403, 404].contains(e.status)
                ? 'Zugriff gesperrt'
                : 'Eingabe prüfen';
            record['sync_error'] = e.message;
          }
        });
      }
    }
  }
}

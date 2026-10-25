import 'dart:async';
import 'dart:convert';

import 'package:flutter/foundation.dart';
import 'package:cryptography/cryptography.dart';

import 'api.dart';
import 'offline_vault.dart';
import 'offline_assets.dart';

part 'offline_imports.dart';
part 'offline_workspace.dart';
part 'business_offline.dart';

/// Plan-only offline workspace. Its scoped seven-day token stays in OS secure storage.
class OfflinePlans extends ChangeNotifier {
  final OfficeApi api;
  final OfficeApi transport;
  final bool ownsTransport;
  final OfflineDevice device;
  final DateTime Function() clock;
  OfflineVault? _vault;
  Map<String, dynamic>? _state;
  Future<void> _tail = Future.value();
  Timer? _timer;
  bool _syncing = false, _disposed = false;
  int _epoch = 0;
  String? notice;
  OfflinePlans({
    required this.api,
    OfflineDevice? device,
    OfficeApi? transport,
    DateTime Function()? clock,
  }) : transport =
           transport ?? OfficeApi(baseUrl: api.base, apiVersion: api.version),
       ownsTransport = transport == null,
       device = device ?? OfflineDevice(),
       clock = clock ?? DateTime.now;
  String get server => '${api.base}|${api.version}';
  bool get active => _state != null;
  bool get permitted {
    if (!active || _state!['locked'] == true) return false;
    final now = clock().toUtc();
    final online = DateTime.parse(_state!['last_online']);
    final seen = DateTime.parse(_state!['last_seen']);
    return !now.isBefore(online) &&
        !now.isBefore(seen.subtract(const Duration(minutes: 2))) &&
        now.difference(online) < const Duration(days: 7);
  }

  Map<String, dynamic> get user =>
      offlineCopy(Map<String, dynamic>.from(_state!['user']));
  List<dynamic> get projects =>
      (offlineCopy({'items': _state?['projects'] ?? []})['items'] as List);
  bool downloaded(String project) =>
      (_state?['downloaded_projects'] as List? ?? []).contains(project);
  int get pending =>
      (_state?['outbox'] as List? ?? []).length +
      (_state?['import_outbox'] as List? ?? []).length +
      (_state?['plan_delete_outbox'] as List? ?? []).length +
      (_state?['import_delete_outbox'] as List? ?? []).length +
      (_state?['workspace_outbox'] as List? ?? []).length +
      (_state?['business_time_outbox'] as List? ?? []).length +
      (_state?['business_media_outbox'] as List? ?? []).length;
  bool get syncing => _syncing;
  void changed() {
    if (!_disposed) notifyListeners();
  }

  void requireAccess() {
    if (!permitted)
      throw const ApiException(
        401,
        'Offline-Freigabe abgelaufen oder gesperrt. Online anmelden; lokale Eingaben bleiben erhalten.',
      );
  }

  bool canAccessProject(String project) => permitted && _allowed(project);
  bool _allowed(String project) => projects.any((p) => p['id'] == project);
  Future<T> _change<T>(T Function(Map<String, dynamic>) action) {
    final epoch = _epoch;
    final next = _tail.then((_) async {
      if (epoch != _epoch || _state == null || _vault == null)
        throw StateError('Offline-Konto wurde gewechselt.');
      final state = offlineCopy(_state!);
      final vault = _vault!;
      final result = action(state);
      state['last_seen'] = clock().toUtc().toIso8601String();
      await vault.write(state);
      if (epoch != _epoch || _vault != vault || _state == null)
        throw StateError('Offline-Konto wurde gewechselt.');
      _state = state;
      changed();
      return result;
    });
    _tail = next.then<void>((_) {}, onError: (Object e, StackTrace s) {});
    return next;
  }

  Future<void> login(
    Map<String, dynamic> user,
    List<dynamic> projects, {
    bool businessTime = false,
    bool fieldMedia = false,
  }) async {
    _epoch++;
    await _tail;
    _state = null;
    _vault = null;
    final vault = await device.open(server, user['id'], create: true);
    final grant = Map<String, dynamic>.from(
      await api.call(
        (businessTime || fieldMedia)
            ? '/api/business/offline/access'
            : '/api/offline/access',
        {},
      ),
    );
    transport.token = grant['token'];
    await device.saveSession(server, user['id'], transport.token);
    final now = clock().toUtc().toIso8601String();
    final state =
        await vault.read() ?? <String, dynamic>{'records': {}, 'outbox': []};
    state.addAll({
      'time_events_supported':
          businessTime &&
          (grant['capabilities'] as List? ?? []).contains('time_events'),
      'field_media_supported':
          fieldMedia &&
          (grant['capabilities'] as List? ?? []).contains('field_media'),
      'cache_schema': 1,
      'user': user,
      'projects': projects,
      'last_online': now,
      'server_expires_at': grant['expires_at'],
      'last_seen': now,
      'locked': false,
      'imports_supported': (grant['capabilities'] as List? ?? []).contains(
        'plan_imports',
      ),
      'deletions_supported': (grant['capabilities'] as List? ?? []).contains(
        'plan_deletion',
      ),
      'workspace_supported':
          (grant['capabilities'] as List? ?? []).contains(
            'offline_workspace',
          ) &&
          (grant['capabilities'] as List? ?? []).contains('project_workspace'),
    });
    for (final record in (state['records'] as Map).values) {
      if (record['sync_status'] == 'Zugriff gesperrt')
        record['sync_status'] = 'Wartet auf Verbindung';
    }
    for (final record in (state['imports'] as Map? ?? {}).values) {
      if (record['sync_status'] == 'Zugriff gesperrt') {
        record['sync_status'] = 'Wartet auf Verbindung';
      }
    }
    for (final record in (state['workspace_records'] as Map? ?? {}).values) {
      if (record['sync_status'] == 'Zugriff gesperrt')
        record['sync_status'] = 'Wartet auf Verbindung';
    }
    await vault.write(state);
    await device.select(server, user['id']);
    _vault = vault;
    _state = state;
    notice = null;
    start();
    changed();
    unawaited(sync());
  }

  Future<void> resume() async {
    if (!await device.unlock())
      throw const ApiException(0, 'Gerät wurde nicht entsperrt.');
    final selected = await device.selected(server);
    if (selected == null)
      throw const ApiException(
        0,
        'Noch keine Offline-Projekte vorhanden. Zuerst online anmelden.',
      );
    _epoch++;
    final epoch = _epoch;
    await _tail;
    _state = null;
    _vault = null;
    try {
      _vault = await device.open(server, selected);
      _state = await _vault!.read();
      if (_state?['cache_schema'] != 1 || _state?['user']?['id'] != selected)
        throw StateError(
          'Offline-Speicherformat oder Konto stimmt nicht überein.',
        );
      transport.token = await device.session(server, selected);
      requireAccess();
      await _change((_) {});
      await _cleanupDeletedAssets(epoch);
      if (epoch != _epoch) throw StateError('Offline-Konto wurde gewechselt.');
    } catch (_) {
      if (epoch == _epoch) {
        _state = null;
        _vault = null;
      }
      rethrow;
    }
    start();
    changed();
    unawaited(sync());
  }

  void start() {
    _timer?.cancel();
    _timer = Timer.periodic(const Duration(seconds: 20), (_) {
      if (permitted)
        unawaited(sync());
      else
        changed();
    });
  }

  Future<void> leave() async {
    _timer?.cancel();
    _epoch++;
    await _tail;
    _state = null;
    _vault = null;
    transport.token = null;
    changed();
  }

  Future<void> logout() async {
    final token = transport.token;
    if (active) {
      await device.saveSession(server, user['id'], null);
      await lock();
    }
    await leave();
    if (token != null) {
      final revoke = OfficeApi(baseUrl: api.base, apiVersion: api.version)
        ..token = token;
      unawaited(
        revoke
            .call('/api/offline/logout', {})
            .then<void>((_) {}, onError: (Object e, StackTrace s) {})
            .whenComplete(revoke.dispose),
      );
    }
  }

  Future<void> flush() => _tail;
  Future<void> refreshProjects(List<dynamic> items) => _change((state) {
    state['projects'] = items;
  });
  List<dynamic> list(String project) {
    requireAccess();
    if (!_allowed(project))
      throw const ApiException(
        403,
        'Projekt ist auf diesem Gerät nicht freigegeben.',
      );
    return [
      for (final entry in (_state!['records'] as Map).values)
        if (entry['project_id'] == project &&
            !_deleted(
              'plan',
              localId: entry['local_id'],
              serverId: entry['server_id'],
            ))
          offlineCopy(Map<String, dynamic>.from(entry)),
    ];
  }

  Map<String, dynamic> get(String localId) {
    requireAccess();
    final record = _state!['records'][localId];
    if (record == null ||
        !_allowed(record['project_id']) ||
        _deleted('plan', localId: localId, serverId: record['server_id']))
      throw const ApiException(404, 'Lokaler Plan nicht verfügbar.');
    return offlineCopy(Map<String, dynamic>.from(record));
  }

  Future<void> refresh(String project) async {
    requireAccess();
    if (!_allowed(project))
      throw const ApiException(403, 'Projekt nicht freigegeben.');
    if (transport.token == null) return;
    final epoch = _epoch;
    try {
      if (_state?['deletions_supported'] == true)
        await _refreshDeletions(epoch, project);
      if (_unresolvedDeletion('plan', project)) return;
      final generation = _state?['deletion_generation'] ?? 0;
      final plans =
          await transport.call('/api/projects/$project/plans') as List;
      if (epoch != _epoch) return;
      if (generation != (_state?['deletion_generation'] ?? 0)) return;
      await _change((state) {
        _entryAccess(epoch, project);
        if (generation != (state['deletion_generation'] ?? 0) ||
            _unresolvedDeletion('plan', project, state: state))
          return;
        final records = state['records'] as Map;
        final downloaded = state['downloaded_projects'] ??= [];
        if (!(downloaded as List).contains(project)) downloaded.add(project);
        for (final remote in plans) {
          if (_deleted('plan', serverId: remote['id'], state: state)) continue;
          final matching = records.values.where(
            (r) => r['server_id'] == remote['id'],
          );
          final key = matching.isEmpty
              ? remote['id']
              : matching.first['local_id'];
          final waiting = (state['outbox'] as List).any(
            (op) => op['local_id'] == key,
          );
          if (waiting && records[key]?['sync_status'] == 'Konflikt')
            records[key]['remote'] = remote;
          if (!waiting)
            records[key] = {
              ...remote,
              'local_id': key,
              'server_id': remote['id'],
              'sync_status': 'Synchronisiert',
            };
        }
      });
      notice = null;
    } on ApiException catch (e) {
      if (epoch != _epoch) return;
      notice = e.status == 0
          ? 'Keine Verbindung – lokal verfügbare Pläne.'
          : e.message;
      if (e.status == 401) await lock();
      if (e.status == 403 || e.status == 404) {
        await _change((state) {
          (state['projects'] as List).removeWhere((p) => p['id'] == project);
        });
      }
      changed();
      if (e.status != 0) rethrow;
    }
  }

  Future<Map<String, dynamic>> save(
    String project,
    Map<String, dynamic> drawing, {
    String? localId,
  }) async {
    final epoch = _epoch;
    requireAccess();
    if (!_allowed(project) ||
        !['owner', 'manager', 'technician'].contains(user['role']))
      throw const ApiException(403, 'Keine Schreibberechtigung.');
    if (drawing['title'] is! String ||
        (drawing['title'] as String).trim().isEmpty ||
        (drawing['title'] as String).length > 200 ||
        drawing['walls'] is! List ||
        (drawing['walls'] as List).length > 2000)
      throw const ApiException(
        400,
        'Plantitel und höchstens 2000 Wände erwartet.',
      );
    final id = localId ?? offlineId();
    final result = await _change((state) {
      _entryAccess(epoch, project, write: true);
      if (_deleted('plan', localId: id, state: state))
        throw const ApiException(410, 'Dieser Plan wurde gelöscht.');
      final records = state['records'] as Map;
      final previous = records[id];
      if (previous != null && previous['project_id'] != project)
        throw const ApiException(409, 'Plan gehört zu einem anderen Projekt.');
      final record = <String, dynamic>{
        ...?(previous as Map?),
        ...drawing,
        'local_id': id,
        'project_id': project,
        'sync_status': previous?['sync_status'] == 'Konflikt'
            ? 'Konflikt'
            : 'Wartet auf Verbindung',
      };
      final outbox = state['outbox'] as List;
      if (previous?['sync_status'] == 'Eingabe prüfen')
        outbox.removeWhere((op) => op['local_id'] == id);
      final unsent = outbox.where(
        (op) => op['local_id'] == id && op['body'] == null,
      );
      final snapshot = {'title': drawing['title'], 'walls': drawing['walls']};
      if (unsent.isNotEmpty) {
        unsent.last['snapshot'] = snapshot;
      } else {
        outbox.add({
          'local_id': id,
          'project_id': project,
          'request_id': offlineId(),
          'snapshot': snapshot,
          'body': null,
        });
      }
      if (record['server_id'] == null && record['create_request_id'] == null) {
        record['create_request_id'] = outbox.firstWhere(
          (op) => op['local_id'] == id,
        )['request_id'];
      }
      records[id] = record;
      return offlineCopy(record);
    });
    unawaited(sync());
    return result;
  }

  void _entryAccess(int epoch, String project, {bool write = false}) {
    if (epoch != _epoch || _disposed)
      throw StateError('Offline-Konto wurde gewechselt.');
    requireAccess();
    if (!_allowed(project) ||
        (write && !['owner', 'manager', 'technician'].contains(user['role']))) {
      throw const ApiException(403, 'Keine Berechtigung für dieses Projekt.');
    }
  }

  bool _deleted(
    String kind, {
    String? localId,
    String? serverId,
    String? createId,
    Map<String, dynamic>? state,
  }) {
    final markers = (state ?? _state)?['${kind}_deletions'] as Map? ?? {};
    return (localId != null && markers.containsKey(localId)) ||
        markers.values.any(
          (marker) =>
              (serverId != null && marker['server_id'] == serverId) ||
              (createId != null && marker['create_request_id'] == createId),
        );
  }

  bool _unresolvedDeletion(
    String kind,
    String project, {
    Map<String, dynamic>? state,
  }) => ((state ?? _state)?['${kind}_deletions'] as Map? ?? {}).values.any(
    (marker) =>
        marker['project_id'] == project &&
        marker['pending'] == true &&
        marker['server_id'] == null,
  );

  String? _creationKey(
    Map<String, dynamic> state,
    String kind,
    String localId,
    Map record,
  ) {
    if (record['create_request_id'] is String)
      return record['create_request_id'];
    if (kind == 'import') {
      if (record['source']?['id'] == localId ||
          (state['import_outbox'] as List? ?? []).contains(localId)) {
        return record['request_id'] as String?;
      }
      return null;
    }
    for (final operation in state['outbox'] as List? ?? []) {
      if (operation['local_id'] == localId &&
          (record['server_id'] == null ||
              (operation['path'] as String? ?? '').endsWith('/plans'))) {
        return operation['request_id'] as String?;
      }
    }
    return null;
  }

  void _markDeleted(
    Map<String, dynamic> state,
    String kind,
    String localId,
    Map record, {
    required bool pending,
  }) {
    state['deletion_generation'] =
        (state['deletion_generation'] as int? ?? 0) + 1;
    final markers = state['${kind}_deletions'] ??= <String, dynamic>{};
    final previous = markers[localId] as Map?;
    final assets = List<dynamic>.from(previous?['assets'] as List? ?? []);
    if (kind == 'import') {
      for (final key in ['source', 'preview', 'recognition']) {
        final ref = record[key];
        if (ref is Map && !assets.any((item) => item['id'] == ref['id']))
          assets.add(offlineCopy(Map<String, dynamic>.from(ref)));
      }
    }
    markers[localId] = {
      ...?previous,
      'local_id': localId,
      'project_id': record['project_id'],
      'server_id': record['server_id'] ?? previous?['server_id'],
      'create_request_id':
          _creationKey(state, kind, localId, record) ??
          previous?['create_request_id'],
      'request_id': previous?['request_id'] ?? offlineId(),
      'assets': assets,
      'pending': pending,
    };
    final queue = state['${kind}_delete_outbox'] ??= <dynamic>[];
    if (pending && !queue.contains(localId)) queue.add(localId);
    if (!pending) queue.remove(localId);
    if (kind == 'plan') {
      (state['outbox'] as List).removeWhere(
        (operation) => operation['local_id'] == localId,
      );
      (state['records'] as Map).remove(localId);
    } else {
      (state['import_outbox'] as List?)?.remove(localId);
      (state['imports'] as Map?)?.remove(localId);
    }
  }

  Future<void> deletePlan(String localId) => _deleteEntry('plan', localId);

  Future<void> _deleteEntry(String kind, String localId) async {
    final epoch = _epoch;
    requireAccess();
    await _change((state) {
      final records =
          state[kind == 'plan' ? 'records' : 'imports'] as Map? ?? {};
      final record =
          records[localId] ??
          (state['${kind}_deletions'] as Map? ?? {})[localId];
      if (record == null)
        throw const ApiException(404, 'Lokaler Plan nicht verfügbar.');
      _entryAccess(epoch, record['project_id'], write: true);
      if (!_deleted(kind, localId: localId, state: state))
        _markDeleted(state, kind, localId, record, pending: true);
    });
    await _cleanupDeletedAssets(epoch);
    unawaited(sync());
  }

  Future<void> _cleanupDeletedAssets(int epoch) async {
    if (epoch != _epoch || !permitted || _vault == null) return;
    final vault = _vault!;
    final markers = (_state?['import_deletions'] as Map? ?? {});
    for (final localId in markers.keys.toList()) {
      final marker = markers[localId];
      if (!_allowed(marker['project_id'])) continue;
      for (final item in List<dynamic>.from(marker['assets'] as List? ?? [])) {
        if (epoch != _epoch || !permitted) return;
        try {
          final ref = Map<String, dynamic>.from(item);
          await EncryptedAssets(vault).remove(ref);
          if (epoch != _epoch || _vault != vault) return;
          await _change((state) {
            final current = (state['import_deletions'] as Map? ?? {})[localId];
            (current?['assets'] as List?)?.removeWhere(
              (asset) => asset['id'] == ref['id'],
            );
          });
        } catch (_) {
          if (epoch == _epoch) notice = 'Löschung gespeichert. Gerätespeicher wird beim nächsten Start erneut bereinigt.';
          return;
        }
      }
    }
  }

  Map<String, dynamic> _deletionEvent(
    dynamic value,
    String project, {
    String? kind,
  }) {
    if (value is! Map ||
        value['deleted'] != true ||
        value['status'] != 'deleted' ||
        !['plan', 'import'].contains(value['kind']) ||
        (kind != null && value['kind'] != kind) ||
        value['project_id'] != project ||
        (value['id'] != null && value['id'] is! String) ||
        (value['create_request_id'] != null &&
            value['create_request_id'] is! String) ||
        (value['id'] == null && value['create_request_id'] == null)) {
      throw const ApiException(0, 'Ungültige Löschbestätigung vom Server.');
    }
    return Map<String, dynamic>.from(value);
  }

  void _applyDeletion(Map<String, dynamic> state, Map<String, dynamic> event) {
    final kind = event['kind'] as String;
    final records = state[kind == 'plan' ? 'records' : 'imports'] as Map? ?? {};
    final markers = state['${kind}_deletions'] ??= <String, dynamic>{};
    final ids = <String>{};
    for (final record in records.values.toList()) {
      if (record['project_id'] == event['project_id'] &&
          ((event['id'] != null && record['server_id'] == event['id']) ||
              (event['create_request_id'] != null &&
                  _creationKey(state, kind, record['local_id'], record) ==
                      event['create_request_id']))) {
        ids.add(record['local_id']);
        _markDeleted(state, kind, record['local_id'], record, pending: false);
      }
    }
    for (final marker in markers.values.toList()) {
      if (marker['project_id'] == event['project_id'] &&
          ((event['id'] != null && marker['server_id'] == event['id']) ||
              (event['create_request_id'] != null &&
                  marker['create_request_id'] == event['create_request_id'])))
        ids.add(marker['local_id']);
    }
    if (ids.isEmpty)
      ids.add('remote:${event['id'] ?? event['create_request_id']}');
    for (final id in ids) {
      final previous = markers[id] as Map?;
      if (previous == null ||
          previous['pending'] == true ||
          (event['id'] != null && previous['server_id'] != event['id']) ||
          (event['create_request_id'] != null &&
              previous['create_request_id'] != event['create_request_id'])) {
        state['deletion_generation'] =
            (state['deletion_generation'] as int? ?? 0) + 1;
      }
      markers[id] = {
        ...?previous,
        'local_id': id,
        'project_id': event['project_id'],
        'server_id': event['id'] ?? previous?['server_id'],
        'create_request_id':
            event['create_request_id'] ?? previous?['create_request_id'],
        'pending': false,
      };
      (state['${kind}_delete_outbox'] as List?)?.remove(id);
    }
  }

  Future<void> _refreshDeletions(int epoch, String project) async {
    _entryAccess(epoch, project);
    final response = await transport.call(
      '/api/projects/$project/plan-deletions',
    );
    _entryAccess(epoch, project);
    if (response is! List)
      throw const ApiException(0, 'Ungültige Löschliste vom Server.');
    final events = response
        .map((item) => _deletionEvent(item, project))
        .toList();
    await _change((state) {
      _entryAccess(epoch, project);
      state['deletions_supported'] = true;
      for (final event in events) _applyDeletion(state, event);
    });
    await _cleanupDeletedAssets(epoch);
  }

  Future<void> _acceptItemGone(int epoch, String kind, String localId) async {
    await _change((state) {
      final records =
          state[kind == 'plan' ? 'records' : 'imports'] as Map? ?? {};
      final marker = (state['${kind}_deletions'] as Map? ?? {})[localId];
      final record = records[localId];
      if (record == null && marker == null) return;
      _entryAccess(epoch, (record ?? marker)['project_id']);
      if (record != null)
        _markDeleted(state, kind, localId, record, pending: false);
      if (marker != null) marker['pending'] = false;
      (state['${kind}_delete_outbox'] as List?)?.remove(localId);
    });
    await _cleanupDeletedAssets(epoch);
  }

  Future<bool> _syncDeletions(int epoch, String? token) async {
    await _cleanupDeletedAssets(epoch);
    if (epoch != _epoch || !permitted) return false;
    if (!['owner', 'manager', 'technician'].contains(user['role'])) return true;
    for (final kind in ['plan', 'import']) {
      final ids = List<dynamic>.from(
        _state?['${kind}_delete_outbox'] as List? ?? [],
      );
      for (final localId in ids) {
        if (epoch != _epoch || !permitted || transport.token != token)
          return false;
        final marker = (_state?['${kind}_deletions'] as Map? ?? {})[localId];
        if (marker == null ||
            marker['pending'] != true ||
            !_allowed(marker['project_id']))
          continue;
        final project = marker['project_id'] as String;
        try {
          final body = <String, dynamic>{
            'request_id': marker['request_id'],
            if (marker['server_id'] != null) 'id': marker['server_id'],
            if (marker['create_request_id'] != null)
              'create_request_id': marker['create_request_id'],
          };
          final result = await transport.call(
            '/api/projects/$project/${kind == 'plan' ? 'plans' : 'plan-imports'}/delete',
            body,
          );
          _entryAccess(epoch, project);
          final event = _deletionEvent(result, project, kind: kind);
          if ((marker['server_id'] != null &&
                  event['id'] != marker['server_id']) ||
              (marker['create_request_id'] != null &&
                  event['create_request_id'] != marker['create_request_id'])) {
            throw const ApiException(
              0,
              'Löschbestätigung gehört zu einem anderen Plan.',
            );
          }
          await _change((state) {
            _entryAccess(epoch, project);
            state['deletions_supported'] = true;
            _applyDeletion(state, event);
          });
        } on ApiException catch (error) {
          if (epoch != _epoch) return false;
          notice = error.status == 404 && _state?['deletions_supported'] != true
              ? 'Löschung wartet auf das Server-Update.'
              : error.message;
          if (error.status == 401) {
            await lock();
            return false;
          }
          if (error.status == 403 ||
              (error.status == 404 && _state?['deletions_supported'] == true)) {
            await _change((state) {
              (state['projects'] as List).removeWhere(
                (item) => item['id'] == project,
              );
            });
          }
          if (error.status == 0 || error.status >= 500) return false;
        }
      }
    }
    return true;
  }

  Future<void> lock() async {
    if (active)
      await _change((state) {
        state['locked'] = true;
      });
  }

  Future<void> sync() async {
    if (_syncing || !permitted || transport.token == null) return;
    _syncing = true;
    final epoch = _epoch;
    final token = transport.token;
    changed();
    try {
      if (!await _syncDeletions(epoch, token)) return;
      if (_state?['deletions_supported'] == true) {
        for (final project
            in projects.map((item) => item['id'] as String).toList()) {
          try {
            await _refreshDeletions(epoch, project);
          } on ApiException catch (error) {
            if (epoch != _epoch) return;
            if (error.status == 401) {
              await lock();
              return;
            }
            if (error.status == 403 || error.status == 404) {
              await _change((state) {
                (state['projects'] as List).removeWhere(
                  (item) => item['id'] == project,
                );
              });
            } else {
              notice = error.message;
              return;
            }
          }
        }
      }
      final attempted = <String>{};
      while (epoch == _epoch &&
          permitted &&
          transport.token == token &&
          ['owner', 'manager', 'technician'].contains(user['role'])) {
        final eligible = (_state!['outbox'] as List).where(
          (op) =>
              !attempted.contains(op['local_id']) &&
              _allowed(op['project_id']) &&
              !_deleted('plan', localId: op['local_id']) &&
              _state!['records'][op['local_id']] != null &&
              ![
                'Konflikt',
                'Zugriff gesperrt',
                'Eingabe prüfen',
              ].contains(_state!['records'][op['local_id']]['sync_status']),
        );
        if (eligible.isEmpty) break;
        final localId = eligible.first['local_id'] as String;
        final operation = await _change<Map<String, dynamic>?>((state) {
          final matches = (state['outbox'] as List).where(
            (op) => op['local_id'] == localId,
          );
          if (matches.isEmpty ||
              _deleted('plan', localId: localId, state: state))
            return null;
          final op = matches.first;
          _entryAccess(epoch, op['project_id'], write: true);
          final record = state['records'][localId];
          if (op['body'] == null) {
            op['path'] =
                '/api/projects/${op['project_id']}/plans${record['server_id'] == null ? '' : '/${record['server_id']}'}';
            op['body'] = {
              ...op['snapshot'],
              'request_id': op['request_id'],
              if (record['server_id'] != null) 'revision': record['revision'],
            };
          }
          return offlineCopy(Map<String, dynamic>.from(op));
        });
        if (epoch != _epoch || transport.token != token) break;
        if (operation == null || _deleted('plan', localId: localId)) continue;
        try {
          final response = await transport.call(
            operation['path'],
            Map<String, dynamic>.from(operation['body']),
          );
          if (epoch != _epoch) break;
          await _change((state) {
            (state['outbox'] as List).removeWhere(
              (op) => op['request_id'] == operation['request_id'],
            );
            final record = state['records'][localId];
            if (_deleted('plan', localId: localId, state: state)) {
              final marker = state['plan_deletions'][localId];
              marker['server_id'] ??= response['id'];
              return;
            }
            _entryAccess(epoch, operation['project_id']);
            record['server_id'] = response['id'];
            record['revision'] = response['revision'];
            record['sync_status'] =
                (state['outbox'] as List).any((op) => op['local_id'] == localId)
                ? 'Wartet auf Verbindung'
                : 'Synchronisiert';
          });
          notice = null;
        } on ApiException catch (e) {
          if (epoch != _epoch) break;
          notice = e.message;
          if (e.status == 401) {
            await lock();
            break;
          }
          if (e.status == 410) {
            await _acceptItemGone(epoch, 'plan', localId);
            continue;
          }
          if (_deleted('plan', localId: localId)) continue;
          if (e.status == 0 || e.status >= 500) break;
          attempted.add(localId);
          Map<String, dynamic>? remote;
          if (e.status == 409 && operation['body']['revision'] != null) {
            try {
              remote = Map<String, dynamic>.from(
                await transport.call(operation['path']),
              );
            } on ApiException catch (conflict) {
              if (conflict.status == 410) {
                if (epoch != _epoch) break;
                await _acceptItemGone(epoch, 'plan', localId);
                continue;
              }
              /* Preserve both local draft and queued request. */
            }
          }
          if (epoch != _epoch) break;
          await _change((state) {
            if (_deleted('plan', localId: localId, state: state)) return;
            _entryAccess(epoch, operation['project_id']);
            final record = state['records'][localId];
            record['sync_status'] = e.status == 409
                ? 'Konflikt'
                : [403, 404].contains(e.status)
                ? 'Zugriff gesperrt'
                : 'Eingabe prüfen';
            if (remote != null) record['remote'] = remote;
            if ([403, 404].contains(e.status))
              (state['projects'] as List).removeWhere(
                (p) => p['id'] == operation['project_id'],
              );
          });
        }
      }
      if (epoch == _epoch && permitted && !await _syncDeletions(epoch, token))
        return;
      if (epoch == _epoch && transport.token == token && permitted) {
        await _syncImports(epoch, token);
      }
      if (epoch == _epoch && permitted) await _syncDeletions(epoch, token);
      if (epoch == _epoch && transport.token == token && permitted)
        await _syncWorkspace(epoch, token);
      final businessPending =
          (_state?['business_time_outbox'] as List? ?? []).isNotEmpty ||
          (_state?['business_media_outbox'] as List? ?? []).isNotEmpty;
      if (epoch == _epoch &&
          transport.token == token &&
          permitted &&
          businessPending &&
          await _businessWritesAvailable(epoch, token)) {
        await _syncBusinessTime(epoch, token);
        if (epoch == _epoch && transport.token == token && permitted)
          await _syncBusinessMedia(epoch, token);
      }
    } catch (e) {
      if (epoch == _epoch && active) {
        notice = 'Synchronisierung nicht abgeschlossen. Lokale Eingaben bleiben gespeichert. Bitte Speicherplatz und Verbindung prüfen.';
      }
    } finally {
      _syncing = false;
      changed();
    }
  }

  Future<void> resolve(String localId, {required bool keepCopy}) async {
    final epoch = _epoch;
    requireAccess();
    final entry = get(localId);
    if (!['owner', 'manager', 'technician'].contains(user['role']) ||
        !canAccessProject(entry['project_id']))
      throw const ApiException(403, 'Keine Schreibberechtigung.');
    await _change((state) {
      _entryAccess(epoch, entry['project_id'], write: true);
      if (_deleted('plan', localId: localId, state: state))
        throw const ApiException(410, 'Dieser Plan wurde gelöscht.');
      final record = state['records'][localId];
      final remote = record['remote'];
      if (remote == null)
        throw const ApiException(
          0,
          'Zuerst mit Verbindung den aktuellen Serverstand laden.',
        );
      (state['outbox'] as List).removeWhere((op) => op['local_id'] == localId);
      if (keepCopy) {
        final copyId = offlineId();
        final snapshot = {
          'title':
              '${record['title'].toString().substring(0, record['title'].toString().length.clamp(0, 180))} (lokale Kopie)',
          'walls': record['walls'],
        };
        state['records'][copyId] = {
          ...snapshot,
          'project_id': record['project_id'],
          'local_id': copyId,
          'sync_status': 'Wartet auf Verbindung',
        };
        (state['outbox'] as List).add({
          'local_id': copyId,
          'project_id': record['project_id'],
          'snapshot': snapshot,
          'request_id': offlineId(),
          'body': null,
        });
      }
      state['records'][localId] = {
        ...remote,
        'local_id': localId,
        'server_id': remote['id'],
        'sync_status': 'Synchronisiert',
      };
    });
    unawaited(sync());
  }

  @override
  void dispose() {
    _disposed = true;
    _timer?.cancel();
    if (ownsTransport) transport.dispose();
    super.dispose();
  }
}

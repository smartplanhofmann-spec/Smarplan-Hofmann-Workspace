import 'dart:async';
import 'dart:convert';

import 'package:flutter/foundation.dart';
import 'package:cryptography/cryptography.dart';

import 'api.dart';
import 'offline_vault.dart';
import 'offline_assets.dart';

part 'offline_imports.dart';

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
      (_state?['import_outbox'] as List? ?? []).length;
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
      final result = action(state);
      state['last_seen'] = clock().toUtc().toIso8601String();
      await _vault!.write(state);
      _state = state;
      changed();
      return result;
    });
    _tail = next.then<void>((_) {}, onError: (Object e, StackTrace s) {});
    return next;
  }

  Future<void> login(Map<String, dynamic> user, List<dynamic> projects) async {
    _epoch++;
    await _tail;
    _state = null;
    _vault = null;
    final vault = await device.open(server, user['id'], create: true);
    final grant = Map<String, dynamic>.from(
      await api.call('/api/offline/access', {}),
    );
    transport.token = grant['token'];
    await device.saveSession(server, user['id'], transport.token);
    final now = clock().toUtc().toIso8601String();
    final state =
        await vault.read() ?? <String, dynamic>{'records': {}, 'outbox': []};
    state.addAll({
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
    } catch (_) {
      _state = null;
      _vault = null;
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
        if (entry['project_id'] == project)
          offlineCopy(Map<String, dynamic>.from(entry)),
    ];
  }

  Map<String, dynamic> get(String localId) {
    requireAccess();
    final record = _state!['records'][localId];
    if (record == null || !_allowed(record['project_id']))
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
      final plans =
          await transport.call('/api/projects/$project/plans') as List;
      if (epoch != _epoch) return;
      await _change((state) {
        final records = state['records'] as Map;
        final downloaded = state['downloaded_projects'] ??= [];
        if (!(downloaded as List).contains(project)) downloaded.add(project);
        for (final remote in plans) {
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
      records[id] = record;
      return offlineCopy(record);
    });
    unawaited(sync());
    return result;
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
      final attempted = <String>{};
      while (epoch == _epoch &&
          permitted &&
          transport.token == token &&
          ['owner', 'manager', 'technician'].contains(user['role'])) {
        final eligible = (_state!['outbox'] as List).where(
          (op) =>
              !attempted.contains(op['local_id']) &&
              _allowed(op['project_id']) &&
              ![
                'Konflikt',
                'Zugriff gesperrt',
                'Eingabe prüfen',
              ].contains(_state!['records'][op['local_id']]['sync_status']),
        );
        if (eligible.isEmpty) break;
        final localId = eligible.first['local_id'] as String;
        final operation = await _change((state) {
          final op = (state['outbox'] as List).firstWhere(
            (op) => op['local_id'] == localId,
          );
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
          if (e.status == 0 || e.status >= 500) break;
          attempted.add(localId);
          Map<String, dynamic>? remote;
          if (e.status == 409 && operation['body']['revision'] != null) {
            try {
              remote = Map<String, dynamic>.from(
                await transport.call(operation['path']),
              );
            } on ApiException {
              /* Preserve both local draft and queued request. */
            }
          }
          if (epoch != _epoch) break;
          await _change((state) {
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
      if (epoch == _epoch && transport.token == token && permitted) {
        await _syncImports(epoch, token);
      }
    } catch (e) {
      notice = 'Synchronisierung nicht abgeschlossen. Lokale Eingaben bleiben gespeichert. Bitte Speicherplatz und Verbindung prüfen.';
    } finally {
      _syncing = false;
      changed();
    }
  }

  Future<void> resolve(String localId, {required bool keepCopy}) async {
    requireAccess();
    final entry = get(localId);
    if (!['owner', 'manager', 'technician'].contains(user['role']) ||
        !canAccessProject(entry['project_id']))
      throw const ApiException(403, 'Keine Schreibberechtigung.');
    await _change((state) {
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

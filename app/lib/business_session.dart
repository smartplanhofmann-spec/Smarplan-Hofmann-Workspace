import 'dart:convert';
import 'dart:async';

import 'package:flutter/foundation.dart';
import 'package:flutter/scheduler.dart';

import 'api.dart';
import 'offline_vault.dart' show offlineId;

Map<String, dynamic> businessMap(dynamic value) =>
    value is Map ? Map<String, dynamic>.from(value) : <String, dynamic>{};
List<Map<String, dynamic>> businessItems(dynamic value) {
  final items = value is Map ? value['items'] : value;
  if (items is! List)
    throw const ApiException(
      0,
      'Der Server hat keine gültige Liste geliefert.',
    );
  return items.map((value) {
    if (value is! Map)
      throw const ApiException(0, 'Ungültiger Eintrag vom Server.');
    return Map<String, dynamic>.from(value);
  }).toList();
}

/// One authenticated view. No business records or financial credentials enter
/// this controller's disk cache. Offline time uses the existing encrypted vault.
class BusinessSession extends ChangeNotifier {
  BusinessSession({
    required this.api,
    this.offlineMode = false,
    this.projectId,
    this.projects = const [],
    this.onDenied,
  }) : _token = api.token {
    api.addListener(_accessChanged);
  }
  final OfficeApi api;
  final bool offlineMode;
  final String? projectId;
  final VoidCallback? onDenied;
  Timer? _metaTimer;
  List<Map<String, dynamic>> projects;
  final String? _token;
  bool _disposed = false,
      ready = false,
      supported = false,
      denied = false,
      loading = false,
      readonly = false;
  int _epoch = 0;
  Object? generation;
  String? error;
  Set<String> permissions = {}, capabilities = {};
  final _pending =
      <
        String,
        ({
          String path,
          String values,
          Object? generation,
          Map<String, dynamic> body,
        })
      >{};
  bool get allowed =>
      !_disposed &&
      !denied &&
      !offlineMode &&
      api.version == 'v1' &&
      _token != null &&
      _token.isNotEmpty &&
      !_token.startsWith('offline_') &&
      api.token == _token;
  bool can(String permission) =>
      allowed && supported && permissions.contains(permission);
  bool canWrite(String permission) => !readonly && can(permission);
  bool hasModule(String module) =>
      allowed &&
      supported &&
      (capabilities.contains(module) ||
          capabilities.contains('business_$module'));
  bool pending(String key) => _pending.containsKey(key);

  void _changed() {
    if (_disposed) return;
    if (SchedulerBinding.instance.schedulerPhase ==
        SchedulerPhase.persistentCallbacks) {
      WidgetsBindingShim.afterFrame(() {
        if (!_disposed) notifyListeners();
      });
    } else {
      notifyListeners();
    }
  }

  void _accessChanged() {
    if (api.token != _token) revoke();
  }

  void revoke() {
    _epoch++;
    denied = true;
    supported = false;
    loading = false;
    permissions = {};
    capabilities = {};
    _pending.clear();
    _metaTimer?.cancel();
    error =
        'Der Zugang ist nicht mehr verfügbar. Bitte melden Sie sich erneut an.';
    _changed();
    onDenied?.call();
  }

  void _guard(int epoch) {
    if (!allowed || epoch != _epoch)
      throw const ApiException(401, 'Der Zugang ist nicht mehr verfügbar.');
  }

  Future<void> load() async {
    if (loading) return;
    if (!allowed) {
      ready = true;
      _changed();
      return;
    }
    final epoch = _epoch;
    loading = true;
    error = null;
    _changed();
    try {
      final meta = businessMap(
        await api.call(
          '/api/business/capabilities${projectId == null ? '' : '?${Uri(queryParameters: {'project_id': projectId}).query}'}',
        ),
      );
      _guard(epoch);
      if (meta['capabilities'] is! List || meta['permissions'] is! List) {
        throw const ApiException(
          0,
          'Die Fachbereiche konnten nicht sicher geladen werden.',
        );
      }
      final nextGeneration = meta['generation'];
      generation = nextGeneration;
      capabilities = (meta['capabilities'] as List).whereType<String>().toSet();
      permissions = (meta['permissions'] as List).whereType<String>().toSet();
      readonly = meta['readonly'] == true;
      supported =
          (meta['compatibility_mode'] == 'business' || readonly) &&
          capabilities.isNotEmpty;
      if (supported)
        _metaTimer ??= Timer.periodic(const Duration(seconds: 30), (_) {
          if (allowed && !loading) unawaited(load());
        });
    } on ApiException catch (e) {
      if (epoch != _epoch || _disposed) return;
      if (e.status == 401 || e.status == 403) {
        revoke();
        return;
      }
      if (e.status == 404) {
        supported = false;
        permissions = {};
        capabilities = {};
      } else {
        error = e.message;
      }
    } catch (_) {
      if (epoch == _epoch && !_disposed) error = 'Die zusätzlichen Fachbereiche konnten nicht geladen werden. Ihre Projektmappe bleibt verfügbar.';
    } finally {
      if (!_disposed && epoch == _epoch) {
        loading = false;
        ready = true;
        _changed();
      }
    }
  }

  String path(String path) => '/api/business$path';
  String query(String path, [Map<String, String> extra = const {}]) {
    final values = {if (projectId != null) 'project_id': projectId!, ...extra};
    return values.isEmpty
        ? path
        : '$path?${Uri(queryParameters: values).query}';
  }

  Future<dynamic> legacyRead(String path) async {
    final epoch = _epoch;
    _guard(epoch);
    final result = await api.call(path);
    _guard(epoch);
    return result;
  }

  Future<dynamic> read(String path) async {
    final epoch = _epoch;
    _guard(epoch);
    final capturedGeneration = generation;
    final result = await api.call(this.path(path));
    _guard(epoch);
    if (generation != capturedGeneration)
      throw const ApiException(
        409,
        'Der freigegebene Funktionsstand hat sich geändert. Bitte neu laden.',
      );
    return result;
  }

  Future<dynamic> command(
    String key,
    String path,
    Map<String, dynamic> values,
  ) async {
    final epoch = _epoch;
    _guard(epoch);
    if (readonly)
      throw const ApiException(
        403,
        'Der Rückkehrmodus erlaubt das Lesen und Exportieren. Änderungen bleiben bis zur erneuten Freigabe gesperrt.',
      );
    final canonical = jsonEncode(values);
    final previous = _pending[key];
    if (previous != null &&
        (previous.path != path ||
            previous.values != canonical ||
            previous.generation != generation)) {
      throw const ApiException(
        409,
        'Die letzte Übertragung ist noch unbestätigt. Bitte zuerst denselben Vorgang erneut senden.',
      );
    }
    final operation =
        previous ??
        (
          path: path,
          values: canonical,
          generation: generation,
          body: Map<String, dynamic>.from(jsonDecode(canonical))
            ..['request_id'] = offlineId(),
        );
    _pending[key] = operation;
    try {
      final result = await api.call(
        this.path(path),
        Map<String, dynamic>.from(operation.body),
      );
      _guard(epoch);
      if (generation != operation.generation)
        throw const ApiException(
          409,
          'Der Funktionsstand wurde geändert. Bitte den gespeicherten Stand prüfen, bevor Sie fortfahren.',
        );
      _pending.remove(key);
      return result;
    } on ApiException catch (e) {
      if (e.status != 0 && e.status < 500 && e.status != 429)
        _pending.remove(key);
      if (e.status == 401) revoke();
      rethrow;
    }
  }

  @override
  void dispose() {
    _disposed = true;
    _metaTimer?.cancel();
    _epoch++;
    api.removeListener(_accessChanged);
    _pending.clear();
    super.dispose();
  }
}

// SchedulerBinding works in tests and on all Flutter platforms without I/O.
abstract final class WidgetsBindingShim {
  static void afterFrame(VoidCallback callback) =>
      SchedulerBinding.instance.addPostFrameCallback((_) => callback());
}

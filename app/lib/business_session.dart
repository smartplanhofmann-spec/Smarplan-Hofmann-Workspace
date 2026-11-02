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

/// An early client hint only; the server checks the same module on every write.
String? organizationCommandSection(String path) {
  final route = path.split('?').first;
  final first = route.split('/').where((part) => part.isNotEmpty).firstOrNull;
  if (first == 'organization' ||
      first == 'settings' ||
      route == '/commercial/settings')
    return null;
  if (const {'employees', 'absences', 'shifts', 'time'}.contains(first)) {
    return 'personnel';
  }
  if (const {'resources', 'appointments', 'planning'}.contains(first)) {
    return 'planning';
  }
  if (first == 'inventory' ||
      first == 'purchasing' ||
      first == 'budgets' ||
      RegExp(r'^/projects/[a-f0-9]{32}/changes(?:/|$)').hasMatch(route)) {
    return 'material';
  }
  if (first == 'portal') return 'documents';
  if (const {
    'documents',
    'articles',
    'services',
    'templates',
    'text-blocks',
    'commercial',
  }.contains(first))
    return 'documents';
  if (first == 'finance' || first == 'accounting') return 'finance';
  if (RegExp(r'^/adapters/imports/[a-f0-9]{32}/(?:apply|offer)$')
      .hasMatch(route)) {
    return 'documents';
  }
  return null;
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
  Set<String> permissions = {}, capabilities = {}, features = {};
  Map<String, Map<String, bool>> organizationModules = {};
  static const organizationSections = {
    'personnel',
    'material',
    'planning',
    'documents',
    'finance',
  };
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
  bool hasFeature(String feature) =>
      allowed && supported && features.contains(feature);

  /// Company preferences change navigation and writing, never user authority.
  bool sectionVisible(String section) =>
      !hasFeature('organization_modules') ||
      !organizationSections.contains(section) ||
      organizationModules[section]?['visible'] == true;
  bool sectionEnabled(String section) =>
      !hasFeature('organization_modules') ||
      !organizationSections.contains(section) ||
      organizationModules[section]?['enabled'] == true;
  bool pending(String key) => _pending.containsKey(key);

  /// A detached copy of the exact unacknowledged input, held only in this
  /// authenticated session. Source/account versions must survive editor reopen.
  Map<String, dynamic>? pendingCommandValues(
    String key, {
    required String path,
  }) {
    final operation = _pending[key];
    if (!allowed || operation == null || operation.path != path) return null;
    return Map<String, dynamic>.from(jsonDecode(operation.values));
  }

  final _pendingEditorValues = <String, Map<String, dynamic>>{};
  Map<String, dynamic>? pendingEditorValues(String key) {
    final values = _pendingEditorValues[key];
    if (!allowed || !pending(key) || values == null) return null;
    return Map<String, dynamic>.from(jsonDecode(jsonEncode(values)));
  }

  void preservePendingEditor(String key, Map<String, dynamic> values) {
    if (allowed && pending(key)) {
      _pendingEditorValues[key] = Map<String, dynamic>.from(
        jsonDecode(jsonEncode(values)),
      );
    }
  }

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
    features = {};
    organizationModules = {};
    _pending.clear();
    _pendingEditorValues.clear();
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
      final nextFeatures = meta['features'] is List
          ? (meta['features'] as List).whereType<String>().toSet()
          : <String>{};
      final nextOrganization = <String, Map<String, bool>>{};
      if (nextFeatures.contains('organization_modules')) {
        final organization = businessMap(meta['organization']);
        if (organization['revision'] is! int ||
            (organization['revision'] as int) < 0 ||
            organization['configured'] is! bool) {
          throw const ApiException(
            0,
            'Die Unternehmenseinstellungen konnten nicht sicher geladen werden. Bitte neu laden.',
          );
        }
        final modules = businessMap(organization['modules']);
        for (final section in organizationSections) {
          final value = businessMap(modules[section]);
          if (value['visible'] is! bool || value['enabled'] is! bool) {
            throw const ApiException(
              0,
              'Die Unternehmenseinstellungen konnten nicht sicher geladen werden. Bitte neu laden.',
            );
          }
          nextOrganization[section] = {
            'visible': value['visible'] as bool,
            'enabled': value['enabled'] as bool,
          };
        }
      }
      final nextGeneration = meta['generation'];
      generation = nextGeneration;
      capabilities = (meta['capabilities'] as List).whereType<String>().toSet();
      features = nextFeatures;
      organizationModules = nextOrganization;
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
        features = {};
        organizationModules = {};
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
    final portalRevocation =
        hasFeature('offer_portal') &&
        RegExp(r'^/portal/grants/[a-f0-9]{32}/revoke$').hasMatch(path);
    if (readonly && !portalRevocation)
      throw const ApiException(
        403,
        'Der Rückkehrmodus erlaubt das Lesen und Exportieren. Änderungen bleiben bis zur erneuten Freigabe gesperrt.',
      );
    final section = organizationCommandSection(path);
    if (section != null &&
        !sectionEnabled(section) &&
        !portalRevocation &&
        !_pending.containsKey(key)) {
      throw const ApiException(
        423,
        'Dieser Bereich ist fachlich deaktiviert. Vorhandene Daten bleiben '
        'lesbar; Änderungen benötigen die Aktivierung in den Unternehmenseinstellungen.',
      );
    }
    final canonical = jsonEncode(values);
    final previous = _pending[key];
    if (previous != null &&
        (previous.path != path ||
            previous.values != canonical ||
            (!portalRevocation && previous.generation != generation))) {
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
      if (!portalRevocation && generation != operation.generation)
        throw const ApiException(
          409,
          'Der Funktionsstand wurde geändert. Bitte den gespeicherten Stand prüfen, bevor Sie fortfahren.',
        );
      _pending.remove(key);
      _pendingEditorValues.remove(key);
      if (hasFeature('organization_modules') &&
          RegExp(r'^/employees(?:/[a-f0-9]{32})?$').hasMatch(path)) {
        await load();
      }
      return result;
    } on ApiException catch (e) {
      if (e.status != 0 &&
          e.status < 500 &&
          e.status != 429 &&
          e.status != 423) {
        _pending.remove(key);
        _pendingEditorValues.remove(key);
      }
      if (e.status == 401) revoke();
      rethrow;
    }
  }

  /// This exact POST computes a proposal without creating a command receipt.
  /// It still needs the normal write-mode and finance authorization gates.
  Future<dynamic> previewPaymentAllocation(
    String paymentId,
    Map<String, dynamic> values,
  ) async {
    final epoch = _epoch;
    _guard(epoch);
    if (!RegExp(r'^[a-f0-9]{32}$').hasMatch(paymentId) ||
        projectId != null ||
        !hasFeature('accounting_payment_allocation') ||
        !hasModule('accounting_allocations') ||
        !can('accounting.read') ||
        !can('finance.read') ||
        !canWrite('accounting.prepare') ||
        !canWrite('finance.write')) {
      throw const ApiException(
        403,
        'Die Zahlungszuordnung ist nicht freigegeben.',
      );
    }
    if (!sectionEnabled('finance')) {
      throw const ApiException(423, 'Finanzen ist fachlich deaktiviert.');
    }
    final capturedGeneration = generation;
    try {
      final result = await api.call(
        path('/accounting/allocations/payments/$paymentId/preview'),
        Map<String, dynamic>.from(jsonDecode(jsonEncode(values))),
      );
      _guard(epoch);
      if (generation != capturedGeneration) {
        throw const ApiException(
          409,
          'Der Funktionsstand wurde geändert. Bitte neu prüfen.',
        );
      }
      return result;
    } on ApiException catch (e) {
      if (e.status == 401) revoke();
      rethrow;
    }
  }

  /// Computes documentary amounts only, without a request receipt or queue.
  Future<dynamic> previewDocumentComponents(
    String eventId,
    Map<String, dynamic> values,
  ) async {
    final epoch = _epoch;
    _guard(epoch);
    if (!RegExp(r'^[a-f0-9]{32}$').hasMatch(eventId) ||
        projectId != null ||
        !hasFeature('accounting_document_components') ||
        !hasModule('accounting_components') ||
        !can('accounting.read') ||
        !can('finance.read') ||
        !canWrite('accounting.prepare') ||
        !canWrite('finance.write')) {
      throw const ApiException(
        403,
        'Die dokumentarische Belegaufteilung ist nicht freigegeben.',
      );
    }
    if (!sectionEnabled('finance')) {
      throw const ApiException(423, 'Finanzen ist fachlich deaktiviert.');
    }
    final capturedGeneration = generation;
    try {
      final result = await api.call(
        path('/accounting/components/events/$eventId/preview'),
        Map<String, dynamic>.from(jsonDecode(jsonEncode(values))),
      );
      _guard(epoch);
      if (generation != capturedGeneration) {
        throw const ApiException(
          409,
          'Der Funktionsstand wurde geändert. Bitte neu prüfen.',
        );
      }
      return result;
    } on ApiException catch (e) {
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
    _pendingEditorValues.clear();
    super.dispose();
  }
}

// SchedulerBinding works in tests and on all Flutter platforms without I/O.
abstract final class WidgetsBindingShim {
  static void afterFrame(VoidCallback callback) =>
      SchedulerBinding.instance.addPostFrameCallback((_) => callback());
}

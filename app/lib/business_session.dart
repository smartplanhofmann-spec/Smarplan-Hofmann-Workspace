import 'dart:convert';
import 'dart:async';

import 'package:flutter/foundation.dart';
import 'package:flutter/scheduler.dart';

import 'api.dart';
import 'business_company_event_contract.dart';
import 'offline_vault.dart' show offlineId;

/// A failed response belongs to one exact command, even if its UI key is reused.
class BusinessCommandException extends ApiException {
  final BusinessSession owner;
  final String key, requestId;
  BusinessCommandException(
    this.owner,
    this.key,
    this.requestId,
    ApiException error,
  ) : super(
        error.status,
        error.message,
        requestResolution: error.requestResolution,
      );
}

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

bool _catalogCommand(String key, String path) {
  final match = RegExp(r'^catalog-(import|apply)-([a-f0-9]{32})$')
      .firstMatch(key);
  if (match == null) return false;
  return path ==
      (match.group(1) == 'import'
          ? '/adapters/${match.group(2)}/import'
          : '/adapters/imports/${match.group(2)}/apply');
}

bool _catalogPricesCommand(String key, String path) {
  if (key == 'catalog-v2-source') return path == '/catalog-prices/sources';
  final match = RegExp(r'^catalog-v2-(import|apply|withdraw)-([a-f0-9]{32})$')
      .firstMatch(key);
  if (match == null) return false;
  final id = match.group(2);
  return path ==
      switch (match.group(1)) {
        'import' => '/catalog-prices/sources/$id/imports',
        'apply' => '/catalog-prices/imports/$id/apply',
        _ => '/catalog-prices/prices/$id/withdraw',
      };
}

bool _datedCatalogConsumer(
  String key,
  String path,
  Map<String, dynamic> values,
) {
  bool bound(dynamic raw) {
    if (raw is! Map) return false;
    if (raw['catalog_price_selection'] is Map ||
        raw['catalog_price_snapshot'] is Map)
      return true;
    final pricing = raw['pricing'];
    return pricing is Map &&
        (pricing['source_price_selection'] is Map ||
            (pricing['components'] is List &&
                (pricing['components'] as List).any(
                  (part) => part is Map && part['price_selection'] is Map,
                )));
  }

  final document =
      RegExp(r'^catalog-v2-document-[a-f0-9]{32}$').hasMatch(key) &&
      RegExp(r'^/documents(?:/[a-f0-9]{32})?$').hasMatch(path) &&
      values['positions'] is List &&
      (values['positions'] as List).any(bound);
  final order =
      (RegExp(
            r'^purchase-proposal-(?:all|[a-f0-9]{32})-(?:new|[a-f0-9]{32})-[0-9]+-[0-9]+$',
          ).hasMatch(key) ||
          RegExp(r'^purchase-approve-[a-f0-9]{32}-[0-9]+$').hasMatch(key)) &&
      RegExp(r'^/inventory/orders(?:/[a-f0-9]{32})?$').hasMatch(path) &&
      values['items'] is List &&
      (values['items'] as List).any(bound);
  return document || order;
}

bool _companyEventCommand(
  String key,
  String path,
  Map<String, dynamic> values,
) {
  try {
    return key == companyEventCommandKey(path, values);
  } on ApiException {
    return false;
  }
}

/// An early client hint only; the server checks the same module on every write.
String? organizationCommandSection(String path) {
  final route = path.split('?').first;
  final first = route.split('/').where((part) => part.isNotEmpty).firstOrNull;
  if (first == 'catalog-prices') return 'documents';
  if (first == 'organization' ||
      first == 'settings' ||
      route == '/commercial/settings')
    return null;
  if (const {
    'employees',
    'absences',
    'shifts',
    'time',
    'personnel',
    'payroll',
  }.contains(first)) {
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
  if (first == 'customer-workspace') {
    if (RegExp(r'^/customer-workspace/(?:grants|files)/[a-f0-9]{32}/revoke$')
        .hasMatch(route))
      return null;
    return 'documents';
  }
  if (const {
    'documents',
    'articles',
    'services',
    'templates',
    'text-blocks',
    'commercial',
  }.contains(first))
    return 'documents';
  if (first == 'finance' ||
      first == 'bank' ||
      first == 'accounting' ||
      first == 'receipt-media' ||
      first == 'project-economics')
    return 'finance';
  if (route == '/assets/from-delivery' ||
      RegExp(r'^/assets/[a-f0-9]{32}/origin$').hasMatch(route)) {
    return 'material';
  }
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
  final _projectSessions = <String, BusinessSession>{};
  BusinessSession? _globalOwner;
  BusinessSession? _ownedGlobalSession;

  /// Global administration always loads its own global grants. A project-only
  /// view may open this session, but it never transfers project permissions.
  BusinessSession sharedGlobalSession() {
    _guard(_epoch);
    if (projectId == null) return this;
    if (_globalOwner != null) return _globalOwner!.sharedGlobalSession();
    final global = _ownedGlobalSession ??= BusinessSession(
      api: api,
      offlineMode: offlineMode,
      projects: projects,
    );
    global.projects = projects;
    return global;
  }

  /// Parent-owned, memory-only sessions keep an unacknowledged project command
  /// while the user follows a source from the company journal and returns.
  /// Every child loads its own project permissions; it inherits no grants.
  BusinessSession sharedProjectSession(String id) {
    _guard(_epoch);
    if (!RegExp(r'^[a-f0-9]{32}$').hasMatch(id) ||
        (projectId != null && projectId != id)) {
      throw const ApiException(
        403,
        'Dieses Projekt ist in der aktuellen Ansicht nicht verfügbar.',
      );
    }
    if (projectId == id) return this;
    final child = _projectSessions.putIfAbsent(
      id,
      () => BusinessSession(
        api: api,
        offlineMode: offlineMode,
        projectId: id,
        projects: projects,
      ),
    );
    child._globalOwner = this;
    child.projects = projects;
    return child;
  }

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
          void Function(dynamic)? validateResult,
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

  /// Only the closed company-event endpoints preserve their original request.
  List<({String key, String path})> get pendingCompanyEventCommands => !allowed
      ? const []
      : List.unmodifiable(
          _pending.entries
              .where(
                (e) => _companyEventCommand(e.key, e.value.path, e.value.body),
              )
              .map((e) => (key: e.key, path: e.value.path)),
        );

  void _requireCompanyEventRights({bool manage = false, bool write = false}) {
    if (projectId != null ||
        !hasFeature('company_event_rules') ||
        !hasModule('company_events') ||
        !can('assistant.use') ||
        manage && !can('settings.manage') ||
        write && !canWrite('assistant.use')) {
      throw const ApiException(
        403,
        'Aktuelle Rechte für Unternehmensereignisse fehlen.',
      );
    }
  }

  /// Recheck every disclosed original after a held response, including embedded
  /// historical project-policy evidence. No global grant substitutes a project grant.
  Future<Set<String>> authorizeCompanyEventData(dynamic raw) async {
    final epoch = _epoch, capturedGeneration = generation;
    _guard(epoch);
    _requireCompanyEventRights();
    final required = <String, Set<String>>{};
    var ownerRequired = false, globalFinance = false;
    void add(String project, String permission) {
      if (!RegExp(r'^[a-f0-9]{32}$').hasMatch(project)) {
        throw const ApiException(0, 'Ungültige Projektquelle.');
      }
      required.putIfAbsent(project, () => <String>{}).add(permission);
    }

    void source(String project, Map<String, dynamic> item) {
      final kind = item['descriptor']?['kind'];
      if (['project', 'task'].contains(kind)) {
        add(project, 'documents.read');
      } else if ([
        'open_item',
        'costs',
        'document',
        'dunning',
        'article',
      ].contains(kind)) {
        add(project, 'finance.read');
        if (kind == 'article') globalFinance = true;
      } else if (kind == 'communication') {
        add(project, 'assistant.use');
        ownerRequired = true;
      } else {
        throw const ApiException(0, 'Unbekannte Unternehmensereignisquelle.');
      }
    }

    Future<void> inspect(Map<String, dynamic> item) async {
      if (item['project_id'] is String && item['source'] is Map) {
        source(item['project_id'], companyEventMap(item['source']));
      } else if (item['project_id'] is String && item['context'] is Map) {
        for (final row in businessItems(item['context']['sources'])) {
          source(item['project_id'], row);
        }
        for (final rule in businessItems(item['policy']['project_policies'])) {
          for (final evidence in businessItems(
            rule['policy']['evidence'] ?? [],
          )) {
            if (evidence['permission'] is! String) {
              throw const ApiException(0, 'Ungültiger Projektregelnachweis.');
            }
            add(item['project_id'], evidence['permission']);
          }
        }
      } else if (item['items'] is List) {
        for (final row in businessItems(item['items'])) {
          if (row['event_id'] is String && row['plan_ids'] is List) {
            final event = companyEventObservation(
              await read('$companyEventBase/events/${row['event_id']}'),
            );
            _guard(epoch);
            await inspect(event);
          } else {
            await inspect(row);
          }
        }
      }
    }

    await inspect(companyEventMap(raw));
    for (final entry in required.entries) {
      final scope = sharedProjectSession(entry.key);
      await scope.load();
      _guard(epoch);
      _requireCompanyEventRights();
      if (scope.error != null ||
          scope.loading ||
          !scope.hasFeature('company_event_rules') ||
          !scope.hasModule('company_events') ||
          !scope.can('assistant.use') ||
          !entry.value.every(scope.can)) {
        throw const ApiException(
          403,
          'Die aktuellen Projekt- und Originalquellenrechte fehlen.',
        );
      }
    }
    if (globalFinance) {
      await load();
      _guard(epoch);
      if (error != null || loading || !can('finance.read')) {
        throw const ApiException(
          403,
          'Aktuelle Leserechte für Artikelquellen fehlen.',
        );
      }
    }
    if (ownerRequired) {
      final actor = businessMap(await legacyRead('/api/me'));
      if (actor['role'] != 'owner') {
        throw const ApiException(
          403,
          'Aktuelle Berechtigung für Anfrageoriginale fehlt.',
        );
      }
    }
    _guard(epoch);
    _requireCompanyEventRights();
    for (final entry in required.entries) {
      final scope = sharedProjectSession(entry.key);
      if (!scope.can('assistant.use') ||
          !scope.hasFeature('company_event_rules') ||
          !scope.hasModule('company_events') ||
          !entry.value.every(scope.can)) {
        throw const ApiException(
          403,
          'Die Originalquellenrechte wurden während der Prüfung entzogen.',
        );
      }
    }
    if (generation != capturedGeneration) {
      throw const ApiException(
        0,
        'Der freigegebene Funktionsstand hat sich geändert.',
      );
    }
    return required.keys.toSet();
  }

  Future<void> _authorizeCompanyEventCommand(
    String path,
    Map<String, dynamic> values,
  ) async {
    final epoch = _epoch;
    _guard(epoch);
    final operation = companyEventOperation(path);
    await load();
    _guard(epoch);
    if (error != null || loading) {
      throw const ApiException(
        0,
        'Aktuelle Unternehmensrechte konnten nicht geprüft werden.',
      );
    }
    _requireCompanyEventRights(
      manage: operation == 'rule' || operation == 'scan',
      write: true,
    );
    if (operation == 'rule' || operation == 'scan') return;
    final capturedGeneration = generation;
    final plan = companyEventPlan(
      await read('$companyEventBase/plans/${operation.split(':')[1]}'),
    );
    if (plan['sha256'] != values['plan_sha256']) {
      throw const ApiException(
        409,
        'Der Auftrag gehört zu einer anderen Planfassung.',
      );
    }
    await authorizeCompanyEventData(plan);
    final scope = sharedProjectSession(plan['project_id']);
    final needed = plan['action'] == 'task.create'
        ? ['projects.manage']
        : plan['action'] == 'offer.draft'
        ? ['finance.read', 'finance.write']
        : ['finance.read', 'finance.approve'];
    if (!scope.canWrite('assistant.use') ||
        !needed.every(scope.canWrite) ||
        (!operation.startsWith('execute:') &&
            !scope.canWrite('assistant.approve')) ||
        plan['action'] != 'task.create' &&
            (!scope.sectionEnabled('finance') ||
                !scope.sectionEnabled('documents'))) {
      throw const ApiException(
        403,
        'Aktuelle Fach-, Modul- oder Freigaberechte fehlen. Der Originalauftrag bleibt erhalten.',
      );
    }
    final actor = businessMap(await legacyRead('/api/me'));
    _guard(epoch);
    _requireCompanyEventRights(write: true);
    if (generation != capturedGeneration) {
      throw const ApiException(
        0,
        'Der Funktionsstand hat sich während der Ereignisprüfung geändert.',
      );
    }
    if (!scope.canWrite('assistant.use') ||
        !needed.every(scope.canWrite) ||
        (!operation.startsWith('execute:') &&
            !scope.canWrite('assistant.approve')) ||
        plan['action'] != 'task.create' &&
            (!scope.sectionEnabled('finance') ||
                !scope.sectionEnabled('documents'))) {
      throw const ApiException(
        403,
        'Die Fachrechte wurden während der Zuständigkeitsprüfung entzogen.',
      );
    }
    if (actor['id'] != plan['policy']['responsible_id']) {
      throw const ApiException(
        403,
        'Nur die aktuell zuständige Person darf diesen Auftrag bestätigen.',
      );
    }
  }

  final _companyEventFlights =
      <String, ({String path, String values, Future<dynamic> future})>{};

  Future<dynamic> companyEventCommand(
    String path,
    Map<String, dynamic> values, {
    bool Function()? stillCurrent,
  }) {
    final copied = companyEventMap(jsonDecode(jsonEncode(values)));
    final key = companyEventCommandKey(path, copied),
        serialized = companyEventCanonical(copied);
    final flight = _companyEventFlights[key];
    if (flight != null) {
      if (flight.path != path || flight.values != serialized) {
        throw const ApiException(
          409,
          'Der ursprüngliche Ereignisauftrag wird noch übertragen.',
        );
      }
      return flight.future;
    }
    final original = _pending[key];
    Future<dynamic> send() async {
      if (stillCurrent != null && !stillCurrent()) {
        throw const ApiException(
          0,
          'Die Ereigniserfassung wurde bereits geschlossen.',
        );
      }
      await _authorizeCompanyEventCommand(path, copied);
      if (stillCurrent != null && !stillCurrent()) {
        throw const ApiException(
          0,
          'Die Ereigniserfassung wurde während der Rechteprüfung geschlossen.',
        );
      }
      if (original != null &&
          _pending[key]?.body['request_id'] != original.body['request_id']) {
        throw const ApiException(
          0,
          'Der frühere Ereignisauftrag wurde inzwischen beantwortet.',
        );
      }
      return _command(
        key,
        path,
        copied,
        documentaryRetry: original != null,
        validateResult: (raw) {
          final exact = _pending[key];
          if (exact == null || exact.path != path) {
            throw const ApiException(
              0,
              'Die ursprüngliche Ereignisübertragung ist nicht mehr verfügbar.',
            );
          }
          companyEventReceipt(path, exact.body, raw);
        },
      );
    }

    late final Future<dynamic> future;
    future = send().whenComplete(() {
      if (identical(_companyEventFlights[key]?.future, future))
        _companyEventFlights.remove(key);
    });
    _companyEventFlights[key] = (
      path: path,
      values: serialized,
      future: future,
    );
    return future;
  }

  Future<dynamic> repeatCompanyEventCommand(
    String key, {
    bool Function()? stillCurrent,
  }) {
    final stored = _pending[key];
    if (stored == null ||
        !_companyEventCommand(key, stored.path, stored.body)) {
      throw const ApiException(
        409,
        'Kein unveränderter offener Unternehmensereignisauftrag verfügbar.',
      );
    }
    return companyEventCommand(
      stored.path,
      companyEventMap(jsonDecode(stored.values)),
      stillCurrent: stillCurrent,
    );
  }

  /// Only opaque command keys, never private bank bodies. Navigation must not
  /// allocate a new nonce for an existing uncertain import or reconciliation.
  List<String> get pendingBankKeys => !allowed
      ? const []
      : List.unmodifiable(
          _pending.entries
              .where(
                (entry) =>
                    entry.key.startsWith('bank-') &&
                    entry.value.path.startsWith('/bank/'),
              )
              .map((entry) => entry.key),
        );

  List<String> get pendingOpeningKeys => !allowed
      ? const []
      : List.unmodifiable(
          _pending.entries
              .where(
                (entry) =>
                    entry.key.startsWith('accounting-opening-') &&
                    const [
                      '/accounting/opening-balances/originals',
                      '/accounting/opening-balances/confirm',
                    ].contains(entry.value.path),
              )
              .map((entry) => entry.key),
        );

  void _requireOpeningRights() {
    if (projectId != null ||
        !hasFeature('accounting_opening_balances') ||
        !hasModule('accounting_openings') ||
        !['accounting.read', 'finance.read', 'bank.read'].every(can) ||
        ![
          'accounting.admin',
          'accounting.prepare',
          'finance.write',
        ].every(canWrite)) {
      throw const ApiException(
        403,
        'Aktuelle globale Rechte für Anfangsbestände fehlen.',
      );
    }
    if (!sectionEnabled('finance'))
      throw const ApiException(423, 'Finanzen ist fachlich deaktiviert.');
  }

  Future<dynamic> repeatOpeningCommand(String key) => _repeatWorkflowCommand(
    key,
    matches: (path) =>
        key.startsWith('accounting-opening-') &&
        const [
          '/accounting/opening-balances/originals',
          '/accounting/opening-balances/confirm',
        ].contains(path),
    requireRights: _requireOpeningRights,
    readPath: '/accounting/opening-balances',
    verifyState: (state) {
      if (state['schema_version'] != 1 ||
          state['rule_version'] != 'account_opening_balances_v1' ||
          state['can_prepare'] != true) {
        throw const ApiException(
          423,
          'Anfangsbestände sind derzeit nicht zur Bearbeitung freigegeben.',
        );
      }
      // Do not replace the original account/profile revisions or nonce. The
      // server checks the saved receipt before evaluating a new journal effect.
    },
  );

  Future<dynamic> previewOpeningBalance(Map<String, dynamic> values) async {
    final epoch = _epoch;
    _guard(epoch);
    _requireOpeningRights();
    final capturedGeneration = generation;
    try {
      final result = await api.call(
        path('/accounting/opening-balances/preview'),
        Map<String, dynamic>.from(jsonDecode(jsonEncode(values))),
      );
      _guard(epoch);
      _requireOpeningRights();
      if (generation != capturedGeneration)
        throw const ApiException(
          409,
          'Der Funktionsstand wurde geändert. Bitte neu prüfen.',
        );
      return result;
    } on ApiException catch (error) {
      if (error.status == 401) revoke();
      rethrow;
    }
  }

  List<String> get pendingOpenItemKeys => !allowed
      ? const []
      : List.unmodifiable(
          _pending.entries
              .where(
                (entry) =>
                    entry.key.startsWith('opening-item-') &&
                    const [
                      '/accounting/open-items/originals',
                      '/accounting/open-items/confirm',
                    ].contains(entry.value.path),
              )
              .map((entry) => entry.key),
        );

  void _requireOpenItemRights() {
    if (projectId != null ||
        !hasFeature('accounting_open_items') ||
        !hasModule('accounting_open_items') ||
        !['accounting.read', 'finance.read'].every(can) ||
        ![
          'accounting.admin',
          'accounting.prepare',
          'finance.write',
        ].every(canWrite)) {
      throw const ApiException(
        403,
        'Aktuelle globale Rechte für historische offene Posten fehlen.',
      );
    }
    if (!sectionEnabled('finance'))
      throw const ApiException(423, 'Finanzen ist fachlich deaktiviert.');
  }

  Future<dynamic> repeatOpenItemCommand(
    String key, {
    bool Function()? stillCurrent,
  }) => _repeatWorkflowCommand(
    key,
    matches: (path) =>
        key.startsWith('opening-item-') &&
        const [
          '/accounting/open-items/originals',
          '/accounting/open-items/confirm',
        ].contains(path),
    requireRights: () {
      _requireOpenItemRights();
      if (stillCurrent != null && !stillCurrent())
        throw const ApiException(
          0,
          "Der Altpostenkontext wurde geschlossen. Der Originalauftrag bleibt offen.",
        );
    },
    readPath: '/accounting/open-items',
    verifyState: (state) {
      if (state['schema_version'] != 1 ||
          state['rule_version'] != 'de_euer_ist_open_items_v1' ||
          state['can_prepare'] != true) {
        throw const ApiException(
          423,
          'historische offene Posten sind derzeit nicht zur Bearbeitung freigegeben.',
        );
      }
      // Do not replace the original asset/profile revisions or nonce. The
      // server checks the saved receipt before evaluating a new journal effect.
    },
  );

  Future<dynamic> previewOpenItem(Map<String, dynamic> values) async {
    final epoch = _epoch;
    _guard(epoch);
    _requireOpenItemRights();
    final capturedGeneration = generation;
    try {
      final result = await api.call(
        path('/accounting/open-items/preview'),
        Map<String, dynamic>.from(jsonDecode(jsonEncode(values))),
      );
      _guard(epoch);
      _requireOpenItemRights();
      if (generation != capturedGeneration)
        throw const ApiException(
          409,
          'Der Funktionsstand wurde geändert. Bitte neu prüfen.',
        );
      return result;
    } on ApiException catch (error) {
      if (error.status == 401) revoke();
      rethrow;
    }
  }

  List<String> get pendingYearValuesKeys => !allowed
      ? const []
      : List.unmodifiable(
          _pending.entries
              .where(
                (e) =>
                    e.key.startsWith('accounting-year-values-') &&
                    const [
                      '/accounting/year-values/originals',
                      '/accounting/year-values/confirm',
                    ].contains(e.value.path),
              )
              .map((e) => e.key),
        );

  void _requireYearValuesRights() {
    if (projectId != null ||
        !hasFeature('accounting_year_values') ||
        !hasModule('accounting_year_openings') ||
        !['accounting.read', 'finance.read'].every(can) ||
        ![
          'accounting.admin',
          'accounting.prepare',
          'finance.write',
        ].every(canWrite)) {
      throw const ApiException(
        403,
        'Aktuelle globale Rechte für Jahresvorträge fehlen.',
      );
    }
    if (!sectionEnabled('finance'))
      throw const ApiException(423, 'Finanzen ist fachlich deaktiviert.');
  }

  Future<dynamic> yearValuesCommand(
    String key,
    String commandPath,
    Map<String, dynamic> values, {
    void Function(dynamic)? validateResult,
    bool Function()? stillCurrent,
    bool retry = false,
  }) async {
    final epoch = _epoch, originalGeneration = generation;
    void check() {
      _guard(epoch);
      _requireYearValuesRights();
      if (generation != originalGeneration || stillCurrent?.call() == false)
        throw const ApiException(
          409,
          'Der Jahresvortragskontext wurde geändert. Bitte neu laden.',
        );
    }

    if (!RegExp(r'^accounting-year-values-(original|confirm)-20[0-9]{2}$')
            .hasMatch(key) ||
        !const [
          '/accounting/year-values/originals',
          '/accounting/year-values/confirm',
        ].contains(commandPath) ||
        key !=
            'accounting-year-values-${commandPath.endsWith('/originals') ? 'original' : 'confirm'}-${values['entity_key']}')
      throw const ApiException(
        409,
        'Der ursprüngliche Jahresauftrag ist nicht eindeutig gebunden.',
      );
    check();
    await load();
    check();
    if (error != null || loading)
      throw const ApiException(
        0,
        'Aktuelle Jahresvortragsrechte konnten nicht bestätigt werden.',
      );
    final state = businessMap(await read('/accounting/year-values'));
    check();
    // A historical void retains the accepted source's original profile. The
    // current profile only gates creation of new active sources and originals;
    // current rights, module gates and the server's original binding still apply.
    final historicalVoid =
        commandPath == '/accounting/year-values/confirm' &&
        values['operation'] == 'year_values' &&
        businessMap(values['payload'])['status'] == 'void';
    if (state['schema_version'] != 1 ||
        state['rule_version'] != 'de_euer_same_year_carryover_v1' ||
        (!retry && !historicalVoid && state['can_prepare'] != true))
      throw const ApiException(
        423,
        'Jahresvorträge sind aktuell nicht zur Bearbeitung freigegeben.',
      );
    await load();
    check();
    if (error != null || loading)
      throw const ApiException(
        0,
        'Aktuelle Jahresvortragsrechte konnten nicht bestätigt werden.',
      );
    return _command(
      key,
      commandPath,
      values,
      validateResult: validateResult,
      documentaryRetry: retry,
    );
  }

  Future<dynamic> repeatYearValuesCommand(
    String key, {
    bool Function()? stillCurrent,
  }) async {
    final saved = _pending[key];
    if (saved == null)
      throw const ApiException(409, 'Der ursprüngliche Jahresauftrag fehlt.');
    return yearValuesCommand(
      key,
      saved.path,
      Map<String, dynamic>.from(jsonDecode(saved.values)),
      retry: true,
      stillCurrent: () =>
          _pending[key]?.body['request_id'] == saved.body['request_id'] &&
          (stillCurrent?.call() ?? true),
    );
  }

  List<String> get pendingHistoricalAssetKeys => !allowed
      ? const []
      : List.unmodifiable(
          _pending.entries
              .where(
                (entry) =>
                    entry.key.startsWith('historical-asset-') &&
                    const [
                      '/accounting/historical-assets/originals',
                      '/accounting/historical-assets/confirm',
                    ].contains(entry.value.path),
              )
              .map((entry) => entry.key),
        );

  void _requireHistoricalAssetRights() {
    if (projectId != null ||
        !hasFeature('accounting_historical_assets') ||
        !hasModule('accounting_asset_openings') ||
        !['accounting.read', 'finance.read'].every(can) ||
        ![
          'accounting.admin',
          'accounting.prepare',
          'finance.write',
        ].every(canWrite)) {
      throw const ApiException(
        403,
        'Aktuelle globale Rechte für historische Anlagen fehlen.',
      );
    }
    if (!sectionEnabled('finance'))
      throw const ApiException(423, 'Finanzen ist fachlich deaktiviert.');
  }

  Future<dynamic> repeatHistoricalAssetCommand(
    String key,
  ) => _repeatWorkflowCommand(
    key,
    matches: (path) =>
        key.startsWith('historical-asset-') &&
        const [
          '/accounting/historical-assets/originals',
          '/accounting/historical-assets/confirm',
        ].contains(path),
    requireRights: _requireHistoricalAssetRights,
    readPath: '/accounting/historical-assets',
    verifyState: (state) {
      if (state['schema_version'] != 1 ||
          state['rule_version'] != 'de_historical_linear_assets_v1' ||
          state['can_prepare'] != true) {
        throw const ApiException(
          423,
          'historische Anlagen sind derzeit nicht zur Bearbeitung freigegeben.',
        );
      }
      // Do not replace the original asset/profile revisions or nonce. The
      // server checks the saved receipt before evaluating a new journal effect.
    },
  );

  Future<dynamic> previewHistoricalAsset(Map<String, dynamic> values) async {
    final epoch = _epoch;
    _guard(epoch);
    _requireHistoricalAssetRights();
    final capturedGeneration = generation;
    try {
      final result = await api.call(
        path('/accounting/historical-assets/preview'),
        Map<String, dynamic>.from(jsonDecode(jsonEncode(values))),
      );
      _guard(epoch);
      _requireHistoricalAssetRights();
      if (generation != capturedGeneration)
        throw const ApiException(
          409,
          'Der Funktionsstand wurde geändert. Bitte neu prüfen.',
        );
      return result;
    } on ApiException catch (error) {
      if (error.status == 401) revoke();
      rethrow;
    }
  }

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

  /// Each documentary operation keeps one logical key across its two writers.
  /// Its original path remains fixed until the server resolves the request.
  String? pendingDocumentComponentPath(String eventId) =>
      _pendingAccountingPath(eventId, 'components');
  String? pendingRefundOriginPath(String eventId) =>
      _pendingAccountingPath(eventId, 'refunds');

  String? _pendingAccountingPath(String eventId, String domain) {
    if (!allowed || !RegExp(r'^[a-f0-9]{32}$').hasMatch(eventId)) return null;
    final stored = _pending['accounting-$domain-$eventId']?.path;
    return stored == '/accounting/$domain/events/$eventId/confirm' ||
            stored == '/accounting/$domain/v2/events/$eventId/confirm'
        ? stored
        : null;
  }

  Future<dynamic> repeatDocumentComponentCommand(String eventId) =>
      _repeatAccountingCommand(eventId, 'components');
  Future<dynamic> repeatRefundOriginCommand(String eventId) =>
      _repeatAccountingCommand(eventId, 'refunds');

  String? pendingPreparationProfilePath() =>
      allowed &&
          _pending['accounting-profile']?.path == '/accounting/profile/confirm'
      ? '/accounting/profile/confirm'
      : null;

  void _requirePreparationProfileRights(int epoch) {
    _guard(epoch);
    if (projectId != null ||
        !hasFeature('accounting_preparation_profile') ||
        !hasModule('accounting_profile') ||
        !can('accounting.read') ||
        !can('finance.read') ||
        !canWrite('accounting.admin')) {
      throw const ApiException(
        403,
        'Das Vorbereitungsprofil ist nicht zur Änderung freigegeben.',
      );
    }
    if (!sectionEnabled('finance')) {
      throw const ApiException(423, 'Finanzen ist fachlich deaktiviert.');
    }
  }

  Future<dynamic> repeatPreparationProfileCommand() async {
    final epoch = _epoch;
    _guard(epoch);
    final operation = _pending['accounting-profile'];
    if (operation == null || pendingPreparationProfilePath() == null) {
      throw const ApiException(
        409,
        'Die frühere Übertragung wurde inzwischen beantwortet. Bitte den Stand neu laden.',
      );
    }
    await load();
    _guard(epoch);
    if (error != null || loading) {
      throw const ApiException(
        0,
        'Die aktuellen Berechtigungen konnten noch nicht bestätigt werden.',
      );
    }
    _requirePreparationProfileRights(epoch);
    final fresh = businessMap(await read('/accounting/profile'));
    _requirePreparationProfileRights(epoch);
    if (fresh['writes_allowed'] != true) {
      throw const ApiException(423, 'Neue Profilstände sind derzeit gesperrt.');
    }
    if (_pending['accounting-profile']?.body['request_id'] !=
        operation.body['request_id']) {
      throw const ApiException(
        409,
        'Die frühere Übertragung wurde inzwischen beantwortet. Bitte den Stand neu laden.',
      );
    }
    return _command(
      'accounting-profile',
      operation.path,
      Map<String, dynamic>.from(jsonDecode(operation.values)),
      documentaryRetry: true,
    );
  }

  /// Replay keeps the original nonce, body and response validator. Reloading
  /// capabilities is mandatory; a changed generation never creates a new write.
  Future<dynamic> _repeatWorkflowCommand(
    String key, {
    required bool Function(String) matches,
    required void Function() requireRights,
    String? readPath,
    void Function(Map<String, dynamic>)? verifyState,
  }) async {
    final epoch = _epoch;
    _guard(epoch);
    final operation = _pending[key];
    if (operation == null || !matches(operation.path)) {
      throw const ApiException(
        409,
        'Der offene Vorgang ist nicht mehr verfügbar. Bitte neu laden.',
      );
    }
    await load();
    _guard(epoch);
    if (error != null || loading) {
      throw const ApiException(
        0,
        'Die aktuellen Berechtigungen konnten noch nicht bestätigt werden.',
      );
    }
    requireRights();
    if (readPath != null) {
      final state = businessMap(await read(readPath));
      _guard(epoch);
      requireRights();
      verifyState?.call(state);
    }
    if (_pending[key]?.body['request_id'] != operation.body['request_id']) {
      throw const ApiException(
        409,
        'Die frühere Übertragung wurde inzwischen beantwortet. Bitte neu laden.',
      );
    }
    return _command(
      key,
      operation.path,
      Map<String, dynamic>.from(jsonDecode(operation.values)),
      documentaryRetry: true,
    );
  }

  Future<dynamic> repeatAccountingEuerCommand() => _repeatWorkflowCommand(
    'accounting-euer',
    matches: (path) => path == '/accounting/euer/confirm',
    readPath: '/accounting/euer',
    requireRights: () {
      if (projectId != null ||
          !hasFeature('accounting_euer') ||
          !hasModule('accounting_euer') ||
          !can('accounting.read') ||
          !can('finance.read') ||
          !canWrite('accounting.prepare') ||
          !canWrite('accounting.admin') ||
          !canWrite('finance.write')) {
        throw const ApiException(
          403,
          'Aktuelle Rechte für das EÜR-Journal fehlen.',
        );
      }
      if (!sectionEnabled('finance')) {
        throw const ApiException(423, 'Finanzen ist fachlich deaktiviert.');
      }
    },
  );

  Future<dynamic> repeatCustomerWorkspaceCommand(String key) {
    final operation = _pending[key];
    final revoke =
        operation != null &&
        RegExp(r'^/customer-workspace/(?:grants|files)/[a-f0-9]{32}/revoke$')
            .hasMatch(operation.path);
    return _repeatWorkflowCommand(
      key,
      matches: (path) => path.startsWith('/customer-workspace/'),
      readPath: '/customer-workspace?project_id=$projectId',
      requireRights: () {
        if (projectId == null ||
            !hasFeature('customer_workspace_portal') ||
            !hasModule('customer_workspace') ||
            !can('portal.manage') ||
            !can('documents.read') ||
            (!revoke && readonly)) {
          throw const ApiException(
            403,
            'Aktuelle Rechte für den Kundenbereich fehlen.',
          );
        }
        if (!revoke && !sectionEnabled('documents')) {
          throw const ApiException(423, 'Dokumente sind fachlich deaktiviert.');
        }
      },
      verifyState: (state) {
        if (businessMap(state['project'])['id'] != projectId ||
            (operation?.body['project_id'] != null &&
                operation!.body['project_id'] != projectId)) {
          throw const ApiException(
            403,
            'Der Vorgang gehört zu einem anderen Projekt.',
          );
        }
        final scoped = RegExp(
          r'^/customer-workspace/(grants|files|uploads)/([a-f0-9]{32})/(?:revoke|accept)$',
        ).firstMatch(operation?.path ?? '');
        if (scoped != null &&
            !businessItems(state[scoped.group(1)] ?? [])
                .any((item) => item['id'] == scoped.group(2))) {
          throw const ApiException(
            403,
            'Die Freigabe oder Datei ist in diesem Projekt nicht zugänglich.',
          );
        }
      },
    );
  }

  Future<dynamic> repeatAssistantCommand(
    String key,
    String selectedProject,
  ) async {
    final epoch = _epoch;
    _guard(epoch);
    final scope = sharedProjectSession(selectedProject);
    await scope.load();
    _guard(epoch);
    if (scope.error != null || scope.loading) {
      throw const ApiException(
        0,
        'Die aktuellen Projektrechte konnten nicht bestätigt werden.',
      );
    }
    final operation = _pending[key];
    final context = operation?.body['context_id'];
    final target = RegExp(
      r'^/assistant/plans/([a-f0-9]{32})/(?:approve|reject|execute)$',
    ).firstMatch(operation?.path ?? '');
    final readPath = target != null
        ? '/assistant/plans/${target.group(1)}'
        : context is String && RegExp(r'^[a-f0-9]{32}$').hasMatch(context)
        ? '/assistant/contexts/$context'
        : '/assistant/sources?project_id=$selectedProject';
    return _repeatWorkflowCommand(
      key,
      matches: (path) => path.startsWith('/assistant/'),
      readPath: readPath,
      requireRights: () {
        if (!scope.hasFeature('assistant_workflow') ||
            !scope.hasModule('assistant') ||
            !scope.canWrite('assistant.use')) {
          throw const ApiException(
            403,
            'Aktuelle Projekt- und Assistentenrechte fehlen.',
          );
        }
      },
      verifyState: (state) {
        final boundProject =
            operation?.body['project_id'] ?? state['project_id'];
        if (boundProject != selectedProject) {
          throw const ApiException(
            403,
            'Der offene Assistentenvorgang gehört zu einem anderen Projekt.',
          );
        }
      },
    );
  }

  /// Catalog replay keeps the original file/mapping, nonce and validator.
  /// Only the two explicit catalog command paths may use this retry policy.
  Future<dynamic> catalogConsumerCommand(
    String key,
    String path,
    Map<String, dynamic> values,
  ) {
    final operation = _pending[key];
    if (operation == null ||
        !_datedCatalogConsumer(
          key,
          operation.path,
          Map<String, dynamic>.from(jsonDecode(operation.values)),
        )) {
      return command(key, path, values);
    }
    if (operation.path != path || operation.values != jsonEncode(values)) {
      throw const ApiException(
        409,
        'Die offene datierte Preisübernahme muss unverändert wiederholt werden.',
      );
    }
    final purchasing = path.startsWith('/inventory/orders');
    return _repeatWorkflowCommand(
      key,
      matches: (route) =>
          route == path && _datedCatalogConsumer(key, route, values),
      requireRights: () {
        if (!hasFeature('catalog_prices_v2') ||
            !hasModule('catalog_prices') ||
            !can('finance.read') ||
            !canWrite(
              purchasing
                  ? (key.startsWith('purchase-approve-')
                        ? 'finance.approve'
                        : 'inventory.write')
                  : 'finance.write',
            ) ||
            (purchasing && !can('inventory.read')) ||
            (projectId != null && values['project_id'] != projectId)) {
          throw const ApiException(
            403,
            'Aktuelle Rechte für die datierte Preisübernahme fehlen.',
          );
        }
        if (!sectionEnabled(purchasing ? 'material' : 'documents'))
          throw const ApiException(
            423,
            'Der zugehörige Bereich ist fachlich deaktiviert.',
          );
      },
    );
  }

  Future<dynamic> repeatCatalogPricesCommand(String key) {
    final operation = _pending[key];
    final match = RegExp(r'^catalog-v2-(import|apply|withdraw)-([a-f0-9]{32})$')
        .firstMatch(key);
    final kind = match?.group(1), id = match?.group(2);
    return _repeatWorkflowCommand(
      key,
      matches: (path) => _catalogPricesCommand(key, path),
      readPath: kind == 'apply'
          ? '/catalog-prices/imports/$id'
          : kind == 'withdraw'
          ? '/catalog-prices/prices/$id/history'
          : '/catalog-prices/sources',
      requireRights: () {
        if (projectId != null ||
            !hasFeature('catalog_prices_v2') ||
            !hasModule('catalog_prices') ||
            !can('settings.manage') ||
            !can('finance.read') ||
            !canWrite('finance.write')) {
          throw const ApiException(
            403,
            'Aktuelle globale Katalog- und Finanzrechte fehlen.',
          );
        }
        if (!sectionEnabled('documents'))
          throw const ApiException(
            423,
            'Kaufmännische Belege sind fachlich deaktiviert.',
          );
      },
      verifyState: (state) {
        if (operation == null ||
            !_catalogPricesCommand(key, operation.path) ||
            kind == 'apply' && state['id'] != id ||
            kind == 'import' &&
                !businessItems(state).any((item) => item['id'] == id) ||
            kind == 'withdraw' &&
                (businessItems(state).isEmpty ||
                    businessItems(state).any((item) => item['id'] != id))) {
          throw const ApiException(
            409,
            'Die ursprüngliche datierte Katalogquelle ist nicht sicher freigegeben.',
          );
        }
      },
    );
  }

  Future<dynamic> repeatCatalogCommand(String key) {
    final operation = _pending[key];
    final match = RegExp(r'^catalog-(import|apply)-([a-f0-9]{32})$')
        .firstMatch(key);
    final importing = match?.group(1) == 'import';
    return _repeatWorkflowCommand(
      key,
      matches: (path) => _catalogCommand(key, path),
      readPath: match == null
          ? null
          : importing
          ? '/adapters/${match.group(2)}'
          : '/adapters/imports/${match.group(2)}',
      requireRights: () {
        if (projectId != null ||
            !hasModule('adapters') ||
            !hasModule('catalog_imports') ||
            !can('settings.manage') ||
            !can('finance.read') ||
            !canWrite('finance.write')) {
          throw const ApiException(
            403,
            'Aktuelle globale Katalog- und Finanzrechte fehlen.',
          );
        }
        if (!sectionEnabled('documents')) {
          throw const ApiException(
            423,
            'Kaufmännische Belege sind fachlich deaktiviert.',
          );
        }
      },
      verifyState: (state) {
        if (state['id'] != match?.group(2) ||
            !const [
              'catalog_csv_v1',
              'datanorm_a14_cp850_v1',
            ].contains(state['profile']) ||
            importing && state['enabled'] != true ||
            !importing &&
                !const ['staged', 'applied'].contains(state['status']) ||
            operation == null ||
            !_catalogCommand(key, operation.path)) {
          throw const ApiException(
            409,
            'Die ursprüngliche Katalogquelle ist nicht sicher freigegeben.',
          );
        }
      },
    );
  }

  Future<dynamic> repeatBankCommand(String key) {
    final operation = _pending[key];
    final route = operation?.path ?? '';
    final accountCommand = route == '/bank/accounts';
    final match = RegExp(r'^/bank/transactions/([a-f0-9]{32})/matches$')
        .firstMatch(route);
    final accountId = operation?.body['account_id'];
    return _repeatWorkflowCommand(
      key,
      matches: (path) =>
          key.startsWith('bank-') &&
          (accountCommand ||
              route == '/bank/statements' ||
              route == '/bank/reconciliations' ||
              match != null),
      readPath: match == null
          ? '/bank/accounts'
          : '/bank/transactions/${match.group(1)}/candidates',
      requireRights: () {
        if (projectId != null ||
            !hasFeature('bank_reconciliation') ||
            !hasModule('bank_reconciliation') ||
            !can('bank.read') ||
            !can('accounting.read') ||
            !can('finance.read') ||
            !canWrite('bank.prepare') ||
            !canWrite('accounting.prepare') ||
            !canWrite('finance.write') ||
            accountCommand &&
                (!canWrite('bank.admin') || !canWrite('accounting.admin'))) {
          throw const ApiException(
            403,
            'Aktuelle globale Rechte für den Bankabgleich fehlen.',
          );
        }
        if (!sectionEnabled('finance')) {
          throw const ApiException(423, 'Finanzen ist fachlich deaktiviert.');
        }
      },
      verifyState: (state) {
        if (match != null) {
          if (businessMap(state['transaction'])['id'] != match.group(1)) {
            throw const ApiException(
              502,
              'Der offene Vorgang gehört nicht zu dieser Bankbuchung.',
            );
          }
        } else {
          final available = state['available_accounts'];
          final bindings = state['items'];
          if (available is! List ||
              bindings is! List ||
              !available.any((item) => businessMap(item)['id'] == accountId) ||
              !accountCommand &&
                  !bindings.any(
                    (item) => businessMap(item)['account_id'] == accountId,
                  )) {
            throw const ApiException(
              403,
              'Das ursprüngliche Bankkonto ist nicht mehr verfügbar.',
            );
          }
        }
        // Current revisions deliberately do not replace the accepted original.
        // The server resolves its unchanged nonce before checking a new effect.
      },
    );
  }

  Future<dynamic> repeatResourceCustodyCommand(String key) {
    final operation = _pending[key];
    final target = RegExp(
      r'^/resource-custody/([a-f0-9]{32})/(profile|requirements|files|inspections|handoffs|returns|corrections)$',
    ).firstMatch(operation?.path ?? '');
    return _repeatWorkflowCommand(
      key,
      matches: (path) => key.startsWith('resource-custody-') && target != null,
      readPath: '/resource-custody/${target?.group(1)}',
      requireRights: () {
        if (projectId != null ||
            !hasFeature('resource_custody') ||
            !hasModule('resource_custody') ||
            !can('planning.read') ||
            !canWrite('planning.write')) {
          throw const ApiException(
            403,
            'Aktuelle globale Rechte für Betriebsmittel fehlen.',
          );
        }
      },
      verifyState: (state) {
        if (state['id'] != target?.group(1) ||
            businessMap(state['resource'])['id'] != target?.group(1)) {
          throw const ApiException(
            502,
            'Der offene Vorgang gehört nicht zu diesem Betriebsmittel.',
          );
        }
      },
    );
  }

  Future<dynamic> repeatCustomFieldsCommand(String key) {
    final operation = _pending[key];
    final definition = operation?.path == '/custom-fields/definitions';
    final entity = RegExp(
      r'^/custom-fields/entities/(contact|project|asset)/([a-f0-9]{32})$',
    ).firstMatch(operation?.path ?? '');
    return _repeatWorkflowCommand(
      key,
      matches: (path) =>
          key.startsWith('custom-fields-') && (definition || entity != null),
      readPath: definition
          ? '/custom-fields/definitions'
          : operation?.path ?? '/custom-fields/definitions',
      requireRights: () {
        if (readonly ||
            !hasModule('custom_fields') ||
            !hasFeature('custom_fields') ||
            definition && (projectId != null || !canWrite('settings.manage'))) {
          throw const ApiException(
            403,
            'Aktuelle Rechte für Zusatzfelder fehlen.',
          );
        }
      },
      verifyState: (state) {
        if (definition) {
          if (state['items'] is! List)
            throw const ApiException(
              502,
              'Die Felddefinitionen konnten nicht bestätigt werden.',
            );
        } else {
          final source = businessMap(state['entity']);
          if (source['entity_type'] != entity?.group(1) ||
              source['id'] != entity?.group(2)) {
            throw const ApiException(
              502,
              'Die Zusatzwerte gehören nicht zum geöffneten Datensatz.',
            );
          }
          if (state['can_write'] != true)
            throw const ApiException(
              403,
              'Die aktuelle Schreibfreigabe für diesen Datensatz fehlt.',
            );
          if (projectId != null &&
              source['project_id'] != null &&
              source['project_id'] != projectId) {
            throw const ApiException(
              403,
              'Die Zusatzwerte gehören zu einem anderen Projekt.',
            );
          }
        }
      },
    );
  }

  Future<dynamic> repeatPurchaseChangeCommand(String key) async {
    final operation = _pending[key];
    final target = RegExp(
      r'^/purchasing/orders/([a-f0-9]{32})/(change-files|amendments|supplier-returns)$',
    ).firstMatch(operation?.path ?? '');
    if (operation == null ||
        !key.startsWith('purchase-change-') ||
        target == null) {
      throw const ApiException(
        409,
        'Der ursprüngliche Einkaufsvorgang ist nicht verfügbar.',
      );
    }
    final epoch = _epoch;
    _guard(epoch);
    final readPath = '/purchasing/orders/${target.group(1)}/changes';
    final item = businessMap(await api.call(path(readPath)));
    _guard(epoch);
    final selectedProject = item['project_id'];
    if (item['id'] != target.group(1) ||
        item['order_id'] != target.group(1) ||
        selectedProject != null &&
            (selectedProject is! String ||
                !RegExp(r'^[a-f0-9]{32}$').hasMatch(selectedProject))) {
      throw const ApiException(
        502,
        'Die ursprüngliche Bestellung konnte nicht bestätigt werden.',
      );
    }
    if (projectId != null && selectedProject != projectId) {
      throw const ApiException(
        403,
        'Die Bestellung gehört nicht zum geöffneten Projekt.',
      );
    }
    final scope = selectedProject == null || selectedProject == projectId
        ? this
        : sharedProjectSession(selectedProject as String);
    await scope.load();
    _guard(epoch);
    if (scope.error != null || scope.loading) {
      throw const ApiException(
        0,
        'Die aktuellen Einkaufsrechte konnten nicht bestätigt werden.',
      );
    }
    return _repeatWorkflowCommand(
      key,
      matches: (value) => value == operation.path,
      readPath: readPath,
      requireRights: () {
        if (!scope.hasFeature('purchase_changes') ||
            !scope.hasModule('purchase_changes') ||
            !scope.can('inventory.read') ||
            !scope.canWrite('inventory.write') ||
            !scope.canWrite(
              target.group(2) == 'amendments'
                  ? 'finance.approve'
                  : 'finance.write',
            )) {
          throw const ApiException(
            403,
            'Aktuelle Rechte für diesen Einkaufsvorgang fehlen.',
          );
        }
        // New effects still need an active material module on the server;
        // an exact already accepted receipt must remain recoverable.
      },
      verifyState: (state) {
        if (state['id'] != target.group(1) ||
            state['order_id'] != target.group(1) ||
            state['project_id'] != selectedProject) {
          throw const ApiException(
            409,
            'Die Bestellung muss frisch geprüft werden.',
          );
        }
      },
    );
  }

  Future<dynamic> repeatServiceCommand(String key) async {
    final operation = _pending[key];
    final route = operation?.path ?? '';
    final target = RegExp(
      r'^/service/cases/([a-f0-9]{32})/(events|project|dispatch|evidence|transition)$',
    ).firstMatch(route);
    if (operation == null ||
        !key.startsWith('service-') ||
        route != '/service/cases' && target == null) {
      throw const ApiException(
        409,
        'Der ursprüngliche Serviceauftrag ist nicht verfügbar.',
      );
    }
    final epoch = _epoch;
    _guard(epoch);
    final caseId = target?.group(1) ?? operation.body['id'];
    String? selectedProject = operation.body['project_id'] as String?;
    if (caseId != null) {
      final item = businessMap(await api.call(path('/service/cases/$caseId')));
      _guard(epoch);
      if (item['id'] != caseId)
        throw const ApiException(
          502,
          'Der Servicefall konnte nicht bestätigt werden.',
        );
      selectedProject = item['project_id'] as String?;
    }
    if (projectId != null && selectedProject != projectId) {
      throw const ApiException(
        403,
        'Der Servicefall gehört nicht zum geöffneten Projekt.',
      );
    }
    final scope = selectedProject == null || selectedProject == projectId
        ? this
        : sharedProjectSession(selectedProject);
    await scope.load();
    _guard(epoch);
    if (scope.error != null || scope.loading)
      throw const ApiException(
        0,
        'Die aktuellen Servicerechte konnten nicht bestätigt werden.',
      );
    if (selectedProject == null) {
      final me = businessMap(await api.call('/api/me'));
      _guard(epoch);
      if (me['role'] != 'owner')
        throw const ApiException(
          403,
          'Servicefälle ohne Projekt benötigen die Geschäftsführung.',
        );
    }
    final query = Uri(
      queryParameters: <String, String>{
        if (operation.body['customer_id'] is String)
          'customer_id': operation.body['customer_id'] as String,
        if (selectedProject != null) 'project_id': selectedProject,
      },
    ).query;
    return _repeatWorkflowCommand(
      key,
      matches: (value) => value == route,
      readPath: caseId != null
          ? '/service/cases/$caseId'
          : '/service/options${query.isEmpty ? '' : '?$query'}',
      requireRights: () {
        if (!scope.hasFeature('service_cases') ||
            !scope.hasModule('service') ||
            scope.readonly ||
            !scope.can('contacts.read') ||
            (selectedProject == null
                ? !scope.canWrite('contacts.write')
                : !scope.can('documents.read') ||
                      !scope.canWrite('documents.write')) ||
            target?.group(2) == 'project' &&
                !scope.canWrite('projects.manage') ||
            target?.group(2) == 'dispatch' &&
                !scope.canWrite('planning.write')) {
          throw const ApiException(
            403,
            'Aktuelle Rechte für diesen Serviceauftrag fehlen.',
          );
        }
        // The frozen request may already have succeeded before deactivation.
        // The server distinguishes its receipt from any new native effect.
      },
      verifyState: (state) {
        if (state['project_id'] != selectedProject ||
            (caseId != null
                ? state['id'] != caseId
                : state['customer_id'] != operation.body['customer_id'])) {
          throw const ApiException(
            409,
            'Die Zuordnung des Serviceauftrags muss frisch geprüft werden.',
          );
        }
      },
    );
  }

  Future<dynamic> repeatCompanyHandoverCommand({bool review = false}) async {
    final epoch = _epoch;
    _guard(epoch);
    final me = businessMap(await api.call('/api/me'));
    _guard(epoch);
    if (me['role'] != 'owner')
      throw const ApiException(
        403,
        'Die Unternehmensübergabe erfordert die Geschäftsführung.',
      );
    final key = review ? 'company-handover-review' : 'company-handover-export';
    final route = review
        ? '/company-handover/exit-reviews'
        : '/company-handover/exports';
    return _repeatWorkflowCommand(
      key,
      matches: (path) => path == route,
      readPath: '/company-handover',
      requireRights: () {
        if (projectId != null ||
            readonly ||
            !hasFeature('company_handover') ||
            !hasModule('company_handover')) {
          throw const ApiException(
            403,
            'Aktuelle Rechte für die Unternehmensübergabe fehlen.',
          );
        }
      },
      verifyState: (state) {
        if (state['instance_id'] != _pending[key]?.body['instance_id']) {
          throw const ApiException(
            409,
            'Der offene Auftrag gehört nicht zur Unternehmensinstanz.',
          );
        }
      },
    );
  }

  Future<dynamic> repeatMigrationCommand(String key) async {
    final operation = _pending[key];
    final match = RegExp(
      r'^/migrations/([a-f0-9]{32})/(files|mapping|apply|reconcile)$',
    ).firstMatch(operation?.path ?? '');
    final epoch = _epoch;
    _guard(epoch);
    final me = businessMap(await api.call('/api/me'));
    _guard(epoch);
    if (me['role'] != 'owner')
      throw const ApiException(
        403,
        'Der Dateiimport erfordert die Geschäftsführung.',
      );
    return _repeatWorkflowCommand(
      key,
      matches: (path) =>
          key.startsWith('migration-') &&
          (path == '/migrations' || match != null),
      readPath: match == null ? '/migrations' : '/migrations/${match.group(1)}',
      requireRights: () {
        if (projectId != null ||
            !hasFeature('file_migrations') ||
            !hasModule('migrations') ||
            !canWrite('settings.manage') ||
            !can('contacts.read') ||
            !can('finance.read') ||
            !can('documents.read') ||
            match?.group(2) == 'apply' &&
                (!canWrite('contacts.write') ||
                    !canWrite('projects.manage') ||
                    !sectionEnabled('documents'))) {
          throw const ApiException(
            403,
            'Aktuelle Rechte für diesen Dateiimport fehlen.',
          );
        }
      },
      verifyState: (state) {
        if (match != null && state['id'] != match.group(1)) {
          throw const ApiException(
            502,
            'Der offene Auftrag gehört nicht zu diesem Importpaket.',
          );
        }
        if (match == null && state['items'] is! List) {
          throw const ApiException(
            502,
            'Die Importübersicht konnte nicht bestätigt werden.',
          );
        }
      },
    );
  }

  Future<dynamic> repeatSalesCommand(String key) {
    final operation = _pending[key];
    final path = operation?.path ?? '';
    final match = RegExp(
      r'^/sales/opportunities/([a-f0-9]{32})(?:/(activities|project|offer))?$',
    ).firstMatch(path);
    final id = match?.group(1) ?? operation?.body['id'];
    final customer = operation?.body['customer_id'];
    return _repeatWorkflowCommand(
      key,
      matches: (route) =>
          key.startsWith('sales-') &&
          (route == '/sales/opportunities' || match != null),
      readPath: id == null
          ? '/sales/options?customer_id=$customer'
          : '/sales/opportunities/$id',
      requireRights: () {
        if (projectId != null ||
            !hasFeature('sales_pipeline') ||
            !hasModule('sales') ||
            !can('contacts.read') ||
            !canWrite('contacts.write') ||
            match?.group(2) == 'project' && !canWrite('projects.manage') ||
            match?.group(2) == 'offer' &&
                (!can('finance.read') ||
                    !canWrite('finance.write') ||
                    !canWrite('projects.manage'))) {
          throw const ApiException(
            403,
            'Aktuelle Rechte für diesen Vertriebsvorgang fehlen.',
          );
        }
        if (match?.group(2) == 'offer' && !sectionEnabled('documents')) {
          throw const ApiException(423, 'Belege sind fachlich deaktiviert.');
        }
      },
      verifyState: (state) {
        if (id != null ? state['id'] != id : state['customer_id'] != customer) {
          throw const ApiException(
            502,
            'Der offene Vorgang gehört nicht eindeutig zu dieser Verkaufschance.',
          );
        }
      },
    );
  }

  Future<dynamic> repeatInventoryCountCommand(String key) {
    final operation = _pending[key];
    final match = RegExp(
      r'^/inventory/counts/([a-f0-9]{32})/(count|approve|cancel)$',
    ).firstMatch(operation?.path ?? '');
    final location = operation?.body['location_id'];
    return _repeatWorkflowCommand(
      key,
      matches: (path) =>
          key.startsWith('inventory-count-') &&
          (path == '/inventory/counts' || match != null),
      readPath: match == null
          ? '/inventory/count-sources?location_id=$location'
          : '/inventory/counts/${match.group(1)}',
      requireRights: () {
        if (projectId != null ||
            !hasFeature('inventory_counts') ||
            !hasModule('inventory_counts') ||
            !can('inventory.read') ||
            !canWrite('inventory.write') ||
            match?.group(2) == 'approve' &&
                (!can('finance.read') ||
                    !canWrite('finance.write') ||
                    !canWrite('finance.approve'))) {
          throw const ApiException(
            403,
            'Aktuelle Rechte für diese Inventur fehlen.',
          );
        }
        if (!sectionEnabled('material'))
          throw const ApiException(423, 'Material ist fachlich deaktiviert.');
      },
      verifyState: (state) {
        if (match != null
            ? state['id'] != match.group(1)
            : businessMap(state['location'])['id'] != location) {
          throw const ApiException(
            502,
            'Der offene Vorgang gehört nicht eindeutig zu dieser Inventur.',
          );
        }
      },
    );
  }

  Future<dynamic> repeatPayrollCashCommand(String employeeId) async {
    final key = 'payroll-cash-$employeeId';
    final epoch = _epoch;
    _guard(epoch);
    final cash = businessMap(await api.call(path('/payroll/cash')));
    _guard(epoch);
    if (cash['writes_allowed'] != true) {
      throw const ApiException(
        423,
        'Die aktuelle Freigabe für Lohnzahlungen fehlt. Der ursprüngliche Auftrag bleibt offen.',
      );
    }
    if (cash['instance_id'] != _pending[key]?.body['instance_id']) {
      throw const ApiException(
        409,
        'Die Lohnzahlungsübernahme gehört zu einer anderen Unternehmensinstanz.',
      );
    }
    return _repeatWorkflowCommand(
      key,
      matches: (route) => route == '/payroll/cash/batches',
      readPath: '/payroll/cash/sources?employee_id=$employeeId',
      requireRights: () {
        if (!RegExp(r'^[a-f0-9]{32}$').hasMatch(employeeId) ||
            projectId != null ||
            !hasFeature('payroll_actual_cash') ||
            !hasModule('payroll_cash') ||
            !can('personnel.read') ||
            !can('accounting.read') ||
            !can('finance.read') ||
            !canWrite('personnel.approve') ||
            !canWrite('accounting.prepare') ||
            !canWrite('finance.write')) {
          throw const ApiException(
            403,
            'Aktuelle Personal- und Finanzrechte für die Zahlungsübernahme fehlen.',
          );
        }
        if (!sectionEnabled('personnel') || !sectionEnabled('finance')) {
          throw const ApiException(
            423,
            'Personal und Finanzen müssen fachlich aktiviert sein.',
          );
        }
      },
      verifyState: (state) {
        if (state['employee_id'] != employeeId ||
            state['instance_id'] != _pending[key]?.body['instance_id']) {
          throw const ApiException(
            502,
            'Die Zahlungsquellen gehören nicht zum Mitarbeiter und zur Unternehmensinstanz.',
          );
        }
      },
    );
  }

  Future<dynamic> repeatPayrollAccountCommand(String employeeId) {
    final key = 'payroll-account-$employeeId';
    final kind = _pending[key]?.body['kind'];
    return _repeatWorkflowCommand(
      key,
      matches: (path) => path == '/payroll/account-records',
      readPath: '/payroll/account-records?employee_id=$employeeId',
      requireRights: () {
        if (!RegExp(r'^[a-f0-9]{32}$').hasMatch(employeeId) ||
            projectId != null ||
            !hasFeature('payroll_wage_account') ||
            !hasModule('payroll_accounts') ||
            !['identity', 'payment', 'carryover'].contains(kind) ||
            !can('personnel.read') ||
            !canWrite(
              kind == 'identity' ? 'personnel.write' : 'personnel.approve',
            ) ||
            _pending[key]?.body['employee_id'] != employeeId) {
          throw const ApiException(
            403,
            'Aktuelle Rechte für diesen Lohnkontovorgang fehlen.',
          );
        }
        if (!sectionEnabled('personnel'))
          throw const ApiException(423, 'Personal ist fachlich deaktiviert.');
      },
      verifyState: (state) {
        final items = state['items'];
        if (state['employee_id'] != employeeId ||
            items is! List ||
            items.any(
              (item) => item is! Map || item['employee_id'] != employeeId,
            )) {
          throw const ApiException(
            502,
            'Die Kontounterlagen gehören nicht eindeutig zum Mitarbeiter.',
          );
        }
      },
    );
  }

  Future<dynamic> repeatPayrollFactsCommand(String employeeId) {
    final key = 'payroll-facts-$employeeId';
    final operation = _pending[key];
    final kind = operation?.body['kind'];
    final approving = kind == 'period_case';
    return _repeatWorkflowCommand(
      key,
      matches: (path) => path == '/payroll/facts',
      readPath: '/payroll/facts/sources?employee_id=$employeeId',
      requireRights: () {
        if (!RegExp(r'^[a-f0-9]{32}$').hasMatch(employeeId) ||
            projectId != null ||
            !hasFeature('payroll_period_facts') ||
            !hasModule('payroll_facts') ||
            ![
              'employment_terms',
              'work_schedule',
              'period_case',
            ].contains(kind) ||
            !can('personnel.read') ||
            !canWrite(approving ? 'personnel.approve' : 'personnel.write') ||
            operation?.body['employee_id'] != employeeId) {
          throw const ApiException(
            403,
            'Aktuelle Rechte für diesen belegten Lohnfall fehlen.',
          );
        }
        // An accepted original remains repeatable after module deactivation.
        // The server still blocks a new effect and checks current authority.
      },
      verifyState: (state) {
        if (state['employee_id'] != employeeId ||
            state['employee'] is! Map ||
            (state['employee'] as Map)['id'] != employeeId) {
          throw const ApiException(
            502,
            'Die Lohnfallquellen gehören nicht eindeutig zum Mitarbeiter.',
          );
        }
        if (state[approving ? 'can_approve' : 'can_write'] != true) {
          throw const ApiException(
            403,
            'Die aktuellen Rechte am Lohnfall konnten nicht bestätigt werden.',
          );
        }
        // Current source revisions can have advanced after a lost response.
        // Preserve the old body and nonce so the server can resolve its receipt.
      },
    );
  }

  Future<dynamic> repeatPayrollEntitlementsCommand(String employeeId) {
    final key = 'payroll-entitlements-$employeeId';
    final operation = _pending[key];
    return _repeatWorkflowCommand(
      key,
      matches: (path) => path == '/payroll/entitlements',
      readPath: '/payroll/entitlements/sources?employee_id=$employeeId',
      requireRights: () {
        if (!RegExp(r'^[a-f0-9]{32}$').hasMatch(employeeId) ||
            projectId != null ||
            !hasFeature('payroll_entitlements') ||
            !hasModule('payroll_entitlements') ||
            ![
              'sickness_history',
              'regular_absence',
              'vacation_reference',
              'unpaid_continuation',
            ].contains(operation?.body['kind']) ||
            !can('personnel.read') ||
            !canWrite('personnel.approve') ||
            operation?.body['employee_id'] != employeeId) {
          throw const ApiException(
            403,
            'Aktuelle Rechte für diesen belegten Lohnanspruch fehlen.',
          );
        }
        // Accepted originals remain repeatable after module deactivation;
        // the server checks its original receipt before allowing a new effect.
      },
      verifyState: (state) {
        if (state['employee_id'] != employeeId ||
            state['employee'] is! Map ||
            (state['employee'] as Map)['id'] != employeeId) {
          throw const ApiException(
            502,
            'Die Anspruchsquellen gehören nicht eindeutig zum Mitarbeiter.',
          );
        }
        if (state['can_approve'] != true) {
          throw const ApiException(
            403,
            'Die aktuellen Freigaberechte am Anspruch fehlen.',
          );
        }
      },
    );
  }

  Future<dynamic> repeatPayrollCalculationCaseCommand(String employeeId) {
    final key = 'payroll-calculation-cases-$employeeId';
    final operation = _pending[key];
    final details = operation?.body['details'];
    final month = details is Map ? details['month'] : null;
    return _repeatWorkflowCommand(
      key,
      matches: (path) => path == '/payroll/calculation-cases',
      readPath:
          '/payroll/calculation-cases/sources?employee_id=$employeeId&month=$month',
      requireRights: () {
        if (!RegExp(r'^[a-f0-9]{32}$').hasMatch(employeeId) ||
            month is! String ||
            !RegExp(r'^2026-(0[1-9]|1[0-2])$').hasMatch(month) ||
            projectId != null ||
            !hasFeature('payroll_calculation_cases') ||
            !hasModule('payroll_calculation_cases') ||
            !can('personnel.read') ||
            !canWrite('personnel.approve') ||
            operation?.body['kind'] != 'calculation_case' ||
            operation?.body['rule_version'] !=
                'de_2026_segments_entitlements_v5' ||
            operation?.body['source_contract_version'] is! int ||
            operation?.body['source_contract_version'] != 1 ||
            operation?.body['employee_id'] != employeeId) {
          throw const ApiException(
            403,
            'Aktuelle Rechte und der ursprüngliche belegte Abrechnungsfall fehlen.',
          );
        }
      },
      verifyState: (state) {
        if (state['employee_id'] != employeeId ||
            state['employee'] is! Map ||
            state['employee']['id'] != employeeId ||
            state['month'] != month ||
            state['calculation_cases'] is! List) {
          throw const ApiException(
            502,
            'Die Quellen gehören nicht eindeutig zum Mitarbeiter und Abrechnungsmonat.',
          );
        }
        if (state['can_approve'] != true) {
          throw const ApiException(
            403,
            'Die aktuellen Freigaberechte am Abrechnungsfall fehlen.',
          );
        }
        // The original accepted body stays unchanged despite newer sources
        // or a paused personnel module. Only the server receipt proves success.
      },
    );
  }

  Future<dynamic> repeatPayrollOneoffCaseCommand(String employeeId) {
    final key = 'payroll-oneoff-cases-$employeeId';
    final operation = _pending[key];
    final details = operation?.body['details'];
    final month = details is Map ? details['month'] : null;
    return _repeatWorkflowCommand(
      key,
      matches: (path) => path == '/payroll/one-off-cases',
      readPath:
          '/payroll/one-off-cases/sources?employee_id=$employeeId&month=$month',
      requireRights: () {
        if (!RegExp(r'^[a-f0-9]{32}$').hasMatch(employeeId) ||
            month is! String ||
            !RegExp(r'^2026-(0[1-9]|1[0-2])$').hasMatch(month) ||
            projectId != null ||
            !hasFeature('payroll_oneoff_cases') ||
            !hasModule('payroll_oneoff_cases') ||
            !can('personnel.read') ||
            !canWrite('personnel.approve') ||
            operation?.body['kind'] != 'one_off_case' ||
            operation?.body['rule_version'] !=
                'de_2026_oneoff_composition_v6' ||
            operation?.body['source_contract_version'] is! int ||
            operation?.body['source_contract_version'] != 1 ||
            operation?.body['employee_id'] != employeeId) {
          throw const ApiException(
            403,
            'Aktuelle Rechte und der ursprüngliche belegte Einmalbezugsfall fehlen.',
          );
        }
      },
      verifyState: (state) {
        if (state['employee_id'] != employeeId ||
            state['employee'] is! Map ||
            state['employee']['id'] != employeeId ||
            state['month'] != month ||
            state['calculation_cases'] is! List ||
            state['annual_facts'] is! List ||
            state['one_off_cases'] is! List) {
          throw const ApiException(
            502,
            'Die Quellen gehören nicht eindeutig zum Mitarbeiter und Abrechnungsmonat.',
          );
        }
        if (state['can_approve'] != true) {
          throw const ApiException(
            403,
            'Die aktuellen Freigaberechte am Einmalbezugsfall fehlen.',
          );
        }
        // The original accepted body stays unchanged despite newer sources
        // or a paused personnel module. Only the server receipt proves success.
      },
    );
  }

  Future<dynamic> repeatPayrollMultipleCaseCommand(String employeeId) {
    final key = 'payroll-multiple-$employeeId';
    final operation = _pending[key];
    final details = operation?.body['details'];
    final month = details is Map ? details['month'] : null;
    return _repeatWorkflowCommand(
      key,
      matches: (path) => path == '/payroll/multiple-one-off-cases',
      readPath:
          '/payroll/multiple-one-off-cases/sources?employee_id=$employeeId&month=$month',
      requireRights: () {
        if (!RegExp(r'^[a-f0-9]{32}$').hasMatch(employeeId) ||
            month is! String ||
            !RegExp(r'^2026-(0[1-9]|1[0-2])$').hasMatch(month) ||
            projectId != null ||
            !hasFeature('payroll_multiple_cases') ||
            !hasModule('payroll_multiple_cases') ||
            !can('personnel.read') ||
            !canWrite('personnel.approve') ||
            operation?.body['kind'] != 'multiple_one_off_case' ||
            operation?.body['rule_version'] != 'de_2026_multiple_oneoff_v7' ||
            operation?.body['source_contract_version'] is! int ||
            operation?.body['source_contract_version'] != 1 ||
            operation?.body['employee_id'] != employeeId) {
          throw const ApiException(
            403,
            'Aktuelle Rechte und der ursprüngliche belegte Monatsgruppenfall fehlen.',
          );
        }
      },
      verifyState: (state) {
        if (state['employee_id'] != employeeId ||
            state['employee'] is! Map ||
            state['employee']['id'] != employeeId ||
            state['month'] != month ||
            state['calculation_cases'] is! List ||
            state['annual_facts'] is! List ||
            state['multiple_one_off_cases'] is! List) {
          throw const ApiException(
            502,
            'Die Quellen gehören nicht eindeutig zum Mitarbeiter und Abrechnungsmonat.',
          );
        }
        if (state['can_approve'] != true) {
          throw const ApiException(
            403,
            'Die aktuellen Freigaberechte am Monatsgruppenfall fehlen.',
          );
        }
        // The original accepted body stays unchanged despite newer sources
        // or a paused personnel module. Only the server receipt proves success.
      },
    );
  }

  Future<dynamic> repeatPayrollAnnualBasisCommand(String employeeId) {
    final key = 'payroll-annual-basis-$employeeId';
    final operation = _pending[key];
    return _repeatWorkflowCommand(
      key,
      matches: (path) => path == '/payroll/annual-facts',
      readPath: '/payroll/annual-facts/sources?employee_id=$employeeId',
      requireRights: () {
        if (!RegExp(r'^[a-f0-9]{32}$').hasMatch(employeeId) ||
            projectId != null ||
            !hasFeature('payroll_annual_basis') ||
            !hasModule('payroll_annual_basis') ||
            !can('personnel.read') ||
            !canWrite('personnel.approve') ||
            operation?.body['employee_id'] != employeeId ||
            ![
              'imported_period',
              'imported_one_off',
              'annual_basis',
              'one_off_earning',
              'annual_tax_forecast',
            ].contains(operation?.body['kind'])) {
          throw const ApiException(
            403,
            'Aktuelle globale Rechte und die ursprüngliche Jahresquelle fehlen.',
          );
        }
      },
      verifyState: (state) {
        if (state['employee_id'] != employeeId ||
            state['employee'] is! Map ||
            state['employee']['id'] != employeeId ||
            state['annual_facts'] is! List ||
            state['payroll_runs'] is! List ||
            state['payroll_payments'] is! List ||
            state['calculation_cases'] is! List) {
          throw const ApiException(
            502,
            'Die privaten Jahresquellen gehören nicht eindeutig zum Mitarbeiter.',
          );
        }
        if (state['can_approve'] != true) {
          throw const ApiException(
            403,
            'Die aktuellen Freigaberechte für die Jahresquelle fehlen.',
          );
        }
        // Exact accepted requests remain repeatable after source changes or a
        // module pause. This never changes the frozen original or its nonce.
      },
    );
  }

  Future<dynamic> repeatPayrollWageInterruptionsCommand(String employeeId) {
    final key = 'payroll-wage-interruptions-$employeeId';
    final operation = _pending[key];
    final details = operation?.body['details'];
    return _repeatWorkflowCommand(
      key,
      matches: (path) => path == '/payroll/wage-interruptions',
      readPath:
          '/payroll/wage-interruptions/sources?employee_id=$employeeId&year=2026',
      requireRights: () {
        if (!RegExp(r'^[a-f0-9]{32}$').hasMatch(employeeId) ||
            projectId != null ||
            !hasFeature('payroll_wage_interruptions') ||
            !hasModule('payroll_wage_interruptions') ||
            !can('personnel.read') ||
            !canWrite('personnel.approve') ||
            operation?.body['employee_id'] != employeeId ||
            operation?.body['kind'] != 'wage_interruption_assessment' ||
            operation?.body['rule_version'] !=
                'de_2026_wage_interruptions_v1' ||
            operation?.body['source_contract_version'] is! int ||
            operation?.body['source_contract_version'] != 1 ||
            details is! Map ||
            details['year'] is! int ||
            details['year'] != 2026) {
          throw const ApiException(
            403,
            'Aktuelle globale Rechte und der ursprüngliche U-Nachweis fehlen.',
          );
        }
      },
      verifyState: (state) {
        if (state['employee_id'] != employeeId ||
            state['employee'] is! Map ||
            state['employee']['id'] != employeeId ||
            state['year'] is! int ||
            state['year'] != 2026 ||
            state['assessments'] is! List ||
            state['runs'] is! List ||
            state['entitlements'] is! List ||
            state['file_references'] is! List) {
          throw const ApiException(
            502,
            'Die privaten Jahresquellen sind nicht eindeutig der Person zugeordnet.',
          );
        }
        if (state['can_approve'] != true) {
          throw const ApiException(
            403,
            'Die aktuellen Freigaberechte für den U-Nachweis fehlen.',
          );
        }
        // A newer source revision or a paused module never changes the
        // accepted original. The server verifies its immutable receipt.
      },
    );
  }

  Future<dynamic> repeatPayrollTravelTaxPolicyCommand() {
    const key = 'payroll-travel-tax-policies';
    final operation = _pending[key];
    return _repeatWorkflowCommand(
      key,
      matches: (path) => path == '/payroll/travel-tax-policies',
      readPath: '/payroll/travel-tax-policies/sources',
      requireRights: () {
        if (projectId != null ||
            !hasFeature('payroll_calculation_cases') ||
            !hasModule('payroll_calculation_cases') ||
            !can('personnel.read') ||
            !canWrite('personnel.approve') ||
            operation?.body['kind'] != 'travel_tax_policy' ||
            operation?.body['rule_version'] != 'de_2026_travel_tax_policy_v1' ||
            operation?.body['source_contract_version'] is! int ||
            operation?.body['source_contract_version'] != 1 ||
            operation?.body.containsKey('employee_id') != true ||
            operation?.body['employee_id'] != null ||
            operation?.body.containsKey('employee_revision') != true ||
            operation?.body['employee_revision'] != null) {
          throw const ApiException(
            403,
            'Aktuelle globale Rechte für die betriebliche Steuerentscheidung fehlen.',
          );
        }
      },
      verifyState: (state) {
        if (!state.containsKey('employee_id') ||
            state['employee_id'] != null ||
            state['files'] is! List ||
            state['file_references'] is! List ||
            state['policies'] is! List) {
          throw const ApiException(
            502,
            'Die betrieblichen Steuerquellen sind nicht eindeutig.',
          );
        }
        if (state['can_approve'] != true) {
          throw const ApiException(
            403,
            'Die aktuellen Freigaberechte für die Steuerentscheidung fehlen.',
          );
        }
        // Fresh sources may advance after a lost response. Replay retains the
        // original body/nonce and works for accepted receipts after a pause.
      },
    );
  }

  Future<dynamic> repeatPayrollCommand(
    String employeeId, {
    bool profile = false,
  }) {
    final key = 'payroll-${profile ? 'profile' : 'run'}-$employeeId';
    final path = profile ? '/payroll/profiles' : '/payroll/runs';
    return _repeatWorkflowCommand(
      key,
      matches: (stored) => stored == path,
      readPath: '$path?employee_id=$employeeId',
      verifyState: (state) {
        final items = state['items'];
        if (state['employee_id'] != employeeId ||
            items is! List ||
            items.any(
              (item) => item is! Map || item['employee_id'] != employeeId,
            )) {
          throw const ApiException(
            502,
            'Die Lohnübersicht gehört nicht eindeutig zum gewählten Mitarbeiter.',
          );
        }
      },
      requireRights: () {
        if (!RegExp(r'^[a-f0-9]{32}$').hasMatch(employeeId) ||
            projectId != null ||
            !hasFeature('german_payroll_2026') ||
            !hasModule('payroll') ||
            !can('personnel.read') ||
            !canWrite(profile ? 'personnel.write' : 'personnel.approve') ||
            _pending[key]?.body['employee_id'] != employeeId) {
          throw const ApiException(
            403,
            'Aktuelle Rechte für diesen Lohnvorgang fehlen.',
          );
        }
        if (!sectionEnabled('personnel')) {
          throw const ApiException(423, 'Personal ist fachlich deaktiviert.');
        }
      },
    );
  }

  Future<dynamic> repeatPersonnelCommand(String key) => _repeatWorkflowCommand(
    key,
    matches: (path) => path.startsWith('/personnel/'),
    requireRights: () {
      if (projectId != null ||
          !hasFeature('personnel_preparation') ||
          !hasModule('personnel_workflow') ||
          readonly ||
          (!can('personnel.read') && !can('time.own'))) {
        throw const ApiException(
          403,
          'Aktuelle Rechte für den Personalvorgang fehlen.',
        );
      }
      if (!sectionEnabled('personnel')) {
        throw const ApiException(423, 'Personal ist fachlich deaktiviert.');
      }
      // Object-specific own/approve/export rights are rechecked by the domain
      // before it can return an existing receipt or create another revision.
    },
  );

  Future<dynamic> repeatProjectEconomicsCommand(
    String project,
    String receipt,
  ) async {
    final epoch = _epoch;
    _guard(epoch);
    if (!RegExp(r'^[a-f0-9]{32}$').hasMatch(project) ||
        !RegExp(r'^[a-f0-9]{32}$').hasMatch(receipt)) {
      throw const ApiException(400, 'Ungültige Projekt- oder Belegkennung.');
    }
    final key = 'project-economics-$project-$receipt';
    final operation = _pending[key];
    if (operation == null || operation.path != '/project-economics/confirm') {
      throw const ApiException(
        409,
        'Die frühere Übertragung wurde inzwischen beantwortet. Bitte den Stand neu laden.',
      );
    }
    await load();
    _guard(epoch);
    if (error != null || loading) {
      throw const ApiException(
        0,
        'Die aktuellen Berechtigungen konnten noch nicht bestätigt werden.',
      );
    }
    void requireRights() {
      _guard(epoch);
      if (projectId != project ||
          !hasFeature('project_economics') ||
          !hasModule('project_economics') ||
          !can('finance.read') ||
          !canWrite('finance.write') ||
          !canWrite('finance.approve')) {
        throw const ApiException(
          403,
          'Die Projekteingangsbelege sind nicht zur Einordnung freigegeben.',
        );
      }
      if (!sectionEnabled('finance')) {
        throw const ApiException(423, 'Finanzen ist fachlich deaktiviert.');
      }
    }

    requireRights();
    await read(query('/project-economics/receipts/$receipt'));
    requireRights();
    if (_pending[key]?.body['request_id'] != operation.body['request_id']) {
      throw const ApiException(
        409,
        'Die frühere Übertragung wurde inzwischen beantwortet. Bitte den Stand neu laden.',
      );
    }
    return _command(
      key,
      operation.path,
      Map<String, dynamic>.from(jsonDecode(operation.values)),
      documentaryRetry: true,
    );
  }

  /// Resume the exact original upload/capture/review after uncertain delivery.
  /// The token and source rights are refreshed; a new nonce is never invented.
  Future<dynamic> repeatProjectReceiptCommand(
    String project,
    String id, {
    bool review = false,
    String? phase,
  }) async {
    final epoch = _epoch;
    _guard(epoch);
    final kind = phase ?? (review ? 'review' : 'capture');
    if (!RegExp(r'^[a-f0-9]{32}$').hasMatch(project) ||
        !RegExp(r'^[a-f0-9]{32}$').hasMatch(id) ||
        !const {
          'capture',
          'review',
          'media',
          'media-complete',
        }.contains(kind)) {
      throw const ApiException(400, 'Ungültige Belegübertragung.');
    }
    final key = 'project-receipt-$kind-$project-$id';
    final operation = _pending[key];
    if (operation == null || !_projectReceiptCommand(key, operation.path)) {
      throw const ApiException(
        409,
        'Die frühere Übertragung wurde inzwischen beantwortet. Bitte den Stand neu laden.',
      );
    }
    await load();
    _guard(epoch);
    if (error != null || loading) {
      throw const ApiException(
        0,
        'Die aktuellen Berechtigungen konnten noch nicht bestätigt werden.',
      );
    }
    void requireRights() {
      _guard(epoch);
      if (projectId != project ||
          !can('finance.read') ||
          !canWrite('finance.write') ||
          (kind == 'review' && !canWrite('finance.approve')) ||
          !hasModule('finance') ||
          (kind.startsWith('media') && !hasModule('operations'))) {
        throw const ApiException(
          403,
          'Die Eingangsbelege sind nicht zur Bearbeitung freigegeben.',
        );
      }
      if (!sectionEnabled('finance')) {
        throw const ApiException(423, 'Finanzen ist fachlich deaktiviert.');
      }
    }

    requireRights();
    if (kind == 'review') {
      await read('/finance/receipts/$id');
      requireRights();
    }
    if (_pending[key]?.body['request_id'] != operation.body['request_id']) {
      throw const ApiException(
        409,
        'Die frühere Übertragung wurde inzwischen beantwortet. Bitte den Stand neu laden.',
      );
    }
    return _command(
      key,
      operation.path,
      Map<String, dynamic>.from(jsonDecode(operation.values)),
      documentaryRetry: true,
    );
  }

  bool _projectReceiptCommand(String key, String path) {
    final match = RegExp(
      r'^project-receipt-(capture|review|media|media-complete)-([a-f0-9]{32})-([a-f0-9]{32})$',
    ).firstMatch(key);
    if (match == null) return false;
    return switch (match.group(1)) {
      'capture' => path == '/finance/receipts',
      'review' => path == '/finance/receipts/${match.group(3)}',
      'media' => path == '/receipt-media',
      'media-complete' => RegExp(
        r'^/receipt-media/[a-f0-9]{32}/complete$',
      ).hasMatch(path),
      _ => false,
    };
  }

  Future<dynamic> previewPreparationProfile(Map<String, dynamic> values) async {
    final epoch = _epoch;
    _requirePreparationProfileRights(epoch);
    final capturedGeneration = generation;
    try {
      final result = await api.call(
        path('/accounting/profile/preview'),
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
    } on ApiException catch (error) {
      if (error.status == 401) revoke();
      rethrow;
    }
  }

  Future<dynamic> _repeatAccountingCommand(
    String eventId,
    String domain,
  ) async {
    final epoch = _epoch;
    _guard(epoch);
    final key = 'accounting-$domain-$eventId';
    final storedPath = _pendingAccountingPath(eventId, domain);
    final operation = _pending[key];
    if (storedPath == null || operation == null) {
      throw const ApiException(
        409,
        'Die frühere Übertragung wurde inzwischen beantwortet. Bitte den Stand neu laden.',
      );
    }
    await load();
    _guard(epoch);
    if (error != null || loading) {
      throw const ApiException(
        0,
        'Die aktuellen Berechtigungen konnten noch nicht bestätigt werden.',
      );
    }
    final currentWriter = storedPath.contains('/$domain/v2/');
    final refund = domain == 'refunds';
    void requireRights() {
      _guard(epoch);
      if (projectId != null ||
          !hasModule(
            refund
                ? (currentWriter
                      ? 'accounting_refunds_v2'
                      : 'accounting_refunds')
                : (currentWriter
                      ? 'accounting_capacity'
                      : 'accounting_components'),
          ) ||
          !hasFeature(
            refund
                ? (currentWriter
                      ? 'accounting_refund_origins_v2'
                      : 'accounting_refund_origins')
                : (currentWriter
                      ? 'accounting_document_component_reuse'
                      : 'accounting_document_components'),
          ) ||
          !can('accounting.read') ||
          !can('finance.read') ||
          !canWrite('accounting.prepare') ||
          !canWrite('finance.write')) {
        throw const ApiException(
          403,
          'Die aktuelle Berechtigung zur Belegdokumentation fehlt.',
        );
      }
      if (!sectionEnabled('finance')) {
        throw const ApiException(423, 'Finanzen ist fachlich deaktiviert.');
      }
    }

    requireRights();
    await read('/accounting/events/$eventId');
    final fresh = businessMap(
      await read(storedPath.replaceFirst(RegExp(r'/confirm$'), '')),
    );
    requireRights();
    if (fresh['writes_allowed'] != true) {
      throw const ApiException(
        423,
        'Neue Belegdokumentationen sind derzeit gesperrt.',
      );
    }
    if (_pending[key]?.body['request_id'] != operation.body['request_id']) {
      throw const ApiException(
        409,
        'Die frühere Übertragung wurde inzwischen beantwortet. Bitte den Stand neu laden.',
      );
    }
    return _command(
      key,
      storedPath,
      Map<String, dynamic>.from(jsonDecode(operation.values)),
      documentaryRetry: true,
    );
  }

  final _pendingEditorValues = <String, Map<String, dynamic>>{};
  Map<String, dynamic>? pendingEditorValues(String key) {
    final values = _pendingEditorValues[key];
    if (!allowed || !pending(key)) return null;
    if (values == null && key.startsWith('custom-fields-')) {
      final body = _pending[key]!.body;
      final definition = body['definition'];
      if (definition is Map) {
        final fields = <String, dynamic>{
          ...businessMap(definition),
          'reason': body['reason'] ?? '',
        };
        for (final option in businessItems(definition['options'] ?? [])) {
          fields['label_${option['id']}'] = option['label'];
          fields['active_${option['id']}'] = '${option['active']}';
        }
        return fields;
      }
      return <String, dynamic>{
        for (final entry in businessMap(body['values']).entries)
          entry.key: entry.value == null ? '' : '${entry.value}',
        'reason': body['reason'] ?? '',
      };
    }
    if (values == null) return null;
    return Map<String, dynamic>.from(jsonDecode(jsonEncode(values)));
  }

  void preservePendingEditor(
    String key,
    Map<String, dynamic> values, {
    ApiException? commandError,
  }) {
    if (commandError != null &&
        (commandError is! BusinessCommandException ||
            !identical(commandError.owner, this) ||
            commandError.key != key ||
            commandError.requestId != _pending[key]?.body['request_id'])) {
      return;
    }
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
    _ownedGlobalSession?.revoke();
    for (final child in _projectSessions.values) {
      child.revoke();
    }
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

  Future<void>? _loadingFuture;

  /// A workflow and the periodic refresh must observe the same completed
  /// capability read. Returning an already completed future while another read
  /// was pending incorrectly made callers reject still-loading permissions.
  Future<void> load() {
    final current = _loadingFuture;
    if (current != null) return current;
    final completion = Completer<void>();
    final future = completion.future;
    _loadingFuture = future;
    _loadCapabilities().then(
      (_) {
        if (identical(_loadingFuture, future)) _loadingFuture = null;
        completion.complete();
      },
      onError: (Object error, StackTrace stack) {
        if (identical(_loadingFuture, future)) _loadingFuture = null;
        completion.completeError(error, stack);
      },
    );
    return future;
  }

  Future<void> _loadCapabilities() async {
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
    Map<String, dynamic> values, {
    void Function(dynamic)? validateResult,
  }) => _command(key, path, values, validateResult: validateResult);

  Future<dynamic> _command(
    String key,
    String path,
    Map<String, dynamic> values, {
    bool documentaryRetry = false,
    void Function(dynamic)? validateResult,
  }) async {
    final epoch = _epoch;
    _guard(epoch);
    final portalRevocation =
        (hasFeature('offer_portal') &&
            RegExp(r'^/portal/grants/[a-f0-9]{32}/revoke$').hasMatch(path)) ||
        (hasFeature('customer_workspace_portal') &&
            RegExp(
              r'^/customer-workspace/(?:grants|files)/[a-f0-9]{32}/revoke$',
            ).hasMatch(path));
    final documentaryMatch = RegExp(
      r'^/accounting/(components|refunds)/(?:v2/)?events/([a-f0-9]{32})/confirm$',
    ).firstMatch(path);
    final documentaryCommand =
        _datedCatalogConsumer(key, path, values) ||
        _catalogPricesCommand(key, path) ||
        _companyEventCommand(key, path, values) ||
        _catalogCommand(key, path) ||
        (key.startsWith('opening-item-') &&
            const [
              '/accounting/open-items/originals',
              '/accounting/open-items/confirm',
            ].contains(path)) ||
        (key.startsWith('accounting-year-values-') &&
            const [
              '/accounting/year-values/originals',
              '/accounting/year-values/confirm',
            ].contains(path)) ||
        (key.startsWith('historical-asset-') &&
            const [
              '/accounting/historical-assets/originals',
              '/accounting/historical-assets/confirm',
            ].contains(path)) ||
        (key.startsWith('accounting-opening-') &&
            const [
              '/accounting/opening-balances/originals',
              '/accounting/opening-balances/confirm',
            ].contains(path)) ||
        _projectReceiptCommand(key, path) ||
        path.startsWith('/customer-workspace/') ||
        path.startsWith('/personnel/') ||
        path.startsWith('/payroll/') ||
        path == '/inventory/counts' ||
        path.startsWith('/inventory/counts/') ||
        path.startsWith('/assistant/') ||
        path.startsWith('/sales/') ||
        path.startsWith('/company-handover/') ||
        path.startsWith('/custom-fields/') ||
        path.startsWith('/service/cases') ||
        path.startsWith('/resource-custody/') ||
        path.startsWith('/bank/') ||
        (key.startsWith('purchase-change-') &&
            RegExp(
              r'^/purchasing/orders/[a-f0-9]{32}/(change-files|amendments|supplier-returns)$',
            ).hasMatch(path)) ||
        path == '/migrations' ||
        path.startsWith('/migrations/') ||
        (path == '/accounting/euer/confirm' && key == 'accounting-euer') ||
        (path == '/accounting/profile/confirm' &&
            key == 'accounting-profile') ||
        (path == '/project-economics/confirm' &&
            RegExp(r'^project-economics-[a-f0-9]{32}-[a-f0-9]{32}$')
                .hasMatch(key)) ||
        (documentaryMatch != null &&
            key ==
                'accounting-${documentaryMatch.group(1)}-${documentaryMatch.group(2)}');
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
            (!portalRevocation &&
                !(documentaryRetry && documentaryCommand) &&
                previous.generation != generation))) {
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
          validateResult: validateResult,
        );
    _pending[key] = operation;
    final requestGeneration = generation;
    try {
      final result = await api.call(
        this.path(path),
        Map<String, dynamic>.from(operation.body),
      );
      _guard(epoch);
      if (_pending[key]?.body['request_id'] != operation.body['request_id']) {
        throw const ApiException(
          0,
          'Die frühere Übertragung wurde inzwischen beantwortet. Bitte den aktuellen Stand neu laden.',
        );
      }
      if (documentaryCommand && generation != requestGeneration) {
        throw const ApiException(
          0,
          'Der Funktionsstand hat sich während der Übertragung geändert. Der Vorgang bleibt unbestätigt und kann unverändert erneut gesendet werden.',
        );
      }
      if (!portalRevocation &&
          !documentaryCommand &&
          generation != operation.generation)
        throw const ApiException(
          409,
          'Der Funktionsstand wurde geändert. Bitte den gespeicherten Stand prüfen, bevor Sie fortfahren.',
        );
      operation.validateResult?.call(result);
      _pending.remove(key);
      _pendingEditorValues.remove(key);
      if (hasFeature('organization_modules') &&
          RegExp(r'^/employees(?:/[a-f0-9]{32})?$').hasMatch(path)) {
        await load();
      }
      return result;
    } on ApiException catch (e, stack) {
      if (_pending[key]?.body['request_id'] == operation.body['request_id'] &&
          e.status != 0 &&
          e.status < 500 &&
          e.status != 429 &&
          e.status != 423 &&
          !(documentaryCommand &&
              e.status == 409 &&
              e.requestResolution != 'not_accepted') &&
          !(documentaryCommand && (e.status == 403 || e.status == 404))) {
        _pending.remove(key);
        _pendingEditorValues.remove(key);
      }
      if (e.status == 401) revoke();
      Error.throwWithStackTrace(
        BusinessCommandException(
          this,
          key,
          operation.body['request_id'] as String,
          e,
        ),
        stack,
      );
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

  Future<dynamic> previewReusableDocumentComponents(
    String eventId,
    Map<String, dynamic> values,
  ) async {
    final epoch = _epoch;
    _guard(epoch);
    if (!RegExp(r'^[a-f0-9]{32}$').hasMatch(eventId) ||
        projectId != null ||
        !hasFeature('accounting_document_component_reuse') ||
        !hasModule('accounting_capacity') ||
        !can('accounting.read') ||
        !can('finance.read') ||
        !canWrite('accounting.prepare') ||
        !canWrite('finance.write')) {
      throw const ApiException(
        403,
        'Die Wiederverwendung von Belegbeträgen ist nicht freigegeben.',
      );
    }
    if (!sectionEnabled('finance')) {
      throw const ApiException(423, 'Finanzen ist fachlich deaktiviert.');
    }
    final capturedGeneration = generation;
    try {
      final result = await api.call(
        path('/accounting/components/v2/events/$eventId/preview'),
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
  Future<dynamic> previewRefundOrigins(
    String eventId,
    Map<String, dynamic> values,
  ) async {
    final epoch = _epoch;
    _guard(epoch);
    if (!RegExp(r'^[a-f0-9]{32}$').hasMatch(eventId) ||
        projectId != null ||
        !hasFeature('accounting_refund_origins') ||
        !hasModule('accounting_refunds') ||
        !can('accounting.read') ||
        !can('finance.read') ||
        !canWrite('accounting.prepare') ||
        !canWrite('finance.write')) {
      throw const ApiException(
        403,
        'Die Erstattungsursprungsbindung ist nicht freigegeben.',
      );
    }
    if (!sectionEnabled('finance')) {
      throw const ApiException(423, 'Finanzen ist fachlich deaktiviert.');
    }
    final capturedGeneration = generation;
    try {
      final result = await api.call(
        path('/accounting/refunds/events/$eventId/preview'),
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

  Future<dynamic> previewVersionedRefundOrigins(
    String eventId,
    Map<String, dynamic> values,
  ) async {
    final epoch = _epoch;
    _guard(epoch);
    if (!RegExp(r'^[a-f0-9]{32}$').hasMatch(eventId) ||
        projectId != null ||
        !hasFeature('accounting_refund_origins_v2') ||
        !hasModule('accounting_refunds_v2') ||
        !can('accounting.read') ||
        !can('finance.read') ||
        !canWrite('accounting.prepare') ||
        !canWrite('finance.write')) {
      throw const ApiException(
        403,
        'Die Erstattungsursprungsbindung ist nicht freigegeben.',
      );
    }
    if (!sectionEnabled('finance')) {
      throw const ApiException(423, 'Finanzen ist fachlich deaktiviert.');
    }
    final capturedGeneration = generation;
    try {
      final result = await api.call(
        path('/accounting/refunds/v2/events/$eventId/preview'),
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
    for (final child in _projectSessions.values) {
      child.dispose();
    }
    _projectSessions.clear();
    _ownedGlobalSession?.dispose();
    _ownedGlobalSession = null;
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

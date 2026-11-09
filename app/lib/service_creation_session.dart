part of 'business_session.dart';

bool _manualServiceCreation(
  String key,
  String path,
  Map<String, dynamic> body,
) =>
    key == 'service-case-new' &&
    path == '/service/cases' &&
    body['revision'] == 0 &&
    !body.containsKey('id') &&
    ['inquiry_id', 'defect_id', 'visit_id'].every((key) => body[key] == null);

class _ServiceCreationContext {
  final ProjectCreationScope scope;
  final ServiceCreationJournalSession journal;
  final Map<String, dynamic> actor;
  final void Function() check;
  _ServiceCreationContext(this.scope, this.journal, this.actor, this.check);
}

extension DurableServiceCreation on BusinessSession {
  String _serviceCreationScopeKey() =>
      serviceCreationCanonical([api.base, api.version, projectCreationScope]);

  bool _serviceCreationVisible(String key) =>
      key != 'service-case-new' ||
      _serviceCreationMemoryScope == null ||
      (_serviceCreationMemoryScope == _serviceCreationScopeKey() &&
          allowed &&
          hasFeature('service_cases') &&
          hasModule('service') &&
          can('contacts.read'));

  void _retireChangedServiceCreation() {
    if (_serviceCreationVisible('service-case-new')) return;
    _pending.remove('service-case-new');
    _pendingEditorValues.remove('service-case-new');
    _serviceCreationMemoryScope = null;
  }

  void _serviceCreationRights(BusinessSession scope, String? project) {
    if (scope.error != null ||
        scope.loading ||
        !scope.hasFeature('service_cases') ||
        !scope.hasModule('service') ||
        scope.readonly ||
        !scope.can('contacts.read') ||
        (project == null
            ? !scope.canWrite('contacts.write')
            : !scope.can('documents.read') ||
                  !scope.canWrite('documents.write'))) {
      throw const ApiException(
        403,
        'Die aktuellen Rechte für den geschützten Serviceauftrag fehlen. Das Original bleibt erhalten.',
      );
    }
  }

  Future<_ServiceCreationContext> _openServiceCreation({
    bool Function()? stillCurrent,
  }) async {
    final epoch = _epoch;
    final host = api.base, version = api.version;
    void active() {
      _guard(epoch);
      if (api.base != host ||
          api.version != version ||
          stillCurrent?.call() == false) {
        throw const ApiException(
          0,
          'Der Servicekontext wurde geschlossen. Der Originalauftrag bleibt erhalten.',
        );
      }
    }

    active();
    await load();
    active();
    if (error != null || loading) {
      throw ApiException(
        0,
        error ?? 'Die aktuellen Servicerechte werden noch geladen. Bitte erneut öffnen.',
      );
    }
    if (!hasFeature('service_cases') ||
        !hasModule('service') ||
        readonly ||
        !can('contacts.read')) {
      throw const ApiException(
        403,
        'Aktuelle Servicerechte konnten nicht bestätigt werden.',
      );
    }
    if (!hasFeature('project_creation_journal')) {
      throw const ApiException(
        0,
        'Die Firmenbindung für einen dauerhaften Serviceauftrag fehlt. Es wurde nichts gesendet.',
      );
    }
    final actor = businessMap(await api.call('/api/me'));
    active();
    if (projectCreationScope?['schema_version'] is! int) {
      throw const ApiException(
        0,
        'Die Version der Firmenbindung konnte nicht bestätigt werden.',
      );
    }
    final scope = ProjectCreationScope.fromServer(
      projectCreationScope,
      server: host,
      version: version,
      accountId: actor['id'],
    );
    final capturedGeneration = generation;
    void current() {
      active();
      final now = ProjectCreationScope.fromServer(
        projectCreationScope,
        server: api.base,
        version: api.version,
        accountId: actor['id'],
      );
      if (generation != capturedGeneration ||
          serviceCreationCanonical(now.toJson()) !=
              serviceCreationCanonical(scope.toJson())) {
        throw const ApiException(
          0,
          'Die Firmenfreigabe wurde geändert. Der Originalauftrag bleibt erhalten.',
        );
      }
      if (!hasFeature('service_cases') ||
          !hasModule('service') ||
          !can('contacts.read') ||
          readonly) {
        throw const ApiException(
          403,
          'Die aktuelle Freigabe des Serviceauftrags fehlt.',
        );
      }
    }

    final journal = await _serviceCreationJournal.open(
      scope: scope,
      requireCurrent: current,
    );
    current();
    return _ServiceCreationContext(scope, journal, actor, current);
  }

  Future<void> _verifyServiceCreationAccess(
    _ServiceCreationContext context,
    Map<String, dynamic> body,
  ) async {
    context.check();
    final project = body['project_id'] as String?;
    if (projectId != null && project != projectId) {
      throw const ApiException(
        403,
        'Der offene Serviceauftrag gehört zu einem anderen Projekt.',
      );
    }
    final scope = project == null || project == projectId
        ? this
        : sharedProjectSession(project);
    await scope.load();
    context.check();
    _serviceCreationRights(scope, project);
    if (project == null && context.actor['role'] != 'owner') {
      throw const ApiException(
        403,
        'Servicefälle ohne Projekt benötigen die Geschäftsführung.',
      );
    }
    final query = Uri(
      queryParameters: {
        'customer_id': body['customer_id'] as String,
        if (project != null) 'project_id': project,
      },
    ).query;
    final sources = businessMap(
      await api.call(path('/service/options?$query')),
    );
    context.check();
    _serviceCreationRights(scope, project);
    if (sources['customer_id'] != body['customer_id'] ||
        sources['project_id'] != project) {
      throw const ApiException(
        0,
        'Der ursprüngliche Kunden- und Projektbezug konnte nicht bestätigt werden.',
      );
    }
  }

  void _restoreServiceCreationPending(Map<String, dynamic> body) {
    const key = 'service-case-new';
    final values = {...body}..remove('request_id');
    final previous = _pending[key];
    if (previous != null &&
        (previous.path != '/service/cases' ||
            serviceCreationCanonical(previous.body) !=
                serviceCreationCanonical(body))) {
      throw const ApiException(
        409,
        'Ein anderer Serviceauftrag ist noch unbestätigt. Das Original bleibt erhalten.',
      );
    }
    _pending[key] = (
      path: '/service/cases',
      values: jsonEncode(values),
      generation: generation,
      body: Map<String, dynamic>.from(jsonDecode(jsonEncode(body))),
      validateResult: previous?.validateResult,
    );
    _serviceCreationMemoryScope = _serviceCreationScopeKey();
    _pendingEditorValues[key] = {
      for (final key in [
        'title',
        'kind',
        'priority',
        'responsible_id',
        'description',
      ])
        key: body[key],
      'follow_up_on': body['follow_up_on'] ?? '',
      for (final key in ['person_id', 'asset_id', 'contract_id'])
        key: body[key] ?? '',
      'origin': '',
    };
  }

  /// Explicitly opens an unresolved manual creation after fresh online checks.
  /// Merely loading a session never sends or exposes a retained command.
  Future<bool> restoreServiceCreation({bool Function()? stillCurrent}) async {
    final context = await _openServiceCreation(stillCurrent: stillCurrent);
    final body = context.journal.pending;
    if (body == null) return false;
    await _verifyServiceCreationAccess(context, body);
    context.check();
    _restoreServiceCreationPending(body);
    return true;
  }

  Future<dynamic> _createManualServiceCase(
    Map<String, dynamic> values, {
    void Function(dynamic)? validateResult,
    bool Function()? stillCurrent,
  }) async {
    final frozenValues = Map<String, dynamic>.from(
      jsonDecode(jsonEncode(values)),
    );
    final context = await _openServiceCreation(stillCurrent: stillCurrent);
    final saved = context.journal.pending;
    final retained = saved ?? _pending['service-case-new']?.body;
    final body = validateServiceCreationCommand({
      ...frozenValues,
      'request_id': retained?['request_id'] ?? offlineId(),
    });
    if (retained != null &&
        serviceCreationCanonical(retained) != serviceCreationCanonical(body)) {
      throw const ApiException(
        409,
        'Der ursprüngliche Serviceauftrag ist noch unbestätigt. Bitte diesen unverändert wiederholen.',
      );
    }
    await _verifyServiceCreationAccess(context, body);
    context.check();
    await context.journal.prepare(body);
    context.check();
    _restoreServiceCreationPending(body);
    var responseReturned = false;
    try {
      final result = await api.call(
        path('/service/cases'),
        Map<String, dynamic>.from(jsonDecode(jsonEncode(body))),
      );
      responseReturned = true;
      context.check();
      _verifyServiceCreationReceipt(body, result, context.scope.accountId);
      validateResult?.call(result);
      await context.journal.clear(body);
      context.check();
      if (_pending['service-case-new']?.body['request_id'] ==
          body['request_id']) {
        _pending.remove('service-case-new');
        _pendingEditorValues.remove('service-case-new');
      }
      return result;
    } on ApiException catch (error, stack) {
      // Only an explicit server assertion proves an ambiguous POST had no effect.
      if (!responseReturned &&
          error.status == 409 &&
          error.requestResolution == 'not_accepted') {
        context.check();
        await context.journal.clear(body);
        context.check();
        _pending.remove('service-case-new');
        _pendingEditorValues.remove('service-case-new');
      }
      if (error.status == 401) revoke();
      Error.throwWithStackTrace(
        BusinessCommandException(
          this,
          'service-case-new',
          body['request_id'] as String,
          error,
        ),
        stack,
      );
    }
  }
}

// Python str.strip uses these whitespace code points; preserve the original
// request, comparing only the server's documented normalized text fields.
String serviceCreationServerText(String value) => value.replaceAll(
  RegExp(
    r'^[\u0009-\u000d\u001c-\u0020\u0085\u00a0\u1680\u2000-\u200a\u2028\u2029\u202f\u205f\u3000]+|[\u0009-\u000d\u001c-\u0020\u0085\u00a0\u1680\u2000-\u200a\u2028\u2029\u202f\u205f\u3000]+$',
  ),
  '',
);

void _verifyServiceCreationReceipt(
  Map<String, dynamic> body,
  dynamic result,
  String account,
) {
  bool id(dynamic value) =>
      value is String &&
      value.length == 32 &&
      RegExp(r'^[a-f0-9]{32}$').hasMatch(value);
  if (result is! Map ||
      !id(result['id']) ||
      result['revision'] is! int ||
      result['revision'] != 1 ||
      result['created_by'] != account ||
      result['updated_by'] != account ||
      result['status'] != 'open' ||
      result['origin_kind'] != 'manual' ||
      !result.containsKey('origin_id') ||
      result['origin_id'] != null ||
      result['source_sha256'] is! String ||
      !RegExp(r'^[a-f0-9]{64}$').hasMatch(result['source_sha256']) ||
      ['created_at', 'updated_at'].any(
        (key) =>
            result[key] is! String || DateTime.tryParse(result[key]) == null,
      )) {
    throw const ApiException(
      0,
      'Die ursprüngliche Serviceanlage konnte nicht vollständig bestätigt werden. Der Auftrag bleibt erhalten.',
    );
  }
  for (final entry in body.entries) {
    if (['request_id', 'revision'].contains(entry.key)) continue;
    final expected = ['title', 'description'].contains(entry.key)
        ? serviceCreationServerText(entry.value as String)
        : entry.value;
    if (!result.containsKey(entry.key) || result[entry.key] != expected) {
      throw const ApiException(
        0,
        'Die Fallantwort bestätigt nicht alle ursprünglichen Angaben. Der Auftrag bleibt erhalten.',
      );
    }
  }
}

part of 'offline_plans.dart';

const _offlineQueues = [
  'outbox',
  'import_outbox',
  'plan_delete_outbox',
  'import_delete_outbox',
  'workspace_outbox',
  'business_time_outbox',
  'business_media_outbox',
  'service_report_outbox',
];

String _offlineNamespace(
  String server,
  String version,
  OfflineBinding binding,
) => jsonEncode([
  'smartplan-offline-v2',
  server,
  version,
  binding.instanceId,
  binding.accountId,
]);
String _offlineIndex(String server, String version) =>
    jsonEncode(['smartplan-offline-v2-selection', server, version]);

class _OfflineActivation {
  OfflineVault? vault;
  Map<String, dynamic>? state;
  OfflineBinding? binding;
  String? token, host, version;

  Future<void> cancel() async {
    if (vault != null && state != null) {
      try {
        final latest = await vault!.read();
        if (latest != null &&
            binding != null &&
            OfflineBinding.fromJson(latest['binding']) == binding) {
          await vault!.write({...latest, 'locked': true});
        }
      } catch (_) {
        // A newer writer wins; never replace its snapshot or delete a file.
      }
    }
    if (token != null && binding != null && host != null) {
      final revoke = OfficeApi(baseUrl: host, apiVersion: version);
      revoke.configureOfflineSession(token!, binding!.headerValue);
      unawaited(
        revoke
            .call('/api/offline/logout', {})
            .then<void>((_) {}, onError: (Object error, StackTrace stack) {})
            .whenComplete(revoke.dispose),
      );
    }
  }
}

Set<String> _queuedOrigins(Map<String, dynamic> state) {
  final result = <String>{};
  for (final name in _offlineQueues) {
    final values = state[name] ?? const [];
    if (values is! List)
      throw const FormatException('Ungültige Offlinewarteschlange.');
    for (final value in values) {
      final dynamic id;
      if (value is String) {
        id = value;
      } else if (value is Map) {
        id = name == 'business_time_outbox'
            ? (value['body'] is Map ? value['body']['request_id'] : null)
            : value['request_id'];
      } else {
        throw const FormatException('Ungültiger Offlineauftrag.');
      }
      if (id is! String ||
          !RegExp(r'^[a-f0-9]{32}$').hasMatch(id) ||
          !result.add(jsonEncode([name, id]))) {
        throw const FormatException(
          'Ungültige Herkunft eines Offlineauftrags.',
        );
      }
    }
  }
  return result;
}

void _checkQueueBindings(Map<String, dynamic> state, OfflineBinding binding) {
  final saved = state['queue_bindings'];
  if (saved is! Map)
    throw const FormatException(
      'Offlineaufträge haben keine gesicherte Firmenbindung.',
    );
  final keys = _queuedOrigins(state);
  if (saved.length != keys.length || !keys.every(saved.containsKey))
    throw const FormatException(
      'Offlineaufträge und Herkunft stimmen nicht überein.',
    );
  for (final key in keys) {
    if (OfflineBinding.fromJson(saved[key]) != binding)
      throw const FormatException(
        'Ein Offlineauftrag gehört zu einer anderen Firma.',
      );
  }
}

void _bindNewQueues(
  Map<String, dynamic> previous,
  Map<String, dynamic> next,
  OfflineBinding binding,
) {
  _checkQueueBindings(previous, binding);
  final old = previous['queue_bindings'] as Map;
  next['queue_bindings'] = {
    for (final key in _queuedOrigins(next)) key: old[key] ?? binding.toJson(),
  };
  _checkQueueBindings(next, binding);
}

extension OfflineInstanceV2 on OfflinePlans {
  OfflineBinding? get binding => _binding;

  bool _matchesBoundState(Map<String, dynamic> state) {
    try {
      return _binding != null &&
          _storageNamespace ==
              _offlineNamespace(api.base, api.version, _binding!) &&
          state['cache_schema'] == 2 &&
          state['server'] == server &&
          OfflineBinding.fromJson(state['binding']) == _binding &&
          state['user']?['id'] == _binding!.accountId;
    } catch (_) {
      return false;
    }
  }

  void _activationCurrent(
    int epoch,
    String? token,
    String host,
    String version,
  ) {
    if (_disposed ||
        epoch != _epoch ||
        api.token != token ||
        api.base != host ||
        api.version != version)
      throw const ApiException(
        0,
        'Die Anmeldung wurde gewechselt. Der bisherige Offlinebestand bleibt erhalten.',
      );
  }

  Future<void> _activate(
    Future<void> Function(int epoch, _OfflineActivation stage) action,
  ) {
    final epoch = ++_epoch;
    _timer?.cancel();
    _state = null;
    _vault = null;
    _binding = null;
    _storageNamespace = null;
    _onlineToken = null;
    transport.token = null;
    changed();
    final next = _activationTail.then((_) async {
      await _tail;
      if (_disposed || epoch != _epoch)
        throw const ApiException(0, 'Die Offlineanmeldung wurde gewechselt.');
      final stage = _OfflineActivation();
      try {
        await action(epoch, stage);
      } catch (_) {
        await stage.cancel();
        rethrow;
      }
    });
    _activationTail = next.then<void>(
      (_) {},
      onError: (Object e, StackTrace s) {},
    );
    return next;
  }

  Future<void> _checkVault(OfflineVault vault) async {
    if (!await vault.directory.exists()) return;
    await for (final entry in vault.directory.list(followLinks: false)) {
      final name = entry.uri.pathSegments.last;
      if (name.startsWith('state-') &&
          !RegExp(r'^state-\d{16}\.enc$').hasMatch(name))
        throw const FormatException(
          'Ein Offline-Speicherstand wartet auf eine ausdrückliche Prüfung.',
        );
    }
  }

  void _validateCache(
    Map<String, dynamic> state,
    OfflineBinding binding,
    String expectedServer,
  ) {
    if (state['cache_schema'] != 2 ||
        state['server'] != expectedServer ||
        state['user']?['id'] != binding.accountId ||
        OfflineBinding.fromJson(state['binding']) != binding)
      throw const FormatException(
        'Der Offlinebestand gehört nicht zu dieser Firma und Anmeldung.',
      );
    _checkQueueBindings(state, binding);
    for (final field in ['last_online', 'last_seen', 'server_expires_at']) {
      if (state[field] is! String || DateTime.tryParse(state[field]) == null)
        throw const FormatException('Ungültige Offlinefreigabe.');
    }
  }

  Future<void> _loginBound(
    Map<String, dynamic> person,
    List<dynamic> projects, {
    required bool businessTime,
    required bool fieldMedia,
    required bool offlineReports,
  }) {
    final host = api.base, version = api.version, onlineToken = api.token;
    final claimedUser = offlineCopy(person);
    return _activate((epoch, stage) async {
      void current() => _activationCurrent(epoch, onlineToken, host, version);
      current();
      if (onlineToken == null || onlineToken.startsWith('offline_'))
        throw const ApiException(
          401,
          'Für eine Offlinefreigabe bitte online anmelden.',
        );
      final discovery = OfflineDiscovery.parse(
        await api.call('/api/offline/context'),
        expectedAccountId: claimedUser['id'],
      );
      current();
      if (!discovery.isBound)
        throw const ApiException(
          0,
          'Dieser Server bestätigt keine Firmenbindung für neue Offlinearbeit. Vorhandene Altaufträge bleiben unverändert gesichert; online können Sie weiterarbeiten.',
        );
      final binding = discovery.binding!;
      final user = Map<String, dynamic>.from(await api.call('/api/me'));
      current();
      if (user['id'] != binding.accountId)
        throw const ApiException(
          0,
          'Die aktuelle Anmeldung gehört zu einer anderen Person.',
        );
      final projectCopy = offlineCopy({
        'items': await api.call('/api/projects'),
      })['items'];
      current();
      if (projectCopy is! List ||
          projectCopy.any((value) => value is! Map || value['id'] is! String))
        throw const ApiException(
          0,
          'Die aktuellen Projektfreigaben konnten nicht bestätigt werden.',
        );
      final business = businessTime || fieldMedia || offlineReports;
      final grant = OfflineGrant.parse(
        await api.call(
          business
              ? '/api/business/offline/access/v2'
              : '/api/offline/access/v2',
          {},
        ),
        expectedBinding: binding,
        kind: business ? 'business' : 'workspace',
      );
      stage
        ..binding = binding
        ..token = grant.token
        ..host = host
        ..version = version;
      current();
      final instant = clock().toUtc();
      if (!grant.expiresAt.isAfter(instant))
        throw const ApiException(
          401,
          'Die Offlinefreigabe ist bereits abgelaufen.',
        );
      final namespace = _offlineNamespace(host, version, binding);
      final vault = await device.open(
        namespace,
        binding.accountId,
        create: true,
      );
      current();
      await _checkVault(vault);
      current();
      final previous = await vault.read();
      current();
      if (previous != null) _validateCache(previous, binding, '$host|$version');
      final state =
          previous ??
          <String, dynamic>{'records': {}, 'outbox': [], 'queue_bindings': {}};
      stage
        ..vault = vault
        ..state = state
        ..binding = binding;
      final now = instant.toIso8601String();
      state.addAll({
        'cache_schema': 2,
        'server': '$host|$version',
        'binding': binding.toJson(),
        'grant_kind': grant.kind,
        'grant_token_hash': offlineBindingHash(grant.token),
        'offline_grant': {...grant.toJson()}..remove('token'),
        'user': user,
        'projects': projectCopy,
        'last_online': now,
        'last_seen': now,
        'server_expires_at': grant.expiresAt.toIso8601String(),
        'locked': false,
        'time_events_supported':
            businessTime && grant.capabilities.contains('time_events'),
        'field_media_supported':
            fieldMedia && grant.capabilities.contains('field_media'),
        'offline_reports_supported':
            offlineReports && grant.capabilities.contains('offline_reports'),
        'report_project_ids': grant.reportProjectIds ?? <String>[],
        'report_writes_enabled': grant.reportWritesEnabled ?? false,
        'imports_supported': grant.capabilities.contains('plan_imports'),
        'deletions_supported': grant.capabilities.contains('plan_deletion'),
        'workspace_supported':
            grant.capabilities.contains('offline_workspace') &&
            grant.capabilities.contains('project_workspace'),
      });
      for (final collection in [
        'records',
        'imports',
        'workspace_records',
        'service_report_records',
      ]) {
        for (final record in (state[collection] as Map? ?? {}).values) {
          if (record['sync_status'] == 'Zugriff gesperrt')
            record['sync_status'] = 'Wartet auf Verbindung';
        }
      }
      _checkQueueBindings(state, binding);
      await vault.write(state);
      current();
      await device.saveSession(namespace, binding.accountId, grant.token);
      current();
      await device.select(namespace, binding.accountId);
      current();
      await device.select(
        _offlineIndex(host, version),
        jsonEncode(binding.toJson()),
      );
      current();
      _vault = vault;
      _binding = binding;
      _storageNamespace = namespace;
      _onlineToken = onlineToken;
      _state = state;
      transport.configureOfflineSession(grant.token, binding.headerValue);
      notice = null;
      start();
      changed();
      unawaited(sync());
    });
  }

  Future<void> _resumeBound() {
    final host = api.base, version = api.version, onlineToken = api.token;
    return _activate((epoch, stage) async {
      void current() => _activationCurrent(epoch, onlineToken, host, version);
      if (!await device.unlock())
        throw const ApiException(0, 'Gerät wurde nicht entsperrt.');
      current();
      final selected = await device.selected(_offlineIndex(host, version));
      current();
      if (selected == null)
        throw const ApiException(
          0,
          'Noch keine firmengebundene Offlinefreigabe vorhanden. Bitte online anmelden. Ungeklärte Altaufträge bleiben gesichert und werden nicht übertragen.',
        );
      final binding = OfflineBinding.fromJson(jsonDecode(selected));
      if (onlineToken != null) {
        final discovery = OfflineDiscovery.parse(
          await api.call('/api/offline/context'),
          expectedAccountId: binding.accountId,
        );
        current();
        if (discovery.binding != binding)
          throw const ApiException(
            0,
            'Der gespeicherte Offlinebestand gehört zu einer anderen Firma. Es wurde nichts geöffnet oder übertragen.',
          );
      }
      final namespace = _offlineNamespace(host, version, binding);
      final account = await device.selected(namespace);
      current();
      if (account != binding.accountId)
        throw const FormatException(
          'Offlineauswahl und Firma stimmen nicht überein.',
        );
      final vault = await device.open(namespace, binding.accountId);
      current();
      await _checkVault(vault);
      current();
      final state = await vault.read();
      current();
      if (state == null)
        throw const FormatException('Firmengebundener Offlinebestand fehlt.');
      _validateCache(state, binding, '$host|$version');
      stage
        ..vault = vault
        ..state = state
        ..binding = binding;
      final token = await device.session(namespace, binding.accountId);
      current();
      if (token is! String ||
          state['grant_token_hash'] != offlineBindingHash(token))
        throw const FormatException(
          'Offline-Freigabe und geschützter Token gehören nicht zusammen. Bitte online erneuern.',
        );
      final grant = OfflineGrant.parse(
        {...Map<String, dynamic>.from(state['offline_grant']), 'token': token},
        expectedBinding: binding,
        kind: state['grant_kind'],
      );
      if (grant.expiresAt.toIso8601String() != state['server_expires_at'])
        throw const FormatException(
          'Offlineablauf und Originalfreigabe stimmen nicht überein.',
        );
      _vault = vault;
      _binding = binding;
      _storageNamespace = namespace;
      _onlineToken = onlineToken;
      _state = state;
      transport.configureOfflineSession(grant.token, binding.headerValue);
      try {
        requireAccess();
        await _change((_) {});
        current();
        await _cleanupDeletedAssets(epoch);
        current();
      } catch (_) {
        if (epoch == _epoch) {
          _state = null;
          _vault = null;
          _binding = null;
          _storageNamespace = null;
          _onlineToken = null;
          transport.token = null;
        }
        rethrow;
      }
      start();
      changed();
      unawaited(sync());
    });
  }

  void _transportCurrent(int epoch) {
    if (_disposed ||
        epoch != _epoch ||
        !permitted ||
        _binding == null ||
        transport.token == null ||
        transport.offlineBindingHeader != _binding!.headerValue)
      throw const ApiException(
        0,
        'Der ursprüngliche Offlinekontext wurde geschlossen. Es wurde nichts übertragen.',
      );
    _checkQueueBindings(_state!, _binding!);
  }

  Future<dynamic> _offlineCall(
    int epoch,
    String path, [
    Map<String, dynamic>? body,
  ]) {
    _transportCurrent(epoch);
    return transport.call(path, body);
  }

  Future<Uint8List> _offlineBytes(
    int epoch,
    String path, {
    required String mediaType,
    int maxBytes = 20 * 1024 * 1024,
  }) {
    _transportCurrent(epoch);
    return transport.bytes(path, mediaType: mediaType, maxBytes: maxBytes);
  }

  Future<dynamic> _offlineChunk(int epoch, String path, Uint8List bytes) {
    _transportCurrent(epoch);
    return transport.putChunk(path, bytes);
  }
}

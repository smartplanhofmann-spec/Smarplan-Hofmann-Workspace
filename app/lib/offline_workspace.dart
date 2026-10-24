part of 'offline_plans.dart';

const _workspaceFields = <String, Set<String>>{
  'profile': {
    'description',
    'site_address',
    'phase',
    'deposit_status',
    'materials_status',
    'start_date',
    'end_date',
  },
  'tasks': {
    'title',
    'details',
    'status',
    'priority',
    'due_date',
    'assignee_id',
  },
  'diary': {
    'entry_date',
    'work_performed',
    'issues',
    'next_steps',
    'weather',
    'crew_count',
  },
  'appointments': {'title', 'details', 'start_at', 'end_at', 'status'},
  'links': {'title', 'category', 'url', 'active'},
};

/// Project work shares the encrypted account writer and explicit seven-day
/// workspace grant. Inbox, reports and financial records never enter this cache.
extension OfflineWorkspace on OfflinePlans {
  bool get workspaceSupported =>
      permitted && _state?['workspace_supported'] == true;

  void _workspaceAccess(
    int epoch,
    String project, {
    bool write = false,
    bool profile = false,
  }) {
    _entryAccess(epoch, project, write: write);
    if (_state?['workspace_supported'] != true) {
      throw const ApiException(
        403,
        'Für die Offline-Projektmappe zuerst mit Verbindung neu anmelden.',
      );
    }
    if (write && profile && !['owner', 'manager'].contains(user['role'])) {
      throw const ApiException(
        403,
        'Die Projektübersicht dürfen nur Inhaber und Projektleitung ändern.',
      );
    }
  }

  String _workspaceKey(String project, String kind, String localId) =>
      '$project|$kind|$localId';

  String? _workspaceFind(
    Map<String, dynamic> state,
    String project,
    String kind,
    String id,
  ) {
    final records = state['workspace_records'] as Map? ?? {};
    for (final entry in records.entries) {
      final value = entry.value;
      if (value['project_id'] == project &&
          value['kind'] == kind &&
          (value['local_id'] == id || value['server_id'] == id))
        return entry.key as String;
    }
    return null;
  }

  Map<String, dynamic> _workspaceView(Map record) => offlineCopy({
    ...Map<String, dynamic>.from(record),
    'id': record['server_id'] ?? record['local_id'],
  });

  Map<String, dynamic>? getWorkspace(String project) {
    _entryAccess(_epoch, project);
    if (!workspaceSupported) return null;
    final snapshot = (_state?['workspace_snapshots'] as Map? ?? {})[project];
    if (snapshot == null) return null;
    final result = offlineCopy(Map<String, dynamic>.from(snapshot));
    final rows = (_state?['workspace_records'] as Map? ?? {}).values
        .where((record) => record['project_id'] == project)
        .toList();
    for (final kind in ['tasks', 'diary', 'appointments', 'links']) {
      result[kind] = rows
          .where((record) => record['kind'] == kind)
          .map((record) => _workspaceView(record as Map))
          .toList();
    }
    final profiles = rows.where((record) => record['kind'] == 'profile');
    if (profiles.isNotEmpty) result['profile'] = _workspaceView(profiles.first);
    final tasks = result['tasks'] as List;
    tasks.sort((a, b) {
      final closedA = ['done', 'cancelled'].contains(a['status']) ? 1 : 0;
      final closedB = ['done', 'cancelled'].contains(b['status']) ? 1 : 0;
      var order = closedA.compareTo(closedB);
      if (order == 0)
        order = (a['due_date'] as String? ?? '9999').compareTo(
          b['due_date'] as String? ?? '9999',
        );
      if (order == 0)
        order = (a['priority'] == 'high' ? 0 : 1).compareTo(
          b['priority'] == 'high' ? 0 : 1,
        );
      return order == 0
          ? (a['local_id'] as String).compareTo(b['local_id'] as String)
          : order;
    });
    final diary = result['diary'] as List;
    diary.sort(
      (a, b) => '${b['entry_date']}|${b['created_at']}|${b['local_id']}'
          .compareTo('${a['entry_date']}|${a['created_at']}|${a['local_id']}'),
    );
    final appointments = result['appointments'] as List;
    appointments.sort(
      (a, b) => '${a['start_at']}|${a['local_id']}'.compareTo(
        '${b['start_at']}|${b['local_id']}',
      ),
    );
    final now = clock().toUtc();
    final today = now.toIso8601String().substring(0, 10);
    final openTasks = tasks
        .where((task) => ['todo', 'in_progress'].contains(task['status']))
        .toList();
    final upcoming = appointments
        .where(
          (item) =>
              item['status'] == 'scheduled' &&
              !(DateTime.tryParse(item['end_at'] as String? ?? '')
                      ?.isBefore(now) ??
                  true),
        )
        .toList();
    result['counters'] = {
      ...Map<String, dynamic>.from(result['counters'] as Map? ?? {}),
      'tasks_open': openTasks.length,
      'tasks_overdue': openTasks
          .where(
            (task) =>
                task['due_date'] is String &&
                (task['due_date'] as String).compareTo(today) < 0,
          )
          .length,
      'appointments_upcoming': upcoming.length,
      'diary_entries': diary.length,
    };
    result['open_tasks'] = openTasks.take(20).toList();
    result['upcoming_appointments'] = upcoming.take(10).toList();
    result['latest_diary'] = diary.take(5).toList();
    result['active_links'] = (result['links'] as List)
        .where((item) => item['active'] == true)
        .toList();
    final pending = (_state?['workspace_outbox'] as List? ?? [])
        .where((operation) => operation['project_id'] == project)
        .length;
    result['has_pending_changes'] = pending > 0;
    result['workspace_sync_status'] =
        rows.any((record) => record['sync_status'] == 'Konflikt')
        ? 'Konflikt'
        : pending > 0
        ? 'Änderungen nur auf diesem Gerät'
        : 'Synchronisiert';
    return result;
  }

  Map<String, dynamic> _workspaceRemote(
    String project,
    String kind,
    dynamic value,
  ) {
    if (value is! Map ||
        value['project_id'] != project ||
        value['revision'] is! int ||
        value['revision'] < (kind == 'profile' ? 0 : 1) ||
        (kind != 'profile' &&
            (value['id'] is! String ||
                !RegExp(r'^[a-f0-9]{32}$').hasMatch(value['id']))) ||
        !_workspaceFields[kind]!.every(value.containsKey)) {
      throw const ApiException(0, 'Ungültiger Projektstand vom Server.');
    }
    return {
      for (final field in _workspaceFields[kind]!) field: value[field],
      'project_id': project,
      'revision': value['revision'],
      if (kind != 'profile') 'id': value['id'],
      for (final field in [
        'created_by',
        'created_at',
        'updated_by',
        'updated_at',
      ])
        if (value.containsKey(field)) field: value[field],
    };
  }

  void _mergeWorkspace(
    Map<String, dynamic> state,
    String project,
    String kind,
    Map<String, dynamic> remote,
  ) {
    final records = state['workspace_records'] ??= <String, dynamic>{};
    final id = kind == 'profile' ? project : remote['id'] as String;
    final matching = _workspaceFind(state, project, kind, id);
    final key = matching ?? _workspaceKey(project, kind, id);
    final previous = records[key];
    final queue = state['workspace_outbox'] as List? ?? [];
    final waiting = queue.any((operation) => operation['record_key'] == key);
    if (matching == null &&
        kind != 'profile' &&
        queue.any(
          (operation) =>
              operation['project_id'] == project &&
              operation['kind'] == kind &&
              records[operation['record_key']]?['server_id'] == null,
        )) {
      // Resolve accepted-but-unacknowledged creates by their stable retry first;
      // lists do not carry creation keys and must not create a second local row.
      return;
    }
    if (waiting) {
      previous['latest_server'] = remote;
      if (previous['sync_status'] == 'Konflikt') previous['remote'] = remote;
      return;
    }
    if (previous != null &&
        (previous['revision'] as int? ?? 0) > remote['revision'])
      return;
    records[key] = {
      ...remote,
      'kind': kind,
      'local_id': previous?['local_id'] ?? id,
      'server_id': id,
      'sync_status': 'Synchronisiert',
    };
  }

  Future<void> refreshWorkspace(String project) async {
    final epoch = _epoch;
    final token = transport.token;
    _workspaceAccess(epoch, project);
    if (token == null)
      throw const ApiException(
        0,
        'Keine Verbindung zur Projektmappe. Bereits geladene Einträge bleiben verfügbar.',
      );
    try {
      final responses = await Future.wait<dynamic>([
        transport.call('/api/projects/$project/workspace'),
        for (final kind in ['tasks', 'diary', 'appointments', 'links'])
          transport.call('/api/projects/$project/$kind'),
      ]);
      _workspaceAccess(epoch, project);
      if (transport.token != token)
        throw StateError('Offline-Anmeldung wurde geändert.');
      final dashboard = responses[0];
      if (dashboard is! Map ||
          dashboard['project'] is! Map ||
          dashboard['project']['id'] != project ||
          dashboard['profile'] is! Map ||
          dashboard['team'] is! List ||
          dashboard['counters'] is! Map) {
        throw const ApiException(0, 'Ungültige Projektübersicht vom Server.');
      }
      final profile = _workspaceRemote(
        project,
        'profile',
        dashboard['profile'],
      );
      final items = <String, List<Map<String, dynamic>>>{};
      for (var index = 0; index < 4; index++) {
        final kind = ['tasks', 'diary', 'appointments', 'links'][index];
        if (responses[index + 1] is! List)
          throw const ApiException(0, 'Ungültige Projektliste vom Server.');
        items[kind] = [
          for (final value in responses[index + 1])
            _workspaceRemote(project, kind, value),
        ];
      }
      await _change((state) {
        _workspaceAccess(epoch, project);
        (state['workspace_snapshots'] ??= {})[project] = {
          ...Map<String, dynamic>.from(dashboard),
          'cached_at': clock().toUtc().toIso8601String(),
        };
        _mergeWorkspace(state, project, 'profile', profile);
        for (final kind in items.keys) {
          for (final item in items[kind]!)
            _mergeWorkspace(state, project, kind, item);
        }
      });
    } on ApiException catch (error) {
      await _workspaceFailure(epoch, project, null, error, collection: true);
      rethrow;
    }
  }

  Future<Map<String, dynamic>> saveWorkspaceItem(
    String project,
    String kind,
    Map<String, dynamic> data, {
    String? id,
  }) {
    if (!['tasks', 'diary', 'appointments', 'links'].contains(kind)) {
      throw const ApiException(400, 'Unbekannter Bereich der Projektmappe.');
    }
    return _saveWorkspace(project, kind, data, id: id);
  }

  Future<Map<String, dynamic>> saveWorkspaceProfile(
    String project,
    Map<String, dynamic> data,
  ) => _saveWorkspace(project, 'profile', data, id: project);

  Future<Map<String, dynamic>> _saveWorkspace(
    String project,
    String kind,
    Map<String, dynamic> data, {
    String? id,
  }) async {
    final epoch = _epoch;
    _workspaceAccess(epoch, project, write: true, profile: kind == 'profile');
    final frozen = offlineCopy(data);
    final localId = id ?? offlineId();
    final result = await _change((state) {
      _workspaceAccess(epoch, project, write: true, profile: kind == 'profile');
      final snapshot = (state['workspace_snapshots'] as Map? ?? {})[project];
      if (snapshot == null)
        throw const ApiException(
          0,
          'Diese Projektmappe zuerst mit Verbindung vollständig laden.',
        );
      final found = id == null
          ? null
          : _workspaceFind(state, project, kind, id);
      if (id != null && found == null)
        throw const ApiException(
          404,
          'Gespeicherter Projekteintrag nicht verfügbar.',
        );
      final key = found ?? _workspaceKey(project, kind, localId);
      final records = state['workspace_records'] ??= <String, dynamic>{};
      final previous = records[key] as Map?;
      final expectedRevision = frozen['revision'];
      if (frozen.containsKey('revision') &&
          (expectedRevision is! int || expectedRevision < 0)) {
        throw const ApiException(400, 'Gültige Ausgangsversion erwartet.');
      }
      final staleEditor =
          previous != null &&
          expectedRevision != null &&
          previous['server_id'] != null &&
          expectedRevision != previous['revision'];
      final currentServer = staleEditor
          ? previous['remote'] as Map? ??
                previous['latest_server'] as Map? ??
                _workspaceRemote(project, kind, {
                  ...previous,
                  'id': previous['server_id'],
                })
          : null;
      final values = _workspaceValues(
        kind,
        frozen,
        previous,
        snapshot['team'] as List? ?? [],
      );
      final stamp = clock().toUtc().toIso8601String();
      final record = <String, dynamic>{
        ...?previous,
        ...values,
        'kind': kind,
        'local_id': previous?['local_id'] ?? localId,
        'project_id': project,
        'server_id': previous?['server_id'],
        'revision': staleEditor ? expectedRevision : previous?['revision'] ?? 0,
        'created_by': previous?['created_by'] ?? user['id'],
        'created_at': previous?['created_at'] ?? stamp,
        'updated_by': user['id'],
        'updated_at': stamp,
        'sync_status': staleEditor || previous?['sync_status'] == 'Konflikt'
            ? 'Konflikt'
            : 'Wartet auf Verbindung',
        if (currentServer != null) 'remote': currentServer,
        if (currentServer != null) 'latest_server': currentServer,
      };
      final outbox = state['workspace_outbox'] ??= <dynamic>[];
      if (previous?['sync_status'] == 'Eingabe prüfen')
        outbox.removeWhere((operation) => operation['record_key'] == key);
      final unsent = outbox.where(
        (operation) =>
            operation['record_key'] == key && operation['body'] == null,
      );
      if (unsent.isNotEmpty) {
        unsent.last['snapshot'] = values;
      } else {
        outbox.add({
          'record_key': key,
          'project_id': project,
          'kind': kind,
          'local_id': record['local_id'],
          'request_id': offlineId(),
          'snapshot': values,
          'body': null,
        });
      }
      records[key] = record;
      return _workspaceView(record);
    });
    unawaited(sync());
    return result;
  }

  Map<String, dynamic> _workspaceValues(
    String kind,
    Map<String, dynamic> data,
    Map? previous,
    List team,
  ) {
    final allowed = _workspaceFields[kind]!;
    const metadata = {
      'id',
      'local_id',
      'server_id',
      'project_id',
      'kind',
      'revision',
      'sync_status',
      'remote',
      'latest_server',
      'created_by',
      'created_at',
      'updated_by',
      'updated_at',
    };
    if (data.keys.any(
          (field) => !allowed.contains(field) && !metadata.contains(field),
        ) ||
        !data.keys.any(allowed.contains)) {
      throw const ApiException(
        400,
        'Gültige Felder der Projektmappe erwartet.',
      );
    }
    final defaults = <String, Map<String, dynamic>>{
      'profile': {
        'description': '',
        'site_address': '',
        'phase': 'planning',
        'deposit_status': 'not_recorded',
        'materials_status': 'not_recorded',
        'start_date': null,
        'end_date': null,
      },
      'tasks': {
        'title': '',
        'details': '',
        'status': 'todo',
        'priority': 'normal',
        'due_date': null,
        'assignee_id': null,
      },
      'diary': {
        'entry_date': clock().toUtc().toIso8601String().substring(0, 10),
        'work_performed': '',
        'issues': '',
        'next_steps': '',
        'weather': '',
        'crew_count': null,
      },
      'appointments': {
        'title': '',
        'details': '',
        'start_at': '',
        'end_at': '',
        'status': 'scheduled',
      },
      'links': {'title': '', 'category': 'document', 'url': '', 'active': true},
    };
    final values = <String, dynamic>{
      for (final field in allowed)
        field: data.containsKey(field)
            ? data[field]
            : previous?[field] ?? defaults[kind]![field],
    };
    String text(String field, int maximum, {bool required = false}) {
      final value = values[field];
      if (value is! String ||
          value.length > maximum ||
          (required && value.trim().isEmpty) ||
          value.contains(RegExp(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]'))) {
        throw ApiException(400, 'Ungültiges Textfeld: $field');
      }
      return value.trim();
    }

    void choice(String field, List<String> choices) {
      if (!choices.contains(values[field]))
        throw ApiException(400, 'Ungültige Auswahl: $field');
    }

    if (kind == 'profile') {
      values['description'] = text('description', 10000);
      values['site_address'] = text('site_address', 2000);
      choice('phase', [
        'planning',
        'scheduling',
        'awaiting_deposit',
        'procurement',
        'execution',
        'final_invoice',
        'completed',
        'on_hold',
      ]);
      choice('deposit_status', [
        'not_recorded',
        'not_required',
        'requested',
        'received',
      ]);
      choice('materials_status', [
        'not_recorded',
        'not_planned',
        'to_order',
        'ordered',
        'delivered',
      ]);
      for (final field in ['start_date', 'end_date'])
        values[field] = _workspaceDate(values[field]);
      if (values['start_date'] != null &&
          values['end_date'] != null &&
          (values['end_date'] as String).compareTo(values['start_date']) < 0)
        throw const ApiException(400, 'Projektende liegt vor dem Beginn.');
    } else if (kind == 'tasks') {
      values['title'] = text('title', 200, required: true);
      values['details'] = text('details', 10000);
      choice('status', ['todo', 'in_progress', 'done', 'cancelled']);
      choice('priority', ['normal', 'high']);
      values['due_date'] = _workspaceDate(values['due_date']);
      if (values['assignee_id'] == '') values['assignee_id'] = null;
      final target = values['assignee_id'];
      if (target != null &&
          (target is! String ||
              !RegExp(r'^[a-f0-9]{32}$').hasMatch(target) ||
              ((previous == null || previous['assignee_id'] != target) &&
                  !team.any((member) => member['id'] == target)))) {
        throw const ApiException(
          400,
          'Verantwortlicher muss Mitglied dieses Projekts sein.',
        );
      }
    } else if (kind == 'diary') {
      values['entry_date'] = _workspaceDate(
        values['entry_date'],
        required: true,
      );
      values['work_performed'] = text('work_performed', 10000, required: true);
      values['issues'] = text('issues', 10000);
      values['next_steps'] = text('next_steps', 5000);
      values['weather'] = text('weather', 200);
      final crew = values['crew_count'];
      if (crew != null && (crew is! int || crew < 0 || crew > 1000))
        throw const ApiException(
          400,
          'Personenanzahl zwischen 0 und 1000 erwartet.',
        );
    } else if (kind == 'appointments') {
      values['title'] = text('title', 200, required: true);
      values['details'] = text('details', 10000);
      choice('status', ['scheduled', 'cancelled']);
      values['start_at'] = _workspaceInstant(values['start_at']);
      values['end_at'] = _workspaceInstant(values['end_at']);
      if (!DateTime.parse(values['end_at'])
          .isAfter(DateTime.parse(values['start_at'])))
        throw const ApiException(
          400,
          'Terminende muss nach dem Beginn liegen.',
        );
    } else {
      values['title'] = text('title', 200, required: true);
      choice('category', [
        'dropbox',
        'offer',
        'invoice',
        'contract',
        'document',
        'other',
      ]);
      final url = values['url'];
      final uri = url is String ? Uri.tryParse(url) : null;
      if (url is! String ||
          url.length > 2048 ||
          url.contains(RegExp(r'[\s\x00-\x1f\x7f]')) ||
          uri == null ||
          uri.scheme != 'https' ||
          uri.host.isEmpty ||
          uri.userInfo.isNotEmpty ||
          (uri.hasPort && (uri.port < 1 || uri.port > 65535))) {
        throw const ApiException(
          400,
          'Gültiger HTTPS-Link ohne eingebettete Zugangsdaten erwartet.',
        );
      }
      if (values['active'] is! bool)
        throw const ApiException(400, 'Aktiv muss ein Wahrheitswert sein.');
    }
    if (utf8.encode(jsonEncode(values)).length > 65536)
      throw const ApiException(400, 'Projekteintrag ist zu groß.');
    return values;
  }

  String? _workspaceDate(dynamic value, {bool required = false}) {
    if ((value == null || value == '') && !required) return null;
    if (value is! String || !RegExp(r'^\d{4}-\d{2}-\d{2}$').hasMatch(value))
      throw const ApiException(400, 'Gültiges Datum erwartet.');
    final parsed = DateTime.tryParse(value);
    if (parsed == null ||
        parsed.year < 1900 ||
        parsed.year > 2200 ||
        parsed.toIso8601String().substring(0, 10) != value) {
      throw const ApiException(400, 'Gültiges Datum erwartet.');
    }
    return value;
  }

  String _workspaceInstant(dynamic value) {
    if (value is! String ||
        value.length > 40 ||
        !RegExp(r'(Z|[+-]\d{2}:\d{2})$').hasMatch(value)) {
      throw const ApiException(400, 'Zeitpunkt mit Zeitzone erwartet.');
    }
    final parsed = DateTime.tryParse(value);
    if (value.length < 16 || parsed == null)
      throw const ApiException(400, 'Gültiger Zeitpunkt erwartet.');
    _workspaceDate(value.substring(0, 10), required: true);
    final time = RegExp(r'^[T ](\d{2}):(\d{2})(?::(\d{2}))?')
        .firstMatch(value.substring(10));
    if (time == null ||
        int.parse(time[1]!) > 23 ||
        int.parse(time[2]!) > 59 ||
        (time[3] != null && int.parse(time[3]!) > 59)) {
      throw const ApiException(400, 'Gültiger Zeitpunkt erwartet.');
    }
    return parsed.toUtc().toIso8601String();
  }

  Future<void> _workspaceFailure(
    int epoch,
    String project,
    String? key,
    ApiException error, {
    bool collection = false,
  }) async {
    if (epoch != _epoch || !active) return;
    notice = error.status == 0 || error.status >= 500
        ? 'Keine Verbindung. Änderungen der Projektmappe bleiben auf diesem Gerät.'
        : error.message;
    if (error.status == 401) {
      await lock();
      return;
    }
    var revoke = collection && [403, 404].contains(error.status);
    if (!collection && [403, 404].contains(error.status)) {
      try {
        await transport.call('/api/projects/$project/workspace');
        _workspaceAccess(epoch, project);
      } on ApiException catch (probe) {
        if (epoch != _epoch) return;
        if (probe.status == 401) {
          await lock();
          return;
        }
        revoke = [403, 404].contains(probe.status);
      }
    }
    if (epoch != _epoch) return;
    await _change((state) {
      if (key != null && state['workspace_records']?[key] != null) {
        state['workspace_records'][key]['sync_status'] = error.status == 409
            ? 'Konflikt'
            : error.status == 403
            ? 'Zugriff gesperrt'
            : [400, 404, 413, 415].contains(error.status)
            ? 'Eingabe prüfen'
            : 'Wartet auf Verbindung';
      }
      if (revoke)
        (state['projects'] as List).removeWhere(
          (item) => item['id'] == project,
        );
    });
  }

  Future<void> _syncWorkspace(int epoch, String? token) async {
    if (!workspaceSupported) return;
    final attempted = <String>{};
    final updatedProjects = <String>{};
    while (epoch == _epoch && workspaceSupported && transport.token == token) {
      final records = _state!['workspace_records'] as Map? ?? {};
      final eligible = (_state!['workspace_outbox'] as List? ?? []).where((
        operation,
      ) {
        final record = records[operation['record_key']];
        return record != null &&
            _allowed(operation['project_id']) &&
            !attempted.contains(operation['record_key']) &&
            ![
              'Konflikt',
              'Zugriff gesperrt',
              'Eingabe prüfen',
            ].contains(record['sync_status']) &&
            (operation['kind'] == 'profile'
                    ? ['owner', 'manager']
                    : ['owner', 'manager', 'technician'])
                .contains(user['role']);
      });
      if (eligible.isEmpty) break;
      final key = eligible.first['record_key'] as String;
      final operation = await _change((state) {
        final item = (state['workspace_outbox'] as List).firstWhere(
          (item) => item['record_key'] == key,
        );
        _workspaceAccess(
          epoch,
          item['project_id'],
          write: true,
          profile: item['kind'] == 'profile',
        );
        final record = state['workspace_records'][key];
        if (item['body'] == null) {
          final collection = item['kind'] == 'profile'
              ? 'workspace'
              : item['kind'];
          item['path'] =
              '/api/projects/${item['project_id']}/$collection${item['kind'] == 'profile' || record['server_id'] == null ? '' : '/${record['server_id']}'}';
          item['body'] = {
            ...Map<String, dynamic>.from(item['snapshot']),
            'request_id': item['request_id'],
            if (item['kind'] == 'profile' || record['server_id'] != null)
              'revision': record['revision'],
          };
        }
        return offlineCopy(Map<String, dynamic>.from(item));
      });
      if (epoch != _epoch || transport.token != token) return;
      final project = operation['project_id'] as String;
      final kind = operation['kind'] as String;
      try {
        final response = await transport.call(
          operation['path'],
          Map<String, dynamic>.from(operation['body']),
        );
        _workspaceAccess(epoch, project);
        final remote = _workspaceRemote(project, kind, response);
        await _change((state) {
          _workspaceAccess(epoch, project);
          final record = state['workspace_records'][key];
          if (record['server_id'] != null &&
              kind != 'profile' &&
              record['server_id'] != remote['id'])
            throw const ApiException(
              0,
              'Antwort gehört zu einem anderen Projekteintrag.',
            );
          final queue = state['workspace_outbox'] as List;
          queue.removeWhere(
            (item) => item['request_id'] == operation['request_id'],
          );
          record['server_id'] = kind == 'profile' ? project : remote['id'];
          record['revision'] = remote['revision'];
          final waiting = queue.any((item) => item['record_key'] == key);
          if (waiting) {
            record['sync_status'] = 'Wartet auf Verbindung';
            record['latest_server'] = remote;
          } else {
            final latest = record['latest_server'] as Map?;
            state['workspace_records'][key] = {
              ...(latest != null && latest['revision'] > remote['revision']
                  ? latest
                  : remote),
              'kind': kind,
              'local_id': record['local_id'],
              'server_id': record['server_id'],
              'sync_status': 'Synchronisiert',
            };
          }
        });
        updatedProjects.add(project);
      } on ApiException catch (error) {
        if (epoch != _epoch) return;
        if (error.status == 409) {
          attempted.add(key);
          Map<String, dynamic>? remote;
          if (operation['body']['revision'] != null) {
            try {
              final value = await transport.call(operation['path']);
              _workspaceAccess(epoch, project);
              remote = _workspaceRemote(
                project,
                kind,
                kind == 'profile' ? value['profile'] : value,
              );
            } on ApiException catch (probe) {
              await _workspaceFailure(epoch, project, key, probe);
            }
          }
          if (epoch != _epoch || !workspaceSupported || !_allowed(project))
            return;
          await _change((state) {
            _workspaceAccess(epoch, project);
            final record = state['workspace_records'][key];
            record['sync_status'] = 'Konflikt';
            if (remote != null) record['remote'] = remote;
          });
        } else {
          await _workspaceFailure(epoch, project, key, error);
          if (error.status == 0 || error.status == 401 || error.status >= 500)
            return;
          attempted.add(key);
        }
      }
    }
    for (final project in updatedProjects) {
      if (epoch != _epoch || !workspaceSupported || !_allowed(project)) return;
      try {
        await refreshWorkspace(project);
      } on ApiException {
        /* Keep the acknowledged local snapshot. */
      }
    }
  }

  Future<void> resolveWorkspaceConflict(
    String project,
    String kind,
    String id, {
    required bool keepLocal,
  }) async {
    final epoch = _epoch;
    if (!_workspaceFields.containsKey(kind))
      throw const ApiException(400, 'Unbekannter Projektbereich.');
    _workspaceAccess(epoch, project, write: true, profile: kind == 'profile');
    await _change((state) {
      _workspaceAccess(epoch, project, write: true, profile: kind == 'profile');
      final key = _workspaceFind(state, project, kind, id);
      if (key == null)
        throw const ApiException(404, 'Projekteintrag nicht verfügbar.');
      final record = state['workspace_records'][key];
      final remote = record['remote'] as Map?;
      if (record['sync_status'] != 'Konflikt' || remote == null)
        throw const ApiException(
          0,
          'Zuerst mit Verbindung den aktuellen Serverstand laden.',
        );
      final queue = state['workspace_outbox'] ??= <dynamic>[];
      queue.removeWhere((item) => item['record_key'] == key);
      if (keepLocal) {
        record['revision'] = remote['revision'];
        record['server_id'] = kind == 'profile' ? project : remote['id'];
        record['sync_status'] = 'Wartet auf Verbindung';
        record.remove('remote');
        record.remove('latest_server');
        queue.add({
          'record_key': key,
          'project_id': project,
          'kind': kind,
          'local_id': record['local_id'],
          'request_id': offlineId(),
          'snapshot': {
            for (final field in _workspaceFields[kind]!) field: record[field],
          },
          'body': null,
        });
      } else {
        state['workspace_records'][key] = {
          ...remote,
          'kind': kind,
          'local_id': record['local_id'],
          'server_id': kind == 'profile' ? project : remote['id'],
          'sync_status': 'Synchronisiert',
        };
      }
    });
    unawaited(sync());
  }
}

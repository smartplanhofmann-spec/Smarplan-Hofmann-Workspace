import 'dart:convert';

import 'package:cryptography/dart.dart';
import 'package:flutter/foundation.dart';

import 'api.dart';
import 'offline_binding.dart';
import 'offline_vault.dart';
import 'offline_time_recovery.dart';
import 'offline_report_recovery.dart';

enum LegacyPlanStatus {
  unchecked,
  unprepared,
  unsupported,
  confirmed,
  unresolved,
}

class LegacyPlanCheck {
  const LegacyPlanCheck(this.number, this.status, {this.serverTitle});
  final int number;
  final LegacyPlanStatus status;
  final String? serverTitle;
  bool get canCheck =>
      status == LegacyPlanStatus.unchecked ||
      status == LegacyPlanStatus.unresolved ||
      status == LegacyPlanStatus.confirmed;
  String get label => switch (status) {
    LegacyPlanStatus.unchecked => 'Originalannahme noch nicht geprüft',
    LegacyPlanStatus.unprepared =>
      'Kein vollständig vorbereiteter Originalauftrag',
    LegacyPlanStatus.unsupported =>
      'Dieser Originalauftrag benötigt einen gesonderten Abgleich',
    LegacyPlanStatus.confirmed => 'Ursprüngliche Annahme bestätigt',
    LegacyPlanStatus.unresolved => 'Annahme ungeklärt; Original erhalten',
  };
}

class _RetainedPlan {
  _RetainedPlan(
    this.status, {
    this.project,
    this.plan,
    this.hash,
    this.command,
  });
  LegacyPlanStatus status;
  String? serverTitle;
  final String? project, plan, hash;
  final Map<String, dynamic>? command;
}

class LegacyTimeCheck {
  const LegacyTimeCheck(this.number, this.status, this.confirmation);
  final int number;
  final LegacyPlanStatus status;
  final LegacyTimeConfirmation? confirmation;
  bool get canCheck => LegacyPlanCheck(number, status).canCheck;
  String get label => LegacyPlanCheck(number, status).label;
}

class _RetainedTime {
  _RetainedTime(this.original);
  final LegacyTimeOriginal original;
  LegacyPlanStatus status = LegacyPlanStatus.unchecked;
  LegacyTimeConfirmation? confirmation;
}

class LegacyReportCheck {
  const LegacyReportCheck(this.number, this.status, this.confirmation);
  final int number;
  final LegacyPlanStatus status;
  final LegacyReportConfirmation? confirmation;
  bool get canCheck => LegacyPlanCheck(number, status).canCheck;
  String get label => LegacyPlanCheck(number, status).label;
}

class _RetainedReport {
  _RetainedReport(this.original);
  final LegacyReportOriginal original;
  LegacyPlanStatus status = LegacyPlanStatus.unchecked;
  LegacyReportConfirmation? confirmation;
}

/// A read-only inspection, never a V1 cache migration or upload authority.
/// A title is exposed only from a freshly authorized, fully matched server
/// original. Unproven local geometry and project details never enter the view.
class LegacyOfflineRecovery extends ChangeNotifier {
  LegacyOfflineRecovery({
    required this.api,
    required this.device,
    bool Function()? allowed,
    Listenable? accessChanges,
  }) : allowed = allowed ?? (() => true),
       accessChanges = accessChanges ?? api,
       token = api.token {
    this.accessChanges.addListener(_accessChanged);
  }
  final OfficeApi api;
  final OfflineDevice device;
  final bool Function() allowed;
  final Listenable accessChanges;
  final String? token;
  OfflineVault? _vault;
  OfflineBinding? _binding;
  String? _snapshotHash;
  int? _generation;
  final _plans = <_RetainedPlan>[];
  final _times = <_RetainedTime>[];
  final _reports = <_RetainedReport>[];
  int _epoch = 0;
  bool _disposed = false;
  bool busy = false, unlocking = false, inspected = false, found = false;
  int otherPending = 0;
  List<LegacyPlanCheck> get plans => List.unmodifiable([
    for (var i = 0; i < _plans.length; i++)
      LegacyPlanCheck(
        i + 1,
        _plans[i].status,
        serverTitle: _plans[i].serverTitle,
      ),
  ]);
  List<LegacyTimeCheck> get times => List.unmodifiable([
    for (var i = 0; i < _times.length; i++)
      LegacyTimeCheck(i + 1, _times[i].status, _times[i].confirmation),
  ]);
  List<LegacyReportCheck> get reports => List.unmodifiable([
    for (var i = 0; i < _reports.length; i++)
      LegacyReportCheck(i + 1, _reports[i].status, _reports[i].confirmation),
  ]);
  String get _server => '${api.base}|${api.version}';
  void _accessChanged() {
    if (!_disposed && (!allowed() || api.token != token)) clear();
  }

  bool _id(dynamic value) =>
      value is String &&
      value.length == 32 &&
      RegExp(r'^[a-f0-9]{32}$').hasMatch(value);
  void _changed() {
    if (!_disposed) notifyListeners();
  }

  void _drop() {
    _epoch++;
    for (final entry in _plans) {
      entry.command?.clear();
    }
    for (final entry in _times) {
      entry.original.clear();
    }
    for (final entry in _reports) {
      entry.original.clear();
    }
    _reports.clear();
    _times.clear();
    _plans.clear();
    _vault = null;
    _binding = null;
    _snapshotHash = null;
    _generation = null;
    inspected = found = false;
    otherPending = 0;
  }

  void clear() {
    _drop();
    _changed();
  }

  void _current(int epoch) {
    if (_disposed ||
        epoch != _epoch ||
        !allowed() ||
        api.version != 'v1' ||
        token == null ||
        token!.isEmpty ||
        token!.startsWith('offline_') ||
        api.token != token) {
      if (!_disposed) clear();
      throw const ApiException(
        0,
        'Die Anmeldung wurde gewechselt. Der alte Gerätebestand bleibt erhalten.',
      );
    }
  }

  Future<OfflineBinding> _fresh(int epoch) async {
    _current(epoch);
    final actor = await api.call('/api/me');
    _current(epoch);
    if (actor is! Map || !_id(actor['id']))
      throw const ApiException(
        0,
        'Die aktuelle Anmeldung konnte nicht bestätigt werden.',
      );
    final discovery = OfflineDiscovery.parse(
      await api.call('/api/offline/context'),
      expectedAccountId: actor['id'],
    );
    _current(epoch);
    final binding = discovery.binding;
    if (binding == null ||
        !_id(actor['id']) ||
        binding.accountId != actor['id'])
      throw const ApiException(
        409,
        'Der Abgleich benötigt eine bestätigte Firmenanmeldung.',
      );
    return binding;
  }

  String _hash(Map<String, dynamic> state) => const DartSha256()
      .hashSync(utf8.encode(jsonEncode(state)))
      .bytes
      .map((byte) => byte.toRadixString(16).padLeft(2, '0'))
      .join();
  Future<Map<String, dynamic>?> _read(OfflineVault vault, int epoch) async {
    await for (final file in vault.directory.list(followLinks: false)) {
      _current(epoch);
      final name = file.uri.pathSegments.last;
      if (name.startsWith('state-') &&
          !RegExp(r'^state-\d{16}\.enc$').hasMatch(name))
        throw const FormatException(
          'Ein alter Speicherstand benötigt eine gesonderte Prüfung.',
        );
    }
    final value = await vault.read();
    _current(epoch);
    return value;
  }

  Future<bool> _supportsTime(int epoch) async {
    _current(epoch);
    try {
      final caps = await api.call('/api/business/capabilities');
      _current(epoch);
      return caps is Map &&
          caps['features'] is List &&
          caps['features'].contains('offline_time_event_recovery') &&
          caps['capabilities'] is List &&
          caps['capabilities'].contains('business_time') &&
          caps['permissions'] is List &&
          caps['permissions'].contains('time.own');
    } on ApiException catch (error) {
      _current(epoch);
      if (error.status == 401) rethrow;
      // Missing/failed capability proof never permits a time lookup or upload.
      return false;
    }
  }

  List<_RetainedTime> _timeCandidates(
    Map<String, dynamic> state,
    String account,
  ) {
    final queue = state['business_time_outbox'] as List? ?? const [],
        records = state['business_time_records'];
    if (records is! Map) return [];
    final result = <_RetainedTime>[];
    for (final op in queue) {
      try {
        final original = LegacyTimeOriginal.fromCache(
          op,
          op is Map ? records[op['entry_id']] : null,
          accountId: account,
        );
        result.add(_RetainedTime(original));
      } on ApiException {
        /* No old basis: no inferred employee or probe. */
      } on FormatException {
        /* Keep unproved input in the other retained count. */
      }
    }
    return result;
  }

  Future<bool> _supportsReports(int epoch) async {
    _current(epoch);
    try {
      final caps = await api.call('/api/business/capabilities');
      _current(epoch);
      return caps is Map &&
          caps['features'] is List &&
          caps['features'].contains(legacyReportRecoveryFeature) &&
          caps['capabilities'] is List &&
          caps['capabilities'].contains('business_operations');
    } on ApiException catch (error) {
      _current(epoch);
      if (error.status == 401) rethrow;
      return false;
    }
  }

  List<_RetainedReport> _reportCandidates(
    Map<String, dynamic> state,
    String account,
  ) {
    final queue = state['service_report_outbox'] as List? ?? const [],
        records = state['service_report_records'];
    if (records is! Map) return [];
    final counts = <String, int>{};
    for (final value in queue) {
      if (value is String) counts[value] = (counts[value] ?? 0) + 1;
    }
    final result = <_RetainedReport>[];
    for (final id in queue) {
      if (id is! String ||
          counts[id] != 1 ||
          records[id] is! Map ||
          records[id]['id'] != id)
        continue;
      try {
        result.add(
          _RetainedReport(
            LegacyReportOriginal.fromCache(records[id], accountId: account),
          ),
        );
      } on ApiException {
        /* Unsupported originals stay in the retained other count. */
      } on FormatException {
        /* No reconstruction or upload authority. */
      }
    }
    return result;
  }

  Future<void> _unchangedSnapshot(int epoch) async {
    _current(epoch);
    final state = await _read(_vault!, epoch);
    if (state == null ||
        _vault!.generation != _generation ||
        _hash(state) != _snapshotHash)
      throw const ApiException(
        409,
        'Der Gerätebestand wurde geändert. Erneut prüfen.',
      );
  }

  _RetainedPlan _plan(dynamic value) {
    if (value is! Map ||
        !_id(value['local_id']) ||
        !_id(value['project_id']) ||
        !_id(value['request_id']))
      return _RetainedPlan(LegacyPlanStatus.unsupported);
    if (value['body'] == null)
      return _RetainedPlan(LegacyPlanStatus.unprepared);
    final path = value['path'], body = value['body'];
    final match = path is String
        ? RegExp(r'^/api/projects/([a-f0-9]{32})/plans(?:/([a-f0-9]{32}))?$')
              .firstMatch(path)
        : null;
    if (match == null ||
        match.group(0) != path ||
        match.group(1) != value['project_id'] ||
        body is! Map ||
        body['request_id'] != value['request_id'])
      return _RetainedPlan(LegacyPlanStatus.unsupported);
    try {
      final command = offlineCopy(Map<String, dynamic>.from(body));
      final hash = offlinePlanRequestHash(
        projectId: value['project_id'],
        planId: match.group(2),
        command: command,
      );
      return _RetainedPlan(
        LegacyPlanStatus.unchecked,
        project: value['project_id'],
        plan: match.group(2),
        hash: hash,
        command: command,
      );
    } on ApiException {
      return _RetainedPlan(LegacyPlanStatus.unsupported);
    } on FormatException {
      return _RetainedPlan(LegacyPlanStatus.unsupported);
    }
  }

  Future<void> inspect() async {
    if (busy) throw const ApiException(0, 'Der Geräteabgleich läuft bereits.');
    _drop();
    final epoch = _epoch;
    busy = true;
    _changed();
    try {
      final binding = await _fresh(epoch);
      bool unlocked;
      unlocking = true;
      try {
        unlocked = await device.unlock();
      } finally {
        unlocking = false;
      }
      if (!unlocked)
        throw const ApiException(403, 'Gerätebestand nicht entsperrt.');
      _current(epoch);
      final vault = await device.openExisting(_server, binding.accountId);
      _current(epoch);
      if (vault == null) {
        inspected = true;
        _changed();
        return;
      }
      final state = await _read(vault, epoch);
      // Historical V1 snapshots kept the host/API scope in the directory;
      // they have no server field. That scope never proves a company.
      if (state == null ||
          (state['server'] != null && state['server'] != _server) ||
          state['user'] is! Map ||
          state['user']['id'] != binding.accountId ||
          state['cache_schema'] != 1 ||
          state['binding'] != null ||
          state['queue_bindings'] != null)
        throw const FormatException(
          'Der alte Gerätebestand ist nicht eindeutig lesbar.',
        );
      final pending = state['outbox'];
      if (pending is! List || pending.length > 10000)
        throw const FormatException(
          'Die ursprünglichen Planaufträge sind nicht eindeutig lesbar.',
        );
      var other = 0;
      for (final key in const [
        'import_outbox',
        'plan_delete_outbox',
        'import_delete_outbox',
        'workspace_outbox',
        'business_time_outbox',
        'business_media_outbox',
        'service_report_outbox',
      ]) {
        final queue = state[key] ?? const [];
        if (queue is! List || queue.length > 10000)
          throw const FormatException(
            'Eine alte Warteschlange ist nicht eindeutig lesbar.',
          );
        other += queue.length;
      }
      final parsed = pending.map(_plan).toList();
      final timeCandidates = _timeCandidates(state, binding.accountId);
      final timeSupported =
          timeCandidates.isNotEmpty && await _supportsTime(epoch);
      final reportCandidates = _reportCandidates(state, binding.accountId);
      final reportsSupported =
          reportCandidates.isNotEmpty && await _supportsReports(epoch);
      _current(epoch);
      _vault = vault;
      _binding = binding;
      _generation = vault.generation;
      _snapshotHash = _hash(state);
      _plans.addAll(parsed);
      if (timeSupported)
        _times.addAll(timeCandidates);
      else
        for (final candidate in timeCandidates) {
          candidate.original.clear();
        }
      if (reportsSupported) {
        _reports.addAll(reportCandidates);
      } else {
        for (final candidate in reportCandidates) {
          candidate.original.clear();
        }
      }
      otherPending = other - _times.length - _reports.length;
      found = inspected = true;
      _changed();
    } catch (_) {
      if (!_disposed && epoch == _epoch) _drop();
      rethrow;
    } finally {
      busy = false;
      _changed();
    }
  }

  Future<void> check(int index) async {
    if (busy || index < 0 || index >= _plans.length || !plans[index].canCheck)
      throw const ApiException(
        0,
        'Diesen Auftrag zuerst aus dem erhaltenen Bestand neu prüfen.',
      );
    final epoch = _epoch, candidate = _plans[index];
    candidate.serverTitle = null;
    candidate.status = LegacyPlanStatus.unchecked;
    busy = true;
    _changed();
    try {
      final binding = await _fresh(epoch);
      if (binding != _binding)
        throw const ApiException(409, 'Die Firma wurde gewechselt.');
      await _unchangedSnapshot(epoch);
      final request = offlineRecoveryRequest(
        nonce: offlineId(),
        projectId: candidate.project!,
        planId: candidate.plan,
        requestId: candidate.command!['request_id'],
        requestHash: candidate.hash!,
      );
      final response = await api.call(
        '/api/business/offline/recovery/lookup',
        request,
      );
      _current(epoch);
      final verified = offlineRecoveryMatch(
        response,
        request: request,
        expectedBinding: binding,
        originalCommand: candidate.command!,
      );
      _current(epoch);
      candidate.serverTitle = verified['original']['title'] as String;
      candidate.status = LegacyPlanStatus.confirmed;
    } catch (error) {
      if (!_disposed && epoch == _epoch) {
        if (error is ApiException && error.status == 401)
          _drop();
        else
          candidate.status = LegacyPlanStatus.unresolved;
      }
      rethrow;
    } finally {
      busy = false;
      _changed();
    }
  }

  Future<void> checkTime(int index) async {
    if (busy || index < 0 || index >= _times.length || !times[index].canCheck)
      throw const ApiException(
        0,
        'Diesen Zeitauftrag zuerst aus dem erhaltenen Bestand neu prüfen.',
      );
    final epoch = _epoch, candidate = _times[index];
    candidate.confirmation = null;
    candidate.status = LegacyPlanStatus.unchecked;
    busy = true;
    _changed();
    try {
      final binding = await _fresh(epoch);
      if (binding != _binding)
        throw const ApiException(409, 'Die Firma wurde gewechselt.');
      if (!await _supportsTime(epoch))
        throw const ApiException(
          409,
          'Die aktuelle Freigabe für den Zeitabgleich fehlt.',
        );
      await _unchangedSnapshot(epoch);
      _current(epoch);
      final request = candidate.original.query(nonce: offlineId());
      final reply = await api.call(
        '/api/business/offline/recovery/time-event',
        request,
      );
      _current(epoch);
      final confirmed = candidate.original.match(
        reply,
        request: request,
        binding: binding,
      );
      _current(epoch);
      candidate.confirmation = confirmed;
      candidate.status = LegacyPlanStatus.confirmed;
    } catch (error) {
      if (!_disposed && epoch == _epoch) {
        if (error is ApiException && error.status == 401)
          _drop();
        else
          candidate.status = LegacyPlanStatus.unresolved;
      }
      rethrow;
    } finally {
      busy = false;
      _changed();
    }
  }

  Future<void> checkReport(int index) async {
    if (busy ||
        index < 0 ||
        index >= _reports.length ||
        !reports[index].canCheck)
      throw const ApiException(
        0,
        'Diesen Protokollauftrag zuerst aus dem erhaltenen Bestand neu prüfen.',
      );
    final epoch = _epoch, candidate = _reports[index];
    candidate.confirmation = null;
    candidate.status = LegacyPlanStatus.unchecked;
    busy = true;
    _changed();
    try {
      final binding = await _fresh(epoch);
      if (binding != _binding)
        throw const ApiException(409, 'Die Firma wurde gewechselt.');
      if (!await _supportsReports(epoch))
        throw const ApiException(
          409,
          'Die aktuelle Freigabe für den Protokollabgleich fehlt.',
        );
      await _unchangedSnapshot(epoch);
      _current(epoch);
      final request = candidate.original.query(nonce: offlineId());
      final reply = await api.call(
        '/api/business/offline/recovery/service-report',
        request,
      );
      _current(epoch);
      final confirmed = candidate.original.match(
        reply,
        request: request,
        binding: binding,
      );
      await _unchangedSnapshot(epoch);
      _current(epoch);
      candidate.confirmation = confirmed;
      candidate.status = LegacyPlanStatus.confirmed;
    } catch (error) {
      if (!_disposed && epoch == _epoch) {
        if (error is ApiException && error.status == 401) {
          _drop();
        } else {
          candidate.status = LegacyPlanStatus.unresolved;
        }
      }
      rethrow;
    } finally {
      busy = false;
      _changed();
    }
  }

  @override
  void dispose() {
    accessChanges.removeListener(_accessChanged);
    _disposed = true;
    _drop();
    super.dispose();
  }
}

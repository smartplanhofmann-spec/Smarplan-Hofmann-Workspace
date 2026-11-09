import 'dart:convert';

import 'package:cryptography/dart.dart';
import 'package:flutter/foundation.dart';

import 'api.dart';
import 'offline_binding.dart';
import 'offline_vault.dart';

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
      _current(epoch);
      _vault = vault;
      _binding = binding;
      _generation = vault.generation;
      _snapshotHash = _hash(state);
      _plans.addAll(parsed);
      otherPending = other;
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
      final state = await _read(_vault!, epoch);
      if (state == null ||
          _vault!.generation != _generation ||
          _hash(state) != _snapshotHash)
        throw const ApiException(
          409,
          'Der Gerätebestand wurde geändert. Erneut prüfen.',
        );
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

  @override
  void dispose() {
    accessChanges.removeListener(_accessChanged);
    _disposed = true;
    _drop();
    super.dispose();
  }
}

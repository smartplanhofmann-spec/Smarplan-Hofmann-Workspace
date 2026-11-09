import 'dart:convert';

import 'api.dart';
import 'offline_binding.dart';

Never _invalidTime() => throw const ApiException(
  0,
  'Der damalige Zeitbezug ist nicht vollständig belegt. Der alte Auftrag bleibt ungeklärt erhalten.',
);
void _requireTime(bool value) {
  if (!value) _invalidTime();
}

bool _id(dynamic value) =>
    value is String &&
    value.length == 32 &&
    RegExp(r'^[a-f0-9]{32}$').hasMatch(value);
Map<String, dynamic> _map(dynamic value) {
  _requireTime(value is Map && value.keys.every((key) => key is String));
  return Map<String, dynamic>.from(value as Map);
}

Map<String, dynamic> _exact(dynamic value, Set<String> keys) {
  final map = _map(value);
  _requireTime(map.length == keys.length && keys.every(map.containsKey));
  return map;
}

Map<String, dynamic> _copy(Map<String, dynamic> value) =>
    Map<String, dynamic>.from(jsonDecode(jsonEncode(value)));
String _pythonInstant(DateTime value) {
  final utc = value.toUtc(),
      micros = value.millisecond * 1000 + value.microsecond;
  return '${utc.toIso8601String().substring(0, 19)}${micros == 0 ? '' : '.${micros.toString().padLeft(6, '0')}'}+00:00';
}

DateTime _nativeInstant(dynamic value) {
  _requireTime(
    value is String &&
        RegExp(r'^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d\.\d{3}(?:\d{3})?Z$')
            .hasMatch(value),
  );
  final parsed = DateTime.tryParse(value as String);
  _requireTime(
    parsed != null &&
        parsed.isUtc &&
        parsed.year >= 1 &&
        parsed.year <= 9999 &&
        parsed.toIso8601String() == value,
  );
  return parsed!;
}

class LegacyTimeConfirmation {
  const LegacyTimeConfirmation({
    required this.action,
    required this.occurredAt,
  });
  final String action;
  final DateTime occurredAt;
}

/// This hashes the historical time CORE, never a reconstructed wire command.
/// Employee/category IDs must come from the separately retained old cache.
class LegacyTimeOriginal {
  LegacyTimeOriginal._(this.accountId, this.requestId, this._core);
  final String accountId, requestId;
  final Map<String, dynamic> _core;
  String get entryId => _core['entry_id'];
  String get projectId => _core['project_id'];
  String get requestHash => offlineBindingHash(_core);
  factory LegacyTimeOriginal.fromCache(
    dynamic operation,
    dynamic record, {
    required String accountId,
  }) {
    _requireTime(_id(accountId));
    final op = _exact(operation, {'entry_id', 'project_id', 'body'}),
        old = _map(record),
        body = _map(op['body']);
    final action = body['action'];
    _exact(body, {
      'request_id',
      'event_id',
      'entry_id',
      'device_id',
      'sequence',
      'revision',
      'action',
      'occurred_at',
      'project_id',
      if (action == 'start' && body.containsKey('category_id')) 'category_id',
    });
    _requireTime(
      [
            op['entry_id'],
            op['project_id'],
            body['request_id'],
            body['device_id'],
            old['employee_id'],
          ].every(_id) &&
          body['event_id'] == body['request_id'] &&
          body['entry_id'] == op['entry_id'] &&
          body['project_id'] == op['project_id'] &&
          old['id'] == op['entry_id'] &&
          old['project_id'] == op['project_id'] &&
          old['user_id'] == accountId &&
          ['start', 'pause', 'resume', 'stop'].contains(action) &&
          body['sequence'] is int &&
          body['revision'] is int &&
          body['sequence'] >= 1 &&
          body['sequence'] <= 1000000000 &&
          body['revision'] >= 0 &&
          body['sequence'] == body['revision'] + 1 &&
          (action == 'start') == (body['sequence'] == 1) &&
          old['revision'] is int &&
          old['revision'] >= body['revision'] + 1,
    );
    if (action != 'start') _requireTime(old.containsKey('category_id'));
    final category = action == 'start'
        ? body['category_id']
        : old['category_id'];
    _requireTime(category == null || _id(category));
    if (body.containsKey('category_id')) _requireTime(_id(category));
    final at = _nativeInstant(body['occurred_at']);
    final core = <String, dynamic>{
      'entry_id': op['entry_id'],
      'employee_id': old['employee_id'],
      'project_id': op['project_id'],
      'category_id': category,
      'action': action,
      'occurred_at': _pythonInstant(at),
      'device_id': body['device_id'],
      'sequence': body['sequence'],
      'revision': body['revision'],
    };
    return LegacyTimeOriginal._(accountId, body['request_id'], core);
  }
  Map<String, dynamic> query({required String nonce}) {
    _requireTime(_id(nonce));
    return {
      'schema_version': 3,
      'nonce': nonce,
      'kind': 'time_event_core',
      'project_id': projectId,
      'entry_id': entryId,
      'request_id': requestId,
      'request_hash': requestHash,
    };
  }

  LegacyTimeConfirmation match(
    dynamic response, {
    required Map<String, dynamic> request,
    required OfflineBinding binding,
  }) {
    _requireTime(_id(request['nonce']));
    final expected = query(nonce: request['nonce']);
    _requireTime(
      offlineBindingCanonical(expected) == offlineBindingCanonical(request) &&
          binding.accountId == accountId,
    );
    final reply = _exact(response, {
      'schema_version',
      'nonce',
      'lookup_hash',
      'binding',
      'kind',
      'project_id',
      'entry_id',
      'request_id',
      'request_hash',
      'original',
    });
    _requireTime(
      reply['schema_version'] is int &&
          reply['schema_version'] == 3 &&
          reply['kind'] == 'time_event_core' &&
          reply['nonce'] == expected['nonce'] &&
          reply['lookup_hash'] == offlineBindingHash(expected) &&
          reply['project_id'] == projectId &&
          reply['entry_id'] == entryId &&
          reply['request_id'] == requestId &&
          reply['request_hash'] == requestHash &&
          OfflineBinding.fromJson(
                reply['binding'],
                expectedAccountId: accountId,
              ) ==
              binding,
    );
    final original = _exact(reply['original'], {
      'schema_version',
      'event_id',
      'request_id',
      'actor_id',
      'request_hash',
      'received_at',
      'core',
    });
    final core = _exact(original['core'], {
      'entry_id',
      'employee_id',
      'project_id',
      'category_id',
      'action',
      'occurred_at',
      'device_id',
      'sequence',
      'revision',
    });
    _requireTime(
      _core.entries.every(
        (e) =>
            core[e.key] == e.value && (e.value is! int || core[e.key] is int),
      ),
    );
    _requireTime(
      original['schema_version'] is int &&
          original['schema_version'] == 1 &&
          original['event_id'] == requestId &&
          original['request_id'] == requestId &&
          original['actor_id'] == accountId &&
          original['request_hash'] == requestHash &&
          offlineBindingHash(core) == requestHash,
    );
    final received = original['received_at'],
        parsed = received is String && received.length <= 40
            ? DateTime.tryParse(received)
            : null;
    _requireTime(
      parsed != null &&
          parsed.isUtc &&
          parsed.year >= 1 &&
          parsed.year <= 9999 &&
          _pythonInstant(parsed) == received,
    );
    return LegacyTimeConfirmation(
      action: _core['action'],
      occurredAt: DateTime.parse(_core['occurred_at']),
    );
  }

  Map<String, dynamic> get preservedCore => _copy(_core);
  void clear() => _core.clear();
}

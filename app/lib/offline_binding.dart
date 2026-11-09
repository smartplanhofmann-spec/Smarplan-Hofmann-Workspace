import 'dart:convert';

import 'package:cryptography/dart.dart';

import 'api.dart';

const offlineBindingHeader = 'X-Smartplan-Offline-Binding';
const _baseCapabilities = {
  'project_plans',
  'offline_plan_access',
  'plan_deletion',
  'project_workspace',
  'offline_workspace',
};
const _businessCapabilities = {'time_events', 'field_media', 'offline_reports'};
final _id = RegExp(r'^[a-f0-9]{32}$');

Never _invalid() => throw const ApiException(
  0,
  'Die Offline-Freigabe oder Firmenbindung konnte nicht eindeutig geprüft werden. Der gespeicherte Ursprung bleibt erhalten.',
);

void _require(bool condition) {
  if (!condition) _invalid();
}

Map<String, dynamic> _map(dynamic raw) {
  _require(raw is Map && raw.keys.every((key) => key is String));
  return Map<String, dynamic>.from(raw as Map);
}

Map<String, dynamic> _keys(dynamic raw, Set<String> fields) {
  final value = _map(raw);
  _require(value.length == fields.length && fields.every(value.containsKey));
  return value;
}

void _identifier(dynamic raw) => _require(raw is String && _id.hasMatch(raw));

bool _unicodeScalars(String value) {
  final units = value.codeUnits;
  for (var index = 0; index < units.length; index++) {
    final unit = units[index];
    if (unit >= 0xd800 && unit <= 0xdbff) {
      if (++index >= units.length ||
          units[index] < 0xdc00 ||
          units[index] > 0xdfff)
        return false;
    } else if (unit >= 0xdc00 && unit <= 0xdfff) {
      return false;
    }
  }
  return true;
}

/// Only closed string/integer DTOs use this canonical form. Historic plan
/// coordinate floats must never be silently reformatted by this helper.
String offlineBindingCanonical(dynamic value) {
  if (value is Map) {
    final map = _map(value), keys = map.keys.toList()..sort();
    _require(keys.every(_unicodeScalars));
    return '{${keys.map((key) => '${jsonEncode(key)}:${offlineBindingCanonical(map[key])}').join(',')}}';
  }
  if (value is List) return '[${value.map(offlineBindingCanonical).join(',')}]';
  if (value is String) _require(_unicodeScalars(value));
  _require(value == null || value is String || value is bool || value is int);
  return jsonEncode(value);
}

String offlineBindingHash(dynamic value) => const DartSha256()
    .hashSync(utf8.encode(offlineBindingCanonical(value)))
    .bytes
    .map((byte) => byte.toRadixString(16).padLeft(2, '0'))
    .join();

DateTime _instant(dynamic raw) {
  _require(raw is String);
  final match = RegExp(
    r'^(\d{4}-\d{2}-\d{2})T(\d{2}):(\d{2}):(\d{2})(?:\.\d{1,9})?(Z|[+-](\d{2}):(\d{2}))$',
  ).firstMatch(raw as String);
  _require(match != null);
  final day = DateTime.tryParse('${match![1]}T00:00:00Z');
  final parsed = DateTime.tryParse(raw);
  _require(
    day != null &&
        day.year >= 1 &&
        day.toIso8601String().substring(0, 10) == match[1] &&
        int.parse(match[2]!) <= 23 &&
        int.parse(match[3]!) <= 59 &&
        int.parse(match[4]!) <= 59 &&
        (match[6] == null || int.parse(match[6]!) <= 23) &&
        (match[7] == null || int.parse(match[7]!) <= 59) &&
        parsed != null,
  );
  return parsed!;
}

/// Immutable server-issued identity, independent of an expiring device token.
class OfflineBinding {
  const OfflineBinding._(this.instanceId, this.accountId);
  final String instanceId, accountId;

  factory OfflineBinding.fromJson(dynamic raw, {String? expectedAccountId}) {
    final value = _keys(raw, {'schema_version', 'instance_id', 'account_id'});
    _require(value['schema_version'] is int && value['schema_version'] == 1);
    _identifier(value['instance_id']);
    _identifier(value['account_id']);
    if (expectedAccountId != null) {
      _identifier(expectedAccountId);
      _require(value['account_id'] == expectedAccountId);
    }
    return OfflineBinding._(value['instance_id'], value['account_id']);
  }

  Map<String, dynamic> toJson() => {
    'schema_version': 1,
    'instance_id': instanceId,
    'account_id': accountId,
  };

  String get headerValue => '$instanceId:$accountId';
  bool matches(OfflineBinding other) => this == other;

  @override
  bool operator ==(Object other) =>
      other is OfflineBinding &&
      other.instanceId == instanceId &&
      other.accountId == accountId;

  @override
  int get hashCode => Object.hash(instanceId, accountId);
}

/// Only an explicit unbound_legacy response denotes an unbound server.
class OfflineDiscovery {
  const OfflineDiscovery._(this.mode, this.binding);
  final String mode;
  final OfflineBinding? binding;
  bool get isBound => binding != null;

  factory OfflineDiscovery.parse(
    dynamic raw, {
    required String expectedAccountId,
  }) => OfflineDiscovery.fromServer(raw, expectedAccountId: expectedAccountId);

  factory OfflineDiscovery.fromServer(
    dynamic raw, {
    String? expectedAccountId,
  }) {
    if (expectedAccountId != null) _identifier(expectedAccountId);
    final value = _keys(raw, {'schema_version', 'mode', 'binding'});
    _require(value['schema_version'] is int && value['schema_version'] == 2);
    if (value['mode'] == 'unbound_legacy') {
      _require(value['binding'] == null);
      return const OfflineDiscovery._('unbound_legacy', null);
    }
    _require(value['mode'] == 'bound_v2');
    return OfflineDiscovery._(
      'bound_v2',
      OfflineBinding.fromJson(
        value['binding'],
        expectedAccountId: expectedAccountId,
      ),
    );
  }

  Map<String, dynamic> toJson() => {
    'schema_version': 2,
    'mode': mode,
    'binding': binding?.toJson(),
  };
}

/// Validated V2 grant. Token, fields and capabilities retain their exact values.
class OfflineGrant {
  OfflineGrant._({
    required this.kind,
    required this.token,
    required this.binding,
    required this.issuedAt,
    required this.expiresAt,
    required List<String> capabilities,
    required List<String>? reportProjectIds,
    required this.reportWritesEnabled,
    required Map<String, dynamic> raw,
  }) : capabilities = List.unmodifiable(capabilities),
       reportProjectIds = reportProjectIds == null
           ? null
           : List.unmodifiable(reportProjectIds),
       _encoded = jsonEncode(raw);

  final String kind, token;
  final OfflineBinding binding;
  final DateTime issuedAt, expiresAt;
  final List<String> capabilities;
  final List<String>? reportProjectIds;
  final bool? reportWritesEnabled;
  final String _encoded;

  Map<String, dynamic> get raw =>
      Map<String, dynamic>.from(jsonDecode(_encoded));
  Map<String, dynamic> toJson() => raw;

  factory OfflineGrant.parse(
    dynamic raw, {
    required OfflineBinding expectedBinding,
    required String kind,
  }) {
    _require(kind == 'workspace' || kind == 'business');
    final value = _keys(raw, {
      'schema_version',
      'token',
      'issued_at',
      'expires_at',
      'capabilities',
      'binding',
      if (kind == 'business') ...{
        'report_project_ids',
        'report_writes_enabled',
      },
    });
    _require(value['schema_version'] is int && value['schema_version'] == 2);
    final binding = OfflineBinding.fromJson(value['binding']);
    _require(binding == expectedBinding);
    final token = value['token'];
    _require(
      token is String &&
          token.length <= 193 &&
          RegExp('^offline_${kind}_v2_[A-Za-z0-9_-]+\$').hasMatch(token),
    );
    final issuedAt = _instant(value['issued_at']);
    final expiresAt = _instant(value['expires_at']);
    _require(
      expiresAt.isAfter(issuedAt) &&
          expiresAt.difference(issuedAt) <= const Duration(days: 7),
    );
    final caps = value['capabilities'];
    _require(caps is List && caps.every((cap) => cap is String));
    final capabilities = List<String>.from(caps);
    final supported = {
      ..._baseCapabilities,
      'plan_imports',
      if (kind == 'business') ..._businessCapabilities,
    };
    _require(
      capabilities.toSet().length == capabilities.length &&
          _baseCapabilities.every(capabilities.contains) &&
          capabilities.every(supported.contains) &&
          (kind != 'business' ||
              capabilities.any(_businessCapabilities.contains)),
    );
    List<String>? reportProjectIds;
    bool? reportWritesEnabled;
    if (kind == 'business') {
      final projects = value['report_project_ids'];
      _require(projects is List && value['report_writes_enabled'] is bool);
      reportProjectIds = [];
      for (final id in projects) {
        _identifier(id);
        _require(!reportProjectIds.contains(id));
        reportProjectIds.add(id);
      }
      reportWritesEnabled = value['report_writes_enabled'];
    }
    return OfflineGrant._(
      kind: kind,
      token: token,
      binding: binding,
      issuedAt: issuedAt,
      expiresAt: expiresAt,
      capabilities: capabilities,
      reportProjectIds: reportProjectIds,
      reportWritesEnabled: reportWritesEnabled,
      raw: value,
    );
  }
}

String _legacyTitle(String value) {
  bool whitespace(int unit) =>
      (unit >= 9 && unit <= 13) ||
      (unit >= 28 && unit <= 32) ||
      const [
        0x85,
        0xa0,
        0x1680,
        0x2028,
        0x2029,
        0x202f,
        0x205f,
        0x3000,
      ].contains(unit) ||
      (unit >= 0x2000 && unit <= 0x200a);
  var first = 0, last = value.length;
  while (first < last && whitespace(value.codeUnitAt(first))) first++;
  while (last > first && whitespace(value.codeUnitAt(last - 1))) last--;
  return value.substring(first, last);
}

void _drawing(dynamic raw) {
  _require(raw is List && raw.length <= 2000);
  final ids = <String>{};
  for (final item in raw as List) {
    final wall = _keys(item, {'id', 'points'}), identifier = wall['id'];
    _require(
      identifier is String &&
          RegExp(r'^[A-Za-z0-9_-]{1,100}$').hasMatch(identifier) &&
          ids.add(identifier),
    );
    final points = wall['points'];
    _require(points is List && points.length == 2);
    for (final point in points) {
      _require(point is List && point.length == 2);
      for (final number in point) {
        _require(number is num && number.isFinite && number.abs() <= 10000);
      }
    }
    _require(points[0][0] != points[1][0] || points[0][1] != points[1][1]);
  }
}

Map<String, dynamic> _planCommand(dynamic raw, String? planId) {
  final command = _keys(raw, {
    'request_id',
    'title',
    'walls',
    if (planId != null) 'revision',
  });
  _identifier(command['request_id']);
  final title = command['title'];
  _require(
    title is String &&
        _unicodeScalars(title) &&
        title.runes.length <= 200 &&
        _legacyTitle(title).isNotEmpty,
  );
  _drawing(command['walls']);
  if (planId != null) {
    _require(command['revision'] is int && command['revision'] >= 1);
  }
  return command;
}

String _planHashCanonical(dynamic value) {
  if (value is Map) {
    final map = _map(value), keys = map.keys.toList()..sort();
    _require(keys.every(_unicodeScalars));
    return '{${keys.map((key) => '${jsonEncode(key)}:${_planHashCanonical(map[key])}').join(',')}}';
  }
  if (value is List) return '[${value.map(_planHashCanonical).join(',')}]';
  if (value is double) {
    _require(
      value.isFinite &&
          value.abs() <= 10000 &&
          value == value.truncateToDouble(),
    );
    if (value == 0 && value.isNegative) return '-0.0';
    return '${value.toInt()}.0';
  }
  return offlineBindingCanonical(value);
}

/// A local proof only for the demonstrated Python/Dart JSON subset. All other
/// floating-point values stay quarantined; this never serializes an upload.
String offlinePlanRequestHash({
  required String projectId,
  String? planId,
  required Map<String, dynamic> command,
}) {
  _identifier(projectId);
  if (planId != null) _identifier(planId);
  final original = _planCommand(command, planId);
  final encoded = _planHashCanonical({
    'project_id': projectId,
    'plan_id': planId,
    'data': original,
  });
  return const DartSha256()
      .hashSync(utf8.encode(encoded))
      .bytes
      .map((byte) => byte.toRadixString(16).padLeft(2, '0'))
      .join();
}

/// The network envelope carries identifiers and a proved hash only. It contains
/// no title, geometry, command JSON or other data from an unbound old cache.
Map<String, dynamic> offlineRecoveryRequest({
  required String nonce,
  required String projectId,
  String? planId,
  required String requestId,
  required String requestHash,
}) {
  _identifier(nonce);
  _identifier(projectId);
  if (planId != null) _identifier(planId);
  _identifier(requestId);
  _require(RegExp(r'^[a-f0-9]{64}$').hasMatch(requestHash));
  final request = <String, dynamic>{
    'schema_version': 2,
    'nonce': nonce,
    'kind': 'plan_write',
    'project_id': projectId,
    'plan_id': planId,
    'request_id': requestId,
    'request_hash': requestHash,
  };
  _require(utf8.encode(offlineBindingCanonical(request)).length <= 4096);
  return Map.unmodifiable(request);
}

bool _sameJson(dynamic a, dynamic b) {
  if (a is num || b is num) {
    if (a is! num || b is! num || (a is int) != (b is int) || a != b)
      return false;
    return a != 0 || a is int || a.isNegative == b.isNegative;
  }
  if (a is List || b is List) {
    return a is List &&
        b is List &&
        a.length == b.length &&
        List.generate(a.length, (i) => i).every((i) => _sameJson(a[i], b[i]));
  }
  if (a is Map || b is Map) {
    return a is Map &&
        b is Map &&
        a.length == b.length &&
        a.keys.every((key) => b.containsKey(key) && _sameJson(a[key], b[key]));
  }
  return a == b;
}

/// Validate a positive lookup against a separately retained local command.
/// This returns evidence for one receipt, never authority for an old cache.
Map<String, dynamic> offlineRecoveryMatch(
  dynamic raw, {
  required Map<String, dynamic> request,
  required OfflineBinding expectedBinding,
  required Map<String, dynamic> originalCommand,
}) {
  final expected = _keys(request, {
    'schema_version',
    'nonce',
    'kind',
    'project_id',
    'plan_id',
    'request_id',
    'request_hash',
  });
  _require(
    expected['schema_version'] is int &&
        expected['schema_version'] == 2 &&
        expected['kind'] == 'plan_write',
  );
  _identifier(expected['nonce']);
  _identifier(expected['project_id']);
  _identifier(expected['request_id']);
  _require(expected['request_hash'] is String);
  if (expected['plan_id'] != null) _identifier(expected['plan_id']);
  final validated = offlineRecoveryRequest(
    nonce: expected['nonce'],
    projectId: expected['project_id'],
    planId: expected['plan_id'],
    requestId: expected['request_id'],
    requestHash: expected['request_hash'],
  );
  final command = _planCommand(originalCommand, validated['plan_id']);
  _require(
    command['request_id'] == validated['request_id'] &&
        offlinePlanRequestHash(
              projectId: validated['project_id'],
              planId: validated['plan_id'],
              command: command,
            ) ==
            validated['request_hash'],
  );
  final result = _keys(raw, {
    'schema_version',
    'nonce',
    'lookup_hash',
    'binding',
    'kind',
    'project_id',
    'plan_id',
    'request_id',
    'request_hash',
    'original',
  });
  _require(
    result['schema_version'] is int &&
        result['schema_version'] == 2 &&
        result['nonce'] == validated['nonce'] &&
        result['kind'] == 'plan_write' &&
        result['project_id'] == validated['project_id'] &&
        result['plan_id'] == validated['plan_id'] &&
        result['lookup_hash'] == offlineBindingHash(validated) &&
        result['request_id'] == command['request_id'] &&
        result['request_hash'] == validated['request_hash'] &&
        OfflineBinding.fromJson(result['binding']) == expectedBinding,
  );
  final original = _keys(result['original'], {
    'id',
    'project_id',
    'title',
    'revision',
    'status',
    'units',
    'walls',
    'updated_at',
    'updated_by',
  });
  _identifier(original['id']);
  _require(
    original['project_id'] == validated['project_id'] &&
        (validated['plan_id'] == null ||
            original['id'] == validated['plan_id']) &&
        original['title'] == _legacyTitle(command['title']) &&
        original['revision'] is int &&
        original['revision'] ==
            (validated['plan_id'] == null ? 1 : command['revision'] + 1) &&
        original['status'] == 'draft' &&
        original['units'] == 'unitless' &&
        original['updated_by'] == expectedBinding.accountId,
  );
  _drawing(original['walls']);
  _require(_sameJson(original['walls'], command['walls']));
  _instant(original['updated_at']);
  return Map<String, dynamic>.from(jsonDecode(jsonEncode(result)));
}

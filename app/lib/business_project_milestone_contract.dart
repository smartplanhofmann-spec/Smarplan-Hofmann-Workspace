import 'dart:convert';

import 'package:cryptography/dart.dart';

import 'api.dart';

const milestoneFeature = 'project_milestones';
const milestoneModule = 'project_milestones';
const milestoneStatuses = {
  'planned': 'Geplant',
  'achieved': 'Erreicht',
  'cancelled': 'Aufgehoben',
};
const milestoneFields = [
  'title',
  'details',
  'due_date',
  'assignee_id',
  'status',
];
const _recordFields = {
  'schema_version',
  'id',
  'project_id',
  'title',
  'details',
  'due_date',
  'assignee_id',
  'status',
  'revision',
  'created_by',
  'created_at',
  'updated_by',
  'updated_at',
  'content_hash',
};
final _identifier = RegExp(r'^[a-f0-9]{32}$');
final _digest = RegExp(r'^[a-f0-9]{64}$');

Never _invalid() => throw const ApiException(
  0,
  'Der Meilenstein-Nachweis ist ungültig oder gehört zu einem anderen Projekt. Der ursprüngliche Auftrag bleibt erhalten.',
);

void _require(bool value) {
  if (!value) _invalid();
}

Map<String, dynamic> _map(dynamic raw) {
  _require(raw is Map && raw.keys.every((key) => key is String));
  return Map<String, dynamic>.from(raw as Map);
}

Map<String, dynamic> _keys(dynamic raw, Set<String> keys) {
  final value = _map(raw);
  _require(value.length == keys.length && keys.every(value.containsKey));
  return value;
}

void _id(dynamic value) =>
    _require(value is String && _identifier.hasMatch(value));

void _revision(dynamic value) =>
    _require(value is int && value >= 1 && value < 2147483648);

void _day(dynamic value) {
  _require(value is String && RegExp(r'^\d{4}-\d{2}-\d{2}$').hasMatch(value));
  final date = DateTime.tryParse('${value}T00:00:00Z');
  _require(
    date != null &&
        date.year >= 1900 &&
        date.year <= 2200 &&
        date.toIso8601String().substring(0, 10) == value,
  );
}

DateTime _instant(dynamic raw) {
  _require(raw is String);
  final value = raw as String;
  final match = RegExp(
    r'^(\d{4}-\d{2}-\d{2})T(\d{2}):(\d{2}):(\d{2})(?:\.\d{1,9})?(Z|[+-](\d{2}):(\d{2}))$',
  ).firstMatch(value);
  _require(match != null);
  final date = DateTime.tryParse('${match![1]}T00:00:00Z');
  final instant = DateTime.tryParse(value);
  _require(
    date != null &&
        date.year >= 1 &&
        date.toIso8601String().substring(0, 10) == match[1] &&
        int.parse(match[2]!) <= 23 &&
        int.parse(match[3]!) <= 59 &&
        int.parse(match[4]!) <= 59 &&
        (match[6] == null || int.parse(match[6]!) <= 23) &&
        (match[7] == null || int.parse(match[7]!) <= 59) &&
        instant != null,
  );
  return instant!;
}

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

void _fields(Map<String, dynamic> value) {
  _require(
    value['title'] is String &&
        (value['title'] as String).trim().isNotEmpty &&
        (value['title'] as String).runes.length <= 200 &&
        value['details'] is String &&
        (value['details'] as String).runes.length <= 10000 &&
        milestoneStatuses.containsKey(value['status']),
  );
  for (final field in ['title', 'details']) {
    _require(_unicodeScalars(value[field] as String));
    _require(
      !(value[field] as String).runes.any(
        (code) =>
            (code < 32 && !const [9, 10, 13].contains(code)) || code == 127,
      ),
    );
  }
  if (value['due_date'] != null) _day(value['due_date']);
  if (value['assignee_id'] != null) _id(value['assignee_id']);
}

String _canonical(dynamic value) {
  if (value is Map) {
    final map = _map(value), keys = map.keys.toList()..sort();
    return '{${keys.map((key) => '${jsonEncode(key)}:${_canonical(map[key])}').join(',')}}';
  }
  if (value is List) return '[${value.map(_canonical).join(',')}]';
  _require(value == null || value is String || value is int || value is bool);
  return jsonEncode(value);
}

String milestoneHash(dynamic value) => const DartSha256()
    .hashSync(utf8.encode(_canonical(value)))
    .bytes
    .map((byte) => byte.toRadixString(16).padLeft(2, '0'))
    .join();

/// Read the exact versioned original. Current team membership never changes it.
Map<String, dynamic> milestoneRecord(
  dynamic raw,
  String project, {
  String? id,
}) {
  _id(project);
  final value = _keys(raw, _recordFields);
  _require(value['schema_version'] is int && value['schema_version'] == 1);
  _id(value['id']);
  _require(value['project_id'] == project && (id == null || value['id'] == id));
  _fields(value);
  _revision(value['revision']);
  _id(value['created_by']);
  _id(value['updated_by']);
  _instant(value['created_at']);
  _instant(value['updated_at']);
  final hash = value['content_hash'];
  _require(hash is String && _digest.hasMatch(hash));
  _require(milestoneHash({...value}..remove('content_hash')) == hash);
  return value;
}

List<Map<String, dynamic>> milestoneList(dynamic raw, String project) {
  _id(project);
  final value = _keys(raw, {'schema_version', 'project_id', 'items'});
  _require(
    value['schema_version'] is int &&
        value['schema_version'] == 1 &&
        value['project_id'] == project &&
        value['items'] is List,
  );
  final ids = <String>{};
  return [
    for (final item in value['items'] as List)
      (() {
        final record = milestoneRecord(item, project);
        _require(ids.add(record['id'] as String));
        return record;
      })(),
  ];
}

List<Map<String, dynamic>> milestoneHistory(
  dynamic raw,
  String project,
  String id, {
  Map<String, dynamic>? anchor,
}) {
  _id(project);
  final value = _keys(raw, {
    'schema_version',
    'project_id',
    'milestone_id',
    'items',
  });
  _id(id);
  _require(
    value['schema_version'] is int &&
        value['schema_version'] == 1 &&
        value['project_id'] == project &&
        value['milestone_id'] == id &&
        value['items'] is List &&
        (value['items'] as List).isNotEmpty,
  );
  final records = <Map<String, dynamic>>[];
  for (final item in value['items'] as List) {
    final record = milestoneRecord(item, project, id: id);
    _require(record['revision'] == records.length + 1);
    if (records.isNotEmpty) {
      final previous = records.last;
      _require(
        record['created_by'] == previous['created_by'] &&
            record['created_at'] == previous['created_at'],
      );
    }
    records.add(record);
  }
  if (anchor != null) {
    final original = milestoneRecord(anchor, project, id: id);
    final revision = original['revision'] as int;
    _require(
      records.length >= revision &&
          _canonical(records[revision - 1]) == _canonical(original),
    );
  }
  return records;
}

/// Prepare the full input without a nonce; BusinessSession freezes request_id.
Map<String, dynamic> milestoneBody(
  Map<String, dynamic> values, {
  int? revision,
}) {
  try {
    final fields = _keys(values, milestoneFields.toSet());
    _fields(fields);
    if (revision != null) _revision(revision);
    return {
      'schema_version': 1,
      ...fields,
      if (revision != null) 'revision': revision,
    };
  } on ApiException {
    throw const FormatException(
      'Bitte Titel (höchstens 200 Zeichen), Beschreibung (höchstens 10.000 Zeichen), Datum und Verantwortlichen prüfen.',
    );
  }
}

void Function(dynamic) milestoneReceiptValidator(
  String project,
  Map<String, dynamic> expected, {
  Map<String, dynamic>? previous,
  String? expectedActor,
}) {
  _id(project);
  if (expectedActor != null) _id(expectedActor);
  final fields = _keys(expected, {
    'schema_version',
    ...milestoneFields,
    if (previous != null) 'revision',
  });
  _require(fields['schema_version'] is int && fields['schema_version'] == 1);
  _fields(fields);
  final old = previous == null ? null : milestoneRecord(previous, project);
  if (old != null) {
    _revision(fields['revision']);
    _require(fields['revision'] == old['revision']);
  }
  return (dynamic raw) {
    final record = milestoneRecord(raw, project, id: old?['id']);
    _require(
      record['revision'] == (old == null ? 1 : (old['revision'] as int) + 1) &&
          milestoneFields.every((field) => record[field] == fields[field]) &&
          (expectedActor == null ||
              (record['updated_by'] == expectedActor &&
                  (old != null || record['created_by'] == expectedActor))),
    );
    if (old != null) {
      _require(
        record['created_by'] == old['created_by'] &&
            record['created_at'] == old['created_at'],
      );
    }
  };
}

/// Today’s project team is an editor choice source, never a historical name.
List<Map<String, dynamic>> milestoneTeam(dynamic raw, String project) {
  _id(project);
  final workspace = _map(raw), record = _map(workspace['project']);
  _require(record['id'] == project && workspace['team'] is List);
  final ids = <String>{};
  return [
    for (final item in workspace['team'] as List)
      (() {
        final member = _keys(item, {'id', 'email', 'role'});
        _id(member['id']);
        _require(
          ids.add(member['id'] as String) &&
              member['email'] is String &&
              (member['email'] as String).trim().isNotEmpty &&
              member['role'] is String &&
              (member['role'] as String).isNotEmpty,
        );
        return member;
      })(),
  ];
}

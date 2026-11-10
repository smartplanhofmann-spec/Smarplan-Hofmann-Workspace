import 'dart:convert';
import 'dart:typed_data';

import 'api.dart';
import 'offline_binding.dart';

const legacyReportRecoveryFeature = 'offline_service_report_recovery';
const _kind = 'service_report_capture';
const _action = 'business.entry.offline.captured';
final _identifier = RegExp(r'^[a-f0-9]{32}$');
final _digest = RegExp(r'^[a-f0-9]{64}$');
Never _bad() => throw const ApiException(
  0,
  'Die ursprüngliche Protokollfassung ist nicht vollständig belegt. Der alte Auftrag bleibt erhalten.',
);
void _need(bool value) {
  if (!value) _bad();
}

Map<String, dynamic> _map(dynamic value) {
  _need(value is Map && value.keys.every((k) => k is String));
  return Map<String, dynamic>.from(value as Map);
}

Map<String, dynamic> _exact(dynamic value, Set<String> fields) {
  final map = _map(value);
  _need(map.length == fields.length && fields.every(map.containsKey));
  return map;
}

// This NEW read-only hash encodes floats by their exact binary64 bytes. It
// never guesses Python's historical decimal formatting or rewrites a capture.
dynamic _typed(dynamic value) {
  if (value is double) {
    _need(value.isFinite);
    final data = ByteData(8)..setFloat64(0, value, Endian.big);
    return {
      r'$float64': List.generate(
        8,
        (i) => data.getUint8(i).toRadixString(16).padLeft(2, '0'),
      ).join(),
    };
  }
  if (value is List) return value.map(_typed).toList();
  if (value is Map)
    return {for (final e in _map(value).entries) e.key: _typed(e.value)};
  return value;
}

String legacyReportProofHash(dynamic value) =>
    offlineBindingHash(_typed(value));
bool _same(dynamic a, dynamic b) =>
    offlineBindingCanonical(_typed(a)) == offlineBindingCanonical(_typed(b));
void _text(dynamic value, int maximum, {bool required = false}) {
  _need(
    value is String &&
        value.runes.length <= maximum &&
        (!required || value.trim().isNotEmpty) &&
        !RegExp(r'[\x00-\x08\x0b-\x1f]').hasMatch(value),
  );
  // The common canonical serializer also rejects unpaired UTF-16 surrogates.
  offlineBindingCanonical(value);
}

DateTime _instant(dynamic value) {
  _need(
    value is String &&
        RegExp(r'^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d{1,6})?(?:Z|\+00:00)$')
            .hasMatch(value),
  );
  final parsed = DateTime.tryParse(value as String);
  _need(
    parsed != null &&
        parsed.isUtc &&
        parsed.year >= 1900 &&
        parsed.year <= 2200 &&
        parsed.toIso8601String().substring(0, 19) == value.substring(0, 19),
  );
  return parsed!;
}

class LegacyReportConfirmation {
  const LegacyReportConfirmation(
    this.signedAt,
    this.receivedAt,
    this.pdfSha256,
  );
  final DateTime signedAt, receivedAt;
  final String pdfSha256;
}

class LegacyReportOriginal {
  LegacyReportOriginal._(this.accountId, this._capture);
  final String accountId;
  final Map<String, dynamic> _capture;
  String get entryId => _capture['entry_id'];
  String get projectId => _capture['project_id'];
  String get requestId => _capture['request_id'];
  Map<String, dynamic> get _body => {..._capture}..remove('project_id');
  String get captureHash =>
      legacyReportProofHash([_action, projectId, entryId, _body]);
  String get signatureHash => legacyReportProofHash({
    for (final k in ['content_hash', 'signer', 'strokes', 'signed_at'])
      k: _capture[k],
  });

  factory LegacyReportOriginal.fromCache(
    dynamic raw, {
    required String accountId,
  }) {
    _need(_identifier.hasMatch(accountId));
    final record = _map(raw),
        body = _exact(record['capture_request'], {
          'request_id',
          'entry_id',
          'project_id',
          'content',
          'content_hash',
          'signer',
          'strokes',
          'signed_at',
        });
    for (final key in ['request_id', 'entry_id', 'project_id'])
      _need(body[key] is String && _identifier.hasMatch(body[key]));
    final content = _exact(body['content'], {
      'title',
      'description',
      'notes',
      'project_name',
      'customer',
      'captured_at',
    });
    for (final e in {
      'title': 300,
      'description': 30000,
      'notes': 10000,
      'project_name': 500,
      'customer': 500,
    }.entries)
      _text(content[e.key], e.value, required: e.key != 'notes');
    _text(body['signer'], 200, required: true);
    final captured = _instant(content['captured_at']),
        signed = _instant(body['signed_at']);
    _need(!signed.isBefore(captured));
    final strokes = body['strokes'];
    _need(strokes is List && strokes.isNotEmpty && strokes.length <= 100);
    var count = 0;
    for (final stroke in strokes as List) {
      _need(stroke is List && stroke.length >= 2 && stroke.length <= 2000);
      count += (stroke as List).length;
      for (final point in stroke) {
        _need(
          point is List &&
              point.length == 2 &&
              point.every((n) => n is num && n.isFinite && n >= 0 && n <= 1),
        );
      }
    }
    _need(
      count <= 10000 &&
          record['status'] == 'signed' &&
          record['kind'] == 'service' &&
          record['id'] == body['entry_id'] &&
          record['project_id'] == body['project_id'] &&
          _same(record['content'], content) &&
          record['content_hash'] == body['content_hash'] &&
          record['signer'] == body['signer'] &&
          record['signed_at'] == body['signed_at'] &&
          _same(record['strokes'], strokes) &&
          body['content_hash'] ==
              offlineBindingHash([
                body['entry_id'],
                body['project_id'],
                content,
              ]) &&
          utf8.encode(jsonEncode(body)).length <= 1000000,
    );
    return LegacyReportOriginal._(
      accountId,
      Map<String, dynamic>.from(jsonDecode(jsonEncode(body)) as Map),
    );
  }

  Map<String, dynamic> query({required String nonce}) {
    _need(_identifier.hasMatch(nonce));
    return {
      'schema_version': 4,
      'nonce': nonce,
      'kind': _kind,
      'project_id': projectId,
      'entry_id': entryId,
      'request_id': requestId,
      'capture_hash': captureHash,
    };
  }

  LegacyReportConfirmation match(
    dynamic raw, {
    required Map<String, dynamic> request,
    required OfflineBinding binding,
  }) {
    _need(
      binding.accountId == accountId &&
          _same(query(nonce: request['nonce']), request),
    );
    final value = _exact(raw, {
      'schema_version',
      'nonce',
      'lookup_hash',
      'binding',
      'kind',
      'project_id',
      'entry_id',
      'request_id',
      'capture_hash',
      'original',
    });
    _need(
      value['schema_version'] == 4 &&
          value['schema_version'] is int &&
          value['nonce'] == request['nonce'] &&
          value['lookup_hash'] == offlineBindingHash(request) &&
          OfflineBinding.fromJson(
                value['binding'],
                expectedAccountId: accountId,
              ) ==
              binding &&
          value['kind'] == _kind &&
          value['project_id'] == projectId &&
          value['entry_id'] == entryId &&
          value['request_id'] == requestId &&
          value['capture_hash'] == captureHash,
    );
    final original = _exact(value['original'], {
      'schema_version',
      'entry_id',
      'project_id',
      'request_id',
      'request_hash',
      'capture_hash',
      'actor_id',
      'revision',
      'content_hash',
      'archive_content_hash',
      'signature_sha256',
      'pdf_sha256',
      'signed_at',
      'received_at',
    });
    _need(
      original['schema_version'] == 1 &&
          original['schema_version'] is int &&
          original['revision'] == 2 &&
          original['revision'] is int &&
          original['entry_id'] == entryId &&
          original['project_id'] == projectId &&
          original['request_id'] == requestId &&
          original['actor_id'] == accountId &&
          original['capture_hash'] == captureHash &&
          original['content_hash'] == _capture['content_hash'] &&
          original['signature_sha256'] == signatureHash &&
          original['signed_at'] == _capture['signed_at'],
    );
    for (final key in ['request_hash', 'archive_content_hash', 'pdf_sha256'])
      _need(original[key] is String && _digest.hasMatch(original[key]));
    final signed = _instant(original['signed_at']),
        received = _instant(original['received_at']);
    _need(!signed.isAfter(received.add(const Duration(minutes: 5))));
    return LegacyReportConfirmation(signed, received, original['pdf_sha256']);
  }

  void clear() => _capture.clear();
}

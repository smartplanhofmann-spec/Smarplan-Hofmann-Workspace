import 'dart:convert';
import 'dart:io';

import 'api.dart';
import 'offline_vault.dart';
import 'project_creation_journal.dart';

bool _keys(Map value, Set<String> expected) =>
    value.length == expected.length && expected.every(value.containsKey);

bool _id(Object? value) =>
    value is String &&
    value.length == 32 &&
    RegExp(r'^[a-f0-9]{32}$').hasMatch(value);

bool _unicode(String value) =>
    !value.runes.any((rune) => rune >= 0xd800 && rune <= 0xdfff);

/// Compare stored commands independently of map order, preserving exact text.
String serviceCreationCanonical(Object? value) {
  if (value is Map) {
    if (value.keys.any((key) => key is! String)) {
      throw const FormatException('Invalid service journal key');
    }
    final keys = value.keys.cast<String>().toList()..sort();
    return '{${keys.map((key) => '${serviceCreationCanonical(key)}:${serviceCreationCanonical(value[key])}').join(',')}}';
  }
  if (value is List) {
    return '[${value.map(serviceCreationCanonical).join(',')}]';
  }
  if (value is String && !_unicode(value)) {
    throw const FormatException('Invalid service journal text');
  }
  return jsonEncode(value);
}

bool _space(int rune) =>
    rune == 0x20 ||
    rune >= 0x09 && rune <= 0x0d ||
    rune >= 0x1c && rune <= 0x1f ||
    rune == 0x85 ||
    rune == 0xa0 ||
    rune == 0x1680 ||
    rune >= 0x2000 && rune <= 0x200a ||
    rune == 0x2028 ||
    rune == 0x2029 ||
    rune == 0x202f ||
    rune == 0x205f ||
    rune == 0x3000;

bool _text(Object? value, int maximum) =>
    value is String &&
    _unicode(value) &&
    value.runes.length <= maximum &&
    !value.runes.any((rune) => rune < 32 && rune != 9 && rune != 10) &&
    !value.runes.every(_space);

bool _date(Object? value) {
  if (value == null) return true;
  if (value is! String || !RegExp(r'^\d{4}-\d{2}-\d{2}$').hasMatch(value)) {
    return false;
  }
  final year = int.parse(value.substring(0, 4));
  final month = int.parse(value.substring(5, 7));
  final day = int.parse(value.substring(8, 10));
  final date = DateTime.utc(year, month, day);
  return year >= 1900 &&
      year <= 2200 &&
      date.year == year &&
      date.month == month &&
      date.day == day;
}

/// Only the existing manual create command belongs in this journal.
/// Validation never trims, normalizes, fills in or removes a field.
Map<String, dynamic> validateServiceCreationCommand(Object? value) {
  if (value is! Map ||
      !_keys(value, {
        'request_id',
        'revision',
        'customer_id',
        'person_id',
        'project_id',
        'asset_id',
        'contract_id',
        'visit_id',
        'inquiry_id',
        'defect_id',
        'title',
        'kind',
        'priority',
        'responsible_id',
        'follow_up_on',
        'description',
      }) ||
      !_id(value['request_id']) ||
      value['revision'] is! int ||
      value['revision'] != 0 ||
      !_id(value['customer_id']) ||
      !_id(value['responsible_id']) ||
      [
        'person_id',
        'project_id',
        'asset_id',
        'contract_id',
      ].any((key) => value[key] != null && !_id(value[key])) ||
      [
        'visit_id',
        'inquiry_id',
        'defect_id',
      ].any((key) => value[key] != null) ||
      !_text(value['title'], 300) ||
      !_text(value['description'], 10000) ||
      !const ['request', 'complaint', 'maintenance'].contains(value['kind']) ||
      !const ['low', 'normal', 'high', 'urgent'].contains(value['priority']) ||
      !_date(value['follow_up_on'])) {
    throw const FormatException('Invalid manual service creation command');
  }
  return Map<String, dynamic>.from(value);
}

void _scope(ProjectCreationScope scope) {
  if (!_id(scope.accountId) ||
      !_id(scope.instanceId) ||
      scope.server.isEmpty ||
      scope.version.isEmpty ||
      !_unicode(scope.server) ||
      !_unicode(scope.version)) {
    throw const ApiException(
      0,
      'Die Unternehmensbindung des Serviceauftrags konnte nicht bestätigt werden.',
    );
  }
}

Map<String, dynamic>? _state(
  Map<String, dynamic>? value,
  ProjectCreationScope scope,
) {
  if (value == null) return null;
  if (!_keys(value, {'schema_version', 'scope', 'pending'}) ||
      value['schema_version'] is! int ||
      value['schema_version'] != 1 ||
      value['scope'] is! Map ||
      !_keys(value['scope'] as Map, {
        'server',
        'version',
        'account_id',
        'instance_id',
      })) {
    throw const FormatException('Invalid service journal');
  }
  final saved = value['scope'] as Map;
  if (saved['server'] != scope.server ||
      saved['version'] != scope.version ||
      saved['account_id'] != scope.accountId ||
      !_id(saved['instance_id'])) {
    throw const FormatException('Invalid service journal scope');
  }
  // Check the origin before even validating the private command. A different
  // company may replace an empty journal, but cannot inspect an unresolved one.
  if (value['pending'] != null && saved['instance_id'] != scope.instanceId) {
    throw const ApiException(
      0,
      'Ein früherer Serviceauftrag wartet auf die ursprüngliche Unternehmensanmeldung. Es wurde nichts erneut gesendet.',
    );
  }
  return {
    'schema_version': 1,
    'scope': Map<String, dynamic>.from(saved),
    'pending': value['pending'] == null
        ? null
        : validateServiceCreationCommand(value['pending']),
  };
}

Future<Map<String, dynamic>?> _read(
  OfflineVault vault,
  ProjectCreationScope scope,
  void Function() requireCurrent,
) async {
  requireCurrent();
  final type = await FileSystemEntity.type(
    vault.directory.path,
    followLinks: false,
  );
  requireCurrent();
  if (type != FileSystemEntityType.notFound &&
      type != FileSystemEntityType.directory) {
    throw const FormatException('Invalid service journal directory');
  }
  if (type == FileSystemEntityType.directory) {
    final files = await vault.directory.list(followLinks: false).toList();
    requireCurrent();
    for (final file in files) {
      final name = file.uri.pathSegments.last;
      if (file is Link ||
          name.startsWith('state-') &&
              (file is! File ||
                  !RegExp(r'^state-\d{16}\.enc$').hasMatch(name) ||
                  name == 'state-0000000000000000.enc')) {
        throw const FormatException('Unresolved service journal state');
      }
    }
  }
  requireCurrent();
  final value = await vault.read();
  requireCurrent();
  return _state(value, scope);
}

/// This journal preserves one uncertain online command, not offline authority.
class ServiceCreationJournal {
  final OfflineDevice device;
  ServiceCreationJournal({OfflineDevice? device})
    : device = device ?? OfflineDevice();

  Future<ServiceCreationJournalSession> open({
    required ProjectCreationScope scope,
    void Function()? requireCurrent,
  }) async {
    final guard = requireCurrent ?? () {};
    guard();
    _scope(scope);
    final namespace = jsonEncode([
      'service-creation-journal-v1',
      scope.server,
      scope.version,
    ]);
    try {
      // Discover retained state before allowing key creation. A quarantined
      // commit with a missing key must not silently acquire a replacement key.
      final existing = await device.openExisting(namespace, scope.accountId);
      guard();
      final vault =
          existing ??
          await device.open(namespace, scope.accountId, create: true);
      guard();
      final value = await _read(vault, scope, guard);
      guard();
      return ServiceCreationJournalSession._(vault, value, scope, guard);
    } on ApiException {
      rethrow;
    } catch (_) {
      throw const ApiException(
        0,
        'Der geschützte Serviceauftrag konnte nicht gelesen werden. Es wurde nichts gesendet. Den lokalen Speicher erhalten und prüfen lassen.',
      );
    }
  }
}

class ServiceCreationJournalSession {
  final OfflineVault _vault;
  final ProjectCreationScope scope;
  final void Function() _requireCurrent;
  Map<String, dynamic>? _value;
  int _generation;
  Future<void> _tail = Future<void>.value();

  ServiceCreationJournalSession._(
    this._vault,
    this._value,
    this.scope,
    this._requireCurrent,
  ) : _generation = _vault.generation;

  Map<String, dynamic>? get pending {
    _requireCurrent();
    final command = _value?['pending'];
    return command == null ? null : validateServiceCreationCommand(command);
  }

  Future<void> _serialize(Future<void> Function() action) {
    final next = _tail.then((_) => action());
    _tail = next.then<void>((_) {}, onError: (Object e, StackTrace s) {});
    return next;
  }

  Future<void> _compare() async {
    _requireCurrent();
    final latest = await _read(_vault, scope, _requireCurrent);
    _requireCurrent();
    if (_vault.generation != _generation ||
        serviceCreationCanonical(latest) != serviceCreationCanonical(_value)) {
      throw const ApiException(
        0,
        'Der geschützte Serviceauftrag wurde in einem anderen Fenster geändert. Bitte erneut öffnen. Es wurde nichts gesendet.',
      );
    }
  }

  Future<void> prepare(Map<String, dynamic> command) {
    _requireCurrent();
    final original = validateServiceCreationCommand(command);
    return _serialize(() async {
      try {
        await _compare();
        final current = pending;
        if (current != null) {
          if (serviceCreationCanonical(current) !=
              serviceCreationCanonical(original)) {
            throw const ApiException(
              409,
              'Der ursprüngliche Serviceauftrag muss zuerst geklärt werden.',
            );
          }
          return;
        }
        final next = {
          'schema_version': 1,
          'scope': scope.toJson(),
          'pending': original,
        };
        _requireCurrent();
        await _vault.write(next);
        _requireCurrent();
        _value = next;
        _generation = _vault.generation;
      } on ApiException {
        rethrow;
      } catch (_) {
        throw const ApiException(
          0,
          'Der Serviceauftrag konnte nicht dauerhaft gespeichert werden. Es wurde nichts gesendet.',
          requestResolution: 'not_accepted',
        );
      }
    });
  }

  /// The caller alone decides whether the original server outcome is resolved.
  Future<void> clear(Map<String, dynamic> command) {
    _requireCurrent();
    final original = validateServiceCreationCommand(command);
    return _serialize(() async {
      try {
        await _compare();
        final current = pending;
        if (current == null ||
            serviceCreationCanonical(current) !=
                serviceCreationCanonical(original)) {
          throw const ApiException(
            0,
            'Der ursprüngliche Serviceauftrag stimmt nicht überein.',
          );
        }
        final next = {
          'schema_version': 1,
          'scope': scope.toJson(),
          'pending': null,
        };
        _requireCurrent();
        await _vault.write(next);
        _requireCurrent();
        _value = next;
        _generation = _vault.generation;
      } on ApiException {
        rethrow;
      } catch (_) {
        throw const ApiException(
          0,
          'Die Bestätigung konnte nicht lokal abgeschlossen werden. Derselbe Serviceauftrag bleibt zur sicheren Wiederholung erhalten.',
        );
      }
    });
  }
}

import 'dart:convert';
import 'dart:io';

import 'api.dart';
import 'offline_vault.dart';
import 'project_creation_journal.dart';
import 'service_creation_journal.dart' show serviceCreationCanonical;

typedef OnlineCommandValidator = Map<String, dynamic> Function(Object?);

bool _keys(Map value, Set<String> keys) =>
    value.length == keys.length && keys.every(value.containsKey);
bool _id(Object? value) =>
    value is String && RegExp(r'^[a-f0-9]{32}$').hasMatch(value);

/// A retained original is online recovery data, never an offline permission.
/// Company binding stays inside ciphertext so a replacement company on the
/// same host cannot bypass an unresolved original by selecting a new directory.
class OnlineCommandJournal {
  OnlineCommandJournal({OfflineDevice? device})
    : device = device ?? OfflineDevice();
  final OfflineDevice device;

  Future<OnlineCommandJournalSession> open({
    required ProjectCreationScope scope,
    required String slot,
    required OnlineCommandValidator validate,
    required void Function() requireCurrent,
  }) async {
    requireCurrent();
    if (!_id(scope.accountId) ||
        !_id(scope.instanceId) ||
        scope.server.isEmpty ||
        scope.version.isEmpty ||
        !RegExp(
          r'^(material-return:(global|[a-f0-9]{32})|mileage:[a-f0-9]{32})$',
        ).hasMatch(slot)) {
      throw const ApiException(
        0,
        'Die Firmenbindung des offenen Auftrags fehlt.',
      );
    }
    final namespace = jsonEncode([
      'online-command-journal-v1',
      scope.server,
      scope.version,
      slot,
    ]);
    try {
      final existing = await device.openExisting(namespace, scope.accountId);
      requireCurrent();
      final vault =
          existing ??
          await device.open(namespace, scope.accountId, create: true);
      requireCurrent();
      final session = OnlineCommandJournalSession._(
        vault,
        scope,
        slot,
        validate,
        requireCurrent,
      );
      session._value = await session._read();
      session._generation = vault.generation;
      return session;
    } on ApiException {
      rethrow;
    } catch (_) {
      throw const ApiException(
        0,
        'Der geschützte Originalauftrag konnte nicht gelesen werden. '
        'Es wurde nichts gesendet. Den lokalen Speicher erhalten und prüfen lassen.',
      );
    }
  }
}

class OnlineCommandJournalSession {
  OnlineCommandJournalSession._(
    this._vault,
    this.scope,
    this.slot,
    this._validate,
    this._requireCurrent,
  );
  final OfflineVault _vault;
  final ProjectCreationScope scope;
  final String slot;
  final OnlineCommandValidator _validate;
  final void Function() _requireCurrent;
  Map<String, dynamic>? _value;
  int _generation = 0;
  Future<void> _tail = Future<void>.value();

  Map<String, dynamic> _checked(Object? raw) {
    // Bound size and reject unsupported/corrupt values before JSON copying.
    final text = serviceCreationCanonical(raw);
    if (utf8.encode(text).length > 1048576) {
      throw const FormatException('Original command exceeds recovery limit');
    }
    return _validate(jsonDecode(text));
  }

  Map<String, dynamic>? get pending {
    _requireCurrent();
    final value = _value?['pending'];
    return value == null ? null : _checked(value);
  }

  Future<Map<String, dynamic>?> _read() async {
    _requireCurrent();
    final type = await FileSystemEntity.type(
      _vault.directory.path,
      followLinks: false,
    );
    _requireCurrent();
    if (type != FileSystemEntityType.notFound &&
        type != FileSystemEntityType.directory) {
      throw const FormatException('Invalid original journal directory');
    }
    if (type == FileSystemEntityType.directory) {
      final entries = await _vault.directory.list(followLinks: false).toList();
      _requireCurrent();
      for (final entry in entries) {
        final name = entry.uri.pathSegments.last;
        if (entry is Link ||
            name.startsWith('state-') &&
                (entry is! File ||
                    !RegExp(r'^state-\d{16}\.enc$').hasMatch(name) ||
                    name == 'state-0000000000000000.enc')) {
          throw const FormatException('Unresolved original journal state');
        }
      }
    }
    final value = await _vault.read();
    _requireCurrent();
    if (value == null) return null;
    if (!_keys(value, {'schema_version', 'scope', 'slot', 'pending'}) ||
        value['schema_version'] is! int ||
        value['schema_version'] != 1 ||
        value['slot'] != slot ||
        value['scope'] is! Map ||
        !_keys(value['scope'], {
          'server',
          'version',
          'account_id',
          'instance_id',
        })) {
      throw const FormatException('Invalid original journal');
    }
    final saved = value['scope'];
    if (saved['server'] != scope.server ||
        saved['version'] != scope.version ||
        saved['account_id'] != scope.accountId ||
        !_id(saved['instance_id'])) {
      throw const FormatException('Invalid original journal identity');
    }
    if (value['pending'] != null && saved['instance_id'] != scope.instanceId) {
      throw const ApiException(
        0,
        'Ein früherer Auftrag wartet auf die ursprüngliche Unternehmensanmeldung. '
        'Es wurde nichts erneut gesendet.',
      );
    }
    return {
      ...value,
      'pending': value['pending'] == null ? null : _checked(value['pending']),
    };
  }

  Future<void> _serialized(Future<void> Function() action) {
    final next = _tail.then((_) => action());
    _tail = next.then<void>((_) {}, onError: (Object e, StackTrace s) {});
    return next;
  }

  Future<void> _compare() async {
    final latest = await _read();
    if (_vault.generation != _generation ||
        serviceCreationCanonical(latest) != serviceCreationCanonical(_value)) {
      throw const ApiException(
        0,
        'Der Originalauftrag wurde in einem anderen Fenster geändert. '
        'Bitte erneut öffnen. Es wurde nichts gesendet.',
      );
    }
  }

  Future<void> prepare(Map<String, dynamic> command) {
    _requireCurrent();
    final original = _checked(command);
    return _serialized(() async {
      try {
        await _compare();
        final old = pending;
        if (old != null) {
          if (serviceCreationCanonical(old) !=
              serviceCreationCanonical(original)) {
            throw const ApiException(
              409,
              'Zuerst die Bestätigung des ursprünglichen Auftrags klären.',
            );
          }
          return;
        }
        final next = {
          'schema_version': 1,
          'scope': scope.toJson(),
          'slot': slot,
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
          'Der Originalauftrag konnte nicht dauerhaft gespeichert werden. '
          'Es wurde nichts gesendet.',
          requestResolution: 'not_accepted',
        );
      }
    });
  }

  /// Recheck both the live company guard and the on-disk original immediately
  /// before looking up a private outcome or sending the unchanged command.
  Future<void> requireOriginal(Map<String, dynamic> command) {
    _requireCurrent();
    final original = _checked(command);
    return _serialized(() async {
      await _compare();
      if (pending == null ||
          serviceCreationCanonical(pending) !=
              serviceCreationCanonical(original)) {
        throw const ApiException(
          0,
          'Der gespeicherte Originalauftrag wurde geändert. Bitte erneut öffnen.',
        );
      }
    });
  }

  /// Call only after the complete original server receipt has been checked.
  Future<void> clear(Map<String, dynamic> command) {
    _requireCurrent();
    final original = _checked(command);
    return _serialized(() async {
      try {
        await _compare();
        if (pending == null ||
            serviceCreationCanonical(pending) !=
                serviceCreationCanonical(original)) {
          throw const ApiException(
            0,
            'Der Originalauftrag stimmt nicht überein.',
          );
        }
        final next = {
          'schema_version': 1,
          'scope': scope.toJson(),
          'slot': slot,
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
          'Die Bestätigung konnte nicht lokal abgeschlossen werden. '
          'Derselbe Originalauftrag bleibt zur sicheren Prüfung erhalten.',
        );
      }
    });
  }
}

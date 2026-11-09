import 'dart:convert';

import 'package:cryptography/cryptography.dart';

import 'api.dart';
import 'offline_vault.dart';

String _canonical(Object? value) {
  if (value is Map) {
    final keys = value.keys.cast<String>().toList()..sort();
    return '{${keys.map((key) => '${jsonEncode(key)}:${_canonical(value[key])}').join(',')}}';
  }
  if (value is List) return '[${value.map(_canonical).join(',')}]';
  return jsonEncode(value);
}

bool _keys(Map value, Set<String> expected) =>
    value.length == expected.length && expected.every(value.containsKey);
bool _id(Object? value) =>
    value is String && RegExp(r'^[a-f0-9]{32}$').hasMatch(value);

/// The scope comes from the authenticated server, never from a form field.
class ProjectCreationScope {
  final String server, version, accountId, instanceId;
  const ProjectCreationScope({
    required this.server,
    required this.version,
    required this.accountId,
    required this.instanceId,
  });

  factory ProjectCreationScope.fromServer(
    Object? value, {
    required String server,
    required String version,
    required Object? accountId,
  }) {
    if (value is! Map ||
        !_keys(value, {'schema_version', 'instance_id', 'account_id'}) ||
        value['schema_version'] != 1 ||
        !_id(value['instance_id']) ||
        !_id(value['account_id']) ||
        value['account_id'] != accountId) {
      throw const ApiException(
        0,
        'Die Unternehmensbindung der Projektanlage konnte nicht bestätigt werden.',
      );
    }
    return ProjectCreationScope(
      server: server,
      version: version,
      accountId: accountId as String,
      instanceId: value['instance_id'] as String,
    );
  }

  Map<String, dynamic> toJson() => {
    'server': server,
    'version': version,
    'account_id': accountId,
    'instance_id': instanceId,
  };
}

/// Separate from plan/time outboxes: this journal grants no offline authority.
/// Reopening it always requires a fresh online identity and company scope.
class ProjectCreationJournal {
  final OfflineDevice device;
  ProjectCreationJournal({OfflineDevice? device})
    : device = device ?? OfflineDevice();

  Future<ProjectCreationJournalSession> open({
    required String server,
    required String version,
    required String accountId,
    required ProjectCreationScope? scope,
  }) async {
    if (!_id(accountId) ||
        (scope != null &&
            (scope.server != server ||
                scope.version != version ||
                scope.accountId != accountId))) {
      throw const ApiException(
        0,
        'Die Projektanlage gehört nicht zu dieser Anmeldung.',
      );
    }
    // Keep the company binding inside the encrypted state. A changed company
    // on the same host cannot silently bypass an outstanding older command.
    final namespace = jsonEncode([
      'project-creation-journal-v1',
      server,
      version,
    ]);
    try {
      final vault = scope == null
          ? await device.openExisting(namespace, accountId)
          : await device.open(namespace, accountId, create: true);
      if (vault == null)
        return ProjectCreationJournalSession._(null, null, null);
      if (await vault.directory.exists()) {
        await for (final file in vault.directory.list(followLinks: false)) {
          final name = file.uri.pathSegments.last;
          if (name.startsWith('state-') &&
              !RegExp(r'^state-\d{16}\.enc$').hasMatch(name)) {
            throw const FormatException('Unresolved project journal state');
          }
        }
      }
      final state = await vault.read();
      if (state != null) {
        if (!_keys(state, {'schema_version', 'scope', 'pending'}) ||
            state['schema_version'] != 1 ||
            state['scope'] is! Map ||
            !_keys(state['scope'] as Map, {
              'server',
              'version',
              'account_id',
              'instance_id',
            })) {
          throw const FormatException('Invalid project journal');
        }
        final saved = state['scope'] as Map;
        if (saved['server'] != server ||
            saved['version'] != version ||
            saved['account_id'] != accountId ||
            !_id(saved['instance_id'])) {
          throw const FormatException('Invalid project journal scope');
        }
        if (state['pending'] != null) {
          _pending(state['pending']);
          if (scope == null ||
              _canonical(saved) != _canonical(scope.toJson())) {
            throw const ApiException(
              0,
              'Eine frühere Projektanlage wartet auf die ursprüngliche Unternehmensanmeldung. Es wurde nichts erneut gesendet.',
            );
          }
        }
      }
      return ProjectCreationJournalSession._(vault, state, scope);
    } on ApiException {
      rethrow;
    } catch (_) {
      throw const ApiException(
        0,
        'Der geschützte Projektauftrag konnte nicht gelesen werden. Es wurde nichts gesendet. Den lokalen Speicher erhalten und prüfen lassen.',
      );
    }
  }
}

Map<String, dynamic> _body(Object? raw) {
  if (raw is! Map ||
      !(_keys(raw, {'request_id', 'name', 'customer_id'}) ||
          _keys(raw, {'request_id', 'name', 'customer'})) ||
      !_id(raw['request_id']) ||
      raw['name'] is! String ||
      (raw['name'] as String).isEmpty ||
      (raw['name'] as String).length > 500 ||
      (raw.containsKey('customer_id') && !_id(raw['customer_id'])) ||
      (raw.containsKey('customer') &&
          (raw['customer'] is! String ||
              (raw['customer'] as String).isEmpty ||
              (raw['customer'] as String).length > 500))) {
    throw const FormatException('Invalid project command');
  }
  return Map<String, dynamic>.from(raw);
}

Map<String, dynamic> _pending(Object? raw) {
  if (raw is! Map || !_keys(raw, {'body', 'customers'})) {
    throw const FormatException('Invalid pending project command');
  }
  final body = _body(raw['body']);
  final customers = raw['customers'];
  if (customers is! List || customers.length > 1) {
    throw const FormatException('Invalid project customer snapshot');
  }
  for (final customer in customers) {
    if (customer is! Map ||
        !_keys(customer, {'id', 'name', 'address', 'active'}) ||
        customer['id'] != body['customer_id'] ||
        !_id(customer['id']) ||
        customer['name'] is! String ||
        customer['address'] is! String ||
        customer['active'] != 1) {
      throw const FormatException('Invalid project customer snapshot');
    }
  }
  if (body.containsKey('customer_id') && customers.length != 1) {
    throw const FormatException('Missing original customer snapshot');
  }
  return offlineCopy(Map<String, dynamic>.from(raw));
}

class ProjectCreationJournalSession {
  final OfflineVault? _vault;
  Map<String, dynamic>? _state;
  final ProjectCreationScope? scope;
  ProjectCreationJournalSession._(this._vault, this._state, this.scope);

  Map<String, dynamic>? get pending =>
      _state?['pending'] == null ? null : _pending(_state!['pending']);

  Future<void> prepare(
    Map<String, dynamic> command,
    List<Map<String, dynamic>> customers,
  ) async {
    if (scope == null) {
      throw const ApiException(
        0,
        'Keine bestätigte Unternehmensbindung für die Projektanlage.',
      );
    }
    final body = _body(command);
    final current = pending;
    if (current != null) {
      if (_canonical(current['body']) != _canonical(body)) {
        throw const ApiException(
          409,
          'Der ursprüngliche Projektauftrag muss zuerst geklärt werden.',
        );
      }
      return;
    }
    final value = _pending({
      'body': body,
      'customers': [
        for (final c in customers)
          if (c['id'] == body['customer_id'])
            {
              'id': c['id'],
              'name': c['name'],
              'address': c['address'] ?? '',
              'active': 1,
            },
      ],
    });
    final next = {
      'schema_version': 1,
      'scope': scope!.toJson(),
      'pending': value,
    };
    try {
      await _vault!.write(next);
      _state = next;
    } catch (_) {
      throw const ApiException(
        0,
        'Der Projektauftrag konnte nicht dauerhaft gespeichert werden. Es wurde nichts gesendet.',
        requestResolution: 'not_accepted',
      );
    }
  }

  Future<void> clear(Map<String, dynamic> command) async {
    if (scope == null ||
        pending == null ||
        _canonical(pending!['body']) != _canonical(command)) {
      throw const ApiException(
        0,
        'Der ursprüngliche Projektauftrag stimmt nicht überein.',
      );
    }
    final next = {
      'schema_version': 1,
      'scope': scope!.toJson(),
      'pending': null,
    };
    try {
      await _vault!.write(next);
      _state = next;
    } catch (_) {
      throw const ApiException(
        0,
        'Die Bestätigung konnte nicht lokal abgeschlossen werden. Derselbe Projektauftrag bleibt zur sicheren Wiederholung erhalten.',
      );
    }
  }

  Future<void> verifyReceipt(
    Map<String, dynamic> command,
    Object? result,
    Object? receipt,
  ) async {
    final body = _body(command);
    final expectedHash = (await Sha256().hash(
      utf8.encode(
        _canonical({
          'operation': 'core.project.create:v1',
          'data': {
            'request_id': body['request_id'],
            'name': body['name'],
            'customer': body['customer'],
            'customer_id': body['customer_id'],
          },
        }),
      ),
    )).bytes.map((v) => v.toRadixString(16).padLeft(2, '0')).join();
    if (scope == null ||
        result is! Map ||
        !_keys(result, {'id'}) ||
        !_id(result['id']) ||
        receipt is! Map ||
        !_keys(receipt, {
          'schema_version',
          'instance_id',
          'account_id',
          'request_id',
          'request_hash',
          'project_id',
        }) ||
        receipt['schema_version'] != 1 ||
        receipt['instance_id'] != scope!.instanceId ||
        receipt['account_id'] != scope!.accountId ||
        receipt['request_id'] != body['request_id'] ||
        receipt['request_hash'] != expectedHash ||
        receipt['project_id'] != result['id']) {
      throw const ApiException(
        0,
        'Die ursprüngliche Projektanlage konnte nicht vollständig bestätigt werden. Derselbe Auftrag bleibt erhalten.',
      );
    }
  }
}

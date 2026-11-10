import 'dart:convert';

import 'package:cryptography/cryptography.dart';

import 'api.dart';
import 'business_session.dart';

String? qontoStatusLabel(dynamic status) => const {
  'pending': 'Vorgemerkt',
  'completed': 'Abgeschlossen',
  'declined': 'Abgelehnt',
  'reversed': 'Storniert',
}[status];
Never _bad() => throw const ApiException(
  409,
  'Der Qonto-Lesestand passt nicht eindeutig zum ausgewählten Konto und Zeitraum.',
);

String qontoMoney(dynamic value) {
  if (value is! int || value.abs() > 999999999999999) _bad();
  final cents = value;
  return '${cents < 0 ? '-' : ''}${cents.abs() ~/ 100}.${(cents.abs() % 100).toString().padLeft(2, '0')}';
}

Map<String, dynamic> qontoWindow(Map<String, dynamic> values) {
  final first = DateTime.tryParse('${values['from']}T00:00:00.000Z');
  final last = DateTime.tryParse('${values['to']}T00:00:00.000Z');
  if (first == null ||
      last == null ||
      first.toIso8601String().substring(0, 10) != values['from'] ||
      last.toIso8601String().substring(0, 10) != values['to'] ||
      !last.isAfter(first) ||
      last.difference(first) > const Duration(days: 31)) {
    throw const ApiException(
      400,
      'Einen UTC-Zeitraum von höchstens 31 Tagen wählen. Das Enddatum ist ausgeschlossen.',
    );
  }
  return {
    'updated_from': first.toIso8601String(),
    'updated_to': last.toIso8601String(),
  };
}

dynamic _ordered(dynamic value) => value is List
    ? value.map(_ordered).toList()
    : value is Map
    ? {
        for (final key in (value.keys.cast<String>().toList()..sort()))
          key: _ordered(value[key]),
      }
    : value;

Future<Map<String, dynamic>> qontoReadView(
  dynamic raw, {
  required String accountId,
  required String bindingHash,
  required String iban,
  required Map<String, dynamic> body,
}) async {
  final value = businessMap(raw);
  final hash = RegExp(r'^[a-f0-9]{64}$');
  final uuid = RegExp(r'^[a-f0-9]{8}-(?:[a-f0-9]{4}-){3}[a-f0-9]{12}$');
  if (value['schema_version'] != 1 ||
      value['provider'] != 'qonto' ||
      value['read_only'] != true ||
      value['complete_statement'] != false ||
      value['atomic_snapshot'] != false ||
      value['financial_changes'] != false ||
      value['local_account_id'] != accountId ||
      !RegExp(r'^[a-f0-9]{32}$').hasMatch(accountId) ||
      value['bank_binding_hash'] != bindingHash ||
      !hash.hasMatch(bindingHash) ||
      !hash.hasMatch('${value['content_hash']}') ||
      !uuid.hasMatch('${value['organization']?['id']}') ||
      value['items'] is! List ||
      (value['items'] as List).length > 1000 ||
      value['source_pages'] is! List ||
      (value['source_pages'] as List).length > 12 ||
      value['window']?['updated_from'] != body['updated_from'] ||
      value['window']?['updated_to'] != body['updated_to'] ||
      value['window']?['upper_exclusive'] != true ||
      value['account_before']?['iban'] != iban ||
      value['account_after']?['iban'] != iban)
    _bad();
  final first = DateTime.parse(body['updated_from']),
      last = DateTime.parse(body['updated_to']);
  final seen = <String>{};
  for (final row in businessItems(value['items'])) {
    final changed = DateTime.tryParse('${row['updated_at']}'),
        cents = row['amount_cents'];
    if (!uuid.hasMatch('${row['id']}') ||
        !seen.add('${row['id']}') ||
        !uuid.hasMatch('${row['bank_account_id']}') ||
        qontoStatusLabel(row['status']) == null ||
        !['credit', 'debit'].contains(row['side']) ||
        row['currency'] != 'EUR' ||
        cents is! int ||
        cents < 0 ||
        cents > 999999999999999 ||
        row['signed_amount_cents'] !=
            (row['side'] == 'debit' ? -cents : cents) ||
        changed == null ||
        changed.isBefore(first) ||
        !changed.isBefore(last) ||
        ![
          'label',
          'counterparty',
          'reference',
        ].every((key) => row[key] == null || row[key] is String))
      _bad();
  }
  final payload = {
    for (final entry in value.entries)
      if (![
        'content_hash',
        'read_at',
        'local_account_id',
        'bank_binding_hash',
      ].contains(entry.key))
        entry.key: entry.value,
  };
  final digest = await Sha256().hash(
    utf8.encode(jsonEncode(_ordered(payload))),
  );
  if (digest.bytes.map((v) => v.toRadixString(16).padLeft(2, '0')).join() !=
      value['content_hash'])
    _bad();
  return value;
}

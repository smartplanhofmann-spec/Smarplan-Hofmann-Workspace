import 'dart:convert';

import 'package:cryptography/cryptography.dart';

import 'api.dart';

const camtContract = 'smartplan_bank_camt053_08_v1';
const camtFormat = 'camt.053.001.08';
const camtSchema =
    'c3cfac080dc31476bde7444b05d00e1b23558d5e44529e58d0ad562e6013873d';
const _namespace = 'urn:iso:std:iso:20022:tech:xsd:camt.053.001.08';
final _hash = RegExp(r'^[a-f0-9]{64}$');
Never _fail() => throw const ApiException(
  0,
  'Der XML-Banknachweis gehört nicht zum unveränderten geprüften Original.',
);
Map<String, dynamic> _map(dynamic raw) {
  if (raw is! Map || raw.keys.any((k) => k is! String)) _fail();
  return Map<String, dynamic>.from(raw);
}

Map<String, dynamic> _shape(dynamic raw, String fields) {
  final value = _map(raw), keys = fields.split(' ').toSet();
  if (value.length != keys.length || !value.keys.toSet().containsAll(keys))
    _fail();
  return value;
}

void _integer(dynamic value, [int min = 0, int max = 9007199254740991]) {
  if (value is! int || value < min || value > max) _fail();
}

void _text(dynamic value, int max, {bool nullable = false}) {
  if (nullable && value == null) return;
  if (value is! String || value.runes.isEmpty || value.runes.length > max)
    _fail();
}

String _day(dynamic value) {
  if (value is! String || !RegExp(r'^\d{4}-\d{2}-\d{2}$').hasMatch(value))
    _fail();
  final date = DateTime.tryParse('${value}T00:00:00Z');
  if (date == null ||
      date.year < 1900 ||
      date.year > 2200 ||
      date.toIso8601String().substring(0, 10) != value)
    _fail();
  return value;
}

BigInt _money(dynamic value) {
  if (value is! String ||
      !RegExp(r'^-?(?:0|[1-9]\d{0,10})\.\d{2}$').hasMatch(value) ||
      value == '-0.00')
    _fail();
  return BigInt.parse(value.replaceAll('.', ''));
}

int _keyOrder(String a, String b) {
  final x = a.runes.toList(), y = b.runes.toList();
  for (var i = 0; i < x.length && i < y.length; i++) {
    if (x[i] != y[i]) return x[i].compareTo(y[i]);
  }
  return x.length.compareTo(y.length);
}

dynamic _ordered(dynamic value) {
  if (value is Map) {
    final map = _map(value), keys = map.keys.toList()..sort(_keyOrder);
    return {for (final key in keys) key: _ordered(map[key])};
  }
  if (value is List) return value.map(_ordered).toList();
  if (value is num) _integer(value, -9007199254740991);
  if (value != null && value is! String && value is! bool && value is! int)
    _fail();
  return value;
}

String bankCamtCanonical(dynamic value) => jsonEncode(_ordered(value));
bool _same(dynamic a, dynamic b) =>
    bankCamtCanonical(a) == bankCamtCanonical(b);

Map<String, dynamic> bankCamtMetadata(dynamic raw) {
  final meta = _shape(
    raw,
    'contract account bank statement_reference period_from period_to opening_balance closing_balance filename delimiter file_sha256 rows complete_statement_confirmed distinct_transaction_confirmations camt',
  );
  if (meta['contract'] != camtContract ||
      meta['delimiter'] != camtFormat ||
      !_hash.hasMatch('${meta['file_sha256']}') ||
      meta['complete_statement_confirmed'] != true ||
      meta['rows'] is! List ||
      (meta['rows'] as List).length > 10000)
    _fail();
  final proof = _shape(
    meta['camt'],
    'schema_sha256 namespace file_sha256 message_id original_period_from original_period_to entry_sources',
  );
  final rows = meta['rows'] as List;
  if (proof['schema_sha256'] != camtSchema ||
      proof['namespace'] != _namespace ||
      proof['file_sha256'] != meta['file_sha256'] ||
      proof['entry_sources'] is! List ||
      (proof['entry_sources'] as List).length != rows.length)
    _fail();
  _text(proof['message_id'], 35);
  _text(meta['statement_reference'], 35);
  final stamp = RegExp(
    r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?(?:Z|[+-]\d{2}:\d{2})?$',
  );
  if (proof['original_period_from'] is! String ||
      proof['original_period_to'] is! String ||
      !stamp.hasMatch(proof['original_period_from']) ||
      !stamp.hasMatch(proof['original_period_to']) ||
      !RegExp(r'^\d{4}-\d{2}-\d{2}T00:00:00(?:\.0+)?(?:Z|[+-]\d{2}:\d{2})?$')
          .hasMatch(proof['original_period_from']))
    _fail();
  final first = proof['original_period_from'] as String,
      last = proof['original_period_to'] as String;
  var end = _day(last.substring(0, 10));
  if (last.substring(11, 19) == '00:00:00')
    end = DateTime.parse('${end}T00:00:00Z')
        .subtract(const Duration(days: 1))
        .toIso8601String()
        .substring(0, 10);
  else if (last.substring(11, 19) != '23:59:59')
    _fail();
  if (_day(meta['period_from']) != _day(first.substring(0, 10)) ||
      _day(meta['period_to']) != end ||
      (meta['period_from'] as String).compareTo(meta['period_to']) > 0)
    _fail();
  final ids = <String>{};
  var movement = BigInt.zero;
  for (var i = 0; i < rows.length; i++) {
    final row = _shape(
      rows[i],
      'line_number transaction_id booking_date value_date amount currency counterparty reference',
    );
    final source = _shape(
      proof['entry_sources'][i],
      'line_number xml_line bank_reference entry_reference transaction_details reversal',
    );
    if (row['line_number'] != i + 1 ||
        source['line_number'] != i + 1 ||
        source['reversal'] is! bool ||
        row['currency'] != 'EUR')
      _fail();
    _integer(source['xml_line'], 1, 5 * 1024 * 1024);
    _integer(source['transaction_details'], 0, 100000);
    _text(source['bank_reference'], 35);
    _text(source['entry_reference'], 35, nullable: true);
    if (row['transaction_id'] !=
            'camt08:${(source['bank_reference'] as String).trim()}' ||
        !ids.add(row['transaction_id']))
      _fail();
    if (_day(row['booking_date']).compareTo(meta['period_from']) < 0 ||
        (row['booking_date'] as String).compareTo(meta['period_to']) > 0)
      _fail();
    _day(row['value_date']);
    if (row['counterparty'] is! String ||
        (row['counterparty'] as String).runes.length > 500 ||
        row['reference'] is! String ||
        (row['reference'] as String).runes.length > 2000)
      _fail();
    final amount = _money(row['amount']);
    if (amount == BigInt.zero) _fail();
    movement += amount;
  }
  if (_money(meta['opening_balance']) + movement !=
      _money(meta['closing_balance']))
    _fail();
  final distinctions = _map(meta['distinct_transaction_confirmations']);
  for (final entry in distinctions.entries) {
    if (!ids.contains(entry.key) ||
        entry.value is! String ||
        (entry.value as String).trim().isEmpty ||
        (entry.value as String).runes.length > 1000 ||
        RegExp(r'[\x00-\x1f\x7f]').hasMatch(entry.value))
      _fail();
  }
  return meta;
}

Future<Map<String, dynamic>> bankCamtPreviewHash(dynamic raw) async {
  final preview = _map(raw);
  bankCamtMetadata(preview['metadata']);
  final content = Map<String, dynamic>.from(preview)..remove('preview_hash');
  final digest = (await Sha256().hash(utf8.encode(bankCamtCanonical(content))))
      .bytes
      .map((v) => v.toRadixString(16).padLeft(2, '0'))
      .join();
  if (digest != preview['preview_hash']) _fail();
  return preview;
}

Future<Map<String, dynamic>> bankCamtInspection(
  dynamic raw,
  Map<String, dynamic> expected,
  String sha256,
) async {
  final value = _shape(
    raw,
    'schema_version contract original_sha256 suggested_body camt preview confirmation_required financial_changes',
  );
  if (value['schema_version'] != 1 ||
      value['schema_version'] is! int ||
      value['contract'] != camtContract ||
      value['original_sha256'] != sha256 ||
      value['confirmation_required'] != true ||
      value['financial_changes'] != false)
    _fail();
  final body = _shape(
    value['suggested_body'],
    'account_id account_revision bank_revision filename delimiter statement_reference period_from period_to opening_balance closing_balance',
  );
  if ([
        'account_id',
        'account_revision',
        'bank_revision',
        'filename',
      ].any((k) => body[k] != expected[k]) ||
      body['delimiter'] != camtFormat)
    _fail();
  final meta = bankCamtMetadata(_map(value['preview'])['metadata']);
  if (meta['file_sha256'] != sha256 ||
      !_same(meta['camt'], value['camt']) ||
      _map(meta['account'])['id'] != expected['account_id'] ||
      _map(meta['account'])['revision'] != expected['account_revision'] ||
      _map(meta['bank'])['revision'] != expected['bank_revision'] ||
      body.keys
          .where(
            (k) => ![
              'account_id',
              'account_revision',
              'bank_revision',
            ].contains(k),
          )
          .any((k) => meta[k] != body[k]))
    _fail();
  await bankCamtPreviewHash(value['preview']);
  return value;
}

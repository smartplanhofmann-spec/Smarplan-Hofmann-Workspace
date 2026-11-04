import 'dart:convert';
import 'dart:typed_data';

import 'package:cryptography/dart.dart';

import 'api.dart';
import 'business_session.dart';

const openingPath = '/accounting/opening-balances';
const openingRule = 'account_opening_balances_v1';
const openingFields = [
  'expected_revision',
  'state_hash',
  'account_id',
  'account_revision',
  'profile_ref',
  'status',
  'opening_date',
  'amount',
  'source',
  'reason',
];
const _flags = [
  'schema_version',
  'rule_version',
  'cash_flow_created',
  'tax_postings_created',
  'balance_timing',
  'timezone',
];
final _id = RegExp(r'^[a-f0-9]{32}$'), _hash = RegExp(r'^[a-f0-9]{64}$');
Never _fail(String message) => throw ApiException(0, message);
dynamic _order(dynamic v) => v is List
    ? v.map(_order).toList()
    : v is Map
    ? {
        for (final k in v.keys.map((v) => '$v').toList()..sort())
          k: _order(v[k]),
      }
    : v;
bool openingSame(dynamic a, dynamic b) =>
    jsonEncode(_order(a)) == jsonEncode(_order(b));
String openingDigest(List<int> bytes) => const DartSha256()
    .hashSync(bytes)
    .bytes
    .map((v) => v.toRadixString(16).padLeft(2, '0'))
    .join();
String _sha(dynamic value) =>
    openingDigest(utf8.encode(jsonEncode(_order(value))));
void _shape(dynamic value, Iterable<String> keys) {
  if (value is! Map ||
      !openingSame(value.keys.toList()..sort(), keys.toList()..sort()))
    _fail(
      'Der Anfangsbestandsnachweis enthält unbekannte oder fehlende Felder.',
    );
}

void _identifier(dynamic value) {
  if (value is! String || !_id.hasMatch(value))
    _fail('Der Nachweis enthält keine gültige Kennung.');
}

void _digest(dynamic value) {
  if (value is! String || !_hash.hasMatch(value)) _fail('Die Prüfsumme fehlt.');
}

int _integer(dynamic value, [int min = 0]) {
  if (value is! int || value < min || value > 2147483646)
    _fail('Die Belegfassung ist ungültig.');
  return value;
}

String openingDate(dynamic value) {
  if (value is! String ||
      !RegExp(r'^\d{4}-\d{2}-\d{2}$').hasMatch(value) ||
      DateTime.tryParse(value)?.toIso8601String().substring(0, 10) != value)
    _fail('Einen gültigen Stichtag angeben.');
  return value;
}

int openingCents(dynamic value) {
  if (value is! String ||
      !RegExp(r'^-?(?:0|[1-9][0-9]{0,10})\.[0-9]{2}$').hasMatch(value) ||
      value == '-0.00')
    _fail('Ein genauer EUR-Betrag mit zwei Nachkommastellen ist erforderlich.');
  final p = value.replaceAll('-', '').split('.');
  return (value.startsWith('-') ? -1 : 1) *
      (int.parse(p[0]) * 100 + int.parse(p[1]));
}

// Aggregate balances can exceed the accepted size of a single input.
// BigInt keeps every cent exact for sums and bank boundary comparisons.
BigInt openingAggregateCents(dynamic value) {
  if (value is! String ||
      !RegExp(r'^-?(?:0|[1-9][0-9]*)\.[0-9]{2}$').hasMatch(value) ||
      value == '-0.00')
    _fail(
      'Ein genauer EUR-Gesamtbetrag mit zwei Nachkommastellen ist erforderlich.',
    );
  return BigInt.parse(value.replaceAll('.', ''));
}

String openingAmount(String value) {
  final s = value.trim().replaceAll(',', '.');
  if (!RegExp(r'^-?(?:0|[1-9][0-9]{0,10})(?:\.[0-9]{1,2})?$').hasMatch(s))
    _fail(
      'Den belegten EUR-Betrag ohne Tausendertrennzeichen und mit höchstens zwei Nachkommastellen eingeben.',
    );
  final p = s.split('.'),
      result = '${p[0]}.${(p.length == 1 ? '' : p[1]).padRight(2, '0')}';
  openingCents(result);
  return result;
}

void _text(dynamic value, [int max = 1000]) {
  if (value is! String ||
      value.trim().isEmpty ||
      value.length > max ||
      value.codeUnits.any((c) => c < 32 || c == 127))
    _fail('Ein begrenzter einzeiliger Nachweistext ist erforderlich.');
}

void _flagsCheck(Map<String, dynamic> v) {
  if (v['schema_version'] != 1 ||
      v['rule_version'] != openingRule ||
      v['cash_flow_created'] != false ||
      v['tax_postings_created'] != false)
    _fail(
      'Unbekannter Anfangsbestandsumfang oder unerwartete Geld-/Steuerbuchung.',
    );
}

Map<String, dynamic> _account(dynamic raw) {
  final v = businessMap(raw);
  _shape(v, [
    'id',
    'revision',
    'active',
    'code',
    'name',
    'kind',
    'currency',
    'created_at',
    'created_by',
  ]);
  _identifier(v['id']);
  _identifier(v['created_by']);
  _integer(v['revision'], 1);
  _text(v['code']);
  _text(v['name']);
  if (v['currency'] != 'EUR' ||
      !['bank', 'cash', 'payment_service'].contains(v['kind']) ||
      v['active'] is! bool ||
      DateTime.tryParse('${v['created_at']}') == null)
    _fail('Das Geldkonto ist nicht eindeutig belegt.');
  return v;
}

void _reference(dynamic raw, {bool profile = false}) {
  _shape(raw, ['id', 'revision', profile ? 'entry_sha256' : 'content_hash']);
  _identifier(raw['id']);
  _integer(raw['revision'], 1);
  _digest(raw[profile ? 'entry_sha256' : 'content_hash']);
}

void _profile(dynamic raw, dynamic ref) {
  _reference(ref, profile: true);
  final v = businessMap(raw), p = businessMap(v['profile']);
  if (v['id'] != ref['id'] ||
      v['revision'] != ref['revision'] ||
      _sha(v) != ref['entry_sha256'] ||
      p['legal_form'] != 'sole_proprietorship' ||
      p['accounting_method'] != 'euer')
    _fail('Das bestätigte Buchführungsprofil stimmt nicht.');
  openingDate(p['bookkeeping_start']);
}

bool openingReadable(BusinessSession s) =>
    s.projectId == null &&
    s.hasFeature('accounting_opening_balances') &&
    s.hasModule('accounting_openings') &&
    ['accounting.read', 'finance.read', 'bank.read'].every(s.can);
bool openingWritable(BusinessSession s) =>
    openingReadable(s) &&
    s.sectionEnabled('finance') &&
    [
      'accounting.admin',
      'accounting.prepare',
      'finance.write',
    ].every(s.canWrite);

Map<String, dynamic> openingOriginal(dynamic raw, String accountId) {
  final v = businessMap(raw);
  _shape(v, [
    'id',
    'account_id',
    'filename',
    'media_type',
    'size',
    'sha256',
    'created_by',
    'created_at',
    'path',
  ]);
  _identifier(v['id']);
  _identifier(v['created_by']);
  _digest(v['sha256']);
  _integer(v['size'], 1);
  _text(v['filename'], 200);
  if (v['account_id'] != accountId ||
      v['path'] != '$openingPath/originals/${v['id']}' ||
      v['size'] > 5 * 1024 * 1024 ||
      ![
        'application/pdf',
        'image/png',
        'image/jpeg',
      ].contains(v['media_type']) ||
      RegExp(r'[/\\]').hasMatch(v['filename']) ||
      DateTime.tryParse('${v['created_at']}') == null)
    _fail('Das Original gehört nicht zum gewählten Konto oder Dateiformat.');
  return v;
}

void Function(dynamic) openingOriginalReceipt(Map<String, dynamic> body) {
  final b = businessMap(jsonDecode(jsonEncode(body))),
      bytes = base64Decode(b['content_base64']);
  return (raw) {
    final v = openingOriginal(raw, b['account_id']);
    if (v['filename'] != b['filename'] ||
        v['media_type'] != b['media_type'] ||
        v['size'] != bytes.length ||
        v['sha256'] != openingDigest(bytes))
      _fail('Die Originalannahme entspricht nicht der ausgewählten Datei.');
  };
}

void openingVerifyBytes(Uint8List bytes, Map<String, dynamic> original) {
  if (bytes.length != original['size'] ||
      openingDigest(bytes) != original['sha256'])
    _fail('Das Original stimmt nicht mit dem gespeicherten Nachweis überein.');
}

void _source(Map<String, dynamic> v) {
  final s = businessMap(v['source']),
      p = businessMap(v['source_proof']),
      a = businessMap(v['account']);
  if (s['kind'] == 'original') {
    _shape(s, [
      'kind',
      'original_id',
      'sha256',
      'evidence_type',
      'at_start_of_day',
    ]);
    _shape(p, [
      'kind',
      'original',
      'evidence_type',
      'opening_date',
      'amount',
      'at_start_of_day',
      'source_path',
    ]);
    final o = openingOriginal(p['original'], v['account_id']);
    if (s['original_id'] != o['id'] ||
        s['sha256'] != o['sha256'] ||
        s['evidence_type'] !=
            (a['kind'] == 'cash' ? 'cash_count' : 'account_statement') ||
        p['evidence_type'] != s['evidence_type'] ||
        s['at_start_of_day'] != true ||
        p['at_start_of_day'] != true ||
        p['opening_date'] != v['opening_date'] ||
        p['amount'] != v['amount'] ||
        p['source_path'] != o['path'] ||
        p['kind'] != 'original')
      _fail('Original, Stichtag und Bestand widersprechen sich.');
  } else if (s['kind'] == 'bank_statement') {
    _shape(s, ['kind', 'statement_id', 'content_hash', 'balance_side']);
    _shape(p, [
      'kind',
      'statement_id',
      'content_hash',
      'file_sha256',
      'account_id',
      'balance_side',
      'period_from',
      'period_to',
      'amount',
      'statement_reference',
      'source_path',
    ]);
    _identifier(s['statement_id']);
    _digest(s['content_hash']);
    _digest(p['file_sha256']);
    openingDate(p['period_from']);
    openingDate(p['period_to']);
    _text(p['statement_reference']);
    final day = s['balance_side'] == 'opening'
        ? p['period_from']
        : DateTime.parse('${p['period_to']}T00:00:00Z')
              .add(const Duration(days: 1))
              .toIso8601String()
              .substring(0, 10);
    if (a['kind'] != 'bank' ||
        !['opening', 'closing'].contains(s['balance_side']) ||
        s.entries.any((e) => p[e.key] != e.value) ||
        p['account_id'] != v['account_id'] ||
        p['amount'] != v['amount'] ||
        day != v['opening_date'] ||
        p['source_path'] != '/bank/statements/${s['statement_id']}/original')
      _fail('Der Auszug belegt nicht genau diesen Kontobestand und Stichtag.');
  } else {
    _fail(
      'Ein unveränderter Auszug oder ein gespeichertes Original ist erforderlich.',
    );
  }
}

Map<String, dynamic> openingPreview(dynamic raw, Map<String, dynamic> body) {
  final v = businessMap(raw);
  _shape(v, [
    ...openingFields,
    ..._flags,
    'account',
    'profile',
    'source_proof',
    'previous_ref',
    'preview_hash',
  ]);
  _flagsCheck(v);
  if (v['balance_timing'] != 'start_of_day' ||
      v['timezone'] != 'Europe/Berlin' ||
      openingFields.any((key) => !openingSame(v[key], body[key])))
    _fail('Die Vorschau stimmt nicht mit den geprüften Eingaben überein.');
  _integer(v['expected_revision']);
  _digest(v['state_hash']);
  _identifier(v['account_id']);
  _integer(v['account_revision'], 1);
  openingDate(v['opening_date']);
  openingCents(v['amount']);
  _text(v['reason']);
  _profile(v['profile'], v['profile_ref']);
  final a = _account(v['account']);
  if (a['id'] != v['account_id'] ||
      a['revision'] != v['account_revision'] ||
      v['opening_date'] != v['profile']['profile']['bookkeeping_start'] ||
      !['active', 'void'].contains(v['status']) ||
      a['kind'] == 'cash' && openingCents(v['amount']) < 0)
    _fail('Konto, Buchführungsbeginn oder Bestandsart widersprechen sich.');
  if (v['previous_ref'] != null) _reference(v['previous_ref']);
  if (v['status'] == 'void' && v['previous_ref'] == null)
    _fail('Eine Aufhebung benötigt einen ursprünglichen Bestand.');
  _source(v);
  final base = Map<String, dynamic>.from(v)..remove('preview_hash');
  if (_sha(base) != v['preview_hash'])
    _fail('Die Vorschau-Prüfsumme stimmt nicht.');
  return v;
}

Map<String, dynamic> openingEvent(dynamic raw) {
  final v = businessMap(raw);
  _shape(v, [
    ...openingFields,
    ..._flags,
    'account',
    'profile',
    'source_proof',
    'previous_ref',
    'preview_hash',
    'id',
    'sequence',
    'revision',
    'previous_hash',
    'created_by',
    'created_at',
    'content_hash',
  ]);
  _identifier(v['id']);
  _identifier(v['created_by']);
  _integer(v['sequence'], 1);
  _integer(v['revision'], 1);
  if (v['previous_hash'] != null) _digest(v['previous_hash']);
  if (DateTime.tryParse('${v['created_at']}') == null)
    _fail('Der Annahmezeitpunkt fehlt.');
  final base = Map<String, dynamic>.from(v)..remove('content_hash');
  if (_sha(base) != v['content_hash'])
    _fail('Die Annahme-Prüfsumme stimmt nicht.');
  for (final k in [
    'id',
    'sequence',
    'revision',
    'previous_hash',
    'created_by',
    'created_at',
  ]) {
    base.remove(k);
  }
  openingPreview(base, {for (final k in openingFields) k: v[k]});
  if (v['sequence'] != v['expected_revision'] + 1 ||
      v['revision'] !=
          (v['previous_ref'] == null ? 1 : v['previous_ref']['revision'] + 1) ||
      v['state_hash'] !=
          _sha({
            'schema_version': 1,
            'revision': v['expected_revision'],
            'head': v['previous_hash'],
          }))
    _fail('Die Annahme passt nicht zur ursprünglichen Journalfassung.');
  return v;
}

void Function(dynamic) openingReceipt(Map<String, dynamic> preview) {
  final p = businessMap(jsonDecode(jsonEncode(preview)));
  return (raw) {
    final v = openingEvent(raw);
    if (p.keys.any((key) => !openingSame(v[key], p[key])))
      _fail('Der angenommene Bestand entspricht nicht der geprüften Vorschau.');
  };
}

Map<String, dynamic> openingState(dynamic raw) {
  final v = businessMap(raw);
  _shape(v, [
    'schema_version',
    'rule_version',
    'revision',
    'state_hash',
    'profile',
    'profile_ref',
    'accounts',
    'items',
    'can_prepare',
    'max_original_bytes',
    'liquidity_path',
    'cash_flow_created',
    'tax_postings_created',
  ]);
  _flagsCheck(v);
  _integer(v['revision']);
  _digest(v['state_hash']);
  if (v['can_prepare'] is! bool ||
      v['max_original_bytes'] != 5 * 1024 * 1024 ||
      v['liquidity_path'] != '$openingPath/liquidity')
    _fail('Die Quellenfreigabe ist unbekannt.');
  if (v['profile'] == null) {
    if (v['profile_ref'] != null || v['can_prepare'] != false)
      _fail('Ohne datiertes Profil ist keine Bestätigung möglich.');
  } else {
    _profile(v['profile'], v['profile_ref']);
  }
  final accounts = businessItems(v['accounts']).map(_account).toList(),
      ids = accounts.map((a) => a['id']).toSet();
  if (ids.length != accounts.length) _fail('Geldkonto mehrfach enthalten.');
  final seen = <String>{};
  Map<String, dynamic>? last;
  for (final item in businessItems(v['items'])) {
    final e = openingEvent(item);
    if (!ids.contains(e['account_id']) ||
        !seen.add(e['account_id']) ||
        e['sequence'] > v['revision'])
      _fail('Der aktuelle Bestand ist nicht eindeutig.');
    if (last == null || e['sequence'] > last['sequence']) last = e;
  }
  if ((last?['sequence'] ?? 0) != v['revision'] ||
      v['state_hash'] !=
          _sha({
            'schema_version': 1,
            'revision': v['revision'],
            'head': last?['content_hash'],
          }))
    _fail('Der Quellenstand passt nicht zum Journal.');
  return v;
}

Map<String, dynamic> openingSources(
  dynamic raw,
  Map<String, dynamic> state,
  String accountId,
) {
  final v = businessMap(raw);
  _shape(v, [
    'schema_version',
    'account',
    'profile_ref',
    'opening_date',
    'bank_statements',
    'originals',
    'original_evidence_type',
  ]);
  final a = _account(v['account']);
  if (v['schema_version'] != 1 ||
      a['id'] != accountId ||
      !businessItems(state['accounts']).any((e) => openingSame(e, a)) ||
      !openingSame(v['profile_ref'], state['profile_ref']) ||
      v['opening_date'] != state['profile']?['profile']?['bookkeeping_start'] ||
      v['original_evidence_type'] !=
          (a['kind'] == 'cash' ? 'cash_count' : 'account_statement'))
    _fail('Die Quellen gehören nicht zum aktuellen Konto und Profil.');
  for (final o in businessItems(v['originals'])) {
    openingOriginal(o, accountId);
  }
  for (final b in businessItems(v['bank_statements'])) {
    _shape(b, [
      'source',
      'amount',
      'statement_reference',
      'period_from',
      'period_to',
    ]);
    _shape(b['source'], [
      'kind',
      'statement_id',
      'content_hash',
      'balance_side',
    ]);
    _identifier(b['source']['statement_id']);
    _digest(b['source']['content_hash']);
    openingCents(b['amount']);
    openingDate(b['period_from']);
    openingDate(b['period_to']);
    _text(b['statement_reference']);
    final side = b['source']['balance_side'],
        day = side == 'opening'
            ? b['period_from']
            : DateTime.parse('${b['period_to']}T00:00:00Z')
                  .add(const Duration(days: 1))
                  .toIso8601String()
                  .substring(0, 10);
    if (a['kind'] != 'bank' ||
        b['source']['kind'] != 'bank_statement' ||
        !['opening', 'closing'].contains(side) ||
        day != v['opening_date'])
      _fail('Der Bankauszug belegt einen anderen Stichtag.');
  }
  return v;
}

Map<String, dynamic> openingHistory(dynamic raw, String accountId) {
  final v = businessMap(raw);
  _shape(v, ['schema_version', 'account_id', 'items']);
  if (v['schema_version'] != 1 || v['account_id'] != accountId)
    _fail('Die Historie gehört zu einem anderen Geldkonto.');
  Map<String, dynamic>? old;
  for (final item in businessItems(v['items'])) {
    final e = openingEvent(item);
    if (e['account_id'] != accountId ||
        e['revision'] != (old == null ? 1 : old['revision'] + 1) ||
        !openingSame(
          e['previous_ref'],
          old == null
              ? null
              : {
                  for (final k in ['id', 'revision', 'content_hash']) k: old[k],
                },
        ))
      _fail('Die Kontohistorie ist nicht lückenlos.');
    old = e;
  }
  return v;
}

Map<String, dynamic> openingLiquidity(dynamic raw, String asOf) {
  final v = businessMap(raw);
  _shape(v, [
    ..._flags,
    'as_of',
    'currency',
    'scope',
    'revision',
    'state_hash',
    'accounts',
    'unresolved_cash_sources',
    'issues',
    'complete_for_recorded_accounts',
    'known_balance_sum',
    'known_account_count',
    'account_count',
    'balance_total',
    'euer_result_unchanged',
  ]);
  _flagsCheck(v);
  openingDate(v['as_of']);
  _integer(v['revision']);
  _digest(v['state_hash']);
  if (v['as_of'] != asOf ||
      v['currency'] != 'EUR' ||
      v['scope'] != 'recorded_movements' ||
      v['balance_timing'] != 'start_of_day' ||
      v['timezone'] != 'Europe/Berlin' ||
      v['euer_result_unchanged'] != true ||
      v['complete_for_recorded_accounts'] is! bool)
    _fail('Unbekannter Liquiditätsumfang oder falscher Stichtag.');
  final issues = businessItems(v['issues']),
      unresolved = businessItems(v['unresolved_cash_sources']),
      accounts = businessItems(v['accounts']);
  var known = BigInt.zero;
  var knownCount = 0;
  bool complete = accounts.isNotEmpty && issues.isEmpty && unresolved.isEmpty;
  final ids = <String>{};
  for (final row in accounts) {
    _shape(row, [
      'account',
      'opening_ref',
      'opening_date',
      'opening_balance',
      'inflows',
      'outflows',
      'calculated_balance',
      'balance',
      'movements',
      'bank_connections',
      'issues',
    ]);
    final a = _account(row['account']);
    if (!ids.add(a['id'])) _fail('Liquiditätskonto doppelt enthalten.');
    if (row['opening_ref'] != null) _reference(row['opening_ref']);
    if (row['opening_date'] != null) openingDate(row['opening_date']);
    final inflows = openingAggregateCents(row['inflows']),
        outflows = openingAggregateCents(row['outflows']);
    if (inflows < BigInt.zero || outflows < BigInt.zero)
      _fail('Geldflussrichtung und Betrag widersprechen sich.');
    var incoming = BigInt.zero, outgoing = BigInt.zero;
    for (final m in businessItems(row['movements'])) {
      if (m['account']?['id'] != a['id'] ||
          !['in', 'out'].contains(m['direction']) ||
          openingDate(m['date']).compareTo(asOf) > 0 ||
          row['opening_date'] == null ||
          m['date'].compareTo(row['opening_date']) < 0)
        _fail('Geldfluss gehört nicht zum Konto und Stichtag.');
      final amount = BigInt.from(openingCents(m['amount']));
      if (amount < BigInt.zero) _fail('Negativer Bewegungsbetrag.');
      if (m['direction'] == 'in') {
        incoming += amount;
      } else {
        outgoing += amount;
      }
    }
    if (incoming != inflows || outgoing != outflows)
      _fail('Die Bewegungssummen stimmen nicht.');
    final gaps = businessItems(row['issues']);
    final boundaries = <String>{};
    for (final check in businessItems(row['bank_connections'])) {
      _shape(check, [
        'statement_id',
        'content_hash',
        'balance_side',
        'date',
        'recorded_balance',
        'statement_balance',
        'matches',
      ]);
      _identifier(check['statement_id']);
      _digest(check['content_hash']);
      final date = openingDate(check['date']), side = check['balance_side'];
      final start = row['opening_date'];
      final previousClosing =
          side == 'closing' &&
          DateTime.parse('${date}T00:00:00Z')
                  .add(const Duration(days: 1))
                  .toIso8601String()
                  .substring(0, 10) ==
              start;
      if (a['kind'] != 'bank' ||
          start == null ||
          start.compareTo(asOf) > 0 ||
          !['opening', 'closing'].contains(side) ||
          !(date.compareTo(start) >= 0 && date.compareTo(asOf) <= 0 ||
              previousClosing) ||
          !boundaries.add('${check['statement_id']}:$side'))
        _fail('Der Bankanschluss gehört nicht zur belegten Bestandszeitachse.');
      final delta = businessItems(row['movements'])
          .where(
            (movement) =>
                movement['date'].compareTo(date) < 0 ||
                side == 'closing' && movement['date'] == date,
          )
          .fold<BigInt>(
            BigInt.zero,
            (sum, movement) =>
                sum +
                BigInt.from(openingCents(movement['amount'])) *
                    (movement['direction'] == 'in' ? BigInt.one : -BigInt.one),
          );
      if (openingAggregateCents(check['recorded_balance']) !=
              BigInt.from(openingCents(row['opening_balance'])) + delta ||
          check['matches'] is! bool ||
          (openingAggregateCents(check['recorded_balance']) ==
                  BigInt.from(openingCents(check['statement_balance']))) !=
              check['matches'])
        _fail('Bankanschlussprüfung widersprüchlich.');
      if (check['matches'] == false &&
          !gaps.any(
            (issue) =>
                issue['code'] == 'bank_statement_connection_mismatch' &&
                issue['statement_id'] == check['statement_id'] &&
                issue['balance_side'] == side &&
                issue['date'] == date,
          ))
        _fail('Ein widersprüchlicher Bankanschluss muss ungeklärt bleiben.');
    }
    final canCalculate =
        row['opening_date'] != null && row['opening_date'].compareTo(asOf) <= 0;
    if (canCalculate) {
      final amount =
          BigInt.from(openingCents(row['opening_balance'])) +
          inflows -
          outflows;
      if (openingAggregateCents(row['calculated_balance']) != amount)
        _fail('Anfangsbestand und Bewegungen ergeben einen anderen Saldo.');
      if (a['kind'] == 'cash' &&
          amount < BigInt.zero &&
          !gaps.any((issue) => issue['code'] == 'cash_balance_negative'))
        _fail(
          'Ein negativer Kassenbestand muss ausdrücklich ungeklärt bleiben.',
        );
    } else if (row['calculated_balance'] != null) {
      _fail('Ohne Anfangsbestand ist der Saldo unbekannt.');
    }
    if (gaps.isNotEmpty || !canCalculate) {
      if (row['balance'] != null)
        _fail('Ungeklärter Bestand darf keinen bestätigten Saldo zeigen.');
      complete = false;
    } else {
      if (row['balance'] != row['calculated_balance'])
        _fail('Bestätigter Saldo widersprüchlich.');
      known += openingAggregateCents(row['balance']);
      knownCount++;
    }
  }
  if (v['complete_for_recorded_accounts'] != complete ||
      _integer(v['known_account_count']) != knownCount ||
      _integer(v['account_count']) != accounts.length ||
      (knownCount == 0
          ? v['known_balance_sum'] != null
          : openingAggregateCents(v['known_balance_sum']) != known) ||
      complete &&
          (v['balance_total'] == null ||
              openingAggregateCents(v['balance_total']) != known) ||
      !complete && v['balance_total'] != null)
    _fail('Unvollständige Geldkonten dürfen keinen Gesamtbestand vortäuschen.');
  return v;
}

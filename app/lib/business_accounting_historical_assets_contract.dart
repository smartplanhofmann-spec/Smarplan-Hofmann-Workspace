import 'dart:convert';
import 'dart:typed_data';

import 'api.dart';
import 'business_accounting_openings_contract.dart';
import 'business_session.dart';

const historicalAssetPath = '/accounting/historical-assets';
const historicalAssetRule = 'de_historical_linear_assets_v1';
const historicalAssetInput = [
  'expected_revision',
  'state_hash',
  'asset_key',
  'profile_ref',
  'status',
  'opening_date',
  'asset',
  'source',
  'reason',
];
const historicalAssetFields = [
  'inventory_number',
  'description',
  'asset_kind',
  'business_use',
  'method',
  'rounding',
  'acquired_on',
  'use_start',
  'life_months',
  'acquisition_gross',
  'deductible_input_tax',
  'cost_basis',
  'depreciation_before_start_year',
  'depreciation_in_start_year',
  'opening_book_value',
  'account',
  'unchanged_linear_history_confirmed',
];
const historicalAssetRounding = {
  'cumulative_months_half_up':
      'Kumulierte Monatsanteile an Jahresgrenzen auf Cent gerundet',
  'annual_half_up': 'Ursprünglicher Jahres-/Teiljahresanteil auf Cent gerundet',
  'monthly_half_up': 'Jeder ursprüngliche Monatsanteil auf Cent gerundet',
};
const _flags = [
  'schema_version',
  'rule_version',
  'cash_flow_created',
  'tax_postings_created',
  'acquisition_created',
  'euer_postings_created',
  'balance_timing',
  'timezone',
];
const _previewExtra = [
  'profile',
  'source_proof',
  'previous_ref',
  'original_schedule',
  'start_year',
  'preview_hash',
];
const _eventExtra = [
  'id',
  'sequence',
  'revision',
  'previous_hash',
  'created_by',
  'created_at',
  'content_hash',
];
Never _fail(String message) => throw ApiException(0, message);
dynamic _ordered(dynamic v) => v is List
    ? v.map(_ordered).toList()
    : v is Map
    ? {
        for (final k in v.keys.map((e) => '$e').toList()..sort())
          k: _ordered(v[k]),
      }
    : v;
String historicalAssetHash(dynamic value) =>
    openingDigest(utf8.encode(jsonEncode(_ordered(value))));
void _shape(dynamic value, Iterable<String> fields) {
  if (value is! Map ||
      !openingSame(value.keys.toList()..sort(), fields.toList()..sort()))
    _fail('Unbekannte oder fehlende Felder im historischen Anlagenvertrag.');
}

void _id(dynamic v) {
  if (v is! String || !RegExp(r'^[a-f0-9]{32}$').hasMatch(v))
    _fail('Ungültige ursprüngliche Anlagenkennung.');
}

void _hash(dynamic v) {
  if (v is! String || !RegExp(r'^[a-f0-9]{64}$').hasMatch(v))
    _fail('Die ursprüngliche Prüfsumme fehlt.');
}

int _integer(dynamic v, [int min = 0]) {
  if (v is! int || v < min || v > 2147483646)
    _fail('Ungültige ganzzahlige Anlagenfassung.');
  return v;
}

String historicalAssetText(dynamic v, String label, [int max = 1000]) {
  if (v is! String ||
      v.trim().isEmpty ||
      v.length > max ||
      v.codeUnits.any((c) => c < 32 || c == 127))
    _fail('$label als begrenzten einzeiligen Text angeben.');
  return v;
}

String historicalAssetAccount(dynamic value) {
  if (value is! String || !RegExp(r'^[0-9]{4}$').hasMatch(value))
    _fail('Geprüfte vierstellige SKR04-Zuordnung eingeben.');
  return value;
}

String historicalAssetAmount(String input) {
  final v = openingAmount(input);
  if (openingCents(v) < 0)
    _fail('Belegte nichtnegative Anlagenwerte eingeben.');
  return v;
}

String historicalAssetHistoryPath(String key) {
  final encoded = utf8
      .encode(key)
      .map(
        (b) => RegExp(r'^[A-Za-z0-9_.~-]$').hasMatch(String.fromCharCode(b))
            ? String.fromCharCode(b)
            : '%${b.toRadixString(16).padLeft(2, '0').toUpperCase()}',
      )
      .join();
  return '$historicalAssetPath/history?asset_key=$encoded';
}

String _money(BigInt value) =>
    '${value ~/ BigInt.from(100)}.${(value % BigInt.from(100)).toString().padLeft(2, '0')}';
BigInt _amount(dynamic v) {
  final n = openingCents(v);
  if (n < 0) _fail('Negative historische Anlagenwerte sind unzulässig.');
  return BigInt.from(n);
}

BigInt _rounded(BigInt numerator, int denominator) =>
    (numerator * BigInt.two + BigInt.from(denominator)) ~/
    BigInt.from(denominator * 2);
void _reference(dynamic raw, {bool profile = false}) {
  _shape(raw, ['id', 'revision', profile ? 'entry_sha256' : 'content_hash']);
  _id(raw['id']);
  _integer(raw['revision'], 1);
  _hash(raw[profile ? 'entry_sha256' : 'content_hash']);
}

void _profile(dynamic raw, dynamic reference) {
  _reference(reference, profile: true);
  final p = businessMap(raw), facts = businessMap(p['profile']);
  if (p['id'] != reference['id'] ||
      p['revision'] != reference['revision'] ||
      historicalAssetHash(p) != reference['entry_sha256'] ||
      facts['legal_form'] != 'sole_proprietorship' ||
      facts['accounting_method'] != 'euer')
    _fail('Die ursprüngliche Buchführungsprofilfassung stimmt nicht.');
  openingDate(facts['bookkeeping_start']);
}

void _scope(Map<String, dynamic> v) {
  if (v['schema_version'] != 1 ||
      v['rule_version'] != historicalAssetRule ||
      v['balance_timing'] != 'start_of_day' ||
      v['timezone'] != 'Europe/Berlin' ||
      [
        'cash_flow_created',
        'tax_postings_created',
        'acquisition_created',
        'euer_postings_created',
      ].any((k) => v[k] != false))
    _fail(
      'Unbekannter Anlagenumfang oder unerwartete Zahlung/Steuer-/Aufwandsbuchung.',
    );
}

bool historicalAssetsReadable(BusinessSession s) =>
    s.projectId == null &&
    s.hasFeature('accounting_historical_assets') &&
    s.hasModule('accounting_asset_openings') &&
    ['accounting.read', 'finance.read'].every(s.can);
bool historicalAssetsWritable(BusinessSession s) =>
    historicalAssetsReadable(s) &&
    s.sectionEnabled('finance') &&
    [
      'accounting.admin',
      'accounting.prepare',
      'finance.write',
    ].every(s.canWrite);
Map<String, dynamic> historicalAssetIdentity(dynamic raw, String input) {
  final v = businessMap(raw);
  _shape(v, ['schema_version', 'inventory_number', 'asset_key']);
  historicalAssetText(input, 'Inventarnummer', 100);
  historicalAssetText(v['asset_key'], 'Bestätigte Inventarkennung', 100);
  if (v['schema_version'] != 1 || v['inventory_number'] != input)
    _fail(
      'Die serverseitige Inventaridentität gehört nicht zur eingegebenen Inventarnummer.',
    );
  return v;
}

Map<String, dynamic> historicalAssetData(dynamic raw, String openingDateValue) {
  final v = businessMap(raw);
  _shape(v, historicalAssetFields);
  historicalAssetText(v['inventory_number'], 'Inventarnummer', 100);
  historicalAssetText(v['description'], 'Anlagenbezeichnung', 300);
  historicalAssetAccount(v['account']);
  final acquired = openingDate(v['acquired_on']),
      started = openingDate(v['use_start']),
      cutover = openingDate(openingDateValue),
      life = _integer(v['life_months']);
  if (v['asset_kind'] != 'movable' ||
      v['business_use'] != 'exclusive_business' ||
      v['method'] != 'linear' ||
      !historicalAssetRounding.containsKey(v['rounding']) ||
      v['unchanged_linear_history_confirmed'] != true ||
      life < 12 ||
      life > 1200 ||
      life % 12 != 0 ||
      acquired.compareTo('1900-01-01') < 0 ||
      cutover.compareTo('2200-12-31') > 0 ||
      acquired.compareTo(started) > 0 ||
      started.compareTo(cutover) >= 0 ||
      acquired.substring(0, 7) != started.substring(0, 7))
    _fail(
      'Nur belegte unverändert lineare bewegliche, vollständig betriebliche Altanlagen mit ursprünglichem Anschaffungsmonat werden unterstützt.',
    );
  final gross = _amount(v['acquisition_gross']),
      tax = _amount(v['deductible_input_tax']),
      basis = _amount(v['cost_basis']),
      past = _amount(v['depreciation_before_start_year']),
      current = _amount(v['depreciation_in_start_year']),
      book = _amount(v['opening_book_value']);
  if (gross <= BigInt.zero ||
      basis <= BigInt.zero ||
      gross - tax != basis ||
      past + current + book != basis)
    _fail(
      'Ursprüngliche Kostenbasis, Vorsteuer, bisherige AfA und Restbuchwert stimmen nicht centgenau überein.',
    );
  final schedule = historicalAssetSchedule(v),
      year = int.parse(cutover.substring(0, 4));
  final expectedPast = schedule
      .where((r) => r['year'] < year)
      .fold<BigInt>(BigInt.zero, (a, r) => a + _amount(r['amount']));
  final quota = _amount(
    schedule.where((r) => r['year'] == year).firstOrNull?['amount'] ?? '0.00',
  );
  if (past != expectedPast ||
      current > quota ||
      cutover.endsWith('-01-01') && current != BigInt.zero)
    _fail(
      'Belegte Vorjahres-AfA oder bereits gebuchte Startjahres-AfA passt nicht zum bestätigten Altverfahren.',
    );
  return v;
}

List<Map<String, dynamic>> historicalAssetSchedule(Map<String, dynamic> asset) {
  final start = DateTime.parse('${asset['use_start']}T00:00:00Z'),
      life = asset['life_months'] as int,
      basis = _amount(asset['cost_basis']);
  final lastYear = (start.year * 12 + start.month - 1 + life - 1) ~/ 12;
  var used = BigInt.zero;
  final result = <Map<String, dynamic>>[];
  for (var year = start.year; year <= lastYear; year++) {
    final before = ((year - start.year) * 12 + 1 - start.month).clamp(0, life),
        after = ((year - start.year) * 12 + 13 - start.month).clamp(0, life);
    BigInt amount;
    switch (asset['rounding']) {
      case 'cumulative_months_half_up':
        amount =
            _rounded(basis * BigInt.from(after), life) -
            _rounded(basis * BigInt.from(before), life);
      case 'annual_half_up':
        amount = _rounded(basis * BigInt.from(after - before), life);
      case 'monthly_half_up':
        amount = _rounded(basis, life) * BigInt.from(after - before);
      default:
        _fail(
          'Das tatsächliche historische Rundungsverfahren ausdrücklich auswählen.',
        );
    }
    if (year == lastYear || amount > basis - used) amount = basis - used;
    result.add({
      'year': year,
      'months': after - before,
      'amount': _money(amount),
      'opening_book_value': _money(basis - used),
      'closing_book_value': _money(basis - used - amount),
    });
    used += amount;
  }
  return result;
}

Map<String, dynamic> historicalAssetContinuation(
  Map<String, dynamic> asset,
  String opening,
  int year,
) {
  final startYear = int.parse(opening.substring(0, 4));
  if (year < startYear || year > 2200)
    _fail('AfA-Jahr ab dem belegten Übernahmejahr bis 2200 wählen.');
  var remaining = _amount(asset['opening_book_value']);
  final rows = <Map<String, dynamic>>[];
  for (final row in historicalAssetSchedule(asset)) {
    if (row['year'] < startYear) continue;
    final imported = row['year'] == startYear
            ? _amount(asset['depreciation_in_start_year'])
            : BigInt.zero,
        amount = _amount(row['amount']) - imported;
    if (amount < BigInt.zero || amount > remaining)
      _fail('Die Folge-AfA überschreitet den belegten Restbuchwert.');
    rows.add({
      'year': row['year'],
      'months': row['months'],
      'original_annual_depreciation': row['amount'],
      'imported_current_year_depreciation': _money(imported),
      'amount': _money(amount),
      'opening_book_value': _money(remaining),
      'closing_book_value': _money(remaining - amount),
    });
    remaining -= amount;
  }
  return {
    ...(rows.where((r) => r['year'] == year).firstOrNull ??
        {
          'year': year,
          'months': 0,
          'original_annual_depreciation': '0.00',
          'imported_current_year_depreciation': '0.00',
          'amount': '0.00',
          'opening_book_value': '0.00',
          'closing_book_value': '0.00',
        }),
    'rule_version': historicalAssetRule,
    'prior_required_years': [
      for (final r in rows)
        if (r['year'] < year && _amount(r['amount']) > BigInt.zero) r['year'],
    ],
  };
}

Map<String, dynamic> historicalAssetOriginal(dynamic raw, String key) {
  final v = businessMap(raw);
  _shape(v, [
    'id',
    'asset_key',
    'filename',
    'media_type',
    'size',
    'sha256',
    'created_by',
    'created_at',
    'path',
  ]);
  _id(v['id']);
  _id(v['created_by']);
  _hash(v['sha256']);
  _integer(v['size'], 1);
  historicalAssetText(v['filename'], 'Originaldateiname', 200);
  if (v['asset_key'] != key ||
      v['path'] != '$historicalAssetPath/originals/${v['id']}' ||
      v['size'] > 5 * 1024 * 1024 ||
      ![
        'application/pdf',
        'image/png',
        'image/jpeg',
      ].contains(v['media_type']) ||
      RegExp(r'[/\\]').hasMatch(v['filename']) ||
      DateTime.tryParse('${v['created_at']}') == null)
    _fail(
      'Das unveränderte Original gehört nicht zur gewählten Inventaridentität.',
    );
  return v;
}

void Function(dynamic) historicalAssetOriginalReceipt(
  Map<String, dynamic> values,
) {
  final b = businessMap(jsonDecode(jsonEncode(values))),
      bytes = base64Decode(values['content_base64']);
  return (raw) {
    final v = historicalAssetOriginal(raw, b['asset_key']);
    if (v['filename'] != b['filename'] ||
        v['media_type'] != b['media_type'] ||
        v['size'] != bytes.length ||
        v['sha256'] != openingDigest(bytes))
      _fail(
        'Die Originalquittung entspricht nicht exakt der ausgewählten Datei.',
      );
  };
}

void historicalAssetVerifyBytes(
  Uint8List bytes,
  Map<String, dynamic> original,
) => openingVerifyBytes(bytes, original);
void _source(Map<String, dynamic> v) {
  final s = businessMap(v['source']), p = businessMap(v['source_proof']);
  _shape(s, ['original_id', 'sha256', 'position', 'history_through']);
  _shape(p, [
    'original',
    'position',
    'position_key',
    'history_through',
    'source_path',
  ]);
  final o = historicalAssetOriginal(p['original'], v['asset_key']);
  historicalAssetText(s['position'], 'Originalposition', 300);
  historicalAssetText(p['position_key'], 'Geprüfte Originalposition', 300);
  final before = DateTime.parse('${v['opening_date']}T00:00:00Z')
      .subtract(const Duration(days: 1))
      .toIso8601String()
      .substring(0, 10);
  if (s['original_id'] != o['id'] ||
      s['sha256'] != o['sha256'] ||
      p['source_path'] != o['path'] ||
      p['position'] != s['position'] ||
      s['history_through'] != before ||
      p['history_through'] != before)
    _fail(
      'Original, Position und Historie bis vor dem Übernahmestichtag widersprechen sich.',
    );
}

Map<String, dynamic> historicalAssetPreview(
  dynamic raw,
  Map<String, dynamic> body,
) {
  final v = businessMap(raw);
  _shape(v, [...historicalAssetInput, ..._flags, ..._previewExtra]);
  _scope(v);
  _integer(v['expected_revision']);
  _hash(v['state_hash']);
  _hash(v['preview_hash']);
  historicalAssetText(v['asset_key'], 'Inventaridentität', 100);
  historicalAssetText(v['reason'], 'Prüfgrund');
  if (historicalAssetInput.any((k) => !openingSame(v[k], body[k])) ||
      !['active', 'void'].contains(v['status']))
    _fail(
      'Die Anlagenvorschau gehört nicht exakt zu den eingegebenen Vortragswerten.',
    );
  _profile(v['profile'], v['profile_ref']);
  if (v['opening_date'] != v['profile']['profile']['bookkeeping_start'])
    _fail('Die Übernahme muss zum bestätigten Buchführungsbeginn erfolgen.');
  final asset = historicalAssetData(v['asset'], v['opening_date']);
  _source(v);
  if (v['previous_ref'] != null) _reference(v['previous_ref']);
  if (!openingSame(v['original_schedule'], historicalAssetSchedule(asset)) ||
      !openingSame(
        v['start_year'],
        historicalAssetContinuation(
          asset,
          v['opening_date'],
          int.parse(v['opening_date'].substring(0, 4)),
        ),
      ))
    _fail(
      'Der ursprüngliche Plan oder die verbleibende Jahres-AfA stimmt nicht.',
    );
  if (historicalAssetHash({...v}..remove('preview_hash')) != v['preview_hash'])
    _fail('Die Anlagenvorschau-Prüfsumme stimmt nicht.');
  return v;
}

Map<String, dynamic> historicalAssetEvent(dynamic raw) {
  final v = businessMap(raw);
  _shape(v, [
    ...historicalAssetInput,
    ..._flags,
    ..._previewExtra,
    ..._eventExtra,
  ]);
  _id(v['id']);
  _id(v['created_by']);
  _integer(v['sequence'], 1);
  _integer(v['revision'], 1);
  if (v['previous_hash'] != null) _hash(v['previous_hash']);
  if (DateTime.tryParse('${v['created_at']}') == null ||
      historicalAssetHash({...v}..remove('content_hash')) != v['content_hash'])
    _fail('Die unveränderliche Anlagenquittung besteht die Hashprüfung nicht.');
  final p = {...v};
  for (final key in _eventExtra) p.remove(key);
  historicalAssetPreview(p, {
    for (final key in historicalAssetInput) key: v[key],
  });
  if (v['sequence'] != v['expected_revision'] + 1 ||
      v['revision'] !=
          (v['previous_ref'] == null ? 1 : v['previous_ref']['revision'] + 1) ||
      v['state_hash'] !=
          historicalAssetHash({
            'schema_version': 1,
            'revision': v['expected_revision'],
            'head': v['previous_hash'],
          }))
    _fail(
      'Die Quittung passt nicht zur ursprünglichen globalen Anlagenfassung.',
    );
  return v;
}

void Function(dynamic) historicalAssetReceipt(Map<String, dynamic> preview) {
  final p = businessMap(jsonDecode(jsonEncode(preview)));
  return (raw) {
    final v = historicalAssetEvent(raw);
    if (p.keys.any((k) => !openingSame(v[k], p[k])))
      _fail('Die angenommene Anlage ist nicht genau die geprüfte Vorschau.');
  };
}

Map<String, dynamic> historicalAssetState(dynamic raw) {
  final v = businessMap(raw);
  _shape(v, [
    ..._flags,
    'revision',
    'state_hash',
    'profile',
    'profile_ref',
    'items',
    'originals',
    'can_prepare',
    'max_original_bytes',
    'supported_rounding',
  ]);
  _scope(v);
  _integer(v['revision']);
  _hash(v['state_hash']);
  if (v['can_prepare'] is! bool ||
      v['max_original_bytes'] != 5 * 1024 * 1024 ||
      !openingSame(
        v['supported_rounding'],
        historicalAssetRounding.keys.toList(),
      ))
    _fail('Unbekannte Freigabe oder unterstütztes Altverfahren.');
  if (v['profile'] == null) {
    if (v['profile_ref'] != null || v['can_prepare'] != false)
      _fail('Ohne bestätigtes Profil ist keine Anlagenübernahme möglich.');
  } else {
    _profile(v['profile'], v['profile_ref']);
  }
  final keys = <String>{}, ids = <String>{};
  Map<String, dynamic>? latest;
  for (final raw in businessItems(v['items'])) {
    final entry = historicalAssetEvent(raw);
    if (!keys.add(entry['asset_key']) || entry['sequence'] > v['revision'])
      _fail('Anlagenfassung mehrfach oder außerhalb des bestätigten Standes.');
    if (latest == null || entry['sequence'] > latest['sequence'])
      latest = entry;
  }
  for (final raw in businessItems(v['originals'])) {
    final o = historicalAssetOriginal(raw, raw['asset_key']);
    if (!ids.add(o['id'])) _fail('Anlagenoriginal mehrfach enthalten.');
  }
  if ((v['revision'] == 0) != (latest == null) ||
      v['state_hash'] !=
          historicalAssetHash({
            'schema_version': 1,
            'revision': v['revision'],
            'head': latest?['content_hash'],
          }))
    _fail(
      'Der globale Quellenstand stimmt nicht zur neuesten angenommenen Fassung.',
    );
  return v;
}

Map<String, dynamic> historicalAssetHistory(dynamic raw, String key) {
  final v = businessMap(raw);
  _shape(v, ['schema_version', 'asset_key', 'items']);
  if (v['schema_version'] != 1 || v['asset_key'] != key)
    _fail('Die Historie gehört nicht zur gewählten Inventaridentität.');
  Map<String, dynamic>? previous;
  for (final raw in businessItems(v['items'])) {
    final row = historicalAssetEvent(raw);
    if (row['asset_key'] != key ||
        row['revision'] != (previous == null ? 1 : previous['revision'] + 1) ||
        !openingSame(
          row['previous_ref'],
          previous == null
              ? null
              : {
                  'id': previous['id'],
                  'revision': previous['revision'],
                  'content_hash': previous['content_hash'],
                },
        ))
      _fail('Die historische Anlagenfolge ist nicht lückenlos.');
    previous = row;
  }
  return v;
}

Map<String, dynamic> historicalAssetSource(dynamic raw) {
  final v = businessMap(raw);
  _shape(v, [
    'kind',
    'schema_version',
    'rule_version',
    'id',
    'revision',
    'entry_hash',
    'asset_key',
    'status',
    'opening_date',
    'profile_ref',
    'asset',
    'source_proof',
    'source_path',
    'source_hash',
  ]);
  _id(v['id']);
  _integer(v['revision'], 1);
  _hash(v['entry_hash']);
  _reference(v['profile_ref'], profile: true);
  historicalAssetText(v['asset_key'], 'Inventaridentität', 100);
  if (v['kind'] != 'opening_asset' ||
      v['schema_version'] != 1 ||
      v['rule_version'] != historicalAssetRule ||
      !['active', 'void'].contains(v['status']) ||
      v['source_path'] != historicalAssetHistoryPath(v['asset_key']) ||
      historicalAssetHash({...v}..remove('source_hash')) != v['source_hash'])
    _fail(
      'Die öffentliche historische Anlagenquelle ist nicht eindeutig gebunden.',
    );
  historicalAssetData(v['asset'], v['opening_date']);
  final p = businessMap(v['source_proof']);
  final o = businessMap(p['original']);
  _source({
    ...v,
    'source': {
      'original_id': o['id'],
      'sha256': o['sha256'],
      'position': p['position'],
      'history_through': p['history_through'],
    },
  });
  return v;
}

Map<String, dynamic> historicalAssetEuerPreview(
  dynamic raw,
  Map<String, dynamic> body,
) {
  final v = businessMap(raw);
  _shape(v, [
    'operation',
    'expected_revision',
    'state_hash',
    'payload',
    'reason',
    'evidence_reference',
    'profile',
    'rule_version',
    'target',
    'effect',
    'reverses',
    'postings',
    'artifact',
    'control',
    'preview_hash',
  ]);
  if (body.entries.any((e) => !openingSame(v[e.key], e.value)) ||
      historicalAssetHash({...v}..remove('preview_hash')) != v['preview_hash'])
    _fail(
      'Die historische AfA-Vorschau ist nicht an den ursprünglichen Auftrag gebunden.',
    );
  final effect = businessMap(v['effect']);
  if (effect['operation'] != 'opening_depreciation')
    _fail('Erwartet wird ausschließlich die bestätigte Folge-AfA.');
  final p = businessMap(effect['payload']),
      source = historicalAssetSource(effect['source']);
  _shape(p, ['asset_entry_id', 'source_hash', 'year', 'account']);
  historicalAssetAccount(p['account']);
  _integer(p['year']);
  final details = historicalAssetContinuation(
    source['asset'],
    source['opening_date'],
    p['year'],
  );
  final target = 'opening_depreciation:${source['id']}:${p['year']}',
      day = '${p['year']}-12-31';
  if (source['status'] != 'active' ||
      p['asset_entry_id'] != source['id'] ||
      p['source_hash'] != source['source_hash'] ||
      v['target'] != target ||
      effect['target'] != target ||
      !openingSame(effect['details'], {
        ...details,
        'date': day,
        'asset_entry_id': source['id'],
        'asset_key': source['asset_key'],
        'basis': source['asset']['cost_basis'],
      }) ||
      _amount(details['amount']) == BigInt.zero)
    _fail('Quelle, Jahresquote und Restbuchwert der Folge-AfA stimmen nicht.');
  if (v['operation'] == 'opening_depreciation' &&
      (!openingSame(v['payload'], p) ||
          v['reverses'] != null ||
          v['artifact'] != null ||
          v['control'] != null))
    _fail('Unerwartete Gegenbuchung oder Nebenwirkung in der neuen Folge-AfA.');
  final expected = [
    {
      'ledger': 'euer',
      'category': 'depreciation',
      'amount': '-${details['amount']}',
      'date': day,
      'account': p['account'],
      'source_key': target,
    },
  ];
  if (!openingSame(effect['postings'], expected) ||
      v['operation'] == 'opening_depreciation' &&
          !openingSame(v['postings'], expected))
    _fail(
      'Die AfA darf nur den belegten Jahresrest ohne Geld- oder Vorsteuerbewegung buchen.',
    );
  if (v['operation'] == 'correct') {
    final correction = businessMap(v['payload']);
    _shape(correction, ['entry_id', 'operation', 'payload']);
    _id(correction['entry_id']);
    final postings = businessItems(v['postings']);
    if (correction['entry_id'] != v['reverses'] ||
        correction['operation'] != 'opening_depreciation' ||
        !openingSame(correction['payload'], p) ||
        postings.length != 2 ||
        !openingSame(postings.last, expected.single))
      _fail(
        'Die AfA-Berichtigung ist nicht eindeutig an die ursprüngliche Quelle gebunden.',
      );
    historicalAssetAccount(postings.first['account']);
    if (!openingSame(postings.first, {
      ...expected.single,
      'amount': details['amount'],
      'account': postings.first['account'],
    }))
      _fail(
        'Die AfA-Berichtigung muss den vorherigen Jahresrest exakt gegenbuchen.',
      );
  } else if (v['operation'] != 'opening_depreciation') {
    _fail('Unerwarteter Vorgang für die historische Folge-AfA.');
  }
  return v;
}

void Function(dynamic) historicalAssetEuerReceipt(
  Map<String, dynamic> preview,
) {
  final p = businessMap(jsonDecode(jsonEncode(preview)));
  return (raw) {
    final v = businessMap(raw);
    _id(v['id']);
    _id(v['created_by']);
    _integer(v['sequence'], 1);
    if (v['sequence'] != p['expected_revision'] + 1 ||
        v['previous_hash'] != p['state_hash'] ||
        p.keys
            .where((k) => !['expected_revision', 'state_hash'].contains(k))
            .any((k) => !openingSame(v[k], p[k])) ||
        historicalAssetHash({...v}..remove('entry_hash')) != v['entry_hash'])
      _fail(
        'Die angenommene Folge-AfA entspricht nicht exakt der geprüften Originalvorschau.',
      );
  };
}

Map<String, dynamic> historicalAssetEuerEntry(dynamic raw) {
  final value = businessMap(raw);
  _shape(value, [
    'operation',
    'payload',
    'reason',
    'evidence_reference',
    'profile',
    'rule_version',
    'target',
    'effect',
    'reverses',
    'postings',
    'artifact',
    'control',
    'preview_hash',
    'id',
    'sequence',
    'previous_hash',
    'created_by',
    'created_at',
    'entry_hash',
  ]);
  _integer(value['sequence'], 1);
  _hash(value['previous_hash']);
  final preview = {...value};
  for (final key in [
    'id',
    'sequence',
    'previous_hash',
    'created_by',
    'created_at',
    'entry_hash',
  ]) {
    preview.remove(key);
  }
  preview['expected_revision'] = value['sequence'] - 1;
  preview['state_hash'] = value['previous_hash'];
  historicalAssetEuerPreview(preview, {
    for (final key in [
      'operation',
      'expected_revision',
      'state_hash',
      'payload',
      'reason',
      'evidence_reference',
    ])
      key: preview[key],
  });
  historicalAssetEuerReceipt(preview)(value);
  return value;
}

List<Map<String, dynamic>> historicalAssetReport(dynamic report) {
  if (report is! Map || report['historical_assets'] is! List)
    _fail(
      'Die aktuelle Jahresauswertung enthält keine eindeutige historische Anlagenliste.',
    );
  final rows = businessItems(report['historical_assets']), seen = <String>{};
  for (final row in rows) {
    _shape(row, [
      'entry_id',
      'entry_hash',
      'asset_key',
      'asset',
      'opening_date',
      'source',
      'continuation',
      'depreciation',
    ]);
    final source = historicalAssetSource(row['source']);
    if (!seen.add(row['entry_id']) ||
        row['entry_id'] != source['id'] ||
        row['entry_hash'] != source['entry_hash'] ||
        row['asset_key'] != source['asset_key'] ||
        row['opening_date'] != source['opening_date'] ||
        !openingSame(row['asset'], source['asset']) ||
        !openingSame(
          row['continuation'],
          historicalAssetContinuation(
            source['asset'],
            source['opening_date'],
            report['year'],
          ),
        ))
      _fail('Die Jahresprojektion widerspricht ihrer ursprünglichen Anlage.');
    if (row['depreciation'] != null) {
      final entry = historicalAssetEuerEntry(row['depreciation']);
      if (entry['effect']['source']['id'] != source['id'] ||
          entry['effect']['payload']['year'] != report['year'] ||
          !openingSame(entry['effect']['source'], source))
        _fail(
          'Die bestätigte Jahres-AfA gehört nicht zur ausgewiesenen Anlagenfassung.',
        );
    }
  }
  return rows;
}

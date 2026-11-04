import 'dart:typed_data';

import 'api.dart';
import 'business_accounting_open_items_contract.dart';
import 'business_accounting_openings_contract.dart';
import 'business_session.dart';

const yearValuesPath = '/accounting/year-values';
const yearValuesRule = 'de_euer_same_year_carryover_v1';
const yearValuesInput = [
  'expected_revision',
  'state_hash',
  'entity_key',
  'profile_ref',
  'operation',
  'payload',
  'reason',
];
const yearValuesScope =
    'Belegte gewöhnliche deutsche 19-/7-Prozent-Rechnungen bei unveränderter EÜR, Regel- und Istbesteuerung. Alte tatsächliche Zahlungstage und bereits ausgeübte Vorsteuer bleiben erhalten. Keine neue Geldbewegung und kein neuer Vorsteueranspruch. Anlagen, Lohn, Privatanteile und Methodenwechsel sind hier nicht freigegeben.';
const yearValuesBoundary =
    'Die Zeitraumdeckung beruht auf dem ausdrücklich geprüften ursprünglichen Journal. Sie beweist keine eigenständige Vollständigkeit sämtlicher externer Altdaten. Fehlende oder unbelegte Werte sind nicht null; Teilzeiträume bleiben unvollständig.';
const _flags = [
  'schema_version',
  'rule_version',
  'cash_flow_created',
  'new_input_vat_claim_created',
  'timezone',
];
const _previewFields = [
  ...yearValuesInput,
  ..._flags,
  'profile',
  'proofs',
  'resolved_sources',
  'details',
  'previous_ref',
  'preview_hash',
];
const _entryFields = [
  'id',
  'sequence',
  'revision',
  'previous_hash',
  'created_by',
  'created_at',
  'content_hash',
];
Never _bad([
  String text = 'Ursprüngliche Jahreswerte sind nicht eindeutig gebunden.',
]) => throw ApiException(0, text);
void _need(bool ok, [String? message]) {
  if (!ok)
    _bad(message ?? 'Ursprüngliche Jahreswerte sind nicht eindeutig gebunden.');
}

void _shape(dynamic v, List<String> keys) =>
    _need(v is Map && v.length == keys.length && keys.every(v.containsKey));
String _id(dynamic v) {
  _need(v is String && RegExp(r'^[a-f0-9]{32}$').hasMatch(v));
  return v;
}

String _hash(dynamic v) {
  _need(v is String && RegExp(r'^[a-f0-9]{64}$').hasMatch(v));
  return v;
}

int _int(dynamic v, [int min = 0]) {
  _need(v is int && v >= min && v <= 2147483646);
  return v;
}

String yearValuesYear(dynamic v) {
  _need(
    v is String && RegExp(r'^20[0-9]{2}$').hasMatch(v),
    'Das vierstellige ursprüngliche Startjahr ist erforderlich.',
  );
  return v;
}

BigInt yearValuesCents(dynamic v) {
  _need(
    v is String &&
        RegExp(r'^-?(0|[1-9][0-9]{0,10})\.[0-9]{2}$').hasMatch(v) &&
        v != '-0.00',
    'Exakte ursprüngliche vorzeichenbehaftete Centwerte erforderlich.',
  );
  return BigInt.parse((v as String).replaceAll('.', ''));
}

String yearValuesMoney(BigInt value) {
  final a = value.abs();
  return '${value.isNegative ? '-' : ''}${a ~/ BigInt.from(100)}.${(a % BigInt.from(100)).toString().padLeft(2, '0')}';
}

String yearValuesAmount(String text) {
  final s = text.trim();
  return s.startsWith('-')
      ? yearValuesMoney(-openItemCents(openItemAmount(s.substring(1))))
      : openItemAmount(s);
}

String yearValuesAccount(dynamic v) {
  _need(
    v is String && RegExp(r'^[0-9]{4}$').hasMatch(v),
    'Geprüftes ursprüngliches SKR04-Konto ausdrücklich eingeben.',
  );
  return v;
}

void _scope(Map v) => _need(
  v['schema_version'] == 1 &&
      v['rule_version'] == yearValuesRule &&
      v['timezone'] == 'Europe/Berlin' &&
      v['cash_flow_created'] == false &&
      v['new_input_vat_claim_created'] == false,
);
bool yearValuesReadable(BusinessSession s) =>
    s.projectId == null &&
    s.hasFeature('accounting_year_values') &&
    s.hasModule('accounting_year_openings') &&
    ['accounting.read', 'finance.read'].every(s.can);
bool yearValuesWritable(BusinessSession s) =>
    yearValuesReadable(s) &&
    s.sectionEnabled('finance') &&
    [
      'accounting.admin',
      'accounting.prepare',
      'finance.write',
    ].every(s.canWrite);
Map<String, dynamic> _ref(Map e) => {
  'id': e['id'],
  'revision': e['revision'],
  'content_hash': e['content_hash'],
};
void _reference(dynamic v, {bool profile = false}) {
  _shape(v, ['id', 'revision', profile ? 'entry_sha256' : 'content_hash']);
  _id(v['id']);
  _int(v['revision'], 1);
  _hash(v[profile ? 'entry_sha256' : 'content_hash']);
}

Map<String, dynamic> _profile(
  dynamic v,
  dynamic ref, {
  bool configured = true,
}) {
  _reference(ref, profile: true);
  _need(
    v is Map &&
        v['id'] == ref['id'] &&
        v['revision'] == ref['revision'] &&
        openItemHash(v) == ref['entry_sha256'],
  );
  final p = businessMap(v['profile']);
  if (!configured) return p;
  _need(
    p['legal_form'] == 'sole_proprietorship' &&
        p['accounting_method'] == 'euer' &&
        p['vat_regime'] == 'regular' &&
        p['vat_timing'] == 'cash',
  );
  openingDate(p['bookkeeping_start']);
  openingDate(p['vat_effective_from']);
  return p;
}

bool yearValuesConfigured(dynamic state) {
  final p = businessMap(businessMap(state)['profile']?['profile']);
  if (p['legal_form'] != 'sole_proprietorship' ||
      p['accounting_method'] != 'euer' ||
      p['vat_regime'] != 'regular' ||
      p['vat_timing'] != 'cash')
    return false;
  try {
    openingDate(p['bookkeeping_start']);
    openingDate(p['vat_effective_from']);
    return true;
  } catch (_) {
    return false;
  }
}

Map<String, dynamic> yearValuesOriginal(dynamic raw, {String? year}) {
  final v = businessMap(raw);
  if (v['path'] is String &&
      (v['path'] as String).startsWith('$openItemPath/')) {
    _need(year == null);
    return openItemOriginal(v);
  }
  _shape(v, [
    'id',
    'entity_key',
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
  yearValuesYear(v['entity_key']);
  openItemText(v['filename'], 'Originaldateiname', 200);
  _need(
    !v['filename'].contains('/') &&
        !v['filename'].contains(r'\') &&
        [
          'application/pdf',
          'image/png',
          'image/jpeg',
        ].contains(v['media_type']) &&
        _int(v['size'], 1) <= 5242880 &&
        DateTime.tryParse('${v['created_at']}') != null &&
        v['path'] == '$yearValuesPath/originals/${v['id']}' &&
        (year == null || v['entity_key'] == year),
  );
  return v;
}

Map<String, dynamic> _proof(
  dynamic ref,
  List<Map<String, dynamic>> originals, {
  String? year,
}) {
  _shape(ref, ['original_id', 'sha256']);
  _id(ref['original_id']);
  _hash(ref['sha256']);
  final found = originals
      .where(
        (o) => o['id'] == ref['original_id'] && o['sha256'] == ref['sha256'],
      )
      .firstOrNull;
  _need(found != null, 'Ein gebundenes ursprüngliches Original fehlt.');
  return yearValuesOriginal(found, year: year);
}

void _coverage(dynamic v, String opening) {
  _shape(v, ['from', 'through']);
  openingDate(v['from']);
  openingDate(v['through']);
  _need(
    (v['from'] as String).compareTo('${opening.substring(0, 4)}-01-01') >= 0 &&
        (v['from'] as String).compareTo(v['through']) <= 0 &&
        (v['through'] as String).compareTo(opening) < 0,
    'Der belegte Zeitraum muss im selben Jahr vor Softwarebeginn liegen.',
  );
}

List<Map<String, dynamic>> _controls(dynamic values) {
  _need(values is List && values.length <= 1000);
  final rows = businessItems(values), seen = <String>{};
  for (final v in rows) {
    _shape(v, ['ledger', 'category', 'account', 'amount']);
    _need(['euer', 'vat'].contains(v['ledger']));
    openItemText(v['category'], 'Kategorie');
    yearValuesAccount(v['account']);
    yearValuesCents(v['amount']);
    _need(seen.add('${v['ledger']}|${v['category']}|${v['account']}'));
  }
  rows.sort(
    (a, b) => '${a['ledger']}|${a['category']}|${a['account']}'.compareTo(
      '${b['ledger']}|${b['category']}|${b['account']}',
    ),
  );
  return rows;
}

void _attest(dynamic a) {
  _shape(a, [
    'continuous_method',
    'original_journal_complete',
    'no_unsupported_values',
  ]);
  _need(
    (a as Map).values.every((v) => v == true),
    'Unveränderte Methode, vollständiges Originaljournal und unterstützten Umfang ausdrücklich bestätigen.',
  );
}

void _details(
  dynamic d,
  String year,
  String opening,
  dynamic coverage, {
  dynamic declared,
}) {
  _shape(d, [
    'schema_version',
    'rule_version',
    'year',
    'opening_date',
    'coverage',
    'complete_prior_period',
    'historical_postings',
    'controls',
    'copied_rows',
    'economic_keys',
    'cash_flow_created',
    'new_input_vat_claim_created',
    'original_periods_preserved',
  ]);
  _need(
    d['schema_version'] == 1 &&
        d['rule_version'] == yearValuesRule &&
        d['year'] == int.parse(year) &&
        d['opening_date'] == opening &&
        openingSame(d['coverage'], coverage) &&
        d['cash_flow_created'] == false &&
        d['new_input_vat_claim_created'] == false &&
        d['original_periods_preserved'] == true,
  );
  _coverage(coverage, opening);
  final last = DateTime.parse(opening)
      .subtract(const Duration(days: 1))
      .toIso8601String()
      .substring(0, 10);
  _need(
    d['complete_prior_period'] ==
        (coverage['from'] == '$year-01-01' && coverage['through'] == last),
    'Ein Teilzeitraum darf keine vollständige Deckung vortäuschen.',
  );
  _need(
    d['historical_postings'] is List &&
        d['copied_rows'] is List &&
        d['economic_keys'] is List,
  );
  final grouped = <String, BigInt>{}, keys = <String>{};
  for (final p in businessItems(d['historical_postings'])) {
    _shape(p, [
      'ledger',
      'category',
      'account',
      'amount',
      'date',
      'economic_key',
      'original_entry_key',
      'source_ref',
    ]);
    _need(['euer', 'vat'].contains(p['ledger']));
    openItemText(p['category'], 'Kategorie');
    yearValuesAccount(p['account']);
    openingDate(p['date']);
    _need(
      (p['date'] as String).compareTo(coverage['from']) >= 0 &&
          (p['date'] as String).compareTo(coverage['through']) <= 0,
    );
    keys.add(_hash(p['economic_key']));
    _hash(p['source_ref']);
    openItemText(p['original_entry_key'], 'Ursprüngliche Buchungsidentität');
    final k = '${p['ledger']}|${p['category']}|${p['account']}';
    grouped[k] = (grouped[k] ?? BigInt.zero) + yearValuesCents(p['amount']);
  }
  final sums = [
    for (final e in grouped.entries)
      {
        'ledger': e.key.split('|')[0],
        'category': e.key.split('|')[1],
        'account': e.key.split('|')[2],
        'amount': yearValuesMoney(e.value),
      },
  ];
  _need(
    openingSame(_controls(sums), _controls(d['controls'])) &&
        (declared == null || openingSame(_controls(sums), _controls(declared))),
    'Historische Zeilen und belegte Kontrollsummen stimmen nicht überein.',
  );
  final actualKeys = keys.toList()..sort();
  _need(openingSame(actualKeys, d['economic_keys']));
  final copied = businessItems(d['copied_rows']);
  _need(
    copied.map((v) => v['economic_key']).toSet().length == copied.length &&
        openingSame(
          copied.map((v) => v['economic_key']).toList()..sort(),
          actualKeys,
        ),
  );
  for (final p in copied) {
    _hash(p['economic_key']);
    _hash(p['source_ref']);
    openingDate(p['date']);
    openItemText(p['original_entry_key'], 'Ursprüngliche Buchungsidentität');
    if (p['kind'] == 'cash_history') {
      _shape(p, [
        'kind',
        'economic_key',
        'date',
        'gross',
        'net',
        'tax',
        'original_entry_key',
        'source_ref',
      ]);
      _need(
        openItemCents(p['net']) + openItemCents(p['tax']) ==
            openItemCents(p['gross']),
      );
    } else {
      _shape(p, [
        'kind',
        'economic_key',
        'date',
        'amount',
        'deducted_on',
        'declared_period',
        'original_entry_key',
        'source_ref',
      ]);
      _need(p['kind'] == 'already_exercised_input_vat');
      openItemCents(p['amount']);
      openingDate(p['deducted_on']);
      _need(
        p['declared_period'] == (p['date'] as String).substring(0, 7) &&
            (p['deducted_on'] as String).compareTo(p['date']) >= 0 &&
            (p['deducted_on'] as String).compareTo(opening) < 0,
      );
    }
    final related = businessItems(d['historical_postings'])
        .where((v) => v['economic_key'] == p['economic_key'])
        .toList();
    _need(
      related.every(
        (v) => [
          'economic_key',
          'date',
          'original_entry_key',
          'source_ref',
        ].every((k) => v[k] == p[k]),
      ),
    );
    if (p['kind'] == 'cash_history') {
      _need(related.length == 2 || related.length == 3);
      final incoming = related.length == 3,
          sign = related.length == 3 ? BigInt.one : -BigInt.one;
      _need(
        related[0]['ledger'] == 'euer' &&
            openItemCategories.containsKey(related[0]['category']) &&
            (related[0]['category'] == 'sales') == incoming &&
            yearValuesCents(related[0]['amount']) ==
                sign * openItemCents(p['net']) &&
            related[1]['ledger'] == 'euer' &&
            related[1]['category'] ==
                (incoming ? 'vat_collected' : 'paid_input_vat') &&
            yearValuesCents(related[1]['amount']) ==
                sign * openItemCents(p['tax']),
        'Öffentliche Jahresprojektion widerspricht den kopierten ursprünglichen Zahlungscentwerten.',
      );
      if (incoming)
        _need(
          related[2]['ledger'] == 'vat' &&
              related[2]['category'] == 'output_vat' &&
              yearValuesCents(related[2]['amount']) == openItemCents(p['tax']),
        );
    } else {
      _need(
        related.length == 1 &&
            related[0]['ledger'] == 'vat' &&
            related[0]['category'] == 'input_vat' &&
            yearValuesCents(related[0]['amount']) ==
                -openItemCents(p['amount']),
        'Öffentliche Jahresprojektion verändert den bereits ausgeübten Vorsteuerbetrag.',
      );
    }
    _need(
      businessItems(d['historical_postings']).any(
        (v) => [
          'economic_key',
          'date',
          'original_entry_key',
          'source_ref',
        ].every((k) => v[k] == p[k]),
      ),
    );
  }
}

Map<String, dynamic> yearValuesPreview(
  dynamic raw,
  Map<String, dynamic> body, {
  List<Map<String, dynamic>>? openingItems,
}) {
  final v = businessMap(raw);
  _shape(v, _previewFields);
  _shape(body, yearValuesInput);
  _scope(v);
  _need(
    yearValuesInput.every((k) => openingSame(v[k], body[k])) &&
        v['operation'] == 'year_values',
    'Vorschau bestätigt nicht genau die ursprünglichen Jahresangaben.',
  );
  _int(v['expected_revision']);
  _hash(v['state_hash']);
  final year = yearValuesYear(v['entity_key']),
      profile = _profile(v['profile'], v['profile_ref']);
  _need((profile['bookkeeping_start'] as String).startsWith(year));
  openItemText(v['reason'], 'Prüfgrund', 1000);
  if (v['previous_ref'] != null) _reference(v['previous_ref']);
  final p = businessMap(v['payload']);
  _shape(p, [
    'status',
    'coverage',
    'sources',
    'controls',
    'ledger_proof',
    'attestations',
  ]);
  _need(['active', 'void'].contains(p['status']));
  _attest(p['attestations']);
  _coverage(p['coverage'], profile['bookkeeping_start']);
  _need(
    p['sources'] is List &&
        (p['sources'] as List).length <= 1000 &&
        v['resolved_sources'] is List &&
        (p['sources'] as List).length ==
            (v['resolved_sources'] as List).length &&
        v['proofs'] is List,
  );
  final proofs = businessItems(v['proofs']);
  for (final original in proofs) {
    yearValuesOriginal(original);
  }
  final journal = _proof(p['ledger_proof'], proofs, year: year);
  _need(
    proofs.first['id'] == journal['id'] &&
        proofs.skip(1).every((v) => v['sha256'] != journal['sha256']),
    'Eigenständiges Zeitraumjournal erforderlich.',
  );
  final sources = businessItems(p['sources']),
      resolved = businessItems(v['resolved_sources']);
  for (var i = 0; i < sources.length; i++) {
    final s = sources[i], r = resolved[i], record = businessMap(r['record']);
    _shape(r, [
      'kind',
      'source_ref',
      'record',
      'accounts',
      'cash_entry_keys',
      'vat_entry_key',
    ]);
    _need(
      s['kind'] == r['kind'] &&
          [
            'accounts',
            'cash_entry_keys',
            'vat_entry_key',
          ].every((k) => openingSame(s[k], r[k])),
    );
    _shape(s['accounts'], ['net', 'tax', 'input_vat']);
    for (final a in (s['accounts'] as Map).values) {
      yearValuesAccount(a);
    }
    _need(
      s['cash_entry_keys'] is List &&
          record['prior_payments'] is List &&
          (s['cash_entry_keys'] as List).length ==
              (record['prior_payments'] as List).length,
    );
    for (final k in s['cash_entry_keys']) {
      openItemText(k, 'Ursprüngliche Zahlungsbuchung');
    }
    if (record['prior_input_vat'] != null) {
      openItemText(s['vat_entry_key'], 'Ursprüngliche Vorsteuerbuchung');
    } else {
      _need(s['vat_entry_key'] == null);
    }
    final refs = [
      record['invoice_proof'],
      record['cutover_proof'],
      for (final row in businessItems(record['prior_payments'])) row['proof'],
      if (record['prior_input_vat'] != null) record['prior_input_vat']['proof'],
    ];
    if (s['kind'] == 'opening_item') {
      _shape(s, [
        'kind',
        'entry_id',
        'entry_hash',
        'accounts',
        'cash_entry_keys',
        'vat_entry_key',
      ]);
      _id(s['entry_id']);
      _need(r['source_ref'] == _hash(s['entry_hash']));
      for (final ref in refs) {
        _proof(ref, proofs);
      }
      if (openingItems != null) {
        final old = openingItems
            .where(
              (e) =>
                  e['id'] == s['entry_id'] &&
                  e['content_hash'] == s['entry_hash'],
            )
            .firstOrNull;
        _need(
          old != null && openingSame(openItemEvent(old)['payload'], record),
          'Die unveränderte kanonische Altpostenfassung stimmt nicht.',
        );
      }
    } else {
      _need(s['kind'] == 'closed_trade');
      _shape(s, [
        'kind',
        'record',
        'accounts',
        'cash_entry_keys',
        'vat_entry_key',
      ]);
      _need(openingSame(s['record'], record));
      yearValuesClosedRecord(record, profile);
      final originals = [
        for (final ref in refs) _proof(ref, proofs, year: year),
      ];
      _need(
        r['source_ref'] ==
            openItemHash({'record': record, 'proofs': originals}),
      );
    }
    _bindRows(v['details'], r, p['coverage']);
  }
  final resolvedRefs = resolved.map((r) => r['source_ref']).toSet();
  _need(
    businessItems(v['details']['copied_rows'])
            .every((r) => resolvedRefs.contains(r['source_ref'])) &&
        businessItems(v['details']['historical_postings'])
            .every((r) => resolvedRefs.contains(r['source_ref'])),
    'Eine historische Journalzeile besitzt keine gebundene ursprüngliche Quelle.',
  );
  _details(
    v['details'],
    year,
    profile['bookkeeping_start'],
    p['coverage'],
    declared: p['controls'],
  );
  final plain = openItemCopy(v)..remove('preview_hash');
  _need(
    openItemHash(plain) == _hash(v['preview_hash']),
    'Prüfsumme der ursprünglichen Jahresvorschau stimmt nicht.',
  );
  return v;
}

void _bindRows(dynamic details, Map<String, dynamic> source, dynamic coverage) {
  final record = source['record'] as Map, expected = <Map<String, dynamic>>[];
  for (var i = 0; i < (record['prior_payments'] as List).length; i++) {
    final p = record['prior_payments'][i];
    if ((p['date'] as String).compareTo(coverage['from']) < 0 ||
        (p['date'] as String).compareTo(coverage['through']) > 0)
      continue;
    expected.add({
      'kind': 'cash_history',
      'date': p['date'],
      'gross': p['gross'],
      'net': p['net'],
      'tax': p['tax'],
      'original_entry_key': source['cash_entry_keys'][i],
      'source_ref': source['source_ref'],
    });
  }
  final vat = record['prior_input_vat'];
  if (vat != null &&
      (vat['entitlement_date'] as String).compareTo(coverage['from']) >= 0 &&
      (vat['entitlement_date'] as String).compareTo(coverage['through']) <= 0) {
    expected.add({
      'kind': 'already_exercised_input_vat',
      'date': vat['entitlement_date'],
      'amount': vat['amount'],
      'deducted_on': vat['deducted_on'],
      'declared_period': vat['declared_period'],
      'original_entry_key': source['vat_entry_key'],
      'source_ref': source['source_ref'],
    });
  }
  final rows = businessItems(details['copied_rows'])
      .where((r) => r['source_ref'] == source['source_ref'])
      .toList();
  _need(
    rows.length == expected.length,
    'Übernommene historische Zeilen fehlen oder wurden ergänzt.',
  );
  for (var i = 0; i < rows.length; i++) {
    final row = rows[i], plain = openItemCopy(row)..remove('economic_key');
    _need(
      openingSame(plain, expected[i]),
      'Historische Zahlung oder ausgeübte Vorsteuer wurde von ihrem Original gelöst.',
    );
    final actual = businessItems(details['historical_postings'])
        .where((p) => p['economic_key'] == row['economic_key'])
        .toList();
    final incoming = record['direction'] == 'receivable',
        accounts = source['accounts'] as Map;
    Map<String, dynamic> post(
      String ledger,
      String category,
      String account,
      BigInt amount,
    ) => {
      'ledger': ledger,
      'category': category,
      'account': account,
      'amount': yearValuesMoney(amount),
      'date': row['date'],
      'economic_key': row['economic_key'],
      'original_entry_key': row['original_entry_key'],
      'source_ref': row['source_ref'],
    };
    final sign = incoming ? BigInt.one : -BigInt.one;
    final projected = row['kind'] == 'cash_history'
        ? [
            post(
              'euer',
              incoming ? 'sales' : record['category'],
              accounts['net'],
              sign * openItemCents(row['net']),
            ),
            post(
              'euer',
              incoming ? 'vat_collected' : 'paid_input_vat',
              accounts['tax'],
              sign * openItemCents(row['tax']),
            ),
            if (incoming)
              post(
                'vat',
                'output_vat',
                accounts['tax'],
                openItemCents(row['tax']),
              ),
          ]
        : [
            post(
              'vat',
              'input_vat',
              accounts['input_vat'],
              -openItemCents(row['amount']),
            ),
          ];
    _need(
      openingSame(actual, projected),
      'Die ursprünglichen Konten, Tage oder Centwerte wurden in der Journalprojektion verändert.',
    );
  }
}

Map<String, dynamic> yearValuesEntry(dynamic raw) {
  final v = businessMap(raw);
  _shape(v, [..._previewFields, ..._entryFields]);
  _id(v['id']);
  _id(v['created_by']);
  _int(v['sequence'], 1);
  _int(v['revision'], 1);
  if (v['previous_hash'] != null) _hash(v['previous_hash']);
  _need(DateTime.tryParse('${v['created_at']}') != null);
  final p = openItemCopy(v);
  for (final k in _entryFields) {
    p.remove(k);
  }
  yearValuesPreview(p, {for (final k in yearValuesInput) k: p[k]});
  final content = openItemCopy(v)..remove('content_hash');
  _need(
    openItemHash(content) == _hash(v['content_hash']) &&
        v['sequence'] == v['expected_revision'] + 1 &&
        v['revision'] == (v['previous_ref']?['revision'] ?? 0) + 1,
  );
  return v;
}

Map<String, dynamic> yearValuesState(dynamic raw) {
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
  ]);
  _scope(v);
  _int(v['revision']);
  _hash(v['state_hash']);
  _need(
    v['items'] is List &&
        v['originals'] is List &&
        v['can_prepare'] is bool &&
        v['max_original_bytes'] == 5242880,
  );
  if (v['profile'] == null) {
    _need(v['profile_ref'] == null && v['can_prepare'] == false);
  } else {
    _profile(v['profile'], v['profile_ref'], configured: false);
  }
  final originals = <String, Map<String, dynamic>>{};
  for (final o in businessItems(v['originals'])) {
    yearValuesOriginal(o, year: o['entity_key']);
    _need(!originals.containsKey(o['id']));
    originals[o['id']] = o;
  }
  final keys = <String>{};
  String? head;
  for (final raw in businessItems(v['items'])) {
    final e = yearValuesEntry(raw);
    _need(keys.add(e['entity_key']) && e['sequence'] <= v['revision']);
    if (e['sequence'] == v['revision']) head = e['content_hash'];
    for (final o in businessItems(
      e['proofs'],
    ).where((p) => (p['path'] as String).startsWith(yearValuesPath))) {
      _need(openingSame(o, originals[o['id']]));
    }
  }
  _need(
    (v['revision'] == 0) == ((v['items'] as List).isEmpty) &&
        (v['revision'] == 0 || head != null) &&
        openItemHash({
              'schema_version': 1,
              'revision': v['revision'],
              'head': head,
            }) ==
            v['state_hash'],
  );
  return v;
}

Map<String, dynamic> yearValuesHistory(dynamic raw, String year) {
  final v = businessMap(raw);
  _shape(v, ['schema_version', 'entity_key', 'items']);
  _need(
    v['schema_version'] == 1 && v['entity_key'] == year && v['items'] is List,
  );
  Map<String, dynamic>? old;
  for (final raw in businessItems(v['items'])) {
    final e = yearValuesEntry(raw);
    _need(
      e['entity_key'] == year &&
          e['revision'] == (old?['revision'] ?? 0) + 1 &&
          openingSame(e['previous_ref'], old == null ? null : _ref(old)),
    );
    old = e;
  }
  return v;
}

void Function(dynamic) yearValuesReceipt(
  Map<String, dynamic> body,
  Map<String, dynamic> preview,
  Map<String, dynamic> state,
) {
  final b = openItemCopy(body),
      p = openItemCopy(preview),
      s = openItemCopy(state),
      old = businessItems(s['items'])
          .where((e) => e['entity_key'] == b['entity_key'])
          .firstOrNull,
      head = businessItems(s['items'])
          .where((e) => e['sequence'] == s['revision'])
          .firstOrNull?['content_hash'];
  return (raw) {
    final v = yearValuesEntry(raw), actual = openItemCopy(v);
    for (final k in _entryFields) {
      actual.remove(k);
    }
    _need(
      b['confirmation'] == true &&
          openingSame(actual, p) &&
          yearValuesInput.every((k) => openingSame(v[k], b[k])) &&
          v['preview_hash'] == b['preview_hash'] &&
          v['previous_hash'] == head &&
          openingSame(v['previous_ref'], old == null ? null : _ref(old)),
      'Quittung bestätigt nicht genau den ursprünglichen Jahresauftrag.',
    );
  };
}

void Function(dynamic) yearValuesUploadReceipt(
  Map<String, dynamic> input,
  Uint8List bytes,
) {
  final b = openItemCopy(input),
      digest = openingDigest(bytes),
      size = bytes.length;
  return (raw) {
    final v = yearValuesOriginal(raw, year: b['entity_key']);
    _need(
      v['filename'] == b['filename'] &&
          v['media_type'] == b['media_type'] &&
          v['sha256'] == digest &&
          v['size'] == size,
      'Uploadantwort bestätigt nicht genau das ausgewählte Jahresoriginal.',
    );
  };
}

Map<String, dynamic> yearValuesSource(
  dynamic raw, {
  Map<String, dynamic>? entry,
}) {
  final v = businessMap(raw);
  _shape(v, [
    'kind',
    'schema_version',
    'rule_version',
    'id',
    'revision',
    'entry_id',
    'entry_hash',
    'status',
    'date',
    'profile_ref',
    'coverage',
    'details',
    'proofs',
    'attestations',
    'cash_movements',
    'source_path',
    'source_hash',
  ]);
  _need(
    v['kind'] == 'opening_year_values' &&
        v['schema_version'] == 1 &&
        v['rule_version'] == yearValuesRule &&
        ['active', 'void'].contains(v['status']),
  );
  yearValuesYear(v['id']);
  _id(v['entry_id']);
  _hash(v['entry_hash']);
  _int(v['revision'], 1);
  openingDate(v['date']);
  _reference(v['profile_ref'], profile: true);
  _attest(v['attestations']);
  _need(
    v['proofs'] is List &&
        v['cash_movements'] is List &&
        (v['cash_movements'] as List).isEmpty &&
        v['source_path'] ==
            '$yearValuesPath/years/${v['id']}?revision=${v['revision']}',
  );
  for (final p in businessItems(v['proofs'])) {
    yearValuesOriginal(p);
  }
  _details(v['details'], v['id'], v['date'], v['coverage']);
  final plain = openItemCopy(v)..remove('source_hash');
  _need(openItemHash(plain) == _hash(v['source_hash']));
  if (entry != null) {
    final e = yearValuesEntry(entry);
    _need(
      v['id'] == e['entity_key'] &&
          v['entry_id'] == e['id'] &&
          v['entry_hash'] == e['content_hash'] &&
          v['revision'] == e['revision'] &&
          v['status'] == e['payload']['status'] &&
          openingSame(v['profile_ref'], e['profile_ref']) &&
          openingSame(v['coverage'], e['payload']['coverage']) &&
          openingSame(v['details'], e['details']) &&
          openingSame(v['proofs'], e['proofs']) &&
          openingSame(v['attestations'], e['payload']['attestations']),
      'Jahresquelle wurde von der unveränderten ursprünglichen Fassung gelöst.',
    );
  }
  return v;
}

Future<Map<String, dynamic>> yearValuesVerifiedEntry(
  BusinessSession session,
  dynamic raw, {
  bool Function()? stillCurrent,
}) async {
  final entry = yearValuesEntry(raw), originals = <Map<String, dynamic>>[];
  for (final source in businessItems(
    entry['payload']['sources'],
  ).where((s) => s['kind'] == 'opening_item')) {
    final resolved = businessItems(entry['resolved_sources'])
        .firstWhere((s) => s['source_ref'] == source['entry_hash']);
    final proof = businessItems(entry['proofs']).firstWhere(
      (p) => p['id'] == resolved['record']['invoice_proof']['original_id'],
    );
    final key = proof['entity_key'] as String;
    final history = openItemHistory(
      await session.read(openItemHistoryPath(key)),
      key,
    );
    if (stillCurrent?.call() == false)
      throw const ApiException(
        409,
        'Der Jahresvortragskontext wurde geändert.',
      );
    final old = businessItems(history['items'])
        .where(
          (e) =>
              e['id'] == source['entry_id'] &&
              e['content_hash'] == source['entry_hash'],
        )
        .firstOrNull;
    _need(
      old != null && openingSame(old['payload'], resolved['record']),
      'Die ursprüngliche Altpostenfassung wurde hinter der Jahresquelle verändert.',
    );
    for (final p in businessItems(old!['proofs'])) {
      final supplied = businessItems(entry['proofs'])
          .where((v) => v['id'] == p['id'])
          .toList();
      _need(
        supplied.isNotEmpty && supplied.every((v) => openingSame(v, p)),
        'Ursprüngliche Altpostenoriginal-Metadaten wurden ersetzt.',
      );
    }
    originals.add(old);
  }
  final preview = openItemCopy(entry);
  for (final key in _entryFields) {
    preview.remove(key);
  }
  yearValuesPreview(preview, {
    for (final key in yearValuesInput) key: entry[key],
  }, openingItems: originals);
  return entry;
}

Future<Map<String, dynamic>> yearValuesVerifiedSource(
  BusinessSession s,
  dynamic raw, {
  bool Function()? stillCurrent,
}) async {
  final source = yearValuesSource(raw);
  final history = yearValuesHistory(
    await s.read('$yearValuesPath/history?entity_key=${source['id']}'),
    source['id'],
  );
  if (stillCurrent?.call() == false)
    throw const ApiException(409, 'Der Jahresquellenkontext wurde geändert.');
  final entry = businessItems(history['items'])
      .where((e) => e['id'] == source['entry_id'])
      .firstOrNull;
  _need(entry != null);
  await yearValuesVerifiedEntry(s, entry, stillCurrent: stillCurrent);
  return yearValuesSource(source, entry: entry);
}

void yearValuesEuerPreview(
  Map<String, dynamic> preview,
  Map<String, dynamic> body,
) {
  final effect = businessMap(preview['effect']),
      source = yearValuesSource(effect['source']),
      payload = businessMap(body['payload']),
      target = 'opening_year_values:${source['id']}';
  _need(
    source['status'] == 'active' &&
        effect['operation'] == 'opening_year_values' &&
        openingSame(effect['payload'], payload) &&
        openingSame(payload, {
          'year': source['id'],
          'revision': source['revision'],
          'source_hash': source['source_hash'],
        }) &&
        effect['target'] == target &&
        preview['target'] == target,
  );
  final postings = [
    for (final p in businessItems(source['details']['historical_postings']))
      {
        'ledger': p['ledger'],
        'category': p['category'],
        'account': p['account'],
        'amount': p['amount'],
        'date': p['date'],
        'source_key': '$target:${p['economic_key']}',
      },
  ];
  _need(
    openingSame(effect['postings'], postings) &&
        openingSame(preview['postings'], postings) &&
        openingSame(effect['details'], {
          'date': source['date'],
          'coverage': source['coverage'],
          'cash_flow_created': false,
          'new_input_vat_claim_created': false,
          'original_periods_preserved': true,
        }),
    'EÜR-Vorschau verändert die ursprünglichen Tage, Konten oder Beträge.',
  );
}

void _recordProof(dynamic v) {
  _shape(v, ['original_id', 'sha256']);
  _id(v['original_id']);
  _hash(v['sha256']);
}

BigInt _taxAt(BigInt gross, BigInt tax, BigInt total) =>
    (BigInt.two * gross * tax + total) ~/ (BigInt.two * total);
void yearValuesClosedRecord(dynamic p, Map<String, dynamic> profile) {
  _need(
    p is Map && p['status'] == 'active',
    'Nur aktive vollständig erledigte ursprüngliche Rechnungen übernehmen.',
  );
  _shape(p, [
    'status',
    'external_system',
    'external_id',
    'direction',
    'counterparty_key',
    'counterparty_name',
    'invoice_number',
    'invoice_date',
    'service_date',
    'invoice_received_date',
    'currency',
    'rate',
    'category',
    'net',
    'tax',
    'gross',
    'prior_payments',
    'invoice_proof',
    'cutover_proof',
    'history_through',
    'prior_input_vat',
    'scope_confirmed',
  ]);
  if (!['active', 'void'].contains(p['status']) ||
      !['receivable', 'payable'].contains(p['direction']) ||
      p['currency'] != 'EUR' ||
      !['19', '7'].contains(p['rate']) ||
      p['scope_confirmed'] != true)
    _bad('Unterstützten gewöhnlichen Altposten ausdrücklich bestätigen.');
  for (final k in [
    'external_system',
    'external_id',
    'counterparty_key',
    'counterparty_name',
    'invoice_number',
  ])
    openItemText(p[k], k);
  for (final k in [
    'invoice_date',
    'service_date',
    'invoice_received_date',
    'history_through',
  ])
    openingDate(p[k]);
  final opening = profile['bookkeeping_start'] as String;
  final priorDay = DateTime.parse(opening)
      .subtract(const Duration(days: 1))
      .toIso8601String()
      .substring(0, 10);
  if (p['history_through'] != priorDay ||
      [
        'invoice_date',
        'service_date',
        'invoice_received_date',
      ].any((k) => (p[k] as String).compareTo(opening) >= 0) ||
      (p['invoice_received_date'] as String).compareTo(p['invoice_date']) < 0 ||
      ['invoice_date', 'service_date'].any(
        (k) => (p[k] as String).compareTo(profile['vat_effective_from']) < 0,
      ))
    _bad(
      'Belegte Altzeitpunkte und vollständige Historie bis zum Vortag erforderlich.',
    );
  final net = openItemCents(p['net']),
      tax = openItemCents(p['tax']),
      gross = openItemCents(p['gross']);
  if (net <= BigInt.zero ||
      net + tax != gross ||
      tax !=
          (net * BigInt.parse(p['rate']) + BigInt.from(50)) ~/ BigInt.from(100))
    _bad(
      'Originalnetto, Originalsteuer und Originalbrutto passen nicht zur belegten Gesamtgruppe.',
    );
  if (!openItemCategories.containsKey(p['category']) ||
      (p['direction'] == 'receivable') != (p['category'] == 'sales'))
    _bad('Passende gewöhnliche Erlös-/Aufwandsart erforderlich.');
  _recordProof(p['invoice_proof']);
  _recordProof(p['cutover_proof']);
  if (p['prior_payments'] is! List ||
      (p['prior_payments'] as List).length > 100)
    _bad('Vollständige Liste der alten Zahlungen erforderlich.');
  var settled = BigInt.zero;
  String? last;
  for (final row in p['prior_payments']) {
    _shape(row, ['date', 'reference', 'gross', 'net', 'tax', 'proof']);
    openingDate(row['date']);
    openItemText(row['reference'], 'Alte Zahlungsreferenz');
    _recordProof(row['proof']);
    final amount = openItemCents(row['gross']);
    final earlier = [p['invoice_date'] as String, p['service_date'] as String]
      ..sort();
    if (amount <= BigInt.zero ||
        settled + amount > gross ||
        (row['date'] as String).compareTo(opening) >= 0 ||
        (row['date'] as String).compareTo(earlier.last) < 0 ||
        last != null && (row['date'] as String).compareTo(last) < 0)
      _bad(
        'Belegte alte Zahlungen chronologisch und innerhalb der Rechnung erfassen.',
      );
    final part =
        _taxAt(settled + amount, tax, gross) - _taxAt(settled, tax, gross);
    if (openItemCents(row['tax']) != part ||
        openItemCents(row['net']) != amount - part)
      _bad(
        'Historische Centaufteilung widerspricht dem unterstützten Originalverfahren; keine Altdaten umrechnen.',
      );
    settled += amount;
    last = row['date'];
  }
  if (settled != gross)
    _bad(
      'Erledigte externe Rechnung muss vor Beginn vollständig bezahlt sein.',
    );
  final vat = p['prior_input_vat'];
  if (p['direction'] == 'receivable') {
    if (vat != null) _bad('Forderung besitzt keinen Vorsteuerübertrag.');
  } else {
    _shape(vat, [
      'amount',
      'entitlement_date',
      'declared_period',
      'deducted_on',
      'proof',
    ]);
    openingDate(vat['entitlement_date']);
    openingDate(vat['deducted_on']);
    _recordProof(vat['proof']);
    final days = [
      p['service_date'] as String,
      p['invoice_received_date'] as String,
    ]..sort();
    if (vat['amount'] != p['tax'] ||
        vat['entitlement_date'] != days.last ||
        vat['declared_period'] != days.last.substring(0, 7) ||
        (vat['declared_period'] as String).compareTo(opening.substring(0, 7)) >=
            0 ||
        (vat['deducted_on'] as String).compareTo(days.last) < 0 ||
        (vat['deducted_on'] as String).compareTo(opening) >= 0)
      _bad(
        'Vollständigen früheren Vorsteuerabzug mit Anspruch, Vorperiode und tatsächlichem Ausübungstag belegen.',
      );
  }
}

void yearValuesReport(
  Map<String, dynamic> report,
  List<Map<String, dynamic>> catalog,
) {
  final row = catalog
      .where(
        (r) =>
            r['kind'] == 'opening_year_values' &&
            r['id'] == '${report['year']}',
      )
      .firstOrNull;
  final current = businessMap(row?['current']),
      projection = report['historical_year_values'];
  if (current.isEmpty) {
    _need(
      !report.containsKey('historical_year_values'),
      'Jahresdeckung ohne aktive ursprüngliche EÜR-Übernahme.',
    );
    return;
  }
  final source = yearValuesSource(current['effect']?['source']);
  _shape(projection, [
    'schema_version',
    'entry_id',
    'entry_hash',
    'source_hash',
    'source_path',
    'coverage',
    'original_periods_preserved',
    'cash_flow_created',
    'new_input_vat_claim_created',
  ]);
  _need(
    projection['schema_version'] == 1 &&
        projection['entry_id'] == current['id'] &&
        projection['entry_hash'] == current['entry_hash'] &&
        projection['source_hash'] == source['source_hash'] &&
        projection['source_path'] == source['source_path'] &&
        openingSame(projection['coverage'], source['coverage']) &&
        projection['cash_flow_created'] == false &&
        projection['new_input_vat_claim_created'] == false &&
        projection['original_periods_preserved'] == true,
    'Die ausgewiesene alte Jahresdeckung gehört nicht zur aktiven ursprünglichen Journalübernahme.',
  );
  if (source['details']['complete_prior_period'] != true &&
      report['period'] == null)
    _need(
      report['complete_for_recorded_sources'] == false &&
          report['totals']['euer_surplus'] == null,
      'Teilzeitraum darf kein vollständiges Unternehmensjahr ausweisen.',
    );
}

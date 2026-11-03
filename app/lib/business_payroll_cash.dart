import 'dart:convert';

import 'api.dart';
import 'business_session.dart';

const payrollCashCategories = {
  'payroll_net': 'Belegte Nettozahlungen',
  'payroll_employee_tax': 'Abgeführte Arbeitnehmersteuern',
  'payroll_employee_social': 'Abgeführte Arbeitnehmerbeiträge',
  'payroll_employer_social': 'Abgeführte Arbeitgeberbeiträge',
  'payroll_employer_levies': 'Bezahlte Arbeitgeberumlagen',
  'payroll_employer_flat_tax': 'Bezahlte Arbeitgeber-Pauschsteuer',
};
const payrollRemittance = {
  'employee_tax': 'Tatsächlich abgeführte Arbeitnehmersteuern (€)',
  'employee_social': 'Tatsächlich abgeführte Arbeitnehmerbeiträge (€)',
  'employer_social': 'Tatsächlich abgeführte Arbeitgeberbeiträge (€)',
  'employer_levies': 'Tatsächlich bezahlte Arbeitgeberumlagen (€)',
  'employer_flat_tax': 'Tatsächlich bezahlte Arbeitgeber-Pauschsteuer (€)',
};
final _id = RegExp(r'^[a-f0-9]{32}$'), _hash = RegExp(r'^[a-f0-9]{64}$');
Never _fail(String message, [int status = 0]) =>
    throw ApiException(status, message);
BigInt _cents(dynamic value) {
  if (value is! String ||
      !RegExp(r'^(?:0|[1-9]\d{0,12})\.\d{2}$').hasMatch(value))
    _fail('Genaue belegte EUR-Cents erwartet.');
  return BigInt.parse(value.replaceAll('.', ''));
}

Map<String, dynamic> payrollCashPublic(dynamic raw) {
  final source = businessMap(raw),
      keys = {
        'kind',
        'id',
        'revision',
        'instance_id',
        'status',
        'date',
        'cash_movements',
        'source_path',
        'source_hash',
        'proof_hash',
      };
  if (source.keys.any((k) => !keys.contains(k)) ||
      source['kind'] != 'payroll_cash' ||
      !_id.hasMatch('${source['id']}') ||
      !_id.hasMatch('${source['instance_id']}') ||
      !_hash.hasMatch('${source['source_hash']}') ||
      !_hash.hasMatch('${source['proof_hash']}') ||
      source['revision'] is! int ||
      source['revision'] < 1 ||
      !['active', 'void'].contains(source['status']) ||
      source['cash_movements'] is! List ||
      !RegExp(r'^2026-\d{2}-\d{2}$').hasMatch('${source['date']}') ||
      source['source_path'] !=
          '/payroll/cash/financial/${source['id']}?revision=${source['revision']}' ||
      source['status'] == 'active' &&
          (source['cash_movements'] as List).isEmpty)
    _fail(
      'Die öffentliche Lohnzahlungsquelle ist nicht eindeutig und datensparsam bestätigt.',
    );
  final seen = <String>{};
  for (final raw in source['cash_movements']) {
    final m = businessMap(raw), categories = businessMap(m['categories']);
    if (m.keys.any(
          (k) => !{
            'id',
            'date',
            'account',
            'direction',
            'amount',
            'categories',
          }.contains(k),
        ) ||
        !_id.hasMatch('${m['id']}') ||
        !seen.add(m['id']) ||
        !['in', 'out'].contains(m['direction']) ||
        !RegExp(r'^2026-\d{2}-\d{2}$').hasMatch('${m['date']}') ||
        !_id.hasMatch('${m['account']?['id']}') ||
        m['account']?['currency'] != 'EUR' ||
        m['categories'] is! Map ||
        categories.keys.any((k) => !payrollCashCategories.containsKey(k)))
      _fail(
        'Die Lohnzahlung ist nicht eindeutig an Richtung, Zeitpunkt und Geldkonto gebunden.',
      );
    final sum = categories.values.fold(BigInt.zero, (sum, v) {
      final amount = _cents(v);
      if (amount <= BigInt.zero)
        _fail('Belegte Kategorien benötigen positive Beträge.');
      return sum + amount;
    });
    if (sum != _cents(m['amount']) || sum <= BigInt.zero)
      _fail(
        'Belegte Lohnzahlungsanteile stimmen nicht mit dem Geldfluss überein.',
      );
  }
  if (source['status'] == 'void' &&
      (source['cash_movements'] as List).isNotEmpty)
    _fail('Die Nachweisaufhebung darf keine Rückzahlung erfinden.');
  return source;
}

List<String> payrollCashCategoryKeys(Map<String, dynamic> source) {
  payrollCashPublic(source);
  return {
    for (final m in source['cash_movements'])
      ...businessMap(m['categories']).keys,
  }.toList()..sort();
}

bool payrollCashReadable(BusinessSession s) =>
    s.hasFeature('payroll_actual_cash') &&
    s.hasModule('payroll_cash') &&
    ['personnel.read', 'accounting.read', 'finance.read'].every(s.can);
bool payrollCashWritable(BusinessSession s) =>
    payrollCashReadable(s) &&
    !s.readonly &&
    ['personnel.approve', 'accounting.prepare', 'finance.write'].every(s.can) &&
    s.sectionEnabled('personnel') &&
    s.sectionEnabled('finance');
Map<String, dynamic> _copy(dynamic v) => businessMap(jsonDecode(jsonEncode(v)));
dynamic _ordered(dynamic v) => v is List
    ? v.map(_ordered).toList()
    : v is Map
    ? {
        for (final k in v.keys.map((k) => '$k').toList()..sort())
          k: _ordered(v[k]),
      }
    : v;
bool payrollCashSame(dynamic a, dynamic b) =>
    jsonEncode(_ordered(a)) == jsonEncode(_ordered(b));
int payrollCashMinor(dynamic v) {
  final text = '${v ?? ''}'.trim().replaceAll(',', '.');
  if (!RegExp(r'^\d{1,10}(?:\.\d{1,2})?$').hasMatch(text))
    _fail('Belegten Betrag ausdrücklich angeben, einschließlich bekannter 0.');
  final parts = text.split('.'),
      result =
          int.parse(parts[0]) * 100 +
          int.parse((parts.length > 1 ? parts[1] : '').padRight(2, '0'));
  if (result > 1000000000000) _fail('Betrag außerhalb des geprüften Bereichs.');
  return result;
}

Map<String, dynamic> payrollCashInput(
  String employee,
  Map<String, dynamic> state,
  Map<String, dynamic> page,
  List<Map<String, dynamic>> accounts,
  Map<String, dynamic> values, {
  required String kind,
  required String batchId,
  List<Map<String, dynamic>> selected = const [],
  Map<String, dynamic>? previous,
  String action = 'adopt',
}) {
  if (page['employee_id'] != employee ||
      page['instance_id'] != state['instance_id'] ||
      !_id.hasMatch(batchId))
    _fail('Mitarbeiter und Unternehmensinstanz zuerst neu prüfen.');
  final bank = action == 'void'
          ? <String, dynamic>{
              'id': previous?['command']?['account_id'],
              'revision': previous?['command']?['account_revision'],
            }
          : accounts
                .where(
                  (a) => a['id'] == values['account_id'] && a['active'] == true,
                )
                .firstOrNull,
      reason = '${values['reason'] ?? ''}'.trim();
  if (bank == null || !_id.hasMatch('${bank['id']}'))
    _fail('Tatsächlich verwendetes aktives Geldkonto auswählen.');
  if (reason.isEmpty || reason.length > 1000)
    _fail('Übernahme- oder Korrekturgrund vollständig angeben.');
  final files = businessItems(page['evidence_files'])
          .where((f) => f['employee_id'] == employee),
      correction = files
          .where((f) => f['id'] == values['correction_file_id'])
          .firstOrNull;
  if (action != 'adopt' && correction == null)
    _fail('Die Nachweiskorrektur benötigt ein geschütztes Original.');
  final body = <String, dynamic>{
    'batch_id': batchId,
    'expected_revision': previous?['revision'] ?? 0,
    'instance_id': state['instance_id'],
    'action': action,
    'kind': kind,
    'account_id': bank['id'],
    'account_revision': bank['revision'],
    'sources': <Map<String, dynamic>>[],
    'settlement': null,
    'correction_file_id': correction?['id'],
    'reason': reason,
  };
  if (action == 'void') return body;
  final sources = body['sources'] as List<Map<String, dynamic>>;
  if (kind == 'net') {
    for (var index = 0; index < selected.length; index++) {
      final source = selected[index],
          original = businessItems(page['net_sources'])
              .where(
                (s) =>
                    s['id'] == source['id'] &&
                    s['revision'] == source['revision'] &&
                    s['content_hash'] == source['content_hash'] &&
                    s['eligible'] == true,
              )
              .firstOrNull;
      if (original == null)
        _fail('Die aktuelle vollständige Nettozahlungsquelle fehlt.');
      final indexes = (values['parts_$index'] as List? ?? [])
          .map((v) => int.parse('$v'))
          .toList();
      if (indexes.toSet().length != indexes.length ||
          indexes.any(
            (i) => !businessItems(original['payments']).any(
              (p) =>
                  p['index'] == i &&
                  (p['already_imported'] != true ||
                      p['import_batch_id'] == previous?['id']),
            ),
          ))
        _fail(
          'Nur ausdrücklich gewählte neue oder korrigierte Zahlungsteile übernehmen.',
        );
      if (indexes.isNotEmpty)
        sources.add({
          'account_record_id': source['id'],
          'revision': source['revision'],
          'content_hash': source['content_hash'],
          'payment_indexes': indexes..sort(),
        });
    }
  } else if (kind == 'remittance') {
    for (var index = 0; index < selected.length; index++) {
      final source = selected[index];
      if (!businessItems(page['remittance_sources']).any(
        (s) =>
            s['source_kind'] == source['source_kind'] &&
            s['id'] == source['id'] &&
            s['revision'] == source['revision'] &&
            s['content_hash'] == source['content_hash'] &&
            s['eligible'] == true,
      ))
        _fail('Die aktuelle vollständige Abführungsquelle fehlt.');
      final amounts = {
        for (final k in payrollRemittance.keys)
          k: payrollCashMinor(values['remit_${index}_$k']),
      };
      if (amounts.values.any((v) => v > 0))
        sources.add({
          'source_kind': source['source_kind'],
          'id': source['id'],
          'revision': source['revision'],
          'content_hash': source['content_hash'],
          'amounts': amounts,
        });
    }
    final file = files
        .where((f) => f['id'] == values['source_file_id'])
        .firstOrNull;
    if (file == null)
      _fail(
        'Geschützten Originalnachweis der tatsächlichen Abführung auswählen.',
      );
    final amount = payrollCashMinor(values['amount_minor']),
        sum = sources.fold<int>(
          0,
          (n, s) =>
              n +
              businessMap(s['amounts']).values
                  .fold<int>(0, (a, b) => a + (b as int)),
        );
    if (amount <= 0 || amount != sum)
      _fail(
        'Belegter Zahlungsbetrag und ausdrücklich ausgewählte Abführungsanteile müssen centgenau übereinstimmen.',
      );
    body['settlement'] = {
      'paid_on': values['paid_on'],
      'payment_reference': '${values['payment_reference'] ?? ''}'.trim(),
      'amount_minor': amount,
      'source_file_id': file['id'],
      'employee_id': employee,
      'sha256': file['sha256'],
    };
    if (!RegExp(r'^2026-\d{2}-\d{2}$').hasMatch('${values['paid_on']}') ||
        body['settlement']['payment_reference'] == '')
      _fail('Tatsächlichen Zahltag 2026 und Zahlungsreferenz angeben.');
  } else {
    _fail('Unbekannte Lohnzahlungsart.');
  }
  if (sources.isEmpty)
    _fail('Mindestens einen belegten tatsächlich gezahlten Anteil auswählen.');
  return body;
}

Map<String, dynamic> payrollCashPreview(
  dynamic raw,
  Map<String, dynamic> body,
) {
  final v = businessMap(raw);
  if (v['batch_id'] != body['batch_id'] ||
      v['revision'] != body['expected_revision'] + 1 ||
      v['kind'] != body['kind'] ||
      v['instance_id'] != body['instance_id'] ||
      !_hash.hasMatch('${v['private_hash']}') ||
      !_hash.hasMatch('${v['preview_hash']}') ||
      v['private_source_count'] is! int ||
      v['private_source_count'] < 0 ||
      body['action'] != 'void' &&
          v['private_source_count'] != (body['sources'] as List).length ||
      v['warnings'] is! List)
    _fail('Die Lohnzahlungsvorschau gehört nicht zum geprüften Auftrag.');
  final source = payrollCashPublic(v['public_source']);
  if (source['id'] != body['batch_id'] ||
      source['revision'] != v['revision'] ||
      source['instance_id'] != body['instance_id'] ||
      source['proof_hash'] != v['private_hash'] ||
      businessItems(source['cash_movements']).any(
        (m) =>
            m['account']['id'] != body['account_id'] ||
            m['account']['revision'] != body['account_revision'],
      ) ||
      source['status'] != (body['action'] == 'void' ? 'void' : 'active'))
    _fail(
      'Private Zahlungsquellen und öffentliche Vorschau sind nicht eindeutig verbunden.',
    );
  return v;
}

void Function(dynamic) payrollCashValidator(
  Map<String, dynamic> body,
  Map<String, dynamic> preview,
) {
  final b = _copy(body), p = _copy(preview);
  return (raw) {
    final v = businessMap(raw);
    if (v['id'] != b['batch_id'] ||
        v['revision'] != p['revision'] ||
        v['kind'] != b['kind'] ||
        v['instance_id'] != b['instance_id'] ||
        v['status'] != p['public_source']['status'] ||
        v['private_hash'] != p['private_hash'] ||
        !payrollCashSame(v['public_source'], p['public_source']))
      _fail(
        'Die Übernahmebestätigung passt nicht zur geprüften Lohnzahlungsvorschau. Der ursprüngliche Auftrag bleibt erhalten.',
      );
  };
}

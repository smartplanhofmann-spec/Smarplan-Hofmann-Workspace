import 'dart:convert';

import 'package:cryptography/dart.dart';

import 'api.dart';
import 'business_payroll_facts.dart';
import 'business_payroll_factor_claims.dart';
import 'business_session.dart' show businessMap, businessItems;

const payrollFactorClaimTravelRule =
    'de_2026_factor_claims_paid_travel_month_v13';
const payrollFactorClaimTravelFeature = 'payroll_factor_claims_paid_travel';
const payrollFactorClaimTravelScope =
    'regular_standard_factor_claims_paid_travel_month';
const _travelRule = 'de_2026_factor_taxfree_travel_month_v10';
const _projections = {
  'claims':
      'UNCHANGED_ORIGINALS_WITH_TRAVEL_SOURCES_EMPTY_AND_FLAT_TRAVEL_TAX_NULL',
  'paid_travel':
      'UNCHANGED_ORIGINALS_WITH_ENTITLEMENTS_EMPTY_FOR_TRAVEL_PROOF_ONLY',
};
final _shaPattern = RegExp(r'^[a-f0-9]{64}$');
Never _bad(String message) => throw ApiException(400, message);
dynamic _ordered(dynamic v) => v is List
    ? v.map(_ordered).toList()
    : v is Map
    ? {
        for (final k in v.keys.cast<String>().toList()..sort())
          k: _ordered(v[k]),
      }
    : v;
String _hash(dynamic v) => const DartSha256()
    .hashSync(utf8.encode(jsonEncode(_ordered(v))))
    .bytes
    .map((b) => b.toRadixString(16).padLeft(2, '0'))
    .join();
bool _same(dynamic a, dynamic b) => payrollFactsSame(a, b);
Map<String, dynamic> _omit(Map<String, dynamic> v, List<String> keys) =>
    {...v}..removeWhere((k, _) => keys.contains(k));
int _money(dynamic v, {bool positive = false}) {
  if (v is! int || v < (positive ? 1 : 0))
    _bad('Ganze belegte Centbeträge erforderlich.');
  return v;
}

String _note(dynamic v) {
  if (v is! String ||
      v.trim().isEmpty ||
      v.trim().length > 3000 ||
      RegExp(r'[\x00-\x1f\x7f]').hasMatch(v))
    _bad('Die ausdrückliche Ergänzung oder Korrektur vollständig begründen.');
  return v.trim();
}

Map<String, Map<String, dynamic>> payrollFactorClaimTravelProjections(
  Map<String, dynamic> s, [
  Map<String, dynamic>? d,
]) {
  final result = <String, Map<String, dynamic>>{
    'claims': {
      ...s,
      'rule_version': payrollFactorClaimsRule,
      'source_contract_version': 4,
      'travel_sources': [],
      'flat_travel_tax': null,
    },
    'paid_travel': {
      ...s,
      'rule_version': _travelRule,
      'source_contract_version': 2,
      'entitlements': [],
    },
  };
  if (d != null) {
    result['claimDetails'] = {...d, 'travel_settlement_refs': []}
      ..remove('travel_payment_refs');
    result['travelDetails'] = {...d, 'entitlement_case_refs': []};
  }
  return result;
}

void payrollFactorClaimTravelPlan(Map<String, dynamic> p) {
  final components = businessMap(p['components']);
  if (p['rule_version'] != payrollFactorClaimTravelRule ||
      p['source_contract_version'] is! int ||
      p['source_contract_version'] != 5 ||
      !_shaPattern.hasMatch('${p['rules_sha256']}') ||
      !_same(components.keys.toList()..sort(), ['claims', 'paid_travel']))
    _bad('Vollständigen eigenen Faktor-/Anspruchs-/Reiseplan verwenden.');
  for (final name in ['claims', 'paid_travel']) {
    final c = businessMap(components[name]), plan = businessMap(c['plan']);
    if (!_same(
          c.keys.toList()..sort(),
          [
            'plan',
            'plan_hash',
            'projection',
            'rule_version',
            'rules_sha256',
            'source_contract_version',
            'source_snapshot_hash',
          ]..sort(),
        ) ||
        c['rule_version'] !=
            (name == 'claims' ? payrollFactorClaimsRule : _travelRule) ||
        c['source_contract_version'] is! int ||
        c['source_contract_version'] != (name == 'claims' ? 4 : 2) ||
        c['projection'] != _projections[name] ||
        !_shaPattern.hasMatch('${c['source_snapshot_hash']}') ||
        c['rules_sha256'] != plan['rules_sha256'] ||
        c['plan_hash'] != plan['plan_hash'] ||
        c['source_snapshot_hash'] != plan['source_snapshot_hash'])
      _bad('Die unveränderten beiden Projektionsverträge fehlen.');
  }
  final wage = businessMap(components['claims']['plan']),
      travel = businessMap(components['paid_travel']['plan']);
  payrollFactorClaimsPlan(wage);
  if (travel['travel_payment_refs'] is! List ||
      (travel['travel_payment_refs'] as List).isEmpty ||
      travel['flat_travel_tax'] != null ||
      businessItems(travel['entitlement_sources']).isNotEmpty ||
      (travel['unpaid_dates'] as List).isNotEmpty ||
      travel['travel']?['letter_m'] != false ||
      [
        'flat_taxable_payroll_minor',
        'individual_taxable_payroll_minor',
        'benefit_in_kind_non_cash_minor',
      ].any((k) => travel['travel']?[k] != 0) ||
      _money(travel['travel_paid_minor'], positive: true) !=
          travel['travel']?['tax_free_external_minor'])
    _bad(
      'Ausschließlich ursprüngliche vollständig bezahlte steuerfreie Reisen binden.',
    );
  final satisfied =
      wage['can_calculate'] == true &&
          _money(wage['gross_minor']) > 0 &&
          businessItems(travel['blockers'])
              .any((r) => r['code'] == 'zero_earnings_requires_review')
      ? ['zero_earnings_requires_review']
      : <String>[];
  final blockers = <String, Map<String, dynamic>>{
    for (final row in businessItems(wage['blockers'])) row['code']: row,
  };
  for (final row in businessItems(travel['blockers'])) {
    if (!satisfied.contains(row['code']))
      blockers.putIfAbsent(row['code'], () => row);
  }
  final merged = blockers.values.toList()
    ..sort((a, b) => (a['code'] as String).compareTo(b['code']));
  final expected = {
    ..._omit(wage, ['plan_hash', 'can_confirm', 'can_calculate']),
    'rule_version': payrollFactorClaimTravelRule,
    'source_contract_version': 5,
    'rules_sha256': p['rules_sha256'],
    'source_snapshot_hash': p['source_snapshot_hash'],
    'components': components,
    'travel': travel['travel'],
    'travel_source_hashes': travel['travel_source_hashes'],
    'travel_payment_refs': travel['travel_payment_refs'],
    'travel_paid_minor': travel['travel_paid_minor'],
    'satisfied_travel_component_wage_reviews': satisfied,
    'blockers': merged,
    'plan_hash': p['plan_hash'],
    'can_confirm': true,
    'can_calculate': merged.isEmpty,
  };
  if (!_same(expected, p))
    _bad(
      'Der gemeinsame Plan verändert Ansprüche, Reisebeweise oder getrennte Geldbeträge.',
    );
}

List<Map<String, dynamic>> _refs(Iterable<dynamic> rows) =>
    rows.map(payrollFactRef).toList()
      ..sort((a, b) => (a['id'] as String).compareTo(b['id']));

void payrollFactorClaimTravelBindings(
  Map<String, dynamic> s,
  Map<String, dynamic> d,
  Map<String, dynamic> p,
) {
  if (s['rule_version'] != payrollFactorClaimTravelRule ||
      s['source_contract_version'] is! int ||
      s['source_contract_version'] != 5 ||
      (d['entitlement_case_refs'] as List).isEmpty ||
      (d['travel_settlement_refs'] as List).isEmpty ||
      (d['travel_payment_refs'] as List).isEmpty)
    _bad(
      'Beide ursprünglichen Anspruchs- und bezahlten Reisekomponenten vollständig binden.',
    );
  payrollFactorClaimTravelPlan(p);
  final x = payrollFactorClaimTravelProjections(s, d);
  payrollFactorClaimsBindings(
    x['claims']!,
    x['claimDetails']!,
    businessMap(p['components']['claims']['plan']),
  );
  final payments = <Map<String, dynamic>>[],
      settlements = <Map<String, dynamic>>[],
      ids = <String>{};
  var total = 0;
  for (final source in businessItems(s['travel_sources'])) {
    final proof = businessMap(source['payment_proof']);
    final settlement = payrollFactRef(source['settlement_ref']);
    settlements.add(settlement);
    if (source['kind'] != 'travel_allowances' ||
        source['schema_version'] != 1 ||
        source['employee_id'] != s['employee_id'] ||
        !_shaPattern.hasMatch('${source['source_hash']}') ||
        !_shaPattern.hasMatch('${source['rule_hash']}') ||
        (source['allocations'] as List).isNotEmpty ||
        source['letter_m'] != false ||
        [
          'flat_taxable_payroll_minor',
          'individual_taxable_payroll_minor',
          'benefit_in_kind_non_cash_minor',
        ].any((k) => source[k] != 0) ||
        proof['schema_version'] is! int ||
        proof['schema_version'] != 1 ||
        proof['cutoff_sequence'] is! int ||
        proof['cutoff_sequence'] < 1 ||
        proof['payments'] is! List ||
        (proof['payments'] as List).isEmpty)
      _bad(
        'Die steuerfreie Reise besitzt keinen vollständigen ursprünglichen Zahlungsnachweis.',
      );
    var paid = 0;
    final sequences = <int>{};
    for (final payment in businessItems(proof['payments'])) {
      payrollFactRef(payment);
      final date = payrollFactDate(payment['paid_on'])!;
      if (!['active', 'void'].contains(payment['status']) ||
          !['reimbursement', 'repayment'].contains(payment['kind']) ||
          !date.startsWith('${d['month']}-') ||
          payment['sequence'] is! int ||
          payment['sequence'] < 1 ||
          payment['sequence'] > proof['cutoff_sequence'] ||
          !sequences.add(payment['sequence']) ||
          !ids.add(payment['id']) ||
          !_shaPattern.hasMatch('${payment['cash_source_hash']}'))
        _bad('Die ursprüngliche Folge der Reisezahlungen ist widersprüchlich.');
      final amount = _money(payment['amount_minor'], positive: true);
      payments.add(payment);
      if (payment['status'] == 'active')
        paid += (payment['kind'] == 'reimbursement' ? 1 : -1) * amount;
    }
    if (sequences.reduce((a, b) => a > b ? a : b) != proof['cutoff_sequence'] ||
        paid != _money(proof['paid_minor']) ||
        paid != _money(source['tax_free_external_minor'], positive: true))
      _bad('Die belegte Reiseerstattung ist nicht vollständig ausgezahlt.');
    total += paid;
  }
  if (settlements.map((v) => v['id']).toSet().length != settlements.length ||
      !_same(_refs(settlements), _refs(d['travel_settlement_refs'])) ||
      !_same(_refs(payments), _refs(d['travel_payment_refs'])) ||
      !_same(p['travel_payment_refs'], d['travel_payment_refs']) ||
      !_same(
        p['travel_source_hashes'],
        businessItems(s['travel_sources'])
            .map((v) => v['source_hash'])
            .toList(),
      ) ||
      total != p['travel_paid_minor'])
    _bad(
      'Die ursprünglichen Reisezahlungen wurden ersetzt oder nicht vollständig ausgewählt.',
    );
}

void payrollFactorClaimTravelCaseHashes(Map<String, dynamic> v) {
  final s = businessMap(v['sources'] ?? v['source_snapshot']),
      p = businessMap(v['plan']);
  payrollFactorClaimTravelPlan(p);
  if (_hash(s) != v['source_hash'] ||
      p['source_snapshot_hash'] != v['source_hash'] ||
      _hash(_omit(p, ['plan_hash', 'can_confirm', 'can_calculate'])) !=
          p['plan_hash'] ||
      _hash({'source_snapshot': s, 'plan': p}) != v['preview_hash'])
    _bad(
      'Die gemeinsame Vorschau bindet andere Originale oder einen anderen Gesamtplan.',
    );
  final x = payrollFactorClaimTravelProjections(s);
  for (final name in ['claims', 'paid_travel']) {
    final component = businessMap(p['components'][name]);
    if (_hash(x[name]) != component['source_snapshot_hash'] ||
        _hash(
              _omit(businessMap(component['plan']), [
                'plan_hash',
                'can_confirm',
                'can_calculate',
              ]),
            ) !=
            component['plan_hash'])
      _bad(
        'Ein ursprünglicher Komponentenplan oder seine tatsächliche Projektion wurde verändert.',
      );
  }
  if (v['details'] is Map)
    payrollFactorClaimTravelBindings(s, businessMap(v['details']), p);
}

void payrollFactorClaimTravelRunHashes(Map<String, dynamic> v) {
  payrollFactorClaimTravelCaseHashes(
    businessMap(v['source']?['calculation_case']),
  );
  if (_hash({'source': v['source'], 'calculation': v['calculation']}) !=
      v['preview_hash'])
    _bad(
      'Die gemeinsame Lohnvorschau wurde gegenüber den belegten Originalen verändert.',
    );
}

Map<String, dynamic> payrollFactorClaimTravelInput(
  String id,
  Map<String, dynamic> s,
  Map<String, dynamic> v, {
  Map<String, dynamic>? previous,
}) {
  if (s['travel_payment_proofs'] is! List || s['travel_settlements'] is! List)
    _bad('Die ursprünglichen Reisezahlungsquellen fehlen.');
  final claim = payrollFactorClaimsInput(id, s, {
    ...v,
    'travel_settlement_ids': [],
    'travel_payment_ids': [],
  });
  List<Map<String, dynamic>> select(
    dynamic raw,
    List<Map<String, dynamic>> available, {
    bool retainVoids = false,
  }) {
    if (raw is! List || raw.isEmpty || raw.toSet().length != raw.length)
      _bad('Alle ursprünglichen Reise- und Zahlungsfassungen auswählen.');
    final ids = raw.cast<String>().toList()..sort();
    return ids.map((id) {
      final item = available.where((r) => r['id'] == id).firstOrNull;
      if (item == null || !retainVoids && item['status'] == 'void')
        _bad('Eine ausgewählte Originalquelle ist nicht mehr verfügbar.');
      payrollFactRef(item);
      return item;
    }).toList();
  }

  final settlements = select(
    v['travel_settlement_ids'],
    businessItems(s['travel_settlements']),
  );
  final settlementRefs = _refs(settlements),
      available = businessItems(s['travel_payment_proofs']);
  final payments = select(
    v['travel_payment_ids'],
    available,
    retainVoids: true,
  );
  bool belongs(Map<String, dynamic> payment) =>
      settlementRefs.any((ref) => _same(ref, payment['settlement_ref']));
  if (payments.any((v) => !belongs(v)) ||
      !_same(_refs(payments), _refs(available.where(belongs))))
    _bad(
      'Der vollständige Zahlungspräfix muss zu genau den ausgewählten Originalreisen gehören.',
    );
  final data = <String, dynamic>{
    ...claim,
    'rule_version': payrollFactorClaimTravelRule,
    'source_contract_version': 5,
    'details': {
      ...businessMap(claim['details']),
      'travel_settlement_refs': settlementRefs,
      'travel_payment_refs': _refs(payments),
    },
  };
  if (previous != null) {
    if (previous['employee_id'] != id ||
        previous['kind'] != 'calculation_case' ||
        previous['status'] != 'active' ||
        previous['details']?['month'] != v['month'])
      _bad('Die ursprüngliche Mitarbeiter-/Monatsidentität bleibt erhalten.');
    if (previous['rule_version'] != payrollFactorClaimTravelRule) {
      if (![
            payrollFactorClaimsRule,
            _travelRule,
          ].contains(previous['rule_version']) ||
          v['confirm_unused_upgrade'] != true)
        _bad(
          'Nur den fehlenden Bestandteil eines unbenutzten ursprünglichen Faktorfalls ausdrücklich ergänzen.',
        );
      final base = businessItems(s['factor_period_facts'])
          .where((r) => r['id'] == v['period_case_id'])
          .firstOrNull;
      if (!_same(previous['sources']?['period_case'], base) ||
          (previous['source_file_ids'] as List).any(
            (id) => !(data['source_file_ids'] as List).contains(id),
          ))
        _bad(
          'Die geprüfte Faktorgrundlage und Originalunterlagen müssen erhalten bleiben.',
        );
      if (previous['rule_version'] == payrollFactorClaimsRule &&
          !_same(
            previous['details']['entitlement_case_refs'],
            data['details']['entitlement_case_refs'],
          ))
        _bad('Die bereits geprüften Anspruchsoriginale unverändert erhalten.');
      if (previous['rule_version'] == _travelRule &&
          (!_same(
                previous['details']['travel_settlement_refs'],
                data['details']['travel_settlement_refs'],
              ) ||
              !_same(
                previous['details']['travel_payment_refs'],
                data['details']['travel_payment_refs'],
              )))
        _bad(
          'Die geprüften Reiseoriginale und Zahlungsfassungen unverändert erhalten.',
        );
    } else if (previous['source_contract_version'] is! int ||
        previous['source_contract_version'] != 5) {
      _bad('Der ursprüngliche gemeinsame Quellenvertrag fehlt.');
    }
    data.addAll({
      'id': previous['id'],
      'revision': previous['revision'],
      'correction_reason': _note(v['correction_reason']),
    });
  }
  return data;
}

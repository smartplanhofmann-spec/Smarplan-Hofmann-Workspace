import 'dart:convert';

import 'package:cryptography/dart.dart';

import 'api.dart';
import 'business_payroll_facts.dart';
import 'business_session.dart' show businessMap, businessItems;

const payrollFactorClaimsRule = 'de_2026_factor_claims_month_v12';
const payrollFactorClaimsFeature = 'payroll_factor_claims';
const payrollFactorClaimsScope = 'regular_standard_factor_claims_month';
const payrollFactorClaimsCareMethod =
    'ROUND_BASE_AND_ADJUSTMENTS_SEPARATELY_GKV_2025_03_31_SECTION_3_3';

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
String _note(dynamic v) {
  if (v is! String ||
      v.trim().isEmpty ||
      v.trim().length > 3000 ||
      RegExp(r'[\x00-\x1f\x7f]').hasMatch(v))
    _bad('Die belegte Prüfung vollständig dokumentieren.');
  return v.trim();
}

bool payrollFactorClaimsBaseEligible(dynamic raw, String month) {
  final v = businessMap(raw), p = businessMap(v['plan']);
  final dates = payrollFactDates(month);
  final tax = businessItems(p['tax_periods']),
      social = businessItems(p['social_periods']);
  final employment = businessItems(p['employment_intervals']);
  return v['kind'] == 'period_case' &&
      v['status'] == 'active' &&
      p['rule_version'] == payrollFactorPeriodRule &&
      v['details']?['month'] == month &&
      tax.length == 1 &&
      social.length == 1 &&
      employment.length == 1 &&
      tax.single['lzz'] == 2 &&
      tax.single['tax_days'] == 30 &&
      social.single['days'] == 30 &&
      social.single['full_month'] == true &&
      [
        tax.single,
        social.single,
        employment.single,
      ].every((p) => p['start'] == dates.first && p['end'] == dates.last);
}

void payrollFactorClaimsPlan(Map<String, dynamic> v) {
  final f = businessMap(v['factor_parameters']);
  if (v['rule_version'] != payrollFactorClaimsRule ||
      v['source_contract_version'] != 4 ||
      v['care_contribution_method'] != payrollFactorClaimsCareMethod ||
      f['tax_factor'] is! String ||
      !RegExp(r'^0\.[0-9]{3}$').hasMatch(f['tax_factor']))
    _bad('Faktor und verbindliche Beitragsmethode fehlen im Anspruchsplan.');
  payrollFactRef(f['profile_ref']);
  if (v['can_calculate'] != true) return;
  final days = payrollFactDates(v['month']);
  for (final key in ['employment_intervals', 'tax_periods', 'social_periods']) {
    final rows = businessItems(v[key]);
    if (rows.length != 1 ||
        rows.single['start'] != days.first ||
        rows.single['end'] != days.last ||
        rows.single.containsKey('gross_minor') &&
            rows.single['gross_minor'] != v['gross_minor'])
      _bad(
        'Dieser Anspruchsfall benötigt genau einen vollständigen Faktor-Monat.',
      );
  }
  final t = businessItems(v['tax_periods']).single,
      s = businessItems(v['social_periods']).single;
  final travel = businessMap(v['travel']);
  if (t['lzz'] != 2 ||
      t['tax_days'] != 30 ||
      s['days'] != 30 ||
      s['full_month'] != true ||
      businessItems(v['entitlement_sources']).isEmpty ||
      (v['travel_source_hashes'] as List).isNotEmpty ||
      v['flat_travel_tax'] != null ||
      travel.entries.any((e) => e.value != (e.key == 'letter_m' ? false : 0)))
    _bad(
      'Vollständige Anspruchsquellen ohne zusätzlichen Reiselohn erforderlich.',
    );
}

void payrollFactorClaimsBindings(
  Map<String, dynamic> s,
  Map<String, dynamic> d,
  Map<String, dynamic> p,
) {
  final base = businessMap(s['period_case']),
      original = businessMap(base['sources']);
  if (s['rule_version'] != payrollFactorClaimsRule ||
      s['source_contract_version'] != 4 ||
      base['plan']?['rule_version'] != payrollFactorPeriodRule ||
      (d['segment_events'] as List).isNotEmpty ||
      d['thirty_day_rule'] != null ||
      d['flat_tax_decision'] != null ||
      (d['travel_settlement_refs'] as List).isNotEmpty ||
      d.containsKey('travel_payment_refs') ||
      (s['travel_sources'] as List).isNotEmpty ||
      s['flat_travel_tax'] != null ||
      (d['entitlement_case_refs'] as List).isEmpty ||
      [
        'employment_terms_refs',
        'profile_refs',
        'identity_refs',
      ].any((k) => (d[k] as List).length != 1) ||
      !payrollFactsSame(s['profiles'], original['profiles']) ||
      !payrollFactsSame(s['identities'], original['identities']) ||
      !payrollFactsSame(s['employment_terms'], [
        original['employment_terms'],
      ]) ||
      !payrollFactsSame(
        p['factor_parameters']?['profile_ref'],
        d['profile_refs'][0],
      ) ||
      p['factor_parameters']?['tax_factor'] !=
          s['profiles'][0]['profile']?['tax_factor'])
    _bad(
      'Die ursprünglichen Faktor-, Beschäftigungs- und Anspruchsnachweise wurden ersetzt.',
    );
  payrollFactorClaimsPlan(p);
}

void payrollFactorClaimsCaseHashes(Map<String, dynamic> v) {
  final s = v['sources'] ?? v['source_snapshot'], p = businessMap(v['plan']);
  payrollFactorClaimsPlan(p);
  final basis = {...p}
    ..remove('plan_hash')
    ..remove('can_confirm')
    ..remove('can_calculate');
  if (_hash(s) != v['source_hash'] ||
      p['source_snapshot_hash'] != v['source_hash'] ||
      _hash(basis) != p['plan_hash'] ||
      _hash({'source_snapshot': s, 'plan': p}) != v['preview_hash'])
    _bad(
      'Die Anspruchsvorschau bindet andere Originale oder einen veränderten Plan.',
    );
}

void payrollFactorClaimsRunHashes(Map<String, dynamic> v) {
  payrollFactorClaimsCaseHashes(businessMap(v['source']?['calculation_case']));
  if (_hash({'source': v['source'], 'calculation': v['calculation']}) !=
      v['preview_hash'])
    _bad(
      'Die Lohnvorschau wurde gegenüber den ursprünglichen Anspruchsquellen verändert.',
    );
}

Map<String, dynamic> payrollFactorClaimsInput(
  String id,
  Map<String, dynamic> s,
  Map<String, dynamic> v, {
  Map<String, dynamic>? previous,
}) {
  if (previous != null &&
      (previous['rule_version'] != payrollFactorClaimsRule ||
          previous['source_contract_version'] != 4))
    _bad(
      'Die ursprüngliche Abrechnungsregel bleibt bei einer Korrektur erhalten.',
    );
  final periods = businessItems(s['factor_period_facts']);
  final base = periods
      .where(
        (p) =>
            p['id'] == v['period_case_id'] &&
            payrollFactorClaimsBaseEligible(p, v['month']),
      )
      .firstOrNull;
  if (s['factor_period_facts'] is! List ||
      base == null ||
      [
        'employment_terms_ids',
        'profile_ids',
        'identity_ids',
      ].any((k) => v[k] is! List || v[k].length != 1) ||
      (v['segment_events'] as List? ?? []).isNotEmpty ||
      ![null, ''].contains(v['thirty_day_rule']) ||
      ![null, ''].contains(v['policy_id']) ||
      (v['travel_settlement_ids'] as List? ?? []).isNotEmpty ||
      (v['travel_payment_ids'] as List? ?? []).isNotEmpty)
    _bad(
      'Einen vollständigen ursprünglichen Faktor-Monat mit seinen Anspruchsquellen auswählen.',
    );
  List<Map<String, dynamic>> refs(dynamic items, dynamic ids, {String? kind}) {
    if (ids is! List || ids.isEmpty || ids.toSet().length != ids.length)
      _bad('Alle einschlägigen Originalquellen ausdrücklich auswählen.');
    return (List<String>.from(ids)..sort()).map((id) {
      final item = businessItems(items)
          .where(
            (v) =>
                v['id'] == id &&
                v['status'] != 'void' &&
                (kind == null || v['kind'] == kind),
          )
          .firstOrNull;
      if (item == null) _bad('Eine Originalquelle ist nicht mehr aktuell.');
      return payrollFactRef(item);
    }).toList();
  }

  final days = payrollFactDates(v['month']);
  final required =
      businessItems(s['entitlements'])
          .where(
            (e) =>
                e['status'] == 'active' &&
                e['effective_from'].compareTo(days.last) <= 0 &&
                e['effective_to'].compareTo(days.first) >= 0,
          )
          .map((e) => e['id'] as String)
          .toList()
        ..sort();
  if (required.isEmpty ||
      !payrollFactsSame(
        required,
        List<String>.from(v['entitlement_case_ids'] ?? [])..sort(),
      ))
    _bad(
      'Sämtliche aktiven Anspruchsnachweise des Monats vollständig auswählen.',
    );
  final files = v['source_file_ids'];
  if (files is! List ||
      files.isEmpty ||
      files.length > 20 ||
      files.toSet().length != files.length ||
      files.any((id) => !businessItems(s['files']).any((f) => f['id'] == id)))
    _bad('Ein bis zwanzig geschützte Personaloriginale auswählen.');
  payrollFactRecord(base, id, kind: 'period_case');
  return {
    'employee_id': id,
    'employee_revision': s['employee']['revision'],
    'kind': 'calculation_case',
    'rule_version': payrollFactorClaimsRule,
    'source_contract_version': 4,
    'details': {
      'month': v['month'],
      'period_case_ref': payrollFactRef(base),
      'employment_terms_refs': refs(
        s['facts'],
        v['employment_terms_ids'],
        kind: 'employment_terms',
      ),
      'profile_refs': refs(s['profiles'], v['profile_ids']),
      'identity_refs': refs(s['identities'], v['identity_ids']),
      'segment_events': [],
      'thirty_day_rule': null,
      'entitlement_case_refs': refs(s['entitlements'], required),
      'travel_settlement_refs': [],
      'flat_tax_decision': null,
      'verification_note': _note(v['verification_note']),
    },
    'source_file_ids': List<String>.from(files)..sort(),
    'revision': previous?['revision'] ?? 0,
    'status': 'active',
    'confirmed': true,
    if (previous != null) ...{
      'id': previous['id'],
      'correction_reason': _note(v['correction_reason']),
    },
  };
}

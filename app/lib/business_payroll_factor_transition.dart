import 'dart:convert';

import 'package:cryptography/dart.dart';

import 'api.dart';
import 'business_payroll_facts.dart';
import 'business_payroll_factor_claims.dart'
    show payrollFactorClaimsBaseEligible;
import 'business_session.dart' show businessMap, businessItems;

const payrollFactorTransitionRule = 'de_2026_factor_transition_month_v14';
const payrollFactorTransitionFeature = 'payroll_factor_transition';
const payrollFactorTransitionScope = 'regular_transition_factor_month';
Never _bad(String message) => throw ApiException(400, message);
dynamic _ordered(dynamic value) => value is List
    ? value.map(_ordered).toList()
    : value is Map
    ? {
        for (final key in value.keys.cast<String>().toList()..sort())
          key: _ordered(value[key]),
      }
    : value;
String _hash(dynamic value) => const DartSha256()
    .hashSync(utf8.encode(jsonEncode(_ordered(value))))
    .bytes
    .map((b) => b.toRadixString(16).padLeft(2, '0'))
    .join();
Map<String, dynamic> _copy(dynamic value) =>
    Map<String, dynamic>.from(jsonDecode(jsonEncode(value)) as Map);
String _note(dynamic value, [int max = 3000]) {
  if (value is! String ||
      value.trim().isEmpty ||
      value.length > max ||
      RegExp(r'[\x00-\x1f\x7f]').hasMatch(value))
    _bad('Die tatsächliche Prognose und Prüfung vollständig dokumentieren.');
  return value.trim();
}

int _amount(dynamic value) {
  if (value is! int || value < 60301 || value > 200000)
    _bad('Belegten festen Monatslohn von603,01 bis2000Euro angeben.');
  return value;
}

Map<String, dynamic> _omit(Map<String, dynamic> value, List<String> names) => {
  for (final entry in value.entries)
    if (!names.contains(entry.key)) entry.key: entry.value,
};

Map<String, dynamic> payrollFactorTransitionAssessment(dynamic raw, String id) {
  final v = businessMap(raw);
  const fields = [
    'schema_version',
    'employee_id',
    'valid_from',
    'valid_to',
    'declaration_date',
    'transition_assessment',
    'forecast_evidence_ref',
    'sole_employment_confirmed',
    'full_fixed_monthly_pay_confirmed',
    'verification_note',
  ];
  if (!payrollFactsSame(v.keys.toList()..sort(), fields.toList()..sort()) ||
      v['schema_version'] != 1 ||
      v['employee_id'] != id ||
      v['sole_employment_confirmed'] is! bool ||
      v['full_fixed_monthly_pay_confirmed'] is! bool)
    _bad('Die personengebundene vollständige Prognoseentscheidung fehlt.');
  for (final key in ['valid_from', 'valid_to', 'declaration_date'])
    payrollFactDate(v[key]);
  if ((v['valid_from'] as String).compareTo(v['valid_to']) > 0)
    _bad('Der Prognosezeitraum ist umgekehrt.');
  if (payrollFactRef(v['forecast_evidence_ref'])['revision'] != 1)
    _bad('Das unveränderte Prognoseoriginal binden.');
  final forecast = businessMap(v['transition_assessment']);
  const forecastFields = [
    'status',
    'assessed_on',
    'regular_monthly_gross_minor',
    'forecast_months',
    'foreseeable_one_off_payments',
    'note',
  ];
  if (!payrollFactsSame(
        forecast.keys.toList()..sort(),
        forecastFields.toList()..sort(),
      ) ||
      forecast['status'] != 'within_transition_area' ||
      forecast['forecast_months'] != 12 ||
      forecast['foreseeable_one_off_payments'] is! bool)
    _bad('Die tatsächliche Zwölfmonatsprognose ausdrücklich angeben.');
  _amount(forecast['regular_monthly_gross_minor']);
  payrollFactDate(forecast['assessed_on']);
  _note(forecast['note'], 2000);
  _note(v['verification_note']);
  return v;
}

void payrollFactorTransitionPlan(Map<String, dynamic> v) {
  final factor = businessMap(v['factor_parameters']);
  if (v['rule_version'] != payrollFactorTransitionRule ||
      v['source_contract_version'] != 6 ||
      factor['tax_factor'] is! String ||
      !RegExp(r'^0\.[0-9]{3}$').hasMatch(factor['tax_factor']))
    _bad('Bekannter Faktor-Midijob-Plan erforderlich.');
  payrollFactRef(factor['profile_ref']);
  final review = payrollFactorTransitionAssessment(
    v['factor_transition_assessment'],
    v['employee_id'],
  );
  if (v['can_calculate'] != true) return;
  final days = payrollFactDates(v['month']);
  for (final key in ['employment_intervals', 'tax_periods', 'social_periods']) {
    final rows = businessItems(v[key]);
    if (rows.length != 1 ||
        rows.single['start'] != days.first ||
        rows.single['end'] != days.last ||
        rows.single.containsKey('gross_minor') &&
            rows.single['gross_minor'] != v['gross_minor'])
      _bad('Genau einen vollständigen unveränderten Monatsfall verwenden.');
  }
  final tax = businessItems(v['tax_periods']).single,
      social = businessItems(v['social_periods']).single;
  final component = businessMap(v['factor_transition_component']),
      forecast = businessMap(review['transition_assessment']);
  final travel = businessMap(v['travel']);
  if (tax['lzz'] != 2 ||
      tax['tax_days'] != 30 ||
      social['days'] != 30 ||
      social['full_month'] != true ||
      businessItems(v['entitlement_sources']).isNotEmpty ||
      (v['unpaid_dates'] as List).isNotEmpty ||
      (v['travel_source_hashes'] as List).isNotEmpty ||
      v['flat_travel_tax'] != null ||
      travel.entries.any((e) => e.value != (e.key == 'letter_m' ? false : 0)) ||
      review['sole_employment_confirmed'] != true ||
      review['full_fixed_monthly_pay_confirmed'] != true ||
      forecast['foreseeable_one_off_payments'] != false ||
      (review['valid_from'] as String).compareTo(days.first) > 0 ||
      (review['valid_to'] as String).compareTo(days.last) < 0 ||
      (forecast['assessed_on'] as String).compareTo(days.first) > 0 ||
      component['scope'] != payrollFactorTransitionScope ||
      component['payroll_calculation_complete'] != true ||
      component['gross_minor'] != v['gross_minor'] ||
      component['tax_parameters']?['tax_factor'] != factor['tax_factor'] ||
      !payrollFactsSame(
        component['factor_transition_components']?['assessment'],
        forecast,
      ))
    _bad(
      'Die vollständige Faktor-/Prognoseentscheidung und der Monatslohn widersprechen sich.',
    );
  _amount(v['gross_minor']);
}

void payrollFactorTransitionBindings(
  Map<String, dynamic> s,
  Map<String, dynamic> d,
  Map<String, dynamic> p,
) {
  final base = businessMap(s['period_case']),
      original = businessMap(base['sources']);
  if (base['plan']?['rule_version'] != payrollFactorPeriodRule ||
      !payrollFactsSame(s['profiles'], original['profiles']) ||
      !payrollFactsSame(s['identities'], original['identities']) ||
      !payrollFactsSame(s['employment_terms'], [
        original['employment_terms'],
      ]) ||
      businessItems(s['profiles']).length != 1 ||
      businessItems(s['identities']).length != 1 ||
      (d['segment_events'] as List).isNotEmpty ||
      (d['entitlement_case_refs'] as List).isNotEmpty ||
      (d['travel_settlement_refs'] as List).isNotEmpty ||
      d['thirty_day_rule'] != null ||
      d['flat_tax_decision'] != null ||
      (s['travel_sources'] as List).isNotEmpty ||
      (s['entitlements'] as List).isNotEmpty ||
      !payrollFactsSame(
        d['factor_transition_assessment'],
        s['factor_transition_assessment'],
      ) ||
      !payrollFactsSame(
        d['factor_transition_assessment'],
        p['factor_transition_assessment'],
      ) ||
      !payrollFactsSame(
        p['factor_parameters']?['profile_ref'],
        (d['profile_refs'] as List).single,
      ) ||
      p['factor_parameters']?['tax_factor'] !=
          businessItems(s['profiles']).single['profile']['tax_factor'])
    _bad(
      'Die tatsächlichen Faktor-, Personen- und Prognoseoriginale wurden ersetzt.',
    );
  final review = payrollFactorTransitionAssessment(
    d['factor_transition_assessment'],
    s['employee_id'],
  );
  final ref = businessMap(review['forecast_evidence_ref']);
  final files = businessItems(s['source_files'])
      .where((f) => f['id'] == ref['id'])
      .toList();
  if (files.length != 1 ||
      files.single['purpose'] != 'personnel' ||
      files.single['employee_id'] != s['employee_id'] ||
      files.single['content_hash'] != ref['content_hash'])
    _bad('Das tatsächliche eigene Prognoseoriginal fehlt.');
  payrollFactorTransitionPlan(p);
}

void payrollFactorTransitionCaseHashes(Map<String, dynamic> value) {
  final s = businessMap(value['sources'] ?? value['source_snapshot']),
      p = businessMap(value['plan']);
  payrollFactorTransitionPlan(p);
  if (_hash(s) != value['source_hash'] ||
      p['source_snapshot_hash'] != value['source_hash'] ||
      _hash(_omit(p, ['plan_hash', 'can_confirm', 'can_calculate'])) !=
          p['plan_hash'] ||
      _hash({'source_snapshot': s, 'plan': p}) != value['preview_hash'])
    _bad(
      'Faktor-Midijob-Plan und ursprüngliche Quellen sind nicht unverändert gebunden.',
    );
  if (p['can_calculate'] != true) return;
  final actual = businessMap(businessItems(s['profiles']).single['profile']);
  final c = businessMap(
    p['factor_transition_component']?['factor_transition_components'],
  );
  final forecast = businessMap(
    s['factor_transition_assessment']?['transition_assessment'],
  );
  final projection = _omit(actual, ['tax_factor'])
    ..['special_cases'] = (actual['special_cases'] as List)
        .where((v) => v != 'tax_factor')
        .toList();
  projection['transition_assessment'] = forecast;
  if (c['actual_profile_sha256'] != _hash(actual) ||
      !payrollFactsSame(c['contribution_profile'], projection) ||
      c['contribution_profile_sha256'] != _hash(projection) ||
      !payrollFactsSame(c['assessment'], forecast) ||
      actual['regular_annual_gross_minor'] !=
          forecast['regular_monthly_gross_minor'] * 12 ||
      p['gross_minor'] != forecast['regular_monthly_gross_minor'])
    _bad(
      'Die ausdrücklich bezeichnete Beitragsprojektion hat die ursprünglichen Merkmale ersetzt.',
    );
}

void payrollFactorTransitionCalculation(Map<String, dynamic> v) {
  if (v['rule_version'] != payrollFactorTransitionRule ||
      v['source_contract_version'] != 6)
    _bad('Bekannter Faktor-Midijob-Regelstand erforderlich.');
  if (v['scope'] == 'unsupported') return;
  final c = businessMap(v['factor_transition_components']),
      tax = businessMap(c['factor_tax']);
  final financials = businessMap(c['contribution_financials']);
  if (v['scope'] != payrollFactorTransitionScope ||
      v['travel_expenses_included_in_net'] != false ||
      v['net_deductions_minor'] != 0 ||
      tax['factor'] != v['tax_parameters']?['tax_factor'] ||
      !payrollFactsSame(
        c['assessment'],
        v['period_details']?['factor_transition_assessment']?['transition_assessment'],
      ) ||
      v['transition']?['factor'] != '0.6619' ||
      !payrollFactsSame(financials['transition'], v['transition']))
    _bad(
      'Faktorsteuer und belegte Übergangsbereichsbeiträge passen nicht zusammen.',
    );
  for (final key in [
    'employee_contributions',
    'employer_contributions',
    'employee_social_total_minor',
    'employer_social_total_minor',
    'employer_levies',
    'employer_flat_tax_minor',
    'employer_total_excluding_accident_insurance_minor',
  ]) {
    if (!payrollFactsSame(financials[key], v[key]))
      _bad('Die unveränderte Beitragskomponente wurde ersetzt.');
  }
  if (tax['totals']?['LSTLZZ'] != v['individual_wage_tax_minor'] ||
      tax['totals']?['SOLZLZZ'] != v['solidarity_minor'] ||
      tax['totals']?['BK'] != v['tax_parameters']?['church_assessment_minor'])
    _bad('Die ursprüngliche Faktorsteuer wurde ersetzt.');
}

void payrollFactorTransitionRunHashes(Map<String, dynamic> v) {
  final fact = businessMap(v['source']?['calculation_case']);
  payrollFactorTransitionCaseHashes(fact);
  if (_hash({'source': v['source'], 'calculation': v['calculation']}) !=
          v['preview_hash'] ||
      v['calculation']?['scope'] != 'unsupported' &&
          !payrollFactsSame(
            _omit(businessMap(v['calculation']), ['period_details']),
            fact['plan']?['factor_transition_component'],
          ))
    _bad(
      'Der Lohnlauf entspricht nicht der unveränderten vollständigen Faktor-Midijob-Vorschau.',
    );
}

Map<String, dynamic> payrollFactorTransitionInput(
  String id,
  Map<String, dynamic> sources,
  Map<String, dynamic> values, {
  Map<String, dynamic>? previous,
}) {
  final month = values['month'] as String,
      dates = payrollFactDates(values['month']);
  final candidates = businessItems(sources['factor_period_facts'])
      .where((v) => v['id'] == values['period_case_id'])
      .toList();
  if (candidates.length != 1 ||
      !payrollFactorClaimsBaseEligible(candidates.single, month) ||
      previous != null &&
          (previous['rule_version'] != payrollFactorTransitionRule ||
              previous['source_contract_version'] != 6 ||
              previous['details']['month'] != month))
    _bad(
      'Einen ursprünglichen vollständigen Faktor-Monat auswählen; die alte Regel bleibt erhalten.',
    );
  final base = candidates.single;
  for (final key in [
    'segment_events',
    'entitlement_case_ids',
    'travel_settlement_ids',
    'travel_payment_ids',
  ])
    if (values[key] is List && (values[key] as List).isNotEmpty)
      _bad(
        'Zusätzliche Vorgänge dürfen nicht aus dem neuen Monatsfall entfernt werden.',
      );
  if (values['policy_id'] != null && values['policy_id'] != '' ||
      values['thirty_day_rule'] != null && values['thirty_day_rule'] != '')
    _bad(
      'Zusätzliche Vorgänge dürfen nicht aus dem neuen Monatsfall entfernt werden.',
    );
  List<Map<String, dynamic>> refs(String source, String key, [String? kind]) {
    final selected = values[key];
    if (selected is! List || selected.length != 1)
      _bad('Genau eine ursprüngliche Fassung auswählen.');
    final rows = businessItems(sources[source])
        .where(
          (r) =>
              r['id'] == selected.single &&
              r['status'] != 'void' &&
              (kind == null || r['kind'] == kind),
        )
        .toList();
    if (rows.length != 1) _bad('Eine ausgewählte ursprüngliche Quelle fehlt.');
    return [payrollFactRef(rows.single)];
  }

  final terms = refs('facts', 'employment_terms_ids', 'employment_terms'),
      profiles = refs('profiles', 'profile_ids'),
      identities = refs('identities', 'identity_ids');
  if (!payrollFactsSame(terms, [
        payrollFactRef(base['sources']['employment_terms']),
      ]) ||
      !payrollFactsSame(profiles, base['details']['profile_refs']) ||
      !payrollFactsSame(identities, base['details']['identity_refs']))
    _bad(
      'Die tatsächlichen ursprünglichen Monatsfassungen unverändert auswählen.',
    );
  if (businessItems(sources['entitlements']).any(
        (r) =>
            r['status'] == 'active' &&
            (r['effective_from'] as String).compareTo(dates.last) <= 0 &&
            (r['effective_to'] as String).compareTo(dates.first) >= 0,
      ) ||
      businessItems(sources['travel_settlements']).any(
        (r) =>
            r['status'] == 'approved' &&
            (r['details']['period_from'] as String).compareTo(dates.last) <=
                0 &&
            (r['details']['period_to'] as String).compareTo(dates.first) >= 0,
      ))
    _bad(
      'Weitere Ansprüche und Reisen benötigen ihren eigenen Faktor-Midijob-Vertrag.',
    );
  final review = _copy(
    payrollFactorTransitionAssessment(
      values['factor_transition_assessment'],
      id,
    ),
  );
  review['verification_note'] = _note(review['verification_note']);
  review['transition_assessment']['note'] = _note(
    review['transition_assessment']['note'],
    2000,
  );
  final files = values['source_file_ids'];
  final available = businessItems(sources['files']),
      evidence = review['forecast_evidence_ref'];
  if (files is! List ||
      files.isEmpty ||
      files.length > 20 ||
      files.toSet().length != files.length ||
      files.any((id) => !available.any((r) => r['id'] == id)) ||
      !files.contains(evidence['id']) ||
      !available.any(
        (r) =>
            r['id'] == evidence['id'] &&
            r['content_hash'] == evidence['content_hash'],
      ))
    _bad('Das eigene tatsächliche Prognoseoriginal ausdrücklich binden.');
  return {
    'employee_id': id,
    'employee_revision': sources['employee']['revision'],
    'kind': 'calculation_case',
    'rule_version': payrollFactorTransitionRule,
    'source_contract_version': 6,
    'details': {
      'month': month,
      'period_case_ref': payrollFactRef(base),
      'employment_terms_refs': terms,
      'profile_refs': profiles,
      'identity_refs': identities,
      'segment_events': [],
      'thirty_day_rule': null,
      'entitlement_case_refs': [],
      'travel_settlement_refs': [],
      'flat_tax_decision': null,
      'factor_transition_assessment': review,
      'verification_note': _note(values['verification_note']),
    },
    'source_file_ids': files.cast<String>().toList()..sort(),
    'revision': previous?['revision'] ?? 0,
    'status': 'active',
    'confirmed': true,
    if (previous != null) ...{
      'id': previous['id'],
      'correction_reason': _note(values['correction_reason']),
    },
  };
}

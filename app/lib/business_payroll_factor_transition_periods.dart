import 'dart:convert';

import 'package:cryptography/dart.dart';

import 'api.dart';
import 'business_payroll_facts.dart';
import 'business_session.dart' show businessMap, businessItems;

const payrollFactorTransitionPeriodRule =
    'de_2026_factor_transition_period_v16';
const payrollFactorTransitionPeriodFeature =
    'payroll_factor_transition_periods';
const payrollFactorTransitionPeriodScope = 'regular_transition_factor_period';

Never _bad([
  String message = 'Die ursprüngliche Faktor-/Midijob-Teilmonatsbindung ist unvollständig oder wurde verändert.',
]) => throw ApiException(400, message);
int _compare(String a, String b) {
  final x = a.runes.toList(), y = b.runes.toList();
  for (var i = 0; i < x.length && i < y.length; i++) {
    if (x[i] != y[i]) return x[i].compareTo(y[i]);
  }
  return x.length.compareTo(y.length);
}

dynamic _ordered(dynamic value) {
  if (value is List) return value.map(_ordered).toList();
  if (value is Map) {
    if (value.keys.any((k) => k is! String)) _bad();
    final keys = value.keys.cast<String>().toList()..sort(_compare);
    return {for (final key in keys) key: _ordered(value[key])};
  }
  return value;
}

bool _same(dynamic a, dynamic b) =>
    jsonEncode(_ordered(a)) == jsonEncode(_ordered(b));
String _hash(dynamic value) => const DartSha256()
    .hashSync(utf8.encode(jsonEncode(_ordered(value))))
    .bytes
    .map((b) => b.toRadixString(16).padLeft(2, '0'))
    .join();
Map<String, dynamic> _copy(dynamic value) =>
    Map<String, dynamic>.from(jsonDecode(jsonEncode(value)) as Map);
Map<String, dynamic> _omit(Map<String, dynamic> value, List<String> names) => {
  for (final e in value.entries)
    if (!names.contains(e.key)) e.key: e.value,
};
void _shape(dynamic value, String names) {
  if (value is! Map ||
      value.keys.any((k) => k is! String) ||
      !_same(value.keys.toList()..sort(), names.split(' ')..sort()))
    _bad();
}

int _integer(dynamic value, [int minimum = 0, int maximum = 1000000000000]) {
  if (value is! int || value < minimum || value > maximum) _bad();
  return value;
}

String _text(dynamic value, [int maximum = 3000]) {
  if (value is! String ||
      value.trim().isEmpty ||
      value.runes.length > maximum ||
      RegExp(r'[\x00-\x08\x0b\x0c\x0e-\x1f]').hasMatch(value))
    _bad('Die tatsächliche Teilmonatsprüfung vollständig dokumentieren.');
  final units = value.codeUnits;
  for (var i = 0; i < units.length; i++) {
    final c = units[i];
    if (c >= 0xd800 && c <= 0xdbff) {
      if (++i >= units.length || units[i] < 0xdc00 || units[i] > 0xdfff) _bad();
    } else if (c >= 0xdc00 && c <= 0xdfff) {
      _bad();
    }
  }
  return value.trim();
}

void _hashValue(dynamic value) {
  if (value is! String || !RegExp(r'^[a-f0-9]{64}$').hasMatch(value)) _bad();
}

Map<String, dynamic> payrollFactorTransitionPeriodAssessment(
  dynamic raw,
  String id,
) {
  _shape(
    raw,
    'schema_version employee_id valid_from valid_to declaration_date transition_assessment forecast_evidence_ref sole_employment_confirmed fixed_monthly_contract_confirmed contractual_30_days_confirmed verification_note',
  );
  final v = businessMap(raw);
  if (v['schema_version'] is! int ||
      v['schema_version'] != 1 ||
      v['employee_id'] != id)
    _bad();
  for (final key in [
    'sole_employment_confirmed',
    'fixed_monthly_contract_confirmed',
    'contractual_30_days_confirmed',
  ]) {
    if (v[key] is! bool) _bad();
  }
  for (final key in ['valid_from', 'valid_to', 'declaration_date']) {
    payrollFactDate(v[key]);
  }
  if ((v['valid_from'] as String).compareTo(v['valid_to']) > 0 ||
      payrollFactRef(v['forecast_evidence_ref'])['revision'] != 1)
    _bad();
  final f = businessMap(v['transition_assessment']);
  _shape(
    f,
    'status assessed_on regular_monthly_gross_minor forecast_months foreseeable_one_off_payments note',
  );
  if (f['status'] != 'within_transition_area' ||
      f['forecast_months'] is! int ||
      f['forecast_months'] != 12 ||
      f['foreseeable_one_off_payments'] is! bool)
    _bad();
  _integer(f['regular_monthly_gross_minor'], 60301, 200000);
  payrollFactDate(f['assessed_on']);
  _text(f['note'], 2000);
  _text(v['verification_note']);
  return v;
}

bool payrollFactorTransitionPeriodSelectable(dynamic raw, String month) {
  final v = businessMap(raw),
      p = businessMap(v['plan']),
      original = businessMap(v['sources']);
  final t = businessItems(p['tax_periods']),
      s = businessItems(p['social_periods']),
      e = businessItems(p['employment_intervals']);
  return v['kind'] == 'period_case' &&
      v['status'] == 'active' &&
      v['details']?['month'] == month &&
      p['rule_version'] == 'de_2026_standard_factor_period_v9' &&
      original['employment_terms']?['details']?['proration_method'] ==
          'contractual_30_days' &&
      t.length == 1 &&
      t.single['lzz'] == 4 &&
      t.single['tax_days'] is int &&
      t.single['tax_days'] >= 1 &&
      t.single['tax_days'] <= 30 &&
      s.length == 1 &&
      s.single['full_month'] == false &&
      s.single['days'] is int &&
      s.single['days'] >= 1 &&
      s.single['days'] <= 30 &&
      e.length == 1 &&
      t.single['start'] == e.single['start'] &&
      t.single['end'] == e.single['end'] &&
      s.single['start'] == e.single['start'] &&
      s.single['end'] == e.single['end'] &&
      p['blockers'] is List &&
      businessItems(p['blockers'])
          .every((r) => r['code'] == 'transition_assessment_missing');
}

Map<String, dynamic> payrollFactorTransitionPeriodPlan(dynamic raw) {
  final v = businessMap(raw);
  if (v['schema_version'] is! int ||
      v['schema_version'] != 1 ||
      v['rule_version'] != payrollFactorTransitionPeriodRule ||
      v['source_contract_version'] is! int ||
      v['source_contract_version'] != 7 ||
      !RegExp(r'^0\.[0-9]{3}$')
          .hasMatch('${v['factor_parameters']?['tax_factor']}'))
    _bad();
  payrollFactRef(v['factor_parameters']['profile_ref']);
  final review = payrollFactorTransitionPeriodAssessment(
    v['factor_transition_period_assessment'],
    v['employee_id'],
  );
  for (final key in ['plan_hash', 'rules_sha256', 'source_snapshot_hash']) {
    _hashValue(v[key]);
  }
  if (v['blockers'] is! List ||
      v['can_calculate'] is! bool ||
      v['can_confirm'] != true ||
      v['can_calculate'] != (v['blockers'] as List).isEmpty)
    _bad();
  if (v['can_calculate'] != true) {
    if (v['factor_transition_period_component'] != null) _bad();
    return v;
  }
  for (final key in [
    'employment_intervals',
    'tax_periods',
    'social_periods',
    'earnings',
    'identity_intervals',
  ]) {
    if (v[key] is! List || businessItems(v[key]).length != 1) _bad();
  }
  final dates = payrollFactDates(v['month']),
      e = businessItems(v['employment_intervals']).single,
      t = businessItems(v['tax_periods']).single,
      s = businessItems(v['social_periods']).single,
      w = businessItems(v['earnings']).single;
  if ((e['start'] as String).compareTo(dates.first) < 0 ||
      (e['end'] as String).compareTo(dates.last) > 0 ||
      (e['start'] as String).compareTo(e['end']) > 0 ||
      t['start'] != e['start'] ||
      t['end'] != e['end'] ||
      s['start'] != e['start'] ||
      s['end'] != e['end'] ||
      t['lzz'] != 4 ||
      s['full_month'] != false)
    _bad();
  final taxDays = _integer(t['tax_days'], 1, 30),
      socialDays = _integer(s['days'], 1, 30);
  if (taxDays != e['calendar_days'] ||
      w['kind'] != 'ordinary_work' ||
      w['pay_basis'] != 'monthly' ||
      w['proration_method'] != 'contractual_30_days' ||
      w['thirty_day_rule'] != 'actual_days_capped_per_claim' ||
      w['numerator'] != socialDays ||
      w['denominator'] != 30 ||
      w['gross_minor'] != v['gross_minor'] ||
      s['gross_minor'] != v['gross_minor'] ||
      t['gross_minor'] != v['gross_minor'] ||
      !_same(s['transition_ratio'], {
        'numerator': socialDays,
        'denominator': 30,
      }) ||
      v['gross_minor'] !=
          (_integer(
                        review['transition_assessment']['regular_monthly_gross_minor'],
                        60301,
                        200000,
                      ) *
                      socialDays +
                  15) ~/
              30)
    _bad();
  if (review['sole_employment_confirmed'] != true ||
      review['fixed_monthly_contract_confirmed'] != true ||
      review['contractual_30_days_confirmed'] != true ||
      review['transition_assessment']['foreseeable_one_off_payments'] !=
          false ||
      (review['valid_from'] as String).compareTo(e['start']) > 0 ||
      (review['valid_to'] as String).compareTo(e['end']) < 0 ||
      (review['transition_assessment']['assessed_on'] as String).compareTo(
            e['start'],
          ) >
          0 ||
      (review['declaration_date'] as String).compareTo(
            review['transition_assessment']['assessed_on'],
          ) <
          0 ||
      businessItems(v['entitlement_sources']).isNotEmpty ||
      (v['unpaid_dates'] as List).isNotEmpty ||
      (v['travel_source_hashes'] as List).isNotEmpty ||
      v['flat_travel_tax'] != null ||
      businessMap(v['travel']).entries
          .any((e) => e.value != (e.key == 'letter_m' ? false : 0)))
    _bad();
  final component = businessMap(v['factor_transition_period_component']);
  if (component.isEmpty ||
      component['rules_sha256'] != v['rules_sha256'] ||
      component['gross_minor'] != v['gross_minor'])
    _bad();
  payrollFactorTransitionPeriodCalculation({...component, 'period_details': v});
  return v;
}

void _sourceBindings(Map<String, dynamic> s, Map<String, dynamic> plan) {
  _shape(
    s,
    'schema_version source_contract_version rule_version employee_id month period_case employment_terms profiles identities segment_events thirty_day_rule entitlements travel_sources flat_travel_tax source_files factor_transition_period_assessment',
  );
  if (s['schema_version'] is! int ||
      s['schema_version'] != 1 ||
      s['source_contract_version'] is! int ||
      s['source_contract_version'] != 7 ||
      s['rule_version'] != payrollFactorTransitionPeriodRule ||
      s['employee_id'] != plan['employee_id'] ||
      s['month'] != plan['month'] ||
      s['thirty_day_rule'] != 'actual_days_capped_per_claim')
    _bad();
  final base = businessMap(s['period_case']),
      original = businessMap(base['sources']);
  final profiles = businessItems(s['profiles']),
      identities = businessItems(s['identities']);
  if (original.isEmpty ||
      base['plan']?['rule_version'] != 'de_2026_standard_factor_period_v9' ||
      profiles.length != 1 ||
      identities.length != 1 ||
      !_same(profiles, original['profiles']) ||
      !_same(identities, original['identities']) ||
      !_same(s['employment_terms'], [original['employment_terms']]) ||
      (s['segment_events'] as List).isNotEmpty ||
      (s['entitlements'] as List).isNotEmpty ||
      (s['travel_sources'] as List).isNotEmpty ||
      s['flat_travel_tax'] != null ||
      !_same(
        s['factor_transition_period_assessment'],
        plan['factor_transition_period_assessment'],
      ) ||
      !_same(
        plan['factor_parameters']['profile_ref'],
        payrollFactRef(profiles.single),
      ) ||
      plan['factor_parameters']['tax_factor'] !=
          profiles.single['profile']['tax_factor'])
    _bad();
  final review = payrollFactorTransitionPeriodAssessment(
    s['factor_transition_period_assessment'],
    s['employee_id'],
  );
  final files = businessItems(s['source_files'])
      .where((f) => f['id'] == review['forecast_evidence_ref']['id'])
      .toList();
  if (files.length != 1 ||
      files.single['purpose'] != 'personnel' ||
      files.single['employee_id'] != s['employee_id'] ||
      files.single['content_hash'] !=
          review['forecast_evidence_ref']['content_hash'] ||
      profiles.single['profile']['regular_annual_gross_minor'] !=
          review['transition_assessment']['regular_monthly_gross_minor'] * 12)
    _bad();
  if (plan['can_calculate'] == true &&
      (!payrollFactorTransitionPeriodSelectable(base, plan['month']) ||
          plan['gross_minor'] != base['plan']['gross_minor']))
    _bad();
}

void payrollFactorTransitionPeriodBindings(
  Map<String, dynamic> s,
  Map<String, dynamic> d,
  Map<String, dynamic> plan,
) {
  payrollFactorTransitionPeriodPlan(plan);
  _sourceBindings(s, plan);
  if (d['month'] != s['month'] ||
      !_same(d['period_case_ref'], payrollFactRef(s['period_case'])) ||
      !_same(
        d['employment_terms_refs'],
        businessItems(s['employment_terms']).map(payrollFactRef).toList(),
      ) ||
      !_same(
        d['profile_refs'],
        businessItems(s['profiles']).map(payrollFactRef).toList(),
      ) ||
      !_same(
        d['identity_refs'],
        businessItems(s['identities']).map(payrollFactRef).toList(),
      ) ||
      (d['segment_events'] as List).isNotEmpty ||
      (d['entitlement_case_refs'] as List).isNotEmpty ||
      (d['travel_settlement_refs'] as List).isNotEmpty ||
      d['flat_tax_decision'] != null ||
      d['thirty_day_rule'] != 'actual_days_capped_per_claim' ||
      !_same(
        d['factor_transition_period_assessment'],
        s['factor_transition_period_assessment'],
      ))
    _bad();
}

void payrollFactorTransitionPeriodCaseHashes(Map<String, dynamic> v) {
  final s = businessMap(v['sources'] ?? v['source_snapshot']),
      plan = businessMap(v['plan']);
  payrollFactorTransitionPeriodPlan(plan);
  _sourceBindings(s, plan);
  if (_hash(s) != v['source_hash'] ||
      plan['source_snapshot_hash'] != v['source_hash'] ||
      _hash(_omit(plan, ['plan_hash', 'can_confirm', 'can_calculate'])) !=
          plan['plan_hash'] ||
      _hash({'source_snapshot': s, 'plan': plan}) != v['preview_hash'])
    _bad();
  if (plan['can_calculate'] == true) {
    final c = businessMap(
      plan['factor_transition_period_component']['factor_transition_period_components'],
    );
    if (c['original_profile_sha256'] != _hash(s['profiles'][0]['profile']) ||
        c['original_period_plan_hash'] != s['period_case']['plan']['plan_hash'])
      _bad();
  }
  if (v['details'] is Map)
    payrollFactorTransitionPeriodBindings(s, businessMap(v['details']), plan);
}

Map<String, dynamic> payrollFactorTransitionPeriodCalculation(dynamic raw) {
  final v = businessMap(raw);
  if (v['rule_version'] != payrollFactorTransitionPeriodRule ||
      v['source_contract_version'] is! int ||
      v['source_contract_version'] != 7)
    _bad();
  const amounts = [
    'employee_social_total_minor',
    'employer_social_total_minor',
    'employer_flat_tax_minor',
    'employer_total_excluding_accident_insurance_minor',
    'individual_wage_tax_minor',
    'solidarity_minor',
    'church_tax_minor',
    'employee_tax_minor',
    'net_minor',
    'payout_minor',
    'employee_additional_payment_minor',
    'net_deductions_minor',
  ];
  if (v['scope'] == 'unsupported') {
    if (v['payroll_calculation_complete'] != false ||
        v['social_contributions_available'] != false ||
        businessItems(v['blockers']).isEmpty ||
        [
          ...amounts,
          'employee_contributions',
          'employer_contributions',
          'employer_levies',
        ].any((k) => v[k] != null))
      _bad();
    return v;
  }
  if (v['scope'] != payrollFactorTransitionPeriodScope ||
      v['payroll_calculation_complete'] != true ||
      v['social_contributions_available'] != true ||
      businessItems(v['blockers']).isNotEmpty ||
      v['travel_expenses_included_in_net'] != false ||
      v['net_deductions_minor'] != 0 ||
      v['official_system_approval'] != false ||
      v['statutory_report_status'] != 'not_transmitted')
    _bad();
  for (final key in amounts) {
    _integer(v[key], key == 'net_minor' ? -1000000000000 : 0);
  }
  _shape(
    v['employee_contributions'],
    'health_general health_additional pension unemployment care',
  );
  _shape(
    v['employer_contributions'],
    'health_general health_additional pension unemployment care',
  );
  _shape(v['employer_levies'], 'u1 u2 insolvency');
  int sum(dynamic value) =>
      businessMap(value).values.fold(0, (int a, dynamic b) => a + _integer(b));
  final component = businessMap(v['factor_transition_period_components']),
      tax = businessMap(component['factor_tax']);
  if (component.isEmpty ||
      tax.isEmpty ||
      tax['factor'] != v['tax_parameters']?['tax_factor'] ||
      !_same(
        component['assessment'],
        v['period_details']?['factor_transition_period_assessment'],
      ) ||
      !_same(component['branch_bases'], v['transition']?['branch_bases']) ||
      !_same(
        component['care_adjustments'],
        v['transition']?['care_adjustments'],
      ) ||
      v['transition']?['factor'] != '0.6619' ||
      sum(v['employee_contributions']) != v['employee_social_total_minor'] ||
      sum(v['employer_contributions']) != v['employer_social_total_minor'] ||
      v['employee_tax_minor'] !=
          v['individual_wage_tax_minor'] +
              v['solidarity_minor'] +
              v['church_tax_minor'] ||
      v['net_minor'] !=
          v['gross_minor'] -
              v['employee_social_total_minor'] -
              v['employee_tax_minor'] ||
      v['payout_minor'] != (v['net_minor'] > 0 ? v['net_minor'] : 0) ||
      v['employee_additional_payment_minor'] !=
          (v['net_minor'] < 0 ? -v['net_minor'] : 0) ||
      v['employer_total_excluding_accident_insurance_minor'] !=
          v['gross_minor'] +
              v['employer_social_total_minor'] +
              sum(v['employer_levies']))
    _bad();
  if (tax['totals']?['LSTLZZ'] != v['individual_wage_tax_minor'] ||
      tax['totals']?['SOLZLZZ'] != v['solidarity_minor'] ||
      tax['totals']?['BK'] != v['tax_parameters']?['church_assessment_minor'] ||
      tax['totals']['BK'] *
              int.parse(v['tax_parameters']['church_tax_percent']) ~/
              100 !=
          v['church_tax_minor'])
    _bad();
  final days = _integer(
        v['period_details']['tax_periods'][0]['tax_days'],
        1,
        30,
      ),
      input = businessMap(tax['inputs']);
  if (input['lzz'] != 4 ||
      input['tax_days'] != days ||
      input['gross_minor'] != v['gross_minor'] ||
      input['pap_gross_minor'] != v['gross_minor'] ~/ days ||
      input['gross_divisor'] != days ||
      input['gross_remainder_minor'] != v['gross_minor'] % days ||
      [
        'LSTLZZ',
        'SOLZLZZ',
        'BK',
      ].any((k) => _integer(tax['component'][k]) * days != tax['totals'][k]))
    _bad();
  return v;
}

void payrollFactorTransitionPeriodRunHashes(Map<String, dynamic> v) {
  final fact = businessMap(v['source']?['calculation_case']),
      c = businessMap(v['calculation']);
  payrollFactorTransitionPeriodCaseHashes(fact);
  payrollFactorTransitionPeriodCalculation(c);
  final plan = businessMap(fact['plan']);
  if (_hash({'source': v['source'], 'calculation': c}) != v['preview_hash'] ||
      c['gross_minor'] != plan['gross_minor'] ||
      c['period_details']?['plan_hash'] != plan['plan_hash'] ||
      c['period_details']?['source_snapshot_hash'] != fact['source_hash'] ||
      c['scope'] != 'unsupported' &&
          !_same(
            _omit(c, ['period_details']),
            plan['factor_transition_period_component'],
          ))
    _bad();
  for (final key in [
    'employment_intervals',
    'identity_intervals',
    'earnings',
    'tax_periods',
    'social_periods',
    'entitlement_sources',
    'unpaid_dates',
    'social_continuation',
    'travel',
    'flat_travel_tax',
    'travel_source_hashes',
    'factor_parameters',
    'factor_transition_period_assessment',
  ]) {
    if (!_same(c['period_details'][key], plan[key])) _bad();
  }
}

Map<String, dynamic> payrollFactorTransitionPeriodInput(
  String id,
  Map<String, dynamic> sources,
  Map<String, dynamic> values, {
  Map<String, dynamic>? previous,
}) {
  final month = values['month'] as String, dates = payrollFactDates(month);
  final selected = businessItems(sources['factor_period_facts'])
      .where((r) => r['id'] == values['period_case_id'])
      .toList();
  if (selected.length != 1 ||
      !payrollFactorTransitionPeriodSelectable(selected.single, month) ||
      previous != null &&
          (previous['rule_version'] != payrollFactorTransitionPeriodRule ||
              previous['source_contract_version'] != 7 ||
              previous['details']['month'] != month))
    _bad();
  final base = selected.single;
  for (final key in [
    'segment_events',
    'entitlement_case_ids',
    'travel_settlement_ids',
    'travel_payment_ids',
  ]) {
    if (values[key] is List && (values[key] as List).isNotEmpty) _bad();
  }
  if (values['policy_id'] != null && values['policy_id'] != '' ||
      values['thirty_day_rule'] != null &&
          values['thirty_day_rule'] != '' &&
          values['thirty_day_rule'] != 'actual_days_capped_per_claim')
    _bad();
  List<Map<String, dynamic>> refs(String list, String key, [String? kind]) {
    final ids = values[key];
    if (ids is! List || ids.length != 1)
      _bad('Genau eine ursprüngliche Fassung ausdrücklich auswählen.');
    final matches = businessItems(sources[list])
        .where(
          (r) =>
              r['id'] == ids.single &&
              r['status'] != 'void' &&
              (kind == null || r['kind'] == kind),
        )
        .toList();
    if (matches.length != 1) _bad();
    return [payrollFactRef(matches.single)];
  }

  final terms = refs('facts', 'employment_terms_ids', 'employment_terms'),
      profiles = refs('profiles', 'profile_ids'),
      identities = refs('identities', 'identity_ids');
  if (!_same(terms, [payrollFactRef(base['sources']['employment_terms'])]) ||
      !_same(profiles, base['details']['profile_refs']) ||
      !_same(identities, base['details']['identity_refs']))
    _bad();
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
    _bad();
  final review = _copy(
    payrollFactorTransitionPeriodAssessment(
      values['factor_transition_period_assessment'],
      id,
    ),
  );
  review['verification_note'] = _text(review['verification_note']);
  review['transition_assessment']['note'] = _text(
    review['transition_assessment']['note'],
    2000,
  );
  final rawFiles = values['source_file_ids'];
  if (rawFiles is! List ||
      rawFiles.isEmpty ||
      rawFiles.length > 20 ||
      rawFiles.toSet().length != rawFiles.length ||
      rawFiles.any(
        (id) => !businessItems(sources['files']).any((r) => r['id'] == id),
      ) ||
      !rawFiles.contains(review['forecast_evidence_ref']['id']) ||
      !businessItems(sources['files']).any(
        (r) =>
            r['id'] == review['forecast_evidence_ref']['id'] &&
            r['content_hash'] ==
                review['forecast_evidence_ref']['content_hash'],
      ))
    _bad();
  final files = rawFiles.cast<String>().toList()..sort();
  return {
    'employee_id': id,
    'employee_revision': sources['employee']['revision'],
    'kind': 'calculation_case',
    'rule_version': payrollFactorTransitionPeriodRule,
    'source_contract_version': 7,
    'details': {
      'month': month,
      'period_case_ref': payrollFactRef(base),
      'employment_terms_refs': terms,
      'profile_refs': profiles,
      'identity_refs': identities,
      'segment_events': [],
      'thirty_day_rule': 'actual_days_capped_per_claim',
      'entitlement_case_refs': [],
      'travel_settlement_refs': [],
      'flat_tax_decision': null,
      'factor_transition_period_assessment': review,
      'verification_note': _text(values['verification_note']),
    },
    'source_file_ids': files,
    'revision': previous?['revision'] ?? 0,
    'status': 'active',
    'confirmed': true,
    if (previous != null) 'id': previous['id'],
    if (previous != null)
      'correction_reason': _text(values['correction_reason']),
  };
}

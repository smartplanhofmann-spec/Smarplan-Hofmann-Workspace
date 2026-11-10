import 'business_payroll_source5_adjustment.dart';

import 'dart:convert';

import 'api.dart';
import 'business_session.dart' show businessMap;
import 'business_payroll_facts.dart' show payrollFactRef, payrollFactDate;
import 'business_payroll_multiple_case_contract.dart'
    show payrollMultipleSource;
import 'business_payroll_source5_transition.dart';

const payrollRepaymentFeature = 'payroll_source5_net_repayments';
const payrollRepaymentReviewContract = 'source5_actual_net_repayment_review_v1';
const payrollRepaymentTransitionContract = 'source5_net_repayment_v1';
const payrollRepaymentPaymentContract = 'source5_actual_net_repayment_v4';
Map<String, dynamic> payrollSettlementReview(dynamic value) =>
    value is Map && value['schema_version'] == 3
    ? payrollAdjustmentReview(value)
    : value is Map && value['schema_version'] == 2
    ? payrollRepaymentReview(value)
    : payrollPositiveSettlementReview(value);
Map<String, dynamic> payrollSettlementTransition(Map<String, dynamic> run) =>
    run['settlement_transition']?['schema_version'] == 3
    ? payrollAdjustmentTransition(run)
    : run['settlement_transition']?['schema_version'] == 2
    ? payrollRepaymentTransition(run)
    : payrollPositiveTransition(run);
Never _bad() => throw const ApiException(
  0,
  'Der tatsächliche Netto-Rückzahlungsfall ist nicht eindeutig an seine Originale gebunden.',
);
Map<String, dynamic> _copy(dynamic value) =>
    Map<String, dynamic>.from(jsonDecode(jsonEncode(value)));
bool _same(dynamic a, dynamic b) => payrollPositiveSame(a, b);
void _shape(dynamic value, String names) {
  if (value is! Map ||
      !_same(value.keys.toList()..sort(), names.split(' ')..sort()))
    _bad();
}

int _int(dynamic n, [int min = 0]) {
  if (n is! int || n < min || n > 1000000000000) _bad();
  return n;
}

void _hash(dynamic value) {
  if (value is! String || !RegExp(r'^[a-f0-9]{64}$').hasMatch(value)) _bad();
}

Map<String, dynamic> _ref(dynamic value) {
  _shape(value, 'id revision content_hash');
  final v = businessMap(value);
  if (v['id'] is! String || !RegExp(r'^[a-f0-9]{32}$').hasMatch(v['id']))
    _bad();
  _int(v['revision'], 1);
  _hash(v['content_hash']);
  return v;
}

Map<String, dynamic> payrollRepaymentReview(dynamic raw) {
  _shape(
    raw,
    'schema_version contract payments_complete remittances_complete evidence_ref',
  );
  final v = businessMap(raw);
  if (v['schema_version'] is! int ||
      v['schema_version'] != 2 ||
      v['contract'] != payrollRepaymentReviewContract ||
      v['payments_complete'] != true ||
      v['remittances_complete'] != true ||
      _ref(v['evidence_ref'])['revision'] != 1)
    _bad();
  return v;
}

Map<String, dynamic> payrollRepaymentTransition(Map<String, dynamic> run) {
  final t = businessMap(run['settlement_transition']),
      source = businessMap(run['source']),
      c = businessMap(run['calculation']);
  _shape(
    t,
    'schema_version contract employee_id month previous_run_ref prior_run_ref prior_payment_ref prior_plan_hash old_composition_hash new_composition_hash component_key event_key receipt_date running_net_minor prior_total_net_minor total_net_minor net_delta_minor repayment_minor remittance_observation settlement_review transition_hash',
  );
  if (t['schema_version'] is! int ||
      t['schema_version'] != 2 ||
      t['contract'] != payrollRepaymentTransitionContract ||
      source['source_schema_version'] is! int ||
      source['source_schema_version'] != 5 ||
      t['employee_id'] != source['employee_id'] ||
      t['month'] != source['month'] ||
      t['month'] != c['month'] ||
      c['rule_version'] != 'de_2026_multiple_oneoff_v7' ||
      c['payroll_calculation_complete'] != true)
    _bad();
  final previous = _ref(t['previous_run_ref']),
      prior = _ref(t['prior_run_ref']),
      paid = _ref(t['prior_payment_ref']);
  if (paid['revision'] != 1 ||
      previous['id'] != prior['id'] ||
      previous['revision'] < prior['revision'])
    _bad();
  if (run.containsKey('id') &&
      (run['id'] != previous['id'] ||
          run['employee_id'] != t['employee_id'] ||
          _int(run['revision'], 2) != previous['revision'] + 1))
    _bad();
  if (!_same(
    payrollRepaymentReview(t['settlement_review']),
    payrollRepaymentReview(source['input']?['settlement_review']),
  ))
    _bad();
  for (final k in [
    'prior_plan_hash',
    'old_composition_hash',
    'new_composition_hash',
    'transition_hash',
  ])
    _hash(t[k]);
  final d = businessMap(c['multiple_one_off_details']),
      events = d['receipt_events'],
      components = d['components'];
  if (events is! List ||
      events.length != 1 ||
      components is! List ||
      components.length != 1)
    _bad();
  final event = businessMap(events.single),
      component = businessMap(components.single),
      running = businessMap(c['running_calculation']);
  if (t['event_key'] != event['event_key'] ||
      t['component_key'] != component['component_key'] ||
      t['receipt_date'] != event['receipt_date'])
    _bad();
  payrollFactDate(t['receipt_date']);
  final net = _int(c['net_minor']) - _int(c['net_deductions_minor']),
      runningNet =
          _int(running['net_minor']) - _int(running['net_deductions_minor']);
  if (_int(t['running_net_minor']) != runningNet ||
      _int(t['total_net_minor']) != net ||
      _int(t['prior_total_net_minor']) <= net ||
      net < runningNet ||
      _int(t['net_delta_minor'], -1000000000000) >= 0 ||
      t['net_delta_minor'] != net - t['prior_total_net_minor'] ||
      _int(t['repayment_minor'], 1) != -t['net_delta_minor'] ||
      payrollPositiveHash(c) != t['new_composition_hash'])
    _bad();
  final o = businessMap(t['remittance_observation']);
  _shape(o, 'schema_version head_sequence entries amounts source_hash');
  final head = _int(o['head_sequence']);
  if (o['schema_version'] is! int ||
      o['schema_version'] != 1 ||
      o['entries'] is! List)
    _bad();
  var last = 0;
  final ids = <String>{};
  for (final raw in o['entries']) {
    _shape(raw, 'id revision sequence private_hash');
    final entry = businessMap(raw), sequence = _int(entry['sequence'], 1);
    if (entry['id'] is! String ||
        !RegExp(r'^[a-f0-9]{32}$').hasMatch(entry['id']) ||
        entry['revision'] is! int ||
        entry['revision'] != 1 ||
        sequence <= last ||
        sequence > head ||
        !ids.add(entry['id']))
      _bad();
    _hash(entry['private_hash']);
    last = sequence;
  }
  final amounts = businessMap(o['amounts']);
  _shape(
    amounts,
    'employee_tax employee_social employer_social employer_levies employer_flat_tax',
  );
  final ceilings = {
    'employee_tax': _int(c['employee_tax_minor']),
    'employee_social': _int(c['employee_social_total_minor']),
    'employer_social': _int(c['employer_social_total_minor']),
    'employer_flat_tax': _int(c['employer_flat_tax_minor']),
    'employer_levies': businessMap(c['employer_levies']).values
        .fold<int>(0, (n, v) => n + _int(v)),
  };
  for (final k in ceilings.keys) {
    if (_int(amounts[k]) > ceilings[k]!) _bad();
  }
  if ((o['entries'] as List).isEmpty && amounts.values.any((n) => n != 0))
    _bad();
  _hash(o['source_hash']);
  _hash(run['preview_hash']);
  if (payrollPositiveHash({...o}..remove('source_hash')) != o['source_hash'] ||
      payrollPositiveHash({...t}..remove('transition_hash')) !=
          t['transition_hash'] ||
      payrollPositiveHash({
            'source': source,
            'calculation': c,
            'settlement_transition': t,
          }) !=
          run['preview_hash'])
    _bad();
  return t;
}

Map<String, dynamic> payrollRepaymentPaymentPlan(
  Map<String, dynamic> details,
  Map<String, dynamic> run, {
  Map<String, dynamic>? prior,
  Map<String, dynamic>? archived,
}) {
  payrollMultipleSource({
    ...run,
    'can_finalize': true,
  }, businessMap(run['source']['input']));
  final t = payrollRepaymentTransition(run),
      c = run['calculation'],
      event = c['multiple_one_off_details']['receipt_events'][0];
  if (run['kind'] != 'run' ||
      run['confirmed'] != true ||
      run['status'] != 'calculation_recorded' ||
      run['accepted_scope'] != c['scope'] ||
      details['payment_source_schema_version'] is! int ||
      details['payment_source_schema_version'] != 4 ||
      details['run_id'] != run['id'] ||
      details['run_revision'] != run['revision'] ||
      !_same(details['prior_payment_ref'], t['prior_payment_ref']))
    _bad();
  final parts = details['payments'],
      allocations = details['settlement_allocations'];
  final count = prior != null
      ? (prior['details']['payments'] as List).length
      : _int(
          archived?['preserved_prior_payment_indexes'] is List
              ? (archived!['preserved_prior_payment_indexes'] as List).length
              : null,
          1,
        );
  if (parts is! List ||
      parts.length <= count ||
      parts.length > 20 ||
      allocations is! List ||
      allocations.length != parts.length)
    _bad();
  if (prior != null) {
    final old = businessMap(prior['sources']['run']),
        plan = businessMap(prior['sources']['single_payment_plan']);
    const contracts = {
      1: 'source5_single_other_payment_settlement_v1',
      2: 'source5_positive_net_correction_v2',
      3: 'source5_positive_net_correction_v3',
    };
    if (prior['kind'] != 'payment' ||
        prior['confirmed'] != true ||
        prior['employee_id'] != run['employee_id'] ||
        !_same(payrollFactRef(prior), t['prior_payment_ref']) ||
        !_same(payrollFactRef(old), t['prior_run_ref']) ||
        plan['schema_version'] is! int ||
        contracts[plan['schema_version']] != plan['contract'] ||
        plan['plan_hash'] != t['prior_plan_hash'] ||
        plan['composition_hash'] != t['old_composition_hash'] ||
        payrollPositiveHash(old['calculation']) != t['old_composition_hash'] ||
        payrollPositiveHash({...plan}..remove('plan_hash')) !=
            plan['plan_hash'] ||
        !_same(parts.take(count).toList(), prior['details']['payments']) ||
        !_same(
          allocations.take(count).toList(),
          prior['details']['settlement_allocations'],
        ) ||
        !_same(plan['payments'], prior['details']['payments']) ||
        !_same(plan['allocations'], prior['details']['settlement_allocations']))
      _bad();
    if (!_same(
          old['source']['calculation_case'],
          run['source']['calculation_case'],
        ) ||
        !_same(
          old['calculation']['running_calculation'],
          c['running_calculation'],
        ) ||
        !_same(
          old['source']['multiple_one_off_case']['sources']['calculation_source']['components'],
          run['source']['multiple_one_off_case']['sources']['calculation_source']['components'],
        ) ||
        !_same(
          old['calculation']['multiple_one_off_details']['receipt_events'],
          c['multiple_one_off_details']['receipt_events'],
        ))
      _bad();
  }
  final earliest = [
    event['receipt_date'] as String,
    ...parts.take(count).map((p) => p['paid_on'] as String),
  ]..sort();
  var repaid = 0, running = 0, bonus = 0, paidTotal = 0, oldTotal = 0;
  final seen = <String>{};
  for (var i = 0; i < parts.length; i++) {
    final p = businessMap(parts[i]);
    _shape(p, 'paid_on amount_minor payment_reference');
    final n = _int(p['amount_minor'], -1000000000000),
        date = p['paid_on'],
        text = p['payment_reference'];
    payrollFactDate(date);
    if (n == 0 ||
        !(date as String).startsWith('2026-') ||
        date.substring(0, 7).compareTo(run['source']['month']) < 0 ||
        text is! String ||
        text.trim() != text ||
        text.isEmpty ||
        text.length > 200 ||
        RegExp(r'[\x00-\x1f\x7f\uD800-\uDFFF]', unicode: true).hasMatch(text))
      _bad();
    final identity = '$date|${text.toLowerCase()}';
    if (!seen.add(identity)) _bad();
    final a = businessMap(allocations[i]);
    _shape(a, 'payment_index running_minor one_off_allocations');
    final r = _int(a['running_minor']), ones = a['one_off_allocations'];
    if (a['payment_index'] is! int ||
        a['payment_index'] != i ||
        ones is! List ||
        ones.length > 1)
      _bad();
    var b = 0;
    for (final raw in ones) {
      _shape(raw, 'event_key net_minor');
      final one = businessMap(raw);
      b = _int(one['net_minor'], -1000000000000);
      if (b == 0 ||
          one['event_key'] != event['event_key'] ||
          date.compareTo(event['receipt_date']) < 0)
        _bad();
    }
    if (r + b != n) _bad();
    running += r;
    bonus += b;
    paidTotal += n;
    if (i < count) {
      if (n <= 0) _bad();
      oldTotal += n;
    } else {
      if (n >= 0 ||
          r != 0 ||
          ones.length != 1 ||
          date.compareTo(earliest.last) < 0)
        _bad();
      repaid -= n;
    }
  }
  if (repaid != t['repayment_minor'] ||
      running != t['running_net_minor'] ||
      bonus != t['total_net_minor'] - t['running_net_minor'] ||
      paidTotal != t['total_net_minor'] ||
      oldTotal != t['prior_total_net_minor'])
    _bad();
  final plan = <String, dynamic>{
    'schema_version': 4,
    'contract': payrollRepaymentPaymentContract,
    'employee_id': run['source']['employee_id'],
    'month': run['source']['month'],
    'composition_hash': payrollPositiveHash(c),
    'event_key': event['event_key'],
    'bonus_receipt_date': event['receipt_date'],
    'running_net_minor': t['running_net_minor'],
    'one_off_net_minor': t['total_net_minor'] - t['running_net_minor'],
    'total_net_minor': t['total_net_minor'],
    'payments': parts.map((v) => _copy(v)).toList(),
    'allocations': allocations.map((v) => _copy(v)).toList(),
    'prior_settlement_refs': {
      'run': t['prior_run_ref'],
      'payment': t['prior_payment_ref'],
    },
    'preserved_prior_payment_indexes': List.generate(count, (i) => i),
    'new_payment_indexes': List.generate(
      parts.length - count,
      (i) => i + count,
    ),
    'actual_payment_created': false,
    'cash_import_created': false,
    'claim_consumption_created': false,
    'prior_total_net_minor': t['prior_total_net_minor'],
    'net_delta_minor': t['net_delta_minor'],
    'repayment_minor': repaid,
    'prior_plan_hash': t['prior_plan_hash'],
    'transition_hash': t['transition_hash'],
    'settlement_date_basis': 'actual_employee_repayment_2026',
  };
  final result = {...plan, 'plan_hash': payrollPositiveHash(plan)};
  if (archived != null && !_same(result, archived)) _bad();
  return result;
}

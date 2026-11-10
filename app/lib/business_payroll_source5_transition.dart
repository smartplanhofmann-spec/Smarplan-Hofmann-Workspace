import 'dart:convert';

import 'package:cryptography/dart.dart';

import 'api.dart';
import 'business_payroll_facts.dart' show payrollFactRef, payrollFactDate;
import 'business_session.dart' show businessMap;

const payrollPositiveCorrectionFeature = 'payroll_source5_positive_corrections';
const payrollPositiveCorrectionContract = 'source5_positive_net_correction_v1';
const payrollPositivePaymentContract = 'source5_positive_net_correction_v2';
const payrollPositivePaymentDatesFeature = 'payroll_source5_payment_dates';
const payrollPositivePaymentDatesContract =
    'source5_positive_net_correction_v3';

Never _bad() => throw const ApiException(
  0,
  'Die positive Nachzahlung ist nicht eindeutig an ihre ursprüngliche Abrechnung und Zahlung gebunden.',
);

dynamic _ordered(dynamic value) => value is List
    ? value.map(_ordered).toList()
    : value is Map
    ? {
        for (final k in value.keys.map((k) => '$k').toList()..sort())
          k: _ordered(value[k]),
      }
    : value;

String payrollPositiveHash(dynamic value) => const DartSha256()
    .hashSync(utf8.encode(jsonEncode(_ordered(value))))
    .bytes
    .map((b) => b.toRadixString(16).padLeft(2, '0'))
    .join();

bool payrollPositiveSame(dynamic a, dynamic b) =>
    jsonEncode(_ordered(a)) == jsonEncode(_ordered(b));

void _shape(dynamic value, String keys) {
  if (value is! Map ||
      !payrollPositiveSame(
        value.keys.toList()..sort(),
        keys.split(' ')..sort(),
      ))
    _bad();
}

int _integer(dynamic value, [int minimum = 0]) {
  if (value is! int || value < minimum || value > 1000000000000) _bad();
  return value;
}

void _hash(dynamic value) {
  if (value is! String || !RegExp(r'^[a-f0-9]{64}$').hasMatch(value)) _bad();
}

Map<String, dynamic> _ref(dynamic value) {
  _shape(value, 'id revision content_hash');
  return payrollFactRef(value);
}

Map<String, dynamic> payrollPositiveSettlementReview(dynamic raw) {
  _shape(
    raw,
    'schema_version payments_complete remittances_complete evidence_ref',
  );
  final review = businessMap(raw), evidence = _ref(review['evidence_ref']);
  if (review['schema_version'] is! int ||
      review['schema_version'] != 1 ||
      review['payments_complete'] != true ||
      review['remittances_complete'] != true ||
      evidence['revision'] != 1)
    _bad();
  return review;
}

/// Only the additive Source5 correction branch has this object. Legacy run
/// and preview hashes retain their original source/calculation-only basis.
Map<String, dynamic> payrollPositiveTransition(Map<String, dynamic> run) {
  final t = businessMap(run['settlement_transition']);
  _shape(
    t,
    'schema_version contract employee_id month previous_run_ref prior_run_ref prior_payment_ref prior_plan_hash old_composition_hash new_composition_hash component_key event_key receipt_date running_net_minor prior_total_net_minor total_net_minor additional_net_minor remittance_observation settlement_review transition_hash',
  );
  final source = businessMap(run['source']),
      c = businessMap(run['calculation']);
  if (t['schema_version'] is! int ||
      t['schema_version'] != 1 ||
      t['contract'] != payrollPositiveCorrectionContract ||
      source['source_schema_version'] is! int ||
      source['source_schema_version'] != 5 ||
      t['employee_id'] is! String ||
      !RegExp(r'^[a-f0-9]{32}$').hasMatch(t['employee_id']) ||
      t['employee_id'] != source['employee_id'] ||
      t['month'] != source['month'] ||
      t['month'] != c['month'] ||
      c['rule_version'] != 'de_2026_multiple_oneoff_v7' ||
      c['payroll_calculation_complete'] != true)
    _bad();
  final previous = _ref(t['previous_run_ref']),
      prior = _ref(t['prior_run_ref']);
  final priorPayment = _ref(t['prior_payment_ref']);
  if (priorPayment['revision'] != 1 ||
      !payrollPositiveSame(
        payrollPositiveSettlementReview(t['settlement_review']),
        payrollPositiveSettlementReview(source['input']?['settlement_review']),
      ))
    _bad();
  if (previous['id'] != prior['id'] ||
      previous['revision'] < prior['revision'] ||
      run.containsKey('id') &&
          (run['id'] != previous['id'] ||
              run['employee_id'] != t['employee_id'] ||
              run['revision'] is! int ||
              run['revision'] != previous['revision'] + 1))
    _bad();
  for (final key in [
    'prior_plan_hash',
    'old_composition_hash',
    'new_composition_hash',
    'transition_hash',
  ])
    _hash(t[key]);
  final details = businessMap(c['multiple_one_off_details']),
      events = details['receipt_events'],
      components = details['components'];
  if (events is! List ||
      events.length != 1 ||
      components is! List ||
      components.length != 1)
    _bad();
  final event = businessMap(events.single),
      component = businessMap(components.single);
  if (t['component_key'] is! String ||
      !RegExp(r'^[a-f0-9]{32}$').hasMatch(t['component_key']) ||
      t['event_key'] is! String ||
      !RegExp(r'^[a-f0-9]{32}$').hasMatch(t['event_key']) ||
      t['component_key'] != component['component_key'] ||
      t['event_key'] != event['event_key'] ||
      t['receipt_date'] != event['receipt_date'])
    _bad();
  payrollFactDate(t['receipt_date']);
  final running = businessMap(c['running_calculation']),
      due = _integer(c['net_minor']) - _integer(c['net_deductions_minor']),
      runningDue =
          _integer(running['net_minor']) -
          _integer(running['net_deductions_minor']);
  if (_integer(t['running_net_minor']) != runningDue ||
      _integer(t['total_net_minor']) != due ||
      _integer(t['prior_total_net_minor'], 1) <= runningDue ||
      _integer(t['additional_net_minor'], 1) !=
          due - t['prior_total_net_minor'] ||
      payrollPositiveHash(c) != t['new_composition_hash'])
    _bad();
  final observation = businessMap(t['remittance_observation']);
  _shape(
    observation,
    'schema_version head_sequence entries amounts source_hash',
  );
  final head = _integer(observation['head_sequence']);
  if (observation['schema_version'] is! int ||
      observation['schema_version'] != 1 ||
      observation['entries'] is! List)
    _bad();
  var last = 0;
  final ids = <String>{};
  for (final raw in observation['entries']) {
    _shape(raw, 'id revision sequence private_hash');
    final e = businessMap(raw), sequence = _integer(e['sequence'], 1);
    if (e['id'] is! String ||
        !RegExp(r'^[a-f0-9]{32}$').hasMatch(e['id']) ||
        e['revision'] is! int ||
        e['revision'] != 1 ||
        sequence <= last ||
        sequence > head ||
        !ids.add(e['id']))
      _bad();
    _hash(e['private_hash']);
    last = sequence;
  }
  final amounts = businessMap(observation['amounts']);
  _shape(
    amounts,
    'employee_tax employee_social employer_social employer_levies employer_flat_tax',
  );
  final levies = businessMap(c['employer_levies']);
  final maximum = {
    'employee_tax': _integer(c['employee_tax_minor']),
    'employee_social': _integer(c['employee_social_total_minor']),
    'employer_social': _integer(c['employer_social_total_minor']),
    'employer_levies': levies.values.fold<int>(
      0,
      (sum, n) => sum + _integer(n),
    ),
    'employer_flat_tax': _integer(c['employer_flat_tax_minor']),
  };
  for (final key in maximum.keys) {
    if (_integer(amounts[key]) > maximum[key]!) _bad();
  }
  _hash(observation['source_hash']);
  if (payrollPositiveHash({...observation}..remove('source_hash')) !=
          observation['source_hash'] ||
      payrollPositiveHash({...t}..remove('transition_hash')) !=
          t['transition_hash'])
    _bad();
  _hash(run['preview_hash']);
  if (run['preview_hash'] !=
      payrollPositiveHash({
        'source': source,
        'calculation': c,
        'settlement_transition': t,
      }))
    _bad();
  return t;
}

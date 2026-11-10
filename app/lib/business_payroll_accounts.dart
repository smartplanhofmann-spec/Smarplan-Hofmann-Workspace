import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:cryptography/cryptography.dart';

import 'business_payroll_facts.dart' show payrollFactRef, payrollFactDate;
import 'business_payroll_multiple_case_contract.dart'
    show payrollMultipleSource;
import 'business_payroll_source5_transition.dart';
import 'business_payroll_source5_repayment.dart';

import 'api.dart';
import 'business_session.dart';
import 'business_payroll_oneoff_case_contract.dart' show payrollOneOffSource;
import 'business_payroll_calculation_case_contract.dart'
    show payrollCompositeSource;
import 'business_widgets.dart';
import 'design.dart';

const payrollAccountKinds = {
  'identity': 'Stamm- und Steuermerkmalsnachweis',
  'payment': 'Tatsächliche Lohnzahlung',
  'carryover': 'Belegter Monatsvortrag',
};
const payrollIdentityLabels = {
  'given_name': 'Vorname laut Nachweis',
  'family_name': 'Familienname laut Nachweis',
  'date_of_birth': 'Geburtsdatum',
  'address_line': 'Straße und Hausnummer',
  'postal_code': 'Postleitzahl',
  'city': 'Wohnort',
  'country_code': 'Land',
  'tax_id': 'Persönliche Steuer-ID (11 Ziffern)',
  'employer_name': 'Arbeitgebername laut Nachweis',
  'employer_address': 'Vollständige Arbeitgeberanschrift',
  'employer_tax_number': 'Arbeitgeber-Steuernummer',
  'employment_from': 'Beschäftigungsbeginn',
  'employment_to': 'Beschäftigungsende, falls bekannt',
  'tax_source': 'Grundlage der Steuermerkmale',
  'tax_source_date': 'Datum des Steuermerkmalsnachweises',
  'valid_from': 'Gültig ab',
  'valid_to': 'Gültig bis',
  'tax_allowance_yearly_minor': 'Jährlicher Freibetrag (€)',
  'tax_addition_yearly_minor': 'Jährlicher Hinzurechnungsbetrag (€)',
  'religion_code': 'Religionsmerkmal laut Nachweis',
};
const payrollCarryLabels = {
  'gross_minor': 'Brutto laut früherer Monatsabrechnung (€)',
  'expected_net_minor': 'Netto laut früherer Monatsabrechnung (€)',
  'expected_employee_tax_minor':
      'Arbeitnehmersteuern laut früherer Monatsabrechnung (€)',
  'expected_employee_social_total_minor':
      'Arbeitnehmerbeiträge laut früherer Monatsabrechnung (€)',
  'expected_employer_social_total_minor':
      'Arbeitgeberbeiträge laut früherer Monatsabrechnung (€)',
  'expected_employer_total_minor': 'Arbeitgeberaufwand ohne Unfallversicherung laut früherer Monatsabrechnung (€)',
};
const _detailsLabels = {
  'profile_id': 'Profilquelle',
  'profile_revision': 'Profilfassung',
  'identity_id': 'Stammnachweis',
  'identity_revision': 'Stammnachweisfassung',
  'run_id': 'Monatslauf',
  'run_revision': 'Monatsfassung',
  'month': 'Vortragsmonat',
  'status': 'Vortragsstatus',
  'tax_free_payments_minor': 'Gesonderte steuerfreie Bezüge',
  'tax_free_basis': 'Grundlage steuerfreier Bezüge',
  'standard_case_confirmed': 'Unterstützten Standardfall geprüft',
};
String _amount(dynamic value) {
  if (value is! int) return '';
  return '${value < 0 ? '-' : ''}${value.abs() ~/ 100}.${(value.abs() % 100).toString().padLeft(2, '0')}';
}

String _money(dynamic value) =>
    value is int ? businessMoney(_amount(value)) : 'Nicht ermittelt';
String _ref(Map<String, dynamic> value) =>
    '${value['id']}@${value['revision']}';
Map<String, dynamic> _copy(dynamic value) =>
    businessMap(jsonDecode(jsonEncode(value)));
dynamic _ordered(dynamic value) => value is List
    ? value.map(_ordered).toList()
    : value is Map
    ? {
        for (final key in value.keys.map((k) => '$k').toList()..sort())
          key: _ordered(value[key]),
      }
    : value;
bool _same(dynamic left, dynamic right) =>
    jsonEncode(_ordered(left)) == jsonEncode(_ordered(right));
int payrollAccountMinor(dynamic value, {bool signed = false}) {
  var text = '${value ?? ''}'.trim().replaceAll(',', '.');
  final negative = signed && text.startsWith('-');
  if (negative) text = text.substring(1);
  if (!RegExp(r'^\d{1,10}(?:\.\d{1,2})?$').hasMatch(text))
    throw const FormatException(
      'Genauen belegten EUR-Betrag ausdrücklich eingeben, auch bekannte 0.',
    );
  final parts = text.split('.'),
      amount =
          int.parse(parts[0]) * 100 +
          int.parse((parts.length == 2 ? parts[1] : '').padRight(2, '0'));
  if (amount > 1000000000000)
    throw const FormatException('Betrag außerhalb des unterstützten Bereichs.');
  return negative ? -amount : amount;
}

Never _multipleFail(String text) => throw ApiException(0, text);
int _multipleInteger(dynamic n, [int min = 0]) {
  if (n is! int || n < min || n > 1000000000000)
    _multipleFail('Die Nettozuordnung benötigt belegte ganze Centbeträge.');
  return n;
}

void _multipleKeys(dynamic raw, List<String> names) {
  if (raw is! Map || !_same(raw.keys.toList()..sort(), [...names]..sort()))
    _multipleFail(
      'Die genaue Form des ursprünglichen Zahlungsnachweises fehlt.',
    );
}

Map<String, dynamic> _multipleSettlementV1(
  Map<String, dynamic> details,
  Map<String, dynamic> run, {
  Map<String, dynamic>? prior,
  Map<String, dynamic>? archived,
  bool actualPositiveDates = false,
}) {
  payrollMultipleSource({
    ...run,
    'can_finalize': true,
  }, businessMap(run['source']['input']));
  final c = run['calculation'],
      event = c['multiple_one_off_details']['receipt_events'][0],
      parts = details['payments'],
      allocations = details['settlement_allocations'];
  if (run['kind'] != 'run' ||
      run['confirmed'] != true ||
      run['status'] != 'calculation_recorded' ||
      run['accepted_scope'] != c['scope'] ||
      details['run_id'] != run['id'] ||
      details['run_revision'] != run['revision'] ||
      details['payment_source_schema_version'] is! int ||
      details['payment_source_schema_version'] != 1 ||
      !details.containsKey('prior_payment_ref') ||
      parts is! List ||
      parts.isEmpty ||
      parts.length > 20 ||
      allocations is! List ||
      allocations.length != parts.length)
    _multipleFail(
      'Die bestätigte Monatsgruppe und sämtliche tatsächlichen Zahlungsteile müssen eindeutig gebunden sein.',
    );
  final running = _multipleInteger(
        c['running_calculation']['net_minor'] -
            c['running_calculation']['net_deductions_minor'],
      ),
      total = _multipleInteger(c['net_minor'] - c['net_deductions_minor']),
      bonus = _multipleInteger(total - running, 1);
  var runningSum = 0, bonusSum = 0;
  final seen = <String>{};
  for (var i = 0; i < parts.length; i++) {
    final p = parts[i], a = allocations[i];
    _multipleKeys(p, ['paid_on', 'amount_minor', 'payment_reference']);
    _multipleInteger(p['amount_minor'], 1);
    final date = payrollFactDate(p['paid_on'])!,
        reference = p['payment_reference'];
    if (!date.startsWith('2026-') ||
        date.substring(0, 7).compareTo(run['source']['month']) < 0 ||
        reference is! String ||
        reference.isEmpty ||
        reference.trim() != reference ||
        reference.length > 200 ||
        RegExp(r'[\x00-\x1f\x7f]').hasMatch(reference) ||
        !seen.add('$date|${reference.toLowerCase()}'))
      _multipleFail(
        'Jeder Zahlungsteil benötigt seinen tatsächlichen Tag und einen eindeutigen unveränderten Originalverweis.',
      );
    _multipleKeys(a, ['payment_index', 'running_minor', 'one_off_allocations']);
    final current = _multipleInteger(a['running_minor']);
    if (a['payment_index'] is! int ||
        a['payment_index'] != i ||
        a['one_off_allocations'] is! List ||
        (a['one_off_allocations'] as List).length > 1)
      _multipleFail(
        'Jeder Zahlungsteil benötigt genau seine eigene Nettozuordnung.',
      );
    var b = 0;
    if ((a['one_off_allocations'] as List).isNotEmpty) {
      final o = a['one_off_allocations'][0];
      _multipleKeys(o, ['event_key', 'net_minor']);
      b = _multipleInteger(o['net_minor'], 1);
      if (o['event_key'] != event['event_key'] ||
          (actualPositiveDates
              ? date.compareTo(event['receipt_date']) < 0
              : date != event['receipt_date']))
        _multipleFail(
          'Die Bonuszahlung gehört zu genau ihrem ursprünglichen Zuflussereignis und Tag.',
        );
    }
    if (current + b != p['amount_minor'])
      _multipleFail(
        'Laufender Nettoanteil und Bonus müssen exakt den tatsächlichen Zahlungsteil ergeben.',
      );
    runningSum += current;
    bonusSum += b;
  }
  if (runningSum != running || bonusSum != bonus)
    _multipleFail(
      'Laufendes Netto und Bonus müssen jeweils vollständig erfüllt werden.',
    );
  var count = 0;
  Map<String, dynamic>? refs;
  if (details['prior_payment_ref'] != null && archived != null) {
    refs = businessMap(archived['prior_settlement_refs']);
    if (archived['preserved_prior_payment_indexes'] is! List)
      _multipleFail('Die früheren Zahlungsteile fehlen.');
    count = (archived['preserved_prior_payment_indexes'] as List).length;
    for (final k in ['run', 'payment']) {
      _multipleKeys(refs[k], ['id', 'revision', 'content_hash']);
      payrollFactRef(refs[k]);
    }
    if (!_same(refs['payment'], details['prior_payment_ref']) ||
        refs['run']['id'] != run['id'] ||
        refs['run']['revision'] >= run['revision'] ||
        count < 1 ||
        count >= parts.length ||
        parts
                .take(count)
                .fold<int>(
                  0,
                  (n, p) => n + _multipleInteger(p['amount_minor']),
                ) !=
            running ||
        List.generate(count, (i) => i).any(
          (i) =>
              allocations[i]['running_minor'] != parts[i]['amount_minor'] ||
              (allocations[i]['one_off_allocations'] as List).isNotEmpty,
        ))
      _multipleFail(
        'Der archivierte Übernahmestand muss sämtliche früheren laufenden Originalteile eindeutig erhalten.',
      );
  } else if (details['prior_payment_ref'] != null) {
    if (prior == null ||
        prior['kind'] != 'payment' ||
        prior['employee_id'] != run['employee_id'] ||
        !_same(payrollFactRef(prior), details['prior_payment_ref']))
      _multipleFail(
        'Den bereits bezahlten ursprünglichen laufenden Lohn ausdrücklich auswählen.',
      );
    payrollAccountRecord(prior, run['employee_id'], kind: 'payment');
    final old = businessMap(prior['sources']?['run']);
    if (old['source']?['source_schema_version'] != 3 ||
        old['id'] != run['id'] ||
        old['revision'] >= run['revision'] ||
        prior['details']['run_id'] != old['id'] ||
        prior['details']['run_revision'] != old['revision'] ||
        !_same(old['calculation'], c['running_calculation']) ||
        !_same(
          old['source']['calculation_case'],
          run['source']['calculation_case'],
        ))
      _multipleFail(
        'Die vorherige Zahlung muss genau dieselbe unveränderte laufende Rechnung belegen.',
      );
    count = (prior['details']['payments'] as List).length;
    if (count < 1 ||
        count >= parts.length ||
        !_same(parts.take(count).toList(), prior['details']['payments']) ||
        (prior['details']['payments'] as List).fold<int>(
              0,
              (n, p) => n + _multipleInteger(p['amount_minor']),
            ) !=
            running ||
        List.generate(count, (i) => i).any(
          (i) =>
              allocations[i]['running_minor'] != parts[i]['amount_minor'] ||
              (allocations[i]['one_off_allocations'] as List).isNotEmpty,
        ))
      _multipleFail(
        'Alle bezahlten laufenden Originalteile bleiben mit Betrag, Tag, Referenz und Reihenfolge unverändert.',
      );
    refs = {'run': payrollFactRef(old), 'payment': payrollFactRef(prior)};
  }
  return {
    'schema_version': 1,
    'contract': 'source5_single_other_payment_settlement_v1',
    'employee_id': run['employee_id'],
    'month': run['source']['month'],
    'event_key': event['event_key'],
    'bonus_receipt_date': event['receipt_date'],
    'running_net_minor': running,
    'one_off_net_minor': bonus,
    'total_net_minor': total,
    'payments': jsonDecode(jsonEncode(parts)),
    'allocations': jsonDecode(jsonEncode(allocations)),
    'prior_settlement_refs': refs,
    'preserved_prior_payment_indexes': List.generate(count, (i) => i),
    'new_payment_indexes': List.generate(
      parts.length - count,
      (i) => i + count,
    ),
    'actual_payment_created': false,
    'cash_import_created': false,
    'claim_consumption_created': false,
  };
}

Map<String, dynamic> _positiveSettlement(
  Map<String, dynamic> details,
  Map<String, dynamic> run, {
  Map<String, dynamic>? prior,
  Map<String, dynamic>? archived,
}) {
  final transition = payrollPositiveTransition(run);
  final version = details['payment_source_schema_version'];
  if (details['payment_source_schema_version'] is! int ||
      ![2, 3].contains(version) ||
      !_same(details['prior_payment_ref'], transition['prior_payment_ref']))
    _multipleFail(
      'Die zusätzliche Zahlung benötigt genau ihre gebundene vorherige Zahlungsfassung.',
    );
  final base = _multipleSettlementV1(
    {...details, 'payment_source_schema_version': 1, 'prior_payment_ref': null},
    run,
    actualPositiveDates: version == 3,
  );
  final parts = details['payments'] as List,
      allocations = details['settlement_allocations'] as List;
  int count;
  if (archived != null) {
    final indexes = archived['preserved_prior_payment_indexes'];
    if (indexes is! List)
      _multipleFail('Die früheren Originalzahlungsteile fehlen.');
    count = indexes.length;
    if (!_same(archived['prior_settlement_refs'], {
          'run': transition['prior_run_ref'],
          'payment': transition['prior_payment_ref'],
        }) ||
        archived['prior_plan_hash'] != transition['prior_plan_hash'])
      _multipleFail(
        'Die ursprüngliche Zahlung und der Übergang wurden ersetzt.',
      );
  } else {
    if (prior == null)
      _multipleFail('Die letzte tatsächlich belegte Zahlung auswählen.');
    payrollAccountRecord(prior, run['employee_id'], kind: 'payment');
    final old = businessMap(prior['sources']?['run']),
        oldPlan = businessMap(prior['sources']?['single_payment_plan']);
    if (version == 2 && oldPlan['schema_version'] == 3)
      _multipleFail(
        'Ein später datierter Zahlungspräfix benötigt weiterhin Zahlungsfassung 3.',
      );
    if (old['source']?['source_schema_version'] != 5 ||
        !_same(payrollFactRef(prior), transition['prior_payment_ref']) ||
        !_same(payrollFactRef(old), transition['prior_run_ref']) ||
        oldPlan['plan_hash'] != transition['prior_plan_hash'] ||
        payrollPositiveHash(old['calculation']) !=
            transition['old_composition_hash'] ||
        !_same(
          old['calculation']?['running_calculation'],
          run['calculation']['running_calculation'],
        ) ||
        !_same(
          old['source']?['calculation_case'],
          run['source']['calculation_case'],
        ))
      _multipleFail(
        'Die Nachzahlung muss denselben unveränderten laufenden Lohn und die letzte tatsächliche Source5-Zahlung erhalten.',
      );
    final oldDetails = businessMap(prior['details']);
    count = (oldDetails['payments'] as List).length;
    if (parts.length <= count ||
        !_same(parts.take(count).toList(), oldDetails['payments']) ||
        !_same(
          allocations.take(count).toList(),
          oldDetails['settlement_allocations'],
        ))
      _multipleFail(
        'Frühere Beträge, Zahlungstage, Originalverweise und Nettozuordnungen müssen vollständig unverändert bleiben.',
      );
    final oldEvent =
            old['calculation']['multiple_one_off_details']['receipt_events'][0],
        event =
            run['calculation']['multiple_one_off_details']['receipt_events'][0];
    if (!_same(oldEvent, event) ||
        oldPlan['total_net_minor'] != transition['prior_total_net_minor'])
      _multipleFail(
        'Bruttoereignis und bereits erfüllte ursprüngliche Nettoschuld dürfen nicht ausgetauscht werden.',
      );
  }
  if (count < 1 || count >= parts.length)
    _multipleFail(
      'Die Nachzahlung benötigt erhaltene Originale und mindestens einen neuen Zahlungsteil.',
    );
  final previousTotal = parts
          .take(count)
          .fold<int>(
            0,
            (sum, p) => sum + _multipleInteger(p['amount_minor'], 1),
          ),
      previousRunning = allocations
          .take(count)
          .fold<int>(0, (sum, a) => sum + _multipleInteger(a['running_minor'])),
      additional = parts
          .skip(count)
          .fold<int>(
            0,
            (sum, p) => sum + _multipleInteger(p['amount_minor'], 1),
          );
  final notBefore = [
    transition['receipt_date'] as String,
    ...parts.take(count).map((p) => p['paid_on'] as String),
  ].reduce((a, b) => a.compareTo(b) >= 0 ? a : b);
  if (previousTotal != transition['prior_total_net_minor'] ||
      previousRunning != transition['running_net_minor'] ||
      additional != transition['additional_net_minor'] ||
      allocations
          .skip(count)
          .any(
            (a) =>
                a['running_minor'] != 0 ||
                (a['one_off_allocations'] as List).length != 1,
          ) ||
      parts
          .skip(count)
          .any(
            (p) => version == 3
                ? (p['paid_on'] as String).compareTo(notBefore) < 0
                : p['paid_on'] != transition['receipt_date'],
          ))
    _multipleFail(
      'Nur die positive zusätzliche Nettoschuld am ursprünglichen Bonus-Zuflusstag darf ergänzt werden.',
    );
  return {
    ...base,
    'schema_version': version,
    'contract': version == 3
        ? payrollPositivePaymentDatesContract
        : payrollPositivePaymentContract,
    if (version == 3) 'settlement_date_basis': 'actual_positive_transfer_2026',
    'prior_settlement_refs': {
      'run': transition['prior_run_ref'],
      'payment': transition['prior_payment_ref'],
    },
    'preserved_prior_payment_indexes': List.generate(count, (i) => i),
    'new_payment_indexes': List.generate(
      parts.length - count,
      (i) => i + count,
    ),
    'prior_total_net_minor': transition['prior_total_net_minor'],
    'additional_net_minor': transition['additional_net_minor'],
    'prior_plan_hash': transition['prior_plan_hash'],
    'transition_hash': transition['transition_hash'],
  };
}

Map<String, dynamic> _multipleSettlement(
  Map<String, dynamic> details,
  Map<String, dynamic> run, {
  Map<String, dynamic>? prior,
  Map<String, dynamic>? archived,
}) {
  if (details['payment_source_schema_version'] == 4) {
    final plan = payrollRepaymentPaymentPlan(
      details,
      run,
      prior: prior,
      archived: archived,
    );
    return {...plan}
      ..remove('composition_hash')
      ..remove('plan_hash');
  }
  if ([2, 3].contains(details['payment_source_schema_version']))
    return _positiveSettlement(details, run, prior: prior, archived: archived);
  if (run.containsKey('settlement_transition'))
    _multipleFail(
      'Dieser positive Korrekturlauf benötigt den eigenen Zahlungsnachweis der Version 2.',
    );
  return _multipleSettlementV1(details, run, prior: prior, archived: archived);
}

Future<String> _multipleHash(dynamic value) async =>
    (await Sha256().hash(utf8.encode(jsonEncode(_ordered(value))))).bytes
        .map((v) => v.toRadixString(16).padLeft(2, '0'))
        .join();
Future<Map<String, dynamic>> payrollMultiplePaymentPlan(
  Map<String, dynamic> details,
  Map<String, dynamic> run, {
  Map<String, dynamic>? prior,
}) async {
  final plan = _multipleSettlement(details, run, prior: prior);
  plan['composition_hash'] = await _multipleHash(run['calculation']);
  return {...plan, 'plan_hash': await _multipleHash(plan)};
}

void _multiplePaymentRecord(Map<String, dynamic> value) {
  final run = businessMap(value['sources']['run']),
      plan = businessMap(value['sources']['single_payment_plan']);
  if (run['employee_id'] != value['employee_id'] ||
      !RegExp(r'^[a-f0-9]{64}$').hasMatch('${plan['composition_hash']}') ||
      !RegExp(r'^[a-f0-9]{64}$').hasMatch('${plan['plan_hash']}'))
    _multipleFail('Der originale Nettozuordnungsplan fehlt.');
  final expected = _multipleSettlement(
    businessMap(value['details']),
    run,
    archived: plan,
  );
  if (!_same(
    {...plan, 'composition_hash': null, 'plan_hash': null},
    {...expected, 'composition_hash': null, 'plan_hash': null},
  ))
    _multipleFail(
      'Der Zahlungsplan widerspricht seinen tatsächlichen Originalteilen, Tagen oder Erfüllungsbeträgen.',
    );
  if ([2, 3, 4].contains(value['details']['payment_source_schema_version']) &&
      (plan['composition_hash'] != payrollPositiveHash(run['calculation']) ||
          plan['plan_hash'] !=
              payrollPositiveHash({...plan}..remove('plan_hash'))))
    _multipleFail(
      'Der ursprüngliche zusätzliche Zahlungsplan besteht die Prüfsummenprüfung nicht.',
    );
}

Map<String, dynamic> payrollAccountRecord(
  dynamic raw,
  String employee, {
  String? kind,
}) {
  final value = businessMap(raw);
  if (value['employee_id'] != employee ||
      !payrollAccountKinds.containsKey(value['kind']) ||
      kind != null && value['kind'] != kind ||
      !RegExp(r'^[a-f0-9]{32}$').hasMatch('${value['id']}') ||
      !RegExp(r'^[a-f0-9]{64}$').hasMatch('${value['content_hash']}') ||
      value['revision'] is! int ||
      value['revision'] < 1 ||
      value['details'] is! Map ||
      value['confirmed'] != true)
    throw const ApiException(
      0,
      'Der Lohnkontonachweis ist nicht eindeutig an Mitarbeiter und Vorgang gebunden.',
    );
  if (value['kind'] == 'identity' &&
      value['details'].containsKey('identity_source_schema_version')) {
    final details = businessMap(value['details']),
        profile = businessMap(value['sources']?['profile']);
    final values = businessMap(profile['profile']);
    if (details['identity_source_schema_version'] is! int ||
        details['identity_source_schema_version'] != 2 ||
        values['employment_kind'] != 'minijob' ||
        values['minijob_tax'] != 'individual' ||
        values['health_insurance'] != 'statutory_other' ||
        details['tax_source'] != 'elstam_imported' ||
        details['profile_id'] != profile['id'] ||
        details['profile_revision'] != profile['revision'] ||
        details['tax_allowance_yearly_minor'] != 0 ||
        details['tax_addition_yearly_minor'] != 0 ||
        details['religion_code'] != 'none')
      throw const ApiException(
        0,
        'Der individuelle Minijob-Identitätsnachweis besitzt keine eindeutige Originalbindung.',
      );
  }
  if (value['kind'] == 'payment') {
    final details = businessMap(value['details']),
        sources = businessMap(value['sources']);
    final multiple =
        details.containsKey('payment_source_schema_version') ||
        details.containsKey('settlement_allocations') ||
        details.containsKey('prior_payment_ref') ||
        sources.containsKey('single_payment_plan') ||
        sources['run']?['calculation']?['rule_version'] ==
            'de_2026_multiple_oneoff_v7';
    if (multiple && sources['run']?['source']?['source_schema_version'] != 5)
      _multipleFail(
        'Die neue Zahlungszuordnung benötigt ihre vollständige ursprüngliche Source5-Monatsfassung.',
      );
  }
  if (value['kind'] == 'payment' &&
      value['sources']?['run']?['source']?['source_schema_version'] == 5)
    _multiplePaymentRecord(value);
  if (value['kind'] == 'payment' &&
      value['sources']?['run']?['source']?['source_schema_version'] == 4) {
    final run = businessMap(value['sources']['run']);
    payrollOneOffSource({
      ...run,
      'can_finalize': true,
    }, businessMap(run['source']['input']));
    final payments = value['details']['payments'];
    final due =
        run['calculation']['net_minor'] -
        run['calculation']['net_deductions_minor'];
    if (run['employee_id'] != employee ||
        run['id'] != value['details']['run_id'] ||
        run['revision'] != value['details']['run_revision'] ||
        run['confirmed'] != true ||
        run['accepted_scope'] != run['calculation']['scope'] ||
        payments is! List ||
        payments.isEmpty ||
        payments.any(
          (p) =>
              p is! Map ||
              p['amount_minor'] is! int ||
              p['amount_minor'] == 0 ||
              p['paid_on'] !=
                  run['calculation']['one_off_details']['receipt_date'],
        ) ||
        payments.fold<int>(0, (sum, p) => sum + (p['amount_minor'] as int)) !=
            due) {
      throw const ApiException(
        0,
        'Der Einmalbezugs-Zahlungsnachweis muss seine bestätigte Monatsfassung, den tatsächlichen Zuflusstag und den vollständigen Barbetrag belegen.',
      );
    }
  }
  if (value['kind'] == 'payment' &&
      value['details']['payments'] is List &&
      (value['details']['payments'] as List).isEmpty) {
    final run = businessMap(value['sources']?['run']);
    if (run['employee_id'] != employee ||
        run['id'] != value['details']['run_id'] ||
        run['revision'] != value['details']['run_revision'] ||
        !payrollAccountNoPaymentDue(run)) {
      throw const ApiException(
        0,
        'Der Nachweis ohne Zahlungsteile benötigt seine vollständig geprüfte Nullnetto-Monatsfassung.',
      );
    }
  }
  return value;
}

bool payrollAccountNoPaymentDue(dynamic raw) {
  final run = businessMap(raw);
  if (run['source']?['source_schema_version'] != 3) return false;
  if (run['kind'] != 'run' ||
      !RegExp(r'^[a-f0-9]{32}$').hasMatch('${run['id']}') ||
      !RegExp(r'^[a-f0-9]{64}$').hasMatch('${run['content_hash']}') ||
      run['revision'] is! int ||
      run['revision'] < 1 ||
      run['confirmed'] != true ||
      run['status'] != 'calculation_recorded' ||
      run['source']?['input']?['employee_id'] != run['employee_id'] ||
      run['calculation']?['payroll_calculation_complete'] != true ||
      run['accepted_scope'] != run['calculation']?['scope']) {
    throw const ApiException(
      0,
      'Keine vollständig bestätigte Quellenfassung für den Nullnetto-Nachweis.',
    );
  }
  payrollCompositeSource({
    ...run,
    'can_finalize': true,
  }, businessMap(run['source']['input']));
  return run['calculation']['net_minor'] -
          run['calculation']['net_deductions_minor'] ==
      0;
}

String? payrollAccountPaymentStatus(
  Map<String, dynamic> month,
  dynamic records,
  String employee,
) {
  final account = businessMap(month['wage_account']),
      source3 = month['source_refs']?['calculation_case'] != null;
  if (!account.containsKey('payment_status')) {
    if (source3 &&
        account['payment_ref'] != null &&
        (account['payments'] is! List || (account['payments'] as List).isEmpty))
      throw const ApiException(
        0,
        'Der belegte Gesamtlohn-Zahlungsstand fehlt.',
      );
    return null;
  }
  if (!source3 ||
      ![
        'no_payment_due',
        'payments_evidenced',
      ].contains(account['payment_status']) ||
      account['payments'] is! List) {
    throw const ApiException(
      0,
      'Der ausgewiesene Nettozahlungsstand ist nicht belegt.',
    );
  }
  final evidence = businessItems(records)
      .where(
        (r) => _same({
          for (final k in ['id', 'revision', 'content_hash']) k: r[k],
        }, account['payment_ref']),
      )
      .firstOrNull;
  if (evidence == null)
    throw const ApiException(
      0,
      'Die ursprüngliche Lohnkonto-Zahlungsfassung fehlt.',
    );
  payrollAccountRecord(evidence, employee, kind: 'payment');
  final run = businessMap(evidence['sources']?['run']),
      zeroDue = payrollAccountNoPaymentDue(run),
      calc = businessMap(month['calculation']),
      payments = businessItems(account['payments']);
  final due = calc['net_minor'] - calc['net_deductions_minor'];
  if (run['id'] != month['run_id'] ||
      run['revision'] != month['revision'] ||
      run['content_hash'] != month['content_hash'] ||
      !_same(run['calculation'], calc) ||
      !_same(evidence['details']['payments'], payments) ||
      account['payable_minor'] != due ||
      account['net_deductions_minor'] != calc['net_deductions_minor'] ||
      payments.any(
        (p) => p['amount_minor'] is! int || p['amount_minor'] == 0,
      ) ||
      payments.fold<int>(0, (n, p) => n + (p['amount_minor'] as int)) != due ||
      (account['payment_status'] == 'no_payment_due'
          ? (!zeroDue || payments.isNotEmpty)
          : payments.isEmpty)) {
    throw const ApiException(
      0,
      'Der Nettozahlungsstand widerspricht dem tatsächlichen Monatslauf und seinen Originalen.',
    );
  }
  return account['payment_status'];
}

void Function(dynamic) payrollAccountReceiptValidator(
  Map<String, dynamic> body,
  Map<String, dynamic> original, {
  Map<String, dynamic>? previous,
  Map<String, dynamic>? sourceEvidence,
}) {
  final frozen = _copy(body),
      file = _copy(original),
      old = previous == null ? null : _copy(previous),
      proof = sourceEvidence == null ? null : _copy(sourceEvidence);
  return (dynamic raw) {
    final value = payrollAccountRecord(
      raw,
      frozen['employee_id'],
      kind: frozen['kind'],
    );
    if (value['revision'] != frozen['revision'] + 1 ||
        old != null && value['id'] != old['id'] ||
        value['previous_hash'] != old?['content_hash'] ||
        value['correction_reason'] != (frozen['correction_reason'] ?? '') ||
        !_same(value['details'], frozen['details']) ||
        [
          'id',
          'employee_id',
          'sha256',
          'content_hash',
        ].any((key) => value['source_file']?[key] != file[key]))
      throw const ApiException(
        0,
        'Die Empfangsbestätigung passt nicht zu den ausdrücklich geprüften Lohnkontonachweisen. Der ursprüngliche Auftrag bleibt offen.',
      );
    for (final name in ['profile', 'identity', 'run']) {
      if (frozen['details']['${name}_id'] != null &&
          (value['sources']?[name]?['id'] != frozen['details']['${name}_id'] ||
              value['sources']?[name]?['revision'] !=
                  frozen['details']['${name}_revision'] ||
              value['sources']?[name]?['employee_id'] != frozen['employee_id']))
        throw const ApiException(
          0,
          'Die eingefrorene Nachweisquelle passt nicht zum ausgewählten Stand.',
        );
    }
    if (proof != null)
      for (final entry in proof.entries)
        if (!_same(value['sources']?[entry.key], entry.value))
          throw const ApiException(
            0,
            'Der zurückgegebene Quelleninhalt stimmt nicht mit der geprüften Fassung überein.',
          );
  };
}

Map<String, dynamic> payrollAccountDetails(
  String kind,
  Map<String, dynamic> values,
  Map<String, List<Map<String, dynamic>>> sources, {
  int count = 0,
  bool paymentDates = false,
  bool repayments = false,
}) {
  if (!payrollAccountKinds.containsKey(kind))
    throw const FormatException('Unbekannte Lohnkontonachweisart.');
  final details = <String, dynamic>{};
  void choose(String name, String collection) {
    final source = sources[collection]
        ?.where((r) => _ref(r) == values['${name}_ref'])
        .firstOrNull;
    if (source == null)
      throw const FormatException(
        'Die belegte Quellfassung ausdrücklich auswählen.',
      );
    details['${name}_id'] = source['id'];
    details['${name}_revision'] = source['revision'];
  }

  if (values['standard_case_confirmed'] != true)
    throw const FormatException(
      'Den unterstützten Standardfall ausdrücklich bestätigen.',
    );
  if (kind == 'identity') {
    choose('profile', 'profiles');
    for (final key in payrollIdentityLabels.keys)
      details[key] = key.endsWith('_minor')
          ? payrollAccountMinor(values[key])
          : key == 'employment_to' && (values[key] == null || values[key] == '')
          ? null
          : '${values[key] ?? ''}'.trim();
    if (details['country_code'] != 'DE' ||
        ![
          'elstam_imported',
          'tax_office_certificate',
          'flat_minijob_evidence',
        ].contains(details['tax_source']))
      throw const FormatException(
        'Land und tatsächliche Herkunft der Steuermerkmale ausdrücklich wählen.',
      );
    if (values['identity_scope'] == 'individual_minijob') {
      final profile = sources['profiles']!.singleWhere(
        (r) =>
            r['id'] == details['profile_id'] &&
            r['revision'] == details['profile_revision'],
      )['profile'];
      if (profile['employment_kind'] != 'minijob' ||
          profile['minijob_tax'] != 'individual' ||
          profile['health_insurance'] != 'statutory_other' ||
          details['tax_source'] != 'elstam_imported' ||
          details['tax_allowance_yearly_minor'] != 0 ||
          details['tax_addition_yearly_minor'] != 0 ||
          details['religion_code'] != 'none')
        throw const FormatException(
          'Der individuelle Minijob benötigt das tatsächliche Minijobprofil und einen ELStAM-Nachweis ohne zusätzliche Merkmale.',
        );
      details['identity_source_schema_version'] = 2;
    } else if (values['identity_scope'] != null &&
        values['identity_scope'] != 'legacy') {
      throw const FormatException(
        'Den Umfang des Identitätsnachweises ausdrücklich wählen.',
      );
    }
  } else {
    choose('identity', 'identities');
    if (kind == 'payment')
      choose('run', 'runs');
    else {
      choose('profile', 'profiles');
      details['month'] = values['month'];
      for (final key in payrollCarryLabels.keys)
        details[key] = payrollAccountMinor(
          values[key],
          signed: key == 'expected_net_minor',
        );
      if (!['active', 'void'].contains(values['status']))
        throw const FormatException('Vortragsstatus ausdrücklich wählen.');
      details['status'] = values['status'];
    }
    final run = kind == 'payment'
        ? sources['runs']
              ?.where((r) => _ref(r) == values['run_ref'])
              .firstOrNull
        : null;
    final zeroDue = run != null && payrollAccountNoPaymentDue(run);
    if (count < (zeroDue ? 0 : 1) || count > 20)
      throw const FormatException(
        'Ein bis 20 belegte Zahlungsteile erfassen; nur eine bestätigte Nullnetto-Berechnung erlaubt keine Zahlungsteile.',
      );
    details['payments'] = [
      for (var i = 0; i < count; i++)
        {
          'paid_on': values['paid_on_$i'],
          'amount_minor': payrollAccountMinor(
            values['amount_$i'],
            signed: true,
          ),
          'payment_reference': '${values['reference_$i'] ?? ''}'.trim(),
        },
    ];
    if ((details['payments'] as List).any((p) => p['amount_minor'] == 0))
      throw const FormatException(
        'Eine tatsächliche Zahlung oder Nachzahlung muss einen Betrag ungleich null haben.',
      );
    if (run?['source']?['source_schema_version'] == 5) {
      final payments = sources['payments'] ?? [],
          selected = values['prior_payment_ref'];
      if (selected != 'none' && !payments.any((p) => _ref(p) == selected))
        throw const FormatException(
          'Vorherige tatsächliche Zahlung ausdrücklich beurteilen.',
        );
      final prior = payments.where((p) => _ref(p) == selected).firstOrNull;
      final event =
          run!['calculation']['multiple_one_off_details']['receipt_events'][0];
      final repayment = run['settlement_transition']?['schema_version'] == 2;
      if (repayment && !repayments)
        throw const ApiException(
          403,
          'Die aktuelle Freigabe für belegte Netto-Rückzahlungen fehlt.',
        );
      details['payment_source_schema_version'] = repayment
          ? 4
          : run.containsKey('settlement_transition')
          ? (paymentDates ? 3 : 2)
          : 1;
      details['prior_payment_ref'] = prior == null
          ? null
          : payrollFactRef(prior);
      details['settlement_allocations'] = [
        for (var i = 0; i < count; i++)
          {
            'payment_index': i,
            'running_minor': payrollAccountMinor(values['running_$i']),
            'one_off_allocations':
                payrollAccountMinor(values['bonus_$i'], signed: repayment) == 0
                ? []
                : [
                    {
                      'event_key': event['event_key'],
                      'net_minor': payrollAccountMinor(
                        values['bonus_$i'],
                        signed: repayment,
                      ),
                    },
                  ],
          },
      ];
      if (run.containsKey('settlement_transition') &&
          paymentDates &&
          !repayment) {
        final allocations = details['settlement_allocations'] as List;
        final parts = details['payments'] as List;
        final requiresDates =
            prior?['sources']?['single_payment_plan']?['schema_version'] == 3 ||
            List.generate(count, (i) => i).any(
              (i) =>
                  (allocations[i]['one_off_allocations'] as List).isNotEmpty &&
                  parts[i]['paid_on'] != event['receipt_date'],
            );
        details['payment_source_schema_version'] = requiresDates ? 3 : 2;
      }
      try {
        _multipleSettlement(details, run, prior: prior);
      } on ApiException catch (error) {
        if ([2, 3].contains(details['payment_source_schema_version'])) {
          throw FormatException(error.message);
        }
        rethrow;
      }
    }
    details['tax_free_payments_minor'] = payrollAccountMinor(
      values['tax_free_payments_minor'],
    );
    details['tax_free_basis'] = '${values['tax_free_basis'] ?? ''}'.trim();
  }
  details['standard_case_confirmed'] = true;
  return details;
}

class BusinessPayrollAccountsPage extends StatefulWidget {
  const BusinessPayrollAccountsPage({
    super.key,
    required this.session,
    required this.employee,
    required this.onOriginal,
  });
  final BusinessSession session;
  final Map<String, dynamic> employee;
  final Future<void> Function(Map<String, dynamic>) onOriginal;
  @override
  State<BusinessPayrollAccountsPage> createState() =>
      _BusinessPayrollAccountsPageState();
}

class _BusinessPayrollAccountsPageState
    extends State<BusinessPayrollAccountsPage>
    with WidgetsBindingObserver {
  BusinessSession get session => widget.session;
  String get employeeId => widget.employee['id'];
  String get key => 'payroll-account-$employeeId';
  Map<String, dynamic> employee = {};
  List<Map<String, dynamic>> records = [], history = [];
  String? actorId, error, message;
  Object? generation;
  bool loading = false, busy = false, denied = false, foreground = true;
  BuildContext? editorContext;
  String? editingKind;
  int epoch = 0;
  bool get available =>
      session.hasFeature('payroll_wage_account') &&
      session.hasModule('payroll_accounts') &&
      session.projectId == null;
  bool get readable =>
      foreground &&
      !denied &&
      available &&
      (session.can('personnel.read') ||
          actorId == employee['user_id'] && session.can('time.own'));
  bool writable(String kind) =>
      readable &&
      session.can('personnel.read') &&
      session.canWrite(
        kind == 'identity' ? 'personnel.write' : 'personnel.approve',
      ) &&
      session.sectionEnabled('personnel');
  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    employee = _copy(widget.employee);
    generation = session.generation;
    session.addListener(changed);
    load();
  }

  @override
  void dispose() {
    epoch++;
    WidgetsBinding.instance.removeObserver(this);
    session.removeListener(changed);
    super.dispose();
  }

  void changed() {
    if (!mounted) return;
    if (!readable ||
        generation != session.generation ||
        editingKind != null && !writable(editingKind!)) {
      clearPrivate();
      generation = session.generation;
    }
    setState(() {});
  }

  void clearPrivate() {
    epoch++;
    records = [];
    history = [];
    error = message = null;
    loading = false;
    final editor = editorContext;
    editorContext = null;
    if (editor != null)
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (editor.mounted && ModalRoute.of(editor)?.isCurrent == true)
          Navigator.of(editor).pop();
      });
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state == AppLifecycleState.hidden ||
        state == AppLifecycleState.paused) {
      foreground = false;
      if (mounted) setState(clearPrivate);
    } else if (state == AppLifecycleState.resumed && mounted) {
      setState(() => foreground = true);
    }
  }

  @override
  void didUpdateWidget(covariant BusinessPayrollAccountsPage oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.employee['id'] != employeeId ||
        !identical(oldWidget.session, session)) {
      oldWidget.session.removeListener(changed);
      clearPrivate();
      employee = _copy(widget.employee);
      actorId = null;
      denied = false;
      generation = session.generation;
      session.addListener(changed);
      load();
    }
  }

  Future<void> privateEditor({
    required BuildContext context,
    required WidgetBuilder builder,
  }) async {
    await showDialog<void>(
      context: context,
      builder: (dialog) {
        editorContext = dialog;
        return builder(dialog);
      },
    );
    editorContext = null;
  }

  void fail(Object e, {int? expectedEpoch}) {
    if (!mounted ||
        !foreground ||
        expectedEpoch != null && expectedEpoch != epoch)
      return;
    setState(() {
      if (e is ApiException && [401, 403, 404].contains(e.status)) {
        denied = true;
        records = [];
        history = [];
      }
      error = e is ApiException
          ? e.message
          : e is FormatException
          ? e.message
          : 'Der Nachweis konnte nicht geprüft werden.';
    });
  }

  Future<void> load({bool refresh = false}) async {
    if (refresh) {
      await session.load();
      denied = false;
    }
    if (!mounted || !available) return;
    final captured = ++epoch;
    setState(() {
      loading = true;
      error = null;
    });
    try {
      final me = businessMap(await session.api.call('/api/me')),
          people = businessItems(await session.read('/employees'));
      final person = people.where((p) => p['id'] == employeeId).firstOrNull;
      if (person == null)
        throw const ApiException(403, 'Mitarbeiter ist nicht freigegeben.');
      if (!mounted || captured != epoch) return;
      actorId = me['id'];
      employee = person;
      if (!readable)
        throw const ApiException(
          403,
          'Lohnkontonachweise sind nicht freigegeben.',
        );
      final page = businessMap(
        await session.read('/payroll/account-records?employee_id=$employeeId'),
      );
      if (page['employee_id'] != employeeId)
        throw const ApiException(
          0,
          'Nachweise gehören nicht zum ausgewählten Mitarbeiter.',
        );
      final items = businessItems(page)
          .map((r) => payrollAccountRecord(r, employeeId))
          .toList();
      if (mounted && captured == epoch && readable)
        setState(() => records = items);
    } catch (e) {
      if (mounted && captured == epoch) fail(e);
    } finally {
      if (mounted && captured == epoch) setState(() => loading = false);
    }
  }

  Future<void> fresh({String? kind}) async {
    await session.load();
    if (!mounted ||
        session.error != null ||
        !readable ||
        kind != null && !writable(kind))
      throw const ApiException(
        403,
        'Aktuelle Mitarbeiter- und Lohnkontorechte fehlen.',
      );
    final page = businessMap(
      await session.read('/payroll/account-records?employee_id=$employeeId'),
    );
    if (page['employee_id'] != employeeId)
      throw const ApiException(
        0,
        'Der Mitarbeiterbezug konnte nicht bestätigt werden.',
      );
    for (final item in businessItems(page))
      payrollAccountRecord(item, employeeId);
  }

  Future<void> repeat() async {
    if (busy) return;
    final captured = epoch;
    setState(() => busy = true);
    try {
      await session.repeatPayrollAccountCommand(employeeId);
      if (!mounted || !readable || captured != epoch) return;
      await load();
      if (mounted)
        setState(() => message = 'Der ursprüngliche Nachweis ist bestätigt.');
    } catch (e) {
      fail(e, expectedEpoch: captured);
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  Future<void> openHistory(Map<String, dynamic> value) async {
    final captured = epoch;
    try {
      await fresh();
      final opening = session.generation,
          page = businessItems(
            await session.read(
              '/payroll/account-records/${value['id']}/history',
            ),
          );
      for (final r in page) {
        payrollAccountRecord(r, employeeId, kind: value['kind']);
        if (r['id'] != value['id'])
          throw const ApiException(
            0,
            'Historie gehört nicht zum gewählten Nachweis.',
          );
      }
      if (mounted &&
          readable &&
          opening == session.generation &&
          captured == epoch)
        setState(() => history = page);
    } catch (e) {
      fail(e, expectedEpoch: captured);
    }
  }

  Future<void> openOriginal(Map<String, dynamic> value) async {
    final captured = epoch;
    try {
      await fresh();
      if (mounted && readable && captured == epoch) {
        await widget.onOriginal(businessMap(value['source_file']));
      }
    } catch (e) {
      fail(e, expectedEpoch: captured);
    }
  }

  Future<void> edit(String kind, [Map<String, dynamic>? previous]) async {
    if (busy || !writable(kind) || session.pending(key)) return;
    final captured = epoch;
    editingKind = kind;
    try {
      await fresh(kind: kind);
      await fresh(kind: kind);
      if (kind == 'identity' &&
          previous?['details']?['identity_source_schema_version'] == 2 &&
          !session.hasFeature('payroll_individual_minijob'))
        throw const ApiException(
          403,
          'Die Freigabe für die ursprüngliche individuelle Minijobidentität fehlt.',
        );
      final opening = session.generation;
      final pages = await Future.wait(
        [
          '/payroll/profiles',
          '/payroll/runs',
          '/payroll/account-records',
          '/personnel/files',
        ].map((path) => session.read('$path?employee_id=$employeeId')),
      );
      for (final page in pages)
        if (businessMap(page)['employee_id'] != employeeId ||
            businessItems(page).any((row) => row['employee_id'] != employeeId))
          throw const ApiException(0, 'Quellen gehören nicht zum Mitarbeiter.');
      if (!mounted ||
          !readable ||
          captured != epoch ||
          opening != session.generation)
        return;
      final sources = {
            'profiles': businessItems(pages[0]),
            'runs': businessItems(pages[1]),
            'payments': businessItems(pages[2])
                .where((r) => r['kind'] == 'payment')
                .toList(),
            'identities': businessItems(pages[2])
                .where((r) => r['kind'] == 'identity')
                .toList(),
          },
          files = businessItems(pages[3])
              .where((f) => f['purpose'] == 'personnel')
              .toList();
      if (previous != null)
        for (final entry in {
          'profile': 'profiles',
          'run': 'runs',
          'identity': 'identities',
        }.entries) {
          final source = businessMap(previous['sources']?[entry.key]);
          if (source.isNotEmpty &&
              !sources[entry.value]!.any((s) => _ref(s) == _ref(source)))
            sources[entry.value]!.add(source);
        }
      Map<String, dynamic>? selectedRun;
      if (kind == 'payment') {
        String? chosen;
        await privateEditor(
          context: context,
          builder: (_) => BusinessEditor(
            session: session,
            title: 'Abgerechneten Lauf für den Lohnkontonachweis auswählen',
            readPermission: 'personnel.read',
            writePermission: 'personnel.approve',
            readAllowed: () =>
                readable && captured == epoch && opening == session.generation,
            fields: [
              BusinessField(
                'run_ref',
                'Abgeschlossene Monatsberechnung',
                type: BusinessInput.choice,
                required: true,
                choices: {
                  '': 'Quelle ausdrücklich auswählen',
                  for (final run in sources['runs']!)
                    _ref(
                      run,
                    ): '${run['source']?['month']} · Fassung ${run['revision']}',
                },
              ),
            ],
            initial: {
              'run_ref': previous?['details']['run_id'] == null
                  ? ''
                  : '${previous!['details']['run_id']}@${previous['details']['run_revision']}',
            },
            saveLabel: 'Ausgewählten Lauf prüfen',
            onSave: (values) async {
              await fresh(kind: kind);
              final run = sources['runs']!
                  .where((v) => _ref(v) == values['run_ref'])
                  .firstOrNull;
              if (run == null)
                throw const FormatException(
                  'Die konkrete angenommene Monatsfassung fehlt.',
                );
              payrollAccountNoPaymentDue(run);
              chosen = values['run_ref'];
            },
          ),
        );
        if (chosen == null ||
            !mounted ||
            !readable ||
            opening != session.generation)
          return;
        selectedRun = sources['runs']!.firstWhere((v) => _ref(v) == chosen);
      }
      final multiple = selectedRun?['source']?['source_schema_version'] == 5;
      final positiveCorrection =
          selectedRun?.containsKey('settlement_transition') == true;
      final repayment =
          selectedRun?['settlement_transition']?['schema_version'] == 2;
      final positivePaymentDates =
          positiveCorrection &&
          !repayment &&
          (previous != null
              ? previous['details']['payment_source_schema_version'] == 3
              : session.hasFeature(payrollPositivePaymentDatesFeature));
      final transition = positiveCorrection
          ? payrollSettlementTransition(selectedRun!)
          : null;
      if (positiveCorrection &&
          (!session.hasFeature(payrollPositiveCorrectionFeature) ||
              repayment && !session.hasFeature(payrollRepaymentFeature) ||
              positivePaymentDates &&
                  !session.hasFeature(payrollPositivePaymentDatesFeature) ||
              !session.hasModule('payroll_multiple_cases')))
        throw const ApiException(
          409,
          'Der Server unterstützt diese belegte zusätzliche Nettozahlung aktuell nicht.',
        );
      Map<String, dynamic>? prior;
      String priorKey = 'none';
      if (multiple) {
        final options = sources['payments']!
            .where(
              (p) =>
                  p['sources']?['run']?['source']?['source_schema_version'] ==
                      (positiveCorrection ? 5 : 3) &&
                  p['details']['run_id'] == selectedRun!['id'] &&
                  p['details']['run_revision'] < selectedRun['revision'] &&
                  (!positiveCorrection ||
                      _same(
                        payrollFactRef(p),
                        transition!['prior_payment_ref'],
                      )),
            )
            .toList();
        String? chosen;
        await privateEditor(
          context: context,
          builder: (_) => BusinessEditor(
            session: session,
            title: positiveCorrection
                ? 'Bisherige tatsächliche Zahlung prüfen'
                : 'Vorherige laufende Zahlung prüfen',
            readPermission: 'personnel.read',
            writePermission: 'personnel.approve',
            readAllowed: () =>
                readable && captured == epoch && opening == session.generation,
            fields: [
              BusinessField(
                'prior_payment_ref',
                positiveCorrection
                    ? 'Letzte tatsächlich belegte Monatsgruppenzahlung'
                    : 'Bereits belegte laufende Originalzahlung',
                type: BusinessInput.choice,
                required: true,
                choices: {
                  '': 'Tatsächlichen Zahlungsstand ausdrücklich wählen',
                  if (!positiveCorrection)
                    'none': 'Keine bereits belegte laufende Zahlung',
                  for (final p in options)
                    _ref(
                      p,
                    ): 'Lohnfassung ${p['details']['run_revision']} · Nachweisfassung ${p['revision']}',
                },
              ),
            ],
            saveLabel: positiveCorrection
                ? 'Bisherigen Zahlungsursprung festhalten'
                : 'Laufenden Zahlungsursprung festhalten',
            onSave: (v) async {
              await fresh(kind: kind);
              if (positiveCorrection && v['prior_payment_ref'] == 'none' ||
                  v['prior_payment_ref'] != 'none' &&
                      !options.any((p) => _ref(p) == v['prior_payment_ref']))
                throw const FormatException(
                  'Die tatsächliche Zahlungsfassung auswählen.',
                );
              chosen = v['prior_payment_ref'];
            },
          ),
        );
        if (chosen == null ||
            !mounted ||
            !readable ||
            captured != epoch ||
            opening != session.generation)
          return;
        priorKey = chosen!;
        prior = options.where((p) => _ref(p) == chosen).firstOrNull;
      }
      final preserved = prior == null
          ? 0
          : (prior['details']['payments'] as List).length;
      final zeroDue =
          selectedRun != null && payrollAccountNoPaymentDue(selectedRun);
      int count = 0;
      if (kind != 'identity' && !zeroDue) {
        int? selected;
        await privateEditor(
          context: context,
          builder: (_) => BusinessEditor(
            session: session,
            title: 'Belegte Zahlungsteile auswählen',
            readPermission: 'personnel.read',
            writePermission: 'personnel.approve',
            readAllowed: () =>
                readable && captured == epoch && opening == session.generation,
            fields: const [
              BusinessField(
                'count',
                'Anzahl belegter Zahlungsteile',
                type: BusinessInput.integer,
                required: true,
              ),
            ],
            initial: {
              'count': previous?['details']['payments'].length ?? preserved + 1,
            },
            saveLabel: 'Zahlungsnachweise erfassen',
            onSave: (values) async {
              final n = values['count'];
              if (n is! int || n < 1 || n > 20 || n <= preserved)
                throw const FormatException(
                  'Ein bis 20 tatsächlich belegte Zahlungsteile angeben.',
                );
              selected = n;
            },
          ),
        );
        if (selected == null || !mounted) return;
        count = selected!;
      }
      final details = {
            ...businessMap(previous?['details']),
            if (selectedRun != null) 'run_id': selectedRun['id'],
            if (selectedRun != null) 'run_revision': selectedRun['revision'],
          },
          fields = <BusinessField>[],
          initial = <String, dynamic>{};
      void sourceField(String name, String collection, String label) {
        fields.add(
          BusinessField(
            '${name}_ref',
            label,
            type: BusinessInput.choice,
            required: true,
            choices: {
              '': 'Quelle ausdrücklich auswählen',
              for (final r
                  in name == 'run' ? [selectedRun!] : sources[collection]!)
                _ref(
                  r,
                ): "${r['profile'] != null ? '${r['profile']['employment_kind'] == 'minijob' ? 'Minijob' : 'Regulär'} · ${r['profile']['effective_from']}' : r['source']?['month'] ?? '${r['sources']?['profile']?['profile']?['employment_kind'] == 'minijob' ? 'Minijob' : 'Regulär'} · ${r['details']?['valid_from']} · Profilfassung ${r['details']?['profile_revision']}'} · Fassung ${r['revision']}",
            },
          ),
        );
        initial['${name}_ref'] = details['${name}_id'] == null
            ? ''
            : '${details['${name}_id']}@${details['${name}_revision']}';
      }

      if (kind == 'identity') {
        if (session.hasFeature('payroll_individual_minijob')) {
          fields.add(
            const BusinessField(
              'identity_scope',
              'Umfang des Identitätsnachweises',
              type: BusinessInput.choice,
              required: true,
              choices: {
                'legacy': 'Bisheriger Standardnachweis',
                'individual_minijob':
                    'ELStAM für individuell besteuerten Minijob',
              },
            ),
          );
          initial['identity_scope'] =
              details['identity_source_schema_version'] == 2
              ? 'individual_minijob'
              : 'legacy';
        }
        sourceField(
          'profile',
          'profiles',
          'Belegtes Steuer- und Versicherungsprofil',
        );
        for (final entry in payrollIdentityLabels.entries) {
          final name = entry.key,
              type = name.endsWith('_minor')
                  ? BusinessInput.decimal
                  : [
                      'date_of_birth',
                      'employment_from',
                      'employment_to',
                      'tax_source_date',
                      'valid_from',
                      'valid_to',
                    ].contains(name)
                  ? BusinessInput.date
                  : BusinessInput.text;
          final choice = name == 'country_code'
              ? {'': 'Bitte wählen', 'DE': 'Deutschland'}
              : name == 'tax_source'
              ? {
                  '': 'Herkunft ausdrücklich wählen',
                  'elstam_imported': 'Vorliegender ELStAM-Nachweis',
                  'tax_office_certificate': 'Bescheinigung des Finanzamts',
                  'flat_minijob_evidence':
                      'Pauschal besteuerter Minijobnachweis',
                }
              : null;
          fields.add(
            BusinessField(
              name,
              entry.value,
              type: choice == null ? type : BusinessInput.choice,
              required: name != 'employment_to',
              choices: choice ?? const {},
              hint: name == 'religion_code'
                  ? 'Geprüftes Merkmal aus dem Nachweis; none bedeutet keine Kirchensteuerpflicht.'
                  : null,
            ),
          );
          initial[name] = name.endsWith('_minor')
              ? _amount(details[name])
              : details[name];
        }
      } else {
        sourceField(
          'identity',
          'identities',
          'Gültiger Stamm- und Steuermerkmalsnachweis',
        );
        if (kind == 'payment')
          sourceField(
            'run',
            'runs',
            'Ausgewählte unveränderte Monatsberechnung',
          );
        else {
          sourceField(
            'profile',
            'profiles',
            'Belegtes Steuer- und Versicherungsprofil',
          );
          fields.add(
            const BusinessField(
              'month',
              'Belegter Vortragsmonat (JJJJ-MM)',
              required: true,
            ),
          );
          initial['month'] = details['month'];
          for (final entry in payrollCarryLabels.entries) {
            fields.add(
              BusinessField(
                entry.key,
                entry.value,
                type: BusinessInput.decimal,
                required: true,
              ),
            );
            initial[entry.key] = _amount(details[entry.key]);
          }
          fields.add(
            const BusinessField(
              'status',
              'Vortragsstatus',
              type: BusinessInput.choice,
              required: true,
              choices: {
                '': 'Bitte wählen',
                'active': 'Als belegten Monat übernehmen',
                'void': 'Vortrag begründet aufheben',
              },
            ),
          );
          initial['status'] = details['status'] ?? '';
        }
        if (multiple) {
          fields.add(
            BusinessField(
              'prior_payment_summary',
              positiveCorrection
                  ? 'Unverändert übernommene bisherige Zahlungen'
                  : 'Übernommener laufender Zahlungsstand',
              type: BusinessInput.choice,
              required: true,
              choices: {
                priorKey: prior == null
                    ? 'Keine frühere Zahlung übernommen'
                    : '$preserved frühere ${positiveCorrection ? 'Zahlungsteile und ihre Nettozuordnungen' : 'laufende Zahlungsteile'} bleiben unverändert',
              },
            ),
          );
          initial['prior_payment_summary'] = priorKey;
          if (positiveCorrection) {
            fields.add(
              BusinessField(
                'additional_payment_summary',
                'Zusätzlich tatsächlich zu belegen',
                type: BusinessInput.choice,
                required: true,
                choices: {
                  'review': repayment
                      ? '${_money(transition!['repayment_minor'])} tatsächliche Rückzahlung 2026; neue Zahlbeträge und Bonusanteile negativ eingeben; frühere Zahlungen bleiben unverändert; kein automatischer Geldeinzug'
                      : positivePaymentDates
                      ? '${_money(transition!['additional_net_minor'])} mit tatsächlichem Zahlungstag 2026; ursprünglicher Bruttozufluss unverändert; kein automatischer Geldtransfer'
                      : '${_money(transition!['additional_net_minor'])} am ursprünglichen Zuflusstag ${businessDate(transition['receipt_date'])}; kein automatischer Geldtransfer',
                },
              ),
            );
            initial['additional_payment_summary'] = 'review';
          }
          for (var i = 0; i < preserved; i++) {
            final p = prior!['details']['payments'][i];
            fields.add(
              BusinessField(
                'preserved_$i',
                'Unverändertes Zahlungsoriginal ${i + 1}',
                type: BusinessInput.choice,
                required: true,
                choices: {
                  'original':
                      '${businessDate(p['paid_on'])} · ${_money(p['amount_minor'])} · ${p['payment_reference']}',
                },
              ),
            );
            initial['preserved_$i'] = 'original';
            if (positiveCorrection) {
              final allocation = businessMap(
                    prior['details']['settlement_allocations'][i],
                  ),
                  bonus = (allocation['one_off_allocations'] as List).fold<int>(
                    0,
                    (n, a) => n + (a['net_minor'] as int),
                  );
              fields.add(
                BusinessField(
                  'preserved_allocation_$i',
                  'Unveränderte Nettozuordnung ${i + 1}',
                  type: BusinessInput.choice,
                  required: true,
                  choices: {
                    'original':
                        'Laufend ${_money(allocation['running_minor'])} · Bonus ${_money(bonus)}',
                  },
                ),
              );
              initial['preserved_allocation_$i'] = 'original';
            }
          }
        }
        for (var i = 0; i < count; i++) {
          final p = businessMap(
            i < preserved
                ? prior!['details']['payments'][i]
                : (details['payments'] as List? ?? []).elementAtOrNull(i),
          );
          if (i < preserved) {
            initial['paid_on_$i'] = p['paid_on'];
            initial['amount_$i'] = _amount(p['amount_minor']);
            initial['reference_$i'] = p['payment_reference'];
            final allocation = positiveCorrection
                ? businessMap(prior!['details']['settlement_allocations'][i])
                : null;
            initial['running_$i'] = _amount(
              allocation?['running_minor'] ?? p['amount_minor'],
            );
            initial['bonus_$i'] = allocation == null
                ? '0.00'
                : _amount(
                    (allocation['one_off_allocations'] as List).fold<int>(
                      0,
                      (n, a) => n + (a['net_minor'] as int),
                    ),
                  );
            continue;
          }
          fields.addAll([
            BusinessField(
              'paid_on_$i',
              'Tatsächlicher Zahlungstag ${i + 1}',
              type: BusinessInput.date,
              required: true,
            ),
            BusinessField(
              'amount_$i',
              'Belegter Zahlbetrag EUR ${i + 1}',
              type: BusinessInput.decimal,
              required: true,
              hint: positiveCorrection
                  ? positivePaymentDates
                        ? 'Nur tatsächlich zusätzlich gezahlte positive Beträge mit ihrem wirklichen Zahlungstag 2026 erfassen. Der Bruttozufluss bleibt unverändert.'
                        : 'Nur einen tatsächlich zusätzlich gezahlten positiven Betrag am ursprünglichen Bonus-Zuflusstag erfassen.'
                  : 'Negativ nur für tatsächliche Arbeitnehmer-Nachzahlung. Nur tatsächlich geflossene Beträge erfassen.',
            ),
            BusinessField(
              'reference_$i',
              'Zahlungsnachweis / Referenz ${i + 1}',
              required: true,
            ),
          ]);
          initial['paid_on_$i'] = p['paid_on'];
          initial['amount_$i'] = _amount(p['amount_minor']);
          initial['reference_$i'] = p['payment_reference'];
          if (multiple) {
            final a = businessMap(
              (details['settlement_allocations'] as List? ?? [])
                  .elementAtOrNull(i),
            );
            fields.addAll([
              BusinessField(
                'running_$i',
                'Laufender Nettoanteil EUR ${i + 1}',
                type: BusinessInput.decimal,
                required: true,
              ),
              BusinessField(
                'bonus_$i',
                'Bonusanteil EUR ${i + 1}',
                type: BusinessInput.decimal,
                required: true,
              ),
            ]);
            initial['running_$i'] = _amount(a['running_minor']);
            initial['bonus_$i'] = a.isEmpty
                ? ''
                : _amount(
                    (a['one_off_allocations'] as List).fold<int>(
                      0,
                      (n, o) => n + (o['net_minor'] as int),
                    ),
                  );
          }
        }
        fields.addAll(const [
          BusinessField(
            'tax_free_payments_minor',
            'Gesondert belegte steuerfreie Bezüge (€)',
            type: BusinessInput.decimal,
            required: true,
          ),
          BusinessField(
            'tax_free_basis',
            'Rechtsgrundlage und Beleg steuerfreier Bezüge',
            type: BusinessInput.multiline,
          ),
        ]);
        initial['tax_free_payments_minor'] = _amount(
          details['tax_free_payments_minor'],
        );
        initial['tax_free_basis'] = details['tax_free_basis'];
      }
      fields.addAll([
        BusinessField(
          'standard_case_confirmed',
          kind == 'payment'
              ? 'Ich habe ausschließlich die im ausgewählten Lohnlauf belegten Entgelte und Nettoabzüge ohne weitere unberücksichtigte Sachverhalte geprüft.'
              : 'Ich habe den unterstützten inländischen Standardfall mit laufendem Barlohn ohne weitere Sonderbezüge oder U-/S-Fälle geprüft.',
          type: BusinessInput.toggle,
        ),
        BusinessField(
          'source_file_id',
          'Geschütztes Original des Nachweises',
          type: BusinessInput.choice,
          required: true,
          choices: {
            '': 'Original ausdrücklich auswählen',
            for (final file in files) '${file['id']}': '${file['filename']}',
          },
        ),
        if (previous != null)
          const BusinessField(
            'correction_reason',
            'Begründung der Nachweiskorrektur',
            type: BusinessInput.multiline,
            required: true,
          ),
        BusinessField(
          'confirmed',
          zeroDue
              ? 'Ich bestätige den belegten Nullnetto-Nachweis und die ausgewählten Quellfassungen. Gesonderte Steuer- und Beitragsabführungen bleiben getrennt nachzuweisen.'
              : 'Ich bestätige die tatsächlichen belegten Angaben und die ausgewählten Quellfassungen.',
          type: BusinessInput.toggle,
        ),
      ]);
      initial['source_file_id'] = previous?['source_file']['id'] ?? '';
      initial['confirmed'] = initial['standard_case_confirmed'] = false;
      await privateEditor(
        context: context,
        builder: (_) => BusinessEditor(
          session: session,
          title:
              '${previous == null ? 'Erfassung' : 'Berichtigung'} · ${zeroDue ? 'Keine Nettozahlung geschuldet' : payrollAccountKinds[kind]}',
          fields: fields,
          initial: initial,
          pendingKey: key,
          readPermission: 'personnel.read',
          writePermission: kind == 'identity'
              ? 'personnel.write'
              : 'personnel.approve',
          readAllowed: () =>
              readable && captured == epoch && opening == session.generation,
          saveLabel: 'Geprüften Lohnkontonachweis speichern',
          onSave: (values) async {
            await fresh(kind: kind);
            if (values['identity_scope'] == 'individual_minijob' &&
                !session.hasFeature('payroll_individual_minijob'))
              throw const ApiException(
                403,
                'Die Freigabe für den individuellen Minijob fehlt.',
              );
            if (session.pending(key)) {
              await session.repeatPayrollAccountCommand(employeeId);
              return;
            }
            if (values['confirmed'] != true)
              throw const FormatException(
                'Belegte Angaben ausdrücklich bestätigen.',
              );
            final file = files
                .where(
                  (f) =>
                      f['id'] == values['source_file_id'] &&
                      f['employee_id'] == employeeId,
                )
                .firstOrNull;
            if (file == null)
              throw const FormatException(
                'Passendes geschütztes Original auswählen.',
              );
            final paymentValues = {
              ...values,
              if (multiple) 'prior_payment_ref': priorKey,
            };
            for (var i = 0; i < preserved; i++) {
              final p = prior!['details']['payments'][i];
              paymentValues.addAll({
                'paid_on_$i': p['paid_on'],
                'amount_$i': _amount(p['amount_minor']),
                'reference_$i': p['payment_reference'],
                'running_$i': positiveCorrection
                    ? _amount(
                        prior['details']['settlement_allocations'][i]['running_minor'],
                      )
                    : _amount(p['amount_minor']),
                'bonus_$i': positiveCorrection
                    ? _amount(
                        (prior['details']['settlement_allocations'][i]['one_off_allocations']
                                as List)
                            .fold<int>(
                              0,
                              (n, a) => n + (a['net_minor'] as int),
                            ),
                      )
                    : '0.00',
              });
            }
            final body = <String, dynamic>{
              'employee_id': employeeId,
              'kind': kind,
              'details': payrollAccountDetails(
                kind,
                paymentValues,
                sources,
                count: count,
                paymentDates: positivePaymentDates,
                repayments: repayment,
              ),
              'source_file_id': file['id'],
              'confirmed': true,
              'revision': previous?['revision'] ?? 0,
              if (previous != null) 'id': previous['id'],
              if (previous != null)
                'correction_reason': '${values['correction_reason'] ?? ''}'
                    .trim(),
            };
            Map<String, dynamic>? paymentPlan;
            try {
              paymentPlan = multiple
                  ? await payrollMultiplePaymentPlan(
                      businessMap(body['details']),
                      selectedRun!,
                      prior: prior,
                    )
                  : null;
            } on ApiException catch (error) {
              if (positiveCorrection) throw FormatException(error.message);
              rethrow;
            }
            if (multiple) {
              await fresh(kind: kind);
              if (!mounted ||
                  !readable ||
                  captured != epoch ||
                  opening != session.generation)
                throw const ApiException(
                  403,
                  'Die private Zahlungsansicht wurde gewechselt.',
                );
              if (positiveCorrection &&
                  (!session.hasFeature(payrollPositiveCorrectionFeature) ||
                      body['details']['payment_source_schema_version'] == 3 &&
                          !session.hasFeature(
                            payrollPositivePaymentDatesFeature,
                          ) ||
                      body['details']['payment_source_schema_version'] == 4 &&
                          !session.hasFeature(payrollRepaymentFeature) ||
                      !session.hasModule('payroll_multiple_cases')))
                throw const ApiException(
                  409,
                  'Die Freigabe der zusätzlichen Nettozahlung ist nicht mehr verfügbar.',
                );
            }
            await session.command(
              key,
              '/payroll/account-records',
              body,
              validateResult: payrollAccountReceiptValidator(
                body,
                file,
                previous: previous,
                sourceEvidence: {
                  if (multiple) 'single_payment_plan': paymentPlan,
                  for (final entry in {
                    'profile': 'profiles',
                    'run': 'runs',
                    'identity': 'identities',
                  }.entries)
                    if (body['details']['${entry.key}_id'] != null)
                      entry.key: sources[entry.value]!.firstWhere(
                        (v) =>
                            v['id'] == body['details']['${entry.key}_id'] &&
                            v['revision'] ==
                                body['details']['${entry.key}_revision'],
                      ),
                },
              ),
            );
          },
        ),
      );
      if (mounted && readable && captured == epoch) await load();
    } catch (e) {
      fail(e, expectedEpoch: captured);
    } finally {
      editingKind = null;
    }
  }

  Widget card(Map<String, dynamic> value, {bool historical = false}) => Card(
    child: Padding(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            '${payrollAccountKinds[value['kind']]} · Fassung ${value['revision']}',
            style: Theme.of(context).textTheme.titleMedium,
          ),
          if ([
            1,
            2,
            3,
            4,
          ].contains(value['details']['payment_source_schema_version'])) ...[
            const Text('Belegte Nettozuordnung'),
            for (final a in businessItems(
              value['details']['settlement_allocations'],
            ))
              ListTile(
                title: Text(
                  'Tatsächlicher Zahlungsteil ${a['payment_index'] + 1}',
                ),
                subtitle: Text(
                  'Laufender Nettoanteil: ${_money(a['running_minor'])} · Bonusanteil: ${_money((a['one_off_allocations'] as List).fold<int>(0, (n, v) => n + (v['net_minor'] as int)))}',
                ),
              ),
            Notice(
              value['details']['prior_payment_ref'] == null
                  ? 'Keine frühere Zahlung übernommen.'
                  : [2, 3, 4].contains(
                      value['details']['payment_source_schema_version'],
                    )
                  ? 'Alle früheren Zahlungsteile und ihre Nettozuordnungen bleiben unverändert. Nur zusätzlich belegte positive Beträge werden ergänzt.'
                  : 'Frühere laufende Zahlungsoriginale bleiben unverändert erhalten.',
            ),
            if (value['details']['payment_source_schema_version'] == 3)
              const Notice(
                'Die ursprünglichen Bruttozuflüsse bleiben unverändert. Zusätzliche Nettozahlungen sind an ihren tatsächlichen belegten Zahlungstagen erfasst.',
              ),
          ],
          if (value['kind'] == 'payment' &&
              value['details']['payment_source_schema_version'] == 4)
            const Notice(
              'Die tatsächliche Rückzahlung des Beschäftigten ist mit ihrem eigenen Tag und Original erfasst. Frühere Zahlungen und der ursprüngliche Bruttozufluss bleiben unverändert. Hier wird kein Geld eingezogen.',
            ),
          if (value['kind'] == 'payment' &&
              (value['details']['payments'] as List).isEmpty)
            const Notice(
              'Keine Nettozahlung geschuldet. Gesonderte Steuer- und Beitragsabführungen bleiben getrennt nachzuweisen.',
              error: false,
            ),
          ExpansionTile(
            title: const Text('Belegte Angaben'),
            children: [
              for (final entry in businessMap(value['details']).entries.where(
                (e) => ![
                  'payments',
                  'payment_source_schema_version',
                  'settlement_allocations',
                  'prior_payment_ref',
                ].contains(e.key),
              ))
                ListTile(
                  title: Text(
                    payrollIdentityLabels[entry.key] ??
                        payrollCarryLabels[entry.key] ??
                        _detailsLabels[entry.key] ??
                        entry.key,
                  ),
                  subtitle: Text(
                    entry.key.endsWith('_minor')
                        ? _money(entry.value)
                        : entry.value == null
                        ? 'Nicht angegeben'
                        : entry.value == true
                        ? 'Ja'
                        : '${entry.value}',
                  ),
                ),
            ],
          ),
          for (final p in businessItems(value['details']['payments'] ?? []))
            ListTile(
              title: Text(
                '${businessDate(p['paid_on'])} · ${_money(p['amount_minor'])}',
              ),
              subtitle: Text(
                '${p['payment_reference']}${p['amount_minor'] < 0 ? ' · Arbeitnehmer-Nachzahlung' : ''}',
              ),
            ),
          if ('${value['correction_reason'] ?? ''}'.isNotEmpty)
            Text('Korrektur: ${value['correction_reason']}'),
          Wrap(
            spacing: 8,
            children: [
              TextButton(
                onPressed: () => openOriginal(value),
                child: const Text('Nachweisoriginal öffnen'),
              ),
              if (!historical)
                TextButton(
                  onPressed: () => openHistory(value),
                  child: const Text('Nachweishistorie'),
                ),
              if (!historical &&
                  writable(value['kind']) &&
                  !session.pending(key))
                OutlinedButton(
                  onPressed: () => edit(value['kind'], value),
                  child: const Text('Nachweis berichtigen'),
                ),
            ],
          ),
        ],
      ),
    ),
  );
  @override
  Widget build(BuildContext context) {
    final pending = session.pendingCommandValues(
      key,
      path: '/payroll/account-records',
    );
    return Scaffold(
      appBar: AppBar(
        title: Text(
          readable
              ? 'Lohnkonto-Nachweise · ${employee['name']}'
              : 'Lohnkonto-Nachweise',
        ),
        actions: [
          IconButton(
            tooltip: 'Rechte und Nachweise aktualisieren',
            onPressed: loading || busy ? null : () => load(refresh: true),
            icon: const Icon(Icons.refresh),
          ),
        ],
      ),
      body: !readable
          ? Padding(
              padding: const EdgeInsets.all(24),
              child: BusinessEmpty(
                'Lohnkonto nicht freigegeben',
                error ?? 'Aktuelle Personal- oder eigene Mitarbeiterfreigabe erforderlich.',
              ),
            )
          : ListView(
              padding: const EdgeInsets.all(20),
              children: [
                const Notice(
                  'Geschützte Stammnachweise, tatsächliche Zahlungen und belegte Vortragsmonate. Hier erfolgt keine Zahlung oder Meldung. Fehlende Angaben bleiben in der Jahresübersicht erkennbar.',
                ),
                if (error != null) Notice(error!, error: true),
                if (message != null) Notice(message!),
                if (loading || busy) const LinearProgressIndicator(),
                if (pending != null)
                  Card(
                    child: Padding(
                      padding: const EdgeInsets.all(16),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          const Text('Nachweisbestätigung offen'),
                          const Text(
                            'Der Vorgang kann bereits gespeichert sein. Die Wiederholung bleibt unverändert.',
                          ),
                          FilledButton(
                            onPressed: !busy && writable('${pending['kind']}')
                                ? repeat
                                : null,
                            child: const Text(
                              'Ursprünglichen Nachweis erneut senden',
                            ),
                          ),
                        ],
                      ),
                    ),
                  ),
                if (pending == null)
                  Wrap(
                    spacing: 8,
                    runSpacing: 8,
                    children: [
                      for (final entry in payrollAccountKinds.entries)
                        if (writable(entry.key))
                          OutlinedButton(
                            onPressed: () => edit(entry.key),
                            child: Text('${entry.value} erfassen'),
                          ),
                    ],
                  ),
                if (records.isEmpty && !loading)
                  const BusinessEmpty(
                    'Noch keine Lohnkonto-Nachweise',
                    'Geschütztes Original in der Personalakte aufnehmen und die dazugehörigen Angaben ausdrücklich bestätigen.',
                  ),
                for (final r in records) card(r),
                if (history.isNotEmpty)
                  Text(
                    'Unveränderliche Nachweishistorie',
                    style: Theme.of(context).textTheme.titleLarge,
                  ),
                for (final r in history) card(r, historical: true),
              ],
            ),
    );
  }
}

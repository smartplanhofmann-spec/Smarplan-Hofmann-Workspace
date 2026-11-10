import 'business_payroll_source5_adjustment.dart';
import 'business_payroll_source5_repayment.dart';

import 'dart:async';
import 'dart:convert';
import 'dart:typed_data';

import 'package:cryptography/cryptography.dart';
import 'package:flutter/material.dart';
import 'package:flutter/scheduler.dart';

import 'api.dart';
import 'business_personnel_workflow.dart' show personnelMinor;
import 'business_payroll_accounts.dart';
import 'business_payroll_cash.dart';
import 'business_payroll_cash_page.dart';
import 'business_payroll_facts.dart';
import 'business_payroll_entitlements.dart';
import 'business_payroll_calculation_case_contract.dart';
import 'business_payroll_calculation_cases.dart';
import 'business_payroll_statements.dart';
import 'business_payroll_wage_interruptions.dart';
import 'business_payroll_rv_lifecycle.dart';
import 'business_payroll_annual_basis.dart';
import 'business_payroll_oneoff_cases.dart';
import 'business_payroll_multiple_cases.dart';
import 'business_payroll_source5_transition.dart';
import 'business_session.dart';
import 'business_widgets.dart';
import 'design.dart';
import 'mail_attachment_preview.dart';
import 'mail_attachment_widgets.dart' show exportMailAttachment;

const payrollScopes = {
  payrollFactorClaimTravelScope:
      'Faktor-Monat mit belegten Ansprüchen und bereits bezahlten Reisen',
  individualMinijobScope:
      'Individuell besteuerter gewerblicher Minijob · belegter Vollmonat',
  payrollFactorTaxfreeTravelScope:
      'Faktor-Vollmonat mit bereits erstatteter steuerfreier Reise',
  'regular_standard_multiple_oneoff': 'Regulärer Gesamtlohn mit vollständigem Einzelanspruch · getrennte Zahlungstage',
  'multiple_oneoff_review_required':
      'Monatsgruppe mit ungeklärter Steuer- oder Beitragszuordnung',
  'regular_standard_factor_claims_oneoff':
      'Faktor-Monat mit belegtem Einmalbezug',
  'regular_standard_oneoff':
      'Regulärer Gesamtlohn mit belegtem Einmalbezug · PAP 2026',
  'regular_standard_segments': 'Regulärer belegter Gesamtfall · PAP 2026',
  'regular_transition_segments': 'Belegter Übergangsbereich · Gesamtfall',
  'commercial_minijob_segments_flat_tax':
      'Gewerblicher Minijob · belegter Gesamtfall',
  'regular_standard_factor_period':
      'Steuerklasse IV mit Faktor · belegter Monat oder Teilmonat',
  'regular_standard_period': 'Reguläre belegte Teilmonatsberechnung · PAP 2026',
  'regular_transition_period':
      'Belegter Übergangsbereich · Teilmonat und PAP 2026',
  'commercial_minijob_period_flat_tax':
      'Gewerblicher Minijob · belegter Teilmonat',
  payrollFactorTransitionScope: 'Belegter Midijob mit ELStAM-Faktor',
  payrollFactorTransitionPeriodScope:
      'Midijob-Teilmonat mit belegtem ELStAM-Faktor',
  'regular_transition_monthly':
      'Belegter Übergangsbereich · Vollmonat und PAP 2026',
  'regular_standard_monthly': 'Reguläre Standard-Monatsberechnung · PAP 2026',
  'regular_standard_factor_claims_month':
      'Faktor-Monat mit belegten Lohnansprüchen',
  'regular_standard_factor_monthly':
      'Reguläre Steuerklasse IV mit Faktor · Vollmonat und PAP 2026',
  'commercial_minijob_flat_tax':
      'Gewerblicher Minijob · Arbeitgeber trägt 2 % Pauschsteuer',
  'social_contributions_only':
      'Nur Sozialversicherung · reguläre Lohnsteuer und Netto offen',
  'unsupported': 'Dieser Fall ist noch nicht berechenbar',
};
const payrollSpecialCases = {
  'church_tax_special_case': 'Kirchensteuer-Sonderfall',
  'multiple_employments': 'Mehrfachbeschäftigung',
  'one_off_payment': 'Einmalzahlung',
  'benefit_in_kind': 'Sachbezug',
  'short_time_work': 'Kurzarbeit',
  'unpaid_absence': 'Unbezahlte Abwesenheit',
  'sick_pay': 'Krankengeld',
  'pension_receipt': 'Rentenbezug',
  'apprentice': 'Ausbildung',
  'working_student': 'Werkstudent',
  'foreign_tax': 'Auslandssteuerfall',
  'occupational_pension': 'Betriebliche Altersversorgung',
  'reduced_health_rate': 'Ermäßigter KV-Satz',
  'tax_factor': 'Steuerfaktor',
  'old_minijob_before_2013': 'Minijob vor 2013',
  'other_special_case': 'Anderer Sonderfall',
};
const _federalStates = {
  'BW': 'Baden-Württemberg',
  'BY': 'Bayern',
  'BE': 'Berlin',
  'BB': 'Brandenburg',
  'HB': 'Bremen',
  'HH': 'Hamburg',
  'HE': 'Hessen',
  'MV': 'Mecklenburg-Vorpommern',
  'NI': 'Niedersachsen',
  'NW': 'Nordrhein-Westfalen',
  'RP': 'Rheinland-Pfalz',
  'SL': 'Saarland',
  'SN': 'Sachsen',
  'ST': 'Sachsen-Anhalt',
  'SH': 'Schleswig-Holstein',
  'TH': 'Thüringen',
};
const _profileLabels = {
  'effective_from': 'Tatsächlich gültig ab',
  'employment_kind': 'Beschäftigungsart',
  'date_of_birth': 'Geburtsdatum',
  'federal_state': 'Bundesland',
  'tax_class': 'Steuerklasse',
  'tax_children_half_units': 'Kinderfreibetrag in halben Einheiten',
  'church_tax': 'Kirchensteuermerkmal',
  'health_insurance': 'Krankenversicherungsstatus',
  'health_fund': 'Krankenkasse / Versicherungsnachweis',
  'health_additional_percent': 'Tatsächlicher Zusatzbeitrag (%)',
  'has_children': 'Elterneigenschaft nachgewiesen',
  'pv_children_under_25': 'Berücksichtigungsfähige PV-Kinder unter 25',
  'u1_required': 'U1-Teilnahme',
  'u1_percent': 'Gültiger U1-Satz (%)',
  'u2_percent': 'Gültiger U2-Satz (%)',
  'minijob_rv_exempt': 'Wirksame Minijob-RV-Befreiung',
  'minijob_tax': 'Minijob-Steuerverfahren',
  'pension_other_compulsory': 'Weitere RV-pflichtige Beschäftigung',
  'regular_annual_gross_minor': 'Regelmäßiges Jahresbrutto',
  'special_cases': 'Geprüfte Sonderfälle',
  'verification_note': 'Prüfvermerk und Grundlage',
  'tax_allowance_monthly_minor': 'Monatlicher ELStAM-Freibetrag (€)',
  'tax_addition_monthly_minor': 'Monatlicher ELStAM-Hinzurechnungsbetrag (€)',
  'tax_factor': 'Eingetragener ELStAM-Faktor (Steuerklasse IV)',
};
const _transitionLabels = {
  'transition_assessment': 'Belegte Übergangsbereichsprognose',
  'status': 'Geprüfter Status',
  'assessed_on': 'Datum der Statusprüfung',
  'regular_monthly_gross_minor': 'Prognostiziertes regelmäßiges Monatsbrutto',
  'forecast_months': 'Geprüfter Prognosezeitraum in Monaten',
  'foreseeable_one_off_payments': 'Vorhersehbare Einmalzahlungen',
  'note': 'Beleggrundlage der Prognose',
};
const _booleanFields = [
  'has_children',
  'u1_required',
  'minijob_rv_exempt',
  'pension_other_compulsory',
];
const _percentFields = [
  'health_additional_percent',
  'u1_percent',
  'u2_percent',
];
const _contributionLabels = {
  'health_general': 'Krankenversicherung',
  'health_additional': 'KV-Zusatzbeitrag',
  'pension': 'Rentenversicherung',
  'unemployment': 'Arbeitslosenversicherung',
  'care': 'Pflegeversicherung',
  'u1': 'U1',
  'u2': 'U2',
  'insolvency': 'Insolvenzgeldumlage',
};

bool payrollAvailable(BusinessSession session) =>
    session.projectId == null &&
    session.hasFeature('german_payroll_2026') &&
    session.hasModule('payroll') &&
    (session.can('personnel.read') || session.can('time.own'));
String payrollMoney(Object? minor) {
  if (minor is! int) return 'Nicht ermittelt';
  final abs = minor.abs();
  return businessMoney(
    '${minor < 0 ? '-' : ''}${abs ~/ 100}.${(abs % 100).toString().padLeft(2, '0')}',
  );
}

String _inputMoney(Object? minor) {
  if (minor is! int) return '';
  final abs = minor.abs();
  return '${minor < 0 ? '-' : ''}${abs ~/ 100}.${(abs % 100).toString().padLeft(2, '0')}';
}

int payrollTaxMinor(Object? value) {
  final text = '${value ?? ''}'.trim().replaceAll(',', '.');
  if (RegExp(r'^0(?:\.0{1,2})?$').hasMatch(text)) return 0;
  return personnelMinor(value);
}

String payrollFactor(Object? value) {
  if (value is! String) {
    throw const FormatException(
      'Den eingetragenen Faktor als genauen Dezimaltext angeben.',
    );
  }
  final text = value.trim().replaceAll(',', '.');
  if (!RegExp(r'^0\.[0-9]{3}$').hasMatch(text)) {
    throw const FormatException(
      'Eingetragenen ELStAM-Faktor mit genau drei Nachkommastellen und kleiner als eins angeben.',
    );
  }
  return text;
}

String payrollRate(Object? input) {
  final text = '${input ?? ''}'.trim().replaceAll(',', '.');
  if (!RegExp(r'^\d{1,2}(?:\.\d{1,3})?$').hasMatch(text))
    throw const FormatException(
      'Beitragssatz mit höchstens drei Nachkommastellen eingeben.',
    );
  final parts = text.split('.'),
      milli =
          int.parse(parts[0]) * 1000 +
          int.parse((parts.length == 2 ? parts[1] : '').padRight(3, '0'));
  if (milli > 20000)
    throw const FormatException(
      'Der Beitragssatz muss zwischen 0 und 20 Prozent liegen.',
    );
  return '${milli ~/ 1000}.${(milli % 1000).toString().padLeft(3, '0')}';
}

dynamic _order(dynamic v) => v is List
    ? v.map(_order).toList()
    : v is Map
    ? {
        for (final key in v.keys.map((k) => '$k').toList()..sort())
          key: _order(v[key]),
      }
    : v;
bool payrollSame(dynamic a, dynamic b) =>
    jsonEncode(_order(a)) == jsonEncode(_order(b));
Map<String, dynamic> _copy(Map<String, dynamic> v) =>
    businessMap(jsonDecode(jsonEncode(v)));
String _hex(List<int> v) =>
    v.map((n) => n.toRadixString(16).padLeft(2, '0')).join();
int _sum(dynamic v) {
  final m = businessMap(v);
  if (m.values.any((n) => n is! int || n < 0))
    throw const ApiException(0, 'Ungültige Beitragsbeträge in der Berechnung.');
  return m.values.fold<int>(0, (total, n) => total + (n as int));
}

Map<String, dynamic> payrollCalculation(dynamic value) {
  final v = businessMap(value), scope = v['scope'];
  final periodRule = [
    'de_2026_periods_pap_v4',
    payrollFactorPeriodRule,
  ].contains(v['rule_version']);
  if (v['rule_version'] == payrollMultipleRule)
    return payrollMultipleCalculation(v);
  if ([payrollOneOffRule, payrollFactorOneOffRule].contains(v['rule_version']))
    return payrollOneOffCalculation(v);
  if (payrollCalculationCaseRuleKnown(
    v['rule_version'],
    v['source_contract_version'],
  ))
    return payrollCompositeCalculation(v);
  if (!payrollScopes.containsKey(scope) ||
      v['currency'] != 'EUR' ||
      (!(periodRule && scope == 'unsupported' && v['gross_minor'] == null) &&
          (v['gross_minor'] is! int ||
              v['gross_minor'] <
                  (periodRule && scope == 'unsupported' ? 0 : 1))) ||
      v['blockers'] is! List ||
      !RegExp(r'^[a-f0-9]{64}$').hasMatch('${v['rules_sha256']}') ||
      v['statutory_report_status'] != 'not_transmitted' ||
      v['official_system_approval'] != false ||
      v['accident_insurance_included'] != false ||
      v['travel_expenses_included_in_net'] != false)
    throw const ApiException(
      0,
      'Der verfügbare Lohnberechnungsumfang konnte nicht sicher gelesen werden.',
    );
  if (periodRule) payrollPeriodCalculation(v);
  if (scope == 'unsupported') {
    if (v['transition'] != null)
      throw const ApiException(
        0,
        'Ein gesperrter Übergangsbereichsfall darf keine berechneten Bemessungsgrundlagen anzeigen.',
      );
    if (v['social_contributions_available'] != false ||
        v['payroll_calculation_complete'] != false ||
        v['net_minor'] != null ||
        v['employee_social_total_minor'] != null ||
        v['employer_social_total_minor'] != null ||
        v['payout_minor'] != null)
      throw const ApiException(
        0,
        'Ein ungeklärter Fall darf keine fertige Berechnung anzeigen.',
      );
  } else {
    if (v['social_contributions_available'] != true ||
        _sum(v['employee_contributions']) != v['employee_social_total_minor'] ||
        _sum(v['employer_contributions']) != v['employer_social_total_minor'] ||
        v['gross_minor'] +
                v['employer_social_total_minor'] +
                _sum(v['employer_levies']) +
                v['employer_flat_tax_minor'] !=
            v['employer_total_excluding_accident_insurance_minor'])
      throw const ApiException(
        0,
        'Die Beitragsaufstellung passt nicht zu ihren Summen.',
      );
    if (scope == 'social_contributions_only') {
      if (v['payroll_calculation_complete'] != false ||
          [
            'individual_wage_tax_minor',
            'solidarity_minor',
            'church_tax_minor',
            'employee_tax_minor',
            'net_minor',
            'payout_minor',
            'employee_additional_payment_minor',
          ].any((key) => v[key] != null))
        throw const ApiException(
          0,
          'Ohne verifizierte individuelle Lohnsteuer bleiben reguläres Netto und Auszahlung unbekannt.',
        );
    } else {
      if ([
            'commercial_minijob_flat_tax',
            'commercial_minijob_period_flat_tax',
          ].contains(scope) &&
          v['employee_tax_minor'] != 0) {
        throw const ApiException(
          0,
          'Die Arbeitgeber-Pauschsteuer darf nicht vom Minijob-Netto abgezogen werden.',
        );
      }
      if ([
            'regular_standard_monthly',
            'regular_standard_factor_monthly',
            'regular_standard_factor_period',
            'regular_transition_monthly',
            'regular_standard_period',
            'regular_transition_period',
          ].contains(scope) &&
          (!RegExp(r'^[a-f0-9]{64}$')
                  .hasMatch('${v['pap_provenance_sha256']}') ||
              v['pap_version'] is! String ||
              [
                'individual_wage_tax_minor',
                'solidarity_minor',
                'church_tax_minor',
              ].any((key) => v[key] is! int || v[key] < 0) ||
              v['employee_tax_minor'] !=
                  v['individual_wage_tax_minor'] +
                      v['solidarity_minor'] +
                      v['church_tax_minor'])) {
        throw const ApiException(
          0,
          'PAP-Nachweis oder Steueraufstellung konnte nicht bestätigt werden.',
        );
      }
      final net =
          v['gross_minor'] -
          v['employee_social_total_minor'] -
          v['employee_tax_minor'];
      if (v['payroll_calculation_complete'] != true ||
          v['net_minor'] != net ||
          v['payout_minor'] != (net < 0 ? 0 : net) ||
          v['employee_additional_payment_minor'] != (net < 0 ? -net : 0))
        throw const ApiException(
          0,
          'Die Berechnung passt nicht zu Abzügen und Auszahlungsbetrag.',
        );
    }
  }
  if (scope == 'regular_transition_monthly') payrollTransition(v);
  if ([
        'regular_standard_factor_monthly',
        'regular_standard_factor_period',
      ].contains(scope) &&
      (v['rule_version'] !=
              (scope == 'regular_standard_factor_period'
                  ? payrollFactorPeriodRule
                  : 'de_2026_standard_factor_monthly_v8') ||
          !RegExp(r'^0\.[0-9]{3}$')
              .hasMatch('${v['tax_parameters']?['tax_factor'] ?? ''}'))) {
    throw const ApiException(
      0,
      'Die Faktorberechnung besitzt keinen eindeutigen Faktor- und Regelstand.',
    );
  }
  return v;
}

Map<String, dynamic> payrollTransition(Map<String, dynamic> value) {
  final t = businessMap(value['transition']);
  bool cents(dynamic n) => n is int && n >= 0;
  if (value['rule_version'] != 'de_2026_transition_monthly_pap_v3' ||
      t['factor'] != '0.6619' ||
      ![
        'within_transition_area',
        'below_or_at_lower_limit',
        'above_upper_limit',
      ].contains(t['regime']) ||
      t['regular_monthly_gross_minor'] is! int ||
      t['regular_monthly_gross_minor'] < 60301 ||
      t['regular_monthly_gross_minor'] > 200000 ||
      [
        'total_assessment_minor',
        'employee_assessment_minor',
        'levy_assessment_minor',
      ].any((k) => !cents(t[k])) ||
      t['employee_assessment_minor'] > t['total_assessment_minor'])
    throw const ApiException(
      0,
      'Die Übergangsbereichsberechnung besitzt keine eindeutige Regel- und Bemessungsgrundlage.',
    );
  for (final key in [
    'health_general',
    'health_additional',
    'pension',
    'unemployment',
    'care',
  ]) {
    final b = businessMap(t['branch_bases']?[key]);
    if (!cents(b['total_minor']) ||
        !cents(b['employee_minor']) ||
        b['employee_minor'] > b['total_minor'])
      throw const ApiException(
        0,
        'Ein Beitragszweig der Übergangsbereichsberechnung ist unvollständig.',
      );
  }
  final care = businessMap(t['care_adjustments']);
  if ([
        'employee_before_adjustments_minor',
        'childless_surcharge_minor',
        'children_discount_minor',
      ].any((k) => !cents(care[k])) ||
      care['employee_before_adjustments_minor'] +
              care['childless_surcharge_minor'] -
              care['children_discount_minor'] !=
          value['employee_contributions']['care'] ||
      !RegExp(r'^\d+\.\d{3}$').hasMatch('${care['employee_base_percent']}') ||
      !RegExp(r'^\d+\.\d{3}$').hasMatch('${care['employer_normal_percent']}'))
    throw const ApiException(
      0,
      'PV-Zuschlag und Kinderabschläge stimmen nicht mit der Beitragsaufstellung überein.',
    );
  return t;
}

Map<String, dynamic> payrollPreview(dynamic raw, Map<String, dynamic> input) {
  if (input['source_schema_version'] == 5) {
    final value = payrollMultipleSource(raw, input);
    if (!RegExp(r'^[a-f0-9]{64}$').hasMatch('${value['preview_hash']}'))
      throw const ApiException(0, 'Die Vorschauprüfsumme fehlt.');
    return value;
  }
  if (input['source_schema_version'] == 4) {
    final value = payrollOneOffSource(raw, input);
    if (!RegExp(r'^[a-f0-9]{64}$').hasMatch('${value['preview_hash']}'))
      throw const ApiException(0, 'Die Vorschauprüfsumme fehlt.');
    return value;
  }
  if (input['source_schema_version'] == 3) {
    final value = payrollCompositeSource(raw, input);
    if (value['calculation']['rule_version'] == payrollFactorClaimsRule)
      payrollFactorClaimsRunHashes(value);
    if (value['calculation']['rule_version'] == payrollFactorClaimTravelRule)
      payrollFactorClaimTravelRunHashes(value);
    if (value['calculation']['rule_version'] ==
        payrollFactorTransitionPeriodRule)
      payrollFactorTransitionPeriodRunHashes(value);
    if (value['calculation']['rule_version'] == payrollFactorTransitionRule)
      payrollFactorTransitionRunHashes(value);
    if (!RegExp(r'^[a-f0-9]{64}$').hasMatch('${value['preview_hash']}'))
      throw const ApiException(0, 'Die Vorschauprüfsumme fehlt.');
    return value;
  }
  if (input['source_schema_version'] == 2) {
    final value = payrollPeriodSource(raw, input);
    payrollCalculation(value['calculation']);
    if (!RegExp(r'^[a-f0-9]{64}$').hasMatch('${value['preview_hash']}'))
      throw const ApiException(0, 'Die Vorschauprüfsumme fehlt.');
    return value;
  }
  final value = businessMap(raw),
      source = businessMap(value['source']),
      calculation = payrollCalculation(value['calculation']);
  if (!payrollSame(source['input'], input) ||
      source['employee_id'] != input['employee_id'] ||
      source['profile']?['id'] != input['profile_id'] ||
      source['profile']?['revision'] != input['profile_revision'] ||
      source['profile']?['employee_id'] != input['employee_id'] ||
      source['preparation']?['id'] != input['preparation_id'] ||
      source['preparation']?['revision'] != input['preparation_revision'] ||
      source['preparation']?['employee_id'] != input['employee_id'] ||
      source['month'] != calculation['month'] ||
      calculation['gross_minor'] != input['gross_minor'] ||
      value['can_finalize'] != calculation['social_contributions_available'] ||
      !RegExp(r'^[a-f0-9]{64}$').hasMatch('${value['preview_hash']}'))
    throw const ApiException(
      0,
      'Die Vorschau gehört nicht zu den gewählten Personal- und Monatsquellen.',
    );
  final profile = businessMap(source['profile']?['profile']);
  if (profile.containsKey('tax_factor') ||
      calculation['rule_version'] == 'de_2026_standard_factor_monthly_v8') {
    if (!RegExp(r'^0\.[0-9]{3}$').hasMatch('${profile['tax_factor'] ?? ''}') ||
        profile['tax_class'] != 4 ||
        calculation['rule_version'] != 'de_2026_standard_factor_monthly_v8' ||
        calculation['tax_parameters']?['tax_factor'] != profile['tax_factor']) {
      throw const ApiException(
        0,
        'Faktorberechnung und belegtes Personalprofil stimmen nicht überein.',
      );
    }
  }
  return value;
}

void Function(dynamic) payrollReceiptValidator(
  Map<String, dynamic> body, {
  Map<String, dynamic>? preview,
  Map<String, dynamic>? previous,
  Map<String, dynamic>? original,
}) {
  final frozen = _copy(body),
      proof = preview == null ? null : _copy(preview),
      prior = previous == null ? null : _copy(previous),
      file = original == null ? null : _copy(original);
  return (dynamic raw) {
    final v = businessMap(raw), profile = proof == null;
    bool bad =
        v['employee_id'] != frozen['employee_id'] ||
        v['kind'] != (profile ? 'profile' : 'run') ||
        v['revision'] != frozen['revision'] + 1 ||
        v['previous_hash'] != prior?['content_hash'] ||
        v['confirmed'] != true ||
        v['correction_reason'] != (frozen['correction_reason'] ?? '') ||
        !RegExp(r'^[a-f0-9]{32}$').hasMatch('${v['id']}') ||
        !RegExp(r'^[a-f0-9]{64}$').hasMatch('${v['content_hash']}') ||
        (frozen['id'] != null && v['id'] != frozen['id']);
    if (profile) {
      bad =
          bad ||
          ['rv_lifecycle_source_contract_version', 'rv_lifecycle_ref'].any(
            (k) =>
                v.containsKey(k) != frozen.containsKey(k) ||
                !payrollSame(v[k], frozen[k]),
          ) ||
          !payrollSame(v['profile'], frozen['profile']) ||
          !payrollSame(v['source_file'], {
            for (final key in ['id', 'employee_id', 'sha256', 'content_hash'])
              key: file?[key],
          });
    } else {
      if (v['calculation']?['rule_version'] == payrollFactorOneOffRule)
        payrollFactorOneOffRunHashes(v);
      if (v['calculation']?['rule_version'] == payrollFactorClaimsRule)
        payrollFactorClaimsRunHashes(v);
      if (v['calculation']?['rule_version'] == payrollFactorClaimTravelRule)
        payrollFactorClaimTravelRunHashes(v);
      if (v['calculation']?['rule_version'] ==
          payrollFactorTransitionPeriodRule)
        payrollFactorTransitionPeriodRunHashes(v);
      if (v['calculation']?['rule_version'] == payrollFactorTransitionRule)
        payrollFactorTransitionRunHashes(v);
      bad =
          bad ||
          !payrollSame(v['source'], proof['source']) ||
          !payrollSame(v['calculation'], proof['calculation']) ||
          v['preview_hash'] != proof['preview_hash'] ||
          v['accepted_scope'] != frozen['accepted_scope'] ||
          v['accepted_scope'] != proof['calculation']['scope'] ||
          v['status'] != 'calculation_recorded' ||
          v['transmission_status'] != 'not_transmitted' ||
          !RegExp(r'^[a-f0-9]{64}$').hasMatch('${v['pdf_sha256']}');
      if (v.containsKey('settlement_transition') !=
              proof.containsKey('settlement_transition') ||
          !payrollSame(
            v['settlement_transition'],
            proof['settlement_transition'],
          ))
        bad = true;
      if (frozen.containsKey('settlement_review') !=
              proof.containsKey('settlement_transition') ||
          proof.containsKey('settlement_transition') &&
              !payrollSame(
                frozen['settlement_review'],
                proof['settlement_transition']['settlement_review'],
              ))
        bad = true;
      if (!bad && v.containsKey('settlement_transition'))
        payrollSettlementTransition(v);
      final expectedDelta = prior == null
          ? null
          : {
              for (final key in [
                'gross_minor',
                'employee_social_total_minor',
                'employer_social_total_minor',
                'employer_flat_tax_minor',
                'net_minor',
                if ([
                  proof['calculation']['scope'],
                  prior['calculation']['scope'],
                ].any(
                  (scope) => [
                    'regular_standard_monthly',
                    'regular_standard_factor_monthly',
                    'regular_standard_factor_period',
                    'regular_transition_factor_month',
                    'regular_transition_monthly',
                    'regular_standard_period',
                    'regular_transition_period',
                    'regular_standard_oneoff',
                    'regular_standard_factor_claims_oneoff',
                    'regular_standard_multiple_oneoff',
                    'regular_standard_segments',
                    'regular_standard_factor_claims_month',
                    'regular_transition_segments',
                  ].contains(scope),
                )) ...[
                  'individual_wage_tax_minor',
                  'solidarity_minor',
                  'church_tax_minor',
                  'employee_tax_minor',
                  'payout_minor',
                ],
              ])
                key:
                    proof['calculation'][key] != null &&
                        prior['calculation'][key] != null
                    ? proof['calculation'][key] - prior['calculation'][key]
                    : null,
            };
      if (expectedDelta != null &&
          (proof['calculation'].containsKey('net_deductions_minor') ||
              prior!['calculation'].containsKey('net_deductions_minor')))
        expectedDelta['net_deductions_minor'] =
            (proof['calculation']['net_deductions_minor'] ?? 0) -
            (prior!['calculation']['net_deductions_minor'] ?? 0);
      bad = bad || !payrollSame(v['delta'], expectedDelta);
      if (!bad) payrollCalculation(v['calculation']);
    }
    if (bad)
      throw const ApiException(
        0,
        'Die Empfangsbestätigung stimmt nicht mit den geprüften Personalquellen überein. Der ursprüngliche Auftrag bleibt erhalten.',
      );
  };
}

Map<String, dynamic> payrollProfileInput(Map<String, dynamic> values) {
  final result = <String, dynamic>{};
  for (final key in _profileLabels.keys.where(
    (key) => ![
      'tax_allowance_monthly_minor',
      'tax_addition_monthly_minor',
      'tax_factor',
    ].contains(key),
  )) {
    if (_booleanFields.contains(key)) {
      if (!['yes', 'no'].contains(values[key]))
        throw const FormatException(
          'Alle Versicherungsmerkmale ausdrücklich mit Ja oder Nein wählen.',
        );
      result[key] = values[key] == 'yes';
    } else if (_percentFields.contains(key))
      result[key] = payrollRate(values[key]);
    else if (key == 'regular_annual_gross_minor')
      result[key] = personnelMinor(values['annual_gross']);
    else if (key == 'special_cases')
      result[key] = List<String>.from(values[key] ?? [])..sort();
    else
      result[key] = values[key] is String
          ? (values[key] as String).trim()
          : values[key];
  }
  if (result['employment_kind'] == 'regular') {
    if (![
      'standard',
      'factor',
      'social_only',
    ].contains(values['regular_tax_scope']))
      throw const FormatException(
        'Regulären Steuerumfang ausdrücklich wählen.',
      );
    if (['standard', 'factor'].contains(values['regular_tax_scope'])) {
      for (final key in [
        'tax_allowance_monthly_minor',
        'tax_addition_monthly_minor',
      ])
        result[key] = payrollTaxMinor(values[key]);
    }
  } else if (values['regular_tax_scope'] != 'minijob') {
    throw const FormatException('Minijob-Steuerumfang ausdrücklich wählen.');
  }
  if (values['regular_tax_scope'] == 'factor') {
    if (result['tax_class'] != 4 ||
        result['tax_allowance_monthly_minor'] != 0 ||
        result['tax_addition_monthly_minor'] != 0 ||
        values['transition_scope'] != 'none') {
      throw const FormatException(
        'Der Faktorfall benötigt Steuerklasse IV, bestätigte null Frei-/Hinzurechnungsbeträge und keinen Übergangsbereich.',
      );
    }
    result['tax_factor'] = payrollFactor(values['tax_factor']);
    result['special_cases'] = <String>{
      ...List<String>.from(result['special_cases']),
      'tax_factor',
    }.toList()..sort();
  } else if ('${values['tax_factor'] ?? ''}'.trim().isNotEmpty) {
    throw const FormatException(
      'Der erfasste Faktor benötigt den ausdrücklich gewählten Faktorumfang.',
    );
  }
  if (!['none', 'monthly'].contains(values['transition_scope']))
    throw const FormatException('Übergangsbereich ausdrücklich beurteilen.');
  if (values['transition_scope'] == 'monthly') {
    if (result['employment_kind'] != 'regular' ||
        values['regular_tax_scope'] != 'standard')
      throw const FormatException(
        'Die Übergangsbereichsprognose benötigt reguläre Beschäftigung und ausdrücklich geprüfte Standard-Steuermerkmale.',
      );
    final monthly = personnelMinor(values['transition_regular_monthly']);
    if (monthly < 60301 ||
        monthly > 200000 ||
        result['regular_annual_gross_minor'] != monthly * 12 ||
        values['transition_forecast_months'] != '12')
      throw const FormatException(
        'Jahresbrutto und ausdrücklich belegte Zwölfmonatsprognose müssen übereinstimmen (603,01 bis 2.000,00 € monatlich).',
      );
    final note = '${values['transition_note'] ?? ''}'.trim(),
        day = '${values['transition_assessed_on'] ?? ''}';
    if (!['yes', 'no'].contains(values['transition_one_off']) ||
        !RegExp(r'^\d{4}-\d{2}-\d{2}$').hasMatch(day) ||
        note.isEmpty ||
        note.length > 2000 ||
        RegExp(r'[\x00-\x1f]').hasMatch(note))
      throw const FormatException(
        'Prüfdatum, Einmalzahlungsmerkmal und Grundlage der Prognose vollständig angeben.',
      );
    result['transition_assessment'] = {
      'status': 'within_transition_area',
      'assessed_on': day,
      'regular_monthly_gross_minor': monthly,
      'forecast_months': 12,
      'foreseeable_one_off_payments': values['transition_one_off'] == 'yes',
      'note': note,
    };
  }
  return result;
}

List<BusinessField> payrollProfileFields(
  List<Map<String, dynamic>> files, {
  bool correction = false,
}) {
  BusinessField field(
    String key, {
    BusinessInput type = BusinessInput.text,
    String? hint,
  }) => BusinessField(
    key,
    _profileLabels[key]!,
    type: type,
    required: true,
    hint: hint,
  );
  BusinessField choice(String key, Map<String, String> values) => BusinessField(
    key,
    _profileLabels[key]!,
    type: BusinessInput.choice,
    required: true,
    choices: {'': 'Bitte ausdrücklich wählen', ...values},
  );
  return [
    field(
      'effective_from',
      type: BusinessInput.date,
      hint: correction
          ? 'Der Gültigkeitsbeginn bleibt bei einer Korrektur unverändert.'
          : null,
    ),
    choice('employment_kind', {
      'regular': 'Reguläre Beschäftigung',
      'minijob': 'Gewerblicher Minijob',
    }),
    field('date_of_birth', type: BusinessInput.date),
    choice('federal_state', _federalStates),
    field(
      'tax_class',
      type: BusinessInput.integer,
      hint: '1 bis 6; kein automatischer ELStAM-Abruf',
    ),
    field(
      'tax_children_half_units',
      type: BusinessInput.integer,
      hint: 'Eine Einheit entspricht 0,5; bekannte 0 ausdrücklich eingeben.',
    ),
    choice('church_tax', {
      'none': 'Keine Kirchensteuer',
      'standard': 'Regulärer Satz des Bundeslands',
    }),
    choice('health_insurance', {
      'statutory_mandatory': 'Gesetzlich pflichtversichert',
      'statutory_other': 'Sonstige gesetzliche Versicherung',
      'private': 'Privat versichert',
    }),
    field('health_fund'),
    field(
      'health_additional_percent',
      type: BusinessInput.decimal,
      hint: 'Tatsächlich gültiger Kassenwert; Durchschnittswert wird nicht vorgegeben.',
    ),
    choice('has_children', {'yes': 'Ja', 'no': 'Nein'}),
    field('pv_children_under_25', type: BusinessInput.integer),
    choice('u1_required', {'yes': 'Ja', 'no': 'Nein'}),
    field('u1_percent', type: BusinessInput.decimal),
    field('u2_percent', type: BusinessInput.decimal),
    choice('minijob_rv_exempt', {'yes': 'Ja', 'no': 'Nein'}),
    choice('minijob_tax', {
      'flat_2_employer':
          'Gewerblicher Minijob: Arbeitgeber trägt 2 % Pauschsteuer',
      'individual':
          'Individuelle Lohnsteuer (regulär; Minijob nicht unterstützt)',
    }),
    choice('pension_other_compulsory', {'yes': 'Ja', 'no': 'Nein'}),
    const BusinessField(
      'annual_gross',
      'Ausdrücklich geprüftes regelmäßiges Jahresbrutto (€)',
      type: BusinessInput.decimal,
      required: true,
    ),
    const BusinessField(
      'special_cases',
      'Geprüfte Sonderfälle',
      type: BusinessInput.multiple,
      choices: payrollSpecialCases,
      hint: 'Faktorverfahren zusätzlich über den Steuerumfang mit gültigem Faktor erfassen. Weitere Fälle benötigen gegebenenfalls eine gesonderte Berechnung.',
    ),
    field('verification_note'),
    const BusinessField(
      'regular_tax_scope',
      'Steuerberechnungsumfang ausdrücklich wählen',
      type: BusinessInput.choice,
      required: true,
      choices: {
        '': 'Bitte ausdrücklich wählen',
        'standard':
            'Regulär: Standard-Lohnsteuer mit geprüften ELStAM-Beträgen',
        'factor': 'Regulär: Steuerklasse IV mit eingetragenem Faktor',
        'social_only': 'Regulär: Nur Sozialversicherung, Netto bleibt offen',
        'minijob': 'Minijob: Pauschsteuerverfahren',
      },
    ),
    BusinessField(
      'tax_factor',
      _profileLabels['tax_factor']!,
      hint: 'Nur beim Faktorverfahren: genau drei Nachkommastellen aus dem gültigen Nachweis. Frei- und Hinzurechnungsbetrag ausdrücklich 0.',
    ),
    for (final key in [
      'tax_allowance_monthly_minor',
      'tax_addition_monthly_minor',
    ])
      BusinessField(
        key,
        _profileLabels[key]!,
        type: BusinessInput.decimal,
        hint: 'Bei regulärer Standard-Lohnsteuer ausdrücklich angeben, auch bekannte 0.',
      ),
    const BusinessField(
      'transition_scope',
      'Übergangsbereich ausdrücklich beurteilen',
      type: BusinessInput.choice,
      required: true,
      choices: {
        '': 'Bitte ausdrücklich wählen',
        'none': 'Keine belegte Übergangsbereichsprognose · bisheriger Umfang',
        'monthly': 'Belegter Übergangsbereich · regulärer Vollmonat 2026',
      },
    ),
    const BusinessField(
      'transition_assessed_on',
      'Datum der belegten Übergangsbereichsprüfung',
      type: BusinessInput.date,
    ),
    const BusinessField(
      'transition_regular_monthly',
      'Prognostiziertes regelmäßiges Monatsbrutto (€)',
      type: BusinessInput.decimal,
      hint: '603,01 bis 2.000,00 €. Die Prognose bestimmt den Status, nicht das schwankende tatsächliche Monatsentgelt.',
    ),
    const BusinessField(
      'transition_forecast_months',
      'Prognosezeitraum ausdrücklich wählen',
      type: BusinessInput.choice,
      choices: {
        '': 'Bitte ausdrücklich wählen',
        '12': 'Zwölf belegte Prognosemonate',
      },
    ),
    const BusinessField(
      'transition_one_off',
      'Vorhersehbare Einmalzahlungen laut Prognose',
      type: BusinessInput.choice,
      choices: {
        '': 'Bitte ausdrücklich wählen',
        'no': 'Nein, ausdrücklich geprüft',
        'yes': 'Ja · dieser Berechnungsfall bleibt gesperrt',
      },
    ),
    const BusinessField(
      'transition_note',
      'Grundlage der belegten Übergangsbereichsprognose',
      hint: 'Dasselbe ausgewählte Personaloriginal muss Prognose, Statusprüfung und Versicherungsmerkmale belegen.',
    ),
    BusinessField(
      'source_file_id',
      'Geschütztes Personaloriginal als Nachweis',
      type: BusinessInput.choice,
      required: true,
      choices: {
        '': 'Original ausdrücklich wählen',
        for (final file in files.where((f) => f['purpose'] == 'personnel'))
          '${file['id']}': '${file['filename']}',
      },
    ),
    if (correction)
      const BusinessField(
        'correction_reason',
        'Begründung der Korrektur',
        required: true,
      ),
    const BusinessField(
      'confirmed',
      'Ich habe die persönlichen Steuer-/Versicherungsmerkmale, Sonderfälle und gültigen Nachweise geprüft.',
      type: BusinessInput.toggle,
    ),
  ];
}

class BusinessPayrollPage extends StatefulWidget {
  const BusinessPayrollPage({
    super.key,
    required this.session,
    required this.employee,
  });
  final BusinessSession session;
  final Map<String, dynamic> employee;
  @override
  State<BusinessPayrollPage> createState() => _BusinessPayrollPageState();
}

class _BusinessPayrollPageState extends State<BusinessPayrollPage>
    with WidgetsBindingObserver {
  List<Map<String, dynamic>> profiles = [],
      preparations = [],
      runs = [],
      files = [],
      history = [];
  Map<String, dynamic>? preview, inputs, correction, runDraft, rules;
  late Map<String, dynamic> employee;
  Map<String, dynamic>? yearView;
  Object? generation;
  String? actorId, error, message, historyKind;
  bool loading = false, busy = false, denied = false, accepted = false;
  int epoch = 0;
  bool suspended = false, approvalState = false;
  final privateRoutes = <Route<dynamic>>[];
  bool currentContext(BusinessSession owner, String person, int ticket) =>
      mounted &&
      identical(session, owner) &&
      employeeId == person &&
      epoch == ticket &&
      !suspended;
  final previews = <MailAttachmentPreviewController>[];
  BusinessSession get session => widget.session;
  String get employeeId => widget.employee['id'];
  String key(bool profile) =>
      'payroll-${profile ? 'profile' : 'run'}-$employeeId';
  bool get readable =>
      !suspended &&
      !denied &&
      payrollAvailable(session) &&
      (session.can('personnel.read') ||
          (actorId != null &&
              employee['user_id'] == actorId &&
              session.can('time.own')));
  bool write(String permission) =>
      readable &&
      session.can('personnel.read') &&
      session.canWrite(permission) &&
      session.sectionEnabled('personnel');
  bool get pendingProfile => session.pending(key(true));
  bool get pendingRun => session.pending(key(false));
  bool get canPreview =>
      readable &&
      session.can('personnel.read') &&
      !loading &&
      !busy &&
      !pendingRun;
  @override
  void initState() {
    super.initState();
    employee = _copy(widget.employee);
    generation = session.generation;
    session.addListener(changed);
    approvalState = session.can('personnel.approve');
    WidgetsBinding.instance.addObserver(this);
    load();
  }

  @override
  void didUpdateWidget(covariant BusinessPayrollPage oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (!identical(oldWidget.session, session) ||
        oldWidget.employee['id'] != employeeId) {
      oldWidget.session.removeListener(changed);
      session.addListener(changed);
      dismissPrivateRoutes();
      clear();
      employee = _copy(widget.employee);
      actorId = null;
      denied = false;
      error = message = null;
      generation = session.generation;
      approvalState = session.can('personnel.approve');
      if (!suspended) unawaited(load());
    }
  }

  void dismissPrivateRoutes() {
    final routes = privateRoutes.toList().reversed.toList();
    privateRoutes.clear();
    void remove() {
      for (final route in routes) {
        final navigator = route.navigator;
        if (navigator == null || !route.isActive) continue;
        // A case editor lives above its source page in the root navigator.
        // Close those owned descendants before removing the source page.
        navigator.popUntil((candidate) => identical(candidate, route));
        if (route.isActive) navigator.removeRoute(route);
      }
    }

    // didUpdateWidget runs during build. The context epoch is invalidated
    // synchronously; navigator animation notifications must wait for its end.
    if (WidgetsBinding.instance.schedulerPhase ==
        SchedulerPhase.persistentCallbacks) {
      WidgetsBinding.instance.addPostFrameCallback((_) => remove());
    } else {
      remove();
    }
  }

  Future<T?> privateRoute<T>(Route<T> route) async {
    privateRoutes.add(route);
    try {
      return await Navigator.of(context, rootNavigator: true).push(route);
    } finally {
      privateRoutes.remove(route);
    }
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state == AppLifecycleState.hidden ||
        state == AppLifecycleState.paused) {
      suspended = true;
      dismissPrivateRoutes();
      if (mounted) setState(clear);
    } else if (state == AppLifecycleState.resumed && suspended && mounted) {
      setState(() => suspended = false);
      unawaited(load(refresh: true));
    }
  }

  @override
  void dispose() {
    epoch++;
    dismissPrivateRoutes();
    session.removeListener(changed);
    WidgetsBinding.instance.removeObserver(this);
    for (final p in previews) p.revoke();
    super.dispose();
  }

  void clear() {
    epoch++;
    profiles = [];
    preparations = [];
    runs = [];
    files = [];
    history = [];
    rules = preview = inputs = correction = runDraft = null;
    yearView = null;
    accepted = false;
    loading = busy = false;
    error = message = historyKind = null;
    for (final p in previews) p.revoke();
  }

  void changed() {
    if (!mounted) return;
    final approvalLost = approvalState && !session.can('personnel.approve');
    approvalState = session.can('personnel.approve');
    if (!payrollAvailable(session) ||
        approvalLost ||
        (actorId != null && !readable) ||
        generation != session.generation) {
      dismissPrivateRoutes();
      clear();
      generation = session.generation;
    } else if (!session.can('personnel.read')) {
      if (payrollStatementsAvailable(session)) clear();
      preview = inputs = runDraft = null;
      accepted = false;
      for (final p in previews) p.revoke();
    }
    setState(() {});
  }

  void failure(Object e) {
    if (!mounted) return;
    setState(() {
      if (e is ApiException && [401, 403, 404].contains(e.status)) {
        clear();
        denied = true;
      }
      error = e is ApiException
          ? e.message
          : e is FormatException
          ? e.message
          : '$e';
    });
  }

  Future<void> load({bool refresh = false}) async {
    if (refresh) {
      await session.load();
      if (!mounted) return;
      denied = false;
    }
    if (!payrollAvailable(session)) return;
    if (payrollStatementsAvailable(session) && !session.can('personnel.read')) {
      if (mounted) setState(() => loading = false);
      return;
    }
    final captured = ++epoch;
    setState(() {
      loading = true;
      error = null;
    });
    try {
      final me = businessMap(await session.api.call('/api/me')),
          team = businessItems(await session.read('/employees'));
      final person = team.where((p) => p['id'] == employeeId).firstOrNull;
      if (!mounted || captured != epoch) return;
      if (person == null)
        throw const ApiException(
          403,
          'Das aktuelle Mitarbeiterprofil ist nicht freigegeben.',
        );
      actorId = me['id'];
      employee = person;
      if (!readable)
        throw const ApiException(
          403,
          'Dieser Mitarbeiter ist nicht für den Zugang freigegeben.',
        );
      final query = 'employee_id=$employeeId';
      final result = await Future.wait([
        session.read('/payroll/profiles?$query'),
        session.read('/payroll/runs?$query'),
        session.read('/personnel/files?$query'),
        session.read('/personnel/payroll-preparations?$query'),
        if (session.can('personnel.read')) session.read('/payroll/rules'),
      ]);
      for (final value in result.take(4)) {
        if (businessMap(value)['employee_id'] != employeeId ||
            businessItems(value).any((v) => v['employee_id'] != employeeId))
          throw const ApiException(
            0,
            'Die Payroll-Antwort gehört nicht zu diesem Mitarbeiter.',
          );
      }
      for (final record in businessItems(result[1])) {
        payrollCalculation(record['calculation']);
        if (record.containsKey('settlement_transition'))
          payrollSettlementTransition(record);
      }
      if (!mounted || captured != epoch || !readable) return;
      setState(() {
        profiles = businessItems(result[0]);
        runs = businessItems(result[1]);
        files = businessItems(result[2]);
        preparations = businessItems(result[3]);
        rules = result.length == 5 ? businessMap(result[4]) : null;
      });
    } catch (e) {
      if (mounted && captured == epoch) failure(e);
    } finally {
      if (mounted && captured == epoch) setState(() => loading = false);
    }
  }

  Future<void> fresh({String? permission}) async {
    final owner = session, person = employeeId, ticket = epoch;
    await owner.load();
    if (!currentContext(owner, person, ticket))
      throw const ApiException(
        409,
        'Die private Lohnansicht wurde gewechselt.',
      );
    if (!mounted || !readable || session.error != null)
      throw const ApiException(
        403,
        'Die aktuellen Personalrechte sind nicht bestätigt.',
      );
    if (permission != null &&
        (permission == 'personnel.export'
            ? !session.can('personnel.read') || !session.can('personnel.export')
            : !write(permission)))
      throw const ApiException(
        403,
        'Die aktuelle Personalberechtigung für diesen Vorgang fehlt.',
      );
    final page = businessMap(
      await owner.read('/payroll/profiles?employee_id=$person'),
    );
    if (!currentContext(owner, person, ticket))
      throw const ApiException(
        409,
        'Die private Lohnansicht wurde gewechselt.',
      );
    if (page['employee_id'] != person)
      throw const ApiException(
        0,
        'Der Mitarbeiterbezug konnte nicht bestätigt werden.',
      );
  }

  Future<void> repeat(bool profile) async {
    if (busy || !write(profile ? 'personnel.write' : 'personnel.approve'))
      return;
    final owner = session, person = employeeId, ticket = epoch;
    setState(() {
      busy = true;
      error = null;
    });
    try {
      await session.repeatPayrollCommand(employeeId, profile: profile);
      if (!currentContext(owner, person, ticket) || !readable) return;
      setState(() {
        busy = false;
        message = 'Der ursprüngliche Payroll-Auftrag ist bestätigt.';
        preview = inputs = null;
        accepted = false;
      });
      await load();
    } catch (e) {
      if (currentContext(owner, person, ticket)) failure(e);
    } finally {
      if (currentContext(owner, person, ticket)) setState(() => busy = false);
    }
  }

  Future<void> profile([Map<String, dynamic>? previous]) async {
    if (!write('personnel.write') || pendingProfile || busy) return;
    final rvOpening = session.generation;
    final rvSources = payrollRvReadable(session)
        ? payrollRvSources(
            await session.read(
              '$payrollRvPath/sources?employee_id=$employeeId',
            ),
            employeeId,
          )
        : null;
    if (!mounted || !readable || rvOpening != session.generation) return;
    final previousProfile = businessMap(previous?['profile']);
    final initial = <String, dynamic>{
      ...previousProfile,
      for (final k in _booleanFields)
        k: previousProfile[k] == null
            ? ''
            : previousProfile[k] == true
            ? 'yes'
            : 'no',
      'annual_gross': _inputMoney(
        previousProfile['regular_annual_gross_minor'],
      ),
      'regular_tax_scope': previous == null
          ? ''
          : previousProfile['employment_kind'] == 'minijob'
          ? 'minijob'
          : previousProfile.containsKey('tax_factor')
          ? 'factor'
          : previousProfile.containsKey('tax_allowance_monthly_minor')
          ? 'standard'
          : 'social_only',
      for (final key in [
        'tax_allowance_monthly_minor',
        'tax_addition_monthly_minor',
      ])
        key: _inputMoney(previousProfile[key]),
      'transition_scope': previous == null
          ? ''
          : previousProfile['transition_assessment'] == null
          ? 'none'
          : 'monthly',
      'transition_assessed_on':
          previousProfile['transition_assessment']?['assessed_on'],
      'transition_regular_monthly': _inputMoney(
        previousProfile['transition_assessment']?['regular_monthly_gross_minor'],
      ),
      'transition_forecast_months':
          previousProfile['transition_assessment']?['forecast_months'] == 12
          ? '12'
          : '',
      'transition_one_off': previousProfile['transition_assessment'] == null
          ? ''
          : previousProfile['transition_assessment']['foreseeable_one_off_payments'] ==
                true
          ? 'yes'
          : 'no',
      'transition_note':
          previousProfile['transition_assessment']?['note'] ?? '',
      'source_file_id': previous?['source_file']?['id'] ?? '',
      'confirmed': false,
    };
    final opening = session.generation;
    await showDialog<void>(
      context: context,
      builder: (_) => BusinessEditor(
        session: session,
        title: previous == null
            ? 'Lohnprofil mit Originalnachweis'
            : 'Lohnprofil nachvollziehbar korrigieren',
        fields: [
          ...payrollProfileFields(files, correction: previous != null),
          if (rvSources != null &&
              businessItems(rvSources['history']).isNotEmpty)
            BusinessField(
              'rv_lifecycle_id',
              'Aktueller RV-Nachweis für den Minijob',
              type: BusinessInput.choice,
              choices: {
                for (final r in [businessItems(rvSources['history']).last])
                  payrollRvSelection(r):
                      'Geprüfter RV-Verlauf · Fassung ${r['revision']}',
              },
              hint: 'Bei einem aufgenommenen RV-Verlauf die aktuelle Originalfassung ausdrücklich an diesem Minijobprofil binden.',
            ),
        ],
        initial: initial,
        readPermission: 'personnel.read',
        writePermission: 'personnel.write',
        readAllowed: () => readable && opening == session.generation,
        pendingKey: key(true),
        saveLabel: 'Geprüftes Lohnprofil speichern',
        onSave: (values) async {
          if (values['confirmed'] != true)
            throw const FormatException(
              'Die geprüften persönlichen Merkmale und Nachweise ausdrücklich bestätigen.',
            );
          await fresh(permission: 'personnel.write');
          if (opening != session.generation)
            throw const ApiException(
              409,
              'Datenstand geändert. Personalquellen neu laden.',
            );
          if (pendingProfile) {
            await session.repeatPayrollCommand(employeeId, profile: true);
            return;
          }
          final file = files
              .where(
                (f) =>
                    f['id'] == values['source_file_id'] &&
                    f['employee_id'] == employeeId &&
                    f['purpose'] == 'personnel',
              )
              .firstOrNull;
          if (file == null)
            throw const FormatException(
              'Einen freigegebenen Personalaktennachweis auswählen.',
            );
          final body = <String, dynamic>{
            'employee_id': employeeId,
            'revision': previous?['revision'] ?? 0,
            'profile': payrollProfileInput(values),
            'source_file_id': file['id'],
            'confirmed': true,
            if (previous != null) 'id': previous['id'],
            if (previous != null)
              'correction_reason': '${values['correction_reason']}'.trim(),
          };
          if (body['profile']['employment_kind'] == 'minijob' &&
              session.hasFeature('payroll_rv_lifecycle')) {
            final current = payrollRvSources(
              await session.read(
                '$payrollRvPath/sources?employee_id=$employeeId',
              ),
              employeeId,
            );
            if (!mounted || !readable || opening != session.generation)
              throw const ApiException(
                403,
                'Die private Profilansicht wurde geschlossen.',
              );
            body.addAll(payrollRvProfileBinding(current, values));
          }
          await session.command(
            key(true),
            '/payroll/profiles',
            body,
            validateResult: payrollReceiptValidator(
              body,
              previous: previous,
              original: file,
            ),
          );
        },
      ),
    );
    if (mounted && readable) await load();
  }

  Future<void> calculate([Map<String, dynamic>? previous]) async {
    if (previous?['source']?['source_schema_version'] == 5)
      return openMultipleCases(previous);
    if (previous?['source']?['source_schema_version'] == 4)
      return chooseOneOffCorrection(previous!);
    if (previous?['source']?['source_schema_version'] == 3)
      return chooseCompositeCorrection(previous!);
    if (previous?['source']?['source_schema_version'] == 2)
      return choosePeriodCorrection(previous!);
    if (!canPreview) return;
    final sameDraft = correction?['id'] == previous?['id'];
    final old = businessMap(previous?['source']?['input']);
    final initial = <String, dynamic>{
      ...old,
      'gross': _inputMoney(old['gross_minor']),
      'full_month_confirmed': false,
      if (sameDraft && runDraft != null) ...runDraft!,
    };
    final opening = session.generation;
    final availablePreparations = preparations.where(
      (p) => previous == null || p['month'] == previous['source']['month'],
    );
    await showDialog<void>(
      context: context,
      builder: (_) => BusinessEditor(
        session: session,
        title: previous == null
            ? 'Belegte Monatsberechnung prüfen'
            : 'Historischen Monat korrigieren',
        readPermission: 'personnel.read',
        readAllowed: () => readable && opening == session.generation,
        fields: [
          BusinessField(
            'profile_id',
            'Geprüftes gültiges Lohnprofil',
            type: BusinessInput.choice,
            required: true,
            choices: {
              '': 'Profil ausdrücklich auswählen',
              for (final p in profiles)
                '${p['id']}':
                    'Ab ${businessDate(p['profile']['effective_from'])} · ${p['profile']['employment_kind'] == 'minijob' ? 'Minijob' : 'Regulär'} · Fassung ${p['revision']}',
            },
          ),
          BusinessField(
            'preparation_id',
            'Abgeschlossene HR-Monatsquelle',
            type: BusinessInput.choice,
            required: true,
            choices: {
              '': 'Monatsfassung ausdrücklich auswählen',
              for (final p in availablePreparations)
                '${p['id']}': '${p['month']} · Fassung ${p['revision']}',
            },
          ),
          const BusinessField(
            'gross',
            'Geprüftes Brutto aus Vereinbarung und Monatsquellen (€)',
            type: BusinessInput.decimal,
            required: true,
          ),
          const BusinessField(
            'full_month_confirmed',
            'Vollständigen Versicherungsmonat geprüft; Ein-/Austritt, Abwesenheiten und Sonderfälle abgeglichen.',
            type: BusinessInput.toggle,
          ),
          if (previous != null)
            const BusinessField(
              'correction_reason',
              'Nachvollziehbarer Korrekturgrund',
              required: true,
            ),
        ],
        initial: initial,
        saveLabel: 'Berechnungsumfang unverbindlich prüfen',
        onSave: (values) async {
          await fresh();
          if (!session.can('personnel.read') || opening != session.generation)
            throw const ApiException(
              403,
              'Die Berechnung benötigt aktuelle Personal-Leserechte.',
            );
          if (pendingRun)
            throw const ApiException(
              409,
              'Zuerst die offene Berechnung unverändert klären.',
            );
          final p = profiles
                  .where((p) => p['id'] == values['profile_id'])
                  .firstOrNull,
              prep = availablePreparations
                  .where((p) => p['id'] == values['preparation_id'])
                  .firstOrNull;
          if (p == null || prep == null)
            throw const FormatException(
              'Aktuelles Lohnprofil und passende Monatsvorbereitung wählen.',
            );
          final input = <String, dynamic>{
            'employee_id': employeeId,
            'profile_id': p['id'],
            'profile_revision': p['revision'],
            'preparation_id': prep['id'],
            'preparation_revision': prep['revision'],
            'gross_minor': personnelMinor(values['gross']),
            'full_month_confirmed': values['full_month_confirmed'] == true,
          };
          final value = payrollPreview(
            await session.api.call(session.path('/payroll/preview'), input),
            input,
          );
          if (!mounted || !readable || opening != session.generation) return;
          setState(() {
            preview = value;
            inputs = input;
            correction = previous;
            runDraft = _copy(values);
            accepted = false;
            error = message = null;
          });
        },
      ),
    );
  }

  Future<void> calculatePeriod(
    Map<String, dynamic> fact, {
    Map<String, dynamic>? previous,
    String reason = '',
    bool Function()? mayContinue,
  }) async {
    if (mayContinue?.call() == false) return;
    final owner = session, person = employeeId, ticket = epoch;
    try {
      await fresh();
      if (!currentContext(owner, person, ticket)) return;
      if (fact['rule_version'] == payrollFactorOneOffRule &&
          !session.hasFeature(payrollFactorOneOffFeature))
        throw const ApiException(
          403,
          'Die aktuelle Freigabe für den Faktor-Einmalbezug fehlt.',
        );
      if (fact['rule_version'] == payrollFactorTransitionPeriodRule &&
          !session.hasFeature(payrollFactorTransitionPeriodFeature))
        throw const ApiException(
          403,
          'Die aktuelle Freigabe für den Faktor-/Midijob-Teilmonat fehlt.',
        );
      if (fact['rule_version'] == payrollFactorTransitionRule &&
          !session.hasFeature(payrollFactorTransitionFeature))
        throw const ApiException(
          403,
          'Die aktuelle Freigabe für den Faktor-Midijob fehlt.',
        );
      if (fact['rule_version'] == payrollFactorClaimTravelRule &&
          !session.hasFeature(payrollFactorClaimTravelFeature))
        throw const ApiException(
          403,
          'Die aktuelle Freigabe für den gemeinsamen Faktor-/Anspruchs-/Reisefall fehlt.',
        );
      if (fact['employee_id'] != person)
        throw const ApiException(
          403,
          'Der Lohnfall gehört nicht zum gewählten Mitarbeiter.',
        );
      if (!session.can('personnel.read') || !canPreview)
        throw const ApiException(
          403,
          'Aktuelle Personal-Leserechte und geklärte Berechnung erforderlich.',
        );
      if (['one_off_case', 'multiple_one_off_case'].contains(fact['kind']) &&
          previous == null) {
        final current = runs
            .where((r) => r['source']?['month'] == fact['details']['month'])
            .toList();
        if (current.length > 1)
          throw const ApiException(
            409,
            'Der vorhandene Monatslauf ist nicht eindeutig.',
          );
        if (current.isNotEmpty)
          return await oneOffCorrectionReason(fact, current.single);
      }
      final opening = session.generation,
          input = fact['kind'] == 'multiple_one_off_case'
              ? payrollMultipleCaseRunInput(fact)
              : fact['kind'] == 'one_off_case'
              ? payrollOneOffCaseRunInput(fact)
              : fact['kind'] == 'calculation_case'
              ? payrollCalculationCaseRunInput(fact)
              : payrollFactRunInput(fact);
      if (previous?['source']?['source_schema_version'] == 5 &&
          session.hasFeature(payrollPositiveCorrectionFeature) &&
          fact['kind'] == 'multiple_one_off_case') {
        final page = businessMap(
          await session.read('/payroll/account-records?employee_id=$person'),
        );
        if (!currentContext(owner, person, ticket) ||
            !readable ||
            opening != session.generation ||
            mayContinue?.call() == false)
          return;
        if (page['employee_id'] != person)
          throw const ApiException(
            403,
            'Die bisherigen Zahlungen gehören nicht zum ausgewählten Mitarbeiter.',
          );
        final paid =
            businessItems(page).where((record) {
              payrollAccountRecord(record, person);
              return record['kind'] == 'payment' &&
                  record['details']['run_id'] == previous!['id'] &&
                  record['details']['run_revision'] <= previous['revision'];
            }).toList()..sort((a, b) {
              final order = (a['details']['run_revision'] as int).compareTo(
                b['details']['run_revision'],
              );
              return order != 0
                  ? order
                  : (a['revision'] as int).compareTo(b['revision']);
            });
        if (paid.isNotEmpty &&
            paid.last['sources']?['run']?['source']?['source_schema_version'] ==
                5) {
          final review = await positiveSettlementReview(
            owner,
            person,
            ticket,
            mayContinue: mayContinue,
          );
          if (review == null ||
              !currentContext(owner, person, ticket) ||
              mayContinue?.call() == false)
            return;
          input['settlement_review'] = review;
        }
      }
      if (input['settlement_review']?['schema_version'] == 3) {
        await fresh(permission: 'personnel.approve');
        if (!session.hasFeature(payrollAdjustmentFeature))
          throw const ApiException(
            403,
            'Die aktuelle Freigabe für weitere Nettoausgleiche fehlt.',
          );
      }
      if (input['settlement_review']?['schema_version'] == 2) {
        await fresh(permission: 'personnel.approve');
        if (!session.hasFeature(payrollRepaymentFeature))
          throw const ApiException(
            403,
            'Die aktuelle Freigabe für belegte Netto-Rückzahlungen fehlt.',
          );
      }
      final value = payrollPreview(
        await session.api.call(session.path('/payroll/preview'), input),
        input,
      );
      if (mayContinue?.call() == false) return;
      if (value.containsKey('settlement_transition')) {
        if (!session.hasFeature(payrollPositiveCorrectionFeature) ||
            !session.hasModule('payroll_multiple_cases'))
          throw const ApiException(
            409,
            'Dieser Server unterstützt den belegten positiven Korrekturvertrag noch nicht.',
          );
        final transition = payrollSettlementTransition(value);
        if (previous == null ||
            !payrollSame(
              transition['previous_run_ref'],
              payrollFactRef(previous),
            ))
          throw const ApiException(
            409,
            'Die unmittelbar vorherige Monatsfassung wurde geändert. Bitte erneut auswählen.',
          );
      }
      if (!currentContext(owner, person, ticket) ||
          !readable ||
          opening != session.generation ||
          mayContinue?.call() == false)
        return;
      await fresh();
      if (!currentContext(owner, person, ticket) ||
          !readable ||
          opening != session.generation ||
          mayContinue?.call() == false)
        return;
      setState(() {
        preview = value;
        inputs = input;
        correction = previous;
        runDraft = {'correction_reason': reason};
        accepted = false;
        error = message = null;
      });
    } catch (error) {
      if (currentContext(owner, person, ticket)) rethrow;
    }
  }

  Future<void> oneOffCorrectionReason(
    Map<String, dynamic> fact,
    Map<String, dynamic> previous,
  ) async {
    if (!mounted || !readable || !canPreview) return;
    final owner = session, person = employeeId, ticket = epoch;
    late final DialogRoute<void> correctionRoute;
    correctionRoute = DialogRoute<void>(
      context: context,
      builder: (_) => BusinessEditor(
        session: owner,
        title: 'Monatslauf mit Einmalbezug korrigieren',
        fields: const [
          BusinessField(
            'reason',
            'Nachvollziehbarer Korrekturgrund',
            required: true,
          ),
        ],
        readPermission: 'personnel.read',
        writePermission: 'personnel.read',
        readAllowed: () =>
            currentContext(owner, person, ticket) &&
            readable &&
            owner.can('personnel.approve'),
        onSave: (values) async {
          if (!currentContext(owner, person, ticket))
            throw const ApiException(
              403,
              'Die private Lohnansicht wurde gewechselt.',
            );
          await calculatePeriod(
            fact,
            previous: previous,
            reason: values['reason'],
            mayContinue: () => correctionRoute.isActive,
          );
        },
      ),
    );
    await privateRoute<void>(correctionRoute);
  }

  Future<void> openOneOffCases([
    Map<String, dynamic>? previous,
    bool factorMode = false,
  ]) async {
    if (!canPreview) return;
    final owner = session,
        person = employeeId,
        ticket = epoch,
        originalEmployee = _copy(employee);
    Map<String, dynamic>? chosen;
    try {
      await privateRoute<void>(
        MaterialPageRoute<void>(
          builder: (_) => BusinessPayrollOneoffCasesPage(
            session: owner,
            employee: originalEmployee,
            initialMonth: previous?['source']?['month'],
            factorMode:
                factorMode ||
                previous?['calculation']?['rule_version'] ==
                    payrollFactorOneOffRule,
            onOriginal: (file) async {
              if (currentContext(owner, person, ticket)) await original(file);
            },
            onCalculate: (fact) async {
              if (!currentContext(owner, person, ticket))
                throw const ApiException(
                  403,
                  'Die private Lohnansicht wurde gewechselt.',
                );
              if (previous != null &&
                  fact['details']['one_off_earning_ref']['id'] !=
                      previous['source']['one_off_case']['details']['one_off_earning_ref']['id']) {
                throw const ApiException(
                  409,
                  'Die Korrektur muss denselben ursprünglichen Einmalanspruch binden.',
                );
              }
              chosen = _copy(fact);
              Navigator.pop(context);
            },
          ),
        ),
      );
      if (!currentContext(owner, person, ticket) || !readable || chosen == null)
        return;
      await load();
      if (!currentContext(owner, person, ticket + 1) || !readable) return;
      if (previous != null)
        await oneOffCorrectionReason(chosen!, previous);
      else
        await calculatePeriod(chosen!);
    } catch (error) {
      if (mounted &&
          identical(owner, session) &&
          person == employeeId &&
          !suspended &&
          (epoch == ticket || epoch == ticket + 1))
        failure(error);
    }
  }

  Future<Map<String, dynamic>?> positiveSettlementReview(
    BusinessSession owner,
    String person,
    int ticket, {
    bool Function()? mayContinue,
  }) async {
    if (!currentContext(owner, person, ticket) ||
        !readable ||
        mayContinue?.call() == false)
      return null;
    Map<String, dynamic>? acceptedReview;
    late final DialogRoute<void> reviewRoute;
    reviewRoute = DialogRoute<void>(
      context: context,
      builder: (_) => BusinessEditor(
        session: session,
        title: 'Zahlungen und Abführungen vollständig prüfen',
        readPermission: 'personnel.read',
        readAllowed: () =>
            currentContext(owner, person, ticket) &&
            readable &&
            reviewRoute.isActive &&
            mayContinue?.call() != false,
        fields: [
          if (session.hasFeature(payrollRepaymentFeature) ||
              session.hasFeature(payrollAdjustmentFeature))
            BusinessField(
              'settlement_kind',
              'Belegte Richtung des Nettoausgleichs',
              type: BusinessInput.choice,
              choices: {
                'positive': 'Zusätzliche positive Nettozahlung',
                if (session.hasFeature(payrollRepaymentFeature))
                  'repayment': 'Tatsächliche Rückzahlung des Beschäftigten',
                if (session.hasFeature(payrollAdjustmentFeature))
                  'adjustment':
                      'Weiterer Nettoausgleich nach belegter Rückzahlung',
              },
            ),
          const BusinessField(
            'payments_complete',
            'Sämtliche tatsächlich erfolgten Zahlungen für diesen Monat, einschließlich externer Vorgänge, sind vollständig im Programm belegt.',
            type: BusinessInput.toggle,
          ),
          const BusinessField(
            'remittances_complete',
            'Sämtliche tatsächlich erfolgten Steuer- und Beitragsabführungen, einschließlich externer Vorgänge, sind vollständig im Programm belegt.',
            type: BusinessInput.toggle,
          ),
          BusinessField(
            'evidence_file',
            'Geschützter Nachweis des vollständigen Abgleichs',
            type: BusinessInput.choice,
            required: true,
            choices: {
              '': 'Original ausdrücklich auswählen',
              for (final f in files.where((f) => f['employee_id'] == person))
                '${f['id']}': '${f['filename']}',
            },
            hint: 'Wenn keine Abführungen erfasst sind, muss der Originalnachweis ausdrücklich bestätigen, dass keine erfolgt sind.',
          ),
        ],
        initial: const {
          'settlement_kind': 'positive',
          'payments_complete': false,
          'remittances_complete': false,
          'evidence_file': '',
        },
        saveLabel: 'Vollständigen Abgleich bestätigen',
        onSave: (values) async {
          if (values['payments_complete'] != true ||
              values['remittances_complete'] != true)
            throw const FormatException(
              'Beide vollständigen Abgleiche ausdrücklich bestätigen.',
            );
          await fresh();
          if (!currentContext(owner, person, ticket) ||
              !reviewRoute.isActive ||
              mayContinue?.call() == false ||
              !session.hasFeature(payrollPositiveCorrectionFeature))
            throw const ApiException(
              403,
              'Der private Korrekturkontext ist nicht mehr verfügbar.',
            );
          final originals = businessItems(
            await session.read('/personnel/files?employee_id=$person'),
          );
          if (!currentContext(owner, person, ticket) ||
              !readable ||
              !reviewRoute.isActive ||
              mayContinue?.call() == false ||
              !session.hasFeature(payrollPositiveCorrectionFeature))
            throw const ApiException(
              403,
              'Der private Korrekturkontext ist nicht mehr verfügbar.',
            );
          final file = originals
              .where(
                (f) =>
                    f['id'] == values['evidence_file'] &&
                    f['employee_id'] == person,
              )
              .firstOrNull;
          if (file == null)
            throw const FormatException(
              'Ein zugängliches geschütztes Original für diesen Mitarbeiter auswählen.',
            );
          final repayment = values['settlement_kind'] == 'repayment';
          final adjustment = values['settlement_kind'] == 'adjustment';
          if (adjustment && !session.hasFeature(payrollAdjustmentFeature))
            throw const ApiException(
              403,
              'Die aktuelle Freigabe für weitere Nettoausgleiche fehlt.',
            );
          if (repayment && !session.hasFeature(payrollRepaymentFeature))
            throw const ApiException(
              403,
              'Die aktuelle Freigabe für belegte Netto-Rückzahlungen fehlt.',
            );
          acceptedReview = payrollSettlementReview({
            'schema_version': adjustment
                ? 3
                : repayment
                ? 2
                : 1,
            if (adjustment) 'contract': payrollAdjustmentReviewContract,
            if (repayment) 'contract': payrollRepaymentReviewContract,
            'payments_complete': values['payments_complete'],
            'remittances_complete': values['remittances_complete'],
            'evidence_ref': {
              'id': file['id'],
              'revision': 1,
              'content_hash': file['content_hash'],
            },
          });
        },
      ),
    );
    await privateRoute<void>(reviewRoute);
    return acceptedReview;
  }

  Future<void> openMultipleCases([Map<String, dynamic>? previous]) async {
    if (!canPreview) return;
    final owner = session,
        person = employeeId,
        ticket = epoch,
        originalEmployee = _copy(employee);
    Map<String, dynamic>? chosen;
    try {
      await privateRoute<void>(
        MaterialPageRoute<void>(
          builder: (_) => BusinessPayrollMultipleCasesPage(
            session: owner,
            employee: originalEmployee,
            initialMonth: previous?['source']?['month'],
            onOriginal: (file) async {
              if (currentContext(owner, person, ticket)) await original(file);
            },
            onCalculate: (fact) async {
              if (!currentContext(owner, person, ticket))
                throw const ApiException(
                  403,
                  'Die private Lohnansicht wurde gewechselt.',
                );
              if (previous != null) {
                final before =
                    previous['source']['multiple_one_off_case']['details'];
                final after = fact['details'];
                dynamic identities(dynamic parts) => [
                  for (final p in businessItems(parts))
                    {
                      'component_key': p['component_key'],
                      'events': [
                        for (final e in businessItems(p['planned_receipts']))
                          {
                            'event_key': e['event_key'],
                            'receipt_date': e['receipt_date'],
                            'gross_minor': e['gross_minor'],
                          },
                      ],
                    },
                ];
                if (!payrollSame(
                  identities(before['components']),
                  identities(after['components']),
                )) {
                  throw const ApiException(
                    409,
                    'Die Korrektur muss dieselben ursprünglichen Ansprüche und Bruttozuflüsse binden.',
                  );
                }
              }
              chosen = _copy(fact);
              Navigator.pop(context);
            },
          ),
        ),
      );
      if (!currentContext(owner, person, ticket) || !readable || chosen == null)
        return;
      await load();
      if (!currentContext(owner, person, ticket + 1) || !readable) return;
      if (previous != null)
        await oneOffCorrectionReason(chosen!, previous);
      else
        await calculatePeriod(chosen!);
    } catch (error) {
      if (mounted &&
          identical(owner, session) &&
          person == employeeId &&
          !suspended &&
          (epoch == ticket || epoch == ticket + 1))
        failure(error);
    }
  }

  Future<void> chooseOneOffCorrection(Map<String, dynamic> previous) =>
      openOneOffCases(previous);

  Future<void> chooseCompositeCorrection(Map<String, dynamic> previous) async {
    if (!canPreview) return;
    Map<String, dynamic>? chosen;
    await Navigator.push<void>(
      context,
      MaterialPageRoute(
        builder: (_) => BusinessPayrollCalculationCasesPage(
          onPolicyOriginal: originalForEmployee,
          session: session,
          employee: employee,
          onOriginal: original,
          initialMonth: previous['source']['month'],
          onCalculate: (fact) async {
            chosen = fact;
            Navigator.pop(context);
          },
        ),
      ),
    );
    if (!mounted || !readable || chosen == null) return;
    await showDialog<void>(
      context: context,
      builder: (_) => BusinessEditor(
        session: session,
        title: 'Belegten Gesamtlohn korrigieren',
        fields: const [
          BusinessField(
            'reason',
            'Nachvollziehbarer Korrekturgrund',
            required: true,
          ),
        ],
        readPermission: 'personnel.read',
        writePermission: 'personnel.read',
        onSave: (values) async {
          await calculatePeriod(
            chosen!,
            previous: previous,
            reason: values['reason'],
          );
        },
      ),
    );
  }

  Future<void> choosePeriodCorrection(Map<String, dynamic> previous) async {
    if (!canPreview) return;
    try {
      await fresh();
      final response = businessMap(
        await session.read(
          '/payroll/facts?employee_id=$employeeId&kind=period_case',
        ),
      );
      if (response['employee_id'] != employeeId)
        throw const ApiException(0, 'Aktuelle Monatsfallquellen fehlen.');
      final items = businessItems(response['items'])
          .where(
            (item) =>
                payrollFactRecord(
                      item,
                      employeeId,
                      kind: 'period_case',
                    )['status'] ==
                    'active' &&
                item['details']['month'] == previous['source']['month'],
          )
          .toList();
      if (!mounted) return;
      await showDialog<bool>(
        context: context,
        builder: (_) => BusinessEditor(
          session: session,
          title: 'Belegte Teilmonatsberechnung korrigieren',
          fields: [
            BusinessField(
              'fact_id',
              'Aktueller bestätigter Monatsfall',
              type: BusinessInput.choice,
              required: true,
              choices: {
                '': 'Monatsfall ausdrücklich wählen',
                for (final item in items)
                  '${item['id']}':
                      '${item['details']['month']} · Fassung ${item['revision']}',
              },
            ),
            const BusinessField(
              'correction_reason',
              'Nachvollziehbarer Korrekturgrund',
              required: true,
            ),
          ],
          readPermission: 'personnel.read',
          readAllowed: () => readable,
          onSave: (values) async {
            final fact = items
                .where((item) => item['id'] == values['fact_id'])
                .firstOrNull;
            if (fact == null)
              throw const FormatException(
                'Einen bestätigten Monatsfall auswählen.',
              );
            await calculatePeriod(
              fact,
              previous: previous,
              reason: '${values['correction_reason']}',
            );
          },
          saveLabel: 'Korrigierten Umfang unverbindlich prüfen',
        ),
      );
    } catch (e) {
      failure(e);
    }
  }

  Future<void> finalize() async {
    if (busy ||
        !write('personnel.approve') ||
        pendingRun ||
        !accepted ||
        preview?['can_finalize'] != true ||
        inputs == null)
      return;
    final proof = _copy(preview!),
        input = _copy(inputs!),
        previous = correction == null ? null : _copy(correction!);
    final opening = session.generation;
    final body = <String, dynamic>{
      ...input,
      'preview_hash': proof['preview_hash'],
      'accepted_scope': proof['calculation']['scope'],
      'confirmed': true,
      'revision': previous?['revision'] ?? 0,
      if (previous != null) 'id': previous['id'],
      if (previous != null)
        'correction_reason': '${runDraft?['correction_reason'] ?? ''}'.trim(),
    };
    final owner = session, person = employeeId, ticket = epoch;
    setState(() {
      busy = true;
      error = null;
    });
    try {
      await fresh(permission: 'personnel.approve');
      if (!currentContext(owner, person, ticket) ||
          opening != session.generation ||
          preview == null)
        throw const ApiException(
          409,
          'Datenstand geändert. Monatsberechnung erneut prüfen.',
        );
      if (proof.containsKey('settlement_transition') &&
          (!session.hasFeature(payrollPositiveCorrectionFeature) ||
              proof['settlement_transition']['schema_version'] == 3 &&
                  !session.hasFeature(payrollAdjustmentFeature) ||
              proof['settlement_transition']['schema_version'] == 2 &&
                  !session.hasFeature(payrollRepaymentFeature) ||
              !session.hasModule('payroll_multiple_cases')))
        throw const ApiException(
          409,
          'Der positive Korrekturvertrag ist aktuell nicht verfügbar.',
        );
      await session.command(
        key(false),
        '/payroll/runs',
        body,
        validateResult: payrollReceiptValidator(
          body,
          preview: proof,
          previous: previous,
        ),
      );
      if (!currentContext(owner, person, ticket) || !readable) return;
      setState(() {
        busy = false;
        message = 'Der ausdrücklich bestätigte Berechnungsumfang ist unveränderlich gespeichert. Es wurde keine Meldung oder Zahlung ausgelöst.';
        preview = inputs = runDraft = correction = null;
        accepted = false;
      });
      await load();
    } catch (e) {
      if (currentContext(owner, person, ticket)) failure(e);
    } finally {
      if (currentContext(owner, person, ticket)) setState(() => busy = false);
    }
  }

  Future<void> openHistory(Map<String, dynamic> record, bool profile) async {
    try {
      await fresh();
      final opening = session.generation;
      final rows = businessItems(
        await session.read(
          '/payroll/${profile ? 'profiles' : 'runs'}/${record['id']}/history',
        ),
      );
      if (rows.any(
        (r) => r['employee_id'] != employeeId || r['id'] != record['id'],
      ))
        throw const ApiException(
          0,
          'Die Historie gehört nicht zum gewählten Mitarbeiter.',
        );
      if (!profile)
        for (final r in rows) {
          payrollCalculation(r['calculation']);
          if (r.containsKey('settlement_transition'))
            payrollSettlementTransition(r);
        }
      if (mounted && readable && opening == session.generation)
        setState(() {
          history = rows;
          historyKind = profile ? 'profile' : 'run';
        });
    } catch (e) {
      failure(e);
    }
  }

  Future<void> originalForEmployee(
    Map<String, dynamic> owner,
    Map<String, dynamic> reference,
  ) async {
    final otherId = owner['id'];
    bool permitted() =>
        mounted &&
        session.allowed &&
        session.projectId == null &&
        session.can('personnel.read') &&
        session.hasFeature('payroll_calculation_cases') &&
        session.hasModule('payroll_calculation_cases');
    if (otherId is! String ||
        !RegExp(r'^[a-f0-9]{32}$').hasMatch(otherId) ||
        reference['employee_id'] != otherId)
      throw const ApiException(
        403,
        'Das betriebliche Original besitzt keine eindeutige Personalzuordnung.',
      );
    await session.load();
    if (!permitted() || session.error != null)
      throw const ApiException(
        403,
        'Aktuelle globale Personal-Leserechte fehlen.',
      );
    final opening = session.generation;
    Future<Map<String, dynamic>> selected() async {
      final page = await session.read('/personnel/files?employee_id=$otherId');
      final file = businessItems(page)
          .where(
            (v) => v['id'] == reference['id'] && v['employee_id'] == otherId,
          )
          .firstOrNull;
      if (file == null ||
          [
            'id',
            'employee_id',
            'sha256',
            'content_hash',
            'size',
          ].any((key) => file[key] != reference[key]))
        throw const ApiException(
          403,
          'Die betriebliche Originalfassung ist nicht unverändert freigegeben.',
        );
      return file;
    }

    final file = await selected();
    final bytes = await session.api.bytes(
      session.path('/personnel/files/${file['id']}/content'),
      mediaType: file['media_type'],
      maxBytes: 600000,
    );
    if (bytes.length != file['size'] ||
        _hex((await Sha256().hash(bytes)).bytes) != file['sha256'])
      throw const ApiException(
        0,
        'Das betriebliche Original stimmt nicht mit seiner Prüfsumme überein.',
      );
    await session.load();
    if (!permitted() || session.error != null || opening != session.generation)
      throw const ApiException(
        403,
        'Die globale Originalfreigabe wurde während des Downloads geändert.',
      );
    await selected();
    if (!permitted() || opening != session.generation)
      throw const ApiException(
        403,
        'Die globale Originalfreigabe wurde geändert.',
      );
    final controller = MailAttachmentPreviewController(
      VerifiedMailAttachment(
        bytes: bytes,
        filename: file['filename'],
        mediaType: file['media_type'],
        sha256: file['sha256'],
      ),
    );
    previews.add(controller);
    try {
      await Navigator.push<void>(
        context,
        MaterialPageRoute(
          builder: (_) => MailAttachmentPreviewPage(
            controller: controller,
            mayView: () => permitted() && opening == session.generation,
            exporter: exportMailAttachment,
          ),
        ),
      );
    } finally {
      previews.remove(controller);
      controller.dispose();
    }
  }

  Future<void> original(Map<String, dynamic> reference) async {
    try {
      await fresh();
      final opening = session.generation;
      final page = businessMap(
        await session.read('/personnel/files?employee_id=$employeeId'),
      );
      final file = businessItems(page)
          .where(
            (f) => f['id'] == reference['id'] && f['employee_id'] == employeeId,
          )
          .firstOrNull;
      if (file == null ||
          (!session.can('personnel.read') &&
              file['owner_visible'] != true &&
              file['owner_visible'] != 1))
        throw const ApiException(
          403,
          'Das Personaloriginal ist nicht freigegeben.',
        );
      if (file['sha256'] != reference['sha256'] ||
          file['content_hash'] != reference['content_hash'])
        throw const ApiException(
          0,
          'Der Originalnachweis passt nicht zur historischen Profilfassung.',
        );
      final bytes = await session.api.bytes(
        session.path('/personnel/files/${file['id']}/content'),
        mediaType: file['media_type'],
        maxBytes: 600000,
      );
      if (_hex((await Sha256().hash(bytes)).bytes) != file['sha256'] ||
          bytes.length != file['size'])
        throw const ApiException(
          0,
          'Originaldatei und gespeicherte Prüfsumme stimmen nicht überein.',
        );
      if (!mounted || !readable || opening != session.generation) return;
      final controller = MailAttachmentPreviewController(
        VerifiedMailAttachment(
          bytes: bytes,
          filename: file['filename'],
          mediaType: file['media_type'],
          sha256: file['sha256'],
        ),
      );
      previews.add(controller);
      await Navigator.push<void>(
        context,
        MaterialPageRoute(
          builder: (_) => MailAttachmentPreviewPage(
            controller: controller,
            mayView: () =>
                readable &&
                opening == session.generation &&
                (session.can('personnel.read') ||
                    file['owner_visible'] == true ||
                    file['owner_visible'] == 1),
            exporter: exportMailAttachment,
          ),
        ),
      );
      previews.remove(controller);
      controller.dispose();
    } catch (e) {
      failure(e);
    }
  }

  Future<void> export(Map<String, dynamic> record, String format) async {
    try {
      await fresh(permission: 'personnel.export');
      final opening = session.generation;
      final archived = businessItems(
        await session.read('/payroll/runs/${record['id']}/history'),
      ).where((r) => r['revision'] == record['revision']).firstOrNull;
      if (archived == null ||
          archived['employee_id'] != employeeId ||
          !payrollSame(archived, record))
        throw const ApiException(
          0,
          'Der gespeicherte Lauf konnte nicht als unveränderte historische Fassung bestätigt werden.',
        );
      final bytes = await session.api.bytes(
        session.path(
          '/payroll/runs/${record['id']}/$format?revision=${record['revision']}',
        ),
        mediaType: format == 'pdf' ? 'application/pdf' : 'application/json',
      );
      final document = await payrollExportAttachment(record, bytes, format);
      if (!mounted ||
          !readable ||
          opening != session.generation ||
          !session.can('personnel.export'))
        return;
      await exportMailAttachment(
        context,
        document,
        () =>
            readable &&
            session.can('personnel.read') &&
            session.can('personnel.export') &&
            opening == session.generation,
      );
    } catch (e) {
      failure(e);
    }
  }

  Future<void> openYear() async {
    if (!readable || busy) return;
    final opening = session.generation;
    await showDialog<void>(
      context: context,
      builder: (_) => BusinessEditor(
        session: session,
        title: 'Lohn-Jahresübersicht auswählen',
        readAllowed: () => readable && opening == session.generation,
        fields: const [
          BusinessField(
            'year',
            'Kalenderjahr',
            type: BusinessInput.integer,
            required: true,
          ),
        ],
        initial: {'year': DateTime.now().year},
        saveLabel: 'Jahresübersicht laden',
        onSave: (values) async {
          await fresh();
          final year = values['year'];
          if (year is! int || year < 2000 || year > 2099)
            throw const FormatException(
              'Gültiges Kalenderjahr von 2000 bis 2099 angeben.',
            );
          final view = await payrollLedgerSnapshot(
            await session.read(
              '/payroll/ledger?employee_id=$employeeId&year=$year',
            ),
            employeeId,
            year,
          );
          if (!mounted || !readable || opening != session.generation) return;
          setState(() {
            yearView = view;
            error = null;
          });
        },
      ),
    );
  }

  Future<void> exportYear(String format) async {
    if (yearView == null) return;
    final view = _copy(yearView!);
    try {
      await fresh(permission: 'personnel.export');
      final opening = session.generation,
          ledger = businessMap(view['ledger']),
          manifest = businessMap(view['exports'][format]);
      final bytes = await session.api.bytes(
        session.path(
          '/payroll/ledger/$format?${Uri(queryParameters: {'employee_id': employeeId, 'year': '${ledger['year']}', 'snapshot_hash': ledger['snapshot_hash']}).query}',
        ),
        mediaType: '${manifest['media_type']}'.split(';').first,
      );
      final document = await payrollLedgerExportAttachment(view, bytes, format);
      await fresh(permission: 'personnel.export');
      if (!mounted || !readable || opening != session.generation) return;
      await exportMailAttachment(
        context,
        document,
        () =>
            readable &&
            session.can('personnel.read') &&
            session.can('personnel.export') &&
            opening == session.generation,
      );
    } catch (e) {
      failure(e);
    }
  }

  Widget yearCard(Map<String, dynamic> view) {
    final ledger = businessMap(view['ledger']);
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              'Lohn-Jahresübersicht ${ledger['year']}',
              style: Theme.of(context).textTheme.titleLarge,
            ),
            Text(
              '${ledger['recorded_months']} von 12 Monaten erfasst. Summen umfassen die jeweils letzte wirksame Monatsfassung.',
            ),
            if (ledger.containsKey('supported_wage_account_fields_complete'))
              Notice(
                ledger['statutory_wage_account_complete'] == true
                    ? 'Die erfassten Pflichtangaben und Zahlungsnachweise sind für die belegten Beschäftigungsmonate im unterstützten Standardfall vollständig.'
                    : 'Für ein vollständiges Lohnkonto fehlen noch Stamm-, Steuer-, Zahlungs- oder Monatsnachweise. Diese lassen sich unter Lohnkonto-Nachweise ergänzen.',
              ),
            for (final issue
                in ledger['account_completeness_issues'] as List? ?? [])
              Notice(
                const {
                      'employment_period_missing':
                          'Ein belegter Beschäftigungszeitraum fehlt.',
                      'employment_periods_conflict': 'Die Beschäftigungszeiträume der Stammnachweise widersprechen sich. Den tatsächlichen Beginn und das Ende des Arbeitsverhältnisses in allen Profilnachweisen abgleichen.',
                      'unpaid_statutory_marker_requires_evidence': 'Für die belegten unbezahlten Tage fehlt noch der geprüfte Jahresnachweis zum U-Merkmal. Die Jahresprüfung der Unterbrechungen im Lohnkonto ergänzen.',
                    }[issue] ??
                    '$issue',
              ),
            if ((ledger['account_missing_months'] as List? ?? []).isNotEmpty)
              Notice(
                'Beschäftigungsmonate mit fehlenden Nachweisen: ${(ledger['account_missing_months'] as List).join(', ')}',
              ),
            if ((ledger['missing_months'] as List).isNotEmpty)
              Notice(
                'Fehlende Monate: ${(ledger['missing_months'] as List).join(', ')}',
              ),
            if ((ledger['partial_months'] as List).isNotEmpty)
              Notice(
                'Unvollständige Steuer-/Nettowerte: ${(ledger['partial_months'] as List).join(', ')}',
              ),
            for (final note in ledger['limitations'] as List) Notice('$note'),
            for (final month in businessItems(ledger['months']))
              ListTile(
                title: Text(
                  '${month['month']} · ${month['status'] == 'missing'
                      ? 'Nicht erfasst'
                      : month['status'] == 'social_only'
                      ? 'Nur Sozialversicherung · Fassung ${month['revision']}'
                      : 'Berechnet · Fassung ${month['revision']}'}',
                ),
                subtitle: Text(
                  'Brutto ${payrollMoney(month['calculation']?['gross_minor'])} · Netto ${payrollMoney(month['calculation']?['net_minor'])}${month['wage_account']?['payment_status'] == 'no_payment_due'
                      ? '\nKeine Nettozahlung geschuldet · Steuer- und Beitragsabführungen separat nachweisen'
                      : month['wage_account']?['payment_status'] == 'payments_evidenced'
                      ? '\nTatsächliche Nettozahlungen belegt'
                      : ''}',
                ),
              ),
            Text(
              'Summen der erfassten wirksamen Monate',
              style: Theme.of(context).textTheme.titleMedium,
            ),
            for (final entry in payrollLedgerAmountLabels.entries)
              ListTile(
                title: Text(entry.value),
                subtitle: Text(payrollMoney(ledger['totals'][entry.key])),
              ),
            for (final group in {
              'employee_contributions': 'Arbeitnehmerbeiträge im Jahr',
              'employer_contributions': 'Arbeitgeberbeiträge im Jahr',
              'employer_levies': 'Arbeitgeberumlagen im Jahr',
            }.entries)
              ExpansionTile(
                title: Text(group.value),
                children: [
                  for (final entry in businessMap(
                    ledger['totals'][group.key],
                  ).entries)
                    ListTile(
                      title: Text(_contributionLabels[entry.key] ?? entry.key),
                      subtitle: Text(payrollMoney(entry.value)),
                    ),
                ],
              ),
            Text(
              'Korrekturen · nicht zusätzlich zu den Summen addiert',
              style: Theme.of(context).textTheme.titleMedium,
            ),
            for (final correction in businessItems(
              ledger['correction_history'],
            ))
              ExpansionTile(
                title: Text(
                  '${correction['month']} · Fassung ${correction['revision']}',
                ),
                subtitle: Text('${correction['reason']}'),
                children: [
                  for (final delta in businessMap(correction['delta']).entries)
                    ListTile(
                      title: Text(
                        payrollLedgerAmountLabels[delta.key] ?? delta.key,
                      ),
                      subtitle: Text(payrollMoney(delta.value)),
                    ),
                ],
              ),
            if (session.can('personnel.read') &&
                session.can('personnel.export'))
              Wrap(
                spacing: 8,
                runSpacing: 8,
                children: [
                  for (final format in ['pdf', 'csv', 'json'])
                    OutlinedButton(
                      onPressed: () => exportYear(format),
                      child: Text(
                        'Jahresübersicht als ${format.toUpperCase()}',
                      ),
                    ),
                ],
              ),
          ],
        ),
      ),
    );
  }

  Widget positiveCorrectionNotice(Map<String, dynamic> value) {
    final transition = payrollSettlementTransition(value);
    if (transition['schema_version'] == 3)
      return Notice(
        'Weiterer belegter Nettoausgleich: ${payrollMoney(transition['net_delta_minor'])}. Bisher erfüllt: ${payrollMoney(transition['prior_total_net_minor'])}; korrigierte Nettoschuld: ${payrollMoney(transition['total_net_minor'])}. ${transition['net_delta_minor'] == 0 ? 'Keine neuen Zahlungsteile und kein neuer Geldfluss.' : 'Tatsächlichen weiteren Nettoausgleich mit eigenem Tag und Original separat belegen.'} Frühere Zahlungen und Rückzahlungen bleiben unverändert.',
      );
    if (transition['schema_version'] == 2)
      return Notice(
        'Belegte Rückzahlungsverpflichtung des Beschäftigten: ${payrollMoney(transition['repayment_minor'])}. '
        'Bisher tatsächlich bezahlt: ${payrollMoney(transition['prior_total_net_minor'])}; '
        'korrigierte Nettoschuld: ${payrollMoney(transition['total_net_minor'])}. '
        'Frühere Zahlungen bleiben unverändert. Die tatsächliche Rückzahlung ist separat mit eigenem Tag und Original zu belegen. Hier wird kein Geld eingezogen.',
      );
    return Notice(
      'Belegte zusätzliche Nettozahlung: ${payrollMoney(transition['additional_net_minor'])}. '
      'Bisher erfüllt: ${payrollMoney(transition['prior_total_net_minor'])}; '
      'korrigierte Nettoschuld: ${payrollMoney(transition['total_net_minor'])}. '
      'Die bisherigen Zahlungsteile bleiben unverändert. Der ursprüngliche Bruttozufluss bleibt '
      'am ${businessDate(transition['receipt_date'])}. Der zusätzliche Nettobetrag benötigt '
      'seinen tatsächlich belegten zulässigen Zahlungstag. '
      'Das Speichern löst keine Überweisung aus.',
    );
  }

  Widget calculationView(Map<String, dynamic> calc) => Column(
    crossAxisAlignment: CrossAxisAlignment.start,
    children: [
      Text(
        payrollScopes[calc['scope']]!,
        style: Theme.of(context).textTheme.titleLarge,
      ),
      Text('${calc['month']} · Brutto ${payrollMoney(calc['gross_minor'])}'),
      if (calc['tax_parameters']?['tax_factor'] != null)
        Text(
          'Eingetragener ELStAM-Faktor (Steuerklasse IV): ${calc['tax_parameters']['tax_factor']}',
        ),
      if (calc['scope'] == 'social_contributions_only')
        const Notice(
          'Dies ist ausschließlich eine Sozialversicherungsberechnung. Individuelle Lohnsteuer, Solidaritätszuschlag, Kirchensteuer, Netto und Auszahlung sind nicht ermittelt.',
        ),
      for (final block in businessItems(calc['blockers']))
        Notice('${block['message']}'),
      if (calc['social_contributions_available'] == true) ...[
        for (final group in const {
          'employee_contributions': 'Arbeitnehmerbeiträge',
          'employer_contributions': 'Arbeitgeberbeiträge',
          'employer_levies': 'Arbeitgeberumlagen',
        }.entries)
          ExpansionTile(
            title: Text(group.value),
            children: [
              for (final entry in businessMap(calc[group.key]).entries)
                ListTile(
                  title: Text(_contributionLabels[entry.key] ?? entry.key),
                  trailing: Text(payrollMoney(entry.value)),
                ),
            ],
          ),
        for (final row in const {
          'employee_social_total_minor': 'Arbeitnehmerbeiträge gesamt',
          'employer_social_total_minor': 'Arbeitgeberbeiträge gesamt',
          'employer_flat_tax_minor': 'Arbeitgeber-Pauschsteuer',
          'individual_wage_tax_minor': 'Individuelle Lohnsteuer',
          'solidarity_minor': 'Solidaritätszuschlag',
          'church_tax_minor': 'Kirchensteuer',
          'employer_total_excluding_accident_insurance_minor':
              'Arbeitgeberaufwand ohne Unfallversicherung',
        }.entries)
          ListTile(
            title: Text(row.value),
            subtitle: Text(payrollMoney(calc[row.key])),
          ),
        ListTile(
          title: const Text('Netto im verfügbaren Berechnungsumfang'),
          subtitle: Text(payrollMoney(calc['net_minor'])),
        ),
        ListTile(
          title: const Text(
            'Berechneter Auszahlungsbetrag · keine Überweisung',
          ),
          subtitle: Text(payrollMoney(calc['payout_minor'])),
        ),
        if (calc['employee_additional_payment_minor'] is int &&
            calc['employee_additional_payment_minor'] > 0)
          Notice(
            [
                  payrollCalculationCaseRule,
                  payrollFactorTaxfreeTravelRule,
                  payrollFactorClaimsRule,
                  payrollFactorClaimTravelRule,
                  payrollFactorTransitionRule,
                  payrollFactorTransitionPeriodRule,
                  individualMinijobRule,
                  payrollOneOffRule,
                  payrollFactorOneOffRule,
                  payrollMultipleRule,
                ].contains(calc['rule_version'])
                ? 'Die belegten Arbeitnehmerabzüge übersteigen den verbleibenden Barbetrag. Zusätzlicher Arbeitnehmeranteil: ${payrollMoney(calc['employee_additional_payment_minor'])}. Der berechnete Auszahlungsbetrag beträgt 0,00 €.'
                : 'Der Mindest-RV-Beitrag übersteigt das Brutto. Zusätzlicher Arbeitnehmeranteil: ${payrollMoney(calc['employee_additional_payment_minor'])}. Der berechnete Auszahlungsbetrag beträgt 0,00 €.',
          ),
      ],
      if ([
        payrollCalculationCaseRule,
        payrollFactorTaxfreeTravelRule,
        payrollFactorClaimsRule,
        payrollFactorClaimTravelRule,
        payrollFactorTransitionRule,
        payrollFactorTransitionPeriodRule,
        individualMinijobRule,
        payrollOneOffRule,
        payrollFactorOneOffRule,
        payrollMultipleRule,
      ].contains(calc['rule_version'])) ...[
        ListTile(
          title: const Text(
            'Belegte Nettoabzüge für Sachbezug und Steuerkosten',
          ),
          subtitle: Text(payrollMoney(calc['net_deductions_minor'])),
        ),
        PayrollCalculationCasePlanView(
          plan: {
            ...businessMap(calc['period_details']),
            'rule_version': calc['rule_version'],
            'month': calc['month'],
            'gross_minor':
                [
                  payrollOneOffRule,
                  payrollFactorOneOffRule,
                  payrollMultipleRule,
                ].contains(calc['rule_version'])
                ? calc['running_calculation']['gross_minor']
                : calc['gross_minor'],
            'blockers': calc['blockers'],
            if (calc['rule_version'] == payrollFactorTransitionPeriodRule) ...{
              'can_calculate': calc['payroll_calculation_complete'],
              'factor_transition_period_component': Map<String, dynamic>.from(
                calc,
              )..remove('period_details'),
            },
            if (calc['rule_version'] == individualMinijobRule) ...{
              'actual_health_insurance':
                  calc['tax_parameters']?['actual_health_insurance'],
              'can_calculate': calc['payroll_calculation_complete'],
            },
          },
        ),
      ] else if (calc['period_details'] != null)
        PayrollPeriodPlanView(
          plan: {...businessMap(calc['period_details']), 'blockers': []},
        ),
      if ([
        payrollOneOffRule,
        payrollFactorOneOffRule,
      ].contains(calc['rule_version']))
        PayrollOneoffCasePlanView(plan: calc),
      if (calc['rule_version'] == payrollMultipleRule)
        PayrollMultipleCasePlanView(plan: calc),
      if (calc['scope'] == 'regular_transition_monthly')
        ExpansionTile(
          title: const Text('Prognose und Beitragsbemessung'),
          children: [
            Text(
              'Tatsächliches Monatsentgelt: ${const {'within_transition_area': 'innerhalb des Übergangsbereichs', 'below_or_at_lower_limit': 'bis zur unteren Grenze', 'above_upper_limit': 'oberhalb der oberen Grenze'}[calc['transition']['regime']]}',
            ),
            const Notice(
              'Der belegte prognostische Status bleibt auch bei abweichendem tatsächlichem Monatsentgelt erhalten.',
            ),
            for (final label in const {
              'regular_monthly_gross_minor':
                  'Prognostiziertes regelmäßiges Monatsbrutto',
              'total_assessment_minor': 'Gesamtbemessungsgrundlage',
              'employee_assessment_minor': 'Arbeitnehmerbemessungsgrundlage',
              'levy_assessment_minor': 'Umlagebemessungsgrundlage',
            }.entries)
              ListTile(
                title: Text(label.value),
                subtitle: Text(payrollMoney(calc['transition'][label.key])),
              ),
            Text('Faktor 2026: ${calc['transition']['factor']}'),
            for (final branch in businessMap(
              calc['transition']['branch_bases'],
            ).entries)
              ListTile(
                title: Text(_contributionLabels[branch.key] ?? branch.key),
                subtitle: Text(
                  'Gesamtgrundlage ${payrollMoney(branch.value['total_minor'])} · Arbeitnehmergrundlage ${payrollMoney(branch.value['employee_minor'])}',
                ),
              ),
            for (final label in const {
              'employee_before_adjustments_minor':
                  'PV-Arbeitnehmerbeitrag vor Anpassungen',
              'childless_surcharge_minor': 'PV-Kinderlosenzuschlag',
              'children_discount_minor': 'PV-Kinderabschläge',
            }.entries)
              ListTile(
                title: Text(label.value),
                subtitle: Text(
                  payrollMoney(
                    calc['transition']['care_adjustments'][label.key],
                  ),
                ),
              ),
          ],
        ),
      Notice(
        [
              payrollCalculationCaseRule,
              payrollFactorTaxfreeTravelRule,
              payrollFactorClaimsRule,
              payrollFactorClaimTravelRule,
              payrollFactorTransitionRule,
              payrollFactorTransitionPeriodRule,
              individualMinijobRule,
              payrollOneOffRule,
              payrollFactorOneOffRule,
              payrollMultipleRule,
            ].contains(calc['rule_version'])
            ? 'Unfallversicherung ist nicht enthalten. Steuerfreie Reiseerstattungen werden außerhalb des Lohnnettos verarbeitet. Amtliche Meldungen und tatsächliche Zahlungen erfolgen separat.'
            : 'Unfallversicherung ist nicht enthalten. Reisekostenerstattungen werden getrennt verarbeitet. Amtliche Meldungen und Zahlungen erfolgen separat.',
      ),
    ],
  );
  Widget sourceView(Map<String, dynamic> source) => ExpansionTile(
    title: Text('Eingefrorene Quellen · ${source['month']}'),
    children: [
      if (source['source_schema_version'] == 5)
        Text(
          'Bestätigte Monatsgruppe · Fassung ${source['multiple_one_off_case']?['revision']} · ursprünglicher Einzelanspruch und getrennte tatsächliche Zahlungszuordnung',
        ),
      if (source['source_schema_version'] == 4)
        Text(
          'Bestätigter Einmalbezugsfall · Fassung ${source['one_off_case']?['revision']} · unveränderte laufende Rechnung und geprüfte Jahresoriginale',
        ),
      if (source['source_schema_version'] == 3)
        Text(
          source['calculation_case']?['rule_version'] == individualMinijobRule
              ? 'Individueller Minijob · Fassung ${source['calculation_case']?['revision']} · ursprüngliche persönliche Prüfbelege'
              : 'Bestätigter Gesamtfall · Fassung ${source['calculation_case']?['revision']} · ursprüngliche Anspruchs- und Reisequellen',
        ),
      if (source['source_schema_version'] == 2)
        Text(
          'Belegter Monatsfall · Fassung ${source['period_case']?['revision']} · getrennte Steuer- und SV-Zeiträume',
        ),
      ListTile(
        title: Text('Lohnprofil Fassung ${source['profile']?['revision']}'),
        subtitle: Text(
          'Gültig ab ${businessDate(source['profile']?['profile']?['effective_from'])}',
        ),
      ),
      ListTile(
        title: Text(
          'HR-Monatsvorbereitung Fassung ${source['preparation']?['revision']}',
        ),
        subtitle: Text('Quellenhash: ${source['preparation']?['source_hash']}'),
      ),
      _PayrollFacts(value: source['profile']?['profile']),
      for (final agreement in businessItems(
        source['preparation']?['snapshot']?['agreements'] ?? [],
      ))
        ListTile(
          title: Text(
            'Belegte Vereinbarung: ${payrollMoney(agreement['amount_minor'])} ${agreement['pay_basis'] == 'hourly' ? 'je Stunde' : 'monatlich'}',
          ),
          subtitle: Text(
            'Ab ${businessDate(agreement['effective_from'])} · Fassung ${agreement['revision']}',
          ),
        ),
      Text(
        'Freigegebene Arbeitszeit: ${source['preparation']?['snapshot']?['net_work_seconds'] ?? 'unbekannt'} Sekunden',
      ),
      if (source['profile']?['source_file'] != null)
        TextButton(
          onPressed: () =>
              original(businessMap(source['profile']['source_file'])),
          child: const Text('Profiloriginal öffnen'),
        ),
    ],
  );
  Widget runCard(Map<String, dynamic> run, {bool historical = false}) => Card(
    child: Padding(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            '${run['source']['month']} · Berechnung Fassung ${run['revision']}',
            style: Theme.of(context).textTheme.titleLarge,
          ),
          calculationView(businessMap(run['calculation'])),
          if (run.containsKey('settlement_transition'))
            positiveCorrectionNotice(run),
          sourceView(businessMap(run['source'])),
          if ('${run['correction_reason'] ?? ''}'.isNotEmpty)
            Text('Korrektur: ${run['correction_reason']}'),
          if (run['delta'] != null)
            ExpansionTile(
              title: const Text('Differenz zur vorherigen Berechnung'),
              children: [
                for (final d in businessMap(run['delta']).entries)
                  ListTile(
                    title: Text(
                      const {
                            'gross_minor': 'Brutto',
                            'employee_social_total_minor':
                                'Arbeitnehmerbeiträge',
                            'employer_social_total_minor':
                                'Arbeitgeberbeiträge',
                            'employer_flat_tax_minor':
                                'Arbeitgeber-Pauschsteuer',
                            'net_minor': 'Netto',
                            'individual_wage_tax_minor':
                                'Individuelle Lohnsteuer',
                            'solidarity_minor': 'Solidaritätszuschlag',
                            'church_tax_minor': 'Kirchensteuer',
                            'employee_tax_minor': 'Steuern gesamt',
                            'payout_minor': 'Auszahlung',
                          }[d.key] ??
                          d.key,
                    ),
                    subtitle: Text(payrollMoney(d.value)),
                  ),
              ],
            ),
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: [
              if (!historical)
                TextButton(
                  onPressed: () => openHistory(run, false),
                  child: const Text('Laufhistorie'),
                ),
              if (!historical)
                OutlinedButton(
                  onPressed: canPreview ? () => calculate(run) : null,
                  child: const Text('Monatsberechnung korrigieren'),
                ),
              if (session.can('personnel.read') &&
                  session.can('personnel.export'))
                for (final type in ['pdf', 'json'])
                  OutlinedButton(
                    onPressed: () => export(run, type),
                    child: Text(
                      '${type.toUpperCase()} · Fassung ${run['revision']}',
                    ),
                  ),
            ],
          ),
        ],
      ),
    ),
  );
  Widget profileCard(
    Map<String, dynamic> value, {
    bool historical = false,
  }) => Card(
    child: Padding(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            'Ab ${businessDate(value['profile']['effective_from'])} · Lohnprofil Fassung ${value['revision']}',
            style: Theme.of(context).textTheme.titleMedium,
          ),
          ExpansionTile(
            title: Text(
              value['profile']['employment_kind'] == 'minijob'
                  ? 'Geprüfte Minijobmerkmale'
                  : 'Geprüfte reguläre Merkmale',
            ),
            children: [_PayrollFacts(value: value['profile'])],
          ),
          if ('${value['correction_reason'] ?? ''}'.isNotEmpty)
            Text('Korrektur: ${value['correction_reason']}'),
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: [
              TextButton(
                onPressed: () => original(businessMap(value['source_file'])),
                child: const Text('Personaloriginal öffnen'),
              ),
              if (!historical)
                TextButton(
                  onPressed: () => openHistory(value, true),
                  child: const Text('Profilhistorie'),
                ),
              if (!historical)
                OutlinedButton(
                  onPressed:
                      write('personnel.write') && !pendingProfile && !busy
                      ? () => profile(value)
                      : null,
                  child: const Text('Profil korrigieren'),
                ),
            ],
          ),
        ],
      ),
    ),
  );
  @override
  Widget build(BuildContext context) =>
      payrollStatementsAvailable(session) && !session.can('personnel.read')
      ? BusinessPayrollStatementsPage(session: session, employee: employee)
      : Scaffold(
          appBar: AppBar(
            title: Text('Lohnberechnung 2026 · ${employee['name']}'),
            actions: [
              IconButton(
                tooltip: 'Rechte und Quellen aktualisieren',
                onPressed: loading || busy ? null : () => load(refresh: true),
                icon: const Icon(Icons.refresh),
              ),
            ],
          ),
          body: !readable
              ? Padding(
                  padding: const EdgeInsets.all(24),
                  child: BusinessEmpty(
                    'Lohnberechnung nicht freigegeben',
                    error ?? 'Die aktuelle Personal- beziehungsweise eigene Mitarbeiterfreigabe ist erforderlich.',
                  ),
                )
              : ListView(
                  padding: const EdgeInsets.all(20),
                  children: [
                    const Notice(
                      'Gewerbliche Minijobs und reguläre Standard-Monatsabrechnung 2026. Persönliche Merkmale und bestätigte Monatsquellen bestimmen den verfügbaren Umfang; Sonderfälle bleiben gesondert zu prüfen.',
                    ),
                    if (error != null) Notice(error!, error: true),
                    if (message != null) Notice(message!),
                    if (loading || busy) const LinearProgressIndicator(),
                    if (payrollStatementsAvailable(session))
                      OutlinedButton(
                        onPressed: busy
                            ? null
                            : () => Navigator.push<void>(
                                context,
                                MaterialPageRoute(
                                  builder: (_) => BusinessPayrollStatementsPage(
                                    session: session,
                                    employee: employee,
                                  ),
                                ),
                              ),
                        child: const Text('Mitarbeiter-Lohnnachweise ansehen'),
                      ),
                    if (Navigator.canPop(context))
                      OutlinedButton(
                        onPressed: () => Navigator.pop(context),
                        child: const Text(
                          'Zur Personalakte und Monatsvorbereitung',
                        ),
                      ),
                    for (final isProfile in [true, false])
                      if (session.pending(key(isProfile)))
                        Card(
                          child: Padding(
                            padding: const EdgeInsets.all(16),
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Text(
                                  isProfile
                                      ? 'Profilbestätigung offen'
                                      : 'Berechnungsbestätigung offen',
                                  style: Theme.of(context)
                                      .textTheme
                                      .titleMedium,
                                ),
                                const Text(
                                  'Der Vorgang kann bereits gespeichert sein. Die Wiederholung verwendet dieselben Eingaben und dieselbe Vorgangskennung.',
                                ),
                                _PayrollFacts(
                                  value: session.pendingCommandValues(
                                    key(isProfile),
                                    path: isProfile
                                        ? '/payroll/profiles'
                                        : '/payroll/runs',
                                  ),
                                ),
                                FilledButton(
                                  onPressed:
                                      write(
                                            isProfile
                                                ? 'personnel.write'
                                                : 'personnel.approve',
                                          ) &&
                                          !busy
                                      ? () => repeat(isProfile)
                                      : null,
                                  child: const Text(
                                    'Ursprünglichen Auftrag erneut senden',
                                  ),
                                ),
                              ],
                            ),
                          ),
                        ),
                    if (payrollCashReadable(session))
                      OutlinedButton(
                        onPressed: () => Navigator.push<void>(
                          context,
                          MaterialPageRoute(
                            builder: (_) => BusinessPayrollCashPage(
                              session: session,
                              employee: widget.employee,
                            ),
                          ),
                        ),
                        child: const Text(
                          'Belegte Lohnzahlungen für EÜR öffnen',
                        ),
                      ),
                    if (payrollCalculationCasesReadable(session))
                      OutlinedButton(
                        onPressed: loading || busy
                            ? null
                            : () async {
                                Map<String, dynamic>? chosen;
                                await Navigator.push<void>(
                                  context,
                                  MaterialPageRoute(
                                    builder: (_) =>
                                        BusinessPayrollCalculationCasesPage(
                                          onPolicyOriginal: originalForEmployee,
                                          session: session,
                                          employee: employee,
                                          onOriginal: original,
                                          onCalculate: (fact) async {
                                            chosen = fact;
                                            Navigator.pop(context);
                                          },
                                        ),
                                  ),
                                );
                                if (mounted && readable) {
                                  await load();
                                  if (chosen != null) {
                                    try {
                                      await calculatePeriod(chosen!);
                                    } catch (e) {
                                      failure(e);
                                    }
                                  }
                                }
                              },
                        child: const Text(
                          'Abrechnungsfälle mit Ansprüchen und Reisen',
                        ),
                      ),
                    if (payrollMultipleCasesReadable(session))
                      OutlinedButton(
                        onPressed: loading || busy ? null : openMultipleCases,
                        child: const Text(
                          'Monatsgruppen mit getrennten Zahlungstagen öffnen',
                        ),
                      ),
                    if (payrollOneoffCasesReadable(session) &&
                        session.hasFeature(payrollFactorOneOffFeature)) ...[
                      OutlinedButton(
                        onPressed: loading || busy
                            ? null
                            : () => openOneOffCases(null, true),
                        child: const Text('Faktor-Einmalbezugsfälle öffnen'),
                      ),
                      OutlinedButton(
                        onPressed: loading || busy
                            ? null
                            : () => Navigator.push<void>(
                                context,
                                MaterialPageRoute(
                                  builder: (_) =>
                                      BusinessPayrollAnnualBasisPage(
                                        session: session,
                                        employee: employee,
                                        onOriginal: original,
                                        factorMode: true,
                                      ),
                                ),
                              ),
                        child: const Text(
                          'Faktor-Jahresbasis und Steuerprognose öffnen',
                        ),
                      ),
                    ],
                    if (payrollOneoffCasesReadable(session))
                      OutlinedButton(
                        onPressed: loading || busy ? null : openOneOffCases,
                        child: const Text(
                          'Einmalbezugsfälle aus Jahresquellen öffnen',
                        ),
                      ),
                    if (payrollAnnualBasisReadable(session))
                      OutlinedButton(
                        onPressed: loading || busy
                            ? null
                            : () => Navigator.push<void>(
                                context,
                                MaterialPageRoute(
                                  builder: (_) =>
                                      BusinessPayrollAnnualBasisPage(
                                        session: session,
                                        employee: employee,
                                        onOriginal: original,
                                      ),
                                ),
                              ),
                        child: const Text(
                          'Jahresquellen und Einmalansprüche öffnen',
                        ),
                      ),
                    if (payrollRvReadable(session))
                      OutlinedButton(
                        onPressed: loading || busy
                            ? null
                            : () => Navigator.push<void>(
                                context,
                                MaterialPageRoute(
                                  builder: (_) => BusinessPayrollRvPage(
                                    session: session,
                                    employee: employee,
                                    onOriginal: original,
                                  ),
                                ),
                              ),
                        child: const Text(
                          'Minijob-RV und Aufhebungsantrag prüfen',
                        ),
                      ),
                    if (payrollWageInterruptionsReadable(session))
                      OutlinedButton(
                        onPressed: loading || busy
                            ? null
                            : () => Navigator.push<void>(
                                context,
                                MaterialPageRoute(
                                  builder: (_) =>
                                      BusinessPayrollWageInterruptionsPage(
                                        session: session,
                                        employee: employee,
                                        onOriginal: original,
                                      ),
                                ),
                              ),
                        child: const Text('U-Merkmal im Lohnkonto prüfen'),
                      ),
                    if (payrollEntitlementsReadable(session))
                      OutlinedButton(
                        onPressed: loading || busy
                            ? null
                            : () => Navigator.push<void>(
                                context,
                                MaterialPageRoute(
                                  builder: (_) =>
                                      BusinessPayrollEntitlementsPage(
                                        session: session,
                                        employee: employee,
                                        onOriginal: original,
                                      ),
                                ),
                              ),
                        child: const Text('Private Anspruchsnachweise öffnen'),
                      ),
                    if (session.hasFeature('payroll_period_facts') &&
                        session.hasModule('payroll_facts') &&
                        session.can('personnel.read'))
                      OutlinedButton(
                        onPressed: loading || busy
                            ? null
                            : () async {
                                Map<String, dynamic>? chosen;
                                await Navigator.push<void>(
                                  context,
                                  MaterialPageRoute(
                                    builder: (_) => BusinessPayrollFactsPage(
                                      session: session,
                                      employee: employee,
                                      onOriginal: original,
                                      onCalculate: (fact) async {
                                        chosen = fact;
                                        Navigator.pop(context);
                                      },
                                    ),
                                  ),
                                );
                                if (mounted && readable) {
                                  await load();
                                  if (chosen != null) {
                                    try {
                                      await calculatePeriod(chosen!);
                                    } catch (e) {
                                      failure(e);
                                    }
                                  }
                                }
                              },
                        child: const Text('Lohnzeitachsen und Teilmonate'),
                      ),
                    if (session.hasFeature('payroll_wage_account') &&
                        session.hasModule('payroll_accounts'))
                      OutlinedButton(
                        onPressed: loading || busy
                            ? null
                            : () => Navigator.push<void>(
                                context,
                                MaterialPageRoute(
                                  builder: (_) => BusinessPayrollAccountsPage(
                                    session: session,
                                    employee: employee,
                                    onOriginal: original,
                                  ),
                                ),
                              ),
                        child: const Text('Lohnkonto-Nachweise öffnen'),
                      ),
                    OutlinedButton(
                      onPressed: loading || busy ? null : openYear,
                      child: const Text('Jahresübersicht öffnen'),
                    ),
                    if (yearView != null) yearCard(yearView!),
                    if (rules != null)
                      ExpansionTile(
                        title: const Text(
                          'Verifizierter Regelstand und Grenzen',
                        ),
                        children: [
                          Text('Regelstand: ${rules!['rules']?['version']}'),
                          if (rules!['regular_transition_rules'] != null)
                            Text(
                              'Belegter Übergangsbereich: ${rules!['regular_transition_rules']['version']}',
                            ),
                          Text(
                            'Minijobgrenze: ${payrollMoney(rules!['rules']?['minijob_monthly_limit_minor'])} pro Monat; ${payrollMoney(rules!['rules']?['minijob_annual_limit_minor'])} jährlich.',
                          ),
                          const Text(
                            'Vollmonate sowie belegte Ein-/Austrittszeiträume zwischen 18 und 64 Jahren. Teilmonate benötigen bestätigte Lohnzeitachsen. Übergangsbereich nur mit ausdrücklich belegter Zwölfmonatsprognose und vollständigen Steuermerkmalen. Sonderfälle und nicht unterstützte Versicherungskonstellationen bleiben gesperrt. Tatsächliche Kassen- und Umlagesätze anhand ihrer Nachweise erfassen.',
                          ),
                        ],
                      ),
                    const SizedBox(height: 12),
                    Text(
                      'Belegte Lohnprofile',
                      style: Theme.of(context).textTheme.titleLarge,
                    ),
                    OutlinedButton(
                      onPressed:
                          write('personnel.write') && !pendingProfile && !busy
                          ? () => profile()
                          : null,
                      child: const Text('Neues Lohnprofil erfassen'),
                    ),
                    if (profiles.isEmpty && !loading)
                      const BusinessEmpty(
                        'Noch kein Lohnprofil',
                        'Zuerst den gültigen Personalnachweis in die Personalakte aufnehmen und die persönlichen Merkmale ausdrücklich erfassen.',
                      ),
                    for (final p in profiles) profileCard(p),
                    Text(
                      'Abgeschlossene HR-Monatsquellen',
                      style: Theme.of(context).textTheme.titleLarge,
                    ),
                    for (final p in preparations)
                      ListTile(
                        title: Text('${p['month']} · Fassung ${p['revision']}'),
                        subtitle: Text(
                          'Bestätigte Quellenvollständigkeit · ${businessDate(p['created_at'], time: true)}',
                        ),
                      ),
                    if (preparations.isEmpty && !loading)
                      const BusinessEmpty(
                        'Monatsquelle fehlt',
                        'In der Personalakte Vereinbarungen, Zeiten und Abwesenheiten prüfen und die Lohnvorbereitung abschließen.',
                      ),
                    FilledButton(
                      onPressed:
                          canPreview &&
                              profiles.isNotEmpty &&
                              preparations.isNotEmpty
                          ? () => calculate()
                          : null,
                      child: const Text('Belegte Monatsberechnung prüfen'),
                    ),
                    if (preview != null && !pendingRun)
                      Card(
                        child: Padding(
                          padding: const EdgeInsets.all(16),
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text(
                                'Unverbindliche Berechnungsvorschau',
                                style: Theme.of(context).textTheme.titleLarge,
                              ),
                              calculationView(
                                businessMap(preview!['calculation']),
                              ),
                              if (preview!.containsKey('settlement_transition'))
                                positiveCorrectionNotice(preview!),
                              sourceView(businessMap(preview!['source'])),
                              if (preview!['can_finalize'] == true) ...[
                                CheckboxListTile(
                                  value: accepted,
                                  onChanged: write('personnel.approve') && !busy
                                      ? (v) =>
                                            setState(() => accepted = v == true)
                                      : null,
                                  title: Text(
                                    'Ich bestätige ausschließlich diesen geprüften Umfang: ${payrollScopes[preview!['calculation']['scope']]}',
                                  ),
                                ),
                                FilledButton(
                                  onPressed:
                                      accepted &&
                                          write('personnel.approve') &&
                                          !busy
                                      ? finalize
                                      : null,
                                  child: const Text(
                                    'Geprüften Berechnungsumfang festhalten',
                                  ),
                                ),
                              ],
                              TextButton(
                                onPressed: canPreview
                                    ? () =>
                                          [4, 5].contains(
                                            preview?['source']?['source_schema_version'],
                                          )
                                          ? calculatePeriod(
                                              businessMap(
                                                preview!['source'][preview!['source']['source_schema_version'] ==
                                                        5
                                                    ? 'multiple_one_off_case'
                                                    : 'one_off_case'],
                                              ),
                                              previous: correction,
                                              reason:
                                                  runDraft?['correction_reason'] ??
                                                  '',
                                            )
                                          : calculate(correction)
                                    : null,
                                child: const Text('Eingaben erneut prüfen'),
                              ),
                            ],
                          ),
                        ),
                      ),
                    Text(
                      'Gespeicherte Berechnungen',
                      style: Theme.of(context).textTheme.titleLarge,
                    ),
                    for (final run in runs) runCard(run),
                    if (history.isNotEmpty) ...[
                      Text(
                        'Unveränderliche Historie',
                        style: Theme.of(context).textTheme.titleLarge,
                      ),
                      for (final record in history)
                        historyKind == 'profile'
                            ? profileCard(record, historical: true)
                            : runCard(record, historical: true),
                    ],
                  ],
                ),
        );
}

Future<VerifiedMailAttachment> payrollExportAttachment(
  Map<String, dynamic> record,
  Uint8List bytes,
  String format,
) async {
  final hash = _hex((await Sha256().hash(bytes)).bytes);
  if (format == 'pdf') {
    if (hash != record['pdf_sha256'] ||
        bytes.length < 5 ||
        utf8.decode(bytes.take(5).toList(), allowMalformed: true) != '%PDF-')
      throw const ApiException(
        0,
        'Das Berechnungs-PDF stimmt nicht mit der historischen Prüfsumme überein.',
      );
  } else if (format == 'json') {
    if (!payrollSame(jsonDecode(utf8.decode(bytes)), record))
      throw const ApiException(
        0,
        'Die JSON-Ausgabe stimmt nicht mit dem historischen Berechnungslauf überein.',
      );
    final payload = _copy(record);
    for (final key in [
      'id',
      'kind',
      'employee_id',
      'revision',
      'content_hash',
      'previous_hash',
      'created_by',
      'created_at',
      'pdf_sha256',
    ])
      payload.remove(key);
    final envelope = {
      for (final key in [
        'id',
        'kind',
        'employee_id',
        'revision',
        'previous_hash',
        'created_by',
        'created_at',
        'pdf_sha256',
      ])
        key: record[key],
      'identity_key': record['revision'] == 1
          ? '${record['kind']}:${record['kind'] == 'profile' ? payload['profile']['effective_from'] : payload['source']['month']}'
          : null,
      'payload': payload,
    };
    if (_hex(
          (await Sha256().hash(utf8.encode(jsonEncode(_order(envelope)))))
              .bytes,
        ) !=
        record['content_hash']) {
      throw const ApiException(0, 'Die JSON-Archivprüfsumme stimmt nicht.');
    }
  } else {
    throw const FormatException(
      'Nur PDF- und JSON-Ausgaben werden unterstützt.',
    );
  }
  return VerifiedMailAttachment(
    bytes: bytes,
    filename:
        'lohn-berechnung-${record['source']['month']}-v${record['revision']}.$format',
    mediaType: format == 'pdf' ? 'application/pdf' : 'application/json',
    sha256: hash,
  );
}

class _PayrollFacts extends StatelessWidget {
  const _PayrollFacts({required this.value});
  final dynamic value;
  @override
  Widget build(BuildContext context) {
    if (value is List)
      return Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [for (final row in value) _PayrollFacts(value: row)],
      );
    if (value is Map)
      return Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          for (final entry in (value as Map).entries)
            Padding(
              padding: const EdgeInsets.only(top: 4),
              child: entry.value is Map || entry.value is List
                  ? ExpansionTile(
                      title: Text(
                        _profileLabels[entry.key] ??
                            _transitionLabels[entry.key] ??
                            const {
                              'profile': 'Lohnprofil',
                              'source_file': 'Originalnachweis',
                            }[entry.key] ??
                            '${entry.key}',
                      ),
                      children: [_PayrollFacts(value: entry.value)],
                    )
                  : SelectableText(
                      '${_profileLabels[entry.key] ?? _transitionLabels[entry.key] ?? entry.key}: ${['regular_monthly_gross_minor', 'regular_annual_gross_minor', 'tax_allowance_monthly_minor', 'tax_addition_monthly_minor'].contains(entry.key)
                          ? payrollMoney(entry.value)
                          : entry.value == null
                          ? 'Nicht angegeben'
                          : entry.value == true
                          ? 'Ja'
                          : entry.value == false
                          ? 'Nein'
                          : const {'within_transition_area': 'Belegter Übergangsbereich', 'regular': 'Reguläre Beschäftigung', 'minijob': 'Gewerblicher Minijob', 'flat_2_employer': 'Arbeitgeber trägt 2 % Pauschsteuer', 'individual': 'Individuelle Lohnsteuer', 'statutory_mandatory': 'Gesetzlich pflichtversichert', 'statutory_other': 'Sonstige gesetzliche Versicherung', 'private': 'Privat versichert', 'none': 'Keine', 'standard': 'Regulärer Satz'}[entry.value] ?? _federalStates[entry.value] ?? entry.value}',
                    ),
            ),
        ],
      );
    return Text(payrollSpecialCases[value] ?? '${value ?? 'Nicht angegeben'}');
  }
}

const payrollLedgerAmountLabels = {
  'gross_minor': 'Brutto',
  'employee_social_total_minor': 'Arbeitnehmerbeiträge',
  'employer_social_total_minor': 'Arbeitgeberbeiträge',
  'employer_flat_tax_minor': 'Arbeitgeber-Pauschsteuer',
  'individual_wage_tax_minor': 'Lohnsteuer',
  'solidarity_minor': 'Solidaritätszuschlag',
  'church_tax_minor': 'Kirchensteuer',
  'employee_tax_minor': 'Steuern gesamt',
  'net_minor': 'Netto',
  'payout_minor': 'Berechnete Auszahlung',
  'employee_additional_payment_minor': 'Zusätzlicher Arbeitnehmerbeitrag',
  'employer_total_excluding_accident_insurance_minor':
      'Arbeitgeberaufwand ohne Unfallversicherung',
};
Future<Map<String, dynamic>> payrollLedgerSnapshot(
  dynamic raw,
  String employee,
  int year,
) async {
  final view = businessMap(raw), ledger = businessMap(view['ledger']);
  if ((ledger['schema_version'] != 1 &&
          (ledger['schema_version'] is! int ||
              ledger['schema_version'] != 4)) ||
      ledger['employee']?['id'] != employee ||
      ledger['year'] != '$year' ||
      ledger['currency'] != 'EUR' ||
      ledger['totals_scope'] != 'recorded_effective_months_only' ||
      ledger['statutory_wage_account_complete'] is! bool ||
      ledger['statutory_report_status'] != 'not_transmitted' ||
      ledger['official_system_approval'] != false ||
      ledger['months'] is! List ||
      ledger['months'].length != 12 ||
      ledger['limitations'] is! List ||
      ledger['correction_history'] is! List) {
    throw const ApiException(
      0,
      'Jahresübersicht gehört nicht zum gewählten Mitarbeiter, Kalenderjahr oder Berechnungsumfang.',
    );
  }
  final recorded = <Map<String, dynamic>>[],
      missing = <String>[],
      partial = <String>[];
  for (var index = 0; index < 12; index++) {
    final month = '$year-${(index + 1).toString().padLeft(2, '0')}',
        m = businessMap(ledger['months'][index]);
    if (m['month'] != month)
      throw const ApiException(
        0,
        'Die Jahresübersicht enthält keinen eindeutigen Kalendermonat.',
      );
    if (m['status'] == 'missing') {
      if ([
        'calculation',
        'run_id',
        'revision',
        'content_hash',
        'source_refs',
      ].any((key) => m[key] != null))
        throw const ApiException(
          0,
          'Ein fehlender Monat darf keine berechneten Werte enthalten.',
        );
      missing.add(month);
    } else {
      if (!['complete', 'social_only'].contains(m['status']) ||
          !RegExp(r'^[a-f0-9]{32}$').hasMatch(
            '${m['origin'] == 'external_carryover' ? m['carryover_id'] : m['run_id']}',
          ) ||
          !RegExp(r'^[a-f0-9]{64}$').hasMatch('${m['content_hash']}') ||
          m['revision'] is! int ||
          m['revision'] < 1)
        throw const ApiException(0, 'Ein Monatsnachweis fehlt.');
      final calc = payrollCalculation(m['calculation']);
      payrollAccountPaymentStatus(m, ledger['account_records'] ?? [], employee);
      if (calc['month'] != month ||
          (m['status'] == 'complete') !=
              (calc['payroll_calculation_complete'] == true))
        throw const ApiException(
          0,
          'Monatsstatus und Berechnung widersprechen sich.',
        );
      recorded.add(m);
      if (m['status'] == 'social_only') partial.add(month);
    }
  }
  if (ledger['recorded_months'] != recorded.length ||
      !payrollSame(ledger['missing_months'], missing) ||
      !payrollSame(ledger['partial_months'], partial) ||
      ledger['calendar_year_complete'] != missing.isEmpty ||
      ledger['tax_totals_complete'] !=
          (recorded.isNotEmpty && partial.isEmpty) ||
      ledger['annual_totals_complete'] != (missing.isEmpty && partial.isEmpty))
    throw const ApiException(
      0,
      'Die Jahresvollständigkeit stimmt nicht mit den Monaten überein.',
    );
  int? sum(List<dynamic> amounts) {
    if (amounts.isEmpty || amounts.contains(null)) return null;
    if (amounts.any((n) => n is! int))
      throw const ApiException(0, 'Jahressummen benötigen genaue Centbeträge.');
    return amounts.fold<int>(0, (total, n) => total + (n as int));
  }

  for (final key in payrollLedgerAmountLabels.keys) {
    final amounts = recorded
        .map(
          (m) =>
              [
                    'commercial_minijob_flat_tax',
                    'commercial_minijob_period_flat_tax',
                  ].contains(m['calculation']['scope']) &&
                  [
                    'individual_wage_tax_minor',
                    'solidarity_minor',
                    'church_tax_minor',
                  ].contains(key)
              ? 0
              : m['calculation'][key],
        )
        .toList();
    if (ledger['totals']?[key] != sum(amounts))
      throw const ApiException(
        0,
        'Eine Jahressumme zählt Korrekturen doppelt oder ersetzt fehlende Werte.',
      );
  }
  for (final group in [
    'employee_contributions',
    'employer_contributions',
    'employer_levies',
  ]) {
    for (final key
        in group == 'employer_levies'
            ? ['u1', 'u2', 'insolvency']
            : [
                'health_general',
                'health_additional',
                'pension',
                'unemployment',
                'care',
              ]) {
      if (ledger['totals']?[group]?[key] !=
          sum(recorded.map((m) => m['calculation'][group][key]).toList()))
        throw const ApiException(0, 'Die Jahresbeitragssumme stimmt nicht.');
    }
  }
  if (ledger['statutory_wage_account_complete'] == true &&
      (ledger['supported_wage_account_fields_complete'] != true ||
          ledger['expected_employment_months'] is! List ||
          ledger['expected_employment_months'].isEmpty ||
          ledger['account_missing_months'] is! List ||
          ledger['account_missing_months'].isNotEmpty))
    throw const ApiException(
      0,
      'Die Lohnkonto-Vollständigkeit ist nicht belegt.',
    );
  final multiples = recorded
      .where((m) => m['calculation']['rule_version'] == payrollMultipleRule)
      .toList();
  if (ledger['schema_version'] == 4) {
    final expected = [
      for (final m in multiples)
        {
          'month': m['month'],
          'run_ref': {
            'id': m['run_id'],
            'revision': m['revision'],
            'content_hash': m['content_hash'],
          },
          'case_ref': m['source_refs']['multiple_one_off_case'],
          'details': m['calculation']['multiple_one_off_details'],
          'letter_s': false,
        },
    ];
    if (multiples.isEmpty ||
        !payrollSame(ledger['recorded_multiple_one_off_payments'], expected))
      throw const ApiException(
        0,
        'Die Jahresübersicht ersetzt die ursprünglichen Monatsgruppen.',
      );
    for (final m in multiples)
      payrollFactRef(m['source_refs']['multiple_one_off_case']);
  } else if (multiples.isNotEmpty ||
      ledger.containsKey('recorded_multiple_one_off_payments')) {
    throw const ApiException(
      0,
      'Die neue Monatsgruppe benötigt ihre eigene Jahresquellenfassung.',
    );
  }
  if (ledger.containsKey('account_records'))
    for (final record in businessItems(ledger['account_records']))
      payrollAccountRecord(record, employee);
  final payload = _copy(ledger)..remove('snapshot_hash');
  if (_hex(
        (await Sha256().hash(utf8.encode(jsonEncode(_order(payload))))).bytes,
      ) !=
      ledger['snapshot_hash'])
    throw const ApiException(
      0,
      'Die Prüfsumme der Jahresübersicht stimmt nicht.',
    );
  for (final format in ['pdf', 'csv', 'json']) {
    final manifest = businessMap(view['exports']?[format]);
    if (!RegExp(r'^[a-f0-9]{64}$').hasMatch('${manifest['sha256']}') ||
        manifest['size'] is! int ||
        manifest['size'] < 1 ||
        manifest['size'] > 21 * 1024 * 1024 ||
        manifest['filename'] is! String ||
        RegExp(r'[/\\\x00-\x1f]').hasMatch(manifest['filename']) ||
        manifest['media_type'] is! String)
      throw const ApiException(
        0,
        'Der Jahres-Exportnachweis ist unvollständig.',
      );
  }
  return view;
}

Future<VerifiedMailAttachment> payrollLedgerExportAttachment(
  Map<String, dynamic> view,
  Uint8List bytes,
  String format,
) async {
  final manifest = businessMap(view['exports']?[format]),
      hash = _hex((await Sha256().hash(bytes)).bytes);
  if (bytes.length != manifest['size'] || hash != manifest['sha256'])
    throw const ApiException(
      0,
      'Die Jahresausgabe stimmt nicht mit der gewählten Vorschau überein.',
    );
  if (format == 'json' &&
      !payrollSame(jsonDecode(utf8.decode(bytes)), view['ledger']))
    throw const ApiException(
      0,
      'JSON-Ausgabe und Jahresübersicht unterscheiden sich.',
    );
  return VerifiedMailAttachment(
    bytes: bytes,
    filename: manifest['filename'],
    mediaType: manifest['media_type'],
    sha256: hash,
  );
}

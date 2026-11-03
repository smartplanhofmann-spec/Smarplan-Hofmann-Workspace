import 'dart:convert';
import 'dart:typed_data';

import 'package:cryptography/cryptography.dart';
import 'package:flutter/material.dart';

import 'api.dart';
import 'business_personnel_workflow.dart' show personnelMinor;
import 'business_payroll_accounts.dart';
import 'business_payroll_cash.dart';
import 'business_payroll_cash_page.dart';
import 'business_session.dart';
import 'business_widgets.dart';
import 'design.dart';
import 'mail_attachment_preview.dart';
import 'mail_attachment_widgets.dart' show exportMailAttachment;

const payrollScopes = {
  'regular_transition_monthly':
      'Belegter Übergangsbereich · Vollmonat und PAP 2026',
  'regular_standard_monthly': 'Reguläre Standard-Monatsberechnung · PAP 2026',
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
  if (!payrollScopes.containsKey(scope) ||
      v['currency'] != 'EUR' ||
      v['gross_minor'] is! int ||
      v['gross_minor'] <= 0 ||
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
      if (scope == 'commercial_minijob_flat_tax' &&
          v['employee_tax_minor'] != 0) {
        throw const ApiException(
          0,
          'Die Arbeitgeber-Pauschsteuer darf nicht vom Minijob-Netto abgezogen werden.',
        );
      }
      if ([
            'regular_standard_monthly',
            'regular_transition_monthly',
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
          !payrollSame(v['profile'], frozen['profile']) ||
          !payrollSame(v['source_file'], {
            for (final key in ['id', 'employee_id', 'sha256', 'content_hash'])
              key: file?[key],
          });
    } else {
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
                    'regular_transition_monthly',
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
    if (!['standard', 'social_only'].contains(values['regular_tax_scope']))
      throw const FormatException(
        'Regulären Steuerumfang ausdrücklich wählen.',
      );
    if (values['regular_tax_scope'] == 'standard') {
      for (final key in [
        'tax_allowance_monthly_minor',
        'tax_addition_monthly_minor',
      ])
        result[key] = payrollTaxMinor(values[key]);
    }
  } else if (values['regular_tax_scope'] != 'minijob') {
    throw const FormatException('Minijob-Steuerumfang ausdrücklich wählen.');
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
      'Geprüfte Sonderfälle · betroffene Fälle bleiben gesperrt',
      type: BusinessInput.multiple,
      choices: payrollSpecialCases,
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
        'social_only': 'Regulär: Nur Sozialversicherung, Netto bleibt offen',
        'minijob': 'Minijob: Pauschsteuerverfahren',
      },
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

class _BusinessPayrollPageState extends State<BusinessPayrollPage> {
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
  final previews = <MailAttachmentPreviewController>[];
  BusinessSession get session => widget.session;
  String get employeeId => widget.employee['id'];
  String key(bool profile) =>
      'payroll-${profile ? 'profile' : 'run'}-$employeeId';
  bool get readable =>
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
    load();
  }

  @override
  void dispose() {
    epoch++;
    session.removeListener(changed);
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
    loading = false;
    for (final p in previews) p.revoke();
  }

  void changed() {
    if (!mounted) return;
    if (!payrollAvailable(session) ||
        (actorId != null && !readable) ||
        generation != session.generation) {
      clear();
      generation = session.generation;
    } else if (!session.can('personnel.read')) {
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
      for (final record in businessItems(result[1]))
        payrollCalculation(record['calculation']);
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
    await session.load();
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
      await session.read('/payroll/profiles?employee_id=$employeeId'),
    );
    if (page['employee_id'] != employeeId)
      throw const ApiException(
        0,
        'Der Mitarbeiterbezug konnte nicht bestätigt werden.',
      );
  }

  Future<void> repeat(bool profile) async {
    if (busy || !write(profile ? 'personnel.write' : 'personnel.approve'))
      return;
    setState(() {
      busy = true;
      error = null;
    });
    try {
      await session.repeatPayrollCommand(employeeId, profile: profile);
      if (!mounted || !readable) return;
      setState(() {
        message = 'Der ursprüngliche Payroll-Auftrag ist bestätigt.';
        preview = inputs = null;
        accepted = false;
      });
      await load();
    } catch (e) {
      failure(e);
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  Future<void> profile([Map<String, dynamic>? previous]) async {
    if (!write('personnel.write') || pendingProfile || busy) return;
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
        fields: payrollProfileFields(files, correction: previous != null),
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
    setState(() {
      busy = true;
      error = null;
    });
    try {
      await fresh(permission: 'personnel.approve');
      if (opening != session.generation || preview == null)
        throw const ApiException(
          409,
          'Datenstand geändert. Monatsberechnung erneut prüfen.',
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
      if (!mounted || !readable) return;
      setState(() {
        message = 'Der ausdrücklich bestätigte Berechnungsumfang ist unveränderlich gespeichert. Es wurde keine Meldung oder Zahlung ausgelöst.';
        preview = inputs = runDraft = correction = null;
        accepted = false;
      });
      await load();
    } catch (e) {
      failure(e);
    } finally {
      if (mounted) setState(() => busy = false);
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
      if (!profile) for (final r in rows) payrollCalculation(r['calculation']);
      if (mounted && readable && opening == session.generation)
        setState(() {
          history = rows;
          historyKind = profile ? 'profile' : 'run';
        });
    } catch (e) {
      failure(e);
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
                  'Brutto ${payrollMoney(month['calculation']?['gross_minor'])} · Netto ${payrollMoney(month['calculation']?['net_minor'])}',
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

  Widget calculationView(Map<String, dynamic> calc) => Column(
    crossAxisAlignment: CrossAxisAlignment.start,
    children: [
      Text(
        payrollScopes[calc['scope']]!,
        style: Theme.of(context).textTheme.titleLarge,
      ),
      Text('${calc['month']} · Brutto ${payrollMoney(calc['gross_minor'])}'),
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
            'Der Mindest-RV-Beitrag übersteigt das Brutto. Zusätzlicher Arbeitnehmeranteil: ${payrollMoney(calc['employee_additional_payment_minor'])}. Der berechnete Auszahlungsbetrag beträgt 0,00 €.',
          ),
      ],
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
      const Notice(
        'Unfallversicherung ist nicht enthalten. Reisekostenerstattungen werden getrennt verarbeitet. Amtliche Meldungen und Zahlungen erfolgen separat.',
      ),
    ],
  );
  Widget sourceView(Map<String, dynamic> source) => ExpansionTile(
    title: Text('Eingefrorene Quellen · ${source['month']}'),
    children: [
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
  Widget build(BuildContext context) => Scaffold(
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
              if (Navigator.canPop(context))
                OutlinedButton(
                  onPressed: () => Navigator.pop(context),
                  child: const Text('Zur Personalakte und Monatsvorbereitung'),
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
                            style: Theme.of(context).textTheme.titleMedium,
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
                  child: const Text('Belegte Lohnzahlungen für EÜR öffnen'),
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
                  title: const Text('Verifizierter Regelstand und Grenzen'),
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
                      'Vollmonatsfälle zwischen 18 und 64 Jahren. Übergangsbereich nur mit ausdrücklich belegter Zwölfmonatsprognose und vollständigen Steuermerkmalen. Sonderfälle und nicht unterstützte Versicherungskonstellationen bleiben gesperrt. Tatsächliche Kassen- und Umlagesätze anhand ihrer Nachweise erfassen.',
                    ),
                  ],
                ),
              const SizedBox(height: 12),
              Text(
                'Belegte Lohnprofile',
                style: Theme.of(context).textTheme.titleLarge,
              ),
              OutlinedButton(
                onPressed: write('personnel.write') && !pendingProfile && !busy
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
                    canPreview && profiles.isNotEmpty && preparations.isNotEmpty
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
                        calculationView(businessMap(preview!['calculation'])),
                        sourceView(businessMap(preview!['source'])),
                        if (preview!['can_finalize'] == true) ...[
                          CheckboxListTile(
                            value: accepted,
                            onChanged: write('personnel.approve') && !busy
                                ? (v) => setState(() => accepted = v == true)
                                : null,
                            title: Text(
                              'Ich bestätige ausschließlich diesen geprüften Umfang: ${payrollScopes[preview!['calculation']['scope']]}',
                            ),
                          ),
                          FilledButton(
                            onPressed:
                                accepted && write('personnel.approve') && !busy
                                ? finalize
                                : null,
                            child: const Text(
                              'Geprüften Berechnungsumfang festhalten',
                            ),
                          ),
                        ],
                        TextButton(
                          onPressed: canPreview
                              ? () => calculate(correction)
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
  if (ledger['schema_version'] != 1 ||
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
              m['calculation']['scope'] == 'commercial_minijob_flat_tax' &&
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

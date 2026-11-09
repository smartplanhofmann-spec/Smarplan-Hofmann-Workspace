import 'api.dart';
import 'business_payroll_facts.dart';
import 'business_session.dart' show businessMap, businessItems;

const individualMinijobRule = 'de_2026_individual_minijob_month_v11';
const individualMinijobScope = 'commercial_minijob_individual_month';
const individualMinijobFeature = 'payroll_individual_minijob';
const individualMinijobConfirmations = {
  'sole_employment_confirmed': 'Einzige Beschäftigung vollständig geprüft',
  'income_review_complete': 'Weitere Einkünfte vollständig geprüft',
  'no_other_relevant_income_confirmed': 'Keine weiteren relevanten Einkünfte',
  'domestic_commercial_employment_confirmed':
      'Inländischer gewerblicher Minijob',
  'no_foreign_insurance_confirmed': 'Keine ausländische Versicherung',
  'no_other_special_cases_confirmed': 'Keine weiteren Sonderfälle',
};
const individualMinijobEvidence = {
  'health_evidence_ref': 'Original der beitragsfreien Familienversicherung',
  'pension_evidence_ref': 'Original der RV-Pflicht oder wirksamen Befreiung',
  'employment_evidence_ref': 'Original zur einzigen Beschäftigung',
  'income_evidence_ref': 'Original der vollständigen Einkünfteprüfung',
  'elstam_evidence_ref': 'Original des tatsächlichen ELStAM-Nachweises',
};
final _hash = RegExp(r'^[a-f0-9]{64}$');
const _healthStatuses = {
  'statutory_family',
  'statutory_mandatory',
  'statutory_voluntary',
  'private',
  'unknown',
};
Never _fail(String message) => throw ApiException(400, message);
int _money(dynamic value) {
  if (value is! int || value < 0 || value > 1000000000000)
    _fail('Ungültiger belegter Geldbetrag.');
  return value;
}

String _note(dynamic value) {
  if (value is! String ||
      value.trim().isEmpty ||
      !_unicodeScalar(value) ||
      value.runes.length > 3000 ||
      RegExp(r'[\x00-\x08\x0b-\x1f]').hasMatch(value))
    _fail('Die belegte Prüfung vollständig dokumentieren.');
  return value.trim();
}

bool _unicodeScalar(String value) {
  final units = value.codeUnits;
  for (var i = 0; i < units.length; i++) {
    final unit = units[i];
    if (unit >= 0xd800 && unit <= 0xdbff) {
      if (++i >= units.length || units[i] < 0xdc00 || units[i] > 0xdfff)
        return false;
    } else if (unit >= 0xdc00 && unit <= 0xdfff)
      return false;
  }
  return true;
}

void _version(Map<String, dynamic> value) {
  if (value['rule_version'] != individualMinijobRule ||
      value['source_contract_version'] is! int ||
      value['source_contract_version'] != 3)
    _fail('Unbekannter Vertrag für den individuell besteuerten Minijob.');
}

void _emptyDetails(Map<String, dynamic> details) {
  for (final key in [
    'segment_events',
    'entitlement_case_refs',
    'travel_settlement_refs',
  ]) {
    if (details[key] is! List || details[key].isNotEmpty)
      _fail('Dieser Minijobfall enthält keine Zusatzansprüche oder Reisen.');
  }
  if (details['thirty_day_rule'] != null ||
      details['flat_tax_decision'] != null ||
      details.containsKey('travel_payment_refs'))
    _fail('Unbekannter Zusatz zum Minijobvertrag.');
  for (final key in [
    'employment_terms_refs',
    'profile_refs',
    'identity_refs',
  ]) {
    if (details[key] is! List || details[key].length != 1)
      _fail('Genau eine zusammengehörige Quellenfassung auswählen.');
    payrollFactRef(details[key].single);
  }
}

Map<String, dynamic> individualMinijobAssessment(
  dynamic raw,
  String employee,
  String month, {
  bool complete = true,
}) {
  final value = businessMap(raw), dates = payrollFactDates(month);
  final keys = {
    'schema_version',
    'employee_id',
    'valid_from',
    'valid_to',
    'declaration_date',
    'actual_health_insurance',
    'pension_status',
    'verification_note',
    ...individualMinijobConfirmations.keys,
    ...individualMinijobEvidence.keys,
  };
  if (value.keys.toSet().difference(keys).isNotEmpty ||
      keys.difference(value.keys.toSet()).isNotEmpty ||
      value['schema_version'] is! int ||
      value['schema_version'] != 1 ||
      value['employee_id'] is! String ||
      !RegExp(r'^[a-f0-9]{32}$').hasMatch(value['employee_id']) ||
      !_healthStatuses.contains(value['actual_health_insurance']) ||
      !['compulsory', 'exempt', 'unknown'].contains(value['pension_status']) ||
      individualMinijobConfirmations.keys.any((key) => value[key] is! bool))
    _fail(
      'Die persönliche Minijobprüfung enthält ungültige oder fehlende Angaben.',
    );
  final from = payrollFactDate(value['valid_from'])!,
      to = payrollFactDate(value['valid_to'])!;
  if (from.compareTo(to) > 0)
    _fail('Der Wirkungszeitraum der Minijobprüfung ist umgekehrt.');
  payrollFactDate(value['declaration_date']);
  _note(value['verification_note']);
  for (final key in individualMinijobEvidence.keys) {
    final ref = businessMap(value[key]);
    payrollFactRef(ref);
    if (ref.length != 3 ||
        !ref.keys.toSet().containsAll({'id', 'revision', 'content_hash'}) ||
        ref['revision'] != 1)
      _fail(
        'Jeder persönliche Prüfbeleg benötigt seine unveränderte Dateifassung.',
      );
  }
  if (complete &&
      (value['employee_id'] != employee ||
          from.compareTo(dates.first) > 0 ||
          to.compareTo(dates.last) < 0 ||
          value['actual_health_insurance'] != 'statutory_family' ||
          !['compulsory', 'exempt'].contains(value['pension_status']) ||
          individualMinijobConfirmations.keys.any((key) => value[key] != true)))
    _fail(
      'Die persönliche Minijobprüfung ist nicht vollständig für diesen vollen Monat belegt.',
    );
  return value;
}

Map<String, dynamic> individualMinijobPlan(
  dynamic raw,
  String employee,
  String month,
) {
  final value = businessMap(raw);
  _version(value);
  final dates = payrollFactDates(month);
  if (value['schema_version'] != 1 ||
      value['employee_id'] != employee ||
      value['month'] != month ||
      [
        'rules_sha256',
        'source_snapshot_hash',
        'plan_hash',
      ].any((key) => !_hash.hasMatch('${value[key]}')) ||
      [
        'earnings',
        'employment_intervals',
        'identity_intervals',
        'tax_periods',
        'social_periods',
        'blockers',
      ].any((key) => value[key] is! List) ||
      value['can_confirm'] is! bool ||
      value['can_calculate'] is! bool ||
      value['can_calculate'] != value['blockers'].isEmpty ||
      value.containsKey('claims_component_hash') ||
      value.containsKey('travel_source_hashes'))
    _fail(
      'Der Minijobplan ist nicht an seinen eigenen Regel- und Quellenvertrag gebunden.',
    );
  final assessment = individualMinijobAssessment(
    value['individual_minijob_assessment'],
    employee,
    month,
    complete: value['can_calculate'],
  );
  payrollFactRef(value['selected_profile_ref']);
  payrollFactRef(value['selected_identity_ref']);
  if (value['actual_health_insurance'] !=
          assessment['actual_health_insurance'] ||
      !value['can_calculate'] && value['technical_pap_parameters'] != null)
    _fail('Die tatsächlichen Versicherungsmerkmale widersprechen der Prüfung.');
  if (value['can_calculate']) {
    final gross = _money(value['gross_minor']);
    if (gross < 17500 || gross > 60300)
      _fail('Dieser Minijobumfang gilt von 175 bis 603 Euro Monatslohn.');
    for (final key in [
      'employment_intervals',
      'identity_intervals',
      'tax_periods',
      'social_periods',
    ]) {
      final rows = businessItems(value[key]);
      if (rows.length != 1 ||
          rows.single['start'] != dates.first ||
          rows.single['end'] != dates.last)
        _fail(
          'Dieser Minijobumfang benötigt einen unveränderten vollen Monat.',
        );
    }
    if (value['tax_periods'][0]['lzz'] != 2 ||
        value['tax_periods'][0]['tax_days'] != 30 ||
        value['social_periods'][0]['days'] != 30 ||
        value['social_periods'][0]['full_month'] != true ||
        value['earnings'].length != 1 ||
        value['earnings'][0]['kind'] != 'ordinary_work' ||
        value['earnings'][0]['gross_minor'] != gross)
      _fail(
        'Zusatzentgelte oder Teilmonate gehören nicht zu diesem Minijobumfang.',
      );
  }
  return value;
}

bool individualMinijobCanConvert(dynamic raw) {
  final value = businessMap(raw),
      sources = businessMap(value['sources']),
      plan = businessMap(value['plan']);
  final profiles = sources['profiles'];
  return value['rule_version'] == 'de_2026_segments_entitlements_v5' &&
      value['source_contract_version'] == 1 &&
      value['status'] == 'active' &&
      plan['can_calculate'] == false &&
      plan['blockers'] is List &&
      (plan['blockers'] as List).any(
        (b) => b is Map && b['code'] == 'minijob_individual_tax',
      ) &&
      profiles is List &&
      profiles.length == 1 &&
      profiles.single['profile']?['employment_kind'] == 'minijob' &&
      profiles.single['profile']?['minijob_tax'] == 'individual';
}

void _bindings(
  Map<String, dynamic> sources,
  Map<String, dynamic> details,
  List files,
  String employee,
  Map<String, dynamic> plan,
) {
  _version(sources);
  _emptyDetails(details);
  final month = details['month'];
  if (sources['schema_version'] != 1 ||
      sources['employee_id'] != employee ||
      sources['month'] != month)
    _fail(
      'Die Minijobquellen gehören nicht zur ausgewählten Person und zum Monat.',
    );
  payrollFactRecord(sources['period_case'], employee, kind: 'period_case');
  if (!payrollFactsSame(
    payrollFactRef(sources['period_case']),
    details['period_case_ref'],
  ))
    _fail('Der Minijob-Basisfall wurde ersetzt.');
  for (final pair in [
    ['employment_terms', 'employment_terms_refs'],
    ['profiles', 'profile_refs'],
    ['identities', 'identity_refs'],
  ]) {
    final rows = businessItems(sources[pair[0]]);
    if (rows.length != 1 ||
        rows.single['employee_id'] != employee ||
        !payrollFactsSame(rows.map(payrollFactRef).toList(), details[pair[1]]))
      _fail('Eine Minijobquellenfassung wurde ersetzt.');
  }
  for (final key in ['segment_events', 'entitlements', 'travel_sources']) {
    if (sources[key] is! List || sources[key].isNotEmpty)
      _fail('Der Minijobquellstand enthält zusätzliche Sachverhalte.');
  }
  if (sources['flat_travel_tax'] != null || sources['thirty_day_rule'] != null)
    _fail('Zusätzliche Reisesteuer- oder Verteilungsregeln sind unzulässig.');
  final assessment = individualMinijobAssessment(
    details['individual_minijob_assessment'],
    employee,
    month,
    complete: plan['can_calculate'],
  );
  if (!payrollFactsSame(assessment, sources['individual_minijob_assessment']) ||
      !payrollFactsSame(assessment, plan['individual_minijob_assessment']))
    _fail('Die persönliche Minijobprüfung wurde ersetzt.');
  final originals = businessItems(sources['source_files']);
  if (originals.any((file) => file['employee_id'] != employee) ||
      !payrollFactsSame(
        originals.map((file) => file['id']).toList()..sort(),
        [...files]..sort(),
      ))
    _fail('Die privaten Minijoboriginale wurden ersetzt.');
  for (final key in individualMinijobEvidence.keys) {
    final ref = assessment[key];
    if (!originals.any(
      (file) =>
          file['id'] == ref['id'] &&
          ref['revision'] == 1 &&
          file['content_hash'] == ref['content_hash'],
    ))
      _fail('Ein konkreter persönlicher Prüfbeleg fehlt.');
  }
  final profile = sources['profiles'][0],
      p = profile['profile'],
      identity = sources['identities'][0],
      d = identity['details'];
  if (!payrollFactsSame(assessment['elstam_evidence_ref'], {
        'id': identity['source_file']['id'],
        'revision': 1,
        'content_hash': identity['source_file']['content_hash'],
      }) ||
      !payrollFactsSame(
        plan['selected_profile_ref'],
        payrollFactRef(profile),
      ) ||
      !payrollFactsSame(
        plan['selected_identity_ref'],
        payrollFactRef(identity),
      ))
    _fail(
      'Die Minijobprüfung gehört nicht zu den ursprünglichen Quellenfassungen.',
    );
  if (plan['can_calculate'] &&
      (p['employment_kind'] != 'minijob' ||
          p['minijob_tax'] != 'individual' ||
          p['health_insurance'] != 'statutory_other' ||
          ![1, 5].contains(p['tax_class']) ||
          p['tax_children_half_units'] != 0 ||
          p['church_tax'] != 'none' ||
          p['special_cases'] is! List ||
          p['special_cases'].isNotEmpty ||
          p['minijob_rv_exempt'] is! bool ||
          (assessment['pension_status'] == 'exempt') !=
              p['minijob_rv_exempt'] ||
          d['identity_source_schema_version'] is! int ||
          d['identity_source_schema_version'] != 2 ||
          d['profile_id'] != profile['id'] ||
          d['profile_revision'] != profile['revision'] ||
          d['tax_source'] != 'elstam_imported' ||
          d['tax_allowance_yearly_minor'] != 0 ||
          d['tax_addition_yearly_minor'] != 0 ||
          d['religion_code'] != 'none'))
    _fail(
      'Steuer- und Versicherungsmerkmale sind nicht an die tatsächlichen Originale gebunden.',
    );
  final pap = businessMap(plan['technical_pap_parameters']);
  final expected = {
    'ALTER1': 0,
    'ALV': 1,
    'KRV': p['minijob_rv_exempt'] ? 1 : 0,
    'KVZ': '0',
    'LZZ': 2,
    'LZZFREIB': 0,
    'LZZHINZU': 0,
    'PKPV': 0,
    'PKPVAGZ': 0,
    'PKV': 1,
    'PVA': 0,
    'PVS': 0,
    'PVZ': 0,
    'RE4': plan['gross_minor'],
    'STKL': p['tax_class'],
    'ZKF': 0,
    'af': 0,
    'f': '1',
  };
  if (plan['can_calculate'] && !payrollFactsSame(pap, expected))
    _fail(
      'Die technischen PAP-Merkmale widersprechen der belegten Familienversicherung.',
    );
}

Map<String, dynamic> individualMinijobRecord(dynamic raw, String employee) {
  final value = businessMap(raw);
  _version(value);
  payrollFactRef(value);
  final details = businessMap(value['details']),
      sources = businessMap(value['sources']);
  if (value['employee_id'] != employee ||
      value['kind'] != 'calculation_case' ||
      !['active', 'void'].contains(value['status']) ||
      !_hash.hasMatch('${value['source_hash']}') ||
      !_hash.hasMatch('${value['preview_hash']}') ||
      value['source_file_ids'] is! List ||
      value['source_file_ids'].isEmpty ||
      (value['revision'] == 1
          ? value['previous_hash'] != null
          : !_hash.hasMatch('${value['previous_hash']}')))
    _fail(
      'Die Minijobfassung gehört nicht zum ursprünglichen Mitarbeiterauftrag.',
    );
  final plan = individualMinijobPlan(value['plan'], employee, details['month']);
  if (plan['source_snapshot_hash'] != value['source_hash'])
    _fail('Minijobplan und Quellenhash widersprechen sich.');
  _bindings(sources, details, value['source_file_ids'], employee, plan);
  return value;
}

Map<String, dynamic> individualMinijobPreview(
  dynamic raw,
  Map<String, dynamic> body,
) {
  final value = businessMap(raw),
      sources = businessMap(value['source_snapshot']);
  final plan = individualMinijobPlan(
    value['plan'],
    body['employee_id'],
    body['details']['month'],
  );
  if (value['employee_id'] != body['employee_id'] ||
      value['kind'] != 'calculation_case' ||
      plan['source_snapshot_hash'] != value['source_hash'] ||
      !_hash.hasMatch('${value['source_hash']}') ||
      !_hash.hasMatch('${value['preview_hash']}') ||
      value['can_confirm'] != plan['can_confirm'] ||
      value['can_calculate'] != plan['can_calculate'] ||
      [
        'can_write',
        'can_approve',
        'writes_enabled',
      ].any((key) => value[key] is! bool))
    _fail('Die Minijobvorschau gehört nicht zur geprüften Quellenwahl.');
  _bindings(
    sources,
    body['details'],
    body['source_file_ids'],
    body['employee_id'],
    plan,
  );
  return value;
}

Map<String, dynamic> individualMinijobInput(
  String employee,
  Map<String, dynamic> sources,
  Map<String, dynamic> values, {
  Map<String, dynamic>? previous,
}) {
  final month = payrollFactMonth(values['month']);
  if (previous != null &&
      (previous['employee_id'] != employee ||
          previous['details']['month'] != month ||
          previous['rule_version'] != individualMinijobRule &&
              !individualMinijobCanConvert(previous)))
    _fail(
      'Nur den eigenen unbenutzten gesperrten Minijobfall ausdrücklich berichtigen.',
    );
  Map<String, dynamic> select(String collection, String id, [String? kind]) {
    final row = businessItems(sources[collection])
        .where(
          (row) =>
              row['id'] == id &&
              row['status'] != 'void' &&
              (kind == null || row['kind'] == kind),
        )
        .firstOrNull;
    if (row == null || row['employee_id'] != employee)
      _fail('Eine aktuelle eigene Quellenfassung auswählen.');
    return payrollFactRef(row);
  }

  final files = List<String>.from(values['source_file_ids'] as List? ?? []);
  if (files.isEmpty ||
      files.length > 20 ||
      files.toSet().length != files.length ||
      files.any(
        (id) => !businessItems(sources['files']).any(
          (file) =>
              file['id'] == id &&
              file['employee_id'] == employee &&
              file['purpose'] == 'personnel',
        ),
      ))
    _fail('Die geschützten Prüfbelege ausdrücklich auswählen.');
  final assessment = <String, dynamic>{
    'schema_version': 1,
    'employee_id': employee,
    'valid_from': values['valid_from'],
    'valid_to': values['valid_to'],
    'declaration_date': values['declaration_date'],
    'actual_health_insurance': values['actual_health_insurance'],
    'pension_status': values['pension_status'],
    'verification_note': _note(values['assessment_note']),
    for (final key in individualMinijobConfirmations.keys) key: values[key],
  };
  for (final key in individualMinijobEvidence.keys) {
    final file = businessItems(sources['files'])
        .where((file) => file['id'] == values['${key}_id'])
        .firstOrNull;
    if (file == null ||
        file['employee_id'] != employee ||
        file['purpose'] != 'personnel' ||
        !files.contains(file['id']))
      _fail('Jeden persönlichen Prüfbeleg zusätzlich am Fall binden.');
    assessment[key] = {
      'id': file['id'],
      'revision': 1,
      'content_hash': file['content_hash'],
    };
  }
  individualMinijobAssessment(assessment, employee, month, complete: false);
  return {
    'employee_id': employee,
    'employee_revision': sources['employee']['revision'],
    'kind': 'calculation_case',
    'rule_version': individualMinijobRule,
    'source_contract_version': 3,
    'details': {
      'month': month,
      'period_case_ref': select(
        'facts',
        values['period_case_id'],
        'period_case',
      ),
      'employment_terms_refs': [
        select('facts', values['employment_terms_id'], 'employment_terms'),
      ],
      'profile_refs': [select('profiles', values['profile_id'])],
      'identity_refs': [select('identities', values['identity_id'])],
      'segment_events': [],
      'thirty_day_rule': null,
      'entitlement_case_refs': [],
      'travel_settlement_refs': [],
      'flat_tax_decision': null,
      'verification_note': _note(values['verification_note']),
      'individual_minijob_assessment': assessment,
    },
    'source_file_ids': files..sort(),
    'revision': previous?['revision'] ?? 0,
    'status': 'active',
    'confirmed': true,
    if (previous != null) ...{
      'id': previous['id'],
      'correction_reason': _note(values['correction_reason']),
    },
  };
}

Map<String, dynamic> individualMinijobCalculation(dynamic raw) {
  final value = businessMap(raw);
  _version(value);
  final details = businessMap(value['period_details']);
  if (value['currency'] != 'EUR' ||
      value['payroll_calculation_complete'] is! bool ||
      value['social_contributions_available'] !=
          value['payroll_calculation_complete'] ||
      value['official_system_approval'] != false ||
      value['statutory_report_status'] != 'not_transmitted' ||
      value['accident_insurance_included'] != false ||
      value['travel_expenses_included_in_net'] != false ||
      value['blockers'] is! List ||
      !_hash.hasMatch('${value['rules_sha256']}') ||
      !_hash.hasMatch('${details['plan_hash']}') ||
      !_hash.hasMatch('${details['source_snapshot_hash']}'))
    _fail('Unbekannter abschließbarer individueller Minijobumfang.');
  payrollFactMonth(value['month']);
  for (final key in [
    'entitlement_sources',
    'unpaid_dates',
    'social_continuation',
  ]) {
    if (details[key] is! List || details[key].isNotEmpty)
      _fail('Der Minijoblauf enthält zusätzliche Ansprüche.');
  }
  if (details['flat_travel_tax'] != null ||
      !payrollFactsSame(details['travel'], {
        'benefit_in_kind_non_cash_minor': 0,
        'flat_taxable_payroll_minor': 0,
        'individual_taxable_payroll_minor': 0,
        'letter_m': false,
        'tax_free_external_minor': 0,
      }))
    _fail('Dieser Minijoblauf enthält keine Reisen oder Pauschalsteuer.');
  if (!value['payroll_calculation_complete']) {
    const unavailable = [
      'employee_contributions',
      'employer_contributions',
      'employee_social_total_minor',
      'employer_social_total_minor',
      'employer_levies',
      'employer_flat_tax_minor',
      'employer_total_excluding_accident_insurance_minor',
      'individual_wage_tax_minor',
      'solidarity_minor',
      'church_tax_minor',
      'employee_tax_minor',
      'net_minor',
      'payout_minor',
      'employee_additional_payment_minor',
    ];
    if (value['scope'] != 'unsupported' ||
        value['blockers'].isEmpty ||
        unavailable.any(
          (key) => !value.containsKey(key) || value[key] != null,
        ) ||
        value['net_deductions_minor'] != 0 ||
        value['tax_parameters']?['technical_pap_parameters'] != null ||
        !_healthStatuses.contains(
          value['tax_parameters']?['actual_health_insurance'],
        ))
      _fail(
        'Ein gesperrter Minijobfall darf keine berechnete Auszahlung ausweisen.',
      );
    return value;
  }
  if (value['scope'] != individualMinijobScope || value['blockers'].isNotEmpty)
    _fail('Unbekannter abschließbarer individueller Minijobumfang.');
  int sum(dynamic raw) =>
      businessMap(raw).values.fold(0, (sum, item) => sum + _money(item));
  if (sum(value['employee_contributions']) !=
          value['employee_social_total_minor'] ||
      sum(value['employer_contributions']) !=
          value['employer_social_total_minor'] ||
      value['employer_flat_tax_minor'] != 0 ||
      value['church_tax_minor'] != 0 ||
      value['solidarity_minor'] != 0 ||
      value['net_deductions_minor'] != 0 ||
      _money(value['gross_minor']) < 17500 ||
      value['gross_minor'] > 60300 ||
      value['individual_wage_tax_minor'] != value['employee_tax_minor'] ||
      value['net_minor'] !=
          value['gross_minor'] -
              value['employee_social_total_minor'] -
              value['employee_tax_minor'] ||
      value['payout_minor'] != value['net_minor'] ||
      value['employee_additional_payment_minor'] != 0 ||
      value['employer_total_excluding_accident_insurance_minor'] !=
          value['gross_minor'] +
              value['employer_social_total_minor'] +
              sum(value['employer_levies']))
    _fail(
      'Minijobbeiträge, individuelle Steuer und Nettobetrag widersprechen sich.',
    );
  if (value['tax_parameters']?['actual_health_insurance'] !=
          'statutory_family' ||
      value['tax_parameters']?['children_half_units'] != 0 ||
      value['tax_parameters']?['church_tax_percent'] != '0' ||
      ![1, 5].contains(value['tax_parameters']?['tax_class']) ||
      [
        'health_general',
        'health_additional',
        'care',
        'unemployment',
      ].any((key) => value['employee_contributions'][key] != 0) ||
      [
        'health_additional',
        'care',
        'unemployment',
      ].any((key) => value['employer_contributions'][key] != 0))
    _fail(
      'Die tatsächlichen Steuer- und Versicherungsmerkmale widersprechen dem Minijobumfang.',
    );
  final dates = payrollFactDates(value['month']);
  for (final key in ['employment_intervals', 'tax_periods', 'social_periods']) {
    final rows = businessItems(details[key]);
    if (rows.length != 1 ||
        rows.single['start'] != dates.first ||
        rows.single['end'] != dates.last)
      _fail(
        'Die individuelle Minijobrechnung muss genau einen vollen Monat belegen.',
      );
  }
  if (details['tax_periods'][0]['lzz'] != 2 ||
      details['tax_periods'][0]['tax_days'] != 30 ||
      details['social_periods'][0]['full_month'] != true ||
      details['social_periods'][0]['days'] != 30)
    _fail(
      'Die individuelle Minijobrechnung enthält eine unzulässige Teilperiode.',
    );
  final tax = businessItems(details['tax_assessments']),
      social = businessItems(details['social_assessments']);
  if (tax.length != 1 ||
      social.length != 1 ||
      !payrollFactsSame(
        tax.map((v) => v['period']).toList(),
        details['tax_periods'],
      ) ||
      !payrollFactsSame(
        social.map((v) => v['period']).toList(),
        details['social_periods'],
      ))
    _fail('Die direkten PAP- und Beitragsnachweise fehlen.');
  final pap = tax.single['calculation'];
  if (pap['version'] != 'bmf_2026_individual_minijob_month_v1' ||
      pap['LSTLZZ'] != value['individual_wage_tax_minor'] ||
      pap['SOLZLZZ'] != 0 ||
      pap['BK'] != 0 ||
      pap['provenance_sha256'] != value['pap_provenance_sha256'])
    _fail('Die individuelle PAP-Steuer gehört nicht zum Minijoblauf.');
  for (final key in [
    'employee_contributions',
    'employer_contributions',
    'employer_levies',
  ]) {
    if (!payrollFactsSame(value[key], social.single[key]))
      _fail('Die einzelne Beitragsrechnung wurde ersetzt.');
  }
  return value;
}

Map<String, dynamic> individualMinijobSource(
  dynamic raw,
  Map<String, dynamic> input,
) {
  final value = businessMap(raw),
      source = businessMap(value['source']),
      calculation = individualMinijobCalculation(value['calculation']);
  final fact = individualMinijobRecord(
    source['calculation_case'],
    input['employee_id'],
  );
  if (source['source_schema_version'] != 3 ||
      source['employee_id'] != input['employee_id'] ||
      source['month'] != fact['details']['month'] ||
      !payrollFactsSame(source['input'], input) ||
      !payrollFactsSame(payrollFactRef(fact), input['calculation_case_ref']) ||
      !payrollFactsSame(
        source['preparation'],
        fact['sources']['period_case']['sources']['preparation'],
      ) ||
      !payrollFactsSame(source['profile'], fact['sources']['profiles'][0]) ||
      calculation['payroll_calculation_complete'] !=
          fact['plan']['can_calculate'] ||
      calculation['month'] != source['month'] ||
      calculation['gross_minor'] != fact['plan']['gross_minor'] ||
      calculation['period_details']['plan_hash'] != fact['plan']['plan_hash'] ||
      calculation['period_details']['source_snapshot_hash'] !=
          fact['source_hash'] ||
      !payrollFactsSame(
        calculation['tax_parameters']['technical_pap_parameters'],
        fact['plan']['technical_pap_parameters'],
      ) ||
      calculation['tax_parameters']['actual_health_insurance'] !=
          fact['plan']['actual_health_insurance'] ||
      calculation['tax_parameters']['tax_class'] !=
          source['profile']['profile']['tax_class'] ||
      value['can_finalize'] != calculation['payroll_calculation_complete'])
    _fail(
      'Der individuelle Minijoblauf gehört nicht zum geprüften Originalfall.',
    );
  for (final key in [
    'earnings',
    'employment_intervals',
    'identity_intervals',
    'tax_periods',
    'social_periods',
  ]) {
    if (!payrollFactsSame(
      calculation['period_details'][key],
      fact['plan'][key],
    ))
      _fail('Ein Minijobzeitraum wurde gegenüber dem Plan verändert.');
  }
  return value;
}

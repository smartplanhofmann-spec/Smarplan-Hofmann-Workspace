import 'dart:convert';

import 'api.dart';
import 'business_payroll_facts.dart';
import 'business_payroll_calculation_case_contract.dart';
import 'business_payroll_annual_basis_contract.dart';
import 'business_session.dart' show businessMap, businessItems;

const payrollOneOffRule = 'de_2026_oneoff_composition_v6';
Map<String, dynamic> payrollOneOffCaseRunInput(Map<String, dynamic> fact) {
  payrollOneOffCaseRecord(fact, fact['employee_id']);
  if (fact['status'] != 'active' ||
      fact['plan']['payroll_calculation_complete'] != true)
    _fail(
      'Nur ein aktiver vollständig berechenbarer Einmalbezugsfall kann einen Lohnlauf begründen.',
      400,
    );
  return {
    'source_schema_version': 4,
    'employee_id': fact['employee_id'],
    'one_off_case_ref': payrollFactRef(fact),
  };
}

Map<String, dynamic> payrollOneOffSource(
  dynamic raw,
  Map<String, dynamic> input,
) {
  final v = businessMap(raw),
      s = businessMap(v['source']),
      c = payrollOneOffCalculation(v['calculation']),
      fact = payrollOneOffCaseRecord(s['one_off_case'], input['employee_id']);
  if (s['source_schema_version'] != 4 ||
      s['employee_id'] != input['employee_id'] ||
      !payrollFactsSame(s['input'], input) ||
      !payrollFactsSame(payrollFactRef(fact), input['one_off_case_ref']) ||
      fact['status'] != 'active' ||
      s['month'] != fact['details']['month'] ||
      c['month'] != s['month'] ||
      !payrollFactsSame(c, fact['plan']) ||
      !payrollFactsSame(
        s['calculation_case'],
        fact['sources']['calculation_source']['running_calculation_case'],
      ) ||
      v['can_finalize'] != c['payroll_calculation_complete'])
    _fail(
      'Die Einmalbezugs-Lohnvorschau gehört nicht zum gewählten ursprünglichen Fall.',
    );
  final runningInput = {
    'source_schema_version': 3,
    'employee_id': input['employee_id'],
    'calculation_case_ref': payrollFactRef(s['calculation_case']),
  };
  payrollCompositeSource({
    ...v,
    'source': {...s, 'source_schema_version': 3, 'input': runningInput},
    'calculation': c['running_calculation'],
    'can_finalize': c['running_calculation']['payroll_calculation_complete'],
  }, runningInput);
  return v;
}

final _id = RegExp(r'^[a-f0-9]{32}$'), _hash = RegExp(r'^[a-f0-9]{64}$');
Never _fail(String message, [int status = 0]) =>
    throw ApiException(status, message);
Map<String, dynamic> _copy(dynamic value) =>
    Map<String, dynamic>.from(jsonDecode(jsonEncode(value)) as Map);
String _note(dynamic value) {
  if (value is! String ||
      value.trim().isEmpty ||
      value.trim().length > 3000 ||
      RegExp(r'[\x00-\x1f\x7f]').hasMatch(value))
    _fail('Den konkreten Einmalbezugsfall nachvollziehbar belegen.', 400);
  return value.trim();
}

int _integer(dynamic value, [int min = 0]) {
  if (value is! int || value < min || value > 1000000000000)
    _fail('Der Einmalbezugsfall enthält keinen eindeutigen Centbetrag.');
  return value;
}

int _sum(dynamic value) {
  if (value is! Map || value.isEmpty)
    _fail('Die getrennte Beitragsaufstellung fehlt.');
  return value.values.fold<int>(0, (sum, item) => sum + _integer(item));
}

const _moneyFields = [
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
  'net_deductions_minor',
  'payout_minor',
  'employee_additional_payment_minor',
];
List<String> _keys(dynamic value) => businessMap(value).keys.toList()..sort();

Map<String, dynamic> payrollOneOffCalculation(dynamic raw) {
  final v = businessMap(raw),
      d = businessMap(v['one_off_details']),
      r = payrollCompositeCalculation(v['running_calculation']);
  if (v['rule_version'] != payrollOneOffRule ||
      v['source_contract_version'] != 1 ||
      !_hash.hasMatch('${v['rules_sha256']}') ||
      v['currency'] != 'EUR' ||
      v['official_system_approval'] != false ||
      v['statutory_report_status'] != 'not_transmitted' ||
      v['accident_insurance_included'] != false ||
      v['blockers'] is! List ||
      v['month'] != r['month'] ||
      !payrollFactsSame(v['period_details'], r['period_details']) ||
      !_hash.hasMatch('${d['source_snapshot_hash']}') ||
      d['actual_payment_created'] != false)
    _fail(
      'Der Einmalbezug ist nicht an die unveränderte laufende Rechnung gebunden.',
    );
  final receipt = payrollFactDate(d['receipt_date'])!;
  if (!receipt.startsWith(v['month']))
    _fail('Einmalzufluss und Lohnmonat widersprechen sich.');
  _integer(d['amount_minor']);
  for (final key in [
    'earning_ref',
    'current_annual_basis_ref',
    'annual_tax_forecast_ref',
  ])
    payrollFactRef(d[key]);
  if (d['previous_annual_basis_ref'] != null)
    payrollFactRef(d['previous_annual_basis_ref']);
  if (v['gross_minor'] !=
      (r['gross_minor'] == null ? null : r['gross_minor'] + d['amount_minor']))
    _fail(
      'Laufendes Brutto und einmaliger Anspruch wurden nicht genau einmal zusammengesetzt.',
    );
  if (v['scope'] == 'unsupported') {
    if (v['payroll_calculation_complete'] != false ||
        v['social_contributions_available'] != false ||
        (v['blockers'] as List).isEmpty ||
        _moneyFields.any((k) => v[k] != null))
      _fail(
        'Ein ungeklärter Einmalbezug darf keine angenommenen Netto- oder Steuerwerte erhalten.',
      );
    return v;
  }
  if (v['scope'] != 'regular_standard_oneoff' ||
      v['payroll_calculation_complete'] != true ||
      v['social_contributions_available'] != true ||
      (v['blockers'] as List).isNotEmpty ||
      r['scope'] != 'regular_standard_segments')
    _fail('Unbekannter abschließbarer Einmalbezugsumfang.');
  final a = businessMap(d['assignment']),
      s = businessMap(d['social']),
      t = businessMap(d['tax']);
  if (a['tax_year'] != 2026 ||
      ![2025, 2026].contains(a['social_year']) ||
      a['march_clause'] is! bool ||
      a['march_clause'] != (a['social_year'] == 2025) ||
      !payrollFactsSame(s['assignment'], a) ||
      s['rule_version'] != 'de_social_oneoff_2025_2026_v1' ||
      s['year'] != a['social_year'] ||
      ['rules_hash', 'source_hash'].any((k) => !_hash.hasMatch('${s[k]}')) ||
      t['pap_version'] != 'bmf_2026_2025_11_12_standard_oneoff_v1' ||
      !_hash.hasMatch('${t['pap_hash']}') ||
      d['assigned_part_key'] is! String ||
      (d['assigned_part_key'] as String).isEmpty)
    _fail(
      'SV-Zuordnung, tatsächliches Beitragsjahr und getrennte PAP-Sondersteuer sind nicht vollständig gebunden.',
    );
  payrollFactRef(a['assigned_period_ref']);
  final assigned = payrollFactDate(a['assigned_period_end'])!;
  payrollFactRef(s['profile_ref']);
  payrollFactRef(d['tax_profile_ref']);
  if (!assigned.startsWith('${a['social_year']}') ||
      !payrollFactsSame(_keys(a['bases_minor']), [
        'care',
        'health',
        'pension',
        'unemployment',
      ]) ||
      !payrollFactsSame(_keys(s['branch_bases']), [
        'care',
        'health',
        'pension',
        'unemployment',
      ]))
    _fail('Die einzelnen Versicherungszweige der Originalzuordnung fehlen.');
  for (final key in _keys(a['bases_minor'])) {
    final b = _integer(a['bases_minor'][key]);
    if (b > d['amount_minor'] ||
        s['branch_bases'][key]['total_minor'] != b ||
        s['branch_bases'][key]['employee_minor'] != b)
      _fail(
        'Die Einmalbeitragsbasis widerspricht ihrem konkreten zugeordneten Betrag.',
      );
  }
  if (_sum(s['employee_contributions']) != s['employee_total_minor'] ||
      _sum(s['employer_contributions']) != s['employer_total_minor'] ||
      s['employer_levies']?['u1'] != 0 ||
      s['employer_levies']?['u2'] != 0 ||
      s['employer_levies']?['insolvency'] != s['insolvency_minor'])
    _fail('Die getrennten Einmalbeiträge und Umlagen stimmen nicht.');
  for (final group in [
    'employee_contributions',
    'employer_contributions',
    'employer_levies',
  ]) {
    if (!payrollFactsSame(_keys(v[group]), _keys(r[group])) ||
        !payrollFactsSame(_keys(s[group]), _keys(r[group])))
      _fail('Die Beitragsgruppen der Zusammensetzung wurden ersetzt.');
    for (final key in _keys(r[group]))
      if (_integer(v[group][key]) != r[group][key] + _integer(s[group][key]))
        _fail(
          'Laufende und einmalige Beiträge summieren sich nicht zur Gesamtzahlung.',
        );
  }
  final difference =
      _integer(t['annual_tax_after_minor']) -
      _integer(t['annual_tax_before_minor']);
  if (_integer(t['STS']) != (difference < 0 ? 0 : difference) ||
      ![0, 8, 9].contains(d['church_tax_percent']) ||
      _integer(d['church_tax_minor']) !=
          _integer(t['BKS']) * d['church_tax_percent'] ~/ 100)
    _fail(
      'Die Sondersteuer oder getrennte Kirchensteuer widerspricht ihrer PAP-Grundlage.',
    );
  for (final pair in [
    ['individual_wage_tax_minor', t['STS']],
    ['solidarity_minor', _integer(t['SOLZS'])],
    ['church_tax_minor', d['church_tax_minor']],
  ])
    if (v[pair[0]] != r[pair[0]] + pair[1])
      _fail('Die Gesamtrechnung ersetzt die unveränderte laufende Steuer.');
  if (_sum(v['employee_contributions']) != v['employee_social_total_minor'] ||
      _sum(v['employer_contributions']) != v['employer_social_total_minor'] ||
      v['employee_tax_minor'] !=
          v['individual_wage_tax_minor'] +
              v['solidarity_minor'] +
              v['church_tax_minor'] ||
      v['net_minor'] !=
          v['gross_minor'] -
              v['employee_social_total_minor'] -
              v['employee_tax_minor'] ||
      v['net_deductions_minor'] != r['net_deductions_minor'] ||
      v['employer_flat_tax_minor'] != r['employer_flat_tax_minor'] ||
      v['employer_total_excluding_accident_insurance_minor'] !=
          r['employer_total_excluding_accident_insurance_minor'] +
              d['amount_minor'] +
              s['employer_total_minor'] +
              _sum(s['employer_levies']))
    _fail(
      'Gesamtbeiträge, Nettoabzüge und Arbeitgeberkosten sind nicht mit der laufenden Originalrechnung vereinbar.',
    );
  final cash = v['net_minor'] - v['net_deductions_minor'];
  if (v['payout_minor'] != (cash < 0 ? 0 : cash) ||
      v['employee_additional_payment_minor'] != (cash < 0 ? -cash : 0))
    _fail(
      'Die Einmalbezugs-Auszahlung berücksichtigt die belegten Nettoabzüge nicht.',
    );
  return v;
}

Map<String, dynamic> payrollOneOffCasePlan(
  dynamic raw,
  String employeeId,
  String month,
) {
  payrollFactMonth(month);
  final v = payrollOneOffCalculation(raw);
  if (!_id.hasMatch(employeeId) || v['month'] != month)
    _fail(
      'Einmalbezugsplan und gewählter Mitarbeiterzeitraum widersprechen sich.',
    );
  return v;
}

void _bindings(
  Map<String, dynamic> s,
  Map<String, dynamic> d,
  dynamic files,
  String id,
  Map<String, dynamic> plan,
) {
  final originals = businessItems(s['source_files']);
  if (s['schema_version'] != 1 ||
      s['employee']?['id'] != id ||
      s['employee']?['revision'] is! int ||
      s['employee']['revision'] < 1 ||
      !payrollFactsSame(s['details'], d) ||
      s['source_files'] is! List ||
      originals.any(
        (f) =>
            f['employee_id'] != id ||
            !_id.hasMatch('${f['id']}') ||
            !_hash.hasMatch('${f['content_hash']}'),
      ) ||
      !payrollFactsSame(originals.map((f) => f['id']).toList()..sort(), files))
    _fail(
      'Mitarbeiterrevision, konkrete Angaben oder Originale des Einmalbezugs wurden ersetzt.',
    );
  final c = businessMap(s['calculation_source']);
  if (c['schema_version'] != 1 ||
      c['source_contract_version'] != 1 ||
      c['rule_version'] != payrollOneOffRule ||
      c['employee_id'] != id ||
      c['month'] != d['month'])
    _fail('Der eingefrorene Einmalbezugsquellenstand ist unbekannt.');
  final r = payrollCalculationCaseRecord(c['running_calculation_case'], id);
  if (r['details']['month'] != d['month'] ||
      !payrollFactsSame(payrollFactRef(r), d['running_calculation_case_ref']))
    _fail('Der laufende Originalfall wurde ersetzt.');
  for (final pair in [
    ['one_off_earning', 'one_off_earning'],
    ['current_annual_basis', 'annual_basis'],
    ['previous_annual_basis', 'annual_basis'],
    ['annual_tax_forecast', 'annual_tax_forecast'],
  ]) {
    final key = pair[0];
    if (key == 'previous_annual_basis' &&
        c[key] == null &&
        d['${key}_ref'] == null)
      continue;
    final record = payrollAnnualRecord(c[key], id, kind: pair[1]);
    if (!payrollFactsSame(payrollFactRef(record), d['${key}_ref']))
      _fail('Eine konkrete Jahresquelle wurde gegenüber dem Auftrag ersetzt.');
  }
  final earning = c['one_off_earning'],
      current = c['current_annual_basis'],
      forecast = c['annual_tax_forecast'],
      p = plan['one_off_details'],
      original = plan['running_calculation'];
  if (!payrollFactsSame(current['sources']['current_calculation_case'], r) ||
      !payrollFactsSame(
        current['details']['current_calculation_case_ref'],
        d['running_calculation_case_ref'],
      ) ||
      !payrollFactsSame(forecast['sources']['annual_basis'], current) ||
      !payrollFactsSame(forecast['sources']['current_one_off'], earning) ||
      !payrollFactsSame(
        forecast['details']['annual_basis_ref'],
        d['current_annual_basis_ref'],
      ) ||
      !payrollFactsSame(
        forecast['details']['current_one_off_ref'],
        d['one_off_earning_ref'],
      ) ||
      !payrollFactsSame(p['earning_ref'], d['one_off_earning_ref']) ||
      !payrollFactsSame(
        p['current_annual_basis_ref'],
        d['current_annual_basis_ref'],
      ) ||
      !payrollFactsSame(
        p['previous_annual_basis_ref'],
        d['previous_annual_basis_ref'],
      ) ||
      !payrollFactsSame(
        p['annual_tax_forecast_ref'],
        d['annual_tax_forecast_ref'],
      ) ||
      p['receipt_date'] != earning['details']['planned_receipt_date'] ||
      p['amount_minor'] != earning['details']['amount_minor'] ||
      original['period_details']['plan_hash'] != r['plan']['plan_hash'] ||
      original['period_details']['source_snapshot_hash'] != r['source_hash'] ||
      original['gross_minor'] != r['plan']['gross_minor'])
    _fail(
      'Anspruch, Jahresbasis, Steuerprognose und laufende Rechnung gehören nicht zum selben ursprünglichen Fall.',
    );
  for (final k in [
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
  ])
    if (!payrollFactsSame(original['period_details'][k], r['plan'][k]))
      _fail(
        'Die laufende Originalrechnung ersetzt einen bestätigten Planbestandteil.',
      );
  if (plan['payroll_calculation_complete'] == true &&
      p['annual_pay_before_minor'] !=
          forecast['plan']['annual_pay_before_minor'])
    _fail('Die konkrete Steuerjahresgrundlage wurde ersetzt.');
}

Map<String, dynamic> payrollOneOffCaseRecord(dynamic raw, String id) {
  final v = businessMap(raw), d = businessMap(v['details']);
  payrollFactRef(v);
  if (v['employee_id'] != id ||
      v['kind'] != 'one_off_case' ||
      v['rule_version'] != payrollOneOffRule ||
      v['source_contract_version'] != 1 ||
      !['active', 'void'].contains(v['status']) ||
      ['source_hash', 'preview_hash'].any((k) => !_hash.hasMatch('${v[k]}')) ||
      (v['revision'] == 1
          ? v['previous_hash'] != null
          : !_hash.hasMatch('${v['previous_hash']}')) ||
      v['source_file_ids'] is! List ||
      (v['source_file_ids'] as List).isEmpty ||
      (v['source_file_ids'] as List).toSet().length !=
          (v['source_file_ids'] as List).length)
    _fail(
      'Die Einmalbezugsfassung gehört nicht eindeutig zum ursprünglichen Mitarbeiterauftrag.',
    );
  final plan = payrollOneOffCasePlan(v['plan'], id, d['month']);
  _bindings(businessMap(v['sources']), d, v['source_file_ids'], id, plan);
  return v;
}

Map<String, dynamic> payrollOneOffCaseSources(
  dynamic raw,
  String id,
  String month,
) {
  final v = payrollAnnualSources(raw, id);
  payrollFactMonth(month);
  if (v['month'] != month || v['one_off_cases'] is! List)
    _fail('Die Einmalbezugsquellen gehören nicht zum gewählten Monat.');
  for (final r in businessItems(v['one_off_cases']))
    payrollOneOffCaseRecord(r, id);
  return v;
}

Map<String, dynamic> payrollOneOffCaseInput(
  String id,
  Map<String, dynamic> sources,
  Map<String, dynamic> values, {
  Map<String, dynamic>? previous,
}) {
  final month = payrollFactMonth(values['month']),
      s = payrollOneOffCaseSources(sources, id, month);
  if (previous != null) {
    payrollOneOffCaseRecord(previous, id);
    if (previous['details']['month'] != month)
      _fail('Der ursprüngliche Einmalbezugsmonat bleibt erhalten.', 400);
  }
  final fileIds = values['source_file_ids'];
  if (fileIds is! List ||
      fileIds.isEmpty ||
      fileIds.length > 20 ||
      fileIds.toSet().length != fileIds.length ||
      fileIds.any((id) => !businessItems(s['files']).any((f) => f['id'] == id)))
    _fail('Ein bis zwanzig konkrete geschützte Originale auswählen.', 400);
  Map<String, dynamic> source(dynamic id, dynamic list, String kind) {
    final records = businessItems(list).where(
      (r) => r['id'] == id && r['status'] == 'active' && r['kind'] == kind,
    );
    if (records.length != 1)
      _fail('Die ausgewählte Originalfassung ist nicht mehr aktuell.', 400);
    return payrollFactRef(records.single);
  }

  return {
    'employee_id': id,
    'employee_revision': s['employee']['revision'],
    'kind': 'one_off_case',
    'rule_version': payrollOneOffRule,
    'source_contract_version': 1,
    'details': {
      'month': month,
      'running_calculation_case_ref': source(
        values['running_calculation_case_id'],
        s['calculation_cases'],
        'calculation_case',
      ),
      'one_off_earning_ref': source(
        values['one_off_earning_id'],
        s['annual_facts'],
        'one_off_earning',
      ),
      'current_annual_basis_ref': source(
        values['current_annual_basis_id'],
        s['annual_facts'],
        'annual_basis',
      ),
      'previous_annual_basis_ref':
          values['previous_annual_basis_id'] == null ||
              values['previous_annual_basis_id'] == ''
          ? null
          : source(
              values['previous_annual_basis_id'],
              s['annual_facts'],
              'annual_basis',
            ),
      'annual_tax_forecast_ref': source(
        values['annual_tax_forecast_id'],
        s['annual_facts'],
        'annual_tax_forecast',
      ),
      'verification_note': _note(values['verification_note']),
    },
    'source_file_ids': [...fileIds]..sort(),
    'revision': previous?['revision'] ?? 0,
    'status': 'active',
    'confirmed': true,
    if (previous != null) ...{
      'id': previous['id'],
      'correction_reason': _note(values['correction_reason']),
    },
  };
}

Map<String, dynamic> payrollOneOffCasePreviewInput(Map<String, dynamic> body) =>
    _copy({
      for (final k in [
        'employee_id',
        'employee_revision',
        'kind',
        'rule_version',
        'source_contract_version',
        'details',
        'source_file_ids',
      ])
        k: body[k],
    });
Map<String, dynamic> payrollOneOffCasePreview(
  dynamic raw,
  Map<String, dynamic> body,
) {
  final v = businessMap(raw),
      p = payrollOneOffCasePlan(
        v['plan'],
        body['employee_id'],
        body['details']['month'],
      );
  if (v['employee_id'] != body['employee_id'] ||
      v['kind'] != 'one_off_case' ||
      v['source_snapshot']?['employee']?['revision'] !=
          body['employee_revision'] ||
      ['source_hash', 'preview_hash'].any((k) => !_hash.hasMatch('${v[k]}')) ||
      [
        'can_confirm',
        'can_calculate',
        'can_approve',
        'writes_enabled',
      ].any((k) => v[k] is! bool) ||
      v['can_calculate'] != p['payroll_calculation_complete'])
    _fail(
      'Die Einmalbezugsvorschau gehört nicht zum unveränderten Mitarbeiterauftrag.',
    );
  _bindings(
    businessMap(v['source_snapshot']),
    businessMap(body['details']),
    body['source_file_ids'],
    body['employee_id'],
    p,
  );
  return v;
}

Map<String, dynamic> Function(dynamic) payrollOneOffCaseValidator(
  Map<String, dynamic> body, {
  Map<String, dynamic>? previous,
  Map<String, dynamic>? preview,
}) {
  final b = _copy(body),
      old = previous == null ? null : _copy(previous),
      p = preview == null ? null : _copy(preview);
  return (raw) {
    final v = payrollOneOffCaseRecord(raw, b['employee_id']);
    if (v['revision'] != (old?['revision'] ?? 0) + 1 ||
        old != null && v['id'] != old['id'] ||
        v['previous_hash'] != old?['content_hash'] ||
        v['status'] != b['status'] ||
        v['rule_version'] != b['rule_version'] ||
        v['source_contract_version'] != b['source_contract_version'] ||
        !payrollFactsSame(v['details'], b['details']) ||
        !payrollFactsSame(v['source_file_ids'], b['source_file_ids']) ||
        v['preview_hash'] != b['preview_hash'] ||
        v['correction_reason'] != (b['correction_reason'] ?? ''))
      _fail(
        'Die Einmalbezugsquittung gehört nicht zum ursprünglichen unveränderten Auftrag.',
      );
    final proof = v['status'] == 'void' ? old : p;
    if (proof != null &&
        (!payrollFactsSame(
              v['sources'],
              proof[v['status'] == 'void' ? 'sources' : 'source_snapshot'],
            ) ||
            !payrollFactsSame(v['plan'], proof['plan']) ||
            v['source_hash'] != proof['source_hash']))
      _fail(
        'Die Quittung ersetzt ursprüngliche Einmalbezugsquellen oder ihre geprüfte Zusammensetzung.',
      );
    return v;
  };
}

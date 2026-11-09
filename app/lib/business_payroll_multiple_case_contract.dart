import 'dart:convert';

import 'api.dart';
import 'business_payroll_facts.dart';
import 'business_payroll_calculation_case_contract.dart';
import 'business_payroll_annual_basis_contract.dart';
import 'business_payroll_oneoff_case_contract.dart';
import 'business_session.dart' show businessMap, businessItems;
import 'business_payroll_source5_transition.dart'
    show payrollPositiveTransition;

const payrollMultipleRule = 'de_2026_multiple_oneoff_v7';
Map<String, dynamic> payrollMultipleCaseRunInput(Map<String, dynamic> fact) {
  payrollMultipleCaseRecord(fact, fact['employee_id']);
  if (fact['status'] != 'active' ||
      fact['plan']['payroll_calculation_complete'] != true)
    _fail(
      'Nur ein aktiver vollständig berechenbarer Monatsgruppenfall kann einen Lohnlauf begründen.',
      400,
    );
  return {
    'source_schema_version': 5,
    'employee_id': fact['employee_id'],
    'multiple_one_off_case_ref': payrollFactRef(fact),
  };
}

Map<String, dynamic> payrollMultipleSource(
  dynamic raw,
  Map<String, dynamic> input,
) {
  final v = businessMap(raw),
      s = businessMap(v['source']),
      c = payrollMultipleCalculation(v['calculation']),
      fact = payrollMultipleCaseRecord(
        s['multiple_one_off_case'],
        input['employee_id'],
      );
  if (s['source_schema_version'] is! int ||
      s['source_schema_version'] != 5 ||
      s['employee_id'] != input['employee_id'] ||
      !payrollFactsSame(s['input'], input) ||
      !payrollFactsSame(
        payrollFactRef(fact),
        input['multiple_one_off_case_ref'],
      ) ||
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
      'Die Monatsgruppen-Lohnvorschau gehört nicht zum gewählten ursprünglichen Fall.',
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
  if (v.containsKey('settlement_transition')) {
    payrollPositiveTransition(v);
  } else if (s['input'] is Map &&
      (s['input'] as Map).containsKey('settlement_review')) {
    _fail(
      'Die bestätigte Zahlungs- und Abführungsprüfung benötigt ihren eindeutigen Korrekturübergang.',
    );
  }
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
    _fail('Den konkreten Monatsgruppenfall nachvollziehbar belegen.', 400);
  return value.trim();
}

int _integer(dynamic value, [int min = 0]) {
  if (value is! int || value < min || value > 1000000000000)
    _fail('Der Monatsgruppenfall enthält keinen eindeutigen Centbetrag.');
  return value;
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

void _shape(dynamic raw, List<String> keys) {
  if (raw is! Map || !payrollFactsSame(_keys(raw), [...keys]..sort()))
    _fail('Die Monatsgruppe enthält unbekannte oder fehlende Angaben.');
}

String _identifier(dynamic v) {
  if (v is! String || !_id.hasMatch(v))
    _fail('Die ursprüngliche Ereigniskennung fehlt.');
  return v;
}

int payrollMultipleMoney(dynamic raw) {
  final value = '$raw'.trim().replaceAll(',', '.');
  if (!RegExp(r'^\d{1,10}(?:\.\d{1,2})?$').hasMatch(value))
    _fail('Den belegten EUR-Betrag ohne Rundung ausdrücklich eingeben.', 400);
  final parts = value.split('.');
  return _integer(
    int.parse(parts[0]) * 100 +
        int.parse(parts.length == 1 ? '0' : parts[1].padRight(2, '0')),
    1,
  );
}

List<Map<String, dynamic>> _events(dynamic components) {
  final result = <Map<String, dynamic>>[
    for (final p in businessItems(components))
      for (final e in businessItems(p['planned_receipts']))
        {
          'component_key': p['component_key'],
          'event_key': e['event_key'],
          'receipt_date': e['receipt_date'],
          'gross_minor': e['gross_minor'],
        },
  ];
  result.sort(
    (a, b) => '${a['receipt_date']}${a['event_key']}'.compareTo(
      '${b['receipt_date']}${b['event_key']}',
    ),
  );
  return result;
}

Map<String, dynamic> _details(dynamic raw) {
  final d = businessMap(raw);
  _shape(d, [
    'month',
    'running_calculation_case_ref',
    'components',
    'current_annual_basis_ref',
    'previous_annual_basis_ref',
    'annual_tax_forecasts',
    'completeness',
    'verification_note',
  ]);
  final month = payrollFactMonth(d['month']);
  if (!month.startsWith('2026-'))
    _fail('Die Monatsgruppe gehört zum unterstützten Jahr 2026.');
  for (final key in [
    'running_calculation_case_ref',
    'current_annual_basis_ref',
  ])
    payrollFactRef(d[key]);
  if (d['previous_annual_basis_ref'] != null)
    payrollFactRef(d['previous_annual_basis_ref']);
  if (d['components'] is! List ||
      (d['components'] as List).isEmpty ||
      (d['components'] as List).length > 20)
    _fail('Ein bis zwanzig ursprüngliche Ansprüche belegen.');
  final components = <String>{}, events = <String>{};
  for (final p in businessItems(d['components'])) {
    _shape(p, ['component_key', 'earning_ref', 'planned_receipts']);
    final key = _identifier(p['component_key']);
    payrollFactRef(p['earning_ref']);
    if (key != p['earning_ref']['id'] ||
        !components.add(key) ||
        p['planned_receipts'] is! List ||
        (p['planned_receipts'] as List).isEmpty ||
        (p['planned_receipts'] as List).length > 20)
      _fail('Jede Komponente muss ihren ursprünglichen Anspruch binden.');
    for (final e in businessItems(p['planned_receipts'])) {
      _shape(e, ['event_key', 'receipt_date', 'gross_minor', 'document_refs']);
      if (!events.add(_identifier(e['event_key'])) ||
          !payrollFactDate(e['receipt_date'])!.startsWith(month) ||
          e['document_refs'] is! List ||
          (e['document_refs'] as List).isEmpty ||
          (e['document_refs'] as List).length > 20)
        _fail('Jeder konkrete Zufluss gehört eindeutig zum selben Monat.');
      _integer(e['gross_minor'], 1);
      final refs = businessItems(e['document_refs']);
      for (var i = 0; i < refs.length; i++) {
        payrollFactRef(refs[i]);
        if (refs.take(i).any((r) => payrollFactsSame(r, refs[i])))
          _fail('Ein Ereignisoriginal wurde doppelt gebunden.');
      }
    }
  }
  if (events.length > 100 ||
      d['annual_tax_forecasts'] is! List ||
      (d['annual_tax_forecasts'] as List).length > 100)
    _fail('Die Monatsgruppe ist nicht begrenzt.');
  final forecasts = <String>{};
  for (final f in businessItems(d['annual_tax_forecasts'])) {
    _shape(f, ['event_key', 'annual_tax_forecast_ref']);
    if (!events.contains(f['event_key']) ||
        !forecasts.add(_identifier(f['event_key'])))
      _fail('Die Steuerquelle muss ein konkretes Ereignis binden.');
    payrollFactRef(f['annual_tax_forecast_ref']);
  }
  _shape(d['completeness'], ['month_events_complete', 'evidence_ref']);
  if (d['completeness']['month_events_complete'] != true)
    _fail('Die vollständige Monatsgruppe ausdrücklich bestätigen.', 400);
  payrollFactRef(d['completeness']['evidence_ref']);
  _note(d['verification_note']);
  return d;
}

Map<String, dynamic> payrollMultipleCalculation(dynamic raw) {
  final v = businessMap(raw),
      r = payrollCompositeCalculation(v['running_calculation']),
      d = businessMap(v['multiple_one_off_details']);
  if (v['rule_version'] != payrollMultipleRule ||
      v['source_contract_version'] is! int ||
      v['source_contract_version'] != 1 ||
      !_hash.hasMatch('${v['rules_sha256']}') ||
      v['currency'] != 'EUR' ||
      v['official_system_approval'] != false ||
      v['statutory_report_status'] != 'not_transmitted' ||
      v['accident_insurance_included'] != false ||
      v['month'] != r['month'] ||
      !payrollFactsSame(v['period_details'], r['period_details']) ||
      v['blockers'] is! List ||
      !_hash.hasMatch('${d['source_snapshot_hash']}') ||
      !_hash.hasMatch('${d['sv_month_group_key']}') ||
      d['month'] != v['month'] ||
      d['actual_payment_created'] != false ||
      d['claim_consumption_created'] != false ||
      d['tax_groups'] != null ||
      d['components'] is! List ||
      d['receipt_events'] is! List ||
      (d['components'] as List).isEmpty ||
      (d['receipt_events'] as List).isEmpty)
    _fail(
      'Die Monatsgruppe ist nicht an die ursprüngliche laufende Rechnung gebunden.',
    );
  final components = <String, Map<String, dynamic>>{}, events = <String>{};
  for (final c in businessItems(d['components'])) {
    final key = _identifier(c['component_key']);
    payrollFactRef(c['earning_ref']);
    if (c['earning_ref']['id'] != key ||
        components.containsKey(key) ||
        _integer(c['planned_minor'], 1) +
                _integer(c['remaining_claim_minor']) !=
            _integer(c['claim_minor'], 1))
      _fail('Geplanter und verbleibender Anspruch widersprechen dem Original.');
    components[key] = c;
  }
  final receipts = businessItems(d['receipt_events']);
  for (final e in receipts) {
    if (!events.add(_identifier(e['event_key'])) ||
        !components.containsKey(e['component_key']) ||
        !payrollFactDate(e['receipt_date'])!.startsWith(v['month']))
      _fail('Die Zuflüsse gehören nicht eindeutig zu ihren Ansprüchen.');
    _integer(e['gross_minor'], 1);
  }
  for (final c in components.values) {
    if (receipts
            .where((e) => e['component_key'] == c['component_key'])
            .fold<int>(0, (n, e) => n + _integer(e['gross_minor'])) !=
        c['planned_minor'])
      _fail('Die Bruttobeträge ersetzen ihren ursprünglichen Anspruch.');
  }
  if (receipts.fold<int>(0, (n, e) => n + _integer(e['gross_minor'])) !=
          _integer(d['amount_minor'], 1) ||
      v['gross_minor'] !=
          (r['gross_minor'] == null
              ? null
              : r['gross_minor'] + d['amount_minor']))
    _fail(
      'Laufendes Brutto und Monatsgruppe werden nicht genau einmal gezählt.',
    );
  if (d['social_month_group'] != null) {
    final g = businessMap(d['social_month_group']),
        a = businessMap(g['assignment']);
    if (g['month'] != v['month'] ||
        g['gross_minor'] != d['amount_minor'] ||
        !payrollFactsSame(g['receipt_events'], receipts) ||
        g['component_allocations'] != null ||
        g['actual_payment_created'] != false ||
        !_hash.hasMatch('${g['source_hash']}') ||
        a['tax_year'] != 2026 ||
        ![2025, 2026].contains(a['social_year']) ||
        a['march_clause'] != (a['social_year'] == 2025) ||
        a['march_clause'] == true && int.parse(v['month'].substring(5)) > 3 ||
        !payrollFactsSame(_keys(a['bases_minor']), [
          'care',
          'health',
          'pension',
          'unemployment',
        ]))
      _fail(
        'Die gemeinsame SV-Zuordnung darf keine ungeprüften Einzelnetti behaupten.',
      );
    payrollFactRef(a['annual_basis_ref']);
    payrollFactRef(a['assigned_period_ref']);
    payrollFactDate(a['assigned_period_end']);
    for (final n in businessMap(a['bases_minor']).values)
      if (_integer(n) > d['amount_minor'])
        _fail('Die Beitragsbasis übersteigt den ursprünglichen Anspruch.');
  }
  if (v['payroll_calculation_complete'] != true) {
    if (v['payroll_calculation_complete'] != false ||
        v['scope'] != 'multiple_oneoff_review_required' ||
        v['social_contributions_available'] != false ||
        (v['blockers'] as List).isEmpty ||
        _moneyFields.any((k) => v[k] != null) ||
        d.containsKey('single_original_calculation'))
      _fail(
        'Ein ungeklärter Mehrfachplan darf keine fertigen Netto- oder Steuerwerte erhalten.',
      );
    return v;
  }
  final single = payrollOneOffCalculation(d['single_original_calculation']),
      e = receipts.first,
      c = components.values.first;
  if (v['scope'] != 'regular_standard_multiple_oneoff' ||
      v['social_contributions_available'] != true ||
      (v['blockers'] as List).isNotEmpty ||
      components.length != 1 ||
      receipts.length != 1 ||
      c['remaining_claim_minor'] != 0 ||
      c['claim_minor'] != d['amount_minor'] ||
      e['gross_minor'] != d['amount_minor'] ||
      single['one_off_details']['receipt_date'] != e['receipt_date'] ||
      single['one_off_details']['amount_minor'] != d['amount_minor'] ||
      !payrollFactsSame(
        d['social_month_group']?['assignment'],
        single['one_off_details']['assignment'],
      ))
    _fail(
      'Nur der vollständig geprüfte ursprüngliche Einzelanspruch ist abschließbar.',
    );
  const ignored = {
    'rule_version',
    'rules_sha256',
    'source_contract_version',
    'scope',
    'multiple_one_off_details',
    'one_off_details',
  };
  Map<String, dynamic> reduced(Map<String, dynamic> x) => {
    for (final e in x.entries)
      if (!ignored.contains(e.key)) e.key: e.value,
  };
  if (!payrollFactsSame(reduced(v), reduced(single)))
    _fail('Die neue Quellenfassung verändert die geprüften Geldwerte.');
  return v;
}

Map<String, dynamic> payrollMultipleCasePlan(
  dynamic raw,
  String employee,
  String month,
) {
  final p = payrollMultipleCalculation(raw);
  if (p['month'] != payrollFactMonth(month))
    _fail('Monat und Rechenplan widersprechen sich.');
  return p;
}

void _bindings(
  Map<String, dynamic> s,
  Map<String, dynamic> d,
  dynamic ids,
  String employee,
  Map<String, dynamic> plan,
) {
  _details(d);
  final files = businessItems(s['source_files']);
  if (s['schema_version'] is! int ||
      s['schema_version'] != 1 ||
      s['employee']?['id'] != employee ||
      s['employee']?['revision'] is! int ||
      s['employee']['revision'] < 1 ||
      !payrollFactsSame(s['details'], d) ||
      s['source_files'] is! List ||
      !payrollFactsSame(
        files.map((f) => f['id']).toList()..sort(),
        [...ids]..sort(),
      ) ||
      files.any(
        (f) =>
            f['employee_id'] != employee ||
            !_id.hasMatch('${f['id']}') ||
            !_hash.hasMatch('${f['content_hash']}'),
      ))
    _fail(
      'Mitarbeiterfassung, Angaben und Originale der Monatsgruppe wurden ersetzt.',
    );
  void document(dynamic r) {
    final found = files.where((f) => f['id'] == r['id']);
    if (found.length != 1 ||
        !payrollFactsSame(r, {
          'id': found.single['id'],
          'revision': 1,
          'content_hash': found.single['content_hash'],
        }))
      _fail('Eine konkrete Fassung des Monatsgruppenoriginals fehlt.');
  }

  document(d['completeness']['evidence_ref']);
  for (final p in businessItems(d['components']))
    for (final e in businessItems(p['planned_receipts']))
      for (final r in e['document_refs']) document(r);
  final c = businessMap(s['calculation_source']);
  if (c['schema_version'] is! int ||
      c['schema_version'] != 1 ||
      c['source_contract_version'] is! int ||
      c['source_contract_version'] != 1 ||
      c['rule_version'] != payrollMultipleRule ||
      c['employee_id'] != employee ||
      c['month'] != d['month'] ||
      !payrollFactsSame(c['completeness'], d['completeness']) ||
      c['components'] is! List ||
      c['annual_tax_forecasts'] is! List)
    _fail('Der eingefrorene Monatsgruppen-Quellenstand ist unbekannt.');
  final running = payrollCalculationCaseRecord(
    c['running_calculation_case'],
    employee,
  );
  if (running['details']['month'] != d['month'] ||
      !payrollFactsSame(
        payrollFactRef(running),
        d['running_calculation_case_ref'],
      ))
    _fail('Die unveränderte laufende Monatsfassung wurde ersetzt.');
  Map<String, dynamic> annual(dynamic value, dynamic reference, String kind) {
    final v = payrollAnnualRecord(value, employee, kind: kind);
    if (!payrollFactsSame(payrollFactRef(v), reference))
      _fail('Eine gebundene ursprüngliche Jahresfassung wurde ersetzt.');
    return v;
  }

  final current = annual(
    c['current_annual_basis'],
    d['current_annual_basis_ref'],
    'annual_basis',
  );
  if ((c['previous_annual_basis'] == null) !=
      (d['previous_annual_basis_ref'] == null))
    _fail('Die Vorjahresentscheidung wurde geändert.');
  if (c['previous_annual_basis'] != null)
    annual(
      c['previous_annual_basis'],
      d['previous_annual_basis_ref'],
      'annual_basis',
    );
  if (!payrollFactsSame(
        current['sources']['current_calculation_case'],
        running,
      ) ||
      !payrollFactsSame(
        current['details']['current_calculation_case_ref'],
        d['running_calculation_case_ref'],
      ))
    _fail('Jahresbasis und laufende Rechnung gehören nicht zusammen.');
  final parts = businessItems(c['components']),
      forecasts = businessItems(c['annual_tax_forecasts']);
  if (parts.length != (d['components'] as List).length ||
      forecasts.length != (d['annual_tax_forecasts'] as List).length)
    _fail('Die ursprüngliche Monatsgruppe wurde erweitert oder verkürzt.');
  Map<String, dynamic> unique(
    List<Map<String, dynamic>> list,
    bool Function(Map<String, dynamic>) match,
  ) {
    final found = list.where(match);
    if (found.length != 1)
      _fail('Eine eindeutige gebundene Originalquelle fehlt.');
    return found.single;
  }

  for (final p in businessItems(d['components'])) {
    final bound = unique(
      parts,
      (v) => v['component_key'] == p['component_key'],
    );
    if (!payrollFactsSame(bound['planned_receipts'], p['planned_receipts']))
      _fail('Ein ursprünglicher Bruttozufluss wurde umgewidmet.');
    final earning = annual(
          bound['earning'],
          p['earning_ref'],
          'one_off_earning',
        ),
        part = unique(
          businessItems(plan['multiple_one_off_details']['components']),
          (v) => v['component_key'] == p['component_key'],
        );
    if (!payrollFactsSame(part['earning_ref'], p['earning_ref']) ||
        part['claim_minor'] != earning['details']['amount_minor'])
      _fail('Der ursprüngliche Anspruch wurde geändert.');
  }
  for (final f in businessItems(d['annual_tax_forecasts'])) {
    final bound = unique(forecasts, (t) => t['event_key'] == f['event_key']),
        forecast = annual(
          bound['annual_tax_forecast'],
          f['annual_tax_forecast_ref'],
          'annual_tax_forecast',
        ),
        component = unique(
          parts,
          (p) =>
              businessItems(p['planned_receipts'])
                  .any((e) => e['event_key'] == f['event_key']),
        ),
        event = unique(
          businessItems(component['planned_receipts']),
          (e) => e['event_key'] == f['event_key'],
        );
    if (!payrollFactsSame(forecast['sources']['annual_basis'], current) ||
        !payrollFactsSame(
          forecast['sources']['current_one_off'],
          component['earning'],
        ) ||
        forecast['details']['receipt_date'] != event['receipt_date'])
      _fail(
        'Steuerprognose, Anspruch, Zuflusstag und Jahresbasis wurden vermischt.',
      );
  }
  if (!payrollFactsSame(
        _events(d['components']),
        plan['multiple_one_off_details']['receipt_events'],
      ) ||
      plan['running_calculation']['period_details']['plan_hash'] !=
          running['plan']['plan_hash'] ||
      plan['running_calculation']['period_details']['source_snapshot_hash'] !=
          running['source_hash'])
    _fail(
      'Die Monatsgruppe ersetzt die laufende Originalrechnung oder ihre Bruttoereignisse.',
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
    if (!payrollFactsSame(
      plan['running_calculation']['period_details'][k],
      running['plan'][k],
    ))
      _fail('Ein laufender Originalbestandteil wurde ersetzt.');
  if (plan['payroll_calculation_complete'] == true) {
    if ((d['annual_tax_forecasts'] as List).length != 1 ||
        forecasts.length != 1)
      _fail(
        'Der vollständig berechnete Einzelanspruch benötigt genau seine ursprüngliche Jahressteuergrundlage.',
      );
    final extra =
        plan['multiple_one_off_details']['single_original_calculation']['one_off_details'];
    if (!payrollFactsSame(
          extra['earning_ref'],
          d['components'][0]['earning_ref'],
        ) ||
        !payrollFactsSame(
          extra['current_annual_basis_ref'],
          d['current_annual_basis_ref'],
        ) ||
        !payrollFactsSame(
          extra['previous_annual_basis_ref'],
          d['previous_annual_basis_ref'],
        ) ||
        !payrollFactsSame(
          extra['annual_tax_forecast_ref'],
          d['annual_tax_forecasts'][0]['annual_tax_forecast_ref'],
        ) ||
        extra['annual_pay_before_minor'] !=
            forecasts[0]['annual_tax_forecast']['plan']['annual_pay_before_minor'])
      _fail(
        'Der Einzelanspruch ersetzt seine ursprüngliche Jahressteuergrundlage.',
      );
  }
}

Map<String, dynamic> payrollMultipleCaseRecord(dynamic raw, String id) {
  final v = businessMap(raw), d = businessMap(v['details']);
  payrollFactRef(v);
  if (v['employee_id'] != id ||
      v['kind'] != 'multiple_one_off_case' ||
      v['rule_version'] != payrollMultipleRule ||
      v['source_contract_version'] is! int ||
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
      'Die Monatsgruppenfassung gehört nicht eindeutig zum ursprünglichen Mitarbeiterauftrag.',
    );
  final plan = payrollMultipleCasePlan(v['plan'], id, d['month']);
  _bindings(businessMap(v['sources']), d, v['source_file_ids'], id, plan);
  return v;
}

Map<String, dynamic> payrollMultipleCaseSources(
  dynamic raw,
  String id,
  String month,
) {
  final v = payrollAnnualSources(raw, id);
  payrollFactMonth(month);
  if (v['month'] != month || v['multiple_one_off_cases'] is! List)
    _fail('Die Monatsgruppenquellen gehören nicht zum gewählten Monat.');
  for (final r in businessItems(v['multiple_one_off_cases']))
    payrollMultipleCaseRecord(r, id);
  return v;
}

Map<String, dynamic> payrollMultipleCaseInput(
  String id,
  Map<String, dynamic> sources,
  Map<String, dynamic> values, {
  Map<String, dynamic>? previous,
}) {
  final month = payrollFactMonth(values['month']),
      s = payrollMultipleCaseSources(sources, id, month);
  if (previous != null) {
    payrollMultipleCaseRecord(previous, id);
    if (previous['details']['month'] != month)
      _fail('Der ursprüngliche Monatsgruppenmonat bleibt erhalten.', 400);
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

  Map<String, dynamic> document(dynamic id) {
    final found = businessItems(s['files']).where((f) => f['id'] == id);
    if (found.length != 1 || !fileIds.contains(id))
      _fail(
        'Jedes Ereignisoriginal zusätzlich an die Monatsgruppe binden.',
        400,
      );
    return {
      'id': id,
      'revision': 1,
      'content_hash': found.single['content_hash'],
    };
  }

  final components = <Map<String, dynamic>>[];
  for (final p in businessItems(values['components'])) {
    final receipts = <Map<String, dynamic>>[];
    for (final e in businessItems(p['receipts'])) {
      final docs = [for (final id in e['document_ids'] as List) document(id)];
      docs.sort(
        (a, b) => '${a['content_hash']}${a['id']}'.compareTo(
          '${b['content_hash']}${b['id']}',
        ),
      );
      receipts.add({
        'event_key': _identifier(e['event_key']),
        'receipt_date': payrollFactDate(e['receipt_date']),
        'gross_minor': _integer(e['gross_minor'], 1),
        'document_refs': docs,
      });
    }
    receipts.sort(
      (a, b) => '${a['receipt_date']}${a['event_key']}'.compareTo(
        '${b['receipt_date']}${b['event_key']}',
      ),
    );
    components.add({
      'component_key': p['earning_id'],
      'earning_ref': source(
        p['earning_id'],
        s['annual_facts'],
        'one_off_earning',
      ),
      'planned_receipts': receipts,
    });
  }
  components.sort(
    (a, b) => '${a['component_key']}'.compareTo('${b['component_key']}'),
  );
  final forecasts = [
    for (final f in businessItems(values['annual_tax_forecasts']))
      {
        'event_key': _identifier(f['event_key']),
        'annual_tax_forecast_ref': source(
          f['forecast_id'],
          s['annual_facts'],
          'annual_tax_forecast',
        ),
      },
  ];
  forecasts.sort((a, b) => '${a['event_key']}'.compareTo('${b['event_key']}'));
  final d = _details({
    'month': month,
    'running_calculation_case_ref': source(
      values['running_calculation_case_id'],
      s['calculation_cases'],
      'calculation_case',
    ),
    'components': components,
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
    'annual_tax_forecasts': forecasts,
    'completeness': {
      'month_events_complete': values['month_events_complete'] == true,
      'evidence_ref': document(values['completeness_file_id']),
    },
    'verification_note': _note(values['verification_note']),
  });
  return {
    'employee_id': id,
    'employee_revision': s['employee']['revision'],
    'kind': 'multiple_one_off_case',
    'rule_version': payrollMultipleRule,
    'source_contract_version': 1,
    'details': d,
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

Map<String, dynamic> payrollMultipleCasePreviewInput(
  Map<String, dynamic> body,
) => _copy({
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
Map<String, dynamic> payrollMultipleCasePreview(
  dynamic raw,
  Map<String, dynamic> body,
) {
  final v = businessMap(raw),
      p = payrollMultipleCasePlan(
        v['plan'],
        body['employee_id'],
        body['details']['month'],
      );
  if (v['employee_id'] != body['employee_id'] ||
      v['kind'] != 'multiple_one_off_case' ||
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
      'Die Monatsgruppenvorschau gehört nicht zum unveränderten Mitarbeiterauftrag.',
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

Map<String, dynamic> Function(dynamic) payrollMultipleCaseValidator(
  Map<String, dynamic> body, {
  Map<String, dynamic>? previous,
  Map<String, dynamic>? preview,
}) {
  final b = _copy(body),
      old = previous == null ? null : _copy(previous),
      p = preview == null ? null : _copy(preview);
  return (raw) {
    final v = payrollMultipleCaseRecord(raw, b['employee_id']);
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
        'Die Monatsgruppenquittung gehört nicht zum ursprünglichen unveränderten Auftrag.',
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
        'Die Quittung ersetzt ursprüngliche Monatsgruppenquellen oder ihre geprüfte Zusammensetzung.',
      );
    return v;
  };
}

Map<String, dynamic> payrollMultipleCaseHistory(
  dynamic raw,
  String employee,
  String id,
) {
  final value = businessMap(raw), items = businessItems(value['items']);
  if (items.isEmpty) _fail('Die ursprüngliche Monatsgruppenhistorie fehlt.');
  Map<String, dynamic>? previous;
  for (final item in items) {
    payrollMultipleCaseRecord(item, employee);
    if (item['id'] != id ||
        item['revision'] != (previous?['revision'] ?? 0) + 1 ||
        item['previous_hash'] != previous?['content_hash'])
      _fail('Die ursprüngliche Monatsgruppenfolge wurde ersetzt.');
    previous = item;
  }
  return value;
}

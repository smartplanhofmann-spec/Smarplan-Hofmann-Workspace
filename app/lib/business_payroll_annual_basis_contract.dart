import 'dart:convert';

import 'api.dart';
import 'business_payroll_facts.dart';
import 'business_payroll_calculation_case_contract.dart';
import 'business_session.dart' show businessMap, businessItems;

const payrollAnnualRule = 'de_2025_2026_annual_basis_v1';
const payrollFactorAnnualRule = 'de_2026_factor_planned_annual_basis_v2';
const payrollFactorAnnualContract = {
  'version': 2,
  'rule_version': payrollFactorAnnualRule,
};
const payrollAnnualKinds = {
  'imported_period': 'Belegte externe Lohnperiode',
  'imported_one_off': 'Bereits verarbeiteter externer Einmalbezug',
  'annual_basis': 'Lückenlose Jahresbasis zu einem Stichtag',
  'one_off_earning': 'Belegter geplanter Einmalanspruch',
  'annual_tax_forecast': 'Jahressteuergrundlage aus Originalquellen',
};
const payrollAnnualBranches = {
  'health': 'Krankenversicherung',
  'care': 'Pflegeversicherung',
  'pension': 'Rentenversicherung',
  'unemployment': 'Arbeitslosenversicherung',
};
const payrollAnnualIntervalReasons = {
  'paid_employment': 'Entgeltberechtigte Beschäftigung',
  'continued_section_7_3': 'Fortbestand nach § 7 Abs. 3 SGB IV',
  'contributory_section_23c': 'Beitragspflichtiger Bezug nach § 23c SGB IV',
  'short_time_contributory': 'Beitragspflichtige Kurzarbeit',
};
const payrollAnnualGapReasons = {
  'not_employed': 'Nachweislich nicht beschäftigt',
  'contribution_free_interruption': 'Belegte beitragsfreie Unterbrechung',
};
const payrollAnnualSchemes = {
  'regular_standard': 'Reguläre Beitragsberechnung',
  'regular_transition': 'Belegter Übergangsbereich',
  'commercial_minijob': 'Gewerblicher Minijob',
};
const payrollAnnualHealth = {
  'statutory_mandatory': 'Gesetzlich pflichtversichert',
  'statutory_voluntary': 'Gesetzlich freiwillig versichert',
  'private': 'Privat versichert',
};
final _id = RegExp(r'^[a-f0-9]{32}$'), _hash = RegExp(r'^[a-f0-9]{64}$');
Never _fail(String message, [int status = 0]) =>
    throw ApiException(status, message);
Map<String, dynamic> _copy(dynamic value) =>
    Map<String, dynamic>.from(jsonDecode(jsonEncode(value)) as Map);
String _note(dynamic value, String label) {
  if (value is! String ||
      value.trim().isEmpty ||
      value.trim().length > 3000 ||
      RegExp(r'[\x00-\x1f\x7f]').hasMatch(value))
    _fail('$label ausdrücklich und vollständig belegen.', 400);
  return value.trim();
}

void _shape(dynamic value, Iterable<String> fields) {
  if (value is! Map ||
      !payrollFactsSame(value.keys.toList()..sort(), fields.toList()..sort()))
    _fail(
      'Die strukturierten Jahresangaben enthalten unbekannte oder fehlende Felder.',
      400,
    );
}

const _fields = {
  'imported_period': 'period_start period_end employment_from employment_to section_key profile branches running_gross_minor running_taxable_minor running_receipts original_rule_version original_rule_hash original_payroll_reference document_refs',
  'imported_one_off': 'receipt_date amount_minor assigned_period_ref section_key bases_minor original_reference document_refs',
  'annual_basis': 'year coverage_to as_of_date payroll_run_refs payroll_payment_refs imported_period_refs imported_one_off_refs current_calculation_case_ref gaps completeness_confirmed',
  'one_off_earning': 'claim_key claim_reference planned_receipt_date amount_minor tax_classification social_classification section_key employment_terms_refs claim_periods document_refs',
  'annual_tax_forecast': 'annual_basis_ref receipt_date remaining_periods previous_employers no_previous_employer_ref identity_ref current_one_off_ref other_tax_receipt_refs',
};
int payrollAnnualMoney(dynamic value) {
  final text = '${value ?? ''}'.trim().replaceAll(',', '.');
  if (!RegExp(r'^\d{1,9}(?:\.\d{1,2})?$').hasMatch(text))
    _fail(
      'Den belegten EUR-Betrag ausdrücklich angeben, auch bekannte 0,00.',
      400,
    );
  final parts = text.split('.');
  return int.parse(parts.first) * 100 +
      int.parse((parts.length == 1 ? '' : parts[1]).padRight(2, '0'));
}

String payrollAnnualRate(dynamic value) {
  final text = '${value ?? ''}'.trim().replaceAll(',', '.');
  if (!RegExp(r'^\d{1,2}(?:\.\d{1,3})?$').hasMatch(text))
    _fail(
      'Den tatsächlichen historischen Beitragssatz mit höchstens drei Nachkommastellen angeben.',
      400,
    );
  final parts = text.split('.');
  return '${parts.first}.${(parts.length == 1 ? '' : parts[1]).padRight(3, '0')}';
}

Map<String, dynamic> payrollAnnualPlan(
  dynamic raw,
  String employeeId,
  String kind,
) {
  final v = businessMap(raw);
  if (v['schema_version'] is! int ||
      v['schema_version'] != 1 ||
      ![
        payrollAnnualRule,
        payrollFactorAnnualRule,
      ].contains(v['rule_version']) ||
      v['rule_version'] == payrollFactorAnnualRule &&
          !['annual_basis', 'annual_tax_forecast'].contains(kind) ||
      v['employee_id'] != employeeId ||
      v['kind'] != kind ||
      !payrollAnnualKinds.containsKey(kind) ||
      [
        'source_hash',
        'plan_hash',
        'employer_key',
      ].any((k) => !_hash.hasMatch('${v[k]}')) ||
      v['can_confirm'] != true)
    _fail(
      'Die Jahresquellenprüfung ist nicht an den bekannten ursprünglichen Regel- und Quellenstand gebunden.',
    );
  if (kind == 'imported_period' &&
      (v['source_documents_verified_by_user'] != true ||
          v['original_tax_not_recalculated'] != true))
    _fail(
      'Ein externer Vortrag darf nicht als neu berechnete ursprüngliche Steuer erscheinen.',
    );
  if (['one_off_earning', 'annual_tax_forecast'].contains(kind) &&
      v['actual_payment_created'] != false)
    _fail('Geplante Jahresquellen sind kein tatsächlicher Zahlungsnachweis.');
  if (kind == 'annual_tax_forecast' && v['current_one_off_excluded'] != true)
    _fail(
      'Die Jahressteuergrundlage darf den aktuellen Einmalbezug nicht doppelt enthalten.',
    );
  return v;
}

void _bindings(
  Map<String, dynamic> s,
  Map<String, dynamic> d,
  List<dynamic> ids,
  String employeeId,
  String kind,
  Map<String, dynamic> plan,
) {
  final factor = plan['rule_version'] == payrollFactorAnnualRule;
  if (factor
      ? !payrollFactsSame(
          s['annual_source_contract'],
          payrollFactorAnnualContract,
        )
      : s.containsKey('annual_source_contract'))
    _fail('Der ausdrückliche Jahresquellenvertrag wurde ersetzt.');
  if (factor) {
    if (kind == 'annual_tax_forecast') {
      payrollAnnualRecord(s['annual_basis'], employeeId, kind: 'annual_basis');
      if (s['annual_basis']['plan']['rule_version'] != payrollFactorAnnualRule)
        _fail('Die Faktorprognose benötigt die eigene V2-Jahresbasis.');
    }
    final c = payrollCalculationCaseRecord(
      kind == 'annual_basis'
          ? s['current_calculation_case']
          : s['annual_basis']['sources']['current_calculation_case'],
      employeeId,
    );
    if (c['rule_version'] != 'de_2026_factor_claims_month_v12' ||
        c['source_contract_version'] != 4 ||
        !payrollFactsSame(plan['factor_case_ref'], payrollFactRef(c)) ||
        !payrollFactsSame(
          plan['factor_profile_ref'],
          payrollFactRef(c['sources']['profiles'][0]),
        ) ||
        kind == 'annual_tax_forecast' &&
            !payrollFactsSame(
              plan['factor_profile_ref'],
              payrollFactRef(s['tax_identity']['sources']['profile']),
            ))
      _fail(
        'Die V2-Jahresquelle hat ihren ursprünglichen Faktorfall oder ihr Faktorprofil verloren.',
      );
  }
  if (s['schema_version'] is! int ||
      s['schema_version'] != 1 ||
      s['employee']?['id'] != employeeId ||
      s['kind'] != kind ||
      !payrollFactsSame(s['details'], d) ||
      !payrollFactsSame(
        payrollFactRef(s['identity']),
        d['employer_identity_ref'],
      ) ||
      s['identity']?['employee_id'] != employeeId)
    _fail(
      'Arbeitgeberidentität oder Jahresquellendetails wurden gegenüber dem Auftrag ersetzt.',
    );
  final files = businessItems(s['source_files']);
  if (s['source_files'] is! List ||
      files.any((v) => v['employee_id'] != employeeId) ||
      !payrollFactsSame(files.map((v) => v['id']).toList()..sort(), ids))
    _fail(
      'Die Jahresquellenoriginale gehören nicht zum gewählten Mitarbeiterauftrag.',
    );
  Map<String, dynamic> fileRef(dynamic id) {
    final f = files.where((v) => v['id'] == id).firstOrNull;
    if (f == null) _fail('Ein konkretes Jahresquellenoriginal fehlt.');
    return {'id': f['id'], 'revision': 1, 'content_hash': f['content_hash']};
  }

  void documents(dynamic value) {
    if (value is Map) {
      for (final entry in value.entries) {
        if ([
              'evidence_ref',
              'claim_key',
              'no_previous_employer_ref',
            ].contains(entry.key) &&
            entry.value != null) {
          if (!payrollFactsSame(entry.value, fileRef(entry.value['id'])))
            _fail('Eine konkrete Originalreferenz wurde ersetzt.');
        } else if (entry.key == 'document_refs') {
          for (final item in entry.value as List)
            if (!payrollFactsSame(item, fileRef(item['id'])))
              _fail('Eine Originalfassung wurde ersetzt.');
        } else {
          documents(entry.value);
        }
      }
    } else if (value is List) {
      for (final item in value) documents(item);
    }
  }

  documents(d);
  void one(String source, String detail) {
    final value = s[source];
    if (value == null ||
        value['employee_id'] != employeeId ||
        !payrollFactsSame(payrollFactRef(value), d[detail]))
      _fail('Eine konkrete Jahresquellenfassung wurde ersetzt.');
  }

  void many(String source, String detail) {
    final list = businessItems(s[source]);
    if (s[source] is! List ||
        list.any((v) => v['employee_id'] != employeeId) ||
        !payrollFactsSame(list.map(payrollFactRef).toList(), d[detail]))
      _fail(
        'Die gebundenen Jahresquellenfassungen stimmen nicht mit dem Auftrag überein.',
      );
  }

  if (kind == 'imported_one_off') one('assigned_period', 'assigned_period_ref');
  if (kind == 'one_off_earning')
    many('employment_terms', 'employment_terms_refs');
  if (kind == 'annual_basis') {
    for (final pair in [
      ['imported_periods', 'imported_period_refs'],
      ['imported_one_offs', 'imported_one_off_refs'],
      ['payroll_runs', 'payroll_run_refs'],
      ['payroll_payments', 'payroll_payment_refs'],
    ])
      many(pair[0], pair[1]);
    if ((d['current_calculation_case_ref'] == null) !=
        (s['current_calculation_case'] == null))
      _fail('Die ausgewählte laufende Monatsquelle fehlt.');
    if (d['current_calculation_case_ref'] != null)
      one('current_calculation_case', 'current_calculation_case_ref');
  }
  if (kind == 'annual_tax_forecast') {
    one('annual_basis', 'annual_basis_ref');
    one('current_one_off', 'current_one_off_ref');
    one('tax_identity', 'identity_ref');
    many('other_tax_receipts', 'other_tax_receipt_refs');
    final future = businessItems(s['future_sources']),
        periods = businessItems(d['remaining_periods']);
    if (s['future_sources'] is! List || future.length != periods.length)
      _fail('Die zukünftigen Vertragsmonate sind nicht vollständig gebunden.');
    for (var i = 0; i < future.length; i++) {
      final f = future[i], p = periods[i];
      if (f['terms']?['employee_id'] != employeeId ||
          !payrollFactsSame(
            payrollFactRef(f['terms']),
            p['employment_terms_ref'],
          ) ||
          businessItems(f['agreements'])
              .any((v) => v['employee_id'] != employeeId) ||
          !payrollFactsSame(
            businessItems(f['agreements']).map(payrollFactRef).toList(),
            p['agreement_refs'],
          ) ||
          !payrollFactsSame(
            f['work_schedule'] == null
                ? null
                : payrollFactRef(f['work_schedule']),
            p['work_schedule_ref'],
          ))
        _fail(
          'Eine zukünftige Beschäftigungs-/Vertrags- oder Arbeitsplanquelle wurde ersetzt.',
        );
    }
  }
}

Map<String, dynamic> payrollAnnualRecord(
  dynamic raw,
  String employeeId, {
  String? kind,
}) {
  final v = businessMap(raw),
      d = businessMap(v['details']),
      s = businessMap(v['sources']);
  payrollFactRef(v);
  if (v['employee_id'] != employeeId ||
      !payrollAnnualKinds.containsKey(v['kind']) ||
      kind != null && v['kind'] != kind ||
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
      'Die Jahresquellenfassung besitzt keinen eindeutigen Mitarbeiter- und Vorgängerbezug.',
    );
  final from = payrollFactDate(v['effective_from'])!,
      to = payrollFactDate(v['effective_to'])!;
  if (from.compareTo(to) > 0)
    _fail('Der Jahresquellenzeitraum ist widersprüchlich.');
  final p = payrollAnnualPlan(v['plan'], employeeId, v['kind']);
  if (p['source_hash'] != v['source_hash'])
    _fail('Der Jahresplan passt nicht zu seinen eingefrorenen Quellen.');
  _bindings(s, d, v['source_file_ids'], employeeId, v['kind'], p);
  return v;
}

Map<String, dynamic> payrollAnnualSources(dynamic raw, String employeeId) {
  final v = payrollFactSources(raw, employeeId);
  if ([
    'annual_facts',
    'payroll_runs',
    'payroll_payments',
    'calculation_cases',
  ].any((k) => v[k] is! List))
    _fail('Die vollständigen privaten Jahresquellen fehlen.');
  for (final fact in businessItems(v['annual_facts']))
    payrollAnnualRecord(fact, employeeId);
  for (final fact in businessItems(v['calculation_cases']))
    payrollCalculationCaseRecord(fact, employeeId);
  for (final key in ['payroll_runs', 'payroll_payments'])
    for (final r in businessItems(v[key])) {
      payrollFactRef(r);
      if (r['employee_id'] != employeeId ||
          r['kind'] != (key == 'payroll_runs' ? 'run' : 'payment'))
        _fail(
          'Eine tatsächliche Lohn-/Zahlungsquelle gehört zu einer anderen Person.',
        );
    }
  return v;
}

Map<String, dynamic> payrollAnnualInput(
  String employeeId,
  Map<String, dynamic> sources,
  String kind,
  Map<String, dynamic> values, {
  Map<String, dynamic>? previous,
}) {
  payrollAnnualSources(sources, employeeId);
  if (!payrollAnnualKinds.containsKey(kind))
    _fail('Unbekannte Jahresquellenart.', 400);
  if (previous != null) payrollAnnualRecord(previous, employeeId, kind: kind);
  final ids = values['source_file_ids'];
  if (ids is! List ||
      ids.isEmpty ||
      ids.length > 20 ||
      ids.toSet().length != ids.length ||
      ids.any(
        (id) => !businessItems(sources['files']).any((v) => v['id'] == id),
      ))
    _fail('Ein bis zwanzig geschützte Jahresquellenoriginale auswählen.', 400);
  final details = _copy(values['details']);
  details['verification_note'] = _note(
    values['verification_note'],
    'Jahresquellen-Prüfvermerk',
  );
  _shape(details, [
    'employer_identity_ref',
    'verification_note',
    ..._fields[kind]!.split(' '),
  ]);
  Map<String, dynamic> document(dynamic id) {
    if (id is! String || !_id.hasMatch(id) || !ids.contains(id))
      _fail(
        'Jedes konkrete Original zusätzlich an die Jahresquelle binden.',
        400,
      );
    final f = businessItems(sources['files']).firstWhere((v) => v['id'] == id);
    return {'id': id, 'revision': 1, 'content_hash': f['content_hash']};
  }

  Map<String, dynamic> source(dynamic id, String page, {List<String>? kinds}) {
    final result = businessItems(sources[page])
        .where(
          (v) =>
              v['id'] == id &&
              v['status'] != 'void' &&
              (kinds == null || kinds.contains(v['kind'])),
        )
        .firstOrNull;
    if (result == null || result['employee_id'] != employeeId)
      _fail(
        'Die gewählte Jahresquelle ist nicht aktuell oder gehört zu einer anderen Person.',
        400,
      );
    return payrollFactRef(result);
  }

  Map<String, dynamic> reference(dynamic id, String key) {
    if ([
      'evidence_ref',
      'claim_key',
      'no_previous_employer_ref',
      'document_refs',
    ].contains(key))
      return document(id);
    if (['employer_identity_ref', 'identity_ref'].contains(key))
      return source(id, 'identities', kinds: ['identity']);
    if (key == 'assigned_period_ref' || key == 'imported_period_refs')
      return source(id, 'annual_facts', kinds: ['imported_period']);
    if (key == 'imported_one_off_refs')
      return source(id, 'annual_facts', kinds: ['imported_one_off']);
    if (key == 'annual_basis_ref')
      return source(id, 'annual_facts', kinds: ['annual_basis']);
    if (key == 'current_one_off_ref')
      return source(id, 'annual_facts', kinds: ['one_off_earning']);
    if (key == 'other_tax_receipt_refs')
      return source(
        id,
        'annual_facts',
        kinds: ['imported_period', 'imported_one_off'],
      );
    if (key == 'payroll_run_refs')
      return source(id, 'payroll_runs', kinds: ['run']);
    if (key == 'payroll_payment_refs')
      return source(id, 'payroll_payments', kinds: ['payment']);
    if (key == 'current_calculation_case_ref')
      return source(id, 'calculation_cases', kinds: ['calculation_case']);
    if (['employment_terms_ref', 'employment_terms_refs'].contains(key))
      return source(id, 'facts', kinds: ['employment_terms']);
    if (key == 'work_schedule_ref')
      return source(id, 'facts', kinds: ['work_schedule']);
    if (key == 'agreement_refs') return source(id, 'agreements');
    _fail('Unbekannte konkrete Jahresquellenreferenz.', 400);
  }

  dynamic normalized(dynamic raw, [String? key]) {
    if (key == 'claim_key' || key?.endsWith('_ref') == true)
      return raw == null ? null : reference(raw, key!);
    if (key == 'document_refs' || key?.endsWith('_refs') == true) {
      if (raw is! List || raw.toSet().length != raw.length)
        _fail(
          'Jede Quellenfassung eindeutig und höchstens einmal auswählen.',
          400,
        );
      return (List<String>.from(
        raw,
      )..sort()).map((id) => reference(id, key!)).toList();
    }
    if (raw is Map)
      return {
        for (final e in raw.entries)
          '${e.key}': normalized(e.value, '${e.key}'),
      };
    if (raw is List) {
      final list = raw.map((v) => normalized(v)).toList();
      if (['eligible_intervals', 'claim_periods', 'gaps'].contains(key))
        list.sort((a, b) => (a['start'] as String).compareTo(b['start']));
      if (key == 'running_receipts')
        list.sort(
          (a, b) => '${a['received_on']}${a['evidence_ref']['id']}'.compareTo(
            '${b['received_on']}${b['evidence_ref']['id']}',
          ),
        );
      if (key == 'remaining_periods')
        list.sort((a, b) => (a['month'] as String).compareTo(b['month']));
      if (key == 'previous_employers')
        list.sort(
          (a, b) => '${a['start']}${a['employer_tax_number']}'.compareTo(
            '${b['start']}${b['employer_tax_number']}',
          ),
        );
      return list;
    }
    if (key?.endsWith('_minor') == true && (raw is! int || raw < 0))
      _fail(
        'Jeden belegten Geldbetrag ausdrücklich in ganzen Cent angeben.',
        400,
      );
    if ([
      'period_start',
      'period_end',
      'employment_from',
      'start',
      'end',
      'received_on',
      'receipt_date',
      'planned_receipt_date',
      'coverage_to',
      'as_of_date',
    ].contains(key))
      return payrollFactDate(raw);
    if (key == 'employment_to') return payrollFactDate(raw, optional: true);
    return raw;
  }

  final d = businessMap(normalized(details));
  if (kind == 'imported_period') {
    final p = businessMap(d['profile']);
    _shape(
      p,
      'scheme health_insurance health_additional_percent saxony childless_surcharge care_child_discounts minijob_rv_exempt pension_other_compulsory u1_percent u2_percent'
          .split(' '),
    );
    if (!payrollAnnualSchemes.containsKey(p['scheme']) ||
        !payrollAnnualHealth.containsKey(p['health_insurance']) ||
        [
          'saxony',
          'childless_surcharge',
          'minijob_rv_exempt',
          'pension_other_compulsory',
        ].any((k) => p[k] is! bool) ||
        p['care_child_discounts'] is! int ||
        p['care_child_discounts'] < 0 ||
        p['care_child_discounts'] > 4 ||
        !_hash.hasMatch('${d['original_rule_hash']}'))
      _fail(
        'Historischen Versicherungszweig, Originalverfahren und persönliche Beitragsmerkmale ausdrücklich belegen.',
        400,
      );
    for (final k in ['health_additional_percent', 'u1_percent', 'u2_percent'])
      p[k] = payrollAnnualRate(p[k]);
    d['profile'] = p;
    _shape(d['branches'], payrollAnnualBranches.keys);
    for (final b in businessMap(d['branches']).values) {
      _shape(b, ['eligible_intervals', 'total_minor', 'employee_minor']);
      if (b['eligible_intervals'] is! List)
        _fail('Die tatsächlichen Beitragsintervalle fehlen.', 400);
      for (final row in businessItems(b['eligible_intervals'])) {
        _shape(row, ['start', 'end', 'legal_reason', 'evidence_ref']);
        if (!payrollAnnualIntervalReasons.containsKey(row['legal_reason']))
          _fail(
            'Den tatsächlichen Rechtsgrund des Beitragsintervalls wählen.',
            400,
          );
      }
    }
    for (final row in businessItems(d['running_receipts']))
      _shape(row, ['received_on', 'taxable_minor', 'evidence_ref']);
  }
  if (kind == 'imported_one_off')
    _shape(d['bases_minor'], payrollAnnualBranches.keys);
  if (kind == 'annual_basis') {
    if (d['completeness_confirmed'] != true ||
        d['year'] is! int ||
        ![2025, 2026].contains(d['year']))
      _fail(
        'Vollständiges tatsächliches Bezugsjahr ausdrücklich bestätigen.',
        400,
      );
    for (final row in businessItems(d['gaps'])) {
      _shape(row, ['start', 'end', 'reason', 'evidence_ref']);
      if (!payrollAnnualGapReasons.containsKey(row['reason']))
        _fail('Jede Jahreslücke mit ihrem tatsächlichen Grund belegen.', 400);
    }
  }
  if (kind == 'one_off_earning') {
    if (d['tax_classification'] != 'other_payment' ||
        d['social_classification'] != 'one_off_remuneration')
      _fail(
        'Sonstigen Bezug und einmaliges Arbeitsentgelt ausdrücklich klassifizieren.',
        400,
      );
    for (final row in businessItems(d['claim_periods']))
      _shape(row, ['start', 'end', 'evidence_ref']);
  }
  if (kind == 'annual_tax_forecast') {
    for (final row in businessItems(d['remaining_periods']))
      _shape(row, [
        'month',
        'employment_terms_ref',
        'agreement_refs',
        'work_schedule_ref',
      ]);
    for (final row in businessItems(d['previous_employers']))
      _shape(row, [
        'employer_name',
        'employer_tax_number',
        'start',
        'end',
        'running_taxable_minor',
        'other_paid_minor',
        'evidence_ref',
      ]);
  }
  return {
    'employee_id': employeeId,
    'employee_revision': sources['employee']['revision'],
    'kind': kind,
    'details': d,
    'source_file_ids': List<String>.from(ids)..sort(),
    'revision': previous?['revision'] ?? 0,
    'status': 'active',
    'confirmed': true,
    if (previous != null) ...{
      'id': previous['id'],
      'correction_reason': _note(values['correction_reason'], 'Korrekturgrund'),
    },
  };
}

Map<String, dynamic> payrollAnnualPreviewInput(Map<String, dynamic> body) =>
    _copy({
      for (final key in [
        'employee_id',
        'employee_revision',
        'kind',
        'details',
        'source_file_ids',
      ])
        key: body[key],
    });
Map<String, dynamic> payrollAnnualPreview(
  dynamic raw,
  Map<String, dynamic> body,
) {
  final v = businessMap(raw),
      s = businessMap(v['source_snapshot']),
      p = payrollAnnualPlan(v['plan'], body['employee_id'], body['kind']);
  if (v['employee_id'] != body['employee_id'] ||
      v['kind'] != body['kind'] ||
      s['employee']?['revision'] != body['employee_revision'] ||
      p['source_hash'] != v['source_hash'] ||
      ['source_hash', 'preview_hash'].any((k) => !_hash.hasMatch('${v[k]}')) ||
      [
        'can_confirm',
        'can_write',
        'can_approve',
        'writes_enabled',
      ].any((k) => v[k] is! bool) ||
      v['can_confirm'] != p['can_confirm'])
    _fail(
      'Die Jahresquellenvorschau gehört nicht zum unveränderten Mitarbeiterauftrag.',
    );
  _bindings(
    s,
    businessMap(body['details']),
    body['source_file_ids'],
    body['employee_id'],
    body['kind'],
    p,
  );
  return v;
}

Map<String, dynamic> Function(dynamic) payrollAnnualValidator(
  Map<String, dynamic> body, {
  Map<String, dynamic>? previous,
  Map<String, dynamic>? preview,
}) {
  final b = _copy(body),
      old = previous == null ? null : _copy(previous),
      p = preview == null ? null : _copy(preview);
  return (raw) {
    final v = payrollAnnualRecord(raw, b['employee_id'], kind: b['kind']);
    if (v['revision'] != (old?['revision'] ?? 0) + 1 ||
        old != null && v['id'] != old['id'] ||
        v['previous_hash'] != old?['content_hash'] ||
        v['status'] != b['status'] ||
        !payrollFactsSame(v['details'], b['details']) ||
        !payrollFactsSame(v['source_file_ids'], b['source_file_ids']) ||
        v['preview_hash'] != b['preview_hash'] ||
        v['correction_reason'] != (b['correction_reason'] ?? ''))
      _fail(
        'Die Jahresquellenquittung gehört nicht zum ursprünglichen unveränderten Auftrag.',
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
        'Die Jahresquellenquittung ersetzt ursprüngliche Quellen oder geprüfte Berechnungsgrundlagen.',
      );
    return v;
  };
}

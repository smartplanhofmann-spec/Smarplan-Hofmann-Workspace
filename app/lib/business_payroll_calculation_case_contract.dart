import 'dart:convert';

import 'api.dart';
import 'business_payroll_facts.dart';
import 'business_payroll_entitlement_contract.dart';
import 'business_session.dart' show businessMap, businessItems;

const payrollCalculationCaseRule = 'de_2026_segments_entitlements_v5';
const payrollFactorTaxfreeTravelRule =
    'de_2026_factor_taxfree_travel_month_v10';
const payrollFactorTaxfreeTravelScope =
    'regular_standard_factor_taxfree_travel_month';
bool payrollCalculationCaseRuleKnown(dynamic rule, dynamic contract) =>
    contract is int &&
    (rule == payrollCalculationCaseRule && contract == 1 ||
        rule == payrollFactorTaxfreeTravelRule && contract == 2);
bool payrollFactorTravelBaseEligible(dynamic raw) {
  final value = businessMap(raw), plan = businessMap(value['plan']);
  final tax = plan['tax_periods'], social = plan['social_periods'];
  return value['kind'] == 'period_case' &&
      value['status'] == 'active' &&
      plan['rule_version'] == payrollFactorPeriodRule &&
      plan['can_calculate'] == true &&
      tax is List &&
      tax.length == 1 &&
      tax.single is Map &&
      tax.single['lzz'] == 2 &&
      tax.single['tax_days'] == 30 &&
      social is List &&
      social.length == 1 &&
      social.single is Map &&
      social.single['full_month'] == true &&
      social.single['days'] == 30;
}

const payrollCalculationEventKinds = {
  'tax_features_change': 'Steuermerkmale geändert',
  'wage_forecast_change': 'Regelmäßige Entgeltprognose geändert',
  'health_fund_change': 'Krankenkasse oder Kassenbeitrag geändert',
  'social_rate_change': 'Beitragsmerkmale geändert',
  'employment_status_change': 'Beschäftigungs-/Versicherungsstatus geändert',
  'data_correction': 'Berichtigung ohne fachliche Merkmalsänderung',
};
const payrollCalculationMembershipKinds = {
  'elstam': 'ELStAM-Nachweis',
  'substitute_tax_certificate': 'Amtliche Ersatzbescheinigung',
  'official_employee_declaration': 'Amtliche Arbeitnehmererklärung',
  'unknown_membership_general_rate':
      'Zugehörigkeit ungeklärt, allgemeiner Satz ausdrücklich gewählt',
};
final _id = RegExp(r'^[a-f0-9]{32}$'), _hash = RegExp(r'^[a-f0-9]{64}$');
Never _fail(String message, [int status = 0]) =>
    throw ApiException(status, message);
Map<String, dynamic> _copy(dynamic v) =>
    Map<String, dynamic>.from(jsonDecode(jsonEncode(v)) as Map);
String _note(dynamic v, String label) {
  if (v is! String ||
      v.trim().isEmpty ||
      v.trim().length > 3000 ||
      RegExp(r'[\x00-\x1f\x7f]').hasMatch(v))
    _fail('$label vollständig belegen.', 400);
  return v.trim();
}

int _integer(dynamic v, [int min = 0, int max = 1000000000000]) {
  if (v is! int || v < min || v > max)
    _fail('Beträge oder Zeiträume des Gesamtfalls sind ungültig.');
  return v;
}

void _factorTravelMetadata(
  Map<String, dynamic> value, {
  bool required = false,
}) {
  if (value['travel_payment_refs'] is! List ||
      value['travel_payment_refs'].isEmpty && required)
    _fail('Die ursprünglichen Reisezahlungsbelege fehlen.');
  final ids = <String>{};
  for (final ref in businessItems(value['travel_payment_refs'])) {
    payrollFactRef(ref);
    if (!ids.add(ref['id']))
      _fail('Ein Reisezahlungsbeleg wurde doppelt gebunden.');
  }
  _integer(value['travel_paid_minor']);
  final factor = businessMap(value['factor_parameters']);
  if (factor.isEmpty && !required) return;
  if (factor['tax_factor'] is! String ||
      !RegExp(r'^0\.[0-9]{3}$').hasMatch(factor['tax_factor']))
    _fail('Der tatsächlich eingetragene Faktor fehlt.');
  payrollFactRef(factor['profile_ref']);
}

void _factorTravelBounds(
  Map<String, dynamic> value,
  String month,
  bool complete,
) {
  if ([
    'entitlement_sources',
    'unpaid_dates',
    'social_continuation',
  ].any((key) => value[key] is! List || value[key].isNotEmpty))
    _fail(
      'Der Faktor-Reisefall enthält keine zusätzlichen Ansprüche oder Unterbrechungen.',
    );
  if (!complete) return;
  final dates = payrollFactDates(month);
  for (final key in ['employment_intervals', 'tax_periods', 'social_periods']) {
    final rows = businessItems(value[key]);
    if (rows.length != 1 ||
        rows.single['start'] != dates.first ||
        rows.single['end'] != dates.last)
      _fail('Der Faktor-Reisefall benötigt genau einen vollständigen Monat.');
  }
  final tax = businessItems(value['tax_periods']).single;
  final social = businessItems(value['social_periods']).single;
  if (tax['lzz'] != 2 ||
      tax['tax_days'] != 30 ||
      social['days'] != 30 ||
      social['full_month'] != true ||
      businessItems(value['earnings']).any((v) => v['kind'] != 'ordinary_work'))
    _fail('Der Faktor-Reisefall ist kein ausschließlich regulärer Vollmonat.');
}

Map<String, dynamic> payrollCalculationCasePlan(
  dynamic raw,
  String employeeId,
  String month,
) {
  final v = businessMap(raw);
  payrollFactMonth(month);
  if (v['schema_version'] != 1 ||
      !payrollCalculationCaseRuleKnown(
        v['rule_version'],
        v['source_contract_version'],
      ) ||
      v['employee_id'] != employeeId ||
      v['month'] != month ||
      [
        'rules_sha256',
        'source_snapshot_hash',
        'claims_component_hash',
        'plan_hash',
      ].any((k) => !_hash.hasMatch('${v[k]}')) ||
      [
        'employment_intervals',
        'identity_intervals',
        'earnings',
        'tax_periods',
        'social_periods',
        'entitlement_sources',
        'unpaid_dates',
        'social_continuation',
        'travel_source_hashes',
        'blockers',
      ].any((k) => v[k] is! List) ||
      v['can_confirm'] is! bool ||
      v['can_calculate'] is! bool ||
      v['can_calculate'] != (v['blockers'] as List).isEmpty)
    _fail(
      'Der Gesamtplan ist nicht an einen bekannten vollständigen Quellen- und Regelstand gebunden.',
    );
  if (v['gross_minor'] != null) _integer(v['gross_minor']);
  if (v['rule_version'] == payrollFactorTaxfreeTravelRule) {
    _factorTravelMetadata(v, required: v['can_calculate'] == true);
    _factorTravelBounds(v, month, v['can_calculate'] == true);
  }
  return v;
}

Map<String, dynamic> payrollCalculationCaseRecord(
  dynamic raw,
  String employeeId,
) {
  final v = businessMap(raw),
      d = businessMap(v['details']),
      s = businessMap(v['sources']);
  payrollFactRef(v);
  if (v['employee_id'] != employeeId ||
      v['kind'] != 'calculation_case' ||
      !payrollCalculationCaseRuleKnown(
        v['rule_version'],
        v['source_contract_version'],
      ) ||
      !['active', 'void'].contains(v['status']) ||
      !_hash.hasMatch('${v['source_hash']}') ||
      !_hash.hasMatch('${v['preview_hash']}') ||
      (v['revision'] == 1
          ? v['previous_hash'] != null
          : !_hash.hasMatch('${v['previous_hash']}')) ||
      v['source_file_ids'] is! List ||
      (v['source_file_ids'] as List).isEmpty ||
      (v['source_file_ids'] as List).any((i) => !_id.hasMatch('$i')))
    _fail(
      'Die Gesamtfallfassung gehört nicht eindeutig zum Mitarbeiter und Originalauftrag.',
    );
  payrollFactMonth(d['month']);
  final p = payrollCalculationCasePlan(v['plan'], employeeId, d['month']);
  if (s['schema_version'] != 1 ||
      !payrollCalculationCaseRuleKnown(
        s['rule_version'],
        s['source_contract_version'],
      ) ||
      s['source_contract_version'] != v['source_contract_version'] ||
      s['rule_version'] != v['rule_version'] ||
      s['employee_id'] != employeeId ||
      s['month'] != d['month'] ||
      p['rule_version'] != v['rule_version'] ||
      p['source_contract_version'] != v['source_contract_version'] ||
      p['source_snapshot_hash'] != v['source_hash'])
    _fail('Gesamtfall und eingefrorener Quellenstand widersprechen sich.');
  _bindings(s, d, v['source_file_ids'], employeeId, p);
  if (v['rule_version'] == payrollFactorTaxfreeTravelRule &&
      p['factor_parameters'] != null &&
      !payrollFactsSame(
        p['factor_parameters']['profile_ref'],
        (d['profile_refs'] as List).single,
      ))
    _fail('Der Faktor gehört nicht zum ausdrücklich gewählten Profil.');
  return v;
}

void _bindings(
  Map<String, dynamic> s,
  Map<String, dynamic> d,
  dynamic files,
  String employeeId,
  Map<String, dynamic> plan,
) {
  payrollFactRecord(s['period_case'], employeeId, kind: 'period_case');
  if (!payrollFactsSame(
        payrollFactRef(s['period_case']),
        d['period_case_ref'],
      ) ||
      !payrollFactsSame(s['segment_events'], d['segment_events']) ||
      s['thirty_day_rule'] != d['thirty_day_rule'])
    _fail('Der Basisfall oder die fachlichen Ereignisse wurden ersetzt.');
  for (final pair in [
    ['employment_terms', 'employment_terms_refs'],
    ['profiles', 'profile_refs'],
    ['identities', 'identity_refs'],
    ['entitlements', 'entitlement_case_refs'],
  ]) {
    final items = businessItems(s[pair[0]]);
    if (s[pair[0]] is! List ||
        items.any((v) => v['employee_id'] != employeeId) ||
        !payrollFactsSame(items.map(payrollFactRef).toList(), d[pair[1]]))
      _fail('Eine gebundene Gesamtfallquelle wurde ersetzt.');
  }
  final travel = businessItems(s['travel_sources']);
  if (s['travel_sources'] is! List ||
      travel.any(
        (v) => v['employee_id'] != employeeId || v['month'] != d['month'],
      ) ||
      !payrollFactsSame(
        travel.map((v) => v['settlement_ref']).toList(),
        d['travel_settlement_refs'],
      ))
    _fail('Die Reiseabrechnungsquellen passen nicht zur Person und zum Monat.');
  if (s['rule_version'] == payrollFactorTaxfreeTravelRule) {
    if (s['period_case']['plan']['rule_version'] != payrollFactorPeriodRule ||
        [
          'employment_terms_refs',
          'profile_refs',
          'identity_refs',
        ].any((key) => d[key] is! List || d[key].length != 1) ||
        [
          'segment_events',
          'entitlement_case_refs',
        ].any((key) => d[key] is! List || d[key].isNotEmpty) ||
        d['thirty_day_rule'] != null ||
        d['flat_tax_decision'] != null ||
        d['travel_payment_refs'] is! List ||
        d['travel_payment_refs'].isEmpty ||
        travel.isEmpty)
      _fail(
        'Der Faktor-Reisefall enthält nicht ausschließlich die begrenzten Monatsquellen.',
      );
    final actual = <Map<String, dynamic>>[];
    var paidTotal = 0;
    for (final source in travel) {
      final proof = businessMap(source['payment_proof']);
      if (source['kind'] != 'travel_allowances' ||
          source['schema_version'] != 1 ||
          source['letter_m'] != false ||
          [
            'flat_taxable_payroll_minor',
            'individual_taxable_payroll_minor',
            'benefit_in_kind_non_cash_minor',
          ].any((key) => source[key] != 0) ||
          proof['schema_version'] != 1 ||
          proof['payments'] is! List)
        _fail(
          'Die Reisequelle ist nicht als steuerfreie externe Erstattung belegt.',
        );
      final cutoff = _integer(proof['cutoff_sequence']);
      _integer(proof['paid_minor']);
      final sequences = <int>{};
      var paid = 0, maximum = 0;
      String? lastId;
      for (final payment in businessItems(proof['payments'])) {
        final ref = payrollFactRef(payment);
        final sequence = _integer(payment['sequence'], 1);
        final amount = _integer(payment['amount_minor']);
        payrollFactDate(payment['paid_on']);
        if (!['active', 'void'].contains(payment['status']) ||
            !['reimbursement', 'repayment'].contains(payment['kind']) ||
            !_hash.hasMatch('${payment['cash_source_hash']}') ||
            !sequences.add(sequence) ||
            sequence > cutoff ||
            lastId != null && '${payment['id']}'.compareTo(lastId) <= 0)
          _fail('Der eingefrorene Reisezahlungsbeleg ist unvollständig.');
        lastId = payment['id'];
        if (sequence > maximum) maximum = sequence;
        if (payment['status'] == 'active')
          paid += payment['kind'] == 'repayment' ? -amount : amount;
        actual.add(ref);
      }
      if (maximum != cutoff ||
          paid != proof['paid_minor'] ||
          paid != source['tax_free_external_minor'])
        _fail(
          'Der Zahlungsstand bestätigt die ausgewählte steuerfreie Reise nicht vollständig.',
        );
      paidTotal += paid;
    }
    final expected = businessItems(d['travel_payment_refs']);
    for (final ref in expected) payrollFactRef(ref);
    List<Map<String, dynamic>> ordered(List<Map<String, dynamic>> refs) =>
        [...refs]..sort((a, b) => '${a['id']}'.compareTo('${b['id']}'));
    if (actual.map((v) => v['id']).toSet().length != actual.length ||
        !payrollFactsSame(ordered(actual), ordered(expected)) ||
        !payrollFactsSame(
          plan['travel_payment_refs'],
          d['travel_payment_refs'],
        ) ||
        paidTotal != plan['travel_paid_minor'] ||
        paidTotal != plan['travel']?['tax_free_external_minor'])
      _fail(
        'Die ursprünglichen Reisezahlungsbelege wurden ersetzt oder ausgelassen.',
      );
    if (plan['can_calculate'] == true &&
        plan['factor_parameters']?['tax_factor'] !=
            s['profiles'][0]['profile']?['tax_factor'])
      _fail('Der Planfaktor wurde gegenüber dem ausgewählten Profil geändert.');
  }
  final originals = businessItems(s['source_files']);
  if (originals.any((v) => v['employee_id'] != employeeId) ||
      !payrollFactsSame(originals.map((v) => v['id']).toList()..sort(), files))
    _fail('Die geschützten Gesamtfalloriginale wurden ersetzt.');
  final decision = d['flat_tax_decision'], tax = s['flat_travel_tax'];
  if ((decision == null) != (tax == null))
    _fail('Die ausgewählte Pauschalsteuerentscheidung fehlt.');
  if (decision != null) {
    final evidence = tax['parameters']['evidence'];
    if (!payrollFactsSame(
          payrollFactRef(tax['policy']),
          decision['policy_ref'],
        ) ||
        !payrollFactsSame(
          evidence['church_membership_evidence'],
          decision['church_membership_evidence'] == null
              ? null
              : {
                  'kind': decision['church_membership_evidence']['kind'],
                  'reference':
                      decision['church_membership_evidence']['reference'],
                },
        ) ||
        tax['parameters']['church_tax'] !=
            decision['church_membership_evidence']?['church_tax'] ||
        !payrollFactsSame(
          evidence['employee_deduction_authorization'],
          decision['employee_deduction_file_ref'],
        ) ||
        evidence['tax_certificate_issued_on'] !=
            decision['tax_certificate_issued_on'] ||
        decision['record_on_finalize'] != true ||
        tax['recording_context']['actual_recorded'] != false)
      _fail(
        'Die Pauschalsteuerquelle oder ihr ausdrücklicher Erfassungsauftrag wurde ersetzt.',
      );
    for (final ref in [
      decision['employee_deduction_file_ref'],
      decision['tax_certificate_file_ref'],
    ].where((v) => v != null)) {
      if (!businessItems(tax['source_files']).any(
        (v) => payrollFactsSame({
          'id': v['id'],
          'revision': 1,
          'content_hash': v['content_hash'],
        }, ref),
      ))
        _fail('Ein konkreter Steuerbeleg wurde ersetzt.');
    }
  }
}

Map<String, dynamic> payrollCalculationCaseSources(
  dynamic raw,
  String employeeId,
  String month,
) {
  final v = payrollFactSources(raw, employeeId);
  payrollFactMonth(month);
  if (v['month'] != month ||
      [
        'calculation_cases',
        'travel_tax_policies',
        'entitlements',
        'travel_settlements',
      ].any((k) => v[k] is! List))
    _fail('Die privaten Gesamtfallquellen gehören nicht zum gewählten Monat.');
  for (final item in businessItems(v['calculation_cases']))
    payrollCalculationCaseRecord(item, employeeId);
  for (final item in businessItems(v['entitlements']))
    payrollEntitlementRecord(item, employeeId);
  for (final item in businessItems(v['travel_settlements'])) {
    payrollFactRef(item);
    if (item['employee_id'] != employeeId || item['kind'] != 'settlement')
      _fail('Eine Reiseabrechnung gehört nicht zum ausgewählten Mitarbeiter.');
  }
  for (final item in businessItems(v['travel_tax_policies'])) {
    payrollFactRef(item);
    if (item['employee_id'] != null || item['kind'] != 'travel_tax_policy')
      _fail('Eine betriebliche Steuerentscheidung ist nicht eindeutig.');
  }
  if (v.containsKey('factor_period_facts')) {
    final ids = <String>{};
    for (final item in businessItems(v['factor_period_facts'])) {
      payrollFactRecord(item, employeeId, kind: 'period_case');
      if (item['plan']['rule_version'] != payrollFactorPeriodRule ||
          !ids.add(item['id']))
        _fail(
          'Der Faktor-Basisfall gehört nicht zum freigegebenen Quellenstand.',
        );
    }
  }
  if (v.containsKey('travel_payment_proofs')) {
    final ids = <String>{};
    for (final item in businessItems(v['travel_payment_proofs'])) {
      payrollFactRef(item);
      payrollFactRef(item['settlement_ref']);
      payrollFactDate(item['paid_on']);
      _integer(item['amount_minor']);
      const keys = {
        'id',
        'revision',
        'content_hash',
        'settlement_ref',
        'status',
        'kind',
        'paid_on',
        'amount_minor',
      };
      if (!ids.add(item['id']) ||
          item.keys.toSet().difference(keys).isNotEmpty ||
          keys.difference(item.keys.toSet()).isNotEmpty ||
          !['active', 'void'].contains(item['status']) ||
          !['reimbursement', 'repayment'].contains(item['kind']))
        _fail(
          'Die begrenzten Reisezahlungsquellen sind nicht eindeutig oder vollständig.',
        );
    }
  }
  return v;
}

Map<String, dynamic> payrollCalculationCaseInput(
  String employeeId,
  Map<String, dynamic> sources,
  Map<String, dynamic> values, {
  Map<String, dynamic>? previous,
}) {
  final month = payrollFactMonth(values['month']);
  payrollCalculationCaseSources(sources, employeeId, month);
  if (previous != null) {
    payrollCalculationCaseRecord(previous, employeeId);
    if (previous['details']['month'] != month)
      _fail('Der ursprüngliche Gesamtfallmonat bleibt erhalten.', 400);
  }
  final rule =
      values['rule_version'] ??
      previous?['rule_version'] ??
      payrollCalculationCaseRule;
  if (![
        payrollCalculationCaseRule,
        payrollFactorTaxfreeTravelRule,
      ].contains(rule) ||
      previous != null && previous['rule_version'] != rule)
    _fail('Die bestätigte Regelwahl bleibt bei der Korrektur erhalten.', 400);
  List<Map<String, dynamic>> refs(
    dynamic raw,
    dynamic ids, {
    String? kind,
    bool optional = false,
    bool includeVoid = false,
  }) {
    if (ids is! List ||
        !optional && ids.isEmpty ||
        ids.toSet().length != ids.length)
      _fail('Die einschlägigen Quellen vollständig auswählen.', 400);
    return (List<String>.from(ids)..sort()).map((id) {
      final item = businessItems(raw)
          .where(
            (v) =>
                v['id'] == id &&
                (includeVoid || v['status'] != 'void') &&
                (kind == null || v['kind'] == kind),
          )
          .firstOrNull;
      if (item == null)
        _fail('Eine ausgewählte Quelle ist nicht mehr aktuell.', 400);
      return payrollFactRef(item);
    }).toList();
  }

  final files = values['source_file_ids'];
  if (files is! List ||
      files.isEmpty ||
      files.length > 20 ||
      files.toSet().length != files.length ||
      files.any(
        (id) => !businessItems(sources['files']).any((v) => v['id'] == id),
      ))
    _fail('Ein bis zwanzig geschützte Personaloriginale auswählen.', 400);
  Map<String, dynamic>? file(dynamic id) {
    if (id == null || id == '') return null;
    final value = businessItems(sources['files'])
        .where((v) => v['id'] == id)
        .firstOrNull;
    if (value == null || !files.contains(id))
      _fail('Jedes konkrete Original zusätzlich am Gesamtfall binden.', 400);
    return {'id': id, 'revision': 1, 'content_hash': value['content_hash']};
  }

  if (rule == payrollFactorTaxfreeTravelRule) {
    if (sources['factor_period_facts'] is! List ||
        sources['travel_payment_proofs'] is! List)
      _fail('Die freigegebenen Faktor- und Reisezahlungsquellen fehlen.', 400);
    final periods = refs(sources['factor_period_facts'], [
      values['period_case_id'],
    ], kind: 'period_case');
    if (!payrollFactorTravelBaseEligible(
      businessItems(sources['factor_period_facts'])
          .singleWhere((v) => v['id'] == periods.single['id']),
    ))
      _fail(
        'Der ausgewählte Faktor-Basisfall ist kein vollständig berechenbarer voller Monat.',
        400,
      );
    final terms = refs(
      sources['facts'],
      values['employment_terms_ids'],
      kind: 'employment_terms',
    );
    final profiles = refs(sources['profiles'], values['profile_ids']);
    final identities = refs(sources['identities'], values['identity_ids']);
    if (periods.length != 1 ||
        terms.length != 1 ||
        profiles.length != 1 ||
        identities.length != 1 ||
        businessItems(values['segment_events'] ?? []).isNotEmpty ||
        (values['entitlement_case_ids'] as List? ?? []).isNotEmpty ||
        values['thirty_day_rule'] != null && values['thirty_day_rule'] != '' ||
        values['policy_id'] != null && values['policy_id'] != '')
      _fail(
        'Der Faktor-Reisefall benötigt genau eine unveränderte volle Monatsquelle ohne weitere Ansprüche.',
        400,
      );
    final settlements = refs(
      sources['travel_settlements'],
      values['travel_settlement_ids'],
    );
    final payments = refs(
      sources['travel_payment_proofs'],
      values['travel_payment_ids'],
      includeVoid: true,
    );
    for (final payment in payments) {
      final proof = businessItems(sources['travel_payment_proofs'])
          .singleWhere((v) => v['id'] == payment['id']);
      if (!settlements.any((v) => payrollFactsSame(v, proof['settlement_ref'])))
        _fail(
          'Jeder Zahlungsnachweis muss genau eine ausgewählte Reiseabrechnung belegen.',
          400,
        );
    }
    final requiredPayments =
        businessItems(sources['travel_payment_proofs'])
            .where(
              (proof) => settlements.any(
                (ref) => payrollFactsSame(ref, proof['settlement_ref']),
              ),
            )
            .map(payrollFactRef)
            .toList()
          ..sort((a, b) => '${a['id']}'.compareTo('${b['id']}'));
    if (!payrollFactsSame(payments, requiredPayments))
      _fail(
        'Sämtliche ursprünglichen Zahlungsfassungen der gewählten Reisen auswählen.',
        400,
      );
    return {
      'employee_id': employeeId,
      'employee_revision': sources['employee']['revision'],
      'kind': 'calculation_case',
      'rule_version': payrollFactorTaxfreeTravelRule,
      'source_contract_version': 2,
      'details': {
        'month': month,
        'period_case_ref': periods.single,
        'employment_terms_refs': terms,
        'profile_refs': profiles,
        'identity_refs': identities,
        'segment_events': <Map<String, dynamic>>[],
        'thirty_day_rule': null,
        'entitlement_case_refs': <Map<String, dynamic>>[],
        'travel_settlement_refs': settlements,
        'travel_payment_refs': payments,
        'flat_tax_decision': null,
        'verification_note': _note(
          values['verification_note'],
          'Gesamtfallprüfung',
        ),
      },
      'source_file_ids': List<String>.from(files)..sort(),
      'revision': previous?['revision'] ?? 0,
      'status': 'active',
      'confirmed': true,
      if (previous != null) ...{
        'id': previous['id'],
        'correction_reason': _note(
          values['correction_reason'],
          'Korrekturgrund',
        ),
      },
    };
  }

  final events = <Map<String, dynamic>>[];
  if (values['segment_events'] is! List ||
      (values['segment_events'] as List).length > 31)
    _fail('Begrenzte tatsächliche Profilereignisse erfassen.', 400);
  for (final item in businessItems(values['segment_events'])) {
    final date = payrollFactDate(item['effective_from'])!;
    if (!date.startsWith(month) ||
        !payrollCalculationEventKinds.containsKey(item['kind']))
      _fail(
        'Ereignis und tatsächlichen Tag innerhalb des Monats belegen.',
        400,
      );
    final ids = item['source_file_ids'];
    if (ids is! List || ids.isEmpty || ids.toSet().length != ids.length)
      _fail('Die konkreten Ereignisoriginale auswählen.', 400);
    for (final id in ids) file(id);
    events.add({
      'kind': item['kind'],
      'effective_from': date,
      'before_profile_ref': refs(sources['profiles'], [
        item['before_profile_id'],
      ]).single,
      'after_profile_ref': refs(sources['profiles'], [
        item['after_profile_id'],
      ]).single,
      'source_file_ids': List<String>.from(ids)..sort(),
      'reason': _note(item['reason'], 'Ereignisgrund'),
    });
  }
  events.sort(
    (a, b) => (a['effective_from'] as String).compareTo(b['effective_from']),
  );
  final required =
      businessItems(sources['entitlements'])
          .where(
            (v) =>
                v['status'] == 'active' &&
                (v['effective_from'] as String).compareTo(
                      payrollFactDates(month).last,
                    ) <=
                    0 &&
                (v['effective_to'] as String).compareTo('$month-01') >= 0,
          )
          .map((v) => v['id'])
          .toList()
        ..sort();
  final selected = List<String>.from(values['entitlement_case_ids'] ?? [])
    ..sort();
  if (!payrollFactsSame(required, selected))
    _fail(
      'Sämtliche aktiven Anspruchsnachweise dieses Monats müssen enthalten bleiben.',
      400,
    );
  if (![
    null,
    '',
    'actual_days_capped_per_claim',
  ].contains(values['thirty_day_rule']))
    _fail('Die konkrete 30-Tage-Regel belegen.', 400);
  Map<String, dynamic>? decision;
  final policyId = values['policy_id'];
  if (policyId != null && policyId != '') {
    final policy = businessItems(sources['travel_tax_policies'])
        .where((v) => v['id'] == policyId && v['status'] == 'active')
        .firstOrNull;
    if (policy == null || values['record_on_finalize'] != true)
      _fail(
        'Aktuelle betriebliche Steuerentscheidung und tatsächliche Erfassung mit Abschluss bestätigen.',
        400,
      );
    Map<String, dynamic>? membership;
    if (policy['details']['church_method'] == 'evidence') {
      final kind = values['membership_kind'];
      if (!payrollCalculationMembershipKinds.containsKey(kind))
        _fail(
          'Tatsächliche Kirchensteuer-Nachweisart ausdrücklich wählen.',
          400,
        );
      final church = values['membership_church_tax'];
      if (kind != 'unknown_membership_general_rate' && church is! bool)
        _fail('Kirchensteuerzugehörigkeit ausdrücklich belegen.', 400);
      final reference = ['elstam', 'substitute_tax_certificate'].contains(kind)
          ? refs(sources['identities'], [
              values['membership_identity_id'],
            ]).single
          : file(values['membership_file_id']);
      if (reference == null)
        _fail('Konkreten Zugehörigkeitsnachweis auswählen.', 400);
      membership = {
        'kind': kind,
        'reference': reference,
        'church_tax': kind == 'unknown_membership_general_rate' ? null : church,
      };
    }
    final deduction = file(values['employee_deduction_file_id']);
    if (policy['details']['employer_bears_tax'] == false && deduction == null)
      _fail(
        'Die Übernahme der Steuerkosten benötigt ein ausdrückliches Arbeitnehmeroriginal.',
        400,
      );
    final certificate = file(values['tax_certificate_file_id']),
        issued = payrollFactDate(
          values['tax_certificate_issued_on'],
          optional: true,
        );
    if ((certificate == null) != (issued == null))
      _fail(
        'Bescheinigungsoriginal und tatsächliches Ausstellungsdatum gemeinsam angeben.',
        400,
      );
    decision = {
      'policy_ref': payrollFactRef(policy),
      'church_membership_evidence': membership,
      'employee_deduction_file_ref': deduction,
      'tax_certificate_file_ref': certificate,
      'tax_certificate_issued_on': issued,
      'record_on_finalize': true,
    };
  }
  return {
    'employee_id': employeeId,
    'employee_revision': sources['employee']['revision'],
    'kind': 'calculation_case',
    'rule_version': payrollCalculationCaseRule,
    'source_contract_version': 1,
    'details': {
      'month': month,
      'period_case_ref': refs(sources['facts'], [
        values['period_case_id'],
      ], kind: 'period_case').single,
      'employment_terms_refs': refs(
        sources['facts'],
        values['employment_terms_ids'],
        kind: 'employment_terms',
      ),
      'profile_refs': refs(sources['profiles'], values['profile_ids']),
      'identity_refs': refs(sources['identities'], values['identity_ids']),
      'segment_events': events,
      'thirty_day_rule': values['thirty_day_rule'] == ''
          ? null
          : values['thirty_day_rule'],
      'entitlement_case_refs': refs(
        sources['entitlements'],
        selected,
        optional: true,
      ),
      'travel_settlement_refs': refs(
        sources['travel_settlements'],
        values['travel_settlement_ids'],
        optional: true,
      ),
      'flat_tax_decision': decision,
      'verification_note': _note(
        values['verification_note'],
        'Gesamtfallprüfung',
      ),
    },
    'source_file_ids': List<String>.from(files)..sort(),
    'revision': previous?['revision'] ?? 0,
    'status': 'active',
    'confirmed': true,
    if (previous != null) ...{
      'id': previous['id'],
      'correction_reason': _note(values['correction_reason'], 'Korrekturgrund'),
    },
  };
}

Map<String, dynamic> payrollCalculationCasePreviewInput(
  Map<String, dynamic> body,
) => _copy({
  for (final key in [
    'employee_id',
    'employee_revision',
    'kind',
    'rule_version',
    'source_contract_version',
    'details',
    'source_file_ids',
  ])
    key: body[key],
});
Map<String, dynamic> payrollCalculationCasePreview(
  dynamic raw,
  Map<String, dynamic> body,
) {
  final v = businessMap(raw),
      s = businessMap(v['source_snapshot']),
      d = businessMap(body['details']);
  final p = payrollCalculationCasePlan(
    v['plan'],
    body['employee_id'],
    d['month'],
  );
  if (v['employee_id'] != body['employee_id'] ||
      v['kind'] != 'calculation_case' ||
      s['employee_id'] != body['employee_id'] ||
      s['month'] != d['month'] ||
      !payrollCalculationCaseRuleKnown(
        s['rule_version'],
        s['source_contract_version'],
      ) ||
      s['rule_version'] != body['rule_version'] ||
      s['source_contract_version'] != body['source_contract_version'] ||
      p['rule_version'] != body['rule_version'] ||
      p['source_contract_version'] != body['source_contract_version'] ||
      p['source_snapshot_hash'] != v['source_hash'] ||
      !_hash.hasMatch('${v['source_hash']}') ||
      !_hash.hasMatch('${v['preview_hash']}') ||
      [
        'can_confirm',
        'can_calculate',
        'can_write',
        'can_approve',
        'writes_enabled',
      ].any((k) => v[k] is! bool) ||
      v['can_confirm'] != p['can_confirm'] ||
      v['can_calculate'] != p['can_calculate'])
    _fail(
      'Die Gesamtfallvorschau gehört nicht zum ausdrücklich geprüften Quellenauftrag.',
    );
  _bindings(s, d, body['source_file_ids'], body['employee_id'], p);
  if (body['rule_version'] == payrollFactorTaxfreeTravelRule &&
      p['factor_parameters'] != null &&
      !payrollFactsSame(
        p['factor_parameters']['profile_ref'],
        (d['profile_refs'] as List).single,
      ))
    _fail('Der Faktor gehört nicht zum ausdrücklich gewählten Profil.');
  return v;
}

Map<String, dynamic> Function(dynamic) payrollCalculationCaseValidator(
  Map<String, dynamic> body, {
  Map<String, dynamic>? previous,
  Map<String, dynamic>? preview,
}) {
  final b = _copy(body),
      old = previous == null ? null : _copy(previous),
      p = preview == null ? null : _copy(preview);
  return (raw) {
    final v = payrollCalculationCaseRecord(raw, b['employee_id']);
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
        'Die Gesamtfallquittung entspricht nicht dem unveränderten ursprünglichen Auftrag.',
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
        'Die Quittung hat den geprüften Gesamtplan oder seine Originalquellen ersetzt.',
      );
    return v;
  };
}

Map<String, dynamic> payrollCalculationCaseRunInput(
  Map<String, dynamic> record,
) {
  payrollCalculationCaseRecord(record, record['employee_id']);
  if (record['status'] != 'active' || record['plan']['can_calculate'] != true)
    _fail(
      'Nur ein aktiver vollständig berechenbarer Gesamtfall kann einen Lohnlauf begründen.',
      400,
    );
  return {
    'source_schema_version': 3,
    'employee_id': record['employee_id'],
    'calculation_case_ref': payrollFactRef(record),
  };
}

Map<String, dynamic> payrollCompositeCalculation(dynamic raw) {
  final v = businessMap(raw), d = businessMap(v['period_details']);
  if (!payrollCalculationCaseRuleKnown(
        v['rule_version'],
        v['source_contract_version'],
      ) ||
      v['currency'] != 'EUR' ||
      !_hash.hasMatch('${v['rules_sha256']}') ||
      v['official_system_approval'] != false ||
      v['statutory_report_status'] != 'not_transmitted' ||
      v['accident_insurance_included'] != false ||
      v['blockers'] is! List ||
      !_hash.hasMatch('${d['plan_hash']}') ||
      !_hash.hasMatch('${d['source_snapshot_hash']}') ||
      [
        'employment_intervals',
        'identity_intervals',
        'earnings',
        'tax_periods',
        'social_periods',
        'entitlement_sources',
        'unpaid_dates',
        'social_continuation',
        'travel_source_hashes',
      ].any((k) => d[k] is! List))
    _fail(
      'Der Gesamtlohn besitzt keine bekannte vollständige Quellen- und Regelbindung.',
    );
  payrollFactMonth(v['month']);
  final travel = businessMap(d['travel']);
  if (v['rule_version'] == payrollCalculationCaseRule &&
      v['scope'] == payrollFactorTaxfreeTravelScope)
    _fail('Der neue Faktor-Reisefall benötigt seinen eigenen Regelstand.');
  if (v['rule_version'] == payrollFactorTaxfreeTravelRule) {
    _factorTravelMetadata(d, required: v['scope'] != 'unsupported');
    _factorTravelBounds(d, v['month'], v['scope'] != 'unsupported');
    if (v['scope'] != 'unsupported' &&
        (v['scope'] != payrollFactorTaxfreeTravelScope ||
            d['factor_parameters']?['tax_factor'] !=
                v['tax_parameters']?['tax_factor'] ||
            d['travel_paid_minor'] != travel['tax_free_external_minor'] ||
            travel['letter_m'] != false ||
            [
              'flat_taxable_payroll_minor',
              'individual_taxable_payroll_minor',
              'benefit_in_kind_non_cash_minor',
            ].any((key) => travel[key] != 0) ||
            d['flat_travel_tax'] != null))
      _fail('Die steuerfreie Reise darf das Faktor-Lohnnetto nicht verändern.');
  }
  for (final key in [
    'tax_free_external_minor',
    'flat_taxable_payroll_minor',
    'individual_taxable_payroll_minor',
    'benefit_in_kind_non_cash_minor',
  ])
    _integer(travel[key]);
  if (travel['letter_m'] is! bool ||
      v['travel_expenses_included_in_net'] !=
          (travel['flat_taxable_payroll_minor'] +
                  travel['individual_taxable_payroll_minor'] >
              0))
    _fail('Die Reisewerte sind nicht eindeutig dem Lohn zugeordnet.');
  for (final group in ['employment_intervals', 'tax_periods', 'social_periods'])
    for (final p in businessItems(d[group])) {
      final start = payrollFactDate(p['start'])!,
          end = payrollFactDate(p['end'])!;
      if (start.compareTo(end) > 0 ||
          !start.startsWith(v['month']) ||
          !end.startsWith(v['month']))
        _fail('Ein Gesamtlohnzeitraum gehört nicht zum Monat.');
      _integer(
        p[group == 'employment_intervals'
            ? 'calendar_days'
            : group == 'tax_periods'
            ? 'tax_days'
            : 'days'],
        1,
        31,
      );
      if (group == 'tax_periods' && ![2, 4].contains(p['lzz']))
        _fail('Der Steuer-Lohnzahlungszeitraum ist nicht eindeutig.');
      if (group == 'social_periods') {
        if (p['full_month'] is! bool || p['days'] > 30)
          _fail('Die getrennte SV-Periode ist nicht eindeutig.');
        for (final key in [
          'health_minor',
          'care_minor',
          'pension_minor',
          'unemployment_minor',
        ])
          _integer(p['caps']?[key]);
      }
    }
  if (v['gross_minor'] != null) _integer(v['gross_minor']);
  if (v['scope'] == 'unsupported') {
    if (v['social_contributions_available'] != false ||
        v['payroll_calculation_complete'] != false ||
        [
          'net_minor',
          'net_deductions_minor',
          'payout_minor',
          'employee_tax_minor',
          'employee_social_total_minor',
          'employer_social_total_minor',
        ].any((k) => v[k] != null))
      _fail(
        'Ein gesperrter Gesamtfall darf keine vermeintlichen Netto- oder Beitragswerte erzeugen.',
      );
    return v;
  }
  if (![
        'regular_standard_segments',
        'regular_transition_segments',
        'commercial_minijob_segments_flat_tax',
        payrollFactorTaxfreeTravelScope,
      ].contains(v['scope']) ||
      v['social_contributions_available'] != true ||
      v['payroll_calculation_complete'] != true ||
      (v['blockers'] as List).isNotEmpty)
    _fail('Unbekannter abschließbarer Gesamtlohnumfang.');
  int sum(dynamic raw) {
    final map = businessMap(raw);
    if (raw is! Map || map.isEmpty) _fail('Die Beitragsaufstellung fehlt.');
    return map.values.fold<int>(0, (a, b) => a + _integer(b));
  }

  final ordinary = businessItems(d['earnings'])
      .fold<int>(0, (a, b) => a + _integer(b['gross_minor']));
  if (ordinary +
          travel['flat_taxable_payroll_minor'] +
          travel['individual_taxable_payroll_minor'] +
          travel['benefit_in_kind_non_cash_minor'] !=
      v['gross_minor'])
    _fail(
      'Entgeltpositionen und einmalig gebundene Reiselohnwerte widersprechen dem Brutto.',
    );
  final flat = d['flat_travel_tax'];
  var shifted = 0;
  if (flat != null) {
    if (flat['rule_version'] != 'de_2026_travel_flat_tax_v1' ||
        flat['schema_version'] != 1 ||
        flat['can_calculate'] != true ||
        flat['amount_minor'] != travel['flat_taxable_payroll_minor'] ||
        flat['actual_payment_created'] != false ||
        flat['statutory_transmitted'] != false ||
        [
          'rules_hash',
          'source_hash',
          'calculation_hash',
        ].any((k) => !_hash.hasMatch('${flat[k]}')))
      _fail('Die Reise-Pauschalsteuer ist nicht eindeutig belegt.');
    shifted = _integer(flat['employee_tax_minor']);
    final due =
        _integer(flat['wage_tax_minor']) +
        _integer(flat['solidarity_minor']) +
        _integer(flat['church_tax_minor']);
    if (due != flat['statutory_employer_due_minor'] ||
        _integer(flat['employer_total_minor']) + shifted != due ||
        flat['employee_cash_after_flat_tax_minor'] !=
            flat['amount_minor'] - shifted)
      _fail('Die Kostenaufteilung der Reise-Pauschalsteuer stimmt nicht.');
  } else if (travel['flat_taxable_payroll_minor'] != 0)
    _fail('Für den Pauschalbetrag fehlt die geprüfte Steuerentscheidung.');
  if (sum(v['employee_contributions']) != v['employee_social_total_minor'] ||
      sum(v['employer_contributions']) != v['employer_social_total_minor'] ||
      v['gross_minor'] +
              v['employer_social_total_minor'] +
              sum(v['employer_levies']) +
              _integer(v['employer_flat_tax_minor']) -
              shifted !=
          v['employer_total_excluding_accident_insurance_minor'])
    _fail('Gesamtlohnbeiträge und Arbeitgeberkosten stimmen nicht.');
  if (_integer(v['individual_wage_tax_minor']) +
              _integer(v['solidarity_minor']) +
              _integer(v['church_tax_minor']) !=
          v['employee_tax_minor'] ||
      v['net_minor'] !=
          v['gross_minor'] -
              v['employee_social_total_minor'] -
              v['employee_tax_minor'] ||
      v['net_deductions_minor'] !=
          travel['benefit_in_kind_non_cash_minor'] + shifted)
    _fail(
      'Netto und belegte Sachbezugs-/Steuerkostenabzüge widersprechen sich.',
    );
  final cash = (v['net_minor'] as int) - _integer(v['net_deductions_minor']);
  if (v['payout_minor'] != (cash < 0 ? 0 : cash) ||
      v['employee_additional_payment_minor'] != (cash < 0 ? -cash : 0))
    _fail(
      'Auszahlung und zusätzliche Arbeitnehmerzahlung berücksichtigen die Nettoabzüge nicht.',
    );
  if (d['social_assessments'] is! List || d['tax_calculations'] is! List)
    _fail('Die einzelnen Steuer-/Beitragsrechnungen fehlen.');
  final assessments = businessItems(d['social_assessments']);
  if (!payrollFactsSame(
    assessments.map((a) => a['period']).toList(),
    d['social_periods'],
  ))
    _fail(
      'Die Beitragsrechnungen sind nicht an die exakten SV-Perioden gebunden.',
    );
  for (final key in [
    'employee_contributions',
    'employer_contributions',
    'employer_levies',
  ])
    for (final name in businessMap(v[key]).keys) {
      if (assessments.fold<int>(0, (a, b) => a + _integer(b[key]?[name])) !=
          v[key][name])
        _fail(
          'Die periodischen Beitragsrechnungen summieren sich nicht zum Gesamtlohn.',
        );
    }
  final taxes = businessItems(d['tax_calculations']);
  if (v['scope'] == 'commercial_minijob_segments_flat_tax') {
    if (taxes.isNotEmpty || v['employee_tax_minor'] != 0)
      _fail(
        'Der Minijob-Gesamtfall enthält widersprüchliche Individualsteuern.',
      );
  } else {
    if (v['rule_version'] == payrollFactorTaxfreeTravelRule &&
        taxes.any(
          (tax) =>
              tax['calculation']?['factor'] !=
                  d['factor_parameters']?['tax_factor'] ||
              tax['calculation']?['version'] !=
                  'bmf_2026_standard_factor_period_wrapper_v2',
        ))
      _fail('Die einzelne Steuerrechnung gehört nicht zum bestätigten Faktor.');
    if (!payrollFactsSame(
          taxes.map((a) => a['period']).toList(),
          d['tax_periods'],
        ) ||
        !_hash.hasMatch('${v['pap_provenance_sha256']}') ||
        v['pap_version'] is! String)
      _fail(
        'Die PAP-Einzelrechnungen besitzen keinen eindeutigen Steuerzeitraum.',
      );
    if (taxes.fold<int>(
              0,
              (a, b) => a + _integer(b['calculation']?['totals']?['LSTLZZ']),
            ) !=
            v['individual_wage_tax_minor'] ||
        taxes.fold<int>(
              0,
              (a, b) => a + _integer(b['calculation']?['totals']?['SOLZLZZ']),
            ) !=
            v['solidarity_minor'] ||
        taxes.fold<int>(0, (a, b) => a + _integer(b['church_tax_minor'])) !=
            v['church_tax_minor'])
      _fail(
        'Die einzelnen PAP-Steuern stimmen nicht mit dem Gesamtbetrag überein.',
      );
  }
  return v;
}

Map<String, dynamic> payrollCompositeSource(
  dynamic raw,
  Map<String, dynamic> input,
) {
  final v = businessMap(raw),
      s = businessMap(v['source']),
      c = payrollCompositeCalculation(v['calculation']),
      fact = payrollCalculationCaseRecord(
        s['calculation_case'],
        input['employee_id'],
      );
  final base = fact['sources']['period_case'];
  if (s['source_schema_version'] != 3 ||
      !payrollFactsSame(s['input'], input) ||
      !payrollFactsSame(payrollFactRef(fact), input['calculation_case_ref']) ||
      s['employee_id'] != input['employee_id'] ||
      fact['status'] != 'active' ||
      s['month'] != fact['details']['month'] ||
      c['month'] != s['month'] ||
      c['rule_version'] != fact['rule_version'] ||
      c['source_contract_version'] != fact['source_contract_version'] ||
      !payrollFactsSame(s['preparation'], base['sources']['preparation']) ||
      !businessItems(fact['sources']['profiles']).any(
        (p) =>
            payrollFactsSame(p, s['profile']) &&
            payrollFactsSame(
              payrollFactRef(p),
              fact['plan']['selected_profile_ref'],
            ),
      ) ||
      c['period_details']['plan_hash'] != fact['plan']['plan_hash'] ||
      c['period_details']['source_snapshot_hash'] != fact['source_hash'] ||
      c['gross_minor'] != fact['plan']['gross_minor'] ||
      v['can_finalize'] != c['payroll_calculation_complete'])
    _fail(
      'Die Gesamtlohnvorschau gehört nicht zum ausgewählten bestätigten Gesamtfall.',
    );
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
    if (fact['rule_version'] == payrollFactorTaxfreeTravelRule) ...[
      'factor_parameters',
      'travel_payment_refs',
      'travel_paid_minor',
    ],
  ])
    if (!payrollFactsSame(c['period_details'][key], fact['plan'][key]))
      _fail(
        'Die Gesamtlohnrechnung hat einen geprüften Planbestandteil ersetzt.',
      );
  return v;
}

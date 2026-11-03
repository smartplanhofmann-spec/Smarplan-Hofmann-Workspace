import 'dart:convert';

import 'api.dart';
import 'business_payroll_facts.dart';
import 'business_session.dart' show businessMap, businessItems;

const payrollEntitlementKinds = {
  'sickness_history': 'Krankheitsverlauf und Vorzeiten',
  'regular_absence': 'Belegte regelmäßige Ausfallvergütung',
  'vacation_reference': 'Urlaubsentgelt aus 13 Wochen',
  'unpaid_continuation': 'Unbezahlte Unterbrechung und SV-Fortbestand',
};
const payrollAbsenceKinds = {
  'public_holiday': 'Gesetzlicher Feiertag',
  'sickness': 'Krankheit mit geprüftem Anspruch',
  'first_sickness_day_regular_wage':
      'Erster Krankheitstag nach begonnener Arbeit',
};
const payrollOnsets = {
  'before_work': 'Vor Arbeitsbeginn',
  'during_work': 'Während tatsächlich begonnener Arbeit',
  'non_workday': 'An einem planmäßig arbeitsfreien Tag',
};
const payrollSicknessModes = {
  'separate': 'Getrennte Krankheitsfälle',
  'combined': 'Zusammenhängende Erkrankungsursachen',
  'preemployment': 'Erkrankung vor Beschäftigungsbeginn',
};
const _phaseRules = ['de_2026_sickness_phases_v3', 'de_2026_sickness_start_v4'];
const payrollContinuationExceptions = {
  'sickness_benefit': 'Krankengeld',
  'private_sickness_benefit': 'Privates Krankentagegeld',
  'injury_benefit': 'Verletztengeld',
  'social_compensation_sickness_benefit':
      'Krankengeld der Sozialen Entschädigung',
  'soldier_compensation_sickness_benefit': 'Soldatenentschädigungs-Krankengeld',
  'transition_benefit': 'Übergangsgeld',
  'care_support_benefit': 'Pflegeunterstützungsgeld',
  'maternity_benefit': 'Mutterschaftsgeld',
  'child_raising_benefit': 'Erziehungsgeld',
  'parental_benefit': 'Elterngeld',
  'parental_leave': 'Elternzeit',
  'military_service': 'Wehrdienst',
  'civilian_service': 'Zivildienst',
  'care_leave_section_3': 'Pflegezeit nach § 3',
};
final _id = RegExp(r'^[a-f0-9]{32}$'), _hash = RegExp(r'^[a-f0-9]{64}$');
Map<String, dynamic> _copy(dynamic value) =>
    Map<String, dynamic>.from(jsonDecode(jsonEncode(value)) as Map);
Never _fail(String message, [int status = 0]) =>
    throw ApiException(status, message);
String _note(dynamic value, String label) {
  if (value is! String ||
      value.trim().isEmpty ||
      value.trim().length > 3000 ||
      RegExp(r'[\x00-\x1f\x7f]').hasMatch(value))
    _fail('$label ausdrücklich belegen.', 400);
  return value.trim();
}

Map<String, bool> payrollEntitlementRights(dynamic raw) {
  final caps = businessMap(raw),
      permissions = Set.from(caps['permissions'] ?? []);
  final read =
      (caps['features'] as List? ?? []).contains('payroll_entitlements') &&
      (caps['capabilities'] as List? ?? []).contains(
        'business_payroll_entitlements',
      ) &&
      permissions.contains('personnel.read');
  return {
    'read': read,
    'approve':
        read &&
        caps['readonly'] == false &&
        permissions.contains('personnel.approve'),
    'enabled':
        read &&
        caps['readonly'] == false &&
        caps['organization']?['modules']?['personnel']?['enabled'] != false,
  };
}

bool _supportedPlan(Map<String, dynamic> plan, String kind) =>
    plan['schema_version'] is int &&
    plan['schema_version'] == 1 &&
    plan['kind'] == kind &&
    (plan['rule_version'] == 'de_2026_entitlements_v1' ||
        kind == 'sickness_history' &&
            [
              'de_2026_sickness_v2',
              ..._phaseRules,
            ].contains(plan['rule_version'])) &&
    [
      'rules_hash',
      'input_hash',
      'source_hash',
      'plan_hash',
    ].every((k) => _hash.hasMatch('${plan[k]}')) &&
    _sicknessPlanShape(plan);

bool _sicknessPlanShape(Map<String, dynamic> plan) {
  if (!_phaseRules.contains(plan['rule_version'])) return true;
  if (plan['episodes'] is! List ||
      plan['prevention_cases'] is! List ||
      plan['phases'] is! List)
    return false;
  final cases = businessItems(plan['prevention_cases'])
          .map((v) => v['id'])
          .toSet(),
      episodes = businessItems(plan['episodes'])
          .map((v) => v['episode_id'])
          .toSet();
  if (cases.length != (plan['prevention_cases'] as List).length ||
      episodes.length != (plan['episodes'] as List).length ||
      [...cases, ...episodes].any((v) => !_id.hasMatch('$v')))
    return false;
  String? last;
  for (final phase in businessItems(plan['phases'])) {
    final active = phase['active_episode_ids'];
    if (!cases.contains(phase['prevention_case_id']) ||
        active is! List ||
        active.isEmpty ||
        active.toSet().length != active.length ||
        active.any((v) => !episodes.contains(v)) ||
        !active.contains(phase['responsible_episode_id']) ||
        [
          'entitled',
          'first_day_remaining_regular_wage',
          'waiting_period',
        ].any((k) => phase[k] is! bool))
      return false;
    try {
      final first = payrollFactDate(phase['from_date'])!,
          end = payrollFactDate(phase['to_date'])!;
      if (first.compareTo(end) > 0 ||
          last != null && first.compareTo(last) <= 0)
        return false;
      last = end;
    } catch (_) {
      return false;
    }
  }
  if (plan['rule_version'] == 'de_2026_sickness_start_v4' &&
      (!_hash.hasMatch('${plan['legal_projection_hash']}') ||
          plan['preemployment_periods'] is! List ||
          (plan['preemployment_periods'] as List).isEmpty ||
          businessItems(plan['preemployment_periods']).any(
            (v) =>
                !episodes.contains(v['episode_id']) ||
                v['employment_wage_entitlement'] != false,
          )))
    return false;
  return true;
}

Map<String, dynamic> payrollSicknessStructure(
  Map<String, dynamic> source,
  String mode, {
  List<String> caseChoices = const [],
  List<String> caseIds = const [],
  List<Map<String, dynamic>> evidenceRefs = const [],
  Map<String, dynamic>? commencement,
}) {
  final value = _copy(source), episodes = businessItems(source['episodes']);
  if (!payrollSicknessModes.containsKey(mode) || source['episodes'] is! List)
    _fail(
      'Die tatsächliche Form des Krankheitsverlaufs ausdrücklich wählen.',
      400,
    );
  if (mode == 'separate') {
    if (episodes.any(
      (v) =>
          !payrollOnsets.containsKey(v['onset']) ||
          v['recovery_before'] != true,
    ))
      _fail(
        'Getrennte Fälle benötigen belegte Arbeitsfähigkeit vor jedem neuen Fall.',
        400,
      );
    return value;
  }
  if (caseChoices.length != episodes.length ||
      caseIds.length != episodes.length ||
      evidenceRefs.isEmpty)
    _fail(
      'Jede Ursache einem konkret belegten Verhinderungsfall zuordnen.',
      400,
    );
  final cases = <Map<String, dynamic>>[], assigned = <Map<String, dynamic>>[];
  for (var i = 0; i < episodes.length; i++) {
    final episode = episodes[i], choice = caseChoices[i];
    late Map<String, dynamic> selected;
    if (choice == 'new') {
      if (episode['recovery_before'] != true ||
          episode['onset'] == 'during_existing_au' ||
          !_id.hasMatch(caseIds[i]) ||
          cases.any((v) => v['id'] == caseIds[i]))
        _fail(
          'Ein neuer Verhinderungsfall benötigt eine eigene Kennung und belegte vorherige Arbeitsfähigkeit.',
          400,
        );
      selected = {
        'id': caseIds[i],
        'episode_ids': <String>[],
        'evidence_refs': evidenceRefs.map(_copy).toList(),
      };
      cases.add(selected);
    } else if (RegExp(r'^same:\d+$').hasMatch(choice) &&
        int.parse(choice.substring(5)) < i) {
      if (episode['recovery_before'] != false ||
          episode['onset'] != 'during_existing_au' ||
          episode['first_scheduled_day'] != null)
        _fail(
          'Ein Hinzutritt muss bei fortbestehender AU ohne erfundenen Solltag belegt sein.',
          400,
        );
      selected = assigned[int.parse(choice.substring(5))];
    } else {
      _fail(
        'Den zusammenhängenden Verhinderungsfall ausdrücklich auswählen.',
        400,
      );
    }
    (selected['episode_ids'] as List).add(episode['id']);
    assigned.add(selected);
  }
  value['prevention_cases'] = cases;
  if (mode == 'preemployment') {
    if (!episodes.any((v) => v['onset'] == 'before_employment') ||
        commencement == null ||
        commencement['evidence_refs'] is! List ||
        (commencement['evidence_refs'] as List).isEmpty)
      _fail(
        'Ursprünglichen AU-Beginn, tatsächliches Vertragsdatum und Vertragsoriginal belegen.',
        400,
      );
    payrollFactDate(commencement['contract_concluded_on']);
    value['employment_commencement'] = _copy(commencement);
  } else if (episodes.any((v) => v['onset'] == 'before_employment')) {
    _fail(
      'Eine AU vor Beschäftigungsbeginn benötigt den ausdrücklichen Beginnfall.',
      400,
    );
  }
  return value;
}

Map<String, dynamic> payrollEntitlementRecord(
  dynamic raw,
  String employeeId, {
  String? kind,
}) {
  final value = businessMap(raw),
      sources = businessMap(businessMap(raw)['sources']),
      details = businessMap(businessMap(raw)['details']);
  payrollFactRef(value);
  final ids = value['source_file_ids'];
  if (value['employee_id'] != employeeId ||
      !payrollEntitlementKinds.containsKey(value['kind']) ||
      kind != null && value['kind'] != kind ||
      !['active', 'void'].contains(value['status']) ||
      !_id.hasMatch('${details['case_key']}') ||
      sources['employee']?['id'] != employeeId ||
      value['plan'] is! Map ||
      !_hash.hasMatch('${value['source_hash']}') ||
      !_hash.hasMatch('${value['preview_hash']}') ||
      ids is! List ||
      ids.isEmpty ||
      ids.toSet().length != ids.length ||
      ids.any((v) => !_id.hasMatch('$v')) ||
      (value['revision'] == 1
          ? value['previous_hash'] != null
          : !_hash.hasMatch('${value['previous_hash']}')))
    _fail(
      'Der Anspruchsnachweis ist nicht eindeutig an Mitarbeiter und Originalfassung gebunden.',
    );
  final from = payrollFactDate(value['effective_from'])!,
      to = payrollFactDate(value['effective_to'])!;
  if (from.compareTo(to) > 0 ||
      !payrollFactsSame(details, sources['details']) ||
      value['kind'] != sources['kind'])
    _fail('Anspruchsdetails und eingefrorene Quellen widersprechen sich.');
  if (!_supportedPlan(businessMap(value['plan']), value['kind']) ||
      value['plan']['source_hash'] != value['source_hash'])
    _fail(
      'Der Anspruchsnachweis verwendet keinen bekannten unveränderten Regelstand.',
    );
  return value;
}

Map<String, dynamic> payrollEntitlementSources(dynamic raw, String employeeId) {
  final value = payrollFactSources(raw, employeeId);
  if (value['entitlements'] is! List ||
      value['file_references'] is! List ||
      (value['file_references'] as List).length !=
          (value['files'] as List).length)
    _fail('Die kanonischen Anspruchs- und Originalreferenzen fehlen.');
  final seen = <String>{};
  for (final fact in businessItems(value['entitlements']))
    if (!seen.add(payrollEntitlementRecord(fact, employeeId)['id']))
      _fail('Eine Anspruchsquelle ist mehrfach enthalten.');
  final originals = <String>{};
  for (final ref in businessItems(value['file_references'])) {
    payrollFactRef(ref);
    final files = businessItems(value['files'])
        .where((f) => f['id'] == ref['id']);
    if (files.length != 1 ||
        ref['revision'] != 1 ||
        ref['content_hash'] != files.single['content_hash'] ||
        !originals.add(ref['id']))
      _fail('Die Anspruchsoriginalreferenz widerspricht der Personaldatei.');
  }
  return value;
}

List<Map<String, dynamic>> _refs(
  dynamic items,
  dynamic ids,
  String employeeId,
  String label, {
  String? kind,
  bool optional = false,
}) {
  if (ids is! List ||
      !optional && ids.isEmpty ||
      ids.toSet().length != ids.length)
    _fail('$label ausdrücklich auswählen.', 400);
  final sorted = List<String>.from(ids)..sort();
  return sorted.map((id) {
    final matches = businessItems(items).where(
      (v) =>
          v['id'] == id &&
          v['employee_id'] == employeeId &&
          v['status'] != 'void' &&
          (kind == null || v['kind'] == kind),
    );
    if (matches.length != 1)
      _fail('$label gehört nicht zum gewählten Mitarbeiterstand.', 400);
    return payrollFactRef(matches.single);
  }).toList();
}

List<Map<String, dynamic>> payrollEntitlementEvidence(
  Map<String, dynamic> sources,
  dynamic ids,
  List<dynamic> outer,
) {
  if (ids is! List || ids.isEmpty || ids.toSet().length != ids.length)
    _fail('Die konkreten Anspruchsoriginale ausdrücklich auswählen.', 400);
  return (List<String>.from(ids)..sort()).map((id) {
    final refs = businessItems(sources['file_references'])
        .where((v) => v['id'] == id);
    if (refs.length != 1 || !outer.contains(id))
      _fail(
        'Jedes Anspruchsoriginal muss zusätzlich in den gesamten Personaloriginalen enthalten sein.',
        400,
      );
    return payrollFactRef(refs.single);
  }).toList();
}

dynamic _normalize(dynamic value, [String? key]) {
  if (value is List) {
    final result = value.map((v) => _normalize(v)).toList();
    String Function(dynamic)? order;
    if (['evidence_refs', 'history_evidence_refs'].contains(key))
      order = (v) => '${v['id']}:${v['revision']}';
    if (['days', 'reference_days', 'vacation_days'].contains(key))
      order = (v) => '${v['date']}';
    if (key == 'episodes') order = (v) => '${v['from']}${v['id']}';
    if (key == 'exceptions')
      order = (v) => '${v['from']}${v['to']}${v['kind']}';
    if (order != null) result.sort((a, b) => order!(a).compareTo(order(b)));
    return result;
  }
  if (value is Map)
    return {
      for (final entry in value.entries)
        '${entry.key}': _normalize(entry.value, '${entry.key}'),
    };
  return value;
}

Map<String, dynamic> payrollEntitlementInput(
  String employeeId,
  Map<String, dynamic> sources,
  String kind,
  Map<String, dynamic> values, {
  Map<String, dynamic>? previous,
}) {
  payrollEntitlementSources(sources, employeeId);
  if (!payrollEntitlementKinds.containsKey(kind))
    _fail('Unbekannte Anspruchsart.', 400);
  if (previous != null)
    payrollEntitlementRecord(previous, employeeId, kind: kind);
  final ids = values['source_file_ids'],
      caseKey = previous?['details']['case_key'] ?? values['case_key'];
  if (ids is! List ||
      ids.isEmpty ||
      ids.length > 20 ||
      ids.toSet().length != ids.length ||
      ids.any(
        (id) => !businessItems(sources['files']).any((v) => v['id'] == id),
      ))
    _fail('Ein bis zwanzig geschützte Personaloriginale auswählen.', 400);
  if (!_id.hasMatch('$caseKey'))
    _fail('Die ursprüngliche Anspruchsfallkennung fehlt.', 400);
  final historyId = '${values['sickness_history_id'] ?? ''}';
  final history = historyId.isEmpty
      ? null
      : _refs(
          sources['entitlements'],
          [historyId],
          employeeId,
          'Geprüfter Krankheitsverlauf',
          kind: 'sickness_history',
        ).single;
  if (history != null && kind != 'regular_absence')
    _fail(
      'Ein Krankheitsverlauf gehört nur zur konkreten Ausfallvergütung.',
      400,
    );
  if (values['input'] is! Map)
    _fail('Anspruchsangaben vollständig und strukturiert belegen.', 400);
  final input = _normalize(_copy(values['input']));
  void check(dynamic value) {
    if (value is List) {
      for (final item in value) check(item);
    } else if (value is Map) {
      for (final entry in value.entries) {
        if (['evidence_refs', 'history_evidence_refs'].contains(entry.key)) {
          final refs = entry.value;
          if (refs is! List ||
              refs.isEmpty ||
              refs.any((v) => v is! Map) ||
              !payrollFactsSame(
                refs,
                payrollEntitlementEvidence(
                  sources,
                  refs.map((v) => v['id']).toList(),
                  ids,
                ),
              ))
            _fail(
              'Die gewählte Anspruchsoriginalfassung ist nicht eindeutig.',
              400,
            );
        } else {
          check(entry.value);
        }
      }
    }
  }

  check(input);
  return {
    'employee_id': employeeId,
    'employee_revision': sources['employee']['revision'],
    'kind': kind,
    'revision': previous?['revision'] ?? 0,
    'status': 'active',
    'details': {
      'case_key': caseKey,
      'employment_terms_ref': _refs(
        sources['facts'],
        [values['employment_terms_id']],
        employeeId,
        'Beschäftigungsnachweis',
        kind: 'employment_terms',
      ).single,
      'work_schedule_refs': _refs(
        sources['facts'],
        values['work_schedule_ids'],
        employeeId,
        'Datierte Arbeitspläne',
        kind: 'work_schedule',
        optional: true,
      ),
      'preparation_refs': _refs(
        sources['preparations'],
        values['preparation_ids'],
        employeeId,
        'Abgeschlossene Monatsvorbereitungen',
        optional: true,
      ),
      'agreement_refs': _refs(
        sources['agreements'],
        values['agreement_ids'],
        employeeId,
        'Einschlägige Entgeltvereinbarungen',
      ),
      'sickness_history_ref': history,
      'input': input,
      'verification_note': _note(
        values['verification_note'],
        'Anspruchsprüfung',
      ),
    },
    'source_file_ids': List<String>.from(ids)..sort(),
    'confirmed': true,
    if (previous != null) ...{
      'id': previous['id'],
      'correction_reason': _note(values['correction_reason'], 'Korrekturgrund'),
    },
  };
}

Map<String, dynamic> payrollEntitlementPreviewInput(
  Map<String, dynamic> body,
) => _copy({
  for (final key in [
    'employee_id',
    'employee_revision',
    'kind',
    'details',
    'source_file_ids',
  ])
    key: body[key],
});

Map<String, dynamic> payrollEntitlementPreview(
  dynamic raw,
  Map<String, dynamic> body,
) {
  final value = businessMap(raw),
      s = businessMap(businessMap(raw)['source_snapshot']),
      p = businessMap(businessMap(raw)['plan']),
      d = businessMap(body['details']);
  if (!_supportedPlan(p, body['kind']) ||
      p['source_hash'] != value['source_hash'] ||
      [
        'rules_hash',
        'input_hash',
        'source_hash',
        'plan_hash',
      ].any((k) => !_hash.hasMatch('${p[k]}')))
    _fail(
      'Der Anspruchsplan ist nicht an den bekannten Quellen- und Regelstand gebunden.',
    );
  if (value['employee_id'] != body['employee_id'] ||
      value['kind'] != body['kind'] ||
      s['employee']?['id'] != body['employee_id'] ||
      s['employee']?['revision'] != body['employee_revision'] ||
      s['kind'] != body['kind'] ||
      s['schema_version'] != 1 ||
      !payrollFactsSame(s['details'], d) ||
      !_hash.hasMatch('${value['source_hash']}') ||
      !_hash.hasMatch('${value['preview_hash']}') ||
      [
        'can_confirm',
        'can_calculate',
        'can_write',
        'can_approve',
        'writes_enabled',
      ].any((k) => value[k] is! bool))
    _fail(
      'Die Anspruchsvorschau ist nicht an den ausdrücklich geprüften Mitarbeiterstand gebunden.',
    );
  for (final pair in [
    ('work_schedules', 'work_schedule_refs'),
    ('preparations', 'preparation_refs'),
    ('agreements', 'agreement_refs'),
  ]) {
    if (!payrollFactsSame(
      businessItems(s[pair.$1]).map(payrollFactRef).toList(),
      d[pair.$2],
    ))
      _fail(
        'Eine Anspruchsquelle wurde gegenüber der gewählten Fassung ausgetauscht.',
      );
  }
  if (!payrollFactsSame(
        payrollFactRef(s['employment_terms']),
        d['employment_terms_ref'],
      ) ||
      !payrollFactsSame(
        s['sickness_history'] == null
            ? null
            : payrollFactRef(s['sickness_history']),
        d['sickness_history_ref'],
      ) ||
      !payrollFactsSame(
        (businessItems(s['source_files']).map((v) => v['id']).toList()..sort()),
        body['source_file_ids'],
      ))
    _fail(
      'Eine Anspruchsquelle wurde gegenüber der gewählten Fassung ausgetauscht.',
    );
  for (final item in [
    businessMap(s['employment_terms']),
    ...businessItems(s['work_schedules']),
    ...businessItems(s['preparations']),
    ...businessItems(s['agreements']),
    ...businessItems(s['source_files']),
    if (s['sickness_history'] != null) businessMap(s['sickness_history']),
  ])
    if (item['employee_id'] != body['employee_id'])
      _fail('Die Anspruchsvorschau enthält eine fremde private Quelle.');
  return value;
}

void Function(dynamic) payrollEntitlementValidator(
  Map<String, dynamic> body, {
  Map<String, dynamic>? previous,
  Map<String, dynamic>? preview,
}) {
  final original = _copy(body),
      prior = previous == null ? null : _copy(previous),
      prepared = preview == null ? null : _copy(preview);
  return (raw) {
    final value = payrollEntitlementRecord(
      raw,
      original['employee_id'],
      kind: original['kind'],
    );
    if (value['revision'] != (prior?['revision'] ?? 0) + 1 ||
        prior != null && value['id'] != prior['id'] ||
        value['previous_hash'] != prior?['content_hash'] ||
        value['status'] != original['status'] ||
        !payrollFactsSame(value['details'], original['details']) ||
        !payrollFactsSame(
          value['source_file_ids'],
          original['source_file_ids'],
        ) ||
        value['preview_hash'] != original['preview_hash'] ||
        value['correction_reason'] != (original['correction_reason'] ?? ''))
      _fail(
        'Die Anspruchsquittung gehört nicht zum unveränderten ursprünglichen Auftrag.',
      );
    if (prepared != null &&
        (!payrollFactsSame(value['sources'], prepared['source_snapshot']) ||
            !payrollFactsSame(value['plan'], prepared['plan']) ||
            value['source_hash'] != prepared['source_hash']))
      _fail(
        'Die angenommene Anspruchsfassung ersetzt die ausdrücklich geprüften Quellen.',
      );
    if (value['status'] == 'void' &&
        (prior == null ||
            !payrollFactsSame(value['sources'], prior['sources']) ||
            !payrollFactsSame(value['plan'], prior['plan']) ||
            value['source_hash'] != prior['source_hash'] ||
            value['preview_hash'] != prior['preview_hash']))
      _fail(
        'Die Aufhebung darf keinen früheren Anspruchs- oder Quellenstand ersetzen.',
      );
  };
}

int payrollEntitlementMoney(dynamic value) {
  final text = '${value ?? ''}'.trim().replaceAll(',', '.');
  if (!RegExp(r'^\d{1,9}(?:\.\d{1,2})?$').hasMatch(text))
    _fail(
      'Einen belegten EUR-Betrag ausdrücklich angeben, auch bekannte 0,00.',
      400,
    );
  final parts = text.split('.');
  return int.parse(parts[0]) * 100 +
      int.parse((parts.length == 1 ? '' : parts[1]).padRight(2, '0'));
}

List<String> payrollEntitlementDays(String from, String to) {
  payrollFactDate(from);
  payrollFactDate(to);
  if (from.compareTo(to) > 0) _fail('Das Ende liegt vor dem Beginn.', 400);
  final first = DateTime.parse('${from}T12:00:00Z'),
      last = DateTime.parse('${to}T12:00:00Z'),
      count =
          DateTime.parse('${to}T12:00:00Z')
              .difference(DateTime.parse('${from}T12:00:00Z'))
              .inDays +
          1;
  if (count > 10000) _fail('Den belegten Zeitraum eingrenzen.', 400);
  return [
    for (
      var day = first;
      !day.isAfter(last);
      day = day.add(const Duration(days: 1))
    )
      day.toIso8601String().substring(0, 10),
  ];
}

Map<String, dynamic> payrollEntitlementDaySource(
  Map<String, dynamic> sources,
  Map<String, dynamic> values,
  String date,
) {
  final schedules = businessItems(sources['facts']).where(
    (v) =>
        (values['work_schedule_ids'] as List).contains(v['id']) &&
        v['kind'] == 'work_schedule',
  );
  final days = schedules
      .expand(
        (v) =>
            businessItems(v['details']['days']).where((v) => v['date'] == date),
      )
      .toList();
  final prepared = businessItems(sources['preparations'])
      .where(
        (v) =>
            (values['preparation_ids'] as List).contains(v['id']) &&
            v['month'] == date.substring(0, 7),
      )
      .toList();
  final agreements =
      businessItems(sources['agreements'])
          .where(
            (v) =>
                (values['agreement_ids'] as List).contains(v['id']) &&
                (v['effective_from'] as String).compareTo(date) <= 0,
          )
          .toList()
        ..sort(
          (a, b) =>
              (a['effective_from'] as String).compareTo(b['effective_from']),
        );
  if (days.length != 1 || prepared.length != 1 || agreements.isEmpty)
    _fail(
      'Für $date genau einen Arbeitsplan, die abgeschlossene Monatsvorbereitung und die einschlägige Vereinbarung auswählen.',
      400,
    );
  final worked = businessItems(prepared.single['snapshot']['approved_days'])
      .where((v) => v['date'] == date)
      .fold<int>(0, (sum, v) => sum + (v['net_seconds'] as int));
  return {
    'scheduled': days.single['scheduled_seconds'],
    'worked': worked,
    'agreement': agreements.last,
    'federal_state': days.single['federal_state'],
  };
}

import 'dart:convert';

import 'package:flutter/material.dart';

import 'api.dart';
import 'business_session.dart';
import 'business_widgets.dart';
import 'design.dart';

const payrollFactKinds = {
  'employment_terms': 'Beschäftigung und Entgelt',
  'work_schedule': 'Datierter Arbeitsplan',
  'period_case': 'Bestätigter Monatsfall',
};
const payrollProration = {
  'calendar_days_actual': 'Tatsächliche Kalendertage laut Vertrag',
  'contractual_30_days': 'Vertraglich belegtes 30-Tage-Verfahren',
  'scheduled_workdays': 'Belegte Sollarbeitstage',
  'scheduled_seconds': 'Belegte Sollarbeitszeit',
};
const payrollFactStates = {
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
const payrollEntitlements = {
  'ordinary_work': 'Gewöhnliche Arbeit',
  'public_holiday': 'Gesetzlicher Feiertag',
  'vacation': 'Urlaub',
  'sickness_continued_pay':
      'Krankheit mit belegtem Entgeltfortzahlungsanspruch',
  'unpaid_leave': 'Unbezahlte Freistellung',
  'sickness_after_entitlement': 'Krankheit nach Ende des Entgeltanspruchs',
};
final _id = RegExp(r'^[a-f0-9]{32}$'), _hash = RegExp(r'^[a-f0-9]{64}$');
Map<String, dynamic> _copy(dynamic value) =>
    Map<String, dynamic>.from(jsonDecode(jsonEncode(value)) as Map);
Never _fail(String value, [int status = 0]) =>
    throw ApiException(status, value);
dynamic _ordered(dynamic value) {
  if (value is List) return value.map(_ordered).toList();
  if (value is Map)
    return {
      for (final key in value.keys.map((k) => '$k').toList()..sort())
        key: _ordered(value[key]),
    };
  return value;
}

bool payrollFactsSame(dynamic a, dynamic b) =>
    jsonEncode(_ordered(a)) == jsonEncode(_ordered(b));
String _text(dynamic value, String label, [int max = 2000]) {
  final result = '${value ?? ''}'.trim();
  if (result.isEmpty ||
      result.length > max ||
      RegExp(r'[\x00-\x1f\x7f]').hasMatch(result))
    _fail('$label vollständig angeben.');
  return result;
}

String? payrollFactDate(dynamic value, {bool optional = false}) {
  final result = '${value ?? ''}'.trim();
  if (result.isEmpty && optional) return null;
  final parsed = DateTime.tryParse(result);
  if (!RegExp(r'^\d{4}-\d{2}-\d{2}$').hasMatch(result) ||
      parsed == null ||
      parsed.toIso8601String().substring(0, 10) != result)
    _fail('Ein tatsächliches gültiges Kalendertagsdatum angeben.');
  return result;
}

String payrollFactMonth(dynamic value) {
  if (value is! String || !RegExp(r'^2026-(0[1-9]|1[0-2])$').hasMatch(value))
    _fail('Einen belegten Kalendermonat 2026 im Format JJJJ-MM wählen.');
  return value;
}

int payrollFactSeconds(dynamic value) {
  final match = RegExp(r'^(\d{1,2}):([0-5]\d)(?::([0-5]\d))?$')
      .firstMatch('${value ?? ''}'.trim());
  if (match == null)
    _fail(
      'Sollzeit ausdrücklich als Stunden:Minuten angeben, auch bekannte 00:00.',
    );
  final seconds =
      int.parse(match.group(1)!) * 3600 +
      int.parse(match.group(2)!) * 60 +
      int.parse(match.group(3) ?? '0');
  if (seconds > 86400)
    _fail('Eine Tages-Sollzeit darf 24 Stunden nicht überschreiten.');
  return seconds;
}

String payrollFactTime(dynamic seconds) {
  if (seconds is! int || seconds < 0 || seconds > 86400)
    _fail('Die belegte Sollzeit ist ungültig.');
  final parts = [
    seconds ~/ 3600,
    seconds ~/ 60 % 60,
    seconds % 60,
  ].map((n) => '$n'.padLeft(2, '0')).toList();
  return parts.take(seconds % 60 == 0 ? 2 : 3).join(':');
}

List<String> payrollFactDates(String value) {
  final month = payrollFactMonth(value),
      count = DateTime(
        int.parse(month.substring(0, 4)),
        int.parse(month.substring(5)) + 1,
        0,
      ).day;
  return List.generate(count, (i) => '$month-${'${i + 1}'.padLeft(2, '0')}');
}

Map<String, dynamic> payrollFactRef(dynamic raw) {
  final value = businessMap(raw);
  if (!_id.hasMatch('${value['id']}') ||
      value['revision'] is! int ||
      value['revision'] < 1 ||
      !_hash.hasMatch('${value['content_hash']}'))
    _fail('Eine genaue belegte Quellenfassung auswählen.');
  return {
    for (final key in ['id', 'revision', 'content_hash']) key: value[key],
  };
}

Map<String, dynamic> payrollFactRecord(
  dynamic raw,
  String employeeId, {
  String? kind,
}) {
  final value = businessMap(raw);
  payrollFactRef(value);
  final ids = value['source_file_ids'];
  if (value['employee_id'] != employeeId ||
      !payrollFactKinds.containsKey(value['kind']) ||
      kind != null && value['kind'] != kind ||
      !['active', 'void'].contains(value['status']) ||
      value['details'] is! Map ||
      value['sources'] is! Map ||
      !_hash.hasMatch('${value['source_hash']}') ||
      ids is! List ||
      ids.isEmpty ||
      ids.any((id) => !_id.hasMatch('$id')) ||
      ids.toSet().length != ids.length ||
      (value['kind'] == 'period_case'
          ? value['plan'] is! Map || !_hash.hasMatch('${value['preview_hash']}')
          : value['plan'] != null || value['preview_hash'] != null) ||
      (value['revision'] == 1
          ? value['previous_hash'] != null
          : !_hash.hasMatch('${value['previous_hash']}')))
    _fail(
      'Der Faktennachweis ist nicht eindeutig an Mitarbeiter, Art und ursprüngliche Fassung gebunden.',
    );
  payrollFactDate(value['effective_from']);
  payrollFactDate(value['effective_to'], optional: true);
  final dates = value['kind'] == 'employment_terms'
      ? [value['details']['employment_from'], value['details']['employment_to']]
      : payrollFactDates(value['details']['month']);
  if (value['effective_from'] != dates.first ||
      value['effective_to'] != dates.last)
    _fail('Der Gültigkeitszeitraum widerspricht den belegten Fakten.');
  return value;
}

Map<String, dynamic> payrollFactSources(dynamic raw, String employeeId) {
  final value = businessMap(raw), person = businessMap(value['employee']);
  if (!_id.hasMatch(employeeId) ||
      value['employee_id'] != employeeId ||
      person['id'] != employeeId ||
      person['revision'] is! int ||
      person['revision'] < 1 ||
      [
        'files',
        'agreements',
        'preparations',
        'profiles',
        'identities',
        'facts',
        'absences',
      ].any((key) => value[key] is! List) ||
      [
        'can_write',
        'can_approve',
        'writes_enabled',
      ].any((key) => value[key] is! bool))
    _fail(
      'Die privaten Lohnquellen gehören nicht eindeutig zum gewählten Mitarbeiter.',
    );
  for (final key in [
    'files',
    'agreements',
    'preparations',
    'profiles',
    'identities',
    'facts',
    'absences',
  ]) {
    final ids = <String>{};
    for (final item in businessItems(value[key])) {
      if (item['employee_id'] != employeeId ||
          !_id.hasMatch('${item['id']}') ||
          !ids.add(item['id']))
        _fail(
          'Eine private Quelle gehört zu einer anderen Person oder ist mehrfach enthalten.',
        );
      if (key == 'files') {
        if (item['purpose'] != 'personnel' ||
            !_hash.hasMatch('${item['sha256']}') ||
            !_hash.hasMatch('${item['content_hash']}') ||
            item['size'] is! int ||
            item['size'] < 1)
          _fail('Ein geschützter Personaloriginalnachweis fehlt.');
      } else if (key == 'absences') {
        if (item['status'] != 'approved' ||
            payrollFactDate(item['start_date'])!
                    .compareTo(payrollFactDate(item['end_date'])!) >
                0 ||
            item.containsKey('details')) {
          _fail(
            'Eine genehmigte Abwesenheitsquelle ist unvollständig oder enthält unnötige private Angaben.',
          );
        }
      } else {
        payrollFactRef(item);
      }
      if (key == 'facts') payrollFactRecord(item, employeeId);
    }
  }
  return value;
}

List<Map<String, dynamic>> _selection(
  dynamic raw,
  dynamic selected,
  String employeeId,
  String label, {
  String? kind,
  bool optional = false,
}) {
  if (selected is! List ||
      selected.toSet().length != selected.length ||
      !optional && selected.isEmpty)
    _fail('$label ausdrücklich auswählen.');
  final ids = selected.map((v) => '$v').toList()..sort(),
      items = businessItems(raw);
  return ids.map((id) {
    final matches = items.where(
      (item) =>
          item['id'] == id &&
          item['employee_id'] == employeeId &&
          (kind == null || item['kind'] == kind) &&
          item['status'] != 'void',
    );
    if (matches.isEmpty)
      _fail('$label gehört nicht zum aktuellen Mitarbeiterstand.');
    return payrollFactRef(matches.first);
  }).toList();
}

Map<String, dynamic> payrollFactInput(
  String employeeId,
  Map<String, dynamic> sources,
  String kind,
  Map<String, dynamic> values, {
  Map<String, dynamic>? previous,
}) {
  payrollFactSources(sources, employeeId);
  if (!payrollFactKinds.containsKey(kind)) _fail('Unbekannte Lohnfaktenart.');
  final ids = values['source_file_ids'];
  if (ids is! List ||
      ids.isEmpty ||
      ids.length > 20 ||
      ids.toSet().length != ids.length ||
      ids.any(
        (id) =>
            !businessItems(sources['files']).any((file) => file['id'] == id),
      ))
    _fail(
      'Ein bis zwanzig unterschiedliche geschützte Personaloriginale auswählen.',
    );
  final body = <String, dynamic>{
    'employee_id': employeeId,
    'employee_revision': sources['employee']['revision'],
    'kind': kind,
    'revision': previous?['revision'] ?? 0,
    'status': 'active',
    'details': <String, dynamic>{},
    'source_file_ids': List<String>.from(ids)..sort(),
    'confirmed': true,
  };
  if (previous != null) {
    payrollFactRecord(previous, employeeId, kind: kind);
    body.addAll({
      'id': previous['id'],
      'correction_reason': _text(
        values['correction_reason'],
        'Korrekturgrund',
        1000,
      ),
    });
  }
  if (kind == 'employment_terms') {
    final from = payrollFactDate(values['employment_from'])!,
        to = payrollFactDate(values['employment_to'], optional: true);
    if (to != null && to.compareTo(from) < 0)
      _fail('Das Beschäftigungsende darf nicht vor dem Beginn liegen.');
    if (from != sources['employee']['employment_from'] ||
        to != sources['employee']['employment_to'])
      _fail(
        'Beschäftigungsdaten zuerst mit dem aktuellen Personalstamm abgleichen.',
      );
    if (!payrollProration.containsKey(values['proration_method']))
      _fail('Die belegte Teilentgeltmethode ausdrücklich wählen.');
    body['details'] = {
      'employment_from': from,
      'employment_to': to,
      'agreement_refs': _selection(
        sources['agreements'],
        values['agreement_ids'],
        employeeId,
        'Entgeltvereinbarungen',
      ),
      'proration_method': values['proration_method'],
      'reason': _text(values['reason'], 'Vertragsgrund'),
    };
  } else if (kind == 'work_schedule') {
    final month = payrollFactMonth(values['month']),
        dates = payrollFactDates(month),
        rawDays = values['days'];
    if (rawDays is! List || rawDays.length != dates.length)
      _fail(
        'Jeden Kalendertag des Monats einschließlich arbeitsfreier Tage ausdrücklich belegen.',
      );
    final days = <Map<String, dynamic>>[];
    for (var i = 0; i < dates.length; i++) {
      final day = businessMap(rawDays[i]), seconds = day['scheduled_seconds'];
      if (day['date'] != dates[i] ||
          seconds is! int ||
          seconds < 0 ||
          seconds > 86400 ||
          !payrollFactStates.containsKey(day['federal_state']))
        _fail(
          'Arbeitsplan mit eindeutigen Tagen, Sollzeiten und Bundesländern vervollständigen.',
        );
      days.add({
        'date': day['date'],
        'scheduled_seconds': seconds,
        'workplace': seconds > 0
            ? _text(day['workplace'], 'Arbeitsort', 500)
            : '${day['workplace'] ?? ''}'.trim(),
        'federal_state': day['federal_state'],
      });
    }
    body['details'] = {
      'month': month,
      'days': days,
      'reason': _text(values['reason'], 'Arbeitsplangrund'),
    };
  } else {
    final month = payrollFactMonth(values['month']);
    final preparation = _selection(
      sources['preparations'],
      [values['preparation_id']],
      employeeId,
      'Monatsvorbereitung',
    ).single;
    if (businessItems(sources['preparations'])
            .firstWhere((p) => p['id'] == preparation['id'])['month'] !=
        month)
      _fail('Die HR-Vorbereitung gehört zu einem anderen Monat.');
    final terms = _selection(
      sources['facts'],
      [values['employment_terms_id']],
      employeeId,
      'Beschäftigungsnachweis',
      kind: 'employment_terms',
    ).single;
    final scheduleId = '${values['work_schedule_id'] ?? ''}',
        schedule = scheduleId.isEmpty
            ? null
            : _selection(
                sources['facts'],
                [scheduleId],
                employeeId,
                'Arbeitsplan',
                kind: 'work_schedule',
              ).single;
    if (schedule != null &&
        businessItems(sources['facts']).firstWhere(
              (f) => f['id'] == schedule['id'],
            )['details']['month'] !=
            month)
      _fail('Der Arbeitsplan gehört zu einem anderen Monat.');
    if (values['tax_treatment'] != 'domestic_running_wages')
      _fail('Die steuerliche Einordnung ausdrücklich bestätigen.');
    final decisions = <Map<String, dynamic>>[];
    for (final value in businessItems(values['entitlement_decisions'] ?? [])) {
      if (!payrollEntitlements.containsKey(value['kind']))
        _fail('Anspruchsart ausdrücklich wählen.');
      final from = payrollFactDate(value['from'])!,
          to = payrollFactDate(value['to'])!,
          files = value['source_file_ids'];
      if (from.compareTo(to) > 0 ||
          !from.startsWith(month) ||
          !to.startsWith(month) ||
          value['source_absence_id'] != null &&
              !_id.hasMatch('${value['source_absence_id']}'))
        _fail('Anspruchszeitraum und Abwesenheitsquelle prüfen.');
      if (value['source_absence_id'] != null &&
          !businessItems(sources['absences']).any(
            (item) =>
                item['id'] == value['source_absence_id'] &&
                (item['start_date'] as String).compareTo(from) <= 0 &&
                (item['end_date'] as String).compareTo(to) >= 0,
          )) {
        _fail(
          'Die Anspruchszeit liegt nicht in der gewählten genehmigten Abwesenheit dieses Mitarbeiters.',
        );
      }
      if (files is! List ||
          files.isEmpty ||
          files.toSet().length != files.length ||
          files.any((id) => !ids.contains(id)))
        _fail(
          'Anspruchsoriginale zusätzlich unter den gesamten Personaloriginalen auswählen.',
        );
      decisions.add({
        'kind': value['kind'],
        'from': from,
        'to': to,
        'source_absence_id': value['source_absence_id'],
        'source_file_ids': List<String>.from(files)..sort(),
        'reason': _text(value['reason'], 'Anspruchsgrund'),
      });
    }
    decisions.sort(
      (a, b) => '${a['from']}${a['to']}${a['kind']}'.compareTo(
        '${b['from']}${b['to']}${b['kind']}',
      ),
    );
    body['details'] = {
      'month': month,
      'preparation_ref': preparation,
      'employment_terms_ref': terms,
      'work_schedule_ref': schedule,
      'profile_refs': _selection(
        sources['profiles'],
        values['profile_ids'],
        employeeId,
        'Lohnprofile',
      ),
      'identity_refs': _selection(
        sources['identities'],
        values['identity_ids'],
        employeeId,
        'Identitätsnachweise',
      ),
      'tax_treatment': values['tax_treatment'],
      'entitlement_decisions': decisions,
      'verification_note': _text(values['verification_note'], 'Prüfvermerk'),
    };
  }
  return body;
}

Map<String, dynamic> payrollFactPreviewInput(Map<String, dynamic> body) {
  if (body['kind'] != 'period_case')
    _fail('Eine Periodenvorschau benötigt einen Monatsfall.');
  return _copy({
    for (final key in [
      'employee_id',
      'employee_revision',
      'details',
      'source_file_ids',
    ])
      key: body[key],
  });
}

Map<String, dynamic> payrollFactPreview(
  dynamic raw,
  Map<String, dynamic> body,
) {
  final value = businessMap(raw),
      snapshot = businessMap(value['source_snapshot']),
      d = businessMap(body['details']);
  final profileRefs = businessItems(snapshot['profiles'])
          .map(payrollFactRef)
          .toList(),
      identityRefs = businessItems(snapshot['identities'])
          .map(payrollFactRef)
          .toList();
  final fileIds = businessItems(
        snapshot['source_files'],
      ).map((f) => '${f['id']}').toList()..sort(),
      selectedFiles = List<String>.from(body['source_file_ids'])..sort();
  if (value['employee_id'] != body['employee_id'] ||
      value['month'] != d['month'] ||
      !_hash.hasMatch('${value['source_hash']}') ||
      !_hash.hasMatch('${value['preview_hash']}') ||
      snapshot['schema_version'] != 1 ||
      snapshot['employee_id'] != body['employee_id'] ||
      snapshot['month'] != d['month'] ||
      !payrollFactsSame(snapshot['case_details'], d) ||
      !payrollFactsSame(
        payrollFactRef(snapshot['preparation']),
        d['preparation_ref'],
      ) ||
      !payrollFactsSame(
        payrollFactRef(snapshot['employment_terms']),
        d['employment_terms_ref'],
      ) ||
      !payrollFactsSame(
        snapshot['work_schedule'] == null
            ? null
            : payrollFactRef(snapshot['work_schedule']),
        d['work_schedule_ref'],
      ) ||
      !payrollFactsSame(profileRefs, d['profile_refs']) ||
      !payrollFactsSame(identityRefs, d['identity_refs']) ||
      !payrollFactsSame(fileIds, selectedFiles) ||
      value['plan'] is! Map ||
      value['plan']['blockers'] is! List ||
      [
        'can_confirm',
        'can_calculate',
        'can_write',
        'can_approve',
        'writes_enabled',
      ].any((key) => value[key] is! bool) ||
      value['can_calculate'] == true &&
          (value['can_confirm'] != true ||
              businessItems(value['plan']['blockers']).isNotEmpty))
    _fail(
      'Die Periodenvorschau ist nicht an die ausdrücklich ausgewählten Monatsquellen gebunden.',
    );
  for (final source in [
    ...businessItems(snapshot['profiles']),
    ...businessItems(snapshot['identities']),
    businessMap(snapshot['preparation']),
    businessMap(snapshot['employment_terms']),
    if (snapshot['work_schedule'] != null)
      businessMap(snapshot['work_schedule']),
    ...businessItems(snapshot['source_files']),
  ]) {
    if (source['employee_id'] != body['employee_id'])
      _fail('Die Periodenvorschau enthält eine fremde Personalquelle.');
  }
  return value;
}

void Function(dynamic) payrollFactValidator(
  Map<String, dynamic> body, {
  Map<String, dynamic>? previous,
  Map<String, dynamic>? preview,
}) {
  final frozen = _copy(body),
      prior = previous == null ? null : _copy(previous),
      proof = preview == null ? null : _copy(preview);
  return (raw) {
    final value = payrollFactRecord(
      raw,
      frozen['employee_id'],
      kind: frozen['kind'],
    );
    if (value['revision'] != frozen['revision'] + 1 ||
        frozen['id'] != null && value['id'] != frozen['id'] ||
        value['previous_hash'] != prior?['content_hash'] ||
        value['status'] != frozen['status'] ||
        !payrollFactsSame(value['details'], frozen['details']) ||
        !payrollFactsSame(
          value['source_file_ids'],
          frozen['source_file_ids'],
        ) ||
        value['correction_reason'] != (frozen['correction_reason'] ?? '') ||
        frozen['kind'] == 'period_case' &&
            value['preview_hash'] != frozen['preview_hash'] ||
        frozen['status'] == 'void' &&
            (prior == null ||
                !payrollFactsSame(value['sources'], prior['sources']) ||
                value['source_hash'] != prior['source_hash'] ||
                !payrollFactsSame(value['plan'], prior['plan'])) ||
        proof != null &&
            (!payrollFactsSame(value['sources'], proof['source_snapshot']) ||
                value['source_hash'] != proof['source_hash'] ||
                !payrollFactsSame(value['plan'], proof['plan'])))
      _fail(
        'Die Bestätigung passt nicht zum geprüften Faktenauftrag. Die ursprüngliche Anfrage bleibt erhalten.',
      );
  };
}

Map<String, dynamic> payrollFactRunInput(Map<String, dynamic> fact) {
  payrollFactRecord(fact, fact['employee_id'], kind: 'period_case');
  if (fact['status'] != 'active')
    _fail('Ein aufgehobener Monatsfall kann keine neue Abrechnung begründen.');
  if (fact['plan']['can_calculate'] != true ||
      businessItems(fact['plan']['blockers']).isNotEmpty) {
    _fail('Der bestätigte Monatsfall ist noch nicht vollständig berechenbar.');
  }
  return {
    'source_schema_version': 2,
    'employee_id': fact['employee_id'],
    'period_case_ref': payrollFactRef(fact),
  };
}

class PayrollPeriodPlanView extends StatelessWidget {
  const PayrollPeriodPlanView({super.key, required this.plan});
  final Map<String, dynamic> plan;
  String money(dynamic value) => value is int
      ? '${value ~/ 100},${(value.abs() % 100).toString().padLeft(2, '0')} €'
      : 'Nicht ermittelt';
  Widget line(String title, String value) =>
      ListTile(dense: true, title: Text(title), subtitle: Text(value));
  @override
  Widget build(BuildContext context) => Column(
    crossAxisAlignment: CrossAxisAlignment.start,
    children: [
      for (final item in businessItems(plan['employment_intervals']))
        ExpansionTile(
          title: const Text('Beschäftigung'),
          children: [
            line(
              'Belegter Zeitraum',
              '${businessDate(item['start'])} – ${businessDate(item['end'])}',
            ),
            line('Kalendertage der Beschäftigung', '${item['calendar_days']}'),
          ],
        ),
      for (final item in businessItems(plan['earnings']))
        ExpansionTile(
          title: Text('Entgeltanspruch · ${money(item['gross_minor'])}'),
          children: [
            line(
              'Belegte Teilentgeltmethode',
              payrollProration[item['proration_method']] ??
                  '${item['proration_method']}',
            ),
            line(
              'Belegte Entgeltquote',
              '${item['numerator']} / ${item['denominator']}',
            ),
            if (item['approved_work_seconds'] != null)
              line(
                'Freigegebene tatsächliche Arbeitszeit',
                '${item['approved_work_seconds']} Sekunden',
              ),
          ],
        ),
      for (final item in businessItems(plan['tax_periods']))
        ExpansionTile(
          title: const Text('Steuerzeitraum'),
          children: [
            line(
              'Belegter Zeitraum',
              '${businessDate(item['start'])} – ${businessDate(item['end'])}',
            ),
            line(
              'Lohnzahlungszeitraum',
              item['lzz'] == 2
                  ? 'Monat'
                  : item['lzz'] == 4
                  ? 'Tägliche Berechnung'
                  : 'Gesonderter Zeitraum',
            ),
            line('Steuertage', '${item['tax_days']}'),
            for (final entry in const {
              'gross_minor': 'Tatsächliches Steuerbrutto',
              'pap_gross_minor': 'Bruttoeingabe an den Tages-PAP',
              'gross_remainder_minor': 'Rest der täglichen Bruttoaufteilung',
              'pap_allowance_minor': 'PAP-Freibetrag',
              'pap_addition_minor': 'PAP-Hinzurechnung',
            }.entries)
              if (item['inputs']?[entry.key] != null)
                line(entry.value, money(item['inputs'][entry.key])),
          ],
        ),
      for (final item in businessItems(plan['social_periods']))
        ExpansionTile(
          title: const Text('Sozialversicherung'),
          children: [
            line(
              'Belegter Zeitraum',
              '${businessDate(item['start'])} – ${businessDate(item['end'])}',
            ),
            line('SV-Tage', '${item['days']}'),
            line(
              'Vollständiger Beitragsmonat',
              item['full_month'] == true ? 'Ja' : 'Nein',
            ),
            for (final entry in const {
              'health_minor': 'Krankenversicherung',
              'care_minor': 'Pflegeversicherung',
              'pension_minor': 'Rentenversicherung',
              'unemployment_minor': 'Arbeitslosenversicherung',
            }.entries)
              if (item['caps']?[entry.key] != null)
                line(
                  'Teil-BBG · ${entry.value}',
                  money(item['caps'][entry.key]),
                ),
            if (item['minimum_pension_basis_minor'] != null)
              line(
                'RV-Mindestbasis',
                money(item['minimum_pension_basis_minor']),
              ),
          ],
        ),
      if (businessItems(plan['blockers'] ?? const []).isEmpty)
        const Notice(
          'Für diesen Periodenplan sind keine offenen Punkte ausgewiesen. Die eigentliche Lohnberechnung wird gesondert geprüft.',
        ),
      for (final item in businessItems(plan['blockers'] ?? const []))
        Notice('${item['message'] ?? item['explanation'] ?? item['code']}'),
    ],
  );
}

class BusinessPayrollFactsPage extends StatefulWidget {
  const BusinessPayrollFactsPage({
    super.key,
    required this.session,
    required this.employee,
    required this.onOriginal,
    this.onCalculate,
  });
  final BusinessSession session;
  final Map<String, dynamic> employee;
  final Future<void> Function(Map<String, dynamic>) onOriginal;
  final Future<void> Function(Map<String, dynamic>)? onCalculate;
  @override
  State<BusinessPayrollFactsPage> createState() =>
      _BusinessPayrollFactsPageState();
}

class _BusinessPayrollFactsPageState extends State<BusinessPayrollFactsPage>
    with WidgetsBindingObserver {
  BusinessSession get session => widget.session;
  String get employeeId => widget.employee['id'];
  String get commandKey => 'payroll-facts-$employeeId';
  Map<String, dynamic>? sources, selected, preview, previewBody, correction;
  List<Map<String, dynamic>> history = [];
  String? error, message;
  bool loading = false, busy = false, historical = false;
  int epoch = 0;
  Object? generation;
  bool get readable =>
      session.allowed &&
      session.projectId == null &&
      session.hasFeature('payroll_period_facts') &&
      session.hasModule('payroll_facts') &&
      session.can('personnel.read');
  bool permitted(String kind) =>
      readable &&
      !session.readonly &&
      session.can(
        kind == 'period_case' ? 'personnel.approve' : 'personnel.write',
      );
  bool writable(String kind) =>
      permitted(kind) &&
      session.sectionEnabled('personnel') &&
      sources?['writes_enabled'] == true &&
      sources?[kind == 'period_case' ? 'can_approve' : 'can_write'] == true;
  Map<String, dynamic>? get pending =>
      session.pendingCommandValues(commandKey, path: '/payroll/facts');
  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    session.addListener(changed);
    load();
  }

  @override
  void dispose() {
    epoch++;
    session.removeListener(changed);
    WidgetsBinding.instance.removeObserver(this);
    super.dispose();
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state == AppLifecycleState.hidden ||
        state == AppLifecycleState.paused) {
      epoch++;
      if (mounted)
        setState(() {
          sources = selected = preview = previewBody = correction = null;
          history = [];
          loading = false;
        });
    }
  }

  void changed() {
    if (!mounted) return;
    if (!readable || generation != null && generation != session.generation) {
      epoch++;
      setState(() {
        sources = selected = preview = previewBody = correction = null;
        history = [];
        loading = false;
        generation = session.generation;
      });
    }
  }

  void failed(Object failure) {
    if (!mounted) return;
    setState(() {
      error = failure is ApiException
          ? failure.message
          : failure is FormatException
          ? failure.message
          : 'Der belegte Faktenvorgang konnte nicht abgeschlossen werden.';
      if (failure is ApiException && [401, 403, 404].contains(failure.status)) {
        sources = selected = preview = previewBody = correction = null;
        history = [];
      }
    });
  }

  Future<Map<String, dynamic>> fresh({
    String? kind,
    bool replay = false,
  }) async {
    await session.load();
    if (!mounted ||
        !readable ||
        session.error != null ||
        kind != null && !permitted(kind))
      _fail(
        'Aktuelle globale Personalrechte für diesen Faktenvorgang fehlen.',
        403,
      );
    final captured = session.generation,
        value = payrollFactSources(
          await session.read('/payroll/facts/sources?employee_id=$employeeId'),
          employeeId,
        );
    if (!mounted ||
        !readable ||
        captured != session.generation ||
        kind != null &&
            (!permitted(kind) ||
                value[kind == 'period_case' ? 'can_approve' : 'can_write'] !=
                    true))
      _fail(
        'Die private Ansicht oder Mitarbeiterfreigabe wurde geändert.',
        403,
      );
    if (kind != null &&
        !replay &&
        (!session.sectionEnabled('personnel') ||
            value['writes_enabled'] != true))
      _fail(
        'Neue Lohnfakten sind im deaktivierten Personalbereich gesperrt.',
        423,
      );
    return value;
  }

  Future<void> load() async {
    if (loading) return;
    final captured = ++epoch;
    setState(() {
      loading = true;
      error = null;
    });
    try {
      final value = await fresh();
      if (!mounted || captured != epoch) return;
      setState(() {
        sources = value;
        generation = session.generation;
      });
    } catch (failure) {
      if (captured == epoch) failed(failure);
    } finally {
      if (mounted && captured == epoch) setState(() => loading = false);
    }
  }

  Future<void> act(Future<void> Function() run) async {
    if (busy) return;
    setState(() {
      busy = true;
      error = null;
      message = null;
    });
    try {
      await run();
    } catch (failure) {
      failed(failure);
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  Future<void> inspect(Map<String, dynamic> fact, {bool old = false}) async {
    final value = payrollFactRecord(fact, employeeId), current = await fresh();
    if (!mounted) return;
    setState(() {
      sources = current;
      selected = _copy(value);
      historical = old;
      preview = previewBody = correction = null;
      history = [];
    });
  }

  Future<void> repeat() => act(() async {
    await session.repeatPayrollFactsCommand(employeeId);
    if (!mounted || !readable) return;
    setState(() {
      message = 'Der ursprüngliche Faktenauftrag ist bestätigt.';
      preview = previewBody = correction = null;
    });
    await load();
  });
  Future<void> save(
    Map<String, dynamic> body, {
    Map<String, dynamic>? previous,
    Map<String, dynamic>? proof,
  }) async {
    await fresh(kind: body['kind']);
    if (pending != null)
      _fail(
        'Zuerst den unbestätigten ursprünglichen Faktenauftrag klären.',
        409,
      );
    final value = payrollFactRecord(
      await session.command(
        commandKey,
        '/payroll/facts',
        body,
        validateResult: payrollFactValidator(
          body,
          previous: previous,
          preview: proof,
        ),
      ),
      employeeId,
    );
    if (!mounted || !readable) return;
    await inspect(value);
  }

  Map<String, String> choices(
    dynamic items,
    String Function(Map<String, dynamic>) title, {
    bool empty = true,
  }) => {
    if (empty) '': 'Bitte ausdrücklich auswählen',
    for (final item in businessItems(items))
      '${item['id']}':
          '${title(item)} · ${item['revision'] == null ? 'Original' : 'Fassung ${item['revision']}'}',
  };
  List<BusinessField> fileFields(
    Map<String, dynamic> page,
    Map<String, dynamic>? previous,
  ) {
    final files = businessItems(page['files']),
        replaced = files
            .map((f) => f['supersedes'])
            .whereType<String>()
            .toSet();
    return [
      BusinessField(
        'source_file_ids',
        'Geschützte Personaloriginale dieses Nachweises',
        type: BusinessInput.multiple,
        required: true,
        choices: {
          for (final file in files.where((f) => !replaced.contains(f['id'])))
            '${file['id']}': '${file['filename']}',
        },
      ),
      if (previous != null)
        const BusinessField(
          'correction_reason',
          'Nachvollziehbarer Korrekturgrund',
          required: true,
        ),
      const BusinessField(
        'confirmed',
        'Ich bestätige die ausdrücklich gewählten Quellen und die belegten Angaben.',
        type: BusinessInput.toggle,
      ),
    ];
  }

  Future<Map<String, dynamic>?> choose(
    String title,
    List<BusinessField> fields, {
    Map<String, dynamic> initial = const {},
  }) async {
    Map<String, dynamic>? values;
    await showDialog<bool>(
      context: context,
      builder: (_) => BusinessEditor(
        session: session,
        title: title,
        fields: fields,
        initial: initial,
        readPermission: 'personnel.read',
        readAllowed: () => readable,
        saveLabel: 'Weiter',
        onSave: (input) async {
          values = _copy(input);
        },
      ),
    );
    return mounted && readable ? values : null;
  }

  Future<void> edit(String kind, [Map<String, dynamic>? previous]) async {
    if (busy || pending != null) return;
    Map<String, dynamic> page;
    try {
      page = await fresh(kind: kind);
    } catch (failure) {
      failed(failure);
      return;
    }
    if (!mounted) return;
    final d = businessMap(previous?['details']),
        initial = <String, dynamic>{
          'source_file_ids': previous?['source_file_ids'] ?? <String>[],
          'confirmed': false,
        },
        fields = <BusinessField>[];
    var count = 0;
    String? month;
    if (kind == 'employment_terms') {
      initial.addAll({
        ...d,
        'agreement_ids': businessItems(d['agreement_refs'] ?? const [])
            .map((r) => r['id'])
            .toList(),
      });
      fields.addAll([
        const BusinessField(
          'employment_from',
          'Belegter Beschäftigungsbeginn',
          type: BusinessInput.date,
          required: true,
        ),
        const BusinessField(
          'employment_to',
          'Belegtes Beschäftigungsende, falls vorhanden',
          type: BusinessInput.date,
        ),
        BusinessField(
          'agreement_ids',
          'Gültige Entgeltvereinbarungen',
          type: BusinessInput.multiple,
          required: true,
          choices: choices(
            page['agreements'],
            (a) => businessDate(a['effective_from']),
            empty: false,
          ),
        ),
        const BusinessField(
          'proration_method',
          'Vertraglich belegte Teilentgeltmethode',
          type: BusinessInput.choice,
          required: true,
          choices: {'': 'Methode ausdrücklich auswählen', ...payrollProration},
        ),
        const BusinessField(
          'reason',
          'Vertragliche Grundlage der Entgeltaufteilung',
          required: true,
        ),
      ]);
    } else if (kind == 'work_schedule') {
      final values = previous == null
          ? await choose('Arbeitsplanmonat wählen', [
              const BusinessField(
                'month',
                'Belegter Kalendermonat (JJJJ-MM)',
                required: true,
              ),
            ])
          : {'month': d['month']};
      if (values == null || !mounted) return;
      try {
        month = payrollFactMonth(values['month']);
      } catch (failure) {
        failed(failure);
        return;
      }
      final days = payrollFactDates(month),
          oldDays = businessItems(d['days'] ?? const []);
      for (var i = 0; i < days.length; i++) {
        final day = days[i],
            old = oldDays.where((v) => v['date'] == day).firstOrNull;
        initial.addAll({
          'time_$i': old == null
              ? ''
              : payrollFactTime(old['scheduled_seconds']),
          'workplace_$i': old?['workplace'] ?? '',
          'state_$i': old?['federal_state'] ?? '',
        });
        fields.addAll([
          BusinessField(
            'time_$i',
            '${businessDate(day)} · Sollzeit (HH:MM)',
            required: true,
            hint: 'Auch bekannte arbeitsfreie Tage ausdrücklich mit 00:00 belegen.',
          ),
          BusinessField('workplace_$i', '${businessDate(day)} · Arbeitsort'),
          BusinessField(
            'state_$i',
            '${businessDate(day)} · Feiertagsregion',
            type: BusinessInput.choice,
            required: true,
            choices: const {
              '': 'Region ausdrücklich wählen',
              ...payrollFactStates,
            },
          ),
        ]);
      }
      initial['reason'] = d['reason'] ?? '';
      fields.add(
        const BusinessField(
          'reason',
          'Beleggrund des vollständigen Arbeitsplans',
          required: true,
        ),
      );
    } else {
      final chosen = await choose(
        'Anspruchs- und Unterbrechungsfälle',
        [
          const BusinessField(
            'decision_count',
            'Anzahl ausdrücklich belegter Anspruchs-/Unterbrechungsfälle',
            type: BusinessInput.integer,
            required: true,
            hint: '0 nur bei geprüftem gewöhnlichem Fall. Vorhandene genehmigte Abwesenheiten bleiben serverseitig prüfpflichtig.',
          ),
        ],
        initial: {
          'decision_count': businessItems(
            d['entitlement_decisions'] ?? const [],
          ).length,
        },
      );
      if (chosen == null || !mounted) return;
      count = chosen['decision_count'] is int
          ? chosen['decision_count']
          : int.tryParse('${chosen['decision_count']}') ?? -1;
      if (count < 0 || count > 31) {
        failed(
          const FormatException(
            'Zwischen null und 31 belegte Anspruchsfälle angeben.',
          ),
        );
        return;
      }
      initial.addAll({
        ...d,
        'preparation_id': d['preparation_ref']?['id'] ?? '',
        'employment_terms_id': d['employment_terms_ref']?['id'] ?? '',
        'work_schedule_id': d['work_schedule_ref']?['id'] ?? '',
        'profile_ids': businessItems(d['profile_refs'] ?? const [])
            .map((r) => r['id'])
            .toList(),
        'identity_ids': businessItems(d['identity_refs'] ?? const [])
            .map((r) => r['id'])
            .toList(),
      });
      fields.addAll([
        const BusinessField(
          'month',
          'Belegter Abrechnungsmonat (JJJJ-MM)',
          required: true,
        ),
        BusinessField(
          'preparation_id',
          'Abgeschlossene HR-Monatsvorbereitung',
          type: BusinessInput.choice,
          required: true,
          choices: choices(page['preparations'], (p) => '${p['month']}'),
        ),
        BusinessField(
          'employment_terms_id',
          'Belegter Beschäftigungsnachweis',
          type: BusinessInput.choice,
          required: true,
          choices: choices(
            businessItems(page['facts'])
                .where(
                  (f) =>
                      f['kind'] == 'employment_terms' &&
                      f['status'] == 'active',
                )
                .toList(),
            (f) => businessDate(f['effective_from']),
          ),
        ),
        BusinessField(
          'work_schedule_id',
          'Datierter Arbeitsplan, falls für die Methode erforderlich',
          type: BusinessInput.choice,
          choices: choices(
            businessItems(page['facts'])
                .where(
                  (f) =>
                      f['kind'] == 'work_schedule' && f['status'] == 'active',
                )
                .toList(),
            (f) => '${f['details']['month']}',
            empty: false,
          ),
        ),
        BusinessField(
          'profile_ids',
          'Alle einschlägigen gültigen Lohnprofile',
          type: BusinessInput.multiple,
          required: true,
          choices: choices(
            page['profiles'],
            (p) => businessDate(p['profile']['effective_from']),
            empty: false,
          ),
        ),
        BusinessField(
          'identity_ids',
          'Alle einschlägigen Lohnkonto-Stammnachweise',
          type: BusinessInput.multiple,
          required: true,
          choices: choices(
            page['identities'],
            (p) => 'Stammnachweis',
            empty: false,
          ),
        ),
        const BusinessField(
          'tax_treatment',
          'Belegte steuerliche Einordnung',
          type: BusinessInput.choice,
          required: true,
          choices: {
            '': 'Bitte ausdrücklich auswählen',
            'domestic_running_wages': 'Inländischer laufender Arbeitslohn',
          },
        ),
        const BusinessField(
          'verification_note',
          'Prüfvermerk zu Beschäftigung, Merkmalen und Anspruch',
          required: true,
        ),
      ]);
      final old = businessItems(d['entitlement_decisions'] ?? const []);
      for (var i = 0; i < count; i++) {
        final item = i < old.length ? old[i] : <String, dynamic>{};
        for (final key in [
          'kind',
          'from',
          'to',
          'source_absence_id',
          'source_file_ids',
          'reason',
        ])
          initial['claim_${i}_$key'] =
              item[key] ?? (key == 'source_file_ids' ? <String>[] : '');
        fields.addAll([
          BusinessField(
            'claim_${i}_kind',
            'Anspruch ${i + 1} · Art',
            type: BusinessInput.choice,
            required: true,
            choices: const {
              '': 'Art ausdrücklich wählen',
              ...payrollEntitlements,
            },
          ),
          BusinessField(
            'claim_${i}_from',
            'Anspruch ${i + 1} · Von',
            type: BusinessInput.date,
            required: true,
          ),
          BusinessField(
            'claim_${i}_to',
            'Anspruch ${i + 1} · Bis',
            type: BusinessInput.date,
            required: true,
          ),
          BusinessField(
            'claim_${i}_source_absence_id',
            'Anspruch ${i + 1} · Genehmigte Abwesenheit, falls vorhanden',
            type: BusinessInput.choice,
            choices: choices(
              page['absences'],
              (a) =>
                  '${businessDate(a['start_date'])} – ${businessDate(a['end_date'])} · ${a['kind']}',
              empty: false,
            ),
          ),
          BusinessField(
            'claim_${i}_source_file_ids',
            'Anspruch ${i + 1} · Geschützte Originale',
            type: BusinessInput.multiple,
            required: true,
            choices: choices(
              page['files'],
              (f) => '${f['filename']}',
              empty: false,
            ),
          ),
          BusinessField(
            'claim_${i}_reason',
            'Anspruch ${i + 1} · Belegter Grund',
            required: true,
          ),
        ]);
      }
    }
    fields.addAll(fileFields(page, previous));
    final captured = session.generation,
        chosenMonth = month,
        claimCount = count;
    Map<String, dynamic>? nextBody, nextPreview;
    await showDialog<bool>(
      context: context,
      builder: (_) => BusinessEditor(
        session: session,
        title:
            '${previous == null ? 'Erfassen' : 'Korrigieren'}: ${payrollFactKinds[kind]}',
        fields: fields,
        initial: initial,
        readPermission: 'personnel.read',
        writePermission: kind == 'period_case'
            ? 'personnel.approve'
            : 'personnel.write',
        readAllowed: () => readable,
        pendingKey: kind == 'period_case' ? null : commandKey,
        saveLabel: kind == 'period_case'
            ? 'Periodenplan unverbindlich prüfen'
            : 'Belegten Nachweis speichern',
        onSave: (values) async {
          if (pending != null && kind != 'period_case') {
            await session.repeatPayrollFactsCommand(employeeId);
            return;
          }
          if (values['confirmed'] != true)
            _fail('Die belegten Quellen und Angaben ausdrücklich bestätigen.');
          await fresh(kind: kind);
          if (captured != session.generation)
            _fail(
              'Der freigegebene Quellenstand wurde geändert. Bitte den Vorgang erneut öffnen.',
              409,
            );
          final input = _copy(values);
          if (kind == 'work_schedule')
            input.addAll({
              'month': chosenMonth,
              'days': [
                for (final entry in payrollFactDates(chosenMonth!).indexed)
                  {
                    'date': entry.$2,
                    'scheduled_seconds': payrollFactSeconds(
                      values['time_${entry.$1}'],
                    ),
                    'workplace': values['workplace_${entry.$1}'] ?? '',
                    'federal_state': values['state_${entry.$1}'] ?? '',
                  },
              ],
            });
          if (kind == 'period_case')
            input['entitlement_decisions'] = [
              for (var i = 0; i < claimCount; i)
                {
                  for (final key in [
                    'kind',
                    'from',
                    'to',
                    'source_file_ids',
                    'reason',
                  ])
                    key: values['claim_${i}_$key'],
                  'source_absence_id':
                      (values['claim_${i}_source_absence_id'] ?? '') == ''
                      ? null
                      : values['claim_${i}_source_absence_id'],
                },
            ];
          final body = payrollFactInput(
            employeeId,
            page,
            kind,
            input,
            previous: previous,
          );
          if (kind == 'period_case') {
            nextPreview = payrollFactPreview(
              await session.api.call(
                session.path('/payroll/periods/preview'),
                payrollFactPreviewInput(body),
              ),
              body,
            );
            nextBody = {...body, 'preview_hash': nextPreview!['preview_hash']};
          } else {
            await save(body, previous: previous);
          }
        },
      ),
    );
    if (!mounted || !readable || captured != session.generation) return;
    if (nextPreview != null && nextBody != null)
      setState(() {
        preview = nextPreview;
        previewBody = nextBody;
        correction = previous == null ? null : _copy(previous);
        selected = null;
        history = [];
      });
    else
      await load();
  }

  Future<void> confirm() async {
    if (preview == null ||
        previewBody == null ||
        !writable('period_case') ||
        pending != null)
      return;
    final proof = _copy(preview!),
        body = _copy(previewBody!),
        previous = correction == null ? null : _copy(correction!);
    if (!await businessConfirm(
      context,
      title: 'Geprüften Fallnachweis festhalten',
      message: 'Ich bestätige genau diesen Periodenplan und seine Quellen. Eine Lohnberechnung, Zahlung oder Meldung erfolgt dadurch nicht.',
      action: 'Fallnachweis festhalten',
    ))
      return;
    await act(() async {
      await save(body, previous: previous, proof: proof);
    });
  }

  Future<void> cancel(Map<String, dynamic> fact) async {
    if (pending != null) return;
    Map<String, dynamic> page;
    try {
      page = await fresh(kind: fact['kind']);
    } catch (failure) {
      failed(failure);
      return;
    }
    if (!mounted) return;
    await showDialog<bool>(
      context: context,
      builder: (_) => BusinessEditor(
        session: session,
        title: 'Fälschlichen Faktennachweis aufheben',
        fields: const [
          BusinessField(
            'correction_reason',
            'Belegter Grund für die Aufhebung',
            required: true,
          ),
          BusinessField(
            'confirmed',
            'Ich bestätige die Aufhebung dieses Nachweises; historische Abrechnungen bleiben unverändert.',
            type: BusinessInput.toggle,
          ),
        ],
        readPermission: 'personnel.read',
        writePermission: fact['kind'] == 'period_case'
            ? 'personnel.approve'
            : 'personnel.write',
        readAllowed: () => readable,
        pendingKey: commandKey,
        saveLabel: 'Aufhebung belegt festhalten',
        onSave: (values) async {
          if (pending != null) {
            await session.repeatPayrollFactsCommand(employeeId);
            return;
          }
          if (values['confirmed'] != true)
            _fail('Die belegte Aufhebung ausdrücklich bestätigen.');
          final body = <String, dynamic>{
            'employee_id': employeeId,
            'employee_revision': page['employee']['revision'],
            'kind': fact['kind'],
            'revision': fact['revision'],
            'id': fact['id'],
            'status': 'void',
            'details': _copy(fact['details']),
            'source_file_ids': List<String>.from(fact['source_file_ids']),
            'confirmed': true,
            'correction_reason': _text(
              values['correction_reason'],
              'Aufhebungsgrund',
              1000,
            ),
            if (fact['kind'] == 'period_case')
              'preview_hash': fact['preview_hash'],
          };
          await save(body, previous: fact);
        },
      ),
    );
    if (mounted && readable) await load();
  }

  Future<void> showHistory(Map<String, dynamic> fact) => act(() async {
    await fresh();
    final captured = epoch,
        raw = businessMap(
          await session.read('/payroll/facts/${fact['id']}/history'),
        ),
        items = businessItems(raw['items']);
    if (raw['employee_id'] != employeeId ||
        items.asMap().entries.any(
          (entry) =>
              payrollFactRecord(
                    entry.value,
                    employeeId,
                    kind: fact['kind'],
                  )['id'] !=
                  fact['id'] ||
              entry.value['revision'] != entry.key + 1,
        ))
      _fail('Die Historie gehört nicht zum ausgewählten Faktennachweis.');
    if (mounted && readable && captured == epoch)
      setState(() => history = items);
  });
  Widget details(Map<String, dynamic> value) {
    final d = businessMap(value['details']);
    if (value['kind'] == 'period_case')
      return Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text('${d['verification_note']}'),
          PayrollPeriodPlanView(plan: businessMap(value['plan'])),
        ],
      );
    if (value['kind'] == 'work_schedule')
      return ExpansionTile(
        title: Text('Arbeitsplan · ${d['month']}'),
        subtitle: Text('${d['reason']}'),
        children: [
          for (final day in businessItems(d['days'] ?? const []))
            ListTile(
              title: Text(
                '${businessDate(day['date'])} · ${payrollFactTime(day['scheduled_seconds'])}',
              ),
              subtitle: Text(
                '${day['workplace'] == '' ? 'Arbeitsfrei' : day['workplace']} · ${payrollFactStates[day['federal_state']]}',
              ),
            ),
        ],
      );
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          'Beschäftigung: ${businessDate(d['employment_from'])} bis ${d['employment_to'] == null ? 'kein belegtes Ende' : businessDate(d['employment_to'])}',
        ),
        Text('Teilentgeltmethode: ${payrollProration[d['proration_method']]}'),
        Text('${d['reason']}'),
      ],
    );
  }

  Widget factCard(Map<String, dynamic> value) => Card(
    child: Padding(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            '${payrollFactKinds[value['kind']]} · Fassung ${value['revision']}',
            style: Theme.of(context).textTheme.titleMedium,
          ),
          Text(
            value['status'] == 'void'
                ? 'Nachweis aufgehoben; Historie bleibt erhalten.'
                : 'Aktiver belegter Nachweis',
          ),
          if ('${value['correction_reason'] ?? ''}'.isNotEmpty)
            Text('Korrekturgrund: ${value['correction_reason']}'),
          details(value),
          for (final id in List<String>.from(value['source_file_ids']))
            Builder(
              builder: (context) {
                final file = [
                  ...businessItems(sources?['files'] ?? const []),
                  ...businessItems(value['sources']?['source_files']),
                ].where((f) => f['id'] == id).firstOrNull;
                return file == null
                    ? const SizedBox.shrink()
                    : TextButton(
                        onPressed: busy
                            ? null
                            : () => act(() async {
                                await fresh();
                                await widget.onOriginal(file);
                              }),
                        child: Text('Personaloriginal: ${file['filename']}'),
                      );
              },
            ),
          if (!historical)
            OutlinedButton(
              onPressed: busy ? null : () => showHistory(value),
              child: const Text('Faktenhistorie öffnen'),
            ),
          if (!historical && writable(value['kind']) && pending == null)
            Wrap(
              spacing: 12,
              runSpacing: 8,
              children: [
                OutlinedButton(
                  onPressed: busy ? null : () => edit(value['kind'], value),
                  child: const Text('Nachweis korrigieren'),
                ),
                if (value['status'] == 'active')
                  OutlinedButton(
                    onPressed: busy ? null : () => cancel(value),
                    child: const Text('Fälschlichen Nachweis aufheben'),
                  ),
              ],
            ),
          if (value['kind'] == 'period_case' &&
              value['status'] == 'active' &&
              value['plan']['can_calculate'] == true &&
              businessItems(value['plan']['blockers']).isEmpty &&
              widget.onCalculate != null)
            FilledButton(
              onPressed: busy
                  ? null
                  : () => act(() async {
                      await fresh();
                      await widget.onCalculate!(value);
                    }),
              child: const Text('Lohn aus diesem Fall berechnen'),
            ),
        ],
      ),
    ),
  );
  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(
      title: Text('Lohnzeitachsen · ${widget.employee['name']}'),
      actions: [
        IconButton(
          tooltip: 'Rechte und Quellen aktualisieren',
          onPressed: busy || loading ? null : load,
          icon: const Icon(Icons.refresh),
        ),
      ],
    ),
    body: !readable
        ? const Padding(
            padding: EdgeInsets.all(24),
            child: BusinessEmpty(
              'Lohnzeitachsen nicht freigegeben',
              'Diese privaten Nachweise benötigen aktuelle globale Personal-Leserechte.',
            ),
          )
        : ListView(
            padding: const EdgeInsets.all(20),
            children: [
              const Notice(
                'Belegte Beschäftigung, Entgeltvereinbarungen, Arbeitspläne und Monatsfälle. Gesetzliche Steuer- und SV-Tage werden aus den Quellen berechnet. Hier wird weder gezahlt noch amtlich gemeldet.',
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
                        const Text('Faktenbestätigung noch offen'),
                        const Notice(
                          'Dieser Auftrag kann bereits gespeichert sein. Nur die ursprünglichen Angaben mit derselben Anfragekennung erneut prüfen.',
                        ),
                        if (permitted(pending!['kind']))
                          FilledButton(
                            onPressed: busy ? null : repeat,
                            child: const Text(
                              'Ursprünglichen Faktenauftrag erneut senden',
                            ),
                          ),
                      ],
                    ),
                  ),
                ),
              if (preview != null) ...[
                Text(
                  'Periodenplan prüfen · ${preview!['month']}',
                  style: Theme.of(context).textTheme.titleLarge,
                ),
                Notice(
                  preview!['can_calculate'] == true
                      ? 'Der bestätigte Periodenplan kann anschließend als Quelle einer gesonderten Lohnberechnung gewählt werden.'
                      : 'Dieser Nachweis ist noch nicht vollständig berechenbar. Die offenen Punkte bleiben auch nach dem Speichern bestehen.',
                ),
                PayrollPeriodPlanView(plan: businessMap(preview!['plan'])),
                if (preview!['can_confirm'] == true &&
                    writable('period_case') &&
                    pending == null)
                  FilledButton(
                    onPressed: busy ? null : confirm,
                    child: const Text('Geprüften Fallnachweis festhalten'),
                  ),
              ],
              if (selected != null) factCard(selected!),
              for (final old in history)
                ListTile(
                  title: Text('Historische Fassung ${old['revision']}'),
                  subtitle: Text('${old['correction_reason'] ?? ''}'),
                  onTap: busy ? null : () => act(() => inspect(old, old: true)),
                ),
              for (final kind in payrollFactKinds.entries)
                Card(
                  child: Padding(
                    padding: const EdgeInsets.all(16),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          kind.value,
                          style: Theme.of(context).textTheme.titleMedium,
                        ),
                        if (businessItems(sources?['facts'] ?? const [])
                            .where((f) => f['kind'] == kind.key)
                            .isEmpty)
                          const Notice('Noch kein belegter Nachweis.'),
                        for (final fact in businessItems(
                          sources?['facts'] ?? const [],
                        ).where((f) => f['kind'] == kind.key))
                          ListTile(
                            title: Text(
                              '${fact['details']['month'] ?? businessDate(fact['effective_from'])} · Fassung ${fact['revision']}',
                            ),
                            subtitle: Text(
                              fact['status'] == 'void' ? 'Aufgehoben' : 'Aktiv',
                            ),
                            trailing: const Icon(Icons.chevron_right),
                            onTap: busy ? null : () => act(() => inspect(fact)),
                          ),
                        if (writable(kind.key) && pending == null)
                          FilledButton(
                            onPressed: busy ? null : () => edit(kind.key),
                            child: Text('${kind.value} erfassen'),
                          ),
                      ],
                    ),
                  ),
                ),
              if (sources?['writes_enabled'] == false)
                const Notice(
                  'Das Personalmodul ist deaktiviert. Historische Nachweise und die Klärung bereits angenommener Originalaufträge bleiben zugänglich.',
                ),
            ],
          ),
  );
}

Map<String, dynamic> payrollPeriodCalculation(dynamic raw) {
  final value = businessMap(raw),
      detail = businessMap(value['period_details']),
      complete = value['scope'] != 'unsupported';
  if (value['rule_version'] != 'de_2026_periods_pap_v4' ||
      !_hash.hasMatch('${detail['plan_hash']}') ||
      !_hash.hasMatch('${detail['source_snapshot_hash']}') ||
      ['employment_intervals', 'earnings', 'tax_periods', 'social_periods'].any(
        (key) =>
            detail[key] is! List || complete && (detail[key] as List).isEmpty,
      ))
    _fail(
      'Die Teilmonatsberechnung besitzt keine vollständige Quellen- und Periodenbindung.',
    );
  final month = payrollFactMonth(value['month']);
  for (final key in ['employment_intervals', 'tax_periods', 'social_periods'])
    for (final period in businessItems(detail[key])) {
      final start = payrollFactDate(period['start'])!,
          end = payrollFactDate(period['end'])!;
      if (start.compareTo(end) > 0 ||
          !start.startsWith(month) ||
          !end.startsWith(month))
        _fail('Ein Teilzeitraum gehört nicht zum Abrechnungsmonat.');
    }
  for (final period in businessItems(detail['social_periods']))
    if (period['days'] is! int ||
        period['days'] < 0 ||
        period['days'] > 30 ||
        complete && period['days'] == 0 ||
        period['full_month'] is! bool ||
        [
          'health_minor',
          'care_minor',
          'pension_minor',
          'unemployment_minor',
        ].any((key) => period['caps']?[key] is! int || period['caps'][key] < 0))
      _fail('SV-Tage und Teil-Bemessungsgrenzen sind nicht eindeutig belegt.');
  for (final period in businessItems(detail['tax_periods']))
    if (![2, 4].contains(period['lzz']) ||
        period['tax_days'] is! int ||
        period['tax_days'] < 1 ||
        period['tax_days'] > 31)
      _fail('Der steuerliche Lohnzahlungszeitraum ist nicht eindeutig belegt.');
  if (complete) {
    var sum = 0;
    for (final item in businessItems(detail['earnings'])) {
      if (item['gross_minor'] is! int || item['gross_minor'] < 0)
        _fail('Eine belegte Entgeltposition fehlt.');
      sum += item['gross_minor'] as int;
    }
    if (sum != value['gross_minor'])
      _fail(
        'Die belegten Entgeltpositionen stimmen nicht mit dem Brutto überein.',
      );
  }
  if (complete && '${value['scope']}'.startsWith('regular_')) {
    final tax = businessMap(detail['tax_calculation']),
        care = businessMap(detail['care_adjustments']);
    if (tax['totals']?['LSTLZZ'] != value['individual_wage_tax_minor'] ||
        tax['totals']?['SOLZLZZ'] != value['solidarity_minor'] ||
        [
          'employee_before_adjustments_minor',
          'childless_surcharge_minor',
          'children_discount_minor',
        ].any((key) => care[key] is! int || care[key] < 0) ||
        care['employee_before_adjustments_minor'] +
                care['childless_surcharge_minor'] -
                care['children_discount_minor'] !=
            value['employee_contributions']['care'])
      _fail(
        'Tagessteuern und PV-Anpassungen passen nicht zur Beitragsaufstellung.',
      );
    for (final key in [
      'health_general',
      'health_additional',
      'pension',
      'unemployment',
      'care',
    ]) {
      final b = businessMap(detail['branch_bases']?[key]);
      if (b['total_minor'] is! int ||
          b['employee_minor'] is! int ||
          b['total_minor'] < b['employee_minor'] ||
          b['employee_minor'] < 0)
        _fail(
          'Die getrennten Teilmonats-Beitragsgrundlagen sind unvollständig.',
        );
    }
  }
  if (value['scope'] == 'regular_transition_period') {
    final t = businessMap(detail['transition']);
    if (![
          'within_transition_area',
          'below_or_at_lower_limit',
          'above_upper_limit',
        ].contains(t['regime']) ||
        t['regular_monthly_gross_minor'] is! int ||
        t['regular_monthly_gross_minor'] < 60301 ||
        t['regular_monthly_gross_minor'] > 200000 ||
        !payrollFactsSame(t['branch_bases'], detail['branch_bases']) ||
        !payrollFactsSame(
          t['ratio'],
          detail['social_periods'][0]['transition_ratio'],
        ))
      _fail(
        'Die Teilmonatsprognose ist nicht an die belegte Entgeltquote gebunden.',
      );
  }
  return detail;
}

Map<String, dynamic> payrollPeriodSource(
  dynamic raw,
  Map<String, dynamic> input,
) {
  final value = businessMap(raw),
      source = businessMap(value['source']),
      calculation = businessMap(value['calculation']),
      fact = payrollFactRecord(
        source['period_case'],
        input['employee_id'],
        kind: 'period_case',
      );
  payrollPeriodCalculation(calculation);
  if (source['source_schema_version'] != 2 ||
      !payrollFactsSame(source['input'], input) ||
      !payrollFactsSame(payrollFactRef(fact), input['period_case_ref']) ||
      source['employee_id'] != input['employee_id'] ||
      fact['status'] != 'active' ||
      source['month'] != fact['details']['month'] ||
      calculation['month'] != source['month'] ||
      !payrollFactsSame(
        source['preparation'],
        fact['sources']['preparation'],
      ) ||
      !businessItems(fact['sources']['profiles']).any(
        (p) =>
            payrollFactsSame(p, source['profile']) &&
            payrollFactsSame(
              payrollFactRef(p),
              fact['plan']['selected_profile_ref'],
            ),
      ) ||
      calculation['period_details']['plan_hash'] != fact['plan']['plan_hash'] ||
      calculation['period_details']['source_snapshot_hash'] !=
          fact['source_hash'] ||
      calculation['gross_minor'] != fact['plan']['gross_minor'] ||
      value['can_finalize'] != calculation['payroll_calculation_complete'])
    _fail(
      'Die neue Lohnvorschau gehört nicht zum bestätigten ursprünglichen Monatsfall.',
    );
  return value;
}

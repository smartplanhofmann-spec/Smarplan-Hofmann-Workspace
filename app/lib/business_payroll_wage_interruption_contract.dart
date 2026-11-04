import 'dart:convert';

import 'api.dart';
import 'business_payroll_facts.dart';
import 'business_payroll_entitlement_contract.dart'
    show payrollEntitlementRecord;
import 'business_session.dart' show businessMap, businessItems;

const payrollWageInterruptionRule = 'de_2026_wage_interruptions_v1';
const payrollWageInterruptionKind = 'wage_interruption_assessment';
const payrollWageInterruptionExceptions = {
  'short_time_work_benefit': 'Kurzarbeitergeld',
  'qualification_benefit': 'Qualifizierungsgeld',
  'employer_maternity_supplement': 'Arbeitgeberzuschuss zum Mutterschaftsgeld',
  'civil_service_parental_birth_supplement': 'Zuschuss bei Beschäftigungsverbot oder Elternzeit nach beamtenrechtlichen Vorschriften',
  'infection_protection_compensation':
      'Entschädigung nach dem Infektionsschutzgesetz',
  'section3_number21': 'Leistungen nach § 3 Nummer 21 EStG',
  'section3_number28': 'Leistungen nach § 3 Nummer 28 EStG',
  'section3_number28a': 'Leistungen nach § 3 Nummer 28a EStG',
};
final _id = RegExp(r'^[a-f0-9]{32}$'), _hash = RegExp(r'^[a-f0-9]{64}$');
Map<String, dynamic> _copy(dynamic v) =>
    Map<String, dynamic>.from(jsonDecode(jsonEncode(v)) as Map);
// Invalid server proofs do not establish whether an original command was
// accepted. Keep its nonce and validator available for an exact retry.
Never _fail(String message, [int status = 0]) =>
    throw ApiException(status, message);
String _date(dynamic v) {
  final value = payrollFactDate(v)!;
  if (!value.startsWith('2026-'))
    _fail('Einen tatsächlichen Prüfungstag 2026 angeben.');
  return value;
}

String _note(dynamic v, String label) {
  if (v is! String ||
      v.trim().isEmpty ||
      v.trim().length > 3000 ||
      RegExp(r'[\x00-\x1f\x7f]').hasMatch(v))
    _fail('$label vollständig belegen.');
  return v.trim();
}

List<Map<String, dynamic>> _refs(
  dynamic values, {
  bool empty = false,
  int max = 200,
}) {
  if (values is! List || !empty && values.isEmpty || values.length > max)
    _fail('Die exakten ursprünglichen Quellenfassungen fehlen.');
  final result = values.map(payrollFactRef).toList();
  if (result.map((v) => v['id']).toSet().length != result.length)
    _fail('Eine Quellenfassung wurde mehrfach gewählt.');
  result.sort((a, b) => (a['id'] as String).compareTo(b['id']));
  return result;
}

Map<String, dynamic> payrollWageInterruptionDetails(dynamic raw) {
  final v = businessMap(raw);
  const keys = [
    'year',
    'assessment_through',
    'employment_terms_refs',
    'run_refs',
    'work_schedule_refs',
    'entitlement_case_refs',
    'excluded_payments_reviewed',
    'exception_review_file_refs',
    'excluded_payments',
    'verification_note',
  ];
  if (v.length != keys.length ||
      v.keys.any((k) => !keys.contains(k)) ||
      v['year'] != 2026 ||
      v['excluded_payments_reviewed'] != true ||
      v['excluded_payments'] is! List ||
      (v['excluded_payments'] as List).length > 200)
    _fail(
      'Prüfjahr und sämtliche gesetzlichen Ausnahmeleistungen ausdrücklich prüfen.',
    );
  final through = _date(v['assessment_through']);
  final payments = <Map<String, dynamic>>[];
  for (final raw in v['excluded_payments']) {
    final p = businessMap(raw);
    if (p.length != 4 ||
        p.keys.any(
          (k) => !['from', 'to', 'kind', 'evidence_refs'].contains(k),
        ) ||
        !payrollWageInterruptionExceptions.containsKey(p['kind']) ||
        _date(p['from']).compareTo(_date(p['to'])) > 0 ||
        (p['to'] as String).compareTo(through) > 0)
      _fail(
        'Jede Ausnahmeleistung durch Art, tatsächlichen Zeitraum und Originale belegen.',
      );
    payments.add({
      'from': p['from'],
      'to': p['to'],
      'kind': p['kind'],
      'evidence_refs': _refs(p['evidence_refs']),
    });
  }
  payments.sort((a, b) {
    for (final key in ['from', 'to', 'kind']) {
      final cmp = (a[key] as String).compareTo(b[key]);
      if (cmp != 0) return cmp;
    }
    return 0;
  });
  for (var i = 1; i < payments.length; i++) {
    if ((payments[i - 1]['to'] as String).compareTo(payments[i]['from']) >= 0)
      _fail(
        'Sich überschneidende Ausnahmeleistungen anhand ihrer Originale abgrenzen.',
      );
  }
  return {
    'year': 2026,
    'assessment_through': through,
    'employment_terms_refs': _refs(v['employment_terms_refs']),
    'run_refs': _refs(v['run_refs'], empty: true, max: 12),
    'work_schedule_refs': _refs(v['work_schedule_refs'], empty: true, max: 12),
    'entitlement_case_refs': _refs(v['entitlement_case_refs'], empty: true),
    'excluded_payments_reviewed': true,
    'exception_review_file_refs': _refs(v['exception_review_file_refs']),
    'excluded_payments': payments,
    'verification_note': _note(v['verification_note'], 'Jahresprüfung'),
  };
}

Map<String, dynamic> payrollWageInterruptionPlan(dynamic raw) {
  final v = businessMap(raw);
  if (v['schema_version'] != 1 ||
      v['rule_version'] != payrollWageInterruptionRule ||
      v['year'] != 2026 ||
      [
        'rules_sha256',
        'source_hash',
        'source_snapshot_hash',
        'plan_hash',
      ].any((k) => !_hash.hasMatch('${v[k]}')) ||
      [
        'periods',
        'candidates',
        'covered_dates',
        'blockers',
      ].any((k) => v[k] is! List) ||
      v['can_determine'] is! bool ||
      v['can_determine'] != (v['blockers'] as List).isEmpty ||
      v['automatic_payment_created'] != false ||
      v['statutory_transmitted'] != false)
    _fail(
      'Der Jahresprüfstand ist nicht vollständig an belegte Quellen und Regeln gebunden.',
    );
  _date(v['assessment_through']);
  if (v['can_determine']
      ? v['number_u'] is! int ||
            v['number_u'] < 0 ||
            v['number_u'] != (v['periods'] as List).length
      : v['number_u'] != null)
    _fail(
      'Unbekannte Unterbrechungsanzahl darf nicht als bestätigte Null erscheinen.',
    );
  final input = businessMap(v['input']);
  if (input['year'] != 2026 ||
      input['assessment_through'] != v['assessment_through'] ||
      input['days'] is! List ||
      (input['days'] as List).length > 366 ||
      input['employment_intervals'] is! List ||
      !['individual', 'flat_minijob'].contains(input['tax_scope']) ||
      input['carry_in_loss'] is! bool)
    _fail('Die tatsächliche Tagesabdeckung des Jahresprüfstands fehlt.');
  final days = <String>{};
  for (final d in businessItems(input['days'])) {
    final date = _date(d['date']), kind = d['section41_1_4_payment_kind'];
    if (date.compareTo(v['assessment_through']) > 0 ||
        !days.add(date) ||
        d['contractual_workday'] is! bool ||
        !['none', 'preserved', 'partial_unknown'].contains(d['wage_claim']) ||
        kind != null &&
            kind != 'none' &&
            !payrollWageInterruptionExceptions.containsKey(kind))
      _fail('Die belegte tägliche Anspruchsherleitung ist widersprüchlich.');
    for (final key in [
      'claim_evidence_refs',
      'schedule_evidence_refs',
      'exception_evidence_refs',
    ])
      _refs(d[key]);
  }
  if (!payrollFactsSame(
        businessItems(input['days']).map((d) => d['date']).toList(),
        v['covered_dates'],
      ) ||
      !payrollFactsSame(days.toList()..sort(), v['covered_dates']))
    _fail('Die tatsächlichen Tagesquellen müssen eindeutig und geordnet sein.');
  for (final interval in businessItems(input['employment_intervals'])) {
    payrollFactDate(interval['from']);
    payrollFactDate(interval['to'], optional: true);
    _refs(interval['evidence_refs']);
  }
  for (final p in [
    ...businessItems(v['periods']),
    ...businessItems(v['candidates']),
  ]) {
    if (_date(p['from_date']).compareTo(_date(p['to_date'])) > 0 ||
        p['qualifying_workdays'] is! List ||
        (p['qualifying_workdays'] as List).any(
          (d) =>
              d is! String ||
              !days.contains(d) ||
              d.compareTo(p['from_date']) < 0 ||
              d.compareTo(p['to_date']) > 0,
        ) ||
        (p['qualifying_workdays'] as List).toSet().length !=
            (p['qualifying_workdays'] as List).length ||
        p['workday_count'] != (p['qualifying_workdays'] as List).length ||
        p['letter_u'] is! bool ||
        p['letter_u'] != (p['workday_count'] >= 5))
      _fail('Die abgeleiteten Unterbrechungszeiträume sind unvollständig.');
  }
  if (businessItems(v['periods']).any(
    (p) =>
        p['letter_u'] != true ||
        !businessItems(v['candidates']).any((c) => payrollFactsSame(p, c)),
  ))
    _fail('Bestätigte Unterbrechungen fehlen in der Tagesherleitung.');
  return v;
}

void _bindings(
  Map<String, dynamic> s,
  Map<String, dynamic> d,
  dynamic ids,
  String employeeId,
) {
  if (s['schema_version'] != 1 ||
      s['rule_version'] != payrollWageInterruptionRule ||
      s['employee']?['id'] != employeeId ||
      s['employee']?['revision'] is! int ||
      s['employee']['revision'] < 1 ||
      !payrollFactsSame(s['details'], d))
    _fail(
      'Der Jahresprüfstand hat Mitarbeiter oder ursprüngliche Angaben ersetzt.',
    );
  for (final pair in [
    ('employment_terms', 'employment_terms_refs'),
    ('runs', 'run_refs'),
    ('work_schedules', 'work_schedule_refs'),
    ('entitlements', 'entitlement_case_refs'),
  ]) {
    if (s[pair.$1] is! List ||
        businessItems(s[pair.$1]).any((v) => v['employee_id'] != employeeId) ||
        !payrollFactsSame(_refs(s[pair.$1], empty: true), d[pair.$2]))
      _fail(
        'Eine tatsächliche Lauf-, Beschäftigungs-, Arbeitsplan- oder Anspruchsfassung wurde ersetzt.',
      );
  }
  if (s['source_files'] is! List ||
      !payrollFactsSame(
        businessItems(s['source_files']).map((f) => f['id']).toList()..sort(),
        ids,
      ) ||
      businessItems(s['source_files']).any(
        (f) =>
            f['employee_id'] != employeeId ||
            f['purpose'] != 'personnel' ||
            !_hash.hasMatch('${f['content_hash']}') ||
            !_hash.hasMatch('${f['sha256']}') ||
            f['size'] is! int ||
            f['size'] < 1,
      ))
    _fail('Die tatsächlich gebundenen privaten Originale wurden ersetzt.');
  final originals = businessItems(s['source_files']).map(
    (f) => {'id': f['id'], 'revision': 1, 'content_hash': f['content_hash']},
  );
  for (final ref in [
    ...businessItems(d['exception_review_file_refs']),
    ...businessItems(d['excluded_payments'])
        .expand((p) => businessItems(p['evidence_refs'])),
  ]) {
    if (!originals.any((v) => payrollFactsSame(v, ref)))
      _fail(
        'Die gesetzliche Ausnahmeprüfung benötigt ihr konkretes unverändertes Original.',
      );
  }
}

void _planBindings(Map<String, dynamic> plan, Map<String, dynamic> snapshot) {
  final allowed = {
    'claim_evidence_refs': [
      ...businessItems(snapshot['runs']),
      ...businessItems(snapshot['employment_terms']),
    ].map(payrollFactRef).toList(),
    'schedule_evidence_refs': [
      ...businessItems(snapshot['work_schedules']),
      ...businessItems(snapshot['employment_terms']),
    ].map(payrollFactRef).toList(),
    'exception_evidence_refs': businessItems(snapshot['source_files'])
        .map(
          (file) => {
            'id': file['id'],
            'revision': 1,
            'content_hash': file['content_hash'],
          },
        )
        .toList(),
  };
  for (final day in businessItems(plan['input']['days'])) {
    for (final entry in allowed.entries) {
      if (businessItems(day[entry.key]).any(
        (ref) =>
            !entry.value.any((original) => payrollFactsSame(ref, original)),
      )) {
        _fail(
          'Eine Tagesentscheidung verweist auf eine fremde oder ersetzte Originalfassung.',
        );
      }
    }
  }
  final terms = businessItems(snapshot['employment_terms'])
    ..sort(
      (a, b) => (a['details']['employment_from'] as String).compareTo(
        b['details']['employment_from'],
      ),
    );
  if (!payrollFactsSame(
    plan['input']['employment_intervals'],
    terms
        .map(
          (term) => {
            'from': term['details']['employment_from'],
            'to': term['details']['employment_to'],
            'evidence_refs': [payrollFactRef(term)],
          },
        )
        .toList(),
  )) {
    _fail(
      'Die geprüften Beschäftigungsepisoden widersprechen den gebundenen Originalen.',
    );
  }
}

Map<String, dynamic> payrollWageInterruptionRecord(
  dynamic raw,
  String employeeId,
) {
  final v = businessMap(raw);
  payrollFactRef(v);
  final d = payrollWageInterruptionDetails(v['details']),
      p = payrollWageInterruptionPlan(v['plan']),
      ids = v['source_file_ids'];
  if (v['employee_id'] != employeeId ||
      v['kind'] != payrollWageInterruptionKind ||
      v['rule_version'] != payrollWageInterruptionRule ||
      v['source_contract_version'] != 1 ||
      !['active', 'void'].contains(v['status']) ||
      v['effective_from'] != '2026-01-01' ||
      v['effective_to'] != d['assessment_through'] ||
      !_hash.hasMatch('${v['source_hash']}') ||
      !_hash.hasMatch('${v['preview_hash']}') ||
      p['source_snapshot_hash'] != v['source_hash'] ||
      p['assessment_through'] != d['assessment_through'] ||
      ids is! List ||
      ids.isEmpty ||
      ids.toSet().length != ids.length ||
      ids.any((id) => !_id.hasMatch('$id')) ||
      (v['revision'] == 1
          ? v['previous_hash'] != null
          : !_hash.hasMatch('${v['previous_hash']}')))
    _fail(
      'Der U-Nachweis gehört nicht eindeutig zur gewählten Person und Jahresfassung.',
    );
  _bindings(businessMap(v['sources']), d, ids, employeeId);
  _planBindings(p, businessMap(v['sources']));
  return v;
}

Map<String, dynamic> payrollWageInterruptionSources(
  dynamic raw,
  String employeeId,
) {
  final v = payrollFactSources(raw, employeeId);
  if (v['year'] != 2026 ||
      [
        'runs',
        'entitlements',
        'assessments',
        'file_references',
      ].any((k) => v[k] is! List) ||
      !payrollFactsSame(
        _refs(v['file_references'], empty: true, max: 2000),
        businessItems(v['files'])
            .map(
              (f) => {
                'id': f['id'],
                'revision': 1,
                'content_hash': f['content_hash'],
              },
            )
            .toList()
          ..sort((a, b) => (a['id'] as String).compareTo(b['id'])),
      ))
    _fail('Die Jahresquellen oder ihre Originalreferenzen sind unvollständig.');
  for (final field in ['runs', 'entitlements', 'assessments']) {
    _refs(v[field], empty: true, max: 2000);
    for (final item in businessItems(v[field])) {
      if (item['employee_id'] != employeeId)
        _fail('Eine Jahresquelle gehört zu einem anderen Mitarbeiter.');
      if (field == 'runs' && item['source']?['month'] is! String)
        _fail('Der tatsächliche Lohnlauf ist unvollständig.');
      if (field == 'entitlements') payrollEntitlementRecord(item, employeeId);
      if (field == 'assessments')
        payrollWageInterruptionRecord(item, employeeId);
    }
  }
  return v;
}

Map<String, dynamic> payrollWageInterruptionInput(
  String employeeId,
  Map<String, dynamic> s,
  Map<String, dynamic> v, {
  Map<String, dynamic>? previous,
}) {
  payrollWageInterruptionSources(s, employeeId);
  if (previous != null) payrollWageInterruptionRecord(previous, employeeId);
  if (v['year'] != 2026) _fail('Das Prüfjahr ausdrücklich auswählen.');
  List<Map<String, dynamic>> choose(
    dynamic rows,
    dynamic ids, {
    String? kind,
    bool empty = false,
  }) {
    if (ids is! List ||
        ids.toSet().length != ids.length ||
        !empty && ids.isEmpty)
      _fail(
        'Alle einschlägigen tatsächlichen Jahresquellen ausdrücklich auswählen.',
      );
    return _refs(
      ids.map((id) {
        final matches = businessItems(rows)
            .where((r) => r['id'] == id && (kind == null || r['kind'] == kind));
        if (matches.length != 1 || matches.single['status'] == 'void')
          _fail('Die ausgewählte aktuelle Quellenfassung fehlt.', 409);
        return matches.single;
      }).toList(),
      empty: empty,
    );
  }

  List<Map<String, dynamic>> files(dynamic ids) =>
      choose(s['file_references'], ids);
  final reviews = businessMap(v['excluded_reviews']);
  if (reviews.length != payrollWageInterruptionExceptions.length ||
      payrollWageInterruptionExceptions.keys.any(
        (k) => !['none', 'present'].contains(reviews[k]),
      ) ||
      v['excluded_payments'] is! List)
    _fail(
      'Jede gesetzliche Leistungsart ausdrücklich anhand der Originale prüfen.',
    );
  final payments = businessItems(v['excluded_payments'])
      .map(
        (p) => {
          'from': p['from'],
          'to': p['to'],
          'kind': p['kind'],
          'evidence_refs': files(p['evidence_file_ids']),
        },
      )
      .toList();
  for (final kind in payrollWageInterruptionExceptions.keys) {
    if ((reviews[kind] == 'present') != payments.any((p) => p['kind'] == kind))
      _fail(
        'Ausnahmeauswahl und tatsächliche Leistungszeiträume müssen übereinstimmen.',
      );
  }
  final d = payrollWageInterruptionDetails({
    'year': 2026,
    'assessment_through': _date(v['assessment_through']),
    'employment_terms_refs': choose(
      s['facts'],
      v['employment_terms_ids'],
      kind: 'employment_terms',
    ),
    'run_refs': choose(s['runs'], v['run_ids'], empty: true),
    'work_schedule_refs': choose(
      s['facts'],
      v['work_schedule_ids'],
      kind: 'work_schedule',
      empty: true,
    ),
    'entitlement_case_refs': choose(
      s['entitlements'],
      v['entitlement_case_ids'],
      empty: true,
    ),
    'excluded_payments_reviewed': true,
    'exception_review_file_refs': files(v['exception_review_file_ids']),
    'excluded_payments': payments,
    'verification_note': _note(v['verification_note'], 'Jahresprüfung'),
  });
  final ids = <String>{
    ...files(v['source_file_ids']).map((f) => f['id'] as String),
    ...businessItems(d['exception_review_file_refs'])
        .map((f) => f['id'] as String),
    ...payments.expand(
      (p) => businessItems(p['evidence_refs']).map((f) => f['id'] as String),
    ),
  }.toList()..sort();
  return {
    'employee_id': employeeId,
    'employee_revision': s['employee']['revision'],
    'kind': payrollWageInterruptionKind,
    'rule_version': payrollWageInterruptionRule,
    'source_contract_version': 1,
    'revision': previous?['revision'] ?? 0,
    'status': 'active',
    'details': d,
    'source_file_ids': ids,
    'confirmed': true,
    if (previous != null) ...{
      'id': previous['id'],
      'correction_reason': _note(v['correction_reason'], 'Korrekturgrund'),
    },
  };
}

Map<String, dynamic> payrollWageInterruptionPreviewInput(
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
Map<String, dynamic> payrollWageInterruptionPreview(
  dynamic raw,
  Map<String, dynamic> body,
) {
  final v = businessMap(raw),
      d = payrollWageInterruptionDetails(body['details']),
      p = payrollWageInterruptionPlan(v['plan']);
  if (v['employee_id'] != body['employee_id'] ||
      v['kind'] != body['kind'] ||
      !_hash.hasMatch('${v['source_hash']}') ||
      !_hash.hasMatch('${v['preview_hash']}') ||
      p['source_snapshot_hash'] != v['source_hash'] ||
      p['assessment_through'] != d['assessment_through'] ||
      [
        'can_confirm',
        'can_determine',
        'can_write',
        'can_approve',
        'writes_enabled',
      ].any((k) => v[k] is! bool) ||
      v['can_determine'] != p['can_determine'] ||
      v['source_snapshot']?['employee']?['revision'] !=
          body['employee_revision'])
    _fail(
      'Die U-Vorschau gehört nicht zum ausdrücklich geprüften Jahresauftrag.',
    );
  _bindings(
    businessMap(v['source_snapshot']),
    d,
    body['source_file_ids'],
    body['employee_id'],
  );
  _planBindings(p, businessMap(v['source_snapshot']));
  return v;
}

void Function(dynamic) payrollWageInterruptionValidator(
  Map<String, dynamic> body, {
  Map<String, dynamic>? previous,
  Map<String, dynamic>? preview,
}) {
  final b = _copy(body),
      old = previous == null ? null : _copy(previous),
      proof = preview == null ? null : _copy(preview);
  return (raw) {
    final v = payrollWageInterruptionRecord(raw, b['employee_id']);
    if (v['revision'] != (old?['revision'] ?? 0) + 1 ||
        old != null && v['id'] != old['id'] ||
        v['previous_hash'] != old?['content_hash'] ||
        v['status'] != b['status'] ||
        !payrollFactsSame(v['details'], b['details']) ||
        !payrollFactsSame(v['source_file_ids'], b['source_file_ids']) ||
        v['preview_hash'] != b['preview_hash'] ||
        v['correction_reason'] != (b['correction_reason'] ?? ''))
      _fail(
        'Die U-Annahme stimmt nicht mit dem unveränderten ursprünglichen Auftrag überein.',
      );
    final source = v['status'] == 'void' ? old : proof;
    if (v['status'] == 'void' && old == null ||
        source != null &&
            (!payrollFactsSame(
                  v['sources'],
                  source[v['status'] == 'void' ? 'sources' : 'source_snapshot'],
                ) ||
                !payrollFactsSame(v['plan'], source['plan']) ||
                v['source_hash'] != source['source_hash']))
      _fail(
        'Die U-Annahme hat den geprüften Jahresplan oder seine Originale ersetzt.',
      );
  };
}

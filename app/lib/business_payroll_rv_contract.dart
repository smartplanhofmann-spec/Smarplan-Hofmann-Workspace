import 'dart:convert';

import 'package:cryptography/dart.dart';

import 'api.dart';
import 'business_payroll_facts.dart';
import 'business_session.dart' show businessMap, businessItems;

const payrollRvRule = 'de_2026_minijob_rv_revocation_v1';
const payrollRvRuleHash =
    '0d63413c7af9c81ebcb99244d98945060198a28c72ac0631b5e605a7304a93e8';
const payrollRvPath = '/payroll/rv-lifecycle';
const payrollRvStatuses = {
  'exempt': 'RV-Befreiung belegt',
  'compulsory_after_revocation': 'RV-Pflicht nach belegter Aufhebung',
  'unresolved': 'RV-Status noch ungeklärt',
};
final _hashPattern = RegExp(r'^[a-f0-9]{64}$'),
    _idPattern = RegExp(r'^[a-f0-9]{32}$');
String payrollRvSelection(dynamic value) {
  final r = payrollFactRef(businessMap(value));
  return '${r['id']}/${r['revision']}/${r['content_hash']}';
}

Never _bad([
  String message = 'Die vollständigen ursprünglichen RV-Nachweise fehlen.',
]) => throw ApiException(400, message);
Map<String, dynamic> _copy(dynamic v) =>
    Map<String, dynamic>.from(jsonDecode(jsonEncode(v)) as Map);
bool _same(dynamic a, dynamic b) => payrollFactsSame(a, b);
int _compare(String a, String b) {
  final x = a.runes.toList(), y = b.runes.toList();
  for (var i = 0; i < x.length && i < y.length; i++) {
    if (x[i] != y[i]) return x[i].compareTo(y[i]);
  }
  return x.length.compareTo(y.length);
}

dynamic _ordered(dynamic v) {
  if (v is List) return v.map(_ordered).toList();
  if (v is Map) {
    final keys = v.keys.cast<String>().toList()..sort(_compare);
    return {for (final k in keys) k: _ordered(v[k])};
  }
  return v;
}

String _hash(dynamic v) => const DartSha256()
    .hashSync(utf8.encode(jsonEncode(_ordered(v))))
    .bytes
    .map((b) => b.toRadixString(16).padLeft(2, '0'))
    .join();
void _shape(dynamic v, String fields) {
  if (v is! Map || !_same(v.keys.toList()..sort(), fields.split(' ')..sort()))
    _bad();
}

Map<String, dynamic> _ref(dynamic v) {
  _shape(v, 'id revision content_hash');
  return payrollFactRef(businessMap(v));
}

List<Map<String, dynamic>> _refs(dynamic values) {
  if (values is! List || values.length > 100) _bad();
  final refs = values.map(_ref).toList()
    ..sort(
      (a, b) => '${a['id']}'.compareTo('${b['id']}') != 0
          ? '${a['id']}'.compareTo('${b['id']}')
          : (a['revision'] as int).compareTo(b['revision'] as int),
    );
  if (refs.map((r) => '${r['id']}/${r['revision']}').toSet().length !=
      refs.length)
    _bad();
  return refs;
}

String _note(dynamic v) {
  if (v is! String ||
      v.trim().isEmpty ||
      v.runes.length > 3000 ||
      RegExp(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]').hasMatch(v))
    _bad('Den tatsächlichen RV-Prüfvermerk vollständig angeben.');
  return v;
}

Map<String, dynamic> payrollRvAssessment(dynamic raw) {
  _shape(
    raw,
    'schema_version employee_id episode_id employment_from employment_to target_month reviewed_as_of sole_continuous_commercial_minijob_confirmed no_old_age_or_other_exclusion_confirmed established_exemption revocation review_note',
  );
  final a = businessMap(raw);
  if (a['schema_version'] is! int ||
      a['schema_version'] != 1 ||
      !_idPattern.hasMatch('${a['employee_id']}') ||
      a['episode_id'] != a['employee_id'])
    _bad();
  for (final k in ['employment_from', 'reviewed_as_of']) {
    payrollFactDate(a[k]);
  }
  payrollFactDate(a['employment_to'], optional: true);
  payrollFactMonth(a['target_month']);
  _note(a['review_note']);
  for (final k in [
    'sole_continuous_commercial_minijob_confirmed',
    'no_old_age_or_other_exclusion_confirmed',
  ]) {
    if (a[k] is! bool) _bad();
  }
  final e = businessMap(a['established_exemption']);
  _shape(
    e,
    'effective_from profile_ref evidence_ref established_status_confirmed',
  );
  payrollFactDate(e['effective_from']);
  _ref(e['profile_ref']);
  _ref(e['evidence_ref']);
  if (e['established_status_confirmed'] is! bool) _bad();
  if (a['revocation'] != null) {
    final r = businessMap(a['revocation']);
    _shape(
      r,
      'received_on request_format request_ref notification_received_on notification_ref authority_status objection_deadline_on deadline_ref deadline_review_confirmed authority_status_on authority_evidence_ref review_note',
    );
    payrollFactDate(r['received_on']);
    _ref(r['request_ref']);
    _note(r['review_note']);
    if ('${r['received_on']}'.compareTo('2026-07-01') < 0 ||
        !['written', 'electronic'].contains(r['request_format']) ||
        ![
          'not_notified',
          'pending',
          'non_objection_verified',
          'objected',
        ].contains(r['authority_status']) ||
        r['deadline_review_confirmed'] is! bool)
      _bad();
    for (final pair in [
      ['notification_received_on', 'notification_ref'],
      ['objection_deadline_on', 'deadline_ref'],
      ['authority_status_on', 'authority_evidence_ref'],
    ]) {
      if ((r[pair[0]] == null) != (r[pair[1]] == null)) _bad();
      if (r[pair[0]] != null) {
        payrollFactDate(r[pair[0]]);
        _ref(r[pair[1]]);
        if (pair[0] != 'objection_deadline_on' &&
            '${r[pair[0]]}'.compareTo('${a['reviewed_as_of']}') > 0)
          _bad();
      }
    }
    if (r['authority_status'] == 'non_objection_verified' &&
        (r['notification_ref'] == null ||
            r['deadline_ref'] == null ||
            r['deadline_review_confirmed'] != true ||
            r['authority_evidence_ref'] == null ||
            '${r['authority_status_on']}'.compareTo(
                  '${r['objection_deadline_on']}',
                ) <=
                0))
      _bad(
        'Den abgeschlossenen Nichtwiderspruch samt tatsächlicher Fristprüfung belegen.',
      );
  }
  return a;
}

Map<String, dynamic> _snapshot(
  dynamic raw,
  Map<String, dynamic> a,
  String employeeId,
) {
  _shape(
    raw,
    'schema_version rule_version employee details original_profile source_files prior_assessments',
  );
  final s = businessMap(raw);
  _shape(s['details'], 'assessment prior_assessment_refs');
  if (s['schema_version'] != 1 ||
      s['rule_version'] != payrollRvRule ||
      s['employee']?['id'] != employeeId ||
      !_same(s['details']['assessment'], a) ||
      a['employee_id'] != employeeId ||
      a['episode_id'] != employeeId ||
      a['employment_from'] != s['employee']['employment_from'] ||
      a['employment_to'] != s['employee']['employment_to'])
    _bad();
  final p = businessMap(s['original_profile']);
  payrollFactRef(p);
  if (p['employee_id'] != employeeId ||
      p['profile']?['employment_kind'] != 'minijob' ||
      p['profile']?['minijob_rv_exempt'] != true ||
      (p['profile']?['special_cases'] is List &&
          (p['profile']['special_cases'] as List).isNotEmpty) ||
      !_same(payrollFactRef(p), a['established_exemption']['profile_ref']))
    _bad('Das ursprüngliche befreite Minijobprofil wurde ersetzt.');
  final files = businessItems(s['source_files']);
  if (s['source_files'] is! List ||
      files.isEmpty ||
      files.map((f) => f['id']).toSet().length != files.length ||
      files.any(
        (f) =>
            f['employee_id'] != employeeId ||
            f['purpose'] != 'personnel' ||
            f['revision'] != 1 ||
            !_hashPattern.hasMatch('${f['sha256']}'),
      ))
    _bad();
  final originals = files
          .map(
            (f) => _ref({
              'id': f['id'],
              'revision': 1,
              'content_hash': f['content_hash'],
            }),
          )
          .toList(),
      r = businessMap(a['revocation']);
  for (final evidence in [
    a['established_exemption']['evidence_ref'],
    if (r.isNotEmpty)
      for (final k in [
        'request_ref',
        'notification_ref',
        'deadline_ref',
        'authority_evidence_ref',
      ])
        if (r[k] != null) r[k],
  ]) {
    if (!originals.any((f) => _same(f, evidence)))
      _bad('Der konkrete unveränderte Verfahrensnachweis fehlt.');
  }
  if (s['prior_assessments'] is! List ||
      !_same(
        _refs(
          businessItems(s['prior_assessments'])
              .map((p) => p['reference'])
              .toList(),
        ),
        _refs(s['details']['prior_assessment_refs']),
      ))
    _bad();
  for (final p in businessItems(s['prior_assessments'])) {
    _shape(p, 'reference assessment');
    final old = payrollRvAssessment(p['assessment']);
    if (old['employee_id'] != employeeId ||
        '${old['reviewed_as_of']}'.compareTo('${a['reviewed_as_of']}') > 0)
      _bad();
  }
  return s;
}

Map<String, dynamic> _plan(dynamic raw, Map<String, dynamic> s) {
  final p = businessMap(raw),
      a = payrollRvAssessment(s['details']['assessment']);
  if (p['rule_version'] != payrollRvRule ||
      p['rules_sha256'] != payrollRvRuleHash ||
      p['employee_id'] != a['employee_id'] ||
      p['episode_id'] != a['episode_id'] ||
      p['month'] != a['target_month'] ||
      !payrollRvStatuses.containsKey(p['status']) ||
      p['blockers'] is! List ||
      p['can_bind_payroll'] != (p['blockers'] as List).isEmpty ||
      p['can_determine'] != p['can_bind_payroll'] ||
      p['minijob_rv_exempt'] !=
          (p['can_bind_payroll'] == true ? p['status'] == 'exempt' : null) ||
      [
        'creates_profile',
        'payment_created',
        'external_transmission',
        'official_system_approval',
      ].any((k) => p[k] != false) ||
      !_hashPattern.hasMatch('${p['source_hash']}') ||
      !_hashPattern.hasMatch('${p['source_snapshot_hash']}'))
    _bad('Der RV-Prüfstand enthält keine eindeutige belegte Entscheidung.');
  final r = businessMap(a['revocation']);
  String? effect;
  if (r.isNotEmpty) {
    final d = DateTime.parse(r['received_on']);
    effect = DateTime.utc(
      d.year,
      d.month + 1,
      1,
    ).toIso8601String().substring(0, 10);
  }
  if (p['candidate_effective_from'] != effect ||
      p['can_bind_payroll'] == true &&
          (a['sole_continuous_commercial_minijob_confirmed'] != true ||
              a['no_old_age_or_other_exclusion_confirmed'] != true ||
              a['established_exemption']['established_status_confirmed'] !=
                  true ||
              '${a['target_month']}'.compareTo(
                    '${a['reviewed_as_of']}'.substring(0, 7),
                  ) >
                  0 ||
              effect != null &&
                  '${a['target_month']}-01'.compareTo(effect) >= 0 &&
                  (r['authority_status'] != 'non_objection_verified' ||
                      p['status'] != 'compulsory_after_revocation')))
    _bad(
      'Die RV-Wirkung ist nicht durch genau diesen Antrag und Prüfstand belegt.',
    );
  return p;
}

Map<String, dynamic> payrollRvPreview(dynamic raw, Map<String, dynamic> b) {
  final v = businessMap(raw),
      s = _snapshot(
        v['source_snapshot'],
        payrollRvAssessment(b['details']['assessment']),
        b['employee_id'],
      ),
      p = _plan(v['plan'], s);
  if (v['employee_id'] != b['employee_id'] ||
      v['kind'] != 'rv_lifecycle_assessment' ||
      !_same(s['details'], b['details']) ||
      v['can_confirm'] != true ||
      v['can_determine'] != p['can_determine'] ||
      v['source_hash'] != _hash(s) ||
      p['source_snapshot_hash'] != v['source_hash'] ||
      v['preview_hash'] != _hash({'source_snapshot': s, 'plan': p}) ||
      p['source_hash'] !=
          _hash({
            'assessment': s['details']['assessment'],
            'original_profile': s['original_profile'],
            'source_files': s['source_files'],
            'prior_assessments': businessItems(s['prior_assessments'])
                .map((p) => p['assessment'])
                .toList(),
          }) ||
      !_same(
        (b['source_file_ids'] as List).toList()..sort(),
        businessItems(s['source_files']).map((f) => f['id']).toList()..sort(),
      ))
    _bad(
      'Die RV-Vorschau wurde von ihren ursprünglichen Angaben oder Nachweisen getrennt.',
    );
  return v;
}

Map<String, dynamic> payrollRvRecord(dynamic raw, String employeeId) {
  final v = businessMap(raw);
  payrollFactRef(v);
  _shape(v['details'], 'assessment prior_assessment_refs');
  final a = payrollRvAssessment(v['details']['assessment']),
      s = _snapshot(v['sources'], a, employeeId);
  _plan(v['plan'], s);
  if (v['employee_id'] != employeeId ||
      v['kind'] != 'rv_lifecycle_assessment' ||
      v['rule_version'] != payrollRvRule ||
      v['source_contract_version'] is! int ||
      v['source_contract_version'] != 1 ||
      v['status'] != 'active' ||
      v['effective_from'] != a['employment_from'] ||
      v['effective_to'] != a['employment_to'] ||
      !_hashPattern.hasMatch('${v['source_hash']}') ||
      !_hashPattern.hasMatch('${v['preview_hash']}') ||
      v['plan']['source_snapshot_hash'] != v['source_hash'] ||
      (v['revision'] == 1
          ? v['previous_hash'] != null
          : !_hashPattern.hasMatch('${v['previous_hash']}')))
    _bad();
  payrollRvPreview(
    {
      'employee_id': employeeId,
      'kind': v['kind'],
      'source_snapshot': s,
      'source_hash': v['source_hash'],
      'plan': v['plan'],
      'preview_hash': v['preview_hash'],
      'can_confirm': true,
      'can_determine': v['plan']['can_determine'],
    },
    {
      'employee_id': employeeId,
      'details': v['details'],
      'source_file_ids': v['source_file_ids'],
    },
  );
  return v;
}

Map<String, dynamic> payrollRvSources(dynamic raw, String employeeId) {
  final s = businessMap(raw);
  if (s['employee_id'] != employeeId ||
      s['employee']?['id'] != employeeId ||
      s['episode_id'] != employeeId ||
      s['employee']?['revision'] is! int ||
      s['employee']['revision'] < 1 ||
      [
        'files',
        'file_references',
        'profiles',
        'history',
        'prior_assessment_refs',
      ].any((k) => s[k] is! List) ||
      ['can_write', 'can_approve', 'writes_enabled'].any((k) => s[k] is! bool))
    _bad();
  if (!_same(
        _refs(businessItems(s['history']).map(payrollFactRef).toList()),
        _refs(s['prior_assessment_refs']),
      ) ||
      !_same(
        _refs(s['file_references']),
        _refs(
          businessItems(s['files'])
              .map(
                (f) => {
                  'id': f['id'],
                  'revision': 1,
                  'content_hash': f['content_hash'],
                },
              )
              .toList(),
        ),
      ))
    _bad();
  for (final p in businessItems(s['profiles'])) {
    if (p['employee_id'] != employeeId || p['kind'] != 'profile') _bad();
    payrollFactRef(p);
  }
  for (final f in businessItems(s['files'])) {
    if (f['employee_id'] != employeeId || f['purpose'] != 'personnel') _bad();
  }
  for (final v in businessItems(s['history'])) {
    payrollRvRecord(v, employeeId);
  }
  return s;
}

Map<String, dynamic> payrollRvInput(
  Map<String, dynamic> s,
  Map<String, dynamic> v, {
  Map<String, dynamic>? previous,
}) {
  payrollRvSources(s, s['employee_id']);
  final employee = businessMap(s['employee']);
  Map<String, dynamic> original(
    dynamic id, [
    dynamic items,
    bool versioned = false,
  ]) {
    final found = businessItems(items ?? s['file_references'])
        .where((r) => (versioned ? payrollRvSelection(r) : r['id']) == id)
        .firstOrNull;
    if (found == null)
      _bad(
        'Eine aktuelle ursprüngliche Quellenfassung ausdrücklich auswählen.',
      );
    return payrollFactRef(found);
  }

  final old = businessMap(previous?['details']?['assessment']);
  final exemption = old.isNotEmpty
      ? _copy(old['established_exemption'])
      : {
          'effective_from': payrollFactDate(v['exempt_from']),
          'profile_ref': original(
            v['original_profile_id'],
            s['profiles'],
            true,
          ),
          'evidence_ref': original(v['exemption_file_id']),
          'established_status_confirmed': false,
        };
  exemption['established_status_confirmed'] =
      v['established_status_confirmed'] == true;
  if (!['none', 'received'].contains(v['request_state']))
    _bad('Den tatsächlichen Antragseingang ausdrücklich auswählen.');
  Map<String, dynamic>? r;
  if (v['request_state'] == 'received')
    r = {
      'received_on': payrollFactDate(v['received_on']),
      'request_format': v['request_format'],
      'request_ref': original(v['request_file_id']),
      'notification_received_on': payrollFactDate(
        v['notification_received_on'],
        optional: true,
      ),
      'notification_ref':
          v['notification_file_id'] == null || v['notification_file_id'] == ''
          ? null
          : original(v['notification_file_id']),
      'authority_status': v['authority_status'],
      'objection_deadline_on': payrollFactDate(
        v['objection_deadline_on'],
        optional: true,
      ),
      'deadline_ref':
          v['deadline_file_id'] == null || v['deadline_file_id'] == ''
          ? null
          : original(v['deadline_file_id']),
      'deadline_review_confirmed': v['deadline_review_confirmed'] == true,
      'authority_status_on': payrollFactDate(
        v['authority_status_on'],
        optional: true,
      ),
      'authority_evidence_ref':
          v['authority_file_id'] == null || v['authority_file_id'] == ''
          ? null
          : original(v['authority_file_id']),
      'review_note': _note(v['procedure_note']),
    };
  final a = payrollRvAssessment({
    'schema_version': 1,
    'employee_id': employee['id'],
    'episode_id': employee['id'],
    'employment_from': employee['employment_from'],
    'employment_to': employee['employment_to'],
    'target_month': payrollFactMonth(v['target_month']),
    'reviewed_as_of': payrollFactDate(v['reviewed_as_of']),
    'sole_continuous_commercial_minijob_confirmed':
        v['sole_continuous_commercial_minijob_confirmed'] == true,
    'no_old_age_or_other_exclusion_confirmed':
        v['no_old_age_or_other_exclusion_confirmed'] == true,
    'established_exemption': exemption,
    'revocation': r,
    'review_note': _note(v['review_note']),
  });
  final ids = [
    exemption['evidence_ref'],
    if (r != null)
      for (final k in [
        'request_ref',
        'notification_ref',
        'deadline_ref',
        'authority_evidence_ref',
      ])
        if (r[k] != null) r[k],
  ].map((ref) => '${ref['id']}').toSet().toList()..sort();
  return {
    'employee_id': employee['id'],
    'employee_revision': employee['revision'],
    'kind': 'rv_lifecycle_assessment',
    'rule_version': payrollRvRule,
    'source_contract_version': 1,
    'revision': previous?['revision'] ?? 0,
    'status': 'active',
    'details': {
      'assessment': a,
      'prior_assessment_refs': s['prior_assessment_refs'],
    },
    'source_file_ids': ids,
    'confirmed': true,
    if (previous != null) 'id': previous['id'],
    if (previous != null) 'correction_reason': _note(v['correction_reason']),
  };
}

Map<String, dynamic> payrollRvPreviewInput(Map<String, dynamic> b) => {
  for (final k in [
    'employee_id',
    'employee_revision',
    'kind',
    'rule_version',
    'source_contract_version',
    'details',
    'source_file_ids',
  ])
    k: b[k],
};
void Function(dynamic) payrollRvValidator(
  Map<String, dynamic> body,
  Map<String, dynamic> preview, {
  Map<String, dynamic>? previous,
}) {
  final b = _copy(body),
      p = _copy(preview),
      old = previous == null ? null : _copy(previous);
  return (raw) {
    try {
      final v = payrollRvRecord(raw, b['employee_id']);
      if (v['revision'] != b['revision'] + 1 ||
          old != null && v['id'] != old['id'] ||
          v['previous_hash'] != old?['content_hash'] ||
          !_same(v['details'], b['details']) ||
          !_same(v['source_file_ids'], b['source_file_ids']) ||
          !_same(v['sources'], p['source_snapshot']) ||
          !_same(v['plan'], p['plan']) ||
          v['preview_hash'] != p['preview_hash'] ||
          v['preview_hash'] != b['preview_hash'] ||
          v['source_hash'] != p['source_hash'] ||
          v['correction_reason'] != (b['correction_reason'] ?? ''))
        _bad('Die RV-Annahme passt nicht zum unveränderten geprüften Auftrag.');
    } catch (_) {
      // A received but invalid answer does not prove that the server rejected
      // the immutable command. Preserve its exact nonce for reconciliation.
      throw const ApiException(
        0,
        'Die RV-Antwort stimmt nicht mit dem ursprünglichen geprüften Auftrag überein. Der Auftrag bleibt unbestätigt.',
      );
    }
  };
}

Map<String, dynamic> payrollRvProfileBinding(
  Map<String, dynamic> s,
  Map<String, dynamic> values,
) {
  payrollRvSources(s, s['employee_id']);
  final latest = businessItems(s['history']).lastOrNull;
  if (latest == null) {
    if (values['rv_lifecycle_id'] != null && values['rv_lifecycle_id'] != '')
      _bad();
    return {};
  }
  if (values['rv_lifecycle_id'] != payrollRvSelection(latest))
    throw const ApiException(
      409,
      'Der RV-Nachweis wurde geändert oder noch nicht ausdrücklich gewählt. Quellen neu laden und die genaue Fassung prüfen.',
    );
  return {
    'rv_lifecycle_source_contract_version': 1,
    'rv_lifecycle_ref': payrollFactRef(latest),
  };
}

import 'dart:convert';

import 'package:cryptography/dart.dart';

import 'api.dart';

const companyEventBase = '/company-events';
const companyEventTriggers = {
  'task.overdue': 'Überfällige Aufgabe',
  'payment.overdue': 'Überfällige Zahlung',
  'cost.threshold': 'Belegte Projektkosten',
  'communication.received': 'Zugeordnete Anfrage',
  'document.finalized': 'Festgeschriebener Beleg',
  'dunning.ready': 'Freigegebene Mahnung',
};
const companyEventActions = {
  'task.create': 'Aufgabe anlegen',
  'offer.draft': 'Angebot entwerfen',
  'document.email': 'Finalen Beleg versenden',
  'dunning.email': 'Freigegebene Mahnung versenden',
  'payment.execute': 'Zahlung ausführen',
  'supplier.order': 'Bestellung ausführen',
};
const companyEventModes = {
  'auto': 'Automatisch erlaubt',
  'approval': 'Freigabe erforderlich',
  'deny': 'Verboten',
};
const companyEventStates = {
  'denied': 'Durch Regeln verboten',
  'awaiting_approval': 'Freigabe offen',
  'ready': 'Bereit',
  'rejected': 'Abgelehnt',
  'stale': 'Quellen oder Regeln geändert',
  'suspended_after_restore': 'Nach Wiederherstellung gesperrt',
  'succeeded': 'Erfolgreich ausgeführt',
  'failed': 'Fehlgeschlagen',
  'unknown': 'Ausgang unklar',
  'blocked': 'Fachlich gesperrt',
  'unconfirmed': 'Ausgang noch nicht bestätigt',
  'prepared': 'Vorbereitet',
};
const companyEventFields = {
  'overdue_days': ('Überfälligkeit in Tagen', 'integer'),
  'source_status': ('Quellenstatus', 'text'),
  'open_minor': ('Offener Betrag in EUR', 'money'),
  'total_cost_minor': ('Erfasste Projektkosten in EUR', 'money'),
  'costs_complete': ('Kostenquellen vollständig', 'boolean'),
  'document_kind': ('Belegart', 'text'),
  'level': ('Mahnstufe', 'integer'),
};
final _id = RegExp(r'^[a-f0-9]{32}$'),
    _hash = RegExp(r'^[a-f0-9]{64}$'),
    _money = RegExp(r'^(?:0|[1-9][0-9]{0,39})$');

Never _invalid([
  String message = 'Der Unternehmensereignis-Nachweis ist ungültig.',
]) => throw ApiException(0, message);
void _require(bool value, [String? message]) {
  if (!value)
    _invalid(message ?? 'Der Unternehmensereignis-Nachweis ist ungültig.');
}

Map<String, dynamic> companyEventMap(dynamic value) {
  _require(value is Map && value.keys.every((key) => key is String));
  return Map<String, dynamic>.from(value as Map);
}

Map<String, dynamic> _keys(
  dynamic value,
  String required, [
  String optional = '',
]) {
  final result = companyEventMap(value);
  final need = required.split(' ').where((s) => s.isNotEmpty).toSet();
  final allowed = {...need, ...optional.split(' ')};
  _require(
    need.every(result.containsKey) && result.keys.every(allowed.contains),
  );
  return result;
}

List<dynamic> _list(dynamic value) {
  _require(value is List);
  return value as List;
}

void _identifier(dynamic value) =>
    _require(value is String && _id.hasMatch(value));
void _digestValue(dynamic value) =>
    _require(value is String && _hash.hasMatch(value));
void _text(dynamic value) => _require(value is String);
void _boolean(dynamic value) => _require(value is bool);
void _integer(dynamic value, [int min = 0, int max = 9007199254740991]) =>
    _require(value is int && value >= min && value <= max);
void _identity(dynamic value) =>
    _identifier(_keys(value, 'instance_id')['instance_id']);
void _day(dynamic value) {
  _require(value is String && RegExp(r'^\d{4}-\d{2}-\d{2}$').hasMatch(value));
  final date = DateTime.tryParse('${value}T00:00:00Z');
  _require(date != null && date.toIso8601String().substring(0, 10) == value);
}

String companyEventCanonical(dynamic value) {
  if (value == null || value is String || value is bool)
    return jsonEncode(value);
  if (value is int) {
    _integer(value, -9007199254740991);
    return '$value';
  }
  if (value is List) return '[${value.map(companyEventCanonical).join(',')}]';
  final map = companyEventMap(value),
      keys = companyEventMap(value).keys.toList()..sort();
  return '{${keys.map((k) => '${jsonEncode(k)}:${companyEventCanonical(map[k])}').join(',')}}';
}

String companyEventHash(dynamic value, {bool raw = false}) => const DartSha256()
    .hashSync(utf8.encode(raw ? value as String : companyEventCanonical(value)))
    .bytes
    .map((v) => v.toRadixString(16).padLeft(2, '0'))
    .join();
bool _same(dynamic first, dynamic second) =>
    companyEventCanonical(first) == companyEventCanonical(second);

String _legacyCanonical(dynamic value, [String key = '']) {
  if (key.endsWith('_minor') && value is String) {
    _require(RegExp(r'^-?(?:0|[1-9][0-9]*)$').hasMatch(value));
    return value;
  }
  if (value is List)
    return '[${value.map((v) => _legacyCanonical(v)).join(',')}]';
  if (value is Map) {
    final map = companyEventMap(value),
        keys = value.keys.cast<String>().toList()..sort();
    return '{${keys.map((k) => '${jsonEncode(k)}:${_legacyCanonical(map[k], k)}').join(',')}}';
  }
  return companyEventCanonical(value);
}

String companyEventMoney(String minor) {
  _require(RegExp(r'^-?(?:0|[1-9][0-9]*)$').hasMatch(minor));
  final n = BigInt.parse(minor),
      a = BigInt.parse(minor).abs(),
      hundred = BigInt.from(100);
  final whole = (a ~/ hundred).toString().replaceAllMapped(
    RegExp(r'\B(?=(\d{3})+(?!\d))'),
    (_) => '.',
  );
  return '${n.isNegative ? '-' : ''}$whole,${(a % hundred).toString().padLeft(2, '0')} €';
}

String companyEventMoneyInput(String minor) {
  _require(_money.hasMatch(minor));
  final n = BigInt.parse(minor), hundred = BigInt.from(100);
  return '${n ~/ hundred}.${(n % hundred).toString().padLeft(2, '0')}';
}

List<Map<String, dynamic>> companyEventConditions(
  String trigger,
  List<Map<String, dynamic>> rows,
  Map<String, dynamic> status,
) {
  _require(rows.length <= 8, 'Höchstens acht belegte Bedingungen erfassen.');
  final fields = companyEventMap(
    companyEventMap(status['condition_fields'])[trigger],
  );
  return rows.map((row) {
    final field = '${row['field']}',
        operator = row['operator'],
        type = fields[field];
    _require(
      type != null && ['eq', 'gte', 'lte'].contains(operator),
      'Eine gültige Bedingung auswählen.',
    );
    dynamic value = row['value'];
    if (field.endsWith('_minor')) {
      final input = '$value'.trim().replaceAll(',', '.');
      _require(
        RegExp(r'^\d{1,38}(?:\.\d{1,2})?$').hasMatch(input),
        'Nichtnegativen EUR-Betrag ohne Rundung eingeben.',
      );
      final parts = input.split('.');
      value =
          (BigInt.parse(parts[0]) * BigInt.from(100) +
                  BigInt.parse(
                    (parts.length > 1 ? parts[1] : '').padRight(2, '0'),
                  ))
              .toString();
      _require(_money.hasMatch(value));
    } else if (type == 'bool') {
      _require(
        operator == 'eq' && [true, false, 'Ja', 'Nein'].contains(value),
        'Ja oder Nein auf Gleichheit prüfen.',
      );
      value = value == true || value == 'Ja';
    } else if (type == 'int') {
      _require(
        RegExp(r'^\d{1,7}$').hasMatch('$value'),
        'Nichtnegative ganze Zahl eingeben.',
      );
      value = int.parse('$value');
      _integer(value, 0, 1000000);
    } else {
      _require(
        operator == 'eq' && value is String && value.length <= 100,
        'Text nur auf Gleichheit prüfen.',
      );
    }
    return <String, dynamic>{
      'field': field,
      'operator': operator,
      'value': value,
    };
  }).toList();
}

void _bound(Map<String, dynamic> value, String ignored) {
  final skip = ignored.split(' ').toSet();
  _digestValue(value['sha256']);
  _require(
    companyEventHash({
          for (final e in value.entries)
            if (!skip.contains(e.key)) e.key: e.value,
        }) ==
        value['sha256'],
    'Der gespeicherte Quellen- oder Planhash stimmt nicht.',
  );
}

Map<String, dynamic> companyEventStatus(dynamic raw) {
  final v = _keys(
    raw,
    'schema_version feature timezone triggers condition_fields actions modes default_policy payroll_sources external_model_calls recurrence max_scan_limit',
  );
  _require(
    v['schema_version'] == 1 &&
        v['feature'] == 'company_event_rules' &&
        v['timezone'] == 'Europe/Berlin' &&
        v['default_policy'] == 'deny' &&
        v['payroll_sources'] == false &&
        v['external_model_calls'] == false &&
        v['recurrence'] == 'once_per_occurrence_and_action' &&
        v['max_scan_limit'] == 100,
  );
  final triggers = _list(v['triggers']).cast<String>().toList()..sort();
  final modes = _list(v['modes']).cast<String>().toList()..sort();
  _require(
    _same(triggers, companyEventTriggers.keys.toList()..sort()) &&
        _same(modes, companyEventModes.keys.toList()..sort()),
  );
  final fields = companyEventMap(v['condition_fields']);
  for (final t in triggers) {
    for (final entry in companyEventMap(fields[t]).entries) {
      _require(
        companyEventFields.containsKey(entry.key) &&
            ['str', 'int', 'bool'].contains(entry.value),
      );
    }
  }
  for (final item in _list(v['actions'])) {
    final a = _keys(item, 'action triggers executable');
    _require(
      companyEventActions.containsKey(a['action']) &&
          _list(a['triggers']).every(companyEventTriggers.containsKey),
    );
    _boolean(a['executable']);
  }
  return v;
}

Map<String, dynamic> companyEventRule(dynamic raw) {
  final v = _keys(
    raw,
    'schema_version id revision title enabled project_ids trigger action mode conditions template responsible_id identity previous_hash created_by created_at',
    'acceptance',
  );
  _require(
    v['schema_version'] == 1 &&
        companyEventTriggers.containsKey(v['trigger']) &&
        companyEventActions.containsKey(v['action']) &&
        companyEventModes.containsKey(v['mode']),
  );
  for (final k in ['id', 'created_by', 'responsible_id']) {
    _identifier(v[k]);
  }
  _integer(v['revision'], 1);
  _boolean(v['enabled']);
  _text(v['title']);
  _text(v['created_at']);
  _identity(v['identity']);
  if (v['revision'] == 1) {
    _require(v['previous_hash'] == null);
  } else {
    _digestValue(v['previous_hash']);
  }
  if (v['project_ids'] != null) {
    final ids = _list(v['project_ids']);
    _require(ids.isNotEmpty && ids.length <= 100);
    for (final i in ids) {
      _identifier(i);
    }
    _require(_same(ids, ids.toSet().toList()..sort()));
  }
  final conditions = _list(v['conditions']);
  _require(conditions.length <= 8);
  for (final item in conditions) {
    final c = _keys(item, 'field operator value');
    _require(
      companyEventFields.containsKey(c['field']) &&
          ['eq', 'gte', 'lte'].contains(c['operator']),
    );
    if ('${c['field']}'.endsWith('_minor')) {
      _require(c['value'] is String && _money.hasMatch(c['value']));
    } else if (c['value'] is int) {
      _integer(c['value'], 0, 1000000);
    } else {
      _require(
        (c['value'] is String || c['value'] is bool) && c['operator'] == 'eq',
      );
    }
  }
  final template = companyEventMap(v['template']);
  if (v['action'] == 'task.create') {
    _keys(template, 'title details priority due_days');
    _text(template['title']);
    _text(template['details']);
    _require(['normal', 'high'].contains(template['priority']));
    if (template['due_days'] != null) {
      _integer(template['due_days'], 0, 365);
    }
  } else if (v['action'] == 'offer.draft') {
    _keys(template, 'title due_days positions');
    _text(template['title']);
    _integer(template['due_days'], 0, 365);
    final positions = _list(template['positions']);
    _require(positions.isNotEmpty && positions.length <= 6);
    for (final raw in positions) {
      final p = _keys(raw, 'article_id article_revision quantity');
      _identifier(p['article_id']);
      _integer(p['article_revision'], 1);
      _require(
        p['quantity'] is String &&
            RegExp(r'^\d{1,6}(?:\.\d{1,4})?$').hasMatch(p['quantity']) &&
            RegExp('[1-9]').hasMatch(p['quantity']),
      );
    }
  } else {
    _keys(template, '');
  }
  return v;
}

Map<String, dynamic> companyEventRuleHistory(dynamic raw, String ruleId) {
  final v = _keys(raw, 'schema_version items');
  _require(v['schema_version'] == 1 && _list(v['items']).isNotEmpty);
  Map<String, dynamic>? previous;
  for (final raw in v['items']) {
    final row = companyEventRule(raw);
    _require(
      row['id'] == ruleId &&
          row['revision'] ==
              (previous == null ? 1 : previous['revision'] + 1) &&
          row['previous_hash'] ==
              (previous == null ? null : companyEventHash(previous)),
    );
    previous = row;
  }
  return v;
}

void _source(dynamic raw, String project) {
  final v = _keys(raw, 'descriptor source_id data sha256');
  final descriptor = _keys(v['descriptor'], 'kind id');
  _identifier(descriptor['id']);
  _require(
    [
      'project',
      'task',
      'open_item',
      'costs',
      'communication',
      'document',
      'dunning',
      'article',
    ].contains(descriptor['kind']),
  );
  _require(v['source_id'] == '${descriptor['kind']}:${descriptor['id']}');
  final data = companyEventMap(v['data']);
  if (data.containsKey('project_id')) {
    _require(data['project_id'] == project);
  }
  _digestValue(v['sha256']);
  _require(
    companyEventHash(data) == v['sha256'],
    'Die Ereignisquelle passt nicht zu ihrem Originalhash.',
  );
  for (final k in ['open_minor', 'total_cost_minor']) {
    if (data.containsKey(k)) {
      _require(
        data[k] is String && RegExp(r'^-?(?:0|[1-9][0-9]*)$').hasMatch(data[k]),
      );
    }
  }
}

Map<String, dynamic> companyEventObservation(dynamic raw) {
  final v = _keys(
    raw,
    'schema_version identity project_id trigger as_of source facts active occurrence_key id sha256 source_current created_at',
  );
  _require(
    v['schema_version'] == 1 && companyEventTriggers.containsKey(v['trigger']),
  );
  _identifier(v['id']);
  _identifier(v['project_id']);
  _identity(v['identity']);
  _day(v['as_of']);
  _digestValue(v['occurrence_key']);
  _boolean(v['active']);
  _boolean(v['source_current']);
  _text(v['created_at']);
  final facts = companyEventMap(v['facts']);
  _source(v['source'], v['project_id']);
  _bound(v, 'id sha256 source_current created_at');
  _require(v['id'] == (v['sha256'] as String).substring(0, 32));
  for (final k in ['open_minor', 'total_cost_minor']) {
    if (facts.containsKey(k)) {
      _require(facts[k] == v['source']['data'][k]);
    }
  }
  return v;
}

void _policy(dynamic raw) {
  final v = _keys(
    raw,
    'mode responsible_id template reason matched_rules uncheckable_rules rule_versions company_mode project_policies',
  );
  _require(
    companyEventModes.containsKey(v['mode']) &&
        companyEventModes.containsKey(v['company_mode']),
  );
  if (v['responsible_id'] != null) {
    _identifier(v['responsible_id']);
  }
  _text(v['reason']);
  for (final name in ['matched_rules', 'uncheckable_rules', 'rule_versions']) {
    for (final item in _list(v[name])) {
      final r = companyEventMap(item);
      _identifier(r['id']);
      _integer(r['revision'], 1);
      if (name == 'rule_versions') {
        _digestValue(r['sha256']);
      }
    }
  }
  for (final raw in _list(v['project_policies'])) {
    final p = _keys(raw, 'trigger policy original_json original_sha256');
    _require(
      p['trigger'] == 'manual' ||
          companyEventTriggers.containsKey(p['trigger']),
    );
    _text(p['original_json']);
    _digestValue(p['original_sha256']);
    _require(
      companyEventHash(p['original_json'], raw: true) == p['original_sha256'] &&
          _legacyCanonical(p['policy']) == p['original_json'],
      'Die Projektregelprojektion passt nicht zum unveränderten Original.',
    );
  }
}

Map<String, dynamic> companyEventPlan(
  dynamic raw, {
  Map<String, dynamic>? event,
}) {
  final v = _keys(
    raw,
    'schema_version event_id event_sha256 project_id action action_key policy context parameters preparation_error id sha256 created_at source_current status can_execute blocked decision execution outcome',
    'reprepared_after_restore acceptance',
  );
  _require(
    v['schema_version'] == 1 &&
        companyEventActions.containsKey(v['action']) &&
        companyEventStates.containsKey(v['status']),
  );
  for (final k in ['id', 'event_id', 'project_id']) {
    _identifier(v[k]);
  }
  for (final k in ['event_sha256', 'action_key']) {
    _digestValue(v[k]);
  }
  _text(v['created_at']);
  _boolean(v['source_current']);
  _boolean(v['can_execute']);
  _policy(v['policy']);
  final context = _keys(v['context'], 'project_id sources');
  _require(
    context['project_id'] == v['project_id'] &&
        _list(context['sources']).isNotEmpty,
  );
  for (final s in context['sources']) {
    _source(s, v['project_id']);
  }
  _bound(
    v,
    'id sha256 created_at source_current status can_execute blocked decision execution outcome acceptance',
  );
  _require(v['id'] == (v['sha256'] as String).substring(0, 32));
  if (event != null) {
    companyEventObservation(event);
    _require(
      event['id'] == v['event_id'] &&
          event['sha256'] == v['event_sha256'] &&
          event['project_id'] == v['project_id'] &&
          _same(event['source'], context['sources'][0]) &&
          companyEventHash([event['occurrence_key'], v['action']]) ==
              v['action_key'],
      'Plan und ursprüngliches Ereignis passen nicht zusammen.',
    );
  }
  if (v['decision'] != null) {
    final d = companyEventMap(v['decision']);
    _require(
      d['plan_id'] == v['id'] &&
          d['plan_sha256'] == v['sha256'] &&
          d['created_by'] == v['policy']['responsible_id'] &&
          ['approved', 'rejected'].contains(d['decision']),
    );
    _text(d['reason']);
  }
  if (v['execution'] != null) {
    final e = companyEventMap(v['execution']);
    _identifier(e['plan_id']);
    _identifier(e['domain_request_id']);
    _identifier(e['created_by']);
    _require(e['action_key'] == v['action_key'] && v['can_execute'] == false);
  }
  if (v['outcome'] != null) {
    final o = companyEventMap(v['outcome']),
        result = companyEventMap(o['result']);
    _require(
      v['execution'] != null &&
          ['succeeded', 'failed', 'unknown', 'blocked'].contains(o['status']),
    );
    if (o['status'] == 'succeeded' && v['action'] == 'task.create') {
      _require(
        result['project_id'] == v['project_id'] &&
            result['assignee_id'] == v['execution']['created_by'],
      );
      _identifier(result['id']);
    }
    if (o['status'] == 'succeeded' && v['action'] == 'offer.draft') {
      _require(
        result['project_id'] == v['project_id'] && result['kind'] == 'offer',
      );
      _identifier(result['id']);
    }
  }
  if (v['status'] == 'succeeded') {
    _require(
      v['execution'] != null &&
          v['outcome'] is Map &&
          v['outcome']['status'] == 'succeeded',
      'Ein erfolgreicher Status benötigt ein bestätigtes Ausführungsergebnis.',
    );
  }
  return v;
}

Map<String, dynamic> companyEventRun(dynamic raw) {
  final v = _keys(
    raw,
    'schema_version identity as_of timezone items issues scanned_count complete next_after after limit id sha256 created_at processing',
    'acceptance',
  );
  _require(v['schema_version'] == 1 && v['timezone'] == 'Europe/Berlin');
  _identity(v['identity']);
  _identifier(v['id']);
  _day(v['as_of']);
  _integer(v['scanned_count']);
  _integer(v['limit'], 1, 100);
  _boolean(v['complete']);
  _text(v['created_at']);
  for (final k in ['after', 'next_after']) {
    _require(
      v[k] == null ||
          v[k] is String &&
              (v[k] as String).isNotEmpty &&
              (v[k] as String).length <= 300,
    );
  }
  final expected = <String>{};
  for (final raw in _list(v['items'])) {
    final r = _keys(raw, 'event_id plan_ids');
    _identifier(r['event_id']);
    for (final id in _list(r['plan_ids'])) {
      _identifier(id);
      expected.add(id);
    }
  }
  for (final raw in _list(v['issues'])) {
    final i = companyEventMap(raw);
    _text(i['code']);
    _integer(i['status_code'], 400, 599);
  }
  if (v['processing'] != null) {
    final p = _keys(v['processing'], 'items');
    final items = _list(p['items']).map(companyEventMap).toList();
    _require(_same(items.map((r) => r['plan_id']).toList(), expected.toList()));
    for (final r in items) {
      _require(companyEventStates.containsKey(r['status']));
    }
  }
  _bound(v, 'id sha256 created_at processing acceptance');
  return v;
}

Map<String, dynamic> companyEventPage(dynamic raw, String kind) {
  final v = _keys(raw, 'schema_version items next_after');
  _require(v['schema_version'] == 1 && _list(v['items']).length <= 100);
  if (v['next_after'] != null) {
    _identifier(v['next_after']);
  }
  for (final item in v['items']) {
    switch (kind) {
      case 'events':
        companyEventObservation(item);
      case 'plans':
        companyEventPlan(item);
      case 'runs':
        companyEventRun(item);
      default:
        _invalid();
    }
  }
  return v;
}

String companyEventOperation(String path) {
  if (path == '$companyEventBase/rules') return 'rule';
  if (path == '$companyEventBase/scan') return 'scan';
  final m = RegExp(
    r'^/company-events/plans/([a-f0-9]{32})/(approve|reject|execute)$',
  ).firstMatch(path);
  if (m == null) _invalid('Unbekannte Unternehmensereignis-Annahme.');
  return '${m.group(2)}:${m.group(1)}';
}

String companyEventCommandKey(String path, Map<String, dynamic> values) {
  final op = companyEventOperation(path);
  if (op == 'rule') {
    _identifier(values['id']);
    return 'company-event-rule-${values['id']}';
  }
  if (op == 'scan') return 'company-event-scan';
  return 'company-event-${op.startsWith('execute:') ? 'execute' : 'decision'}-${op.split(':')[1]}';
}

void companyEventReceipt(String path, Map<String, dynamic> body, dynamic raw) {
  final op = companyEventOperation(path), result = companyEventMap(raw);
  final a = _keys(result['acceptance'], 'request_id operation request_hash');
  _require(
    a['request_id'] == body['request_id'] &&
        a['operation'] == op &&
        a['request_hash'] == companyEventHash([op, body]),
    'Die Antwort bestätigt nicht den unveränderten ursprünglichen Ereignisauftrag.',
  );
  if (op == 'rule') {
    companyEventRule(result);
    _require(
      result['id'] == body['id'] && result['revision'] == body['revision'] + 1,
    );
    for (final k in [
      'title',
      'enabled',
      'project_ids',
      'trigger',
      'action',
      'mode',
      'conditions',
      'template',
      'responsible_id',
    ]) {
      _require(
        _same(result[k], body[k]),
        'Die angenommene Regelfassung widerspricht dem Auftrag.',
      );
    }
  } else if (op == 'scan') {
    companyEventRun(result);
    _require(
      result['after'] == body['after'] && result['limit'] == body['limit'],
    );
  } else {
    companyEventPlan(result);
    _require(
      result['id'] == op.split(':')[1] &&
          result['sha256'] == body['plan_sha256'],
    );
    if (op.startsWith('execute:')) {
      _require(
        result['execution'] != null &&
            (result['outcome'] != null || result['status'] == 'unconfirmed'),
      );
    } else {
      _require(
        result['decision']?['decision'] ==
                (op.startsWith('approve:') ? 'approved' : 'rejected') &&
            result['decision']?['reason'] == body['reason'],
      );
    }
  }
}

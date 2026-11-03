import 'dart:convert';
import 'dart:typed_data';

import 'package:cryptography/cryptography.dart';
import 'package:flutter/material.dart';

import 'api.dart';
import 'business_session.dart';
import 'business_widgets.dart';
import 'design.dart';
import 'mail_attachment_widgets.dart';
import 'offline_vault.dart' show offlineId;

const travelStatuses = {
  'draft': 'Entwurf',
  'submitted': 'Eingereicht',
  'rejected': 'Zurückgewiesen',
  'approved': 'Freigegeben',
  'void': 'Aufgehoben',
  'active': 'Gültig',
  'partially_paid': 'Teilweise erstattet',
  'paid': 'Erstattet',
};
const _travelRoot = '/personnel/travel';
final _travelId = RegExp(r'^[a-f0-9]{32}$');
final _travelHash = RegExp(r'^[a-f0-9]{64}$');
Never _fail(String message, [int status = 400]) =>
    throw ApiException(status, message);
Map<String, dynamic> _copy(Map<String, dynamic> value) =>
    businessMap(jsonDecode(jsonEncode(value)));

int travelMinor(Object? input, {bool zero = false}) {
  final value = '${input ?? ''}'.trim().replaceAll(',', '.');
  if (!RegExp(r'^\d{1,11}(?:\.\d{1,2})?$').hasMatch(value)) {
    _fail('EUR-Betrag mit höchstens zwei Nachkommastellen eingeben.');
  }
  final parts = value.split('.');
  final amount =
      int.parse(parts.first) * 100 +
      int.parse((parts.length == 1 ? '' : parts.last).padRight(2, '0'));
  if (amount < (zero ? 0 : 1) || amount > 1000000000000) {
    _fail(
      zero
          ? 'Ein nicht negativer EUR-Betrag ist erforderlich.'
          : 'Ein positiver EUR-Betrag ist erforderlich.',
    );
  }
  return amount;
}

String travelLocalTime(Object? input) {
  final value = '${input ?? ''}'.trim();
  final match = RegExp(r'^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})$')
      .firstMatch(value);
  if (match == null) {
    _fail('Tatsächliches Datum und lokale Uhrzeit vollständig angeben.');
  }
  final values = List.generate(5, (index) => int.parse(match[index + 1]!));
  final date = DateTime.utc(
    values[0],
    values[1],
    values[2],
    values[3],
    values[4],
  );
  if (date.year != values[0] ||
      date.month != values[1] ||
      date.day != values[2] ||
      date.hour != values[3] ||
      date.minute != values[4]) {
    _fail('Die lokale Datums- oder Zeitangabe ist ungültig.');
  }
  // Do not reinterpret the entered civil time in this device's own timezone.
  return value;
}

String travelCanonical(dynamic value) {
  if (value == null || value is bool || value is String) {
    return jsonEncode(value);
  }
  if (value is int && value.abs() <= 9007199254740991) return '$value';
  if (value is List) return '[${value.map(travelCanonical).join(',')}]';
  if (value is Map && value.keys.every((key) => key is String)) {
    final keys = value.keys.cast<String>().toList()..sort();
    return '{${keys.map((key) => '${jsonEncode(key)}:${travelCanonical(value[key])}').join(',')}}';
  }
  _fail('Der Reiseauftrag enthält kein eindeutig speicherbares Feld.');
}

Future<String> travelHash(dynamic value) async =>
    (await Sha256().hash(utf8.encode(travelCanonical(value)))).bytes
        .map((v) => v.toRadixString(16).padLeft(2, '0'))
        .join();

Future<Map<String, dynamic>> travelReceipt(
  dynamic raw,
  Map<String, dynamic> expected,
) async {
  final value = businessMap(raw),
      result = businessMap(businessMap(raw)['result']);
  if (value['confirmed'] != true ||
      value['request_id'] != expected['request_id'] ||
      value['actor_id'] != expected['actor_id'] ||
      value['employee_id'] != expected['employee_id'] ||
      value['operation'] != expected['operation'] ||
      value['target_kind'] != expected['target_kind'] ||
      value['target_id'] != expected['target_id'] ||
      value['revision'] is! int ||
      value['revision'] < 1 ||
      value['request_hash'] != expected['request_hash'] ||
      !_travelHash.hasMatch('${value['result_hash']}') ||
      result['id'] != expected['target_id'] ||
      result['employee_id'] != expected['employee_id'] ||
      result['revision'] != value['revision'] ||
      await travelHash(result) != value['result_hash']) {
    _fail('Die Bestätigung gehört nicht zum ursprünglichen Reiseauftrag.');
  }
  return value;
}

Future<VerifiedMailAttachment> travelOriginal(
  Uint8List bytes,
  Map<String, dynamic> expected,
) async {
  if (!_travelHash.hasMatch('${expected['sha256']}') ||
      expected['size'] is! int ||
      expected['size'] < 1 ||
      expected['size'] > 16000000) {
    _fail('Der Originalnachweis ist unvollständig.');
  }
  final hash = (await Sha256().hash(bytes)).bytes
      .map((v) => v.toRadixString(16).padLeft(2, '0'))
      .join();
  if (bytes.length != expected['size'] || hash != expected['sha256']) {
    _fail('Das Original stimmt nicht mit Größe und Prüfsumme überein.');
  }
  return VerifiedMailAttachment(
    bytes: bytes,
    filename: '${expected['filename']}',
    mediaType: '${expected['media_type']}',
    sha256: hash,
  );
}

/// Complete private bodies never enter BusinessSession's general pending map.
class TravelCommand extends ChangeNotifier {
  TravelCommand(
    this.session, {
    required this.employeeId,
    bool Function()? allowed,
  }) : allowed = allowed ?? (() => true) {
    if (!_travelId.hasMatch(employeeId)) {
      _fail('Eine eindeutige Mitarbeiterzuordnung ist erforderlich.');
    }
  }
  final BusinessSession session;
  final String employeeId;
  final bool Function() allowed;
  Map<String, dynamic>? _pending;
  int epoch = 0;
  Map<String, dynamic>? get pending => _pending == null
      ? null
      : {
          for (final key in const [
            'request_id',
            'actor_id',
            'employee_id',
            'operation',
            'target_kind',
            'target_id',
          ])
            key: _pending![key],
        };
  String get stamp => jsonEncode([
    session.api.token,
    session.generation,
    session.projectId,
    session.permissions.toList()..sort(),
    session.capabilities.toList()..sort(),
    session.features.toList()..sort(),
  ]);
  bool get available =>
      allowed() &&
      session.allowed &&
      session.projectId == null &&
      session.hasFeature('travel_allowances') &&
      session.hasModule('travel_allowances');
  void clear() {
    final body = _pending?['body'];
    if (body is Map) body.clear();
    _pending = null;
    epoch++;
    notifyListeners();
  }

  void check(String original, int captured) {
    if (!available || stamp != original || epoch != captured) {
      clear();
      _fail(
        'Sitzung oder Mitarbeiter geändert. Private Reiseeingaben wurden verworfen.',
        403,
      );
    }
  }

  Future<dynamic> read(String path) async {
    final original = stamp, captured = epoch;
    try {
      final result = await session.read(path);
      check(original, captured);
      return result;
    } on ApiException catch (error) {
      if ({401, 403, 410}.contains(error.status)) clear();
      rethrow;
    }
  }

  Future<Map<String, dynamic>> fresh([String right = 'read']) async {
    final original = stamp, captured = epoch;
    if (!available) {
      clear();
      _fail('Die aktuelle Reisefreigabe fehlt.', 403);
    }
    late Map<String, dynamic> actor;
    try {
      actor = businessMap(await session.api.call('/api/me'));
      await session.load();
    } on ApiException catch (error) {
      if ({401, 403, 410}.contains(error.status)) clear();
      rethrow;
    }
    check(original, captured);
    final sources = businessMap(
      await read('$_travelRoot/sources?employee_id=$employeeId'),
    );
    final rights = businessMap(sources['rights']);
    check(original, captured);
    if (!_travelId.hasMatch('${actor['id']}') ||
        businessMap(sources['employee'])['id'] != employeeId ||
        rights['read'] != true ||
        rights[right] != true ||
        right != 'read' &&
            (session.readonly ||
                sources['active'] != true ||
                sources['readonly'] != false)) {
      clear();
      _fail('Die aktuelle Mitarbeiter- oder Reisefreigabe fehlt.', 403);
    }
    return {'actor': actor, 'sources': sources};
  }

  Future<Map<String, dynamic>> submit(
    String path,
    Map<String, dynamic> body, {
    required String operation,
    required String targetKind,
    required String targetId,
    String right = 'write',
    Future<void> Function(Map<String, dynamic>)? validate,
  }) async {
    if (_pending != null)
      _fail('Zuerst die Bestätigung des offenen Reiseauftrags prüfen.', 409);
    if (!_travelId.hasMatch(targetId) ||
        !const ['site', 'trip', 'settlement', 'payment'].contains(targetKind) ||
        !RegExp(r'^[a-z][a-z_.-]{0,39}$').hasMatch(operation) ||
        !path.startsWith('$_travelRoot/') ||
        path.contains(RegExp(r'[?#]')) ||
        body['employee_id'] != employeeId) {
      _fail(
        'Der Reiseauftrag ist nicht eindeutig an Mitarbeiter und Quelle gebunden.',
      );
    }
    final original = stamp, captured = epoch;
    final access = await fresh(right);
    final frozen = {..._copy(body), 'request_id': offlineId()};
    final requestHash = await travelHash([
      operation,
      targetKind,
      targetId,
      frozen,
    ]);
    check(original, captured);
    _pending = {
      'path': path,
      'body': frozen,
      'operation': operation,
      'target_kind': targetKind,
      'target_id': targetId,
      'request_id': frozen['request_id'],
      'employee_id': employeeId,
      'actor_id': businessMap(access['actor'])['id'],
      'request_hash': requestHash,
      'right': right,
      'validate': validate,
      'stamp': original,
      'epoch': captured,
    };
    notifyListeners();
    return send();
  }

  Future<Map<String, dynamic>> status({bool resolve = false}) async {
    final current = _pending;
    if (current == null)
      _fail('Kein unbestätigter Reiseauftrag im Arbeitsspeicher.');
    check(current['stamp'], current['epoch']);
    final access = await fresh();
    if (businessMap(access['actor'])['id'] != current['actor_id']) {
      clear();
      _fail('Der Auftraggeber wurde geändert.', 403);
    }
    final raw = await read('$_travelRoot/requests/${current['request_id']}');
    final receipt = await travelReceipt(raw, current);
    check(current['stamp'], current['epoch']);
    final validator =
        current['validate'] as Future<void> Function(Map<String, dynamic>)?;
    if (validator != null) await validator(businessMap(receipt['result']));
    check(current['stamp'], current['epoch']);
    if (resolve) {
      (current['body'] as Map).clear();
      _pending = null;
      notifyListeners();
    }
    return receipt;
  }

  Future<Map<String, dynamic>> send() async {
    final current = _pending;
    if (current == null)
      _fail('Kein privater Reiseauftrag zum Senden vorhanden.');
    check(current['stamp'], current['epoch']);
    final access = await fresh(current['right']);
    if (businessMap(access['actor'])['id'] != current['actor_id']) {
      clear();
      _fail('Der Auftraggeber wurde geändert.', 403);
    }
    try {
      await session.api.call(
        session.path(current['path']),
        _copy(current['body']),
      );
      check(current['stamp'], current['epoch']);
      return await status(resolve: true);
    } on ApiException catch (error) {
      if ({401, 403, 410}.contains(error.status)) clear();
      rethrow;
    }
  }

  Future<Map<String, dynamic>> retry() async {
    if (_pending == null) _fail('Kein unbestätigter Reiseauftrag vorhanden.');
    try {
      return await status(resolve: true);
    } on ApiException catch (error) {
      if (error.status != 404) rethrow;
    }
    return send();
  }
}

Map<String, dynamic> travelReference(dynamic raw) {
  final value = businessMap(raw);
  if (!_travelId.hasMatch('${value['id']}') ||
      value['revision'] is! int ||
      value['revision'] < 1 ||
      !_travelHash.hasMatch('${value['content_hash']}')) {
    _fail('Die gewählte Reisequelle besitzt keine eindeutige Fassung.');
  }
  return {
    for (final key in const ['id', 'revision', 'content_hash']) key: value[key],
  };
}

List<Map<String, dynamic>> travelTimeOptions(
  dynamic raw,
  String local,
  String timezone,
) {
  final value = businessMap(raw);
  final options = value['options'] is List
      ? (value['options'] as List).map(businessMap).toList()
      : <Map<String, dynamic>>[];
  if (value['local'] != travelLocalTime(local) ||
      value['timezone'] != timezone ||
      value['options'] is! List ||
      options.length > 2 ||
      value['valid'] != options.isNotEmpty ||
      options.any(
        (item) =>
            item['label'] is! String ||
            !RegExp(r'^[+-]\d{2}:\d{2}$').hasMatch('${item['offset']}') ||
            item['instant'] != '$local:00${item['offset']}',
      ) ||
      options.map((item) => item['instant']).toSet().length != options.length) {
    _fail('Die Zeitauflösung gehört nicht zum gewählten Ort und Zeitpunkt.');
  }
  if (options.isEmpty) {
    _fail(
      'Diese lokale Uhrzeit existiert beim Zeitwechsel nicht. Tatsächlichen Zeitpunkt angeben.',
    );
  }
  return options;
}

Map<String, dynamic> travelPreview(
  dynamic raw,
  String employeeId,
  Map<String, dynamic> body,
) {
  final value = businessMap(raw),
      totals = businessMap(businessMap(raw)['totals']);
  final amounts = [
    'meal_base_minor',
    'meal_reduction_minor',
    'meal_allowance_minor',
    'lodging_allowance_minor',
    'requested_minor',
    'tax_free_minor',
    'flat_taxable_minor',
    'individual_taxable_minor',
    'benefit_in_kind_minor',
    'already_paid_minor',
    'remaining_minor',
    'overpaid_minor',
    if ([
      'de_travel_2026_v2',
      'de_travel_2026_v3',
    ].contains(value['rule_version'])) ...[
      'expense_allowance_minor',
      'expense_already_paid_minor',
    ],
  ];
  if (value['employee_id'] != employeeId ||
      const [
        'source_hash',
        'preview_hash',
        'rule_hash',
        'table_hash',
      ].any((key) => !_travelHash.hasMatch('${value[key]}')) ||
      value['rule_version'] is! String ||
      value['days'] is! List ||
      value['blockers'] is! List ||
      value['can_approve'] is! bool ||
      value['can_pay'] is! bool ||
      value['trip_refs'] is! List ||
      travelCanonical(value['trip_refs']) !=
          travelCanonical(body['trip_refs']) ||
      amounts.any(
        (key) =>
            totals[key] is! int || key != 'remaining_minor' && totals[key] < 0,
      ) ||
      (value['blockers'] as List).isNotEmpty && value['can_approve'] == true) {
    _fail(
      'Die Abrechnungsvorschau gehört nicht zu den gewählten Reisen und Quellen.',
    );
  }
  for (final reference in value['trip_refs']) {
    travelReference(reference);
  }
  for (final rawDay in value['days']) {
    final day = businessMap(rawDay);
    if (!RegExp(r'^\d{4}-\d{2}-\d{2}$').hasMatch('${day['date']}') ||
        const [
          'full_minor',
          'base_minor',
          'meal_reduction_minor',
          'meal_allowance_minor',
          'lodging_allowance_minor',
          'benefit_in_kind_minor',
          'absence_seconds',
        ].any((key) => day[key] is! int || day[key] < 0) ||
        day['reasons'] is! List) {
      _fail(
        'Die Tagesherleitung ist unvollständig. Es wird kein Nullanspruch angenommen.',
      );
    }
  }
  if (value['rule_version'] == 'de_travel_2026_v3')
    travelV3Calculation(value, businessItems(body['trip_refs']));
  return value;
}

Map<String, dynamic> travelMixedAssessment(
  dynamic raw,
  List<Map<String, dynamic>> files,
) {
  final value = businessMap(raw);
  const keys = [
    'method',
    'program_sessions',
    'program_complete',
    'cost_allocation_reviewed',
    'source_file_ids',
    'review_note',
  ];
  List<String> originals(dynamic ids) {
    if (ids is! List ||
        ids.isEmpty ||
        ids.length > 100 ||
        ids.toSet().length != ids.length ||
        ids.any(
          (id) =>
              id is! String ||
              !_travelId.hasMatch(id) ||
              !files.any((f) => f['id'] == id),
        ))
      _fail(
        'Jeden Programmpunkt mit tatsächlichen freigegebenen Originalen belegen.',
      );
    return List<String>.from(ids)..sort();
  }

  if (value.keys.any((key) => !keys.contains(key)) ||
      value['method'] != 'documented_program_ratio' ||
      value['program_complete'] is! bool ||
      value['cost_allocation_reviewed'] is! bool ||
      value['review_note'] is! String ||
      (value['review_note'] as String).trim().isEmpty ||
      value['review_note'].length > 2000 ||
      value['program_sessions'] is! List ||
      value['program_sessions'].length < 2 ||
      value['program_sessions'].length > 1000)
    _fail(
      'Das vollständige gemischte Programm mit Prüfvermerk und beiden ausdrücklichen Prüfbestätigungen erfassen.',
    );
  final seen = <String>{}, sessions = <Map<String, dynamic>>[];
  final instant = RegExp(
    r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:Z|[+-]\d{2}:\d{2})$',
  );
  for (final rawItem in value['program_sessions']) {
    final item = businessMap(rawItem), names = item.keys.toList()..sort();
    if (names.join(',') != 'from,id,kind,source_file_ids,to' ||
        item['id'] is! String ||
        !_travelId.hasMatch(item['id']) ||
        !seen.add(item['id']) ||
        !['business', 'private'].contains(item['kind']) ||
        ['from', 'to'].any(
          (key) =>
              item[key] is! String ||
              !instant.hasMatch(item[key]) ||
              DateTime.tryParse(item[key]) == null,
        ) ||
        !DateTime.parse(item['from']).isBefore(DateTime.parse(item['to'])))
      _fail(
        'Programmpunkte benötigen eindeutige tatsächliche Zeiträume, Art und Originale.',
      );
    sessions.add({
      ...item,
      'source_file_ids': originals(item['source_file_ids']),
    });
  }
  final ordered = [...sessions]
    ..sort(
      (a, b) => DateTime.parse(a['from']).compareTo(DateTime.parse(b['from'])),
    );
  for (var i = 1; i < ordered.length; i++)
    if (DateTime.parse(ordered[i]['from'])
        .isBefore(DateTime.parse(ordered[i - 1]['to'])))
      _fail('Programmpunkte dürfen sich zeitlich nicht überschneiden.');
  return {
    ..._copy(value),
    'program_sessions': sessions,
    'source_file_ids': originals(value['source_file_ids']),
    'review_note': value['review_note'].trim(),
  };
}

Map<String, dynamic> travelV3Calculation(
  Map<String, dynamic> value,
  List<Map<String, dynamic>> tripRefs,
) {
  bool share(dynamic raw) {
    final v = businessMap(raw);
    return v['numerator'] is int &&
        v['denominator'] is int &&
        v['denominator'] > 0 &&
        v['numerator'] >= 0 &&
        v['numerator'] <= v['denominator'];
  }

  for (final day in businessItems(value['days']))
    if (day['unapportioned_base_minor'] is! int ||
        day['unapportioned_base_minor'] < 0 ||
        !share(day['business_share']) ||
        day['base_minor'] > day['unapportioned_base_minor'])
      _fail('Der berufliche Tagesanteil und die ungekürzte Bemessung fehlen.');
  for (final entry in const {
    'ground_calendar_sources': 'de_travel_ground_2026_v1',
    'mixed_program_sources': 'de_travel_mixed_program_2026_v1',
  }.entries) {
    final seen = <String>{};
    if (value[entry.key] is! List)
      _fail('Die belegte Programm- oder Ortskalenderherleitung fehlt.');
    for (final source in businessItems(value[entry.key])) {
      final ref = travelReference(source['trip']);
      if (source['rule_version'] != entry.value ||
          !seen.add(ref['id']) ||
          !tripRefs.any((v) => travelCanonical(v) == travelCanonical(ref)))
        _fail(
          'Die Programm- oder Ortskalenderquelle gehört nicht zur ausgewählten Reisefassung.',
        );
      if (entry.key == 'mixed_program_sources' && source['method'] == null) {
        if (source['can_calculate'] != false ||
            source['blockers'] is! List ||
            source['blockers'].isEmpty ||
            value['can_approve'] != false)
          _fail(
            'Die fehlende Programmbeurteilung wurde nicht ausdrücklich blockiert.',
          );
        continue;
      }
      if (!_travelHash.hasMatch('${source['module_hash']}') ||
          !_travelHash.hasMatch('${source['facts_hash']}'))
        _fail(
          'Die unveränderliche Programm- oder Ortskalenderquelle ist unvollständig.',
        );
      if (entry.key == 'mixed_program_sources' &&
          (source['method'] != 'documented_program_ratio' ||
              !share(source) ||
              source['business_seconds'] is! int ||
              source['business_seconds'] < 0 ||
              source['private_seconds'] is! int ||
              source['private_seconds'] < 0 ||
              source['source_file_ids'] is! List ||
              source['source_file_ids'].isEmpty ||
              source['source_file_ids'].toSet().length !=
                  source['source_file_ids'].length ||
              source['source_file_ids'].any(
                (id) => id is! String || !_travelId.hasMatch(id),
              ) ||
              source['can_calculate'] is! bool ||
              source['blockers'] is! List))
        _fail('Die belegte Programmquote ist unvollständig.');
      if (entry.key == 'ground_calendar_sources' &&
          (source['days'] is! Map ||
              source['boundaries'] is! List ||
              businessMap(source['days']).values.any((raw) {
                final day = businessMap(raw);
                return day['absence_seconds'] is! int ||
                    day['absence_seconds'] < 0 ||
                    day['intervals'] is! List ||
                    day['timezone'] is! String;
              })))
        _fail('Der belegte örtliche Reisekalender ist unvollständig.');
    }
  }
  return value;
}

bool travelAvailable(BusinessSession session) =>
    session.projectId == null &&
    session.hasFeature('travel_allowances') &&
    session.hasModule('travel_allowances') &&
    (session.can('personnel.read') || session.can('time.own'));

class BusinessTravelAllowancesPage extends StatefulWidget {
  const BusinessTravelAllowancesPage({
    super.key,
    required this.session,
    required this.employee,
    this.exporter,
  });
  final BusinessSession session;
  final Map<String, dynamic> employee;
  final MailAttachmentExporter? exporter;
  @override
  State<BusinessTravelAllowancesPage> createState() =>
      _BusinessTravelAllowancesPageState();
}

class _BusinessTravelAllowancesPageState
    extends State<BusinessTravelAllowancesPage>
    with WidgetsBindingObserver {
  BusinessSession get session => widget.session;
  late final TravelCommand command;
  Map<String, dynamic> sources = {}, catalog = {};
  List<Map<String, dynamic>> trips = [], settlements = [], payments = [];
  Map<String, dynamic>? current, draft, preview, previewBody, previewPrevious;
  String? currentKind, error, openedStamp;
  int privateEpoch = 0, dialogDepth = 0;
  bool busy = false, suspended = false, historical = false;
  String get employeeId => '${widget.employee['id']}';
  bool get available => !suspended && travelAvailable(session);
  bool can(String right) =>
      businessMap(sources['rights'])[right] == true &&
      sources['active'] == true &&
      sources['readonly'] == false;
  List<Map<String, dynamic>> items(dynamic value) =>
      (value as List? ?? []).map(businessMap).toList();
  String money(dynamic value) => value is int
      ? businessMoney((value / 100).toStringAsFixed(2))
      : 'Noch nicht bestimmt';
  Map<String, String> choices(
    dynamic values, [
    String Function(Map<String, dynamic>)? label,
  ]) => {
    for (final item in items(values))
      '${item['id']}':
          label?.call(item) ??
          '${item['name'] ?? item['filename'] ?? item['id']}',
  };
  @override
  void initState() {
    super.initState();
    command = TravelCommand(
      session,
      employeeId: employeeId,
      allowed: () => mounted && !suspended,
    );
    command.addListener(privateChanged);
    session.addListener(sessionChanged);
    WidgetsBinding.instance.addObserver(this);
    run(load);
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    session.removeListener(sessionChanged);
    command.removeListener(privateChanged);
    command.clear();
    command.dispose();
    sources.clear();
    catalog.clear();
    draft?.clear();
    super.dispose();
  }

  void wipe() {
    sources = {};
    catalog = {};
    trips = [];
    settlements = [];
    payments = [];
    current = null;
    currentKind = null;
    draft?.clear();
    draft = null;
    preview = null;
    previewBody = null;
    previewPrevious = null;
    if (dialogDepth > 0 && mounted) {
      final page = ModalRoute.of(context);
      Navigator.of(
        context,
        rootNavigator: true,
      ).popUntil((route) => route == page || route.isFirst);
    }
  }

  void privateChanged() {
    if (!mounted) return;
    if (privateEpoch != command.epoch) {
      privateEpoch = command.epoch;
      wipe();
    }
    setState(() {});
  }

  void sessionChanged() {
    if (!mounted) return;
    if (!available || openedStamp != null && openedStamp != command.stamp)
      command.clear();
    if (mounted) setState(() {});
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state != AppLifecycleState.resumed) {
      suspended = true;
      command.clear();
    } else {
      suspended = false;
      run(load);
    }
  }

  Future<void> run(Future<void> Function() action) async {
    if (busy || !mounted) return;
    setState(() => busy = true);
    try {
      await action();
      if (mounted) setState(() => error = null);
    } catch (e) {
      if (e is ApiException && {401, 403, 410}.contains(e.status))
        command.clear();
      if (mounted) setState(() => error = e is ApiException ? e.message : '$e');
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  Future<void> fresh([String right = 'read']) async {
    final access = await command.fresh(right);
    sources = businessMap(access['sources']);
    openedStamp = command.stamp;
  }

  Future<Map<String, dynamic>> get(String path) async =>
      businessMap(await command.read('$_travelRoot$path'));
  Future<void> load() async {
    await fresh();
    final original = command.stamp, captured = command.epoch;
    final values = await Future.wait([
      get('/catalog'),
      get('/trips?employee_id=$employeeId'),
      get('/settlements?employee_id=$employeeId'),
      get('/payments?employee_id=$employeeId'),
    ]);
    command.check(original, captured);
    if (values
            .skip(1)
            .any(
              (value) =>
                  value['employee_id'] != employeeId || value['items'] is! List,
            ) ||
        values[0]['rates'] is! List) {
      _fail('Die Reiseübersicht gehört nicht zum geöffneten Mitarbeiter.');
    }
    catalog = values[0];
    trips = items(values[1]['items']);
    settlements = items(values[2]['items']);
    payments = items(values[3]['items']);
    current = null;
    currentKind = null;
    preview = null;
    previewBody = null;
    previewPrevious = null;
    if (mounted) setState(() {});
  }

  Future<void> edit(
    String title,
    List<BusinessField> fields,
    Future<void> Function(Map<String, dynamic>) save, {
    String right = 'write',
    String? saveLabel,
  }) async {
    await fresh(right);
    if (!mounted) return;
    final original = command.stamp, captured = command.epoch;
    dialogDepth++;
    try {
      await showDialog<bool>(
        context: context,
        barrierDismissible: false,
        builder: (_) => BusinessEditor(
          session: session,
          title: title,
          fields: fields,
          readAllowed: () => available && command.epoch == captured,
          saveLabel: saveLabel ?? 'Angaben übernehmen',
          onSave: (value) async {
            command.check(original, captured);
            if (command.pending != null) {
              // BusinessEditor labels this explicit action as an unchanged
              // retry after the uncertain exception below. The private
              // controller first reads the original status and never creates
              // a replacement nonce or copies its body into BusinessSession.
              await command.retry();
              command.check(original, captured);
              return;
            }
            try {
              await save(value);
              command.check(original, captured);
            } on ApiException catch (error) {
              if (command.pending != null) {
                throw ApiException(
                  0,
                  '${error.message} Die Bestätigung des ursprünglichen Auftrags ist noch offen. Unverändertes Wiederholen prüft zuerst dessen Status; alternativ schließen und den Status separat prüfen.',
                );
              }
              rethrow;
            }
          },
        ),
      );
    } finally {
      dialogDepth--;
    }
    if (mounted) setState(() {});
  }

  Future<void> submit(
    String path,
    Map<String, dynamic> body,
    String operation,
    String kind,
    String id, {
    String right = 'write',
  }) async {
    await command.submit(
      '$_travelRoot$path',
      {'employee_id': employeeId, ...body},
      operation: operation,
      targetKind: kind,
      targetId: id,
      right: right,
    );
  }

  List<String> requireFiles(dynamic raw) {
    final values = (raw as List? ?? []).map((id) => '$id').toList();
    if (values.isEmpty ||
        values.any(
          (id) => !items(sources['files']).any(
            (file) => file['id'] == id && file['employee_id'] == employeeId,
          ),
        )) {
      _fail('Mindestens ein tatsächlich freigegebenes Original auswählen.');
    }
    return values;
  }

  BusinessField text(
    String name,
    String label, [
    dynamic initial,
    bool required = true,
  ]) => BusinessField(name, label, initial: initial, required: required);
  BusinessField date(
    String name,
    String label, [
    dynamic initial,
    bool required = true,
  ]) => BusinessField(
    name,
    label,
    type: BusinessInput.date,
    initial: initial == '' ? null : initial,
    required: required,
  );
  BusinessField choice(
    String name,
    String label,
    Map<String, String> values, [
    dynamic initial,
    bool required = true,
  ]) => BusinessField(
    name,
    label,
    type: BusinessInput.choice,
    choices: values,
    initial: initial == '' ? null : initial,
    required: required,
  );
  BusinessField multiple(
    String name,
    String label,
    Map<String, String> values, [
    dynamic initial,
  ]) => BusinessField(
    name,
    label,
    type: BusinessInput.multiple,
    choices: values,
    initial: initial ?? const [],
  );
  Future<List<Map<String, dynamic>>> editFrequency(dynamic previous) async {
    final periods = items(previous).map(_copy).toList();
    dialogDepth++;
    try {
      final result = await showDialog<List<Map<String, dynamic>>>(
        context: context,
        barrierDismissible: false,
        builder: (dialogContext) => StatefulBuilder(
          builder: (context, update) {
            Future<void> editPeriod([int? index]) async {
              final old = index == null ? <String, dynamic>{} : periods[index];
              await edit(
                'Belegte Häufigkeitsphase',
                [
                  date('from', 'Häufigkeitsphase gültig ab', old['from']),
                  date(
                    'to',
                    'Häufigkeitsphase gültig bis, falls beendet',
                    old['to'],
                    false,
                  ),
                  BusinessField(
                    'days_per_week',
                    'Einsatztage pro Woche in dieser Phase',
                    type: BusinessInput.integer,
                    initial: old['days_per_week'],
                    required: true,
                  ),
                  multiple(
                    'source_file_ids',
                    'Originale dieser Häufigkeitsphase',
                    choices(sources['files']),
                    old['source_file_ids'],
                  ),
                ],
                (value) async {
                  if (value['days_per_week'] < 0 || value['days_per_week'] > 7)
                    _fail(
                      'Einsatztage müssen zwischen null und sieben liegen.',
                    );
                  value['source_file_ids'] = requireFiles(
                    value['source_file_ids'],
                  );
                  value['to'] = value['to'] == '' ? null : value['to'];
                  if (index == null) {
                    periods.add(value);
                  } else {
                    periods[index] = value;
                  }
                },
              );
              if (dialogContext.mounted) update(() {});
            }

            return AlertDialog(
              title: const Text('Datierte Einsatzhäufigkeit'),
              content: SizedBox(
                width: 620,
                child: SingleChildScrollView(
                  child: Column(
                    mainAxisSize: MainAxisSize.min,
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const Text(
                        'Die Phasen müssen ab dem Zuordnungsbeginn lückenlos sein. Jede Änderung braucht einen datierten Originalnachweis.',
                      ),
                      for (var index = 0; index < periods.length; index++)
                        ListTile(
                          title: Text(
                            '${periods[index]['from']} – ${periods[index]['to'] ?? 'offen'}',
                          ),
                          subtitle: Text(
                            '${periods[index]['days_per_week']} belegte Einsatztage pro Woche',
                          ),
                          onTap: () => editPeriod(index),
                          trailing: IconButton(
                            tooltip: 'Häufigkeitsphase entfernen',
                            icon: const Icon(Icons.delete_outline),
                            onPressed: () =>
                                update(() => periods.removeAt(index)),
                          ),
                        ),
                      OutlinedButton(
                        onPressed: editPeriod,
                        child: const Text('Häufigkeitsphase hinzufügen'),
                      ),
                    ],
                  ),
                ),
              ),
              actions: [
                TextButton(
                  onPressed: () => Navigator.pop(dialogContext),
                  child: const Text('Abbrechen'),
                ),
                FilledButton(
                  onPressed: periods.isEmpty
                      ? null
                      : () => Navigator.pop(dialogContext, periods),
                  child: const Text('Belegte Phasen übernehmen'),
                ),
              ],
            );
          },
        ),
      );
      if (result == null)
        _fail('Die datierten Häufigkeitsphasen wurden nicht übernommen.');
      return result;
    } finally {
      dialogDepth--;
    }
  }

  Future<void> editSite([Map<String, dynamic>? previous]) async {
    final old = businessMap(previous?['details']),
        id = '${previous?['id'] ?? offlineId()}';
    await fresh('write');
    await edit(
      previous == null
          ? 'Stätte belegt erfassen'
          : 'Stättennachweis korrigieren',
      [
        text('name', 'Bezeichnung der Stätte', old['name']),
        choice('kind', 'Art der Stätte', const {
          'home': 'Wohnung',
          'first_workplace': 'Erste Tätigkeitsstätte',
          'external_fixed': 'Auswärtige feste Stätte',
          'mobile': 'Mobile Tätigkeit',
          'wide_area': 'Weiträumiges Gebiet',
        }, old['kind']),
        BusinessField(
          'address',
          'Tatsächliche Anschrift oder Ortsbeschreibung',
          type: BusinessInput.multiline,
          initial: old['address'],
          required: true,
        ),
        choice(
          'rate_id',
          'Land und Gebiet',
          choices(
            catalog['rates'],
            (rate) => '${rate['country']} · ${rate['region'] ?? ''}',
          ),
          old['rate_id'],
        ),
        text(
          'timezone',
          'Zeitzone am Ort (IANA, z. B. Europe/Berlin)',
          old['timezone'],
        ),
        date('effective_from', 'Zuordnung gültig ab', old['effective_from']),
        date(
          'effective_to',
          'Gültig bis, falls beendet',
          old['effective_to'],
          false,
        ),
        BusinessField(
          'assignment_basis',
          'Begründung und Nachweis der Zuordnung',
          type: BusinessInput.multiline,
          initial: old['assignment_basis'],
          required: true,
        ),
        BusinessField(
          'regular_days_per_week',
          'Belegte tatsächliche Einsatztage pro Woche',
          type: BusinessInput.integer,
          initial: old['regular_days_per_week'],
          required: true,
        ),
        BusinessField(
          'frequency_changed',
          'Einsatzhäufigkeit hat sich geändert',
          type: BusinessInput.toggle,
          initial: items(old['frequency_periods']).isNotEmpty,
        ),
        date(
          'history_complete_from',
          'Vorgeschichte vollständig geprüft ab',
          old['history_complete_from'],
        ),
        BusinessField(
          'prior_visit_dates',
          'Frühere belegte Besuchstage, ein Datum YYYY-MM-DD je Zeile',
          type: BusinessInput.multiline,
          initial: (old['prior_visit_dates'] as List? ?? []).join('\n'),
        ),
        multiple(
          'source_file_ids',
          'Originalnachweise der Stätte',
          choices(sources['files']),
          old['source_file_ids'],
        ),
        if (previous != null) ...[
          choice('status', 'Nachweisstatus', const {
            'active': 'Gültig',
            'void': 'Begründet aufgehoben',
          }, previous['status']),
          text('correction_reason', 'Korrekturgrund'),
        ],
      ],
      (values) async {
        final details = _copy(values);
        final reason = details.remove('correction_reason') ?? '';
        final status = details.remove('status') ?? 'active';
        final frequencyChanged = details.remove('frequency_changed') == true;
        if (frequencyChanged)
          details['frequency_periods'] = await editFrequency(
            old['frequency_periods'],
          );
        details['source_file_ids'] = requireFiles(details['source_file_ids']);
        details['prior_visit_dates'] = '${details['prior_visit_dates'] ?? ''}'
            .split(RegExp(r'\s+'))
            .where((item) => item.isNotEmpty)
            .toList();
        if ((details['prior_visit_dates'] as List).any(
          (item) => !RegExp(r'^\d{4}-\d{2}-\d{2}$').hasMatch('$item'),
        ))
          _fail('Frühere Besuchstage als vollständige Datumsangabe erfassen.');
        if (details['regular_days_per_week'] < 0 ||
            details['regular_days_per_week'] > 7)
          _fail(
            'Tatsächliche Einsatztage müssen zwischen null und sieben liegen.',
          );
        await submit(
          '/sites',
          {
            'id': id,
            'revision': previous?['revision'] ?? 0,
            'status': status,
            'details': details,
            'correction_reason': reason,
          },
          'site.save',
          'site',
          id,
        );
      },
      saveLabel: 'Nachweis unveränderlich speichern',
    );
    if (command.pending == null) await load();
  }

  Future<void> openDetail(String kind, String id, [int? revision]) async {
    await fresh();
    final result = await get(
      '/$kind/$id${revision == null ? '' : '?revision=$revision'}',
    );
    final item = businessMap(result['item']);
    if (item['id'] != id ||
        item['employee_id'] != employeeId ||
        item['revision'] is! int ||
        revision != null && item['revision'] != revision)
      _fail('Die historische Ansicht gehört nicht zur gewählten Reisequelle.');
    if (kind == 'settlements' &&
        businessMap(item['calculation'])['rule_version'] == 'de_travel_2026_v3')
      travelV3Calculation(
        businessMap(item['calculation']),
        items(businessMap(item['details'])['trip_refs']),
      );
    current = item;
    currentKind = kind;
    historical = revision != null;
    draft = null;
    preview = null;
    previewBody = null;
    previewPrevious = null;
    if (mounted) setState(() {});
  }

  Future<void> history() async {
    final kind = currentKind!, id = '${current!['id']}';
    final result = await get('/$kind/$id/history');
    if (result['id'] != id || result['employee_id'] != employeeId)
      _fail('Historie gehört nicht zur gewählten Quelle.');
    if (!mounted) return;
    final selected = await showDialog<int>(
      context: context,
      builder: (context) => SimpleDialog(
        title: const Text('Unveränderte Fassungen'),
        children: [
          for (final item in items(result['items']))
            SimpleDialogOption(
              onPressed: () => Navigator.pop(context, item['revision']),
              child: Text(
                'Fassung ${item['revision']} · ${travelStatuses[item['status']] ?? item['status'] ?? ''}',
              ),
            ),
        ],
      ),
    );
    if (selected != null) await openDetail(kind, id, selected);
  }

  List<BusinessField> timeFields(
    String prefix,
    String label, [
    String instant = '',
  ]) => [
    date(
      '${prefix}_date',
      '$label · Datum',
      instant.isEmpty ? null : instant.substring(0, 10),
    ),
    text(
      '${prefix}_time',
      '$label · Ortszeit HH:mm',
      instant.isEmpty ? null : instant.substring(11, 16),
    ),
  ];
  Future<String> resolveTime(
    Map<String, dynamic> values,
    String key,
    String timezone,
  ) async {
    final local = travelLocalTime(
      '${values['${key}_date']}T${values['${key}_time']}',
    );
    final options = travelTimeOptions(
      await get(
        '/time-options?local=${Uri.encodeQueryComponent(local)}&timezone=${Uri.encodeQueryComponent(timezone)}',
      ),
      local,
      timezone,
    );
    if (options.length == 1) return '${options.single['instant']}';
    if (!mounted) _fail('Die Reiseansicht wurde geschlossen.', 403);
    dialogDepth++;
    String? selected;
    try {
      selected = await showDialog<String>(
        context: context,
        barrierDismissible: false,
        builder: (context) => SimpleDialog(
          title: Text('Tatsächliche Zeitlage · $local'),
          children: [
            const Padding(
              padding: EdgeInsets.all(16),
              child: Text('Diese Ortszeit kommt beim Zeitwechsel zweimal vor.'),
            ),
            for (final option in options)
              SimpleDialogOption(
                onPressed: () => Navigator.pop(context, option['instant']),
                child: Text('${option['label']}'),
              ),
            SimpleDialogOption(
              onPressed: () => Navigator.pop(context),
              child: const Text('Abbrechen'),
            ),
          ],
        ),
      );
    } finally {
      dialogDepth--;
    }
    if (selected == null ||
        !options.any((option) => option['instant'] == selected))
      _fail('Tatsächliche Zeitlage wurde noch nicht ausgewählt.');
    return selected;
  }

  void startTrip([Map<String, dynamic>? previous]) {
    draft = {
      'id': previous?['id'] ?? offlineId(),
      'revision': previous?['revision'] ?? 0,
      'correction_reason': '',
      'details': _copy(
        businessMap(previous?['details']).isEmpty
            ? {
                'purpose': '',
                'project_id': null,
                'departed_at': '',
                'returned_at': '',
                'timezone': '',
                'source_file_ids': [],
                'home_site_ref': null,
                'first_workplace_ref': null,
                'segments': [],
                'overnights': [],
                'meals': [],
                'expense_refs': [],
                'requested_meal_minor': 0,
                'requested_lodging_minor': 0,
                'tax_choice': 'tax_free_only',
                'private_intervals': [],
              }
            : businessMap(previous?['details']),
      ),
    };
    current = null;
    currentKind = null;
    preview = null;
    previewBody = null;
    previewPrevious = null;
    setState(() {});
  }

  Future<void> mixedEditor() async {
    await fresh('write');
    final captured = draft!,
        details = businessMap(draft!['details']),
        old = businessMap(businessMap(draft!['details'])['mixed_assessment']);
    await edit(
      'Gemischtes Programm belegt beurteilen',
      [
        multiple(
          'source_file_ids',
          'Originale des vollständigen Reiseprogramms',
          choices(sources['files']),
          old['source_file_ids'],
        ),
        text(
          'review_note',
          'Begründung der beruflichen und privaten Programmzuordnung',
          old['review_note'],
        ),
        const BusinessField(
          'program_complete',
          'Das gesamte berufliche und private Programm ist vollständig belegt.',
          type: BusinessInput.toggle,
          initial: false,
        ),
        const BusinessField(
          'cost_allocation_reviewed',
          'Die Originalkosten sind getrennt beruflich, privat und bereitgestellt geprüft.',
          type: BusinessInput.toggle,
          initial: false,
        ),
      ],
      (values) async {
        if (!identical(draft, captured))
          _fail('Der Reiseentwurf wurde geschlossen.', 403);
        final note = '${values['review_note'] ?? ''}'.trim();
        if (note.isEmpty || note.length > 2000)
          _fail('Die belegte Programmzuordnung vollständig begründen.');
        details['mixed_assessment'] = {
          'method': 'documented_program_ratio',
          'program_sessions': items(old['program_sessions']),
          'source_file_ids': requireFiles(values['source_file_ids']),
          'review_note': note,
          'program_complete': values['program_complete'] == true,
          'cost_allocation_reviewed':
              values['cost_allocation_reviewed'] == true,
        };
        captured['details'] = details;
      },
      saveLabel: 'Programmbeurteilung in den Entwurf übernehmen',
    );
  }

  Future<void> programEditor([
    Map<String, dynamic>? previous,
    int? index,
  ]) async {
    await fresh('write');
    final captured = draft!,
        details = businessMap(draft!['details']),
        old = previous ?? <String, dynamic>{};
    final assessment = businessMap(details['mixed_assessment']);
    await edit(
      'Belegter Programmpunkt',
      [
        ...timeFields('from', 'Programmbeginn', '${old['from'] ?? ''}'),
        ...timeFields('to', 'Programmende', '${old['to'] ?? ''}'),
        text('timezone', 'Zeitzone am Programmort (IANA)', details['timezone']),
        choice('kind', 'Belegte Art des Programmpunkts', const {
          'business': 'Berufliches Programm',
          'private': 'Privates Programm',
        }, old['kind']),
        multiple(
          'source_file_ids',
          'Originale dieses Programmpunkts',
          choices(sources['files']),
          old['source_file_ids'],
        ),
      ],
      (values) async {
        final files = requireFiles(values['source_file_ids']),
            from = await resolveTime(values, 'from', values['timezone']),
            to = await resolveTime(values, 'to', values['timezone']);
        if (!identical(draft, captured))
          _fail('Die Programmbeurteilung wurde geschlossen.', 403);
        if (!DateTime.parse(from).isBefore(DateTime.parse(to)))
          _fail('Der Programmbeginn muss vor dem Ende liegen.');
        final item = {
              'id': old['id'] ?? offlineId(),
              'from': from,
              'to': to,
              'kind': values['kind'],
              'source_file_ids': files,
            },
            list = items(assessment['program_sessions']);
        if (index == null) {
          list.add(item);
        } else {
          list[index] = item;
        }
        assessment.addAll({
          'program_sessions': list,
          'program_complete': false,
          'cost_allocation_reviewed': false,
        });
        details['mixed_assessment'] = assessment;
        captured['details'] = details;
      },
      saveLabel: 'Programmpunkt in den Entwurf übernehmen',
    );
  }

  Future<void> tripBasics() async {
    await fresh('write');
    final captured = draft!, value = businessMap(draft!['details']);
    final siteChoices = choices(
      sources['sites'],
      (site) => '${businessMap(site['details'])['name'] ?? site['name']}',
    );
    await edit(
      'Reisegrunddaten',
      [
        BusinessField(
          'purpose',
          'Tatsächlicher Reisezweck',
          type: BusinessInput.multiline,
          initial: value['purpose'],
          required: true,
        ),
        choice(
          'project_id',
          'Projektbezug',
          choices(sources['projects']),
          value['project_id'],
          false,
        ),
        text(
          'timezone',
          'Zeitzone des Reisezeitraums (IANA)',
          value['timezone'],
        ),
        ...timeFields(
          'departed_at',
          'Tatsächlicher Beginn',
          '${value['departed_at']}',
        ),
        ...timeFields(
          'returned_at',
          'Tatsächliches Ende',
          '${value['returned_at']}',
        ),
        choice(
          'home_site_ref',
          'Belegte Wohnung',
          siteChoices,
          businessMap(value['home_site_ref'])['id'],
          false,
        ),
        choice(
          'first_workplace_ref',
          'Belegte erste Tätigkeitsstätte',
          siteChoices,
          businessMap(value['first_workplace_ref'])['id'],
          false,
        ),
        multiple(
          'source_file_ids',
          'Reiseoriginale',
          choices(sources['files']),
          value['source_file_ids'],
        ),
        multiple(
          'expense_refs',
          'Bereits erfasste tatsächliche Auslagen',
          choices(
            sources['expenses'],
            (item) => '${item['purpose'] ?? item['id']}',
          ),
          items(value['expense_refs']).map((item) => item['id']).toList(),
        ),
        text(
          'requested_meal',
          'Beantragte Verpflegung EUR',
          (value['requested_meal_minor'] / 100).toStringAsFixed(2),
        ),
        text(
          'requested_lodging',
          'Beantragte Unterkunft EUR',
          (value['requested_lodging_minor'] / 100).toStringAsFixed(2),
        ),
        choice('tax_choice', 'Beantragte steuerliche Behandlung', const {
          'tax_free_only': 'Nur belegbar steuerfreie Erstattung',
          'flat_25': 'Pauschalversteuerung ausdrücklich prüfen',
          'individual': 'Individuelle Lohnversteuerung ausdrücklich prüfen',
        }, value['tax_choice']),
        if (captured['revision'] > 0)
          text(
            'correction_reason',
            'Korrekturgrund',
            captured['correction_reason'],
          ),
      ],
      (values) async {
        final from = await resolveTime(
          values,
          'departed_at',
          values['timezone'],
        );
        final to = await resolveTime(values, 'returned_at', values['timezone']);
        if (!identical(draft, captured))
          _fail('Der Reiseentwurf wurde geschlossen.', 403);
        final details = businessMap(captured['details']);
        for (final key in const ['purpose', 'timezone', 'tax_choice']) {
          details[key] = values[key];
        }
        details.addAll({
          'departed_at': from,
          'returned_at': to,
          'project_id': values['project_id'],
          'source_file_ids': requireFiles(values['source_file_ids']),
          'requested_meal_minor': travelMinor(
            values['requested_meal'],
            zero: true,
          ),
          'requested_lodging_minor': travelMinor(
            values['requested_lodging'],
            zero: true,
          ),
        });
        for (final key in const ['home_site_ref', 'first_workplace_ref']) {
          details[key] = values[key] == null
              ? null
              : travelReference(
                  items(sources['sites'])
                      .firstWhere((item) => item['id'] == values[key]),
                );
        }
        details['expense_refs'] = (values['expense_refs'] as List)
            .map(
              (id) => travelReference(
                items(sources['expenses'])
                    .firstWhere((item) => item['id'] == id),
              ),
            )
            .toList();
        captured['details'] = details;
        captured['correction_reason'] = values['correction_reason'] ?? '';
      },
    );
  }

  List<Map<String, dynamic>> expensePositions() {
    final selected = items(businessMap(draft!['details'])['expense_refs'])
        .map((item) => item['id'])
        .toSet();
    return [
      for (final expense in items(
        sources['expenses'],
      ).where((value) => selected.contains(value['id'])))
        for (final item in items(expense['items']))
          {
            'expense': expense,
            'item': item,
            'id': '${expense['id']}:${item['receipt_file_id']}',
            'name':
                '${expense['purpose']} · ${item['date']} · ${item['description']} · ${money(item['amount_minor'])}',
          },
    ];
  }

  Future<void> expenseEditor([
    Map<String, dynamic>? previous,
    int? index,
  ]) async {
    await fresh('write');
    final captured = draft!,
        old = previous ?? <String, dynamic>{},
        positions = expensePositions();
    if (positions.isEmpty)
      _fail(
        'Zuerst vorhandene tatsächliche Auslagen in den Reisegrunddaten auswählen.',
      );
    await edit(
      'Belegte Auslagenposition aufteilen',
      [
        choice(
          'position',
          'Tatsächlich gespeicherte Auslagenposition',
          choices(positions),
          previous == null
              ? null
              : '${businessMap(old['expense_ref'])['id']}:${old['receipt_file_id']}',
        ),
        choice('kind', 'Belegte Auslagenart', const {
          'transport': 'Beförderung',
          'lodging': 'Unterkunft',
          'incidental': 'Reisenebenkosten',
        }, old['kind']),
        for (final entry in const {
          'business_minor': 'Tatsächlich beruflicher Anteil EUR',
          'private_minor': 'Tatsächlich privater Anteil EUR',
          'provided_minor':
              'Vom Arbeitgeber oder Dritten bereitgestellter Anteil EUR',
        }.entries)
          text(
            entry.key,
            entry.value,
            previous == null ? null : (old[entry.key] / 100).toStringAsFixed(2),
          ),
        text(
          'review_note',
          'Nachweis und Begründung der vollständigen Aufteilung',
          old['review_note'],
        ),
      ],
      (values) async {
        if (!identical(draft, captured))
          _fail('Der Reiseentwurf wurde geschlossen.', 403);
        final position = positions.firstWhere(
          (item) => item['id'] == values['position'],
        );
        final value = <String, dynamic>{
          'expense_ref': travelReference(businessMap(position['expense'])),
          'receipt_file_id': businessMap(position['item'])['receipt_file_id'],
          'kind': values['kind'],
          'review_note': values['review_note'],
          for (final key in const [
            'business_minor',
            'private_minor',
            'provided_minor',
          ])
            key: travelMinor(values[key], zero: true),
        };
        if (value['business_minor'] +
                value['private_minor'] +
                value['provided_minor'] !=
            businessMap(position['item'])['amount_minor'])
          _fail(
            'Beruflicher, privater und bereitgestellter Anteil müssen genau den gespeicherten Originalbetrag ergeben.',
          );
        final details = businessMap(captured['details']),
            list = items(details['expense_allocations']);
        if (list.indexed.any(
          (entry) =>
              entry.$1 != index &&
              businessMap(entry.$2['expense_ref'])['id'] ==
                  businessMap(value['expense_ref'])['id'] &&
              entry.$2['receipt_file_id'] == value['receipt_file_id'],
        ))
          _fail('Diese Originalposition ist bereits aufgeteilt.');
        if (index == null) {
          list.add(value);
        } else {
          list[index] = value;
        }
        details['expense_allocations'] = list;
        captured['details'] = details;
      },
      saveLabel: 'Belegte Aufteilung übernehmen',
    );
  }

  Future<void> transportEditor(
    String kind, [
    Map<String, dynamic>? previous,
    int? index,
  ]) async {
    await fresh('write');
    final captured = draft!,
        old = previous ?? <String, dynamic>{},
        details = businessMap(captured['details']);
    final segments = items(details['segments'])
        .where((item) => item['transport'] == kind)
        .toList();
    if (segments.isEmpty)
      _fail(
        'Zuerst die tatsächlichen Flug- beziehungsweise Schiffsabschnitte als Reisestationen erfassen.',
      );
    final sites = choices(
          sources['sites'],
          (item) => '${businessMap(item['details'])['name']}',
        ),
        segmentChoices = <String, String>{
          for (final indexed in segments.indexed)
            '${indexed.$2['id']}':
                '${kind == 'flight' ? 'Flug' : 'Schiff'} ${indexed.$1 + 1} · ${indexed.$2['from']} – ${indexed.$2['to']}',
        };
    final nights = choices(
      details['overnights'],
      (item) => '${item['date']} · belegte Übernachtung',
    );
    final fields = <BusinessField>[
      multiple(
        'segment_ids',
        'Zu dieser zusammenhängenden Beförderung gehörende Abschnitte',
        segmentChoices,
        kind == 'flight'
            ? items(old['legs']).map((item) => item['segment_id']).toList()
            : old['segment_ids'],
      ),
    ];
    if (kind == 'flight') {
      for (final indexed in segments.indexed) {
        final at = indexed.$1, segment = indexed.$2;
        final legs = items(old['legs'])
                .where((item) => item['segment_id'] == segment['id']),
            stops = items(old['stopovers'])
                .where((item) => item['after_segment_id'] == segment['id']);
        final leg = legs.isEmpty ? <String, dynamic>{} : legs.first,
            stop = stops.isEmpty ? <String, dynamic>{} : stops.first;
        fields.addAll([
          choice(
            'departure_$at',
            'Flugabschnitt ${at + 1} · tatsächlicher Abflugort',
            sites,
            businessMap(leg['departure_site_ref'])['id'],
            false,
          ),
          choice(
            'arrival_$at',
            'Flugabschnitt ${at + 1} · tatsächlicher Ankunftsort',
            sites,
            businessMap(leg['arrival_site_ref'])['id'],
            false,
          ),
          multiple(
            'nights_$at',
            'Notwendige Zwischenübernachtungen nach Flugabschnitt ${at + 1}',
            nights,
            stop['overnight_ids'],
          ),
        ]);
      }
    } else {
      fields.addAll([
        choice(
          'departure_site',
          'Tatsächlicher Einschiffungsort',
          sites,
          businessMap(old['departure_site_ref'])['id'],
        ),
        choice(
          'arrival_site',
          'Tatsächlicher Ausschiffungsort',
          sites,
          businessMap(old['arrival_site_ref'])['id'],
        ),
        choice('role', 'Belegte Rolle während der Schiffsreise', const {
          'passenger': 'Reisender',
          'german_state_crew': 'Besatzung eines deutschen staatlichen Schiffs',
          'german_merchant_crew': 'Besatzung eines deutschen Handelsschiffs',
        }, old['role']),
        multiple(
          'high_seas_segment_ids',
          'Belegte Abschnitte auf hoher See',
          segmentChoices,
          old['high_seas_segment_ids'],
        ),
      ]);
    }
    fields.add(
      multiple(
        'source_file_ids',
        'Originale dieser zusammenhängenden Beförderung',
        choices(sources['files']),
        old['source_file_ids'],
      ),
    );
    await edit(
      kind == 'flight'
          ? 'Zusammenhängende Flugreise belegen'
          : 'Zusammenhängende Schiffsreise belegen',
      fields,
      (values) async {
        if (!identical(draft, captured))
          _fail('Der Reiseentwurf wurde geschlossen.', 403);
        final selected = values['segment_ids'] as List;
        if (selected.isEmpty)
          _fail(
            'Die tatsächlich zugehörigen Beförderungsabschnitte auswählen.',
          );
        Map<String, dynamic> ref(dynamic siteId) => travelReference(
          items(sources['sites'])
              .firstWhere((site) => site['id'] == siteId, orElse: () => {}),
        );
        final value = <String, dynamic>{
          'id': old['id'] ?? offlineId(),
          'kind': kind,
          'source_file_ids': requireFiles(values['source_file_ids']),
        };
        if (kind == 'flight') {
          value['legs'] = [
            for (final indexed in segments.indexed)
              if (selected.contains(indexed.$2['id']))
                {
                  'segment_id': indexed.$2['id'],
                  'departure_site_ref': ref(values['departure_${indexed.$1}']),
                  'arrival_site_ref': ref(values['arrival_${indexed.$1}']),
                },
          ];
          value['stopovers'] = [
            for (final indexed in segments.indexed)
              if (selected.contains(indexed.$2['id']) &&
                  (values['nights_${indexed.$1}'] as List).isNotEmpty)
                {
                  'after_segment_id': indexed.$2['id'],
                  'overnight_ids': values['nights_${indexed.$1}'],
                },
          ];
        } else {
          value.addAll({
            'segment_ids': selected,
            'departure_site_ref': ref(values['departure_site']),
            'arrival_site_ref': ref(values['arrival_site']),
            'role': values['role'],
            'high_seas_segment_ids': values['high_seas_segment_ids'],
          });
        }
        final list = items(details['transport_facts']);
        if (index == null) {
          list.add(value);
        } else {
          list[index] = value;
        }
        details['transport_facts'] = list;
        captured['details'] = details;
      },
      saveLabel: 'Belegte Beförderung übernehmen',
    );
  }

  Future<void> tripRow(
    String kind, [
    Map<String, dynamic>? previous,
    int? index,
  ]) async {
    await fresh('write');
    final captured = draft!, old = previous ?? <String, dynamic>{};
    final details = businessMap(captured['details']);
    final siteChoices = choices(
      sources['sites'],
      (site) => '${businessMap(site['details'])['name'] ?? site['name']}',
    );
    List<BusinessField> fields;
    if (kind == 'segments' || kind == 'private_intervals') {
      fields = [
        ...timeFields('from', 'Beginn', '${old['from'] ?? ''}'),
        ...timeFields('to', 'Ende', '${old['to'] ?? ''}'),
        text('timezone', 'Zeitzone am Ort (IANA)', details['timezone']),
        if (kind == 'segments') ...[
          choice(
            'site_id',
            'Tatsächliche Stätte',
            siteChoices,
            businessMap(old['site_ref'])['id'],
          ),
          choice('activity', 'Tatsächliche Tätigkeit', const {
            'work': 'Tätigkeit',
            'transit': 'Unterwegs',
            'stay': 'Aufenthalt',
          }, old['activity']),
          choice('transport', 'Beförderungsart', const {
            'ground': 'Landweg',
            'flight': 'Flug',
            'ship': 'Schiff',
          }, old['transport']),
          BusinessField(
            'necessary_stopover',
            'Notwendige Zwischenübernachtung',
            type: BusinessInput.toggle,
            initial: old['necessary_stopover'] == true,
          ),
        ],
      ];
    } else if (kind == 'overnights') {
      fields = [
        date('date', 'Datum der Außenübernachtung', old['date']),
        choice(
          'site_id',
          'Tatsächliche Übernachtungsstätte',
          siteChoices,
          businessMap(old['site_ref'])['id'],
        ),
        choice('claim_method', 'Beantragter Unterkunftsnachweis', const {
          'none': 'Keine Unterkunftserstattung beantragt',
          'flat': 'Übernachtungspauschale',
          'expense': 'Bereits erfasste tatsächliche Auslage',
        }, old['claim_method']),
        choice(
          'provided_by',
          'Unterkunft bezahlt oder bereitgestellt durch',
          const {
            'employee': 'Mitarbeiter',
            'employer': 'Arbeitgeber',
            'third_party_free': 'Dritter unentgeltlich',
          },
          old['provided_by'],
        ),
        choice(
          'accommodation_kind',
          'Tatsächliche Unterkunftsart · bei Pauschale erforderlich',
          const {
            'lodging': 'Unterkunft außerhalb eines Fahrzeugs',
            'vehicle': 'Übernachtung im Fahrzeug',
            'sleeper_train': 'Schlafwagen',
            'ship_cabin': 'Schiffskabine',
          },
          old['accommodation_kind'],
          false,
        ),
        BusinessField(
          'other_lodging_started_or_finished',
          'Schlafwagen oder Schiffskabine: Übernachtung begann oder endete tatsächlich in einer anderen Unterkunft; belegt durch Reiseoriginale.',
          type: BusinessInput.toggle,
          initial: old['other_lodging_started_or_finished'] == true,
        ),
        choice(
          'expense_receipt_file_id',
          'Unterkunftsoriginal innerhalb der gewählten Auslage',
          <String, String>{
            for (final expense in items(sources['expenses']))
              for (final item in items(expense['items']))
                '${item['receipt_file_id']}':
                    '${expense['purpose']} · ${item['description']} · ${money(item['amount_minor'])}',
          },
          old['expense_receipt_file_id'],
          false,
        ),
        choice(
          'expense_id',
          'Vorhandene tatsächliche Auslage',
          choices(
            sources['expenses'],
            (item) => '${item['purpose'] ?? item['id']}',
          ),
          businessMap(old['expense_ref'])['id'],
          false,
        ),
      ];
    } else {
      fields = [
        date('date', 'Datum der Mahlzeit', old['date']),
        choice('kind', 'Mahlzeit', const {
          'breakfast': 'Frühstück',
          'lunch': 'Mittagessen',
          'dinner': 'Abendessen',
        }, old['kind']),
        choice('provider', 'Bereitstellung', const {
          'employer': 'Arbeitgeber',
          'employer_arranged': 'Vom Arbeitgeber veranlasst',
          'independent_third_party': 'Unabhängiger Dritter',
          'self': 'Selbst beschafft',
        }, old['provider']),
        BusinessField(
          'offered',
          'Tatsächlich bereitgestellt',
          type: BusinessInput.toggle,
          initial: old['offered'] == true,
        ),
        BusinessField(
          'is_meal',
          'Vollwertige Mahlzeit, kein bloßer Snack',
          type: BusinessInput.toggle,
          initial: old['is_meal'] == true,
        ),
        text(
          'price',
          'Tatsächlicher Mahlzeitenpreis EUR',
          previous == null
              ? null
              : (old['price_minor'] / 100).toStringAsFixed(2),
        ),
        text(
          'employee_paid',
          'Tatsächlicher eigener Anteil EUR',
          previous == null
              ? null
              : (old['employee_paid_minor'] / 100).toStringAsFixed(2),
        ),
        choice(
          'replacement_for',
          'Ersatz für bereits erfasste Mahlzeit',
          choices(
            items(details['meals'])
                .where((item) => item['id'] != old['id'])
                .toList(),
            (item) => '${item['date']} · ${item['kind']}',
          ),
          old['replacement_for'],
          false,
        ),
        multiple(
          'source_file_ids',
          'Mahlzeitnachweise',
          choices(sources['files']),
          old['source_file_ids'],
        ),
      ];
    }
    await edit(
      {
        'segments': 'Reisestation',
        'private_intervals': 'Privater Reiseabschnitt',
        'overnights': 'Außenübernachtung',
        'meals': 'Mahlzeitnachweis',
      }[kind]!,
      fields,
      (values) async {
        final result = <String, dynamic>{'id': old['id'] ?? offlineId()};
        if (kind == 'segments' || kind == 'private_intervals') {
          result['from'] = await resolveTime(
            values,
            'from',
            values['timezone'],
          );
          result['to'] = await resolveTime(values, 'to', values['timezone']);
          if (kind == 'segments')
            result.addAll({
              'site_ref': travelReference(
                items(sources['sites'])
                    .firstWhere((site) => site['id'] == values['site_id']),
              ),
              'activity': values['activity'],
              'transport': values['transport'],
              'necessary_stopover': values['necessary_stopover'] == true,
            });
        } else if (kind == 'overnights') {
          result.addAll({
            'date': values['date'],
            'site_ref': travelReference(
              items(sources['sites'])
                  .firstWhere((site) => site['id'] == values['site_id']),
            ),
            'claim_method': values['claim_method'],
            'provided_by': values['provided_by'],
            if (values['accommodation_kind'] != null)
              'accommodation_kind': values['accommodation_kind'],
            'other_lodging_started_or_finished':
                values['other_lodging_started_or_finished'] == true,
            if (values['expense_receipt_file_id'] != null)
              'expense_receipt_file_id': values['expense_receipt_file_id'],
            'expense_ref': values['expense_id'] == null
                ? null
                : travelReference(
                    items(
                      sources['expenses'],
                    ).firstWhere((item) => item['id'] == values['expense_id']),
                  ),
          });
        } else {
          result.addAll({
            for (final key in const [
              'date',
              'kind',
              'provider',
              'offered',
              'is_meal',
              'replacement_for',
              'source_file_ids',
            ])
              key: values[key],
            'price_minor': travelMinor(values['price'], zero: true),
            'employee_paid_minor': travelMinor(
              values['employee_paid'],
              zero: true,
            ),
          });
        }
        if (!identical(draft, captured))
          _fail('Der Reiseentwurf wurde geschlossen.', 403);
        final list = items(details[kind]);
        if (index == null) {
          list.add(result);
        } else {
          list[index] = result;
        }
        details[kind] = list;
        captured['details'] = details;
      },
    );
  }

  Future<void> saveTrip() async {
    await fresh('write');
    final captured = draft!;
    final details = businessMap(captured['details']);
    if (const [
          'purpose',
          'departed_at',
          'returned_at',
          'timezone',
        ].any((key) => '${details[key] ?? ''}'.isEmpty) ||
        items(details['segments']).isEmpty) {
      _fail(
        'Reisezweck, tatsächlicher Zeitraum, Zeitzone und vollständige Stationen sind erforderlich.',
      );
    }
    requireFiles(details['source_file_ids']);
    if (details['mixed_assessment'] != null) {
      details['mixed_assessment'] = travelMixedAssessment(
        details['mixed_assessment'],
        items(sources['files']),
      );
      captured['details'] = details;
    }
    if (captured['revision'] > 0 &&
        '${captured['correction_reason']}'.trim().isEmpty)
      _fail('Korrekturgrund angeben.');
    await submit(
      '/trips',
      _copy(captured),
      'trip.save',
      'trip',
      captured['id'],
    );
    draft = null;
    await load();
  }

  Future<void> tripAction(String action) async {
    final item = current!, right = action == 'reject' ? 'approve' : 'write';
    await fresh(right);
    final sourceHash = sources['source_hash'];
    await edit(
      action == 'reject'
          ? 'Reise zurückweisen'
          : 'Reise zur Prüfung einreichen',
      [
        if (action == 'reject') text('reason', 'Begründung der Zurückweisung'),
        const BusinessField(
          'confirmed',
          'Ich bestätige die ausgewählte Reise und ihre belegten Angaben.',
          type: BusinessInput.toggle,
        ),
      ],
      (values) async {
        if (values['confirmed'] != true)
          _fail('Den gewählten Reiseauftrag ausdrücklich bestätigen.');
        await submit(
          '/trips/${item['id']}/$action',
          {'revision': item['revision'], 'source_hash': sourceHash, ...values},
          'trip.$action',
          'trip',
          item['id'],
          right: right,
        );
      },
      right: right,
      saveLabel: action == 'reject'
          ? 'Begründet zurückweisen'
          : 'Zur fremden Prüfung einreichen',
    );
    if (command.pending == null) await load();
  }

  Future<void> settlementEditor([Map<String, dynamic>? previous]) async {
    await fresh('approve');
    final page = await get('/trips?employee_id=$employeeId');
    final availableTrips = items(page['items'])
        .where((trip) => trip['status'] == 'submitted')
        .toList();
    if (availableTrips.isEmpty)
      _fail('Zuerst einen fremd prüfbaren Reiseantrag einreichen.');
    final old = businessMap(previous?['details']);
    await edit(
      previous == null
          ? 'Eingereichte Reisen abrechnen'
          : 'Abrechnung belegt korrigieren',
      [
        multiple(
          'trip_ids',
          'Ausdrücklich ausgewählte Reisen',
          choices(
            availableTrips,
            (trip) =>
                '${businessMap(trip['details'])['purpose'] ?? trip['purpose'] ?? trip['id']}',
          ),
          items(old['trip_refs']).map((item) => item['id']).toList(),
        ),
        text(
          'payroll_month',
          'Vorgesehener Zuflussmonat steuerpflichtiger Mehrbeträge (JJJJ-MM)',
          old['payroll_month'],
          false,
        ),
        date('period_from', 'Abrechnung von', old['period_from']),
        date('period_to', 'Abrechnung bis', old['period_to']),
        choice('settlement_unit', 'Abrechnungseinheit', const {
          'trip': 'Eine Reise',
          'combined_period': 'Belegt zusammengefasster Zeitraum',
        }, old['settlement_unit']),
        choice('tax_choice', 'Geprüfte steuerliche Behandlung', const {
          'tax_free_only': 'Nur steuerfreie Erstattung',
          'flat_25': 'Zulässige Pauschalversteuerung',
          'individual': 'Individuelle Lohnversteuerung',
        }, old['tax_choice']),
        text(
          'requested_meal',
          'Geprüfter Verpflegungsantrag EUR',
          previous == null
              ? null
              : (old['requested_meal_minor'] / 100).toStringAsFixed(2),
        ),
        text(
          'requested_lodging',
          'Geprüfter Unterkunftsantrag EUR',
          previous == null
              ? null
              : (old['requested_lodging_minor'] / 100).toStringAsFixed(2),
        ),
        BusinessField(
          'review_note',
          'Prüfung von Stätte, Vorgeschichte, Belegen und Behandlung',
          type: BusinessInput.multiline,
          required: true,
        ),
      ],
      (values) async {
        final ids = values['trip_ids'] as List;
        if (ids.isEmpty) _fail('Mindestens eine eingereichte Reise auswählen.');
        final body = {
          'employee_id': employeeId,
          'payroll_month': values['payroll_month'] == ''
              ? null
              : values['payroll_month'],
          'trip_refs': ids
              .map(
                (id) => travelReference(
                  availableTrips.firstWhere((trip) => trip['id'] == id),
                ),
              )
              .toList(),
          for (final key in const [
            'period_from',
            'period_to',
            'settlement_unit',
            'tax_choice',
            'review_note',
          ])
            key: values[key],
          'requested_meal_minor': travelMinor(
            values['requested_meal'],
            zero: true,
          ),
          'requested_lodging_minor': travelMinor(
            values['requested_lodging'],
            zero: true,
          ),
          'correction_of': previous == null ? null : travelReference(previous),
        };
        final original = command.stamp, captured = command.epoch;
        final result = travelPreview(
          await session.api.call(
            session.path('$_travelRoot/settlements/preview'),
            body,
          ),
          employeeId,
          body,
        );
        command.check(original, captured);
        preview = result;
        previewBody = body;
        previewPrevious = previous;
        current = null;
        currentKind = null;
        draft = null;
      },
      right: 'approve',
      saveLabel: 'Tagesrechnung und offene Punkte prüfen',
    );
  }

  Future<void> approveSettlement() async {
    final value = preview!,
        body = _copy(previewBody!),
        id = '${previewPrevious?['id'] ?? offlineId()}';
    if (value['can_approve'] != true)
      _fail('Die Abrechnung enthält noch offene fachliche Schritte.');
    await edit(
      'Geprüfte Reiseabrechnung bestätigen',
      const [
        BusinessField(
          'confirmed',
          'Ich bestätige die fremd geprüften Quellen und genau diese Tagesrechnung.',
          type: BusinessInput.toggle,
        ),
      ],
      (input) async {
        if (input['confirmed'] != true)
          _fail('Die konkrete Abrechnung ausdrücklich bestätigen.');
        await submit(
          '/settlements',
          {
            ...body,
            'id': id,
            'revision': previewPrevious?['revision'] ?? 0,
            'source_hash': value['source_hash'],
            'preview_hash': value['preview_hash'],
            'confirmed': true,
          },
          'settlement.approve',
          'settlement',
          id,
          right: 'approve',
        );
      },
      right: 'approve',
      saveLabel: 'Abrechnung freigeben',
    );
    if (command.pending == null) await load();
  }

  Future<void> adoptLegacy(Map<String, dynamic> settlement) async {
    await fresh('payments');
    final entries = <Map<String, dynamic>>[
      for (final expense in items(
        businessMap(settlement['sources'])['expenses'],
      ))
        for (final indexed in items(expense['payments']).indexed)
          {
            'expense': expense,
            'payment': indexed.$2,
            'payment_index': indexed.$1,
            'id': '${expense['id']}:${indexed.$1}',
            'name':
                '${expense['purpose']} · ${businessDate(indexed.$2['paid_on'])} · ${factLabel(indexed.$2['kind'])} · ${money(indexed.$2['amount_minor'])} · ${indexed.$2['reference']}',
          },
    ];
    if (entries.isEmpty)
      _fail(
        'In dieser Abrechnung sind keine früher bestätigten Auslagenzahlungen gebunden.',
      );
    Map<String, dynamic>? selected;
    await edit(
      'Früher belegte Auslagenzahlung auswählen',
      [
        choice(
          'payment_id',
          'Unveränderte ursprüngliche Zahlung',
          choices(entries),
        ),
      ],
      (values) async {
        selected = entries.firstWhere(
          (item) => item['id'] == values['payment_id'],
        );
      },
      right: 'payments',
      saveLabel: 'Finanznachweis dieser Altzahlung ergänzen',
    );
    if (selected == null) return;
    final item = selected!, payment = businessMap(selected!['payment']);
    await paymentEditor(
      settlement,
      payment['kind'],
      action: 'adopt_legacy',
      legacy: {
        'payment': payment,
        'binding': {
          'expense_ref': travelReference(businessMap(item['expense'])),
          'payment_index': item['payment_index'],
          'payment_hash': await travelHash(payment),
        },
      },
    );
  }

  Future<void> paymentEditor(
    Map<String, dynamic> settlement,
    String kind, {
    Map<String, dynamic>? previous,
    String action = 'record',
    Map<String, dynamic>? legacy,
  }) async {
    await fresh('payments');
    final state = _copy(sources), id = '${previous?['id'] ?? offlineId()}';
    final prior = businessMap(previous?['details']),
        legacyBinding = businessMap(
          legacy?['binding'] ??
              businessMap(previous?['details'])['legacy_payment'],
        );
    final bound = legacyBinding.isNotEmpty,
        fixed = businessMap(legacy?['payment'] ?? prior);
    await edit(
      action == 'adopt_legacy'
          ? 'Bereits belegte Auslagenzahlung für Finanzen übernehmen'
          : action == 'void'
          ? 'Fälschlichen Zahlungsnachweis aufheben'
          : previous != null
          ? 'Zahlungsnachweis korrigieren'
          : kind == 'repayment'
          ? 'Tatsächliche Rückzahlung erfassen'
          : 'Tatsächliche Erstattung erfassen',
      [
        if (action != 'void' && !bound) ...[
          date('paid_on', 'Tatsächlicher Zahlungstag', prior['paid_on']),
          text(
            'amount',
            'Tatsächlich belegter Betrag EUR',
            previous == null
                ? null
                : (prior['amount_minor'] / 100).toStringAsFixed(2),
          ),
        ],
        if (action != 'void') ...[
          choice(
            'account_id',
            'Tatsächlich verwendetes Geldkonto',
            choices(
              items(state['accounts'])
                  .where((account) => account['active'] == true)
                  .toList(),
            ),
            prior['account_id'],
          ),
          if (!bound)
            text(
              'reference',
              'Zahlungsnachweis / Referenz',
              prior['reference'],
            ),
          choice(
            'reference_file_id',
            'Unverändertes Zahlungsoriginal',
            choices(
              items(state['files'])
                  .where((file) => file['purpose'] == 'personnel')
                  .toList(),
            ),
          ),
        ],
        if (previous != null)
          text(
            'correction_reason',
            action == 'void'
                ? 'Belegte Nachweiskorrektur für unveränderte Zahlung ${prior['paid_on']} · ${money(prior['amount_minor'])} · ${prior['reference']}'
                : 'Belegte Nachweiskorrektur',
          ),
        BusinessField(
          'confirmed',
          action == 'void' && bound
              ? 'Die Finanz-Nachweisübernahme war sachlich falsch; die ursprüngliche tatsächliche Auslagenzahlung bleibt erhalten.'
              : bound
              ? 'Unverändert gebundene frühere Zahlung: ${businessDate(fixed['paid_on'])} · ${factLabel(fixed['kind'])} · ${money(fixed['amount_minor'])} · ${fixed['reference']}. Ich bestätige ausschließlich den Finanznachweis; keine neue Auszahlung.'
              : action == 'void'
              ? 'Der frühere Zahlungsnachweis war sachlich falsch; dies ist keine tatsächliche Rückzahlung.'
              : 'Ich bestätige die bereits tatsächlich erfolgte ${kind == 'repayment' ? 'Rückzahlung' : 'Erstattung'}.',
          type: BusinessInput.toggle,
        ),
      ],
      (input) async {
        if (input['confirmed'] != true)
          _fail('Den tatsächlichen Nachweis ausdrücklich bestätigen.');
        final account = action == 'void'
            ? {'id': prior['account_id'], 'revision': prior['account_revision']}
            : items(state['accounts'])
                  .firstWhere((item) => item['id'] == input['account_id']);
        await submit(
          '/payments',
          {
            'id': id,
            'revision': previous?['revision'] ?? 0,
            'action': action,
            'settlement_ref': action == 'void' || bound && previous != null
                ? prior['settlement_ref']
                : travelReference(settlement),
            'kind': kind,
            'paid_on': action == 'void' || bound
                ? fixed['paid_on']
                : input['paid_on'],
            'amount_minor': action == 'void' || bound
                ? fixed['amount_minor']
                : travelMinor(input['amount']),
            'account_id': account['id'],
            'account_revision': account['revision'],
            'instance_id': state['instance_id'],
            'reference': action == 'void' || bound
                ? fixed['reference']
                : input['reference'],
            'reference_file_id': action == 'void'
                ? prior['reference_file_id']
                : input['reference_file_id'],
            if (bound) 'legacy_payment': legacyBinding,
            'source_hash': state['source_hash'],
            'correction_reason': input['correction_reason'] ?? '',
            'confirmed': true,
          },
          'payment.record',
          'payment',
          id,
          right: 'payments',
        );
      },
      right: 'payments',
      saveLabel: action == 'adopt_legacy'
          ? 'Vorhandene Zahlung als Finanzquelle übernehmen'
          : action == 'void'
          ? 'Falschen Nachweis belegt aufheben'
          : 'Tatsächlichen Geldfluss dokumentieren',
    );
    if (command.pending == null) await load();
  }

  Future<void> originalFile(Map<String, dynamic> metadata) async {
    await fresh();
    final matches = items(sources['files'])
        .where(
          (file) =>
              file['id'] == metadata['id'] &&
              file['sha256'] == metadata['sha256'] &&
              file['employee_id'] == employeeId,
        )
        .toList();
    if (matches.length != 1)
      _fail(
        'Das private Original ist für diese Person nicht mehr freigegeben.',
        403,
      );
    final file = matches.single,
        original = command.stamp,
        captured = command.epoch;
    final bytes = await session.api.bytes(
      session.path('/personnel/files/${file['id']}/content'),
      mediaType: '${file['media_type']}',
      maxBytes: 16000000,
    );
    final attachment = await travelOriginal(bytes, file);
    await fresh();
    command.check(original, captured);
    if (!items(sources['files']).any(
      (value) => value['id'] == file['id'] && value['sha256'] == file['sha256'],
    ))
      _fail('Die Originalfreigabe wurde geändert.', 403);
    if (!mounted) return;
    await (widget.exporter ?? exportMailAttachment)(
      context,
      attachment,
      () =>
          mounted &&
          available &&
          command.stamp == original &&
          command.epoch == captured,
    );
  }

  Future<void> download(String format) async {
    await fresh();
    final item = current!;
    if (businessMap(sources['rights'])['export'] != true)
      _fail('Die Exportfreigabe fehlt.', 403);
    final metadata = businessMap(businessMap(item['exports'])[format]);
    final original = command.stamp, captured = command.epoch;
    final bytes = await session.api.bytes(
      session.path(
        '$_travelRoot/settlements/${item['id']}/export?revision=${item['revision']}&format=$format',
      ),
      mediaType: '${metadata['media_type']}',
      maxBytes: 16000000,
    );
    final attachment = await travelOriginal(bytes, metadata);
    await fresh();
    command.check(original, captured);
    if (businessMap(sources['rights'])['export'] != true)
      _fail('Die Exportfreigabe wurde entzogen.', 403);
    await (widget.exporter ?? exportMailAttachment)(
      context,
      attachment,
      () =>
          mounted &&
          available &&
          command.stamp == original &&
          command.epoch == captured &&
          businessMap(sources['rights'])['export'] == true,
    );
  }

  Widget action(
    String label,
    Future<void> Function() function, {
    bool primary = false,
  }) => primary
      ? FilledButton(
          onPressed: busy ? null : () => run(function),
          child: Text(label),
        )
      : OutlinedButton(
          onPressed: busy ? null : () => run(function),
          child: Text(label),
        );
  Widget section(String title, List<Widget> children) => Card(
    child: Padding(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(title, style: Theme.of(context).textTheme.titleMedium),
          const SizedBox(height: 12),
          ...children,
        ],
      ),
    ),
  );
  String factLabel(dynamic value) =>
      const <String, String>{
        'work': 'Tätigkeit',
        'transit': 'Unterwegs',
        'stay': 'Aufenthalt',
        'ground': 'Landweg',
        'flight': 'Flug',
        'ship': 'Schiff',
        'none': 'Keine Unterkunftserstattung',
        'flat': 'Übernachtungspauschale',
        'expense': 'Tatsächliche Auslage',
        'employee': 'Mitarbeiter',
        'employer': 'Arbeitgeber',
        'third_party_free': 'Dritter unentgeltlich',
        'breakfast': 'Frühstück',
        'lunch': 'Mittagessen',
        'dinner': 'Abendessen',
        'home': 'Wohnung',
        'first_workplace': 'Erste Tätigkeitsstätte',
        'external_fixed': 'Auswärtige feste Stätte',
        'mobile': 'Mobile Tätigkeit',
        'wide_area': 'Weiträumiges Gebiet',
        'reimbursement': 'Erstattung',
        'repayment': 'Rückzahlung',
        'transport': 'Beförderung',
        'lodging': 'Unterkunft',
        'incidental': 'Reisenebenkosten',
      }['$value'] ??
      '${value ?? ''}';
  Widget fieldRows(
    Map<String, dynamic> value,
    Map<String, String> fields,
  ) => Column(
    crossAxisAlignment: CrossAxisAlignment.start,
    children: [
      for (final field in fields.entries)
        Padding(
          padding: const EdgeInsets.only(bottom: 8),
          child: Text(
            '${field.value}: ${value[field.key] == null || value[field.key] == '' ? 'Nicht angegeben' : factLabel(value[field.key])}',
          ),
        ),
    ],
  );
  Widget pendingBox() => section('Bestätigung noch offen', [
    const Notice(
      'Zuerst den ursprünglichen Auftrag prüfen. Es wird keine neue Zahlung angelegt.',
    ),
    action('Status des ursprünglichen Auftrags prüfen', () async {
      await command.status(resolve: true);
      await load();
    }, primary: true),
    action('Ursprünglichen Auftrag unverändert wiederholen', () async {
      await command.retry();
      await load();
    }),
    action('Private Eingaben verwerfen und Stand neu laden', () async {
      command.clear();
      await load();
    }),
  ]);
  Widget calculation(Map<String, dynamic> value) {
    final totals = businessMap(value['totals']);
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        if (items(value['blockers']).isNotEmpty)
          section('Noch zu klären', [
            for (final blocker in items(value['blockers']))
              Notice('${blocker['text'] ?? blocker['code']}'),
          ]),
        for (final day in items(value['days']))
          section('${businessDate(day['date'])} · ${day['country'] ?? ''} ${day['region'] ?? ''}', [
            if (value['rule_version'] == 'de_travel_2026_v3')
              Text(
                'Bemessung vor Aufteilung: ${money(day['unapportioned_base_minor'])} · belegter beruflicher Anteil: ${businessMap(day['business_share'])['numerator']}/${businessMap(day['business_share'])['denominator']}',
              ),
            Text(
              'Tagesanspruch ${money(day['base_minor'])} · Mahlzeitenkürzung ${money(day['meal_reduction_minor'])}',
            ),
            Text(
              'Verpflegung ${money(day['meal_allowance_minor'])} · Unterkunft ${money(day['lodging_allowance_minor'])}',
            ),
            ExpansionTile(
              title: const Text('Herleitung und Stättenfrist'),
              children: [
                ListTile(
                  title: Text(
                    'Voller Tagessatz: ${money(day['full_minor'])} · Kennzeichen M: ${day['letter_m'] == true
                        ? 'Ja'
                        : day['letter_m'] == false
                        ? 'Nein'
                        : 'Noch nicht festgestellt'}',
                  ),
                  subtitle: Text(
                    'Belegte Abwesenheit: ${day['absence_seconds']} Sekunden · Sachbezug: ${money(day['benefit_in_kind_minor'])}',
                  ),
                ),
                for (final reason in items(day['reasons']))
                  ListTile(title: Text('${reason['text'] ?? reason['code']}')),
                if (day['three_month'] is Map)
                  ListTile(
                    title: Text(
                      'Stättenfrist: ${businessMap(day['three_month'])['eligible'] == true ? 'Anspruch zeitlich zulässig' : 'Kein bestätigter Anspruch'}',
                    ),
                    subtitle: Text(
                      '${businessDate(businessMap(day['three_month'])['started_on'])} – ${businessDate(businessMap(day['three_month'])['expires_on'])}',
                    ),
                  ),
              ],
            ),
          ]),
        for (final source in items(value['mixed_program_sources']))
          section('Belegte Programmaufteilung', [
            Text(
              source['method'] == null
                  ? 'Eine belegte vollständige Programmbeurteilung fehlt.'
                  : 'Beruflich ${source['business_seconds']} Sekunden · privat ${source['private_seconds']} Sekunden · Anteil ${source['numerator']}/${source['denominator']} · ${(source['source_file_ids'] as List).length} Originalnachweise',
            ),
          ]),
        for (final source in items(value['ground_calendar_sources']))
          section('Örtlicher Reisekalender', [
            for (final entry in businessMap(source['days']).entries)
              ListTile(
                title: Text(businessDate(entry.key)),
                subtitle: Text(
                  '${entry.value['absence_seconds']} Sekunden · ${entry.value['timezone']}',
                ),
              ),
          ]),
        if (value['payroll_required'] == true)
          const Notice(
            'Diese geprüfte Abrechnung benötigt zusätzlich die gebundene Lohnverarbeitung. Steuerpflichtige Mehrbeträge werden über Lohnnetto ausgezahlt; ein Reisekostenauftrag zahlt sie nicht nochmals.',
          ),
        if (items(value['expense_items']).isNotEmpty)
          section('Tatsächliche Auslagen je Original', [
            for (final item in items(value['expense_items']))
              ListTile(
                title: Text(
                  '${businessDate(item['date'])} · ${factLabel(item['kind'])}',
                ),
                subtitle: Text(
                  'Beruflich ${money(item['business_minor'])} · privat ${money(item['private_minor'])} · bereitgestellt ${money(item['provided_minor'])} · bereits bezahlt ${money(item['already_paid_minor'])}\n${item['review_note']}',
                ),
              ),
          ]),
        section('Getrennte Abrechnungsbeträge', [
          for (final entry in const {
            'requested_minor': 'Beantragt',
            'tax_free_minor': 'Steuerfrei',
            'flat_taxable_minor': 'Pauschalierbarer Anteil',
            'individual_taxable_minor': 'Individuell steuerpflichtig',
            'benefit_in_kind_minor': 'Sachbezug',
            'already_paid_minor': 'Bereits tatsächlich bezahlt',
            'remaining_minor': 'Verbleibend',
            'overpaid_minor': 'Belegt überzahlt',
            'expense_allowance_minor': 'Tatsächliche berufliche Auslagen',
            'expense_already_paid_minor':
                'Davon bereits belegte Auslagenerstattung',
          }.entries)
            if (totals.containsKey(entry.key))
              Text('${entry.value}: ${money(totals[entry.key])}'),
        ]),
      ],
    );
  }

  List<Widget> overview() => [
    section('Reisen', [
      if (can('write') && command.pending == null)
        action('Neue Reise erfassen', () async {
          startTrip();
        }, primary: true),
      if (trips.isEmpty) const Text('Noch keine Reisen erfasst.'),
      for (final trip in trips)
        ListTile(
          title: Text(
            '${businessMap(trip['details'])['purpose'] ?? trip['purpose'] ?? 'Reise'}',
          ),
          subtitle: Text(
            'Fassung ${trip['revision']} · ${travelStatuses[trip['status']] ?? trip['status']}',
          ),
          onTap: busy ? null : () => run(() => openDetail('trips', trip['id'])),
        ),
    ]),
    section('Orte und Nachweise', [
      if (can('write') && command.pending == null)
        action('Stätte belegt erfassen', editSite),
      for (final site in items(sources['sites']))
        ListTile(
          title: Text(
            '${businessMap(site['details'])['name'] ?? site['name']}',
          ),
          subtitle: Text('Fassung ${site['revision']}'),
          onTap: busy ? null : () => run(() => openDetail('sites', site['id'])),
        ),
    ]),
    section('Abrechnungen', [
      if (can('approve') && command.pending == null)
        action(
          'Eingereichte Reisen abrechnen',
          settlementEditor,
          primary: true,
        ),
      for (final item in settlements)
        ListTile(
          title: Text('Abrechnung · Fassung ${item['revision']}'),
          subtitle: Text(
            money(
              businessMap(
                    businessMap(item['calculation'])['totals'],
                  )['requested_minor'] ??
                  businessMap(item['totals'])['requested_minor'],
            ),
          ),
          onTap: busy
              ? null
              : () => run(() => openDetail('settlements', item['id'])),
        ),
    ]),
    section('Tatsächliche Erstattungen', [
      for (final item in payments)
        ListTile(
          title: Text(
            '${businessMap(item['details'])['kind'] == 'repayment' ? 'Tatsächliche Rückzahlung' : 'Tatsächliche Erstattung'} · ${money(businessMap(item['details'])['amount_minor'])}',
          ),
          subtitle: Text(
            '${businessDate(businessMap(item['details'])['paid_on'])} · Fassung ${item['revision']}',
          ),
          onTap: busy
              ? null
              : () => run(() => openDetail('payments', item['id'])),
        ),
    ]),
  ];
  List<Widget> draftView() {
    final details = businessMap(draft!['details']);
    return [
      section('Reiseentwurf', [
        fieldRows(details, const {
          'purpose': 'Reisezweck',
          'departed_at': 'Beginn',
          'returned_at': 'Ende',
          'timezone': 'Zeitzone',
        }),
        action(
          'Grunddaten und Pauschalenwunsch bearbeiten',
          tripBasics,
          primary: true,
        ),
      ]),
      for (final kind in const {
        'segments': 'Stationen',
        'overnights': 'Übernachtungen',
        'meals': 'Mahlzeiten',
        'private_intervals': 'Private Reiseabschnitte',
      }.entries)
        section(kind.value, [
          action('${kind.value} hinzufügen', () => tripRow(kind.key)),
          for (final indexed in items(details[kind.key]).indexed)
            ListTile(
              title: Text(
                '${indexed.$2['date'] ?? indexed.$2['from'] ?? kind.value}',
              ),
              subtitle: Text(
                factLabel(
                  indexed.$2['kind'] ??
                      indexed.$2['activity'] ??
                      indexed.$2['claim_method'],
                ),
              ),
              onTap: busy
                  ? null
                  : () => run(() => tripRow(kind.key, indexed.$2, indexed.$1)),
              trailing: IconButton(
                tooltip: 'Aus Entwurf entfernen',
                onPressed: busy
                    ? null
                    : () => setState(() {
                        final values = items(details[kind.key])
                          ..removeAt(indexed.$1);
                        details[kind.key] = values;
                        draft!['details'] = details;
                      }),
                icon: const Icon(Icons.close),
              ),
            ),
        ]),
      if (catalog['rule_version'] == 'de_travel_2026_v3' ||
          details['mixed_assessment'] != null)
        section('Belegtes gemischtes Reiseprogramm', [
          const Text(
            'Nur ein vollständig belegtes berufliches und privates Gesamtprogramm erlaubt diese Aufteilung. Tatsächliche Privatzeiten zusätzlich einzeln erfassen; Originalkosten gesondert aufteilen.',
          ),
          action('Programmbeurteilung bearbeiten', mixedEditor),
          if (details['mixed_assessment'] != null) ...[
            Text('${details['mixed_assessment']['review_note']}'),
            Text(
              'Vollständiges Programm: ${details['mixed_assessment']['program_complete'] == true ? 'bestätigt' : 'noch offen'} · getrennte Kosten: ${details['mixed_assessment']['cost_allocation_reviewed'] == true ? 'geprüft' : 'noch offen'}',
            ),
            action('Programmpunkt hinzufügen', programEditor),
            for (final indexed in items(
              details['mixed_assessment']['program_sessions'],
            ).indexed)
              ListTile(
                title: Text('${indexed.$2['from']} – ${indexed.$2['to']}'),
                subtitle: Text(
                  indexed.$2['kind'] == 'business'
                      ? 'Berufliches Programm'
                      : 'Privates Programm',
                ),
                onTap: busy
                    ? null
                    : () => run(() => programEditor(indexed.$2, indexed.$1)),
                trailing: IconButton(
                  tooltip: 'Programmpunkt entfernen',
                  icon: const Icon(Icons.close),
                  onPressed: busy
                      ? null
                      : () => setState(() {
                          final assessment = businessMap(
                                details['mixed_assessment'],
                              ),
                              list = items(assessment['program_sessions'])
                                ..removeAt(indexed.$1);
                          assessment.addAll({
                            'program_sessions': list,
                            'program_complete': false,
                            'cost_allocation_reviewed': false,
                          });
                          details['mixed_assessment'] = assessment;
                          draft!['details'] = details;
                        }),
                ),
              ),
            action('Programmbeurteilung aus Entwurf entfernen', () async {
              setState(() {
                details.remove('mixed_assessment');
                draft!['details'] = details;
              });
            }),
          ],
        ]),
      section('Tatsächliche Auslagen', [
        const Text(
          'Nur tatsächlich berufliche Arbeitnehmerauslagen werden erstattet. Bereits belegte Erstattungen bleiben bezahlt. Hier wird keine Vorsteuer beansprucht.',
        ),
        action('Auslagenposition belegt aufteilen', expenseEditor),
        for (final indexed in items(details['expense_allocations']).indexed)
          ListTile(
            title: Text(
              const {
                    'transport': 'Beförderung',
                    'lodging': 'Unterkunft',
                    'incidental': 'Reisenebenkosten',
                  }[indexed.$2['kind']] ??
                  'Auslage',
            ),
            subtitle: Text(
              'Beruflich ${money(indexed.$2['business_minor'])} · privat ${money(indexed.$2['private_minor'])} · bereitgestellt ${money(indexed.$2['provided_minor'])}',
            ),
            onTap: busy
                ? null
                : () => run(() => expenseEditor(indexed.$2, indexed.$1)),
            trailing: IconButton(
              tooltip: 'Aufteilung entfernen',
              icon: const Icon(Icons.close),
              onPressed: busy
                  ? null
                  : () => setState(() {
                      final list = items(details['expense_allocations'])
                        ..removeAt(indexed.$1);
                      details['expense_allocations'] = list;
                      draft!['details'] = details;
                    }),
            ),
          ),
      ]),
      section('Zusammenhängende Beförderungen', [
        action('Flugreise belegen', () => transportEditor('flight')),
        action('Schiffsreise belegen', () => transportEditor('ship')),
        for (final indexed in items(details['transport_facts']).indexed)
          ListTile(
            title: Text(
              indexed.$2['kind'] == 'flight'
                  ? 'Belegte Flugreise'
                  : 'Belegte Schiffsreise',
            ),
            subtitle: Text(
              '${(indexed.$2['legs'] ?? indexed.$2['segment_ids'] as List).length} zugeordnete Abschnitte',
            ),
            onTap: busy
                ? null
                : () => run(
                    () => transportEditor(
                      indexed.$2['kind'],
                      indexed.$2,
                      indexed.$1,
                    ),
                  ),
            trailing: IconButton(
              tooltip: 'Beförderungszuordnung entfernen',
              icon: const Icon(Icons.close),
              onPressed: busy
                  ? null
                  : () => setState(() {
                      final list = items(details['transport_facts'])
                        ..removeAt(indexed.$1);
                      details['transport_facts'] = list;
                      draft!['details'] = details;
                    }),
            ),
          ),
      ]),
      action('Reiseentwurf belegt speichern', saveTrip, primary: true),
      action('Entwurf verwerfen und zur Übersicht', () async {
        draft?.clear();
        draft = null;
        await load();
      }),
    ];
  }

  List<Widget> detailView() {
    final item = current!, details = businessMap(item['details']);
    return [
      Text(
        'Fassung ${item['revision']} · ${travelStatuses[item['status']] ?? item['status'] ?? 'Gespeichert'}',
      ),
      if (currentKind == 'sites') ...[
        fieldRows(details, const {
          'name': 'Stätte',
          'kind': 'Art',
          'address': 'Anschrift',
          'timezone': 'Zeitzone',
          'effective_from': 'Gültig ab',
          'effective_to': 'Gültig bis',
          'assignment_basis': 'Belegte Zuordnung',
          'history_complete_from': 'Vorgeschichte vollständig ab',
        }),
        if (items(details['frequency_periods']).isNotEmpty)
          section('Datierte Einsatzhäufigkeit', [
            for (final period in items(details['frequency_periods']))
              Text(
                '${period['from']} – ${period['to'] ?? 'offen'} · ${period['days_per_week']} belegte Einsatztage je Woche',
              ),
          ]),
        if (!historical && can('write') && command.pending == null)
          action('Stättennachweis korrigieren', () => editSite(item)),
      ] else if (currentKind == 'trips') ...[
        fieldRows(details, const {
          'purpose': 'Reisezweck',
          'departed_at': 'Tatsächlicher Beginn',
          'returned_at': 'Tatsächliches Ende',
          'timezone': 'Zeitzone',
        }),
        for (final kind in const {
          'segments': 'Stationen',
          'overnights': 'Übernachtungen',
          'meals': 'Mahlzeiten',
          'private_intervals': 'Private Reiseabschnitte',
        }.entries)
          section(kind.value, [
            for (final row in items(details[kind.key]))
              ListTile(
                title: Text('${row['date'] ?? row['from']}'),
                subtitle: Text(
                  factLabel(
                    row['kind'] ?? row['activity'] ?? row['claim_method'],
                  ),
                ),
              ),
          ]),
        if (details['mixed_assessment'] != null)
          section('Belegtes gemischtes Reiseprogramm', [
            Text('${details['mixed_assessment']['review_note']}'),
            for (final point in items(
              details['mixed_assessment']['program_sessions'],
            ))
              ListTile(
                title: Text('${point['from']} – ${point['to']}'),
                subtitle: Text(
                  point['kind'] == 'business'
                      ? 'Berufliches Programm'
                      : 'Privates Programm',
                ),
              ),
          ]),
        if (!historical && command.pending == null) ...[
          if (can('write'))
            action('Reise korrigieren', () async {
              startTrip(item);
            }),
          if (item['status'] == 'draft' && can('write'))
            action(
              'Reise zur Prüfung einreichen',
              () => tripAction('submit'),
              primary: true,
            ),
          if (item['status'] == 'submitted' && can('approve'))
            action('Mit Begründung zurückweisen', () => tripAction('reject')),
        ],
      ] else if (currentKind == 'settlements') ...[
        const Notice(
          'Stand dieser gespeicherten Abrechnung. Nachfolgende tatsächliche Zahlungen und Rückzahlungen sind separat in den Zahlungsnachweisen dokumentiert.',
        ),
        calculation(
          businessMap(item['calculation'] ?? item['preview'] ?? item),
        ),
        if (businessMap(sources['rights'])['export'] == true)
          for (final format in const ['pdf', 'json'])
            if (businessMap(item['exports'])[format] != null)
              action(
                '${format.toUpperCase()} · Fassung ${item['revision']}',
                () => download(format),
              ),
        if (!historical && can('payments') && command.pending == null) ...[
          action(
            'Tatsächliche Erstattung erfassen',
            () => paymentEditor(item, 'reimbursement'),
            primary: true,
          ),
          action(
            'Tatsächliche Rückzahlung erfassen',
            () => paymentEditor(item, 'repayment'),
          ),
          if (items(businessMap(item['sources'])['expenses'])
              .any((expense) => items(expense['payments']).isNotEmpty))
            action(
              'Bereits belegte Auslagenzahlung für Finanzen übernehmen',
              () => adoptLegacy(item),
            ),
        ],
      ] else ...[
        if (businessMap(details['legacy_payment']).isNotEmpty)
          const Notice(
            'Finanznachweis einer bereits früher belegten Auslagenzahlung. Diese Übernahme erzeugt keine weitere Auszahlung.',
          ),
        fieldRows(details, const {
          'kind': 'Zahlungsart',
          'paid_on': 'Tatsächlicher Tag',
          'reference': 'Zahlungsreferenz',
          'status': 'Nachweisstatus',
        }),
        Text('Tatsächlicher Betrag: ${money(details['amount_minor'])}'),
        if (!historical && can('payments') && command.pending == null)
          for (final operation in const {
            'correct': 'Zahlungsnachweis korrigieren',
            'void': 'Fälschlichen Zahlungsnachweis aufheben',
          }.entries)
            action(operation.value, () async {
              final value = await get(
                '/settlements/${businessMap(details['settlement_ref'])['id']}',
              );
              await paymentEditor(
                businessMap(value['item']),
                details['kind'],
                previous: item,
                action: operation.key,
              );
            }),
      ],
      if (currentKind == 'settlements' &&
          !historical &&
          can('approve') &&
          command.pending == null)
        action('Abrechnung belegt korrigieren', () => settlementEditor(item)),
      if (items(businessMap(item['sources'])['files']).isNotEmpty)
        section('Unveränderte Originalnachweise', [
          for (final file in items(businessMap(item['sources'])['files']))
            action('${file['filename']}', () => originalFile(file)),
        ]),
      if (!historical) action('Alle Fassungen öffnen', history),
      action('Zur Reiseübersicht', load),
    ];
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(
      title: Text(
        'Reisen und Pauschalen · ${businessMap(sources['employee'])['name'] ?? widget.employee['name']}',
      ),
      actions: [
        IconButton(
          onPressed: busy ? null : () => run(load),
          tooltip: 'Neu laden',
          icon: const Icon(Icons.refresh),
        ),
      ],
    ),
    body: !available
        ? const BusinessEmpty(
            'Reiseansicht nicht freigegeben',
            'Die aktuelle Mitarbeiterzuordnung und Freigabe sind erforderlich.',
          )
        : ListView(
            padding: const EdgeInsets.all(20),
            children: [
              const Notice(
                'Belegte Reisen, nachvollziehbare Tagesbeträge und tatsächliche Erstattungen. Eine Berechnung ist noch keine Zahlung.',
              ),
              if (busy && dialogDepth == 0) const LinearProgressIndicator(),
              if (error != null) Notice(error!, error: true),
              if (command.pending != null) pendingBox(),
              if (draft != null)
                ...draftView()
              else if (preview != null) ...[
                calculation(preview!),
                if (preview!['can_approve'] == true &&
                    can('approve') &&
                    command.pending == null)
                  action(
                    'Geprüfte Reiseabrechnung bestätigen',
                    approveSettlement,
                    primary: true,
                  ),
                action('Zur Reiseübersicht', load),
              ] else if (current != null)
                ...detailView()
              else
                ...overview(),
            ],
          ),
  );
}

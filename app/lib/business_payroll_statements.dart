import 'dart:convert';
import 'dart:typed_data';

import 'package:cryptography/cryptography.dart';
import 'package:flutter/material.dart';

import 'api.dart';
import 'business_session.dart';
import 'business_widgets.dart';
import 'design.dart';
import 'mail_attachment_preview.dart';
import 'mail_attachment_widgets.dart' show exportMailAttachment;

const statementAmounts = {
  'gross_minor': 'Brutto',
  'employee_social_total_minor': 'Arbeitnehmerbeiträge gesamt',
  'individual_wage_tax_minor': 'Lohnsteuer',
  'solidarity_minor': 'Solidaritätszuschlag',
  'church_tax_minor': 'Kirchenlohnsteuer',
  'employee_tax_minor': 'Arbeitnehmersteuern gesamt',
  'net_minor': 'Netto',
  'payout_minor': 'Berechneter Auszahlungsbetrag',
  'employee_additional_payment_minor': 'Zusätzlicher Arbeitnehmerbeitrag',
  'employer_flat_tax_minor': 'Arbeitgeber-Pauschsteuer',
};
const statementBranches = {
  'health_general': 'Krankenversicherung',
  'health_additional': 'KV-Zusatzbeitrag',
  'pension': 'Rentenversicherung',
  'unemployment': 'Arbeitslosenversicherung',
  'care': 'Pflegeversicherung',
};
const _scopes = {
  'regular_standard_factor_taxfree_travel_month',
  'commercial_minijob_individual_month',
  'regular_standard_factor_claims_month',
  'regular_standard_factor_claims_paid_travel_month',
  'regular_transition_factor_month',
  'regular_standard_multiple_oneoff',
  'regular_standard_oneoff',
  'regular_standard_factor_claims_oneoff',
  'regular_standard_segments',
  'regular_transition_segments',
  'commercial_minijob_segments_flat_tax',
  'commercial_minijob_flat_tax',
  'commercial_minijob_period_flat_tax',
  'regular_standard_monthly',
  'regular_standard_factor_monthly',
  'regular_standard_factor_period',
  'regular_standard_period',
  'regular_transition_monthly',
  'regular_transition_period',
  'social_contributions_only',
};
const _compositeV2 = {
  'de_2026_segments_entitlements_v5': {
    'regular_standard_segments',
    'regular_transition_segments',
    'commercial_minijob_segments_flat_tax',
  },
  'de_2026_factor_taxfree_travel_month_v10': {
    'regular_standard_factor_taxfree_travel_month',
  },
  'de_2026_individual_minijob_month_v11': {
    'commercial_minijob_individual_month',
  },
  'de_2026_factor_claims_month_v12': {'regular_standard_factor_claims_month'},
  'de_2026_factor_claims_paid_travel_month_v13': {
    'regular_standard_factor_claims_paid_travel_month',
  },
  'de_2026_factor_transition_month_v14': {'regular_transition_factor_month'},
};
final _id = RegExp(r'^[a-f0-9]{32}$'), _hash = RegExp(r'^[a-f0-9]{64}$');
Never _fail(String message, [int status = 0]) =>
    throw ApiException(status, message);
dynamic _order(dynamic v) => v is List
    ? v.map(_order).toList()
    : v is Map
    ? {
        for (final k in v.keys.map((v) => '$v').toList()..sort())
          k: _order(v[k]),
      }
    : v;
bool _same(dynamic a, dynamic b) =>
    jsonEncode(_order(a)) == jsonEncode(_order(b));
void _shape(dynamic v, Iterable<String> keys) {
  if (v is! Map || !_same(v.keys.toList()..sort(), keys.toList()..sort()))
    _fail('Der Mitarbeiterbeleg enthält unbekannte oder fehlende Angaben.');
}

int _integer(dynamic v, [int min = 0, int max = 1000000000000]) {
  if (v is! int || v < min || v > max)
    _fail('Die Beträge oder Tage des Mitarbeiterbelegs sind ungültig.');
  return v;
}

String _date(dynamic value) {
  final s = '$value', parsed = DateTime.tryParse(s);
  if (!RegExp(r'^\d{4}-\d{2}-\d{2}$').hasMatch(s) ||
      parsed == null ||
      parsed.toIso8601String().substring(0, 10) != s)
    _fail('Der Mitarbeiterbeleg enthält einen ungültigen Zeitraum.');
  return s;
}

String _hex(List<int> v) =>
    v.map((v) => v.toRadixString(16).padLeft(2, '0')).join();
Future<String> payrollStatementHash(List<int> value) async =>
    _hex((await Sha256().hash(value)).bytes);

Future<Map<String, dynamic>> payrollStatement(
  dynamic raw,
  String employeeId, {
  Map<String, dynamic>? reference,
}) async {
  final v = businessMap(raw),
      oneoff = [3, 4, 5].contains(businessMap(raw)['schema_version']),
      composite = [2, 3, 4, 5].contains(businessMap(raw)['schema_version']);
  _shape(v, [
    if (oneoff) 'one_off_summary',
    if (composite) ...['earnings_summary', 'travel_summary'],
    'schema_version',
    'employee_id',
    'employee_name',
    'run_ref',
    'month',
    'created_at',
    'calculation',
    'period_summary',
    'transmission_status',
    'payment_status',
    'statement_hash',
    'pdf_sha256',
    'pdf_size',
  ]);
  final ref = businessMap(v['run_ref']);
  _shape(ref, ['id', 'revision', 'content_hash']);
  if (![1, 2, 3, 4, 5].contains(v['schema_version']) ||
      !_id.hasMatch(employeeId) ||
      v['employee_id'] != employeeId ||
      !_id.hasMatch('${ref['id']}') ||
      !_hash.hasMatch('${ref['content_hash']}') ||
      !_hash.hasMatch('${v['statement_hash']}') ||
      !_hash.hasMatch('${v['pdf_sha256']}') ||
      v['employee_name'] is! String ||
      (v['employee_name'] as String).trim().isEmpty ||
      !RegExp(r'^20\d{2}-(0[1-9]|1[0-2])$').hasMatch('${v['month']}') ||
      DateTime.tryParse('${v['created_at']}') == null ||
      v['transmission_status'] != 'not_transmitted' ||
      v['payment_status'] != 'not_evidenced_by_calculation' ||
      reference != null && !_same(reference, ref))
    _fail(
      'Der Mitarbeiterbeleg gehört nicht eindeutig zur gewählten Person und Fassung.',
    );
  _integer(ref['revision'], 1);
  _integer(v['pdf_size'], 1, 20 * 1024 * 1024);
  final c = businessMap(v['calculation']);
  _shape(c, [
    if (composite) 'net_deductions_minor',
    ...statementAmounts.keys,
    'rule_version',
    'scope',
    'currency',
    'payroll_calculation_complete',
    'employee_contributions',
  ]);
  if ((v['schema_version'] == 2) !=
          _compositeV2.containsKey(c['rule_version']) ||
      (v['schema_version'] == 2) !=
          _compositeV2.values.any((scopes) => scopes.contains(c['scope'])) ||
      v['schema_version'] == 2 &&
          !(_compositeV2[c['rule_version']]?.contains(c['scope']) ?? false) ||
      (v['schema_version'] == 3) !=
          (c['rule_version'] == 'de_2026_oneoff_composition_v6') ||
      (v['schema_version'] == 3) != (c['scope'] == 'regular_standard_oneoff') ||
      (v['schema_version'] == 4) !=
          (c['rule_version'] == 'de_2026_multiple_oneoff_v7') ||
      (v['schema_version'] == 4) !=
          (c['scope'] == 'regular_standard_multiple_oneoff') ||
      (v['schema_version'] == 5) !=
          (c['rule_version'] == 'de_2026_factor_claims_oneoff_v15') ||
      (v['schema_version'] == 5) !=
          (c['scope'] == 'regular_standard_factor_claims_oneoff'))
    _fail(
      'Die Belegversion stimmt nicht mit dem Gesamtlohnregelstand überein.',
    );
  final deductions = composite ? _integer(c['net_deductions_minor']) : 0;
  if (c['currency'] != 'EUR' ||
      c['rule_version'] is! String ||
      !_scopes.contains(c['scope']) ||
      c['payroll_calculation_complete'] is! bool)
    _fail('Der ausgewiesene Berechnungsumfang ist nicht bekannt.');
  for (final k in statementAmounts.keys) {
    if (c[k] != null) _integer(c[k], k == 'net_minor' ? -1000000000000 : 0);
  }
  if (c['employee_contributions'] != null) {
    final parts = businessMap(c['employee_contributions']);
    _shape(parts, statementBranches.keys);
    if (parts.values.fold<int>(0, (n, v) => n + _integer(v)) !=
        c['employee_social_total_minor'])
      _fail('Beitragssumme des Mitarbeiterbelegs stimmt nicht.');
  }
  if (c['payroll_calculation_complete'] == true) {
    if (c['gross_minor'] == null ||
        c['employee_social_total_minor'] == null ||
        c['employee_tax_minor'] == null ||
        c['net_minor'] !=
            c['gross_minor'] -
                c['employee_social_total_minor'] -
                c['employee_tax_minor'] ||
        c['payout_minor'] !=
            (c['net_minor'] - deductions > 0
                ? c['net_minor'] - deductions
                : 0) ||
        c['employee_additional_payment_minor'] !=
            (c['net_minor'] - deductions < 0 ? deductions - c['net_minor'] : 0))
      _fail('Netto und Auszahlung widersprechen den belegten Werten.');
  } else if ([
    'net_minor',
    'payout_minor',
    'employee_tax_minor',
    'employee_additional_payment_minor',
  ].any((k) => c[k] != null))
    _fail(
      'Ein unvollständiger Umfang darf kein vermeintliches Netto ausweisen.',
    );
  if (v['period_summary'] != null) {
    final p = businessMap(v['period_summary']);
    _shape(p, ['employment_intervals', 'tax_periods', 'social_periods']);
    for (final spec in [
      (
        'employment_intervals',
        ['start', 'end', 'calendar_days'],
        'calendar_days',
      ),
      ('tax_periods', ['start', 'end', 'lzz', 'tax_days'], 'tax_days'),
      ('social_periods', ['start', 'end', 'days', 'full_month'], 'days'),
    ]) {
      final items = businessItems(p[spec.$1]);
      if (items.isEmpty) _fail('Die getrennten Zeiträume fehlen.');
      for (final item in items) {
        _shape(item, spec.$2);
        if (_date(item['start']).compareTo(_date(item['end'])) > 0 ||
            !(item['start'] as String).startsWith(v['month']) ||
            !(item['end'] as String).startsWith(v['month']))
          _fail('Der Zeitraum gehört nicht zum Abrechnungsmonat.');
        _integer(item[spec.$3], 1, 31);
        if (spec.$1 == 'tax_periods' && ![2, 4].contains(item['lzz']) ||
            spec.$1 == 'social_periods' && item['full_month'] is! bool)
          _fail('Die Steuer-/SV-Zeitachse ist nicht eindeutig.');
      }
    }
  }
  if (oneoff) {
    final extra = businessMap(v['one_off_summary']);
    _shape(extra, [
      'amount_minor',
      'receipt_date',
      'tax_year',
      'social_year',
      'march_clause',
      'employee_contributions',
      'employee_social_total_minor',
      'individual_wage_tax_minor',
      'solidarity_minor',
      'church_tax_minor',
    ]);
    _integer(extra['amount_minor'], 1);
    if (!_date(extra['receipt_date']).startsWith(v['month']) ||
        !(v['month'] as String).startsWith('2026-') ||
        extra['tax_year'] != 2026 ||
        ![2025, 2026].contains(extra['social_year']) ||
        extra['march_clause'] is! bool ||
        extra['march_clause'] != (extra['social_year'] == 2025) ||
        extra['march_clause'] == true &&
            int.parse((v['month'] as String).substring(5)) > 3 ||
        c['payroll_calculation_complete'] != true ||
        v['period_summary'] == null ||
        c['employee_contributions'] == null)
      _fail(
        'Die Einmalzahlung ist nicht eindeutig dem belegten Monat und Jahr zugeordnet.',
      );
    final parts = businessMap(extra['employee_contributions']);
    _shape(parts, statementBranches.keys);
    var total = 0;
    for (final entry in parts.entries) {
      final amount = _integer(entry.value);
      if (amount > c['employee_contributions'][entry.key])
        _fail('Einzelbeiträge übersteigen den Gesamtbeitrag.');
      total += amount;
    }
    if (total != _integer(extra['employee_social_total_minor']))
      _fail('Die Arbeitnehmerbeiträge der Einmalzahlung stimmen nicht.');
    for (final key in [
      'employee_social_total_minor',
      'individual_wage_tax_minor',
      'solidarity_minor',
      'church_tax_minor',
    ]) {
      if (_integer(extra[key]) > _integer(c[key]))
        _fail('Die Beträge der Einmalzahlung übersteigen den Gesamtlohn.');
    }
    if ([
          'individual_wage_tax_minor',
          'solidarity_minor',
          'church_tax_minor',
        ].fold<int>(0, (sum, key) => sum + (c[key] as int)) !=
        c['employee_tax_minor'])
      _fail(
        'Die einzelnen Arbeitnehmersteuern stimmen nicht mit der Gesamtsteuer überein.',
      );
  }
  if (composite) {
    final t = businessMap(v['travel_summary']);
    _shape(t, [
      'tax_free_external_minor',
      'flat_taxable_payroll_minor',
      'individual_taxable_payroll_minor',
      'benefit_in_kind_non_cash_minor',
      'letter_m',
      'employee_flat_tax_deduction_minor',
    ]);
    for (final entry in t.entries)
      if (entry.key != 'letter_m') _integer(entry.value);
    if (t['letter_m'] is! bool ||
        deductions !=
            t['benefit_in_kind_non_cash_minor'] +
                t['employee_flat_tax_deduction_minor'] ||
        v['earnings_summary'] is! List)
      _fail('Die eigenen Reise- und Nettoabzugsbeträge widersprechen sich.');
    final earnings = businessItems(v['earnings_summary']);
    for (final row in earnings) {
      _shape(row, ['kind', 'dates', 'gross_minor']);
      if (![
            'ordinary_work',
            'public_holiday',
            'sickness',
            'first_sickness_day_regular_wage',
            'vacation',
          ].contains(row['kind']) ||
          row['dates'] is! List ||
          (row['dates'] as List).toSet().length !=
              (row['dates'] as List).length ||
          (row['dates'] as List).any((d) => !_date(d).startsWith(v['month'])))
        _fail('Ein eigener Anspruchsbestandteil enthält unbekannte Angaben.');
      _integer(row['gross_minor']);
    }
    if (earnings.fold<int>(0, (a, b) => a + (b['gross_minor'] as int)) +
            t['flat_taxable_payroll_minor'] +
            t['individual_taxable_payroll_minor'] +
            t['benefit_in_kind_non_cash_minor'] +
            (oneoff ? v['one_off_summary']['amount_minor'] : 0) !=
        c['gross_minor'])
      _fail(
        'Eigene Anspruchs- und Reisebeträge summieren sich nicht zum Brutto.',
      );
  }
  final base = Map<String, dynamic>.from(v)
    ..remove('statement_hash')
    ..remove('pdf_sha256')
    ..remove('pdf_size');
  if (await payrollStatementHash(utf8.encode(jsonEncode(_order(base)))) !=
      v['statement_hash'])
    _fail('Die Prüfsumme des Mitarbeiterbelegs stimmt nicht.');
  return v;
}

Future<Map<String, dynamic>> payrollStatementPage(
  dynamic raw,
  String employeeId, {
  bool detail = false,
  Map<String, dynamic>? reference,
}) async {
  final v = businessMap(raw);
  _shape(v, ['employee_id', 'can_export', detail ? 'statement' : 'items']);
  if (v['employee_id'] != employeeId || v['can_export'] is! bool)
    _fail('Die Belegliste gehört nicht zum gewählten Mitarbeiter.');
  if (detail) {
    await payrollStatement(v['statement'], employeeId, reference: reference);
  } else {
    final seen = <String>{};
    for (final item in businessItems(v)) {
      await payrollStatement(item, employeeId);
      if (!seen.add('${item['run_ref']['id']}:${item['run_ref']['revision']}'))
        _fail('Die Belegliste enthält eine Fassung mehrfach.');
    }
  }
  return v;
}

Future<VerifiedMailAttachment> payrollStatementAttachment(
  Uint8List bytes,
  Map<String, dynamic> v,
) async {
  if (bytes.length != v['pdf_size'] ||
      await payrollStatementHash(bytes) != v['pdf_sha256'] ||
      bytes.length < 5 ||
      ascii.decode(bytes.take(5).toList(), allowInvalid: true) != '%PDF-')
    _fail(
      'Der gelieferte PDF-Beleg stimmt nicht mit der gewählten Fassung überein.',
    );
  return VerifiedMailAttachment(
    bytes: bytes,
    filename: 'lohnnachweis-${v['month']}-v${v['run_ref']['revision']}.pdf',
    mediaType: 'application/pdf',
    sha256: v['pdf_sha256'],
  );
}

Future<VerifiedMailAttachment> payrollStatementJsonAttachment(
  Uint8List bytes,
  Map<String, dynamic> value,
) async {
  if (bytes.isEmpty || bytes.length > 1024 * 1024)
    _fail('Der JSON-Lohnnachweis hat eine ungültige Größe.');
  dynamic decoded;
  late String encoded;
  try {
    encoded = utf8.decode(bytes);
    decoded = jsonDecode(encoded);
  } on FormatException {
    _fail('Der JSON-Lohnnachweis ist nicht lesbar.');
  }
  await payrollStatement(
    decoded,
    value['employee_id'],
    reference: businessMap(value['run_ref']),
  );
  if (encoded != jsonEncode(_order(decoded)) || !_same(decoded, value))
    _fail(
      'Der JSON-Lohnnachweis stimmt nicht mit der gewählten ursprünglichen Fassung überein.',
    );
  return VerifiedMailAttachment(
    bytes: bytes,
    filename:
        'lohnnachweis-${value['month']}-v${value['run_ref']['revision']}.json',
    mediaType: 'application/json',
    sha256: await payrollStatementHash(bytes),
  );
}

bool payrollStatementsAvailable(BusinessSession s) =>
    s.projectId == null &&
    s.hasModule('payroll') &&
    s.hasFeature('payroll_employee_statements') &&
    (s.can('personnel.read') || s.can('time.own'));

class BusinessPayrollStatementsPage extends StatefulWidget {
  const BusinessPayrollStatementsPage({
    super.key,
    required this.session,
    required this.employee,
    this.exporter,
  });
  final BusinessSession session;
  final Map<String, dynamic> employee;
  final MailAttachmentExporter? exporter;
  @override
  State<BusinessPayrollStatementsPage> createState() => _StatementsState();
}

class _StatementsState extends State<BusinessPayrollStatementsPage>
    with WidgetsBindingObserver {
  BusinessSession get session => widget.session;
  String get employeeId => widget.employee['id'];
  List<Map<String, dynamic>> items = [];
  Map<String, dynamic>? selected;
  bool history = false, canExport = false, busy = false, denied = false;
  String? error, actorId;
  int epoch = 0;
  Object? generation;
  late Map<String, dynamic> employee;
  bool get allowed =>
      !denied &&
      payrollStatementsAvailable(session) &&
      (session.can('personnel.read') ||
          actorId != null &&
              employee['user_id'] == actorId &&
              session.can('time.own'));
  @override
  void initState() {
    super.initState();
    employee = Map.from(widget.employee);
    generation = session.generation;
    session.addListener(changed);
    WidgetsBinding.instance.addObserver(this);
    load();
  }

  @override
  void dispose() {
    epoch++;
    session.removeListener(changed);
    WidgetsBinding.instance.removeObserver(this);
    super.dispose();
  }

  void clear() {
    epoch++;
    items = [];
    selected = null;
    history = false;
    canExport = false;
    busy = false;
  }

  void changed() {
    if (!mounted) return;
    if (generation != session.generation ||
        !payrollStatementsAvailable(session) ||
        actorId != null && !allowed) {
      clear();
      generation = session.generation;
    }
    setState(() {});
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state == AppLifecycleState.paused ||
        state == AppLifecycleState.hidden) {
      if (mounted) setState(clear);
    } else if (state == AppLifecycleState.resumed) {
      load();
    }
  }

  void failure(Object e) {
    if (!mounted) return;
    setState(() {
      if (e is ApiException && [401, 403, 404].contains(e.status)) {
        clear();
        denied = true;
      }
      busy = false;
      error = e is ApiException ? e.message : '$e';
    });
  }

  Future<void> fresh() async {
    final current = session.generation;
    await session.load();
    if (!mounted || current != session.generation)
      _fail('Die Sitzung wurde gewechselt.', 403);
    final me = businessMap(await session.api.call('/api/me')),
        team = businessItems(await session.read('/employees'));
    final person = team.where((v) => v['id'] == employeeId).firstOrNull;
    if (person == null) _fail('Dieser Mitarbeiter ist nicht freigegeben.', 403);
    actorId = me['id'];
    employee = person;
    if (!allowed) _fail('Die aktuelle Mitarbeiterfreigabe fehlt.', 403);
  }

  Future<void> load() async {
    if (!mounted) return;
    denied = false;
    final captured = ++epoch;
    setState(() {
      busy = true;
      error = null;
    });
    try {
      await fresh();
      final page = await payrollStatementPage(
        await session.read(
          '/payroll/employee-statements?employee_id=$employeeId',
        ),
        employeeId,
      );
      if (!mounted || captured != epoch || !allowed) return;
      setState(() {
        items = businessItems(page);
        selected = null;
        history = false;
        canExport = page['can_export'];
        busy = false;
      });
    } catch (e) {
      failure(e);
    }
  }

  Future<void> open(Map<String, dynamic> value) async {
    final captured = ++epoch;
    setState(() {
      busy = true;
      error = null;
    });
    try {
      await fresh();
      final ref = businessMap(value['run_ref']);
      final page = await payrollStatementPage(
        await session.read(
          '/payroll/employee-statements/${ref['id']}?revision=${ref['revision']}',
        ),
        employeeId,
        detail: true,
        reference: ref,
      );
      if (!mounted || captured != epoch || !allowed) return;
      setState(() {
        selected = businessMap(page['statement']);
        canExport = page['can_export'];
        busy = false;
      });
    } catch (e) {
      failure(e);
    }
  }

  Future<void> showHistory(Map<String, dynamic> value) async {
    final captured = ++epoch;
    setState(() {
      busy = true;
      error = null;
    });
    try {
      await fresh();
      final ref = businessMap(value['run_ref']);
      final page = await payrollStatementPage(
            await session.read(
              '/payroll/employee-statements/${ref['id']}/history',
            ),
            employeeId,
          ),
          list = businessItems(page);
      for (var i = 0; i < list.length; i++) {
        if (list[i]['run_ref']['id'] != ref['id'] ||
            list[i]['run_ref']['revision'] != i + 1)
          _fail('Die Historie gehört nicht zum gewählten Mitarbeiterbeleg.');
      }
      if (!mounted || captured != epoch || !allowed) return;
      setState(() {
        items = list;
        selected = null;
        history = true;
        canExport = page['can_export'];
        busy = false;
      });
    } catch (e) {
      failure(e);
    }
  }

  Future<void> export(
    Map<String, dynamic> value, {
    String fileFormat = 'pdf',
  }) async {
    final captured = ++epoch;
    setState(() {
      busy = true;
      error = null;
    });
    try {
      await fresh();
      final opening = session.generation,
          ref = businessMap(value['run_ref']),
          path = '/payroll/employee-statements/${ref['id']}';
      final page = await payrollStatementPage(
        await session.read('$path?revision=${ref['revision']}'),
        employeeId,
        detail: true,
        reference: ref,
      );
      if (page['can_export'] != true || !_same(page['statement'], value))
        _fail(
          'Die gewählte Belegfassung ist nicht zum Export freigegeben.',
          403,
        );
      final bytes = await session.api.bytes(
        session.path(
          '$path/$fileFormat?revision=${ref['revision']}&statement_hash=${value['statement_hash']}',
        ),
        mediaType: fileFormat == 'json'
            ? 'application/json'
            : 'application/pdf',
      );
      final document = fileFormat == 'json'
          ? await payrollStatementJsonAttachment(bytes, value)
          : await payrollStatementAttachment(bytes, value);
      await fresh();
      final finalPage = await payrollStatementPage(
        await session.read('$path?revision=${ref['revision']}'),
        employeeId,
        detail: true,
        reference: ref,
      );
      if (!mounted ||
          captured != epoch ||
          opening != session.generation ||
          !allowed ||
          finalPage['can_export'] != true ||
          !_same(finalPage['statement'], value))
        return;
      await (widget.exporter ?? exportMailAttachment)(
        context,
        document,
        () =>
            mounted &&
            allowed &&
            canExport &&
            opening == session.generation &&
            captured == epoch,
      );
      if (mounted && captured == epoch) setState(() => busy = false);
    } catch (e) {
      failure(e);
    }
  }

  String money(dynamic v) {
    if (v is! int) return 'Nicht ermittelt';
    final sign = v < 0 ? '-' : '', n = v.abs();
    return businessMoney(
      '$sign${n ~/ 100}.${(n % 100).toString().padLeft(2, '0')}',
    );
  }

  Widget line(String title, String value) =>
      ListTile(dense: true, title: Text(title), subtitle: Text(value));
  List<Widget> details(Map<String, dynamic> v) {
    final c = businessMap(v['calculation']), p = v['period_summary'];
    return [
      Text(
        '${v['employee_name']} · ${v['month']} · Fassung ${v['run_ref']['revision']}',
        style: Theme.of(context).textTheme.titleLarge,
      ),
      if (c['payroll_calculation_complete'] != true)
        const Notice(
          'Lohnsteuer und Netto sind in diesem Rechenumfang noch nicht vollständig ermittelt.',
        ),
      for (final entry in statementAmounts.entries)
        line(entry.value, money(c[entry.key])),
      if ([2, 3, 4, 5].contains(v['schema_version'])) ...[
        line('Belegte Nettoabzüge', money(c['net_deductions_minor'])),
        const Text('Eigene Entgeltbestandteile'),
        for (final row in businessItems(v['earnings_summary']))
          line(
            const {
              'ordinary_work': 'Regelmäßiges Arbeitsentgelt',
              'public_holiday': 'Feiertagsvergütung',
              'sickness': 'Entgeltfortzahlung',
              'first_sickness_day_regular_wage':
                  'Entgelt am ersten Krankheitstag',
              'vacation': 'Urlaubsentgelt',
            }[row['kind']]!,
            '${(row['dates'] as List).map(businessDate).join(', ')} · ${money(row['gross_minor'])}',
          ),
        for (final label in const {
          'tax_free_external_minor':
              'Steuerfreie Reiseerstattung außerhalb des Lohnnettos',
          'flat_taxable_payroll_minor': 'Pauschal versteuerter Reiselohn',
          'individual_taxable_payroll_minor':
              'Individuell versteuerter Reiselohn',
          'benefit_in_kind_non_cash_minor': 'Sachbezug ohne Barauszahlung',
          'employee_flat_tax_deduction_minor': 'Eigener Steuerkostenabzug',
        }.entries)
          line(label.value, money(v['travel_summary'][label.key])),
        line(
          'Mahlzeitenmerkmal M',
          v['travel_summary']['letter_m'] == true ? 'Ja' : 'Nein',
        ),
      ],
      if ([3, 4, 5].contains(v['schema_version'])) ...[
        const Text('Einmalzahlung / sonstiger Bezug'),
        line(
          'Brutto der Einmalzahlung',
          money(v['one_off_summary']['amount_minor']),
        ),
        line(
          'Berechneter Zuflussstichtag',
          businessDate(v['one_off_summary']['receipt_date']),
        ),
        line(
          'Steuerjahr / SV-Zuordnungsjahr',
          '${v['one_off_summary']['tax_year']} / ${v['one_off_summary']['social_year']}',
        ),
        line(
          'Märzklausel',
          v['one_off_summary']['march_clause'] == true ? 'Ja' : 'Nein',
        ),
        for (final key in [
          'employee_social_total_minor',
          'individual_wage_tax_minor',
          'solidarity_minor',
          'church_tax_minor',
        ])
          line(
            '${statementAmounts[key]} der Einmalzahlung',
            money(v['one_off_summary'][key]),
          ),
        for (final entry in statementBranches.entries)
          line(
            '${entry.value} der Einmalzahlung',
            money(v['one_off_summary']['employee_contributions'][entry.key]),
          ),
      ],
      if (c['employee_contributions'] != null) ...[
        const Text('Arbeitnehmerbeiträge'),
        for (final entry in statementBranches.entries)
          line(entry.value, money(c['employee_contributions'][entry.key])),
      ],
      if (p != null) ...[
        const Text('Getrennte Zeiträume'),
        for (final spec in [
          ('employment_intervals', 'Beschäftigung', 'calendar_days'),
          ('tax_periods', 'Steuerzeitraum', 'tax_days'),
          ('social_periods', 'Sozialversicherung', 'days'),
        ])
          for (final item in businessItems(p[spec.$1]))
            line(
              spec.$2,
              '${businessDate(item['start'])} – ${businessDate(item['end'])} · ${item[spec.$3]} Tage',
            ),
      ],
      Notice(
        [2, 3, 4, 5].contains(v['schema_version'])
            ? 'Der berechnete Auszahlungsbetrag ist kein Zahlungsnachweis. Steuerfreie Reiseerstattungen werden außerhalb dieses Lohnnettos gezahlt. Es wurde keine amtliche Meldung übermittelt.'
            : 'Der berechnete Auszahlungsbetrag ist kein Zahlungsnachweis. Auslagen und Reisekosten werden gesondert belegt. Es wurde keine amtliche Meldung übermittelt.',
      ),
      if (canExport)
        FilledButton(
          onPressed: busy ? null : () => export(v),
          child: const Text('Eigenen PDF-Lohnnachweis herunterladen'),
        ),
      if (canExport)
        OutlinedButton(
          onPressed: busy ? null : () => export(v, fileFormat: 'json'),
          child: const Text('Eigenen JSON-Lohnnachweis herunterladen'),
        ),
      OutlinedButton(
        onPressed: busy ? null : () => showHistory(v),
        child: const Text('Beleghistorie öffnen'),
      ),
      TextButton(
        onPressed: busy ? null : load,
        child: const Text('Zur Belegübersicht'),
      ),
    ];
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(
      title: Text(
        history ? 'Mitarbeiter-Beleghistorie' : 'Meine Lohnnachweise',
      ),
      actions: [
        IconButton(
          tooltip: 'Freigabe und Belege aktualisieren',
          onPressed: busy ? null : load,
          icon: const Icon(Icons.refresh),
        ),
      ],
    ),
    body: ListView(
      padding: const EdgeInsets.all(20),
      children: [
        if (error != null) Notice(error!, error: true),
        if (busy) const LinearProgressIndicator(),
        if (!allowed && !busy)
          const BusinessEmpty(
            'Lohnnachweise nicht freigegeben',
            'Die aktuelle eigene Mitarbeiter- oder Personalfreigabe ist erforderlich.',
          ),
        if (allowed) ...[
          if (selected != null)
            ...details(selected!)
          else ...[
            const Notice(
              'Die Übersicht zeigt jeweils die neueste gespeicherte Berechnungsfassung. Frühere Fassungen bleiben in der Beleghistorie erreichbar.',
            ),
            if (items.isEmpty && !busy)
              const Text('Noch kein bestätigter Lohnnachweis vorhanden.'),
            for (final v in items)
              Card(
                child: Padding(
                  padding: const EdgeInsets.all(16),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        '${v['month']} · Fassung ${v['run_ref']['revision']}',
                      ),
                      Text(
                        'Brutto ${money(v['calculation']['gross_minor'])} · Netto ${money(v['calculation']['net_minor'])}',
                      ),
                      FilledButton(
                        onPressed: busy ? null : () => open(v),
                        child: Text(
                          history
                              ? 'Diese Fassung ansehen'
                              : 'Lohnnachweis ansehen',
                        ),
                      ),
                    ],
                  ),
                ),
              ),
            if (history)
              TextButton(
                onPressed: busy ? null : load,
                child: const Text('Zur Belegübersicht'),
              ),
          ],
        ],
      ],
    ),
  );
}

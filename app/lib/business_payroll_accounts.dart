import 'dart:convert';

import 'package:flutter/material.dart';

import 'api.dart';
import 'business_session.dart';
import 'business_widgets.dart';
import 'design.dart';

const payrollAccountKinds = {
  'identity': 'Stamm- und Steuermerkmalsnachweis',
  'payment': 'Tatsächliche Lohnzahlung',
  'carryover': 'Belegter Monatsvortrag',
};
const payrollIdentityLabels = {
  'given_name': 'Vorname laut Nachweis',
  'family_name': 'Familienname laut Nachweis',
  'date_of_birth': 'Geburtsdatum',
  'address_line': 'Straße und Hausnummer',
  'postal_code': 'Postleitzahl',
  'city': 'Wohnort',
  'country_code': 'Land',
  'tax_id': 'Persönliche Steuer-ID (11 Ziffern)',
  'employer_name': 'Arbeitgebername laut Nachweis',
  'employer_address': 'Vollständige Arbeitgeberanschrift',
  'employer_tax_number': 'Arbeitgeber-Steuernummer',
  'employment_from': 'Beschäftigungsbeginn',
  'employment_to': 'Beschäftigungsende, falls bekannt',
  'tax_source': 'Grundlage der Steuermerkmale',
  'tax_source_date': 'Datum des Steuermerkmalsnachweises',
  'valid_from': 'Gültig ab',
  'valid_to': 'Gültig bis',
  'tax_allowance_yearly_minor': 'Jährlicher Freibetrag (€)',
  'tax_addition_yearly_minor': 'Jährlicher Hinzurechnungsbetrag (€)',
  'religion_code': 'Religionsmerkmal laut Nachweis',
};
const payrollCarryLabels = {
  'gross_minor': 'Brutto laut früherer Monatsabrechnung (€)',
  'expected_net_minor': 'Netto laut früherer Monatsabrechnung (€)',
  'expected_employee_tax_minor':
      'Arbeitnehmersteuern laut früherer Monatsabrechnung (€)',
  'expected_employee_social_total_minor':
      'Arbeitnehmerbeiträge laut früherer Monatsabrechnung (€)',
  'expected_employer_social_total_minor':
      'Arbeitgeberbeiträge laut früherer Monatsabrechnung (€)',
  'expected_employer_total_minor': 'Arbeitgeberaufwand ohne Unfallversicherung laut früherer Monatsabrechnung (€)',
};
const _detailsLabels = {
  'profile_id': 'Profilquelle',
  'profile_revision': 'Profilfassung',
  'identity_id': 'Stammnachweis',
  'identity_revision': 'Stammnachweisfassung',
  'run_id': 'Monatslauf',
  'run_revision': 'Monatsfassung',
  'month': 'Vortragsmonat',
  'status': 'Vortragsstatus',
  'tax_free_payments_minor': 'Gesonderte steuerfreie Bezüge',
  'tax_free_basis': 'Grundlage steuerfreier Bezüge',
  'standard_case_confirmed': 'Unterstützten Standardfall geprüft',
};
String _amount(dynamic value) {
  if (value is! int) return '';
  return '${value < 0 ? '-' : ''}${value.abs() ~/ 100}.${(value.abs() % 100).toString().padLeft(2, '0')}';
}

String _money(dynamic value) =>
    value is int ? businessMoney(_amount(value)) : 'Nicht ermittelt';
String _ref(Map<String, dynamic> value) =>
    '${value['id']}@${value['revision']}';
Map<String, dynamic> _copy(dynamic value) =>
    businessMap(jsonDecode(jsonEncode(value)));
dynamic _ordered(dynamic value) => value is List
    ? value.map(_ordered).toList()
    : value is Map
    ? {
        for (final key in value.keys.map((k) => '$k').toList()..sort())
          key: _ordered(value[key]),
      }
    : value;
bool _same(dynamic left, dynamic right) =>
    jsonEncode(_ordered(left)) == jsonEncode(_ordered(right));
int payrollAccountMinor(dynamic value, {bool signed = false}) {
  var text = '${value ?? ''}'.trim().replaceAll(',', '.');
  final negative = signed && text.startsWith('-');
  if (negative) text = text.substring(1);
  if (!RegExp(r'^\d{1,10}(?:\.\d{1,2})?$').hasMatch(text))
    throw const FormatException(
      'Genauen belegten EUR-Betrag ausdrücklich eingeben, auch bekannte 0.',
    );
  final parts = text.split('.'),
      amount =
          int.parse(parts[0]) * 100 +
          int.parse((parts.length == 2 ? parts[1] : '').padRight(2, '0'));
  if (amount > 1000000000000)
    throw const FormatException('Betrag außerhalb des unterstützten Bereichs.');
  return negative ? -amount : amount;
}

Map<String, dynamic> payrollAccountRecord(
  dynamic raw,
  String employee, {
  String? kind,
}) {
  final value = businessMap(raw);
  if (value['employee_id'] != employee ||
      !payrollAccountKinds.containsKey(value['kind']) ||
      kind != null && value['kind'] != kind ||
      !RegExp(r'^[a-f0-9]{32}$').hasMatch('${value['id']}') ||
      !RegExp(r'^[a-f0-9]{64}$').hasMatch('${value['content_hash']}') ||
      value['revision'] is! int ||
      value['revision'] < 1 ||
      value['details'] is! Map ||
      value['confirmed'] != true)
    throw const ApiException(
      0,
      'Der Lohnkontonachweis ist nicht eindeutig an Mitarbeiter und Vorgang gebunden.',
    );
  return value;
}

void Function(dynamic) payrollAccountReceiptValidator(
  Map<String, dynamic> body,
  Map<String, dynamic> original, {
  Map<String, dynamic>? previous,
  Map<String, dynamic>? sourceEvidence,
}) {
  final frozen = _copy(body),
      file = _copy(original),
      old = previous == null ? null : _copy(previous),
      proof = sourceEvidence == null ? null : _copy(sourceEvidence);
  return (dynamic raw) {
    final value = payrollAccountRecord(
      raw,
      frozen['employee_id'],
      kind: frozen['kind'],
    );
    if (value['revision'] != frozen['revision'] + 1 ||
        old != null && value['id'] != old['id'] ||
        value['previous_hash'] != old?['content_hash'] ||
        value['correction_reason'] != (frozen['correction_reason'] ?? '') ||
        !_same(value['details'], frozen['details']) ||
        [
          'id',
          'employee_id',
          'sha256',
          'content_hash',
        ].any((key) => value['source_file']?[key] != file[key]))
      throw const ApiException(
        0,
        'Die Empfangsbestätigung passt nicht zu den ausdrücklich geprüften Lohnkontonachweisen. Der ursprüngliche Auftrag bleibt offen.',
      );
    for (final name in ['profile', 'identity', 'run']) {
      if (frozen['details']['${name}_id'] != null &&
          (value['sources']?[name]?['id'] != frozen['details']['${name}_id'] ||
              value['sources']?[name]?['revision'] !=
                  frozen['details']['${name}_revision'] ||
              value['sources']?[name]?['employee_id'] != frozen['employee_id']))
        throw const ApiException(
          0,
          'Die eingefrorene Nachweisquelle passt nicht zum ausgewählten Stand.',
        );
    }
    if (proof != null)
      for (final entry in proof.entries)
        if (!_same(value['sources']?[entry.key], entry.value))
          throw const ApiException(
            0,
            'Der zurückgegebene Quelleninhalt stimmt nicht mit der geprüften Fassung überein.',
          );
  };
}

Map<String, dynamic> payrollAccountDetails(
  String kind,
  Map<String, dynamic> values,
  Map<String, List<Map<String, dynamic>>> sources, {
  int count = 0,
}) {
  if (!payrollAccountKinds.containsKey(kind))
    throw const FormatException('Unbekannte Lohnkontonachweisart.');
  final details = <String, dynamic>{};
  void choose(String name, String collection) {
    final source = sources[collection]
        ?.where((r) => _ref(r) == values['${name}_ref'])
        .firstOrNull;
    if (source == null)
      throw const FormatException(
        'Die belegte Quellfassung ausdrücklich auswählen.',
      );
    details['${name}_id'] = source['id'];
    details['${name}_revision'] = source['revision'];
  }

  if (values['standard_case_confirmed'] != true)
    throw const FormatException(
      'Den unterstützten Standardfall ausdrücklich bestätigen.',
    );
  if (kind == 'identity') {
    choose('profile', 'profiles');
    for (final key in payrollIdentityLabels.keys)
      details[key] = key.endsWith('_minor')
          ? payrollAccountMinor(values[key])
          : key == 'employment_to' && (values[key] == null || values[key] == '')
          ? null
          : '${values[key] ?? ''}'.trim();
    if (details['country_code'] != 'DE' ||
        ![
          'elstam_imported',
          'tax_office_certificate',
          'flat_minijob_evidence',
        ].contains(details['tax_source']))
      throw const FormatException(
        'Land und tatsächliche Herkunft der Steuermerkmale ausdrücklich wählen.',
      );
  } else {
    choose('identity', 'identities');
    if (kind == 'payment')
      choose('run', 'runs');
    else {
      choose('profile', 'profiles');
      details['month'] = values['month'];
      for (final key in payrollCarryLabels.keys)
        details[key] = payrollAccountMinor(
          values[key],
          signed: key == 'expected_net_minor',
        );
      if (!['active', 'void'].contains(values['status']))
        throw const FormatException('Vortragsstatus ausdrücklich wählen.');
      details['status'] = values['status'];
    }
    if (count < 1 || count > 20)
      throw const FormatException('Ein bis 20 belegte Zahlungsteile erfassen.');
    details['payments'] = [
      for (var i = 0; i < count; i++)
        {
          'paid_on': values['paid_on_$i'],
          'amount_minor': payrollAccountMinor(
            values['amount_$i'],
            signed: true,
          ),
          'payment_reference': '${values['reference_$i'] ?? ''}'.trim(),
        },
    ];
    if ((details['payments'] as List).any((p) => p['amount_minor'] == 0))
      throw const FormatException(
        'Eine tatsächliche Zahlung oder Nachzahlung muss einen Betrag ungleich null haben.',
      );
    details['tax_free_payments_minor'] = payrollAccountMinor(
      values['tax_free_payments_minor'],
    );
    details['tax_free_basis'] = '${values['tax_free_basis'] ?? ''}'.trim();
  }
  details['standard_case_confirmed'] = true;
  return details;
}

class BusinessPayrollAccountsPage extends StatefulWidget {
  const BusinessPayrollAccountsPage({
    super.key,
    required this.session,
    required this.employee,
    required this.onOriginal,
  });
  final BusinessSession session;
  final Map<String, dynamic> employee;
  final Future<void> Function(Map<String, dynamic>) onOriginal;
  @override
  State<BusinessPayrollAccountsPage> createState() =>
      _BusinessPayrollAccountsPageState();
}

class _BusinessPayrollAccountsPageState
    extends State<BusinessPayrollAccountsPage> {
  BusinessSession get session => widget.session;
  String get employeeId => widget.employee['id'];
  String get key => 'payroll-account-$employeeId';
  Map<String, dynamic> employee = {};
  List<Map<String, dynamic>> records = [], history = [];
  String? actorId, error, message;
  Object? generation;
  bool loading = false, busy = false, denied = false;
  int epoch = 0;
  bool get available =>
      session.hasFeature('payroll_wage_account') &&
      session.hasModule('payroll_accounts') &&
      session.projectId == null;
  bool get readable =>
      !denied &&
      available &&
      (session.can('personnel.read') ||
          actorId == employee['user_id'] && session.can('time.own'));
  bool writable(String kind) =>
      readable &&
      session.can('personnel.read') &&
      session.canWrite(
        kind == 'identity' ? 'personnel.write' : 'personnel.approve',
      ) &&
      session.sectionEnabled('personnel');
  @override
  void initState() {
    super.initState();
    employee = _copy(widget.employee);
    generation = session.generation;
    session.addListener(changed);
    load();
  }

  @override
  void dispose() {
    epoch++;
    session.removeListener(changed);
    super.dispose();
  }

  void changed() {
    if (!mounted) return;
    if (!readable || generation != session.generation) {
      epoch++;
      records = [];
      history = [];
      generation = session.generation;
    }
    setState(() {});
  }

  void fail(Object e) {
    if (!mounted) return;
    setState(() {
      if (e is ApiException && [401, 403, 404].contains(e.status)) {
        denied = true;
        records = [];
        history = [];
      }
      error = e is ApiException
          ? e.message
          : e is FormatException
          ? e.message
          : 'Der Nachweis konnte nicht geprüft werden.';
    });
  }

  Future<void> load({bool refresh = false}) async {
    if (refresh) {
      await session.load();
      denied = false;
    }
    if (!mounted || !available) return;
    final captured = ++epoch;
    setState(() {
      loading = true;
      error = null;
    });
    try {
      final me = businessMap(await session.api.call('/api/me')),
          people = businessItems(await session.read('/employees'));
      final person = people.where((p) => p['id'] == employeeId).firstOrNull;
      if (person == null)
        throw const ApiException(403, 'Mitarbeiter ist nicht freigegeben.');
      if (!mounted || captured != epoch) return;
      actorId = me['id'];
      employee = person;
      if (!readable)
        throw const ApiException(
          403,
          'Lohnkontonachweise sind nicht freigegeben.',
        );
      final page = businessMap(
        await session.read('/payroll/account-records?employee_id=$employeeId'),
      );
      if (page['employee_id'] != employeeId)
        throw const ApiException(
          0,
          'Nachweise gehören nicht zum ausgewählten Mitarbeiter.',
        );
      final items = businessItems(page)
          .map((r) => payrollAccountRecord(r, employeeId))
          .toList();
      if (mounted && captured == epoch && readable)
        setState(() => records = items);
    } catch (e) {
      if (mounted && captured == epoch) fail(e);
    } finally {
      if (mounted && captured == epoch) setState(() => loading = false);
    }
  }

  Future<void> fresh({String? kind}) async {
    await session.load();
    if (!mounted ||
        session.error != null ||
        !readable ||
        kind != null && !writable(kind))
      throw const ApiException(
        403,
        'Aktuelle Mitarbeiter- und Lohnkontorechte fehlen.',
      );
    final page = businessMap(
      await session.read('/payroll/account-records?employee_id=$employeeId'),
    );
    if (page['employee_id'] != employeeId)
      throw const ApiException(
        0,
        'Der Mitarbeiterbezug konnte nicht bestätigt werden.',
      );
    for (final item in businessItems(page))
      payrollAccountRecord(item, employeeId);
  }

  Future<void> repeat() async {
    if (busy) return;
    setState(() => busy = true);
    try {
      await session.repeatPayrollAccountCommand(employeeId);
      await load();
      if (mounted)
        setState(() => message = 'Der ursprüngliche Nachweis ist bestätigt.');
    } catch (e) {
      fail(e);
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  Future<void> openHistory(Map<String, dynamic> value) async {
    try {
      await fresh();
      final opening = session.generation,
          page = businessItems(
            await session.read(
              '/payroll/account-records/${value['id']}/history',
            ),
          );
      for (final r in page) {
        payrollAccountRecord(r, employeeId, kind: value['kind']);
        if (r['id'] != value['id'])
          throw const ApiException(
            0,
            'Historie gehört nicht zum gewählten Nachweis.',
          );
      }
      if (mounted && readable && opening == session.generation)
        setState(() => history = page);
    } catch (e) {
      fail(e);
    }
  }

  Future<void> edit(String kind, [Map<String, dynamic>? previous]) async {
    if (busy || !writable(kind) || session.pending(key)) return;
    try {
      await fresh(kind: kind);
      int count = 0;
      if (kind != 'identity') {
        int? selected;
        await showDialog<void>(
          context: context,
          builder: (_) => BusinessEditor(
            session: session,
            title: 'Belegte Zahlungsteile auswählen',
            readPermission: 'personnel.read',
            writePermission: 'personnel.approve',
            readAllowed: () => readable,
            fields: const [
              BusinessField(
                'count',
                'Anzahl belegter Zahlungsteile',
                type: BusinessInput.integer,
                required: true,
              ),
            ],
            initial: {'count': previous?['details']['payments'].length ?? 1},
            saveLabel: 'Zahlungsnachweise erfassen',
            onSave: (values) async {
              final n = values['count'];
              if (n is! int || n < 1 || n > 20)
                throw const FormatException(
                  'Ein bis 20 tatsächlich belegte Zahlungsteile angeben.',
                );
              selected = n;
            },
          ),
        );
        if (selected == null || !mounted) return;
        count = selected!;
      }
      await fresh(kind: kind);
      final opening = session.generation;
      final pages = await Future.wait(
        [
          '/payroll/profiles',
          '/payroll/runs',
          '/payroll/account-records',
          '/personnel/files',
        ].map((path) => session.read('$path?employee_id=$employeeId')),
      );
      for (final page in pages)
        if (businessMap(page)['employee_id'] != employeeId ||
            businessItems(page).any((row) => row['employee_id'] != employeeId))
          throw const ApiException(0, 'Quellen gehören nicht zum Mitarbeiter.');
      if (!mounted || !readable || opening != session.generation) return;
      final sources = {
            'profiles': businessItems(pages[0]),
            'runs': businessItems(pages[1]),
            'identities': businessItems(pages[2])
                .where((r) => r['kind'] == 'identity')
                .toList(),
          },
          files = businessItems(pages[3])
              .where((f) => f['purpose'] == 'personnel')
              .toList();
      if (previous != null)
        for (final entry in {
          'profile': 'profiles',
          'run': 'runs',
          'identity': 'identities',
        }.entries) {
          final source = businessMap(previous['sources']?[entry.key]);
          if (source.isNotEmpty &&
              !sources[entry.value]!.any((s) => _ref(s) == _ref(source)))
            sources[entry.value]!.add(source);
        }
      final details = businessMap(previous?['details']),
          fields = <BusinessField>[],
          initial = <String, dynamic>{};
      void sourceField(String name, String collection, String label) {
        fields.add(
          BusinessField(
            '${name}_ref',
            label,
            type: BusinessInput.choice,
            required: true,
            choices: {
              '': 'Quelle ausdrücklich auswählen',
              for (final r in sources[collection]!)
                _ref(
                  r,
                ): "${r['profile'] != null ? '${r['profile']['employment_kind'] == 'minijob' ? 'Minijob' : 'Regulär'} · ${r['profile']['effective_from']}' : r['source']?['month'] ?? '${r['sources']?['profile']?['profile']?['employment_kind'] == 'minijob' ? 'Minijob' : 'Regulär'} · ${r['details']?['valid_from']} · Profilfassung ${r['details']?['profile_revision']}'} · Fassung ${r['revision']}",
            },
          ),
        );
        initial['${name}_ref'] = details['${name}_id'] == null
            ? ''
            : '${details['${name}_id']}@${details['${name}_revision']}';
      }

      if (kind == 'identity') {
        sourceField(
          'profile',
          'profiles',
          'Belegtes Steuer- und Versicherungsprofil',
        );
        for (final entry in payrollIdentityLabels.entries) {
          final name = entry.key,
              type = name.endsWith('_minor')
                  ? BusinessInput.decimal
                  : [
                      'date_of_birth',
                      'employment_from',
                      'employment_to',
                      'tax_source_date',
                      'valid_from',
                      'valid_to',
                    ].contains(name)
                  ? BusinessInput.date
                  : BusinessInput.text;
          final choice = name == 'country_code'
              ? {'': 'Bitte wählen', 'DE': 'Deutschland'}
              : name == 'tax_source'
              ? {
                  '': 'Herkunft ausdrücklich wählen',
                  'elstam_imported': 'Vorliegender ELStAM-Nachweis',
                  'tax_office_certificate': 'Bescheinigung des Finanzamts',
                  'flat_minijob_evidence':
                      'Pauschal besteuerter Minijobnachweis',
                }
              : null;
          fields.add(
            BusinessField(
              name,
              entry.value,
              type: choice == null ? type : BusinessInput.choice,
              required: name != 'employment_to',
              choices: choice ?? const {},
              hint: name == 'religion_code'
                  ? 'Geprüftes Merkmal aus dem Nachweis; none bedeutet keine Kirchensteuerpflicht.'
                  : null,
            ),
          );
          initial[name] = name.endsWith('_minor')
              ? _amount(details[name])
              : details[name];
        }
      } else {
        sourceField(
          'identity',
          'identities',
          'Gültiger Stamm- und Steuermerkmalsnachweis',
        );
        if (kind == 'payment')
          sourceField('run', 'runs', 'Abgeschlossene Monatsberechnung');
        else {
          sourceField(
            'profile',
            'profiles',
            'Belegtes Steuer- und Versicherungsprofil',
          );
          fields.add(
            const BusinessField(
              'month',
              'Belegter Vortragsmonat (JJJJ-MM)',
              required: true,
            ),
          );
          initial['month'] = details['month'];
          for (final entry in payrollCarryLabels.entries) {
            fields.add(
              BusinessField(
                entry.key,
                entry.value,
                type: BusinessInput.decimal,
                required: true,
              ),
            );
            initial[entry.key] = _amount(details[entry.key]);
          }
          fields.add(
            const BusinessField(
              'status',
              'Vortragsstatus',
              type: BusinessInput.choice,
              required: true,
              choices: {
                '': 'Bitte wählen',
                'active': 'Als belegten Monat übernehmen',
                'void': 'Vortrag begründet aufheben',
              },
            ),
          );
          initial['status'] = details['status'] ?? '';
        }
        for (var i = 0; i < count; i++) {
          final p = businessMap(
            (details['payments'] as List? ?? []).elementAtOrNull(i),
          );
          fields.addAll([
            BusinessField(
              'paid_on_$i',
              'Tatsächlicher Zahlungstag ${i + 1}',
              type: BusinessInput.date,
              required: true,
            ),
            BusinessField(
              'amount_$i',
              'Belegter Zahlbetrag EUR ${i + 1}',
              type: BusinessInput.decimal,
              required: true,
              hint: 'Negativ nur für tatsächliche Arbeitnehmer-Nachzahlung. Nur tatsächlich geflossene Beträge erfassen.',
            ),
            BusinessField(
              'reference_$i',
              'Zahlungsnachweis / Referenz ${i + 1}',
              required: true,
            ),
          ]);
          initial['paid_on_$i'] = p['paid_on'];
          initial['amount_$i'] = _amount(p['amount_minor']);
          initial['reference_$i'] = p['payment_reference'];
        }
        fields.addAll(const [
          BusinessField(
            'tax_free_payments_minor',
            'Gesondert belegte steuerfreie Bezüge (€)',
            type: BusinessInput.decimal,
            required: true,
          ),
          BusinessField(
            'tax_free_basis',
            'Rechtsgrundlage und Beleg steuerfreier Bezüge',
            type: BusinessInput.multiline,
          ),
        ]);
        initial['tax_free_payments_minor'] = _amount(
          details['tax_free_payments_minor'],
        );
        initial['tax_free_basis'] = details['tax_free_basis'];
      }
      fields.addAll([
        const BusinessField(
          'standard_case_confirmed',
          'Ich habe den unterstützten inländischen Standardfall mit laufendem Barlohn ohne weitere Sonderbezüge oder U-/S-Fälle geprüft.',
          type: BusinessInput.toggle,
        ),
        BusinessField(
          'source_file_id',
          'Geschütztes Original des Nachweises',
          type: BusinessInput.choice,
          required: true,
          choices: {
            '': 'Original ausdrücklich auswählen',
            for (final file in files) '${file['id']}': '${file['filename']}',
          },
        ),
        if (previous != null)
          const BusinessField(
            'correction_reason',
            'Begründung der Nachweiskorrektur',
            type: BusinessInput.multiline,
            required: true,
          ),
        const BusinessField(
          'confirmed',
          'Ich bestätige die tatsächlichen belegten Angaben und die ausgewählten Quellfassungen.',
          type: BusinessInput.toggle,
        ),
      ]);
      initial['source_file_id'] = previous?['source_file']['id'] ?? '';
      initial['confirmed'] = initial['standard_case_confirmed'] = false;
      await showDialog<void>(
        context: context,
        builder: (_) => BusinessEditor(
          session: session,
          title:
              '${previous == null ? 'Erfassung' : 'Berichtigung'} · ${payrollAccountKinds[kind]}',
          fields: fields,
          initial: initial,
          pendingKey: key,
          readPermission: 'personnel.read',
          writePermission: kind == 'identity'
              ? 'personnel.write'
              : 'personnel.approve',
          readAllowed: () => readable && opening == session.generation,
          saveLabel: 'Geprüften Lohnkontonachweis speichern',
          onSave: (values) async {
            await fresh(kind: kind);
            if (session.pending(key)) {
              await session.repeatPayrollAccountCommand(employeeId);
              return;
            }
            if (values['confirmed'] != true)
              throw const FormatException(
                'Belegte Angaben ausdrücklich bestätigen.',
              );
            final file = files
                .where(
                  (f) =>
                      f['id'] == values['source_file_id'] &&
                      f['employee_id'] == employeeId,
                )
                .firstOrNull;
            if (file == null)
              throw const FormatException(
                'Passendes geschütztes Original auswählen.',
              );
            final body = <String, dynamic>{
              'employee_id': employeeId,
              'kind': kind,
              'details': payrollAccountDetails(
                kind,
                values,
                sources,
                count: count,
              ),
              'source_file_id': file['id'],
              'confirmed': true,
              'revision': previous?['revision'] ?? 0,
              if (previous != null) 'id': previous['id'],
              if (previous != null)
                'correction_reason': '${values['correction_reason'] ?? ''}'
                    .trim(),
            };
            await session.command(
              key,
              '/payroll/account-records',
              body,
              validateResult: payrollAccountReceiptValidator(
                body,
                file,
                previous: previous,
                sourceEvidence: {
                  for (final entry in {
                    'profile': 'profiles',
                    'run': 'runs',
                    'identity': 'identities',
                  }.entries)
                    if (body['details']['${entry.key}_id'] != null)
                      entry.key: sources[entry.value]!.firstWhere(
                        (v) =>
                            v['id'] == body['details']['${entry.key}_id'] &&
                            v['revision'] ==
                                body['details']['${entry.key}_revision'],
                      ),
                },
              ),
            );
          },
        ),
      );
      if (mounted && readable) await load();
    } catch (e) {
      fail(e);
    }
  }

  Widget card(Map<String, dynamic> value, {bool historical = false}) => Card(
    child: Padding(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            '${payrollAccountKinds[value['kind']]} · Fassung ${value['revision']}',
            style: Theme.of(context).textTheme.titleMedium,
          ),
          ExpansionTile(
            title: const Text('Belegte Angaben'),
            children: [
              for (final entry in businessMap(
                value['details'],
              ).entries.where((e) => e.key != 'payments'))
                ListTile(
                  title: Text(
                    payrollIdentityLabels[entry.key] ??
                        payrollCarryLabels[entry.key] ??
                        _detailsLabels[entry.key] ??
                        entry.key,
                  ),
                  subtitle: Text(
                    entry.key.endsWith('_minor')
                        ? _money(entry.value)
                        : entry.value == null
                        ? 'Nicht angegeben'
                        : entry.value == true
                        ? 'Ja'
                        : '${entry.value}',
                  ),
                ),
            ],
          ),
          for (final p in businessItems(value['details']['payments'] ?? []))
            ListTile(
              title: Text(
                '${businessDate(p['paid_on'])} · ${_money(p['amount_minor'])}',
              ),
              subtitle: Text(
                '${p['payment_reference']}${p['amount_minor'] < 0 ? ' · Arbeitnehmer-Nachzahlung' : ''}',
              ),
            ),
          if ('${value['correction_reason'] ?? ''}'.isNotEmpty)
            Text('Korrektur: ${value['correction_reason']}'),
          Wrap(
            spacing: 8,
            children: [
              TextButton(
                onPressed: () =>
                    widget.onOriginal(businessMap(value['source_file'])),
                child: const Text('Nachweisoriginal öffnen'),
              ),
              if (!historical)
                TextButton(
                  onPressed: () => openHistory(value),
                  child: const Text('Nachweishistorie'),
                ),
              if (!historical &&
                  writable(value['kind']) &&
                  !session.pending(key))
                OutlinedButton(
                  onPressed: () => edit(value['kind'], value),
                  child: const Text('Nachweis berichtigen'),
                ),
            ],
          ),
        ],
      ),
    ),
  );
  @override
  Widget build(BuildContext context) {
    final pending = session.pendingCommandValues(
      key,
      path: '/payroll/account-records',
    );
    return Scaffold(
      appBar: AppBar(
        title: Text('Lohnkonto-Nachweise · ${employee['name']}'),
        actions: [
          IconButton(
            tooltip: 'Rechte und Nachweise aktualisieren',
            onPressed: loading || busy ? null : () => load(refresh: true),
            icon: const Icon(Icons.refresh),
          ),
        ],
      ),
      body: !readable
          ? Padding(
              padding: const EdgeInsets.all(24),
              child: BusinessEmpty(
                'Lohnkonto nicht freigegeben',
                error ?? 'Aktuelle Personal- oder eigene Mitarbeiterfreigabe erforderlich.',
              ),
            )
          : ListView(
              padding: const EdgeInsets.all(20),
              children: [
                const Notice(
                  'Geschützte Stammnachweise, tatsächliche Zahlungen und belegte Vortragsmonate. Hier erfolgt keine Zahlung oder Meldung. Fehlende Angaben bleiben in der Jahresübersicht erkennbar.',
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
                          const Text('Nachweisbestätigung offen'),
                          const Text(
                            'Der Vorgang kann bereits gespeichert sein. Die Wiederholung bleibt unverändert.',
                          ),
                          FilledButton(
                            onPressed: !busy && writable('${pending['kind']}')
                                ? repeat
                                : null,
                            child: const Text(
                              'Ursprünglichen Nachweis erneut senden',
                            ),
                          ),
                        ],
                      ),
                    ),
                  ),
                if (pending == null)
                  Wrap(
                    spacing: 8,
                    runSpacing: 8,
                    children: [
                      for (final entry in payrollAccountKinds.entries)
                        if (writable(entry.key))
                          OutlinedButton(
                            onPressed: () => edit(entry.key),
                            child: Text('${entry.value} erfassen'),
                          ),
                    ],
                  ),
                if (records.isEmpty && !loading)
                  const BusinessEmpty(
                    'Noch keine Lohnkonto-Nachweise',
                    'Geschütztes Original in der Personalakte aufnehmen und die dazugehörigen Angaben ausdrücklich bestätigen.',
                  ),
                for (final r in records) card(r),
                if (history.isNotEmpty)
                  Text(
                    'Unveränderliche Nachweishistorie',
                    style: Theme.of(context).textTheme.titleLarge,
                  ),
                for (final r in history) card(r, historical: true),
              ],
            ),
    );
  }
}

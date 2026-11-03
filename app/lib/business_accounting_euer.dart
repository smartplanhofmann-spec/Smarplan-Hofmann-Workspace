import 'dart:convert';
import 'dart:typed_data';

import 'package:flutter/material.dart';
import 'package:cryptography/cryptography.dart';

import 'api.dart';
import 'business_payroll_cash.dart';
import 'business_travel_cash.dart';
import 'business_accounting.dart'
    show businessAccountingReadable, BusinessAccountingPage;
import 'business_project_receipts.dart';
import 'business_accounting_profile.dart';
import 'business_session.dart';
import 'business_widgets.dart';
import 'design.dart';
import 'mail_attachment_preview.dart';
import 'mail_attachment_widgets.dart' show exportMailAttachment;

const euerPath = '/accounting/euer', euerPendingKey = 'accounting-euer';
const euerOperations = {
  'travel_cash': 'Belegte Reiseerstattung einordnen',
  'payroll_cash': 'Belegte Lohnzahlungen einordnen',
  'cash': 'Geldfluss fachlich buchen',
  'input_vat': 'Vorsteuerrecht prüfen',
  'external_cash': 'Steuer- oder Kapitalgeldbewegung',
  'asset': 'Anlagegut erfassen',
  'depreciation': 'Lineare Jahres-AfA',
  'reverse': 'Buchung gegenbuchen',
  'correct': 'Buchung berichtigen',
  'period': 'Monatsperiode prüfen',
  'export': 'Jahresprüfpaket festhalten',
};
const euerCategories = {
  ...payrollCashCategories,
  ...travelCashCategories,
  'sales': 'Inländischer Erlös',
  'materials': 'Material',
  'external_services': 'Fremdleistungen',
  'rent': 'Miete',
  'insurance': 'Versicherung',
  'software': 'Software',
  'travel': 'Reisekosten',
  'other_expense': 'Sonstiger Aufwand',
  'asset_acquisition': 'Anlageanschaffung · kein sofortiger Nettoaufwand',
  'vat_payment': 'Umsatzsteuerzahlung',
  'vat_refund': 'Umsatzsteuererstattung',
  'owner_contribution': 'Geldeinlage',
  'owner_withdrawal': 'Geldentnahme',
  'loan_received': 'Darlehensaufnahme',
  'loan_repayment': 'Darlehenstilgung',
  'vat_collected': 'Vereinnahmte Umsatzsteuer',
  'paid_input_vat': 'Bezahlte abziehbare Vorsteuer',
  'input_vat': 'Vorsteuerrecht',
  'output_vat': 'Ist-Umsatzsteuer',
  'private_portion': 'Privatanteil',
  'depreciation': 'Lineare AfA',
};
const _moneyFields = {
  'business_net': 'Betrieblicher Nettoanteil',
  'deductible_net': 'Davon abziehbarer Nettoaufwand',
  'business_tax': 'Betrieblicher Steueranteil',
  'deductible_input_tax': 'Davon bezahlte abziehbare Vorsteuer',
  'deductible_tax_cost': 'Davon als Kosten abziehbare Steuer',
};
const _externalDirection = {
  'vat_payment': 'out',
  'vat_refund': 'in',
  'owner_contribution': 'in',
  'owner_withdrawal': 'out',
  'loan_received': 'in',
  'loan_repayment': 'out',
};

bool businessEuerReadable(BusinessSession session) =>
    businessAccountingReadable(session) &&
    session.hasFeature('accounting_euer') &&
    session.hasModule('accounting_euer');
bool businessEuerWritable(BusinessSession session) =>
    businessEuerReadable(session) &&
    session.canWrite('accounting.prepare') &&
    session.canWrite('accounting.admin') &&
    session.canWrite('finance.write') &&
    session.sectionEnabled('finance');
String euerMoney(Object? input) {
  final value = businessDecimal('$input');
  if (!RegExp(r'^\d{1,13}(?:\.\d{1,2})?$').hasMatch(value)) {
    throw const FormatException(
      'EUR-Betrag ohne Rundung mit höchstens zwei Nachkommastellen eingeben.',
    );
  }
  final parts = value.split('.');
  return '${BigInt.parse(parts[0])}.${(parts.length == 2 ? parts[1] : '').padRight(2, '0')}';
}

String _account(Object? input) {
  final value = '$input'.trim();
  if (!RegExp(r'^\d{4}$').hasMatch(value))
    throw const FormatException(
      'Das ausdrücklich geprüfte vierstellige SKR04-Konto eingeben.',
    );
  return value;
}

String _required(Object? input, String label) {
  final value = '${input ?? ''}'.trim();
  if (value.isEmpty ||
      value.length > 1000 ||
      RegExp(r'[\x00-\x1f\x7f]').hasMatch(value))
    throw FormatException('$label als einzeiligen Text eingeben.');
  return value;
}

dynamic _ordered(dynamic value) {
  if (value is Map) {
    final keys = value.keys.map((v) => '$v').toList()..sort();
    return {for (final key in keys) key: _ordered(value[key])};
  }
  if (value is List) return value.map(_ordered).toList();
  return value;
}

bool euerSame(dynamic a, dynamic b) =>
    jsonEncode(_ordered(a)) == jsonEncode(_ordered(b));
Map<String, dynamic> _copy(Map<String, dynamic> value) =>
    businessMap(jsonDecode(jsonEncode(value)));
Map<String, dynamic> euerPreview(
  Map<String, dynamic> value,
  Map<String, dynamic> body,
) {
  if (!RegExp(r'^[a-f0-9]{64}$').hasMatch('${value['preview_hash']}') ||
      body.entries.any((entry) => !euerSame(value[entry.key], entry.value)) ||
      value['postings'] is! List) {
    throw const ApiException(
      0,
      'Die Buchungsvorschau gehört nicht zu den eingegebenen Angaben.',
    );
  }
  return value;
}

void Function(dynamic) euerReceiptValidator(
  Map<String, dynamic> body,
  Map<String, dynamic> preview,
) {
  final frozen = _copy(body), proof = _copy(preview);
  return (dynamic raw) {
    final value = businessMap(raw);
    if (!RegExp(r'^[a-f0-9]{32}$').hasMatch('${value['id']}') ||
        !RegExp(r'^[a-f0-9]{64}$').hasMatch('${value['entry_hash']}') ||
        value['sequence'] != frozen['expected_revision'] + 1 ||
        value['previous_hash'] != frozen['state_hash'] ||
        [
          'operation',
          'payload',
          'reason',
          'evidence_reference',
          'preview_hash',
        ].any((key) => !euerSame(value[key], frozen[key])) ||
        [
          'postings',
          'effect',
          'reverses',
          'profile',
          'artifact',
          'control',
          'target',
          'rule_version',
        ].any((key) => !euerSame(value[key], proof[key]))) {
      throw const ApiException(
        0,
        'Die Buchungsbestätigung passt nicht zur geprüften Vorschau. Der ursprüngliche Auftrag bleibt für die Wiederholung erhalten.',
      );
    }
  };
}

Future<VerifiedMailAttachment> euerExportAttachment(
  Map<String, dynamic> value,
  Map<String, dynamic> entry, {
  required bool csv,
}) async {
  if (value['entry_id'] != entry['id'] ||
      value['entry_hash'] != entry['entry_hash'] ||
      value['format'] != 'smartplan_euer_review_v1' ||
      value['official_tax_return'] != false ||
      value['datev_certified'] != false ||
      !euerSame(entry['artifact'], {
        for (final key in businessMap(entry['artifact']).keys) key: value[key],
      }))
    throw const ApiException(
      0,
      'Das Prüfpaket stimmt nicht mit dem gespeicherten Journalnachweis überein.',
    );
  for (final pair in [
    ('report', jsonEncode(_ordered(value['report']))),
    ('csv', '${value['csv']}'),
  ]) {
    final hash = (await Sha256().hash(utf8.encode(pair.$2))).bytes
        .map((v) => v.toRadixString(16).padLeft(2, '0'))
        .join();
    if (hash != value['${pair.$1}_sha256'])
      throw const ApiException(
        0,
        'Die Prüfsumme der Jahresausgabe stimmt nicht.',
      );
  }
  final bytes = Uint8List.fromList(
    utf8.encode(
      csv
          ? '${value['csv']}'
          : const JsonEncoder.withIndent('  ').convert(value),
    ),
  );
  final hash = (await Sha256().hash(bytes)).bytes
      .map((v) => v.toRadixString(16).padLeft(2, '0'))
      .join();

  return VerifiedMailAttachment(
    bytes: bytes,
    filename:
        'Smartplan-EUER-${businessMap(value['report'])['year']}-${entry['id']}.${csv ? 'csv' : 'json'}',
    mediaType: csv ? 'text/csv' : 'application/json',
    sha256: hash,
  );
}

class EuerForm {
  EuerForm(this.fields, this.initial, this.payload);
  final List<BusinessField> fields;
  final Map<String, dynamic> initial;
  final Map<String, dynamic> Function(Map<String, dynamic>) payload;
}

EuerForm euerForm(
  String operation,
  Map<String, dynamic> source, {
  Map<String, dynamic> initial = const {},
  List<Map<String, dynamic>> accounts = const [],
  List<Map<String, dynamic>> cashSources = const [],
}) {
  final fields = <BusinessField>[], values = <String, dynamic>{...initial};
  void input(
    String key,
    String label, {
    BusinessInput type = BusinessInput.text,
    bool required = true,
    String? hint,
  }) => fields.add(
    BusinessField(key, label, type: type, required: required, hint: hint),
  );
  void choice(
    String key,
    String label,
    Map<String, String> choices, {
    String? value,
  }) {
    fields.add(
      BusinessField(
        key,
        label,
        type: BusinessInput.choice,
        required: true,
        choices: {'': 'Bitte ausdrücklich wählen', ...choices},
      ),
    );
    values.putIfAbsent(key, () => value ?? '');
  }

  void toggle(String key, String label) => fields.add(
    BusinessField(key, label, type: BusinessInput.toggle, initial: false),
  );
  void account([
    String key = 'account',
    String label = 'Geprüftes SKR04-Sachkonto',
  ]) => input(
    key,
    label,
    hint: 'Vier Ziffern; keine automatisch vorgeschlagene Zuordnung',
  );
  void yearRule(String? cashDate) {
    input('euer_date', 'EÜR-Zuordnungsdatum', type: BusinessInput.date);
    values.putIfAbsent('euer_date', () => cashDate ?? '');
    choice('year_kind', 'Jahreszuordnung', {
      'cash': 'Tatsächlicher Geldflusstag',
      'ten_day': 'Geprüfte Zehn-Tage-Ausnahme',
    }, value: businessMap(initial['year_rule'])['kind'] ?? 'cash');
    input(
      'economic_year',
      'Nur Zehn-Tage-Ausnahme: wirtschaftliches Jahr',
      type: BusinessInput.integer,
      required: false,
    );
    input(
      'due_date',
      'Nur Zehn-Tage-Ausnahme: belegte Fälligkeit',
      type: BusinessInput.date,
      required: false,
    );
    toggle(
      'recurring',
      'Nur Zehn-Tage-Ausnahme: regelmäßig wiederkehrender Vorgang ausdrücklich geprüft',
    );
    final rule = businessMap(initial['year_rule']);
    for (final key in ['economic_year', 'due_date', 'recurring'])
      if (rule.containsKey(key)) values[key] = rule[key];
  }

  Map<String, dynamic> rule(Map<String, dynamic> v) => v['year_kind'] == 'cash'
      ? {'kind': 'cash'}
      : {
          'kind': 'ten_day',
          'economic_year': v['economic_year'],
          'due_date': v['due_date'],
          'recurring': v['recurring'] == true,
        };
  final event = businessMap(source['event']),
      receipt = businessMap(source['receipt']);
  Map<String, dynamic> receiptBase() => {
    'receipt_id': receipt['receipt_id'],
    'source_hash': source['source_hash'],
  };
  late Map<String, dynamic> Function(Map<String, dynamic>) build;
  switch (operation) {
    case 'travel_cash':
      final categories = travelCashCategoryKeys(source);
      for (final category in categories) {
        account(
          'travel_$category',
          '${travelCashCategories[category]} · geprüftes SKR04-Konto',
        );
        if (initial['accounts']?[category] != null)
          values['travel_$category'] = initial['accounts'][category];
      }
      build = (v) => {
        'payment_id': source['id'],
        'revision': source['revision'],
        'source_hash': source['source_hash'],
        'accounts': {
          for (final category in categories)
            category: _account(v['travel_$category']),
        },
      };
      break;
    case 'payroll_cash':
      final categories = payrollCashCategoryKeys(source);
      for (final category in categories) {
        account(
          'payroll_$category',
          '${payrollCashCategories[category]} · geprüftes SKR04-Konto',
        );
        if (initial['accounts']?[category] != null)
          values['payroll_$category'] = initial['accounts'][category];
      }
      build = (v) => {
        'batch_id': source['id'],
        'revision': source['revision'],
        'source_hash': source['source_hash'],
        'accounts': {
          for (final category in categories)
            category: _account(v['payroll_$category']),
        },
      };
      break;
    case 'cash':
      yearRule(event['cash_date']);
      final units = businessItems(source['units']);
      final payment = businessMap(event['source'])['kind'] == 'payment';
      final saved = {
        for (final row in businessItems(initial['lines'] ?? []))
          row['unit_id']: row,
      };
      for (var i = 0; i < units.length; i++) {
        final unit = units[i], prefix = 'u$i';
        choice(
          '${prefix}_category',
          'Anteil ${i + 1}: Kosten-/Erlösart',
          payment
              ? {'sales': euerCategories['sales']!}
              : {
                  for (final k in [
                    'materials',
                    'external_services',
                    'rent',
                    'insurance',
                    'software',
                    'travel',
                    'other_expense',
                    'asset_acquisition',
                  ])
                    k: euerCategories[k]!,
                },
        );
        for (final f in _moneyFields.entries)
          input(
            '${prefix}_${f.key}',
            'Anteil ${i + 1}: ${f.value} (€)',
            type: BusinessInput.decimal,
            hint:
                'Belegt: ${businessMoney(unit['net'])} netto / ${businessMoney(unit['tax'])} Steuer. Keine automatische Abzugsquote.',
          );
        account(
          '${prefix}_account',
          'Anteil ${i + 1}: geprüftes SKR04-Sachkonto',
        );
        account(
          '${prefix}_vat_account',
          'Anteil ${i + 1}: geprüftes SKR04-Steuerkonto',
        );
        final previous = businessMap(saved[unit['unit_id']]);
        for (final key in [
          'category',
          ..._moneyFields.keys,
          'account',
          'vat_account',
        ])
          if (previous.containsKey(key))
            values['${prefix}_$key'] = previous[key];
      }
      build = (v) => {
        'event_id': event['id'],
        'source_hash': source['source_hash'],
        'euer_date': v['euer_date'],
        'year_rule': rule(v),
        'lines': [
          for (var i = 0; i < units.length; i++)
            {
              'unit_id': units[i]['unit_id'],
              'category': v['u${i}_category'],
              for (final key in _moneyFields.keys)
                key: euerMoney(v['u${i}_$key']),
              'account': _account(v['u${i}_account']),
              'vat_account': _account(v['u${i}_vat_account']),
            },
        ],
      };
    case 'input_vat':
      input(
        'invoice_received_date',
        'Tatsächlicher Rechnungseingang',
        type: BusinessInput.date,
      );
      input(
        'service_date',
        'Leistung ausgeführt am · bei Vorauszahlung leer',
        type: BusinessInput.date,
        required: false,
      );
      toggle(
        'prepayment',
        'Vollständige Vorauszahlung statt bereits ausgeführter Leistung',
      );
      fields.add(
        BusinessField(
          'payment_event_id',
          'Nur Vorauszahlung: belegter vollständiger Zahlungsvorgang',
          type: BusinessInput.choice,
          choices: {
            '': 'Nicht verwendet',
            for (final row in cashSources)
              if (businessMap(businessMap(row['event'])['source'])['kind'] ==
                  'receipt')
                '${businessMap(row['event'])['id']}':
                    '${businessMap(row['event'])['cash_date']} · ${businessMoney(businessMap(row['event'])['amount'])} · ${businessMap(row['event'])['evidence_reference']}',
          },
        ),
      );
      input(
        'entitlement_date',
        'Eintritt aller Vorsteuervoraussetzungen',
        type: BusinessInput.date,
      );
      input(
        'deductible_tax',
        'Ausdrücklich abziehbare Vorsteuer (€)',
        type: BusinessInput.decimal,
        hint:
            'Auch 0,00 muss begründet geprüft werden; ausgewiesen: ${businessMoney(receipt['tax'])}',
      );
      account();
      toggle(
        'conditions_confirmed',
        'Ordnungsgemäße inländische Rechnung, betrieblicher Bezug, Leistung/Zahlung und Vorsteuerrecht geprüft',
      );
      build = (v) => {
        ...receiptBase(),
        'invoice_received_date': v['invoice_received_date'],
        'service_date': v['service_date'],
        'prepayment': v['prepayment'] == true,
        'payment_event_id': v['payment_event_id'],
        'entitlement_date': v['entitlement_date'],
        'deductible_tax': euerMoney(v['deductible_tax']),
        'account': _account(v['account']),
        'conditions_confirmed': v['conditions_confirmed'] == true,
      };
    case 'external_cash':
      choice('account_id', 'Tatsächlich verwendetes Geldkonto', {
        for (final a in accounts.where((a) => a['active'] == true))
          '${a['id']}': '${a['code']} · ${a['name']}',
      });
      input('evidence_key', 'Eindeutige Zahlungsnachweis-ID');
      input(
        'cash_date',
        'Tatsächlicher Geldflusstag',
        type: BusinessInput.date,
      );
      input(
        'amount',
        'Vollständiger belegter Betrag (€)',
        type: BusinessInput.decimal,
      );
      choice('category', 'Steuer-/Kapitalbewegung', {
        for (final key in _externalDirection.keys) key: euerCategories[key]!,
      });
      yearRule(null);
      account();
      build = (v) {
        final selected = accounts
            .where((a) => a['id'] == v['account_id'] && a['active'] == true)
            .firstOrNull;
        if (selected == null)
          throw const FormatException('Aktives Geldkonto wählen.');
        return {
          ...receiptBase(),
          'account_id': selected['id'],
          'account_revision': selected['revision'],
          'evidence_key': _required(v['evidence_key'], 'Zahlungsnachweis'),
          'cash_date': v['cash_date'],
          'amount': euerMoney(v['amount']),
          'direction': _externalDirection[v['category']],
          'category': v['category'],
          'euer_date': v['euer_date'],
          'year_rule': rule(v),
          'account': _account(v['account']),
        };
      };
    case 'asset':
      input('description', 'Bezeichnung des belegten neuen Anlageguts');
      input(
        'business_basis',
        'Geprüfte betriebliche Anschaffungsbasis (€)',
        type: BusinessInput.decimal,
      );
      input(
        'use_start',
        'Tatsächlicher Nutzungsbeginn',
        type: BusinessInput.date,
      );
      input(
        'life_months',
        'Geprüfte lineare Nutzungsdauer in Monaten',
        type: BusinessInput.integer,
        hint: 'Ganze Jahre, 12 bis 1200 Monate; keine automatisch geschätzte Nutzungsdauer.',
      );
      account();
      build = (v) => {
        ...receiptBase(),
        'description': _required(v['description'], 'Anlagenbezeichnung'),
        'business_basis': euerMoney(v['business_basis']),
        'use_start': v['use_start'],
        'life_months': v['life_months'],
        'account': _account(v['account']),
      };
    case 'depreciation':
      input('year', 'AfA-Jahr', type: BusinessInput.integer);
      account();
      build = (v) => {
        'asset_entry_id': initial['asset_entry_id'] ?? source['id'],
        'year': v['year'],
        'account': _account(v['account']),
      };
    case 'reverse':
      build = (v) => {'entry_id': source['id']};
    case 'period':
      input('period', 'Monatsperiode (JJJJ-MM)');
      choice('action', 'Periodenaktion', {
        'close': 'Periode schließen',
        'reopen': 'Periode begründet wieder öffnen',
      });
      toggle(
        'bank_reconciled',
        'Bank- und Kassenbewegungen vollständig abgeglichen',
      );
      toggle(
        'originals_complete',
        'Originalbelege für diese Periode vollständig geprüft',
      );
      toggle(
        'special_cases_reviewed',
        'Sonderfälle und erforderliche Berichtigungen geprüft',
      );
      final attest = businessMap(initial['attestation']);
      values.addAll(attest);
      build = (v) => {
        'period': v['period'],
        'action': v['action'],
        'expected_period_revision': source['revision'] ?? 0,
        'attestation': {
          for (final k in [
            'bank_reconciled',
            'originals_complete',
            'special_cases_reviewed',
          ])
            k: v[k] == true,
        },
      };
    case 'export':
      input('year', 'Auswertungsjahr', type: BusinessInput.integer);
      build = (v) => {'year': v['year']};
    default:
      throw const FormatException(
        'Dieser Buchungsvorgang wird noch nicht unterstützt.',
      );
  }
  input('reason', 'Fachliche Begründung');
  input('evidence_reference', 'Nachweis / Prüfgrundlage');
  return EuerForm(fields, values, build);
}

const _issues = {
  'travel_cash_classification_missing':
      'Belegte Reiseerstattung noch nicht eingeordnet',
  'travel_cash_source_changed':
      'Reisezahlungsnachweis geändert; Einordnung ausdrücklich berichtigen',
  'payroll_cash_classification_missing':
      'Belegte Lohnzahlung noch nicht eingeordnet',
  'payroll_cash_source_changed':
      'Lohnzahlungsnachweis geändert; Einordnung ausdrücklich berichtigen',
  'documentary_components_missing':
      'Belegte Netto-/Steueranteile im Geldflussvorjournal fehlen',
  'external_cash_classification_missing':
      'Sondergeldbewegung nach Gegenbuchung erneut einordnen',
  'cash_classification_missing': 'Geldfluss noch nicht fachlich gebucht',
  'cash_import_missing':
      'Vorhandene Zahlung noch nicht mit dem Geldflussvorjournal verknüpft',
  'original_review_missing': 'Original und Belegangaben noch prüfen',
  'input_vat_decision_missing':
      'Vorsteuerrecht des Originals noch ausdrücklich prüfen',
  'original_review_changed':
      'Belegprüfung geändert; bestehende Buchungen berichtigen',
  'duplicate_original': 'Dasselbe Original ist bereits anderweitig gebunden',
  'asset_register_missing':
      'Anlageanschaffung benötigt das belegte Anlagenverzeichnis',
  'depreciation_missing': 'Lineare Jahres-AfA noch nicht bestätigt',
  'partial_period_profile_coverage': 'Der bestätigte Buchführungsbeginn deckt diesen Zeitraum nicht vollständig ab',
  'profile_incomplete':
      'Profil und tatsächliche Gültigkeits-/Buchführungsdaten fehlen',
  'restore_reconciliation_pending': 'Abgleich nach Wiederherstellung ist offen',
};
String _issue(Object? code) => _issues[code] ?? 'Offener Fachfall: $code';
String _ledgerLabel(Object? code) =>
    const {
      'euer': 'EÜR',
      'vat': 'Umsatzsteuer',
      'asset': 'Anlagevermögen',
      'nondeductible': 'Nicht abziehbarer Aufwand',
      'neutral': 'Neutrale Geldbewegung',
    }[code] ??
    '$code';

class BusinessEuerPage extends StatefulWidget {
  const BusinessEuerPage({super.key, required this.session});
  final BusinessSession session;
  @override
  State<BusinessEuerPage> createState() => _BusinessEuerPageState();
}

class _BusinessEuerPageState extends State<BusinessEuerPage> {
  final year = TextEditingController(text: '${DateTime.now().year}');
  Map<String, dynamic>? state, report, preview, body, catalog;
  List<Map<String, dynamic>> sources = [], journal = [], accounts = [];
  int? nextOffset;
  int epoch = 0;
  Object? generation;
  bool loading = false, busy = false, denied = false, accepted = false;
  String tab = 'sources';
  String? error, message;
  bool get readable => businessEuerReadable(widget.session) && !denied;
  bool get rights => businessEuerWritable(widget.session) && !denied;
  bool get pending => widget.session.pending(euerPendingKey);
  bool get writable =>
      rights &&
      state?['writes_allowed'] == true &&
      !loading &&
      !busy &&
      !pending;
  @override
  void initState() {
    super.initState();
    generation = widget.session.generation;
    widget.session.addListener(changed);
    load();
  }

  @override
  void dispose() {
    epoch++;
    widget.session.removeListener(changed);
    year.dispose();
    super.dispose();
  }

  void changed() {
    if (!mounted) return;
    if (!businessEuerReadable(widget.session) ||
        generation != widget.session.generation) {
      epoch++;
      state = report = catalog = preview = body = null;
      sources = [];
      journal = [];
      accounts = [];
      loading = false;
      accepted = false;
      generation = widget.session.generation;
    } else if (!businessEuerWritable(widget.session)) {
      preview = body = null;
      accepted = false;
    }
    setState(() {});
  }

  void failure(Object e) {
    if (!mounted) return;
    setState(() {
      if (e is ApiException && [401, 403, 404].contains(e.status)) {
        denied = true;
        state = report = catalog = preview = null;
        sources = [];
        journal = [];
        accounts = [];
      }
      error = e is ApiException
          ? e.message
          : e is FormatException
          ? e.message
          : '$e';
    });
  }

  int selectedYear() {
    final value = int.tryParse(year.text);
    if (value == null || value < 1900 || value > 2200)
      throw const FormatException(
        'Kalenderjahr zwischen 1900 und 2200 eingeben.',
      );
    return value;
  }

  Future<void> load({bool refreshRights = false}) async {
    if (refreshRights) {
      await widget.session.load();
      if (!mounted) return;
      denied = false;
    }
    if (!businessEuerReadable(widget.session)) return;
    final current = ++epoch;
    setState(() {
      loading = true;
      error = null;
    });
    try {
      final y = selectedYear();
      final values = await Future.wait([
        widget.session.read(euerPath),
        widget.session.read('$euerPath/sources'),
        widget.session.read('$euerPath/journal?limit=50&offset=0'),
        widget.session.read('$euerPath/report?year=$y'),
        widget.session.read('/accounting/accounts'),
      ]);
      final next = businessMap(values[0]),
          sourcePage = businessMap(values[1]),
          page = businessMap(values[2]),
          yearReport = businessMap(values[3]);
      if (next['revision'] is! int ||
          !RegExp(r'^[a-f0-9]{64}$').hasMatch('${next['state_hash']}') ||
          next['official_tax_return'] != false ||
          next['account_frame'] != 'SKR04' ||
          sourcePage['items'] is! List ||
          page['items'] is! List ||
          yearReport['year'] != y ||
          yearReport['scope'] != 'recorded_sources' ||
          yearReport['official_tax_return'] != false ||
          yearReport['currency'] != 'EUR')
        throw const ApiException(
          0,
          'Der EÜR-Stand konnte nicht eindeutig gelesen werden.',
        );
      for (final row in businessItems(sourcePage)) {
        if (row['kind'] == 'travel_cash') {
          final source = travelCashPublic(row['source']);
          if (source['id'] != row['id'])
            throw const ApiException(
              0,
              'Die Reisezahlungsquelle gehört nicht zum Nachweis.',
            );
        }
        if (row['kind'] == 'payroll_cash') {
          final source = payrollCashPublic(row['source']);
          if (source['id'] != row['id'])
            throw const ApiException(
              0,
              'Die Lohnzahlungsquelle gehört nicht zum Batch.',
            );
        }
      }
      if (!mounted || current != epoch || !readable) return;
      setState(() {
        state = next;
        catalog = sourcePage;
        sources = businessItems(sourcePage);
        journal = businessItems(page);
        nextOffset = page['next_offset'];
        report = yearReport;
        accounts = businessItems(values[4]);
      });
    } catch (e) {
      if (mounted && current == epoch) failure(e);
    } finally {
      if (mounted && current == epoch) setState(() => loading = false);
    }
  }

  Future<Map<String, dynamic>> fresh({bool write = false}) async {
    await widget.session.load();
    if (!mounted || !readable || widget.session.error != null)
      throw const ApiException(
        403,
        'Die aktuellen globalen Rechte sind nicht bestätigt.',
      );
    final next = businessMap(await widget.session.read(euerPath));
    if (write && (!rights || next['writes_allowed'] != true))
      throw const ApiException(
        423,
        'Neue Buchungen sind durch Rechte, Finanzbetrieb oder Wiederherstellungsabgleich gesperrt.',
      );
    return next;
  }

  Future<void> moreJournal() async {
    if (!readable || nextOffset == null || loading) return;
    final current = epoch;
    setState(() => loading = true);
    try {
      final page = businessMap(
        await widget.session.read(
          '$euerPath/journal?limit=50&offset=$nextOffset',
        ),
      );
      if (mounted && current == epoch && readable)
        setState(() {
          journal.addAll(businessItems(page));
          nextOffset = page['next_offset'];
        });
    } catch (e) {
      if (mounted && current == epoch) failure(e);
    } finally {
      if (mounted && current == epoch) setState(() => loading = false);
    }
  }

  Future<void> profile() async {
    await Navigator.push<void>(
      context,
      MaterialPageRoute(
        builder: (_) => BusinessPreparationProfilePage(session: widget.session),
      ),
    );
    if (mounted) await load(refreshRights: true);
  }

  Future<void> upstream([Map<String, dynamic>? row]) async {
    try {
      await fresh();
      if (!mounted) return;
      final source = businessMap(row?['source']), kind = row?['kind'];
      if (kind == 'payroll_cash' || kind == 'travel_cash') {
        final proof = (kind == 'travel_cash' ? travelCashPublic : payrollCashPublic)(
          await widget.session.read(
            kind == 'travel_cash'
                ? '/personnel/travel/financial/${row!['id']}?revision=${source['revision']}'
                : '/payroll/cash/financial/${row!['id']}?revision=${source['revision']}',
          ),
        );
        if (!euerSame(source, proof))
          throw const ApiException(
            0,
            'Der gespeicherte Lohnzahlungsnachweis wurde verändert.',
          );
        if (!mounted || !readable) return;
        final opening = widget.session.generation;
        await showDialog<void>(
          context: context,
          builder: (_) => AnimatedBuilder(
            animation: widget.session,
            builder: (context, _) =>
                !readable || widget.session.generation != opening
                ? const AlertDialog(
                    title: Text('Zugang geändert'),
                    content: Notice(
                      'Finanznachweise sind nicht mehr freigegeben.',
                      error: true,
                    ),
                  )
                : AlertDialog(
                    title: Text(
                      kind == 'travel_cash'
                          ? 'Öffentlicher Reisezahlungsnachweis'
                          : 'Öffentlicher Lohnzahlungsnachweis',
                    ),
                    content: SizedBox(
                      width: 600,
                      child: SingleChildScrollView(child: payrollFacts(proof)),
                    ),
                    actions: [
                      TextButton(
                        onPressed: () => Navigator.pop(context),
                        child: const Text('Schließen'),
                      ),
                    ],
                  ),
          ),
        );
      } else if (kind == 'receipt' || kind == 'receipt_review') {
        final record = businessMap(
          await widget.session.read('/finance/receipts/${row!['id']}'),
        );
        if (!mounted || !readable) return;
        final child = widget.session.sharedProjectSession(record['project_id']);
        await child.load();
        if (!mounted || !readable) return;
        await Navigator.push<void>(
          context,
          MaterialPageRoute(
            builder: (_) => BusinessProjectReceiptsPage(
              session: child,
              initialReceiptId: row['id'],
            ),
          ),
        );
      } else {
        await Navigator.push<void>(
          context,
          MaterialPageRoute(
            builder: (_) => BusinessAccountingPage(
              session: widget.session,
              initialTab: kind == 'payment_import' ? 'payments' : 'events',
              initialEventId: source['event']?['id'],
            ),
          ),
        );
      }
      if (mounted) await load(refreshRights: true);
    } catch (e) {
      failure(e);
    }
  }

  Future<void> captureReceipt() async {
    if (!rights) return;
    await showDialog<void>(
      context: context,
      builder: (_) => BusinessEditor(
        session: widget.session,
        title: 'Projekt für Eingangsbeleg',
        readPermission: 'finance.read',
        writePermission: 'finance.write',
        fields: [
          BusinessField(
            'project',
            'Projekt',
            type: BusinessInput.choice,
            required: true,
            choices: {
              '': 'Projekt auswählen',
              for (final p in widget.session.projects)
                '${p['id']}': '${p['name']}',
            },
          ),
        ],
        onSave: (values) async {
          final child = widget.session.sharedProjectSession(values['project']);
          await child.load();
          if (!mounted || !readable) return;
          // Close only this selector before the receipt page owns its own navigation.
          Navigator.pop(context);
          await Navigator.push<void>(
            context,
            MaterialPageRoute(
              builder: (_) => BusinessProjectReceiptsPage(session: child),
            ),
          );
          if (mounted) await load(refreshRights: true);
        },
        saveLabel: 'Belegaufnahme öffnen',
      ),
    );
  }

  Map<String, dynamic> currentSource(Map<String, dynamic> entry) {
    final effect = businessMap(entry['effect']),
        source = businessMap(effect['source']);
    final id =
        source['event']?['id'] ??
        source['receipt']?['receipt_id'] ??
        source['id'];
    return businessMap(
      sources.where((r) => r['id'] == id).firstOrNull?['source'] ?? source,
    );
  }

  Future<void> edit(
    String operation,
    Map<String, dynamic> source, {
    Map<String, dynamic>? correction,
    Map<String, dynamic> initial = const {},
  }) async {
    if (!writable) return;
    final openingGeneration = widget.session.generation;
    final effect = businessMap(correction?['effect']);
    final initialValues = {...businessMap(effect['payload']), ...initial};
    final spec = euerForm(
      operation,
      source,
      initial: initialValues,
      accounts: accounts,
      cashSources: sources
          .where((s) => s['kind'] == 'cash')
          .map((s) => businessMap(s['source']))
          .toList(),
    );
    await showDialog<void>(
      context: context,
      builder: (_) => BusinessEditor(
        session: widget.session,
        title: correction == null
            ? euerOperations[operation]!
            : '${euerOperations[operation]} berichtigen',
        readPermission: 'accounting.read',
        writePermission: 'accounting.prepare',
        readAllowed: () =>
            readable && openingGeneration == widget.session.generation,
        fields: spec.fields,
        initial: spec.initial,
        saveLabel: 'Buchung unverbindlich prüfen',
        onSave: (values) async {
          if (pending)
            throw const ApiException(
              409,
              'Zuerst die offene Buchungsbestätigung unverändert klären.',
            );
          final next = await fresh(write: true);
          if (openingGeneration != widget.session.generation)
            throw const ApiException(
              409,
              'Datenstand geändert. Quellen neu laden und erneut prüfen.',
            );
          final payload = spec.payload(values);
          if (operation == 'period')
            payload['expected_period_revision'] =
                businessItems(next['periods'])
                    .where((p) => p['period'] == payload['period'])
                    .firstOrNull?['revision'] ??
                0;
          final input = <String, dynamic>{
            'operation': correction == null ? operation : 'correct',
            'expected_revision': next['revision'],
            'state_hash': next['state_hash'],
            'payload': correction == null
                ? payload
                : {
                    'entry_id': correction['id'],
                    'operation': operation,
                    'payload': payload,
                  },
            'reason': _required(values['reason'], 'Fachliche Begründung'),
            'evidence_reference': _required(
              values['evidence_reference'],
              'Nachweis',
            ),
          };
          final result = euerPreview(
            businessMap(
              await widget.session.api.call(
                widget.session.path('$euerPath/preview'),
                input,
              ),
            ),
            input,
          );
          if (!mounted ||
              !readable ||
              openingGeneration != widget.session.generation)
            return;
          setState(() {
            state = next;
            preview = result;
            body = {
              ...input,
              'preview_hash': result['preview_hash'],
              'confirmation': true,
            };
            accepted = false;
            error = message = null;
          });
        },
      ),
    );
  }

  Future<void> confirm() async {
    if (busy ||
        !rights ||
        (!pending && (!accepted || preview == null || body == null)))
      return;
    setState(() {
      busy = true;
      error = null;
    });
    try {
      if (!pending) {
        await fresh(write: true);
        if (preview == null || body == null)
          throw const ApiException(
            409,
            'Datenstand oder Rechte geändert. Quellen neu laden und eine neue Vorschau prüfen.',
          );
      }
      final value = pending
          ? await widget.session.repeatAccountingEuerCommand()
          : await widget.session.command(
              euerPendingKey,
              '$euerPath/confirm',
              body!,
              validateResult: euerReceiptValidator(body!, preview!),
            );
      if (!mounted || !readable) return;
      setState(() {
        preview = body = null;
        accepted = false;
        message =
            'Buchung ${businessMap(value)['sequence']} ist unveränderlich im Journal gespeichert.';
      });
      await load();
    } catch (e) {
      if (mounted) failure(e);
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  Future<void> exportFile(Map<String, dynamic> entry, bool csv) async {
    try {
      await fresh();
      final capturedGeneration = widget.session.generation;
      final value = businessMap(
        await widget.session.read('$euerPath/exports/${entry['id']}'),
      );
      final attachment = await euerExportAttachment(value, entry, csv: csv);
      if (!mounted ||
          !readable ||
          capturedGeneration != widget.session.generation)
        return;
      await exportMailAttachment(
        context,
        attachment,
        () => readable && capturedGeneration == widget.session.generation,
      );
    } catch (e) {
      failure(e);
    }
  }

  Widget postingList(dynamic data) => Column(
    children: [
      for (final row in businessItems(data))
        ListTile(
          isThreeLine: true,
          title: Text(
            '${_ledgerLabel(row['ledger'])} · ${euerCategories[row['category']] ?? row['category']}',
          ),
          subtitle: Text(
            '${businessDate(row['date'])} · SKR04 ${row['account']}\n${businessMoney(row['amount'])}',
          ),
          dense: true,
        ),
    ],
  );
  Widget payrollFacts(Map<String, dynamic> source) {
    (source['kind'] == 'travel_cash' ? travelCashPublic : payrollCashPublic)(
      source,
    );
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      mainAxisSize: MainAxisSize.min,
      children: [
        Notice(
          source['status'] == 'void'
              ? 'Nachweisaufhebung ohne tatsächliche Rückzahlung. Vorherige Einordnung ausdrücklich berichtigen.'
              : 'Nur belegte tatsächliche Zahlungen. Private Beschäftigten- und Originaldaten bleiben im Personalbereich.',
        ),
        for (final m in source['cash_movements'])
          ListTile(
            title: Text(
              '${businessDate(m['date'])} · ${m['direction'] == 'in' ? 'Zufluss / Arbeitnehmerzahlung' : 'Abfluss'} ${businessMoney(m['amount'])}',
            ),
            subtitle: Text(
              '${m['account']['code']} · ${m['account']['name']}\n${businessMap(m['categories']).entries.map((e) => '${({...payrollCashCategories, ...travelCashCategories})[e.key]}: ${businessMoney(e.value)}').join('\n')}',
            ),
          ),
      ],
    );
  }

  Widget sourceCard(Map<String, dynamic> row) {
    final source = businessMap(row['source']),
        event = businessMap(source['event']),
        receipt = businessMap(source['receipt']);
    final current = businessMap(row['current']);
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              row['kind'] == 'travel_cash'
                  ? 'Belegte Reiseerstattung · Fassung ${source['revision']}'
                  : row['kind'] == 'payroll_cash'
                  ? 'Belegte Lohnzahlungen · Fassung ${source['revision']}'
                  : row['kind'] == 'cash'
                  ? '${event['direction'] == 'in' ? 'Zufluss' : 'Abfluss'} · ${businessMoney(event['amount'])}'
                  : '${receipt['vendor'] ?? (row['kind'] == 'payment_import' ? 'Vorhandene Zahlung' : 'Eingangsoriginal')} · ${receipt['invoice_number'] ?? ''}',
              style: Theme.of(context).textTheme.titleMedium,
            ),
            Text(
              '${businessDate(row['date'])} · ${event['evidence_reference'] ?? receipt['filename'] ?? row['id']}',
            ),
            if (row['kind'] == 'payroll_cash' || row['kind'] == 'travel_cash')
              payrollFacts(source),
            if (row['kind'] == 'receipt')
              Text(
                'Belegt: ${businessMoney(receipt['net'])} netto · ${businessMoney(receipt['tax'])} Steuer · ${businessMoney(receipt['gross'])} brutto',
              ),
            for (final unit in businessItems(source['units'] ?? []))
              Text(
                'Beleganteil ${unit['version']}: ${businessMoney(unit['net'])} netto + ${businessMoney(unit['tax'])} Steuer = ${businessMoney(unit['gross'])}',
              ),
            for (final reason in row['reasons'] ?? []) Text(_issue(reason)),
            if (current.isNotEmpty)
              Text(
                'Aktuelle Buchung: ${current['sequence']} · ${current['reason']}',
              ),
            Wrap(
              spacing: 8,
              runSpacing: 8,
              children: [
                TextButton(
                  onPressed: () => upstream(row),
                  child: Text(
                    row['kind'] == 'payroll_cash' ||
                            row['kind'] == 'travel_cash'
                        ? 'Öffentlichen Zahlungsnachweis ansehen'
                        : row['kind'] == 'receipt' ||
                              row['kind'] == 'receipt_review'
                        ? 'Original / Belegprüfung'
                        : 'Geldfluss / Beleganteile',
                  ),
                ),
                if (row['kind'] == 'travel_cash' &&
                    (source['status'] == 'active' || current.isNotEmpty))
                  FilledButton(
                    onPressed: writable
                        ? () => edit(
                            'travel_cash',
                            source,
                            correction: current.isEmpty ? null : current,
                          )
                        : null,
                    child: Text(
                      current.isEmpty
                          ? 'Belegte Reiseerstattung einordnen'
                          : 'Reisezahlungseinordnung berichtigen',
                    ),
                  ),
                if (row['kind'] == 'payroll_cash' &&
                    (source['status'] == 'active' || current.isNotEmpty))
                  FilledButton(
                    onPressed: writable
                        ? () => edit(
                            'payroll_cash',
                            source,
                            correction: current.isEmpty ? null : current,
                          )
                        : null,
                    child: Text(
                      current.isEmpty
                          ? 'Belegte Lohnzahlungen einordnen'
                          : 'Lohnzahlungseinordnung berichtigen',
                    ),
                  ),
                if (row['kind'] == 'cash' && current.isEmpty)
                  FilledButton(
                    onPressed: writable ? () => edit('cash', source) : null,
                    child: const Text('Geldfluss einordnen'),
                  ),
                if (row['kind'] == 'receipt') ...[
                  if (row['source_role'] != 'payment_evidence')
                    OutlinedButton(
                      onPressed: writable
                          ? () => edit(
                              'input_vat',
                              source,
                              correction: current.isEmpty ? null : current,
                            )
                          : null,
                      child: Text(
                        current.isEmpty
                            ? 'Vorsteuerrecht prüfen'
                            : 'Vorsteuerprüfung berichtigen',
                      ),
                    ),
                  OutlinedButton(
                    onPressed: writable
                        ? () => edit(
                            'external_cash',
                            source,
                            correction: row['external_cash'],
                          )
                        : null,
                    child: const Text('Steuer-/Kapitalbewegung'),
                  ),
                  if (row['source_role'] != 'payment_evidence')
                    OutlinedButton(
                      onPressed: writable
                          ? () =>
                                edit('asset', source, correction: row['asset'])
                          : null,
                      child: const Text('Anlagegut'),
                    ),
                ],
                if (row['kind'] == 'cash' && current.isNotEmpty)
                  OutlinedButton(
                    onPressed: writable
                        ? () => edit('cash', source, correction: current)
                        : null,
                    child: const Text('Einordnung berichtigen'),
                  ),
              ],
            ),
          ],
        ),
      ),
    );
  }

  Widget journalCard(Map<String, dynamic> entry) {
    final effect = businessMap(entry['effect']);
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              'Nr. ${entry['sequence']} · ${euerOperations[entry['operation']] ?? entry['operation']}',
              style: Theme.of(context).textTheme.titleMedium,
            ),
            Text(
              '${businessDate(entry['created_at'], time: true)} · ${entry['reason']}',
            ),
            Text('Prüfgrundlage: ${entry['evidence_reference']}'),
            if (entry['reverses'] != null)
              SelectableText('Gegenbuchung zu ${entry['reverses']}'),
            postingList(entry['postings']),
            ExpansionTile(
              title: const Text('Geprüfte Angaben und Herkunft'),
              children: [
                _EuerFacts(value: entry['payload']),
                if (effect.isNotEmpty) _EuerFacts(value: effect['source']),
                SelectableText('Nachweis: ${entry['entry_hash']}'),
              ],
            ),
            Wrap(
              spacing: 8,
              runSpacing: 8,
              children: [
                if (effect.isNotEmpty) ...[
                  OutlinedButton(
                    onPressed: writable
                        ? () => edit(
                            effect['operation'],
                            currentSource(entry),
                            correction: entry,
                          )
                        : null,
                    child: const Text('Geprüft berichtigen'),
                  ),
                  OutlinedButton(
                    onPressed: writable ? () => edit('reverse', entry) : null,
                    child: const Text('Genau gegenbuchen'),
                  ),
                  if (effect['operation'] == 'asset')
                    OutlinedButton(
                      onPressed: writable
                          ? () => edit(
                              'depreciation',
                              entry,
                              initial: {'year': selectedYear()},
                            )
                          : null,
                      child: const Text('Jahres-AfA prüfen'),
                    ),
                ],
                if (entry['operation'] == 'export') ...[
                  OutlinedButton(
                    onPressed: () => exportFile(entry, false),
                    child: const Text('Prüfpaket JSON speichern'),
                  ),
                  OutlinedButton(
                    onPressed: () => exportFile(entry, true),
                    child: const Text('Buchungsliste CSV speichern'),
                  ),
                ],
              ],
            ),
          ],
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final waiting = widget.session.pendingCommandValues(
      euerPendingKey,
      path: '$euerPath/confirm',
    );
    return Scaffold(
      appBar: AppBar(
        title: const Text('Eigene EÜR und Umsatzsteuer'),
        actions: [
          IconButton(
            tooltip: 'Rechte und Daten aktualisieren',
            onPressed: loading || busy ? null : () => load(refreshRights: true),
            icon: const Icon(Icons.refresh),
          ),
        ],
      ),
      body: !readable
          ? const Padding(
              padding: EdgeInsets.all(24),
              child: BusinessEmpty(
                'EÜR nicht freigegeben',
                'Aktuelle globale Finanz- und Buchführungsrechte sowie das EÜR-Modul sind erforderlich. Unbestätigte Aufträge bleiben in dieser Sitzung erhalten.',
              ),
            )
          : ListView(
              padding: const EdgeInsets.all(24),
              children: [
                const Notice(
                  'EÜR und Umsatzsteuer werden getrennt aus ausdrücklich geprüften Quellen gebucht. Eigene Jahresauswertung und Beraterprüfpaket; keine amtliche Erklärung und keine Übermittlung.',
                ),
                if (error != null) Notice(error!, error: true),
                if (message != null) Notice(message!),
                if (loading || busy) const LinearProgressIndicator(),
                Wrap(
                  spacing: 8,
                  runSpacing: 8,
                  children: [
                    OutlinedButton(
                      onPressed: profile,
                      child: const Text('Unternehmensprofil und Gültigkeit'),
                    ),
                    OutlinedButton(
                      onPressed: () => upstream(),
                      child: const Text('Geldflüsse vorbereiten'),
                    ),
                    OutlinedButton(
                      onPressed: rights ? captureReceipt : null,
                      child: const Text('Eingangsbeleg erfassen'),
                    ),
                  ],
                ),
                if (state != null) ...[
                  Text(
                    'Journalstand ${state!['revision']} · SKR04 · ${state!['profile_ready'] == true ? 'Profil mit bestätigter Gültigkeit' : 'Profil oder tatsächliche Startdaten fehlen'}',
                  ),
                  if (state!['profile_ready'] != true)
                    const Notice(
                      'Vor wirtschaftlichen Buchungen das Einzelunternehmen/EÜR-Profil mit Regelbesteuerung und Ist-Versteuerung sowie tatsächlichem Gültigkeits- und Buchführungsbeginn bestätigen. Es werden keine historischen Daten vorgegeben.',
                    ),
                  if (state!['writes_allowed'] != true)
                    const Notice(
                      'Gespeicherte Nachweise sind lesbar. Neue Buchungen benötigen die Freigabe des Finanzbetriebs und gegebenenfalls den Wiederherstellungsabgleich.',
                    ),
                ],
                if (pending)
                  Card(
                    child: Padding(
                      padding: const EdgeInsets.all(16),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          const Text(
                            'Buchungsantwort offen',
                            style: TextStyle(fontWeight: FontWeight.bold),
                          ),
                          Text(
                            euerOperations[waiting?['operation']] ??
                                'Begonnener Buchungsvorgang',
                          ),
                          const Text(
                            'Die Antwort kann nach der Speicherung verloren gegangen sein. Nur der ursprüngliche Auftrag wird erneut gesendet.',
                          ),
                          _EuerFacts(value: waiting?['payload']),
                          FilledButton(
                            onPressed: rights && !busy ? confirm : null,
                            child: const Text(
                              'Ursprünglichen Auftrag erneut senden',
                            ),
                          ),
                        ],
                      ),
                    ),
                  ),
                if (preview != null && !pending)
                  Card(
                    child: Padding(
                      padding: const EdgeInsets.all(16),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            'Geprüfte Buchungsvorschau',
                            style: Theme.of(context).textTheme.titleLarge,
                          ),
                          Text(euerOperations[preview!['operation']] ?? ''),
                          Text('${preview!['reason']}'),
                          Text(
                            'Prüfgrundlage: ${preview!['evidence_reference']}',
                          ),
                          _EuerFacts(value: preview!['payload']),
                          postingList(preview!['postings']),
                          if (preview!['postings'].isEmpty)
                            const Text(
                              'Dieser Schritt hat keine unmittelbare Einnahmen-/Ausgabenbuchung.',
                            ),
                          CheckboxListTile(
                            value: accepted,
                            onChanged: rights && !busy
                                ? (v) => setState(() => accepted = v == true)
                                : null,
                            title: const Text(
                              'Ich habe Quelle, fachliche Einordnung, Beträge, Zeitraum und Konten geprüft und bestätige diesen Vorgang.',
                            ),
                          ),
                          Wrap(
                            spacing: 8,
                            children: [
                              FilledButton(
                                onPressed: rights && accepted && !busy
                                    ? confirm
                                    : null,
                                child: const Text(
                                  'Buchung verbindlich festhalten',
                                ),
                              ),
                              TextButton(
                                onPressed: busy
                                    ? null
                                    : () => setState(() {
                                        preview = body = null;
                                        accepted = false;
                                      }),
                                child: const Text('Vorschau verwerfen'),
                              ),
                            ],
                          ),
                        ],
                      ),
                    ),
                  ),
                const SizedBox(height: 16),
                Wrap(
                  spacing: 8,
                  children: [
                    for (final entry in const {
                      'sources': 'Quellen und Prüfung',
                      'journal': 'Buchungen und Korrekturen',
                      'report': 'Jahr und Perioden',
                    }.entries)
                      ChoiceChip(
                        label: Text(entry.value),
                        selected: tab == entry.key,
                        onSelected: (_) => setState(() => tab = entry.key),
                      ),
                  ],
                ),
                if (tab == 'sources') ...[
                  for (final row in sources) sourceCard(row),
                  if (sources.isEmpty && !loading)
                    const BusinessEmpty(
                      'Noch keine Quellen',
                      'Geldflüsse verknüpfen oder Originalbelege aufnehmen und prüfen.',
                    ),
                  for (final a in businessItems(
                    catalog?['account_movements'] ?? [],
                  ))
                    ListTile(
                      title: Text(
                        '${a['account']?['code']} · ${a['account']?['name']}',
                      ),
                      subtitle: Text(
                        'Zufluss ${businessMoney(a['inflows'])} · Abfluss ${businessMoney(a['outflows'])} · Bewegungssaldo ${businessMoney(a['movement_net'])}\nAnfangs- und Endbestand nicht festgestellt.',
                      ),
                    ),
                ],
                if (tab == 'journal') ...[
                  const Text(
                    'Berichtigung und Gegenbuchung sind nur für aktuell wirksame Einträge und offene Zeiträume möglich. Abhängige Einträge zuerst berichtigen.',
                  ),
                  for (final entry in journal) journalCard(entry),
                  if (nextOffset != null)
                    OutlinedButton(
                      onPressed: loading ? null : moreJournal,
                      child: const Text('Weitere Journalfassungen'),
                    ),
                ],
                if (tab == 'report') ...[
                  TextField(
                    controller: year,
                    keyboardType: TextInputType.number,
                    decoration: const InputDecoration(
                      labelText: 'Auswertungsjahr',
                    ),
                  ),
                  OutlinedButton(
                    onPressed: loading ? null : () => load(),
                    child: const Text('Jahresauswertung laden'),
                  ),
                  if (report != null) ...[
                    Text(
                      'Jahr ${report!['year']} · nur erfasste Quellen',
                      style: Theme.of(context).textTheme.titleLarge,
                    ),
                    if (report!['coverage_start'] != null)
                      Text(
                        'Bestätigter Buchführungsbeginn: ${businessDate(report!['coverage_start'])}',
                      ),
                    for (final field in const {
                      'confirmed_income': 'Bestätigte Einnahmen',
                      'confirmed_expenses': 'Bestätigte Ausgaben',
                      'confirmed_surplus':
                          'Zwischenergebnis bestätigter Buchungen',
                      'euer_surplus': 'Ergebnis bei vollständiger Einordnung erfasster Quellen',
                      'confirmed_output_vat': 'Bestätigte Ist-Umsatzsteuer',
                      'confirmed_input_vat': 'Bestätigtes Vorsteuerrecht',
                      'vat_balance':
                          'USt-Saldo bei vollständig eingeordneten Quellen',
                    }.entries)
                      ListTile(
                        title: Text(field.value),
                        subtitle: Text(
                          businessMoney(report!['totals']?[field.key]),
                        ),
                      ),
                    ExpansionTile(
                      title: const Text('Jahreswerte nach Einordnung'),
                      children: [
                        for (final category in businessItems(
                          report!['categories'] ?? [],
                        ))
                          ListTile(
                            title: Text(
                              '${_ledgerLabel(category['ledger'])} · ${euerCategories[category['category']] ?? category['category']}',
                            ),
                            subtitle: Text(businessMoney(category['amount'])),
                          ),
                      ],
                    ),
                    ExpansionTile(
                      title: const Text('Gebuchte Einzelposten des Jahres'),
                      children: [postingList(report!['postings'] ?? [])],
                    ),
                    if (report!['complete_for_recorded_sources'] != true)
                      const Notice(
                        'Offene Quellen begrenzen das Ergebnis. Ein fehlendes Gesamtergebnis ist nicht null; bestätigte Zwischensummen sind kein vollständiges Unternehmensjahr.',
                      ),
                    for (final issue in businessItems(report!['issues']))
                      ListTile(
                        title: Text(_issue(issue['code'])),
                        subtitle: Text(businessDate(issue['date'])),
                        onTap: () => upstream(
                          sources
                              .where((s) => s['id'] == issue['source_id'])
                              .firstOrNull,
                        ),
                      ),
                    for (final period in businessItems(report!['periods']))
                      ListTile(
                        title: Text(
                          '${period['period']} · ${period['status'] == 'closed' ? 'Gesperrt' : 'Offen'}',
                        ),
                        subtitle: Text('Fassung ${period['revision']}'),
                        trailing: TextButton(
                          onPressed: writable
                              ? () => edit(
                                  'period',
                                  period,
                                  initial: {
                                    'period': period['period'],
                                    'action': period['status'] == 'closed'
                                        ? 'reopen'
                                        : 'close',
                                  },
                                )
                              : null,
                          child: const Text('Prüfen'),
                        ),
                      ),
                    for (final asset in businessItems(report!['assets']))
                      ListTile(
                        title: Text('${asset['description']}'),
                        subtitle: Text(
                          'Basis ${businessMoney(asset['basis'])} · ${asset['life_months']} Monate · ${asset['depreciation'] == null ? 'AfA offen' : 'AfA bestätigt'}',
                        ),
                        trailing: TextButton(
                          onPressed: writable
                              ? () => edit(
                                  'depreciation',
                                  {'id': asset['entry_id']},
                                  initial: {'year': report!['year']},
                                )
                              : null,
                          child: const Text('AfA prüfen'),
                        ),
                      ),
                  ],
                  Wrap(
                    spacing: 8,
                    runSpacing: 8,
                    children: [
                      OutlinedButton(
                        onPressed: writable ? () => edit('period', {}) : null,
                        child: const Text('Monatsperiode prüfen'),
                      ),
                      FilledButton(
                        onPressed: writable
                            ? () => edit(
                                'export',
                                {},
                                initial: {'year': selectedYear()},
                              )
                            : null,
                        child: const Text('Jahresprüfpaket vorbereiten'),
                      ),
                    ],
                  ),
                  const Notice(
                    'Prüfpakete frieren ihren Journalstand samt offenen Fällen ein. Spätere Buchungen ändern eine frühere Ausgabe nicht. Gespeicherte JSON-/CSV-Dateien sind im Journal verfügbar.',
                  ),
                ],
              ],
            ),
    );
  }
}

const _fieldLabels = {
  'operation': 'Vorgang',
  'entry_id': 'Ursprungsbuchung',
  'event_id': 'Geldflussnachweis',
  'receipt_id': 'Originalbeleg',
  'source_hash': 'Quellenprüfsumme',
  'euer_date': 'EÜR-Datum',
  'year_rule': 'Jahreszuordnung',
  'kind': 'Art',
  'cash': 'Geldflusstag',
  'ten_day': 'Zehn-Tage-Regel',
  'due_date': 'Fälligkeit',
  'economic_year': 'Wirtschaftliches Jahr',
  'recurring': 'Wiederkehrend',
  'unit_id': 'Dokumentarischer Anteil',
  'lines': 'Beleganteile',
  'category': 'Einordnung',
  'account': 'SKR04-Sachkonto',
  'vat_account': 'SKR04-Steuerkonto',
  'invoice_received_date': 'Rechnungseingang',
  'service_date': 'Leistungstag',
  'prepayment': 'Vorauszahlung',
  'payment_event_id': 'Zahlungsnachweis',
  'entitlement_date': 'Vorsteuerberechtigung ab',
  'deductible_tax': 'Abziehbare Vorsteuer',
  'conditions_confirmed': 'Voraussetzungen geprüft',
  'account_id': 'Geldkonto',
  'account_revision': 'Kontofassung',
  'evidence_key': 'Zahlungsnachweis-ID',
  'cash_date': 'Geldflusstag',
  'amount': 'Betrag',
  'direction': 'Richtung',
  'description': 'Anlagegut',
  'business_basis': 'Betriebliche Basis',
  'use_start': 'Nutzungsbeginn',
  'life_months': 'Nutzungsmonate',
  'asset_entry_id': 'Anlagenbuchung',
  'year': 'Jahr',
  'period': 'Monatsperiode',
  'action': 'Aktion',
  'expected_period_revision': 'Bisherige Periodenfassung',
  'attestation': 'Prüfaussagen',
  'bank_reconciled': 'Kontenabgleich',
  'originals_complete': 'Originalvollständigkeit',
  'special_cases_reviewed': 'Sonderfälle geprüft',
};

class _EuerFacts extends StatelessWidget {
  const _EuerFacts({required this.value});
  final dynamic value;
  @override
  Widget build(BuildContext context) {
    if (value is Map)
      return Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          for (final e in (value as Map).entries)
            Padding(
              padding: const EdgeInsets.only(top: 4),
              child: e.value is Map || e.value is List
                  ? ExpansionTile(
                      title: Text(
                        _fieldLabels[e.key] ??
                            _moneyFields[e.key] ??
                            '${e.key}',
                      ),
                      children: [_EuerFacts(value: e.value)],
                    )
                  : SelectableText(
                      '${_fieldLabels[e.key] ?? _moneyFields[e.key] ?? e.key}: ${e.value == null
                          ? 'Nicht angegeben'
                          : e.value == true
                          ? 'Ja'
                          : e.value == false
                          ? 'Nein'
                          : euerCategories[e.value] ?? e.value}',
                    ),
            ),
        ],
      );
    if (value is List)
      return Column(
        children: [
          for (final row in value)
            Padding(
              padding: const EdgeInsets.all(8),
              child: _EuerFacts(value: row),
            ),
        ],
      );
    return Text('${value ?? 'Keine Angaben'}');
  }
}

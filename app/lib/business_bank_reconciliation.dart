import 'dart:convert';
import 'dart:typed_data';

import 'package:cryptography/cryptography.dart';
import 'package:file_selector/file_selector.dart';
import 'package:flutter/material.dart';

import 'api.dart';
import 'business_session.dart';
import 'business_qonto_readonly.dart';
import 'business_travel_cash.dart';
import 'business_widgets.dart';
import 'design.dart';
import 'mail_attachment_widgets.dart';
import 'offline_vault.dart' show offlineId;

final _id = RegExp(r'^[a-f0-9]{32}$'), _hash = RegExp(r'^[a-f0-9]{64}$');
Never _fail(String message, [int status = 0]) =>
    throw ApiException(status, message);
Map<String, dynamic> _copy(dynamic value) =>
    businessMap(jsonDecode(jsonEncode(value)));
dynamic _ordered(dynamic value) => value is List
    ? value.map(_ordered).toList()
    : value is Map
    ? {
        for (final key in value.keys.map((v) => '$v').toList()..sort())
          key: _ordered(value[key]),
      }
    : value;
bool bankSame(dynamic a, dynamic b) =>
    jsonEncode(_ordered(a)) == jsonEncode(_ordered(b));
String bankMoney(dynamic raw, {bool signed = false, bool positive = false}) {
  final text = '${raw ?? ''}'.trim().replaceAll(',', '.');
  if (!RegExp(
    signed ? r'^-?\d{1,13}(?:\.\d{1,2})?$' : r'^\d{1,13}(?:\.\d{1,2})?$',
  ).hasMatch(text))
    _fail(
      'Einen genauen EUR-Betrag mit höchstens zwei Nachkommastellen angeben.',
    );
  final parts = text.replaceAll('-', '').split('.'),
      value =
          BigInt.parse(parts[0]) * BigInt.from(100) +
          BigInt.parse((parts.length > 1 ? parts[1] : '').padRight(2, '0'));
  if (positive && value == BigInt.zero)
    _fail('Ein positiver tatsächlicher Teilbetrag ist erforderlich.');
  return '${text.startsWith('-') && value != BigInt.zero ? '-' : ''}${value ~/ BigInt.from(100)}.${(value % BigInt.from(100)).toString().padLeft(2, '0')}';
}

bool bankReadable(BusinessSession s) =>
    s.hasFeature('bank_reconciliation') &&
    s.hasModule('bank_reconciliation') &&
    ['bank.read', 'accounting.read', 'finance.read'].every(s.can);
bool bankWritable(BusinessSession s) =>
    bankReadable(s) &&
    !s.readonly &&
    s.sectionEnabled('finance') &&
    ['bank.prepare', 'accounting.prepare', 'finance.write'].every(s.can);
bool bankAdministrative(BusinessSession s) =>
    bankWritable(s) && ['bank.admin', 'accounting.admin'].every(s.can);
Map<String, dynamic> bankEvent(dynamic raw) {
  final value = businessMap(raw);
  if (value['payload'] is! Map ||
      !_hash.hasMatch('${value['content_hash']}') ||
      !_id.hasMatch('${value['created_by']}') ||
      value['created_at'] is! String)
    _fail('Der gespeicherte Banknachweis ist unvollständig.');
  _checkTravelSources(businessMap(value['payload']));
  return value;
}

Map<String, dynamic> bankImportPreview(
  dynamic raw,
  Map<String, dynamic> body,
  String sha256,
) {
  final value = businessMap(raw), meta = businessMap(value['metadata']);
  if (!_hash.hasMatch('${value['preview_hash']}') ||
      [
        'errors',
        'duplicates',
        'identity_checks',
      ].any((k) => value[k] is! List) ||
      value['can_import'] is! bool ||
      meta['rows'] is! List ||
      meta['account']?['id'] != body['account_id'] ||
      meta['account']?['revision'] != body['account_revision'] ||
      meta['bank']?['revision'] != body['bank_revision'] ||
      meta['file_sha256'] != sha256 ||
      [
        'statement_reference',
        'period_from',
        'period_to',
        'opening_balance',
        'closing_balance',
        'filename',
        'delimiter',
        'complete_statement_confirmed',
      ].any((k) => meta[k] != body[k]) ||
      !bankSame(
        meta['distinct_transaction_confirmations'],
        body['distinct_transaction_confirmations'] ?? {},
      ))
    _fail(
      'Die Importvorschau bestätigt nicht das gewählte Original und seine Angaben.',
    );
  return value;
}

String _bankIssue(String code) =>
    const {
      'statement_coverage_gap_or_overlap':
          'Lücke oder Überlappung im Auszugszeitraum',
      'statement_balance_discontinuity':
          'Die Salden aufeinanderfolgender Auszüge passen nicht',
      'statement_coverage_incomplete':
          'Der Kontoführungszeitraum ist nicht vollständig belegt',
      'source_changed': 'Eine zugeordnete Geldquelle wurde geändert',
      'bank_amount_unmatched':
          'Ein Bankbetrag ist noch nicht vollständig zugeordnet',
      'cash_amount_unmatched':
          'Ein vorhandener Geldfluss ist noch nicht vollständig abgeglichen',
    }[code] ??
    code;
String bankSourceLabel(dynamic kind) =>
    const {
      'cash_event': 'Belegter Geldfluss',
      'reviewed_external_cash': 'Geprüfte Sondergeldbewegung',
      'payroll_cash': 'Belegte Lohnzahlung',
      'travel_cash': 'Belegte Reiseerstattung',
    }[kind] ??
    'Geldquelle';
void _checkTravelSources(Map<String, dynamic> value) {
  for (final list in [value['items'], value['links'], value['cash_rows']]) {
    for (final raw in list as List? ?? []) {
      final source = businessMap(businessMap(raw)['source']);
      if (source['source_kind'] == 'travel_cash') travelBankSource(source);
    }
  }
}

String _sourceKey(Map<String, dynamic> s) {
  if (s['source_kind'] == 'travel_cash') travelBankSource(s);
  return '${s['source_kind']}:${s['source_id']}';
}

Map<String, dynamic> bankMatchInput(
  Map<String, dynamic> page,
  Map<String, dynamic> values,
  List<Map<String, dynamic>> selected,
) {
  final seen = <String>{}, links = <Map<String, dynamic>>[];
  for (var i = 0; i < selected.length; i++) {
    final source = businessMap(selected[i]['source']), key = _sourceKey(source);
    if (!seen.add(key) ||
        !businessItems(page['items']).any(
          (v) =>
              bankSame(v['source'], source) &&
              v['stale_existing_links'] != true,
        ))
      _fail('Nur aktuelle ausdrücklich ausgewählte Geldquellen verwenden.');
    final amount = bankMoney(values['amount_$i'], positive: true),
        difference = '${values['date_reason_$i'] ?? ''}'.trim();
    if (source['date'] != page['transaction']?['payload']?['booking_date'] &&
        difference.isEmpty)
      _fail('Abweichende tatsächliche Zahlungstage ausdrücklich begründen.');
    links.add({
      'source_kind': source['source_kind'],
      'source_id': source['source_id'],
      'source_hash': source['source_hash'],
      'amount': amount,
      'date_difference_reason': difference,
    });
  }
  final reason = '${values['reason'] ?? ''}'.trim();
  if (reason.isEmpty) _fail('Zuordnungs- oder Aufhebungsgrund angeben.');
  return {
    'revision': page['current']['revision'],
    'links': links,
    'reason': reason,
  };
}

Map<String, dynamic> bankMatchPreview(
  dynamic raw,
  Map<String, dynamic> body,
  String transaction,
) {
  final value = businessMap(raw), links = businessItems(value['links']);
  if (value['transaction']?['id'] != transaction ||
      value['revision'] != body['revision'] + 1 ||
      value['reason'] != body['reason'] ||
      !_hash.hasMatch('${value['preview_hash']}') ||
      value['links'] is! List ||
      links.length != (body['links'] as List).length)
    _fail('Die Zuordnungsvorschau passt nicht zum Auftrag.');
  for (var i = 0; i < links.length; i++) {
    final link = links[i], b = body['links'][i];
    if ([
          'source_kind',
          'source_id',
          'source_hash',
        ].any((k) => link['source']?[k] != b[k]) ||
        link['amount'] != b['amount'] ||
        link['date_difference_reason'] != b['date_difference_reason'])
      _fail('Quellen oder Teilbeträge der Zuordnung wurden verändert.');
  }
  _checkTravelSources(value);
  return value;
}

Map<String, dynamic> bankReportPreview(dynamic raw, Map<String, dynamic> body) {
  final value = businessMap(raw);
  if (value['schema_version'] != 1 ||
      value['account_id'] != body['account_id'] ||
      value['period'] != body['period'] ||
      value['reason'] != body['reason'] ||
      !bankSame(
        List.of(value['statement_ids'] ?? [])..sort(),
        List.of(body['statement_ids'])..sort(),
      ) ||
      ['issues', 'bank_rows', 'cash_rows'].any((k) => value[k] is! List) ||
      value['complete'] is! bool ||
      [
        'external_bank_verification',
        'new_payment_created',
        'tax_classification_changed',
      ].any((k) => value[k] != false) ||
      !_hash.hasMatch('${value['state_hash']}') ||
      !_hash.hasMatch('${value['preview_hash']}'))
    _fail(
      'Der Abgleichbericht ist nicht eindeutig an den geprüften Umfang gebunden.',
    );
  _checkTravelSources(value);
  return value;
}

void Function(dynamic) bankReceipt(
  String kind,
  Map<String, dynamic> body,
  Map<String, dynamic>? preview,
) {
  final b = _copy(body), p = preview == null ? null : _copy(preview);
  return (raw) {
    final value = businessMap(raw);
    switch (kind) {
      case 'account':
        bankEvent(value);
        if (value['account_id'] != b['account_id'] ||
            value['revision'] != b['revision'] + 1 ||
            value['payload']['account']?['id'] != b['account_id'] ||
            value['payload']['account']?['revision'] != b['account_revision'] ||
            [
              'iban',
              'label',
              'active',
              'coverage_from',
              'coverage_to',
              'reason',
            ].any((k) => value['payload'][k] != b[k]))
          _fail('Die Kontobindung bestätigt nicht den ursprünglichen Auftrag.');
        break;
      case 'import':
        final event = bankEvent(value['statement']);
        if (event['account_id'] != b['account_id'] ||
            !bankSame(event['payload'], p!['metadata']) ||
            value['original']?['sha256'] != p['metadata']['file_sha256'] ||
            value['original']?['filename'] != b['filename'] ||
            value['original']?['path'] !=
                '/bank/statements/${event['id']}/original' ||
            value['lines'] is! List ||
            (value['lines'] as List).length !=
                (p['metadata']['rows'] as List).length)
          _fail(
            'Die Importquittung bestätigt nicht das vollständige Original.',
          );
        final lines = businessItems(value['lines']);
        for (var i = 0; i < lines.length; i++) {
          final line = lines[i],
              transaction = bankEvent(line['transaction']),
              row = businessMap(p['metadata']['rows'][i]);
          if (line['line_number'] != row['line_number'] ||
              line['transaction_id'] != transaction['id'] ||
              transaction['account_id'] != b['account_id'] ||
              !bankSame(transaction['payload'], {
                for (final e in row.entries)
                  if (e.key != 'line_number') e.key: e.value,
              }))
            _fail(
              'Bestätigte Bankzeilen wurden gegenüber der Vorschau verändert.',
            );
        }
        break;
      case 'match':
        bankEvent(value);
        if (value['transaction_id'] != p!['transaction']['id'] ||
            value['revision'] != p['revision'] ||
            value['previous_hash'] != p['previous_hash'] ||
            !bankSame(value['payload'], {
              for (final k in [
                'transaction',
                'links',
                'reason',
                'matched_amount',
                'remaining',
                'complete',
                'preview_hash',
              ])
                k: p[k],
            }))
          _fail('Die Zuordnungsquittung passt nicht exakt zur Vorschau.');
        break;
      case 'report':
        final event = bankEvent(value['record']);
        if (event['account_id'] != b['account_id'] ||
            event['period'] != b['period'] ||
            !bankSame(event['payload'], p) ||
            ['json', 'csv', 'pdf'].any(
              (k) =>
                  !_hash.hasMatch('${value['exports']?[k]?['sha256']}') ||
                  value['exports']?[k]?['size'] is! int ||
                  value['exports'][k]['size'] < 1,
            ))
          _fail(
            'Der gespeicherte Bericht bestätigt nicht die geprüfte Fassung.',
          );
        break;
      default:
        _fail('Unbekannter Bankvorgang.');
    }
  };
}

String bankExportMediaType(String format, Map<String, dynamic> manifest) {
  final expected = const {
        'json': 'application/json',
        'csv': 'text/csv',
        'pdf': 'application/pdf',
      }[format],
      actual = '${manifest['media_type'] ?? ''}'
          .split(';')
          .first
          .trim()
          .toLowerCase();
  if (expected == null || actual != expected)
    _fail('Das Exportmanifest nennt ein unerwartetes Dateiformat.');
  return actual;
}

Future<String> bankDigest(List<int> bytes) async =>
    (await Sha256().hash(bytes)).bytes
        .map((v) => v.toRadixString(16).padLeft(2, '0'))
        .join();
Future<void> bankVerifyBytes(
  Uint8List bytes,
  Map<String, dynamic> manifest, {
  Map<String, dynamic>? event,
}) async {
  if (await bankDigest(bytes) != manifest['sha256'] ||
      manifest['size'] != null && bytes.length != manifest['size'])
    _fail(
      'Die vollständige Datei stimmt nicht mit dem archivierten Nachweis überein.',
    );
  if (event != null && !bankSame(jsonDecode(utf8.decode(bytes)), event))
    _fail('Der JSON-Export gehört nicht zum gewählten Bericht.');
}

class BusinessBankReconciliationPage extends StatefulWidget {
  const BusinessBankReconciliationPage({
    super.key,
    required this.session,
    this.pickFile,
  });
  final BusinessSession session;
  final Future<XFile?> Function()? pickFile;
  @override
  State<BusinessBankReconciliationPage> createState() =>
      _BusinessBankReconciliationPageState();
}

class _BusinessBankReconciliationPageState
    extends State<BusinessBankReconciliationPage> {
  BusinessSession get session => widget.session;
  Map<String, dynamic>? accounts, data, preview, command;
  String view = 'accounts',
      title = 'Bankabgleich',
      kind = '',
      key = '',
      path = '';
  String? error;
  bool busy = false, accepted = false;
  Object? generation;
  bool get readable => bankReadable(session);
  bool get writable => bankWritable(session);
  @override
  void initState() {
    super.initState();
    session.addListener(changed);
    load();
  }

  @override
  void dispose() {
    session.removeListener(changed);
    super.dispose();
  }

  void changed() {
    if (!mounted) return;
    setState(() {
      if (!readable || generation != null && generation != session.generation) {
        accounts = data = preview = command = null;
        accepted = false;
      }
    });
  }

  Future<Map<String, dynamic>> fresh({
    bool write = false,
    bool admin = false,
    String? account,
    String? transaction,
  }) async {
    final before = session.generation;
    await session.load();
    void check() {
      if (!mounted ||
          !readable ||
          write && !writable ||
          admin && !bankAdministrative(session) ||
          before != session.generation)
        _fail(
          'Aktuelle globale Bank-, Finanz- und Buchführungsrechte fehlen oder die Sitzung wurde geändert.',
          403,
        );
    }

    check();
    final page = businessMap(await session.read('/bank/accounts'));
    if (page['items'] is! List ||
        page['available_accounts'] is! List ||
        page['external_connection'] != false)
      _fail(
        'Die eingerichteten Bankkonten konnten nicht eindeutig geprüft werden.',
      );
    if (account != null &&
        (!businessItems(page['available_accounts'])
                .any((v) => v['id'] == account) ||
            !admin &&
                !businessItems(page['items'])
                    .any((v) => v['account_id'] == account)))
      _fail('Das ursprüngliche Geldkonto ist nicht zugänglich.', 403);
    if (transaction != null) {
      final candidate = businessMap(
        await session.read('/bank/transactions/$transaction/candidates'),
      );
      if (candidate['transaction']?['id'] != transaction ||
          candidate['current']?['transaction_id'] != transaction ||
          candidate['items'] is! List)
        _fail('Die Banktransaktion gehört nicht zum ursprünglichen Auftrag.');
      check();
      generation = session.generation;
      return candidate;
    }
    check();
    generation = session.generation;
    return page;
  }

  Future<void> act(Future<void> Function() fn) async {
    if (busy) return;
    setState(() => busy = true);
    try {
      await fn();
    } catch (e) {
      if (mounted) setState(() => error = '$e');
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  Future<void> present(Future<void> Function() fn) async {
    try {
      await fn();
    } catch (e) {
      if (mounted) setState(() => error = '$e');
    }
  }

  void display(String next, String heading, Map<String, dynamic> value) {
    if (!mounted || !readable || generation != session.generation) return;
    setState(() {
      view = next;
      title = heading;
      data = value;
      preview = command = null;
      accepted = false;
      error = null;
    });
  }

  Future<void> load() async {
    try {
      final page = await fresh();
      if (mounted) {
        setState(() => accounts = page);
        display('accounts', 'Bankabgleich', page);
      }
    } catch (e) {
      if (mounted) setState(() => error = '$e');
    }
  }

  Future<void> qontoRead() async {
    await fresh();
    final status = businessMap(
      await session.legacyRead('/api/bank-feeds/qonto/status'),
    );
    await fresh();
    if (status['provider'] != 'qonto' ||
        status['read_only'] != true ||
        status['configured'] is! bool)
      _fail('Der Qonto-Verbindungsstand ist nicht eindeutig.');
    if (status['configured'] != true) {
      display('qonto-unconfigured', 'Qonto lesen', {});
      return;
    }
    final accountId = '${status['account_id']}';
    await fresh(account: accountId);
    await editor(
      'Qonto lesen',
      [
        const BusinessField(
          'from',
          'Änderungen ab (UTC, einschließlich)',
          type: BusinessInput.date,
          required: true,
        ),
        const BusinessField(
          'to',
          'Änderungen bis (UTC, ausschließlich)',
          type: BusinessInput.date,
          required: true,
        ),
      ],
      (values) async {
        final body = qontoWindow(values);
        await fresh(account: accountId);
        final result = await session.api.call(
          '/api/bank-feeds/qonto/read',
          body,
        );
        final page = await fresh(account: accountId);
        final binding = businessItems(page['items'])
            .firstWhere((v) => v['account_id'] == accountId);
        final checked = await qontoReadView(
          result,
          accountId: accountId,
          bindingHash: binding['content_hash'],
          iban: binding['payload']['iban'],
          body: body,
        );
        await fresh(account: accountId);
        display('qonto', 'Qonto · gelesene Umsatzänderungen', checked);
      },
    );
  }

  Widget card(String title, List<Widget> children) => Card(
    child: Padding(
      padding: const EdgeInsets.all(18),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(title, style: Theme.of(context).textTheme.titleLarge),
          const SizedBox(height: 8),
          ...children,
        ],
      ),
    ),
  );
  Widget action(String label, Future<void> Function() fn) => Padding(
    padding: const EdgeInsets.only(bottom: 8),
    child: OutlinedButton(
      onPressed: busy ? null : () => present(fn),
      child: Text(label),
    ),
  );
  Future<void> editor(
    String title,
    List<BusinessField> fields,
    Future<void> Function(Map<String, dynamic>) save, {
    String? pendingKey,
  }) async {
    if (!mounted) return;
    final opening = session.generation;
    await showDialog<bool>(
      context: context,
      builder: (_) => BusinessEditor(
        session: session,
        title: title,
        fields: fields,
        saveLabel: 'Angaben unverbindlich prüfen',
        pendingKey: pendingKey,
        readAllowed: () => readable && opening == session.generation,
        onSave: save,
      ),
    );
  }

  void prepare(
    String operation,
    String pendingKey,
    String route,
    Map<String, dynamic> body,
    Map<String, dynamic>? proof,
  ) {
    if (!mounted || !readable) return;
    setState(() {
      kind = operation;
      key = pendingKey;
      path = route;
      command = operation == 'account'
          ? _copy(body)
          : {
              ..._copy(body),
              'preview_hash': proof!['preview_hash'],
              'confirmation': true,
            };
      preview = proof == null ? null : _copy(proof);
      accepted = false;
      error = null;
    });
  }

  Future<void> confirm() async {
    if (!accepted || command == null) return;
    final body = _copy(command),
        proof = preview == null ? null : _copy(preview);
    await fresh(
      write: true,
      admin: kind == 'account',
      account: body['account_id'],
      transaction: kind == 'match' ? proof!['transaction']['id'] : null,
    );
    final result = session.pending(key)
        ? await session.repeatBankCommand(key)
        : await session.command(
            key,
            path,
            body,
            validateResult: bankReceipt(kind, body, proof),
          );
    if (kind == 'report') {
      await openReport('${result['record']['id']}');
    } else if (kind == 'match') {
      await openMatch('${proof!['transaction']['id']}');
    } else if (kind == 'import') {
      await openStatement('${result['statement']['id']}');
    } else {
      await load();
    }
  }

  Future<void> binding([Map<String, dynamic>? old]) async {
    final page = await fresh(write: true, admin: true),
        available = businessItems(page['available_accounts'])
            .where(
              (v) =>
                  v['active'] == true &&
                  (old == null || v['id'] == old['account_id']),
            )
            .toList(),
        payload = businessMap(old?['payload']);
    await editor(
      'Bankkonto ausdrücklich verbinden',
      [
        BusinessField(
          'account_id',
          'Vorhandenes EUR-Bankgeldkonto',
          type: BusinessInput.choice,
          required: true,
          initial: old?['account_id'] ?? '',
          choices: {
            '': 'Geldkonto auswählen',
            for (final a in available)
              '${a['id']}': '${a['code']} · ${a['name']}',
          },
        ),
        BusinessField(
          'iban',
          'IBAN',
          required: true,
          initial: payload['iban'] ?? '',
          hint: 'Die Prüfziffer bestätigt keinen Kontoinhaber; bestehende IBAN bleibt unverändert.',
        ),
        BusinessField(
          'label',
          'Bankbezeichnung',
          required: true,
          initial: payload['label'] ?? '',
        ),
        BusinessField(
          'coverage_from',
          'Belegter Kontoführungsbeginn',
          type: BusinessInput.date,
          required: true,
          initial: payload['coverage_from'],
        ),
        BusinessField(
          'coverage_to',
          'Belegtes Kontoführungsende (falls beendet)',
          type: BusinessInput.date,
          initial: payload['coverage_to'],
        ),
        BusinessField(
          'active',
          'Bankbindung aktiv',
          type: BusinessInput.toggle,
          initial: payload['active'] ?? false,
        ),
        BusinessField(
          'reason',
          'Anlage- oder Änderungsgrund',
          type: BusinessInput.multiline,
          required: old != null,
        ),
      ],
      (v) async {
        final current = await fresh(write: true, admin: true),
            account = businessItems(current['available_accounts'])
                .where((a) => a['id'] == v['account_id'] && a['active'] == true)
                .firstOrNull;
        if (account == null)
          _fail('Das gewählte Geldkonto ist nicht mehr aktiv.');
        final body = <String, dynamic>{
          'account_id': account['id'],
          'account_revision': account['revision'],
          'revision': old?['revision'] ?? 0,
          'iban': '${v['iban']}'.replaceAll(RegExp(r'\s'), '').toUpperCase(),
          'label': '${v['label']}'.trim(),
          'active': v['active'] == true,
          'coverage_from': v['coverage_from'],
          'coverage_to': '${v['coverage_to'] ?? ''}'.isEmpty
              ? null
              : v['coverage_to'],
          'reason': '${v['reason'] ?? ''}'.trim(),
        };
        prepare(
          'account',
          'bank-account-${account['id']}',
          '/bank/accounts',
          body,
          null,
        );
      },
    );
  }

  Future<void> openAccount(
    String accountId, {
    int offset = 0,
    int reportOffset = 0,
  }) async {
    final page = await fresh(account: accountId),
        binding = businessItems(page['items'])
            .where((v) => v['account_id'] == accountId)
            .firstOrNull;
    if (binding == null) _fail('Bankbindung fehlt.');
    final statements = businessMap(
          await session.read(
            '/bank/statements?account_id=$accountId&limit=50&offset=$offset',
          ),
        ),
        reports = businessMap(
          await session.read(
            '/bank/reconciliations?account_id=$accountId&limit=50&offset=$reportOffset',
          ),
        );
    display('account', 'Bankkonto · ${binding['payload']['label']}', {
      'binding': binding,
      'statements': statements,
      'reports': reports,
      'offset': offset,
      'report_offset': reportOffset,
    });
  }

  Future<void> importFile(Map<String, dynamic> binding) async {
    await fresh(write: true, account: binding['account_id']);
    final opening = session.generation,
        file =
            await (widget.pickFile?.call() ??
                openFile(
                  acceptedTypeGroups: [
                    const XTypeGroup(
                      label: 'CSV-Kontoauszug',
                      extensions: ['csv'],
                    ),
                  ],
                ));
    if (file == null) return;
    final size = await file.length();
    if (size < 1 || size > 5 * 1024 * 1024)
      _fail('Eine originale CSV-Datei mit 1 Byte bis 5 MiB auswählen.');
    final bytes = await file.readAsBytes(), digest = await bankDigest(bytes);
    await fresh(write: true, account: binding['account_id']);
    if (opening != session.generation || bytes.length != size)
      _fail('Datei oder Sitzung wurde während der Auswahl geändert.');
    final importKey = 'bank-import-${offlineId()}';
    await editor(
      'Originalen Kontoauszug prüfen',
      [
        const BusinessField(
          'statement_reference',
          'Unveränderte Auszugsreferenz',
          required: true,
        ),
        const BusinessField(
          'period_from',
          'Auszugsbeginn',
          type: BusinessInput.date,
          required: true,
        ),
        const BusinessField(
          'period_to',
          'Auszugsende',
          type: BusinessInput.date,
          required: true,
        ),
        const BusinessField(
          'opening_balance',
          'Belegter Anfangssaldo (€)',
          type: BusinessInput.decimal,
          required: true,
        ),
        const BusinessField(
          'closing_balance',
          'Belegter Endsaldo (€)',
          type: BusinessInput.decimal,
          required: true,
        ),
        const BusinessField(
          'delimiter',
          'Trennzeichen der Originaldatei',
          type: BusinessInput.choice,
          required: true,
          initial: '',
          choices: {'': 'Auswählen', ';': 'Semikolon', ',': 'Komma'},
        ),
        BusinessField(
          'complete',
          'Ich bestätige den vollständigen Originalauszug ${file.name} für den angegebenen Zeitraum.',
          type: BusinessInput.toggle,
          initial: false,
        ),
      ],
      (v) async {
        if (v['complete'] != true)
          _fail('Den vollständigen Originalauszug ausdrücklich bestätigen.');
        final current = await fresh(
              write: true,
              account: binding['account_id'],
            ),
            a = businessItems(current['available_accounts'])
                .firstWhere((a) => a['id'] == binding['account_id']),
            b = businessItems(current['items'])
                .firstWhere((a) => a['account_id'] == binding['account_id']),
            body = <String, dynamic>{
              'account_id': binding['account_id'],
              'account_revision': a['revision'],
              'bank_revision': b['revision'],
              'statement_reference': '${v['statement_reference']}'.trim(),
              'period_from': v['period_from'],
              'period_to': v['period_to'],
              'opening_balance': bankMoney(v['opening_balance'], signed: true),
              'closing_balance': bankMoney(v['closing_balance'], signed: true),
              'filename': file.name,
              'delimiter': v['delimiter'],
              'content_base64': base64Encode(bytes),
              'complete_statement_confirmed': true,
            };
        await importPreview(body, digest, importKey);
      },
    );
  }

  Future<void> importPreview(
    Map<String, dynamic> body,
    String digest,
    String pendingKey,
  ) async {
    await fresh(write: true, account: body['account_id']);
    final proof = bankImportPreview(
      await session.api.call(session.path('/bank/import/preview'), body),
      body,
      digest,
    );
    if (proof['can_import'] == true) {
      prepare('import', pendingKey, '/bank/statements', body, proof);
    } else {
      display('import-errors', 'Kontoauszug prüfen', {
        'body': body,
        'proof': proof,
        'digest': digest,
        'key': pendingKey,
      });
    }
  }

  Future<void> distinct() async {
    final saved = _copy(data),
        checks = businessItems(saved['proof']['identity_checks']);
    await editor(
      'Inhaltsgleiche Bankzeilen ausdrücklich prüfen',
      [
        for (var i = 0; i < checks.length; i++)
          BusinessField(
            'distinct_$i',
            '${checks[i]['external_id']}: eigenständige Zahlung gegenüber ${(checks[i]['similar_external_ids'] as List).join(', ')}',
            type: BusinessInput.multiline,
            required: true,
          ),
      ],
      (v) => importPreview(
        {
          ...businessMap(saved['body']),
          'distinct_transaction_confirmations': {
            for (var i = 0; i < checks.length; i++)
              checks[i]['external_id']: '${v['distinct_$i']}'.trim(),
          },
        },
        saved['digest'],
        saved['key'],
      ),
    );
  }

  Future<void> openStatement(String id) async {
    await fresh();
    final value = businessMap(await session.read('/bank/statements/$id'));
    if (bankEvent(value['statement'])['id'] != id)
      _fail('Falscher Kontoauszug.');
    display('statement', 'Originaler Kontoauszug', value);
  }

  Future<void> original(Map<String, dynamic> value) async {
    final id = '${value['statement']['id']}',
        account = '${value['statement']['account_id']}';
    await fresh(account: account);
    final opening = session.generation,
        bytes = await session.api.bytes(
          session.path('/bank/statements/$id/original'),
          mediaType: 'text/csv',
          maxBytes: 5 * 1024 * 1024,
        );
    await bankVerifyBytes(bytes, businessMap(value['original']));
    await fresh(account: account);
    await save(
      bytes,
      '${value['original']['filename']}',
      'text/csv',
      '${value['original']['sha256']}',
      opening,
    );
  }

  Future<void> save(
    Uint8List bytes,
    String filename,
    String media,
    String digest,
    Object? opening,
  ) async {
    if (!mounted || !readable || opening != session.generation) return;
    await exportMailAttachment(
      context,
      VerifiedMailAttachment(
        bytes: bytes,
        filename: filename,
        mediaType: media,
        sha256: digest,
      ),
      () => mounted && readable && opening == session.generation,
    );
  }

  Future<void> openMatch(String id) async {
    final value = await fresh(transaction: id);
    display('match', 'Bankzeile ausdrücklich abgleichen', value);
  }

  Future<void> chooseMatch(Map<String, dynamic> page) async {
    final candidates = businessItems(page['items'])
        .where((v) => v['stale_existing_links'] != true)
        .toList();
    List<Map<String, dynamic>>? selected;
    await editor(
      'Vorhandene Geldquellen auswählen',
      [
        BusinessField(
          'sources',
          'Ausdrücklich abzugleichende Geldquellen',
          type: BusinessInput.multiple,
          initial: const <String>[],
          choices: {
            for (final v in candidates)
              _sourceKey(
                businessMap(v['source']),
              ): '${bankSourceLabel(v['source']['source_kind'])} · ${v['source']['date']} · verfügbar ${businessMoney(v['remaining'])} · ${v['source']['source_id']}',
          },
        ),
      ],
      (v) async {
        selected = candidates
            .where(
              (c) => (v['sources'] as List).contains(
                _sourceKey(businessMap(c['source'])),
              ),
            )
            .toList();
      },
    );
    if (selected != null && mounted) await matchFields(page, selected!);
  }

  Future<void> matchFields(
    Map<String, dynamic> page,
    List<Map<String, dynamic>> selected,
  ) async {
    await editor(
      selected.isEmpty
          ? 'Zuordnung ausdrücklich aufheben'
          : 'Explizite Teilbeträge',
      [
        for (var i = 0; i < selected.length; i++) ...[
          BusinessField(
            'amount_$i',
            '${bankSourceLabel(selected[i]['source']['source_kind'])} ${selected[i]['source']['source_id']}: tatsächlicher Teilbetrag (€)',
            type: BusinessInput.decimal,
            required: true,
            hint: 'Verfügbar ${businessMoney(selected[i]['remaining'])}',
          ),
          BusinessField(
            'date_reason_$i',
            'Begründung abweichender Zahlungstage',
            type: BusinessInput.multiline,
            required:
                selected[i]['source']['date'] !=
                page['transaction']['payload']['booking_date'],
          ),
        ],
        BusinessField(
          'reason',
          selected.isEmpty
              ? 'Begründung der Zuordnungsaufhebung'
              : 'Zuordnungsgrund',
          type: BusinessInput.multiline,
          required: true,
        ),
      ],
      (v) async {
        final id = '${page['transaction']['id']}',
            current = await fresh(write: true, transaction: id);
        if (current['current']['revision'] != page['current']['revision'])
          _fail('Die Zuordnung wurde inzwischen geändert. Bitte neu öffnen.');
        final body = bankMatchInput(current, v, selected),
            proof = bankMatchPreview(
              await session.api.call(
                session.path('/bank/transactions/$id/preview'),
                body,
              ),
              body,
              id,
            );
        prepare(
          'match',
          'bank-match-$id',
          '/bank/transactions/$id/matches',
          body,
          proof,
        );
      },
    );
  }

  Future<void> history(String id, [int offset = 0]) async {
    await fresh(transaction: id);
    final value = businessMap(
      await session.read(
        '/bank/transactions/$id/history?limit=50&offset=$offset',
      ),
    );
    display('history', 'Unveränderlicher Zuordnungsverlauf', {
      'transaction_id': id,
      ...value,
    });
  }

  Future<void> reportEditor(Map<String, dynamic> binding) async {
    await fresh(write: true, account: binding['account_id']);
    final items = <Map<String, dynamic>>[];
    int? offset = 0;
    do {
      final page = businessMap(
        await session.read(
          '/bank/statements?account_id=${binding['account_id']}&limit=100&offset=$offset',
        ),
      );
      items.addAll(businessItems(page['items']));
      offset = page['next_offset'];
    } while (offset != null && items.length < 10000);
    await editor(
      'Monatsabgleich vorbereiten',
      [
        const BusinessField(
          'period',
          'Abzugleichender Monat (JJJJ-MM)',
          required: true,
        ),
        BusinessField(
          'statement_ids',
          'Ausdrücklich geprüfte vollständige Kontoauszüge',
          type: BusinessInput.multiple,
          required: true,
          initial: const <String>[],
          choices: {
            for (final v in items)
              '${v['id']}':
                  '${v['reference_key']} · ${businessDate(v['created_at'])}',
          },
        ),
        const BusinessField(
          'reason',
          'Prüfgrund und Umfang',
          type: BusinessInput.multiline,
          required: true,
        ),
      ],
      (v) async {
        final ids = List<String>.from(v['statement_ids']);
        if (!RegExp(r'^\d{4}-\d{2}$').hasMatch('${v['period']}') ||
            ids.isEmpty ||
            ids.length > 100)
          _fail(
            'Monat und 1 bis 100 vollständige Auszüge ausdrücklich auswählen.',
          );
        final body = <String, dynamic>{
          'account_id': binding['account_id'],
          'period': v['period'],
          'statement_ids': ids,
          'reason': '${v['reason']}'.trim(),
        };
        await fresh(write: true, account: binding['account_id']);
        final proof = bankReportPreview(
          await session.api.call(
            session.path('/bank/reconciliations/preview'),
            body,
          ),
          body,
        );
        prepare(
          'report',
          'bank-reconciliation-${offlineId()}',
          '/bank/reconciliations',
          body,
          proof,
        );
      },
    );
  }

  Future<void> openReport(String id) async {
    await fresh();
    final value = businessMap(await session.read('/bank/reconciliations/$id'));
    if (bankEvent(value['record'])['id'] != id)
      _fail('Der Bericht gehört nicht zur gewählten Fassung.');
    display('report', 'Gespeicherter Bankprüfstand', value);
  }

  Future<void> exportReport(Map<String, dynamic> value, String format) async {
    await fresh(account: value['record']['account_id']);
    final opening = session.generation,
        manifest = businessMap(value['exports'][format]),
        size = manifest['size'];
    if (size is! int || size < 1 || size > 128 * 1024 * 1024)
      _fail('Der Bankexport überschreitet den geprüften Downloadumfang.');
    final bytes = await session.api.bytes(
      session.path('/bank/reconciliations/${value['record']['id']}/$format'),
      mediaType: bankExportMediaType(format, manifest),
      maxBytes: size,
    );
    await bankVerifyBytes(
      bytes,
      manifest,
      event: format == 'json' ? businessMap(value['record']) : null,
    );
    await fresh(account: value['record']['account_id']);
    await save(
      bytes,
      manifest['filename'],
      bankExportMediaType(format, manifest),
      manifest['sha256'],
      opening,
    );
  }

  List<Widget> reportSummary(Map<String, dynamic> v) => [
    Text(
      'Nachweiszeitraum ${v['coverage_from']} bis ${v['coverage_to']} · ${v['reason']}',
    ),
    Notice(
      v['complete'] == true
          ? 'Alle ausgewählten Bankzeilen und vorhandenen Geldflüsse sind in diesem Prüfstand vollständig abgeglichen.'
          : 'Dieser Prüfstand ist unvollständig und erlaubt keinen Periodenabschluss.',
    ),
    for (final pair in {
      'Anfangssaldo': v['opening_balance'],
      'Endsaldo': v['closing_balance'],
      'Bankbewegung': v['bank_movement_net'],
      'Erfasster Geldfluss': v['cash_movement_net'],
    }.entries)
      Text('${pair.key}: ${businessMoney(pair.value)}'),
    for (final issue in businessItems(v['issues']))
      Notice(
        '${_bankIssue('${issue['code']}')}${issue['id'] == null ? '' : ' · ${issue['id']}'}${issue['message'] == null ? '' : ' · ${issue['message']}'}',
        error: true,
      ),
    ExpansionTile(
      tilePadding: EdgeInsets.zero,
      title: Text(
        'Bankzeilen und vorhandene Geldflüsse prüfen (${businessItems(v['bank_rows']).length} / ${businessItems(v['cash_rows']).length})',
      ),
      children: [
        for (final row in businessItems(v['bank_rows']).take(100))
          ListTile(
            title: Text(
              '${row['transaction']['external_id']} · ${row['transaction']['payload']['booking_date']} · ${businessMoney(row['transaction']['payload']['amount'])}',
            ),
            subtitle: Text(
              'Zugeordnet ${businessMoney(row['matched_amount'])} · offen ${businessMoney(row['remaining'])}',
            ),
          ),
        for (final row in businessItems(v['cash_rows']).take(100))
          ListTile(
            title: Text(
              '${bankSourceLabel(row['source']['source_kind'])} · ${row['source']['source_id']} · ${row['source']['date']} · ${businessMoney(row['source']['amount'])}',
            ),
            subtitle: Text(
              'Zugeordnet ${businessMoney(row['matched_amount'])} · offen ${businessMoney(row['remaining'])}',
            ),
          ),
        if (businessItems(v['bank_rows']).length > 100 ||
            businessItems(v['cash_rows']).length > 100)
          const Notice(
            'Die ersten 100 Zeilen jeder Art werden angezeigt. Das archivierte JSON/CSV enthält den vollständigen Prüfstand.',
          ),
      ],
    ),
    const Notice(
      'Keine externe Bankbestätigung, keine neue Zahlung und keine Änderung der Steuerzuordnung.',
    ),
  ];
  List<Widget> content() {
    final v = data!;
    switch (view) {
      case 'accounts':
        return [
          if (session.hasFeature('qonto_read_only'))
            action('Qonto-Umsatzänderungen lesen', qontoRead),
          if (bankAdministrative(session))
            action('Vorhandenes Geldkonto mit Bank verbinden', () => binding()),
          for (final item in businessItems(v['items']))
            card('${item['payload']['label']}', [
              Text(
                '${item['payload']['account']['code']} · ${item['payload']['iban']}',
              ),
              Text(
                'Nachweis ab ${item['payload']['coverage_from']} bis ${item['payload']['coverage_to'] ?? 'offen'} · ${item['payload']['active'] == true ? 'Aktiv' : 'Inaktiv'}',
              ),
              action(
                'Kontoauszüge und Abgleich öffnen',
                () => openAccount(item['account_id']),
              ),
              if (bankAdministrative(session))
                action('Bankbindung bearbeiten', () => binding(item)),
            ]),
          if (businessItems(v['items']).isEmpty)
            const Notice(
              'Vorhandenes EUR-Geldkonto der Art Bank auswählen. Geldkonten werden unter EÜR-Vorbereitung angelegt.',
            ),
        ];
      case 'qonto-unconfigured':
        return [
          const Notice(
            'Qonto ist noch nicht verbunden. Ein Administrator muss den Lesezugang auf dem Server einrichten. Der CSV-Bankabgleich steht weiterhin zur Verfügung.',
          ),
          action('Alle Bankkonten', load),
        ];
      case 'qonto':
        return [
          const Notice(
            'Dieser Abruf zeigt Umsatzänderungen. Er ist kein vollständiger Kontoauszug und erzeugt keine Zahlung oder Buchung.',
          ),
          Text('${v['organization']['name']} · ${v['account_after']['iban']}'),
          Text(
            'Aktuell gelesener Saldo: ${businessMoney(qontoMoney(v['account_after']['balance_cents']))}',
          ),
          const Notice(
            'Der Zeitraum bezieht sich auf Änderungen beim Anbieter. Bereits früher gebuchte Umsätze können darin enthalten sein. Vorgemerkte, abgelehnte und stornierte Umsätze sind gesondert gekennzeichnet.',
          ),
          for (final row in businessItems(v['items']))
            card(qontoStatusLabel(row['status'])!, [
              Text('${row['counterparty'] ?? row['label']}'),
              Text(
                '${businessMoney(qontoMoney(row['signed_amount_cents']))} · ${businessDate(row['updated_at'], time: true)}',
              ),
            ]),
          if (businessItems(v['items']).isEmpty)
            const Notice(
              'Für diesen Änderungszeitraum wurden keine Umsätze geliefert.',
            ),
          action('Erneut lesen', qontoRead),
          action('Alle Bankkonten', load),
        ];
      case 'account':
        final b = businessMap(v['binding']);
        return [
          if (writable && b['payload']['active'] == true)
            action('Originalen CSV-Auszug prüfen', () => importFile(b)),
          if (writable)
            action('Monatsabgleich vorbereiten', () => reportEditor(b)),
          card('Kontoauszüge', [
            for (final item in businessItems(v['statements']['items']))
              action(
                '${item['reference_key']} · ${businessDate(item['created_at'])}',
                () => openStatement(item['id']),
              ),
            if (v['statements']['next_offset'] != null)
              action(
                'Weitere Kontoauszüge',
                () => openAccount(
                  b['account_id'],
                  offset: v['statements']['next_offset'],
                  reportOffset: v['report_offset'],
                ),
              ),
          ]),
          card('Gespeicherte Monatsprüfstände', [
            for (final item in businessItems(v['reports']['items']))
              action(
                '${item['period']} · ${businessDate(item['created_at'])}',
                () => openReport(item['id']),
              ),
            if (v['reports']['next_offset'] != null)
              action(
                'Weitere Prüfstände',
                () => openAccount(
                  b['account_id'],
                  offset: v['offset'],
                  reportOffset: v['reports']['next_offset'],
                ),
              ),
          ]),
        ];
      case 'import-errors':
        return [
          for (final e in businessItems(v['proof']['errors']))
            Notice(
              '${e['line_number'] == null ? 'Auszug' : 'CSV-Zeile ${e['line_number']}'}: ${e['message']}',
              error: true,
            ),
          if (businessItems(v['proof']['identity_checks'])
              .any((c) => c['confirmed'] != true))
            action(
              'Inhaltsgleiche Zahlungen ausdrücklich unterscheiden',
              distinct,
            ),
        ];
      case 'statement':
        final lines = businessItems(v['lines']);
        return [
          Text(
            '${v['statement']['payload']['statement_reference']} · ${v['statement']['payload']['period_from']} bis ${v['statement']['payload']['period_to']}',
          ),
          action('Unverändertes CSV-Original herunterladen', () => original(v)),
          for (final line in lines.take(100))
            card(
              '${line['transaction']['external_id']} · ${businessMoney(line['transaction']['payload']['amount'])}',
              [
                Text(
                  '${line['transaction']['payload']['booking_date']} · ${line['transaction']['payload']['counterparty']} · ${line['transaction']['payload']['reference']}',
                ),
                Notice(
                  line['current']?['payload']?['complete'] == true
                      ? 'Vollständig zugeordnet'
                      : 'Noch nicht vollständig zugeordnet',
                ),
                action(
                  'Zuordnung und Verlauf',
                  () => openMatch(line['transaction_id']),
                ),
              ],
            ),
          if (lines.length > 100) ...[
            Notice('100 von ${lines.length} Zeilen angezeigt.'),
            action('Weitere Bankzeile über externe ID öffnen', () async {
              String? selected;
              await editor(
                'Bankzeile auswählen',
                [
                  const BusinessField(
                    'external_id',
                    'Exakte externe Transaktions-ID',
                    required: true,
                  ),
                ],
                (input) async {
                  selected = lines
                      .where(
                        (line) =>
                            line['transaction']['external_id'] ==
                            input['external_id'],
                      )
                      .firstOrNull?['transaction_id'];
                  if (selected == null)
                    _fail('Diese ID gehört nicht zum gewählten Auszug.');
                },
              );
              if (selected != null) await openMatch(selected!);
            }),
          ],
        ];
      case 'match':
        final id = '${v['transaction']['id']}',
            p = businessMap(v['transaction']['payload']);
        return [
          Text(
            '${p['transaction_id']} · ${p['booking_date']} · ${businessMoney(p['amount'])} · ${p['counterparty']} · ${p['reference']}',
          ),
          Notice(
            'Aktuelle Zuordnungsfassung ${v['current']['revision']}. Keine neue Zahlung und keine Änderung des EÜR-Zahltags.',
          ),
          for (final l in businessItems(v['current']['payload']['links']))
            Text(
              '${bankSourceLabel(l['source']['source_kind'])} · ${l['source']['date']} · ${businessMoney(l['amount'])}',
            ),
          action(
            'Unveränderlichen Zuordnungsverlauf öffnen',
            () => history(id),
          ),
          if (writable)
            action(
              'Teilzuordnung ausdrücklich bearbeiten',
              () => chooseMatch(v),
            ),
          if (writable && v['current']['revision'] > 0)
            action(
              'Bisherige Zuordnung ausdrücklich aufheben',
              () => matchFields(v, []),
            ),
        ];
      case 'history':
        return [
          for (final item in businessItems(v['items']))
            card(
              'Fassung ${item['revision']} · ${businessDate(item['created_at'])}',
              [
                Text('${item['payload']['reason']}'),
                for (final link in businessItems(item['payload']['links']))
                  Text(
                    '${bankSourceLabel(link['source']['source_kind'])} · ${link['source']['source_id']} · ${businessMoney(link['amount'])}',
                  ),
              ],
            ),
          if (v['next_offset'] != null)
            action(
              'Weitere Fassungen',
              () => history(v['transaction_id'], v['next_offset']),
            ),
        ];
      case 'report':
        return [
          Text(
            '${v['record']['period']} · ${businessDate(v['record']['created_at'])}',
          ),
          Notice(
            v['current'] == true
                ? 'Der gespeicherte Quellenstand ist noch aktuell.'
                : 'Dieser historische Bericht ist inzwischen veraltet. Für einen Abschluss ist ein neuer vollständiger Prüfstand erforderlich.',
            error: v['current'] != true,
          ),
          ...reportSummary(businessMap(v['record']['payload'])),
          for (final format in ['json', 'csv', 'pdf'])
            action(
              'Unveränderten ${format.toUpperCase()}-Bericht herunterladen',
              () => exportReport(v, format),
            ),
        ];
      default:
        return [];
    }
  }

  List<Widget> confirmation() {
    final b = command!, p = preview;
    return [
      card('Banknachweis bestätigen', [
        if (kind == 'account') ...[
          Text('${b['iban']} · ${b['label']}'),
          Text(
            '${b['coverage_from']} bis ${b['coverage_to'] ?? 'offen'} · ${b['active'] == true ? 'Aktiv' : 'Inaktiv'}',
          ),
        ],
        if (kind == 'import') ...[
          Text(
            '${b['filename']} · ${(p!['metadata']['rows'] as List).length} Bankzeilen · bekannte Zeilen ${(p['duplicates'] as List).length} · Bewegung ${businessMoney(p['total'])}',
          ),
          for (final row in businessItems(p['metadata']['rows']).take(100))
            Text(
              '${row['transaction_id']} · ${row['booking_date']} · ${businessMoney(row['amount'])} · ${row['counterparty']} · ${row['reference']}',
            ),
          if ((p['metadata']['rows'] as List).length > 100)
            const Notice(
              'Die ersten 100 Zeilen werden angezeigt; bestätigt wird ausschließlich der vollständige fehlerfreie Auszug.',
            ),
        ],
        if (kind == 'match') ...[
          Notice(
            p!['complete'] == true
                ? 'Bankzeile vollständig abgeglichen'
                : 'Bankzeile bleibt teilweise oder vollständig offen',
          ),
          Text(
            'Zugeordnet ${businessMoney(p['matched_amount'])} · offen ${businessMoney(p['remaining'])}',
          ),
          for (final link in businessItems(p['links']))
            Text(
              '${bankSourceLabel(link['source']['source_kind'])} · ${link['source']['source_id']} · ${link['source']['date']} · ${businessMoney(link['amount'])} · ${link['date_difference_reason']}',
            ),
        ],
        if (kind == 'report') ...reportSummary(p!),
        CheckboxListTile(
          contentPadding: EdgeInsets.zero,
          title: const Text(
            'Ich habe Original, Umfang und ausdrücklich gewählte Angaben geprüft.',
          ),
          value: accepted,
          onChanged: busy || !writable
              ? null
              : (v) => setState(() => accepted = v == true),
        ),
        FilledButton(
          onPressed: busy || !accepted || !writable ? null : () => act(confirm),
          child: const Text('Geprüften Banknachweis speichern'),
        ),
      ]),
    ];
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(title: Text(title)),
    body: !readable
        ? const BusinessEmpty(
            'Bankdaten nicht freigegeben',
            'Aktuelle globale Bank-, Finanz- und Buchführungsrechte sind erforderlich.',
          )
        : ListView(
            padding: const EdgeInsets.all(20),
            children: [
              const Notice(
                'Originale Kontoauszüge und ausdrückliche Zuordnung zu vorhandenen belegten Geldflüssen. Der Import erzeugt weder eine Zahlung noch eine EÜR-Buchung. Bankoriginale können personenbezogene Daten enthalten.',
              ),
              if (error != null) Notice(error!, error: true),
              if (busy) const LinearProgressIndicator(),
              action('Alle Bankkonten / Stand aktualisieren', load),
              for (final pending in session.pendingBankKeys)
                action(
                  'Ursprünglichen Bankauftrag unverändert erneut senden',
                  () async {
                    await act(() async {
                      await session.repeatBankCommand(pending);
                      await load();
                    });
                  },
                ),
              if (command != null)
                ...confirmation()
              else if (data != null)
                ...content(),
            ],
          ),
  );
}

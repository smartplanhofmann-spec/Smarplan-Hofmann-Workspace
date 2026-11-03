import 'dart:convert';

import 'package:cryptography/cryptography.dart';
import 'package:file_selector/file_selector.dart';
import 'package:flutter/material.dart';

import 'api.dart';
import 'business_session.dart';
import 'business_widgets.dart';
import 'design.dart';
import 'mail_attachment_widgets.dart';

const purchaseChangeKinds = {
  'quantity_change': 'Vereinbarte Gesamtmenge ändern',
  'replacement': 'Zusätzliche Ersatzlieferung vereinbart',
  'cancel_remaining': 'Offene Restlieferung storniert',
};
bool _id(Object? value) => RegExp(r'^[a-f0-9]{32}$').hasMatch('$value');
bool _hash(Object? value) => RegExp(r'^[a-f0-9]{64}$').hasMatch('$value');
String _hex(List<int> bytes) =>
    bytes.map((value) => value.toRadixString(16).padLeft(2, '0')).join();
Object? _sort(Object? value) {
  if (value is Map) {
    final keys = value.keys.map((key) => '$key').toList()..sort();
    return {for (final key in keys) key: _sort(value[key])};
  }
  if (value is List) return value.map(_sort).toList();
  return value;
}

bool _same(Object? first, Object? second) =>
    jsonEncode(_sort(first)) == jsonEncode(_sort(second));
String purchaseChangeQuantity(Object? raw, {bool positive = false}) {
  final value = '${raw ?? ''}'.trim().replaceAll(',', '.');
  if (!RegExp(r'^\d{1,18}(?:\.\d{1,4})?$').hasMatch(value))
    throw const FormatException(
      'Mengen benötigen eine nicht negative Dezimalzahl mit höchstens vier Nachkommastellen. Es wird nicht gerundet.',
    );
  final parts = value.split('.'),
      units =
          BigInt.parse(parts[0]) * BigInt.from(10000) +
          BigInt.parse((parts.length == 1 ? '' : parts[1]).padRight(4, '0'));
  if (positive && units == BigInt.zero)
    throw const FormatException(
      'Tatsächliche Rücksendemenge muss positiv sein.',
    );
  return '${units ~/ BigInt.from(10000)}.${(units % BigInt.from(10000)).toString().padLeft(4, '0')}';
}

Map<String, dynamic> purchaseChangeBasis(Map<String, dynamic> detail) {
  if (!_id(detail['id']) ||
      detail['order_id'] != detail['id'] ||
      !_hash(detail['source_sha256']) ||
      ![
        'source_revision',
        'receipt_revision',
        'amendment_revision',
        'return_revision',
      ].every((key) => detail[key] is int && detail[key] >= 0) ||
      detail['source_revision'] < 1)
    throw const FormatException(
      'Aktuellen Quellenstand der Bestellung zuerst laden.',
    );
  return {
    'source_revision': detail['source_revision'],
    'expected_receipt_revision': detail['receipt_revision'],
    'expected_amendment_revision': detail['amendment_revision'],
    'expected_return_revision': detail['return_revision'],
    'source_sha256': detail['source_sha256'],
  };
}

Map<String, dynamic> purchaseChangeInput(
  Map<String, dynamic> detail,
  String action,
  Map<String, dynamic> values,
) {
  if ('${values['reference'] ?? ''}'.trim().isEmpty ||
      '${values['reason'] ?? ''}'.trim().isEmpty ||
      !_id(values['evidence_id']))
    throw const FormatException(
      'Referenz, Grund und Original ausdrücklich wählen.',
    );
  final common = {
    ...purchaseChangeBasis(detail),
    'reference': '${values['reference']}'.trim(),
    'reason': '${values['reason']}'.trim(),
    'evidence_id': values['evidence_id'],
  };
  if (action == 'amendments') {
    if (!purchaseChangeKinds.containsKey(values['kind']))
      throw const FormatException('Art der Mengenvereinbarung wählen.');
    return {
      ...common,
      'kind': values['kind'],
      'effective_on': values['effective_on'],
      'lines': [
        for (final line in businessItems(detail['items']))
          {
            'line_index': line['line_index'],
            'authorized_quantity': purchaseChangeQuantity(
              values['quantity_${line['line_index']}'],
            ),
          },
      ],
    };
  }
  if (action != 'supplier-returns')
    throw const FormatException('Unbekannte Einkaufsaktion.');
  final lines = <Map<String, dynamic>>[];
  for (final receipt in businessItems(detail['receipts'])) {
    for (final line in businessItems(receipt['lines'])) {
      final raw = values['quantity_${receipt['id']}_${line['line_index']}'];
      if (raw == null || '$raw'.trim().isEmpty) continue;
      final quantity = purchaseChangeQuantity(raw);
      if (quantity == '0.0000') continue;
      lines.add({
        'receipt_id': receipt['id'],
        'line_index': line['line_index'],
        'quantity': quantity,
      });
    }
  }
  if (lines.isEmpty)
    throw const FormatException(
      'Tatsächliche Rücksendemenge einer konkreten Lieferposition angeben.',
    );
  return {...common, 'returned_on': values['returned_on'], 'lines': lines};
}

bool _priceKeys(Object? value) {
  if (value is List) return value.any(_priceKeys);
  if (value is Map)
    return value.entries.any(
      (entry) => '${entry.key}'.endsWith('_net') || _priceKeys(entry.value),
    );
  return false;
}

Map<String, dynamic> purchaseChangePreview(
  Map<String, dynamic> detail,
  String action,
  Map<String, dynamic> body,
  dynamic result,
) {
  final value = businessMap(result);
  if (value['order_id'] != detail['id'] ||
      value['action'] != action ||
      value['source_sha256'] != body['source_sha256'] ||
      !_hash(value['preview_sha256']) ||
      !_same(value['values'], body) ||
      value['lines'] is! List ||
      (value['lines'] as List).length != (body['lines'] as List).length ||
      value['financial_values_visible'] is! bool ||
      value['financial_values_visible'] == false && _priceKeys(value))
    throw const ApiException(
      0,
      'Vorschau bestätigt ursprünglichen Auftrag und Quellen nicht.',
    );
  return value;
}

Map<String, dynamic> purchaseChangeReceipt(
  String orderId,
  String action,
  Map<String, dynamic> body,
  Map<String, dynamic>? preview,
  dynamic result,
) {
  final value = businessMap(result),
      order = businessMap(value['order']),
      record = businessMap(value['record']),
      amend = action == 'amendments';
  if (order['id'] != orderId ||
      order['order_id'] != orderId ||
      !_id(record['id']) ||
      record['order_id'] != orderId ||
      record['project_id'] != order['project_id'] ||
      record['source_sha256'] != body['source_sha256'] ||
      record['preview_sha256'] != body['preview_sha256'] ||
      value['financial_values_visible'] is! bool ||
      value['financial_values_visible'] == false && _priceKeys(value))
    throw const ApiException(
      0,
      'Quittung gehört nicht zum ursprünglichen Bestellauftrag.',
    );
  if (record['revision'] !=
          (amend
                  ? body['expected_amendment_revision']
                  : body['expected_return_revision']) +
              1 ||
      record['source_revision'] != body['source_revision'] ||
      record['receipt_revision'] != body['expected_receipt_revision'] ||
      record['amendment_revision'] != body['expected_amendment_revision'] ||
      record['return_revision'] != body['expected_return_revision'] ||
      [
        'reference',
        'reason',
        'evidence_id',
        amend ? 'effective_on' : 'returned_on',
        if (amend) 'kind',
      ].any((key) => record[key] != body[key]) ||
      !_hash(record['evidence_sha256']))
    throw const ApiException(
      0,
      'Gespeicherte Fassung bestätigt die ursprüngliche Entscheidung nicht.',
    );
  if (preview != null) {
    final keys = amend
        ? [
            'line_index',
            'article_id',
            'article_name',
            'unit',
            'received_quantity',
            'previous_authorized_quantity',
            'authorized_quantity',
            'remaining_quantity',
          ]
        : [
            'receipt_id',
            'line_index',
            'article_id',
            'article_name',
            'unit',
            'location_id',
            'quantity',
            'received_quantity',
            'returned_quantity',
            'bound_quantity',
            'returnable_quantity',
            'free_quantity',
            'stock_quantity',
          ];
    List<Map<String, dynamic>> select(Object? lines) => [
      for (final line in businessItems(lines ?? const []))
        {for (final key in keys) key: line[key]},
    ];
    if (!_same(select(record['lines']), select(preview['lines'])))
      throw const ApiException(
        0,
        'Gespeicherte Mengen bestätigen die Vorschau nicht.',
      );
  }
  return value;
}

class BusinessPurchaseChangesPage extends StatefulWidget {
  const BusinessPurchaseChangesPage({
    super.key,
    required this.session,
    required this.orderId,
    this.pickFile,
    this.exporter,
  });
  final BusinessSession session;
  final String orderId;
  final Future<XFile?> Function()? pickFile;
  final MailAttachmentExporter? exporter;
  @override
  State<BusinessPurchaseChangesPage> createState() =>
      _BusinessPurchaseChangesPageState();
}

class _BusinessPurchaseChangesPageState
    extends State<BusinessPurchaseChangesPage> {
  BusinessSession get session => widget.session;
  BusinessSession? scope;
  Map<String, dynamic>? detail;
  String? error;
  bool loading = false;
  int epoch = 0;
  Object? generation;
  Set<String> rights = {};
  bool get available =>
      session.allowed &&
      session.hasFeature('purchase_changes') &&
      session.hasModule('purchase_changes') &&
      session.can('inventory.read');
  bool get readable =>
      available && scope?.can('inventory.read') == true && scope?.error == null;
  bool get prices => readable && scope!.can('finance.read');
  bool write(String action) =>
      readable &&
      scope!.canWrite('inventory.write') &&
      scope!.canWrite(
        action == 'amendments' ? 'finance.approve' : 'finance.write',
      ) &&
      scope!.sectionEnabled('material');
  String get base => '/purchasing/orders/${widget.orderId}';
  @override
  void initState() {
    super.initState();
    generation = session.generation;
    session.addListener(changed);
    load();
  }

  @override
  void dispose() {
    epoch++;
    session.removeListener(changed);
    if (scope != null && !identical(scope, session))
      scope!.removeListener(changed);
    super.dispose();
  }

  void changed() {
    if (!mounted) return;
    if (!available ||
        session.generation != generation ||
        scope != null && !scope!.permissions.containsAll(rights)) {
      epoch++;
      detail = null;
      loading = false;
    }
    generation = session.generation;
    rights = Set.of(scope?.permissions ?? {});
    setState(() {});
  }

  void guard({String? action}) {
    if (!mounted || !readable || action != null && !write(action))
      throw const ApiException(
        403,
        'Aktuelle Bestell-, Material- oder Finanzfreigabe fehlt.',
      );
  }

  Future<void> attempt(Future<void> Function() fn) async {
    try {
      await fn();
    } catch (value) {
      if (mounted) setState(() => error = '$value');
    }
  }

  Future<Map<String, dynamic>> get(String path) async {
    if (!available) throw const ApiException(403, 'Einkaufszugang fehlt.');
    final captured = epoch;
    try {
      final value = businessMap(await session.read(path));
      if (!mounted || captured != epoch || !available)
        throw const ApiException(0, 'Sitzung oder Auswahl geändert.');
      return value;
    } on ApiException catch (value) {
      if ([401, 403, 404].contains(value.status) && mounted)
        setState(() => detail = null);
      rethrow;
    }
  }

  Future<void> load() async {
    if (!available) return;
    final captured = ++epoch;
    setState(() {
      loading = true;
      error = null;
    });
    try {
      final value = await get('$base/changes');
      purchaseChangeBasis(value);
      if (value['id'] != widget.orderId)
        throw const ApiException(0, 'Falsche Bestellung.');
      final next = value['project_id'] == null
          ? session.sharedGlobalSession()
          : session.sharedProjectSession(value['project_id']);
      if (scope != null &&
          !identical(scope, next) &&
          !identical(scope, session))
        scope!.removeListener(changed);
      if (!identical(next, scope) && !identical(next, session))
        next.addListener(changed);
      scope = next;
      await next.load();
      guard();
      if (mounted && captured == epoch) setState(() => detail = value);
    } catch (value) {
      if (mounted && captured == epoch) setState(() => error = '$value');
    } finally {
      if (mounted && captured == epoch) setState(() => loading = false);
    }
  }

  List<Map<String, dynamic>> items(Object? value) =>
      businessItems(value ?? const []);
  String amount(Object? value) =>
      '${value ?? 'Nicht freigegeben'}'.replaceAll('.', ',');
  Future<void> prepare(String action) async {
    guard(action: action);
    final item = detail!, key = 'purchase-change-$action-${widget.orderId}';
    if (session.pending(key)) {
      await pending(action);
      return;
    }
    Map<String, dynamic>? body, preview;
    final captured = epoch, amend = action == 'amendments';
    await showDialog<bool>(
      context: context,
      builder: (_) => BusinessEditor(
        session: scope!,
        title: amend
            ? 'Belegte Mengenänderung vorbereiten'
            : 'Tatsächliche Lieferantenretoure vorbereiten',
        readAllowed: () => readable && captured == epoch,
        readPermission: 'inventory.read',
        writePermission: amend ? 'finance.approve' : 'finance.write',
        saveLabel: 'Aktuelle Mengen und Quellen prüfen',
        fields: [
          BusinessField(
            'reference',
            amend
                ? 'Externe Änderungsreferenz'
                : 'Tatsächliche Rücksendereferenz',
            required: true,
          ),
          BusinessField(
            amend ? 'effective_on' : 'returned_on',
            amend
                ? 'Datum der vereinbarten Änderung'
                : 'Tatsächliches Rücksendedatum',
            type: BusinessInput.date,
            required: true,
          ),
          const BusinessField(
            'reason',
            'Tatsächlicher Grund',
            type: BusinessInput.multiline,
            required: true,
          ),
          BusinessField(
            'evidence_id',
            'Unveränderliches Original dieser Bestellung',
            type: BusinessInput.choice,
            choices: {
              '': 'Bitte auswählen',
              for (final file in items(item['files']))
                '${file['id']}': '${file['filename']}',
            },
            initial: '',
            required: true,
          ),
          if (amend) ...[
            const BusinessField(
              'kind',
              'Art der Mengenvereinbarung',
              type: BusinessInput.choice,
              choices: purchaseChangeKinds,
              initial: 'quantity_change',
            ),
            for (final line in items(item['items']))
              BusinessField(
                'quantity_${line['line_index']}',
                'Pos. ${line['line_index'] + 1} · Neue kumulierte Gesamtliefermenge (${line['unit']})',
                type: BusinessInput.decimal,
                initial: line['authorized_quantity'],
                required: true,
                hint:
                    '${line['article_name']} · brutto empfangen ${amount(line['received_quantity'])}; Reststornierung exakt auf diese Menge.',
              ),
          ] else
            for (final receipt in items(item['receipts'])) ...[
              for (final line in items(receipt['lines']))
                BusinessField(
                  'quantity_${receipt['id']}_${line['line_index']}',
                  '${receipt['receipt_reference']} · Pos. ${line['line_index'] + 1} · Tatsächlich zurück (${line['unit']})',
                  type: BusinessInput.decimal,
                  omitIfEmpty: true,
                  hint:
                      '${line['article_name']} · Eingang ${amount(line['quantity'])} · retourniert ${amount(line['returned_quantity'])} · gerätegebunden ${amount(line['bound_quantity'])} · Herkunftskapazität ${amount(line['returnable_quantity'])} · frei ${amount(line['free_quantity'])}',
                ),
            ],
        ],
        onSave: (values) async {
          guard(action: action);
          body = purchaseChangeInput(item, action, values);
          final result = await session.api.call(
            session.path('$base/$action/preview'),
            body,
          );
          guard(action: action);
          if (captured != epoch)
            throw const ApiException(0, 'Sitzung während Vorschau geändert.');
          preview = purchaseChangePreview(item, action, body!, result);
        },
      ),
    );
    if (body != null && preview != null && mounted && captured == epoch)
      await confirm(action, body!, preview!);
  }

  Future<void> confirm(
    String action,
    Map<String, dynamic> body,
    Map<String, dynamic> preview,
  ) async {
    guard(action: action);
    final key = 'purchase-change-$action-${widget.orderId}',
        captured = epoch,
        amend = action == 'amendments';
    await showDialog<bool>(
      context: context,
      barrierDismissible: false,
      builder: (_) => _PurchaseChangeConfirmation(
        session: session,
        scope: scope!,
        pendingKey: key,
        readAllowed: () => readable && captured == epoch,
        writeAllowed: () => write(action),
        replayAllowed: () =>
            readable &&
            scope!.canWrite('inventory.write') &&
            scope!.canWrite(amend ? 'finance.approve' : 'finance.write'),
        confirmation: amend
            ? 'Ich bestätige die belegte externe Mengenvereinbarung genau dieser Positionen.'
            : 'Ich bestätige die tatsächliche physische Rücksendung dieser konkreten Lieferpositionen.',
        submit: amend
            ? 'Mengenvereinbarung verbindlich dokumentieren'
            : 'Physische Rücksendung verbindlich buchen',
        details: () => [
          Text('Originalreferenz: ${body['reference']}'),
          Text('${body['reason']}'),
          ...lineWidgets(
            action,
            items(preview['lines']),
            prices && preview['financial_values_visible'] == true,
          ),
          if (!amend && prices && preview['financial_values_visible'] == true)
            Text(
              'Auszubuchender Lagerwert netto: ${amount(preview['total_book_value_net'])} EUR',
            ),
          const Notice(
            'Die Bestätigung erzeugt keine Lieferantenkommunikation, Gutschrift, Erstattung oder Zahlung.',
          ),
        ],
        onConfirm: () async {
          guard();
          if (session.pending(key)) {
            await session.repeatPurchaseChangeCommand(key);
            return;
          }
          guard(action: action);
          final command = {
            ...body,
            'preview_sha256': preview['preview_sha256'],
            'confirmation': true,
          };
          await session.command(
            key,
            '$base/$action',
            command,
            validateResult: (value) => purchaseChangeReceipt(
              widget.orderId,
              action,
              command,
              preview,
              value,
            ),
          );
        },
      ),
    );
    if (mounted) await load();
  }

  Future<void> pending(String action) async {
    guard();
    final key = action == 'change-files'
            ? 'purchase-change-file-${widget.orderId}'
            : 'purchase-change-$action-${widget.orderId}',
        path = '$base/$action';
    final body = session.pendingCommandValues(key, path: path);
    if (body == null) return;
    final captured = epoch;
    await showDialog<bool>(
      context: context,
      barrierDismissible: false,
      builder: (_) => _PurchaseChangeConfirmation(
        session: session,
        scope: scope!,
        pendingKey: key,
        readAllowed: () => readable && captured == epoch,
        writeAllowed: () => false,
        replayAllowed: () =>
            readable &&
            scope!.canWrite('inventory.write') &&
            scope!.canWrite(
              action == 'amendments' ? 'finance.approve' : 'finance.write',
            ),
        confirmation: 'Der ursprüngliche Auftrag bleibt unverändert.',
        submit: 'Ursprüngliche Antwort erneut prüfen',
        details: () => [
          Text('Bestellung: ${detail?['supplier_name']}'),
          if (body['reference'] != null)
            Text('Ursprüngliche Belegreferenz: ${body['reference']}'),
          if (body['filename'] != null)
            Text('Unverändertes Original: ${body['filename']}'),
          if (body['reason'] != null) Text('Grund: ${body['reason']}'),
          if (body['kind'] != null)
            Text('Vereinbarung: ${purchaseChangeKinds[body['kind']]}'),
          if (body['effective_on'] != null || body['returned_on'] != null)
            Text(
              'Tatsächliches Datum: ${businessDate(body['effective_on'] ?? body['returned_on'])}',
            ),
          for (final line in items(body['lines']))
            Text(
              'Position ${line['line_index'] + 1}${line['receipt_id'] == null ? '' : ' · Lieferung ${line['receipt_id']}'}: ${amount(line['authorized_quantity'] ?? line['quantity'])}',
            ),
          const Notice(
            'Dieser unveränderte Auftrag wird mit aktuellen Rechten geprüft. Es wird keine neue Vorschau unter derselben Anfrage-ID erzeugt.',
          ),
        ],
        onConfirm: () async {
          guard();
          await session.repeatPurchaseChangeCommand(key);
        },
      ),
    );
    if (mounted) await load();
  }

  Future<void> upload() async {
    guard(action: 'change-files');
    const action = 'change-files';
    final key = 'purchase-change-file-${widget.orderId}',
        path = '$base/$action';
    if (session.pending(key)) {
      await pending(action);
      return;
    }
    final captured = epoch,
        file = await (widget.pickFile?.call() ?? openFile());
    if (file == null) return;
    guard(action: action);
    final size = await file.length();
    if (size < 1 || size > 2097152)
      throw const ApiException(413, 'Originaldatei bis 2 MiB wählen.');
    final bytes = await file.readAsBytes(),
        media = const {
          'pdf': 'application/pdf',
          'png': 'image/png',
          'jpg': 'image/jpeg',
          'jpeg': 'image/jpeg',
          'xml': 'application/xml',
        }[file.name.split('.').last.toLowerCase()];
    if (media == null || bytes.length != size || captured != epoch)
      throw const ApiException(0, 'Originaldatei oder Sitzung ungültig.');
    final digest = _hex((await Sha256().hash(bytes)).bytes),
        body = {
          'filename': file.name,
          'media_type': media,
          'content_base64': base64Encode(bytes),
        };
    if (!mounted) return;
    await showDialog<bool>(
      context: context,
      barrierDismissible: false,
      builder: (_) => BusinessEditor(
        session: scope!,
        pendingSession: session,
        pendingKey: key,
        title: 'Original unverändert speichern: ${file.name}',
        readAllowed: () => readable && captured == epoch,
        readPermission: 'inventory.read',
        writePermission: 'finance.write',
        fields: const [],
        onSave: (_) async {
          guard();
          if (session.pending(key)) {
            await session.repeatPurchaseChangeCommand(key);
            return;
          }
          guard(action: action);
          await session.command(
            key,
            path,
            body,
            validateResult: (result) {
              final value = businessMap(result);
              if (!_id(value['id']) ||
                  value['order_id'] != widget.orderId ||
                  value['filename'] != file.name ||
                  value['sha256'] != digest ||
                  value['size'] != size)
                throw const ApiException(
                  0,
                  'Original wurde nicht unverändert bestätigt.',
                );
            },
          );
        },
      ),
    );
    if (mounted) await load();
  }

  Future<void> download(Map<String, dynamic> file) async {
    await load();
    guard();
    if (!prices)
      throw const ApiException(
        403,
        'Originale benötigen aktuelle Finanzleserechte.',
      );
    final captured = epoch,
        bytes = await session.api.bytes(
          session.path('$base/change-files/${file['id']}/original'),
          mediaType: 'application/octet-stream',
          maxBytes: 2097152,
        );
    await scope!.load();
    guard();
    final digest = _hex((await Sha256().hash(bytes)).bytes);
    if (!prices ||
        captured != epoch ||
        bytes.length != file['size'] ||
        digest != file['sha256'])
      throw const ApiException(
        0,
        'Original oder aktuelle Finanzfreigabe stimmen nicht überein.',
      );
    if (!mounted) return;
    await (widget.exporter ?? exportMailAttachment)(
      context,
      VerifiedMailAttachment(
        bytes: bytes,
        filename: file['filename'],
        mediaType: 'application/octet-stream',
        sha256: digest,
      ),
      () => mounted && prices && captured == epoch,
    );
  }

  List<Widget> lineWidgets(
    String action,
    List<Map<String, dynamic>> lines,
    bool financial,
  ) => [
    for (final line in lines)
      Card(
        child: Padding(
          padding: const EdgeInsets.all(12),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                'Pos. ${line['line_index'] + 1} · ${line['article_name']} (${line['unit']})',
              ),
              if (action == 'amendments')
                Text(
                  'Brutto empfangen: ${amount(line['received_quantity'])}\nBisher freigegeben: ${amount(line['previous_authorized_quantity'])}\nNeu freigegeben gesamt: ${amount(line['authorized_quantity'])}\nNoch lieferbar: ${amount(line['remaining_quantity'])}',
                )
              else ...[
                Text(
                  'Lieferung: ${line['receipt_id']}\nTatsächlich zurück: ${amount(line['quantity'])}\nEingegangen: ${amount(line['received_quantity'])} · früher retourniert: ${amount(line['returned_quantity'])}\nGerätegebunden: ${amount(line['bound_quantity'])} · Herkunftskapazität: ${amount(line['returnable_quantity'])}\nFreier Lagerbestand: ${amount(line['free_quantity'])}',
                ),
                if (financial)
                  Text(
                    'Gewichteter Buchwert netto: ${amount(line['book_value_net'])} EUR',
                  ),
              ],
            ],
          ),
        ),
      ),
  ];
  Widget button(String title, Future<void> Function() fn) => OutlinedButton(
    onPressed: loading ? null : () => attempt(fn),
    child: Text(title),
  );
  Widget history(String action, List<Map<String, dynamic>> records) => Column(
    crossAxisAlignment: CrossAxisAlignment.stretch,
    children: [
      Text(
        action == 'amendments'
            ? 'Belegte Mengenänderungen'
            : 'Tatsächliche Lieferantenretouren',
        style: Theme.of(context).textTheme.titleLarge,
      ),
      for (final record in records)
        Card(
          child: Padding(
            padding: const EdgeInsets.all(16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text('${record['reference']} · Fassung ${record['revision']}'),
                Text(
                  '${action == 'amendments' ? purchaseChangeKinds[record['kind']] : 'Physische Rücksendung'} · ${businessDate(record['effective_on'] ?? record['returned_on'])}',
                ),
                Text('${record['reason']}'),
                ...lineWidgets(
                  action,
                  items(record['lines']),
                  prices && detail?['financial_values_visible'] == true,
                ),
                for (final file in items(
                  detail?['files'],
                ).where((file) => file['id'] == record['evidence_id']))
                  if (prices)
                    button('Gebundenes Original', () => download(file)),
              ],
            ),
          ),
        ),
    ],
  );
  @override
  Widget build(BuildContext context) {
    if (!available)
      return const Center(child: Text('Einkaufszugang nicht verfügbar.'));
    final item = detail;
    return Scaffold(
      appBar: AppBar(
        title: Text(
          item == null
              ? 'Bestelländerungen und Retouren'
              : 'Änderungen · ${item['supplier_name']}',
        ),
      ),
      body: ListView(
        padding: const EdgeInsets.all(20),
        children: [
          if (error != null) Notice(error!, error: true),
          if (loading) const LinearProgressIndicator(),
          if (readable && item != null) ...[
            const Notice(
              'Empfangene, zurückgesendete, behaltene und noch freigegebene Mengen bleiben getrennt. Eine Retoure erzeugt weder Ersatzanspruch noch Zahlung oder EÜR-Buchung.',
            ),
            Wrap(
              spacing: 8,
              runSpacing: 8,
              children: [
                if (write('change-files'))
                  button('Änderungs- oder Retourenbeleg hochladen', upload),
                if (item['confirmation'] != null && write('amendments'))
                  button(
                    'Belegte Mengenänderung vorbereiten',
                    () => prepare('amendments'),
                  ),
                if (items(item['receipts']).isNotEmpty &&
                    write('supplier-returns'))
                  button(
                    'Tatsächliche Lieferantenretoure vorbereiten',
                    () => prepare('supplier-returns'),
                  ),
                button('Aktuellen Bestellstand laden', load),
              ],
            ),
            for (final action in [
              'change-files',
              'amendments',
              'supplier-returns',
            ])
              if (session.pending(
                action == 'change-files'
                    ? 'purchase-change-file-${widget.orderId}'
                    : 'purchase-change-$action-${widget.orderId}',
              ))
                button('Offenen Originalauftrag prüfen', () => pending(action)),
            for (final line in items(item['items']))
              Card(
                child: ListTile(
                  title: Text(
                    'Pos. ${line['line_index'] + 1} · ${line['article_name']} (${line['unit']})',
                  ),
                  subtitle: Text(
                    'Ursprünglich ${amount(line['original_ordered_quantity'])} · freigegeben gesamt ${amount(line['authorized_quantity'])}\nBrutto empfangen ${amount(line['received_quantity'])} · retourniert ${amount(line['returned_quantity'])}\nBehalten ${amount(line['retained_quantity'])} · noch lieferbar ${amount(line['remaining_quantity'])}',
                  ),
                ),
              ),
            Text(
              'Unveränderte Änderungs- und Retourenoriginale',
              style: Theme.of(context).textTheme.titleLarge,
            ),
            for (final file in items(item['files']))
              ListTile(
                title: Text('${file['filename']}'),
                subtitle: Text(
                  '${file['size']} Byte · SHA-256 ${file['sha256']}${prices ? '' : '\nOriginalbytes benötigen Finanzleserechte.'}',
                ),
                trailing: prices
                    ? IconButton(
                        onPressed: () => attempt(() => download(file)),
                        icon: const Icon(Icons.download),
                        tooltip: 'Original herunterladen',
                      )
                    : null,
              ),
            history('amendments', items(item['amendments'])),
            history('supplier-returns', items(item['returns'])),
          ],
        ],
      ),
    );
  }
}

class _PurchaseChangeConfirmation extends StatefulWidget {
  const _PurchaseChangeConfirmation({
    required this.session,
    required this.scope,
    required this.pendingKey,
    required this.readAllowed,
    required this.writeAllowed,
    required this.replayAllowed,
    required this.confirmation,
    required this.submit,
    required this.details,
    required this.onConfirm,
  });
  final BusinessSession session, scope;
  final String pendingKey, confirmation, submit;
  final bool Function() readAllowed, writeAllowed, replayAllowed;
  final List<Widget> Function() details;
  final Future<void> Function() onConfirm;
  @override
  State<_PurchaseChangeConfirmation> createState() =>
      _PurchaseChangeConfirmationState();
}

class _PurchaseChangeConfirmationState
    extends State<_PurchaseChangeConfirmation> {
  bool checked = false, busy = false;
  String? error;
  bool get pending => widget.session.pending(widget.pendingKey);
  Future<void> confirm() async {
    if (busy ||
        !widget.readAllowed() ||
        !widget.replayAllowed() ||
        !pending && (!checked || !widget.writeAllowed()))
      return;
    setState(() {
      busy = true;
      error = null;
    });
    try {
      await widget.onConfirm();
      if (mounted) Navigator.pop(context, true);
    } catch (value) {
      if (mounted) setState(() => error = '$value');
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  @override
  Widget build(BuildContext context) => AnimatedBuilder(
    animation: Listenable.merge([widget.session, widget.scope]),
    builder: (context, _) => AlertDialog(
      title: const Text('Geprüfte Vorschau ausdrücklich bestätigen'),
      content: SizedBox(
        width: 750,
        child: SingleChildScrollView(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: !widget.readAllowed()
                ? [const Notice('Quellenzugang geändert. Vorschau neu laden.')]
                : [
                    ...widget.details(),
                    SwitchListTile.adaptive(
                      value: checked,
                      onChanged: busy || pending
                          ? null
                          : (value) => setState(() => checked = value),
                      title: Text(widget.confirmation),
                    ),
                    if (error != null) Notice(error!, error: true),
                    if (pending)
                      const Notice(
                        'Die ursprüngliche Antwort ist offen. Die erneute Prüfung verwendet denselben Auftrag, dieselbe Anfrage-ID und frische Rechte.',
                      ),
                  ],
          ),
        ),
      ),
      actions: [
        TextButton(
          onPressed: busy ? null : () => Navigator.pop(context),
          child: const Text('Schließen'),
        ),
        FilledButton(
          onPressed:
              busy ||
                  !widget.readAllowed() ||
                  !widget.replayAllowed() ||
                  !pending && (!checked || !widget.writeAllowed())
              ? null
              : confirm,
          child: Text(
            pending ? 'Ursprüngliche Antwort erneut prüfen' : widget.submit,
          ),
        ),
      ],
    ),
  );
}

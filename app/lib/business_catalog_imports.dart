import 'dart:convert';
import 'dart:typed_data';

import 'package:cryptography/cryptography.dart';
import 'package:file_selector/file_selector.dart';
import 'package:flutter/material.dart';

import 'api.dart';
import 'business_session.dart';
import 'design.dart';
import 'mail_attachment_widgets.dart';

const catalogProfiles = {
  'catalog_csv_v1': 'Smartplan Artikel-CSV v1',
  'datanorm_a14_cp850_v1': 'DATANORM A/N · 14 Felder · CP850',
};
const _fields = {
  'code': 'Artikelnummer',
  'name': 'Bezeichnung',
  'unit': 'Einheit',
  'cost_price_net': 'Einkauf netto',
  'unit_price_net': 'Verkauf netto',
  'tax_rate': 'USt. %',
  'kind': 'Artikelart',
  'currency': 'Währung',
  'active': 'Aktiv',
  'cost_known': 'Einstand bekannt',
  'tax_category': 'Steuerkategorie',
  'tax_exemption_reason': 'Steuerbefreiungsgrund',
  'pricing_snapshot': 'Gespeicherte Preiskalkulation',
};
bool _id(Object? value) =>
    value is String && RegExp(r'^[a-f0-9]{32}$').hasMatch(value);
bool _hash(Object? value) =>
    value is String && RegExp(r'^[a-f0-9]{64}$').hasMatch(value);
Never _invalid(String message) => throw ApiException(0, message);
Object? _sorted(Object? value) {
  if (value is Map) {
    final keys = value.keys.cast<String>().toList()..sort();
    return {for (final key in keys) key: _sorted(value[key])};
  }
  if (value is List) return value.map(_sorted).toList();
  return value;
}

bool _same(Object? first, Object? second) =>
    jsonEncode(_sorted(first)) == jsonEncode(_sorted(second));
Future<String> _digest(List<int> bytes) async =>
    (await Sha256().hash(bytes)).bytes
        .map((v) => v.toRadixString(16).padLeft(2, '0'))
        .join();

bool catalogReadable(BusinessSession session) =>
    session.projectId == null &&
    session.hasModule('adapters') &&
    session.hasModule('catalog_imports') &&
    session.can('settings.manage') &&
    session.can('finance.read');
bool catalogWritable(BusinessSession session) =>
    catalogReadable(session) &&
    session.canWrite('finance.write') &&
    session.sectionEnabled('documents');

String catalogDecimal(Object? raw) {
  final value = '${raw ?? ''}'.trim().replaceAll(',', '.');
  if (!RegExp(r'^(0|[1-9][0-9]{0,12})(\.[0-9]{1,4})?$').hasMatch(value)) {
    throw const FormatException(
      'Nicht negative Dezimalzahl mit höchstens vier Nachkommastellen erforderlich.',
    );
  }
  return value;
}

BigInt _scaled(Object? value) {
  final parts = catalogDecimal(value).split('.');
  return BigInt.parse(parts[0]) * BigInt.from(10000) +
      BigInt.parse((parts.length == 1 ? '' : parts[1]).padRight(4, '0'));
}

String catalogDatanormPrice(Map<String, dynamic> item, Object? scale) {
  if (!RegExp(r'^\d{1,14}$')
          .hasMatch('${item['source_price_integer'] ?? ''}') ||
      !const ['1', '10', '100', '1000'].contains(item['price_basis']) ||
      _scaled(scale) <= BigInt.zero) {
    throw const FormatException(
      'Rohpreis, Preisbasis und positive Skalierung prüfen.',
    );
  }
  final basis = BigInt.parse(item['price_basis']),
      numerator = BigInt.parse(item['source_price_integer']) * _scaled(scale),
      result = (numerator + basis ~/ BigInt.two) ~/ basis;
  return '${result ~/ BigInt.from(10000)}.${(result % BigInt.from(10000)).toString().padLeft(4, '0')}';
}

Map<String, dynamic> catalogRun(
  dynamic raw, {
  required String adapterId,
  String? runId,
  String? sourceHash,
}) {
  final value = businessMap(raw);
  if (!_id(value['id']) ||
      value['adapter_id'] != adapterId ||
      runId != null && value['id'] != runId ||
      !_hash(value['source_sha256']) ||
      sourceHash != null && value['source_sha256'] != sourceHash ||
      !catalogProfiles.containsKey(value['profile']) ||
      !const ['staged', 'applied'].contains(value['status']) ||
      value['result'] is! Map ||
      value['rows'] is! List ||
      (value['rows'] as List).isEmpty ||
      (value['rows'] as List).length > 2000) {
    _invalid(
      'Importantwort ist nicht vollständig an die Originaldatei gebunden.',
    );
  }
  final codes = <String>{};
  for (final row in businessItems(value['rows'])) {
    if (row['code'] is! String ||
        (row['code'] as String).isEmpty ||
        !codes.add(row['code']) ||
        row['name'] is! String ||
        row['unit'] is! String)
      _invalid('Importpositionen sind unvollständig oder doppelt.');
    if (value['profile'] == 'catalog_csv_v1') {
      for (final key in ['cost_price_net', 'unit_price_net', 'tax_rate']) {
        if (row[key] is! String)
          _invalid(
            'Originalpreise müssen unveränderte Dezimalzeichenfolgen sein.',
          );
        try {
          catalogDecimal(row[key]);
        } on FormatException {
          _invalid('Originalpreis ist ungültig.');
        }
      }
    }
  }
  final original = businessMap(value['original']);
  if (original['available'] != true && original['available'] != false)
    _invalid('Originalnachweis fehlt in der Importantwort.');
  if (original['available'] == true &&
      (original['sha256'] != value['source_sha256'] ||
          original['filename'] is! String ||
          original['size'] is! int ||
          original['size'] <= 0 ||
          original['size'] > 2097152)) {
    _invalid('Originaldatei und Importnachweis stimmen nicht überein.');
  }
  return value;
}

Future<Map<String, dynamic>> catalogPreview(
  Map<String, dynamic> run,
  Map<String, dynamic> mapping,
  dynamic raw,
) async {
  final value = businessMap(raw), rows = businessItems(value['rows']);
  if (value['run_id'] != run['id'] ||
      value['source_sha256'] != run['source_sha256'] ||
      value['profile'] != run['profile'] ||
      !_same(value['price_mapping'], mapping) ||
      !_hash(value['preview_sha256']) ||
      rows.length != (run['rows'] as List).length) {
    _invalid('Vorschau gehört nicht zu Originaldatei und Preiszuordnung.');
  }
  final unsigned = Map<String, dynamic>.from(value)..remove('preview_sha256');
  if (await _digest(utf8.encode(jsonEncode(_sorted(unsigned)))) !=
      value['preview_sha256']) {
    _invalid(
      'Die Übernahmevorschau hat ihre Integritätsprüfung nicht bestanden.',
    );
  }
  for (var index = 0; index < rows.length; index++) {
    final item = rows[index],
        source = businessMap(run['rows'][index]),
        expected = businessMap(
          businessMap(run['result'])['target_revisions'],
        )[source['code']],
        before = item['before'] == null ? null : businessMap(item['before']),
        after = businessMap(item['after']);
    if (item['code'] != source['code'] ||
        !const ['create', 'update', 'noop'].contains(item['action']) ||
        (expected != null) != (item['action'] != 'create') ||
        expected != null &&
            (item['article_id'] != expected['article_id'] ||
                item['revision'] != expected['revision'] ||
                before == null) ||
        expected == null &&
            (item['article_id'] != null ||
                item['revision'] != null ||
                before != null) ||
        item['action'] == 'noop' && !_same(before, after))
      _invalid('Artikelzuordnung oder unveränderte Übernahme stimmt nicht.');
    if (['code', 'name', 'unit'].any((key) => after[key] != source[key]) ||
        after['kind'] != 'material' ||
        after['currency'] != 'EUR' ||
        after['active'] != true)
      _invalid('Vorschau verändert die Originalposition.');
    if (run['profile'] == 'catalog_csv_v1') {
      if ([
        'cost_price_net',
        'unit_price_net',
        'tax_rate',
      ].any((key) => _scaled(after[key]) != _scaled(source[key])))
        _invalid('Vorschau verändert die Originalpreise.');
    } else {
      if (!const [
            'purchase_net',
            'sales_net',
          ].contains(mapping['target_price']) ||
          source['discount_group'] != '' ||
          source['long_text_key'] != '')
        _invalid('Diese DATANORM-Zuordnung wird nicht unterstützt.');
      final field = mapping['target_price'] == 'purchase_net'
              ? 'cost_price_net'
              : 'unit_price_net',
          other = field == 'cost_price_net'
              ? 'unit_price_net'
              : 'cost_price_net';
      if (_scaled(after[field]) !=
              _scaled(catalogDatanormPrice(source, mapping['price_scale'])) ||
          _scaled(after[other]) != _scaled(before?[other] ?? '0') ||
          _scaled(after['tax_rate']) != _scaled(mapping['tax_rate'])) {
        _invalid(
          'Vorschau weicht von der ausdrücklich gewählten Preiszuordnung ab.',
        );
      }
    }
  }
  return value;
}

class BusinessCatalogImportsPage extends StatefulWidget {
  const BusinessCatalogImportsPage({
    super.key,
    required this.session,
    required this.adapter,
    this.picker,
    this.exporter,
  });
  final BusinessSession session;
  final Map<String, dynamic> adapter;
  final Future<XFile?> Function()? picker;
  final MailAttachmentExporter? exporter;
  @override
  State<BusinessCatalogImportsPage> createState() =>
      _BusinessCatalogImportsPageState();
}

class _BusinessCatalogImportsPageState extends State<BusinessCatalogImportsPage>
    with WidgetsBindingObserver {
  BusinessSession get session => widget.session;
  List<Map<String, dynamic>> history = [];
  Map<String, dynamic>? run, preview;
  final scale = TextEditingController(), tax = TextEditingController();
  String? target, error;
  bool busy = false, confirmed = false, background = false, editing = false;
  int epoch = 0, previewEpoch = 0, offset = 0, total = 0, page = 0;
  Object? generation;
  String get adapterId => '${widget.adapter['id']}';
  bool get readable => catalogReadable(session);
  bool get writable =>
      catalogWritable(session) && widget.adapter['enabled'] == true;
  String get importKey => 'catalog-import-$adapterId';
  bool valid(int captured) =>
      mounted && !background && epoch == captured && readable;
  @override
  void initState() {
    super.initState();
    generation = session.generation;
    session.addListener(changed);
    WidgetsBinding.instance.addObserver(this);
    load();
  }

  @override
  void didUpdateWidget(covariant BusinessCatalogImportsPage oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (!identical(oldWidget.session, session) ||
        oldWidget.adapter['id'] != adapterId) {
      oldWidget.session.removeListener(changed);
      session.addListener(changed);
      generation = session.generation;
      erase();
      load();
    }
  }

  void erase() {
    epoch++;
    previewEpoch++;
    history = [];
    run = null;
    preview = null;
    error = null;
    busy = false;
    confirmed = false;
    editing = false;
    offset = 0;
    total = 0;
    page = 0;
    target = null;
    scale.clear();
    tax.clear();
  }

  void changed() {
    if (!mounted) return;
    if (generation != session.generation || !readable || editing && !writable)
      erase();
    generation = session.generation;
    setState(() {});
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (!mounted) return;
    background = state != AppLifecycleState.resumed;
    if (background) erase();
    setState(() {});
  }

  @override
  void dispose() {
    epoch++;
    session.removeListener(changed);
    WidgetsBinding.instance.removeObserver(this);
    scale.dispose();
    tax.dispose();
    super.dispose();
  }

  Future<void> fresh(int captured, {bool write = false}) async {
    if (!valid(captured))
      throw const ApiException(0, 'Katalogansicht gewechselt.');
    await session.load();
    if (!valid(captured))
      throw const ApiException(0, 'Katalogansicht gewechselt.');
    if (session.error != null || session.loading)
      throw const ApiException(
        0,
        'Aktuelle Freigabe konnte nicht bestätigt werden.',
      );
    if ((write || editing) && !writable) {
      setState(erase);
      throw const ApiException(
        0,
        'Katalogbearbeitung ist nicht mehr freigegeben.',
      );
    }
  }

  Future<void> task(Future<void> Function(int) work) async {
    if (busy || !readable || background) return;
    final captured = epoch;
    setState(() {
      busy = true;
      error = null;
    });
    try {
      await work(captured);
    } catch (value) {
      if (valid(captured)) {
        if (value is ApiException && [401, 403].contains(value.status)) {
          setState(erase);
        } else {
          setState(() => error = '$value');
        }
      }
    } finally {
      if (valid(captured)) setState(() => busy = false);
    }
  }

  Future<void> load() async {
    await task((captured) async {
      await fresh(captured);
      final response = businessMap(
        await session.read(
          '/adapters/$adapterId/imports?offset=$offset&limit=20',
        ),
      );
      await fresh(captured);
      final items = businessItems(response);
      if (response['total'] is! int ||
          response['offset'] != offset ||
          response['limit'] != 20 ||
          items.length > 20 ||
          items.any(
            (item) => !_id(item['id']) || item['adapter_id'] != adapterId,
          ))
        _invalid('Historienantwort ist unvollständig.');
      if (valid(captured))
        setState(() {
          history = items;
          total = response['total'];
        });
    });
  }

  Future<void> chooseFile() async {
    if (!writable) return;
    editing = true;
    await task((captured) async {
      final sourceId = adapterId, sourceProfile = widget.adapter['profile'];
      await fresh(captured, write: true);
      Map<String, dynamic> result;
      if (session.pending(importKey)) {
        result = businessMap(await session.repeatCatalogCommand(importKey));
      } else {
        final file =
            await (widget.picker?.call() ??
                openFile(
                  acceptedTypeGroups: [
                    XTypeGroup(
                      label: 'Katalogoriginal',
                      extensions: widget.adapter['profile'] == 'catalog_csv_v1'
                          ? ['csv']
                          : ['dat', '001', 'txt', 'datanorm'],
                    ),
                  ],
                ));
        if (file == null || !valid(captured)) return;
        final size = await file.length();
        if (!valid(captured)) return;
        if (size <= 0 || size > 2097152)
          throw const ApiException(
            413,
            'Eine Datei zwischen 1 Byte und 2 MiB auswählen.',
          );
        final builder = BytesBuilder(copy: false);
        await for (final part in file.openRead(0, size)) {
          if (!valid(captured)) return;
          builder.add(part);
          if (builder.length > 2097152)
            throw const ApiException(413, 'Datei überschreitet 2 MiB.');
        }
        final bytes = builder.takeBytes();
        if (bytes.length != size || await file.length() != size)
          throw const ApiException(
            0,
            'Dateigröße hat sich beim Lesen geändert.',
          );
        final hash = await _digest(bytes),
            body = {
              'filename': file.name,
              'content_base64': base64Encode(bytes),
            };
        await fresh(captured, write: true);
        result = businessMap(
          await session.command(
            importKey,
            '/adapters/$adapterId/import',
            body,
            validateResult: (value) {
              final checked = catalogRun(
                value,
                adapterId: sourceId,
                sourceHash: hash,
              );
              final original = businessMap(checked['original']);
              if (checked['profile'] != sourceProfile ||
                  original['available'] != true ||
                  original['filename'] != file.name.trim() ||
                  original['size'] != size) {
                _invalid(
                  'Die ursprüngliche Datei wurde nicht vollständig bestätigt.',
                );
              }
            },
          ),
        );
      }
      await fresh(captured, write: true);
      await showRun(result, captured);
    });
  }

  Future<void> openRun(String id) async {
    await task((captured) async {
      await fresh(captured);
      final value = await session.read('/adapters/imports/$id');
      await fresh(captured);
      await showRun(
        catalogRun(value, adapterId: adapterId, runId: id),
        captured,
      );
    });
  }

  Future<void> showRun(dynamic value, int captured) async {
    final selected = catalogRun(value, adapterId: adapterId);
    if (!valid(captured)) return;
    final pending = session.pendingCommandValues(
      'catalog-apply-${selected['id']}',
      path: '/adapters/imports/${selected['id']}/apply',
    );
    setState(() {
      run = selected;
      preview = null;
      confirmed = false;
      page = 0;
      error = null;
      editing = selected['status'] == 'staged' && writable;
      target = pending?['target_price'];
      scale.text = '${pending?['price_scale'] ?? ''}';
      tax.text = '${pending?['tax_rate'] ?? ''}';
      previewEpoch++;
    });
    if (selected['status'] == 'staged' &&
        (selected['profile'] == 'catalog_csv_v1' || pending != null))
      await calculate(captured);
  }

  Map<String, dynamic> mapping() {
    if (run?['profile'] == 'catalog_csv_v1') return {};
    if (!const ['purchase_net', 'sales_net'].contains(target) ||
        _scaled(scale.text) <= BigInt.zero ||
        _scaled(tax.text) > BigInt.from(1000000)) {
      throw const FormatException(
        'Preisziel, positive Skalierung und Steuersatz bis 100 ausdrücklich angeben.',
      );
    }
    return {
      'price_scale': catalogDecimal(scale.text),
      'target_price': target,
      'tax_rate': catalogDecimal(tax.text),
    };
  }

  void mappingChanged() {
    setState(() {
      previewEpoch++;
      preview = null;
      confirmed = false;
      error = null;
    });
  }

  Future<void> calculate(int captured) async {
    final selected = run;
    if (selected == null || selected['status'] != 'staged') return;
    final current = ++previewEpoch, body = mapping();
    setState(() {
      preview = null;
      confirmed = false;
    });
    await fresh(captured);
    final raw = await session.api.call(
      session.path('/adapters/imports/${selected['id']}/catalog-preview'),
      body,
    );
    if (!valid(captured) || current != previewEpoch) return;
    await fresh(captured);
    final checked = await catalogPreview(selected, body, raw);
    if (valid(captured) && current == previewEpoch && _same(mapping(), body))
      setState(() => preview = checked);
  }

  Future<void> accept() async {
    if (!writable || run == null) return;
    editing = true;
    await task((captured) async {
      final selected = run!, key = 'catalog-apply-${run!['id']}';
      await fresh(captured, write: true);
      dynamic result;
      if (session.pending(key)) {
        result = await session.repeatCatalogCommand(key);
      } else {
        if (preview == null ||
            !confirmed ||
            !_same(preview!['price_mapping'], mapping()))
          throw const FormatException(
            'Aktuelle vollständige Vorschau prüfen und ausdrücklich bestätigen.',
          );
        result = await session.command(
          key,
          '/adapters/imports/${selected['id']}/apply',
          {'confirmed': true, ...mapping()},
          validateResult: (raw) {
            final value = catalogRun(
              raw,
              adapterId: selected['adapter_id'],
              runId: selected['id'],
              sourceHash: selected['source_sha256'],
            );
            if (value['status'] != 'applied' ||
                businessMap(value['result'])['article_ids'] is! List ||
                (value['result']['article_ids'] as List).length !=
                    (selected['rows'] as List).length)
              _invalid('Die Übernahme wurde nicht vollständig bestätigt.');
          },
        );
      }
      await fresh(captured, write: true);
      await showRun(result, captured);
    });
  }

  Future<void> download() async {
    await task((captured) async {
      final selected = run!, original = businessMap(run!['original']);
      await fresh(captured);
      final bytes = await session.api.bytes(
        session.path('/adapters/imports/${selected['id']}/original'),
        mediaType: 'application/octet-stream',
        maxBytes: 2097152,
      );
      final hash = await _digest(bytes);
      await fresh(captured);
      if (hash != selected['source_sha256'] ||
          hash != original['sha256'] ||
          bytes.length != original['size'])
        _invalid(
          'Originaldatei und gespeicherter Import stimmen nicht überein.',
        );
      if (!valid(captured)) return;
      await (widget.exporter ?? exportMailAttachment)(
        context,
        VerifiedMailAttachment(
          bytes: bytes,
          filename: original['filename'],
          mediaType: 'application/octet-stream',
          sha256: hash,
        ),
        () => valid(captured) && (!editing || writable),
      );
    });
  }

  String shown(String key, Object? value) {
    if (key == 'pricing_snapshot') return value == null ? 'Nein' : 'Ja';
    if (value is bool) return value ? 'Ja' : 'Nein';
    if (value == null || value == '') return '—';
    return const {
          'material': 'Material',
          'service': 'Leistung',
          'labor': 'Arbeit',
          'machine': 'Maschine',
        }[value] ??
        '$value';
  }

  List<Widget> positions() {
    final rows = preview == null
        ? businessItems(run!['rows'])
        : businessItems(preview!['rows']);
    return [
      for (final item in rows.skip(page * 50).take(50))
        Card(
          child: Padding(
            padding: const EdgeInsets.all(16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  '${item['code']} · ${preview == null ? item['name'] : item['after']['name']}',
                  style: Theme.of(context).textTheme.titleMedium,
                ),
                if (preview != null) ...[
                  Text(
                    const {
                      'create': 'Neuer Artikel',
                      'update': 'Artikel wird aktualisiert',
                      'noop': 'Ohne erneute Artikeländerung',
                    }[item['action']]!,
                  ),
                  for (final field in _fields.entries)
                    Text(
                      '${field.value}: ${shown(field.key, businessMap(item['before'])[field.key])} → ${shown(field.key, businessMap(item['after'])[field.key])}',
                    ),
                ] else if (run!['profile'] == 'catalog_csv_v1') ...[
                  Text('Einheit: ${item['unit']}'),
                  Text('Einkauf netto: ${item['cost_price_net']}'),
                  Text('Verkauf netto: ${item['unit_price_net']}'),
                  Text('USt. %: ${item['tax_rate']}'),
                ] else
                  Text(
                    'Einheit: ${item['unit']} · Rohpreis: ${item['source_price_integer']} · Preisbasis: ${item['price_basis']} · Kennzeichen: ${item['price_flag']}',
                  ),
              ],
            ),
          ),
        ),
      Text(
        'Artikel ${page * 50 + 1}–${(page + 1) * 50 > rows.length ? rows.length : (page + 1) * 50} von ${rows.length}',
      ),
      Wrap(
        spacing: 12,
        children: [
          if (page > 0)
            OutlinedButton(
              onPressed: () => setState(() => page--),
              child: const Text('Vorige Artikel'),
            ),
          if ((page + 1) * 50 < rows.length)
            OutlinedButton(
              onPressed: () => setState(() => page++),
              child: const Text('Weitere Artikel'),
            ),
        ],
      ),
    ];
  }

  @override
  Widget build(BuildContext context) {
    if (!readable || background)
      return Scaffold(
        appBar: AppBar(title: const Text('Katalogimporte')),
        body: const Center(
          child: Text('Katalogansicht derzeit nicht freigegeben.'),
        ),
      );
    final selected = run,
        pendingApply =
            selected != null &&
            session.pending('catalog-apply-${selected['id']}');
    return Scaffold(
      appBar: AppBar(title: Text('Katalog · ${widget.adapter['name']}')),
      body: ListView(
        padding: const EdgeInsets.all(20),
        children: [
          Text(
            catalogProfiles[widget.adapter['profile']] ?? '',
            style: Theme.of(context).textTheme.titleLarge,
          ),
          const Notice(
            'Lokale Dateiimporte ohne Lieferantenkontakt. Preise erhalten keine automatisch angenommene zeitliche Gültigkeit. Gleiche Artikelnummern anderer Quellen werden nicht automatisch verbunden.',
          ),
          if (error != null) Notice(error!, error: true),
          if (busy) const LinearProgressIndicator(),
          if (selected == null) ...[
            if (writable)
              FilledButton(
                onPressed: busy ? null : chooseFile,
                child: Text(
                  session.pending(importKey)
                      ? 'Ursprüngliche Importantwort erneut prüfen'
                      : 'Katalogdatei auswählen',
                ),
              ),
            OutlinedButton(
              onPressed: busy ? null : load,
              child: const Text('Historie neu laden'),
            ),
            const SizedBox(height: 16),
            Text(
              'Importhistorie',
              style: Theme.of(context).textTheme.titleLarge,
            ),
            if (history.isEmpty && !busy) const Text('Keine Importe geladen.'),
            for (final item in history)
              Card(
                child: ListTile(
                  title: Text(
                    '${businessMap(item['original'])['filename'] ?? 'Früherer Import ohne Original'}',
                  ),
                  subtitle: Text(
                    '${item['created_at']} · ${item['row_count']} Artikel · ${item['status'] == 'applied' ? 'Übernommen' : 'Zur Prüfung'}',
                  ),
                  trailing: const Icon(Icons.chevron_right),
                  onTap: busy ? null : () => openRun(item['id']),
                ),
              ),
            Wrap(
              spacing: 12,
              children: [
                if (offset > 0)
                  OutlinedButton(
                    onPressed: busy
                        ? null
                        : () {
                            offset -= 20;
                            load();
                          },
                    child: const Text('Neuere Importe'),
                  ),
                if (offset + 20 < total)
                  OutlinedButton(
                    onPressed: busy
                        ? null
                        : () {
                            offset += 20;
                            load();
                          },
                    child: const Text('Ältere Importe'),
                  ),
              ],
            ),
          ] else ...[
            Text(
              '${(selected['rows'] as List).length} Artikel · ${selected['status'] == 'applied' ? 'Bereits übernommen' : 'Noch nicht übernommen'}',
              style: Theme.of(context).textTheme.titleLarge,
            ),
            SelectableText('SHA-256: ${selected['source_sha256']}'),
            if (businessMap(selected['original'])['available'] == true)
              OutlinedButton(
                onPressed: busy ? null : download,
                child: const Text('Original herunterladen'),
              )
            else
              const Notice(
                'Für diesen früheren Import wurde keine Originaldatei gespeichert.',
              ),
            if (selected['status'] == 'staged') ...[
              if (selected['profile'] == 'datanorm_a14_cp850_v1') ...[
                const Notice(
                  'Begrenztes DATANORM-Profil. Preisziel, Rohpreisskalierung und Steuersatz ausdrücklich wählen. Rabatt-/Langtextverweise werden nicht aufgelöst.',
                ),
                DropdownButtonFormField<String>(
                  initialValue: target,
                  decoration: const InputDecoration(
                    labelText: 'Nettopreisziel',
                  ),
                  items: const [
                    DropdownMenuItem(
                      value: 'purchase_net',
                      child: Text('Einkauf netto'),
                    ),
                    DropdownMenuItem(
                      value: 'sales_net',
                      child: Text('Verkauf netto'),
                    ),
                  ],
                  onChanged: pendingApply
                      ? null
                      : (value) {
                          target = value;
                          mappingChanged();
                        },
                ),
                TextField(
                  controller: scale,
                  enabled: !pendingApply,
                  decoration: const InputDecoration(
                    labelText: 'Rohpreisskalierung',
                    hintText: 'Zum Beispiel 0,01 laut Dateivertrag',
                  ),
                  keyboardType: const TextInputType.numberWithOptions(
                    decimal: true,
                  ),
                  onChanged: (_) => mappingChanged(),
                ),
                TextField(
                  controller: tax,
                  enabled: !pendingApply,
                  decoration: const InputDecoration(
                    labelText: 'Umsatzsteuersatz',
                  ),
                  keyboardType: const TextInputType.numberWithOptions(
                    decimal: true,
                  ),
                  onChanged: (_) => mappingChanged(),
                ),
                OutlinedButton(
                  onPressed: busy ? null : () => task(calculate),
                  child: const Text('Verbindliche Vorschau laden'),
                ),
              ],
              if (preview != null)
                Text(
                  '${businessItems(preview!['rows']).where((r) => r['action'] == 'create').length} neu · ${businessItems(preview!['rows']).where((r) => r['action'] == 'update').length} aktualisiert · ${businessItems(preview!['rows']).where((r) => r['action'] == 'noop').length} ohne Änderung',
                ),
              if (writable && !pendingApply)
                CheckboxListTile(
                  value: confirmed,
                  onChanged: busy || preview == null
                      ? null
                      : (value) => setState(() => confirmed = value == true),
                  title: const Text(
                    'Ich bestätige die Originalpositionen und alle angezeigten Änderungen.',
                  ),
                ),
            ],
            if (writable && (selected['status'] == 'staged' || pendingApply))
              FilledButton(
                onPressed: busy ? null : accept,
                child: Text(
                  pendingApply
                      ? 'Ursprüngliche Annahmeantwort erneut prüfen'
                      : 'Artikel ausdrücklich übernehmen',
                ),
              ),
            if (pendingApply)
              const Notice(
                'Eine frühere Annahme ist noch unbestätigt. Die ursprüngliche Eingabe und Vorgangs-ID bleiben für die Wiederholung erhalten.',
              ),
            OutlinedButton(
              onPressed: busy
                  ? null
                  : () {
                      setState(() {
                        run = null;
                        preview = null;
                        confirmed = false;
                        editing = false;
                        previewEpoch++;
                      });
                      load();
                    },
              child: const Text('Zur Importhistorie'),
            ),
            ...positions(),
          ],
        ],
      ),
    );
  }
}

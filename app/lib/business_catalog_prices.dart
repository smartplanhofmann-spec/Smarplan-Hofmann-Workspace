import 'dart:async';
import 'dart:convert';
import 'dart:typed_data';

import 'package:cryptography/cryptography.dart';
import 'package:file_selector/file_selector.dart';
import 'package:flutter/material.dart';

import 'api.dart';
import 'business_session.dart';
import 'business_widgets.dart';
import 'design.dart';
import 'mail_attachment_widgets.dart';

bool catalogPricesAvailable(BusinessSession session) =>
    session.allowed &&
    session.hasFeature('catalog_prices_v2') &&
    session.hasModule('catalog_prices');
bool catalogPricesReadable(BusinessSession session) =>
    catalogPricesAvailable(session) && session.can('finance.read');
bool catalogPricesManageable(BusinessSession session) =>
    catalogPricesReadable(session) &&
    session.projectId == null &&
    session.can('settings.manage');
bool catalogPricesWritable(BusinessSession session) =>
    catalogPricesReadable(session) &&
    session.canWrite('finance.write') &&
    session.sectionEnabled('documents');
bool catalogPriceManaged(Map<String, dynamic> article) =>
    article['price_policy'] == 'dated_catalog' ||
    article['catalog_price_required'] == true;
Map<String, dynamic> _copy(dynamic value) =>
    Map<String, dynamic>.from(jsonDecode(jsonEncode(value)) as Map);
bool _id(dynamic value) =>
    value is String && RegExp(r'^[a-f0-9]{32}$').hasMatch(value);
bool _hash(dynamic value) =>
    value is String && RegExp(r'^[a-f0-9]{64}$').hasMatch(value);
Never _bad(String message) => throw ApiException(0, message);
dynamic _sorted(dynamic value) => value is Map
    ? {
        for (final key in value.keys.map((key) => '$key').toList()..sort())
          key: _sorted(value[key]),
      }
    : value is List
    ? value.map(_sorted).toList()
    : value;
Future<String> catalogPriceHash(dynamic value) async => (await Sha256().hash(
  value is Uint8List ? value : utf8.encode(jsonEncode(_sorted(value))),
)).bytes.map((v) => v.toRadixString(16).padLeft(2, '0')).join();
String catalogPriceDay(String text) {
  if (!RegExp(r'^\d{4}-\d{2}-\d{2}$').hasMatch(text))
    throw const FormatException(
      'Preisstand ausdrücklich als JJJJ-MM-TT eingeben.',
    );
  final day = DateTime.tryParse(text);
  if (day == null || day.toIso8601String().substring(0, 10) != text)
    throw const FormatException('Ein echtes Kalenderdatum angeben.');
  return text;
}

String catalogPriceLabel(Map<String, dynamic> price) =>
    '${price['price_net']} EUR / ${price['price_base_quantity']} ${price['unit']} · ${price['price_role'] == 'purchase_net' ? 'Einkauf' : 'Verkauf'} netto';
String catalogPriceValidity(Map<String, dynamic> price) =>
    '${price['valid_from']} bis ${price['valid_until'] ?? 'ausdrücklich offen'} (einschließlich)';
Map<String, dynamic> catalogSelectionFromSnapshot(
  Map<String, dynamic> snapshot,
) => {
  for (final key in [
    'price_id',
    'price_revision',
    'price_sha256',
    'effective_on',
  ])
    key: snapshot[key],
};

class CatalogPriceChoice {
  CatalogPriceChoice(Map<String, dynamic> value) : value = _copy(value);
  final Map<String, dynamic> value;
  Map<String, dynamic> get selection => catalogSelectionFromSnapshot(value);
  Map<String, dynamic> get price => businessMap(value['price']);
  String get sourceLabel =>
      '${value['source_name']}${value['source_reference'] is String && (value['source_reference'] as String).isNotEmpty ? ' · ${value['source_reference']}' : ''}';
  String get label =>
      '$sourceLabel · ${catalogPriceLabel(price)} · Preisstand ${value['effective_on']}';
}

List<CatalogPriceChoice> catalogPriceCandidates(
  dynamic raw, {
  required String articleId,
  required String role,
  required String day,
}) {
  final value = businessMap(raw);
  if (value['article_id'] != articleId ||
      value['price_role'] != role ||
      value['effective_on'] != day ||
      value['managed'] is! bool)
    _bad('Preisantwort gehört nicht zur gewählten Quelle oder zum Stichtag.');
  return businessItems(value).map((item) {
    final price = businessMap(item['price']);
    if (!_id(item['price_id']) ||
        item['price_revision'] is! int ||
        item['price_revision'] < 1 ||
        !_hash(item['price_sha256']) ||
        !_id(item['source_id']) ||
        item['source_name'] is! String ||
        (item.containsKey('source_reference') &&
            item['source_reference'] is! String) ||
        item['effective_on'] != day ||
        price['article_id'] != articleId ||
        price['price_role'] != role ||
        price['currency'] != 'EUR' ||
        !const [
          'eligible',
          'not_yet_valid',
          'expired',
          'withdrawn',
          'retired_binding',
          'unit_conflict',
        ].contains(item['status']))
      _bad('Unvollständiger datierter Preisnachweis.');
    for (final key in ['price_net', 'price_base_quantity', 'tax_rate']) {
      if (price[key] is! String ||
          !RegExp(r'^\d+(?:\.\d{1,4})?$').hasMatch(price[key]))
        _bad('Preisquelle enthält keinen exakten Dezimalwert.');
    }
    if (BigInt.parse('${price['price_base_quantity']}'.replaceAll('.', '')) ==
            BigInt.zero ||
        price['unit'] is! String)
      _bad('Positive Bezugsmenge und Einheit fehlen.');
    final from = catalogPriceDay('${price['valid_from']}'),
        until = price['valid_until'] == null
            ? null
            : catalogPriceDay('${price['valid_until']}');
    if (item['status'] == 'eligible' &&
        (day.compareTo(from) < 0 || until != null && day.compareTo(until) > 0))
      _bad('Preis liegt außerhalb seiner belegten Gültigkeit.');
    return CatalogPriceChoice(item);
  }).toList();
}

Future<Map<String, dynamic>> catalogPricePreview(
  Map<String, dynamic> run,
  Map<String, dynamic> decisions,
  dynamic raw,
) async {
  final value = businessMap(raw), hash = value['preview_sha256'];
  if (value['import_id'] != run['id'] ||
      value['source_id'] != run['source_id'] ||
      value['original_sha256'] != run['original']?['sha256'] ||
      value['rows_sha256'] != run['rows_sha256'] ||
      value['source_version'] != decisions['expected_source_version'] ||
      jsonEncode(_sorted(value['decisions'])) !=
          jsonEncode(_sorted(decisions)) ||
      value['ready'] is! bool ||
      value['required_replacements'] is! List ||
      value['rows'] is! List ||
      (value['rows'] as List).length != (run['rows'] as List).length ||
      !_hash(hash))
    _bad(
      'Katalogvorschau ist nicht an das gewählte Original und die Entscheidungen gebunden.',
    );
  final unhashed = {...value}..remove('preview_sha256');
  if (await catalogPriceHash(unhashed) != hash)
    _bad('Katalogvorschau und Prüfsumme stimmen nicht überein.');
  for (final item in value['rows'])
    if (item is! Map ||
        !const ['create', 'correct', 'unchanged'].contains(item['action']) ||
        item['price'] is! Map)
      _bad('Vollständige Preisänderungen fehlen.');
  return value;
}

abstract class _PriceState<T extends StatefulWidget> extends State<T>
    with WidgetsBindingObserver {
  BusinessSession get session;
  bool get permitted;
  bool get mayWrite;
  Object? get identity => null;
  BusinessSession? owner;
  Object? watchedIdentity, generation;
  bool background = false, busy = false, editing = false;
  int epoch = 0;
  String? error;
  final dialogs = <DialogRoute<dynamic>>[];
  bool valid(int captured) =>
      mounted && !background && captured == epoch && permitted;
  void clearValues();
  @override
  void initState() {
    super.initState();
    owner = session;
    generation = session.generation;
    watchedIdentity = identity;
    session.addListener(changed);
    WidgetsBinding.instance.addObserver(this);
  }

  void erase() {
    epoch++;
    busy = false;
    error = null;
    editing = false;
    clearValues();
    for (final route in dialogs.toList().reversed) {
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (route.isActive) route.navigator?.removeRoute(route);
      });
    }
    dialogs.clear();
  }

  void changed() {
    if (!mounted) return;
    if (generation != session.generation || !permitted || editing && !mayWrite)
      erase();
    generation = session.generation;
    setState(() {});
  }

  @override
  void didUpdateWidget(covariant T oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (owner != session || watchedIdentity != identity) {
      owner?.removeListener(changed);
      owner = session;
      session.addListener(changed);
      watchedIdentity = identity;
      generation = session.generation;
      erase();
    }
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
    owner?.removeListener(changed);
    WidgetsBinding.instance.removeObserver(this);
    super.dispose();
  }

  Future<R?> dialog<R>(WidgetBuilder builder) async {
    final route = DialogRoute<R>(context: context, builder: builder);
    dialogs.add(route);
    try {
      return await Navigator.of(context, rootNavigator: true).push(route);
    } finally {
      dialogs.remove(route);
    }
  }

  Future<void> fresh(int captured, {bool write = false}) async {
    if (!valid(captured))
      throw const ApiException(0, 'Preisquelle gewechselt.');
    await session.load();
    if (!valid(captured) || session.error != null || session.loading)
      throw const ApiException(0, 'Aktuelle Preisfreigabe fehlt.');
    if ((write || editing) && !mayWrite) {
      setState(erase);
      throw const ApiException(0, 'Preiswahl nicht mehr freigegeben.');
    }
  }

  Future<void> task(Future<void> Function(int) work) async {
    if (busy || !permitted || background) return;
    final captured = epoch;
    setState(() {
      busy = true;
      error = null;
    });
    try {
      await work(captured);
    } catch (e) {
      if (valid(captured)) setState(() => error = '$e');
    } finally {
      if (valid(captured)) setState(() => busy = false);
    }
  }
}

Future<CatalogPriceChoice?> selectCatalogPrice(
  BuildContext context, {
  required BusinessSession session,
  required Map<String, dynamic> article,
  required String role,
  String writePermission = 'finance.write',
  String section = 'documents',
}) => showDialog<CatalogPriceChoice>(
  context: context,
  builder: (_) => CatalogPricePicker(
    session: session,
    article: article,
    role: role,
    writePermission: writePermission,
    section: section,
  ),
);

class CatalogPricePicker extends StatefulWidget {
  const CatalogPricePicker({
    super.key,
    required this.session,
    required this.article,
    required this.role,
    this.writePermission = 'finance.write',
    this.section = 'documents',
  });
  final BusinessSession session;
  final Map<String, dynamic> article;
  final String role, writePermission, section;
  @override
  State<CatalogPricePicker> createState() => _CatalogPricePickerState();
}

class _CatalogPricePickerState extends _PriceState<CatalogPricePicker> {
  final day = TextEditingController();
  List<CatalogPriceChoice> choices = [];
  String? sourceId;
  @override
  BusinessSession get session => widget.session;
  @override
  Object get identity => '${widget.article['id']}:${widget.role}';
  @override
  bool get permitted => catalogPricesReadable(session);
  @override
  bool get mayWrite =>
      catalogPricesReadable(session) &&
      session.canWrite(widget.writePermission) &&
      session.sectionEnabled(widget.section);
  @override
  void initState() {
    super.initState();
    editing = true;
  }

  @override
  void clearValues() {
    day.clear();
    choices = [];
    sourceId = null;
    final route = ModalRoute.of(context);
    if (route is DialogRoute)
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (route.isActive) route.navigator?.removeRoute(route);
      });
  }

  @override
  void dispose() {
    day.dispose();
    super.dispose();
  }

  Future<void> search() => task((captured) async {
    editing = true;
    final date = catalogPriceDay(day.text.trim());
    await fresh(captured, write: true);
    final raw = await session.api.call(
      session.path('/catalog-prices/candidates'),
      {
        'article_id': widget.article['id'],
        'price_role': widget.role,
        'effective_on': date,
      },
    );
    await fresh(captured, write: true);
    final values = catalogPriceCandidates(
      raw,
      articleId: widget.article['id'],
      role: widget.role,
      day: date,
    );
    if (valid(captured) && day.text.trim() == date)
      setState(() => choices = values);
  });
  Future<void> choose(CatalogPriceChoice value) => task((captured) async {
    if (value.value['status'] != 'eligible') return;
    await fresh(captured, write: true);
    final raw = await session.api.call(
      session.path('/catalog-prices/candidates'),
      {
        'article_id': widget.article['id'],
        'price_role': widget.role,
        'effective_on': value.value['effective_on'],
        'source_id': value.value['source_id'],
      },
    );
    await fresh(captured, write: true);
    final current = catalogPriceCandidates(
      raw,
      articleId: widget.article['id'],
      role: widget.role,
      day: value.value['effective_on'],
    );
    if (!current.any(
      (item) =>
          item.value['status'] == 'eligible' &&
          jsonEncode(_sorted(item.value)) == jsonEncode(_sorted(value.value)),
    ))
      throw const ApiException(
        409,
        'Preisquelle wurde geändert; erneut auswählen.',
      );
    if (valid(captured)) Navigator.pop(context, value);
  });
  @override
  Widget build(BuildContext context) => AlertDialog(
    title: const Text('Datierten Preis ausdrücklich wählen'),
    content: SizedBox(
      width: 650,
      child: !permitted || background
          ? const Text('Preiswahl derzeit nicht freigegeben.')
          : SingleChildScrollView(
              child: Column(
                mainAxisSize: MainAxisSize.min,
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    '${widget.article['name'] ?? widget.article['article_name']} · ${widget.role == 'purchase_net' ? 'Einkauf' : 'Verkauf'}',
                  ),
                  const Text(
                    'Gültigkeitsgrenzen gelten einschließlich. Keine automatische Preis- oder Datumswahl.',
                  ),
                  TextField(
                    key: const ValueKey('catalog-price-day'),
                    controller: day,
                    enabled: !busy && mayWrite,
                    decoration: const InputDecoration(
                      labelText: 'Preisstand am (JJJJ-MM-TT)',
                    ),
                    onChanged: (_) => setState(() {
                      epoch++;
                      choices = [];
                      sourceId = null;
                      error = null;
                    }),
                  ),
                  FilledButton(
                    onPressed: busy || !mayWrite ? null : search,
                    child: const Text('Preisquellen prüfen'),
                  ),
                  if (error != null) Notice(error!, error: true),
                  if (busy) const LinearProgressIndicator(),
                  if (choices.isNotEmpty)
                    DropdownButtonFormField<String>(
                      isExpanded: true,
                      initialValue: sourceId,
                      decoration: const InputDecoration(
                        labelText: 'Quelle eingrenzen',
                      ),
                      items: [
                        const DropdownMenuItem(
                          value: null,
                          child: Text('Alle Quellen'),
                        ),
                        for (final id
                            in choices
                                .map(
                                  (item) => item.value['source_id'] as String,
                                )
                                .toSet())
                          DropdownMenuItem(
                            value: id,
                            child: Text(
                              choices
                                  .firstWhere(
                                    (item) => item.value['source_id'] == id,
                                  )
                                  .sourceLabel,
                              maxLines: 2,
                              overflow: TextOverflow.ellipsis,
                            ),
                          ),
                      ],
                      onChanged: busy
                          ? null
                          : (value) => setState(() => sourceId = value),
                    ),
                  for (final choice in choices.where(
                    (item) =>
                        sourceId == null || item.value['source_id'] == sourceId,
                  ))
                    Card(
                      child: Padding(
                        padding: const EdgeInsets.all(12),
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(choice.label),
                            Text(catalogPriceValidity(choice.price)),
                            Text(
                              const {
                                'eligible': 'Am gewählten Tag gültig',
                                'not_yet_valid': 'Noch nicht gültig',
                                'expired': 'Abgelaufen',
                                'withdrawn': 'Zurückgenommen',
                                'retired_binding': 'Artikelbindung abgelöst',
                                'unit_conflict': 'Einheiten-/Artikelkonflikt',
                              }[choice.value['status']]!,
                            ),
                            Text(
                              'Revision ${choice.value['price_revision']} · Originalpreissteuer ${choice.price['tax_rate']} %',
                            ),
                            if (choice.value['status'] == 'eligible')
                              OutlinedButton(
                                onPressed: busy || !mayWrite
                                    ? null
                                    : () => choose(choice),
                                child: const Text('Diesen Preis wählen'),
                              ),
                          ],
                        ),
                      ),
                    ),
                ],
              ),
            ),
    ),
    actions: [
      TextButton(
        onPressed: () => Navigator.pop(context),
        child: const Text('Abbrechen'),
      ),
    ],
  );
}

class BusinessCatalogPricesPage extends StatefulWidget {
  const BusinessCatalogPricesPage({
    super.key,
    required this.session,
    this.picker,
    this.exporter,
  });
  final BusinessSession session;
  final Future<XFile?> Function()? picker;
  final MailAttachmentExporter? exporter;
  @override
  State<BusinessCatalogPricesPage> createState() =>
      _BusinessCatalogPricesPageState();
}

class _BusinessCatalogPricesPageState
    extends _PriceState<BusinessCatalogPricesPage> {
  List<Map<String, dynamic>> sources = [],
      history = [],
      articles = [],
      priceHistory = [];
  Map<String, dynamic>? source, run, preview;
  Map<String, dynamic> bindings = {}, replacements = {};
  int offset = 0, total = 0, page = 0;
  bool confirmed = false;
  @override
  BusinessSession get session => widget.session;
  @override
  bool get permitted => catalogPricesManageable(session);
  @override
  bool get mayWrite => permitted && catalogPricesWritable(session);
  @override
  void initState() {
    super.initState();
    unawaited(load());
  }

  @override
  void clearValues() {
    sources = [];
    history = [];
    articles = [];
    priceHistory = [];
    source = null;
    run = null;
    preview = null;
    bindings = {};
    replacements = {};
    confirmed = false;
    offset = 0;
    total = 0;
    page = 0;
  }

  void changeScreen() {
    epoch++;
    busy = false;
    error = null;
    preview = null;
    bindings = {};
    replacements = {};
    confirmed = false;
    priceHistory = [];
    page = 0;
    editing = false;
  }

  Future<void> load() => task((captured) async {
    await fresh(captured);
    final value = businessItems(await session.read('/catalog-prices/sources'));
    await fresh(captured);
    if (value.any((item) => !_id(item['id']) || item['source_version'] is! int))
      _bad('Quellenantwort unvollständig.');
    setState(() => sources = value);
  });
  Future<void> selectSource(Map<String, dynamic> chosen) async {
    setState(() {
      changeScreen();
      source = chosen;
      run = null;
      history = [];
      offset = 0;
    });
    await loadHistory();
  }

  Future<void> loadHistory() => task((captured) async {
    final id = source!['id'];
    await fresh(captured);
    final value = businessMap(
      await session.read(
        '/catalog-prices/sources/$id/imports?offset=$offset&limit=20',
      ),
    );
    await fresh(captured);
    if (value['offset'] != offset ||
        value['limit'] != 20 ||
        value['total'] is! int ||
        businessItems(value)
            .any((item) => item['source_id'] != id || !_id(item['id'])))
      _bad('Historie gehört nicht zur ausgewählten Quelle.');
    setState(() {
      history = businessItems(value);
      total = value['total'];
    });
  });
  Future<void> showImport(String id) => task((captured) async {
    await fresh(captured);
    final value = businessMap(
      await session.read('/catalog-prices/imports/$id'),
    );
    await fresh(captured);
    if (value['id'] != id ||
        value['source_id'] != source?['id'] ||
        value['rows'] is! List ||
        !_hash(value['original']?['sha256']) ||
        value['current_source_version'] is! int)
      _bad('Originalimport ist unvollständig.');
    setState(() {
      run = value;
      preview = null;
      bindings = {};
      replacements = {};
      confirmed = false;
      priceHistory = [];
      page = 0;
      editing = value['status'] == 'staged' && mayWrite;
    });
  });
  Future<dynamic> command(
    String key,
    String path,
    Map<String, dynamic> body, {
    void Function(dynamic)? validate,
  }) => session.pending(key)
      ? session.repeatCatalogPricesCommand(key)
      : session.command(key, path, body, validateResult: validate);
  Future<void> createSource() async {
    editing = true;
    final captured = epoch;
    await dialog<void>(
      (_) => BusinessEditor(
        session: session,
        readPermission: 'finance.read',
        writePermission: 'finance.write',
        pendingKey: 'catalog-v2-source',
        title: 'Datierte Katalogquelle anlegen',
        fields: const [
          BusinessField('name', 'Quellenname', required: true),
          BusinessField('reference', 'Belegte Katalogreferenz', required: true),
        ],
        onSave: (values) async {
          await fresh(captured, write: true);
          await command(
            'catalog-v2-source',
            '/catalog-prices/sources',
            values,
            validate: (raw) {
              final value = businessMap(raw);
              if (!_id(value['id']) ||
                  value['name'] != values['name'] ||
                  value['reference'] != values['reference'])
                _bad('Quellenannahme unvollständig.');
            },
          );
        },
      ),
    );
    if (valid(captured)) await load();
  }

  Future<void> stage() async {
    if (!mayWrite || source == null) return;
    editing = true;
    final captured = epoch,
        id = source!['id'],
        key = 'catalog-v2-import-${source!['id']}';
    if (session.pending(key)) {
      await task((current) async {
        await fresh(current, write: true);
        await session.repeatCatalogPricesCommand(key);
        await fresh(current, write: true);
      });
      if (valid(captured)) await loadHistory();
      return;
    }
    Map<String, dynamic>? chosen;
    await dialog<void>(
      (_) => BusinessEditor(
        session: session,
        readPermission: 'finance.read',
        writePermission: 'finance.write',
        title: 'Originalrevision benennen',
        fields: const [
          BusinessField(
            'catalog_revision',
            'Belegte Katalogrevision',
            required: true,
            hint: 'Eigene nachprüfbare Referenz; kein automatisch behauptetes Datum',
          ),
        ],
        onSave: (values) async {
          chosen = values;
        },
      ),
    );
    if (!valid(captured) || chosen == null) return;
    await task((current) async {
      await fresh(current, write: true);
      final file =
          await (widget.picker?.call() ??
              openFile(
                acceptedTypeGroups: [
                  const XTypeGroup(
                    label: 'Smartplan CSV-v2',
                    extensions: ['csv'],
                  ),
                ],
              ));
      if (file == null || !valid(current)) return;
      final size = await file.length();
      if (size < 1 || size > 2097152)
        throw const ApiException(
          413,
          'Original zwischen 1 Byte und 2 MiB auswählen.',
        );
      final out = BytesBuilder(copy: false);
      await for (final bytes in file.openRead(0, size)) {
        if (!valid(current)) return;
        out.add(bytes);
        if (out.length > 2097152)
          throw const ApiException(413, 'Original überschreitet 2 MiB.');
      }
      final bytes = out.takeBytes();
      if (bytes.length != size || await file.length() != size)
        _bad('Originaldatei hat sich beim Lesen verändert.');
      final digest = await catalogPriceHash(bytes);
      await fresh(current, write: true);
      await command(
        key,
        '/catalog-prices/sources/$id/imports',
        {
          'catalog_revision': chosen!['catalog_revision'],
          'filename': file.name,
          'content_base64': base64Encode(bytes),
        },
        validate: (raw) {
          final value = businessMap(raw),
              original = businessMap(value['original']);
          if (!_id(value['id']) ||
              value['source_id'] != id ||
              value['catalog_revision'] != chosen!['catalog_revision'] ||
              original['sha256'] != digest ||
              original['size'] != size ||
              original['filename'] != file.name.trim())
            _bad('Originalimport wurde nicht vollständig bestätigt.');
        },
      );
      await fresh(current, write: true);
    });
    if (valid(captured)) await loadHistory();
  }

  Map<String, dynamic> decisions() => {
    'expected_source_version': run!['current_source_version'],
    'bindings': _copy(bindings),
    'replacements': _copy(replacements),
  };
  void defaults() {
    final old = businessMap(run!['bindings']);
    setState(() {
      for (final item in (run!['rows'] as List).map(businessMap)) {
        final code = item['code'],
            prior = businessMap(old[code]),
            article = businessMap(prior['article']);
        bindings[code] = {
          'action': article.isEmpty ? 'create' : 'bind',
          'article_id': article['id'],
          'article_revision': article['revision'],
          'expected_binding_revision': prior['binding_revision'] ?? 0,
          'confirm_name_difference': false,
        };
      }
      preview = null;
      confirmed = false;
    });
  }

  Future<void> bind(String code) async {
    editing = true;
    final captured = epoch;
    await task((current) async {
      await fresh(current, write: true);
      articles = businessItems(await session.read('/articles'));
      await fresh(current, write: true);
    });
    if (!valid(captured)) return;
    final item = (run!['rows'] as List)
            .map(businessMap)
            .firstWhere((row) => row['code'] == code),
        prior = businessMap(run!['bindings']?[code]);
    await dialog<void>(
      (_) => BusinessEditor(
        session: session,
        readPermission: 'finance.read',
        writePermission: 'finance.write',
        title: 'Artikelbindung · $code',
        initial: {
          'article_id': bindings[code]?['article_id'],
          'confirm_name_difference': false,
        },
        fields: [
          BusinessField(
            'article_id',
            'Vorhandenen Artikel wählen; leer = neuer Artikel',
            type: BusinessInput.choice,
            choices: {
              for (final article in articles.where(
                (value) =>
                    value['active'] == true &&
                    value['kind'] == 'material' &&
                    value['unit'] == item['unit'],
              ))
                '${article['id']}':
                    '${article['code']} · ${article['name']} · ${article['unit']}',
            },
          ),
          const BusinessField(
            'confirm_name_difference',
            'Abweichende Artikelbezeichnung ausdrücklich bestätigen',
            type: BusinessInput.toggle,
          ),
        ],
        onSave: (values) async {
          await fresh(captured, write: true);
          final id = values['article_id'];
          final selected = articles
              .where((article) => article['id'] == id)
              .firstOrNull;
          setState(() {
            bindings[code] = {
              'action': selected == null ? 'create' : 'bind',
              'article_id': selected?['id'],
              'article_revision': selected?['revision'],
              'expected_binding_revision': prior['binding_revision'] ?? 0,
              'confirm_name_difference':
                  selected != null && values['confirm_name_difference'] == true,
            };
            preview = null;
            confirmed = false;
          });
        },
      ),
    );
  }

  Future<void> check() => task((captured) async {
    final selected = run!, body = decisions();
    await fresh(captured);
    final raw = await session.api.call(
      session.path('/catalog-prices/imports/${selected['id']}/preview'),
      body,
    );
    await fresh(captured);
    final value = await catalogPricePreview(selected, body, raw);
    if (valid(captured) &&
        jsonEncode(_sorted(body)) == jsonEncode(_sorted(decisions())))
      setState(() {
        preview = value;
        confirmed = false;
      });
  });
  Future<void> correct() async {
    setState(() {
      for (final item in preview!['required_replacements'])
        replacements[item['external_price_id']] = {
          'revision': item['revision'],
          'sha256': item['sha256'],
        };
      preview = null;
      confirmed = false;
    });
    await check();
  }

  Future<void> apply() => task((captured) async {
    final selected = run!, key = 'catalog-v2-apply-${run!['id']}';
    await fresh(captured, write: true);
    if (!session.pending(key) && (preview?['ready'] != true || !confirmed))
      throw const FormatException(
        'Vollständige aktuelle Vorschau ausdrücklich bestätigen.',
      );
    final proposal = preview;
    await command(
      key,
      '/catalog-prices/imports/${selected['id']}/apply',
      {
        ...decisions(),
        'preview_sha256': proposal?['preview_sha256'],
        'confirmation': true,
      },
      validate: (raw) {
        final value = businessMap(raw);
        if (value['import_id'] != selected['id'] ||
            value['source_id'] != selected['source_id'] ||
            value['original_sha256'] != selected['original']['sha256'] ||
            value['preview_sha256'] != proposal?['preview_sha256'] ||
            value['prices'] is! List ||
            (value['prices'] as List).length !=
                (selected['rows'] as List).length)
          _bad('Preisübernahme wurde nicht vollständig bestätigt.');
      },
    );
    await fresh(captured, write: true);
    final value = businessMap(
      await session.read('/catalog-prices/imports/${selected['id']}'),
    );
    await fresh(captured, write: true);
    setState(() {
      run = value;
      preview = null;
      confirmed = false;
      editing = false;
    });
  });
  Future<void> original() => task((captured) async {
    final selected = run!, metadata = businessMap(run!['original']);
    await fresh(captured);
    final bytes = await session.api.bytes(
      session.path('/catalog-prices/imports/${selected['id']}/original'),
      mediaType: 'application/octet-stream',
      maxBytes: 2097152,
    );
    if (bytes.length != metadata['size'] ||
        await catalogPriceHash(bytes) != metadata['sha256'])
      _bad('Originalbytes stimmen nicht mit dem Katalognachweis überein.');
    await fresh(captured);
    final file = VerifiedMailAttachment(
      bytes: bytes,
      filename: metadata['filename'],
      mediaType: 'application/octet-stream',
      sha256: metadata['sha256'],
    );
    await (widget.exporter ?? exportMailAttachment)(
      context,
      file,
      () => valid(captured),
    );
  });
  Future<void> priceDetails(String id) => task((captured) async {
    await fresh(captured);
    final value = businessItems(
      await session.read('/catalog-prices/prices/$id/history'),
    );
    await fresh(captured);
    if (value.any((item) => item['id'] != id || !_hash(item['sha256'])))
      _bad('Preisverlauf gehört nicht zur gewählten Preiskennung.');
    setState(() => priceHistory = value);
  });
  Future<void> withdraw() async {
    if (priceHistory.isEmpty) return;
    editing = true;
    final captured = epoch,
        head = _copy(priceHistory.last),
        key = 'catalog-v2-withdraw-${priceHistory.last['id']}';
    await dialog<void>(
      (_) => BusinessEditor(
        session: session,
        readPermission: 'finance.read',
        writePermission: 'finance.write',
        pendingKey: key,
        title: 'Preisrevision ausdrücklich zurücknehmen',
        fields: const [
          BusinessField(
            'reason',
            'Belegter Rücknahmegrund',
            required: true,
            type: BusinessInput.multiline,
          ),
          BusinessField(
            'confirmation',
            'Diese Preisquelle für neue Auswahlen zurücknehmen',
            type: BusinessInput.toggle,
          ),
        ],
        onSave: (values) async {
          await fresh(captured, write: true);
          if (values['confirmation'] != true)
            throw const FormatException('Rücknahme ausdrücklich bestätigen.');
          await command(
            key,
            '/catalog-prices/prices/${head['id']}/withdraw',
            {'revision': head['revision'], 'sha256': head['sha256'], ...values},
            validate: (raw) {
              final value = businessMap(raw);
              if (value['id'] != head['id'] ||
                  value['status'] != 'withdrawn' ||
                  value['revision'] != head['revision'] + 1)
                _bad('Rücknahme wurde nicht vollständig bestätigt.');
            },
          );
        },
      ),
    );
    if (valid(captured)) await priceDetails(head['id']);
  }

  Widget priceCard(Map<String, dynamic> item) {
    final price = businessMap(item['price'] ?? item),
        before = businessMap(item['before']);
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('${price['code']} · ${price['name']}'),
            Text(catalogPriceLabel(price)),
            Text(catalogPriceValidity(price)),
            if (item['action'] != null)
              Text(
                const {
                      'create': 'Neuer Preis',
                      'correct': 'Preisrevision wird korrigiert',
                      'unchanged': 'Preis unverändert',
                    }[item['action']] ??
                    '${item['action']}',
              ),
            if (before.isNotEmpty)
              Text(
                'Vorher: ${catalogPriceLabel(businessMap(before['price'] ?? before))}\n${catalogPriceValidity(businessMap(before['price'] ?? before))}',
              ),
            if (run?['status'] == 'staged')
              Text(
                'Artikelbindung: ${bindings[price['code']]?['action'] == 'create' ? 'Neuanlage' : bindings[price['code']]?['article_id'] ?? 'noch ausdrücklich wählen'}',
              ),
            if (run?['status'] == 'staged' && !busy && mayWrite)
              TextButton(
                onPressed: () => bind(price['code']),
                child: const Text('Artikelbindung wählen'),
              ),
          ],
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final selected = run;
    final rows = (preview?['rows'] ?? selected?['rows'] ?? []) as List;
    return Scaffold(
      appBar: AppBar(title: const Text('Datierte Katalogpreise · CSV-v2')),
      body: !permitted || background
          ? const Center(
              child: Text('Katalogpreise derzeit nicht freigegeben.'),
            )
          : ListView(
              padding: const EdgeInsets.all(20),
              children: [
                const Notice(
                  'Eigenes Smartplan-CSV-v2. Keine Lieferantenverbindung. Preise gelten ausschließlich für ausdrücklich belegte Zeiträume; Rohbetrag und Bezugsmenge bleiben getrennt.',
                ),
                if (error != null) Notice(error!, error: true),
                if (busy) const LinearProgressIndicator(),
                if (source == null) ...[
                  if (mayWrite)
                    FilledButton(
                      onPressed: busy ? null : createSource,
                      child: Text(
                        session.pending('catalog-v2-source')
                            ? 'Ursprüngliche Quellenannahme erneut prüfen'
                            : 'Katalogquelle anlegen',
                      ),
                    ),
                  OutlinedButton(
                    onPressed: busy ? null : load,
                    child: const Text('Quellen neu laden'),
                  ),
                  for (final item in sources)
                    Card(
                      child: ListTile(
                        title: Text('${item['name']}'),
                        subtitle: Text(
                          '${item['reference']} · Stand ${item['source_version']}',
                        ),
                        onTap: busy ? null : () => selectSource(item),
                      ),
                    ),
                ],
                if (source != null) ...[
                  Text(
                    '${source!['name']} · ${source!['reference']}',
                    style: Theme.of(context).textTheme.titleLarge,
                  ),
                  TextButton(
                    onPressed: busy
                        ? null
                        : () {
                            setState(() {
                              changeScreen();
                              source = null;
                              run = null;
                            });
                            load();
                          },
                    child: const Text('Zur Quellenauswahl'),
                  ),
                ],
                if (source != null && selected == null) ...[
                  if (mayWrite)
                    FilledButton(
                      onPressed: busy ? null : stage,
                      child: Text(
                        session.pending('catalog-v2-import-${source!['id']}')
                            ? 'Ursprünglichen Dateiimport erneut prüfen'
                            : 'CSV-v2-Original auswählen',
                      ),
                    ),
                  OutlinedButton(
                    onPressed: busy ? null : loadHistory,
                    child: const Text('Importhistorie neu laden'),
                  ),
                  for (final item in history)
                    Card(
                      child: ListTile(
                        title: Text(
                          '${item['catalog_revision']} · ${item['original']?['filename']}',
                        ),
                        subtitle: Text(
                          '${item['status']} · ${item['row_count']} Preiszeilen',
                        ),
                        onTap: busy ? null : () => showImport(item['id']),
                      ),
                    ),
                  Wrap(
                    children: [
                      if (offset > 0)
                        TextButton(
                          onPressed: busy
                              ? null
                              : () {
                                  offset -= 20;
                                  loadHistory();
                                },
                          child: const Text('Vorherige Importe'),
                        ),
                      if (offset + 20 < total)
                        TextButton(
                          onPressed: busy
                              ? null
                              : () {
                                  offset += 20;
                                  loadHistory();
                                },
                          child: const Text('Weitere Importe'),
                        ),
                    ],
                  ),
                ],
                if (selected != null) ...[
                  Text(
                    '${selected['catalog_revision']} · ${selected['original']?['filename']}',
                  ),
                  Text('SHA-256 ${selected['original']?['sha256']}'),
                  Wrap(
                    spacing: 12,
                    children: [
                      OutlinedButton(
                        onPressed: busy ? null : original,
                        child: const Text('Original herunterladen'),
                      ),
                      TextButton(
                        onPressed: busy
                            ? null
                            : () {
                                setState(() {
                                  changeScreen();
                                  run = null;
                                });
                                loadHistory();
                              },
                        child: const Text('Zur Importhistorie'),
                      ),
                    ],
                  ),
                  if (selected['status'] == 'staged') ...[
                    const Text(
                      'Jede Quellnummer ausdrücklich neu anlegen oder an einen passenden Artikel binden.',
                    ),
                    OutlinedButton(
                      onPressed: busy ? null : defaults,
                      child: const Text(
                        'Vorhandene Bindungen und Neuanlagen als Vorschlag einsetzen',
                      ),
                    ),
                    OutlinedButton(
                      onPressed: busy ? null : check,
                      child: const Text('Verbindliche Preisvorschau laden'),
                    ),
                  ],
                  for (final item
                      in rows.skip(page * 30).take(30).map(businessMap))
                    priceCard(item),
                  Wrap(
                    children: [
                      if (page > 0)
                        TextButton(
                          onPressed: busy ? null : () => setState(() => page--),
                          child: const Text('Vorherige Preiszeilen'),
                        ),
                      if ((page + 1) * 30 < rows.length)
                        TextButton(
                          onPressed: busy ? null : () => setState(() => page++),
                          child: const Text('Weitere Preiszeilen'),
                        ),
                    ],
                  ),
                  if (preview != null && preview!['ready'] == false) ...[
                    const Notice(
                      'Vorhandene Preise werden geändert. Die angezeigten alten und neuen Fakten vor der Korrektur prüfen.',
                      error: true,
                    ),
                    for (final item in preview!['required_replacements'])
                      Text(
                        '${item['external_price_id']} · bisherige Revision ${item['revision']}',
                      ),
                    OutlinedButton(
                      onPressed: busy || !mayWrite ? null : correct,
                      child: const Text(
                        'Diese Korrekturen ausdrücklich bestätigen und erneut prüfen',
                      ),
                    ),
                  ],
                  if (selected['status'] == 'staged' &&
                      preview?['ready'] == true)
                    CheckboxListTile(
                      value: confirmed,
                      onChanged: busy || !mayWrite
                          ? null
                          : (value) =>
                                setState(() => confirmed = value == true),
                      title: const Text(
                        'Original, Bindungen, Gültigkeiten und Preisänderungen vollständig geprüft',
                      ),
                    ),
                  if (mayWrite &&
                      (selected['status'] == 'staged' ||
                          session.pending(
                            'catalog-v2-apply-${selected['id']}',
                          )))
                    FilledButton(
                      onPressed: busy ? null : apply,
                      child: Text(
                        session.pending('catalog-v2-apply-${selected['id']}')
                            ? 'Ursprüngliche Preisannahme erneut prüfen'
                            : 'Preise ausdrücklich übernehmen',
                      ),
                    ),
                  if (selected['status'] == 'applied') ...[
                    const Notice(
                      'Diese Preisrevisionen wurden angenommen. Bestehende Belege behalten ihre historischen Fakten.',
                    ),
                    for (final fact
                        in (selected['application']?['prices'] as List? ?? []))
                      TextButton(
                        onPressed: busy
                            ? null
                            : () => priceDetails(fact['price_id']),
                        child: Text(
                          'Preisverlauf · ${fact['price_id']} · Revision ${fact['revision']}',
                        ),
                      ),
                  ],
                ],
                if (priceHistory.isNotEmpty) ...[
                  Text(
                    'Unveränderlicher Preisverlauf',
                    style: Theme.of(context).textTheme.titleLarge,
                  ),
                  for (final fact in priceHistory) ...[
                    Text(
                      'Revision ${fact['revision']} · ${fact['status']} · ${fact['created_at']}',
                    ),
                    priceCard(businessMap(fact)),
                    if (fact['reason'] != null) Text('${fact['reason']}'),
                  ],
                  if (mayWrite &&
                      (priceHistory.last['status'] == 'active' ||
                          session.pending(
                            'catalog-v2-withdraw-${priceHistory.last['id']}',
                          )))
                    OutlinedButton(
                      onPressed: busy ? null : withdraw,
                      child: const Text('Preis ausdrücklich zurücknehmen'),
                    ),
                ],
              ],
            ),
    );
  }
}

/// Owns only the dialogs opened for one explicit consumer selection.
class CatalogPriceFlow with WidgetsBindingObserver {
  CatalogPriceFlow(this.context, this.session, this.current)
    : generation = session.generation {
    session.addListener(changed);
    WidgetsBinding.instance.addObserver(this);
  }
  final BuildContext context;
  final BusinessSession session;
  final bool Function() current;
  final Object? generation;
  bool stopped = false;
  final routes = <DialogRoute<dynamic>>[];
  bool get valid =>
      !stopped &&
      context.mounted &&
      current() &&
      session.generation == generation &&
      session.allowed;
  void changed() {
    if (!valid) stop();
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state != AppLifecycleState.resumed) stop();
  }

  void stop() {
    if (stopped) return;
    stopped = true;
    for (final route in routes.toList().reversed) {
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (route.isActive) route.navigator?.removeRoute(route);
      });
    }
    routes.clear();
  }

  void dispose() {
    stop();
    session.removeListener(changed);
    WidgetsBinding.instance.removeObserver(this);
  }

  Future<T?> dialog<T>(WidgetBuilder builder) async {
    if (!valid) return null;
    final route = DialogRoute<T>(context: context, builder: builder);
    routes.add(route);
    try {
      final value = await Navigator.of(
        context,
        rootNavigator: true,
      ).push(route);
      return valid ? value : null;
    } finally {
      routes.remove(route);
    }
  }

  Future<CatalogPriceChoice?> choose(
    Map<String, dynamic> article,
    String role, {
    String writePermission = 'finance.write',
    String section = 'documents',
  }) => dialog<CatalogPriceChoice>(
    (_) => CatalogPricePicker(
      session: session,
      article: article,
      role: role,
      writePermission: writePermission,
      section: section,
    ),
  );
  Future<void> fresh() async {
    if (!valid)
      throw const ApiException(0, 'Preisauswahlkontext wurde geschlossen.');
    await session.load();
    if (!valid || session.error != null || session.loading)
      throw const ApiException(0, 'Aktuelle Auswahlrechte fehlen.');
  }
}

import 'dart:convert';
import 'dart:typed_data';

import 'package:cryptography/cryptography.dart';
import 'package:file_selector/file_selector.dart';
import 'package:flutter/material.dart';

import 'api.dart';
import 'business_session.dart';
import 'business_contacts.dart';
import 'business_widgets.dart';
import 'design.dart';
import 'mail_attachment_widgets.dart';

const migrationDocumentKinds = {
  'invoice': 'Rechnung',
  'credit_note': 'Gutschrift',
  'offer': 'Angebot',
  'order': 'Auftrag',
  'delivery_note': 'Lieferschein',
  'other': 'Sonstiges',
};
const migrationKinds = {
  'contact': 'Kontakte',
  'project': 'Projekte',
  'document': 'Historische Dokumente',
};
const migrationLabels = {
  'source_id': 'Stabile Quellkennung',
  'name': 'Name',
  'contact': 'Kontaktangabe',
  'email': 'E-Mail',
  'phone': 'Telefon',
  'address': 'Anschrift',
  'notes': 'Notizen',
  'person_name': 'Ansprechpartner – Name',
  'person_email': 'Ansprechpartner – E-Mail',
  'person_phone': 'Ansprechpartner – Telefon',
  'customer_source_id': 'Quellkennung des Kunden',
  'project_source_id': 'Quellkennung des Projekts',
  'kind': 'Dokumentart',
  'number': 'Historische Dokumentnummer',
  'issue_date': 'Belegdatum (YYYY-MM-DD)',
  'net': 'Nettobetrag',
  'tax': 'Steuerbetrag',
  'gross': 'Bruttobetrag',
  'currency': 'Währung',
  'original_filename': 'Exakter Originaldateiname',
};
bool _id(Object? value) => RegExp(r'^[a-f0-9]{32}$').hasMatch('$value');
bool _hash(Object? value) => RegExp(r'^[a-f0-9]{64}$').hasMatch('$value');
String _hex(List<int> value) =>
    value.map((v) => v.toRadixString(16).padLeft(2, '0')).join();
String migrationAmount(Object? value, [Object? exact]) {
  if (exact != null) {
    if (exact is! String || !RegExp(r'^-?\d+\.\d{2}$').hasMatch(exact))
      throw const FormatException('Exakter Betragsnachweis ist ungültig.');
    return exact.replaceAll('.', ',');
  }
  if (value is! int) return 'Nicht angegeben';
  final absolute = value.abs();
  return '${value < 0 ? '-' : ''}${absolute ~/ 100},${(absolute % 100).toString().padLeft(2, '0')}';
}

Object? _stable(Object? value) {
  if (value is Map) {
    final keys = value.keys.map((key) => '$key').toList()..sort();
    return {for (final key in keys) key: _stable(value[key])};
  }
  if (value is List) return value.map(_stable).toList();
  return value;
}

Map<String, dynamic> migrationDeclaration(Map<String, dynamic> values) {
  final result = Map<String, dynamic>.from(values);
  for (final key in ['period_from', 'period_to']) {
    if (result[key] == '') result[key] = null;
  }
  if (!['hero', 'sevdesk', 'other'].contains(result['source_system']) ||
      [
        'source_account',
        'label',
        'scope',
      ].any((key) => '${result[key] ?? ''}'.trim().isEmpty))
    throw const FormatException(
      'Quellsystem, Konto, Bezeichnung und Umfang vollständig angeben.',
    );
  final from = result['period_from'], to = result['period_to'];
  if ((from == null) != (to == null) ||
      (from != null && '$from'.compareTo('$to') > 0))
    throw const FormatException(
      'Vollständigen geordneten Exportzeitraum wählen.',
    );
  return result;
}

Map<String, dynamic> migrationMapping(
  Map<String, dynamic> detail, {
  Map<String, dynamic>? table,
  Map<String, dynamic>? decision,
}) {
  final current = businessMap(detail['mapping']),
      tables = businessItems(current['tables'])
          .map((v) => Map<String, dynamic>.from(v))
          .toList(),
      decisions = businessItems(current['decisions'])
          .map((v) => Map<String, dynamic>.from(v))
          .toList();
  if (table != null) {
    if (!_id(table['file_id']) ||
        !migrationKinds.containsKey(table['kind']) ||
        businessMap(table['columns']).isEmpty)
      throw const FormatException(
        'Datei, Datensatzart und Quellspalten ausdrücklich zuordnen.',
      );
    tables.removeWhere((v) => v['file_id'] == table['file_id']);
    tables.add(table);
  }
  if (decision != null) {
    if (!migrationKinds.containsKey(decision['kind']) ||
        '${decision['source_id'] ?? ''}'.trim().isEmpty ||
        !['create', 'link', 'skip'].contains(decision['action']) ||
        '${decision['reason'] ?? ''}'.trim().isEmpty ||
        (decision['action'] == 'link' &&
            (!_id(decision['target_id']) || decision['kind'] == 'document')) ||
        (decision['action'] != 'link' && decision['target_id'] != null))
      throw const FormatException(
        'Übernahmeentscheidung und Begründung prüfen.',
      );
    decisions.removeWhere(
      (v) =>
          v['kind'] == decision['kind'] &&
          v['source_id'] == decision['source_id'],
    );
    decisions.add(decision);
  }
  return {
    'revision': current['revision'] ?? 0,
    'tables': tables,
    'decisions': decisions,
  };
}

Map<String, dynamic> migrationApplyValues(
  Map<String, dynamic> detail,
  Map<String, dynamic> preview,
  bool confirmed,
) {
  if (!confirmed ||
      preview['package_id'] != detail['id'] ||
      preview['revision'] != detail['mapping']['revision'] ||
      preview['ready'] != true ||
      !_hash(preview['preview_sha256']))
    throw const FormatException(
      'Nur eine aktuelle fehlerfreie Vorschau ausdrücklich übernehmen.',
    );
  return {
    'revision': preview['revision'],
    'preview_sha256': preview['preview_sha256'],
    'confirmation': true,
  };
}

Map<String, dynamic> migrationReceipt(
  String path,
  Map<String, dynamic> body,
  dynamic response, {
  String? originalSha256,
  int? originalSize,
}) {
  final value = businessMap(response);
  if (path == '/migrations') {
    if (!_id(value['id']) ||
        body.entries.any(
          (entry) =>
              entry.key != 'request_id' && value[entry.key] != entry.value,
        ))
      throw const ApiException(
        0,
        'Importantwort bestätigt die ursprüngliche Erklärung nicht.',
      );
    return value;
  }
  final match = RegExp(
    r'^/migrations/([a-f0-9]{32})/(files|mapping|apply|reconcile)$',
  ).firstMatch(path);
  if (match == null || value['package_id'] != match.group(1))
    throw const ApiException(0, 'Importantwort gehört zu einem anderen Paket.');
  switch (match.group(2)) {
    case 'files':
      if (!_id(value['id']) ||
          value['filename'] != body['filename'] ||
          !_hash(value['sha256']) ||
          value['size'] != base64Decode(body['content_base64']).length ||
          (originalSha256 != null && value['sha256'] != originalSha256) ||
          (originalSize != null && value['size'] != originalSize))
        throw const ApiException(
          0,
          'Originalantwort stimmt nicht mit der Datei überein.',
        );
      break;
    case 'mapping':
      if (value['revision'] != body['revision'] + 1 ||
          jsonEncode(_stable(value['tables'])) !=
              jsonEncode(_stable(body['tables'])) ||
          jsonEncode(_stable(value['decisions'])) !=
              jsonEncode(_stable(body['decisions'])))
        throw const ApiException(0, 'Zuordnungsfassung wurde nicht bestätigt.');
      break;
    case 'apply':
      if (value['revision'] != body['revision'] ||
          value['preview_sha256'] != body['preview_sha256'] ||
          !_hash(value['report_sha256']) ||
          value['financial_effects'] != false)
        throw const ApiException(
          0,
          'Übernahmebericht bestätigt diese Vorschau nicht.',
        );
      break;
    case 'reconcile':
      if (value['report_sha256'] != body['report_sha256'] ||
          value['note'] != body['note'])
        throw const ApiException(
          0,
          'Abgleich bestätigt den ursprünglichen Bericht nicht.',
        );
      break;
  }
  return value;
}

class BusinessMigrationsPage extends StatefulWidget {
  const BusinessMigrationsPage({
    super.key,
    required this.session,
    this.pickFile,
    this.exporter,
    this.onProject,
  });
  final BusinessSession session;
  final Future<XFile?> Function()? pickFile;
  final MailAttachmentExporter? exporter;
  final void Function(Map<String, dynamic>)? onProject;
  @override
  State<BusinessMigrationsPage> createState() => _BusinessMigrationsPageState();
}

class _BusinessMigrationsPageState extends State<BusinessMigrationsPage> {
  BusinessSession get session => widget.session;
  Map<String, dynamic>? options, selected, preview, report;
  List<Map<String, dynamic>> packages = [];
  String? error, selectedId;
  bool loading = false, owner = false;
  int epoch = 0;
  Object? generation;
  Set<String> knownPermissions = {};
  bool get allowed =>
      session.allowed &&
      session.projectId == null &&
      session.hasFeature('file_migrations') &&
      session.hasModule('migrations') &&
      [
        'settings.manage',
        'contacts.read',
        'finance.read',
        'documents.read',
      ].every(session.can);
  bool get writable => allowed && owner && session.canWrite('settings.manage');
  bool get canApply =>
      writable &&
      owner &&
      session.canWrite('contacts.write') &&
      session.canWrite('projects.manage');
  @override
  void initState() {
    super.initState();
    generation = session.generation;
    knownPermissions = Set.of(session.permissions);
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
    if (!allowed ||
        generation != session.generation ||
        !session.permissions.containsAll(knownPermissions)) {
      epoch++;
      options = null;
      selected = null;
      preview = null;
      report = null;
      packages = [];
      owner = false;
      loading = false;
    }
    generation = session.generation;
    knownPermissions = Set.of(session.permissions);
    setState(() {});
  }

  void guard({bool write = false}) {
    if (!mounted || !allowed || (write && !writable))
      throw const ApiException(
        403,
        'Die aktuelle globale Importberechtigung fehlt.',
      );
  }

  Future<void> attempt(Future<void> Function() callback) async {
    try {
      await callback();
    } catch (value) {
      if (mounted && allowed) setState(() => error = '$value');
    }
  }

  Future<void> load() async {
    if (!allowed) return;
    final captured = ++epoch;
    setState(() {
      loading = true;
      error = null;
    });
    try {
      final responses = await Future.wait([
        session.read('/migrations/options'),
        session.read('/migrations'),
        session.api.call('/api/me'),
        if (selectedId != null) session.read('/migrations/$selectedId'),
      ]);
      guard();
      if (captured != epoch) return;
      setState(() {
        options = businessMap(responses[0]);
        packages = businessItems(responses[1]);
        owner = businessMap(responses[2])['role'] == 'owner';
        if (!owner)
          throw const ApiException(
            403,
            'Originalimporte benötigen die Geschäftsführung.',
          );
        if (selectedId != null) {
          final record = businessMap(responses[3]);
          if (record['id'] != selectedId)
            throw const ApiException(
              0,
              'Paketantwort gehört zu einem anderen Paket.',
            );
          selected = record;
        }
        preview = null;
        report = null;
      });
    } catch (value) {
      if (mounted && captured == epoch)
        setState(() {
          error = '$value';
          if (value is ApiException && [403, 404].contains(value.status)) {
            selected = null;
            preview = null;
            report = null;
            packages = [];
            options = null;
            owner = false;
          }
        });
    } finally {
      if (mounted && captured == epoch) setState(() => loading = false);
    }
  }

  Future<Map<String, dynamic>> read(String path) async {
    guard();
    final captured = epoch;
    Map<String, dynamic> result;
    try {
      result = businessMap(await session.read(path));
    } on ApiException catch (error) {
      if (mounted &&
          captured == epoch &&
          [401, 403, 404].contains(error.status)) {
        setState(() {
          selected = null;
          preview = null;
          report = null;
          packages = [];
          options = null;
          owner = false;
          epoch++;
        });
      }
      rethrow;
    }
    guard();
    if (captured != epoch)
      throw const ApiException(0, 'Sitzung oder Auswahl geändert.');
    return result;
  }

  Future<dynamic> command(
    String key,
    String path,
    Map<String, dynamic> body, {
    String? originalSha256,
    int? originalSize,
  }) async {
    guard(write: true);
    if (session.pending(key)) return session.repeatMigrationCommand(key);
    return session.command(
      key,
      path,
      body,
      validateResult: (value) => migrationReceipt(
        path,
        body,
        value,
        originalSha256: originalSha256,
        originalSize: originalSize,
      ),
    );
  }

  Future<dynamic> edit(
    String title,
    String key,
    String path,
    List<BusinessField> fields,
    Map<String, dynamic> Function(Map<String, dynamic>) build, {
    String? originalSha256,
    int? originalSize,
  }) async {
    guard(write: true);
    dynamic result;
    await showDialog<bool>(
      context: context,
      barrierDismissible: false,
      builder: (_) => BusinessEditor(
        session: session,
        title: title,
        fields: fields,
        pendingKey: key,
        readAllowed: () => allowed,
        readPermission: 'settings.manage',
        writePermission: 'settings.manage',
        saveLabel: title,
        onSave: (values) async {
          guard(write: true);
          final body =
              session.pendingCommandValues(key, path: path) ?? build(values);
          result = await command(
            key,
            path,
            body,
            originalSha256: originalSha256,
            originalSize: originalSize,
          );
        },
      ),
    );
    return result;
  }

  Future<void> create() async {
    const key = 'migration-create';
    final old = session.pendingCommandValues(key, path: '/migrations') ?? {};
    final result = await edit('Paket verbindlich anlegen', key, '/migrations', [
      BusinessField(
        'source_system',
        'Quellsystem',
        type: BusinessInput.choice,
        choices: const {
          'other': 'Andere / eigene Datei',
          'hero': 'HERO',
          'sevdesk': 'sevdesk',
        },
        initial: old['source_system'] ?? 'other',
      ),
      BusinessField(
        'source_account',
        'Eindeutiges Quellkonto',
        required: true,
        initial: old['source_account'],
      ),
      BusinessField(
        'label',
        'Bezeichnung des Pakets',
        required: true,
        initial: old['label'],
      ),
      BusinessField(
        'period_from',
        'Exportzeitraum ab',
        type: BusinessInput.date,
        initial: old['period_from'],
      ),
      BusinessField(
        'period_to',
        'Exportzeitraum bis',
        type: BusinessInput.date,
        initial: old['period_to'],
      ),
      BusinessField(
        'scope',
        'Deklarierter Umfang / Exportauswahl',
        type: BusinessInput.multiline,
        required: true,
        initial: old['scope'],
      ),
    ], migrationDeclaration);
    if (result != null && mounted) {
      selectedId = businessMap(result)['id'];
      await load();
    }
  }

  Future<void> upload() async {
    final item = selected!;
    final key = 'migration-file-${item['id']}',
        path = '/migrations/${item['id']}/files';
    final old = session.pendingCommandValues(key, path: path);
    Map<String, dynamic> body;
    String? digest;
    int? length;
    if (old != null) {
      body = old;
    } else {
      guard(write: true);
      final captured = epoch;
      final file = await (widget.pickFile?.call() ?? openFile());
      if (file == null) return;
      guard(write: true);
      length = await file.length();
      if (length < 1 || length > options!['max_file_bytes'])
        throw const ApiException(
          413,
          'Eine Originaldatei mit 1 Byte bis 2 MiB auswählen.',
        );
      final bytes = await file.readAsBytes();
      guard(write: true);
      if (captured != epoch || bytes.length != length)
        throw const ApiException(
          409,
          'Datei oder Sitzung wurde während der Auswahl geändert.',
        );
      digest = _hex((await Sha256().hash(bytes)).bytes);
      final suffix = file.name.split('.').last.toLowerCase(),
          media =
              const {
                'csv': 'text/csv',
                'json': 'application/json',
                'pdf': 'application/pdf',
                'xml': 'application/xml',
                'zip': 'application/zip',
                'jpg': 'image/jpeg',
                'jpeg': 'image/jpeg',
                'png': 'image/png',
              }[suffix] ??
              'application/octet-stream';
      body = {
        'filename': file.name,
        'media_type': media,
        'content_base64': base64Encode(bytes),
      };
    }
    final result = await edit(
      'Original unverändert speichern: ${body['filename']}',
      key,
      path,
      const [],
      (_) => body,
      originalSha256: digest,
      originalSize: length,
    );
    if (result != null) await load();
  }

  Future<void> download(Map<String, dynamic> file) async {
    guard();
    final captured = epoch, item = selected!;
    final bytes = await session.api.bytes(
      session.path('/migrations/${item['id']}/files/${file['id']}/original'),
      mediaType: 'application/octet-stream',
    );
    guard();
    final digest = _hex((await Sha256().hash(bytes)).bytes);
    if (captured != epoch ||
        digest != file['sha256'] ||
        bytes.length != file['size'])
      throw const ApiException(
        0,
        'Original stimmt nicht mit der gespeicherten Prüfsumme überein.',
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
      () => mounted && allowed && epoch == captured,
    );
  }

  Future<void> configure(
    Map<String, dynamic> file, [
    Map<String, dynamic>? previous,
  ]) async {
    if (session.pending('migration-mapping-$selectedId')) {
      await resolvePending('mapping');
      return;
    }
    guard(write: true);
    final item = selected!, captured = epoch;
    Map<String, dynamic>? config, sample;
    await showDialog<bool>(
      context: context,
      builder: (_) => BusinessEditor(
        session: session,
        title: 'Quelltabelle lesen',
        readAllowed: () => allowed && captured == epoch,
        writePermission: 'settings.manage',
        saveLabel: 'Spalten und Beispielzeilen lesen',
        fields: [
          BusinessField(
            'kind',
            'Datensatzart',
            type: BusinessInput.choice,
            choices: migrationKinds,
            initial: previous?['kind'] ?? 'contact',
          ),
          BusinessField(
            'format',
            'Tabellenformat',
            type: BusinessInput.choice,
            choices: const {'csv': 'CSV', 'json': 'JSON-Zeilenliste'},
            initial: previous?['format'] ?? 'csv',
          ),
          BusinessField(
            'encoding',
            'Zeichensatz',
            type: BusinessInput.choice,
            choices: const {
              'utf-8-sig': 'UTF-8 (optional BOM)',
              'cp1252': 'Windows-1252',
            },
            initial: previous?['encoding'] ?? 'utf-8-sig',
          ),
          BusinessField(
            'delimiter',
            'Spaltentrennzeichen',
            type: BusinessInput.choice,
            choices: const {';': 'Semikolon', ',': 'Komma', '\t': 'Tabulator'},
            initial: previous?['delimiter'] ?? ';',
          ),
          BusinessField(
            'decimal_separator',
            'Dezimaltrennzeichen',
            type: BusinessInput.choice,
            choices: const {'.': 'Punkt', ',': 'Komma'},
            initial: previous?['decimal_separator'] ?? '.',
          ),
        ],
        onSave: (values) async {
          guard(write: true);
          config = values;
          final query = Uri(
            queryParameters: {
              for (final key in ['format', 'encoding', 'delimiter'])
                key: '${values[key]}',
            },
          ).query;
          sample = await read(
            '/migrations/${item['id']}/files/${file['id']}/inspect?$query',
          );
          if (sample!['file_id'] != file['id'] ||
              sample!['sha256'] != file['sha256'])
            throw const ApiException(
              0,
              'Vorschau gehört nicht zur Originaldatei.',
            );
        },
      ),
    );
    if (config == null || sample == null || !mounted || captured != epoch)
      return;
    final proceed = await showDialog<bool>(
      context: context,
      builder: (_) => ListenableBuilder(
        listenable: session,
        builder: (_, __) => AlertDialog(
          title: Text(
            '${sample!['row_count']} Quellzeilen · ${file['filename']}',
          ),
          content: !allowed || captured != epoch
              ? const Notice('Quellzugang wurde entzogen.')
              : SizedBox(
                  width: 750,
                  child: SingleChildScrollView(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        const Notice(
                          'Beispielzeilen prüfen. Keine Spalte wird anhand ihres Namens automatisch zugeordnet.',
                        ),
                        for (final value in businessItems(
                          sample!['samples'],
                        )) ...[_values(value), const Divider()],
                      ],
                    ),
                  ),
                ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(context, false),
              child: const Text('Abbrechen'),
            ),
            FilledButton(
              onPressed: writable && captured == epoch
                  ? () => Navigator.pop(context, true)
                  : null,
              child: const Text('Quellspalten zuordnen'),
            ),
          ],
        ),
      ),
    );
    if (proceed != true || !mounted || captured != epoch) return;
    guard(write: true);
    final kind = config!['kind'],
        fields = (options!['fields'][kind] as List).cast<String>(),
        required = (options!['required_fields'][kind] as List).cast<String>(),
        columns = (sample!['columns'] as List).cast<String>();
    final result = await edit(
      'Zuordnung als neue Fassung speichern',
      'migration-mapping-${item['id']}',
      '/migrations/${item['id']}/mapping',
      [
        for (final name in fields)
          BusinessField(
            name,
            (migrationLabels[name] ?? name) +
                (required.contains(name) ? ' *' : ''),
            type: BusinessInput.choice,
            choices: {
              '': 'Nicht zugeordnet',
              for (final column in columns) column: column,
            },
            initial: previous?['columns'][name] ?? '',
            required: required.contains(name),
          ),
      ],
      (values) => migrationMapping(
        item,
        table: {
          'file_id': file['id'],
          ...config!,
          'columns': Map.fromEntries(
            values.entries.where(
              (entry) => entry.value != '' && entry.value != null,
            ),
          ),
        },
      ),
    );
    if (result != null) await load();
  }

  Future<void> loadPreview() async {
    final item = await read('/migrations/$selectedId'),
        value = await read('/migrations/$selectedId/preview');
    if (value['package_id'] != item['id'] ||
        value['revision'] != item['mapping']['revision'])
      throw const ApiException(
        0,
        'Vorschau gehört nicht zur aktuellen Zuordnungsfassung.',
      );
    setState(() {
      selected = item;
      preview = value;
      report = null;
    });
  }

  Future<void> decide(Map<String, dynamic> entry) async {
    if (session.pending('migration-mapping-$selectedId')) {
      await resolvePending('mapping');
      return;
    }
    final item = selected!,
        choices = businessItems(
          options![entry['kind'] == 'contact' ? 'contacts' : 'projects'],
        );
    final result = await edit(
      'Entscheidung als neue Fassung speichern',
      'migration-mapping-${item['id']}',
      '/migrations/${item['id']}/mapping',
      [
        BusinessField(
          'action',
          'Entscheidung',
          type: BusinessInput.choice,
          initial: 'create',
          choices: {
            'create': 'Bewusst neu anlegen',
            if (entry['kind'] != 'document')
              'link': 'Mit bestehendem Datensatz verknüpfen',
            'skip': 'Diese Zeile ausschließen',
          },
        ),
        BusinessField(
          'target_id',
          'Bestehendes Ziel nur bei Verknüpfung',
          type: BusinessInput.choice,
          initial: '',
          choices: {
            '': 'Kein Ziel',
            for (final value in choices) '${value['id']}': '${value['name']}',
          },
        ),
        BusinessField(
          'reason',
          'Begründung',
          type: BusinessInput.multiline,
          required: true,
          initial: entry['reason'] ?? '',
          hint: businessItems(entry['candidates'])
              .map((v) => v['name'])
              .join(' · '),
        ),
      ],
      (values) => migrationMapping(
        item,
        decision: {
          'kind': entry['kind'],
          'source_id': entry['source_id'],
          'action': values['action'],
          'target_id': values['action'] == 'link' ? values['target_id'] : null,
          'reason': values['reason'],
        },
      ),
    );
    if (result != null) await loadPreview();
  }

  Future<void> removeTable(Map<String, dynamic> table) async {
    if (session.pending('migration-mapping-$selectedId')) {
      await resolvePending('mapping');
      return;
    }
    final item = selected!;
    final result = await edit(
      'Zuordnung ohne diese Tabelle speichern',
      'migration-mapping-${item['id']}',
      '/migrations/${item['id']}/mapping',
      const [
        BusinessField(
          'confirmation',
          'Ich entferne diese Tabellenzuordnung und prüfe danach alle Dublettenentscheidungen erneut. Die Originaldatei bleibt erhalten.',
          type: BusinessInput.toggle,
          required: true,
          initial: false,
        ),
      ],
      (values) {
        if (values['confirmation'] != true)
          throw const FormatException('Entfernen bestätigen.');
        return {
          'revision': item['mapping']['revision'],
          'tables': businessItems(item['mapping']['tables'])
              .where((value) => value['file_id'] != table['file_id'])
              .toList(),
          'decisions': [],
        };
      },
    );
    if (result != null) await load();
  }

  Future<void> resetDecision(Map<String, dynamic> entry) async {
    if (session.pending('migration-mapping-$selectedId')) {
      await resolvePending('mapping');
      return;
    }
    final item = selected!;
    final result = await edit(
      'Entscheidung in neuer Fassung zurücksetzen',
      'migration-mapping-${item['id']}',
      '/migrations/${item['id']}/mapping',
      const [
        BusinessField(
          'confirmation',
          'Ich entferne die frühere Entscheidung und prüfe diese Quellzeile erneut.',
          type: BusinessInput.toggle,
          required: true,
          initial: false,
        ),
      ],
      (values) {
        if (values['confirmation'] != true)
          throw const FormatException('Zurücksetzen bestätigen.');
        return {
          'revision': item['mapping']['revision'],
          'tables': item['mapping']['tables'],
          'decisions': businessItems(item['mapping']['decisions'])
              .where(
                (value) =>
                    value['kind'] != entry['kind'] ||
                    value['source_id'] != entry['source_id'],
              )
              .toList(),
        };
      },
    );
    if (result != null) await loadPreview();
  }

  Future<void> resolvePending(String operation) async {
    final path = '/migrations/$selectedId/$operation',
        key =
            'migration-${const {'files': 'file', 'mapping': 'mapping', 'apply': 'apply', 'reconcile': 'reconcile'}[operation]}-$selectedId';
    final body = session.pendingCommandValues(key, path: path);
    if (body == null) return;
    final description = const JsonEncoder.withIndent('  ').convert({
      for (final entry in body.entries)
        if (entry.key != 'content_base64') entry.key: entry.value,
    });
    final result = await edit(
      'Ursprüngliche Importantwort erneut prüfen',
      key,
      path,
      [
        BusinessField(
          'pending_description',
          'Unveränderter ursprünglicher Auftrag',
          type: BusinessInput.multiline,
          initial: description,
        ),
      ],
      (_) => body,
    );
    if (result != null) await load();
  }

  Future<void> apply() async {
    if (!canApply)
      throw const ApiException(
        403,
        'Die Übernahme benötigt die Geschäftsführung und aktuelle Stammdatenrechte.',
      );
    final item = selected!, value = preview!;
    final result = await edit(
      'Geprüfte Daten einmalig übernehmen',
      'migration-apply-${item['id']}',
      '/migrations/${item['id']}/apply',
      [
        BusinessField(
          'confirmation',
          'Ich habe Quellen, Dubletten, Beziehungen und Beträge geprüft und bestätige genau diese Vorschau.',
          type: BusinessInput.toggle,
          required: true,
          initial: false,
          hint: 'Vorschau: ${value['preview_sha256']}',
        ),
      ],
      (values) =>
          migrationApplyValues(item, value, values['confirmation'] == true),
    );
    if (result != null) {
      await load();
      await loadReport();
    }
  }

  Future<void> loadReport() async {
    final item = await read('/migrations/$selectedId'),
        value = await read('/migrations/$selectedId/report');
    if (value['package_id'] != item['id'] ||
        !_hash(value['report_sha256']) ||
        value['financial_effects'] != false)
      throw const ApiException(0, 'Übernahmebericht ist nicht vollständig.');
    setState(() {
      selected = item;
      report = value;
      preview = null;
    });
  }

  Future<void> reconcile() async {
    final item = selected!, value = report!;
    final result = await edit(
      'Abgleich unveränderlich festhalten',
      'migration-reconcile-${item['id']}',
      '/migrations/${item['id']}/reconcile',
      const [
        BusinessField(
          'note',
          'Abgleichvermerk und verbleibende Lücken',
          type: BusinessInput.multiline,
          required: true,
        ),
        BusinessField(
          'confirmation',
          'Ich bestätige den Abgleich dieses deklarierten Exportumfangs mit den Originalen.',
          type: BusinessInput.toggle,
          required: true,
          initial: false,
        ),
      ],
      (values) => {...values, 'report_sha256': value['report_sha256']},
    );
    if (result != null) await loadReport();
  }

  Future<void> exportReport() async {
    guard();
    final captured = epoch,
        value = await read('/migrations/$selectedId/report');
    if (value['package_id'] != selectedId ||
        !_hash(value['report_sha256']) ||
        value['financial_effects'] != false)
      throw const ApiException(0, 'Bericht konnte nicht bestätigt werden.');
    final bytes = Uint8List.fromList(
          utf8.encode(const JsonEncoder.withIndent('  ').convert(value)),
        ),
        digest = _hex((await Sha256().hash(bytes)).bytes);
    guard();
    if (captured != epoch) return;
    await (widget.exporter ?? exportMailAttachment)(
      context,
      VerifiedMailAttachment(
        bytes: bytes,
        filename: 'import-$selectedId.json',
        mediaType: 'application/json',
        sha256: digest,
      ),
      () => mounted && allowed && epoch == captured,
    );
  }

  Future<void> openProject(String projectId) async {
    guard();
    final captured = epoch;
    final value = businessItems(await session.api.call('/api/projects'))
        .where((item) => item['id'] == projectId)
        .firstOrNull;
    guard();
    if (captured != epoch || value == null)
      throw const ApiException(403, 'Projektbezug ist nicht mehr freigegeben.');
    widget.onProject?.call(value);
  }

  Future<void> openContact(String customerId) async {
    guard();
    await Navigator.push<void>(
      context,
      MaterialPageRoute(
        builder: (_) => BusinessContactPage(
          session: session,
          id: customerId,
          onProject: widget.onProject,
        ),
      ),
    );
  }

  Widget _values(Map<String, dynamic> values) => Column(
    crossAxisAlignment: CrossAxisAlignment.start,
    children: [
      for (final entry in values.entries)
        Padding(
          padding: const EdgeInsets.symmetric(vertical: 4),
          child: SelectableText(
            '${migrationLabels[entry.key] ?? entry.key}: ${entry.value ?? 'Nicht angegeben'}',
          ),
        ),
    ],
  );
  Widget section(String title, List<Widget> children) => Card(
    child: Padding(
      padding: const EdgeInsets.all(20),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Text(title, style: Theme.of(context).textTheme.titleLarge),
          const SizedBox(height: 12),
          ...children,
        ],
      ),
    ),
  );
  Widget sourceRows(Map<String, dynamic> data, bool editable) => Column(
    children: [
      for (final entry in businessItems(data['rows']))
        Card(
          child: ExpansionTile(
            title: Text(
              '${migrationKinds[entry['kind']]} · ${entry['source_id'] ?? 'Quellkennung fehlt'}',
            ),
            subtitle: Text(
              'Datei ${businessItems(selected!['files']).where((file) => file['id'] == entry['file_id']).firstOrNull?['filename'] ?? entry['file_id']} · Zeile ${entry['row']} · ${const {'create': 'Neu übernehmen', 'link': 'Verknüpfen', 'reuse': 'Bereits übernommen', 'skip': 'Ausschließen', 'review': 'Entscheidung erforderlich'}[entry['action']] ?? entry['action']}',
            ),
            children: [
              Padding(
                padding: const EdgeInsets.all(16),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    _values(businessMap(entry['values'])),
                    SelectableText('Quellhash: ${entry['source_sha256']}'),
                    if (entry['target_id'] != null)
                      SelectableText('Ziel: ${entry['target_id']}'),
                    for (final issue in businessItems(entry['errors']))
                      Notice('${issue['message']}', error: true),
                    if ('${entry['reason'] ?? ''}'.isNotEmpty)
                      Text('${entry['reason']}'),
                    if (editable &&
                        writable &&
                        businessItems(selected!['mapping']['decisions']).any(
                          (value) =>
                              value['kind'] == entry['kind'] &&
                              value['source_id'] == entry['source_id'],
                        ))
                      OutlinedButton(
                        onPressed: () => attempt(() => resetDecision(entry)),
                        child: const Text('Entscheidung zurücksetzen'),
                      ),
                    if (!editable && entry['customer_id'] != null)
                      OutlinedButton(
                        onPressed: () =>
                            attempt(() => openContact(entry['customer_id'])),
                        child: const Text('Zielkontakt öffnen'),
                      ),
                    if (!editable &&
                        entry['project_id'] != null &&
                        widget.onProject != null)
                      OutlinedButton(
                        onPressed: () =>
                            attempt(() => openProject(entry['project_id'])),
                        child: const Text('Verknüpftes Projekt öffnen'),
                      ),
                    if (!editable &&
                        entry['original_file_id'] != null &&
                        businessItems(selected!['files']).any(
                          (file) => file['id'] == entry['original_file_id'],
                        ))
                      OutlinedButton(
                        onPressed: () => attempt(
                          () => download(
                            businessItems(selected!['files']).firstWhere(
                              (file) => file['id'] == entry['original_file_id'],
                            ),
                          ),
                        ),
                        child: const Text('Dokumentoriginal herunterladen'),
                      ),
                    if (editable &&
                        writable &&
                        '${entry['source_id'] ?? ''}'.isNotEmpty)
                      OutlinedButton(
                        onPressed: () => attempt(() => decide(entry)),
                        child: const Text('Übernahmeentscheidung'),
                      ),
                  ],
                ),
              ),
            ],
          ),
        ),
    ],
  );
  Widget countsAndTotals(Map<String, dynamic> data) => Column(
    crossAxisAlignment: CrossAxisAlignment.stretch,
    children: [
      _values({
        for (final entry in businessMap(data['counts']).entries)
          const {
                    'source': 'Quellzeilen',
                    'create': 'Neu',
                    'link': 'Verknüpft',
                    'reuse': 'Bereits übernommen',
                    'skip': 'Ausgeschlossen',
                    'errors': 'Fehler',
                  }[entry.key] ??
                  entry.key:
              entry.value,
      }),
      for (final value in businessItems(data['totals']))
        section(
          '${migrationDocumentKinds[value['kind']] ?? value['kind']} · ${value['currency'] ?? 'Währung fehlt'}',
          [
            Text(
              'Quelle netto / Steuer / brutto: ${['net', 'tax', 'gross'].map((key) => migrationAmount(value['source'][key], value['source']['${key}_exact'])).join(' / ')}',
            ),
            Text(
              'Ausgewählt netto / Steuer / brutto: ${['net', 'tax', 'gross'].map((key) => migrationAmount(value['selected'][key], value['selected']['${key}_exact'])).join(' / ')}',
            ),
            Text(
              'Zeilen mit fehlenden Beträgen Quelle / Auswahl: ${value['source']['missing']} / ${value['selected']['missing']}',
            ),
          ],
        ),
    ],
  );
  Widget packageView() {
    final item = selected!, staged = item['status'] == 'staged';
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Text(
          '${item['label']}',
          style: Theme.of(context).textTheme.headlineMedium,
        ),
        _values({
          'Quelle': item['source_system'],
          'Quellkonto': item['source_account'],
          'Zeitraum':
              '${item['period_from'] ?? 'Nicht angegeben'} – ${item['period_to'] ?? 'Nicht angegeben'}',
          'Umfang': item['scope'],
          'Zuordnungsfassung': item['mapping']['revision'],
        }),
        for (final operation in ['files', 'mapping', 'apply', 'reconcile'])
          if (session.pending(
            'migration-${const {'files': 'file', 'mapping': 'mapping', 'apply': 'apply', 'reconcile': 'reconcile'}[operation]}-${item['id']}',
          ))
            OutlinedButton(
              onPressed: writable
                  ? () => attempt(() => resolvePending(operation))
                  : null,
              child: Text('Ursprüngliche Importantwort prüfen · $operation'),
            ),
        section('1 · Originaldateien', [
          if (staged && writable)
            FilledButton(
              onPressed: () => attempt(upload),
              child: const Text('Originaldatei hinzufügen'),
            ),
          for (final file in businessItems(item['files']))
            Card(
              child: Padding(
                padding: const EdgeInsets.all(12),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text('${file['filename']}'),
                    SelectableText(
                      '${file['size']} Bytes · SHA-256 ${file['sha256']}',
                    ),
                    Wrap(
                      spacing: 8,
                      children: [
                        TextButton(
                          onPressed: () => attempt(() => download(file)),
                          child: const Text('Original herunterladen'),
                        ),
                        if (staged && writable)
                          TextButton(
                            onPressed: () => attempt(
                              () => configure(
                                file,
                                businessItems(item['mapping']['tables'])
                                    .where(
                                      (table) => table['file_id'] == file['id'],
                                    )
                                    .firstOrNull,
                              ),
                            ),
                            child: const Text('Als Datentabelle zuordnen'),
                          ),
                      ],
                    ),
                  ],
                ),
              ),
            ),
        ]),
        section('2 · Gespeicherte Feldzuordnung', [
          for (final table in businessItems(item['mapping']['tables']))
            ExpansionTile(
              title: Text(
                '${migrationKinds[table['kind']]} · ${businessItems(item['files']).where((file) => file['id'] == table['file_id']).firstOrNull?['filename']}',
              ),
              children: [
                _values(businessMap(table['columns'])),
                if (staged &&
                    writable &&
                    businessItems(item['mapping']['tables']).length > 1)
                  OutlinedButton(
                    onPressed: () => attempt(() => removeTable(table)),
                    child: const Text('Tabellenzuordnung entfernen'),
                  ),
              ],
            ),
        ]),
        if (staged && item['mapping']['revision'] > 0)
          FilledButton(
            onPressed: () => attempt(loadPreview),
            child: const Text('3 · Übernahmevorschau prüfen'),
          ),
        if (item['report'] != null)
          FilledButton(
            onPressed: () => attempt(loadReport),
            child: const Text('Übernahmebericht und Abgleich'),
          ),
        if (preview != null)
          section('Übernahmevorschau', [
            Notice(
              preview!['ready'] == true
                  ? 'Geprüfte Zeilen sind übernahmefähig.'
                  : 'Vor der Übernahme Fehler und Dubletten klären.',
            ),
            SelectableText('Vorschau: ${preview!['preview_sha256']}'),
            countsAndTotals(preview!),
            for (final issue in businessItems(preview!['errors']))
              Notice('${issue['message']}', error: true),
            sourceRows(preview!, true),
            if (preview!['ready'] == true && canApply)
              FilledButton(
                onPressed: () => attempt(apply),
                child: const Text('Geprüfte Vorschau übernehmen'),
              ),
          ]),
        if (report != null)
          section('Übernahmebericht und Abgleich', [
            SelectableText('Bericht: ${report!['report_sha256']}'),
            const Notice(
              'Keine finanzielle Buchungswirkung. Der Abgleich bestätigt nur den deklarierten Umfang.',
            ),
            countsAndTotals(report!),
            sourceRows(report!, false),
            if (item['reconciliation'] != null)
              Notice('Abgleich bestätigt: ${item['reconciliation']['note']}')
            else if (writable)
              FilledButton(
                onPressed: () => attempt(reconcile),
                child: const Text(
                  'Abgleich des deklarierten Umfangs bestätigen',
                ),
              ),
            OutlinedButton(
              onPressed: () => attempt(exportReport),
              child: const Text('Bericht als JSON exportieren'),
            ),
          ]),
      ],
    );
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(
      title: const Text('Kontrollierter Dateiimport'),
      actions: [
        if (allowed)
          IconButton(
            onPressed: load,
            icon: const Icon(Icons.refresh),
            tooltip: 'Neu laden',
          ),
      ],
    ),
    body: !allowed
        ? const Center(
            child: Text('Die globalen Importrechte sind nicht mehr verfügbar.'),
          )
        : ListView(
            padding: const EdgeInsets.all(24),
            children: [
              const Notice(
                'Smartplan-Dateiimport v1: Originale und CSV/JSON-Felder werden ausdrücklich geprüft. Anbieterprofile für HERO/sevdesk sind nicht für Ihren Export bestätigt. Historische Dokumente erzeugen keine neuen Rechnungen, Zahlungen oder EÜR-Buchungen.',
              ),
              if (error != null) Notice(error!, error: true),
              if (loading) const LinearProgressIndicator(),
              if (selectedId != null)
                Align(
                  alignment: Alignment.centerLeft,
                  child: TextButton(
                    onPressed: () {
                      selectedId = null;
                      selected = null;
                      preview = null;
                      report = null;
                      load();
                    },
                    child: const Text('Alle Importpakete'),
                  ),
                ),
              if (selectedId == null) ...[
                if (writable)
                  FilledButton(
                    onPressed: () => attempt(create),
                    child: const Text('Importpaket anlegen'),
                  ),
                for (final item in packages)
                  Card(
                    child: ListTile(
                      title: Text('${item['label']}'),
                      subtitle: Text(
                        '${item['source_system']} · ${item['source_account']} · ${const {'staged': 'Vorbereitet', 'applied': 'Übernommen', 'reconciled': 'Abgeglichen'}[item['status']]}',
                      ),
                      trailing: const Icon(Icons.chevron_right),
                      onTap: () {
                        selectedId = item['id'];
                        load();
                      },
                    ),
                  ),
              ] else if (selected != null)
                packageView(),
            ],
          ),
  );
}

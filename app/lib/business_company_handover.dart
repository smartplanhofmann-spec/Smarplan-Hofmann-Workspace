import 'dart:convert';
import 'dart:typed_data';

import 'package:cryptography/cryptography.dart';
import 'package:flutter/material.dart';

import 'api.dart';
import 'business_session.dart';
import 'business_widgets.dart';
import 'design.dart';
import 'mail_attachment_widgets.dart';

const handoverMaxBytes = 128 * 1024 * 1024;
const handoverChecks = {
  'export_opened': 'Archiv selbst geöffnet und geprüft',
  'retention_reviewed': 'Aufbewahrung und Löschfristen fachlich geprüft',
  'recipient_handover_confirmed':
      'Tatsächliche Übergabe an benannte Empfänger bestätigt',
  'provider_revocations_reviewed':
      'Anbieterzugänge und erforderliche Widerrufe geprüft',
  'local_access_reviewed': 'Lokale, Portal- und Importzugänge geprüft',
  'backup_plan_reviewed':
      'Weitere Sicherung und Wiederherstellungsplan geprüft',
  'service_shutdown_reviewed':
      'Betriebsstilllegung mit Verantwortlichen geprüft',
};
final _id = RegExp(r'^[a-f0-9]{32}$'), _hash = RegExp(r'^[a-f0-9]{64}$');
Map<String, dynamic> _copy(dynamic v) => businessMap(jsonDecode(jsonEncode(v)));
dynamic _ordered(dynamic v) => v is List
    ? v.map(_ordered).toList()
    : v is Map
    ? {
        for (final k in v.keys.map((k) => '$k').toList()..sort())
          k: _ordered(v[k]),
      }
    : v;
bool _same(dynamic a, dynamic b) =>
    jsonEncode(_ordered(a)) == jsonEncode(_ordered(b));
Never _fail(String text, [int status = 0]) => throw ApiException(status, text);
String _required(dynamic value, String label, int max) {
  final text = '${value ?? ''}'.trim();
  if (text.isEmpty || text.length > max) _fail('$label vollständig angeben.');
  return text;
}

Map<String, dynamic> handoverMetadata(dynamic raw, String instance) {
  final v = businessMap(raw);
  if (!_id.hasMatch('${v['id']}') ||
      v['instance_id'] != instance ||
      !_id.hasMatch(instance) ||
      !_hash.hasMatch('${v['sha256']}') ||
      !_hash.hasMatch('${v['catalog_sha256']}') ||
      v['size'] is! int ||
      v['size'] < 1 ||
      v['size'] > handoverMaxBytes ||
      [
        'table_count',
        'row_count',
        'file_count',
      ].any((k) => v[k] is! int || v[k] < 0))
    _fail(
      'Der Archivnachweis gehört nicht eindeutig zu dieser Unternehmensinstanz.',
    );
  return v;
}

Map<String, dynamic> handoverState(dynamic raw) {
  final v = businessMap(raw);
  if (v['ready'] is! bool ||
      v['instance_id'] != null && !_id.hasMatch('${v['instance_id']}') ||
      !_hash.hasMatch('${v['catalog_sha256']}') ||
      v['inventory'] is! List ||
      v['exports'] is! List ||
      v['blockers'] is! List ||
      v['owner_only'] != true ||
      v['deletion_executed'] != false ||
      v['revocations_executed'] != false ||
      v['database_restore_supported'] != false ||
      v['external_only_files_downloaded'] != false ||
      !_same(
        (v['checklist_keys'] as List? ?? []).map((k) => '$k').toList()..sort(),
        handoverChecks.keys.toList()..sort(),
      ))
    _fail('Die Bestandsaufnahme konnte nicht vollständig bestätigt werden.');
  for (final a in v['exports']) {
    handoverMetadata(a, '${v['instance_id']}');
  }
  if (v['ready'] == true &&
      (v['instance_id'] == null || (v['blockers'] as List).isNotEmpty))
    _fail('Die Exportbereitschaft widerspricht der Bestandsaufnahme.');
  return v;
}

Map<String, dynamic> handoverExportData(
  Map<String, dynamic> state,
  Map<String, dynamic> values,
) {
  handoverState(state);
  if (state['ready'] != true)
    _fail('Die Bestandsaufnahme ist noch nicht exportbereit.', 409);
  if (values['confirmation'] != true ||
      values['sensitive_data_confirmed'] != true)
    _fail('Archiv und sensible Unternehmensdaten ausdrücklich bestätigen.');
  return {
    'instance_id': state['instance_id'],
    'catalog_sha256': state['catalog_sha256'],
    'reason': _required(values['reason'], 'Exportgrund', 1000),
    'confirmation': true,
    'sensitive_data_confirmed': true,
  };
}

Map<String, dynamic> handoverReviewData(
  Map<String, dynamic> state,
  Map<String, dynamic> archive,
  Map<String, dynamic> values,
) {
  handoverMetadata(archive, '${state['instance_id']}');
  if (values['confirmation'] != true ||
      handoverChecks.keys.any((k) => values[k] is! bool))
    _fail('Prüfpunkte und Dokumentation ausdrücklich bewerten.');
  return {
    'instance_id': state['instance_id'],
    'expected_revision': state['exit_review']?['revision'] ?? 0,
    'export_id': archive['id'],
    'export_sha256': archive['sha256'],
    'checks': {for (final k in handoverChecks.keys) k: values[k]},
    'evidence': _required(
      values['evidence'],
      'Nachweise und Verantwortliche',
      5000,
    ),
    'reason': _required(values['reason'], 'Prüfgrund', 1000),
    'confirmation': true,
  };
}

void Function(dynamic) handoverValidator(
  Map<String, dynamic> body, {
  bool review = false,
  String? actor,
}) {
  final b = _copy(body);
  return (raw) {
    final v = businessMap(raw);
    if (review) {
      final complete = businessMap(b['checks']).values.every((x) => x == true);
      if (!_id.hasMatch('${v['id']}') ||
          v['instance_id'] != b['instance_id'] ||
          v['revision'] != b['expected_revision'] + 1 ||
          v['export_id'] != b['export_id'] ||
          v['export_sha256'] != b['export_sha256'] ||
          !_same(v['checks'], b['checks']) ||
          v['reason'] != b['reason'] ||
          v['evidence'] != b['evidence'] ||
          v['attested_only'] != true ||
          v['revocations_executed'] != false ||
          v['deletion_executed'] != false ||
          v['status'] !=
              (complete ? 'ready_for_operator_review' : 'in_progress'))
        _fail('Die Prüfbestätigung passt nicht zum unveränderten Auftrag.');
    } else {
      handoverMetadata(v, b['instance_id']);
      if (v['reason'] != b['reason'] ||
          v['catalog_sha256'] != b['catalog_sha256'])
        _fail(
          'Die Archivbestätigung passt nicht zur geprüften Bestandsaufnahme.',
        );
    }
    if (actor != null && v['created_by'] != actor)
      _fail('Die Bestätigung gehört nicht zum Auftraggeber.');
  };
}

Future<VerifiedMailAttachment> handoverArchiveAttachment(
  Uint8List bytes,
  Map<String, dynamic> expected,
  Map<String, dynamic> proof,
) async {
  handoverMetadata(expected, expected['instance_id']);
  if (proof['valid'] != true ||
      [
        'sha256',
        'instance_id',
        'table_count',
        'row_count',
        'file_count',
      ].any((k) => proof[k] != expected[k]))
    _fail('Die unabhängige Archivprüfung passt nicht zum gewählten Export.');
  if (bytes.length != expected['size'] ||
      bytes.length > handoverMaxBytes ||
      bytes.length < 4 ||
      bytes[0] != 80 ||
      bytes[1] != 75 ||
      bytes[2] != 3 ||
      bytes[3] != 4)
    _fail('Archivformat oder Dateigröße stimmt nicht.');
  final digest = await Sha256().hash(bytes),
      hash = digest.bytes
          .map((x) => x.toRadixString(16).padLeft(2, '0'))
          .join();
  if (hash != expected['sha256']) _fail('Die Archivprüfsumme stimmt nicht.');
  return VerifiedMailAttachment(
    bytes: bytes,
    filename: 'smartplan-company-${expected['id']}.zip',
    mediaType: 'application/zip',
    sha256: hash,
  );
}

class BusinessCompanyHandoverPage extends StatefulWidget {
  const BusinessCompanyHandoverPage({
    super.key,
    required this.session,
    this.exporter,
  });
  final BusinessSession session;
  final MailAttachmentExporter? exporter;
  @override
  State<BusinessCompanyHandoverPage> createState() =>
      _BusinessCompanyHandoverPageState();
}

class _BusinessCompanyHandoverPageState
    extends State<BusinessCompanyHandoverPage> {
  BusinessSession get session => widget.session;
  Map<String, dynamic>? state;
  String? error, owner;
  Object? ownerGeneration;
  bool busy = false;
  bool get available =>
      session.allowed &&
      session.hasFeature('company_handover') &&
      session.hasModule('company_handover') &&
      session.projectId == null;
  bool get writable => available && owner != null && !session.readonly;
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
      if (!available ||
          ownerGeneration != null && ownerGeneration != session.generation) {
        state = null;
        owner = null;
      }
    });
  }

  Future<Map<String, dynamic>> fresh({
    String? instance,
    bool write = false,
  }) async {
    if (!available) _fail('Die aktuelle Unternehmensfreigabe fehlt.', 403);
    final generation = session.generation,
        me = businessMap(await session.api.call('/api/me'));
    if (me['role'] != 'owner') {
      owner = null;
      state = null;
      _fail('Diese Ansicht erfordert die aktuelle Geschäftsführung.', 403);
    }
    await session.load();
    if (!available ||
        write && session.readonly ||
        generation != session.generation)
      _fail('Die Sitzung oder Freigabe wurde geändert.', 403);
    final result = handoverState(await session.read('/company-handover'));
    if (instance != null && result['instance_id'] != instance)
      _fail(
        'Die Unternehmensinstanz wurde gewechselt. Der ursprüngliche Auftrag bleibt erhalten.',
        409,
      );
    owner = '${me['id']}';
    ownerGeneration = session.generation;
    return result;
  }

  Future<void> load() async {
    try {
      final result = await fresh();
      if (mounted)
        setState(() {
          state = result;
          error = null;
        });
    } catch (e) {
      if (mounted)
        setState(() {
          error = '$e';
          state = null;
        });
    }
  }

  Future<void> present(Future<void> Function() task) async {
    try {
      await task();
    } catch (e) {
      if (mounted) setState(() => error = '$e');
    }
  }

  Future<void> action(Future<void> Function() task) async {
    if (busy) return;
    setState(() => busy = true);
    try {
      await task();
    } catch (e) {
      if (mounted) setState(() => error = '$e');
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  String key(bool review) => 'company-handover-${review ? 'review' : 'export'}';
  String route(bool review) =>
      '/company-handover/${review ? 'exit-reviews' : 'exports'}';
  Future<void> retry(bool review) async {
    await session.repeatCompanyHandoverCommand(review: review);
    await load();
  }

  Future<void> edit({Map<String, dynamic>? archive}) async {
    final review = archive != null, initial = _copy(state!);
    await fresh(instance: initial['instance_id'], write: true);
    if (!mounted) return;
    await showDialog<bool>(
      context: context,
      builder: (_) => BusinessEditor(
        session: session,
        title: review
            ? 'Ausstiegsprüfung dokumentieren'
            : 'Unternehmensarchiv erstellen',
        pendingKey: key(review),
        readAllowed: () => writable,
        fields: [
          if (review) ...[
            for (final e in handoverChecks.entries)
              BusinessField(
                e.key,
                e.value,
                type: BusinessInput.toggle,
                initial: false,
              ),
            const BusinessField(
              'evidence',
              'Nachweise und Verantwortliche',
              type: BusinessInput.multiline,
              required: true,
            ),
          ] else
            const BusinessField(
              'sensitive_data_confirmed',
              'Ich bestätige den Export sensibler Unternehmens-, Finanz- und Personaldaten.',
              type: BusinessInput.toggle,
              initial: false,
            ),
          BusinessField(
            'reason',
            review ? 'Prüfgrund' : 'Exportgrund',
            type: BusinessInput.multiline,
            required: true,
          ),
          BusinessField(
            'confirmation',
            review
                ? 'Ich bestätige ausschließlich tatsächlich geprüfte Punkte.'
                : 'Ich habe Umfang, Auslassungen und Aufbewahrung geprüft.',
            type: BusinessInput.toggle,
            initial: false,
          ),
        ],
        saveLabel: review
            ? 'Prüfstand dokumentieren'
            : 'Archiv verbindlich erstellen',
        onSave: (values) async {
          if (session.pending(key(review))) {
            await session.repeatCompanyHandoverCommand(review: review);
            return;
          }
          await fresh(instance: initial['instance_id'], write: true);
          final body = review
              ? handoverReviewData(initial, archive, values)
              : handoverExportData(initial, values);
          await session.command(
            key(review),
            route(review),
            body,
            validateResult: handoverValidator(
              body,
              review: review,
              actor: owner,
            ),
          );
        },
      ),
    );
    if (mounted) await load();
  }

  Future<void> download(Map<String, dynamic> archive) async {
    await fresh(instance: archive['instance_id']);
    final generation = session.generation;
    final metadata = handoverMetadata(
      await session.read('/company-handover/exports/${archive['id']}'),
      archive['instance_id'],
    );
    if ([
      'id',
      'sha256',
      'size',
      'catalog_sha256',
      'table_count',
      'row_count',
      'file_count',
    ].any((k) => metadata[k] != archive[k]))
      _fail('Das gespeicherte Archiv wurde verändert.');
    final proof = businessMap(
      await session.read('/company-handover/exports/${archive['id']}/verify'),
    );
    final bytes = await session.api.bytes(
      session.path('/company-handover/exports/${archive['id']}/archive'),
      mediaType: 'application/zip',
      maxBytes: handoverMaxBytes,
    );
    final file = await handoverArchiveAttachment(bytes, archive, proof);
    await fresh(instance: archive['instance_id']);
    if (!mounted || !available || generation != session.generation) return;
    await (widget.exporter ?? exportMailAttachment)(
      context,
      file,
      () =>
          mounted &&
          available &&
          owner != null &&
          generation == session.generation,
    );
  }

  Widget card(String title, List<Widget> children) => Card(
    child: Padding(
      padding: const EdgeInsets.all(20),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(title, style: Theme.of(context).textTheme.titleLarge),
          const SizedBox(height: 12),
          ...children,
        ],
      ),
    ),
  );
  Future<void> inventory() async {
    final snapshot = _copy(state!);
    await fresh(instance: snapshot['instance_id']);
    if (!mounted) return;
    await Navigator.push<void>(
      context,
      MaterialPageRoute(
        builder: (_) => Scaffold(
          appBar: AppBar(title: const Text('Dateninventar und Auslassungen')),
          body: AnimatedBuilder(
            animation: session,
            builder: (context, _) =>
                !available ||
                    owner == null ||
                    ownerGeneration != session.generation
                ? const Notice('Zugang nicht mehr verfügbar.', error: true)
                : ListView(
                    padding: const EdgeInsets.all(16),
                    children: [
                      const Notice(
                        'Aufbewahrungsfristen einzeln prüfen. Fehlende Fristen sind keine Löschfreigabe.',
                      ),
                      for (final raw in snapshot['inventory'])
                        ExpansionTile(
                          title: Text(
                            '${raw['table']} · ${raw['row_count']} Datensätze',
                          ),
                          subtitle: Text(
                            raw['included'] == true
                                ? 'Im Archiv enthalten'
                                : 'Ausgeschlossen',
                          ),
                          children: [
                            ListTile(
                              title: Text(
                                '${raw['purpose']} · ${raw['category']}',
                              ),
                              subtitle: Text(
                                'Aufbewahrung: ${raw['retention_basis']} · ${raw['retention_days'] ?? 'keine pauschale'} Tage\nAuslassung: ${raw['exclusion_reason'] ?? 'keine'}\nSpalten: ${(raw['omitted_columns'] as List? ?? []).join(', ')}',
                              ),
                            ),
                            if (raw['retention_rule'] != null)
                              ListTile(
                                title: Text(
                                  '${raw['retention_rule']['legal_basis']}',
                                ),
                                subtitle: Text(
                                  '${raw['retention_rule']['scope']}\nBeispiel: letzte belegte Zahlung ${raw['retention_rule']['example']['last_payment_date']}, aufbewahren bis ${raw['retention_rule']['example']['retain_through']}. Weitere Fristen und Sperren gesondert prüfen; keine pauschale Frist für unbezahlte Läufe oder Personalakten.',
                                ),
                              ),
                          ],
                        ),
                    ],
                  ),
          ),
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final data = state;
    return Scaffold(
      appBar: AppBar(
        title: const Text('Unternehmensübergabe'),
        actions: [
          IconButton(
            onPressed: busy ? null : load,
            icon: const Icon(Icons.refresh),
            tooltip: 'Neu prüfen',
          ),
        ],
      ),
      body: ListView(
        padding: const EdgeInsets.all(20),
        children: [
          const Notice(
            'Portable Unternehmensdaten und dokumentierte Ausstiegsprüfung. Das Archiv ist kein Datenbank-Restore. Diese Oberfläche überträgt keine Daten an Empfänger, widerruft keine Zugänge, löscht nichts und stellt keinen Dienst ab.',
          ),
          if (error != null) Notice(error!, error: true),
          if (busy) const LinearProgressIndicator(),
          if (data != null && available) ...[
            for (final b in data['blockers'])
              Notice('${b['message']}', error: true),
            for (final review in [false, true])
              if (session.pending(key(review)))
                card('Unbestätigter Auftrag', [
                  const Text(
                    'Der ursprüngliche Inhalt bleibt in dieser Sitzung erhalten.',
                  ),
                  FilledButton(
                    onPressed: busy || !writable
                        ? null
                        : () => action(() => retry(review)),
                    child: Text(
                      'Ursprünglichen ${review ? 'Prüfstand' : 'Exportauftrag'} erneut senden',
                    ),
                  ),
                ]),
            card('Bestandsaufnahme', [
              Text(
                '${(data['inventory'] as List).length} Datenbereiche · ${(data['inventory'] as List).where((v) => v['included'] == true).length} im Archiv',
              ),
              const Text(
                'Grenzen: 128 MiB ZIP, 256 MiB Quelldaten, 250.000 Datensätze. Bei Überschreitung wird keine Teilsicherung gespeichert.',
              ),
              TextButton(
                onPressed: busy ? null : () => present(inventory),
                child: const Text('Inventar und Auslassungen prüfen'),
              ),
              if (data['ready'] == true &&
                  writable &&
                  !session.pending(key(false)))
                FilledButton(
                  onPressed: busy ? null : () => present(() => edit()),
                  child: const Text('Unternehmensarchiv erstellen'),
                ),
            ]),
            card('Zugänge und Zuständigkeiten', [
              for (final entry in const {
                'users': 'Benutzer',
                'portal_grants': 'Portalzugänge',
                'integrations': 'Anbieter',
                'offline_access': 'Offlinezugänge',
                'inbound_access': 'Importzugänge',
              }.entries)
                ExpansionTile(
                  title: Text(
                    '${entry.value}: ${(data['access_review']?[entry.key] as List? ?? []).length}',
                  ),
                  children: [
                    for (final item
                        in data['access_review']?[entry.key] as List? ?? [])
                      ListTile(
                        title: Text(
                          (item as Map).entries
                              .map((v) => '${v.key}: ${v.value ?? '–'}')
                              .join('\n'),
                        ),
                      ),
                  ],
                ),
              const Text(
                'Externe Empfänger zusätzlich anhand Korrespondenz und Anbieteraccounts prüfen. Keine Zugänge wurden widerrufen.',
              ),
            ]),
            card('Gespeicherte Archive', [
              if ((data['exports'] as List).isEmpty)
                const Text('Noch kein Unternehmensarchiv gespeichert.'),
              for (final raw in data['exports'])
                Builder(
                  builder: (context) {
                    final a = businessMap(raw);
                    return Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          '${businessDate(a['created_at'])} · ${a['reason']}',
                        ),
                        Text(
                          '${a['table_count']} Tabellen · ${a['row_count']} Datensätze · ${a['file_count']} Dateien · ${(a['size'] / 1024).toStringAsFixed(1)} KiB',
                        ),
                        Wrap(
                          spacing: 8,
                          children: [
                            TextButton(
                              onPressed: busy
                                  ? null
                                  : () => action(() => download(a)),
                              child: const Text('ZIP prüfen und herunterladen'),
                            ),
                            if (writable && !session.pending(key(true)))
                              TextButton(
                                onPressed: busy
                                    ? null
                                    : () => present(() => edit(archive: a)),
                                child: const Text(
                                  'Ausstiegsprüfung dokumentieren',
                                ),
                              ),
                          ],
                        ),
                        const Divider(),
                      ],
                    );
                  },
                ),
            ]),
            if (data['exit_review'] != null)
              card('Letzter dokumentierter Prüfstand', [
                Text(
                  'Fassung ${data['exit_review']['revision']} · ${data['exit_review']['status'] == 'ready_for_operator_review' ? 'Alle Prüfpunkte bestätigt; Operatorprüfung ausstehend' : 'Prüfung in Arbeit'}',
                ),
                for (final e in handoverChecks.entries)
                  ListTile(
                    title: Text(e.value),
                    subtitle: Text(
                      data['exit_review']['checks'][e.key] == true
                          ? 'Bestätigt'
                          : 'Offen',
                    ),
                  ),
                Text('${data['exit_review']['evidence']}'),
                Text('${data['exit_review']['reason']}'),
                const Notice(
                  'Dokumentierte Selbstauskunft; keine Löschung oder Widerrufe ausgeführt.',
                ),
              ]),
          ] else if (error == null)
            const LinearProgressIndicator(),
        ],
      ),
    );
  }
}

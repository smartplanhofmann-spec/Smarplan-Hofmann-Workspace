import 'package:flutter/material.dart';

import 'business_documentation.dart';
import 'business_session.dart';
import 'business_widgets.dart';
import 'design.dart';
import 'mail_attachment_preview.dart';
import 'mail_attachment_widgets.dart' show exportMailAttachment;
import 'offline_plans.dart';
import 'signature_editor.dart';

/// One service-report list for the business archive and this device's captures.
/// Captures retain their IDs when the server archives them; they are never
/// copied into the historical, separate legacy report store.
class BusinessServiceReportsPage extends StatefulWidget {
  const BusinessServiceReportsPage({
    super.key,
    required this.session,
    required this.repository,
  });
  final BusinessSession session;
  final OfflinePlans repository;
  @override
  State<BusinessServiceReportsPage> createState() =>
      _BusinessServiceReportsPageState();
}

class _BusinessServiceReportsPageState
    extends State<BusinessServiceReportsPage> {
  List<Map<String, dynamic>> remote = [];
  String? error;
  int epoch = 0;
  String? get project => widget.session.projectId;
  bool get allowed =>
      project != null &&
      !widget.session.denied &&
      (widget.session.offlineMode || widget.session.can('documents.read')) &&
      widget.repository.canAccessServiceReports(project!);
  bool get writable =>
      allowed &&
      widget.repository.serviceReportsWritable &&
      (widget.session.offlineMode ||
          widget.session.canWrite('documents.write'));
  @override
  void initState() {
    super.initState();
    widget.session.addListener(changed);
    widget.repository.addListener(changed);
    load();
  }

  @override
  void dispose() {
    epoch++;
    widget.session.removeListener(changed);
    widget.repository.removeListener(changed);
    super.dispose();
  }

  void changed() {
    if (!mounted) return;
    if (!allowed) {
      epoch++;
      remote = [];
    }
    setState(() {});
  }

  Future<void> load() async {
    if (!allowed || !widget.session.can('documents.read')) return;
    final current = ++epoch;
    try {
      final result = businessItems(
        await widget.session.read(widget.session.query('/service-reports')),
      );
      if (mounted && current == epoch && allowed)
        setState(() {
          remote = result;
          error = null;
        });
    } catch (e) {
      if (mounted && current == epoch && allowed) setState(() => error = '$e');
    }
  }

  Future<void> open([Map<String, dynamic>? row]) async {
    if (!allowed || (row == null && !writable)) return;
    final local = row == null || row['content'] is Map;
    await Navigator.push<void>(
      context,
      MaterialPageRoute(
        builder: (_) => local
            ? OfflineServiceReportPage(
                session: widget.session,
                repository: widget.repository,
                project: project!,
                id: row?['id'],
              )
            : BusinessOperationDocumentPage(
                session: widget.session,
                path: '/service-reports',
                id: row['id'],
                fields: const [
                  BusinessField('title', 'Titel', required: true),
                  BusinessField(
                    'description',
                    'Beschreibung',
                    type: BusinessInput.multiline,
                  ),
                  BusinessField(
                    'notes',
                    'Notizen',
                    type: BusinessInput.multiline,
                  ),
                ],
              ),
      ),
    );
    if (mounted) await load();
  }

  @override
  Widget build(BuildContext context) {
    if (!allowed)
      return const BusinessEmpty(
        'Serviceberichte nicht freigegeben',
        'Mit Verbindung neu anmelden. Gesicherte Fassungen bleiben auf diesem Gerät.',
        icon: Icons.lock_outline,
      );
    final rows = <String, Map<String, dynamic>>{
      for (final row in remote) row['id']: row,
      for (final row in widget.repository.serviceReports(project!))
        row['id']: row,
    }.values.toList();
    return ListView(
      padding: const EdgeInsets.all(24),
      children: [
        Text(
          'Serviceberichte',
          style: Theme.of(context).textTheme.headlineMedium,
        ),
        const SizedBox(height: 8),
        const Text(
          'Entwürfe und Unterschriften werden zuerst verschlüsselt auf diesem Gerät gesichert. Die Übertragung übernimmt dieselbe Fassung in das Projektarchiv.',
        ),
        const SizedBox(height: 16),
        Wrap(
          spacing: 12,
          runSpacing: 12,
          children: [
            FilledButton.icon(
              onPressed: writable ? () => open() : null,
              icon: const Icon(Icons.add),
              label: const Text('Servicebericht erfassen'),
            ),
            OutlinedButton.icon(
              onPressed: widget.repository.syncing
                  ? null
                  : () async {
                      await widget.repository.sync();
                      if (mounted) await load();
                    },
              icon: const Icon(Icons.sync),
              label: const Text('Synchronisieren'),
            ),
          ],
        ),
        if (error != null)
          Padding(
            padding: const EdgeInsets.only(top: 16),
            child: Notice(error!),
          ),
        if (widget.repository.notice != null)
          Padding(
            padding: const EdgeInsets.only(top: 16),
            child: Notice(widget.repository.notice!),
          ),
        const SizedBox(height: 16),
        if (rows.isEmpty) const Notice('Noch keine Serviceberichte vorhanden.'),
        for (final row in rows)
          Card(
            child: ListTile(
              leading: Icon(
                row['status'] == 'signed'
                    ? Icons.draw_outlined
                    : Icons.description_outlined,
              ),
              title: Text('${row['title']}'),
              subtitle: Text(
                '${row['sync_status'] ?? (row['status'] == 'signed' ? 'Im Projektarchiv unterzeichnet' : 'Entwurf im Projektarchiv')}',
              ),
              trailing: const Icon(Icons.chevron_right),
              onTap: () => open(row),
            ),
          ),
      ],
    );
  }
}

class OfflineServiceReportPage extends StatefulWidget {
  const OfflineServiceReportPage({
    super.key,
    required this.session,
    required this.repository,
    required this.project,
    this.id,
  });
  final BusinessSession session;
  final OfflinePlans repository;
  final String project;
  final String? id;
  @override
  State<OfflineServiceReportPage> createState() =>
      _OfflineServiceReportPageState();
}

class _OfflineServiceReportPageState extends State<OfflineServiceReportPage> {
  final title = TextEditingController(),
      description = TextEditingController(),
      notes = TextEditingController();
  Map<String, dynamic>? record;
  bool editing = true, busy = false;
  String? error;
  final previews = <MailAttachmentPreviewController>[];
  bool get allowed =>
      !widget.session.denied &&
      (widget.session.offlineMode || widget.session.can('documents.read')) &&
      widget.repository.canAccessServiceReports(widget.project);
  bool get writable =>
      allowed &&
      widget.repository.serviceReportsWritable &&
      (widget.session.offlineMode ||
          widget.session.canWrite('documents.write'));
  @override
  void initState() {
    super.initState();
    widget.session.addListener(changed);
    widget.repository.addListener(changed);
    if (widget.id != null && allowed) {
      record = widget.repository.serviceReport(widget.project, widget.id!);
      editing = false;
      fill();
    }
  }

  void fill() {
    title.text = record?['title'] ?? '';
    description.text = record?['description'] ?? '';
    notes.text = record?['notes'] ?? '';
  }

  void changed() {
    if (!mounted) return;
    if (!allowed) {
      for (final preview in previews) preview.revoke();
    } else if (record != null)
      record = widget.repository.serviceReport(widget.project, record!['id']);
    setState(() {});
  }

  @override
  void dispose() {
    widget.session.removeListener(changed);
    widget.repository.removeListener(changed);
    for (final controller in [title, description, notes]) {
      controller.clear();
      controller.dispose();
    }
    for (final preview in previews) preview.revoke();
    super.dispose();
  }

  Future<void> save() async {
    if (!writable || busy) return;
    setState(() {
      busy = true;
      error = null;
    });
    try {
      final saved = await widget.repository.saveServiceReportDraft(
        widget.project,
        entryId: record?['id'],
        title: title.text.trim(),
        description: description.text,
        notes: notes.text,
      );
      if (mounted && allowed)
        setState(() {
          record = saved;
          editing = false;
        });
    } catch (e) {
      if (mounted) setState(() => error = '$e');
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  Future<void> sign() async {
    if (!writable || record == null || busy || record!['status'] != 'draft')
      return;
    await showDialog<void>(
      context: context,
      barrierDismissible: false,
      builder: (_) => _OfflineServiceSignature(
        session: widget.session,
        repository: widget.repository,
        project: widget.project,
        record: record!,
      ),
    );
    if (mounted) changed();
  }

  Future<void> pdf() async {
    if (!allowed || record == null || busy) return;
    setState(() {
      busy = true;
      error = null;
    });
    try {
      final id = record!['id'] as String;
      final bytes = await widget.repository.serviceReportPdf(
        widget.project,
        id,
      );
      if (!mounted || !allowed) return;
      final controller = MailAttachmentPreviewController(
        VerifiedMailAttachment(
          bytes: bytes,
          filename: 'servicebericht-$id.pdf',
          mediaType: 'application/pdf',
          sha256: record!['server_record']['pdf_sha256'],
        ),
      );
      previews.add(controller);
      await Navigator.push<void>(
        context,
        MaterialPageRoute(
          builder: (_) => MailAttachmentPreviewPage(
            controller: controller,
            mayView: () => mounted && allowed,
            exporter: exportMailAttachment,
          ),
        ),
      );
      controller.revoke();
      previews.remove(controller);
      controller.dispose();
    } catch (e) {
      if (mounted && allowed) setState(() => error = '$e');
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  Future<void> reviewConflict() async {
    if (!writable || record == null || busy) return;
    final id = record!['id'] as String;
    setState(() {
      busy = true;
      error = null;
    });
    try {
      final linked = record!['conflict_successor_id'];
      Map<String, dynamic>? successor;
      if (linked is String) {
        successor = widget.repository.serviceReport(widget.project, linked);
      } else {
        final diagnosis = await widget.repository.diagnoseServiceReport(
          widget.project,
          id,
        );
        if (!mounted || !writable) return;
        if (diagnosis['state'] != 'context_changed') {
          await widget.repository.retryServiceReport(widget.project, id);
          return;
        }
        final confirmed = await showDialog<bool>(
          context: context,
          builder: (dialogContext) => ListenableBuilder(
            listenable: Listenable.merge([widget.session, widget.repository]),
            builder: (_, _) => AlertDialog(
              title: const Text('Projektangaben wurden geändert'),
              content: SingleChildScrollView(
                child: !writable
                    ? const Text(
                        'Der Zugang ist nicht mehr verfügbar. Das Original bleibt gesichert.',
                      )
                    : Text(
                        'Unterschriebenes Original:\nProjekt: ${diagnosis['captured_context']['project_name']}\n'
                        'Kunde: ${diagnosis['captured_context']['customer']}\n\n'
                        'Aktueller Serverstand:\nProjekt: ${diagnosis['current_context']['project_name']}\n'
                        'Kunde: ${diagnosis['current_context']['customer']}\n\n'
                        'Das Original bleibt unverändert auf diesem Gerät und wird weiterhin als Konflikt angezeigt. '
                        'Ein neuer Entwurf übernimmt den Berichtstext mit den aktuellen Projektangaben. '
                        'Er muss geprüft und neu unterschrieben werden. Die bisherige Unterschrift wird nicht übernommen.',
                      ),
              ),
              actions: [
                TextButton(
                  onPressed: () => Navigator.pop(dialogContext, false),
                  child: const Text('Abbrechen'),
                ),
                FilledButton(
                  onPressed: writable
                      ? () => Navigator.pop(dialogContext, true)
                      : null,
                  child: const Text('Neuen Entwurf erstellen'),
                ),
              ],
            ),
          ),
        );
        if (confirmed != true || !mounted || !writable) return;
        successor = await widget.repository.copyConflictedServiceReport(
          widget.project,
          id,
          reviewedDiagnosis: diagnosis,
        );
      }
      if (!mounted || !writable) return;
      await Navigator.push<void>(
        context,
        MaterialPageRoute(
          builder: (_) => OfflineServiceReportPage(
            session: widget.session,
            repository: widget.repository,
            project: widget.project,
            id: successor!['id'],
          ),
        ),
      );
    } catch (e) {
      if (mounted && allowed) setState(() => error = '$e');
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final current = record;
    return Scaffold(
      appBar: AppBar(title: const Text('Servicebericht')),
      body: !allowed
          ? const Center(
              child: Text(
                'Der Zugang ist nicht mehr verfügbar. Die gespeicherte Fassung bleibt erhalten.',
              ),
            )
          : ListView(
              padding: const EdgeInsets.all(24),
              children: [
                if (error != null) Notice(error!, error: true),
                if (editing) ...[
                  TextField(
                    controller: title,
                    enabled: writable && !busy,
                    maxLength: 300,
                    decoration: const InputDecoration(labelText: 'Titel'),
                  ),
                  const SizedBox(height: 16),
                  TextField(
                    controller: description,
                    enabled: writable && !busy,
                    minLines: 5,
                    maxLines: 14,
                    maxLength: 30000,
                    decoration: const InputDecoration(
                      labelText: 'Erbrachte Leistungen',
                    ),
                  ),
                  const SizedBox(height: 16),
                  TextField(
                    controller: notes,
                    enabled: writable && !busy,
                    minLines: 2,
                    maxLines: 6,
                    maxLength: 10000,
                    decoration: const InputDecoration(
                      labelText: 'Notizen im unterschriebenen Bericht',
                    ),
                  ),
                  const SizedBox(height: 16),
                  FilledButton(
                    onPressed: busy || !writable ? null : save,
                    child: const Text('Entwurf auf diesem Gerät speichern'),
                  ),
                ] else if (current != null) ...[
                  Text(
                    '${current['title']}',
                    style: Theme.of(context).textTheme.headlineMedium,
                  ),
                  const SizedBox(height: 12),
                  Notice('${current['sync_status']}'),
                  if (current['sync_error'] != null)
                    Notice('${current['sync_error']}', error: true),
                  if (current['conflict_source'] != null)
                    const Notice(
                      'Neuer Entwurf aus einem Konflikt. Das frühere unterschriebene Original bleibt gesichert; für diesen Bericht ist eine neue Unterschrift erforderlich.',
                    ),
                  if (current['conflict_successor_id'] != null)
                    const Notice(
                      'Ein neuer Bericht wurde als Entwurf angelegt. Dieses unterschriebene Original bleibt unverändert und ist weiterhin nicht synchronisiert.',
                    ),
                  const SizedBox(height: 16),
                  Text(
                    'Projekt: ${current['content']['project_name']}\nKunde: ${current['content']['customer']}',
                  ),
                  const SizedBox(height: 16),
                  SelectableText('${current['description']}'),
                  if (current['notes'] != '')
                    Padding(
                      padding: const EdgeInsets.only(top: 16),
                      child: SelectableText('${current['notes']}'),
                    ),
                  const SizedBox(height: 24),
                  if (current['status'] == 'signed') ...[
                    Text(
                      'Unterzeichnet von ${current['signer']}\nGerätezeit: ${businessDate(current['signed_at'], time: true)}',
                    ),
                    const SizedBox(height: 12),
                    Semantics(
                      label: 'Gesicherte Unterschrift von ${current['signer']}',
                      child: AspectRatio(
                        aspectRatio: signatureAspectRatio,
                        child: CustomPaint(
                          painter: SignaturePainter([
                            for (final stroke in current['strokes'] as List)
                              [
                                for (final point in stroke as List)
                                  Offset(
                                    (point[0] as num).toDouble(),
                                    (point[1] as num).toDouble(),
                                  ),
                              ],
                          ]),
                        ),
                      ),
                    ),
                    const SizedBox(height: 8),
                    const Text(
                      'Die Gerätezeit ist keine unabhängig bestätigte Zeitangabe. Inhalt und Unterschrift dieser Fassung bleiben unverändert.',
                    ),
                    if (current['server_record'] != null)
                      Text(
                        'Serverempfang: ${businessDate(current['server_record']['offline_capture']['received_at'], time: true)}',
                      ),
                    const SizedBox(height: 16),
                    if (current['pdf_source'] != null)
                      OutlinedButton.icon(
                        onPressed: busy ? null : pdf,
                        icon: const Icon(Icons.picture_as_pdf_outlined),
                        label: const Text('Archiviertes PDF öffnen'),
                      )
                    else
                      const Notice(
                        'Das archivierte PDF wird nach bestätigter Übertragung geladen. Die unterschriebene Fassung ist auf diesem Gerät gesichert.',
                      ),
                    if (current['sync_status'] == 'Konflikt' &&
                        !widget.repository.reportConflictReviewSupported)
                      const Notice(
                        'Die Konfliktprüfung benötigt einen aktuellen Serverstand mit Verbindung. Das unterschriebene Original bleibt auf diesem Gerät gesichert.',
                      ),
                    if (current['sync_status'] == 'Konflikt')
                      OutlinedButton.icon(
                        onPressed:
                            !writable ||
                                busy ||
                                widget.repository.syncing ||
                                !widget.repository.reportConflictReviewSupported
                            ? null
                            : reviewConflict,
                        icon: const Icon(Icons.rule_folder_outlined),
                        label: Text(
                          current['conflict_successor_id'] != null
                              ? 'Neuen Bericht öffnen'
                              : 'Konflikt prüfen',
                        ),
                      )
                    else if (current['sync_status'] != 'Synchronisiert')
                      OutlinedButton.icon(
                        onPressed: widget.repository.syncing
                            ? null
                            : () => widget.repository.sync(),
                        icon: const Icon(Icons.sync),
                        label: const Text('Übertragung erneut versuchen'),
                      ),
                  ] else
                    Wrap(
                      spacing: 12,
                      runSpacing: 12,
                      children: [
                        OutlinedButton(
                          onPressed: writable
                              ? () => setState(() {
                                  fill();
                                  editing = true;
                                })
                              : null,
                          child: const Text('Entwurf bearbeiten'),
                        ),
                        FilledButton.icon(
                          onPressed: writable ? sign : null,
                          icon: const Icon(Icons.draw_outlined),
                          label: const Text('Prüfen und unterschreiben'),
                        ),
                      ],
                    ),
                ],
              ],
            ),
    );
  }
}

class _OfflineServiceSignature extends StatefulWidget {
  const _OfflineServiceSignature({
    required this.session,
    required this.repository,
    required this.project,
    required this.record,
  });
  final BusinessSession session;
  final OfflinePlans repository;
  final String project;
  final Map<String, dynamic> record;
  @override
  State<_OfflineServiceSignature> createState() =>
      _OfflineServiceSignatureState();
}

class _OfflineServiceSignatureState extends State<_OfflineServiceSignature> {
  final signer = TextEditingController();
  List<List<Offset>> strokes = [];
  bool confirmed = false, busy = false;
  String? error;
  bool get allowed =>
      !widget.session.denied &&
      widget.repository.serviceReportsWritable &&
      (widget.session.offlineMode ||
          widget.session.canWrite('documents.write')) &&
      widget.repository.canAccessServiceReports(widget.project);
  @override
  void initState() {
    super.initState();
    widget.session.addListener(changed);
    widget.repository.addListener(changed);
  }

  void changed() {
    if (mounted) setState(() {});
  }

  @override
  void dispose() {
    widget.session.removeListener(changed);
    widget.repository.removeListener(changed);
    signer.clear();
    signer.dispose();
    strokes = [];
    super.dispose();
  }

  Future<void> save() async {
    if (!allowed || busy) return;
    if (!confirmed ||
        signer.text.trim().isEmpty ||
        !strokes.any((s) => s.length > 1)) {
      setState(() => error = 'Namen, Unterschrift und Bestätigung ergänzen.');
      return;
    }
    setState(() {
      busy = true;
      error = null;
    });
    try {
      await widget.repository.signServiceReport(
        widget.project,
        widget.record['id'],
        expectedContentHash: widget.record['content_hash'],
        signer: signer.text.trim(),
        strokes: strokes
            .where((s) => s.length > 1)
            .map((s) => s.map((p) => [p.dx, p.dy]).toList())
            .toList(),
      );
      if (mounted) Navigator.pop(context);
    } catch (e) {
      if (mounted) setState(() => error = '$e');
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  @override
  Widget build(BuildContext context) => AlertDialog(
    title: const Text('Diese Fassung unterschreiben'),
    content: SizedBox(
      width: 560,
      child: !allowed
          ? const Notice(
              'Die Freigabe ist nicht mehr verfügbar. Die Fassung bleibt erhalten.',
              error: true,
            )
          : SingleChildScrollView(
              child: Column(
                mainAxisSize: MainAxisSize.min,
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    '${widget.record['title']}',
                    style: Theme.of(context).textTheme.titleLarge,
                  ),
                  const SizedBox(height: 12),
                  Text(
                    'Projekt: ${widget.record['content']['project_name']}\nKunde: ${widget.record['content']['customer']}',
                  ),
                  const SizedBox(height: 12),
                  Text('${widget.record['description']}'),
                  if (widget.record['notes'] != '')
                    Padding(
                      padding: const EdgeInsets.only(top: 12),
                      child: Text('${widget.record['notes']}'),
                    ),
                  const SizedBox(height: 16),
                  const Text(
                    'Die einfache elektronische Unterschrift gehört zu genau dieser Fassung. Sie wird verschlüsselt auf diesem Gerät gesichert und bei Verbindung übertragen.',
                  ),
                  const SizedBox(height: 16),
                  TextField(
                    controller: signer,
                    enabled: !busy,
                    maxLength: 200,
                    decoration: const InputDecoration(
                      labelText: 'Name der unterzeichnenden Person',
                    ),
                  ),
                  OutlinedButton.icon(
                    onPressed: busy
                        ? null
                        : () async {
                            final ink = await showSignatureEditor(
                              context,
                              initialStrokes: strokes,
                            );
                            if (mounted && allowed && ink != null)
                              setState(() => strokes = ink);
                          },
                    icon: const Icon(Icons.draw_outlined),
                    label: Text(
                      strokes.isEmpty
                          ? 'Unterschrift erfassen'
                          : 'Unterschrift ändern',
                    ),
                  ),
                  CheckboxListTile(
                    contentPadding: EdgeInsets.zero,
                    value: confirmed,
                    onChanged: busy
                        ? null
                        : (v) => setState(() => confirmed = v == true),
                    title: const Text(
                      'Ich habe diese Fassung geprüft und bestätige sie.',
                    ),
                  ),
                  if (error != null) Notice(error!, error: true),
                ],
              ),
            ),
    ),
    actions: [
      TextButton(
        onPressed: busy ? null : () => Navigator.pop(context),
        child: const Text('Abbrechen'),
      ),
      FilledButton(
        onPressed: busy || !allowed ? null : save,
        child: const Text('Unterschrift auf diesem Gerät sichern'),
      ),
    ],
  );
}

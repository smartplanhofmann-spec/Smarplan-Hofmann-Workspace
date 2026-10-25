import 'package:cryptography/cryptography.dart';
import 'package:flutter/material.dart';

import 'api.dart';
import 'business_session.dart';
import 'business_widgets.dart';
import 'design.dart';
import 'mail_attachment_preview.dart';
import 'mail_attachment_widgets.dart' show exportMailAttachment;
import 'signature_editor.dart';

class BusinessMeasurementEditor extends StatefulWidget {
  const BusinessMeasurementEditor({
    super.key,
    required this.session,
    this.document,
  });
  final BusinessSession session;
  final Map<String, dynamic>? document;
  @override
  State<BusinessMeasurementEditor> createState() =>
      _BusinessMeasurementEditorState();
}

class _BusinessMeasurementEditorState extends State<BusinessMeasurementEditor> {
  late final TextEditingController title;
  late List<Map<String, dynamic>> lines;
  bool busy = false;
  String? error;
  final key = 'measurement-${DateTime.now().microsecondsSinceEpoch}';
  Map<String, dynamic>? pending;
  @override
  void initState() {
    super.initState();
    title = TextEditingController(text: widget.document?['title'] ?? '');
    lines = (widget.document?['lines'] as List? ?? [])
        .map(businessMap)
        .toList();
    widget.session.addListener(changed);
  }

  void changed() {
    if (mounted) setState(() {});
  }

  @override
  void dispose() {
    widget.session.removeListener(changed);
    title.clear();
    title.dispose();
    super.dispose();
  }

  Future<void> add() async {
    await showDialog<bool>(
      context: context,
      builder: (_) => BusinessEditor(
        session: widget.session,
        title: 'Aufmaßposition',
        fields: const [
          BusinessField('description', 'Beschreibung', required: true),
          BusinessField(
            'unit',
            'Einheit',
            type: BusinessInput.choice,
            required: true,
            initial: 'm2',
            choices: {
              'm': 'Länge (m)',
              'm2': 'Fläche (m²)',
              'm3': 'Volumen (m³)',
              'piece': 'Stück',
              'h': 'Stunden',
            },
          ),
          BusinessField(
            'length',
            'Länge / Menge',
            type: BusinessInput.decimal,
            required: true,
          ),
          BusinessField(
            'width',
            'Breite (bei Fläche und Volumen)',
            type: BusinessInput.decimal,
            initial: '1',
            required: true,
          ),
          BusinessField(
            'height',
            'Höhe (bei Volumen)',
            type: BusinessInput.decimal,
            initial: '1',
            required: true,
          ),
        ],
        onSave: (values) async {
          final unit = values['unit'];
          final dimensions = unit == 'm3'
              ? 3
              : unit == 'm2'
              ? 2
              : 1;
          final vars = <String, dynamic>{
            'length': {
              'value': values['length'],
              'unit': unit == 'piece'
                  ? 'piece'
                  : unit == 'h'
                  ? 'h'
                  : 'm',
            },
            if (dimensions >= 2)
              'width': {'value': values['width'], 'unit': 'm'},
            if (dimensions == 3)
              'height': {'value': values['height'], 'unit': 'm'},
          };
          if (mounted)
            setState(
              () => lines.add({
                'description': values['description'],
                'unit': unit,
                'formula': dimensions == 3
                    ? 'length * width * height'
                    : dimensions == 2
                    ? 'length * width'
                    : 'length',
                'variables': vars,
              }),
            );
        },
      ),
    );
  }

  Future<void> save() async {
    if (busy || !widget.session.canWrite('documents.write')) return;
    if (title.text.trim().isEmpty || lines.isEmpty) {
      setState(
        () =>
            error = 'Bitte Titel und mindestens eine Aufmaßposition erfassen.',
      );
      return;
    }
    setState(() => busy = true);
    pending ??= {
      'project_id': widget.session.projectId,
      'title': title.text.trim(),
      'lines': lines
          .map(
            (line) => {
              for (final e in line.entries)
                if (e.key != 'quantity') e.key: e.value,
            },
          )
          .toList(),
      if (widget.document != null) 'revision': widget.document!['revision'],
    };
    try {
      final result = businessMap(
        await widget.session.command(
          key,
          '/measurements${widget.document == null ? '' : '/${widget.document!['id']}'}',
          pending!,
        ),
      );
      if (mounted && widget.session.allowed)
        Navigator.pushReplacement<void, void>(
          context,
          MaterialPageRoute(
            builder: (_) => BusinessOperationDocumentPage(
              session: widget.session,
              path: '/measurements',
              id: result['id'],
            ),
          ),
        );
    } on ApiException catch (e) {
      if (mounted)
        setState(() {
          error = e.message;
          if (e.status != 0 && e.status < 500 && e.status != 429)
            pending = null;
        });
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(title: const Text('Aufmaß erfassen')),
    body: !widget.session.canWrite('documents.write')
        ? const Center(child: Text('Der Zugang ist nicht mehr verfügbar.'))
        : ListView(
            padding: const EdgeInsets.all(24),
            children: [
              const Notice(
                'Maße werden manuell erfasst. Es werden keine Längen oder Flächen automatisch aus einem Planfoto abgeleitet. Mengen berechnet und prüft der Server.',
              ),
              if (error != null) Notice(error!, error: true),
              const SizedBox(height: 16),
              TextField(
                controller: title,
                enabled: !busy && pending == null,
                decoration: const InputDecoration(labelText: 'Titel'),
              ),
              const SizedBox(height: 16),
              for (final line in lines)
                Card(
                  child: ListTile(
                    title: Text('${line['description']}'),
                    subtitle: Text('${line['formula']} · ${line['unit']}'),
                    trailing: pending != null
                        ? null
                        : IconButton(
                            tooltip: 'Position entfernen',
                            onPressed: busy
                                ? null
                                : () => setState(() => lines.remove(line)),
                            icon: const Icon(Icons.delete_outline),
                          ),
                  ),
                ),
              OutlinedButton.icon(
                onPressed: busy || pending != null ? null : add,
                icon: const Icon(Icons.add),
                label: const Text('Aufmaßposition hinzufügen'),
              ),
              const SizedBox(height: 16),
              FilledButton(
                onPressed: busy ? null : save,
                child: Text(
                  pending == null
                      ? 'Aufmaß speichern'
                      : 'Dieselbe Übertragung erneut senden',
                ),
              ),
            ],
          ),
  );
}

class BusinessOperationDocumentPage extends StatefulWidget {
  const BusinessOperationDocumentPage({
    super.key,
    required this.session,
    required this.path,
    required this.id,
    this.fields = const [],
  });
  final BusinessSession session;
  final String path, id;
  final List<BusinessField> fields;
  @override
  State<BusinessOperationDocumentPage> createState() =>
      _BusinessOperationDocumentPageState();
}

class _BusinessOperationDocumentPageState
    extends State<BusinessOperationDocumentPage> {
  Map<String, dynamic>? record;
  String? error;
  int epoch = 0;
  bool busy = false;
  final previews = <MailAttachmentPreviewController>[];
  bool get allowed => widget.session.can('documents.read');
  @override
  void initState() {
    super.initState();
    widget.session.addListener(changed);
    load();
  }

  void changed() {
    if (!mounted) return;
    if (!allowed) {
      epoch++;
      record = null;
      for (final p in previews) p.revoke();
    }
    setState(() {});
  }

  @override
  void dispose() {
    epoch++;
    widget.session.removeListener(changed);
    for (final p in previews) p.revoke();
    super.dispose();
  }

  Future<void> load() async {
    final current = ++epoch;
    try {
      final result = businessMap(
        await widget.session.read('${widget.path}/${widget.id}'),
      );
      if (mounted && current == epoch && allowed)
        setState(() => record = result);
    } catch (e) {
      if (mounted && current == epoch) setState(() => error = '$e');
    }
  }

  Future<void> edit() async {
    if (record == null ||
        record!['status'] == 'signed' ||
        !widget.session.canWrite('documents.write'))
      return;
    if (widget.path == '/measurements') {
      await Navigator.push<void>(
        context,
        MaterialPageRoute(
          builder: (_) => BusinessMeasurementEditor(
            session: widget.session,
            document: record,
          ),
        ),
      );
    } else {
      final initial = Map<String, dynamic>.from(record!);
      await showDialog<bool>(
        context: context,
        builder: (_) => BusinessEditor(
          session: widget.session,
          title: 'Dokument bearbeiten',
          fields: widget.fields,
          initial: initial,
          onSave: (values) async {
            await widget.session.command(
              'entry-edit-${widget.id}-${initial['revision']}',
              '${widget.path}/${widget.id}',
              {...values, 'revision': initial['revision']},
            );
          },
        ),
      );
    }
    if (mounted) await load();
  }

  Future<void> sign() async {
    if (record == null || !allowed) return;
    await showDialog<bool>(
      context: context,
      barrierDismissible: false,
      builder: (_) => BusinessSignatureDialog(
        session: widget.session,
        path: '${widget.path}/${widget.id}/sign',
        record: record!,
      ),
    );
    if (mounted) await load();
  }

  Future<void> pdf() async {
    if (busy || !allowed || record == null) return;
    setState(() => busy = true);
    final current = epoch;
    final source = record!;
    try {
      final bytes = await widget.session.api.bytes(
        widget.session.path('${widget.path}/${widget.id}/pdf'),
        mediaType: 'application/pdf',
      );
      final digest = (await Sha256().hash(bytes)).bytes
          .map((v) => v.toRadixString(16).padLeft(2, '0'))
          .join();
      if (!mounted || current != epoch || !allowed) return;
      if (source['pdf_sha256'] != digest)
        throw const ApiException(
          0,
          'Die Prüfsumme des PDFs stimmt nicht mit dem Dokument überein.',
        );
      final controller = MailAttachmentPreviewController(
        VerifiedMailAttachment(
          bytes: bytes,
          filename: 'smartplan-${widget.id}.pdf',
          mediaType: 'application/pdf',
          sha256: digest,
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

  @override
  Widget build(BuildContext context) {
    final r = record;
    return Scaffold(
      appBar: AppBar(
        title: Text(
          allowed ? '${r?['title'] ?? 'Dokumentation'}' : 'Dokumentation',
        ),
      ),
      body: !allowed
          ? const Center(child: Text('Der Zugang ist nicht mehr verfügbar.'))
          : r == null
          ? Center(
              child: error == null
                  ? const CircularProgressIndicator()
                  : Text(error!),
            )
          : ListView(
              padding: const EdgeInsets.all(24),
              children: [
                Text(
                  '${r['title']}',
                  style: Theme.of(context).textTheme.headlineMedium,
                ),
                if (error != null) Notice(error!, error: true),
                const SizedBox(height: 16),
                if (r['status'] == 'signed')
                  Notice(
                    'Unveränderliche Fassung · Unterzeichnet von ${r['signer']} am ${businessDate(r['signed_at'], time: true)}',
                  )
                else
                  const Notice('Diese Fassung ist noch nicht unterzeichnet.'),
                Wrap(
                  spacing: 12,
                  runSpacing: 12,
                  children: [
                    if (r['status'] != 'signed' &&
                        widget.session.canWrite('documents.write')) ...[
                      OutlinedButton.icon(
                        onPressed: edit,
                        icon: const Icon(Icons.edit_outlined),
                        label: const Text('Bearbeiten'),
                      ),
                      FilledButton.icon(
                        onPressed: sign,
                        icon: const Icon(Icons.draw_outlined),
                        label: const Text('Prüfen und unterschreiben'),
                      ),
                    ],
                    if (r['status'] == 'signed')
                      OutlinedButton.icon(
                        onPressed: busy ? null : pdf,
                        icon: const Icon(Icons.picture_as_pdf_outlined),
                        label: const Text('Unterzeichnetes PDF öffnen'),
                      ),
                  ],
                ),
                const SizedBox(height: 24),
                for (final field in [
                  'work',
                  'weather',
                  'issues',
                  'description',
                  'notes',
                ])
                  if (r[field] != null && r[field] != '')
                    Padding(
                      padding: const EdgeInsets.only(bottom: 16),
                      child: Text('${r[field]}'),
                    ),
                for (final line in (r['lines'] as List? ?? []).map(businessMap))
                  Card(
                    child: ListTile(
                      title: Text('${line['description']}'),
                      subtitle: Text(
                        '${line['quantity'] ?? 'Noch nicht berechnet'} ${line['unit']}\n${line['formula']}',
                      ),
                    ),
                  ),
              ],
            ),
    );
  }
}

class BusinessSignatureDialog extends StatefulWidget {
  const BusinessSignatureDialog({
    super.key,
    required this.session,
    required this.path,
    required this.record,
    this.commercial = false,
  });
  final BusinessSession session;
  final String path;
  final Map<String, dynamic> record;
  final bool commercial;
  @override
  State<BusinessSignatureDialog> createState() =>
      _BusinessSignatureDialogState();
}

class _BusinessSignatureDialogState extends State<BusinessSignatureDialog> {
  final signer = TextEditingController();
  List<List<Offset>> strokes = [];
  bool busy = false, confirmed = false;
  String? error;
  Map<String, dynamic>? frozen;
  bool get allowed => widget.session.canWrite('documents.write');
  @override
  void initState() {
    super.initState();
    widget.session.addListener(changed);
  }

  void changed() {
    if (mounted) setState(() {});
  }

  @override
  void dispose() {
    widget.session.removeListener(changed);
    signer.clear();
    signer.dispose();
    strokes = [];
    super.dispose();
  }

  Future<void> save() async {
    if (busy || !allowed) return;
    if (signer.text.trim().isEmpty ||
        !confirmed ||
        !strokes.any((s) => s.length > 1)) {
      setState(
        () => error = 'Bitte Namen, Unterschrift und Bestätigung ergänzen.',
      );
      return;
    }
    setState(() => busy = true);
    frozen ??= {
      'revision': widget.record['revision'],
      if (!widget.commercial) 'expected_hash': widget.record['content_hash'],
      if (widget.commercial) 'level': 'simple',
      if (widget.commercial) 'confirmation': true,
      'signer': signer.text.trim(),
      'strokes': strokes
          .map((s) => s.map((p) => [p.dx, p.dy]).toList())
          .toList(),
    };
    try {
      await widget.session.command(
        'sign-${widget.record['id']}',
        widget.path,
        frozen!,
      );
      if (mounted && allowed) Navigator.pop(context, true);
    } on ApiException catch (e) {
      if (mounted)
        setState(() {
          error = e.message;
          if (e.status != 0 && e.status < 500 && e.status != 429) frozen = null;
        });
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  @override
  Widget build(BuildContext context) => AlertDialog(
    title: const Text('Geprüfte Fassung unterschreiben'),
    content: SizedBox(
      width: 500,
      child: !allowed
          ? const Notice('Der Zugang ist nicht mehr verfügbar.', error: true)
          : SingleChildScrollView(
              child: Column(
                mainAxisSize: MainAxisSize.min,
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text('${widget.record['title']}'),
                  const SizedBox(height: 12),
                  const Text(
                    'Die einfache elektronische Unterschrift wird an diese Dokumentfassung gebunden. Eine qualifizierte Signatur oder Identitätsprüfung wird damit nicht zugesagt.',
                  ),
                  const SizedBox(height: 16),
                  TextField(
                    controller: signer,
                    enabled: !busy && frozen == null,
                    decoration: const InputDecoration(
                      labelText: 'Name der unterzeichnenden Person',
                    ),
                  ),
                  const SizedBox(height: 12),
                  OutlinedButton.icon(
                    onPressed: busy || frozen != null
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
                    onChanged: busy || frozen != null
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
        child: Text(
          frozen == null
              ? 'Verbindlich speichern'
              : 'Dieselbe Signatur erneut senden',
        ),
      ),
    ],
  );
}

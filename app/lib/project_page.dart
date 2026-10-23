import 'package:flutter/material.dart';

import 'admin_pages.dart';
import 'api.dart';
import 'pdf_page.dart';
import 'design.dart';
import 'customer_pages.dart';
import 'signature_editor.dart';

export 'signature_editor.dart' show SignaturePainter;

String localDate(String value) {
  final date = DateTime.tryParse(value)?.toLocal();
  if (date == null) return value;
  String two(int n) => n.toString().padLeft(2, '0');
  return '${two(date.day)}.${two(date.month)}.${date.year} ${two(date.hour)}:${two(date.minute)} (Ortszeit)';
}

class ProjectPage extends StatefulWidget {
  final OfficeApi api;
  final Map<String, dynamic> project;
  final String role;
  const ProjectPage({
    super.key,
    required this.api,
    required this.project,
    required this.role,
  });
  @override
  State<ProjectPage> createState() => _ProjectPageState();
}

class _ProjectPageState extends State<ProjectPage> {
  final description = TextEditingController(), signer = TextEditingController();
  String kind = 'Servicebericht';
  Map<String, dynamic>? report;
  List<dynamic> reports = [];
  List<List<Offset>> strokes = [];
  bool checked = false, busy = false, editingSignature = false;
  String? message;
  late String customerName;
  String? customerId;
  bool get canWrite => ['owner', 'manager', 'technician'].contains(widget.role);
  bool get canSign => canWrite && report?['status'] == 'draft';
  bool get hasSignature => strokes.any((s) => s.length > 1);
  @override
  void initState() {
    super.initState();
    customerName = widget.project['customer'];
    customerId = widget.project['customer_id'];
    run(readReports);
  }

  @override
  void dispose() {
    description.dispose();
    signer.dispose();
    super.dispose();
  }

  Future<void> run(Future<void> Function() action) async {
    if (busy) return;
    setState(() {
      busy = true;
      message = null;
    });
    try {
      await action();
    } catch (e) {
      if (mounted) setState(() => message = e.toString());
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  Future<void> readReports() async {
    final items = List<dynamic>.from(
      await widget.api.call('/api/projects/${widget.project['id']}/reports'),
    );
    if (mounted) setState(() => reports = items);
  }

  Future<void> select(String id) => run(() async {
    final item = Map<String, dynamic>.from(
      await widget.api.call('/api/reports/$id'),
    );
    if (mounted)
      setState(() {
        report = item;
        strokes = [];
        checked = false;
        signer.clear();
      });
  });
  void newDraft() {
    if (report != null) {
      description.text = report!['content']['description'];
      kind = report!['content']['kind'];
    }
    setState(() {
      report = null;
      strokes = [];
      checked = false;
      signer.clear();
      message = null;
    });
  }

  Future<void> draft() => run(() async {
    if (description.text.trim().isEmpty)
      throw const ApiException(
        400,
        'Leistungen oder gelieferte Positionen eingeben.',
      );
    final item = await widget.api.call(
      '/api/projects/${widget.project['id']}/reports',
      {'kind': kind, 'description': description.text.trim()},
    );
    if (mounted)
      setState(() {
        report = Map<String, dynamic>.from(item);
        strokes = [];
        checked = false;
        signer.clear();
      });
    await readReports();
  });
  Future<void> sign() => run(() async {
    final item = await widget.api.call('/api/reports/${report!['id']}/sign', {
      'content_hash': report!['content_hash'],
      'signer': signer.text.trim(),
      'strokes': strokes
          .where((s) => s.length > 1)
          .map((s) => s.map((p) => [p.dx, p.dy]).toList())
          .toList(),
    });
    if (mounted) setState(() => report = Map<String, dynamic>.from(item));
    await readReports();
  });
  Future<void> upload() => run(() async {
    final target = widget.api.version == 'v1' ? 'storage' : 'onedrive';
    await widget.api.call('/api/reports/${report!['id']}/$target', {});
    if (mounted)
      setState(() => message = 'PDF wurde in der Ablage gespeichert.');
  });
  Future<void> editSignature() async {
    if (busy || editingSignature || !canSign) return;
    final reportId = report!['id'];
    final contentHash = report!['content_hash'];
    setState(() => editingSignature = true);
    try {
      final edited = await showSignatureEditor(
        context,
        initialStrokes: strokes,
      );
      if (!mounted ||
          edited == null ||
          busy ||
          !canSign ||
          report!['id'] != reportId ||
          report!['content_hash'] != contentHash) {
        return;
      }
      setState(() {
        strokes = edited;
        checked = false;
      });
    } finally {
      if (mounted) setState(() => editingSignature = false);
    }
  }

  Future<void> changeCustomer() async {
    if (busy) return;
    List<Map<String, dynamic>> choices = [];
    await run(() async {
      final result = await widget.api.call('/api/customers');
      choices = [
        for (final c in result)
          if (c['active'] == 1) Map<String, dynamic>.from(c),
      ];
    });
    if (!mounted || message != null) return;
    final selected = await showDialog<String>(
      context: context,
      builder: (_) =>
          CustomerAssignmentDialog(customers: choices, customerId: customerId),
    );
    if (!mounted || selected == null) return;
    await run(() async {
      final updated = await widget.api.call(
        '/api/projects/${widget.project['id']}/customer',
        {'customer_id': selected},
      );
      if (mounted)
        setState(() {
          customerName = updated['customer'];
          customerId = updated['customer_id'];
        });
    });
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(
      title: const Text('Projektübersicht'),
      actions: [
        IconButton(
          tooltip: 'Berichte aktualisieren',
          onPressed: busy ? null : () => run(readReports),
          icon: const Icon(Icons.refresh_rounded, size: 21),
        ),
        if (widget.role == 'owner')
          IconButton(
            tooltip: 'Kunden zuordnen',
            onPressed: busy ? null : changeCustomer,
            icon: const Icon(Icons.contacts_outlined, size: 21),
          ),
        if (widget.role == 'owner')
          IconButton(
            tooltip: 'Projektzugriff verwalten',
            onPressed: busy
                ? null
                : () => Navigator.push(
                    context,
                    MaterialPageRoute(
                      builder: (_) => AssignmentsPage(
                        api: widget.api,
                        project: widget.project,
                      ),
                    ),
                  ),
            icon: const Icon(Icons.group_outlined, size: 21),
          ),
        const SizedBox(width: 16),
      ],
    ),
    body: LayoutBuilder(
      builder: (context, box) {
        final wide = box.maxWidth >= 1100;
        return Center(
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 1420),
            child: ListView(
              padding: EdgeInsets.fromLTRB(
                wide ? 40 : 20,
                12,
                wide ? 40 : 20,
                40,
              ),
              children: [
                PageHeading(
                  eyebrow: 'Projekt',
                  title: widget.project['name'],
                  subtitle: customerName,
                  action: canWrite
                      ? OutlinedButton.icon(
                          onPressed: busy ? null : newDraft,
                          icon: const Icon(Icons.add_rounded, size: 18),
                          label: const Text('Neues Dokument'),
                        )
                      : null,
                ),
                const SizedBox(height: 28),
                if (busy)
                  const Padding(
                    padding: EdgeInsets.only(bottom: 20),
                    child: LinearProgressIndicator(minHeight: 2),
                  ),
                if (message != null)
                  Notice(
                    message!,
                    error: message != 'PDF wurde in der Ablage gespeichert.',
                  ),
                if (!canWrite)
                  const Notice(
                    'Lesender Zugriff. Dokumenterstellung und Unterschriften sind für diese Rolle gesperrt.',
                    error: false,
                  ),
                if (wide)
                  Row(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      SizedBox(width: 300, child: documents()),
                      const SizedBox(width: 24),
                      Expanded(child: editor()),
                    ],
                  )
                else ...[
                  documents(),
                  const SizedBox(height: 24),
                  editor(),
                ],
              ],
            ),
          ),
        );
      },
    ),
  );

  Widget documents() => OfficeSurface(
    padding: const EdgeInsets.all(20),
    child: Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            Expanded(
              child: Text(
                'Dokumente',
                style: Theme.of(context).textTheme.titleMedium,
              ),
            ),
            StatusPill('${reports.length}'),
          ],
        ),
        const SizedBox(height: 6),
        const Text(
          'Berichte und Lieferscheine',
          style: TextStyle(fontSize: 12, color: OfficeColors.muted),
        ),
        const SizedBox(height: 20),
        if (reports.isEmpty && !busy)
          const EmptyState(
            title: 'Noch keine Dokumente vorhanden.',
            description: 'Ihr erster Bericht beginnt hier.',
            icon: Icons.description_outlined,
          ),
        for (final item in reports)
          Padding(
            padding: const EdgeInsets.only(bottom: 8),
            child: Material(
              color: report?['id'] == item['id']
                  ? OfficeColors.blueTint
                  : const Color(0xfffafafa),
              borderRadius: BorderRadius.circular(12),
              child: InkWell(
                borderRadius: BorderRadius.circular(12),
                onTap: busy ? null : () => select(item['id']),
                child: Padding(
                  padding: const EdgeInsets.all(14),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Row(
                        children: [
                          Icon(
                            item['status'] == 'signed'
                                ? Icons.task_alt_rounded
                                : Icons.description_outlined,
                            size: 18,
                            color: item['status'] == 'signed'
                                ? OfficeColors.green
                                : OfficeColors.blue,
                          ),
                          const SizedBox(width: 8),
                          Expanded(
                            child: Text(
                              item['content']['kind'],
                              style: const TextStyle(
                                fontSize: 12,
                                fontWeight: FontWeight.w600,
                              ),
                            ),
                          ),
                          const Icon(
                            Icons.chevron_right_rounded,
                            size: 16,
                            color: OfficeColors.muted,
                          ),
                        ],
                      ),
                      const SizedBox(height: 8),
                      Text(
                        item['content']['description'],
                        maxLines: 2,
                        overflow: TextOverflow.ellipsis,
                        style: const TextStyle(
                          fontSize: 11,
                          height: 1.6,
                          color: OfficeColors.muted,
                        ),
                      ),
                      const SizedBox(height: 12),
                      Row(
                        children: [
                          StatusPill(
                            item['status'] == 'signed'
                                ? 'Unterzeichnet'
                                : 'Entwurf',
                            positive: item['status'] == 'signed',
                          ),
                          const SizedBox(width: 8),
                          Expanded(
                            child: Text(
                              localDate(item['content']['created_at']),
                              maxLines: 1,
                              overflow: TextOverflow.ellipsis,
                              style: const TextStyle(
                                fontSize: 9,
                                color: OfficeColors.muted,
                              ),
                            ),
                          ),
                        ],
                      ),
                    ],
                  ),
                ),
              ),
            ),
          ),
      ],
    ),
  );

  Widget editor() {
    if (!canWrite && report == null)
      return const OfficeSurface(
        child: EmptyState(
          title: 'Ein Dokument auswählen.',
          description: 'Öffnen Sie einen Bericht, um ihn zu lesen\noder das PDF zu speichern.',
          icon: Icons.article_outlined,
        ),
      );
    return OfficeSurface(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          if (canWrite) ...[
            Row(
              children: [
                for (var index = 0; index < 3; index++) ...[
                  if (index > 0)
                    const Padding(
                      padding: EdgeInsets.symmetric(horizontal: 8),
                      child: Icon(
                        Icons.chevron_right_rounded,
                        size: 14,
                        color: OfficeColors.muted,
                      ),
                    ),
                  Expanded(
                    child: Text(
                      ['01 Erfassen', '02 Prüfen', '03 Abschließen'][index],
                      style: TextStyle(
                        fontSize: 10,
                        fontWeight: FontWeight.w600,
                        color:
                            (report == null
                                    ? 0
                                    : report!['status'] == 'draft'
                                    ? 1
                                    : 2) ==
                                index
                            ? OfficeColors.blue
                            : OfficeColors.muted,
                      ),
                    ),
                  ),
                ],
              ],
            ),
            const SizedBox(height: 24),
            const Divider(),
            const SizedBox(height: 28),
          ],
          if (report == null && canWrite) ...[
            const Eyebrow('Dokument erstellen'),
            const SizedBox(height: 10),
            Text(
              'Neues Dokument',
              style: Theme.of(context).textTheme.headlineMedium,
            ),
            const SizedBox(height: 8),
            const Text(
              'Halten Sie fest, was vor Ort geleistet wurde.',
              style: TextStyle(color: OfficeColors.muted, fontSize: 13),
            ),
            const SizedBox(height: 24),
            DropdownButtonFormField<String>(
              key: ValueKey(kind),
              initialValue: kind,
              items: [
                'Servicebericht',
                'Lieferschein',
              ].map((k) => DropdownMenuItem(value: k, child: Text(k))).toList(),
              onChanged: busy ? null : (v) => setState(() => kind = v!),
              decoration: const InputDecoration(labelText: 'Dokumenttyp'),
            ),
            const SizedBox(height: 18),
            TextField(
              controller: description,
              enabled: !busy,
              minLines: 5,
              maxLines: 12,
              maxLength: 10000,
              decoration: const InputDecoration(
                labelText: 'Leistungen / gelieferte Positionen',
                alignLabelWithHint: true,
                hintText: 'Beschreiben Sie die ausgeführten Arbeiten …',
              ),
            ),
            const SizedBox(height: 22),
            Align(
              alignment: Alignment.centerRight,
              child: FilledButton.icon(
                onPressed: busy ? null : draft,
                icon: const Icon(Icons.arrow_forward_rounded, size: 17),
                label: const Text('Dokument zur Prüfung erstellen'),
              ),
            ),
          ],
          if (report != null) ...[
            Row(
              children: [
                const Expanded(child: Eyebrow('Dokumentansicht')),
                StatusPill(
                  report!['status'] == 'signed' ? 'Unterzeichnet' : 'Entwurf',
                  positive: report!['status'] == 'signed',
                ),
              ],
            ),
            const SizedBox(height: 12),
            Text(
              report!['content']['kind'],
              style: Theme.of(context).textTheme.headlineMedium,
            ),
            const SizedBox(height: 8),
            Text(
              'Erstellt: ${localDate(report!['content']['created_at'])}',
              style: const TextStyle(fontSize: 11, color: OfficeColors.muted),
            ),
            const SizedBox(height: 24),
            Container(
              padding: const EdgeInsets.all(22),
              decoration: BoxDecoration(
                color: const Color(0xfffafafa),
                borderRadius: BorderRadius.circular(12),
                border: Border.all(color: OfficeColors.line),
              ),
              child: SelectableText(
                report!['content']['description'],
                style: const TextStyle(fontSize: 14, height: 1.8),
              ),
            ),
            const SizedBox(height: 20),
            Align(
              alignment: Alignment.centerLeft,
              child: OutlinedButton.icon(
                onPressed: busy
                    ? null
                    : () => Navigator.push(
                        context,
                        MaterialPageRoute(
                          builder: (_) => ReportPdfPage(
                            api: widget.api,
                            reportId: report!['id'],
                          ),
                        ),
                      ),
                icon: const Icon(Icons.picture_as_pdf_outlined, size: 18),
                label: const Text('PDF ansehen / speichern'),
              ),
            ),
            const SizedBox(height: 24),
            const Divider(),
            const SizedBox(height: 24),
            if (report!['status'] == 'signed') ...[
              Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const IconTile(
                    Icons.task_alt_rounded,
                    color: OfficeColors.green,
                  ),
                  const SizedBox(width: 14),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        const Text(
                          'Abgeschlossen und unterzeichnet.',
                          style: TextStyle(
                            fontWeight: FontWeight.w600,
                            fontSize: 15,
                          ),
                        ),
                        const SizedBox(height: 6),
                        Text(
                          'Unterzeichnet von ${report!['signer']}\n${localDate(report!['signed_at'])}',
                          style: const TextStyle(
                            fontSize: 12,
                            color: OfficeColors.muted,
                          ),
                        ),
                      ],
                    ),
                  ),
                ],
              ),
              if (['owner', 'manager'].contains(widget.role))
                Padding(
                  padding: const EdgeInsets.only(top: 20),
                  child: Align(
                    alignment: Alignment.centerLeft,
                    child: OutlinedButton.icon(
                      onPressed: busy ? null : upload,
                      icon: const Icon(Icons.cloud_upload_outlined, size: 18),
                      label: const Text('PDF in Ablage speichern'),
                    ),
                  ),
                ),
            ],
            if (canSign) ...[
              Text(
                'Zur Unterschrift',
                style: Theme.of(context).textTheme.titleLarge,
              ),
              const SizedBox(height: 8),
              const Text(
                'Bitte prüfen Sie den Dokumentinhalt vor dem Unterzeichnen.',
                style: TextStyle(fontSize: 12, color: OfficeColors.muted),
              ),
              const SizedBox(height: 20),
              TextField(
                controller: signer,
                enabled: !busy,
                maxLength: 200,
                onChanged: (_) => setState(() {}),
                decoration: const InputDecoration(
                  labelText: 'Name des Unterzeichners',
                ),
              ),
              const SizedBox(height: 12),
              const Text(
                'Unterschrift',
                style: TextStyle(fontSize: 12, fontWeight: FontWeight.w500),
              ),
              const SizedBox(height: 8),
              Material(
                color: Colors.white,
                clipBehavior: Clip.antiAlias,
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(12),
                  side: const BorderSide(color: Color(0xffd2d2d7)),
                ),
                child: InkWell(
                  key: const ValueKey('signature-preview'),
                  onTap: busy || editingSignature ? null : editSignature,
                  child: Padding(
                    padding: const EdgeInsets.all(16),
                    child: Column(
                      children: [
                        AspectRatio(
                          aspectRatio: signatureAspectRatio,
                          child: hasSignature
                              ? CustomPaint(painter: SignaturePainter(strokes))
                              : const Center(
                                  child: Icon(
                                    Icons.draw_outlined,
                                    size: 30,
                                    color: OfficeColors.muted,
                                  ),
                                ),
                        ),
                        const SizedBox(height: 12),
                        Row(
                          children: [
                            Expanded(
                              child: Text(
                                hasSignature
                                    ? 'Unterschrift bearbeiten'
                                    : 'Zum Unterschreiben antippen',
                                style: const TextStyle(
                                  fontSize: 12,
                                  color: OfficeColors.muted,
                                ),
                              ),
                            ),
                            const SizedBox(width: 8),
                            const Icon(Icons.open_in_full_rounded, size: 18),
                          ],
                        ),
                      ],
                    ),
                  ),
                ),
              ),
              const SizedBox(height: 12),
              CheckboxListTile(
                contentPadding: const EdgeInsets.symmetric(horizontal: 0),
                controlAffinity: ListTileControlAffinity.leading,
                value: checked,
                onChanged: busy ? null : (v) => setState(() => checked = v!),
                title: const Text(
                  'Der Unterzeichner hat den oben angezeigten Dokumentinhalt geprüft.',
                  style: TextStyle(fontSize: 12, height: 1.6),
                ),
              ),
              const SizedBox(height: 18),
              FilledButton(
                onPressed:
                    busy ||
                        editingSignature ||
                        !checked ||
                        !hasSignature ||
                        signer.text.trim().isEmpty
                    ? null
                    : sign,
                child: const Text('Unterschrift speichern'),
              ),
            ],
            if (canWrite)
              Padding(
                padding: const EdgeInsets.only(top: 16),
                child: Align(
                  alignment: Alignment.centerLeft,
                  child: TextButton(
                    onPressed: busy ? null : newDraft,
                    child: const Text('Neuen Entwurf erstellen'),
                  ),
                ),
              ),
          ],
        ],
      ),
    );
  }
}

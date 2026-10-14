import 'package:flutter/material.dart';

import 'admin_pages.dart';
import 'api.dart';
import 'pdf_page.dart';

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
  bool checked = false, busy = false;
  String? message;
  bool get canWrite => ['owner', 'manager', 'technician'].contains(widget.role);
  bool get canSign => canWrite && report?['status'] == 'draft';
  bool get hasSignature => strokes.any((s) => s.length > 1);
  @override
  void initState() {
    super.initState();
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
    await widget.api.call('/api/reports/${report!['id']}/onedrive', {});
    if (mounted) setState(() => message = 'PDF wurde in OneDrive abgelegt.');
  });
  Offset point(Offset position, double width) => Offset(
    (position.dx / width).clamp(0, 1).toDouble(),
    (position.dy / 160).clamp(0, 1).toDouble(),
  );
  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(
      title: Text(widget.project['name']),
      actions: [
        IconButton(
          tooltip: 'Berichte aktualisieren',
          onPressed: busy ? null : () => run(readReports),
          icon: const Icon(Icons.refresh),
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
            icon: const Icon(Icons.group),
          ),
      ],
    ),
    body: Center(
      child: ConstrainedBox(
        constraints: const BoxConstraints(maxWidth: 900),
        child: ListView(
          padding: const EdgeInsets.all(24),
          children: [
            Text(
              widget.project['customer'],
              style: const TextStyle(fontSize: 22),
            ),
            const SizedBox(height: 24),
            if (busy) const LinearProgressIndicator(),
            if (message != null)
              Padding(
                padding: const EdgeInsets.symmetric(vertical: 12),
                child: Text(message!),
              ),
            const Text(
              'Vorhandene Dokumente',
              style: TextStyle(fontSize: 20, fontWeight: FontWeight.bold),
            ),
            if (reports.isEmpty && !busy)
              const Padding(
                padding: EdgeInsets.symmetric(vertical: 12),
                child: Text('Noch keine Dokumente vorhanden.'),
              ),
            for (final item in reports)
              Card(
                child: ListTile(
                  leading: Icon(
                    item['status'] == 'signed'
                        ? Icons.verified_outlined
                        : Icons.edit_document,
                  ),
                  title: Text(item['content']['kind']),
                  subtitle: Text(
                    '${item['status'] == 'signed' ? 'Unterzeichnet' : 'Entwurf'} · ${localDate(item['content']['created_at'])}\n${item['content']['description']}',
                    maxLines: 3,
                    overflow: TextOverflow.ellipsis,
                  ),
                  selected: report?['id'] == item['id'],
                  trailing: const Icon(Icons.chevron_right),
                  onTap: busy ? null : () => select(item['id']),
                ),
              ),
            const SizedBox(height: 24),
            if (!canWrite)
              const Text(
                'Lesender Zugriff. Dokumenterstellung und Unterschriften sind für diese Rolle gesperrt.',
              ),
            if (report == null && canWrite) ...[
              const Text(
                'Neues Dokument',
                style: TextStyle(fontSize: 22, fontWeight: FontWeight.bold),
              ),
              const SizedBox(height: 16),
              DropdownButtonFormField<String>(
                key: ValueKey(kind),
                initialValue: kind,
                items: ['Servicebericht', 'Lieferschein']
                    .map((k) => DropdownMenuItem(value: k, child: Text(k)))
                    .toList(),
                onChanged: busy ? null : (v) => setState(() => kind = v!),
                decoration: const InputDecoration(labelText: 'Dokumenttyp'),
              ),
              const SizedBox(height: 16),
              TextField(
                controller: description,
                enabled: !busy,
                minLines: 4,
                maxLines: 12,
                maxLength: 10000,
                decoration: const InputDecoration(
                  labelText: 'Leistungen / gelieferte Positionen',
                ),
              ),
              const SizedBox(height: 16),
              FilledButton(
                onPressed: busy ? null : draft,
                child: const Text('Dokument zur Prüfung erstellen'),
              ),
            ],
            if (report != null) ...[
              Text(
                report!['content']['kind'],
                style: const TextStyle(
                  fontSize: 26,
                  fontWeight: FontWeight.bold,
                ),
              ),
              const SizedBox(height: 12),
              SelectableText(report!['content']['description']),
              const SizedBox(height: 12),
              Text('Erstellt: ${localDate(report!['content']['created_at'])}'),
              const SizedBox(height: 16),
              OutlinedButton.icon(
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
                icon: const Icon(Icons.picture_as_pdf),
                label: const Text('PDF ansehen / speichern'),
              ),
              const SizedBox(height: 24),
              if (report!['status'] == 'signed') ...[
                const Icon(Icons.check_circle, color: Colors.green, size: 48),
                Text(
                  'Unterzeichnet von ${report!['signer']}\n${localDate(report!['signed_at'])}',
                ),
                if (['owner', 'manager'].contains(widget.role))
                  Padding(
                    padding: const EdgeInsets.only(top: 16),
                    child: FilledButton(
                      onPressed: busy ? null : upload,
                      child: const Text('PDF in OneDrive ablegen'),
                    ),
                  ),
              ],
              if (canSign) ...[
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
                const Text('Unterschrift'),
                const SizedBox(height: 8),
                SizedBox(
                  height: 160,
                  child: LayoutBuilder(
                    builder: (context, constraints) => GestureDetector(
                      onPanStart: busy
                          ? null
                          : (d) => setState(
                              () => strokes.add([
                                point(d.localPosition, constraints.maxWidth),
                              ]),
                            ),
                      onPanUpdate: busy
                          ? null
                          : (d) {
                              if (strokes.isNotEmpty)
                                setState(
                                  () => strokes.last.add(
                                    point(
                                      d.localPosition,
                                      constraints.maxWidth,
                                    ),
                                  ),
                                );
                            },
                      child: Container(
                        color: Colors.white,
                        child: CustomPaint(
                          painter: SignaturePainter(strokes),
                          size: Size(constraints.maxWidth, 160),
                        ),
                      ),
                    ),
                  ),
                ),
                TextButton(
                  onPressed: busy
                      ? null
                      : () => setState(() {
                          strokes = [];
                          checked = false;
                        }),
                  child: const Text('Unterschrift neu zeichnen'),
                ),
                CheckboxListTile(
                  value: checked,
                  onChanged: busy ? null : (v) => setState(() => checked = v!),
                  title: const Text(
                    'Der Unterzeichner hat den oben angezeigten Dokumentinhalt geprüft.',
                  ),
                ),
                FilledButton(
                  onPressed:
                      busy ||
                          !checked ||
                          !hasSignature ||
                          signer.text.trim().isEmpty
                      ? null
                      : sign,
                  child: const Text('Unterschrift speichern'),
                ),
              ],
              if (canWrite)
                TextButton(
                  onPressed: busy ? null : newDraft,
                  child: const Text('Neuen Entwurf erstellen'),
                ),
            ],
          ],
        ),
      ),
    ),
  );
}

class SignaturePainter extends CustomPainter {
  final List<List<Offset>> strokes;
  SignaturePainter(this.strokes);
  @override
  void paint(Canvas canvas, Size size) {
    final paint = Paint()
      ..color = const Color(0xff172b38)
      ..strokeWidth = 2
      ..style = PaintingStyle.stroke
      ..strokeCap = StrokeCap.round;
    for (final stroke in strokes) {
      if (stroke.length < 2) continue;
      final path = Path()
        ..moveTo(stroke.first.dx * size.width, stroke.first.dy * size.height);
      for (final p in stroke.skip(1)) {
        path.lineTo(p.dx * size.width, p.dy * size.height);
      }
      canvas.drawPath(path, paint);
    }
  }

  @override
  bool shouldRepaint(covariant SignaturePainter oldDelegate) => true;
}

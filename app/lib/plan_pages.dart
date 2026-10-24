import 'dart:convert';
import 'dart:async';

import 'package:flutter/material.dart';

import 'api.dart';
import 'offline_plans.dart';
import 'plan_import_page.dart';

class PlansPage extends StatefulWidget {
  final OfficeApi api;
  final Map<String, dynamic> project;
  final bool canWrite;
  final OfflinePlans? repository;
  const PlansPage({
    super.key,
    required this.api,
    required this.project,
    required this.canWrite,
    this.repository,
  });
  @override
  State<PlansPage> createState() => _PlansPageState();
}

class _PlansPageState extends State<PlansPage> {
  List<dynamic> plans = [];
  List<Map<String, dynamic>> imports = [];
  bool busy = true;
  String? error;
  String get path => '/api/projects/${widget.project['id']}/plans';
  bool get onlineImports => widget.api.version == 'v1';
  bool get canDelete =>
      widget.canWrite &&
      widget.repository != null &&
      widget.repository!.canAccessProject(widget.project['id']) &&
      [
        'owner',
        'manager',
        'technician',
      ].contains(widget.repository!.user['role']);
  @override
  void initState() {
    super.initState();
    widget.repository?.addListener(localChanged);
    load();
  }

  void localChanged() {
    if (!mounted) return;
    try {
      setState(() {
        plans = widget.repository!.list(widget.project['id']);
        imports = onlineImports
            ? widget.repository!.imports(widget.project['id'])
            : [];
      });
    } catch (e) {
      setState(() {
        error = e.toString();
        if (widget.repository != null && !widget.repository!.permitted) {
          plans = [];
          imports = [];
        }
      });
    }
  }

  @override
  void dispose() {
    widget.repository?.removeListener(localChanged);
    super.dispose();
  }

  Future<void> resolve(Map<String, dynamic> plan) async {
    final choice = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Zwei Planfassungen'),
        content: SizedBox(
          width: 560,
          child: SingleChildScrollView(
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text('Lokal: ${plan['title']} · ${plan['walls'].length} Wände'),
                AspectRatio(
                  aspectRatio: 10 / 7,
                  child: CustomPaint(
                    painter: PlanPainter(
                      List<dynamic>.from(plan['walls']),
                      null,
                    ),
                  ),
                ),
                const SizedBox(height: 12),
                Text(
                  'Server: ${plan['remote']?['title'] ?? 'Noch nicht geladen'} · ${plan['remote']?['walls']?.length ?? '?'} Wände',
                ),
                if (plan['remote'] != null)
                  AspectRatio(
                    aspectRatio: 10 / 7,
                    child: CustomPaint(
                      painter: PlanPainter(
                        List<dynamic>.from(plan['remote']['walls']),
                        null,
                      ),
                    ),
                  ),
                const SizedBox(height: 12),
                const Text(
                  'Lokale Fassung als zusätzlichen Plan behalten oder lokale Änderungen verwerfen und den Serverstand übernehmen?',
                ),
              ],
            ),
          ),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx),
            child: const Text('Später'),
          ),
          TextButton(
            onPressed: () => Navigator.pop(ctx, false),
            child: const Text('Serverstand übernehmen'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(ctx, true),
            child: const Text('Lokale Kopie behalten'),
          ),
        ],
      ),
    );
    if (choice == null || !mounted) return;
    try {
      await widget.repository!.resolve(plan['local_id'], keepCopy: choice);
    } catch (e) {
      if (mounted) setState(() => error = e.toString());
    }
  }

  Future<void> load() async {
    setState(() {
      busy = true;
      error = null;
    });
    try {
      final repo = widget.repository;
      if (repo != null) {
        await repo.sync();
        await repo.refresh(widget.project['id']);
        if (onlineImports) await repo.refreshImports(widget.project['id']);
      }
      final result = repo == null
          ? await widget.api.call(path)
          : repo.list(widget.project['id']);
      if (mounted) {
        setState(() {
          plans = List<dynamic>.from(result);
          imports = onlineImports
              ? repo?.imports(widget.project['id']) ?? []
              : [];
        });
      }
    } catch (e) {
      if (mounted) setState(() => error = e.toString());
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  Future<void> open([String? id]) async {
    setState(() {
      busy = true;
      error = null;
    });
    try {
      final repo = widget.repository;
      final plan = repo != null
          ? (id == null
                ? await repo.save(widget.project['id'], {
                    'title': 'Neuer Grundriss',
                    'walls': [],
                  })
                : repo.get(id))
          : (id == null
                ? <String, dynamic>{'title': '', 'walls': []}
                : Map<String, dynamic>.from(
                    await widget.api.call('$path/$id'),
                  ));
      if (!mounted) return;
      await Navigator.push(
        context,
        MaterialPageRoute(
          builder: (_) => PlanPage(
            api: widget.api,
            path: path,
            initial: plan,
            canWrite: widget.canWrite,
            repository: widget.repository,
          ),
        ),
      );
      if (mounted) await load();
    } catch (e) {
      if (mounted) setState(() => error = e.toString());
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  Future<void> openImport([String? localId]) async {
    final repo = widget.repository;
    if (!onlineImports ||
        repo == null ||
        !repo.canAccessProject(widget.project['id']))
      return;
    await Navigator.push<void>(
      context,
      MaterialPageRoute(
        builder: (_) => localId == null
            ? PlanImportPage(
                repository: repo,
                project: widget.project,
                canWrite: widget.canWrite,
              )
            : PlanImportDetailPage(
                repository: repo,
                project: widget.project,
                localId: localId,
                canWrite: widget.canWrite,
              ),
      ),
    );
    if (mounted) await load();
  }

  Future<void> delete(
    Map<String, dynamic> item, {
    required bool imported,
  }) async {
    if (busy || !canDelete) return;
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (dialogContext) => AlertDialog(
        title: const Text('Plan aus dem Projekt entfernen?'),
        content: Text(
          '„${item['title']}“ wird aus diesem Projekt entfernt. '
          'Ihre Geräte übernehmen die Änderung bei der nächsten Verbindung.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(dialogContext, false),
            child: const Text('Abbrechen'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(dialogContext, true),
            child: const Text('Löschen'),
          ),
        ],
      ),
    );
    if (confirmed != true || !mounted || !canDelete) return;
    setState(() {
      busy = true;
      error = null;
    });
    try {
      if (imported) {
        await widget.repository!.deleteImport(item['local_id']);
      } else {
        await widget.repository!.deletePlan(item['local_id']);
      }
      if (!mounted) return;
      setState(() {
        plans = widget.repository!.list(widget.project['id']);
        imports = onlineImports
            ? widget.repository!.imports(widget.project['id'])
            : [];
      });
    } catch (e) {
      if (mounted) {
        final reason = e is ApiException
            ? e.message
            : 'Bitte erneut versuchen.';
        final message = 'Löschen nicht abgeschlossen. $reason';
        setState(() => error = message);
        ScaffoldMessenger.of(context)
            .showSnackBar(SnackBar(content: Text(message)));
      }
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  Widget deleteButton(Map<String, dynamic> item, {required bool imported}) =>
      TextButton.icon(
        onPressed: busy || !canDelete
            ? null
            : () => delete(item, imported: imported),
        icon: const Icon(Icons.delete_outline),
        label: const Text('Löschen'),
      );

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(
      title: Text('Pläne · ${widget.project['name']}'),
      actions: [
        IconButton(
          tooltip: 'Neu laden',
          onPressed: busy ? null : load,
          icon: const Icon(Icons.refresh),
        ),
      ],
    ),
    floatingActionButton: widget.canWrite && !onlineImports
        ? FloatingActionButton.extended(
            onPressed: busy ? null : () => open(),
            icon: const Icon(Icons.add),
            label: const Text('Neuer Grundriss'),
          )
        : widget.canWrite && widget.repository != null
        ? FloatingActionButton.extended(
            onPressed:
                busy ||
                    !widget.repository!.canAccessProject(widget.project['id'])
                ? null
                : () => openImport(),
            icon: const Icon(Icons.add_photo_alternate_outlined),
            label: const Text('Plan hinzufügen'),
          )
        : null,
    body: busy
        ? const Center(child: CircularProgressIndicator())
        : ListView(
            padding: const EdgeInsets.fromLTRB(20, 20, 20, 112),
            children: [
              if (error != null)
                Text(
                  error!,
                  style: TextStyle(color: Theme.of(context).colorScheme.error),
                ),
              if (onlineImports)
                Text(
                  'Importierte Pläne',
                  style: Theme.of(context).textTheme.titleLarge,
                ),
              if (onlineImports)
                const Text(
                  'Fotos und PDF-Quellen je Geschoss · Original und Ergebnis zur Prüfung',
                ),
              if (!onlineImports)
                const Text('Grundrisse je Geschoss · Entwürfe ohne Maßstab'),
              if (widget.repository != null)
                Padding(
                  padding: const EdgeInsets.symmetric(vertical: 12),
                  child: Text(
                    '${widget.repository!.pending} Änderungen ausstehend${widget.repository!.syncing ? ' · Wird synchronisiert' : ''}\n${widget.repository!.notice ?? 'Pläne werden zuerst verschlüsselt auf diesem Gerät gespeichert.'}',
                  ),
                ),
              if (widget.repository != null &&
                  !widget.repository!.downloaded(widget.project['id']))
                const Padding(
                  padding: EdgeInsets.symmetric(vertical: 12),
                  child: Text(
                    'Für dieses Projekt sind noch keine Serverpläne auf dem Gerät geladen. Offline sind nur lokale Entwürfe verfügbar.',
                  ),
                ),
              if (onlineImports && imports.isEmpty && error == null)
                const Padding(
                  padding: EdgeInsets.symmetric(vertical: 20),
                  child: Text('Noch keine Planquellen importiert.'),
                ),
              if (onlineImports &&
                  (widget.repository?.canAccessProject(widget.project['id']) ??
                      false))
                for (final source in imports)
                  Card(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.stretch,
                      children: [
                        ListTile(
                          leading: Icon(
                            source['media_type'] == 'application/pdf'
                                ? Icons.picture_as_pdf_outlined
                                : Icons.photo_outlined,
                          ),
                          title: Text(source['title']),
                          subtitle: Text(
                            '${source['filename']}\n${planImportStatus(source)}',
                          ),
                          isThreeLine: true,
                          trailing: const Icon(Icons.chevron_right),
                          onTap: () => openImport(source['local_id']),
                        ),
                        if (canDelete)
                          Align(
                            alignment: Alignment.centerRight,
                            child: deleteButton(source, imported: true),
                          ),
                      ],
                    ),
                  ),
              if (onlineImports) const SizedBox(height: 24),
              if (onlineImports)
                Text(
                  'Manuell gezeichnete Entwürfe',
                  style: Theme.of(context).textTheme.titleMedium,
                ),
              if (onlineImports) const Text('Ohne bestätigten Maßstab'),
              if (onlineImports && widget.canWrite)
                Align(
                  alignment: Alignment.centerLeft,
                  child: TextButton.icon(
                    onPressed:
                        busy ||
                            !(widget.repository?.canAccessProject(
                                  widget.project['id'],
                                ) ??
                                true)
                        ? null
                        : () => open(),
                    icon: const Icon(Icons.draw_outlined),
                    label: const Text('Neuer Grundriss'),
                  ),
                ),
              if (plans.isEmpty && error == null)
                const Padding(
                  padding: EdgeInsets.symmetric(vertical: 12),
                  child: Text('Noch keine manuellen Entwürfe vorhanden.'),
                ),
              if (widget.repository?.canAccessProject(widget.project['id']) ??
                  true)
                for (final plan in plans)
                  Card(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.stretch,
                      children: [
                        ListTile(
                          leading: const Icon(Icons.architecture),
                          title: Text(plan['title']),
                          subtitle: Text(
                            '${plan['revision'] == null ? 'Lokaler Entwurf' : 'Stand ${plan['revision']}'} · ${plan['walls'].length} Wände · ${plan['sync_status'] ?? 'Entwurf'}',
                          ),
                          trailing: const Icon(Icons.chevron_right),
                          onTap: () => open(plan['local_id'] ?? plan['id']),
                        ),
                        if ((plan['sync_status'] == 'Konflikt' &&
                                widget.canWrite) ||
                            canDelete)
                          Wrap(
                            alignment: WrapAlignment.end,
                            children: [
                              if (plan['sync_status'] == 'Konflikt' &&
                                  widget.canWrite)
                                TextButton(
                                  onPressed: busy
                                      ? null
                                      : () => resolve(
                                          Map<String, dynamic>.from(plan),
                                        ),
                                  child: const Text('Konflikt klären'),
                                ),
                              if (canDelete)
                                deleteButton(
                                  Map<String, dynamic>.from(plan),
                                  imported: false,
                                ),
                            ],
                          ),
                      ],
                    ),
                  ),
            ],
          ),
  );
}

class PlanPage extends StatefulWidget {
  final OfficeApi api;
  final String path;
  final Map<String, dynamic> initial;
  final bool canWrite;
  final OfflinePlans? repository;
  const PlanPage({
    super.key,
    required this.api,
    required this.path,
    required this.initial,
    required this.canWrite,
    this.repository,
  });
  @override
  State<PlanPage> createState() => _PlanPageState();
}

class _PlanPageState extends State<PlanPage> {
  late final TextEditingController title;
  late Map<String, dynamic> plan;
  late List<dynamic> walls;
  final List<List<dynamic>> history = [];
  Offset? start;
  bool busy = false, dirty = false, deleting = false;
  String? message;
  int edits = 0, localWrites = 0;
  bool get writable =>
      widget.canWrite &&
      (widget.repository?.canAccessProject(widget.initial['project_id']) ??
          true);
  bool get canDelete =>
      writable &&
      widget.repository != null &&
      [
        'owner',
        'manager',
        'technician',
      ].contains(widget.repository!.user['role']);
  void localChanged() {
    if (!mounted || deleting) return;
    try {
      final record = widget.repository!.get(plan['local_id']);
      setState(() {
        plan['revision'] = record['revision'];
        plan['sync_status'] = record['sync_status'];
      });
    } catch (e) {
      setState(() => message = e.toString());
    }
  }

  Future<void> persistLocal() async {
    final repo = widget.repository;
    if (repo == null) return;
    final edit = edits;
    final drawing = Map<String, dynamic>.from(
      jsonDecode(
        jsonEncode({
          'title': title.text.trim().isEmpty
              ? 'Neuer Grundriss'
              : title.text.trim(),
          'walls': walls,
        }),
      ),
    );
    setState(() => localWrites++);
    try {
      final result = await repo.save(
        widget.initial['project_id'],
        drawing,
        localId: plan['local_id'],
      );
      if (mounted)
        setState(() {
          plan['local_id'] = result['local_id'];
          plan['sync_status'] = result['sync_status'];
          if (edits == edit) {
            dirty = false;
            message = 'Lokal gespeichert';
          }
        });
    } catch (e) {
      if (mounted)
        setState(
          () => message = e is ApiException ? e.message : 'Nicht lokal gespeichert. Bitte freien Gerätespeicher prüfen. Änderungen sind noch nicht dauerhaft gesichert.',
        );
    } finally {
      if (mounted) setState(() => localWrites--);
    }
  }

  void edited() {
    setState(() {
      dirty = true;
      edits++;
    });
    if (widget.repository != null) unawaited(persistLocal());
  }

  @override
  void initState() {
    super.initState();
    plan = Map<String, dynamic>.from(jsonDecode(jsonEncode(widget.initial)));
    walls = List<dynamic>.from(plan['walls']);
    title = TextEditingController(text: plan['title']);
    title.addListener(() {
      if (mounted) edited();
    });
    widget.repository?.addListener(localChanged);
  }

  @override
  void dispose() {
    widget.repository?.removeListener(localChanged);
    title.dispose();
    super.dispose();
  }

  void tap(Offset position, Size size) {
    if (!writable || busy) return;
    // Fixed Cartesian draft coordinates; viewport dimensions do not change geometry.
    final point = Offset(
      (position.dx / size.width * 1000 / 10).round() * 10.0,
      ((1 - position.dy / size.height) * 700 / 10).round() * 10.0,
    );
    setState(() {
      if (start == null) {
        start = point;
        return;
      }
      if (point == start) return;
      history.add(List<dynamic>.from(walls));
      walls = [
        ...walls,
        {
          'id': 'w_${DateTime.now().microsecondsSinceEpoch}',
          'points': [
            [start!.dx, start!.dy],
            [point.dx, point.dy],
          ],
        },
      ];
      start = null;
      dirty = true;
      message = null;
    });
    if (start == null) edited();
  }

  Future<void> save() async {
    if (widget.repository != null) {
      await persistLocal();
      await widget.repository!.sync();
      return;
    }
    if (title.text.trim().isEmpty) {
      setState(() => message = 'Bitte Geschoss oder Plantitel eingeben.');
      return;
    }
    setState(() {
      busy = true;
      message = null;
    });
    try {
      final result = await widget.api.call(
        '${widget.path}${plan['id'] == null ? '' : '/${plan['id']}'}',
        {
          'title': title.text.trim(),
          'walls': walls,
          if (plan['id'] != null) 'revision': plan['revision'],
        },
      );
      if (mounted)
        setState(() {
          plan = Map<String, dynamic>.from(result);
          dirty = false;
          message = 'Stand ${plan['revision']} gespeichert.';
        });
    } catch (e) {
      if (mounted) setState(() => message = e.toString());
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  Future<void> leave() async {
    if (busy || localWrites > 0) return;
    if (dirty) {
      final discard = await showDialog<bool>(
        context: context,
        builder: (context) => AlertDialog(
          title: const Text('Ungespeicherte Änderungen'),
          content: const Text('Plan verlassen und Änderungen verwerfen?'),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(context, false),
              child: const Text('Weiter bearbeiten'),
            ),
            TextButton(
              onPressed: () => Navigator.pop(context, true),
              child: const Text('Verwerfen'),
            ),
          ],
        ),
      );
      if (discard != true || !mounted) return;
    }
    if (mounted) Navigator.pop(context);
  }

  Future<void> delete() async {
    final repo = widget.repository;
    if (repo == null || !canDelete || busy || deleting || localWrites > 0)
      return;
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (dialogContext) => AlertDialog(
        title: const Text('Plan aus dem Projekt entfernen?'),
        content: Text(
          '„${title.text.trim().isEmpty ? 'Neuer Grundriss' : title.text.trim()}“ '
          'wird aus diesem Projekt entfernt. Ihre Geräte übernehmen die Änderung '
          'bei der nächsten Verbindung.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(dialogContext, false),
            child: const Text('Abbrechen'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(dialogContext, true),
            child: const Text('Löschen'),
          ),
        ],
      ),
    );
    if (confirmed != true ||
        !mounted ||
        !canDelete ||
        deleting ||
        localWrites > 0)
      return;
    setState(() {
      busy = true;
      deleting = true;
      message = null;
    });
    try {
      await repo.deletePlan(plan['local_id']);
      if (!mounted) return;
      setState(() {
        dirty = false;
        busy = false;
      });
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (mounted) Navigator.pop(context);
      });
    } catch (e) {
      if (!mounted) return;
      final reason = e is ApiException ? e.message : 'Bitte erneut versuchen.';
      setState(() {
        busy = false;
        deleting = false;
        message =
            'Löschen nicht abgeschlossen. Der Plan bleibt geöffnet. $reason';
      });
    }
  }

  @override
  Widget build(BuildContext context) =>
      widget.repository != null &&
          !widget.repository!.canAccessProject(widget.initial['project_id'])
      ? Scaffold(
          appBar: AppBar(title: const Text('Projektplan')),
          body: const Center(
            child: Padding(
              padding: EdgeInsets.all(24),
              child: Text(
                'Offline-Freigabe abgelaufen oder gesperrt. Bitte online anmelden. Lokale Eingaben bleiben erhalten.',
              ),
            ),
          ),
        )
      : PopScope(
          canPop: !dirty && !busy && localWrites == 0,
          onPopInvokedWithResult: (didPop, result) {
            if (!didPop) leave();
          },
          child: Scaffold(
            appBar: AppBar(
              leading: IconButton(
                onPressed: busy || localWrites > 0 ? null : leave,
                icon: const Icon(Icons.arrow_back),
              ),
              title: const Text('Grundriss'),
              actions: [
                if (canDelete)
                  TextButton.icon(
                    onPressed: busy || deleting || localWrites > 0
                        ? null
                        : delete,
                    icon: const Icon(Icons.delete_outline),
                    label: const Text('Löschen'),
                  ),
                if (widget.canWrite)
                  IconButton(
                    tooltip: 'Speichern',
                    onPressed: busy ? null : save,
                    icon: const Icon(Icons.save_outlined),
                  ),
              ],
            ),
            body: Column(
              children: [
                Padding(
                  padding: const EdgeInsets.all(16),
                  child: TextField(
                    controller: title,
                    enabled: writable && !busy,
                    maxLength: 200,
                    decoration: const InputDecoration(
                      labelText: 'Geschoss / Plantitel',
                      hintText: 'Zum Beispiel Erdgeschoss',
                    ),
                  ),
                ),
                Text(
                  'Entwurf – nicht maßstäblich${plan['revision'] == null ? '' : ' · Stand ${plan['revision']}'}${dirty ? ' · ungespeichert' : ''}',
                ),
                if (widget.repository != null)
                  Text(
                    localWrites > 0
                        ? 'Wird lokal gespeichert …'
                        : '${plan['sync_status'] ?? 'Lokal gespeichert'} · ${widget.repository!.pending} Änderungen ausstehend',
                  ),
                if (message != null)
                  Padding(
                    padding: const EdgeInsets.all(8),
                    child: Text(message!),
                  ),
                if (writable)
                  Wrap(
                    alignment: WrapAlignment.center,
                    children: [
                      TextButton.icon(
                        onPressed: busy || history.isEmpty
                            ? null
                            : () => setState(() {
                                walls = history.removeLast();
                                start = null;
                                dirty = true;
                                edits++;
                                if (widget.repository != null)
                                  unawaited(persistLocal());
                              }),
                        icon: const Icon(Icons.undo),
                        label: const Text('Rückgängig'),
                      ),
                      TextButton(
                        onPressed: start == null
                            ? null
                            : () => setState(() => start = null),
                        child: const Text('Wand abbrechen'),
                      ),
                    ],
                  ),
                Padding(
                  padding: const EdgeInsets.all(8),
                  child: Text(
                    widget.canWrite
                        ? (start == null
                              ? 'Wand zeichnen: Startpunkt und Endpunkt antippen.'
                              : 'Jetzt den Endpunkt der Wand antippen.')
                        : 'Gespeicherter Plan · Leseansicht',
                  ),
                ),
                Expanded(
                  child: LayoutBuilder(
                    builder: (context, constraints) => Center(
                      child: AspectRatio(
                        aspectRatio: 10 / 7,
                        child: LayoutBuilder(
                          builder: (context, box) => GestureDetector(
                            onTapUp: (details) =>
                                tap(details.localPosition, box.biggest),
                            child: CustomPaint(
                              painter: PlanPainter(walls, start),
                              size: box.biggest,
                              child: const SizedBox.expand(),
                            ),
                          ),
                        ),
                      ),
                    ),
                  ),
                ),
              ],
            ),
          ),
        );
}

class PlanPainter extends CustomPainter {
  final List<dynamic> walls;
  final Offset? start;
  PlanPainter(this.walls, this.start);
  @override
  void paint(Canvas canvas, Size size) {
    canvas.drawRect(Offset.zero & size, Paint()..color = Colors.white);
    final grid = Paint()
      ..color = const Color(0xffe5e7eb)
      ..strokeWidth = 1;
    Offset screen(num x, num y) =>
        Offset(x / 1000 * size.width, (1 - y / 700) * size.height);
    for (var x = 0; x <= 1000; x += 50) {
      canvas.drawLine(screen(x, 0), screen(x, 700), grid);
    }
    for (var y = 0; y <= 700; y += 50) {
      canvas.drawLine(screen(0, y), screen(1000, y), grid);
    }
    final pen = Paint()
      ..color = const Color(0xff1f2937)
      ..strokeWidth = 4
      ..strokeCap = StrokeCap.square;
    for (final wall in walls) {
      final points = wall['points'];
      canvas.drawLine(
        screen(points[0][0], points[0][1]),
        screen(points[1][0], points[1][1]),
        pen,
      );
    }
    if (start != null)
      canvas.drawCircle(
        screen(start!.dx, start!.dy),
        6,
        Paint()..color = Colors.blue,
      );
  }

  @override
  bool shouldRepaint(covariant PlanPainter oldDelegate) => true;
}

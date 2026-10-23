import 'dart:async';
import 'dart:io';
import 'dart:typed_data';
import 'dart:ui' as ui;

import 'package:file_selector/file_selector.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:image_picker/image_picker.dart' show ImagePicker, ImageSource;

import 'api.dart';
import 'offline_plans.dart';

const maxPlanImportBytes = 20 * 1024 * 1024;

/// Only camera-created app temporary files may be removed after durable capture.
class PlanImportFile {
  final XFile file;
  final bool temporary;
  const PlanImportFile(this.file, {this.temporary = false});
}

typedef PlanImportPicker = Future<PlanImportFile?> Function();

class PlanImportPayload {
  final Uint8List bytes;
  final String mediaType;
  const PlanImportPayload(this.bytes, this.mediaType);
}

/// Check both the declared length and the actual bounded stream. File names and
/// provider MIME hints never determine which decoder receives the source.
Future<PlanImportPayload> readPlanImportFile(XFile file) async {
  final declared = await file.length();
  if (declared <= 0 || declared > maxPlanImportBytes) {
    throw const ApiException(413, 'Eine Datei mit höchstens 20 MiB auswählen.');
  }
  final builder = BytesBuilder(copy: false);
  await for (final chunk in file.openRead()) {
    if (builder.length + chunk.length > maxPlanImportBytes) {
      throw const ApiException(413, 'Die Datei ist größer als 20 MiB.');
    }
    builder.add(chunk);
  }
  if (builder.length != declared) {
    throw const ApiException(
      400,
      'Die Datei wurde nicht vollständig gelesen oder inzwischen verändert. Bitte erneut auswählen.',
    );
  }
  final bytes = builder.takeBytes();
  bool starts(List<int> signature) =>
      bytes.length >= signature.length &&
      List.generate(
        signature.length,
        (i) => bytes[i] == signature[i],
      ).every((v) => v);
  final type = starts([0x89, 0x50, 0x4e, 0x47, 13, 10, 26, 10])
      ? 'image/png'
      : starts([0xff, 0xd8, 0xff])
      ? 'image/jpeg'
      : starts([0x25, 0x50, 0x44, 0x46, 0x2d])
      ? 'application/pdf'
      : null;
  if (type == null) {
    throw const ApiException(
      415,
      'Bitte JPEG, PNG oder PDF auswählen. HEIC, DXF und DWG werden noch nicht unterstützt.',
    );
  }
  if (type != 'application/pdf') {
    await validatePlanImportImage(bytes);
  }
  return PlanImportPayload(bytes, type);
}

/// Inspect the compressed header before asking a widget to decode pixels.
/// This also covers originals and previews downloaded by another device.
Future<void> validatePlanImportImage(Uint8List bytes) async {
  if (bytes.isEmpty || bytes.length > maxPlanImportBytes) {
    throw const ApiException(413, 'Das Bild darf höchstens 20 MiB groß sein.');
  }
  final buffer = await ui.ImmutableBuffer.fromUint8List(bytes);
  ui.ImageDescriptor? descriptor;
  try {
    descriptor = await ui.ImageDescriptor.encoded(buffer);
    if (descriptor.width <= 0 ||
        descriptor.height <= 0 ||
        descriptor.width * descriptor.height > 40000000) {
      throw const ApiException(
        413,
        'Das Bild darf höchstens 40 Millionen Bildpunkte haben.',
      );
    }
  } on ApiException {
    rethrow;
  } catch (_) {
    throw const ApiException(
      400,
      'Die Bilddatei kann nicht gelesen werden. Bitte erneut aufnehmen oder eine andere Datei wählen.',
    );
  } finally {
    descriptor?.dispose();
    buffer.dispose();
  }
}

String planImportStatus(Map<String, dynamic> record) {
  final sync = record['sync_status']?.toString() ?? '';
  if ([
    'Zugriff gesperrt',
    'Eingabe prüfen',
    'Server-Update erforderlich',
  ].contains(sync)) {
    return sync;
  }
  if (record['status'] == 'local') {
    return 'Lokal gespeichert · wartet auf Verbindung';
  }
  return switch (record['status']) {
    'queued' => 'Auf Hetzner · wartet auf Verarbeitung',
    'running' => 'Wird auf Hetzner verarbeitet',
    'needs_review' => 'Ergebnis zur Prüfung bereit',
    'failed' => 'Verarbeitung fehlgeschlagen · Original bleibt erhalten',
    _ => sync.isEmpty ? 'Lokal gespeichert' : sync,
  };
}

class PlanImportPage extends StatefulWidget {
  final OfflinePlans repository;
  final Map<String, dynamic> project;
  final bool canWrite;
  final PlanImportPicker? pickFile;
  final PlanImportPicker? takePhoto;
  final bool? cameraAvailable;
  const PlanImportPage({
    super.key,
    required this.repository,
    required this.project,
    required this.canWrite,
    this.pickFile,
    this.takePhoto,
    this.cameraAvailable,
  });

  @override
  State<PlanImportPage> createState() => _PlanImportPageState();
}

class _PlanImportPageState extends State<PlanImportPage> {
  final title = TextEditingController();
  bool busy = false;
  String? error;
  PlanImportFile? pendingFile;
  PlanImportPayload? pendingPayload;
  int selectedPage = 0;
  bool get allowed =>
      widget.repository.api.version == 'v1' &&
      widget.canWrite &&
      widget.repository.canAccessProject(widget.project['id']);

  @override
  void initState() {
    super.initState();
    widget.repository.addListener(changed);
  }

  void changed() {
    if (mounted) setState(() {});
  }

  @override
  void dispose() {
    widget.repository.removeListener(changed);
    title.dispose();
    super.dispose();
  }

  Future<PlanImportFile?> selectFile() async {
    final file = await openFile(
      acceptedTypeGroups: [
        const XTypeGroup(
          label: 'Plan (JPEG, PNG, PDF)',
          extensions: ['jpg', 'jpeg', 'png', 'pdf'],
          uniformTypeIdentifiers: [
            'public.jpeg',
            'public.png',
            'com.adobe.pdf',
          ],
        ),
      ],
    );
    return file == null ? null : PlanImportFile(file);
  }

  Future<PlanImportFile?> capturePhoto() async {
    final file = await ImagePicker().pickImage(
      source: ImageSource.camera,
      requestFullMetadata: false,
    );
    return file == null ? null : PlanImportFile(file, temporary: true);
  }

  Future<int?> pdfPage() => showDialog<int>(
    context: context,
    builder: (_) => const _PlanPdfPageDialog(),
  );

  Future<void> removeTemporary(PlanImportFile file) async {
    if (!file.temporary || file.file.path.isEmpty) return;
    final temporary = File(file.file.path);
    if (await temporary.exists()) await temporary.delete();
  }

  Future<void> choose({required bool camera}) async {
    if (busy || !allowed) return;
    setState(() {
      busy = true;
      error = null;
    });
    PlanImportFile? selected;
    try {
      selected = await (camera
          ? (widget.takePhoto ?? capturePhoto)()
          : (widget.pickFile ?? selectFile)());
      if (selected == null) return;
      if (!mounted) {
        await removeTemporary(selected);
        return;
      }
      if (!allowed)
        throw const ApiException(
          401,
          'Projektzugriff ist abgelaufen. Bitte erneut anmelden.',
        );
      final payload = await readPlanImportFile(selected.file);
      if (!mounted) {
        await removeTemporary(selected);
        return;
      }
      final page = payload.mediaType == 'application/pdf' ? await pdfPage() : 0;
      if (page == null) {
        await removeTemporary(selected);
        return;
      }
      if (!mounted) {
        await removeTemporary(selected);
        return;
      }
      pendingFile = selected;
      pendingPayload = payload;
      selectedPage = page;
      await persist();
    } on PlatformException catch (e) {
      if (mounted)
        setState(
          () =>
              error = e.code.contains('access') || e.code.contains('permission')
              ? 'Die Kamera ist nicht freigegeben. Bitte den Kamerazugriff in den Einstellungen erlauben oder eine Datei importieren.'
              : 'Die Aufnahme oder Dateiauswahl konnte nicht abgeschlossen werden. Bitte erneut versuchen.',
        );
    } on ApiException catch (e) {
      if (mounted) setState(() => error = e.message);
    } catch (_) {
      if (mounted)
        setState(
          () => error = 'Quelle konnte nicht übernommen werden. Bitte Datei, Verbindung und freien Gerätespeicher prüfen.',
        );
    } finally {
      if (selected != null && pendingFile == null) {
        try {
          await removeTemporary(selected);
        } catch (_) {
          /* Already copied or cancelled. */
        }
      }
      if (mounted) setState(() => busy = false);
    }
  }

  Future<void> persist() async {
    if (!allowed || pendingFile == null || pendingPayload == null) return;
    final file = pendingFile!;
    final payload = pendingPayload!;
    final name = file.file.name;
    final fallback = file.temporary
        ? 'Papierplan ${DateTime.now().toIso8601String().substring(0, 16).replaceFirst('T', ' ')}'
        : name.replaceFirst(RegExp(r'\.[^.]+$'), '').trim();
    final entered = title.text.trim();
    final label = entered.isNotEmpty
        ? entered
        : (fallback.isEmpty ? 'Papierplan' : fallback);
    try {
      final record = await widget.repository.captureImport(
        widget.project['id'],
        payload.bytes,
        filename: name,
        mediaType: payload.mediaType,
        title: label.length > 200 ? label.substring(0, 200) : label,
        page: selectedPage,
      );
      // captureImport resolves only after the encrypted source AND metadata commit.
      String? cleanupWarning;
      try {
        await removeTemporary(file);
      } catch (_) {
        cleanupWarning = 'Lokal gespeichert. Die temporäre Kameraaufnahme konnte noch nicht entfernt werden.';
      }
      pendingFile = null;
      pendingPayload = null;
      if (!mounted) return;
      if (cleanupWarning != null)
        ScaffoldMessenger.of(context)
            .showSnackBar(SnackBar(content: Text(cleanupWarning)));
      unawaited(
        Navigator.pushReplacement<void, void>(
          context,
          MaterialPageRoute(
            builder: (_) => PlanImportDetailPage(
              repository: widget.repository,
              project: widget.project,
              localId: record['local_id'],
            ),
          ),
        ),
      );
    } on ApiException catch (e) {
      if (mounted)
        setState(() => error = 'Noch nicht lokal gespeichert. ${e.message}');
    } on FormatException catch (e) {
      if (mounted)
        setState(() => error = 'Noch nicht lokal gespeichert. ${e.message}');
    } catch (_) {
      if (mounted)
        setState(
          () => error = 'Noch nicht lokal gespeichert. Bitte freien Gerätespeicher prüfen und erneut speichern.',
        );
    }
  }

  Future<void> retry() async {
    if (busy || !allowed) return;
    setState(() {
      busy = true;
      error = null;
    });
    try {
      await persist();
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  Future<void> leave() async {
    if (busy) return;
    if (pendingFile != null) {
      final discard = await showDialog<bool>(
        context: context,
        builder: (context) => AlertDialog(
          title: const Text('Quelle noch nicht gespeichert'),
          content: const Text(
            'Die Quelle ist noch nicht dauerhaft gesichert. Import verwerfen?',
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(context, false),
              child: const Text('Weiter speichern'),
            ),
            TextButton(
              onPressed: () => Navigator.pop(context, true),
              child: const Text('Verwerfen'),
            ),
          ],
        ),
      );
      if (discard != true || !mounted) return;
      try {
        await removeTemporary(pendingFile!);
      } catch (_) {
        /* No durable-save claim. */
      }
      pendingFile = null;
      pendingPayload = null;
    }
    if (mounted) Navigator.pop(context);
  }

  @override
  Widget build(BuildContext context) => PopScope(
    canPop: !busy && pendingFile == null,
    onPopInvokedWithResult: (didPop, result) {
      if (!didPop) unawaited(leave());
    },
    child: Scaffold(
      appBar: AppBar(
        title: const Text('Plan hinzufügen'),
        leading: IconButton(
          onPressed: busy ? null : leave,
          icon: const Icon(Icons.arrow_back),
        ),
      ),
      body: ListView(
        padding: const EdgeInsets.all(24),
        children: [
          Text(
            widget.project['name'] ?? 'Projekt',
            style: Theme.of(context).textTheme.titleLarge,
          ),
          const SizedBox(height: 12),
          const Text(
            'Papierplan mit Handnotizen aufnehmen oder eine vorhandene Datei auswählen. Die Quelle wird zuerst verschlüsselt auf diesem Gerät gespeichert.',
          ),
          const SizedBox(height: 20),
          if (!allowed)
            const Text(
              'Projektzugriff ist gesperrt oder die Offline-Freigabe abgelaufen. Bitte online anmelden. Bereits gespeicherte Quellen bleiben erhalten.',
            )
          else ...[
            TextField(
              controller: title,
              enabled: !busy,
              maxLength: 200,
              decoration: const InputDecoration(
                labelText: 'Geschoss / Plantitel (optional)',
                hintText: 'Zum Beispiel Erdgeschoss',
              ),
            ),
            if (pendingFile == null) ...[
              if (widget.cameraAvailable ?? Platform.isIOS)
                FilledButton.icon(
                  onPressed: busy ? null : () => choose(camera: true),
                  icon: const Icon(Icons.photo_camera_outlined),
                  label: const Text('Plan fotografieren'),
                ),
              const SizedBox(height: 12),
              OutlinedButton.icon(
                onPressed: busy ? null : () => choose(camera: false),
                icon: const Icon(Icons.upload_file_outlined),
                label: const Text('Datei importieren'),
              ),
              const SizedBox(height: 12),
              const Text(
                'JPEG, PNG oder PDF · höchstens 20 MiB. Bei PDF wird eine Seite von 1 bis 50 ausgewählt.',
              ),
            ] else ...[
              Text('Noch nicht lokal gespeichert: ${pendingFile!.file.name}'),
              FilledButton.icon(
                onPressed: busy ? null : retry,
                icon: const Icon(Icons.save_outlined),
                label: const Text('Erneut speichern'),
              ),
            ],
          ],
          if (busy)
            const Padding(
              padding: EdgeInsets.all(20),
              child: Column(
                children: [
                  CircularProgressIndicator(),
                  SizedBox(height: 12),
                  Text('Quelle wird übernommen …'),
                ],
              ),
            ),
          if (error != null)
            Padding(
              padding: const EdgeInsets.symmetric(vertical: 16),
              child: Text(
                error!,
                style: TextStyle(color: Theme.of(context).colorScheme.error),
              ),
            ),
          const SizedBox(height: 20),
          const Text(
            'Die Verarbeitung beginnt auf Hetzner nach der Übertragung. Ergebnisse bleiben Vorschläge zur Prüfung; Wände, Handschrift und Maße werden nicht als bestätigt übernommen.',
          ),
        ],
      ),
    ),
  );
}

class _PlanPdfPageDialog extends StatefulWidget {
  const _PlanPdfPageDialog();
  @override
  State<_PlanPdfPageDialog> createState() => _PlanPdfPageDialogState();
}

class _PlanPdfPageDialogState extends State<_PlanPdfPageDialog> {
  final controller = TextEditingController(text: '1');
  final form = GlobalKey<FormState>();
  @override
  void dispose() {
    controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => AlertDialog(
    title: const Text('PDF-Seite auswählen'),
    content: Form(
      key: form,
      child: TextFormField(
        controller: controller,
        autofocus: true,
        keyboardType: TextInputType.number,
        decoration: const InputDecoration(labelText: 'Seite (1–50)'),
        validator: (value) {
          final page = int.tryParse(value?.trim() ?? '');
          return page == null || page < 1 || page > 50
              ? 'Eine Seitenzahl von 1 bis 50 eingeben.'
              : null;
        },
      ),
    ),
    actions: [
      TextButton(
        onPressed: () => Navigator.pop(context),
        child: const Text('Abbrechen'),
      ),
      FilledButton(
        onPressed: () {
          if (form.currentState!.validate())
            Navigator.pop(context, int.parse(controller.text.trim()) - 1);
        },
        child: const Text('Quelle speichern'),
      ),
    ],
  );
}

class PlanImportDetailPage extends StatefulWidget {
  final OfflinePlans repository;
  final Map<String, dynamic> project;
  final String localId;
  const PlanImportDetailPage({
    super.key,
    required this.repository,
    required this.project,
    required this.localId,
  });
  @override
  State<PlanImportDetailPage> createState() => _PlanImportDetailPageState();
}

class _PlanImportDetailPageState extends State<PlanImportDetailPage> {
  Map<String, dynamic>? record;
  Map<String, dynamic>? recognition;
  ImageProvider? sourceImage, previewImage;
  bool busy = false, showPreview = false;
  bool showLines = true, showTextBoxes = false;
  String? error, previewNotice;
  int generation = 0;

  bool get allowed =>
      widget.repository.api.version == 'v1' &&
      widget.repository.canAccessProject(widget.project['id']);

  @override
  void initState() {
    super.initState();
    widget.repository.addListener(changed);
    unawaited(load());
  }

  void clearImages() {
    if (sourceImage != null) unawaited(sourceImage!.evict());
    if (previewImage != null) unawaited(previewImage!.evict());
    sourceImage = null;
    previewImage = null;
    recognition = null;
  }

  void changed() {
    if (!mounted) return;
    try {
      final next = widget.repository.getImport(widget.localId);
      if (!allowed || next['project_id'] != widget.project['id'])
        throw const ApiException(401, 'Projektzugriff ist gesperrt.');
      final ready =
          (record?['status'] != 'needs_review' &&
              next['status'] == 'needs_review') ||
          (record?['source'] == null && next['source'] != null) ||
          (record?['preview'] == null && next['preview'] != null) ||
          (record?['recognition'] == null && next['recognition'] != null);
      setState(() => record = next);
      if (ready) unawaited(load());
    } catch (_) {
      generation++;
      clearImages();
      setState(() {
        record = null;
        busy = false;
        error = 'Offline-Freigabe abgelaufen oder Projektzugriff gesperrt. Bitte online anmelden.';
      });
    }
  }

  Future<void> load({bool synchronize = false}) async {
    final request = ++generation;
    setState(() {
      busy = true;
      error = null;
      previewNotice = null;
    });
    try {
      if (synchronize) await widget.repository.sync();
      final current = widget.repository.getImport(widget.localId);
      if (!allowed || current['project_id'] != widget.project['id'])
        throw const ApiException(401, 'Projektzugriff ist gesperrt.');
      final hadPreview = previewImage != null;
      clearImages();
      record = current;
      if (mounted && request == generation) setState(() {});
      try {
        final source = await widget.repository.importSource(widget.localId);
        if (!mounted || request != generation || !allowed) return;
        if (current['media_type'] != 'application/pdf') {
          await validatePlanImportImage(source);
          if (!mounted || request != generation || !allowed) return;
          sourceImage = ResizeImage(
            MemoryImage(source),
            width: 1800,
            height: 1800,
            policy: ResizeImagePolicy.fit,
          );
        }
      } on ApiException catch (e) {
        if (e.status == 401 || e.status == 403) rethrow;
        previewNotice = e.message;
      } catch (_) {
        previewNotice = 'Das Original konnte auf diesem Gerät nicht geprüft werden. Bitte mit Verbindung erneut laden.';
      }
      if (current['status'] == 'needs_review' && current['preview'] != null) {
        try {
          final preview = await widget.repository.importPreview(widget.localId);
          if (!mounted || request != generation || !allowed) return;
          await validatePlanImportImage(preview);
          if (!mounted || request != generation || !allowed) return;
          previewImage = ResizeImage(
            MemoryImage(preview),
            width: 1800,
            height: 1800,
            policy: ResizeImagePolicy.fit,
          );
          if (!hadPreview) showPreview = true;
        } on ApiException catch (e) {
          if (e.status == 401 || e.status == 403) rethrow;
          previewNotice =
              'Die Servervorschau ist auf diesem Gerät noch nicht verfügbar.';
        }
      }
      if (current['status'] == 'needs_review' &&
          current['recognition'] != null) {
        try {
          final result = await widget.repository.importRecognition(
            widget.localId,
          );
          if (!mounted || request != generation || !allowed) return;
          recognition = result;
        } on ApiException catch (e) {
          if (e.status == 401 || e.status == 403) rethrow;
          previewNotice = 'Die Erkennung ist auf diesem Gerät noch nicht vollständig verfügbar.';
        }
      }
      if (mounted && request == generation && allowed) setState(() {});
    } catch (e) {
      if (mounted && request == generation) {
        clearImages();
        setState(
          () => error = e is ApiException ? e.message : 'Quelle konnte nicht geöffnet werden. Bitte Gerätespeicher und Verbindung prüfen.',
        );
      }
    } finally {
      if (mounted && request == generation) setState(() => busy = false);
    }
  }

  @override
  void dispose() {
    generation++;
    widget.repository.removeListener(changed);
    clearImages();
    super.dispose();
  }

  Widget picture(ImageProvider image) {
    final dimensions = recognition?['preview'];
    final width = dimensions is Map ? dimensions['width'] : null;
    final height = dimensions is Map ? dimensions['height'] : null;
    final overlay =
        showPreview &&
        recognition != null &&
        width is num &&
        height is num &&
        width.isFinite &&
        height.isFinite &&
        width > 0 &&
        height > 0 &&
        width * height <= 40000000;
    final view = Image(
      image: image,
      fit: overlay ? BoxFit.fill : BoxFit.contain,
      frameBuilder: overlay
          ? (context, child, frame, synchronous) =>
                frame == null && !synchronous
                ? child
                : CustomPaint(
                    foregroundPainter: PlanImportCandidatesPainter(
                      recognition!,
                      lines: showLines,
                      textBoxes: showTextBoxes,
                    ),
                    child: child,
                  )
          : null,
      errorBuilder: (_, _, _) => const Text(
        'Bildvorschau nicht lesbar. Das gespeicherte Original bleibt erhalten.',
      ),
    );
    return overlay
        ? AspectRatio(aspectRatio: width / height, child: view)
        : view;
  }

  Widget detailLayout(Widget child) => LayoutBuilder(
    builder: (context, constraints) => constraints.maxHeight < 460
        ? SingleChildScrollView(child: SizedBox(height: 640, child: child))
        : child,
  );

  @override
  Widget build(BuildContext context) {
    final visible = allowed ? record : null;
    final image = showPreview ? previewImage : sourceImage;
    final texts = recognition == null
        ? <Map<String, dynamic>>[]
        : planImportTexts(recognition!);
    final pdfNotice = visible?['source'] != null
        ? 'PDF-Original lokal gespeichert. Die gewählte Seite wird nach der Verarbeitung auf Hetzner als Vorschau angezeigt.'
        : 'Das PDF-Original ist auf diesem Gerät noch nicht gespeichert. Bitte mit Verbindung neu laden.';
    return Scaffold(
      appBar: AppBar(
        title: Text(visible?['title'] ?? 'Importierter Plan'),
        actions: [
          IconButton(
            tooltip: 'Status aktualisieren',
            onPressed: busy || !allowed ? null : () => load(synchronize: true),
            icon: const Icon(Icons.refresh),
          ),
        ],
      ),
      body: !allowed
          ? const Center(
              child: Padding(
                padding: EdgeInsets.all(24),
                child: Text(
                  'Offline-Freigabe abgelaufen oder Projektzugriff gesperrt. Bitte online anmelden. Lokale Quellen bleiben erhalten.',
                ),
              ),
            )
          : detailLayout(
              Column(
                children: [
                  if (visible != null)
                    Padding(
                      padding: const EdgeInsets.all(16),
                      child: Column(
                        children: [
                          Text(planImportStatus(visible)),
                          Text(
                            '${visible['filename']} · ${visible['media_type'] == 'application/pdf' ? 'Seite ${(visible['page'] as int? ?? 0) + 1}' : 'Originalfoto / Bild'}',
                          ),
                          if (visible['error_message'] != null)
                            Text(
                              visible['error_message'],
                              style: TextStyle(
                                color: Theme.of(context).colorScheme.error,
                              ),
                            ),
                          if (previewImage != null)
                            SegmentedButton<bool>(
                              segments: const [
                                ButtonSegment(
                                  value: false,
                                  label: Text('Quelle'),
                                ),
                                ButtonSegment(
                                  value: true,
                                  label: Text('Servervorschau'),
                                ),
                              ],
                              selected: {showPreview},
                              onSelectionChanged: (selection) =>
                                  setState(() => showPreview = selection.first),
                            ),
                          if (showPreview && recognition != null)
                            Wrap(
                              spacing: 8,
                              children: [
                                FilterChip(
                                  label: const Text('Linienvorschläge'),
                                  selected: showLines,
                                  onSelected: (value) =>
                                      setState(() => showLines = value),
                                ),
                                FilterChip(
                                  label: const Text('Textstellen'),
                                  selected: showTextBoxes,
                                  onSelected: (value) =>
                                      setState(() => showTextBoxes = value),
                                ),
                              ],
                            ),
                        ],
                      ),
                    ),
                  if (busy) const LinearProgressIndicator(),
                  if (error != null)
                    Padding(
                      padding: const EdgeInsets.all(16),
                      child: Text(error!),
                    ),
                  if (previewNotice != null)
                    Padding(
                      padding: const EdgeInsets.all(16),
                      child: Text(previewNotice!),
                    ),
                  Expanded(
                    child: image != null
                        ? InteractiveViewer(
                            minScale: .5,
                            maxScale: 6,
                            child: Center(child: picture(image)),
                          )
                        : Center(
                            child: Padding(
                              padding: const EdgeInsets.all(24),
                              child: Text(
                                visible?['media_type'] == 'application/pdf'
                                    ? pdfNotice
                                    : busy
                                    ? 'Quelle wird geöffnet …'
                                    : 'Auf diesem Gerät ist noch keine Bildvorschau verfügbar.',
                              ),
                            ),
                          ),
                  ),
                  if (showPreview && texts.isNotEmpty)
                    ExpansionTile(
                      title: Text('${texts.length} erkannte Textstellen'),
                      children: [
                        SizedBox(
                          height: 140,
                          child: ListView(
                            children: [
                              for (final item in texts)
                                ListTile(
                                  dense: true,
                                  title: Text(item['text']),
                                  subtitle: Text(item['origin']),
                                ),
                            ],
                          ),
                        ),
                      ],
                    ),
                  const Padding(
                    padding: EdgeInsets.all(16),
                    child: Text(
                      'Quelle und Vorschau dienen der Prüfung. Maßstab, Wände und Handschrift sind noch nicht fachlich bestätigt.',
                    ),
                  ),
                ],
              ),
            ),
    );
  }
}

List<Map<String, dynamic>> planImportTexts(Map<String, dynamic> result) {
  final analysis = result['analysis'];
  final ocr = analysis is Map ? analysis['text_candidates'] : null;
  return [
    for (final group in [
      [ocr, 'Drucktext-OCR'],
      [result['pdf_text'], 'PDF-Text'],
    ])
      if (group[0] is List)
        for (final item in group[0] as List)
          if (item is Map && item['text'] is String)
            {...Map<String, dynamic>.from(item), 'origin': group[1]},
  ];
}

/// Geometry stays a visual candidate overlay; it never becomes a wall model.
class PlanImportCandidatesPainter extends CustomPainter {
  final Map<String, dynamic> result;
  final bool lines, textBoxes;
  PlanImportCandidatesPainter(
    this.result, {
    required this.lines,
    required this.textBoxes,
  });

  bool valid(Object? value) =>
      value is num && value.isFinite && value >= 0 && value <= 1;

  @override
  void paint(Canvas canvas, Size size) {
    final analysis = result['analysis'];
    final candidates = analysis is Map ? analysis['line_candidates'] : null;
    final pen = Paint()
      ..color = const Color(0xff078d78)
      ..strokeWidth = 1.5;
    if (lines && candidates is List) {
      for (final line in candidates) {
        if (line is! Map) continue;
        final start = line['start'], end = line['end'];
        if (start is! List ||
            end is! List ||
            start.length != 2 ||
            end.length != 2 ||
            ![...start, ...end].every(valid))
          continue;
        canvas.drawLine(
          Offset(start[0] * size.width, start[1] * size.height),
          Offset(end[0] * size.width, end[1] * size.height),
          pen,
        );
      }
    }
    if (textBoxes) {
      pen
        ..color = const Color(0xffd4870f)
        ..style = PaintingStyle.stroke;
      for (final word in planImportTexts(result)) {
        final box = word['bbox'];
        if (box is! List ||
            box.length != 4 ||
            !box.every(valid) ||
            box[0] > box[2] ||
            box[1] > box[3])
          continue;
        canvas.drawRect(
          Rect.fromLTRB(
            box[0] * size.width,
            box[1] * size.height,
            box[2] * size.width,
            box[3] * size.height,
          ),
          pen,
        );
      }
    }
  }

  @override
  bool shouldRepaint(covariant PlanImportCandidatesPainter oldDelegate) =>
      !identical(result, oldDelegate.result) ||
      lines != oldDelegate.lines ||
      textBoxes != oldDelegate.textBoxes;
}

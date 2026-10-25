import 'dart:convert';
import 'dart:io';
import 'dart:typed_data';

import 'package:cryptography/cryptography.dart';
import 'package:file_selector/file_selector.dart';
import 'package:flutter/material.dart';
import 'package:flutter/foundation.dart';
import 'package:image_picker/image_picker.dart';

import 'api.dart';
import 'business_session.dart';
import 'business_widgets.dart';
import 'design.dart';
import 'mail_attachment_preview.dart';
import 'mail_attachment_widgets.dart' show exportMailAttachment;
import 'offline_vault.dart' show offlineId;
import 'offline_plans.dart';

class BusinessMediaPage extends StatefulWidget {
  const BusinessMediaPage({
    super.key,
    required this.session,
    this.pickFile,
    this.takePhoto,
    this.repository,
  });
  final BusinessSession session;
  final Future<XFile?> Function()? pickFile, takePhoto;
  final OfflinePlans? repository;
  @override
  State<BusinessMediaPage> createState() => _BusinessMediaPageState();
}

class _BusinessMediaPageState extends State<BusinessMediaPage> {
  List<Map<String, dynamic>> records = [];
  Uint8List? source;
  Map<String, dynamic>? manifest, remote;
  String? captureId, error, success;
  int cursor = 0, epoch = 0;
  bool busy = false, loading = true;
  final previews = <MailAttachmentPreviewController>[];
  final caption = TextEditingController();
  XFile? temporaryPhoto;
  bool get local =>
      widget.repository?.fieldMediaSupported == true &&
      widget.session.projectId != null &&
      widget.repository!.canAccessProject(widget.session.projectId!) &&
      (!widget.session.allowed || widget.session.can('documents.read'));
  bool get allowed => local || widget.session.can('documents.read');
  bool get canCapture =>
      !widget.session.readonly &&
      widget.repository?.businessReadOnly != true &&
      (local || widget.session.canWrite('documents.write'));
  bool get canImportPdf =>
      widget.session.allowed && widget.session.canWrite('finance.write');
  bool get mobile =>
      !kIsWeb &&
      [
        TargetPlatform.iOS,
        TargetPlatform.android,
      ].contains(defaultTargetPlatform);
  @override
  void initState() {
    super.initState();
    widget.session.addListener(changed);
    widget.repository?.addListener(changed);
    load();
  }

  void changed() {
    if (!mounted) return;
    if (!allowed) {
      epoch++;
      source = null;
      manifest = null;
      remote = null;
      records = [];
      for (final p in previews) p.revoke();
    }
    if (local && mounted) {
      try {
        final localRows = widget.repository!.fieldPhotos(
          widget.session.projectId!,
        );
        final serverIds = localRows.map((r) => r['server_id']).toSet();
        records = [
          ...localRows,
          ...records.where(
            (r) => r['local_id'] == null && !serverIds.contains(r['id']),
          ),
        ];
      } catch (_) {}
    }
    setState(() {});
  }

  @override
  void dispose() {
    epoch++;
    source = null;
    manifest = null;
    records = [];
    for (final p in previews) p.revoke();
    widget.session.removeListener(changed);
    widget.repository?.removeListener(changed);
    caption.clear();
    caption.dispose();
    super.dispose();
  }

  Future<void> load() async {
    final current = epoch;
    List<Map<String, dynamic>> localRows = [];
    if (local) {
      localRows = widget.repository!.fieldPhotos(widget.session.projectId!);
      if (mounted) setState(() => records = localRows);
    }
    if (!widget.session.can('documents.read')) {
      if (mounted) setState(() => loading = false);
      return;
    }
    try {
      final result = businessItems(
        await widget.session.read(widget.session.query('/media')),
      );
      if (mounted && current == epoch && allowed) {
        final ids = localRows.map((r) => r['server_id']).toSet();
        setState(
          () => records = [
            ...localRows,
            ...result.where((r) => !ids.contains(r['id'])),
          ],
        );
      }
    } catch (e) {
      if (mounted && current == epoch) setState(() => error = '$e');
    } finally {
      if (mounted) setState(() => loading = false);
    }
  }

  String hex(List<int> bytes) =>
      bytes.map((n) => n.toRadixString(16).padLeft(2, '0')).join();
  Future<void> removeTemporaryPhoto(XFile photo) async {
    if (photo.path.isEmpty) return;
    try {
      final file = File(photo.path);
      if (await file.exists()) await file.delete();
    } catch (_) {
      /* The encrypted original, when committed, remains authoritative. */
    }
  }

  Future<void> choose({bool camera = false}) async {
    if (busy || !canCapture) return;
    setState(() {
      busy = true;
      error = null;
      success = null;
    });
    final current = epoch;
    try {
      final file = camera
          ? await (widget.takePhoto?.call() ??
                ImagePicker().pickImage(
                  source: ImageSource.camera,
                  requestFullMetadata: false,
                ))
          : await (widget.pickFile?.call() ??
                openFile(
                  acceptedTypeGroups: [
                    XTypeGroup(
                      label: 'Fotos und PDF',
                      extensions: canImportPdf
                          ? ['jpg', 'jpeg', 'png', 'pdf']
                          : ['jpg', 'jpeg', 'png'],
                      uniformTypeIdentifiers: canImportPdf
                          ? ['public.jpeg', 'public.png', 'com.adobe.pdf']
                          : ['public.jpeg', 'public.png'],
                    ),
                  ],
                ));
      if (camera && file != null) temporaryPhoto = file;
      if (file == null || !mounted || current != epoch || !allowed) return;
      const maximum = 20 * 1024 * 1024;
      final length = await file.length();
      if (length < 1 || length > maximum)
        throw const ApiException(
          413,
          'Bitte eine Datei mit höchstens 20 MiB auswählen.',
        );
      final builder = BytesBuilder(copy: false);
      await for (final chunk in file.openRead(0, maximum + 1)) {
        builder.add(chunk);
        if (builder.length > maximum)
          throw const ApiException(413, 'Die Datei ist größer als 20 MiB.');
      }
      final bytes = builder.takeBytes();
      if (bytes.length != length)
        throw const ApiException(
          409,
          'Die Quelldatei wurde während der Auswahl geändert. Bitte neu auswählen.',
        );
      String? type;
      if (bytes.length >= 8 &&
          base64Encode(bytes.sublist(0, 8)) == 'iVBORw0KGgo=')
        type = 'image/png';
      if (bytes.length >= 3 &&
          bytes[0] == 255 &&
          bytes[1] == 216 &&
          bytes[2] == 255)
        type = 'image/jpeg';
      if (bytes.length >= 5 &&
          ascii.decode(bytes.sublist(0, 5), allowInvalid: true) == '%PDF-')
        type = 'application/pdf';
      if (type == null)
        throw const ApiException(
          415,
          'Nur echte JPEG-, PNG- und PDF-Dateien werden unterstützt.',
        );
      if (type == 'application/pdf' && !canImportPdf)
        throw const ApiException(
          403,
          'Für Plan-PDFs verwenden Sie den Bereich Pläne. Diese Fotodokumentation speichert JPEG- und PNG-Aufnahmen.',
        );
      final digest = hex((await Sha256().hash(bytes)).bytes);
      if (!mounted || current != epoch || !allowed) return;
      // cross_file's name getter only splits on Platform.pathSeparator. A
      // valid mixed-separator Windows picker path can therefore retain a
      // directory component. Parse the selected path using the actual host.
      final sourceSegments = File(file.path).uri.pathSegments;
      if (sourceSegments.isEmpty || sourceSegments.last.isEmpty)
        throw const ApiException(
          400,
          'Die ausgewählte Datei hat keinen gültigen Dateinamen. Bitte erneut auswählen.',
        );
      captureId = offlineId();
      cursor = 0;
      remote = null;
      source = bytes;
      manifest = {
        'project_id': widget.session.projectId,
        'filename': sourceSegments.last,
        'media_type': type,
        'size': bytes.length,
        'sha256': digest,
        'caption': caption.text.trim(),
      };
    } catch (e) {
      if (mounted && current == epoch) setState(() => error = '$e');
    } finally {
      if (source == null && temporaryPhoto != null) {
        final photo = temporaryPhoto!;
        temporaryPhoto = null;
        await removeTemporaryPhoto(photo);
      }
      if (mounted) setState(() => busy = false);
    }
    if (source != null && mounted && allowed) await upload();
  }

  Future<void> upload() async {
    final bytes = source;
    final input = manifest;
    final key = captureId;
    if (busy || bytes == null || input == null || key == null || !canCapture)
      return;
    setState(() {
      busy = true;
      error = null;
    });
    final current = epoch;
    try {
      if (local && ['image/jpeg', 'image/png'].contains(input['media_type'])) {
        await widget.repository!.captureFieldPhoto(
          widget.session.projectId!,
          bytes,
          filename: input['filename'],
          mediaType: input['media_type'],
          caption: input['caption'] ?? '',
        );
        final temporary = temporaryPhoto;
        temporaryPhoto = null;
        if (temporary != null) await removeTemporaryPhoto(temporary);
        if (!mounted || current != epoch || !allowed) return;
        setState(() {
          source = null;
          manifest = null;
          remote = null;
          caption.clear();
          success = 'Foto und Notiz sind verschlüsselt auf diesem Gerät gesichert. Die Übertragung läuft bei Verbindung automatisch.';
        });
        await load();
        return;
      }
      if (!widget.session.canWrite('documents.write'))
        throw const ApiException(403, 'Für PDF-Importe bitte online anmelden.');
      remote ??= businessMap(
        await widget.session.command('media-$key', '/media', input),
      );
      if (!mounted || current != epoch || !allowed) return;
      for (var index = cursor; index * 262144 < bytes.length; index++) {
        final start = index * 262144;
        final end = (start + 262144).clamp(0, bytes.length);
        await widget.session.api.call(
          widget.session.path('/media/${remote!['id']}/chunks/$index'),
          {'content_base64': base64Encode(bytes.sublist(start, end))},
        );
        if (!mounted || current != epoch || !allowed) return;
        cursor = index + 1;
        setState(() {});
      }
      await widget.session.command(
        'media-complete-$key',
        '/media/${remote!['id']}/complete',
        {},
      );
      if (!mounted || current != epoch || !allowed) return;
      setState(() {
        source = null;
        manifest = null;
        remote = null;
        success = 'Originaldatei vollständig und mit geprüfter Prüfsumme im Projekt gespeichert.';
      });
      await load();
    } catch (e) {
      if (mounted && current == epoch && allowed) setState(() => error = '$e');
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  Future<void> open(Map<String, dynamic> record) async {
    if (busy ||
        !allowed ||
        (record['local_id'] == null && record['status'] != 'ready'))
      return;
    setState(() => busy = true);
    final current = epoch;
    try {
      final bytes = record['local_id'] != null && local
          ? await widget.repository!.fieldPhotoSource(record['local_id'])
          : await widget.session.api.bytes(
              widget.session.path('/media/${record['id']}/content'),
              mediaType: record['media_type'],
            );
      final digest = hex((await Sha256().hash(bytes)).bytes);
      if (!mounted || current != epoch || !allowed) return;
      if (bytes.length != record['size'] || digest != record['sha256'])
        throw const ApiException(
          0,
          'Die Datei stimmt nicht mit dem gespeicherten Original überein.',
        );
      final controller = MailAttachmentPreviewController(
        VerifiedMailAttachment(
          bytes: bytes,
          filename: record['filename'],
          mediaType: record['media_type'],
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
    if (!allowed)
      return const BusinessEmpty(
        'Fotos nicht freigegeben',
        'Dokumente sind nur mit passendem Projektzugriff verfügbar.',
      );
    return ListView(
      padding: const EdgeInsets.all(24),
      children: [
        Wrap(
          spacing: 12,
          runSpacing: 12,
          crossAxisAlignment: WrapCrossAlignment.center,
          children: [
            Text(
              'Fotos und Originaldateien',
              style: Theme.of(context).textTheme.headlineMedium,
            ),
            if (canCapture)
              FilledButton.icon(
                onPressed: busy || source != null ? null : () => choose(),
                icon: const Icon(Icons.add_photo_alternate_outlined),
                label: const Text('Foto / Datei importieren'),
              ),
            if (mobile && canCapture && local)
              OutlinedButton.icon(
                onPressed: busy || source != null
                    ? null
                    : () => choose(camera: true),
                icon: const Icon(Icons.camera_alt_outlined),
                label: const Text('Foto aufnehmen'),
              ),
          ],
        ),
        const SizedBox(height: 12),
        Text(
          local
              ? 'Fotos und Bildnotizen werden zuerst verschlüsselt auf diesem Gerät gesichert. Der Abgleich läuft bei Verbindung. Originale bleiben unverändert.'
              : 'Das Original bleibt unverändert. Für Offlinefotos bitte einmal mit Verbindung neu anmelden.',
        ),
        if (canCapture) ...[
          const SizedBox(height: 12),
          TextField(
            controller: caption,
            enabled: !busy && source == null,
            maxLength: 2000,
            maxLines: 2,
            decoration: const InputDecoration(
              labelText: 'Bildnotiz (optional)',
            ),
          ),
        ],
        if (error != null) Notice(error!, error: true),
        if (success != null) Notice(success!),
        if (loading || busy) const LinearProgressIndicator(),
        if (source != null) ...[
          const SizedBox(height: 16),
          Text('${manifest?['filename']} · $cursor Dateiblöcke bestätigt'),
          OutlinedButton(
            onPressed: busy || !canCapture ? null : upload,
            child: const Text('Dieselbe Übertragung fortsetzen'),
          ),
        ],
        const SizedBox(height: 16),
        if (!loading && records.isEmpty && error == null)
          const BusinessEmpty(
            'Noch keine Originaldateien',
            'Importieren Sie ein Baustellenfoto oder ein PDF für dieses Projekt.',
          ),
        for (final record in records)
          Card(
            child: ListTile(
              leading: Icon(
                record['media_type'] == 'application/pdf'
                    ? Icons.picture_as_pdf_outlined
                    : Icons.photo_outlined,
              ),
              title: Text(
                '${(record['caption'] as String? ?? '').trim().isEmpty ? record['filename'] : record['caption']}',
              ),
              subtitle: Text(
                '${record['filename']} · ${record['size']} Bytes · ${record['sync_status'] ?? (record['status'] == 'ready' ? 'Vollständig gespeichert' : 'Übertragung noch offen')}',
              ),
              trailing:
                  record['local_id'] != null || record['status'] == 'ready'
                  ? const Icon(Icons.open_in_full)
                  : null,
              onTap:
                  (record['local_id'] != null || record['status'] == 'ready') &&
                      !busy
                  ? () => open(record)
                  : null,
            ),
          ),
      ],
    );
  }
}

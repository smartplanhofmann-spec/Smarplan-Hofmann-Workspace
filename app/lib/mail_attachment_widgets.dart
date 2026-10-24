import 'dart:io';
import 'dart:async';

import 'package:cryptography/cryptography.dart';
import 'package:file_selector/file_selector.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:path_provider/path_provider.dart';
import 'package:share_plus/share_plus.dart';

import 'api.dart';
import 'mail_attachment_preview.dart';
import 'offline_vault.dart' show offlineId;

export 'mail_attachment_preview.dart'
    show
        VerifiedMailAttachment,
        MailAttachmentExportResult,
        MailAttachmentExporter;

const maxMailAttachmentBytes = 20 * 1024 * 1024;
const _planMedia = {'application/pdf', 'image/jpeg', 'image/png'};

String attachmentSize(int bytes) => bytes >= 1024 * 1024
    ? '${(bytes / (1024 * 1024)).toStringAsFixed(1).replaceAll('.', ',')} MiB'
    : bytes >= 1024
    ? '${(bytes / 1024).ceil()} KiB'
    : '$bytes B';

String safeAttachmentFilename(String filename) {
  var result = filename
      .replaceAll(RegExp(r'[<>:"/\\|?*\x00-\x1f\x7f]'), '_')
      .replaceAll(RegExp(r'^[. ]+|[. ]+$'), '');
  if (result.length > 200) result = result.substring(0, 200);
  if (result.isEmpty) result = 'mail-anhang';
  if (RegExp(
    r'^(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\.|$)',
    caseSensitive: false,
  ).hasMatch(result)) {
    result = 'Datei-$result';
  }
  return result;
}

class _AccessLost implements Exception {}

Future<MailAttachmentExportResult> exportMailAttachment(
  BuildContext context,
  VerifiedMailAttachment attachment,
  bool Function() mayExport,
) async {
  if (!mayExport()) throw _AccessLost();
  final name = safeAttachmentFilename(attachment.filename);
  if (!Platform.isIOS && !Platform.isAndroid) {
    final location = await getSaveLocation(suggestedName: name);
    if (location == null) return MailAttachmentExportResult.cancelled;
    if (!mayExport()) throw _AccessLost();
    await File(location.path).writeAsBytes(attachment.bytes, flush: true);
    return MailAttachmentExportResult.saved;
  }
  // Own the share file so it can be removed after cancellation or completion.
  // XFile.fromData would leave the plugin's generated plaintext cache behind.
  final temporary = await getTemporaryDirectory();
  if (!mayExport() || !context.mounted) throw _AccessLost();
  final render = context.findRenderObject();
  if (render is! RenderBox || !render.hasSize || render.size.isEmpty) {
    throw const ApiException(0, 'Dateiausgabe ist hier nicht verfügbar.');
  }
  final origin = render.localToGlobal(Offset.zero) & render.size;
  final folder = Directory('${temporary.path}/smartplan-mail-${offlineId()}');
  await folder.create();
  try {
    if (!mayExport()) throw _AccessLost();
    final file = File('${folder.path}/$name');
    await file.writeAsBytes(attachment.bytes, flush: true);
    if (!mayExport()) throw _AccessLost();
    final result = await SharePlus.instance.share(
      ShareParams(
        files: [XFile(file.path, name: name, mimeType: attachment.mediaType)],
        fileNameOverrides: [name],
        sharePositionOrigin: origin,
      ),
    );
    if (result.status == ShareResultStatus.dismissed)
      return MailAttachmentExportResult.cancelled;
    if (result.status != ShareResultStatus.success) {
      throw const ApiException(
        0,
        'Die Datei konnte nicht zum Teilen übergeben werden.',
      );
    }
    return MailAttachmentExportResult.shared;
  } finally {
    if (await folder.exists()) await folder.delete(recursive: true);
  }
}

/// Inquiry metadata is supplied by its existing detail request. Refreshes read
/// only this card's data, preserving unsaved customer/workflow fields above it.
/// Project metadata is loaded only when the Documents register mounts the card.
class MailAttachmentsCard extends StatefulWidget {
  final OfficeApi api;
  final String? inquiryId, projectId;
  final Map<String, dynamic>? attachments;
  final bool canDelete, canImportPlan, offlineMode;
  final ValueListenable<bool>? accessAllowed;
  final VoidCallback? onAccessDenied, onPlans;
  final MailAttachmentExporter? exporter;
  final ValueChanged<Map<String, dynamic>?>? onManifestChanged;
  const MailAttachmentsCard({
    super.key,
    required this.api,
    this.inquiryId,
    this.projectId,
    this.attachments,
    this.canDelete = false,
    this.canImportPlan = false,
    this.offlineMode = false,
    this.accessAllowed,
    this.onAccessDenied,
    this.onPlans,
    this.exporter,
    this.onManifestChanged,
  }) : assert((inquiryId == null) != (projectId == null));
  @override
  State<MailAttachmentsCard> createState() => _MailAttachmentsCardState();
}

class _MailAttachmentsCardState extends State<MailAttachmentsCard> {
  Map<String, dynamic>? manifest;
  String? token, error, notice;
  bool loading = false, blocked = false, needsUpdate = false;
  int fetchEpoch = 0;
  final working = <String>{};
  final planRequests = <String, String>{};
  final previewGuards = <MailAttachmentPreviewController, bool Function()>{};
  final actionAllowed = ValueNotifier<bool>(true);
  bool get project => widget.projectId != null;
  bool get allowed => !blocked && widget.accessAllowed?.value != false;
  List<Map<String, dynamic>> get files => [
    for (final file in manifest?['files'] as List? ?? [])
      if (file is Map && file['status'] != 'deleted')
        Map<String, dynamic>.from(file),
  ];
  String get path => project
      ? '/api/projects/${widget.projectId}/mail-attachments'
      : '/api/inquiries/${widget.inquiryId}';

  @override
  void initState() {
    super.initState();
    token = widget.api.token;
    manifest = widget.attachments;
    widget.api.addListener(accessChanged);
    widget.accessAllowed?.addListener(accessChanged);
    if (project && !widget.offlineMode && allowed) unawaited(refresh());
  }

  @override
  void didUpdateWidget(covariant MailAttachmentsCard oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.accessAllowed != widget.accessAllowed) {
      oldWidget.accessAllowed?.removeListener(accessChanged);
      widget.accessAllowed?.addListener(accessChanged);
    }
    if (oldWidget.attachments != widget.attachments &&
        !project &&
        allowed &&
        widget.attachments != manifest) {
      fetchEpoch++;
      loading = false;
      manifest = widget.attachments;
      needsUpdate = manifest == null;
    }
    accessChanged();
    revalidatePreviews();
  }

  @override
  void dispose() {
    fetchEpoch++;
    widget.api.removeListener(accessChanged);
    widget.accessAllowed?.removeListener(accessChanged);
    for (final preview in previewGuards.keys) {
      preview.revoke();
    }
    previewGuards.clear();
    actionAllowed.dispose();
    super.dispose();
  }

  void accessChanged() {
    if (!mounted || blocked) return;
    if (widget.accessAllowed?.value == false ||
        (token != null && widget.api.token != token))
      deny();
  }

  void deny() {
    if (!mounted || blocked) return;
    fetchEpoch++;
    actionAllowed.value = false;
    for (final preview in previewGuards.keys) {
      preview.revoke();
    }
    setState(() {
      blocked = true;
      loading = false;
      manifest = null;
      error = null;
      notice = null;
      planRequests.clear();
    });
    widget.onAccessDenied?.call();
  }

  bool sessionValid(String? captured) =>
      mounted &&
      allowed &&
      captured != null &&
      captured.isNotEmpty &&
      widget.api.token == captured &&
      !widget.offlineMode;

  bool fileValid(Map<String, dynamic> file, String? captured) =>
      sessionValid(captured) &&
      files.any(
        (current) =>
            current['id'] == file['id'] &&
            current['status'] == file['status'] &&
            current['sha256'] == file['sha256'] &&
            current['size'] == file['size'],
      );

  void revalidatePreviews() {
    for (final entry in previewGuards.entries) {
      if (!entry.value()) entry.key.revoke();
    }
  }

  bool bounded(Map<String, dynamic> file) =>
      file['id'] is String &&
      RegExp(r'^[a-f0-9]{32}$').hasMatch(file['id']) &&
      file['filename'] is String &&
      (file['filename'] as String).isNotEmpty &&
      file['media_type'] is String &&
      file['size'] is int &&
      file['size'] >= 1 &&
      file['size'] <= maxMailAttachmentBytes &&
      file['sha256'] is String &&
      RegExp(r'^[a-f0-9]{64}$').hasMatch(file['sha256']);

  void message(String value, {bool failure = true}) {
    if (!mounted || !allowed) return;
    setState(() {
      if (failure) {
        error = value;
        notice = null;
      } else {
        notice = value;
        error = null;
      }
    });
    ScaffoldMessenger.maybeOf(context)
        ?.showSnackBar(SnackBar(content: Text(value)));
  }

  Future<void> refresh() async {
    if (loading || !allowed || widget.offlineMode) return;
    final captured = widget.api.token;
    final epoch = ++fetchEpoch;
    setState(() {
      loading = true;
      error = null;
    });
    try {
      final result = await widget.api.call(path);
      if (!sessionValid(captured) || epoch != fetchEpoch) {
        accessChanged();
        return;
      }
      if (result is! Map)
        throw const ApiException(0, 'Anhänge konnten nicht gelesen werden.');
      final value = project ? result : result['attachments'];
      if (value != null && (value is! Map || value['files'] is! List)) {
        throw const ApiException(0, 'Anhänge konnten nicht gelesen werden.');
      }
      setState(() {
        manifest = value == null ? null : Map<String, dynamic>.from(value);
        needsUpdate = value == null;
      });
      revalidatePreviews();
      if (!project) widget.onManifestChanged?.call(manifest);
    } on ApiException catch (e) {
      if (!mounted || epoch != fetchEpoch) return;
      if (e.status == 401 || e.status == 403) {
        deny();
        return;
      }
      if (e.status == 404) {
        if (project) {
          try {
            final projects = await widget.api.call('/api/projects');
            if (!sessionValid(captured) || epoch != fetchEpoch) {
              accessChanged();
              return;
            }
            if (projects is! List ||
                !projects.any(
                  (item) => item is Map && item['id'] == widget.projectId,
                )) {
              deny();
              return;
            }
          } on ApiException catch (probe) {
            if (probe.status == 401 || probe.status == 403) {
              deny();
              return;
            }
            message(
              'Anhänge konnten nicht geladen werden. Bitte Verbindung prüfen.',
            );
            return;
          } catch (_) {
            message(
              'Projektzugriff konnte nicht bestätigt werden. Bitte erneut laden.',
            );
            return;
          }
        }
        setState(() {
          manifest = null;
          needsUpdate = true;
        });
        revalidatePreviews();
      } else {
        message(
          'Anhänge konnten nicht geladen werden. Bitte Verbindung prüfen und erneut versuchen.',
        );
      }
    } catch (_) {
      if (mounted && allowed && epoch == fetchEpoch)
        message(
          'Anhänge konnten nicht geladen werden. Bitte erneut versuchen.',
        );
    } finally {
      if (mounted && epoch == fetchEpoch) setState(() => loading = false);
    }
  }

  Future<VerifiedMailAttachment?> verifiedFile(
    Map<String, dynamic> file,
    String? captured,
  ) async {
    final id = file['id'] as String;
    final downloadPath = project
        ? '$path/$id/content'
        : '$path/attachments/$id/content';
    final bytes = await widget.api.bytes(
      downloadPath,
      mediaType: 'application/octet-stream',
      maxBytes: maxMailAttachmentBytes,
    );
    if (!fileValid(file, captured)) {
      accessChanged();
      return null;
    }
    if (bytes.length != file['size'] || bytes.length > maxMailAttachmentBytes) {
      throw const ApiException(
        0,
        'Die Dateigröße stimmt nicht. Es wurde nichts gespeichert.',
      );
    }
    final hash = (await Sha256().hash(bytes)).bytes
        .map((value) => value.toRadixString(16).padLeft(2, '0'))
        .join();
    if (!fileValid(file, captured)) {
      accessChanged();
      return null;
    }
    if (hash != file['sha256'])
      throw const ApiException(
        0,
        'Die Datei konnte nicht geprüft werden. Es wurde nichts gespeichert.',
      );
    return VerifiedMailAttachment(
      bytes: bytes,
      filename: file['filename'],
      mediaType: file['media_type'],
      sha256: hash,
    );
  }

  Future<void> download(
    BuildContext buttonContext,
    Map<String, dynamic> file,
  ) async {
    final id = file['id'] as String;
    final captured = widget.api.token;
    if (loading ||
        working.isNotEmpty ||
        !bounded(file) ||
        !fileValid(file, captured) ||
        file['status'] != 'ready')
      return;
    setState(() {
      working.add(id);
      error = null;
      notice = null;
    });
    try {
      final verified = await verifiedFile(file, captured);
      if (verified == null || !buttonContext.mounted) return;
      final exported = await (widget.exporter ?? exportMailAttachment)(
        buttonContext,
        verified,
        () => fileValid(file, captured),
      );
      if (!fileValid(file, captured)) {
        accessChanged();
        return;
      }
      if (exported != MailAttachmentExportResult.cancelled)
        message(
          exported == MailAttachmentExportResult.saved
              ? 'Datei gespeichert.'
              : 'Datei zum Speichern oder Teilen übergeben.',
          failure: false,
        );
    } on ApiException catch (e) {
      if (e.status == 401 || e.status == 403)
        deny();
      else if (fileValid(file, captured))
        message(e.message);
    } on _AccessLost {
      accessChanged();
      /* A revoked handoff must not write or share anything. */
    } catch (_) {
      if (fileValid(file, captured))
        message(
          'Datei konnte nicht gespeichert oder geteilt werden. Bitte erneut versuchen.',
        );
    } finally {
      if (mounted) setState(() => working.remove(id));
    }
  }

  Future<void> preview(Map<String, dynamic> file) async {
    final captured = widget.api.token;
    if (loading ||
        working.isNotEmpty ||
        !bounded(file) ||
        !fileValid(file, captured) ||
        file['status'] != 'ready')
      return;
    final id = file['id'] as String;
    MailAttachmentPreviewController? controller;
    setState(() {
      working.add(id);
      error = null;
      notice = null;
    });
    try {
      var verified = await verifiedFile(file, captured);
      if (verified == null || !mounted || !fileValid(file, captured)) return;
      final session = MailAttachmentPreviewController(verified);
      controller = session;
      verified = null;
      previewGuards[session] = () => fileValid(file, captured);
      setState(() => working.remove(id));
      await Navigator.of(context).push<void>(
        MaterialPageRoute(
          builder: (_) => MailAttachmentPreviewPage(
            controller: session,
            mayView: () => fileValid(file, captured),
            exporter: widget.exporter ?? exportMailAttachment,
          ),
        ),
      );
    } on ApiException catch (e) {
      if (e.status == 401 || e.status == 403) {
        deny();
      } else if (fileValid(file, captured)) {
        message(e.message);
      }
    } catch (_) {
      if (fileValid(file, captured)) {
        message(
          'Die Vorschau konnte nicht geladen werden. Bitte erneut versuchen.',
        );
      }
    } finally {
      if (controller != null) {
        previewGuards.remove(controller);
        controller.dispose();
      }
      if (mounted) setState(() => working.remove(id));
    }
  }

  Future<void> remove(Map<String, dynamic> file) async {
    final inquiry = widget.inquiryId ?? file['inquiry_id'];
    final captured = widget.api.token;
    if (loading ||
        !widget.canDelete ||
        inquiry is! String ||
        !RegExp(r'^[a-f0-9]{32}$').hasMatch(inquiry) ||
        !fileValid(file, captured) ||
        working.isNotEmpty)
      return;
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => ValueListenableBuilder<bool>(
        valueListenable: actionAllowed,
        builder: (context, allowed, _) => !allowed
            ? AlertDialog(
                title: const Text('Zugriff nicht mehr verfügbar'),
                actions: [
                  TextButton(
                    onPressed: () => Navigator.pop(context),
                    child: const Text('Schließen'),
                  ),
                ],
              )
            : AlertDialog(
                title: const Text('Anhang entfernen?'),
                content: Text(
                  '„${file['filename']}“ wird aus der Anfrage und ihren Projektdokumenten entfernt. Bereits übernommene Planquellen bleiben erhalten.',
                ),
                actions: [
                  TextButton(
                    onPressed: () => Navigator.pop(context, false),
                    child: const Text('Abbrechen'),
                  ),
                  FilledButton(
                    onPressed: () => Navigator.pop(context, true),
                    child: const Text('Anhang entfernen'),
                  ),
                ],
              ),
      ),
    );
    if (confirmed != true || !fileValid(file, captured)) return;
    final id = file['id'] as String;
    setState(() => working.add(id));
    try {
      await widget.api.call(
        '/api/inquiries/$inquiry/attachments/$id/delete',
        {},
      );
      if (!fileValid(file, captured)) return;
      setState(() {
        fetchEpoch++;
        loading = false;
        manifest = {
          ...?manifest,
          'files': files.where((row) => row['id'] != id).toList(),
          if (!project)
            'deleted_count': (manifest?['deleted_count'] as int? ?? 0) + 1,
        };
      });
      revalidatePreviews();
      if (!project) widget.onManifestChanged?.call(manifest);
      message('Anhang entfernt.', failure: false);
      await refresh();
    } on ApiException catch (e) {
      if (e.status == 401 || e.status == 403)
        deny();
      else if (sessionValid(captured))
        message('Anhang konnte nicht entfernt werden. Bitte erneut versuchen.');
    } catch (_) {
      if (sessionValid(captured))
        message('Anhang konnte nicht entfernt werden. Bitte erneut versuchen.');
    } finally {
      if (mounted) setState(() => working.remove(id));
    }
  }

  Future<void> importPlan(Map<String, dynamic> file) async {
    final captured = widget.api.token;
    if (!widget.canImportPlan ||
        loading ||
        working.isNotEmpty ||
        widget.api.version != 'v1' ||
        !project ||
        !bounded(file) ||
        !fileValid(file, captured) ||
        file['status'] != 'ready' ||
        !_planMedia.contains(file['media_type']))
      return;
    String? requestKey;
    final result = await showDialog<bool>(
      context: context,
      barrierDismissible: false,
      builder: (_) => _AttachmentPlanDialog(
        api: widget.api,
        projectId: widget.projectId!,
        file: file,
        accessAllowed: actionAllowed,
        maySubmit: () => fileValid(file, captured),
        requestId: (page, title) {
          requestKey = '${file['id']}|${file['sha256']}|$page|$title';
          return planRequests.putIfAbsent(requestKey!, offlineId);
        },
        onDenied: deny,
      ),
    );
    if (result == true && fileValid(file, captured)) {
      // A confirmed operation is complete. A later deliberate copy (including
      // after deleting its plan) must be a new request; uncertain retries above
      // continue to use the original ID.
      planRequests.remove(requestKey);
      message(
        'Planübernahme beauftragt. Die Verarbeitung erfolgt auf Hetzner.',
        failure: false,
      );
      widget.onPlans?.call();
    }
  }

  String summary() {
    if (needsUpdate || manifest == null)
      return 'E-Mail-Anhänge benötigen das neue Serverpaket. Bereits vorhandene Anfragen und Dokumentlinks bleiben nutzbar.';
    final ready = files.where((file) => file['status'] == 'ready').length;
    if (project) {
      final pending = manifest?['pending_count'] as int? ?? 0;
      final unknown = manifest?['unannounced_count'] as int? ?? 0;
      return '${files.isEmpty ? 'Noch keine E-Mail-Dateien im Projekt.' : '$ready Dateien aus verknüpften Anfragen verfügbar.'}'
          '${pending > 0 ? ' $pending Dateien werden noch übertragen.' : ''}'
          '${unknown > 0 ? ' Für $unknown Anfragen fehlt noch die Anhangsliste; weitere Dateien können fehlen.' : ''}';
    }
    if (manifest?['status'] == 'not_announced')
      return 'Für diese E-Mail wurde noch keine Anhangsliste übermittelt. Dateien können deshalb noch fehlen.';
    final expected = manifest?['expected_count'];
    final removed = manifest?['deleted_count'] as int? ?? 0;
    return manifest?['status'] == 'complete'
        ? 'Übertragung abgeschlossen · $ready verfügbar${removed > 0 ? ' · $removed entfernt' : ''}.'
        : '$ready${expected is int ? ' von $expected angekündigten Dateien' : ' Dateien'} verfügbar. Die Übertragung läuft noch${removed > 0 ? '; $removed wurden entfernt' : ''}.';
  }

  @override
  Widget build(BuildContext context) => Card(
    margin: const EdgeInsets.symmetric(vertical: 12),
    child: Padding(
      padding: const EdgeInsets.all(18),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Expanded(
                child: Text(
                  project ? 'E-Mail-Anhänge' : 'Anhänge',
                  style: Theme.of(context).textTheme.titleMedium,
                ),
              ),
              if (allowed && !widget.offlineMode)
                IconButton(
                  tooltip: 'Anhänge aktualisieren',
                  onPressed: loading || working.isNotEmpty ? null : refresh,
                  icon: const Icon(Icons.refresh),
                ),
            ],
          ),
          if (!allowed)
            const Text('Zugriff nicht mehr verfügbar. Bitte online anmelden.')
          else if (widget.offlineMode)
            const Text(
              'E-Mail-Anhänge sind nur mit Online-Anmeldung verfügbar. Die übrigen Projektdokumente und Links bleiben nutzbar.',
            )
          else ...[
            if (loading) const LinearProgressIndicator(),
            if (!loading || manifest != null) Text(summary()),
            if (error != null)
              Padding(
                padding: const EdgeInsets.only(top: 8),
                child: Text(
                  error!,
                  style: TextStyle(color: Theme.of(context).colorScheme.error),
                ),
              ),
            if (notice != null)
              Padding(
                padding: const EdgeInsets.only(top: 8),
                child: Text(notice!),
              ),
            for (final file in files)
              Padding(
                padding: const EdgeInsets.only(top: 16),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    InkWell(
                      key: ValueKey('mail-attachment-name-${file['id']}'),
                      borderRadius: BorderRadius.circular(6),
                      onTap:
                          file['status'] == 'ready' &&
                              bounded(file) &&
                              !loading &&
                              working.isEmpty &&
                              sessionValid(widget.api.token)
                          ? () => preview(file)
                          : null,
                      child: Padding(
                        padding: const EdgeInsets.symmetric(vertical: 4),
                        child: Text(
                          file['filename']?.toString() ?? 'Anhang',
                          maxLines: 2,
                          overflow: TextOverflow.ellipsis,
                          style: const TextStyle(fontWeight: FontWeight.w600),
                        ),
                      ),
                    ),
                    Text(
                      '${file['size'] is int ? attachmentSize(file['size']) : 'Größe noch offen'} · ${file['status'] == 'ready' ? 'Verfügbar' : 'Wird übertragen'}',
                    ),
                    if (project && file['subject'] is String)
                      Text('Aus Anfrage: ${file['subject']}'),
                    if (working.contains(file['id']))
                      const LinearProgressIndicator(),
                    Wrap(
                      spacing: 8,
                      runSpacing: 4,
                      children: [
                        TextButton.icon(
                          key: ValueKey(
                            'mail-attachment-preview-${file['id']}',
                          ),
                          onPressed:
                              file['status'] == 'ready' &&
                                  bounded(file) &&
                                  !loading &&
                                  working.isEmpty &&
                                  sessionValid(widget.api.token)
                              ? () => preview(file)
                              : null,
                          icon: const Icon(Icons.visibility_outlined),
                          label: const Text('Vorschau'),
                        ),
                        Builder(
                          builder: (buttonContext) => OutlinedButton.icon(
                            key: ValueKey(
                              'mail-attachment-download-${file['id']}',
                            ),
                            onPressed:
                                file['status'] == 'ready' &&
                                    bounded(file) &&
                                    !loading &&
                                    working.isEmpty &&
                                    sessionValid(widget.api.token)
                                ? () => download(buttonContext, file)
                                : null,
                            icon: const Icon(Icons.download_outlined),
                            label: Text(
                              Platform.isIOS || Platform.isAndroid
                                  ? 'Speichern / Teilen'
                                  : 'Datei speichern',
                            ),
                          ),
                        ),
                        if (project &&
                            widget.canImportPlan &&
                            widget.api.version == 'v1' &&
                            _planMedia.contains(file['media_type']) &&
                            file['can_import_plan'] != false)
                          TextButton.icon(
                            key: ValueKey('mail-attachment-plan-${file['id']}'),
                            onPressed:
                                file['status'] == 'ready' &&
                                    bounded(file) &&
                                    !loading &&
                                    working.isEmpty &&
                                    sessionValid(widget.api.token)
                                ? () => importPlan(file)
                                : null,
                            icon: const Icon(Icons.architecture_outlined),
                            label: const Text('Als Plan übernehmen'),
                          ),
                        if (widget.canDelete)
                          TextButton.icon(
                            key: ValueKey(
                              'mail-attachment-remove-${file['id']}',
                            ),
                            onPressed:
                                bounded(file) &&
                                    !loading &&
                                    working.isEmpty &&
                                    sessionValid(widget.api.token)
                                ? () => remove(file)
                                : null,
                            icon: const Icon(Icons.delete_outline),
                            label: const Text('Entfernen'),
                          ),
                      ],
                    ),
                  ],
                ),
              ),
          ],
        ],
      ),
    ),
  );
}

class _AttachmentPlanDialog extends StatefulWidget {
  final OfficeApi api;
  final String projectId;
  final Map<String, dynamic> file;
  final ValueListenable<bool> accessAllowed;
  final bool Function() maySubmit;
  final String Function(int page, String title) requestId;
  final VoidCallback onDenied;
  const _AttachmentPlanDialog({
    required this.api,
    required this.projectId,
    required this.file,
    required this.accessAllowed,
    required this.maySubmit,
    required this.requestId,
    required this.onDenied,
  });
  @override
  State<_AttachmentPlanDialog> createState() => _AttachmentPlanDialogState();
}

class _AttachmentPlanDialogState extends State<_AttachmentPlanDialog> {
  final form = GlobalKey<FormState>();
  final page = TextEditingController(text: '1');
  late final TextEditingController title;
  bool busy = false, uncertain = false;
  String? error;
  Map<String, dynamic>? pending;
  @override
  void initState() {
    super.initState();
    final fallback = widget.file['filename'].toString().replaceFirst(
      RegExp(r'\.[^.]+$'),
      '',
    );
    title = TextEditingController(
      text: fallback.length > 200 ? fallback.substring(0, 200) : fallback,
    );
  }

  @override
  void dispose() {
    title.dispose();
    page.dispose();
    super.dispose();
  }

  Future<void> submit() async {
    if (busy || !widget.maySubmit() || !form.currentState!.validate()) return;
    final chosen = widget.file['media_type'] == 'application/pdf'
        ? int.parse(page.text.trim()) - 1
        : 0;
    pending ??= {
      'request_id': widget.requestId(chosen, title.text.trim()),
      'page': chosen,
      'title': title.text.trim(),
    };
    setState(() {
      busy = true;
      error = null;
    });
    try {
      final result = await widget.api.call(
        '/api/projects/${widget.projectId}/mail-attachments/${widget.file['id']}/plan-import',
        pending,
      );
      if (!mounted || !widget.maySubmit()) return;
      if (result is! Map ||
          result['id'] is! String ||
          result['project_id'] != widget.projectId) {
        throw const ApiException(
          0,
          'Die Planübernahme konnte noch nicht bestätigt werden.',
        );
      }
      setState(() => busy = false);
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (mounted && widget.maySubmit()) Navigator.pop(context, true);
      });
    } on ApiException catch (e) {
      if (e.status == 401 || e.status == 403) {
        widget.onDenied();
        return;
      }
      if (!mounted || !widget.maySubmit()) return;
      setState(() {
        uncertain = e.status == 0 || e.status >= 500;
        if (!uncertain) pending = null;
        error = uncertain
            ? 'Die Antwort ist noch nicht bestätigt. Erneut übernehmen verwendet denselben Auftrag.'
            : e.message;
      });
    } catch (_) {
      if (mounted && widget.maySubmit())
        setState(() {
          uncertain = true;
          error = 'Die Antwort ist noch nicht bestätigt. Bitte denselben Auftrag erneut übernehmen.';
        });
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  @override
  Widget build(BuildContext context) => ValueListenableBuilder<bool>(
    valueListenable: widget.accessAllowed,
    builder: (context, allowed, _) => !allowed
        ? AlertDialog(
            title: const Text('Zugriff nicht mehr verfügbar'),
            actions: [
              TextButton(
                onPressed: () => Navigator.pop(context),
                child: const Text('Schließen'),
              ),
            ],
          )
        : PopScope(
            canPop: !busy,
            child: AlertDialog(
              title: const Text('Anhang als Plan übernehmen'),
              content: SizedBox(
                width: 480,
                child: SingleChildScrollView(
                  child: Form(
                    key: form,
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        Text(widget.file['filename']),
                        const SizedBox(height: 16),
                        TextFormField(
                          key: const ValueKey('mail-plan-title'),
                          controller: title,
                          readOnly: busy || uncertain,
                          maxLength: 200,
                          decoration: const InputDecoration(
                            labelText: 'Plantitel / Geschoss',
                          ),
                          validator: (value) => value?.trim().isEmpty ?? true
                              ? 'Bitte einen Plantitel angeben.'
                              : null,
                        ),
                        if (widget.file['media_type'] == 'application/pdf')
                          TextFormField(
                            key: const ValueKey('mail-plan-page'),
                            controller: page,
                            readOnly: busy || uncertain,
                            keyboardType: TextInputType.number,
                            decoration: const InputDecoration(
                              labelText: 'PDF-Seite (1–50)',
                            ),
                            validator: (value) {
                              final chosen = int.tryParse(value?.trim() ?? '');
                              return chosen == null || chosen < 1 || chosen > 50
                                  ? 'Eine Seite von 1 bis 50 wählen.'
                                  : null;
                            },
                          ),
                        const SizedBox(height: 12),
                        const Text(
                          'Die gewählte Quelle wird auf dem Smartplan-Server in die Projektpläne übernommen und auf Hetzner verarbeitet. Die E-Mail-Datei bleibt erhalten.',
                        ),
                        if (error != null)
                          Padding(
                            padding: const EdgeInsets.only(top: 12),
                            child: Text(
                              error!,
                              style: TextStyle(
                                color: Theme.of(context).colorScheme.error,
                              ),
                            ),
                          ),
                        if (busy) const LinearProgressIndicator(),
                      ],
                    ),
                  ),
                ),
              ),
              actions: [
                TextButton(
                  onPressed: busy ? null : () => Navigator.pop(context, false),
                  child: const Text('Abbrechen'),
                ),
                FilledButton(
                  onPressed: busy ? null : submit,
                  child: Text(
                    uncertain ? 'Erneut übernehmen' : 'Plan übernehmen',
                  ),
                ),
              ],
            ),
          ),
  );
}

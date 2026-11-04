import 'dart:io';

import 'package:file_selector/file_selector.dart';
import 'package:flutter/material.dart';

import 'api.dart';
import 'business_accounting_year_evidence_contract.dart';
import 'business_session.dart';
import 'design.dart';
import 'mail_attachment_widgets.dart';

export 'business_accounting_year_evidence_contract.dart';

class BusinessYearEvidencePage extends StatefulWidget {
  const BusinessYearEvidencePage({
    super.key,
    required this.session,
    required this.exportEntry,
    this.exportFile,
  });
  final BusinessSession session;
  final Map<String, dynamic> exportEntry;

  /// Tests or platform hosts must check authorization immediately before writing.
  final Future<void> Function(VerifiedMailAttachment, Future<bool> Function())?
  exportFile;
  @override
  State<BusinessYearEvidencePage> createState() =>
      _BusinessYearEvidencePageState();
}

class _BusinessYearEvidencePageState extends State<BusinessYearEvidencePage>
    with WidgetsBindingObserver {
  Map<String, dynamic>? entry, metadata;
  String? error, message, token, baseUrl;
  Object? generation;
  bool busy = false, denied = false, backgrounded = false;
  int epoch = 0;
  BusinessSession get session => widget.session;
  bool get readable =>
      yearEvidenceReadable(session) && !denied && !backgrounded;
  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    session.addListener(changed);
    bind();
    load();
  }

  void bind() {
    token = session.api.token;
    baseUrl = session.api.base;
    generation = session.generation;
  }

  void clear() {
    epoch++;
    entry = metadata = null;
    error = message = null;
    busy = false;
  }

  void changed() {
    if (!mounted) return;
    setState(() {
      if (!yearEvidenceReadable(session) ||
          token != session.api.token ||
          baseUrl != session.api.base ||
          generation != session.generation) {
        clear();
        bind();
      }
    });
  }

  @override
  void didUpdateWidget(covariant BusinessYearEvidencePage old) {
    super.didUpdateWidget(old);
    if (!identical(old.session, session) ||
        !identical(old.exportEntry, widget.exportEntry)) {
      old.session.removeListener(changed);
      session.addListener(changed);
      clear();
      bind();
      load();
    }
  }

  @override
  void dispose() {
    epoch++;
    WidgetsBinding.instance.removeObserver(this);
    session.removeListener(changed);
    super.dispose();
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState value) {
    if (!mounted) return;
    if ([
      AppLifecycleState.paused,
      AppLifecycleState.hidden,
      AppLifecycleState.detached,
    ].contains(value)) {
      setState(() {
        clear();
        backgrounded = denied = true;
      });
    } else if (value == AppLifecycleState.resumed) {
      setState(() => backgrounded = false);
    }
  }

  bool same(int stamp) =>
      mounted &&
      stamp == epoch &&
      readable &&
      token == session.api.token &&
      baseUrl == session.api.base &&
      generation == session.generation;
  void failure(Object value, int stamp) {
    if (!mounted || stamp != epoch) return;
    setState(() {
      entry = metadata = null;
      error = value is ApiException ? value.message : 'Der ursprüngliche Jahresnachweis konnte nicht sicher gelesen werden.';
      if (value is ApiException && [401, 403, 404].contains(value.status)) {
        denied = true;
        error = null;
      }
    });
  }

  Future<void> fresh(int stamp) async {
    if (!same(stamp))
      throw const ApiException(
        0,
        'Der ursprüngliche Exportkontext wurde geschlossen.',
      );
    await session.load();
    if (!same(stamp) || session.error != null || session.loading)
      throw const ApiException(
        403,
        'Aktuelle globale Finanzleserechte fehlen.',
      );
  }

  Future<Map<String, dynamic>> readMetadata(
    int stamp,
    Map<String, dynamic> original, {
    Map<String, dynamic>? previous,
  }) async {
    await fresh(stamp);
    final result = await session.read(yearEvidencePath(original['id']));
    if (!same(stamp))
      throw const ApiException(
        0,
        'Der ursprüngliche Exportkontext wurde gewechselt.',
      );
    final validated = yearEvidenceMetadata(
      result,
      original,
      previous: previous,
    );
    await fresh(stamp);
    return validated;
  }

  Future<void> recheck() async {
    if (busy || backgrounded) return;
    final originalSession = session;
    await originalSession.load();
    if (!mounted || backgrounded || !identical(originalSession, session))
      return;
    if (!yearEvidenceReadable(session)) {
      setState(() {
        clear();
        denied = true;
      });
      return;
    }
    bind();
    await load();
  }

  Future<void> load() async {
    if (busy || backgrounded || !yearEvidenceReadable(session)) return;
    final stamp = ++epoch;
    setState(() {
      denied = false;
      busy = true;
      entry = metadata = null;
      error = message = null;
    });
    try {
      final original = yearEvidenceCopy(yearEvidenceEntry(widget.exportEntry));
      await fresh(stamp);
      final value = await session.read(
        '/accounting/euer/exports/${original['id']}',
      );
      if (!same(stamp)) return;
      yearEvidenceOriginalExport(value, original);
      final meta = await readMetadata(stamp, original);
      if (!same(stamp)) return;
      setState(() {
        entry = original;
        metadata = yearEvidenceCopy(meta);
      });
    } catch (e) {
      failure(e, stamp);
    } finally {
      if (mounted && stamp == epoch) setState(() => busy = false);
    }
  }

  Future<void> download() async {
    if (busy || !readable || metadata == null || entry == null) return;
    final stamp = epoch,
        original = yearEvidenceCopy(entry),
        expected = yearEvidenceCopy(metadata);
    setState(() {
      busy = true;
      error = message = null;
    });
    try {
      await readMetadata(stamp, original, previous: expected);
      if (!same(stamp)) return;
      final bytes = await session.api.bytes(
        session.path(expected['archive_path']),
        mediaType: 'application/zip',
        maxBytes: yearEvidenceMaxBytes,
      );
      if (!same(stamp)) return;
      final attachment = yearEvidenceAttachment(bytes, expected, original);
      Future<bool> authorize() async {
        if (!same(stamp)) return false;
        await readMetadata(stamp, original, previous: expected);
        return same(stamp);
      }

      if (!await authorize()) return;
      if (widget.exportFile != null) {
        await widget.exportFile!(attachment, authorize);
      } else if (!Platform.isIOS && !Platform.isAndroid) {
        final location = await getSaveLocation(
          suggestedName: attachment.filename,
        );
        if (location == null) return;
        if (!await authorize()) return;
        await File(location.path).writeAsBytes(attachment.bytes, flush: true);
      } else {
        if (!await authorize()) return;
        await exportMailAttachment(context, attachment, () => same(stamp));
      }
      if (same(stamp))
        setState(
          () => message = 'ZIPdatei nach Größe und SHA-256 für die Dateiausgabe abgeglichen.',
        );
    } catch (e) {
      failure(e, stamp);
    } finally {
      if (mounted && stamp == epoch) setState(() => busy = false);
    }
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(title: const Text('Jahresnachweis mit Originalen')),
    body: !readable
        ? Center(
            child: Padding(
              padding: const EdgeInsets.all(24),
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  const Text(
                    'Der ursprüngliche Jahresnachweis ist derzeit nicht freigegeben.',
                  ),
                  OutlinedButton(
                    onPressed: !busy && !backgrounded ? recheck : null,
                    child: const Text('Zugriff erneut prüfen'),
                  ),
                ],
              ),
            ),
          )
        : ListView(
            padding: const EdgeInsets.all(16),
            children: [
              if (busy) const LinearProgressIndicator(),
              if (error != null) Notice(error!, error: true),
              if (message != null) Notice(message!),
              const Notice(
                'Originale und Journalentscheidungen gehören genau zum damals bestätigten EÜR-Export. Das Paket ist keine Steuererklärung und kein DATEV-Importformat.',
              ),
              OutlinedButton(
                onPressed: !busy ? load : null,
                child: const Text('Originalnachweis erneut lesen'),
              ),
              if (metadata != null) ...[
                Text(
                  'Bestätigter Jahresexport ${metadata!['year']}',
                  style: Theme.of(context).textTheme.titleLarge,
                ),
                Text(
                  metadata!['original_year_complete'] == true
                      ? 'Der ursprüngliche EÜR-Report kennzeichnet seine erfassten Quellen als vollständig.'
                      : 'Der damalige Jahresstand war unvollständig. Das Archiv schließt diese offenen Fragen nicht.',
                ),
                Text(
                  '${metadata!['original_count']} beigefügte Originaldateien · ${attachmentSize(metadata!['size'])}',
                ),
                const Text(
                  'Private Personaloriginale sind nicht Bestandteil dieses Finanznachweises.',
                ),
                for (final boundary in metadata!['private_source_boundaries'])
                  Text(
                    boundary == 'payroll_cash'
                        ? 'Lohn: ausschließlich öffentliche Finanzprojektionen; keine privaten Abrechnungsoriginale.'
                        : 'Reisen: ausschließlich öffentliche Finanzprojektionen; keine privaten Reiseoriginale.',
                  ),
                SelectableText('Originalexport: ${metadata!['export_id']}'),
                SelectableText('Exporthash: ${metadata!['export_hash']}'),
                SelectableText('ZIP-SHA-256: ${metadata!['sha256']}'),
                Text(metadata!['filename']),
                const Text(
                  'Das Paket enthält die aufgelösten Originale und einen lokalen Prüfer. Die Hashprüfung bestätigt keine eigenständige Vollständigkeit aller zugrunde liegenden Nachweise. Für die Offlineprüfung ist der separat aufbewahrte, hier angezeigte Archiv-SHA-256 erforderlich.',
                ),
                FilledButton(
                  onPressed: !busy ? download : null,
                  child: const Text('Original-/Journal-ZIP speichern'),
                ),
              ],
            ],
          ),
  );
}

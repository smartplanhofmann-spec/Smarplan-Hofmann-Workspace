import 'dart:io';
import 'dart:typed_data';

import 'package:file_selector/file_selector.dart';
import 'package:flutter/material.dart';
import 'package:printing/printing.dart';

import 'api.dart';
import 'design.dart';

class ReportPdfPage extends StatefulWidget {
  final OfficeApi api;
  final String reportId;
  const ReportPdfPage({super.key, required this.api, required this.reportId});

  @override
  State<ReportPdfPage> createState() => _ReportPdfPageState();
}

class _ReportPdfPageState extends State<ReportPdfPage> {
  Uint8List? bytes;
  String? error;
  bool saving = false;

  @override
  void initState() {
    super.initState();
    load();
  }

  Future<void> load() async {
    setState(() {
      bytes = null;
      error = null;
    });
    try {
      final data = await widget.api.pdf(widget.reportId);
      if (mounted) setState(() => bytes = data);
    } catch (e) {
      if (mounted) setState(() => error = e.toString());
    }
  }

  Future<void> save() async {
    setState(() => saving = true);
    try {
      final filename = 'smartplan-${widget.reportId}.pdf';
      if (Platform.isWindows) {
        final target = await getSaveLocation(
          suggestedName: filename,
          acceptedTypeGroups: [
            const XTypeGroup(label: 'PDF', extensions: ['pdf']),
          ],
        );
        if (target == null) return;
        await XFile.fromData(
          bytes!,
          mimeType: 'application/pdf',
          name: filename,
        ).saveTo(target.path);
      } else {
        final shared = await Printing.sharePdf(
          bytes: bytes!,
          filename: filename,
        );
        if (!shared)
          throw const ApiException(0, 'PDF-Ausgabe nicht verfügbar.');
      }
    } catch (_) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text(
              'PDF konnte nicht ausgegeben werden. Bitte erneut versuchen.',
            ),
          ),
        );
      }
    } finally {
      if (mounted) setState(() => saving = false);
    }
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(
      title: const Text('PDF-Vorschau'),
      actions: [
        Padding(
          padding: const EdgeInsets.only(right: 20),
          child: FilledButton.icon(
            onPressed: bytes == null || saving ? null : save,
            icon: Icon(
              saving ? Icons.hourglass_top_rounded : Icons.save_alt_rounded,
              size: 17,
            ),
            label: Text(
              Platform.isWindows ? 'PDF speichern' : 'Speichern / Teilen',
            ),
          ),
        ),
      ],
    ),
    body: error != null
        ? Center(
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                Padding(
                  padding: const EdgeInsets.all(24),
                  child: Notice(error!),
                ),
                TextButton(
                  onPressed: load,
                  child: const Text('Erneut versuchen'),
                ),
              ],
            ),
          )
        : bytes == null
        ? const Center(child: CircularProgressIndicator())
        : PdfPreview(
            build: (_) async => bytes!,
            pdfFileName: 'smartplan-${widget.reportId}.pdf',
            canChangePageFormat: false,
            canChangeOrientation: false,
            allowPrinting: false,
            allowSharing: false,
            canDebug: false,
          ),
  );
}

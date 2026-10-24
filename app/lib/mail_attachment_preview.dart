import 'dart:async';
import 'dart:io';
import 'dart:math' as math;
import 'dart:typed_data';
import 'dart:ui' as ui;

import 'package:flutter/material.dart';
import 'package:flutter/scheduler.dart';
import 'package:pdfrx/pdfrx.dart' as pdf;

class VerifiedMailAttachment {
  final Uint8List bytes;
  final String filename, mediaType, sha256;
  const VerifiedMailAttachment({
    required this.bytes,
    required this.filename,
    required this.mediaType,
    required this.sha256,
  });
}

enum MailAttachmentExportResult { saved, shared, cancelled }

/// Native file output must check the live guard after its picker as well.
typedef MailAttachmentExporter = Future<MailAttachmentExportResult> Function(
  BuildContext context,
  VerifiedMailAttachment attachment,
  bool Function() mayExport,
);

/// The route owns a revocable, memory-only document. No preview file is staged.
class MailAttachmentPreviewController extends ChangeNotifier {
  MailAttachmentPreviewController(VerifiedMailAttachment document)
    : _document = document;
  VerifiedMailAttachment? _document;
  VerifiedMailAttachment? get document => _document;

  void revoke() {
    if (_document == null) return;
    _document = null;
    notifyListeners();
  }

  @override
  void dispose() {
    revoke();
    super.dispose();
  }
}

class MailAttachmentPreviewPage extends StatefulWidget {
  final MailAttachmentPreviewController controller;
  final bool Function() mayView;
  final MailAttachmentExporter exporter;
  const MailAttachmentPreviewPage({
    super.key,
    required this.controller,
    required this.mayView,
    required this.exporter,
  });
  @override
  State<MailAttachmentPreviewPage> createState() =>
      _MailAttachmentPreviewPageState();
}

class _MailAttachmentPreviewPageState extends State<MailAttachmentPreviewPage> {
  final transformation = TransformationController();
  ui.Image? image;
  pdf.PdfDocument? pdfDocument;
  pdf.PdfPageRenderCancellationToken? pdfCancellation;
  int pageIndex = 0;
  bool loading = false, imageFailed = false, exporting = false;
  int generation = 0;
  bool get allowed => widget.controller.document != null && widget.mayView();
  bool get isImage => const {
    'image/jpeg',
    'image/png',
  }.contains(widget.controller.document?.mediaType);
  bool get isPdf => widget.controller.document?.mediaType == 'application/pdf';

  @override
  void initState() {
    super.initState();
    widget.controller.addListener(accessChanged);
    if (isImage) unawaited(decodeImage());
    if (isPdf) unawaited(openPdf());
  }

  void releaseImage() {
    final previous = image;
    image = null;
    if (previous != null) {
      // RawImage is removed by this frame before its native image handle dies.
      WidgetsBinding.instance.addPostFrameCallback((_) => previous.dispose());
    }
  }

  void accessChanged() {
    if (!mounted) return;
    if (!allowed) {
      generation++;
      releasePdf();
      releaseImage();
      if (widget.controller.document != null) widget.controller.revoke();
      loading = false;
      // Metadata can be replaced while the underlying route is building.
      // Revoke the buffer immediately; rebuild this sibling route next frame.
      if (SchedulerBinding.instance.schedulerPhase ==
          SchedulerPhase.persistentCallbacks) {
        WidgetsBinding.instance.addPostFrameCallback((_) {
          if (mounted) setState(() {});
        });
      } else {
        setState(() {});
      }
    }
  }

  @override
  void dispose() {
    generation++;
    widget.controller.removeListener(accessChanged);
    widget.controller.revoke();
    releasePdf();
    image?.dispose();
    image = null;
    transformation.dispose();
    super.dispose();
  }

  void releasePdf() {
    pdfCancellation?.cancel();
    pdfCancellation = null;
    final document = pdfDocument;
    pdfDocument = null;
    if (document != null) unawaited(document.dispose());
  }

  Future<void> openPdf() async {
    final source = widget.controller.document;
    if (source == null || !allowed) return;
    final current = ++generation;
    setState(() => loading = true);
    pdf.PdfDocument? opened;
    try {
      await pdf.pdfrxFlutterInitialize();
      if (!mounted || current != generation || !allowed) return;
      opened = await pdf.PdfDocument.openData(
        source.bytes,
        sourceName:
            'mail-preview-${source.sha256}-${identityHashCode(widget.controller)}',
        useProgressiveLoading: true,
        maxSizeToCacheOnMemory: source.bytes.length,
      );
      if (!mounted || current != generation || !allowed) return;
      if (opened.pages.isEmpty || opened.pages.length > 1000) {
        throw const FormatException('PDF page count');
      }
      pdfDocument = opened;
      opened = null;
      await renderPdfPage(0);
    } catch (_) {
      if (mounted && current == generation && allowed) {
        setState(() {
          loading = false;
          imageFailed = true;
        });
      }
    } finally {
      await opened?.dispose();
    }
  }

  Future<void> renderPdfPage(int index) async {
    final document = pdfDocument;
    if (!allowed ||
        document == null ||
        index < 0 ||
        index >= document.pages.length)
      return;
    final current = ++generation;
    pdfCancellation?.cancel();
    pdf.PdfPageRenderCancellationToken? cancellation;
    setState(() {
      releaseImage();
      transformation.value = Matrix4.identity();
      pageIndex = index;
      loading = true;
      imageFailed = false;
    });
    pdf.PdfImage? raster;
    try {
      if (!document.pages[index].isLoaded) {
        await document.reloadPages(pageNumbersToReload: [index + 1]);
      }
      if (!mounted || current != generation || !allowed) return;
      final page = document.pages[index];
      cancellation = page.createCancellationToken();
      pdfCancellation = cancellation;
      if (!page.width.isFinite ||
          !page.height.isFinite ||
          page.width <= 0 ||
          page.height <= 0) {
        throw const FormatException('PDF page dimensions');
      }
      // Explicit bitmap dimensions bound native allocation before PDFium
      // renders, even for extremely large PDF MediaBoxes. Keep one page only.
      final scale = 2048 / math.max(page.width, page.height);
      final width = math.max(1, (page.width * scale).round()).clamp(1, 2048);
      final height = math.max(1, (page.height * scale).round()).clamp(1, 2048);
      raster = await page.render(
        width: width,
        height: height,
        fullWidth: width.toDouble(),
        fullHeight: height.toDouble(),
        annotationRenderingMode: pdf.PdfAnnotationRenderingMode.annotation,
        flags: pdf.PdfPageRenderFlags.limitedImageCache,
        cancellationToken: cancellation,
      );
      if (raster == null) throw const FormatException('PDF page unavailable');
      if (!mounted || current != generation || !allowed) return;
      final decoded = await raster.createImage();
      if (!mounted || current != generation || !allowed) {
        decoded.dispose();
        return;
      }
      setState(() {
        image = decoded;
        loading = false;
      });
    } catch (_) {
      if (mounted && current == generation && allowed) {
        setState(() {
          loading = false;
          imageFailed = true;
        });
      }
    } finally {
      raster?.dispose();
      if (identical(pdfCancellation, cancellation)) pdfCancellation = null;
    }
  }

  Future<void> decodeImage() async {
    final document = widget.controller.document;
    if (document == null || !allowed) return;
    final current = ++generation;
    setState(() => loading = true);
    ui.ImmutableBuffer? buffer;
    ui.ImageDescriptor? descriptor;
    ui.Codec? codec;
    try {
      final bytes = document.bytes;
      final png =
          bytes.length >= 8 &&
          bytes[0] == 137 &&
          bytes[1] == 80 &&
          bytes[2] == 78 &&
          bytes[3] == 71 &&
          bytes[4] == 13 &&
          bytes[5] == 10 &&
          bytes[6] == 26 &&
          bytes[7] == 10;
      final jpeg =
          bytes.length >= 3 &&
          bytes[0] == 255 &&
          bytes[1] == 216 &&
          bytes[2] == 255;
      if ((document.mediaType == 'image/png' && !png) ||
          (document.mediaType == 'image/jpeg' && !jpeg)) {
        throw const FormatException('Image signature');
      }
      buffer = await ui.ImmutableBuffer.fromUint8List(bytes);
      descriptor = await ui.ImageDescriptor.encoded(buffer);
      // Inspect dimensions before requesting any decoded pixel buffer. Keep
      // ordinary 48 MP camera photos, reject implausible compressed canvases.
      if (descriptor.width <= 0 ||
          descriptor.height <= 0 ||
          descriptor.width > 16384 ||
          descriptor.height > 16384 ||
          descriptor.width * descriptor.height > 50000000) {
        throw const FormatException('Image dimensions');
      }
      if (!mounted || current != generation || !allowed) return;
      final scale = math.min(
        1.0,
        2048 / math.max(descriptor.width, descriptor.height),
      );
      codec = await descriptor.instantiateCodec(
        targetWidth: math.max(1, (descriptor.width * scale).round()),
        targetHeight: math.max(1, (descriptor.height * scale).round()),
      );
      final frame = await codec.getNextFrame();
      if (!mounted || current != generation || !allowed) {
        frame.image.dispose();
        return;
      }
      setState(() {
        image = frame.image;
        loading = false;
      });
    } catch (_) {
      if (mounted && current == generation && allowed) {
        setState(() {
          loading = false;
          imageFailed = true;
        });
      }
    } finally {
      codec?.dispose();
      descriptor?.dispose();
      buffer?.dispose();
    }
  }

  Future<void> export(BuildContext buttonContext) async {
    if (!allowed || exporting) return;
    final document = widget.controller.document!;
    setState(() => exporting = true);
    try {
      final result = await widget.exporter(
        buttonContext,
        document,
        () => allowed,
      );
      if (!mounted ||
          !allowed ||
          result == MailAttachmentExportResult.cancelled)
        return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(
            result == MailAttachmentExportResult.saved
                ? 'Datei gespeichert.'
                : 'Datei zum Speichern oder Teilen übergeben.',
          ),
        ),
      );
    } catch (_) {
      if (mounted && allowed) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text(
              'Datei konnte nicht ausgegeben werden. Bitte erneut versuchen.',
            ),
          ),
        );
      }
    } finally {
      if (mounted) setState(() => exporting = false);
    }
  }

  Widget fallback(String text) => Center(
    child: Padding(
      padding: const EdgeInsets.all(28),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          const Icon(Icons.description_outlined, size: 44),
          const SizedBox(height: 16),
          Text(text, textAlign: TextAlign.center),
          const SizedBox(height: 12),
          Text(
            Platform.isIOS || Platform.isAndroid
                ? 'Das Original bleibt erhalten. Oben kannst du es speichern oder teilen.'
                : 'Das Original bleibt erhalten. Über „Datei speichern“ kannst du es auf deinem Gerät ablegen.',
            textAlign: TextAlign.center,
          ),
        ],
      ),
    ),
  );

  Widget preview() {
    if (!allowed) {
      return const Center(
        child: Padding(
          padding: EdgeInsets.all(28),
          child: Text(
            'Die Vorschau ist nicht mehr verfügbar. Bitte schließen und bei Bedarf online anmelden.',
            textAlign: TextAlign.center,
          ),
        ),
      );
    }
    if (isImage || isPdf) {
      if (loading) return const Center(child: CircularProgressIndicator());
      if (imageFailed || image == null) {
        return fallback(
          isPdf
              ? 'Diese PDF-Seite kann auf dem Gerät nicht angezeigt werden. Die Datei ist möglicherweise geschützt, beschädigt oder zu umfangreich.'
              : 'Dieses Bild kann auf dem Gerät nicht sicher angezeigt werden.',
        );
      }
      return InteractiveViewer(
        key: ValueKey(
          isPdf ? 'mail-attachment-pdf-view' : 'mail-attachment-image-view',
        ),
        transformationController: transformation,
        minScale: 1,
        maxScale: 8,
        child: SizedBox.expand(
          child: RawImage(image: image, fit: BoxFit.contain),
        ),
      );
    }
    return fallback(
      'Für dieses Dateiformat ist keine Vorschau in der App verfügbar.',
    );
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(
      leading: CloseButton(onPressed: () => Navigator.maybePop(context)),
      title: const Text('Vorschau'),
      actions: [
        Padding(
          padding: const EdgeInsets.only(right: 12),
          child: Builder(
            builder: (buttonContext) => OutlinedButton.icon(
              key: const ValueKey('mail-preview-export'),
              onPressed: allowed && !exporting
                  ? () => export(buttonContext)
                  : null,
              icon: Icon(
                exporting ? Icons.hourglass_top : Icons.download_outlined,
              ),
              label: Text(
                Platform.isIOS || Platform.isAndroid
                    ? 'Speichern / Teilen'
                    : 'Datei speichern',
              ),
            ),
          ),
        ),
      ],
    ),
    body: SafeArea(
      child: Column(
        children: [
          if (allowed)
            Padding(
              padding: const EdgeInsets.fromLTRB(20, 12, 20, 12),
              child: Row(
                children: [
                  Expanded(
                    child: Text(
                      widget.controller.document!.filename,
                      maxLines: 2,
                      overflow: TextOverflow.ellipsis,
                    ),
                  ),
                  if ((isImage || isPdf) && image != null)
                    IconButton(
                      tooltip: 'Ansicht einpassen',
                      onPressed: () =>
                          transformation.value = Matrix4.identity(),
                      icon: const Icon(Icons.fit_screen),
                    ),
                ],
              ),
            ),
          const Divider(height: 1),
          Expanded(child: preview()),
          if (allowed && isPdf && pdfDocument != null)
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
              child: Row(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  IconButton(
                    key: const ValueKey('mail-preview-previous-page'),
                    tooltip: 'Vorherige PDF-Seite',
                    onPressed: !loading && pageIndex > 0
                        ? () => renderPdfPage(pageIndex - 1)
                        : null,
                    icon: const Icon(Icons.chevron_left),
                  ),
                  Padding(
                    padding: const EdgeInsets.symmetric(horizontal: 16),
                    child: Text(
                      'Seite ${pageIndex + 1} von ${pdfDocument!.pages.length}',
                    ),
                  ),
                  IconButton(
                    key: const ValueKey('mail-preview-next-page'),
                    tooltip: 'Nächste PDF-Seite',
                    onPressed:
                        !loading && pageIndex + 1 < pdfDocument!.pages.length
                        ? () => renderPdfPage(pageIndex + 1)
                        : null,
                    icon: const Icon(Icons.chevron_right),
                  ),
                ],
              ),
            ),
        ],
      ),
    ),
  );
}

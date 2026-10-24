import 'dart:async';
import 'dart:convert';
import 'dart:io';
import 'dart:typed_data' show BytesBuilder;
import 'dart:ui' as ui;

import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:pdfrx/pdfrx.dart' as pdf;
import 'package:smartplan_office/mail_attachment_preview.dart'
    show MailAttachmentPreviewController, MailAttachmentPreviewPage;
import 'package:smartplan_office/mail_attachment_widgets.dart';

import 'mail_attachment_widget_test.dart'
    show AttachmentApi, attachment, inquiry;

final _png = base64Decode(
  'iVBORw0KGgoAAAANSUhEUgAAACgAAAAeCAIAAADRv8uKAAAAUklEQVR4nGP8//8/w0AApgGxddRiegIWND4jIyMVTceTcgeNjyGA8jxGMORGXuIatXjU4lGLRy0etXjU4sFnMfaGAHUbQFjBgPmYcbQnMewtBgCfvQw+z8BVfQAAAABJRU5ErkJggg==',
);

Uint8List _twoPagePdf({int width = 100, int height = 100}) {
  String stream(String shade) {
    final data = '0 0 $width $height re\n$shade g f\n';
    return '<< /Length ${data.length} >>\nstream\n${data}endstream';
  }

  final objects = [
    '<< /Type /Catalog /Pages 2 0 R >>',
    '<< /Type /Pages /Count 2 /Kids [3 0 R 4 0 R] >>',
    '<< /Type /Page /Parent 2 0 R /MediaBox [0 0 $width $height] /Contents 5 0 R >>',
    '<< /Type /Page /Parent 2 0 R /MediaBox [0 0 $width $height] /Contents 6 0 R >>',
    stream('0.8'),
    stream('0.4'),
  ];
  final result = StringBuffer('%PDF-1.4\n');
  final offsets = <int>[];
  for (var index = 0; index < objects.length; index++) {
    offsets.add(result.length);
    result.write('${index + 1} 0 obj\n${objects[index]}\nendobj\n');
  }
  final xref = result.length;
  result.write('xref\n0 ${objects.length + 1}\n0000000000 65535 f \n');
  for (final offset in offsets) {
    result.write('${offset.toString().padLeft(10, '0')} 00000 n \n');
  }
  result.write(
    'trailer\n<< /Size ${objects.length + 1} /Root 1 0 R >>\n'
    'startxref\n$xref\n%%EOF\n',
  );
  return Uint8List.fromList(ascii.encode(result.toString()));
}

Uint8List _widePng() {
  int crc32(List<int> bytes) {
    var crc = 0xffffffff;
    for (final byte in bytes) {
      crc ^= byte;
      for (var bit = 0; bit < 8; bit++) {
        crc = (crc >>> 1) ^ ((crc & 1) == 0 ? 0 : 0xedb88320);
      }
    }
    return (crc ^ 0xffffffff) & 0xffffffff;
  }

  Uint8List chunk(String kind, List<int> bytes) {
    final data = Uint8List.fromList([...ascii.encode(kind), ...bytes]);
    final result = Uint8List(bytes.length + 12);
    ByteData.sublistView(result).setUint32(0, bytes.length);
    result.setRange(4, 4 + data.length, data);
    ByteData.sublistView(result).setUint32(result.length - 4, crc32(data));
    return result;
  }

  const width = 5000, height = 1000;
  final header = ByteData(13)
    ..setUint32(0, width)
    ..setUint32(4, height)
    ..setUint8(8, 1); // One-bit grayscale, no palette or ancillary metadata.
  final scanlines = Uint8List((1 + (width + 7) ~/ 8) * height);
  return (BytesBuilder(copy: false)
        ..add([137, 80, 78, 71, 13, 10, 26, 10])
        ..add(chunk('IHDR', header.buffer.asUint8List()))
        ..add(chunk('IDAT', ZLibEncoder().convert(scanlines)))
        ..add(chunk('IEND', [])))
      .takeBytes();
}

class _PdfCache {
  final Directory folder;
  final String? previous, previousPdfiumModule;
  _PdfCache(this.folder, this.previous, this.previousPdfiumModule);

  static Future<_PdfCache> create() async {
    // Flutter 3.47 emits native_assets.json; pdfium_dart 0.4's test loader
    // still probes the old YAML path on Linux/macOS. Use the real build asset.
    final module = Platform.isLinux
        ? File('build/native_assets/linux/libpdfium.so').absolute
        : Platform.isMacOS
        ? File('build/native_assets/macos/libpdfium.dylib').absolute
        : null;
    if (module != null) {
      expect(
        await module.exists(),
        isTrue,
        reason:
            'The native PDF tests require the actual Flutter-built PDFium library: ${module.path}',
      );
    }
    final folder = await Directory.systemTemp.createTemp(
      'smartplan-mail-preview-test-',
    );
    final cache = _PdfCache(
      folder,
      pdf.Pdfrx.cacheDirectoryPath,
      pdf.Pdfrx.pdfiumModulePath,
    );
    pdf.Pdfrx.cacheDirectoryPath = folder.path;
    if (module != null) pdf.Pdfrx.pdfiumModulePath = module.path;
    return cache;
  }

  Future<void> expectEmpty() async {
    expect(
      await folder.list().toList(),
      isEmpty,
      reason: 'The PDF source and rendered pages must not be cached as files.',
    );
  }

  Future<void> close() async {
    pdf.Pdfrx.cacheDirectoryPath = previous;
    pdf.Pdfrx.pdfiumModulePath = previousPdfiumModule;
    await folder.delete(recursive: true);
  }
}

class _PreviewApi extends AttachmentApi {
  @override
  final Uint8List payload;
  _PreviewApi(this.payload);

  static Future<_PreviewApi> create({
    String mediaType = 'image/png',
    Uint8List? data,
  }) async {
    final api = _PreviewApi(data ?? Uint8List.fromList(_png));
    await api.prepare();
    api.file['media_type'] = mediaType;
    api.file['filename'] = switch (mediaType) {
      'image/png' => 'Synthetischer Grundriss.png',
      'application/pdf' => 'Synthetischer Plan mit zwei Seiten.pdf',
      _ => 'Synthetischer Anhang.bin',
    };
    return api;
  }

  void expireSession() {
    token = null;
    notifyListeners();
  }
}

const _previewKey = ValueKey('mail-attachment-preview-$attachment');
const _downloadKey = ValueKey('mail-attachment-download-$attachment');

Future<void> until(WidgetTester tester, bool Function() condition) async {
  // Real codec/FFI work runs outside Flutter's simulated animation clock.
  for (var attempt = 0; attempt < 1000; attempt++) {
    await tester.runAsync(
      () => Future<void>.delayed(const Duration(milliseconds: 5)),
    );
    await tester.pump(const Duration(milliseconds: 20));
    if (condition()) return;
  }
  fail('Synthetic attachment preview did not finish its native operation.');
}

Future<void> _mount(
  WidgetTester tester,
  _PreviewApi api, {
  ValueNotifier<bool>? access,
  ValueNotifier<Map<String, dynamic>>? manifest,
  MailAttachmentExporter? exporter,
}) async {
  tester.view.physicalSize = const Size(390, 840);
  tester.view.devicePixelRatio = 1;
  addTearDown(tester.view.resetPhysicalSize);
  addTearDown(tester.view.resetDevicePixelRatio);
  Widget card(Map<String, dynamic> current) => Scaffold(
    body: SingleChildScrollView(
      child: MailAttachmentsCard(
        api: api,
        inquiryId: inquiry,
        attachments: current,
        accessAllowed: access,
        exporter: exporter,
      ),
    ),
  );
  await tester.pumpWidget(
    MaterialApp(
      home: manifest == null
          ? card(api.manifest)
          : ValueListenableBuilder<Map<String, dynamic>>(
              valueListenable: manifest,
              builder: (_, current, _) => card(current),
            ),
    ),
  );
  await tester.pumpAndSettle();
}

Future<MailAttachmentPreviewController> _openImage(WidgetTester tester) async {
  await tester.tap(find.byKey(_previewKey));
  await until(
    tester,
    () => find.byType(MailAttachmentPreviewPage).evaluate().isNotEmpty,
  );
  await until(
    tester,
    () => find
        .byType(RawImage)
        .evaluate()
        .any((element) => (element.widget as RawImage).image != null),
  );
  await tester.pumpAndSettle();
  return tester
      .widget<MailAttachmentPreviewPage>(find.byType(MailAttachmentPreviewPage))
      .controller;
}

RawImage _displayedImage(WidgetTester tester) => tester.widget<RawImage>(
  find.byWidgetPredicate(
    (widget) => widget is RawImage && widget.image != null,
  ),
);

Future<void> _dispose(WidgetTester tester, _PreviewApi api) async {
  try {
    await tester.pumpWidget(const SizedBox());
    await tester.pumpAndSettle();
  } finally {
    api.dispose();
  }
}

Future<void> _closePdf(
  WidgetTester tester,
  _PreviewApi api,
  _PdfCache cache,
) async {
  try {
    await _dispose(tester, api);
  } finally {
    await tester.runAsync(cache.close);
  }
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  testWidgets(
    'A verified PNG opens the real zoomable image; closing releases bytes and decoded image',
    (tester) async {
      final api = (await tester.runAsync(_PreviewApi.create))!;
      try {
        await _mount(tester, api);
        final controller = await _openImage(tester);
        final image = _displayedImage(tester).image!;
        expect(controller.document!.bytes, orderedEquals(_png));
        expect(image.width, 40);
        expect(image.height, 30);
        expect(image.debugDisposed, isFalse);
        final zoom = tester.widget<InteractiveViewer>(
          find.byType(InteractiveViewer),
        );
        expect(zoom.panEnabled, isTrue);
        expect(zoom.scaleEnabled, isTrue);
        expect(zoom.maxScale, greaterThan(zoom.minScale));
        expect(
          api.calls.where((path) => path.endsWith('/content')),
          hasLength(1),
        );
        expect(tester.takeException(), isNull);

        await tester.tap(find.byType(CloseButton));
        await tester.pumpAndSettle();
        expect(find.byType(MailAttachmentPreviewPage), findsNothing);
        expect(controller.document, isNull);
        expect(image.debugDisposed, isTrue);
        expect(
          _png.take(8),
          orderedEquals([137, 80, 78, 71, 13, 10, 26, 10]),
          reason:
              'Closing a preview must not mutate the canonical test source.',
        );
      } finally {
        await _dispose(tester, api);
      }
    },
  );

  testWidgets(
    'A real 5000 by 1000 PNG is decoded to a bounded 2048 by 410 image',
    (tester) async {
      final api = (await tester.runAsync(
        () => _PreviewApi.create(data: _widePng()),
      ))!;
      try {
        await _mount(tester, api);
        final controller = await _openImage(tester);
        final image = _displayedImage(tester).image!;
        expect(image.width, 2048);
        expect(image.height, 410);
        expect(controller.document!.bytes, orderedEquals(api.payload));
        expect(tester.takeException(), isNull);
        await tester.tap(find.byType(CloseButton));
        await tester.pumpAndSettle();
        expect(controller.document, isNull);
        expect(image.debugDisposed, isTrue);
      } finally {
        await _dispose(tester, api);
      }
    },
  );

  testWidgets(
    'Preview remains closed until download completes and rejects changed size or SHA',
    (tester) async {
      for (final corrupt in ['size', 'sha256']) {
        final api = (await tester.runAsync(_PreviewApi.create))!
          ..downloadGate = Completer<Uint8List>();
        api.file[corrupt] = corrupt == 'size'
            ? api.payload.length + 1
            : '0' * 64;
        try {
          await _mount(tester, api);
          await tester.tap(find.byKey(_previewKey));
          await tester.pump();
          expect(find.byType(MailAttachmentPreviewPage), findsNothing);
          api.downloadGate!.complete(Uint8List.fromList(api.payload));
          await until(
            tester,
            () => find.byType(LinearProgressIndicator).evaluate().isEmpty,
          );
          await tester.pumpAndSettle();
          expect(find.byType(MailAttachmentPreviewPage), findsNothing);
          expect(find.byType(RawImage), findsNothing);
          expect(
            find.byKey(const ValueKey('mail-attachment-pdf-view')),
            findsNothing,
          );
          expect(
            api.calls.where((path) => path.endsWith('/content')),
            hasLength(1),
          );
          expect(
            find.descendant(
              of: find.byType(MailAttachmentsCard),
              matching: find.textContaining(
                corrupt == 'size'
                    ? 'Die Dateigröße stimmt nicht'
                    : 'Die Datei konnte nicht geprüft werden',
              ),
            ),
            findsOneWidget,
          );
          expect(tester.takeException(), isNull);
        } finally {
          await _dispose(tester, api);
        }
      }
    },
  );

  testWidgets(
    'Unauthorized download and a late successful response after logout never expose a preview',
    (tester) async {
      for (final unauthorized in [true, false]) {
        final api = (await tester.runAsync(_PreviewApi.create))!;
        if (unauthorized) {
          api.downloadError = 401;
        } else {
          api.downloadGate = Completer<Uint8List>();
        }
        try {
          await _mount(tester, api);
          await tester.tap(find.byKey(_previewKey));
          await tester.pump();
          if (!unauthorized) {
            // No notification: the asynchronous completion must recheck the token.
            api.token = null;
            api.downloadGate!.complete(Uint8List.fromList(api.payload));
          }
          await until(
            tester,
            () => find.byType(LinearProgressIndicator).evaluate().isEmpty,
          );
          await tester.pumpAndSettle();
          expect(find.byType(MailAttachmentPreviewPage), findsNothing);
          expect(find.text('Synthetischer Grundriss.png'), findsNothing);
          expect(
            find.textContaining('Zugriff nicht mehr verfügbar'),
            findsOneWidget,
          );
          expect(tester.takeException(), isNull);
        } finally {
          await _dispose(tester, api);
        }
      }
    },
  );

  testWidgets(
    'Logout or explicit access revocation hides an open preview and releases the decoded image',
    (tester) async {
      for (final revokeThroughNotifier in [false, true]) {
        final api = (await tester.runAsync(_PreviewApi.create))!;
        final access = ValueNotifier(true);
        try {
          await _mount(tester, api, access: access);
          final controller = await _openImage(tester);
          final image = _displayedImage(tester).image!;
          if (revokeThroughNotifier) {
            access.value = false;
          } else {
            api.expireSession();
          }
          await tester.pumpAndSettle();
          expect(find.byType(RawImage), findsNothing);
          expect(controller.document, isNull);
          expect(image.debugDisposed, isTrue);
          expect(find.textContaining('nicht mehr verfügbar'), findsWidgets);
          expect(tester.takeException(), isNull);
        } finally {
          await _dispose(tester, api);
          access.dispose();
        }
      }
    },
  );

  testWidgets(
    'Removing the file from refreshed metadata revokes its already open preview',
    (tester) async {
      final api = (await tester.runAsync(_PreviewApi.create))!;
      final manifest = ValueNotifier(api.manifest);
      try {
        await _mount(tester, api, manifest: manifest);
        final controller = await _openImage(tester);
        final image = _displayedImage(tester).image!;
        manifest.value = {
          ...api.manifest,
          'files': <dynamic>[],
          'ready_count': 0,
          'deleted_count': 1,
        };
        await tester.pumpAndSettle();
        expect(find.byType(RawImage), findsNothing);
        expect(controller.document, isNull);
        expect(image.debugDisposed, isTrue);
        expect(tester.takeException(), isNull);
      } finally {
        await _dispose(tester, api);
        manifest.dispose();
      }
    },
  );

  testWidgets(
    'A real two-page PDF renders bounded pages in memory, switches pages and releases its images',
    (tester) async {
      final api = (await tester.runAsync(
        () => _PreviewApi.create(
          mediaType: 'application/pdf',
          data: _twoPagePdf(),
        ),
      ))!;
      final cache = (await tester.runAsync(_PdfCache.create))!;
      try {
        await _mount(tester, api);
        final controller = await _openImage(tester);
        final first = _displayedImage(tester).image!;
        expect(controller.document!.bytes, orderedEquals(api.payload));
        expect(
          find.byKey(const ValueKey('mail-attachment-pdf-view')),
          findsOneWidget,
        );
        expect(find.text('Seite 1 von 2'), findsOneWidget);
        expect(first.width, lessThanOrEqualTo(2048));
        expect(first.height, lessThanOrEqualTo(2048));
        final firstPixels = (await tester.runAsync(
          () => first.toByteData(format: ui.ImageByteFormat.rawRgba),
        ))!;
        final firstGray = firstPixels.getUint8(0);
        expect(firstGray, inInclusiveRange(195, 210));
        final previous = find.byKey(
          const ValueKey('mail-preview-previous-page'),
        );
        final next = find.byKey(const ValueKey('mail-preview-next-page'));
        expect(tester.widget<IconButton>(previous).onPressed, isNull);
        expect(tester.widget<IconButton>(next).onPressed, isNotNull);

        await tester.tap(next);
        await until(
          tester,
          () => find.byType(RawImage).evaluate().any((element) {
            final image = (element.widget as RawImage).image;
            return image != null && !identical(image, first);
          }),
        );
        await tester.pumpAndSettle();
        final second = _displayedImage(tester).image!;
        expect(find.text('Seite 2 von 2'), findsOneWidget);
        expect(first.debugDisposed, isTrue);
        expect(second.width, lessThanOrEqualTo(2048));
        expect(second.height, lessThanOrEqualTo(2048));
        final secondPixels = (await tester.runAsync(
          () => second.toByteData(format: ui.ImageByteFormat.rawRgba),
        ))!;
        expect(secondPixels.getUint8(0), inInclusiveRange(95, 110));
        expect(secondPixels.getUint8(0), lessThan(firstGray));
        expect(tester.widget<IconButton>(previous).onPressed, isNotNull);
        expect(tester.widget<IconButton>(next).onPressed, isNull);

        await tester.tap(previous);
        await until(
          tester,
          () => find.byType(RawImage).evaluate().any((element) {
            final image = (element.widget as RawImage).image;
            return image != null && !identical(image, second);
          }),
        );
        await tester.pumpAndSettle();
        final returned = _displayedImage(tester).image!;
        expect(find.text('Seite 1 von 2'), findsOneWidget);
        expect(second.debugDisposed, isTrue);
        expect(
          api.calls.where((path) => path.endsWith('/content')),
          hasLength(1),
        );
        await tester.runAsync(cache.expectEmpty);
        expect(find.byIcon(Icons.print), findsNothing);
        expect(find.byIcon(Icons.share), findsNothing);
        expect(tester.takeException(), isNull);
        await tester.tap(find.byType(CloseButton));
        await tester.pumpAndSettle();
        expect(controller.document, isNull);
        expect(returned.debugDisposed, isTrue);
      } finally {
        await _closePdf(tester, api, cache);
      }
    },
    tags: 'native_pdf',
  );

  testWidgets(
    'An enormous valid PDF MediaBox still renders only a bounded native bitmap',
    (tester) async {
      final api = (await tester.runAsync(
        () => _PreviewApi.create(
          mediaType: 'application/pdf',
          data: _twoPagePdf(width: 10000000, height: 12000000),
        ),
      ))!;
      final cache = (await tester.runAsync(_PdfCache.create))!;
      try {
        await _mount(tester, api);
        final controller = await _openImage(tester);
        final image = _displayedImage(tester).image!;
        expect(find.text('Seite 1 von 2'), findsOneWidget);
        expect(image.width, inInclusiveRange(1, 2048));
        expect(image.height, inInclusiveRange(1, 2048));
        expect(image.width * image.height, lessThanOrEqualTo(2048 * 2048));
        expect(controller.document!.bytes, orderedEquals(api.payload));
        await tester.runAsync(cache.expectEmpty);
        expect(tester.takeException(), isNull);
        await tester.tap(find.byType(CloseButton));
        await tester.pumpAndSettle();
        expect(controller.document, isNull);
        expect(image.debugDisposed, isTrue);
      } finally {
        await _closePdf(tester, api, cache);
      }
    },
    tags: 'native_pdf',
  );

  testWidgets(
    'A damaged PDF with correct SHA offers an explicit fallback and verified save',
    (tester) async {
      final api = (await tester.runAsync(
        () => _PreviewApi.create(
          mediaType: 'application/pdf',
          data: Uint8List.fromList(
            ascii.encode('%PDF-1.7\ninvalid synthetic document\n'),
          ),
        ),
      ))!;
      final cache = (await tester.runAsync(_PdfCache.create))!;
      var exports = 0;
      try {
        await _mount(
          tester,
          api,
          exporter: (_, document, mayExport) async {
            expect(mayExport(), isTrue);
            expect(document.bytes, orderedEquals(api.payload));
            exports++;
            return MailAttachmentExportResult.cancelled;
          },
        );
        await tester.tap(find.byKey(_previewKey));
        await until(
          tester,
          () => find
              .textContaining(
                'Diese PDF-Seite kann auf dem Gerät nicht angezeigt werden',
              )
              .evaluate()
              .isNotEmpty,
        );
        await tester.pumpAndSettle();
        expect(find.byType(RawImage), findsNothing);
        expect(
          find.textContaining('Das Original bleibt erhalten'),
          findsOneWidget,
        );
        await tester.tap(find.byKey(const ValueKey('mail-preview-export')));
        await until(tester, () => exports == 1);
        await tester.pumpAndSettle();
        expect(
          api.calls.where((path) => path.endsWith('/content')),
          hasLength(1),
        );
        await tester.runAsync(cache.expectEmpty);
        expect(tester.takeException(), isNull);
      } finally {
        await _closePdf(tester, api, cache);
      }
    },
    tags: 'native_pdf',
  );

  testWidgets(
    'Unsupported formats show a safe fallback with verified download, without a native save dialog',
    (tester) async {
      final api = (await tester.runAsync(
        () => _PreviewApi.create(
          mediaType: 'application/octet-stream',
          data: Uint8List.fromList(utf8.encode('Synthetischer Dateianhang')),
        ),
      ))!;
      var exports = 0;
      try {
        await _mount(
          tester,
          api,
          exporter: (_, document, mayExport) async {
            expect(mayExport(), isTrue);
            expect(document.bytes, orderedEquals(api.payload));
            expect(document.mediaType, 'application/octet-stream');
            exports++;
            return MailAttachmentExportResult.cancelled;
          },
        );
        await tester.tap(find.byKey(_downloadKey));
        await until(tester, () => exports == 1);
        await tester.pumpAndSettle();
        await tester.tap(find.byKey(_previewKey));
        await until(
          tester,
          () => find.byType(MailAttachmentPreviewPage).evaluate().isNotEmpty,
        );
        await tester.pumpAndSettle();
        expect(
          find.textContaining('keine Vorschau in der App verfügbar'),
          findsOneWidget,
        );
        expect(find.byType(RawImage), findsNothing);
        expect(
          find.byKey(const ValueKey('mail-attachment-pdf-view')),
          findsNothing,
        );
        await tester.tap(find.byKey(const ValueKey('mail-preview-export')));
        await until(tester, () => exports == 2);
        await tester.pumpAndSettle();
        expect(
          api.calls.where((path) => path.endsWith('/content')),
          hasLength(2),
          reason:
              'Export from the open fallback must reuse its verified bytes.',
        );
        expect(tester.takeException(), isNull);
      } finally {
        await _dispose(tester, api);
      }
    },
  );
}

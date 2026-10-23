import 'dart:async';
import 'dart:convert';
import 'dart:io';
import 'dart:typed_data';
import 'dart:ui' as ui;

import 'package:cryptography/cryptography.dart';
import 'package:file_selector/file_selector.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart' show PlatformException;
import 'package:flutter_test/flutter_test.dart';
import 'package:smartplan_office/api.dart';
import 'package:smartplan_office/offline_plans.dart';
import 'package:smartplan_office/offline_vault.dart';
import 'package:smartplan_office/plan_import_page.dart';

import 'offline_plans_test.dart' show PlanServer, TestDevice, idle;

// A real 40x30 PNG containing a synthetic black rectangle on white paper.
final _png = base64Decode(
  'iVBORw0KGgoAAAANSUhEUgAAACgAAAAeCAIAAADRv8uKAAAAUklEQVR4nGP8//8/w0AApgGxddRiegIWND4jIyMVTceTcgeNjyGA8jxGMORGXuIatXjU4lGLRy0etXjU4sFnMfaGAHUbQFjBgPmYcbQnMewtBgCfvQw+z8BVfQAAAABJRU5ErkJggg==',
);

Uint8List _oneBitPng(int width, int height) {
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

  Uint8List chunk(String kind, List<int> data) {
    final content = Uint8List.fromList([...ascii.encode(kind), ...data]);
    final output = Uint8List(data.length + 12);
    ByteData.sublistView(output).setUint32(0, data.length);
    output.setRange(4, 4 + content.length, content);
    ByteData.sublistView(output).setUint32(output.length - 4, crc32(content));
    return output;
  }

  final header = ByteData(13)
    ..setUint32(0, width)
    ..setUint32(4, height)
    ..setUint8(
      8,
      1,
    ); // One-bit grayscale, with standard PNG compression/filter.
  final scanlines = Uint8List((1 + (width + 7) ~/ 8) * height);
  return (BytesBuilder(copy: false)
        ..add([137, 80, 78, 71, 13, 10, 26, 10])
        ..add(chunk('IHDR', header.buffer.asUint8List()))
        ..add(chunk('IDAT', ZLibEncoder().convert(scanlines)))
        ..add(chunk('IEND', [])))
      .takeBytes();
}

Uint8List _pdf({int pages = 50}) {
  final objects = [
    '<< /Type /Catalog /Pages 2 0 R >>',
    '<< /Type /Pages /Count $pages /Kids [${List.generate(pages, (i) => '${i + 3} 0 R').join(' ')}] >>',
    for (var i = 0; i < pages; i++)
      '<< /Type /Page /Parent 2 0 R /MediaBox [0 0 400 300] >>',
  ];
  final buffer = StringBuffer('%PDF-1.4\n');
  final offsets = <int>[0];
  for (var i = 0; i < objects.length; i++) {
    offsets.add(buffer.length);
    buffer.write('${i + 1} 0 obj\n${objects[i]}\nendobj\n');
  }
  final xref = buffer.length;
  buffer.write('xref\n0 ${objects.length + 1}\n0000000000 65535 f \n');
  for (final offset in offsets.skip(1)) {
    buffer.write('${offset.toString().padLeft(10, '0')} 00000 n \n');
  }
  buffer.write(
    'trailer\n<< /Size ${objects.length + 1} /Root 1 0 R >>\nstartxref\n$xref\n%%EOF\n',
  );
  return Uint8List.fromList(ascii.encode(buffer.toString()));
}

const _ocrText = '</script><script>alert("synthetic OCR")</script>';

Map<String, dynamic> _candidates() => {
  'schema_version': 1,
  'status': 'needs_review',
  'preview': {'width': 40, 'height': 30},
  'analysis': {
    'line_candidates': [
      {
        'start': [.1, .25],
        'end': [.9, .25],
      },
    ],
    'text_candidates': [
      {
        'text': _ocrText,
        'bbox': [.2, .4, .4, .8],
      },
    ],
  },
  'pdf_text': [
    {
      'text': 'PDF reference 4.20 m',
      'bbox': [.6, .4, .8, .8],
    },
  ],
};

Future<Uint8List> _paintCandidates(
  Map<String, dynamic> result, {
  bool lines = true,
  bool textBoxes = true,
}) async {
  final recorder = ui.PictureRecorder();
  final canvas = Canvas(recorder)..drawColor(Colors.white, BlendMode.src);
  PlanImportCandidatesPainter(
    result,
    lines: lines,
    textBoxes: textBoxes,
  ).paint(canvas, const Size(200, 100));
  final picture = recorder.endRecording();
  final image = await picture.toImage(200, 100);
  try {
    final data = await image.toByteData(format: ui.ImageByteFormat.rawRgba);
    return Uint8List.fromList(
      data!.buffer.asUint8List(data.offsetInBytes, data.lengthInBytes),
    );
  } finally {
    image.dispose();
    picture.dispose();
  }
}

List<int> _pixel(Uint8List rgba, int x, int y) =>
    rgba.sublist((y * 200 + x) * 4, (y * 200 + x + 1) * 4);

/// This transport returns synthetic server output, while repository validation,
/// hash binding, encrypted caches and widget cache-arrival listeners stay real.
class _ImportServer extends PlanServer {
  @override
  String get version => 'v1';
}

class _ReviewServer extends _ImportServer {
  late Map<String, dynamic> remote;
  late Uint8List recognitionBytes;
  final previewStarted = Completer<void>();
  final releasePreview = Completer<void>();

  Future<void> prepare(Map<String, dynamic> record) async {
    final result = _candidates()
      ..['source'] = {
        'sha256': record['sha256'],
        'selected_page': record['page'],
      };
    recognitionBytes = Uint8List.fromList(utf8.encode(jsonEncode(result)));
    Future<String> hash(Uint8List bytes) async =>
        (await Sha256().hash(bytes)).bytes
            .map((byte) => byte.toRadixString(16).padLeft(2, '0'))
            .join();
    remote = {
      for (final key in [
        'project_id',
        'filename',
        'title',
        'sha256',
        'size',
        'media_type',
        'page',
      ])
        key: record[key],
      'id': record['local_id'],
      'status': 'needs_review',
      'uploaded_chunks': <int>[],
      'preview_sha256': await hash(_png),
      'preview_size': _png.length,
      'result_sha256': await hash(recognitionBytes),
    };
  }

  @override
  Future<dynamic> call(String path, [Map<String, dynamic>? body]) async {
    if (online && path.contains('/plan-imports')) {
      return path.endsWith('/plan-imports') && body == null ? [remote] : remote;
    }
    return super.call(path, body);
  }

  @override
  Future<Uint8List> bytes(
    String path, {
    required String mediaType,
    int maxBytes = maxPlanImportBytes,
  }) async {
    if (!online) throw const ApiException(0, 'Synthetic offline transport');
    if (path.endsWith('/preview')) {
      expect(mediaType, 'image/png');
      expect(maxBytes, _png.length);
      if (!previewStarted.isCompleted) previewStarted.complete();
      await releasePreview.future;
      return Uint8List.fromList(_png);
    }
    if (path.endsWith('/result')) {
      expect(mediaType, 'application/json');
      return Uint8List.fromList(recognitionBytes);
    }
    throw StateError('Unexpected synthetic download: $path');
  }
}

/// A provider can report a false length. The reader must bound its actual stream.
class _ProviderFile extends XFile {
  final int declared;
  final Stream<Uint8List> Function() stream;
  int opened = 0;
  _ProviderFile(this.declared, this.stream) : super('/provider/untrusted.pdf');

  @override
  Future<int> length() async => declared;

  @override
  Stream<Uint8List> openRead([int? start, int? end]) {
    opened++;
    return stream();
  }
}

/// Only metadata is held in memory to control a durable-commit boundary. Source
/// encryption and decryption use the actual EncryptedAssets filesystem code.
class _CommitVault extends OfflineVault {
  Map<String, dynamic>? value;
  Completer<void>? release;
  Completer<void>? started;
  bool failNext = false;

  _CommitVault(super.directory, super.key);

  void pauseNextCommit() {
    release = Completer<void>();
    started = Completer<void>();
  }

  @override
  Future<Map<String, dynamic>?> read() async =>
      value == null ? null : offlineCopy(value!);

  @override
  Future<void> write(Map<String, dynamic> data) async {
    final gate = release;
    if (gate != null && !started!.isCompleted) {
      started!.complete();
      await gate.future;
      release = null;
    }
    if (failNext) {
      failNext = false;
      throw const FileSystemException('Synthetic full metadata disk');
    }
    value = offlineCopy(data);
  }
}

class _ImportDevice extends TestDevice {
  final _CommitVault vault;
  _ImportDevice(this.vault) : super(vault.directory);

  @override
  Future<OfflineVault> open(
    String server,
    String user, {
    bool create = false,
  }) async => vault;
}

class _Fixture {
  final Directory folder;
  final _CommitVault vault;
  final PlanServer server;
  final OfflinePlans repository;
  DateTime now = DateTime.utc(2026, 10, 23);
  static const project = {'id': 'project', 'name': 'Synthetic site'};

  _Fixture(this.folder, this.vault, this.server, this.repository);

  static Future<_Fixture> create({PlanServer? suppliedServer}) async {
    final folder = await Directory.systemTemp.createTemp(
      'smartplan-import-ui-',
    );
    final vault = _CommitVault(
      Directory('${folder.path}/account'),
      SecretKey(List<int>.generate(32, (i) => i)),
    );
    final server = (suppliedServer ?? _ImportServer())
      ..token = 'synthetic-session';
    late _Fixture fixture;
    final repository = OfflinePlans(
      api: server,
      transport: server,
      device: _ImportDevice(vault),
      clock: () => fixture.now,
    );
    fixture = _Fixture(folder, vault, server, repository);
    await repository.login({'id': 'a' * 32, 'role': 'owner'}, [project]);
    await idle(repository);
    server.online = false;
    return fixture;
  }

  Future<File> file(String name, Uint8List bytes) =>
      File.fromUri(folder.uri.resolve(name)).writeAsBytes(bytes, flush: true);

  Future<void> dispose() async {
    final gate = vault.release;
    if (gate != null && !gate.isCompleted) gate.complete();
    await repository.flush();
    await idle(repository);
    repository.dispose();
    server.dispose();
    await folder.delete(recursive: true);
  }
}

Future<void> _pumpUntil(
  WidgetTester tester,
  bool Function() done, {
  String reason = 'The asynchronous import did not complete',
}) async {
  for (var attempt = 0; attempt < 300; attempt++) {
    await tester.runAsync(
      () => Future<void>.delayed(const Duration(milliseconds: 5)),
    );
    await tester.pump(const Duration(milliseconds: 20));
    if (done()) return;
  }
  fail(reason);
}

Future<void> _mount(
  WidgetTester tester,
  _Fixture fixture, {
  PlanImportPicker? pickFile,
  PlanImportPicker? takePhoto,
  bool cameraAvailable = false,
}) => tester.pumpWidget(
  MaterialApp(
    home: PlanImportPage(
      repository: fixture.repository,
      project: _Fixture.project,
      canWrite: true,
      pickFile: pickFile,
      takePhoto: takePhoto,
      cameraAvailable: cameraAvailable,
    ),
  ),
);

Future<void> _close(WidgetTester tester, _Fixture fixture) async {
  // Removing a page cancels publication, but its already-started file read must
  // still close its handle before Windows can remove the fixture directory.
  if (find.byType(PlanImportDetailPage).evaluate().isNotEmpty) {
    await _pumpUntil(
      tester,
      () => find.byType(LinearProgressIndicator).evaluate().isEmpty,
      reason: 'The detail page did not finish reading its encrypted fixture',
    );
  }
  await tester.pumpWidget(const SizedBox());
  await tester.runAsync(fixture.dispose);
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  test('Candidate painter maps normalized lines and OCR/PDF boxes onto real canvas pixels', () async {
    final rgba = await _paintCandidates(_candidates());
    final line = _pixel(rgba, 100, 25);
    expect(line[1], greaterThan(line[0] + 20));
    expect(line[1], greaterThan(line[2] + 5));
    for (final x in [40, 120]) {
      final boxEdge = _pixel(rgba, x, 60);
      expect(boxEdge[0], greaterThan(boxEdge[1] + 20));
      expect(boxEdge[1], greaterThan(boxEdge[2] + 20));
    }
    for (final point in [
      const Offset(10, 25),
      const Offset(60, 60),
      const Offset(100, 90),
    ]) {
      expect(_pixel(rgba, point.dx.toInt(), point.dy.toInt()), [
        255,
        255,
        255,
        255,
      ]);
    }
    final hidden = await _paintCandidates(
      _candidates(),
      lines: false,
      textBoxes: false,
    );
    expect(hidden.every((value) => value == 255), isTrue);
  });

  test(
    'Candidate painter ignores malformed, non-finite and out-of-range geometry',
    () async {
      final result = {
        'analysis': {
          'line_candidates': [
            null,
            'not a line',
            {
              'start': [double.nan, .1],
              'end': [.5, .5],
            },
            {
              'start': [-.1, .1],
              'end': [.5, .5],
            },
            {
              'start': [.1],
              'end': [.5, .5],
            },
            {
              'start': [true, .1],
              'end': [.5, .5],
            },
            {
              'start': [.1, .1],
              'end': [1.1, .5],
            },
          ],
          'text_candidates': [
            for (final box in [
              [double.nan, .1, .5, .5],
              [0, .1, double.infinity, .5],
              [0, .1, 1.1, .5],
              [.8, .1, .5, .5],
              [0, .8, .5, .5],
              [false, .1, .5, .5],
              ['0', .1, .5, .5],
              [0, 1],
            ])
              {'text': 'Untrusted candidate', 'bbox': box},
          ],
        },
        'pdf_text': [
          {
            'text': _ocrText,
            'bbox': [0, 0, .5, double.negativeInfinity],
          },
        ],
      };
      final rgba = await _paintCandidates(result);
      expect(rgba.every((value) => value == 255), isTrue);
    },
  );

  test('Candidate text mapping preserves literal OCR and distinguishes embedded PDF text', () {
    final words = planImportTexts(_candidates());
    expect(words.map((word) => word['text']), [
      _ocrText,
      'PDF reference 4.20 m',
    ]);
    expect(words.map((word) => word['origin']), ['Drucktext-OCR', 'PDF-Text']);
  });

  test(
    'Reader sniffs actual PNG/PDF bytes despite suffix and provider MIME',
    () async {
      final png = await readPlanImportFile(
        XFile.fromData(
          _png,
          path: 'misleading.dwg',
          mimeType: 'application/pdf',
        ),
      );
      expect(png.mediaType, 'image/png');
      expect(png.bytes, orderedEquals(_png));
      final pdf = _pdf();
      final source = await readPlanImportFile(
        XFile.fromData(pdf, path: 'misleading.jpg', mimeType: 'image/jpeg'),
      );
      expect(source.mediaType, 'application/pdf');
      expect(source.bytes, orderedEquals(pdf));
    },
  );

  test(
    'Reader rejects oversized declared length before opening provider stream',
    () async {
      for (final declared in [0, maxPlanImportBytes + 1]) {
        final file = _ProviderFile(declared, () => Stream.value(_png));
        await expectLater(
          readPlanImportFile(file),
          throwsA(isA<ApiException>().having((e) => e.status, 'status', 413)),
        );
        expect(file.opened, 0);
      }
    },
  );

  test(
    'Reader bounds actual stream and cancels even when provider length lies',
    () async {
      var cancelled = false;
      var consumedTail = false;
      Stream<Uint8List> oversized() async* {
        try {
          for (var i = 0; i < 20; i++) {
            yield Uint8List(1024 * 1024);
          }
          yield Uint8List(1);
          consumedTail = true;
          throw StateError(
            'The rejected provider stream must never reach its tail',
          );
        } finally {
          cancelled = true;
        }
      }

      final file = _ProviderFile(1, oversized);
      await expectLater(
        readPlanImportFile(file),
        throwsA(isA<ApiException>().having((e) => e.status, 'status', 413)),
      );
      expect(file.opened, 1);
      expect(cancelled, isTrue);
      expect(consumedTail, isFalse);
    },
  );

  test('Reader accepts exactly 20 MiB and rejects mismatched actual length', () async {
    // The reader sniffs PDF; full PDF parsing remains the bounded worker's job.
    final bytes = Uint8List(maxPlanImportBytes)
      ..setRange(0, 5, ascii.encode('%PDF-'));
    final accepted = await readPlanImportFile(XFile.fromData(bytes));
    expect(accepted.bytes.length, maxPlanImportBytes);
    expect(accepted.mediaType, 'application/pdf');
    final incomplete = _ProviderFile(_png.length + 1, () => Stream.value(_png));
    await expectLater(
      readPlanImportFile(incomplete),
      throwsA(isA<ApiException>().having((e) => e.status, 'status', 400)),
    );
  });

  test('Reader rejects unsupported and corrupted picture contents', () async {
    for (final bytes in [
      Uint8List.fromList(ascii.encode('AC1032 synthetic DWG')),
      Uint8List.fromList([137, 80, 78, 71, 13, 10, 26, 10, 0]),
    ]) {
      await expectLater(
        readPlanImportFile(
          XFile.fromData(bytes, path: 'looks-like-a-plan.png'),
        ),
        throwsA(isA<ApiException>()),
      );
    }
  });

  test('Reader rejects a real compressed 45 MP PNG before allocating an RGBA bitmap', () async {
    final oversized = _oneBitPng(9000, 5000);
    expect(oversized.length, lessThan(20000));
    await expectLater(
      readPlanImportFile(XFile.fromData(oversized, path: 'large-plan.png')),
      throwsA(
        isA<ApiException>()
            .having((error) => error.status, 'status', 413)
            .having(
              (error) => error.message,
              'message',
              contains('40 Millionen'),
            ),
      ),
    );
  });

  testWidgets(
    'File import shows saved state only after encrypted source and metadata commit',
    (tester) async {
      final fixture = (await tester.runAsync(_Fixture.create))!;
      try {
        final original = (await tester.runAsync(
          () => fixture.file('source.dwg', _png),
        ))!;
        var selected = 0;
        await _mount(
          tester,
          fixture,
          pickFile: () async {
            selected++;
            return PlanImportFile(
              XFile(original.path, mimeType: 'application/pdf'),
            );
          },
        );
        fixture.vault.pauseNextCommit();
        await tester.tap(find.text('Datei importieren'));
        await _pumpUntil(tester, () => fixture.vault.started!.isCompleted);
        expect(selected, 1);
        expect(fixture.repository.imports('project'), isEmpty);
        expect(find.byType(PlanImportDetailPage), findsNothing);
        expect(
          find.text('Lokal gespeichert · wartet auf Verbindung'),
          findsNothing,
        );
        final encrypted = await tester.runAsync(
          () => fixture.folder
              .list(recursive: true)
              .where((file) => file.path.endsWith('original.enc'))
              .cast<File>()
              .single,
        );
        expect(encrypted, isNotNull);
        final encryptedBytes = await tester.runAsync(encrypted!.readAsBytes);
        expect(encryptedBytes, isNot(orderedEquals(_png)));
        fixture.vault.release!.complete();
        await _pumpUntil(
          tester,
          () => find
              .text('Lokal gespeichert · wartet auf Verbindung')
              .evaluate()
              .isNotEmpty,
        );
        final record = fixture.repository.imports('project').single;
        expect(record['filename'], 'source.dwg');
        expect(record['media_type'], 'image/png');
        final roundtrip = await tester.runAsync(
          () => fixture.repository.importSource(record['local_id']),
        );
        expect(roundtrip, orderedEquals(_png));
        expect(
          await tester.runAsync(original.exists),
          isTrue,
          reason: 'A user-selected file must remain untouched',
        );
      } finally {
        await _close(tester, fixture);
      }
    },
  );

  testWidgets(
    'Camera temp remains through a failed commit and is removed after successful retry',
    (tester) async {
      final fixture = (await tester.runAsync(_Fixture.create))!;
      try {
        final temporary = (await tester.runAsync(
          () => fixture.file('camera.jpg', _png),
        ))!;
        var captured = 0;
        await _mount(
          tester,
          fixture,
          cameraAvailable: true,
          takePhoto: () async {
            captured++;
            return PlanImportFile(XFile(temporary.path), temporary: true);
          },
        );
        fixture.vault.failNext = true;
        await tester.tap(find.text('Plan fotografieren'));
        await _pumpUntil(
          tester,
          () => find.text('Erneut speichern').evaluate().isNotEmpty,
        );
        expect(captured, 1);
        expect(fixture.repository.imports('project'), isEmpty);
        expect(find.byType(PlanImportDetailPage), findsNothing);
        expect(
          find.textContaining('Noch nicht lokal gespeichert.'),
          findsOneWidget,
        );
        expect(
          find.text('Lokal gespeichert · wartet auf Verbindung'),
          findsNothing,
        );
        expect(await tester.runAsync(temporary.exists), isTrue);

        fixture.vault.pauseNextCommit();
        await tester.ensureVisible(find.text('Erneut speichern'));
        await tester.tap(find.text('Erneut speichern'));
        await _pumpUntil(tester, () => fixture.vault.started!.isCompleted);
        expect(await tester.runAsync(temporary.exists), isTrue);
        expect(fixture.repository.imports('project'), isEmpty);
        fixture.vault.release!.complete();
        await _pumpUntil(
          tester,
          () => find
              .text('Lokal gespeichert · wartet auf Verbindung')
              .evaluate()
              .isNotEmpty,
        );
        expect(await tester.runAsync(temporary.exists), isFalse);
        expect(
          captured,
          1,
          reason:
              'Retry must use the retained source, not launch the camera again',
        );
        final record = fixture.repository.imports('project').single;
        expect(
          await tester.runAsync(
            () => fixture.repository.importSource(record['local_id']),
          ),
          orderedEquals(_png),
        );
      } finally {
        await _close(tester, fixture);
      }
    },
  );

  for (final page in [1, 50]) {
    testWidgets(
      'PDF page $page is validated and committed as zero-based ${page - 1}',
      (tester) async {
        final fixture = (await tester.runAsync(_Fixture.create))!;
        try {
          await _mount(
            tester,
            fixture,
            pickFile: () async =>
                PlanImportFile(XFile.fromData(_pdf(), path: 'storey.pdf')),
          );
          await tester.tap(find.text('Datei importieren'));
          await _pumpUntil(
            tester,
            () => find.text('PDF-Seite auswählen').evaluate().isNotEmpty,
          );
          if (page == 50) {
            for (final invalid in ['0', '51', '-1', 'floor']) {
              await tester.enterText(find.byType(TextFormField), invalid);
              await tester.tap(find.text('Quelle speichern'));
              await tester.pump();
              expect(
                find.text('Eine Seitenzahl von 1 bis 50 eingeben.'),
                findsOneWidget,
              );
              expect(fixture.repository.imports('project'), isEmpty);
            }
          }
          await tester.enterText(find.byType(TextFormField), '$page');
          await tester.tap(find.text('Quelle speichern'));
          await _pumpUntil(
            tester,
            () => find
                .text('Lokal gespeichert · wartet auf Verbindung')
                .evaluate()
                .isNotEmpty,
          );
          expect(
            fixture.repository.imports('project').single['page'],
            page - 1,
          );
          expect(find.text('storey.pdf · Seite $page'), findsOneWidget);
        } finally {
          await _close(tester, fixture);
        }
      },
    );
  }

  testWidgets(
    'Expired offline permission hides an already opened source and keeps encrypted original',
    (tester) async {
      final fixture = (await tester.runAsync(_Fixture.create))!;
      try {
        final record = (await tester.runAsync(
          () => fixture.repository.captureImport(
            'project',
            _png,
            filename: 'private-plan.png',
            mediaType: 'image/png',
            title: 'Private floor',
          ),
        ))!;
        await tester.pumpWidget(
          MaterialApp(
            home: PlanImportDetailPage(
              repository: fixture.repository,
              project: _Fixture.project,
              localId: record['local_id'],
            ),
          ),
        );
        await _pumpUntil(
          tester,
          () => find.byType(Image).evaluate().isNotEmpty,
        );
        expect(find.text('Private floor'), findsOneWidget);
        fixture.now = fixture.now.add(const Duration(days: 7));
        fixture.repository.changed();
        await tester.pump();
        expect(find.byType(Image), findsNothing);
        expect(find.text('Private floor'), findsNothing);
        expect(
          find.textContaining('Offline-Freigabe abgelaufen'),
          findsOneWidget,
        );
        expect(
          () => fixture.repository.getImport(record['local_id']),
          throwsA(isA<ApiException>()),
        );
        final originals = await tester.runAsync(
          () => fixture.folder
              .list(recursive: true)
              .where((file) => file.path.endsWith('original.enc'))
              .toList(),
        );
        expect(originals, hasLength(1));
      } finally {
        await _close(tester, fixture);
      }
    },
  );

  testWidgets(
    'Camera permission denial keeps file import available without a saved claim',
    (tester) async {
      final fixture = (await tester.runAsync(_Fixture.create))!;
      try {
        await _mount(
          tester,
          fixture,
          cameraAvailable: true,
          takePhoto: () async {
            throw PlatformException(code: 'camera_access_denied');
          },
        );
        await tester.tap(find.text('Plan fotografieren'));
        await tester.pumpAndSettle();
        expect(
          find.textContaining('Die Kamera ist nicht freigegeben.'),
          findsOneWidget,
        );
        expect(find.text('Datei importieren'), findsOneWidget);
        expect(find.byType(PlanImportDetailPage), findsNothing);
        expect(fixture.repository.imports('project'), isEmpty);
      } finally {
        await _close(tester, fixture);
      }
    },
  );

  testWidgets(
    'Late encrypted server PNG and recognition refresh an open PDF review, including landscape',
    (tester) async {
      final server = _ReviewServer();
      final fixture = (await tester.runAsync(
        () => _Fixture.create(suppliedServer: server),
      ))!;
      final initialSize = tester.view.physicalSize;
      final initialRatio = tester.view.devicePixelRatio;
      Future<void>? refresh;
      var refreshFinished = false;
      Object? refreshError;
      try {
        final record = (await tester.runAsync(
          () => fixture.repository.captureImport(
            'project',
            _pdf(),
            filename: 'review-source.pdf',
            mediaType: 'application/pdf',
            title: 'Review floor',
            page: 49,
          ),
        ))!;
        await tester.runAsync(() => idle(fixture.repository));
        await tester.runAsync(() => server.prepare(record));
        await tester.pumpWidget(
          MaterialApp(
            home: PlanImportDetailPage(
              repository: fixture.repository,
              project: _Fixture.project,
              localId: record['local_id'],
            ),
          ),
        );
        await _pumpUntil(
          tester,
          () => find
              .textContaining('PDF-Original lokal gespeichert.')
              .evaluate()
              .isNotEmpty,
        );
        expect(find.byType(Image), findsNothing);
        expect(find.text('Servervorschau'), findsNothing);
        expect(find.text('review-source.pdf · Seite 50'), findsOneWidget);

        await tester.runAsync(() async {
          server.online = true;
          refresh = fixture.repository
              .refreshImports('project')
              .then<void>(
                (_) {
                  refreshFinished = true;
                },
                onError: (Object error, StackTrace _) {
                  refreshError = error;
                  refreshFinished = true;
                },
              );
        });
        await _pumpUntil(
          tester,
          () => server.previewStarted.isCompleted || refreshFinished,
          reason: 'Synthetic preview download did not start',
        );
        expect(refreshError, isNull);
        expect(server.previewStarted.isCompleted, isTrue);
        await _pumpUntil(
          tester,
          () => find.text('Ergebnis zur Prüfung bereit').evaluate().isNotEmpty,
        );
        expect(
          fixture.repository.getImport(record['local_id'])['status'],
          'needs_review',
        );
        expect(
          fixture.repository.getImport(record['local_id'])['preview'],
          isNull,
        );
        expect(
          find.text('Servervorschau'),
          findsNothing,
          reason: 'A ready status alone must not label an uncached source as a server preview',
        );

        server.releasePreview.complete();
        await _pumpUntil(
          tester,
          () => refreshFinished,
          reason: 'Encrypted preview and recognition cache did not finish',
        );
        expect(refreshError, isNull);
        final overlay = find.byWidgetPredicate(
          (widget) =>
              widget is CustomPaint &&
              widget.foregroundPainter is PlanImportCandidatesPainter,
        );
        try {
          await _pumpUntil(tester, () => overlay.evaluate().isNotEmpty);
        } catch (_) {
          fail(
            'Candidate overlay missing after cache arrival. '
            'Cached fields: ${fixture.repository.getImport(record["local_id"]).keys.toList()}. '
            'Visible text: ${tester.widgetList<Text>(find.byType(Text)).map((text) => text.data).join(" | ")}',
          );
        }
        expect(find.text('Servervorschau'), findsOneWidget);
        expect(find.text('Linienvorschläge'), findsOneWidget);
        expect(find.text('Textstellen'), findsOneWidget);
        final cached = fixture.repository.getImport(record['local_id']);
        expect(cached['preview'], isA<Map>());
        expect(cached['recognition'], isA<Map>());
        expect(
          await tester.runAsync(
            () => fixture.repository.importPreview(record['local_id']),
          ),
          orderedEquals(_png),
        );
        final recognition = await tester.runAsync(
          () => fixture.repository.importRecognition(record['local_id']),
        );
        expect(
          recognition!['analysis']['text_candidates'][0]['text'],
          _ocrText,
        );

        await tester.ensureVisible(find.text('2 erkannte Textstellen'));
        await tester.tap(find.text('2 erkannte Textstellen'));
        await tester.pumpAndSettle();
        expect(find.text(_ocrText), findsOneWidget);
        expect(find.text('Drucktext-OCR'), findsOneWidget);
        expect(find.text('PDF-Text'), findsOneWidget);
        final text = tester.widget<Text>(find.text(_ocrText));
        expect(
          text.data,
          _ocrText,
          reason: 'OCR contents must remain a plain Flutter Text value',
        );

        tester.view.devicePixelRatio = 1;
        tester.view.physicalSize = const Size(800, 320);
        await tester.pump();
        expect(
          tester.takeException(),
          isNull,
          reason: 'Expanded review must fit a small landscape viewport without overflow',
        );
        expect(find.byType(PlanImportDetailPage), findsOneWidget);

        final files = (await tester.runAsync(
          () => fixture.folder
              .list(recursive: true)
              .where((file) => file.path.endsWith('original.enc'))
              .toList(),
        ))!;
        expect(
          files,
          hasLength(3),
          reason: 'Source PDF, server PNG and recognition JSON must all use real encrypted files',
        );
      } finally {
        if (!server.releasePreview.isCompleted)
          server.releasePreview.complete();
        if (refresh != null) {
          await _pumpUntil(tester, () => refreshFinished);
          await tester.runAsync(() => refresh!);
        }
        tester.view.physicalSize = initialSize;
        tester.view.devicePixelRatio = initialRatio;
        await _close(tester, fixture);
      }
    },
  );
}

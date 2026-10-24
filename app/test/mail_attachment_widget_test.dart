import 'dart:async';
import 'dart:convert';
import 'dart:typed_data';

import 'package:cryptography/cryptography.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:smartplan_office/api.dart';
import 'package:smartplan_office/mail_attachment_widgets.dart';

const inquiry = '11111111111111111111111111111111';
const project = '33333333333333333333333333333333';
const attachment = '55555555555555555555555555555555';

Uint8List syntheticPdf() {
  final objects = [
    '<< /Type /Catalog /Pages 2 0 R >>',
    '<< /Type /Pages /Count 1 /Kids [3 0 R] >>',
    '<< /Type /Page /Parent 2 0 R /MediaBox [0 0 100 100] >>',
  ];
  final result = StringBuffer('%PDF-1.4\n');
  final offsets = <int>[];
  for (var index = 0; index < objects.length; index++) {
    offsets.add(result.length);
    result.write('${index + 1} 0 obj\n${objects[index]}\nendobj\n');
  }
  final xref = result.length;
  result.write('xref\n0 4\n0000000000 65535 f \n');
  for (final offset in offsets)
    result.write('${offset.toString().padLeft(10, '0')} 00000 n \n');
  result.write('trailer\n<< /Size 4 /Root 1 0 R >>\nstartxref\n$xref\n%%EOF\n');
  return Uint8List.fromList(ascii.encode(result.toString()));
}

class AttachmentApi extends OfficeApi {
  AttachmentApi({String version = 'v1'}) : super(apiVersion: version) {
    token = 'synthetic-session';
  }
  final payload = syntheticPdf();
  late Map<String, dynamic> file;
  late Map<String, dynamic> manifest;
  final calls = <String>[];
  final copies = <Map<String, dynamic>>[];
  final receipts = <String, Map<String, dynamic>>{};
  final deletedPlanRequests = <String>{};
  Completer<Uint8List>? downloadGate;
  Completer<void>? deleteGate;
  Completer<void>? inquiryGetGate;
  bool loseCopyAck = false, unsupported = false, projectAllowed = true;
  int? downloadError, deleteError;

  Future<void> prepare() async {
    final sha = (await Sha256().hash(payload)).bytes
        .map((value) => value.toRadixString(16).padLeft(2, '0'))
        .join();
    file = {
      'id': attachment,
      'inquiry_id': inquiry,
      'filename': 'Synthetischer Plan.pdf',
      'media_type': 'application/pdf',
      'size': payload.length,
      'sha256': sha,
      'status': 'ready',
      'subject': 'Synthetischer Auftrag',
    };
    manifest = {
      'status': 'complete',
      'expected_count': 1,
      'ready_count': 1,
      'deleted_count': 0,
      'total_bytes': payload.length,
      'files': [file],
    };
  }

  @override
  Future<dynamic> call(String path, [Map<String, dynamic>? body]) async {
    calls.add(path);
    if (path == '/api/projects')
      return projectAllowed
          ? [
              {'id': project},
            ]
          : [];
    if (path == '/api/inquiries/$inquiry') {
      final reply = jsonDecode(jsonEncode({'attachments': manifest}));
      final gate = inquiryGetGate;
      inquiryGetGate = null;
      if (gate != null) await gate.future;
      return reply;
    }
    if (path == '/api/projects/$project/mail-attachments') {
      if (unsupported) throw const ApiException(404, 'Not available');
      return {
        'files': manifest['files'],
        'pending_count': 0,
        'unannounced_count': 0,
      };
    }
    if (path.endsWith('/delete')) {
      if (deleteGate != null) await deleteGate!.future;
      if (deleteError != null)
        throw ApiException(deleteError!, 'Synthetic deletion failure');
      manifest = {
        ...manifest,
        'files': <dynamic>[],
        'ready_count': 0,
        'deleted_count': 1,
      };
      return {'ok': true};
    }
    if (path.endsWith('/plan-import')) {
      final frozen = Map<String, dynamic>.from(body!);
      copies.add(frozen);
      final id = frozen['request_id'] as String;
      if (deletedPlanRequests.contains(id))
        throw const ApiException(410, 'Plan was removed');
      final result = receipts.putIfAbsent(
        id,
        () => {
          'id': '77777777777777777777777777777777',
          'project_id': project,
          'status': 'queued',
        },
      );
      if (loseCopyAck) {
        loseCopyAck = false;
        throw const ApiException(0, 'Synthetic lost acknowledgement');
      }
      return result;
    }
    throw StateError('Unexpected synthetic request: $path');
  }

  @override
  Future<Uint8List> bytes(
    String path, {
    required String mediaType,
    int maxBytes = 20 * 1024 * 1024,
  }) async {
    calls.add(path);
    expect(mediaType, 'application/octet-stream');
    expect(maxBytes, maxMailAttachmentBytes);
    if (downloadError != null)
      throw ApiException(downloadError!, 'Synthetic access failure');
    return downloadGate == null
        ? Uint8List.fromList(payload)
        : await downloadGate!.future;
  }
}

Future<AttachmentApi> apiFixture() async {
  final api = AttachmentApi();
  await api.prepare();
  return api;
}

Future<void> until(WidgetTester tester, bool Function() condition) async {
  for (var attempt = 0; attempt < 200; attempt++) {
    await tester.runAsync(
      () => Future<void>.delayed(const Duration(milliseconds: 3)),
    );
    await tester.pump(const Duration(milliseconds: 20));
    if (condition()) return;
  }
  fail('Synthetic attachment operation did not finish');
}

Future<void> mount(
  WidgetTester tester,
  AttachmentApi api, {
  bool projectScope = false,
  bool remove = false,
  bool import = false,
  bool offline = false,
  Map<String, dynamic>? manifest,
  MailAttachmentExporter? exporter,
  VoidCallback? denied,
  VoidCallback? plans,
}) => tester.pumpWidget(
  MaterialApp(
    home: Scaffold(
      body: SingleChildScrollView(
        child: MailAttachmentsCard(
          api: api,
          inquiryId: projectScope ? null : inquiry,
          projectId: projectScope ? project : null,
          attachments: projectScope ? null : manifest ?? api.manifest,
          canDelete: remove,
          canImportPlan: import,
          offlineMode: offline,
          exporter: exporter,
          onAccessDenied: denied,
          onPlans: plans,
        ),
      ),
    ),
  ),
);

void main() {
  test(
    'Export filename cannot contain path traversal or reserved Windows names',
    () {
      final traversal = safeAttachmentFilename('../../CON.pdf');
      expect(traversal, isNot(contains('/')));
      expect(traversal, isNot(startsWith('.')));
      expect(safeAttachmentFilename('CON.pdf'), 'Datei-CON.pdf');
      expect(safeAttachmentFilename('  .. '), 'mail-anhang');
      expect(safeAttachmentFilename('plan:entwurf?.pdf'), 'plan_entwurf_.pdf');
    },
  );

  testWidgets(
    'Announced upload, unavailable list and intentional deletion have distinct states',
    (tester) async {
      final api = (await tester.runAsync(apiFixture))!;
      var data = {
        ...api.manifest,
        'status': 'not_announced',
        'expected_count': null,
        'files': <dynamic>[],
      };
      await mount(tester, api, manifest: data);
      expect(find.textContaining('noch keine Anhangsliste'), findsOneWidget);
      data = {
        ...api.manifest,
        'status': 'uploading',
        'expected_count': 2,
        'files': [
          {...api.file, 'status': 'uploading'},
        ],
      };
      await mount(tester, api, manifest: data);
      expect(find.textContaining('Übertragung läuft noch'), findsOneWidget);
      expect(
        tester
            .widget<OutlinedButton>(
              find.byKey(
                const ValueKey('mail-attachment-download-$attachment'),
              ),
            )
            .onPressed,
        isNull,
      );
      data = {...api.manifest, 'deleted_count': 1};
      await mount(tester, api, manifest: data);
      expect(find.textContaining('1 entfernt'), findsOneWidget);
      expect(find.textContaining('Übertragung abgeschlossen'), findsOneWidget);
    },
  );

  testWidgets(
    'A ready download verifies exact bytes and hash before invoking export once',
    (tester) async {
      final api = (await tester.runAsync(apiFixture))!;
      final exported = <VerifiedMailAttachment>[];
      await mount(
        tester,
        api,
        exporter: (context, value, allowed) async {
          expect(allowed(), isTrue);
          exported.add(value);
          return MailAttachmentExportResult.saved;
        },
      );
      await tester.tap(
        find.byKey(const ValueKey('mail-attachment-download-$attachment')),
      );
      await until(tester, () => exported.isNotEmpty);
      expect(exported.single.bytes, orderedEquals(api.payload));
      expect(exported.single.sha256, api.file['sha256']);
      expect(exported.single.mediaType, 'application/pdf');
      expect(
        api.calls.where((path) => path.endsWith('/content')),
        hasLength(1),
      );
    },
  );

  for (final mismatch in ['size', 'sha256']) {
    testWidgets('A $mismatch mismatch never reaches file output', (
      tester,
    ) async {
      final api = (await tester.runAsync(apiFixture))!;
      api.file[mismatch] = mismatch == 'size'
          ? api.payload.length + 1
          : '0' * 64;
      var exports = 0;
      await mount(
        tester,
        api,
        exporter: (_, _, _) async {
          exports++;
          return MailAttachmentExportResult.saved;
        },
      );
      await tester.tap(
        find.byKey(const ValueKey('mail-attachment-download-$attachment')),
      );
      await until(
        tester,
        () => find
            .textContaining('Es wurde nichts gespeichert.')
            .evaluate()
            .isNotEmpty,
      );
      expect(exports, 0);
    });
  }

  testWidgets('An oversized announced file is not offered for download', (
    tester,
  ) async {
    final api = (await tester.runAsync(apiFixture))!;
    api.file['size'] = maxMailAttachmentBytes + 1;
    await mount(tester, api);
    expect(
      tester
          .widget<OutlinedButton>(
            find.byKey(const ValueKey('mail-attachment-download-$attachment')),
          )
          .onPressed,
      isNull,
    );
    expect(api.calls, isEmpty);
  });

  testWidgets('A fresh 401 clears filenames and cannot export', (tester) async {
    final api = (await tester.runAsync(apiFixture))!..downloadError = 401;
    var exports = 0, denied = 0;
    await mount(
      tester,
      api,
      denied: () => denied++,
      exporter: (_, _, _) async {
        exports++;
        return MailAttachmentExportResult.saved;
      },
    );
    await tester.tap(
      find.byKey(const ValueKey('mail-attachment-download-$attachment')),
    );
    await tester.pumpAndSettle();
    expect(exports, 0);
    expect(denied, 1);
    expect(find.text('Synthetischer Plan.pdf'), findsNothing);
    expect(find.textContaining('Zugriff nicht mehr verfügbar'), findsOneWidget);
  });

  testWidgets('A successful response arriving after logout is never exported', (
    tester,
  ) async {
    final api = (await tester.runAsync(apiFixture))!
      ..downloadGate = Completer<Uint8List>();
    var exports = 0;
    await mount(
      tester,
      api,
      exporter: (_, _, _) async {
        exports++;
        return MailAttachmentExportResult.saved;
      },
    );
    await tester.tap(
      find.byKey(const ValueKey('mail-attachment-download-$attachment')),
    );
    await tester.pump();
    api.token =
        null; // No notification: the response guard must still reject it.
    api.downloadGate!.complete(api.payload);
    await tester.pumpAndSettle();
    expect(exports, 0);
    expect(find.text('Synthetischer Plan.pdf'), findsNothing);
  });

  testWidgets(
    'The native handoff guard stays live while a user chooses an output',
    (tester) async {
      final api = (await tester.runAsync(apiFixture))!;
      final opened = Completer<void>(), finish = Completer<void>();
      var writes = 0;
      await mount(
        tester,
        api,
        exporter: (_, _, allowed) async {
          opened.complete();
          await finish.future;
          if (allowed()) writes++;
          return MailAttachmentExportResult.cancelled;
        },
      );
      await tester.tap(
        find.byKey(const ValueKey('mail-attachment-download-$attachment')),
      );
      await until(tester, () => opened.isCompleted);
      api.token = null;
      finish.complete();
      await tester.pumpAndSettle();
      expect(writes, 0);
    },
  );

  testWidgets(
    'Owner removal waits for explicit confirmation and server acknowledgement',
    (tester) async {
      final api = (await tester.runAsync(apiFixture))!
        ..deleteGate = Completer<void>();
      await mount(tester, api, remove: true);
      await tester.tap(
        find.byKey(const ValueKey('mail-attachment-remove-$attachment')),
      );
      await tester.pumpAndSettle();
      await tester.tap(find.text('Abbrechen'));
      await tester.pumpAndSettle();
      expect(api.calls.where((path) => path.endsWith('/delete')), isEmpty);
      await tester.tap(
        find.byKey(const ValueKey('mail-attachment-remove-$attachment')),
      );
      await tester.pumpAndSettle();
      await tester.tap(find.widgetWithText(FilledButton, 'Anhang entfernen'));
      await tester.pump();
      expect(find.text('Synthetischer Plan.pdf'), findsOneWidget);
      api.deleteGate!.complete();
      await until(
        tester,
        () => find.text('Synthetischer Plan.pdf').evaluate().isEmpty,
      );
      await tester.pumpAndSettle();
      expect(api.manifest['deleted_count'], 1);
    },
  );

  testWidgets(
    'A metadata response started before deletion cannot restore the removed attachment',
    (tester) async {
      final api = (await tester.runAsync(apiFixture))!
        ..deleteGate = Completer<void>();
      await mount(tester, api, remove: true);
      await tester.tap(
        find.byKey(const ValueKey('mail-attachment-remove-$attachment')),
      );
      await tester.pumpAndSettle();
      await tester.tap(find.widgetWithText(FilledButton, 'Anhang entfernen'));
      await tester.pump();
      expect(
        tester
            .widget<IconButton>(
              find.ancestor(
                of: find.byTooltip('Anhänge aktualisieren'),
                matching: find.byType(IconButton),
              ),
            )
            .onPressed,
        isNull,
      );
      // Exercise a future programmatic/global refresh as well as the disabled
      // header: its old reply must remain invalid after the delete ACK.
      final oldGet = Completer<void>();
      api.inquiryGetGate = oldGet;
      final held =
          (tester.state(find.byType(MailAttachmentsCard)) as dynamic).refresh()
              as Future<void>;
      await tester.pump();
      api.deleteGate!.complete();
      await until(
        tester,
        () => find.text('Synthetischer Plan.pdf').evaluate().isEmpty,
      );
      oldGet.complete();
      await tester.pumpAndSettle();
      await held;
      expect(find.text('Synthetischer Plan.pdf'), findsNothing);
      expect(find.textContaining('1 entfernt'), findsOneWidget);
    },
  );

  testWidgets(
    'Plan copy keeps one UUID, selected page and title across a lost response',
    (tester) async {
      final api = (await tester.runAsync(apiFixture))!..loseCopyAck = true;
      var openedPlans = 0;
      await mount(
        tester,
        api,
        projectScope: true,
        import: true,
        plans: () => openedPlans++,
      );
      await tester.pumpAndSettle();
      await tester.tap(
        find.byKey(const ValueKey('mail-attachment-plan-$attachment')),
      );
      await tester.pumpAndSettle();
      await tester.enterText(
        find.byKey(const ValueKey('mail-plan-page')),
        '50',
      );
      await tester.enterText(
        find.byKey(const ValueKey('mail-plan-title')),
        'Obergeschoss',
      );
      await tester.tap(find.widgetWithText(FilledButton, 'Plan übernehmen'));
      await tester.pumpAndSettle();
      expect(openedPlans, 0);
      expect(
        tester
            .widget<TextField>(
              find.descendant(
                of: find.byKey(const ValueKey('mail-plan-title')),
                matching: find.byType(TextField),
              ),
            )
            .readOnly,
        isTrue,
      );
      await tester.tap(find.widgetWithText(FilledButton, 'Erneut übernehmen'));
      await tester.pumpAndSettle();
      expect(api.copies, hasLength(2));
      expect(api.copies[0], api.copies[1]);
      expect(api.copies.first['page'], 49);
      expect(api.copies.first['title'], 'Obergeschoss');
      expect(
        api.copies.first['request_id'],
        matches(RegExp(r'^[a-f0-9]{32}$')),
      );
      expect(api.receipts, hasLength(1));
      expect(openedPlans, 1);
    },
  );

  testWidgets(
    'A deliberate new copy gets a fresh UUID after the previous plan was removed',
    (tester) async {
      final api = (await tester.runAsync(apiFixture))!;
      var openedPlans = 0;
      await mount(
        tester,
        api,
        projectScope: true,
        import: true,
        plans: () => openedPlans++,
      );
      await tester.pumpAndSettle();
      for (var copy = 0; copy < 2; copy++) {
        await tester.tap(
          find.byKey(const ValueKey('mail-attachment-plan-$attachment')),
        );
        await tester.pumpAndSettle();
        await tester.tap(find.widgetWithText(FilledButton, 'Plan übernehmen'));
        await tester.pumpAndSettle();
        expect(openedPlans, copy + 1);
        if (copy == 0)
          api.deletedPlanRequests.add(
            api.copies.single['request_id'] as String,
          );
      }
      expect(api.copies, hasLength(2));
      expect(
        api.copies.first['request_id'],
        isNot(api.copies.last['request_id']),
      );
      expect(api.copies.first['title'], api.copies.last['title']);
      expect(api.copies.first['page'], api.copies.last['page']);
      expect(api.receipts, hasLength(2));
    },
  );

  testWidgets('Unsupported formats and readers never get a plan-copy button', (
    tester,
  ) async {
    final api = (await tester.runAsync(apiFixture))!;
    api.file['media_type'] = 'application/msword';
    await mount(tester, api, projectScope: true, import: true);
    await tester.pumpAndSettle();
    expect(find.text('Als Plan übernehmen'), findsNothing);
    expect(find.text('Entfernen'), findsNothing);
  });

  testWidgets(
    'Offline project attachments explain online access without fetching anything',
    (tester) async {
      final api = (await tester.runAsync(apiFixture))!;
      await mount(tester, api, projectScope: true, offline: true);
      await tester.pumpAndSettle();
      expect(api.calls, isEmpty);
      expect(find.textContaining('nur mit Online-Anmeldung'), findsOneWidget);
      expect(find.text('Synthetischer Plan.pdf'), findsNothing);
    },
  );

  testWidgets(
    'A valid old-server project gets an update hint rather than invented empty files',
    (tester) async {
      final api = (await tester.runAsync(apiFixture))!..unsupported = true;
      await mount(tester, api, projectScope: true);
      await tester.pumpAndSettle();
      expect(find.textContaining('neue Serverpaket'), findsOneWidget);
      expect(api.calls, contains('/api/projects'));
      expect(find.text('Synthetischer Plan.pdf'), findsNothing);
    },
  );

  testWidgets('Long filenames and actions fit a 390px screen', (tester) async {
    final api = (await tester.runAsync(apiFixture))!;
    api.file['filename'] = '${'Langer synthetischer Planname ' * 5}.pdf';
    tester.view.devicePixelRatio = 1;
    tester.view.physicalSize = const Size(390, 840);
    addTearDown(tester.view.resetDevicePixelRatio);
    addTearDown(tester.view.resetPhysicalSize);
    await mount(tester, api, projectScope: true, import: true, remove: true);
    await tester.pumpAndSettle();
    expect(tester.takeException(), isNull);
    expect(find.text('Als Plan übernehmen').hitTestable(), findsOneWidget);
  });
}

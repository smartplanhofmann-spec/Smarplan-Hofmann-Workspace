import 'dart:convert';

import 'package:cryptography/cryptography.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:smartplan_office/inquiry_pages.dart';
import 'package:smartplan_office/mail_attachment_widgets.dart';
import 'package:smartplan_office/offline_plans.dart';
import 'package:smartplan_office/project_workspace_page.dart';

import 'inquiry_widget_test.dart' show InquiryApi, inquiryId, field, copy;
import 'offline_plans_test.dart' show idle;
import 'project_workspace_widget_test.dart'
    show WorkspaceApi, CacheFixture, section, settleStorage;

const _attachmentId = '55555555555555555555555555555555';
const _filename = 'synthetischer-hausplan.png';

Future<Map<String, dynamic>> _attachment() async {
  // A real PNG from the existing synthetic plan fixture. These integration
  // cases never download or hand its bytes to a native file/share dialog.
  final bytes = base64Decode(
    'iVBORw0KGgoAAAANSUhEUgAAACgAAAAeCAIAAADRv8uKAAAAUklEQVR4nGP8//8/w0AApgGxddRiegIWND4jIyMVTceTcgeNjyGA8jxGMORGXuIatXjU4lGLRy0etXjU4sFnMfaGAHUbQFjBgPmYcbQnMewtBgCfvQw+z8BVfQAAAABJRU5ErkJggg==',
  );
  final digest = (await Sha256().hash(bytes)).bytes
      .map((byte) => byte.toRadixString(16).padLeft(2, '0'))
      .join();
  return {
    'id': _attachmentId,
    'filename': _filename,
    'media_type': 'image/png',
    'size': bytes.length,
    'sha256': digest,
    'status': 'ready',
    'created_at': '2026-10-24T12:00:00Z',
    'updated_at': '2026-10-24T12:00:00Z',
  };
}

class _InquiryAttachmentsApi extends InquiryApi {
  int removed = 0;

  static Future<_InquiryAttachmentsApi> create({
    String source = 'gmail',
    bool withManifest = true,
  }) async {
    final api = _InquiryAttachmentsApi()..token = 'synthetic-session';
    final file = await _attachment();
    final record = api.fixture(source: source);
    if (withManifest) {
      record['attachments'] = {
        'status': 'complete',
        'expected_count': 1,
        'ready_count': 1,
        'deleted_count': 0,
        'total_bytes': file['size'],
        'files': [file],
      };
    }
    api.records[inquiryId] = record;
    return api;
  }

  @override
  Future<dynamic> call(String path, [Map<String, dynamic>? body]) async {
    if (path == '/api/inquiries/$inquiryId/attachments/$_attachmentId/delete') {
      calls.add((path: path, body: body == null ? null : copy(body)));
      expect(body, isEmpty);
      removed++;
      final manifest = records[inquiryId]!['attachments'] as Map;
      manifest['files'] = <dynamic>[];
      manifest['ready_count'] = 0;
      manifest['deleted_count'] = 1;
      return {'deleted': true};
    }
    return super.call(path, body);
  }
}

class _ProjectAttachmentsApi extends WorkspaceApi {
  int attachmentReads = 0;
  int planReads = 0;
  int planCopies = 0;
  late Map<String, dynamic> attachment;

  @override
  String get version => 'v1';

  static Future<_ProjectAttachmentsApi> create() async {
    final api = _ProjectAttachmentsApi()..token = 'synthetic-session';
    api.attachment = {
      ...await _attachment(),
      'inquiry_id': inquiryId,
      'subject': 'Synthetische übernommene Gmail-Anfrage',
    };
    api.items['links']!.add({
      'id': '66666666666666666666666666666666',
      'revision': 1,
      'title': 'Vertrag im Projektordner',
      'category': 'contract',
      'url': 'https://example.test/synthetic-contract',
      'active': true,
    });
    return api;
  }

  @override
  Future<dynamic> call(String path, [Map<String, dynamic>? body]) async {
    if (path == '/api/projects/project-1/plans' && body == null) {
      calls.add((path: path, body: null));
      planReads++;
      return <dynamic>[];
    }
    if (path ==
        '/api/projects/project-1/mail-attachments/$_attachmentId/plan-import') {
      calls.add((path: path, body: body == null ? null : copy(body)));
      expect(body?['request_id'], matches(RegExp(r'^[0-9a-f]{32}$')));
      expect(body?['page'], 0);
      planCopies++;
      return {
        'id': '77777777777777777777777777777777',
        'project_id': 'project-1',
        'status': 'queued',
      };
    }
    if (path == '/api/projects/project-1/mail-attachments') {
      calls.add((path: path, body: body));
      expect(body, isNull);
      attachmentReads++;
      return {
        'files': [copy(attachment)],
        'pending_count': 0,
        'unannounced_count': 0,
      };
    }
    return super.call(path, body);
  }
}

Future<void> _show(
  WidgetTester tester,
  Widget page, {
  Size size = const Size(1100, 1900),
}) async {
  tester.view.physicalSize = size;
  tester.view.devicePixelRatio = 1;
  addTearDown(tester.view.resetPhysicalSize);
  addTearDown(tester.view.resetDevicePixelRatio);
  await tester.pumpWidget(const SizedBox());
  await tester.pumpWidget(MaterialApp(home: page));
  await tester.pumpAndSettle();
}

void main() {
  testWidgets(
    'Gmail attachments precede the mail body; only Gmail without a manifest shows the old-server hint',
    (tester) async {
      final gmail = (await tester.runAsync(_InquiryAttachmentsApi.create))!;
      try {
        await _show(
          tester,
          InquiryDetailPage(api: gmail, role: 'owner', inquiryId: inquiryId),
        );
        expect(find.byType(MailAttachmentsCard), findsOneWidget);
        expect(find.text(_filename), findsOneWidget);
        expect(
          tester.getTopLeft(find.text(_filename)).dy,
          lessThan(
            tester
                .getTopLeft(find.text(gmail.records[inquiryId]!['message']))
                .dy,
          ),
        );
        expect(
          gmail.calls.where((call) => call.path == '/api/inquiries/$inquiryId'),
          hasLength(1),
          reason: 'The existing detail response already contains the manifest.',
        );
      } finally {
        await tester.pumpWidget(const SizedBox());
        gmail.dispose();
      }

      for (final source in ['gmail', 'manual', 'whatsapp']) {
        final api = (await tester.runAsync(
          () => _InquiryAttachmentsApi.create(
            source: source,
            withManifest: false,
          ),
        ))!;
        try {
          await _show(
            tester,
            InquiryDetailPage(api: api, role: 'owner', inquiryId: inquiryId),
            size: const Size(390, 1000),
          );
          expect(
            find.byType(MailAttachmentsCard),
            source == 'gmail' ? findsOneWidget : findsNothing,
          );
          expect(
            find.textContaining(
              'E-Mail-Anhänge benötigen das neue Serverpaket',
            ),
            source == 'gmail' ? findsOneWidget : findsNothing,
          );
          expect(tester.takeException(), isNull);
        } finally {
          await tester.pumpWidget(const SizedBox());
          api.dispose();
        }
      }
    },
  );

  testWidgets(
    'Attachment refresh and confirmed owner deletion preserve an unsaved inquiry note without reviving the file',
    (tester) async {
      final api = (await tester.runAsync(_InquiryAttachmentsApi.create))!;
      try {
        await _show(
          tester,
          InquiryDetailPage(api: api, role: 'owner', inquiryId: inquiryId),
        );
        final next = field('Nächster Schritt / Wiedervorlage');
        await tester.enterText(next, 'Unfertige synthetische Rückrufnotiz');
        await tester.tap(find.byTooltip('Anhänge aktualisieren'));
        await tester.pumpAndSettle();
        expect(
          tester.widget<TextField>(next).controller!.text,
          'Unfertige synthetische Rückrufnotiz',
        );
        expect(find.text(_filename), findsOneWidget);

        final remove = find.byKey(
          const ValueKey('mail-attachment-remove-$_attachmentId'),
        );
        await tester.tap(remove);
        await tester.pumpAndSettle();
        await tester.tap(find.text('Abbrechen'));
        await tester.pumpAndSettle();
        expect(api.removed, 0);
        expect(find.text(_filename), findsOneWidget);

        await tester.tap(remove);
        await tester.pumpAndSettle();
        await tester.tap(find.widgetWithText(FilledButton, 'Anhang entfernen'));
        await tester.pumpAndSettle();
        expect(api.removed, 1);
        expect(find.text(_filename), findsNothing);
        expect(find.textContaining('1 entfernt'), findsOneWidget);
        expect(
          tester.widget<TextField>(next).controller!.text,
          'Unfertige synthetische Rückrufnotiz',
        );

        // A normal parent setState from the workflow editor must not restore
        // the old attachment snapshot after an acknowledged removal.
        await tester.enterText(next, 'Rückruf bleibt weiterhin ungespeichert');
        await tester.pumpAndSettle();
        expect(find.text(_filename), findsNothing);
        expect(api.records[inquiryId]!['next_action'], '');
        expect(
          api.calls.where(
            (call) =>
                call.path == '/api/inquiries/$inquiryId' && call.body != null,
          ),
          isEmpty,
        );
        expect(tester.takeException(), isNull);
      } finally {
        await tester.pumpWidget(const SizedBox());
        api.dispose();
      }
    },
  );

  testWidgets(
    'Project Documents loads linked enquiry files only after selection and keeps existing document links',
    (tester) async {
      final api = (await tester.runAsync(_ProjectAttachmentsApi.create))!;
      try {
        await _show(
          tester,
          ProjectWorkspacePage(
            api: api,
            project: WorkspaceApi.project,
            role: 'owner',
            reportsBuilder: (_) => const Text('Synthetischer Berichtsbereich'),
          ),
        );
        expect(api.attachmentReads, 0);
        expect(find.byType(MailAttachmentsCard), findsNothing);
        await section(tester, 'Dokumente');
        expect(api.attachmentReads, 1);
        expect(find.text(_filename), findsOneWidget);
        expect(
          find.text('Aus Anfrage: Synthetische übernommene Gmail-Anfrage'),
          findsOneWidget,
        );
        expect(find.text('Vertrag im Projektordner'), findsOneWidget);
        expect(find.text('Link öffnen'), findsOneWidget);
        expect(find.text('Als Plan übernehmen'), findsOneWidget);
        expect(
          api.calls.where((call) => call.body != null),
          isEmpty,
          reason: 'Listing an existing converted mail must not copy or import files.',
        );
        expect(tester.takeException(), isNull);
      } finally {
        await tester.pumpWidget(const SizedBox());
        api.dispose();
      }
    },
  );

  testWidgets(
    'Copying an attachment reopens and reloads an already visited Plans register',
    (tester) async {
      final api = (await tester.runAsync(_ProjectAttachmentsApi.create))!;
      try {
        await _show(
          tester,
          ProjectWorkspacePage(
            api: api,
            project: WorkspaceApi.project,
            role: 'owner',
            reportsBuilder: (_) => const Text('Synthetischer Berichtsbereich'),
          ),
        );
        await section(tester, 'Pläne');
        expect(api.planReads, 1);
        expect(find.text('Importierte Pläne'), findsOneWidget);

        await section(tester, 'Dokumente');
        await tester.tap(find.text('Als Plan übernehmen'));
        await tester.pumpAndSettle();
        expect(find.text('Anhang als Plan übernehmen'), findsOneWidget);
        await tester.tap(find.widgetWithText(FilledButton, 'Plan übernehmen'));
        await tester.pumpAndSettle();

        expect(api.planCopies, 1);
        expect(
          api.planReads,
          2,
          reason: 'An earlier Plans visit must not retain a stale list.',
        );
        expect(find.text('Importierte Pläne'), findsOneWidget);
        expect(find.text('Anhang als Plan übernehmen'), findsNothing);
        expect(tester.takeException(), isNull);
      } finally {
        await tester.pumpWidget(const SizedBox());
        api.dispose();
      }
    },
  );

  testWidgets(
    'Offline Documents shows the attachment online hint without requests while cached links remain usable',
    (tester) async {
      final fixture = (await tester.runAsync(CacheFixture.create))!;
      try {
        await tester.runAsync(() async {
          await fixture.repository.saveWorkspaceItem('project-1', 'links', {
            'title': 'Lokaler Dropbox-Verweis',
            'category': 'dropbox',
            'url': 'https://example.test/synthetic-folder',
            'active': true,
          });
          await idle(fixture.repository);
        });
        final requestsBefore = fixture.api.networkCalls;
        await _show(
          tester,
          ProjectWorkspacePage(
            api: fixture.api,
            project: WorkspaceApi.project,
            role: 'owner',
            repository: fixture.repository,
            offlineMode: true,
            reportsBuilder: (_) => const Text('Synthetischer Berichtsbereich'),
          ),
        );
        await section(tester, 'Dokumente');
        expect(
          find.textContaining(
            'E-Mail-Anhänge sind nur mit Online-Anmeldung verfügbar',
          ),
          findsOneWidget,
        );
        expect(find.text('Lokaler Dropbox-Verweis'), findsOneWidget);
        expect(
          tester
              .widget<TextButton>(
                find.widgetWithText(TextButton, 'Link öffnen'),
              )
              .onPressed,
          isNotNull,
          reason: 'An offline attachment hint must not disable existing document links.',
        );
        expect(fixture.api.networkCalls, requestsBefore);
        expect(
          fixture.api.calls.where(
            (call) => call.path.contains('mail-attachments'),
          ),
          isEmpty,
        );
        expect(tester.takeException(), isNull);
      } finally {
        await settleStorage(tester, () => !fixture.repository.syncing);
        await tester.pumpWidget(const SizedBox());
        await tester.runAsync(fixture.close);
      }
    },
  );
}

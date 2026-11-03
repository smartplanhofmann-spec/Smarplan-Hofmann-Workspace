import 'dart:async';
import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:smartplan_office/api.dart';
import 'package:smartplan_office/business_customer_workspace.dart';
import 'package:smartplan_office/business_session.dart';
import 'package:smartplan_office/design.dart';
import 'package:smartplan_office/mail_attachment_preview.dart';

const projectId = 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa';
const customerId = 'bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb';
const grantId = 'cccccccccccccccccccccccccccccccc';
const sourceId = 'eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee';
const uploadId = 'ffffffffffffffffffffffffffffffff';
Map<String, dynamic> copy(Map<String, dynamic> value) =>
    jsonDecode(jsonEncode(value)) as Map<String, dynamic>;

class WorkspaceApi extends OfficeApi {
  WorkspaceApi()
    : super(apiVersion: 'v1', baseUrl: 'https://office.example.test') {
    token = 'synthetic-customer-workspace-session';
  }
  bool readonly = false, documentsEnabled = true, loseCreate = false;
  bool loseRevoke = false;
  bool inbox = false, mismatchAcceptance = false;
  String? originalFailure;
  Map<String, dynamic>? acceptance;
  final contentCalls = <String>[];
  Completer<void>? creationReply;
  Set<String> permissions = {
    'portal.manage',
    'documents.read',
    'documents.write',
    'documents.classify',
  };
  final calls = <({String path, Map<String, dynamic>? body})>[];
  final grants = <Map<String, dynamic>>[];
  final requests = <String, Map<String, dynamic>>{};
  final results = <String, Map<String, dynamic>>{};
  String get invitation =>
      'https://office.example.test/office/customer-workspace.html#grant=$grantId&key=SPCI_${'s' * 43}';

  Map<String, dynamic> grant() => {
    'id': grantId,
    'recipient_name': 'Synthetische Kundin',
    'recipient_email': 'customer@example.test',
    'allow_upload': true,
    'status': 'active',
    'created_at': '2026-11-03T10:00:00Z',
    'expires_at': '2026-11-10T10:00:00Z',
  };

  Map<String, dynamic> metadata() => {
    'filename': 'Original.png',
    'media_type': 'image/png',
    'size': originalFailure == 'size' ? 4 : 3,
    'sha256': originalFailure == 'sha'
        ? '0' * 64
        : '039058c6f2c0cb492c533b0a4d14ef77cc0f78abccced5287d84a1a2011cfb81',
  };

  @override
  Future<Uint8List> bytes(
    String path, {
    required String mediaType,
    int maxBytes = 20 * 1024 * 1024,
  }) async {
    expect(
      path,
      '/api/business/customer-workspace/sources/media/$sourceId/content?project_id=$projectId',
    );
    expect(mediaType, 'image/png');
    contentCalls.add(path);
    return Uint8List.fromList([1, 2, 3]);
  }

  @override
  Future<dynamic> call(String path, [Map<String, dynamic>? body]) async {
    calls.add((path: path, body: body == null ? null : copy(body)));
    final uri = Uri.parse(path), route = uri.path;
    if (route == '/api/business/capabilities') {
      expect(uri.queryParameters['project_id'], projectId);
      return {
        'storage_version': 7,
        'compatibility_mode': readonly ? 'legacy' : 'business',
        'readonly': readonly,
        'generation': 1,
        'capabilities': ['business_customer_workspace', 'business_documents'],
        'features': ['customer_workspace_portal', 'organization_modules'],
        'permissions': permissions.toList(),
        'organization': {
          'revision': 1,
          'configured': true,
          'modules': {
            for (final key in BusinessSession.organizationSections)
              key: {
                'visible': true,
                'enabled': key == 'documents' ? documentsEnabled : true,
              },
          },
        },
      };
    }
    if (route == '/api/business/customer-workspace' && body == null) {
      expect(uri.queryParameters['project_id'], projectId);
      if (!permissions.contains('portal.manage') ||
          !permissions.contains('documents.read')) {
        throw const ApiException(403, 'Projektzugriff entzogen');
      }
      return {
        'project': {
          'id': projectId,
          'customer_id': customerId,
          'name': 'Synthetisches Projekt',
          'customer': 'Synthetische Kundin',
        },
        'publication': {
          'id': 'd' * 32,
          'revision': 1,
          'title': 'Freigegebene vertrauliche Projektinformation',
          'description': 'Nur für das gebundene Kundenprojekt.',
          'status_label': 'Freigegeben',
          'start_date': null,
          'end_date': null,
          'published_at': '2026-11-03T10:00:00Z',
        },
        'grants': grants.map(copy).toList(),
        'files': <dynamic>[],
        'uploads': [
          if (inbox)
            {
              ...metadata(),
              'id': uploadId,
              'grant_id': grantId,
              'project_id': projectId,
              'customer_id': customerId,
              'note': 'Synthetischer Eingang zur Prüfung',
              'status': acceptance == null ? 'received' : 'accepted',
              'created_at': '2026-11-03T10:00:00Z',
              'acceptance': acceptance,
            },
        ],
        'source_files': [
          if (originalFailure != null)
            {
              ...metadata(),
              'source_kind': 'media',
              'source_id': sourceId,
              'title': 'Original zur Prüfung',
            },
        ],
        'writes_allowed': !readonly && documentsEnabled,
        'can_accept': !readonly && documentsEnabled,
      };
    }
    if (body == null) throw StateError('Unexpected GET $path');
    expect(permissions, contains('portal.manage'));
    expect(permissions, contains('documents.read'));
    final request = '${body['request_id']}';
    expect(request, matches(RegExp(r'^[a-f0-9]{32}$')));
    if (requests.containsKey(request)) {
      expect(body, requests[request]);
      return copy(results[request]!);
    }
    if (route == '/api/business/customer-workspace/grants') {
      expect(body['project_id'], projectId);
      expect(body['customer_id'], customerId);
      expect(body['confirmation'], isTrue);
      expect(grants, isEmpty);
      grants.add(grant());
      requests[request] = copy(body);
      results[request] = {
        'grant': copy(grants.single),
        'link_available': false,
      };
      await creationReply?.future;
      if (loseCreate) {
        loseCreate = false;
        throw const ApiException(0, 'Synthetisch verlorene Erfolgsantwort');
      }
      return {
        'grant': copy(grants.single),
        'link_available': true,
        'portal_url': invitation,
      };
    }
    if (route == '/api/business/customer-workspace/grants/$grantId/revoke') {
      expect(body['reason'], 'Synthetischer Widerrufsgrund');
      grants.single['status'] = 'revoked';
      requests[request] = copy(body);
      results[request] = copy(grants.single);
      if (loseRevoke) {
        loseRevoke = false;
        throw const ApiException(0, 'Synthetisch verlorener Widerruf');
      }
      return copy(grants.single);
    }
    if (route == '/api/business/customer-workspace/uploads/$uploadId/accept') {
      expect(body['confirmation'], isTrue);
      expect(body['classification'], 'restricted');
      acceptance = {
        'upload_id': uploadId,
        'media_id': sourceId,
        'classification': body['classification'],
        'accepted_at': '2026-11-03T11:00:00Z',
      };
      requests[request] = copy(body);
      results[request] = copy(acceptance!);
      if (mismatchAcceptance) {
        mismatchAcceptance = false;
        return {...acceptance!, 'classification': 'operational'};
      }
      return copy(acceptance!);
    }
    throw StateError('Unexpected POST $path');
  }
}

Finder field(String name) => find.byKey(ValueKey('business-field-$name'));

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  setUpAll(() async {
    await (FontLoader(
      'Inter',
    )..addFont(rootBundle.load('assets/fonts/Inter.ttf'))).load();
  });
  Future<BusinessSession> show(
    WidgetTester tester,
    WorkspaceApi api, {
    double width = 1200,
  }) async {
    tester.view.physicalSize = Size(width, 1100);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    final session = BusinessSession(
      api: api,
      projectId: projectId,
      projects: [
        {'id': projectId, 'name': 'Synthetisches Projekt'},
      ],
    );
    await session.load();
    await tester.pumpWidget(
      MaterialApp(
        theme: officeTheme(),
        home: Scaffold(body: BusinessCustomerWorkspacePage(session: session)),
      ),
    );
    await tester.pumpAndSettle();
    return session;
  }

  Future<void> close(
    WidgetTester tester,
    BusinessSession session,
    WorkspaceApi api,
  ) async {
    await tester.pumpWidget(const SizedBox());
    session.dispose();
    api.dispose();
  }

  Future<void> tap(WidgetTester tester, Finder finder) async {
    await tester.ensureVisible(finder);
    await tester.pumpAndSettle();
    await tester.tap(finder);
    await tester.pumpAndSettle();
  }

  Future<void> create(WidgetTester tester, {bool complete = true}) async {
    await tap(
      tester,
      find.widgetWithText(FilledButton, 'Kundenzugang erstellen'),
    );
    for (final entry in {
      'recipient_name': 'Synthetische Kundin',
      'recipient_email': 'customer@example.test',
      'expires_in_days': '7',
    }.entries) {
      await tester.ensureVisible(field(entry.key));
      await tester.enterText(field(entry.key), entry.value);
    }
    await tap(tester, find.text('Inhalt, Empfänger und Umfang sind geprüft'));
    if (complete) {
      await tap(tester, find.widgetWithText(FilledButton, 'Speichern'));
    } else {
      await tester.tap(find.widgetWithText(FilledButton, 'Speichern'));
      await tester.pump();
    }
  }

  testWidgets(
    'lost grant receipt repeats the exact project command without redisclosing an invitation',
    (tester) async {
      final api = WorkspaceApi()..loseCreate = true;
      final session = await show(tester, api);
      try {
        await create(tester);
        final first = api.calls.lastWhere((call) => call.body != null).body!;
        expect(api.grants, hasLength(1));
        expect(
          find.textContaining('Synthetisch verlorene Erfolgsantwort'),
          findsOneWidget,
        );
        await tap(tester, find.text('Schließen'));
        await tap(
          tester,
          find.widgetWithText(FilledButton, 'Kundenzugang erstellen'),
        );
        expect(
          tester.widget<TextFormField>(field('recipient_email')).enabled,
          isFalse,
        );
        await tap(tester, find.widgetWithText(FilledButton, 'Erneut senden'));
        expect(api.calls.lastWhere((call) => call.body != null).body, first);
        expect(api.grants, hasLength(1));
        expect(find.text('Einmaliger Zugangslink'), findsNothing);
        expect(
          find.textContaining('Link wird nicht erneut ausgegeben'),
          findsOneWidget,
        );
        expect(session.pending('customer-grant-$projectId'), isFalse);
        expect(
          api.calls.any(
            (call) =>
                call.body != null && jsonEncode(call.body).contains('SPCI_'),
          ),
          isFalse,
        );
        expect(tester.takeException(), isNull);
      } finally {
        await close(tester, session, api);
      }
    },
  );

  testWidgets(
    'current document permission loss clears invitation and published project content',
    (tester) async {
      final api = WorkspaceApi();
      final session = await show(tester, api, width: 390);
      try {
        await create(tester);
        expect(find.text('Einmaliger Zugangslink'), findsOneWidget);
        expect(find.text(api.invitation), findsOneWidget);
        expect(
          find.text('Freigegebene vertrauliche Projektinformation'),
          findsOneWidget,
        );
        api.permissions.remove('documents.read');
        await session.load();
        await tester.pumpAndSettle();
        expect(find.text(api.invitation), findsNothing);
        expect(
          find.text('Freigegebene vertrauliche Projektinformation'),
          findsNothing,
        );
        expect(
          find.text('Synthetische Kundin · customer@example.test'),
          findsNothing,
        );
        expect(find.text('Kundenportal nicht verfügbar'), findsOneWidget);
        expect(tester.takeException(), isNull);
      } finally {
        await close(tester, session, api);
      }
    },
  );

  for (final readonly in [false, true]) {
    testWidgets(
      'revocation remains available with documents paused and readonly=$readonly; lost response uses same receipt',
      (tester) async {
        final api = WorkspaceApi()
          ..readonly = readonly
          ..documentsEnabled = false
          ..loseRevoke = true;
        api.grants.add(api.grant());
        final session = await show(tester, api);
        try {
          expect(
            tester
                .widget<FilledButton>(
                  find.widgetWithText(FilledButton, 'Kundenzugang erstellen'),
                )
                .onPressed,
            isNull,
          );
          expect(
            tester
                .widget<FilledButton>(
                  find.widgetWithText(
                    FilledButton,
                    'Projektinformation veröffentlichen',
                  ),
                )
                .onPressed,
            isNull,
          );
          await tap(
            tester,
            find.widgetWithText(TextButton, 'Zugang widerrufen'),
          );
          await tester.enterText(
            find.descendant(
              of: find.byType(AlertDialog),
              matching: find.byType(TextField),
            ),
            'Synthetischer Widerrufsgrund',
          );
          await tap(tester, find.widgetWithText(FilledButton, 'Widerrufen'));
          final first = api.calls.lastWhere((call) => call.body != null).body!;
          expect(api.grants.single['status'], 'revoked');
          expect(find.textContaining('Unbestätigter Widerruf'), findsOneWidget);
          await tap(
            tester,
            find.widgetWithText(FilledButton, 'Unverändert erneut senden'),
          );
          expect(api.calls.lastWhere((call) => call.body != null).body, first);
          expect(
            find.widgetWithText(TextButton, 'Zugang widerrufen'),
            findsNothing,
          );
          expect(session.pending('customer-revoke-grants-$grantId'), isFalse);
          expect(tester.takeException(), isNull);
        } finally {
          await close(tester, session, api);
        }
      },
    );
  }

  testWidgets(
    'late successful grant reply cannot restore a secret after current permission revocation',
    (tester) async {
      final deferred = Completer<void>();
      final api = WorkspaceApi()..creationReply = deferred;
      final session = await show(tester, api);
      try {
        await create(tester, complete: false);
        expect(api.grants, hasLength(1));
        api.permissions.remove('portal.manage');
        await session.load();
        await tester.pump();
        deferred.complete();
        await tester.pumpAndSettle();
        expect(find.text(api.invitation), findsNothing);
        expect(find.text('Einmaliger Zugangslink'), findsNothing);
        expect(
          find.text('Freigegebene vertrauliche Projektinformation'),
          findsNothing,
        );
        expect(find.text('Kundenportal nicht verfügbar'), findsOneWidget);
        expect(tester.takeException(), isNull);
      } finally {
        if (!deferred.isCompleted) deferred.complete();
        await close(tester, session, api);
      }
    },
  );

  for (final failure in ['sha', 'size']) {
    testWidgets(
      'original $failure mismatch prevents a preview and export route',
      (tester) async {
        final api = WorkspaceApi()..originalFailure = failure;
        final session = await show(tester, api);
        try {
          await tap(tester, find.text('Original zur Prüfung'));
          expect(api.contentCalls, hasLength(1));
          expect(
            find.text(
              'Originaldatei stimmt nicht mit Größe und Prüfsumme überein.',
            ),
            findsOneWidget,
          );
          expect(find.byType(MailAttachmentPreviewPage), findsNothing);
          expect(find.byType(BusinessCustomerWorkspacePage), findsOneWidget);
          expect(tester.takeException(), isNull);
        } finally {
          await close(tester, session, api);
        }
      },
    );
  }

  testWidgets(
    'a different acceptance classification stays unconfirmed and retries the original protected target',
    (tester) async {
      final api = WorkspaceApi()
        ..inbox = true
        ..mismatchAcceptance = true;
      final session = await show(tester, api);
      try {
        await tap(tester, find.widgetWithText(TextButton, 'Intern übernehmen'));
        expect(
          tester
              .widget<DropdownButtonFormField<String>>(
                find.byType(DropdownButtonFormField<String>),
              )
              .initialValue,
          'restricted',
        );
        await tap(
          tester,
          find.text('Inhalt, Empfänger und Umfang sind geprüft'),
        );
        await tap(tester, find.widgetWithText(FilledButton, 'Speichern'));
        final first = api.calls.lastWhere((call) => call.body != null).body!;
        expect(first['classification'], 'restricted');
        expect(
          find.text('Interne Übernahme konnte nicht bestätigt werden.'),
          findsOneWidget,
        );
        expect(session.pending('customer-accept-$uploadId'), isTrue);
        expect(find.byType(AlertDialog), findsOneWidget);
        await tap(tester, find.widgetWithText(FilledButton, 'Erneut senden'));
        expect(api.calls.lastWhere((call) => call.body != null).body, first);
        expect(session.pending('customer-accept-$uploadId'), isFalse);
        expect(find.byType(AlertDialog), findsNothing);
        expect(find.textContaining('Intern übernommen'), findsOneWidget);
        expect(
          find.widgetWithText(TextButton, 'Intern übernehmen'),
          findsNothing,
        );
        expect(acceptanceRequests(api), hasLength(2));
        expect(tester.takeException(), isNull);
      } finally {
        await close(tester, session, api);
      }
    },
  );
}

List<Map<String, dynamic>?> acceptanceRequests(WorkspaceApi api) => api.calls
    .where((call) => call.path.endsWith('/accept') && call.body != null)
    .map((call) => call.body)
    .toList();

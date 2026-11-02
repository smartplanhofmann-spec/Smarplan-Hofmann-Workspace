import 'dart:async';
import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:smartplan_office/api.dart';
import 'package:smartplan_office/business_documents.dart';
import 'package:smartplan_office/business_portal.dart';
import 'package:smartplan_office/business_session.dart';
import 'package:smartplan_office/design.dart';

const offerId = 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa';
const projectId = 'bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb';
const decisionId = 'dddddddddddddddddddddddddddddddd';
const documentId = 'eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee';
final source = <String, dynamic>{
  'offer_id': offerId,
  'number': 'AN-SYN-1',
  'project_id': projectId,
  'customer_id': 'f' * 32,
  'source_revision': 2,
  'content_hash': 'a' * 64,
  'pdf_hash': 'b' * 64,
};
Map<String, dynamic> copy(Map<String, dynamic> value) =>
    jsonDecode(jsonEncode(value)) as Map<String, dynamic>;

class PortalApi extends OfficeApi {
  PortalApi() : super(apiVersion: 'v1') {
    token = 'synthetic-internal-session';
  }
  bool feature = true, readonly = false, documentsEnabled = true;
  bool lostCreate = false, lostRevoke = false, lostOther = false;
  bool deniedOverview = false;
  Completer<void>? creationReply;
  int generation = 1;
  Set<String> permissions = {
    'finance.read',
    'finance.write',
    'projects.manage',
    'portal.manage',
  };
  Set<String>? scopedPermissions;
  final calls = <({String path, Map<String, dynamic>? body})>[];
  final grants = <Map<String, dynamic>>[];
  final requests = <String, Map<String, dynamic>>{};
  final results = <String, Map<String, dynamic>>{};
  Map<String, dynamic>? decision, adoption;

  void accept() => decision = {
    'id': decisionId,
    'offer_id': offerId,
    'decision': 'accepted',
    'declared_name': 'Synthetischer Kunde',
    'created_at': '2026-11-02T13:00:00+02:00',
    'statement_version': 'v1',
    'statement_text': 'Dieses konkrete Angebot nehme ich an.',
    'content_hash': source['content_hash'],
    'pdf_hash': source['pdf_hash'],
  };

  @override
  Future<dynamic> call(String path, [Map<String, dynamic>? body]) async {
    calls.add((path: path, body: body == null ? null : copy(body)));
    final route = path.split('?').first;
    if (route == '/api/business/capabilities') {
      final scoped = Uri.parse(path).queryParameters['project_id'] == projectId;
      return {
        'storage_version': 7,
        'compatibility_mode': readonly ? 'legacy' : 'business',
        'readonly': readonly,
        'generation': generation,
        'capabilities': ['business_documents', 'business_portal'],
        'features': ['organization_modules', if (feature) 'offer_portal'],
        'permissions': (scoped ? scopedPermissions ?? permissions : permissions)
            .toList(),
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
    if (route == '/api/business/documents/$offerId')
      return {
        'id': offerId,
        'number': 'AN-SYN-1',
        'project_id': projectId,
        'status': 'final',
        'kind': 'offer',
        'title': 'Synthetisches finales Angebot',
        'revision': 2,
        'issue_date': '2026-11-02',
        'positions': [],
        'totals': {},
      };
    if (route.endsWith('/signatures')) return {'items': []};
    if (route == '/api/business/portal/grants' && body == null) {
      if (deniedOverview)
        throw const ApiException(403, 'Synthetischer Quellenzugriff entzogen');
      expect(Uri.parse(path).queryParameters['offer_id'], offerId);
      return {
        'source': copy(source),
        'items': grants.map(copy).toList(),
        'decision': decision == null ? null : copy(decision!),
        'adoption': adoption == null ? null : copy(adoption!),
      };
    }
    if (body == null)
      throw const ApiException(404, 'Unbekannter synthetischer Pfad');
    final requestId = '${body['request_id']}';
    if (requests.containsKey(requestId)) {
      expect(body, requests[requestId]);
      return copy(results[requestId]!);
    }
    if (route == '/api/business/portal/grants') {
      expect(body['confirmation'], true);
      expect(body['offer_id'], offerId);
      expect(body['source_revision'], 2);
      expect(body['content_hash'], source['content_hash']);
      expect(body['pdf_hash'], source['pdf_hash']);
      final id = 'c' * 31 + grants.length.toRadixString(16);
      final grant = <String, dynamic>{
        ...source,
        'id': id,
        'principal': {
          'id': '1' * 32,
          'name': body['recipient_name'],
          'email': body['recipient_email'],
          'active': true,
        },
        'status': 'active',
        'created_at': '2026-11-02T10:00:00Z',
        'expires_at': DateTime.now()
            .toUtc()
            .add(const Duration(days: 7))
            .toIso8601String(),
        'created_by': 'synthetic-owner',
      };
      grants.add(grant);
      requests[requestId] = copy(body);
      results[requestId] = {'grant': copy(grant), 'link_available': false};
      await creationReply?.future;
      if (lostCreate) {
        lostCreate = false;
        throw const ApiException(0, 'Synthetisch verlorene Erfolgsantwort');
      }
      return {
        'grant': copy(grant),
        'link_available': true,
        'portal_url':
            'https://office.example.test/office/portal.html#grant=$id&key=SPPI_${'s' * 43}',
      };
    }
    if (route.endsWith('/revoke')) {
      final id = route.split('/')[5];
      final grant = grants.singleWhere((item) => item['id'] == id);
      grant['status'] = 'revoked';
      grant['revocation'] = {
        'reason': body['reason'],
        'created_at': '2026-11-02T12:00:00Z',
      };
      requests[requestId] = copy(body);
      results[requestId] = copy(grant);
      if (lostRevoke) {
        lostRevoke = false;
        throw const ApiException(0, 'Synthetisch verlorene Widerrufsantwort');
      }
      return copy(grant);
    }
    if (route == '/api/business/portal/offers/$offerId/adopt') {
      expect(body['confirmation'], true);
      expect(body['decision_id'], decisionId);
      expect(body['content_hash'], source['content_hash']);
      expect(body['pdf_hash'], source['pdf_hash']);
      expect(adoption, isNull);
      adoption = {
        'id': '2' * 32,
        'offer_id': offerId,
        'decision_id': decisionId,
        'document_id': documentId,
        'project_id': projectId,
        'created_at': '2026-11-02T12:30:00Z',
        'created_by': 'synthetic-owner',
      };
      requests[requestId] = copy(body);
      results[requestId] = copy(adoption!);
      return copy(adoption!);
    }
    if (lostOther) {
      lostOther = false;
      throw const ApiException(0, 'Andere Antwort verloren');
    }
    return {};
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
    PortalApi api, {
    double width = 1200,
    bool documentEntry = false,
    ValueChanged<String>? onOpenDocument,
  }) async {
    tester.view.physicalSize = Size(width, 1000);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    final session = BusinessSession(
      api: api,
      projects: [
        {'id': projectId, 'name': 'Synthetisches Projekt'},
      ],
    );
    await session.load();
    await tester.pumpWidget(
      MaterialApp(
        theme: officeTheme(),
        home: documentEntry
            ? BusinessDocumentPage(session: session, id: offerId)
            : Scaffold(
                body: SingleChildScrollView(
                  child: BusinessOfferPortalPanel(
                    session: session,
                    offerId: offerId,
                    projectId: projectId,
                    onOpenDocument: onOpenDocument,
                  ),
                ),
              ),
      ),
    );
    await tester.pumpAndSettle();
    return session;
  }

  Future<void> close(
    WidgetTester tester,
    BusinessSession session,
    PortalApi api,
  ) async {
    await tester.pumpWidget(const SizedBox());
    session.dispose();
    api.dispose();
  }

  Future<void> tap(WidgetTester tester, Finder target) async {
    await tester.ensureVisible(target);
    await tester.pumpAndSettle();
    await tester.tap(target);
    await tester.pumpAndSettle();
  }

  Future<void> type(WidgetTester tester, String name, String value) async {
    await tester.ensureVisible(field(name));
    await tester.enterText(field(name), value);
    await tester.pumpAndSettle();
  }

  Future<void> create(
    WidgetTester tester, {
    String days = '7',
    bool waitForReply = true,
  }) async {
    await tap(
      tester,
      find.widgetWithText(FilledButton, 'Portalzugang erstellen').last,
    );
    await type(tester, 'recipient_name', 'Synthetischer Empfänger');
    await type(tester, 'recipient_email', 'customer@example.test');
    await type(tester, 'expires_in_days', days);
    await tap(
      tester,
      find.text(
        'Finales Angebot, Empfänger und Zugangsdauer sind geprüft. Den Link gebe ich selbst weiter.',
      ),
    );
    final submit = find
        .widgetWithText(FilledButton, 'Portalzugang erstellen')
        .last;
    if (waitForReply) {
      await tap(tester, submit);
    } else {
      await tester.ensureVisible(submit);
      await tester.tap(submit);
      await tester.pump();
    }
  }

  Future<void> revoke(WidgetTester tester) async {
    await tap(tester, find.text('Zugang widerrufen'));
    await tester.enterText(
      find.byKey(const ValueKey('portal-revocation-reason')),
      'Synthetischer Empfängerwechsel',
    );
    await tap(
      tester,
      find.text(
        'Diesen Zugang einschließlich bestehender Portalsitzungen sperren',
      ),
    );
    await tap(tester, find.text('Zugang verbindlich widerrufen'));
  }

  for (final width in [390.0, 1200.0]) {
    testWidgets(
      'Final offer explicitly creates a one-time portal URL at width $width',
      (tester) async {
        final api = PortalApi();
        final session = await show(
          tester,
          api,
          width: width,
          documentEntry: true,
        );
        try {
          await create(tester, days: '31');
          expect(api.grants, isEmpty);
          expect(find.textContaining('von 1 bis 30 Tagen'), findsOneWidget);
          await type(tester, 'expires_in_days', '7');
          await tap(
            tester,
            find.widgetWithText(FilledButton, 'Portalzugang erstellen').last,
          );
          expect(api.grants, hasLength(1));
          expect(
            find.byKey(const ValueKey('portal-fresh-url')),
            findsOneWidget,
          );
          expect(
            find.textContaining('keine Nachricht versendet'),
            findsOneWidget,
          );
          expect(
            tester
                .widget<Text>(find.textContaining('gültig bis '))
                .data!
                .endsWith(' UTC'),
            true,
          );
          expect(session.pendingEditorValues('portal-create-$offerId'), isNull);
          expect(
            api.calls.any(
              (call) =>
                  call.body != null && jsonEncode(call.body).contains('SPPI_'),
            ),
            false,
          );
          await tap(tester, find.text('Link ausblenden'));
          await tap(tester, find.byTooltip('Portalzugänge aktualisieren'));
          expect(find.byKey(const ValueKey('portal-fresh-url')), findsNothing);
          await revoke(tester);
          expect(api.grants.single['status'], 'revoked');
          expect(find.text('Zugang widerrufen'), findsNothing);
          expect(tester.takeException(), isNull);
        } finally {
          await close(tester, session, api);
        }
      },
    );
  }

  testWidgets(
    'Lost creation response reopens the same request and never fabricates a second link',
    (tester) async {
      final api = PortalApi()..lostCreate = true;
      final session = await show(tester, api);
      try {
        await create(tester);
        final first = api.calls.lastWhere((call) => call.body != null).body!;
        expect(api.grants, hasLength(1));
        await tap(tester, find.text('Schließen'));
        await tap(
          tester,
          find.widgetWithText(FilledButton, 'Portalzugang erstellen').last,
        );
        expect(
          tester.widget<TextFormField>(field('recipient_email')).enabled,
          false,
        );
        await tap(tester, find.text('Erneut senden'));
        expect(api.calls.lastWhere((call) => call.body != null).body!, first);
        expect(api.grants, hasLength(1));
        expect(find.byKey(const ValueKey('portal-fresh-url')), findsNothing);
        expect(
          find.textContaining('Link kann nicht erneut ausgelesen werden'),
          findsOneWidget,
        );
        await revoke(tester);
        await create(tester);
        expect(api.grants, hasLength(2));
        expect(find.byKey(const ValueKey('portal-fresh-url')), findsOneWidget);
      } finally {
        await close(tester, session, api);
      }
    },
  );

  testWidgets(
    'Scoped portal grants enable management and scoped denial clears the one-time URL',
    (tester) async {
      final api = PortalApi()
        ..permissions = {'finance.read'}
        ..scopedPermissions = {
          'finance.read',
          'portal.manage',
          'finance.write',
          'projects.manage',
        };
      final session = await show(tester, api);
      try {
        expect(session.can('portal.manage'), false);
        await create(tester);
        expect(find.byKey(const ValueKey('portal-fresh-url')), findsOneWidget);
        expect(session.can('portal.manage'), false);
        api.scopedPermissions = {'finance.read'};
        await session.load();
        await tester.pumpAndSettle();
        expect(find.byKey(const ValueKey('portal-fresh-url')), findsNothing);
        expect(
          find.text('Synthetischer Empfänger · customer@example.test'),
          findsNothing,
        );
        expect(find.text('Portalzugang erstellen'), findsNothing);
      } finally {
        await close(tester, session, api);
      }
    },
  );

  testWidgets(
    'Security revocation retries unchanged across readonly generation while ordinary pending writes stay blocked',
    (tester) async {
      final api = PortalApi();
      final session = await show(tester, api);
      try {
        await create(tester);
        api.lostOther = true;
        await expectLater(
          session.command('ordinary-pending', '/documents/$offerId/update', {
            'value': 'original',
          }),
          throwsA(
            isA<ApiException>().having((error) => error.status, 'status', 0),
          ),
        );
        api.lostRevoke = true;
        await revoke(tester);
        final first = api.calls
            .lastWhere(
              (call) => call.path.endsWith('/revoke') && call.body != null,
            )
            .body!;
        api.readonly = true;
        api.documentsEnabled = false;
        api.generation = 2;
        await session.load();
        await tester.pumpAndSettle();
        await tap(tester, find.text('Erneut senden'));
        expect(
          api.calls
              .lastWhere(
                (call) => call.path.endsWith('/revoke') && call.body != null,
              )
              .body!,
          first,
        );
        expect(api.grants.single['status'], 'revoked');
        await expectLater(
          session.command('ordinary-pending', '/documents/$offerId/update', {
            'value': 'original',
          }),
          throwsA(
            isA<ApiException>().having((error) => error.status, 'status', 403),
          ),
        );
        await expectLater(
          session.command('not-revoke', '/portal/grants', {}),
          throwsA(
            isA<ApiException>().having((error) => error.status, 'status', 403),
          ),
        );
        await expectLater(
          session.command(
            'query-bypass',
            '/portal/grants/${api.grants.single['id']}/revoke?x=1',
            {},
          ),
          throwsA(
            isA<ApiException>().having((error) => error.status, 'status', 403),
          ),
        );
        expect(find.text('Portalzugang erstellen'), findsNothing);
        expect(find.textContaining('weiterhin widerrufen'), findsOneWidget);
      } finally {
        await close(tester, session, api);
      }
    },
  );

  testWidgets(
    'An accepted decision adopts only after explicit confirmation and keeps the existing project',
    (tester) async {
      final api = PortalApi()..accept();
      String? opened;
      final session = await show(
        tester,
        api,
        onOpenDocument: (id) => opened = id,
      );
      try {
        expect(find.text('Kunde hat angenommen'), findsOneWidget);
        expect(find.textContaining('02.11.2026 · 11:00 UTC'), findsOneWidget);
        await tap(tester, find.text('Annahme in Auftragsentwurf übernehmen'));
        await tap(tester, find.text('Auftragsbestätigungsentwurf erstellen'));
        expect(api.adoption, isNull);
        await tap(
          tester,
          find.text(
            'Diese Kundenerklärung und Angebotsfassung in einen Auftragsbestätigungsentwurf im bestehenden Projekt übernehmen.',
          ),
        );
        await tap(tester, find.text('Auftragsbestätigungsentwurf erstellen'));
        expect(api.adoption!['project_id'], projectId);
        await tap(tester, find.text('Auftragsbestätigungsentwurf öffnen'));
        expect(opened, documentId);
        expect(
          find.text('Annahme in Auftragsentwurf übernehmen'),
          findsNothing,
        );
        expect(
          api.calls.any(
            (call) =>
                call.body != null &&
                (call.path.contains('/email') ||
                    call.path.contains('/finalize') ||
                    call.path.contains('/payments')),
          ),
          false,
        );
      } finally {
        await close(tester, session, api);
      }
    },
  );

  testWidgets(
    'A recorded decision permits a new explicit historical access after revocation',
    (tester) async {
      final api = PortalApi()..accept();
      final session = await show(tester, api);
      try {
        await create(tester);
        expect(
          find.widgetWithText(FilledButton, 'Portalzugang erstellen'),
          findsNothing,
        );
        expect(
          find.textContaining('bereits ein aktiver Zugang'),
          findsOneWidget,
        );
        await revoke(tester);
        expect(find.text('Kunde hat angenommen'), findsOneWidget);
        await create(tester);
        expect(api.grants, hasLength(2));
        expect(api.decision!['id'], decisionId);
        expect(api.adoption, isNull);
        expect(find.byKey(const ValueKey('portal-fresh-url')), findsOneWidget);
      } finally {
        await close(tester, session, api);
      }
    },
  );

  testWidgets(
    'Late creation reply never reveals the link after a known source denial',
    (tester) async {
      final reply = Completer<void>();
      final api = PortalApi()..creationReply = reply;
      final session = await show(tester, api);
      try {
        await create(tester, waitForReply: false);
        expect(api.grants, hasLength(1));
        await tester.tapAt(const Offset(8, 8));
        await tester.pumpAndSettle();
        api.deniedOverview = true;
        await tap(tester, find.byTooltip('Portalzugänge aktualisieren'));
        expect(
          find.text('Synthetischer Quellenzugriff entzogen'),
          findsOneWidget,
        );
        reply.complete();
        await tester.pumpAndSettle();
        expect(find.byKey(const ValueKey('portal-fresh-url')), findsNothing);
        expect(
          find.textContaining('Der Link wird nur jetzt angezeigt'),
          findsNothing,
        );
      } finally {
        if (!reply.isCompleted) reply.complete();
        await close(tester, session, api);
      }
    },
  );

  testWidgets(
    'Late creation reply never revives the link after a known revocation',
    (tester) async {
      final reply = Completer<void>();
      final api = PortalApi()..creationReply = reply;
      final session = await show(tester, api);
      try {
        await create(tester, waitForReply: false);
        await tester.tapAt(const Offset(8, 8));
        await tester.pumpAndSettle();
        await tap(tester, find.byTooltip('Portalzugänge aktualisieren'));
        await revoke(tester);
        reply.complete();
        await tester.pumpAndSettle();
        expect(api.grants.single['status'], 'revoked');
        expect(find.byKey(const ValueKey('portal-fresh-url')), findsNothing);
        expect(
          find.textContaining('Der Link wird nur jetzt angezeigt'),
          findsNothing,
        );
      } finally {
        if (!reply.isCompleted) reply.complete();
        await close(tester, session, api);
      }
    },
  );

  testWidgets(
    'Missing online feature exposes no portal controls or API calls and no readonly bypass',
    (tester) async {
      final api = PortalApi()..feature = false;
      final session = await show(tester, api, documentEntry: true);
      try {
        expect(find.text('Kundenportal für dieses Angebot'), findsNothing);
        expect(
          api.calls.where((call) => call.path.contains('/portal/')),
          isEmpty,
        );
        api.readonly = true;
        await session.load();
        await expectLater(
          session.command(
            'unsupported-revoke',
            '/portal/grants/${'c' * 32}/revoke',
            {},
          ),
          throwsA(
            isA<ApiException>().having((error) => error.status, 'status', 403),
          ),
        );
      } finally {
        await close(tester, session, api);
      }
    },
  );
}

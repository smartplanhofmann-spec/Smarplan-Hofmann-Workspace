import 'dart:convert';

import 'package:file_selector/file_selector.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:smartplan_office/api.dart';
import 'package:smartplan_office/inquiry_pages.dart';

Map<String, dynamic> copy(Map<String, dynamic> value) =>
    Map<String, dynamic>.from(jsonDecode(jsonEncode(value)));

const inquiryId = '11111111111111111111111111111111';
const customerId = '22222222222222222222222222222222';
const projectId = '33333333333333333333333333333333';
const tokenId = '44444444444444444444444444444444';
const privateToken = 'SPIN_SYNTHETIC_SECRET_FOR_ONETIME_WIDGET_TEST';

class InquiryApi extends OfficeApi {
  InquiryApi({bool online = true})
    : super(
        baseUrl: 'https://synthetic.example.test',
        apiVersion: online ? 'v1' : '',
      );
  final calls = <({String path, Map<String, dynamic>? body})>[];
  final records = <String, Map<String, dynamic>>{};
  final receipts = <String, Map<String, dynamic>>{};
  final tokens = <Map<String, dynamic>>[];
  final customers = <Map<String, dynamic>>[
    {
      'id': customerId,
      'name': 'Synthetischer Kunde',
      'email': 'synthetic@example.test',
      'active': 1,
    },
  ];
  bool lostCreateResponse = false;
  int? listError, saveError, tokenListError;

  Map<String, dynamic> fixture({
    String source = 'whatsapp',
    String status = 'new',
  }) => {
    'id': inquiryId,
    'source': source,
    'source_account': 'manual',
    'source_id': null,
    'subject': 'Synthetischer Umbau',
    'message': 'Bitte Unterlagen prüfen und zurückrufen.',
    'message_preview': 'Bitte Unterlagen prüfen und zurückrufen.',
    'sender_name': 'Synthetische Kundin',
    'sender_email': 'synthetic@example.test',
    'sender_phone': '+49 123 456789',
    'received_at': '2026-10-24T12:00:00Z',
    'status': status,
    'review_method': '',
    'acceptance_channel': '',
    'customer_id': null,
    'customer': null,
    'project_id': null,
    'project': null,
    'next_action': '',
    'due_date': null,
    'sevdesk_url': '',
    'revision': 1,
    'provenance': {'warnings': [], 'attachments': []},
    'candidate_customers': [
      {
        'id': customerId,
        'name': 'Synthetischer Kunde',
        'email': 'synthetic@example.test',
        'phone': '+49 123 456789',
        'active': 1,
        'match_reasons': ['email'],
      },
    ],
  };

  @override
  Future<dynamic> call(String path, [Map<String, dynamic>? body]) async {
    calls.add((path: path, body: body == null ? null : copy(body)));
    if (path == '/api/customers') return customers.map(copy).toList();
    if (path == '/api/inquiries' && body == null) {
      if (listError != null)
        throw ApiException(listError!, 'Synthetic list unavailable');
      return records.values.map(copy).toList();
    }
    if ((path == '/api/inquiries' || path == '/api/inquiries/import-eml') &&
        body != null) {
      final key = body['request_id'];
      if (receipts[key] != null) return copy(receipts[key]!);
      final created = fixture(
        source: path.endsWith('import-eml') ? 'import' : body['source'],
      );
      if (!path.endsWith('import-eml')) {
        for (final key in [
          'subject',
          'message',
          'sender_name',
          'sender_email',
          'sender_phone',
        ]) {
          created[key] = body[key];
        }
      } else {
        created['provenance'] = {
          'warnings': [
            'Anhänge sind nur vermerkt und wurden nicht übernommen.',
          ],
          'attachments': [],
        };
      }
      records[inquiryId] = created;
      receipts[key] = copy(created);
      if (lostCreateResponse) {
        lostCreateResponse = false;
        throw const ApiException(
          0,
          'Synthetic accepted request, response lost',
        );
      }
      return copy(created);
    }
    if (path == '/api/inquiries/$inquiryId') {
      if (body == null) return copy(records[inquiryId]!);
      if (saveError != null)
        throw ApiException(saveError!, 'Synthetic save rejected');
      records[inquiryId] = {
        ...records[inquiryId]!,
        ...body,
        'revision': records[inquiryId]!['revision'] + 1,
      };
      return copy(records[inquiryId]!);
    }
    if (path == '/api/inquiries/$inquiryId/convert') {
      if (saveError != null)
        throw ApiException(saveError!, 'Synthetic conversion rejected');
      final project = {
        'id': projectId,
        'name': body!['project_name'],
        'customer_id': body['customer_id'] ?? 'new-customer',
        'customer': body['customer']?['name'] ?? 'Synthetischer Kunde',
      };
      records[inquiryId] = {
        ...records[inquiryId]!,
        'status': 'converted',
        'project_id': projectId,
        'project': project,
      };
      return {'inquiry': copy(records[inquiryId]!), 'project': project};
    }
    if (path == '/api/inbound/gmail/tokens') {
      if (body == null) {
        if (tokenListError != null)
          throw ApiException(
            tokenListError!,
            'Synthetic credential access revoked',
          );
        return tokens.map(copy).toList();
      }
      final token = {
        'id': tokenId,
        'name': body['name'],
        'source_account': body['source_account'],
        'created_at': '2026-10-24T12:00:00Z',
        'expires_at': '2099-10-24T12:00:00Z',
        'revoked_at': null,
        'last_used_at': null,
      };
      tokens.add(token);
      return {...token, 'token': privateToken};
    }
    if (path == '/api/inbound/gmail/tokens/$tokenId/revoke') {
      tokens.single['revoked_at'] = '2026-10-24T12:05:00Z';
      return copy(tokens.single);
    }
    throw StateError('Unexpected synthetic inquiry request: $path');
  }
}

Future<void> showPage(
  WidgetTester tester,
  Widget page, {
  Size size = const Size(1100, 1900),
}) async {
  tester.view.physicalSize = size;
  tester.view.devicePixelRatio = 1;
  addTearDown(tester.view.resetPhysicalSize);
  addTearDown(tester.view.resetDevicePixelRatio);
  await tester.pumpWidget(MaterialApp(home: page));
  await tester.pumpAndSettle();
}

Finder field(String label) => find.byWidgetPredicate(
  (widget) => widget is TextField && widget.decoration?.labelText == label,
);

Future<void> tapVisible(WidgetTester tester, Finder finder) async {
  await tester.ensureVisible(finder);
  await tester.pumpAndSettle();
  await tester.tap(finder);
  await tester.pumpAndSettle();
}

void main() {
  testWidgets(
    'Inbox and Gmail management expose no data or requests to assigned nonowners',
    (tester) async {
      final api = InquiryApi();
      await showPage(tester, InquiriesPage(api: api, role: 'manager'));
      expect(api.calls, isEmpty);
      expect(
        find.textContaining('Geschäftsführung vorbehalten'),
        findsOneWidget,
      );
      await tester.pumpWidget(
        MaterialApp(
          home: GmailInboxPage(api: api, role: 'technician'),
        ),
      );
      await tester.pumpAndSettle();
      expect(api.calls, isEmpty);
      expect(find.text('Eingangsschlüssel erstellen'), findsNothing);
    },
  );

  testWidgets('Inbox shows real next steps and filters the actual records', (
    tester,
  ) async {
    final api = InquiryApi();
    api.records[inquiryId] = {
      ...api.fixture(),
      'next_action': 'Rückruf am Nachmittag',
      'due_date': '2000-01-01',
    };
    api.records['other'] = {
      ...api.fixture(source: 'gmail'),
      'id': 'other',
      'subject': 'Anderes Vorhaben',
      'status': 'converted',
    };
    await showPage(tester, InquiriesPage(api: api, role: 'owner'));
    expect(find.text('Synthetischer Umbau'), findsOneWidget);
    expect(find.text('Anderes Vorhaben'), findsNothing);
    expect(find.textContaining('Rückruf am Nachmittag'), findsOneWidget);
    expect(find.text('Überfällige Wiedervorlagen'), findsOneWidget);
    expect(
      find.descendant(
        of: find.byKey(const ValueKey('inquiry-count-overdue')),
        matching: find.text('1'),
      ),
      findsOneWidget,
    );
    await tester.enterText(field('Anfragen durchsuchen'), 'nicht vorhanden');
    await tester.pumpAndSettle();
    expect(find.text('Synthetischer Umbau'), findsNothing);
    await tester.enterText(field('Anfragen durchsuchen'), 'synthetisch');
    await tester.pumpAndSettle();
    expect(find.text('Synthetischer Umbau'), findsOneWidget);
  });

  testWidgets(
    'Old-server failure is explicit and does not invent an inbox connection',
    (tester) async {
      final api = InquiryApi()..listError = 404;
      await showPage(tester, InquiriesPage(api: api, role: 'owner'));
      expect(
        find.textContaining('benötigt das neue Serverupdate'),
        findsOneWidget,
      );
      expect(api.calls.map((c) => c.path), ['/api/inquiries']);
      expect(find.textContaining('Verbunden'), findsNothing);
    },
  );

  testWidgets(
    'Manual WhatsApp capture preserves input and request identity after a lost response',
    (tester) async {
      final api = InquiryApi()..lostCreateResponse = true;
      await showPage(tester, InquiriesPage(api: api, role: 'owner'));
      await tester.tap(find.text('Anfrage erfassen'));
      await tester.pumpAndSettle();
      await tester.enterText(
        field('Betreff / Vorhaben').first,
        'Synthetischer Rückruf',
      );
      await tester.enterText(
        field('Nachricht / Gesprächsnotiz').first,
        'Text aus einer synthetischen WhatsApp-Nachricht.',
      );
      await tester.tap(find.byType(DropdownButtonFormField<String>).first);
      await tester.pumpAndSettle();
      await tester.tap(find.text('WhatsApp-Nachricht einfügen').last);
      await tester.pumpAndSettle();
      await tapVisible(tester, find.text('Anfrage speichern'));
      expect(
        find.textContaining('Antwort ist noch nicht bestätigt'),
        findsOneWidget,
      );
      expect(find.text('Synthetischer Rückruf'), findsOneWidget);
      final first = api.calls
          .lastWhere((c) => c.path == '/api/inquiries' && c.body != null)
          .body!;
      await tapVisible(tester, find.text('Erneut übermitteln'));
      final creates = api.calls
          .where((c) => c.path == '/api/inquiries' && c.body != null)
          .toList();
      expect(creates, hasLength(2));
      expect(creates.first.body, creates.last.body);
      expect(first['source'], 'whatsapp');
      expect(first.containsKey('status'), isFalse);
      expect(api.records, hasLength(1));
      expect(find.text('Kunde und nächster Schritt'), findsOneWidget);
    },
  );

  testWidgets(
    'A bounded EML file is sent once and attachment limitations are visible',
    (tester) async {
      final api = InquiryApi();
      final bytes = utf8.encode(
        'From: synthetic@example.test\nSubject: Synthetic\n\nOnly synthetic plain text.',
      );
      await showPage(
        tester,
        InquiriesPage(
          api: api,
          role: 'owner',
          pickEmail: () async =>
              XFile.fromData(Uint8List.fromList(bytes), path: 'synthetic.eml'),
        ),
      );
      await tester.tap(find.text('E-Mail importieren'));
      await tester.pumpAndSettle();
      expect(find.text('synthetic.eml'), findsOneWidget);
      await tester.tap(find.text('E-Mail übernehmen').last);
      await tester.pumpAndSettle();
      final sent = api.calls
          .singleWhere((c) => c.path == '/api/inquiries/import-eml')
          .body!;
      expect(base64Decode(sent['content_base64']), bytes);
      expect(
        find.byType(InquiryDetailPage),
        findsOneWidget,
        reason: api.calls.map((call) => call.path).join(', '),
      );
      expect(
        find.text('Anhänge sind nur vermerkt und wurden nicht übernommen.'),
        findsOneWidget,
      );
      expect(
        api.calls.where((c) => c.path == '/api/inquiries/import-eml'),
        hasLength(1),
      );
    },
  );

  testWidgets('Oversized EML never reaches the server', (tester) async {
    final api = InquiryApi();
    await showPage(
      tester,
      InquiriesPage(
        api: api,
        role: 'owner',
        pickEmail: () async =>
            XFile.fromData(Uint8List(512 * 1024 + 1), name: 'too-large.eml'),
      ),
    );
    await tester.tap(find.text('E-Mail importieren'));
    await tester.pumpAndSettle();
    expect(find.textContaining('höchstens 512 KiB'), findsOneWidget);
    expect(
      api.calls.where((c) => c.path == '/api/inquiries/import-eml'),
      isEmpty,
    );
  });

  testWidgets(
    'Project handover works directly from a new enquiry without a fabricated acceptance',
    (tester) async {
      final api = InquiryApi();
      api.records[inquiryId] = api.fixture();
      Map<String, dynamic>? opened;
      await showPage(
        tester,
        InquiriesPage(
          api: api,
          role: 'owner',
          onProject: (project) async => opened = project,
        ),
      );
      await tester.tap(find.text('Synthetischer Umbau'));
      await tester.pumpAndSettle();
      await tapVisible(tester, find.text('Als Projekt übernehmen'));
      expect(find.text('Anfrage mit Projekt verknüpfen'), findsOneWidget);
      await tester.enterText(
        field('Projektname').first,
        'Erstklärung und Aufmaß',
      );
      await tapVisible(tester, find.text('Kunde und Projekt bestätigen'));
      expect(opened?['name'], 'Erstklärung und Aufmaß');
      final body = api.calls
          .singleWhere((c) => c.path.endsWith('/convert'))
          .body!;
      expect(body['customer_id'], customerId);
      expect(body['revision'], 1);
      expect(body.containsKey('acceptance_channel'), isFalse);
      expect(
        api.calls.where(
          (c) => c.path == '/api/inquiries/$inquiryId' && c.body != null,
        ),
        isEmpty,
      );
    },
  );

  testWidgets(
    'A failed update keeps the next-action draft visible and editable',
    (tester) async {
      final api = InquiryApi()..saveError = 400;
      api.records[inquiryId] = api.fixture();
      await showPage(
        tester,
        InquiryDetailPage(api: api, role: 'owner', inquiryId: inquiryId),
      );
      await tester.enterText(
        field('Nächster Schritt / Wiedervorlage').first,
        'Unterlagen sichten, dann Termin abstimmen',
      );
      await tapVisible(tester, find.text('Änderungen speichern'));
      expect(find.text('Synthetic save rejected'), findsOneWidget);
      expect(
        find.text('Unterlagen sichten, dann Termin abstimmen'),
        findsOneWidget,
      );
      expect(api.records[inquiryId]!['next_action'], '');
      api.saveError = null;
      await tapVisible(tester, find.text('Änderungen speichern'));
      expect(
        api.records[inquiryId]!['next_action'],
        'Unterlagen sichten, dann Termin abstimmen',
      );
    },
  );

  testWidgets('Project handover first saves an edited next step', (
    tester,
  ) async {
    final api = InquiryApi();
    api.records[inquiryId] = api.fixture();
    await showPage(tester, InquiriesPage(api: api, role: 'owner'));
    await tester.tap(find.text('Synthetischer Umbau'));
    await tester.pumpAndSettle();
    await tester.enterText(
      field('Nächster Schritt / Wiedervorlage').first,
      'Vor Ort Umfang klären',
    );
    await tapVisible(tester, find.text('Als Projekt übernehmen'));
    final update = api.calls.singleWhere(
      (call) => call.path == '/api/inquiries/$inquiryId' && call.body != null,
    );
    expect(update.body!['next_action'], 'Vor Ort Umfang klären');
    await tapVisible(tester, find.text('Kunde und Projekt bestätigen'));
    expect(
      api.calls
          .singleWhere((call) => call.path.endsWith('/convert'))
          .body!['revision'],
      2,
    );
    expect(api.records[inquiryId]!['next_action'], 'Vor Ort Umfang klären');
  });

  testWidgets(
    'Leaving or reloading a changed enquiry asks before discarding draft fields',
    (tester) async {
      final api = InquiryApi();
      api.records[inquiryId] = api.fixture();
      await showPage(tester, InquiriesPage(api: api, role: 'owner'));
      await tester.tap(find.text('Synthetischer Umbau'));
      await tester.pumpAndSettle();
      await tester.enterText(
        field('Nächster Schritt / Wiedervorlage').first,
        'Ungespeicherter Rückruf',
      );
      await tester.pumpAndSettle();
      await tester.pageBack();
      await tester.pumpAndSettle();
      expect(find.text('Ungespeicherte Angaben verwerfen?'), findsOneWidget);
      await tester.tap(find.text('Weiter bearbeiten'));
      await tester.pumpAndSettle();
      expect(find.text('Ungespeicherter Rückruf'), findsOneWidget);
      await tester.tap(find.byTooltip('Anfrage neu laden'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Angaben verwerfen'));
      await tester.pumpAndSettle();
      expect(find.text('Ungespeicherter Rückruf'), findsNothing);
      expect(
        api.calls.where(
          (call) =>
              call.path == '/api/inquiries/$inquiryId' && call.body != null,
        ),
        isEmpty,
      );
    },
  );

  testWidgets(
    'Gmail secret is shown only once and metadata does not claim a successful connection',
    (tester) async {
      final api = InquiryApi();
      final clipboard = <MethodCall>[];
      tester.binding.defaultBinaryMessenger.setMockMethodCallHandler(
        SystemChannels.platform,
        (call) async {
          clipboard.add(call);
          return null;
        },
      );
      addTearDown(
        () => tester.binding.defaultBinaryMessenger.setMockMethodCallHandler(
          SystemChannels.platform,
          null,
        ),
      );
      await showPage(tester, GmailInboxPage(api: api, role: 'owner'));
      await tester.enterText(
        field('Gmail-Adresse des einzubindenden Postfachs').first,
        'synthetic@gmail.com',
      );
      await tapVisible(tester, find.text('Eingangsschlüssel erstellen'));
      expect(find.text(privateToken), findsOneWidget);
      expect(clipboard.where((c) => c.method == 'Clipboard.setData'), isEmpty);
      expect(find.textContaining('Nicht im Chat teilen'), findsOneWidget);
      await tester.tap(find.text('Schlüssel kopieren'));
      await tester.pumpAndSettle();
      expect(
        clipboard
            .singleWhere((c) => c.method == 'Clipboard.setData')
            .arguments['text'],
        privateToken,
      );
      await tester.tap(find.text('Fertig'));
      await tester.pumpAndSettle();
      expect(find.text(privateToken), findsNothing);
      expect(
        find.text('Wartet auf erste Nachrichtenübernahme'),
        findsOneWidget,
      );
      expect(find.text('Nachrichtenübernahme bestätigt'), findsNothing);
      expect(api.tokens.single.containsKey('token'), isFalse);
    },
  );

  testWidgets(
    'Gmail revocation requires the explicit confirmation and keeps existing enquiries',
    (tester) async {
      final api = InquiryApi();
      api.tokens.add({
        'id': tokenId,
        'name': 'Synthetischer Eingang',
        'source_account': 'synthetic@gmail.com',
        'expires_at': '2099-01-01T12:00:00Z',
        'revoked_at': null,
        'last_used_at': '2026-10-24T12:00:00Z',
      });
      api.records[inquiryId] = api.fixture();
      await showPage(tester, GmailInboxPage(api: api, role: 'owner'));
      expect(find.text('Nachrichtenübernahme bestätigt'), findsOneWidget);
      await tapVisible(tester, find.text('Zugang widerrufen'));
      await tester.tap(find.text('Abbrechen'));
      await tester.pumpAndSettle();
      expect(api.calls.where((c) => c.path.endsWith('/revoke')), isEmpty);
      await tapVisible(tester, find.text('Zugang widerrufen'));
      await tester.tap(find.text('Zugang widerrufen').last);
      await tester.pumpAndSettle();
      expect(api.calls.where((c) => c.path.endsWith('/revoke')), hasLength(1));
      expect(find.text('Widerrufen'), findsOneWidget);
      expect(api.records, hasLength(1));
    },
  );

  testWidgets(
    'A rejected refresh hides cached owner-only enquiries and token metadata',
    (tester) async {
      final api = InquiryApi();
      api.records[inquiryId] = api.fixture();
      await showPage(tester, InquiriesPage(api: api, role: 'owner'));
      expect(find.text('Synthetischer Umbau'), findsOneWidget);
      api.listError = 403;
      await tester.tap(find.byTooltip('Anfragen aktualisieren'));
      await tester.pumpAndSettle();
      expect(find.text('Synthetischer Umbau'), findsNothing);
      api.tokens.add({
        'id': tokenId,
        'name': 'Private token metadata',
        'source_account': 'private@example.test',
        'revoked_at': null,
        'expires_at': '2099-01-01T12:00:00Z',
        'last_used_at': null,
      });
      await tester.pumpWidget(
        MaterialApp(
          home: GmailInboxPage(api: api, role: 'owner'),
        ),
      );
      await tester.pumpAndSettle();
      expect(find.text('Private token metadata'), findsOneWidget);
      api.tokenListError = 403;
      await tester.tap(find.byTooltip('Gmail-Eingang aktualisieren'));
      await tester.pumpAndSettle();
      expect(find.text('Private token metadata'), findsNothing);
      expect(find.text('private@example.test'), findsNothing);
    },
  );

  testWidgets(
    'Local capture works without offering an unusable central Gmail token',
    (tester) async {
      final api = InquiryApi(online: false);
      await showPage(tester, InquiriesPage(api: api, role: 'owner'));
      expect(find.text('Anfrage erfassen'), findsOneWidget);
      expect(find.text('Gmail einrichten'), findsNothing);
      api.calls.clear();
      await tester.pumpWidget(
        MaterialApp(
          home: GmailInboxPage(api: api, role: 'owner'),
        ),
      );
      await tester.pumpAndSettle();
      expect(
        find.textContaining('Online-App auf dem gemeinsamen Server'),
        findsOneWidget,
      );
      expect(api.calls, isEmpty);
    },
  );

  testWidgets('Inbox remains usable on a narrow phone viewport', (
    tester,
  ) async {
    final api = InquiryApi();
    api.records[inquiryId] = api.fixture();
    await showPage(
      tester,
      InquiriesPage(api: api, role: 'owner'),
      size: const Size(390, 844),
    );
    expect(tester.takeException(), isNull);
    await tapVisible(tester, find.text('Synthetischer Umbau'));
    expect(tester.takeException(), isNull);
    expect(find.textContaining('Bitte Unterlagen prüfen'), findsWidgets);
  });
}

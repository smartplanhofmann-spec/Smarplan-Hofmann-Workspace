import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:smartplan_office/api.dart';
import 'package:smartplan_office/integration_pages.dart';
import 'package:smartplan_office/project_integration_widgets.dart';

const projectId = '11111111111111111111111111111111';
Map<String, dynamic> clone(Map<String, dynamic> value) =>
    Map<String, dynamic>.from(jsonDecode(jsonEncode(value)));

class IntegrationsApi extends OfficeApi {
  IntegrationsApi() : super(apiVersion: 'v1') {
    token = 'synthetic-session';
  }
  final calls = <({String path, Map<String, dynamic>? body})>[];
  final status = <String, Map<String, dynamic>>{
    for (final id in integrationNames.keys)
      id: {
        'id': id,
        'method': id == 'sevdesk' ? 'api' : 'bot',
        'configured': false,
        'connected': false,
        'state': 'disconnected',
        'revision': 0,
        'generation': 1,
        'binding': null,
        'data': null,
        if (id != 'sevdesk')
          'redirect_uri':
              'https://example.test/api/v1/integrations/$id/callback',
        'scopes': [if (id == 'google_calendar') 'calendar.events.readonly'],
      },
  };
  bool old = false, assigned = true, loseAck = false, unsafeOAuth = false;
  int? syncFailure;
  int? botFailure;
  bool previewPending = false, loseBotAck = false;
  bool badCatalog = false;
  final botReceipts = <String, Map<String, dynamic>>{};
  late Map<String, dynamic> file;
  final receipts = <String, Map<String, dynamic>>{};
  final candidates = <String, Map<String, dynamic>>{
    'sevdesk': {
      'contact': {'id': 'contact-a', 'name': 'Synthetischer Kontakt'},
      'offers': [
        {
          'id': 'offer-a',
          'number': 'ANG-1',
          'title': 'Nur dieses Angebot',
          'status_label': 'Offen',
        },
        {
          'id': 'offer-b',
          'number': 'ANG-2',
          'title': 'Anderes Angebot',
          'status_label': 'Offen',
        },
      ],
      'invoices': [
        {
          'id': 'invoice-a',
          'number': 'RE-1',
          'title': 'Nur diese Rechnung',
          'status_label': 'Bezahlt',
          'total_gross': '120.50',
          'currency': 'EUR',
        },
      ],
    },
    'google_calendar': {
      'calendar': {'id': 'calendar-a', 'name': 'Baustellentermine'},
      'events': [
        {
          'id': 'event-a',
          'title': 'Aufmaß am Haus',
          'start': '2026-10-24',
          'end': '2026-10-25',
          'all_day': true,
          'status': 'confirmed',
        },
        {
          'id': 'event-b',
          'title': 'Nicht zuordnen',
          'start': '2026-10-25T09:00:00+02:00',
          'end': '2026-10-25T10:00:00+02:00',
          'all_day': false,
          'status': 'confirmed',
        },
      ],
    },
  };
  void connected(String provider) {
    status[provider]!.addAll({
      'configured': true,
      'connected': true,
      'state': 'connected',
    });
  }

  void logout() {
    token = null;
    notifyListeners();
  }

  void prepareOneDrive() {
    file = {
      'id': 'file-a',
      'drive_id': 'drive-a',
      'parent_id': 'folder-a',
      'name': 'Synthetischer Grundriss.pdf',
      'size': 1024,
      'web_url': 'https://example.sharepoint.com/sites/test/Grundriss.pdf',
    };
    candidates['onedrive'] = {
      'folder': {
        'id': 'folder-a',
        'drive_id': 'drive-a',
        'name': 'Projektordner',
      },
      'files': [file],
    };
    connected('onedrive');
    status['onedrive']!.addAll({
      'binding': {'drive_id': 'drive-a', 'folder_id': 'folder-a'},
      'revision': 1,
      'data': clone(candidates['onedrive']!),
    });
  }

  @override
  Future<dynamic> call(String path, [Map<String, dynamic>? body]) async {
    calls.add((path: path, body: body == null ? null : clone(body)));
    if (path == '/api/projects')
      return assigned
          ? [
              {'id': projectId},
            ]
          : [];
    if (old) throw const ApiException(404, 'Not available');
    if (path == '/api/integrations')
      return {
        'providers': status.values.map(clone).toList(),
        'capabilities': ['business_integrations'],
      };
    if (path == '/api/projects/$projectId/integrations')
      return {
        'providers': status.values.map(clone).toList(),
        'financial_visible': true,
      };
    if (path == '/api/integrations/bot/connect') {
      if (botFailure != null)
        throw ApiException(
          botFailure!,
          'Der Schlüssel wurde bereits ausgegeben. Bei Bedarf ausdrücklich einen neuen erstellen.',
        );
      final id = body!['request_id'] as String;
      final result = botReceipts.putIfAbsent(
        id,
        () => {
          'token': 'SPIX_SYNTHETIC_NOT_A_REAL_SECRET',
          'expires_at': '2027-01-22T12:00:00Z',
          'providers': ['google_calendar', 'onedrive'],
          'instructions': integrationBotInstructions,
        },
      );
      for (final provider in ['google_calendar', 'onedrive'])
        status[provider]!.addAll({
          'configured': true,
          'method': 'bot',
          'connected': false,
          'state': 'awaiting_bot',
        });
      if (loseBotAck) {
        loseBotAck = false;
        throw const ApiException(0, 'Lost key receipt');
      }
      return clone(result);
    }
    if (path == '/api/integrations/bot/sync')
      return {'providers': status.values.map(clone).toList()};
    final provider = integrationNames.keys.firstWhere(
      (id) => path.contains('/$id/'),
    );
    if (path.endsWith('/configure')) {
      status[provider]!.addAll({'configured': true, 'method': 'oauth'});
      return clone(status[provider]!);
    }
    if (path.endsWith('/connect')) {
      if (provider == 'sevdesk') {
        connected(provider);
        return clone(status[provider]!);
      }
      return {
        'url': unsafeOAuth
            ? 'https://evil.example.test/authorize'
            : provider == 'google_calendar'
            ? 'https://accounts.google.com/o/oauth2/v2/auth?state=synthetic'
            : 'https://login.microsoftonline.com/oauth2/authorize?state=synthetic',
      };
    }
    if (path.endsWith('/catalog'))
      return {
        if (badCatalog)
          'items': 'invalid'
        else
          'items': provider == 'sevdesk'
              ? [
                  {'id': 'contact-a', 'name': 'Synthetischer Kontakt'},
                ]
              : provider == 'google_calendar'
              ? [
                  {'id': 'calendar-a', 'name': 'Baustellentermine'},
                ]
              : [
                  {
                    'id': 'folder-a',
                    'drive_id': 'drive-a',
                    'name': 'Projektordner A',
                    'path': '/Projekte/A',
                  },
                  {
                    'id': 'folder-a',
                    'drive_id': 'drive-b',
                    'name': 'Projektordner B',
                    'path': '/Projekte/B',
                  },
                ],
      };
    if (path.endsWith('/preview')) {
      if (previewPending)
        return {
          'pending': true,
          'job_id': 'synthetic-job',
          'generation': status[provider]!['generation'],
          'message': 'Der Bot liefert die Auswahl beim nächsten Lauf.',
        };
      if (provider == 'onedrive') {
        candidates[provider]!['folder']['drive_id'] = body!['drive_id'];
        for (final file in candidates[provider]!['files'])
          file['drive_id'] = body['drive_id'];
      }
      return {
        ...clone(candidates[provider]!),
        'generation': status[provider]!['generation'],
      };
    }
    if (path.endsWith('/link')) {
      final id = body!['request_id'] as String;
      if (!receipts.containsKey(id)) {
        final data = clone(candidates[provider]!);
        if (provider == 'sevdesk') {
          data['offers'] = (data['offers'] as List)
              .where((item) => (body['offer_ids'] as List).contains(item['id']))
              .toList();
          data['invoices'] = (data['invoices'] as List)
              .where(
                (item) => (body['invoice_ids'] as List).contains(item['id']),
              )
              .toList();
        }
        if (provider == 'google_calendar')
          data['events'] = (data['events'] as List)
              .where((item) => (body['event_ids'] as List).contains(item['id']))
              .toList();
        status[provider]!.addAll({
          'binding': {
            for (final entry in body.entries)
              if (!['request_id', 'revision'].contains(entry.key))
                entry.key: entry.value,
          },
          'data': data,
          'revision': 1,
        });
        receipts[id] = clone(status[provider]!);
      }
      if (loseAck) {
        loseAck = false;
        throw const ApiException(0, 'Lost acknowledgement');
      }
      return clone(receipts[id]!);
    }
    if (path.endsWith('/sync')) {
      if (syncFailure != null)
        throw ApiException(syncFailure!, 'Synthetic refresh failure');
      return clone(status[provider]!);
    }
    throw StateError('Unexpected synthetic request: $path');
  }

  @override
  Future<Uint8List> bytes(
    String path, {
    required String mediaType,
    int maxBytes = 20 * 1024 * 1024,
  }) async {
    throw StateError('OneDrive metadata must not download file bytes.');
  }
}

Future<void> until(WidgetTester tester, bool Function() condition) async {
  for (var i = 0; i < 1000; i++) {
    await tester.runAsync(
      () => Future<void>.delayed(const Duration(milliseconds: 5)),
    );
    await tester.pump(const Duration(milliseconds: 20));
    if (condition()) return;
  }
  fail('Synthetic integration operation did not complete.');
}

Future<void> mount(WidgetTester tester, Widget page) async {
  tester.view.physicalSize = const Size(390, 1000);
  tester.view.devicePixelRatio = 1;
  addTearDown(tester.view.resetPhysicalSize);
  addTearDown(tester.view.resetDevicePixelRatio);
  await tester.pumpWidget(MaterialApp(home: page));
  await tester.pumpAndSettle();
}

Future<void> tap(WidgetTester tester, Finder finder) async {
  if (finder.evaluate().isEmpty)
    await tester.scrollUntilVisible(finder, 250, maxScrolls: 20);
  await tester.ensureVisible(finder);
  await tester.pumpAndSettle();
  await tester.tap(finder);
  await tester.pumpAndSettle();
}

Finder field(String label) => find.byWidgetPredicate(
  (widget) => widget is TextField && widget.decoration?.labelText == label,
);
ProjectIntegrationsController controller(
  IntegrationsApi api, {
  String role = 'owner',
  bool offline = false,
}) => ProjectIntegrationsController(
  api: api,
  projectId: projectId,
  role: role,
  offlineMode: offline,
);
Future<void> panel(
  WidgetTester tester,
  ProjectIntegrationsController state,
  String provider,
) => mount(
  tester,
  Scaffold(
    body: SingleChildScrollView(
      child: ProjectIntegrationPanel(controller: state, provider: provider),
    ),
  ),
);

void main() {
  test('Google all-day exclusive end and cancellation are displayed without invented dates', () {
    expect(
      externalEventTime({
        'start': '2026-10-24',
        'end': '2026-10-25',
        'all_day': true,
      }),
      '24.10.2026 · Ganztägig',
    );
    expect(
      externalEventTime({
        'start': '2026-10-24',
        'end': '2026-10-27',
        'all_day': true,
      }),
      '24.10.2026 – 26.10.2026 · Ganztägig',
    );
    expect(
      externalEventTime({'status': 'cancelled', 'start': null, 'end': null}),
      'Abgesagt',
    );
  });
  testWidgets(
    'Nonowners, offline mode and offline grants never request integration setup',
    (tester) async {
      for (final mode in ['role', 'offline', 'grant']) {
        final api = IntegrationsApi();
        if (mode == 'grant') api.token = 'offline_synthetic';
        await mount(
          tester,
          IntegrationsPage(
            api: api,
            role: mode == 'role' ? 'technician' : 'owner',
            offlineMode: mode == 'offline',
          ),
        );
        expect(api.calls, isEmpty);
        final state = controller(api, offline: mode == 'offline');
        if (mode != 'role') {
          await state.refresh();
          expect(api.calls, isEmpty);
        }
        state.dispose();
        api.dispose();
      }
      expect(tester.takeException(), isNull);
    },
  );
  testWidgets(
    'Protected credentials are submitted once and OAuth does not invent a connected account',
    (tester) async {
      final api = IntegrationsApi();
      final opened = <Uri>[];
      await mount(
        tester,
        IntegrationsPage(
          api: api,
          role: 'owner',
          openExternal: (uri) async {
            opened.add(uri);
            return true;
          },
        ),
      );
      await tap(tester, find.text('Zugang hinterlegen'));
      final secret = field('Sevdesk API-Token');
      expect(tester.widget<TextField>(secret).obscureText, isTrue);
      await tester.enterText(secret, 'SYNTHETIC_NOT_A_REAL_TOKEN');
      await tap(tester, find.text('Geschützt speichern'));
      expect(find.text('SYNTHETIC_NOT_A_REAL_TOKEN'), findsNothing);
      expect(find.text('Verbunden'), findsOneWidget);
      expect(
        api.calls.where((c) => c.path == '/api/integrations/sevdesk/connect'),
        hasLength(1),
      );
      await tap(tester, find.text('Erweiterte Google-Direktverbindung'));
      await tap(tester, find.text('Anbieter einmalig einrichten').first);
      expect(
        find.text(
          'https://example.test/api/v1/integrations/google_calendar/callback',
        ),
        findsOneWidget,
      );
      await tester.enterText(field('Google Client-ID'), 'synthetic-client');
      await tester.enterText(field('Google Client-Secret'), 'SYNTHETIC_SECRET');
      await tap(tester, find.text('Geschützt speichern'));
      expect(find.text('SYNTHETIC_SECRET'), findsNothing);
      await tap(tester, find.text('Konto verbinden').first);
      expect(opened.single.host, 'accounts.google.com');
      expect(api.status['sevdesk']!['connected'], isTrue);
      expect(api.status['google_calendar']!['connected'], isFalse);
      expect(find.text('Nicht verbunden'), findsWidgets);
      api.unsafeOAuth = true;
      await tap(tester, find.text('Konto verbinden').first);
      expect(
        opened,
        hasLength(1),
        reason: 'Unexpected OAuth hosts must never open.',
      );
      expect(tester.takeException(), isNull);
      await tester.pumpWidget(const SizedBox());
      api.dispose();
    },
  );
  testWidgets('Old server is distinct from withdrawn project access', (
    tester,
  ) async {
    final api = IntegrationsApi()..old = true;
    await mount(tester, IntegrationsPage(api: api, role: 'owner'));
    expect(
      find.textContaining('nach dem nächsten Serverupdate'),
      findsOneWidget,
    );
    final state = controller(api);
    await state.refresh();
    expect(state.unavailable, isTrue);
    expect(state.blocked, isFalse);
    api.assigned = false;
    await state.refresh();
    expect(state.blocked, isTrue);
    expect(state.providers, isEmpty);
    state.dispose();
    await tester.pumpWidget(const SizedBox());
    api.dispose();
  });
  testWidgets(
    'Finance data stays hidden for project members and readonly for accountants',
    (tester) async {
      final api = IntegrationsApi()..connected('sevdesk');
      api.status['sevdesk']!.addAll({
        'binding': {'contact_id': 'contact-a'},
        'data': clone(api.candidates['sevdesk']!),
      });
      final member = controller(api, role: 'technician');
      await member.refresh();
      expect(member.providers.containsKey('sevdesk'), isFalse);
      await panel(tester, member, 'sevdesk');
      expect(find.textContaining('120.50'), findsNothing);
      await tester.pumpWidget(const SizedBox());
      member.dispose();
      final accountant = controller(api, role: 'accountant');
      await accountant.refresh();
      await panel(tester, accountant, 'sevdesk');
      expect(find.text('120.50 EUR · Brutto'), findsOneWidget);
      expect(find.text('Kontakt und Belege zuordnen'), findsNothing);
      expect(find.text('Zuordnung entfernen'), findsNothing);
      await tester.pumpWidget(const SizedBox());
      accountant.dispose();
      api.dispose();
    },
  );
  testWidgets(
    'Sevdesk links only checked documents and keeps the same request across a lost acknowledgement',
    (tester) async {
      final api = IntegrationsApi()
        ..connected('sevdesk')
        ..loseAck = true;
      final state = controller(api);
      await state.refresh();
      await panel(tester, state, 'sevdesk');
      await tap(tester, find.text('Kontakt und Belege zuordnen'));
      await tap(tester, find.byType(DropdownButtonFormField<String>));
      await tap(tester, find.text('Synthetischer Kontakt').last);
      await tap(tester, find.text('Inhalte anzeigen'));
      final boxes = tester.widgetList<CheckboxListTile>(
        find.byType(CheckboxListTile),
      );
      expect(boxes.every((box) => box.value == false), isTrue);
      await tap(
        tester,
        find.widgetWithText(CheckboxListTile, 'Nur dieses Angebot'),
      );
      await tap(
        tester,
        find.widgetWithText(CheckboxListTile, 'Nur diese Rechnung'),
      );
      await tap(tester, find.text('Auswahl zuordnen'));
      expect(find.textContaining('Die Antwort ist offen'), findsOneWidget);
      await tap(tester, find.text('Erneut zuordnen'));
      final writes = api.calls
          .where((c) => c.path.endsWith('/sevdesk/link'))
          .toList();
      expect(writes, hasLength(2));
      expect(writes[0].body, writes[1].body);
      expect(writes[0].body!['offer_ids'], ['offer-a']);
      expect(writes[0].body!['invoice_ids'], ['invoice-a']);
      expect(find.text('Anderes Angebot'), findsNothing);
      expect(api.receipts, hasLength(1));
      expect(tester.takeException(), isNull);
      await tester.pumpWidget(const SizedBox());
      state.dispose();
      api.dispose();
    },
  );
  testWidgets(
    'Automatic read refresh keeps the confirmed cache and throttles failed provider attempts',
    (tester) async {
      final api = IntegrationsApi()
        ..connected('sevdesk')
        ..syncFailure = 429;
      api.status['sevdesk']!.addAll({
        'binding': {'contact_id': 'contact-a'},
        'data': clone(api.candidates['sevdesk']!),
      });
      var now = DateTime.utc(2026, 10, 24, 12);
      final state = ProjectIntegrationsController(
        api: api,
        projectId: projectId,
        role: 'accountant',
        clock: () => now,
      );
      await state.refresh();
      await until(tester, () => !state.autoSyncRunning);
      expect(
        api.calls.where((c) => c.path.endsWith('/sevdesk/sync')),
        hasLength(1),
      );
      await panel(tester, state, 'sevdesk');
      expect(find.text('120.50 EUR · Brutto'), findsOneWidget);
      expect(find.textContaining('Letzter bestätigter Stand.'), findsOneWidget);
      await state.refresh();
      state.didChangeAppLifecycleState(AppLifecycleState.resumed);
      await until(tester, () => !state.loading && !state.autoSyncRunning);
      expect(
        api.calls.where((c) => c.path.endsWith('/sevdesk/sync')),
        hasLength(1),
      );
      now = now.add(const Duration(minutes: 5));
      await state.refresh();
      await until(tester, () => !state.autoSyncRunning);
      expect(
        api.calls.where((c) => c.path.endsWith('/sevdesk/sync')),
        hasLength(2),
      );
      await tester.pumpWidget(const SizedBox());
      state.dispose();
      api.dispose();
    },
  );

  testWidgets(
    'Google project linking chooses individual events without creating calendar entries',
    (tester) async {
      final api = IntegrationsApi()..connected('google_calendar');
      final state = controller(api);
      await state.refresh();
      await panel(tester, state, 'google_calendar');
      await tap(tester, find.text('Kalender und Termine zuordnen'));
      await tap(tester, find.byType(DropdownButtonFormField<String>));
      await tap(tester, find.text('Baustellentermine').last);
      await tap(tester, find.text('Inhalte anzeigen'));
      expect(
        find.textContaining('Vom vorhandenen Bot bestätigte Termine'),
        findsOneWidget,
      );
      expect(
        tester
            .widgetList<CheckboxListTile>(find.byType(CheckboxListTile))
            .every((row) => row.value == false),
        isTrue,
      );
      await tap(
        tester,
        find.widgetWithText(CheckboxListTile, 'Aufmaß am Haus'),
      );
      await tap(tester, find.text('Auswahl zuordnen'));
      final write = api.calls
          .singleWhere((c) => c.path.endsWith('/google_calendar/link'))
          .body!;
      expect(write['calendar_id'], 'calendar-a');
      expect(write['event_ids'], ['event-a']);
      expect(find.text('Aufmaß am Haus'), findsOneWidget);
      expect(find.text('Nicht zuordnen'), findsNothing);
      expect(api.calls.where((c) => c.path.contains('/events')), isEmpty);
      expect(tester.takeException(), isNull);
      await tester.pumpWidget(const SizedBox());
      state.dispose();
      api.dispose();
    },
  );
  testWidgets(
    'OneDrive opens only the authenticated Microsoft file address after a click',
    (tester) async {
      final api = IntegrationsApi()..prepareOneDrive();
      final state = controller(api);
      await state.refresh();
      final opened = <Uri>[];
      await mount(
        tester,
        Scaffold(
          body: SingleChildScrollView(
            child: ProjectIntegrationPanel(
              controller: state,
              provider: 'onedrive',
              openExternal: (uri) async {
                opened.add(uri);
                return true;
              },
            ),
          ),
        ),
      );
      expect(opened, isEmpty);
      await tap(tester, find.text('In OneDrive öffnen'));
      expect(opened.single.host, 'example.sharepoint.com');
      expect(
        api.calls.where((call) => call.path.endsWith('/content')),
        isEmpty,
      );
      api.logout();
      await tester.pumpAndSettle();
      expect(find.text('In OneDrive öffnen'), findsNothing);
      expect(opened, hasLength(1));
      await tester.pumpWidget(const SizedBox());
      state.dispose();
      api.dispose();
    },
  );
  test('OneDrive rejects insecure or unrelated file addresses', () {
    expect(
      oneDriveWebUri('https://example.sharepoint.com/sites/project/file.pdf'),
      isNotNull,
    );
    expect(
      oneDriveWebUri('https://onedrive.live.com/?id=synthetic'),
      isNotNull,
    );
    expect(oneDriveWebUri('http://example.sharepoint.com/file'), isNull);
    expect(
      oneDriveWebUri('https://example.sharepoint.com.evil.test/file'),
      isNull,
    );
    expect(
      oneDriveWebUri('https://user:secret@example.sharepoint.com/file'),
      isNull,
    );
    expect(oneDriveWebUri('https://evil.test/file'), isNull);
  });
  testWidgets(
    'Changing the account generation clears an already open document selection',
    (tester) async {
      final api = IntegrationsApi()..connected('sevdesk');
      final state = controller(api);
      await state.refresh();
      await panel(tester, state, 'sevdesk');
      await tap(tester, find.text('Kontakt und Belege zuordnen'));
      await tap(tester, find.byType(DropdownButtonFormField<String>));
      await tap(tester, find.text('Synthetischer Kontakt').last);
      await tap(tester, find.text('Inhalte anzeigen'));
      expect(find.text('Nur dieses Angebot'), findsOneWidget);
      api.status['sevdesk']!['generation'] = 2;
      await state.refresh();
      await tester.pumpAndSettle();
      expect(find.text('Nur dieses Angebot'), findsNothing);
      expect(
        find.textContaining('Verbindung wurde inzwischen geändert'),
        findsOneWidget,
      );
      expect(api.calls.where((call) => call.path.endsWith('/link')), isEmpty);
      expect(tester.takeException(), isNull);
      await tester.pumpWidget(const SizedBox());
      state.dispose();
      api.dispose();
    },
  );
  testWidgets(
    'One protected bot key reuses its request after a lost reply and never implies connected catalogs',
    (tester) async {
      final api = IntegrationsApi()..loseBotAck = true;
      final copied = <String>[];
      tester.binding.defaultBinaryMessenger.setMockMethodCallHandler(
        SystemChannels.platform,
        (call) async {
          if (call.method == 'Clipboard.setData')
            copied.add(call.arguments['text'] as String);
          return null;
        },
      );
      addTearDown(
        () => tester.binding.defaultBinaryMessenger.setMockMethodCallHandler(
          SystemChannels.platform,
          null,
        ),
      );
      await mount(tester, IntegrationsPage(api: api, role: 'owner'));
      await tap(tester, find.text('Bot verbinden'));
      expect(
        find.descendant(
          of: find.byKey(const ValueKey('integration-bot-card')),
          matching: find.textContaining('Antwort noch nicht bestätigt'),
        ),
        findsOneWidget,
      );
      await tap(tester, find.text('Schlüssel erneut anfordern'));
      expect(find.text('SPIX_SYNTHETIC_NOT_A_REAL_SECRET'), findsOneWidget);
      expect(copied, isEmpty);
      await tap(tester, find.text('Schlüssel kopieren'));
      expect(copied.single, 'SPIX_SYNTHETIC_NOT_A_REAL_SECRET');
      await tap(tester, find.text('Fertig'));
      expect(find.text('SPIX_SYNTHETIC_NOT_A_REAL_SECRET'), findsNothing);
      final requests = api.calls
          .where((call) => call.path.endsWith('/bot/connect'))
          .toList();
      expect(requests, hasLength(2));
      expect(requests.first.body, requests.last.body);
      expect(api.botReceipts, hasLength(1));
      expect(api.status['google_calendar']!['connected'], isFalse);
      expect(api.status['onedrive']!['connected'], isFalse);
      await tap(tester, find.text('Botauftrag kopieren'));
      expect(copied.last, contains('vorhandenen Fünfminutenjob'));
      expect(copied.last, contains('SMARTPLAN_INTAKE_TOKEN'));
      expect(copied.last, isNot(contains('SPIX_SYNTHETIC_NOT_A_REAL_SECRET')));
      await tap(tester, find.text('Daten anfordern'));
      expect(
        api.calls.where((call) => call.path.endsWith('/bot/sync')),
        hasLength(1),
      );
      expect(tester.takeException(), isNull);
      await tester.pumpWidget(const SizedBox());
      api.dispose();
    },
  );
  testWidgets(
    'Pending bot previews remain explicit and retry the same resource without linking empty data',
    (tester) async {
      final api = IntegrationsApi()
        ..connected('google_calendar')
        ..previewPending = true;
      final state = controller(api);
      await state.refresh();
      await panel(tester, state, 'google_calendar');
      await tap(tester, find.text('Kalender und Termine zuordnen'));
      await tap(tester, find.byType(DropdownButtonFormField<String>));
      await tap(tester, find.text('Baustellentermine').last);
      await tap(tester, find.text('Inhalte anzeigen'));
      expect(
        find.text('Der Bot liefert die Auswahl beim nächsten Lauf.'),
        findsOneWidget,
      );
      expect(
        tester
            .widget<FilledButton>(
              find.widgetWithText(FilledButton, 'Auswahl zuordnen'),
            )
            .onPressed,
        isNull,
      );
      await tap(tester, find.text('Auswahl erneut laden'));
      final previews = api.calls
          .where((call) => call.path.endsWith('/preview'))
          .toList();
      expect(previews, hasLength(2));
      expect(previews.first.body, previews.last.body);
      expect(api.calls.where((call) => call.path.endsWith('/link')), isEmpty);
      expect(find.text('Keine Einträge verfügbar.'), findsNothing);
      await tester.pumpWidget(const SizedBox());
      state.dispose();
      api.dispose();
    },
  );
  testWidgets(
    'OneDrive explicitly sends both drive and folder IDs even when folder IDs coincide',
    (tester) async {
      final api = IntegrationsApi()..prepareOneDrive();
      final state = controller(api);
      await state.refresh();
      await panel(tester, state, 'onedrive');
      await tap(tester, find.text('Ordner zuordnen'));
      await tap(tester, find.byType(DropdownButtonFormField<String>));
      await tap(tester, find.textContaining('Projektordner B').last);
      await tap(tester, find.text('Inhalte anzeigen'));
      final preview = api.calls
          .singleWhere((call) => call.path.endsWith('/onedrive/preview'))
          .body!;
      expect(preview['drive_id'], 'drive-b');
      expect(preview['folder_id'], 'folder-a');
      expect(preview['generation'], 1);
      await tap(tester, find.text('Auswahl zuordnen'));
      final link = api.calls
          .singleWhere((call) => call.path.endsWith('/onedrive/link'))
          .body!;
      expect(link['drive_id'], 'drive-b');
      expect(link['folder_id'], 'folder-a');
      expect(link['generation'], 1);
      expect(tester.takeException(), isNull);
      await tester.pumpWidget(const SizedBox());
      state.dispose();
      api.dispose();
    },
  );
  testWidgets(
    'An expired bot bootstrap can be replaced explicitly instead of retrying its dead request forever',
    (tester) async {
      final api = IntegrationsApi()..loseBotAck = true;
      await mount(tester, IntegrationsPage(api: api, role: 'owner'));
      await tap(tester, find.text('Bot verbinden'));
      api.botFailure = 409;
      await tap(tester, find.text('Schlüssel erneut anfordern'));
      expect(find.text('Schlüssel erneut anfordern'), findsNothing);
      expect(find.text('Bot verbinden'), findsOneWidget);
      api.botFailure = null;
      await tap(tester, find.text('Bot verbinden'));
      expect(find.text('Integrationsschlüssel erneuern?'), findsOneWidget);
      await tap(tester, find.text('Schlüssel erneuern'));
      expect(find.text('SPIX_SYNTHETIC_NOT_A_REAL_SECRET'), findsOneWidget);
      final requests = api.calls
          .where((call) => call.path.endsWith('/bot/connect'))
          .toList();
      expect(requests, hasLength(3));
      expect(requests[0].body, requests[1].body);
      expect(
        requests[2].body!['request_id'],
        isNot(requests[0].body!['request_id']),
      );
      await tap(tester, find.text('Fertig'));
      await tester.pumpWidget(const SizedBox());
      api.dispose();
    },
  );
  testWidgets(
    'Malformed provider catalogs show a readable failure and never become a confirmed empty selection',
    (tester) async {
      final api = IntegrationsApi()
        ..connected('sevdesk')
        ..badCatalog = true;
      final state = controller(api);
      await state.refresh();
      await panel(tester, state, 'sevdesk');
      await tap(tester, find.text('Kontakt und Belege zuordnen'));
      expect(
        find.text('Die Anbieterliste konnte nicht gelesen werden.'),
        findsOneWidget,
      );
      expect(find.byType(CheckboxListTile), findsNothing);
      expect(
        tester
            .widget<FilledButton>(
              find.widgetWithText(FilledButton, 'Auswahl zuordnen'),
            )
            .onPressed,
        isNull,
      );
      expect(api.calls.where((call) => call.path.endsWith('/link')), isEmpty);
      await tester.pumpWidget(const SizedBox());
      state.dispose();
      api.dispose();
    },
  );
}

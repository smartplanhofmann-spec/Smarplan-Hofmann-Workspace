import 'dart:async';
import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:smartplan_office/api.dart';
import 'package:smartplan_office/main.dart';

import 'administration_return_navigation_test.dart' show AdministrationApi;

class CreateApi extends AdministrationApi {
  bool receipts = true;
  bool created = false;
  int capabilityReads = 0;
  Completer<dynamic>? heldCapabilities;
  String server = 'https://first.example.test';
  String apiVersion = 'v1';
  @override
  String get base => server;
  @override
  String get version => apiVersion;
  final posts = <Map<String, dynamic>>[];
  int customerReads = 0, projectReads = 0;
  Object? rejectNext;
  Completer<dynamic>? heldPost, heldCustomers;
  static const customer = 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa';
  static const project = 'bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb';

  void changed({bool notify = true}) {
    if (notify) notifyListeners();
  }

  @override
  Future<dynamic> call(String path, [Map<String, dynamic>? body]) async {
    if (path.split('?').first == '/api/business/capabilities') {
      capabilityReads++;
      if (heldCapabilities != null) return heldCapabilities!.future;
      return {
        'storage_version': 7,
        'compatibility_mode': 'business',
        'generation': 1,
        'capabilities': ['business_foundation'],
        'permissions': <String>[],
        'features': [if (receipts) 'project_creation_receipts'],
      };
    }
    if (path == '/api/customers') {
      customerReads++;
      return heldCustomers?.future ??
          [
            {
              'id': customer,
              'name': 'Bestehender Kunde',
              'address': 'Testweg 1',
              'active': 1,
            },
          ];
    }
    if (path == '/api/projects' && body != null) {
      posts.add(Map<String, dynamic>.from(jsonDecode(jsonEncode(body)) as Map));
      if (heldPost != null) return heldPost!.future;
      final error = rejectNext;
      rejectNext = null;
      if (error != null) throw error;
      created = true;
      return {'id': project};
    }
    if (path == '/api/projects') {
      projectReads++;
      if (created)
        return [
          {
            'id': project,
            'name': posts.last['name'],
            'customer': 'Bestehender Kunde',
          },
        ];
    }
    return super.call(path, body);
  }
}

Future<void> login(WidgetTester tester, CreateApi api) async {
  tester.view.devicePixelRatio = 1;
  tester.view.physicalSize = const Size(1200, 900);
  addTearDown(tester.view.resetPhysicalSize);
  addTearDown(tester.view.resetDevicePixelRatio);
  await tester.pumpWidget(OfficeApp(api: api));
  await tester.enterText(
    find.byType(TextFormField).at(0),
    'owner@example.test',
  );
  await tester.enterText(
    find.byType(TextFormField).at(1),
    'Synthetic-password-123',
  );
  await tester.tap(find.text('Anmelden'));
  await tester.pumpAndSettle();
  await tester.tap(find.text('Weitere Verwaltung'));
  await tester.pumpAndSettle();
}

Future<void> openCreate(WidgetTester tester) async {
  await tester.tap(find.widgetWithText(FilledButton, 'Projekt anlegen'));
  await tester.pumpAndSettle();
}

Future<void> enterProject(WidgetTester tester) async {
  await openCreate(tester);
  await tester.enterText(
    find.byType(TextFormField).first,
    'Synthetische Montage',
  );
  await tester.tap(find.byType(DropdownButtonFormField<String>));
  await tester.pumpAndSettle();
  await tester.tap(find.textContaining('Bestehender Kunde').last);
  await tester.pumpAndSettle();
}

Future<void> send(
  WidgetTester tester, {
  String label = 'Anlegen',
  bool settle = true,
}) async {
  await tester.tap(find.widgetWithText(FilledButton, label));
  if (settle) {
    await tester.pumpAndSettle();
  } else {
    for (var i = 0; i < 4; i++)
      await tester.pump(const Duration(milliseconds: 30));
  }
}

void main() {
  setUpAll(() async {
    await (FontLoader(
      'Inter',
    )..addFont(rootBundle.load('assets/fonts/Inter.ttf'))).load();
    await (FontLoader(
      'MaterialIcons',
    )..addFont(rootBundle.load('fonts/MaterialIcons-Regular.otf'))).load();
  });

  testWidgets(
    'Uncertain create retains the exact original body and retries its request id',
    (tester) async {
      final api = CreateApi()
        ..rejectNext = const ApiException(0, 'Synthetic lost response');
      try {
        await login(tester, api);
        await enterProject(tester);
        await send(tester);
        expect(find.byType(ProjectDialog), findsOneWidget);
        expect(
          tester
              .widget<TextFormField>(find.byType(TextFormField).first)
              .enabled,
          isFalse,
        );
        final original = api.posts.single;
        expect(original['request_id'], matches(RegExp(r'^[a-f0-9]{32}$')));
        expect(original['customer_id'], CreateApi.customer);
        expect(original.containsKey('customer'), isFalse);
        await send(tester, label: 'Erneut versuchen');
        expect(api.posts, hasLength(2));
        expect(api.posts.last, original);
        expect(find.text('Synthetische Montage'), findsOneWidget);
        expect(find.byType(ProjectDialog), findsNothing);
        expect(tester.takeException(), isNull);
      } finally {
        await tester.pumpWidget(const SizedBox());
        api.dispose();
      }
    },
  );

  testWidgets(
    'Closing and reopening an uncertain create keeps its body and selected customer',
    (tester) async {
      final api = CreateApi()
        ..rejectNext = const ApiException(0, 'Synthetic lost response');
      try {
        await login(tester, api);
        await enterProject(tester);
        await send(tester);
        await tester.tap(find.text('Später fortsetzen'));
        await tester.pumpAndSettle();
        final reads = api.customerReads;
        await openCreate(tester);
        expect(api.customerReads, reads);
        expect(
          tester
              .widget<TextFormField>(find.byType(TextFormField).first)
              .controller!
              .text,
          'Synthetische Montage',
        );
        await send(tester, label: 'Erneut versuchen');
        expect(api.posts.last, api.posts.first);
        expect(tester.takeException(), isNull);
      } finally {
        await tester.pumpWidget(const SizedBox());
        api.dispose();
      }
    },
  );

  for (final change in ['token', 'server', 'version']) {
    testWidgets(
      'A $change change drops an in-flight create result without refreshing the new context',
      (tester) async {
        final api = CreateApi()..heldPost = Completer<dynamic>();
        try {
          await login(tester, api);
          await enterProject(tester);
          await send(tester, settle: false);
          expect(api.posts, hasLength(1));
          final reads = api.projectReads;
          switch (change) {
            case 'token':
              api.token = 'different-account-session';
            case 'server':
              api.server = 'https://second.example.test';
            case 'version':
              api.apiVersion = '';
          }
          api.changed();
          await tester.pumpAndSettle();
          expect(find.byType(ProjectDialog), findsNothing);
          api.heldPost!.complete({'id': CreateApi.project});
          await tester.pumpAndSettle();
          expect(api.projectReads, reads);
          expect(api.posts, hasLength(1));
          expect(tester.takeException(), isNull);
        } finally {
          if (!api.heldPost!.isCompleted)
            api.heldPost!.complete({'id': CreateApi.project});
          await tester.pumpWidget(const SizedBox());
          api.dispose();
        }
      },
    );
  }

  testWidgets('Quiet context change cannot reuse an old retry callback', (
    tester,
  ) async {
    final api = CreateApi()
      ..rejectNext = const ApiException(0, 'Synthetic lost response');
    try {
      await login(tester, api);
      await enterProject(tester);
      await send(tester);
      final retry = tester
          .widget<FilledButton>(
            find.widgetWithText(FilledButton, 'Erneut versuchen'),
          )
          .onPressed!;
      api.server = 'https://second.example.test';
      retry();
      await tester.pumpAndSettle();
      expect(api.posts, hasLength(1));
      expect(find.byType(ProjectDialog), findsNothing);
      retry();
      await tester.pumpAndSettle();
      expect(api.posts, hasLength(1));
      expect(tester.takeException(), isNull);
    } finally {
      await tester.pumpWidget(const SizedBox());
      api.dispose();
    }
  });

  testWidgets(
    'API replacement closes only the stale project dialog and sends nothing to either server',
    (tester) async {
      final api = CreateApi();
      final replacement = CreateApi()..server = 'https://second.example.test';
      try {
        await login(tester, api);
        await enterProject(tester);
        final submit = tester
            .widget<FilledButton>(find.widgetWithText(FilledButton, 'Anlegen'))
            .onPressed!;
        await tester.pumpWidget(OfficeApp(api: replacement));
        await tester.pumpAndSettle();
        expect(find.byType(ProjectDialog), findsNothing);
        submit();
        await tester.pumpAndSettle();
        expect(api.posts, isEmpty);
        expect(replacement.posts, isEmpty);
        expect(tester.takeException(), isNull);
      } finally {
        await tester.pumpWidget(const SizedBox());
        api.dispose();
        replacement.dispose();
      }
    },
  );

  testWidgets('A late customer list cannot open a form after a server switch', (
    tester,
  ) async {
    final api = CreateApi()..heldCustomers = Completer<dynamic>();
    try {
      await login(tester, api);
      await tester.tap(find.widgetWithText(FilledButton, 'Projekt anlegen'));
      await tester.pump();
      api.server = 'https://second.example.test';
      api.changed();
      api.heldCustomers!.complete([]);
      await tester.pumpAndSettle();
      expect(find.byType(ProjectDialog), findsNothing);
      expect(api.posts, isEmpty);
      expect(tester.takeException(), isNull);
    } finally {
      if (!api.heldCustomers!.isCompleted) api.heldCustomers!.complete([]);
      await tester.pumpWidget(const SizedBox());
      api.dispose();
    }
  });

  testWidgets(
    'An old server permits first creation but no uncertain repeat and local resolution makes no POST',
    (tester) async {
      final api = CreateApi()
        ..receipts = false
        ..rejectNext = const ApiException(0, 'Synthetic lost response');
      try {
        await login(tester, api);
        await enterProject(tester);
        await send(tester);
        expect(api.posts, hasLength(1));
        expect(
          find.textContaining('noch keine sichere Wiederholung'),
          findsOneWidget,
        );
        expect(
          tester
              .widget<FilledButton>(
                find.widgetWithText(FilledButton, 'Erneut versuchen'),
              )
              .onPressed,
          isNull,
        );
        final reads = api.projectReads;
        await tester.tap(find.text('Projektliste prüfen'));
        await tester.pumpAndSettle();
        expect(api.projectReads, greaterThan(reads));
        await openCreate(tester);
        expect(
          tester
              .widget<FilledButton>(
                find.widgetWithText(FilledButton, 'Erneut versuchen'),
              )
              .onPressed,
          isNull,
        );
        await tester.tap(find.text('Als geprüft abschließen'));
        await tester.pumpAndSettle();
        await tester.tap(find.text('Vorgang als geprüft schließen'));
        await tester.pumpAndSettle();
        expect(api.posts, hasLength(1));
        await openCreate(tester);
        expect(
          tester
              .widget<TextFormField>(find.byType(TextFormField).first)
              .controller!
              .text,
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
    'A definite rejection preserves editable input and a corrected command receives a new request id',
    (tester) async {
      final api = CreateApi()
        ..rejectNext = const ApiException(400, 'Synthetic rejected name');
      try {
        await login(tester, api);
        await enterProject(tester);
        await send(tester);
        expect(
          tester
              .widget<TextFormField>(find.byType(TextFormField).first)
              .enabled,
          isTrue,
        );
        await tester.enterText(
          find.byType(TextFormField).first,
          'Korrigierter Projektname',
        );
        await send(tester);
        expect(
          api.posts.last['request_id'],
          isNot(api.posts.first['request_id']),
        );
        expect(api.posts.last['name'], 'Korrigierter Projektname');
        expect(find.byType(ProjectDialog), findsNothing);
        expect(tester.takeException(), isNull);
      } finally {
        await tester.pumpWidget(const SizedBox());
        api.dispose();
      }
    },
  );
  testWidgets(
    'Removing the receipt feature before retry prevents a second POST',
    (tester) async {
      final api = CreateApi()
        ..rejectNext = const ApiException(0, 'Synthetic lost response');
      try {
        await login(tester, api);
        await enterProject(tester);
        await send(tester);
        final reads = api.capabilityReads;
        api.receipts = false;
        await send(tester, label: 'Erneut versuchen');
        expect(api.capabilityReads, greaterThan(reads));
        expect(api.posts, hasLength(1));
        expect(
          find.textContaining('noch keine sichere Wiederholung'),
          findsOneWidget,
        );
        expect(
          tester
              .widget<FilledButton>(
                find.widgetWithText(FilledButton, 'Erneut versuchen'),
              )
              .onPressed,
          isNull,
        );
        expect(tester.takeException(), isNull);
      } finally {
        await tester.pumpWidget(const SizedBox());
        api.dispose();
      }
    },
  );

  testWidgets('A context switch during retry preflight prevents its POST', (
    tester,
  ) async {
    final api = CreateApi()
      ..rejectNext = const ApiException(0, 'Synthetic lost response');
    try {
      await login(tester, api);
      await enterProject(tester);
      await send(tester);
      api.heldCapabilities = Completer<dynamic>();
      await send(tester, label: 'Erneut versuchen', settle: false);
      api.server = 'https://second.example.test';
      api.changed();
      api.heldCapabilities!.complete({
        'storage_version': 7,
        'compatibility_mode': 'business',
        'generation': 1,
        'capabilities': ['business_foundation'],
        'permissions': <String>[],
        'features': ['project_creation_receipts'],
      });
      await tester.pumpAndSettle();
      expect(api.posts, hasLength(1));
      expect(find.byType(ProjectDialog), findsNothing);
      expect(tester.takeException(), isNull);
    } finally {
      if (api.heldCapabilities?.isCompleted == false)
        api.heldCapabilities!.complete({});
      await tester.pumpWidget(const SizedBox());
      api.dispose();
    }
  });
  testWidgets(
    'Returning to the same token cannot revive an older create operation',
    (tester) async {
      final first = Completer<dynamic>();
      final api = CreateApi()..heldPost = first;
      try {
        await login(tester, api);
        await enterProject(tester);
        await send(tester, settle: false);
        final token = api.token;
        api.token = 'different-session';
        api.changed();
        await tester.pumpAndSettle();
        api.token = token;
        api.changed();
        api.heldPost = null;
        await openCreate(tester);
        // Restoring a token string does not restore the revoked authenticated
        // business context. A real new login is required before another create.
        expect(find.byType(ProjectDialog), findsNothing);
        expect(api.posts, hasLength(1));
        final reads = api.projectReads;
        first.complete({'id': CreateApi.project});
        await tester.pumpAndSettle();
        expect(api.projectReads, reads);
        expect(find.byType(ProjectDialog), findsNothing);
        expect(tester.takeException(), isNull);
      } finally {
        if (!first.isCompleted) first.complete({'id': CreateApi.project});
        await tester.pumpWidget(const SizedBox());
        api.dispose();
      }
    },
  );
  testWidgets(
    'A denied retry does not discard an originally uncertain command',
    (tester) async {
      final api = CreateApi()
        ..rejectNext = const ApiException(0, 'Synthetic lost response');
      try {
        await login(tester, api);
        await enterProject(tester);
        await send(tester);
        api.rejectNext = const ApiException(
          403,
          'Synthetic permission revoked after original submit',
        );
        await send(tester, label: 'Erneut versuchen');
        expect(
          tester
              .widget<TextFormField>(find.byType(TextFormField).first)
              .enabled,
          isFalse,
        );
        expect(api.posts.last, api.posts.first);
        await tester.tap(find.text('Später fortsetzen'));
        await tester.pumpAndSettle();
        await openCreate(tester);
        await send(tester, label: 'Erneut versuchen');
        expect(api.posts, hasLength(3));
        expect(api.posts.last, api.posts.first);
        expect(find.byType(ProjectDialog), findsNothing);
        expect(tester.takeException(), isNull);
      } finally {
        await tester.pumpWidget(const SizedBox());
        api.dispose();
      }
    },
  );
  testWidgets(
    'A detached workspace create callback performs no read or write',
    (tester) async {
      final api = CreateApi();
      try {
        await login(tester, api);
        final create = tester
            .widget<FilledButton>(
              find.widgetWithText(FilledButton, 'Projekt anlegen'),
            )
            .onPressed!;
        await tester.pumpWidget(const SizedBox());
        create();
        await tester.pump();
        expect(api.customerReads, 0);
        expect(api.posts, isEmpty);
        expect(tester.takeException(), isNull);
      } finally {
        await tester.pumpWidget(const SizedBox());
        api.dispose();
      }
    },
  );
}

import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:smartplan_office/api.dart';
import 'package:smartplan_office/business_resource_custody.dart';
import 'package:smartplan_office/business_service.dart';
import 'package:smartplan_office/business_session.dart';
import 'package:smartplan_office/business_widgets.dart';

Map<String, dynamic> fixture() => jsonDecode(
  File('test/fixtures/service_equipment_native_review_2026.json')
      .readAsStringSync(),
) as Map<String, dynamic>;

class ActualServiceEquipmentApi extends OfficeApi {
  ActualServiceEquipmentApi({this.empty = false}) : super(apiVersion: 'v1') {
    token = empty ? 'synthetic-second-context' : 'synthetic-original-context';
  }
  final bool empty;
  final f = fixture();
  String? holdOn;
  bool denied = false, failHeld = false;
  Completer<void>? release;
  final started = Completer<void>();
  final posts = <Map<String, dynamic>>[];
  @override
  Future<dynamic> call(String path, [Map<String, dynamic>? body]) async {
    if (body != null) {
      posts.add(jsonDecode(jsonEncode(body)) as Map<String, dynamic>);
      throw const ApiException(0, 'Synthetic response unknown');
    }
    final response = answer(path);
    if (holdOn != null && Uri.parse(path).path.endsWith(holdOn!)) {
      holdOn = null;
      final gate = release = Completer<void>();
      if (!started.isCompleted) started.complete();
      await gate.future;
      if (failHeld) throw const ApiException(403, 'OLD-PRIVATE-ERROR');
    }
    return response;
  }

  dynamic answer(String path) {
    final uri = Uri.parse(path), p = uri.path;
    if (p.endsWith('/capabilities')) {
      final value =
          f[uri.queryParameters.containsKey('project_id')
              ? 'scoped_capabilities'
              : 'capabilities'];
      return denied ? {...value as Map, 'permissions': []} : value;
    }
    if (p == '/api/me') return f['actor'];
    final service = f['service'], custody = f['custody'];
    if (p.endsWith('/service/options')) return service['options'];
    if (p.endsWith('/service/cases')) {
      return empty
          ? {...service['listing'] as Map, 'items': []}
          : service['listing'];
    }
    if (p.endsWith('/service/cases/${service['item']['id']}/history'))
      return service['history'];
    if (p.endsWith('/service/cases/${service['item']['id']}'))
      return service['item'];
    if (p.endsWith('/resource-custody/options')) return custody['options'];
    if (p.endsWith('/resource-custody/${custody['item']['id']}/history'))
      return custody['history'];
    if (p.endsWith('/resource-custody/${custody['item']['id']}'))
      return custody['item'];
    if (p.endsWith('/resource-custody'))
      return empty ? {'items': []} : custody['listing'];
    throw StateError(path);
  }
}

void main() {
  for (final kind in ['service', 'custody']) {
    testWidgets(
      'actual $kind original is removed on allowed session replacement',
      (t) async {
        final api = ActualServiceEquipmentApi(),
            nextApi = ActualServiceEquipmentApi(empty: true);
        final session = BusinessSession(api: api),
            next = BusinessSession(api: nextApi);
        await session.load();
        expect(session.allowed, true);
        await t.binding.setSurfaceSize(const Size(1200, 1200));
        addTearDown(() => t.binding.setSurfaceSize(null));
        await next.load();
        final privateTitle = kind == 'service'
            ? api.f['service']['item']['title'] as String
            : api.f['custody']['item']['resource']['name'] as String;
        Widget page(BusinessSession s) => MaterialApp(
          home: kind == 'service'
              ? BusinessServicePage(session: s)
              : BusinessResourceCustodyPage(session: s),
        );
        try {
          await t.pumpWidget(page(session));
          await t.pumpAndSettle();
          expect(find.text(privateTitle), findsWidgets);
          await t.pumpWidget(page(next));
          await t.pumpAndSettle();
          expect(
            find.text(privateTitle),
            findsNothing,
            reason:
                'The replacement session has no corresponding visible record.',
          );
        } finally {
          await t.pumpWidget(const SizedBox());
          session.dispose();
          next.dispose();
          api.dispose();
          nextApi.dispose();
        }
      },
    );
    testWidgets('actual $kind original is cleared while backgrounded', (
      t,
    ) async {
      final api = ActualServiceEquipmentApi();
      final session = BusinessSession(api: api);
      await session.load();
      expect(session.allowed, true);
      await t.binding.setSurfaceSize(const Size(1200, 1200));
      addTearDown(() => t.binding.setSurfaceSize(null));
      final privateTitle = kind == 'service'
          ? api.f['service']['item']['title'] as String
          : api.f['custody']['item']['resource']['name'] as String;
      try {
        await t.pumpWidget(
          MaterialApp(
            home: kind == 'service'
                ? BusinessServicePage(session: session)
                : BusinessResourceCustodyPage(session: session),
          ),
        );
        await t.pumpAndSettle();
        expect(find.text(privateTitle), findsWidgets);
        t.binding.handleAppLifecycleStateChanged(AppLifecycleState.inactive);
        t.binding.handleAppLifecycleStateChanged(AppLifecycleState.hidden);
        t.binding.handleAppLifecycleStateChanged(AppLifecycleState.paused);
        t.binding.scheduleForcedFrame();
        await t.pump();
        expect(find.text(privateTitle), findsNothing);
      } finally {
        t.binding.handleAppLifecycleStateChanged(AppLifecycleState.hidden);
        t.binding.handleAppLifecycleStateChanged(AppLifecycleState.inactive);
        t.binding.handleAppLifecycleStateChanged(AppLifecycleState.resumed);
        await t.pumpWidget(const SizedBox());
        session.dispose();
        api.dispose();
      }
    });
    for (final change in [
      'session',
      'dispose',
      'background',
      'foreign_dialog',
    ]) {
      testWidgets(
        '$kind owned draft closes for $change and preserves unrelated routes',
        (t) async {
          final api = ActualServiceEquipmentApi(),
              nextApi = ActualServiceEquipmentApi(empty: true);
          final session = BusinessSession(api: api),
              next = BusinessSession(api: nextApi);
          await session.load();
          await next.load();
          await t.binding.setSurfaceSize(const Size(1200, 1200));
          addTearDown(() => t.binding.setSurfaceSize(null));
          Widget page(BusinessSession s) => kind == 'service'
              ? BusinessServicePage(session: s)
              : BusinessResourceCustodyPage(
                  session: s,
                  resourceId: api.f['custody']['item']['id'],
                );
          final host = ValueNotifier<Widget>(page(session));
          final nav = GlobalKey<NavigatorState>();
          try {
            await t.pumpWidget(
              MaterialApp(
                navigatorKey: nav,
                home: ValueListenableBuilder<Widget>(
                  valueListenable: host,
                  builder: (_, page, __) => page,
                ),
              ),
            );
            await t.pumpAndSettle();
            if (kind == 'service') {
              await t.tap(find.text(api.f['service']['item']['title']));
              await t.pumpAndSettle();
            }
            final trigger = find.text(
              kind == 'service'
                  ? 'Aktivität dokumentieren'
                  : 'Profil und Zustand',
            );
            await t.ensureVisible(trigger);
            await t.tap(trigger);
            await t.pumpAndSettle();
            expect(find.byType(BusinessEditor), findsOneWidget);
            await t.enterText(
              find.byType(TextFormField).last,
              'PRIVATE-CONTEXT-DRAFT',
            );
            if (change == 'foreign_dialog') {
              unawaited(
                showDialog<void>(
                  context: nav.currentContext!,
                  builder: (_) => const AlertDialog(
                    title: Text('Unrelated route stays open'),
                  ),
                ),
              );
              await t.pumpAndSettle();
            }
            if (change == 'session')
              host.value = page(next);
            else if (change == 'background') {
              t.binding.handleAppLifecycleStateChanged(
                AppLifecycleState.inactive,
              );
              t.binding.handleAppLifecycleStateChanged(
                AppLifecycleState.hidden,
              );
              t.binding.handleAppLifecycleStateChanged(
                AppLifecycleState.paused,
              );
              t.binding.scheduleForcedFrame();
            } else
              host.value = const Scaffold(body: Text('Replacement host'));
            await t.pump();
            if (change == 'background') {
              t.binding.handleAppLifecycleStateChanged(
                AppLifecycleState.hidden,
              );
              t.binding.handleAppLifecycleStateChanged(
                AppLifecycleState.inactive,
              );
              t.binding.handleAppLifecycleStateChanged(
                AppLifecycleState.resumed,
              );
            }
            await t.pumpAndSettle();
            expect(
              find.byType(BusinessEditor, skipOffstage: false),
              findsNothing,
            );
            expect(
              find.text('PRIVATE-CONTEXT-DRAFT', skipOffstage: false),
              findsNothing,
            );
            if (change == 'foreign_dialog')
              expect(find.text('Unrelated route stays open'), findsOneWidget);
          } finally {
            await t.pumpWidget(const SizedBox());
            host.dispose();
            session.dispose();
            next.dispose();
            api.dispose();
            nextApi.dispose();
          }
        },
      );
    }
    for (final outcome in ['reply', 'error', 'silent_revocation']) {
      testWidgets(
        '$kind held original $outcome cannot populate a superseded or revoked view',
        (t) async {
          final api = ActualServiceEquipmentApi(),
              nextApi = ActualServiceEquipmentApi(empty: true);
          final session = BusinessSession(api: api),
              next = BusinessSession(api: nextApi);
          await session.load();
          await next.load();
          api.holdOn = kind == 'service'
              ? '/service/cases'
              : '/resource-custody';
          api.failHeld = outcome == 'error';
          Widget page(BusinessSession s) => MaterialApp(
            home: kind == 'service'
                ? BusinessServicePage(session: s)
                : BusinessResourceCustodyPage(session: s),
          );
          try {
            await t.pumpWidget(page(session));
            await t.pump();
            expect(api.release, isNotNull);
            if (outcome == 'silent_revocation')
              api.denied = true;
            else
              await t.pumpWidget(page(next));
            api.release!.complete();
            await t.pumpAndSettle();
            expect(find.text(api.f['service']['item']['title']), findsNothing);
            expect(
              find.text(api.f['custody']['item']['resource']['name']),
              findsNothing,
            );
            expect(find.textContaining('OLD-PRIVATE-ERROR'), findsNothing);
          } finally {
            await t.pumpWidget(const SizedBox());
            session.dispose();
            next.dispose();
            api.dispose();
            nextApi.dispose();
          }
        },
      );
    }
    test(
      '$kind pending preflight cannot post after originating view closes',
      () async {
        final api = ActualServiceEquipmentApi(),
            session = BusinessSession(api: ActualServiceEquipmentApi());
        final actual = session.api as ActualServiceEquipmentApi;
        await session.load();
        final item = actual.f[kind]['item'] as Map<String, dynamic>;
        final id = item['id'];
        final key = kind == 'service'
            ? 'service-review-$id'
            : 'resource-custody-profile-$id';
        final path = kind == 'service'
            ? '/service/cases/$id/transition'
            : '/resource-custody/$id/profile';
        final body = kind == 'service'
            ? {
                ...serviceBound(item),
                'status': 'triaged',
                'reason': 'Explicit review',
                'resolution': '',
              }
            : {
                ...custodyBound(item),
                ...item['profile'] as Map,
                'confirmation': true,
                'reason': 'Explicit review',
              };
        try {
          await expectLater(
            session.command(key, path, Map<String, dynamic>.from(body)),
            throwsA(isA<ApiException>()),
          );
          final original = jsonEncode(actual.posts.single);
          actual.holdOn = kind == 'service'
              ? '/service/cases/$id'
              : '/capabilities';
          var alive = true;
          final retry = kind == 'service'
              ? session.repeatServiceCommand(key, stillCurrent: () => alive)
              : session.repeatResourceCustodyCommand(
                  key,
                  stillCurrent: () => alive,
                );
          final expectation = expectLater(retry, throwsA(isA<ApiException>()));
          await actual.started.future;
          alive = false;
          actual.release!.complete();
          await expectation;
          expect(actual.posts.length, 1);
          expect(jsonEncode(actual.posts.single), original);
          expect(session.pending(key), true);
        } finally {
          session.dispose();
          actual.dispose();
          api.dispose();
        }
      },
    );
  }
}

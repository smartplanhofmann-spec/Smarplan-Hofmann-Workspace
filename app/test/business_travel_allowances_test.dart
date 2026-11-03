import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:smartplan_office/api.dart';
import 'package:smartplan_office/business_session.dart';
import 'package:smartplan_office/business_travel_allowances.dart';

const employeeId = 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa';
const actorId = 'bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb';
const tripId = 'cccccccccccccccccccccccccccccccc';
const sourceHash =
    'dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd';
Map<String, dynamic> clone(dynamic value) =>
    Map<String, dynamic>.from(jsonDecode(jsonEncode(value)) as Map);

class TravelApi extends OfficeApi {
  TravelApi() : super(apiVersion: 'v1') {
    token = 'synthetic-travel-token';
  }
  String actor = actorId;
  bool readAllowed = true,
      writeAllowed = true,
      active = true,
      lose = false,
      accepted = true;
  final posts = <Map<String, dynamic>>[];
  final receipts = <String, Map<String, dynamic>>{};
  Map<String, dynamic>? foreign;
  Completer<void>? delayed;
  @override
  Future<dynamic> call(String path, [Map<String, dynamic>? body]) async {
    if (path == '/api/me') return {'id': actor, 'role': 'owner'};
    if (path.startsWith('/api/business/capabilities'))
      return {
        'compatibility_mode': 'business',
        'storage_version': 7,
        'generation': 1,
        'readonly': false,
        'features': ['travel_allowances'],
        'capabilities': ['business_travel_allowances'],
        'permissions': [
          'personnel.read',
          'personnel.write',
          'personnel.approve',
          'personnel.export',
        ],
      };
    if (path.contains('/travel/sources?'))
      return {
        'employee': {
          'id': employeeId,
          'user_id': actorId,
          'name': 'Synthetische Person',
        },
        'rights': {
          'read': readAllowed,
          'write': writeAllowed,
          'approve': false,
          'export': true,
          'payments': false,
        },
        'active': active,
        'readonly': false,
        'source_hash': sourceHash,
        'files': [],
        'sites': [],
        'projects': [],
        'expenses': [],
      };
    if (path.contains('/travel/requests/')) {
      final receipt = receipts[path.split('/').last];
      if (receipt == null) throw const ApiException(404, 'Not found');
      return {...clone(receipt), ...?foreign};
    }
    if (body != null && path.endsWith('/travel/trips')) {
      posts.add({'path': path, 'body': clone(body)});
      final request = '${body['request_id']}';
      if (accepted && !receipts.containsKey(request)) {
        final result = {
          'id': tripId,
          'employee_id': employeeId,
          'revision': 1,
          'status': 'draft',
          'details': {'purpose': body['details']['purpose']},
        };
        receipts[request] = {
          'request_id': request,
          'actor_id': actorId,
          'employee_id': employeeId,
          'operation': 'trip.save',
          'target_kind': 'trip',
          'target_id': tripId,
          'revision': 1,
          'request_hash': await travelHash(['trip.save', 'trip', tripId, body]),
          'result_hash': await travelHash(result),
          'confirmed': true,
          'result': result,
        };
      }
      if (delayed != null) await delayed!.future;
      if (lose) {
        lose = false;
        throw const ApiException(0, 'Lost reply');
      }
      return {};
    }
    if (path.endsWith('/travel/catalog'))
      return {
        'rates': [
          {
            'id': 'de_2026',
            'country': 'Deutschland',
            'region': '',
            'full_minor': 2800,
            'short_minor': 1400,
            'lodging_minor': 2000,
          },
        ],
      };
    if (RegExp(r'/travel/(trips|settlements|payments)\?').hasMatch(path))
      return {
        'items': [],
        'employee_id': employeeId,
        'rights': {},
        'active': active,
        'readonly': false,
      };
    throw StateError('Unexpected synthetic travel path $path');
  }
}

class SnapshotApi extends TravelApi {
  SnapshotApi(this.snapshot, {this.legacy = false});
  final bool legacy;
  final Map<String, dynamic> snapshot;
  @override
  Future<dynamic> call(String path, [Map<String, dynamic>? body]) async {
    final person = businessMap(snapshot['employee']),
        trip = businessMap(snapshot['trip']);
    if (path.contains('/travel/sources?'))
      return {
        ...businessMap(snapshot['sources']),
        'rights': {
          'read': true,
          'write': true,
          'approve': false,
          'export': true,
          'payments': legacy,
        },
      };
    if (legacy && path.contains('/travel/settlements?'))
      return {
        'employee_id': person['id'],
        'items': [snapshot['legacy']['settlement']],
      };
    if (legacy &&
        body == null &&
        path.endsWith(
          '/travel/settlements/${snapshot['legacy']['settlement']['id']}',
        ))
      return {
        'item': snapshot['legacy']['settlement'],
        'source_hash': sourceHash,
      };
    if (path.endsWith('/travel/trips?employee_id=${person['id']}'))
      return {
        'employee_id': person['id'],
        'items': [trip],
      };
    if (RegExp(r'/travel/(settlements|payments)\?').hasMatch(path))
      return {'employee_id': person['id'], 'items': []};
    if (body == null && path.endsWith('/travel/trips/${trip['id']}'))
      return {'item': trip, 'source_hash': sourceHash};
    if (path.contains('/travel/time-options?')) {
      final query = Uri.parse(path).queryParameters,
          local = query['local']!,
          zone = query['timezone'];
      return {
        'local': local,
        'timezone': zone,
        'valid': true,
        'options': [
          {
            'instant': '$local:00+01:00',
            'offset': '+01:00',
            'label': '$local +01:00',
          },
        ],
      };
    }
    if (body != null && path.endsWith('/travel/payments')) {
      posts.add({'path': path, 'body': clone(body)});
      final result = {
        'id': body['id'],
        'employee_id': person['id'],
        'revision': 1,
        'status': 'active',
        'details': clone(body),
      };
      receipts[body['request_id']] = {
        'request_id': body['request_id'],
        'actor_id': actorId,
        'employee_id': person['id'],
        'operation': 'payment.record',
        'target_kind': 'payment',
        'target_id': body['id'],
        'revision': 1,
        'request_hash': await travelHash([
          'payment.record',
          'payment',
          body['id'],
          body,
        ]),
        'result_hash': await travelHash(result),
        'confirmed': true,
        'result': result,
      };
      if (lose) {
        lose = false;
        throw const ApiException(0, 'Lost legacy acknowledgement');
      }
      return {};
    }
    if (body != null && path.endsWith('/travel/trips')) {
      posts.add({'path': path, 'body': clone(body)});
      final result = {
        ...trip,
        'revision': (body['revision'] as int) + 1,
        'status': 'draft',
        'details': body['details'],
      };
      receipts[body['request_id']] = {
        'request_id': body['request_id'],
        'actor_id': actorId,
        'employee_id': person['id'],
        'operation': 'trip.save',
        'target_kind': 'trip',
        'target_id': body['id'],
        'revision': result['revision'],
        'request_hash': await travelHash([
          'trip.save',
          'trip',
          body['id'],
          body,
        ]),
        'result_hash': await travelHash(result),
        'confirmed': true,
        'result': result,
      };
      return {};
    }
    return super.call(path, body);
  }
}

Future<(TravelApi, BusinessSession, TravelCommand)> fixture() async {
  final api = TravelApi();
  final realSession = BusinessSession(api: api);
  await realSession.load();
  final command = TravelCommand(realSession, employeeId: employeeId);
  addTearDown(() {
    command.dispose();
    realSession.dispose();
  });
  return (api, realSession, command);
}

Future<Map<String, dynamic>> send(
  TravelCommand command, [
  Map<String, dynamic>? body,
]) => command.submit(
  '/personnel/travel/trips',
  body ??
      {
        'employee_id': employeeId,
        'id': tripId,
        'revision': 0,
        'details': {'purpose': 'PRIVATE Reise'},
      },
  operation: 'trip.save',
  targetKind: 'trip',
  targetId: tripId,
);

void main() {
  test('exact EUR values keep missing input separate from explicit zero and preserve civil time', () {
    expect(travelMinor('14,05'), 1405);
    expect(travelMinor('0', zero: true), 0);
    for (final value in ['', null, '-1', '1.234', '1e2', '1,002']) {
      expect(
        () => travelMinor(value, zero: true),
        throwsA(isA<ApiException>()),
      );
    }
    expect(travelLocalTime('2026-10-25T02:30'), '2026-10-25T02:30');
    for (final value in [
      '2026-02-29T12:00',
      '2026-11-03T24:00',
      '',
      '2026-11-03',
    ]) {
      expect(() => travelLocalTime(value), throwsA(isA<ApiException>()));
    }
    expect(
      travelCanonical({
        'z': ['ä', 1, false],
        'a': null,
      }),
      '{"a":null,"z":["ä",1,false]}',
    );
    expect(
      () => travelCanonical({'amount': 1.1}),
      throwsA(isA<ApiException>()),
    );
  });
  test('DST clock ambiguity keeps both actual time choices; nonexistent clock is not normalized', () {
    const local = '2026-10-25T02:30', timezone = 'Europe/Berlin';
    final options = ['+02:00', '+01:00']
        .map(
          (offset) => {
            'instant': '$local:00$offset',
            'offset': offset,
            'label': offset,
          },
        )
        .toList();
    expect(
      travelTimeOptions(
        {
          'local': local,
          'timezone': timezone,
          'options': options,
          'valid': true,
        },
        local,
        timezone,
      ),
      hasLength(2),
    );
    expect(
      () => travelTimeOptions(
        {'local': local, 'timezone': timezone, 'options': [], 'valid': false},
        local,
        timezone,
      ),
      throwsA(isA<ApiException>()),
    );
  });
  test('accepted lost reply resolves with status only after module pause without exposing private pending body', () async {
    final (api, _, command) = await fixture();
    api.lose = true;
    final body = {
      'employee_id': employeeId,
      'id': tripId,
      'revision': 0,
      'details': {'purpose': 'PRIVATE Original'},
    };
    await expectLater(send(command, body), throwsA(isA<ApiException>()));
    (body['details'] as Map)['purpose'] = 'changed after click';
    expect(command.pending?['target_id'], tripId);
    expect(command.pending?.containsKey('body'), isFalse);
    api.active = false;
    api.writeAllowed = false;
    final receipt = await command.retry();
    expect(receipt['result']['details']['purpose'], 'PRIVATE Original');
    expect(api.posts, hasLength(1));
    expect(command.pending, isNull);
  });
  test('missing status retains original body and nonce for explicit identical retry', () async {
    final (api, _, command) = await fixture();
    api.accepted = false;
    api.lose = true;
    await expectLater(send(command), throwsA(isA<ApiException>()));
    await expectLater(
      command.status(),
      throwsA(isA<ApiException>().having((e) => e.status, 'status', 404)),
    );
    expect(command.pending, isNotNull);
    api.accepted = true;
    await command.retry();
    expect(api.posts[0], api.posts[1]);
    expect(api.receipts, hasLength(1));
  });
  test('fresh rights or actor change discards private command before another write', () async {
    for (final change in [
      (TravelApi api) {
        api.readAllowed = false;
      },
      (TravelApi api) {
        api.actor = 'eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee';
      },
    ]) {
      final (api, _, command) = await fixture();
      api.lose = true;
      await expectLater(send(command), throwsA(isA<ApiException>()));
      change(api);
      await expectLater(command.retry(), throwsA(isA<ApiException>()));
      expect(command.pending, isNull);
      expect(api.posts, hasLength(1));
    }
  });
  test('changed result, operation, employee or request cannot resolve the accepted original', () async {
    for (final altered in [
      {'employee_id': 'eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee'},
      {'operation': 'payment.record'},
      {'request_hash': 'e' * 64},
      {
        'result': {
          'id': tripId,
          'employee_id': employeeId,
          'revision': 1,
          'details': {'purpose': 'tampered'},
        },
      },
    ]) {
      final (api, _, command) = await fixture();
      api.lose = true;
      await expectLater(send(command), throwsA(isA<ApiException>()));
      api.foreign = altered;
      await expectLater(command.status(), throwsA(isA<ApiException>()));
      expect(command.pending, isNotNull);
      expect(api.posts, hasLength(1));
    }
  });
  test('closing private scope rejects late accepted response without undoing server effect', () async {
    final (api, _, command) = await fixture();
    api.delayed = Completer<void>();
    final result = send(command);
    while (api.receipts.isEmpty) {
      await Future<void>.delayed(Duration.zero);
    }
    command.clear();
    api.delayed!.complete();
    await expectLater(result, throwsA(isA<ApiException>()));
    expect(command.pending, isNull);
    expect(api.receipts, hasLength(1));
  });
  test('real v2 flight and expense snapshot has source-bound receipts and versioned totals', () async {
    final value = clone(
      jsonDecode(
        File('test/fixtures/travel_allowances.json').readAsStringSync(),
      ),
    );
    final preview = travelPreview(
      value['preview'],
      value['employee']['id'],
      businessMap(value['preview_body']),
    );
    expect(preview['totals']['tax_free_minor'], 2000);
    expect(preview['totals']['expense_allowance_minor'], 600);
    expect(preview['expense_items'][0]['private_minor'], 400);
    for (final key in [
      'expense_allowance_minor',
      'expense_already_paid_minor',
    ]) {
      final altered = clone(preview);
      (altered['totals'] as Map).remove(key);
      expect(
        () => travelPreview(
          altered,
          value['employee']['id'],
          businessMap(value['preview_body']),
        ),
        throwsA(isA<ApiException>()),
      );
    }
    for (final pair in const [
      ['trip_receipt', 'trip_body'],
      ['approval_receipt', 'approval_body'],
      ['payment_receipt', 'payment_body'],
    ]) {
      final receipt = businessMap(value[pair[0]]),
          body = businessMap(value[pair[1]]);
      expect(
        await travelReceipt(receipt, {
          'request_id': body['request_id'],
          'actor_id': receipt['actor_id'],
          'employee_id': body['employee_id'],
          'operation': receipt['operation'],
          'target_kind': receipt['target_kind'],
          'target_id': body['id'],
          'request_hash': await travelHash([
            receipt['operation'],
            receipt['target_kind'],
            body['id'],
            body,
          ]),
        }),
        receipt,
      );
    }
    final historical = clone(preview)..['rule_version'] = 'de_travel_2026_v1';
    (historical['totals'] as Map)
      ..remove('expense_allowance_minor')
      ..remove('expense_already_paid_minor');
    expect(
      travelPreview(
        historical,
        value['employee']['id'],
        businessMap(value['preview_body']),
      ),
      historical,
    );
  });
  testWidgets(
    'native actual flight and expense forms preserve originals while requiring a complete cent split',
    (tester) async {
      await tester.binding.setSurfaceSize(const Size(1100, 1000));
      addTearDown(() => tester.binding.setSurfaceSize(null));
      final snapshot = clone(
            jsonDecode(
              File('test/fixtures/travel_allowances.json').readAsStringSync(),
            ),
          ),
          api = SnapshotApi(
            clone(
              jsonDecode(
                File('test/fixtures/travel_allowances.json').readAsStringSync(),
              ),
            ),
          );
      final session = BusinessSession(api: api);
      await session.load();
      var disposed = false;
      addTearDown(() {
        if (!disposed) session.dispose();
      });
      await tester.pumpWidget(
        MaterialApp(
          home: BusinessTravelAllowancesPage(
            session: session,
            employee: businessMap(snapshot['employee']),
          ),
        ),
      );
      await tester.pumpAndSettle();
      Future<void> tap(String label) async {
        if (find.text(label).evaluate().isEmpty) {
          await tester.scrollUntilVisible(
            find.text(label),
            500,
            scrollable: find.byType(Scrollable).first,
            maxScrolls: 15,
          );
          await tester.pumpAndSettle();
        }
        final target = find.text(label).last;
        await tester.ensureVisible(target);
        await tester.pumpAndSettle();
        await tester.tap(target);
        await tester.pumpAndSettle();
      }

      Future<void> enter(String name, String value) async {
        final target = find.byKey(ValueKey('business-field-$name'));
        await tester.ensureVisible(target);
        await tester.pumpAndSettle();
        await tester.enterText(target, value);
      }

      await tap(snapshot['trip']['details']['purpose']);
      await tap('Reise korrigieren');
      await tap('Beförderung');
      expect(find.text('Belegte Auslagenposition aufteilen'), findsOneWidget);
      expect(
        tester
            .widget<TextFormField>(
              find.byKey(const ValueKey('business-field-business_minor')),
            )
            .controller!
            .text,
        '6.00',
      );
      await enter('business_minor', '7');
      await tap('Belegte Aufteilung übernehmen');
      expect(
        find.textContaining('genau den gespeicherten Originalbetrag'),
        findsOneWidget,
      );
      expect(api.posts, isEmpty);
      await enter('private_minor', '3');
      await tap('Belegte Aufteilung übernehmen');
      await tap('Belegte Flugreise');
      expect(find.text('Zusammenhängende Flugreise belegen'), findsOneWidget);
      expect(
        find.text('Flugabschnitt 1 · tatsächlicher Abflugort'),
        findsOneWidget,
      );
      await tap('Belegte Beförderung übernehmen');
      expect(
        find.text('Zusammenhängende Flugreise belegen'),
        findsNothing,
        reason: tester
            .widgetList<Text>(find.byType(Text))
            .map((w) => w.data)
            .join(' | '),
      );
      await tester.drag(find.byType(ListView).first, const Offset(0, 2000));
      await tester.pumpAndSettle();
      await tap('Grunddaten und Pauschalenwunsch bearbeiten');
      await enter(
        'correction_reason',
        'Synthetic reviewed exact original split correction',
      );
      await tap('Angaben übernehmen');
      await tap('Reiseentwurf belegt speichern');
      expect(api.posts, hasLength(1));
      final sent = api.posts.single['body']['details'];
      expect(sent['expense_allocations'][0]['business_minor'], 700);
      expect(sent['expense_allocations'][0]['private_minor'], 300);
      expect(
        sent['transport_facts'],
        snapshot['trip']['details']['transport_facts'],
      );
      expect(sent['expense_refs'], snapshot['trip']['details']['expense_refs']);
      expect(tester.takeException(), isNull);
      await tester.pumpWidget(const SizedBox.shrink());
      session.dispose();
      disposed = true;
    },
  );
  test('actual old-payment financial adoption binds original payment hash and receipt', () async {
    final fixture = clone(
          jsonDecode(
            File('test/fixtures/travel_allowances.json').readAsStringSync(),
          ),
        ),
        legacy = businessMap(fixture['legacy']),
        body = businessMap(fixture['legacy']['body']),
        receipt = businessMap(fixture['legacy']['receipt']);
    expect(body['action'], 'adopt_legacy');
    expect(
      body['legacy_payment']['payment_hash'],
      await travelHash(
        legacy['expense']['payments'][body['legacy_payment']['payment_index']],
      ),
    );
    expect(
      legacy['settlement']['calculation']['totals']['already_paid_minor'],
      1000,
    );
    expect(
      legacy['settlement']['calculation']['totals']['remaining_minor'],
      1400,
    );
    expect(legacy['cash_source']['cash_movements'][0]['amount'], '10.00');
    for (final key in ['kind', 'paid_on', 'amount_minor', 'reference'])
      expect(body[key], legacy['expense']['payments'][0][key]);
    final expected = {
      ...receipt,
      'request_hash': await travelHash([
        'payment.record',
        'payment',
        body['id'],
        body,
      ]),
    };
    expect(await travelReceipt(receipt, expected), receipt);
    final altered = clone(receipt);
    altered['result']['details']['legacy_payment'] = null;
    await expectLater(
      travelReceipt(altered, expected),
      throwsA(isA<ApiException>()),
    );
  });
  testWidgets(
    'native old-payment adoption locks existing facts and recovers accepted reply by status only',
    (tester) async {
      await tester.binding.setSurfaceSize(const Size(1100, 1000));
      addTearDown(() => tester.binding.setSurfaceSize(null));
      final snapshot = clone(
            jsonDecode(
              File('test/fixtures/travel_allowances.json').readAsStringSync(),
            ),
          ),
          api = SnapshotApi(
            clone(
              jsonDecode(
                File('test/fixtures/travel_allowances.json').readAsStringSync(),
              ),
            ),
            legacy: true,
          );
      final session = BusinessSession(api: api);
      await session.load();
      var disposed = false;
      addTearDown(() {
        if (!disposed) session.dispose();
      });
      await tester.pumpWidget(
        MaterialApp(
          home: BusinessTravelAllowancesPage(
            session: session,
            employee: businessMap(snapshot['employee']),
          ),
        ),
      );
      await tester.pumpAndSettle();
      Future<void> tap(String label) async {
        if (find.text(label).evaluate().isEmpty) {
          await tester.scrollUntilVisible(
            find.text(label),
            500,
            scrollable: find.byType(Scrollable).first,
            maxScrolls: 15,
          );
          await tester.pumpAndSettle();
        }
        final target = find.text(label).last;
        await tester.ensureVisible(target);
        await tester.pumpAndSettle();
        await tester.tap(target);
        await tester.pumpAndSettle();
      }

      Future<void> select(String label, Finder item) async {
        final target = find.byWidgetPredicate(
          (w) =>
              w is DropdownButtonFormField<String> &&
              w.decoration.labelText == label,
        );
        await tester.ensureVisible(target);
        await tester.pumpAndSettle();
        await tester.tap(target);
        await tester.pumpAndSettle();
        await tester.tap(item.last);
        await tester.pumpAndSettle();
      }

      await tap('Abrechnung · Fassung 1');
      await tap('Bereits belegte Auslagenzahlung für Finanzen übernehmen');
      await select(
        'Unveränderte ursprüngliche Zahlung',
        find.textContaining('SYN-LEGACY-ACTUAL-PAYMENT'),
      );
      await tap('Finanznachweis dieser Altzahlung ergänzen');
      expect(
        find.byKey(const ValueKey('business-field-paid_on')),
        findsNothing,
      );
      expect(find.byKey(const ValueKey('business-field-amount')), findsNothing);
      expect(
        find.byKey(const ValueKey('business-field-reference')),
        findsNothing,
      );
      expect(find.textContaining('keine neue Auszahlung'), findsOneWidget);
      final account = businessMap(
            (snapshot['sources']['accounts'] as List).first,
          ),
          files = (snapshot['sources']['files'] as List)
              .map(businessMap)
              .where((item) => item['purpose'] == 'personnel')
              .toList();
      await select(
        'Tatsächlich verwendetes Geldkonto',
        find.text(account['name']),
      );
      await select(
        'Unverändertes Zahlungsoriginal',
        find.text(files.last['filename']).hitTestable(),
      );
      await tester.tap(find.byType(SwitchListTile).last);
      await tester.pumpAndSettle();
      api.lose = true;
      await tap('Vorhandene Zahlung als Finanzquelle übernehmen');
      expect(find.textContaining('ursprünglichen Auftrags'), findsWidgets);
      expect(api.posts, hasLength(1));
      await tap('Erneut senden');
      expect(
        api.posts,
        hasLength(1),
        reason: 'explicit retry resolves accepted receipt without another POST',
      );
      final sent = businessMap(api.posts.single['body']),
          original = businessMap(snapshot['legacy']['body']);
      for (final key in [
        'kind',
        'paid_on',
        'amount_minor',
        'reference',
        'legacy_payment',
      ])
        expect(sent[key], original[key]);
      expect(sent['account_id'], account['id']);
      expect(sent['reference_file_id'], files.last['id']);
      expect(sent['action'], 'adopt_legacy');
      expect(tester.takeException(), isNull);
      await tester.pumpWidget(const SizedBox.shrink());
      session.dispose();
      disposed = true;
    },
  );
  testWidgets(
    'travel editor starts without invented dates and backgrounding discards private draft',
    (tester) async {
      final api = TravelApi();
      final actual = BusinessSession(api: api);
      await actual.load();
      var disposed = false;
      addTearDown(() {
        if (!disposed) actual.dispose();
      });
      await tester.pumpWidget(
        MaterialApp(
          home: BusinessTravelAllowancesPage(
            session: actual,
            employee: const {'id': employeeId, 'name': 'Synthetische Person'},
          ),
        ),
      );
      await tester.pumpAndSettle();
      expect(find.text('Neue Reise erfassen'), findsOneWidget);
      await tester.tap(find.text('Neue Reise erfassen'));
      await tester.pumpAndSettle();
      expect(find.text('Reiseentwurf'), findsOneWidget);
      expect(find.text('Beginn: Nicht angegeben'), findsOneWidget);
      tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.inactive);
      await tester.pumpAndSettle();
      expect(find.text('Reiseentwurf'), findsNothing);
      tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.resumed);
      await tester.pumpAndSettle();
      expect(find.text('Neue Reise erfassen'), findsOneWidget);
      expect(tester.takeException(), isNull);
      await tester.pumpWidget(const SizedBox.shrink());
      actual.dispose();
      disposed = true;
    },
  );
}

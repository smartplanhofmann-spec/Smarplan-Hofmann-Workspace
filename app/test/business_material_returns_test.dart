import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:smartplan_office/api.dart';
import 'package:smartplan_office/business_material_returns.dart';
import 'package:smartplan_office/business_operations.dart';
import 'package:smartplan_office/business_session.dart';
import 'package:smartplan_office/service_creation_journal.dart'
    show serviceCreationCanonical;

final fixture = jsonDecode(
  File('test/fixtures/material_return.json').readAsStringSync(),
) as Map<String, dynamic>;
Map<String, dynamic> copy(dynamic value) =>
    Map<String, dynamic>.from(jsonDecode(jsonEncode(value)) as Map);
final mainCase = copy(fixture['main']);

class ReturnHttp extends HttpOverrides {}

class ReturnApi extends OfficeApi {
  ReturnApi({bool operational = false}) : super(apiVersion: 'v1') {
    token = 'synthetic-material-return-session';
    if (operational) {
      final op = mainCase['operational'];
      movements = [...op['movements'], op['second_issue']].map(copy).toList();
      result = copy(op['returned']);
      actor = result['created_by'];
    }
  }
  bool read = true, write = true, finance = true, lose = false, wrong = false;
  String actor = mainCase['issue']['created_by'];
  List<Map<String, dynamic>> movements =
      (mainCase['before']['movements'] as List).map(copy).toList();
  Map<String, dynamic> result = copy(mainCase['first']['returned']);
  final sent = <Map<String, dynamic>>[];
  final accepted = <String, Map<String, dynamic>>{};
  Completer<void>? beforeReply;
  void Function(Map<String, dynamic>)? changeGet;
  @override
  Future<dynamic> call(String path, [Map<String, dynamic>? body]) async {
    final uri = Uri.parse(path);
    if (uri.path == '/api/business/capabilities')
      return {
        'compatibility_mode': 'business',
        'generation': 1,
        'storage_version': 10,
        'readonly': false,
        'capabilities': ['business_inventory'],
        'features': ['inventory_article_refs'],
        'permissions': [
          if (read) 'inventory.read',
          if (write) 'inventory.write',
          if (finance) 'finance.read',
        ],
        'organization': {
          'modules': {
            'material': {'enabled': true, 'visible': true},
          },
        },
      };
    if (uri.path == '/api/me') return {'id': actor};
    if (uri.path == '/api/business/inventory/articles')
      return {
        'items': [
          {
            'id': mainCase['article']['id'],
            'name': 'Synthetic cable',
            'active': true,
          },
        ],
        'has_more': false,
        'next_after': null,
      };
    if (uri.path == '/api/business/inventory/locations')
      return {
        'items': [mainCase['location']],
      };
    if (uri.path == '/api/business/inventory/movements') {
      if (body == null) return {'items': movements.map(copy).toList()};
      sent.add(copy(body));
      if (!write) throw const ApiException(403, 'Synthetic write withdrawn.');
      final previous = accepted[body['request_id']];
      if (previous != null &&
          serviceCreationCanonical(previous) != serviceCreationCanonical(body))
        throw const ApiException(409, 'Synthetic nonce changed.');
      if (previous == null) {
        accepted[body['request_id']] = copy(body);
        movements.add(copy(result));
      }
      if (beforeReply != null) await beforeReply!.future;
      if (lose) {
        lose = false;
        throw const ApiException(0, 'Synthetic accepted response lost.');
      }
      final response = copy(result);
      if (wrong) response['reversal_of'] = 'e' * 32;
      return response;
    }
    if (uri.path == '/api/business/inventory/movements/${result['id']}') {
      final value = copy(result);
      changeGet?.call(value);
      return value;
    }
    if (uri.path == '/api/business/inventory/stock') return {'items': []};
    throw StateError(path);
  }
}

Future<
  ({
    ReturnApi api,
    BusinessSession session,
    MaterialReturnFlow flow,
    void Function() cleanup,
  })
>
setup({bool operational = false}) async {
  final api = ReturnApi(operational: operational);
  final owner = BusinessSession(api: api, projectId: mainCase['project_id']);
  await owner.load();
  final flow = MaterialReturnFlow(owner);
  var disposed = false;
  void cleanup() {
    if (!disposed) {
      disposed = true;
      flow.dispose();
      owner.dispose();
      api.dispose();
    }
  }

  addTearDown(cleanup);
  return (api: api, session: owner, flow: flow, cleanup: cleanup);
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  test('real partial and final returns retain exact original quantities and historical valuation', () {
    for (final entry in [
      ('before', '6.0000'),
      ('first', '4.0000'),
      ('second', '3.0000'),
      ('final', '0.0000'),
    ]) {
      final state = entry.$1 == 'before'
          ? mainCase['before']
          : mainCase[entry.$1]['after'];
      final options = materialReturnOptions(
        state['movements'],
        projectId: mainCase['project_id'],
      );
      expect(options.single['remaining_quantity'], entry.$2);
      expect(options.single['issue'], mainCase['issue']);
    }
    for (final name in ['first', 'second', 'final']) {
      materialReturnReceipt(
        mainCase[name]['returned'],
        mainCase[name]['command'],
      );
      expect(mainCase[name]['returned']['unit_cost_net'], '10.0000');
    }
    expect(mainCase['updated_article']['cost_price_net'], '99.0000');
    for (final row in fixture['rounding']['returns']) {
      materialReturnReceipt(row['returned'], {
        ...copy(row['command']),
        'note': '',
      });
    }
    expect(
      (fixture['rounding']['returns'] as List)
          .map((v) => v['returned']['cost_net'])
          .toList(),
      ['0.3333', '0.3333', '0.3334'],
    );
    expect(
      materialReturnQuantityText(materialReturnQuantity('999999999999.9999')),
      '999999999999.9999',
    );
  });
  test('first return binds original project and article and never sends current price or source warehouse', () async {
    final t = await setup();
    final original = copy(mainCase['issue']);
    await t.flow.submit(
      original,
      '2,0000',
      mainCase['location']['id'],
      'Synthetic first actual return',
    );
    final body = copy(t.api.sent.single)..remove('request_id');
    final expected = copy(mainCase['first']['command'])..remove('request_id');
    expected['quantity'] = '2.0000';
    expect(body, expected);
    expect(t.flow.pending, isNull);
    expect(t.api.accepted.length, 1);
    expect(original, mainCase['issue']);
  });
  test('fresh remaining balance prevents over-return and changed source before any POST', () async {
    final t = await setup();
    t.api.movements = (mainCase['second']['after']['movements'] as List)
        .map(copy)
        .toList();
    await expectLater(
      t.flow.submit(
        copy(mainCase['issue']),
        '3.0001',
        mainCase['location']['id'],
        '',
      ),
      throwsA(isA<ApiException>()),
    );
    final changed = copy(mainCase['issue'])..['article_id'] = 'e' * 32;
    await expectLater(
      t.flow.submit(changed, '1', mainCase['location']['id'], ''),
      throwsA(isA<ApiException>()),
    );
    expect(t.api.sent, isEmpty);
    expect(t.flow.pending, isNull);
    for (final input in ['0', '-1', '1.00001', '1e3', 'NaN']) {
      expect(() => materialReturnQuantity(input), throwsA(isA<ApiException>()));
    }
  });
  test('accepted lost response repeats exact original after all material is already returned', () async {
    final t = await setup();
    t.api.lose = true;
    await expectLater(
      t.flow.submit(
        copy(mainCase['issue']),
        '2',
        mainCase['location']['id'],
        'Synthetic first actual return',
      ),
      throwsA(isA<ApiException>()),
    );
    t.api.movements = (mainCase['final']['after']['movements'] as List)
        .map(copy)
        .toList();
    await t.flow.retry();
    expect(t.api.sent.length, 2);
    expect(t.api.sent[0], t.api.sent[1]);
    expect(t.api.accepted.length, 1);
    expect(t.flow.pending, isNull);
  });
  test('price-free original acknowledgement survives finance withdrawal but write withdrawal preserves it', () async {
    final t = await setup(operational: true);
    final op = mainCase['operational'];
    t.api.lose = true;
    await expectLater(
      t.flow.submit(
        copy(op['second_issue']),
        '1',
        mainCase['location']['id'],
        op['command']['note'],
      ),
      throwsA(isA<ApiException>()),
    );
    t.api.finance = false;
    t.api.write = false;
    await t.session.load();
    await expectLater(t.flow.retry(), throwsA(isA<ApiException>()));
    expect(t.api.sent.length, 1);
    expect(t.flow.pending, isNotNull);
    t.api.write = true;
    await t.flow.retry();
    expect(t.api.sent[0], t.api.sent[1]);
    expect(t.api.result.containsKey('cost_net'), false);
    expect(t.flow.pending, isNull);
  });
  test('wrong acknowledgement and changed account cannot consume or resend another original', () async {
    final t = await setup();
    t.api.wrong = true;
    await expectLater(
      t.flow.submit(
        copy(mainCase['issue']),
        '2',
        mainCase['location']['id'],
        'Synthetic first actual return',
      ),
      throwsA(isA<ApiException>()),
    );
    expect(t.flow.pending, isNotNull);
    t.api.actor = 'e' * 32;
    await expectLater(t.flow.retry(), throwsA(isA<ApiException>()));
    expect(t.api.sent.length, 1);
    expect(t.flow.pending, isNotNull);
    t.api.actor = mainCase['issue']['created_by'];
    t.api.wrong = false;
    await t.flow.retry();
    expect(t.api.accepted.length, 1);
  });
  test(
    'concurrent first submissions cannot create two return commands',
    () async {
      final t = await setup();
      t.api.beforeReply = Completer<void>();
      final first = t.flow.submit(
        copy(mainCase['issue']),
        '2',
        mainCase['location']['id'],
        'Synthetic first actual return',
      );
      while (t.api.sent.isEmpty) {
        await Future<void>.delayed(Duration.zero);
      }
      await expectLater(
        t.flow.submit(
          copy(mainCase['issue']),
          '2',
          mainCase['location']['id'],
          'Synthetic first actual return',
        ),
        throwsA(isA<ApiException>()),
      );
      t.api.beforeReply!.complete();
      await first;
      expect(t.api.sent.length, 1);
    },
  );
  test(
    'changed author metadata or readback value cannot confirm the original',
    () async {
      for (final change in <void Function(Map<String, dynamic>)>[
        (v) => v['created_by'] = 'e' * 32,
        (v) => v['created_at'] = '2026-10-26T10:00:00+00:00',
        (v) => v['article_snapshot']['name'] = 'Wrong material',
        (v) => v['cost_net'] = '20.0001',
        (v) => v['article_snapshot']['cost_price_net'] = '99.0001',
      ]) {
        final t = await setup();
        t.api.changeGet = change;
        await expectLater(
          t.flow.submit(
            copy(mainCase['issue']),
            '2',
            mainCase['location']['id'],
            'Synthetic first actual return',
          ),
          throwsA(isA<ApiException>()),
        );
        expect(t.flow.pending, isNotNull);
        expect(t.api.accepted.length, 1);
        t.api.changeGet = null;
        await t.flow.retry();
        expect(t.api.sent[0], t.api.sent[1]);
        expect(t.api.accepted.length, 1);
      }
    },
  );
  test('real HTTP lost response retains its original request and produces one stored return', () async {
    await HttpOverrides.runWithHttpOverrides(() async {
      final model = ReturnApi()..lose = true;
      final server = await HttpServer.bind(InternetAddress.loopbackIPv4, 0);
      final authorizations = <String?>[];
      server.listen((request) async {
        authorizations.add(
          request.headers.value(HttpHeaders.authorizationHeader),
        );
        final text = await utf8.decoder.bind(request).join();
        final body = text.isEmpty ? null : copy(jsonDecode(text));
        final path = request.uri.toString().replaceFirst('/api/v1/', '/api/');
        try {
          final result = await model.call(path, body);
          request.response.headers.contentType = ContentType.json;
          request.response.write(jsonEncode(result));
          await request.response.close();
        } on ApiException catch (e) {
          if (e.status == 0) {
            final socket = await request.response.detachSocket(
              writeHeaders: false,
            );
            socket.destroy();
          } else {
            request.response.statusCode = e.status;
            request.response.headers.contentType = ContentType.json;
            request.response.write(jsonEncode({'error': e.message}));
            await request.response.close();
          }
        }
      });
      final api = OfficeApi(
        baseUrl: 'http://127.0.0.1:${server.port}',
        apiVersion: 'v1',
      )..token = 'synthetic-http-return-session';
      final owner = BusinessSession(
        api: api,
        projectId: mainCase['project_id'],
      );
      final flow = MaterialReturnFlow(owner);
      try {
        await owner.load();
        await expectLater(
          flow.submit(
            copy(mainCase['issue']),
            '2',
            mainCase['location']['id'],
            'Synthetic first actual return',
          ),
          throwsA(isA<ApiException>()),
        );
        expect(flow.pending, isNotNull);
        await flow.retry();
        expect(model.sent[0], model.sent[1]);
        expect(model.accepted.length, 1);
        expect(flow.pending, isNull);
        expect(
          authorizations.every(
            (v) => v == 'Bearer synthetic-http-return-session',
          ),
          true,
        );
      } finally {
        flow.dispose();
        owner.dispose();
        api.dispose();
        model.dispose();
        await server.close(force: true);
      }
    }, ReturnHttp());
  });
  testWidgets(
    'closing and reopening an unconfirmed return retains only the original retry',
    (tester) async {
      final t = await setup();
      t.api.lose = true;
      await expectLater(
        t.flow.submit(
          copy(mainCase['issue']),
          '2',
          mainCase['location']['id'],
          'Synthetic first actual return',
        ),
        throwsA(isA<ApiException>()),
      );
      await tester.pumpWidget(
        MaterialApp(
          home: Builder(
            builder: (context) => Scaffold(
              body: TextButton(
                onPressed: () => showDialog<void>(
                  context: context,
                  builder: (_) => MaterialReturnDialog(flow: t.flow),
                ),
                child: const Text('Öffnen'),
              ),
            ),
          ),
        ),
      );
      await tester.tap(find.text('Öffnen'));
      await tester.pumpAndSettle();
      expect(find.text('Ursprüngliche Rückgabe erneut prüfen'), findsOneWidget);
      expect(
        find.byKey(const ValueKey('material-return-quantity')),
        findsNothing,
      );
      await tester.tap(find.text('Schließen'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Öffnen'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Ursprüngliche Rückgabe erneut prüfen'));
      await tester.pumpAndSettle();
      expect(t.api.sent[0], t.api.sent[1]);
      expect(t.api.accepted.length, 1);
      await tester.pumpWidget(const SizedBox());
      t.cleanup();
      await tester.pump();
    },
  );
  testWidgets(
    'actual material area opens an original-bound return form without price inputs',
    (tester) async {
      final t = await setup();
      tester.view.physicalSize = const Size(1100, 1400);
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.resetPhysicalSize);
      addTearDown(tester.view.resetDevicePixelRatio);
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: BusinessAreaPage(session: t.session, area: 'material'),
          ),
        ),
      );
      await tester.pumpAndSettle();
      await tester.tap(find.byType(DropdownButtonFormField<String>).first);
      await tester.pumpAndSettle();
      await tester.tap(find.text('Lagerbewegungen').last);
      await tester.pumpAndSettle();
      await tester.tap(find.text('Material zurückgeben'));
      await tester.pumpAndSettle();
      expect(find.text('Originalentnahme'), findsOneWidget);
      expect(
        find.text('Tatsächlicher Einstand netto je Einheit (€)'),
        findsNothing,
      );
      await tester.tap(find.byType(DropdownButtonFormField<String>).at(1));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Synthetic cable · Rest 6.0000').last);
      await tester.pumpAndSettle();
      expect(
        tester
            .widget<TextFormField>(
              find.byKey(const ValueKey('material-return-quantity')),
            )
            .controller!
            .text,
        '',
      );
      await tester.tap(find.byType(DropdownButtonFormField<String>).at(2));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Synthetic main store').last);
      await tester.pumpAndSettle();
      await tester.enterText(
        find.byKey(const ValueKey('material-return-quantity')),
        '2',
      );
      await tester.enterText(
        find.byKey(const ValueKey('material-return-note')),
        'Synthetic first actual return',
      );
      expect(
        tester
            .widget<FilledButton>(
              find.widgetWithText(FilledButton, 'Rückgabe buchen'),
            )
            .onPressed,
        isNull,
      );
      await tester.tap(find.byType(CheckboxListTile));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Rückgabe buchen'));
      await tester.pumpAndSettle();
      expect(t.api.accepted.length, 1);
      expect(t.api.sent.single['reversal_of'], mainCase['issue']['id']);
      await tester.pumpWidget(const SizedBox());
      t.cleanup();
      await tester.pump();
    },
  );
}

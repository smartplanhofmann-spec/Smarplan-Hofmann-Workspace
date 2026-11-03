import 'dart:async';
import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:smartplan_office/api.dart';
import 'package:smartplan_office/business_session.dart';

const eventId = '11111111111111111111111111111111';
const key = 'accounting-components-$eventId';
const oldPath = '/accounting/components/events/$eventId/confirm';
const newPath = '/accounting/components/v2/events/$eventId/confirm';

class CapacitySessionApi extends OfficeApi {
  CapacitySessionApi() : super(apiVersion: 'v1') {
    token = 'synthetic-capacity';
  }
  int generation = 1;
  int? confirmationFailure;
  String? requestResolution;
  bool sourceDenied = false, stateDenied = false, writable = true;
  Completer<void>? confirmationReply, sourceReply;
  final calls = <({String path, Map<String, dynamic>? body})>[];
  @override
  Future<dynamic> call(String path, [Map<String, dynamic>? body]) async {
    calls.add((
      path: path,
      body: body == null
          ? null
          : jsonDecode(jsonEncode(body)) as Map<String, dynamic>,
    ));
    if (path == '/api/business/capabilities') {
      return {
        'compatibility_mode': 'business',
        'generation': generation,
        'readonly': false,
        'capabilities': [
          'business_accounting_components',
          'business_accounting_capacity',
        ],
        'features': [
          'accounting_document_components',
          'accounting_document_component_reuse',
        ],
        'permissions': [
          'accounting.read',
          'finance.read',
          'accounting.prepare',
          if (writable) 'finance.write',
        ],
      };
    }
    if (body == null && path.endsWith('/accounting/events/$eventId')) {
      if (sourceReply != null) await sourceReply!.future;
      if (sourceDenied)
        throw const ApiException(403, 'Gesamte Quelle nicht freigegeben');
      return {'id': eventId};
    }
    if (body == null) {
      if (stateDenied)
        throw const ApiException(403, 'Gebundene Quellen nicht freigegeben');
      return {'writes_allowed': true, 'eligible': false};
    }
    if (confirmationReply != null) await confirmationReply!.future;
    if (confirmationFailure != null)
      throw ApiException(
        confirmationFailure!,
        'Synthetische Antwort',
        requestResolution: requestResolution,
      );
    return {'id': '2' * 32, 'revision': 1, 'reason': body['reason']};
  }
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  Future<(CapacitySessionApi, BusinessSession)> start() async {
    final api = CapacitySessionApi();
    final active = BusinessSession(api: api);
    addTearDown(active.dispose);
    addTearDown(api.dispose);
    await active.load();
    return (api, active);
  }

  Future<void> uncertain(
    CapacitySessionApi api,
    BusinessSession session,
    String path,
  ) async {
    api.confirmationFailure = 0;
    await expectLater(
      session.command(key, path, {
        'reason': 'Unverändert',
        'confirmation': true,
      }),
      throwsA(isA<ApiException>()),
    );
    api.confirmationFailure = null;
  }

  for (final path in [oldPath, newPath]) {
    test(
      'pending $path survives generation change and replays exact original command',
      () async {
        final (api, session) = await start();
        await uncertain(api, session, path);
        final original = api.calls.last;
        expect(session.pendingDocumentComponentPath(eventId), path);
        api.generation = 2;
        final result = await session.repeatDocumentComponentCommand(eventId);
        final sent = api.calls.where((call) => call.body != null).toList();
        expect(sent.map((call) => call.path), [original.path, original.path]);
        expect(sent.map((call) => call.body), [original.body, original.body]);
        expect(result['reason'], 'Unverändert');
        expect(session.pending(key), false);
        expect(api.calls.any((c) => c.path.endsWith('/portions')), false);
        expect(
          api.calls.any(
            (c) => c.path == '/api/business/accounting/events/$eventId',
          ),
          true,
        );
        expect(
          api.calls.any(
            (c) =>
                c.path == '/api/business${path.substring(0, path.length - 8)}',
          ),
          true,
        );
      },
    );
  }
  test('server terminal conflict clears old pending, local generation check does not', () async {
    final (api, session) = await start();
    await uncertain(api, session, oldPath);
    api.generation = 2;
    await session.load();
    final before = api.calls.length;
    await expectLater(
      session.command(key, newPath, {
        'reason': 'Geändert',
        'confirmation': true,
      }),
      throwsA(isA<ApiException>().having((e) => e.status, 'status', 409)),
    );
    expect(api.calls.length, before);
    expect(session.pending(key), true);
    api.confirmationFailure = 409;
    api.requestResolution = 'not_accepted';
    await expectLater(
      session.repeatDocumentComponentCommand(eventId),
      throwsA(isA<ApiException>()),
    );
    expect(session.pending(key), false);
    expect(api.calls.last.path, '/api/business$oldPath');
  });
  for (final status in [0, 403, 404, 409, 423, 429, 500]) {
    test(
      'retry status $status preserves original path, body and request ID',
      () async {
        final (api, session) = await start();
        await uncertain(api, session, oldPath);
        final original = api.calls.last;
        api.generation = 2;
        api.confirmationFailure = status;
        await expectLater(
          session.repeatDocumentComponentCommand(eventId),
          throwsA(isA<ApiException>()),
        );
        expect(session.pendingDocumentComponentPath(eventId), oldPath);
        expect(api.calls.last.path, original.path);
        expect(api.calls.last.body, original.body);
      },
    );
  }
  for (final path in [oldPath, newPath]) {
    test(
      'unmarked gate conflict after preflight keeps $path retryable with its original ID',
      () async {
        final (api, session) = await start();
        await uncertain(api, session, path);
        final original = api.calls.last.body;
        api.confirmationFailure = 409;
        await expectLater(
          session.repeatDocumentComponentCommand(eventId),
          throwsA(
            isA<ApiException>().having(
              (e) => e.requestResolution,
              'resolution',
              isNull,
            ),
          ),
        );
        expect(session.pendingDocumentComponentPath(eventId), path);
        api.confirmationFailure = null;
        await session.repeatDocumentComponentCommand(eventId);
        expect(api.calls.where((c) => c.body != null).map((c) => c.body), [
          original,
          original,
          original,
        ]);
        expect(session.pending(key), false);
      },
    );
  }
  for (final gate in ['write', 'source', 'state']) {
    test(
      '$gate denial prevents cross-generation retry without discarding pending',
      () async {
        final (api, session) = await start();
        await uncertain(api, session, newPath);
        api.generation = 2;
        if (gate == 'write') api.writable = false;
        if (gate == 'source') api.sourceDenied = true;
        if (gate == 'state') api.stateDenied = true;
        await expectLater(
          session.repeatDocumentComponentCommand(eventId),
          throwsA(isA<ApiException>()),
        );
        expect(api.calls.where((c) => c.body != null), hasLength(1));
        expect(session.pending(key), true);
      },
    );
  }
  test('generation change during acknowledged component command cannot become local terminal conflict', () async {
    final (api, session) = await start();
    api.confirmationReply = Completer<void>();
    final response = session.command(key, oldPath, {'reason': 'Unverändert'});
    api.generation = 2;
    await session.load();
    api.confirmationReply!.complete();
    await expectLater(
      response,
      throwsA(isA<ApiException>().having((e) => e.status, 'status', 0)),
    );
    expect(session.pending(key), true);
    expect(
      (await session.repeatDocumentComponentCommand(eventId))['reason'],
      'Unverändert',
    );
    expect(session.pending(key), false);
  });
  test(
    'logout during source preflight drops pending and cannot submit a retry',
    () async {
      final (api, session) = await start();
      await uncertain(api, session, oldPath);
      api.sourceReply = Completer<void>();
      final retry = session.repeatDocumentComponentCommand(eventId);
      await Future<void>.delayed(Duration.zero);
      api.token = null;
      session.revoke();
      api.sourceReply!.complete();
      await expectLater(retry, throwsA(isA<ApiException>()));
      expect(session.pending(key), false);
      expect(api.calls.where((c) => c.body != null), hasLength(1));
    },
  );
  test(
    'original ACK during retry preflight never starts a replacement command',
    () async {
      final (api, session) = await start();
      api.confirmationReply = Completer<void>();
      final original = session.command(key, oldPath, {'reason': 'Unverändert'});
      api.sourceReply = Completer<void>();
      final retry = session.repeatDocumentComponentCommand(eventId);
      await Future<void>.delayed(Duration.zero);
      api.confirmationReply!.complete();
      await original;
      api.sourceReply!.complete();
      await expectLater(
        retry,
        throwsA(isA<ApiException>().having((e) => e.status, 'status', 409)),
      );
      expect(api.calls.where((c) => c.body != null), hasLength(1));
      expect(session.pending(key), false);
    },
  );
}

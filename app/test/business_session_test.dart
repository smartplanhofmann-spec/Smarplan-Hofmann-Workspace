import 'dart:async';
import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:smartplan_office/api.dart';
import 'package:smartplan_office/business_session.dart';

class BusinessTestApi extends OfficeApi {
  BusinessTestApi() : super(apiVersion: 'v1') {
    token = 'synthetic-session';
  }
  final calls = <({String path, Map<String, dynamic>? body})>[];
  Completer<dynamic>? delayed;
  bool missing = false, loseAck = false, readMode = false;
  List<String>? availableFeatures;
  @override
  Future<dynamic> call(String path, [Map<String, dynamic>? body]) async {
    calls.add((
      path: path,
      body: body == null
          ? null
          : jsonDecode(jsonEncode(body)) as Map<String, dynamic>,
    ));
    if (path.split('?').first == '/api/business/capabilities') {
      if (missing) throw const ApiException(404, 'Unbekannt');
      return {
        'storage_version': 7,
        'compatibility_mode': readMode ? 'legacy' : 'business',
        'readonly': readMode,
        'generation': 1,
        'capabilities': ['business_foundation', 'business_documents'],
        'permissions': ['contacts.read', 'documents.read'],
        if (availableFeatures != null) 'features': availableFeatures,
      };
    }
    if (delayed != null) return delayed!.future;
    if (loseAck) {
      loseAck = false;
      throw const ApiException(0, 'Antwort fehlt');
    }
    return {'id': 'a' * 32, 'revision': 1};
  }

  void logout() {
    token = null;
    notifyListeners();
  }
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  test('Additive feature support neither grants rights nor survives logout or removal', () async {
    final api = BusinessTestApi();
    final session = BusinessSession(api: api);
    addTearDown(session.dispose);
    addTearDown(api.dispose);
    await session.load();
    expect(session.hasFeature('quote_pricing'), isFalse);
    api.availableFeatures = ['quote_pricing'];
    await session.load();
    expect(session.hasFeature('quote_pricing'), isTrue);
    expect(session.can('finance.read'), isFalse);
    api.availableFeatures = null;
    await session.load();
    expect(session.features, isEmpty);
    api.availableFeatures = ['quote_pricing'];
    await session.load();
    api.logout();
    expect(session.features, isEmpty);
    expect(session.hasFeature('quote_pricing'), isFalse);
  });
  test(
    'Permissions come from server and unsupported modules remain absent',
    () async {
      final api = BusinessTestApi();
      final session = BusinessSession(api: api);
      addTearDown(session.dispose);
      addTearDown(api.dispose);
      await session.load();
      expect(session.supported, isTrue);
      expect(session.can('contacts.read'), isTrue);
      expect(session.can('finance.read'), isFalse);
      expect(session.hasModule('documents'), isTrue);
      expect(session.hasModule('inventory'), isFalse);
    },
  );
  test('Old server remains unsupported and offline grant makes no business request', () async {
    final api = BusinessTestApi()..missing = true;
    final session = BusinessSession(api: api);
    await session.load();
    expect(session.ready, isTrue);
    expect(session.supported, isFalse);
    session.dispose();
    api.token = 'offline_synthetic';
    api.calls.clear();
    final offline = BusinessSession(api: api);
    await offline.load();
    expect(api.calls, isEmpty);
    expect(offline.supported, isFalse);
    offline.dispose();
    api.dispose();
  });
  test(
    'Logout during a real asynchronous read drops its late result',
    () async {
      final api = BusinessTestApi();
      final session = BusinessSession(api: api);
      await session.load();
      api.delayed = Completer<dynamic>();
      final pending = session.read('/contacts');
      api.logout();
      api.delayed!.complete({
        'items': [
          {'name': 'Private synthetic contact'},
        ],
      });
      await expectLater(pending, throwsA(isA<ApiException>()));
      expect(session.denied, isTrue);
      expect(session.permissions, isEmpty);
      session.dispose();
      api.dispose();
    },
  );
  test('Uncertain retries keep exact body and request ID, changed edits are refused', () async {
    final api = BusinessTestApi();
    final session = BusinessSession(api: api);
    await session.load();
    api.loseAck = true;
    await expectLater(
      session.command('draft', '/documents', {'title': 'Original'}),
      throwsA(isA<ApiException>()),
    );
    final first = api.calls.last.body;
    await expectLater(
      session.command('draft', '/documents', {'title': 'Changed'}),
      throwsA(isA<ApiException>()),
    );
    await session.command('draft', '/documents', {'title': 'Original'});
    expect(api.calls.last.body, first);
    expect(first?['request_id'], matches(RegExp(r'^[a-f0-9]{32}$')));
    session.dispose();
    api.dispose();
  });
  test(
    'Read-only return mode keeps archives visible and refuses every command',
    () async {
      final api = BusinessTestApi()..readMode = true;
      final session = BusinessSession(api: api);
      await session.load();
      expect(session.supported, isTrue);
      expect(session.readonly, isTrue);
      expect(session.hasModule('documents'), isTrue);
      expect(session.can('documents.read'), isTrue);
      expect(session.canWrite('documents.read'), isFalse);
      final before = api.calls.length;
      await expectLater(
        session.command('forbidden', '/documents', {'title': 'Must not write'}),
        throwsA(isA<ApiException>().having((e) => e.status, 'status', 403)),
      );
      expect(api.calls.length, before);
      session.dispose();
      api.dispose();
    },
  );
}

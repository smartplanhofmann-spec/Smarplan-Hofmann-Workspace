import 'dart:async';

import 'package:flutter_test/flutter_test.dart';
import 'package:smartplan_office/api.dart';
import 'package:smartplan_office/business_session.dart';

class HeldCapabilitiesApi extends OfficeApi {
  HeldCapabilitiesApi() : super(apiVersion: 'v1') {
    token = 'synthetic-capability-actor';
  }
  int calls = 0;
  final replies = <Completer<dynamic>>[];
  @override
  Future<dynamic> call(String path, [Map<String, dynamic>? body]) {
    expect(path, '/api/business/capabilities');
    calls++;
    final c = Completer<dynamic>();
    replies.add(c);
    return c.future;
  }
}

Map<String, dynamic> capabilities({bool read = true, int generation = 1}) => {
  'compatibility_mode': 'business',
  'generation': generation,
  'storage_version': 13,
  'readonly': false,
  'features': ['accounting_historical_assets'],
  'capabilities': ['business_accounting_asset_openings'],
  'permissions': [if (read) 'finance.read', 'accounting.read'],
};
void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  test('synchronous listener joins the future published before the first loading notification', () async {
    final api = HeldCapabilitiesApi(), session = BusinessSession(api: api);
    addTearDown(session.dispose);
    Future<void>? reentrant;
    session.addListener(() {
      if (session.loading && reentrant == null) reentrant = session.load();
    });
    final first = session.load();
    expect(api.calls, 1);
    expect(identical(first, reentrant), true);
    api.replies.single.complete(capabilities());
    await Future.wait([first, reentrant!]);
    expect(session.loading, false);
  });
  test('parallel timer/workflow capability callers await the same actual read and receive revoked grants before continuing', () async {
    final api = HeldCapabilitiesApi(), session = BusinessSession(api: api);
    addTearDown(session.dispose);
    final first = session.load();
    api.replies.single.complete(capabilities());
    await first;
    expect(session.can('finance.read'), true);
    final timer = session.load(), workflow = session.load();
    var finished = false;
    workflow.then((_) {
      finished = true;
    });
    await Future<void>.delayed(Duration.zero);
    expect(
      finished,
      false,
      reason: 'Workflow must not continue on stale grants while periodic refresh remains held',
    );
    expect(identical(timer, workflow), true);
    expect(api.calls, 2);
    api.replies.last.complete(capabilities(read: false));
    await Future.wait([timer, workflow]);
    expect(session.loading, false);
    expect(session.can('finance.read'), false);
    final next = session.load();
    expect(api.calls, 3);
    api.replies.last.complete(capabilities(read: true, generation: 2));
    await next;
    expect(session.can('finance.read'), true);
    expect(session.generation, 2);
  });
  test('shared capability failure completes every waiter, retains error and permits actual retry', () async {
    final api = HeldCapabilitiesApi(), session = BusinessSession(api: api);
    addTearDown(session.dispose);
    final one = session.load(), two = session.load();
    api.replies.single.completeError(
      const ApiException(0, 'Synthetic network response lost'),
    );
    await Future.wait([one, two]);
    expect(session.loading, false);
    expect(session.error, 'Synthetic network response lost');
    expect(session.can('finance.read'), false);
    final retry = session.load();
    api.replies.last.complete(capabilities());
    await retry;
    expect(api.calls, 2);
    expect(session.error, null);
    expect(session.can('finance.read'), true);
  });
  test('old token or disposed session cannot receive a late shared capability response; new session has independent in-flight state', () async {
    for (final dispose in [false, true]) {
      final api = HeldCapabilitiesApi(), old = BusinessSession(api: api);
      final a = old.load(), b = old.load();
      if (dispose) {
        old.dispose();
      } else {
        api.token = 'synthetic-other-actor';
      }
      final replacement = BusinessSession(api: api);
      final next = replacement.load();
      expect(api.calls, 2);
      api.replies.first.complete(capabilities(generation: 1));
      await Future.wait([a, b]);
      expect(old.allowed, false);
      expect(old.permissions, isEmpty);
      api.replies.last.complete(capabilities(generation: 2));
      await next;
      expect(replacement.generation, 2);
      expect(replacement.can('finance.read'), true);
      replacement.dispose();
      if (!dispose) old.dispose();
    }
  });
}

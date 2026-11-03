import 'package:flutter_test/flutter_test.dart';
import 'package:smartplan_office/api.dart';
import 'package:smartplan_office/business_session.dart';

import 'business_customer_workspace_test.dart'
    show WorkspaceApi, projectId, customerId;

class RetryWorkspaceApi extends WorkspaceApi {
  int generation = 1;
  int? failure;
  String? resolution;
  @override
  Future<dynamic> call(String path, [Map<String, dynamic>? body]) async {
    if (body != null && failure != null) {
      calls.add((path: path, body: Map<String, dynamic>.from(body)));
      throw ApiException(
        failure!,
        'Synthetic response',
        requestResolution: resolution,
      );
    }
    final result = await super.call(path, body);
    if (path.contains('/capabilities')) result['generation'] = generation;
    return result;
  }
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  const key = 'customer-grant-$projectId', route = '/customer-workspace/grants';
  final body = <String, dynamic>{
    'project_id': projectId,
    'customer_id': customerId,
    'recipient_name': 'Synthetische Kundin',
    'recipient_email': 'customer@example.test',
    'expires_in_days': 7,
    'allow_upload': true,
    'confirmation': true,
  };
  Future<(RetryWorkspaceApi, BusinessSession)> start() async {
    final api = RetryWorkspaceApi();
    final session = BusinessSession(api: api, projectId: projectId);
    addTearDown(api.dispose);
    addTearDown(session.dispose);
    await session.load();
    return (api, session);
  }

  test('lost accepted grant replays the same nonce after capability generation changes', () async {
    final (api, session) = await start();
    api.loseCreate = true;
    await expectLater(
      session.command(key, route, body),
      throwsA(isA<ApiException>()),
    );
    final first = api.calls.lastWhere((call) => call.body != null).body;
    api.generation = 2;
    final reply = await session.repeatCustomerWorkspaceCommand(key);
    expect(reply['link_available'], false);
    expect(api.calls.lastWhere((call) => call.body != null).body, first);
    expect(api.grants, hasLength(1));
    expect(session.pending(key), false);
  });
  test(
    'unknown denials retain the nonce and known nonacceptance releases it',
    () async {
      final (api, session) = await start();
      for (final status in [0, 403, 404, 409, 423, 500]) {
        api.failure = status;
        await expectLater(
          session.command(key, route, body),
          throwsA(isA<ApiException>()),
        );
        expect(session.pending(key), true);
      }
      final original = api.calls.lastWhere((call) => call.body != null).body;
      api.permissions.remove('portal.manage');
      await expectLater(
        session.repeatCustomerWorkspaceCommand(key),
        throwsA(isA<ApiException>().having((e) => e.status, 'status', 403)),
      );
      expect(session.pending(key), true);
      api.permissions.add('portal.manage');
      api.failure = 409;
      api.resolution = 'not_accepted';
      await expectLater(
        session.repeatCustomerWorkspaceCommand(key),
        throwsA(isA<ApiException>()),
      );
      expect(session.pending(key), false);
      for (final call in api.calls.where((call) => call.body != null))
        expect(call.body, original);
    },
  );
}

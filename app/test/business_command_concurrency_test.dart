import 'dart:async';

import 'package:flutter_test/flutter_test.dart';
import 'package:smartplan_office/api.dart';
import 'package:smartplan_office/business_session.dart';

import 'business_session_test.dart' show BusinessTestApi;

class ScopedSessionApi extends BusinessTestApi {
  @override
  Future<dynamic> call(String path, [Map<String, dynamic>? body]) async {
    if (path.split('?').first == '/api/business/capabilities') {
      final result = businessMap(await super.call(path, body));
      result['permissions'] = path.contains('project_id=')
          ? ['planning.read', 'planning.write']
          : ['contacts.read'];
      return result;
    }
    return super.call(path, body);
  }
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  test('project entry reuses parent global pending state without inheriting rights', () async {
    final api = ScopedSessionApi();
    final global = BusinessSession(api: api);
    addTearDown(global.dispose);
    addTearDown(api.dispose);
    await global.load();
    final project = global.sharedProjectSession('a' * 32);
    await project.load();
    expect(project.canWrite('planning.write'), isTrue);
    expect(identical(project.sharedGlobalSession(), global), isTrue);
    expect(global.canWrite('planning.write'), isFalse);
    api.loseAck = true;
    await expectLater(
      global.command(
        'resource-custody-test',
        '/resource-custody/${'b' * 32}/profile',
        {'label': 'Original'},
      ),
      throwsA(isA<ApiException>()),
    );
    expect(
      project.sharedGlobalSession().pending('resource-custody-test'),
      isTrue,
    );
    api.logout();
    expect(global.pending('resource-custody-test'), isFalse);
    expect(project.allowed, isFalse);
  });

  test('standalone project owns separately authorized global session and revokes it', () async {
    final api = ScopedSessionApi();
    final project = BusinessSession(api: api, projectId: 'a' * 32);
    addTearDown(project.dispose);
    addTearDown(api.dispose);
    await project.load();
    final global = project.sharedGlobalSession();
    expect(global.projectId, isNull);
    expect(global.permissions, isEmpty);
    await global.load();
    expect(global.can('contacts.read'), isTrue);
    expect(global.canWrite('planning.write'), isFalse);
    expect(identical(project.sharedGlobalSession(), global), isTrue);
    project.revoke();
    expect(global.allowed, isFalse);
    expect(global.permissions, isEmpty);
  });

  test(
    'late duplicate acknowledgement cannot delete a newer pending command',
    () async {
      final api = BusinessTestApi();
      final session = BusinessSession(api: api);
      addTearDown(session.dispose);
      addTearDown(api.dispose);
      await session.load();
      final first = Completer<dynamic>(),
          duplicate = Completer<dynamic>(),
          next = Completer<dynamic>();
      api.delayed = first;
      final accepted = session.command('shared', '/personnel/expenses', {
        'title': 'Original',
      });
      api.delayed = duplicate;
      final late = session.command('shared', '/personnel/expenses', {
        'title': 'Original',
      });
      final lateCheck = expectLater(
        late,
        throwsA(isA<ApiException>().having((e) => e.status, 'uncertain', 0)),
      );
      first.complete({'id': 'a' * 32});
      await accepted;
      api.delayed = next;
      final newer = session.command('shared', '/personnel/expenses', {
        'title': 'Next',
      });
      duplicate.complete({'id': 'a' * 32});
      await lateCheck;
      expect(session.pending('shared'), isTrue);
      expect(
        session.pendingCommandValues(
          'shared',
          path: '/personnel/expenses',
        )?['title'],
        'Next',
      );
      next.complete({'id': 'b' * 32});
      await newer;
      expect(session.pending('shared'), isFalse);
    },
  );
}

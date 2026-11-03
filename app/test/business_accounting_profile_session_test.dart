import 'dart:async';

import 'package:flutter_test/flutter_test.dart';
import 'package:smartplan_office/api.dart';
import 'package:smartplan_office/business_session.dart';

import 'business_accounting_profile_test.dart' show ProfileApi, unknownProfile;

const key = 'accounting-profile', confirmPath = '/accounting/profile/confirm';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  Future<(ProfileApi, BusinessSession)> start({
    bool offline = false,
    String? projectId,
  }) async {
    final api = ProfileApi()
      ..rights = {'accounting.read', 'finance.read', 'accounting.admin'};
    final session = BusinessSession(
      api: api,
      offlineMode: offline,
      projectId: projectId,
    );
    addTearDown(session.dispose);
    addTearDown(api.dispose);
    await session.load();
    return (api, session);
  }

  Map<String, dynamic> body(ProfileApi api) => {
    'expected_revision': api.revision,
    'state_hash': api.profileState['state_hash'],
    'profile': unknownProfile,
    'reason': 'Ausdrückliche Inhaberangabe',
    'evidence_reference': 'SYN-INHABER',
    'preview_hash': 'b' * 64,
    'confirmation': true,
  };
  Future<void> lose(ProfileApi api, BusinessSession session) async {
    api.loseConfirm = true;
    await expectLater(
      session.command(key, confirmPath, body(api)),
      throwsA(isA<ApiException>().having((e) => e.status, 'status', 0)),
    );
    expect(session.pendingPreparationProfilePath(), confirmPath);
  }

  test('profile replay reads only its own fresh state and returns old result after new revision and generation', () async {
    final (api, session) = await start();
    await lose(api, session);
    final original = api.calls.lastWhere((c) => c.path.endsWith('/confirm'));
    final old = api.versions.first;
    api.addVersion(reason: 'Später erklärt');
    api.generation = 2;
    final result = await session.repeatPreparationProfileCommand();
    final sent = api.calls.where((c) => c.path.endsWith('/confirm')).toList();
    expect(sent.last.body, original.body);
    expect(result, old);
    expect(api.versions, hasLength(2));
    expect(session.pending(key), false);
    expect(
      api.calls.where(
        (c) =>
            c.path.contains('/accounting/events') ||
            c.path.contains('/components/') ||
            c.path.contains('/refunds/'),
      ),
      isEmpty,
    );
    expect(
      api.calls.any((c) => c.path == '/api/business/accounting/profile'),
      true,
    );
  });
  for (final status in [0, 403, 404, 409, 423, 429, 500]) {
    test(
      'first profile status $status retains exact original body and ID',
      () async {
        final (api, session) = await start();
        api.confirmStatus = status;
        await expectLater(
          session.command(key, confirmPath, body(api)),
          throwsA(isA<ApiException>()),
        );
        final original = api.calls.last;
        expect(session.pendingPreparationProfilePath(), confirmPath);
        api.confirmStatus = null;
        api.generation = 2;
        await session.repeatPreparationProfileCommand();
        expect(api.calls.last.body, original.body);
        expect(api.calls.last.path, original.path);
        expect(api.versions, hasLength(1));
        expect(session.pending(key), false);
      },
    );
    test(
      'accepted original profile remains retryable after gate status $status',
      () async {
        final (api, session) = await start();
        await lose(api, session);
        final original = api.calls.lastWhere(
          (c) => c.path.endsWith('/confirm'),
        );
        api.confirmStatus = status;
        await expectLater(
          session.repeatPreparationProfileCommand(),
          throwsA(isA<ApiException>()),
        );
        expect(session.pendingPreparationProfilePath(), confirmPath);
        api.confirmStatus = null;
        await session.repeatPreparationProfileCommand();
        expect(api.calls.last.body, original.body);
        expect(api.versions, hasLength(1));
      },
    );
  }
  test('only marked not accepted conflict releases the profile key for a new version', () async {
    final (api, session) = await start();
    api.beforeServer = true;
    await expectLater(
      session.command(key, confirmPath, body(api)),
      throwsA(isA<ApiException>()),
    );
    api.addVersion();
    await expectLater(
      session.repeatPreparationProfileCommand(),
      throwsA(
        isA<ApiException>().having(
          (e) => e.requestResolution,
          'resolution',
          'not_accepted',
        ),
      ),
    );
    expect(session.pending(key), false);
    expect(api.versions, hasLength(1));
  });
  test('different body and generation cannot replace the unresolved original locally', () async {
    final (api, session) = await start();
    await lose(api, session);
    api.generation = 2;
    await session.load();
    final count = api.calls.length;
    await expectLater(
      session.command(key, confirmPath, body(api)),
      throwsA(isA<ApiException>().having((e) => e.status, 'status', 409)),
    );
    expect(api.calls.length, count);
    expect(session.pending(key), true);
  });
  for (final gate in [
    'admin',
    'read',
    'feature',
    'module',
    'readonly',
    'disabled',
    'state',
    'writes',
  ]) {
    test(
      'fresh $gate blocks replay without losing original or sending confirm',
      () async {
        final (api, session) = await start();
        await lose(api, session);
        final count = api.calls
            .where((c) => c.path.endsWith('/confirm'))
            .length;
        if (gate == 'admin') api.rights.remove('accounting.admin');
        if (gate == 'read') api.rights.remove('finance.read');
        if (gate == 'feature') api.profileFeature = false;
        if (gate == 'module') api.profileModule = false;
        if (gate == 'readonly') api.readonly = true;
        if (gate == 'disabled') api.enabled = false;
        if (gate == 'state') api.profileDenied = true;
        if (gate == 'writes') api.writes = false;
        await expectLater(
          session.repeatPreparationProfileCommand(),
          throwsA(isA<ApiException>()),
        );
        expect(session.pending(key), true);
        expect(
          api.calls.where((c) => c.path.endsWith('/confirm')),
          hasLength(count),
        );
      },
    );
  }
  test(
    'profile exception is restricted to exact path and logical key',
    () async {
      final (api, session) = await start();
      api.confirmStatus = 403;
      await expectLater(
        session.command('different-operation', confirmPath, body(api)),
        throwsA(isA<ApiException>()),
      );
      expect(session.pending('different-operation'), false);
    },
  );
  test('generation change during accepted confirmation preserves exact request for replay', () async {
    final (api, session) = await start();
    api.confirmReply = Completer<void>();
    final operation = session.command(key, confirmPath, body(api));
    await Future<void>.delayed(Duration.zero);
    api.generation = 2;
    await session.load();
    api.confirmReply!.complete();
    await expectLater(
      operation,
      throwsA(isA<ApiException>().having((e) => e.status, 'status', 0)),
    );
    expect(session.pending(key), true);
    final old = api.calls.firstWhere((c) => c.path.endsWith('/confirm'));
    await session.repeatPreparationProfileCommand();
    expect(api.calls.last.body, old.body);
    expect(api.versions, hasLength(1));
  });
  test(
    'original ACK during retry state read cannot send a replacement request',
    () async {
      final (api, session) = await start();
      api.confirmReply = Completer<void>();
      final operation = session.command(key, confirmPath, body(api));
      await Future<void>.delayed(Duration.zero);
      api.stateReply = Completer<void>();
      final retry = session.repeatPreparationProfileCommand();
      await Future<void>.delayed(Duration.zero);
      api.confirmReply!.complete();
      await operation;
      api.stateReply!.complete();
      await expectLater(
        retry,
        throwsA(isA<ApiException>().having((e) => e.status, 'status', 409)),
      );
      expect(session.pending(key), false);
      expect(api.calls.where((c) => c.path.endsWith('/confirm')), hasLength(1));
    },
  );
  test(
    'logout discards pending and late acknowledgement cannot restore session',
    () async {
      final (api, session) = await start();
      api.confirmReply = Completer<void>();
      final operation = session.command(key, confirmPath, body(api));
      await Future<void>.delayed(Duration.zero);
      api.token = null;
      api.confirmReply!.complete();
      await expectLater(
        operation,
        throwsA(isA<ApiException>().having((e) => e.status, 'status', 401)),
      );
      expect(session.pending(key), false);
      expect(session.pendingPreparationProfilePath(), isNull);
    },
  );
  test(
    'preview is side effect free and needs admin, not finance write',
    () async {
      final (api, session) = await start();
      final draft = body(api)
        ..remove('confirmation')
        ..remove('preview_hash');
      final result = await session.previewPreparationProfile(draft);
      expect(result['profile'], unknownProfile);
      expect(api.versions, isEmpty);
      expect(session.pending(key), false);
      api.rights.remove('accounting.admin');
      api.rights.addAll(['accounting.prepare', 'finance.write']);
      await session.load();
      final count = api.calls.length;
      await expectLater(
        session.previewPreparationProfile(draft),
        throwsA(isA<ApiException>().having((e) => e.status, 'status', 403)),
      );
      expect(api.calls.length, count);
    },
  );
}

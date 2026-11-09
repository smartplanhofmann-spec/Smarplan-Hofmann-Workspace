import 'dart:convert';
import 'dart:io';

import 'package:cryptography/cryptography.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:smartplan_office/api.dart';
import 'package:smartplan_office/offline_vault.dart';
import 'package:smartplan_office/project_creation_journal.dart';

import 'offline_plans_test.dart' show TestDevice;

const account = 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa';
const instance = 'bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb';
const project = 'cccccccccccccccccccccccccccccccc';
const server = 'https://journal.example.test';
const scope = ProjectCreationScope(
  server: server,
  version: 'v1',
  accountId: account,
  instanceId: instance,
);
const command = {
  'request_id': 'dddddddddddddddddddddddddddddddd',
  'name': 'Montage Süd',
  'customer': 'Müller',
};

Future<Map<String, dynamic>> receipt() async {
  // Literal independent server canonicalization, including absent null fields.
  const canonical =
      '{"data":{"customer":"Müller","customer_id":null,"name":"Montage Süd","request_id":"dddddddddddddddddddddddddddddddd"},"operation":"core.project.create:v1"}';
  final hash = (await Sha256().hash(utf8.encode(canonical))).bytes
      .map((n) => n.toRadixString(16).padLeft(2, '0'))
      .join();
  return {
    'schema_version': 1,
    'instance_id': instance,
    'account_id': account,
    'request_id': command['request_id'],
    'request_hash': hash,
    'project_id': project,
  };
}

class JournalDevice extends TestDevice {
  JournalDevice(super.folder);
  @override
  Future<OfflineVault?> openExisting(String server, String user) async {
    final namespaceKey = '${await namespace(server)}.$user';
    final path = Directory('${folder.path}/$namespaceKey');
    if (!await path.exists() ||
        !await path.list().any((f) => f.uri.pathSegments.last.startsWith('state-')))
      return null;
    return open(server, user);
  }
}

class FailingVault extends OfflineVault {
  FailingVault(super.directory, super.key);
  @override
  Future<void> write(Map<String, dynamic> data) async =>
      throw const FileSystemException('Synthetic disk full');
}

class FailingDevice extends TestDevice {
  FailingDevice(super.folder);
  @override
  Future<OfflineVault> open(
    String server,
    String user, {
    bool create = false,
  }) async {
    final vault = await super.open(server, user, create: create);
    return FailingVault(vault.directory, vault.key);
  }
}

void main() {
  late Directory temp;
  late TestDevice device;
  late ProjectCreationJournal journal;
  Future<ProjectCreationJournalSession> open({
    ProjectCreationScope? current = scope,
  }) => journal.open(
    server: server,
    version: 'v1',
    accountId: account,
    scope: current,
  );
  setUp(() async {
    temp = await Directory.systemTemp.createTemp('project-journal-unit-');
    device = JournalDevice(temp);
    journal = ProjectCreationJournal(device: device);
  });
  tearDown(() async {
    await temp.delete(recursive: true);
  });

  test('encrypted exact command survives new journal and clears after a bound receipt', () async {
    final first = await open();
    await first.prepare(command, []);
    final bytes = await temp
        .list(recursive: true)
        .where((f) => f.path.endsWith('.enc'))
        .asyncMap((f) => File(f.path).readAsString())
        .toList();
    expect(bytes, hasLength(1));
    for (final secret in ['Montage', 'Müller', 'request_id', account, instance])
      expect(bytes.single, isNot(contains(secret)));
    journal = ProjectCreationJournal(device: device);
    final reopened = await open();
    expect(reopened.pending!['body'], command);
    await reopened.verifyReceipt(command, {'id': project}, await receipt());
    await reopened.clear(command);
    expect((await open()).pending, isNull);
  });

  test(
    'wrong hash, result, account or instance never clears the original',
    () async {
      final saved = await open();
      await saved.prepare(command, []);
      final original = await receipt();
      for (final patch in [
        {'request_hash': '0' * 64},
        {'account_id': 'e' * 32},
        {'instance_id': 'e' * 32},
        {'project_id': 'e' * 32},
        {'unexpected': true},
      ]) {
        await expectLater(
          saved.verifyReceipt(
            command,
            {'id': project},
            {...original, ...patch},
          ),
          throwsA(isA<ApiException>()),
        );
        expect(saved.pending!['body'], command);
      }
      await expectLater(
        saved.verifyReceipt(command, {'id': 'e' * 32}, original),
        throwsA(isA<ApiException>()),
      );
      expect((await open()).pending!['body'], command);
    },
  );

  test(
    'missing and changed company scope block without exposing saved customer',
    () async {
      await (await open()).prepare(command, []);
      for (final current in [
        null,
        const ProjectCreationScope(
          server: server,
          version: 'v1',
          accountId: account,
          instanceId: 'eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee',
        ),
      ]) {
        try {
          await open(current: current);
          fail('Expected scope refusal');
        } on ApiException catch (error) {
          expect(error.message, isNot(contains('Müller')));
          expect(error.message, isNot(contains('Montage')));
        }
      }
      expect((await open()).pending!['body'], command);
    },
  );

  test('another server or user sees no pending command', () async {
    await (await open()).prepare(command, []);
    for (final other in [
      const ProjectCreationScope(
        server: 'https://other.example.test',
        version: 'v1',
        accountId: account,
        instanceId: instance,
      ),
      const ProjectCreationScope(
        server: server,
        version: 'v1',
        accountId: 'eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee',
        instanceId: instance,
      ),
    ]) {
      final isolated = await journal.open(
        server: other.server,
        version: other.version,
        accountId: other.accountId,
        scope: other,
      );
      expect(isolated.pending, isNull);
    }
  });

  test(
    'corrupt newest commit fails closed and does not replay preceding state',
    () async {
      final saved = await open();
      await saved.prepare(command, []);
      await saved.clear(command);
      final commits = await temp
          .list(recursive: true)
          .where((f) => f.path.endsWith('.enc'))
          .toList();
      commits.sort((a, b) => a.path.compareTo(b.path));
      expect(commits, hasLength(2));
      await File(commits.last.path)
          .writeAsString('{"ciphertext":"broken"}', flush: true);
      await expectLater(
        open(),
        throwsA(
          isA<ApiException>().having(
            (e) => e.message,
            'message',
            contains('nichts gesendet'),
          ),
        ),
      );
      expect(await File(commits.first.path).exists(), isTrue);
    },
  );

  test(
    'concurrent fresh sessions cannot overwrite a first unknown command',
    () async {
      final first = await open(), second = await open();
      await first.prepare(command, []);
      await expectLater(
        second.prepare({...command, 'request_id': 'e' * 32}, []),
        throwsA(
          isA<ApiException>().having(
            (e) => e.requestResolution,
            'resolution',
            'not_accepted',
          ),
        ),
      );
      expect((await open()).pending!['body'], command);
    },
  );

  test(
    'write failure reports no dispatch and leaves no current pending state',
    () async {
      journal = ProjectCreationJournal(device: FailingDevice(temp));
      final saved = await open();
      await expectLater(
        saved.prepare(command, []),
        throwsA(
          isA<ApiException>().having(
            (e) => e.requestResolution,
            'resolution',
            'not_accepted',
          ),
        ),
      );
      expect(saved.pending, isNull);
    },
  );

  test('legacy absence reads no key and creates no encrypted store', () async {
    FlutterSecureStorage.setMockInitialValues({});
    const storage = FlutterSecureStorage();
    final productionDevice = OfflineDevice(
      storage: storage,
      root: () async => temp,
    );
    final legacy = await ProjectCreationJournal(device: productionDevice)
        .open(server: server, version: 'v1', accountId: account, scope: null);
    expect(legacy.pending, isNull);
    expect(await storage.readAll(), isEmpty);
    expect(await temp.list(recursive: true).toList(), isEmpty);
  });

  test(
    'concurrent first opens retain one encryption key and readable original',
    () async {
      FlutterSecureStorage.setMockInitialValues({});
      final firstDevice = OfflineDevice(root: () async => temp);
      final secondDevice = OfflineDevice(root: () async => temp);
      final stores = await Future.wait([
        firstDevice.open('synthetic-concurrent-key', account, create: true),
        secondDevice.open('synthetic-concurrent-key', account, create: true),
      ]);
      expect(
        await stores[0].key.extractBytes(),
        await stores[1].key.extractBytes(),
      );
      await stores[0].write({'original': command});
      final restarted = await secondDevice.open(
        'synthetic-concurrent-key',
        account,
      );
      expect((await restarted.read())!['original'], command);
    },
  );

  test(
    'quarantined original blocks legacy and current company without rollback',
    () async {
      await (await open()).prepare(command, []);
      final stored =
          (await temp
                  .list(recursive: true)
                  .where((file) => file.path.endsWith('.enc'))
                  .toList())
              .single;
      await File(stored.path).rename('${stored.path}.quarantine');
      await expectLater(open(), throwsA(isA<ApiException>()));
      await expectLater(open(current: null), throwsA(isA<ApiException>()));
    },
  );

  test('declared scope requires exact schema and authenticated account', () {
    final valid = {
      'schema_version': 1,
      'instance_id': instance,
      'account_id': account,
    };
    expect(
      ProjectCreationScope.fromServer(
        valid,
        server: server,
        version: 'v1',
        accountId: account,
      ).instanceId,
      instance,
    );
    for (final value in [
      null,
      {...valid, 'schema_version': 2},
      {...valid, 'account_id': 'e' * 32},
      {...valid, 'token': 'not-allowed'},
    ]) {
      expect(
        () => ProjectCreationScope.fromServer(
          value,
          server: server,
          version: 'v1',
          accountId: account,
        ),
        throwsA(isA<ApiException>()),
      );
    }
  });
}

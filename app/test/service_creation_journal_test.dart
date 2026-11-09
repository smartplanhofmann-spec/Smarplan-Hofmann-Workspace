import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:smartplan_office/api.dart';
import 'package:smartplan_office/offline_vault.dart';
import 'package:smartplan_office/project_creation_journal.dart';
import 'package:smartplan_office/service_creation_journal.dart';

const account = 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa';
const instance = 'bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb';
const server = 'https://service-journal.example.test';
const scope = ProjectCreationScope(
  server: server,
  version: 'v1',
  accountId: account,
  instanceId: instance,
);
const otherCompany = ProjectCreationScope(
  server: server,
  version: 'v1',
  accountId: account,
  instanceId: '22222222222222222222222222222222',
);

Map<String, dynamic> command() => {
  'request_id': '11111111111111111111111111111111',
  'revision': 0,
  'customer_id': 'cccccccccccccccccccccccccccccccc',
  'person_id': null,
  'project_id': 'dddddddddddddddddddddddddddddddd',
  'asset_id': null,
  'contract_id': null,
  'visit_id': null,
  'inquiry_id': null,
  'defect_id': null,
  'title': ' \tPrüfung e\u0301 / é 😀\n ',
  'kind': 'complaint',
  'priority': 'high',
  'responsible_id': 'ffffffffffffffffffffffffffffffff',
  'follow_up_on': '2028-02-29',
  'description':
      '\n Unveränderte Beschreibung\tmit Unicode 🛠 und Randspaces. \n',
};

String namespace(ProjectCreationScope current) => jsonEncode([
  'service-creation-journal-v1',
  current.server,
  current.version,
]);

class Gate {
  final entered = Completer<void>();
  final release = Completer<void>();
  Future<void> wait() async {
    entered.complete();
    await release.future;
  }

  void finish() {
    if (!release.isCompleted) release.complete();
  }
}

class ControlledDevice extends OfflineDevice {
  ControlledDevice(Directory folder) : super(root: () async => folder);
  Gate? nextRead, nextWrite;
  bool failWrite = false;
  int writes = 0;

  @override
  Future<OfflineVault> open(
    String server,
    String user, {
    bool create = false,
  }) async {
    final vault = await super.open(server, user, create: create);
    return ControlledVault(vault, this);
  }
}

class ControlledVault extends OfflineVault {
  ControlledVault(OfflineVault vault, this.device)
    : super(vault.directory, vault.key);
  final ControlledDevice device;

  @override
  Future<Map<String, dynamic>?> read() async {
    final value = await super.read();
    final gate = device.nextRead;
    device.nextRead = null;
    if (gate != null) await gate.wait();
    return value;
  }

  @override
  Future<void> write(Map<String, dynamic> value) async {
    device.writes++;
    final gate = device.nextWrite;
    device.nextWrite = null;
    if (gate != null) await gate.wait();
    if (device.failWrite) {
      device.failWrite = false;
      throw const FileSystemException('Synthetic write failure');
    }
    await super.write(value);
  }
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  late Directory temp;
  late ControlledDevice device;
  late ServiceCreationJournal journal;
  const storage = FlutterSecureStorage();

  Future<ServiceCreationJournalSession> open({
    ProjectCreationScope current = scope,
    void Function()? requireCurrent,
  }) => journal.open(scope: current, requireCurrent: requireCurrent);

  Future<OfflineVault> rawVault([ProjectCreationScope current = scope]) async {
    final vault = await device.open(namespace(current), current.accountId);
    await vault.read();
    return vault;
  }

  Future<Map<String, String>> files() async => {
    await for (final entry in temp.list(recursive: true, followLinks: false))
      if (entry is File)
        entry.path.substring(temp.path.length): base64Encode(
          await entry.readAsBytes(),
        ),
  };

  setUp(() async {
    FlutterSecureStorage.setMockInitialValues({});
    temp = await Directory.systemTemp.createTemp('service-creation-journal-');
    device = ControlledDevice(temp);
    journal = ServiceCreationJournal(device: device);
  });

  tearDown(() async {
    device.nextRead?.finish();
    device.nextWrite?.finish();
    await temp.delete(recursive: true);
  });

  test('manual command validation preserves Unicode and exact fields', () {
    final original = command();
    final checked = validateServiceCreationCommand(original);
    original['title'] = 'Changed after validation';
    expect(checked, command());
    expect(
      validateServiceCreationCommand({
        ...command(),
        'title': '😀' * 300,
      })['title'],
      '😀' * 300,
    );
    expect(
      validateServiceCreationCommand({
        ...command(),
        'description': 'é' * 10000,
      })['description'],
      'é' * 10000,
    );
    for (final key in command().keys) {
      expect(
        () => validateServiceCreationCommand(command()..remove(key)),
        throwsFormatException,
        reason: 'Missing $key must not be reconstructed',
      );
    }
    for (final patch in <Map<String, dynamic>>[
      {'id': '1' * 32},
      {'unknown': null},
      {'revision': 0.0},
      {'revision': false},
      {'revision': 1},
      {'request_id': 'A' * 32},
      {'request_id': '${'a' * 32}\n'},
      {'responsible_id': '${'b' * 32}\n'},
      {'customer_id': null},
      {'person_id': ''},
      {'responsible_id': 'short'},
      {'visit_id': '1' * 32},
      {'inquiry_id': '1' * 32},
      {'defect_id': '1' * 32},
      {'kind': 'other'},
      {'priority': 'other'},
      {'follow_up_on': '2027-02-29'},
      {'follow_up_on': '2028-2-29'},
      {'follow_up_on': '1899-12-31'},
      {'follow_up_on': '2201-01-01'},
      {'title': ''},
      {'title': ' \t\n\u0085\u00a0\u1680\u2000\u2028\u2029\u202f\u205f\u3000'},
      {'title': 'Bad\rtitle'},
      {'description': 'Bad\u0000description'},
      {'title': String.fromCharCode(0xd800)},
      {'description': String.fromCharCode(0xdc00)},
      {'title': '😀' * 301},
      {'description': 'é' * 10001},
    ]) {
      expect(
        () => validateServiceCreationCommand({...command(), ...patch}),
        throwsFormatException,
        reason: 'Invalid fields: ${patch.keys}',
      );
    }
    expect(
      serviceCreationCanonical({
        'z': [1, null],
        'a': 'e\u0301',
      }),
      '{"a":"é","z":[1,null]}',
    );
    expect(
      serviceCreationCanonical({'a': 'é'}),
      isNot(serviceCreationCanonical({'a': 'e\u0301'})),
    );
  });

  test(
    'encrypted exact original survives restart and only exact clear',
    () async {
      final session = await open();
      final input = command();
      final prepared = session.prepare(input);
      input['request_id'] = '9' * 32;
      input['description'] = 'Mutation while storage is pending';
      await prepared;
      expect(session.pending, command());
      session.pending!['title'] = 'Mutation of detached read';
      expect(session.pending, command());
      final before = await files();
      final encrypted = before.entries
          .where((entry) => entry.key.endsWith('.enc'))
          .map((entry) => utf8.decode(base64Decode(entry.value)))
          .single;
      for (final private in [
        'Prüfung',
        'Beschreibung',
        'request_id',
        account,
        instance,
      ]) {
        expect(encrypted, isNot(contains(private)));
      }
      journal = ServiceCreationJournal(
        device: OfflineDevice(root: () async => temp),
      );
      final restarted = await open();
      expect(restarted.pending, command());
      final reversed = Map<String, dynamic>.fromEntries(
        command().entries.toList().reversed,
      );
      await restarted.prepare(reversed);
      expect(await files(), before, reason: 'Exact retry needs no new commit');
      for (final changed in [
        {...command(), 'request_id': '9' * 32},
        {...command(), 'title': 'Different text'},
      ]) {
        await expectLater(
          restarted.prepare(changed),
          throwsA(isA<ApiException>()),
        );
        await expectLater(
          restarted.clear(changed),
          throwsA(isA<ApiException>()),
        );
        expect(restarted.pending, command());
      }
      await restarted.clear(command());
      expect(restarted.pending, isNull);
      expect((await open()).pending, isNull);
    },
  );

  test(
    'unresolved company binding is checked before private payload',
    () async {
      await (await open()).prepare(command());
      final beforeKeys = await storage.readAll();
      final vault = await rawVault();
      await vault.write({
        'schema_version': 1,
        'scope': scope.toJson(),
        'pending': 'SYN private malformed payload',
      });
      final beforeFiles = await files();
      await expectLater(
        open(current: otherCompany),
        throwsA(
          isA<ApiException>().having(
            (error) => error.message,
            'binding refusal without private validation',
            allOf(
              contains('ursprüngliche Unternehmensanmeldung'),
              isNot(contains('private')),
            ),
          ),
        ),
      );
      await expectLater(open(), throwsA(isA<ApiException>()));
      expect(await storage.readAll(), beforeKeys);
      expect(await files(), beforeFiles);
    },
  );

  test('empty old company journal can be prepared for a new company', () async {
    final first = await open();
    await first.prepare(command());
    await first.clear(command());
    final keys = await storage.readAll();
    final second = await open(current: otherCompany);
    expect(second.pending, isNull);
    final next = {...command(), 'request_id': '2' * 32};
    await second.prepare(next);
    expect((await open(current: otherCompany)).pending, next);
    await expectLater(open(), throwsA(isA<ApiException>()));
    expect(
      await storage.readAll(),
      keys,
      reason: 'Account key is never replaced',
    );
  });

  test(
    'server version and account isolate keys and encrypted originals',
    () async {
      await (await open()).prepare(command());
      final firstKeys = await storage.readAll();
      for (final other in [
        const ProjectCreationScope(
          server: 'https://other.example.test',
          version: 'v1',
          accountId: account,
          instanceId: instance,
        ),
        const ProjectCreationScope(
          server: server,
          version: 'v2',
          accountId: account,
          instanceId: instance,
        ),
        const ProjectCreationScope(
          server: server,
          version: 'v1',
          accountId: '33333333333333333333333333333333',
          instanceId: instance,
        ),
      ]) {
        final isolated = await open(current: other);
        expect(isolated.pending, isNull);
        await isolated.prepare({
          ...command(),
          'title': 'Other account original',
        });
      }
      final after = await storage.readAll();
      for (final entry in firstKeys.entries) {
        expect(after[entry.key], entry.value);
      }
      expect(after.length, 4);
      expect((await open()).pending, command());
    },
  );

  test('stale sessions cannot overwrite or clear a newer original', () async {
    final first = await open(), stale = await open();
    await first.prepare(command());
    await expectLater(
      stale.prepare({...command(), 'request_id': '2' * 32}),
      throwsA(isA<ApiException>()),
    );
    final clearer = await open(), staleClearer = await open();
    await clearer.clear(command());
    final next = {...command(), 'request_id': '2' * 32};
    await clearer.prepare(next);
    await expectLater(
      staleClearer.clear(command()),
      throwsA(isA<ApiException>()),
    );
    expect((await open()).pending, next);
  });

  test(
    'concurrent operations in one session cannot replace a pending ID',
    () async {
      final session = await open();
      final first = session.prepare(command());
      final second = expectLater(
        session.prepare({...command(), 'request_id': '2' * 32}),
        throwsA(isA<ApiException>()),
      );
      await first;
      await second;
      expect((await open()).pending, command());
    },
  );

  test('CAS catches another writer after the journal read', () async {
    final first = await open(), second = await open();
    final gate = Gate();
    device.nextWrite = gate;
    final firstResult = expectLater(
      first.prepare(command()),
      throwsA(isA<ApiException>()),
    );
    try {
      await gate.entered.future;
      final winner = {...command(), 'request_id': '2' * 32};
      await second.prepare(winner);
      gate.finish();
      await firstResult;
      expect((await open()).pending, winner);
    } finally {
      gate.finish();
      await firstResult;
    }
  });

  test('corrupt latest commit never rolls back to an older original', () async {
    final session = await open();
    await session.prepare(command());
    await session.clear(command());
    final commits =
        (await temp.list(recursive: true).toList())
            .whereType<File>()
            .where((file) => file.path.endsWith('.enc'))
            .toList()
          ..sort((a, b) => a.path.compareTo(b.path));
    expect(commits, hasLength(2));
    await commits.last.writeAsString('{"ciphertext":"broken"}', flush: true);
    final before = await files(), keys = await storage.readAll();
    await expectLater(open(), throwsA(isA<ApiException>()));
    await expectLater(session.prepare(command()), throwsA(isA<ApiException>()));
    expect(await files(), before);
    expect(await storage.readAll(), keys);
  });

  test(
    'quarantined or incompatible state is preserved and blocks writing',
    () async {
      final session = await open();
      await session.prepare(command());
      final commit = (await temp.list(recursive: true).toList())
          .whereType<File>()
          .singleWhere((file) => file.path.endsWith('.enc'));
      await commit.rename('${commit.path}.quarantine');
      final before = await files(), keys = await storage.readAll();
      await expectLater(open(), throwsA(isA<ApiException>()));
      await expectLater(session.clear(command()), throwsA(isA<ApiException>()));
      expect(await files(), before);
      expect(await storage.readAll(), keys);
    },
  );

  test('strict state and scope failures preserve every key and file', () async {
    await open();
    final vault = await rawVault();
    final valid = {
      'schema_version': 1,
      'scope': scope.toJson(),
      'pending': command(),
    };
    for (final invalid in <Map<String, dynamic>>[
      {...valid, 'unexpected': null},
      {...valid, 'schema_version': 1.0},
      {
        ...valid,
        'scope': {...scope.toJson(), 'unexpected': null},
      },
      {
        ...valid,
        'scope': {...scope.toJson(), 'account_id': '3' * 32},
      },
      {
        ...valid,
        'scope': {...scope.toJson(), 'instance_id': 'B' * 32},
      },
      {...valid, 'pending': command()..remove('description')},
      {
        ...valid,
        'pending': {...command(), 'revision': 1},
      },
    ]) {
      await vault.write(invalid);
      final before = await files(), keys = await storage.readAll();
      await expectLater(open(), throwsA(isA<ApiException>()));
      expect(await files(), before);
      expect(await storage.readAll(), keys);
    }
  });

  test('invalid requested binding creates no key or journal', () async {
    for (final invalid in [
      const ProjectCreationScope(
        server: server,
        version: 'v1',
        accountId: 'invalid',
        instanceId: instance,
      ),
      const ProjectCreationScope(
        server: server,
        version: 'v1',
        accountId: account,
        instanceId: 'invalid',
      ),
      const ProjectCreationScope(
        server: '',
        version: 'v1',
        accountId: account,
        instanceId: instance,
      ),
      const ProjectCreationScope(
        server: server,
        version: '',
        accountId: account,
        instanceId: instance,
      ),
    ]) {
      await expectLater(open(current: invalid), throwsA(isA<ApiException>()));
      expect(await files(), isEmpty);
      expect(await storage.readAll(), isEmpty);
    }
  });

  test('unknown encrypted schema never becomes an empty new journal', () async {
    await open();
    final vault = await rawVault();
    await vault.write({
      'schema_version': 2,
      'scope': scope.toJson(),
      'pending': null,
    });
    final before = await files(), keys = await storage.readAll();
    await expectLater(open(), throwsA(isA<ApiException>()));
    expect(await files(), before);
    expect(await storage.readAll(), keys);
  });

  test(
    'missing key never replaces the encryption key for retained ciphertext',
    () async {
      await (await open()).prepare(command());
      final before = await files();
      final keys = await storage.readAll();
      expect(keys, hasLength(1));
      await storage.delete(key: keys.keys.single);
      await expectLater(open(), throwsA(isA<ApiException>()));
      expect(await storage.readAll(), isEmpty);
      expect(await files(), before);
    },
  );

  test(
    'write failures keep the prior original and allow exact retry',
    () async {
      final session = await open();
      device.failWrite = true;
      await expectLater(
        session.prepare(command()),
        throwsA(
          isA<ApiException>().having(
            (error) => error.requestResolution,
            'no dispatch',
            'not_accepted',
          ),
        ),
      );
      expect(session.pending, isNull);
      await session.prepare(command());
      device.failWrite = true;
      await expectLater(session.clear(command()), throwsA(isA<ApiException>()));
      expect(session.pending, command());
      expect((await open()).pending, command());
    },
  );

  test(
    'quarantined ciphertext with a missing key never gets a new key',
    () async {
      await (await open()).prepare(command());
      final commit = (await temp.list(recursive: true).toList())
          .whereType<File>()
          .singleWhere((file) => file.path.endsWith('.enc'));
      await commit.rename('${commit.path}.quarantine');
      final keys = await storage.readAll();
      await storage.delete(key: keys.keys.single);
      final before = await files();
      await expectLater(open(), throwsA(isA<ApiException>()));
      expect(await storage.readAll(), isEmpty);
      expect(await files(), before);
    },
  );

  test('closed context is refused before opening storage', () async {
    await expectLater(
      open(requireCurrent: () => throw const ApiException(0, 'Closed')),
      throwsA(isA<ApiException>()),
    );
    expect(await files(), isEmpty);
    expect(await storage.readAll(), isEmpty);
  });

  test(
    'late read guard exposes no session and late clear sends no write',
    () async {
      await (await open()).prepare(command());
      var current = true;
      void guard() {
        if (!current) throw const ApiException(0, 'Closed');
      }

      final readGate = Gate();
      device.nextRead = readGate;
      final closedOpen = expectLater(
        open(requireCurrent: guard),
        throwsA(isA<ApiException>()),
      );
      try {
        await readGate.entered.future;
        current = false;
      } finally {
        readGate.finish();
        await closedOpen;
      }
      current = true;
      final session = await open(requireCurrent: guard);
      final before = await files(), count = device.writes;
      final clearGate = Gate();
      device.nextRead = clearGate;
      final closedClear = expectLater(
        session.clear(command()),
        throwsA(isA<ApiException>()),
      );
      try {
        await clearGate.entered.future;
        current = false;
      } finally {
        clearGate.finish();
        await closedClear;
      }
      expect(device.writes, count);
      expect(await files(), before);
      expect(() => session.pending, throwsA(isA<ApiException>()));
      expect((await open()).pending, command());
    },
  );

  test('late completed write remains bound to its captured company', () async {
    var current = true;
    final session = await open(
      requireCurrent: () {
        if (!current) throw const ApiException(0, 'Closed');
      },
    );
    final keys = await storage.readAll();
    final gate = Gate();
    device.nextWrite = gate;
    final prepared = expectLater(
      session.prepare(command()),
      throwsA(isA<ApiException>()),
    );
    try {
      await gate.entered.future;
      current = false;
    } finally {
      gate.finish();
      await prepared;
    }
    expect((await open()).pending, command());
    await expectLater(
      open(current: otherCompany),
      throwsA(isA<ApiException>()),
    );
    expect(await storage.readAll(), keys);
  });
}

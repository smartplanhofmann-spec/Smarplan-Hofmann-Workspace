import 'dart:convert';
import 'dart:io';

import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:smartplan_office/api.dart';
import 'package:smartplan_office/offline_vault.dart';
import 'package:smartplan_office/online_command_journal.dart';
import 'package:smartplan_office/project_creation_journal.dart';

const account = 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa';
const instance = 'bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb';
const scope = ProjectCreationScope(
  server: 'https://original.example.test',
  version: 'v1',
  accountId: account,
  instanceId: instance,
);
const slot = 'material-return:global';
Map<String, dynamic> original() => {
  'request_id': '1' * 32,
  'private': 'Original Müller e\u0301 🛠\n  unverändert ',
  'metres': 100001,
};
Map<String, dynamic> validate(Object? raw) {
  if (raw is! Map ||
      raw.length != 3 ||
      raw['request_id'] is! String ||
      raw['private'] is! String ||
      raw['metres'] is! int) {
    throw const FormatException('Synthetic invalid original');
  }
  return Map<String, dynamic>.from(raw);
}

class ControlledDevice extends OfflineDevice {
  ControlledDevice(Directory dir) : super(root: () async => dir);
  bool fail = false;
  @override
  Future<OfflineVault> open(
    String server,
    String user, {
    bool create = false,
  }) async =>
      ControlledVault(await super.open(server, user, create: create), this);
}

class ControlledVault extends OfflineVault {
  ControlledVault(OfflineVault vault, this.device)
    : super(vault.directory, vault.key);
  final ControlledDevice device;
  @override
  Future<void> write(Map<String, dynamic> value) async {
    if (device.fail) throw const FileSystemException('Synthetic write denied');
    await super.write(value);
  }
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  late Directory dir;
  late ControlledDevice device;
  Future<OnlineCommandJournalSession> open({
    ProjectCreationScope current = scope,
    String currentSlot = slot,
    void Function()? guard,
  }) => OnlineCommandJournal(device: device).open(
    scope: current,
    slot: currentSlot,
    validate: validate,
    requireCurrent: guard ?? () {},
  );
  Future<Map<String, String>> bytes() async => {
    await for (final file in dir.list(recursive: true, followLinks: false))
      if (file is File) file.path: base64Encode(await file.readAsBytes()),
  };
  setUp(() async {
    FlutterSecureStorage.setMockInitialValues({});
    dir = await Directory.systemTemp.createTemp('online-original-journal-');
    device = ControlledDevice(dir);
  });
  tearDown(() async {
    await dir.delete(recursive: true);
  });
  Future<void> discover() =>
      OnlineCommandJournal(device: device).requireNoPending(
        server: scope.server,
        version: scope.version,
        accountId: scope.accountId,
        slot: slot,
        requireCurrent: () {},
      );
  test(
    'older server discovery of an empty device creates neither files nor keys',
    () async {
      await discover();
      expect(await bytes(), isEmpty);
      expect(await const FlutterSecureStorage().readAll(), isEmpty);
    },
  );
  test('older server cannot bypass a retained original; resolved empty state is checked read-only', () async {
    final current = await open();
    await current.prepare(original());
    final before = await bytes();
    await expectLater(discover(), throwsA(isA<ApiException>()));
    expect(await bytes(), before);
    await current.clear(original());
    final resolved = await bytes();
    await discover();
    expect(await bytes(), resolved);
  });
  test('older server discovery cannot replace a missing key for retained ciphertext', () async {
    await (await open()).prepare(original());
    final before = await bytes();
    FlutterSecureStorage.setMockInitialValues({});
    await expectLater(discover(), throwsA(isA<ApiException>()));
    expect(await bytes(), before);
    expect(await const FlutterSecureStorage().readAll(), isEmpty);
  });
  test(
    'older server discovery never skips a corrupt newest snapshot',
    () async {
      final current = await open();
      await current.prepare(original());
      await current.clear(original());
      final entries = await dir
          .list(recursive: true)
          .where((v) => v.path.endsWith('.enc'))
          .toList();
      entries.sort((a, b) => a.path.compareTo(b.path));
      await File(entries.last.path).writeAsString('corrupt newest');
      final before = await bytes();
      await expectLater(discover(), throwsA(isA<ApiException>()));
      expect(await bytes(), before);
    },
  );
  test('new journal and device objects reopen exact encrypted original, not caller mutations', () async {
    final first = await open(), body = original();
    await first.prepare(body);
    body['private'] = 'Mutated';
    device = ControlledDevice(dir);
    final second = await open();
    expect(second.pending, original());
    final disk = (await bytes()).values
        .map((v) => utf8.decode(base64Decode(v)))
        .join();
    expect(disk, isNot(contains('Müller')));
    expect(disk, isNot(contains('metres')));
    final copy = second.pending!;
    copy['private'] = 'Mutated again';
    expect(second.pending, original());
    await second.clear(original());
    expect((await open()).pending, isNull);
  });
  test(
    'replacement company cannot inspect or overwrite unresolved original',
    () async {
      await (await open()).prepare(original());
      final before = await bytes();
      const other = ProjectCreationScope(
        server: 'https://original.example.test',
        version: 'v1',
        accountId: account,
        instanceId: 'cccccccccccccccccccccccccccccccc',
      );
      await expectLater(open(current: other), throwsA(isA<ApiException>()));
      expect(await bytes(), before);
      expect((await open()).pending, original());
    },
  );
  test('account host API and employee/project slots stay separate', () async {
    await (await open()).prepare(original());
    for (final other in [
      const ProjectCreationScope(
        server: 'https://elsewhere.example.test',
        version: 'v1',
        accountId: account,
        instanceId: instance,
      ),
      const ProjectCreationScope(
        server: 'https://original.example.test',
        version: 'v2',
        accountId: account,
        instanceId: instance,
      ),
      const ProjectCreationScope(
        server: 'https://original.example.test',
        version: 'v1',
        accountId: 'dddddddddddddddddddddddddddddddd',
        instanceId: instance,
      ),
    ]) {
      expect((await open(current: other)).pending, isNull);
    }
    expect((await open(currentSlot: 'mileage:${'e' * 32}')).pending, isNull);
    expect((await open()).pending, original());
  });
  test(
    'only a resolved empty journal may rebind to a replacement company',
    () async {
      final first = await open();
      await first.prepare(original());
      await first.clear(original());
      const other = ProjectCreationScope(
        server: 'https://original.example.test',
        version: 'v1',
        accountId: account,
        instanceId: 'cccccccccccccccccccccccccccccccc',
      );
      final rebound = await open(current: other);
      expect(rebound.pending, isNull);
      await rebound.prepare({...original(), 'request_id': '3' * 32});
      await expectLater(open(), throwsA(isA<ApiException>()));
      expect((await open(current: other)).pending?['request_id'], '3' * 32);
    },
  );
  test('concurrent windows cannot replace or clear a newer original', () async {
    final first = await open(), second = await open();
    await first.prepare(original());
    await expectLater(
      second.prepare({...original(), 'request_id': '2' * 32}),
      throwsA(isA<ApiException>()),
    );
    await expectLater(second.clear(original()), throwsA(isA<ApiException>()));
    expect((await open()).pending, original());
  });
  test('same original prepare is idempotent; different fields and clear are refused', () async {
    final current = await open();
    await current.prepare(original());
    final before = await bytes();
    await current.prepare(original());
    expect(await bytes(), before);
    await expectLater(
      current.prepare({...original(), 'metres': 100002}),
      throwsA(isA<ApiException>()),
    );
    await expectLater(
      current.clear({...original(), 'private': 'replacement'}),
      throwsA(isA<ApiException>()),
    );
    expect(await bytes(), before);
  });
  test('write failure cannot become a prepared command', () async {
    final current = await open();
    device.fail = true;
    await expectLater(
      current.prepare(original()),
      throwsA(
        isA<ApiException>().having(
          (e) => e.requestResolution,
          'resolution',
          'not_accepted',
        ),
      ),
    );
    device.fail = false;
    expect((await open()).pending, isNull);
  });
  test('clear failure preserves exact original for next launch', () async {
    final current = await open();
    await current.prepare(original());
    final before = await bytes();
    device.fail = true;
    await expectLater(current.clear(original()), throwsA(isA<ApiException>()));
    device.fail = false;
    expect(await bytes(), before);
    expect((await open()).pending, original());
  });
  test('corrupt newest ciphertext is preserved, never rolled back', () async {
    final current = await open();
    await current.prepare(original());
    await current.clear(original());
    final files = await dir
        .list(recursive: true)
        .where((v) => v.path.endsWith('.enc'))
        .toList();
    files.sort((a, b) => a.path.compareTo(b.path));
    await File(files.last.path).writeAsString('corrupt newest state');
    final before = await bytes();
    await expectLater(open(), throwsA(isA<ApiException>()));
    expect(await bytes(), before);
  });
  test('missing key never replaces retained encrypted originals', () async {
    await (await open()).prepare(original());
    final before = await bytes();
    FlutterSecureStorage.setMockInitialValues({});
    await expectLater(open(), throwsA(isA<ApiException>()));
    expect(await bytes(), before);
  });
  test('changed authentication guard blocks reads and writes without deleting original', () async {
    var active = true;
    void guard() {
      if (!active) throw const ApiException(403, 'Synthetic signed out');
    }

    final current = await open(guard: guard);
    await current.prepare(original());
    final before = await bytes();
    active = false;
    expect(() => current.pending, throwsA(isA<ApiException>()));
    expect(() => current.clear(original()), throwsA(isA<ApiException>()));
    expect(await bytes(), before);
    expect((await open()).pending, original());
  });
}

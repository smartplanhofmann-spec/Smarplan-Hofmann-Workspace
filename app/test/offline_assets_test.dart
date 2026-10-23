import 'dart:async';
import 'dart:convert';
import 'dart:io';
import 'dart:isolate';
import 'dart:typed_data';

import 'package:cryptography/cryptography.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:smartplan_office/offline_assets.dart';
import 'package:smartplan_office/offline_vault.dart';

File nativeFile(String path) => Zone.root.run(() => File(path));
Directory nativeDirectory(String path) => Zone.root.run(() => Directory(path));

class InterruptedFile implements File {
  InterruptedFile(this.file, {this.started, this.release});
  final File file;
  final Completer<void>? started;
  final Completer<void>? release;
  @override
  String get path => file.path;
  @override
  Future<File> create({bool recursive = false, bool exclusive = false}) =>
      file.create(recursive: recursive, exclusive: exclusive);
  @override
  Future<File> writeAsBytes(
    List<int> bytes, {
    FileMode mode = FileMode.write,
    bool flush = false,
  }) async {
    expect(flush, isTrue);
    expect(ascii.decode(bytes.take(8).toList()), 'SPASSET1');
    if (started != null) {
      await file.writeAsBytes(bytes, mode: mode, flush: flush);
      started!.complete();
      await release!.future;
      return file;
    }
    await file.writeAsBytes(bytes.take(24).toList(), mode: mode, flush: true);
    throw const FileSystemException('Synthetic interrupted ciphertext write');
  }

  @override
  dynamic noSuchMethod(Invocation invocation) => super.noSuchMethod(invocation);
}

class CollidingDirectory implements Directory {
  CollidingDirectory(this.directory, this.collisions);
  final Directory directory;
  final List<File> collisions;
  @override
  String get path => directory.path;
  @override
  Future<bool> exists() => directory.exists();
  @override
  Future<FileStat> stat() => directory.stat();
  @override
  Future<FileSystemEntity> delete({bool recursive = false}) =>
      directory.delete(recursive: recursive);
  @override
  Future<Directory> rename(String newPath) async {
    // Appear after the store's notFound check, at the actual rename boundary.
    await nativeDirectory(newPath).create();
    final existing = nativeFile('$newPath/original.enc');
    await existing.writeAsString(
      'Existing encrypted original sentinel',
      flush: true,
    );
    collisions.add(existing);
    return directory.rename(newPath);
  }

  @override
  dynamic noSuchMethod(Invocation invocation) => super.noSuchMethod(invocation);
}

Future<Map<String, dynamic>> isolatedPut(String path, int number) async {
  final key = SecretKey(List<int>.generate(32, (index) => index));
  final assets = EncryptedAssets(OfflineVault(Directory(path), key));
  return assets.put(
    Uint8List.fromList(utf8.encode('%PDF-1.7\nSynthetic isolate $number\n')),
    mediaType: 'application/pdf',
    filename: 'synthetic-$number.pdf',
  );
}

void main() {
  late Directory folder;
  late Directory account;
  late SecretKey key;
  late EncryptedAssets assets;
  late Uint8List original;
  const marker = 'SYNTHETIC PRIVATE ORIGINAL; no customer data 0123456789';

  Future<Map<String, dynamic>> put() => assets.put(
    original,
    mediaType: 'application/pdf',
    filename: 'Grundriss.pdf',
  );
  File assetFile(Map<String, dynamic> ref) =>
      File('${account.path}/assets/${ref['id']}/original.enc');
  Future<List<File>> allFiles() async => account.existsSync()
      ? await account
            .list(recursive: true, followLinks: false)
            .where((item) => item is File)
            .cast<File>()
            .toList()
      : [];

  setUp(() async {
    folder = await Directory.systemTemp.createTemp('smartplan-assets-test-');
    account = Directory('${folder.path}/serverhash.account-a');
    key = SecretKey(List<int>.generate(32, (index) => index));
    assets = EncryptedAssets(OfflineVault(account, key));
    original = Uint8List.fromList(utf8.encode('%PDF-1.7\n$marker\n%%EOF'));
  });
  tearDown(() async {
    await folder.delete(recursive: true);
  });

  test('Encrypted originals survive a fresh instance and contain no plaintext artifacts', () async {
    final ref = await put();
    expect(ref['size'], original.length);
    expect(ref['media_type'], 'application/pdf');
    expect(ref['filename'], 'Grundriss.pdf');
    expect(ref['id'], matches(RegExp(r'^[a-f0-9]{32}$')));
    expect(ref['sha256'], matches(RegExp(r'^[a-f0-9]{64}$')));
    final reopened = EncryptedAssets(OfflineVault(account, key));
    expect(await reopened.read(ref), original);
    final files = await allFiles();
    expect(files, hasLength(1));
    final ciphertext = await files.single.readAsBytes();
    expect(ciphertext.length, original.length + 36);
    expect(ascii.decode(ciphertext.sublist(0, 8)), 'SPASSET1');
    expect(latin1.decode(ciphertext), isNot(contains(marker)));
    if (!Platform.isWindows) {
      expect((await Directory('${account.path}/assets').stat()).mode & 0x3f, 0);
      expect((await assetFile(ref).parent.stat()).mode & 0x3f, 0);
    }
  });

  test('Caller mutation cannot change bytes or references while awaits are pending', () async {
    final expected = Uint8List.fromList(original);
    final writing = put();
    original.fillRange(0, original.length, 0);
    final ref = await writing;
    expect(await assets.read(ref), expected);
    final reading = assets.read(ref);
    ref['filename'] = 'changed-after-read-start.pdf';
    expect(await reading, expected);
  });

  test(
    'Magic, nonce, MAC, ciphertext and encryption-key changes fail closed',
    () async {
      final ref = await put();
      final file = assetFile(ref);
      final pristine = await file.readAsBytes();
      for (final offset in [0, 8, 20, 36, pristine.length - 1]) {
        final changed = Uint8List.fromList(pristine)..[offset] ^= 1;
        await file.writeAsBytes(changed, flush: true);
        await expectLater(assets.read(ref), throwsA(anything));
      }
      await file.writeAsBytes(pristine, flush: true);
      final wrong = EncryptedAssets(
        OfflineVault(account, SecretKey(List<int>.filled(32, 99))),
      );
      await expectLater(wrong.read(ref), throwsA(anything));
      expect(await assets.read(ref), original);
    },
  );

  test(
    'References authenticate hash, size, MIME, filename and asset identity',
    () async {
      final ref = await put();
      for (final change in [
        {'sha256': '0' * 64},
        {'size': ref['size'] + 1},
        {'media_type': 'image/png'},
        {'filename': 'other.pdf'},
      ]) {
        await expectLater(assets.read({...ref, ...change}), throwsA(anything));
      }
      final id = 'f' * 32;
      final copy = await Directory('${account.path}/assets')
          .createTemp('.copy-');
      await assetFile(ref).copy('${copy.path}/original.enc');
      await copy.rename('${account.path}/assets/$id');
      await expectLater(assets.read({...ref, 'id': id}), throwsA(anything));
      expect(await assets.read(ref), original);
    },
  );

  test('The stable account namespace authenticates files but permits container relocation', () async {
    final ref = await put();
    final other = Directory('${folder.path}/serverhash.account-b');
    final otherAssets = EncryptedAssets(OfflineVault(other, key));
    final otherRef = await otherAssets.put(
      original,
      mediaType: 'application/pdf',
      filename: 'Grundriss.pdf',
    );
    final otherDirectory = Directory('${other.path}/assets/${otherRef['id']}');
    await otherDirectory.delete(recursive: true);
    // Recreate via a private temp directory so a permission failure cannot mask
    // the authentication failure we want to exercise.
    final privateCopy = await Directory('${other.path}/assets')
        .createTemp('.copy-');
    await assetFile(ref).copy('${privateCopy.path}/original.enc');
    await privateCopy.rename('${other.path}/assets/${ref['id']}');
    await expectLater(otherAssets.read(ref), throwsA(anything));
    final movedParent = await Directory('${folder.path}/moved-container')
        .create();
    account = await account.rename('${movedParent.path}/serverhash.account-a');
    final moved = EncryptedAssets(OfflineVault(account, key));
    expect(await moved.read(ref), original);
  });

  test('MIME and filename guards reject unsupported sources before writing anything', () async {
    for (final media in [
      'image/heic',
      'image/png',
      'text/plain',
      'application/PDF',
    ]) {
      await expectLater(
        assets.put(original, mediaType: media, filename: 'test.pdf'),
        throwsFormatException,
      );
    }
    for (final name in [
      '',
      ' ',
      '.',
      '..',
      '../file.pdf',
      '/absolute.pdf',
      'a\\b.pdf',
      'a\u0000.pdf',
      'x' * 201,
    ]) {
      await expectLater(
        assets.put(original, mediaType: 'application/pdf', filename: name),
        throwsFormatException,
      );
    }
    await expectLater(
      assets.put(
        Uint8List.fromList([1, 2, 3]),
        mediaType: 'image/jpeg',
        filename: 'test.jpg',
      ),
      throwsFormatException,
    );
    expect(await account.exists(), isFalse);
  });

  test(
    'Matching JPEG and PNG signatures preserve the original bytes',
    () async {
      for (final sample in [
        (
          'image/jpeg',
          'synthetic.jpg',
          [255, 216, 255, 224, ...utf8.encode(marker)],
        ),
        (
          'image/png',
          'synthetic.png',
          [137, 80, 78, 71, 13, 10, 26, 10, ...utf8.encode(marker)],
        ),
      ]) {
        final bytes = Uint8List.fromList(sample.$3);
        final ref = await assets.put(
          bytes,
          mediaType: sample.$1,
          filename: sample.$2,
        );
        expect(await assets.read(ref), bytes);
      }
    },
  );

  test('Size limits reject empty and oversized originals and accept exactly 20 MiB', () async {
    await expectLater(
      assets.put(
        Uint8List(0),
        mediaType: 'application/pdf',
        filename: 'empty.pdf',
      ),
      throwsFormatException,
    );
    await expectLater(
      assets.put(
        Uint8List(EncryptedAssets.maxBytes + 1),
        mediaType: 'application/pdf',
        filename: 'large.pdf',
      ),
      throwsFormatException,
    );
    expect(await account.exists(), isFalse);
    final bytes = Uint8List(EncryptedAssets.maxBytes)
      ..setRange(0, 5, ascii.encode('%PDF-'));
    final ref = await assets.put(
      bytes,
      mediaType: 'application/pdf',
      filename: 'boundary.pdf',
    );
    expect(await assets.read(ref), bytes);
  }, timeout: const Timeout(Duration(minutes: 2)));

  test(
    'Oversized or truncated encrypted files fail before decryption',
    () async {
      final ref = await put();
      final file = assetFile(ref);
      final pristine = await file.readAsBytes();
      await file.writeAsBytes([...pristine, 0]);
      await expectLater(assets.read(ref), throwsFormatException);
      await file.writeAsBytes(pristine.sublist(0, 15));
      await expectLater(assets.read(ref), throwsFormatException);
    },
  );

  test(
    'Symlink roots, asset directories and original files are refused',
    () async {
      if (Platform.isWindows)
        return; // Link creation may require OS privileges.
      final ref = await put();
      final rootAlias = Link('${folder.path}/root-alias');
      await rootAlias.create(account.path);
      await expectLater(
        EncryptedAssets(OfflineVault(Directory(rootAlias.path), key)).read(ref),
        throwsA(isA<FileSystemException>()),
      );
      final file = assetFile(ref);
      final external = File('${folder.path}/external.bin');
      await file.copy(external.path);
      await file.delete();
      await Link(file.path).create(external.path);
      await expectLater(assets.read(ref), throwsA(isA<FileSystemException>()));
      expect(await external.readAsBytes(), isNotEmpty);
      await Link(file.path).delete();
      final assetDirectory = file.parent;
      final backup = await assetDirectory.rename('${account.path}/backup');
      await Link(assetDirectory.path).create(backup.path);
      await expectLater(assets.read(ref), throwsA(isA<FileSystemException>()));
    },
  );

  test('A symlink assets directory cannot receive new originals', () async {
    if (Platform.isWindows) return;
    await account.create();
    final external = await Directory('${folder.path}/external').create();
    await Link('${account.path}/assets').create(external.path);
    await expectLater(put(), throwsA(isA<FileSystemException>()));
    expect(await external.list().toList(), isEmpty);
  });

  test('Interrupted writes retain old assets and never leave plaintext temporary files', () async {
    final existing = await put();
    await IOOverrides.runZoned(
      () async {
        await expectLater(put(), throwsA(isA<FileSystemException>()));
      },
      createFile: (path) {
        final file = nativeFile(path);
        return path.contains('/.pending-') && path.endsWith('/original.enc')
            ? InterruptedFile(file)
            : file;
      },
    );
    expect(await assets.read(existing), original);
    expect(await allFiles(), hasLength(1));
  });

  test('A pending write contains ciphertext and is not acknowledged before atomic publication', () async {
    final started = Completer<void>(), release = Completer<void>();
    await IOOverrides.runZoned(
      () async {
        var acknowledged = false;
        final writing = put().then((ref) {
          acknowledged = true;
          return ref;
        });
        await started.future;
        expect(acknowledged, isFalse);
        final file = (await allFiles()).single;
        expect(file.path, contains('.pending-'));
        final encrypted = await file.readAsBytes();
        expect(latin1.decode(encrypted), isNot(contains(marker)));
        release.complete();
        final ref = await writing;
        expect(await assets.read(ref), original);
      },
      createFile: (path) {
        final file = nativeFile(path);
        return path.contains('/.pending-') && path.endsWith('/original.enc')
            ? InterruptedFile(file, started: started, release: release)
            : file;
      },
    );
  });

  test(
    'A destination appearing at rename cannot overwrite an existing original',
    () async {
      final existing = await put();
      final collisions = <File>[];
      await IOOverrides.runZoned(
        () async {
          await expectLater(put(), throwsA(isA<FileSystemException>()));
        },
        createDirectory: (path) {
          final directory = nativeDirectory(path);
          return path.contains('/assets/.pending-')
              ? CollidingDirectory(directory, collisions)
              : directory;
        },
      );
      expect(collisions, hasLength(1));
      expect(
        await collisions.single.readAsString(),
        'Existing encrypted original sentinel',
      );
      expect(await assets.read(existing), original);
    },
  );

  test(
    'Concurrent instances and isolates publish separate immutable originals',
    () async {
      final path = account.path;
      final futures = [
        for (var index = 0; index < 5; index++)
          EncryptedAssets(OfflineVault(account, key)).put(
            original,
            mediaType: 'application/pdf',
            filename: 'parallel-$index.pdf',
          ),
        for (var index = 0; index < 2; index++)
          Isolate.run(() => isolatedPut(path, index)),
      ];
      final references = await Future.wait(futures);
      expect(references.map((ref) => ref['id']).toSet(), hasLength(7));
      for (final ref in references) {
        expect(await assets.read(ref), isNotEmpty);
      }
      final files = await allFiles();
      expect(files, hasLength(7));
      expect(
        files.every((file) => file.path.endsWith('/original.enc')),
        isTrue,
      );
    },
  );

  test('Recognition cache is encrypted separately and freezes nested candidate data', () async {
    final result = <String, dynamic>{
      'schema_version': 1,
      'status': 'needs_review',
      'analysis': {'text': marker, 'lines': <dynamic>[]},
    };
    final expected = jsonDecode(jsonEncode(result));
    final writing = assets.putRecognition(result);
    (result['analysis'] as Map)['text'] = 'Changed after save began';
    final ref = await writing;
    expect(ref['media_type'], 'application/json');
    expect(ref['filename'], 'recognition.json');
    final reopened = EncryptedAssets(OfflineVault(account, key));
    expect(jsonDecode(utf8.decode(await reopened.read(ref))), expected);
    for (final file in await allFiles()) {
      expect(latin1.decode(await file.readAsBytes()), isNot(contains(marker)));
    }
  });

  test(
    'Only internal finite schema-1 review results enter the recognition cache',
    () async {
      for (final result in <Map<String, dynamic>>[
        {},
        {'schema_version': true, 'status': 'needs_review'},
        {'schema_version': 2, 'status': 'needs_review'},
        {'schema_version': 1, 'status': 'published'},
        {'schema_version': 1, 'status': 'needs_review', 'value': double.nan},
        {
          'schema_version': 1,
          'status': 'needs_review',
          'text': 'x' * (EncryptedAssets.maxRecognitionBytes + 1),
        },
      ]) {
        await expectLater(assets.putRecognition(result), throwsFormatException);
      }
      await expectLater(
        assets.put(
          Uint8List.fromList(
            utf8.encode('{"schema_version":1,"status":"needs_review"}'),
          ),
          mediaType: 'application/json',
          filename: 'recognition.json',
        ),
        throwsFormatException,
      );
      expect(await account.exists(), isFalse);
    },
  );

  test('Recognition size limit is exactly one MiB', () async {
    final result = <String, dynamic>{
      'schema_version': 1,
      'status': 'needs_review',
      'text': '',
    };
    final overhead = utf8.encode(jsonEncode(result)).length;
    result['text'] = 'x' * (EncryptedAssets.maxRecognitionBytes - overhead);
    final ref = await assets.putRecognition(result);
    expect(ref['size'], EncryptedAssets.maxRecognitionBytes);
    expect(
      (await assets.read(ref)).length,
      EncryptedAssets.maxRecognitionBytes,
    );
    result['text'] = '${result['text']}x';
    await expectLater(assets.putRecognition(result), throwsFormatException);
    await expectLater(
      assets.read({...ref, 'size': EncryptedAssets.maxRecognitionBytes + 1}),
      throwsFormatException,
    );
  });
}

import 'dart:convert';
import 'dart:io';
import 'dart:math';

import 'package:cryptography/cryptography.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:flutter/services.dart';
import 'package:local_auth/local_auth.dart';
import 'package:path_provider/path_provider.dart';

String offlineId() => List.generate(
  16,
  (_) => Random.secure().nextInt(256).toRadixString(16).padLeft(2, '0'),
).join();
Map<String, dynamic> offlineCopy(Map<String, dynamic> value) =>
    Map<String, dynamic>.from(jsonDecode(jsonEncode(value)));

/// Immutable encrypted snapshots. A failed write leaves the last commit intact.
/// A corrupt newest commit is an error, never a silent rollback of user edits.
class OfflineVault {
  final Directory directory;
  final SecretKey key;
  int generation = 0;
  static final Map<String, Future<void>> _writers = {};
  OfflineVault(this.directory, this.key);
  Future<Map<String, dynamic>?> read() async {
    if (!await directory.exists()) return null;
    final files = await directory
        .list()
        .where((f) => RegExp(r'state-\d{16}\.enc$').hasMatch(f.path))
        .toList();
    files.sort((a, b) => a.path.compareTo(b.path));
    if (files.isEmpty) return null;
    final file = File(files.last.path);
    final envelope =
        jsonDecode(await file.readAsString()) as Map<String, dynamic>;
    final plaintext = await AesGcm.with256bits().decrypt(
      SecretBox(
        base64Decode(envelope['ciphertext']),
        nonce: base64Decode(envelope['nonce']),
        mac: Mac(base64Decode(envelope['mac'])),
      ),
      secretKey: key,
    );
    final data = Map<String, dynamic>.from(jsonDecode(utf8.decode(plaintext)));
    generation = data.remove('_generation') as int;
    if (generation !=
        int.parse(RegExp(r'state-(\d{16})\.enc$').firstMatch(file.path)![1]!))
      throw const FormatException(
        'Offline-Speicherstand stimmt nicht überein.',
      );
    return data;
  }

  Future<void> write(Map<String, dynamic> data) {
    final name = directory.absolute.path;
    final next = (_writers[name] ?? Future<void>.value()).then(
      (_) => _writeLocked(data),
    );
    _writers[name] = next.then<void>(
      (_) {},
      onError: (Object e, StackTrace s) {},
    );
    return next;
  }

  Future<void> _writeLocked(Map<String, dynamic> data) async {
    await directory.create(recursive: true);
    final lock = await File('${directory.path}/writer.lock')
        .open(mode: FileMode.append);
    try {
      await lock.lock(FileLock.blockingExclusive);
      final commits = await directory
          .list()
          .where((f) => RegExp(r'state-\d{16}\.enc$').hasMatch(f.path))
          .toList();
      commits.sort((a, b) => a.path.compareTo(b.path));
      final latest = commits.isEmpty
          ? 0
          : int.parse(
              RegExp(r'state-(\d{16})\.enc$')
                  .firstMatch(commits.last.path)![1]!,
            );
      if (latest != generation)
        throw const FileSystemException(
          'Offline-Speicher wurde in einem anderen Fenster geändert. Neu öffnen.',
        );
      await _writeSnapshot(data);
    } finally {
      await lock.unlock();
      await lock.close();
    }
  }

  Future<void> _writeSnapshot(Map<String, dynamic> data) async {
    await directory.create(recursive: true);
    final next = generation + 1;
    final box = await AesGcm.with256bits().encrypt(
      utf8.encode(jsonEncode({...data, '_generation': next})),
      secretKey: key,
    );
    final name =
        '${directory.path}/state-${next.toString().padLeft(16, '0')}.enc';
    final temp = File('$name.${offlineId()}.tmp');
    try {
      await temp.writeAsString(
        jsonEncode({
          'ciphertext': base64Encode(box.cipherText),
          'nonce': base64Encode(box.nonce),
          'mac': base64Encode(box.mac.bytes),
        }),
        flush: true,
      );
      if (await File(name).exists())
        throw const FileSystemException(
          'Offline-Speicher wird bereits verwendet.',
        );
      await temp.rename(name);
      generation = next;
    } finally {
      if (await temp.exists()) await temp.delete();
    }
    // Keep the preceding commit too. Cleanup must not make a committed save fail.
    try {
      await for (final file in directory.list()) {
        final match = RegExp(r'state-(\d{16})\.enc$').firstMatch(file.path);
        if (match != null && int.parse(match[1]!) < generation - 1)
          await file.delete();
      }
    } catch (_) {
      /* Retaining an older encrypted commit is harmless. */
    }
  }
}

class OfflineDevice {
  final FlutterSecureStorage storage;
  final Future<Directory> Function() root;
  final Future<bool> Function() unlock;
  OfflineDevice({
    FlutterSecureStorage? storage,
    Future<Directory> Function()? root,
    Future<bool> Function()? unlock,
  }) : storage =
           storage ??
           const FlutterSecureStorage(
             iOptions: IOSOptions(
               accessibility: KeychainAccessibility.unlocked_this_device,
             ),
           ),
       root = root ?? getApplicationSupportDirectory,
       unlock =
           unlock ??
           (() => LocalAuthentication().authenticate(
             localizedReason: 'Smartplan-Pläne auf diesem Gerät entsperren',
           ));
  Future<String> namespace(String server) async =>
      (await Sha256().hash(utf8.encode(server))).bytes
          .map((n) => n.toRadixString(16).padLeft(2, '0'))
          .join();
  Future<String?> selected(String server) async =>
      storage.read(key: 'smartplan.account.${await namespace(server)}');
  Future<void> select(String server, String user) async => storage.write(
    key: 'smartplan.account.${await namespace(server)}',
    value: user,
  );
  Future<void> saveSession(String server, String user, String? token) async {
    final key = 'smartplan.session.${await namespace(server)}.$user';
    if (token == null) {
      await storage.delete(key: key);
    } else {
      await storage.write(key: key, value: token);
    }
  }

  Future<String?> session(String server, String user) async =>
      storage.read(key: 'smartplan.session.${await namespace(server)}.$user');
  Future<OfflineVault> open(
    String server,
    String user, {
    bool create = false,
  }) async {
    if (!RegExp(r'^[a-f0-9]{32}$').hasMatch(user))
      throw StateError('Ungültiger Offline-Benutzer.');
    final scope = '${await namespace(server)}.$user';
    final keyName = 'smartplan.key.$scope';
    final directory = Directory(
      '${(await root()).path}/smartplan-offline/$scope',
    );
    if (Platform.isIOS && (create || await directory.exists())) {
      await directory.create(recursive: true);
      await const MethodChannel('smartplan/offline-storage')
          .invokeMethod<void>('protectDirectory', directory.path);
    }
    var encoded = await storage.read(key: keyName);
    if (encoded == null) {
      if (!create ||
          (await directory.exists() &&
              await directory.list().any((f) => f.path.endsWith('.enc'))))
        throw StateError('Offline-Schlüssel fehlt. Online anmelden.');
      encoded = base64Encode(
        await AesGcm.with256bits().newSecretKey().then(
          (key) => key.extractBytes(),
        ),
      );
      await storage.write(key: keyName, value: encoded);
      if (await storage.read(key: keyName) != encoded)
        throw StateError(
          'Offline-Schlüssel konnte nicht sicher gespeichert werden.',
        );
    }
    return OfflineVault(directory, SecretKey(base64Decode(encoded)));
  }
}

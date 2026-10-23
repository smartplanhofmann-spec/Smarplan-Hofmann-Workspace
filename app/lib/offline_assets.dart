import 'dart:convert';
import 'dart:io';
import 'dart:typed_data';

import 'package:cryptography/cryptography.dart';

import 'offline_vault.dart';

/// Immutable encrypted originals in the vault's existing account/server scope.
///
/// Only ciphertext is written. A successful put precedes the caller's metadata
/// commit; an interrupted metadata commit may leave an unreferenced asset. No
/// asset is removed here. dart:io flushes the file but exposes no directory fsync;
/// native device acceptance remains necessary for filesystem/OS protection.
class EncryptedAssets {
  EncryptedAssets(this.vault)
    : _root = Directory(
        vault.directory.absolute.uri.normalizePath().toFilePath(),
      );

  final OfflineVault vault;
  final Directory _root;
  static const maxBytes = 20 * 1024 * 1024;
  static const maxRecognitionBytes = 1024 * 1024;
  static const _magic = <int>[83, 80, 65, 83, 83, 69, 84, 49]; // SPASSET1
  static const _nonceBytes = 12;
  static const _macBytes = 16;
  static const _headerBytes = 8 + _nonceBytes + _macBytes;
  static final _cipher = AesGcm.with256bits();
  static final _identifier = RegExp(r'^[a-f0-9]{32}$');
  static final _hash = RegExp(r'^[a-f0-9]{64}$');
  static const _types = {'image/jpeg', 'image/png', 'application/pdf'};

  String get _scope =>
      _root.uri.pathSegments.lastWhere((part) => part.isNotEmpty);
  Directory get _assets => Directory('${_root.path}/assets');

  static void _filename(Object? value) {
    if (value is! String ||
        value.trim().isEmpty ||
        value.length > 200 ||
        value == '.' ||
        value == '..' ||
        value.contains(RegExp(r'[/\\\x00-\x1f\x7f]'))) {
      throw const FormatException(
        'Ungültiger Dateiname für ein Offline-Original.',
      );
    }
  }

  static String _mediaType(Uint8List bytes) {
    bool prefix(List<int> signature) =>
        bytes.length >= signature.length &&
        List.generate(
          signature.length,
          (index) => bytes[index] == signature[index],
        ).every((same) => same);
    if (prefix(const [137, 80, 78, 71, 13, 10, 26, 10])) return 'image/png';
    if (prefix(const [255, 216, 255])) return 'image/jpeg';
    if (prefix(const [37, 80, 68, 70, 45])) return 'application/pdf';
    throw const FormatException(
      'Nur JPEG-, PNG- und PDF-Originale werden unterstützt.',
    );
  }

  static String _hex(List<int> bytes) =>
      bytes.map((value) => value.toRadixString(16).padLeft(2, '0')).join();

  Map<String, dynamic> _reference(Map<String, dynamic> reference) {
    final ref = <String, dynamic>{
      for (final name in ['id', 'sha256', 'size', 'media_type', 'filename'])
        name: reference[name],
    };
    if (ref['id'] is! String ||
        !_identifier.hasMatch(ref['id']) ||
        ref['sha256'] is! String ||
        !_hash.hasMatch(ref['sha256']) ||
        ref['size'] is! int ||
        ref['size'] <= 0 ||
        ref['size'] > maxBytes ||
        (!_types.contains(ref['media_type']) &&
            ref['media_type'] != 'application/json') ||
        (ref['media_type'] == 'application/json' &&
            (ref['size'] > maxRecognitionBytes ||
                ref['filename'] != 'recognition.json'))) {
      throw const FormatException(
        'Ungültige Referenz auf ein Offline-Original.',
      );
    }
    _filename(ref['filename']);
    return ref;
  }

  List<int> _aad(Map<String, dynamic> ref) => utf8.encode(
    jsonEncode([
      'smartplan.offline.asset',
      1,
      _scope,
      ref['id'],
      ref['sha256'],
      ref['size'],
      ref['media_type'],
      ref['filename'],
    ]),
  );

  static Future<void> _rejectLinks(Directory directory) async {
    var path = directory.absolute;
    while (true) {
      final kind = await FileSystemEntity.type(path.path, followLinks: false);
      if (kind == FileSystemEntityType.link) {
        // Standard Apple OS aliases are above the application container. All
        // application-owned links, including account/assets links, are rejected.
        final alias =
            (Platform.isIOS || Platform.isMacOS) &&
            ((path.path == '/var' &&
                    await path.resolveSymbolicLinks() == '/private/var') ||
                (path.path == '/tmp' &&
                    await path.resolveSymbolicLinks() == '/private/tmp'));
        if (!alias) {
          throw const FileSystemException(
            'Verknüpfungen im Offline-Medienspeicher sind nicht erlaubt.',
          );
        }
      } else if (kind != FileSystemEntityType.directory &&
          kind != FileSystemEntityType.notFound) {
        throw const FileSystemException(
          'Offline-Medienspeicher ist kein Verzeichnis.',
        );
      }
      final parent = path.parent;
      if (parent.path == path.path) break;
      path = parent;
    }
  }

  static Future<void> _privateDirectory(Directory directory) async {
    if (await FileSystemEntity.type(directory.path, followLinks: false) !=
        FileSystemEntityType.directory) {
      throw const FileSystemException('Privater Offline-Medienordner fehlt.');
    }
    if (!Platform.isWindows && (await directory.stat()).mode & 0x3f != 0) {
      throw const FileSystemException('Offline-Medienordner ist nicht privat.');
    }
  }

  Future<void> _layout({required bool create}) async {
    await _rejectLinks(_root);
    if (create) await _root.create(recursive: true);
    if (await FileSystemEntity.type(_root.path, followLinks: false) !=
        FileSystemEntityType.directory) {
      throw const FileSystemException('Offline-Kontospeicher fehlt.');
    }
    if (create &&
        await FileSystemEntity.type(_assets.path, followLinks: false) ==
            FileSystemEntityType.notFound) {
      // createTemp uses a private directory on POSIX. Directory.create alone
      // inherits the umask and could otherwise produce a world-readable folder.
      final pending = await _root.createTemp('.assets-');
      try {
        await _privateDirectory(pending);
        if (await FileSystemEntity.type(_assets.path, followLinks: false) ==
            FileSystemEntityType.notFound) {
          try {
            await pending.rename(_assets.path);
          } on FileSystemException {
            if (await FileSystemEntity.type(_assets.path, followLinks: false) !=
                FileSystemEntityType.directory) {
              rethrow;
            }
          }
        }
      } finally {
        if (await pending.exists()) await pending.delete();
      }
    }
    await _rejectLinks(_assets);
    await _privateDirectory(_assets);
  }

  Future<Map<String, dynamic>> put(
    Uint8List bytes, {
    required String mediaType,
    required String filename,
  }) async {
    if (bytes.isEmpty || bytes.length > maxBytes) {
      throw const FormatException(
        'Ein Original muss zwischen 1 Byte und 20 MiB enthalten.',
      );
    }
    _filename(filename);
    // Freeze before the first await: caller edits must not change an upload's
    // hash, authentication data or encrypted original while it is being saved.
    final original = Uint8List.fromList(bytes);
    if (!_types.contains(mediaType) || _mediaType(original) != mediaType) {
      throw const FormatException(
        'Dateiinhalt und angegebener Dateityp stimmen nicht überein.',
      );
    }
    return _put(original, mediaType: mediaType, filename: filename);
  }

  static void _recognition(Object? result) {
    if (result is! Map<String, dynamic> ||
        result['schema_version'] is! int ||
        result['schema_version'] != 1 ||
        result['status'] != 'needs_review') {
      throw const FormatException(
        'Nur ungeprüfte Erkennungsergebnisse im Format 1 werden gespeichert.',
      );
    }
  }

  /// Internal server-result cache; ordinary source imports still exclude JSON.
  Future<Map<String, dynamic>> putRecognition(
    Map<String, dynamic> result,
  ) async {
    _recognition(result);
    late Uint8List encoded;
    try {
      // Serialize before any await to freeze nested maps/lists as well.
      encoded = Uint8List.fromList(utf8.encode(jsonEncode(result)));
    } on JsonUnsupportedObjectError {
      throw const FormatException(
        'Erkennungsergebnis enthält ungültige JSON-Werte.',
      );
    }
    if (encoded.length > maxRecognitionBytes) {
      throw const FormatException(
        'Ein Erkennungsergebnis darf höchstens 1 MiB enthalten.',
      );
    }
    return _put(
      encoded,
      mediaType: 'application/json',
      filename: 'recognition.json',
    );
  }

  Future<Map<String, dynamic>> _put(
    Uint8List original, {
    required String mediaType,
    required String filename,
  }) async {
    final ref = <String, dynamic>{
      'id': offlineId(),
      'sha256': _hex((await Sha256().hash(original)).bytes),
      'size': original.length,
      'media_type': mediaType,
      'filename': filename,
    };
    final box = await _cipher.encrypt(
      original,
      secretKey: vault.key,
      aad: _aad(ref),
    );
    final encrypted = Uint8List(_headerBytes + box.cipherText.length)
      ..setRange(0, _magic.length, _magic)
      ..setRange(_magic.length, _magic.length + _nonceBytes, box.nonce)
      ..setRange(_magic.length + _nonceBytes, _headerBytes, box.mac.bytes)
      ..setRange(
        _headerBytes,
        _headerBytes + box.cipherText.length,
        box.cipherText,
      );
    await _layout(create: true);
    final destination = Directory('${_assets.path}/${ref['id']}');
    final pending = await _assets.createTemp('.pending-');
    try {
      await _privateDirectory(pending);
      final file = File('${pending.path}/original.enc');
      await file.create(exclusive: true);
      await file.writeAsBytes(encrypted, flush: true);
      await _rejectLinks(_assets);
      if (await FileSystemEntity.type(destination.path, followLinks: false) !=
          FileSystemEntityType.notFound) {
        throw const FileSystemException('Offline-Original existiert bereits.');
      }
      // Rename a nonempty directory, never a file: even a competing destination
      // appearing after the check cannot replace an existing original or link.
      await Directory(pending.path).rename(destination.path);
      return ref;
    } finally {
      if (await pending.exists()) await pending.delete(recursive: true);
    }
  }

  Future<Uint8List> read(Map<String, dynamic> reference) async {
    final ref = _reference(reference);
    await _layout(create: false);
    final directory = Directory('${_assets.path}/${ref['id']}');
    await _rejectLinks(directory);
    await _privateDirectory(directory);
    final file = File('${directory.path}/original.enc');
    if (await FileSystemEntity.type(file.path, followLinks: false) !=
        FileSystemEntityType.file) {
      throw const FileSystemException(
        'Verschlüsseltes Offline-Original fehlt.',
      );
    }
    final expected = (ref['size'] as int) + _headerBytes;
    final handle = await file.open();
    late Uint8List encrypted;
    try {
      if (await handle.length() != expected) {
        throw const FormatException(
          'Größe des verschlüsselten Originals stimmt nicht überein.',
        );
      }
      encrypted = await handle.read(expected + 1);
      if (encrypted.length != expected || await handle.length() != expected) {
        throw const FormatException(
          'Offline-Original wurde während des Lesens verändert.',
        );
      }
    } finally {
      await handle.close();
    }
    for (var index = 0; index < _magic.length; index++) {
      if (encrypted[index] != _magic[index]) {
        throw const FormatException('Unbekanntes Offline-Medienformat.');
      }
    }
    final original = await _cipher.decrypt(
      SecretBox(
        Uint8List.sublistView(encrypted, _headerBytes),
        nonce: Uint8List.sublistView(
          encrypted,
          _magic.length,
          _magic.length + _nonceBytes,
        ),
        mac: Mac(
          Uint8List.sublistView(
            encrypted,
            _magic.length + _nonceBytes,
            _headerBytes,
          ),
        ),
      ),
      secretKey: vault.key,
      aad: _aad(ref),
    );
    if (original.length != ref['size'] ||
        _hex((await Sha256().hash(original)).bytes) != ref['sha256']) {
      throw const FormatException(
        'Integrität des Offline-Originals stimmt nicht überein.',
      );
    }
    if (ref['media_type'] == 'application/json') {
      _recognition(jsonDecode(utf8.decode(original)));
    } else if (_mediaType(Uint8List.fromList(original)) != ref['media_type']) {
      throw const FormatException(
        'Dateityp des Offline-Originals stimmt nicht überein.',
      );
    }
    return Uint8List.fromList(original);
  }
}

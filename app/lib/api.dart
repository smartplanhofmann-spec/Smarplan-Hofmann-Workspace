import 'dart:async';
import 'dart:convert';
import 'dart:io';
import 'dart:typed_data';

import 'package:flutter/foundation.dart';

class ApiException implements Exception {
  final int status;
  final String message;
  const ApiException(this.status, this.message);
  @override
  String toString() => message;
}

class OfficeApi extends ChangeNotifier {
  OfficeApi({String? baseUrl, String? apiVersion})
    : base =
          baseUrl ??
          const String.fromEnvironment(
            'API_URL',
            defaultValue: 'http://127.0.0.1:8765',
          ),
      version = apiVersion ?? const String.fromEnvironment('API_VERSION');
  final String base;
  final String version;
  String? token;

  Future<Uint8List> _request(
    String path,
    Map<String, dynamic>? body, {
    bool pdf = false,
    Uint8List? binary,
    String? method,
    String? expectedMediaType,
    int maxResponseBytes = 20 * 1024 * 1024,
  }) async {
    final versionedPath = version == 'v1' && path.startsWith('/api/')
        ? '/api/v1/${path.substring(5)}'
        : path;
    final uri = Uri.parse(
      '${base.replaceFirst(RegExp(r'/+$'), '')}$versionedPath',
    );
    if (uri.scheme != 'https' &&
        !(uri.scheme == 'http' &&
            ['localhost', '127.0.0.1'].contains(uri.host))) {
      throw const ApiException(
        0,
        'Für entfernte Server ist HTTPS erforderlich.',
      );
    }
    final client = HttpClient()
      ..connectionTimeout = const Duration(seconds: 15);
    final sessionToken = token;
    try {
      final request = await client
          .openUrl(method ?? (body == null ? 'GET' : 'POST'), uri)
          .timeout(const Duration(seconds: 15));
      request.followRedirects = false;
      if (sessionToken != null)
        request.headers.set('Authorization', 'Bearer $sessionToken');
      if (binary != null) {
        request.headers.contentType = ContentType.binary;
        request.contentLength = binary.length;
        request.add(binary);
      } else if (body != null) {
        final encodedBody = utf8.encode(jsonEncode(body));
        request.headers.contentType = ContentType.json;
        request.contentLength = encodedBody.length;
        request.add(encodedBody);
      }
      final response = await request.close().timeout(
        const Duration(seconds: 40),
      );
      final bytes = BytesBuilder(copy: false);
      await for (final chunk in response.timeout(const Duration(seconds: 40))) {
        bytes.add(chunk);
        if (bytes.length > maxResponseBytes) {
          throw const ApiException(0, 'Antwort ist zu groß.');
        }
      }
      final data = bytes.takeBytes();
      if (response.statusCode >= 400) {
        if (response.statusCode == 401 &&
            token != null &&
            token == sessionToken) {
          token = null;
          notifyListeners();
        }
        String message = 'Anfrage fehlgeschlagen (${response.statusCode}).';
        try {
          final error = jsonDecode(utf8.decode(data));
          if (error is Map && error['error'] is String)
            message = error['error'];
        } on FormatException {
          // A proxy or an unavailable server may return a non-JSON error.
        }
        throw ApiException(response.statusCode, message);
      }
      if (response.statusCode >= 300) {
        throw const ApiException(0, 'Unerwartete Weiterleitung des Servers.');
      }
      if (expectedMediaType != null &&
          response.headers.contentType?.mimeType != expectedMediaType) {
        throw const ApiException(0, 'Unerwartetes Dateiformat vom Server.');
      }
      if (pdf &&
          (response.headers.contentType?.mimeType != 'application/pdf' ||
              data.length < 4 ||
              ascii.decode(data.sublist(0, 4), allowInvalid: true) != '%PDF')) {
        throw const ApiException(
          0,
          'Der Server hat kein gültiges PDF geliefert.',
        );
      }
      return data;
    } on TimeoutException {
      throw const ApiException(
        0,
        'Der Server antwortet nicht rechtzeitig. Bitte erneut versuchen.',
      );
    } on SocketException {
      throw const ApiException(
        0,
        'Server nicht erreichbar. Verbindung prüfen.',
      );
    } on HttpException {
      throw const ApiException(
        0,
        'Übertragung unterbrochen. Bitte erneut versuchen.',
      );
    } finally {
      client.close(force: true);
    }
  }

  Future<dynamic> call(String path, [Map<String, dynamic>? body]) async {
    final bytes = await _request(path, body);
    try {
      return jsonDecode(utf8.decode(bytes));
    } on FormatException {
      throw const ApiException(0, 'Ungültige Antwort des Servers.');
    }
  }

  Future<Uint8List> pdf(String reportId) =>
      _request('/api/reports/$reportId/pdf', null, pdf: true);

  Future<dynamic> putChunk(String path, Uint8List bytes) async {
    if (bytes.isEmpty || bytes.length > 262144) {
      throw const ApiException(400, 'Ungültiger Dateiabschnitt.');
    }
    final response = await _request(
      path,
      null,
      binary: bytes,
      method: 'PUT',
      maxResponseBytes: 1024 * 1024,
    );
    try {
      return jsonDecode(utf8.decode(response));
    } on FormatException {
      throw const ApiException(0, 'Ungültige Antwort des Servers.');
    }
  }

  Future<Uint8List> bytes(
    String path, {
    required String mediaType,
    int maxBytes = 20 * 1024 * 1024,
  }) => _request(
    path,
    null,
    expectedMediaType: mediaType,
    maxResponseBytes: maxBytes,
  );
}

const roleLabels = {
  'owner': 'Geschäftsführung',
  'manager': 'Projektleitung',
  'technician': 'Technik',
  'accountant': 'Buchhaltung',
};

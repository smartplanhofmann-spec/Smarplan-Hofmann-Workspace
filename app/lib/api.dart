import 'dart:async';
import 'dart:convert';
import 'dart:io';
import 'dart:typed_data';

import 'package:flutter/foundation.dart';

class ApiException implements Exception {
  final int status;
  final String message;
  final String? requestResolution;
  const ApiException(this.status, this.message, {this.requestResolution});
  @override
  String toString() => message;
}

/// Local validation/rendering and explicitly approved mail delivery can take
/// longer than an ordinary read. This does not relax connection or byte limits.
Duration officeRequestHeaderTimeout(String path, {required String method}) =>
    method == 'POST' &&
        RegExp(
          r'^/api/(?:v1/)?business/(?:documents/[a-f0-9]{32}/(?:finalize|email)|finance/outbox/[a-f0-9]{32}/deliver)$',
        ).hasMatch(path)
    ? const Duration(seconds: 240)
    : const Duration(seconds: 40);

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
  String? _token, _offlineToken, _offlineBindingHeader;
  String? get token => _token;
  set token(String? value) {
    _token = value;
    _offlineToken = _offlineBindingHeader = null;
  }

  String? get offlineBindingHeader =>
      _offlineToken == token ? _offlineBindingHeader : null;

  /// The origin belongs to this exact stored device grant, not a later login.
  void configureOfflineSession(String value, String bindingHeader) {
    if (!(value.startsWith('offline_workspace_v2_') ||
            value.startsWith('offline_business_v2_')) ||
        !RegExp(r'^[a-f0-9]{32}:[a-f0-9]{32}$').hasMatch(bindingHeader)) {
      throw const ApiException(
        0,
        'Ungültige Firmenbindung der Offline-Freigabe.',
      );
    }
    _token = _offlineToken = value;
    _offlineBindingHeader = bindingHeader;
  }

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
    final sessionBinding = offlineBindingHeader;
    if ((sessionToken?.startsWith('offline_workspace_v2_') == true ||
            sessionToken?.startsWith('offline_business_v2_') == true) &&
        sessionBinding == null) {
      client.close(force: true);
      throw const ApiException(
        0,
        'Die ursprüngliche Offline-Firmenbindung fehlt.',
      );
    }
    final requestMethod = method ?? (body == null ? 'GET' : 'POST');
    try {
      final request = await client
          .openUrl(requestMethod, uri)
          .timeout(const Duration(seconds: 15));
      request.followRedirects = false;
      if (sessionToken != null)
        request.headers.set('Authorization', 'Bearer $sessionToken');
      if (sessionBinding != null)
        request.headers.set('X-Smartplan-Offline-Binding', sessionBinding);
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
        officeRequestHeaderTimeout(path, method: requestMethod),
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
        String? requestResolution;
        try {
          final error = jsonDecode(utf8.decode(data));
          if (error is Map && error['error'] is String)
            message = error['error'];
          if (response.statusCode == 409 &&
              error is Map &&
              error['request_resolution'] == 'not_accepted') {
            requestResolution = 'not_accepted';
          }
        } on FormatException {
          // A proxy or an unavailable server may return a non-JSON error.
        }
        throw ApiException(
          response.statusCode,
          message,
          requestResolution: requestResolution,
        );
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
    final bytes = await _request(
      path,
      body,
      maxResponseBytes: officeJsonResponseLimit(path),
    );
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

/// A bounded large bank DTO can contain up to 10,000 canonical statement rows.
/// Other API and binary download limits remain independent.
int officeJsonResponseLimit(String path) =>
    RegExp(
      r'^/api/(?:v1/)?business/(?:adapters/(?:[a-f0-9]{32}/import|imports/[a-f0-9]{32}(?:/(?:catalog-preview|apply))?)|catalog-prices/(?:sources/[a-f0-9]{32}/imports|imports/[a-f0-9]{32}(?:/(?:preview|apply))?|candidates|prices/[a-f0-9]{32}/history))$',
    ).hasMatch(path.split('?').first)
    ? 32 * 1024 * 1024
    : RegExp(
        r'^/api/business/bank/(?:accounts|import/preview|statements(?:/[a-f0-9]{32})?|transactions/[a-f0-9]{32}/(?:candidates|history|preview|matches)|reconciliations(?:/preview|/[a-f0-9]{32})?)$',
      ).hasMatch(path.split('?').first)
    ? 128 * 1024 * 1024
    : 20 * 1024 * 1024;

const roleLabels = {
  'owner': 'Geschäftsführung',
  'manager': 'Projektleitung',
  'technician': 'Technik',
  'accountant': 'Buchhaltung',
};

part of 'offline_plans.dart';

/// Service reports share the encrypted account vault. The signed capture is
/// frozen before any network request; only its exact command may be retried.
extension OfflineServiceReports on OfflinePlans {
  bool get offlineReportsSupported =>
      permitted && _state?['offline_reports_supported'] == true;
  bool get serviceReportsWritable =>
      offlineReportsSupported &&
      !businessReadOnly &&
      _state?['report_writes_enabled'] != false;

  bool canAccessServiceReports(String project) =>
      offlineReportsSupported &&
      canAccessProject(project) &&
      (_state?['report_project_ids'] as List? ?? []).contains(project);

  bool _invalidReportText(String value) =>
      value.contains(RegExp(r'[\x00-\x08\x0b-\x1f\x7f]')) ||
      value.runes.any((v) => v >= 0xd800 && v <= 0xdfff);

  void _reportAccess(int epoch, String project, {bool write = false}) {
    _entryAccess(epoch, project, write: write);
    if (!canAccessServiceReports(project)) {
      throw const ApiException(
        403,
        'Serviceberichte sind für dieses Projekt nicht offline freigegeben. Gesicherte Fassungen bleiben erhalten.',
      );
    }
  }

  List<Map<String, dynamic>> serviceReports(String project) {
    _reportAccess(_epoch, project);
    return [
      for (final record
          in (_state?['service_report_records'] as Map? ?? {}).values)
        if (record['project_id'] == project)
          offlineCopy(Map<String, dynamic>.from(record)),
    ];
  }

  Map<String, dynamic> serviceReport(String project, String id) {
    _reportAccess(_epoch, project);
    final value = (_state?['service_report_records'] as Map? ?? {})[id];
    if (value == null || value['project_id'] != project)
      throw const ApiException(
        404,
        'Servicebericht ist auf diesem Gerät nicht vorhanden.',
      );
    return offlineCopy(Map<String, dynamic>.from(value));
  }

  Future<String> _serviceHash(
    String id,
    String project,
    Map<String, dynamic> content,
  ) async {
    final keys = content.keys.toList()..sort();
    final bytes = utf8.encode(
      jsonEncode([
        id,
        project,
        {for (final key in keys) key: content[key]},
      ]),
    );
    return (await Sha256().hash(bytes)).bytes
        .map((v) => v.toRadixString(16).padLeft(2, '0'))
        .join();
  }

  Future<Map<String, dynamic>> saveServiceReportDraft(
    String project, {
    String? entryId,
    required String title,
    String description = '',
    String notes = '',
  }) async {
    final epoch = _epoch;
    _reportAccess(epoch, project, write: true);
    if (!serviceReportsWritable)
      throw const ApiException(
        423,
        'Serviceberichte warten auf die Schreibfreigabe.',
      );
    if (title.trim().isEmpty ||
        title.length > 300 ||
        description.trim().isEmpty ||
        description.length > 30000 ||
        notes.length > 10000 ||
        [title, description, notes].any(_invalidReportText)) {
      throw const ApiException(400, 'Titel und Berichtstext prüfen.');
    }
    final source = projects.firstWhere((p) => p['id'] == project) as Map;
    if (source['name'] is! String ||
        (source['name'] as String).isEmpty ||
        source['customer'] is! String ||
        (source['customer'] as String).isEmpty ||
        [source['name'] as String, source['customer'] as String].any(
          (s) => s.trim().isEmpty || s.length > 500 || _invalidReportText(s),
        ))
      throw const ApiException(
        409,
        'Projekt und Kunde müssen zuerst mit Verbindung geladen werden.',
      );
    final id = entryId ?? offlineId();
    final before = (_state?['service_report_records'] as Map? ?? {})[id];
    if (clock().toUtc().year < 1900 || clock().toUtc().year > 2200)
      throw const ApiException(400, 'Die Gerätezeit ist nicht gültig.');
    final content = <String, dynamic>{
      'title': title,
      'description': description,
      'notes': notes,
      'project_name': source['name'],
      'customer': source['customer'],
      'captured_at':
          before?['content']?['captured_at'] ??
          clock().toUtc().toIso8601String(),
    };
    final hash = await _serviceHash(id, project, content);
    return _change((state) {
      _reportAccess(epoch, project, write: true);
      final records = state.putIfAbsent(
        'service_report_records',
        () => <String, dynamic>{},
      ) as Map;
      final current = records[id];
      if (current != null &&
          (current['project_id'] != project || current['status'] != 'draft'))
        throw const ApiException(
          409,
          'Eine unterschriebene Fassung ist unveränderlich.',
        );
      if (current?['content_hash'] != before?['content_hash'])
        throw const ApiException(
          409,
          'Der Entwurf wurde zwischenzeitlich geändert. Bitte neu öffnen.',
        );
      final record = <String, dynamic>{
        'id': id,
        'project_id': project,
        'kind': 'service',
        ...content,
        'content': content,
        'content_hash': hash,
        'status': 'draft',
        'sync_status': 'Auf diesem Gerät gesichert',
      };
      records[id] = record;
      return offlineCopy(record);
    });
  }

  Future<Map<String, dynamic>> signServiceReport(
    String project,
    String id, {
    required String signer,
    required List<List<List<double>>> strokes,
    String? expectedContentHash,
  }) async {
    final epoch = _epoch;
    _reportAccess(epoch, project, write: true);
    if (!serviceReportsWritable)
      throw const ApiException(
        423,
        'Serviceberichte warten auf die Schreibfreigabe.',
      );
    var count = 0;
    if (signer.trim().isEmpty ||
        signer.length > 200 ||
        signer.contains(RegExp(r'[\x00-\x1f\x7f]')) ||
        _invalidReportText(signer) ||
        strokes.isEmpty ||
        strokes.length > 100 ||
        strokes.any((stroke) {
          count += stroke.length;
          return stroke.length < 2 ||
              stroke.length > 2000 ||
              stroke.any(
                (p) =>
                    p.length != 2 ||
                    p.any((v) => !v.isFinite || v < 0 || v > 1),
              );
        }) ||
        count > 10000)
      throw const ApiException(400, 'Namen und gültige Unterschrift ergänzen.');
    final result = await _change((state) {
      _reportAccess(epoch, project, write: true);
      final record =
          (state['service_report_records'] as Map? ?? {})[id] as Map?;
      if (record == null || record['project_id'] != project)
        throw const ApiException(404, 'Servicebericht ist nicht vorhanden.');
      if (record['status'] != 'draft')
        throw const ApiException(
          409,
          'Diese Fassung wurde bereits unterschrieben.',
        );
      if (expectedContentHash != null &&
          record['content_hash'] != expectedContentHash)
        throw const ApiException(
          409,
          'Der Bericht wurde seit der Prüfung geändert.',
        );
      final signed = clock().toUtc();
      if (signed.year < 1900 || signed.year > 2200)
        throw const ApiException(400, 'Die Gerätezeit ist nicht gültig.');
      if (signed.isBefore(DateTime.parse(record['content']['captured_at'])))
        throw const ApiException(
          409,
          'Die Gerätezeit liegt vor der Erfassungszeit.',
        );
      final body = <String, dynamic>{
        'request_id': offlineId(),
        'entry_id': id,
        'project_id': project,
        'content': record['content'],
        'content_hash': record['content_hash'],
        'signer': signer,
        'strokes': strokes,
        'signed_at': signed.toIso8601String(),
      };
      final frozen = offlineCopy(body);
      record.addAll(<String, dynamic>{
        'capture_request': frozen,
        'signer': signer,
        'strokes': offlineCopy({'strokes': strokes})['strokes'],
        'signed_at': body['signed_at'],
        'status': 'signed',
        'sync_status':
            'Auf diesem Gerät unterschrieben · Übertragung ausstehend',
      });
      (state.putIfAbsent('service_report_outbox', () => []) as List).add(id);
      return offlineCopy(Map<String, dynamic>.from(record));
    });
    unawaited(sync());
    return result;
  }

  bool _sameReportValue(Object? a, Object? b) {
    if (a is Map && b is Map)
      return a.length == b.length &&
          a.keys.every((k) => b.containsKey(k) && _sameReportValue(a[k], b[k]));
    if (a is List && b is List)
      return a.length == b.length &&
          List.generate(
            a.length,
            (i) => i,
          ).every((i) => _sameReportValue(a[i], b[i]));
    return a == b;
  }

  void _checkServiceReceipt(Map<String, dynamic> remote, Map request) {
    final capture = remote['offline_capture'];
    if (remote['id'] != request['entry_id'] ||
        remote['project_id'] != request['project_id'] ||
        remote['status'] != 'signed' ||
        remote['kind'] != 'service' ||
        remote['revision'] != 2 ||
        remote['signed_by'] != user['id'] ||
        remote['created_by'] != user['id'] ||
        remote['updated_by'] != user['id'] ||
        remote['signer'] != request['signer'] ||
        remote['signed_at'] != request['signed_at'] ||
        remote['title'] != request['content']['title'] ||
        remote['description'] != request['content']['description'] ||
        remote['notes'] != request['content']['notes'] ||
        !_sameReportValue(remote['strokes'], request['strokes']) ||
        remote['pdf_sha256'] is! String ||
        !RegExp(r'^[a-f0-9]{64}$').hasMatch(remote['pdf_sha256']) ||
        capture is! Map ||
        capture['schema'] != 1 ||
        capture['request_id'] != request['request_id'] ||
        capture['content_hash'] != request['content_hash'] ||
        capture['signed_at'] != request['signed_at'] ||
        !_sameReportValue(capture['content'], request['content']) ||
        capture['received_at'] is! String ||
        DateTime.tryParse(capture['received_at']) == null)
      throw const ApiException(
        0,
        'Die Serverbestätigung passt nicht zur unterschriebenen Fassung. Das Original bleibt auf diesem Gerät.',
      );
  }

  Future<Uint8List> serviceReportPdf(String project, String id) async {
    final epoch = _epoch;
    final record = serviceReport(project, id);
    final source = record['pdf_source'];
    if (source is! Map)
      throw const ApiException(
        409,
        'Das archivierte PDF ist noch nicht auf diesem Gerät verfügbar.',
      );
    final bytes = await EncryptedAssets(_vault!)
        .read(Map<String, dynamic>.from(source));
    _reportAccess(epoch, project);
    if (source['sha256'] != record['server_record']?['pdf_sha256'])
      throw const ApiException(
        0,
        'Die PDF-Prüfsumme stimmt nicht mit dem Archiv überein.',
      );
    return bytes;
  }

  Future<void> _syncServiceReports(int epoch, String? token) async {
    if (!offlineReportsSupported) return;
    if (!serviceReportsWritable) {
      notice = 'Unterschriebene Serviceberichte bleiben gesichert. Die Übertragung wartet auf die erneute Freigabe.';
      return;
    }
    for (final id in List<String>.from(
      _state?['service_report_outbox'] as List? ?? [],
    )) {
      if (epoch != _epoch || transport.token != token || !permitted) return;
      final record =
          (_state?['service_report_records'] as Map? ?? {})[id] as Map?;
      if (record == null ||
          !canAccessServiceReports(record['project_id']) ||
          [
            'Zugriff gesperrt',
            'Konflikt',
            'Eingabe prüfen',
          ].contains(record['sync_status']))
        continue;
      final project = record['project_id'] as String;
      final vault = _vault!;
      final request = offlineCopy(
        Map<String, dynamic>.from(record['capture_request']),
      );
      try {
        _reportAccess(epoch, project);
        final remote = Map<String, dynamic>.from(
          await _offlineCall(
            epoch,
            '/api/business/service-reports/offline',
            request,
          ),
        );
        _reportAccess(epoch, project);
        if (transport.token != token) return;
        _checkServiceReceipt(remote, request);
        await _change((state) {
          _reportAccess(epoch, project);
          (state['service_report_records'][id] as Map).addAll(<String, dynamic>{
            'server_record': offlineCopy(remote),
            'sync_status': 'Serverbestätigt · PDF wird geladen',
          });
        });
        final bytes = await _offlineBytes(
          epoch,
          '/api/business/service-reports/$id/pdf',
          mediaType: 'application/pdf',
        );
        _reportAccess(epoch, project);
        if (transport.token != token) return;
        final hash = (await Sha256().hash(bytes)).bytes
            .map((v) => v.toRadixString(16).padLeft(2, '0'))
            .join();
        _reportAccess(epoch, project);
        if (_vault != vault || transport.token != token) return;
        if (hash != remote['pdf_sha256'])
          throw const ApiException(
            0,
            'Das empfangene PDF stimmt nicht mit dem unterschriebenen Archiv überein.',
          );
        final source = await EncryptedAssets(vault).put(
          bytes,
          mediaType: 'application/pdf',
          filename: 'servicebericht-$id.pdf',
        );
        try {
          _reportAccess(epoch, project);
          if (_vault != vault || transport.token != token)
            throw StateError('Offline-Konto wurde gewechselt.');
          await _change((state) {
            _reportAccess(epoch, project);
            (state['service_report_records'][id] as Map).addAll(
              <String, dynamic>{
                'pdf_source': source,
                'sync_status': 'Synchronisiert',
              },
            );
            (state['service_report_records'][id] as Map).remove('sync_error');
            (state['service_report_outbox'] as List).remove(id);
          });
        } catch (_) {
          // Read a separate snapshot: a failed acknowledgement may follow a
          // committed write. Never delete an original referenced on disk.
          await _removeUnpublishedReportPdf(vault, source);
          rethrow;
        }
      } on ApiException catch (error) {
        if (epoch != _epoch || !active || transport.token != token) return;
        if (error.status == 401) {
          await lock();
          return;
        }
        if (error.status == 0 || error.status >= 500 || error.status == 429) {
          notice = 'Die unterschriebene Fassung bleibt verschlüsselt gesichert. Übertragung und PDF-Abruf werden fortgesetzt.';
          return;
        }
        await _change((state) {
          final local = state['service_report_records'][id] as Map;
          local['sync_status'] = [403, 404].contains(error.status)
              ? 'Zugriff gesperrt'
              : error.status == 409
              ? 'Konflikt'
              : error.status == 423
              ? 'Wartet auf Freigabe'
              : 'Eingabe prüfen';
          local['sync_error'] = error.message;
          if ([403, 404].contains(error.status))
            (state['report_project_ids'] as List).remove(project);
        });
      }
    }
  }

  Future<void> _removeUnpublishedReportPdf(
    OfflineVault vault,
    Map<String, dynamic> source,
  ) async {
    try {
      final stored = await OfflineVault(vault.directory, vault.key).read();
      final records = (stored?['service_report_records'] as Map? ?? {}).values;
      if (records.any((record) => record['pdf_source']?['id'] == source['id']))
        return;
      await EncryptedAssets(vault).remove(source);
    } catch (_) {
      // Preserve bytes if a durable reference cannot be ruled out.
    }
  }
}

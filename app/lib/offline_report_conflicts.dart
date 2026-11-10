part of 'offline_plans.dart';

/// A conflict never grants authority to change a frozen signature. Diagnosis
/// is read-only; a deliberate successor is a local, unsigned new document.
extension OfflineReportConflicts on OfflinePlans {
  bool get reportConflictReviewSupported =>
      permitted && _state?['offline_report_diagnosis_supported'] == true;
  Map<String, dynamic> _reportForReview(int epoch, String project, String id) {
    _reportAccess(epoch, project, write: true);
    if (!serviceReportsWritable) {
      throw const ApiException(
        423,
        'Serviceberichte warten auf die Schreibfreigabe.',
      );
    }
    final record = serviceReport(project, id);
    final request = record['capture_request'];
    if (record['status'] != 'signed' ||
        request is! Map ||
        request['entry_id'] != id ||
        request['project_id'] != project ||
        request['content_hash'] != record['content_hash'] ||
        !_sameReportValue(request['content'], record['content']) ||
        request['signer'] != record['signer'] ||
        request['signed_at'] != record['signed_at'] ||
        !_sameReportValue(request['strokes'], record['strokes'])) {
      throw const ApiException(
        409,
        'Unveränderte unterschriebene Gerätefassung erforderlich.',
      );
    }
    return record;
  }

  Future<Map<String, dynamic>> diagnoseServiceReport(
    String project,
    String id,
  ) async {
    final epoch = _epoch, token = transport.token;
    final record = _reportForReview(epoch, project, id);
    if (!await _businessWritesAvailable(epoch, token) ||
        !reportConflictReviewSupported) {
      throw const ApiException(
        409,
        'Die Konfliktprüfung benötigt einen aktuellen freigegebenen Serverstand. Das Original bleibt gesichert.',
      );
    }
    _reportForReview(epoch, project, id);
    final request = offlineCopy(
      Map<String, dynamic>.from(record['capture_request']),
    );
    if (await _serviceHash(
          id,
          project,
          Map<String, dynamic>.from(request['content']),
        ) !=
        request['content_hash']) {
      throw const ApiException(
        409,
        'Die Prüfsumme der Gerätefassung stimmt nicht.',
      );
    }
    _reportForReview(epoch, project, id);
    dynamic raw;
    try {
      raw = await _offlineCall(
        epoch,
        '/api/business/service-reports/offline/diagnosis',
        request,
      );
    } on ApiException catch (error) {
      if ([403, 404].contains(error.status) &&
          epoch == _epoch &&
          transport.token == token &&
          permitted) {
        await _change((state) {
          _reportAccess(epoch, project);
          (state['report_project_ids'] as List).remove(project);
          final local = state['service_report_records'][id] as Map;
          local['sync_status'] = 'Zugriff gesperrt';
          local['sync_error'] = error.message;
        });
      }
      rethrow;
    }
    _reportForReview(epoch, project, id);
    if (transport.token != token) {
      throw const ApiException(401, 'Die Sitzung wurde gewechselt.');
    }
    const fields = {
      'schema',
      'entry_id',
      'project_id',
      'request_id',
      'content_hash',
      'captured_context',
      'current_context',
      'state',
      'server_record',
    };
    bool contextShape(dynamic value) =>
        value is Map &&
        value.length == 2 &&
        value.keys.toSet().containsAll({'project_name', 'customer'}) &&
        value.values.every(
          (v) =>
              v is String &&
              v.trim().isNotEmpty &&
              v.length <= 500 &&
              !_invalidReportText(v),
        );
    if (raw is! Map ||
        raw.length != fields.length ||
        !raw.keys.toSet().containsAll(fields) ||
        raw['schema'] != 1 ||
        raw['schema'] is! int ||
        raw['entry_id'] != id ||
        raw['project_id'] != project ||
        raw['request_id'] != request['request_id'] ||
        raw['content_hash'] != request['content_hash'] ||
        !contextShape(raw['captured_context']) ||
        !contextShape(raw['current_context']) ||
        !_sameReportValue(raw['captured_context'], {
          'project_name': request['content']['project_name'],
          'customer': request['content']['customer'],
        }) ||
        !{'accepted', 'ready', 'context_changed'}.contains(raw['state'])) {
      throw const ApiException(
        0,
        'Die Konfliktprüfung passt nicht zum gesicherten Original.',
      );
    }
    if (raw['state'] == 'accepted') {
      if (raw['server_record'] is! Map) {
        throw const ApiException(0, 'Die Originalbestätigung fehlt.');
      }
      _checkServiceReceipt(
        Map<String, dynamic>.from(raw['server_record']),
        request,
      );
    } else if (raw['server_record'] != null ||
        (raw['state'] == 'ready') !=
            _sameReportValue(raw['captured_context'], raw['current_context'])) {
      throw const ApiException(
        0,
        'Der gemeldete Konfliktzustand ist widersprüchlich.',
      );
    }
    return offlineCopy(Map<String, dynamic>.from(raw));
  }

  Future<void> retryServiceReport(String project, String id) async {
    final epoch = _epoch;
    final before = _reportForReview(epoch, project, id);
    if (before['conflict_successor_id'] != null) {
      throw const ApiException(
        409,
        'Für dieses Original wurde bereits ein neuer Bericht angelegt. Bitte diesen öffnen.',
      );
    }
    final diagnosis = await diagnoseServiceReport(project, id);
    if (diagnosis['state'] == 'context_changed') {
      throw const ApiException(
        409,
        'Projekt oder Kunde wurde geändert. Original prüfen und bei Bedarf einen neuen Entwurf anlegen.',
      );
    }
    await _change((state) {
      final current = _reportForReview(epoch, project, id);
      if (current['conflict_successor_id'] != null) {
        throw const ApiException(
          409,
          'Für dieses Original wurde zwischenzeitlich ein neuer Bericht angelegt.',
        );
      }
      if (!_sameReportValue(
        current['capture_request'],
        before['capture_request'],
      )) {
        throw const ApiException(
          409,
          'Die Gerätefassung wurde zwischenzeitlich geändert.',
        );
      }
      // Only the delivery state changes. Nonce, content and signature stay exact.
      final local = state['service_report_records'][id] as Map;
      local['sync_status'] = 'Übertragung erneut freigegeben';
      local.remove('sync_error');
      final queue =
          state.putIfAbsent('service_report_outbox', () => []) as List;
      if (!queue.contains(id)) queue.add(id);
    });
    await sync();
  }

  Future<Map<String, dynamic>> copyConflictedServiceReport(
    String project,
    String id, {
    required Map<String, dynamic> reviewedDiagnosis,
  }) async {
    final epoch = _epoch;
    final before = _reportForReview(epoch, project, id);
    final linked = before['conflict_successor_id'];
    if (linked is String) return serviceReport(project, linked);
    if (before['sync_status'] != 'Konflikt' ||
        before['server_record'] != null ||
        reviewedDiagnosis['state'] != 'context_changed') {
      throw const ApiException(
        409,
        'Nur eine ungeklärte, nicht serverbestätigte Kontextänderung kann kopiert werden.',
      );
    }
    final fresh = await diagnoseServiceReport(project, id);
    if (!_sameReportValue(fresh, reviewedDiagnosis)) {
      throw const ApiException(
        409,
        'Der Serverstand wurde geändert. Bitte den Konflikt erneut prüfen.',
      );
    }
    final captured = clock().toUtc();
    if (captured.year < 1900 || captured.year > 2200) {
      throw const ApiException(400, 'Die Gerätezeit ist nicht gültig.');
    }
    final successorId = offlineId();
    final content = <String, dynamic>{
      for (final key in ['title', 'description', 'notes'])
        key: before['content'][key],
      'project_name': fresh['current_context']['project_name'],
      'customer': fresh['current_context']['customer'],
      'captured_at': captured.toIso8601String(),
    };
    final hash = await _serviceHash(successorId, project, content);
    return _change((state) {
      final current = _reportForReview(epoch, project, id);
      if (current['conflict_successor_id'] is String) {
        return serviceReport(project, current['conflict_successor_id']);
      }
      if (current['sync_status'] != 'Konflikt' ||
          current['server_record'] != null ||
          !_sameReportValue(
            current['capture_request'],
            before['capture_request'],
          )) {
        throw const ApiException(
          409,
          'Das Original wurde zwischenzeitlich bestätigt oder geändert.',
        );
      }
      final record = <String, dynamic>{
        'id': successorId,
        'project_id': project,
        'kind': 'service',
        ...content,
        'content': content,
        'content_hash': hash,
        'status': 'draft',
        'sync_status': 'Auf diesem Gerät gesichert',
        'conflict_source': {
          'entry_id': id,
          'content_hash': before['content_hash'],
          'request_id': before['capture_request']['request_id'],
        },
      };
      state['service_report_records'][successorId] = record;
      state['service_report_records'][id]['conflict_successor_id'] =
          successorId;
      // Keep the old original and its frozen command, paused as a conflict.
      return offlineCopy(record);
    });
  }
}

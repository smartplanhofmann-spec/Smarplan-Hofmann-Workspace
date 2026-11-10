import 'dart:async';
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:smartplan_office/api.dart';
import 'package:smartplan_office/offline_plans.dart';
import 'package:smartplan_office/offline_vault.dart';

import 'business_offline_reports_test.dart'
    show OfflineReportServer, reportInk, reportProject, reportUser, copyReport;
import 'offline_plans_test.dart' show TestDevice, loginV2, idle;

const conflictProjects = [
  {
    'id': reportProject,
    'name': 'Ursprüngliches Projekt',
    'customer': 'Ursprünglicher Kunde',
  },
];

class ConflictReportServer extends OfflineReportServer {
  ConflictReportServer(super.clock) {
    reportMetadata = {'offline_report_diagnosis_supported': true};
  }
  Map<String, dynamic> currentContext = {
    'project_name': 'Ursprüngliches Projekt',
    'customer': 'Ursprünglicher Kunde',
  };
  final diagnoses = <Map<String, dynamic>>[];
  bool invalidDiagnosis = false;
  Completer<void>? diagnosisEntered, diagnosisRelease;

  @override
  Future<dynamic> call(String path, [Map<String, dynamic>? body]) async {
    if (!online) throw const ApiException(0, 'Offline');
    if (path == '/api/business/service-reports/offline/diagnosis') {
      if (forbidden) throw const ApiException(403, 'Zugriff entzogen');
      diagnoses.add(copyReport(body!));
      diagnosisEntered?.complete();
      await diagnosisRelease?.future;
      final captured = {
        'project_name': body['content']['project_name'],
        'customer': body['content']['customer'],
      };
      final accepted = reportReceipts[body['request_id']];
      return {
        'schema': 1,
        'entry_id': body['entry_id'],
        'project_id': body['project_id'],
        'request_id': body['request_id'],
        'content_hash': body['content_hash'],
        'captured_context': captured,
        'current_context': Map<String, dynamic>.from(currentContext),
        'state': accepted != null
            ? 'accepted'
            : captured.toString() == currentContext.toString()
            ? 'ready'
            : 'context_changed',
        'server_record': accepted == null ? null : copyReport(accepted),
        if (invalidDiagnosis) 'ignore_signature': true,
      };
    }
    if (path == '/api/business/service-reports/offline' &&
        !reportReceipts.containsKey(body!['request_id']) &&
        (body['content']['project_name'] != currentContext['project_name'] ||
            body['content']['customer'] != currentContext['customer'])) {
      throw const ApiException(409, 'Projekt oder Kunde wurde geändert');
    }
    return super.call(path, body);
  }
}

class FailingConflictDevice extends TestDevice {
  FailingConflictDevice(super.folder);
  bool failWrites = false;
  int writesBeforeFailure = 0;
  @override
  Future<OfflineVault> open(
    String server,
    String user, {
    bool create = false,
  }) async {
    final vault = await super.open(server, user, create: create);
    return _FailingVault(vault, () {
      if (!failWrites) return false;
      if (writesBeforeFailure > 0) {
        writesBeforeFailure--;
        return false;
      }
      return true;
    });
  }
}

class _FailingVault extends OfflineVault {
  _FailingVault(OfflineVault original, this.fail)
    : super(original.directory, original.key);
  final bool Function() fail;
  @override
  Future<void> write(Map<String, dynamic> state) {
    if (fail()) throw const FileSystemException('Synthetic disk full');
    return super.write(state);
  }
}

void main() {
  late Directory directory;
  late FailingConflictDevice device;
  late ConflictReportServer server;
  late OfflinePlans repo;
  final now = DateTime.utc(2026, 11, 10, 10);
  const user = {'id': reportUser, 'role': 'technician'};

  setUp(() async {
    directory = await Directory.systemTemp.createTemp(
      'smartplan-report-conflict-',
    );
    device = FailingConflictDevice(directory);
    server = ConflictReportServer(() => now)..token = 'synthetic-full-session';
    repo = OfflinePlans(
      api: server,
      transport: server.offlineTransport,
      device: device,
      clock: () => now,
    );
    await loginV2(repo, user, conflictProjects, offlineReports: true);
    await idle(repo);
    server.online = false;
  });
  tearDown(() async {
    await idle(repo);
    repo.dispose();
    server.dispose();
    await directory.delete(recursive: true);
  });

  Future<String> signed() async {
    final draft = await repo.saveServiceReportDraft(
      reportProject,
      title: 'Unveränderter Bericht',
      description: 'Geprüft.\nDichtheit bestätigt.',
      notes: ' Hinweise. ',
    );
    await repo.signServiceReport(
      reportProject,
      draft['id'],
      signer: 'Synthetische Kundin',
      strokes: reportInk,
    );
    await idle(repo);
    return draft['id'];
  }

  Future<String> conflict() async {
    final id = await signed();
    server.currentContext = {
      'project_name': 'Neues Projekt',
      'customer': 'Neuer Kunde',
    };
    server.online = true;
    await repo.sync();
    expect(repo.serviceReport(reportProject, id)['sync_status'], 'Konflikt');
    return id;
  }

  test('context review is read-only and simultaneous copies create one unsigned successor', () async {
    final id = await conflict();
    final original = repo.serviceReport(reportProject, id);
    final diagnosis = await repo.diagnoseServiceReport(reportProject, id);
    expect(diagnosis['state'], 'context_changed');
    expect(server.reportReceipts, isEmpty);
    expect(repo.serviceReports(reportProject), hasLength(1));
    final copies = await Future.wait(
      List.generate(
        2,
        (_) => repo.copyConflictedServiceReport(
          reportProject,
          id,
          reviewedDiagnosis: diagnosis,
        ),
      ),
    );
    expect(copies[0], copies[1]);
    final copy = copies.first;
    expect(copy['id'], isNot(id));
    expect(copy['status'], 'draft');
    expect(copy['content']['project_name'], 'Neues Projekt');
    expect(copy['content']['customer'], 'Neuer Kunde');
    for (final key in [
      'signer',
      'strokes',
      'capture_request',
      'server_record',
    ]) {
      expect(copy.containsKey(key), isFalse);
    }
    final preserved = repo.serviceReport(reportProject, id);
    expect(preserved['capture_request'], original['capture_request']);
    expect(preserved['content'], original['content']);
    expect(preserved['strokes'], original['strokes']);
    expect(preserved['sync_status'], 'Konflikt');
    expect(repo.pending, 1);
    await expectLater(
      repo.retryServiceReport(reportProject, id),
      throwsA(isA<ApiException>()),
    );
  });

  test('new draft keeps reviewed names when the project cache is old, survives encrypted restart and needs a new signature', () async {
    final id = await conflict();
    final original = repo.serviceReport(reportProject, id);
    final copy = await repo.copyConflictedServiceReport(
      reportProject,
      id,
      reviewedDiagnosis: await repo.diagnoseServiceReport(reportProject, id),
    );
    final edited = await repo.saveServiceReportDraft(
      reportProject,
      entryId: copy['id'],
      title: copy['title'],
      description: '${copy['description']}\nErgänzt.',
      notes: copy['notes'],
    );
    expect(edited['content']['project_name'], 'Neues Projekt');
    expect(edited['conflict_source'], copy['conflict_source']);
    await repo.leave();
    repo.dispose();
    repo = OfflinePlans(
      api: server,
      transport: server.offlineTransport,
      device: device,
      clock: () => now,
    );
    repo.api.token = null;
    server.online = false;
    await repo.resume();
    await idle(repo);
    expect(
      repo.serviceReport(reportProject, id)['capture_request'],
      original['capture_request'],
    );
    expect(repo.serviceReport(reportProject, copy['id'])['status'], 'draft');
    await repo.signServiceReport(
      reportProject,
      copy['id'],
      signer: 'Neue Unterzeichnerin',
      strokes: reportInk,
    );
    await idle(repo);
    server.online = true;
    await repo.sync();
    expect(server.reportReceipts, hasLength(1));
    expect(
      repo.serviceReport(reportProject, copy['id'])['sync_status'],
      'Synchronisiert',
    );
    expect(
      repo.serviceReport(reportProject, copy['id'])['signer'],
      'Neue Unterzeichnerin',
    );
    expect(repo.serviceReport(reportProject, id)['sync_status'], 'Konflikt');
    expect(
      repo.serviceReport(reportProject, id)['capture_request'],
      original['capture_request'],
    );
    expect(repo.pending, 1);
  });

  test('restored context retries the identical command without a new signature or document', () async {
    final id = await conflict();
    final original = repo.serviceReport(reportProject, id);
    server.currentContext = {
      'project_name': 'Ursprüngliches Projekt',
      'customer': 'Ursprünglicher Kunde',
    };
    await repo.retryServiceReport(reportProject, id);
    expect(repo.serviceReports(reportProject), hasLength(1));
    expect(
      repo.serviceReport(reportProject, id)['sync_status'],
      'Synchronisiert',
    );
    expect(server.reportBodies.single, original['capture_request']);
    expect(repo.pending, 0);
  });

  test('lost accepted response is diagnosed as original even after a project rename', () async {
    final id = await signed();
    final original = repo.serviceReport(reportProject, id);
    server.online = true;
    server.loseAck = true;
    await repo.sync();
    server.currentContext = {
      'project_name': 'Neues Projekt',
      'customer': 'Neuer Kunde',
    };
    final diagnosis = await repo.diagnoseServiceReport(reportProject, id);
    expect(diagnosis['state'], 'accepted');
    await repo.retryServiceReport(reportProject, id);
    expect(
      repo.serviceReport(reportProject, id)['sync_status'],
      'Synchronisiert',
    );
    expect(server.reportReceipts, hasLength(1));
    expect(server.reportBodies, everyElement(original['capture_request']));
    expect(repo.serviceReports(reportProject), hasLength(1));
  });

  test('changed server context between review and confirmation leaves only the original', () async {
    final id = await conflict();
    final diagnosis = await repo.diagnoseServiceReport(reportProject, id);
    server.currentContext['customer'] = 'Nochmals geändert';
    await expectLater(
      repo.copyConflictedServiceReport(
        reportProject,
        id,
        reviewedDiagnosis: diagnosis,
      ),
      throwsA(isA<ApiException>()),
    );
    expect(repo.serviceReports(reportProject), hasLength(1));
    expect(
      repo
          .serviceReport(reportProject, id)
          .containsKey('conflict_successor_id'),
      isFalse,
    );
    expect(server.reportReceipts, isEmpty);
  });

  test(
    'unknown diagnosis fields and offline failure never permit a copy',
    () async {
      final id = await conflict();
      server.invalidDiagnosis = true;
      await expectLater(
        repo.diagnoseServiceReport(reportProject, id),
        throwsA(isA<ApiException>()),
      );
      server.invalidDiagnosis = false;
      final diagnosis = await repo.diagnoseServiceReport(reportProject, id);
      server.online = false;
      await expectLater(
        repo.copyConflictedServiceReport(
          reportProject,
          id,
          reviewedDiagnosis: diagnosis,
        ),
        throwsA(isA<ApiException>()),
      );
      expect(repo.serviceReports(reportProject), hasLength(1));
    },
  );

  test('disk failure publishes neither successor nor link and the original remains exact', () async {
    final id = await conflict();
    final original = repo.serviceReport(reportProject, id);
    final diagnosis = await repo.diagnoseServiceReport(reportProject, id);
    device.failWrites = true;
    device.writesBeforeFailure =
        1; // Fresh capability receipt succeeds; draft commit fails.
    await expectLater(
      repo.copyConflictedServiceReport(
        reportProject,
        id,
        reviewedDiagnosis: diagnosis,
      ),
      throwsA(isA<FileSystemException>()),
    );
    expect(repo.serviceReports(reportProject), hasLength(1));
    expect(repo.serviceReport(reportProject, id), original);
    device.failWrites = false;
    await repo.copyConflictedServiceReport(
      reportProject,
      id,
      reviewedDiagnosis: diagnosis,
    );
    expect(repo.serviceReports(reportProject), hasLength(2));
  });

  test('known project denial hides cached reports without deleting their originals', () async {
    final id = await conflict();
    server.forbidden = true;
    await expectLater(
      repo.diagnoseServiceReport(reportProject, id),
      throwsA(isA<ApiException>()),
    );
    expect(repo.canAccessServiceReports(reportProject), isFalse);
    expect(
      () => repo.serviceReport(reportProject, id),
      throwsA(isA<ApiException>()),
    );
    final vault = await device.open(repo.storageNamespace, reportUser);
    final stored = await vault.read();
    expect(stored!['service_report_records'][id]['status'], 'signed');
    expect(
      stored['service_report_records'][id]['capture_request']['entry_id'],
      id,
    );
  });

  test(
    'older server capability never revokes a valid project or imports a report',
    () async {
      final id = await conflict();
      final original = repo.serviceReport(reportProject, id);
      server.reportMetadata = {};
      await expectLater(
        repo.diagnoseServiceReport(reportProject, id),
        throwsA(isA<ApiException>()),
      );
      expect(repo.reportConflictReviewSupported, isFalse);
      expect(repo.canAccessServiceReports(reportProject), isTrue);
      expect(repo.serviceReport(reportProject, id), original);
      expect(server.diagnoses, isEmpty);
      expect(server.reportReceipts, isEmpty);
    },
  );

  test(
    'account lock while diagnosis is pending cannot publish a new draft',
    () async {
      final id = await conflict();
      server.diagnosisEntered = Completer<void>();
      server.diagnosisRelease = Completer<void>();
      final pending = repo.diagnoseServiceReport(reportProject, id);
      final expectation = expectLater(pending, throwsA(anything));
      await server.diagnosisEntered!.future;
      await repo.lock();
      server.diagnosisRelease!.complete();
      await expectation;
      expect(repo.permitted, isFalse);
      expect(server.reportReceipts, isEmpty);
    },
  );
}

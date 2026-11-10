@Tags(['posix_backend'])
library;

import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:smartplan_office/api.dart';
import 'package:smartplan_office/offline_plans.dart';

import 'backend_integration_test.dart' show BackendHttp;
import 'business_offline_media_test.dart' show fieldPng;
import 'business_offline_reports_test.dart' show reportInk;
import 'import_backend_integration_test.dart' show fixture, ImportConnection;
import 'offline_plans_test.dart' show TestDevice, idle;

/// Drops only the response after a real HTTP request has committed successfully.
/// Both the retry and the archive download still use the real Python service.
class ReportHttpConnection extends ImportConnection {
  ReportHttpConnection(super.base);
  bool loseReportAck = false;
  final captures = <Map<String, dynamic>>[];

  @override
  Future<dynamic> call(String path, [Map<String, dynamic>? body]) async {
    if (connected && path == '/api/business/service-reports/offline') {
      captures.add(Map<String, dynamic>.from(jsonDecode(jsonEncode(body))));
    }
    final result = await super.call(path, body);
    if (path == '/api/business/service-reports/offline' && loseReportAck) {
      loseReportAck = false;
      throw const ApiException(0, 'Synthetic loss after committed report');
    }
    return result;
  }
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  final backend = Directory(
    Platform.environment['SMARTPLAN_TEST_BACKEND'] ?? '../backend',
  ).absolute;
  final python =
      Platform.environment['SMARTPLAN_TEST_PYTHON'] ??
      '${backend.path}/.venv/${Platform.isWindows ? 'Scripts/python.exe' : 'bin/python'}';

  test('Real HTTP joins offline time, photo and signed report after restart without duplicate capture', () async {
    await HttpOverrides.runWithHttpOverrides(() async {
      final directory = await Directory.systemTemp.createTemp(
        'smartplan-offline-service-http-',
      );
      Process? process;
      StreamIterator<String>? output;
      StreamSubscription<String>? errors;
      OfficeApi? api;
      ReportHttpConnection? connection;
      OfflinePlans? repo;
      final diagnostics = StringBuffer();
      try {
        final seed = fixture.replaceFirst(
          'app = create_app(',
          '''from business_schema import ensure_schema
from business_planning import Planning
ensure_schema(office, activate=True)
Planning(office).save_employee(user, dict(request_id='1'*32, user_id=user['id'], name='Synthetic employee', active=True, weekly_minutes=2400, hourly_cost_minor=1000))
app = create_app(''',
        );
        process = await Process.start(python, [
          '-u',
          '-c',
          seed,
          directory.path,
        ], workingDirectory: backend.path);
        errors = process.stderr
            .transform(utf8.decoder)
            .listen(diagnostics.write);
        output = StreamIterator(
          process.stdout
              .transform(utf8.decoder)
              .transform(const LineSplitter()),
        );
        if (!await output.moveNext().timeout(const Duration(seconds: 30))) {
          throw StateError('Fixture not ready: $diagnostics');
        }
        final hello = Map<String, dynamic>.from(jsonDecode(output.current));
        final base = 'http://127.0.0.1:${hello['port']}';
        api = OfficeApi(baseUrl: base, apiVersion: 'v1')
          ..token = hello['token'];
        final owner = api;
        final project = hello['project_id'] as String;
        var now = DateTime.now().toUtc().subtract(const Duration(minutes: 2));
        final device = TestDevice(Directory('${directory.path}/device'));
        connection = ReportHttpConnection(base);
        final transport = connection;
        OfflinePlans open() => OfflinePlans(
          api: owner,
          transport: transport,
          device: device,
          clock: () => now,
        );
        repo = open();
        await repo.login(
          Map<String, dynamic>.from(hello['user']),
          List<dynamic>.from(hello['projects']),
          businessTime: true,
          fieldMedia: true,
          offlineReports: true,
        );
        await idle(repo);
        expect(repo.canAccessServiceReports(project), isTrue);
        transport.connected = false;
        final time = await repo.saveTimeEvent(
          project,
          'start',
          occurredAt: now.subtract(const Duration(minutes: 45)),
        );
        await idle(repo);
        await repo.saveTimeEvent(
          project,
          'stop',
          entryId: time['id'],
          occurredAt: now,
        );
        final photo = await repo.captureFieldPhoto(
          project,
          fieldPng,
          filename: 'synthetic-inspection.png',
          mediaType: 'image/png',
          caption: 'Synthetische Prüfung vor Ort',
        );
        final draft = await repo.saveServiceReportDraft(
          project,
          title: 'Prüfung Süd: Rücklaufventil',
          description: 'Ventil ersetzt.\nDichtheit bei 8 bar geprüft.',
          notes: 'Bedienung erläutert.',
        );
        now = now.add(const Duration(seconds: 20));
        await repo.signServiceReport(
          project,
          draft['id'],
          signer: 'Synthetische Kundin',
          strokes: reportInk,
          expectedContentHash: draft['content_hash'],
        );
        await idle(repo);
        expect(repo.pending, 4);
        await repo.leave();
        repo.dispose();
        repo = open();
        await repo.resume();
        await idle(repo);
        expect(
          repo.serviceReports(project).single['content_hash'],
          draft['content_hash'],
        );
        expect(repo.serviceReports(project).single['strokes'], reportInk);
        expect(repo.timeEntries(project).single['status'], 'stopped');
        expect(await repo.fieldPhotoSource(photo['local_id']), fieldPng);

        transport.connected = true;
        transport.loseReportAck = true;
        await repo.sync();
        expect(repo.pending, 1, reason: repo.notice);
        expect(transport.captures, hasLength(1));
        final accepted = Map<String, dynamic>.from(
          await owner.call('/api/business/service-reports/${draft['id']}'),
        );
        expect(accepted['status'], 'signed');
        expect(accepted['offline_capture']['content'], draft['content']);
        expect(
          accepted['offline_capture']['content_hash'],
          draft['content_hash'],
        );
        expect(accepted['offline_capture']['signed_at'], now.toIso8601String());
        expect(accepted['signer'], 'Synthetische Kundin');
        expect(accepted['strokes'], reportInk);
        expect(
          repo.serviceReports(project).single['sync_status'],
          isNot('Synchronisiert'),
        );
        await repo.sync();
        expect(repo.pending, 0, reason: repo.notice);
        expect(transport.captures, hasLength(2));
        expect(transport.captures.first, transport.captures.last);
        final archived = Map<String, dynamic>.from(
          await owner.call('/api/business/service-reports/${draft['id']}'),
        );
        expect(archived, accepted);
        final reportList = await owner.call(
          '/api/business/service-reports?project_id=$project',
        );
        expect(reportList['items'], hasLength(1));
        final serverPdf = await owner.bytes(
          '/api/business/service-reports/${draft['id']}/pdf',
          mediaType: 'application/pdf',
        );
        expect(serverPdf.take(5).toList(), ascii.encode('%PDF-'));
        expect(await repo.serviceReportPdf(project, draft['id']), serverPdf);
        final timeEntry = await owner.call(
          '/api/business/time/entries/${time['id']}',
        );
        expect(timeEntry['events'], hasLength(2));
        final uploadedPhoto = repo.fieldPhotos(project).single;
        expect(uploadedPhoto['sync_status'], 'Synchronisiert');
        expect(
          await owner.bytes(
            '/api/business/media/${uploadedPhoto['server_id']}/content',
            mediaType: 'image/png',
          ),
          fieldPng,
        );

        await expectLater(
          transport.call('/api/business/finance/open-items'),
          throwsA(
            isA<ApiException>().having((error) => error.status, 'status', 403),
          ),
        );
        await repo.sync();
        expect(transport.captures, hasLength(2));
        transport.connected = false;
        await repo.leave();
        repo.dispose();
        repo = open();
        await repo.resume();
        await idle(repo);
        expect(repo.pending, 0);
        expect(
          repo.serviceReports(project).single['sync_status'],
          'Synchronisiert',
        );
        expect(await repo.serviceReportPdf(project, draft['id']), serverPdf);
        // A real customer rename changes the live project snapshot while the
        // second frozen offline capture remains on disk, never accepted.
        final conflicting = await repo.saveServiceReportDraft(
          project,
          title: 'Neuer Prüfbericht',
          description: 'Prüfung vor Kundenumbenennung.',
          notes: '',
        );
        await repo.signServiceReport(
          project,
          conflicting['id'],
          signer: 'Bisheriger Kundenname',
          strokes: reportInk,
        );
        await idle(repo);
        final frozen = repo.serviceReport(
          project,
          conflicting['id'],
        )['capture_request'];
        final customerId = (hello['projects'] as List).single['customer_id'];
        await owner.call('/api/customers/$customerId', {
          'name': 'Geänderter synthetischer Kunde',
        });
        transport.connected = true;
        await repo.sync();
        expect(
          repo.serviceReport(project, conflicting['id'])['sync_status'],
          'Konflikt',
        );
        final diagnosis = await repo.diagnoseServiceReport(
          project,
          conflicting['id'],
        );
        expect(diagnosis['state'], 'context_changed');
        expect(
          diagnosis['current_context']['customer'],
          'Geänderter synthetischer Kunde',
        );
        final copied = await repo.copyConflictedServiceReport(
          project,
          conflicting['id'],
          reviewedDiagnosis: diagnosis,
        );
        expect(copied['status'], 'draft');
        expect(copied.containsKey('strokes'), isFalse);
        await repo.signServiceReport(
          project,
          copied['id'],
          signer: 'Neu bestätigter Kundenname',
          strokes: reportInk,
        );
        await idle(repo);
        await repo.sync();
        expect(
          repo.serviceReport(project, copied['id'])['sync_status'],
          'Synchronisiert',
        );
        expect(
          repo.serviceReport(project, conflicting['id'])['sync_status'],
          'Konflikt',
        );
        expect(
          repo.serviceReport(project, conflicting['id'])['capture_request'],
          frozen,
        );
        final remoteReports = await owner.call(
          '/api/business/service-reports?project_id=$project',
        );
        expect(remoteReports['items'], hasLength(2));
        expect(
          (remoteReports['items'] as List).map((r) => r['id']),
          isNot(contains(conflicting['id'])),
        );
        final freshPdf = await owner.bytes(
          '/api/business/service-reports/${copied['id']}/pdf',
          mediaType: 'application/pdf',
        );
        expect(await repo.serviceReportPdf(project, copied['id']), freshPdf);
        expect(await repo.serviceReportPdf(project, draft['id']), serverPdf);
        expect(repo.pending, 1);
      } finally {
        if (repo != null) {
          await idle(repo);
          await repo.flush();
          await repo.leave();
          repo.dispose();
        }
        connection?.dispose();
        api?.dispose();
        if (process != null) {
          process.kill();
          try {
            await process.exitCode.timeout(const Duration(seconds: 5));
          } on TimeoutException {
            process.kill(ProcessSignal.sigkill);
            await process.exitCode;
          }
        }
        await output?.cancel();
        await errors?.cancel();
        await directory.delete(recursive: true);
      }
    }, BackendHttp());
  }, skip: File(python).existsSync() ? false : 'Backend virtualenv required');
}

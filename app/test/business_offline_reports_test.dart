import 'dart:async';
import 'dart:convert';
import 'dart:io';
import 'dart:typed_data';

import 'package:cryptography/cryptography.dart';
import 'package:cryptography/dart.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:smartplan_office/api.dart';
import 'package:smartplan_office/offline_plans.dart';

import 'offline_plans_test.dart' show PlanServer, TestDevice, idle, loginV2;

class PdfHashGate extends DartSha256 {
  PdfHashGate(this.pdf);
  final List<int> pdf;
  final entered = Completer<void>(), release = Completer<void>();
  int matches = 0;
  @override
  Future<Hash> hash(List<int> input) async {
    if (input.length == pdf.length &&
        List.generate(pdf.length, (i) => i).every((i) => input[i] == pdf[i])) {
      matches++;
      if (matches == 2) {
        entered.complete();
        await release.future;
      }
    }
    return super.hash(input);
  }
}

class PdfGateCryptography extends DartCryptography {
  PdfGateCryptography(this.gate);
  final PdfHashGate gate;
  @override
  Sha256 sha256() => gate;
}

const reportUser = 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa';
const reportProject = 'cccccccccccccccccccccccccccccccc';
const reportInk = <List<List<double>>>[
  [
    [0.1, 0.2],
    [0.6, 0.8],
    [0.9, 0.3],
  ],
];

Map<String, dynamic> copyReport(Map<String, dynamic> value) =>
    Map<String, dynamic>.from(jsonDecode(jsonEncode(value)));

class OfflineReportServer extends PlanServer {
  OfflineReportServer(this.clock);
  final DateTime Function() clock;
  bool reportGrant = true, reportEnabled = true, wrongResponse = false;
  bool corruptPdf = false, unavailablePdf = false;
  int? reportFailure;
  Map<String, dynamic> reportMetadata = {};
  final reportBodies = <Map<String, dynamic>>[];
  final reportReceipts = <String, Map<String, dynamic>>{};
  final reportPdf = Uint8List.fromList(
    ascii.encode('%PDF-1.4\nsynthetic archive\n%%EOF'),
  );

  @override
  Future<dynamic> call(String path, [Map<String, dynamic>? body]) async {
    if (!online) throw const ApiException(0, 'Offline');
    if (path.split('?').first == '/api/business/capabilities') {
      return {
        'readonly': false,
        'permissions': ['documents.read', 'documents.write'],
        'capabilities': ['business_operations'],
        ...reportMetadata,
      };
    }
    if (path == '/api/business/offline/access/v2') {
      return v2Grant(
        kind: 'business',
        at: clock(),
        extra: [if (reportGrant) 'offline_reports'],
        reports: [if (reportGrant) reportProject],
      );
    }
    if (path == '/api/business/service-reports/offline') {
      reportBodies.add(copyReport(body!));
      if (forbidden) throw const ApiException(403, 'Zugriff entzogen');
      if (reportFailure != null) {
        throw ApiException(reportFailure!, 'Synthetischer Übertragungsfehler');
      }
      if (!reportEnabled)
        throw const ApiException(423, 'Dokumentation pausiert');
      final request = body['request_id'] as String;
      if (!reportReceipts.containsKey(request)) {
        final content = Map<String, dynamic>.from(body['content']);
        final pdfHash = (await Sha256().hash(reportPdf)).bytes
            .map((byte) => byte.toRadixString(16).padLeft(2, '0'))
            .join();
        reportReceipts[request] = {
          'id': body['entry_id'],
          'project_id': body['project_id'],
          'kind': 'service',
          'title': content['title'],
          'description': content['description'],
          'notes': content['notes'],
          'media_ids': <String>[],
          'status': 'signed',
          'revision': 2,
          'content_hash': body['content_hash'],
          'signed_content_hash': body['content_hash'],
          'signer': body['signer'],
          'strokes': body['strokes'],
          'signed_at': body['signed_at'],
          'signed_by': reportUser,
          'created_by': reportUser,
          'created_at': clock().toIso8601String(),
          'updated_by': reportUser,
          'updated_at': clock().toIso8601String(),
          'pdf_sha256': pdfHash,
          'offline_capture': {
            'schema': 1,
            'content': content,
            'content_hash': body['content_hash'],
            'signed_at': body['signed_at'],
            'received_at': clock().toIso8601String(),
            'request_id': request,
          },
        };
      }
      if (loseAck) {
        loseAck = false;
        throw const ApiException(0, 'Gespeichert, Bestätigung verloren');
      }
      final response = copyReport(reportReceipts[request]!);
      if (wrongResponse) response['project_id'] = 'd' * 32;
      return response;
    }
    return super.call(path, body);
  }

  @override
  Future<Uint8List> bytes(
    String path, {
    required String mediaType,
    int maxBytes = 20 * 1024 * 1024,
  }) async {
    if (!online) throw const ApiException(0, 'Offline');
    if (forbidden) throw const ApiException(403, 'Zugriff entzogen');
    if (path.contains('/service-reports/') && path.endsWith('/pdf')) {
      if (unavailablePdf) throw const ApiException(0, 'PDF-Abruf unterbrochen');
      return corruptPdf
          ? Uint8List.fromList(
              ascii.encode('%PDF-1.4\nFremdes Dokument\n%%EOF'),
            )
          : reportPdf;
    }
    throw const ApiException(404, 'Datei nicht vorhanden');
  }
}

void main() {
  late Directory folder;
  late TestDevice device;
  late OfflineReportServer server;
  late OfflinePlans repo;
  late DateTime now;
  const user = {'id': reportUser, 'role': 'technician'};
  const projects = [
    {
      'id': reportProject,
      'name': 'Synthetische Wartung Süd',
      'customer': 'Synthetischer Auftraggeber',
    },
  ];

  Future<Map<String, dynamic>> draft() => repo.saveServiceReportDraft(
    reportProject,
    title: 'Druckprüfung an Anlage Süd',
    description: 'Ventil gewechselt. Prüfung: 8 bar.\nDichtheit bestätigt.',
    notes: 'Kunde erhielt die Bedienhinweise.',
  );

  Future<Map<String, dynamic>> sign(String id) => repo.signServiceReport(
    reportProject,
    id,
    signer: 'Synthetische Kundin',
    strokes: reportInk,
  );

  Future<void> reopen() async {
    await idle(repo);
    await repo.leave();
    repo.dispose();
    repo = OfflinePlans(
      api: server,
      transport: server.offlineTransport,
      device: device,
      clock: () => now,
    );
    repo.api.token = null;
    await repo.resume();
    await idle(repo);
  }

  setUp(() async {
    now = DateTime.utc(2026, 11, 3, 9);
    folder = await Directory.systemTemp.createTemp('smartplan-offline-report-');
    device = TestDevice(folder);
    server = OfflineReportServer(() => now)..token = 'synthetic-full-session';
    repo = OfflinePlans(
      api: server,
      transport: server.offlineTransport,
      device: device,
      clock: () => now,
    );
    await loginV2(repo, user, projects, offlineReports: true);
    await idle(repo);
    server.online = false;
  });

  tearDown(() async {
    await idle(repo);
    repo.dispose();
    server.dispose();
    await folder.delete(recursive: true);
  });

  test('company switch while hashing a private report PDF never writes its bytes to B', () async {
    final created = await draft();
    await sign(created['id']);
    await idle(repo);
    final scopeA = repo.storageNamespace;
    final gate = PdfHashGate(server.reportPdf);
    final previousCrypto = Cryptography.instance;
    Cryptography.instance = PdfGateCryptography(gate);
    try {
      server.online = true;
      final syncing = repo.sync();
      await gate.entered.future.timeout(const Duration(seconds: 5));
      server.instanceId = 'b' * 32;
      await loginV2(repo, user, projects, offlineReports: true);
      final scopeB = repo.storageNamespace;
      expect(scopeB, isNot(scopeA));
      gate.release.complete();
      await syncing;
      await idle(repo);
      expect(repo.serviceReports(reportProject), isEmpty);
      final bVault = await device.open(scopeB, reportUser);
      final bAssets = Directory('${bVault.directory.path}/assets');
      expect(
        await bAssets.exists() ? await bAssets.list().toList() : [],
        isEmpty,
      );
      final aState = await (await device.open(scopeA, reportUser)).read();
      expect(aState!['service_report_outbox'], [created['id']]);
      expect(
        aState['service_report_records'][created['id']]['pdf_source'],
        isNull,
      );
      Cryptography.instance = previousCrypto;
      server.instanceId = 'f' * 32;
      await loginV2(repo, user, projects, offlineReports: true);
      await idle(repo);
      expect(
        await repo.serviceReportPdf(reportProject, created['id']),
        server.reportPdf,
      );
      expect(repo.pending, 0);
      expect(
        await bAssets.exists() ? await bAssets.list().toList() : [],
        isEmpty,
      );
    } finally {
      if (!gate.release.isCompleted) gate.release.complete();
      Cryptography.instance = previousCrypto;
    }
  });

  test(
    'Unsigned draft survives restart and is never sent as a signed report',
    () async {
      final created = await draft();
      expect(created['status'], 'draft');
      expect(repo.pending, 0);
      await reopen();
      final restored = repo.serviceReports(reportProject).single;
      expect(restored['id'], created['id']);
      expect(restored['description'], created['description']);
      expect(restored['content_hash'], created['content_hash']);
      server.online = true;
      await repo.sync();
      expect(server.reportBodies, isEmpty);
    },
  );

  test('Signed original is encrypted, survives restart and repeats the exact capture after lost ACK', () async {
    final created = await draft();
    now = now.add(const Duration(minutes: 5));
    final signed = await sign(created['id']);
    await idle(repo);
    expect(signed['status'], 'signed');
    expect(repo.pending, 1);
    final plaintext = await folder
        .list(recursive: true)
        .where((entry) => entry is File)
        .cast<File>()
        .asyncMap((file) => file.readAsBytes())
        .toList();
    for (final bytes in plaintext) {
      final text = utf8.decode(bytes, allowMalformed: true);
      expect(text, isNot(contains('Druckprüfung')));
      expect(text, isNot(contains('Synthetische Kundin')));
    }
    await reopen();
    final reopened = repo.serviceReports(reportProject).single;
    expect(reopened['id'], created['id']);
    expect(reopened['signer'], 'Synthetische Kundin');
    expect(reopened['strokes'], reportInk);
    server.online = true;
    server.loseAck = true;
    await repo.sync();
    expect(repo.pending, 1);
    expect(server.reportReceipts, hasLength(1));
    expect(
      repo.serviceReports(reportProject).single['sync_status'],
      isNot('Synchronisiert'),
    );
    now = now.add(const Duration(hours: 1));
    await repo.sync();
    expect(repo.pending, 0);
    expect(server.reportBodies, hasLength(2));
    expect(server.reportBodies.first, server.reportBodies.last);
    expect(server.reportBodies.first['entry_id'], created['id']);
    expect(server.reportReceipts, hasLength(1));
    expect(
      repo.serviceReports(reportProject).single['sync_status'],
      'Synchronisiert',
    );
    await repo.sync();
    expect(server.reportBodies, hasLength(2));
  });

  test(
    'Signed contents cannot be edited or replaced with another signature',
    () async {
      final created = await draft();
      final signed = await sign(created['id']);
      await idle(repo);
      await expectLater(
        repo.saveServiceReportDraft(
          reportProject,
          entryId: created['id'],
          title: 'Geänderter Auftrag',
          description: 'Nicht unterschriebene andere Leistung',
        ),
        throwsA(isA<ApiException>().having((e) => e.status, 'status', 409)),
      );
      await expectLater(
        repo.signServiceReport(
          reportProject,
          created['id'],
          signer: 'Andere Person',
          strokes: reportInk,
        ),
        throwsA(isA<ApiException>()),
      );
      expect(
        repo.serviceReports(reportProject).single['content_hash'],
        signed['content_hash'],
      );
      expect(
        repo.serviceReports(reportProject).single['signer'],
        'Synthetische Kundin',
      );
      expect(repo.pending, 1);
    },
  );

  test(
    'A failed durable signature write leaves the last committed draft unsigned',
    () async {
      final created = await draft();
      await idle(repo);
      final vault = await device.open(repo.storageNamespace, reportUser);
      final original = vault.directory.path;
      final backup = await vault.directory.rename('$original.backup');
      await File(original).writeAsString('Simulated unavailable storage');
      try {
        await expectLater(
          sign(created['id']),
          throwsA(isA<FileSystemException>()),
        );
        expect(repo.serviceReports(reportProject).single['status'], 'draft');
        expect(repo.pending, 0);
      } finally {
        await File(original).delete();
        await backup.rename(original);
      }
      await reopen();
      expect(repo.serviceReports(reportProject).single['status'], 'draft');
      await sign(created['id']);
      expect(repo.pending, 1);
    },
  );

  test(
    'A response for another project cannot acknowledge the frozen signature',
    () async {
      final created = await draft();
      await sign(created['id']);
      await idle(repo);
      server.online = true;
      server.wrongResponse = true;
      await repo.sync();
      expect(repo.pending, 1);
      expect(
        repo.serviceReports(reportProject).single['sync_status'],
        isNot('Synchronisiert'),
      );
      final first = copyReport(server.reportBodies.single);
      server.wrongResponse = false;
      await repo.sync();
      expect(repo.pending, 0);
      expect(server.reportBodies.last, first);
    },
  );

  test(
    'A conflict keeps the signed original and stops automatic retries',
    () async {
      final created = await draft();
      await sign(created['id']);
      await idle(repo);
      server.online = true;
      server.reportFailure = 409;
      await repo.sync();
      expect(repo.pending, 1);
      expect(
        repo.serviceReports(reportProject).single['sync_status'],
        'Konflikt',
      );
      final attempts = server.reportBodies.length;
      await repo.sync();
      expect(server.reportBodies, hasLength(attempts));
      expect(repo.serviceReports(reportProject).single['strokes'], reportInk);
    },
  );

  test(
    'Module pause retains exact signed input and resumes after reactivation',
    () async {
      final created = await draft();
      await sign(created['id']);
      await idle(repo);
      server.online = true;
      server.reportEnabled = false;
      await repo.sync();
      expect(repo.pending, 1);
      expect(
        repo.serviceReports(reportProject).single['sync_status'],
        'Wartet auf Freigabe',
      );
      final original = copyReport(server.reportBodies.single);
      server.online = false;
      await reopen();
      server.online = true;
      server.reportEnabled = true;
      await repo.sync();
      expect(repo.pending, 0);
      expect(server.reportBodies.last, original);
    },
  );

  test('Expired grants and clock rollback retain captured originals without allowing access', () async {
    final created = await draft();
    await sign(created['id']);
    await idle(repo);
    final captured = now;
    now = now.subtract(const Duration(hours: 1));
    expect(repo.offlineReportsSupported, isFalse);
    expect(
      () => repo.serviceReports(reportProject),
      throwsA(isA<ApiException>()),
    );
    expect(repo.pending, 1);
    now = captured.add(const Duration(days: 7));
    expect(repo.offlineReportsSupported, isFalse);
    await repo.sync();
    expect(server.reportBodies, isEmpty);
    expect(repo.pending, 1);
    server.online = true;
    await loginV2(repo, user, projects, offlineReports: true);
    await idle(repo);
    expect(repo.pending, 0);
    expect(repo.serviceReports(reportProject).single['id'], created['id']);
  });

  test(
    'A missing report grant cannot be silently expanded and preserves old work',
    () async {
      final created = await draft();
      await sign(created['id']);
      await idle(repo);
      server.online = true;
      server.reportGrant = false;
      final oldNamespace = repo.storageNamespace;
      await expectLater(
        loginV2(repo, user, projects, offlineReports: true),
        throwsA(isA<ApiException>()),
      );
      await idle(repo);
      expect(repo.offlineReportsSupported, isFalse);
      await expectLater(draft(), throwsA(isA<ApiException>()));
      expect(repo.active, isFalse);
      expect(
        (await (await device.open(
          oldNamespace,
          reportUser,
        )).read())!['service_report_outbox'],
        hasLength(1),
      );
      expect(server.reportBodies, isEmpty);
      server.reportGrant = true;
      await loginV2(repo, user, projects, offlineReports: true);
      await idle(repo);
      expect(repo.pending, 0);
      expect(repo.serviceReports(reportProject).single['id'], created['id']);
    },
  );

  test('Authentication loss locks local access while preserving the queued capture', () async {
    final created = await draft();
    await sign(created['id']);
    await idle(repo);
    server.online = true;
    server.reportFailure = 401;
    await repo.sync();
    expect(repo.permitted, isFalse);
    expect(repo.pending, 1);
    expect(
      () => repo.serviceReports(reportProject),
      throwsA(isA<ApiException>()),
    );
    server.reportFailure = null;
    await loginV2(repo, user, projects, offlineReports: true);
    await idle(repo);
    expect(repo.pending, 0);
    expect(server.reportReceipts, hasLength(1));
  });

  test(
    'Invalid strokes are rejected before any signed capture is durable',
    () async {
      final created = await draft();
      for (final invalid in <List<List<List<double>>>>[
        [],
        [
          [
            [0.2, 0.3],
          ],
        ],
        [
          [
            [0.1, 0.2],
            [1.1, 0.7],
          ],
        ],
        [
          [
            [0.1, 0.2],
            [double.nan, 0.7],
          ],
        ],
      ]) {
        await expectLater(
          repo.signServiceReport(
            reportProject,
            created['id'],
            signer: 'Kunde',
            strokes: invalid,
          ),
          throwsA(anything),
        );
        expect(repo.serviceReports(reportProject).single['status'], 'draft');
        expect(repo.pending, 0);
      }
    },
  );

  test('Server acknowledgement alone does not claim an unavailable archive PDF is synchronized', () async {
    final created = await draft();
    await sign(created['id']);
    await idle(repo);
    await expectLater(
      repo.serviceReportPdf(reportProject, created['id']),
      throwsA(isA<ApiException>()),
    );
    server.online = true;
    server.unavailablePdf = true;
    await repo.sync();
    expect(server.reportReceipts, hasLength(1));
    expect(repo.pending, 1);
    expect(
      repo.serviceReports(reportProject).single['sync_status'],
      'Serverbestätigt · PDF wird geladen',
    );
    await expectLater(
      repo.serviceReportPdf(reportProject, created['id']),
      throwsA(isA<ApiException>()),
    );
    final original = copyReport(server.reportBodies.single);
    server.online = false;
    await reopen();
    server.online = true;
    server.unavailablePdf = false;
    await repo.sync();
    expect(repo.pending, 0);
    expect(server.reportReceipts, hasLength(1));
    expect(server.reportBodies.last, original);
    server.online = false;
    await reopen();
    expect(
      await repo.serviceReportPdf(reportProject, created['id']),
      server.reportPdf,
    );
  });

  test(
    'A PDF with the wrong digest cannot replace the signed archive',
    () async {
      final created = await draft();
      await sign(created['id']);
      await idle(repo);
      server.online = true;
      server.corruptPdf = true;
      await repo.sync();
      expect(repo.pending, 1);
      expect(
        repo.serviceReports(reportProject).single['sync_status'],
        isNot('Synchronisiert'),
      );
      await expectLater(
        repo.serviceReportPdf(reportProject, created['id']),
        throwsA(isA<ApiException>()),
      );
      server.corruptPdf = false;
      await repo.sync();
      expect(repo.pending, 0);
      expect(
        await repo.serviceReportPdf(reportProject, created['id']),
        server.reportPdf,
      );
    },
  );

  test('Known permission denial hides cached report content without deleting the capture', () async {
    final created = await draft();
    await sign(created['id']);
    await idle(repo);
    server.online = true;
    server.forbidden = true;
    await repo.sync();
    expect(repo.pending, 1);
    expect(repo.canAccessServiceReports(reportProject), isFalse);
    expect(
      () => repo.serviceReports(reportProject),
      throwsA(isA<ApiException>()),
    );
    final first = copyReport(server.reportBodies.single);
    server.forbidden = false;
    await loginV2(repo, user, projects, offlineReports: true);
    await idle(repo);
    expect(repo.pending, 0);
    expect(server.reportBodies.last, first);
    expect(
      repo.serviceReports(reportProject).single['signer'],
      'Synthetische Kundin',
    );
  });

  test(
    'A signature cannot approve a draft changed after the displayed review',
    () async {
      final reviewed = await draft();
      final changed = await repo.saveServiceReportDraft(
        reportProject,
        entryId: reviewed['id'],
        title: 'Überarbeiteter Bericht',
        description: 'Zusätzliche Arbeiten müssen neu geprüft werden.',
      );
      await expectLater(
        repo.signServiceReport(
          reportProject,
          reviewed['id'],
          signer: 'Synthetische Kundin',
          strokes: reportInk,
          expectedContentHash: reviewed['content_hash'],
        ),
        throwsA(
          isA<ApiException>().having((error) => error.status, 'status', 409),
        ),
      );
      expect(repo.pending, 0);
      expect(
        repo.serviceReports(reportProject).single['content_hash'],
        changed['content_hash'],
      );
      expect(repo.serviceReports(reportProject).single['status'], 'draft');
    },
  );

  test('Mutating the editor strokes after save cannot change the frozen signed original', () async {
    final created = await draft();
    final editorStrokes = [
      for (final stroke in reportInk)
        [for (final point in stroke) List<double>.from(point)],
    ];
    await repo.signServiceReport(
      reportProject,
      created['id'],
      signer: 'Synthetische Kundin',
      strokes: editorStrokes,
    );
    await idle(repo);
    editorStrokes.first.first[0] = 0.77;
    expect(repo.serviceReports(reportProject).single['strokes'], reportInk);
    server.online = true;
    await repo.sync();
    expect(server.reportBodies.single['strokes'], reportInk);
    server.online = false;
    await reopen();
    expect(repo.serviceReports(reportProject).single['strokes'], reportInk);
  });

  test('Capture hash agrees with Python canonical UTF-8 for Unicode and escaped whitespace', () async {
    final created = await repo.saveServiceReportDraft(
      reportProject,
      entryId: 'e' * 32,
      title: 'Prüfung 🛠',
      description: 'Zeile1\nCafe\u0301\u2028x',
      notes: '\tHinweis',
    );
    // Independently generated with Python json.dumps(sort_keys=True,
    // ensure_ascii=False, separators=(',', ':')) and SHA-256 over UTF-8.
    // No Unicode normalization: the combining accent remains part of the input.
    expect(created['content']['captured_at'], '2026-11-03T09:00:00.000Z');
    expect(
      created['content_hash'],
      'e4fbb2e972ff81b497348f664737ee3320bda8286425e8387832140b161ccce7',
    );
  });

  test('Metadata refresh applies pause, reactivation and project denial even without queued captures', () async {
    expect(repo.pending, 0);
    server.online = true;
    server.reportMetadata = {
      'report_project_ids': [reportProject],
      'report_writes_enabled': false,
    };
    await repo.sync();
    expect(repo.canAccessServiceReports(reportProject), isTrue);
    await expectLater(
      draft(),
      throwsA(
        isA<ApiException>().having((error) => error.status, 'status', 423),
      ),
    );
    expect(repo.serviceReports(reportProject), isEmpty);
    expect(repo.pending, 0);

    server.reportMetadata['report_writes_enabled'] = true;
    await repo.sync();
    final created = await draft();
    expect(created['status'], 'draft');
    expect(repo.pending, 0);
    expect(server.reportBodies, isEmpty);

    server.reportMetadata['report_project_ids'] = <String>[];
    await repo.sync();
    expect(repo.canAccessServiceReports(reportProject), isFalse);
    expect(
      () => repo.serviceReports(reportProject),
      throwsA(
        isA<ApiException>().having((error) => error.status, 'status', 403),
      ),
    );
    server.reportMetadata = {};
    await loginV2(repo, user, projects, offlineReports: true);
    await idle(repo);
    expect(repo.serviceReports(reportProject).single['id'], created['id']);
    expect(repo.pending, 0);
  });
}

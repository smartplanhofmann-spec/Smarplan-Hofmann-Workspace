import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:cryptography/cryptography.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:smartplan_office/api.dart';
import 'package:smartplan_office/business_project_economics.dart';
import 'package:smartplan_office/business_project_receipts.dart';
import 'package:smartplan_office/business_session.dart';

import 'backend_integration_test.dart' show BackendHttp;
import 'business_offline_media_test.dart' show fieldPng;
import 'import_backend_integration_test.dart' show fixture;

class EconomicsHttpApi extends OfficeApi {
  EconomicsHttpApi(String base) : super(baseUrl: base, apiVersion: 'v1');
  final drop = <String>{};
  final calls = <({String path, Map<String, dynamic> body})>[];
  bool wrongConfirm = false;
  String lastPath = '';
  @override
  Future<dynamic> call(String path, [Map<String, dynamic>? body]) async {
    lastPath = path;
    if (body != null)
      calls.add((
        path: path,
        body: Map<String, dynamic>.from(jsonDecode(jsonEncode(body))),
      ));
    final result = await super.call(path, body);
    if (body != null && drop.remove(path))
      throw const ApiException(0, 'Synthetic lost response after real commit');
    if (wrongConfirm && path == '/api/business/project-economics/confirm') {
      wrongConfirm = false;
      return {...Map<String, dynamic>.from(result), 'receipt_id': '9' * 32};
    }
    return result;
  }
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  test('Real HTTP receipt capture, review, allocation and correction retain original nonces and source history', () async {
    await HttpOverrides.runWithHttpOverrides(() async {
      final backend = Directory('../backend').absolute;
      final python =
          Platform.environment['SMARTPLAN_TEST_PYTHON'] ??
          '${backend.path}/.venv/${Platform.isWindows ? 'Scripts/python.exe' : 'bin/python'}';
      final directory = await Directory.systemTemp.createTemp(
        'smartplan-economics-http-',
      );
      Process? process;
      StreamIterator<String>? output;
      StreamSubscription<String>? stderr;
      EconomicsHttpApi? api;
      BusinessSession? session;
      final diagnostic = StringBuffer();
      try {
        final seed = fixture.replaceFirst(
          'app = create_app(',
          'from business_schema import ensure_schema\nensure_schema(office, activate=True)\napp = create_app(',
        );
        process = await Process.start(python, [
          '-u',
          '-c',
          seed,
          directory.path,
        ], workingDirectory: backend.path);
        stderr = process.stderr
            .transform(utf8.decoder)
            .listen(diagnostic.write);
        output = StreamIterator(
          process.stdout
              .transform(utf8.decoder)
              .transform(const LineSplitter()),
        );
        expect(
          await output.moveNext().timeout(const Duration(seconds: 30)),
          isTrue,
          reason: diagnostic.toString(),
        );
        final hello = Map<String, dynamic>.from(jsonDecode(output.current)),
            project = hello['project_id'] as String;
        api = EconomicsHttpApi('http://127.0.0.1:${hello['port']}')
          ..token = hello['token'];
        session = BusinessSession(
          api: api,
          projectId: project,
          projects: [
            Map<String, dynamic>.from((hello['projects'] as List).single),
          ],
        );
        final live = session;
        await live.load();
        expect(live.hasFeature('project_economics'), isTrue);
        final hash = (await Sha256().hash(fieldPng)).bytes
            .map((n) => n.toRadixString(16).padLeft(2, '0'))
            .join();
        const local = '11111111111111111111111111111111';
        final manifest = {
          'project_id': project,
          'filename': 'Synthetische-Rechnung.png',
          'media_type': 'image/png',
          'size': fieldPng.length,
          'sha256': hash,
        };
        final media = businessMap(
          await live.command(
            'project-receipt-media-$project-$local',
            '/receipt-media',
            manifest,
            validateResult: projectReceiptUploadValidator(
              phase: 'media',
              expected: manifest,
            ),
          ),
        );
        await api.call('/api/business/receipt-media/${media['id']}/chunks/0', {
          'content_base64': base64Encode(fieldPng),
        });
        await live.command(
          'project-receipt-media-complete-$project-$local',
          '/receipt-media/${media['id']}/complete',
          {'project_id': project},
          validateResult: projectReceiptUploadValidator(
            phase: 'media-complete',
            expected: manifest,
            mediaId: media['id'],
          ),
        );
        final captureKey = 'project-receipt-capture-$project-$local';
        api.drop.add('/api/business/finance/receipts');
        await expectLater(
          live.command(
            captureKey,
            '/finance/receipts',
            {'project_id': project, 'media_id': media['id'], 'note': ''},
            validateResult: projectReceiptUploadValidator(
              phase: 'capture',
              expected: manifest,
            ),
          ),
          throwsA(isA<ApiException>().having((e) => e.status, 'status', 0)),
        );
        expect(live.pending(captureKey), isTrue);
        expect(
          businessItems(await live.read(live.query('/finance/receipts'))),
          hasLength(1),
        );
        final captured = businessMap(
          await live.repeatProjectReceiptCommand(project, local),
        );
        final receipt = captured['id'] as String;
        expect(live.pending(captureKey), isFalse);
        final original = await api.bytes(
          '/api/business/finance/receipts/$receipt/original',
          mediaType: 'image/png',
        );
        expect(original, fieldPng);
        final reviewKey = 'project-receipt-review-$project-$receipt',
            reviewPath = '/finance/receipts/$receipt';
        final review = {
          'revision': 0,
          'vendor': 'Prüfbetrieb Süd',
          'invoice_number': 'SYN-REAL-42',
          'issue_date': '2026-11-03',
          'net': '100.00',
          'tax': '19.00',
          'gross': '119.00',
          'currency': 'EUR',
          'status': 'reviewed',
          'note': 'Original manuell geprüft.',
        };
        api.drop.add('/api/business$reviewPath');
        await expectLater(
          live.command(
            reviewKey,
            reviewPath,
            review,
            validateResult: projectReceiptReviewValidator(
              project: project,
              receipt: receipt,
              originalHash: hash,
              expected: review,
            ),
          ),
          throwsA(isA<ApiException>()),
        );
        final reviewed = businessMap(
          await live.repeatProjectReceiptCommand(
            project,
            receipt,
            review: true,
          ),
        );
        expect(reviewed['revision'], 1);
        final source = businessItems(
          await live.read(live.query('/project-economics/sources')),
        ).single;
        expect(source['classification_status'], 'unclassified');
        final values = {
          'project_id': project,
          'receipt_id': receipt,
          'source_revision': 1,
          'expected_revision': 0,
          'allocations': [
            {'category': 'external_service', 'amount_net': '60.00'},
            {'category': 'machine', 'amount_net': '10.00'},
            {'category': 'other', 'amount_net': '10.00'},
            {'category': 'stock_material', 'amount_net': '15.00'},
            {'category': 'excluded', 'amount_net': '5.00'},
          ],
          'reason':
              'Geprüfte vollständige Aufteilung ohne doppelte Materialkosten.',
        };
        final preview = businessMap(
          await api.call('/api/business/project-economics/preview', values),
        );
        final command = {
          ...values,
          'allocations': preview['allocations'],
          'preview_hash': preview['preview_hash'],
        };
        final costKey = 'project-economics-$project-$receipt';
        api.wrongConfirm = true;
        await expectLater(
          live.command(
            costKey,
            '/project-economics/confirm',
            command,
            validateResult: projectCostReceiptValidator(
              command,
              businessMap(preview['source']),
            ),
          ),
          throwsA(isA<ApiException>().having((e) => e.status, 'status', 0)),
        );
        expect(live.pending(costKey), isTrue);
        final classified = businessMap(
          await live.repeatProjectEconomicsCommand(project, receipt),
        );
        expect(classified['revision'], 1);
        var history = businessItems(
          await live.read(live.query('/project-economics/receipts/$receipt')),
        );
        expect(history, hasLength(1));
        final firstJson = jsonEncode(history.single);
        var summary = businessMap(
          await live.read(live.query('/project-economics')),
        );
        expect(summary['costs']['total_net'], '80.00');
        expect(summary['result']['complete_for_recorded_sources'], isTrue);
        // A later source review creates a visible unresolved issue without
        // overwriting the previous allocation or pretending its value is current.
        await live.command(reviewKey, reviewPath, {
          ...review,
          'revision': 1,
          'net': '110.00',
          'tax': '20.90',
          'gross': '130.90',
          'note': 'Belegprüfung anhand Original korrigiert.',
        });
        summary = businessMap(
          await live.read(live.query('/project-economics')),
        );
        expect(summary['result']['document_net_contribution'], isNull);
        final changed = {
          ...values,
          'source_revision': 2,
          'expected_revision': 1,
          'allocations': [
            {'category': 'external_service', 'amount_net': '110.00'},
          ],
          'reason': 'Neue Kosteneinordnung nach korrigierter Belegprüfung.',
        };
        final next = businessMap(
          await api.call('/api/business/project-economics/preview', changed),
        );
        final correction = {...changed, 'preview_hash': next['preview_hash']};
        await live.command(
          costKey,
          '/project-economics/confirm',
          correction,
          validateResult: projectCostReceiptValidator(
            correction,
            businessMap(next['source']),
          ),
        );
        history = businessItems(
          await live.read(live.query('/project-economics/receipts/$receipt')),
        );
        expect(history, hasLength(2));
        expect(jsonEncode(history.first), firstJson);
        summary = businessMap(
          await live.read(live.query('/project-economics')),
        );
        expect(summary['costs']['total_net'], '110.00');
        final captureRequests = api.calls
            .where((c) => c.path == '/api/business/finance/receipts')
            .map((c) => jsonEncode(c.body))
            .toSet();
        expect(captureRequests, hasLength(1));
        final firstConfirm = api.calls
            .where(
              (c) =>
                  c.path.endsWith('/project-economics/confirm') &&
                  c.body['expected_revision'] == 0,
            )
            .map((c) => jsonEncode(c.body))
            .toSet();
        expect(firstConfirm, hasLength(1));
        expect(
          businessItems(await live.read(live.query('/finance/receipts'))),
          hasLength(1),
        );
        expect(
          await api.bytes(
            '/api/business/finance/receipts/$receipt/original',
            mediaType: 'image/png',
          ),
          fieldPng,
        );
      } catch (error) {
        throw StateError(
          '$error at ${api?.lastPath}; server diagnostics: $diagnostic',
        );
      } finally {
        session?.dispose();
        api?.dispose();
        process?.kill();
        await output?.cancel();
        await stderr?.cancel();
        if (process != null)
          await process.exitCode.timeout(
            const Duration(seconds: 5),
            onTimeout: () => -1,
          );
        await directory.delete(recursive: true);
      }
    }, BackendHttp());
  }, timeout: const Timeout(Duration(seconds: 60)));
}

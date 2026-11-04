@Tags(['posix_backend'])
library;

import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:smartplan_office/api.dart';
import 'package:smartplan_office/business_session.dart';

import 'backend_integration_test.dart' show BackendHttp;
import 'import_backend_integration_test.dart' show fixture;

class PortalConnection extends OfficeApi {
  PortalConnection(String base) : super(baseUrl: base, apiVersion: 'v1');
  bool loseCreationReply = true;
  final createBodies = <Map<String, dynamic>>[];
  @override
  Future<dynamic> call(String path, [Map<String, dynamic>? body]) async {
    if (body != null && path == '/api/business/portal/grants') {
      createBodies.add(jsonDecode(jsonEncode(body)) as Map<String, dynamic>);
    }
    final result = await super.call(path, body);
    if (body != null &&
        path == '/api/business/portal/grants' &&
        loseCreationReply) {
      loseCreationReply = false;
      throw const ApiException(0, 'Synthetisch verlorene Erstellungsantwort');
    }
    return result;
  }
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  test(
    'Actual HTTP preserves one-time grant semantics and allows exact revocation with documents disabled',
    () async {
      final backend = Directory('../backend').absolute;
      final python =
          Platform.environment['SMARTPLAN_TEST_PYTHON'] ??
          '${backend.path}/.venv/bin/python';
      final temporary = await Directory.systemTemp.createTemp(
        'smartplan-portal-client-',
      );
      Process? server;
      StreamIterator<String>? output;
      StreamSubscription<String>? errors;
      PortalConnection? api;
      BusinessSession? session;
      final diagnostics = StringBuffer();
      try {
        final seed = fixture.replaceFirst(
          'app = create_app(',
          '''from business_schema import ensure_schema
ensure_schema(office, activate=True)
app = create_app(''',
        );
        server = await Process.start(python, [
          '-u',
          '-c',
          seed,
          temporary.path,
        ], workingDirectory: backend.path);
        errors = server.stderr
            .transform(utf8.decoder)
            .listen(diagnostics.write);
        output = StreamIterator(
          server.stdout.transform(utf8.decoder).transform(const LineSplitter()),
        );
        expect(
          await output.moveNext().timeout(const Duration(seconds: 30)),
          true,
          reason: '$diagnostics',
        );
        final setup = jsonDecode(output.current) as Map<String, dynamic>;
        await HttpOverrides.runWithHttpOverrides(() async {
          api = PortalConnection('http://127.0.0.1:${setup['port']}')
            ..token = setup['token'];
          final project = setup['project_id'];
          session = BusinessSession(api: api!, projectId: project);
          await session!.load();
          expect(
            session!.hasFeature('offer_portal'),
            true,
            reason: session!.error,
          );
          await session!.command('issuer', '/commercial/settings', {
            'revision': 0,
            'company_name': 'Synthetischer Aussteller',
            'address_line': 'Testweg 1',
            'postal_code': '10115',
            'city': 'Berlin',
            'country': 'DE',
            'issuer_mode': 'own',
            'issuing_enabled': false,
            'einvoice_format': 'none',
          });
          final draft = businessMap(
            await session!.command('offer', '/documents', {
              'project_id': project,
              'kind': 'offer',
              'title': 'Synthetisches Portalangebot',
              'issue_date': '2026-11-02',
              'due_date': '2026-11-16',
              'buyer': {
                'name': 'Synthetic customer',
                'address_line': 'Testweg 2',
                'postal_code': '10117',
                'city': 'Berlin',
                'country': 'DE',
              },
              'positions': [
                {
                  'description': 'Synthetische Montage',
                  'quantity': '2.5000',
                  'unit': 'HUR',
                  'unit_price_net': '50.00',
                  'unit_cost_net': '20.00',
                  'tax_rate': '19',
                  'kind': 'labor',
                },
              ],
            }),
          );
          final offer = businessMap(
            await session!.command(
              'finalize',
              '/documents/${draft['id']}/finalize',
              {'revision': draft['revision']},
            ),
          );
          final path = '/portal/grants?offer_id=${offer['id']}';
          final overview = businessMap(await session!.read(path));
          final source = businessMap(overview['source']);
          final values = <String, dynamic>{
            'offer_id': offer['id'],
            'source_revision': source['source_revision'],
            'content_hash': source['content_hash'],
            'pdf_hash': source['pdf_hash'],
            'recipient_name': 'Synthetischer Empfänger',
            'recipient_email': 'portal@example.test',
            'expires_in_days': 7,
            'confirmation': true,
          };
          await expectLater(
            session!.command('grant', '/portal/grants', values),
            throwsA(
              isA<ApiException>().having((error) => error.status, 'status', 0),
            ),
          );
          final replay = businessMap(
            await session!.command('grant', '/portal/grants', values),
          );
          expect(api!.createBodies, hasLength(2));
          expect(api!.createBodies[0], api!.createBodies[1]);
          expect(replay['link_available'], false);
          expect(replay.containsKey('portal_url'), false);
          final recorded = businessItems(await session!.read(path));
          expect(recorded, hasLength(1));
          expect(recorded.single.containsKey('portal_url'), false);
          expect(recorded.single.containsKey('key'), false);
          await session!.command(
            'revoke-lost',
            '/portal/grants/${recorded.single['id']}/revoke',
            {
              'reason': 'Verlorene Linkantwort ausdrücklich ersetzt',
              'confirmation': true,
            },
          );
          final replacement = businessMap(
            await session!.command('replacement', '/portal/grants', values),
          );
          expect(replacement['link_available'], true);
          final uri = Uri.parse(replacement['portal_url'] as String);
          expect(uri.scheme, 'https');
          expect(uri.host, 'office.example.test');
          expect(uri.path, '/office/portal.html');
          final grantId = '${replacement['grant']['id']}';
          expect(Uri.splitQueryString(uri.fragment)['grant'], grantId);
          final organization = businessMap(
            await session!.read('/organization'),
          );
          await session!.command('pause-documents', '/organization', {
            'revision': organization['revision'],
            'needs': organization['needs'],
            'modules': {
              for (final entry in businessMap(organization['modules']).entries)
                entry.key: {
                  'visible': businessMap(entry.value)['visibility_override'],
                  'enabled': entry.key != 'documents',
                },
            },
          });
          await session!.load();
          expect(session!.sectionEnabled('documents'), false);
          await expectLater(
            session!.command('blocked-create', '/portal/grants', values),
            throwsA(
              isA<ApiException>().having(
                (error) => error.status,
                'status',
                423,
              ),
            ),
          );
          final revoked = businessMap(
            await session!.command(
              'security-revoke',
              '/portal/grants/$grantId/revoke',
              {
                'reason': 'Synthetischer Sicherheitswiderruf bei pausiertem Dokumentmodul',
                'confirmation': true,
              },
            ),
          );
          expect(revoked['status'], 'revoked');
          final history = businessItems(await session!.read(path));
          expect(history, hasLength(2));
          expect(
            history.map((grant) => grant['status']),
            everyElement('revoked'),
          );
          final reread = businessMap(
            await session!.read('/documents/${offer['id']}'),
          );
          expect(reread['status'], 'final');
          expect(reread['revision'], offer['revision']);
        }, BackendHttp());
      } finally {
        session?.dispose();
        api?.dispose();
        await output?.cancel();
        await errors?.cancel();
        if (server != null) {
          server.kill();
          try {
            await server.exitCode.timeout(const Duration(seconds: 5));
          } on TimeoutException {
            server.kill(ProcessSignal.sigkill);
            await server.exitCode;
          }
        }
        await temporary.delete(recursive: true);
      }
    },
    skip: !Platform.isLinux,
    timeout: const Timeout(Duration(minutes: 2)),
  );
}

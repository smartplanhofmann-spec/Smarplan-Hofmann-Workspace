@Tags(['posix_backend'])
library;

import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:smartplan_office/api.dart';
import 'package:smartplan_office/business_resource_custody.dart';
import 'package:smartplan_office/business_service.dart';
import 'package:smartplan_office/business_session.dart';

import 'backend_integration_test.dart' show BackendHttp;
import 'import_backend_integration_test.dart' show fixture;

class GuardedServiceHttp extends OfficeApi {
  GuardedServiceHttp(String base) : super(baseUrl: base, apiVersion: 'v1');
  final posts = <Map<String, dynamic>>[];
  final accepted = <dynamic>[];
  String? holdRead;
  final held = Completer<void>(), release = Completer<void>();
  @override
  Future<dynamic> call(String path, [Map<String, dynamic>? body]) async {
    if (body != null) {
      posts.add({'path': path, 'body': jsonDecode(jsonEncode(body))});
    }
    final result = await super.call(path, body);
    if (body != null) {
      accepted.add(jsonDecode(jsonEncode(result)));
      if (accepted.length == 1) {
        throw const ApiException(0, 'Synthetic accepted HTTP response lost');
      }
    } else if (holdRead != null && Uri.parse(path).path == holdRead) {
      holdRead = null;
      held.complete();
      await release.future;
    }
    return result;
  }
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  for (final kind in ['service', 'custody']) {
    test(
      'actual $kind HTTP keeps one accepted original across closed-view retry and explicit replay',
      () async {
        final backend = Directory(
          Platform.environment['SMARTPLAN_TEST_BACKEND'] ?? '../backend',
        ).absolute;
        final python =
            Platform.environment['SMARTPLAN_TEST_PYTHON'] ??
            '${backend.path}/.venv/${Platform.isWindows ? 'Scripts/python.exe' : 'bin/python'}';
        final temporary = await Directory.systemTemp.createTemp(
          'smartplan-service-guard-http-',
        );
        Process? process;
        StreamIterator<String>? output;
        StreamSubscription<String>? errors;
        BusinessSession? session;
        GuardedServiceHttp? api;
        final diagnostics = StringBuffer();
        try {
          final seed = fixture
              .replaceFirst('app = create_app(', r'''
import tempfile, uuid
tempfile.tempdir = str(root)
from test_business_resource_custody import ResourceCustodyTests, req
from business_schema import ensure_schema
from business_service import Service
office.db.close()
domain = ResourceCustodyTests('runTest')
domain.setUp()
office = domain.office
ensure_schema(office, activate=True)
# The replacement database needs its own matching key, marker and storage.
# Keep the original fixture's company files separate and untouched.
key = Fernet.generate_key()
instance_id = uuid.uuid4().hex
storage = Storage(office, key, 'office.example.test', config={
    'server': {'path': str(root / 'service-review-storage')}})
bind(office, instance_id, 'office.example.test', key, storage)
token = office.login('custody-owner@example.test', 'Synthetic-resource-owner-password')
user = office.user(token)
project = domain.project
domain.profile(serial_number='SYN-HTTP-ORIGINAL', location='Original synthetic shelf')
service = Service(office)
incident = service.save(user, req(revision=0, customer_id=domain.customer['id'], person_id=None,
    project_id=project, asset_id=None, contract_id=None, visit_id=None, inquiry_id=None,
    defect_id=None, title='Synthetic HTTP private complaint', kind='complaint', priority='high',
    responsible_id=domain.manager['id'], follow_up_on=None, description='Synthetic original history'))
app = create_app(''')
              .replaceFirst(
                'projects=office.projects(user), project_id=project)',
                "projects=office.projects(user), project_id=project, service_id=incident['id'], resource_id=domain.resource['id'], instance_id=instance_id)",
              );
          process = await Process.start(python, [
            '-u',
            '-c',
            seed,
            temporary.path,
          ], workingDirectory: backend.path);
          errors = process.stderr
              .transform(utf8.decoder)
              .listen(diagnostics.write);
          output = StreamIterator(
            process.stdout
                .transform(utf8.decoder)
                .transform(const LineSplitter()),
          );
          expect(
            await output.moveNext().timeout(const Duration(seconds: 30)),
            true,
            reason: diagnostics.toString(),
          );
          final hello = businessMap(jsonDecode(output.current));
          await HttpOverrides.runWithHttpOverrides(() async {
            api = GuardedServiceHttp('http://127.0.0.1:${hello['port']}')
              ..token = hello['token'];
            session = BusinessSession(
              api: api!,
              projects: businessItems(hello['projects']),
            );
            await session!.load();
            expect(session!.allowed, true, reason: session!.error);
            expect(await api!.call('/api/offline/context'), {
              'schema_version': 2,
              'mode': 'bound_v2',
              'binding': {
                'schema_version': 1,
                'instance_id': hello['instance_id'],
                'account_id': hello['user']['id'],
              },
            });
            final id = hello[kind == 'service' ? 'service_id' : 'resource_id'];
            final readPath = kind == 'service'
                ? '/service/cases/$id'
                : '/resource-custody/$id';
            final item = businessMap(await session!.read(readPath));
            final historyBefore = businessMap(
              await session!.read('$readPath/history'),
            );
            final key = kind == 'service'
                ? 'service-review-$id'
                : 'resource-custody-profile-$id';
            final path =
                '$readPath/${kind == 'service' ? 'transition' : 'profile'}';
            final body = <String, dynamic>{
              if (kind == 'service') ...{
                ...serviceBound(item),
                'status': 'triaged',
                'reason': 'Explicit local HTTP review',
                'resolution': '',
              } else ...{
                ...custodyBound(item),
                for (final field in [
                  'revision',
                  'serial_number',
                  'manufacturer',
                  'model',
                  'location',
                  'notes',
                ])
                  field: item['profile'][field],
                'condition': item['state']['condition'],
                'location': 'Explicitly changed synthetic shelf',
                'confirmation': true,
                'reason': 'Explicit local HTTP review',
              },
            };
            await expectLater(
              session!.command(
                key,
                path,
                body,
                validateResult: (value) => kind == 'service'
                    ? serviceReceipt(path, body, value)
                    : custodyReceipt(path, body, value),
              ),
              throwsA(
                isA<ApiException>().having(
                  (e) => e.status,
                  'lost accepted response',
                  0,
                ),
              ),
            );
            expect(api!.accepted, hasLength(1));
            expect(session!.pending(key), true);
            final originalCommand = jsonEncode(api!.posts.single);
            final originalReceipt = jsonEncode(api!.accepted.single);
            var active = true;
            api!.holdRead =
                '/api/business${kind == 'service' ? readPath : '/capabilities'}';
            final pending = kind == 'service'
                ? session!.repeatServiceCommand(key, stillCurrent: () => active)
                : session!.repeatResourceCustodyCommand(
                    key,
                    stillCurrent: () => active,
                  );
            final rejected = expectLater(pending, throwsA(isA<ApiException>()));
            await api!.held.future.timeout(const Duration(seconds: 10));
            active = false;
            api!.release.complete();
            await rejected;
            expect(
              api!.posts,
              hasLength(1),
              reason: 'Closing the original view must stop the second POST.',
            );
            expect(session!.pending(key), true);
            final receipt = kind == 'service'
                ? await session!.repeatServiceCommand(
                    key,
                    stillCurrent: () => true,
                  )
                : await session!.repeatResourceCustodyCommand(
                    key,
                    stillCurrent: () => true,
                  );
            expect(jsonEncode(receipt), originalReceipt);
            expect(api!.posts, hasLength(2));
            expect(jsonEncode(api!.posts[1]), originalCommand);
            expect(session!.pending(key), false);
            final history = businessMap(
              await session!.read('$readPath/history'),
            );
            final family = kind == 'service' ? 'versions' : 'profiles';
            expect(history[family].length, historyBefore[family].length + 1);
            expect(
              jsonEncode(history[family].first),
              jsonEncode(historyBefore[family].first),
            );
          }, BackendHttp());
        } finally {
          session?.dispose();
          api?.dispose();
          process?.kill();
          await process?.exitCode.timeout(const Duration(seconds: 10));
          await output?.cancel();
          await errors?.cancel();
          await temporary.delete(recursive: true);
        }
      },
      timeout: const Timeout(Duration(seconds: 60)),
    );
  }
}

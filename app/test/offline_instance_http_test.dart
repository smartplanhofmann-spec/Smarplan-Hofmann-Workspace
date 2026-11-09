@Tags(['posix_backend'])
library;

import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:smartplan_office/api.dart';
import 'package:smartplan_office/offline_plans.dart';
import 'package:smartplan_office/offline_binding.dart';
import 'package:smartplan_office/offline_vault.dart' show offlineId;

import 'backend_integration_test.dart' show BackendHttp;
import 'offline_plans_test.dart' show TestDevice, idle;
import 'business_offline_media_test.dart' show fieldPng;

const instanceFixture = r'''
import io, json, sqlite3, sys
from pathlib import Path
from socketserver import TCPServer
from wsgiref.simple_server import WSGIServer, WSGIRequestHandler
from cryptography.fernet import Fernet
from core import Office
from online.web import create_app
from online.test_instance_isolation import MFA_SCHEMA
from online.test_offline_instance_binding import OfflineInstanceBindingHttpTests, PASSWORD

root=Path(sys.argv[1]).resolve(strict=True)
f=OfflineInstanceBindingHttpTests('runTest');f.root=root
seed=Office(root/'seed.sqlite3');seed.db.executescript(MFA_SCHEMA)
f.account=seed.add_user('owner@example.test',PASSWORD,'owner')
f.actor=dict(id=f.account,role='owner');f.project=seed.add_project(f.actor,'Same name','Same customer')
for name in ('a','b','c'):
    target=sqlite3.connect(root/(name+'.sqlite3'));seed.db.backup(target);target.close()
seed.db.close()
a=f.company('a');b=f.company('b')
c=dict(office=Office(root/'c.sqlite3'),host='same.example.test',key=Fernet.generate_key())
capp=create_app(office=c['office'],key=c['key'],host=c['host'])
c['client']=capp.test_client();c['token']=f.login(c)
companies={'a':a,'b':b,'c':c}
apps={name:create_app(office=v['office'],key=v['key'],host=v['host'],
    instance_id=v.get('instance_id'),**({'storage':v['storage']} if 'storage'in v else {}))
    for name,v in companies.items()}
selected=['a'];seen=[]
def response(start,status,value):
    body=json.dumps(value).encode();start(status,[('Content-Type','application/json'),('Content-Length',str(len(body)))]);return[body]
def router(environ,start_response):
    path=environ['PATH_INFO']
    if path.startswith('/__select/'):
        label=path.rsplit('/',1)[1];selected[0]=label
        return response(start_response,'200 OK',{'selected':label})
    if path=='/__state':
        return response(start_response,'200 OK',{'plans':{name:v['office'].plans(f.actor,f.project) for name,v in companies.items()},'seen':seen,'media':{name:v['office'].db.execute('SELECT COUNT(*) FROM business_media').fetchone()[0] for name,v in companies.items()}})
    label=selected[0];key='c'if label=='missing'else label
    if label=='missing' and path.endswith('/offline/context'):
        return response(start_response,'404 Not Found',{'error':'Old synthetic server'})
    observed=dict(company=key,path=path,method=environ['REQUEST_METHOD'],binding=environ.get('HTTP_X_SMARTPLAN_OFFLINE_BINDING'))
    if path.endswith('/business/offline/recovery/lookup'):
        raw=environ['wsgi.input'].read(int(environ.get('CONTENT_LENGTH') or 0))
        environ['wsgi.input']=io.BytesIO(raw);observed['body']=raw.decode()
    seen.append(observed)
    environ['HTTP_HOST']='same.example.test';environ['HTTP_X_FORWARDED_PROTO']='https'
    return apps[key](environ,start_response)
class Loopback(WSGIServer):
    def server_bind(self):
        TCPServer.server_bind(self);self.server_name,self.server_port=self.server_address;self.setup_environ()
class Quiet(WSGIRequestHandler):
    def log_message(self,*args):pass
server=Loopback(('127.0.0.1',0),Quiet);server.set_app(router)
print(json.dumps(dict(port=server.server_port,account=f.account,project=f.project,
    token_a=a['token'],token_b=b['token'],token_c=c['token'],
    instance_a=a['instance_id'],instance_b=b['instance_id'],password=PASSWORD)),flush=True)
server.serve_forever()
''';

class DelayedPlanTransport extends OfficeApi {
  DelayedPlanTransport(String base) : super(baseUrl: base, apiVersion: 'v1');
  final accepted = Completer<void>(), release = Completer<void>();
  final mediaAccepted = Completer<void>(), mediaRelease = Completer<void>();
  bool delayMedia = true;
  bool delay = true;
  final bodies = <Map<String, dynamic>>[];
  @override
  Future<dynamic> call(String path, [Map<String, dynamic>? body]) async {
    final planWrite =
        body != null && RegExp(r'/plans(?:/[^/]+)?$').hasMatch(path);
    if (planWrite)
      bodies.add(Map<String, dynamic>.from(jsonDecode(jsonEncode(body))));
    final result = await super.call(path, body);
    if (planWrite && delay) {
      delay = false;
      accepted.complete();
      await release.future;
    }
    if (body != null &&
        path.contains('/business/media/') &&
        path.contains('/chunks/') &&
        delayMedia) {
      delayMedia = false;
      mediaAccepted.complete();
      await mediaRelease.future;
    }
    return result;
  }
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  test('actual MFA companies isolate queued plans and late ACKs while online-only servers remain usable', () async {
    final backend = Directory(
      Platform.environment['SMARTPLAN_TEST_BACKEND'] ?? '../backend',
    ).absolute;
    final python =
        Platform.environment['SMARTPLAN_TEST_PYTHON'] ??
        '${backend.path}/.venv/bin/python';
    final temp = await Directory.systemTemp.createTemp('offline-v2-http-');
    Process? process;
    StreamIterator<String>? output;
    StreamSubscription<String>? errors;
    OfficeApi? api;
    DelayedPlanTransport? transport;
    OfflinePlans? repo;
    final diagnostics = StringBuffer();
    try {
      process = await Process.start(python, [
        '-u',
        '-c',
        instanceFixture,
        temp.path,
      ], workingDirectory: backend.path);
      errors = process.stderr.transform(utf8.decoder).listen(diagnostics.write);
      output = StreamIterator(
        process.stdout.transform(utf8.decoder).transform(const LineSplitter()),
      );
      expect(
        await output.moveNext().timeout(const Duration(seconds: 45)),
        isTrue,
        reason: '$diagnostics',
      );
      final setup = Map<String, dynamic>.from(jsonDecode(output.current));
      await HttpOverrides.runWithHttpOverrides(() async {
        final base = 'http://127.0.0.1:${setup['port']}';
        api = OfficeApi(baseUrl: base, apiVersion: 'v1')
          ..token = setup['token_a'];
        transport = DelayedPlanTransport(base);
        final device = TestDevice(Directory('${temp.path}/device'));
        repo = OfflinePlans(api: api!, transport: transport, device: device);
        final user = Map<String, dynamic>.from(await api!.call('/api/me'));
        final projects = List<dynamic>.from(await api!.call('/api/projects'));
        await repo!.login(user, projects);
        await idle(repo!);
        final namespaceA = repo!.storageNamespace;
        final local = await repo!.save(setup['project'], {
          'title': 'Only company A',
          'walls': [
            {
              'id': 'wall',
              'points': [
                [1.0, -0.0],
                [1e-6, 2.0],
              ],
            },
          ],
        });
        await transport!.accepted.future.timeout(const Duration(seconds: 20));
        final original = Map<String, dynamic>.from(transport!.bodies.single);
        await api!.call('/__select/b');
        api!.token = setup['token_b'];
        await repo!.login(user, projects);
        expect(repo!.storageNamespace, isNot(namespaceA));
        expect(repo!.list(setup['project']), isEmpty);
        expect(repo!.pending, 0);
        transport!.release.complete();
        await idle(repo!);
        expect(repo!.list(setup['project']), isEmpty);
        var state = await api!.call('/__state');
        expect(state['plans']['a'], hasLength(1));
        expect(state['plans']['b'], isEmpty);
        expect(
          (await (await device.open(
            namespaceA,
            setup['account'],
          )).read())!['outbox'],
          hasLength(1),
        );
        await repo!.save(setup['project'], {
          'title': 'Only company B',
          'walls': [],
        });
        await idle(repo!);
        final namespaceB = repo!.storageNamespace;
        await api!.call('/__select/a');
        api!.token = setup['token_a'];
        await repo!.login(user, projects);
        await idle(repo!);
        expect(repo!.get(local['local_id'])['title'], 'Only company A');
        expect(repo!.pending, 0);
        expect(
          transport!.bodies.where(
            (b) => b['request_id'] == original['request_id'],
          ),
          [original, original],
        );
        state = await api!.call('/__state');
        expect(state['plans']['a'], hasLength(1));
        expect(state['plans']['b'], hasLength(1));
        expect(state['plans']['a'][0]['title'], 'Only company A');
        expect(state['plans']['b'][0]['title'], 'Only company B');
        expect(
          (await (await device.open(
            namespaceB,
            setup['account'],
          )).read())!['outbox'],
          isEmpty,
        );
        // The first A media chunk has been accepted by the real server, but
        // its acknowledgement arrives only after B has become active.
        await repo!.login(user, projects, fieldMedia: true);
        final photo = await repo!.captureFieldPhoto(
          setup['project'],
          fieldPng,
          filename: 'company-a.png',
          mediaType: 'image/png',
          caption: 'A private photo',
        );
        await transport!.mediaAccepted.future.timeout(
          const Duration(seconds: 20),
        );
        await api!.call('/__select/b');
        api!.token = setup['token_b'];
        await repo!.login(user, projects, fieldMedia: true);
        expect(repo!.fieldPhotos(setup['project']), isEmpty);
        transport!.mediaRelease.complete();
        await idle(repo!);
        expect(repo!.fieldPhotos(setup['project']), isEmpty);
        state = await api!.call('/__state');
        expect(state['media']['a'], 1);
        expect(state['media']['b'], 0);
        await api!.call('/__select/a');
        api!.token = setup['token_a'];
        await repo!.login(user, projects, fieldMedia: true);
        await idle(repo!);
        expect(repo!.pending, 0);
        expect(
          repo!.fieldPhotos(setup['project']).single['caption'],
          'A private photo',
        );
        expect(await repo!.fieldPhotoSource(photo['local_id']), fieldPng);
        state = await api!.call('/__state');
        expect(state['media']['a'], 1);
        expect(state['media']['b'], 0);
        final expected = {
          'a': '${setup['instance_a']}:${setup['account']}',
          'b': '${setup['instance_b']}:${setup['account']}',
        };
        for (final request in state['seen']) {
          if (request['binding'] != null)
            expect(request['binding'], expected[request['company']]);
        }
        // Explicit read-only contract check only: production does not auto-probe
        // unbound old caches. Even a wrong-company lookup contains no old body.
        final retained = <String, dynamic>{
          'request_id': offlineId(),
          'title': 'Private A recovery original',
          'walls': [
            {
              'id': 'original',
              'points': [
                [1.0, -0.0],
                [2.0, 10],
              ],
            },
          ],
        };
        await api!.call('/api/projects/${setup['project']}/plans', retained);
        final probe = offlineRecoveryRequest(
          nonce: offlineId(),
          projectId: setup['project'],
          requestId: retained['request_id'],
          requestHash: offlinePlanRequestHash(
            projectId: setup['project'],
            command: retained,
          ),
        );
        await api!.call('/__select/b');
        api!.token = setup['token_b'];
        await expectLater(
          api!.call('/api/business/offline/recovery/lookup', probe),
          throwsA(isA<ApiException>().having((e) => e.status, 'status', 404)),
        );
        state = await api!.call('/__state');
        final firstProbes = (state['seen'] as List)
            .where(
              (r) => (r['path'] as String).endsWith(
                '/business/offline/recovery/lookup',
              ),
            )
            .toList();
        expect(firstProbes, hasLength(1));
        expect(jsonDecode(firstProbes.single['body']), probe);
        expect(
          firstProbes.single.toString(),
          isNot(contains(retained['title'])),
        );
        for (final forbidden in ['command_json', 'title', 'walls', 'points']) {
          expect(
            (jsonDecode(firstProbes.single['body']) as Map).containsKey(
              forbidden,
            ),
            isFalse,
          );
        }
        expect(
          () => offlinePlanRequestHash(
            projectId: setup['project'],
            command: original,
          ),
          throwsA(isA<ApiException>()),
        );
        await api!.call('/__select/a');
        api!.token = setup['token_a'];
        final proof = await api!.call(
          '/api/business/offline/recovery/lookup',
          probe,
        );
        final matched = offlineRecoveryMatch(
          proof,
          request: probe,
          expectedBinding: OfflineBinding.fromJson({
            'schema_version': 1,
            'instance_id': setup['instance_a'],
            'account_id': setup['account'],
          }),
          originalCommand: retained,
        );
        expect(matched['original']['title'], retained['title']);
        state = await api!.call('/__state');
        expect(
          (state['seen'] as List).where(
            (r) => (r['path'] as String).endsWith(
              '/business/offline/recovery/lookup',
            ),
          ),
          hasLength(2),
        );
        // An explicit online-only server and a missing context route must not
        // activate a V1 store or disturb the normal online identity.
        for (final target in ['c', 'missing']) {
          await api!.call('/__select/$target');
          api!.token = setup['token_c'];
          await expectLater(
            repo!.login(user, projects),
            throwsA(isA<ApiException>()),
          );
          expect(repo!.active, isFalse);
          expect(api!.token, setup['token_c']);
          expect(await api!.call('/api/projects'), hasLength(1));
          await api!.call('/api/projects/${setup['project']}/plans', {
            'request_id': offlineId(),
            'title': 'Online $target',
            'walls': [],
          });
        }
      }, BackendHttp());
    } finally {
      if (transport?.release.isCompleted == false)
        transport!.release.complete();
      if (transport?.mediaRelease.isCompleted == false)
        transport!.mediaRelease.complete();
      await repo?.leave();
      repo?.dispose();
      transport?.dispose();
      api?.dispose();
      process?.kill();
      await process?.exitCode;
      await output?.cancel();
      await errors?.cancel();
      await temp.delete(recursive: true);
    }
  });
}

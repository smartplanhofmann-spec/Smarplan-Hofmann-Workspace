@Tags(['posix_backend'])
library;

import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:smartplan_office/api.dart';
import 'package:smartplan_office/business_material_returns.dart';
import 'package:smartplan_office/business_session.dart';
import 'package:smartplan_office/business_travel_allowances.dart';
import 'package:smartplan_office/business_travel_mileage.dart';
import 'package:smartplan_office/online_command_journal.dart';
import 'package:smartplan_office/offline_vault.dart';

import 'backend_integration_test.dart' show BackendHttp;

const fixture = r'''
import json,sys,tempfile,uuid
from pathlib import Path
from socketserver import TCPServer
from wsgiref.simple_server import WSGIServer,WSGIRequestHandler
root=Path(sys.argv[1]).resolve(strict=True);tempfile.tempdir=str(root);mode=sys.argv[2]
from online.web import create_app
if mode=='material':
    from online.test_material_returns_http import MaterialReturnHttpTests
    from online.storage import Storage
    from online.instance import bind
    f=MaterialReturnHttpTests('runTest');f.setUp();issue=f.initial_issue()
    host='purchasing.example.test';instance=uuid.uuid4().hex
    storage=Storage(f.office,f.key,host,config={'server':{'path':str(root/'bound-storage')}})
    bind(f.office,instance,host,f.key,storage)
    app=create_app(office=f.office,key=f.key,host=host,storage=storage,instance_id=instance)
    hello=dict(token=f.token,project=f.project,issue=issue,location=f.location)
else:
    from online.test_business_travel_mileage_http import MileageHttpTests
    from business_travel_allowances import _ref
    from test_business_planning import rid
    f=MileageHttpTests('runTest');f.setUp();x=f.x;domain=f.f
    host='travel.example.test';app=f.app
    token=f.tech
    original_trip=None
    if mode=='trip':command=x.input;operation='trip.save';kind='trip';path='/trips';target=command['id']
    elif mode=='submit':
        original_trip=x.api.save_trip(domain.technician,x.input)['result'];target=original_trip['id']
        command=dict(request_id=rid(),employee_id=domain.employee['id'],revision=original_trip['revision'],
          source_hash=x.api._basis(domain.employee['id']),confirmed=True)
        operation='trip.submit';kind='trip';path='/trips/'+target+'/submit'
    else:
        trip=x.submitted();token=f.token
        proposal=dict(employee_id=domain.employee['id'],trip_refs=[_ref(trip)],
          period_from='2026-10-26',period_to='2026-10-26',settlement_unit='trip',
          tax_choice='tax_free_only',requested_meal_minor=0,requested_lodging_minor=0,
          correction_of=None,review_note='Independent actual restart and original route review')
        preview=x.api.preview(domain.owner,proposal)
        approval=dict(proposal,id=rid(),request_id=rid(),revision=0,
          source_hash=preview['source_hash'],preview_hash=preview['preview_hash'],confirmed=True)
        if mode=='approval':command=approval;operation='settlement.approve';kind='settlement';path='/settlements'
        else:
            settlement=x.api.approve(domain.owner,approval)['result']
            command=domain.payment(settlement,3000);operation='payment.record';kind='payment';path='/payments'
    if mode not in ('trip','submit'):target=command['id']
    hello=dict(token=token,employee=domain.employee['id'],command=command,target=target,original_trip=original_trip,
      operation=operation,kind=kind,path='/personnel/travel/mileage'+path)
def proxy(environ,start_response):
    environ['HTTP_HOST']=host;environ['HTTP_X_FORWARDED_PROTO']='https'
    return app(environ,start_response)
class LocalServer(WSGIServer):
    def server_bind(self):
        TCPServer.server_bind(self);self.server_name,self.server_port=self.server_address;self.setup_environ()
class Quiet(WSGIRequestHandler):
    def log_message(self,*args):pass
server=LocalServer(('127.0.0.1',0),Quiet);server.set_app(proxy)
print(json.dumps(dict(port=server.server_port,**hello)),flush=True)
try:server.serve_forever()
finally:f.doCleanups()
''';

class ActualApi extends OfficeApi {
  ActualApi(String base) : super(baseUrl: base, apiVersion: 'v1');
  bool lose = false, wrong = false;
  final posts = <Map<String, dynamic>>[];
  String? expectedPath;
  @override
  Future<dynamic> call(String path, [Map<String, dynamic>? body]) async {
    final command = body != null && path == expectedPath;
    if (command) posts.add(businessMap(jsonDecode(jsonEncode(body))));
    final value = await super.call(path, body);
    if (command && lose) {
      lose = false;
      throw const ApiException(0, 'Synthetic actual accepted reply lost');
    }
    if (wrong && path.contains('/requests/'))
      return {...businessMap(value), 'request_hash': 'f' * 64};
    return value;
  }
}

class ActualFixture {
  ActualFixture(this.dir, this.process, this.output, this.errors, this.hello);
  final Directory dir;
  final Process process;
  final StreamIterator<String> output;
  final StreamSubscription<String> errors;
  final Map<String, dynamic> hello;
  static Future<ActualFixture> start(String mode) async {
    final dir = await Directory.systemTemp.createTemp('original-command-http-');
    final python =
        Platform.environment['SMARTPLAN_TEST_PYTHON'] ??
        '../backend/.venv/bin/python';
    final process = await Process.start(python, [
      '-u',
      '-c',
      fixture,
      dir.path,
      mode,
    ], workingDirectory: Directory('../backend').absolute.path);
    final diagnostics = StringBuffer();
    final errors = process.stderr
        .transform(utf8.decoder)
        .listen(diagnostics.write);
    final output = StreamIterator(
      process.stdout.transform(utf8.decoder).transform(const LineSplitter()),
    );
    try {
      if (!await output.moveNext().timeout(const Duration(seconds: 40)))
        throw StateError('$diagnostics');
      return ActualFixture(
        dir,
        process,
        output,
        errors,
        businessMap(jsonDecode(output.current)),
      );
    } catch (_) {
      process.kill();
      await errors.cancel();
      await dir.delete(recursive: true);
      rethrow;
    }
  }

  ActualApi api() =>
      ActualApi('http://127.0.0.1:${hello['port']}')..token = hello['token'];
  OnlineCommandJournal journal() => OnlineCommandJournal(
    device: OfflineDevice(root: () async => Directory('${dir.path}/device')),
  );
  Future<void> close() async {
    process.kill();
    await process.exitCode.timeout(const Duration(seconds: 10));
    await output.cancel();
    await errors.cancel();
    await dir.delete(recursive: true);
  }
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  setUp(() => FlutterSecureStorage.setMockInitialValues({}));
  test('actual MFA TCP return cannot duplicate after complete app session destruction', () async {
    final f = await ActualFixture.start('material');
    try {
      await HttpOverrides.runWithHttpOverrides(() async {
        final api = f.api()
          ..lose = true
          ..expectedPath = '/api/business/inventory/movements';
        BusinessSession session() => BusinessSession(
          api: api,
          projectId: f.hello['project'],
          onlineCommandJournal: f.journal(),
        );
        var owner = session();
        await owner.load();
        expect(owner.error, isNull);
        expect(owner.hasFeature('project_creation_journal'), true);
        var flow = MaterialReturnFlow(owner);
        await expectLater(
          flow.submit(
            businessMap(f.hello['issue']),
            '2',
            f.hello['location']['id'],
            'Actual original return 🛠',
          ),
          throwsA(isA<ApiException>().having((e) => e.status, 'lost', 0)),
        );
        final original = api.posts.single;
        flow.dispose();
        owner.dispose();
        owner = session();
        await owner.load();
        flow = MaterialReturnFlow(owner);
        await expectLater(
          flow.submit(
            businessMap(f.hello['issue']),
            '2',
            f.hello['location']['id'],
            'Do not send another return',
          ),
          throwsA(isA<ApiException>().having((e) => e.status, 'blocked', 409)),
        );
        expect(flow.pending, original);
        expect(api.posts.length, 1);
        await flow.retry();
        expect(api.posts.length, 2);
        expect(api.posts.last, original);
        final movements = businessItems(
          await owner.read(owner.query('/inventory/movements')),
        );
        expect(movements.where((v) => v['kind'] == 'return').length, 1);
        expect(
          materialReturnOptions(movements).single['remaining_quantity'],
          '4.0000',
        );
        expect(flow.pending, isNull);
        flow.dispose();
        owner.dispose();
        api.dispose();
      }, BackendHttp());
    } finally {
      await f.close();
    }
  });
  for (final mode in ['trip', 'submit', 'approval', 'payment']) {
    test(
      'actual MFA TCP $mode recovers original status after full private controller destruction',
      () async {
        final f = await ActualFixture.start(mode);
        try {
          await HttpOverrides.runWithHttpOverrides(() async {
            final api = f.api()
              ..lose = true
              ..expectedPath = '/api/business${f.hello['path']}';
            BusinessSession session() =>
                BusinessSession(api: api, onlineCommandJournal: f.journal());
            var owner = session();
            await owner.load();
            expect(owner.error, isNull);
            expect(owner.hasFeature('project_creation_journal'), true);
            final original = businessMap(f.hello['command']),
                body = businessMap(jsonDecode(jsonEncode(original)))
                  ..remove('request_id');
            TravelCommand command() => TravelCommand(
              owner,
              employeeId: f.hello['employee'],
              mileage: true,
              requestIdFactory: () => original['request_id'],
            );
            var flow = command();
            await expectLater(
              flow.submit(
                f.hello['path'],
                body,
                operation: f.hello['operation'],
                targetKind: f.hello['kind'],
                targetId: f.hello['target'],
                originalTrip: f.hello['original_trip'] == null
                    ? null
                    : businessMap(f.hello['original_trip']),
                right: ['trip', 'submit'].contains(mode)
                    ? 'write'
                    : mode == 'approval'
                    ? 'approve'
                    : 'payments',
              ),
              throwsA(isA<ApiException>().having((e) => e.status, 'lost', 0)),
            );
            flow.clear();
            flow.dispose();
            owner.dispose();
            owner = session();
            await owner.load();
            flow = command();
            await flow.restorePending();
            expect(flow.pending?['request_id'], original['request_id']);
            api.wrong = true;
            await expectLater(flow.retry(), throwsA(isA<ApiException>()));
            expect(flow.pending, isNotNull);
            expect(api.posts.length, 1);
            api.wrong = false;
            final receipt = await flow.retry();
            expect(receipt['request_id'], original['request_id']);
            expect(api.posts.length, 1);
            expect(flow.pending, isNull);
            if (mode == 'payment') {
              final movements = businessItems(
                await owner.read(
                  '$mileageRoot/payments?employee_id=${f.hello['employee']}',
                ),
              );
              expect(movements.length, 1);
              expect(movements.single['details']['amount_minor'], 3000);
            }
            flow.dispose();
            owner.dispose();
            api.dispose();
          }, BackendHttp());
        } finally {
          await f.close();
        }
      },
    );
  }
}

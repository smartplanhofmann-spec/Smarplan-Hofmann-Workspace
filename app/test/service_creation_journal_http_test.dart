@Tags(['posix_backend'])
library;

import 'dart:async';
import 'dart:convert';
import 'dart:io';
import 'dart:ui' as ui;

import 'package:flutter/material.dart';
import 'package:flutter/rendering.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:smartplan_office/api.dart';
import 'package:smartplan_office/business_service.dart';
import 'package:smartplan_office/business_session.dart';
import 'package:smartplan_office/service_creation_journal.dart';
import 'package:smartplan_office/offline_vault.dart';

import 'backend_integration_test.dart' show BackendHttp;
import 'offline_plans_test.dart' show TestDevice;

class ServiceTestDevice extends TestDevice {
  ServiceTestDevice(super.folder);
  @override
  Future<OfflineVault?> openExisting(String server, String user) async {
    final directory = Directory(
      '${folder.path}/${await namespace(server)}.$user',
    );
    if (!await directory.exists() ||
        !await directory.list().any(
          (entry) => entry.uri.pathSegments.last.startsWith('state-'),
        ))
      return null;
    return open(server, user);
  }
}

class FailingServiceDevice extends OfflineDevice {
  FailingServiceDevice(this.original);
  final TestDevice original;
  bool failWrite = false, failClear = false;
  @override
  Future<OfflineVault?> openExisting(String server, String user) async {
    final vault = await original.openExisting(server, user);
    return vault == null ? null : FailingServiceVault(vault, this);
  }

  @override
  Future<OfflineVault> open(
    String server,
    String user, {
    bool create = false,
  }) async => FailingServiceVault(
    await original.open(server, user, create: create),
    this,
  );
}

class FailingServiceVault extends OfflineVault {
  FailingServiceVault(OfflineVault original, this.device)
    : super(original.directory, original.key);
  final FailingServiceDevice device;
  @override
  Future<void> write(Map<String, dynamic> value) async {
    if (device.failWrite || device.failClear && value['pending'] == null) {
      throw const FileSystemException('Synthetic storage write refused');
    }
    await super.write(value);
  }
}

const fixture = r'''
import json, sys, uuid, sqlite3, tempfile
from pathlib import Path
from socketserver import TCPServer
from wsgiref.simple_server import WSGIServer, WSGIRequestHandler
from cryptography.fernet import Fernet
from core import Office
from online.web import create_app
from online.instance import bind
from online.storage import Storage
from business_schema import ensure_schema, set_mode
from test_business_resource_custody import ResourceCustodyTests
root=Path(sys.argv[1]).resolve(strict=True); tempfile.tempdir=str(root)
domain=ResourceCustodyTests('runTest');domain.setUp();first=domain.office
ensure_schema(first,activate=True)
owner=domain.owner['id'];project=domain.project;customer=domain.customer['id']
token=first.login('custody-owner@example.test','Synthetic-resource-owner-password')
manager_token=first.login('custody-manager@example.test','Synthetic-resource-manager-password')
copy=sqlite3.connect(root/'second.sqlite3');first.db.backup(copy);copy.close()
second=Office(root/'second.sqlite3')
host='service-journal.example.test'
apps=[]
for index,office in enumerate((first,second)):
    key=Fernet.generate_key();instance=uuid.uuid4().hex
    storage=Storage(office,key,host,config={'server':{'path':str(root/('storage'+str(index)))}})
    bind(office,instance,host,key,storage)
    apps.append(create_app(office=office,key=key,host=host,storage=storage,instance_id=instance))
control=root/'control.json';control.write_text('{}');last=None
def proxy(environ,start_response):
    global last
    raw=control.read_text();state=json.loads(raw)
    if raw!=last:
        for office in (first,second):
            set_mode(office,'legacy' if state.get('readonly') else 'business')
            with office.db:
                office.db.execute('UPDATE users SET active=? WHERE id=?',(0 if state.get('inactive') else 1,owner))
                office.db.execute('DELETE FROM assignments WHERE project_id=? AND user_id=?',(project,domain.manager['id']))
                if not state.get('deny_manager'):
                    office.db.execute('INSERT INTO assignments(project_id,user_id) VALUES(?,?)',(project,domain.manager['id']))
        last=raw
    environ['HTTP_HOST']=host;environ['HTTP_X_FORWARDED_PROTO']='https'
    return apps[1 if state.get('company')=='B' else 0](environ,start_response)
class LocalServer(WSGIServer):
    def server_bind(self):
        TCPServer.server_bind(self);self.server_name,self.server_port=self.server_address;self.setup_environ()
class Quiet(WSGIRequestHandler):
    def log_message(self,*args):pass
server=LocalServer(('127.0.0.1',0),Quiet);server.set_app(proxy)
print(json.dumps(dict(port=server.server_port,token=token,manager_token=manager_token,
    account=owner,project=project,customer=customer,responsible=domain.manager['id'])),flush=True)
server.serve_forever()
''';

class ActualServiceApi extends OfficeApi {
  ActualServiceApi(String base) : super(baseUrl: base, apiVersion: 'v1');
  bool loseAck = false, alterReceipt = false;
  String? holdPath;
  Completer<void>? entered, release;
  final posts = <Map<String, dynamic>>[];
  final accepted = <Map<String, dynamic>>[];
  @override
  Future<dynamic> call(String path, [Map<String, dynamic>? body]) async {
    final create = path == '/api/business/service/cases' && body != null;
    if (create)
      posts.add(Map<String, dynamic>.from(jsonDecode(jsonEncode(body))));
    final result = await super.call(path, body);
    if (path == holdPath) {
      holdPath = null;
      entered!.complete();
      await release!.future;
    }
    if (create) {
      accepted.add(Map<String, dynamic>.from(jsonDecode(jsonEncode(result))));
      if (loseAck) {
        loseAck = false;
        throw const ApiException(0, 'Synthetic accepted response lost');
      }
      if (alterReceipt)
        return {...businessMap(result), 'description': 'Foreign receipt'};
    }
    return result;
  }
}

class ActualServiceFixture {
  final Directory root;
  final Process process;
  final StreamIterator<String> output;
  final StreamSubscription<String> errors;
  final Map<String, dynamic> hello;
  final TestDevice device;
  final Link? rootAlias;
  ActualServiceFixture(
    this.root,
    this.process,
    this.output,
    this.errors,
    this.hello, {
    this.rootAlias,
  }) : device = ServiceTestDevice(Directory('${root.path}/device'));
  static Future<ActualServiceFixture> start({
    bool throughRootAlias = false,
  }) async {
    final root = await Directory.systemTemp.createTemp('service-journal-http-');
    // macOS exposes its temporary directory through /var. Exercise the same
    // canonicalization with an actual link on every POSIX test runner.
    final alias = throughRootAlias ? Link('${root.path}-alias') : null;
    if (alias != null) await alias.create(root.path);
    final python =
        Platform.environment['SMARTPLAN_TEST_PYTHON'] ??
        '../backend/.venv/bin/python';
    final process = await Process.start(python, [
      '-u',
      '-c',
      fixture,
      alias?.path ?? root.path,
    ], workingDirectory: Directory('../backend').absolute.path);
    final diagnostics = StringBuffer();
    final errors = process.stderr
        .transform(utf8.decoder)
        .listen(diagnostics.write);
    final output = StreamIterator(
      process.stdout.transform(utf8.decoder).transform(const LineSplitter()),
    );
    if (!await output.moveNext().timeout(const Duration(seconds: 30))) {
      await errors.cancel();
      throw StateError('$diagnostics');
    }
    return ActualServiceFixture(
      root,
      process,
      output,
      errors,
      businessMap(jsonDecode(output.current)),
      rootAlias: alias,
    );
  }

  ActualServiceApi api({bool manager = false}) =>
      ActualServiceApi('http://127.0.0.1:${hello['port']}')
        ..token = hello[manager ? 'manager_token' : 'token'];
  BusinessSession session(ActualServiceApi api) => BusinessSession(
    api: api,
    serviceCreationJournal: ServiceCreationJournal(device: device),
  );
  Map<String, dynamic> body([String suffix = '']) => {
    'revision': 0,
    'customer_id': hello['customer'],
    'person_id': null,
    'project_id': hello['project'],
    'asset_id': null,
    'contract_id': null,
    'visit_id': null,
    'inquiry_id': null,
    'defect_id': null,
    'title': 'Original Müller 🛠 $suffix',
    'kind': 'complaint',
    'priority': 'high',
    'responsible_id': hello['responsible'],
    'follow_up_on': '2026-12-20',
    'description': 'Original e\u0301 / é\nSecond line $suffix',
  };
  Future<void> control(Map<String, dynamic> value) =>
      File('${root.path}/control.json').writeAsString(jsonEncode(value));
  Future<void> close() async {
    process.kill();
    await process.exitCode.timeout(const Duration(seconds: 10));
    await output.cancel();
    await errors.cancel();
    if (rootAlias != null) await rootAlias!.delete();
    await root.delete(recursive: true);
  }
}

Future<void> settle(WidgetTester tester, bool Function() done) async {
  for (var n = 0; n < 300 && !done(); n++) {
    await tester.runAsync(
      () => Future<void>.delayed(const Duration(milliseconds: 20)),
    );
    await tester.pump(const Duration(milliseconds: 20));
  }
  expect(done(), isTrue);
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  setUpAll(() async {
    await (FontLoader(
      'Inter',
    )..addFont(rootBundle.load('assets/fonts/Inter.ttf'))).load();
    await (FontLoader(
      'MaterialIcons',
    )..addFont(rootBundle.load('fonts/MaterialIcons-Regular.otf'))).load();
  });
  testWidgets(
    'actual accepted POST survives complete app recreation, explicit replay and 390px UI',
    (tester) async {
      final fixture = (await tester.runAsync(
        () => ActualServiceFixture.start(throughRootAlias: true),
      ))!;
      ActualServiceApi? api;
      BusinessSession? session;
      try {
        await HttpOverrides.runWithHttpOverrides(() async {
          api = fixture.api()..loseAck = true;
          session = fixture.session(api!);
          await tester.runAsync(() => session!.load());
          expect(session!.error, isNull);
          expect(session!.hasFeature('service_cases'), isTrue);
          const captureKey = ValueKey('service-create-recovery-390');
          await tester.pumpWidget(
            RepaintBoundary(
              key: captureKey,
              child: MaterialApp(
                theme: ThemeData(fontFamily: 'Inter'),
                home: BusinessServicePage(session: session!),
              ),
            ),
          );
          await settle(
            tester,
            () =>
                !session!.loading &&
                find.byType(LinearProgressIndicator).evaluate().isEmpty &&
                find.text('Servicefall anlegen').evaluate().isNotEmpty,
          );
          final values = fixture.body();
          await tester.runAsync(
            () => expectLater(
              session!.command('service-case-new', '/service/cases', values),
              throwsA(
                isA<ApiException>().having((e) => e.status, 'lost ACK', 0),
              ),
            ),
          );
          final original = api!.accepted.single;
          final command = api!.posts.single;
          await tester.pumpWidget(const SizedBox.shrink());
          session!.dispose();
          api!.dispose();
          api = fixture.api();
          session = fixture.session(api!);
          await tester.runAsync(() => session!.load());
          await tester.binding.setSurfaceSize(const Size(390, 844));
          await tester.pumpWidget(
            RepaintBoundary(
              key: captureKey,
              child: MaterialApp(
                theme: ThemeData(fontFamily: 'Inter'),
                home: BusinessServicePage(session: session!),
              ),
            ),
          );
          await settle(
            tester,
            () =>
                find.byType(LinearProgressIndicator).evaluate().isEmpty &&
                find.text('Servicefall anlegen').evaluate().isNotEmpty,
          );
          expect(
            api!.posts,
            isEmpty,
            reason: 'Session reopening must not send automatically',
          );
          await tester.ensureVisible(find.text('Servicefall anlegen'));
          await tester.tap(find.text('Servicefall anlegen'));
          await settle(
            tester,
            () => find.text('Erneut senden').evaluate().isNotEmpty,
          );
          expect(find.byType(AlertDialog), findsOneWidget);
          final texts = tester.widgetList<TextFormField>(
            find.byType(TextFormField),
          );
          expect(
            texts.map((f) => f.controller?.text),
            contains(values['title']),
          );
          expect(
            texts.map((f) => f.controller?.text),
            contains(values['description']),
          );
          expect(api!.posts, isEmpty);
          if (Platform.environment['SMARTPLAN_CAPTURE_UI'] == '1') {
            await tester.ensureVisible(
              find.byKey(const ValueKey('business-field-title')),
            );
            await tester.pump(const Duration(milliseconds: 400));
            await tester.runAsync(() async {
              final directory = Directory(
                Platform.environment['SMARTPLAN_UI_OUTPUT'] ??
                    Directory.systemTemp.path,
              );
              await directory.create(recursive: true);
              final image = await tester
                  .renderObject<RenderRepaintBoundary>(find.byKey(captureKey))
                  .toImage(pixelRatio: 1);
              try {
                final png = await image.toByteData(
                  format: ui.ImageByteFormat.png,
                );
                await File('${directory.path}/service-create-recovery-390.png')
                    .writeAsBytes(png!.buffer.asUint8List(), flush: true);
              } finally {
                image.dispose();
              }
            });
          }
          await tester.tap(find.text('Erneut senden'));
          await settle(
            tester,
            () =>
                api!.accepted.isNotEmpty &&
                find.byType(AlertDialog).evaluate().isEmpty &&
                find.byType(LinearProgressIndicator).evaluate().isEmpty &&
                find.text('Vollständiger Fallverlauf').evaluate().isNotEmpty,
          );
          expect(api!.posts.single, command);
          expect(api!.accepted.single, original);
          final cases = await tester.runAsync(
            () => session!.read('/service/cases'),
          );
          expect(
            businessItems(businessMap(cases)['items']).where(
              (r) =>
                  r['title'] ==
                  serviceCreationServerText(values['title'] as String),
            ),
            hasLength(1),
          );
          final history = businessMap(
            await tester.runAsync(
              () => session!.read('/service/cases/${original['id']}/history'),
            ),
          );
          expect(history['versions'], hasLength(1));
          expect(history['events'], hasLength(1));
          expect(session!.pending('service-case-new'), isFalse);
          expect(tester.takeException(), isNull);
        }, BackendHttp());
      } finally {
        await tester.pumpWidget(const SizedBox.shrink());
        session?.dispose();
        api?.dispose();
        await tester.binding.setSurfaceSize(null);
        await tester.runAsync(fixture.close);
      }
    },
  );

  test('actual company switch, readonly, denied project, late logout and false receipt retain exact original', () async {
    final fixture = await ActualServiceFixture.start();
    final sessions = <BusinessSession>[];
    final apis = <ActualServiceApi>[];
    BusinessSession open({bool manager = false, bool loseAck = false}) {
      final api = fixture.api(manager: manager)..loseAck = loseAck;
      apis.add(api);
      final session = fixture.session(api);
      sessions.add(session);
      return session;
    }

    try {
      await HttpOverrides.runWithHttpOverrides(() async {
        final session = open(loseAck: true), values = fixture.body('protected');
        await session.load();
        expect(session.error, isNull);
        expect(session.hasFeature('service_cases'), isTrue);
        await expectLater(
          session.command('service-case-new', '/service/cases', values),
          throwsA(isA<ApiException>()),
        );
        final original = apis.last.posts.single;
        await fixture.control({'company': 'B'});
        await session.load();
        expect(session.pending('service-case-new'), isFalse);
        expect(
          session.pendingCommandValues(
            'service-case-new',
            path: '/service/cases',
          ),
          isNull,
        );
        session.dispose();
        sessions.remove(session);
        final foreign = open();
        await foreign.load();
        await expectLater(
          foreign.restoreServiceCreation(),
          throwsA(isA<ApiException>()),
        );
        expect(foreign.pending('service-case-new'), isFalse);
        expect(apis.last.posts, isEmpty);
        await fixture.control({'readonly': true});
        final readonly = open();
        await readonly.load();
        await expectLater(
          readonly.command('service-case-new', '/service/cases', values),
          throwsA(isA<ApiException>()),
        );
        expect(apis.last.posts, isEmpty);
        await fixture.control({});
        final late = open();
        await late.load();
        final delayed = apis.last;
        delayed.holdPath = '/api/me';
        delayed.entered = Completer();
        delayed.release = Completer();
        final pending = late.restoreServiceCreation();
        final observed = expectLater(pending, throwsA(isA<ApiException>()));
        await delayed.entered!.future;
        late.dispose();
        sessions.remove(late);
        delayed.release!.complete();
        await observed;
        expect(delayed.posts, isEmpty);
        final wrong = open();
        await wrong.load();
        apis.last.alterReceipt = true;
        await expectLater(
          wrong.command('service-case-new', '/service/cases', values),
          throwsA(isA<ApiException>()),
        );
        expect(apis.last.posts.single, original);
        expect(wrong.pending('service-case-new'), isTrue);
        final localFailure = open();
        await localFailure.load();
        await expectLater(
          localFailure.command(
            'service-case-new',
            '/service/cases',
            values,
            validateResult: (_) => throw const ApiException(
              409,
              'Synthetic local validation failure',
              requestResolution: 'not_accepted',
            ),
          ),
          throwsA(isA<ApiException>()),
        );
        expect(apis.last.posts.single, original);
        expect(localFailure.pending('service-case-new'), isTrue);
        final correct = open();
        await correct.load();
        final accepted = businessMap(
          await correct.command('service-case-new', '/service/cases', values),
        );
        expect(apis.last.posts.single, original);
        expect(accepted['id'], apis.first.accepted.single['id']);
        final manager = open(manager: true, loseAck: true);
        await manager.load();
        final managerValues = fixture.body('manager');
        await expectLater(
          manager.command('service-case-new', '/service/cases', managerValues),
          throwsA(isA<ApiException>()),
        );
        final managerOriginal = apis.last.posts.single;
        await fixture.control({'deny_manager': true});
        final denied = open(manager: true);
        await denied.load();
        await expectLater(
          denied.restoreServiceCreation(),
          throwsA(isA<ApiException>()),
        );
        expect(apis.last.posts, isEmpty);
        expect(denied.pending('service-case-new'), isFalse);
        await fixture.control({});
        final restored = open(manager: true);
        await restored.load();
        await restored.command(
          'service-case-new',
          '/service/cases',
          managerValues,
        );
        expect(apis.last.posts.single, managerOriginal);
      }, BackendHttp());
    } finally {
      for (final session in sessions) {
        session.dispose();
      }
      for (final api in apis) {
        api.dispose();
      }
      await fixture.close();
    }
  });

  test('actual HTTP freezes caller input before awaiting and storage failures never release a duplicate', () async {
    final fixture = await ActualServiceFixture.start();
    final sessions = <BusinessSession>[], apis = <ActualServiceApi>[];
    BusinessSession open([OfflineDevice? device]) {
      final api = fixture.api();
      apis.add(api);
      final session = BusinessSession(
        api: api,
        serviceCreationJournal: ServiceCreationJournal(
          device: device ?? fixture.device,
        ),
      );
      sessions.add(session);
      return session;
    }

    try {
      await HttpOverrides.runWithHttpOverrides(() async {
        final frozen = open(), values = fixture.body('before await');
        values['title'] = '\u0085${values['title']}\u0085';
        final originalValues = {...values};
        await frozen.load();
        final api = apis.last;
        api.holdPath = '/api/me';
        api.entered = Completer();
        api.release = Completer();
        final sending = frozen.command(
          'service-case-new',
          '/service/cases',
          values,
          validateResult: (v) =>
              serviceReceipt('/service/cases', originalValues, v),
        );
        await api.entered!.future;
        final originalTitle = values['title'];
        values['title'] = 'Mutated caller after await';
        api.release!.complete();
        final result = businessMap(await sending);
        expect(api.posts.single['title'], originalTitle);
        expect(
          result['title'],
          serviceCreationServerText(originalTitle as String),
        );
        final failing = FailingServiceDevice(fixture.device)..failWrite = true;
        final noWrite = open(failing);
        await noWrite.load();
        await expectLater(
          noWrite.command(
            'service-case-new',
            '/service/cases',
            fixture.body('disk full'),
          ),
          throwsA(isA<ApiException>()),
        );
        expect(apis.last.posts, isEmpty);
        failing.failWrite = false;
        failing.failClear = true;
        final noClear = open(failing);
        await noClear.load();
        final completion = fixture.body('failed completion');
        await expectLater(
          noClear.command('service-case-new', '/service/cases', completion),
          throwsA(isA<ApiException>()),
        );
        final original = apis.last.posts.single,
            accepted = apis.last.accepted.single;
        expect(noClear.pending('service-case-new'), isTrue);
        final reopened = open();
        await reopened.load();
        final repeated = businessMap(
          await reopened.command(
            'service-case-new',
            '/service/cases',
            completion,
          ),
        );
        expect(apis.last.posts.single, original);
        expect(repeated, accepted);
        expect(reopened.pending('service-case-new'), isFalse);
      }, BackendHttp());
    } finally {
      for (final session in sessions) {
        session.dispose();
      }
      for (final api in apis) {
        api.dispose();
      }
      await fixture.close();
    }
  });
}

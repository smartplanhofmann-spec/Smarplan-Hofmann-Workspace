@Tags(['posix_backend'])
library;

import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:smartplan_office/api.dart';
import 'package:smartplan_office/business_company_event_contract.dart';
import 'package:smartplan_office/business_session.dart';
import 'package:smartplan_office/offline_vault.dart' show offlineId;

import 'backend_integration_test.dart' show BackendHttp;
import 'import_backend_integration_test.dart' show fixture;

class EventHttpApi extends OfficeApi {
  EventHttpApi(String base) : super(baseUrl: base, apiVersion: 'v1');
  final commands = <Map<String, dynamic>>[], lost = <String>{};
  @override
  Future<dynamic> call(String path, [Map<String, dynamic>? body]) async {
    if (body != null && path.startsWith('/api/business/company-events/'))
      commands.add({'path': path, 'body': jsonDecode(jsonEncode(body))});
    final result = await super.call(path, body);
    if (body != null &&
        (path.endsWith('/rules') ||
            path.endsWith('/scan') ||
            path.endsWith('/execute')) &&
        lost.add(path)) {
      throw const ApiException(0, 'Synthetic successful HTTP response lost');
    }
    return result;
  }
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  test('actual HTTP creates a bound rule, replays all lost ACKs, approves one plan and creates exactly one task', () async {
    final backend = Directory('../backend').absolute;
    final python =
        Platform.environment['SMARTPLAN_TEST_PYTHON'] ??
        '${backend.path}/.venv/${Platform.isWindows ? 'Scripts/python.exe' : 'bin/python'}';
    final temporary = await Directory.systemTemp.createTemp(
      'smartplan-native-company-events-',
    );
    Process? process;
    StreamIterator<String>? output;
    StreamSubscription<String>? stderr;
    EventHttpApi? api;
    BusinessSession? session;
    final diagnostics = StringBuffer();
    try {
      final seed = fixture
          .replaceFirst('app = create_app(', r'''
from business_schema import ensure_schema
from datetime import datetime, timedelta, timezone
from project_workspace import ProjectWorkspace
from business_operations import transaction
import uuid
ensure_schema(office, activate=True)
from online.instance import bind
from online.storage import Storage
instance_key=Fernet.generate_key()
instance_id=uuid.uuid4().hex
instance_storage=Storage(office,instance_key,'office.example.test',config={'server':{'path':str(Path(sys.argv[1])/'private-storage')}})
bind(office,instance_id,'office.example.test',instance_key,instance_storage)
with transaction(office):
    ProjectWorkspace(office).save_item(user,project,'tasks',dict(request_id=uuid.uuid4().hex,
        title='Synthetic native HTTP overdue task',details='Exact original source',status='todo',priority='normal',
        due_date=(datetime.now(timezone.utc)-timedelta(days=3)).date().isoformat(),assignee_id=user['id']))
app = create_app(''')
          .replaceFirst(
            "key=Fernet.generate_key(), host='office.example.test', storage_config={}",
            "key=instance_key, host='office.example.test', storage=instance_storage, instance_id=instance_id",
          );
      process = await Process.start(python, [
        '-u',
        '-c',
        seed,
        temporary.path,
      ], workingDirectory: backend.path);
      stderr = process.stderr.transform(utf8.decoder).listen(diagnostics.write);
      output = StreamIterator(
        process.stdout.transform(utf8.decoder).transform(const LineSplitter()),
      );
      expect(
        await output.moveNext().timeout(const Duration(seconds: 30)),
        true,
        reason: diagnostics.toString(),
      );
      final hello = businessMap(jsonDecode(output.current));
      await HttpOverrides.runWithHttpOverrides(() async {
        api = EventHttpApi('http://127.0.0.1:${hello['port']}')
          ..token = hello['token'];
        session = BusinessSession(
          api: api!,
          projects: businessItems(hello['projects']),
        );
        await session!.load();
        expect(
          session!.hasFeature('company_event_rules'),
          true,
          reason: session!.error,
        );
        companyEventStatus(await session!.read('/company-events/status'));
        final body = <String, dynamic>{
          'id': offlineId(),
          'revision': 0,
          'title': 'Explicit native HTTP rule',
          'enabled': true,
          'project_ids': [hello['project_id']],
          'trigger': 'task.overdue',
          'action': 'task.create',
          'mode': 'approval',
          'conditions': [],
          'template': {
            'title': 'One actual native follow-up',
            'details': 'Fixed reviewed native template',
            'priority': 'normal',
            'due_days': null,
          },
          'responsible_id': hello['user']['id'],
          'confirmation': true,
        };
        await expectLater(
          session!.companyEventCommand('/company-events/rules', body),
          throwsA(isA<ApiException>()),
        );
        final rule = companyEventRule(
          await session!.repeatCompanyEventCommand(
            companyEventCommandKey('/company-events/rules', body),
          ),
        );
        expect(rule['revision'], 1);
        expect(api!.commands[0]['body'], api!.commands[1]['body']);
        final scanBody = <String, dynamic>{'limit': 100, 'after': null};
        await expectLater(
          session!.companyEventCommand('/company-events/scan', scanBody),
          throwsA(isA<ApiException>()),
        );
        final run = companyEventRun(
          await session!.repeatCompanyEventCommand('company-event-scan'),
        );
        expect(api!.commands[2]['body'], api!.commands[3]['body']);
        expect(run['items'].length, 1);
        final id = run['items'][0]['plan_ids'][0];
        final plan = companyEventPlan(
          await session!.read('/company-events/plans/$id'),
        );
        final event = companyEventObservation(
          await session!.read('/company-events/events/${plan['event_id']}'),
        );
        companyEventPlan(plan, event: event);
        await session!.authorizeCompanyEventData(plan);
        expect(plan['status'], 'awaiting_approval');
        final approved = companyEventPlan(
          await session!.companyEventCommand(
            '/company-events/plans/$id/approve',
            {
              'plan_sha256': plan['sha256'],
              'reason': 'Actual native HTTP source and policy checked',
              'confirmation': true,
            },
          ),
        );
        expect(approved['can_execute'], true);
        final executeBody = <String, dynamic>{
          'plan_sha256': plan['sha256'],
          'confirmation': true,
        };
        await expectLater(
          session!.companyEventCommand(
            '/company-events/plans/$id/execute',
            executeBody,
          ),
          throwsA(isA<ApiException>()),
        );
        final done = companyEventPlan(
          await session!.repeatCompanyEventCommand('company-event-execute-$id'),
        );
        expect(done['status'], 'succeeded');
        expect(done['can_execute'], false);
        expect(api!.commands[5]['body'], api!.commands[6]['body']);
        final task = businessMap(
          await session!.legacyRead(
            '/api/projects/${hello['project_id']}/tasks/${done['outcome']['result']['id']}',
          ),
        );
        expect(task['title'], 'One actual native follow-up');
        expect(
          businessItems(
            await session!.legacyRead(
              '/api/projects/${hello['project_id']}/tasks',
            ),
          ).length,
          2,
        );
        for (final kind in ['events', 'plans', 'runs'])
          companyEventPage(
            await session!.read('/company-events/$kind?limit=1'),
            kind,
          );
        final changed = {...body, 'revision': 1, 'enabled': false};
        companyEventRule(
          await session!.companyEventCommand('/company-events/rules', changed),
        );
        final history = companyEventRuleHistory(
          await session!.read('/company-events/rules/${body['id']}/history'),
          body['id'],
        );
        expect(history['items'].length, 2);
        expect(history['items'][0]['enabled'], true);
        expect(history['items'][1]['enabled'], false);
        expect(session!.pendingCompanyEventCommands, isEmpty);
      }, BackendHttp());
    } finally {
      session?.dispose();
      api?.dispose();
      process?.kill();
      if (process != null) await process.exitCode;
      await output?.cancel();
      await stderr?.cancel();
      await temporary.delete(recursive: true);
    }
  }, timeout: const Timeout(Duration(minutes: 2)));
}

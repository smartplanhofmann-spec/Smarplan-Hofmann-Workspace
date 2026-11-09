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

import 'business_material_returns_test.dart' as material;
import 'business_travel_mileage_test.dart' as mileage;
import 'online_command_journal_test.dart' show ControlledDevice;

class BoundMaterialApi extends material.ReturnApi {
  String instance = 'a' * 32;
  bool projectRead = true;
  @override
  Future<dynamic> call(String path, [Map<String, dynamic>? body]) async {
    if (body == null &&
        Uri.parse(path).path ==
            '/api/business/inventory/movements/${material.mainCase['issue']['id']}') {
      if (!projectRead)
        throw const ApiException(404, 'Synthetic project access withdrawn');
      return material.copy(material.mainCase['issue']);
    }
    final value = await super.call(path, body);
    if (Uri.parse(path).path == '/api/business/capabilities')
      return {
        ...businessMap(value),
        'features': [...value['features'], 'project_creation_journal'],
        'project_creation_scope': {
          'schema_version': 1,
          'instance_id': instance,
          'account_id': actor,
        },
      };
    return value;
  }
}

class BoundMileageApi extends mileage.MileageApi {
  String instance = 'b' * 32;
  bool journalCapability = true;
  @override
  Future<dynamic> call(String path, [Map<String, dynamic>? body]) async {
    final value = await super.call(path, body);
    if (Uri.parse(path).path == '/api/business/capabilities')
      return {
        ...businessMap(value),
        'features': [
          ...value['features'],
          if (journalCapability) 'project_creation_journal',
        ],
        if (journalCapability)
          'project_creation_scope': {
            'schema_version': 1,
            'instance_id': instance,
            'account_id': actor,
          },
      };
    return value;
  }
}

class ConflictMaterialApi extends BoundMaterialApi {
  ConflictMaterialApi(this.explicit);
  final bool explicit;
  @override
  Future<dynamic> call(String path, [Map<String, dynamic>? body]) async {
    if (body != null &&
        Uri.parse(path).path == '/api/business/inventory/movements') {
      sent.add(material.copy(body));
      throw ApiException(
        409,
        'Synthetic original return conflict',
        requestResolution: explicit ? 'not_accepted' : null,
      );
    }
    return super.call(path, body);
  }
}

class ConflictMileageApi extends BoundMileageApi {
  ConflictMileageApi(this.explicit);
  final bool explicit;
  @override
  Future<dynamic> call(String path, [Map<String, dynamic>? body]) async {
    if (body != null && path == '/api/business$mileageRoot/trips') {
      posts.add({'path': path, 'body': mileage.copy(body)});
      throw ApiException(
        409,
        'Synthetic original trip conflict',
        requestResolution: explicit ? 'not_accepted' : null,
      );
    }
    return super.call(path, body);
  }
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  late Directory dir;
  OnlineCommandJournal journal() =>
      OnlineCommandJournal(device: OfflineDevice(root: () async => dir));
  setUp(() async {
    FlutterSecureStorage.setMockInitialValues({});
    dir = await Directory.systemTemp.createTemp('command-restart-');
  });
  tearDown(() async {
    await dir.delete(recursive: true);
  });
  test('global warehouse grant cannot reveal retained project note after project revocation', () async {
    final api = BoundMaterialApi()..lose = true;
    BusinessSession session() =>
        BusinessSession(api: api, onlineCommandJournal: journal());
    var owner = session();
    await owner.load();
    var flow = MaterialReturnFlow(owner);
    await expectLater(
      flow.submit(
        material.copy(material.mainCase['issue']),
        '2',
        material.mainCase['location']['id'],
        'Synthetic first actual return',
      ),
      throwsA(isA<ApiException>()),
    );
    flow.dispose();
    owner.dispose();
    api.projectRead = false;
    owner = session();
    await owner.load();
    flow = MaterialReturnFlow(owner);
    expect(owner.can('inventory.read'), true);
    await expectLater(
      flow.restorePending(),
      throwsA(
        isA<ApiException>().having((e) => e.status, 'denied project', 404),
      ),
    );
    expect(flow.pending, isNull);
    expect(api.sent.length, 1);
    api.projectRead = true;
    await flow.restorePending();
    expect(flow.pending, isNotNull);
    await flow.retry();
    expect(api.accepted.length, 1);
    flow.dispose();
    owner.dispose();
    api.dispose();
  });
  test(
    'older server metadata cannot bypass retained private mileage command',
    () async {
      final data = mileage.fixture['initial'],
          api = BoundMileageApi()
            ..kind = 'trip'
            ..operation = 'trip.save'
            ..receiptKey = 'draft_receipt'
            ..actor = data['draft_receipt']['actor_id']
            ..lose = true;
      BusinessSession session() =>
          BusinessSession(api: api, onlineCommandJournal: journal());
      var owner = session();
      await owner.load();
      TravelCommand command() => TravelCommand(
        owner,
        employeeId: mileage.employee,
        mileage: true,
        requestIdFactory: () => data['trip_command']['request_id'],
      );
      var flow = command();
      final body = mileage.copy(data['trip_command'])..remove('request_id');
      await expectLater(
        flow.submit(
          '$mileageRoot/trips',
          body,
          operation: 'trip.save',
          targetKind: 'trip',
          targetId: body['id'],
        ),
        throwsA(isA<ApiException>()),
      );
      flow.dispose();
      owner.dispose();
      api.journalCapability = false;
      owner = session();
      await owner.load();
      flow = command();
      expect(owner.hasFeature('project_creation_journal'), false);
      await expectLater(flow.restorePending(), throwsA(isA<ApiException>()));
      expect(flow.pending, isNull);
      await expectLater(
        flow.submit(
          '$mileageRoot/trips',
          body,
          operation: 'trip.save',
          targetKind: 'trip',
          targetId: body['id'],
        ),
        throwsA(isA<ApiException>()),
      );
      expect(api.posts.length, 1);
      api.journalCapability = true;
      await owner.load();
      await flow.restorePending();
      await flow.retry();
      expect(api.posts.length, 1);
      flow.dispose();
      owner.dispose();
      api.dispose();
    },
  );
  for (final explicit in [false, true]) {
    test(
      'material conflict resolves only with explicit no-effect proof: $explicit',
      () async {
        final api = ConflictMaterialApi(explicit);
        BusinessSession session() => BusinessSession(
          api: api,
          projectId: material.mainCase['project_id'],
          onlineCommandJournal: journal(),
        );
        var owner = session();
        await owner.load();
        var flow = MaterialReturnFlow(owner);
        await expectLater(
          flow.submit(
            material.copy(material.mainCase['issue']),
            '2',
            material.mainCase['location']['id'],
            'Synthetic first actual return',
          ),
          throwsA(isA<ApiException>()),
        );
        expect(flow.pending == null, explicit);
        expect(api.accepted, isEmpty);
        flow.dispose();
        owner.dispose();
        owner = session();
        await owner.load();
        flow = MaterialReturnFlow(owner);
        await flow.restorePending();
        expect(flow.pending == null, explicit);
        expect(api.sent.length, 1);
        flow.dispose();
        owner.dispose();
        api.dispose();
      },
    );
    test(
      'mileage conflict resolves only with explicit no-effect proof: $explicit',
      () async {
        final b = mileage.fixture['initial'],
            api = ConflictMileageApi(explicit)
              ..actor = b['draft_receipt']['actor_id'];
        BusinessSession session() =>
            BusinessSession(api: api, onlineCommandJournal: journal());
        var owner = session();
        await owner.load();
        TravelCommand command() => TravelCommand(
          owner,
          employeeId: mileage.employee,
          mileage: true,
          requestIdFactory: () => b['trip_command']['request_id'],
        );
        var flow = command();
        final body = mileage.copy(b['trip_command'])..remove('request_id');
        await expectLater(
          flow.submit(
            '$mileageRoot/trips',
            body,
            operation: 'trip.save',
            targetKind: 'trip',
            targetId: body['id'],
          ),
          throwsA(isA<ApiException>()),
        );
        expect(flow.pending == null, explicit);
        expect(api.receipts, isEmpty);
        flow.dispose();
        owner.dispose();
        owner = session();
        await owner.load();
        flow = command();
        await flow.restorePending();
        expect(flow.pending == null, explicit);
        expect(api.posts.length, 1);
        flow.dispose();
        owner.dispose();
        api.dispose();
      },
    );
  }
  test('material accepted loss cannot be replaced by a fresh nonce after full controller/session recreation', () async {
    final api = BoundMaterialApi()..lose = true;
    BusinessSession session() => BusinessSession(
      api: api,
      projectId: material.mainCase['project_id'],
      onlineCommandJournal: journal(),
    );
    var owner = session();
    await owner.load();
    var flow = MaterialReturnFlow(owner);
    await expectLater(
      flow.submit(
        material.copy(material.mainCase['issue']),
        '2',
        material.mainCase['location']['id'],
        'Synthetic first actual return',
      ),
      throwsA(isA<ApiException>()),
    );
    final sent = material.copy(api.sent.single);
    flow.dispose();
    owner.dispose();
    owner = session();
    await owner.load();
    flow = MaterialReturnFlow(owner);
    addTearDown(() {
      flow.dispose();
      owner.dispose();
      api.dispose();
    });
    await expectLater(
      flow.submit(
        material.copy(material.mainCase['issue']),
        '2',
        material.mainCase['location']['id'],
        'Replacement must not be sent',
      ),
      throwsA(isA<ApiException>().having((e) => e.status, 'blocked', 409)),
    );
    expect(flow.pending, sent);
    expect(api.sent.length, 1);
    expect(api.accepted.length, 1);
    await flow.retry();
    expect(api.sent.length, 2);
    expect(api.sent.last, sent);
    expect(api.accepted.length, 1);
    expect(flow.pending, isNull);
    await flow.restorePending();
    expect(flow.pending, isNull);
  });
  test(
    'material view notices an original already resolved in another window',
    () async {
      final api = BoundMaterialApi()..lose = true;
      BusinessSession session() => BusinessSession(
        api: api,
        projectId: material.mainCase['project_id'],
        onlineCommandJournal: journal(),
      );
      final first = session(), second = session();
      await first.load();
      await second.load();
      final a = MaterialReturnFlow(first), b = MaterialReturnFlow(second);
      await expectLater(
        a.submit(
          material.copy(material.mainCase['issue']),
          '2',
          material.mainCase['location']['id'],
          'Synthetic first actual return',
        ),
        throwsA(isA<ApiException>()),
      );
      await b.restorePending();
      await b.retry();
      expect(a.pending, isNotNull);
      await a.restorePending();
      expect(a.pending, isNull);
      expect(api.accepted.length, 1);
      a.dispose();
      b.dispose();
      first.dispose();
      second.dispose();
      api.dispose();
    },
  );
  test(
    'mileage view notices an original already resolved in another window',
    () async {
      final data = mileage.fixture['initial'],
          api = BoundMileageApi()
            ..kind = 'trip'
            ..operation = 'trip.save'
            ..receiptKey = 'draft_receipt'
            ..actor = data['draft_receipt']['actor_id']
            ..lose = true;
      BusinessSession session() =>
          BusinessSession(api: api, onlineCommandJournal: journal());
      final first = session(), second = session();
      await first.load();
      await second.load();
      TravelCommand command(BusinessSession owner) => TravelCommand(
        owner,
        employeeId: mileage.employee,
        mileage: true,
        requestIdFactory: () => data['trip_command']['request_id'],
      );
      final a = command(first),
          b = command(second),
          body = mileage.copy(data['trip_command'])..remove('request_id');
      await expectLater(
        a.submit(
          '$mileageRoot/trips',
          body,
          operation: 'trip.save',
          targetKind: 'trip',
          targetId: body['id'],
        ),
        throwsA(isA<ApiException>()),
      );
      await b.restorePending();
      await b.retry();
      expect(a.pending, isNotNull);
      await a.restorePending();
      expect(a.pending, isNull);
      expect(api.posts.length, 1);
      a.dispose();
      b.dispose();
      first.dispose();
      second.dispose();
      api.dispose();
    },
  );
  test('material original is withheld under another company or revoked read rights', () async {
    final api = BoundMaterialApi()..lose = true;
    BusinessSession session() => BusinessSession(
      api: api,
      projectId: material.mainCase['project_id'],
      onlineCommandJournal: journal(),
    );
    var owner = session();
    await owner.load();
    var flow = MaterialReturnFlow(owner);
    await expectLater(
      flow.submit(
        material.copy(material.mainCase['issue']),
        '2',
        material.mainCase['location']['id'],
        'Synthetic first actual return',
      ),
      throwsA(isA<ApiException>()),
    );
    flow.dispose();
    owner.dispose();
    api.instance = 'c' * 32;
    owner = session();
    await owner.load();
    flow = MaterialReturnFlow(owner);
    await expectLater(flow.restorePending(), throwsA(isA<ApiException>()));
    expect(flow.pending, isNull);
    flow.dispose();
    owner.dispose();
    api.instance = 'a' * 32;
    api.read = false;
    owner = session();
    await owner.load();
    flow = MaterialReturnFlow(owner);
    await expectLater(flow.restorePending(), throwsA(isA<ApiException>()));
    expect(flow.pending, isNull);
    api.read = true;
    await owner.load();
    await flow.restorePending();
    expect(flow.pending, api.sent.single);
    await flow.retry();
    expect(api.accepted.length, 1);
    flow.dispose();
    owner.dispose();
    api.dispose();
  });
  test('trip approval and actual cash lost replies survive fresh session and recover by status without another POST', () async {
    final b = mileage.fixture['initial'];
    for (final entry in [
      ('trip', 'trip.save', 'trip_command', 'draft_receipt', 'write'),
      (
        'settlement',
        'settlement.approve',
        'settlement_command',
        'settlement_receipt',
        'approve',
      ),
      (
        'payment',
        'payment.record',
        'payment_command',
        'payment_receipt',
        'payments',
      ),
    ]) {
      final api = BoundMileageApi()
        ..kind = entry.$1
        ..operation = entry.$2
        ..receiptKey = entry.$4
        ..actor = b[entry.$4]['actor_id']
        ..lose = true;
      BusinessSession session() =>
          BusinessSession(api: api, onlineCommandJournal: journal());
      var owner = session();
      await owner.load();
      TravelCommand command() => TravelCommand(
        owner,
        employeeId: mileage.employee,
        mileage: true,
        requestIdFactory: () => b[entry.$3]['request_id'],
      );
      var flow = command();
      final body = mileage.copy(b[entry.$3])..remove('request_id');
      final path =
          '$mileageRoot/${entry.$1 == 'trip'
              ? 'trips'
              : entry.$1 == 'settlement'
              ? 'settlements'
              : 'payments'}';
      await expectLater(
        flow.submit(
          path,
          body,
          operation: entry.$2,
          targetKind: entry.$1,
          targetId: body['id'],
          right: entry.$5,
        ),
        throwsA(isA<ApiException>()),
      );
      flow.clear();
      flow.dispose();
      owner.dispose();
      owner = session();
      await owner.load();
      flow = command();
      await flow.restorePending();
      expect(flow.pending?['request_id'], b[entry.$3]['request_id']);
      expect(flow.pending!.containsKey('body'), false);
      await flow.retry();
      expect(api.posts.length, 1);
      expect(flow.pending, isNull);
      await flow.restorePending();
      expect(flow.pending, isNull);
      flow.dispose();
      owner.dispose();
      api.dispose();
    }
  });
  test('material prepare failure sends nothing and clear failure preserves the accepted original', () async {
    final api = BoundMaterialApi(), device = ControlledDevice(dir);
    BusinessSession session() => BusinessSession(
      api: api,
      projectId: material.mainCase['project_id'],
      onlineCommandJournal: OnlineCommandJournal(device: device),
    );
    var owner = session();
    await owner.load();
    var flow = MaterialReturnFlow(owner);
    device.fail = true;
    await expectLater(
      flow.submit(
        material.copy(material.mainCase['issue']),
        '2',
        material.mainCase['location']['id'],
        'Synthetic first actual return',
      ),
      throwsA(isA<ApiException>()),
    );
    expect(api.sent, isEmpty);
    expect(api.accepted, isEmpty);
    device.fail = false;
    // The server has accepted before local outcome resolution is attempted.
    api.changeGet = (_) => device.fail = true;
    await expectLater(
      flow.submit(
        material.copy(material.mainCase['issue']),
        '2',
        material.mainCase['location']['id'],
        'Synthetic first actual return',
      ),
      throwsA(isA<ApiException>()),
    );
    expect(api.accepted.length, 1);
    final original = material.copy(api.sent.single);
    flow.dispose();
    owner.dispose();
    device.fail = false;
    api.changeGet = null;
    owner = session();
    await owner.load();
    flow = MaterialReturnFlow(owner);
    await flow.restorePending();
    expect(flow.pending, original);
    await flow.retry();
    expect(api.accepted.length, 1);
    expect(api.sent.last, original);
    flow.dispose();
    owner.dispose();
    api.dispose();
  });
  test('live company change with identical token generation and user cannot replay a material original', () async {
    final api = BoundMaterialApi()..lose = true;
    final owner = BusinessSession(
      api: api,
      projectId: material.mainCase['project_id'],
      onlineCommandJournal: journal(),
    );
    await owner.load();
    final flow = MaterialReturnFlow(owner);
    await expectLater(
      flow.submit(
        material.copy(material.mainCase['issue']),
        '2',
        material.mainCase['location']['id'],
        'Synthetic first actual return',
      ),
      throwsA(isA<ApiException>()),
    );
    api.instance = 'c' * 32;
    await owner.load();
    expect(flow.pending, isNull);
    await expectLater(flow.retry(), throwsA(isA<ApiException>()));
    expect(api.sent.length, 1);
    expect(api.accepted.length, 1);
    api.instance = 'a' * 32;
    await owner.load();
    await flow.restorePending();
    await flow.retry();
    expect(api.accepted.length, 1);
    flow.dispose();
    owner.dispose();
    api.dispose();
  });
  test('live company change blocks private status lookup and retains the original for its own firm', () async {
    final b = mileage.fixture['initial'],
        api = BoundMileageApi()
          ..kind = 'trip'
          ..operation = 'trip.save'
          ..receiptKey = 'draft_receipt'
          ..actor = b['draft_receipt']['actor_id']
          ..lose = true;
    final owner = BusinessSession(api: api, onlineCommandJournal: journal());
    await owner.load();
    TravelCommand command() => TravelCommand(
      owner,
      employeeId: mileage.employee,
      mileage: true,
      requestIdFactory: () => b['trip_command']['request_id'],
    );
    var flow = command();
    final body = mileage.copy(b['trip_command'])..remove('request_id');
    await expectLater(
      flow.submit(
        '$mileageRoot/trips',
        body,
        operation: 'trip.save',
        targetKind: 'trip',
        targetId: body['id'],
      ),
      throwsA(isA<ApiException>()),
    );
    api.instance = 'c' * 32;
    await owner.load();
    await expectLater(flow.retry(), throwsA(isA<ApiException>()));
    expect(api.posts.length, 1);
    flow.dispose();
    api.instance = 'b' * 32;
    await owner.load();
    flow = command();
    await flow.restorePending();
    expect(flow.pending, isNotNull);
    await flow.retry();
    expect(api.posts.length, 1);
    flow.dispose();
    owner.dispose();
    api.dispose();
  });
  test('unaccepted mileage original is retried with exact body and original nonce after restart', () async {
    final b = mileage.fixture['initial'],
        api = BoundMileageApi()
          ..kind = 'trip'
          ..operation = 'trip.save'
          ..receiptKey = 'draft_receipt'
          ..actor = b['draft_receipt']['actor_id']
          ..lose = true
          ..accepted = false;
    BusinessSession session() =>
        BusinessSession(api: api, onlineCommandJournal: journal());
    var owner = session();
    await owner.load();
    TravelCommand command() => TravelCommand(
      owner,
      employeeId: mileage.employee,
      mileage: true,
      requestIdFactory: () => b['trip_command']['request_id'],
    );
    var flow = command();
    final body = mileage.copy(b['trip_command'])..remove('request_id');
    await expectLater(
      flow.submit(
        '$mileageRoot/trips',
        body,
        operation: 'trip.save',
        targetKind: 'trip',
        targetId: body['id'],
      ),
      throwsA(isA<ApiException>()),
    );
    final first = mileage.copy(api.posts.single);
    flow.clear();
    flow.dispose();
    owner.dispose();
    api.accepted = true;
    owner = session();
    await owner.load();
    flow = command();
    await flow.restorePending();
    await flow.retry();
    expect(api.posts.length, 2);
    expect(api.posts.last, first);
    expect(api.receipts.length, 1);
    expect(flow.pending, isNull);
    flow.dispose();
    owner.dispose();
    api.dispose();
  });
}

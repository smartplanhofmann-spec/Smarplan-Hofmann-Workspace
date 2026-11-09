import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:smartplan_office/api.dart';
import 'package:smartplan_office/business_material_returns.dart';
import 'package:smartplan_office/business_session.dart';
import 'package:smartplan_office/business_travel_allowances.dart';
import 'package:smartplan_office/business_travel_mileage.dart';
import 'package:smartplan_office/offline_vault.dart';
import 'package:smartplan_office/online_command_journal.dart';

import 'business_material_returns_test.dart' as material;
import 'business_travel_mileage_test.dart' as mileage;
import 'online_command_restart_test.dart'
    show BoundMaterialApi, BoundMileageApi;

Future<void> settle(WidgetTester tester, bool Function() done) async {
  for (var n = 0; n < 400 && !done(); n++) {
    await tester.runAsync(
      () => Future<void>.delayed(const Duration(milliseconds: 10)),
    );
    await tester.pump(const Duration(milliseconds: 10));
  }
  expect(done(), true);
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  late Directory dir;
  OnlineCommandJournal journal() =>
      OnlineCommandJournal(device: OfflineDevice(root: () async => dir));
  setUp(() async {
    FlutterSecureStorage.setMockInitialValues({});
    dir = await Directory.systemTemp.createTemp('restart-ui-');
  });
  tearDown(() async {
    await dir.delete(recursive: true);
  });
  testWidgets(
    '390px return dialog restores only the original after full session replacement',
    (tester) async {
      await tester.binding.setSurfaceSize(const Size(390, 844));
      addTearDown(() => tester.binding.setSurfaceSize(null));
      final api = BoundMaterialApi()..lose = true;
      BusinessSession session() => BusinessSession(
        api: api,
        projectId: material.mainCase['project_id'],
        onlineCommandJournal: journal(),
      );
      var owner = session();
      await tester.runAsync(() => owner.load());
      var flow = MaterialReturnFlow(owner);
      await tester.runAsync(
        () => expectLater(
          flow.submit(
            material.copy(material.mainCase['issue']),
            '2',
            material.mainCase['location']['id'],
            'Synthetic first actual return',
          ),
          throwsA(isA<ApiException>()),
        ),
      );
      flow.dispose();
      owner.dispose();
      owner = session();
      await tester.runAsync(() => owner.load());
      flow = MaterialReturnFlow(owner);
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(body: MaterialReturnDialog(flow: flow)),
        ),
      );
      await settle(
        tester,
        () => find.text('Menge: 2.0000').evaluate().isNotEmpty,
      );
      expect(find.byType(DropdownButtonFormField<String>), findsNothing);
      expect(
        find.byKey(const ValueKey('material-return-quantity')),
        findsNothing,
      );
      expect(find.text('Ursprüngliche Rückgabe erneut prüfen'), findsOneWidget);
      expect(api.sent.length, 1);
      expect(tester.takeException(), isNull);
      await tester.pumpWidget(const SizedBox.shrink());
      flow.dispose();
      owner.dispose();
      api.dispose();
    },
  );
  testWidgets(
    '390px mileage page discovers retained original before allowing a new trip',
    (tester) async {
      await tester.binding.setSurfaceSize(const Size(390, 844));
      addTearDown(() => tester.binding.setSurfaceSize(null));
      final b = mileage.fixture['initial'],
          api = BoundMileageApi()
            ..kind = 'trip'
            ..operation = 'trip.save'
            ..receiptKey = 'draft_receipt'
            ..actor = b['draft_receipt']['actor_id']
            ..lose = true;
      BusinessSession session() =>
          BusinessSession(api: api, onlineCommandJournal: journal());
      var owner = session();
      await tester.runAsync(() => owner.load());
      final old = TravelCommand(
        owner,
        employeeId: mileage.employee,
        mileage: true,
        requestIdFactory: () => b['trip_command']['request_id'],
      );
      final body = mileage.copy(b['trip_command'])..remove('request_id');
      await tester.runAsync(
        () => expectLater(
          old.submit(
            '$mileageRoot/trips',
            body,
            operation: 'trip.save',
            targetKind: 'trip',
            targetId: body['id'],
          ),
          throwsA(isA<ApiException>()),
        ),
      );
      old.dispose();
      owner.dispose();
      owner = session();
      await tester.runAsync(() => owner.load());
      await tester.pumpWidget(
        MaterialApp(
          home: BusinessTravelAllowancesPage(
            session: owner,
            employee: mileage.copy(mileage.fixture['employee']),
            mileage: true,
          ),
        ),
      );
      await settle(
        tester,
        () => find
            .text('Status des ursprünglichen Auftrags prüfen')
            .evaluate()
            .isNotEmpty,
      );
      expect(find.text('Bestätigung noch offen'), findsOneWidget);
      expect(api.posts.length, 1);
      expect(tester.takeException(), isNull);
      await tester.pumpWidget(const SizedBox.shrink());
      owner.dispose();
      api.dispose();
    },
  );
}

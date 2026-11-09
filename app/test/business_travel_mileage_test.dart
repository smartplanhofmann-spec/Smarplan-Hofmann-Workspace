import 'dart:convert';
import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:smartplan_office/api.dart';
import 'package:smartplan_office/business_session.dart';
import 'package:smartplan_office/business_travel_allowances.dart';
import 'package:smartplan_office/business_travel_cash.dart';
import 'package:smartplan_office/business_travel_mileage.dart';
import 'package:smartplan_office/business_widgets.dart';

final fixture = jsonDecode(
  File('test/fixtures/private_car_mileage.json').readAsStringSync(),
) as Map<String, dynamic>;
Map<String, dynamic> copy(dynamic value) =>
    Map<String, dynamic>.from(jsonDecode(jsonEncode(value)) as Map);
String get employee => fixture['employee']['id'];

class MileageApi extends OfficeApi {
  MileageApi() : super(apiVersion: 'v1') {
    token = 'synthetic-native-mileage';
  }
  String actor = fixture['owner']['id'];
  bool feature = true,
      readMarker = true,
      active = true,
      lose = false,
      accepted = true;
  String? kind, operation, receiptKey;
  Map<String, dynamic>? wrongReceipt;
  final posts = <Map<String, dynamic>>[];
  final receipts = <String, Map<String, dynamic>>{};
  bool showTrip = false;
  @override
  Future<dynamic> call(String path, [Map<String, dynamic>? body]) async {
    final uri = Uri.parse(path);
    if (uri.path == '/api/me') return {'id': actor};
    if (uri.path == '/api/business/capabilities')
      return {
        'compatibility_mode': 'business',
        'generation': 1,
        'storage_version': 10,
        'readonly': false,
        'features': [
          'travel_allowances',
          if (feature) mileageFeature,
          if (readMarker) mileageReadFeature,
        ],
        'capabilities': ['business_travel_allowances'],
        'permissions': [
          'personnel.read',
          'personnel.write',
          'personnel.approve',
          'personnel.export',
        ],
      };
    if (uri.path == '/api/business$mileageRoot/sources') {
      final value = copy(fixture['sources']);
      value['active'] = active;
      return value;
    }
    if (uri.path == '/api/business$mileageRoot/catalog')
      return copy(fixture['catalog']);
    if (uri.path.contains('$mileageRoot/requests/')) {
      final value = receipts[uri.path.split('/').last];
      if (value == null)
        throw const ApiException(404, 'Synthetic original not found.');
      return {...copy(value), ...?wrongReceipt};
    }
    if (body != null && uri.path.startsWith('/api/business$mileageRoot/')) {
      posts.add({'path': uri.path, 'body': copy(body)});
      if (accepted && !receipts.containsKey(body['request_id'])) {
        final receipt = copy(fixture['initial'][receiptKey!]);
        expect(receipt['request_id'], body['request_id']);
        expect(
          receipt['request_hash'],
          await travelHash([operation, kind, body['id'], body]),
        );
        expect(receipt['actor_id'], actor);
        receipts[body['request_id']] = receipt;
      }
      if (lose) {
        lose = false;
        throw const ApiException(0, 'Synthetic accepted mileage reply lost.');
      }
      return {};
    }
    if (uri.path == '/api/business$mileageRoot/trips')
      return {
        'employee_id': employee,
        'items': [if (showTrip) copy(fixture['initial']['trip'])],
      };
    if (uri.path ==
        '/api/business$mileageRoot/trips/${fixture['initial']['trip']['id']}')
      return {'item': copy(fixture['initial']['trip'])};
    if (uri.path == '/api/business$mileageRoot/settlements' ||
        uri.path == '/api/business$mileageRoot/payments')
      return {'employee_id': employee, 'items': []};
    throw StateError(path);
  }
}

Future<
  ({
    MileageApi api,
    BusinessSession session,
    TravelCommand command,
    void Function() cleanup,
  })
>
setup({String? requestId}) async {
  final api = MileageApi();
  final owner = BusinessSession(api: api);
  await owner.load();
  final command = requestId == null
      ? TravelCommand(owner, employeeId: employee, mileage: true)
      : TravelCommand(
          owner,
          employeeId: employee,
          mileage: true,
          requestIdFactory: () => requestId,
        );
  var disposed = false;
  void cleanup() {
    if (!disposed) {
      disposed = true;
      command.clear();
      command.dispose();
      owner.dispose();
      api.dispose();
    }
  }

  addTearDown(cleanup);
  return (api: api, session: owner, command: command, cleanup: cleanup);
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  test('real initial and corrected originals preserve metres, once-only rounding and existing cash', () async {
    mileageCatalog(fixture['catalog']);
    for (final name in ['initial', 'correction']) {
      final b = fixture[name];
      mileageTrip(b['draft'], employee);
      mileageTrip(b['trip'], employee);
      final body = mileagePreviewInput(
        copy(b['trip']),
        b['preview_command']['review_note'],
        previous: name == 'correction'
            ? copy(fixture['initial']['settlement'])
            : null,
      );
      expect(body, b['preview_command']);
      mileagePreview(b['preview'], body, copy(b['trip']));
      mileageCalculation(b['settlement']['calculation'], [
        mileageRef(b['trip']),
      ], trip: copy(b['trip']));
      expect(
        b['preview']['totals']['mileage_allowance_minor'],
        name == 'initial' ? 3000 : 1500,
      );
      expect(
        b['preview']['totals']['overpaid_minor'],
        name == 'initial' ? 0 : 1500,
      );
      expect(
        b['payment_command']['kind'],
        name == 'initial' ? 'reimbursement' : 'repayment',
      );
      travelCashPublic(b['public_source']);
      for (final entry in [
        ('draft_receipt', 'trip_command', 'trip.save', 'trip'),
        ('submit_receipt', 'submit_command', 'trip.submit', 'trip'),
        if (name == 'correction')
          ('reject_receipt', 'reject_command', 'trip.reject', 'trip'),
        (
          'settlement_receipt',
          'settlement_command',
          'settlement.approve',
          'settlement',
        ),
        ('payment_receipt', 'payment_command', 'payment.record', 'payment'),
      ]) {
        final raw = b[entry.$1], command = b[entry.$2];
        await travelReceipt(raw, {
          'request_id': command['request_id'],
          'actor_id': raw['actor_id'],
          'employee_id': employee,
          'operation': entry.$3,
          'target_kind': entry.$4,
          'target_id': raw['target_id'],
          'request_hash': await travelHash([
            entry.$3,
            entry.$4,
            raw['target_id'],
            command,
          ]),
        });
        mileageResult(
          raw['result'],
          copy(command),
          entry.$3,
          actorId: raw['actor_id'],
          targetId: raw['target_id'],
        );
      }
    }
    expect(fixture['initial']['payment_command']['amount_minor'], 3000);
    expect(fixture['correction']['payment_command']['amount_minor'], 1500);
  });
  test('whole metres and personal originals cannot be replaced by money, private or foreign facts', () {
    for (final change in <void Function(Map<String, dynamic>)>[
      (v) => v['details']['mileage']['legs'][0]['distance_m'] = 1.0,
      (v) => v['details']['mileage']['legs'][0]['distance_m'] = 0,
      (v) => v['details']['mileage']['legs'][0]['distance_m'] = 2000001,
      (v) => v['details']['mileage']['vehicle_kind'] = 'company_car',
      (v) => v['details']['mileage']['legs'][0]['amount_minor'] = 3000,
      (v) => v['details']['mileage']['legs'][0]['evidence_file_id'] = 'e' * 32,
      (v) => v['details']['mileage']['no_other_reimbursement'] = 1,
      (v) => v['details']['timezone'] = 'UTC',
      (v) => v['details']['returned_at'] = '2026-10-27T13:00:00+01:00',
      (v) => v['sources']['sites'][0]['employee_id'] = 'e' * 32,
    ]) {
      final v = copy(fixture['initial']['trip']);
      change(v);
      expect(() => mileageTrip(v, employee), throwsA(isA<ApiException>()));
    }
  });
  test('frozen original route and paid correction reject extra rounding, M or net additions', () {
    for (final change in <void Function(Map<String, dynamic>)>[
      (v) => v['totals']['mileage_distance_m']++,
      (v) => v['totals']['mileage_allowance_minor']++,
      (v) => v['totals']['tax_free_minor']++,
      (v) => v['totals']['already_paid_minor'] = 0,
      (v) => v['days'][0]['letter_m'] = true,
      (v) => v['payroll_required'] = true,
      (v) => v['mileage_items'][0]['evidence_sha256'] = 'e' * 64,
      (v) => v['mileage_items'][0]['amount_minor'] = 750,
      (v) => v['mileage_items'][0]['trip_ref']['revision']++,
    ]) {
      final b = fixture['correction'], v = copy(b['preview']);
      change(v);
      expect(
        () => mileagePreview(v, copy(b['preview_command']), copy(b['trip'])),
        throwsA(isA<ApiException>()),
      );
    }
  });
  test('unchecked personal declarations remain draft facts and can never silently approve', () {
    for (final key in mileageDeclarations.keys) {
      final trip = copy(fixture['initial']['trip']);
      trip['details']['mileage'][key] = false;
      mileageDetails(trip['details'], employee, copy(trip['sources']));
      expect(
        () => mileageCalculation(copy(fixture['initial']['preview']), [
          mileageRef(trip),
        ], trip: trip),
        throwsA(isA<ApiException>()),
      );
    }
  });
  test('private mileage and legacy command roots cannot be mixed', () async {
    final t = await setup();
    final legacy = TravelCommand(t.session, employeeId: employee);
    addTearDown(legacy.dispose);
    final body = copy(fixture['initial']['trip_command'])..remove('request_id');
    for (final pair in [
      (t.command, '/personnel/travel/trips'),
      (legacy, '$mileageRoot/trips'),
    ]) {
      await expectLater(
        pair.$1.submit(
          pair.$2,
          body,
          operation: 'trip.save',
          targetKind: 'trip',
          targetId: body['id'],
        ),
        throwsA(isA<ApiException>()),
      );
    }
    await expectLater(
      t.command.read('/personnel/travel/sources?employee_id=$employee'),
      throwsA(isA<ApiException>()),
    );
    expect(t.api.posts, isEmpty);
  });
  test('lost trip settlement and payment replies resolve exact originals by private status only', () async {
    for (final entry in [
      ('trip', 'trip.save', 'trip_command', 'draft', 'draft_receipt', 'write'),
      (
        'settlement',
        'settlement.approve',
        'settlement_command',
        'settlement',
        'settlement_receipt',
        'approve',
      ),
      (
        'payment',
        'payment.record',
        'payment_command',
        'payment',
        'payment_receipt',
        'payments',
      ),
    ]) {
      final b = fixture['initial'];
      final t = await setup(requestId: b[entry.$3]['request_id']);
      t.api.kind = entry.$1;
      t.api.operation = entry.$2;
      t.api.receiptKey = entry.$5;
      t.api.actor = b[entry.$5]['actor_id'];
      t.api.lose = true;
      final body = copy(b[entry.$3])..remove('request_id');
      await expectLater(
        t.command.submit(
          '$mileageRoot/${entry.$1 == 'trip'
              ? 'trips'
              : entry.$1 == 'settlement'
              ? 'settlements'
              : 'payments'}',
          body,
          operation: entry.$2,
          targetKind: entry.$1,
          targetId: body['id'],
          right: entry.$6,
        ),
        throwsA(isA<ApiException>()),
      );
      expect(t.command.pending?.containsKey('body'), false);
      expect(
        t.session.pendingCommandValues('mileage', path: '$mileageRoot/trips'),
        isNull,
      );
      t.api.active = false;
      await t.command.retry();
      expect(t.api.posts.length, 1);
      expect(t.command.pending, isNull);
      final sent = copy(t.api.posts.single['body'])..remove('request_id');
      expect(sent, body);
    }
  });
  test('absent new feature blocks mileage writes while actual original metadata stays readable', () async {
    final t = await setup();
    t.api.feature = false;
    await t.session.load();
    await t.command.fresh();
    final body = copy(fixture['initial']['trip_command'])..remove('request_id');
    await expectLater(
      t.command.submit(
        '$mileageRoot/trips',
        body,
        operation: 'trip.save',
        targetKind: 'trip',
        targetId: body['id'],
      ),
      throwsA(isA<ApiException>()),
    );
    expect(t.api.posts, isEmpty);
  });
  test('the historical entry requires the explicit read marker and never falls back to an old server', () async {
    final t = await setup();
    t.api.readMarker = false;
    await t.session.load();
    await expectLater(t.command.fresh(), throwsA(isA<ApiException>()));
    expect(t.api.posts, isEmpty);
  });
  test('self-consistent altered payment hash or body cannot clear its accepted original', () async {
    for (final change in <void Function(Map<String, dynamic>)>[
      (v) => v['command_hash'] = 'e' * 64,
      (v) => v['details']['amount_minor']++,
      (v) => v['details']['account_id'] = 'e' * 32,
      (v) => v['created_by'] = 'e' * 32,
    ]) {
      final b = fixture['initial'],
          body = copy(fixture['initial']['payment_command'])
            ..remove('request_id');
      final t = await setup(requestId: b['payment_command']['request_id']);
      t.api.kind = 'payment';
      t.api.operation = 'payment.record';
      t.api.receiptKey = 'payment_receipt';
      t.api.actor = b['payment_receipt']['actor_id'];
      t.api.lose = true;
      await expectLater(
        t.command.submit(
          '$mileageRoot/payments',
          body,
          operation: 'payment.record',
          targetKind: 'payment',
          targetId: body['id'],
          right: 'payments',
        ),
        throwsA(isA<ApiException>()),
      );
      final changed = copy(b['payment']);
      change(changed);
      t.api.wrongReceipt = {
        'result': changed,
        'result_hash': await travelHash(changed),
      };
      await expectLater(
        t.command.status(resolve: true),
        throwsA(isA<ApiException>()),
      );
      expect(t.command.pending, isNotNull);
      expect(t.api.posts.length, 1);
      t.api.wrongReceipt = null;
      await t.command.retry();
      expect(t.command.pending, isNull);
      expect(t.api.posts.length, 1);
    }
  });
  testWidgets(
    'explicit native mileage draft starts six declarations false and accepts only whole metres',
    (tester) async {
      final t = await setup();
      tester.view.physicalSize = const Size(390, 844);
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.resetPhysicalSize);
      addTearDown(tester.view.resetDevicePixelRatio);
      await tester.pumpWidget(
        MaterialApp(
          home: BusinessTravelAllowancesPage(
            session: t.session,
            employee: copy(fixture['employee']),
            mileage: true,
          ),
        ),
      );
      await tester.pumpAndSettle();
      await tester.tap(find.text('Private Pkw-Fahrt erfassen'));
      await tester.pumpAndSettle();
      await tester.tap(
        find.text('Fahrtgrunddaten und sechs Erklärungen prüfen'),
      );
      await tester.pumpAndSettle();
      final editor = tester.widget<BusinessEditor>(find.byType(BusinessEditor));
      for (final key in mileageDeclarations.keys) {
        expect(editor.fields.singleWhere((f) => f.name == key).initial, false);
      }
      await tester.tap(find.text('Schließen').last);
      await tester.pumpAndSettle();
      final add = find.text('Belegte Pkw-Teilstrecke hinzufügen');
      await tester.scrollUntilVisible(
        add,
        300,
        scrollable: find.byType(Scrollable).first,
      );
      await tester.tap(add);
      await tester.pumpAndSettle();
      final legEditor = tester.widget<BusinessEditor>(
        find.byType(BusinessEditor),
      );
      expect(
        legEditor.fields.singleWhere((f) => f.name == 'distance_m').type,
        BusinessInput.integer,
      );
      expect(legEditor.fields.any((f) => f.name.contains('amount')), false);
      expect(t.api.posts, isEmpty);
      await tester.pumpWidget(const SizedBox());
      t.cleanup();
      await tester.pump();
    },
  );
  testWidgets(
    'reused private mileage state clears its original employee owner and mode',
    (tester) async {
      for (final change in ['employee', 'owner', 'mode']) {
        final first = await setup(), other = await setup();
        first.api.showTrip = true;
        Widget page({bool changed = false}) => MaterialApp(
          home: BusinessTravelAllowancesPage(
            key: const ValueKey('mileage-private-context'),
            session: changed && change == 'owner'
                ? other.session
                : first.session,
            employee: changed && change == 'employee'
                ? {
                    ...copy(fixture['employee']),
                    'id': 'e' * 32,
                    'name': 'Other private employee',
                  }
                : copy(fixture['employee']),
            mileage: !(changed && change == 'mode'),
          ),
        );
        try {
          await tester.pumpWidget(page());
          await tester.pumpAndSettle();
          expect(
            find.text(fixture['initial']['trip']['details']['purpose']),
            findsOneWidget,
          );
          await tester.pumpWidget(page(changed: true));
          await tester.pumpAndSettle();
          expect(
            find.textContaining(
              fixture['initial']['trip']['details']['purpose'],
            ),
            findsNothing,
          );
          expect(find.text('Private Pkw-Fahrt erfassen'), findsNothing);
          await first.session.load();
          await tester.pumpAndSettle();
          expect(
            find.textContaining(
              fixture['initial']['trip']['details']['purpose'],
            ),
            findsNothing,
          );
          expect(first.api.posts, isEmpty);
          expect(other.api.posts, isEmpty);
        } finally {
          await tester.pumpWidget(const SizedBox());
          first.cleanup();
          other.cleanup();
          await tester.pump();
        }
      }
    },
  );
  testWidgets(
    'submitted mileage original is readable and cannot be silently corrected before rejection',
    (tester) async {
      final t = await setup();
      t.api.showTrip = true;
      await tester.pumpWidget(
        MaterialApp(
          home: BusinessTravelAllowancesPage(
            session: t.session,
            employee: copy(fixture['employee']),
            mileage: true,
          ),
        ),
      );
      await tester.pumpAndSettle();
      await tester.tap(
        find.text(fixture['initial']['trip']['details']['purpose']),
      );
      await tester.pumpAndSettle();
      expect(find.text('Reise korrigieren'), findsNothing);
      await tester.scrollUntilVisible(
        find.textContaining('SYNTHETIC-1'),
        250,
        scrollable: find.byType(Scrollable).first,
      );
      expect(find.textContaining('SYNTHETIC-1'), findsWidgets);
      await tester.scrollUntilVisible(
        find.text('Alle Fassungen öffnen'),
        250,
        scrollable: find.byType(Scrollable).first,
      );
      expect(find.text('Alle Fassungen öffnen'), findsOneWidget);
      expect(t.api.posts, isEmpty);
      await tester.pumpWidget(const SizedBox());
      t.cleanup();
      await tester.pump();
    },
  );
}

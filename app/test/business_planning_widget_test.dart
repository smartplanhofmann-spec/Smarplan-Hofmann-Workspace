import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:smartplan_office/api.dart';
import 'package:smartplan_office/business_planning.dart';
import 'package:smartplan_office/business_session.dart';

import 'business_session_test.dart' show BusinessTestApi;

class PlanningApi extends BusinessTestApi {
  bool collision = false;
  late Map<String, dynamic> appointment;
  PlanningApi() {
    final n = DateTime.now();
    final monday = DateTime(n.year, n.month, n.day - n.weekday + 1, 8);
    appointment = {
      'id': 'a' * 32,
      'project_id': 'b' * 32,
      'title': 'Synthetischer Montageeinsatz',
      'details': 'Vor Ort prüfen',
      'timezone': 'Europe/Berlin',
      'start_at': monday.toUtc().toIso8601String(),
      'end_at': monday.add(const Duration(hours: 2)).toUtc().toIso8601String(),
      'employee_ids': ['c' * 32],
      'resource_ids': <String>[],
      'status': 'scheduled',
      'revision': 1,
    };
  }
  @override
  Future<dynamic> call(String path, [Map<String, dynamic>? body]) async {
    if (path.split('?').first == '/api/business/capabilities')
      return {
        'storage_version': 7,
        'compatibility_mode': 'business',
        'generation': 1,
        'capabilities': ['business_planning'],
        'permissions': ['planning.read', 'planning.write'],
      };
    calls.add((path: path, body: body));
    if (path.contains('/planning/calendar'))
      return {
        'appointments': [Map<String, dynamic>.from(appointment)],
        'employees': [
          {'id': 'c' * 32, 'name': 'Synthetischer Techniker'},
        ],
        'resources': [],
        'absences': [],
      };
    if (path.startsWith('/api/business/appointments') && body != null) {
      if (collision)
        throw const ApiException(409, 'Synthetische Doppelbelegung');
      appointment = {
        ...appointment,
        ...body,
        'revision': appointment['revision'] + 1,
      };
      return appointment;
    }
    return super.call(path, body);
  }
}

void main() {
  testWidgets(
    'Dragging a confirmed appointment updates the same employee-calendar record',
    (tester) async {
      tester.view.physicalSize = const Size(1100, 1100);
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.resetPhysicalSize);
      addTearDown(tester.view.resetDevicePixelRatio);
      final api = PlanningApi();
      final session = BusinessSession(api: api, projectId: 'b' * 32);
      await session.load();
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(body: BusinessPlanningPage(session: session)),
        ),
      );
      await tester.pumpAndSettle();
      final gesture = await tester.startGesture(
        tester.getCenter(find.text('Synthetischer Montageeinsatz')),
      );
      await tester.pump(const Duration(milliseconds: 700));
      final target = find.textContaining('Dienstag ·');
      await gesture.moveTo(tester.getCenter(target));
      await tester.pump(const Duration(milliseconds: 100));
      await gesture.up();
      await tester.pumpAndSettle();
      expect(
        DateTime.parse(api.appointment['start_at']).toLocal().weekday,
        DateTime.tuesday,
      );
      expect(api.appointment['employee_ids'], ['c' * 32]);
      expect(
        api.calls.where((c) => c.body != null).single.path,
        '/api/business/appointments/${'a' * 32}',
      );
      expect(tester.takeException(), isNull);
      await tester.pumpWidget(const SizedBox());
      session.dispose();
      api.dispose();
    },
  );
  testWidgets(
    'A collision keeps the original calendar and shows a clear failure',
    (tester) async {
      tester.view.physicalSize = const Size(1100, 1100);
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.resetPhysicalSize);
      addTearDown(tester.view.resetDevicePixelRatio);
      final api = PlanningApi()..collision = true;
      final original = api.appointment['start_at'];
      final session = BusinessSession(api: api, projectId: 'b' * 32);
      await session.load();
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(body: BusinessPlanningPage(session: session)),
        ),
      );
      await tester.pumpAndSettle();
      final gesture = await tester.startGesture(
        tester.getCenter(find.text('Synthetischer Montageeinsatz')),
      );
      await tester.pump(const Duration(milliseconds: 700));
      await gesture.moveTo(tester.getCenter(find.textContaining('Dienstag ·')));
      await tester.pump(const Duration(milliseconds: 100));
      await gesture.up();
      await tester.pumpAndSettle();
      expect(api.appointment['start_at'], original);
      expect(find.text('Synthetische Doppelbelegung'), findsOneWidget);
      expect(tester.takeException(), isNull);
      await tester.pumpWidget(const SizedBox());
      session.dispose();
      api.dispose();
    },
  );
}

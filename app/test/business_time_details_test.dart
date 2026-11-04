import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:smartplan_office/api.dart';
import 'package:smartplan_office/business_session.dart';
import 'package:smartplan_office/business_time_details.dart';
import 'package:smartplan_office/business_workflows.dart';

import 'business_session_test.dart' show BusinessTestApi;

class TimeDetailsApi extends BusinessTestApi {
  bool approver = true, own = true, loseCorrectionAck = false;
  final entryId = 'c' * 32;
  final corrections = <Map<String, dynamic>>[];
  final receipts = <String, Map<String, dynamic>>{};
  final writes = <Map<String, dynamic>>[];
  Map<String, dynamic> get entry => {
    'id': entryId,
    'project_id': 'b' * 32,
    'employee_id': 'd' * 32,
    'revision': 2,
    'status': 'approved',
    'timezone': 'Europe/Berlin',
    'started_at': '2026-10-25T23:30:00Z',
    'ended_at': '2026-10-26T01:30:00Z',
    'work_dates': ['2026-10-26'],
    'approved_work_dates': ['2026-10-26'],
    'worked_seconds': 7200,
    'break_seconds': 0,
    'events': [
      {'action': 'start', 'occurred_at': '2026-10-25T23:30:00Z'},
      {'action': 'stop', 'occurred_at': '2026-10-26T01:30:00Z'},
    ],
    'corrections': corrections,
  };
  @override
  Future<dynamic> call(String path, [Map<String, dynamic>? body]) async {
    final route = path.split('?').first;
    if (route == '/api/business/capabilities')
      return {
        'storage_version': 7,
        'compatibility_mode': 'business',
        'generation': 1,
        'readonly': readMode,
        'capabilities': ['business_time'],
        'permissions': [if (own) 'time.own', if (approver) 'time.approve'],
      };
    if (route == '/api/business/time/entries/$entryId')
      return jsonDecode(jsonEncode(entry));
    if (route == '/api/business/time/entries')
      return {
        'items': [entry],
      };
    if (route == '/api/business/time/accounts')
      return {'employee_id': 'd' * 32, 'days': []};
    if (route == '/api/business/time/entries/$entryId/correct') {
      final command = Map<String, dynamic>.from(jsonDecode(jsonEncode(body)));
      writes.add(command);
      final result = receipts.putIfAbsent(command['request_id'], () {
        final value = <String, dynamic>{
          'id': 'e' * 32,
          'entry_id': entryId,
          'work_date': command['work_date'],
          'delta_seconds': command['delta_seconds'],
          'reason': command['reason'],
        };
        corrections.add(value);
        return value;
      });
      if (loseCorrectionAck) {
        loseCorrectionAck = false;
        throw const ApiException(0, 'Synthetisch verlorene Antwort');
      }
      return result;
    }
    throw StateError('Unexpected time API $path');
  }
}

Future<void> openDetails(
  WidgetTester tester,
  BusinessSession session,
  String id,
) async {
  await tester.pumpWidget(
    MaterialApp(
      home: Scaffold(
        body: Builder(
          builder: (context) => FilledButton(
            onPressed: () => showBusinessTimeDetails(context, session, id),
            child: const Text('Nachweis öffnen'),
          ),
        ),
      ),
    ),
  );
  await tester.tap(find.text('Nachweis öffnen'));
  await tester.pumpAndSettle();
}

void main() {
  testWidgets(
    'Mobile correction uses approved server date and reopens the exact lost acknowledgement',
    (tester) async {
      tester.view.physicalSize = const Size(390, 844);
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.resetPhysicalSize);
      addTearDown(tester.view.resetDevicePixelRatio);
      final api = TimeDetailsApi()..loseCorrectionAck = true;
      final session = BusinessSession(
        api: api,
        projects: [
          {'id': 'b' * 32, 'name': 'Kundenprojekt Nord'},
        ],
      );
      await session.load();
      await openDetails(tester, session, api.entryId);
      expect(find.textContaining('Erfasste Arbeitszeit: 2:00'), findsOneWidget);
      expect(find.text('Projekt: Kundenprojekt Nord'), findsOneWidget);
      await tester.tap(
        find.widgetWithText(FilledButton, 'Freigegebene Zeit korrigieren'),
      );
      await tester.pumpAndSettle();
      expect(find.text('26.10.2026'), findsWidgets);
      await tester.enterText(
        find.widgetWithText(TextFormField, 'Änderung in Minuten'),
        '-30',
      );
      await tester.enterText(
        find.widgetWithText(TextFormField, 'Korrekturgrund'),
        'Doppelt erfasste halbe Stunde',
      );
      await tester.ensureVisible(find.byType(SwitchListTile));
      await tester.tap(find.byType(SwitchListTile));
      await tester.tap(find.text('Begründete Korrektur speichern'));
      await tester.pumpAndSettle();
      expect(api.writes, hasLength(1));
      expect(api.writes.single['work_date'], '2026-10-26');
      expect(api.writes.single['delta_seconds'], -1800);
      await tester.tap(find.text('Schließen').last);
      await tester.pumpAndSettle();
      await tester.tap(
        find.widgetWithText(FilledButton, 'Freigegebene Zeit korrigieren'),
      );
      await tester.pumpAndSettle();
      await tester.tap(find.text('Erneut senden'));
      await tester.pumpAndSettle();
      expect(api.writes, hasLength(2));
      expect(api.writes.first, api.writes.last);
      expect(api.corrections, hasLength(1));
      expect(
        find.textContaining('Doppelt erfasste halbe Stunde'),
        findsOneWidget,
      );
      expect(find.textContaining('-0:30 Std.'), findsOneWidget);
      expect(api.entry['events'], hasLength(2));
      expect(tester.takeException(), isNull);
      await tester.pumpWidget(const SizedBox());
      session.dispose();
      api.dispose();
    },
  );

  testWidgets(
    'Read-only and non-approver can inspect seconds but cannot correct',
    (tester) async {
      final api = TimeDetailsApi()..approver = false;
      api.corrections.add({
        'work_date': '2026-10-26',
        'delta_seconds': -1,
        'reason': 'Eine Sekunde berichtigt',
      });
      final session = BusinessSession(
        api: api,
        projects: [
          {'id': 'b' * 32, 'name': 'Kundenprojekt Nord'},
        ],
      );
      await session.load();
      await openDetails(tester, session, api.entryId);
      expect(find.textContaining('-0:00:01 Std.'), findsOneWidget);
      expect(
        find.widgetWithText(FilledButton, 'Freigegebene Zeit korrigieren'),
        findsNothing,
      );
      api.approver = true;
      api.readMode = true;
      await session.load();
      await tester.pumpAndSettle();
      expect(
        find.widgetWithText(FilledButton, 'Freigegebene Zeit korrigieren'),
        findsNothing,
      );
      expect(api.writes, isEmpty);
      await tester.pumpWidget(const SizedBox());
      session.dispose();
      api.dispose();
    },
  );

  testWidgets(
    'Revoked time access clears the already open original and history',
    (tester) async {
      final api = TimeDetailsApi();
      final session = BusinessSession(
        api: api,
        projects: [
          {'id': 'b' * 32, 'name': 'Kundenprojekt Nord'},
        ],
      );
      await session.load();
      await openDetails(tester, session, api.entryId);
      expect(find.text('Originalereignisse'), findsOneWidget);
      api.own = false;
      await session.load();
      await tester.pumpAndSettle();
      expect(find.text('Originalereignisse'), findsNothing);
      expect(
        find.widgetWithText(FilledButton, 'Freigegebene Zeit korrigieren'),
        findsNothing,
      );
      expect(api.writes, isEmpty);
      await tester.pumpWidget(const SizedBox());
      session.dispose();
      api.dispose();
    },
  );

  testWidgets(
    'Own time account exposes originals without the staff-only CSV export',
    (tester) async {
      final api = TimeDetailsApi()..approver = false;
      final session = BusinessSession(
        api: api,
        projects: [
          {'id': 'b' * 32, 'name': 'Kundenprojekt Nord'},
        ],
      );
      await session.load();
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(body: BusinessTimeAccountsPage(session: session)),
        ),
      );
      await tester.pumpAndSettle();
      expect(find.text('Einzelne Zeitnachweise'), findsOneWidget);
      expect(find.text('Freigegebene Stunden exportieren'), findsNothing);
      expect(tester.takeException(), isNull);
      await tester.pumpWidget(const SizedBox());
      session.dispose();
      api.dispose();
    },
  );
}

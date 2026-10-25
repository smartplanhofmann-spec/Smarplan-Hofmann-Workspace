import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:smartplan_office/api.dart';
import 'package:smartplan_office/business_session.dart';
import 'package:smartplan_office/business_time.dart';

import 'business_session_test.dart' show BusinessTestApi;

class ClockApi extends BusinessTestApi {
  bool loseStartAck = false;
  final receipts = <String, Map<String, dynamic>>{};
  Map<String, dynamic>? entry;
  @override
  Future<dynamic> call(String path, [Map<String, dynamic>? body]) async {
    if (path.split('?').first == '/api/business/capabilities')
      return {
        'storage_version': 7,
        'compatibility_mode': 'business',
        'generation': 1,
        'capabilities': ['business_time'],
        'permissions': ['time.own'],
      };
    if (path.contains('/time/entries')) return {'items': []};
    if (path == '/api/business/time/events') {
      calls.add((
        path: path,
        body: Map<String, dynamic>.from(jsonDecode(jsonEncode(body))),
      ));
      expect(
        body!['event_id'],
        isNull,
        reason: 'The server derives event_id from the stable request_id.',
      );
      final request = body['request_id'] as String;
      if (receipts.containsKey(request)) return receipts[request];
      expect(body['revision'], entry?['revision'] ?? 0);
      expect(body['sequence'], (entry?['sequence'] as int? ?? 0) + 1);
      entry = {
        'id': body['entry_id'],
        'project_id': body['project_id'],
        'revision': body['revision'] + 1,
        'sequence': body['sequence'],
        'status': body['action'] == 'pause'
            ? 'paused'
            : body['action'] == 'stop'
            ? 'stopped'
            : 'working',
        'started_at': DateTime.now().toUtc().toIso8601String(),
        'events': [],
        'worked_seconds': 0,
      };
      final result = {
        'request_id': request,
        'event_id': request,
        'entry': entry,
      };
      receipts[request] = result;
      if (loseStartAck) {
        loseStartAck = false;
        throw const ApiException(0, 'Verlorene Bestätigung');
      }
      return result;
    }
    throw StateError('Unexpected clock API $path');
  }
}

void main() {
  testWidgets(
    'Online clock actions use the canonical revision and sequence without conflicting event IDs',
    (tester) async {
      final api = ClockApi();
      final session = BusinessSession(api: api, projectId: 'b' * 32);
      await session.load();
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(body: BusinessTimePage(session: session)),
        ),
      );
      await tester.pumpAndSettle();
      await tester.tap(find.text('Arbeit beginnen'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Pause beginnen'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Arbeit beenden'));
      await tester.pumpAndSettle();
      expect(api.entry?['revision'], 3);
      expect(api.entry?['status'], 'stopped');
      expect(api.receipts, hasLength(3));
      expect(tester.takeException(), isNull);
      await tester.pumpWidget(const SizedBox());
      session.dispose();
      api.dispose();
    },
  );
  testWidgets(
    'Lost online clock acknowledgement retries the same exact operation',
    (tester) async {
      final api = ClockApi()..loseStartAck = true;
      final session = BusinessSession(api: api, projectId: 'b' * 32);
      await session.load();
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(body: BusinessTimePage(session: session)),
        ),
      );
      await tester.pumpAndSettle();
      await tester.tap(find.text('Arbeit beginnen'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Dieselbe Zeitaktion erneut senden'));
      await tester.pumpAndSettle();
      expect(api.receipts, hasLength(1));
      expect(api.calls[0].body, api.calls[1].body);
      expect(api.entry?['revision'], 1);
      expect(tester.takeException(), isNull);
      await tester.pumpWidget(const SizedBox());
      session.dispose();
      api.dispose();
    },
  );
}

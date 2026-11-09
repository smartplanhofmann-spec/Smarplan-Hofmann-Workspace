import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:smartplan_office/api.dart';
import 'package:smartplan_office/business_communication_history.dart';
import 'package:smartplan_office/business_session.dart';

final f = jsonDecode(
  File('test/fixtures/communication_history.json').readAsStringSync(),
) as Map<String, dynamic>;
Map<String, dynamic> copy(dynamic v) =>
    Map<String, dynamic>.from(jsonDecode(jsonEncode(v)) as Map);

class HistoryApi extends OfficeApi {
  HistoryApi() : super(apiVersion: 'v1') {
    token = 'synthetic-history-session-12345';
  }
  bool read = true, changeAfterRead = false;
  int historyReads = 0;
  Completer<dynamic>? pending;
  @override
  Future<dynamic> call(String path, [Map<String, dynamic>? body]) async {
    if (path.startsWith('/api/business/capabilities'))
      return {
        'storage_version': 7,
        'generation': 1,
        'compatibility_mode': 'business',
        'readonly': false,
        'capabilities': ['business_sales'],
        'features': ['communication_history'],
        'permissions': [
          if (read) 'contacts.read',
          if (!changeAfterRead || historyReads == 0) 'finance.read',
        ],
      };
    if (path.startsWith('/api/business/sales/communication-history?')) {
      historyReads++;
      return pending == null ? copy(f['full']) : await pending!.future;
    }
    throw StateError('Unexpected synthetic history path $path');
  }
}

void main() {
  test('actual customer/project source snapshots bind all six categories', () {
    final full = communicationHistoryPage(f['full'], copy(f['scope']));
    expect((full['items'] as List).length, 11);
    expect((full['items'] as List).map((v) => v['kind']).toSet().length, 6);
    communicationHistoryPage(f['project'], copy(f['project_scope']));
    expect(
      communicationStatus({'kind': 'inquiry', 'status': 'accepted'}),
      'Zusage vermerkt',
    );
    expect(
      communicationStatus({'kind': 'delivery', 'status': 'accepted'}),
      'Vom Versandserver angenommen',
    );
  });
  test('stable paging preserves original and corrected activities once', () {
    final scope = {...copy(f['scope']), 'limit': '2'};
    final first = communicationHistoryPage(f['first'], scope),
        second = communicationHistoryPage(f['second'], scope, previous: first);
    expect((second['items'] as List).length, 4);
    final changed = copy(f['second']);
    changed['snapshot_sha256'] = 'f' * 64;
    expect(
      () => communicationHistoryPage(changed, scope, previous: first),
      throwsA(isA<ApiException>()),
    );
    expect(
      () => communicationHistoryPage(
        f['second'],
        copy(f['scope']),
        previous: first,
      ),
      throwsA(isA<ApiException>()),
    );
    final full = communicationHistoryPage(f['full'], copy(f['scope']));
    final old = (full['items'] as List).firstWhere(
      (i) => i['superseded'] == true,
    );
    final correction = (full['items'] as List).firstWhere(
      (i) => i['supersedes_key'] == old['key'],
    );
    expect(correction['provenance'], 'manual_activity');
    expect(correction['precision'], 'day');
    expect(correction['accepted_by_server'], isFalse);
  });
  test('foreign scope, extra fields, false delivery and invalid timestamps fail closed', () {
    final changes = <void Function(Map<String, dynamic>)>[
      (v) => v['customer']['id'] = 'f' * 32,
      (v) => v['items'][0]['credential'] = 'forbidden',
      (v) => v['items'][0]['recipient_delivery_confirmed'] = true,
      (v) => v['items'][0]['accepted_by_server'] =
          !v['items'][0]['accepted_by_server'],
      (v) => v['items'][0]['recorded_at'] = '2026-02-30T00:00:00+00:00',
      (v) => v['items'].add(v['items'][0]),
      (v) => v['items'] = (v['items'] as List).reversed.toList(),
    ];
    for (final change in changes) {
      final altered = copy(f['full']);
      change(altered);
      expect(
        () => communicationHistoryPage(altered, copy(f['scope'])),
        throwsA(isA<ApiException>()),
      );
    }
    final unicode = copy(f['full']);
    unicode['items'][0]['text'] = List.filled(40000, '😀').join();
    communicationHistoryPage(unicode, copy(f['scope']));
  });
  testWidgets(
    'mobile history renders source meaning and clears immediately on fresh role withdrawal',
    (tester) async {
      final api = HistoryApi();
      final current = BusinessSession(api: api);
      await current.load();
      await tester.binding.setSurfaceSize(const Size(390, 844));
      addTearDown(() => tester.binding.setSurfaceSize(null));
      await tester.pumpWidget(
        MaterialApp(
          home: BusinessCommunicationHistoryPage(
            session: current,
            customerId: f['scope']['customer_id'],
          ),
        ),
      );
      await tester.pumpAndSettle();
      expect(api.historyReads, 1);
      await tester.scrollUntilVisible(
        find.text(f['full']['items'][0]['title']),
        400,
        scrollable: find.byType(Scrollable).first,
      );
      expect(find.text(f['full']['items'][0]['title']), findsOneWidget);
      api.read = false;
      await current.load();
      await tester.pumpAndSettle();
      expect(find.text(f['full']['items'][0]['title']), findsNothing);
      expect(find.text('Der Zugang ist nicht mehr verfügbar.'), findsOneWidget);
      expect(tester.takeException(), isNull);
      await tester.pumpWidget(const SizedBox());
      current.dispose();
      api.dispose();
    },
  );
  testWidgets(
    'background and inactive project slot discard pending private response',
    (tester) async {
      final api = HistoryApi();
      final current = BusinessSession(api: api);
      await current.load();
      api.pending = Completer<dynamic>();
      Widget page(bool active) => MaterialApp(
        home: BusinessCommunicationHistoryPage(
          session: current,
          customerId: f['scope']['customer_id'],
          active: active,
        ),
      );
      await tester.pumpWidget(page(true));
      await tester.pump();
      expect(api.historyReads, 1);
      expect(tester.widget<TextField>(find.byType(TextField)).enabled, isFalse);
      await tester.pumpWidget(page(false));
      api.pending!.complete(copy(f['full']));
      await tester.pumpAndSettle();
      expect(find.text(f['full']['items'][0]['title']), findsNothing);
      api.pending = null;
      await tester.pumpWidget(page(true));
      await tester.pumpAndSettle();
      expect(api.historyReads, 2);
      expect(tester.widget<TextField>(find.byType(TextField)).enabled, isTrue);
      tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.inactive);
      await tester.pump();
      expect(find.text(f['full']['items'][0]['title']), findsNothing);
      tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.hidden);
      tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.paused);
      tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.hidden);
      tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.inactive);
      tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.resumed);
      await tester.pump();
      expect(api.historyReads, 2);
      await tester.pumpWidget(const SizedBox());
      current.dispose();
      api.dispose();
    },
  );
  testWidgets(
    'permissions changed between source and final guard never render old source',
    (tester) async {
      final api = HistoryApi();
      final session = BusinessSession(api: api);
      await session.load();
      api.changeAfterRead = true;
      await tester.pumpWidget(
        MaterialApp(
          home: BusinessCommunicationHistoryPage(
            session: session,
            customerId: f['scope']['customer_id'],
          ),
        ),
      );
      await tester.pumpAndSettle();
      expect(find.text(f['full']['items'][0]['title']), findsNothing);
      expect(find.textContaining('Leserechte wurden'), findsOneWidget);
      await tester.pumpWidget(const SizedBox());
      session.dispose();
      api.dispose();
    },
  );
}

import 'dart:convert';
import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:smartplan_office/api.dart';
import 'package:smartplan_office/business_resource_custody.dart';
import 'package:smartplan_office/business_service.dart';
import 'package:smartplan_office/business_session.dart';

Map<String, dynamic> fixture() => jsonDecode(File(
  'test/fixtures/service_equipment_native_review_2026.json',
).readAsStringSync()) as Map<String, dynamic>;

class ActualServiceEquipmentApi extends OfficeApi {
  ActualServiceEquipmentApi({this.empty = false}) : super(apiVersion: 'v1') {
    token = empty ? 'synthetic-second-context' : 'synthetic-original-context';
  }
  final bool empty;
  final f = fixture();
  @override
  Future<dynamic> call(String path, [Map<String, dynamic>? body]) async {
    final uri = Uri.parse(path), p = uri.path;
    if (body != null) throw StateError('Unexpected mutation: $path');
    if (p.endsWith('/capabilities')) {
      return f[uri.queryParameters.containsKey('project_id')
          ? 'scoped_capabilities' : 'capabilities'];
    }
    if (p == '/api/me') return f['actor'];
    final service = f['service'], custody = f['custody'];
    if (p.endsWith('/service/options')) return service['options'];
    if (p.endsWith('/service/cases')) {
      return empty ? {...service['listing'] as Map, 'items': []} : service['listing'];
    }
    if (p.endsWith('/service/cases/${service['item']['id']}/history')) return service['history'];
    if (p.endsWith('/service/cases/${service['item']['id']}')) return service['item'];
    if (p.endsWith('/resource-custody/options')) return custody['options'];
    if (p.endsWith('/resource-custody/${custody['item']['id']}/history')) return custody['history'];
    if (p.endsWith('/resource-custody/${custody['item']['id']}')) return custody['item'];
    if (p.endsWith('/resource-custody')) return empty ? {'items': []} : custody['listing'];
    throw StateError(path);
  }
}

void main() {
  for (final kind in ['service', 'custody']) {
    testWidgets('actual $kind original is removed on allowed session replacement', (t) async {
      final api = ActualServiceEquipmentApi(), nextApi = ActualServiceEquipmentApi(empty: true);
      final session = BusinessSession(api: api), next = BusinessSession(api: nextApi);
      await session.load();
      expect(session.allowed, true);
      await t.binding.setSurfaceSize(const Size(1200, 1200));
      addTearDown(() => t.binding.setSurfaceSize(null));
      await next.load();
      final privateTitle = kind == 'service'
          ? api.f['service']['item']['title'] as String
          : api.f['custody']['item']['resource']['name'] as String;
      Widget page(BusinessSession s) => MaterialApp(home: kind == 'service'
          ? BusinessServicePage(session: s)
          : BusinessResourceCustodyPage(session: s));
      try {
        await t.pumpWidget(page(session));
        await t.pumpAndSettle();
        expect(find.text(privateTitle), findsWidgets);
        await t.pumpWidget(page(next));
        await t.pumpAndSettle();
        expect(find.text(privateTitle), findsNothing,
            reason: 'The replacement session has no corresponding visible record.');
      } finally {
        await t.pumpWidget(const SizedBox());
        session.dispose(); next.dispose(); api.dispose(); nextApi.dispose();
      }
    });
    testWidgets('actual $kind original is cleared while backgrounded', (t) async {
      final api = ActualServiceEquipmentApi();
      final session = BusinessSession(api: api);
      await session.load();
      expect(session.allowed, true);
      await t.binding.setSurfaceSize(const Size(1200, 1200));
      addTearDown(() => t.binding.setSurfaceSize(null));
      final privateTitle = kind == 'service'
          ? api.f['service']['item']['title'] as String
          : api.f['custody']['item']['resource']['name'] as String;
      try {
        await t.pumpWidget(MaterialApp(home: kind == 'service'
            ? BusinessServicePage(session: session)
            : BusinessResourceCustodyPage(session: session)));
        await t.pumpAndSettle();
        expect(find.text(privateTitle), findsWidgets);
        t.binding.handleAppLifecycleStateChanged(AppLifecycleState.inactive);
        t.binding.handleAppLifecycleStateChanged(AppLifecycleState.hidden);
        t.binding.handleAppLifecycleStateChanged(AppLifecycleState.paused);
        await t.pump();
        expect(find.text(privateTitle), findsNothing);
      } finally {
        t.binding.handleAppLifecycleStateChanged(AppLifecycleState.hidden);
        t.binding.handleAppLifecycleStateChanged(AppLifecycleState.inactive);
        t.binding.handleAppLifecycleStateChanged(AppLifecycleState.resumed);
        await t.pumpWidget(const SizedBox());
        session.dispose(); api.dispose();
      }
    });
  }
}

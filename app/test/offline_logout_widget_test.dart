import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:smartplan_office/api.dart';
import 'package:smartplan_office/main.dart';
import 'package:smartplan_office/offline_plans.dart';

import 'administration_return_navigation_test.dart' show AdministrationApi;
import 'offline_plans_test.dart' show TestDevice;

class FailingClose extends OfflinePlans {
  FailingClose(OfficeApi api, this.reason) : super(api: api);
  final String reason;
  @override
  Future<void> logout() async => throw FileSystemException(reason);
}

class OnlineWithoutOffline extends AdministrationApi {
  OnlineWithoutOffline(this.missing);
  final bool missing;
  int contextReads = 0;
  @override
  Future<dynamic> call(String path, [Map<String, dynamic>? body]) async {
    if (path == '/api/me')
      return {'id': 'a' * 32, 'email': 'owner@example.test', 'role': 'owner'};
    if (path == '/api/offline/context') {
      contextReads++;
      if (missing) throw const ApiException(404, 'Synthetic old server');
      return {'schema_version': 2, 'mode': 'unbound_legacy', 'binding': null};
    }
    return super.call(path, body);
  }
}

void main() {
  for (final missing in [false, true]) {
    testWidgets(
      'online login remains usable when offline binding ${missing ? "is missing" : "is unbound"}',
      (tester) async {
        final api = OnlineWithoutOffline(missing);
        final device = TestDevice(Directory('unused'));
        try {
          await tester.binding.setSurfaceSize(const Size(1200, 900));
          await tester.pumpWidget(OfficeApp(api: api));
          final dynamic state = tester.state(find.byType(OfficeHome));
          final repo = OfflinePlans(api: api, device: device);
          state.offline = repo;
          await tester.enterText(
            find.byType(TextFormField).at(0),
            'owner@example.test',
          );
          await tester.enterText(
            find.byType(TextFormField).at(1),
            'Synthetic-password-123',
          );
          await tester.tap(find.text('Anmelden'));
          await tester.pumpAndSettle();
          expect(api.contextReads, 1);
          expect(api.token, isNotNull);
          expect(state.user['id'], 'a' * 32);
          expect(state.projects, isNotEmpty);
          expect(repo.active, isFalse);
          expect(find.text('Anmelden'), findsNothing);
          expect(device.keys, isEmpty);
          expect(device.sessions, isEmpty);
          expect(device.accounts, isEmpty);
          expect(tester.takeException(), isNull);
        } finally {
          await tester.pumpWidget(const SizedBox());
          await tester.binding.setSurfaceSize(null);
          api.dispose();
        }
      },
    );
  }

  for (final reason in [
    'Synthetic disk lock failure',
    'Synthetic token removal failure',
  ]) {
    testWidgets(
      'application clears private UI when offline logout reports $reason',
      (tester) async {
        final api = AdministrationApi();
        try {
          await tester.binding.setSurfaceSize(const Size(1200, 900));
          await tester.pumpWidget(OfficeApp(api: api));
          await tester.enterText(
            find.byType(TextFormField).at(0),
            'owner@example.test',
          );
          await tester.enterText(
            find.byType(TextFormField).at(1),
            'Synthetic-password-123',
          );
          await tester.tap(find.text('Anmelden'));
          await tester.pumpAndSettle();
          final dynamic state = tester.state(find.byType(OfficeHome));
          expect(state.user, isNotNull);
          final business = state.business;
          state.offline = FailingClose(api, reason);
          await state.logout();
          await tester.pumpAndSettle();
          expect(api.token, isNull);
          expect(state.user, isNull);
          expect(state.projects, isEmpty);
          expect(state.storage, isNull);
          expect(state.offlineMode, isFalse);
          if (business != null) expect(business.denied, isTrue);
          expect(find.text('Anmelden'), findsOneWidget);
          expect(find.textContaining(reason), findsOneWidget);
          expect(tester.takeException(), isNull);
        } finally {
          await tester.pumpWidget(const SizedBox());
          await tester.binding.setSurfaceSize(null);
          api.dispose();
        }
      },
    );
  }
}

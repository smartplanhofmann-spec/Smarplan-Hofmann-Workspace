import 'dart:async';
import 'dart:convert';
import 'dart:typed_data';

import 'package:cryptography/cryptography.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:smartplan_office/api.dart';
import 'package:smartplan_office/business_privacy_cases.dart';
import 'package:smartplan_office/business_session.dart';

const caseId = 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',
    actor = 'bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb';
Map<String, dynamic> copy(dynamic value) =>
    Map<String, dynamic>.from(jsonDecode(jsonEncode(value)) as Map);
Map<String, dynamic> record() => {
  'id': caseId,
  'revision': 1,
  'status': 'open',
  'purged': false,
  'automatic_completeness': false,
  'external_messages_sent': false,
  'request_kind': 'access',
  'subject_kind': 'customer',
  'subject_id': 'c' * 32,
  'subject_label': 'Synthetic private case',
  'scope': 'PRIVATE REQUEST CONTENT',
  'received_date': '2026-11-03',
  'due_date': '2026-12-03',
  'retain_until': '2027-01-01',
  'retention_reason': 'Documented limited purpose',
  'legal_hold': false,
  'assigned_to': actor,
  'identity': null,
  'inventory': null,
  'reviews': {},
  'manual_reviews': {},
  'actions': [],
  'exports': [],
};

class PrivacyApi extends OfficeApi {
  PrivacyApi() : super(apiVersion: 'v1') {
    token = 'synthetic-private-case-token';
  }
  bool permission = true,
      finance = true,
      lose = false,
      foreignReceipt = false,
      sourceAccess = true;
  int generation = 1;
  final posts = <Map<String, dynamic>>[];
  final receipts = <String, Map<String, dynamic>>{};
  Map<String, dynamic> value = record();
  Completer<dynamic>? delayed;
  @override
  Future<dynamic> call(String path, [Map<String, dynamic>? body]) async {
    if (path == '/api/me') return {'id': actor, 'role': 'owner'};
    if (path.startsWith('/api/business/capabilities'))
      return {
        'compatibility_mode': 'business',
        'storage_version': 7,
        'generation': generation,
        'readonly': false,
        'features': ['privacy_cases'],
        'capabilities': ['business_privacy_cases'],
        'permissions': [
          if (permission) 'privacy.manage',
          'contacts.read',
          if (finance) 'finance.read',
        ],
      };
    if (body != null) {
      posts.add(copy(body));
      final key = '${body['request_id']}';
      if (!receipts.containsKey(key)) {
        value = {
          ...value,
          'revision': (value['revision'] as int) + 1,
          'status': 'verified',
          'identity': {'evidence': body['evidence']},
        };
        receipts[key] = {
          'case_id': caseId,
          'request_id': key,
          'confirmed': true,
          'operation': 'identity',
          'reference': {'case_id': caseId},
        };
      }
      if (delayed != null) return delayed!.future;
      if (lose) {
        lose = false;
        throw const ApiException(0, 'Synthetic lost reply');
      }
      return {'case': copy(value)};
    }
    if (path.contains('/commands/')) {
      final key = path.split('/').last;
      return {
        ...receipts[key] ?? {},
        if (foreignReceipt) 'request_id': 'f' * 32,
      };
    }
    if (path == '/api/business/privacy/cases')
      return {
        'items': [copy(value)],
      };
    if (path == '/api/business/privacy/cases/$caseId') {
      if (!sourceAccess) throw const ApiException(403, 'Source access revoked');
      return copy(value);
    }
    if (path == '/api/business/privacy/cases/options')
      return {
        'subjects': [
          {
            'kind': 'customer',
            'id': 'c' * 32,
            'label': 'Synthetic private case',
          },
        ],
        'handlers': [
          {'id': actor, 'email': 'handler@example.test'},
        ],
        'limited': false,
      };
    throw StateError(path);
  }
}

Future<BusinessSession> session(PrivacyApi api) async {
  final value = BusinessSession(api: api);
  await value.load();
  return value;
}

void main() {
  test(
    'current source ACL revocation clears an unresolved private payload',
    () async {
      final api = PrivacyApi()..lose = true,
          s = await session(api),
          command = PrivacyCommand(s);
      addTearDown(command.dispose);
      addTearDown(s.dispose);
      addTearDown(api.dispose);
      await expectLater(
        command.submit('/privacy/cases/$caseId/identity', {
          'revision': 1,
          'evidence': 'PRIVATE PROOF',
        }, caseId),
        throwsA(isA<ApiException>()),
      );
      api.sourceAccess = false;
      await expectLater(command.retry(), throwsA(isA<ApiException>()));
      expect(api.posts.length, 1);
      expect(command.pending, isNull);
    },
  );
  test('case and receipt validation bind identity and reject automatic completeness', () {
    privacyCase(record(), caseId);
    expect(
      () => privacyCase({...record(), 'automatic_completeness': true}, caseId),
      throwsA(isA<ApiException>()),
    );
    expect(
      () => privacyCase({...record(), 'id': 'f' * 32}, caseId),
      throwsA(isA<ApiException>()),
    );
    expect(
      () => privacyReceipt(
        {
          'case_id': caseId,
          'request_id': 'c' * 32,
          'confirmed': true,
          'operation': 'identity',
          'reference': {'case_id': 'f' * 32},
        },
        caseId,
        'c' * 32,
      ),
      throwsA(isA<ApiException>()),
    );
  });
  test(
    'lost response keeps exact private RAM command; status is read only',
    () async {
      final api = PrivacyApi()..lose = true,
          s = await session(api),
          command = PrivacyCommand(s);
      addTearDown(command.dispose);
      addTearDown(s.dispose);
      addTearDown(api.dispose);
      final body = {
        'revision': 1,
        'evidence': 'PRIVATE IDENTITY PROOF',
        'confirmed': true,
      };
      await expectLater(
        command.submit('/privacy/cases/$caseId/identity', body, caseId),
        throwsA(isA<ApiException>()),
      );
      body['evidence'] = 'changed after click';
      expect((await command.status())['confirmed'], true);
      expect(api.posts.length, 1);
      await command.retry();
      expect(api.posts[0], api.posts[1]);
      expect(api.posts[1]['evidence'], 'PRIVATE IDENTITY PROOF');
      expect(command.pending, isNull);
    },
  );
  test(
    'revoked permission or changed source grant clears before repeat',
    () async {
      final api = PrivacyApi()..lose = true,
          s = await session(api),
          command = PrivacyCommand(s);
      addTearDown(command.dispose);
      addTearDown(s.dispose);
      addTearDown(api.dispose);
      await expectLater(
        command.submit('/privacy/cases/$caseId/identity', {
          'revision': 1,
          'evidence': 'PRIVATE',
        }, caseId),
        throwsA(isA<ApiException>()),
      );
      api.finance = false;
      await expectLater(command.retry(), throwsA(isA<ApiException>()));
      expect(api.posts.length, 1);
      expect(command.pending, isNull);
    },
  );
  test(
    'closing while response is in flight cannot publish private result',
    () async {
      final api = PrivacyApi()..delayed = Completer<dynamic>(),
          s = await session(api),
          command = PrivacyCommand(s);
      addTearDown(command.dispose);
      addTearDown(s.dispose);
      addTearDown(api.dispose);
      final result = command.submit('/privacy/cases/$caseId/identity', {
        'revision': 1,
        'evidence': 'PRIVATE',
      }, caseId);
      while (api.posts.isEmpty) {
        await Future<void>.delayed(Duration.zero);
      }
      command.clear();
      api.delayed!.complete({'case': record()});
      await expectLater(result, throwsA(isA<ApiException>()));
      expect(command.pending, isNull);
    },
  );
  test('foreign receipt leaves original private request unresolved', () async {
    final api = PrivacyApi()..foreignReceipt = true,
        s = await session(api),
        command = PrivacyCommand(s);
    addTearDown(command.dispose);
    addTearDown(s.dispose);
    addTearDown(api.dispose);
    await expectLater(
      command.submit('/privacy/cases/$caseId/identity', {
        'revision': 1,
      }, caseId),
      throwsA(isA<ApiException>()),
    );
    expect(api.posts.length, 1);
    expect(command.pending, isNotNull);
    command.clear();
  });
  test('private ZIP download verifies bounded bytes and exact hash', () async {
    final bytes = Uint8List.fromList([
          80,
          75,
          3,
          4,
          ...utf8.encode('synthetic private export'),
        ]),
        digest = (await Sha256().hash(bytes)).bytes
            .map((v) => v.toRadixString(16).padLeft(2, '0'))
            .join();
    final value = await privacyArchiveAttachment(bytes, {
      'size': bytes.length,
      'sha256': digest,
    }, caseId);
    expect(value.bytes, bytes);
    await expectLater(
      privacyArchiveAttachment(bytes, {
        'size': bytes.length,
        'sha256': 'f' * 64,
      }, caseId),
      throwsA(isA<ApiException>()),
    );
  });
  testWidgets(
    'actual identity editor closes on success and private source rights revoke visible case',
    (tester) async {
      final api = PrivacyApi(), s = await session(api);
      addTearDown(api.dispose);
      await tester.pumpWidget(
        MaterialApp(home: BusinessPrivacyCasesPage(session: s)),
      );
      await tester.pumpAndSettle();
      await tester.tap(find.text('Synthetic private case'));
      await tester.pumpAndSettle();
      expect(find.text('PRIVATE REQUEST CONTENT'), findsOneWidget);
      await tester.ensureVisible(find.text('Identität prüfen'));
      await tester.tap(find.text('Identität prüfen'));
      await tester.pumpAndSettle();
      await tester.enterText(
        find.byType(TextFormField).first,
        'Synthetic independently checked identity',
      );
      await tester.tap(find.text('Identität wurde tatsächlich geprüft.'));
      await tester.tap(find.widgetWithText(FilledButton, 'Speichern'));
      await tester.pumpAndSettle();
      expect(api.posts.length, 1);
      expect(find.text('Identität dokumentieren'), findsNothing);
      expect(find.text('PRIVATE REQUEST CONTENT'), findsOneWidget);
      api.finance = false;
      await s.load();
      await tester.pumpAndSettle();
      expect(find.text('PRIVATE REQUEST CONTENT'), findsNothing);
      await tester.pumpWidget(const SizedBox());
      s.dispose();
    },
  );
  testWidgets(
    'backgrounding discards private visible case and pending response',
    (tester) async {
      final api = PrivacyApi(), s = await session(api);
      addTearDown(api.dispose);
      await tester.pumpWidget(
        MaterialApp(home: BusinessPrivacyCasesPage(session: s)),
      );
      await tester.pumpAndSettle();
      await tester.tap(find.text('Synthetic private case'));
      await tester.pumpAndSettle();
      tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.inactive);
      await tester.pumpAndSettle();
      expect(find.text('PRIVATE REQUEST CONTENT'), findsNothing);
      tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.resumed);
      await tester.pumpAndSettle();
      await tester.pumpWidget(const SizedBox());
      s.dispose();
    },
  );
}

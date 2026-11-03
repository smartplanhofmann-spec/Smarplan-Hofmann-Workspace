import 'dart:convert';
import 'dart:io';
import 'dart:typed_data';

import 'package:cryptography/cryptography.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:smartplan_office/api.dart';
import 'package:smartplan_office/business_company_handover.dart';
import 'package:smartplan_office/business_session.dart';

final f = jsonDecode(
  File('test/fixtures/company_handover.json').readAsStringSync(),
) as Map<String, dynamic>;
Map<String, dynamic> copy(dynamic v) =>
    Map<String, dynamic>.from(jsonDecode(jsonEncode(v)) as Map);

class HandoverApi extends OfficeApi {
  HandoverApi() : super(apiVersion: 'v1') {
    token = 'synthetic-handover-session';
  }
  String role = 'owner', instance = f['state']['instance_id'];
  bool lose = false, blocked = false;
  int generation = 1;
  final posts = <Map<String, dynamic>>[];
  @override
  Future<dynamic> call(String path, [Map<String, dynamic>? body]) async {
    if (path == '/api/me') return {'id': f['owner'], 'role': role};
    if (path.startsWith('/api/business/capabilities'))
      return {
        'compatibility_mode': 'business',
        'storage_version': 8,
        'generation': generation,
        'readonly': false,
        'capabilities': ['business_company_handover'],
        'features': ['company_handover'],
        'permissions': ['settings.manage'],
      };
    if (path == '/api/business/company-handover')
      return {
        ...copy(f['state']),
        'instance_id': instance,
        'ready': !blocked,
        'blockers': blocked
            ? [
                {
                  'code': 'catalog_review_required',
                  'message': 'Synthetic blocked catalog',
                },
              ]
            : [],
      };
    if (body != null) {
      posts.add(copy(body));
      if (lose) {
        lose = false;
        throw const ApiException(0, 'Synthetic lost ACK');
      }
      return path.endsWith('/exit-reviews')
          ? copy(f['review'])
          : copy(f['archive']);
    }
    throw StateError(path);
  }
}

Future<BusinessSession> session(HandoverApi api) async {
  final s = BusinessSession(api: api);
  await s.load();
  return s;
}

void main() {
  test(
    'full archive requires both explicit confirmations and ready catalog',
    () {
      final body = copy(f['body'])..remove('request_id');
      expect(handoverExportData(copy(f['state']), body), body);
      for (final key in ['confirmation', 'sensitive_data_confirmed'])
        expect(
          () => handoverExportData(copy(f['state']), {...body, key: false}),
          throwsA(isA<ApiException>()),
        );
      expect(
        () => handoverExportData({...copy(f['state']), 'ready': false}, body),
        throwsA(isA<ApiException>()),
      );
    },
  );
  test('unchecked review remains incomplete and binds exact archive and previous version', () {
    final b = handoverReviewData(copy(f['state']), copy(f['archive']), {
      ...copy(f['review_body']),
      ...copy(f['review_body']['checks']),
    });
    expect((b['checks'] as Map).values.every((v) => v == false), true);
    final validate = handoverValidator(b, review: true, actor: f['owner']);
    validate(f['review']);
    for (final change in [
      {'revision': 2},
      {'deletion_executed': true},
      {'revocations_executed': true},
      {'status': 'ready_for_operator_review'},
      {'export_sha256': 'f' * 64},
    ])
      expect(
        () => validate({...copy(f['review']), ...change}),
        throwsA(isA<ApiException>()),
      );
  });
  test(
    'receipt validator freezes original catalog, reason, actor and instance',
    () {
      final b = copy(f['body']),
          validate = handoverValidator(b, actor: f['owner']);
      b['reason'] = 'altered';
      validate(f['archive']);
      for (final k in ['reason', 'catalog_sha256', 'instance_id', 'created_by'])
        expect(
          () => validate({...copy(f['archive']), k: 'f' * 64}),
          throwsA(isA<ApiException>()),
        );
    },
  );
  test('fresh owner and instance required for identical retry; current blocked catalog does not lose accepted receipt', () async {
    final api = HandoverApi()..lose = true, s = await session(api);
    addTearDown(s.dispose);
    addTearDown(api.dispose);
    final body = copy(f['body'])..remove('request_id');
    await expectLater(
      s.command(
        'company-handover-export',
        '/company-handover/exports',
        body,
        validateResult: handoverValidator(body),
      ),
      throwsA(isA<ApiException>()),
    );
    api.role = 'office';
    await expectLater(
      s.repeatCompanyHandoverCommand(),
      throwsA(isA<ApiException>()),
    );
    expect(api.posts.length, 1);
    expect(s.pending('company-handover-export'), true);
    api.role = 'owner';
    api.instance = 'f' * 32;
    await expectLater(
      s.repeatCompanyHandoverCommand(),
      throwsA(isA<ApiException>()),
    );
    expect(api.posts.length, 1);
    api.instance = f['state']['instance_id'];
    api.blocked = true;
    await s.repeatCompanyHandoverCommand();
    expect(api.posts[0], api.posts[1]);
    expect(s.pending('company-handover-export'), false);
  });
  test(
    'review retry freezes the original checklist and new revision receipt',
    () async {
      final api = HandoverApi()..lose = true, s = await session(api);
      addTearDown(s.dispose);
      addTearDown(api.dispose);
      final body = copy(f['review_body'])..remove('request_id');
      await expectLater(
        s.command(
          'company-handover-review',
          '/company-handover/exit-reviews',
          body,
          validateResult: handoverValidator(body, review: true),
        ),
        throwsA(isA<ApiException>()),
      );
      (body['checks'] as Map)['export_opened'] = true;
      await s.repeatCompanyHandoverCommand(review: true);
      expect(api.posts[0], api.posts[1]);
      expect(api.posts[1]['checks']['export_opened'], false);
    },
  );
  test(
    'ZIP bytes require exact independent proof, hash, size and signature',
    () async {
      final bytes = Uint8List.fromList([80, 75, 3, 4, 1, 2, 3]),
          hash = (await Sha256().hash(bytes)).bytes
              .map((v) => v.toRadixString(16).padLeft(2, '0'))
              .join(),
          archive = {
            ...copy(f['archive']),
            'size': bytes.length,
            'sha256': hash,
          },
          proof = {...copy(f['proof']), 'sha256': hash};
      final file = await handoverArchiveAttachment(bytes, archive, proof);
      expect(file.filename, 'smartplan-company-${archive['id']}.zip');
      await expectLater(
        handoverArchiveAttachment(bytes, archive, {
          ...proof,
          'instance_id': 'f' * 32,
        }),
        throwsA(isA<ApiException>()),
      );
      await expectLater(
        handoverArchiveAttachment(
          Uint8List.fromList([80, 75, 3, 4, 4, 5, 6]),
          archive,
          proof,
        ),
        throwsA(isA<ApiException>()),
      );
    },
  );
  testWidgets(
    'native owner form starts every confirmation unchecked and displays no actual shutdown',
    (tester) async {
      tester.view.physicalSize = const Size(1200, 1200);
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.resetPhysicalSize);
      addTearDown(tester.view.resetDevicePixelRatio);
      final api = HandoverApi(), s = await session(api);
      await tester.pumpWidget(
        MaterialApp(home: BusinessCompanyHandoverPage(session: s)),
      );
      await tester.pumpAndSettle();
      expect(find.textContaining('widerruft keine Zugänge'), findsOneWidget);
      await tester.tap(find.text('Unternehmensarchiv erstellen'));
      await tester.pumpAndSettle();
      final switches = tester.widgetList<SwitchListTile>(
        find.byType(SwitchListTile),
      );
      expect(switches.length, 2);
      expect(switches.every((v) => v.value == false), true);
      expect(api.posts, isEmpty);
      await tester.pumpWidget(const SizedBox());
      s.dispose();
      api.dispose();
    },
  );
  testWidgets(
    'native non-owner cannot read sensitive inventory or create an export',
    (tester) async {
      final api = HandoverApi()..role = 'office', s = await session(api);
      await tester.pumpWidget(
        MaterialApp(home: BusinessCompanyHandoverPage(session: s)),
      );
      await tester.pumpAndSettle();
      expect(find.textContaining('aktuelle Geschäftsführung'), findsOneWidget);
      expect(find.text('Unternehmensarchiv erstellen'), findsNothing);
      expect(api.posts, isEmpty);
      await tester.pumpWidget(const SizedBox());
      s.dispose();
      api.dispose();
    },
  );
  testWidgets(
    'open sensitive inventory is cleared after the access generation changes',
    (tester) async {
      tester.view.physicalSize = const Size(1200, 1200);
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.resetPhysicalSize);
      addTearDown(tester.view.resetDevicePixelRatio);
      final api = HandoverApi(), s = await session(api);
      await tester.pumpWidget(
        MaterialApp(home: BusinessCompanyHandoverPage(session: s)),
      );
      await tester.pumpAndSettle();
      await tester.tap(find.text('Inventar und Auslassungen prüfen'));
      await tester.pumpAndSettle();
      expect(find.textContaining('users ·'), findsOneWidget);
      api.generation = 2;
      api.role = 'office';
      await s.load();
      await tester.pumpAndSettle();
      expect(find.textContaining('users ·'), findsNothing);
      expect(find.text('Zugang nicht mehr verfügbar.'), findsOneWidget);
      await tester.pumpWidget(const SizedBox());
      s.dispose();
      api.dispose();
    },
  );
}

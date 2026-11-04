import 'dart:async';
import 'dart:convert';
import 'dart:typed_data';

import 'package:file_selector/file_selector.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:smartplan_office/api.dart';
import 'package:smartplan_office/business_accounting_open_items.dart';
import 'package:smartplan_office/business_session.dart';
import 'package:smartplan_office/mail_attachment_widgets.dart';

import 'business_accounting_open_items_contract_test.dart'
    show openItemsFixture, openItemsBody;
import 'business_accounting_open_items_lifecycle_test.dart' as owner;

class IndependentOpenItemsApi extends owner.OpenItemsApi {
  IndependentOpenItemsApi({this.scenario = 'clerical_payment_correction'}) {
    stateName = 'review_state';
  }
  final String scenario;
  Completer<dynamic>? heldConfirm;
  Completer<Uint8List>? heldBytes;
  Map<String, dynamic>? alteredSource;
  int byteRequests = 0;
  bool feature = true;
  @override
  Map<String, dynamic> get f {
    final result = openItemCopy(openItemsFixture[scenario]);
    final state = openItemCopy(result['final_state']);
    if (scenario == 'clerical_payment_correction') {
      final payment = result['payments'][0]['payment'];
      state['revision'] = payment['sequence'];
      state['state_hash'] = openItemHash({
        'schema_version': 1,
        'revision': payment['sequence'],
        'head': payment['content_hash'],
      });
      state['payments'] = [payment];
      state['items'][0]['remaining'] = '59.50';
      state['items'][0]['remaining_net'] = '50.00';
      state['items'][0]['remaining_tax'] = '9.50';
    }
    result['review_state'] = state;
    return result;
  }

  @override
  Map<String, dynamic> capabilities() => {
    ...super.capabilities(),
    if (!feature) 'features': <String>[],
  };
  @override
  Future<dynamic> call(String path, [Map<String, dynamic>? body]) async {
    if (path.contains('$openItemPath/history?') && heldHistory == null) {
      final key = Uri.parse(path).queryParameters['entity_key'];
      if (key == f['item']['entity_key']) return openItemCopy(f['history']);
      final records = [
        for (final value in f['payments']) value['payment'],
        if (f['correction'] != null) ...[
          f['correction']['void'],
          f['correction']['payment'],
        ],
      ].where((value) => value['entity_key'] == key).toList();
      if (records.isNotEmpty) {
        return {'schema_version': 1, 'entity_key': key, 'items': records};
      }
    }
    if (body != null &&
        path.endsWith('$openItemPath/preview') &&
        scenario == 'clerical_payment_correction') {
      posts.add(openItemCopy(body));
      return heldPreview?.future ??
          openItemCopy(f['correction']['void_preview']);
    }
    if (body != null &&
        path.endsWith('$openItemPath/confirm') &&
        scenario == 'clerical_payment_correction') {
      posts.add(openItemCopy(body));
      return heldConfirm?.future ?? openItemCopy(f['correction']['void']);
    }
    if (path.contains('$openItemPath/payments/') && alteredSource != null)
      return openItemCopy(alteredSource);
    return super.call(path, body);
  }

  @override
  Future<Uint8List> bytes(
    String path, {
    String mediaType = 'application/pdf',
    int maxBytes = 10485760,
  }) async {
    byteRequests++;
    if (heldBytes != null) return heldBytes!.future;
    final id = path.split('/').last;
    final original = (f['originals'] as List).singleWhere(
      (v) => v['original_id'] == id,
    );
    return base64Decode(original['content_base64']);
  }
}

Future<void> visible(WidgetTester t, Finder finder) async {
  final scroll = find.byType(Scrollable).first;
  t.state<ScrollableState>(scroll).position.jumpTo(0);
  await t.pump();
  for (var attempt = 0; attempt < 70 && finder.evaluate().isEmpty; attempt++) {
    await t.drag(scroll, const Offset(0, -250));
    await t.pump();
  }
  expect(finder, findsWidgets);
  await t.ensureVisible(finder.first);
  await t.pumpAndSettle();
}

Future<void> tapKey(WidgetTester t, String key) async {
  final finder = find.byKey(ValueKey('opening-item-$key'));
  await visible(t, finder);
  await t.tap(finder);
  await t.pumpAndSettle();
}

Future<void> mount(
  WidgetTester t,
  IndependentOpenItemsApi api,
  BusinessSession s, {
  Future<XFile?> Function()? pickFile,
  Future<void> Function(VerifiedMailAttachment)? exportFile,
}) async {
  await s.load();
  await t.pumpWidget(
    MaterialApp(
      home: BusinessOpenItemsPage(
        session: s,
        entityKey: api.f['item']['entity_key'],
        pickFile: pickFile,
        exportFile: exportFile,
      ),
    ),
  );
  await t.pumpAndSettle();
  expect(find.textContaining('Synthetic counterparty'), findsOneWidget);
}

Future<void> voidDraft(WidgetTester t, IndependentOpenItemsApi api) async {
  await owner.oiTap(t, 'Fehlerhaften Zahlungsnachweis aufheben');
  await t.pumpAndSettle();
  await tapKey(t, 'void-confirmed');
  final reason = find.byKey(const ValueKey('opening-item-reason'));
  await visible(t, reason);
  await t.enterText(reason, api.f['correction']['void_preview']['reason']);
  await t.pump();
}

Future<BusinessSession?> changeContext(
  WidgetTester t,
  IndependentOpenItemsApi api,
  BusinessSession session,
  String kind,
) async {
  if (kind == 'session') {
    final replacement = BusinessSession(api: IndependentOpenItemsApi());
    await replacement.load();
    await t.pumpWidget(
      MaterialApp(
        home: BusinessOpenItemsPage(
          session: replacement,
          entityKey: api.f['item']['entity_key'],
        ),
      ),
    );
    await t.pumpAndSettle();
    return replacement;
  }
  if (kind == 'background') {
    t.binding.handleAppLifecycleStateChanged(AppLifecycleState.paused);
    await t.pump();
    t.binding.handleAppLifecycleStateChanged(AppLifecycleState.resumed);
    await t.pump();
  } else {
    if (kind == 'read') api.read = false;
    if (kind == 'write') api.write = false;
    if (kind == 'generation') api.generation++;
    if (kind == 'feature') api.feature = false;
    await session.load();
    await t.pump();
  }
  return null;
}

Future<void> disposeSessions(
  WidgetTester t,
  BusinessSession session,
  BusinessSession? other,
) async {
  await t.pumpWidget(const SizedBox.shrink());
  session.dispose();
  other?.dispose();
  expect(t.takeException(), null);
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  test(
    'reconstructed paid prefix contains exact original real fixture events',
    () {
      final api = IndependentOpenItemsApi();
      expect(openItemState(api.f['review_state']), api.f['review_state']);
      expect(
        api.f['review_state']['payments'][0],
        api.f['payments'][0]['payment'],
      );
    },
  );

  test('bound source cannot replace the actual payment bank with a different valid account', () {
    final f = openItemsFixture['receivable_prior_parts']['payments'][0];
    final source = openItemCopy(f['source']);
    source['cash_movements'][0]['account']['id'] = 'f' * 32;
    source['source_hash'] = openItemHash({...source}..remove('source_hash'));
    expect(
      () => openItemSource(source, payment: f['payment']),
      throwsA(isA<ApiException>()),
    );
  });

  test('old payment cents and exercised VAT dates reject independently rehashed contradictions', () {
    for (final scenario in [
      'receivable_prior_parts',
      'payable_old_input_vat',
    ]) {
      final original = openItemsFixture[scenario];
      final preview = openItemCopy(original['item_preview']);
      final body = openItemsBody(original['item_command']);
      if (scenario == 'receivable_prior_parts') {
        preview['payload']['prior_payments'][0]['tax'] = '6.34';
        preview['payload']['prior_payments'][0]['net'] = '33.33';
      } else {
        preview['payload']['prior_input_vat']['deducted_on'] =
            preview['profile']['profile']['bookkeeping_start'];
      }
      body['payload'] = openItemCopy(preview['payload']);
      preview['preview_hash'] = openItemHash(
        {...preview}..remove('preview_hash'),
      );
      expect(
        () => openItemPreview(preview, body),
        throwsA(isA<ApiException>()),
      );
    }
  });

  testWidgets(
    'source display cannot replace the selected old VAT exercise date with a self-rehashed value',
    (t) async {
      final api = IndependentOpenItemsApi(scenario: 'payable_old_input_vat');
      final s = BusinessSession(api: api);
      api.alteredSource = openItemCopy(api.f['payments'][0]['source']);
      api.alteredSource!['prior_input_vat']['deducted_on'] = '2025-12-11';
      api.alteredSource!['source_hash'] = openItemHash(
        {...api.alteredSource!}..remove('source_hash'),
      );
      await mount(t, api, s);
      await owner.oiTap(t, 'Zahlungsquelle und EÜR-Zuordnung');
      await t.pumpAndSettle();
      expect(find.text('Originalgebundene Geld-/EÜR-Quelle'), findsNothing);
      expect(
        find.textContaining('ursprüngliche Rechnung oder frühere Vorsteuer'),
        findsOneWidget,
      );
      await owner.oiClose(t, s);
    },
  );

  test('verified real sources preserve exact payment bank and original earlier VAT in both directions', () async {
    for (final scenario in [
      'receivable_prior_parts',
      'payable_old_input_vat',
    ]) {
      final api = IndependentOpenItemsApi(scenario: scenario);
      final s = BusinessSession(api: api);
      try {
        await s.load();
        final expected = api.f['payments'][0]['source'];
        final verified = await openItemVerifiedSource(s, expected);
        expect(verified, expected);
        expect(
          verified['cash_movements'][0]['account'],
          api.f['payments'][0]['payment']['details']['account'],
        );
        expect(
          verified['prior_input_vat'],
          api.f['item']['payload']['prior_input_vat'],
        );
      } finally {
        s.dispose();
      }
    }
  });

  testWidgets(
    'valid old supplier VAT display keeps zero new deduction and exact original source',
    (t) async {
      final api = IndependentOpenItemsApi(scenario: 'payable_old_input_vat');
      final s = BusinessSession(api: api);
      await mount(t, api, s);
      await owner.oiTap(t, 'Zahlungsquelle und EÜR-Zuordnung');
      await t.pumpAndSettle();
      await visible(t, find.text('Originalgebundene Geld-/EÜR-Quelle'));
      expect(
        find.textContaining('neuer Vorsteuerabzug: 0,00 €.'),
        findsOneWidget,
      );
      expect(
        find.textContaining('ursprüngliche Rechnung oder frühere Vorsteuer'),
        findsNothing,
      );
      expect(api.posts, isEmpty);
      await owner.oiClose(t, s);
    },
  );

  for (final length in [0, 5242881]) {
    testWidgets(
      'selected original of $length bytes is rejected before upload',
      (t) async {
        final api = IndependentOpenItemsApi();
        final s = BusinessSession(api: api);
        await mount(
          t,
          api,
          s,
          pickFile: () async =>
              XFile.fromData(Uint8List(length), name: 'synthetic.pdf'),
        );
        await owner.oiTap(t, 'Originaldatei unverändert hochladen');
        await t.pumpAndSettle();
        expect(api.posts, isEmpty);
        expect(find.textContaining('1 Byte bis 5 MiB'), findsOneWidget);
        await owner.oiClose(t, s);
      },
    );
  }

  for (final contextChange in [
    'read',
    'write',
    'generation',
    'feature',
    'background',
    'session',
  ]) {
    testWidgets(
      'held real void preview is discarded after $contextChange change',
      (t) async {
        final api = IndependentOpenItemsApi();
        final session = BusinessSession(api: api);
        await mount(t, api, session);
        await voidDraft(t, api);
        api.heldPreview = Completer<dynamic>();
        await owner.oiTap(t, 'Verbindliche Vorschau prüfen');
        expect(
          api.posts.single,
          openItemsBody(api.f['correction']['void_command']),
        );
        final other = await changeContext(t, api, session, contextChange);
        api.heldPreview!.complete(
          openItemCopy(api.f['correction']['void_preview']),
        );
        await t.pumpAndSettle();
        expect(find.text('Unveränderte Servervorschau'), findsNothing);
        expect(
          find.byKey(const ValueKey('opening-item-void-confirmed')),
          findsNothing,
        );
        expect(api.posts.length, 1);
        await disposeSessions(t, session, other);
      },
    );
  }

  for (final contextChange in ['background', 'session', 'write']) {
    for (final failure in [false, true]) {
      testWidgets(
        'late real void ${failure ? 'error' : 'ACK'} after $contextChange remains owned by original session',
        (t) async {
          final api = IndependentOpenItemsApi();
          final session = BusinessSession(api: api);
          await mount(t, api, session);
          await voidDraft(t, api);
          await owner.oiTap(t, 'Verbindliche Vorschau prüfen');
          await t.pumpAndSettle();
          expect(find.text('Unveränderte Servervorschau'), findsOneWidget);
          await tapKey(t, 'accept');
          api.heldConfirm = Completer<dynamic>();
          await owner.oiTap(t, 'Unverändert verbindlich bestätigen');
          final key =
              'opening-item-confirm-${api.f['correction']['void']['entity_key']}';
          expect(session.pendingOpenItemKeys, [key]);
          final frozen = openItemCopy(api.posts.last);
          final other = await changeContext(t, api, session, contextChange);
          if (other != null) {
            await owner.oiTap(
              t,
              'Übernahme berichtigen / Profil erneut prüfen',
            );
            await t.pumpAndSettle();
            final field = find.byKey(
              const ValueKey('opening-item-counterparty_name'),
            );
            await visible(t, field);
            await t.enterText(field, 'Private replacement editor remains');
            await t.pump();
          }
          if (failure) {
            api.heldConfirm!.completeError(
              const ApiException(503, 'Private old correction ACK error'),
            );
          } else {
            api.heldConfirm!.complete(
              openItemCopy(api.f['correction']['void']),
            );
          }
          await t.pumpAndSettle();
          expect(
            find.textContaining('Private old correction ACK'),
            findsNothing,
          );
          expect(find.text('Unveränderte Servervorschau'), findsNothing);
          expect(api.posts.last, frozen);
          expect(api.posts.length, 2);
          expect(session.pendingOpenItemKeys, failure ? [key] : isEmpty);
          if (other != null) {
            expect(
              find.text('Private replacement editor remains'),
              findsOneWidget,
            );
            expect(other.pendingOpenItemKeys, isEmpty);
            api.read = false;
            await session.load();
            await t.pumpAndSettle();
            expect(
              find.text('Private replacement editor remains'),
              findsOneWidget,
            );
          }
          await disposeSessions(t, session, other);
        },
      );
    }
  }

  for (final contextChange in ['read', 'background', 'session']) {
    testWidgets(
      'late original bytes cannot export after $contextChange change',
      (t) async {
        final api = IndependentOpenItemsApi(),
            saved = <VerifiedMailAttachment>[];
        final session = BusinessSession(api: api);
        api.heldBytes = Completer<Uint8List>();
        await mount(t, api, session, exportFile: (f) async => saved.add(f));
        final original = api.f['review_state']['originals'][0];
        final metadata = (api.f['originals'] as List).singleWhere(
          (v) => v['original_id'] == original['id'],
        );
        await visible(t, find.byType(ListTile));
        await t.tap(find.byType(ListTile).first);
        await t.pump();
        expect(api.byteRequests, 1);
        final other = await changeContext(t, api, session, contextChange);
        api.heldBytes!.complete(base64Decode(metadata['content_base64']));
        await t.pumpAndSettle();
        expect(saved, isEmpty);
        expect(api.posts, isEmpty);
        await disposeSessions(t, session, other);
      },
    );
  }

  testWidgets(
    'download rejects equal-size altered original bytes before file export',
    (t) async {
      final api = IndependentOpenItemsApi(), saved = <VerifiedMailAttachment>[];
      final s = BusinessSession(api: api);
      api.heldBytes = Completer<Uint8List>();
      await mount(t, api, s, exportFile: (f) async => saved.add(f));
      final original = api.f['review_state']['originals'][0];
      final metadata = (api.f['originals'] as List).singleWhere(
        (v) => v['original_id'] == original['id'],
      );
      await visible(t, find.byType(ListTile));
      await t.tap(find.byType(ListTile).first);
      await t.pump();
      final altered = base64Decode(metadata['content_base64']);
      altered[0] ^= 1;
      api.heldBytes!.complete(altered);
      await t.pumpAndSettle();
      expect(saved, isEmpty);
      expect(
        find.textContaining('Originalbytes stimmen nicht'),
        findsOneWidget,
      );
      await owner.oiClose(t, s);
    },
  );

  testWidgets(
    'picker returning original after write withdrawal creates no upload or pending command',
    (t) async {
      final api = IndependentOpenItemsApi();
      final s = BusinessSession(api: api), picker = Completer<XFile?>();
      await mount(t, api, s, pickFile: () => picker.future);
      await owner.oiTap(t, 'Originaldatei unverändert hochladen');
      api.write = false;
      await s.load();
      picker.complete(
        XFile.fromData(
          Uint8List.fromList(utf8.encode('%PDF-1.4 synthetic original')),
          name: 'synthetic.pdf',
        ),
      );
      await t.pumpAndSettle();
      expect(api.posts, isEmpty);
      expect(s.pendingOpenItemKeys, isEmpty);
      await owner.oiClose(t, s);
    },
  );
}

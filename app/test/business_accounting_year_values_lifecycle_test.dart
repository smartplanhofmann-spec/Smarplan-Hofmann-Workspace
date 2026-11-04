import 'dart:async';
import 'dart:typed_data';
import 'dart:convert';
import 'dart:io';

import 'package:file_selector_platform_interface/file_selector_platform_interface.dart';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:smartplan_office/api.dart';
import 'package:smartplan_office/business_session.dart';
import 'package:smartplan_office/business_accounting_year_values.dart';
import 'package:smartplan_office/business_accounting_open_items_contract.dart';

import 'business_accounting_year_values_test.dart' show yearValuesFixture;

class YearValuesApi extends OfficeApi {
  YearValuesApi({Map<String, dynamic>? fixture})
    : f = fixture ?? yearValuesFixture()['complete'],
      super(apiVersion: 'v1') {
    token = 'synthetic-year-values';
  }
  final Map<String, dynamic> f;
  bool read = true,
      write = true,
      enabled = true,
      lose = false,
      foreign = false,
      accepted = false;
  int generation = 1, byteReads = 0;
  bool denyOriginal = false;
  Completer<dynamic>? heldState,
      heldHistory,
      heldPreview,
      heldConfirm,
      heldCaps;
  Completer<Uint8List>? heldBytes;
  final calls = <({String path, Map<String, dynamic>? body})>[];
  Map<String, dynamic> get state =>
      openItemCopy(f[accepted ? 'state_after_acceptance' : 'initial_state']);
  Map<String, dynamic> get openingState {
    final item = openItemCopy(f['old_item']);
    return {
      for (final k in [
        'schema_version',
        'rule_version',
        'invoice_created',
        'opening_cash_flow_created',
        'opening_tax_postings_created',
        'balance_timing',
        'timezone',
        'profile',
        'profile_ref',
      ])
        k: item[k],
      'revision': 1,
      'state_hash': openItemHash({
        'schema_version': 1,
        'revision': 1,
        'head': item['content_hash'],
      }),
      'items': [
        {
          ...item,
          'remaining': item['details']['opening_remaining'],
          'remaining_net': item['details']['opening_remaining_net'],
          'remaining_tax': item['details']['opening_remaining_tax'],
        },
      ],
      'payments': [],
      'originals': {for (final p in item['proofs']) p['id']: p}.values.toList(),
      'can_prepare': true,
      'max_original_bytes': 5242880,
    };
  }

  @override
  Future<dynamic> call(String path, [Map<String, dynamic>? body]) async {
    calls.add((path: path, body: body == null ? null : openItemCopy(body)));
    if (path.endsWith('/capabilities')) {
      if (heldCaps != null) return heldCaps!.future;
      return caps;
    }
    if (!read) throw const ApiException(403, 'Synthetic year source denied');
    if (path.endsWith('/year-values')) return heldState?.future ?? state;
    if (path.endsWith('/open-items')) return openingState;
    if (path.contains('/open-items/history'))
      return {
        'schema_version': 1,
        'entity_key': f['old_item']['entity_key'],
        'items': [openItemCopy(f['old_item'])],
      };
    if (path.contains('/year-values/history'))
      return heldHistory?.future ?? openItemCopy(f['history']);
    if (path.contains('/year-values/years/')) return openItemCopy(f['source']);
    if (path.endsWith('/year-values/preview'))
      return heldPreview?.future ?? openItemCopy(f['preview']);
    if (path.endsWith('/year-values/confirm')) {
      accepted = true;
      if (heldConfirm != null) return heldConfirm!.future;
      if (lose) {
        lose = false;
        throw const ApiException(0, 'Synthetic lost accepted reply');
      }
      return openItemCopy(
        foreign ? yearValuesFixture()['closed_trade']['entry'] : f['entry'],
      );
    }
    throw StateError('Unexpected year path $path');
  }

  Map<String, dynamic> get caps => {
    'compatibility_mode': 'business',
    'generation': generation,
    'storage_version': 16,
    'readonly': false,
    'features': [
      'accounting_year_values',
      'accounting_open_items',
      'organization_modules',
    ],
    'capabilities': [
      'business_accounting_year_openings',
      'business_accounting_open_items',
    ],
    'permissions': [
      'accounting.read',
      if (read) 'finance.read',
      if (write) ...['accounting.admin', 'accounting.prepare', 'finance.write'],
    ],
    'organization': {
      'revision': 1,
      'configured': true,
      'modules': {
        for (final s in BusinessSession.organizationSections)
          s: {'visible': true, 'enabled': s == 'finance' ? enabled : true},
      },
    },
  };
  @override
  Future<Uint8List> bytes(
    String path, {
    required String mediaType,
    int maxBytes = 20 * 1024 * 1024,
  }) async {
    byteReads++;
    if (denyOriginal)
      throw const ApiException(
        403,
        'Synthetic individual year original revoked',
      );
    if (heldBytes != null) return heldBytes!.future;
    final originals = f['originals'] as List;
    final found = originals
        .where((v) => path.endsWith('/${v['original_id']}'))
        .first;
    return base64Decode(found['content_base64']);
  }
}

class YearValuesSavePicker extends FileSelectorPlatform {
  final answer = Completer<FileSaveLocation?>();
  int calls = 0;
  @override
  Future<FileSaveLocation?> getSaveLocation({
    List<XTypeGroup>? acceptedTypeGroups,
    SaveDialogOptions options = const SaveDialogOptions(),
  }) {
    calls++;
    return answer.future;
  }
}

Future<void> yvTap(WidgetTester t, String label, {bool settle = true}) async {
  final f = find.text(label);
  final scroll = find.byType(Scrollable).first;
  t.state<ScrollableState>(scroll).position.jumpTo(0);
  await t.pump();
  await t.scrollUntilVisible(f, 300, scrollable: scroll, maxScrolls: 70);
  await Scrollable.ensureVisible(t.element(f.first), alignment: 0.35);
  await t.pumpAndSettle();
  await t.tap(f.first);
  await t.pump();
  if (settle) await t.pumpAndSettle();
}

final _mountedSessions = <BusinessSession>[];
final _mountedApis = <YearValuesApi>[];
void yearWidget(String name, Future<void> Function(WidgetTester) action) =>
    testWidgets(name, (t) async {
      try {
        await action(t);
      } finally {
        await t.pumpWidget(const SizedBox());
        for (final s in _mountedSessions) {
          s.dispose();
        }
        for (final a in _mountedApis) {
          a.dispose();
        }
        _mountedSessions.clear();
        _mountedApis.clear();
      }
    });
Future<BusinessSession> yvMount(WidgetTester t, YearValuesApi api) async {
  final s = BusinessSession(api: api);
  await s.load();
  await t.pumpWidget(MaterialApp(home: BusinessYearValuesPage(session: s)));
  await t.pumpAndSettle();
  _mountedSessions.add(s);
  _mountedApis.add(api);
  return s;
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  test('unknown acceptance repeats original nonce and frozen receipt after newer state', () async {
    final api = YearValuesApi()..lose = true, s = BusinessSession(api: api);
    addTearDown(s.dispose);
    addTearDown(api.dispose);
    await s.load();
    final b = openItemCopy(api.f['command'])..remove('request_id'),
        key = 'accounting-year-values-confirm-2026';
    await expectLater(
      s.yearValuesCommand(
        key,
        '$yearValuesPath/confirm',
        b,
        validateResult: yearValuesReceipt(
          b,
          openItemCopy(api.f['preview']),
          api.state,
        ),
      ),
      throwsA(isA<ApiException>()),
    );
    expect(s.pending(key), true);
    b['reason'] = 'changed local draft';
    await s.repeatYearValuesCommand(key);
    final commands = api.calls
        .where((e) => e.path.endsWith('/confirm'))
        .toList();
    expect(commands.length, 2);
    expect(commands[0].body, commands[1].body);
    expect(s.pending(key), false);
  });
  test('foreign valid acceptance cannot clear original pending', () async {
    final api = YearValuesApi()..foreign = true, s = BusinessSession(api: api);
    addTearDown(s.dispose);
    addTearDown(api.dispose);
    await s.load();
    final b = openItemCopy(api.f['command'])..remove('request_id'),
        key = 'accounting-year-values-confirm-2026';
    await expectLater(
      s.yearValuesCommand(
        key,
        '$yearValuesPath/confirm',
        b,
        validateResult: yearValuesReceipt(
          b,
          openItemCopy(api.f['preview']),
          api.state,
        ),
      ),
      throwsA(isA<ApiException>()),
    );
    expect(s.pending(key), true);
  });
  test(
    'held capability preflight cannot send after editor context ended',
    () async {
      final api = YearValuesApi(), s = BusinessSession(api: api);
      addTearDown(s.dispose);
      addTearDown(api.dispose);
      await s.load();
      api.heldCaps = Completer();
      var current = true;
      final b = openItemCopy(api.f['command'])..remove('request_id');
      final result = s.yearValuesCommand(
        'accounting-year-values-confirm-2026',
        '$yearValuesPath/confirm',
        b,
        stillCurrent: () => current,
      );
      final expected = expectLater(result, throwsA(isA<ApiException>()));
      current = false;
      api.heldCaps!.complete(api.caps);
      await expected;
      expect(api.calls.where((e) => e.path.endsWith('/confirm')), isEmpty);
    },
  );
  yearWidget('390px original year state history and no invented cash', (
    t,
  ) async {
    t.view.physicalSize = const Size(390, 844);
    t.view.devicePixelRatio = 1;
    addTearDown(t.view.resetPhysicalSize);
    addTearDown(t.view.resetDevicePixelRatio);
    final api = YearValuesApi()..accepted = true;
    await yvMount(t, api);
    expect(find.textContaining('Die Zeitraumdeckung beruht'), findsOneWidget);
    await yvTap(t, 'Ursprüngliche Jahresfassungen');
    await yvTap(t, 'Ursprüngliche Fassung 1 · Aktiv');
    await yvTap(t, 'Diese ursprüngliche Quelle prüfen');
    await t.scrollUntilVisible(
      find.text('Originalgebundene Jahres-/EÜR-Quelle'),
      250,
      scrollable: find.byType(Scrollable).first,
      maxScrolls: 80,
    );
    expect(find.text('Originalgebundene Jahres-/EÜR-Quelle'), findsOneWidget);
    expect(t.takeException(), null);
  });
  for (final change in ['rights', 'generation', 'background'])
    yearWidget('held original history discarded after $change', (t) async {
      final api = YearValuesApi()..accepted = true;
      final s = await yvMount(t, api);
      api.heldHistory = Completer();
      await yvTap(t, 'Ursprüngliche Jahresfassungen', settle: false);
      if (change == 'rights') {
        api.read = false;
      } else if (change == 'generation') {
        api.generation++;
        await s.load();
      } else {
        t.binding.handleAppLifecycleStateChanged(AppLifecycleState.paused);
        await t.pump();
      }
      api.heldHistory!.complete(openItemCopy(api.f['history']));
      await t.pumpAndSettle();
      expect(find.textContaining('Ursprüngliche Fassung 1'), findsNothing);
      expect(find.text(api.f['entry']['content_hash']), findsNothing);
      if (change == 'background')
        t.binding.handleAppLifecycleStateChanged(AppLifecycleState.resumed);
      expect(t.takeException(), null);
    });
  yearWidget(
    'new editor has empty dates accounts and controls without inferred zero',
    (t) async {
      final api = YearValuesApi();
      await yvMount(t, api);
      await yvTap(t, 'Jahresvortrag vorbereiten');
      expect(
        t
            .widget<TextField>(find.byKey(const ValueKey('year-values-from')))
            .controller!
            .text,
        isEmpty,
      );
      await t.scrollUntilVisible(
        find.byKey(const ValueKey('year-values-through')),
        200,
        scrollable: find.byType(Scrollable).first,
      );
      expect(
        t
            .widget<TextField>(
              find.byKey(const ValueKey('year-values-through')),
            )
            .controller!
            .text,
        isEmpty,
      );
      expect(find.byKey(const ValueKey('year-values-through')), findsOneWidget);
      expect(api.calls.where((e) => e.path.endsWith('/preview')), isEmpty);
      expect(t.takeException(), null);
    },
  );
  yearWidget(
    'write revoke clears populated annual editor without hiding readable history',
    (t) async {
      final api = YearValuesApi();
      final s = await yvMount(t, api);
      await yvTap(t, 'Jahresvortrag vorbereiten');
      await t.enterText(
        find.byKey(const ValueKey('year-values-from')),
        '2026-01-01',
      );
      api.write = false;
      await s.load();
      await t.pumpAndSettle();
      expect(find.byKey(const ValueKey('year-values-from')), findsNothing);
      expect(
        find.textContaining('Bestätigter Softwarebeginn:'),
        findsOneWidget,
      );
    },
  );
  yearWidget('old initial state error after session replacement stays hidden', (
    t,
  ) async {
    final api = YearValuesApi(), s = BusinessSession(api: api);
    await s.load();
    api.heldState = Completer();
    await t.pumpWidget(MaterialApp(home: BusinessYearValuesPage(session: s)));
    await t.pump();
    final newer = YearValuesApi()..accepted = true,
        n = BusinessSession(api: newer);
    await n.load();
    await t.pumpWidget(MaterialApp(home: BusinessYearValuesPage(session: n)));
    await t.pumpAndSettle();
    api.heldState!.completeError(
      const ApiException(403, 'Old private annual reason'),
    );
    await t.pumpAndSettle();
    expect(find.text('Old private annual reason'), findsNothing);
    await t.scrollUntilVisible(
      find.textContaining('Jahr 2026 · Fassung 1'),
      250,
      scrollable: find.byType(Scrollable).first,
    );
    expect(find.textContaining('Jahr 2026 · Fassung 1'), findsOneWidget);
    await t.pumpWidget(const SizedBox());
    s.dispose();
    n.dispose();
    api.dispose();
    newer.dispose();
  });
  for (final change in ['rights', 'generation', 'background'])
    yearWidget('held actual preview cannot display after $change', (t) async {
      final api = YearValuesApi(), session = await yvMount(t, api);
      await yvTap(t, 'Jahresvortrag vorbereiten');
      final dynamic page = t.state(find.byType(BusinessYearValuesPage));
      final payload = api.f['command']['payload'];
      page.sources = businessItems(
        openItemCopy({'items': payload['sources']})['items'],
      );
      page.controls = businessItems(
        openItemCopy({'items': payload['controls']})['items'],
      );
      page.c('from').text = payload['coverage']['from'];
      page.c('through').text = payload['coverage']['through'];
      page.ledgerProof = payload['ledger_proof']['original_id'];
      page.continuous = true;
      page.journalComplete = true;
      page.supported = true;
      page.c('reason').text = api.f['command']['reason'];
      api.heldPreview = Completer();
      final Future<void> pending = page.prepare();
      for (var i = 0; i < 8; i++) {
        await t.pump();
      }
      expect(api.calls.where((v) => v.path.endsWith('/preview')), hasLength(1));
      if (change == 'rights') {
        api.write = false;
      } else if (change == 'generation') {
        api.generation++;
        await session.load();
      } else {
        t.binding.handleAppLifecycleStateChanged(AppLifecycleState.paused);
        await t.pump();
      }
      api.heldPreview!.complete(openItemCopy(api.f['preview']));
      await pending;
      await t.pumpAndSettle();
      expect(
        find.text(
          'Genau diese ursprünglichen Werte und Nachweise verbindlich bestätigen',
        ),
        findsNothing,
      );
      expect(api.calls.where((v) => v.path.endsWith('/confirm')), isEmpty);
      if (change == 'background')
        t.binding.handleAppLifecycleStateChanged(AppLifecycleState.resumed);
    });
  for (final change in ['generation', 'background'])
    yearWidget(
      'late actual accepted reply cannot restore changed $change editor',
      (t) async {
        final api = YearValuesApi(), session = await yvMount(t, api);
        await yvTap(t, 'Jahresvortrag vorbereiten');
        final dynamic page = t.state(find.byType(BusinessYearValuesPage));
        page.preview = openItemCopy(api.f['preview']);
        page.body = {for (final k in yearValuesInput) k: api.f['command'][k]};
        page.accepted = true;
        api.heldConfirm = Completer();
        final Future<void> pending = page.confirm();
        for (var i = 0; i < 8; i++) {
          await t.pump();
        }
        expect(
          api.calls.where((v) => v.path.endsWith('/confirm')),
          hasLength(1),
        );
        if (change == 'generation') {
          api.generation++;
          await session.load();
        } else {
          t.binding.handleAppLifecycleStateChanged(AppLifecycleState.paused);
          await t.pump();
        }
        api.heldConfirm!.complete(openItemCopy(api.f['entry']));
        await pending;
        await t.pumpAndSettle();
        expect(
          find.textContaining('Ursprüngliche Jahresfassung angenommen'),
          findsNothing,
        );
        expect(find.byKey(const ValueKey('year-values-from')), findsNothing);
        if (change == 'background')
          t.binding.handleAppLifecycleStateChanged(AppLifecycleState.resumed);
      },
    );
  for (final revoke in [false, true])
    yearWidget(
      'actual desktop original output rechecks individual source after picker revoke=$revoke',
      (t) async {
        final previous = FileSelectorPlatform.instance,
            picker = YearValuesSavePicker();
        FileSelectorPlatform.instance = picker;
        final temp = Directory.systemTemp.createTempSync(
              'year-values-native-save-',
            ),
            output = File('${temp.path}/original.pdf');
        try {
          final api = YearValuesApi();
          await yvMount(t, api);
          await yvTap(t, 'Geschützte Jahresoriginale (1)');
          await yvTap(t, 'historical.pdf', settle: false);
          for (var i = 0; i < 8; i++) {
            await t.pump();
          }
          expect(picker.calls, 1);
          api.denyOriginal = revoke;
          picker.answer.complete(FileSaveLocation(output.path));
          for (var i = 0; i < 35; i++) {
            await t.runAsync(
              () => Future<void>.delayed(const Duration(milliseconds: 8)),
            );
            await t.pump(const Duration(milliseconds: 10));
          }
          await t.pumpAndSettle();
          expect(api.read, true);
          expect(api.byteReads, 2);
          expect(output.existsSync(), !revoke);
          if (!revoke) {
            expect(
              output.readAsBytesSync(),
              base64Decode(api.f['originals'][0]['content_base64']),
            );
          } else {
            expect(find.text('historical.pdf'), findsNothing);
          }
        } finally {
          FileSelectorPlatform.instance = previous;
          temp.deleteSync(recursive: true);
        }
      },
    );
  final boundaries = jsonDecode(
    File('test/fixtures/accounting_year_values_native_boundaries_v1.json')
        .readAsStringSync(),
  );
  for (final name in ['missing_start', 'missing_vat_timing']) {
    final b = businessMap(boundaries[name]);
    Map<String, dynamic> scenario() => {
      ...b,
      'initial_state': b['before'],
      'state_after_acceptance': b['state'],
    };
    test(
      'actual $name profile keeps immutable accepted replay despite today incomplete profile',
      () async {
        final api = YearValuesApi(fixture: scenario())..lose = true,
            s = BusinessSession(api: api);
        addTearDown(s.dispose);
        addTearDown(api.dispose);
        await s.load();
        final state = yearValuesState(b['state']);
        expect(yearValuesConfigured(state), false);
        final body = openItemCopy(b['command'])..remove('request_id'),
            key = 'accounting-year-values-confirm-2026';
        await expectLater(
          s.yearValuesCommand(
            key,
            '$yearValuesPath/confirm',
            body,
            validateResult: yearValuesReceipt(
              body,
              openItemCopy(b['preview']),
              openItemCopy(b['before']),
            ),
          ),
          throwsA(isA<ApiException>()),
        );
        await s.repeatYearValuesCommand(key);
        expect(s.pending(key), false);
        final commands = api.calls
            .where((c) => c.path.endsWith('/confirm'))
            .toList();
        expect(commands[0].body, commands[1].body);
      },
    );
    yearWidget(
      'actual $name profile preserves readable original annual history with new editor disabled',
      (t) async {
        final api = YearValuesApi(fixture: scenario())..accepted = true;
        await yvMount(t, api);
        await yvTap(t, 'Ursprüngliche Jahresfassungen');
        await yvTap(t, 'Ursprüngliche Fassung 1 · Aktiv');
        expect(api.calls.where((c) => c.path.endsWith('/preview')), isEmpty);
        await t.scrollUntilVisible(
          find.text('Jahresvortrag vorbereiten'),
          -250,
          scrollable: find.byType(Scrollable).first,
          maxScrolls: 80,
        );
        expect(
          t
              .widget<TextButton>(
                find.ancestor(
                  of: find.text('Jahresvortrag vorbereiten'),
                  matching: find.byType(TextButton),
                ),
              )
              .onPressed,
          isNull,
        );
      },
    );
  }
}

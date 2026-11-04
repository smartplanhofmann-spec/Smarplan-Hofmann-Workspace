import 'dart:convert';
import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:file_selector_platform_interface/file_selector_platform_interface.dart';
import 'package:smartplan_office/business_accounting_year_values.dart';
import 'package:smartplan_office/business_accounting_open_items_contract.dart';
import 'package:smartplan_office/business_session.dart';
import 'package:smartplan_office/business_widgets.dart';

import 'business_accounting_year_values_lifecycle_test.dart'
    show YearValuesApi, YearValuesSavePicker, yvTap;
import 'business_accounting_year_values_test.dart' show yearValuesFixture;

Map<String, dynamic> reviewBody(Map<String, dynamic> value) => {
  for (final key in yearValuesInput) key: value[key],
};
void rehashPreview(Map<String, dynamic> value) {
  value.remove('preview_hash');
  value['preview_hash'] = openItemHash(value);
}

void reviewPause(WidgetTester t) {
  for (final state in [
    AppLifecycleState.inactive,
    AppLifecycleState.hidden,
    AppLifecycleState.paused,
  ]) {
    t.binding.handleAppLifecycleStateChanged(state);
  }
}

void reviewResume(WidgetTester t) {
  for (final state in [
    AppLifecycleState.hidden,
    AppLifecycleState.inactive,
    AppLifecycleState.resumed,
  ]) {
    t.binding.handleAppLifecycleStateChanged(state);
  }
}

class CrossedYearHistoryApi extends YearValuesApi {
  @override
  Future<dynamic> call(String path, [Map<String, dynamic>? body]) {
    if (path.contains('/open-items/history')) {
      return Future.value({
        'schema_version': 1,
        'entity_key': f['old_item']['entity_key'],
        'items': [
          openItemCopy(yearValuesFixture()['closed_trade']['old_item']),
        ],
      });
    }
    return super.call(path, body);
  }
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  final complete = yearValuesFixture()['complete'];
  final independent = jsonDecode(
    File('test/fixtures/accounting_year_values_native_independent_v1.json')
        .readAsStringSync(),
  ) as Map<String, dynamic>;
  final boundaries = jsonDecode(
    File('test/fixtures/accounting_year_values_native_boundaries_v1.json')
        .readAsStringSync(),
  ) as Map<String, dynamic>;
  for (final name in ['missing_start', 'missing_vat_timing']) {
    test(
      'independent actual $name preserves readable original history and receipt',
      () {
        final b = openItemCopy(boundaries[name]);
        final state = yearValuesState(b['state']);
        expect(yearValuesConfigured(state), false);
        expect(state['items'], isNotEmpty);
        expect(state['can_prepare'], name == 'missing_vat_timing');
        yearValuesReceipt(b['command'], b['preview'], b['before'])(b['replay']);
        expect(b['replay'], b['entry']);
      },
    );
  }
  for (final denial in ['new_active', 'void_without_write_rights']) {
    test(
      'independent historical void exception does not allow $denial',
      () async {
        final scenario = openItemCopy(independent['void_after_missing_start']);
        final api = YearValuesApi(fixture: scenario);
        if (denial == 'void_without_write_rights') api.write = false;
        final session = BusinessSession(api: api);
        try {
          await session.load();
          final body = openItemCopy(
            scenario[denial == 'new_active' ? 'original_command' : 'command'],
          )..remove('request_id');
          await expectLater(
            session.yearValuesCommand(
              'accounting-year-values-confirm-2026',
              '$yearValuesPath/confirm',
              body,
            ),
            throwsException,
          );
          expect(api.calls.where((c) => c.path.endsWith('/confirm')), isEmpty);
        } finally {
          session.dispose();
          api.dispose();
        }
      },
    );
  }
  test('independent evidenced zero remains distinct from missing controls or missing journal', () {
    final s = independent['actual_evidenced_zero'];
    final p = yearValuesPreview(
      s['preview'],
      reviewBody(openItemCopy(s['preview'])),
      openingItems: [],
    );
    expect(p['details']['historical_postings'], isEmpty);
    expect(p['proofs'], isNotEmpty);
    expect(p['payload']['attestations']['original_journal_complete'], true);
    expect(p['cash_flow_created'], false);
    final missing = openItemCopy(p)..['proofs'] = [];
    rehashPreview(missing);
    expect(
      () => yearValuesPreview(missing, reviewBody(missing), openingItems: []),
      throwsException,
    );
  });
  test('independent genuine original void after EÜR reverse remains possible with missing current start', () async {
    final scenario = openItemCopy(independent['void_after_missing_start']);
    expect(scenario['blocked_before_reverse']['status'], 409);
    expect(scenario['euer_reverse']['reverses'], scenario['euer_posted']['id']);
    expect(scenario['initial_state']['profile'], null);
    expect(scenario['initial_state']['can_prepare'], false);
    final api = YearValuesApi(fixture: scenario),
        session = BusinessSession(api: api);
    try {
      await session.load();
      final body = openItemCopy(scenario['command'])..remove('request_id');
      final result = await session.yearValuesCommand(
        'accounting-year-values-confirm-2026',
        '$yearValuesPath/confirm',
        body,
        validateResult: yearValuesReceipt(
          body,
          openItemCopy(scenario['preview']),
          openItemCopy(scenario['initial_state']),
        ),
      );
      expect(result, scenario['entry']);
      expect((result as Map)['payload']['status'], 'void');
      expect(api.calls.where((c) => c.path.endsWith('/confirm')).length, 1);
    } finally {
      session.dispose();
      api.dispose();
    }
  });
  for (final corruption in [
    'cash_date',
    'cash_cent',
    'net_projection',
    'account_projection',
    'vat_date',
    'vat_deduction_date',
  ]) {
    test(
      'independent rehashed $corruption cannot override unchanged actual original',
      () {
        final p = openItemCopy(complete['preview']);
        final details = p['details'] as Map,
            cash = (details['copied_rows'] as List).firstWhere(
              (r) => r['kind'] == 'cash_history',
            );
        final vat = (details['copied_rows'] as List).firstWhere(
          (r) => r['kind'] == 'already_exercised_input_vat',
        );
        final postings = businessItems(details['historical_postings']);
        if (corruption == 'cash_date') {
          cash['date'] = '2026-09-20';
          for (final row in postings.where(
            (r) => r['economic_key'] == cash['economic_key'],
          ))
            row['date'] = cash['date'];
        } else if (corruption == 'cash_cent' ||
            corruption == 'net_projection') {
          final amount = corruption == 'cash_cent' ? '-50.01' : '-49.00';
          if (corruption == 'cash_cent') {
            cash['gross'] = '59.51';
            cash['net'] = '50.01';
          }
          postings.firstWhere((r) => r['category'] == 'materials')['amount'] =
              amount;
          for (final rows in [details['controls'], p['payload']['controls']]) {
            (rows as List).firstWhere(
              (r) => r['category'] == 'materials',
            )['amount'] = amount;
          }
        } else if (corruption == 'account_projection') {
          postings.firstWhere((r) => r['category'] == 'materials')['account'] =
              '5401';
          for (final rows in [details['controls'], p['payload']['controls']]) {
            (rows as List).firstWhere(
              (r) => r['category'] == 'materials',
            )['account'] = '5401';
          }
        } else if (corruption == 'vat_date') {
          vat['date'] = '2026-07-11';
          vat['declared_period'] = '2026-07';
          postings.firstWhere((r) => r['ledger'] == 'vat')['date'] =
              vat['date'];
        } else {
          vat['deducted_on'] = '2026-07-11';
        }
        details['historical_postings'] = postings;
        rehashPreview(p);
        expect(
          () => yearValuesPreview(
            p,
            reviewBody(p),
            openingItems: [openItemEvent(complete['old_item'])],
          ),
          throwsException,
        );
      },
    );
  }
  test('independent old 19 VAT and 59.50 expense retain exact distinct days without cash', () {
    final p = yearValuesPreview(
      complete['preview'],
      reviewBody(openItemCopy(complete['preview'])),
      openingItems: [openItemEvent(complete['old_item'])],
    );
    final postings = businessItems(p['details']['historical_postings']);
    expect(
      postings
          .map((r) => [r['ledger'], r['amount'], r['date'], r['account']])
          .toList(),
      [
        ['euer', '-50.00', '2026-08-20', '5400'],
        ['euer', '-9.50', '2026-08-20', '1406'],
        ['vat', '-19.00', '2026-06-11', '1406'],
      ],
    );
    expect(p['details']['copied_rows'][1]['deducted_on'], '2026-07-10');
    expect(p['cash_flow_created'], false);
    expect(p['new_input_vat_claim_created'], false);
    expect(
      yearValuesSource(
        complete['source'],
        entry: openItemCopy(complete['entry']),
      )['cash_movements'],
      isEmpty,
    );
  });
  for (final missing in ['controls', 'journal']) {
    test(
      'independent missing $missing is not converted to an implicit zero journal',
      () {
        final p = openItemCopy(complete['preview']);
        if (missing == 'controls') {
          p['payload']['controls'] = [];
          p['details']['controls'] = [];
        } else {
          (p['proofs'] as List).removeAt(0);
        }
        rehashPreview(p);
        expect(
          () => yearValuesPreview(
            p,
            reviewBody(p),
            openingItems: [openItemEvent(complete['old_item'])],
          ),
          throwsException,
        );
      },
    );
  }
  test('independent actual private old-item history remains required for a valid yearly entry', () async {
    final api = CrossedYearHistoryApi(), session = BusinessSession(api: api);
    try {
      await session.load();
      await expectLater(
        yearValuesVerifiedEntry(session, complete['entry']),
        throwsException,
      );
      expect(api.calls.where((c) => c.body != null), isEmpty);
    } finally {
      session.dispose();
      api.dispose();
    }
  });
  testWidgets(
    'independent yearly controls editor closes when page unmounts with retained navigator',
    (t) async {
      final api = YearValuesApi(),
          session = BusinessSession(api: api),
          visible = ValueNotifier(true);
      try {
        await session.load();
        await t.pumpWidget(
          MaterialApp(
            home: ValueListenableBuilder<bool>(
              valueListenable: visible,
              builder: (_, show, child) => show
                  ? BusinessYearValuesPage(session: session)
                  : const Scaffold(body: Text('Neutral retained navigator')),
            ),
          ),
        );
        await t.pumpAndSettle();
        await yvTap(t, 'Jahresvortrag vorbereiten');
        await yvTap(t, 'Belegte Kontrollsumme hinzufügen');
        expect(find.byType(BusinessEditor), findsOneWidget);
        await t.enterText(
          find.byKey(const ValueKey('business-field-account')),
          '5400',
        );
        await t.enterText(
          find.byKey(const ValueKey('business-field-amount')),
          '-12345,67',
        );
        visible.value = false;
        await t.pumpAndSettle();
        expect(find.byType(BusinessYearValuesPage), findsNothing);
        expect(find.byType(BusinessEditor), findsNothing);
        expect(find.text('-12345,67'), findsNothing);
        expect(t.takeException(), null);
      } finally {
        await t.pumpWidget(const SizedBox.shrink());
        visible.dispose();
        session.dispose();
        api.dispose();
      }
    },
  );

  testWidgets(
    'independent yearly controls editor closes on allowed parent session replacement',
    (t) async {
      final api = YearValuesApi(), other = YearValuesApi();
      final first = BusinessSession(api: api),
          second = BusinessSession(api: other);
      final selected = ValueNotifier(first);
      try {
        await first.load();
        await second.load();
        await t.pumpWidget(
          MaterialApp(
            home: ValueListenableBuilder<BusinessSession>(
              valueListenable: selected,
              builder: (_, session, child) =>
                  BusinessYearValuesPage(session: session),
            ),
          ),
        );
        await t.pumpAndSettle();
        await yvTap(t, 'Jahresvortrag vorbereiten');
        await yvTap(t, 'Belegte Kontrollsumme hinzufügen');
        expect(find.byType(BusinessEditor), findsOneWidget);
        await t.enterText(
          find.byKey(const ValueKey('business-field-account')),
          '5400',
        );
        await t.enterText(
          find.byKey(const ValueKey('business-field-amount')),
          '-98765,43',
        );
        selected.value = second;
        await t.pumpAndSettle();
        expect(find.byType(BusinessEditor), findsNothing);
        expect(find.text('-98765,43'), findsNothing);
        expect(t.takeException(), null);
      } finally {
        await t.pumpWidget(const SizedBox.shrink());
        selected.dispose();
        first.dispose();
        second.dispose();
        api.dispose();
        other.dispose();
      }
    },
  );
  for (final change in ['background', 'dispose_under_unrelated_dialog']) {
    testWidgets(
      'independent private controls close on $change without removing foreign route',
      (t) async {
        final api = YearValuesApi();
        final session = BusinessSession(api: api);
        final visible = ValueNotifier(true);
        final navigator = GlobalKey<NavigatorState>();
        try {
          await session.load();
          await t.pumpWidget(
            MaterialApp(
              navigatorKey: navigator,
              home: ValueListenableBuilder<bool>(
                valueListenable: visible,
                builder: (_, show, child) => show
                    ? BusinessYearValuesPage(session: session)
                    : const Scaffold(body: Text('Neutral page')),
              ),
            ),
          );
          await t.pumpAndSettle();
          await yvTap(t, 'Jahresvortrag vorbereiten');
          await yvTap(t, 'Belegte Kontrollsumme hinzufügen');
          await t.enterText(
            find.byKey(const ValueKey('business-field-amount')),
            '-87654,32',
          );
          if (change == 'background') {
            reviewPause(t);
            // Paused Flutter deliberately does not draw. Observe the first
            // resumed frame, when the owned route can actually be removed.
            reviewResume(t);
          } else {
            navigator.currentState!.push(
              DialogRoute<void>(
                context: navigator.currentContext!,
                builder: (_) =>
                    const AlertDialog(content: Text('Unrelated route remains')),
              ),
            );
            await t.pumpAndSettle();
            visible.value = false;
          }
          await t.pumpAndSettle();
          expect(
            find.byType(BusinessEditor, skipOffstage: false),
            findsNothing,
          );
          expect(find.text('-87654,32', skipOffstage: false), findsNothing);
          if (change != 'background')
            expect(find.text('Unrelated route remains'), findsOneWidget);
          expect(t.takeException(), null);
        } finally {
          await t.pumpWidget(const SizedBox.shrink());
          visible.dispose();
          session.dispose();
          api.dispose();
        }
      },
    );
  }
  for (final change in ['background', 'session', 'write_failure']) {
    testWidgets(
      'independent actual original file chooser protects $change boundary',
      (t) async {
        final oldPlatform = FileSelectorPlatform.instance,
            picker = YearValuesSavePicker();
        FileSelectorPlatform.instance = picker;
        final temp = Directory.systemTemp.createTempSync(
          'year-values-independent-',
        );
        final api = YearValuesApi(), otherApi = YearValuesApi();
        final first = BusinessSession(api: api),
            second = BusinessSession(api: otherApi);
        final selected = ValueNotifier(first);
        final output = File('${temp.path}/original.pdf');
        try {
          await first.load();
          await second.load();
          await t.pumpWidget(
            MaterialApp(
              home: ValueListenableBuilder<BusinessSession>(
                valueListenable: selected,
                builder: (_, s, child) => BusinessYearValuesPage(session: s),
              ),
            ),
          );
          await t.pumpAndSettle();
          await yvTap(t, 'Geschützte Jahresoriginale (1)');
          await yvTap(t, 'historical.pdf', settle: false);
          for (var i = 0; i < 8; i++) {
            await t.pump();
          }
          expect(picker.calls, 1);
          if (change == 'background') reviewPause(t);
          if (change == 'session') selected.value = second;
          await t.pumpAndSettle();
          picker.answer.complete(
            FileSaveLocation(
              change == 'write_failure' ? temp.path : output.path,
            ),
          );
          for (var i = 0; i < 30; i++) {
            await t.runAsync(
              () => Future<void>.delayed(const Duration(milliseconds: 8)),
            );
            await t.pump(const Duration(milliseconds: 10));
          }
          await t.pumpAndSettle();
          expect(output.existsSync(), false);
          expect(api.byteReads, change == 'write_failure' ? 2 : 1);
          if (change == 'write_failure') {
            expect(
              find.text('Die Jahreswerte konnten nicht geprüft werden.'),
              findsOneWidget,
            );
          }
          expect(t.takeException(), null);
        } finally {
          if (change == 'background') reviewResume(t);
          await t.pumpWidget(const SizedBox.shrink());
          FileSelectorPlatform.instance = oldPlatform;
          selected.dispose();
          first.dispose();
          second.dispose();
          api.dispose();
          otherApi.dispose();
          temp.deleteSync(recursive: true);
        }
      },
    );
  }
}

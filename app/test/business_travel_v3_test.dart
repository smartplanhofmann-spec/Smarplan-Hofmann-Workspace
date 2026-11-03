import 'dart:convert';
import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:smartplan_office/api.dart';
import 'package:smartplan_office/business_session.dart';
import 'package:smartplan_office/business_travel_allowances.dart';

import 'business_travel_allowances_test.dart' show SnapshotApi;

final f = jsonDecode(
  File('test/fixtures/travel_allowances_v3.json').readAsStringSync(),
) as Map<String, dynamic>;
Map<String, dynamic> copy(dynamic v) =>
    Map<String, dynamic>.from(jsonDecode(jsonEncode(v)) as Map);

class MixedApi extends SnapshotApi {
  MixedApi() : super(copy(f));
  @override
  Future<dynamic> call(String path, [Map<String, dynamic>? body]) async {
    if (path.endsWith('/travel/catalog')) return copy(f['catalog']);
    return super.call(path, body);
  }
}

void main() {
  test('actual programme binds all originals with explicit incomplete flags allowed in draft', () {
    final raw = copy(f['trip_body']['details']['mixed_assessment']),
        files = businessItems(f['sources']['files']);
    expect(travelMixedAssessment(raw, files), raw);
    expect(
      travelMixedAssessment({
        ...raw,
        'program_complete': false,
        'cost_allocation_reviewed': false,
      }, files)['program_complete'],
      false,
    );
    for (final change in <void Function(Map<String, dynamic>)>[
      (v) => v['program_complete'] = null,
      (v) => v['program_sessions'].removeLast(),
      (v) => v['program_sessions'][1]['id'] = v['program_sessions'][0]['id'],
      (v) =>
          v['program_sessions'][1]['from'] = v['program_sessions'][0]['from'],
      (v) => v['program_sessions'][0]['source_file_ids'] = ['f' * 32],
      (v) => v['program_sessions'][0]['from'] = '2026-10-26T08:00:00',
      (v) => v['chosen_share'] = 1,
    ]) {
      final bad = copy(raw);
      change(bad);
      expect(
        () => travelMixedAssessment(bad, files),
        throwsA(isA<ApiException>()),
      );
    }
  });
  test('actual preview preserves programme split and independent original expense amount', () {
    expect(
      travelPreview(f['preview'], f['employee']['id'], copy(f['preview_body'])),
      f['preview'],
    );
    expect(f['preview']['days'][0]['base_minor'], 933);
    expect(f['preview']['totals']['expense_allowance_minor'], 600);
    expect(f['preview']['totals']['tax_free_minor'], 1533);
    for (final change in <void Function(Map<String, dynamic>)>[
      (v) => v['totals'].remove('expense_allowance_minor'),
      (v) => v['totals']['expense_already_paid_minor'] = -1,
      (v) => v['days'][0].remove('business_share'),
      (v) => v['days'][0]['business_share']['denominator'] = 0,
      (v) => v['days'][0]['business_share']['numerator'] = true,
      (v) => v.remove('ground_calendar_sources'),
      (v) => v['ground_calendar_sources'][0]['trip']['revision']++,
      (v) => v['mixed_program_sources'][0]['facts_hash'] = 'bad',
      (v) => v['mixed_program_sources'][0]['source_file_ids'].add(
        v['mixed_program_sources'][0]['source_file_ids'][0],
      ),
    ]) {
      final bad = copy(f['preview']);
      change(bad);
      expect(
        () => travelPreview(bad, f['employee']['id'], copy(f['preview_body'])),
        throwsA(isA<ApiException>()),
      );
    }
  });
  test(
    'missing programme remains visible blocked without fabricated facts hash',
    () {
      final v = copy(f['preview']);
      v['can_approve'] = false;
      v['blockers'] = [
        {'code': 'mixed_travel_assessment', 'text': 'Actual programme missing'},
      ];
      v['days'][0]['business_share'] = {'numerator': 0, 'denominator': 1};
      v['days'][0]['base_minor'] = 0;
      v['mixed_program_sources'] = [
        {
          'trip': copy(v['trip_refs'][0]),
          'rule_version': 'de_travel_mixed_program_2026_v1',
          'can_calculate': false,
          'blockers': v['blockers'],
        },
      ];
      expect(
        travelPreview(
          v,
          f['employee']['id'],
          copy(f['preview_body']),
        )['can_approve'],
        false,
      );
      v['can_approve'] = true;
      expect(
        () => travelV3Calculation(v, businessItems(v['trip_refs'])),
        throwsA(isA<ApiException>()),
      );
    },
  );
  test('actual correction leaves immutable historical programme and ground calendar intact', () {
    for (final item in businessItems(f['settlement_history']['items']))
      travelV3Calculation(
        businessMap(item['calculation']),
        businessItems(item['details']['trip_refs']),
      );
    expect(
      f['settlement_history']['items'][0]['calculation'],
      f['calculation'],
    );
  });
  testWidgets(
    'rendered programme edit clears both confirmations until fresh explicit review and preserves original expenses',
    (tester) async {
      await tester.binding.setSurfaceSize(const Size(1100, 1000));
      addTearDown(() => tester.binding.setSurfaceSize(null));
      final api = MixedApi();
      final current = BusinessSession(api: api);
      await current.load();
      var disposed = false;
      addTearDown(() {
        if (!disposed) current.dispose();
        api.dispose();
      });
      await tester.pumpWidget(
        MaterialApp(
          home: BusinessTravelAllowancesPage(
            session: current,
            employee: copy(f['employee']),
          ),
        ),
      );
      await tester.pumpAndSettle();
      Future<void> tap(String label) async {
        if (find.text(label).evaluate().isEmpty) {
          await tester.scrollUntilVisible(
            find.text(label),
            400,
            scrollable: find.byType(Scrollable).first,
            maxScrolls: 20,
          );
          await tester.pumpAndSettle();
        }
        final target = find.text(label).last;
        await tester.ensureVisible(target);
        await tester.pumpAndSettle();
        await tester.tap(target);
        await tester.pumpAndSettle();
      }

      Future<void> enter(String key, String value) async {
        final field = find.byKey(ValueKey('business-field-$key'));
        await tester.ensureVisible(field);
        await tester.pumpAndSettle();
        await tester.enterText(field, value);
        await tester.pumpAndSettle();
      }

      await tap(f['trip']['details']['purpose']);
      await tap('Reise korrigieren');
      await tap('Berufliches Programm');
      expect(find.text('Belegter Programmpunkt'), findsOneWidget);
      await tap('Programmpunkt in den Entwurf übernehmen');
      await tester.drag(find.byType(ListView).first, const Offset(0, 2000));
      await tester.pumpAndSettle();
      await tap('Programmbeurteilung bearbeiten');
      for (final value in tester.widgetList<SwitchListTile>(
        find.byType(SwitchListTile),
      ))
        expect(value.value, false);
      await tap(
        'Das gesamte berufliche und private Programm ist vollständig belegt.',
      );
      await tap(
        'Die Originalkosten sind getrennt beruflich, privat und bereitgestellt geprüft.',
      );
      await tap('Programmbeurteilung in den Entwurf übernehmen');
      await tester.drag(find.byType(ListView).first, const Offset(0, 2000));
      await tester.pumpAndSettle();
      await tap('Grunddaten und Pauschalenwunsch bearbeiten');
      await enter(
        'correction_reason',
        'Synthetic programme reread and independently reviewed',
      );
      await tap('Angaben übernehmen');
      await tap('Reiseentwurf belegt speichern');
      expect(api.posts, hasLength(1));
      final details = api.posts.single['body']['details'];
      expect(
        details['mixed_assessment'],
        f['trip']['details']['mixed_assessment'],
      );
      expect(
        details['expense_allocations'],
        f['trip']['details']['expense_allocations'],
      );
      expect(
        details['private_intervals'],
        f['trip']['details']['private_intervals'],
      );
      expect(tester.takeException(), isNull);
      await tester.pumpWidget(const SizedBox.shrink());
      current.dispose();
      disposed = true;
    },
  );
}

import 'dart:convert';
import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:smartplan_office/api.dart';
import 'package:smartplan_office/business_session.dart';
import 'package:smartplan_office/business_payroll_travel_tax_policies.dart';

final f = jsonDecode(
  File('test/fixtures/payroll_travel_tax_policies.json').readAsStringSync(),
) as Map<String, dynamic>;
Map<String, dynamic> copy(dynamic value) =>
    Map<String, dynamic>.from(jsonDecode(jsonEncode(value)) as Map);
Map<String, dynamic> clean(dynamic value) => copy(value)..remove('request_id');

class PolicyApi extends OfficeApi {
  PolicyApi() : super(apiVersion: 'v1') {
    token = 'synthetic-policy-ui-token';
  }
  bool read = true, approve = true, paused = false, lose = false;
  final sent = <Map<String, dynamic>>[], previews = <Map<String, dynamic>>[];
  final accepted = <String>{};
  Map<String, dynamic> current = copy(f['saved']);
  @override
  Future<dynamic> call(String path, [Map<String, dynamic>? body]) async {
    if (path.startsWith('/api/business/capabilities'))
      return {
        ...copy(f['capabilities']),
        'compatibility_mode': 'business',
        'storage_version': 10,
        'generation': 1,
        'permissions': [
          if (read) 'personnel.read',
          if (approve) 'personnel.approve',
        ],
        'organization': {
          'modules': {
            'personnel': {'visible': true, 'enabled': !paused},
          },
        },
      };
    if (path == '/api/me') return {'id': 'a' * 32};
    if (path == '/api/business/payroll/travel-tax-policies/sources')
      return {
        ...copy(f['sources']),
        'policies': [copy(current)],
        'can_approve': approve,
        'writes_enabled': !paused,
      };
    if (path == '/api/business/payroll/travel-tax-policies/preview') {
      previews.add(copy(body));
      return copy(f['correction_preview']);
    }
    if (path == '/api/business/payroll/travel-tax-policies') {
      sent.add(copy(body));
      accepted.add(body!['request_id']);
      current = copy(body['status'] == 'void' ? f['void'] : f['corrected']);
      if (lose) {
        lose = false;
        throw const ApiException(
          0,
          'Synthetisch verlorene angenommene Antwort.',
        );
      }
      return copy(current);
    }
    if (path.endsWith('/history')) return copy(f['history']);
    throw StateError(path);
  }
}

Future<void> tap(WidgetTester tester, String label) async {
  final target = find.text(label).last;
  await tester.ensureVisible(target);
  await tester.pumpAndSettle();
  await tester.tap(target);
  await tester.pumpAndSettle();
}

Future<void> enter(WidgetTester tester, String label, String value) async {
  final target = find.widgetWithText(TextFormField, label);
  await tester.ensureVisible(target);
  await tester.pumpAndSettle();
  await tester.enterText(target, value);
  await tester.pumpAndSettle();
}

Future<void> open(WidgetTester tester, BusinessSession session) async {
  await session.load();
  await tester.pumpWidget(
    MaterialApp(home: BusinessPayrollTravelTaxPoliciesPage(session: session)),
  );
  await tester.pumpAndSettle();
}

void main() {
  test(
    'actual employer evidence fixes filing window original and null person',
    () {
      final body = payrollTravelTaxPolicyInput(copy(f['sources_before']), {
        'details': copy(f['body']['details']),
        'source_file_ids': f['body']['source_file_ids'],
      });
      expect({
        ...body,
        'preview_hash': f['preview']['preview_hash'],
      }, clean(f['body']));
      expect(payrollTravelTaxPolicyRecord(f['saved']), f['saved']);
      for (final dates in [
        ['2026-02-01', '2026-02-28'],
        ['2026-07-01', '2026-09-30'],
        ['2026-01-01', '2026-12-31'],
      ]) {
        expect(
          payrollTravelTaxPolicyDetails({
            ...copy(f['body']['details']),
            'filing_period_from': dates[0],
            'filing_period_to': dates[1],
          })['filing_period_to'],
          dates[1],
        );
      }
      for (final patch in [
        {'filing_period_from': ''},
        {'filing_period_to': '2026-02-29'},
        {'filing_period_from': '2026-10-02'},
        {'employer_bears_tax': null},
        {'employer_bears_tax': 1},
        {'church_method_applies_to_all': false},
        {'church_rate_region': 'ni_ev_westfalen'},
        {'chosen_tax_minor': 0},
      ]) {
        expect(
          () => payrollTravelTaxPolicyDetails({
            ...copy(f['body']['details']),
            ...patch,
          }),
          throwsA(isA<ApiException>()),
        );
      }
    },
  );
  test('private sources reject substituted originals duplicate references and person scope', () {
    for (final alter in <void Function(Map<String, dynamic>)>[
      (v) => v['employee_id'] = 'a' * 32,
      (v) => v['file_references'][0]['content_hash'] = '0' * 64,
      (v) => v['files'].add(copy(v['files'][0])),
      (v) => v['policies'].add(copy(v['policies'][0])),
    ]) {
      final bad = copy(f['sources']);
      alter(bad);
      expect(
        () => payrollTravelTaxPolicySources(bad),
        throwsA(isA<ApiException>()),
      );
    }
    for (final alter in <void Function(Map<String, dynamic>)>[
      (v) => v['source_contract_version'] = true,
      (v) => v['sources']['schema_version'] = true,
      (v) => v['sources']['source_files'].add(
        copy(v['sources']['source_files'][0]),
      ),
    ]) {
      final bad = copy(f['saved']);
      alter(bad);
      expect(
        () => payrollTravelTaxPolicyRecord(bad),
        throwsA(isA<ApiException>()),
      );
    }
  });
  test('preview correction and void bind the exact original predecessor', () {
    final body = clean(f['correction_body']),
        proof = copy(f['correction_preview']);
    payrollTravelTaxPolicyPreview(proof, body);
    final validate = payrollTravelTaxPolicyValidator(
      body,
      previous: copy(f['saved']),
      preview: proof,
    );
    body['details']['verification_note'] = 'changed editor';
    proof['source_snapshot']['policy']['verification_note'] = 'changed editor';
    expect(() => validate(f['corrected']), returnsNormally);
    payrollTravelTaxPolicyValidator(
      clean(f['void_body']),
      previous: copy(f['corrected']),
    )(f['void']);
    final bad = copy(f['void'])..['previous_hash'] = f['saved']['content_hash'];
    expect(
      () => payrollTravelTaxPolicyValidator(
        clean(f['void_body']),
        previous: copy(f['corrected']),
      )(bad),
      throwsA(isA<ApiException>()),
    );
  });
  testWidgets(
    'mobile employer view clears private evidence after fresh global role withdrawal',
    (tester) async {
      tester.view.physicalSize = const Size(390, 844);
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.resetPhysicalSize);
      addTearDown(tester.view.resetDevicePixelRatio);
      final api = PolicyApi(), session = BusinessSession(api: api);
      addTearDown(api.dispose);
      await open(tester, session);
      await tap(tester, 'Entscheidung öffnen');
      await tester.drag(find.byType(ListView), const Offset(0, 2000));
      await tester.pumpAndSettle();
      await tester.scrollUntilVisible(
        find.text(f['saved']['details']['verification_note']),
        200,
      );
      await tester.pumpAndSettle();
      expect(
        find.text(f['saved']['details']['verification_note']),
        findsOneWidget,
      );
      expect(tester.takeException(), isNull);
      api.read = false;
      await session.load();
      await tester.pumpAndSettle();
      expect(
        find.text(f['saved']['details']['verification_note']),
        findsNothing,
      );
      expect(
        find.text('Steuerentscheidungen nicht freigegeben'),
        findsOneWidget,
      );
      await tester.pumpWidget(const SizedBox.shrink());
      session.dispose();
    },
  );
  testWidgets(
    'new policy does not invent dates method region or economic cost choice',
    (tester) async {
      final api = PolicyApi(), session = BusinessSession(api: api);
      addTearDown(api.dispose);
      await open(tester, session);
      await tap(tester, 'Betriebliche Steuerentscheidung erfassen');
      for (final label in [
        'Tatsächlicher Anmeldezeitraum ab',
        'Tatsächlicher Anmeldezeitraum bis',
      ]) {
        expect(
          tester
              .widget<TextFormField>(find.widgetWithText(TextFormField, label))
              .controller!
              .text,
          '',
        );
      }
      for (final field in tester.widgetList<DropdownButtonFormField<String>>(
        find.byType(DropdownButtonFormField<String>),
      )) {
        expect(field.initialValue, isNull);
      }
      expect(api.previews, isEmpty);
      expect(api.sent, isEmpty);
      expect(tester.takeException(), isNull);
      await tester.pumpWidget(const SizedBox.shrink());
      session.dispose();
    },
  );
  testWidgets(
    'rendered correction previews then freezes and repeats accepted command after lost response',
    (tester) async {
      final api = PolicyApi(), session = BusinessSession(api: api);
      addTearDown(api.dispose);
      await open(tester, session);
      await tap(tester, 'Entscheidung öffnen');
      await tap(tester, 'Entscheidung korrigieren');
      await enter(
        tester,
        'Nachvollziehbarer betrieblicher Prüfvermerk',
        f['correction_body']['details']['verification_note'],
      );
      await enter(
        tester,
        'Belegter Korrekturgrund',
        f['correction_body']['correction_reason'],
      );
      await tap(
        tester,
        'Dieses Verfahren gilt einheitlich für den gesamten Anmeldezeitraum und Tatbestand.',
      );
      await tap(tester, 'Betriebliche Entscheidung unverbindlich prüfen');
      expect(api.sent, isEmpty);
      expect(
        api.previews.single,
        payrollTravelTaxPolicyPreviewInput(clean(f['correction_body'])),
      );
      await tap(tester, 'Geprüfte Entscheidung festhalten');
      await tap(
        tester,
        'Ich bestätige die belegten Originale und die einheitliche betriebliche Entscheidung.',
      );
      api.lose = true;
      await tap(tester, 'Geprüfte Entscheidung festhalten');
      expect(session.pending(payrollTravelPolicyKey), isTrue);
      expect(clean(api.sent.single), clean(f['correction_body']));
      expect(
        tester
            .widget<SwitchListTile>(find.byType(SwitchListTile).last)
            .onChanged,
        isNull,
      );
      await tap(tester, 'Erneut senden');
      expect(api.sent.length, 2);
      expect(api.sent.first, api.sent.last);
      expect(api.accepted.length, 1);
      expect(session.pending(payrollTravelPolicyKey), isFalse);
      expect(
        find.text(f['corrected']['details']['verification_note']),
        findsOneWidget,
      );
      expect(tester.takeException(), isNull);
      await tester.pumpWidget(const SizedBox.shrink());
      session.dispose();
    },
  );
}

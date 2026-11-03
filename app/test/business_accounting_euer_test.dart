import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:smartplan_office/api.dart';
import 'package:smartplan_office/business_accounting_euer.dart';
import 'package:smartplan_office/business_accounting.dart';
import 'package:smartplan_office/business_session.dart';

import 'business_accounting_test.dart' show AccountingApi;

import 'package:smartplan_office/business_project_receipts.dart';

import 'euer_fixture.dart';
import 'project_economics_fixture.dart';

Future<void> visibleTap(WidgetTester tester, Finder finder) async {
  await tester.scrollUntilVisible(
    finder,
    350,
    scrollable: find.byType(Scrollable).first,
    maxScrolls: 45,
  );
  await tester.ensureVisible(finder);
  await tester.tap(finder);
  await tester.pumpAndSettle();
}

void main() {
  test('Explicit EÜR inputs preserve source cents and never invent dates, tax shares or SKR04 accounts', () {
    expect(euerMoney('0001,2'), '1.20');
    for (final value in ['1.001', '-1', 'NaN', ''])
      expect(() => euerMoney(value), throwsFormatException);
    final form = euerForm('cash', euerSource());
    expect(form.initial['euer_date'], '2026-11-02');
    expect(form.initial.containsKey('u0_account'), isFalse);
    expect(form.initial.containsKey('u0_deductible_input_tax'), isFalse);
    final values = {
      'euer_date': '2026-11-02',
      'year_kind': 'cash',
      'u0_category': 'sales',
      'u0_business_net': '100',
      'u0_business_tax': '19',
      'u0_deductible_net': '0',
      'u0_deductible_input_tax': '0',
      'u0_deductible_tax_cost': '0',
      'u0_account': '4400',
      'u0_vat_account': '3806',
    };
    expect(euerSame(form.payload(values), euerPayload()), isTrue);
    expect(
      euerForm('asset', {
        'receipt': {'receipt_id': economicsReceipt},
        'source_hash': 'a' * 64,
      }).initial.containsKey('use_start'),
      isFalse,
    );
    expect(
      () => form.payload({...values, 'u0_account': ''}),
      throwsFormatException,
    );
    final asset = {
      'id': 'a' * 32,
      'receipt': {'receipt_id': economicsReceipt},
    };
    expect(
      euerForm(
        'depreciation',
        asset,
        initial: {'asset_entry_id': 'c' * 32},
      ).payload({'year': 2026, 'account': '6220'})['asset_entry_id'],
      'c' * 32,
    );
  });
  test('Unknown ACK, fresh rights, ambiguous errors and generation retain original EÜR request; definitive nonacceptance clears it', () async {
    final api = EuerApi()..wrong = true, session = await euerSession(api);
    addTearDown(session.dispose);
    addTearDown(api.dispose);
    final body = {
          ...euerCommand(),
          'preview_hash': 'e' * 64,
          'confirmation': true,
        },
        proof = euerProof(euerCommand());
    await expectLater(
      session.command(
        euerPendingKey,
        '$euerPath/confirm',
        body,
        validateResult: euerReceiptValidator(body, proof),
      ),
      throwsA(isA<ApiException>().having((e) => e.status, 'status', 0)),
    );
    expect(session.pending(euerPendingKey), isTrue);
    expect(api.euerEntries, hasLength(1));
    body['reason'] = 'Locally edited';
    proof['postings'] = [];
    for (final failure in [
      const ApiException(403, 'Source denied'),
      const ApiException(404, 'Source hidden'),
      const ApiException(409, 'Ambiguous conflict'),
    ]) {
      api.nextFailure = failure;
      await expectLater(
        session.repeatAccountingEuerCommand(),
        throwsA(
          isA<ApiException>().having((e) => e.status, 'status', failure.status),
        ),
      );
      expect(session.pending(euerPendingKey), isTrue);
    }
    api.rights.remove('accounting.admin');
    await expectLater(
      session.repeatAccountingEuerCommand(),
      throwsA(isA<ApiException>().having((e) => e.status, 'status', 403)),
    );
    expect(session.pending(euerPendingKey), isTrue);
    api.rights.add('accounting.admin');
    api.generation++;
    final result = await session.repeatAccountingEuerCommand();
    expect(result['reason'], 'Geprüfter synthetischer Erlös');
    expect(session.pending(euerPendingKey), isFalse);
    expect(api.euerEntries, hasLength(1));
    expect(
      api.calls
          .where((c) => c.path.endsWith('/euer/confirm'))
          .map((c) => jsonEncode(c.body))
          .toSet(),
      hasLength(1),
    );
    final next = {
      ...euerCommand(),
      'expected_revision': 1,
      'preview_hash': 'e' * 64,
      'confirmation': true,
    };
    api.nextFailure = const ApiException(0, 'Before receipt');
    await expectLater(
      session.command(euerPendingKey, '$euerPath/confirm', next),
      throwsA(isA<ApiException>()),
    );
    api.nextFailure = const ApiException(
      409,
      'Not accepted',
      requestResolution: 'not_accepted',
    );
    await expectLater(
      session.repeatAccountingEuerCommand(),
      throwsA(isA<ApiException>()),
    );
    expect(session.pending(euerPendingKey), isFalse);
  });
  testWidgets(
    'Full cash review shows postings, requires confirmation, retains lost response across page close and allows correction',
    (tester) async {
      tester.view.physicalSize = const Size(1200, 2400);
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.resetPhysicalSize);
      addTearDown(tester.view.resetDevicePixelRatio);
      final api = EuerApi()..lose = true, session = await euerSession(api);
      Widget page() => MaterialApp(home: BusinessEuerPage(session: session));
      await tester.pumpWidget(page());
      await tester.pumpAndSettle();
      await visibleTap(tester, find.text('Geldfluss einordnen'));
      await tester.tap(find.text('Bitte ausdrücklich wählen'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Inländischer Erlös').last);
      await tester.pumpAndSettle();
      for (final entry in {
        'u0_business_net': '100',
        'u0_deductible_net': '0',
        'u0_business_tax': '19',
        'u0_deductible_input_tax': '0',
        'u0_deductible_tax_cost': '0',
        'u0_account': '4400',
        'u0_vat_account': '3806',
        'reason': 'Geprüfter synthetischer Erlös',
        'evidence_reference': 'Synthetischer Kontoauszug',
      }.entries)
        await tester.enterText(
          find.byKey(ValueKey('business-field-${entry.key}')),
          entry.value,
        );
      await tester.tap(find.text('Buchung unverbindlich prüfen'));
      await tester.pumpAndSettle();
      expect(find.text('Geprüfte Buchungsvorschau'), findsOneWidget);
      final confirm = find.widgetWithText(
        FilledButton,
        'Buchung verbindlich festhalten',
      );
      await tester.scrollUntilVisible(
        confirm,
        350,
        scrollable: find.byType(Scrollable).first,
        maxScrolls: 30,
      );
      expect(tester.widget<FilledButton>(confirm).onPressed, isNull);
      await visibleTap(tester, find.byType(CheckboxListTile));
      await visibleTap(tester, confirm);
      expect(api.euerEntries, hasLength(1));
      expect(session.pending(euerPendingKey), isTrue);
      await tester.pumpWidget(const SizedBox());
      await tester.pumpAndSettle();
      await tester.pumpWidget(page());
      await tester.pumpAndSettle();
      await visibleTap(
        tester,
        find.text('Ursprünglichen Auftrag erneut senden'),
      );
      expect(api.euerEntries, hasLength(1));
      expect(session.pending(euerPendingKey), isFalse);
      await visibleTap(tester, find.text('Einordnung berichtigen'));
      expect(
        find.text('Geldfluss fachlich buchen berichtigen'),
        findsOneWidget,
      );
      expect(
        tester
            .widget<TextFormField>(
              find.byKey(const ValueKey('business-field-u0_account')),
            )
            .controller!
            .text,
        '4400',
      );
      await tester.tap(find.text('Schließen'));
      await tester.pumpAndSettle();
      api.rights.remove('accounting.admin');
      await session.load();
      await tester.pumpAndSettle();
      expect(
        tester
            .widget<OutlinedButton>(
              find.widgetWithText(OutlinedButton, 'Einordnung berichtigen'),
            )
            .onPressed,
        isNull,
      );
      await tester.pumpWidget(const SizedBox());
      session.dispose();
      api.dispose();
    },
    variant: TargetPlatformVariant.only(TargetPlatform.windows),
  );
  testWidgets(
    '390px annual view keeps incomplete values unknown and clears private data on read revocation',
    (tester) async {
      tester.view.physicalSize = const Size(390, 844);
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.resetPhysicalSize);
      addTearDown(tester.view.resetDevicePixelRatio);
      final api = EuerApi(), session = await euerSession(api);
      await tester.pumpWidget(
        MaterialApp(home: BusinessEuerPage(session: session)),
      );
      await tester.pumpAndSettle();
      await visibleTap(tester, find.text('Jahr und Perioden'));
      await visibleTap(tester, find.text('Jahresauswertung laden'));
      await tester.scrollUntilVisible(
        find.textContaining('Ein fehlendes Gesamtergebnis ist nicht null'),
        350,
        scrollable: find.byType(Scrollable).first,
        maxScrolls: 40,
      );
      expect(tester.takeException(), isNull);
      api.rights.remove('finance.read');
      await session.load();
      await tester.pumpAndSettle();
      expect(find.text('EÜR nicht freigegeben'), findsOneWidget);
      expect(find.textContaining('119,00'), findsNothing);
      await tester.pumpWidget(const SizedBox());
      session.dispose();
      api.dispose();
    },
    variant: TargetPlatformVariant.only(TargetPlatform.windows),
  );
  testWidgets(
    'Receipt source opens scoped original review and preserves child pending command across return; parent revoke clears it',
    (tester) async {
      final api = EuerApi()..unreviewed = true,
          session = await euerSession(api);
      await tester.pumpWidget(
        MaterialApp(home: BusinessEuerPage(session: session)),
      );
      await tester.pumpAndSettle();
      await visibleTap(tester, find.text('Original / Belegprüfung'));
      expect(find.byType(BusinessProjectReceiptsPage), findsOneWidget);
      final child = session.sharedProjectSession(economicsProject);
      expect(child.projectId, economicsProject);
      expect(child, same(session.sharedProjectSession(economicsProject)));
      expect(child.can('finance.approve'), isTrue);
      // Retain a real protected receipt command in this child; response loss is synthetic.
      api.loseConfirm = true;
      await expectLater(
        child.command(
          'project-economics-$economicsProject-$economicsReceipt',
          '/project-economics/confirm',
          {
            'project_id': economicsProject,
            'receipt_id': economicsReceipt,
            'source_revision': 1,
            'expected_revision': 0,
            'reason': 'Synthetic pending',
            'allocations': [],
            'preview_hash': 'e' * 64,
          },
        ),
        throwsA(isA<ApiException>()),
      );
      await tester.pageBack();
      await tester.pumpAndSettle();
      expect(
        session
            .sharedProjectSession(economicsProject)
            .pending('project-economics-$economicsProject-$economicsReceipt'),
        isTrue,
      );
      session.revoke();
      await tester.pumpAndSettle();
      expect(child.allowed, isFalse);
      expect(
        child.pending('project-economics-$economicsProject-$economicsReceipt'),
        isFalse,
      );
      await tester.pumpWidget(const SizedBox());
      session.dispose();
      api.dispose();
    },
    variant: TargetPlatformVariant.only(TargetPlatform.windows),
  );
  testWidgets(
    'An EÜR tax or capital original is shown as payment evidence without invented supplier liability',
    (tester) async {
      tester.view.physicalSize = const Size(1200, 1600);
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.resetPhysicalSize);
      addTearDown(tester.view.resetDevicePixelRatio);
      final api = AccountingApi();
      api.receipt.addAll({
        'source_role': 'payment_evidence',
        'payable': false,
        'blocked_reason': 'external_cash_evidence',
        'paid_amount': null,
        'remaining_amount': null,
        'external_cash_binding': {
          'reserved_entry_id': 'a' * 32,
          'active_entry_id': 'a' * 32,
          'source_path': '/accounting/euer/journal',
        },
      });
      final session = BusinessSession(api: api);
      await session.load();
      await tester.pumpWidget(
        MaterialApp(
          home: BusinessAccountingPage(
            session: session,
            initialTab: 'receipts',
          ),
        ),
      );
      await tester.pumpAndSettle();
      expect(
        find.text(
          'Gebundener Zahlungsnachweis im EÜR-Journal; keine Lieferantenverbindlichkeit.',
        ),
        findsOneWidget,
      );
      expect(find.textContaining('Bestätigt ausgezahlt:'), findsNothing);
      expect(find.text('Auszahlung bestätigen'), findsNothing);
      await tester.pumpWidget(const SizedBox());
      session.dispose();
      api.dispose();
      final euerApi = EuerApi()..paymentEvidence = true,
          euer = await euerSession(euerApi);
      await tester.pumpWidget(
        MaterialApp(home: BusinessEuerPage(session: euer)),
      );
      await tester.pumpAndSettle();
      expect(
        find.text('Sondergeldbewegung nach Gegenbuchung erneut einordnen'),
        findsOneWidget,
      );
      expect(find.text('Steuer-/Kapitalbewegung'), findsOneWidget);
      expect(find.text('Vorsteuerrecht prüfen'), findsNothing);
      expect(find.text('Anlagegut'), findsNothing);
      await tester.pumpWidget(const SizedBox());
      euer.dispose();
      euerApi.dispose();
    },
    variant: TargetPlatformVariant.only(TargetPlatform.windows),
  );
}

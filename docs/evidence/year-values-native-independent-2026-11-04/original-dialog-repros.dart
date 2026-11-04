import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:smartplan_office/business_accounting_year_values.dart';
import 'package:smartplan_office/business_session.dart';
import 'package:smartplan_office/business_widgets.dart';

import 'business_accounting_year_values_lifecycle_test.dart'
    show YearValuesApi, yvTap;

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
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
          second = BusinessSession(api: other),
          selected = ValueNotifier<BusinessSession>(BusinessSession(api: api));
      selected.value.dispose();
      selected.value = first;
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
}

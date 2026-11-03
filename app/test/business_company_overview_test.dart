import 'dart:convert';
import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:smartplan_office/business_company_overview.dart';

Map<String, dynamic> fixture() =>
    jsonDecode(File('test/fixtures/company_overview.json').readAsStringSync())
        as Map<String, dynamic>;
void main() {
  test(
    'Unvollständige Finanzwerte werden nicht als sichere Summen dargestellt',
    () {
      final data = fixture();
      data['finance']['complete_for_recorded_sources'] = false;
      expect(() => companyOverviewData(data), throwsFormatException);
      data['finance']['contribution_net'] = null;
      expect(companyOverviewData(data)['finance']['contribution_net'], isNull);
      data['scope'] = 'selected_project';
      expect(() => companyOverviewData(data), throwsFormatException);
    },
  );
  testWidgets(
    'Umsatz, Zahlung und EÜR getrennt, Quellen und fehlender Anfangsbestand sichtbar',
    (tester) async {
      await tester.binding.setSurfaceSize(const Size(1200, 2400));
      addTearDown(() => tester.binding.setSurfaceSize(null));
      final selected = <String>[];
      var accounting = 0;
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: SingleChildScrollView(
              child: BusinessCompanyOverview(
                data: fixture(),
                onProject: selected.add,
                onAccounting: () => accounting++,
              ),
            ),
          ),
        ),
      );
      expect(find.text('Rechnungsumsatz netto'), findsOneWidget);
      expect(find.text('1.000,00 €'), findsOneWidget);
      expect(find.text('119,00 €'), findsOneWidget);
      expect(find.text('Klärung erforderlich'), findsOneWidget);
      expect(find.textContaining('Anfangsbestände'), findsOneWidget);
      await tester.tap(find.text('Beleg prüfen'));
      expect(selected, ['c' * 32]);
      await tester.ensureVisible(find.text('EÜR und Belege öffnen'));
      await tester.tap(find.text('EÜR und Belege öffnen'));
      expect(accounting, 1);
      expect(tester.takeException(), isNull);
    },
  );
  testWidgets('Mobile Übersicht ohne Überlauf oder fremde Finanzkarte', (
    tester,
  ) async {
    await tester.binding.setSurfaceSize(const Size(390, 844));
    addTearDown(() => tester.binding.setSurfaceSize(null));
    final data = fixture();
    data['accounting'] = {'available': false};
    data['finance'] = {
      'project_count': 0,
      'projects': [],
      'complete_for_recorded_sources': false,
      for (final key in [
        'revenue_net',
        'costs_net',
        'contribution_net',
        'receipts_gross',
        'refunds_gross',
        'open_gross',
        'overdue_gross',
      ])
        key: null,
    };
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: SingleChildScrollView(
            child: BusinessCompanyOverview(
              data: data,
              onProject: (_) {},
              onAccounting: () {},
            ),
          ),
        ),
      ),
    );
    expect(find.text('Rechnungsumsatz netto'), findsNothing);
    expect(find.text('EÜR und Belege öffnen'), findsNothing);
    expect(tester.takeException(), isNull);
  });
}

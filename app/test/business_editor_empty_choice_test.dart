import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:smartplan_office/business_session.dart';
import 'package:smartplan_office/business_widgets.dart';

import 'business_session_test.dart' show BusinessTestApi;

void main() {
  for (final supplied in [false, true]) {
    testWidgets('optional choice has one empty item when supplied=$supplied', (
      tester,
    ) async {
      final api = BusinessTestApi();
      final session = BusinessSession(api: api);
      await session.load();
      try {
        await tester.pumpWidget(
          MaterialApp(
            home: Scaffold(
              body: BusinessEditor(
                session: session,
                title: 'Optional choice',
                fields: [
                  BusinessField(
                    'person',
                    'Ansprechpartner',
                    type: BusinessInput.choice,
                    initial: '',
                    choices: {
                      if (supplied) '': 'Kein Ansprechpartner',
                      'a': 'Alpha',
                    },
                  ),
                ],
                onSave: (_) async {},
              ),
            ),
          ),
        );
        final dropdown = find.byWidgetPredicate(
          (widget) => widget is DropdownButton<String>,
        );
        var field = tester.widget<DropdownButton<String>>(dropdown);
        expect(field.items!.where((item) => item.value == ''), hasLength(1));
        expect(
          field.items!.map((item) => (item.child as Text).data),
          contains(supplied ? 'Kein Ansprechpartner' : 'Nicht angegeben'),
        );
        expect(tester.takeException(), isNull);
        await tester.tap(dropdown);
        await tester.pumpAndSettle();
        await tester.tap(find.text('Alpha').last);
        await tester.pumpAndSettle();
        field = tester.widget<DropdownButton<String>>(dropdown);
        expect(field.value, 'a');
        expect(tester.takeException(), isNull);
      } finally {
        await tester.pumpWidget(const SizedBox.shrink());
        session.dispose();
        api.dispose();
      }
    });
  }
}

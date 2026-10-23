import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:smartplan_office/api.dart';
import 'package:smartplan_office/plan_pages.dart';

class PlanTestApi extends OfficeApi {
  Map<String, dynamic>? saved;
  bool conflict = false;
  @override
  Future<dynamic> call(String path, [Map<String, dynamic>? body]) async {
    if (body != null) {
      if (conflict)
        throw const ApiException(409, 'Plan wurde inzwischen geändert');
      saved = Map<String, dynamic>.from(
        jsonDecode(
          jsonEncode({
            ...body,
            'id': 'plan1',
            'revision': (saved?['revision'] ?? 0) + 1,
          }),
        ),
      );
      return saved;
    }
    return path.endsWith('/plans') ? [if (saved != null) saved] : saved;
  }
}

void main() {
  testWidgets('Draw, undo, save and reopen a project plan', (tester) async {
    final api = PlanTestApi();
    await tester.pumpWidget(
      MaterialApp(
        home: PlansPage(
          api: api,
          project: const {'id': 'p1', 'name': 'Testprojekt'},
          canWrite: true,
        ),
      ),
    );
    await tester.pumpAndSettle();
    await tester.tap(find.text('Neuer Grundriss'));
    await tester.pumpAndSettle();
    await tester.enterText(find.byType(TextField), 'Erdgeschoss');
    final canvas = find.byWidgetPredicate(
      (widget) => widget is CustomPaint && widget.painter is PlanPainter,
    );
    final rect = tester.getRect(canvas);
    await tester.tapAt(
      rect.topLeft + Offset(rect.width * .2, rect.height * .2),
    );
    await tester.pump();
    await tester.tapAt(
      rect.topLeft + Offset(rect.width * .7, rect.height * .2),
    );
    await tester.pump();
    await tester.tap(find.text('Rückgängig'));
    await tester.pump();
    expect(tester.widget<CustomPaint>(canvas).painter, isA<PlanPainter>());
    expect(
      (tester.widget<CustomPaint>(canvas).painter as PlanPainter).walls,
      isEmpty,
    );
    await tester.tapAt(
      rect.topLeft + Offset(rect.width * .2, rect.height * .3),
    );
    await tester.pump();
    await tester.tapAt(
      rect.topLeft + Offset(rect.width * .7, rect.height * .3),
    );
    await tester.pump();
    await tester.tap(find.byTooltip('Speichern'));
    await tester.pumpAndSettle();
    expect(api.saved!['walls'], hasLength(1));
    await tester.tap(find.byIcon(Icons.arrow_back));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Erdgeschoss'));
    await tester.pumpAndSettle();
    expect(
      (tester.widget<CustomPaint>(canvas).painter as PlanPainter).walls,
      hasLength(1),
    );
  });

  testWidgets('Conflict retains draft; reader cannot draw or save', (
    tester,
  ) async {
    final api = PlanTestApi()..conflict = true;
    const initial = <String, dynamic>{
      'id': 'plan1',
      'title': 'EG',
      'revision': 1,
      'walls': [],
    };
    await tester.pumpWidget(
      MaterialApp(
        home: PlanPage(
          api: api,
          path: '/api/projects/p1/plans',
          initial: initial,
          canWrite: true,
        ),
      ),
    );
    await tester.enterText(find.byType(TextField), 'Mein Entwurf');
    await tester.tap(find.byTooltip('Speichern'));
    await tester.pumpAndSettle();
    expect(find.text('Plan wurde inzwischen geändert'), findsOneWidget);
    expect(find.text('Mein Entwurf'), findsOneWidget);
    await tester.pumpWidget(
      MaterialApp(
        home: PlanPage(
          key: const ValueKey('reader'),
          api: api,
          path: '/api/projects/p1/plans',
          initial: initial,
          canWrite: false,
        ),
      ),
    );
    expect(find.byTooltip('Speichern'), findsNothing);
    expect(tester.widget<TextField>(find.byType(TextField)).enabled, false);
  });
}

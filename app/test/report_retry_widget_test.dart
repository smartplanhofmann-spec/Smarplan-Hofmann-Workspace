import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:smartplan_office/api.dart';
import 'package:smartplan_office/project_page.dart';

import 'workflow_test.dart' show TestApi, openProjectReports;

class LostSignResponseApi extends TestApi {
  final signRequests = <Map<String, dynamic>>[];
  Map<String, dynamic>? archived;

  @override
  Future<dynamic> call(String path, [Map<String, dynamic>? body]) async {
    if (path == '/api/reports/report-1/sign') {
      signRequests.add(jsonDecode(jsonEncode(body)) as Map<String, dynamic>);
      if (archived == null) {
        archived = Map<String, dynamic>.from(await super.call(path, body));
        throw const ApiException(
          0,
          'Verbindung nach dem Speichern unterbrochen.',
        );
      }
      // Backend contract: an identical retry returns the original archive.
      expect(body, signRequests.first);
      return archived;
    }
    return super.call(path, body);
  }
}

void main() {
  testWidgets(
    'A lost signature response preserves the input and can finish with an identical retry',
    (tester) async {
      tester.view.physicalSize = const Size(1200, 1800);
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.resetPhysicalSize);
      addTearDown(tester.view.resetDevicePixelRatio);
      final api = LostSignResponseApi();
      addTearDown(api.dispose);
      await tester.pumpWidget(
        MaterialApp(
          home: ProjectPage(
            api: api,
            project: const {
              'id': 'project-1',
              'name': 'Synthetisches Projekt',
              'customer': 'Synthetischer Kunde',
            },
            role: 'technician',
          ),
        ),
      );
      await tester.pumpAndSettle();
      await openProjectReports(tester);
      await tester.tap(find.text('Servicebericht').first);
      await tester.pumpAndSettle();
      await tester.enterText(find.byType(TextField), 'Synthetischer Kunde');
      await tester.tap(find.byKey(const ValueKey('signature-preview')));
      await tester.pumpAndSettle();
      await tester.drag(
        find.byKey(const ValueKey('signature-canvas')),
        const Offset(100, 30),
      );
      await tester.pumpAndSettle();
      await tester.tap(find.byKey(const ValueKey('signature-done')));
      await tester.pumpAndSettle();
      await tester.tap(find.byType(CheckboxListTile));
      await tester.pumpAndSettle();
      final save = find.widgetWithText(FilledButton, 'Unterschrift speichern');
      await tester.tap(save);
      await tester.pumpAndSettle();
      expect(
        find.text('Verbindung nach dem Speichern unterbrochen.'),
        findsOneWidget,
      );
      expect(find.text('Abgeschlossen und unterzeichnet.'), findsNothing);
      expect(tester.widget<FilledButton>(save).onPressed, isNotNull);
      expect(
        tester.widget<CheckboxListTile>(find.byType(CheckboxListTile)).value,
        isTrue,
      );
      expect(
        find.widgetWithText(TextField, 'Synthetischer Kunde'),
        findsOneWidget,
      );

      await tester.ensureVisible(save);
      await tester.tap(save);
      await tester.pumpAndSettle();
      expect(api.signRequests, hasLength(2));
      expect(api.signRequests.last, api.signRequests.first);
      expect(find.text('Abgeschlossen und unterzeichnet.'), findsOneWidget);
      expect(find.text('Unterschrift speichern'), findsNothing);
      expect(
        find.text('Verbindung nach dem Speichern unterbrochen.'),
        findsNothing,
      );
      await tester.pumpWidget(const SizedBox.shrink());
    },
    variant: TargetPlatformVariant.only(TargetPlatform.windows),
  );
}

import 'dart:convert';
import 'dart:io';
import 'dart:ui' as ui;

import 'package:file_selector/file_selector.dart';
import 'package:flutter/foundation.dart' show defaultTargetPlatform;
import 'package:flutter/material.dart';
import 'package:flutter/rendering.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:smartplan_office/business_bank_reconciliation.dart';
import 'package:smartplan_office/business_session.dart';
import 'package:smartplan_office/design.dart';

import 'business_bank_camt_test.dart' show CamtApi, camtFixture;

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  setUpAll(() async {
    await (FontLoader(
      'Inter',
    )..addFont(rootBundle.load('assets/fonts/Inter.ttf'))).load();
    await (FontLoader(
      'MaterialIcons',
    )..addFont(rootBundle.load('fonts/MaterialIcons-Regular.otf'))).load();
  });
  const captureKey = ValueKey('camt-native-capture');
  Future<void> capture(WidgetTester tester, String name) async {
    final folder = Platform.environment['SMARTPLAN_CAMT_UI_OUTPUT'];
    if (folder == null) return;
    await tester.runAsync(() async {
      final image = await tester
          .renderObject<RenderRepaintBoundary>(find.byKey(captureKey))
          .toImage(pixelRatio: 1);
      try {
        final bytes = await image.toByteData(format: ui.ImageByteFormat.png);
        final file = File('$folder/$name-${defaultTargetPlatform.name}.png');
        await file.parent.create(recursive: true);
        await file.writeAsBytes(bytes!.buffer.asUint8List(), flush: true);
      } finally {
        image.dispose();
      }
    });
  }

  Future<void> tap(WidgetTester tester, String label) async {
    await tester.scrollUntilVisible(
      find.text(label),
      250,
      scrollable: find.byType(Scrollable).first,
    );
    await tester.tap(find.text(label));
    await tester.pumpAndSettle();
  }

  testWidgets(
    '390px XML original requires both reviews, repeats a lost ACK and hides private history after revocation',
    (tester) async {
      tester.view.physicalSize = const Size(390, 1000);
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.resetPhysicalSize);
      addTearDown(tester.view.resetDevicePixelRatio);
      final api = CamtApi();
      final s = BusinessSession(api: api);
      var disposed = false;
      await s.load();
      addTearDown(() {
        if (!disposed) s.dispose();
        api.dispose();
      });
      final bytes = base64Decode(camtFixture['body']['content_base64']);
      await tester.pumpWidget(
        RepaintBoundary(
          key: captureKey,
          child: MaterialApp(
            theme: officeTheme(),
            debugShowCheckedModeBanner: false,
            home: BusinessBankReconciliationPage(
              session: s,
              pickFile: () async => XFile.fromData(
                bytes,
                name: camtFixture['request']['filename'],
                path: camtFixture['request']['filename'],
                mimeType: 'application/xml',
              ),
            ),
          ),
        ),
      );
      await tester.pumpAndSettle();
      await tap(tester, 'Kontoauszüge und Abgleich öffnen');
      await tap(tester, 'Originalen XML-Auszug prüfen');
      expect(
        find.text('XML-Kontoauszug prüfen'),
        findsOneWidget,
        reason: tester
            .widgetList<Text>(find.byType(Text))
            .map((t) => t.data)
            .join(' | '),
      );
      expect(
        tester.widget<CheckboxListTile>(find.byType(CheckboxListTile)).value,
        isFalse,
      );
      expect(api.posts, isEmpty);
      await capture(tester, 'camt-original-review-390');
      await tester.tap(find.byType(CheckboxListTile));
      await tester.pumpAndSettle();
      await tap(tester, 'Auszug unverbindlich prüfen');
      expect(
        tester.widget<CheckboxListTile>(find.byType(CheckboxListTile)).value,
        isFalse,
      );
      expect(api.posts, isEmpty);
      await capture(tester, 'camt-proposed-import-390');
      await tester.tap(find.byType(CheckboxListTile));
      await tester.pumpAndSettle();
      api.lose = true;
      await tap(tester, 'Geprüften Banknachweis speichern');
      expect(api.posts, hasLength(1));
      await tap(tester, 'Geprüften Banknachweis speichern');
      expect(api.posts, hasLength(2));
      expect(api.posts.first, api.posts.last);
      expect(
        find.text('Unverändertes XML-Original herunterladen'),
        findsOneWidget,
      );
      await capture(tester, 'camt-accepted-original-390');
      api.read = false;
      await s.load();
      await tester.pumpAndSettle();
      expect(
        find.text('Unverändertes XML-Original herunterladen'),
        findsNothing,
      );
      expect(find.textContaining('DE89370400440532013000'), findsNothing);
      expect(tester.takeException(), isNull);
      s.dispose();
      disposed = true;
      await tester.pumpWidget(const SizedBox.shrink());
    },
    variant: TargetPlatformVariant({
      TargetPlatform.windows,
      TargetPlatform.iOS,
    }),
  );
}

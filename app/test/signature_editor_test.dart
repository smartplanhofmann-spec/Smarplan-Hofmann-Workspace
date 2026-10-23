import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:smartplan_office/design.dart';
import 'package:smartplan_office/signature_editor.dart';

const _canvasKey = ValueKey('signature-canvas');
const _doneKey = ValueKey('signature-done');
const _clearKey = ValueKey('signature-clear');
const _cancelKey = ValueKey('signature-cancel');
const _openKey = ValueKey('open-signature');

class _EditorSession {
  List<List<Offset>>? result;
  bool returned = false;
  final orientations = <List<String>>[];
}

Future<_EditorSession> _openEditor(
  WidgetTester tester, {
  List<List<Offset>> initialStrokes = const [],
  Size viewport = const Size(390, 844),
  ScrollController? scrollController,
  bool refuseRotation = false,
}) async {
  final session = _EditorSession();
  tester.view.physicalSize = viewport;
  tester.view.devicePixelRatio = 1;
  addTearDown(tester.view.resetPhysicalSize);
  addTearDown(tester.view.resetDevicePixelRatio);

  final messenger = tester.binding.defaultBinaryMessenger;
  messenger.setMockMethodCallHandler(SystemChannels.platform, (call) async {
    if (call.method == 'SystemChrome.setPreferredOrientations') {
      final orientations = List<String>.from(call.arguments as List);
      session.orientations.add(orientations);
      if (refuseRotation && orientations.isNotEmpty) {
        throw PlatformException(code: 'orientation-not-available');
      }
    }
    return null;
  });
  addTearDown(
    () => messenger.setMockMethodCallHandler(SystemChannels.platform, null),
  );

  await tester.pumpWidget(
    MaterialApp(
      theme: officeTheme(),
      home: Builder(
        builder: (context) => Scaffold(
          body: SingleChildScrollView(
            controller: scrollController,
            child: Column(
              children: [
                const SizedBox(height: 500),
                FilledButton(
                  key: _openKey,
                  onPressed: () async {
                    session.result = await showSignatureEditor(
                      context,
                      initialStrokes: initialStrokes,
                    );
                    session.returned = true;
                  },
                  child: const Text('Unterschrift öffnen'),
                ),
                const SizedBox(height: 1800),
              ],
            ),
          ),
        ),
      ),
    ),
  );
  await tester.ensureVisible(find.byKey(_openKey));
  await tester.pumpAndSettle();
  await tester.tap(find.byKey(_openKey));
  await tester.pumpAndSettle();
  expect(find.byType(SignatureEditor), findsOneWidget);
  return session;
}

RenderBox _canvas(WidgetTester tester) =>
    tester.renderObject<RenderBox>(find.byKey(_canvasKey));

Future<void> _drawSmallStroke(WidgetTester tester) async {
  final box = _canvas(tester);
  final start = Offset(box.size.width * .25, box.size.height * .4);
  final gesture = await tester.createGesture(pointer: 1);
  await gesture.down(box.localToGlobal(start));
  await gesture.moveTo(box.localToGlobal(start + const Offset(1, 1)));
  await gesture.up();
  await tester.pump();
}

void _testOnIPhone(String description, WidgetTesterCallback callback) {
  testWidgets(
    description,
    callback,
    variant: TargetPlatformVariant.only(TargetPlatform.iOS),
  );
}

void main() {
  _testOnIPhone(
    'The first one-pixel movement is captured and returned in normalized coordinates',
    (tester) async {
      final session = await _openEditor(tester, viewport: const Size(844, 390));
      expect(
        tester.widget<FilledButton>(find.byKey(_doneKey)).onPressed,
        isNull,
      );
      final size = _canvas(tester).size;
      await _drawSmallStroke(tester);
      expect(
        tester.widget<FilledButton>(find.byKey(_doneKey)).onPressed,
        isNotNull,
      );
      await tester.tap(find.byKey(_doneKey));
      await tester.pumpAndSettle();

      expect(session.returned, isTrue);
      final points = session.result!.single;
      expect(points, hasLength(2));
      expect(points.first.dx, closeTo(.25, .00001));
      expect(points.first.dy, closeTo(.4, .00001));
      expect(points.last.dx, closeTo(.25 + 1 / size.width, .00001));
      expect(points.last.dy, closeTo(.4 + 1 / size.height, .00001));
      expect(session.orientations.first, [
        'DeviceOrientation.landscapeLeft',
        'DeviceOrientation.landscapeRight',
      ]);
      expect(session.orientations.last, isEmpty);
    },
  );

  _testOnIPhone(
    'A vertical finger stroke cannot scroll the report underneath the editor',
    (tester) async {
      final controller = ScrollController(initialScrollOffset: 320);
      addTearDown(controller.dispose);
      final session = await _openEditor(tester, scrollController: controller);
      final oldOffset = controller.offset;
      final box = _canvas(tester);
      expect(
        box.size.width / box.size.height,
        closeTo(signatureAspectRatio, .001),
      );

      final gesture = await tester.createGesture(pointer: 1);
      await gesture.down(box.localToGlobal(box.size.center(Offset.zero)));
      await gesture.moveBy(const Offset(0, 95));
      await gesture.up();
      await tester.pump();
      expect(controller.offset, oldOffset);
      await tester.tap(find.byKey(_doneKey));
      await tester.pumpAndSettle();
      expect(session.result!.single.length, greaterThan(1));
      expect(controller.offset, oldOffset);
    },
  );

  _testOnIPhone('Clear followed by cancel preserves the saved signature', (
    tester,
  ) async {
    final original = [
      [const Offset(.1, .2), const Offset(.8, .7)],
    ];
    final expected = [for (final stroke in original) List<Offset>.of(stroke)];
    final session = await _openEditor(tester, initialStrokes: original);
    expect(
      tester.widget<FilledButton>(find.byKey(_doneKey)).onPressed,
      isNotNull,
    );
    await tester.tap(find.byKey(_clearKey));
    await tester.pump();
    expect(tester.widget<FilledButton>(find.byKey(_doneKey)).onPressed, isNull);
    await _drawSmallStroke(tester);
    await tester.tap(find.byKey(_cancelKey));
    await tester.pumpAndSettle();

    expect(session.returned, isTrue);
    expect(session.result, isNull);
    expect(original, expected);
    expect(session.orientations.last, isEmpty);
  });

  _testOnIPhone(
    'System back discards edits and restores the orientation policy',
    (tester) async {
      final original = [
        [const Offset(.1, .2), const Offset(.8, .7)],
      ];
      final expected = [for (final stroke in original) List<Offset>.of(stroke)];
      final session = await _openEditor(tester, initialStrokes: original);
      await _drawSmallStroke(tester);
      await tester.binding.handlePopRoute();
      await tester.pumpAndSettle();

      expect(session.returned, isTrue);
      expect(session.result, isNull);
      expect(original, expected);
      expect(session.orientations.last, isEmpty);
    },
  );

  _testOnIPhone(
    'A refused rotation still provides a landscape signing surface',
    (tester) async {
      final session = await _openEditor(tester, refuseRotation: true);
      final size = _canvas(tester).size;
      expect(size.width, greaterThan(size.height));
      expect(size.width / size.height, closeTo(signatureAspectRatio, .001));
      expect(tester.takeException(), isNull);
      await _drawSmallStroke(tester);
      await tester.tap(find.byKey(_doneKey));
      await tester.pumpAndSettle();
      expect(session.result, isNotEmpty);
      expect(session.orientations.last, isEmpty);
    },
  );

  _testOnIPhone('A second finger cannot start or extend the active stroke', (
    tester,
  ) async {
    final session = await _openEditor(tester);
    final box = _canvas(tester);
    final start = Offset(box.size.width * .25, box.size.height * .4);
    final first = await tester.createGesture(pointer: 1);
    final second = await tester.createGesture(pointer: 2);
    await first.down(box.localToGlobal(start));
    await second.down(box.localToGlobal(start + const Offset(40, 10)));
    await second.moveBy(const Offset(0, 40));
    await second.up();
    await tester.pump();
    expect(tester.widget<FilledButton>(find.byKey(_doneKey)).onPressed, isNull);

    await first.moveTo(box.localToGlobal(start + const Offset(1, 1)));
    await first.up();
    await tester.pump();
    await tester.tap(find.byKey(_doneKey));
    await tester.pumpAndSettle();
    expect(session.result, hasLength(1));
    expect(session.result!.single, hasLength(2));
  });
}

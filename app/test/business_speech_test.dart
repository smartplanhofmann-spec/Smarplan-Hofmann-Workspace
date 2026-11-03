import 'dart:async';
import 'dart:convert';
import 'dart:typed_data';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:smartplan_office/api.dart';
import 'package:smartplan_office/business_session.dart';
import 'package:smartplan_office/business_speech.dart';

const project = 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',
    sourceId = 'bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb';
final source = {
  'id': sourceId,
  'project_id': project,
  'sha256': 'c' * 64,
  'current': true,
};

class FakeRecorder implements SpeechRecorder {
  bool permitted = true;
  Completer<bool>? permissionResult;
  int starts = 0, cancels = 0, stops = 0;
  StreamController<Uint8List>? stream;
  @override
  Future<bool> permission() =>
      permissionResult?.future ?? Future.value(permitted);
  @override
  Future<Stream<Uint8List>> start() async {
    starts++;
    stream = StreamController<Uint8List>();
    return stream!.stream;
  }

  @override
  Future<void> stop() async {
    stops++;
    await stream?.close();
  }

  @override
  Future<void> cancel() async {
    cancels++;
    if (stream?.isClosed == false) await stream?.close();
  }

  @override
  Future<void> dispose() => cancel();
  void emit() => stream!.add(
    Uint8List.fromList(List.generate(320, (index) => index % 128)),
  );
}

class FakeTimer implements Timer {
  FakeTimer(this.callback);
  final void Function() callback;
  bool active = true;
  @override
  bool get isActive => active;
  @override
  int get tick => 0;
  @override
  void cancel() => active = false;
  void fire() {
    if (active) {
      active = false;
      callback();
    }
  }
}

class SpeechApi extends OfficeApi {
  SpeechApi() : super(apiVersion: 'v1') {
    token = 'synthetic-voice-test-token';
  }
  bool lose = false, allow = true;
  Completer<void>? responseGate;
  int generation = 1;
  final posts = <Map<String, dynamic>>[], paths = <String>[];
  @override
  Future<dynamic> call(String path, [Map<String, dynamic>? body]) async {
    paths.add(path);
    if (path.startsWith('/api/business/capabilities'))
      return {
        'compatibility_mode': 'business',
        'generation': generation,
        'readonly': false,
        'capabilities': ['business_assistant', 'business_assistant_speech'],
        'features': ['assistant_workflow', 'assistant_speech'],
        'permissions': allow ? ['assistant.use', 'documents.read'] : [],
      };
    if (path == '/api/business/assistant/contexts/$sourceId') return source;
    if (path == '/api/business/assistant/speech/transcribe') {
      posts.add(jsonDecode(jsonEncode(body)) as Map<String, dynamic>);
      await responseGate?.future;
      if (lose) throw const ApiException(0, 'Erfolgsantwort verloren');
      return {
        'id': body!['request_id'],
        'project_id': project,
        'context_id': sourceId,
        'context_sha256': source['sha256'],
        'status': 'completed',
        'text': 'Synthetischer erkannter Entwurf.',
        'audio_sha256': 'd' * 64,
        'audio_persisted': false,
        'transcript_persisted': false,
        'retry_automatically': false,
      };
    }
    if (path.startsWith('/api/business/assistant/speech/requests/'))
      return {
        'id': path.split('/').last,
        'project_id': project,
        'context_id': sourceId,
        'status': 'completed',
        'retry_automatically': false,
        'transcript_persisted': false,
      };
    throw StateError('Unexpected $path');
  }
}

void main() {
  test(
    'canonical WAV keeps raw PCM unchanged and bounds duration and alignment',
    () {
      final pcm = Uint8List.fromList([0, 128, 255, 127]),
          wav = speechPcmWav(pcm),
          data = ByteData.view(wav.buffer);
      expect(wav.length, 48);
      expect(ascii.decode(wav.sublist(0, 4)), 'RIFF');
      expect(data.getUint32(24, Endian.little), 16000);
      expect(data.getUint16(22, Endian.little), 1);
      expect(data.getUint16(34, Endian.little), 16);
      expect(wav.sublist(44), pcm);
      for (final invalid in [
        Uint8List(0),
        Uint8List(1),
        Uint8List(speechMaxPcmBytes + 2),
      ]) {
        expect(() => speechPcmWav(invalid), throwsFormatException);
      }
    },
  );
  test(
    'permission cancelled while pending cannot later start microphone',
    () async {
      final recorder = FakeRecorder()..permissionResult = Completer<bool>(),
          controller = SpeechCaptureController(recorder: recorder);
      final start = controller.start();
      controller.cancel();
      recorder.permissionResult!.complete(true);
      await start;
      expect(recorder.starts, 0);
      expect(controller.audio, isNull);
      controller.dispose();
    },
  );
  test(
    'explicit stop produces RAM-only WAV and disposal erases held bytes',
    () async {
      final recorder = FakeRecorder(),
          controller = SpeechCaptureController(recorder: recorder);
      await controller.start();
      recorder.emit();
      await Future<void>.delayed(Duration.zero);
      await controller.stop();
      expect(controller.phase, 'ready');
      expect(recorder.stops, 1);
      final bytes = controller.audio!;
      expect(bytes.length, 364);
      controller.dispose();
      expect(bytes.every((value) => value == 0), isTrue);
      expect(controller.audio, isNull);
    },
  );
  test(
    'hard 60 second timer stops capture without triggering any provider',
    () async {
      FakeTimer? timer;
      final recorder = FakeRecorder(),
          controller = SpeechCaptureController(
            recorder: recorder,
            timer: (duration, callback) {
              expect(duration, const Duration(seconds: 60));
              return timer = FakeTimer(callback);
            },
          );
      await controller.start();
      recorder.emit();
      await Future<void>.delayed(Duration.zero);
      timer!.fire();
      await Future<void>.delayed(Duration.zero);
      expect(controller.phase, 'ready');
      expect(recorder.stops, 1);
      controller.dispose();
    },
  );
  Future<BusinessSession> show(
    WidgetTester tester,
    SpeechApi api,
    FakeRecorder recorder,
  ) async {
    tester.view.physicalSize = const Size(1300, 1500);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    final session = BusinessSession(api: api, projectId: project);
    await session.load();
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: BusinessSpeechDraft(
            session: session,
            source: source,
            provider: {
              'model': 'synthetic-test-model',
              'endpoint': 'https://speech.example.test/v1/audio/transcriptions',
            },
            recorder: recorder,
          ),
        ),
      ),
    );
    await tester.pumpAndSettle();
    return session;
  }

  Future<void> capture(WidgetTester tester, FakeRecorder recorder) async {
    final gesture = await tester.startGesture(
      tester.getCenter(find.text('Zum Sprechen gedrückt halten')),
    );
    await tester.pumpAndSettle();
    recorder.emit();
    await tester.pump();
    await gesture.up();
    await tester.pumpAndSettle();
    expect(recorder.starts, 1);
  }

  Future<void> upload(WidgetTester tester) async {
    await tester.tap(
      find.text(
        'Ich bestätige die Übertragung dieser Aufnahme an den eingerichteten Sprachanbieter.',
      ),
    );
    await tester.pump();
    await tester.tap(find.text('Aufnahme in Text umwandeln'));
    await tester.pumpAndSettle();
  }

  testWidgets(
    'press and release only prepares audio; explicit consent produces an editable draft without chat send',
    (tester) async {
      final api = SpeechApi(),
          recorder = FakeRecorder(),
          session = await show(tester, api, recorder);
      try {
        await capture(tester, recorder);
        expect(api.posts, isEmpty);
        expect(
          tester
              .widget<FilledButton>(
                find.widgetWithText(FilledButton, 'Aufnahme in Text umwandeln'),
              )
              .onPressed,
          isNull,
        );
        await upload(tester);
        expect(api.posts, hasLength(1));
        expect(base64Decode(api.posts.single['audio_base64']).length, 364);
        expect(find.text('Synthetischer erkannter Entwurf.'), findsOneWidget);
        await tester.enterText(
          find.widgetWithText(TextField, 'Erkannter Textentwurf'),
          'Manuell geprüfter Entwurf.',
        );
        expect(
          api.paths.any((path) => path == '/api/business/assistant/chat'),
          isFalse,
        );
        expect(api.posts, hasLength(1));
      } finally {
        await tester.pumpWidget(const SizedBox());
        session.dispose();
        api.dispose();
      }
    },
    variant: TargetPlatformVariant.only(TargetPlatform.windows),
  );
  testWidgets(
    'lost speech acknowledgement only polls metadata and never posts audio again',
    (tester) async {
      final api = SpeechApi()..lose = true,
          recorder = FakeRecorder(),
          session = await show(tester, api, recorder);
      try {
        await capture(tester, recorder);
        await upload(tester);
        expect(find.text('Erkannter Textentwurf'), findsNothing);
        await tester.tap(find.text('Status des begonnenen Aufrufs prüfen'));
        await tester.pumpAndSettle();
        await tester.tap(find.text('Status des begonnenen Aufrufs prüfen'));
        await tester.pumpAndSettle();
        expect(api.posts, hasLength(1));
        expect(
          find.textContaining('der Text wurde nicht gespeichert'),
          findsOneWidget,
        );
        expect(find.text('Aufnahme in Text umwandeln'), findsNothing);
      } finally {
        await tester.pumpWidget(const SizedBox());
        session.dispose();
        api.dispose();
      }
    },
    variant: TargetPlatformVariant.only(TargetPlatform.windows),
  );
  testWidgets(
    'late provider response after background and resume cannot restore discarded text',
    (tester) async {
      final api = SpeechApi()..responseGate = Completer<void>(),
          recorder = FakeRecorder(),
          session = await show(tester, api, recorder);
      try {
        await capture(tester, recorder);
        await upload(tester);
        expect(api.posts, hasLength(1));
        tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.hidden);
        await tester.pump();
        tester.binding.handleAppLifecycleStateChanged(
          AppLifecycleState.resumed,
        );
        await tester.pumpAndSettle();
        api.responseGate!.complete();
        await tester.pumpAndSettle();
        expect(find.text('Synthetischer erkannter Entwurf.'), findsNothing);
        expect(find.text('Erkannter Textentwurf'), findsNothing);
        expect(
          find.text('Status des begonnenen Aufrufs prüfen'),
          findsOneWidget,
        );
        await tester.tap(find.text('Status des begonnenen Aufrufs prüfen'));
        await tester.pumpAndSettle();
        expect(api.posts, hasLength(1));
      } finally {
        await tester.pumpWidget(const SizedBox());
        session.dispose();
        api.dispose();
      }
    },
    variant: TargetPlatformVariant.only(TargetPlatform.windows),
  );
  testWidgets(
    'background transition and known rights loss stop microphone and erase draft',
    (tester) async {
      final api = SpeechApi(),
          recorder = FakeRecorder(),
          session = await show(tester, api, recorder);
      try {
        final gesture = await tester.startGesture(
          tester.getCenter(find.text('Zum Sprechen gedrückt halten')),
        );
        await tester.pumpAndSettle();
        recorder.emit();
        tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.hidden);
        await tester.pumpAndSettle();
        await gesture.up();
        await tester.pumpAndSettle();
        expect(recorder.cancels, greaterThan(0));
        expect(api.posts, isEmpty);
        tester.binding.handleAppLifecycleStateChanged(
          AppLifecycleState.resumed,
        );
        await tester.pumpAndSettle();
        expect(find.textContaining('verworfen'), findsOneWidget);
        api.allow = false;
        api.generation++;
        await session.load();
        await tester.pumpAndSettle();
        expect(
          tester
              .widget<FilledButton>(
                find.widgetWithText(
                  FilledButton,
                  'Zum Sprechen gedrückt halten',
                ),
              )
              .onPressed,
          isNull,
        );
        expect(api.posts, isEmpty);
      } finally {
        tester.binding.handleAppLifecycleStateChanged(
          AppLifecycleState.resumed,
        );
        await tester.pumpWidget(const SizedBox());
        session.dispose();
        api.dispose();
      }
    },
    variant: TargetPlatformVariant.only(TargetPlatform.windows),
  );
}

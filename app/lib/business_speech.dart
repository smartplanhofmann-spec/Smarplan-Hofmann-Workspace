import 'dart:async';
import 'dart:convert';
import 'dart:typed_data';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:record/record.dart';

import 'api.dart';
import 'business_session.dart';
import 'design.dart';
import 'offline_vault.dart' show offlineId;

const speechSampleRate = 16000, speechMaxPcmBytes = 1920000;
Uint8List speechPcmWav(Uint8List pcm) {
  if (pcm.isEmpty || pcm.length.isOdd || pcm.length > speechMaxPcmBytes) {
    throw const FormatException(
      'Eine vollständige PCM-Aufnahme bis 60 Sekunden ist erforderlich.',
    );
  }
  final bytes = Uint8List(44 + pcm.length), data = ByteData.view(bytes.buffer);
  void ascii(int offset, String text) =>
      bytes.setRange(offset, offset + text.length, asciiEncode(text));
  ascii(0, 'RIFF');
  data.setUint32(4, bytes.length - 8, Endian.little);
  ascii(8, 'WAVE');
  ascii(12, 'fmt ');
  data.setUint32(16, 16, Endian.little);
  data.setUint16(20, 1, Endian.little);
  data.setUint16(22, 1, Endian.little);
  data.setUint32(24, 16000, Endian.little);
  data.setUint32(28, 32000, Endian.little);
  data.setUint16(32, 2, Endian.little);
  data.setUint16(34, 16, Endian.little);
  ascii(36, 'data');
  data.setUint32(40, pcm.length, Endian.little);
  bytes.setRange(44, bytes.length, pcm);
  return bytes;
}

List<int> asciiEncode(String text) => ascii.encode(text);
String speechDraftResult(
  dynamic raw, {
  required String requestId,
  required String projectId,
  required String contextId,
  required String contextSha256,
}) {
  final value = businessMap(raw), text = value['text'];
  if (value['id'] != requestId ||
      value['project_id'] != projectId ||
      value['context_id'] != contextId ||
      value['context_sha256'] != contextSha256 ||
      value['status'] != 'completed' ||
      value['audio_persisted'] != false ||
      value['transcript_persisted'] != false ||
      value['retry_automatically'] != false ||
      text is! String ||
      text.trim().isEmpty ||
      text.length > 4000 ||
      !RegExp(r'^[a-f0-9]{64}$').hasMatch('${value['audio_sha256'] ?? ''}')) {
    throw const ApiException(
      0,
      'Die Sprachantwort bestätigt den ursprünglichen Auftrag nicht.',
    );
  }
  return text;
}

abstract interface class SpeechRecorder {
  Future<bool> permission();
  Future<Stream<Uint8List>> start();
  Future<void> stop();
  Future<void> cancel();
  Future<void> dispose();
}

/// record 7.1.2: native AVFoundation/MediaFoundation PCM stream; no file path.
class NativeSpeechRecorder implements SpeechRecorder {
  AudioRecorder? _recorder;
  StreamSubscription<Uint8List>? _subscription;
  StreamSubscription<RecordState>? _stateSubscription;
  StreamController<Uint8List>? _output;
  AudioRecorder get recorder => _recorder ??= AudioRecorder();
  @override
  Future<bool> permission() => recorder.hasPermission();
  @override
  Future<Stream<Uint8List>> start() async {
    final output = StreamController<Uint8List>();
    _output = output;
    await recorder.setOnConfigChanged((config) {
      if (config.encoder != AudioEncoder.pcm16bits ||
          config.sampleRate != 16000 ||
          config.numChannels != 1) {
        if (!output.isClosed)
          output.addError(
            const FormatException(
              'Dieses Mikrofon liefert nicht das freigegebene Sprachformat.',
            ),
          );
        unawaited(cancel());
      }
    });
    _stateSubscription = recorder.onStateChanged().listen((state) {
      if (state == RecordState.pause) {
        if (!output.isClosed)
          output.addError(
            const FormatException('Die Mikrofonaufnahme wurde unterbrochen.'),
          );
        unawaited(cancel());
      }
    });
    final stream = await recorder.startStream(
      const RecordConfig(
        encoder: AudioEncoder.pcm16bits,
        sampleRate: 16000,
        numChannels: 1,
        streamBufferSize: 3200,
        audioInterruption: AudioInterruptionMode.pause,
      ),
    );
    _subscription = stream.listen(
      (bytes) {
        if (!output.isClosed) output.add(bytes);
      },
      onError: (Object error, StackTrace stack) {
        if (!output.isClosed) output.addError(error, stack);
      },
      onDone: () {
        if (!output.isClosed) unawaited(output.close());
      },
    );
    return output.stream;
  }

  @override
  Future<void> stop() async {
    await _recorder?.stop();
  }

  @override
  Future<void> cancel() async {
    await _recorder?.cancel();
    await _subscription?.cancel();
    await _stateSubscription?.cancel();
    _stateSubscription = null;
    _subscription = null;
    final output = _output;
    if (output != null && !output.isClosed) unawaited(output.close());
  }

  @override
  Future<void> dispose() async {
    await cancel();
    await _recorder?.dispose();
    _recorder = null;
  }
}

class SpeechCaptureController extends ChangeNotifier {
  SpeechCaptureController({
    required this.recorder,
    bool Function()? allowed,
    Timer Function(Duration, void Function())? timer,
  }) : allowed = allowed ?? (() => true),
       createTimer =
           timer ?? ((duration, callback) => Timer(duration, callback));
  final SpeechRecorder recorder;
  final bool Function() allowed;
  final Timer Function(Duration, void Function()) createTimer;
  String phase = 'idle',
      message =
          'Zum Sprechen gedrückt halten. Es wird keine Audiodatei gespeichert.';
  Uint8List? audio;
  int _epoch = 0, _bytes = 0;
  bool _closed = false;
  Timer? _timer;
  StreamSubscription<Uint8List>? _subscription;
  Completer<void>? _done;
  final _chunks = <Uint8List>[];
  void changed() {
    if (!_closed) notifyListeners();
  }

  void erase() {
    audio?.fillRange(0, audio!.length, 0);
    audio = null;
    for (final chunk in _chunks) {
      chunk.fillRange(0, chunk.length, 0);
    }
    _chunks.clear();
    _bytes = 0;
  }

  Future<void> start() async {
    if (_closed || !allowed() || !['idle', 'error'].contains(phase)) return;
    final epoch = ++_epoch;
    erase();
    phase = 'requesting';
    message = 'Mikrofonfreigabe wird geprüft. Zum Sprechen gedrückt halten.';
    changed();
    try {
      if (!await recorder.permission())
        throw const ApiException(
          403,
          'Mikrofonzugriff nicht freigegeben. Die Texteingabe bleibt verfügbar.',
        );
      if (_closed || epoch != _epoch || !allowed()) return;
      final stream = await recorder.start();
      if (_closed || epoch != _epoch || !allowed()) {
        await recorder.cancel();
        return;
      }
      _done = Completer<void>();
      phase = 'recording';
      message =
          'Aufnahme läuft · zum Beenden loslassen · höchstens 60 Sekunden';
      _subscription = stream.listen(
        (value) {
          if (epoch != _epoch || _closed) return;
          _bytes += value.length;
          if (_bytes > speechMaxPcmBytes) {
            cancel('Die Aufnahme überschreitet 60 Sekunden.');
            return;
          }
          _chunks.add(Uint8List.fromList(value));
        },
        onError: (Object error) {
          if (epoch == _epoch) cancel('$error');
        },
        onDone: () {
          if (!(_done?.isCompleted ?? true)) _done!.complete();
          if (epoch == _epoch && phase == 'recording')
            cancel('Die Mikrofonaufnahme wurde unterbrochen.');
        },
      );
      _timer = createTimer(
        const Duration(seconds: 60),
        () => unawaited(stop()),
      );
      changed();
    } catch (error) {
      if (epoch == _epoch && !_closed) cancel('$error');
    }
  }

  Future<void> stop() async {
    if (phase == 'requesting') {
      cancel(
        'Vor dem Start losgelassen. Nach der Mikrofonfreigabe erneut gedrückt halten.',
      );
      return;
    }
    if (phase != 'recording') return;
    final epoch = _epoch;
    phase = 'processing';
    message = 'Aufnahme beendet. Audiodaten werden lokal geprüft.';
    _timer?.cancel();
    _timer = null;
    changed();
    try {
      await recorder.stop();
      await _done?.future.timeout(const Duration(seconds: 3));
      if (_closed || epoch != _epoch || !allowed()) return;
      final pcm = Uint8List(_bytes);
      var offset = 0;
      for (final chunk in _chunks) {
        pcm.setRange(offset, offset + chunk.length, chunk);
        offset += chunk.length;
      }
      final wav = speechPcmWav(pcm);
      pcm.fillRange(0, pcm.length, 0);
      erase();
      audio = wav;
      phase = 'ready';
      message = 'Aufnahme beendet. Erst nach Ihrer Bestätigung wird sie zur Spracherkennung übertragen.';
      changed();
    } catch (error) {
      if (epoch == _epoch && !_closed) cancel('$error');
    }
  }

  void cancel([String reason = 'Aufnahme verworfen.']) {
    _epoch++;
    _timer?.cancel();
    _timer = null;
    erase();
    phase = 'error';
    message = reason;
    if (!(_done?.isCompleted ?? true)) _done!.complete();
    unawaited(_subscription?.cancel());
    _subscription = null;
    unawaited(recorder.cancel());
    changed();
  }

  @override
  void dispose() {
    if (_closed) return;
    cancel('');
    _closed = true;
    unawaited(recorder.dispose());
    super.dispose();
  }
}

Future<String?> showBusinessSpeechDraft(
  BuildContext context, {
  required BusinessSession session,
  required Map<String, dynamic> source,
  required Map<String, dynamic> provider,
  SpeechRecorder? recorder,
}) => showDialog<String>(
  context: context,
  barrierDismissible: false,
  builder: (_) => BusinessSpeechDraft(
    session: session,
    source: source,
    provider: provider,
    recorder: recorder,
  ),
);

class BusinessSpeechDraft extends StatefulWidget {
  const BusinessSpeechDraft({
    super.key,
    required this.session,
    required this.source,
    required this.provider,
    this.recorder,
  });
  final BusinessSession session;
  final Map<String, dynamic> source, provider;
  final SpeechRecorder? recorder;
  @override
  State<BusinessSpeechDraft> createState() => _BusinessSpeechDraftState();
}

class _BusinessSpeechDraftState extends State<BusinessSpeechDraft>
    with WidgetsBindingObserver {
  late final SpeechCaptureController capture;
  final text = TextEditingController(), requestId = offlineId();
  late final String? token;
  late final BusinessSession originalSession;
  late final Object? generation;
  late final Set<String> permissions;
  bool consent = false,
      sent = false,
      closing = false,
      foreground = true,
      contextInvalidated = false;
  String status = '';
  int cancellationEpoch = 0;
  bool get allowed =>
      mounted &&
      !closing &&
      !contextInvalidated &&
      foreground &&
      identical(widget.session, originalSession) &&
      widget.session.allowed &&
      widget.session.api.token == token &&
      widget.session.generation == generation &&
      widget.session.permissions.containsAll(permissions) &&
      widget.session.canWrite('assistant.use') &&
      widget.session.hasFeature('assistant_speech') &&
      widget.session.hasModule('assistant_speech');
  @override
  void initState() {
    super.initState();
    originalSession = widget.session;
    token = widget.session.api.token;
    generation = widget.session.generation;
    permissions = Set.of(widget.session.permissions);
    capture = SpeechCaptureController(
      recorder: widget.recorder ?? NativeSpeechRecorder(),
      allowed: () => allowed,
    )..addListener(changed);
    widget.session.addListener(accessChanged);
    WidgetsBinding.instance.addObserver(this);
  }

  @override
  void didUpdateWidget(covariant BusinessSpeechDraft oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (!identical(oldWidget.session, widget.session) ||
        oldWidget.source['id'] != widget.source['id'] ||
        oldWidget.source['project_id'] != widget.source['project_id'] ||
        oldWidget.source['sha256'] != widget.source['sha256'] ||
        jsonEncode(oldWidget.provider) != jsonEncode(widget.provider) ||
        !identical(oldWidget.recorder, widget.recorder)) {
      oldWidget.session.removeListener(accessChanged);
      widget.session.addListener(accessChanged);
      contextInvalidated = true;
      cancellationEpoch++;
      capture.cancel(
        'Sitzung oder Datenbasis geändert. Aufnahme und Entwurf wurden verworfen. Bitte neu öffnen.',
      );
      text.clear();
      status = '';
      consent = false;
    }
  }

  void changed() {
    if (mounted && !closing) setState(() {});
  }

  void accessChanged() {
    if (!allowed) {
      cancellationEpoch++;
      capture.cancel(
        'Berechtigung oder Sitzung geändert. Aufnahme und Entwurf wurden verworfen.',
      );
      text.clear();
      consent = false;
    }
    changed();
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state == AppLifecycleState.resumed) {
      foreground = true;
      changed();
      return;
    }
    if (state == AppLifecycleState.hidden ||
        state == AppLifecycleState.paused ||
        state == AppLifecycleState.detached ||
        (state == AppLifecycleState.inactive && capture.phase == 'recording')) {
      foreground = false;
      cancellationEpoch++;
      capture.cancel(
        'App im Hintergrund. Aufnahme und Entwurf wurden verworfen.',
      );
      text.clear();
      consent = false;
      if (sent) capture.phase = 'unknown';
    }
  }

  @override
  void dispose() {
    closing = true;
    WidgetsBinding.instance.removeObserver(this);
    widget.session.removeListener(accessChanged);
    capture.removeListener(changed);
    capture.dispose();
    text.dispose();
    super.dispose();
  }

  Future<void> transcribe() async {
    if (!allowed || capture.phase != 'ready' || !consent || sent) return;
    final startedEpoch = cancellationEpoch;
    sent = true;
    capture.phase = 'sending';
    capture.message = 'Die bestätigte Aufnahme wird einmalig übertragen. Ein begonnener Anbieteraufruf lässt sich möglicherweise nicht zurückrufen.';
    changed();
    Map<String, dynamic>? body;
    try {
      final current = businessMap(
        await widget.session.read('/assistant/contexts/${widget.source['id']}'),
      );
      if (!allowed ||
          startedEpoch != cancellationEpoch ||
          current['project_id'] != widget.source['project_id'] ||
          current['sha256'] != widget.source['sha256'] ||
          current['current'] != true)
        throw const ApiException(
          403,
          'Datenbasis oder Berechtigung wurde geändert. Bitte neu auswählen.',
        );
      body = {
        'request_id': requestId,
        'context_id': widget.source['id'],
        'data_transfer_confirmed': true,
        'audio_base64': base64Encode(capture.audio!),
      };
      capture.erase();
      final result = await widget.session.api.call(
        widget.session.path('/assistant/speech/transcribe'),
        body,
      );
      body['audio_base64'] = '';
      if (!allowed || startedEpoch != cancellationEpoch) return;
      text.text = speechDraftResult(
        result,
        requestId: requestId,
        projectId: '${widget.source['project_id']}',
        contextId: '${widget.source['id']}',
        contextSha256: '${widget.source['sha256']}',
      );
      capture.phase = 'completed';
      capture.message = 'Erkannten Text prüfen und bearbeiten. Es wurde noch keine Chatnachricht gesendet.';
    } catch (error) {
      if (allowed && startedEpoch == cancellationEpoch) {
        capture.phase = 'unknown';
        capture.message = 'Keine bestätigte Sprachantwort. Ein Anbieteraufruf kann bereits erfolgt sein. Den Status prüfen; dieselbe Aufnahme wird nicht erneut gesendet.';
        status = '$error';
      }
    } finally {
      if (body != null) body['audio_base64'] = '';
      capture.erase();
      if (allowed) changed();
    }
  }

  Future<void> poll() async {
    if (!allowed || !sent) return;
    final startedEpoch = cancellationEpoch;
    try {
      final value = businessMap(
        await widget.session.read('/assistant/speech/requests/$requestId'),
      );
      if (!allowed || startedEpoch != cancellationEpoch) return;
      if (value['id'] != requestId ||
          value['context_id'] != widget.source['id'] ||
          value['project_id'] != widget.source['project_id'] ||
          value['retry_automatically'] != false ||
          value['transcript_persisted'] != false)
        throw const ApiException(
          0,
          'Status bestätigt den ursprünglichen Auftrag nicht.',
        );
      status =
          'Dokumentierter Status: ${{'started': 'Begonnen', 'completed': 'Anbieterantwort erhalten; der Text wurde nicht gespeichert', 'failed': 'Fehlgeschlagen', 'interrupted': 'Unterbrochen'}[value['status']] ?? 'Unbestätigt'}. Für einen neuen Versuch eine neue Aufnahme ausdrücklich starten.';
    } catch (error) {
      if (allowed && startedEpoch == cancellationEpoch) status = '$error';
    }
    if (allowed && startedEpoch == cancellationEpoch) changed();
  }

  @override
  Widget build(BuildContext context) {
    final canStart =
        allowed &&
        !sent &&
        ['idle', 'error', 'requesting', 'recording'].contains(capture.phase);
    return AlertDialog(
      title: const Text('Sprache als Textentwurf'),
      content: SizedBox(
        width: 700,
        child: SingleChildScrollView(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Notice(
                'Sprachanbieter: ${widget.provider['model']} · ${widget.provider['endpoint']}. Aufnahme nur während des Gedrückthaltens, höchstens 60 Sekunden; Audio bleibt ausschließlich im Arbeitsspeicher.',
              ),
              Focus(
                onKeyEvent: (_, event) {
                  if (event.logicalKey != LogicalKeyboardKey.space &&
                      event.logicalKey != LogicalKeyboardKey.enter)
                    return KeyEventResult.ignored;
                  if (event is KeyDownEvent && canStart)
                    unawaited(capture.start());
                  if (event is KeyUpEvent) unawaited(capture.stop());
                  return KeyEventResult.handled;
                },
                child: Listener(
                  onPointerDown: canStart
                      ? (_) => unawaited(capture.start())
                      : null,
                  onPointerUp: (_) => unawaited(capture.stop()),
                  onPointerCancel: (_) => capture.cancel(),
                  child: Semantics(
                    button: true,
                    enabled: canStart,
                    label: capture.phase == 'recording'
                        ? 'Aufnahme beenden'
                        : 'Aufnahme starten. Höchstens 60 Sekunden.',
                    onTap: canStart
                        ? () {
                            if (capture.phase == 'recording') {
                              unawaited(capture.stop());
                            } else {
                              unawaited(capture.start());
                            }
                          }
                        : null,
                    child: ExcludeSemantics(
                      child: FilledButton(
                        onPressed: canStart ? () {} : null,
                        child: const Text('Zum Sprechen gedrückt halten'),
                      ),
                    ),
                  ),
                ),
              ),
              const SizedBox(height: 12),
              Text(capture.message),
              if (capture.phase == 'ready') ...[
                SwitchListTile.adaptive(
                  contentPadding: EdgeInsets.zero,
                  title: const Text(
                    'Ich bestätige die Übertragung dieser Aufnahme an den eingerichteten Sprachanbieter.',
                  ),
                  value: consent,
                  onChanged: allowed && !sent
                      ? (value) => setState(() => consent = value)
                      : null,
                ),
                FilledButton(
                  onPressed: allowed && consent && !sent ? transcribe : null,
                  child: const Text('Aufnahme in Text umwandeln'),
                ),
              ],
              if (capture.phase == 'completed')
                TextField(
                  controller: text,
                  maxLength: 4000,
                  maxLines: 6,
                  enabled: allowed,
                  decoration: const InputDecoration(
                    labelText: 'Erkannter Textentwurf',
                  ),
                ),
              if (capture.phase == 'unknown') ...[
                Text(status),
                TextButton(
                  onPressed: allowed ? poll : null,
                  child: const Text('Status des begonnenen Aufrufs prüfen'),
                ),
              ],
            ],
          ),
        ),
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.pop(context),
          child: const Text('Aufnahme und Entwurf verwerfen'),
        ),
        if (capture.phase == 'completed')
          FilledButton(
            onPressed: allowed
                ? () {
                    final value = text.text.trim();
                    if (value.isNotEmpty && value.length <= 4000)
                      Navigator.pop(context, value);
                  }
                : null,
            child: const Text('Textentwurf übernehmen'),
          ),
      ],
    );
  }
}

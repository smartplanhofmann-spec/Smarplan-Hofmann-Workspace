import 'dart:math' as math;

import 'package:flutter/foundation.dart';
import 'package:flutter/gestures.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import 'design.dart';

// The PDF uses a 420 by 110 point signature area. Keep capture and preview at
// that same ratio so adopting a signature never stretches its handwriting.
const double signatureAspectRatio = 420 / 110;

bool get _isMobile =>
    !kIsWeb &&
    (defaultTargetPlatform == TargetPlatform.iOS ||
        defaultTargetPlatform == TargetPlatform.android);

Future<void> _requestOrientation(List<DeviceOrientation> orientations) async {
  try {
    await SystemChrome.setPreferredOrientations(orientations);
  } on PlatformException {
    // Rotation can be refused by a windowed iPad or the platform. The rotated
    // landscape surface below remains usable without changing global settings.
  } on MissingPluginException {
    // A host without an orientation implementation can still edit the ink.
  }
}

/// Edits a private copy of the signature. Only "Fertig" returns new ink.
Future<List<List<Offset>>?> showSignatureEditor(
  BuildContext context, {
  required List<List<Offset>> initialStrokes,
}) async {
  FocusManager.instance.primaryFocus?.unfocus();
  final rotateDevice = _isMobile;
  try {
    if (rotateDevice) {
      await _requestOrientation(const [
        DeviceOrientation.landscapeLeft,
        DeviceOrientation.landscapeRight,
      ]);
    }
    if (!context.mounted) return null;
    return await Navigator.of(context).push<List<List<Offset>>>(
      MaterialPageRoute(
        fullscreenDialog: true,
        builder: (_) => SignatureEditor(initialStrokes: initialStrokes),
      ),
    );
  } finally {
    if (rotateDevice) {
      // The rest of the app uses the platform's supported orientation policy.
      await _requestOrientation(const []);
    }
  }
}

class SignatureEditor extends StatefulWidget {
  final List<List<Offset>> initialStrokes;

  const SignatureEditor({super.key, required this.initialStrokes});

  @override
  State<SignatureEditor> createState() => _SignatureEditorState();
}

class _SignatureEditorState extends State<SignatureEditor>
    with WidgetsBindingObserver {
  late final List<List<Offset>> _strokes;
  int? _activePointer;

  bool get _hasSignature => _strokes.any((stroke) => stroke.length > 1);

  @override
  void initState() {
    super.initState();
    _strokes = [for (final stroke in widget.initialStrokes) List.of(stroke)];
    WidgetsBinding.instance.addObserver(this);
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    super.dispose();
  }

  @override
  void didChangeMetrics() {
    // Stop an in-flight stroke if UIKit rotates/resizes the view. The existing
    // normalized ink survives, but a finger must not connect across two layouts.
    _activePointer = null;
  }

  Offset _point(Offset position, Size size) => Offset(
    (position.dx / size.width).clamp(0.0, 1.0),
    (position.dy / size.height).clamp(0.0, 1.0),
  );

  void _start(PointerDownEvent event, Size size) {
    if (_activePointer != null || (event.buttons & kPrimaryButton) == 0) return;
    setState(() {
      _activePointer = event.pointer;
      _strokes.add([_point(event.localPosition, size)]);
    });
  }

  void _move(PointerMoveEvent event, Size size) {
    if (event.pointer != _activePointer || _strokes.isEmpty) return;
    final point = _point(event.localPosition, size);
    if (_strokes.last.last == point) return;
    setState(() => _strokes.last.add(point));
  }

  void _end(PointerEvent event) {
    if (event.pointer == _activePointer) _activePointer = null;
  }

  void _clear() {
    setState(() {
      _activePointer = null;
      _strokes.clear();
    });
  }

  void _done() {
    if (!_hasSignature) return;
    Navigator.of(context).pop([
      for (final stroke in _strokes)
        if (stroke.length > 1) List<Offset>.of(stroke),
    ]);
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    backgroundColor: OfficeColors.canvas,
    body: SafeArea(
      child: LayoutBuilder(
        builder: (context, constraints) => RotatedBox(
          // The OS may keep a portrait viewport (e.g. rotation lock/windowing).
          // Rotate the complete surface, including its controls and hit testing.
          quarterTurns:
              _isMobile && constraints.maxHeight > constraints.maxWidth ? 1 : 0,
          child: Padding(
            padding: const EdgeInsets.all(16),
            child: Column(
              children: [
                LayoutBuilder(
                  builder: (context, constraints) {
                    final compact =
                        constraints.maxWidth < 600 ||
                        MediaQuery.textScalerOf(context).scale(14) > 22;
                    return Row(
                      children: [
                        IconButton(
                          key: const ValueKey('signature-cancel'),
                          tooltip: 'Abbrechen',
                          onPressed: () => Navigator.of(context).pop(),
                          icon: const Icon(Icons.close_rounded),
                        ),
                        const SizedBox(width: 8),
                        const Expanded(
                          child: Text(
                            'Unterschrift',
                            overflow: TextOverflow.ellipsis,
                            style: TextStyle(
                              fontSize: 20,
                              fontWeight: FontWeight.w600,
                            ),
                          ),
                        ),
                        if (compact)
                          IconButton(
                            key: const ValueKey('signature-clear'),
                            tooltip: 'Neu zeichnen',
                            onPressed: _strokes.isEmpty ? null : _clear,
                            icon: const Icon(Icons.refresh_rounded),
                          )
                        else
                          TextButton.icon(
                            key: const ValueKey('signature-clear'),
                            onPressed: _strokes.isEmpty ? null : _clear,
                            icon: const Icon(Icons.refresh_rounded, size: 18),
                            label: const Text('Neu zeichnen'),
                          ),
                        const SizedBox(width: 12),
                        FilledButton(
                          key: const ValueKey('signature-done'),
                          onPressed: _hasSignature ? _done : null,
                          child: const Text('Fertig'),
                        ),
                      ],
                    );
                  },
                ),
                const SizedBox(height: 12),
                Expanded(
                  child: Center(
                    child: LayoutBuilder(
                      builder: (context, constraints) {
                        final width = math.min(
                          constraints.maxWidth,
                          constraints.maxHeight * signatureAspectRatio,
                        );
                        final size = Size(width, width / signatureAspectRatio);
                        return SizedBox.fromSize(
                          size: size,
                          child: DecoratedBox(
                            decoration: BoxDecoration(
                              color: Colors.white,
                              borderRadius: BorderRadius.circular(12),
                              border: Border.all(
                                color: const Color(0xffd2d2d7),
                              ),
                            ),
                            child: ClipRRect(
                              borderRadius: BorderRadius.circular(12),
                              child: Listener(
                                key: const ValueKey('signature-canvas'),
                                behavior: HitTestBehavior.opaque,
                                onPointerDown: (event) => _start(event, size),
                                onPointerMove: (event) => _move(event, size),
                                onPointerUp: _end,
                                onPointerCancel: _end,
                                child: Stack(
                                  fit: StackFit.expand,
                                  children: [
                                    CustomPaint(
                                      painter: SignaturePainter(_strokes),
                                    ),
                                    const Positioned(
                                      left: 20,
                                      right: 20,
                                      bottom: 32,
                                      child: IgnorePointer(child: Divider()),
                                    ),
                                    const Positioned(
                                      right: 20,
                                      bottom: 10,
                                      child: IgnorePointer(
                                        child: Text(
                                          'Hier unterschreiben',
                                          style: TextStyle(
                                            fontSize: 10,
                                            color: OfficeColors.muted,
                                          ),
                                        ),
                                      ),
                                    ),
                                  ],
                                ),
                              ),
                            ),
                          ),
                        );
                      },
                    ),
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    ),
  );
}

class SignaturePainter extends CustomPainter {
  final List<List<Offset>> strokes;

  SignaturePainter(this.strokes);

  @override
  void paint(Canvas canvas, Size size) {
    final paint = Paint()
      ..color = const Color(0xff172b38)
      ..strokeWidth = 2
      ..style = PaintingStyle.stroke
      ..strokeCap = StrokeCap.round;
    for (final stroke in strokes) {
      if (stroke.length < 2) continue;
      final path = Path()
        ..moveTo(stroke.first.dx * size.width, stroke.first.dy * size.height);
      for (final point in stroke.skip(1)) {
        path.lineTo(point.dx * size.width, point.dy * size.height);
      }
      canvas.drawPath(path, paint);
    }
  }

  @override
  bool shouldRepaint(covariant SignaturePainter oldDelegate) => true;
}

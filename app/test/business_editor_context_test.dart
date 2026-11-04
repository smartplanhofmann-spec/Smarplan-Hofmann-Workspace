import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:smartplan_office/api.dart';
import 'package:smartplan_office/business_session.dart';
import 'package:smartplan_office/business_widgets.dart';

import 'business_session_test.dart' show BusinessTestApi;

// Instrument subscriptions only; all authorization, command and pending-value
// behavior is the production BusinessSession implementation.
class ListenerSession extends BusinessSession {
  ListenerSession({required super.api});
  final subscriptions = <VoidCallback>[];

  @override
  void addListener(VoidCallback listener) {
    subscriptions.add(listener);
    super.addListener(listener);
  }

  @override
  void removeListener(VoidCallback listener) {
    subscriptions.remove(listener);
    super.removeListener(listener);
  }
}

class EditorContext {
  const EditorContext(this.session, this.key, {this.pendingSession});
  final BusinessSession session;
  final BusinessSession? pendingSession;
  final String key;
  BusinessSession get owner => pendingSession ?? session;
}

class EditorHarness {
  final firstApi = BusinessTestApi(), nextApi = BusinessTestApi();
  late final first = ListenerSession(api: firstApi);
  late final next = ListenerSession(api: nextApi);
  late final current = ValueNotifier(EditorContext(first, 'editor-original'));
  final results = <bool?>[];
  static const original = {'title': 'Private synthetic original draft'};
  static const replacement = {'title': 'Separate synthetic replacement draft'};
  static const invalidated =
      'Die Sitzung oder der Vorgang wurde gewechselt. Bitte die Erfassung neu öffnen.';

  Future<void> open(WidgetTester t) async {
    await Future.wait([first.load(), next.load()]);
    await t.pumpWidget(
      MaterialApp(
        home: Builder(
          builder: (context) => Scaffold(
            body: TextButton(
              onPressed: () async {
                final result = await showDialog<bool>(
                  context: context,
                  builder: (_) => ValueListenableBuilder<EditorContext>(
                    valueListenable: current,
                    builder: (_, value, _) => BusinessEditor(
                      session: value.session,
                      pendingSession: value.pendingSession,
                      pendingKey: value.key,
                      title: 'Synthetic editor review',
                      readPermission: 'documents.read',
                      fields: const [
                        BusinessField('title', 'Titel', required: true),
                      ],
                      initial: original,
                      onSave: (fields) async {
                        await value.owner.command(
                          value.key,
                          '/documents',
                          fields,
                        );
                      },
                    ),
                  ),
                );
                results.add(result);
              },
              child: const Text('Editor öffnen'),
            ),
          ),
        ),
      ),
    );
    await t.tap(find.text('Editor öffnen'));
    await t.pumpAndSettle();
    expect(find.byType(BusinessEditor), findsOneWidget);
    expect(first.subscriptions, hasLength(1));
  }

  EditorContext replacementFor(String change) => switch (change) {
    'session' => EditorContext(next, 'editor-original'),
    'pendingSession' => EditorContext(
      first,
      'editor-original',
      pendingSession: next,
    ),
    'pendingKey' => EditorContext(first, 'editor-next'),
    _ => throw ArgumentError.value(change),
  };

  Future<void> seedReplacement(EditorContext context) async {
    final api = identical(context.owner, first) ? firstApi : nextApi;
    api.loseAck = true;
    await expectLater(
      context.owner.command(context.key, '/documents', replacement),
      throwsA(isA<ApiException>().having((e) => e.status, 'status', 0)),
    );
    context.owner.preservePendingEditor(context.key, replacement);
    expect(context.owner.pendingEditorValues(context.key), replacement);
  }

  Future<Completer<dynamic>> beginSave(WidgetTester t) async {
    final held = Completer<dynamic>();
    firstApi.delayed = held;
    await t.tap(find.text('Speichern'));
    await t.pump();
    expect(first.pending('editor-original'), isTrue);
    expect(firstApi.calls.last.body?['title'], original['title']);
    expect(results, isEmpty);
    return held;
  }

  Future<void> switchTo(WidgetTester t, EditorContext value) async {
    current.value = value;
    await t.pumpAndSettle();
    expect(find.text(invalidated), findsOneWidget);
    expect(find.byType(TextFormField), findsNothing);
    expect(find.text(original['title']!), findsNothing);
    expect(t.widget<FilledButton>(find.byType(FilledButton)).onPressed, isNull);
    expect(results, isEmpty);
  }

  Future<void> dispose(WidgetTester t) async {
    if (firstApi.delayed case final pending? when !pending.isCompleted) {
      pending.complete({'id': 'a' * 32, 'revision': 1});
      await t.pumpAndSettle();
    }
    await t.pumpWidget(const SizedBox.shrink());
    current.dispose();
    first.dispose();
    next.dispose();
    firstApi.dispose();
    nextApi.dispose();
  }
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  testWidgets('editor transfers only its listener on session replacement', (
    t,
  ) async {
    final h = EditorHarness();
    try {
      await h.open(t);
      expect(h.next.subscriptions, isEmpty);
      await h.switchTo(t, h.replacementFor('session'));
      expect(h.first.subscriptions, isEmpty);
      expect(h.next.subscriptions, hasLength(1));
      h.first.revoke();
      await t.pumpAndSettle();
      expect(find.text(EditorHarness.invalidated), findsOneWidget);
      await t.tap(find.text('Schließen'));
      await t.pumpAndSettle();
      expect(h.results, [null]);
      expect(h.first.subscriptions, isEmpty);
      expect(h.next.subscriptions, isEmpty);
      expect(t.takeException(), isNull);
    } finally {
      await h.dispose(t);
    }
  });

  for (final change in ['session', 'pendingSession', 'pendingKey']) {
    for (final outcome in ['success', 'rejected', 'unconfirmed', 'format']) {
      testWidgets('editor ignores late $outcome after $change replacement', (
        t,
      ) async {
        final h = EditorHarness();
        const secret = 'Synthetic private delayed response';
        try {
          await h.open(t);
          final replacement = h.replacementFor(change);
          await h.seedReplacement(replacement);
          final held = await h.beginSave(t);
          final request = Map<String, dynamic>.from(
            h.firstApi.calls.last.body!,
          );
          await h.switchTo(t, replacement);
          if (outcome == 'success') {
            held.complete({'id': 'a' * 32, 'revision': 1});
          } else if (outcome == 'format') {
            held.completeError(const FormatException(secret));
          } else {
            held.completeError(
              ApiException(outcome == 'rejected' ? 400 : 0, secret),
            );
          }
          await t.pumpAndSettle();
          expect(find.text(secret), findsNothing);
          expect(find.text(EditorHarness.invalidated), findsOneWidget);
          expect(find.byType(BusinessEditor), findsOneWidget);
          expect(find.byType(TextFormField), findsNothing);
          expect(
            h.results,
            isEmpty,
            reason: 'An old save cannot pop this route.',
          );
          expect(
            replacement.owner.pendingEditorValues(replacement.key),
            EditorHarness.replacement,
          );
          if (outcome == 'unconfirmed') {
            expect(
              h.first.pendingEditorValues('editor-original'),
              EditorHarness.original,
            );
            h.firstApi.delayed = null;
            await h.first.command(
              'editor-original',
              '/documents',
              EditorHarness.original,
            );
            expect(h.firstApi.calls.last.body, request);
            expect(h.first.pending('editor-original'), isFalse);
            expect(h.first.pendingEditorValues('editor-original'), isNull);
            expect(
              replacement.owner.pendingEditorValues(replacement.key),
              EditorHarness.replacement,
            );
          } else if (outcome != 'format') {
            expect(h.first.pending('editor-original'), isFalse);
            expect(h.first.pendingEditorValues('editor-original'), isNull);
          }
          expect(t.takeException(), isNull);
        } finally {
          await h.dispose(t);
        }
      });
    }
  }

  testWidgets('same-context save still closes with a confirmed result', (
    t,
  ) async {
    final h = EditorHarness();
    try {
      await h.open(t);
      final held = await h.beginSave(t);
      held.complete({'id': 'a' * 32, 'revision': 1});
      await t.pumpAndSettle();
      expect(find.byType(BusinessEditor), findsNothing);
      expect(h.results, [true]);
      expect(h.first.pending('editor-original'), isFalse);
      expect(h.first.subscriptions, isEmpty);
      expect(t.takeException(), isNull);
    } finally {
      await h.dispose(t);
    }
  });

  testWidgets('same-context uncertain save preserves and repeats exact input', (
    t,
  ) async {
    final h = EditorHarness();
    try {
      await h.open(t);
      final held = await h.beginSave(t);
      final request = Map<String, dynamic>.from(h.firstApi.calls.last.body!);
      held.completeError(const ApiException(0, 'Synthetic response missing'));
      await t.pumpAndSettle();
      expect(find.text('Synthetic response missing'), findsOneWidget);
      expect(find.text('Erneut senden'), findsOneWidget);
      expect(
        h.first.pendingEditorValues('editor-original'),
        EditorHarness.original,
      );
      h.firstApi.delayed = null;
      await t.tap(find.text('Erneut senden'));
      await t.pumpAndSettle();
      expect(h.firstApi.calls.last.body, request);
      expect(h.results, [true]);
      expect(h.first.pending('editor-original'), isFalse);
      expect(h.first.pendingEditorValues('editor-original'), isNull);
      expect(t.takeException(), isNull);
    } finally {
      await h.dispose(t);
    }
  });

  testWidgets(
    'late failure cannot restore values in a revoked original owner',
    (t) async {
      final h = EditorHarness();
      try {
        await h.open(t);
        final replacement = h.replacementFor('session');
        await h.seedReplacement(replacement);
        final held = await h.beginSave(t);
        await h.switchTo(t, replacement);
        h.firstApi.logout();
        held.completeError(const ApiException(0, 'Synthetic revoked response'));
        await t.pumpAndSettle();
        expect(h.first.allowed, isFalse);
        expect(h.first.pending('editor-original'), isFalse);
        expect(h.first.pendingEditorValues('editor-original'), isNull);
        expect(
          replacement.owner.pendingEditorValues(replacement.key),
          EditorHarness.replacement,
        );
        expect(find.text('Synthetic revoked response'), findsNothing);
        expect(h.results, isEmpty);
        expect(t.takeException(), isNull);
      } finally {
        await h.dispose(t);
      }
    },
  );

  testWidgets(
    'late old command failure cannot overwrite a newer command at the same key',
    (t) async {
      final h = EditorHarness();
      try {
        await h.open(t);
        final held = await h.beginSave(t);
        final originalRequest = Map<String, dynamic>.from(
          h.firstApi.calls.last.body!,
        );
        await h.switchTo(t, h.replacementFor('session'));

        // A second authorized view resolves the very same operation, then
        // starts a different operation under this editor's reusable key.
        h.firstApi.delayed = null;
        await h.first.command(
          'editor-original',
          '/documents',
          EditorHarness.original,
        );
        expect(h.firstApi.calls.last.body, originalRequest);
        expect(h.first.pending('editor-original'), isFalse);
        h.firstApi.loseAck = true;
        await expectLater(
          h.first.command(
            'editor-original',
            '/documents',
            EditorHarness.replacement,
          ),
          throwsA(isA<ApiException>().having((e) => e.status, 'status', 0)),
        );
        h.first.preservePendingEditor(
          'editor-original',
          EditorHarness.replacement,
        );
        final replacementRequest = Map<String, dynamic>.from(
          h.firstApi.calls.last.body!,
        );
        expect(
          replacementRequest['request_id'],
          isNot(originalRequest['request_id']),
        );
        held.completeError(
          const ApiException(0, 'Old synthetic request failed'),
        );
        await t.pumpAndSettle();
        expect(
          h.first.pendingCommandValues('editor-original', path: '/documents'),
          EditorHarness.replacement,
        );
        expect(
          h.first.pendingEditorValues('editor-original'),
          EditorHarness.replacement,
          reason: 'A completed older request must not replace the newer draft.',
        );
        expect(find.text('Old synthetic request failed'), findsNothing);
        expect(h.results, isEmpty);
        expect(t.takeException(), isNull);
      } finally {
        await h.dispose(t);
      }
    },
  );

  testWidgets(
    'pre-command changed-body conflict cannot overwrite the existing pending draft',
    (t) async {
      final h = EditorHarness();
      try {
        await h.open(t);
        await h.seedReplacement(EditorContext(h.first, 'editor-original'));
        final before = h.firstApi.calls.length;
        final replacementRequest = Map<String, dynamic>.from(
          h.firstApi.calls.last.body!,
        );
        await t.tap(find.text('Speichern'));
        await t.pumpAndSettle();
        expect(h.firstApi.calls.length, before);
        expect(
          h.first.pendingCommandValues('editor-original', path: '/documents'),
          EditorHarness.replacement,
        );
        expect(
          h.first.pendingEditorValues('editor-original'),
          EditorHarness.replacement,
          reason:
              'A rejected different draft did not submit this pending command.',
        );
        await h.first.command(
          'editor-original',
          '/documents',
          EditorHarness.replacement,
        );
        expect(h.firstApi.calls.last.body, replacementRequest);
        expect(h.results, isEmpty);
        expect(t.takeException(), isNull);
      } finally {
        await h.dispose(t);
      }
    },
  );
}

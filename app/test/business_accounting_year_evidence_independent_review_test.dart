import 'dart:async';
import 'dart:convert';
import 'dart:io';
import 'dart:typed_data';

import 'package:file_selector_platform_interface/file_selector_platform_interface.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:smartplan_office/api.dart';
import 'package:smartplan_office/business_accounting_year_evidence.dart';
import 'package:smartplan_office/business_session.dart';

import 'business_accounting_year_evidence_test.dart' as actual;

/// The plugin boundary alone is controlled. These tests execute the production
/// desktop branch, including its post-picker authorization and actual File IO.
class ReviewSavePicker extends FileSelectorPlatform {
  final answer = Completer<FileSaveLocation?>();
  int calls = 0;
  String? suggested;
  @override
  Future<FileSaveLocation?> getSaveLocation({
    List<XTypeGroup>? acceptedTypeGroups,
    SaveDialogOptions options = const SaveDialogOptions(),
  }) {
    calls++;
    suggested = options.suggestedName;
    return answer.future;
  }
}

class ReviewYearApi extends actual.YearEvidenceApi {
  Completer<dynamic>? heldOriginal;
  bool denyOneSource = false;
  int sourceDenials = 0, originalReads = 0;
  Map<String, dynamic>? differentOriginal;
  @override
  Future<dynamic> call(String path, [Map<String, dynamic>? body]) async {
    if (path.endsWith('/evidence') && denyOneSource) {
      sourceDenials++;
      throw const ApiException(403, 'Synthetic one original source denied');
    }
    if (path.endsWith('/exports/${entry['id']}')) {
      originalReads++;
      if (heldOriginal != null) return heldOriginal!.future;
      if (differentOriginal != null) return differentOriginal;
    }
    return super.call(path, body);
  }
}

Future<void> flushFileIO(WidgetTester t) async {
  for (var i = 0; i < 35; i++) {
    await t.runAsync(
      () => Future<void>.delayed(const Duration(milliseconds: 8)),
    );
    await t.pump(const Duration(milliseconds: 10));
  }
  await t.pumpAndSettle();
}

const saveLabel = 'Original-/Journal-ZIP speichern';
const savedLabel =
    'ZIPdatei nach Größe und SHA-256 für die Dateiausgabe abgeglichen.';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  late FileSelectorPlatform previousPicker;
  late ReviewSavePicker picker;
  late Directory temporary;
  setUp(() {
    previousPicker = FileSelectorPlatform.instance;
    FileSelectorPlatform.instance = picker = ReviewSavePicker();
    temporary = Directory.systemTemp.createTempSync(
      'synthetic-independent-year-',
    );
  });
  tearDown(() {
    FileSelectorPlatform.instance = previousPicker;
    temporary.deleteSync(recursive: true);
  });

  testWidgets(
    'independent real desktop output retains actual historical bytes and external hash',
    (t) async {
      final api = ReviewYearApi(), session = BusinessSession(api: api);
      api.scenario = 'old_after_profile_change';
      final output = File('${temporary.path}/verified.zip');
      await actual.mountYear(t, api, session);
      await actual.yearTap(t, saveLabel, settle: false);
      expect(picker.calls, 1);
      expect(picker.suggested, api.f['metadata']['filename']);
      final readsBeforeSelection = api.metadataReads;
      picker.answer.complete(FileSaveLocation(output.path));
      await flushFileIO(t);
      expect(api.metadataReads, greaterThan(readsBeforeSelection));
      expect(output.readAsBytesSync(), base64Decode(api.f['archive_base64']));
      expect(
        yearEvidenceAttachment(
          output.readAsBytesSync(),
          api.f['metadata'],
          api.entry,
        ).sha256,
        api.f['metadata']['sha256'],
      );
      expect(find.text(savedLabel), findsOneWidget);
      expect(
        find.textContaining('keine eigenständige Vollständigkeit'),
        findsOneWidget,
      );
      expect(api.posts, 0);
      await actual.closeYear(t, session);
    },
  );

  for (final change in [
    'source_right',
    'external_hash',
    'session',
    'export',
    'background',
    'dispose',
    'token',
  ]) {
    testWidgets('independent actual picker discards old bytes after $change', (
      t,
    ) async {
      final api = ReviewYearApi(), session = BusinessSession(api: api);
      BusinessSession? replacement;
      final output = File('${temporary.path}/must-not-write.zip');
      await actual.mountYear(t, api, session);
      await actual.yearTap(t, saveLabel, settle: false);
      expect(picker.calls, 1);
      expect(api.byteReads, 1);
      switch (change) {
        case 'source_right':
          api.denyOneSource = true;
        case 'external_hash':
          api.overrideMetadata = {...api.f['metadata'], 'sha256': '0' * 64};
        case 'session':
          final other = ReviewYearApi();
          other.token = 'different-synthetic-session';
          replacement = BusinessSession(api: other);
          await replacement.load();
          await t.pumpWidget(
            MaterialApp(
              home: BusinessYearEvidencePage(
                session: replacement,
                exportEntry: other.entry,
              ),
            ),
          );
        case 'export':
          api.scenario = 'incomplete_year';
          await t.pumpWidget(
            MaterialApp(
              home: BusinessYearEvidencePage(
                session: session,
                exportEntry: api.entry,
              ),
            ),
          );
        case 'background':
          t.binding.handleAppLifecycleStateChanged(AppLifecycleState.hidden);
          await t.pump();
        case 'dispose':
          await t.pumpWidget(
            const MaterialApp(home: Scaffold(body: Text('Neutral home'))),
          );
        case 'token':
          api.token = 'different-synthetic-session';
          await session.load();
      }
      picker.answer.complete(FileSaveLocation(output.path));
      await flushFileIO(t);
      expect(output.existsSync(), false);
      expect(find.text(savedLabel), findsNothing);
      expect(api.posts, 0);
      if (change == 'source_right') {
        expect(session.can('finance.read'), true);
        expect(api.sourceDenials, 1);
        expect(find.text(api.f['metadata']['filename']), findsNothing);
        expect(
          find.textContaining('derzeit nicht freigegeben'),
          findsOneWidget,
        );
      }
      if (change == 'export') {
        expect(find.text(api.f['metadata']['filename']), findsOneWidget);
        expect(
          find.textContaining('damalige Jahresstand war unvollständig'),
          findsOneWidget,
        );
      }
      if (change == 'background') {
        t.binding.handleAppLifecycleStateChanged(AppLifecycleState.resumed);
        await t.pump();
        expect(find.text(api.f['metadata']['filename']), findsNothing);
      }
      if (replacement != null) {
        session.dispose();
        await actual.closeYear(t, replacement);
      } else {
        await actual.closeYear(t, session);
      }
    });
  }

  testWidgets(
    'independent real write failure cannot report success or overwrite original metadata',
    (t) async {
      final api = ReviewYearApi(), session = BusinessSession(api: api);
      await actual.mountYear(t, api, session);
      await actual.yearTap(t, saveLabel, settle: false);
      picker.answer.complete(
        FileSaveLocation(temporary.path),
      ); // Existing directory: genuine FileSystemException.
      await flushFileIO(t);
      expect(find.text(savedLabel), findsNothing);
      expect(find.text(api.f['metadata']['filename']), findsNothing);
      expect(temporary.listSync(), isEmpty);
      expect(t.takeException(), null);
      FileSelectorPlatform.instance = picker = ReviewSavePicker();
      await actual.yearTap(t, 'Originalnachweis erneut lesen');
      await actual.yearTap(t, saveLabel, settle: false);
      final output = File('${temporary.path}/retry.zip');
      picker.answer.complete(FileSaveLocation(output.path));
      await flushFileIO(t);
      expect(output.readAsBytesSync(), base64Decode(api.f['archive_base64']));
      expect(api.posts, 0);
      await actual.closeYear(t, session);
    },
  );

  testWidgets(
    'independent picker cancellation has no file or success assertion',
    (t) async {
      final api = ReviewYearApi(), session = BusinessSession(api: api);
      await actual.mountYear(t, api, session);
      await actual.yearTap(t, saveLabel, settle: false);
      picker.answer.complete(null);
      await flushFileIO(t);
      expect(temporary.listSync(), isEmpty);
      expect(find.text(savedLabel), findsNothing);
      expect(find.text(api.f['metadata']['filename']), findsOneWidget);
      await actual.closeYear(t, session);
    },
  );

  for (final change in ['token', 'background', 'session', 'export']) {
    testWidgets(
      'independent late initial original response cannot revive $change context',
      (t) async {
        final api = ReviewYearApi(), session = BusinessSession(api: api);
        final originalResponse = yearEvidenceCopy(api.f['export']);
        final originalName = api.f['metadata']['filename'];
        api.heldOriginal = Completer<dynamic>();
        await session.load();
        await t.pumpWidget(
          MaterialApp(
            home: BusinessYearEvidencePage(
              session: session,
              exportEntry: api.entry,
            ),
          ),
        );
        await t.pump();
        expect(api.originalReads, 1);
        expect(api.metadataReads, 0);
        BusinessSession? replacement;
        if (change == 'token') {
          api.token = 'replacement-token';
          await session.load();
        } else if (change == 'background') {
          t.binding.handleAppLifecycleStateChanged(AppLifecycleState.paused);
        } else if (change == 'session') {
          final other = ReviewYearApi()..scenario = 'public_payroll';
          replacement = BusinessSession(api: other);
          await replacement.load();
          await t.pumpWidget(
            MaterialApp(
              home: BusinessYearEvidencePage(
                session: replacement,
                exportEntry: other.entry,
              ),
            ),
          );
        } else {
          api.scenario = 'incomplete_year';
          final pending = api.heldOriginal!;
          api.heldOriginal = null;
          await t.pumpWidget(
            MaterialApp(
              home: BusinessYearEvidencePage(
                session: session,
                exportEntry: api.entry,
              ),
            ),
          );
          pending.complete(originalResponse);
        }
        if (api.heldOriginal != null)
          api.heldOriginal!.complete(originalResponse);
        await t.pumpAndSettle();
        expect(find.text(originalName), findsNothing);
        expect(picker.calls, 0);
        expect(api.byteReads, 0);
        if (change == 'background') {
          t.binding.handleAppLifecycleStateChanged(AppLifecycleState.resumed);
          await t.pump();
          expect(find.text(originalName), findsNothing);
        }
        if (replacement != null) {
          session.dispose();
          await actual.closeYear(t, replacement);
        } else {
          await actual.closeYear(t, session);
        }
      },
    );
  }

  testWidgets(
    'independent foreign original response is rejected before archive metadata or picker',
    (t) async {
      final api = ReviewYearApi(), session = BusinessSession(api: api);
      api.differentOriginal = yearEvidenceCopy(
        actual.yearFixtures['scenarios']['incomplete_year']['export'],
      );
      await actual.mountYear(t, api, session);
      expect(api.originalReads, 1);
      expect(api.metadataReads, 0);
      expect(api.byteReads, 0);
      expect(picker.calls, 0);
      expect(find.text(saveLabel), findsNothing);
      await actual.closeYear(t, session);
    },
  );

  testWidgets(
    'independent downloaded altered archive never substitutes its self-supplied hash',
    (t) async {
      final api = ReviewYearApi(), session = BusinessSession(api: api);
      await actual.mountYear(t, api, session);
      final expectedHash = api.f['metadata']['sha256'];
      api.heldBytes = Completer<Uint8List>();
      await actual.yearTap(t, saveLabel, settle: false);
      final altered = base64Decode(api.f['archive_base64']);
      altered[altered.length ~/ 2] ^= 1;
      api.heldBytes!.complete(altered);
      await t.pumpAndSettle();
      expect(picker.calls, 0);
      expect(temporary.listSync(), isEmpty);
      expect(find.text(savedLabel), findsNothing);
      expect(api.f['metadata']['sha256'], expectedHash);
      expect(api.posts, 0);
      await actual.closeYear(t, session);
    },
  );
}

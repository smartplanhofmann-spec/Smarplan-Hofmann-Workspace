import 'dart:async';
import 'dart:convert';
import 'dart:io';
import 'dart:typed_data';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:smartplan_office/api.dart';
import 'package:smartplan_office/business_accounting_year_evidence.dart';
import 'package:smartplan_office/business_session.dart';
import 'package:smartplan_office/mail_attachment_widgets.dart';

final yearFixtures = yearEvidenceCopy(
  jsonDecode(
    File('test/fixtures/accounting_year_package_v1.json').readAsStringSync(),
  ),
);

/// Reads only the known uncompressed actual fixture, never extracts or executes
/// any archive content. Production downloads only bind bytes to server metadata.
Map<String, dynamic> fixtureYearEntry(Map<String, dynamic> scenario) {
  final raw = base64Decode(scenario['archive_base64']),
      data = ByteData.sublistView(raw);
  int cursor = 0;
  while (cursor + 30 <= raw.length &&
      data.getUint32(cursor, Endian.little) == 0x04034b50) {
    final length = data.getUint32(cursor + 18, Endian.little),
        nameLength = data.getUint16(cursor + 26, Endian.little),
        extra = data.getUint16(cursor + 28, Endian.little);
    expect(data.getUint16(cursor + 8, Endian.little), 0);
    final name = utf8.decode(
      raw.sublist(cursor + 30, cursor + 30 + nameLength),
    );
    final start = cursor + 30 + nameLength + extra;
    if (name == 'journal.json') {
      final journal = jsonDecode(
        utf8.decode(raw.sublist(start, start + length)),
      );
      return yearEvidenceCopy(
        (journal['decisions'] as List).singleWhere(
          (v) => v['entry']['id'] == scenario['export']['entry_id'],
        )['entry'],
      );
    }
    cursor = start + length;
  }
  throw StateError('Actual fixture journal not found');
}

class YearEvidenceApi extends OfficeApi {
  YearEvidenceApi({this.scenario = 'ordinary_correction'})
    : super(apiVersion: 'v1') {
    token = 'synthetic-year-reader';
  }
  String scenario;
  bool read = true, feature = true, loseBytes = false;
  int generation = 1, metadataReads = 0, byteReads = 0, posts = 0;
  Completer<dynamic>? heldMetadata;
  Completer<Uint8List>? heldBytes;
  Map<String, dynamic>? overrideMetadata;
  Map<String, dynamic> get f => yearFixtures['scenarios'][scenario];
  Map<String, dynamic> get entry => fixtureYearEntry(f);
  @override
  Future<dynamic> call(String path, [Map<String, dynamic>? body]) async {
    if (body != null) posts++;
    if (path.endsWith('/capabilities'))
      return {
        'compatibility_mode': 'business',
        'generation': generation,
        'storage_version': 16,
        'readonly': false,
        'features': [if (feature) 'accounting_year_evidence_v1'],
        'capabilities': ['business_accounting_euer'],
        'permissions': ['accounting.read', if (read) 'finance.read'],
      };
    if (path.endsWith('/evidence')) {
      metadataReads++;
      return heldMetadata?.future ??
          yearEvidenceCopy(overrideMetadata ?? f['metadata']);
    }
    if (path.endsWith('/exports/${entry['id']}'))
      return yearEvidenceCopy(f['export']);
    throw StateError('Unexpected year route $path');
  }

  @override
  Future<Uint8List> bytes(
    String path, {
    required String mediaType,
    int maxBytes = 20 * 1024 * 1024,
  }) async {
    expect(path, '/api/business${f['metadata']['archive_path']}');
    expect(mediaType, 'application/zip');
    expect(maxBytes, yearEvidenceMaxBytes);
    byteReads++;
    if (loseBytes) {
      loseBytes = false;
      throw const ApiException(0, 'Synthetic archive reply lost');
    }
    return heldBytes?.future ?? base64Decode(f['archive_base64']);
  }
}

Future<void> yearTap(WidgetTester t, String label, {bool settle = true}) async {
  final finder = find.text(label), scroll = find.byType(Scrollable).first;
  t.state<ScrollableState>(scroll).position.jumpTo(0);
  await t.pump();
  await t.scrollUntilVisible(finder, 250, scrollable: scroll);
  await t.ensureVisible(finder.first);
  await t.pumpAndSettle();
  await t.tap(finder.first);
  await t.pump();
  if (settle) await t.pumpAndSettle();
}

Future<void> mountYear(
  WidgetTester t,
  YearEvidenceApi api,
  BusinessSession s, {
  Future<void> Function(VerifiedMailAttachment, Future<bool> Function())? save,
}) async {
  await s.load();
  await t.pumpWidget(
    MaterialApp(
      home: BusinessYearEvidencePage(
        session: s,
        exportEntry: api.entry,
        exportFile: save,
      ),
    ),
  );
  await t.pumpAndSettle();
}

Future<void> closeYear(WidgetTester t, BusinessSession s) async {
  await t.pumpWidget(const SizedBox.shrink());
  s.dispose();
  expect(t.takeException(), null);
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  for (final name in (yearFixtures['scenarios'] as Map).keys) {
    test(
      'actual $name export, immutable journal hash, metadata and exact ZIP bytes',
      () {
        final f = yearFixtures['scenarios'][name], e = fixtureYearEntry(f);
        expect(yearEvidenceOriginalExport(f['export'], e), f['export']);
        expect(yearEvidenceMetadata(f['metadata'], e), f['metadata']);
        final archive = yearEvidenceAttachment(
          base64Decode(f['archive_base64']),
          f['metadata'],
          e,
        );
        expect(archive.sha256, f['metadata']['sha256']);
        expect(archive.bytes.length, f['metadata']['size']);
      },
    );
  }
  test('old export bytes remain identical after actual profile change', () {
    final scenarios = yearFixtures['scenarios'];
    expect(
      scenarios['old_after_profile_change']['archive_base64'],
      scenarios['ordinary_correction']['archive_base64'],
    );
    expect(
      scenarios['old_after_profile_change']['metadata'],
      scenarios['ordinary_correction']['metadata'],
    );
  });
  test('foreign export, completeness, unsafe path and excessive limits are rejected', () {
    final f = yearFixtures['scenarios']['ordinary_correction'],
        e = fixtureYearEntry(f);
    for (final change in [
      {'export_id': 'f' * 32},
      {'export_hash': 'a' * 64},
      {'year': 2025},
      {'instance_id': 'invalid'},
      {'archive_path': 'https://foreign.example.test/a.zip'},
      {'filename': '../../a.zip'},
      {'size': yearEvidenceMaxBytes + 1},
      {'original_count': 9994},
      {'original_year_complete': false},
      {'private_personnel_originals_included': true},
      {'unknown': true},
    ])
      expect(
        () => yearEvidenceMetadata({...f['metadata'], ...change}, e),
        throwsA(isA<ApiException>()),
      );
  });
  for (final name in ['public_payroll', 'public_travel'])
    test('$name original public source boundary cannot be hidden', () {
      final f = yearFixtures['scenarios'][name], e = fixtureYearEntry(f);
      expect(
        () => yearEvidenceMetadata({
          ...f['metadata'],
          'private_source_boundaries': [],
        }, e),
        throwsA(isA<ApiException>()),
      );
    });
  test('download rejects equal-sized foreign ZIP and changed second instance metadata', () {
    final f = yearFixtures['scenarios']['ordinary_correction'],
        e = fixtureYearEntry(f),
        bytes = base64Decode(f['archive_base64']);
    bytes[200] ^= 1;
    expect(
      () => yearEvidenceAttachment(bytes, f['metadata'], e),
      throwsA(isA<ApiException>()),
    );
    expect(
      () => yearEvidenceMetadata(
        {...f['metadata'], 'instance_id': 'f' * 32},
        e,
        previous: f['metadata'],
      ),
      throwsA(isA<ApiException>()),
    );
  });
  testWidgets(
    '390px old incomplete year stays incomplete and successful read-only download rechecks metadata',
    (t) async {
      await t.binding.setSurfaceSize(const Size(390, 844));
      final api = YearEvidenceApi(scenario: 'incomplete_year'),
          s = BusinessSession(api: api),
          saved = <VerifiedMailAttachment>[];
      await mountYear(
        t,
        api,
        s,
        save: (a, authorize) async {
          if (await authorize()) saved.add(a);
        },
      );
      expect(
        find.textContaining('damalige Jahresstand war unvollständig'),
        findsOneWidget,
      );
      await yearTap(t, 'Original-/Journal-ZIP speichern');
      expect(saved.single.bytes, base64Decode(api.f['archive_base64']));
      expect(api.metadataReads, greaterThanOrEqualTo(4));
      expect(api.posts, 0);
      await closeYear(t, s);
      await t.binding.setSurfaceSize(null);
    },
  );
  testWidgets(
    'unknown archive response is retried as same original read without any command',
    (t) async {
      final api = YearEvidenceApi()..loseBytes = true,
          s = BusinessSession(api: api),
          saved = <VerifiedMailAttachment>[];
      await mountYear(
        t,
        api,
        s,
        save: (a, authorize) async {
          if (await authorize()) saved.add(a);
        },
      );
      await yearTap(t, 'Original-/Journal-ZIP speichern');
      expect(saved, isEmpty);
      await yearTap(t, 'Originalnachweis erneut lesen');
      await yearTap(t, 'Original-/Journal-ZIP speichern');
      expect(saved.single.sha256, api.f['metadata']['sha256']);
      expect(api.byteReads, 2);
      expect(api.posts, 0);
      await closeYear(t, s);
    },
  );
  for (final change in ['read', 'background', 'generation'])
    testWidgets('held ZIP is discarded after $change context change', (
      t,
    ) async {
      final api = YearEvidenceApi(),
          s = BusinessSession(api: api),
          saved = <VerifiedMailAttachment>[];
      await mountYear(
        t,
        api,
        s,
        save: (a, authorize) async {
          if (await authorize()) saved.add(a);
        },
      );
      api.heldBytes = Completer<Uint8List>();
      await yearTap(t, 'Original-/Journal-ZIP speichern', settle: false);
      if (change == 'read') {
        api.read = false;
      } else if (change == 'generation') {
        api.generation++;
        await s.load();
      } else {
        t.binding.handleAppLifecycleStateChanged(AppLifecycleState.paused);
        await t.pump();
      }
      api.heldBytes!.complete(base64Decode(api.f['archive_base64']));
      await t.pumpAndSettle();
      expect(saved, isEmpty);
      expect(find.text(api.f['metadata']['filename']), findsNothing);
      if (change == 'background') {
        t.binding.handleAppLifecycleStateChanged(AppLifecycleState.resumed);
        await t.pump();
        expect(find.text(api.f['metadata']['filename']), findsNothing);
      }
      await closeYear(t, s);
    });
  testWidgets(
    'silent source-right loss during file chooser is rechecked before actual save',
    (t) async {
      final api = YearEvidenceApi(),
          s = BusinessSession(api: api),
          saved = <VerifiedMailAttachment>[];
      final chooser = Completer<void>();
      await mountYear(
        t,
        api,
        s,
        save: (a, authorize) async {
          await chooser.future;
          if (await authorize()) saved.add(a);
        },
      );
      await yearTap(t, 'Original-/Journal-ZIP speichern', settle: false);
      api.read = false;
      chooser.complete();
      await t.pumpAndSettle();
      expect(saved, isEmpty);
      expect(api.posts, 0);
      await closeYear(t, s);
    },
  );
  testWidgets(
    'late old metadata and errors cannot populate a replacement export screen',
    (t) async {
      final api = YearEvidenceApi(), s = BusinessSession(api: api);
      await s.load();
      api.heldMetadata = Completer<dynamic>();
      await t.pumpWidget(
        MaterialApp(
          home: BusinessYearEvidencePage(session: s, exportEntry: api.entry),
        ),
      );
      await t.pump();
      final other = YearEvidenceApi(scenario: 'public_payroll'),
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
      await t.pumpAndSettle();
      api.heldMetadata!.completeError(
        const ApiException(409, 'Old private original details'),
      );
      await t.pumpAndSettle();
      expect(find.textContaining('Old private'), findsNothing);
      expect(find.text(other.f['metadata']['filename']), findsOneWidget);
      s.dispose();
      await closeYear(t, replacement);
    },
  );
  testWidgets(
    'explicit recheck can recover restored global rights without restoring old private screen state',
    (t) async {
      final api = YearEvidenceApi(), session = BusinessSession(api: api);
      await mountYear(t, api, session);
      api.read = false;
      await session.load();
      await t.pumpAndSettle();
      expect(find.text(api.f['metadata']['filename']), findsNothing);
      api.read = true;
      await t.tap(find.text('Zugriff erneut prüfen'));
      await t.pumpAndSettle();
      expect(find.text(api.f['metadata']['filename']), findsOneWidget);
      await closeYear(t, session);
    },
  );
  testWidgets(
    'held old ZIP cannot save after selecting another valid export in the same session',
    (t) async {
      final api = YearEvidenceApi(),
          session = BusinessSession(api: api),
          saved = <VerifiedMailAttachment>[];
      Future<void> save(
        VerifiedMailAttachment a,
        Future<bool> Function() authorize,
      ) async {
        if (await authorize()) saved.add(a);
      }

      await mountYear(t, api, session, save: save);
      final oldBytes = base64Decode(api.f['archive_base64']);
      api.heldBytes = Completer<Uint8List>();
      await yearTap(t, 'Original-/Journal-ZIP speichern', settle: false);
      api.scenario = 'incomplete_year';
      await t.pumpWidget(
        MaterialApp(
          home: BusinessYearEvidencePage(
            session: session,
            exportEntry: api.entry,
            exportFile: save,
          ),
        ),
      );
      await t.pumpAndSettle();
      api.heldBytes!.complete(oldBytes);
      await t.pumpAndSettle();
      expect(saved, isEmpty);
      expect(find.text(api.f['metadata']['filename']), findsOneWidget);
      expect(
        find.textContaining('damalige Jahresstand war unvollständig'),
        findsOneWidget,
      );
      await closeYear(t, session);
    },
  );
  testWidgets(
    'project-scoped session cannot use the global original-year download',
    (t) async {
      final api = YearEvidenceApi(),
          session = BusinessSession(api: api, projectId: 'f' * 32);
      await mountYear(t, api, session);
      expect(api.metadataReads, 0);
      expect(api.byteReads, 0);
      expect(find.text(api.f['metadata']['filename']), findsNothing);
      expect(find.textContaining('derzeit nicht freigegeben'), findsOneWidget);
      await closeYear(t, session);
    },
  );
}

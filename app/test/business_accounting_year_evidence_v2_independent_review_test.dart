import 'dart:async';
import 'dart:convert';
import 'dart:io';
import 'dart:typed_data';

import 'package:file_selector_platform_interface/file_selector_platform_interface.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:smartplan_office/business_accounting_year_evidence.dart';
import 'package:smartplan_office/business_session.dart';

import 'business_accounting_year_evidence_independent_review_test.dart'
    show ReviewSavePicker, flushFileIO, saveLabel, savedLabel;
import 'business_accounting_year_evidence_test.dart' as actual;

final v2 = yearEvidenceCopy(
  jsonDecode(
    File('test/fixtures/accounting_year_package_v2.json').readAsStringSync(),
  ),
);

class IndependentV2Api extends actual.YearEvidenceApi {
  IndependentV2Api() : super(scenario: 'v2:complete_history');
  @override
  Map<String, dynamic> get f => scenario.startsWith('v2:')
      ? v2['scenarios'][scenario.substring(3)]
      : super.f;
  @override
  Future<dynamic> call(String path, [Map<String, dynamic>? body]) async {
    final value = await super.call(path, body);
    if (path.endsWith('/capabilities')) {
      (value['features'] as List).add('accounting_year_evidence_v2');
    }
    return value;
  }
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  for (final name in (v2['scenarios'] as Map).keys) {
    test(
      'independent actual V2 $name original export and archive stay exact',
      () {
        final scenario = v2['scenarios'][name],
            entry = actual.fixtureYearEntry(scenario);
        expect(
          yearEvidenceOriginalExport(scenario['export'], entry),
          scenario['export'],
        );
        expect(
          yearEvidenceMetadata(scenario['metadata'], entry),
          scenario['metadata'],
        );
        expect(
          yearEvidenceAttachment(
            base64Decode(scenario['archive_base64']),
            scenario['metadata'],
            entry,
          ).sha256,
          scenario['metadata']['sha256'],
        );
        expect(
          scenario['metadata']['original_year_complete'],
          name == 'complete_history',
        );
        for (final foreign in actual.yearFixtures['scenarios'].values) {
          expect(
            () => yearEvidenceMetadata(foreign['metadata'], entry),
            throwsException,
          );
        }
      },
    );
  }

  test('independent V2 earlier partial archive stays byte-identical after actual correction', () {
    expect(
      v2['scenarios']['old_partial_after_correction'],
      v2['scenarios']['partial_coverage'],
    );
  });

  testWidgets(
    'independent V2 actual production desktop write retains trusted complete-history bytes',
    (t) async {
      final previous = FileSelectorPlatform.instance,
          picker = ReviewSavePicker();
      final directory = Directory.systemTemp.createTempSync(
        'synthetic-v2-native-review-',
      );
      final api = IndependentV2Api(), session = BusinessSession(api: api);
      try {
        FileSelectorPlatform.instance = picker;
        await actual.mountYear(t, api, session);
        await actual.yearTap(t, saveLabel, settle: false);
        expect(picker.calls, 1);
        final output = File('${directory.path}/actual-v2.zip');
        picker.answer.complete(FileSaveLocation(output.path));
        await flushFileIO(t);
        expect(output.readAsBytesSync(), base64Decode(api.f['archive_base64']));
        expect(find.text(savedLabel), findsOneWidget);
        expect(api.posts, 0);
      } finally {
        await actual.closeYear(t, session);
        FileSelectorPlatform.instance = previous;
        directory.deleteSync(recursive: true);
      }
    },
  );

  testWidgets(
    'independent V2-to-V1 metadata format replacement after chooser cannot change original contract',
    (t) async {
      final previous = FileSelectorPlatform.instance,
          picker = ReviewSavePicker();
      final directory = Directory.systemTemp.createTempSync(
        'synthetic-v2-native-review-',
      );
      final api = IndependentV2Api(), session = BusinessSession(api: api);
      try {
        FileSelectorPlatform.instance = picker;
        await actual.mountYear(t, api, session);
        await actual.yearTap(t, saveLabel, settle: false);
        expect(picker.calls, 1);
        api.overrideMetadata = {
          ...api.f['metadata'],
          'format': 'smartplan-year-evidence-v1',
        };
        final output = File('${directory.path}/forbidden.zip');
        picker.answer.complete(FileSaveLocation(output.path));
        await flushFileIO(t);
        expect(output.existsSync(), false);
        expect(find.text(savedLabel), findsNothing);
        expect(find.text(api.f['metadata']['filename']), findsNothing);
        expect(api.posts, 0);
      } finally {
        await actual.closeYear(t, session);
        FileSelectorPlatform.instance = previous;
        directory.deleteSync(recursive: true);
      }
    },
  );

  testWidgets(
    'independent pending V2 bytes cannot populate newly selected real V1 export',
    (t) async {
      final previous = FileSelectorPlatform.instance,
          picker = ReviewSavePicker();
      final api = IndependentV2Api(), session = BusinessSession(api: api);
      try {
        FileSelectorPlatform.instance = picker;
        await actual.mountYear(t, api, session);
        final old = base64Decode(api.f['archive_base64']);
        api.heldBytes = Completer<Uint8List>();
        await actual.yearTap(t, saveLabel, settle: false);
        expect(api.byteReads, 1);
        api.scenario = 'incomplete_year';
        await t.pumpWidget(
          MaterialApp(
            home: BusinessYearEvidencePage(
              session: session,
              exportEntry: api.entry,
            ),
          ),
        );
        await t.pumpAndSettle();
        api.heldBytes!.complete(old);
        await t.pumpAndSettle();
        expect(picker.calls, 0);
        expect(find.text(api.f['metadata']['filename']), findsOneWidget);
        expect(
          find.textContaining('damalige Jahresstand war unvollständig'),
          findsOneWidget,
        );
        expect(find.text(savedLabel), findsNothing);
        expect(api.posts, 0);
      } finally {
        await actual.closeYear(t, session);
        FileSelectorPlatform.instance = previous;
      }
    },
  );
}

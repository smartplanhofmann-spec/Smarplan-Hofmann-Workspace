import 'dart:convert';
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:smartplan_office/business_accounting_year_evidence.dart';

import 'business_accounting_year_evidence_test.dart' show fixtureYearEntry;

void main() {
  final fixture = yearEvidenceCopy(
    jsonDecode(
      File('test/fixtures/accounting_year_package_v2.json').readAsStringSync(),
    ),
  );
  final legacy = yearEvidenceCopy(
    jsonDecode(
      File('test/fixtures/accounting_year_package_v1.json').readAsStringSync(),
    ),
  );
  for (final item in (fixture['scenarios'] as Map).entries) {
    test('actual v2 ${item.key} preserves original export and ZIP', () {
      final value = yearEvidenceCopy(item.value),
          entry = fixtureYearEntry(value);
      yearEvidenceEntry(entry);
      yearEvidenceOriginalExport(value['export'], entry);
      final metadata = yearEvidenceMetadata(value['metadata'], entry);
      expect(metadata['format'], 'smartplan-year-evidence-v2');
      final file = yearEvidenceAttachment(
        base64Decode(value['archive_base64']),
        metadata,
        entry,
      );
      expect(file.sha256, metadata['sha256']);
      expect(
        metadata['original_year_complete'],
        value['export']['report']['complete_for_recorded_sources'],
      );
    });
  }
  test('old v1 remains accepted; unknown formats are not guessed', () {
    final value = yearEvidenceCopy(legacy['scenarios']['ordinary_correction']),
        entry = fixtureYearEntry(value);
    expect(
      yearEvidenceMetadata(value['metadata'], entry)['format'],
      yearEvidenceFormat,
    );
    for (final format in [
      'smartplan-year-evidence-v3',
      'smartplan-year-evidence-v20',
      null,
      1,
      {},
      'smartplan-year-evidence-v2 ',
    ]) {
      expect(
        () => yearEvidenceMetadata({
          ...value['metadata'],
          'format': format,
        }, entry),
        throwsException,
      );
    }
  });
  test('version change after first read and crossed actual originals fail', () {
    final value = yearEvidenceCopy(fixture['scenarios']['complete_history']),
        entry = fixtureYearEntry(value);
    expect(
      () => yearEvidenceMetadata(
        {...value['metadata'], 'format': yearEvidenceFormat},
        entry,
        previous: value['metadata'],
      ),
      throwsException,
    );
    final old = yearEvidenceCopy(legacy['scenarios']['ordinary_correction']);
    expect(() => yearEvidenceMetadata(old['metadata'], entry), throwsException);
    expect(
      () => yearEvidenceAttachment(
        base64Decode(old['archive_base64']),
        value['metadata'],
        entry,
      ),
      throwsException,
    );
  });
}

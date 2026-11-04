import 'dart:convert';
import 'dart:typed_data';

import 'api.dart';
import 'business_accounting_openings_contract.dart'
    show openingDigest, openingSame;
import 'business_session.dart';
import 'mail_attachment_widgets.dart' show VerifiedMailAttachment;

const yearEvidenceFormat = 'smartplan-year-evidence-v1';
const _yearEvidenceFormats = {
  yearEvidenceFormat,
  'smartplan-year-evidence-v2',
};
const yearEvidenceMaxBytes = 128 * 1024 * 1024;
const _metadataFields = [
  'format',
  'schema_version',
  'instance_id',
  'year',
  'export_id',
  'export_hash',
  'sha256',
  'size',
  'filename',
  'archive_path',
  'original_count',
  'original_year_complete',
  'private_source_boundaries',
  'official_tax_return',
  'datev_certified',
  'private_personnel_originals_included',
];
Never _bad(String message) => throw ApiException(0, message);
Map<String, dynamic> yearEvidenceCopy(dynamic value) =>
    businessMap(jsonDecode(jsonEncode(value)));
dynamic _ordered(dynamic value) => value is Map
    ? {
        for (final k in value.keys.map((v) => '$v').toList()..sort())
          k: _ordered(value[k]),
      }
    : value is List
    ? value.map(_ordered).toList()
    : value;
String yearEvidenceHash(dynamic value) =>
    openingDigest(utf8.encode(jsonEncode(_ordered(value))));
void _shape(dynamic value, Iterable<String> keys) {
  if (value is! Map ||
      !openingSame(value.keys.toList()..sort(), keys.toList()..sort()))
    _bad('Unbekannte oder fehlende Felder im ursprünglichen Jahresnachweis.');
}

void _id(dynamic value) {
  if (value is! String || !RegExp(r'^[a-f0-9]{32}$').hasMatch(value))
    _bad('Ungültige ursprüngliche Export- oder Instanzkennung.');
}

void _hash(dynamic value) {
  if (value is! String || !RegExp(r'^[a-f0-9]{64}$').hasMatch(value))
    _bad('Ungültige Originalprüfsumme.');
}

bool yearEvidenceReadable(BusinessSession s) =>
    s.projectId == null &&
    s.hasFeature('accounting_year_evidence_v1') &&
    s.hasModule('accounting_euer') &&
    ['accounting.read', 'finance.read'].every(s.can);
String yearEvidencePath(String id) {
  _id(id);
  return '/accounting/euer/exports/$id/evidence';
}

Map<String, dynamic> yearEvidenceEntry(dynamic raw) {
  final e = businessMap(raw);
  _shape(e, [
    'artifact',
    'control',
    'created_at',
    'created_by',
    'effect',
    'entry_hash',
    'evidence_reference',
    'id',
    'operation',
    'payload',
    'postings',
    'preview_hash',
    'previous_hash',
    'profile',
    'reason',
    'reverses',
    'rule_version',
    'sequence',
    'target',
  ]);
  _id(e['id']);
  _id(e['created_by']);
  _hash(e['entry_hash']);
  _hash(e['preview_hash']);
  _hash(e['previous_hash']);
  _shape(e['payload'], ['year']);
  final year = e['payload']['year'];
  if (year is! int ||
      year < 1900 ||
      year > 2200 ||
      e['operation'] != 'export' ||
      e['target'] != 'export:$year' ||
      e['control'] != null ||
      e['effect'] != null ||
      e['reverses'] != null ||
      !openingSame(e['postings'], []) ||
      e['sequence'] is! int ||
      e['sequence'] < 1 ||
      yearEvidenceHash({...e}..remove('entry_hash')) != e['entry_hash'])
    _bad(
      'Nur die unveränderte bestätigte EÜR-Exportfassung kann ein Jahrespaket begründen.',
    );
  final artifact = businessMap(e['artifact']);
  _shape(artifact, [
    'csv',
    'csv_sha256',
    'datev_certified',
    'format',
    'generated_at',
    'official_tax_return',
    'report',
    'report_sha256',
  ]);
  final report = businessMap(artifact['report']);
  if (artifact['format'] != 'smartplan_euer_review_v1' ||
      artifact['official_tax_return'] != false ||
      artifact['datev_certified'] != false ||
      report['year'] != year ||
      report['complete_for_recorded_sources'] is! bool ||
      report['sources'] is! List ||
      artifact['csv'] is! String ||
      yearEvidenceHash(report) != artifact['report_sha256'] ||
      openingDigest(utf8.encode(artifact['csv'])) != artifact['csv_sha256'])
    _bad(
      'Die ursprünglichen Jahresdaten oder CSVbytes stimmen nicht mit dem Exporteintrag überein.',
    );
  return e;
}

Map<String, dynamic> yearEvidenceOriginalExport(
  dynamic raw,
  Map<String, dynamic> entry,
) {
  final e = yearEvidenceEntry(entry), v = businessMap(raw);
  _shape(v, [
    'entry_id',
    'entry_hash',
    'created_at',
    ...businessMap(e['artifact']).keys,
  ]);
  if (v['entry_id'] != e['id'] ||
      v['entry_hash'] != e['entry_hash'] ||
      v['created_at'] != e['created_at'] ||
      !openingSame({
        for (final k in businessMap(e['artifact']).keys) k: v[k],
      }, e['artifact']))
    _bad(
      'Der gelesene EÜR-Export gehört zu einer anderen ursprünglichen Fassung.',
    );
  return v;
}

Map<String, dynamic> yearEvidenceMetadata(
  dynamic raw,
  Map<String, dynamic> entry, {
  Map<String, dynamic>? previous,
}) {
  final e = yearEvidenceEntry(entry),
      v = businessMap(raw),
      report = businessMap(e['artifact']['report']);
  _shape(v, _metadataFields);
  _id(v['instance_id']);
  _id(v['export_id']);
  _hash(v['export_hash']);
  _hash(v['sha256']);
  final boundaries = v['private_source_boundaries'];
  if (!_yearEvidenceFormats.contains(v['format']) ||
      v['schema_version'] != 1 ||
      v['export_id'] != e['id'] ||
      v['export_hash'] != e['entry_hash'] ||
      v['year'] != e['payload']['year'] ||
      v['original_year_complete'] != report['complete_for_recorded_sources'] ||
      v['filename'] !=
          'smartplan-jahresnachweis-${v['year']}-${v['export_id']}.zip' ||
      v['archive_path'] != '${yearEvidencePath(e['id'])}/archive' ||
      v['size'] is! int ||
      v['size'] < 4 ||
      v['size'] > yearEvidenceMaxBytes ||
      v['original_count'] is! int ||
      v['original_count'] < 0 ||
      v['original_count'] > 9993 ||
      v['official_tax_return'] != false ||
      v['datev_certified'] != false ||
      v['private_personnel_originals_included'] != false ||
      boundaries is! List ||
      boundaries.any((b) => !['payroll_cash', 'travel_cash'].contains(b)) ||
      boundaries.toSet().length != boundaries.length ||
      !openingSame(boundaries, [...boundaries]..sort()))
    _bad(
      'Die Jahrespaket-Metadaten passen nicht zu dieser ursprünglichen Exportfassung oder ihrem begrenzten Umfang.',
    );
  for (final source in businessItems(report['sources'])) {
    if (['payroll_cash', 'travel_cash'].contains(source['kind']) &&
        !boundaries.contains(source['kind']))
      _bad(
        'Die belegte Grenze privater Personaloriginale fehlt im Jahresnachweis.',
      );
  }
  if (previous != null && !openingSame(v, previous))
    _bad(
      'Der Originalnachweis wurde während des Downloads verändert oder gehört zu einer anderen Instanz.',
    );
  return v;
}

VerifiedMailAttachment yearEvidenceAttachment(
  Uint8List bytes,
  Map<String, dynamic> metadata,
  Map<String, dynamic> entry,
) {
  final m = yearEvidenceMetadata(metadata, entry);
  if (bytes.length != m['size'] ||
      bytes.length > yearEvidenceMaxBytes ||
      bytes.length < 4 ||
      bytes[0] != 80 ||
      bytes[1] != 75 ||
      bytes[2] != 3 ||
      bytes[3] != 4 ||
      openingDigest(bytes) != m['sha256'])
    _bad(
      'Die heruntergeladenen ZIPbytes stimmen nicht mit Größe und SHA-256 dieses Originalpakets überein.',
    );
  return VerifiedMailAttachment(
    bytes: bytes,
    filename: m['filename'],
    mediaType: 'application/zip',
    sha256: m['sha256'],
  );
}

import 'dart:convert';
import 'dart:typed_data';

import 'package:cryptography/cryptography.dart';
import 'package:flutter/material.dart';

import 'api.dart';
import 'business_session.dart';
import 'business_widgets.dart';
import 'design.dart';
import 'mail_attachment_widgets.dart';
import 'offline_vault.dart' show offlineId;

const _privacyLabels = {
  'open': 'Aufgenommen',
  'verified': 'Identität geprüft',
  'reviewing': 'In Bearbeitung',
  'closed': 'Abgeschlossen',
  'purged': 'Private Inhalte gelöscht',
  'checked': 'Geprüft',
  'not_applicable': 'Nicht einschlägig',
  'pending': 'Noch offen',
  'include': 'Zur Auskunft freigegeben',
  'redact': 'Redigierte Auskunft',
  'retain': 'Begründet aufbewahren',
  'not_subject': 'Nicht zugeordnet',
  'erase_master': 'Stammanonymisierung geprüft',
  'contact_rectified': 'Kontakt berichtigt',
  'contact_erased': 'Kontaktanonymisierung geprüft',
  'export_created': 'Personenexport erstellt',
};
String _privacyLabel(dynamic value) =>
    _privacyLabels[value] ?? (value == null ? 'Offen' : '$value');

const privacyKinds = {
  'access': 'Auskunft',
  'export': 'Datenexport',
  'rectification': 'Berichtigung',
  'erasure': 'Löschprüfung',
};
const privacyManual = {
  'free_text': 'Freitext und weitere Namensnennungen',
  'originals_and_third_parties': 'Originale und Daten anderer Personen',
  'historical_receipts': 'Historische Nachweise und Quittungen',
  'external_systems': 'Externe Systeme und lokale Dateien',
  'recipients_and_copies': 'Empfänger und weitergegebene Kopien',
  'backups': 'Sicherungen und Wiederherstellung',
  'retention_and_legal_holds': 'Aufbewahrungspflichten und Sperren',
};
final _id = RegExp(r'^[a-f0-9]{32}$'), _hash = RegExp(r'^[a-f0-9]{64}$');
Never _fail(String message, [int status = 0]) =>
    throw ApiException(status, message);
Map<String, dynamic> _copy(Map<String, dynamic> value) =>
    businessMap(jsonDecode(jsonEncode(value)));
Map<String, dynamic> privacyCase(dynamic raw, String id) {
  final v = businessMap(raw);
  if (v['id'] != id ||
      !_id.hasMatch(id) ||
      v['revision'] is! int ||
      v['revision'] < 1 ||
      !const [
        'open',
        'verified',
        'reviewing',
        'closed',
        'purged',
      ].contains(v['status']) ||
      v['purged'] is! bool ||
      v['purged'] == false &&
          (v['automatic_completeness'] != false ||
              v['external_messages_sent'] != false))
    _fail('Die Antwort bestätigt den geöffneten Datenschutzfall nicht.');
  return v;
}

Map<String, dynamic> privacyReceipt(
  dynamic raw,
  String caseId,
  String requestId,
) {
  final v = businessMap(raw);
  if (v['case_id'] != caseId ||
      v['request_id'] != requestId ||
      v['confirmed'] != true ||
      businessMap(v['reference'])['case_id'] != caseId ||
      v['operation'] is! String)
    _fail('Quittung gehört nicht zum ursprünglichen Datenschutzauftrag.');
  return v;
}

Future<VerifiedMailAttachment> privacyArchiveAttachment(
  Uint8List bytes,
  Map<String, dynamic> expected,
  String caseId,
) async {
  if (!_hash.hasMatch('${expected['sha256']}') ||
      bytes.length != expected['size'] ||
      bytes.length > 8000000 ||
      bytes.length < 4 ||
      bytes[0] != 80 ||
      bytes[1] != 75)
    _fail('Exportformat oder Größe stimmt nicht.');
  final hash = (await Sha256().hash(bytes)).bytes
      .map((v) => v.toRadixString(16).padLeft(2, '0'))
      .join();
  if (hash != expected['sha256']) _fail('Exportprüfsumme stimmt nicht.');
  return VerifiedMailAttachment(
    bytes: bytes,
    filename: 'Datenauskunft-$caseId.zip',
    mediaType: 'application/zip',
    sha256: hash,
  );
}

/// Private drafts are never added to BusinessSession's general pending map.
class PrivacyCommand extends ChangeNotifier {
  PrivacyCommand(this.session, {bool Function()? allowed})
    : allowed = allowed ?? (() => true);
  final BusinessSession session;
  final bool Function() allowed;
  Map<String, dynamic>? pending;
  int epoch = 0;
  String get stamp => jsonEncode([
    session.api.token,
    session.generation,
    session.projectId,
    session.permissions.toList()..sort(),
    session.capabilities.toList()..sort(),
    session.features.toList()..sort(),
  ]);
  bool get available =>
      allowed() &&
      session.allowed &&
      session.can('privacy.manage') &&
      session.hasFeature('privacy_cases') &&
      session.hasModule('privacy_cases');
  void clear() {
    final body = pending?['body'];
    if (body is Map) body.clear();
    pending = null;
    epoch++;
    notifyListeners();
  }

  void check(String original, int captured) {
    if (!available || stamp != original || epoch != captured) {
      clear();
      _fail(
        'Sitzung oder Ansicht geändert; private Eingaben wurden verworfen.',
        403,
      );
    }
  }

  Future<Map<String, dynamic>> fresh({bool write = false}) async {
    final original = stamp, captured = epoch;
    if (!available) _fail('Aktuelle Datenschutzfreigabe fehlt.', 403);
    final me = businessMap(await session.api.call('/api/me'));
    await session.load();
    check(original, captured);
    if (!_id.hasMatch('${me['id']}') || write && session.readonly) {
      clear();
      _fail('Datenschutzauftrag ist aktuell nicht freigegeben.', 403);
    }
    return me;
  }

  Future<Map<String, dynamic>> submit(
    String path,
    Map<String, dynamic> body,
    String caseId,
  ) async {
    if (pending != null)
      _fail(
        'Zuerst den offenen Auftrag prüfen oder unverändert wiederholen.',
        409,
      );
    if (!_id.hasMatch(caseId) || !path.startsWith('/privacy/cases'))
      _fail('Ungültiger Fallauftrag.');
    final me = await fresh(write: true);
    pending = {
      'path': path,
      'case_id': caseId,
      'body': {..._copy(body), 'request_id': offlineId()},
      'actor': me['id'],
      'stamp': stamp,
      'epoch': epoch,
    };
    return retry();
  }

  Future<Map<String, dynamic>> retry() async {
    final operation = pending;
    if (operation == null) _fail('Kein privater Auftrag im Arbeitsspeicher.');
    check(operation['stamp'], operation['epoch']);
    final me = await fresh(write: true);
    if (me['id'] != operation['actor']) {
      clear();
      _fail('Auftraggeber geändert.', 403);
    }
    final caseId = '${operation['case_id']}';
    if (operation['path'] != '/privacy/cases')
      privacyCase(
        await privateRead('/privacy/cases/$caseId', missing: true),
        caseId,
      );
    check(operation['stamp'], operation['epoch']);
    await session.api.call(
      session.path(operation['path']),
      _copy(businessMap(operation['body'])),
    );
    check(operation['stamp'], operation['epoch']);
    final proof = await status();
    final value = privacyCase(
      await privateRead('/privacy/cases/$caseId', missing: true),
      caseId,
    );
    check(operation['stamp'], operation['epoch']);
    // Completion discards the private payload without revoking the editor
    // that is about to close successfully. Scope invalidation uses clear().
    (operation['body'] as Map).clear();
    pending = null;
    return {'case': value, 'receipt': proof['reference']};
  }

  Future<Map<String, dynamic>> status() async {
    final operation = pending;
    if (operation == null) _fail('Kein unbestätigter Auftrag vorhanden.');
    check(operation['stamp'], operation['epoch']);
    final me = await fresh();
    if (me['id'] != operation['actor']) {
      clear();
      _fail('Auftraggeber geändert.', 403);
    }
    final requestId = '${operation['body']['request_id']}',
        caseId = '${operation['case_id']}';
    final value = await privateRead(
      '/privacy/cases/$caseId/commands/$requestId',
    );
    check(operation['stamp'], operation['epoch']);
    return privacyReceipt(value, caseId, requestId);
  }

  Future<dynamic> privateRead(String path, {bool missing = false}) async {
    try {
      return await session.read(path);
    } on ApiException catch (error) {
      if ({
        401,
        403,
        if (missing) 404,
        if (missing) 410,
      }.contains(error.status)) {
        clear();
      }
      rethrow;
    }
  }
}

class BusinessPrivacyCasesPage extends StatefulWidget {
  const BusinessPrivacyCasesPage({
    super.key,
    required this.session,
    this.exporter,
  });
  final BusinessSession session;
  final MailAttachmentExporter? exporter;
  @override
  State<BusinessPrivacyCasesPage> createState() =>
      _BusinessPrivacyCasesPageState();
}

class _BusinessPrivacyCasesPageState extends State<BusinessPrivacyCasesPage>
    with WidgetsBindingObserver {
  BusinessSession get session => widget.session;
  late final PrivacyCommand command;
  List<Map<String, dynamic>> cases = [];
  Map<String, dynamic>? current;
  String? error;
  bool busy = false, suspended = false;
  String? openedStamp;
  bool get available =>
      mounted &&
      !suspended &&
      session.allowed &&
      session.can('privacy.manage') &&
      session.hasFeature('privacy_cases') &&
      session.hasModule('privacy_cases');
  @override
  void initState() {
    super.initState();
    command = PrivacyCommand(session, allowed: () => mounted && !suspended);
    command.addListener(privateRevoked);
    session.addListener(changed);
    WidgetsBinding.instance.addObserver(this);
    load();
  }

  @override
  void dispose() {
    command.removeListener(privateRevoked);
    command.clear();
    command.dispose();
    session.removeListener(changed);
    WidgetsBinding.instance.removeObserver(this);
    super.dispose();
  }

  void privateRevoked() {
    if (mounted)
      setState(() {
        current = null;
        cases = [];
      });
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state != AppLifecycleState.resumed) {
      suspended = true;
      command.clear();
      if (mounted)
        setState(() {
          current = null;
          cases = [];
        });
    } else {
      suspended = false;
      load();
    }
  }

  void changed() {
    if (!mounted) return;
    if (!available || openedStamp != null && openedStamp != command.stamp) {
      command.clear();
      current = null;
      cases = [];
    }
    setState(() {});
  }

  Future<void> run(Future<void> Function() task) async {
    if (busy) return;
    setState(() => busy = true);
    try {
      await task();
      if (mounted) setState(() => error = null);
    } catch (e) {
      if (mounted) setState(() => error = e is ApiException ? e.message : '$e');
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  Future<dynamic> readPrivate(String path) async {
    final original = command.stamp, captured = command.epoch;
    final value = await command.privateRead(path);
    command.check(original, captured);
    return value;
  }

  Future<void> load([String? id]) async {
    try {
      await command.fresh();
      final original = command.stamp, captured = command.epoch;
      final value = await readPrivate(
        '/privacy/cases${id == null ? '' : '/$id'}',
      );
      command.check(original, captured);
      if (mounted)
        setState(() {
          openedStamp = original;
          error = null;
          if (id == null) {
            cases = businessItems(value);
            current = null;
          } else {
            current = privacyCase(value, id);
          }
        });
    } catch (e) {
      if (mounted)
        setState(() {
          error = '$e';
          current = null;
          cases = [];
        });
    }
  }

  BusinessField field(
    String name,
    String label, {
    BusinessInput type = BusinessInput.text,
    Object? value,
    bool required = false,
    Map<String, String> choices = const {},
  }) => BusinessField(
    name,
    label,
    type: type,
    initial: value,
    required: required,
    choices: choices,
  );
  BusinessField note(String name, String label, {String value = ''}) => field(
    name,
    label,
    type: BusinessInput.multiline,
    value: value,
    required: true,
  );
  BusinessField confirm(String label) => field(
    'confirmed',
    label,
    type: BusinessInput.toggle,
    value: false,
    required: true,
  );
  Widget privateDialog(Widget child, String original, int captured) =>
      ListenableBuilder(
        listenable: Listenable.merge([session, command]),
        builder: (_, __) =>
            available && command.stamp == original && command.epoch == captured
            ? child
            : const AlertDialog(
                title: Text('Private Ansicht geschlossen'),
                content: Text(
                  'Sitzung, Quellenrechte oder Ansicht wurden geändert. Private Inhalte wurden verworfen.',
                ),
              ),
      );
  Future<void> edit(
    String title,
    String operation,
    List<BusinessField> fields, {
    Map<String, dynamic> Function(Map<String, dynamic>)? transform,
    Map<String, dynamic>? record,
  }) async {
    final caseValue = record ?? current!;
    await command.fresh(write: true);
    privacyCase(
      await readPrivate('/privacy/cases/${caseValue['id']}'),
      '${caseValue['id']}',
    );
    if (!mounted) return;
    final original = command.stamp, captured = command.epoch;
    await showDialog<bool>(
      context: context,
      builder: (_) => privateDialog(
        BusinessEditor(
          session: session,
          title: title,
          fields: fields,
          readPermission: 'privacy.manage',
          writePermission: 'privacy.manage',
          readAllowed: () => available,
          onSave: (values) async {
            final result = await command.submit(
              '/privacy/cases/${caseValue['id']}/$operation',
              {
                'revision': caseValue['revision'],
                ...(transform?.call(values) ?? values),
              },
              caseValue['id'],
            );
            if (mounted) setState(() => current = businessMap(result['case']));
          },
        ),
        original,
        captured,
      ),
    );
    if (mounted && available) setState(() {});
  }

  Future<void> create() async {
    final me = await command.fresh(write: true),
        options = businessMap(await readPrivate('/privacy/cases/options'));
    final people = {
      for (final item in businessItems(options['subjects']))
        '${item['kind']}:${item['id']}':
            '${{'customer': 'Kontakt', 'employee': 'Mitarbeiter', 'user': 'Benutzer'}[item['kind']]} · ${item['label']}',
    };
    final handlers = {
      for (final item in businessItems(options['handlers']))
        '${item['id']}': '${item['email']}',
    };
    final id = offlineId();
    if (!mounted) return;
    final original = command.stamp, captured = command.epoch;
    await showDialog<bool>(
      context: context,
      builder: (_) => privateDialog(
        BusinessEditor(
          session: session,
          title: 'Datenschutzfall aufnehmen',
          readPermission: 'privacy.manage',
          writePermission: 'privacy.manage',
          readAllowed: () => available,
          fields: [
            field(
              'subject',
              'Betroffene Person',
              type: BusinessInput.choice,
              choices: people,
              value: people.keys.firstOrNull,
              required: true,
            ),
            field(
              'request_kind',
              'Anfragetyp',
              type: BusinessInput.choice,
              choices: privacyKinds,
              value: 'access',
            ),
            field(
              'received_date',
              'Eingang am',
              type: BusinessInput.date,
              value: DateTime.now().toIso8601String().substring(0, 10),
              required: true,
            ),
            field(
              'due_date',
              'Geprüfte Antwortfrist',
              type: BusinessInput.date,
              required: true,
            ),
            field(
              'assigned_to',
              'Verantwortliche Person',
              type: BusinessInput.choice,
              choices: handlers,
              value: me['id'],
              required: true,
            ),
            note('scope', 'Erbetener Umfang'),
            field(
              'retain_until',
              'Private Inhalte aufbewahren bis',
              type: BusinessInput.date,
              required: true,
            ),
            note('retention_reason', 'Zweck und Begründung der Aufbewahrung'),
          ],
          onSave: (values) async {
            final v = Map<String, dynamic>.from(values),
                subject = '${v.remove('subject')}'.split(':');
            final result = await command.submit('/privacy/cases', {
              'id': id,
              'subject_kind': subject[0],
              'subject_id': subject[1],
              ...v,
            }, id);
            if (mounted) setState(() => current = businessMap(result['case']));
          },
        ),
        original,
        captured,
      ),
    );
    if (mounted && available) setState(() {});
  }

  Future<void> scan() async {
    final c = current!;
    final result = await command.submit('/privacy/cases/${c['id']}/scan', {
      'revision': c['revision'],
    }, c['id']);
    if (mounted) setState(() => current = businessMap(result['case']));
  }

  Future<void> sourceReview(Map<String, dynamic> source) async {
    final c = current!,
        value = businessMap(
          await readPrivate(
            '/privacy/cases/${current!['id']}/sources/${source['key']}',
          ),
        );
    await command.fresh();
    if (!mounted) return;
    final original = command.stamp, captured = command.epoch;
    await showDialog<void>(
      context: context,
      builder: (context) => privateDialog(
        AlertDialog(
          title: const Text('Aktueller Quellenstand'),
          content: SizedBox(
            width: 620,
            child: SingleChildScrollView(
              child: SelectableText(
                const JsonEncoder.withIndent('  ').convert(value['value']),
              ),
            ),
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(context),
              child: const Text('Zur Entscheidung'),
            ),
          ],
        ),
        original,
        captured,
      ),
    );
    if (!mounted || !available) return;
    await edit(
      'Quelle prüfen',
      'review',
      [
        field(
          'decision',
          'Entscheidung',
          type: BusinessInput.choice,
          value: 'retain',
          choices: const {
            'retain': 'Begründet aufbewahren / nicht ausgeben',
            'include': 'Geprüft in Auskunft aufnehmen',
            'redact': 'Nur redigierte Auskunft aufnehmen',
            'not_subject': 'Begründet nicht dieser Person zugeordnet',
            'erase_master': 'Nur Kontaktstamm zur Anonymisierung prüfen',
          },
        ),
        note('reason', 'Begründung und Daten anderer Personen'),
        field(
          'statement',
          'Bei Redaktion: geprüfter Auskunftstext',
          type: BusinessInput.multiline,
        ),
        field(
          'include_originals',
          'Originaldateien sind auf Fremdpersonen geprüft und werden unverändert beigefügt.',
          type: BusinessInput.toggle,
          value: false,
        ),
      ],
      record: c,
      transform: (v) => {
        'source_key': source['key'],
        'source_sha256': source['sha256'],
        'decision': v['decision'],
        'reason': v['reason'],
        'redacted_value': v['decision'] == 'redact'
            ? {'reviewed_statement': v['statement']}
            : null,
        'include_originals': v['include_originals'],
      },
    );
  }

  Future<void> management() async {
    final c = current!,
        options = businessMap(await readPrivate('/privacy/cases/options'));
    await edit('Fallverwaltung', 'manage', [
      field(
        'due_date',
        'Antwortfrist',
        type: BusinessInput.date,
        value: c['due_date'],
        required: true,
      ),
      field(
        'assigned_to',
        'Verantwortliche Person',
        type: BusinessInput.choice,
        value: c['assigned_to'],
        required: true,
        choices: {
          for (final item in businessItems(options['handlers']))
            '${item['id']}': '${item['email']}',
        },
      ),
      field(
        'retain_until',
        'Private Inhalte aufbewahren bis',
        type: BusinessInput.date,
        value: c['retain_until'],
        required: true,
      ),
      note(
        'retention_reason',
        'Aufbewahrungsgrund',
        value: c['retention_reason'],
      ),
      field(
        'legal_hold',
        'Aufbewahrungssperre aktiv',
        type: BusinessInput.toggle,
        value: c['legal_hold'],
      ),
      note('reason', 'Begründung der Änderung'),
      field(
        'notification_evidence',
        'Bei Fristverlängerung: Nachweis der erfolgten Information',
        type: BusinessInput.multiline,
      ),
    ], record: c);
  }

  Future<void> correction() async {
    final c = current!,
        contact = businessMap(
          await readPrivate('/contacts/${current!['subject_id']}'),
        );
    await edit(
      'Kontakt berichtigen',
      'correct',
      [
        field(
          'target',
          'Zu berichtigendes Feld',
          type: BusinessInput.choice,
          value: 'email',
          choices: const {
            'name': 'Name',
            'contact': 'Ansprechpartner',
            'email': 'E-Mail',
            'phone': 'Telefon',
            'address': 'Adresse',
            'notes': 'Interne Notiz',
          },
        ),
        field(
          'replacement',
          'Geprüfter neuer Inhalt',
          type: BusinessInput.multiline,
        ),
        note('reason', 'Berichtigungsnachweis'),
        confirm('Nur das gewählte Stammdatenfeld ändern.'),
      ],
      record: c,
      transform: (v) => {
        'source_revision': contact['revision'],
        'changes': {v['target']: v['replacement']},
        'reason': v['reason'],
        'confirmed': v['confirmed'],
      },
    );
  }

  Future<void> erase() async {
    final c = current!,
        contact = businessMap(
          await readPrivate('/contacts/${current!['subject_id']}'),
        );
    await edit(
      'Kontaktstamm anonymisieren',
      'erase',
      [
        note('reason', 'Begründung der geprüften Anonymisierung'),
        confirm(
          'Nur Kontaktstamm anonymisieren; Pflichtnachweise und Fallaufbewahrung bleiben gesondert geprüft.',
        ),
      ],
      record: c,
      transform: (v) => {'contact_revision': contact['revision'], ...v},
    );
  }

  Future<void> inventoryView() async {
    final id = '${current!['id']}',
        result = businessMap(await readPrivate('/privacy/cases/$id/sources'));
    await command.fresh();
    if (!mounted) return;
    final original = command.stamp, captured = command.epoch;
    await showDialog<void>(
      context: context,
      builder: (context) => privateDialog(
        AlertDialog(
          title: const Text('Dateninventar und Aufbewahrung'),
          content: SizedBox(
            width: 680,
            child: ListView(
              shrinkWrap: true,
              children: businessItems(result['inventory'])
                  .map(
                    (v) => ExpansionTile(
                      title: Text('${v['table']}'),
                      children: [
                        ListTile(
                          title: Text('${v['purpose']}'),
                          subtitle: Text('${v['retention_basis']}'),
                        ),
                      ],
                    ),
                  )
                  .toList(),
            ),
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(context),
              child: const Text('Schließen'),
            ),
          ],
        ),
        original,
        captured,
      ),
    );
  }

  Future<void> download(Map<String, dynamic> metadata) async {
    await command.fresh();
    final id = '${current!['id']}',
        original = command.stamp,
        captured = command.epoch;
    privacyCase(await readPrivate('/privacy/cases/$id'), id);
    final bytes = await session.api.bytes(
      session.path('/privacy/cases/$id/exports/${metadata['id']}'),
      mediaType: 'application/zip',
      maxBytes: 8000000,
    );
    final file = await privacyArchiveAttachment(bytes, metadata, id);
    await command.fresh();
    final fresh = privacyCase(await readPrivate('/privacy/cases/$id'), id);
    command.check(original, captured);
    if (!businessItems(fresh['exports']).any(
      (v) =>
          v['id'] == metadata['id'] &&
          v['available'] == true &&
          v['sha256'] == metadata['sha256'],
    ))
      _fail('Exportfreigabe wurde geändert.', 403);
    if (!mounted) return;
    await (widget.exporter ?? exportMailAttachment)(
      context,
      file,
      () =>
          mounted &&
          available &&
          command.stamp == original &&
          command.epoch == captured,
    );
  }

  Widget button(String label, Future<void> Function() action) => OutlinedButton(
    onPressed: busy || !available ? null : () => run(action),
    child: Text(label),
  );
  Widget card(String title, List<Widget> children) => Card(
    child: Padding(
      padding: const EdgeInsets.all(20),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(title, style: Theme.of(context).textTheme.titleLarge),
          const SizedBox(height: 12),
          ...children,
        ],
      ),
    ),
  );
  Widget pendingPanel() => card('Antwort unbestätigt', [
    const Text(
      'Private Eingaben bleiben nur im Arbeitsspeicher dieser Ansicht. Status prüfen oder unverändert wiederholen. Beim Verlassen werden sie verworfen.',
    ),
    button('Status des offenen Auftrags prüfen', () async {
      final proof = await command.status();
      command.clear();
      await load(proof['case_id']);
    }),
    button('Offenen Auftrag unverändert wiederholen', () async {
      final result = await command.retry();
      if (mounted) setState(() => current = businessMap(result['case']));
    }),
    button('Private Eingaben verwerfen', () async {
      command.clear();
      await load();
    }),
  ]);
  List<Widget> detail() {
    final c = current!, closed = c['status'] == 'closed';
    if (c['purged'] == true)
      return [
        card('Bereinigter Fallnachweis', [
          Text(
            '${privacyKinds[c['request_kind']]} · ${_privacyLabel(c['status'])}',
          ),
          const Text(
            'Private Inhalte sind gelöscht; minimale Bearbeitungs- und Löschhashnachweise bleiben erhalten.',
          ),
        ]),
      ];
    final inv = businessMap(c['inventory']),
        reviews = businessMap(c['reviews']),
        manual = businessMap(c['manual_reviews']);
    return [
      card('${c['subject_label']}', [
        Text(
          '${privacyKinds[c['request_kind']]} · ${_privacyLabel(c['status'])} · Frist ${businessDate(c['due_date'])}${c['overdue'] == true ? ' · ÜBERFÄLLIG' : ''}',
        ),
        Text('${c['scope']}'),
        Text(
          'Private Aufbewahrung bis ${businessDate(c['retain_until'])} · ${c['legal_hold'] == true ? 'Aufbewahrungssperre aktiv' : 'Keine Aufbewahrungssperre'}',
        ),
        Text('${c['retention_reason']}'),
        if (!closed) ...[
          button(
            'Identität prüfen',
            () => edit('Identität dokumentieren', 'identity', [
              field(
                'method',
                'Prüfweg',
                type: BusinessInput.choice,
                value: 'existing_contact_channel',
                choices: const {
                  'existing_contact_channel':
                      'Unabhängig bestätigter Kontaktweg',
                  'in_person': 'Persönlich geprüft',
                  'authenticated_account': 'Authentifizierter Zugang',
                  'other': 'Anderer begründeter Weg',
                },
              ),
              note('evidence', 'Prüfnachweis ohne Ausweiskopie'),
              confirm('Identität wurde tatsächlich geprüft.'),
            ]),
          ),
          button('Quellen neu erfassen', scan),
        ],
        button('Frist, Verantwortung und Aufbewahrung', management),
      ]),
      if (inv.isNotEmpty) ...[
        card('Strukturierte Quellen', [
          Text(
            '${businessItems(inv['sources']).length} Quellen · ${(inv['blocked_tables'] as List).length} Datenarten benötigen zusätzliche Rechte.',
          ),
          button('Dateninventar anzeigen', inventoryView),
          ...businessItems(inv['sources']).map(
            (source) => ListTile(
              title: Text('${source['table']}'),
              subtitle: Text(
                '${source['category']} · ${_privacyLabel(businessMap(reviews[source['key']])['decision'])}',
              ),
              trailing: TextButton(
                onPressed: busy ? null : () => run(() => sourceReview(source)),
                child: const Text('Prüfen'),
              ),
            ),
          ),
        ]),
        card('Manuelle Quellenprüfung', [
          for (final area in privacyManual.entries)
            ListTile(
              title: Text(area.value),
              subtitle: Text(
                '${_privacyLabel(businessMap(manual[area.key])['decision'])}',
              ),
              trailing: TextButton(
                onPressed: busy || closed
                    ? null
                    : () => run(
                        () => edit(area.value, 'manual', [
                          field(
                            'decision',
                            'Prüfergebnis',
                            type: BusinessInput.choice,
                            value:
                                businessMap(manual[area.key])['decision'] ??
                                'pending',
                            choices: const {
                              'pending': 'Noch offen',
                              'checked': 'Tatsächlich geprüft',
                              'not_applicable': 'Begründet nicht einschlägig',
                            },
                          ),
                          note(
                            'evidence',
                            'Konkreter Prüfnachweis und verbleibende Grenzen',
                            value:
                                businessMap(manual[area.key])['evidence'] ?? '',
                          ),
                        ], transform: (v) => {'area': area.key, ...v}),
                      ),
                child: const Text('Dokumentieren'),
              ),
            ),
        ]),
        if (!closed)
          button(
            'Geprüften Personenexport erstellen',
            () => edit('Personenexport freigeben', 'export', [
              field(
                'expires_on',
                'Download verfügbar bis',
                type: BusinessInput.date,
                value: c['retain_until'],
                required: true,
              ),
              confirm(
                'Auswahl, fremde Personendaten und sichere Übergabe geprüft.',
              ),
            ]),
          ),
      ],
      if (!closed &&
          c['request_kind'] == 'rectification' &&
          c['subject_kind'] == 'customer')
        button('Kontaktstamm berichtigen', correction),
      if (!closed &&
          c['request_kind'] == 'erasure' &&
          c['subject_kind'] == 'customer')
        button('Kontaktanonymisierung prüfen und ausführen', erase),
      if (!closed)
        button(
          'Antwort und Abschluss',
          () => edit('Antwort dokumentieren', 'close', [
            field(
              'outcome',
              'Ergebnis',
              type: BusinessInput.choice,
              value: 'partially_fulfilled',
              choices: const {
                'partially_fulfilled': 'Begründete Teilantwort',
                'fulfilled': 'Umfang nach manueller Prüfung erledigt',
                'refused': 'Begründete Ablehnung',
              },
            ),
            field(
              'response_date',
              'Tatsächliches Antwortdatum',
              type: BusinessInput.date,
              value: DateTime.now().toIso8601String().substring(0, 10),
              required: true,
            ),
            note(
              'response_evidence',
              'Nachweis der tatsächlichen Antwort / Übergabe',
            ),
            note('reason', 'Begründung und verbleibende Grenzen'),
            confirm(
              'Ich bestätige tatsächliche Bearbeitung; es wird keine Nachricht gesendet.',
            ),
          ]),
        ),
      if ((c['actions'] as List).isNotEmpty)
        card('Bearbeitung', [
          ...businessItems(c['actions']).map(
            (v) => ExpansionTile(
              title: Text(_privacyLabel(v['kind'])),
              subtitle: Text(businessDate(v['at'], time: true)),
              children: [
                SelectableText(const JsonEncoder.withIndent('  ').convert(v)),
              ],
            ),
          ),
        ]),
      card('Private Exporte', [
        ...businessItems(c['exports']).map(
          (v) => ListTile(
            title: Text('Export ${'${v['id']}'.substring(0, 8)}'),
            subtitle: Text(
              'Bis ${businessDate(v['expires_on'])} · ${v['available'] == true ? 'verfügbar' : 'abgelaufen / gelöscht'}',
            ),
            trailing: Wrap(
              children: [
                if (v['available'] == true)
                  TextButton(
                    onPressed: busy ? null : () => run(() => download(v)),
                    child: const Text('ZIP laden'),
                  ),
                TextButton(
                  onPressed: busy
                      ? null
                      : () => run(
                          () => edit(
                            'Exportkopie geschützt löschen',
                            'exports/${v['id']}/purge',
                            [
                              note('reason', 'Löschgrund'),
                              confirm(
                                'Temporäre Exportkopie nach unabhängigem Checkpoint löschen.',
                              ),
                            ],
                          ),
                        ),
                  child: const Text('Kopie löschen'),
                ),
              ],
            ),
          ),
        ),
      ]),
      if (closed)
        button(
          'Private Fallinhalte nach Aufbewahrungsende löschen',
          () => edit('Private Fallkopien löschen', 'purge', [
            note('reason', 'Ablauf des Aufbewahrungszwecks'),
            confirm(
              'Nach Frist, ohne Sperre und mit unabhängigem Checkpoint private Fallkopien löschen.',
            ),
          ]),
        ),
    ];
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(title: const Text('Datenschutzfälle')),
    body: !available
        ? const BusinessEmpty(
            'Kein Zugriff',
            'Aktuelle Datenschutz- und Quellenfreigaben werden benötigt.',
          )
        : ListView(
            padding: const EdgeInsets.all(20),
            children: [
              const Notice(
                'Betroffenenanfragen mit Identitätsprüfung und begründeten Quellenentscheidungen. Keine automatische Vollständigkeitsbehauptung.',
              ),
              if (error != null) Notice(error!, error: true),
              if (command.pending != null) pendingPanel(),
              if (current != null) ...[
                button('Zur Fallübersicht', () => load()),
                ...detail(),
              ] else ...[
                button('Datenschutzfall aufnehmen', create),
                ...cases.map(
                  (v) => ListTile(
                    title: Text(
                      '${v['subject_label'] ?? 'Bereinigter Fallnachweis'}',
                    ),
                    subtitle: Text(
                      '${privacyKinds[v['request_kind']]} · ${_privacyLabel(v['status'])} · ${businessDate(v['due_date'])}${v['overdue'] == true ? ' · ÜBERFÄLLIG' : ''}',
                    ),
                    onTap: busy ? null : () => run(() => load(v['id'])),
                  ),
                ),
              ],
            ],
          ),
  );
}

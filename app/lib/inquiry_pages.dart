import 'dart:convert';
import 'dart:typed_data';

import 'package:file_selector/file_selector.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:url_launcher/url_launcher.dart';

import 'api.dart';
import 'offline_vault.dart' show offlineId;
import 'mail_attachment_widgets.dart';

const inquiryStatuses = <String, String>{
  'new': 'Neu',
  'callback': 'Rückruf',
  'review': 'Klärung / Aufmaß',
  'offer': 'Angebot',
  'awaiting_acceptance': 'Wartet auf Rückmeldung',
  'accepted': 'Zusage erfasst',
  'qualified': 'Abgeklärt',
  'declined': 'Abgesagt',
  'converted': 'Mit Projekt verknüpft',
};

const _sources = <String, String>{
  'manual': 'Manuell',
  'gmail': 'Gmail',
  'whatsapp': 'WhatsApp',
  'import': 'E-Mail-Datei',
};
const _reviews = <String, String>{
  '': 'Noch offen',
  'documents': 'Unterlagen prüfen',
  'on_site': 'Aufmaß vor Ort',
  'zoom': 'Zoom / Videotermin',
  'other': 'Anderer Weg',
};
const _channels = <String, String>{
  '': 'Noch keine Zusage erfasst',
  'phone': 'Telefon',
  'email': 'E-Mail',
  'other': 'Anderer Weg',
};
const _gmailGuide =
    'https://github.com/smartplanhofmann-spec/Smarplan-Hofmann-Workspace/blob/codex/testupdate-0.7-20261023/integrations/mail_bot/README.md';

String _label(Map<String, String> labels, dynamic value) =>
    labels[value?.toString()] ?? value?.toString() ?? '';

String _displayDate(dynamic value, {bool time = false}) {
  final date = DateTime.tryParse(value?.toString() ?? '')?.toLocal();
  if (date == null) return value?.toString() ?? '';
  String two(int number) => number.toString().padLeft(2, '0');
  return '${two(date.day)}.${two(date.month)}.${date.year}'
      '${time ? ' · ${two(date.hour)}:${two(date.minute)}' : ''}';
}

String? _dateValue(String value) {
  value = value.trim();
  if (value.isEmpty) return null;
  final german = RegExp(r'^(\d{2})\.(\d{2})\.(\d{4})$').firstMatch(value);
  return german == null ? value : '${german[3]}-${german[2]}-${german[1]}';
}

String _errorMessage(Object error) => error is ApiException
    ? error.message
    : 'Der Vorgang konnte nicht abgeschlossen werden. Bitte Verbindung prüfen und erneut versuchen.';

bool _uncertain(Object error) =>
    error is ApiException && (error.status == 0 || error.status >= 500);

bool _denied(Object error) =>
    error is ApiException && [401, 403].contains(error.status);

bool _overdue(Map<String, dynamic> record) {
  if (['declined', 'converted'].contains(record['status'])) return false;
  final due = DateTime.tryParse(record['due_date']?.toString() ?? '');
  final now = DateTime.now();
  return due != null && due.isBefore(DateTime(now.year, now.month, now.day));
}

Future<void> _openHttps(BuildContext context, String address) async {
  final uri = Uri.tryParse(address);
  try {
    if (uri == null ||
        uri.scheme != 'https' ||
        uri.host.isEmpty ||
        uri.userInfo.isNotEmpty ||
        !await launchUrl(uri, mode: LaunchMode.externalApplication)) {
      throw const ApiException(0, 'Der Link konnte nicht geöffnet werden.');
    }
  } catch (error) {
    if (context.mounted) {
      ScaffoldMessenger.of(context)
          .showSnackBar(SnackBar(content: Text(_errorMessage(error))));
    }
  }
}

Widget _errorBox(BuildContext context, String message) => Padding(
  padding: const EdgeInsets.symmetric(vertical: 12),
  child: Text(
    message,
    style: TextStyle(color: Theme.of(context).colorScheme.error),
  ),
);

class InquiriesPage extends StatefulWidget {
  final OfficeApi api;
  final String role;
  final Future<void> Function(Map<String, dynamic> project)? onProject;
  final Future<XFile?> Function()? pickEmail;
  const InquiriesPage({
    super.key,
    required this.api,
    required this.role,
    this.onProject,
    this.pickEmail,
  });

  @override
  State<InquiriesPage> createState() => _InquiriesPageState();
}

class _InquiriesPageState extends State<InquiriesPage> {
  final search = TextEditingController();
  List<Map<String, dynamic>> records = [];
  bool busy = false;
  String? error;
  String status = 'open', source = 'all';
  bool get allowed => widget.role == 'owner';

  @override
  void initState() {
    super.initState();
    if (allowed) load();
  }

  @override
  void dispose() {
    search.dispose();
    super.dispose();
  }

  Future<void> load() async {
    if (!allowed || busy) return;
    setState(() {
      busy = true;
      error = null;
    });
    try {
      final response = await widget.api.call('/api/inquiries');
      if (response is! List)
        throw const ApiException(0, 'Ungültige Anfragenliste.');
      if (mounted) {
        setState(
          () => records = [
            for (final row in response) Map<String, dynamic>.from(row),
          ],
        );
      }
    } catch (e) {
      if (mounted) {
        setState(() {
          if (_denied(e)) records = [];
          error = e is ApiException && e.status == 404
              ? 'Der Anfrageneingang benötigt das neue Serverupdate. Bereits vorhandene Projekte bleiben nutzbar.'
              : _errorMessage(e);
        });
      }
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  Future<void> open(Map<String, dynamic> item) async {
    final project = await Navigator.push<Map<String, dynamic>>(
      context,
      MaterialPageRoute(
        builder: (_) => InquiryDetailPage(
          api: widget.api,
          role: widget.role,
          inquiryId: item['id'],
        ),
      ),
    );
    if (!mounted) return;
    await load();
    if (project != null && mounted) await widget.onProject?.call(project);
  }

  Future<void> capture() async {
    final created = await showDialog<Map<String, dynamic>>(
      context: context,
      barrierDismissible: false,
      builder: (_) => _CaptureInquiryDialog(api: widget.api),
    );
    if (!mounted) return;
    // A lost HTTP response may still have created the enquiry. Refresh even
    // after a cancelled dialog so the actual server record can be found.
    await load();
    if (created != null && mounted) await open(created);
  }

  Future<void> importEmail() async {
    if (busy || !allowed) return;
    XFile? file;
    try {
      file =
          await (widget.pickEmail?.call() ??
              openFile(
                acceptedTypeGroups: [
                  const XTypeGroup(label: 'E-Mail-Datei', extensions: ['eml']),
                ],
              ));
      if (file == null || !mounted) return;
      final length = await file.length();
      if (length < 1 || length > 512 * 1024) {
        throw const ApiException(
          413,
          'Eine EML-Datei mit höchstens 512 KiB auswählen. Anhänge werden nur vermerkt.',
        );
      }
      final builder = BytesBuilder(copy: false);
      await for (final chunk in file.openRead()) {
        if (builder.length + chunk.length > 512 * 1024) {
          throw const ApiException(
            413,
            'Die E-Mail-Datei ist größer als 512 KiB.',
          );
        }
        builder.add(chunk);
      }
      if (builder.length != length)
        throw const ApiException(
          400,
          'Die E-Mail-Datei wurde während des Lesens verändert.',
        );
      if (!mounted) return;
      final encoded = base64Encode(builder.takeBytes());
      final imported = await showDialog<Map<String, dynamic>>(
        context: context,
        barrierDismissible: false,
        builder: (_) => _EmailImportDialog(
          api: widget.api,
          filename: file!.name,
          content: encoded,
        ),
      );
      if (!mounted) return;
      await load();
      if (imported != null && mounted) await open(imported);
    } catch (e) {
      if (mounted) setState(() => error = _errorMessage(e));
    }
  }

  @override
  Widget build(BuildContext context) {
    final needle = search.text.toLowerCase().trim();
    final visible = records.where((row) {
      final statusMatch =
          status == 'all' ||
          (status == 'open' &&
              !['declined', 'converted'].contains(row['status'])) ||
          row['status'] == status;
      return statusMatch &&
          (source == 'all' || row['source'] == source) &&
          (needle.isEmpty ||
              [
                row['subject'],
                row['sender_name'],
                row['sender_email'],
                row['sender_phone'],
                row['customer']?['name'],
                row['project']?['name'],
              ].any(
                (value) =>
                    value?.toString().toLowerCase().contains(needle) ?? false,
              ));
    }).toList();
    return Scaffold(
      appBar: AppBar(
        title: const Text('Anfragen'),
        actions: [
          IconButton(
            tooltip: 'Anfragen aktualisieren',
            onPressed: busy || !allowed ? null : load,
            icon: const Icon(Icons.refresh),
          ),
        ],
      ),
      body: !allowed
          ? const Center(
              child: Padding(
                padding: EdgeInsets.all(24),
                child: Text(
                  'Anfragen und Kundenzuordnung sind der Geschäftsführung vorbehalten.',
                ),
              ),
            )
          : RefreshIndicator(
              onRefresh: load,
              child: ListView(
                padding: const EdgeInsets.all(24),
                children: [
                  Text(
                    'Vom ersten Kontakt zum Projekt',
                    style: Theme.of(context).textTheme.headlineMedium,
                  ),
                  const SizedBox(height: 8),
                  const Text(
                    'Jeder Auftrag ist anders. Sammle Nachrichten, halte den nächsten Schritt fest und verknüpfe bei Bedarf ein Projekt.',
                  ),
                  const SizedBox(height: 20),
                  Wrap(
                    spacing: 10,
                    runSpacing: 10,
                    children: [
                      FilledButton.icon(
                        onPressed: busy ? null : capture,
                        icon: const Icon(Icons.add),
                        label: const Text('Anfrage erfassen'),
                      ),
                      OutlinedButton.icon(
                        onPressed: busy ? null : importEmail,
                        icon: const Icon(Icons.mail_outline),
                        label: const Text('E-Mail importieren'),
                      ),
                      if (widget.api.version == 'v1')
                        OutlinedButton.icon(
                          onPressed: busy
                              ? null
                              : () => Navigator.push<void>(
                                  context,
                                  MaterialPageRoute(
                                    builder: (_) => GmailInboxPage(
                                      api: widget.api,
                                      role: widget.role,
                                    ),
                                  ),
                                ),
                          icon: const Icon(Icons.settings_outlined),
                          label: const Text('Gmail einrichten'),
                        ),
                    ],
                  ),
                  const SizedBox(height: 20),
                  Wrap(
                    spacing: 12,
                    runSpacing: 8,
                    children: [
                      Chip(
                        label: Text(
                          '${records.where((r) => !['declined', 'converted'].contains(r['status'])).length} offen',
                        ),
                      ),
                      Chip(
                        label: Text(
                          '${records.where(_overdue).length} überfällige Wiedervorlagen',
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 16),
                  TextField(
                    controller: search,
                    onChanged: (_) => setState(() {}),
                    decoration: const InputDecoration(
                      labelText: 'Anfragen durchsuchen',
                      prefixIcon: Icon(Icons.search),
                    ),
                  ),
                  const SizedBox(height: 12),
                  Wrap(
                    spacing: 16,
                    runSpacing: 10,
                    children: [
                      SizedBox(
                        width: 300,
                        child: DropdownButton<String>(
                          isExpanded: true,
                          value: status,
                          items: [
                            const DropdownMenuItem(
                              value: 'open',
                              child: Text('Offene Anfragen'),
                            ),
                            const DropdownMenuItem(
                              value: 'all',
                              child: Text('Alle Anfragen'),
                            ),
                            for (final entry in inquiryStatuses.entries)
                              DropdownMenuItem(
                                value: entry.key,
                                child: Text(entry.value),
                              ),
                          ],
                          onChanged: (value) => setState(() => status = value!),
                        ),
                      ),
                      SizedBox(
                        width: 220,
                        child: DropdownButton<String>(
                          isExpanded: true,
                          value: source,
                          items: [
                            const DropdownMenuItem(
                              value: 'all',
                              child: Text('Alle Eingangskanäle'),
                            ),
                            for (final entry in _sources.entries)
                              DropdownMenuItem(
                                value: entry.key,
                                child: Text(entry.value),
                              ),
                          ],
                          onChanged: (value) => setState(() => source = value!),
                        ),
                      ),
                    ],
                  ),
                  if (error != null) _errorBox(context, error!),
                  if (busy) const LinearProgressIndicator(),
                  if (!busy && visible.isEmpty && error == null)
                    const Padding(
                      padding: EdgeInsets.symmetric(vertical: 28),
                      child: Text(
                        'Hier sind noch keine passenden Anfragen. Erfasse eine Nachricht oder importiere eine E-Mail.',
                      ),
                    ),
                  for (final item in visible)
                    Card(
                      child: ListTile(
                        contentPadding: const EdgeInsets.symmetric(
                          horizontal: 18,
                          vertical: 10,
                        ),
                        title: Text(item['subject'] ?? 'Anfrage'),
                        subtitle: Padding(
                          padding: const EdgeInsets.only(top: 6),
                          child: Text(
                            [
                              '${_label(_sources, item['source'])} · ${_label(inquiryStatuses, item['status'])}',
                              if ((item['sender_name'] ?? '').isNotEmpty)
                                item['sender_name'],
                              if ((item['next_action'] ?? '').isNotEmpty)
                                'Nächster Schritt: ${item['next_action']}',
                              if (item['due_date'] != null)
                                'Wiedervorlage: ${_displayDate(item['due_date'])}${_overdue(item) ? ' · überfällig' : ''}',
                            ].join('\n'),
                          ),
                        ),
                        trailing: const Icon(Icons.chevron_right),
                        onTap: busy ? null : () => open(item),
                      ),
                    ),
                ],
              ),
            ),
    );
  }
}

class _CaptureInquiryDialog extends StatefulWidget {
  final OfficeApi api;
  const _CaptureInquiryDialog({required this.api});
  @override
  State<_CaptureInquiryDialog> createState() => _CaptureInquiryDialogState();
}

class _CaptureInquiryDialogState extends State<_CaptureInquiryDialog> {
  final form = GlobalKey<FormState>();
  final subject = TextEditingController(), message = TextEditingController();
  final name = TextEditingController(),
      email = TextEditingController(),
      phone = TextEditingController();
  String source = 'manual';
  bool busy = false, uncertain = false;
  String? error;
  Map<String, dynamic>? pending;

  @override
  void dispose() {
    for (final c in [subject, message, name, email, phone]) {
      c.dispose();
    }
    super.dispose();
  }

  Future<void> save() async {
    if (busy || !form.currentState!.validate()) return;
    pending ??= {
      'request_id': offlineId(),
      'source': source,
      'source_account': 'manual',
      'subject': subject.text.trim(),
      'message': message.text.trim(),
      'sender_name': name.text.trim(),
      'sender_email': email.text.trim(),
      'sender_phone': phone.text.trim(),
    };
    setState(() {
      busy = true;
      error = null;
    });
    try {
      final result = Map<String, dynamic>.from(
        await widget.api.call('/api/inquiries', pending),
      );
      if (mounted) Navigator.pop(context, result);
    } catch (e) {
      if (mounted)
        setState(() {
          error = _errorMessage(e);
          uncertain = _uncertain(e);
          if (!uncertain) pending = null;
        });
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  @override
  Widget build(BuildContext context) => AlertDialog(
    title: const Text('Anfrage erfassen'),
    content: SizedBox(
      width: 600,
      child: SingleChildScrollView(
        child: Form(
          key: form,
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              DropdownButtonFormField<String>(
                isExpanded: true,
                initialValue: source,
                decoration: const InputDecoration(labelText: 'Eingangskanal'),
                items: const [
                  DropdownMenuItem(
                    value: 'manual',
                    child: Text('Manuell / Telefon'),
                  ),
                  DropdownMenuItem(
                    value: 'whatsapp',
                    child: Text('WhatsApp-Nachricht einfügen'),
                  ),
                  DropdownMenuItem(
                    value: 'gmail',
                    child: Text('E-Mail manuell erfassen'),
                  ),
                ],
                onChanged: busy || uncertain
                    ? null
                    : (v) => setState(() => source = v!),
              ),
              const SizedBox(height: 12),
              TextFormField(
                controller: subject,
                readOnly: busy || uncertain,
                maxLength: 300,
                decoration: const InputDecoration(
                  labelText: 'Betreff / Vorhaben',
                ),
                validator: (v) => v?.trim().isEmpty ?? true
                    ? 'Bitte einen Betreff eingeben.'
                    : null,
              ),
              TextFormField(
                controller: message,
                readOnly: busy || uncertain,
                minLines: 4,
                maxLines: 10,
                maxLength: 40000,
                decoration: const InputDecoration(
                  labelText: 'Nachricht / Gesprächsnotiz',
                ),
                validator: (v) => v?.trim().isEmpty ?? true
                    ? 'Bitte die Nachricht oder Notiz eingeben.'
                    : null,
              ),
              TextFormField(
                controller: name,
                readOnly: busy || uncertain,
                maxLength: 200,
                decoration: const InputDecoration(
                  labelText: 'Absender / Ansprechpartner',
                ),
              ),
              TextFormField(
                controller: email,
                readOnly: busy || uncertain,
                maxLength: 254,
                keyboardType: TextInputType.emailAddress,
                decoration: const InputDecoration(
                  labelText: 'E-Mail des Kunden',
                ),
              ),
              TextFormField(
                controller: phone,
                readOnly: busy || uncertain,
                maxLength: 100,
                keyboardType: TextInputType.phone,
                decoration: const InputDecoration(
                  labelText: 'Telefon des Kunden',
                ),
              ),
              if (uncertain)
                const Text(
                  'Die Antwort ist noch nicht bestätigt. Erneutes Übermitteln wiederholt denselben Vorgang; die Angaben bleiben dafür erhalten.',
                ),
              if (error != null) _errorBox(context, error!),
            ],
          ),
        ),
      ),
    ),
    actions: [
      TextButton(
        onPressed: busy ? null : () => Navigator.pop(context),
        child: const Text('Abbrechen'),
      ),
      FilledButton(
        onPressed: busy ? null : save,
        child: Text(
          busy
              ? 'Wird gespeichert …'
              : uncertain
              ? 'Erneut übermitteln'
              : 'Anfrage speichern',
        ),
      ),
    ],
  );
}

class _EmailImportDialog extends StatefulWidget {
  final OfficeApi api;
  final String filename, content;
  const _EmailImportDialog({
    required this.api,
    required this.filename,
    required this.content,
  });
  @override
  State<_EmailImportDialog> createState() => _EmailImportDialogState();
}

class _EmailImportDialogState extends State<_EmailImportDialog> {
  final requestId = offlineId();
  bool busy = false;
  String? error;
  Future<void> submit() async {
    setState(() {
      busy = true;
      error = null;
    });
    try {
      final result = Map<String, dynamic>.from(
        await widget.api.call('/api/inquiries/import-eml', {
          'request_id': requestId,
          'content_base64': widget.content,
        }),
      );
      if (mounted) Navigator.pop(context, result);
    } catch (e) {
      if (mounted) setState(() => error = _errorMessage(e));
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  @override
  Widget build(BuildContext context) => AlertDialog(
    title: const Text('E-Mail übernehmen'),
    content: SizedBox(
      width: 480,
      child: SingleChildScrollView(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Text(widget.filename),
            const SizedBox(height: 12),
            const Text(
              'Betreff, Absender und Nachricht werden als Anfrage gespeichert. Anhänge werden nur vermerkt. Die Kundenzuordnung bestätigst du anschließend.',
            ),
            if (error != null) _errorBox(context, error!),
          ],
        ),
      ),
    ),
    actions: [
      TextButton(
        onPressed: busy ? null : () => Navigator.pop(context),
        child: const Text('Abbrechen'),
      ),
      FilledButton(
        onPressed: busy ? null : submit,
        child: Text(busy ? 'Wird übernommen …' : 'E-Mail übernehmen'),
      ),
    ],
  );
}

class InquiryDetailPage extends StatefulWidget {
  final OfficeApi api;
  final String role, inquiryId;
  const InquiryDetailPage({
    super.key,
    required this.api,
    required this.role,
    required this.inquiryId,
  });
  @override
  State<InquiryDetailPage> createState() => _InquiryDetailPageState();
}

class _InquiryDetailPageState extends State<InquiryDetailPage> {
  final next = TextEditingController(),
      due = TextEditingController(),
      sevdesk = TextEditingController();
  Map<String, dynamic>? record, pending;
  bool busy = false, uncertain = false;
  bool discardAllowed = false;
  String? error;
  String status = 'new', review = '', channel = '';
  String? customerId;
  bool accessDenied = false;
  String? initialSession;
  final attachmentAccess = ValueNotifier<bool>(true);
  bool get allowed => widget.role == 'owner' && !accessDenied;
  bool get editable =>
      allowed &&
      record != null &&
      record!['status'] != 'converted' &&
      !busy &&
      !uncertain;

  bool get dirty =>
      record != null &&
      record!['status'] != 'converted' &&
      (status != record!['status'] ||
          review != (record!['review_method'] ?? '') ||
          channel != (record!['acceptance_channel'] ?? '') ||
          customerId != record!['customer_id'] ||
          next.text.trim() != (record!['next_action'] ?? '') ||
          _dateValue(due.text) != record!['due_date'] ||
          sevdesk.text.trim() != (record!['sevdesk_url'] ?? ''));

  Future<bool> confirmDiscard() async =>
      await showDialog<bool>(
        context: context,
        builder: (ctx) => AlertDialog(
          title: const Text('Ungespeicherte Angaben verwerfen?'),
          content: const Text(
            'Deine Änderungen an dieser Anfrage sind noch nicht gespeichert.',
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(ctx, false),
              child: const Text('Weiter bearbeiten'),
            ),
            FilledButton(
              onPressed: () => Navigator.pop(ctx, true),
              child: const Text('Angaben verwerfen'),
            ),
          ],
        ),
      ) ??
      false;

  Future<void> reload() async {
    if (dirty && !await confirmDiscard()) return;
    if (mounted) await load();
  }

  @override
  void initState() {
    super.initState();
    initialSession = widget.api.token;
    widget.api.addListener(sessionChanged);
    if (allowed) load();
  }

  void sessionChanged() {
    if (initialSession != null && widget.api.token != initialSession)
      denyAccess();
  }

  void denyAccess() {
    if (!mounted || accessDenied) return;
    attachmentAccess.value = false;
    setState(() {
      accessDenied = true;
      record = null;
      error =
          'Anmeldung oder Zugriff nicht mehr verfügbar. Bitte online anmelden.';
    });
  }

  @override
  void dispose() {
    widget.api.removeListener(sessionChanged);
    attachmentAccess.dispose();
    next.dispose();
    due.dispose();
    sevdesk.dispose();
    super.dispose();
  }

  void accept(Map<String, dynamic> value) {
    final currentAttachments = record?['attachments'];
    final incomingAttachments = value['attachments'];
    if (currentAttachments is Map &&
        incomingAttachments is Map &&
        (currentAttachments['deleted_count'] as int? ?? 0) >
            (incomingAttachments['deleted_count'] as int? ?? 0)) {
      value['attachments'] = currentAttachments;
    }
    record = value;
    status = value['status'];
    review = value['review_method'] ?? '';
    channel = value['acceptance_channel'] ?? '';
    customerId = value['customer_id'];
    next.text = value['next_action'] ?? '';
    due.text = value['due_date'] == null ? '' : _displayDate(value['due_date']);
    sevdesk.text = value['sevdesk_url'] ?? '';
    pending = null;
    uncertain = false;
    discardAllowed = false;
  }

  Future<void> load() async {
    if (!allowed || busy) return;
    setState(() {
      busy = true;
      error = null;
    });
    try {
      final value = Map<String, dynamic>.from(
        await widget.api.call('/api/inquiries/${widget.inquiryId}'),
      );
      if (mounted && allowed) setState(() => accept(value));
    } catch (e) {
      if (mounted)
        setState(() {
          if (_denied(e)) {
            record = null;
            accessDenied = true;
            attachmentAccess.value = false;
          }
          error = _errorMessage(e);
        });
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  Future<void> save() async {
    if ((!editable && !uncertain) || busy) return;
    if (!uncertain && status == 'accepted' && channel.isEmpty) {
      setState(
        () => error = 'Bitte angeben, ob die Zusage per Telefon, E-Mail oder auf anderem Weg eingegangen ist.',
      );
      return;
    }
    pending ??= {
      'request_id': offlineId(),
      'revision': record!['revision'],
      'status': status,
      'review_method': review,
      'acceptance_channel': channel,
      'customer_id': customerId,
      'next_action': next.text.trim(),
      'due_date': _dateValue(due.text),
      'sevdesk_url': sevdesk.text.trim(),
    };
    setState(() {
      busy = true;
      error = null;
    });
    try {
      final value = Map<String, dynamic>.from(
        await widget.api.call('/api/inquiries/${widget.inquiryId}', pending),
      );
      if (mounted && allowed) {
        setState(() => accept(value));
        ScaffoldMessenger.of(
          context,
        ).showSnackBar(const SnackBar(content: Text('Anfrage aktualisiert.')));
      }
    } catch (e) {
      if (_denied(e)) denyAccess();
      if (mounted)
        setState(() {
          error = _errorMessage(e);
          uncertain = _uncertain(e);
          if (!uncertain) pending = null;
        });
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  Future<void> pickDate() async {
    final first = DateTime(2000), last = DateTime(2100);
    final parsed = DateTime.tryParse(_dateValue(due.text) ?? '');
    final chosen = await showDatePicker(
      context: context,
      initialDate:
          parsed != null && !parsed.isBefore(first) && !parsed.isAfter(last)
          ? parsed
          : DateTime.now(),
      firstDate: first,
      lastDate: last,
    );
    if (chosen != null && mounted)
      setState(() => due.text = _displayDate(chosen.toIso8601String()));
  }

  Future<void> convert() async {
    if (!editable) return;
    if (dirty) {
      await save();
      if (!mounted || !editable || error != null) return;
    }
    setState(() {
      busy = true;
      error = null;
    });
    try {
      final customers = List<dynamic>.from(
        await widget.api.call('/api/customers'),
      );
      if (!mounted) return;
      setState(() => busy = false);
      final result = await showDialog<Map<String, dynamic>>(
        context: context,
        barrierDismissible: false,
        builder: (_) => _ConvertInquiryDialog(
          api: widget.api,
          inquiry: record!,
          customers: [
            for (final customer in customers)
              if (customer['active'] == 1 || customer['active'] == true)
                Map<String, dynamic>.from(customer),
          ],
        ),
      );
      if (result != null && mounted && allowed)
        Navigator.pop(context, Map<String, dynamic>.from(result['project']));
    } catch (e) {
      if (mounted) setState(() => error = _errorMessage(e));
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final item = allowed ? record : null;
    final candidates = item?['candidate_customers'] as List? ?? [];
    return PopScope<Object?>(
      canPop: !busy && (!dirty || discardAllowed),
      onPopInvokedWithResult: (didPop, result) async {
        if (didPop || busy || !await confirmDiscard() || !mounted) return;
        setState(() => discardAllowed = true);
        await WidgetsBinding.instance.endOfFrame;
        if (mounted) Navigator.pop(context, result);
      },
      child: Scaffold(
        appBar: AppBar(
          title: Text(item?['subject'] ?? 'Anfrage'),
          actions: [
            IconButton(
              tooltip: 'Anfrage neu laden',
              onPressed: busy || !allowed ? null : reload,
              icon: const Icon(Icons.refresh),
            ),
          ],
        ),
        body: !allowed
            ? Center(
                child: Text(
                  accessDenied
                      ? 'Anmeldung oder Zugriff nicht mehr verfügbar. Bitte online anmelden.'
                      : 'Keine Berechtigung für den Anfrageneingang.',
                ),
              )
            : ListView(
                padding: const EdgeInsets.all(24),
                children: [
                  if (busy) const LinearProgressIndicator(),
                  if (error != null) _errorBox(context, error!),
                  if (item != null) ...[
                    Wrap(
                      spacing: 10,
                      runSpacing: 8,
                      children: [
                        Chip(label: Text(_label(_sources, item['source']))),
                        Chip(
                          label: Text(_label(inquiryStatuses, item['status'])),
                        ),
                        if (item['received_at'] != null)
                          Chip(
                            label: Text(
                              _displayDate(item['received_at'], time: true),
                            ),
                          ),
                      ],
                    ),
                    const SizedBox(height: 12),
                    Text(
                      item['sender_name']?.toString().isNotEmpty == true
                          ? item['sender_name']
                          : 'Absender nicht benannt',
                      style: Theme.of(context).textTheme.titleMedium,
                    ),
                    if (item['sender_email']?.toString().isNotEmpty == true)
                      SelectableText(item['sender_email']),
                    if (item['sender_phone']?.toString().isNotEmpty == true)
                      SelectableText(item['sender_phone']),
                    const SizedBox(height: 18),
                    if (item['source'] == 'gmail' ||
                        item['attachments'] != null)
                      MailAttachmentsCard(
                        key: ValueKey(
                          'inquiry-attachments-${widget.inquiryId}',
                        ),
                        api: widget.api,
                        inquiryId: widget.inquiryId,
                        attachments: item['attachments'] is Map
                            ? item['attachments'] as Map<String, dynamic>
                            : null,
                        canDelete: allowed,
                        accessAllowed: attachmentAccess,
                        onAccessDenied: denyAccess,
                        onManifestChanged: (manifest) {
                          if (mounted && allowed && record != null) {
                            setState(() => record!['attachments'] = manifest);
                          }
                        },
                      ),
                    Card(
                      child: Padding(
                        padding: const EdgeInsets.all(18),
                        child: SelectableText(item['message'] ?? ''),
                      ),
                    ),
                    if (item['provenance']?['warnings'] is List)
                      for (final warning in item['provenance']['warnings'])
                        Padding(
                          padding: const EdgeInsets.symmetric(vertical: 4),
                          child: Text(warning.toString()),
                        ),
                    if (item['status'] == 'converted') ...[
                      const SizedBox(height: 18),
                      Text(
                        'Mit Projekt verknüpft',
                        style: Theme.of(context).textTheme.titleLarge,
                      ),
                      Text(item['project']?['name'] ?? 'Projekt'),
                      const Text(
                        'Die Projektanlage ist keine automatische Beauftragung. Termine und Arbeitsschritte werden in der Projektmappe geführt.',
                      ),
                      const SizedBox(height: 10),
                      FilledButton.icon(
                        onPressed: busy || item['project'] == null
                            ? null
                            : () => Navigator.pop(
                                context,
                                Map<String, dynamic>.from(item['project']),
                              ),
                        icon: const Icon(Icons.folder_open),
                        label: const Text('Projekt öffnen'),
                      ),
                    ] else ...[
                      const SizedBox(height: 22),
                      Text(
                        'Kunde und nächster Schritt',
                        style: Theme.of(context).textTheme.titleLarge,
                      ),
                      const SizedBox(height: 8),
                      if (item['customer'] != null)
                        Text('Zugeordnet: ${item['customer']['name']}'),
                      if (candidates.isNotEmpty)
                        Text(
                          candidates.length == 1
                              ? 'Ein Kunde mit passenden Kontaktdaten wurde gefunden. Bitte die Zuordnung bestätigen.'
                              : 'Mehrere Kunden haben passende Kontaktdaten. Bitte den richtigen Kunden wählen.',
                        ),
                      if (candidates.isNotEmpty)
                        RadioGroup<String>(
                          groupValue: customerId,
                          onChanged: (id) {
                            if (editable) setState(() => customerId = id);
                          },
                          child: Column(
                            children: [
                              for (final candidate in candidates)
                                RadioListTile<String>(
                                  value: candidate['id'],
                                  enabled: editable,
                                  title: Text(candidate['name']),
                                  subtitle: Text(
                                    [candidate['email'], candidate['phone']]
                                        .where(
                                          (value) =>
                                              value != null &&
                                              value.toString().isNotEmpty,
                                        )
                                        .join(' · '),
                                  ),
                                ),
                            ],
                          ),
                        ),
                      if (candidates.isEmpty && item['customer'] == null)
                        const Text(
                          'Noch keine eindeutige Kundenzuordnung. Bei der Projektanlage kannst du einen bestehenden Kunden wählen oder einen neuen bestätigen.',
                        ),
                      const SizedBox(height: 14),
                      DropdownButtonFormField<String>(
                        isExpanded: true,
                        key: ValueKey('inquiry-status-${item['revision']}'),
                        initialValue: status,
                        decoration: const InputDecoration(
                          labelText: 'Stand der Anfrage',
                        ),
                        items: [
                          for (final entry in inquiryStatuses.entries.where(
                            (e) => e.key != 'converted',
                          ))
                            DropdownMenuItem(
                              value: entry.key,
                              child: Text(entry.value),
                            ),
                        ],
                        onChanged: editable
                            ? (value) => setState(() => status = value!)
                            : null,
                      ),
                      const SizedBox(height: 12),
                      DropdownButtonFormField<String>(
                        isExpanded: true,
                        key: ValueKey('inquiry-review-${item['revision']}'),
                        initialValue: review,
                        decoration: const InputDecoration(
                          labelText: 'Klärung / Aufmaß – falls benötigt',
                        ),
                        items: [
                          for (final entry in _reviews.entries)
                            DropdownMenuItem(
                              value: entry.key,
                              child: Text(entry.value),
                            ),
                        ],
                        onChanged: editable
                            ? (value) => setState(() => review = value!)
                            : null,
                      ),
                      if (status == 'accepted' || channel.isNotEmpty) ...[
                        const SizedBox(height: 12),
                        DropdownButtonFormField<String>(
                          isExpanded: true,
                          key: ValueKey('inquiry-channel-${item['revision']}'),
                          initialValue: channel,
                          decoration: const InputDecoration(
                            labelText: 'Zusage erhalten über',
                          ),
                          items: [
                            for (final entry in _channels.entries)
                              DropdownMenuItem(
                                value: entry.key,
                                child: Text(entry.value),
                              ),
                          ],
                          onChanged: editable
                              ? (value) => setState(() => channel = value!)
                              : null,
                        ),
                      ],
                      const SizedBox(height: 12),
                      TextField(
                        controller: next,
                        onChanged: (_) =>
                            setState(() => discardAllowed = false),
                        readOnly: !editable,
                        maxLines: 3,
                        maxLength: 2000,
                        decoration: const InputDecoration(
                          labelText: 'Nächster Schritt / Wiedervorlage',
                        ),
                      ),
                      TextField(
                        controller: due,
                        onChanged: (_) =>
                            setState(() => discardAllowed = false),
                        readOnly: !editable,
                        decoration: InputDecoration(
                          labelText: 'Wiedervorlage am',
                          hintText: 'TT.MM.JJJJ',
                          suffixIcon: IconButton(
                            tooltip: 'Datum wählen',
                            onPressed: editable ? pickDate : null,
                            icon: const Icon(Icons.calendar_today),
                          ),
                        ),
                      ),
                      const SizedBox(height: 12),
                      TextField(
                        controller: sevdesk,
                        onChanged: (_) =>
                            setState(() => discardAllowed = false),
                        readOnly: !editable,
                        maxLength: 2048,
                        decoration: const InputDecoration(
                          labelText:
                              'Angebot in Sevdesk – Verknüpfung (optional)',
                          hintText: 'https://my.sevdesk.de/…',
                        ),
                      ),
                      if ((item['sevdesk_url'] ?? '').isNotEmpty)
                        TextButton.icon(
                          onPressed: () =>
                              _openHttps(context, item['sevdesk_url']),
                          icon: const Icon(Icons.open_in_new),
                          label: const Text('In Sevdesk öffnen'),
                        ),
                      if (uncertain)
                        const Text(
                          'Antwort noch nicht bestätigt. Erneutes Übermitteln verwendet denselben Vorgang. Deine Angaben bleiben erhalten.',
                        ),
                      const SizedBox(height: 14),
                      Wrap(
                        spacing: 12,
                        runSpacing: 10,
                        children: [
                          FilledButton.icon(
                            onPressed: busy || (!editable && !uncertain)
                                ? null
                                : save,
                            icon: const Icon(Icons.save_outlined),
                            label: Text(
                              uncertain
                                  ? 'Erneut übermitteln'
                                  : 'Änderungen speichern',
                            ),
                          ),
                          OutlinedButton.icon(
                            onPressed: editable && status != 'declined'
                                ? convert
                                : null,
                            icon: const Icon(Icons.create_new_folder_outlined),
                            label: const Text('Als Projekt übernehmen'),
                          ),
                        ],
                      ),
                      const SizedBox(height: 12),
                      const Text(
                        'Du kannst Schritte überspringen oder zurückgehen. Ein Projekt kann schon zur Klärung entstehen; eine Zusage wird nur erfasst, wenn du sie ausdrücklich bestätigst.',
                      ),
                    ],
                  ],
                ],
              ),
      ),
    );
  }
}

class _ConvertInquiryDialog extends StatefulWidget {
  final OfficeApi api;
  final Map<String, dynamic> inquiry;
  final List<Map<String, dynamic>> customers;
  const _ConvertInquiryDialog({
    required this.api,
    required this.inquiry,
    required this.customers,
  });
  @override
  State<_ConvertInquiryDialog> createState() => _ConvertInquiryDialogState();
}

class _ConvertInquiryDialogState extends State<_ConvertInquiryDialog> {
  final form = GlobalKey<FormState>();
  late final TextEditingController project, name, email, phone;
  final address = TextEditingController();
  String mode = 'existing';
  String? customerId, error;
  bool busy = false, uncertain = false;
  Map<String, dynamic>? pending;

  @override
  void initState() {
    super.initState();
    project = TextEditingController(text: widget.inquiry['subject']);
    name = TextEditingController(text: widget.inquiry['sender_name']);
    email = TextEditingController(text: widget.inquiry['sender_email']);
    phone = TextEditingController(text: widget.inquiry['sender_phone']);
    final candidates = widget.inquiry['candidate_customers'] as List? ?? [];
    customerId =
        widget.inquiry['customer_id'] ??
        (candidates.length == 1 ? candidates.single['id'] : null);
    if (customerId != null &&
        !widget.customers.any((c) => c['id'] == customerId))
      customerId = null;
    if (widget.customers.isEmpty) mode = 'new';
  }

  @override
  void dispose() {
    for (final c in [project, name, email, phone, address]) {
      c.dispose();
    }
    super.dispose();
  }

  Future<void> submit() async {
    if (busy || !form.currentState!.validate()) return;
    if (mode == 'existing' && customerId == null) {
      setState(() => error = 'Bitte einen bestehenden Kunden auswählen.');
      return;
    }
    pending ??= {
      'request_id': offlineId(),
      'revision': widget.inquiry['revision'],
      'project_name': project.text.trim(),
      if (mode == 'existing') 'customer_id': customerId,
      if (mode == 'new')
        'customer': {
          'name': name.text.trim(),
          'email': email.text.trim(),
          'phone': phone.text.trim(),
          'address': address.text.trim(),
        },
    };
    setState(() {
      busy = true;
      error = null;
    });
    try {
      final result = Map<String, dynamic>.from(
        await widget.api.call(
          '/api/inquiries/${widget.inquiry['id']}/convert',
          pending,
        ),
      );
      if (mounted) Navigator.pop(context, result);
    } catch (e) {
      if (mounted)
        setState(() {
          error = _errorMessage(e);
          uncertain = _uncertain(e);
          if (!uncertain) pending = null;
        });
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  @override
  Widget build(BuildContext context) => AlertDialog(
    title: const Text('Anfrage mit Projekt verknüpfen'),
    content: SizedBox(
      width: 600,
      child: SingleChildScrollView(
        child: Form(
          key: form,
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              const Text(
                'Bestätige Kunde und Projekt. Dies legt die Projektmappe an und erfasst keine automatische Beauftragung.',
              ),
              const SizedBox(height: 14),
              TextFormField(
                controller: project,
                readOnly: busy || uncertain,
                maxLength: 500,
                decoration: const InputDecoration(labelText: 'Projektname'),
                validator: (v) => v?.trim().isEmpty ?? true
                    ? 'Bitte einen Projektnamen eingeben.'
                    : null,
              ),
              Wrap(
                spacing: 10,
                runSpacing: 8,
                children: [
                  ChoiceChip(
                    selected: mode == 'existing',
                    label: const Text('Bestehenden Kunden verwenden'),
                    onSelected: busy || uncertain || widget.customers.isEmpty
                        ? null
                        : (_) => setState(() => mode = 'existing'),
                  ),
                  ChoiceChip(
                    selected: mode == 'new',
                    label: const Text('Neuen Kunden bestätigen'),
                    onSelected: busy || uncertain
                        ? null
                        : (_) => setState(() => mode = 'new'),
                  ),
                ],
              ),
              if (mode == 'existing')
                DropdownButtonFormField<String>(
                  isExpanded: true,
                  initialValue: customerId,
                  decoration: const InputDecoration(labelText: 'Kunde'),
                  items: [
                    for (final customer in widget.customers)
                      DropdownMenuItem(
                        value: customer['id'],
                        child: Text(
                          customer['name'],
                          overflow: TextOverflow.ellipsis,
                        ),
                      ),
                  ],
                  onChanged: busy || uncertain
                      ? null
                      : (v) => setState(() => customerId = v),
                ),
              if (mode == 'new') ...[
                TextFormField(
                  controller: name,
                  readOnly: busy || uncertain,
                  maxLength: 500,
                  decoration: const InputDecoration(labelText: 'Name / Firma'),
                  validator: (v) => v?.trim().isEmpty ?? true
                      ? 'Bitte den Kundennamen eingeben.'
                      : null,
                ),
                TextFormField(
                  controller: email,
                  readOnly: busy || uncertain,
                  maxLength: 254,
                  decoration: const InputDecoration(labelText: 'E-Mail'),
                ),
                TextFormField(
                  controller: phone,
                  readOnly: busy || uncertain,
                  maxLength: 100,
                  decoration: const InputDecoration(labelText: 'Telefon'),
                ),
                TextFormField(
                  controller: address,
                  readOnly: busy || uncertain,
                  maxLines: 3,
                  maxLength: 2000,
                  decoration: const InputDecoration(labelText: 'Kundenadresse'),
                ),
              ],
              if (uncertain)
                const Text(
                  'Die Antwort ist noch nicht bestätigt. Wiederholen legt denselben Vorgang nicht doppelt an.',
                ),
              if (error != null) _errorBox(context, error!),
            ],
          ),
        ),
      ),
    ),
    actions: [
      TextButton(
        onPressed: busy ? null : () => Navigator.pop(context),
        child: const Text('Abbrechen'),
      ),
      FilledButton(
        onPressed: busy ? null : submit,
        child: Text(
          busy
              ? 'Wird angelegt …'
              : uncertain
              ? 'Erneut übermitteln'
              : 'Kunde und Projekt bestätigen',
        ),
      ),
    ],
  );
}

class GmailInboxPage extends StatefulWidget {
  final OfficeApi api;
  final String role;
  const GmailInboxPage({super.key, required this.api, required this.role});
  @override
  State<GmailInboxPage> createState() => _GmailInboxPageState();
}

class _GmailInboxPageState extends State<GmailInboxPage> {
  final name = TextEditingController(text: 'Gmail-Anfragen'),
      account = TextEditingController();
  List<Map<String, dynamic>> tokens = [];
  bool busy = false;
  String? error;
  bool get allowed => widget.role == 'owner' && widget.api.version == 'v1';
  @override
  void initState() {
    super.initState();
    if (allowed) load();
  }

  @override
  void dispose() {
    name.dispose();
    account.dispose();
    super.dispose();
  }

  Future<void> load() async {
    setState(() {
      busy = true;
      error = null;
    });
    try {
      final result = List<dynamic>.from(
        await widget.api.call('/api/inbound/gmail/tokens'),
      );
      if (mounted)
        setState(
          () => tokens = [
            for (final row in result) Map<String, dynamic>.from(row),
          ],
        );
    } catch (e) {
      if (mounted)
        setState(() {
          if (_denied(e)) tokens = [];
          error = e is ApiException && e.status == 404
              ? 'Die Gmail-Eingangseinrichtung benötigt das neue Serverupdate.'
              : _errorMessage(e);
        });
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  Future<void> issue() async {
    if (busy || !allowed) return;
    if (account.text.trim().isEmpty || name.text.trim().isEmpty) {
      setState(() => error = 'Bitte Bezeichnung und Gmail-Adresse eingeben.');
      return;
    }
    setState(() {
      busy = true;
      error = null;
    });
    try {
      final result = Map<String, dynamic>.from(
        await widget.api.call('/api/inbound/gmail/tokens', {
          'name': name.text.trim(),
          'source_account': account.text.trim(),
          'expires_days': 90,
        }),
      );
      if (!mounted) return;
      setState(() => busy = false);
      await showDialog<void>(
        context: context,
        builder: (_) => _OneTimeTokenDialog(token: result['token']),
      );
      if (mounted) {
        setState(() => busy = false);
        await load();
      }
    } catch (e) {
      if (mounted) setState(() => error = _errorMessage(e));
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  Future<void> revoke(Map<String, dynamic> token) async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Gmail-Eingang widerrufen?'),
        content: Text(
          '„${token['name']}“ kann anschließend keine weiteren Nachrichten übernehmen. Bereits gespeicherte Anfragen bleiben erhalten.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx, false),
            child: const Text('Abbrechen'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(ctx, true),
            child: const Text('Zugang widerrufen'),
          ),
        ],
      ),
    );
    if (confirmed != true || !mounted) return;
    setState(() {
      busy = true;
      error = null;
    });
    try {
      await widget.api.call(
        '/api/inbound/gmail/tokens/${token['id']}/revoke',
        {},
      );
      if (mounted) {
        setState(() => busy = false);
        await load();
      }
    } catch (e) {
      if (mounted) setState(() => error = _errorMessage(e));
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  String state(Map<String, dynamic> token) {
    if (token['revoked_at'] != null) return 'Widerrufen';
    final expires = DateTime.tryParse(token['expires_at']?.toString() ?? '');
    if (expires != null && !expires.isAfter(DateTime.now()))
      return 'Abgelaufen';
    if (token['last_used_at'] != null) return 'Nachrichtenübernahme bestätigt';
    return 'Wartet auf erste Nachrichtenübernahme';
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(
      title: const Text('Gmail-Eingang'),
      actions: [
        IconButton(
          tooltip: 'Gmail-Eingang aktualisieren',
          onPressed: busy || !allowed ? null : load,
          icon: const Icon(Icons.refresh),
        ),
      ],
    ),
    body: !allowed
        ? Center(
            child: Text(
              widget.role == 'owner'
                  ? 'Den Gmail-Eingang richtest du in der Online-App auf dem gemeinsamen Server ein.'
                  : 'Keine Berechtigung für die Eingangseinrichtung.',
            ),
          )
        : ListView(
            padding: const EdgeInsets.all(24),
            children: [
              Text(
                'Ausgewählte E-Mails als Anfragen übernehmen',
                style: Theme.of(context).textTheme.headlineMedium,
              ),
              const SizedBox(height: 10),
              const Text(
                'Der Mailbot übernimmt ausgewählte Gmail-Nachrichten als Anfragen und überträgt ihre Anhänge über einen geschützten Zugang an Smartplan. Den Bot richtest du mit der Anleitung ein; diese App verbindet sich nicht direkt mit deinem Google-Konto.',
              ),
              const SizedBox(height: 12),
              Align(
                alignment: Alignment.centerLeft,
                child: OutlinedButton.icon(
                  onPressed: () => _openHttps(context, _gmailGuide),
                  icon: const Icon(Icons.open_in_new),
                  label: const Text('Einrichtungsanleitung öffnen'),
                ),
              ),
              const SizedBox(height: 20),
              TextField(
                controller: name,
                enabled: !busy,
                maxLength: 100,
                decoration: const InputDecoration(labelText: 'Bezeichnung'),
              ),
              TextField(
                controller: account,
                enabled: !busy,
                maxLength: 254,
                keyboardType: TextInputType.emailAddress,
                decoration: const InputDecoration(
                  labelText: 'Gmail-Adresse des einzubindenden Postfachs',
                ),
              ),
              const SizedBox(height: 10),
              Align(
                alignment: Alignment.centerLeft,
                child: FilledButton.icon(
                  onPressed: busy ? null : issue,
                  icon: const Icon(Icons.key),
                  label: const Text('Eingangsschlüssel erstellen'),
                ),
              ),
              if (error != null) _errorBox(context, error!),
              if (busy) const LinearProgressIndicator(),
              const SizedBox(height: 24),
              Text(
                'Vorbereitete Postfächer',
                style: Theme.of(context).textTheme.titleLarge,
              ),
              const Text(
                'Eine erfolgreiche Verbindung wird erst nach der ersten tatsächlich übernommenen Nachricht bestätigt. Der Schlüssel allein verbindet noch kein Postfach.',
              ),
              if (tokens.isEmpty && !busy)
                const Padding(
                  padding: EdgeInsets.all(16),
                  child: Text('Noch kein Gmail-Eingang eingerichtet.'),
                ),
              for (final token in tokens)
                Card(
                  child: Padding(
                    padding: const EdgeInsets.all(16),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          token['name'],
                          style: Theme.of(context).textTheme.titleMedium,
                        ),
                        SelectableText(token['source_account']),
                        Text(state(token)),
                        if (token['last_used_at'] != null)
                          Text(
                            'Letzte Übernahme: ${_displayDate(token['last_used_at'], time: true)}',
                          ),
                        Text(
                          'Gültig bis: ${_displayDate(token['expires_at'], time: true)}',
                        ),
                        TextButton.icon(
                          onPressed: busy || token['revoked_at'] != null
                              ? null
                              : () => revoke(token),
                          icon: const Icon(Icons.link_off),
                          label: const Text('Zugang widerrufen'),
                        ),
                      ],
                    ),
                  ),
                ),
            ],
          ),
  );
}

class _OneTimeTokenDialog extends StatelessWidget {
  final String token;
  const _OneTimeTokenDialog({required this.token});
  @override
  Widget build(BuildContext context) => AlertDialog(
    title: const Text('Eingangsschlüssel einmalig übernehmen'),
    content: SizedBox(
      width: 580,
      child: SingleChildScrollView(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text(
              'Trage diesen Schlüssel nur in die geschützten Zugangsdaten-Einstellungen deines Bots ein. Er wird später nicht erneut angezeigt.',
            ),
            const SizedBox(height: 12),
            SelectableText(token),
            const SizedBox(height: 12),
            const Text(
              'Nicht im Chat teilen und keinen Screenshot dieses Schlüssels weitergeben.',
            ),
          ],
        ),
      ),
    ),
    actions: [
      TextButton(
        onPressed: () async {
          try {
            await Clipboard.setData(ClipboardData(text: token));
            if (context.mounted)
              ScaffoldMessenger.of(context).showSnackBar(
                const SnackBar(content: Text('Schlüssel kopiert.')),
              );
          } catch (_) {
            if (context.mounted)
              ScaffoldMessenger.of(context).showSnackBar(
                const SnackBar(
                  content: Text(
                    'Kopieren fehlgeschlagen. Bitte den Schlüssel markieren und manuell kopieren.',
                  ),
                ),
              );
          }
        },
        child: const Text('Schlüssel kopieren'),
      ),
      FilledButton(
        onPressed: () => Navigator.pop(context),
        child: const Text('Fertig'),
      ),
    ],
  );
}

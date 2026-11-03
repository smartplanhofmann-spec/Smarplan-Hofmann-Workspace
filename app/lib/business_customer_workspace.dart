import 'package:cryptography/cryptography.dart';
import 'package:flutter/material.dart';

import 'api.dart';
import 'business_document_access.dart' show documentClassNames;
import 'business_session.dart';
import 'business_widgets.dart';
import 'design.dart';
import 'mail_attachment_preview.dart';
import 'mail_attachment_widgets.dart' show exportMailAttachment;

/// Project-scoped internal management. Invitation secrets and original previews
/// live only in this page's memory and are revoked with the current access.
class BusinessCustomerWorkspacePage extends StatefulWidget {
  const BusinessCustomerWorkspacePage({super.key, required this.session});
  final BusinessSession session;
  @override
  State<BusinessCustomerWorkspacePage> createState() =>
      _CustomerWorkspaceState();
}

class _CustomerWorkspaceState extends State<BusinessCustomerWorkspacePage> {
  late final String project = widget.session.projectId ?? '';
  Map<String, dynamic>? state;
  String? error, notice, invitation, invitationGrant;
  bool loading = false;
  int epoch = 0;
  MailAttachmentPreviewController? preview;
  String? previewPermissions;
  bool get allowed =>
      project.isNotEmpty &&
      widget.session.projectId == project &&
      widget.session.hasFeature('customer_workspace_portal') &&
      widget.session.can('portal.manage') &&
      widget.session.can('documents.read');
  bool get writable =>
      allowed &&
      !loading &&
      state?['writes_allowed'] == true &&
      !widget.session.readonly &&
      widget.session.sectionEnabled('documents');
  List<Map<String, dynamic>> rows(String key) =>
      businessItems(state?[key] ?? []);
  Map<String, dynamic> get binding => businessMap(state?['project']);

  @override
  void initState() {
    super.initState();
    widget.session.addListener(changed);
    load();
  }

  void changed() {
    if (!mounted) return;
    if (!allowed) {
      epoch++;
      state = null;
      invitation = invitationGrant = null;
      preview?.revoke();
      loading = false;
    }
    if (preview != null &&
        previewPermissions !=
            (widget.session.permissions.toList()..sort()).join('|'))
      preview?.revoke();
    setState(() {});
  }

  @override
  void dispose() {
    epoch++;
    invitation = invitationGrant = null;
    widget.session.removeListener(changed);
    preview?.revoke();
    super.dispose();
  }

  Future<void> load() async {
    if (!allowed) return;
    final captured = ++epoch;
    setState(() {
      loading = true;
      error = null;
    });
    try {
      await widget.session.load();
      if (!mounted || captured != epoch || !allowed) return;
      final value = businessMap(
        await widget.session.read('/customer-workspace?project_id=$project'),
      );
      if (!mounted || captured != epoch || !allowed) return;
      if (businessMap(value['project'])['id'] != project) {
        throw const ApiException(
          0,
          'Die Antwort gehört nicht zum geöffneten Projekt.',
        );
      }
      setState(() {
        state = value;
        if (invitationGrant != null &&
            !rows('grants').any(
              (row) =>
                  row['id'] == invitationGrant && row['status'] == 'active',
            )) {
          invitation = invitationGrant = null;
        }
      });
    } on ApiException catch (e) {
      if (mounted && captured == epoch)
        setState(() {
          error = e.message;
          if ([401, 403, 404].contains(e.status)) {
            state = null;
            invitation = invitationGrant = null;
            preview?.revoke();
          }
        });
    } catch (_) {
      if (mounted && captured == epoch)
        setState(
          () => error = 'Kundenarbeitsbereich konnte nicht geladen werden.',
        );
    } finally {
      if (mounted && captured == epoch) setState(() => loading = false);
    }
  }

  Future<void> editor(
    String key,
    String title,
    String path,
    List<BusinessField> fields,
    Map<String, dynamic> initial,
    Map<String, dynamic> Function(Map<String, dynamic>) values, {
    void Function(Map<String, dynamic>)? result,
    String? writePermission,
    void Function(dynamic, Map<String, dynamic>)? validate,
  }) async {
    if (!writable) return;
    final captured = epoch;
    final saved = await showDialog<bool>(
      context: context,
      builder: (_) => BusinessEditor(
        session: widget.session,
        pendingKey: key,
        title: title,
        readPermission: 'portal.manage',
        writePermission: writePermission ?? 'portal.manage',
        readAllowed: () => mounted && captured == epoch && allowed,
        initial: initial,
        fields: fields,
        onSave: (input) async {
          await widget.session.load();
          if (!allowed ||
              captured != epoch ||
              !widget.session.sectionEnabled('documents')) {
            throw const ApiException(
              403,
              'Aktuelle Projektrechte und aktivierte Dokumente erforderlich.',
            );
          }
          if (input['confirmation'] != true)
            throw const FormatException('Bitte ausdrücklich bestätigen.');
          final attempted =
              widget.session.pendingCommandValues(key, path: path) ??
              values(input);
          final reply = businessMap(
            await (widget.session.pending(key)
                ? widget.session.repeatCustomerWorkspaceCommand(key)
                : widget.session.command(
                    key,
                    path,
                    attempted,
                    validateResult: validate == null
                        ? null
                        : (value) => validate(value, attempted),
                  )),
          );
          if (mounted && captured == epoch && allowed) result?.call(reply);
        },
      ),
    );
    if (mounted && saved == true) await load();
  }

  static const confirm = BusinessField(
    'confirmation',
    'Inhalt, Empfänger und Umfang sind geprüft',
    type: BusinessInput.toggle,
  );

  Future<void> createGrant() async {
    final customer = binding['customer_id'];
    await editor(
      'customer-grant-$project',
      'Kundenzugang erstellen',
      '/customer-workspace/grants',
      const [
        BusinessField(
          'recipient_name',
          'Vorgesehener Empfänger',
          required: true,
        ),
        BusinessField(
          'recipient_email',
          'E-Mail des Empfängers',
          required: true,
        ),
        BusinessField(
          'expires_in_days',
          'Gültigkeit in Tagen (1–30)',
          type: BusinessInput.integer,
          required: true,
        ),
        BusinessField(
          'allow_upload',
          'Kunde darf Dateien in den Posteingang übermitteln',
          type: BusinessInput.toggle,
        ),
        confirm,
      ],
      const {'expires_in_days': 7, 'allow_upload': false},
      (values) => {'project_id': project, 'customer_id': customer, ...values},
      result: (value) {
        final grant = businessMap(value['grant']);
        final url = value['portal_url'];
        final uri = url is String ? Uri.tryParse(url) : null;
        final fragment = uri == null
            ? <String, String>{}
            : Uri.splitQueryString(uri.fragment);
        final valid =
            value['link_available'] == true &&
            uri?.scheme == 'https' &&
            uri!.host.isNotEmpty &&
            uri.origin == Uri.parse(widget.session.api.base).origin &&
            uri.userInfo.isEmpty &&
            uri.query.isEmpty &&
            uri.path == '/office/customer-workspace.html' &&
            fragment.length == 2 &&
            fragment['grant'] == grant['id'] &&
            RegExp(r'^SPCI_[A-Za-z0-9_-]{43}$').hasMatch(fragment['key'] ?? '');
        setState(() {
          invitation = valid ? url as String : null;
          invitationGrant = valid ? '${grant['id']}' : null;
          notice = valid
              ? 'Link nur jetzt verfügbar. Geben Sie ihn selbst an den vorgesehenen Empfänger weiter.'
              : 'Zugang gespeichert; der Link wird nicht erneut ausgegeben. Bei verlorener Antwort diesen Zugang widerrufen und ausdrücklich neu erstellen.';
        });
      },
    );
  }

  Future<void> publishInfo() async {
    final existing = businessMap(state?['publication']),
        customer = binding['customer_id'];
    await editor(
      'customer-info-$project',
      'Projektinformation veröffentlichen',
      '/customer-workspace/publications',
      const [
        BusinessField('title', 'Öffentlicher Titel', required: true),
        BusinessField(
          'description',
          'Freigegebene Projektinformation',
          type: BusinessInput.multiline,
          required: true,
        ),
        BusinessField('status_label', 'Öffentlicher Projektstatus'),
        BusinessField('start_date', 'Beginn', type: BusinessInput.date),
        BusinessField('end_date', 'Ende', type: BusinessInput.date),
        BusinessField(
          'confirmation',
          'Diese Informationen für alle aktiven Projektzugänge veröffentlichen',
          type: BusinessInput.toggle,
        ),
      ],
      {
        for (final key in [
          'title',
          'description',
          'status_label',
          'start_date',
          'end_date',
        ])
          key: existing[key],
      },
      (values) => {
        'project_id': project,
        'customer_id': customer,
        'expected_revision': existing['revision'] ?? 0,
        ...values,
        'start_date': values['start_date'] == '' ? null : values['start_date'],
        'end_date': values['end_date'] == '' ? null : values['end_date'],
      },
    );
  }

  Future<void> publishFile(Map<String, dynamic> source) async {
    final customer = binding['customer_id'];
    await editor(
      'customer-file-${source['source_kind']}-${source['source_id']}',
      'Originaldatei für Kunden freigeben',
      '/customer-workspace/files',
      const [
        BusinessField('title', 'Öffentlicher Dateititel', required: true),
        confirm,
      ],
      {'title': source['title']},
      (values) => {
        'project_id': project,
        'customer_id': customer,
        'source_kind': source['source_kind'],
        'source_id': source['source_id'],
        'source_sha256': source['sha256'],
        ...values,
      },
      validate: (result, attempted) {
        final value = businessMap(result);
        if (value['project_id'] != project ||
            value['source_id'] != source['source_id'] ||
            value['source_kind'] != source['source_kind'] ||
            value['size'] != source['size'] ||
            value['media_type'] != source['media_type'] ||
            value['sha256'] != source['sha256']) {
          throw const ApiException(
            0,
            'Dateifreigabe konnte nicht der geprüften Quelle zugeordnet werden.',
          );
        }
      },
    );
  }

  Future<void> accept(Map<String, dynamic> upload) async {
    if (state?['can_accept'] != true) return;
    await editor(
      'customer-accept-${upload['id']}',
      'Kundendatei intern übernehmen',
      '/customer-workspace/uploads/${upload['id']}/accept',
      [
        BusinessField(
          'classification',
          'Interner Zugriff auf die Datei',
          type: BusinessInput.choice,
          required: true,
          choices: {
            for (final key in [
              'restricted',
              'operational',
              if (widget.session.can('finance.write')) 'financial',
              if (widget.session.can('personnel.manage')) 'personnel',
            ])
              key: documentClassNames[key]!,
          },
        ),
        confirm,
      ],
      const {'classification': 'restricted'},
      (values) => values,
      writePermission: 'documents.classify',
      validate: (result, attempted) {
        final value = businessMap(result);
        if (value['upload_id'] != upload['id'] ||
            value['classification'] != attempted['classification'] ||
            !RegExp(r'^[a-f0-9]{32}$').hasMatch('${value['media_id']}')) {
          throw const ApiException(
            0,
            'Interne Übernahme konnte nicht bestätigt werden.',
          );
        }
      },
    );
  }

  Future<void> original(Map<String, dynamic> file, String kind) async {
    if (!allowed || loading) return;
    final captured = epoch;
    final path = kind == 'source'
        ? '/customer-workspace/sources/${file['source_kind']}/${file['source_id']}/content?project_id=$project'
        : '/customer-workspace/$kind/${file['id']}/content';
    setState(() => loading = true);
    try {
      final bytes = await widget.session.api.bytes(
        widget.session.path(path),
        mediaType: '${file['media_type']}',
      );
      final hash = (await Sha256().hash(bytes)).bytes
          .map((byte) => byte.toRadixString(16).padLeft(2, '0'))
          .join();
      if (!mounted || captured != epoch || !allowed) return;
      if (hash != file['sha256'] || bytes.length != file['size'])
        throw const ApiException(
          0,
          'Originaldatei stimmt nicht mit Größe und Prüfsumme überein.',
        );
      final controller = MailAttachmentPreviewController(
        VerifiedMailAttachment(
          bytes: bytes,
          filename: '${file['filename']}',
          mediaType: '${file['media_type']}',
          sha256: hash,
        ),
      );
      preview = controller;
      previewPermissions = (widget.session.permissions.toList()..sort()).join(
        '|',
      );
      await Navigator.push<void>(
        context,
        MaterialPageRoute(
          builder: (_) => MailAttachmentPreviewPage(
            controller: controller,
            mayView: () => mounted && captured == epoch && allowed,
            exporter: exportMailAttachment,
          ),
        ),
      );
      if (preview == controller) preview = null;
      controller.dispose();
    } catch (e) {
      if (mounted && captured == epoch && allowed)
        setState(
          () => error = e is ApiException
              ? e.message
              : 'Original konnte nicht geöffnet werden.',
        );
    } finally {
      if (mounted && captured == epoch) setState(() => loading = false);
    }
  }

  Future<void> revoke(String kind, String id) async {
    if (!allowed || loading) return;
    final key = 'customer-revoke-$kind-$id',
        path = '/customer-workspace/$kind/$id/revoke';
    await showDialog<bool>(
      context: context,
      builder: (_) => _CustomerRevokeDialog(
        session: widget.session,
        operationKey: key,
        allowed: () => mounted && allowed,
        submit: (values) async {
          await widget.session.load();
          if (!allowed)
            throw const ApiException(403, 'Aktuelle Portalrechte fehlen.');
          if (widget.session.pending(key)) {
            await widget.session.repeatCustomerWorkspaceCommand(key);
          } else {
            await widget.session.command(key, path, values);
          }
          if (mounted && allowed && invitationGrant == id)
            setState(() => invitation = invitationGrant = null);
        },
      ),
    );
    if (mounted) await load();
  }

  Widget section(String title, List<Widget> children) => Card(
    child: Padding(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(title, style: Theme.of(context).textTheme.titleMedium),
          const SizedBox(height: 8),
          ...children,
        ],
      ),
    ),
  );

  @override
  Widget build(BuildContext context) {
    if (!allowed)
      return const BusinessEmpty(
        'Kundenportal nicht verfügbar',
        'Online-Dienst und aktuelle Portal- sowie Dokumentenrechte im Projekt sind erforderlich.',
      );
    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        Wrap(
          spacing: 12,
          runSpacing: 8,
          crossAxisAlignment: WrapCrossAlignment.center,
          children: [
            Text(
              'Kundenportal',
              style: Theme.of(context).textTheme.headlineSmall,
            ),
            TextButton.icon(
              onPressed: loading ? null : load,
              icon: const Icon(Icons.refresh),
              label: const Text('Aktualisieren'),
            ),
          ],
        ),
        const Text(
          'Kunden sehen ausdrücklich veröffentlichte Projektinformationen und Dateien. Eingehende Originale werden vor der internen Übernahme geprüft.',
        ),
        if (loading) const LinearProgressIndicator(),
        if (error != null) Notice(error!, error: true),
        if (notice != null) Notice(notice!),
        if (invitation != null)
          section('Einmaliger Zugangslink', [SelectableText(invitation!)]),
        if (state != null) ...[
          if (!writable)
            const Notice(
              'Veröffentlichung und Übernahme sind derzeit gesperrt. Vorhandene Zugänge und Dateien können widerrufen werden.',
            ),
          section('Projektinformation', [
            if (state!['publication'] == null)
              const Text('Noch keine Projektinformation veröffentlicht.')
            else ...[
              Text('${state!['publication']['title']}'),
              Text('${state!['publication']['description']}'),
              Text(
                'Fassung ${state!['publication']['revision']} · ${businessDate(state!['publication']['published_at'], time: true)}',
              ),
            ],
            FilledButton(
              onPressed: writable ? publishInfo : null,
              child: const Text('Projektinformation veröffentlichen'),
            ),
          ]),
          section('Kundenzugänge', [
            for (final grant in rows('grants'))
              ListTile(
                contentPadding: EdgeInsets.zero,
                title: Text(
                  '${grant['recipient_name']} · ${grant['recipient_email']}',
                ),
                subtitle: Text(
                  '${grant['status']} · bis ${businessDate(grant['expires_at'], time: true)} · Upload ${grant['allow_upload'] == true ? 'erlaubt' : 'gesperrt'}',
                ),
                trailing: grant['status'] == 'revoked'
                    ? null
                    : TextButton(
                        onPressed: loading
                            ? null
                            : () => revoke('grants', '${grant['id']}'),
                        child: const Text('Zugang widerrufen'),
                      ),
              ),
            FilledButton(
              onPressed: writable ? createGrant : null,
              child: const Text('Kundenzugang erstellen'),
            ),
          ]),
          section('Freigegebene Dateien', [
            if (rows('files').isEmpty) const Text('Keine Dateien freigegeben.'),
            for (final file in rows('files'))
              ListTile(
                contentPadding: EdgeInsets.zero,
                title: Text('${file['title']}'),
                subtitle: Text('${file['filename']} · ${file['status']}'),
                onTap: loading ? null : () => original(file, 'files'),
                trailing: file['status'] == 'revoked'
                    ? null
                    : TextButton(
                        onPressed: loading
                            ? null
                            : () => revoke('files', '${file['id']}'),
                        child: const Text('Datei widerrufen'),
                      ),
              ),
          ]),
          section('Originale zur Freigabe', [
            if (rows('source_files').isEmpty)
              const Text('Keine zugänglichen fertigen Projektoriginale.'),
            for (final file in rows('source_files'))
              ListTile(
                contentPadding: EdgeInsets.zero,
                title: Text('${file['title']}'),
                subtitle: Text('${file['filename']} · ${file['size']} Byte'),
                onTap: loading ? null : () => original(file, 'source'),
                trailing: TextButton(
                  onPressed: writable ? () => publishFile(file) : null,
                  child: const Text('Datei freigeben'),
                ),
              ),
          ]),
          section('Kundenposteingang', [
            if (rows('uploads').isEmpty)
              const Text('Keine Kundendateien eingegangen.'),
            for (final file in rows('uploads'))
              ListTile(
                contentPadding: EdgeInsets.zero,
                title: Text('${file['filename']}'),
                subtitle: Text(
                  '${file['note']}\n${file['status'] == 'accepted' ? 'Intern übernommen' : 'Eingegangen · noch nicht übernommen'}',
                ),
                onTap: loading ? null : () => original(file, 'uploads'),
                trailing: file['status'] == 'accepted'
                    ? null
                    : TextButton(
                        onPressed: writable && state!['can_accept'] == true
                            ? () => accept(file)
                            : null,
                        child: const Text('Intern übernehmen'),
                      ),
              ),
          ]),
        ],
      ],
    );
  }
}

class _CustomerRevokeDialog extends StatefulWidget {
  const _CustomerRevokeDialog({
    required this.session,
    required this.operationKey,
    required this.allowed,
    required this.submit,
  });
  final BusinessSession session;
  final String operationKey;
  final bool Function() allowed;
  final Future<void> Function(Map<String, dynamic>) submit;
  @override
  State<_CustomerRevokeDialog> createState() => _CustomerRevokeState();
}

class _CustomerRevokeState extends State<_CustomerRevokeDialog> {
  final reason = TextEditingController();
  bool busy = false;
  String? error;
  Map<String, dynamic>? frozen;
  @override
  void initState() {
    super.initState();
    frozen = widget.session.pendingEditorValues(widget.operationKey);
    reason.text = '${frozen?['reason'] ?? ''}';
    widget.session.addListener(changed);
  }

  void changed() {
    if (mounted) setState(() {});
  }

  @override
  void dispose() {
    widget.session.removeListener(changed);
    reason.dispose();
    super.dispose();
  }

  Future<void> submit() async {
    if (busy || !widget.allowed()) return;
    if (reason.text.trim().isEmpty) {
      setState(() => error = 'Widerrufsgrund angeben.');
      return;
    }
    final values = frozen ?? {'reason': reason.text.trim()};
    setState(() {
      busy = true;
      error = null;
    });
    try {
      await widget.submit(values);
      if (mounted && widget.allowed()) Navigator.pop(context, true);
    } catch (e) {
      if (widget.session.pending(widget.operationKey)) {
        frozen = values;
        widget.session.preservePendingEditor(widget.operationKey, values);
      }
      if (mounted)
        setState(
          () => error = e is ApiException
              ? e.message
              : 'Widerruf konnte nicht bestätigt werden.',
        );
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  @override
  Widget build(BuildContext context) => AlertDialog(
    title: const Text('Freigabe widerrufen'),
    content: SizedBox(
      width: 450,
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          if (!widget.allowed())
            const Text('Aktuelle Projektrechte fehlen.')
          else
            TextField(
              controller: reason,
              enabled: !busy && frozen == null,
              maxLength: 500,
              decoration: const InputDecoration(labelText: 'Widerrufsgrund'),
            ),
          if (error != null) Notice(error!, error: true),
          if (frozen != null)
            const Text(
              'Unbestätigter Widerruf wird unverändert erneut gesendet.',
            ),
        ],
      ),
    ),
    actions: [
      TextButton(
        onPressed: busy ? null : () => Navigator.pop(context),
        child: const Text('Schließen'),
      ),
      FilledButton(
        onPressed: busy || !widget.allowed() ? null : submit,
        child: Text(
          frozen == null ? 'Widerrufen' : 'Unverändert erneut senden',
        ),
      ),
    ],
  );
}

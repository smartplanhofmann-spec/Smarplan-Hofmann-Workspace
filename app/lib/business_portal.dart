import 'dart:async';

import 'package:flutter/material.dart';

import 'api.dart';
import 'business_session.dart';
import 'business_widgets.dart';
import 'design.dart';

String portalUtc(Object? value) {
  final date = DateTime.tryParse('$value')?.toUtc();
  if (date == null) return 'Nicht angegeben';
  String two(int n) => '$n'.padLeft(2, '0');
  return '${two(date.day)}.${two(date.month)}.${date.year} · ${two(date.hour)}:${two(date.minute)} UTC';
}

/// Internal management only. Invitation URLs remain in this widget's memory.
class BusinessOfferPortalPanel extends StatefulWidget {
  const BusinessOfferPortalPanel({
    super.key,
    required this.session,
    required this.offerId,
    required this.projectId,
    this.onOpenDocument,
  });
  final BusinessSession session;
  final String offerId, projectId;
  final ValueChanged<String>? onOpenDocument;
  @override
  State<BusinessOfferPortalPanel> createState() =>
      _BusinessOfferPortalPanelState();
}

class _BusinessOfferPortalPanelState extends State<BusinessOfferPortalPanel> {
  late final BusinessSession access;
  late final bool ownsAccess;
  Map<String, dynamic>? data;
  String? error, notice, freshUrl, freshGrant;
  bool busy = false, denied = false;
  int epoch = 0;

  bool get supported =>
      widget.session.allowed && widget.session.hasFeature('offer_portal');
  bool get mayRead =>
      supported &&
      access.error == null &&
      access.hasFeature('offer_portal') &&
      access.can('portal.manage') &&
      access.can('finance.read');
  bool get mayModify =>
      mayRead &&
      !denied &&
      !busy &&
      !access.readonly &&
      access.sectionEnabled('documents');
  bool get mayAdopt =>
      mayModify &&
      access.canWrite('finance.write') &&
      access.canWrite('projects.manage');
  bool get hasActiveGrant =>
      data != null &&
      businessItems(data).any((grant) {
        final expiry = DateTime.tryParse('${grant['expires_at']}');
        return grant['status'] == 'active' &&
            (expiry == null || expiry.isAfter(DateTime.now().toUtc()));
      });
  bool get mayCreate =>
      mayModify &&
      (!hasActiveGrant ||
          widget.session.pending('portal-create-${widget.offerId}'));

  @override
  void initState() {
    super.initState();
    ownsAccess = widget.session.projectId != widget.projectId;
    access = ownsAccess
        ? BusinessSession(
            api: widget.session.api,
            projectId: widget.projectId,
            projects: widget.session.projects,
          )
        : widget.session;
    access.addListener(changed);
    if (ownsAccess) widget.session.addListener(rootChanged);
    refresh();
  }

  void rootChanged() {
    if (!mounted) return;
    if (!supported) {
      epoch++;
      data = null;
      freshUrl = null;
      freshGrant = null;
      busy = false;
    } else if (!widget.session.loading && !access.loading) {
      unawaited(access.load());
    }
    setState(() {});
  }

  void changed() {
    if (!mounted) return;
    if (!mayRead) {
      data = null;
      freshUrl = null;
      freshGrant = null;
    }
    setState(() {});
  }

  @override
  void dispose() {
    epoch++;
    freshUrl = null;
    access.removeListener(changed);
    if (ownsAccess) {
      widget.session.removeListener(rootChanged);
      access.dispose();
    }
    super.dispose();
  }

  Future<void> refresh() async {
    if (!supported || busy) return;
    final current = ++epoch;
    setState(() {
      busy = true;
      error = null;
    });
    try {
      await access.load();
      if (!mounted || current != epoch || !mayRead) return;
      final result = businessMap(
        await widget.session.read(
          '/portal/grants?${Uri(queryParameters: {'offer_id': widget.offerId}).query}',
        ),
      );
      if (!mounted || current != epoch || !mayRead) return;
      setState(() {
        denied = false;
        data = result;
        if (freshGrant != null &&
            !businessItems(result).any(
              (grant) =>
                  grant['id'] == freshGrant && grant['status'] == 'active',
            )) {
          freshUrl = null;
          freshGrant = null;
        }
      });
    } catch (e) {
      if (mounted && current == epoch && mayRead)
        setState(() {
          error = e is ApiException
              ? e.message
              : 'Portalzugänge konnten nicht geladen werden.';
          if (e is ApiException && const [401, 403, 404].contains(e.status)) {
            denied = true;
            data = null;
            freshUrl = null;
            freshGrant = null;
          }
        });
    } finally {
      if (mounted && current == epoch) setState(() => busy = false);
    }
  }

  Future<void> requireAccess({
    bool mutation = true,
    bool adoption = false,
  }) async {
    await access.load();
    if (!mayRead ||
        (adoption &&
            (!access.can('finance.write') || !access.can('projects.manage')))) {
      throw const ApiException(403, 'Die erforderlichen Portalrechte fehlen.');
    }
    if (mutation && access.readonly) {
      throw const ApiException(
        403,
        'Im Rückkehrmodus können nur bestehende Portalzugänge widerrufen werden.',
      );
    }
    if (mutation && !access.sectionEnabled('documents')) {
      throw const ApiException(
        423,
        'Dokumente sind fachlich deaktiviert. Bestehende Zugänge können weiterhin widerrufen werden.',
      );
    }
  }

  Widget gated(Widget child) => AnimatedBuilder(
    animation: access,
    builder: (context, _) => mayRead
        ? child
        : AlertDialog(
            title: const Text('Portalzugriff nicht verfügbar'),
            content: const Text(
              'Die erforderlichen Projektrechte sind nicht mehr vorhanden.',
            ),
            actions: [
              TextButton(
                onPressed: () => Navigator.pop(context),
                child: const Text('Schließen'),
              ),
            ],
          ),
  );

  Future<void> create() async {
    final source = businessMap(data?['source']);
    if (!mayCreate || source.isEmpty) return;
    final sourceEpoch = epoch;
    final requestSession = widget.session;
    final key = 'portal-create-${widget.offerId}';
    final saved = await showDialog<bool>(
      context: context,
      builder: (_) => gated(
        BusinessEditor(
          session: access,
          pendingSession: requestSession,
          pendingKey: key,
          title: 'Finales Angebot für Kunden freigeben',
          readPermission: 'portal.manage',
          writePermission: 'portal.manage',
          initial: const {'expires_in_days': 7},
          fields: const [
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
              'Zugangsdauer in Tagen (1–30)',
              type: BusinessInput.integer,
              required: true,
            ),
            BusinessField(
              'confirmation',
              'Finales Angebot, Empfänger und Zugangsdauer sind geprüft. Den Link gebe ich selbst weiter.',
              type: BusinessInput.toggle,
            ),
          ],
          saveLabel: 'Portalzugang erstellen',
          onSave: (values) async {
            await requireAccess();
            final days = values['expires_in_days'];
            if (days is! int || days < 1 || days > 30)
              throw const FormatException(
                'Bitte eine Zugangsdauer von 1 bis 30 Tagen eingeben.',
              );
            if ('${values['recipient_name']}'.length > 200) {
              throw const FormatException(
                'Der Empfängername darf höchstens 200 Zeichen lang sein.',
              );
            }
            if ('${values['recipient_email']}'.length > 254 ||
                !RegExp(r'^[^@\s<>]+@[^@\s<>]+\.[^@\s<>]+$')
                    .hasMatch('${values['recipient_email']}')) {
              throw const FormatException(
                'Bitte eine gültige E-Mail-Adresse eingeben.',
              );
            }
            if (values['confirmation'] != true)
              throw const FormatException(
                'Bitte die geprüfte Freigabe ausdrücklich bestätigen.',
              );
            final result = businessMap(
              await requestSession.command(key, '/portal/grants', {
                'offer_id': widget.offerId,
                'source_revision': source['source_revision'],
                'content_hash': source['content_hash'],
                'pdf_hash': source['pdf_hash'],
                ...values,
              }),
            );
            if (!mounted || !mayRead || denied || sourceEpoch != epoch) return;
            final grant = businessMap(result['grant']);
            final url = result['portal_url'];
            final uri = url is String ? Uri.tryParse(url) : null;
            final fragment = uri == null
                ? <String, String>{}
                : Uri.splitQueryString(uri.fragment);
            final valid =
                result['link_available'] == true &&
                uri?.scheme == 'https' &&
                uri!.host.isNotEmpty &&
                uri.path == '/office/portal.html' &&
                fragment['grant'] == grant['id'] &&
                (fragment['key']?.startsWith('SPPI_') ?? false);
            setState(() {
              freshUrl = valid ? url as String : null;
              freshGrant = valid ? '${grant['id']}' : null;
              notice = valid
                  ? 'Zugang erstellt. Der Link wird nur jetzt angezeigt. Es wurde keine Nachricht versendet.'
                  : 'Der Zugang ist bereits vorhanden. Der Link kann nicht erneut ausgelesen werden. Widerrufen Sie diesen Zugang und erstellen Sie bei Bedarf ausdrücklich einen neuen.';
            });
          },
        ),
      ),
    );
    if (mounted && saved == true) await refresh();
  }

  Future<void> revokeGrant(Map<String, dynamic> grant) async {
    if (!mayRead || busy) return;
    final id = '${grant['id']}';
    final requestSession = widget.session;
    final saved = await showDialog<bool>(
      context: context,
      builder: (_) => gated(
        _PortalRevocationDialog(
          session: access,
          requestSession: requestSession,
          operationKey: 'portal-revoke-$id',
          onSave: (values) async {
            await requireAccess(mutation: false);
            await requestSession.command(
              'portal-revoke-$id',
              '/portal/grants/$id/revoke',
              values,
            );
            if (mounted && mayRead)
              setState(() {
                if (freshGrant == id) {
                  freshUrl = null;
                  freshGrant = null;
                }
                notice = 'Portalzugang widerrufen. Bereits gespeicherte Kundenerklärungen bleiben erhalten.';
              });
          },
        ),
      ),
    );
    if (mounted && saved == true) await refresh();
  }

  Future<void> adopt() async {
    final source = businessMap(data?['source']),
        decision = businessMap(data?['decision']);
    if (!mayAdopt ||
        decision['decision'] != 'accepted' ||
        data?['adoption'] != null)
      return;
    final requestSession = widget.session;
    final key = 'portal-adopt-${widget.offerId}';
    final saved = await showDialog<bool>(
      context: context,
      builder: (_) => gated(
        BusinessEditor(
          session: access,
          pendingSession: requestSession,
          pendingKey: key,
          readPermission: 'portal.manage',
          writePermission: 'finance.write',
          title: 'Angenommenes Angebot übernehmen',
          fields: const [
            BusinessField(
              'confirmation',
              'Diese Kundenerklärung und Angebotsfassung in einen Auftragsbestätigungsentwurf im bestehenden Projekt übernehmen.',
              type: BusinessInput.toggle,
            ),
          ],
          saveLabel: 'Auftragsbestätigungsentwurf erstellen',
          onSave: (values) async {
            await requireAccess(adoption: true);
            if (values['confirmation'] != true)
              throw const FormatException(
                'Bitte die Übernahme ausdrücklich bestätigen.',
              );
            await requestSession.command(
              key,
              '/portal/offers/${widget.offerId}/adopt',
              {
                'decision_id': decision['id'],
                'source_revision': source['source_revision'],
                'content_hash': source['content_hash'],
                'pdf_hash': source['pdf_hash'],
                'confirmation': true,
              },
            );
            if (mounted && mayRead)
              setState(
                () => notice = 'Auftragsbestätigungsentwurf angelegt. Es wurde nichts festgeschrieben, versendet oder bezahlt.',
              );
          },
        ),
      ),
    );
    if (mounted && saved == true) await refresh();
  }

  @override
  Widget build(BuildContext context) {
    if (!supported || (access.ready && !mayRead))
      return const SizedBox.shrink();
    final source = businessMap(data?['source']),
        decision = businessMap(data?['decision']),
        adoption = businessMap(data?['adoption']);
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(20),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Wrap(
              spacing: 12,
              runSpacing: 8,
              crossAxisAlignment: WrapCrossAlignment.center,
              children: [
                Text(
                  'Kundenportal für dieses Angebot',
                  style: Theme.of(context).textTheme.titleLarge,
                ),
                IconButton(
                  tooltip: 'Portalzugänge aktualisieren',
                  onPressed: busy ? null : refresh,
                  icon: const Icon(Icons.refresh),
                ),
              ],
            ),
            const Text(
              'Freigabe und Kundenerklärung betreffen ausschließlich dieses finale Angebot. Den Zugangslink geben Sie selbst weiter.',
            ),
            if (busy) const LinearProgressIndicator(),
            if (error != null) Notice(error!, error: true),
            if (notice != null) Notice(notice!),
            if (mayRead &&
                (access.readonly || !access.sectionEnabled('documents')))
              const Notice(
                'Neue Freigaben und Übernahmen sind gesperrt. Bestehende Zugänge können weiterhin widerrufen werden.',
              ),
            if (freshUrl != null && mayRead) ...[
              const SizedBox(height: 12),
              const Text('Einmalige Linkanzeige · vertraulich weitergeben'),
              SelectableText(
                freshUrl!,
                key: const ValueKey('portal-fresh-url'),
              ),
              TextButton(
                onPressed: () => setState(() {
                  freshUrl = null;
                  freshGrant = null;
                }),
                child: const Text('Link ausblenden'),
              ),
            ],
            if (hasActiveGrant && mayModify && !mayCreate)
              const Notice(
                'Es besteht bereits ein aktiver Zugang. Widerrufen Sie ihn ausdrücklich, bevor Sie einen neuen Zugang erstellen.',
              ),
            if (source.isNotEmpty && mayCreate)
              Padding(
                padding: const EdgeInsets.symmetric(vertical: 12),
                child: FilledButton.icon(
                  onPressed: create,
                  icon: const Icon(Icons.link),
                  label: const Text('Portalzugang erstellen'),
                ),
              ),
            if (data != null) ...[
              for (final grant in businessItems(data))
                Padding(
                  padding: const EdgeInsets.symmetric(vertical: 12),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        '${grant['principal']?['name']} · ${grant['principal']?['email']}',
                      ),
                      Text(
                        '${const {'active': 'Aktiv', 'expired': 'Abgelaufen', 'revoked': 'Widerrufen'}[grant['status']] ?? grant['status']} · gültig bis ${portalUtc(grant['expires_at'])}',
                      ),
                      Text('Erstellt: ${portalUtc(grant['created_at'])}'),
                      if (grant['revocation'] != null)
                        Text(
                          'Widerruf: ${businessMap(grant['revocation'])['reason'] ?? 'Dokumentiert'}',
                        ),
                      if (grant['status'] != 'revoked' && mayRead)
                        OutlinedButton(
                          onPressed: busy ? null : () => revokeGrant(grant),
                          child: const Text('Zugang widerrufen'),
                        ),
                    ],
                  ),
                ),
              if (businessItems(data).isEmpty)
                const Padding(
                  padding: EdgeInsets.symmetric(vertical: 12),
                  child: Text('Noch kein Portalzugang für dieses Angebot.'),
                ),
              if (decision.isNotEmpty) ...[
                const Divider(),
                Text(
                  decision['decision'] == 'accepted'
                      ? 'Kunde hat angenommen'
                      : 'Kunde hat abgelehnt',
                  style: Theme.of(context).textTheme.titleMedium,
                ),
                Text(
                  'Erklärter Name: ${decision['declared_name']} · ${portalUtc(decision['created_at'])}',
                ),
                Text('${decision['statement_text']}'),
                const Text(
                  'Gespeicherte Kundenerklärung; kein Zahlungsnachweis und keine qualifizierte elektronische Signatur.',
                ),
                if (decision['decision'] == 'accepted' &&
                    adoption.isEmpty &&
                    mayAdopt)
                  Padding(
                    padding: const EdgeInsets.only(top: 12),
                    child: FilledButton(
                      onPressed: adopt,
                      child: const Text(
                        'Annahme in Auftragsentwurf übernehmen',
                      ),
                    ),
                  ),
              ],
              if (adoption.isNotEmpty) ...[
                Text(
                  'Übernommen: ${portalUtc(adoption['created_at'])} · bestehendes Projekt',
                ),
                if (widget.onOpenDocument != null)
                  TextButton(
                    onPressed: () =>
                        widget.onOpenDocument!('${adoption['document_id']}'),
                    child: const Text('Auftragsbestätigungsentwurf öffnen'),
                  ),
              ],
            ],
          ],
        ),
      ),
    );
  }
}

class _PortalRevocationDialog extends StatefulWidget {
  const _PortalRevocationDialog({
    required this.session,
    required this.requestSession,
    required this.operationKey,
    required this.onSave,
  });
  final BusinessSession session, requestSession;
  final String operationKey;
  final Future<void> Function(Map<String, dynamic>) onSave;
  @override
  State<_PortalRevocationDialog> createState() =>
      _PortalRevocationDialogState();
}

class _PortalRevocationDialogState extends State<_PortalRevocationDialog> {
  final reason = TextEditingController();
  bool confirmation = false, busy = false;
  String? error;
  Map<String, dynamic>? frozen;
  bool get mayRead =>
      widget.session.can('portal.manage') && widget.session.can('finance.read');
  @override
  void initState() {
    super.initState();
    frozen = widget.requestSession.pendingEditorValues(widget.operationKey);
    reason.text = '${frozen?['reason'] ?? ''}';
    confirmation = frozen?['confirmation'] == true;
    widget.session.addListener(changed);
  }

  void changed() {
    if (mounted) setState(() {});
  }

  @override
  void dispose() {
    widget.session.removeListener(changed);
    reason.clear();
    reason.dispose();
    super.dispose();
  }

  Future<void> save() async {
    if (busy || !mayRead) return;
    if (reason.text.trim().isEmpty || !confirmation) {
      setState(
        () => error =
            'Bitte einen Widerrufsgrund angeben und den Widerruf bestätigen.',
      );
      return;
    }
    final attempted =
        frozen ?? {'reason': reason.text.trim(), 'confirmation': true};
    setState(() {
      busy = true;
      error = null;
    });
    try {
      await widget.onSave(Map<String, dynamic>.from(attempted));
      if (mounted && mayRead) Navigator.pop(context, true);
    } on ApiException catch (e) {
      final pending = widget.requestSession.pending(widget.operationKey);
      if (pending)
        widget.requestSession.preservePendingEditor(
          widget.operationKey,
          attempted,
        );
      if (mounted)
        setState(() {
          error = e.message;
          frozen = pending ? attempted : null;
        });
    } catch (_) {
      if (mounted)
        setState(() => error = 'Der Widerruf konnte nicht bestätigt werden.');
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  @override
  Widget build(BuildContext context) => AlertDialog(
    title: const Text('Portalzugang widerrufen'),
    content: SizedBox(
      width: 500,
      child: SingleChildScrollView(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            TextField(
              key: const ValueKey('portal-revocation-reason'),
              controller: reason,
              enabled: !busy && frozen == null && mayRead,
              maxLength: 500,
              decoration: const InputDecoration(labelText: 'Widerrufsgrund'),
            ),
            SwitchListTile.adaptive(
              contentPadding: EdgeInsets.zero,
              title: const Text(
                'Diesen Zugang einschließlich bestehender Portalsitzungen sperren',
              ),
              value: confirmation,
              onChanged: busy || frozen != null || !mayRead
                  ? null
                  : (value) => setState(() => confirmation = value),
            ),
            if (error != null) Notice(error!, error: true),
            if (frozen != null)
              const Notice(
                'Der Widerruf ist noch unbestätigt. Erneutes Senden verwendet denselben Vorgang.',
              ),
          ],
        ),
      ),
    ),
    actions: [
      TextButton(
        onPressed: busy ? null : () => Navigator.pop(context),
        child: const Text('Schließen'),
      ),
      FilledButton(
        onPressed: busy || !mayRead ? null : save,
        child: Text(
          frozen == null ? 'Zugang verbindlich widerrufen' : 'Erneut senden',
        ),
      ),
    ],
  );
}

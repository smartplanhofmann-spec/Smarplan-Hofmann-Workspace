import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:url_launcher/url_launcher.dart';

import 'api.dart';
import 'design.dart';
import 'offline_vault.dart' show offlineId;

const integrationNames = {
  'sevdesk': 'Sevdesk',
  'google_calendar': 'Google Kalender',
  'onedrive': 'OneDrive',
};

const integrationBotInstructions =
    'Erweitere den vorhandenen Fünfminutenjob, lege keinen zweiten Job an. Verwende die bereits verbundenen Google-Kalender- und OneDrive-Werkzeuge ausschließlich lesend. SMARTPLAN_INTAKE_TOKEN und bestätigte Mail-IDs unverändert erhalten. Den separaten SPIX-Zugang nur als geschützte Referenz SMARTPLAN_INTEGRATION_TOKEN binden, niemals im Chat anzeigen. Mit dieser Bindung ausschließlich GET https://office.smartplan-hofmann.de/api/v1/intake/integrations/jobs und POST https://office.smartplan-hofmann.de/api/v1/intake/integrations/jobs/{id}/result verwenden. Nur angeforderte Kataloge, Ressourcen und ausgewählte Projekt-IDs liefern; Original-IDs, Zeitzonen und Versionen erhalten. Vollständige echte Ergebnisse bestätigen, fehlende Fähigkeit als Fehler melden. Keine erfundenen leeren Listen, keine Finanzdaten abrufen und keine Dateien, Termine, Freigaben oder Einladungen verändern. Job- und Quittungsjournal für sichere identische Wiederholungen erhalten.';

Map<String, dynamic> integrationMap(Object? value) =>
    value is Map ? Map<String, dynamic>.from(value) : {};
List<Map<String, dynamic>> integrationRows(Object? value) => value is List
    ? value
          .whereType<Map>()
          .map((row) => Map<String, dynamic>.from(row))
          .toList()
    : [];
bool onlineIntegrationSession(OfficeApi api, {bool offline = false}) =>
    !offline &&
    api.version == 'v1' &&
    api.token != null &&
    api.token!.isNotEmpty &&
    !api.token!.startsWith('offline_');

String integrationState(Map<String, dynamic> value) {
  if (value['state'] == 'key_expired')
    return 'Integrationsschlüssel abgelaufen';
  if (value['connected'] == true) {
    if (value['state'] == 'stale' || value['error'] != null)
      return 'Stand prüfen';
    return 'Verbunden';
  }
  if (value['state'] == 'awaiting_bot') return 'Warte auf Bot-Daten';
  if (value['configured'] != true) return 'Einrichtung fehlt';
  return 'Nicht verbunden';
}

DateTime? integrationInstant(Object? value) => value is num
    ? DateTime.fromMillisecondsSinceEpoch((value * 1000).round(), isUtc: true)
    : DateTime.tryParse(value?.toString() ?? '');

String integrationSyncTime(Object value) {
  final date = integrationInstant(value)?.toLocal();
  if (date == null) return 'Zeitpunkt nicht verfügbar';
  String two(int n) => n.toString().padLeft(2, '0');
  return '${two(date.day)}.${two(date.month)}.${date.year} · ${two(date.hour)}:${two(date.minute)}';
}

Future<bool> openIntegrationUri(
  Uri uri, {
  Future<bool> Function(Uri)? opener,
}) async {
  if (uri.scheme != 'https' ||
      uri.userInfo.isNotEmpty ||
      (uri.hasPort && uri.port != 443))
    return false;
  return opener != null
      ? opener(uri)
      : launchUrl(uri, mode: LaunchMode.externalApplication);
}

class IntegrationsPage extends StatefulWidget {
  final OfficeApi api;
  final String role;
  final bool offlineMode;
  final Future<bool> Function(Uri)? openExternal;
  const IntegrationsPage({
    super.key,
    required this.api,
    required this.role,
    this.offlineMode = false,
    this.openExternal,
  });
  @override
  State<IntegrationsPage> createState() => _IntegrationsPageState();
}

class _IntegrationsPageState extends State<IntegrationsPage>
    with WidgetsBindingObserver {
  final access = ValueNotifier(true);
  final providers = <String, Map<String, dynamic>>{};
  late final String? session;
  bool loading = false, blocked = false, unavailable = false;
  String? error, working, botError;
  int epoch = 0;
  Timer? statusTimer;
  String? botRequest, botInstructions;
  bool get allowed =>
      mounted &&
      !blocked &&
      widget.role == 'owner' &&
      onlineIntegrationSession(widget.api, offline: widget.offlineMode) &&
      widget.api.token == session;

  @override
  void initState() {
    super.initState();
    session = widget.api.token;
    widget.api.addListener(changed);
    WidgetsBinding.instance.addObserver(this);
    if (allowed)
      statusTimer = Timer.periodic(const Duration(seconds: 30), (_) {
        if (working == null) unawaited(refresh());
      });
    if (allowed) unawaited(refresh());
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state == AppLifecycleState.resumed && allowed && working == null)
      unawaited(refresh());
  }

  void changed() {
    if (mounted && session != widget.api.token) deny();
  }

  void deny() {
    if (!mounted || blocked) return;
    epoch++;
    access.value = false;
    setState(() {
      blocked = true;
      providers.clear();
      loading = false;
      error = null;
    });
  }

  @override
  void dispose() {
    epoch++;
    access.value = false;
    widget.api.removeListener(changed);
    WidgetsBinding.instance.removeObserver(this);
    statusTimer?.cancel();
    access.dispose();
    super.dispose();
  }

  Future<void> refresh() async {
    if (!allowed || loading) return;
    final request = ++epoch;
    setState(() {
      loading = true;
      error = null;
    });
    try {
      final result = integrationMap(await widget.api.call('/api/integrations'));
      if (!allowed || request != epoch) return;
      if (result['providers'] is! List)
        throw const ApiException(0, 'Status nicht lesbar.');
      setState(() {
        providers.clear();
        for (final row in integrationRows(result['providers'])) {
          if (integrationNames.containsKey(row['id']))
            providers[row['id']] = row;
        }
        unavailable = false;
        if (result['instructions'] is String)
          botInstructions = result['instructions'];
      });
    } on ApiException catch (e) {
      if (!mounted || request != epoch) return;
      if (e.status == 401 || e.status == 403) {
        deny();
        return;
      }
      setState(() {
        providers.clear();
        unavailable = e.status == 404;
        error = unavailable ? null : 'Der Verbindungsstatus konnte nicht geladen werden. Bitte erneut versuchen.';
      });
    } catch (_) {
      if (allowed && request == epoch)
        setState(
          () => error = 'Der Verbindungsstatus konnte nicht geladen werden.',
        );
    } finally {
      if (mounted && request == epoch) setState(() => loading = false);
    }
  }

  Future<void> perform(
    String provider,
    String action,
    Map<String, dynamic> body,
  ) async {
    if (!allowed || working != null) {
      body.clear();
      return;
    }
    setState(() {
      working = provider;
      error = null;
    });
    String? failure;
    try {
      final response = await widget.api.call(
        '/api/integrations/$provider/$action',
        body,
      );
      if (!allowed) return;
      if (action == 'connect' && provider == 'google_calendar') {
        final uri = Uri.tryParse(
          integrationMap(response)['url']?.toString() ?? '',
        );
        const host = 'accounts.google.com';
        const path = '/o/oauth2/v2/auth';
        if (uri == null ||
            uri.host != host ||
            uri.path != path ||
            !await openIntegrationUri(uri, opener: widget.openExternal)) {
          throw const ApiException(
            0,
            'Die Anmeldeseite konnte nicht geöffnet werden.',
          );
        }
      }
    } on ApiException catch (e) {
      if (e.status == 401 || e.status == 403) {
        deny();
        return;
      }
      failure = e.status == 0 || e.status >= 500
          ? 'Die Antwort ist noch nicht bestätigt. Bitte zuerst den Status aktualisieren.'
          : e.message;
    } catch (_) {
      failure = 'Die Verbindung konnte nicht aktualisiert werden. Bitte den Status prüfen.';
    } finally {
      body.clear();
      if (allowed) {
        await refresh();
        if (allowed)
          setState(() {
            working = null;
            error = failure;
          });
      }
    }
  }

  Future<void> credentials(String provider) async {
    if (!allowed || working != null) return;
    final result = await showDialog<Map<String, dynamic>>(
      context: context,
      builder: (_) => _IntegrationCredentialsDialog(
        provider: provider,
        status: providers[provider] ?? {},
        access: access,
      ),
    );
    if (result == null) return;
    if (!allowed) {
      result.clear();
      return;
    }
    await perform(
      provider,
      provider == 'sevdesk' ? 'connect' : 'configure',
      result,
    );
  }

  Future<void> disconnect(String provider) async {
    final yes = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: Text('${integrationNames[provider]} trennen?'),
        content: const Text(
          'Smartplan zeigt verknüpfte Daten dieser Verbindung danach nicht mehr an. Die Daten beim Anbieter bleiben erhalten.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: const Text('Abbrechen'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(context, true),
            child: const Text('Verbindung trennen'),
          ),
        ],
      ),
    );
    if (yes == true && allowed)
      await perform(provider, 'disconnect', {'request_id': offlineId()});
  }

  Future<void> connectBot() async {
    if (!allowed || working != null) return;
    if (botRequest == null &&
        providers.values.any(
          (row) => row['method'] == 'bot' && row['configured'] == true,
        )) {
      final yes = await showDialog<bool>(
        context: context,
        builder: (context) => AlertDialog(
          title: const Text('Integrationsschlüssel erneuern?'),
          content: const Text(
            'Der bisherige Integrationsschlüssel wird ersetzt. Aktualisieren Sie danach nur dieses geschützte Zugangsfeld im vorhandenen Bot. Mailschlüssel und bestätigte Mail-IDs bleiben erhalten.',
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(context, false),
              child: const Text('Abbrechen'),
            ),
            FilledButton(
              onPressed: () => Navigator.pop(context, true),
              child: const Text('Schlüssel erneuern'),
            ),
          ],
        ),
      );
      if (yes != true || !allowed) return;
    }
    botRequest ??= offlineId();
    setState(() {
      working = 'bot';
      error = null;
      botError = null;
    });
    String? failure;
    Map<String, dynamic>? result;
    try {
      final response = await widget.api.call('/api/integrations/bot/connect', {
        'request_id': botRequest,
      });
      result = integrationMap(response);
      if (response is Map) response.remove('token');
      if (!allowed) return;
      final token = result.remove('token');
      if (token is! String ||
          !token.startsWith('SPIX_') ||
          result['expires_at'] is! String) {
        throw const ApiException(0, 'Integrationsschlüssel nicht bestätigt.');
      }
      botInstructions = (result['instructions'] as String?)?.replaceAll(
        token,
        '<geschützte Referenz SMARTPLAN_INTEGRATION_TOKEN>',
      );
      setState(() => working = null);
      await showDialog<void>(
        context: context,
        barrierDismissible: false,
        builder: (_) => _IntegrationBotKeyDialog(
          token: token,
          expiresAt: result!['expires_at'],
          access: access,
        ),
      );
      botRequest = null;
    } on ApiException catch (e) {
      if (e.status == 401 || e.status == 403) {
        deny();
        return;
      }
      if (e.status != 0 && e.status < 500 && e.status != 429) botRequest = null;
      failure = e.status == 0 || e.status >= 500
          ? 'Antwort noch nicht bestätigt. Erneutes Anfordern verwendet denselben Auftrag.'
          : e.message;
    } catch (_) {
      failure = 'Der Integrationszugang konnte nicht bestätigt werden. Bitte erneut prüfen.';
    } finally {
      result?.clear();
      if (allowed) {
        await refresh();
        if (allowed)
          setState(() {
            working = null;
            botError = failure;
          });
      }
    }
  }

  Widget botCard() => OfficeSurface(
    key: const ValueKey('integration-bot-card'),
    child: Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          'Vorhandenen Bot weiterverwenden',
          style: Theme.of(context).textTheme.titleLarge,
        ),
        const SizedBox(height: 10),
        const Text(
          'Google Kalender und OneDrive aus Ihrem vorhandenen Bot übernehmen, ohne neue Anbieteranmeldung.',
        ),
        const SizedBox(height: 12),
        Wrap(
          spacing: 8,
          runSpacing: 6,
          children: [
            for (final id in ['google_calendar', 'onedrive'])
              if (providers[id] != null && providers[id]!['method'] == 'bot')
                StatusPill(
                  '${integrationNames[id]} · ${integrationState(providers[id]!)}',
                ),
          ],
        ),
        const SizedBox(height: 14),
        if (botError != null) Notice(botError!),
        Wrap(
          spacing: 8,
          runSpacing: 8,
          children: [
            FilledButton(
              onPressed: working != null ? null : connectBot,
              child: Text(
                botRequest != null
                    ? 'Schlüssel erneut anfordern'
                    : 'Bot verbinden',
              ),
            ),
            OutlinedButton(
              onPressed:
                  working != null ||
                      !providers.values.any(
                        (row) =>
                            row['method'] == 'bot' && row['configured'] == true,
                      )
                  ? null
                  : () => perform('bot', 'sync', {}),
              child: const Text('Daten anfordern'),
            ),
            OutlinedButton.icon(
              onPressed: () => Clipboard.setData(
                ClipboardData(
                  text: botInstructions ?? integrationBotInstructions,
                ),
              ),
              icon: const Icon(Icons.copy_outlined),
              label: const Text('Botauftrag kopieren'),
            ),
          ],
        ),
        if (working == 'bot') const LinearProgressIndicator(),
        ExpansionTile(
          title: const Text('Einrichtung und Botauftrag'),
          children: [
            Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text(
                  'Fünfminutenjob, SPIN-Mailschlüssel und bestätigte Mail-IDs bleiben erhalten. Keinen zweiten Job anlegen. SMARTPLAN_INTAKE_TOKEN bleibt unverändert; der getrennte Integrationszugang wird geschützt als SMARTPLAN_INTEGRATION_TOKEN hinterlegt.',
                ),
                const SizedBox(height: 10),
                const Text(
                  'Bestätigte Kalender und Ordner erscheinen nach dem nächsten Botlauf. Der Status aktualisiert sich automatisch.',
                ),
                for (final expiry
                    in providers.values
                        .where(
                          (row) =>
                              row['method'] == 'bot' &&
                              row['expires_at'] != null,
                        )
                        .map((row) => row['expires_at'])
                        .toSet())
                  Text(
                    'Integrationszugang gültig bis: ${integrationSyncTime(expiry)}',
                  ),
                const SizedBox(height: 12),
                SelectableText(botInstructions ?? integrationBotInstructions),
              ],
            ),
          ],
        ),
      ],
    ),
  );

  Widget providerCard(String id) {
    final status = providers[id];
    return OfficeSurface(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Wrap(
            spacing: 12,
            runSpacing: 8,
            crossAxisAlignment: WrapCrossAlignment.center,
            children: [
              Text(
                integrationNames[id]!,
                style: Theme.of(context).textTheme.titleLarge,
              ),
              StatusPill(
                status == null
                    ? 'Status nicht verfügbar'
                    : integrationState(status),
              ),
            ],
          ),
          const SizedBox(height: 10),
          Text(switch (id) {
            'sevdesk' => 'Kontakte, Angebote und Rechnungen lesen. Je Projekt wählen Sie die passenden Belege selbst aus.',
            'google_calendar' => 'Kalender und ausgewählte Termine lesen. Smartplan erstellt keine Termine oder Einladungen.',
            _ => 'Einen OneDrive-Projektordner zuordnen und Dateien nach Ihrem Klick in OneDrive öffnen. Die vorhandene Botverbindung wird weiterverwendet.',
          }),
          if (status?['connected'] == true &&
              integrationMap(status?['identity'])['label'] != null)
            Padding(
              padding: const EdgeInsets.only(top: 10),
              child: Text(
                'Konto: ${integrationMap(status?['identity'])['label']}',
              ),
            ),
          if (status?['error'] != null)
            const Padding(
              padding: EdgeInsets.only(top: 10),
              child: Text(
                'Die Verbindung muss geprüft werden. Bitte Status aktualisieren; Zugangsdaten nicht im Chat teilen.',
              ),
            ),
          const SizedBox(height: 16),
          if (id == 'sevdesk')
            OutlinedButton(
              onPressed: working != null || status == null
                  ? null
                  : () => credentials(id),
              child: const Text('Zugang hinterlegen'),
            ),
          if (id != 'sevdesk' &&
              !(status?['method'] == 'oauth' && status?['configured'] == true))
            const Text(
              'Daten aus dem vorhandenen Bot. Kein erneutes Google- oder Microsoft-Login in Smartplan erforderlich.',
            ),
          if (id == 'google_calendar' &&
              status?['method'] == 'oauth' &&
              status?['configured'] == true)
            const Text(
              'Direkte Google-Verbindung. Die freigegebenen Kalender werden über Ihren Server gelesen.',
            ),
          if (id == 'google_calendar')
            ExpansionTile(
              title: const Text('Erweiterte Google-Direktverbindung'),
              subtitle: const Text(
                'Optional, wenn Sie den vorhandenen Bot nicht verwenden möchten.',
              ),
              children: [
                Wrap(
                  spacing: 8,
                  runSpacing: 8,
                  children: [
                    OutlinedButton(
                      onPressed: working != null || status == null
                          ? null
                          : () => credentials(id),
                      child: const Text('Anbieter einmalig einrichten'),
                    ),
                    FilledButton(
                      onPressed:
                          working != null || status?['configured'] != true
                          ? null
                          : () => perform(id, 'connect', {}),
                      child: const Text('Konto verbinden'),
                    ),
                  ],
                ),
              ],
            ),
          if (status?['connected'] == true || status?['configured'] == true)
            TextButton(
              onPressed: working != null ? null : () => disconnect(id),
              child: const Text('Verbindung trennen'),
            ),
          if (working == id)
            const Padding(
              padding: EdgeInsets.only(top: 12),
              child: LinearProgressIndicator(),
            ),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(
      title: const Text('Integrationen'),
      actions: [
        IconButton(
          tooltip: 'Verbindungsstatus aktualisieren',
          onPressed: allowed && !loading && working == null ? refresh : null,
          icon: const Icon(Icons.refresh),
        ),
      ],
    ),
    body: !allowed
        ? Center(
            child: Padding(
              padding: const EdgeInsets.all(28),
              child: Text(
                blocked
                    ? 'Zugriff nicht mehr verfügbar. Bitte online anmelden.'
                    : widget.role != 'owner'
                    ? 'Die Geschäftsführung verwaltet diese Verbindungen.'
                    : 'Integrationen sind nur mit einer Online-Anmeldung am gemeinsamen Server verfügbar.',
              ),
            ),
          )
        : ListView(
            padding: const EdgeInsets.all(24),
            children: [
              const PageHeading(
                title: 'Ihre Werkzeuge verbinden.',
                subtitle: 'Einmal einrichten. Im Projekt bewusst auswählen.',
              ),
              const SizedBox(height: 20),
              if (loading) const LinearProgressIndicator(),
              if (error != null) Notice(error!),
              if (unavailable)
                const Notice(
                  'Die Integrationen sind nach dem nächsten Serverupdate verfügbar. Bestehende Projektunterlagen bleiben nutzbar.',
                )
              else ...[
                Padding(
                  padding: const EdgeInsets.only(bottom: 16),
                  child: providerCard('sevdesk'),
                ),
                botCard(),
                const SizedBox(height: 16),
                for (final id in ['google_calendar', 'onedrive'])
                  Padding(
                    padding: const EdgeInsets.only(bottom: 16),
                    child: providerCard(id),
                  ),
              ],
            ],
          ),
  );
}

class _IntegrationCredentialsDialog extends StatefulWidget {
  final String provider;
  final Map<String, dynamic> status;
  final ValueNotifier<bool> access;
  const _IntegrationCredentialsDialog({
    required this.provider,
    required this.status,
    required this.access,
  });
  @override
  State<_IntegrationCredentialsDialog> createState() =>
      _IntegrationCredentialsDialogState();
}

class _IntegrationCredentialsDialogState
    extends State<_IntegrationCredentialsDialog> {
  final form = GlobalKey<FormState>();
  final token = TextEditingController(),
      client = TextEditingController(),
      secret = TextEditingController();
  @override
  void initState() {
    super.initState();
    widget.access.addListener(clearOnDeny);
  }

  void clearOnDeny() {
    if (!widget.access.value) {
      token.clear();
      client.clear();
      secret.clear();
    }
  }

  @override
  void dispose() {
    widget.access.removeListener(clearOnDeny);
    token.dispose();
    client.dispose();
    secret.dispose();
    super.dispose();
  }

  void submit() {
    if (!widget.access.value || !form.currentState!.validate()) return;
    final values = <String, dynamic>{
      'request_id': offlineId(),
      if (widget.provider == 'sevdesk')
        'api_token': token.text.trim()
      else ...{
        'client_id': client.text.trim(),
        'client_secret': secret.text.trim(),
      },
    };
    token.clear();
    client.clear();
    secret.clear();
    Navigator.pop(context, values);
  }

  @override
  Widget build(BuildContext context) => ValueListenableBuilder<bool>(
    valueListenable: widget.access,
    builder: (context, allowed, _) => AlertDialog(
      title: Text(
        allowed
            ? '${integrationNames[widget.provider]} einrichten'
            : 'Zugriff nicht mehr verfügbar',
      ),
      content: !allowed
          ? const Text('Bitte schließen und online anmelden.')
          : SizedBox(
              width: 560,
              child: SingleChildScrollView(
                child: Form(
                  key: form,
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      const Text(
                        'Zugangsdaten nur hier eingeben. Sie werden geschützt auf Ihrem Server gespeichert und nicht im Chat benötigt.',
                      ),
                      if (widget.provider != 'sevdesk') ...[
                        const SizedBox(height: 14),
                        Text(
                          'Einmalig im Google-Cloud-Konto: Calendar API aktivieren, OAuth-Zustimmung einrichten und einen Web-Client registrieren.',
                        ),
                        TextButton.icon(
                          onPressed: () => openIntegrationUri(
                            Uri.parse(
                              'https://console.cloud.google.com/apis/credentials',
                            ),
                          ),
                          icon: const Icon(Icons.open_in_new),
                          label: const Text('Anbieter-Einrichtung öffnen'),
                        ),
                        const SizedBox(height: 10),
                        const Text(
                          'Rücksprungadresse beim Anbieter exakt eintragen:',
                        ),
                        SelectableText(
                          widget.status['redirect_uri']?.toString() ?? 'Bitte zuerst den Verbindungsstatus aktualisieren.',
                        ),
                        if (widget.status['redirect_uri'] is String)
                          TextButton.icon(
                            onPressed: () => Clipboard.setData(
                              ClipboardData(
                                text: widget.status['redirect_uri'],
                              ),
                            ),
                            icon: const Icon(Icons.copy_outlined),
                            label: const Text('Rücksprungadresse kopieren'),
                          ),
                        for (final scope
                            in widget.status['scopes'] as List? ?? [])
                          Text('Leserecht: $scope'),
                      ],
                      const SizedBox(height: 16),
                      for (final field
                          in widget.provider == 'sevdesk'
                              ? [(token, 'Sevdesk API-Token', true)]
                              : [
                                  (client, 'Google Client-ID', false),
                                  (secret, 'Google Client-Secret', true),
                                ]) ...[
                        TextFormField(
                          controller: field.$1,
                          obscureText: field.$3,
                          autocorrect: false,
                          enableSuggestions: false,
                          autofillHints: const [],
                          decoration: InputDecoration(labelText: field.$2),
                          validator: (value) => value?.trim().isNotEmpty == true
                              ? null
                              : 'Bitte ausfüllen.',
                        ),
                        const SizedBox(height: 12),
                      ],
                    ],
                  ),
                ),
              ),
            ),
      actions: [
        TextButton(
          onPressed: () => Navigator.pop(context),
          child: const Text('Schließen'),
        ),
        if (allowed)
          FilledButton(
            onPressed: submit,
            child: const Text('Geschützt speichern'),
          ),
      ],
    ),
  );
}

class _IntegrationBotKeyDialog extends StatefulWidget {
  final String token, expiresAt;
  final ValueNotifier<bool> access;
  const _IntegrationBotKeyDialog({
    required this.token,
    required this.expiresAt,
    required this.access,
  });
  @override
  State<_IntegrationBotKeyDialog> createState() =>
      _IntegrationBotKeyDialogState();
}

class _IntegrationBotKeyDialogState extends State<_IntegrationBotKeyDialog> {
  String? token;
  @override
  void initState() {
    super.initState();
    token = widget.token;
    widget.access.addListener(changed);
  }

  void changed() {
    if (!widget.access.value && mounted) setState(() => token = null);
  }

  @override
  void dispose() {
    widget.access.removeListener(changed);
    token = null;
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => AlertDialog(
    title: Text(
      widget.access.value
          ? 'Integrationsschlüssel einmalig übernehmen'
          : 'Zugriff nicht mehr verfügbar',
    ),
    content: SizedBox(
      width: 560,
      child: SingleChildScrollView(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            if (token != null && widget.access.value) ...[
              const Text(
                'Nur im geschützten Bot-Zugangsfeld SMARTPLAN_INTEGRATION_TOKEN hinterlegen. Nicht in den Chat, Auftrag oder ein Protokoll kopieren. Der Mailschlüssel bleibt getrennt.',
              ),
              const SizedBox(height: 14),
              SelectableText(token!),
              const SizedBox(height: 14),
              Text('Gültig bis: ${integrationSyncTime(widget.expiresAt)}'),
            ] else
              const Text('Bitte schließen und online anmelden.'),
          ],
        ),
      ),
    ),
    actions: [
      if (token != null && widget.access.value)
        TextButton.icon(
          onPressed: () => Clipboard.setData(ClipboardData(text: token!)),
          icon: const Icon(Icons.copy_outlined),
          label: const Text('Schlüssel kopieren'),
        ),
      FilledButton(
        onPressed: () {
          token = null;
          Navigator.pop(context);
        },
        child: const Text('Fertig'),
      ),
    ],
  );
}

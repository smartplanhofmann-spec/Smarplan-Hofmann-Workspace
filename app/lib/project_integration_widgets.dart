import 'dart:async';
import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter/scheduler.dart';

import 'api.dart';
import 'design.dart';
import 'integration_pages.dart';
import 'mail_attachment_widgets.dart' show attachmentSize;
import 'offline_vault.dart' show offlineId;

Uri? oneDriveWebUri(Object? value) {
  final uri = Uri.tryParse(value?.toString() ?? '');
  if (uri == null ||
      uri.scheme != 'https' ||
      uri.userInfo.isNotEmpty ||
      (uri.hasPort && uri.port != 443))
    return null;
  return uri.host == 'onedrive.live.com' ||
          uri.host == '1drv.ms' ||
          uri.host.endsWith('.sharepoint.com')
      ? uri
      : null;
}

String externalEventTime(Map<String, dynamic> event) {
  if (event['status'] == 'cancelled') return 'Abgesagt';
  final start = DateTime.tryParse(event['start']?.toString() ?? '');
  final end = DateTime.tryParse(event['end']?.toString() ?? '');
  if (start == null) return 'Zeitangabe nicht verfügbar';
  String day(DateTime date) =>
      '${date.day.toString().padLeft(2, '0')}.${date.month.toString().padLeft(2, '0')}.${date.year}';
  String clock(DateTime date) =>
      '${date.hour.toString().padLeft(2, '0')}:${date.minute.toString().padLeft(2, '0')}';
  if (event['all_day'] == true) {
    final first = DateTime.utc(start.year, start.month, start.day);
    final last = end == null
        ? null
        : DateTime.utc(end.year, end.month, end.day - 1);
    return '${day(first)}${last != null && last.isAfter(first) ? ' – ${day(last)}' : ''} · Ganztägig';
  }
  final local = start.toLocal(), last = end?.toLocal();
  return '${day(local)} · ${clock(local)}${last != null ? ' – ${day(last) == day(local) ? '' : '${day(last)} · '}${clock(last)}' : ''}';
}

class ProjectIntegrationsController extends ChangeNotifier
    with WidgetsBindingObserver {
  final OfficeApi api;
  final String projectId, role;
  final bool offlineMode;
  final ValueNotifier<bool>? projectAccess;
  final VoidCallback? onDenied;
  final DateTime Function() clock;
  final syncAttempts = <String, DateTime>{};
  Timer? syncTimer;
  bool autoSyncRunning = false;
  final access = ValueNotifier(true);
  final providers = <String, Map<String, dynamic>>{};
  final busy = <String>{};
  late final String? session;
  bool loading = false,
      blocked = false,
      unavailable = false,
      financialVisible = false,
      disposed = false;
  String? error;
  int epoch = 0;
  ProjectIntegrationsController({
    required this.api,
    required this.projectId,
    required this.role,
    this.offlineMode = false,
    this.projectAccess,
    this.onDenied,
    DateTime Function()? clock,
  }) : clock = clock ?? DateTime.now {
    session = api.token;
    api.addListener(changed);
    projectAccess?.addListener(changed);
    WidgetsBinding.instance.addObserver(this);
    if (online)
      syncTimer = Timer.periodic(
        const Duration(seconds: 30),
        (_) => unawaited(refresh()),
      );
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state == AppLifecycleState.resumed && allowed) unawaited(refresh());
  }

  bool get online => onlineIntegrationSession(api, offline: offlineMode);
  bool get allowed =>
      !disposed &&
      !blocked &&
      online &&
      api.token == session &&
      projectAccess?.value != false;
  bool get owner => role == 'owner';
  String get base => '/api/projects/$projectId/integrations';
  void changed() {
    if (!disposed && (api.token != session || projectAccess?.value == false))
      deny();
  }

  void deny() {
    if (disposed || blocked) return;
    epoch++;
    blocked = true;
    providers.clear();
    access.value = false;
    notifyListeners();
    onDenied?.call();
  }

  @override
  void dispose() {
    disposed = true;
    epoch++;
    api.removeListener(changed);
    projectAccess?.removeListener(changed);
    WidgetsBinding.instance.removeObserver(this);
    syncTimer?.cancel();
    access.value = false;
    access.dispose();
    super.dispose();
  }

  Future<void> refresh() async {
    if (!allowed || loading) return;
    final current = ++epoch;
    loading = true;
    error = null;
    notifyListeners();
    try {
      final value = integrationMap(await api.call(base));
      if (!allowed || current != epoch) return;
      if (value['providers'] is! List)
        throw const ApiException(0, 'Integrationen nicht lesbar.');
      providers.clear();
      financialVisible =
          ['owner', 'accountant'].contains(role) &&
          value['financial_visible'] == true;
      for (final row in integrationRows(value['providers'])) {
        if (!integrationNames.containsKey(row['id']) ||
            (row['id'] == 'sevdesk' && !financialVisible))
          continue;
        providers[row['id']] = row;
      }
      unavailable = false;
    } on ApiException catch (e) {
      if (!allowed || current != epoch) return;
      if (e.status == 401 || e.status == 403) {
        deny();
        return;
      }
      providers.clear();
      if (e.status == 404) {
        try {
          final projects = integrationRows(await api.call('/api/projects'));
          if (!allowed || current != epoch) return;
          if (!projects.any((row) => row['id'] == projectId)) {
            deny();
            return;
          }
          unavailable = true;
        } catch (_) {
          if (allowed) error = 'Projektzugriff konnte nicht bestätigt werden. Bitte erneut laden.';
        }
      } else {
        error = 'Die verbundenen Werkzeuge konnten nicht geladen werden. Bitte Verbindung prüfen.';
      }
    } catch (_) {
      if (allowed && current == epoch) {
        providers.clear();
        error = 'Die verbundenen Werkzeuge konnten nicht geladen werden.';
      }
    } finally {
      if (!disposed && current == epoch) {
        loading = false;
        notifyListeners();
      }
    }
    if (allowed) unawaited(autoSync());
  }

  Future<void> autoSync() async {
    if (!allowed || autoSyncRunning) return;
    autoSyncRunning = true;
    try {
      for (final provider in providers.keys.toList()) {
        if (!allowed) return;
        final status = providers[provider];
        if (status?['connected'] != true ||
            status?['binding'] is! Map ||
            busy.contains(provider))
          continue;
        final confirmed = integrationInstant(status?['synced_at']);
        final now = clock();
        if (confirmed != null &&
            now.difference(confirmed) < const Duration(minutes: 5))
          continue;
        if (syncAttempts[provider] != null &&
            now.difference(syncAttempts[provider]!) <
                const Duration(minutes: 5))
          continue;
        syncAttempts[provider] = now;
        try {
          await command(provider, 'sync', {
            'revision': status?['revision'] ?? 0,
            'generation': status?['generation'],
          });
        } catch (_) {
          if (allowed) {
            error =
                '${integrationNames[provider]} konnte nicht aktualisiert werden. Der letzte bestätigte Stand bleibt gekennzeichnet.';
            notifyListeners();
          }
        }
      }
    } finally {
      autoSyncRunning = false;
    }
  }

  Future<dynamic> request(String path, Map<String, dynamic> body) async {
    if (!allowed) throw const ApiException(401, 'Bitte online anmelden.');
    try {
      final value = await api.call(path, body);
      if (!allowed)
        throw const ApiException(401, 'Der Zugriff ist nicht mehr verfügbar.');
      return value;
    } on ApiException catch (e) {
      if (e.status == 401 || e.status == 403) deny();
      rethrow;
    }
  }

  Future<void> command(
    String provider,
    String action,
    Map<String, dynamic> body,
  ) async {
    if (!allowed) throw const ApiException(401, 'Bitte online anmelden.');
    if (busy.contains(provider))
      throw const ApiException(409, 'Bitte den laufenden Vorgang abwarten.');
    busy.add(provider);
    notifyListeners();
    try {
      await request('$base/$provider/$action', body);
      if (allowed) await refresh();
    } on ApiException catch (e) {
      if (allowed && action == 'sync')
        providers[provider]?['client_refresh_error'] = true;
      if (allowed && e.status == 409) await refresh();
      rethrow;
    } catch (_) {
      if (allowed && action == 'sync')
        providers[provider]?['client_refresh_error'] = true;
      rethrow;
    } finally {
      if (!disposed) {
        busy.remove(provider);
        notifyListeners();
      }
    }
  }

  Future<void> openOneDriveFile(
    Map<String, dynamic> file, {
    Future<bool> Function(Uri)? opener,
  }) async {
    final status = providers['onedrive'];
    final address = file['web_url'] ?? file['webUrl'] ?? file['url'];
    final uri = oneDriveWebUri(address);
    final current = integrationRows(integrationMap(status?['data'])['files'])
        .any(
          (row) =>
              row['id'] == file['id'] &&
              (row['web_url'] ?? row['webUrl'] ?? row['url']) == address,
        );
    if (!allowed || status?['connected'] != true || !current) return;
    if (uri == null) {
      error = 'Für diese Datei fehlt eine bestätigte OneDrive-Adresse.';
      notifyListeners();
      return;
    }
    final opened = await openIntegrationUri(uri, opener: opener);
    if (!opened && allowed) {
      error = 'Die Datei konnte nicht in OneDrive geöffnet werden.';
      notifyListeners();
    }
  }
}

class ProjectIntegrationPanel extends StatelessWidget {
  final ProjectIntegrationsController controller;
  final String provider;
  final Future<bool> Function(Uri)? openExternal;
  const ProjectIntegrationPanel({
    super.key,
    required this.controller,
    required this.provider,
    this.openExternal,
  });
  Future<void> settings(BuildContext context) async {
    await Navigator.of(context).push<void>(
      MaterialPageRoute(
        builder: (_) => IntegrationsPage(
          api: controller.api,
          role: controller.role,
          openExternal: openExternal,
        ),
      ),
    );
    if (controller.allowed) await controller.refresh();
  }

  Future<void> link(BuildContext context) => showDialog<void>(
    context: context,
    builder: (_) => _ProjectIntegrationLinkDialog(
      controller: controller,
      provider: provider,
    ),
  );
  Future<void> action(BuildContext context, String action) async {
    final status = controller.providers[provider];
    if (status == null || !controller.allowed) return;
    if (action == 'unlink') {
      final yes = await showDialog<bool>(
        context: context,
        builder: (context) => AlertDialog(
          title: const Text('Zuordnung aus dem Projekt entfernen?'),
          content: const Text(
            'Die Daten beim Anbieter bleiben erhalten. Dieses Projekt zeigt sie danach nicht mehr an.',
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(context, false),
              child: const Text('Abbrechen'),
            ),
            FilledButton(
              onPressed: () => Navigator.pop(context, true),
              child: const Text('Zuordnung entfernen'),
            ),
          ],
        ),
      );
      if (yes != true || !controller.allowed) return;
    }
    try {
      await controller.command(provider, action, {
        'revision': status['revision'] ?? 0,
        'generation': status['generation'],
        if (action == 'unlink') 'request_id': offlineId(),
      });
    } on ApiException catch (e) {
      if (context.mounted && controller.allowed)
        ScaffoldMessenger.of(context)
            .showSnackBar(SnackBar(content: Text(e.message)));
    }
  }

  Widget finance(BuildContext context, Map<String, dynamic> data) => Column(
    crossAxisAlignment: CrossAxisAlignment.start,
    children: [
      Text(
        integrationMap(data['contact'])['name']?.toString() ??
            'Ausgewählter Sevdesk-Kontakt',
        style: Theme.of(context).textTheme.titleMedium,
      ),
      for (final group in [
        ('offers', 'Angebote'),
        ('invoices', 'Rechnungen'),
      ]) ...[
        const SizedBox(height: 12),
        Text(group.$2, style: const TextStyle(fontWeight: FontWeight.w600)),
        if (integrationRows(data[group.$1]).isEmpty)
          const Text('Keine Belege für dieses Projekt ausgewählt.'),
        for (final item in integrationRows(data[group.$1]))
          Padding(
            padding: const EdgeInsets.symmetric(vertical: 8),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text('${item['number'] ?? ''} ${item['title'] ?? ''}'.trim()),
                Text(
                  item['status_label']?.toString() ?? 'Status nicht bekannt',
                ),
                if (item['total_gross'] != null && item['currency'] != null)
                  Text('${item['total_gross']} ${item['currency']} · Brutto'),
                if (item['url'] is String)
                  TextButton.icon(
                    onPressed: () => openIntegrationUri(
                      Uri.parse(item['url']),
                      opener: openExternal,
                    ),
                    icon: const Icon(Icons.open_in_new),
                    label: const Text('In Sevdesk öffnen'),
                  ),
              ],
            ),
          ),
      ],
    ],
  );
  Widget calendar(BuildContext context, Map<String, dynamic> data) => Column(
    crossAxisAlignment: CrossAxisAlignment.start,
    children: [
      Text(
        integrationMap(data['calendar'])['name']?.toString() ??
            'Ausgewählter Kalender',
        style: Theme.of(context).textTheme.titleMedium,
      ),
      const Text(
        'Aus Google übernommen · nur lesen. Zeitangaben erscheinen in der Ortszeit dieses Geräts.',
      ),
      if (integrationRows(data['events']).isEmpty)
        const Padding(
          padding: EdgeInsets.only(top: 12),
          child: Text('Keine Termine für dieses Projekt ausgewählt.'),
        ),
      for (final item in integrationRows(data['events']))
        ListTile(
          contentPadding: EdgeInsets.zero,
          leading: const Icon(Icons.event_outlined),
          title: Text(item['title']?.toString() ?? 'Termin'),
          subtitle: Text(
            '${externalEventTime(item)}${item['location']?.toString().isNotEmpty == true ? '\n${item['location']}' : ''}${item['description']?.toString().isNotEmpty == true ? '\n${item['description']}' : ''}',
            maxLines: 8,
            overflow: TextOverflow.ellipsis,
          ),
        ),
    ],
  );
  Widget onedrive(BuildContext context, Map<String, dynamic> data) => Column(
    crossAxisAlignment: CrossAxisAlignment.start,
    children: [
      Text(
        integrationMap(data['folder'])['name']?.toString() ??
            'Ausgewählter Ordner',
        style: Theme.of(context).textTheme.titleMedium,
      ),
      const Text(
        'Dateien öffnen nach Ihrem Klick in OneDrive. Dort gelten Ihre Microsoft-Anmeldung und Zugriffsrechte.',
      ),
      if (integrationRows(data['files']).isEmpty)
        const Text(
          'Für diesen Ordner wurden noch keine Dateien bereitgestellt.',
        ),
      for (final file in integrationRows(data['files']))
        Padding(
          padding: const EdgeInsets.only(top: 14),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                file['name']?.toString() ?? 'Datei',
                style: const TextStyle(fontWeight: FontWeight.w600),
              ),
              if (file['size'] is int) Text(attachmentSize(file['size'])),
              TextButton.icon(
                onPressed:
                    oneDriveWebUri(
                          file['web_url'] ?? file['webUrl'] ?? file['url'],
                        ) ==
                        null
                    ? null
                    : () => controller.openOneDriveFile(
                        file,
                        opener: openExternal,
                      ),
                icon: const Icon(Icons.open_in_new),
                label: const Text('In OneDrive öffnen'),
              ),
            ],
          ),
        ),
    ],
  );

  @override
  Widget build(BuildContext context) => AnimatedBuilder(
    animation: controller,
    builder: (context, _) {
      if (provider == 'sevdesk' &&
          !['owner', 'accountant'].contains(controller.role))
        return const SizedBox();
      final status = controller.providers[provider];
      final data = status?['connected'] == true && status?['binding'] is Map
          ? integrationMap(status?['data'])
          : <String, dynamic>{};
      final confirmed = integrationInstant(status?['synced_at']);
      final stale =
          data.isNotEmpty &&
          (confirmed == null ||
              controller.clock().difference(confirmed) >=
                  const Duration(minutes: 5));
      return Padding(
        padding: const EdgeInsets.symmetric(vertical: 8),
        child: OfficeSurface(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Wrap(
                spacing: 12,
                runSpacing: 8,
                crossAxisAlignment: WrapCrossAlignment.center,
                children: [
                  Text(
                    provider == 'sevdesk'
                        ? 'Angebote und Rechnungen'
                        : integrationNames[provider]!,
                    style: Theme.of(context).textTheme.titleLarge,
                  ),
                  if (status != null) StatusPill(integrationState(status)),
                ],
              ),
              const SizedBox(height: 12),
              if (!controller.online)
                const Text(
                  'Diese Verbindung benötigt eine Online-Anmeldung. Lokale Projektangaben bleiben nutzbar.',
                )
              else if (controller.blocked)
                const Text(
                  'Zugriff nicht mehr verfügbar. Bitte online anmelden.',
                )
              else if (controller.unavailable)
                const Text(
                  'Die Integrationen werden nach dem Serverupdate verfügbar.',
                )
              else if (controller.loading && status == null)
                const LinearProgressIndicator()
              else if (status == null)
                Text(
                  controller.error ??
                      'Status noch nicht verfügbar. Bitte aktualisieren.',
                )
              else ...[
                if (status['state'] == 'sync_pending')
                  const Text(
                    'Bot-Aktualisierung vorgemerkt. Der letzte bestätigte Stand bleibt sichtbar.',
                  ),
                if (status['error'] != null ||
                    status['state'] == 'stale' ||
                    status['client_refresh_error'] == true ||
                    stale)
                  const Text(
                    'Letzter bestätigter Stand. Die Aktualisierung ist offen; bitte Verbindung prüfen.',
                  ),
                if (data.isNotEmpty)
                  switch (provider) {
                    'sevdesk' => finance(context, data),
                    'google_calendar' => calendar(context, data),
                    _ => onedrive(context, data),
                  }
                else
                  Text(
                    status['connected'] == true
                        ? status['binding'] is Map
                              ? 'Für diese Zuordnung liegen noch keine bestätigten Daten vor.'
                              : 'Für dieses Projekt ist noch keine Auswahl zugeordnet.'
                        : status['state'] == 'awaiting_bot'
                        ? 'Der Bot hat noch keine vollständige Kalender- oder Ordnerliste bestätigt.'
                        : 'Der Anbieter ist noch nicht verbunden.',
                  ),
                if (status['synced_at'] != null)
                  Padding(
                    padding: const EdgeInsets.only(top: 10),
                    child: Text(
                      'Zuletzt bestätigt: ${integrationSyncTime(status['synced_at'])}',
                    ),
                  ),
              ],
              if (controller.error != null && status != null)
                Notice(controller.error!),
              const SizedBox(height: 12),
              if (controller.allowed)
                Wrap(
                  spacing: 8,
                  runSpacing: 4,
                  children: [
                    OutlinedButton.icon(
                      onPressed:
                          controller.loading ||
                              controller.busy.contains(provider)
                          ? null
                          : controller.refresh,
                      icon: const Icon(Icons.refresh),
                      label: const Text('Status laden'),
                    ),
                    if (status?['binding'] is Map)
                      TextButton(
                        onPressed: controller.busy.contains(provider)
                            ? null
                            : () => action(context, 'sync'),
                        child: const Text('Daten aktualisieren'),
                      ),
                    if (controller.owner) ...[
                      if (status?['connected'] == true)
                        FilledButton(
                          onPressed: controller.busy.contains(provider)
                              ? null
                              : () => link(context),
                          child: Text(
                            provider == 'sevdesk'
                                ? 'Kontakt und Belege zuordnen'
                                : provider == 'google_calendar'
                                ? 'Kalender und Termine zuordnen'
                                : 'Ordner zuordnen',
                          ),
                        )
                      else
                        TextButton(
                          onPressed: () => settings(context),
                          child: const Text('Verbindung einrichten'),
                        ),
                      if (status?['binding'] is Map)
                        TextButton(
                          onPressed: controller.busy.contains(provider)
                              ? null
                              : () => action(context, 'unlink'),
                          child: const Text('Zuordnung entfernen'),
                        ),
                    ],
                  ],
                ),
              if (controller.busy.contains(provider))
                const LinearProgressIndicator(),
            ],
          ),
        ),
      );
    },
  );
}

class _ProjectIntegrationLinkDialog extends StatefulWidget {
  final ProjectIntegrationsController controller;
  final String provider;
  const _ProjectIntegrationLinkDialog({
    required this.controller,
    required this.provider,
  });
  @override
  State<_ProjectIntegrationLinkDialog> createState() =>
      _ProjectIntegrationLinkDialogState();
}

class _ProjectIntegrationLinkDialogState
    extends State<_ProjectIntegrationLinkDialog> {
  final query = TextEditingController();
  List<Map<String, dynamic>> items = [];
  Map<String, dynamic>? candidate, pending;
  final offers = <String>{}, invoices = <String>{}, events = <String>{};
  String? selected, error;
  String? pendingMessage;
  bool loading = false, saving = false, uncertain = false, conflict = false;
  late final int revision, generation;
  bool get sameGeneration =>
      widget.controller.allowed &&
      widget.controller.providers[widget.provider]?['connected'] == true &&
      widget.controller.providers[widget.provider]?['generation'] == generation;
  String get key => widget.provider == 'sevdesk'
      ? 'contact_id'
      : widget.provider == 'google_calendar'
      ? 'calendar_id'
      : 'folder_id';
  @override
  void initState() {
    super.initState();
    revision =
        widget.controller.providers[widget.provider]?['revision'] as int? ?? 0;
    generation =
        widget.controller.providers[widget.provider]?['generation'] as int? ??
        -1;
    widget.controller.addListener(connectionChanged);
    unawaited(catalog());
  }

  void connectionChanged() {
    if (!mounted ||
        (widget.controller.allowed &&
            widget.controller.providers[widget.provider]?['connected'] ==
                true &&
            widget.controller.providers[widget.provider]?['generation'] ==
                generation))
      return;
    items.clear();
    candidate = null;
    selected = null;
    pending = null;
    offers.clear();
    invoices.clear();
    events.clear();
    conflict = true;
    error = 'Die Verbindung wurde inzwischen geändert. Bitte schließen und die Auswahl neu öffnen.';
    if (SchedulerBinding.instance.schedulerPhase ==
        SchedulerPhase.persistentCallbacks) {
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (mounted) setState(() {});
      });
    } else {
      setState(() {});
    }
  }

  @override
  void dispose() {
    widget.controller.removeListener(connectionChanged);
    query.dispose();
    super.dispose();
  }

  String targetId(Map<String, dynamic> item) => widget.provider == 'onedrive'
      ? jsonEncode([item['drive_id'], item['id']])
      : item['id'] as String;
  Map<String, dynamic> get target =>
      items.firstWhere((item) => targetId(item) == selected, orElse: () => {});
  Map<String, dynamic> get selection => widget.provider == 'onedrive'
      ? {'drive_id': target['drive_id'], 'folder_id': target['id']}
      : {key: selected};
  List<Map<String, dynamic>> get visibleItems =>
      widget.provider != 'onedrive' || query.text.trim().isEmpty
      ? items
      : items
            .where(
              (row) => '${row['name']} ${row['path']}'.toLowerCase().contains(
                query.text.trim().toLowerCase(),
              ),
            )
            .toList();

  Future<void> catalog() async {
    if (!widget.controller.allowed || loading || saving) return;
    setState(() {
      loading = true;
      error = null;
      candidate = null;
      selected = null;
      pendingMessage = null;
    });
    try {
      final result = integrationMap(
        await widget.controller.request(
          '/api/integrations/${widget.provider}/catalog',
          {
            if (widget.provider == 'sevdesk' && query.text.trim().isNotEmpty)
              'query': query.text.trim(),
            if (widget.controller.providers[widget.provider]?['method'] ==
                'bot')
              'generation': generation,
          },
        ),
      );
      if (result['items'] is! List)
        throw const ApiException(
          0,
          'Die Anbieterliste konnte nicht gelesen werden.',
        );
      if (mounted && sameGeneration)
        setState(() {
          items = integrationRows(result['items']);
          if (result['pending'] == true) pendingMessage = 'Der Bot liefert die Liste beim nächsten Lauf. Der vorhandene Fünfminutenjob bleibt bestehen.';
        });
    } on ApiException catch (e) {
      if (mounted) setState(() => error = e.message);
    } catch (_) {
      if (mounted)
        setState(() => error = 'Auswahl konnte nicht geladen werden.');
    } finally {
      if (mounted) setState(() => loading = false);
    }
  }

  Future<void> preview() async {
    if (selected == null || loading || saving || conflict) return;
    final chosen = selected;
    setState(() {
      loading = true;
      error = null;
      candidate = null;
      pendingMessage = null;
    });
    try {
      final result = integrationMap(
        await widget.controller.request(
          '${widget.controller.base}/${widget.provider}/preview',
          {...selection, 'generation': generation},
        ),
      );
      if (!mounted || !widget.controller.allowed || chosen != selected) return;
      if (result['generation'] != generation)
        throw const ApiException(
          409,
          'Die Verbindung wurde inzwischen geändert. Bitte die Auswahl neu öffnen.',
        );
      if (result['pending'] == true) {
        setState(
          () => pendingMessage =
              result['message']?.toString() ??
              'Der Bot liefert die Auswahl beim nächsten Lauf.',
        );
        return;
      }
      final resource = integrationMap(
        result[widget.provider == 'sevdesk'
            ? 'contact'
            : widget.provider == 'google_calendar'
            ? 'calendar'
            : 'folder'],
      );
      if (resource['id'] !=
              (widget.provider == 'onedrive' ? target['id'] : chosen) ||
          (widget.provider == 'onedrive' &&
              resource['drive_id'] != target['drive_id'])) {
        throw const ApiException(
          409,
          'Die gelieferte Auswahl passt nicht zum gewählten Eintrag. Bitte die Auswahl neu laden.',
        );
      }
      final binding = integrationMap(
        widget.controller.providers[widget.provider]?['binding'],
      );
      setState(() {
        candidate = result;
        offers.clear();
        invoices.clear();
        events.clear();
        if (widget.provider == 'onedrive'
            ? binding['folder_id'] == target['id'] &&
                  binding['drive_id'] == target['drive_id']
            : binding[key] == chosen) {
          offers.addAll(
            (binding['offer_ids'] as List? ?? []).whereType<String>(),
          );
          invoices.addAll(
            (binding['invoice_ids'] as List? ?? []).whereType<String>(),
          );
          events.addAll(
            (binding['event_ids'] as List? ?? []).whereType<String>(),
          );
        }
      });
    } on ApiException catch (e) {
      if (mounted) setState(() => error = e.message);
    } catch (_) {
      if (mounted)
        setState(() => error = 'Inhalte konnten nicht geladen werden.');
    } finally {
      if (mounted) setState(() => loading = false);
    }
  }

  Future<void> save() async {
    if (candidate == null ||
        selected == null ||
        saving ||
        conflict ||
        !widget.controller.allowed)
      return;
    pending ??= {
      'revision': revision,
      'generation': generation,
      'request_id': offlineId(),
      ...selection,
      if (widget.provider == 'sevdesk') ...{
        'offer_ids': offers.toList(),
        'invoice_ids': invoices.toList(),
      },
      if (widget.provider == 'google_calendar') 'event_ids': events.toList(),
    };
    setState(() {
      saving = true;
      error = null;
    });
    try {
      await widget.controller.command(widget.provider, 'link', pending!);
      if (mounted && widget.controller.allowed) Navigator.pop(context);
    } on ApiException catch (e) {
      if (mounted)
        setState(() {
          uncertain = e.status == 0 || e.status >= 500;
          conflict = e.status == 409;
          if (!uncertain) pending = null;
          error = conflict
              ? 'Die Verbindung oder Zuordnung wurde geändert. Bitte schließen, den Status laden und Ihre Auswahl erneut prüfen.'
              : uncertain
              ? 'Die Antwort ist offen. Erneut zuordnen verwendet denselben Auftrag.'
              : e.message;
        });
    } catch (_) {
      if (mounted)
        setState(() {
          uncertain = true;
          error = 'Die Antwort ist offen. Bitte denselben Auftrag erneut versuchen.';
        });
    } finally {
      if (mounted) setState(() => saving = false);
    }
  }

  Widget choices(String list, Set<String> selectedIds) {
    final rows = integrationRows(candidate?[list]);
    final confirmed = integrationRows(
      integrationMap(
        widget.controller.providers[widget.provider]?['data'],
      )[list],
    );
    for (final row in confirmed) {
      if (selectedIds.contains(row['id']) &&
          !rows.any((item) => item['id'] == row['id']))
        rows.add(row);
    }
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          list == 'offers'
              ? 'Angebote'
              : list == 'invoices'
              ? 'Rechnungen'
              : 'Termine',
          style: const TextStyle(fontWeight: FontWeight.w600),
        ),
        if (rows.isEmpty) const Text('Keine Einträge verfügbar.'),
        for (final row in rows)
          CheckboxListTile(
            contentPadding: EdgeInsets.zero,
            controlAffinity: ListTileControlAffinity.leading,
            value: selectedIds.contains(row['id']),
            title: Text(
              row['title']?.toString().isNotEmpty == true
                  ? row['title']
                  : row['number']?.toString() ?? 'Eintrag',
            ),
            subtitle: Text(
              list == 'events'
                  ? externalEventTime(row)
                  : '${row['number'] ?? ''} · ${row['status_label'] ?? 'Status nicht bekannt'}',
            ),
            onChanged:
                saving ||
                    uncertain ||
                    conflict ||
                    (!selectedIds.contains(row['id']) &&
                        list == 'events' &&
                        selectedIds.length >= 50)
                ? null
                : (value) => setState(() {
                    value == true
                        ? selectedIds.add(row['id'])
                        : selectedIds.remove(row['id']);
                  }),
          ),
      ],
    );
  }

  @override
  Widget build(BuildContext context) => ValueListenableBuilder<bool>(
    valueListenable: widget.controller.access,
    builder: (context, allowed, _) => PopScope(
      canPop: !saving,
      child: AlertDialog(
        title: Text(
          allowed
              ? '${integrationNames[widget.provider]} diesem Projekt zuordnen'
              : 'Zugriff nicht mehr verfügbar',
        ),
        content: SizedBox(
          width: 620,
          child: SingleChildScrollView(
            child: !allowed
                ? const Text('Bitte schließen und online anmelden.')
                : Column(
                    mainAxisSize: MainAxisSize.min,
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const Text(
                        'Es werden nur die hier ausdrücklich ausgewählten Daten zugeordnet. Beim Anbieter wird nichts geändert.',
                      ),
                      const SizedBox(height: 14),
                      if (widget.provider == 'sevdesk')
                        TextField(
                          controller: query,
                          enabled: !loading && !saving && !uncertain,
                          decoration: const InputDecoration(
                            labelText: 'Kontakt suchen',
                          ),
                        ),
                      if (widget.provider == 'sevdesk')
                        TextButton(
                          onPressed: loading || saving || uncertain
                              ? null
                              : catalog,
                          child: const Text('Suchen'),
                        ),
                      if (loading) const LinearProgressIndicator(),
                      if (error != null) Notice(error!),
                      if (!loading && items.isEmpty && pendingMessage == null)
                        const Text(
                          'Keine Auswahl verfügbar. Verbindung und Rechte beim Anbieter prüfen.',
                        ),
                      if (widget.provider == 'onedrive')
                        TextField(
                          controller: query,
                          enabled: !saving && !uncertain && !conflict,
                          onChanged: (_) => setState(() {
                            selected = null;
                            candidate = null;
                            pendingMessage = null;
                          }),
                          decoration: const InputDecoration(
                            labelText: 'OneDrive-Ordner suchen',
                          ),
                        ),
                      if (pendingMessage != null) Text(pendingMessage!),
                      if (pendingMessage != null)
                        TextButton(
                          onPressed: loading || saving || uncertain
                              ? null
                              : selected == null
                              ? catalog
                              : preview,
                          child: Text(
                            selected == null
                                ? 'Bot-Liste erneut laden'
                                : 'Auswahl erneut laden',
                          ),
                        ),
                      if (visibleItems.isNotEmpty)
                        DropdownButtonFormField<String>(
                          key: ValueKey(
                            'integration-target-${items.map((item) => item['id']).join('|')}-$selected',
                          ),
                          initialValue: selected,
                          isExpanded: true,
                          decoration: InputDecoration(
                            labelText: widget.provider == 'sevdesk'
                                ? 'Kontakt'
                                : widget.provider == 'google_calendar'
                                ? 'Kalender'
                                : 'Ordner',
                          ),
                          items: [
                            for (final item in visibleItems)
                              DropdownMenuItem(
                                value: targetId(item),
                                child: Text(
                                  '${item['name']?.toString() ?? item['id']}${widget.provider == 'onedrive' && item['path']?.toString().isNotEmpty == true ? ' · ${item['path']}' : ''}',
                                  overflow: TextOverflow.ellipsis,
                                ),
                              ),
                          ],
                          onChanged: loading || saving || uncertain || conflict
                              ? null
                              : (value) => setState(() {
                                  selected = value;
                                  candidate = null;
                                  pendingMessage = null;
                                }),
                        ),
                      Wrap(
                        spacing: 8,
                        children: [
                          TextButton(
                            onPressed:
                                selected == null ||
                                    loading ||
                                    saving ||
                                    uncertain
                                ? null
                                : preview,
                            child: const Text('Inhalte anzeigen'),
                          ),
                        ],
                      ),
                      if (candidate != null) ...[
                        if (widget.provider == 'sevdesk') ...[
                          choices('offers', offers),
                          choices('invoices', invoices),
                        ],
                        if (widget.provider == 'google_calendar') ...[
                          choices('events', events),
                          Text(
                            widget.controller.providers[widget
                                        .provider]?['method'] ==
                                    'oauth'
                                ? 'Vorschau: letzte 31 Tage und nächste 366 Tage, höchstens 500 Termine. Bis zu 50 auswählen; keine Termine werden erstellt oder eingeladen. Bereits zugeordnete Termine bleiben auch außerhalb dieses Fensters verknüpft.'
                                : 'Vom vorhandenen Bot bestätigte Termine. Bis zu 50 ausdrücklich für dieses Projekt auswählen; keine Termine werden erstellt oder eingeladen.',
                          ),
                        ],
                        if (widget.provider == 'onedrive') ...[
                          Text(
                            'Ordner: ${integrationMap(candidate?['folder'])['name'] ?? selected}',
                          ),
                          for (final file in integrationRows(
                            candidate?['files'],
                          ))
                            Text(file['name']?.toString() ?? 'Datei'),
                          const Text(
                            'Dieser Ordner wird zugeordnet. Dateien werden erst nach Ihrem Klick geöffnet.',
                          ),
                        ],
                      ],
                    ],
                  ),
          ),
        ),
        actions: [
          TextButton(
            onPressed: saving ? null : () => Navigator.pop(context),
            child: const Text('Schließen'),
          ),
          if (allowed)
            FilledButton(
              onPressed: candidate == null || saving || loading || conflict
                  ? null
                  : save,
              child: Text(uncertain ? 'Erneut zuordnen' : 'Auswahl zuordnen'),
            ),
        ],
      ),
    ),
  );
}

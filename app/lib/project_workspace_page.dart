import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:file_selector/file_selector.dart';
import 'package:flutter/material.dart';
import 'package:url_launcher/url_launcher.dart';

import 'admin_pages.dart';
import 'api.dart';
import 'customer_pages.dart';
import 'design.dart';
import 'offline_plans.dart';
import 'offline_vault.dart' show offlineId;
import 'plan_pages.dart';
import 'project_workspace_forms.dart';
import 'mail_attachment_widgets.dart';

const projectSections = [
  'Übersicht',
  'Aufgaben',
  'Termine',
  'Bautagebuch',
  'Pläne',
  'Dokumente',
  'Berichte',
];

const _sectionIcons = [
  Icons.space_dashboard_outlined,
  Icons.check_circle_outline,
  Icons.calendar_today_outlined,
  Icons.menu_book_outlined,
  Icons.layers_outlined,
  Icons.folder_outlined,
  Icons.description_outlined,
];

String workspaceDate(Object? value, {bool time = false}) {
  if (value == null || value == '') return 'Ohne Datum';
  final parsed = DateTime.tryParse(value.toString());
  if (parsed == null) return value.toString();
  final date = time ? parsed.toLocal() : parsed;
  String two(int n) => n.toString().padLeft(2, '0');
  return '${two(date.day)}.${two(date.month)}.${date.year}'
      '${time ? ' · ${two(date.hour)}:${two(date.minute)}' : ''}';
}

Uri googleCalendarDraft(Map<String, dynamic> appointment, String address) {
  String stamp(Object? value) =>
      DateTime.parse(value as String)
          .toUtc()
          .toIso8601String()
          .replaceAll('-', '')
          .replaceAll(':', '')
          .split('.')
          .first +
      'Z';
  return Uri.https('calendar.google.com', '/calendar/render', {
    'action': 'TEMPLATE',
    'text': appointment['title'] as String,
    'dates':
        '${stamp(appointment['start_at'])}/${stamp(appointment['end_at'])}',
    'details': appointment['details'] as String? ?? '',
    'location': address,
  });
}

class ProjectWorkspacePage extends StatefulWidget {
  final OfficeApi api;
  final Map<String, dynamic> project;
  final String role;
  final OfflinePlans? repository;
  final Widget Function(Map<String, dynamic>) reportsBuilder;
  final Future<void> Function(Map<String, dynamic>)? calendarExport;
  final Future<bool> Function(Uri)? openExternal;
  final bool offlineMode;
  const ProjectWorkspacePage({
    super.key,
    required this.api,
    required this.project,
    required this.role,
    required this.reportsBuilder,
    this.repository,
    this.calendarExport,
    this.openExternal,
    this.offlineMode = false,
  });
  @override
  State<ProjectWorkspacePage> createState() => _ProjectWorkspacePageState();
}

class _ProjectWorkspacePageState extends State<ProjectWorkspacePage> {
  Map<String, dynamic>? dashboard;
  late Map<String, dynamic> project;
  late final ValueNotifier<Map<String, dynamic>> projectChanges;
  final lists = <String, List<Map<String, dynamic>>>{};
  final visited = <int>{0};
  var plansNavigator = GlobalKey<NavigatorState>();
  final reportsNavigator = GlobalKey<NavigatorState>();
  final working = <String>{};
  final actionRequests = <String, String>{};
  final accessAllowed = ValueNotifier<bool>(true);
  int section = 0;
  bool loading = true,
      refreshing = false,
      unavailable = false,
      denied = false,
      exporting = false;
  String? error, success, initialToken;
  String get base => '/api/projects/${widget.project['id']}';
  bool get canWrite => ['owner', 'manager', 'technician'].contains(widget.role);
  bool get canProfile => ['owner', 'manager'].contains(widget.role);
  bool get enabled => dashboard != null && !denied && !unavailable;
  bool get cachedWorkspace => widget.repository?.workspaceSupported ?? false;
  Map<String, dynamic> get profile =>
      Map<String, dynamic>.from(dashboard?['profile'] as Map? ?? {});
  List<Map<String, dynamic>> get team => rows(dashboard?['team']);
  List<Map<String, dynamic>> rows(Object? value) => value is List
      ? value
            .whereType<Map>()
            .map((row) => Map<String, dynamic>.from(row))
            .toList()
      : [];
  String? get activeKind => switch (section) {
    1 => 'tasks',
    2 => 'appointments',
    3 => 'diary',
    5 => 'links',
    _ => null,
  };

  @override
  void initState() {
    super.initState();
    project = Map<String, dynamic>.from(widget.project);
    projectChanges = ValueNotifier(project);
    initialToken = widget.api.token;
    widget.api.addListener(accessChanged);
    widget.repository?.addListener(accessChanged);
    if (cachedWorkspace) {
      try {
        final snapshot = widget.repository!.getWorkspace(widget.project['id']);
        if (snapshot != null) applySnapshot(snapshot);
      } on ApiException {
        /* The refresh reports a locked or expired project. */
      }
    }
    unawaited(reload());
  }

  void applySnapshot(Map<String, dynamic> snapshot) {
    dashboard = Map<String, dynamic>.from(snapshot);
    project = Map<String, dynamic>.from(snapshot['project'] as Map? ?? project);
    projectChanges.value = project;
    for (final kind in ['tasks', 'diary', 'appointments', 'links']) {
      if (snapshot[kind] is List) lists[kind] = rows(snapshot[kind]);
    }
    unavailable = false;
  }

  void accessChanged() {
    if (!mounted) return;
    if ((initialToken != null && widget.api.token == null) ||
        (widget.repository != null &&
            !widget.repository!.canAccessProject(widget.project['id']))) {
      denyAccess();
    } else if (cachedWorkspace && !denied) {
      try {
        final snapshot = widget.repository!.getWorkspace(widget.project['id']);
        if (snapshot != null) setState(() => applySnapshot(snapshot));
      } on ApiException catch (e) {
        if (e.status == 401 || e.status == 403) denyAccess();
      }
    }
  }

  void denyAccess() {
    if (!mounted) return;
    accessAllowed.value = false;
    setState(() {
      denied = true;
      dashboard = null;
      lists.clear();
      error = 'Projektzugriff ist nicht mehr verfügbar. Bitte online anmelden.';
    });
  }

  Future<dynamic> request(String path, [Map<String, dynamic>? body]) async {
    try {
      return await widget.api.call(path, body);
    } on ApiException catch (e) {
      if (e.status == 401 || e.status == 403) denyAccess();
      rethrow;
    }
  }

  Future<T> repositoryRequest<T>(Future<T> Function() operation) async {
    try {
      return await operation();
    } on ApiException catch (e) {
      if (e.status == 401 || e.status == 403) denyAccess();
      rethrow;
    }
  }

  @override
  void dispose() {
    widget.api.removeListener(accessChanged);
    widget.repository?.removeListener(accessChanged);
    accessAllowed.dispose();
    projectChanges.dispose();
    super.dispose();
  }

  Future<void> reload() async {
    if (!mounted || denied || refreshing) return;
    setState(() {
      refreshing = true;
      loading = dashboard == null;
      error = null;
    });
    try {
      if (cachedWorkspace) {
        if (!widget.offlineMode) {
          await repositoryRequest(
            () => widget.repository!.refreshWorkspace(widget.project['id']),
          );
        }
        if (!mounted || denied) return;
        final snapshot = widget.repository!.getWorkspace(widget.project['id']);
        if (snapshot != null) {
          setState(() => applySnapshot(snapshot));
        } else {
          setState(
            () => error = 'Diese Projektmappe wurde auf diesem Gerät noch nicht gespeichert. Bitte einmal mit Verbindung öffnen.',
          );
        }
        return;
      }
      final result = await request('$base/workspace');
      if (result is! Map ||
          result['project'] is! Map ||
          result['profile'] is! Map) {
        throw const ApiException(
          0,
          'Die Projektübersicht konnte nicht gelesen werden.',
        );
      }
      if (!mounted || denied) return;
      setState(() {
        dashboard = Map<String, dynamic>.from(result);
        project = Map<String, dynamic>.from(result['project']);
        projectChanges.value = project;
        unavailable = false;
      });
      final kind = activeKind;
      if (kind != null) await loadList(kind);
    } on ApiException catch (e) {
      if (!mounted) return;
      if (e.status == 404) {
        // A missing feature and a withdrawn project must not share a fallback.
        try {
          final projects = await request('/api/projects');
          if (!mounted || denied || !accessAllowed.value) return;
          final allowed = rows(projects)
              .any((row) => row['id'] == widget.project['id']);
          setState(() {
            unavailable = allowed;
            denied = !allowed;
            if (!allowed) accessAllowed.value = false;
            dashboard = null;
            lists.clear();
            error = allowed
                ? 'Die erweiterte Projektmappe ist noch nicht verfügbar. Pläne und Berichte können Sie weiter öffnen.'
                : 'Dieses Projekt ist nicht mehr verfügbar. Bitte zur Projektliste zurückkehren.';
          });
        } catch (_) {
          if (mounted)
            setState(() {
              denied = true;
              dashboard = null;
              lists.clear();
              error = 'Projektzugriff konnte nicht bestätigt werden. Bitte online anmelden.';
            });
        }
      } else {
        if (e.status == 401 || e.status == 403) {
          denyAccess();
          return;
        }
        setState(
          () => error = e.status == 0
              ? 'Die Projektmappe konnte nicht geladen werden. Bitte Verbindung prüfen und erneut laden.'
              : e.message,
        );
      }
    } catch (_) {
      if (mounted)
        setState(
          () => error = 'Die Projektmappe konnte nicht geladen werden. Pläne und Berichte bleiben erreichbar.',
        );
    } finally {
      if (mounted)
        setState(() {
          loading = false;
          refreshing = false;
        });
    }
  }

  Future<void> loadList(String kind) async {
    if (!enabled) return;
    try {
      if (cachedWorkspace) {
        final snapshot = widget.repository!.getWorkspace(widget.project['id']);
        if (snapshot != null && mounted)
          setState(() => applySnapshot(snapshot));
        return;
      }
      final result = await request('$base/$kind');
      if (result is! List)
        throw const ApiException(0, 'Liste konnte nicht gelesen werden.');
      if (mounted && !denied) setState(() => lists[kind] = rows(result));
    } on ApiException catch (e) {
      if (!mounted) return;
      if (e.status == 401 || e.status == 403) {
        denyAccess();
      } else {
        setState(
          () => error =
              'Die Liste konnte nicht aktualisiert werden. ${e.message}',
        );
      }
    } catch (_) {
      if (mounted)
        setState(
          () => error =
              'Die Liste konnte nicht aktualisiert werden. Bitte erneut laden.',
        );
    }
  }

  void selectSection(int value) {
    setState(() {
      section = value;
      visited.add(value);
    });
    final kind = activeKind;
    if (kind != null && !lists.containsKey(kind)) unawaited(loadList(kind));
  }

  void openImportedPlans() {
    if (!mounted || denied || widget.offlineMode) return;
    setState(() {
      // The server created this source outside the local plan editor. Reopen
      // the list so its normal load also discovers the new import, even when
      // this tab previously displayed a different plan or an empty list.
      plansNavigator = GlobalKey<NavigatorState>();
      section = 4;
      visited.add(4);
    });
  }

  Future<void> edit(String kind, [Map<String, dynamic>? initial]) async {
    if (!enabled || loading || !(kind == 'profile' ? canProfile : canWrite))
      return;
    final original = kind == 'profile' ? profile : initial;
    if (cachedWorkspace && original?['sync_status'] == 'Konflikt') {
      await resolveLocal(kind, original!);
      return;
    }
    var revision = original?['revision'] as int? ?? 0;
    String? fingerprint, requestId;
    final path = kind == 'profile'
        ? '$base/workspace'
        : '$base/$kind${initial == null ? '' : '/${initial['id']}'}';
    final saved = await showWorkspaceEditor(
      context,
      kind: kind,
      initial: original,
      team: team,
      accessAllowed: accessAllowed,
      onResolveConflict: () async {
        final response = await request(path);
        final current = kind == 'profile' && response is Map
            ? response['profile']
            : response;
        if (current is! Map || current['revision'] is! int) {
          throw const ApiException(
            0,
            'Die aktuelle Fassung konnte nicht geladen werden.',
          );
        }
        if (!mounted || denied) return false;
        final use = await showDialog<bool>(
          context: context,
          builder: (context) => ValueListenableBuilder<bool>(
            valueListenable: accessAllowed,
            builder: (context, allowed, _) => !allowed
                ? AlertDialog(
                    title: const Text('Projektzugriff nicht verfügbar'),
                    actions: [
                      TextButton(
                        onPressed: () => Navigator.pop(context, false),
                        child: const Text('Schließen'),
                      ),
                    ],
                  )
                : AlertDialog(
                    title: const Text('Aktuelle Fassung im Projekt'),
                    content: SizedBox(
                      width: 560,
                      child: SingleChildScrollView(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          mainAxisSize: MainAxisSize.min,
                          children: [
                            const Text(
                              'Diese Fassung wurde zwischenzeitlich gespeichert. Ihre Eingaben bleiben im Formular. Vergleichen Sie die Inhalte, bevor Sie sie erneut speichern.',
                            ),
                            const SizedBox(height: 16),
                            for (final entry in current.entries)
                              if (fieldLabels.containsKey(entry.key))
                                Padding(
                                  padding: const EdgeInsets.only(bottom: 12),
                                  child: Text(
                                    '${fieldLabels[entry.key]}: ${fieldValue(entry.key.toString(), entry.value)}',
                                  ),
                                ),
                          ],
                        ),
                      ),
                    ),
                    actions: [
                      TextButton(
                        onPressed: () => Navigator.pop(context, false),
                        child: const Text('Zurück zum Formular'),
                      ),
                      FilledButton(
                        onPressed: () => Navigator.pop(context, true),
                        child: const Text('Eigene Eingaben weiterverwenden'),
                      ),
                    ],
                  ),
          ),
        );
        if (use != true) return false;
        revision = current['revision'];
        fingerprint = null;
        return true;
      },
      onSave: (values) async {
        if (denied)
          throw const ApiException(
            403,
            'Projektzugriff ist nicht mehr verfügbar.',
          );
        if (cachedWorkspace) {
          final localValues = <String, dynamic>{
            ...values,
            if (kind == 'profile' || initial != null) 'revision': revision,
          };
          if (kind == 'profile') {
            await repositoryRequest(
              () => widget.repository!.saveWorkspaceProfile(
                widget.project['id'],
                localValues,
              ),
            );
          } else {
            await repositoryRequest(
              () => widget.repository!.saveWorkspaceItem(
                widget.project['id'],
                kind,
                localValues,
                id: initial?['local_id'] ?? initial?['id'],
              ),
            );
          }
          if (!mounted || denied) return;
          final snapshot = widget.repository!.getWorkspace(
            widget.project['id'],
          );
          setState(() {
            if (snapshot != null) applySnapshot(snapshot);
            success = snapshot?['workspace_sync_status'] == 'Konflikt'
                ? 'Auf diesem Gerät gespeichert. Eine zweite Fassung muss noch verglichen werden.'
                : 'Auf diesem Gerät gespeichert. Änderungen werden bei Verbindung abgeglichen.';
          });
          return;
        }
        final body = <String, dynamic>{
          ...values,
          if (kind == 'profile' || initial != null) 'revision': revision,
        };
        final encoded = jsonEncode(body);
        if (encoded != fingerprint) {
          fingerprint = encoded;
          requestId = offlineId();
        }
        final response = await request(path, {
          ...body,
          'request_id': requestId,
        });
        if (response is! Map || response['revision'] is! int) {
          throw const ApiException(
            0,
            'Die Speicherung konnte nicht bestätigt werden. Bitte erneut versuchen.',
          );
        }
        if (!mounted || denied) return;
        final result = Map<String, dynamic>.from(response);
        setState(() {
          success = 'Gespeichert.';
          if (kind == 'profile') {
            dashboard!['profile'] = result;
          } else {
            final current = lists[kind] ?? [];
            lists[kind] = [
              ...current.where((row) => row['id'] != result['id']),
              result,
            ];
          }
        });
      },
    );
    if (saved && mounted && !denied) {
      ScaffoldMessenger.of(context)
        ..clearSnackBars()
        ..showSnackBar(SnackBar(content: Text(success ?? 'Gespeichert.')));
      unawaited(reload());
    }
  }

  Future<void> completeTask(Map<String, dynamic> task) async {
    if (!canWrite || !enabled || working.contains(task['id'])) return;
    final id = task['id'] as String;
    setState(() => working.add(id));
    try {
      if (cachedWorkspace) {
        await repositoryRequest(
          () => widget.repository!.saveWorkspaceItem(
            widget.project['id'],
            'tasks',
            {'status': 'done', 'revision': task['revision']},
            id: task['local_id'] ?? task['id'],
          ),
        );
        if (mounted) {
          final snapshot = widget.repository!.getWorkspace(
            widget.project['id'],
          );
          setState(() {
            if (snapshot != null) applySnapshot(snapshot);
            success = 'Auf diesem Gerät als erledigt gespeichert.';
          });
        }
        return;
      }
      final key = '$id:${task['revision']}:done';
      await request('$base/tasks/$id', {
        'status': 'done',
        'revision': task['revision'],
        'request_id': actionRequests.putIfAbsent(key, offlineId),
      });
      if (mounted) {
        success = 'Aufgabe erledigt.';
        await reload();
      }
    } on ApiException catch (e) {
      if (mounted)
        showMessage(
          e.status == 409
              ? 'Die Aufgabe wurde inzwischen geändert. Bitte neu laden und den aktuellen Stand prüfen.'
              : e.message,
        );
    } catch (_) {
      if (mounted)
        showMessage(
          'Die Änderung konnte nicht bestätigt werden. Bitte erneut versuchen.',
        );
    } finally {
      if (mounted) setState(() => working.remove(id));
    }
  }

  Future<void> resolveLocal(String kind, Map<String, dynamic> local) async {
    if (!cachedWorkspace || denied) return;
    final remote = local['remote'];
    if (remote is! Map) {
      showMessage(
        'Bitte mit Verbindung neu laden, um die zweite Fassung zu vergleichen. Ihre Eingaben bleiben gespeichert.',
      );
      return;
    }
    final keep = await showDialog<bool>(
      context: context,
      builder: (context) => ValueListenableBuilder<bool>(
        valueListenable: accessAllowed,
        builder: (context, allowed, _) => !allowed
            ? AlertDialog(
                title: const Text('Projektzugriff nicht verfügbar'),
                actions: [
                  TextButton(
                    onPressed: () => Navigator.pop(context),
                    child: const Text('Schließen'),
                  ),
                ],
              )
            : AlertDialog(
                title: const Text('Zwei gespeicherte Fassungen'),
                content: SizedBox(
                  width: 620,
                  child: SingleChildScrollView(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        const Text(
                          'Die eigene Fassung und die Projektfassung wurden unabhängig geändert. Bitte vergleichen und bewusst auswählen.',
                        ),
                        for (final version in [
                          ('Auf diesem Gerät', local),
                          ('Im Projekt', remote),
                        ]) ...[
                          const SizedBox(height: 16),
                          Text(
                            version.$1,
                            style: Theme.of(context).textTheme.titleMedium,
                          ),
                          for (final entry in version.$2.entries)
                            if (fieldLabels.containsKey(entry.key))
                              Text(
                                '${fieldLabels[entry.key]}: ${fieldValue(entry.key.toString(), entry.value)}',
                              ),
                        ],
                      ],
                    ),
                  ),
                ),
                actions: [
                  TextButton(
                    onPressed: () => Navigator.pop(context),
                    child: const Text('Später'),
                  ),
                  TextButton(
                    onPressed: () => Navigator.pop(context, false),
                    child: const Text('Projektfassung übernehmen'),
                  ),
                  FilledButton(
                    onPressed: () => Navigator.pop(context, true),
                    child: const Text('Eigene Fassung weiterverwenden'),
                  ),
                ],
              ),
      ),
    );
    if (keep == null || !mounted || denied) return;
    try {
      await repositoryRequest(
        () => widget.repository!.resolveWorkspaceConflict(
          widget.project['id'],
          kind,
          kind == 'profile'
              ? widget.project['id']
              : local['local_id'] ?? local['id'],
          keepLocal: keep,
        ),
      );
      final snapshot = widget.repository!.getWorkspace(widget.project['id']);
      if (mounted && snapshot != null)
        setState(() {
          applySnapshot(snapshot);
          success = 'Die gewählte Fassung ist auf diesem Gerät gespeichert.';
        });
    } on ApiException catch (e) {
      showMessage(e.message);
    } catch (_) {
      showMessage(
        'Die Auswahl konnte nicht gespeichert werden. Beide Fassungen bleiben erhalten.',
      );
    }
  }

  void showMessage(String message) {
    if (!mounted) return;
    setState(() => error = message);
    ScaffoldMessenger.of(context)
        .showSnackBar(SnackBar(content: Text(message)));
  }

  Future<void> openLink(Uri uri) async {
    if (uri.scheme != 'https' || uri.host.isEmpty || uri.userInfo.isNotEmpty) {
      showMessage(
        'Bitte einen gültigen HTTPS-Link ohne Zugangsdaten verwenden.',
      );
      return;
    }
    try {
      final opened =
          await (widget.openExternal?.call(uri) ??
              launchUrl(uri, mode: LaunchMode.externalApplication));
      if (!opened) showMessage('Der Link konnte nicht geöffnet werden.');
    } catch (_) {
      showMessage(
        'Der Link konnte nicht geöffnet werden. Bitte die Geräteinstellungen prüfen.',
      );
    }
  }

  Future<void> exportCalendar(Map<String, dynamic> appointment) async {
    if (exporting || !enabled) return;
    setState(() => exporting = true);
    try {
      if (widget.calendarExport != null) {
        await widget.calendarExport!(appointment);
      } else {
        final location = await getSaveLocation(
          suggestedName: 'termin-${appointment['id']}.ics',
          acceptedTypeGroups: [
            const XTypeGroup(label: 'Kalenderdatei', extensions: ['ics']),
          ],
        );
        if (location == null || denied || !accessAllowed.value) return;
        final bytes = await widget.api.bytes(
          '$base/appointments/${appointment['id']}/calendar',
          mediaType: 'text/calendar',
          maxBytes: 262144,
        );
        if (denied || !accessAllowed.value) return;
        await File(location.path).writeAsBytes(bytes, flush: true);
      }
      if (mounted)
        setState(
          () => success = 'Kalenderdatei gespeichert. Sie kann in Ihren Kalender importiert werden.',
        );
    } on ApiException catch (e) {
      if (e.status == 401 || e.status == 403) denyAccess();
      showMessage(
        'Die Kalenderdatei konnte nicht gespeichert werden. Der Termin im Projekt bleibt erhalten.',
      );
    } catch (_) {
      showMessage(
        'Die Kalenderdatei konnte nicht gespeichert werden. Der Termin im Projekt bleibt erhalten.',
      );
    } finally {
      if (mounted) setState(() => exporting = false);
    }
  }

  Future<void> changeCustomer() async {
    if (widget.role != 'owner' || denied || widget.offlineMode) return;
    try {
      final result = await request('/api/customers');
      if (!mounted || denied) return;
      final selected = await showDialog<String>(
        context: context,
        builder: (_) => CustomerAssignmentDialog(
          customers: rows(result).where((row) => row['active'] == 1).toList(),
          customerId: project['customer_id'],
        ),
      );
      if (selected == null || !mounted || denied) return;
      final updated = await request('$base/customer', {
        'customer_id': selected,
      });
      if (mounted)
        setState(() {
          project = Map<String, dynamic>.from(updated);
          projectChanges.value = project;
        });
      await reload();
    } on ApiException catch (e) {
      showMessage(e.message);
    } catch (_) {
      showMessage(
        'Der Kunde konnte nicht zugeordnet werden. Bitte erneut versuchen.',
      );
    }
  }

  static const fieldLabels = {
    'description': 'Beschreibung',
    'site_address': 'Baustelle',
    'phase': 'Projektphase',
    'deposit_status': 'Anzahlung',
    'materials_status': 'Material',
    'start_date': 'Projektbeginn',
    'end_date': 'Projektende',
    'title': 'Titel',
    'details': 'Beschreibung',
    'status': 'Status',
    'priority': 'Priorität',
    'due_date': 'Fällig am',
    'assignee_id': 'Verantwortlich',
    'entry_date': 'Datum',
    'work_performed': 'Ausgeführte Arbeiten',
    'issues': 'Probleme / Hinweise',
    'next_steps': 'Nächste Schritte',
    'weather': 'Wetter',
    'crew_count': 'Personen vor Ort',
    'start_at': 'Beginn',
    'end_at': 'Ende',
    'category': 'Dokumentart',
    'url': 'Link',
    'active': 'Aktiv',
  };
  String fieldValue(String key, Object? value) {
    if (value == null || value == '') return 'Nicht erfasst';
    if (key == 'assignee_id')
      return team.where((user) => user['id'] == value).firstOrNull?['email'] ??
          'Nicht mehr im aktuellen Projektteam';
    final labels = switch (key) {
      'phase' => workspacePhaseLabels,
      'deposit_status' => workspaceDepositLabels,
      'materials_status' => workspaceMaterialsLabels,
      'status' => {
        ...workspaceTaskStatusLabels,
        ...workspaceAppointmentStatusLabels,
      },
      'priority' => workspacePriorityLabels,
      'category' => workspaceLinkCategoryLabels,
      _ => <String, String>{},
    };
    return labels[value] ??
        (value is bool ? (value ? 'Ja' : 'Nein') : value.toString());
  }

  Widget surface(String title, List<Widget> children, {Widget? action}) =>
      OfficeSurface(
        padding: const EdgeInsets.all(22),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Expanded(
                  child: Text(
                    title,
                    style: Theme.of(context).textTheme.titleLarge,
                  ),
                ),
                if (action != null) action,
              ],
            ),
            const SizedBox(height: 16),
            ...children,
          ],
        ),
      );
  Widget listBody(List<Widget> children) => ListView(
    padding: const EdgeInsets.fromLTRB(20, 20, 20, 40),
    children: [
      if (loading) const LinearProgressIndicator(),
      if (error != null)
        Padding(
          padding: const EdgeInsets.only(bottom: 16),
          child: Notice(error!),
        ),
      if (success != null)
        Padding(
          padding: const EdgeInsets.only(bottom: 16),
          child: Notice(success!, error: false),
        ),
      if (cachedWorkspace &&
          dashboard != null &&
          (dashboard!['has_pending_changes'] == true ||
              dashboard!['workspace_sync_status'] != null))
        Padding(
          padding: const EdgeInsets.only(bottom: 16),
          child: Notice(
            dashboard!['workspace_sync_status']?.toString() ?? 'Änderungen sind auf diesem Gerät gespeichert und warten auf Verbindung.',
            error:
                dashboard!['workspace_sync_status']?.toString() == 'Konflikt',
          ),
        ),
      ...children,
    ],
  );
  Widget empty(String message) => Padding(
    padding: const EdgeInsets.symmetric(vertical: 12),
    child: Text(message),
  );

  Widget projectDetails({required bool compact}) {
    final content = <Widget>[
      if ((profile['description'] as String? ?? '').isNotEmpty)
        Text(profile['description']),
      const SizedBox(height: 8),
      Text(
        (profile['site_address'] as String? ?? '').isNotEmpty
            ? profile['site_address']
            : 'Baustellenadresse noch nicht erfasst.',
      ),
      const SizedBox(height: 16),
      Wrap(
        spacing: 8,
        runSpacing: 8,
        children: [
          if (!compact)
            StatusPill('Phase: ${fieldValue('phase', profile['phase'])}'),
          StatusPill(
            'Anzahlung: ${fieldValue('deposit_status', profile['deposit_status'])}',
          ),
          StatusPill(
            'Material: ${fieldValue('materials_status', profile['materials_status'])}',
          ),
        ],
      ),
      if (profile['sync_status'] == 'Konflikt' && canProfile)
        TextButton(
          onPressed: () => resolveLocal('profile', profile),
          child: const Text('Profilkonflikt klären'),
        ),
      if (profile['start_date'] != null || profile['end_date'] != null)
        Padding(
          padding: const EdgeInsets.only(top: 12),
          child: Text(
            'Geplant: ${workspaceDate(profile['start_date'])} bis ${workspaceDate(profile['end_date'])}',
          ),
        ),
      if (compact && canProfile)
        Padding(
          padding: const EdgeInsets.only(top: 12),
          child: OutlinedButton.icon(
            onPressed: loading ? null : () => edit('profile'),
            icon: const Icon(Icons.edit_outlined),
            label: const Text('Projektdaten bearbeiten'),
          ),
        ),
    ];
    if (!compact) return surface('Projekt und Baustelle', content);
    return OfficeSurface(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 4),
      child: ExpansionTile(
        key: const PageStorageKey('project-mobile-details'),
        tilePadding: EdgeInsets.zero,
        childrenPadding: const EdgeInsets.fromLTRB(0, 8, 0, 12),
        shape: const Border(),
        collapsedShape: const Border(),
        title: const Text(
          'Projekt und Baustelle',
          style: TextStyle(fontSize: 15, fontWeight: FontWeight.w600),
        ),
        subtitle: Text(
          'Phase: ${fieldValue('phase', profile['phase'])}${profile['sync_status'] == 'Konflikt' ? ' · Konflikt' : ''}',
          style: const TextStyle(fontSize: 12),
        ),
        children: [
          Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: content,
          ),
        ],
      ),
    );
  }

  Widget overviewMetrics(Map counters, {required bool compact}) {
    const metrics = [
      ('tasks_open', 'Offene Aufgaben'),
      ('tasks_overdue', 'Überfällige Aufgaben'),
      ('appointments_upcoming', 'Nächste Termine'),
    ];
    Widget tile((String, String) metric) {
      final index = metrics.indexOf(metric);
      final overdue = index == 1 && (counters[metric.$1] as int? ?? 0) > 0;
      final color = overdue
          ? Theme.of(context).colorScheme.error
          : OfficeColors.blue;
      return OfficeSurface(
        key: ValueKey('workspace-metric-${metric.$1}'),
        padding: EdgeInsets.all(compact ? 12 : 20),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            if (!compact) ...[
              Icon(
                [
                  Icons.check_circle_outline,
                  Icons.schedule_outlined,
                  Icons.calendar_today_outlined,
                ][index],
                color: color,
                size: 22,
              ),
              const SizedBox(height: 14),
            ],
            Text(
              '${counters[metric.$1] ?? 0}',
              style: compact
                  ? TextStyle(
                      fontSize: 26,
                      fontWeight: FontWeight.w600,
                      height: 1.15,
                      color: overdue ? color : OfficeColors.ink,
                    )
                  : Theme.of(context).textTheme.headlineMedium,
            ),
            if (compact) const SizedBox(height: 5),
            Text(
              compact ? metric.$2.replaceFirst(' ', '\n') : metric.$2,
              maxLines: compact ? 2 : null,
              overflow: compact ? TextOverflow.ellipsis : null,
              style: compact
                  ? const TextStyle(fontSize: 11.5, height: 1.25)
                  : null,
            ),
          ],
        ),
      );
    }

    return IntrinsicHeight(
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          for (var i = 0; i < metrics.length; i++) ...[
            if (i > 0) SizedBox(width: compact ? 8 : 16),
            Expanded(child: tile(metrics[i])),
          ],
        ],
      ),
    );
  }

  Widget primaryActions({required bool compact}) {
    if (compact)
      return IntrinsicHeight(
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            for (final action in [
              ('tasks', 'Aufgabe anlegen'),
              ('diary', 'Tagesbericht erfassen'),
              ('appointments', 'Termin planen'),
            ]) ...[
              if (action.$1 != 'tasks') const SizedBox(width: 8),
              Expanded(
                child: action.$1 == 'tasks'
                    ? FilledButton(
                        onPressed: loading ? null : () => edit(action.$1),
                        style: FilledButton.styleFrom(
                          padding: const EdgeInsets.symmetric(
                            horizontal: 8,
                            vertical: 13,
                          ),
                        ),
                        child: Text(
                          action.$2,
                          textAlign: TextAlign.center,
                          style: const TextStyle(fontSize: 12),
                        ),
                      )
                    : OutlinedButton(
                        onPressed: loading ? null : () => edit(action.$1),
                        style: OutlinedButton.styleFrom(
                          padding: const EdgeInsets.symmetric(
                            horizontal: 8,
                            vertical: 13,
                          ),
                        ),
                        child: Text(
                          action.$2,
                          textAlign: TextAlign.center,
                          style: const TextStyle(fontSize: 12),
                        ),
                      ),
              ),
            ],
          ],
        ),
      );
    return Wrap(
      spacing: 10,
      runSpacing: 10,
      children: [
        FilledButton.icon(
          onPressed: loading ? null : () => edit('tasks'),
          icon: const Icon(Icons.add_task),
          label: const Text('Aufgabe anlegen'),
        ),
        OutlinedButton.icon(
          onPressed: loading ? null : () => edit('diary'),
          icon: const Icon(Icons.edit_note),
          label: const Text('Tagesbericht erfassen'),
        ),
        OutlinedButton.icon(
          onPressed: loading ? null : () => edit('appointments'),
          icon: const Icon(Icons.event_outlined),
          label: const Text('Termin planen'),
        ),
      ],
    );
  }

  Widget overview() {
    final compact = MediaQuery.sizeOf(context).width < 600;
    final counters = dashboard?['counters'] as Map? ?? {};
    final tasks = rows(dashboard?['open_tasks']);
    final appointments = rows(dashboard?['upcoming_appointments']);
    final diary = rows(dashboard?['latest_diary']);
    Widget taskPanel() => surface(
      'Offene Aufgaben',
      [
        if (tasks.isEmpty)
          empty('Aktuell sind keine offenen Aufgaben erfasst.'),
        for (final task in tasks.take(5)) taskTile(task),
      ],
      action: TextButton(
        onPressed: () => selectSection(1),
        child: const Text('Alle Aufgaben'),
      ),
    );
    Widget appointmentPanel() => surface(
      'Nächste Termine',
      [
        if (appointments.isEmpty) empty('Keine anstehenden Termine erfasst.'),
        for (final appointment in appointments.take(3))
          appointmentTile(appointment, compact: true),
      ],
      action: TextButton(
        onPressed: () => selectSection(2),
        child: const Text('Alle Termine'),
      ),
    );
    return listBody([
      if (compact)
        Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Eyebrow('Projektmappe'),
            const SizedBox(height: 10),
            Text(
              project['name'] ?? 'Projekt',
              style: const TextStyle(
                fontSize: 28,
                fontWeight: FontWeight.w600,
                height: 1.15,
                letterSpacing: -.7,
              ),
            ),
            const SizedBox(height: 8),
            Text(
              project['customer'] ?? '',
              style: const TextStyle(color: OfficeColors.muted),
            ),
          ],
        )
      else
        PageHeading(
          eyebrow: 'Projektmappe',
          title: project['name'] ?? 'Projekt',
          subtitle: project['customer'] ?? '',
          action: enabled && canProfile
              ? OutlinedButton.icon(
                  onPressed: loading ? null : () => edit('profile'),
                  icon: const Icon(Icons.edit_outlined),
                  label: const Text('Projektdaten bearbeiten'),
                )
              : null,
        ),
      SizedBox(height: compact ? 16 : 20),
      if (enabled) ...[
        if (compact) ...[
          projectDetails(compact: true),
          const SizedBox(height: 12),
        ],
        overviewMetrics(counters, compact: compact),
        SizedBox(height: compact ? 14 : 20),
        if (canWrite) primaryActions(compact: compact),
        SizedBox(height: compact ? 16 : 20),
        LayoutBuilder(
          builder: (context, constraints) => constraints.maxWidth < 900
              ? Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    taskPanel(),
                    const SizedBox(height: 16),
                    appointmentPanel(),
                  ],
                )
              : Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Expanded(flex: 3, child: taskPanel()),
                    const SizedBox(width: 20),
                    Expanded(flex: 2, child: appointmentPanel()),
                  ],
                ),
        ),
        const SizedBox(height: 16),
        if (!compact) ...[
          projectDetails(compact: false),
          const SizedBox(height: 16),
        ],
        surface(
          'Zuletzt im Bautagebuch',
          [
            if (diary.isEmpty) empty('Noch kein Tagesbericht erfasst.'),
            if (diary.isNotEmpty) diaryTile(diary.first),
          ],
          action: TextButton(
            onPressed: () => selectSection(3),
            child: const Text('Bautagebuch öffnen'),
          ),
        ),
        const SizedBox(height: 16),
        surface('Projektteam', [
          for (final member in team)
            ListTile(
              contentPadding: EdgeInsets.zero,
              leading: const Icon(Icons.person_outline),
              title: Text(member['email']),
              subtitle: Text(roleLabels[member['role']] ?? member['role']),
            ),
          if (team.isEmpty)
            empty('Keine Teamkontakte für dieses Projekt verfügbar.'),
        ]),
      ] else if (!loading)
        Wrap(
          spacing: 12,
          children: [
            OutlinedButton(
              onPressed: () => selectSection(4),
              child: const Text('Pläne öffnen'),
            ),
            OutlinedButton(
              onPressed: () => selectSection(6),
              child: const Text('Berichte öffnen'),
            ),
          ],
        ),
    ]);
  }

  Widget taskTile(Map<String, dynamic> task) {
    final overdue =
        task['due_date'] != null &&
        ['todo', 'in_progress'].contains(task['status']) &&
        task['due_date'].toString().compareTo(
              DateTime.now().toIso8601String().substring(0, 10),
            ) <
            0;
    return ListTile(
      contentPadding: EdgeInsets.zero,
      isThreeLine: true,
      leading: Icon(
        task['status'] == 'done'
            ? Icons.task_alt
            : Icons.radio_button_unchecked,
        color: overdue ? Theme.of(context).colorScheme.error : null,
      ),
      title: Text(task['title']),
      subtitle: Text(
        '${fieldValue('status', task['status'])} · ${fieldValue('assignee_id', task['assignee_id'])}\n${overdue ? 'Überfällig: ' : 'Fällig: '}${workspaceDate(task['due_date'])}${task['sync_status'] == null ? '' : '\n${task['sync_status']}'}',
      ),
      onTap: canWrite
          ? () => task['sync_status'] == 'Konflikt'
                ? resolveLocal('tasks', task)
                : edit('tasks', task)
          : null,
      trailing: canWrite && ['todo', 'in_progress'].contains(task['status'])
          ? IconButton(
              tooltip: 'Als erledigt markieren',
              onPressed: working.contains(task['id'])
                  ? null
                  : () => completeTask(task),
              icon: const Icon(Icons.check),
            )
          : null,
    );
  }

  Widget diaryTile(Map<String, dynamic> entry) => Padding(
    padding: const EdgeInsets.only(bottom: 12),
    child: Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            Expanded(
              child: Text(
                workspaceDate(entry['entry_date']),
                style: Theme.of(context).textTheme.titleMedium,
              ),
            ),
            if (canWrite)
              TextButton(
                onPressed: () => entry['sync_status'] == 'Konflikt'
                    ? resolveLocal('diary', entry)
                    : edit('diary', entry),
                child: Text(
                  entry['sync_status'] == 'Konflikt'
                      ? 'Konflikt klären'
                      : 'Bearbeiten',
                ),
              ),
          ],
        ),
        Text(entry['work_performed'] ?? ''),
        if (entry['sync_status'] != null) Text(entry['sync_status']),
        if ((entry['issues'] as String? ?? '').isNotEmpty)
          Padding(
            padding: const EdgeInsets.only(top: 8),
            child: Text('Probleme / Hinweise: ${entry['issues']}'),
          ),
        if ((entry['next_steps'] as String? ?? '').isNotEmpty)
          Padding(
            padding: const EdgeInsets.only(top: 8),
            child: Text('Nächste Schritte: ${entry['next_steps']}'),
          ),
        if (entry['crew_count'] != null ||
            (entry['weather'] as String? ?? '').isNotEmpty)
          Text(
            '${entry['crew_count'] == null ? '' : '${entry['crew_count']} Personen vor Ort'}${(entry['weather'] as String? ?? '').isEmpty ? '' : ' · ${entry['weather']}'}',
          ),
      ],
    ),
  );
  Widget appointmentTile(
    Map<String, dynamic> item, {
    bool compact = false,
  }) => Padding(
    padding: const EdgeInsets.only(bottom: 16),
    child: Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(item['title'], style: Theme.of(context).textTheme.titleMedium),
        Text(
          '${workspaceDate(item['start_at'], time: true)} bis ${workspaceDate(item['end_at'], time: true)}',
        ),
        if (item['status'] == 'cancelled') const Text('Abgesagt'),
        if (item['sync_status'] != null) Text(item['sync_status']),
        if (!compact) ...[
          if ((item['details'] as String? ?? '').isNotEmpty)
            Text(item['details']),
          Wrap(
            spacing: 8,
            children: [
              if (canWrite)
                TextButton(
                  onPressed: () => item['sync_status'] == 'Konflikt'
                      ? resolveLocal('appointments', item)
                      : edit('appointments', item),
                  child: Text(
                    item['sync_status'] == 'Konflikt'
                        ? 'Konflikt klären'
                        : 'Bearbeiten',
                  ),
                ),
              OutlinedButton.icon(
                onPressed:
                    exporting ||
                        widget.offlineMode ||
                        (cachedWorkspace &&
                            (item['server_id'] == null ||
                                item['sync_status'] != 'Synchronisiert'))
                    ? null
                    : () => exportCalendar(item),
                icon: const Icon(Icons.download_outlined),
                label: const Text('Kalenderdatei speichern'),
              ),
              TextButton(
                onPressed: () => openLink(
                  googleCalendarDraft(item, profile['site_address'] ?? ''),
                ),
                child: const Text('In Google Kalender öffnen'),
              ),
            ],
          ),
        ],
      ],
    ),
  );

  Widget itemSection(String kind) {
    final entries = lists[kind];
    final label = switch (kind) {
      'tasks' => 'Aufgabe anlegen',
      'appointments' => 'Termin planen',
      'diary' => 'Tagesbericht erfassen',
      _ => 'Dokumentlink hinzufügen',
    };
    return listBody([
      PageHeading(
        eyebrow: project['name'] ?? 'Projekt',
        title: projectSections[section],
        subtitle: switch (kind) {
          'tasks' => 'Verantwortung, Fälligkeiten und Arbeitsstand.',
          'appointments' =>
            'Termine im Projekt und bei Bedarf im eigenen Kalender.',
          'diary' => 'Arbeiten, Hinweise und nächste Schritte je Tag.',
          _ => 'Projektunterlagen und Verweise an einem Ort.',
        },
        action: enabled && canWrite
            ? FilledButton.icon(
                onPressed: loading ? null : () => edit(kind),
                icon: const Icon(Icons.add),
                label: Text(label),
              )
            : null,
      ),
      const SizedBox(height: 20),
      if (kind == 'links' && visited.contains(5))
        MailAttachmentsCard(
          key: ValueKey('project-mail-attachments-${widget.project['id']}'),
          api: widget.api,
          projectId: widget.project['id'],
          offlineMode: widget.offlineMode,
          canDelete: widget.role == 'owner',
          canImportPlan: canWrite && widget.api.version == 'v1',
          accessAllowed: accessAllowed,
          onAccessDenied: denyAccess,
          onPlans: openImportedPlans,
        ),
      if (!enabled)
        empty(
          'Dieser Bereich benötigt die erweiterte Projektmappe und eine Verbindung. Pläne und Berichte bleiben über die Register erreichbar.',
        )
      else if (entries == null)
        const LinearProgressIndicator()
      else if (entries.isEmpty)
        empty(switch (kind) {
          'tasks' => 'Noch keine Aufgaben erfasst.',
          'appointments' => 'Noch keine Termine erfasst.',
          'diary' => 'Noch keine Tagesberichte erfasst.',
          _ => 'Noch keine Dokumentlinks hinterlegt.',
        })
      else
        surface(projectSections[section], [
          for (final entry in entries)
            switch (kind) {
              'tasks' => taskTile(entry),
              'appointments' => appointmentTile(entry),
              'diary' => diaryTile(entry),
              _ => Padding(
                padding: const EdgeInsets.only(bottom: 16),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      entry['title'],
                      style: Theme.of(context).textTheme.titleMedium,
                    ),
                    Text(
                      '${fieldValue('category', entry['category'])}${entry['active'] == true ? '' : ' · Archiviert'}',
                    ),
                    if (entry['sync_status'] != null)
                      Text(entry['sync_status']),
                    SelectableText(entry['url']),
                    Wrap(
                      spacing: 8,
                      children: [
                        if (entry['active'] == true)
                          TextButton.icon(
                            onPressed: () => openLink(Uri.parse(entry['url'])),
                            icon: const Icon(Icons.open_in_new),
                            label: const Text('Link öffnen'),
                          ),
                        if (canWrite)
                          TextButton(
                            onPressed: () => entry['sync_status'] == 'Konflikt'
                                ? resolveLocal('links', entry)
                                : edit('links', entry),
                            child: Text(
                              entry['sync_status'] == 'Konflikt'
                                  ? 'Konflikt klären'
                                  : 'Bearbeiten',
                            ),
                          ),
                      ],
                    ),
                  ],
                ),
              ),
            },
        ]),
      if (kind == 'appointments')
        const Padding(
          padding: EdgeInsets.only(top: 16),
          child: Text(
            'Google öffnet erst nach Ihrem Klick einen Terminentwurf. Speichern Sie ihn dort selbst; es gibt keinen automatischen Kalenderabgleich.',
          ),
        ),
      if (kind == 'links')
        const Padding(
          padding: EdgeInsets.only(top: 16),
          child: Text(
            'Links öffnen die jeweilige Website. Dropbox, sevdesk und Vertragsablagen sind hier nicht automatisch verbunden.',
          ),
        ),
    ]);
  }

  Widget nested(
    GlobalKey<NavigatorState> key,
    Widget Function(Map<String, dynamic>) builder,
  ) => NavigatorPopHandler<Object?>(
    enabled:
        (section == 4 && key == plansNavigator) ||
        (section == 6 && key == reportsNavigator),
    onPopWithResult: (result) => key.currentState?.pop(result),
    child: Navigator(
      key: key,
      onGenerateRoute: (_) => MaterialPageRoute<void>(
        builder: (_) => ValueListenableBuilder<Map<String, dynamic>>(
          valueListenable: projectChanges,
          builder: (context, current, _) => builder(current),
        ),
      ),
    ),
  );

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(
      title: Text(
        denied ? 'Projektmappe' : project['name'] ?? 'Projektmappe',
        maxLines: 1,
        overflow: TextOverflow.ellipsis,
      ),
      actions: [
        IconButton(
          tooltip: 'Projekt aktualisieren',
          onPressed: refreshing || denied ? null : reload,
          icon: const Icon(Icons.refresh),
        ),
        if (widget.role == 'owner' && !denied && !widget.offlineMode) ...[
          IconButton(
            tooltip: 'Kunden zuordnen',
            onPressed: loading ? null : changeCustomer,
            icon: const Icon(Icons.contacts_outlined),
          ),
          IconButton(
            tooltip: 'Projektzugriff verwalten',
            onPressed: () async {
              await Navigator.push<void>(
                context,
                MaterialPageRoute(
                  builder: (_) =>
                      AssignmentsPage(api: widget.api, project: project),
                ),
              );
              if (mounted) await reload();
            },
            icon: const Icon(Icons.group_outlined),
          ),
        ],
      ],
    ),
    body: denied
        ? Center(
            child: Padding(
              padding: const EdgeInsets.all(24),
              child: Text(error ?? 'Projektzugriff ist nicht verfügbar.'),
            ),
          )
        : Column(
            children: [
              LayoutBuilder(
                builder: (context, constraints) => constraints.maxWidth < 1000
                    ? Padding(
                        padding: const EdgeInsets.fromLTRB(20, 4, 20, 12),
                        child: DropdownButtonFormField<int>(
                          key: ValueKey('project-section-picker-$section'),
                          initialValue: section,
                          decoration: InputDecoration(
                            labelText: 'Projektbereich',
                            prefixIcon: Icon(_sectionIcons[section], size: 20),
                          ),
                          items: [
                            for (
                              var index = 0;
                              index < projectSections.length;
                              index++
                            )
                              DropdownMenuItem(
                                value: index,
                                child: Text(projectSections[index]),
                              ),
                          ],
                          onChanged: (value) {
                            if (value != null) selectSection(value);
                          },
                        ),
                      )
                    : SingleChildScrollView(
                        scrollDirection: Axis.horizontal,
                        child: Container(
                          margin: const EdgeInsets.fromLTRB(24, 0, 24, 16),
                          padding: const EdgeInsets.all(5),
                          decoration: BoxDecoration(
                            color: const Color(0xffeaeaec),
                            borderRadius: BorderRadius.circular(14),
                          ),
                          child: Row(
                            children: [
                              for (
                                var index = 0;
                                index < projectSections.length;
                                index++
                              )
                                Padding(
                                  padding: const EdgeInsets.only(right: 8),
                                  child: TextButton.icon(
                                    style: TextButton.styleFrom(
                                      backgroundColor: section == index
                                          ? Colors.white
                                          : null,
                                      foregroundColor: section == index
                                          ? OfficeColors.blue
                                          : OfficeColors.muted,
                                      padding: const EdgeInsets.symmetric(
                                        horizontal: 14,
                                        vertical: 12,
                                      ),
                                    ),
                                    onPressed: () => selectSection(index),
                                    icon: Icon(_sectionIcons[index], size: 18),
                                    label: Text(projectSections[index]),
                                  ),
                                ),
                            ],
                          ),
                        ),
                      ),
              ),
              const Divider(height: 1),
              Expanded(
                child: IndexedStack(
                  index: section,
                  children:
                      <Widget>[
                            overview(),
                            for (final kind in [
                              'tasks',
                              'appointments',
                              'diary',
                            ])
                              itemSection(kind),
                            visited.contains(4)
                                ? nested(
                                    plansNavigator,
                                    (current) => PlansPage(
                                      api: widget.api,
                                      project: current,
                                      canWrite: canWrite,
                                      repository: widget.repository,
                                    ),
                                  )
                                : const SizedBox(),
                            itemSection('links'),
                            widget.offlineMode
                                ? const Center(
                                    child: Padding(
                                      padding: EdgeInsets.all(24),
                                      child: Text(
                                        'Berichte und Unterschriften benötigen eine Online-Anmeldung. Aufgaben, Termine, Bautagebuch und gespeicherte Pläne bleiben in der Projektmappe verfügbar.',
                                      ),
                                    ),
                                  )
                                : visited.contains(6)
                                ? nested(
                                    reportsNavigator,
                                    widget.reportsBuilder,
                                  )
                                : const SizedBox(),
                          ]
                          .asMap()
                          .entries
                          .map(
                            (entry) => TickerMode(
                              enabled: entry.key == section,
                              child: entry.value,
                            ),
                          )
                          .toList(),
                ),
              ),
            ],
          ),
  );
}

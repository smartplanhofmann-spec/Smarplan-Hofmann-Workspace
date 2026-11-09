import 'dart:async';

import 'package:flutter/material.dart';

import 'api.dart';
import 'business_project_milestone_contract.dart';
import 'business_session.dart';
import 'business_widgets.dart';
import 'design.dart';

/// Meilensteine belong to the currently authorized online project only.
class BusinessProjectMilestonesPage extends StatefulWidget {
  const BusinessProjectMilestonesPage({
    super.key,
    required this.session,
    this.active = true,
  });

  final BusinessSession session;
  final bool active;

  @override
  State<BusinessProjectMilestonesPage> createState() =>
      _BusinessProjectMilestonesPageState();
}

class _BusinessProjectMilestonesPageState
    extends State<BusinessProjectMilestonesPage> {
  List<Map<String, dynamic>> records = [], team = [];
  String? error;
  bool loading = false, opening = false, denied = false, invalidated = false;
  int epoch = 0;
  Object? generation;
  String? token, project;
  late String server, version;
  DialogRoute<bool>? modal;

  BusinessSession get session => widget.session;
  bool get sameContext =>
      mounted &&
      !invalidated &&
      widget.active &&
      project != null &&
      session.projectId == project &&
      session.api.token == token &&
      session.api.base == server &&
      session.api.version == version;
  bool get readable =>
      sameContext &&
      !denied &&
      session.allowed &&
      session.hasModule('project_milestones') &&
      session.hasFeature('project_milestones') &&
      session.can('planning.read');
  bool get writable =>
      readable &&
      session.canWrite('projects.manage') &&
      session.sectionEnabled('planning');

  @override
  void initState() {
    super.initState();
    bind();
    session.addListener(changed);
    session.api.addListener(changed);
    unawaited(load());
  }

  void bind() {
    token = session.api.token;
    server = session.api.base;
    version = session.api.version;
    project = session.projectId;
    generation = session.generation;
    invalidated = denied = false;
  }

  void clear() {
    epoch++;
    records = [];
    team = [];
    error = null;
    loading = false;
    opening = false;
    final route = modal;
    modal = null;
    if (route?.isActive == true) {
      scheduleMicrotask(() {
        if (route?.isActive == true) route!.navigator?.removeRoute(route);
      });
    }
  }

  void changed() {
    if (!mounted) return;
    if (session.api.token != token ||
        session.api.base != server ||
        session.api.version != version ||
        session.projectId != project) {
      invalidated = true;
    }
    if (!readable || generation != session.generation) {
      clear();
      generation = session.generation;
    }
    setState(() {});
  }

  @override
  void didUpdateWidget(covariant BusinessProjectMilestonesPage oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (!identical(oldWidget.session, session)) {
      oldWidget.session.removeListener(changed);
      oldWidget.session.api.removeListener(changed);
      clear();
      bind();
      session.addListener(changed);
      session.api.addListener(changed);
      unawaited(load());
    } else if (oldWidget.active != widget.active) {
      clear();
      if (widget.active) unawaited(load());
    }
  }

  @override
  void dispose() {
    clear();
    session.removeListener(changed);
    session.api.removeListener(changed);
    super.dispose();
  }

  bool current(int stamp) =>
      stamp == epoch && readable && generation == session.generation;

  Future<bool> fresh(int stamp, {bool write = false}) async {
    if (!current(stamp)) return false;
    await session.load();
    if (!current(stamp)) return false;
    if (session.error != null)
      throw const ApiException(
        0,
        'Die aktuellen Projektberechtigungen konnten nicht geprüft werden.',
      );
    if (write && !writable)
      throw const ApiException(
        403,
        'Meilensteine können mit Ihren aktuellen Rechten nur gelesen werden.',
      );
    return true;
  }

  String get path => '/projects/$project/milestones';
  String commandKey(String? id) => 'project-milestone-$project-${id ?? 'new'}';

  Future<void> load() async {
    if (!readable || loading) return;
    final stamp = ++epoch;
    setState(() {
      loading = true;
      error = null;
    });
    try {
      if (!await fresh(stamp)) return;
      final values = await Future.wait([
        session.read(path),
        session.legacyRead('/api/projects/$project/workspace'),
      ]);
      if (!current(stamp)) return;
      final items = milestoneList(values[0], project!);
      final people = milestoneTeam(values[1], project!);
      setState(() {
        records = items;
        team = people;
      });
    } on ApiException catch (failure) {
      if (current(stamp)) {
        if ([401, 403, 404].contains(failure.status)) {
          records = [];
          team = [];
          denied = true;
        }
        setState(() => error = failure.message);
      }
    } catch (failure) {
      if (current(stamp)) setState(() => error = '$failure');
    } finally {
      if (mounted && stamp == epoch) setState(() => loading = false);
    }
  }

  String assigneeLabel(Object? id) {
    if (id == null) return 'Keine Zuordnung';
    for (final person in team) {
      if (person['id'] == id) return '${person['email']}';
    }
    return 'Nicht mehr im aktuellen Projektteam';
  }

  Future<void> push(DialogRoute<bool> route) async {
    modal = route;
    try {
      await Navigator.of(context).push(route);
    } finally {
      if (identical(modal, route)) modal = null;
    }
  }

  Future<void> edit([Map<String, dynamic>? selected]) async {
    if (!writable || loading || opening || modal != null) return;
    final stamp = epoch, id = selected?['id'] as String?;
    final editingSession = session, editingProject = project!;
    final endpoint = '$path${id == null ? '' : '/$id'}';
    final key = commandKey(id);
    setState(() => opening = true);
    try {
      if (!await fresh(stamp, write: true)) return;
      final people = milestoneTeam(
        await session.legacyRead('/api/projects/$project/workspace'),
        editingProject,
      );
      if (!current(stamp) || !writable) return;
      final source = id == null
          ? null
          : milestoneRecord(
              await session.read(endpoint),
              editingProject,
              id: id,
            );
      if (!current(stamp) || !writable) return;
      final pending = session.pendingCommandValues(key, path: endpoint);
      String? originalRequest = session.pendingProjectMilestoneRequest(
        editingProject,
        id,
      );
      if (pending != null && session.pendingEditorValues(key) == null) {
        session.preservePendingEditor(key, {
          for (final field in milestoneFields) field: pending[field],
          'assignee_id': pending['assignee_id'] ?? '',
        });
      }
      team = people;
      final initial =
          pending ??
          source ??
          <String, dynamic>{
            'title': '',
            'details': '',
            'due_date': null,
            'assignee_id': null,
            'status': 'planned',
          };
      final assignee = initial['assignee_id'] as String?;
      final choices = <String, String>{
        for (final person in people) person['id']: person['email'],
        if (assignee != null && !people.any((p) => p['id'] == assignee))
          assignee: 'Nicht mehr im aktuellen Projektteam',
      };
      final route = DialogRoute<bool>(
        context: context,
        builder: (_) => BusinessEditor(
          session: editingSession,
          title: id == null ? 'Meilenstein anlegen' : 'Meilenstein bearbeiten',
          pendingKey: key,
          readPermission: 'planning.read',
          writePermission: 'projects.manage',
          readAllowed: () =>
              current(stamp) && identical(session, editingSession),
          initial: {...initial, 'assignee_id': assignee ?? ''},
          fields: [
            const BusinessField(
              'title',
              'Titel',
              required: true,
              trimInput: false,
            ),
            const BusinessField(
              'details',
              'Beschreibung',
              type: BusinessInput.multiline,
              trimInput: false,
            ),
            const BusinessField(
              'due_date',
              'Fällig am',
              type: BusinessInput.date,
            ),
            BusinessField(
              'assignee_id',
              'Verantwortlich (aktuelles Projektteam)',
              type: BusinessInput.choice,
              choices: choices,
            ),
            BusinessField(
              'status',
              'Status',
              required: true,
              type: BusinessInput.choice,
              choices: milestoneStatuses,
            ),
          ],
          onSave: (values) async {
            originalRequest ??= editingSession.pendingProjectMilestoneRequest(
              editingProject,
              id,
            );
            if (!current(stamp) || !identical(session, editingSession))
              throw const ApiException(
                403,
                'Der Projektkontext wurde geschlossen.',
              );
            if (!await fresh(stamp, write: true))
              throw const ApiException(
                403,
                'Der Projektkontext wurde geschlossen.',
              );
            final actor = await editingSession.legacyRead('/api/me');
            if (!current(stamp) || !identical(session, editingSession))
              throw const ApiException(
                403,
                'Der Projektkontext wurde geschlossen.',
              );
            if (actor is! Map ||
                actor['id'] is! String ||
                !RegExp(r'^[a-f0-9]{32}$').hasMatch(actor['id']))
              throw const ApiException(
                0,
                'Die angemeldete Person konnte nicht bestätigt werden.',
              );
            final body = milestoneBody(
              {
                ...values,
                'assignee_id': values['assignee_id'] == ''
                    ? null
                    : values['assignee_id'],
              },
              revision: id == null
                  ? null
                  : (pending?['revision'] ?? source!['revision']) as int,
            );
            try {
              await editingSession.projectMilestoneCommand(
                editingProject,
                id,
                body,
                expectedRequestId: originalRequest,
                validateResult: (result) => milestoneReceiptValidator(
                  editingProject,
                  body,
                  previous: source,
                  expectedActor: actor['id'],
                )(result),
              );
            } on BusinessCommandException catch (failure) {
              originalRequest ??= failure.requestId;
              rethrow;
            }
          },
        ),
      );
      if (!current(stamp) || !writable) return;
      setState(() => opening = false);
      await push(route);
      if (current(stamp)) await load();
    } on ApiException catch (failure) {
      if (current(stamp)) setState(() => error = failure.message);
    } catch (failure) {
      if (current(stamp)) setState(() => error = '$failure');
    } finally {
      if (mounted && stamp == epoch) setState(() => opening = false);
    }
  }

  Future<void> history(Map<String, dynamic> selected) async {
    if (!readable || loading || opening || modal != null) return;
    final stamp = epoch, id = selected['id'] as String;
    setState(() => opening = true);
    try {
      if (!await fresh(stamp)) return;
      final values = await Future.wait([
        session.read('$path/$id/history'),
        session.legacyRead('/api/projects/$project/workspace'),
      ]);
      if (!current(stamp)) return;
      final versions = milestoneHistory(
        values[0],
        project!,
        id,
        anchor: selected,
      );
      team = milestoneTeam(values[1], project!);
      if (!current(stamp)) return;
      setState(() => opening = false);
      await push(
        DialogRoute<bool>(
          context: context,
          builder: (dialog) => AlertDialog(
            title: const Text('Meilenstein: Änderungshistorie'),
            content: SizedBox(
              width: 580,
              height: 460,
              child: ListView(
                children: [
                  const Text(
                    'Jede Änderung bleibt als eigene Fassung erhalten. Teambezeichnungen beziehen sich auf die aktuelle Zuordnung.',
                  ),
                  const SizedBox(height: 12),
                  for (final value in versions.reversed)
                    ExpansionTile(
                      initiallyExpanded:
                          value['revision'] == versions.last['revision'],
                      title: Text(
                        'Revision ${value['revision']} · ${milestoneStatuses[value['status']]}',
                      ),
                      subtitle: Text(
                        businessDate(value['updated_at'], time: true),
                      ),
                      children: [
                        ListTile(
                          title: Text(value['title']),
                          subtitle: Text(value['details']),
                        ),
                        ListTile(
                          title: Text(
                            'Fällig: ${value['due_date'] == null ? 'Ohne Termin' : businessDate(value['due_date'])}',
                          ),
                          subtitle: Text(
                            'Verantwortlich heute: ${assigneeLabel(value['assignee_id'])}',
                          ),
                        ),
                        if (value['assignee_id'] != null)
                          SelectableText(
                            'Verantwortlichenkennung im Original: ${value['assignee_id']}',
                          ),
                        SelectableText(
                          'Originalhash: ${value['content_hash']}',
                        ),
                        const SizedBox(height: 12),
                      ],
                    ),
                ],
              ),
            ),
            actions: [
              TextButton(
                onPressed: () => Navigator.pop(dialog),
                child: const Text('Schließen'),
              ),
            ],
          ),
        ),
      );
    } on ApiException catch (failure) {
      if (current(stamp)) setState(() => error = failure.message);
    } catch (failure) {
      if (current(stamp)) setState(() => error = '$failure');
    } finally {
      if (mounted && stamp == epoch) setState(() => opening = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    if (!readable)
      return const Center(
        child: Text(
          'Meilensteine sind für diesen Projektkontext nicht verfügbar.',
        ),
      );
    return ListView(
      padding: const EdgeInsets.all(24),
      children: [
        Wrap(
          spacing: 12,
          runSpacing: 12,
          crossAxisAlignment: WrapCrossAlignment.center,
          children: [
            Text(
              'Meilensteine',
              style: Theme.of(context).textTheme.headlineMedium,
            ),
            OutlinedButton.icon(
              onPressed: loading || opening ? null : load,
              icon: const Icon(Icons.refresh),
              label: const Text('Aktualisieren'),
            ),
            if (writable)
              FilledButton.icon(
                onPressed: loading || opening ? null : () => edit(),
                icon: const Icon(Icons.add),
                label: Text(
                  session.pending(commandKey(null))
                      ? 'Anlage fortsetzen'
                      : 'Meilenstein anlegen',
                ),
              ),
          ],
        ),
        const SizedBox(height: 12),
        const Text(
          'Projektziele mit Termin und Verantwortlichem. Der Status wird manuell gepflegt; „Erreicht“ ersetzt keine fachliche Abnahme.',
        ),
        const SizedBox(height: 12),
        if (loading || opening) const LinearProgressIndicator(),
        if (error != null) Notice(error!, error: true),
        if (!loading && records.isEmpty && error == null)
          const BusinessEmpty(
            'Noch keine Meilensteine',
            'Halten Sie wichtige Ziele und Zwischenergebnisse für dieses Projekt fest.',
          ),
        for (final value in records)
          Card(
            child: Padding(
              padding: const EdgeInsets.all(12),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    value['title'],
                    style: Theme.of(context).textTheme.titleMedium,
                  ),
                  const SizedBox(height: 6),
                  Text(
                    '${milestoneStatuses[value['status']]} · ${value['due_date'] == null ? 'Ohne Termin' : 'Fällig: ${businessDate(value['due_date'])}'}',
                  ),
                  Text(
                    'Verantwortlich: ${assigneeLabel(value['assignee_id'])}',
                  ),
                  if ((value['details'] as String).isNotEmpty)
                    Text(value['details']),
                  Wrap(
                    spacing: 8,
                    children: [
                      TextButton.icon(
                        onPressed: loading || opening
                            ? null
                            : () => history(value),
                        icon: const Icon(Icons.history),
                        label: Text(
                          'Änderungshistorie · Revision ${value['revision']}',
                        ),
                      ),
                      if (writable)
                        TextButton.icon(
                          onPressed: loading || opening
                              ? null
                              : () => edit(value),
                          icon: const Icon(Icons.edit_outlined),
                          label: Text(
                            session.pending(commandKey(value['id']))
                                ? 'Änderung fortsetzen'
                                : 'Bearbeiten',
                          ),
                        ),
                    ],
                  ),
                ],
              ),
            ),
          ),
      ],
    );
  }
}

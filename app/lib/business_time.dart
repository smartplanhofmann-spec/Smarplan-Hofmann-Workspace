import 'dart:async';

import 'package:flutter/material.dart';

import 'api.dart';
import 'business_session.dart';
import 'business_widgets.dart';
import 'design.dart';
import 'offline_plans.dart';
import 'offline_vault.dart' show offlineId;

class BusinessTimePage extends StatefulWidget {
  const BusinessTimePage({super.key, required this.session, this.repository});
  final BusinessSession session;
  final OfflinePlans? repository;
  @override
  State<BusinessTimePage> createState() => _BusinessTimePageState();
}

class _BusinessTimePageState extends State<BusinessTimePage> {
  List<Map<String, dynamic>> entries = [];
  String? error;
  bool busy = false;
  int epoch = 0;
  final device = offlineId();
  Timer? timer;
  ({String action, Map<String, dynamic> body})? retry;
  bool get local =>
      widget.repository?.timeEventsSupported == true &&
      (!widget.session.allowed || widget.session.can('time.own'));
  bool get allowed => local || widget.session.can('time.own');
  String? get project => widget.session.projectId;
  @override
  void initState() {
    super.initState();
    widget.session.addListener(changed);
    widget.repository?.addListener(changed);
    timer = Timer.periodic(const Duration(seconds: 1), (_) {
      if (mounted) setState(() {});
    });
    load();
  }

  void changed() {
    if (!mounted) return;
    if (!allowed) {
      epoch++;
      entries = [];
    } else if (local && project != null) {
      try {
        entries = widget.repository!.timeEntries(project!);
      } catch (_) {
        entries = [];
      }
    }
    setState(() {});
  }

  @override
  void dispose() {
    epoch++;
    timer?.cancel();
    widget.session.removeListener(changed);
    widget.repository?.removeListener(changed);
    super.dispose();
  }

  Future<void> load() async {
    if (project == null || !allowed) return;
    final current = ++epoch;
    if (local) {
      try {
        entries = widget.repository!.timeEntries(project!);
        setState(() {});
      } catch (e) {
        error = '$e';
      }
    }
    if (!widget.session.can('time.own')) return;
    try {
      final records = businessItems(
        await widget.session.read(widget.session.query('/time/entries')),
      );
      if (!mounted || current != epoch || !allowed) return;
      if (local) {
        await widget.repository!.cacheTimeEntries(project!, records);
        if (!mounted || current != epoch) return;
        entries = widget.repository!.timeEntries(project!);
      } else {
        entries = records;
      }
      setState(() => error = null);
    } catch (e) {
      if (mounted && current == epoch) setState(() => error = '$e');
    }
  }

  Future<void> act(String action, [Map<String, dynamic>? entry]) async {
    if (busy ||
        project == null ||
        !allowed ||
        (widget.session.readonly ||
            widget.repository?.businessReadOnly == true))
      return;
    setState(() {
      busy = true;
      error = null;
    });
    try {
      if (local) {
        await widget.repository!.saveTimeEvent(
          project!,
          action,
          entryId: entry?['id'],
        );
        entries = widget.repository!.timeEntries(project!);
      } else {
        final body =
            retry?.body ??
            {
              'entry_id': entry?['id'] ?? offlineId(),
              'device_id': device,
              'sequence':
                  (entry?['sequence'] as int? ??
                      entry?['last_sequence'] as int? ??
                      0) +
                  1,
              'revision': entry?['revision'] ?? 0,
              'project_id': project,
              'action': action,
              'occurred_at': DateTime.now().toUtc().toIso8601String(),
            };
        retry = (action: action, body: body);
        final response = businessMap(
          await widget.session.command(
            'clock-${body['entry_id']}-$action',
            '/time/events',
            body,
          ),
        );
        if (!mounted || !allowed) return;
        final result = businessMap(response['entry']);
        entries.removeWhere((r) => r['id'] == result['id']);
        entries.add(result);
        retry = null;
      }
      if (mounted) setState(() {});
    } on ApiException catch (e) {
      if (mounted)
        setState(() {
          error = e.message;
          if (e.status != 0 && e.status < 500 && e.status != 429) retry = null;
        });
    } catch (_) {
      if (mounted)
        setState(
          () => error =
              'Die Zeit konnte nicht gesichert werden. Bitte erneut versuchen.',
        );
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  String duration(Map<String, dynamic> entry) {
    final events =
        (entry['local_events'] as List? ?? entry['events'] as List? ?? [])
            .map(businessMap)
            .toList();
    var seconds = 0;
    for (var i = 0; i < events.length; i++) {
      if (!['start', 'resume'].contains(events[i]['action'])) continue;
      final begin = DateTime.tryParse('${events[i]['occurred_at']}');
      final end = i + 1 < events.length
          ? DateTime.tryParse('${events[i + 1]['occurred_at']}')
          : DateTime.now();
      if (begin != null && end != null && end.isAfter(begin))
        seconds += end.difference(begin).inSeconds;
    }
    if (events.isEmpty) seconds = entry['worked_seconds'] as int? ?? 0;
    return '${seconds ~/ 3600}:${'${seconds % 3600 ~/ 60}'.padLeft(2, '0')} Std.';
  }

  @override
  Widget build(BuildContext context) {
    if (!allowed)
      return const BusinessEmpty(
        'Stempeluhr nicht freigegeben',
        'Melden Sie sich mit Verbindung an. Bereits gesicherte Zeiten bleiben erhalten.',
        icon: Icons.lock_outline,
      );
    if (project == null)
      return const BusinessEmpty(
        'Projekt wählen',
        'Öffnen Sie die Stempeluhr in der zugehörigen Projektmappe.',
      );
    final active = entries
        .where((e) => ['working', 'paused'].contains(e['status']))
        .firstOrNull;
    return ListView(
      padding: const EdgeInsets.all(24),
      children: [
        Text('Arbeitszeit', style: Theme.of(context).textTheme.headlineMedium),
        const SizedBox(height: 8),
        Text(
          local
              ? 'Ihre Zeitaktionen werden zuerst verschlüsselt auf diesem Gerät gesichert und bei Verbindung synchronisiert.'
              : 'Für Offlinezeiten dieses Projekt einmal mit einer neuen Offline-Freigabe vorbereiten.',
        ),
        const SizedBox(height: 20),
        if (error != null) Notice(error!, error: true),
        Card(
          child: Padding(
            padding: const EdgeInsets.all(24),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  active == null
                      ? 'Bereit für den Arbeitstag'
                      : active['status'] == 'paused'
                      ? 'Pause'
                      : 'Arbeit läuft',
                  style: Theme.of(context).textTheme.titleLarge,
                ),
                if (active != null) ...[
                  const SizedBox(height: 12),
                  Text(
                    duration(active),
                    style: Theme.of(context).textTheme.headlineLarge,
                  ),
                  Text('${active['sync_status'] ?? 'Online bestätigt'}'),
                ],
                const SizedBox(height: 20),
                Wrap(
                  spacing: 12,
                  runSpacing: 12,
                  children: [
                    if (retry != null)
                      FilledButton(
                        onPressed:
                            busy ||
                                widget.session.readonly ||
                                widget.repository?.businessReadOnly == true
                            ? null
                            : () => act(retry!.action, active),
                        child: const Text('Dieselbe Zeitaktion erneut senden'),
                      )
                    else if (active == null)
                      FilledButton.icon(
                        onPressed:
                            busy ||
                                widget.session.readonly ||
                                widget.repository?.businessReadOnly == true
                            ? null
                            : () => act('start'),
                        icon: const Icon(Icons.play_arrow),
                        label: const Text('Arbeit beginnen'),
                      )
                    else ...[
                      OutlinedButton.icon(
                        onPressed:
                            busy ||
                                widget.session.readonly ||
                                widget.repository?.businessReadOnly == true
                            ? null
                            : () => act(
                                active['status'] == 'paused'
                                    ? 'resume'
                                    : 'pause',
                                active,
                              ),
                        icon: Icon(
                          active['status'] == 'paused'
                              ? Icons.play_arrow
                              : Icons.pause,
                        ),
                        label: Text(
                          active['status'] == 'paused'
                              ? 'Weiterarbeiten'
                              : 'Pause beginnen',
                        ),
                      ),
                      FilledButton.icon(
                        onPressed:
                            busy ||
                                widget.session.readonly ||
                                widget.repository?.businessReadOnly == true
                            ? null
                            : () => act('stop', active),
                        icon: const Icon(Icons.stop),
                        label: const Text('Arbeit beenden'),
                      ),
                    ],
                  ],
                ),
                if (busy) const LinearProgressIndicator(),
              ],
            ),
          ),
        ),
        const SizedBox(height: 20),
        Text('Erfasste Zeiten', style: Theme.of(context).textTheme.titleLarge),
        if (entries.isEmpty)
          const BusinessEmpty(
            'Noch keine Arbeitszeiten',
            'Starten Sie die Erfassung vor Beginn Ihrer Arbeit.',
          ),
        for (final entry in entries.reversed)
          Card(
            child: ListTile(
              leading: Icon(
                entry['sync_status'] == 'Konflikt'
                    ? Icons.warning_amber_rounded
                    : Icons.schedule,
              ),
              title: Text(
                '${businessDate(entry['started_at'] ?? entry['start_at'] ?? (entry['local_events'] as List?)?.firstOrNull?['occurred_at'], time: true)} · ${duration(entry)}',
              ),
              subtitle: Text(
                '${const {'working': 'Arbeit läuft', 'paused': 'Pause', 'stopped': 'Beendet', 'approved': 'Freigegeben', 'partially_approved': 'Teilweise freigegeben'}[entry['status']] ?? entry['status']} · ${entry['sync_status'] ?? 'Online bestätigt'}${entry['sync_error'] == null ? '' : '\n${entry['sync_error']}'}',
              ),
            ),
          ),
        const SizedBox(height: 16),
        const Text(
          'Standort wird nicht erfasst. Ein Freigeben des Arbeitstages erfolgt gesondert durch eine berechtigte Person.',
        ),
      ],
    );
  }
}

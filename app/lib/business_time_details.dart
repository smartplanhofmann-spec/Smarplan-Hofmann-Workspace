import 'package:flutter/material.dart';

import 'api.dart';
import 'business_session.dart';
import 'business_widgets.dart';
import 'design.dart';

String timeHours(int seconds) {
  final value = seconds.abs();
  final rest = value % 60;
  return '${seconds < 0 ? '-' : ''}${value ~/ 3600}:${'${value % 3600 ~/ 60}'.padLeft(2, '0')}${rest == 0 ? '' : ':${'$rest'.padLeft(2, '0')}'} Std.';
}

String timeProjectName(BusinessSession session, Map<String, dynamic> entry) =>
    session.projects
            .where((project) => project['id'] == entry['project_id'])
            .firstOrNull?['name']
        as String? ??
    'Zugeordnetes Projekt';

Future<void> showBusinessTimeDetails(
  BuildContext context,
  BusinessSession session,
  String entryId, {
  String readPermission = 'time.own',
}) => showDialog<void>(
  context: context,
  builder: (_) => _TimeDetails(
    session: session,
    entryId: entryId,
    readPermission: readPermission,
  ),
);

class _TimeDetails extends StatefulWidget {
  const _TimeDetails({
    required this.session,
    required this.entryId,
    required this.readPermission,
  });
  final BusinessSession session;
  final String entryId, readPermission;
  @override
  State<_TimeDetails> createState() => _TimeDetailsState();
}

class _TimeDetailsState extends State<_TimeDetails> {
  Map<String, dynamic>? entry;
  String? error;
  bool busy = false;
  int epoch = 0;
  bool get allowed => widget.session.can(widget.readPermission);
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
      entry = null;
      error = null;
    }
    setState(() {});
  }

  @override
  void dispose() {
    epoch++;
    widget.session.removeListener(changed);
    super.dispose();
  }

  Future<void> load() async {
    if (!allowed) return;
    final current = ++epoch;
    setState(() {
      busy = true;
      error = null;
    });
    try {
      final value = businessMap(
        await widget.session.read('/time/entries/${widget.entryId}'),
      );
      if (!mounted || current != epoch || !allowed) return;
      if (value['id'] != widget.entryId)
        throw const ApiException(
          0,
          'Der Zeitnachweis gehört nicht zum gewählten Eintrag.',
        );
      setState(() => entry = value);
    } catch (e) {
      if (mounted && current == epoch)
        setState(() {
          entry = null;
          error = '$e';
        });
    } finally {
      if (mounted && current == epoch) setState(() => busy = false);
    }
  }

  Future<void> correct() async {
    final value = entry;
    if (value == null ||
        busy ||
        !allowed ||
        !widget.session.canWrite('time.approve'))
      return;
    final dates = (value['approved_work_dates'] as List? ?? [])
        .whereType<String>()
        .toList();
    if (dates.isEmpty) return;
    final key = 'time-correction-${widget.entryId}';
    final saved = await showDialog<bool>(
      context: context,
      builder: (_) => BusinessEditor(
        session: widget.session,
        pendingKey: key,
        readPermission: widget.readPermission,
        writePermission: 'time.approve',
        title:
            'Freigegebene Zeit korrigieren · ${timeProjectName(widget.session, value)}',
        saveLabel: 'Begründete Korrektur speichern',
        fields: [
          BusinessField(
            'work_date',
            'Freigegebener Arbeitstag',
            type: BusinessInput.choice,
            required: true,
            initial: dates.length == 1 ? dates.single : null,
            choices: {for (final date in dates) date: businessDate(date)},
          ),
          const BusinessField(
            'minutes',
            'Änderung in Minuten',
            type: BusinessInput.integer,
            required: true,
            hint: 'Zum Beispiel -30 abziehen oder 15 ergänzen',
          ),
          const BusinessField(
            'reason',
            'Korrekturgrund',
            type: BusinessInput.multiline,
            required: true,
          ),
          const BusinessField(
            'confirmed',
            'Ich habe Arbeitstag und Zeitänderung geprüft. Der Originalnachweis bleibt erhalten.',
            type: BusinessInput.toggle,
            initial: false,
          ),
        ],
        onSave: (values) async {
          final minutes = values['minutes'];
          if (!dates.contains(values['work_date']) ||
              minutes is! int ||
              minutes == 0 ||
              minutes.abs() > 1440 ||
              values['confirmed'] != true)
            throw const ApiException(
              400,
              'Freigegebenen Tag, eine Änderung zwischen -1440 und 1440 Minuten (nicht 0) und die Bestätigung angeben.',
            );
          final body = <String, dynamic>{
            'work_date': values['work_date'],
            'delta_seconds': minutes * 60,
            'reason': values['reason'],
          };
          await widget.session.command(
            key,
            '/time/entries/${widget.entryId}/correct',
            body,
            validateResult: (result) {
              final record = businessMap(result);
              if (record['entry_id'] != widget.entryId ||
                  record['work_date'] != body['work_date'] ||
                  record['delta_seconds'] != body['delta_seconds'] ||
                  record['reason'] != '${body['reason']}'.trim())
                throw const ApiException(
                  0,
                  'Die Korrekturbestätigung passt nicht zum gesendeten Zeitnachweis.',
                );
            },
          );
        },
      ),
    );
    if (saved == true && mounted && allowed) await load();
  }

  @override
  Widget build(BuildContext context) {
    final value = allowed ? entry : null;
    final corrections = (value?['corrections'] as List? ?? [])
        .map(businessMap)
        .toList();
    return AlertDialog(
      title: const Text('Zeitnachweis'),
      content: SizedBox(
        width: 600,
        child: SingleChildScrollView(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              if (!allowed)
                const Notice(
                  'Der Zugriff auf diesen Zeitnachweis ist nicht mehr freigegeben.',
                  error: true,
                ),
              if (busy) const LinearProgressIndicator(),
              if (error != null) Notice(error!, error: true),
              if (value != null) ...[
                Text('Projekt: ${timeProjectName(widget.session, value)}'),
                Text(
                  'Erfasste Arbeitszeit: ${timeHours(value['worked_seconds'] as int? ?? 0)}',
                ),
                Text(
                  'Erfasste Pause: ${timeHours(value['break_seconds'] as int? ?? 0)}',
                ),
                Text(
                  'Arbeitstage (${value['timezone'] ?? 'Betriebszeitzone'}): ${(value['work_dates'] as List? ?? []).map(businessDate).join(', ')}',
                ),
                const SizedBox(height: 16),
                Text(
                  'Originalereignisse',
                  style: Theme.of(context).textTheme.titleMedium,
                ),
                for (final event in (value['events'] as List? ?? []).map(
                  businessMap,
                ))
                  Text(
                    '${const {'start': 'Beginn', 'pause': 'Pause', 'resume': 'Fortgesetzt', 'stop': 'Beendet'}[event['action']] ?? event['action']} · ${businessDate(event['occurred_at'], time: true)}',
                  ),
                const SizedBox(height: 16),
                Text(
                  'Begründete Korrekturen',
                  style: Theme.of(context).textTheme.titleMedium,
                ),
                if (corrections.isEmpty)
                  const Text('Keine Korrekturen gespeichert.'),
                for (final correction in corrections)
                  Padding(
                    padding: const EdgeInsets.symmetric(vertical: 6),
                    child: Text(
                      '${businessDate(correction['work_date'])}: ${timeHours(correction['delta_seconds'] as int? ?? 0)}\n${correction['reason']}',
                    ),
                  ),
                const SizedBox(height: 12),
                const Text(
                  'Korrekturen bleiben zusätzlich zu den Originalereignissen erhalten. Die bestätigte Nettozeit einschließlich automatischer Pausen steht im Zeitkonto.',
                ),
              ],
            ],
          ),
        ),
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.pop(context),
          child: const Text('Schließen'),
        ),
        if (value != null &&
            widget.session.canWrite('time.approve') &&
            (value['approved_work_dates'] as List? ?? []).isNotEmpty)
          FilledButton(
            onPressed: busy ? null : correct,
            child: const Text('Freigegebene Zeit korrigieren'),
          ),
      ],
    );
  }
}

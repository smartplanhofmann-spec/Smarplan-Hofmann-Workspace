import 'package:flutter/material.dart';

import 'business_session.dart';
import 'business_widgets.dart';
import 'design.dart';

class BusinessPlanningPage extends StatefulWidget {
  const BusinessPlanningPage({super.key, required this.session});
  final BusinessSession session;
  @override
  State<BusinessPlanningPage> createState() => _BusinessPlanningPageState();
}

class _BusinessPlanningPageState extends State<BusinessPlanningPage> {
  late DateTime week;
  Map<String, dynamic>? snapshot;
  bool loading = true;
  String? error;
  int epoch = 0;
  @override
  void initState() {
    super.initState();
    final now = DateTime.now();
    week = DateTime(now.year, now.month, now.day - now.weekday + 1);
    widget.session.addListener(changed);
    load();
  }

  void changed() {
    if (!mounted) return;
    if (!widget.session.can('planning.read')) {
      epoch++;
      snapshot = null;
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
    final current = ++epoch;
    setState(() {
      loading = true;
      error = null;
    });
    try {
      final data = businessMap(
        await widget.session.read(
          widget.session.query('/planning/calendar', {
            'from': week.toUtc().toIso8601String(),
            'to': DateTime(
              week.year,
              week.month,
              week.day + 7,
            ).toUtc().toIso8601String(),
          }),
        ),
      );
      if (mounted && current == epoch && widget.session.allowed)
        setState(() => snapshot = data);
    } catch (e) {
      if (mounted && current == epoch) setState(() => error = '$e');
    } finally {
      if (mounted && current == epoch) setState(() => loading = false);
    }
  }

  Future<void> edit([Map<String, dynamic>? item, DateTime? day]) async {
    if (!widget.session.canWrite('planning.write')) return;
    final id = item?['id'];
    final start = day ?? DateTime.now();
    final key = 'appointment-${id ?? DateTime.now().microsecondsSinceEpoch}';
    final employees = (snapshot?['employees'] as List? ?? []).map(businessMap);
    final resources = (snapshot?['resources'] as List? ?? []).map(businessMap);
    final fields = <BusinessField>[
      if (widget.session.projectId == null)
        BusinessField(
          'project_id',
          'Projekt',
          required: true,
          type: BusinessInput.choice,
          choices: {
            for (final p in widget.session.projects)
              '${p['id']}': '${p['name']}',
          },
        ),
      const BusinessField('title', 'Termin / Einsatz', required: true),
      const BusinessField(
        'details',
        'Beschreibung',
        type: BusinessInput.multiline,
      ),
      const BusinessField(
        'start_at',
        'Beginn',
        type: BusinessInput.instant,
        required: true,
      ),
      const BusinessField(
        'end_at',
        'Ende',
        type: BusinessInput.instant,
        required: true,
      ),
      BusinessField(
        'employee_ids',
        'Mitarbeiter',
        type: BusinessInput.multiple,
        choices: {for (final e in employees) '${e['id']}': '${e['name']}'},
      ),
      BusinessField(
        'resource_ids',
        'Fahrzeuge, Maschinen und Werkzeuge',
        type: BusinessInput.multiple,
        choices: {for (final r in resources) '${r['id']}': '${r['name']}'},
      ),
      if (item == null) ...[
        const BusinessField(
          'recurrence_frequency',
          'Wiederholung',
          type: BusinessInput.choice,
          required: true,
          initial: 'none',
          choices: {
            'none': 'Einzeltermin',
            'daily': 'Täglich',
            'weekly': 'Wöchentlich',
            'monthly': 'Monatlich',
          },
        ),
        const BusinessField(
          'recurrence_interval',
          'Abstand der Wiederholung',
          type: BusinessInput.integer,
          initial: 1,
          required: true,
        ),
        const BusinessField(
          'recurrence_count',
          'Anzahl Termine (einschließlich des ersten)',
          type: BusinessInput.integer,
          initial: 1,
          required: true,
        ),
      ],
      const BusinessField(
        'status',
        'Status',
        type: BusinessInput.choice,
        required: true,
        choices: {'scheduled': 'Geplant', 'cancelled': 'Abgesagt'},
      ),
    ];
    await showDialog<bool>(
      context: context,
      builder: (_) => BusinessEditor(
        readPermission: 'planning.read',
        writePermission: 'planning.write',
        session: widget.session,
        title: item == null ? 'Einsatz planen' : 'Einsatz verschieben / ändern',
        fields: fields,
        initial:
            item ??
            {
              'start_at': DateTime(
                start.year,
                start.month,
                start.day,
                8,
              ).toIso8601String(),
              'end_at': DateTime(
                start.year,
                start.month,
                start.day,
                9,
              ).toIso8601String(),
              'status': 'scheduled',
            },
        onSave: (values) async {
          final frequency = values.remove('recurrence_frequency');
          final interval = values.remove('recurrence_interval');
          final count = values.remove('recurrence_count');
          await widget.session.command(
            key,
            '/appointments${id == null ? '' : '/$id'}',
            {
              'timezone': item?['timezone'] ?? 'Europe/Berlin',
              ...values,
              if (frequency != null && frequency != 'none')
                'recurrence': {
                  'frequency': frequency,
                  'interval': interval,
                  'count': count,
                },
              if (widget.session.projectId != null)
                'project_id': widget.session.projectId,
              if (id != null) 'revision': item!['revision'],
            },
          );
        },
      ),
    );
    if (mounted) await load();
  }

  Widget appointment(Map<String, dynamic> item) {
    final names = {
      for (final row in (snapshot?['employees'] as List? ?? []).map(
        businessMap,
      ))
        '${row['id']}': '${row['name']}',
    };
    final card = Card(
      child: ListTile(
        title: Text('${item['title']}'),
        subtitle: Text(
          '${businessDate(item['start_at'], time: true)} – ${businessDate(item['end_at'], time: true)}\n${(item['employee_ids'] as List? ?? []).map((id) => names[id] ?? 'Zugeordneter Mitarbeiter').join(', ')}${item['status'] == 'cancelled' ? ' · Abgesagt' : ''}',
        ),
        isThreeLine: true,
        trailing: widget.session.canWrite('planning.write')
            ? const Icon(Icons.edit_calendar_outlined)
            : null,
        onTap: widget.session.canWrite('planning.write')
            ? () => edit(item)
            : null,
      ),
    );
    if (!widget.session.canWrite('planning.write') ||
        item['status'] == 'cancelled')
      return card;
    return LongPressDraggable<Map<String, dynamic>>(
      data: item,
      feedback: Material(
        elevation: 8,
        borderRadius: BorderRadius.circular(12),
        child: SizedBox(
          width: 280,
          child: Padding(
            padding: const EdgeInsets.all(16),
            child: Text('${item['title']}'),
          ),
        ),
      ),
      childWhenDragging: Opacity(opacity: .35, child: card),
      child: card,
    );
  }

  Future<void> moveToDay(Map<String, dynamic> item, DateTime day) async {
    if (loading || !widget.session.canWrite('planning.write')) return;
    final start = DateTime.parse(item['start_at']).toLocal();
    final end = DateTime.parse(item['end_at']).toLocal();
    final target = DateTime(
      day.year,
      day.month,
      day.day,
      start.hour,
      start.minute,
      start.second,
    );
    setState(() => loading = true);
    try {
      await widget.session.command(
        'move-${item['id']}-${item['revision']}-${day.toIso8601String()}',
        '/appointments/${item['id']}',
        {
          for (final name in [
            'project_id',
            'title',
            'details',
            'timezone',
            'employee_ids',
            'resource_ids',
            'status',
          ])
            name: item[name],
          'start_at': target.toUtc().toIso8601String(),
          'end_at': target.add(end.difference(start)).toUtc().toIso8601String(),
          'revision': item['revision'],
        },
      );
      if (mounted) await load();
    } catch (e) {
      if (mounted) setState(() => error = '$e');
    } finally {
      if (mounted) setState(() => loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    if (!widget.session.can('planning.read'))
      return const Center(child: Text('Der Zugang ist nicht mehr verfügbar.'));
    final appointments = (snapshot?['appointments'] as List? ?? [])
        .map(businessMap)
        .toList();
    return ListView(
      padding: const EdgeInsets.all(24),
      children: [
        Wrap(
          spacing: 12,
          runSpacing: 12,
          crossAxisAlignment: WrapCrossAlignment.center,
          children: [
            Text(
              'Einsatzplanung',
              style: Theme.of(context).textTheme.headlineMedium,
            ),
            if (widget.session.canWrite('planning.write'))
              FilledButton.icon(
                onPressed: loading ? null : () => edit(),
                icon: const Icon(Icons.add),
                label: const Text('Einsatz planen'),
              ),
          ],
        ),
        const SizedBox(height: 16),
        Row(
          children: [
            IconButton(
              tooltip: 'Vorherige Woche',
              onPressed: loading
                  ? null
                  : () {
                      setState(
                        () => week = DateTime(
                          week.year,
                          week.month,
                          week.day - 7,
                        ),
                      );
                      load();
                    },
              icon: const Icon(Icons.chevron_left),
            ),
            Expanded(
              child: Text(
                '${businessDate(week.toIso8601String())} – ${businessDate(DateTime(week.year, week.month, week.day + 6).toIso8601String())}',
                textAlign: TextAlign.center,
                style: Theme.of(context).textTheme.titleMedium,
              ),
            ),
            IconButton(
              tooltip: 'Nächste Woche',
              onPressed: loading
                  ? null
                  : () {
                      setState(
                        () => week = DateTime(
                          week.year,
                          week.month,
                          week.day + 7,
                        ),
                      );
                      load();
                    },
              icon: const Icon(Icons.chevron_right),
            ),
          ],
        ),
        const SizedBox(height: 8),
        const Text(
          'Alle Zeiten in Ihrer Gerätezeitzone. Mitarbeiterkalender und Plantafel zeigen denselben bestätigten Einsatz.',
        ),
        if (error != null) Notice(error!, error: true),
        if (loading) const LinearProgressIndicator(),
        const SizedBox(height: 16),
        for (var day = 0; day < 7; day++) ...[
          DragTarget<Map<String, dynamic>>(
            onWillAcceptWithDetails: (_) =>
                widget.session.canWrite('planning.write'),
            onAcceptWithDetails: (details) => moveToDay(
              details.data,
              DateTime(week.year, week.month, week.day + day),
            ),
            builder: (context, candidates, rejected) => Container(
              padding: const EdgeInsets.symmetric(vertical: 8),
              decoration: BoxDecoration(
                color: candidates.isEmpty ? null : OfficeColors.blueTint,
                borderRadius: BorderRadius.circular(12),
              ),
              child: Row(
                children: [
                  Expanded(
                    child: Text(
                      '${const ['Montag', 'Dienstag', 'Mittwoch', 'Donnerstag', 'Freitag', 'Samstag', 'Sonntag'][day]} · ${businessDate(DateTime(week.year, week.month, week.day + day).toIso8601String())}',
                      style: Theme.of(context).textTheme.titleMedium,
                    ),
                  ),
                  if (widget.session.canWrite('planning.write'))
                    IconButton(
                      tooltip: 'An diesem Tag planen',
                      onPressed: () => edit(
                        null,
                        DateTime(week.year, week.month, week.day + day),
                      ),
                      icon: const Icon(Icons.add_circle_outline),
                    ),
                ],
              ),
            ),
          ),
          for (final item in appointments.where((item) {
            final start = DateTime.tryParse('${item['start_at']}')?.toLocal();
            final date = DateTime(week.year, week.month, week.day + day);
            return start != null &&
                start.year == date.year &&
                start.month == date.month &&
                start.day == date.day;
          }))
            appointment(item),
          const SizedBox(height: 12),
        ],
        if (!loading &&
            snapshot != null &&
            (snapshot?['absences'] as List? ?? []).isNotEmpty) ...[
          const Divider(),
          Text('Abwesenheiten', style: Theme.of(context).textTheme.titleLarge),
          for (final absence in (snapshot!['absences'] as List).map(
            businessMap,
          ))
            ListTile(
              leading: const Icon(Icons.beach_access_outlined),
              title: Text(
                '${absence['employee_name'] ?? 'Mitarbeiter'} · ${businessDate(absence['start_date'])} – ${businessDate(absence['end_date'])}',
              ),
              subtitle: Text('${absence['status'] ?? ''}'),
            ),
        ],
      ],
    );
  }
}

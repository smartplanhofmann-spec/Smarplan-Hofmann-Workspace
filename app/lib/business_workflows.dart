import 'package:cryptography/cryptography.dart';
import 'package:flutter/material.dart';

import 'api.dart';
import 'business_session.dart';
import 'business_widgets.dart';
import 'business_documentation.dart';
import 'design.dart';
import 'mail_attachment_preview.dart';
import 'mail_attachment_widgets.dart' show exportMailAttachment;

String businessHours(Object? value) {
  final seconds = value is int ? value : 0;
  final sign = seconds < 0 ? '-' : '';
  final n = seconds.abs();
  return '$sign${n ~/ 3600}:${'${n % 3600 ~/ 60}'.padLeft(2, '0')} Std.';
}

class BusinessTimeAccountsPage extends StatefulWidget {
  const BusinessTimeAccountsPage({super.key, required this.session});
  final BusinessSession session;
  @override
  State<BusinessTimeAccountsPage> createState() =>
      _BusinessTimeAccountsPageState();
}

class _BusinessTimeAccountsPageState extends State<BusinessTimeAccountsPage> {
  Map<String, dynamic>? account;
  List<Map<String, dynamic>> employees = [];
  String? employee, error;
  bool busy = false;
  int epoch = 0;
  DateTime from = DateTime(DateTime.now().year, DateTime.now().month, 1),
      to = DateTime.now();
  Map<String, String> get query => {
    'from': from.toIso8601String().substring(0, 10),
    'to': to.toIso8601String().substring(0, 10),
    if (employee != null) 'employee_id': employee!,
  };
  @override
  void initState() {
    super.initState();
    widget.session.addListener(changed);
    load();
  }

  void changed() {
    if (mounted) {
      if (!widget.session.can('time.own')) {
        epoch++;
        account = null;
        employees = [];
      }
      setState(() {});
    }
  }

  @override
  void dispose() {
    epoch++;
    widget.session.removeListener(changed);
    super.dispose();
  }

  Future<void> load() async {
    final current = ++epoch;
    setState(() => busy = true);
    try {
      final values = businessMap(
        await widget.session.read(
          '/time/accounts?${Uri(queryParameters: query).query}',
        ),
      );
      if (!mounted || current != epoch || !widget.session.can('time.own'))
        return;
      setState(() => account = values);
      if (widget.session.can('personnel.read')) {
        final team = businessItems(await widget.session.read('/employees'));
        if (mounted && current == epoch && widget.session.allowed)
          setState(() => employees = team);
      }
    } catch (e) {
      if (mounted && current == epoch) setState(() => error = '$e');
    } finally {
      if (mounted && current == epoch) setState(() => busy = false);
    }
  }

  Future<void> approve(Map<String, dynamic> day) async {
    if (busy || !widget.session.canWrite('time.approve') || account == null)
      return;
    if (!await businessConfirm(
          context,
          title: 'Arbeitstag freigeben?',
          message:
              'Bitte Zeiten und Pausen für ${businessDate(day['date'])} prüfen. Nach Freigabe sind Änderungen nur noch mit nachvollziehbarer Korrektur möglich. Optionale Standortdaten werden gelöscht.',
          action: 'Geprüften Tag freigeben',
        ) ||
        !mounted)
      return;
    setState(() => busy = true);
    try {
      await widget.session.command(
        'approve-${account!['employee_id']}-${day['date']}-${day['revision']}',
        '/time/days/${day['date']}/approve',
        {'employee_id': account!['employee_id'], 'revision': day['revision']},
      );
      await load();
    } catch (e) {
      if (mounted) setState(() => error = '$e');
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  Future<void> export() async {
    if (busy || !widget.session.can('time.own')) return;
    setState(() => busy = true);
    try {
      final bytes = await widget.session.api.bytes(
        widget.session.path(
          '/time/export?${Uri(queryParameters: query).query}',
        ),
        mediaType: 'text/csv',
      );
      if (!mounted || !widget.session.can('time.own')) return;
      final digest = (await Sha256().hash(bytes)).bytes
          .map((v) => v.toRadixString(16).padLeft(2, '0'))
          .join();
      if (!mounted || !widget.session.allowed) return;
      await exportMailAttachment(
        context,
        VerifiedMailAttachment(
          bytes: bytes,
          filename: 'freigegebene-stunden.csv',
          mediaType: 'text/csv',
          sha256: digest,
        ),
        () => mounted && widget.session.can('time.own'),
      );
    } catch (e) {
      if (mounted) setState(() => error = '$e');
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    if (!widget.session.can('time.own'))
      return const BusinessEmpty(
        'Zeitkonto nicht freigegeben',
        'Arbeitszeiten benötigen die passende Personalberechtigung.',
      );
    final data = account;
    return ListView(
      padding: const EdgeInsets.all(24),
      children: [
        Wrap(
          spacing: 12,
          runSpacing: 12,
          crossAxisAlignment: WrapCrossAlignment.center,
          children: [
            Text(
              'Zeitkonto',
              style: Theme.of(context).textTheme.headlineMedium,
            ),
            OutlinedButton.icon(
              onPressed: busy ? null : export,
              icon: const Icon(Icons.download_outlined),
              label: const Text('Freigegebene Stunden exportieren'),
            ),
          ],
        ),
        const SizedBox(height: 16),
        if (employees.isNotEmpty)
          DropdownButtonFormField<String>(
            initialValue: employee ?? '',
            decoration: const InputDecoration(labelText: 'Mitarbeiter'),
            items: [
              const DropdownMenuItem(value: '', child: Text('Eigene Zeiten')),
              for (final e in employees)
                DropdownMenuItem(
                  value: e['id'] as String,
                  child: Text('${e['name']}'),
                ),
            ],
            onChanged: busy
                ? null
                : (v) {
                    setState(() => employee = v == '' ? null : v);
                    load();
                  },
          ),
        const SizedBox(height: 12),
        Wrap(
          spacing: 12,
          runSpacing: 12,
          children: [
            OutlinedButton(
              onPressed: busy
                  ? null
                  : () async {
                      final value = await showDatePicker(
                        context: context,
                        initialDate: from,
                        firstDate: DateTime(2000),
                        lastDate: DateTime(2200),
                      );
                      if (value != null && mounted) {
                        setState(() => from = value);
                        load();
                      }
                    },
              child: Text('Von ${businessDate(from.toIso8601String())}'),
            ),
            OutlinedButton(
              onPressed: busy
                  ? null
                  : () async {
                      final value = await showDatePicker(
                        context: context,
                        initialDate: to,
                        firstDate: from,
                        lastDate: DateTime(2200),
                      );
                      if (value != null && mounted) {
                        setState(() => to = value);
                        load();
                      }
                    },
              child: Text('Bis ${businessDate(to.toIso8601String())}'),
            ),
          ],
        ),
        if (error != null) Notice(error!, error: true),
        if (busy) const LinearProgressIndicator(),
        if (data != null) ...[
          const SizedBox(height: 16),
          Card(
            child: Padding(
              padding: const EdgeInsets.all(20),
              child: Wrap(
                spacing: 24,
                runSpacing: 12,
                children: [
                  Text('Netto erfasst: ${businessHours(data['net_seconds'])}'),
                  Text('Soll: ${businessHours(data['target_seconds'])}'),
                  Text('Saldo: ${businessHours(data['balance_seconds'])}'),
                ],
              ),
            ),
          ),
          for (final day in (data['days'] as List? ?? []).map(businessMap))
            Card(
              child: Padding(
                padding: const EdgeInsets.all(20),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      businessDate(day['date']),
                      style: Theme.of(context).textTheme.titleMedium,
                    ),
                    Text(
                      'Arbeit: ${businessHours(day['net_seconds'])} · Pause: ${businessHours(day['break_seconds'])} · Automatischer Abzug: ${businessHours(day['auto_pause_seconds'])}',
                    ),
                    Text(
                      day['status'] == 'approved'
                          ? 'Freigegeben'
                          : 'Noch nicht freigegeben',
                    ),
                    if (day['status'] != 'approved' &&
                        widget.session.canWrite('time.approve'))
                      TextButton(
                        onPressed: busy ? null : () => approve(day),
                        child: const Text('Tag prüfen und freigeben'),
                      ),
                  ],
                ),
              ),
            ),
        ],
      ],
    );
  }
}

class BusinessDunningSettingsPage extends StatefulWidget {
  const BusinessDunningSettingsPage({super.key, required this.session});
  final BusinessSession session;
  @override
  State<BusinessDunningSettingsPage> createState() =>
      _BusinessDunningSettingsPageState();
}

class _BusinessDunningSettingsPageState
    extends State<BusinessDunningSettingsPage> {
  Map<String, dynamic>? settings;
  List<Map<String, dynamic>> levels = [];
  bool enabled = false, busy = false;
  String? error;
  Map<String, dynamic>? pending;
  @override
  void initState() {
    super.initState();
    widget.session.addListener(changed);
    load();
  }

  void changed() {
    if (mounted) {
      if (!widget.session.can('settings.manage')) {
        settings = null;
        levels = [];
      }
      setState(() {});
    }
  }

  @override
  void dispose() {
    widget.session.removeListener(changed);
    super.dispose();
  }

  Future<void> load() async {
    try {
      final result = businessMap(
        await widget.session.read('/finance/dunning/settings'),
      );
      if (mounted && widget.session.can('settings.manage'))
        setState(() {
          settings = result;
          levels = (result['levels'] as List? ?? []).map(businessMap).toList();
          enabled = result['enabled'] == true;
        });
    } catch (e) {
      if (mounted) setState(() => error = '$e');
    }
  }

  Future<void> edit([int? index]) async {
    if (!widget.session.canWrite('settings.manage') || busy || pending != null)
      return;
    await showDialog<bool>(
      context: context,
      builder: (_) => BusinessEditor(
        session: widget.session,
        title: index == null ? 'Mahnstufe hinzufügen' : 'Mahnstufe bearbeiten',
        initial: index == null
            ? {
                'kind': 'reminder',
                'days': 7,
                'fee': '0',
                'interest_percent': '0',
              }
            : levels[index],
        fields: const [
          BusinessField(
            'kind',
            'Art',
            type: BusinessInput.choice,
            required: true,
            choices: {'reminder': 'Zahlungserinnerung', 'demand': 'Mahnung'},
          ),
          BusinessField('name', 'Stufenname', required: true),
          BusinessField(
            'days',
            'Abstand in Tagen',
            type: BusinessInput.integer,
            required: true,
          ),
          BusinessField(
            'fee',
            'Gebühr (€)',
            type: BusinessInput.decimal,
            required: true,
          ),
          BusinessField(
            'interest_percent',
            'Zins (%)',
            type: BusinessInput.decimal,
            required: true,
          ),
          BusinessField('subject', 'E-Mail-Betreff', required: true),
          BusinessField(
            'text',
            'Text',
            type: BusinessInput.multiline,
            required: true,
          ),
        ],
        onSave: (values) async {
          if (mounted)
            setState(() {
              if (index == null)
                levels.add(values);
              else
                levels[index] = values;
            });
        },
      ),
    );
  }

  Future<void> save() async {
    if (busy || settings == null || !widget.session.canWrite('settings.manage'))
      return;
    setState(() => busy = true);
    pending ??= {
      'revision': settings!['revision'],
      'enabled': enabled,
      'levels': [
        for (var i = 0; i < levels.length; i++) {...levels[i], 'level': i + 1},
      ],
    };
    try {
      await widget.session.command(
        'dunning-settings-${settings!['revision']}',
        '/finance/dunning/settings',
        pending!,
      );
      if (mounted) {
        pending = null;
        await load();
      }
    } on ApiException catch (e) {
      if (mounted)
        setState(() {
          error = e.message;
          if (e.status != 0 && e.status < 500 && e.status != 429)
            pending = null;
        });
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    if (!widget.session.can('settings.manage'))
      return const Scaffold(body: Center(child: Text('Kein Zugriff.')));
    final writable =
        widget.session.canWrite('settings.manage') && !busy && pending == null;
    return Scaffold(
      appBar: AppBar(title: const Text('Mahnregeln')),
      body: ListView(
        padding: const EdgeInsets.all(24),
        children: [
          const Notice(
            'Bis zu sechs Stufen. Diese Regeln erzeugen zunächst nur Vorschläge. Jede Mahnung braucht weiterhin Ihre Freigabe; ein ungeklärter Versand wird nicht blind wiederholt.',
          ),
          if (error != null) Notice(error!, error: true),
          SwitchListTile.adaptive(
            contentPadding: EdgeInsets.zero,
            title: const Text('Mahnvorschläge aktivieren'),
            value: enabled,
            onChanged: writable ? (v) => setState(() => enabled = v) : null,
          ),
          for (var i = 0; i < levels.length; i++)
            Card(
              child: ListTile(
                title: Text('${i + 1}. ${levels[i]['name']}'),
                subtitle: Text(
                  '${levels[i]['days']} Tage · ${businessMoney(levels[i]['fee'])} Gebühr',
                ),
                onTap: writable ? () => edit(i) : null,
                trailing: IconButton(
                  tooltip: 'Stufe entfernen',
                  onPressed: writable
                      ? () => setState(() => levels.removeAt(i))
                      : null,
                  icon: const Icon(Icons.delete_outline),
                ),
              ),
            ),
          if (levels.length < 6)
            OutlinedButton.icon(
              onPressed: writable ? () => edit() : null,
              icon: const Icon(Icons.add),
              label: const Text('Stufe hinzufügen'),
            ),
          const SizedBox(height: 16),
          FilledButton(
            onPressed: busy || !widget.session.canWrite('settings.manage')
                ? null
                : save,
            child: Text(
              pending == null
                  ? 'Mahnregeln speichern'
                  : 'Dieselben Regeln erneut senden',
            ),
          ),
        ],
      ),
    );
  }
}

class BusinessChecklistsPage extends StatefulWidget {
  const BusinessChecklistsPage({super.key, required this.session});
  final BusinessSession session;
  @override
  State<BusinessChecklistsPage> createState() => _BusinessChecklistsPageState();
}

class _BusinessChecklistsPageState extends State<BusinessChecklistsPage> {
  List<Map<String, dynamic>> templates = [], runs = [];
  String? error;
  bool busy = false;
  @override
  void initState() {
    super.initState();
    widget.session.addListener(changed);
    load();
  }

  void changed() {
    if (mounted) {
      if (!widget.session.can('documents.read')) {
        templates = [];
        runs = [];
      }
      setState(() {});
    }
  }

  @override
  void dispose() {
    widget.session.removeListener(changed);
    super.dispose();
  }

  Future<void> load() async {
    try {
      final t = businessItems(
        await widget.session.read(widget.session.query('/checklists')),
      );
      final r = businessItems(
        await widget.session.read(widget.session.query('/checklist-runs')),
      );
      if (mounted && widget.session.can('documents.read'))
        setState(() {
          templates = t;
          runs = r;
        });
    } catch (e) {
      if (mounted) setState(() => error = '$e');
    }
  }

  Future<void> create() async {
    await showDialog<bool>(
      context: context,
      builder: (_) => BusinessEditor(
        session: widget.session,
        title: 'Technikercheckliste erstellen',
        fields: const [
          BusinessField('title', 'Titel', required: true),
          BusinessField(
            'lines',
            'Prüfpunkte (ein Punkt je Zeile)',
            type: BusinessInput.multiline,
            required: true,
          ),
        ],
        onSave: (values) async {
          final rows = (values['lines'] as String)
              .split('\n')
              .map((s) => s.trim())
              .where((s) => s.isNotEmpty)
              .toList();
          await widget.session.command('checklist-create', '/checklists', {
            'project_id': widget.session.projectId,
            'title': values['title'],
            'items': [
              for (var i = 0; i < rows.length; i++)
                {
                  'key': 'point_$i',
                  'label': rows[i],
                  'type': 'boolean',
                  'required': true,
                },
            ],
          });
        },
      ),
    );
    if (mounted) await load();
  }

  Future<void> start(Map<String, dynamic> template) async {
    if (busy) return;
    setState(() => busy = true);
    try {
      final run = businessMap(
        await widget.session.command(
          'checklist-start-${template['id']}',
          '/checklists/${template['id']}/start',
          {},
        ),
      );
      if (mounted && widget.session.allowed) await openRun(run);
      await load();
    } catch (e) {
      if (mounted) setState(() => error = '$e');
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  Future<void> openRun(Map<String, dynamic> run) async {
    await Navigator.push<void>(
      context,
      MaterialPageRoute(
        builder: (_) =>
            BusinessChecklistRunPage(session: widget.session, id: run['id']),
      ),
    );
    if (mounted) await load();
  }

  @override
  Widget build(BuildContext context) {
    if (!widget.session.can('documents.read'))
      return const BusinessEmpty(
        'Kein Zugriff',
        'Checklisten benötigen Dokumentzugriff.',
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
              'Checklisten',
              style: Theme.of(context).textTheme.headlineMedium,
            ),
            if (widget.session.canWrite('documents.write'))
              FilledButton.icon(
                onPressed: busy ? null : create,
                icon: const Icon(Icons.add),
                label: const Text('Vorlage erstellen'),
              ),
          ],
        ),
        if (error != null) Notice(error!, error: true),
        const SizedBox(height: 16),
        for (final t in templates)
          Card(
            child: ListTile(
              title: Text('${t['title']}'),
              subtitle: Text('Vorlage · Version ${t['revision']}'),
              trailing: widget.session.canWrite('documents.write')
                  ? TextButton(
                      onPressed: busy ? null : () => start(t),
                      child: const Text('Prüfung beginnen'),
                    )
                  : null,
            ),
          ),
        const SizedBox(height: 20),
        Text(
          'Durchgeführte Prüfungen',
          style: Theme.of(context).textTheme.titleLarge,
        ),
        for (final r in runs)
          Card(
            child: ListTile(
              title: Text('${r['title']}'),
              subtitle: Text(
                r['status'] == 'completed'
                    ? 'Im Servicebericht übernommen'
                    : 'Prüfung offen',
              ),
              trailing: const Icon(Icons.chevron_right),
              onTap: () => openRun(r),
            ),
          ),
      ],
    );
  }
}

class BusinessChecklistRunPage extends StatefulWidget {
  const BusinessChecklistRunPage({
    super.key,
    required this.session,
    required this.id,
  });
  final BusinessSession session;
  final String id;
  @override
  State<BusinessChecklistRunPage> createState() =>
      _BusinessChecklistRunPageState();
}

class _BusinessChecklistRunPageState extends State<BusinessChecklistRunPage> {
  Map<String, dynamic>? run;
  String? error;
  bool busy = false;
  @override
  void initState() {
    super.initState();
    widget.session.addListener(changed);
    load();
  }

  void changed() {
    if (mounted) {
      if (!widget.session.can('documents.read')) run = null;
      setState(() {});
    }
  }

  @override
  void dispose() {
    widget.session.removeListener(changed);
    super.dispose();
  }

  Future<void> load() async {
    try {
      final result = businessMap(
        await widget.session.read('/checklist-runs/${widget.id}'),
      );
      if (mounted && widget.session.can('documents.read'))
        setState(() => run = result);
    } catch (e) {
      if (mounted) setState(() => error = '$e');
    }
  }

  Future<void> answer() async {
    final r = run;
    if (r == null) return;
    final items = (r['items'] as List).map(businessMap).toList();
    await showDialog<bool>(
      context: context,
      builder: (_) => BusinessEditor(
        session: widget.session,
        title: 'Prüfpunkte beantworten',
        initial: businessMap(r['answers']),
        fields: [
          for (final item in items)
            BusinessField(
              item['key'],
              item['label'],
              type: item['type'] == 'boolean'
                  ? BusinessInput.toggle
                  : item['type'] == 'number'
                  ? BusinessInput.decimal
                  : BusinessInput.multiline,
              required: item['required'] == true,
            ),
        ],
        onSave: (values) async {
          await widget.session.command(
            'checklist-answers-${widget.id}-${r['revision']}',
            '/checklists/${widget.id}/answers',
            {'revision': r['revision'], 'answers': values},
          );
        },
      ),
    );
    if (mounted) await load();
  }

  Future<void> report() async {
    if (run == null || busy) return;
    setState(() => busy = true);
    try {
      final result = businessMap(
        await widget.session.command(
          'checklist-report-${widget.id}',
          '/checklists/${widget.id}/report',
          {},
        ),
      );
      if (mounted && widget.session.allowed)
        await Navigator.push<void>(
          context,
          MaterialPageRoute(
            builder: (_) => BusinessOperationDocumentPage(
              session: widget.session,
              path: '/service-reports',
              id: result['id'],
              fields: const [
                BusinessField('title', 'Titel', required: true),
                BusinessField(
                  'description',
                  'Beschreibung',
                  type: BusinessInput.multiline,
                ),
                BusinessField(
                  'notes',
                  'Notizen',
                  type: BusinessInput.multiline,
                ),
              ],
            ),
          ),
        );
      if (mounted) await load();
    } catch (e) {
      if (mounted) setState(() => error = '$e');
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final r = run;
    return Scaffold(
      appBar: AppBar(title: const Text('Technikerprüfung')),
      body: !widget.session.can('documents.read')
          ? const Center(child: Text('Kein Zugriff.'))
          : ListView(
              padding: const EdgeInsets.all(24),
              children: [
                if (error != null) Notice(error!, error: true),
                if (r != null) ...[
                  Text(
                    '${r['title']}',
                    style: Theme.of(context).textTheme.headlineMedium,
                  ),
                  Text('Verwendete Vorlagenversion: ${r['template_revision']}'),
                  const SizedBox(height: 20),
                  for (final item in (r['items'] as List).map(businessMap))
                    Card(
                      child: ListTile(
                        title: Text('${item['label']}'),
                        subtitle: Text(
                          businessMap(r['answers']).containsKey(item['key'])
                              ? 'Antwort: ${businessMap(r['answers'])[item['key']] == true
                                    ? 'Ja'
                                    : businessMap(r['answers'])[item['key']] == false
                                    ? 'Nein'
                                    : businessMap(r['answers'])[item['key']]}'
                              : 'Noch nicht beantwortet',
                        ),
                      ),
                    ),
                  if (r['status'] == 'open' &&
                      widget.session.canWrite('documents.write')) ...[
                    OutlinedButton(
                      onPressed: busy ? null : answer,
                      child: const Text('Prüfpunkte beantworten'),
                    ),
                    const SizedBox(height: 12),
                    FilledButton(
                      onPressed: busy ? null : report,
                      child: const Text('In Servicebericht übernehmen'),
                    ),
                  ],
                  if (r['report_id'] != null)
                    OutlinedButton(
                      onPressed: () => Navigator.push<void>(
                        context,
                        MaterialPageRoute(
                          builder: (_) => BusinessOperationDocumentPage(
                            session: widget.session,
                            path: '/service-reports',
                            id: r['report_id'],
                          ),
                        ),
                      ),
                      child: const Text('Servicebericht öffnen'),
                    ),
                ],
              ],
            ),
    );
  }
}

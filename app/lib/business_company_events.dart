import 'dart:convert';

import 'package:flutter/material.dart';

import 'api.dart';
import 'business_company_event_contract.dart';
import 'business_session.dart';
import 'business_widgets.dart';
import 'design.dart';
import 'offline_vault.dart' show offlineId;

bool companyEventsReadable(BusinessSession session) =>
    session.allowed &&
    session.hasFeature('company_event_rules') &&
    session.hasModule('company_events') &&
    session.can('assistant.use');

/// Owns exactly the route opened by this entry. Replacing its parent session
/// cannot leave an old private page on top of the new authenticated view.
class BusinessCompanyEventsEntry extends StatefulWidget {
  const BusinessCompanyEventsEntry({super.key, required this.session});
  final BusinessSession session;
  @override
  State<BusinessCompanyEventsEntry> createState() =>
      _BusinessCompanyEventsEntryState();
}

class _BusinessCompanyEventsEntryState
    extends State<BusinessCompanyEventsEntry> {
  Route<void>? route;
  NavigatorState? navigator;
  @override
  void initState() {
    super.initState();
    widget.session.addListener(changed);
  }

  @override
  void didUpdateWidget(covariant BusinessCompanyEventsEntry oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (!identical(oldWidget.session, widget.session)) {
      oldWidget.session.removeListener(changed);
      widget.session.addListener(changed);
      closeRoute();
    }
  }

  void changed() {
    if (!companyEventsReadable(widget.session)) closeRoute();
    if (mounted) setState(() {});
  }

  void closeRoute() {
    final old = route, owner = navigator;
    route = null;
    navigator = null;
    if (old == null || owner == null) return;
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (owner.mounted && old.isActive) owner.removeRoute(old);
    });
  }

  Future<void> open() async {
    if (route != null || !companyEventsReadable(widget.session)) return;
    final source = widget.session, owner = Navigator.of(context);
    final opened = MaterialPageRoute<void>(
      builder: (_) => BusinessCompanyEventsPage(session: source),
    );
    route = opened;
    navigator = owner;
    await owner.push(opened);
    if (identical(route, opened)) {
      route = null;
      navigator = null;
    }
  }

  @override
  void dispose() {
    widget.session.removeListener(changed);
    closeRoute();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => companyEventsReadable(widget.session)
      ? OutlinedButton.icon(
          icon: const Icon(Icons.event_note_outlined),
          label: const Text('Unternehmensereignisse öffnen'),
          onPressed: open,
        )
      : const SizedBox.shrink();
}

String _sourceTitle(Map<String, dynamic> source) {
  final value = businessMap(source['data']);
  return '${value['title'] ?? value['subject'] ?? value['name'] ?? value['number'] ?? 'Fachquelle'}';
}

String _fact(String key, dynamic value) =>
    key.endsWith('_minor') && value is String
    ? companyEventMoney(value)
    : value is bool
    ? (value ? 'Ja' : 'Nein')
    : value == null
    ? 'Nicht angegeben'
    : '$value';

class BusinessCompanyEventsPage extends StatefulWidget {
  const BusinessCompanyEventsPage({super.key, required this.session});
  final BusinessSession session;
  @override
  State<BusinessCompanyEventsPage> createState() =>
      _BusinessCompanyEventsPageState();
}

class _BusinessCompanyEventsPageState extends State<BusinessCompanyEventsPage>
    with WidgetsBindingObserver {
  late BusinessSession session;
  final scopes = <BusinessSession, String>{};
  String? signature, error, actorId, actorRole, cursor, scanAfter;
  String screen = 'overview', tab = 'plans';
  Map<String, dynamic>? data, event, status, oldRule;
  List<Map<String, dynamic>> users = [], articles = [];
  int epoch = 0;
  bool busy = false, background = false, confirmed = false;
  final reason = TextEditingController();
  final scroll = ScrollController();
  bool get readable => companyEventsReadable(session);
  bool get manage => readable && session.can('settings.manage');
  bool get writable => readable && session.canWrite('assistant.use');

  String fingerprint(BusinessSession value) => jsonEncode([
    value.allowed,
    value.supported,
    value.generation,
    value.readonly,
    value.permissions.toList()..sort(),
    value.capabilities.toList()..sort(),
    value.features.toList()..sort(),
    value.organizationModules,
  ]);
  void bind() {
    session = widget.session.sharedGlobalSession();
    widget.session.addListener(changed);
    if (!identical(session, widget.session)) session.addListener(changed);
  }

  void unbind(BusinessSession parent) {
    parent.removeListener(changed);
    if (!identical(session, parent)) session.removeListener(changed);
    for (final scope in scopes.keys) {
      scope.removeListener(changed);
    }
    scopes.clear();
  }

  @override
  void initState() {
    super.initState();
    bind();
    WidgetsBinding.instance.addObserver(this);
    loadOverview();
  }

  @override
  void didUpdateWidget(covariant BusinessCompanyEventsPage oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (!identical(oldWidget.session, widget.session)) {
      unbind(oldWidget.session);
      erase();
      bind();
      loadOverview();
    }
  }

  void erase() {
    epoch++;
    data = null;
    event = null;
    status = null;
    oldRule = null;
    users = [];
    articles = [];
    actorId = null;
    actorRole = null;
    error = null;
    busy = false;
    confirmed = false;
    reason.clear();
    screen = 'overview';
    cursor = null;
    scanAfter = null;
    signature = null;
    for (final scope in scopes.keys) {
      scope.removeListener(changed);
    }
    scopes.clear();
  }

  void changed() {
    if (!mounted) return;
    if (!widget.session.allowed ||
        !readable ||
        signature != null && signature != fingerprint(session) ||
        scopes.entries.any((entry) => entry.value != fingerprint(entry.key))) {
      erase();
    }
    setState(() {});
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (!mounted) return;
    background = state != AppLifecycleState.resumed;
    if (background) erase();
    setState(() {});
  }

  @override
  void dispose() {
    epoch++;
    unbind(widget.session);
    WidgetsBinding.instance.removeObserver(this);
    reason.dispose();
    scroll.dispose();
    super.dispose();
  }

  bool alive(int ticket) =>
      mounted && !background && ticket == epoch && widget.session.allowed;
  void guard(int ticket) {
    if (!alive(ticket))
      throw const ApiException(
        0,
        'Die Unternehmensereignis-Ansicht wurde geschlossen oder gewechselt.',
      );
  }

  int begin(String next) {
    erase();
    signature = session.ready ? fingerprint(session) : null;
    screen = next;
    busy = true;
    setState(() {});
    if (scroll.hasClients) scroll.jumpTo(0);
    return epoch;
  }

  void remember(Set<String> projects) {
    signature = fingerprint(session);
    for (final id in projects) {
      final scope = session.sharedProjectSession(id);
      if (!scopes.containsKey(scope)) scope.addListener(changed);
      scopes[scope] = fingerprint(scope);
    }
  }

  Future<void> fresh(
    int ticket, {
    bool manager = false,
    bool write = false,
  }) async {
    guard(ticket);
    await session.load();
    guard(ticket);
    if (!readable ||
        manager && !manage ||
        write && !writable ||
        session.error != null ||
        session.loading) {
      throw const ApiException(403, 'Die aktuellen Unternehmensrechte fehlen.');
    }
    signature ??= fingerprint(session);
  }

  Future<void> authorize(
    int ticket,
    dynamic value, {
    bool manager = false,
    bool write = false,
  }) async {
    await fresh(ticket, manager: manager, write: write);
    final projectIds = await session.authorizeCompanyEventData(value);
    guard(ticket);
    if (!readable || manager && !manage || write && !writable)
      throw const ApiException(403, 'Aktuelle Berechtigung entzogen.');
    remember(projectIds);
  }

  void failed(int ticket, Object problem) {
    if (!alive(ticket)) return;
    if (problem is ApiException && [401, 403, 404].contains(problem.status)) {
      erase();
      setState(
        () => error =
            'Dieser Vorgang ist mit den aktuellen Rechten nicht verfügbar.',
      );
    } else {
      setState(
        () => error = 'Der Vorgang konnte nicht sicher bestätigt werden. Bitte den aktuellen Stand prüfen; ein unbestätigter Originalauftrag bleibt erhalten.',
      );
    }
  }

  void done(int ticket) {
    if (alive(ticket)) setState(() => busy = false);
  }

  Future<void> loadOverview([String? nextTab, String? after]) async {
    final selected = nextTab ?? tab, ticket = begin('overview');
    tab = selected;
    try {
      await fresh(ticket);
      if (['rules', 'runs'].contains(tab) && !manage) tab = 'plans';
      final rawStatus = await session.read('$companyEventBase/status');
      guard(ticket);
      final checkedStatus = companyEventStatus(rawStatus);
      final actor = businessMap(await session.legacyRead('/api/me'));
      guard(ticket);
      final path = tab == 'rules'
          ? '$companyEventBase/rules'
          : '$companyEventBase/$tab?${Uri(queryParameters: {'limit': '50', if (after != null) 'after': after}).query}';
      final result = companyEventMap(await session.read(path));
      guard(ticket);
      if (tab == 'rules') {
        if (result['schema_version'] != 1)
          throw const ApiException(0, 'Ungültige Regelübersicht.');
        for (final row in businessItems(result)) {
          companyEventRule(row);
        }
      } else {
        companyEventPage(result, tab);
      }
      await authorize(ticket, result, manager: ['rules', 'runs'].contains(tab));
      guard(ticket);
      setState(() {
        data = result;
        status = checkedStatus;
        actorId = actor['id'];
        actorRole = actor['role'];
        cursor = after;
      });
    } catch (e) {
      failed(ticket, e);
    } finally {
      done(ticket);
    }
  }

  Future<void> open(String kind, String id) async {
    final ticket = begin(kind);
    try {
      await fresh(ticket, manager: kind == 'run' || kind == 'rule_history');
      final path = kind == 'rule_history'
          ? '$companyEventBase/rules/$id/history'
          : '$companyEventBase/${kind}s/$id';
      final raw = await session.read(path);
      guard(ticket);
      final value = switch (kind) {
        'plan' => companyEventPlan(raw),
        'event' => companyEventObservation(raw),
        'run' => companyEventRun(raw),
        'rule_history' => companyEventRuleHistory(raw, id),
        _ => throw const ApiException(0, 'Unbekannte Ereignisansicht.'),
      };
      Map<String, dynamic>? original;
      if (kind == 'plan') {
        original = companyEventObservation(
          await session.read('$companyEventBase/events/${value['event_id']}'),
        );
        guard(ticket);
        companyEventPlan(value, event: original);
      }
      final actor = businessMap(await session.legacyRead('/api/me'));
      guard(ticket);
      await authorize(
        ticket,
        value,
        manager: kind == 'run' || kind == 'rule_history',
      );
      guard(ticket);
      setState(() {
        data = value;
        event = original;
        actorId = actor['id'];
        actorRole = actor['role'];
      });
    } catch (e) {
      failed(ticket, e);
    } finally {
      done(ticket);
    }
  }

  Future<void> startScan([String? after]) async {
    final ticket = begin('scan');
    try {
      await fresh(ticket, manager: true, write: true);
      remember({});
      setState(() => scanAfter = after);
    } catch (e) {
      failed(ticket, e);
    } finally {
      done(ticket);
    }
  }

  Future<void> editRule([Map<String, dynamic>? original]) async {
    final ticket = begin('rule_edit');
    try {
      await fresh(ticket, manager: true, write: true);
      final checkedStatus = companyEventStatus(
        await session.read('$companyEventBase/status'),
      );
      guard(ticket);
      final actor = businessMap(await session.legacyRead('/api/me'));
      guard(ticket);
      List<Map<String, dynamic>> people;
      try {
        people = businessItems(await session.legacyRead('/api/users'));
      } on ApiException catch (e) {
        if (e.status != 403) rethrow;
        people = [
          {'id': actor['id'], 'name': 'Sie'},
        ];
      }
      guard(ticket);
      List<Map<String, dynamic>> choices = [];
      if (session.can('finance.read')) {
        choices = businessItems(await session.read('/articles'));
        guard(ticket);
        await fresh(ticket, manager: true, write: true);
        if (!session.can('finance.read'))
          throw const ApiException(403, 'Artikelrechte entzogen.');
      }
      await fresh(ticket, manager: true, write: true);
      guard(ticket);
      remember({});
      setState(() {
        status = checkedStatus;
        oldRule = original;
        users = people;
        articles = choices;
        actorId = actor['id'];
        actorRole = actor['role'];
      });
    } catch (e) {
      failed(ticket, e);
    } finally {
      done(ticket);
    }
  }

  Future<void> send(String path, Map<String, dynamic> values) async {
    final ticket = begin('pending'), owner = session;
    try {
      final result = companyEventMap(
        await owner.companyEventCommand(
          path,
          values,
          stillCurrent: () =>
              alive(ticket) && identical(owner, session) && writable,
        ),
      );
      guard(ticket);
      await authorize(
        ticket,
        result,
        manager: ['rule', 'scan'].contains(companyEventOperation(path)),
      );
      guard(ticket);
      final operation = companyEventOperation(path);
      if (operation == 'rule') {
        await loadOverview('rules');
      } else {
        await open(operation == 'scan' ? 'run' : 'plan', result['id']);
      }
    } catch (e) {
      failed(ticket, e);
    } finally {
      done(ticket);
    }
  }

  Future<void> repeat(String key) async {
    final ticket = begin('pending'), owner = session;
    try {
      final entry = owner.pendingCompanyEventCommands.firstWhere(
        (entry) => entry.key == key,
      );
      final result = companyEventMap(
        await owner.repeatCompanyEventCommand(
          key,
          stillCurrent: () =>
              alive(ticket) && identical(owner, session) && writable,
        ),
      );
      guard(ticket);
      final operation = companyEventOperation(entry.path);
      await authorize(
        ticket,
        result,
        manager: ['rule', 'scan'].contains(operation),
      );
      guard(ticket);
      if (operation == 'rule') {
        await loadOverview('rules');
      } else {
        await open(operation == 'scan' ? 'run' : 'plan', result['id']);
      }
    } catch (e) {
      failed(ticket, e);
    } finally {
      done(ticket);
    }
  }

  Future<void> decision(String action, Map<String, dynamic> plan) async {
    final original = companyEventMap(jsonDecode(jsonEncode(plan))),
        ticket = begin(action);
    try {
      await authorize(ticket, original, write: true);
      guard(ticket);
      final scope = session.sharedProjectSession(original['project_id']);
      final actor = businessMap(await session.legacyRead('/api/me'));
      guard(ticket);
      if (actor['id'] != original['policy']['responsible_id'] ||
          action != 'execute' && !scope.canWrite('assistant.approve')) {
        throw const ApiException(
          403,
          'Zuständigkeit oder Freigaberecht fehlt.',
        );
      }
      setState(() {
        data = original;
        actorId = actor['id'];
        actorRole = actor['role'];
      });
    } catch (e) {
      failed(ticket, e);
    } finally {
      done(ticket);
    }
  }

  Future<void> openTask(Map<String, dynamic> plan) async {
    final ticket = begin('task');
    try {
      await authorize(ticket, plan);
      guard(ticket);
      final project = plan['project_id'], id = plan['outcome']['result']['id'];
      final value = businessMap(
        await session.legacyRead('/api/projects/$project/tasks/$id'),
      );
      guard(ticket);
      await authorize(ticket, plan);
      guard(ticket);
      if (value['id'] != id || value['project_id'] != project)
        throw const ApiException(
          0,
          'Aufgabe stimmt nicht mit dem Fachvorgang überein.',
        );
      setState(() => data = value);
    } catch (e) {
      failed(ticket, e);
    } finally {
      done(ticket);
    }
  }

  String projectName(dynamic id) =>
      '${session.projects.where((p) => p['id'] == id).firstOrNull?['name'] ?? 'Freigegebenes Projekt'}';
  Widget button(
    String title,
    VoidCallback callback, {
    bool primary = false,
    bool enabled = true,
  }) => primary
      ? FilledButton(
          onPressed: busy || !enabled ? null : callback,
          child: Text(title),
        )
      : TextButton(
          onPressed: busy || !enabled ? null : callback,
          child: Text(title),
        );
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
  Widget fact(String name, String value) => Padding(
    padding: const EdgeInsets.symmetric(vertical: 4),
    child: Text('$name: $value'),
  );
  List<Widget> sourceView(Map<String, dynamic> value) => [
    fact('Original', _sourceTitle(companyEventMap(value['source']))),
    fact('Auslöser', companyEventTriggers[value['trigger']]!),
    fact('Projekt', projectName(value['project_id'])),
    fact('Abfragedatum', businessDate(value['as_of'])),
    for (final e in companyEventMap(value['facts']).entries)
      fact(companyEventFields[e.key]?.$1 ?? e.key, _fact(e.key, e.value)),
    if (value['source_current'] != true)
      const Notice('Dieser Nachweis gehört zu einem früheren Quellenstand.'),
    ExpansionTile(
      title: const Text('Unveränderte Originalquelle ansehen'),
      children: [
        SelectableText(
          const JsonEncoder.withIndent('  ').convert(value['source']['data']),
        ),
        SelectableText('Quellennachweis: ${value['source']['sha256']}'),
      ],
    ),
  ];
  List<Widget> overview() => [
    Wrap(
      spacing: 8,
      children: [
        for (final entry in {
          'plans': 'Aktionspläne',
          'events': 'Originalereignisse',
          if (manage) 'rules': 'Unternehmensregeln',
          if (manage) 'runs': 'Laufhistorie',
        }.entries)
          button(entry.value, () => loadOverview(entry.key)),
      ],
    ),
    if (manage && writable)
      Wrap(
        spacing: 8,
        children: [
          button('Ereignislauf starten', () => startScan(), primary: true),
          button('Unternehmensregel anlegen', () => editRule()),
        ],
      ),
    if (data != null && businessItems(data!).isEmpty)
      const Text('Keine zugänglichen Einträge vorhanden.'),
    if (data != null)
      for (final item in businessItems(data!))
        section(
          tab == 'rules'
              ? '${item['title']}'
              : tab == 'events'
              ? _sourceTitle(companyEventMap(item['source']))
              : tab == 'runs'
              ? 'Ereignislauf ${businessDate(item['as_of'])}'
              : companyEventActions[item['action']]!,
          [
            if (tab == 'rules') ...[
              fact(
                'Fassung',
                '${item['revision']} · ${item['enabled'] == true ? 'Aktiv' : 'Deaktiviert'}',
              ),
              fact('Entscheidung', companyEventModes[item['mode']]!),
              fact('Auslöser', companyEventTriggers[item['trigger']]!),
              Wrap(
                spacing: 8,
                children: [
                  button(
                    'Regelhistorie ansehen',
                    () => open('rule_history', item['id']),
                  ),
                  if (writable)
                    button(
                      'Neue Regelfassung bearbeiten',
                      () => editRule(item),
                    ),
                ],
              ),
            ] else if (tab == 'runs') ...[
              fact(
                'Quellen',
                '${item['scanned_count']} · ${item['complete'] == true ? 'Abfrage vollständig' : 'Abfrage unvollständig'}',
              ),
              button('Ereignislauf öffnen', () => open('run', item['id'])),
            ] else if (tab == 'events') ...[
              fact('Projekt', projectName(item['project_id'])),
              fact('Auslöser', companyEventTriggers[item['trigger']]!),
              button(
                'Originalereignis öffnen',
                () => open('event', item['id']),
              ),
            ] else ...[
              fact('Projekt', projectName(item['project_id'])),
              fact('Status', companyEventStates[item['status']]!),
              button('Ereignisplan öffnen', () => open('plan', item['id'])),
            ],
          ],
        ),
    if (cursor != null) button('Zur ersten Seite', () => loadOverview(tab)),
    if (data?['next_after'] != null)
      button(
        'Weitere Einträge laden',
        () => loadOverview(tab, data!['next_after']),
      ),
  ];
  List<Widget> planView(Map<String, dynamic> value) {
    final scope = session.sharedProjectSession(value['project_id']);
    final own = value['policy']['responsible_id'] == actorId;
    final canDecide =
        own &&
        writable &&
        scope.canWrite('assistant.approve') &&
        value['source_current'] == true &&
        value['decision'] == null &&
        value['execution'] == null &&
        ['awaiting_approval', 'ready'].contains(value['status']) &&
        value['policy']['mode'] != 'deny';
    return [
      Notice(companyEventStates[value['status']]!),
      if (value['blocked'] != null)
        Notice('${value['blocked']['message']}', error: true),
      section('Konkreter Ereignisauftrag', [
        fact('Aktion', companyEventActions[value['action']]!),
        fact('Projekt', projectName(value['project_id'])),
        fact(
          'Zuständigkeit',
          own ? 'Sie' : 'Andere ausdrücklich benannte Person',
        ),
        fact(
          'Unternehmensregel',
          companyEventModes[value['policy']['company_mode']]!,
        ),
        fact(
          'Wirksame Entscheidung',
          companyEventModes[value['policy']['mode']]!,
        ),
        for (final e in companyEventMap(value['parameters'] ?? {}).entries)
          fact(
            {
                  'title': 'Titel',
                  'details': 'Beschreibung',
                  'priority': 'Priorität',
                  'due_date': 'Fällig am',
                  'issue_date': 'Belegdatum',
                  'positions': 'Artikelpositionen',
                }[e.key] ??
                e.key,
            _fact(e.key, e.value),
          ),
      ]),
      if (event != null) section('Belegte Grundlage', sourceView(event!)),
      section('Gebundene Regeln', [
        for (final rule in businessItems(value['policy']['rule_versions']))
          SelectableText(
            'Unternehmensregel · Fassung ${rule['revision']}\n${rule['sha256']}',
          ),
        for (final rule in businessItems(
          value['policy']['project_policies'],
        )) ...[
          fact(
            'Projektregel',
            companyEventModes[rule['policy']['mode']] ??
                'Gebundene Entscheidung',
          ),
          ExpansionTile(
            title: const Text('Unveränderten Projektregelnachweis ansehen'),
            children: [
              SelectableText(rule['original_json']),
              SelectableText(rule['original_sha256']),
            ],
          ),
        ],
      ]),
      if (value['decision'] != null)
        section('Gespeicherte Entscheidung', [
          Text(
            value['decision']['decision'] == 'approved'
                ? 'Freigegeben'
                : 'Abgelehnt',
          ),
          Text('${value['decision']['reason']}'),
          Text(businessDate(value['decision']['created_at'], time: true)),
        ]),
      if (value['execution'] != null)
        section('Tatsächlicher Ausführungsstand', [
          Text(
            companyEventStates[value['outcome']?['status'] ?? 'unconfirmed']!,
          ),
          if (value['outcome']?['status'] == 'succeeded')
            Text(
              '${value['outcome']['result']['title'] ?? value['outcome']['result']['number'] ?? 'Fachvorgang gespeichert'}',
            )
          else
            const Text(
              'Die Aktion wurde bereits beansprucht. Ein ungeklärter Ausgang wird nicht als Erfolg dargestellt oder erneut gestartet.',
            ),
          if (value['outcome']?['status'] == 'succeeded' &&
              value['action'] == 'task.create')
            button('Angelegte Aufgabe ansehen', () => openTask(value)),
        ]),
      if (canDecide)
        Wrap(
          spacing: 8,
          children: [
            button(
              'Diesen Ereignisplan freigeben',
              () => decision('approve', value),
              primary: true,
            ),
            button('Ereignisplan ablehnen', () => decision('reject', value)),
          ],
        ),
      if (own && writable && value['can_execute'] == true)
        button(
          'Freigegebenen Ereignisplan ausführen',
          () => decision('execute', value),
          primary: true,
        ),
    ];
  }

  List<Widget> runView(Map<String, dynamic> value) => [
    section('Ereignislauf', [
      fact('Abfragedatum', businessDate(value['as_of'])),
      fact('Zeitzone', '${value['timezone']}'),
      fact('Geprüfte Quellen', '${value['scanned_count']}'),
      fact(
        'Abfragestatus',
        value['complete'] == true ? 'Vollständig' : 'Unvollständig',
      ),
      const Text(
        'Vollständigkeit der Abfrage und Erfolg einzelner Aktionen sind getrennte Angaben.',
      ),
      for (final issue in businessItems(value['issues']))
        Notice(
          'Eine Quelle konnte nicht vollständig geprüft werden (${issue['status_code']}).',
          error: true,
        ),
      for (final item in businessItems(value['items']))
        Wrap(
          spacing: 8,
          children: [
            button(
              'Beobachtetes Ereignis ansehen',
              () => open('event', item['event_id']),
            ),
            for (final id in item['plan_ids'])
              button('Verknüpften Aktionsplan öffnen', () => open('plan', id)),
          ],
        ),
      if (value['processing'] == null)
        const Notice(
          'Die Verarbeitung dieses angenommenen Laufs ist noch nicht vollständig bestätigt.',
        )
      else
        for (final item in businessItems(value['processing']))
          fact('Gespeicherter Ablauf', companyEventStates[item['status']]!),
      if (value['next_after'] != null && manage && writable)
        button(
          'Nächste Quellen-Seite prüfen',
          () => startScan(value['next_after']),
          primary: true,
        ),
    ]),
  ];
  List<Widget> decisionView(Map<String, dynamic> value) => [
    Text(
      '${companyEventActions[value['action']]} · ${projectName(value['project_id'])}',
    ),
    if (screen != 'execute')
      TextField(
        controller: reason,
        maxLines: 3,
        maxLength: 1000,
        decoration: const InputDecoration(labelText: 'Prüfvermerk'),
        onChanged: (_) => setState(() {}),
      ),
    CheckboxListTile(
      value: confirmed,
      onChanged: (v) => setState(() => confirmed = v == true),
      title: Text(
        screen == 'execute'
            ? 'Ich bestätige die Ausführung dieses konkreten Ereignisplans.'
            : 'Ich habe diesen Ereignisplan, seine Quellen und Zuständigkeit geprüft.',
      ),
    ),
    button(
      screen == 'execute'
          ? 'Konkrete Ereignisaktion ausführen'
          : screen == 'approve'
          ? 'Konkrete Ereignisfreigabe speichern'
          : 'Ereignisplan verbindlich ablehnen',
      () => send('$companyEventBase/plans/${value['id']}/$screen', {
        'plan_sha256': value['sha256'],
        if (screen != 'execute') 'reason': reason.text.trim(),
        'confirmation': true,
      }),
      primary: true,
      enabled:
          confirmed && (screen == 'execute' || reason.text.trim().isNotEmpty),
    ),
  ];

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(title: const Text('Unternehmensereignisse')),
    body: ListView(
      controller: scroll,
      padding: const EdgeInsets.all(16),
      children: [
        const Text(
          'Belegte Ereignisse, ausdrücklich gespeicherte Unternehmensregeln und konkrete Aktionen.',
        ),
        if (background)
          const Notice(
            'Die private Ansicht wurde beim Verlassen der App geschlossen.',
          )
        else if (!readable && !busy)
          const Notice(
            'Unternehmensereignisse sind mit den aktuellen Rechten nicht verfügbar.',
          )
        else ...[
          Wrap(
            spacing: 8,
            children: [
              TextButton(
                onPressed: () => loadOverview(),
                child: const Text('Übersicht aktualisieren'),
              ),
              if (screen != 'overview')
                TextButton(
                  onPressed: () => loadOverview(tab),
                  child: const Text('Zur Übersicht'),
                ),
            ],
          ),
          if (error != null) Notice(error!, error: true),
          if (busy) const LinearProgressIndicator(),
          if (readable)
            for (final operation in session.pendingCompanyEventCommands)
              if (manage ||
                  ![
                    'rule',
                    'scan',
                  ].contains(companyEventOperation(operation.path)))
                section('Unbestätigter Originalauftrag', [
                  const Text(
                    'Die ursprüngliche Anforderung bleibt in dieser Sitzung erhalten. Wiederholen bestätigt denselben Auftrag; es wird keine neue Kennung vergeben.',
                  ),
                  button(
                    'Originalauftrag unverändert erneut senden',
                    () => repeat(operation.key),
                    enabled: writable,
                  ),
                ]),
          if (!busy && readable) ...[
            if (screen == 'overview') ...overview(),
            if (screen == 'plan' && data != null) ...planView(data!),
            if (screen == 'event' && data != null) ...sourceView(data!),
            if (screen == 'run' && data != null) ...runView(data!),
            if (['approve', 'reject', 'execute'].contains(screen) &&
                data != null)
              ...decisionView(data!),
            if (screen == 'scan' && manage && writable) ...[
              const Notice(
                'Gespeicherte Automatikregeln können echte interne Aufgaben oder freigegebene Außenwirkungen auslösen. Der Server prüft den tatsächlichen aktuellen Stand.',
              ),
              CheckboxListTile(
                value: confirmed,
                onChanged: (v) => setState(() => confirmed = v == true),
                title: const Text(
                  'Ich starte die aktuelle Quellenprüfung und bestätige die mögliche Wirkung gespeicherter Automatikregeln.',
                ),
              ),
              button(
                'Ereignislauf verbindlich starten',
                () => send('$companyEventBase/scan', {
                  'limit': 100,
                  'after': scanAfter,
                }),
                primary: true,
                enabled: confirmed,
              ),
            ],
            if (screen == 'rule_history' && data != null)
              for (final rule in businessItems(data!))
                section('${rule['title']} · Fassung ${rule['revision']}', [
                  fact(
                    'Status',
                    rule['enabled'] == true ? 'Aktiv' : 'Deaktiviert',
                  ),
                  fact('Auslöser', companyEventTriggers[rule['trigger']]!),
                  fact('Aktion', companyEventActions[rule['action']]!),
                  fact('Entscheidung', companyEventModes[rule['mode']]!),
                  fact(
                    'Projekte',
                    rule['project_ids'] == null
                        ? 'Alle aktuell erreichbaren Projekte'
                        : (rule['project_ids'] as List)
                              .map(projectName)
                              .join(', '),
                  ),
                  for (final c in businessItems(rule['conditions']))
                    fact(
                      companyEventFields[c['field']]!.$1,
                      '${c['operator']}: ${_fact(c['field'], c['value'])}',
                    ),
                  ExpansionTile(
                    title: const Text('Gespeicherte Vorlage ansehen'),
                    children: [
                      SelectableText(
                        const JsonEncoder.withIndent('  ')
                            .convert(rule['template']),
                      ),
                    ],
                  ),
                ]),
            if (screen == 'task' && data != null)
              section('Aktuelle Aufgabe im Projekt', [
                fact('Titel', '${data!['title']}'),
                fact('Beschreibung', '${data!['details']}'),
                fact('Status', '${data!['status']}'),
                fact('Fällig', businessDate(data!['due_date'])),
              ]),
            if (screen == 'rule_edit' && status != null && manage && writable)
              CompanyEventRuleEditor(
                key: ValueKey(epoch),
                status: status!,
                original: oldRule,
                users: users,
                articles: articles,
                projects: session.projects,
                actorId: actorId!,
                onSave: (values) => send('$companyEventBase/rules', values),
              ),
          ],
        ],
      ],
    ),
  );
}

class CompanyEventRuleEditor extends StatefulWidget {
  const CompanyEventRuleEditor({
    super.key,
    required this.status,
    required this.original,
    required this.users,
    required this.articles,
    required this.projects,
    required this.actorId,
    required this.onSave,
  });
  final Map<String, dynamic> status;
  final Map<String, dynamic>? original;
  final List<Map<String, dynamic>> users, articles, projects;
  final String actorId;
  final Future<void> Function(Map<String, dynamic>) onSave;
  @override
  State<CompanyEventRuleEditor> createState() => _CompanyEventRuleEditorState();
}

class _CompanyEventRuleEditorState extends State<CompanyEventRuleEditor> {
  late String id, trigger, action, mode, responsible;
  late bool enabled, allProjects;
  bool confirmation = false;
  final selectedProjects = <String>{}, text = <String, String>{};
  final conditions = <Map<String, dynamic>>[],
      positions = <Map<String, dynamic>>[];
  String? error;
  @override
  void initState() {
    super.initState();
    final old = widget.original;
    id = old?['id'] ?? offlineId();
    trigger = old?['trigger'] ?? 'task.overdue';
    action = old?['action'] ?? 'task.create';
    mode = old?['mode'] ?? 'approval';
    responsible = old?['responsible_id'] ?? widget.actorId;
    enabled = old?['enabled'] ?? true;
    allProjects = old?['project_ids'] == null;
    if (old?['project_ids'] != null)
      selectedProjects.addAll((old!['project_ids'] as List).cast<String>());
    text['title'] = old?['title'] ?? '';
    final template = businessMap(old?['template']);
    text['template_title'] = template['title'] ?? '';
    text['details'] = template['details'] ?? '';
    text['due_days'] = '${template['due_days'] ?? ''}';
    text['priority'] = template['priority'] ?? 'normal';
    for (final c in businessItems(old?['conditions'] ?? []))
      conditions.add({
        ...c,
        'editor_id': offlineId(),
        'value': '${c['field']}'.endsWith('_minor')
            ? companyEventMoneyInput(c['value'])
            : c['value'] is bool
            ? (c['value'] ? 'Ja' : 'Nein')
            : '${c['value']}',
      });
    for (final p in businessItems(template['positions'] ?? []))
      positions.add({...p, 'editor_id': offlineId()});
  }

  Widget field(String name, String label, {int lines = 1}) => Padding(
    padding: const EdgeInsets.symmetric(vertical: 6),
    child: TextFormField(
      key: ValueKey('$name-$action'),
      initialValue: text[name] ?? '',
      maxLines: lines,
      decoration: InputDecoration(labelText: label),
      onChanged: (v) => text[name] = v,
    ),
  );
  Widget select(
    String label,
    String value,
    Map<String, String> values,
    void Function(String) change,
  ) => Padding(
    padding: const EdgeInsets.symmetric(vertical: 6),
    child: DropdownButtonFormField<String>(
      key: ValueKey('$label-$value'),
      initialValue: values.containsKey(value) ? value : null,
      isExpanded: true,
      decoration: InputDecoration(labelText: label),
      items: [
        for (final e in values.entries)
          DropdownMenuItem(
            value: e.key,
            child: Text(e.value, overflow: TextOverflow.ellipsis),
          ),
      ],
      onChanged: (v) {
        if (v != null) setState(() => change(v));
      },
    ),
  );
  Map<String, String> get actionOptions => {
    for (final a in businessItems(widget.status['actions']))
      if ((a['triggers'] as List).contains(trigger))
        '${a['action']}': companyEventActions[a['action']]!,
  };
  Future<void> save() async {
    try {
      if (!confirmation || text['title']!.trim().isEmpty)
        throw const ApiException(
          0,
          'Regelbezeichnung und ausdrückliche Bestätigung erforderlich.',
        );
      if (!allProjects && selectedProjects.isEmpty)
        throw const ApiException(
          0,
          'Mindestens ein betroffenes Projekt auswählen.',
        );
      if (!actionOptions.containsKey(action))
        throw const ApiException(
          0,
          'Aktion und Auslöser passen nicht zusammen.',
        );
      Map<String, dynamic> template = {};
      if (['task.create', 'offer.draft'].contains(action)) {
        final due = text['due_days']!.trim(),
            days = due.isEmpty ? null : int.tryParse(due);
        if ((due.isNotEmpty && (days == null || days < 0 || days > 365)) ||
            action == 'offer.draft' && days == null ||
            text['template_title']!.trim().isEmpty)
          throw const ApiException(
            0,
            'Vorlagentitel und Fälligkeit von 0 bis 365 Tagen prüfen.',
          );
        if (action == 'task.create') {
          template = {
            'title': text['template_title']!.trim(),
            'details': text['details']!.trim(),
            'priority': text['priority'],
            'due_days': days,
          };
        } else {
          final selected = <Map<String, dynamic>>[];
          for (final p in positions) {
            final article = widget.articles
                    .where((a) => a['id'] == p['article_id'])
                    .firstOrNull,
                quantity = '${p['quantity'] ?? ''}'.trim().replaceAll(',', '.');
            if (article == null ||
                article['active'] != true ||
                article['price_policy'] == 'dated_catalog' ||
                !RegExp(r'^\d{1,6}(?:\.\d{1,4})?$').hasMatch(quantity) ||
                !RegExp('[1-9]').hasMatch(quantity))
              throw const ApiException(
                0,
                'Aktiven Artikel mit unterstützter Preisquelle und positiver Menge wählen.',
              );
            selected.add({
              'article_id': article['id'],
              'article_revision': article['revision'],
              'quantity': quantity,
            });
          }
          if (selected.isEmpty || selected.length > 6)
            throw const ApiException(
              0,
              'Eine bis sechs Artikelpositionen erforderlich.',
            );
          template = {
            'title': text['template_title']!.trim(),
            'due_days': days,
            'positions': selected,
          };
        }
      }
      await widget.onSave({
        'id': id,
        'revision': widget.original?['revision'] ?? 0,
        'title': text['title']!.trim(),
        'enabled': enabled,
        'project_ids': allProjects ? null : (selectedProjects.toList()..sort()),
        'trigger': trigger,
        'action': action,
        'mode': mode,
        'conditions': companyEventConditions(
          trigger,
          conditions,
          widget.status,
        ),
        'template': template,
        'responsible_id': responsible,
        'confirmation': true,
      });
    } catch (e) {
      if (mounted)
        setState(
          () => error = e is ApiException
              ? e.message
              : 'Regel konnte nicht bestätigt werden.',
        );
    }
  }

  @override
  Widget build(BuildContext context) {
    final fields = companyEventMap(widget.status['condition_fields'][trigger]);
    final current = businessItems(widget.status['actions'])
        .where((a) => a['action'] == action)
        .first;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          widget.original == null
              ? 'Unternehmensregel anlegen'
              : 'Neue Unternehmensregelfassung',
          style: Theme.of(context).textTheme.titleLarge,
        ),
        const Text(
          'Eine neue Fassung erhält alle bisherigen Regeln und Nachweise. Verbote und bestehende Projektregeln behalten Vorrang.',
        ),
        field('title', 'Regelbezeichnung'),
        SwitchListTile(
          value: enabled,
          onChanged: (v) => setState(() => enabled = v),
          title: const Text('Regel aktiv'),
        ),
        select('Auslöser', trigger, companyEventTriggers, (v) {
          trigger = v;
          conditions.clear();
          if (!actionOptions.containsKey(action)) action = 'task.create';
          confirmation = false;
        }),
        select('Aktion', action, actionOptions, (v) {
          action = v;
          positions.clear();
          text['template_title'] = '';
          text['details'] = '';
          text['due_days'] = '';
          confirmation = false;
        }),
        if (current['executable'] != true)
          const Notice(
            'Für diese Aktion ist kein ausführender Adapter vorhanden. Es wird keine erfolgreiche Zahlung angenommen.',
          ),
        select('Regelentscheidung', mode, companyEventModes, (v) => mode = v),
        select('Zuständige Person', responsible, {
          for (final user in widget.users)
            '${user['id']}':
                '${user['email'] ?? user['name'] ?? 'Benannte Person'}',
          if (!widget.users.any((u) => u['id'] == responsible))
            responsible: 'Bisherige belegte Zuständigkeit',
        }, (v) => responsible = v),
        SwitchListTile(
          value: allProjects,
          onChanged: (v) => setState(() => allProjects = v),
          title: const Text('Alle aktuell erreichbaren Projekte'),
        ),
        if (!allProjects)
          for (final project in widget.projects)
            CheckboxListTile(
              value: selectedProjects.contains(project['id']),
              onChanged: (v) => setState(() {
                if (v == true) {
                  selectedProjects.add(project['id']);
                } else {
                  selectedProjects.remove(project['id']);
                }
              }),
              title: Text('${project['name']}'),
            ),
        const SizedBox(height: 12),
        const Text('Belegte Bedingungen'),
        for (final condition in conditions)
          Card(
            key: ValueKey(condition['editor_id']),
            child: Padding(
              padding: const EdgeInsets.all(12),
              child: Column(
                children: [
                  select(
                    'Ereignisfakt',
                    '${condition['field']}',
                    {
                      for (final field in fields.keys)
                        field: companyEventFields[field]!.$1,
                    },
                    (v) {
                      condition['field'] = v;
                      condition['value'] = '';
                      condition['operator'] = 'eq';
                    },
                  ),
                  select('Bedingungsvergleich', '${condition['operator']}', {
                    'eq': 'Ist gleich',
                    if (fields[condition['field']] == 'int' ||
                        '${condition['field']}'.endsWith('_minor'))
                      'gte': 'Mindestens',
                    if (fields[condition['field']] == 'int' ||
                        '${condition['field']}'.endsWith('_minor'))
                      'lte': 'Höchstens',
                  }, (v) => condition['operator'] = v),
                  TextFormField(
                    key: ValueKey(
                      '${condition['editor_id']}-${condition['field']}',
                    ),
                    initialValue: '${condition['value']}',
                    decoration: const InputDecoration(
                      labelText:
                          'Bedingungswert (EUR, Tage, Text oder Ja/Nein)',
                    ),
                    onChanged: (v) => condition['value'] = v,
                  ),
                  TextButton(
                    onPressed: () =>
                        setState(() => conditions.remove(condition)),
                    child: const Text('Bedingung entfernen'),
                  ),
                ],
              ),
            ),
          ),
        TextButton(
          onPressed: conditions.length >= 8
              ? null
              : () => setState(
                  () => conditions.add({
                    'editor_id': offlineId(),
                    'field': fields.keys.first,
                    'operator': 'eq',
                    'value': '',
                  }),
                ),
          child: const Text('Bedingung hinzufügen'),
        ),
        if (['task.create', 'offer.draft'].contains(action)) ...[
          field(
            'template_title',
            action == 'task.create' ? 'Aufgabentitel' : 'Angebotstitel',
          ),
          field(
            'due_days',
            action == 'task.create'
                ? 'Fällig nach Tagen (leer: ohne Datum)'
                : 'Fällig nach Tagen',
          ),
          if (action == 'task.create') ...[
            field('details', 'Feste Aufgabenbeschreibung', lines: 3),
            select('Priorität', text['priority']!, {
              'normal': 'Normal',
              'high': 'Hoch',
            }, (v) => text['priority'] = v),
          ],
          if (action == 'offer.draft') ...[
            const Text(
              'Artikel und Fassung ausdrücklich auswählen. Preise werden aus der bestätigten Quelle geprüft.',
            ),
            for (final p in positions)
              Card(
                key: ValueKey(p['editor_id']),
                child: Padding(
                  padding: const EdgeInsets.all(12),
                  child: Column(
                    children: [
                      select('Artikelposition', '${p['article_id'] ?? ''}', {
                        for (final a in widget.articles)
                          if (a['active'] == true &&
                              a['price_policy'] != 'dated_catalog')
                            '${a['id']}':
                                '${a['name']} · Fassung ${a['revision']}',
                      }, (v) => p['article_id'] = v),
                      TextFormField(
                        initialValue: '${p['quantity'] ?? ''}',
                        decoration: const InputDecoration(labelText: 'Menge'),
                        onChanged: (v) => p['quantity'] = v,
                      ),
                      TextButton(
                        onPressed: () => setState(() => positions.remove(p)),
                        child: const Text('Position entfernen'),
                      ),
                    ],
                  ),
                ),
              ),
            TextButton(
              onPressed: positions.length >= 6
                  ? null
                  : () => setState(
                      () => positions.add({
                        'editor_id': offlineId(),
                        'article_id': '',
                        'quantity': '',
                      }),
                    ),
              child: const Text('Artikelposition hinzufügen'),
            ),
          ],
        ],
        CheckboxListTile(
          value: confirmation,
          onChanged: (v) => setState(() => confirmation = v == true),
          title: const Text(
            'Ich bestätige diese Unternehmensregel, ihre Zuständigkeit und zulässige Wirkung.',
          ),
        ),
        if (error != null) Notice(error!, error: true),
        FilledButton(
          onPressed: confirmation ? save : null,
          child: const Text('Neue Unternehmensregelfassung speichern'),
        ),
      ],
    );
  }
}

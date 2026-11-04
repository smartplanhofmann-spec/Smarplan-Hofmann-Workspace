import 'dart:async';
import 'dart:convert';

import 'package:flutter/material.dart';

import 'api.dart';
import 'business_session.dart';
import 'business_company_events.dart';
import 'business_speech.dart';
import 'business_widgets.dart';
import 'design.dart';
import 'offline_vault.dart' show offlineId;

const assistantActions = {
  'task.create': 'Aufgabe anlegen',
  'offer.draft': 'Angebot entwerfen',
  'document.email': 'Finalen Beleg versenden',
  'dunning.email': 'Vorbereitete Mahnung versenden',
  'supplier.order': 'Lieferantenbestellung ausführen',
  'payment.execute': 'Zahlung ausführen',
};
const assistantModes = {
  'deny': 'Verboten',
  'approval': 'Freigabe erforderlich',
  'auto': 'Automatisch erlaubt',
};
const assistantTriggers = {
  'manual': 'Manueller Auftrag',
  'payment.overdue': 'Überfällige Zahlung',
  'task.overdue': 'Überfällige Aufgabe',
  'cost.threshold': 'Belegte Kostenschwelle',
};
const assistantKinds = {
  'project': 'Projekt',
  'task': 'Aufgabe',
  'open_item': 'Offener Posten',
  'costs': 'Projektkosten',
  'communication': 'Kommunikation',
  'document': 'Beleg',
  'dunning': 'Mahnung',
  'purchase': 'Bestellung',
  'article': 'Artikel / Leistung',
};
const assistantStates = {
  'denied': 'Durch Regeln verboten',
  'awaiting_approval': 'Freigabe offen',
  'ready': 'Bereit',
  'rejected': 'Abgelehnt',
  'stale': 'Quellen oder Regeln geändert',
  'adapter_blocked': 'Ausführender Adapter fehlt',
  'suspended_after_restore': 'Nach Wiederherstellung gesperrt',
  'succeeded': 'Erfolgreich ausgeführt',
  'failed': 'Fehlgeschlagen',
  'unknown': 'Ausgang unklar',
  'blocked': 'Fachlich gesperrt',
  'unconfirmed': 'Antwort offen',
};
const _facts = {
  'overdue_payment': ('Überfällige Zahlung', 'boolean'),
  'payment_overdue_days': ('Zahlungsverzug in Tagen', 'integer'),
  'open_minor': ('Offener Betrag in EUR', 'money'),
  'overdue_task': ('Überfällige Aufgabe', 'boolean'),
  'task_overdue_days': ('Aufgabenverzug in Tagen', 'integer'),
  'total_cost_minor': ('Erfasste Gesamtkosten in EUR', 'money'),
  'costs_complete': ('Kostenquellen vollständig', 'boolean'),
};
String _date() => DateTime.now().toIso8601String().substring(0, 10);
String _sourceTitle(Map<String, dynamic> source) {
  final data = businessMap(source['data']);
  return '${data['title'] ?? data['name'] ?? data['number'] ?? data['subject'] ?? assistantKinds[source['descriptor']['kind']] ?? 'Fachquelle'}';
}

List<Map<String, dynamic>> assistantOfferPositions(
  Map<String, dynamic> context,
  Map<String, dynamic> values,
) {
  final sources = businessItems(context['sources']);
  if (!sources.any(
    (row) =>
        row['descriptor']['kind'] == 'project' &&
        row['descriptor']['id'] == context['project_id'],
  ))
    throw const FormatException(
      'Die Projektquelle zusätzlich zu den Artikeln auswählen.',
    );
  final result = <Map<String, dynamic>>[];
  for (final source in sources.where(
    (row) => row['descriptor']['kind'] == 'article',
  )) {
    final id = '${source['descriptor']['id']}',
        amount = '${values[id] ?? ''}'.trim().replaceAll(',', '.');
    if (amount.isEmpty || amount == '0') continue;
    if (!RegExp(r'^\d{1,6}(?:\.\d{1,4})?$').hasMatch(amount) ||
        RegExp(r'^0*(?:\.0*)?$').hasMatch(amount) ||
        source['data']['active'] != true ||
        source['data']['revision'] is! int)
      throw const FormatException(
        'Positive Menge und eine aktuelle aktive Artikelfassung erforderlich.',
      );
    result.add({
      'article_id': id,
      'article_revision': source['data']['revision'],
      'quantity': amount,
    });
  }
  if (result.isEmpty)
    throw const FormatException(
      'Mindestens eine ausgewählte Artikelposition mit Menge erfassen.',
    );
  return result;
}

List<Map<String, dynamic>> assistantConditions(
  List<Map<String, dynamic>> rows,
) {
  if (rows.length > 8)
    throw const FormatException('Höchstens acht Bedingungen erfassen.');
  return [for (final row in rows) _condition(row)];
}

Map<String, dynamic> _condition(Map<String, dynamic> row) {
  final type = _facts[row['field']]?.$2;
  if (type == null || !['eq', 'gte', 'lte'].contains(row['operator']))
    throw const FormatException('Eine unterstützte Regelbedingung auswählen.');
  dynamic value;
  final input = '${row['value']}'.trim().replaceAll(',', '.');
  if (type == 'boolean') {
    final normalized = input.toLowerCase();
    if (row['operator'] != 'eq' ||
        !['true', 'false', 'ja', 'nein'].contains(normalized))
      throw const FormatException('Ja/Nein nur auf Gleichheit prüfen.');
    value = ['true', 'ja'].contains(normalized);
  } else if (type == 'money') {
    if (!RegExp(r'^-?\d{1,12}(?:\.\d{1,2})?$').hasMatch(input))
      throw const FormatException(
        'EUR-Betrag mit höchstens zwei Nachkommastellen eingeben.',
      );
    final parts = input.replaceFirst('-', '').split('.');
    value =
        (int.parse(parts[0]) * 100 +
            int.parse((parts.length > 1 ? parts[1] : '').padRight(2, '0'))) *
        (input.startsWith('-') ? -1 : 1);
  } else {
    if (!RegExp(r'^-?\d{1,15}$').hasMatch(input))
      throw const FormatException('Ganze Tageszahl eingeben.');
    value = int.parse(input);
  }
  if (value is int && value.abs() > 1000000000000000)
    throw const FormatException('Vergleichswert zu groß.');
  return {'field': row['field'], 'operator': row['operator'], 'value': value};
}

Map<String, dynamic> assistantAnswerValues(
  Map<String, dynamic> context,
  Map<String, dynamic> chat,
) {
  final answer = businessMap(chat['result']);
  if (chat['context_id'] != context['id'] ||
      chat['project_id'] != context['project_id'] ||
      chat['status'] != 'completed' ||
      answer['response_type'] != 'source_answer' ||
      answer['business_values'] != 'resolved_from_selected_sources' ||
      answer['actions_executed_by_model'] != false)
    throw const FormatException(
      'Keine bestätigte quellgebundene Antwort verfügbar.',
    );
  final sources = {
    for (final source in businessItems(context['sources']))
      '${source['source_id']}': source,
  };
  final citations = answer['citations'];
  if (citations is! List ||
      citations.isEmpty ||
      citations.toSet().length != citations.length ||
      citations.any((id) => !sources.containsKey(id)))
    throw const FormatException(
      'Die Antwort verweist auf eine nicht ausgewählte Quelle.',
    );
  for (final fact in businessItems(answer['facts'])) {
    final path = '${fact['path']}';
    if (!citations.contains(fact['source_id']) ||
        !RegExp(r'^[a-z][a-z0-9_]*(?:\.(?:[a-z][a-z0-9_]*|\d{1,3})){0,6}$')
            .hasMatch(path))
      throw const FormatException('Der Faktennachweis ist ungültig.');
    dynamic value = sources[fact['source_id']]!['data'];
    for (final part in path.split('.')) {
      if (value is Map && value.containsKey(part)) {
        value = value[part];
      } else if (value is List &&
          int.tryParse(part) != null &&
          int.parse(part) < value.length) {
        value = value[int.parse(part)];
      } else {
        throw const FormatException('Der angegebene Fakt fehlt in der Quelle.');
      }
    }
    if (value != null && value is! String && value is! bool && value is! int ||
        jsonEncode(value) != jsonEncode(fact['value']))
      throw const FormatException(
        'Die Antwort stimmt nicht mit dem ausgewählten Beleg überein.',
      );
  }
  return answer;
}

void assistantReceipt(
  String path,
  String project,
  Map<String, dynamic> values,
  dynamic raw,
) {
  final result = businessMap(raw);
  if (!RegExp(r'^[a-f0-9]{32}$').hasMatch('${result['id'] ?? ''}') ||
      result['project_id'] != project)
    throw const ApiException(
      0,
      'Die Assistentenantwort bestätigt das ursprüngliche Projekt nicht.',
    );
  if (path == '/assistant/contexts') {
    final expected = businessItems(
      values['sources'],
    ).map((row) => '${row['kind']}:${row['id']}').toList()..sort();
    final received = businessItems(
      result['sources'],
    ).map((row) => '${row['source_id']}').toList()..sort();
    if (!RegExp(r'^[a-f0-9]{64}$').hasMatch('${result['sha256'] ?? ''}') ||
        jsonEncode(expected) != jsonEncode(received))
      throw const ApiException(
        0,
        'Die Antwort bestätigt die ausgewählten Quellen nicht.',
      );
  } else if (path == '/assistant/rules') {
    if (result['id'] != values['id'] ||
        result['revision'] != values['revision'] + 1)
      throw const ApiException(
        0,
        'Die Antwort bestätigt die Regelfassung nicht.',
      );
  } else if (path == '/assistant/plans' || path == '/assistant/chat') {
    if (result['context_id'] != values['context_id'] ||
        result['status'] is! String)
      throw const ApiException(
        0,
        'Die Antwort bestätigt die ursprüngliche Datenbasis nicht.',
      );
    if (path == '/assistant/plans' &&
        (result['action'] != values['action'] ||
            !assistantModes.containsKey(result['policy']?['mode']) ||
            !RegExp(r'^[a-f0-9]{64}$').hasMatch('${result['sha256'] ?? ''}')))
      throw const ApiException(
        0,
        'Die Antwort bestätigt die konkrete Regelentscheidung nicht.',
      );
  } else {
    final match = RegExp(
      r'^/assistant/plans/([a-f0-9]{32})/(?:approve|reject|execute)$',
    ).firstMatch(path);
    if (match == null ||
        result['id'] != match.group(1) ||
        result['sha256'] != values['plan_sha256'])
      throw const ApiException(
        0,
        'Die Antwort bestätigt diesen konkreten Auftrag nicht.',
      );
  }
}

class _AssistantMemory {
  String? contextId;
  final pending = <String, ({String path, String title})>{};
}

final _memory = Expando<_AssistantMemory>();

class BusinessAssistantPage extends StatefulWidget {
  const BusinessAssistantPage({super.key, required this.session});
  final BusinessSession session;
  @override
  State<BusinessAssistantPage> createState() => _BusinessAssistantPageState();
}

class _BusinessAssistantPageState extends State<BusinessAssistantPage>
    with WidgetsBindingObserver {
  BusinessSession? scope;
  String? project, userId, error;
  int epoch = 0, foregroundEpoch = 0, sourceOffset = 0, sourceTotal = 0;
  int? nextSourceOffset;
  String sourceQuery = '', speechDraft = '';
  Map<String, dynamic>? speechStatus;
  bool busy = false, foreground = true;
  final privateDialogs = <DialogRoute<dynamic>>[];
  Set<String> loadedPermissions = {}, loadedParentPermissions = {};
  Object? loadedGeneration, loadedParentGeneration;
  Map<String, dynamic>? status, contextValue;
  List<Map<String, dynamic>> sources = [], rules = [], plans = [], chats = [];
  _AssistantMemory get memory => _memory[scope!] ??= _AssistantMemory();
  bool get readable =>
      foreground &&
      scope != null &&
      scope!.hasFeature('assistant_workflow') &&
      scope!.hasModule('assistant') &&
      scope!.can('assistant.use') &&
      widget.session.allowed;
  bool get writable => readable && scope!.canWrite('assistant.use');
  bool canAction(String action) =>
      readable &&
      switch (action) {
        'task.create' => scope!.can('projects.manage'),
        'offer.draft' =>
          scope!.can('finance.read') && scope!.can('finance.write'),
        'supplier.order' =>
          scope!.can('inventory.read') &&
              scope!.can('inventory.write') &&
              scope!.can('finance.approve'),
        _ => scope!.can('finance.read') && scope!.can('finance.approve'),
      };
  @override
  void initState() {
    super.initState();
    widget.session.addListener(changed);
    WidgetsBinding.instance.addObserver(this);
    if (widget.session.projectId != null) select(widget.session.projectId!);
  }

  @override
  void didUpdateWidget(covariant BusinessAssistantPage oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (!identical(oldWidget.session, widget.session)) {
      oldWidget.session.removeListener(changed);
      if (!identical(scope, oldWidget.session)) scope?.removeListener(changed);
      scope = null;
      project = null;
      erase();
      dismissPrivateDialogs(afterBuild: true);
      widget.session.addListener(changed);
      if (widget.session.projectId != null) {
        unawaited(select(widget.session.projectId!));
      }
    }
  }

  @override
  void dispose() {
    epoch++;
    dismissPrivateDialogs(afterBuild: true);
    WidgetsBinding.instance.removeObserver(this);
    widget.session.removeListener(changed);
    if (scope != widget.session) scope?.removeListener(changed);
    super.dispose();
  }

  void erase() {
    epoch++;
    loadedGeneration = loadedParentGeneration = null;
    loadedPermissions = {};
    loadedParentPermissions = {};
    sources = [];
    rules = [];
    plans = [];
    chats = [];
    status = contextValue = speechStatus = null;
    userId = error = null;
    sourceOffset = sourceTotal = 0;
    nextSourceOffset = null;
    sourceQuery = speechDraft = '';
    busy = false;
  }

  void dismissPrivateDialogs({bool afterBuild = false}) {
    final routes = privateDialogs.toList().reversed.toList();
    privateDialogs.clear();
    void remove() {
      for (final route in routes) {
        if (route.isActive) route.navigator?.removeRoute(route);
      }
    }

    if (afterBuild && routes.isNotEmpty) {
      WidgetsBinding.instance.addPostFrameCallback((_) => remove());
    } else {
      remove();
    }
  }

  Future<T?> privateDialog<T>({
    required WidgetBuilder builder,
    bool barrierDismissible = true,
  }) async {
    guard();
    final route = DialogRoute<T>(
      context: context,
      builder: builder,
      barrierDismissible: barrierDismissible,
    );
    privateDialogs.add(route);
    try {
      return await Navigator.of(context, rootNavigator: true).push(route);
    } finally {
      privateDialogs.remove(route);
    }
  }

  bool Function() currentView() {
    final session = scope,
        parent = widget.session,
        selected = project,
        current = epoch;
    return () =>
        mounted &&
        identical(scope, session) &&
        identical(widget.session, parent) &&
        project == selected &&
        epoch == current &&
        readable;
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state == AppLifecycleState.resumed) {
      foreground = true;
    } else if (state == AppLifecycleState.hidden ||
        state == AppLifecycleState.paused ||
        state == AppLifecycleState.detached) {
      foreground = false;
      foregroundEpoch++;
      erase();
      dismissPrivateDialogs();
    }
    if (mounted) setState(() {});
  }

  void changed() {
    if (!mounted) return;
    if (!readable ||
        (loadedGeneration != null &&
            (scope!.generation != loadedGeneration ||
                widget.session.generation != loadedParentGeneration ||
                !widget.session.permissions.containsAll(
                  loadedParentPermissions,
                ) ||
                !scope!.permissions.containsAll(loadedPermissions)))) {
      erase();
      dismissPrivateDialogs();
    }
    setState(() {});
  }

  void guard([bool write = false]) {
    if (!mounted || !readable || (write && !writable))
      throw const ApiException(
        403,
        'Die aktuellen Projekt- und Assistentenrechte fehlen.',
      );
  }

  Future<void> select(String id) async {
    dismissPrivateDialogs();
    if (scope != widget.session) scope?.removeListener(changed);
    erase();
    project = id;
    sourceOffset = 0;
    sourceQuery = '';
    speechDraft = '';
    speechStatus = null;
    scope = widget.session.sharedProjectSession(id);
    if (scope != widget.session) scope!.addListener(changed);
    sources = [];
    rules = [];
    plans = [];
    chats = [];
    status = null;
    contextValue = null;
    setState(() => busy = true);
    await load();
  }

  Future<void> load() async {
    final session = scope,
        parent = widget.session,
        startedForeground = foregroundEpoch;
    if (session == null) return;
    epoch++;
    int? current;
    bool ownsRequest() =>
        mounted &&
        identical(session, scope) &&
        identical(parent, widget.session) &&
        foreground &&
        startedForeground == foregroundEpoch &&
        (current == null || current == epoch);
    setState(() {
      busy = true;
      error = null;
    });
    try {
      await session.load();
      if (!ownsRequest()) return;
      if (!readable) {
        setState(
          () => error =
              'Dieses Projekt ist für den Assistenten nicht freigegeben.',
        );
        return;
      }
      current = epoch;
      final actorId = '${businessMap(await session.api.call('/api/me'))['id']}';
      if (!ownsRequest() || !readable) return;
      final query = Uri(queryParameters: {'project_id': project!}).query;
      final result = await Future.wait(
        [
          '/assistant/status?$query',
          '/assistant/sources?$query&${Uri(queryParameters: {'q': sourceQuery, 'offset': '$sourceOffset'}).query}',
          '/assistant/rules?$query',
          '/assistant/plans?$query',
          '/assistant/chat?$query',
          if (session.hasFeature('assistant_speech') &&
              session.hasModule('assistant_speech'))
            '/assistant/speech/status?$query',
        ].map(session.read),
      );
      if (!ownsRequest() || !readable) return;
      Map<String, dynamic>? context;
      if (memory.contextId != null) {
        try {
          context = await freshContext(memory.contextId!);
        } on ApiException catch (e) {
          if (!ownsRequest() || !readable) return;
          if (![403, 404, 409].contains(e.status)) rethrow;
          memory.contextId = null;
        }
      }
      if (!ownsRequest() || !readable) return;
      setState(() {
        userId = actorId;
        loadedGeneration = session.generation;
        loadedPermissions = Set.of(session.permissions);
        loadedParentPermissions = Set.of(widget.session.permissions);
        loadedParentGeneration = widget.session.generation;
        status = businessMap(result[0]);
        sources = businessItems(businessMap(result[1])['items']);
        sourceTotal = businessMap(result[1])['total'] as int? ?? sources.length;
        nextSourceOffset = businessMap(result[1])['next_offset'] as int?;
        rules = businessItems(businessMap(result[2])['items']);
        plans = businessItems(businessMap(result[3])['items']);
        chats = businessItems(businessMap(result[4])['items']);
        speechStatus = result.length > 5 ? businessMap(result[5]) : null;
        contextValue = context;
      });
    } catch (e) {
      if (ownsRequest()) setState(() => error = '$e');
    } finally {
      if (ownsRequest()) {
        setState(() => busy = false);
      }
    }
  }

  Future<Map<String, dynamic>> freshContext(String id) async {
    guard();
    final valid = currentView(), session = scope!;
    final selected = project;
    final result = businessMap(await session.read('/assistant/contexts/$id'));
    guard();
    if (!valid() || selected != project || result['project_id'] != project)
      throw const ApiException(
        403,
        'Die Datenbasis gehört zu einem anderen Projekt.',
      );
    return result;
  }

  Future<dynamic> command(
    String key,
    String path,
    Map<String, dynamic> values,
    String title,
  ) async {
    guard(true);
    final session = scope!, selected = project!, valid = currentView();
    memory.pending[key] = (path: path, title: title);
    final dynamic result = session.pending(key)
        ? await session.repeatAssistantCommand(key, selected)
        : await session.command(
            key,
            path,
            values,
            validateResult: (result) =>
                assistantReceipt(path, selected, values, result),
          );
    if (!valid()) return null;
    if (!session.pending(key)) memory.pending.remove(key);
    if (path == '/assistant/contexts') {
      final row = businessMap(result);
      if (row['project_id'] != selected)
        throw const ApiException(403, 'Falsche Projektbindung der Antwort.');
      memory.contextId = '${row['id']}';
      speechDraft = '';
    }
    return result;
  }

  Future<void> repeat(String key) async {
    guard(true);
    final session = scope!,
        entry = memory.pending[key],
        selected = project!,
        valid = currentView();
    setState(() => busy = true);
    try {
      final result = await session.repeatAssistantCommand(key, selected);
      if (!valid()) return;
      if (entry?.path == '/assistant/contexts')
        memory.contextId = '${businessMap(result)['id']}';
      memory.pending.remove(key);
      await load();
    } catch (e) {
      if (valid()) setState(() => error = '$e');
    } finally {
      if (mounted && session == scope) setState(() => busy = false);
    }
  }

  Future<dynamic> editor(
    String title,
    String key,
    String path,
    List<BusinessField> fields,
    Map<String, dynamic> Function(Map<String, dynamic>) body, {
    String permission = 'assistant.use',
  }) async {
    guard(true);
    final session = scope!,
        selected = project,
        parent = widget.session,
        valid = currentView();
    dynamic result;
    await privateDialog<bool>(
      barrierDismissible: false,
      builder: (_) => BusinessEditor(
        session: session,
        title: title,
        fields: fields,
        pendingKey: key,
        readPermission: 'assistant.use',
        writePermission: permission,
        readAllowed: () => valid() && project == selected,
        saveLabel: title,
        onSave: (values) async {
          if (!valid())
            throw const ApiException(
              403,
              'Die ursprüngliche Sitzung wurde geändert.',
            );
          guard(true);
          result = await command(
            key,
            path,
            session.pendingCommandValues(key, path: path) ?? body(values),
            title,
          );
        },
      ),
    );
    if (!valid()) return null;
    await load();
    return mounted &&
            identical(session, scope) &&
            identical(parent, widget.session) &&
            readable
        ? result
        : null;
  }

  Future<void> searchSources() async {
    guard();
    final session = scope, selected = project, valid = currentView();
    var text = sourceQuery;
    final query = await privateDialog<String>(
      builder: (dialogContext) => AlertDialog(
        title: const Text('Quellen durchsuchen'),
        content: TextFormField(
          initialValue: text,
          onChanged: (value) => text = value,
          maxLength: 200,
          decoration: const InputDecoration(
            labelText: 'Quellenbezeichnung oder Kennung',
          ),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(dialogContext),
            child: const Text('Abbrechen'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(dialogContext, text.trim()),
            child: const Text('Quellen suchen'),
          ),
        ],
      ),
    );
    if (query == null || !valid() || scope != session || project != selected)
      return;
    guard();
    sourceQuery = query;
    sourceOffset = 0;
    await load();
  }

  Future<void> chooseSources() async {
    guard(true);
    final choices = {
      for (final source in sources)
        '${source['kind']}:${source['id']}':
            '${assistantKinds[source['kind']]} · ${source['title']}',
    };
    final descriptors = {
      for (final source in sources)
        '${source['kind']}:${source['id']}': {
          'kind': source['kind'],
          'id': source['id'],
        },
    };
    for (final source in businessItems(contextValue?['sources'] ?? [])) {
      choices.putIfAbsent(
        '${source['source_id']}',
        () =>
            '${assistantKinds[source['descriptor']['kind']]} · ${_sourceTitle(source)}',
      );
      descriptors.putIfAbsent(
        '${source['source_id']}',
        () => businessMap(source['descriptor']),
      );
    }

    await editor(
      'Datenbasis verbindlich auswählen',
      'assistant-context-$project',
      '/assistant/contexts',
      [
        BusinessField(
          'sources',
          'Ausgewählte Belege und Fachquellen',
          type: BusinessInput.multiple,
          initial: businessItems(contextValue?['sources'] ?? [])
              .map((row) => row['source_id'])
              .toList(),
          choices: choices,
        ),
      ],
      (values) {
        final selected = values['sources'];
        if (selected is! List || selected.isEmpty || selected.length > 8)
          throw const FormatException(
            'Eine bis acht Quellen ausdrücklich auswählen.',
          );
        return {
          'project_id': project,
          'sources': [
            for (final key in selected)
              descriptors[key] ??
                  (throw const FormatException('Quelle nicht mehr verfügbar.')),
          ],
        };
      },
    );
  }

  Future<void> dialogContent(
    String title,
    List<Widget> children, {
    List<Widget> buttons = const [],
  }) async {
    guard();
    final session = scope!,
        selected = project,
        permissions = Set.of(session.permissions),
        generation = session.generation,
        parentGeneration = widget.session.generation,
        parentPermissions = Set.of(widget.session.permissions);
    bool allowed() =>
        mounted &&
        scope == session &&
        project == selected &&
        readable &&
        session.permissions.containsAll(permissions) &&
        session.generation == generation &&
        widget.session.generation == parentGeneration &&
        widget.session.permissions.containsAll(parentPermissions);
    await privateDialog<void>(
      builder: (_) => ListenableBuilder(
        listenable: Listenable.merge([session, widget.session]),
        builder: (context, _) => AlertDialog(
          title: Text(title),
          content: SizedBox(
            width: 780,
            child: SingleChildScrollView(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: allowed()
                    ? children
                    : [
                        const Text(
                          'Die Berechtigung für diese Ansicht wurde geändert. Bitte neu laden.',
                        ),
                      ],
              ),
            ),
          ),
          actions: [
            if (allowed()) ...buttons,
            TextButton(
              onPressed: () => Navigator.pop(context),
              child: const Text('Schließen'),
            ),
          ],
        ),
      ),
    );
  }

  Future<void> sourceDetail(String contextId, String sourceId) async {
    final valid = currentView();
    try {
      final context = await freshContext(contextId),
          source = businessItems(context['sources'])
              .firstWhere((row) => row['source_id'] == sourceId),
          data = businessMap(source['data']);
      if (!valid()) return;
      guard();
      final labels = {
        'name': 'Bezeichnung',
        'title': 'Titel',
        'number': 'Belegnummer',
        'subject': 'Betreff',
        'description': 'Beschreibung',
        'details': 'Einzelheiten',
        'status': 'Status',
        'revision': 'Fassung',
        'due_date': 'Fällig am',
        'issue_date': 'Belegdatum',
        'start_date': 'Beginn',
        'end_date': 'Ende',
        'recipient': 'Empfänger',
        'unit': 'Einheit',
        'unit_price_net': 'Netto-Verkaufspreis je Einheit',
        'tax_rate': 'Steuersatz',
        'currency': 'Währung',
        'open': 'Offener Betrag',
        'paid': 'Bezahlt',
        'overdue_days': 'Verzug in Tagen',
        'message': 'Nachricht',
      };
      await dialogContent(
        '${assistantKinds[source['descriptor']['kind']]} · ${_sourceTitle(source)}',
        [
          if (source['descriptor']['kind'] == 'communication')
            const Notice(
              'Externer Inhalt dient als Beleg. Er erteilt keine Regel- oder Ausführungsfreigabe.',
            ),
          for (final entry in labels.entries)
            if (data[entry.key] != null && data[entry.key] != '')
              Padding(
                padding: const EdgeInsets.only(bottom: 8),
                child: SelectableText('${entry.value}: ${data[entry.key]}'),
              ),
          if (data['totals'] != null)
            Text(
              'Netto: ${data['totals']['net']} · Steuer: ${data['totals']['tax']} · Brutto: ${data['totals']['gross']}',
            ),
          if (data['costs'] != null)
            Text('Erfasste Projektkosten netto: ${data['costs']['total_net']}'),
          SelectableText('Originalquelle: $sourceId'),
          SelectableText('Quellenprüfung: ${source['sha256']}'),
        ],
      );
    } catch (e) {
      if (valid()) setState(() => error = '$e');
    }
  }

  Future<void> speak() async {
    guard(true);
    final current = contextValue, session = scope, valid = currentView();
    if (current == null ||
        current['current'] != true ||
        speechStatus?['provider']?['configured'] != true)
      return;
    final provider = businessMap(speechStatus!['provider']);
    final result = await privateDialog<String>(
      barrierDismissible: false,
      builder: (_) => BusinessSpeechDraft(
        session: session!,
        source: current,
        provider: provider,
      ),
    );
    if (result != null &&
        valid() &&
        scope == session &&
        readable &&
        contextValue?['id'] == current['id'])
      setState(() => speechDraft = result);
  }

  Future<void> ask() async {
    guard(true);
    final current = contextValue;
    if (current == null ||
        current['current'] != true ||
        status?['provider']['configured'] != true)
      return;
    final result = await editor(
      'Frage mit ausgewählten Quellen senden',
      'assistant-chat-${current['id']}',
      '/assistant/chat',
      [
        BusinessField(
          'message',
          'Ihre Frage',
          initial: speechDraft,
          type: BusinessInput.multiline,
          required: true,
        ),
        const BusinessField(
          'data_transfer_confirmed',
          'Ich bestätige die Weitergabe dieser Nachricht und ausgewählten Quellen an den eingerichteten Anbieter. Passende Automatikregeln dürfen konkrete Vorschläge unmittelbar ausführen.',
          type: BusinessInput.toggle,
          initial: false,
        ),
      ],
      (values) {
        if (values['data_transfer_confirmed'] != true)
          throw const FormatException(
            'Datenweitergabe ausdrücklich bestätigen.',
          );
        return {'context_id': current['id'], ...values};
      },
    );
    if (result != null && mounted && readable) {
      speechDraft = '';
      await chatDetail('${businessMap(result)['id']}');
    }
  }

  Future<void> chatDetail(String id) async {
    guard();
    final valid = currentView(), session = scope!;
    try {
      final chat = businessMap(await session.read('/assistant/chat/$id'));
      if (!valid()) return;
      final source = await freshContext('${chat['context_id']}');
      if (!valid()) return;
      guard();
      final children = <Widget>[
        Text('Ihre Frage: ${chat['message']}'),
        if (chat['source_current'] != true)
          const Notice(
            'Die gespeicherte Antwort bezieht sich auf einen früheren Quellenstand.',
          ),
      ];
      if (chat['status'] == 'completed') {
        final answer = assistantAnswerValues(source, chat);
        children.addAll([
          Text('${answer['summary']}'),
          for (final fact in businessItems(answer['facts']))
            ListTile(
              contentPadding: EdgeInsets.zero,
              title: Text(
                '${fact['path']}: ${fact['value'] is bool ? (fact['value'] ? 'Ja' : 'Nein') : fact['value'] ?? 'Nicht angegeben'}',
              ),
              subtitle: Text(
                _sourceTitle(
                  businessItems(
                    source['sources'],
                  ).firstWhere((row) => row['source_id'] == fact['source_id']),
                ),
              ),
              onTap: () =>
                  sourceDetail('${source['id']}', '${fact['source_id']}'),
            ),
          Wrap(
            spacing: 8,
            children: [
              for (final citation in answer['citations'] as List)
                TextButton(
                  onPressed: () => sourceDetail('${source['id']}', '$citation'),
                  child: Text(
                    'Beleg: ${_sourceTitle(businessItems(source['sources']).firstWhere((row) => row['source_id'] == citation))}',
                  ),
                ),
            ],
          ),
          for (final plan in answer['plan_ids'] as List? ?? [])
            TextButton(
              onPressed: () => planDetail('$plan'),
              child: const Text('Aktionsvorschlag prüfen'),
            ),
        ]);
      } else
        children.add(
          const Notice(
            'Keine bestätigte Modellantwort. Ein begonnener Aufruf kann bereits abgerechnet worden sein; er wird nicht automatisch erneut angefordert.',
          ),
        );
      await dialogContent('Antwort und Belege', children);
    } catch (e) {
      if (valid()) setState(() => error = '$e');
    }
  }

  Future<void> planForm() async {
    guard(true);
    final current = contextValue, valid = currentView();
    if (current == null || current['current'] != true) return;
    Map<String, dynamic>? choice;
    await privateDialog<bool>(
      builder: (_) => BusinessEditor(
        session: scope!,
        title: 'Aktionsart auswählen',
        readPermission: 'assistant.use',
        writePermission: 'assistant.use',
        fields: const [
          BusinessField(
            'action',
            'Konkrete Aktion',
            type: BusinessInput.choice,
            initial: 'task.create',
            choices: assistantActions,
            required: true,
          ),
          BusinessField(
            'trigger',
            'Auslöser',
            type: BusinessInput.choice,
            initial: 'manual',
            choices: assistantTriggers,
            required: true,
          ),
        ],
        saveLabel: 'Aktionsparameter eingeben',
        onSave: (values) async => choice = values,
      ),
    );
    if (choice == null || !valid()) return;
    guard(true);
    final action = '${choice!['action']}',
        fields = <BusinessField>[
          const BusinessField(
            'reason',
            'Anlass und Begründung',
            type: BusinessInput.multiline,
            required: true,
          ),
        ];
    if (action == 'task.create')
      fields.addAll(const [
        BusinessField('title', 'Aufgabe', required: true),
        BusinessField(
          'details',
          'Aufgabenbeschreibung',
          type: BusinessInput.multiline,
        ),
        BusinessField('due_date', 'Fällig am', type: BusinessInput.date),
        BusinessField(
          'priority',
          'Priorität',
          type: BusinessInput.choice,
          initial: 'normal',
          choices: {'normal': 'Normal', 'high': 'Hoch'},
        ),
      ]);
    else if (action == 'offer.draft') {
      fields.addAll([
        const BusinessField('title', 'Angebotstitel', required: true),
        BusinessField(
          'issue_date',
          'Belegdatum',
          type: BusinessInput.date,
          initial: _date(),
          required: true,
        ),
        BusinessField(
          'due_date',
          'Fällig am',
          type: BusinessInput.date,
          initial: _date(),
          required: true,
        ),
        for (final source in businessItems(
          current['sources'],
        ).where((row) => row['descriptor']['kind'] == 'article'))
          BusinessField(
            '${source['descriptor']['id']}',
            'Menge · ${_sourceTitle(source)}',
            hint:
                '${source['data']['unit']} · Artikelfassung ${source['data']['revision']}',
          ),
      ]);
    } else {
      final mapping = {
        'document.email': ('document_id', 'document'),
        'dunning.email': ('outbox_id', 'dunning'),
        'supplier.order': ('order_id', 'purchase'),
        'payment.execute': ('document_id', 'open_item'),
      }[action]!;
      fields.add(
        BusinessField(
          mapping.$1,
          'Ausgewählte Fachquelle',
          type: BusinessInput.choice,
          required: true,
          choices: {
            for (final source in businessItems(
              current['sources'],
            ).where((row) => row['descriptor']['kind'] == mapping.$2))
              '${source['descriptor']['id']}': _sourceTitle(source),
          },
        ),
      );
    }
    fields.add(
      const BusinessField(
        'confirmation',
        'Ich bestätige diesen konkreten Aktionsauftrag. Eine passende Automatikregel darf ihn unmittelbar ausführen.',
        type: BusinessInput.toggle,
        initial: false,
      ),
    );
    final result = await editor(
      'Auftrag mit aktuellen Regeln prüfen',
      'assistant-plan-${current['id']}-$action',
      '/assistant/plans',
      fields,
      (values) {
        if (values['confirmation'] != true)
          throw const FormatException(
            'Konkreten Aktionsauftrag ausdrücklich bestätigen.',
          );
        Map<String, dynamic> parameters;
        if (action == 'task.create') {
          parameters = {
            for (final field in ['title', 'details', 'due_date', 'priority'])
              field: values[field],
          };
        } else if (action == 'offer.draft') {
          parameters = {
            'title': values['title'],
            'issue_date': values['issue_date'],
            'due_date': values['due_date'],
            'positions': assistantOfferPositions(current, values),
          };
        } else {
          final field = action == 'supplier.order'
              ? 'order_id'
              : action == 'dunning.email'
              ? 'outbox_id'
              : 'document_id';
          parameters = {field: values[field]};
        }
        return {
          'context_id': current['id'],
          'trigger': choice!['trigger'],
          'action': action,
          'parameters': parameters,
          'reason': values['reason'],
        };
      },
    );
    if (result != null && mounted && readable)
      await planDetail('${businessMap(result)['id']}');
  }

  Future<void> planDetail(String id) async {
    guard();
    final valid = currentView(), session = scope!;
    try {
      final item = businessMap(await session.read('/assistant/plans/$id'));
      if (!valid()) return;
      if (item['project_id'] != project)
        throw const ApiException(403, 'Der Auftrag gehört nicht zum Projekt.');
      final source = await freshContext('${item['context_id']}');
      if (!valid()) return;
      guard();
      final policy = businessMap(item['policy']),
          parameters = businessMap(item['parameters']),
          buttons = <Widget>[];
      if (writable &&
          scope!.can('assistant.approve') &&
          canAction('${item['action']}') &&
          policy['mode'] != 'deny' &&
          policy['responsible_id'] == userId &&
          item['source_current'] == true &&
          item['decision'] == null &&
          item['execution'] == null &&
          item['status'] != 'stale') {
        buttons.addAll([
          TextButton(
            onPressed: () {
              Navigator.pop(context);
              decide(item, false);
            },
            child: const Text('Ablehnen'),
          ),
          FilledButton(
            onPressed: () {
              Navigator.pop(context);
              decide(item, true);
            },
            child: const Text('Konkreten Auftrag freigeben'),
          ),
        ]);
      }
      if (writable && item['can_execute'] == true)
        buttons.add(
          FilledButton(
            onPressed: () {
              Navigator.pop(context);
              execute(item);
            },
            child: const Text('Freigegebenen Auftrag ausführen'),
          ),
        );
      await dialogContent('Aktionsauftrag · ${assistantActions[item['action']]}', [
        Text(
          '${assistantStates[item['status']] ?? item['status']}',
          style: Theme.of(context).textTheme.titleLarge,
        ),
        Notice(
          '${item['execution_blocked_reason'] ?? 'Regelentscheidung: ${assistantModes[policy['mode']]}'}',
        ),
        Text('${item['reason']}'),
        for (final field in [
          'title',
          'details',
          'issue_date',
          'due_date',
          'priority',
          'document_id',
          'outbox_id',
          'order_id',
        ])
          if (parameters[field] != null)
            Text(
              '${{'title': 'Titel', 'details': 'Beschreibung', 'issue_date': 'Belegdatum', 'due_date': 'Fällig am', 'priority': 'Priorität', 'document_id': 'Belegquelle', 'outbox_id': 'Mahnquelle', 'order_id': 'Bestellquelle'}[field]}: ${parameters[field]}',
            ),
        for (final line in businessItems(parameters['positions'] ?? []))
          Text(
            '${_sourceTitle(businessItems(source['sources']).firstWhere((row) => row['descriptor']['kind'] == 'article' && row['descriptor']['id'] == line['article_id']))} · Fassung ${line['article_revision']} · Menge ${line['quantity']}',
          ),
        const Divider(),
        Text(
          'Zuständig: ${policy['responsible_id'] == userId ? 'Sie' : policy['responsible_id'] ?? 'Keine eindeutige Zuständigkeit'}',
        ),
        for (final fact in businessMap(
          policy['facts'],
        ).entries.where((entry) => entry.value != null))
          Text(
            '${_facts[fact.key]?.$1 ?? fact.key}: ${fact.value is bool
                ? (fact.value ? 'Ja' : 'Nein')
                : _facts[fact.key]?.$2 == 'money'
                ? (fact.value / 100).toStringAsFixed(2)
                : fact.value}',
          ),
        for (final proof in businessItems(policy['evidence'] ?? []))
          SelectableText(
            'Regelbeleg: ${proof['kind']} · ${proof['source_sha256']}',
          ),
        for (final rule in businessItems(policy['matched_rules']))
          TextButton(
            onPressed: () => ruleHistory('${rule['id']}'),
            child: Text('Regel · Fassung ${rule['revision']}'),
          ),
        for (final row in businessItems(source['sources']))
          TextButton(
            onPressed: () =>
                sourceDetail('${source['id']}', '${row['source_id']}'),
            child: Text('Quelle prüfen: ${_sourceTitle(row)}'),
          ),
        if (item['decision'] != null) ...[
          const Divider(),
          Text(
            item['decision']['decision'] == 'approved'
                ? 'Freigegeben'
                : 'Abgelehnt',
          ),
          Text('${item['decision']['reason']}'),
        ],
        if (item['outcome'] != null) ...[
          const Divider(),
          Text(
            'Dokumentiertes Ergebnis: ${assistantStates[item['outcome']['status']] ?? item['outcome']['status']}',
          ),
          if (item['outcome']['status'] == 'succeeded')
            Text(
              'Fachvorgang: ${item['outcome']['result']['id'] ?? item['outcome']['result']['status'] ?? 'Bestätigt'}',
            )
          else
            const Notice(
              'Keine erneute Ausführung ohne Klärung des dokumentierten Ergebnisses.',
            ),
        ],
      ], buttons: buttons);
    } catch (e) {
      if (valid()) setState(() => error = '$e');
    }
  }

  Future<void> decide(Map<String, dynamic> item, bool approved) async {
    final result = await editor(
      approved ? 'Konkrete Freigabe speichern' : 'Auftrag verbindlich ablehnen',
      'assistant-decision-${item['id']}-$approved',
      '/assistant/plans/${item['id']}/${approved ? 'approve' : 'reject'}',
      const [
        BusinessField(
          'reason',
          'Prüfvermerk',
          type: BusinessInput.multiline,
          required: true,
        ),
        BusinessField(
          'confirmation',
          'Ich habe diese konkrete Aktion, Quellen und Regelentscheidung geprüft.',
          type: BusinessInput.toggle,
          initial: false,
        ),
      ],
      (values) {
        if (values['confirmation'] != true)
          throw const FormatException(
            'Die konkrete Aktionsentscheidung ausdrücklich bestätigen.',
          );
        return {'plan_sha256': item['sha256'], ...values};
      },
      permission: 'assistant.approve',
    );
    if (result != null && mounted && readable)
      await planDetail('${item['id']}');
  }

  Future<void> execute(Map<String, dynamic> item) async {
    final result = await editor(
      'Konkrete Aktion jetzt ausführen',
      'assistant-execute-${item['id']}',
      '/assistant/plans/${item['id']}/execute',
      const [
        BusinessField(
          'confirmation',
          'Ich bestätige die Ausführung der angezeigten konkreten Aktion.',
          type: BusinessInput.toggle,
          initial: false,
        ),
      ],
      (values) {
        if (values['confirmation'] != true)
          throw const FormatException('Ausführung ausdrücklich bestätigen.');
        return {'plan_sha256': item['sha256'], ...values};
      },
    );
    if (result != null && mounted && readable)
      await planDetail('${item['id']}');
  }

  Future<void> ruleForm([Map<String, dynamic>? old]) async {
    guard(true);
    final valid = currentView(), session = scope!;
    if (!scope!.canWrite('settings.manage')) return;
    var users = <Map<String, dynamic>>[
      {'id': userId, 'email': 'Eigene Zuständigkeit'},
    ];
    try {
      users = businessItems(await session.api.call('/api/users'));
    } on ApiException catch (e) {
      if (!valid()) return;
      if (e.status != 403) rethrow;
    }
    if (!valid()) return;
    guard(true);
    final original = businessItems(old?['conditions'] ?? []);
    int? count;
    await privateDialog<bool>(
      builder: (_) => BusinessEditor(
        session: scope!,
        title: 'Regelbedingungen',
        readPermission: 'assistant.use',
        writePermission: 'settings.manage',
        fields: [
          BusinessField(
            'count',
            'Zahl der belegten Bedingungen (0 bis 8)',
            type: BusinessInput.integer,
            initial: original.length,
            required: true,
          ),
        ],
        saveLabel: 'Regel bearbeiten',
        onSave: (values) async {
          if (values['count'] is! int ||
              values['count'] < 0 ||
              values['count'] > 8)
            throw const FormatException('Null bis acht Bedingungen auswählen.');
          count = values['count'];
        },
      ),
    );
    if (count == null || !valid()) return;
    guard(true);
    final id = old?['id'] ?? offlineId(),
        fields = <BusinessField>[
          BusinessField(
            'title',
            'Regelbezeichnung',
            required: true,
            initial: old?['title'] ?? '',
          ),
          BusinessField(
            'enabled',
            'Regel aktiv',
            type: BusinessInput.toggle,
            initial: old?['enabled'] ?? true,
          ),
          BusinessField(
            'trigger',
            'Auslöser',
            type: BusinessInput.choice,
            initial: old?['trigger'] ?? 'manual',
            choices: assistantTriggers,
          ),
          BusinessField(
            'action',
            'Erlaubte oder verbotene Aktion',
            type: BusinessInput.choice,
            initial: old?['action'] ?? 'task.create',
            choices: assistantActions,
          ),
          BusinessField(
            'mode',
            'Entscheidung',
            type: BusinessInput.choice,
            initial: old?['mode'] ?? 'approval',
            choices: assistantModes,
          ),
          BusinessField(
            'responsible_id',
            'Zuständige Person',
            type: BusinessInput.choice,
            initial: old?['responsible_id'] ?? userId,
            required: true,
            choices: {
              for (final user in users)
                '${user['id']}':
                    '${user['email'] ?? user['name'] ?? user['id']}',
              if (old != null &&
                  !users.any((user) => user['id'] == old['responsible_id']))
                '${old['responsible_id']}': 'Bisherige zuständige Person',
            },
          ),
        ];
    for (var index = 0; index < count!; index++) {
      final condition = index < original.length
              ? original[index]
              : <String, dynamic>{
                  'field': 'overdue_payment',
                  'operator': 'eq',
                  'value': true,
                },
          value = condition['value'];
      final formatted = _facts[condition['field']]?.$2 == 'money'
          ? (value / 100).toStringAsFixed(2)
          : value is bool
          ? (value ? 'Ja' : 'Nein')
          : '$value';
      fields.addAll([
        BusinessField(
          'field_$index',
          'Belegter Fakt ${index + 1}',
          type: BusinessInput.choice,
          initial: condition['field'],
          choices: {
            for (final entry in _facts.entries) entry.key: entry.value.$1,
          },
        ),
        BusinessField(
          'operator_$index',
          'Vergleich ${index + 1}',
          type: BusinessInput.choice,
          initial: condition['operator'],
          choices: const {
            'eq': 'Ist gleich',
            'gte': 'Mindestens',
            'lte': 'Höchstens',
          },
        ),
        BusinessField(
          'value_$index',
          'Vergleichswert ${index + 1} (Tage / EUR / Ja oder Nein)',
          initial: formatted,
          required: true,
        ),
      ]);
    }
    fields.add(
      const BusinessField(
        'confirmation',
        'Ich bestätige diese Regel und ihre Zuständigkeit. Automatisch erlaubte Aktionen können unmittelbar ausgeführt werden.',
        type: BusinessInput.toggle,
        initial: false,
      ),
    );
    await editor(
      'Neue Regelfassung verbindlich speichern',
      'assistant-rule-$id-${old?['revision'] ?? 0}',
      '/assistant/rules',
      fields,
      (values) {
        if (values['confirmation'] != true)
          throw const FormatException(
            'Regel und Zuständigkeit ausdrücklich bestätigen.',
          );
        return {
          'id': id,
          'revision': old?['revision'] ?? 0,
          'project_id': project,
          for (final name in [
            'title',
            'enabled',
            'trigger',
            'action',
            'mode',
            'responsible_id',
            'confirmation',
          ])
            name: values[name],
          'conditions': assistantConditions([
            for (var index = 0; index < count!; index++)
              {
                'field': values['field_$index'],
                'operator': values['operator_$index'],
                'value': values['value_$index'],
              },
          ]),
        };
      },
      permission: 'settings.manage',
    );
  }

  Future<void> ruleHistory(String id) async {
    guard();
    final valid = currentView(), session = scope!;
    try {
      final result = businessMap(
        await session.read('/assistant/rules/$id/history'),
      );
      if (!valid()) return;
      guard();
      await dialogContent('Regelhistorie', [
        for (final rule in businessItems(result['items'])) ...[
          Text(
            '${rule['title']} · Fassung ${rule['revision']}',
            style: Theme.of(context).textTheme.titleLarge,
          ),
          Text(
            '${rule['enabled'] ? 'Aktiv' : 'Deaktiviert'} · ${assistantTriggers[rule['trigger']]} · ${assistantActions[rule['action']]} · ${assistantModes[rule['mode']]}',
          ),
          Text('Zuständig: ${rule['responsible_id']}'),
          for (final condition in businessItems(rule['conditions']))
            Text(
              '${_facts[condition['field']]?.$1} · ${{'eq': 'Ist gleich', 'gte': 'Mindestens', 'lte': 'Höchstens'}[condition['operator']]} · ${condition['value'] is bool
                  ? (condition['value'] ? 'Ja' : 'Nein')
                  : _facts[condition['field']]?.$2 == 'money'
                  ? (condition['value'] / 100).toStringAsFixed(2)
                  : condition['value']}',
            ),
          Text(businessDate(rule['created_at'], time: true)),
          const Divider(),
        ],
      ]);
    } catch (e) {
      if (valid()) setState(() => error = '$e');
    }
  }

  Widget section(String title, List<Widget> children) => Card(
    child: Padding(
      padding: const EdgeInsets.all(20),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(title, style: Theme.of(context).textTheme.titleLarge),
          const SizedBox(height: 12),
          ...children,
        ],
      ),
    ),
  );
  @override
  Widget build(BuildContext context) => ListView(
    padding: const EdgeInsets.all(20),
    children: [
      Text('Assistent', style: Theme.of(context).textTheme.headlineMedium),
      const Text(
        'Belegte Projektquellen, konkrete Aufträge und nachvollziehbare Unternehmensregeln.',
      ),
      BusinessCompanyEventsEntry(session: widget.session),
      if (widget.session.projectId == null)
        DropdownButtonFormField<String>(
          initialValue: project,
          decoration: const InputDecoration(
            labelText: 'Projekt für den Assistenten',
          ),
          items: [
            for (final item in widget.session.projects)
              DropdownMenuItem(
                value: '${item['id']}',
                child: Text('${item['name']}'),
              ),
          ],
          onChanged: (id) {
            if (id != null) select(id);
          },
        ),
      if (project == null)
        const BusinessEmpty(
          'Projekt auswählen',
          'Die Datenbasis bleibt an dieses Projekt und Ihre jeweiligen Fachrechte gebunden.',
        ),
      if (error != null) Notice(error!, error: true),
      if (busy) const LinearProgressIndicator(),
      if (project != null)
        TextButton(
          onPressed: busy ? null : load,
          child: const Text('Assistent aktualisieren'),
        ),
      if (readable) ...[
        for (final entry in memory.pending.entries.where(
          (entry) => scope!.pending(entry.key),
        ))
          Card(
            child: ListTile(
              title: Text('Antwort offen: ${entry.value.title}'),
              subtitle: const Text(
                'Denselben Auftrag unverändert wiederholen; keine neue Außenwirkung wird ungeprüft erneut ausgelöst.',
              ),
              trailing: TextButton(
                onPressed: writable && !busy ? () => repeat(entry.key) : null,
                child: const Text('Unverändert wiederholen'),
              ),
            ),
          ),
        section('Ausgewählte Fachquellen', [
          const Notice(
            'Nur ausdrücklich ausgewählte und aktuell zugängliche Quellen gehören zur Datenbasis.',
          ),
          Wrap(
            spacing: 8,
            children: [
              TextButton(
                onPressed: busy ? null : searchSources,
                child: const Text('Quellen suchen'),
              ),
              if (sourceOffset > 0)
                TextButton(
                  onPressed: busy
                      ? null
                      : () async {
                          sourceOffset = (sourceOffset - 100).clamp(0, 100000);
                          await load();
                        },
                  child: const Text('Vorherige Quellen'),
                ),
              if (nextSourceOffset != null)
                TextButton(
                  onPressed: busy
                      ? null
                      : () async {
                          sourceOffset = nextSourceOffset!;
                          await load();
                        },
                  child: const Text('Weitere Quellen'),
                ),
            ],
          ),
          Text(
            '$sourceTotal zugängliche Treffer · ab ${sourceOffset + 1}. Bereits bestätigte Quellen bleiben enthalten.',
          ),
          if (sourceQuery.isNotEmpty) Text('Suche: $sourceQuery'),
          FilledButton(
            onPressed: writable && !busy ? chooseSources : null,
            child: const Text('Quellen auswählen'),
          ),
          if (contextValue == null)
            const Text('Noch keine Datenbasis bestätigt.')
          else ...[
            if (contextValue!['current'] != true)
              const Notice(
                'Die Quellen wurden geändert. Vor einem neuen Auftrag eine aktuelle Datenbasis auswählen.',
              ),
            for (final source in businessItems(contextValue!['sources']))
              ListTile(
                contentPadding: EdgeInsets.zero,
                title: Text(_sourceTitle(source)),
                subtitle: Text(
                  '${assistantKinds[source['descriptor']['kind']]}',
                ),
                trailing: TextButton(
                  onPressed: () => sourceDetail(
                    '${contextValue!['id']}',
                    '${source['source_id']}',
                  ),
                  child: const Text('Quelle prüfen'),
                ),
              ),
          ],
        ]),
        section('Fragen zu diesen Quellen', [
          if (status?['provider']['configured'] == true) ...[
            Text('Eingerichtetes Modell: ${status!['provider']['model']}'),
            FilledButton(
              onPressed: writable && contextValue?['current'] == true
                  ? ask
                  : null,
              child: const Text('Frage stellen'),
            ),
          ] else
            Notice(
              '${status?['provider']['message'] ?? 'KI-Anbieter, Unternehmensbindung und Datenweitergabe müssen noch eingerichtet werden.'}',
            ),
          if (speechStatus?['provider']?['configured'] == true)
            TextButton(
              onPressed: writable && contextValue?['current'] == true
                  ? speak
                  : null,
              child: const Text('Sprache aufnehmen'),
            )
          else
            Text(
              '${speechStatus?['provider']?['message'] ?? 'Spracheingabe ist noch nicht eingerichtet. Es läuft keine Mikrofonaufnahme.'}',
            ),
          if (speechDraft.isNotEmpty) Text('Textentwurf: $speechDraft'),
          for (final chat in chats)
            ListTile(
              contentPadding: EdgeInsets.zero,
              title: Text('${chat['message']}'),
              subtitle: Text(
                '${businessDate(chat['created_at'], time: true)} · ${{'completed': 'Belegte Antwort', 'failed': 'Antwort nicht bestätigt', 'stale': 'Quellen geändert', 'interrupted': 'Unterbrochen', 'unconfirmed': 'Antwort offen'}[chat['status']] ?? chat['status']}',
              ),
              onTap: () => chatDetail('${chat['id']}'),
            ),
        ]),
        section('Konkrete Aktionsaufträge', [
          if (writable && contextValue?['current'] == true)
            FilledButton(
              onPressed: planForm,
              child: const Text('Aktionsauftrag vorbereiten'),
            ),
          for (final plan in plans)
            ListTile(
              contentPadding: EdgeInsets.zero,
              title: Text('${assistantActions[plan['action']]}'),
              subtitle: Text(
                '${assistantStates[plan['status']] ?? plan['status']} · ${assistantModes[plan['policy']['mode']]}',
              ),
              onTap: () => planDetail('${plan['id']}'),
            ),
        ]),
        section('Unternehmensregeln für dieses Projekt', [
          const Notice(
            'Ohne passende Erlaubnis ist eine Aktion verboten. Verbot hat Vorrang vor Freigabe und Automatik.',
          ),
          if (writable && scope!.canWrite('settings.manage'))
            FilledButton(
              onPressed: () => ruleForm(),
              child: const Text('Regel anlegen'),
            ),
          for (final rule in rules)
            ListTile(
              contentPadding: EdgeInsets.zero,
              title: Text('${rule['title']}'),
              subtitle: Text(
                '${rule['enabled'] ? 'Aktiv' : 'Deaktiviert'} · ${assistantModes[rule['mode']]} · Fassung ${rule['revision']}',
              ),
              onTap: () => ruleHistory('${rule['id']}'),
              trailing: writable && scope!.canWrite('settings.manage')
                  ? TextButton(
                      onPressed: () => ruleForm(rule),
                      child: const Text('Bearbeiten'),
                    )
                  : null,
            ),
        ]),
      ],
    ],
  );
}

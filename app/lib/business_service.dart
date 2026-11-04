import 'package:cryptography/cryptography.dart';
import 'package:flutter/material.dart';

import 'api.dart';
import 'business_session.dart';
import 'business_resource_custody.dart';
import 'business_widgets.dart';
import 'design.dart';
import 'mail_attachment_widgets.dart';

const serviceEvents = {
  'created': 'Fall angelegt',
  'edited': 'Fall bearbeitet',
  'project_linked': 'Projekt zugeordnet',
  'dispatched': 'Einsatz disponiert',
  'evidence_linked': 'Bericht zugeordnet',
  'transition': 'Statusentscheidung',
  'note': 'Notiz',
  'call': 'Telefonat',
  'email': 'E-Mail dokumentiert',
  'meeting': 'Besprechung',
};
const serviceStages = {
  'open': 'Offen',
  'triaged': 'Geprüft',
  'planned': 'Einsatz geplant',
  'in_progress': 'In Bearbeitung',
  'waiting_customer': 'Warten auf Kunde',
  'waiting_supplier': 'Warten auf Lieferant',
  'resolved': 'Gelöst',
  'closed': 'Abgeschlossen',
  'cancelled': 'Abgebrochen',
};
const serviceKinds = {
  'request': 'Kundenanliegen',
  'complaint': 'Reklamation',
  'maintenance': 'Wartung',
};
const servicePriorities = {
  'low': 'Niedrig',
  'normal': 'Normal',
  'high': 'Hoch',
  'urgent': 'Dringend',
};
bool _id(Object? value) => RegExp(r'^[a-f0-9]{32}$').hasMatch('$value');
bool _hash(Object? value) => RegExp(r'^[a-f0-9]{64}$').hasMatch('$value');
Map<String, dynamic> serviceBound(Map<String, dynamic> item) {
  if (!_id(item['id']) ||
      item['revision'] is! int ||
      item['revision'] < 1 ||
      !_hash(item['source_sha256']))
    throw const FormatException('Die aktuelle Fallfassung zuerst laden.');
  return {'revision': item['revision'], 'source_sha256': item['source_sha256']};
}

Map<String, dynamic> serviceCaseValues(
  Map<String, dynamic> values,
  Map<String, dynamic> refs, {
  Map<String, dynamic>? previous,
}) {
  if (!_id(refs['customer_id']) ||
      !serviceKinds.containsKey(values['kind']) ||
      !servicePriorities.containsKey(values['priority']) ||
      !_id(values['responsible_id']) ||
      '${values['title'] ?? ''}'.trim().isEmpty)
    throw const FormatException(
      'Kunde, Fallart, Priorität, Betreff und Zuständigkeit vollständig wählen.',
    );
  if ([
        'inquiry_id',
        'defect_id',
        'visit_id',
      ].where((key) => refs[key] != null && refs[key] != '').length >
      1)
    throw const FormatException(
      'Höchstens eine Anfrage, einen Mangel oder Wartungsbesuch übernehmen.',
    );
  return {
    'revision': previous?['revision'] ?? 0,
    for (final key in [
      'customer_id',
      'person_id',
      'project_id',
      'asset_id',
      'contract_id',
      'visit_id',
      'inquiry_id',
      'defect_id',
    ])
      key: refs[key] == '' ? null : refs[key],
    ...values,
    'follow_up_on': values['follow_up_on'] == ''
        ? null
        : values['follow_up_on'],
    if (previous != null) 'id': previous['id'],
  };
}

Map<String, dynamic> serviceTransitionValues(
  Map<String, dynamic> item,
  Map<String, dynamic> values,
) {
  if (!(item['allowed_transitions'] as List).contains(values['status']) ||
      '${values['reason'] ?? ''}'.trim().isEmpty ||
      (['resolved', 'closed'].contains(values['status']) &&
          '${values['resolution'] ?? ''}'.trim().isEmpty))
    throw const FormatException(
      'Erlaubten Status, Begründung und bei Lösung den Lösungsnachweis angeben.',
    );
  return {
    ...serviceBound(item),
    'status': values['status'],
    'reason': values['reason'],
    'resolution': values['resolution'] ?? '',
  };
}

Map<String, dynamic> serviceReceipt(
  String path,
  Map<String, dynamic> body,
  dynamic value,
) {
  final response = businessMap(value),
      item = path == '/service/cases'
          ? response
          : businessMap(response['case']);
  if (!_id(item['id']) ||
      !_hash(item['source_sha256']) ||
      item['revision'] != body['revision'] + (path.endsWith('/events') ? 0 : 1))
    throw const ApiException(
      0,
      'Antwort bestätigt die konkrete neue Fallfassung nicht.',
    );
  if (path == '/service/cases') {
    if (body['id'] != null && item['id'] != body['id'] ||
        item['customer_id'] != body['customer_id'] ||
        item['project_id'] != body['project_id'] ||
        item['title'] != body['title'] ||
        item['responsible_id'] != body['responsible_id'])
      throw const ApiException(
        0,
        'Fallantwort gehört zu einer anderen Eingabe.',
      );
  } else {
    final match = RegExp(
      r'^/service/cases/([a-f0-9]{32})/(events|project|dispatch|evidence|transition)$',
    ).firstMatch(path);
    if (match == null || item['id'] != match.group(1))
      throw const ApiException(
        0,
        'Antwort gehört zu einem anderen Servicefall.',
      );
    if (match.group(2) == 'events' &&
        (!_id(response['event']?['id']) ||
            response['event']['case_id'] != item['id'] ||
            response['event']['kind'] != body['kind'] ||
            response['event']['values']?['text'] != body['text'] ||
            response['event']['values']?['occurred_on'] != body['occurred_on']))
      throw const ApiException(
        0,
        'Der dokumentierte Kontakt wurde nicht bestätigt.',
      );
    if (match.group(2) == 'transition' && item['status'] != body['status'])
      throw const ApiException(0, 'Statusentscheidung wurde nicht bestätigt.');
    if (match.group(2) == 'project' && !_id(item['project_id']))
      throw const ApiException(0, 'Projektübernahme wurde nicht bestätigt.');
    if (['dispatch', 'evidence'].contains(match.group(2)) &&
        !_id(response['link']?['target_id']))
      throw const ApiException(0, 'Der konkrete Fachnachweis fehlt.');
  }
  return response;
}

class BusinessServicePage extends StatefulWidget {
  const BusinessServicePage({
    super.key,
    required this.session,
    this.customerId,
    this.projectId,
    this.origin,
    this.onProject,
    this.exporter,
  });
  final BusinessSession session;
  final String? customerId, projectId;
  final Map<String, dynamic>? origin;
  final void Function(Map<String, dynamic>)? onProject;
  final MailAttachmentExporter? exporter;
  @override
  State<BusinessServicePage> createState() => _BusinessServicePageState();
}

class _BusinessServicePageState extends State<BusinessServicePage>
    with WidgetsBindingObserver {
  BusinessSession get session => widget.session;
  BusinessSession? scope;
  Map<String, dynamic>? listing, selected, options, history;
  final search = TextEditingController();
  String? selectedId, error;
  String status = '', due = '', priority = '', responsible = '';
  List<Map<String, dynamic>> filterResponsibles = [];
  bool owner = false, loading = false;
  int epoch = 0;
  Object? generation;
  Set<String> rights = {};
  String? token, baseUrl;
  bool backgrounded = false;
  final Map<Route<dynamic>, NavigatorState> ownedDialogs = {};
  String? get projectId => widget.projectId ?? session.projectId;
  bool get available =>
      !backgrounded &&
      session.allowed &&
      session.hasFeature('service_cases') &&
      session.hasModule('service') &&
      session.can('contacts.read');
  bool get readable =>
      available &&
      (selected == null || selected!['project_id'] == null
          ? available
          : scope?.can('documents.read') == true);
  bool get writable =>
      readable &&
      scope != null &&
      !scope!.readonly &&
      (scope!.projectId == null
          ? owner && scope!.canWrite('contacts.write')
          : scope!.canWrite('documents.write'));
  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    token = session.api.token;
    baseUrl = session.api.base;
    generation = session.generation;
    rights = Set.of(session.permissions);
    session.addListener(changed);
    load();
  }

  bool current(int captured) => mounted && !backgrounded && captured == epoch;

  void ensureCurrent(int captured) {
    if (!current(captured))
      throw const ApiException(0, 'Der Servicekontext wurde geschlossen.');
  }

  void closeOwnedDialogs() {
    final previous = Map<Route<dynamic>, NavigatorState>.of(ownedDialogs);
    ownedDialogs.clear();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      for (final entry in previous.entries) {
        if (entry.value.mounted && entry.key.isActive)
          entry.value.removeRoute(entry.key);
      }
    });
  }

  Future<T?> ownedDialog<T>({
    required BuildContext context,
    required WidgetBuilder builder,
    bool barrierDismissible = true,
  }) async {
    final captured = epoch;
    ensureCurrent(captured);
    final navigator = Navigator.of(context, rootNavigator: true);
    final route = DialogRoute<T>(
      context: context,
      barrierDismissible: barrierDismissible,
      builder: (context) =>
          current(captured) ? builder(context) : const SizedBox.shrink(),
    );
    ownedDialogs[route] = navigator;
    try {
      return await navigator.push(route);
    } finally {
      ownedDialogs.remove(route);
    }
  }

  void clearPrivate() {
    epoch++;
    closeOwnedDialogs();
    if (scope != null && !identical(scope, session))
      scope!.removeListener(changed);
    scope = null;
    listing = selected = options = history = null;
    selectedId = error = null;
    filterResponsibles = [];
    status = due = priority = responsible = '';
    search.clear();
    owner = loading = false;
  }

  @override
  void didUpdateWidget(covariant BusinessServicePage old) {
    super.didUpdateWidget(old);
    if (!identical(old.session, session) ||
        old.projectId != widget.projectId ||
        old.customerId != widget.customerId ||
        old.origin != widget.origin) {
      old.session.removeListener(changed);
      clearPrivate();
      session.addListener(changed);
      token = session.api.token;
      baseUrl = session.api.base;
      generation = session.generation;
      rights = Set.of(session.permissions);
      load();
    }
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState value) {
    if (!mounted) return;
    if ([
      AppLifecycleState.hidden,
      AppLifecycleState.paused,
      AppLifecycleState.detached,
    ].contains(value)) {
      setState(() {
        backgrounded = true;
        clearPrivate();
      });
    } else if (value == AppLifecycleState.resumed) {
      setState(() => backgrounded = false);
    }
  }

  @override
  void dispose() {
    epoch++;
    WidgetsBinding.instance.removeObserver(this);
    closeOwnedDialogs();
    session.removeListener(changed);
    if (scope != null && !identical(scope, session))
      scope!.removeListener(changed);
    search.dispose();
    super.dispose();
  }

  void changed() {
    if (!mounted) return;
    if (!available ||
        token != session.api.token ||
        baseUrl != session.api.base ||
        generation != session.generation ||
        !session.permissions.containsAll(rights) ||
        (selected?['project_id'] != null &&
            scope?.can('documents.read') != true)) {
      clearPrivate();
    }
    token = session.api.token;
    baseUrl = session.api.base;
    generation = session.generation;
    rights = Set.of(session.permissions);
    setState(() {});
  }

  void guard({bool write = false}) {
    if (!mounted || !available || !readable || (write && !writable))
      throw const ApiException(
        403,
        'Die aktuelle Service- oder Quellberechtigung fehlt.',
      );
  }

  Future<void> attempt(Future<void> Function() callback) async {
    final captured = epoch;
    try {
      await callback();
    } catch (value) {
      if (current(captured) && available) setState(() => error = '$value');
    }
  }

  Future<Map<String, dynamic>> get(String path) async {
    if (!available) throw const ApiException(403, 'Servicefreigabe fehlt.');
    final captured = epoch;
    try {
      final result = businessMap(await session.read(path));
      if (!mounted || !available || captured != epoch)
        throw const ApiException(0, 'Sitzung oder Auswahl geändert.');
      return result;
    } on ApiException catch (value) {
      if (mounted &&
          captured == epoch &&
          [401, 403, 404].contains(value.status))
        setState(() {
          clearPrivate();
        });
      rethrow;
    }
  }

  Future<void> sources(String? customer, String? project) async {
    final captured = epoch;
    final next = project == null
        ? session
        : session.sharedProjectSession(project);
    if (scope != null && !identical(scope, session) && !identical(scope, next))
      scope!.removeListener(changed);
    if (!identical(next, scope) && !identical(next, session))
      next.addListener(changed);
    scope = next;
    await next.load();
    ensureCurrent(captured);
    if (next.error != null)
      throw const ApiException(
        0,
        'Aktuelle Fachrechte konnten nicht geladen werden.',
      );
    final choices = await get(
      session.query('/service/options', {
        if (customer != null) 'customer_id': customer,
        if (project != null) 'project_id': project,
      }),
    );
    final actor = businessMap(await session.api.call('/api/me'));
    ensureCurrent(captured);
    await next.load();
    ensureCurrent(captured);
    if (next.error != null ||
        !next.can('contacts.read') ||
        project != null && !next.can('documents.read'))
      throw const ApiException(403, 'Aktuelle Quellenrechte wurden entzogen.');
    if (!available) return;
    options = choices;
    owner = actor['role'] == 'owner';
  }

  Future<void> load() async {
    if (!available) return;
    final captured = ++epoch;
    setState(() {
      loading = true;
      error = null;
    });
    try {
      if (selectedId == null) {
        final result = await get(
          session.query('/service/cases', {
            if (widget.customerId != null) 'customer_id': widget.customerId!,
            if (projectId != null) 'project_id': projectId!,
            'q': search.text,
            if (status.isNotEmpty) 'status': status,
            if (priority.isNotEmpty) 'priority': priority,
            if (responsible.isNotEmpty) 'responsible_id': responsible,
            if (due.isNotEmpty) 'due': due,
          }),
        );
        final choices = await get(
          session.query('/service/options', {
            if (widget.customerId != null) 'customer_id': widget.customerId!,
            if (projectId != null) 'project_id': projectId!,
          }),
        );
        await session.load();
        ensureCurrent(captured);
        if (session.error != null || !available)
          throw const ApiException(403, 'Aktuelle Servicerechte fehlen.');
        if (mounted && captured == epoch)
          setState(() {
            listing = result;
            filterResponsibles = {
              for (final value in businessItems(choices['responsibles']))
                '${value['id']}': value,
              for (final value in businessItems(result))
                '${value['responsible_id']}': <String, dynamic>{
                  'id': value['responsible_id'],
                  'email': value['responsible_name'],
                },
            }.values.toList();
          });
      } else {
        final item = await get('/service/cases/$selectedId');
        if (item['id'] != selectedId)
          throw const ApiException(0, 'Falscher Servicefall.');
        await sources(item['customer_id'], item['project_id']);
        final events = await get('/service/cases/$selectedId/history');
        await sources(item['customer_id'], item['project_id']);
        ensureCurrent(captured);
        if (item['project_id'] == null && !owner)
          throw const ApiException(
            403,
            'Der ursprüngliche Fall ist nicht mehr freigegeben.',
          );
        events['events'] = businessItems(events['events'])
            .map((value) => {...value, ...businessMap(value['values'])})
            .toList();
        if (mounted && captured == epoch)
          setState(() {
            selected = item;
            history = events;
          });
      }
    } catch (value) {
      if (current(captured))
        setState(() {
          if (value is ApiException && [401, 403, 404].contains(value.status)) {
            clearPrivate();
            error =
                'Der Service- oder Quellenzugang ist nicht mehr freigegeben.';
          } else {
            error = '$value';
          }
        });
    } finally {
      if (mounted && captured == epoch) setState(() => loading = false);
    }
  }

  Future<dynamic> edit(
    String title,
    String key,
    String path,
    List<BusinessField> fields,
    Map<String, dynamic> Function(Map<String, dynamic>) build,
  ) async {
    guard(write: true);
    final captured = epoch, commandSession = session;
    var active = true;
    bool stillCurrent() => active && current(captured);
    dynamic result;
    try {
      await ownedDialog<bool>(
        context: context,
        barrierDismissible: false,
        builder: (_) => BusinessEditor(
          session: scope!,
          pendingSession: commandSession,
          title: title,
          fields: fields,
          pendingKey: key,
          readAllowed: () => stillCurrent() && readable,
          writePermission: scope!.projectId == null
              ? 'contacts.write'
              : 'documents.write',
          saveLabel: title,
          onSave: (values) async {
            ensureCurrent(captured);
            guard(write: true);
            if (commandSession.pending(key)) {
              result = await commandSession.repeatServiceCommand(
                key,
                stillCurrent: stillCurrent,
              );
              return;
            }
            final body = build(values);
            result = await commandSession.command(
              key,
              path,
              body,
              validateResult: (value) => serviceReceipt(path, body, value),
            );
          },
        ),
      );
    } finally {
      active = false;
    }
    return current(captured) ? result : null;
  }

  Future<void> choose() async {
    final captured = epoch;
    final original = session.pendingCommandValues(
      'service-case-new',
      path: '/service/cases',
    );
    if (original != null) {
      await sources(original['customer_id'], original['project_id']);
      ensureCurrent(captured);
      await caseForm(refs: original);
      return;
    }
    await sources(widget.customerId, projectId);
    ensureCurrent(captured);
    final data = options!;
    Map<String, dynamic>? refs;
    await ownedDialog<bool>(
      context: context,
      builder: (_) => BusinessEditor(
        session: session,
        title: 'Kunden- und Projektbezug wählen',
        readAllowed: () => available,
        saveLabel: 'Bezüge und Zuständige prüfen',
        fields: [
          BusinessField(
            'customer_id',
            'Kunde',
            type: BusinessInput.choice,
            required: true,
            initial: widget.customerId ?? '',
            choices: {
              '': 'Bitte auswählen',
              for (final value in businessItems(data['customers']))
                '${value['id']}': '${value['name']}',
            },
          ),
          BusinessField(
            'project_id',
            'Bestehendes Projekt',
            type: BusinessInput.choice,
            initial: projectId ?? '',
            choices: {
              '': 'Zunächst ohne Projekt',
              for (final value in businessItems(data['projects']))
                '${value['id']}': '${value['name']}',
            },
          ),
        ],
        onSave: (values) async {
          refs = {
            ...?widget.origin,
            ...values,
            'project_id': values['project_id'] == ''
                ? null
                : values['project_id'],
          };
          await sources(refs!['customer_id'], refs!['project_id']);
        },
      ),
    );
    if (refs != null && current(captured)) await caseForm(refs: refs!);
  }

  Future<void> caseForm({
    Map<String, dynamic>? previous,
    Map<String, dynamic> refs = const {},
  }) async {
    if (previous != null) {
      refs = previous;
      await sources(previous['customer_id'], previous['project_id']);
    }
    guard(write: true);
    final data = options!,
        customer = businessItems(data['customers'])
            .where((value) => value['id'] == refs['customer_id'])
            .firstOrNull;
    final origins = {
      '': 'Kein einzelner Eingang',
      for (final value in businessItems(data['inquiries']))
        'inquiry:${value['id']}': 'Anfrage: ${value['subject']}',
      for (final value in businessItems(data['defects']))
        'defect:${value['id']}': 'Mangel: ${value['title']}',
      for (final value in businessItems(data['visits']))
        'visit:${value['id']}':
            'Wartung: ${value['asset_snapshot']?['name'] ?? value['id']} · ${businessDate(value['due_date'])}',
    };
    final origin = [
      'inquiry',
      'defect',
      'visit',
    ].where((kind) => refs['${kind}_id'] != null).firstOrNull;
    final result = await edit(
      previous == null ? 'Servicefall anlegen' : 'Servicefall bearbeiten',
      'service-case-${previous?['id'] ?? 'new'}',
      '/service/cases',
      [
        if (previous == null) ...[
          BusinessField(
            'person_id',
            'Ansprechpartner',
            type: BusinessInput.choice,
            initial: refs['person_id'] ?? '',
            choices: {
              '': 'Kein einzelner Ansprechpartner',
              for (final value in businessItems(
                customer?['persons'] ?? const [],
              ))
                '${value['id']}': '${value['name']}',
            },
          ),
          BusinessField(
            'origin',
            'Ursprünglicher Eingang',
            type: BusinessInput.choice,
            initial: origin == null ? '' : '$origin:${refs['${origin}_id']}',
            choices: origins,
          ),
          BusinessField(
            'asset_id',
            'Kundenanlage',
            type: BusinessInput.choice,
            initial: refs['asset_id'] ?? '',
            choices: {
              '': 'Keine Kundenanlage',
              for (final value in businessItems(data['assets']))
                '${value['id']}': '${value['name']}',
            },
          ),
          BusinessField(
            'contract_id',
            'Wartungsvertrag',
            type: BusinessInput.choice,
            initial: refs['contract_id'] ?? '',
            choices: {
              '': 'Kein Vertrag',
              for (final value in businessItems(data['contracts']))
                '${value['id']}': '${value['title']}',
            },
          ),
        ],
        BusinessField(
          'title',
          'Betreff',
          required: true,
          initial: previous?['title'] ?? refs['title'],
        ),
        BusinessField(
          'kind',
          'Fallart',
          type: BusinessInput.choice,
          initial: previous?['kind'] ?? refs['kind'] ?? 'request',
          choices: serviceKinds,
        ),
        BusinessField(
          'priority',
          'Priorität',
          type: BusinessInput.choice,
          initial: previous?['priority'] ?? 'normal',
          choices: servicePriorities,
        ),
        BusinessField(
          'responsible_id',
          'Verantwortlich',
          type: BusinessInput.choice,
          required: true,
          initial: previous?['responsible_id'] ?? '',
          choices: {
            '': 'Bitte auswählen',
            for (final value in businessItems(data['responsibles']))
              '${value['id']}': '${value['email']}',
          },
        ),
        BusinessField(
          'follow_up_on',
          'Nächste Wiedervorlage',
          type: BusinessInput.date,
          initial: previous?['follow_up_on'],
        ),
        BusinessField(
          'description',
          'Problembeschreibung',
          type: BusinessInput.multiline,
          required: true,
          initial: previous?['description'] ?? refs['description'],
        ),
      ],
      (values) {
        if (previous != null)
          return serviceCaseValues(values, previous, previous: previous);
        final common = Map<String, dynamic>.from(values);
        final selectedOrigin = '${common.remove('origin') ?? ''}'.split(':'),
            person = common.remove('person_id'),
            asset = common.remove('asset_id'),
            contract = common.remove('contract_id');
        final visit = selectedOrigin.first == 'visit'
            ? businessItems(data['visits'])
                  .where((value) => value['id'] == selectedOrigin.last)
                  .firstOrNull
            : null;
        return serviceCaseValues(common, {
          ...refs,
          'person_id': person,
          'asset_id': asset == '' ? (visit?['asset_id']) : asset,
          'contract_id': contract == '' ? (visit?['contract_id']) : contract,
          'inquiry_id': selectedOrigin.first == 'inquiry'
              ? selectedOrigin.last
              : null,
          'defect_id': selectedOrigin.first == 'defect'
              ? selectedOrigin.last
              : null,
          'visit_id': selectedOrigin.first == 'visit'
              ? selectedOrigin.last
              : null,
        });
      },
    );
    if (result != null && mounted) {
      selectedId = businessMap(result)['id'];
      await load();
    }
  }

  Future<void> eventForm([Map<String, dynamic>? previous]) async {
    final item = selected!;
    final result = await edit(
      previous == null
          ? 'Aktivität dokumentieren'
          : 'Aktivität begründet korrigieren',
      'service-event-${previous?['id'] ?? item['id']}',
      '/service/cases/${item['id']}/events',
      [
        BusinessField(
          'kind',
          'Kontaktart',
          type: BusinessInput.choice,
          initial: previous?['kind'] ?? 'note',
          choices: const {
            'note': 'Notiz',
            'call': 'Telefonat',
            'email': 'E-Mail dokumentieren',
            'meeting': 'Besprechung',
          },
        ),
        BusinessField(
          'occurred_on',
          'Tatsächlicher Kontakttag',
          type: BusinessInput.date,
          required: true,
          initial:
              previous?['occurred_on'] ??
              DateTime.now().toIso8601String().substring(0, 10),
        ),
        BusinessField(
          'text',
          'Inhalt',
          type: BusinessInput.multiline,
          required: true,
          initial: previous?['text'],
          hint: 'E-Mail dokumentieren versendet keine Nachricht.',
        ),
        if (previous != null)
          const BusinessField(
            'correction_reason',
            'Korrekturgrund',
            type: BusinessInput.multiline,
            required: true,
          ),
      ],
      (values) => {
        ...serviceBound(item),
        ...values,
        'supersedes_id': previous?['id'],
        'correction_reason': values['correction_reason'] ?? '',
      },
    );
    if (result != null) await load();
  }

  Future<void> transition() async {
    final item = selected!,
        choices = (item['allowed_transitions'] as List).cast<String>();
    final result = await edit(
      'Statusentscheidung festhalten',
      'service-transition-${item['id']}',
      '/service/cases/${item['id']}/transition',
      [
        BusinessField(
          'status',
          'Nächster Zustand',
          type: BusinessInput.choice,
          initial: choices.first,
          choices: {for (final value in choices) value: serviceStages[value]!},
        ),
        const BusinessField(
          'reason',
          'Begründung / Wiedereröffnungsgrund',
          type: BusinessInput.multiline,
          required: true,
        ),
        BusinessField(
          'resolution',
          'Dokumentierte Lösung',
          type: BusinessInput.multiline,
          initial: item['resolution'],
          hint: 'Ein Status ist keine rechtliche Kundenabnahme oder Gewährleistungsentscheidung.',
        ),
      ],
      (values) => serviceTransitionValues(item, values),
    );
    if (result != null) await load();
  }

  Future<void> projectForm() async {
    final item = selected!;
    final result = await edit(
      'Kanonisches Projekt zuordnen',
      'service-project-${item['id']}',
      '/service/cases/${item['id']}/project',
      [
        BusinessField(
          'project_id',
          'Projektzuordnung',
          type: BusinessInput.choice,
          initial: '',
          choices: {
            '': 'Neues Projekt anlegen',
            for (final value in businessItems(
              options!['projects'],
            ).where((value) => value['customer_id'] == item['customer_id']))
              '${value['id']}': '${value['name']}',
          },
        ),
        BusinessField(
          'project_name',
          'Projektname bei Neuanlage',
          required: true,
          initial: item['title'],
        ),
        const BusinessField(
          'confirmation',
          'Ich bestätige den Kunden und die einmalige Projektzuordnung.',
          type: BusinessInput.toggle,
          required: true,
          initial: false,
        ),
      ],
      (values) => {
        ...serviceBound(item),
        ...values,
        'project_id': values['project_id'] == '' ? null : values['project_id'],
      },
    );
    if (result != null) await load();
  }

  Future<void> dispatch() async {
    final item = selected!;
    final result = await edit(
      'Serviceeinsatz disponieren',
      'service-dispatch-${item['id']}',
      '/service/cases/${item['id']}/dispatch',
      [
        BusinessField(
          'title',
          'Einsatzbezeichnung',
          required: true,
          initial: item['title'],
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
        const BusinessField(
          'timezone',
          'Einsatzzeitzone (IANA)',
          initial: 'Europe/Berlin',
          required: true,
        ),
        BusinessField(
          'employee_ids',
          'Mitarbeiter',
          type: BusinessInput.multiple,
          choices: {
            for (final value in businessItems(options!['employees']))
              '${value['id']}': '${value['name']}',
          },
        ),
        BusinessField(
          'resource_ids',
          'Fahrzeuge, Maschinen und Werkzeuge',
          type: BusinessInput.multiple,
          choices: {
            for (final value in businessItems(options!['resources']))
              '${value['id']}': '${value['name']}',
          },
        ),
        const BusinessField(
          'details',
          'Einsatzbeschreibung',
          type: BusinessInput.multiline,
        ),
        const BusinessField(
          'confirmation',
          'Ich bestätige diesen Serviceeinsatz und die gewählten Mitarbeiter und Betriebsmittel.',
          type: BusinessInput.toggle,
          required: true,
          initial: false,
        ),
      ],
      (values) => {...serviceBound(item), ...values},
    );
    if (result != null) await load();
  }

  Future<void> evidence() async {
    final item = selected!, reports = businessItems(options!['reports']);
    if (reports.isEmpty)
      throw const ApiException(
        409,
        'Zuerst im bestehenden Projekt einen Servicebericht erfassen und unterzeichnen.',
      );
    final result = await edit(
      'Unterzeichneten Bericht zuordnen',
      'service-evidence-${item['id']}',
      '/service/cases/${item['id']}/evidence',
      [
        BusinessField(
          'report_id',
          'Unterzeichneter Servicebericht',
          type: BusinessInput.choice,
          required: true,
          initial: '',
          choices: {
            '': 'Bitte auswählen',
            for (final value in reports) '${value['id']}': '${value['title']}',
          },
        ),
        const BusinessField(
          'confirmation',
          'Ich bestätige den unveränderten Bericht für diesen Fall und gegebenenfalls den Wartungsabschluss.',
          type: BusinessInput.toggle,
          required: true,
          initial: false,
        ),
      ],
      (values) => {...serviceBound(item), ...values},
    );
    if (result != null) await load();
  }

  Future<void> resolvePending(String key, String action) async {
    final path = action == 'case'
        ? '/service/cases'
        : '/service/cases/$selectedId/$action';
    final original = session.pendingCommandValues(key, path: path);
    if (original == null) return;
    final result = await edit(
      'Ursprüngliche Serviceantwort erneut prüfen',
      key,
      path,
      [
        BusinessField(
          'original',
          'Unveränderter ursprünglicher Auftrag',
          type: BusinessInput.multiline,
          initial: original.toString(),
        ),
      ],
      (_) => original,
    );
    if (result != null) await load();
  }

  Future<void> openProject() async {
    guard();
    final captured = epoch;
    final id = selected!['project_id'];
    final projects = businessItems(await session.api.call('/api/projects')),
        project = projects.where((value) => value['id'] == id).firstOrNull;
    ensureCurrent(captured);
    guard();
    if (project == null)
      throw const ApiException(
        403,
        'Das verknüpfte Projekt ist nicht mehr freigegeben.',
      );
    widget.onProject?.call(project);
  }

  Future<void> reportOriginal(Map<String, dynamic> link) async {
    guard();
    final captured = epoch,
        item = selected!,
        current = await get('/service-reports/${link['target_id']}');
    if (current['project_id'] != item['project_id'] ||
        current['status'] != 'signed' ||
        !_hash(current['pdf_sha256']))
      throw const ApiException(
        409,
        'Unterzeichneter Projektnachweis ist nicht bestätigt.',
      );
    final bytes = await session.api.bytes(
      session.path('/service-reports/${link['target_id']}/pdf'),
      mediaType: 'application/pdf',
    );
    final digest = (await Sha256().hash(bytes)).bytes
        .map((value) => value.toRadixString(16).padLeft(2, '0'))
        .join();
    ensureCurrent(captured);
    await sources(item['customer_id'], item['project_id']);
    await get('/service/cases/${item['id']}');
    ensureCurrent(captured);
    guard();
    if (captured != epoch || digest != current['pdf_sha256'])
      throw const ApiException(
        0,
        'Original stimmt nicht mit dem unterzeichneten Nachweis überein.',
      );
    await (widget.exporter ?? exportMailAttachment)(
      context,
      VerifiedMailAttachment(
        bytes: bytes,
        filename: 'Servicebericht.pdf',
        mediaType: 'application/pdf',
        sha256: digest,
      ),
      () => mounted && readable && epoch == captured,
    );
  }

  Future<void> linkDetail(Map<String, dynamic> link) async {
    final captured = epoch;
    await get('/service/cases/$selectedId');
    ensureCurrent(captured);
    Map<String, dynamic>? current;
    if (link['kind'] == 'appointment')
      current = await get('/appointments/${link['target_id']}');
    if (link['kind'] == 'report')
      current = await get('/service-reports/${link['target_id']}');
    ensureCurrent(captured);
    await ownedDialog<void>(
      context: context,
      builder: (_) => ListenableBuilder(
        listenable: scope!,
        builder: (_, __) => AlertDialog(
          title: const Text('Gebundener Nachweis'),
          content: SizedBox(
            width: 650,
            child: SingleChildScrollView(
              child: !readable || captured != epoch
                  ? const Notice('Quellzugang wurde entzogen.')
                  : Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        const Notice(
                          'Dieser gespeicherte Quellenstand bleibt mit dem Fall verbunden.',
                        ),
                        values(businessMap(link['source_snapshot'])),
                        if (current != null)
                          Text(
                            'Aktueller Fachstand: ${current['status'] ?? current['title'] ?? current['id']}',
                          ),
                        if (link['kind'] == 'report')
                          OutlinedButton(
                            onPressed: () =>
                                attempt(() => reportOriginal(link)),
                            child: const Text(
                              'Unterzeichnetes Original öffnen',
                            ),
                          ),
                      ],
                    ),
            ),
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(context),
              child: const Text('Schließen'),
            ),
          ],
        ),
      ),
    );
  }

  Widget values(Map<String, dynamic> value) => Column(
    crossAxisAlignment: CrossAxisAlignment.start,
    children: [
      for (final entry in value.entries.where(
        (entry) =>
            entry.value == null || entry.value is! Map && entry.value is! List,
      ))
        Padding(
          padding: const EdgeInsets.symmetric(vertical: 4),
          child: SelectableText(
            '${entry.key}: ${entry.value ?? 'Nicht angegeben'}',
          ),
        ),
    ],
  );
  Widget section(String title, List<Widget> children) => Card(
    child: Padding(
      padding: const EdgeInsets.all(20),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Text(title, style: Theme.of(context).textTheme.titleLarge),
          const SizedBox(height: 12),
          ...children,
        ],
      ),
    ),
  );
  Widget detail() {
    final item = selected!,
        events = businessItems(history?['events'] ?? const []),
        links = businessItems(item['links']);
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Text(item['title'], style: Theme.of(context).textTheme.headlineMedium),
        Text(
          '${item['customer_name']} · ${serviceKinds[item['kind']]} · ${serviceStages[item['status']]} · ${servicePriorities[item['priority']]}',
        ),
        Text(
          '${item['responsible_name']} · Wiedervorlage ${businessDate(item['follow_up_on'])}${item['overdue'] == true ? ' · Überfällig' : ''} · Fassung ${item['revision']}',
        ),
        Notice(item['description']),
        if ('${item['resolution'] ?? ''}'.isNotEmpty)
          section('Dokumentierte Lösung', [Text(item['resolution'])]),
        for (final action in [
          'case',
          'events',
          'project',
          'dispatch',
          'evidence',
          'transition',
        ])
          if (session.pending(
            'service-${action == 'events' ? 'event' : action}-${item['id']}',
          ))
            OutlinedButton(
              onPressed: writable
                  ? () => attempt(
                      () => resolvePending(
                        'service-${action == 'events' ? 'event' : action}-${item['id']}',
                        action,
                      ),
                    )
                  : null,
              child: const Text('Ursprüngliche Serviceantwort prüfen'),
            ),
        for (final event in events)
          if (session.pending('service-event-${event['id']}'))
            OutlinedButton(
              onPressed: writable
                  ? () => attempt(
                      () => resolvePending(
                        'service-event-${event['id']}',
                        'events',
                      ),
                    )
                  : null,
              child: const Text('Ursprüngliche Korrekturantwort prüfen'),
            ),
        Wrap(
          spacing: 8,
          runSpacing: 8,
          children: [
            if (writable)
              OutlinedButton(
                onPressed: () => attempt(() => caseForm(previous: item)),
                child: const Text('Fall bearbeiten'),
              ),
            if (writable)
              OutlinedButton(
                onPressed: () => attempt(eventForm),
                child: const Text('Aktivität dokumentieren'),
              ),
            if (writable && (item['allowed_transitions'] as List).isNotEmpty)
              FilledButton(
                onPressed: () => attempt(transition),
                child: const Text('Status und Lösung'),
              ),
            if (item['project_id'] != null && widget.onProject != null)
              OutlinedButton(
                onPressed: () => attempt(openProject),
                child: const Text('Projekt und Erfassung öffnen'),
              ),
            if (item['project_id'] == null &&
                writable &&
                scope!.canWrite('projects.manage') &&
                !['resolved', 'closed', 'cancelled'].contains(item['status']))
              OutlinedButton(
                onPressed: () => attempt(projectForm),
                child: const Text('Projekt zuordnen'),
              ),
            if (session.hasFeature('resource_custody') &&
                session.hasModule('resource_custody') &&
                session.can('planning.read'))
              OutlinedButton(
                onPressed: () => attempt(
                  () => openResourceCustody(
                    context,
                    session,
                    projectId: item['project_id'],
                  ),
                ),
                child: const Text('Betriebsmittel und Nachweise'),
              ),
            if (item['project_id'] != null &&
                writable &&
                scope!.canWrite('planning.write') &&
                scope!.sectionEnabled('planning') &&
                !['resolved', 'closed', 'cancelled'].contains(item['status']))
              FilledButton(
                onPressed: () => attempt(dispatch),
                child: const Text('Serviceeinsatz disponieren'),
              ),
            if (item['project_id'] != null &&
                writable &&
                scope!.sectionEnabled('documents') &&
                !['resolved', 'closed', 'cancelled'].contains(item['status']))
              OutlinedButton(
                onPressed: () => attempt(evidence),
                child: const Text('Unterzeichneten Bericht zuordnen'),
              ),
          ],
        ),
        section('Gebundene Quellen und Fachvorgänge', [
          for (final link in links)
            ListTile(
              title: Text(
                const {
                      'project': 'Projekt',
                      'asset': 'Kundenanlage',
                      'contract': 'Wartungsvertrag',
                      'visit': 'Wartungsbesuch',
                      'inquiry': 'Anfrage',
                      'defect': 'Projektmangel',
                      'appointment': 'Disponierter Einsatz',
                      'report': 'Unterzeichneter Bericht',
                    }[link['kind']] ??
                    link['kind'],
              ),
              subtitle: Text(
                '${link['source_snapshot']?['title'] ?? link['source_snapshot']?['name'] ?? link['target_id']}',
              ),
              trailing: const Icon(Icons.chevron_right),
              onTap: () => attempt(() => linkDetail(link)),
            ),
        ]),
        section('Aktivitäten', [
          const Text(
            'Ein E-Mail-Eintrag dokumentiert einen Kontakt und verschickt keine Nachricht.',
          ),
          for (final event in events)
            Card(
              child: ListTile(
                title: Text(
                  const {
                        'note': 'Notiz',
                        'call': 'Telefonat',
                        'email': 'E-Mail dokumentiert',
                        'meeting': 'Besprechung',
                      }[event['kind']] ??
                      event['kind'],
                ),
                subtitle: Text(
                  '${businessDate(event['occurred_on'] ?? event['created_at'], time: true)}\n${event['text'] ?? event['reason'] ?? ''}',
                ),
                trailing:
                    writable &&
                        [
                          'note',
                          'call',
                          'email',
                          'meeting',
                        ].contains(event['kind']) &&
                        !events.any(
                          (value) => value['supersedes_id'] == event['id'],
                        )
                    ? TextButton(
                        onPressed: () => attempt(() => eventForm(event)),
                        child: const Text('Korrigieren'),
                      )
                    : null,
              ),
            ),
        ]),
        section('Vollständiger Fallverlauf', [
          for (final version in businessItems(history?['versions'] ?? const []))
            ExpansionTile(
              title: Text(
                'Fassung ${version['revision']} · ${serviceStages[version['status']]}',
              ),
              subtitle: Text('${version['title']}'),
              children: [
                values({
                  'Verantwortlich':
                      version['responsible_name'] ?? version['responsible_id'],
                  'Wiedervorlage': businessDate(version['follow_up_on']),
                  'Lösung': version['resolution'],
                  'Gespeichert': businessDate(
                    version['updated_at'],
                    time: true,
                  ),
                }),
              ],
            ),
        ]),
      ],
    );
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(
      title: const Text('Kundenservice'),
      actions: [
        if (available)
          IconButton(
            onPressed: load,
            icon: const Icon(Icons.refresh),
            tooltip: 'Neu laden',
          ),
      ],
    ),
    body: !available
        ? const Center(
            child: Text('Der Servicezugang ist nicht mehr verfügbar.'),
          )
        : ListView(
            padding: const EdgeInsets.all(24),
            children: [
              if (error != null) Notice(error!, error: true),
              if (loading) const LinearProgressIndicator(),
              if (selectedId != null)
                TextButton(
                  onPressed: () {
                    selectedId = null;
                    selected = null;
                    history = null;
                    load();
                  },
                  child: const Text('Zur Fallübersicht'),
                ),
              if (selectedId == null) ...[
                if (listing != null)
                  Notice(
                    '${listing!['summary']['open_count']} offene Fälle · ${listing!['summary']['overdue_count']} Wiedervorlagen überfällig',
                  ),
                TextField(
                  controller: search,
                  decoration: const InputDecoration(
                    labelText: 'Betreff oder Kunde suchen',
                  ),
                  onSubmitted: (_) => load(),
                ),
                DropdownButtonFormField<String>(
                  initialValue: status,
                  decoration: const InputDecoration(labelText: 'Fallstatus'),
                  items: [
                    const DropdownMenuItem(
                      value: '',
                      child: Text('Alle Zustände'),
                    ),
                    for (final entry in serviceStages.entries)
                      DropdownMenuItem(
                        value: entry.key,
                        child: Text(entry.value),
                      ),
                  ],
                  onChanged: (value) {
                    status = value ?? '';
                    load();
                  },
                ),
                DropdownButtonFormField<String>(
                  initialValue: priority,
                  decoration: const InputDecoration(labelText: 'Priorität'),
                  items: [
                    const DropdownMenuItem(
                      value: '',
                      child: Text('Alle Prioritäten'),
                    ),
                    for (final entry in servicePriorities.entries)
                      DropdownMenuItem(
                        value: entry.key,
                        child: Text(entry.value),
                      ),
                  ],
                  onChanged: (value) {
                    priority = value ?? '';
                    load();
                  },
                ),
                DropdownButtonFormField<String>(
                  initialValue: responsible,
                  decoration: const InputDecoration(labelText: 'Zuständigkeit'),
                  items: [
                    const DropdownMenuItem(
                      value: '',
                      child: Text('Alle Zuständigen'),
                    ),
                    for (final value in filterResponsibles)
                      DropdownMenuItem(
                        value: '${value['id']}',
                        child: Text('${value['email']}'),
                      ),
                  ],
                  onChanged: (value) {
                    responsible = value ?? '';
                    load();
                  },
                ),
                SwitchListTile(
                  title: const Text('Nur überfällige Wiedervorlagen'),
                  value: due == 'overdue',
                  onChanged: (value) {
                    due = value ? 'overdue' : '';
                    load();
                  },
                ),
                if (!session.readonly)
                  FilledButton(
                    onPressed: () => attempt(choose),
                    child: const Text('Servicefall anlegen'),
                  ),
                for (final item in businessItems(listing ?? const []))
                  Card(
                    child: ListTile(
                      title: Text(item['title']),
                      subtitle: Text(
                        '${item['customer_name']} · ${serviceStages[item['status']]} · ${servicePriorities[item['priority']]}\n${item['responsible_name']} · ${businessDate(item['follow_up_on'])}${item['overdue'] == true ? ' · Überfällig' : ''}',
                      ),
                      trailing: const Icon(Icons.chevron_right),
                      onTap: () {
                        selectedId = item['id'];
                        load();
                      },
                    ),
                  ),
              ] else if (selected != null && readable)
                detail(),
            ],
          ),
  );
}

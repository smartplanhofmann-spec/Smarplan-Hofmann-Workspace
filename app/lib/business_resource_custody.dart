import 'dart:convert';

import 'package:cryptography/cryptography.dart';
import 'package:file_selector/file_selector.dart';
import 'package:flutter/material.dart';

import 'api.dart';
import 'business_session.dart';
import 'business_widgets.dart';
import 'design.dart';
import 'mail_attachment_widgets.dart';

const custodyConditions = {
  'unknown': 'Zustand ungeklärt',
  'serviceable': 'Einsatzfähig dokumentiert',
  'restricted': 'Eingeschränkt / gesperrt',
  'out_of_service': 'Außer Betrieb',
};
const custodyResults = {
  'passed': 'Bestanden dokumentiert',
  'failed': 'Nicht bestanden',
  'review_required': 'Weitere Prüfung erforderlich',
};
const custodyKinds = {
  'vehicle': 'Fahrzeug',
  'machine': 'Maschine',
  'tool': 'Werkzeug',
};
bool _id(Object? value) => RegExp(r'^[a-f0-9]{32}$').hasMatch('$value');
bool _hash(Object? value) => RegExp(r'^[a-f0-9]{64}$').hasMatch('$value');
String _hex(List<int> bytes) =>
    bytes.map((value) => value.toRadixString(16).padLeft(2, '0')).join();
Map<String, dynamic> custodyBound(Map<String, dynamic> item) {
  if (!_id(item['id']) ||
      item['resource']?['id'] != item['id'] ||
      !_hash(item['source_sha256']))
    throw const FormatException(
      'Den aktuellen Stand der kanonischen Ressource zuerst laden.',
    );
  return {'source_sha256': item['source_sha256']};
}

Map<String, dynamic> custodyHandoffValues(
  Map<String, dynamic> item,
  Map<String, dynamic> values,
) {
  final result = {...custodyBound(item), ...values};
  for (final key in [
    'employee_id',
    'project_id',
    'expected_return_at',
    'evidence_id',
  ]) {
    if (result[key] == '') result[key] = null;
  }
  if (result['employee_id'] == null && result['project_id'] == null)
    throw const FormatException(
      'Mitarbeiter oder Projekt ausdrücklich zuordnen.',
    );
  if (item['state']?['open_handoff'] != null)
    throw const FormatException('Die vorherige Ausgabe zuerst zurücknehmen.');
  return result;
}

Map<String, dynamic> custodyReceipt(
  String path,
  Map<String, dynamic> body,
  dynamic value, {
  String? originalSha256,
}) {
  final match = RegExp(
    r'^/resource-custody/([a-f0-9]{32})/(profile|requirements|files|inspections|handoffs|returns|corrections)$',
  ).firstMatch(path);
  if (match == null)
    throw const ApiException(0, 'Unbekannte Betriebsmittelquittung.');
  final response = businessMap(value),
      action = match.group(2),
      record = action == 'files' ? response : businessMap(response['record']);
  if (record['resource_id'] != match.group(1))
    throw const ApiException(0, 'Quittung gehört zu einer anderen Ressource.');
  if (action == 'files') {
    if (!_id(record['id']) ||
        !_hash(record['sha256']) ||
        record['filename'] != body['filename'] ||
        record['size'] != base64Decode(body['content_base64']).length ||
        originalSha256 != null && record['sha256'] != originalSha256)
      throw const ApiException(0, 'Original nicht unverändert bestätigt.');
    return response;
  }
  final item = businessMap(response['resource']);
  custodyBound(item);
  if (item['id'] != match.group(1))
    throw const ApiException(0, 'Falsche Ressourcenfassung.');
  if (['profile', 'requirements'].contains(action) &&
      record['revision'] != body['revision'] + 1)
    throw const ApiException(0, 'Neue Fassung wurde nicht bestätigt.');
  if (action == 'requirements' &&
      body['id'] != null &&
      record['id'] != body['id'])
    throw const ApiException(0, 'Falsche Anforderung.');
  final fields =
      const {
        'profile': ['serial_number', 'condition'],
        'requirements': ['title', 'active', 'required_for_use'],
        'inspections': [
          'requirement_id',
          'requirement_revision',
          'result',
          'evidence_id',
          'supersedes_id',
        ],
        'handoffs': ['employee_id', 'project_id', 'condition'],
        'returns': ['handoff_id', 'condition'],
        'corrections': ['target_id', 'reason'],
      }[action] ??
      [];
  if (fields.any((key) => record[key] != body[key]))
    throw const ApiException(
      0,
      'Quittung bestätigt die ursprüngliche Eingabe nicht.',
    );
  return response;
}

Future<void> openResourceCustody(
  BuildContext context,
  BusinessSession parent, {
  String? projectId,
}) async {
  final global = parent.sharedGlobalSession();
  await global.load();
  if (!context.mounted) return;
  if (global.error != null ||
      global.loading ||
      !global.ready ||
      !global.allowed ||
      !global.can('planning.read') ||
      !global.can('planning.write') ||
      !global.hasFeature('resource_custody') ||
      !global.hasModule('resource_custody'))
    throw const ApiException(403, 'Globale Betriebsmittelfreigabe fehlt.');
  await Navigator.of(context).push(
    MaterialPageRoute<void>(
      builder: (_) => BusinessResourceCustodyPage(
        session: global,
        projectId: projectId ?? parent.projectId,
      ),
    ),
  );
}

class BusinessResourceCustodyPage extends StatefulWidget {
  const BusinessResourceCustodyPage({
    super.key,
    required this.session,
    this.projectId,
    this.resourceId,
    this.pickFile,
    this.exporter,
  });
  final BusinessSession session;
  final String? projectId, resourceId;
  final Future<XFile?> Function()? pickFile;
  final MailAttachmentExporter? exporter;
  @override
  State<BusinessResourceCustodyPage> createState() =>
      _BusinessResourceCustodyPageState();
}

class _BusinessResourceCustodyPageState
    extends State<BusinessResourceCustodyPage>
    with WidgetsBindingObserver {
  BusinessSession get session => widget.session;
  Map<String, dynamic>? selected, options, caps;
  List<Map<String, dynamic>> listing = [];
  String? selectedId, error;
  bool loading = false;
  int epoch = 0;
  Object? generation;
  Set<String> rights = {};
  String? token, baseUrl;
  bool backgrounded = false;
  final Map<Route<dynamic>, NavigatorState> ownedDialogs = {};
  bool get available =>
      !backgrounded &&
      session.allowed &&
      session.hasFeature('resource_custody') &&
      session.hasModule('resource_custody');
  bool get readable =>
      available &&
      [
        'planning.read',
        'planning.write',
      ].every((right) => (caps?['permissions'] as List? ?? []).contains(right));
  bool get writable =>
      readable &&
      !session.readonly &&
      session.sectionEnabled('planning') &&
      caps?['readonly'] == false &&
      (!((caps?['features'] as List? ?? []).contains('organization_modules')) ||
          caps?['organization']?['modules']?['planning']?['enabled'] == true);
  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    token = session.api.token;
    baseUrl = session.api.base;
    selectedId = widget.resourceId;
    generation = session.generation;
    rights = Set.of(session.permissions);
    session.addListener(changed);
    load();
  }

  bool current(int captured) => mounted && !backgrounded && captured == epoch;

  void ensureCurrent(int captured) {
    if (!current(captured))
      throw const ApiException(
        0,
        'Der Betriebsmittelkontext wurde geschlossen.',
      );
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
    selected = options = caps = null;
    listing = [];
    loading = false;
    error = null;
  }

  @override
  void didUpdateWidget(covariant BusinessResourceCustodyPage old) {
    super.didUpdateWidget(old);
    if (!identical(old.session, session) ||
        old.projectId != widget.projectId ||
        old.resourceId != widget.resourceId) {
      old.session.removeListener(changed);
      clearPrivate();
      selectedId = widget.resourceId;
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
    super.dispose();
  }

  void changed() {
    if (!mounted) return;
    if (!available ||
        token != session.api.token ||
        baseUrl != session.api.base ||
        generation != session.generation ||
        !session.permissions.containsAll(rights)) {
      clearPrivate();
    }
    token = session.api.token;
    baseUrl = session.api.base;
    generation = session.generation;
    rights = Set.of(session.permissions);
    setState(() {});
  }

  void guard({bool write = false}) {
    if (!mounted || !readable || (write && !writable))
      throw const ApiException(
        403,
        'Aktuelle globale Betriebsmittelfreigabe fehlt.',
      );
  }

  Future<void> attempt(Future<void> Function() fn) async {
    final captured = epoch;
    try {
      await fn();
    } catch (value) {
      if (current(captured)) setState(() => error = '$value');
    }
  }

  Future<Map<String, dynamic>> get(String path) async {
    final captured = epoch;
    if (!available)
      throw const ApiException(403, 'Betriebsmittelfreigabe fehlt.');
    try {
      final value = businessMap(await session.read(path));
      if (!mounted || captured != epoch || !available)
        throw const ApiException(0, 'Sitzung geändert.');
      return value;
    } on ApiException catch (e) {
      if ([401, 403, 404].contains(e.status) && current(captured)) {
        setState(() {
          clearPrivate();
        });
      }
      rethrow;
    }
  }

  Future<void> load() async {
    if (!available) return;
    final captured = ++epoch;
    setState(() {
      loading = true;
      error = null;
    });
    try {
      final current = await get('/capabilities');
      caps = current;
      guard();
      final choices = await get('/resource-custody/options');
      final data = await get(
        '/resource-custody${selectedId == null ? '' : '/$selectedId'}',
      );
      await session.load();
      ensureCurrent(captured);
      if (session.error != null)
        throw const ApiException(403, 'Aktuelle Betriebsmittelrechte fehlen.');
      caps = await get('/capabilities');
      guard();
      if (mounted && captured == epoch)
        setState(() {
          options = choices;
          if (selectedId == null) {
            listing = businessItems(data);
            selected = null;
          } else {
            custodyBound(data);
            if (data['id'] != selectedId)
              throw const ApiException(0, 'Falsche Ressource.');
            selected = data;
          }
        });
    } catch (value) {
      if (current(captured))
        setState(() {
          if (value is ApiException && [401, 403, 404].contains(value.status)) {
            clearPrivate();
            error =
                'Der globale Betriebsmittelzugang ist nicht mehr freigegeben.';
          } else {
            error = '$value';
          }
        });
    } finally {
      if (mounted && captured == epoch) setState(() => loading = false);
    }
  }

  List<Map<String, dynamic>> items(Object? value) =>
      businessItems(value ?? const []);
  BusinessField confirm(String label) => BusinessField(
    'confirmation',
    label,
    type: BusinessInput.toggle,
    initial: false,
    required: true,
  );
  BusinessField condition([Object? value]) => BusinessField(
    'condition',
    'Dokumentierter Zustand',
    type: BusinessInput.choice,
    choices: custodyConditions,
    initial: value ?? 'unknown',
  );
  BusinessField evidence({bool required = false}) => BusinessField(
    'evidence_id',
    'Unveränderlicher Originalnachweis',
    type: BusinessInput.choice,
    required: required,
    initial: '',
    choices: {
      '': 'Kein Original zuordnen',
      for (final file in items(selected?['files']))
        '${file['id']}': '${file['filename']}',
    },
  );
  Map<String, dynamic> nullable(
    Map<String, dynamic> values,
    List<String> keys,
  ) => {
    ...values,
    for (final key in keys) key: values[key] == '' ? null : values[key],
  };
  Future<dynamic> edit(
    String title,
    String operation,
    List<BusinessField> fields,
    Map<String, dynamic> Function(Map<String, dynamic>) build, {
    String? key,
    String? originalSha256,
  }) async {
    guard();
    final captured = epoch, commandSession = session;
    var active = true;
    bool stillCurrent() => active && current(captured);
    final item = selected!, path = '/resource-custody/${item['id']}/$operation';
    key ??= 'resource-custody-$operation-${item['id']}';
    final commandKey = key;
    dynamic result;
    try {
      await ownedDialog<bool>(
        context: context,
        barrierDismissible: false,
        builder: (_) => BusinessEditor(
          session: commandSession,
          pendingKey: commandKey,
          readAllowed: () => stillCurrent() && readable,
          readPermission: 'planning.read',
          writePermission: 'planning.write',
          title: title,
          fields: fields,
          saveLabel: title,
          onSave: (values) async {
            ensureCurrent(captured);
            guard();
            if (commandSession.pending(commandKey)) {
              result = await commandSession.repeatResourceCustodyCommand(
                commandKey,
                stillCurrent: stillCurrent,
              );
              return;
            }
            guard(write: true);
            final body = build(values);
            result = await commandSession.command(
              commandKey,
              path,
              body,
              validateResult: (value) => custodyReceipt(
                path,
                body,
                value,
                originalSha256: originalSha256,
              ),
            );
          },
        ),
      );
    } finally {
      active = false;
    }
    if (!current(captured)) return null;
    if (result != null) await load();
    return result;
  }

  Future<void> nativeResource([Map<String, dynamic>? previous]) async {
    guard(write: true);
    final captured = epoch;
    final key = 'resource-native-${previous?['id'] ?? 'new'}';
    await ownedDialog<bool>(
      context: context,
      builder: (_) => BusinessEditor(
        session: session,
        pendingKey: key,
        readAllowed: () => readable,
        writePermission: 'planning.write',
        title: previous == null
            ? 'Planungsressource anlegen'
            : 'Planungsressource bearbeiten',
        fields: [
          BusinessField(
            'name',
            'Ressourcenname',
            required: true,
            initial: previous?['name'],
          ),
          BusinessField(
            'kind',
            'Ressourcenart',
            type: BusinessInput.choice,
            choices: custodyKinds,
            initial: previous?['kind'] ?? 'tool',
          ),
          BusinessField(
            'code',
            'Kanonischer Ressourcencode',
            initial: previous?['code'],
          ),
          BusinessField(
            'active',
            'Ressource aktiv',
            type: BusinessInput.toggle,
            initial: previous?['active'] ?? true,
          ),
        ],
        onSave: (values) async {
          ensureCurrent(captured);
          guard(write: true);
          await session.command(key, '/resources', {
            ...values,
            'code': values['code'] == '' ? null : values['code'],
            if (previous != null) 'id': previous['id'],
            if (previous != null) 'revision': previous['revision'],
          });
        },
      ),
    );
    if (current(captured)) await load();
  }

  Future<void> profile() async {
    final item = selected!, current = businessMap(item['profile']);
    await edit(
      'Profil und Zustand speichern',
      'profile',
      [
        for (final entry in {
          'serial_number': 'Serien-/Inventarnummer',
          'manufacturer': 'Hersteller',
          'model': 'Modell',
          'location': 'Standort',
        }.entries)
          BusinessField(entry.key, entry.value, initial: current[entry.key]),
        condition(item['state']['condition']),
        BusinessField(
          'notes',
          'Zustandsnotiz',
          type: BusinessInput.multiline,
          initial: current['notes'],
        ),
        const BusinessField(
          'reason',
          'Grund der neuen Profilfassung',
          type: BusinessInput.multiline,
          required: true,
        ),
        confirm('Ich bestätige diesen dokumentierten Zustand.'),
      ],
      (values) => {
        ...custodyBound(item),
        'revision': current['revision'] ?? 0,
        ...values,
      },
    );
  }

  Future<void> requirement([Map<String, dynamic>? previous]) async {
    final item = selected!;
    await edit(
      previous == null
          ? 'Anforderung verbindlich erfassen'
          : 'Anforderung versioniert ändern',
      'requirements',
      [
        BusinessField(
          'title',
          'Anforderungsbezeichnung',
          required: true,
          initial: previous?['title'],
        ),
        BusinessField(
          'due_on',
          'Explizite Fälligkeit',
          type: BusinessInput.date,
          initial: previous?['due_on'],
        ),
        BusinessField(
          'required_for_use',
          'Erfüllung ist Voraussetzung für die Nutzung',
          type: BusinessInput.toggle,
          initial: previous?['required_for_use'] ?? true,
        ),
        BusinessField(
          'active',
          'Anforderung aktiv',
          type: BusinessInput.toggle,
          initial: previous?['active'] ?? true,
        ),
        BusinessField(
          'notes',
          'Anforderungsbeschreibung',
          type: BusinessInput.multiline,
          initial: previous?['notes'],
        ),
        const BusinessField(
          'reason',
          'Grund / Aufhebungsgrund',
          type: BusinessInput.multiline,
          required: true,
        ),
        confirm('Ich bestätige diese konkrete Anforderung und Fälligkeit.'),
      ],
      (values) => {
        ...custodyBound(item),
        ...nullable(values, ['due_on']),
        'revision': previous?['revision'] ?? 0,
        if (previous != null) 'id': previous['id'],
      },
      key:
          'resource-custody-requirement-${item['id']}-${previous?['id'] ?? 'new'}',
    );
  }

  Future<void> inspection(
    Map<String, dynamic> requirement, [
    Map<String, dynamic>? previous,
  ]) async {
    final item = selected!;
    await edit(
      previous == null
          ? 'Prüfung mit Original dokumentieren'
          : 'Prüfaussage begründet korrigieren',
      'inspections',
      [
        const BusinessField(
          'performed_at',
          'Tatsächlicher Prüfzeitpunkt',
          type: BusinessInput.instant,
          required: true,
        ),
        BusinessField(
          'inspector',
          'Benannte prüfende Person',
          required: true,
          initial: previous?['inspector'],
        ),
        BusinessField(
          'result',
          'Dokumentiertes Prüfergebnis',
          type: BusinessInput.choice,
          choices: custodyResults,
          initial: previous?['result'] ?? 'review_required',
        ),
        const BusinessField(
          'next_due_on',
          'Ausdrücklich festgelegte nächste Fälligkeit',
          type: BusinessInput.date,
        ),
        evidence(required: true),
        const BusinessField(
          'note',
          'Prüfnotiz',
          type: BusinessInput.multiline,
          required: true,
        ),
        if (previous != null)
          const BusinessField(
            'correction_reason',
            'Grund der Korrektur',
            type: BusinessInput.multiline,
            required: true,
          ),
        confirm(
          'Ich bestätige die tatsächliche Prüfung und den ausgewählten Originalnachweis.',
        ),
      ],
      (values) => {
        ...custodyBound(item),
        ...nullable(values, ['next_due_on']),
        'requirement_id': requirement['id'],
        'requirement_revision': requirement['revision'],
        'supersedes_id': previous?['id'],
        'correction_reason': values['correction_reason'] ?? '',
      },
      key:
          'resource-custody-inspection-${item['id']}-${previous?['id'] ?? requirement['id']}',
    );
  }

  List<BusinessField> handoffFields([Map<String, dynamic>? previous]) => [
    BusinessField(
      'employee_id',
      'Tatsächlich empfangender Mitarbeiter',
      type: BusinessInput.choice,
      initial: previous?['employee_id'] ?? '',
      choices: {
        '': 'Nur Projektbindung',
        for (final value in items(
          options?['employees'],
        ).where((value) => value['active'] == true || value['active'] == 1))
          '${value['id']}': '${value['name']}',
      },
    ),
    BusinessField(
      'project_id',
      'Projektbindung der Ausgabe',
      type: BusinessInput.choice,
      initial:
          previous?['project_id'] ??
          widget.projectId ??
          session.projectId ??
          '',
      choices: {
        '': 'Ohne Projektbindung',
        for (final value in items(options?['projects']))
          '${value['id']}': '${value['name']}',
      },
    ),
    BusinessField(
      'issued_at',
      'Tatsächlicher Ausgabezeitpunkt',
      type: BusinessInput.instant,
      required: true,
      initial: previous?['issued_at'],
    ),
    BusinessField(
      'expected_return_at',
      'Erwartete Rückgabe',
      type: BusinessInput.instant,
      initial: previous?['expected_return_at'],
    ),
    condition(previous?['condition'] ?? selected?['state']?['condition']),
    BusinessField(
      'notes',
      'Ausgabezustand / Übergabenotiz',
      type: BusinessInput.multiline,
      required: true,
      initial: previous?['notes'],
    ),
    evidence(),
  ];
  List<BusinessField> returnFields([Map<String, dynamic>? previous]) => [
    BusinessField(
      'returned_at',
      'Tatsächlicher Rückgabezeitpunkt',
      type: BusinessInput.instant,
      required: true,
      initial: previous?['returned_at'],
    ),
    BusinessField(
      'received_by_employee_id',
      'Empfangender Mitarbeiter bei Rücknahme',
      type: BusinessInput.choice,
      initial: previous?['received_by_employee_id'] ?? '',
      choices: {
        '': 'Bearbeiter dokumentiert Rücknahme',
        for (final value in items(
          options?['employees'],
        ).where((value) => value['active'] == true || value['active'] == 1))
          '${value['id']}': '${value['name']}',
      },
    ),
    condition(previous?['condition']),
    BusinessField(
      'notes',
      'Rückgabezustand / Mängel',
      type: BusinessInput.multiline,
      required: true,
      initial: previous?['notes'],
    ),
    evidence(),
  ];
  Future<void> handoff() async {
    final item = selected!;
    await edit('Ausgabe ausdrücklich bestätigen', 'handoffs', [
      ...handoffFields(),
      confirm(
        'Ich bestätige diese tatsächliche Ausgabe an den gewählten Mitarbeiter beziehungsweise das Projekt.',
      ),
    ], (values) => custodyHandoffValues(item, values));
  }

  Future<void> returnHandoff() async {
    final item = selected!,
        handoff = businessMap(item['state']['open_handoff']);
    await edit(
      'Tatsächliche Rücknahme bestätigen',
      'returns',
      [
        ...returnFields(),
        confirm(
          'Ich bestätige die tatsächliche Rücknahme genau dieser offenen Ausgabe.',
        ),
      ],
      (values) => {
        ...custodyBound(item),
        ...nullable(values, ['received_by_employee_id', 'evidence_id']),
        'handoff_id': handoff['id'],
      },
    );
  }

  Future<void> correction(String kind, Map<String, dynamic> record) async {
    final item = selected!;
    final bound = kind == 'handoff'
        ? items(item['handoffs'])
              .where((value) => value['id'] == record['id'])
              .firstOrNull
        : items(item['handoffs'])
              .map((value) => businessMap(value['return']))
              .where((value) => value['id'] == record['id'])
              .firstOrNull;
    final effective = businessMap(bound?['effective']).isEmpty
        ? record
        : businessMap(bound?['effective']);
    await edit(
      'Übergabenachweis begründet korrigieren',
      'corrections',
      [
        ...(kind == 'handoff'
                ? handoffFields(effective)
                : returnFields(effective))
            .where((field) => field.name != 'evidence_id'),
        const BusinessField(
          'reason',
          'Grund der Korrektur',
          type: BusinessInput.multiline,
          required: true,
        ),
        evidence(required: true),
        confirm(
          'Ich bestätige die belegte Korrektur; der ursprüngliche Nachweis bleibt erhalten.',
        ),
      ],
      (values) {
        final data = Map<String, dynamic>.from(values)
          ..remove('reason')
          ..remove('confirmation')
          ..remove('evidence_id');
        return {
          ...custodyBound(item),
          'target_kind': kind,
          'target_id': record['id'],
          'values': {
            ...nullable(
              data,
              kind == 'handoff'
                  ? ['employee_id', 'project_id', 'expected_return_at']
                  : ['received_by_employee_id'],
            ),
            'evidence_id': effective['evidence_id'],
            if (kind == 'return') 'handoff_id': record['handoff_id'],
          },
          'reason': values['reason'],
          'evidence_id': values['evidence_id'],
          'confirmation': true,
        };
      },
      key: 'resource-custody-correction-${record['id']}',
    );
  }

  Future<void> upload() async {
    guard();
    final item = selected!,
        key = 'resource-custody-files-${selected!['id']}',
        path = '/resource-custody/${selected!['id']}/files';
    Map<String, dynamic>? body = session.pendingCommandValues(key, path: path);
    String? digest;
    if (body == null) {
      guard(write: true);
      final captured = epoch,
          file = await (widget.pickFile?.call() ?? openFile());
      if (file == null) return;
      guard(write: true);
      final length = await file.length();
      if (length < 1 || length > 2097152)
        throw const ApiException(413, 'Originaldatei bis 2 MiB wählen.');
      final bytes = await file.readAsBytes(),
          media = const {
            'pdf': 'application/pdf',
            'png': 'image/png',
            'jpg': 'image/jpeg',
            'jpeg': 'image/jpeg',
          }[file.name.split('.').last.toLowerCase()];
      guard(write: true);
      if (captured != epoch || bytes.length != length || media == null)
        throw const ApiException(409, 'Datei oder Sitzung ungültig.');
      digest = _hex((await Sha256().hash(bytes)).bytes);
      ensureCurrent(captured);
      body = {
        'filename': file.name,
        'media_type': media,
        'content_base64': base64Encode(bytes),
      };
    }
    await edit(
      'Original unverändert speichern: ${body['filename']}',
      'files',
      const [],
      (_) => body!,
      key: key,
      originalSha256: digest,
    );
    if (selected?['id'] != item['id'])
      throw const ApiException(0, 'Ressourcenauswahl geändert.');
  }

  Future<void> download(Map<String, dynamic> file) async {
    guard();
    final item = selected!, captured = epoch;
    await get('/resource-custody/${item['id']}');
    final bytes = await session.api.bytes(
      session.path(
        '/resource-custody/${item['id']}/files/${file['id']}/original',
      ),
      mediaType: 'application/octet-stream',
      maxBytes: 2097152,
    );
    ensureCurrent(captured);
    await get('/resource-custody/${item['id']}');
    guard();
    final digest = _hex((await Sha256().hash(bytes)).bytes);
    if (captured != epoch ||
        digest != file['sha256'] ||
        bytes.length != file['size'])
      throw const ApiException(0, 'Originalprüfsumme oder Freigabe geändert.');
    if (!mounted) return;
    await (widget.exporter ?? exportMailAttachment)(
      context,
      VerifiedMailAttachment(
        bytes: bytes,
        filename: file['filename'],
        mediaType: 'application/octet-stream',
        sha256: digest,
      ),
      () => mounted && readable && captured == epoch,
    );
  }

  Future<void> availability() async {
    guard();
    final captured = epoch;
    final item = selected!;
    Map<String, dynamic>? result;
    await ownedDialog<bool>(
      context: context,
      builder: (_) => BusinessEditor(
        session: session,
        title: 'Konkrete Verfügbarkeit prüfen',
        readAllowed: () => readable,
        saveLabel: 'Zeitraum prüfen',
        fields: [
          const BusinessField(
            'start_at',
            'Geplanter Beginn',
            type: BusinessInput.instant,
            required: true,
          ),
          const BusinessField(
            'end_at',
            'Geplantes Ende',
            type: BusinessInput.instant,
            required: true,
          ),
          const BusinessField(
            'timezone',
            'Zeitzone',
            initial: 'Europe/Berlin',
            required: true,
          ),
          BusinessField(
            'employee_id',
            'Geplanter Mitarbeiter',
            type: BusinessInput.choice,
            initial: '',
            choices: {
              '': 'Nicht zugeordnet',
              for (final value in items(options?['employees']))
                '${value['id']}': '${value['name']}',
            },
          ),
          BusinessField(
            'project_id',
            'Geplantes Projekt',
            type: BusinessInput.choice,
            initial: widget.projectId ?? session.projectId ?? '',
            choices: {
              '': 'Nicht zugeordnet',
              for (final value in items(options?['projects']))
                '${value['id']}': '${value['name']}',
            },
          ),
        ],
        onSave: (values) async {
          ensureCurrent(captured);
          guard();
          result = await get(
            '/resource-custody/${item['id']}/availability?${Uri(queryParameters: {for (final entry in values.entries)
              if (entry.value != null && entry.value != '') entry.key: '${entry.value}'}).query}',
          );
        },
      ),
    );
    if (result != null && current(captured))
      await showInfo('Ergebnis der Verfügbarkeitsprüfung', [
        Notice(
          result!['available'] == true
              ? 'Für Zeitraum und Zuordnung aktuell verfügbar.'
              : 'Für Zeitraum oder Zuordnung gesperrt.',
        ),
        for (final value in items(result!['blockers']))
          Notice('${value['message']}', error: true),
        const Text('Die tatsächliche Terminbuchung prüft den Zustand erneut.'),
      ]);
  }

  Future<void> showInfo(String title, List<Widget> children) async {
    guard();
    await ownedDialog<void>(
      context: context,
      builder: (_) => AnimatedBuilder(
        animation: session,
        builder: (context, _) => AlertDialog(
          title: Text(title),
          content: SizedBox(
            width: 600,
            child: SingleChildScrollView(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: readable
                    ? children
                    : [const Text('Freigabe nicht mehr verfügbar.')],
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

  List<Widget> recordFields(Map<String, dynamic> record) {
    const labels = {
      'revision': 'Fassung',
      'serial_number': 'Seriennummer',
      'manufacturer': 'Hersteller',
      'model': 'Modell',
      'location': 'Standort',
      'condition': 'Zustand',
      'notes': 'Zustandsnotiz',
      'reason': 'Begründung',
      'title': 'Anforderung',
      'due_on': 'Fälligkeit',
      'required_for_use': 'Nutzungsrelevant',
      'active': 'Aktiv',
      'inspector': 'Prüfende Person',
      'result': 'Ergebnis',
      'performed_at': 'Tatsächliche Prüfung',
      'next_due_on': 'Nächste Fälligkeit',
      'note': 'Prüfnotiz',
      'correction_reason': 'Korrekturgrund',
      'issued_at': 'Ausgabezeitpunkt',
      'expected_return_at': 'Erwartete Rückgabe',
      'returned_at': 'Rückgabezeitpunkt',
      'created_at': 'Dokumentiert',
      'target_kind': 'Korrigierte Nachweisart',
    };
    final widgets = <Widget>[];
    for (final entry in labels.entries) {
      final value = record[entry.key];
      if (value == null) continue;
      final displayed = entry.key == 'condition'
          ? custodyConditions[value]
          : entry.key == 'result'
          ? custodyResults[value]
          : entry.key.endsWith('_at') || entry.key.endsWith('_on')
          ? businessDate(value, time: entry.key.endsWith('_at'))
          : value is bool
          ? (value ? 'Ja' : 'Nein')
          : '$value';
      widgets.add(Text('${entry.value}: $displayed'));
    }
    const refs = {
      'employee_id': 'Empfänger',
      'received_by_employee_id': 'Rücknahme durch',
      'project_id': 'Projekt',
      'evidence_id': 'Originalbeleg',
    };
    for (final entry in refs.entries) {
      if (record[entry.key] == null) continue;
      Object? source;
      if (entry.key == 'project_id') {
        source = options?['projects'];
      } else if (entry.key == 'evidence_id') {
        source = selected?['files'];
      } else {
        source = options?['employees'];
      }
      final target = items(source)
          .where((value) => value['id'] == record[entry.key])
          .firstOrNull;
      final snapshotName = {
        'employee_id': record['employee_snapshot']?['name'],
        'received_by_employee_id': record['receiver_snapshot']?['name'],
        'project_id': record['project_snapshot']?['name'],
        'evidence_id': record['evidence_snapshot']?['filename'],
      }[entry.key];
      final label =
          snapshotName ??
          target?[entry.key == 'evidence_id' ? 'filename' : 'name'] ??
          record[entry.key];
      widgets.add(Text('${entry.value}: $label'));
    }
    return widgets;
  }

  Future<void> history() async {
    final item = selected!,
        value = await get('/resource-custody/${item['id']}/history');
    await showInfo('Betriebsmittelverlauf · ${item['resource']['name']}', [
      for (final entry in {
        'profiles': 'Profilfassungen',
        'requirements': 'Anforderungsfassungen',
        'inspections': 'Prüfaussagen',
        'handoffs': 'Ausgaben',
        'returns': 'Rücknahmen',
        'corrections': 'Begründete Ergänzungen',
      }.entries) ...[
        Text(entry.value, style: Theme.of(context).textTheme.titleLarge),
        for (final record in items(value[entry.key]))
          Card(
            child: Padding(
              padding: const EdgeInsets.all(12),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  ...recordFields(record),
                  if (record['values'] is Map) ...[
                    const Text('Belegte Berichtigung'),
                    ...recordFields(businessMap(record['values'])),
                  ],
                  if (writable &&
                      entry.key == 'inspections' &&
                      items(value['inspections'])
                              .where(
                                (other) =>
                                    other['requirement_id'] ==
                                    record['requirement_id'],
                              )
                              .lastOrNull?['id'] ==
                          record['id'])
                    TextButton(
                      onPressed: () {
                        Navigator.pop(context);
                        attempt(
                          () => inspection(
                            items(item['requirements']).firstWhere(
                              (requirement) =>
                                  requirement['id'] == record['requirement_id'],
                            ),
                            record,
                          ),
                        );
                      },
                      child: const Text('Prüfaussage korrigieren'),
                    ),
                  if (writable && ['handoffs', 'returns'].contains(entry.key))
                    TextButton(
                      onPressed: () {
                        Navigator.pop(context);
                        attempt(
                          () => correction(
                            entry.key == 'handoffs' ? 'handoff' : 'return',
                            record,
                          ),
                        );
                      },
                      child: const Text('Übergabenachweis korrigieren'),
                    ),
                ],
              ),
            ),
          ),
      ],
    ]);
  }

  Widget button(String label, Future<void> Function() fn) => OutlinedButton(
    onPressed: loading ? null : () => attempt(fn),
    child: Text(label),
  );
  Widget section(String title, List<Widget> children) => Card(
    child: Padding(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Text(title, style: Theme.of(context).textTheme.titleLarge),
          ...children,
        ],
      ),
    ),
  );
  @override
  Widget build(BuildContext context) {
    if (!available)
      return const Center(child: Text('Betriebsmittelzugang nicht verfügbar.'));
    final item = selected,
        profile = businessMap(item?['profile']),
        state = businessMap(item?['state']),
        handoff = {
          ...businessMap(state['open_handoff']),
          ...businessMap(state['open_handoff']?['effective']),
        };
    return Scaffold(
      appBar: AppBar(
        title: Text(
          item?['resource']?['name'] ?? 'Betriebsmittel und Nachweise',
        ),
        actions: [
          IconButton(
            onPressed: load,
            icon: const Icon(Icons.refresh),
            tooltip: 'Neu laden',
          ),
        ],
      ),
      body: ListView(
        padding: const EdgeInsets.all(20),
        children: [
          if (error != null) Notice(error!, error: true),
          if (loading) const LinearProgressIndicator(),
          if (!loading && !readable)
            const Notice(
              'Globale Lese- und Schreibrechte für Planung erforderlich.',
            ),
          if (readable && item == null) ...[
            const Notice(
              'Gemeinsame Fahrzeuge, Maschinen und Werkzeuge. Ein freier Kalender ersetzt keinen dokumentierten Zustand oder Prüfnachweis.',
            ),
            if (writable)
              button('Planungsressource anlegen', () => nativeResource()),
            for (final resource in listing)
              Card(
                child: ListTile(
                  title: Text('${resource['resource']['name']}'),
                  subtitle: Text(
                    '${custodyKinds[resource['resource']['kind']]} · ${custodyConditions[resource['state']['condition']]}${resource['state']['open_handoff'] != null ? ' · Ausgegeben' : ''}\n${items(resource['state']['blockers']).map((value) => value['message']).join(' · ')}',
                  ),
                  trailing: const Icon(Icons.chevron_right),
                  onTap: () {
                    selectedId = resource['id'];
                    load();
                  },
                ),
              ),
          ],
          if (readable && item != null) ...[
            section('Aktueller Ressourcenstand', [
              Text(
                'Code: ${item['resource']['code'] ?? 'Nicht angegeben'} · ${item['resource']['active'] == true ? 'Aktiv' : 'Inaktiv'}',
              ),
              Text(
                'Profilfassung ${profile['revision'] ?? 0} · ${profile['manufacturer'] ?? ''} ${profile['model'] ?? ''}',
              ),
              Text(
                'Seriennummer: ${profile['serial_number'] ?? 'Nicht angegeben'}',
              ),
              Text('Standort: ${profile['location'] ?? 'Nicht angegeben'}'),
              Text('Zustand: ${custodyConditions[state['condition']]}'),
              Text('${profile['notes'] ?? ''}'),
              Notice(
                state['inspection_knowledge'] == 'unconfigured'
                    ? 'Prüfanforderungen noch nicht erfasst. Keine bestandene Prüfung wird daraus abgeleitet.'
                    : state['available'] == true
                    ? 'Nach dokumentiertem Stand freigegeben. Konkreten Zeitraum separat prüfen.'
                    : 'Aktuelle Sperren beachten.',
              ),
              for (final blocker in items(state['blockers']))
                Notice('${blocker['message']}', error: true),
            ]),
            Wrap(
              spacing: 8,
              runSpacing: 8,
              children: [
                if (writable) ...[
                  button('Profil und Zustand', profileForm),
                  button(
                    'Planungsressource bearbeiten',
                    () => nativeResource(businessMap(item['resource'])),
                  ),
                  button('Anforderung hinzufügen', () => requirement()),
                  button('Originalnachweis hochladen', upload),
                  if (handoff.isEmpty)
                    button('Betriebsmittel ausgeben', this.handoff)
                  else
                    button('Ausgabe zurücknehmen', returnHandoff),
                ],
                button('Aktuellen Stand laden', load),
                button('Verfügbarkeit prüfen', availability),
                button('Vollständiger Verlauf', history),
              ],
            ),
            for (final pending in pendingEntries.entries.where(
              (value) => session.pending(value.key),
            ))
              button(
                'Offenen Originalauftrag prüfen',
                () => resolvePending(pending.key, pending.value),
              ),
            if (handoff.isNotEmpty)
              section('Offene Ausgabe', [
                Text(
                  '${handoff['employee_snapshot']?['name'] ?? handoff['employee_name'] ?? handoff['employee_id'] ?? 'Projektbindung'} · ${handoff['project_snapshot']?['name'] ?? handoff['project_name'] ?? handoff['project_id'] ?? 'Ohne Projekt'}',
                ),
                Text(
                  'Ausgegeben: ${businessDate(handoff['issued_at'], time: true)}',
                ),
                Text(
                  'Rückgabe erwartet: ${businessDate(handoff['expected_return_at'], time: true)}',
                ),
                if (DateTime.tryParse('${handoff['expected_return_at']}')
                        ?.isBefore(DateTime.now()) ==
                    true)
                  const Notice('Rückgabe überfällig.', error: true),
              ]),
            section('Prüf- und Wartungsanforderungen', [
              for (final requirement in items(item['requirements']))
                ListTile(
                  title: Text('${requirement['title']}'),
                  subtitle: Text(
                    '${requirement['active'] == true ? 'Aktiv' : 'Aufgehoben'} · Fällig ${businessDate(requirement['due_on'])} · Fassung ${requirement['revision']}\n${inspectionSummary(item, requirement)}',
                  ),
                  trailing: writable
                      ? PopupMenuButton<String>(
                          onSelected: (value) => attempt(
                            () => value == 'edit'
                                ? this.requirement(requirement)
                                : inspection(requirement),
                          ),
                          itemBuilder: (_) => [
                            const PopupMenuItem(
                              value: 'edit',
                              child: Text('Anforderung bearbeiten'),
                            ),
                            if (requirement['active'] == true)
                              const PopupMenuItem(
                                value: 'inspect',
                                child: Text('Prüfung dokumentieren'),
                              ),
                          ],
                        )
                      : null,
                ),
            ]),
            section('Unveränderte Originale', [
              for (final file in items(item['files']))
                ListTile(
                  title: Text('${file['filename']}'),
                  subtitle: Text(
                    '${file['size']} Byte · SHA-256 ${file['sha256']}',
                  ),
                  onTap: () => attempt(() => download(file)),
                  trailing: const Icon(Icons.download),
                ),
            ]),
            button('Zur Betriebsmittelübersicht', () async {
              selectedId = null;
              await load();
            }),
          ],
        ],
      ),
    );
  }

  Map<String, String> get pendingEntries {
    final item = selected;
    if (item == null) return {};
    final resource = item['id'], prefix = '/resource-custody/$resource/';
    return {
      for (final action in ['profile', 'files', 'handoffs', 'returns'])
        'resource-custody-$action-$resource': '$prefix$action',
      'resource-custody-requirement-$resource-new': '${prefix}requirements',
      for (final requirement in items(item['requirements']))
        'resource-custody-requirement-$resource-${requirement['id']}':
            '${prefix}requirements',
      for (final record in [
        ...items(item['requirements']),
        ...items(item['inspections']),
      ])
        'resource-custody-inspection-$resource-${record['id']}':
            '${prefix}inspections',
      for (final record in items(item['handoffs']))
        'resource-custody-correction-${record['id']}': '${prefix}corrections',
      for (final record in items(
        item['handoffs'],
      ).where((value) => value['return'] != null))
        'resource-custody-correction-${record['return']['id']}':
            '${prefix}corrections',
    };
  }

  String inspectionSummary(
    Map<String, dynamic> item,
    Map<String, dynamic> requirement,
  ) {
    final latest = items(item['inspections']).reversed
        .where(
          (value) =>
              value['requirement_id'] == requirement['id'] &&
              value['requirement_revision'] == requirement['revision'],
        )
        .firstOrNull;
    return latest == null
        ? 'Für diese Anforderungsfassung fehlt eine dokumentierte Prüfung.'
        : '${custodyResults[latest['result']]} · Prüfung ${businessDate(latest['performed_at'], time: true)} · Nächste Fälligkeit ${businessDate(latest['next_due_on'])}';
  }

  Future<void> profileForm() => profile();
  Future<void> resolvePending(String key, String path) async {
    guard();
    final captured = epoch, commandSession = session;
    var active = true;
    final body = session.pendingCommandValues(key, path: path);
    if (body == null) return;
    try {
      await ownedDialog<bool>(
        context: context,
        builder: (_) => BusinessEditor(
          session: commandSession,
          pendingKey: key,
          readAllowed: () => active && current(captured) && readable,
          writePermission: 'planning.write',
          title: 'Ursprünglichen Betriebsmittelauftrag prüfen',
          fields: const [],
          initial: body,
          onSave: (_) async {
            ensureCurrent(captured);
            guard();
            await commandSession.repeatResourceCustodyCommand(
              key,
              stillCurrent: () => active && current(captured),
            );
          },
        ),
      );
    } finally {
      active = false;
    }
    if (current(captured)) await load();
  }
}

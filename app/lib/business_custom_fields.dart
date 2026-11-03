import 'dart:convert';

import 'package:flutter/material.dart';

import 'api.dart';
import 'business_session.dart';
import 'business_widgets.dart';
import 'design.dart';
import 'offline_vault.dart' show offlineId;

const customTypes = {
  'text': 'Text',
  'number': 'Zahl',
  'date': 'Datum',
  'choice': 'Auswahl',
  'boolean': 'Ja / Nein',
};
const customEntities = {
  'contact': 'Kontakte',
  'project': 'Projekte',
  'asset': 'Geräte',
};
final _id = RegExp(r'^[a-f0-9]{32}$'), _hash = RegExp(r'^[a-f0-9]{64}$');
Never _invalid() => throw const ApiException(
  0,
  'Zusatzfeld-Fassung oder Bestätigung stimmt nicht mit dem geprüften Vorgang überein.',
);
dynamic _ordered(dynamic value) => value is List
    ? value.map(_ordered).toList()
    : value is Map
    ? {
        for (final key in value.keys.map((e) => '$e').toList()..sort())
          key: _ordered(value[key]),
      }
    : value;
bool customSame(dynamic left, dynamic right) =>
    jsonEncode(_ordered(left)) == jsonEncode(_ordered(right));
Map<String, dynamic> _copy(Map<String, dynamic> value) =>
    businessMap(jsonDecode(jsonEncode(value)));

dynamic customValue(
  Map<String, dynamic> definition,
  dynamic input, [
  dynamic previous,
]) {
  dynamic value = input == '' ? null : input;
  if (value == null) {
    if (definition['required'] == true)
      throw ApiException(
        400,
        'Pflichtfeld „${definition['label']}“ ausfüllen.',
      );
    return null;
  }
  switch (definition['field_type']) {
    case 'text':
      if (value is! String ||
          value.length > 4000 ||
          RegExp(r'[\x00-\x08\x0b-\x1f]').hasMatch(value) ||
          definition['required'] == true && value.trim().isEmpty)
        _invalid();
    case 'number':
      if (input is! String) _invalid();
      value = input.trim().replaceAll(',', '.');
      if (!RegExp(r'^-?(?:0|[1-9][0-9]{0,11})(?:\.[0-9]{1,6})?$')
          .hasMatch(value))
        throw const ApiException(
          400,
          'Exakte Zahl mit höchstens zwölf Vor- und sechs Nachkommastellen eingeben.',
        );
    case 'date':
      final date = value is String ? DateTime.tryParse(value) : null;
      if (date == null ||
          date.year < 1900 ||
          date.year > 2200 ||
          date.toIso8601String().substring(0, 10) != value)
        _invalid();
    case 'boolean':
      if (value == 'true')
        value = true;
      else if (value == 'false')
        value = false;
      if (value is! bool) _invalid();
    case 'choice':
      if (!businessItems(definition['options']).any(
        (o) => o['id'] == value && (o['active'] == true || value == previous),
      ))
        throw const ApiException(
          400,
          'Eine aktive Auswahl wählen; archivierte Bestandsauswahl darf unverändert bleiben.',
        );
    default:
      _invalid();
  }
  return value;
}

String customDisplay(dynamic raw) {
  if (raw is! Map || raw['value'] == null) return 'Nicht erfasst';
  final item = businessMap(raw), definition = businessMap(item['definition']);
  if (definition['field_type'] == 'boolean')
    return item['value'] == true ? 'Ja' : 'Nein';
  if (definition['field_type'] == 'choice') {
    for (final option in businessItems(definition['options'])) {
      if (option['id'] == item['value']) return '${option['label']}';
    }
    return 'Unbekannte Auswahl';
  }
  return '${item['value']}';
}

Map<String, dynamic> customDefinition(dynamic raw) {
  final d = businessMap(raw);
  if (!_id.hasMatch('${d['id']}') ||
      d['revision'] is! int ||
      d['revision'] < 1 ||
      !_hash.hasMatch('${d['content_hash']}') ||
      !customEntities.containsKey(d['entity_type']) ||
      !customTypes.containsKey(d['field_type']) ||
      d['label'] is! String ||
      '${d['label']}'.isEmpty ||
      d['help_text'] is! String ||
      d['required'] is! bool ||
      d['active'] is! bool ||
      d['options'] is! List)
    _invalid();
  for (final o in businessItems(d['options'])) {
    if (!_id.hasMatch('${o['id']}') ||
        o['label'] is! String ||
        o['active'] is! bool)
      _invalid();
  }
  return d;
}

Map<String, dynamic> customSnapshot(dynamic raw, String type, String id) {
  final v = businessMap(raw),
      entity = businessMap(v['entity']),
      current = businessMap(v['current']);
  if (entity['entity_type'] != type ||
      entity['id'] != id ||
      v['definitions'] is! List ||
      !_hash.hasMatch('${v['definitions_hash']}') ||
      v['can_write'] is! bool ||
      v['missing_required'] is! List ||
      v['complete'] is! bool ||
      current['entity_type'] != type ||
      current['entity_id'] != id ||
      current['revision'] is! int ||
      current['revision'] < 0 ||
      current['values'] is! Map)
    _invalid();
  for (final d in businessItems(v['definitions'])) {
    if (customDefinition(d)['entity_type'] != type) _invalid();
  }
  if (current['revision'] > 0 && !_hash.hasMatch('${current['content_hash']}'))
    _invalid();
  for (final entry in businessMap(current['values']).entries) {
    final item = businessMap(entry.value),
        d = customDefinition(item['definition']);
    if (d['id'] != entry.key || d['entity_type'] != type) _invalid();
    customValue(d, item['value'], item['value']);
  }
  return v;
}

void Function(dynamic) customReceipt(
  Map<String, dynamic> body, {
  Map<String, dynamic>? previous,
  Map<String, dynamic>? snapshot,
}) {
  final frozen = _copy(body),
      prior = previous == null ? null : _copy(previous),
      view = snapshot == null ? null : _copy(snapshot);
  return (raw) {
    final value = businessMap(raw);
    if (value['revision'] != frozen['revision'] + 1 ||
        value['previous_hash'] != prior?['content_hash'] ||
        !_hash.hasMatch('${value['content_hash']}') ||
        !_id.hasMatch('${value['created_by']}') ||
        value['created_at'] is! String ||
        value['reason'] != frozen['reason'])
      _invalid();
    if (frozen['definition'] != null) {
      customDefinition(value);
      if (frozen['id'] != null && value['id'] != frozen['id']) _invalid();
      for (final e in businessMap(frozen['definition']).entries) {
        if (!customSame(value[e.key], e.value)) _invalid();
      }
    } else {
      if (view == null ||
          value['entity_type'] != view['entity']['entity_type'] ||
          value['entity_id'] != view['entity']['id'] ||
          value['definitions_hash'] != frozen['definitions_hash'] ||
          !customSame(value['definitions'], view['definitions']))
        _invalid();
      final expected = businessMap(prior?['values']);
      for (final d in businessItems(
        view['definitions'],
      ).where((d) => d['active'] == true)) {
        expected[d['id']] = {
          'definition': d,
          'value': frozen['values'][d['id']],
        };
      }
      if (!customSame(value['values'], expected)) _invalid();
    }
  };
}

class BusinessCustomFieldsPage extends StatefulWidget {
  const BusinessCustomFieldsPage({
    super.key,
    required this.session,
    this.entityType,
    this.entityId,
  });
  final BusinessSession session;
  final String? entityType, entityId;
  @override
  State<BusinessCustomFieldsPage> createState() =>
      _BusinessCustomFieldsPageState();
}

class _BusinessCustomFieldsPageState extends State<BusinessCustomFieldsPage> {
  Map<String, dynamic>? view;
  List<Map<String, dynamic>> definitions = [];
  String? error;
  bool loading = false;
  int epoch = 0;
  bool get admin => widget.entityId == null;
  String get permission => admin
      ? 'settings.manage'
      : widget.entityType == 'contact'
      ? 'contacts.read'
      : 'documents.read';
  String get writePermission => admin
      ? 'settings.manage'
      : widget.entityType == 'contact'
      ? 'contacts.write'
      : widget.entityType == 'project'
      ? 'projects.manage'
      : 'documents.write';
  bool get allowed =>
      widget.session.hasFeature('custom_fields') &&
      widget.session.can(permission);
  bool get writable =>
      allowed &&
      widget.session.canWrite(writePermission) &&
      (admin || view?['can_write'] == true);
  String get path => admin
      ? '/custom-fields/definitions'
      : '/custom-fields/entities/${widget.entityType}/${widget.entityId}';
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
      view = null;
      definitions = [];
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
    final stamp = ++epoch;
    setState(() {
      loading = true;
      error = null;
    });
    try {
      final raw = await widget.session.read(path);
      if (!mounted || stamp != epoch || !allowed) return;
      setState(() {
        if (admin) {
          definitions = businessItems(businessMap(raw)['items'])
              .map(customDefinition)
              .toList();
        } else {
          view = customSnapshot(raw, widget.entityType!, widget.entityId!);
          definitions = businessItems(view!['definitions']);
        }
      });
    } catch (e) {
      if (mounted && stamp == epoch)
        setState(() {
          error = '$e';
          view = null;
          definitions = [];
        });
    } finally {
      if (mounted && stamp == epoch) setState(() => loading = false);
    }
  }

  Future<void> history({Map<String, dynamic>? definition, int? before}) async {
    if (!allowed) return;
    final stamp = epoch;
    try {
      final target = definition == null
              ? path
              : '/custom-fields/definitions/${definition['id']}',
          raw = businessMap(
            await widget.session.read(
              '$target/history${before == null ? '' : '?before_revision=$before'}',
            ),
          );
      if (!mounted || stamp != epoch || !allowed) return;
      await showDialog<void>(
        context: context,
        builder: (context) => AnimatedBuilder(
          animation: widget.session,
          builder: (context, _) => !allowed
              ? const AlertDialog(title: Text('Zugang nicht mehr verfügbar'))
              : AlertDialog(
                  title: const Text('Zusatzfelder · Historie'),
                  content: SizedBox(
                    width: 650,
                    child: SingleChildScrollView(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          for (final event in businessItems(raw['items'])) ...[
                            Text(
                              'Fassung ${event['revision']} · ${businessDate(event['created_at'], time: true)}',
                              style: Theme.of(context).textTheme.titleMedium,
                            ),
                            Text('${event['reason'] ?? 'Ersterfassung'}'),
                            if (definition != null) ...[
                              Text(
                                '${event['label']} · ${customTypes[event['field_type']]} · ${event['active'] == true ? 'Aktiv' : 'Archiviert'}',
                              ),
                              Text(
                                'Pflichtfeld: ${event['required'] == true ? 'Ja' : 'Nein'}',
                              ),
                              Text('${event['help_text']}'),
                              for (final o in businessItems(event['options']))
                                Text(
                                  '${o['label']}${o['active'] == true ? '' : ' (archiviert)'}',
                                ),
                            ] else
                              for (final item in businessMap(
                                event['values'],
                              ).values)
                                Text(
                                  '${item['definition']['label']}: ${customDisplay(item)}',
                                ),
                            const Divider(),
                          ],
                          if (raw['next_before_revision'] != null)
                            TextButton(
                              onPressed: () {
                                Navigator.pop(context);
                                history(
                                  definition: definition,
                                  before: raw['next_before_revision'],
                                );
                              },
                              child: const Text('Ältere Fassungen'),
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
    } catch (e) {
      if (mounted) setState(() => error = '$e');
    }
  }

  Future<void> editValues() async {
    final captured = view;
    if (!writable || captured == null) return;
    final prior = businessMap(captured['current']),
        stored = businessMap(prior['values']);
    final fields = <BusinessField>[];
    for (final d in definitions.where((d) => d['active'] == true)) {
      final old = businessMap(stored[d['id']])['value'];
      fields.add(
        BusinessField(
          d['id'],
          d['label'],
          required: d['required'],
          hint: d['help_text'],
          type: d['field_type'] == 'boolean' || d['field_type'] == 'choice'
              ? BusinessInput.choice
              : d['field_type'] == 'date'
              ? BusinessInput.date
              : d['field_type'] == 'text'
              ? BusinessInput.multiline
              : BusinessInput.text,
          initial: d['field_type'] == 'boolean'
              ? (old == null ? null : '$old')
              : old,
          choices: d['field_type'] == 'boolean'
              ? {'true': 'Ja', 'false': 'Nein'}
              : {
                  for (final o in businessItems(
                    d['options'],
                  ).where((o) => o['active'] == true || o['id'] == old))
                    o['id']:
                        '${o['label']}${o['active'] == true ? '' : ' (archiviert)'}',
                },
        ),
      );
    }
    fields.add(
      BusinessField(
        'reason',
        'Änderungsgrund',
        required: prior['revision'] > 0,
      ),
    );
    final key = 'custom-fields-${widget.entityType}-${widget.entityId}';
    await showDialog<bool>(
      context: context,
      builder: (_) => BusinessEditor(
        session: widget.session,
        title: 'Zusatzwerte bearbeiten',
        readPermission: permission,
        writePermission: writePermission,
        readAllowed: () => allowed,
        pendingKey: key,
        fields: fields,
        onSave: (values) async {
          if (widget.session.pending(key)) {
            await widget.session.repeatCustomFieldsCommand(key);
            return;
          }
          final fresh = customSnapshot(
            await widget.session.read(path),
            widget.entityType!,
            widget.entityId!,
          );
          if (!allowed ||
              !widget.session.canWrite(writePermission) ||
              fresh['can_write'] != true)
            throw const ApiException(
              403,
              'Die aktuelle Schreibfreigabe fehlt.',
            );
          final body =
              widget.session.pendingCommandValues(key, path: path) ??
              {
                'revision': prior['revision'],
                'definitions_hash': captured['definitions_hash'],
                'values': {
                  for (final d in businessItems(
                    captured['definitions'],
                  ).where((d) => d['active'] == true))
                    d['id']: customValue(
                      d,
                      values[d['id']],
                      businessMap(stored[d['id']])['value'],
                    ),
                },
                'reason': '${values['reason'] ?? ''}'.trim(),
              };
          await widget.session.command(
            key,
            path,
            body,
            validateResult: customReceipt(
              body,
              previous: prior,
              snapshot: captured,
            ),
          );
        },
      ),
    );
    if (mounted) await load();
  }

  Future<void> editDefinition([Map<String, dynamic>? previous]) async {
    if (!writable) return;
    final choices = businessItems(previous?['options']),
        key = 'custom-fields-definition-${previous?['id'] ?? 'new'}';
    await showDialog<bool>(
      context: context,
      builder: (_) => BusinessEditor(
        session: widget.session,
        title: previous == null
            ? 'Zusatzfeld anlegen'
            : 'Zusatzfeld bearbeiten',
        readPermission: 'settings.manage',
        writePermission: 'settings.manage',
        readAllowed: () => allowed,
        pendingKey: key,
        fields: [
          BusinessField(
            'entity_type',
            'Zuordnung',
            type: BusinessInput.choice,
            required: true,
            initial: previous?['entity_type'] ?? 'contact',
            choices: customEntities,
          ),
          BusinessField(
            'label',
            'Feldname',
            required: true,
            initial: previous?['label'],
          ),
          BusinessField(
            'help_text',
            'Ausfüllhilfe',
            type: BusinessInput.multiline,
            initial: previous?['help_text'],
          ),
          BusinessField(
            'field_type',
            'Feldart',
            type: BusinessInput.choice,
            required: true,
            initial: previous?['field_type'] ?? 'text',
            choices: customTypes,
          ),
          BusinessField(
            'required',
            'Als Pflichtfeld aktivieren',
            type: BusinessInput.toggle,
            initial: previous?['required'] ?? false,
          ),
          BusinessField(
            'active',
            'Feld aktiv',
            type: BusinessInput.toggle,
            initial: previous?['active'] ?? true,
          ),
          for (final o in choices) ...[
            BusinessField(
              'label_${o['id']}',
              'Auswahlbezeichnung',
              required: true,
              initial: o['label'],
            ),
            BusinessField(
              'active_${o['id']}',
              'Auswahl aktiv: ${o['label']}',
              type: BusinessInput.toggle,
              initial: o['active'],
            ),
          ],
          const BusinessField(
            'new_options',
            'Neue Auswahlmöglichkeiten · eine Bezeichnung je Zeile',
            type: BusinessInput.multiline,
            hint: 'Nur für Auswahlfelder. Bestehende Auswahlen über ihre Aktivierung archivieren.',
          ),
          BusinessField('reason', 'Änderungsgrund', required: previous != null),
        ],
        onSave: (values) async {
          if (widget.session.pending(key)) {
            await widget.session.repeatCustomFieldsCommand(key);
            return;
          }
          if (!writable)
            throw const ApiException(
              403,
              'Die aktuelle Schreibfreigabe fehlt.',
            );
          final body =
              widget.session.pendingCommandValues(key, path: path) ??
              {
                'revision': previous?['revision'] ?? 0,
                if (previous != null) 'id': previous['id'],
                'definition': {
                  'entity_type': values['entity_type'],
                  'label': '${values['label']}'.trim(),
                  'help_text': '${values['help_text'] ?? ''}'.trim(),
                  'field_type': values['field_type'],
                  'required': values['required'],
                  'active': values['active'],
                  'options': values['field_type'] == 'choice'
                      ? [
                          for (final o in choices)
                            {
                              'id': o['id'],
                              'label': '${values['label_${o['id']}']}'.trim(),
                              'active': values['active_${o['id']}'],
                            },
                          for (final label
                              in '${values['new_options'] ?? ''}'
                                  .split('\n')
                                  .map((s) => s.trim())
                                  .where((s) => s.isNotEmpty))
                            {'id': offlineId(), 'label': label, 'active': true},
                        ]
                      : [],
                },
                'reason': '${values['reason'] ?? ''}'.trim(),
              };
          await widget.session.command(
            key,
            path,
            body,
            validateResult: customReceipt(body, previous: previous),
          );
        },
      ),
    );
    if (mounted) await load();
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(
      title: Text(
        admin
            ? 'Zusatzfelder verwalten'
            : 'Zusatzfelder${view == null ? '' : ' · ${view!['entity']['label']}'}',
      ),
      actions: [
        IconButton(
          onPressed: loading ? null : load,
          icon: const Icon(Icons.refresh),
          tooltip: 'Neu laden',
        ),
      ],
    ),
    body: !allowed
        ? const Center(child: Text('Der Zugang ist nicht mehr verfügbar.'))
        : ListView(
            padding: const EdgeInsets.all(24),
            children: [
              const Notice(
                'Eigene Angaben für Kontakte, Projekte und Geräte. Kernfelder, Rechte, Steuern und Kennzahlen bleiben eigenständig.',
              ),
              if (error != null) Notice(error!, error: true),
              if (loading) const LinearProgressIndicator(),
              if (admin) ...[
                const Text(
                  'Pflichtangaben werden ausdrücklich aktiviert. Bestehende leere Werte bleiben sichtbar; gespeicherte Feldarten werden nicht umgedeutet.',
                ),
                if (writable)
                  FilledButton(
                    onPressed: () => editDefinition(),
                    child: const Text('Feld anlegen'),
                  ),
                for (final d in definitions)
                  Card(
                    child: ListTile(
                      title: Text(d['label']),
                      subtitle: Text(
                        '${customEntities[d['entity_type']]} · ${customTypes[d['field_type']]} · ${d['active'] == true ? 'Aktiv' : 'Archiviert'}${d['required'] == true ? ' · Pflichtfeld' : ''}',
                      ),
                      trailing: Wrap(
                        children: [
                          if (writable)
                            IconButton(
                              onPressed: () => editDefinition(d),
                              icon: const Icon(Icons.edit_outlined),
                              tooltip: 'Definition bearbeiten',
                            ),
                          IconButton(
                            onPressed: () => history(definition: d),
                            icon: const Icon(Icons.history),
                            tooltip: 'Historie',
                          ),
                        ],
                      ),
                    ),
                  ),
              ] else if (view != null) ...[
                Notice(
                  view!['complete'] == true
                      ? 'Alle aktuell definierten Pflichtfelder sind ausgefüllt.'
                      : 'Pflichtangaben fehlen: ${definitions.where((d) => (view!['missing_required'] as List).contains(d['id'])).map((d) => d['label']).join(', ')}',
                ),
                for (final d in definitions)
                  ListTile(
                    title: Text(
                      '${d['label']}${d['active'] == true ? '' : ' (archiviert)'}',
                    ),
                    subtitle: SelectableText(
                      customDisplay(view!['current']['values'][d['id']]),
                    ),
                  ),
                if (writable)
                  FilledButton(
                    onPressed: editValues,
                    child: const Text('Zusatzwerte bearbeiten'),
                  ),
                OutlinedButton(
                  onPressed: () => history(),
                  child: const Text('Änderungshistorie'),
                ),
              ],
            ],
          ),
  );
}

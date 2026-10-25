import 'package:flutter/material.dart';

import 'api.dart';
import 'business_session.dart';
import 'design.dart';

String businessDate(Object? value, {bool time = false}) {
  if (value == null || value == '') return 'Nicht angegeben';
  final parsed = DateTime.tryParse('$value');
  if (parsed == null) return '$value';
  final date = time ? parsed.toLocal() : parsed;
  String two(int n) => '$n'.padLeft(2, '0');
  return '${two(date.day)}.${two(date.month)}.${date.year}${time ? ' · ${two(date.hour)}:${two(date.minute)}' : ''}';
}

String businessMoney(Object? value, [String currency = 'EUR']) {
  if (value == null) return 'Nicht erfasst';
  final parts = '$value'.split('.');
  final integer = parts.first.replaceAllMapped(
    RegExp(r'(\d)(?=(\d{3})+$)'),
    (m) => '${m[1]}.',
  );
  return '$integer,${(parts.length > 1 ? parts[1] : '').padRight(2, '0')} ${currency == 'EUR' ? '€' : currency}';
}

DateTime businessParseDate(String text) {
  final match = RegExp(
    r'^(\d{1,2})\.(\d{1,2})\.(\d{4})(?:[ ·]+(\d{1,2}):(\d{2}))?$',
  ).firstMatch(text.trim());
  if (match == null) return DateTime.parse(text);
  final day = int.parse(match[1]!),
      month = int.parse(match[2]!),
      year = int.parse(match[3]!),
      hour = int.parse(match[4] ?? '0'),
      minute = int.parse(match[5] ?? '0');
  final date = DateTime(year, month, day, hour, minute);
  if (date.year != year ||
      date.month != month ||
      date.day != day ||
      date.hour != hour ||
      date.minute != minute)
    throw const FormatException('Ungültiges Datum.');
  return date;
}

String businessDecimal(String input) {
  var text = input.trim().replaceAll(' ', '');
  if (text.contains(',')) text = text.replaceAll('.', '').replaceAll(',', '.');
  if (!RegExp(r'^-?\d+(?:\.\d{1,6})?$').hasMatch(text))
    throw const FormatException(
      'Bitte eine Zahl eingeben, zum Beispiel 12,50.',
    );
  return text;
}

enum BusinessInput {
  text,
  multiline,
  decimal,
  integer,
  date,
  instant,
  toggle,
  choice,
  multiple,
}

class BusinessField {
  const BusinessField(
    this.name,
    this.label, {
    this.type = BusinessInput.text,
    this.required = false,
    this.choices = const {},
    this.initial,
    this.hint,
    this.omitIfEmpty = false,
  });
  final String name, label;
  final BusinessInput type;
  final bool required;
  final Map<String, String> choices;
  final Object? initial;
  final String? hint;
  final bool omitIfEmpty;
}

class BusinessEmpty extends StatelessWidget {
  const BusinessEmpty(
    this.title,
    this.message, {
    super.key,
    this.icon = Icons.folder_open_outlined,
  });
  final String title, message;
  final IconData icon;
  @override
  Widget build(BuildContext context) => Card(
    child: Padding(
      padding: const EdgeInsets.all(24),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(icon, color: OfficeColors.muted),
          const SizedBox(height: 12),
          Text(title, style: Theme.of(context).textTheme.titleMedium),
          const SizedBox(height: 6),
          Text(message, style: Theme.of(context).textTheme.bodySmall),
        ],
      ),
    ),
  );
}

class BusinessEditor extends StatefulWidget {
  const BusinessEditor({
    super.key,
    required this.session,
    required this.title,
    required this.fields,
    required this.onSave,
    this.initial = const {},
    this.saveLabel = 'Speichern',
    this.readPermission,
    this.writePermission,
  });
  final BusinessSession session;
  final String title, saveLabel;
  final String? readPermission, writePermission;
  final List<BusinessField> fields;
  final Map<String, dynamic> initial;
  final Future<void> Function(Map<String, dynamic>) onSave;
  @override
  State<BusinessEditor> createState() => _BusinessEditorState();
}

class _BusinessEditorState extends State<BusinessEditor> {
  bool get mayView =>
      widget.session.allowed &&
      (widget.readPermission == null ||
          widget.session.can(widget.readPermission!));
  bool get mayWrite =>
      mayView &&
      !widget.session.readonly &&
      (widget.writePermission == null ||
          widget.session.canWrite(widget.writePermission!));
  final form = GlobalKey<FormState>();
  final controllers = <String, TextEditingController>{};
  final choices = <String, dynamic>{};
  bool busy = false, uncertain = false;
  String? error;
  Map<String, dynamic>? frozen;
  @override
  void initState() {
    super.initState();
    widget.session.addListener(changed);
    for (final field in widget.fields) {
      final value = widget.initial.containsKey(field.name)
          ? widget.initial[field.name]
          : field.initial;
      if ([
        BusinessInput.toggle,
        BusinessInput.choice,
        BusinessInput.multiple,
      ].contains(field.type)) {
        choices[field.name] = field.type == BusinessInput.multiple
            ? List<String>.from(value as List? ?? [])
            : value ?? (field.type == BusinessInput.toggle ? false : null);
      } else {
        controllers[field.name] = TextEditingController(
          text: value == null
              ? ''
              : field.type == BusinessInput.date
              ? businessDate(value)
              : field.type == BusinessInput.instant
              ? businessDate(value, time: true).replaceAll(' · ', ' ')
              : '${field.type == BusinessInput.decimal ? '$value'.replaceAll('.', ',') : value}',
        );
      }
    }
  }

  void changed() {
    if (mounted) {
      if (!mayView) {
        for (final c in controllers.values) c.clear();
        choices.clear();
        frozen = null;
      }
      setState(() {});
    }
  }

  @override
  void dispose() {
    widget.session.removeListener(changed);
    for (final c in controllers.values) {
      c.clear();
      c.dispose();
    }
    super.dispose();
  }

  Map<String, dynamic> values() {
    final values = <String, dynamic>{};
    for (final field in widget.fields) {
      if (choices.containsKey(field.name)) {
        values[field.name] = choices[field.name];
        continue;
      }
      final text = controllers[field.name]!.text.trim();
      if (text.isEmpty) {
        if (field.omitIfEmpty) continue;
        values[field.name] =
            [BusinessInput.text, BusinessInput.multiline].contains(field.type)
            ? ''
            : null;
        continue;
      }
      values[field.name] = switch (field.type) {
        BusinessInput.decimal => businessDecimal(text),
        BusinessInput.integer => int.parse(text),
        BusinessInput.instant => businessParseDate(
          text,
        ).toUtc().toIso8601String(),
        BusinessInput.date => businessParseDate(
          text,
        ).toIso8601String().substring(0, 10),
        _ => text,
      };
    }
    return values;
  }

  Future<void> save() async {
    if (busy || !mayWrite || !(form.currentState?.validate() ?? false)) return;
    setState(() {
      busy = true;
      error = null;
    });
    try {
      frozen ??= values();
      await widget.onSave(Map<String, dynamic>.from(frozen!));
      if (mounted && widget.session.allowed) Navigator.pop(context, true);
    } on ApiException catch (e) {
      if (mounted)
        setState(() {
          error = e.message;
          uncertain = e.status == 0 || e.status >= 500 || e.status == 429;
          if (!uncertain) frozen = null;
        });
    } catch (e) {
      if (mounted)
        setState(() {
          error = e is FormatException ? e.message : 'Der Eintrag konnte nicht gespeichert werden. Ihre Eingaben bleiben geöffnet.';
          frozen = null;
        });
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  String? validate(BusinessField field, String? value) {
    final text = (value ?? '').trim();
    if (field.required && text.isEmpty)
      return 'Bitte ${field.label.toLowerCase()} eingeben.';
    if (text.isEmpty) return null;
    if (text.length > 10000) return 'Der Text ist zu lang.';
    try {
      if (field.type == BusinessInput.decimal) businessDecimal(text);
      if (field.type == BusinessInput.integer) int.parse(text);
      if (field.type == BusinessInput.date &&
          (businessParseDate(text).year < 1900 ||
              businessParseDate(text).year > 2200))
        return 'Bitte ein gültiges Datum wählen.';
      if (field.type == BusinessInput.instant) businessParseDate(text);
    } catch (_) {
      return field.type == BusinessInput.date
          ? 'Datum im Format TT.MM.JJJJ.'
          : field.type == BusinessInput.instant
          ? 'Bitte Datum und Uhrzeit eingeben.'
          : 'Bitte eine gültige Zahl eingeben.';
    }
    return null;
  }

  Widget field(BusinessField field) {
    final enabled = !busy && !uncertain && mayWrite;
    if (field.type == BusinessInput.toggle)
      return SwitchListTile.adaptive(
        contentPadding: EdgeInsets.zero,
        title: Text(field.label),
        value: choices[field.name] == true,
        onChanged: enabled
            ? (v) => setState(() => choices[field.name] = v)
            : null,
      );
    if (field.type == BusinessInput.multiple)
      return Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(field.label, style: Theme.of(context).textTheme.titleSmall),
          for (final option in field.choices.entries)
            CheckboxListTile(
              contentPadding: EdgeInsets.zero,
              dense: true,
              title: Text(option.value),
              value: (choices[field.name] as List).contains(option.key),
              onChanged: enabled
                  ? (value) => setState(() {
                      final list = choices[field.name] as List;
                      value == true
                          ? list.add(option.key)
                          : list.remove(option.key);
                    })
                  : null,
            ),
        ],
      );
    if (field.type == BusinessInput.choice) {
      final current = choices[field.name] as String?;
      final options = {
        ...field.choices,
        if (current != null && !field.choices.containsKey(current))
          current: 'Nicht mehr in der aktuellen Auswahl',
      };
      return DropdownButtonFormField<String>(
        initialValue: current,
        decoration: InputDecoration(labelText: field.label),
        isExpanded: true,
        items: [
          if (!field.required)
            const DropdownMenuItem(value: '', child: Text('Nicht angegeben')),
          for (final entry in options.entries)
            DropdownMenuItem(
              value: entry.key,
              child: Text(entry.value, overflow: TextOverflow.ellipsis),
            ),
        ],
        onChanged: enabled
            ? (v) => setState(() => choices[field.name] = v == '' ? null : v)
            : null,
        validator: (v) => field.required && (v == null || v.isEmpty)
            ? 'Bitte auswählen.'
            : null,
      );
    }
    return TextFormField(
      key: ValueKey('business-field-${field.name}'),
      controller: controllers[field.name],
      enabled: enabled,
      maxLines: field.type == BusinessInput.multiline ? 4 : 1,
      keyboardType:
          [BusinessInput.integer, BusinessInput.decimal].contains(field.type)
          ? const TextInputType.numberWithOptions(decimal: true, signed: true)
          : null,
      decoration: InputDecoration(
        labelText: field.label,
        hintText:
            field.hint ??
            (field.type == BusinessInput.date
                ? 'TT.MM.JJJJ'
                : field.type == BusinessInput.instant
                ? 'TT.MM.JJJJ HH:MM'
                : null),
        suffixIcon:
            [BusinessInput.date, BusinessInput.instant].contains(field.type)
            ? IconButton(
                tooltip: 'Datum wählen',
                onPressed: enabled
                    ? () async {
                        final now = DateTime.now();
                        final date = await showDatePicker(
                          context: context,
                          initialDate:
                              DateTime.tryParse(
                                controllers[field.name]!.text,
                              ) ??
                              now,
                          firstDate: DateTime(2000),
                          lastDate: DateTime(2200),
                        );
                        if (date != null && mounted) {
                          if (field.type == BusinessInput.instant) {
                            final time = await showTimePicker(
                              context: context,
                              initialTime: TimeOfDay.now(),
                            );
                            if (!mounted || time == null) return;
                            controllers[field.name]!.text =
                                '${businessDate(date.toIso8601String())} ${time.hour.toString().padLeft(2, '0')}:${time.minute.toString().padLeft(2, '0')}';
                          } else {
                            controllers[field.name]!.text = businessDate(
                              date.toIso8601String(),
                            );
                          }
                        }
                      }
                    : null,
                icon: const Icon(Icons.calendar_today_outlined),
              )
            : null,
      ),
      validator: (v) => validate(field, v),
    );
  }

  @override
  Widget build(BuildContext context) => AlertDialog(
    title: Text(widget.title),
    content: SizedBox(
      width: 600,
      child: SingleChildScrollView(
        child: !mayView
            ? const Notice('Der Zugang ist nicht mehr verfügbar.', error: true)
            : Form(
                key: form,
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    for (final f in widget.fields) ...[
                      field(f),
                      const SizedBox(height: 16),
                    ],
                    if (error != null) Notice(error!, error: true),
                    if (uncertain)
                      const Notice(
                        'Die Übertragung ist noch unbestätigt. Erneutes Senden verwendet denselben Vorgang und dieselben Eingaben.',
                      ),
                  ],
                ),
              ),
      ),
    ),
    actions: [
      TextButton(
        onPressed: busy ? null : () => Navigator.pop(context),
        child: const Text('Schließen'),
      ),
      FilledButton(
        onPressed: busy || !mayWrite ? null : save,
        child: busy
            ? const SizedBox(
                width: 18,
                height: 18,
                child: CircularProgressIndicator(strokeWidth: 2),
              )
            : Text(uncertain ? 'Erneut senden' : widget.saveLabel),
      ),
    ],
  );
}

Future<bool> businessConfirm(
  BuildContext context, {
  required String title,
  required String message,
  String action = 'Bestätigen',
}) async =>
    await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: Text(title),
        content: Text(message),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: const Text('Abbrechen'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(context, true),
            child: Text(action),
          ),
        ],
      ),
    ) ??
    false;

class BusinessCollection extends StatefulWidget {
  const BusinessCollection({
    super.key,
    required this.session,
    required this.path,
    required this.title,
    required this.readPermission,
    required this.writePermission,
    required this.fields,
    this.createLabel = 'Neu anlegen',
    this.titleOf,
    this.subtitleOf,
    this.onOpen,
    this.onCreate,
    this.fixed = const {},
    this.actions,
    this.projectScoped = false,
    this.editable = true,
    this.updateAtCollection = false,
  });
  final BusinessSession session;
  final String path, title, readPermission, writePermission, createLabel;
  final List<BusinessField> fields;
  final Map<String, dynamic> fixed;
  final String Function(Map<String, dynamic>)? titleOf, subtitleOf;
  final Future<void> Function(Map<String, dynamic>)? onOpen;
  final Future<void> Function()? onCreate;
  final Widget? actions;
  final bool projectScoped, editable, updateAtCollection;
  @override
  State<BusinessCollection> createState() => _BusinessCollectionState();
}

class _BusinessCollectionState extends State<BusinessCollection> {
  List<Map<String, dynamic>> records = [];
  bool loading = true;
  String? error;
  String search = '';
  int epoch = 0;
  @override
  void initState() {
    super.initState();
    widget.session.addListener(changed);
    load();
  }

  void changed() {
    if (!mounted) return;
    if (!widget.session.can(widget.readPermission)) {
      epoch++;
      setState(() {
        records = [];
        loading = false;
      });
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
    if (!widget.session.can(widget.readPermission)) {
      if (mounted) setState(() => loading = false);
      return;
    }
    setState(() {
      loading = true;
      error = null;
    });
    try {
      final result = businessItems(
        await widget.session.read(widget.session.query(widget.path)),
      );
      if (mounted &&
          current == epoch &&
          widget.session.can(widget.readPermission))
        setState(() => records = result);
    } on ApiException catch (e) {
      if (mounted && current == epoch)
        setState(() {
          error = e.message;
          if ([401, 403, 404].contains(e.status)) records = [];
        });
    } catch (_) {
      if (mounted && current == epoch)
        setState(() => error = 'Die Einträge konnten nicht geladen werden.');
    } finally {
      if (mounted && current == epoch) setState(() => loading = false);
    }
  }

  Future<void> edit([Map<String, dynamic>? record]) async {
    if (!widget.session.canWrite(widget.writePermission)) return;
    if (record == null && widget.onCreate != null) {
      await widget.onCreate!();
      if (mounted) await load();
      return;
    }
    final revision = record?['revision'];
    final id = record?['id'];
    final key = '${widget.path}/${id ?? DateTime.now().microsecondsSinceEpoch}';
    await showDialog<bool>(
      context: context,
      builder: (_) => BusinessEditor(
        session: widget.session,
        title: record == null
            ? widget.createLabel
            : '${widget.title} bearbeiten',
        fields: widget.fields,
        readPermission: widget.readPermission,
        writePermission: widget.writePermission,
        initial: record ?? const {},
        onSave: (values) async {
          await widget.session.command(
            key,
            '${widget.path}${id == null || widget.updateAtCollection ? '' : '/$id'}',
            {
              ...widget.fixed,
              if (widget.projectScoped && widget.session.projectId != null)
                'project_id': widget.session.projectId,
              ...values,
              if (record != null) 'revision': revision,
            },
          );
        },
      ),
    );
    if (mounted) await load();
  }

  Future<void> open(Map<String, dynamic> record) async {
    if (widget.onOpen != null) {
      await widget.onOpen!(record);
      if (mounted) await load();
      return;
    }
    if (widget.editable && widget.session.canWrite(widget.writePermission)) {
      await edit(record);
      return;
    }
    if (!mounted) return;
    await showDialog<void>(
      context: context,
      builder: (_) => AlertDialog(
        title: Text(
          widget.titleOf?.call(record) ??
              '${record['name'] ?? record['title'] ?? widget.title}',
        ),
        content: SingleChildScrollView(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              for (final field in widget.fields) ...[
                Text(
                  field.label,
                  style: Theme.of(context).textTheme.labelMedium,
                ),
                Text(
                  field.choices['${record[field.name]}'] ??
                      '${record[field.name] ?? 'Nicht angegeben'}',
                ),
                const SizedBox(height: 12),
              ],
            ],
          ),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('Schließen'),
          ),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    if (!widget.session.can(widget.readPermission))
      return const BusinessEmpty(
        'Kein Zugriff',
        'Dieser Bereich ist für Ihren Zugang nicht freigegeben.',
        icon: Icons.lock_outline,
      );
    return RefreshIndicator(
      onRefresh: load,
      child: ListView(
        padding: const EdgeInsets.all(24),
        children: [
          Wrap(
            alignment: WrapAlignment.spaceBetween,
            crossAxisAlignment: WrapCrossAlignment.center,
            spacing: 16,
            runSpacing: 12,
            children: [
              Text(
                widget.title,
                style: Theme.of(context).textTheme.headlineMedium,
              ),
              Wrap(
                spacing: 8,
                runSpacing: 8,
                children: [
                  if (widget.actions != null) widget.actions!,
                  if (widget.session.canWrite(widget.writePermission))
                    FilledButton.icon(
                      onPressed: () => edit(),
                      icon: const Icon(Icons.add),
                      label: Text(widget.createLabel),
                    ),
                  IconButton(
                    tooltip: 'Aktualisieren',
                    onPressed: loading ? null : load,
                    icon: const Icon(Icons.refresh),
                  ),
                ],
              ),
            ],
          ),
          const SizedBox(height: 20),
          TextField(
            decoration: const InputDecoration(
              labelText: 'Einträge durchsuchen',
              prefixIcon: Icon(Icons.search),
            ),
            onChanged: (value) => setState(() => search = value.toLowerCase()),
          ),
          const SizedBox(height: 12),
          if (error != null) Notice(error!, error: true),
          if (loading) const LinearProgressIndicator(),
          if (!loading && records.isEmpty && error == null)
            BusinessEmpty(
              'Noch keine Einträge',
              'Mit „${widget.createLabel}“ erfassen Sie den ersten Eintrag.',
            ),
          for (final record in records.where(
            (r) =>
                search.isEmpty ||
                [
                  r['name'],
                  r['title'],
                  r['number'],
                  r['email'],
                  r['phone'],
                  r['contact'],
                  r['code'],
                ].join(' ').toLowerCase().contains(search),
          ))
            Card(
              child: ListTile(
                contentPadding: const EdgeInsets.symmetric(
                  horizontal: 20,
                  vertical: 8,
                ),
                title: Text(
                  widget.titleOf?.call(record) ??
                      '${record['name'] ?? record['title'] ?? record['number'] ?? widget.title}',
                ),
                subtitle: widget.subtitleOf == null
                    ? null
                    : Text(widget.subtitleOf!(record)),
                trailing: const Icon(Icons.chevron_right),
                onTap: () => open(record),
              ),
            ),
        ],
      ),
    );
  }
}

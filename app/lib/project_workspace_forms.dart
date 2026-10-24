import 'package:flutter/foundation.dart' show ValueListenable;
import 'package:flutter/material.dart';

import 'api.dart';
import 'design.dart';

const workspacePhaseLabels = <String, String>{
  'planning': 'Klärung / Planung',
  'scheduling': 'Terminabstimmung',
  'awaiting_deposit': 'Anzahlung offen',
  'procurement': 'Materialbeschaffung',
  'execution': 'In Ausführung',
  'final_invoice': 'Schlussrechnung',
  'completed': 'Abgeschlossen',
  'on_hold': 'Pausiert',
};
const workspaceDepositLabels = <String, String>{
  'not_recorded': 'Noch nicht erfasst',
  'not_required': 'Nicht erforderlich',
  'requested': 'Angefordert',
  'received': 'Eingegangen',
};
const workspaceMaterialsLabels = <String, String>{
  'not_recorded': 'Nicht erfasst',
  'not_planned': 'Noch nicht geplant',
  'to_order': 'Zu bestellen',
  'ordered': 'Bestellt',
  'delivered': 'Geliefert',
};
const workspaceTaskStatusLabels = <String, String>{
  'todo': 'Offen',
  'in_progress': 'In Arbeit',
  'done': 'Erledigt',
  'cancelled': 'Entfallen',
};
const workspacePriorityLabels = <String, String>{
  'normal': 'Normal',
  'high': 'Wichtig',
};
const workspaceAppointmentStatusLabels = <String, String>{
  'scheduled': 'Geplant',
  'cancelled': 'Abgesagt',
};
const workspaceLinkCategoryLabels = <String, String>{
  'dropbox': 'Dropbox-Ordner / Datei',
  'offer': 'Angebot',
  'invoice': 'Rechnung',
  'contract': 'Vertrag',
  'document': 'Dokument',
  'other': 'Weiterer Link',
};

/// The caller owns request IDs and revisions. A failed save keeps this editor
/// and its values open; it must never be replaced with a new blank form.
Future<bool> showWorkspaceEditor(
  BuildContext context, {
  required String kind,
  Map<String, dynamic>? initial,
  List<Map<String, dynamic>> team = const [],
  required Future<void> Function(Map<String, dynamic>) onSave,
  Future<bool> Function()? onResolveConflict,
  ValueListenable<bool>? accessAllowed,
}) async {
  if (!const [
    'profile',
    'tasks',
    'diary',
    'appointments',
    'links',
  ].contains(kind)) {
    throw ArgumentError.value(kind, 'kind');
  }
  return await showDialog<bool>(
        context: context,
        barrierDismissible: false,
        builder: (_) => _WorkspaceEditor(
          kind: kind,
          initial: initial,
          team: team,
          onSave: onSave,
          onResolveConflict: onResolveConflict,
          accessAllowed: accessAllowed,
        ),
      ) ??
      false;
}

class _WorkspaceEditor extends StatefulWidget {
  final String kind;
  final Map<String, dynamic>? initial;
  final List<Map<String, dynamic>> team;
  final Future<void> Function(Map<String, dynamic>) onSave;
  final Future<bool> Function()? onResolveConflict;
  final ValueListenable<bool>? accessAllowed;
  const _WorkspaceEditor({
    required this.kind,
    required this.initial,
    required this.team,
    required this.onSave,
    required this.onResolveConflict,
    required this.accessAllowed,
  });

  @override
  State<_WorkspaceEditor> createState() => _WorkspaceEditorState();
}

class _WorkspaceEditorState extends State<_WorkspaceEditor> {
  final form = GlobalKey<FormState>();
  final scroll = ScrollController();
  final fields = <String, TextEditingController>{};
  final values = <String, String>{};
  late final List<Map<String, dynamic>> team;
  bool active = true,
      saving = false,
      comparing = false,
      conflict = false,
      comparisonChecked = false;
  bool accessLost = false;
  String? error;
  bool get allowed => !accessLost && (widget.accessAllowed?.value ?? true);

  @override
  void initState() {
    super.initState();
    accessLost = widget.accessAllowed?.value == false;
    widget.accessAllowed?.addListener(accessChanged);
    final original = widget.initial ?? const <String, dynamic>{};
    team = {
      for (final member in widget.team)
        if (member['id'] is String && (member['id'] as String).isNotEmpty)
          member['id'] as String: member,
    }.values.toList();
    for (final name in [
      'title',
      'details',
      'description',
      'site_address',
      'work_performed',
      'issues',
      'next_steps',
      'weather',
      'url',
      'crew_count',
    ]) {
      fields[name] = TextEditingController(
        text: original[name]?.toString() ?? '',
      );
    }
    for (final name in ['start_date', 'end_date', 'due_date', 'entry_date']) {
      final source = original[name]?.toString();
      final date = source == null ? null : DateTime.tryParse(source);
      fields[name] = TextEditingController(
        text: date != null
            ? _dateLabel(date)
            : name == 'entry_date'
            ? _dateLabel(DateTime.now())
            : '',
      );
    }
    final now = DateTime.now();
    final defaultStart = DateTime(now.year, now.month, now.day, now.hour + 1);
    for (final name in ['start', 'end']) {
      final parsed = DateTime.tryParse(original['${name}_at']?.toString() ?? '')
          ?.toLocal();
      final date =
          parsed ??
          (name == 'start'
              ? defaultStart
              : defaultStart.add(const Duration(hours: 1)));
      fields['${name}_day'] = TextEditingController(text: _dateLabel(date));
      fields['${name}_time'] = TextEditingController(
        text: '${_two(date.hour)}:${_two(date.minute)}',
      );
    }
    for (final entry in {
      'phase': workspacePhaseLabels,
      'deposit_status': workspaceDepositLabels,
      'materials_status': workspaceMaterialsLabels,
      'priority': workspacePriorityLabels,
      'category': workspaceLinkCategoryLabels,
      'status': widget.kind == 'appointments'
          ? workspaceAppointmentStatusLabels
          : workspaceTaskStatusLabels,
    }.entries) {
      final stored = original[entry.key]?.toString();
      final fallback = switch (entry.key) {
        'phase' => 'planning',
        'deposit_status' => 'not_recorded',
        'materials_status' => 'not_recorded',
        'priority' => 'normal',
        'category' => 'document',
        _ => widget.kind == 'appointments' ? 'scheduled' : 'todo',
      };
      values[entry.key] = entry.value.containsKey(stored) ? stored! : fallback;
    }
    values['assignee_id'] = original['assignee_id']?.toString() ?? '';
    active = original['active'] is bool ? original['active'] as bool : true;
  }

  @override
  void didUpdateWidget(covariant _WorkspaceEditor oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.accessAllowed != widget.accessAllowed) {
      oldWidget.accessAllowed?.removeListener(accessChanged);
      widget.accessAllowed?.addListener(accessChanged);
      if (widget.accessAllowed?.value == false) accessLost = true;
    }
  }

  void accessChanged() {
    if (!mounted || widget.accessAllowed?.value != false) return;
    FocusManager.instance.primaryFocus?.unfocus();
    // Close this form's dropdown/date/comparison routes before removing their
    // owners. Dropdown disposal must not mutate Navigator while the tree locks.
    final route = ModalRoute.of(context);
    if (route != null && route.isActive && !route.isCurrent) {
      Navigator.of(context).popUntil((candidate) => candidate == route);
    }
    setState(() => accessLost = true);
  }

  @override
  void dispose() {
    widget.accessAllowed?.removeListener(accessChanged);
    for (final controller in fields.values) {
      controller.dispose();
    }
    scroll.dispose();
    super.dispose();
  }

  static String _two(int value) => value.toString().padLeft(2, '0');
  static String _dateLabel(DateTime value) =>
      '${_two(value.day)}.${_two(value.month)}.${value.year.toString().padLeft(4, '0')}';
  static String _dateValue(DateTime value) =>
      '${value.year.toString().padLeft(4, '0')}-${_two(value.month)}-${_two(value.day)}';

  DateTime? date(String key) {
    final value = fields[key]!.text.trim();
    final german = RegExp(r'^(\d{2})\.(\d{2})\.(\d{4})$').firstMatch(value);
    final iso = RegExp(r'^(\d{4})-(\d{2})-(\d{2})$').firstMatch(value);
    if (german == null && iso == null) return null;
    final year = int.parse((german?.group(3) ?? iso!.group(1))!);
    final month = int.parse((german?.group(2) ?? iso!.group(2))!);
    final day = int.parse((german?.group(1) ?? iso!.group(3))!);
    if (year < 1900 ||
        year > 2200 ||
        month < 1 ||
        month > 12 ||
        day < 1 ||
        day > 31)
      return null;
    final parsed = DateTime(year, month, day);
    return parsed.year == year && parsed.month == month && parsed.day == day
        ? parsed
        : null;
  }

  TimeOfDay? time(String key) {
    final match = RegExp(r'^(\d{1,2}):(\d{2})$')
        .firstMatch(fields[key]!.text.trim());
    if (match == null) return null;
    final hour = int.parse(match.group(1)!);
    final minute = int.parse(match.group(2)!);
    return hour < 24 && minute < 60
        ? TimeOfDay(hour: hour, minute: minute)
        : null;
  }

  DateTime? instant(String key) {
    final day = date('${key}_day');
    final clock = time('${key}_time');
    if (day == null || clock == null) return null;
    final existing = DateTime.tryParse(
      widget.initial?['${key}_at']?.toString() ?? '',
    )?.toLocal();
    if (existing != null &&
        existing.year == day.year &&
        existing.month == day.month &&
        existing.day == day.day &&
        existing.hour == clock.hour &&
        existing.minute == clock.minute) {
      return existing;
    }
    final result = DateTime(
      day.year,
      day.month,
      day.day,
      clock.hour,
      clock.minute,
    );
    // A local wall time skipped by daylight-saving time must be chosen anew.
    return result.year == day.year &&
            result.month == day.month &&
            result.day == day.day &&
            result.hour == clock.hour &&
            result.minute == clock.minute
        ? result
        : null;
  }

  String? dateError(String key, {bool required = false}) {
    if (fields[key]!.text.trim().isEmpty && !required) return null;
    return date(key) == null ? 'Gültiges Datum als TT.MM.JJJJ eingeben.' : null;
  }

  Future<void> pickDate(String key) async {
    if (!allowed || saving) return;
    final selected = await showDatePicker(
      context: context,
      initialDate: date(key) ?? DateTime.now(),
      firstDate: DateTime(1900),
      lastDate: DateTime(2200, 12, 31),
      helpText: 'Datum auswählen',
      cancelText: 'Abbrechen',
      confirmText: 'Übernehmen',
    );
    if (selected != null && mounted && allowed)
      setState(() => fields[key]!.text = _dateLabel(selected));
  }

  Future<void> pickTime(String key) async {
    if (!allowed || saving) return;
    final selected = await showTimePicker(
      context: context,
      initialTime: time(key) ?? TimeOfDay.now(),
      helpText: 'Uhrzeit auswählen',
      cancelText: 'Abbrechen',
      confirmText: 'Übernehmen',
      builder: (context, child) => MediaQuery(
        data: MediaQuery.of(context).copyWith(alwaysUse24HourFormat: true),
        child: child!,
      ),
    );
    if (selected != null && mounted && allowed)
      setState(
        () => fields[key]!.text =
            '${_two(selected.hour)}:${_two(selected.minute)}',
      );
  }

  Widget textField(
    String key,
    String label,
    int maximum, {
    bool required = false,
    int lines = 1,
    TextInputType? keyboard,
  }) => Padding(
    padding: const EdgeInsets.only(bottom: 16),
    child: TextFormField(
      key: ValueKey('workspace-field-$key'),
      controller: fields[key],
      enabled: !saving,
      minLines: lines,
      maxLines: lines == 1 ? 1 : lines + 3,
      maxLength: maximum,
      keyboardType:
          keyboard ??
          (lines > 1 ? TextInputType.multiline : TextInputType.text),
      autocorrect: key != 'url',
      decoration: InputDecoration(
        labelText: label,
        alignLabelWithHint: lines > 1,
      ),
      validator: (value) {
        final text = (value ?? '').trim();
        if (required && text.isEmpty) return '$label eingeben.';
        if (text.contains('\u0000'))
          return 'Dieses Zeichen ist nicht zulässig.';
        if (key == 'url' && !_validUrl(text))
          return 'Gültigen HTTPS-Link ohne eingebettete Zugangsdaten eingeben.';
        if (key == 'crew_count' && text.isNotEmpty) {
          final number = int.tryParse(text);
          if (number == null || number < 0 || number > 1000)
            return 'Ganze Anzahl von 0 bis 1000 eingeben.';
        }
        return null;
      },
    ),
  );

  static bool _validUrl(String value) {
    if (value.isEmpty ||
        RegExp(r'\s').hasMatch(value) ||
        value.runes.any((value) => value < 32 || value == 127))
      return false;
    try {
      final uri = Uri.tryParse(value);
      return uri != null &&
          uri.scheme == 'https' &&
          uri.host.isNotEmpty &&
          uri.userInfo.isEmpty &&
          (!uri.hasPort || uri.port >= 1 && uri.port <= 65535);
    } on FormatException {
      return false;
    }
  }

  Widget choice(String key, String label, Map<String, String> labels) =>
      Padding(
        padding: const EdgeInsets.only(bottom: 16),
        child: DropdownButtonFormField<String>(
          key: ValueKey('workspace-field-$key'),
          initialValue: values[key],
          isExpanded: true,
          decoration: InputDecoration(labelText: label),
          items: labels.entries
              .map(
                (entry) => DropdownMenuItem(
                  value: entry.key,
                  child: Text(entry.value, overflow: TextOverflow.ellipsis),
                ),
              )
              .toList(),
          onChanged: saving
              ? null
              : (value) => setState(() => values[key] = value!),
        ),
      );

  Widget dateField(String key, String label, {bool required = false}) =>
      Padding(
        padding: const EdgeInsets.only(bottom: 16),
        child: TextFormField(
          key: ValueKey('workspace-field-$key'),
          controller: fields[key],
          enabled: !saving,
          keyboardType: TextInputType.datetime,
          decoration: InputDecoration(
            labelText: label,
            hintText: 'TT.MM.JJJJ',
            suffixIcon: IconButton(
              tooltip: '$label auswählen',
              onPressed: saving ? null : () => pickDate(key),
              icon: const Icon(Icons.calendar_today_outlined),
            ),
          ),
          validator: (_) => dateError(key, required: required),
        ),
      );

  Widget timeField(String key, String label) => Padding(
    padding: const EdgeInsets.only(bottom: 16),
    child: TextFormField(
      key: ValueKey('workspace-field-$key'),
      controller: fields[key],
      enabled: !saving,
      keyboardType: TextInputType.datetime,
      decoration: InputDecoration(
        labelText: label,
        hintText: 'HH:MM',
        suffixIcon: IconButton(
          tooltip: '$label auswählen',
          onPressed: saving ? null : () => pickTime(key),
          icon: const Icon(Icons.schedule),
        ),
      ),
      validator: (_) =>
          time(key) == null ? 'Gültige Uhrzeit als HH:MM eingeben.' : null,
    ),
  );

  Widget assignee() {
    final selected = values['assignee_id']!;
    final original = widget.initial?['assignee_id']?.toString() ?? '';
    final originalMissing =
        original.isNotEmpty && !team.any((member) => member['id'] == original);
    return Padding(
      padding: const EdgeInsets.only(bottom: 16),
      child: DropdownButtonFormField<String>(
        key: const ValueKey('workspace-field-assignee_id'),
        initialValue: selected,
        isExpanded: true,
        decoration: const InputDecoration(labelText: 'Verantwortlich'),
        items: [
          const DropdownMenuItem(value: '', child: Text('Nicht zugewiesen')),
          for (final member in team)
            DropdownMenuItem(
              value: member['id'] as String,
              child: Text(
                member['email']?.toString() ?? 'Projektmitglied',
                overflow: TextOverflow.ellipsis,
              ),
            ),
          if (originalMissing)
            DropdownMenuItem(
              value: original,
              child: const Text('Nicht mehr im aktuellen Projektteam'),
            ),
        ],
        onChanged: saving
            ? null
            : (value) => setState(() => values['assignee_id'] = value!),
        validator: (value) =>
            value != null &&
                value.isNotEmpty &&
                value != original &&
                !team.any((member) => member['id'] == value)
            ? 'Aktive Person wählen oder Zuordnung entfernen.'
            : null,
      ),
    );
  }

  List<Widget> content() => switch (widget.kind) {
    'profile' => [
      const Padding(
        padding: EdgeInsets.only(bottom: 20),
        child: Text(
          'Phase, Anzahlung und Material können unabhängig gepflegt werden. Auch Aufmaß- und Serviceprojekte sind möglich.',
        ),
      ),
      textField('description', 'Projektbeschreibung', 10000, lines: 3),
      textField('site_address', 'Baustellenadresse', 2000, lines: 2),
      choice('phase', 'Projektphase', workspacePhaseLabels),
      choice('deposit_status', 'Anzahlung', workspaceDepositLabels),
      choice('materials_status', 'Material', workspaceMaterialsLabels),
      dateField('start_date', 'Geplanter Beginn (optional)'),
      dateField('end_date', 'Geplantes Ende (optional)'),
    ],
    'tasks' => [
      textField('title', 'Aufgabe', 200, required: true),
      textField('details', 'Beschreibung', 10000, lines: 3),
      assignee(),
      dateField('due_date', 'Fällig am (optional)'),
      choice('priority', 'Priorität', workspacePriorityLabels),
      choice('status', 'Aufgabenstatus', workspaceTaskStatusLabels),
    ],
    'diary' => [
      dateField('entry_date', 'Datum', required: true),
      textField(
        'work_performed',
        'Ausgeführte Arbeiten',
        10000,
        required: true,
        lines: 4,
      ),
      textField('issues', 'Probleme / Besonderheiten', 10000, lines: 3),
      textField('next_steps', 'Nächste Schritte', 5000, lines: 3),
      textField('weather', 'Wetter (optional)', 200),
      textField(
        'crew_count',
        'Personen vor Ort (optional)',
        4,
        keyboard: TextInputType.number,
      ),
    ],
    'appointments' => [
      textField('title', 'Termin', 200, required: true),
      textField('details', 'Beschreibung / Hinweise', 10000, lines: 3),
      const Padding(
        padding: EdgeInsets.only(bottom: 16),
        child: Text('Datum und Uhrzeit gelten in der Ortszeit dieses Geräts.'),
      ),
      dateField('start_day', 'Beginn – Datum', required: true),
      timeField('start_time', 'Beginn – Uhrzeit'),
      dateField('end_day', 'Ende – Datum', required: true),
      timeField('end_time', 'Ende – Uhrzeit'),
      choice('status', 'Terminstatus', workspaceAppointmentStatusLabels),
    ],
    _ => [
      textField('title', 'Bezeichnung', 200, required: true),
      choice('category', 'Dokumentart', workspaceLinkCategoryLabels),
      textField(
        'url',
        'HTTPS-Link',
        2048,
        required: true,
        keyboard: TextInputType.url,
      ),
      const Text(
        'Hier wird ein vorhandener Link hinterlegt. Es wird kein Dropbox-, sevdesk- oder anderes Konto verbunden.',
      ),
      SwitchListTile.adaptive(
        contentPadding: EdgeInsets.zero,
        title: const Text('Link im Projekt anzeigen'),
        value: active,
        onChanged: saving ? null : (value) => setState(() => active = value),
      ),
    ],
  };

  Map<String, dynamic> payload() {
    String text(String key) => fields[key]!.text.trim();
    String? day(String key) =>
        date(key) == null ? null : _dateValue(date(key)!);
    return switch (widget.kind) {
      'profile' => {
        'description': text('description'),
        'site_address': text('site_address'),
        'phase': values['phase'],
        'deposit_status': values['deposit_status'],
        'materials_status': values['materials_status'],
        'start_date': day('start_date'),
        'end_date': day('end_date'),
      },
      'tasks' => {
        'title': text('title'),
        'details': text('details'),
        'assignee_id': values['assignee_id']!.isEmpty
            ? null
            : values['assignee_id'],
        'due_date': day('due_date'),
        'priority': values['priority'],
        'status': values['status'],
      },
      'diary' => {
        'entry_date': day('entry_date'),
        'work_performed': text('work_performed'),
        'issues': text('issues'),
        'next_steps': text('next_steps'),
        'weather': text('weather'),
        'crew_count': text('crew_count').isEmpty
            ? null
            : int.parse(text('crew_count')),
      },
      'appointments' => {
        'title': text('title'),
        'details': text('details'),
        'status': values['status'],
        'start_at': instant('start')!.toUtc().toIso8601String(),
        'end_at': instant('end')!.toUtc().toIso8601String(),
      },
      _ => {
        'title': text('title'),
        'category': values['category'],
        'url': text('url'),
        'active': active,
      },
    };
  }

  Future<void> save() async {
    if (!allowed || saving || conflict) return;
    FocusScope.of(context).unfocus();
    final invalid = form.currentState!.validateGranularly();
    if (invalid.isNotEmpty) {
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (mounted) {
          Scrollable.ensureVisible(
            invalid.first.context,
            duration: const Duration(milliseconds: 180),
            alignment: .1,
          );
        }
      });
      return;
    }
    if (widget.kind == 'profile' &&
        date('start_date') != null &&
        date('end_date') != null &&
        date('end_date')!.isBefore(date('start_date')!)) {
      setState(
        () => error = 'Das geplante Ende muss am oder nach dem Beginn liegen.',
      );
      revealError();
      return;
    }
    if (widget.kind == 'appointments') {
      final start = instant('start'), end = instant('end');
      if (start == null || end == null || !end.isAfter(start)) {
        setState(
          () => error = start == null || end == null
              ? 'Diese Ortszeit ist ungültig. Bitte Datum und Uhrzeit prüfen.'
              : 'Das Terminende muss nach dem Beginn liegen.',
        );
        revealError();
        return;
      }
    }
    setState(() {
      saving = true;
      error = null;
      comparisonChecked = false;
    });
    try {
      await widget.onSave(payload());
      if (!mounted) return;
      setState(() => saving = false);
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (mounted && allowed) Navigator.pop(context, true);
      });
    } catch (exception) {
      if (!mounted) return;
      setState(() {
        saving = false;
        comparisonChecked = false;
        conflict = exception is ApiException && exception.status == 409;
        error = switch (exception) {
          ApiException(status: 409) => 'Der Eintrag wurde inzwischen geändert. Bitte zuerst die aktuelle Fassung neu laden und vergleichen. Ihre Eingaben bleiben hier erhalten.',
          ApiException(status: 401 || 403) => 'Anmeldung oder Projektzugriff fehlen. Ihre Eingaben bleiben erhalten; bitte zuerst wieder online anmelden.',
          ApiException(status: 0) => 'Speichern derzeit nicht möglich. Bitte Verbindung prüfen und erneut versuchen. Ihre Eingaben bleiben erhalten.',
          ApiException(:final status) when status >= 500 => 'Speichern derzeit nicht möglich. Bitte später erneut versuchen. Ihre Eingaben bleiben erhalten.',
          ApiException(:final message) => message,
          _ => 'Speichern nicht abgeschlossen. Ihre Eingaben bleiben erhalten. Bitte erneut versuchen.',
        };
      });
      revealError();
    }
  }

  Future<void> resolveConflict() async {
    final resolve = widget.onResolveConflict;
    if (!allowed || saving || !conflict || resolve == null) return;
    setState(() {
      saving = true;
      comparing = true;
    });
    try {
      final accepted = await resolve();
      if (!mounted || !allowed) return;
      setState(() {
        saving = false;
        if (!accepted) return;
        conflict = false;
        comparisonChecked = true;
        error = 'Aktuelle Fassung geprüft. Eigene Eingaben nochmals prüfen und speichern.';
      });
      revealError();
    } catch (_) {
      if (!mounted) return;
      setState(() {
        saving = false;
        error = 'Vergleich nicht abgeschlossen. Ihre Eingaben bleiben erhalten. Bitte die aktuelle Fassung prüfen.';
      });
      revealError();
    } finally {
      if (mounted) {
        setState(() {
          saving = false;
          comparing = false;
        });
      }
    }
  }

  void revealError() {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (mounted && scroll.hasClients) scroll.jumpTo(0);
    });
  }

  String get title => switch (widget.kind) {
    'profile' => 'Projektprofil bearbeiten',
    'tasks' =>
      widget.initial == null ? 'Aufgabe anlegen' : 'Aufgabe bearbeiten',
    'diary' =>
      widget.initial == null
          ? 'Bautagebuch ergänzen'
          : 'Tagebucheintrag bearbeiten',
    'appointments' =>
      widget.initial == null ? 'Termin anlegen' : 'Termin bearbeiten',
    _ =>
      widget.initial == null
          ? 'Dokumentlink hinzufügen'
          : 'Dokumentlink bearbeiten',
  };

  @override
  Widget build(BuildContext context) {
    if (!allowed) {
      return AlertDialog(
        title: const Text('Projektzugriff nicht verfügbar'),
        content: const Text(
          'Bitte schließen und den Projektzugriff erneut prüfen.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: const Text('Schließen'),
          ),
        ],
      );
    }
    return PopScope(
      canPop: !saving,
      child: AlertDialog(
        title: Text(title),
        content: SizedBox(
          width: 620,
          child: ScrollConfiguration(
            behavior: ScrollConfiguration.of(context)
                .copyWith(scrollbars: false),
            child: Scrollbar(
              controller: scroll,
              thumbVisibility: true,
              child: SingleChildScrollView(
                controller: scroll,
                padding: const EdgeInsets.only(right: 12),
                child: Form(
                  key: form,
                  child: Column(
                    mainAxisSize: MainAxisSize.min,
                    crossAxisAlignment: CrossAxisAlignment.stretch,
                    children: [
                      if (saving && !comparing)
                        const Padding(
                          padding: EdgeInsets.only(bottom: 16),
                          child: LinearProgressIndicator(),
                        ),
                      if (error != null)
                        Notice(error!, error: !comparisonChecked),
                      if (conflict && widget.onResolveConflict != null)
                        Padding(
                          padding: const EdgeInsets.only(bottom: 16),
                          child: OutlinedButton.icon(
                            onPressed: saving ? null : resolveConflict,
                            icon: const Icon(Icons.compare_arrows),
                            label: const Text('Andere Fassung prüfen'),
                          ),
                        ),
                      ...content(),
                    ],
                  ),
                ),
              ),
            ),
          ),
        ),
        actions: [
          TextButton(
            onPressed: saving ? null : () => Navigator.pop(context, false),
            child: const Text('Abbrechen'),
          ),
          FilledButton(
            onPressed: saving || conflict ? null : save,
            child: const Text('Speichern'),
          ),
        ],
      ),
    );
  }
}
